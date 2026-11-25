from __future__ import annotations

import pandas as pd
import pytest

from infra_defense import cli
from infra_defense import schema as S
from infra_defense.data.io import load_bundle
from infra_defense.data.swat import load_swat_csv, write_format_fixture


def readings(**over):
    df = pd.DataFrame({"ts": ["2026-01-01T00:00:00Z", "2026-01-01T00:05:00Z"], "asset_id": ["A", "A"],
                       "sensor": ["flow", "flow"], "value": [1.0, 2.0]})
    for k, v in over.items():
        df[k] = v
    return df


def test_validate_readings_ok_and_sorted():
    out = S.validate_readings(readings().iloc[::-1])
    assert list(out["value"]) == [1.0, 2.0] and str(out["ts"].dt.tz) == "UTC"


@pytest.mark.parametrize("bad,err", [({"ts": ["nope", "2026-01-01T00:05:00Z"]}, "unparseable"),
                                     ({"ts": ["2026-01-01T00:00:00Z"] * 2}, "duplicate")])
def test_validate_readings_rejects(bad, err):
    with pytest.raises(S.SchemaError, match=err):
        S.validate_readings(readings(**bad))


def test_missing_values_become_nan_and_columns_required():
    out = S.validate_readings(readings(value=["x", 2.0]))
    assert out["value"].isna().sum() == 1
    with pytest.raises(S.SchemaError):
        S.validate_readings(readings().drop(columns="sensor"))


def test_intervals_validated():
    df = pd.DataFrame({"incident_id": ["I"], "asset_id": ["A"], "onset": ["2026-01-02T00:00:00Z"], "end": ["2026-01-01T00:00:00Z"]})
    with pytest.raises(S.SchemaError, match="end precedes start"):
        S.validate_intervals(df, S.LABELS_COLUMNS, "onset", "end", "labels")


def test_load_bundle_errors_and_jsonl(tmp_path):
    with pytest.raises(FileNotFoundError):
        load_bundle(tmp_path / "missing")
    with pytest.raises(FileNotFoundError, match="readings"):
        load_bundle(tmp_path)
    readings().to_json(tmp_path / "readings.jsonl", orient="records", lines=True)
    pd.DataFrame({"asset_id": ["A"], "criticality": ["high"], "stage": [1]}).to_csv(tmp_path / "assets.csv", index=False)
    b = load_bundle(tmp_path)
    assert len(b.readings) == 2 and b.labels is None and b.maintenance.empty
    with pytest.raises(FileNotFoundError, match="labels"):
        load_bundle(tmp_path, require_labels=True)


def test_fixture_bundle_has_separate_label_files(bundle):
    assert set(bundle.readings.columns) == set(S.READINGS_COLUMNS)
    assert bundle.labels is not None and bundle.scenarios is not None and bundle.reviews is not None


# ---- SWaT adapter (FICTIONAL values in SWaT's layout) ----------------------------------------------
def test_swat_format_loader(tmp_path):
    f = write_format_fixture(tmp_path / "swat_like.csv", rows=240)
    b = load_swat_csv([f])
    assert set(b.readings["asset_id"]) == {"P1", "P2"}              # stage from tag digit
    assert "MV101" not in set(b.readings["sensor"])                  # actuator column excluded
    assert b.readings["ts"].is_monotonic_increasing or b.readings.sort_values("ts")["ts"].iloc[0] == b.readings["ts"].min()
    lab = b.labels[b.labels["asset_id"] == "P1"]
    assert len(lab) == 1 and (lab["end"] - lab["onset"]).iloc[0] == pd.Timedelta(seconds=30)  # 'A ttack' normalised
    assert "31 attack-labelled rows" in b.notes[0]


def test_swat_normal_rows_stay_normal_not_whole_tail_positive(tmp_path):
    f = write_format_fixture(tmp_path / "s.csv", rows=240)
    b = load_swat_csv([f])
    rows_total = b.readings["ts"].nunique()
    attack_secs = ((b.labels["end"] - b.labels["onset"]).dt.total_seconds().iloc[0]) + 1
    assert attack_secs < rows_total / 4


def test_swat_resample_and_errors(tmp_path):
    f = write_format_fixture(tmp_path / "s.csv", rows=600)
    b = load_swat_csv([f], resample_minutes=5)
    assert b.readings["ts"].nunique() == 2
    with pytest.raises(FileNotFoundError):
        load_swat_csv([tmp_path / "absent.csv"])
    with pytest.raises(FileNotFoundError):
        load_swat_csv([])
    bad = tmp_path / "bad.csv"
    pd.DataFrame({"a": [1]}).to_csv(bad, index=False)
    with pytest.raises(S.SchemaError):
        load_swat_csv([bad])


def test_cli_swat_without_files_fails_and_never_uses_generated_data(tmp_path, capsys):
    rc = cli.main(["prepare", "--swat", str(tmp_path / "SWaT_missing.csv"), "--run", str(tmp_path / "r")])
    out = capsys.readouterr().out
    assert rc == 2 and "DATA ERROR" in out and not (tmp_path / "r" / "baseline.json").exists()
    assert cli.main(["data-check", "--swat", str(tmp_path / "SWaT_missing.csv")]) == 2
