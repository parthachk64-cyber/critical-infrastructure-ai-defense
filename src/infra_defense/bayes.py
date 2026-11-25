"""ILLUSTRATIVE risk graph. All probabilities are EXPERT-SPECIFIED EXAMPLES chosen by this project's author.
They are not learned from data, not validated, and not the structure or tables of the article's Figure 5
(whose structure and probabilities could not be verified; see docs/paper-map.md).

Structure (latent concern C with two observed context parents and two evidence children):

    M (planned maintenance active) ──┐
                                     ├─> C (concern: high/low) ──> A (anomaly alert raised)
    K (asset criticality high)     ──┘                          └─> R (corroborated by another asset)

Evidence semantics: A = a detector alert group exists for the asset in the window; R = an alert group on a DIFFERENT
asset starts within the corroboration window. "Concern" is a triage-priority variable, NOT a probability of attack.
A missing (None) evidence variable is marginalised out, never treated as "no".
"""

from __future__ import annotations

from itertools import product

import pandas as pd

P_M = {True: 0.10, False: 0.90}
P_K = {True: 0.40, False: 0.60}
P_C_HIGH = {(True, True): 0.10, (True, False): 0.05, (False, True): 0.30, (False, False): 0.15}  # P(C=high | M, K)
P_A_GIVEN_C = {True: 0.85, False: 0.05}   # P(A=yes | C=high / low)
P_R_GIVEN_C = {True: 0.60, False: 0.03}   # P(R=yes | C=high / low)
VERSION = "bayes-example-v1"
PROVENANCE = "expert-specified example probabilities; not learned; not from the article"


def validate() -> None:
    for d in (P_M, P_K):
        if abs(sum(d.values()) - 1) > 1e-12:
            raise ValueError("prior does not sum to 1")
    for k, p in P_C_HIGH.items():
        if not 0 <= p <= 1:
            raise ValueError(f"P(C|{k}) outside [0,1]")
    for d in (P_A_GIVEN_C, P_R_GIVEN_C):
        if any(not 0 <= v <= 1 for v in d.values()):
            raise ValueError("conditional outside [0,1]")


def _lik(table: dict[bool, float], c: bool, obs: bool | None) -> float:
    if obs is None:
        return 1.0  # marginalised: sum over both outcomes of a normalised child = 1
    p = table[c]
    return p if obs else 1.0 - p


def posterior_high(maintenance: bool | None = None, critical: bool | None = None,
                   anomaly: bool | None = None, corroborated: bool | None = None) -> float:
    """P(C=high | evidence) by exact enumeration. None = not observed."""
    validate()
    num = den = 0.0
    for m, k, c in product((True, False), repeat=3):
        if maintenance is not None and m != maintenance:
            continue
        if critical is not None and k != critical:
            continue
        pc = P_C_HIGH[(m, k)] if c else 1.0 - P_C_HIGH[(m, k)]
        w = P_M[m] * P_K[k] * pc * _lik(P_A_GIVEN_C, c, anomaly) * _lik(P_R_GIVEN_C, c, corroborated)
        den += w
        num += w if c else 0.0
    return num / den


def cpt_tables() -> dict[str, pd.DataFrame]:
    rows = [{"maintenance": m, "critical": k, "P(concern=high)": p} for (m, k), p in P_C_HIGH.items()]
    return {"P(C|M,K)": pd.DataFrame(rows),
            "P(A|C)": pd.DataFrame([{"concern": "high", "P(alert=yes)": 0.85}, {"concern": "low", "P(alert=yes)": 0.05}]),
            "P(R|C)": pd.DataFrame([{"concern": "high", "P(corroborated=yes)": 0.60},
                                    {"concern": "low", "P(corroborated=yes)": 0.03}])}
