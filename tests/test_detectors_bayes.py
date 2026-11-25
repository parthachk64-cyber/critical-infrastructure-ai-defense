from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from infra_defense import bayes
from infra_defense.detectors.iforest import IsolationForestDetector, ModelIntegrityError, score_orientation_check
from infra_defense.detectors.rules import RuleDetector
from infra_defense.evaluation.metrics import average_precision, budget_threshold, confusion
from infra_defense.features import FeatureSet


def test_iforest_fit_is_seeded_and_requires_data(prepared):
    mask = (prepared.split == "train")
    a = IsolationForestDetector(50, 1).fit(prepared.fs, mask)
    b = IsolationForestDetector(50, 1).fit(prepared.fs, mask)
    assert np.allclose(a.score(prepared.fs), b.score(prepared.fs))
    with pytest.raises(ValueError):
        IsolationForestDetector().fit(prepared.fs, prepared.split == "nowhere")
    with pytest.raises(RuntimeError):
        IsolationForestDetector().score(prepared.fs)


def test_iforest_score_orientation_higher_is_more_anomalous(prepared, fitted):
    assert score_orientation_check(fitted["iforest"], prepared.fs)
    s = fitted["scores"]["iforest"]
    pos, neg = s[prepared.y], s[(~prepared.y) & (prepared.split == "test")]
    assert pos.median() > neg.median()


def test_model_persistence_roundtrip_and_tamper(prepared, fitted, tmp_path):
    meta = fitted["iforest"].save(tmp_path)
    loaded = IsolationForestDetector.load(tmp_path)
    assert np.allclose(loaded.score(prepared.fs), fitted["scores"]["iforest"]) and meta["orientation"] == "higher_is_more_anomalous"
    p = tmp_path / "iforest.joblib"
    p.write_bytes(p.read_bytes() + b"x")
    with pytest.raises(ModelIntegrityError):
        IsolationForestDetector.load(tmp_path)


def test_feature_column_mismatch_is_refused(prepared, fitted):
    fs = FeatureSet(prepared.fs.meta, prepared.fs.X.iloc[:, :-1], prepared.fs.absz)
    with pytest.raises(ValueError):
        fitted["iforest"].score(fs)


def test_rule_needs_persistence_single_spike_does_not_score():
    meta = pd.DataFrame({"asset_id": ["A"] * 5})
    fs = FeatureSet(meta, pd.DataFrame(index=range(5)), pd.Series([0.1, 9.0, 0.2, 9.0, 9.0]))
    s = RuleDetector(2).score(fs)
    assert list(s) == [0.1, 0.1, 0.2, 0.2, 9.0]           # only two consecutive high rows reach 9
    with pytest.raises(ValueError):
        RuleDetector(0)


def test_budget_threshold_uses_normal_dev_rows_only():
    scores = pd.Series(np.arange(100.0))
    pos = pd.Series([False] * 98 + [True] * 2)
    thr = budget_threshold(scores, pos, 0.05)
    assert (scores[~pos] >= thr).mean() <= 0.05
    assert thr == 94.0 and budget_threshold(pd.Series([1.0] * 10), pd.Series([False] * 10), 0.05) > 1.0   # ties: never exceed budget
    with pytest.raises(ValueError):
        budget_threshold(scores, pd.Series([True] * 100), 0.05)


def test_undefined_metrics_are_none_not_zero():
    c = confusion(np.array([0, 0, 0]), np.array([0, 0, 0]))
    assert c["precision"] is None and c["recall"] is None and c["f1"] is None and c["false_alert_rate"] == 0.0
    assert average_precision(np.array([0, 0]), np.array([0.1, 0.2])) is None
    assert average_precision(np.array([0, 1]), np.array([0.5, 0.5])) is None
    assert average_precision(np.array([0, 1]), np.array([0.1, 0.9])) == 1.0
    c = confusion(np.array([1, 1, 0, 0]), np.array([1, 0, 1, 0]))
    assert (c["tp"], c["fp"], c["fn"], c["tn"]) == (1, 1, 1, 1) and c["prevalence"] == 0.5


# ---- Bayesian example --------------------------------------------------------------------------
def test_cpts_normalised_and_posterior_hand_computed():
    bayes.validate()
    # M=no, K=high, A=yes, R unobserved:  .30*.85 / (.30*.85 + .70*.05) = .255 / .290
    assert bayes.posterior_high(maintenance=False, critical=True, anomaly=True) == pytest.approx(0.255 / 0.290)
    # with R=yes too: .30*.85*.60 / (.30*.85*.60 + .70*.05*.03)
    assert bayes.posterior_high(False, True, True, True) == pytest.approx(0.153 / (0.153 + 0.00105))


def test_missing_evidence_is_marginalised_not_assumed_no():
    prior = bayes.posterior_high()
    assert 0 < prior < 1
    manual = sum(bayes.P_M[m] * bayes.P_K[k] * bayes.P_C_HIGH[(m, k)] for m in (True, False) for k in (True, False))
    assert prior == pytest.approx(manual)
    assert bayes.posterior_high(anomaly=True) > prior > bayes.posterior_high(anomaly=False)
    assert bayes.posterior_high(anomaly=True, corroborated=None) > bayes.posterior_high(anomaly=True, corroborated=False)


def test_maintenance_lowers_concern_and_corroboration_raises_it():
    base = bayes.posterior_high(maintenance=False, critical=True, anomaly=True)
    assert bayes.posterior_high(maintenance=True, critical=True, anomaly=True) < base
    assert bayes.posterior_high(maintenance=False, critical=True, anomaly=True, corroborated=True) > base


def test_invalid_cpt_is_rejected(monkeypatch):
    monkeypatch.setitem(bayes.P_C_HIGH, (True, True), 1.5)
    with pytest.raises(ValueError):
        bayes.validate()
    monkeypatch.setitem(bayes.P_M, True, 0.5)
    with pytest.raises(ValueError):
        bayes.validate()


def test_cpt_tables_are_documented_frames():
    t = bayes.cpt_tables()
    assert set(t) == {"P(C|M,K)", "P(A|C)", "P(R|C)"} and len(t["P(C|M,K)"]) == 4
