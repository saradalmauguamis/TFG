"""Case-by-case comparison of the shortest_paths_algorithms/reports/*.txt outputs.

Aggregates the already-computed Dijkstra / h_geo / h_cheat / h_bcn per-pair
reports by graph region, instead of only the single global
number each report already prints on its own. Every pair is put in one of the
5 cases below, based on how source and target relate to the Barcelona
subway's Center/Branch topology (shortest_paths_algorithms/barcelona_division.py):
  CC - source and target both in the Center
  CB - source in the Center, target in a Branch
  BC - source in a Branch, target in the Center
  SB - source and target in the SAME Branch
  DB - source and target in DIFFERENT Branches

Why split by case at all: graph_inspection/graph_draw/resources/graph.png shows
that, setting aside PW (entry<->platform) edges, the subway network's shape is
a "ball" with 8 branches sticking out of it, which is exactly the Center/Branch_*
split barcelona_division.py encodes. Within that shape, the large majority of PW
and TF (cross-line transfer) edges sit in the Center, not in the branches.
Those two facts mean a heuristic's real payoff can look very different case by
case (e.g. crossing into or out of a branch vs. staying inside the dense
Center), which the single aggregate proportion already reported by
a_star_report.py/dijkstra_report.py cannot show on its own.

Requires: one report file per heuristic per graph mode (DIJKSTRA_REPORT_FULL_FILE/
DIJKSTRA_REPORT_NO_PW_FILE, A_STAR_GEO_REPORT_FULL_FILE/A_STAR_GEO_REPORT_NO_PW_FILE,
A_STAR_CHEAT_REPORT_FULL_FILE/A_STAR_CHEAT_REPORT_NO_PW_FILE,
A_STAR_BCN_REPORT_FULL_FILE/A_STAR_BCN_REPORT_NO_PW_FILE, from
shortest_paths_algorithms/paths.py, the full/no_pw pair generated with
GRAPH_MODE=FULL_GRAPH/WITHOUT_ENTRANCES_GRAPH respectively, see
shortest_paths_algorithms/algorithms_utils.py), each with at
least the source_id, target_id, and proportion columns (report_fieldnames,
shortest_paths_algorithms/reports/report_utils.py). proportion there means
path_vertices / iterations, i.e. how close a search came to only ever
extracting nodes on the optimal path.

Two outputs are built, from HEURISTIC_REPORTS_BY_MODE:
- *_full_report.txt / *_full_chart.png: FULL_GRAPH reports only, one bar per
  heuristic per case, same as this module originally produced (just switched
  from the no_pw half to the full half).
- *_combined_report.txt / *_combined_chart.png: both FULL_GRAPH and
  WITHOUT_ENTRANCES_GRAPH reports together, two adjacent bars per heuristic per
  case (full graph, no_pw graph): same COLOR_BY_HEURISTIC per heuristic in
  both bars, with the no_pw bar hatched (HATCH_BY_MODE) so the two graph modes
  stay visually distinct without needing a second color scale.

Output_name: algorithms_comparison_{full,combined}_report.txt (plain
comma-separated tables, convertible via scripts/from_txt_to_xlsx.py) and
algorithms_comparison_{full,combined}_chart.png, all saved into
'shortest_paths_algorithms/analysis/resources'
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import matplotlib.pyplot as plt
import pandas as pd
from matplotlib.patches import Patch

_PROJECT_ROOT = str(Path(__file__).resolve().parents[2])
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from shortest_paths_algorithms.barcelona_division import classify  # noqa: E402
from shortest_paths_algorithms.paths import (  # noqa: E402
    A_STAR_CHEAT_REPORT_FULL_FILE,
    A_STAR_CHEAT_REPORT_NO_PW_FILE,
    A_STAR_GEO_REPORT_FULL_FILE,
    A_STAR_GEO_REPORT_NO_PW_FILE,
    A_STAR_BCN_REPORT_FULL_FILE,
    A_STAR_BCN_REPORT_NO_PW_FILE,
    ALGORITHMS_COMPARISON_REPORT_COMBINED_FILE,
    ALGORITHMS_COMPARISON_REPORT_FULL_FILE,
    DIJKSTRA_REPORT_FULL_FILE,
    DIJKSTRA_REPORT_NO_PW_FILE,
)

# Dijkstra has no heuristic, so only a_star_h_* labels get an "A*" prefix in the chart legend.
# The no_pw reports are generated via cut_dijkstra (see dijkstra_report.py), not plain
# Dijkstra, so the legend says so regardless of which graph mode is plotted.
LEGEND_LABEL_BY_HEURISTIC = {
    "Dijkstra": "Cut-Dijkstra",
    "a_star_h_geo": "A*_geo",
    "a_star_h_bcn": "A*_bcn",
    "a_star_h_cheat": "A*_cheat",
}

COLOR_BY_HEURISTIC = {
    "Dijkstra": "#e87ba4",
    "a_star_h_geo": "#1baf7a",
    "a_star_h_bcn": "#9c85d1",
    "a_star_h_cheat": "#d99f3d",
}

# One report file per heuristic (outer key), per graph mode (inner key):
# every heuristic/mode combination LEGEND_LABEL_BY_HEURISTIC and
# GRAPH_MODE_LABEL (algorithms_utils.py) can name.
HEURISTIC_REPORTS_BY_MODE: Dict[str, Dict[str, str]] = {
    "full": {
        "Dijkstra": DIJKSTRA_REPORT_FULL_FILE,
        "a_star_h_geo": A_STAR_GEO_REPORT_FULL_FILE,
        "a_star_h_bcn": A_STAR_BCN_REPORT_FULL_FILE,
        "a_star_h_cheat": A_STAR_CHEAT_REPORT_FULL_FILE,
    },
    "no_pw": {
        "Dijkstra": DIJKSTRA_REPORT_NO_PW_FILE,
        "a_star_h_geo": A_STAR_GEO_REPORT_NO_PW_FILE,
        "a_star_h_bcn": A_STAR_BCN_REPORT_NO_PW_FILE,
        "a_star_h_cheat": A_STAR_CHEAT_REPORT_NO_PW_FILE,
    },
}
MODE_LABEL = {"full": "Full graph", "no_pw": "Without entrances (no PW)"}
# Solid for full, hatched for no_pw: the combined chart tells graph modes apart
# by pattern, not color, since color is already spent on COLOR_BY_HEURISTIC.
HATCH_BY_MODE = {"full": "", "no_pw": "//"}

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
OUTPUT_PATH_FULL = Path(ALGORITHMS_COMPARISON_REPORT_FULL_FILE)
OUTPUT_PATH_COMBINED = Path(ALGORITHMS_COMPARISON_REPORT_COMBINED_FILE)
CHART_OUTPUT_PATH_FULL = (
    OUTPUT_PATH_FULL.parent / "algorithms_comparison_full_chart.png"
)
CHART_OUTPUT_PATH_COMBINED = (
    OUTPUT_PATH_COMBINED.parent / "algorithms_comparison_combined_chart.png"
)


def analyze(path: str, dtype_ids: type = str) -> pd.DataFrame:
    """Read one heuristic's report file and tag every row with its case.

    args:
        path: Path to a report file with at least source_id, target_id, and
            proportion columns (e.g. DIJKSTRA_REPORT_NO_PW_FILE).
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


