"""Deterministic synthetic fixtures. FICTIONAL assets, abstract status only. For verifying software and metric
behaviour; they are NOT a model of any real facility and NOT the article's data."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd

from infra_defense.config import sha256_file

T0 = pd.Timestamp("2026-01-05T00:00:00Z")
STEP_MIN = 5
DAYS = 14
STEPS = DAYS * 24 * 60 // STEP_MIN
ASSETS = [("PUMP-01", "high", 1), ("TANK-02", "low", 1), ("VALVE-03", "high", 2), ("FILTER-04", "low", 2)]
BASE = {"flow": (100.0, 3.0, 1.5), "pressure": (50.0, 1.5, 0.8)}  # mean, diurnal amplitude, AR noise sigma
SEED = 20260325


def _t(day: float) -> pd.Timestamp:
    return T0 + pd.Timedelta(minutes=round(day * 24 * 60))


def _bump(n: int, start: int, ramp: int, hold: int, amp: float) -> np.ndarray:
    out = np.zeros(n)
    up = np.linspace(0, amp, ramp + 1)[1:] if ramp else np.array([])
    shape = np.concatenate([up, np.full(hold, amp), up[::-1] if ramp else np.array([])])
    end = min(n, start + len(shape))
    out[start:end] = shape[: end - start]
    return out


def _series(rng: np.random.Generator, sensor: str) -> np.ndarray:
    mean, amp, sig = BASE[sensor]
    t = np.arange(STEPS)
    x = mean + amp * np.sin(2 * np.pi * t / (24 * 60 / STEP_MIN) + rng.uniform(0, 6.28))
    e = np.zeros(STEPS)
    for i in range(1, STEPS):
        e[i] = 0.6 * e[i - 1] + rng.normal(0, sig)
    return x + e


# (kind, scenario_id, [(asset, sensor, delta)], start_day, duration_min, ramp_steps)
SCENARIOS = [
    ("normal_transition", "S-T1", [("TANK-02", "flow", 4.0)], 6.2, 420, 12),
    ("normal_transition", "S-T2", [("TANK-02", "flow", 4.0)], 8.3, 420, 12),
    ("normal_transition", "S-T3", [("FILTER-04", "pressure", 3.0)], 12.8, 360, 12),
    ("data_gap", "S-D1", [("TANK-02", "pressure", None)], 9.0, 180, 0),
    ("maintenance", "S-M1", [("PUMP-01", "flow", -70.0)], 9.5, 120, 1),
    ("incident", "INC-5", [("TANK-02", "flow", -9.0)], 7.6, 60, 1),
    ("incident", "INC-1", [("VALVE-03", "pressure", 8.0), ("FILTER-04", "flow", -16.0)], 10.3, 90, 1),
    ("incident", "INC-4", [("PUMP-01", "pressure", 7.0)], 11.1, 60, 1),
    ("incident", "INC-2", [("PUMP-01", "flow", -70.0)], 12.2, 120, 1),
    ("incident", "INC-3", [("VALVE-03", "flow", 3.0)], 13.2, 60, 1),
    ("incident", "INC-6", [("FILTER-04", "pressure", -6.0), ("VALVE-03", "flow", -8.0)], 13.6, 75, 1),
]


def generate(seed: int = SEED) -> dict[str, pd.DataFrame]:
    rng = np.random.default_rng(seed)
    grid = pd.date_range(T0, periods=STEPS, freq=f"{STEP_MIN}min")
    series = {(a, s): _series(rng, s) for a, _, _ in ASSETS for s in BASE}
    missing: dict[tuple[str, str], np.ndarray] = {}
    labels, scen_rows = [], []
    for kind, sid, effects, day, dur, ramp in SCENARIOS:
        start = int(round(day * 24 * 60 / STEP_MIN))
        hold = dur // STEP_MIN
        end_ts = grid[start + hold - 1]
        assets = []
        for a, s, delta in effects:
            assets.append(a)
            if delta is None:
                m = np.zeros(STEPS, bool)
                m[start:start + hold] = True
                missing[(a, s)] = m
            else:
                series[(a, s)] = series[(a, s)] + _bump(STEPS, start, ramp, hold, delta)
            if kind == "incident":
                labels.append({"incident_id": sid, "asset_id": a, "onset": grid[start], "end": end_ts})
        scen_rows.append({"scenario_id": sid, "kind": kind, "asset_ids": ";".join(assets),
                          "start": grid[start], "end": end_ts})
    rows = []
    for (a, s), v in series.items():
        vals = np.round(v, 3)
        mask = missing.get((a, s), np.zeros(STEPS, bool))
        keep = ~mask  # missing sensor = reading absent from the file
        rows.append(pd.DataFrame({"ts": grid[keep], "asset_id": a, "sensor": s, "value": vals[keep]}))
    readings = pd.concat(rows).sort_values(["ts", "asset_id", "sensor"]).reset_index(drop=True)
    assets_df = pd.DataFrame(ASSETS, columns=["asset_id", "criticality", "stage"])
    maint = pd.DataFrame([{"window_id": "MW-1", "asset_id": "PUMP-01", "start": _t(9.4), "end": _t(9.7)}])
    labels_df = pd.DataFrame(labels)
    scen_df = pd.DataFrame(scen_rows)
    reviews = _reviews(scen_df)
    return {"readings": readings, "assets": assets_df, "maintenance": maint, "labels": labels_df,
            "scenarios": scen_df, "reviews": reviews}


def _reviews(scen: pd.DataFrame) -> pd.DataFrame:
    """Pre-authored, SIMULATED analyst dispositions (fictional reviewer) used by the demo."""
    who = "analyst-01 (simulated, fictional)"
    plan = {"incident": ("escalation_recorded", 40, "corroborating deviation; escalation recorded, no cause asserted"),
            "maintenance": ("benign_maintenance_confirmed", 30, "matches planned window MW-1"),
            "normal_transition": ("observation_continued", 45, "expected operating transition; keep observing"),
            "data_gap": ("telemetry_quality_check", 20, "sensor reading absent; quality check requested")}
    rows = []
    for _, r in scen.iterrows():
        if r["scenario_id"] == "INC-3":  # stealth incident: no alert expected, so no reviewer record
            continue
        dec, delay, note = plan[r["kind"]]
        for a in r["asset_ids"].split(";"):
            rows.append({"reviewer_id": who, "asset_id": a, "window_start": r["start"] - pd.Timedelta(minutes=10),
                         "window_end": r["end"] + pd.Timedelta(minutes=30), "decision": dec,
                         "decided_at": r["start"] + pd.Timedelta(minutes=delay + 60), "note": note})
    return pd.DataFrame(rows)


def write_fixtures(out_dir: Path | str, seed: int = SEED) -> dict[str, str]:
    d = Path(out_dir)
    d.mkdir(parents=True, exist_ok=True)
    data = generate(seed)
    for name, df in data.items():
        df.to_csv(d / f"{name}.csv", index=False, date_format="%Y-%m-%dT%H:%M:%SZ", lineterminator="\n")
    sums = {f"{n}.csv": sha256_file(d / f"{n}.csv") for n in data}
    (d / "CHECKSUMS.json").write_text(json.dumps({"seed": seed, "sha256": sums}, indent=1, sort_keys=True) + "\n",
                                      encoding="utf-8", newline="\n")
    return sums
