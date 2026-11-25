"""prepare -> fit -> replay -> evaluate on saved files, via the same public functions the CLI calls."""

from __future__ import annotations

import json
import platform
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import sklearn

from infra_defense import __version__, bayes
from infra_defense.config import REPO_ROOT, sha256_file, sha256_obj
from infra_defense.data.io import Bundle
from infra_defense.detectors.iforest import IsolationForestDetector
from infra_defense.detectors.rules import RuleDetector
from infra_defense.evaluation.matching import AlertGroup, group_alerts, match_incidents, unmatched_groups
from infra_defense.evaluation.metrics import average_precision, budget_threshold, confusion, monitored_asset_hours
from infra_defense.evaluation.profiling import profile_scoring
from infra_defense.features import Baseline, FeatureSet, assign_split, build_features, fit_baseline
from infra_defense.triage import TriageStore, apply_reviews, build_cases, build_quality_cases

DETECTORS = ("rule", "iforest")


@dataclass
class Prepared:
    bundle: Bundle
    cfg: dict
    baseline: Baseline
    fs: FeatureSet
    split: pd.Series
    y: pd.Series            # row-level label from interval annotations (evaluation only)
    t0: pd.Timestamp


def label_rows(meta: pd.DataFrame, labels: pd.DataFrame | None) -> pd.Series:
    y = pd.Series(False, index=meta.index)
    if labels is None or labels.empty:
        return y
    for _, lab in labels.iterrows():
        y |= (meta["asset_id"] == lab["asset_id"]) & (meta["ts"] >= lab["onset"]) & (meta["ts"] <= lab["end"])
    return y


def prepare(bundle: Bundle, cfg: dict) -> Prepared:
    r = bundle.readings
    t0 = r["ts"].min().floor(f"{cfg['step_minutes']}min")
    t_train_end = t0 + pd.Timedelta(days=cfg["splits"]["train_days"])
    base = fit_baseline(r, t_train_end)  # train rows only
    fs = build_features(r, base, cfg["window_steps"], cfg["delta_steps"], cfg["step_minutes"])
    split = assign_split(fs.meta["ts"], t0, cfg["splits"]["train_days"], cfg["splits"]["dev_days"])
    return Prepared(bundle, cfg, base, fs, split, label_rows(fs.meta, bundle.labels), t0)


def fit(p: Prepared, out_dir: Path) -> dict:
    """Fit detectors on TRAIN rows that are not labeled positive; pick alert-budget thresholds on DEV only."""
    cfg, fs = p.cfg, p.fs
    train = (p.split == "train") & (~p.y)
    dev = p.split == "dev"
    rule = RuleDetector(cfg["rule_persistence_steps"], cfg["detector_versions"]["rule"]).fit(fs, train)
    iso = IsolationForestDetector(cfg["isolation_forest"]["n_estimators"], cfg["isolation_forest"]["seed"],
                                  cfg["detector_versions"]["iforest"]).fit(fs, train)
    scores = {"rule": rule.score(fs), "iforest": iso.score(fs)}
    thr = {k: budget_threshold(s[dev], p.y[dev], cfg["alert_budget_rate"]) for k, s in scores.items()}
    out = Path(out_dir)
    meta = iso.save(out / "model")
    (out / "model" / "thresholds.json").write_text(json.dumps(
        {"selected_on": "development split, normal rows only", "alert_budget_rate": cfg["alert_budget_rate"],
         "thresholds": thr, "baseline": p.baseline.to_dict()}, indent=1, sort_keys=True), encoding="utf-8")
    return {"rule": rule, "iforest": iso, "scores": scores, "thresholds": thr, "model_meta": meta}


def replay(p: Prepared, fitted: dict, out_dir: Path) -> dict:
    """Score the TEST period in time order, group alerts, build evidence-linked cases, attach recorded reviews."""
    cfg, fs = p.cfg, p.fs
    test = p.split == "test"
    res: dict = {"groups": {}, "cases": {}}
    store_stats = {}
    for name in DETECTORS:
        s = fitted["scores"][name]
        sub_meta = fs.meta[test].reset_index(drop=True)
        groups = group_alerts(sub_meta, s[test].reset_index(drop=True), fitted["thresholds"][name], cfg["alert_merge_gap_minutes"])
        res["groups"][name] = groups
        sub_fs = FeatureSet(sub_meta, fs.X[test].reset_index(drop=True), fs.absz[test].reset_index(drop=True))
        ver = cfg["detector_versions"]["rule" if name == "rule" else "iforest"]
        cases = build_cases(groups, sub_fs, s[test].reset_index(drop=True), p.bundle.assets, p.bundle.maintenance, cfg, ver)
        cases += build_quality_cases(sub_fs, cfg, ver)
        cases = apply_reviews(cases, p.bundle.reviews)
        res["cases"][name] = cases
        store_stats[name] = TriageStore(Path(out_dir) / f"cases_{name}.jsonl").upsert_many(cases)
    res["store_stats"] = store_stats
    return res


def _unmatched_breakdown(groups: list[AlertGroup], scen: pd.DataFrame | None) -> dict[str, int]:
    out: dict[str, int] = {}
    for g in groups:
        kind = "no_annotated_scenario"
        if scen is not None:
            m = scen[(scen["asset_ids"].str.contains(g.asset_id)) & (scen["start"] - pd.Timedelta(minutes=10) <= g.start)
                     & (g.start <= scen["end"] + pd.Timedelta(minutes=30))]
            if not m.empty:
                kind = str(m["kind"].iloc[0])
        out[kind] = out.get(kind, 0) + 1
    return out