def build_combined(modes: List[str]) -> Tuple[pd.DataFrame, List[Tuple[str, str]]]:
    """Build the case-by-case comparison table for one or more graph modes.

    args:
        modes: Which HEURISTIC_REPORTS_BY_MODE keys to include, e.g. ["full"]
            for the full-graph-only table/chart or ["full", "no_pw"] for the
            combined one. Column names are prefixed with the mode only when
            more than one mode is requested, so the full-only table's columns
            stay exactly f"{label}_proportion_mean", not
            f"{label}_full_proportion_mean".

    returns:
        (combined, used): combined is indexed by case in CASE_ORDER ("n",
        "pct", a mean/median column pair per available (label, mode)
        combination, and a trailing "legend" column); used is the ordered
        list of (label, mode) pairs that actually had a report to load,
        heuristic-major (both of one heuristic's modes adjacent) so
        plot_comparison can group each heuristic's bars next to each other.
    """
    multi_mode = len(modes) > 1
    summaries: List[pd.DataFrame] = []
    used: List[Tuple[str, str]] = []
    n_column: Optional[pd.DataFrame] = None
    combined: pd.DataFrame

    for label in LEGEND_LABEL_BY_HEURISTIC:
        for mode in modes:
            path = HEURISTIC_REPORTS_BY_MODE[mode][label]
            if not Path(path).exists():
                print(f"Skipping {label} ({mode}): no report found at {path}")
                continue
            df = analyze(path)
            if n_column is None:
                n_column = case_sizes(df)
            summaries.append(summarize(df, f"{label}_{mode}" if multi_mode else label))
            used.append((label, mode))

    combined = pd.concat([n_column, *summaries], axis=1).reindex(CASE_ORDER)
    combined["legend"] = [
        CASE_DEFINITIONS.get(case, "All cases combined") for case in combined.index
    ]
    return combined.round(4), used


