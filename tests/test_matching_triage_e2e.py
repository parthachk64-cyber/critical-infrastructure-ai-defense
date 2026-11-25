from __future__ import annotations

import json

import pandas as pd
import pytest

from infra_defense import cli
from infra_defense.data.synthetic import write_fixtures
from infra_defense.evaluation.matching import AlertGroup, group_alerts, match_incidents, unmatched_groups
from infra_defense.schema import ALLOWED_ACTIONS
from infra_defense.triage import TriageStore, apply_reviews, case_id

T = pd.Timestamp("2026-01-10T00:00:00Z")


def meta(minutes, asset="A"):
    ts = [T + pd.Timedelta(minutes=m) for m in minutes]
    return pd.DataFrame({"obs_id": [f"{asset}@{m}" for m in minutes], "asset_id": asset, "ts": ts})


def test_alert_merge_gap_boundary_and_per_asset_grouping():
    m = pd.concat([meta([0, 30, 70]), meta([5], "B")], ignore_index=True)
    s = pd.Series([1.0] * len(m))
    g = group_alerts(m, s, 1.0, 30)
    a = [x for x in g if x.asset_id == "A"]
    assert len(a) == 2 and a[0].obs_ids == ("A@0", "A@30")          # exactly 30 min apart merges; 40 min apart splits
    assert [x.asset_id for x in g if x.asset_id == "B"] == ["B"]
    assert group_alerts(m, pd.Series([0.5] * len(m)), 1.0, 30) == []   # score == threshold alerts, below does not
    assert len(group_alerts(m, s, 1.0, 30)) == 3


def labels(onset=60, end=90):
    return pd.DataFrame([{"incident_id": "I1", "asset_id": "A", "onset": T + pd.Timedelta(minutes=onset),
                          "end": T + pd.Timedelta(minutes=end)}])


def grp(start, asset="A"):
    t = T + pd.Timedelta(minutes=start)
    return AlertGroup(asset, t, t, (f"{asset}@{start}",), 1.0)


def test_incident_matching_window_and_time_to_first_alert():
    ok = match_incidents([grp(75)], labels(), 30)
    assert bool(ok["detected"][0]) and ok["time_to_first_alert_min"][0] == 15.0
    assert bool(match_incidents([grp(120)], labels(), 30)["detected"][0])      # end + 30 grace is inclusive
    for g in (grp(59), grp(121), grp(75, "B")):                                # before onset / after grace / wrong asset
        r = match_incidents([g], labels(), 30)
        assert not bool(r["detected"][0]) and r["time_to_first_alert_min"][0] is None
    two = match_incidents([grp(65), grp(70)], labels(), 30)                   # counted once, earliest alert used
    assert len(two) == 1 and two["n_groups_matched"][0] == 2 and two["time_to_first_alert_min"][0] == 5.0


def test_unmatched_groups_are_the_false_alert_burden():
    un = unmatched_groups([grp(75), grp(300), grp(10, "B")], labels(), 30)
    assert [g.start for g in un] == [T + pd.Timedelta(minutes=300), T + pd.Timedelta(minutes=10)]


def test_case_ids_deterministic_and_store_idempotent(tmp_path, replayed):
    cases = replayed["cases"]["rule"]
    assert case_id("A", T, "v1", "detection") == case_id("A", T, "v1", "detection") != case_id("A", T, "v2", "detection")
    st = TriageStore(tmp_path / "cases.jsonl")
    s1 = st.upsert_many(cases)
    s2 = st.upsert_many(cases)
    s3 = st.upsert_many(cases + cases[:3])                                    # duplicates in one batch
    assert s1["inserted"] == len({c["case_id"] for c in cases}) and s2["inserted"] == 0 and s2["unchanged"] == s1["inserted"]
    assert s3["inserted"] == 0 and len(st.load()) == s1["inserted"]


def test_case_separates_observed_inferred_and_review(replayed):
    c = next(c for c in replayed["cases"]["rule"] if c["kind"] == "detection")
    assert {"observed", "inferred", "review", "evidence_ids", "detector_version", "created_at", "alert_ts"} <= set(c)
    assert c["inferred"]["meaning"].startswith("triage-priority") and "cause" in c["inferred"]["meaning"]
    assert c["recommended_action"] in ALLOWED_ACTIONS and c["evidence_ids"]
    assert all(r["review"] is None or r["review"]["decision"] in ALLOWED_ACTIONS for r in replayed["cases"]["rule"])


def test_review_latency_exists_only_with_valid_timestamp():
    case = {"case_id": "C", "asset_id": "A", "alert_ts": "2026-01-10T01:00:00Z", "review": None}
    rv = pd.DataFrame([{"reviewer_id": "r", "asset_id": "A", "window_start": T, "window_end": T + pd.Timedelta(hours=3),
                        "decision": "observation_continued", "decided_at": T + pd.Timedelta(hours=2), "note": ""}])
    assert apply_reviews([case], rv)[0]["review"]["review_latency_min"] == 60.0
    early = rv.assign(decided_at=T + pd.Timedelta(minutes=30))
    r = apply_reviews([case], early)[0]["review"]
    assert r["valid"] is False and r["review_latency_min"] is None
    assert apply_reviews([case], None)[0]["review"] is None
    bad = rv.assign(decision="shutdown_plant")
    assert apply_reviews([case], bad)[0]["review"]["valid"] is False