def evaluate(p: Prepared, fitted: dict, replayed: dict, out_dir: Path, run_id: str) -> dict:
    cfg, fs = p.cfg, p.fs
    out = Path(out_dir)
    test = (p.split == "test").to_numpy()
    y = p.y.to_numpy()
    hours = monitored_asset_hours(fs.meta[test], cfg["step_minutes"])
    labels = p.bundle.labels
    t_test = p.t0 + pd.Timedelta(days=cfg["splits"]["train_days"] + cfg["splits"]["dev_days"])
    lab_test = labels[labels["onset"] >= t_test] if labels is not None else None
    metrics: dict = {"run_id": run_id, "origin": "independently measured on the dataset named in manifest (not article-reported)",
                     "counts": {s: int((p.split == s).sum()) for s in ("train", "dev", "test")},
                     "test_rows": int(test.sum()), "test_positive_rows": int(y[test].sum()),
                     "test_prevalence": float(y[test].mean()) if test.any() else None,
                     "monitored_asset_hours_test": hours, "alert_budget_rate": cfg["alert_budget_rate"],
                     "budget_rule": "threshold = (1-rate) quantile of NORMAL development scores; same rate for both detectors",
                     "detectors": {}}
    for name in DETECTORS:
        s = fitted["scores"][name].to_numpy()
        thr = fitted["thresholds"][name]
        d = {"threshold": thr, "event": confusion(y[test], s[test] >= thr),
             "average_precision": average_precision(y[test], s[test])}
        groups = replay_groups = replayed["groups"][name]
        d["alert_groups"] = len(replay_groups)
        if lab_test is not None and len(lab_test):
            m = match_incidents(groups, lab_test, cfg["match_grace_minutes"])
            un = unmatched_groups(groups, lab_test, cfg["match_grace_minutes"])
            d["incident"] = {"incidents": int(len(m)), "detected": int(m["detected"].sum()),
                             "missed": int((~m["detected"]).sum()),
                             "missed_ids": [f"{r.incident_id}/{r.asset_id}" for r in m[~m["detected"]].itertuples()],
                             "time_to_first_alert_min": [float(x) for x in m["time_to_first_alert_min"].dropna()],
                             "unmatched_alert_groups": len(un),
                             "unmatched_by_annotation": _unmatched_breakdown(un, p.bundle.scenarios),
                             "false_alert_groups_per_24_asset_hours": len(un) / hours * 24 if hours else None}
            m.to_csv(out / f"incident_matches_{name}.csv", index=False, date_format="%Y-%m-%dT%H:%M:%SZ")
        else:
            d["incident"] = None
        metrics["detectors"][name] = d
    metrics["profiling"] = profile_scoring(p, fitted, cfg)
    pd.DataFrame({"obs_id": fs.meta["obs_id"], "ts": fs.meta["ts"].dt.strftime("%Y-%m-%dT%H:%M:%SZ"),
                  "asset_id": fs.meta["asset_id"], "split": p.split, "label_positive": p.y.astype(int),
                  "rule_score": fitted["scores"]["rule"].round(6), "iforest_score": fitted["scores"]["iforest"].round(6)}
                 ).to_csv(out / "scores.csv", index=False)
    (out / "metrics.json").write_text(json.dumps(metrics, indent=1, sort_keys=True, default=str), encoding="utf-8")
    return metrics


def git_commit() -> str:
    try:
        r = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, cwd=REPO_ROOT, timeout=10)
        return r.stdout.strip() if r.returncode == 0 else "uncommitted"
    except (OSError, subprocess.SubprocessError):
        return "uncommitted"


def write_manifest(out: Path, p: Prepared, fitted: dict, data_dir: Path, dataset_id: str) -> dict:
    files = {f.name: sha256_file(f) for f in sorted(Path(data_dir).glob("*.csv"))}
    m = {"package_version": __version__, "git_commit": git_commit(), "dataset_id": dataset_id, "data_files_sha256": files,
         "config_sha256": sha256_obj(p.cfg), "model_version": fitted["model_meta"]["version"],
         "model_sha256": fitted["model_meta"]["sha256"], "bayes_version": bayes.VERSION, "bayes_provenance": bayes.PROVENANCE,
         "seed": p.cfg["isolation_forest"]["seed"],
         "packages": {"python": sys.version.split()[0], "numpy": np.__version__, "pandas": pd.__version__,
                      "scikit-learn": sklearn.__version__},
         "platform": platform.platform(), "machine": platform.machine(),
         "clock_conventions": {"data_clock": "ts in the input files (UTC); used for alerts, time-to-first-alert, review latency",
                               "processing_clock": "time.perf_counter(), only in profiling; never mixed with the data clock"}}
    (out / "manifest.json").write_text(json.dumps(m, indent=1, sort_keys=True), encoding="utf-8")
    return m


def load_fitted(p: Prepared, run_dir: Path) -> dict:
    """Rebuild the fitted state from files written by fit(): saved forest + thresholds; rule is parameter-only."""
    mdir = Path(run_dir) / "model"
    thr = json.loads((mdir / "thresholds.json").read_text(encoding="utf-8"))["thresholds"]
    rule = RuleDetector(p.cfg["rule_persistence_steps"], p.cfg["detector_versions"]["rule"])
    iso = IsolationForestDetector.load(mdir)
    meta = json.loads((mdir / "iforest.meta.json").read_text(encoding="utf-8"))
    return {"rule": rule, "iforest": iso, "scores": {"rule": rule.score(p.fs), "iforest": iso.score(p.fs)},
            "thresholds": thr, "model_meta": meta}
