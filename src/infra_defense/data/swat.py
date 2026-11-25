"""Adapter for owner-provided, authorized copies of iTrust SWaT (SWaT.A1_Dec 2015 first).

Source: https://www.sutd.edu.sg/itrust/itrust-labs/datasets/dataset-characteristics/swat/ (page checked 2026-11-25).
That page states: 11 days of continuous operation, 7 under normal operation and 4 days with attack scenarios;
all values from 51 sensors and actuators; data labelled normal/abnormal; 41 attacks launched in the 4 attack days.
This is a Singapore research testbed: no U.S. deployment evidence, not the article's data, not a substitute for it.

Conventions implemented (verify against your copy; the release is the authority):
* header names may carry spaces; the label column is ``Normal/Attack`` with values such as ``Normal``, ``Attack``,
  ``A ttack``; timestamps look like ``28/12/2015 10:00:00 AM`` and are kept as recorded (no timezone offset applied,
  stored with a nominal UTC tag so only ordering and differences are meaningful);
* attack intervals are the maximal runs of consecutive rows labelled attack. Rows of the last four days that are
  labelled normal stay normal: the days are NOT labelled positive wholesale;
* the release does not give per-asset ground truth in this file, so an interval is applied to every stage asset
  (P1..P6). That is a coarser label than the release's own attack descriptions and is a stated limitation.
Nothing here downloads data. Missing files raise; the CLI never falls back to generated data.
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from infra_defense import schema as S
from infra_defense.data.io import Bundle

ANALOG_PREFIXES = ("FIT", "LIT", "AIT", "DPIT", "PIT")
TS_FORMATS = ("%d/%m/%Y %I:%M:%S %p", "%d/%m/%Y %H:%M:%S", "%Y-%m-%d %H:%M:%S")


def _clean_columns(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [str(c).strip() for c in df.columns]
    return df


def _parse_ts(col: pd.Series) -> pd.Series:
    s = col.astype(str).str.strip()
    for fmt in TS_FORMATS:
        out = pd.to_datetime(s, format=fmt, errors="coerce")
        if out.notna().all():
            return out.dt.tz_localize("UTC")
    raise S.SchemaError("SWaT timestamps match none of the supported formats " + str(TS_FORMATS))


def _stage(tag: str) -> str | None:
    m = re.search(r"(\d)\d\d$", tag)
    return f"P{m.group(1)}" if m else None


def load_swat_csv(paths: list[Path | str], resample_minutes: int | None = None) -> Bundle:
    """Load one or more SWaT CSV files (e.g. Normal then Attack), ordered by time, into a Bundle."""
    if not paths:
        raise FileNotFoundError("no SWaT file given")
    frames = []
    for p in paths:
        if not Path(p).is_file():
            raise FileNotFoundError(f"SWaT file not found: {p}")
        df = _clean_columns(pd.read_csv(p, low_memory=False))
        if "Timestamp" not in df.columns or "Normal/Attack" not in df.columns:
            raise S.SchemaError(f"{p}: expected 'Timestamp' and 'Normal/Attack' columns")
        frames.append(df)
    df = pd.concat(frames, ignore_index=True)
    df["ts"] = _parse_ts(df["Timestamp"])
    df = df.sort_values("ts").reset_index(drop=True)
    if df["ts"].duplicated().any():
        raise S.SchemaError("duplicate timestamps across SWaT files")
    attack = df["Normal/Attack"].astype(str).str.replace(r"\s+", "", regex=True).str.lower().str.startswith("a")
    tags = [c for c in df.columns if c.startswith(ANALOG_PREFIXES) and _stage(c)]
    if not tags:
        raise S.SchemaError("no analog sensor columns (FIT/LIT/AIT/DPIT/PIT) found")
    wide = df[["ts"] + tags]
    if resample_minutes:  # the release is ~1 Hz; mean-resample to the analysis grid BEFORE melting (memory)
        wide = wide.set_index("ts").resample(f"{resample_minutes}min").mean().reset_index()
    long = wide.melt("ts", var_name="sensor", value_name="value").dropna(subset=["value"])
    long["asset_id"] = long["sensor"].map(_stage)
    readings = S.validate_readings(long[["ts", "asset_id", "sensor", "value"]])
    runs = (attack != attack.shift(fill_value=False)).cumsum()
    labels = []
    n = 0
    for _, g in df[attack].groupby(runs[attack]):
        n += 1
        for st in sorted({_stage(t) for t in tags}):
            labels.append({"incident_id": f"SWAT-RUN-{n:03d}", "asset_id": st, "onset": g["ts"].iloc[0], "end": g["ts"].iloc[-1]})
    assets = pd.DataFrame({"asset_id": sorted({_stage(t) for t in tags})})
    assets["criticality"], assets["stage"] = "unknown", assets["asset_id"].str[1:].astype(int)
    notes = [f"{len(df)} rows, {len(tags)} analog sensors, {int(attack.sum())} attack-labelled rows in {n} contiguous runs"]
    return Bundle(readings, assets, pd.DataFrame(columns=S.MAINTENANCE_COLUMNS),
                  pd.DataFrame(labels, columns=S.LABELS_COLUMNS) if labels else pd.DataFrame(columns=S.LABELS_COLUMNS),
                  None, None, source="swat:" + ",".join(str(p) for p in paths), notes=notes)


def write_format_fixture(path: Path | str, rows: int = 240) -> Path:
    """FICTIONAL values in SWaT's file layout, for schema tests only. Not SWaT data."""
    import numpy as np
    rng = np.random.default_rng(1)
    ts = pd.date_range("2015-12-28 10:00:00", periods=rows, freq="s")
    df = pd.DataFrame({
        "Timestamp": [t.strftime("%d/%m/%Y %I:%M:%S %p") for t in ts],
        " FIT101": rng.normal(2.5, 0.01, rows), " LIT101": rng.normal(500, 1, rows),
        " MV101": 2, "FIT201": rng.normal(2.4, 0.01, rows), "AIT201": rng.normal(250, 0.5, rows),
        "Normal/Attack": ["Normal"] * rows})
    df.loc[100:130, "Normal/Attack"] = "A ttack"
    df.to_csv(path, index=False)
    return Path(path)
