"""Evidence-linked case traces: observation -> detector score -> alert -> case -> reviewer decision, with timestamps
on the DATA clock. Scenario annotations are used only to pick and explain examples, never as detector inputs."""

from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

EXAMPLES = [
    ("1_normal_operating_transition", "S-T2", "expected setpoint-style transition; may or may not alert"),
    ("2_scheduled_maintenance", "S-M1", "planned window MW-1 makes readings unusual; context must be recorded"),
    ("3_corroborated_incident", "INC-1", "two assets deviate together; warrants analyst review"),
    ("4_missing_sensor", "S-D1", "sensor stops reporting; data quality must be surfaced, not hidden"),
    ("5_incident_resembling_maintenance", "INC-2", "same shape as example 2 but no maintenance window"),
]


def _iso(ts) -> str:
    return pd.Timestamp(ts).strftime("%Y-%m-%dT%H:%M:%SZ")


def build_trace(p, fitted: dict, replayed: dict, name: str, scenario_id: str, why: str) -> dict:
    scen = p.bundle.scenarios[p.bundle.scenarios["scenario_id"] == scenario_id].iloc[0]
    assets = scen["asset_ids"].split(";")
    lo, hi = scen["start"] - pd.Timedelta(minutes=10), scen["end"] + pd.Timedelta(minutes=30)
    meta = p.fs.meta
    inwin = (meta["ts"] >= lo) & (meta["ts"] <= hi) & meta["asset_id"].isin(assets)
    out = {"example": name, "why_chosen": why,
           "annotation_note": "scenario fields below are evaluation annotations; detectors never receive them",
           "scenario": {"scenario_id": scenario_id, "kind": scen["kind"], "assets": assets,
                        "start": _iso(scen["start"]), "end": _iso(scen["end"])},
           "clock": "data clock (UTC timestamps of the input files). No review wall-clock time exists.", "detectors": {}}
    for det in ("rule", "iforest"):
        s = fitted["scores"][det]
        thr = fitted["thresholds"][det]
        cases = [c for c in replayed["cases"][det]
                 if c["asset_id"] in assets and lo <= pd.Timestamp(c["alert_ts"]) <= hi]
        out["detectors"][det] = {
            "threshold": thr, "peak_score_in_window": float(s[inwin].max()) if inwin.any() else None,
            "rows_at_or_above_threshold": int((s[inwin] >= thr).sum()), "outcome": (
                "alert_and_case" if cases else "no_alert_raised"),
            "cases": cases,
            "timeline": [{"case_id": c["case_id"], "first_evidence_ts": c["first_evidence_ts"], "alert_ts": c["alert_ts"],
                          "case_created_at": c["created_at"],
                          "review_decided_at": (c["review"] or {}).get("decided_at"),
                          "review_latency_min": (c["review"] or {}).get("review_latency_min")} for c in cases]}
    r = p.bundle.readings
    obs = r[(r["asset_id"].isin(assets)) & (r["ts"] >= lo) & (r["ts"] <= hi)]
    out["recorded_observations_sample"] = [{"ts": _iso(a.ts), "asset_id": a.asset_id, "sensor": a.sensor,
                                            "value": None if pd.isna(a.value) else float(a.value)}
                                           for a in obs.iloc[:: max(1, len(obs) // 40)].itertuples()]
    out["recorded_observation_count_in_window"] = int(len(obs))
    out["expected_rows_in_window"] = int(inwin.sum()) * len(p.baseline.sensors)
    return out


def export_traces(p, fitted: dict, replayed: dict, out_dir: Path) -> list[dict]:
    d = Path(out_dir) / "traces"
    d.mkdir(parents=True, exist_ok=True)
    traces = []
    for name, sid, why in EXAMPLES:
        t = build_trace(p, fitted, replayed, name, sid, why)
        (d / f"{name}.json").write_text(json.dumps(t, indent=1, sort_keys=True, default=str), encoding="utf-8")
        traces.append(t)
    return traces
