from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from infra_defense import pipeline as P
from infra_defense.features import assert_feature_names_safe, assign_split, build_features, fit_baseline

T0 = pd.Timestamp("2026-01-01T00:00:00Z")


def stream(n=400, seed=0, gap=None):
    rng = np.random.default_rng(seed)
    ts = pd.date_range(T0, periods=n, freq="5min")
    df = pd.DataFrame({"ts": ts, "asset_id": "A", "sensor": "flow", "value": 10 + rng.normal(0, 1, n)})
    if gap:
        df = df.drop(df.index[gap[0]:gap[1]])
    return df.reset_index(drop=True)


def feats(df, train_end_steps=200):
    base = fit_baseline(df, df["ts"].iloc[0] + pd.Timedelta(minutes=5 * train_end_steps))
    return base, build_features(df, base, 12, 3, 5)


def test_score_at_t_uses_only_data_up_to_t():
    df = stream()
    _, a = feats(df)
    df2 = df.copy()
    df2.loc[df2["ts"] > df["ts"].iloc[300], "value"] += 100.0   # alter everything AFTER step 300
    base = fit_baseline(df2, df["ts"].iloc[0] + pd.Timedelta(minutes=1000))
    b = build_features(df2, base, 12, 3, 5)
    k = a.meta.index[a.meta["ts"] == df["ts"].iloc[300]][0]
    assert np.allclose(a.X.iloc[: k + 1].to_numpy(), b.X.iloc[: k + 1].to_numpy())


def test_baseline_uses_train_period_only():
    df = stream()
    b1, _ = feats(df)
    df2 = df.copy()
    df2.loc[200:, "value"] += 50          # change only post-training data
    b2, _ = feats(df2)
    assert b1.mean == b2.mean and b1.std == b2.std
    with pytest.raises(ValueError):
        fit_baseline(df, T0 - pd.Timedelta(days=1))


def test_missing_values_are_explicit_not_silent():
    df = stream(gap=(300, 330))
    _, fs = feats(df)
    gap_rows = fs.meta["ts"].between(T0 + pd.Timedelta(minutes=5 * 305), T0 + pd.Timedelta(minutes=5 * 325))
    assert len(fs.meta) == 400                                     # regular grid keeps the gap rows
    assert (fs.X.loc[gap_rows, "z_flow"] == 0).all()               # filled with baseline ...
    assert fs.X.loc[gap_rows, "window_missing_fraction"].iloc[-1] == 1.0   # ... but surfaced as its own feature
    assert fs.X["window_missing_fraction"].iloc[:290].max() == 0.0


def test_split_boundaries_are_chronological_and_half_open():
    ts = pd.Series(pd.to_datetime(["2026-01-01T00:00:00Z", "2026-01-05T23:55:00Z", "2026-01-06T00:00:00Z",
                                   "2026-01-07T23:55:00Z", "2026-01-08T00:00:00Z"], utc=True))
    s = assign_split(ts, T0, 5, 2)
    assert list(s) == ["train", "train", "dev", "dev", "test"]    # exactly day 5 -> dev, exactly day 7 -> test


def test_duplicate_observations_are_rejected_upstream():
    from infra_defense import schema as S
    d = stream(10)
    with pytest.raises(S.SchemaError):
        S.validate_readings(pd.concat([d, d.iloc[:1]]))


def test_feature_names_cannot_carry_labels(prepared):
    assert_feature_names_safe(list(prepared.fs.X.columns))
    with pytest.raises(ValueError):
        assert_feature_names_safe(["z_flow", "scenario_kind"])
    assert not (set(prepared.fs.X.columns) & {"asset_id", "ts", "obs_id", "label", "scenario_id", "incident_id"})


def test_flipping_labels_and_scenarios_does_not_change_features(bundle, cfg):
    p1 = P.prepare(bundle, cfg)
    b2 = type(bundle)(**{**bundle.__dict__})
    b2.labels = bundle.labels.assign(asset_id="ZZZ")
    b2.scenarios = bundle.scenarios.assign(kind="x")
    p2 = P.prepare(b2, cfg)
    assert p1.fs.X.equals(p2.fs.X) and p1.fs.meta.equals(p2.fs.meta)


def test_partitions_do_not_overlap_in_time(prepared):
    ts, sp = prepared.fs.meta["ts"], prepared.split
    assert ts[sp == "train"].max() < ts[sp == "dev"].min() and ts[sp == "dev"].max() < ts[sp == "test"].min()
    assert not (prepared.y[sp == "train"].any() or prepared.y[sp == "dev"].any())  # incidents live only in test
