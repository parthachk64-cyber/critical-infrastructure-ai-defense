"""Isolation Forest fitted on a normal training interval. Companion baseline, NOT the article's model.
Score orientation: -score_samples, higher = more anomalous. Model files are joblib pickles: load only files you
generated; load() verifies a SHA-256 sidecar."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import sklearn
from sklearn.ensemble import IsolationForest

from infra_defense.features import FeatureSet

ORIENTATION = "higher_is_more_anomalous"


class ModelIntegrityError(RuntimeError):
    pass


class IsolationForestDetector:
    def __init__(self, n_estimators: int = 200, seed: int = 42, version: str = "iforest-v1") -> None:
        self.n_estimators, self.seed, self.version = n_estimators, seed, version
        self.model: IsolationForest | None = None
        self.columns: list[str] = []

    def fit(self, fs: FeatureSet, mask: pd.Series) -> IsolationForestDetector:
        x = fs.X[mask.to_numpy()]
        if len(x) < 50:
            raise ValueError("too few training rows to fit the detector")
        self.columns = list(fs.X.columns)
        self.model = IsolationForest(n_estimators=self.n_estimators, contamination="auto",
                                     random_state=self.seed).fit(x.to_numpy())
        self.n_train = int(len(x))
        return self

    def score(self, fs: FeatureSet) -> pd.Series:
        if self.model is None:
            raise RuntimeError("detector is not fitted")
        if list(fs.X.columns) != self.columns:
            raise ValueError("feature columns differ from those used at fit time")
        return pd.Series(-self.model.score_samples(fs.X.to_numpy()), index=fs.X.index)

    def save(self, directory: Path | str) -> dict:
        d = Path(directory)
        d.mkdir(parents=True, exist_ok=True)
        p = d / "iforest.joblib"
        joblib.dump(self.model, p)
        meta = {"version": self.version, "seed": self.seed, "n_estimators": self.n_estimators, "columns": self.columns,
                "orientation": ORIENTATION, "n_train": self.n_train, "sklearn_version": sklearn.__version__,
                "sha256": hashlib.sha256(p.read_bytes()).hexdigest()}
        (d / "iforest.meta.json").write_text(json.dumps(meta, indent=1, sort_keys=True), encoding="utf-8")
        return meta

    @classmethod
    def load(cls, directory: Path | str) -> IsolationForestDetector:
        d = Path(directory)
        meta = json.loads((d / "iforest.meta.json").read_text(encoding="utf-8"))
        p = d / "iforest.joblib"
        if hashlib.sha256(p.read_bytes()).hexdigest() != meta["sha256"]:
            raise ModelIntegrityError("model file does not match its recorded SHA-256")
        det = cls(meta["n_estimators"], meta["seed"], meta["version"])
        det.model, det.columns, det.n_train = joblib.load(p), meta["columns"], meta["n_train"]
        return det


def score_orientation_check(det: IsolationForestDetector, fs: FeatureSet) -> bool:
    """True if an extreme synthetic row scores higher than the median training-like row (sanity test helper)."""
    s = det.score(fs)
    x = fs.X.copy()
    x.iloc[0] = x.iloc[0] * 0 + 25.0
    ext = -det.model.score_samples(x.iloc[[0]].to_numpy())[0]
    return bool(ext > float(np.median(s)))