def plot_comparison(
    combined: pd.DataFrame,
    output_path: Path,
    used: List[Tuple[str, str]],
    modes: List[str],
) -> None:
    """Save a grouped bar chart of each heuristic's mean proportion, by case.

    args:
        combined: The table from build_combined, indexed by case, with one
            f"{label}_proportion_mean" (single mode) or
            f"{label}_{mode}_proportion_mean" (multiple modes) column per
            (label, mode) pair in used.
        output_path: Destination .png path.
        used: (label, mode) pairs to draw a bar for, in draw order:
            heuristic-major, so one heuristic's full/no_pw bars sit adjacent
            (build_combined's own order).
        modes: Which graph modes are being plotted (["full"], ["no_pw"], or
            ["full", "no_pw"]); len(modes) > 1 is what turns on hatching and
            the second (mode) legend; a single mode looks exactly as this
            chart always has.
    """
    multi_mode = len(modes) > 1
    cases = [case for case in CASE_ORDER if case in combined.index]
    bar_width = 0.8 / len(used)
    positions = range(len(cases))
    value_columns: List[str]
    heuristic_handles: List[Patch]
    mode_handles: List[Patch]

    fig, ax = plt.subplots(
        figsize=(15, 5.5) if multi_mode else (11, 5.5), facecolor="#fcfcfb"
    )
    ax.set_facecolor("#fcfcfb")

    value_columns = [
        f"{label}_{mode}_proportion_mean" if multi_mode else f"{label}_proportion_mean"
        for label, mode in used
    ]
    for i, ((label, mode), column) in enumerate(zip(used, value_columns)):
        values = combined.loc[cases, column]
        offsets = [pos + (i - (len(used) - 1) / 2) * bar_width for pos in positions]
        bars = ax.bar(
            offsets,
            values,
            width=bar_width,
            color=COLOR_BY_HEURISTIC[label],
            edgecolor="#52514e" if multi_mode else "none",
            linewidth=0.6 if multi_mode else 0,
            hatch=HATCH_BY_MODE[mode] if multi_mode else None,
            zorder=3,
        )
        ax.bar_label(
            bars,
            fmt="%.2f",
            padding=2,
            color="#52514e",
            fontsize=8 if not multi_mode else 6.5,
            rotation=0 if not multi_mode else 90,
        )

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
        "Algorithm performance by graph region"
        + (": full graph vs graph without entrances" if multi_mode else ""),
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
    # Rotated (multi_mode) value labels take up more vertical room per bar than
    # horizontal ones, so they need more headroom above the tallest bar.
    ax.set_ylim(
        0, combined[value_columns].to_numpy().max() * (1.15 if not multi_mode else 1.3)
    )

    ax.yaxis.grid(True, color="#e1e0d9", linewidth=1, zorder=0)
    ax.set_axisbelow(True)
    for spine in ("top", "right", "left"):
        ax.spines[spine].set_visible(False)
    ax.spines["bottom"].set_color("#c3c2b7")
    ax.tick_params(axis="both", colors="#898781", length=0)

    # One legend entry per heuristic color, plus (multi_mode only) one per
    # graph-mode hatch, built from Patch handles instead of each bar's own
    # label, since a bar can only carry one legend entry and we need color
    # (heuristic) and hatch (mode) to be explained separately.
    heuristic_handles = [
        Patch(
            facecolor=COLOR_BY_HEURISTIC[label],
            edgecolor="#52514e" if multi_mode else "none",
            label=LEGEND_LABEL_BY_HEURISTIC[label],
        )
        for label in dict.fromkeys(label for label, _ in used)
    ]
    mode_handles = (
        [
            Patch(
                facecolor="#dedcd2",
                edgecolor="#52514e",
                hatch=HATCH_BY_MODE[mode] or None,
                label=MODE_LABEL[mode],
            )
            for mode in modes
        ]
        if multi_mode
        else []
    )
    # Legend lives above the axes (figure-level), not inside it: every case's
    # h_cheat bar sits near the top of the range, so an in-axes legend would
    # always collide with some bar's value label.
    fig.legend(
        handles=heuristic_handles + mode_handles,
        frameon=False,
        loc="upper right",
        bbox_to_anchor=(0.99, 0.90),
        labelcolor="#52514e",
        ncol=len(heuristic_handles) + len(mode_handles) if multi_mode else 3,
    )

    fig.text(0.01, 0.045, CASE_LEGEND_LINES[0], fontsize=7, color="#898781")
    fig.text(0.01, 0.015, CASE_LEGEND_LINES[1], fontsize=7, color="#898781")

    fig.tight_layout(rect=(0, 0.09, 1, 0.88))
    fig.savefig(output_path, dpi=150)
    plt.close(fig)


