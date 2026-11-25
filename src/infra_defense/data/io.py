"""Local CSV/JSONL ingest. Never fetches anything; never substitutes generated data."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path

import pandas as pd

from infra_defense import schema as S


@dataclass
class Bundle:
    readings: pd.DataFrame
    assets: pd.DataFrame
    maintenance: pd.DataFrame
    labels: pd.DataFrame | None = None
    scenarios: pd.DataFrame | None = None
    reviews: pd.DataFrame | None = None
    source: str = ""
    notes: list[str] = field(default_factory=list)


def read_table(path: Path | str) -> pd.DataFrame:
    p = Path(path)
    if p.suffix == ".jsonl":
        return pd.read_json(p, lines=True)
    if p.suffix == ".csv":
        return pd.read_csv(p)
    raise S.SchemaError(f"unsupported file type: {p.suffix}")


def _opt(d: Path, name: str) -> pd.DataFrame | None:
    for ext in (".csv", ".jsonl"):
        if (d / f"{name}{ext}").exists():
            return read_table(d / f"{name}{ext}")
    return None


def load_bundle(directory: Path | str, require_labels: bool = False) -> Bundle:
    d = Path(directory)
    if not d.is_dir():
        raise FileNotFoundError(f"data directory not found: {d}")
    readings = _opt(d, "readings")
    if readings is None:
        raise FileNotFoundError(f"{d}: readings.csv/jsonl missing")
    assets = _opt(d, "assets")
    if assets is None:
        raise FileNotFoundError(f"{d}: assets.csv/jsonl missing")
    S.require_columns(assets, S.ASSETS_COLUMNS, "assets")
    maint = _opt(d, "maintenance")
    maint = (S.validate_intervals(maint, S.MAINTENANCE_COLUMNS, "start", "end", "maintenance")
             if maint is not None else pd.DataFrame(columns=S.MAINTENANCE_COLUMNS))
    labels = _opt(d, "labels")
    if labels is None and require_labels:
        raise FileNotFoundError(f"{d}: labels.csv missing (needed to fit/evaluate)")
    if labels is not None:
        labels = S.validate_intervals(labels, S.LABELS_COLUMNS, "onset", "end", "labels")
    scen = _opt(d, "scenarios")
    if scen is not None:
        scen = S.validate_intervals(scen, S.SCENARIOS_COLUMNS, "start", "end", "scenarios")
    rev = _opt(d, "reviews")
    if rev is not None:
        rev = S.validate_intervals(rev, S.REVIEWS_COLUMNS, "window_start", "window_end", "reviews")
        rev["decided_at"] = pd.to_datetime(rev["decided_at"], utc=True)
    return Bundle(S.validate_readings(readings), assets, maint, labels, scen, rev, source=str(d))
