"""docs/results.md from run artifacts. Three labelled origins; every number has definition, unit, denominator, run id."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from infra_defense.config import REPO_ROOT


def _f(x, n=3):
    return "undefined" if x is None else (f"{x:.{n}f}" if isinstance(x, float) else str(x))


def results_md(run: Path, traces: list[dict]) -> str:
    m = json.loads((run / "metrics.json").read_text(encoding="utf-8"))
    man = json.loads((run / "manifest.json").read_text(encoding="utf-8"))
    rid = m["run_id"]
    L = ["# Results\n",
         "Three origins are kept apart. **Nothing in section B or C is an article result; nothing in section A was "
         "measured here.** `data/synthetic` values verify the software and metric behaviour; they say nothing about real "
         "infrastructure or about the article's system.\n",
         "## A. Article-reported (Das et al. 2026, Int. Cybersecur. Law Rev. 7:147-163)\n",
         "The full text is paywalled and was not read; the Springer page shows six figures, an abstract, a reference list "
         "and a data statement. The figures carry **no printed numeric labels**. Only visible orderings are preserved; "
         "numeric bar heights are marked unverified (`references/reported/manifest.csv`).\n",
         "| Item | What is legible | Value status | Source location | Caveat |", "|---|---|---|---|---|"]
    for r in csv.DictReader(open(REPO_ROOT / "references" / "reported" / "manifest.csv", encoding="utf-8")):
        if r["item"] in ("Fig. 3", "Fig. 4", "Fig. 6", "Fig. 2"):
            L.append(f"| {r['item']} | {r['what_can_be_identified']} | {r['verification_status']} | {r['source_location']} | {r['caveat']} |")
    L += ["\nNo article-reported dataset, split, metric definition, timing condition or model specification could be verified "
          "(data statement: \"available on request\"; not requested).\n",
          "## B. Independently measured on a named dataset\n",
          "**Not run.** The only named benchmark supported is iTrust SWaT.A1 Dec 2015, which needs an owner-provided "
          "authorized copy; none was supplied. `infra-defense prepare --swat ...` refuses to run without files and never "
          "falls back to synthetic data. The loader and schema are covered by format-fixture tests (fictional values).\n",
          f"## C. Synthetic demonstration (run `{rid}`, dataset `{man['dataset_id']}`)\n",
          f"Synthetic fictional assets; chronological split train/dev/test = {m['counts']['train']}/{m['counts']['dev']}/{m['counts']['test']} "
          f"asset-time rows (5-minute grid). Test: **{m['test_rows']} rows, {m['test_positive_rows']} positive "
          f"(prevalence {_f(m['test_prevalence'])})**, {m['monitored_asset_hours_test']:.0f} monitored asset-hours. "
          f"Alert budget: threshold = (1 - {m['alert_budget_rate']}) quantile of NORMAL development scores, identical rate for both detectors "
          "(thresholds chosen on development data only).\n",
          "### C1. Event-level (test rows)\n",
          "Definitions: a row is one asset at one 5-minute step; positive = inside a labeled incident interval for that asset; "
          "precision = TP/(TP+FP); recall = TP/(TP+FN); F1 = harmonic mean; false-alert rate = FP/(FP+TN). `undefined` = zero denominator. "
          "Average precision defined only with continuous scores and both classes.\n",
          "| detector | threshold | TP | FP | FN | TN | precision | recall | F1 | false-alert rate | avg. precision |", "|---|---|---|---|---|---|---|---|---|---|---|"]
    for d, v in m["detectors"].items():
        e = v["event"]
        L.append(f"| {d} | {_f(v['threshold'])} | {e['tp']} | {e['fp']} | {e['fn']} | {e['tn']} | {_f(e['precision'])} ({e['tp']}/{e['tp']+e['fp']}) | "
                 f"{_f(e['recall'])} ({e['tp']}/{e['positives']}) | {_f(e['f1'])} | {_f(e['false_alert_rate'])} ({e['fp']}/{e['negatives']}) | {_f(v['average_precision'])} |")
    L += ["\n### C2. Incident-level (each labeled incident-on-asset counted once)\n",
          "Alert rows of one asset closer than 30 min merge into one alert group. A group matches an incident if it starts between "
          "labeled onset and end + 30 min on the same asset. Time to first alert is measured from labeled onset on the data clock; "
          "misses are excluded from it and listed.\n",
          "| detector | incidents | detected | missed (ids) | alert groups | unmatched groups | unmatched by annotated scenario | false-alert groups / 24 asset-h | time to first alert (min, detected only) |",
          "|---|---|---|---|---|---|---|---|---|"]
    for d, v in m["detectors"].items():
        i = v["incident"]
        L.append(f"| {d} | {i['incidents']} | {i['detected']} | {i['missed']} ({', '.join(i['missed_ids']) or 'none'}) | {v['alert_groups']} | "
                 f"{i['unmatched_alert_groups']} | {json.dumps(i['unmatched_by_annotation'])} | {_f(i['false_alert_groups_per_24_asset_hours'])} | "
                 f"{', '.join(f'{x:g}' for x in i['time_to_first_alert_min'])} |")
    L += ["\nTrade-off visible here: both detectors raise nuisance alert groups on unlabeled normal noise, planned maintenance and "
          "normal transitions at this budget, and both miss the deliberately small INC-3 deviation. Lowering the budget cuts nuisance "
          "alerts and increases misses; this table shows one operating point, not a curve.\n",
          "### C3. Traced examples (data clock; see `runs/demo/traces/*.json`)\n",
          "| example | scenario | rule outcome | iforest outcome | what the case records |", "|---|---|---|---|---|"]
    for t in traces:
        def cell(det, t=t):
            d = t["detectors"][det]
            return f"{d['outcome']} ({len(d['cases'])} case(s))"
        c0 = next((c for det in ("rule", "iforest") for c in t["detectors"][det]["cases"]), None)
        what = "no case: nothing to record beyond scores" if c0 is None else (
            f"kind={c0['kind']}; maintenance={c0['context'].get('maintenance_window_id')}; "
            f"posterior={_f((c0['inferred'] or {}).get('concern_posterior'))}; review={(c0['review'] or {}).get('decision')}")
        L.append(f"| {t['example']} | {t['scenario']['scenario_id']} ({t['scenario']['kind']}) | {cell('rule')} | {cell('iforest')} | {what} |")
    pr = m["profiling"]
    L += ["\n### C4. Local processing latency (not analyst response time)\n",
          f"Hardware: {pr['hardware']['platform']} / {pr['hardware']['processor']}; timer {pr['timer']}; {pr['warmup_runs']} warm-up runs, "
          f"{pr['repeats']} timed repeats, test rows scored per repeat shown; scope: {pr['scope']}. {pr['caveat']}.\n",
          "| measurement | batch size | rows per repeat | median us/row | min | max |", "|---|---|---|---|---|---|"]
    for k, v in pr["results"].items():
        if k.startswith("iforest"):
            L.append(f"| Isolation Forest scoring | {v['batch_size']} | {v['rows_per_repeat']} | {v['median_us_per_row']:.1f} | {v['min_us_per_row']:.1f} | {v['max_us_per_row']:.1f} |")
    fc = pr["results"]["feature_construction"]
    L.append(f"| feature construction, full stream | n/a | {fc['stream_rows']} | {fc['us_per_row']:.1f} | n/a | n/a |")
    L += ["\nReview latency exists only where a reviewer timestamp exists; here the reviewers are pre-authored simulated records, so "
          "`review_latency_min` in the traces is a property of the fixture, not a human-speed measurement.\n",
          f"Provenance: run `{rid}`, commit `{man['git_commit'][:12]}`, model `{man['model_version']}` sha256 `{man['model_sha256'][:16]}...`, "
          f"seed {man['seed']}, {man['platform']}.\n"]
    return "\n".join(L) + "\n"
