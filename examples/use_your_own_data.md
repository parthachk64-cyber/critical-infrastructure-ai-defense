# Using authorized data

**Your own records.** Put these files in a directory (CSV or JSONL):

* `readings.csv`: `ts` (UTC ISO 8601), `asset_id`, `sensor`, `value` (a missing reading is an absent row or a blank value)
* `assets.csv`: `asset_id`, `criticality` (high/low/unknown), `stage`
* optional `maintenance.csv`: `window_id`, `asset_id`, `start`, `end` (planned work, known at scoring time)
* optional `labels.csv`: `incident_id`, `asset_id`, `onset`, `end` (evaluation only; never a feature)

```bash
infra-defense data-check --data my_dir
infra-defense prepare --data my_dir --run runs/mine
infra-defense fit --run runs/mine && infra-defense evaluate --run runs/mine
```

Use fictional or de-identified asset names; keep site identifiers out of Git.

**iTrust SWaT (owner-provided).** Request SWaT.A1_Dec 2015 from iTrust under its terms
(<https://www.sutd.edu.sg/itrust/itrust-labs/datasets/dataset-characteristics/swat/>); keep the files outside the repository.

```bash
infra-defense data-check --swat SWaT_Normal.csv SWaT_Attack.csv      # row counts, span, attack runs, sha256 of each file
infra-defense prepare --swat SWaT_Normal.csv SWaT_Attack.csv --run runs/swat
infra-defense fit --run runs/swat && infra-defense evaluate --run runs/swat && infra-defense report --run runs/swat --out docs/results_swat.md
```

Read `src/infra_defense/data/swat.py` first: it states the label convention (attack intervals = runs of attack-labelled rows; later "attack days" are
not wholesale positive), the per-stage label limitation and the timestamp handling. SWaT is a Singapore testbed; results from it are not U.S.
deployment evidence and not the article's data. Chronological splitting uses days from stream start (5 train, 2 development, rest test), so list the
normal file first; change `configs/default.yaml` if your files need other boundaries.