def main() -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Build both the full-only and combined (full + no_pw) comparison tables/charts.

    returns:
        (combined_full, combined_all): the two tables from build_combined,
        also written to OUTPUT_PATH_FULL/OUTPUT_PATH_COMBINED and charted to
        CHART_OUTPUT_PATH_FULL/CHART_OUTPUT_PATH_COMBINED.
    """
    combined_full: pd.DataFrame
    used_full: List[Tuple[str, str]]
    combined_all: pd.DataFrame
    used_all: List[Tuple[str, str]]

    pd.set_option("display.float_format", lambda x: f"{x:.4f}")

    combined_full, used_full = build_combined(["full"])
    print(combined_full)
    OUTPUT_PATH_FULL.parent.mkdir(parents=True, exist_ok=True)
    combined_full.to_csv(OUTPUT_PATH_FULL)
    plot_comparison(combined_full, CHART_OUTPUT_PATH_FULL, used_full, ["full"])

    combined_all, used_all = build_combined(["full", "no_pw"])
    print(combined_all)
    OUTPUT_PATH_COMBINED.parent.mkdir(parents=True, exist_ok=True)
    combined_all.to_csv(OUTPUT_PATH_COMBINED)
    plot_comparison(
        combined_all, CHART_OUTPUT_PATH_COMBINED, used_all, ["full", "no_pw"]
    )

    return combined_full, combined_all


if __name__ == "__main__":
    main()
    for report_path in (OUTPUT_PATH_FULL, OUTPUT_PATH_COMBINED):
        print(
            f"{report_path.name} generated into {report_path.relative_to(_PROJECT_ROOT)}"
        )
    for chart_path in (CHART_OUTPUT_PATH_FULL, CHART_OUTPUT_PATH_COMBINED):
        print(
            f"{chart_path.name} generated into {chart_path.relative_to(_PROJECT_ROOT)}"
        )
