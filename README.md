# infra-defense: offline companion to a review of AI-driven threat detection for U.S. critical infrastructure

**Article.** N. Das, H. Kaur, K. B. Siddiqa, S. N. Hasan, P. Chakraborty, J. kaur, H. Rahman, A. Shan-A-Alahi and R. Hasan,
"AI-driven threat detection and response framework for protecting U.S. critical infrastructure from cyberattacks,"
*International Cybersecurity Law Review* 7, 147-163 (2026), published 9 March 2026.
DOI [10.1365/s43439-026-00169-5](https://doi.org/10.1365/s43439-026-00169-5) ·
[publisher page](https://link.springer.com/article/10.1365/s43439-026-00169-5).
The publisher page also shows an unrelated German subtitle about quantum cryptography and payments; it is recorded and ignored
([bibliographic notes](docs/bibliographic-notes.md)). The article credits Partha Chakraborty and Habiba Rahman with *visualization, figure
preparation and formatting*. Partha's role **here** is a different one: maintainer of this independent software.

> **What this is, and is not.** The article's abstract describes a study that *examines* and *reviews*, so this project is a companion to a
> primarily review/comparative article. The full text is paywalled and was not read; the data are "available on request" and were not requested.
> Nothing here is the authors' code, trained system, data or result. Figures 2-6 cannot be reproduced without artifacts listed in
> [`docs/data-card.md`](docs/data-card.md); each is mapped to a verified description or an explanation of what is missing
> ([`docs/paper-map.md`](docs/paper-map.md), [`references/reported/manifest.csv`](references/reported/manifest.csv)).

Two paths:

1. **Start from a published figure** -> [paper map](docs/paper-map.md): what the public figure shows, its data/source, what is unverified, and the original Python figure that stands in for it.
2. **Run a defensive demonstration** from recorded telemetry through detection, analyst review and a timestamped decision. Offline, advisory only.

## Quick start (tested in a clean virtual environment)

```bash
git clone https://github.com/parthachk64-cyber/critical-infrastructure-ai-defense && cd critical-infrastructure-ai-defense
python -m pip install -e ".[dev]"      # editable: configs/ and data/ are read from the checkout
infra-defense demo                      # prepare -> fit (real model) -> replay -> evaluate -> figures -> five traced examples
```

The demo uses `data/synthetic/` explicitly. Other commands: `data-check`, `prepare`, `fit`, `replay`, `evaluate`, `figures`, `report`
(`infra-defense --help`). `infra-defense prepare --swat Normal.csv Attack.csv` uses an owner-provided SWaT copy and **exits with code 2 if the
files are missing; it never falls back to generated data**.

### One generated case trace (real output, rule detector, example 3)

Full JSON: [`examples/trace_3_corroborated_incident.json`](examples/trace_3_corroborated_incident.json). Timestamps are on the **data clock**; the
reviewer is a pre-authored, simulated record, so the 95-minute figure is a fixture property, not human speed.

```text
3_corroborated_incident  [incident, 2026-01-15T07:10:00Z -> 2026-01-15T08:35:00Z]
  rule: alert_and_case; peak score 6.204 vs threshold 2.425
    case CASE-73d74efcd038: first_evidence=07:15 alert=07:15 created=07:15 reviewed=08:50 latency_min=95.0
    kind=detection recommended=review_requested maintenance=None posterior=0.98 disposition=escalation_recorded
```

The case keeps three things apart: **observed** (peak |z| per sensor, missing fraction), **inferred** (a triage-priority posterior from an
illustrative Bayes graph; never a cause or intent) and **review** (reviewer id, disposition, decision time). Evidence ids, detector version and
corroborating evidence from the other asset are attached. Re-running `replay` creates no new cases (test).

The five examples: (1) a normal operating transition, (2) scheduled maintenance that makes readings unusual, (3) corroborating telemetry that
warrants review, (4) a missing sensor that must surface as a data-quality case, (5) an incident whose readings resemble example 2 but with no
maintenance window - the detector scores both alike; the recorded context and disposition differ.

## Source map and measurement provenance

| origin | where | what it is |
|---|---|---|
| **article-reported** | [`docs/paper-map.md`](docs/paper-map.md), `references/reported/` | descriptions and visible orderings from six public figures; **no numeric value verified** (bars have no printed labels) |
| **independently measured on a named dataset** | `docs/results.md` section B | **not run**: needs an owner-provided iTrust SWaT.A1 Dec 2015 copy; loader and schema tests exist |
| **synthetic demonstration** | `docs/results.md` section C, `runs/demo/` | fictional assets; verifies software and metric behaviour only |

Headline synthetic numbers (test split: 8,064 asset-time rows, 126 positive, prevalence 0.0156, 672 monitored asset-hours; both detectors at the
same development-set alert budget of 1%): fixed rule P 0.495 / R 0.746 / F1 0.595; Isolation Forest P 0.286 / R 0.468 / F1 0.355; each detects
7 of 8 labeled incident intervals and both miss the deliberately small INC-3. Nuisance alert groups: rule 21, Isolation Forest 45 over 672
asset-hours. These say nothing about real infrastructure or about the article's models. Definitions, denominators, run id and caveats:
[`docs/results.md`](docs/results.md); recompute from `runs/demo/scores.csv`, `incident_matches_*.csv`, `manifest.json`.

## Method summary

Chronological partitions (train 0-5 d, development 5-7 d, test 7-14 d) and episode-grouped labels; features per asset use only data up to the
scoring time (rolling counts, rates of change, missingness, deviation from a train-only baseline); thresholds from development normal rows;
alert rows merged into groups (30 min), matched to labeled intervals (onset to end + 30 min), each incident counted once; time to first alert from
labeled onset; processing latency measured separately with a monotonic clock. Detectors: a fixed persistence rule and an Isolation Forest fitted on
the normal training interval (companion baselines, not the article's models). Bayes: [`bayes.py`](src/infra_defense/bayes.py), expert-specified
example probabilities, hand-checked posterior in tests.

## Reproduction gaps (genuine)

Full text; dataset identifiers/versions, schema, class labels, preprocessing, train/test membership; model specification or checkpoint for the
"proposed solution", "state of art" and the Hybrid CNN-LSTM; per-record scores; Fig. 4 timing conditions; source and denominator of Fig. 2;
whether "state of art" values are original measurements. No SWaT benchmark has been run. Colonial Pipeline: the GAO PDF could not be fetched
(HTTP 403); GAO statements in [`docs/case-colonial-pipeline.md`](docs/case-colonial-pipeline.md) are marked *via search summary*.

## Policy and case context

[`docs/case-colonial-pipeline.md`](docs/case-colonial-pipeline.md) (no retrospective alerts, no claim a model would have prevented anything) and
[`docs/policy-map.md`](docs/policy-map.md) (outputs -> NIST CSF 2.0 and SP 800-82 Rev. 3, explanatory only; no binding obligation asserted).

## Safety scope

Saved files only. No scanner, attack reproducer, live plant connector or controller command exists; every output is an advisory record
(`review_requested`, `telemetry_quality_check`, `observation_continued`, `benign_maintenance_confirmed`, `escalation_recorded`).

## Maintainer, license, citation

Sole maintainer and code owner: Partha Chakraborty ([@parthachk64-cyber](https://github.com/parthachk64-cyber)) via `.github/CODEOWNERS`.
MIT for the original code (`LICENSE`; confirm the copyright holder). `CITATION.cff` keeps all nine article authors in the preferred citation.
The article, its figures and any SWaT data are not covered by this license and are not in the repository.
