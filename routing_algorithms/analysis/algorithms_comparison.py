"""Case-by-case comparison of the routing_algorithms/reports/*.txt outputs.

Aggregates the already-computed Dijkstra / h_geo / h_cheat (/ h_bcn once it
exists) per-pair reports by graph region, instead of only the single global
number each report already prints on its own. Every pair is put in one of the
5 cases below, based on how source and target relate to the Barcelona
subway's Center/Branch topology (routing_algorithms/barcelona_divison.py):
  CC - source and target both in the Center
  CB - source in the Center, target in a Branch
  BC - source in a Branch, target in the Center
  SB - source and target in the SAME Branch
  DB - source and target in DIFFERENT Branches

Why split by case at all: graph_inspection/graph_draw/resources/graph.png shows
that, setting aside PW (entry<->platform) edges, the subway network's shape is
a "ball" with 8 branches sticking out of it, which is exactly the Center/Branch_*
split barcelona_divison.py encodes. Within that shape, the large majority of PW
and TF (cross-line transfer) edges sit in the Center, not in the branches.
Those two facts mean a heuristic's real payoff can look very different case by
case (e.g. crossing into or out of a branch vs. staying inside the dense
Center), which the single aggregate proportion already reported by
a_star_report.py/a_star_need_report.py cannot show on its own.

Requires: one report file per heuristic (DIJKSTRA_REPORT_FILE, A_STAR_GEO_REPORT_FILE,
A_STAR_CHEAT_REPORT_FILE, from routing_algorithms/paths.py), each with at
least the source_id, target_id, and proportion columns (report_fieldnames,
routing_algorithms/reports/report_utils.py). proportion there means
path_vertices / iterations, i.e. how close a search came to only ever
extracting nodes on the optimal path.

Output_name: algorithms_comparison_report.txt (a plain comma-separated table,
convertible via scripts/from_txt_to_xlsx.py) and algorithms_comparison_chart.png,
both saved into 'routing_algorithms/analysis/resources'
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import List, Optional

import matplotlib.pyplot as plt
import pandas as pd

_PROJECT_ROOT = str(Path(__file__).resolve().parents[2])
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from routing_algorithms.barcelona_divison import classify  # noqa: E402
from routing_algorithms.paths import (  # noqa: E402
    A_STAR_CHEAT_REPORT_FILE,
    A_STAR_GEO_REPORT_FILE,
    ALGORITHMS_COMPARISON_REPORT_FILE,
    DIJKSTRA_REPORT_FILE,
)

HEURISTIC_REPORTS = {
    "Dijkstra": DIJKSTRA_REPORT_FILE,
    "a_star_h_geo": A_STAR_GEO_REPORT_FILE,
    "a_star_h_cheat": A_STAR_CHEAT_REPORT_FILE,
    # "a_star_h_bcn": A_STAR_BCN_REPORT_FILE,  # uncomment once h_bcn exists (heuristics/h_bcn.py)
}
# Dijkstra has no heuristic, so only a_star_h_* labels get an "A*" prefix in the chart legend.
LEGEND_LABEL_BY_HEURISTIC = {
    "Dijkstra": "Dijkstra",
    "a_star_h_geo": "A* (h_geo)",
    "a_star_h_cheat": "A* (h_cheat)",
    "a_star_h_bcn": "A* (h_bcn)",
}
# Fixed categorical colors (dataviz skill's validated default palette, slots
# 1-4 in order), one per heuristic, so the same heuristic always gets the
# same color across runs/charts.
COLOR_BY_HEURISTIC = {
    "Dijkstra": "#2a78d6",
    "a_star_h_geo": "#1baf7a",
    "a_star_h_cheat": "#eda100",
    "a_star_h_bcn": "#008300",
}
CASE_DEFINITIONS = {
    "CC": "source and target both in the Center",
    "CB": "source in the Center, target in a Branch",
    "BC": "source in a Branch, target in the Center",
    "SB": "source and target in the SAME Branch",
    "DB": "source and target in DIFFERENT Branches",
}
CASE_ORDER = [*CASE_DEFINITIONS, "GLOBAL"]
CASE_LEGEND_LINES = [
    "  |  ".join(
        f"{case}: {definition}"
        for case, definition in list(CASE_DEFINITIONS.items())[:3]
    ),
    "  |  ".join(
        f"{case}: {definition}"
        for case, definition in list(CASE_DEFINITIONS.items())[3:]
    ),
]
OUTPUT_PATH = Path(ALGORITHMS_COMPARISON_REPORT_FILE)
CHART_OUTPUT_PATH = OUTPUT_PATH.parent / "algorithms_comparison_chart.png"


def analyze(path: str, dtype_ids: type = str) -> pd.DataFrame:
    """Read one heuristic's report file and tag every row with its case.

    args:
        path: Path to a report file with at least source_id, target_id, and
            proportion columns (e.g. DIJKSTRA_REPORT_FILE).
        dtype_ids: dtype forced on source_id/target_id, so ids like "1.111"
            are read as strings, not floats.

    returns:
        The report as a DataFrame, with an extra "case" column from classify.
    """
    df = pd.read_csv(path, dtype={"source_id": dtype_ids, "target_id": dtype_ids})
    df["case"] = [classify(s, t) for s, t in zip(df["source_id"], df["target_id"])]
    return df


def summarize(df: pd.DataFrame, label: str) -> pd.DataFrame:
    """Return per-case mean/median proportion, plus a GLOBAL row, for one heuristic.

    args:
        df: A report DataFrame from analyze, with a "case" column.
        label: The heuristic's name, used to prefix this heuristic's columns
            (e.g. "Dijkstra" -> "Dijkstra_proportion_mean").

    returns:
        DataFrame indexed by case (CC/CB/BC/SB/DB/GLOBAL), columns
        f"{label}_proportion_mean"/f"{label}_proportion_median".
    """
    grouped = df.groupby("case")["proportion"]
    summary = pd.DataFrame(
        {
            f"{label}_proportion_mean": grouped.mean(),
            f"{label}_proportion_median": grouped.median(),
        }
    )
    summary.loc["GLOBAL"] = [df["proportion"].mean(), df["proportion"].median()]
    return summary


def case_sizes(df: pd.DataFrame) -> pd.DataFrame:
    """Return the pair count and share of the total, per case, plus a GLOBAL row.

    Every heuristic's report covers the exact same platform pairs (one row
    each, regardless of whether a path was found), so this only needs to run
    once, on whichever report loads first, instead of once per heuristic.

    args:
        df: Any one heuristic's report DataFrame, with a "case" column.

    returns:
        DataFrame indexed by case (CC/CB/BC/SB/DB/GLOBAL), columns "n" (pair
        count) and "pct" (that count's percentage of the GLOBAL total).
    """
    total = len(df)
    sizes = df.groupby("case").size()
    sizes.loc["GLOBAL"] = total
    counts = sizes.to_frame(name="n")
    counts["pct"] = counts["n"] / total * 100
    return counts


def plot_comparison(combined: pd.DataFrame, output_path: Path) -> None:
    """Save a grouped bar chart of each heuristic's mean proportion, by case.

    args:
        combined: The table from main(), indexed by case, with one
            f"{label}_proportion_mean" column per available heuristic.
        output_path: Destination .png path.
    """
    cases = [case for case in CASE_ORDER if case in combined.index]
    labels = [
        label
        for label in HEURISTIC_REPORTS
        if f"{label}_proportion_mean" in combined.columns
    ]
    bar_width = 0.8 / len(labels)
    positions = range(len(cases))

    fig, ax = plt.subplots(figsize=(11, 5.5), facecolor="#fcfcfb")
    ax.set_facecolor("#fcfcfb")

    for i, label in enumerate(labels):
        values = combined.loc[cases, f"{label}_proportion_mean"]
        offsets = [pos + (i - (len(labels) - 1) / 2) * bar_width for pos in positions]
        bars = ax.bar(
            offsets,
            values,
            width=bar_width,
            color=COLOR_BY_HEURISTIC[label],
            edgecolor="none",
            label=LEGEND_LABEL_BY_HEURISTIC[label],
            zorder=3,
        )
        ax.bar_label(bars, fmt="%.2f", padding=2, color="#52514e", fontsize=8)

    ax.set_xticks(list(positions))
    ax.set_xticklabels(
        [
            f"{case}\nn={combined.loc[case, 'n']:.0f} ({combined.loc[case, 'pct']:.1f}%)"
            for case in cases
        ],
        color="#52514e",
    )
    ax.set_ylabel("Mean proportion (path_vertices / iterations)", color="#52514e")
    fig.suptitle(
        "Algorithm performance by graph region",
        x=0.01,
        ha="left",
        y=0.99,
        fontsize=13,
        color="#0b0b0b",
    )
    ax.set_title(
        "Region case depends on where the source and target platforms sit (Center vs. Branch)",
        loc="left",
        fontsize=9.5,
        color="#52514e",
        pad=12,
    )
    ax.set_ylim(
        0,
        combined[[f"{label}_proportion_mean" for label in labels]].to_numpy().max()
        * 1.15,
    )

    ax.yaxis.grid(True, color="#e1e0d9", linewidth=1, zorder=0)
    ax.set_axisbelow(True)
    for spine in ("top", "right", "left"):
        ax.spines[spine].set_visible(False)
    ax.spines["bottom"].set_color("#c3c2b7")
    ax.tick_params(axis="both", colors="#898781", length=0)
    # Legend lives above the axes (figure-level), not inside it: every case's
    # h_cheat bar sits near the top of the range, so an in-axes legend would
    # always collide with some bar's value label.
    fig.legend(
        *ax.get_legend_handles_labels(),
        frameon=False,
        loc="upper right",
        bbox_to_anchor=(0.99, 0.90),
        labelcolor="#52514e",
        ncol=3,
    )

    fig.text(0.01, 0.045, CASE_LEGEND_LINES[0], fontsize=7, color="#898781")
    fig.text(0.01, 0.015, CASE_LEGEND_LINES[1], fontsize=7, color="#898781")

    fig.tight_layout(rect=(0, 0.09, 1, 0.88))
    fig.savefig(output_path, dpi=150)
    plt.close(fig)


def main() -> pd.DataFrame:
    """Build the case-by-case comparison table across every available heuristic report.

    returns:
        The combined comparison table (also written to OUTPUT_PATH and
        charted to CHART_OUTPUT_PATH), indexed by case in CASE_ORDER: "n",
        "pct", a mean/median column pair per available heuristic report, and
        a trailing "legend" column spelling out each case.
    """
    summaries: List[pd.DataFrame] = []
    n_column: Optional[pd.DataFrame] = None
    combined: pd.DataFrame

    for label, path in HEURISTIC_REPORTS.items():
        if not Path(path).exists():
            print(f"Skipping {label}: no report found at {path}")
            continue
        df = analyze(path)
        if n_column is None:
            n_column = case_sizes(df)
        summaries.append(summarize(df, label))

    combined = pd.concat([n_column, *summaries], axis=1).reindex(CASE_ORDER)
    combined["legend"] = [
        CASE_DEFINITIONS.get(case, "All cases combined") for case in combined.index
    ]
    combined = combined.round(4)

    pd.set_option("display.float_format", lambda x: f"{x:.4f}")
    print(combined)

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    combined.to_csv(OUTPUT_PATH)
    plot_comparison(combined, CHART_OUTPUT_PATH)
    return combined


if __name__ == "__main__":
    main()
    print(f"{OUTPUT_PATH.name} generated into {OUTPUT_PATH.relative_to(_PROJECT_ROOT)}")
    print(
        f"{CHART_OUTPUT_PATH.name} generated into {CHART_OUTPUT_PATH.relative_to(_PROJECT_ROOT)}"
    )
