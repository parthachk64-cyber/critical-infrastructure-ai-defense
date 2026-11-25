# Results

Three origins are kept apart. **Nothing in section B or C is an article result; nothing in section A was measured here.** `data/synthetic` values verify the software and metric behaviour; they say nothing about real infrastructure or about the article's system.

## A. Article-reported (Das et al. 2026, Int. Cybersecur. Law Rev. 7:147-163)

The full text is paywalled and was not read; the Springer page shows six figures, an abstract, a reference list and a data statement. The figures carry **no printed numeric labels**. Only visible orderings are preserved; numeric bar heights are marked unverified (`references/reported/manifest.csv`).

| Item | What is legible | Value status | Source location | Caveat |
|---|---|---|---|---|
| Fig. 2 | Single-series bar chart, y-axis Percentages (%), six categories: IoT attacks, Ransomware attacks, Malware attacks, Cryptojacking attacks, Intrusion attempts (sic), Encrypted threats; descending bars | Categories and descending order legible; values UNVERIFIED (no printed labels, bar heights only) | Springer article page, https://link.springer.com/article/10.1365/s43439-026-00169-5, Fig. 2 (public image 43439_2026_169_Fig2_HTML.png; not copied here) | NOT a timeline of incidents and responses as the project brief assumed. No incident timeline is derivable from it. |
| Fig. 3 | Grouped bars, y Accuracy (%) axis 70-100, x Data Sets: Data set 1..5; series Proposed solution and State of art | Series, labels, axes legible; ranking Proposed > State of art in all five labels visible; values UNVERIFIED | Springer article page, https://link.springer.com/article/10.1365/s43439-026-00169-5, Fig. 3 (public image 43439_2026_169_Fig3_HTML.png; not copied here) | Truncated y-axis (starts at 70) exaggerates differences; metric definition, denominators and splits unknown. |
| Fig. 4 | Grouped bars, y Processing Time (seconds) 0-0,06 (comma decimal), x Data set 1..5; series Proposed solution and State of art | Series, labels, unit legible; Proposed <= State of art in all five labels (Data set 4 nearly equal) visible; values UNVERIFIED | Springer article page, https://link.springer.com/article/10.1365/s43439-026-00169-5, Fig. 4 (public image 43439_2026_169_Fig4_HTML.png; not copied here) | Cross-dataset speed comparison is invalid without job size, hardware, software and the timed operation. |
| Fig. 6 | Grouped bars, y Score 0-1, x Models: Isolation Forest and Hybrid CNN-LSTM; series Precision, Recall, F1-Score | Model labels and metric columns legible; Hybrid CNN-LSTM above Isolation Forest on all three metrics visible; values UNVERIFIED (hybrid bars reach the 1.0 gridline) | Springer article page, https://link.springer.com/article/10.1365/s43439-026-00169-5, Fig. 6 (public image 43439_2026_169_Fig6_HTML.png; not copied here) | Scores of 1.0 on three metrics need the evaluation protocol; no confusion counts exist to check them. |

No article-reported dataset, split, metric definition, timing condition or model specification could be verified (data statement: "available on request"; not requested).

## B. Independently measured on a named dataset

**Not run.** The only named benchmark supported is iTrust SWaT.A1 Dec 2015, which needs an owner-provided authorized copy; none was supplied. `infra-defense prepare --swat ...` refuses to run without files and never falls back to synthetic data. The loader and schema are covered by format-fixture tests (fictional values).

## C. Synthetic demonstration (run `demo`, dataset `synthetic-fixtures`)

Synthetic fictional assets; chronological split train/dev/test = 5760/2304/8064 asset-time rows (5-minute grid). Test: **8064 rows, 126 positive (prevalence 0.016)**, 672 monitored asset-hours. Alert budget: threshold = (1 - 0.01) quantile of NORMAL development scores, identical rate for both detectors (thresholds chosen on development data only).

### C1. Event-level (test rows)

Definitions: a row is one asset at one 5-minute step; positive = inside a labeled incident interval for that asset; precision = TP/(TP+FP); recall = TP/(TP+FN); F1 = harmonic mean; false-alert rate = FP/(FP+TN). `undefined` = zero denominator. Average precision defined only with continuous scores and both classes.