def case_in(replayed, det, asset, lo, hi):
    return [c for c in replayed["cases"][det] if c["asset_id"] == asset and lo <= pd.Timestamp(c["alert_ts"]) <= hi]


def test_maintenance_and_similar_incident_alert_alike_but_record_different_context(prepared, replayed):
    sc = prepared.bundle.scenarios.set_index("scenario_id")
    m, i = sc.loc["S-M1"], sc.loc["INC-2"]
    cm = case_in(replayed, "rule", "PUMP-01", m["start"], m["end"] + pd.Timedelta(minutes=30))
    ci = case_in(replayed, "rule", "PUMP-01", i["start"], i["end"] + pd.Timedelta(minutes=30))
    assert cm and ci                                                    # both look anomalous to the detector
    assert cm[0]["context"]["maintenance_window_id"] == "MW-1" and ci[0]["context"]["maintenance_window_id"] is None
    assert cm[0]["observed"]["peak_abs_z_by_sensor"]["flow"] > 10 and ci[0]["observed"]["peak_abs_z_by_sensor"]["flow"] > 10
    assert cm[0]["inferred"]["concern_posterior"] < ci[0]["inferred"]["concern_posterior"]
    assert cm[0]["review"]["decision"] == "benign_maintenance_confirmed" and ci[0]["review"]["decision"] == "escalation_recorded"
    assert cm[0]["recommended_action"] == ci[0]["recommended_action"] == "review_requested"   # the score alone decides nothing


def test_missing_sensor_surfaces_a_data_quality_case(prepared, replayed):
    s = prepared.bundle.scenarios.set_index("scenario_id").loc["S-D1"]
    q = [c for c in replayed["cases"]["rule"] if c["kind"] == "data_quality" and c["asset_id"] == "TANK-02"
         and s["start"] <= pd.Timestamp(c["alert_ts"]) <= s["end"]]
    assert q and q[0]["recommended_action"] == "telemetry_quality_check" and q[0]["inferred"] is None


def test_corroborating_assets_are_linked(prepared, replayed):
    s = prepared.bundle.scenarios.set_index("scenario_id").loc["INC-1"]
    cs = case_in(replayed, "rule", "VALVE-03", s["start"], s["end"]) + case_in(replayed, "rule", "FILTER-04", s["start"], s["end"])
    assert len(cs) >= 2 and all(c["context"]["corroborated_by_other_asset"] for c in cs)
    assert all(c["corroborating_evidence_ids"] for c in cs)


# ---- full CPU path through the public CLI -------------------------------------------------------------
@pytest.fixture(scope="module")
def run_dir(tmp_path_factory):
    d = tmp_path_factory.mktemp("e2e")
    run = d / "run"
    assert cli.main(["prepare", "--run", str(run)]) == 0
    assert cli.main(["fit", "--run", str(run)]) == 0
    assert cli.main(["replay", "--run", str(run)]) == 0
    assert cli.main(["evaluate", "--run", str(run)]) == 0
    assert cli.main(["figures", "--run", str(run)]) == 0
    assert cli.main(["report", "--run", str(run), "--out", str(d / "results.md")]) == 0
    return d


def test_end_to_end_artifacts_and_metrics(run_dir):
    run = run_dir / "run"
    for f in ("metrics.json", "manifest.json", "scores.csv", "cases_rule.jsonl", "cases_iforest.jsonl", "model/iforest.joblib",
              "incident_matches_rule.csv", "figures/fig1_workflow_original.png", "figures/fig_case_trace.png",
              "figures/fig6_companion_detection.png", "figures/fig4_companion_timing.png", "figures/fig5_bayes_example.png"):
        assert (run / f).exists(), f
    m = json.loads((run / "metrics.json").read_text())
    for d in ("rule", "iforest"):
        e = m["detectors"][d]["event"]
        assert e["tp"] + e["fn"] == m["test_positive_rows"] and e["rows"] == m["test_rows"]
        assert m["detectors"][d]["incident"]["incidents"] == 8
        assert "INC-3/VALVE-03" in m["detectors"][d]["incident"]["missed_ids"]      # deliberately small deviation is missed
    inc1 = pd.read_csv(run / "incident_matches_rule.csv")
    assert inc1[inc1["incident_id"] == "INC-1"]["detected"].all()
    man = json.loads((run / "manifest.json").read_text())
    assert man["dataset_id"] == "synthetic-fixtures" and man["model_sha256"] and "clock_conventions" in man
    assert "Synthetic demonstration" in (run_dir / "results.md").read_text() and "Not run" in (run_dir / "results.md").read_text()


def test_replay_twice_creates_no_new_cases(run_dir):
    run = run_dir / "run"
    before = (run / "cases_rule.jsonl").read_text()
    assert cli.main(["replay", "--run", str(run)]) == 0
    assert (run / "cases_rule.jsonl").read_text() == before


def test_fixtures_regenerate_byte_identically(tmp_path):
    from infra_defense.config import FIXTURE_DIR
    sums = write_fixtures(tmp_path)
    assert sums == json.loads((FIXTURE_DIR / "CHECKSUMS.json").read_text())["sha256"]


def test_data_check_and_unknown_dir(capsys, tmp_path):
    assert cli.main(["data-check"]) == 0
    assert "synthetic-fixtures" in capsys.readouterr().out
    assert cli.main(["data-check", "--data", str(tmp_path / "nope")]) == 2
