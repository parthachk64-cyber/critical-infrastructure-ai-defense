"""Event-level metrics with explicit undefined values and denominators."""

from __future__ import annotations

import numpy as np
import pandas as pd
from sklearn.metrics import average_precision_score


def confusion(y: np.ndarray, pred: np.ndarray) -> dict:
    y, pred = np.asarray(y).astype(bool), np.asarray(pred).astype(bool)
    tp, fp = int((pred & y).sum()), int((pred & ~y).sum())
    fn, tn = int((~pred & y).sum()), int((~pred & ~y).sum())
    p = tp / (tp + fp) if (tp + fp) else None
    r = tp / (tp + fn) if (tp + fn) else None
    f1 = (2 * p * r / (p + r) if p and r else (0.0 if p is not None and r is not None else None))
    return {"tp": tp, "fp": fp, "fn": fn, "tn": tn, "rows": int(len(y)), "positives": tp + fn,
            "negatives": fp + tn, "prevalence": (tp + fn) / len(y) if len(y) else None,
            "precision": p, "recall": r, "f1": f1, "false_alert_rate": fp / (fp + tn) if (fp + tn) else None}


def average_precision(y: np.ndarray, score: np.ndarray) -> float | None:
    """Defined only with continuous scores (>1 distinct value) and both classes present."""
    y = np.asarray(y).astype(int)
    if y.sum() == 0 or y.sum() == len(y) or len(np.unique(score)) < 2:
        return None
    return float(average_precision_score(y, score))


def budget_threshold(dev_scores: pd.Series, dev_is_positive: pd.Series, rate: float) -> float:
    """Smallest score value v such that at most floor(rate * n_normal) NORMAL development rows score >= v.

    Rows scoring exactly v are alerts (>=). If no value satisfies the budget (ties at the top), the threshold is just
    above the maximum normal score, so the budget is never exceeded on the development period."""
    normal = np.sort(dev_scores[~dev_is_positive.to_numpy()].to_numpy())[::-1]
    if normal.size == 0:
        raise ValueError("no normal development rows to set an alert budget")
    k = int(np.floor(rate * normal.size))
    for v in np.unique(normal)[::-1][::-1]:          # ascending unique values
        if int((normal >= v).sum()) <= k:
            return float(v)
    return float(np.nextafter(normal[0], np.inf))


def monitored_asset_hours(meta: pd.DataFrame, step_minutes: int) -> float:
    return float(len(meta) * step_minutes / 60.0)