| detector | threshold | TP | FP | FN | TN | precision | recall | F1 | false-alert rate | avg. precision |
|---|---|---|---|---|---|---|---|---|---|---|
| iforest | 0.569 | 59 | 147 | 67 | 7791 | 0.286 (59/206) | 0.468 (59/126) | 0.355 | 0.019 (147/7938) | 0.262 |
| rule | 2.425 | 94 | 96 | 32 | 7842 | 0.495 (94/190) | 0.746 (94/126) | 0.595 | 0.012 (96/7938) | 0.433 |

### C2. Incident-level (each labeled incident-on-asset counted once)

Alert rows of one asset closer than 30 min merge into one alert group. A group matches an incident if it starts between labeled onset and end + 30 min on the same asset. Time to first alert is measured from labeled onset on the data clock; misses are excluded from it and listed.

| detector | incidents | detected | missed (ids) | alert groups | unmatched groups | unmatched by annotated scenario | false-alert groups / 24 asset-h | time to first alert (min, detected only) |
|---|---|---|---|---|---|---|---|---|
| iforest | 8 | 7 | 1 (INC-3/VALVE-03) | 56 | 45 | {"maintenance": 3, "no_annotated_scenario": 37, "normal_transition": 5} | 1.607 | 5, 0, 0, 0, 0, 0, 90 |
| rule | 8 | 7 | 1 (INC-3/VALVE-03) | 28 | 21 | {"maintenance": 1, "no_annotated_scenario": 16, "normal_transition": 4} | 0.750 | 5, 5, 5, 5, 5, 5, 70 |

Trade-off visible here: both detectors raise nuisance alert groups on unlabeled normal noise, planned maintenance and normal transitions at this budget, and both miss the deliberately small INC-3 deviation. Lowering the budget cuts nuisance alerts and increases misses; this table shows one operating point, not a curve.

### C3. Traced examples (data clock; see `runs/demo/traces/*.json`)

| example | scenario | rule outcome | iforest outcome | what the case records |
|---|---|---|---|---|
| 1_normal_operating_transition | S-T2 (normal_transition) | alert_and_case (2 case(s)) | alert_and_case (2 case(s)) | kind=detection; maintenance=None; posterior=0.553; review=observation_continued |
| 2_scheduled_maintenance | S-M1 (maintenance) | alert_and_case (1 case(s)) | alert_and_case (3 case(s)) | kind=detection; maintenance=MW-1; posterior=0.438; review=benign_maintenance_confirmed |
| 3_corroborated_incident | INC-1 (incident) | alert_and_case (2 case(s)) | alert_and_case (3 case(s)) | kind=detection; maintenance=None; posterior=0.984; review=escalation_recorded |
| 4_missing_sensor | S-D1 (data_gap) | alert_and_case (1 case(s)) | alert_and_case (1 case(s)) | kind=data_quality; maintenance=None; posterior=undefined; review=telemetry_quality_check |
| 5_incident_resembling_maintenance | INC-2 (incident) | alert_and_case (1 case(s)) | alert_and_case (2 case(s)) | kind=detection; maintenance=None; posterior=0.750; review=escalation_recorded |

### C4. Local processing latency (not analyst response time)

Hardware: Windows-10-10.0.26300-SP0 / Intel64 Family 6 Model 186 Stepping 2, GenuineIntel; timer time.perf_counter (monotonic); 2 warm-up runs, 5 timed repeats, test rows scored per repeat shown; scope: model inference on precomputed features, plus feature construction. single machine, shared desktop OS, small batches; not a throughput claim and not comparable to any article timing.

| measurement | batch size | rows per repeat | median us/row | min | max |
|---|---|---|---|---|---|
| Isolation Forest scoring | 1 | 200 | 94014.4 | 90836.3 | 105736.2 |
| Isolation Forest scoring | 256 | 8064 | 487.8 | 425.2 | 549.0 |
| Isolation Forest scoring | 8064 | 8064 | 87.4 | 78.8 | 93.6 |
| feature construction, full stream | n/a | 16128 | 86.4 | n/a | n/a |

Review latency exists only where a reviewer timestamp exists; here the reviewers are pre-authored simulated records, so `review_latency_min` in the traces is a property of the fixture, not a human-speed measurement.

Provenance: run `demo`, commit `7660dddd25bf`, model `iforest-v1` sha256 `9631d692a3d462ad...`, seed 42, Windows-10-10.0.26300-SP0.

