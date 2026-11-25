"""Alert grouping, deduplication and incident matching."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class AlertGroup:
    asset_id: str
    start: pd.Timestamp
    end: pd.Timestamp
    obs_ids: tuple[str, ...]
    peak_score: float


def group_alerts(meta: pd.DataFrame, scores: pd.Series, threshold: float, merge_gap_min: float) -> list[AlertGroup]:
    """Alert rows (score >= threshold) of one asset closer than merge_gap_min form ONE group (deduplication)."""
    flag = scores >= threshold
    rows = meta[flag.to_numpy()].assign(score=scores[flag].to_numpy())
    out: list[AlertGroup] = []
    gap = pd.Timedelta(minutes=merge_gap_min)
    for asset, g in rows.sort_values(["asset_id", "ts"]).groupby("asset_id"):
        cur: list[tuple[str, pd.Timestamp, float]] = []
        for oid, ts, sc in zip(g["obs_id"], g["ts"], g["score"]):
            if cur and ts - cur[-1][1] > gap:
                out.append(_mk(asset, cur))
                cur = []
            cur.append((oid, ts, float(sc)))
        if cur:
            out.append(_mk(asset, cur))
    return sorted(out, key=lambda a: (a.start, a.asset_id))


def _mk(asset: str, cur: list[tuple[str, pd.Timestamp, float]]) -> AlertGroup:
    return AlertGroup(asset, cur[0][1], cur[-1][1], tuple(c[0] for c in cur), max(c[2] for c in cur))


def match_incidents(groups: list[AlertGroup], labels: pd.DataFrame, grace_min: float) -> pd.DataFrame:
    """Each labeled (incident, asset) counts once. Matched if a group on that asset STARTS in [onset, end+grace].
    time_to_first_alert is measured from labeled onset on the data clock."""
    grace = pd.Timedelta(minutes=grace_min)
    rows = []
    for _, lab in labels.iterrows():
        hits = [g for g in groups if g.asset_id == lab["asset_id"] and lab["onset"] <= g.start <= lab["end"] + grace]
        first = min(hits, key=lambda g: g.start) if hits else None
        rows.append({"incident_id": lab["incident_id"], "asset_id": lab["asset_id"], "onset": lab["onset"],
                     "end": lab["end"], "detected": first is not None,
                     "first_alert_ts": first.start if first else pd.NaT,
                     "time_to_first_alert_min": ((first.start - lab["onset"]).total_seconds() / 60 if first else None),
                     "n_groups_matched": len(hits)})
    return pd.DataFrame(rows)


def unmatched_groups(groups: list[AlertGroup], labels: pd.DataFrame, grace_min: float) -> list[AlertGroup]:
    grace = pd.Timedelta(minutes=grace_min)
    keep = []
    for g in groups:
        ok = ((labels["asset_id"] == g.asset_id) & (labels["onset"] <= g.start) & (g.start <= labels["end"] + grace)).any()
        if not ok:
            keep.append(g)
    return keep
