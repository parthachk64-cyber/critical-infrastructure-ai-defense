"""Fixed rule baseline (companion; NOT a detector from the article, whose detectors are not specified in the
accessible text). Score = minimum over the last N steps of max_s |z_s|, so a single noisy sample cannot alert.
Orientation: higher = more anomalous."""

from __future__ import annotations

import pandas as pd

from infra_defense.features import FeatureSet


class RuleDetector:
    def __init__(self, persistence_steps: int = 2, version: str = "rule-v1") -> None:
        if persistence_steps < 1:
            raise ValueError("persistence_steps must be >= 1")
        self.persistence, self.version = persistence_steps, version

    def fit(self, fs: FeatureSet, mask: pd.Series) -> RuleDetector:
        return self  # fixed rule: nothing to learn

    def score(self, fs: FeatureSet) -> pd.Series:
        s = fs.absz.groupby(fs.meta["asset_id"]).transform(lambda x: x.rolling(self.persistence, min_periods=1).min())
        return s.astype(float)
