"""Local scoring/processing latency. Wall-clock, monotonic, reported separately from the data clock and
never equated with analyst response time."""

from __future__ import annotations

import platform
import time

import numpy as np

from infra_defense.features import build_features


def profile_scoring(p, fitted: dict, cfg: dict) -> dict:
    pr = cfg["profiling"]
    test = (p.split == "test").to_numpy()
    X = p.fs.X[test].to_numpy()
    iso = fitted["iforest"].model
    n = len(X)
    out: dict = {"hardware": {"platform": platform.platform(), "processor": platform.processor(),
                              "machine": platform.machine()},
                 "timer": "time.perf_counter (monotonic)", "warmup_runs": pr["warmup_runs"], "repeats": pr["repeats"],
                 "rows_scored": n, "scope": "model inference on precomputed features, plus feature construction"}
    res = {}
    for b in pr["batch_sizes"]:
        size = n if b == 0 else b
        chunks = [X[i:i + size] for i in range(0, min(n, size * 200), size)]  # at most 200 batches timed
        for _ in range(pr["warmup_runs"]):
            iso.score_samples(chunks[0])
        runs = []
        for _ in range(pr["repeats"]):
            t = time.perf_counter()
            for c in chunks:
                iso.score_samples(c)
            runs.append(time.perf_counter() - t)
        rows = sum(len(c) for c in chunks)
        per_row_us = [r / rows * 1e6 for r in runs]
        res[f"iforest_batch_{size}"] = {"batch_size": size, "rows_per_repeat": rows, "median_us_per_row": float(np.median(per_row_us)),
                                        "min_us_per_row": float(np.min(per_row_us)), "max_us_per_row": float(np.max(per_row_us))}
    t = time.perf_counter()
    for _ in range(pr["repeats"]):
        build_features(p.bundle.readings, p.baseline, cfg["window_steps"], cfg["delta_steps"], cfg["step_minutes"])
    feat_s = (time.perf_counter() - t) / pr["repeats"]
    res["feature_construction"] = {"seconds_per_full_stream": feat_s, "stream_rows": int(len(p.fs.meta)),
                                   "us_per_row": feat_s / len(p.fs.meta) * 1e6}
    out["results"] = res
    out["caveat"] = "single machine, shared desktop OS, small batches; not a throughput claim and not comparable to any article timing"
    return out
