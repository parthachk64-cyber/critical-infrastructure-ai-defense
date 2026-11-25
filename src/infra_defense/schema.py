"""File schemas. Observations carry NO labels; labels, scenarios and context are separate files."""

from __future__ import annotations

import pandas as pd

READINGS_COLUMNS = ["ts", "asset_id", "sensor", "value"]
ASSETS_COLUMNS = ["asset_id", "criticality", "stage"]
MAINTENANCE_COLUMNS = ["window_id", "asset_id", "start", "end"]
LABELS_COLUMNS = ["incident_id", "asset_id", "onset", "end"]          # annotation, never a feature
SCENARIOS_COLUMNS = ["scenario_id", "kind", "asset_ids", "start", "end"]  # annotation, never a feature
REVIEWS_COLUMNS = ["reviewer_id", "asset_id", "window_start", "window_end", "decision", "decided_at", "note"]
LEAKY_NAME_PARTS = ("label", "scenario", "incident", "kind", "maintenance_id", "decision")
ALLOWED_ACTIONS = ("review_requested", "telemetry_quality_check", "observation_continued",
                   "benign_maintenance_confirmed", "escalation_recorded")


class SchemaError(ValueError):
    pass


def require_columns(df: pd.DataFrame, cols: list[str], name: str) -> None:
    missing = [c for c in cols if c not in df.columns]
    if missing:
        raise SchemaError(f"{name}: missing columns {missing}")


def validate_readings(df: pd.DataFrame) -> pd.DataFrame:
    """Return a clean copy: UTC timestamps, float values (NaN = missing), duplicates rejected."""
    require_columns(df, READINGS_COLUMNS, "readings")
    out = df[READINGS_COLUMNS].copy()
    out["ts"] = pd.to_datetime(out["ts"], utc=True, errors="coerce")
    if out["ts"].isna().any():
        raise SchemaError("readings: unparseable timestamp")
    out["value"] = pd.to_numeric(out["value"], errors="coerce")
    if out.duplicated(["ts", "asset_id", "sensor"]).any():
        raise SchemaError("readings: duplicate (ts, asset_id, sensor)")
    if out["asset_id"].isna().any() or out["sensor"].isna().any():
        raise SchemaError("readings: null asset_id/sensor")
    return out.sort_values(["asset_id", "sensor", "ts"]).reset_index(drop=True)


def validate_intervals(df: pd.DataFrame, cols: list[str], start: str, end: str, name: str) -> pd.DataFrame:
    require_columns(df, cols, name)
    out = df.copy()
    for c in (start, end):
        out[c] = pd.to_datetime(out[c], utc=True, errors="coerce")
    if out[[start, end]].isna().any().any():
        raise SchemaError(f"{name}: unparseable timestamp")
    if (out[end] < out[start]).any():
        raise SchemaError(f"{name}: end precedes start")
    return out


def feature_name_is_safe(name: str) -> bool:
    return not any(p in name.lower() for p in LEAKY_NAME_PARTS)
