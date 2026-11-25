"""Analyst-review cases. ADVISORY ONLY: nothing here issues or implies a controller command.

Three kinds of information stay in separate fields:
  observed   recorded measurements (peak |z| per sensor, missing fraction), copied from the data
  inferred   model output (posterior concern from the illustrative Bayes example) -- never a cause or intent
  review     the analyst's disposition, with reviewer id and decision timestamp; absent until a human decides
Case ids are deterministic, so re-processing the same alert never creates a second case.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pandas as pd

from infra_defense import bayes
from infra_defense.evaluation.matching import AlertGroup, group_alerts
from infra_defense.features import FeatureSet
from infra_defense.schema import ALLOWED_ACTIONS


def case_id(asset_id: str, start: pd.Timestamp, detector_version: str, kind: str) -> str:
    raw = f"{kind}|{asset_id}|{start.strftime('%Y-%m-%dT%H:%M:%SZ')}|{detector_version}"
    return "CASE-" + hashlib.sha256(raw.encode()).hexdigest()[:12]


def _iso(ts: pd.Timestamp | None) -> str | None:
    return None if ts is None or pd.isna(ts) else ts.strftime("%Y-%m-%dT%H:%M:%SZ")


def _maintenance_window(maint: pd.DataFrame, asset: str, ts: pd.Timestamp) -> str | None:
    m = maint[(maint["asset_id"] == asset) & (maint["start"] <= ts) & (ts <= maint["end"])]
    return None if m.empty else str(m["window_id"].iloc[0])


def build_cases(groups: list[AlertGroup], fs: FeatureSet, scores: pd.Series, assets: pd.DataFrame, maint: pd.DataFrame,
                cfg: dict, detector_version: str) -> list[dict]:
    idx = {oid: i for i, oid in enumerate(fs.meta["obs_id"])}
    crit = dict(zip(assets["asset_id"], assets["criticality"]))
    corr = pd.Timedelta(minutes=cfg["corroboration_minutes"])
    zcols = [c for c in fs.X.columns if c.startswith("z_")]
    cases = []
    for g in groups:
        rows = [idx[o] for o in g.obs_ids]
        others = [o for o in groups if o.asset_id != g.asset_id and abs(o.start - g.start) <= corr]
        mw = _maintenance_window(maint, g.asset_id, g.start)
        k = crit.get(g.asset_id)
        post = bayes.posterior_high(maintenance=mw is not None, critical=None if k in (None, "unknown") else k == "high",
                                    anomaly=True, corroborated=bool(others))
        peaks = {c[2:]: float(fs.X.loc[rows, c].abs().max()) for c in zcols}
        cases.append({
            "case_id": case_id(g.asset_id, g.start, detector_version, "detection"), "kind": "detection",
            "asset_id": g.asset_id, "detector_version": detector_version, "bayes_version": bayes.VERSION,
            "first_evidence_ts": _iso(g.start), "alert_ts": _iso(g.start), "created_at": _iso(g.start),
            "evidence_ids": list(g.obs_ids), "corroborating_evidence_ids": sorted(o.obs_ids[0] for o in others),
            "peak_score": g.peak_score,
            "reason": f"detector score at or above the budget threshold on {len(g.obs_ids)} consecutive-ish observation(s)",
            "observed": {"peak_abs_z_by_sensor": peaks,
                         "window_missing_fraction_max": float(fs.X.loc[rows, "window_missing_fraction"].max())},
            "context": {"maintenance_window_id": mw, "criticality": k, "corroborated_by_other_asset": bool(others)},
            "inferred": {"concern_posterior": post, "provenance": bayes.PROVENANCE,
                         "meaning": "triage-priority index; does not establish cause or intent"},
            "recommended_action": "review_requested", "review": None})
    return cases


def build_quality_cases(fs: FeatureSet, cfg: dict, detector_version: str) -> list[dict]:
    thr = cfg["missing_fraction_quality_case"]
    groups = group_alerts(fs.meta, fs.X["window_missing_fraction"], thr, cfg["alert_merge_gap_minutes"])
    cases = []
    for g in groups:
        cases.append({
            "case_id": case_id(g.asset_id, g.start, detector_version, "data_quality"), "kind": "data_quality",
            "asset_id": g.asset_id, "detector_version": detector_version, "bayes_version": None,
            "first_evidence_ts": _iso(g.start), "alert_ts": _iso(g.start), "created_at": _iso(g.start),
            "evidence_ids": list(g.obs_ids), "corroborating_evidence_ids": [], "peak_score": g.peak_score,
            "reason": f"window missing fraction >= {thr}: telemetry gap, anomaly scores for this asset are less reliable",
            "observed": {"window_missing_fraction_max": g.peak_score}, "context": {},
            "inferred": None, "recommended_action": "telemetry_quality_check", "review": None})
    return cases


def apply_reviews(cases: list[dict], reviews: pd.DataFrame | None) -> list[dict]:
    """Attach the earliest valid reviewer decision whose window contains the case. Review latency exists only
    when a decision timestamp exists AND it is not earlier than the alert."""
    out = []
    for c in cases:
        c = dict(c)
        if reviews is not None and not reviews.empty:
            ts = pd.Timestamp(c["alert_ts"])
            m = reviews[(reviews["asset_id"] == c["asset_id"]) & (reviews["window_start"] <= ts) & (ts <= reviews["window_end"])]
            if not m.empty:
                r = m.sort_values("decided_at").iloc[0]
                valid = r["decision"] in ALLOWED_ACTIONS and r["decided_at"] >= ts
                c["review"] = {"reviewer_id": r["reviewer_id"], "decision": r["decision"], "decided_at": _iso(r["decided_at"]),
                               "note": r["note"], "valid": bool(valid),
                               "review_latency_min": ((r["decided_at"] - ts).total_seconds() / 60 if valid else None)}
        out.append(c)
    return out


class TriageStore:
    """Append-only JSONL keyed by case_id; upsert is idempotent."""

    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)

    def load(self) -> dict[str, dict]:
        if not self.path.exists():
            return {}
        return {c["case_id"]: c for c in (json.loads(x) for x in self.path.read_text(encoding="utf-8").splitlines() if x.strip())}

    def upsert_many(self, cases: list[dict]) -> dict[str, int]:
        cur = self.load()
        stats = {"inserted": 0, "unchanged": 0, "updated": 0}
        for c in cases:
            old = cur.get(c["case_id"])
            if old is None:
                stats["inserted"] += 1
            elif old == c:
                stats["unchanged"] += 1
                continue
            else:
                stats["updated"] += 1
            cur[c["case_id"]] = c
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text("".join(json.dumps(v, sort_keys=True) + "\n" for _, v in sorted(cur.items())),
                             encoding="utf-8", newline="\n")
        return stats
