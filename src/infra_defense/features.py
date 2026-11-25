"""Per-asset features. A score issued at time t uses only observations with ts <= t.

Window = ``window_steps`` past grid steps including the current one. Baseline (mean/std per asset+sensor) is fitted
on TRAIN-period rows only. Missing readings stay NaN until the very end: z-values are filled with 0 (the baseline)
AFTER computing the window missing fraction, which is exposed as its own feature so the model can see data quality.
Fixture names, scenario ids and labels never enter the matrix (checked by ``assert_feature_names_safe``).
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from infra_defense.schema import feature_name_is_safe


@dataclass(frozen=True)
class Baseline:
    mean: dict[tuple[str, str], float]
    std: dict[tuple[str, str], float]
    sensors: tuple[str, ...]

    def to_dict(self) -> dict:
        return {"mean": {f"{a}|{s}": v for (a, s), v in self.mean.items()},
                "std": {f"{a}|{s}": v for (a, s), v in self.std.items()}, "sensors": list(self.sensors)}


@dataclass
class FeatureSet:
    meta: pd.DataFrame  # obs_id, asset_id, ts   (row-aligned with X)
    X: pd.DataFrame     # numeric feature matrix
    absz: pd.Series     # max_s |z_s| at each row (input to the rule baseline)


def fit_baseline(readings: pd.DataFrame, t_end: pd.Timestamp, min_std: float = 1e-6) -> Baseline:
    tr = readings[(readings["ts"] < t_end) & readings["value"].notna()]
    if tr.empty:
        raise ValueError("no training readings before the training cutoff")
    g = tr.groupby(["asset_id", "sensor"])["value"]
    mean, std = g.mean(), g.std(ddof=0).clip(lower=min_std)
    return Baseline(mean.to_dict(), std.to_dict(), tuple(sorted(readings["sensor"].unique())))


def to_grid(readings: pd.DataFrame, step_minutes: int) -> pd.DataFrame:
    """Wide frame indexed by (asset_id, ts) on a regular grid; absent readings become NaN rows/cells."""
    t0, t1 = readings["ts"].min(), readings["ts"].max()
    grid = pd.date_range(t0.floor(f"{step_minutes}min"), t1, freq=f"{step_minutes}min", tz="UTC")
    r = readings.copy()
    r["ts"] = r["ts"].dt.floor(f"{step_minutes}min")
    wide = r.groupby(["asset_id", "ts", "sensor"])["value"].mean().unstack("sensor")
    idx = pd.MultiIndex.from_product([sorted(r["asset_id"].unique()), grid], names=["asset_id", "ts"])
    return wide.reindex(idx)


def feature_names(sensors: tuple[str, ...]) -> list[str]:
    cols = [f"{k}_{s}" for s in sensors for k in ("z", "rollmean_z", "rollstd_z", "delta_z")]
    return cols + ["window_missing_fraction"]


def assert_feature_names_safe(names: list[str]) -> None:
    bad = [n for n in names if not feature_name_is_safe(n)]
    if bad:
        raise ValueError(f"feature names look like labels/annotations: {bad}")


def build_features(readings: pd.DataFrame, baseline: Baseline, window_steps: int, delta_steps: int,
                   step_minutes: int) -> FeatureSet:
    wide = to_grid(readings, step_minutes)
    sensors = baseline.sensors
    for s in sensors:
        if s not in wide.columns:
            wide[s] = np.nan
    parts = []
    for asset, g in wide.groupby(level="asset_id", sort=True):
        g = g.droplevel("asset_id")
        cols: dict[str, pd.Series] = {}
        zs = {}
        for s in sensors:
            mu, sd = baseline.mean.get((asset, s), np.nan), baseline.std.get((asset, s), np.nan)
            z = (g[s] - mu) / sd if not np.isnan(mu) else pd.Series(np.nan, index=g.index)
            zs[s] = z
            cols[f"z_{s}"] = z
            cols[f"rollmean_z_{s}"] = z.rolling(window_steps, min_periods=1).mean()
            cols[f"rollstd_z_{s}"] = z.rolling(window_steps, min_periods=2).std(ddof=0)
            cols[f"delta_z_{s}"] = z - z.shift(delta_steps)
        isn = pd.concat([zs[s].isna() for s in sensors], axis=1).mean(axis=1)
        cols["window_missing_fraction"] = isn.rolling(window_steps, min_periods=1).mean()
        f = pd.DataFrame(cols).fillna(0.0)
        f["asset_id"] = asset
        parts.append((f, pd.concat([zs[s].abs() for s in sensors], axis=1).max(axis=1).fillna(0.0)))
    X = pd.concat([p[0] for p in parts])
    az = pd.concat([p[1] for p in parts])
    meta = X[["asset_id"]].reset_index()
    meta.columns = ["ts", "asset_id"]
    meta["obs_id"] = meta["asset_id"] + "@" + meta["ts"].dt.strftime("%Y-%m-%dT%H:%M:%SZ")
    meta = meta[["obs_id", "asset_id", "ts"]].reset_index(drop=True)
    names = feature_names(sensors)
    assert_feature_names_safe(names)
    return FeatureSet(meta, X[names].reset_index(drop=True), az.reset_index(drop=True))


def assign_split(ts: pd.Series, t0: pd.Timestamp, train_days: float, dev_days: float) -> pd.Series:
    """Chronological partition by time since stream start: [0,train) train, [train,train+dev) dev, rest test."""
    days = (ts - t0).dt.total_seconds() / 86400.0
    return pd.Series(np.where(days < train_days, "train", np.where(days < train_days + dev_days, "dev", "test")),
                     index=ts.index)
