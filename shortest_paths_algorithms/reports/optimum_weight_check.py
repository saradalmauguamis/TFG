"""Sanity check: for every platform pair, optimum_weight must agree across reports.

The 4 reports for one graph mode: dijkstra_{mode}_report.txt,
a_star_{mode}_geo_report.txt, a_star_{mode}_h_bcn_report.txt, and
a_star_{mode}_h_cheat_report.txt (shortest_paths_algorithms/reports/resources/, paths
in shortest_paths_algorithms/paths.py), picked via GRAPH_MODE (FULL_GRAPH or
WITHOUT_ENTRANCES_GRAPH, see shortest_paths_algorithms/algorithms_utils.py), all
run the same collect_platform_pairs pairs over the same graph
(shortest_paths_algorithms/reports/report_utils.py), just with different
search algorithms/heuristics. The actual path found for a pair can legitimately
differ between reports (ties in shortest-path weight aren't unique), but
optimum_weight (the shortest-path cost itself) must not: if it does, one
of the algorithms/heuristics has a bug.

This script never touches or reruns any search: every column it
needs (source_id, target_id, source_name, target_name, optimum_weight) is
already in the report files, so it only reads and cross-compares them via
read_dict_rows (data_validation/gtfs_utils.py).

Methodology:
1. check_missing_files + print_file_disclaimer on the 4 report files for
   GRAPH_MODE, fitting the same pattern as every other report/checker in this
   package.
2. Read each report via read_dict_rows into {(source_id, target_id):
   (source_name, target_name, optimum_weight)}, parsing "NA" to None.
3. For every pair appearing in at least one report, collect its weight from
   each report (None if the pair is missing from that file or is "NA" there)
   and split mismatches into two kinds:
   - weight mismatches: two or more reports found a path, but with different
     optimum_weight, i.e., the actual bug this script exists to catch.
   - reachability mismatches: some reports found a path and others didn't,
     for the same pair, i.e., a different problem (one algorithm silently
     failing to find a reachable path), reported separately since it doesn't
     mean optimum_weight disagrees.
4. Print counts and the offending pairs for both kinds.

Exit code is non-zero if any mismatch of either kind is found, so this can be
used as a safety gate, matching check_missing_files' raise-on-problem idiom.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, List, NamedTuple, Optional, Tuple

_PROJECT_ROOT = str(Path(__file__).resolve().parents[2])
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from data_validation.gtfs_utils import (  # noqa: E402
    check_missing_files,
    print_file_disclaimer,
    read_dict_rows,
)
from shortest_paths_algorithms.algorithms_utils import (  # noqa: E402
    FULL_GRAPH,
    WITHOUT_ENTRANCES_GRAPH,
    GraphMode,
    Node,
)
from shortest_paths_algorithms.config import GRAPH_MODE  # noqa: E402
from shortest_paths_algorithms.paths import (  # noqa: E402
    A_STAR_CHEAT_REPORT_FULL_FILE,
    A_STAR_CHEAT_REPORT_NO_PW_FILE,
    A_STAR_GEO_REPORT_FULL_FILE,
    A_STAR_GEO_REPORT_NO_PW_FILE,
    A_STAR_BCN_REPORT_FULL_FILE,
    A_STAR_BCN_REPORT_NO_PW_FILE,
    DIJKSTRA_REPORT_FULL_FILE,
    DIJKSTRA_REPORT_NO_PW_FILE,
)

_REPORT_FILES_BY_MODE: Dict[GraphMode, List[str]] = {
    FULL_GRAPH: [
        DIJKSTRA_REPORT_FULL_FILE,
        A_STAR_GEO_REPORT_FULL_FILE,
        A_STAR_BCN_REPORT_FULL_FILE,
        A_STAR_CHEAT_REPORT_FULL_FILE,
    ],
    WITHOUT_ENTRANCES_GRAPH: [
        DIJKSTRA_REPORT_NO_PW_FILE,
        A_STAR_GEO_REPORT_NO_PW_FILE,
        A_STAR_BCN_REPORT_NO_PW_FILE,
        A_STAR_CHEAT_REPORT_NO_PW_FILE,
    ],
}
REPORT_FILES: List[str] = _REPORT_FILES_BY_MODE[GRAPH_MODE]

Pair = Tuple[Node, Node]
PairEntry = Tuple[str, str, Optional[int]]  # (source_name, target_name, optimum_weight)


class Mismatch(NamedTuple):
    """One platform pair whose optimum_weight (or reachability) disagrees across reports."""

    source_id: Node
    target_id: Node
    source_name: str
    target_name: str
    weight_by_report: Dict[str, Optional[int]]


def parse_optimum_weight(value: str) -> Optional[int]:
    """Parse a report's optimum_weight column value.

    args:
        value: The raw "optimum_weight" cell, "NA" or an integer string.

    returns:
        None for "NA", otherwise the parsed weight.
    """
    return None if value == "NA" else int(value)


def load_pair_weights(report_path: str) -> Dict[Pair, PairEntry]:
    """Read one report file into a per-pair (names, optimum_weight) lookup.

    args:
        report_path: Path to a platform-to-platform report .txt file, with at
            least source_id, target_id, source_name, target_name, and
            optimum_weight columns.

    returns:
        Dict keyed by (source_id, target_id) to (source_name, target_name,
        optimum_weight), optimum_weight being None for "NA".
    """
    return {
        (row["source_id"], row["target_id"]): (
            row["source_name"],
            row["target_name"],
            parse_optimum_weight(row["optimum_weight"]),
        )
        for row in read_dict_rows(report_path)
    }


def find_mismatches(
    pair_weights_by_report: Dict[str, Dict[Pair, PairEntry]],
) -> Tuple[List[Mismatch], List[Mismatch]]:
    """Cross-compare optimum_weight for every pair across the given reports.

    args:
        pair_weights_by_report: Each report's name mapped to its
            load_pair_weights output.

    returns:
        (weight_mismatches, reachability_mismatches), both sorted by
        (source_id, target_id): see module docstring for the distinction.
    """
    report_names = list(pair_weights_by_report)
    all_pairs = {pair for pairs in pair_weights_by_report.values() for pair in pairs}

    weight_mismatches: List[Mismatch] = []
    reachability_mismatches: List[Mismatch] = []
    for source_id, target_id in sorted(all_pairs):
        source_name = target_name = ""
        weight_by_report: Dict[str, Optional[int]] = {}
        for report_name in report_names:
            entry = pair_weights_by_report[report_name].get((source_id, target_id))
            if entry is None:
                weight_by_report[report_name] = None
                continue
            source_name, target_name, weight = entry
            weight_by_report[report_name] = weight

        present_weights = [w for w in weight_by_report.values() if w is not None]
        row = Mismatch(source_id, target_id, source_name, target_name, weight_by_report)
        if len(set(present_weights)) > 1:
            weight_mismatches.append(row)
        elif present_weights and len(present_weights) < len(report_names):
            reachability_mismatches.append(row)

    return weight_mismatches, reachability_mismatches


def format_weight_by_report(weight_by_report: Dict[str, Optional[int]]) -> str:
    """Render a mismatch's per-report weights for a print line.

    args:
        weight_by_report: Report name to optimum_weight (or None for "NA").

    returns:
        e.g. "dijkstra_no_pw_report=972, a_star_no_pw_geo_report=972,
        a_star_no_pw_h_cheat_report=NA".
    """
    return ", ".join(
        f"{name}={'NA' if weight is None else weight}"
        for name, weight in weight_by_report.items()
    )


def main() -> Tuple[List[Mismatch], List[Mismatch]]:
    """Cross-check optimum_weight across REPORT_FILES and print the results.

    returns:
        (weight_mismatches, reachability_mismatches), see find_mismatches.
    """
    pair_weights_by_report: Dict[str, Dict[Pair, PairEntry]]
    weight_mismatches: List[Mismatch]
    reachability_mismatches: List[Mismatch]

    pair_weights_by_report = {
        Path(path).stem: load_pair_weights(path) for path in REPORT_FILES
    }
    total_pairs = len(
        {pair for pairs in pair_weights_by_report.values() for pair in pairs}
    )

    weight_mismatches, reachability_mismatches = find_mismatches(pair_weights_by_report)

    print(
        f"Checked {total_pairs} distinct platform pairs across {len(REPORT_FILES)} reports."
    )
    print(f"Weight mismatches: {len(weight_mismatches)}")
    print(f"Reachability mismatches: {len(reachability_mismatches)}")

    if weight_mismatches:
        print("\noptimum_weight differs across reports for these pairs:")
        for row in weight_mismatches:
            print(
                f" - {row.source_name} -> {row.target_name}"
                f" ({row.source_id} -> {row.target_id}):"
                f" {format_weight_by_report(row.weight_by_report)}"
            )

    if reachability_mismatches:
        print("\nSome reports found no path (NA) while others did, for these pairs:")
        for row in reachability_mismatches:
            print(
                f" - {row.source_name} -> {row.target_name}"
                f" ({row.source_id} -> {row.target_id}):"
                f" {format_weight_by_report(row.weight_by_report)}"
            )

    return weight_mismatches, reachability_mismatches


if __name__ == "__main__":
    check_missing_files(REPORT_FILES)
    print_file_disclaimer(REPORT_FILES)

    print("Starting optimum_weight cross-report check...")
    weight_mismatches, reachability_mismatches = main()
    if weight_mismatches or reachability_mismatches:
        sys.exit(1)
