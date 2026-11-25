"""Original figures generated from artifacts. No article image is copied; no article value is re-plotted."""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyBboxPatch  # noqa: E402

from infra_defense import bayes  # noqa: E402

BLUE, ORANGE, GREEN, GREY, RED = "#1b6ca8", "#c4511d", "#2a7f3f", "#888888", "#b22222"


def _box(ax, xy, w, h, text, fc, ec="#333", fs=9):
    ax.add_patch(FancyBboxPatch(xy, w, h, boxstyle="round,pad=0.02", fc=fc, ec=ec, lw=1.2))
    ax.text(xy[0] + w / 2, xy[1] + h / 2, text, ha="center", va="center", fontsize=fs)


def _arrow(ax, a, b):
    ax.annotate("", xy=b, xytext=a, arrowprops=dict(arrowstyle="->", color="#333", lw=1.2))


def fig_workflow(out: Path) -> Path:
    """ORIGINAL redraw of the structure visible in the article's public Figure 1 preview (research design flow)."""
    fig, ax = plt.subplots(figsize=(7.2, 7))
    ax.set_xlim(0, 10), ax.set_ylim(0, 12), ax.axis("off")
    _box(ax, (3.5, 10.6), 3, 1, "Research design", "#dbe7fb")
    _box(ax, (0.3, 8.2), 4, 1.3, "Quantitative survey\n(instrument and responses:\nNOT available to this repo)", "#fde2d6")
    _box(ax, (5.7, 8.2), 4, 1.3, "Qualitative literature review\n(cited sources listed on the\npublisher page)", "#dff0e1")
    _box(ax, (3, 6.0), 4, 1, "Data analysis", "#dbe7fb")
    _box(ax, (3, 4.0), 4, 1, "Integration and triangulation", "#dbe7fb")
    _box(ax, (3, 2.0), 4, 1, "Ethical considerations", "#dbe7fb")
    for a, b in [((5, 10.6), (2.3, 9.5)), ((5, 10.6), (7.7, 9.5)), ((2.3, 8.2), (4.3, 7.0)), ((7.7, 8.2), (5.7, 7.0)),
                 ((5, 6.0), (5, 5.0)), ((5, 4.0), (5, 3.0))]:
        _arrow(ax, a, b)
    ax.text(0.2, 0.6, "Original diagram. Stage names transcribed from the public Fig. 1 preview "
            "(Springer, DOI 10.1365/s43439-026-00169-5).\nRed = no data accessible here; green = public sources only. "
            "The preview shows no Colonial Pipeline source box\nand no expert-validation stage.", fontsize=7.5, va="bottom")
    p = Path(out) / "fig1_workflow_original.png"
    fig.savefig(p, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return p


def fig_bayes(out: Path) -> Path:
    fig, ax = plt.subplots(figsize=(8, 4.8))
    ax.set_xlim(0, 12), ax.set_ylim(0, 7), ax.axis("off")
    pos = {"M": (1, 5.2), "K": (1, 2.2), "C": (5, 3.7), "A": (9.5, 5.2), "R": (9.5, 2.2)}
    txt = {"M": "M\nplanned\nmaintenance", "K": "K\ncritical\nasset", "C": "C\nconcern\n(high/low)", "A": "A\nalert\nraised", "R": "R\ncorroborated\nby other asset"}
    for k, (x, y) in pos.items():
        _box(ax, (x, y), 2.2, 1.5, txt[k], "#dbe7fb" if k == "C" else "#eef3fa", fs=8)
    for a, b in [("M", "C"), ("K", "C"), ("C", "A"), ("C", "R")]:
        _arrow(ax, (pos[a][0] + 2.2, pos[a][1] + 0.75) if a in "MK" else (pos[a][0] + 2.2, pos[a][1] + 0.75),
               (pos[b][0], pos[b][1] + 0.75))
    ax.text(0.2, 0.3, "ILLUSTRATIVE example (" + bayes.VERSION + "): " + bayes.PROVENANCE +
            ".\nP(C=high|M,K): " + ", ".join(f"M={int(m)},K={int(k)}: {v:.2f}" for (m, k), v in bayes.P_C_HIGH.items()) +
            f"\nP(A|C=high)={bayes.P_A_GIVEN_C[True]}, P(A|C=low)={bayes.P_A_GIVEN_C[False]}; "
            f"P(R|C=high)={bayes.P_R_GIVEN_C[True]}, P(R|C=low)={bayes.P_R_GIVEN_C[False]}.  Not the article's Fig. 5.",
            fontsize=7, va="bottom")
    p = Path(out) / "fig5_bayes_example.png"
    fig.savefig(p, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return p


def fig_detection(metrics: dict, out: Path) -> Path:
    fig, ax = plt.subplots(figsize=(6, 4))
    names = {"rule": "fixed rule", "iforest": "Isolation Forest"}
    w = 0.25
    for j, (m, col) in enumerate((("precision", BLUE), ("recall", GREEN), ("f1", ORANGE))):
        vals = [metrics["detectors"][d]["event"][m] or 0.0 for d in names]
        ax.bar([i + (j - 1) * w for i in range(2)], vals, w, label=m, color=col)
    ax.set_xticks(range(2)), ax.set_xticklabels(names.values()), ax.set_ylim(0, 1), ax.set_ylabel("score (test rows)")
    ax.set_title("SYNTHETIC demonstration, equal alert budget\n(companion analogue of the article's Fig. 6 comparison)", fontsize=9)
    ax.legend()
    p = Path(out) / "fig6_companion_detection.png"
    fig.savefig(p, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return p


def fig_timing(metrics: dict, out: Path) -> Path:
    pr = metrics["profiling"]["results"]
    keys = [k for k in pr if k.startswith("iforest_batch_")]
    fig, ax = plt.subplots(figsize=(6, 4))
    ax.bar([k.replace("iforest_batch_", "batch ") for k in keys], [pr[k]["median_us_per_row"] for k in keys], color=BLUE)
    ax.set_ylabel("microseconds per row (median of repeats)")
    ax.set_title("Isolation Forest scoring cost, local CPU\n(conditions in manifest; not comparable to the article's Fig. 4)", fontsize=9)
    ax.set_yscale("log")
    p = Path(out) / "fig4_companion_timing.png"
    fig.savefig(p, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return p


def fig_case(p, fitted: dict, trace: dict, out: Path) -> Path:
    import pandas as pd
    assets = trace["scenario"]["assets"]
    lo = pd.Timestamp(trace["scenario"]["start"]) - pd.Timedelta(hours=3)
    hi = pd.Timestamp(trace["scenario"]["end"]) + pd.Timedelta(hours=3)
    fig, axes = plt.subplots(len(assets), 1, figsize=(7.5, 2.6 * len(assets)), sharex=True, squeeze=False)
    for ax, a in zip(axes[:, 0], assets):
        m = (p.fs.meta["asset_id"] == a) & (p.fs.meta["ts"] >= lo) & (p.fs.meta["ts"] <= hi)
        ax.plot(p.fs.meta["ts"][m], fitted["scores"]["rule"][m], color=BLUE, label="rule score")
        ax.axhline(fitted["thresholds"]["rule"], color=BLUE, ls=":", lw=1)
        ax2 = ax.twinx()
        ax2.plot(p.fs.meta["ts"][m], fitted["scores"]["iforest"][m], color=ORANGE, label="iforest score")
        ax2.axhline(fitted["thresholds"]["iforest"], color=ORANGE, ls=":", lw=1)
        for det, col in (("rule", BLUE), ("iforest", ORANGE)):
            for c in trace["detectors"][det]["cases"]:
                if c["asset_id"] == a:
                    ax.axvline(pd.Timestamp(c["alert_ts"]), color=col, alpha=.6)
                    if c.get("review"):
                        ax.axvline(pd.Timestamp(c["review"]["decided_at"]), color=GREEN, ls="--", alpha=.8)
        ax.axvspan(pd.Timestamp(trace["scenario"]["start"]), pd.Timestamp(trace["scenario"]["end"]), color=GREY, alpha=.15)
        ax.set_ylabel(a, fontsize=8)
    axes[0, 0].set_title(f"{trace['example']}: data-clock timeline (grey = annotated window; solid = alert; dashed green = reviewer decision)\n"
                         "blue = rule score, orange = Isolation Forest score (dotted = thresholds). SYNTHETIC demo",
                         fontsize=7)
    fig.autofmt_xdate()
    path = Path(out) / "fig_case_trace.png"
    fig.savefig(path, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return path


def fig_coverage(manifest_rows: list[dict], out: Path) -> Path:
    fig, ax = plt.subplots(figsize=(9, 3.6))
    ax.axis("off")
    cell = [[r["item"], r["article_content"], r["status"]] for r in manifest_rows]
    t = ax.table(cellText=cell, colLabels=["Article item", "What the public preview shows", "Repository treatment / status"],
                 loc="center", cellLoc="left", colWidths=[0.1, 0.45, 0.45])
    t.auto_set_font_size(False), t.set_fontsize(7), t.scale(1, 1.9)
    ax.set_title("Figure coverage map (source of truth: references/reported/manifest.csv)", fontsize=9)
    p = Path(out) / "fig_coverage_status.png"
    fig.savefig(p, dpi=150, bbox_inches="tight")
    plt.close(fig)
    return p


def generate_all(p, fitted, metrics, traces, out: Path) -> list[Path]:
    import csv

    from infra_defense.config import REPO_ROOT
    out.mkdir(parents=True, exist_ok=True)
    made = [fig_workflow(out), fig_bayes(out), fig_detection(metrics, out), fig_timing(metrics, out),
            fig_case(p, fitted, next(t for t in traces if t["example"].startswith("3_")), out)]
    mf = REPO_ROOT / "references" / "reported" / "manifest.csv"
    if mf.exists():
        rows = [r for r in csv.DictReader(open(mf, encoding="utf-8")) if r["item"].startswith("Fig.")]
        short = [{"item": r["item"], "article_content": r["what_can_be_identified"][:70],
                  "status": r["verification_status"][:60]} for r in rows]
        made.append(fig_coverage(short, out))
    (out / "figures.json").write_text(json.dumps([str(x.name) for x in made]), encoding="utf-8")
    return made
