"""infra-defense: demo | data-check | prepare | fit | replay | evaluate | figures | report. Offline, advisory only."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from infra_defense import pipeline as P
from infra_defense.config import FIXTURE_DIR, RUNS_DIR, load_config, sha256_file
from infra_defense.data.io import load_bundle
from infra_defense.evaluation.trace import export_traces
from infra_defense.schema import SchemaError

EXIT_DATA = 2


def _bundle_from_args(a) -> tuple[object, Path, str]:
    cfg = load_config()
    if getattr(a, "swat", None):
        from infra_defense.data.swat import load_swat_csv
        b = load_swat_csv([Path(x) for x in a.swat], resample_minutes=cfg["step_minutes"])
        return b, Path(a.swat[0]).parent, "swat-a1-dec2015 (owner-provided)"
    d = Path(a.data) if getattr(a, "data", None) else FIXTURE_DIR
    return load_bundle(d, require_labels=False), d, ("synthetic-fixtures" if d == FIXTURE_DIR else f"user-supplied:{d.name}")


def _write_prepared(run: Path, data_dir: Path, dataset_id: str, swat: list[str] | None) -> None:
    (run / "prepared.json").write_text(json.dumps({"data_dir": str(data_dir), "dataset_id": dataset_id,
                                                   "swat": swat}, indent=1), encoding="utf-8")


def _state(run: Path):
    """Rebuild Prepared from prepared.json; SWaT is reloaded from the owner's files, never substituted."""
    info = json.loads((run / "prepared.json").read_text(encoding="utf-8"))
    cfg = load_config()
    if info.get("swat"):
        from infra_defense.data.swat import load_swat_csv
        b = load_swat_csv([Path(x) for x in info["swat"]], resample_minutes=cfg["step_minutes"])
    else:
        b = load_bundle(info["data_dir"])
    return P.prepare(b, cfg), info


def cmd_data_check(a) -> int:
    try:
        b, d, ds = _bundle_from_args(a)
    except (FileNotFoundError, SchemaError) as e:
        print(f"DATA ERROR: {e}")
        return EXIT_DATA
    print(f"dataset: {ds}\nsource: {b.source}")
    print(f"readings: {len(b.readings)} rows, assets: {b.readings['asset_id'].nunique()}, sensors: {b.readings['sensor'].nunique()}, "
          f"span: {b.readings['ts'].min()} -> {b.readings['ts'].max()}")
    print(f"labels: {'none' if b.labels is None else len(b.labels)}; maintenance windows: {len(b.maintenance)}")
    for n in b.notes:
        print("note:", n)
    for f in sorted((Path(x) for x in (a.swat or [])), key=str):
        print(f"sha256 {f.name}: {sha256_file(f)}")
    return 0


def cmd_prepare(a) -> int:
    run = Path(a.run)
    run.mkdir(parents=True, exist_ok=True)
    try:
        b, d, ds = _bundle_from_args(a)
        _write_prepared(run, d, ds, [str(Path(x).resolve()) for x in a.swat] if a.swat else None)
        p, _ = _state(run)
    except (FileNotFoundError, SchemaError) as e:
        print(f"DATA ERROR: {e}")
        return EXIT_DATA
    (run / "baseline.json").write_text(json.dumps(p.baseline.to_dict(), indent=1, sort_keys=True), encoding="utf-8")
    print(f"prepared {ds}: {len(p.fs.meta)} scored rows; splits {p.split.value_counts().to_dict()}; positives {int(p.y.sum())}")
    return 0


def cmd_fit(a) -> int:
    run = Path(a.run)
    p, _ = _state(run)
    f = P.fit(p, run)
    print("fitted; thresholds:", json.dumps({k: round(v, 4) for k, v in f["thresholds"].items()}), "| model", f["model_meta"]["version"])
    return 0


def cmd_replay(a) -> int:
    run = Path(a.run)
    p, _ = _state(run)
    f = P.load_fitted(p, run)
    r = P.replay(p, f, run)
    print("alert groups:", {k: len(v) for k, v in r["groups"].items()}, "| case store:", r["store_stats"])
    return 0


def cmd_evaluate(a) -> int:
    run = Path(a.run)
    p, info = _state(run)
    f = P.load_fitted(p, run)
    r = P.replay(p, f, run)
    m = P.evaluate(p, f, r, run, run.name)
    P.write_manifest(run, p, f, Path(info["data_dir"]), info["dataset_id"])
    if p.bundle.scenarios is not None:
        export_traces(p, f, r, run)
    for d, v in m["detectors"].items():
        e = v["event"]
        print(f"{d}: P={e['precision']} R={e['recall']} F1={e['f1']} AP={v['average_precision']}; incidents "
              f"{v['incident']['detected']}/{v['incident']['incidents']} detected" if v["incident"] else f"{d}: {e}")
    return 0


def cmd_figures(a) -> int:
    from infra_defense.evaluation.plots import generate_all
    run = Path(a.run)
    p, _ = _state(run)
    f = P.load_fitted(p, run)
    r = P.replay(p, f, run)
    m = json.loads((run / "metrics.json").read_text(encoding="utf-8"))
    traces = [json.loads(x.read_text(encoding="utf-8")) for x in sorted((run / "traces").glob("*.json"))]
    made = generate_all(p, f, m, traces, Path(a.out) if a.out else run / "figures")
    print("figures:", ", ".join(x.name for x in made))
    return 0 if r else 1


def cmd_report(a) -> int:
    from infra_defense.report import results_md
    run = Path(a.run)
    traces = [json.loads(x.read_text(encoding="utf-8")) for x in sorted((run / "traces").glob("*.json"))]
    out = Path(a.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(results_md(run, traces), encoding="utf-8")
    print("wrote", out)
    return 0


def cmd_demo(a) -> int:
    run = Path(a.run)
    run.mkdir(parents=True, exist_ok=True)
    ns = argparse.Namespace(run=str(run), data=a.data, swat=None, out=None)
    for name, fn in (("prepare", cmd_prepare), ("fit", cmd_fit), ("evaluate", cmd_evaluate), ("figures", cmd_figures)):
        print(f"--- {name}")
        rc = fn(ns)
        if rc:
            return rc
    print("--- traced examples (data clock; advisory only)")
    for t in sorted((run / "traces").glob("*.json")):
        d = json.loads(t.read_text(encoding="utf-8"))
        print(f"\n{d['example']}  [{d['scenario']['kind']}, {d['scenario']['start']} -> {d['scenario']['end']}]")
        for det in ("rule", "iforest"):
            x = d["detectors"][det]
            print(f"  {det}: {x['outcome']}; peak score {x['peak_score_in_window']:.3f} vs threshold {x['threshold']:.3f}")
            for tl in x["timeline"][:2]:
                print(f"    case {tl['case_id']}: first_evidence={tl['first_evidence_ts']} alert={tl['alert_ts']} "
                      f"created={tl['case_created_at']} reviewed={tl['review_decided_at']} latency_min={tl['review_latency_min']}")
            for c in x["cases"][:1]:
                print(f"    kind={c['kind']} recommended={c['recommended_action']} maintenance={c['context'].get('maintenance_window_id')} "
                      f"posterior={(c['inferred'] or {}).get('concern_posterior')} disposition={(c['review'] or {}).get('decision')}")
    print(f"\nartifacts in {run}  (metrics.json, manifest.json, scores.csv, cases_*.jsonl, traces/, figures/)")
    return 0


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="infra-defense", description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    def add(name, fn, run=True):
        sp = sub.add_parser(name)
        sp.set_defaults(fn=fn)
        if run:
            sp.add_argument("--run", default=str(RUNS_DIR / "demo"))
        return sp

    for name, fn in (("demo", cmd_demo), ("prepare", cmd_prepare), ("data-check", cmd_data_check)):
        sp = add(name, fn, run=name != "data-check")
        sp.add_argument("--data", default=None, help="directory with readings.csv, assets.csv, ... (default: data/synthetic, explicit)")
        if name != "demo":
            sp.add_argument("--swat", nargs="+", default=None, help="owner-provided SWaT CSV file(s); never auto-downloaded")
    for name, fn in (("fit", cmd_fit), ("replay", cmd_replay), ("evaluate", cmd_evaluate)):
        add(name, fn)
    sp = add("figures", cmd_figures)
    sp.add_argument("--out", default=None)
    sp = add("report", cmd_report)
    sp.add_argument("--out", default=str(Path("docs") / "results.md"))
    a = ap.parse_args(argv)
    try:
        return a.fn(a)
    except (FileNotFoundError, SchemaError) as e:
        print(f"ERROR: {e}")
        return EXIT_DATA


if __name__ == "__main__":
    sys.exit(main())
