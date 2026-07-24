"""Platform-to-platform report helpers shared by dijkstra_report.txt and
a_star_geo_report.txt (shortest_paths_algorithms/reports/): cut_dijkstra and a_star both
stop as soon as target is extracted, so both fit the same row shape via the
ReportRunner they're wrapped into, and both reports are built, sorted, and
written to CSV the same way via run_platform_pair_report.
"""

from __future__ import annotations
import statistics
from pathlib import Path
from time import perf_counter
from typing import Callable, Dict, List, NamedTuple, Optional, Tuple

from data_validation.gtfs_utils import write_rows
from shortest_paths_algorithms.algorithms_utils import (
    Graph,
    Node,
    NodeFmt,
    rebuild_path,
)


def na_or(value: object, fmt: str = "{}") -> str:
    """Return "NA" for a None value, otherwise the formatted value.

    args:
        value: The value to format, or None.
        fmt: A str.format template applied to value when it is not None.

    returns:
        "NA" if value is None, otherwise fmt.format(value).
    """
    return "NA" if value is None else fmt.format(value)


def collect_platform_pairs(graph: Graph) -> List[Tuple[Node, Node]]:
    """Return every directed pair of distinct platform vertices in the graph.

    args:
        graph: A directed, weighted graph (build_graph_from_weights output),
            keyed by every stop_id, including platforms (stop_ids starting with "1.").

    returns:
        Sorted list of (source, target) pairs with source != target, both platforms.
    """
    platforms = sorted(node for node in graph if node.startswith("1."))
    return [
        (source, target)
        for source in platforms
        for target in platforms
        if source != target
    ]


class ReportRow(NamedTuple):
    """One directed platform-to-platform route and its shortest-path outcome.

    Shared row shape for dijkstra_report.txt (cut_dijkstra) and
    a_star_geo_report.txt (a_star): iterations means cut_iterations for the
    former and a_star_iterations for the latter; report_fieldnames and
    report_row_to_csv_dict take the actual column name as a parameter so
    each report's output file still shows its own algorithm-specific label.
    """

    source_id: Node
    target_id: Node
    source_name: str
    target_name: str
    iterations: int
    path_vertices: Optional[int]
    optimum_weight: Optional[int]
    proportion: Optional[float]
    path: List[Node]


# Runs one search from source to target, returning (dist, parent, iterations):
# a thin wrapper around cut_dijkstra (dropping its 4th, `expanded` value) or
# around a_star (with its heuristic already bound), so compute_report_row
# doesn't need to know which algorithm it's calling.
ReportRunner = Callable[
    [Graph, Node, Node], Tuple[Dict[Node, int], Dict[Node, Optional[Node]], int]
]


def compute_report_row(
    graph: Graph, source: Node, target: Node, node_fmt: NodeFmt, runner: ReportRunner
) -> ReportRow:
    """Run a shortest-path search for one platform pair and build its ReportRow.

    args:
        graph: A directed, weighted graph.
        source: Platform stop_id to start from.
        target: Platform stop_id to reach.
        node_fmt: Callable to label a node (stop name and line).
        runner: Callable running one search from source to target, see
            ReportRunner above.

    returns:
        The ReportRow for this (source, target) pair.
    """
    dist, parent, iterations = runner(graph, source, target)
    path = rebuild_path(parent, source, target)

    path_vertices: Optional[int] = None
    optimum_weight: Optional[int] = None
    proportion: Optional[float] = None
    if path:
        path_vertices = len(path)
        optimum_weight = dist[target]
        proportion = path_vertices / iterations

    return ReportRow(
        source_id=source,
        target_id=target,
        source_name=node_fmt(source),
        target_name=node_fmt(target),
        iterations=iterations,
        path_vertices=path_vertices,
        optimum_weight=optimum_weight,
        proportion=proportion,
        path=path,
    )


def report_fieldnames(iterations_label: str) -> List[str]:
    """Return a report's CSV column order, naming the iterations column.

    args:
        iterations_label: Column name for the iterations count, e.g.
            "cut_iterations" or "a_star_iterations".

    returns:
        Column names for write_rows, in report column order.
    """
    return [
        "source_name",
        "target_name",
        "proportion",
        "source_id",
        "target_id",
        iterations_label,
        "path_vertices",
        "optimum_weight",
        "path",
    ]


def report_row_to_csv_dict(row: ReportRow, iterations_label: str) -> Dict[str, str]:
    """Convert one ReportRow into the string dict write_rows expects.

    args:
        row: A single report row.
        iterations_label: Column name for row.iterations, e.g.
            "cut_iterations" or "a_star_iterations" (must match the label
            passed to report_fieldnames for the same report).

    returns:
        Dict keyed by report_fieldnames(iterations_label), "NA" standing in
        for every missing value.
    """
    path_str = "NA" if not row.path else " -> ".join(row.path)
    return {
        "source_name": row.source_name,
        "target_name": row.target_name,
        "proportion": na_or(row.proportion, "{:.5f}"),
        "source_id": row.source_id,
        "target_id": row.target_id,
        iterations_label: str(row.iterations),
        "path_vertices": na_or(row.path_vertices),
        "optimum_weight": na_or(row.optimum_weight),
        "path": path_str,
    }


def run_platform_pair_report(
    graph: Graph,
    pairs: List[Tuple[Node, Node]],
    node_fmt: NodeFmt,
    runner: ReportRunner,
    output_path: Path,
    fieldnames: List[str],
    iterations_label: str,
) -> Tuple[List[ReportRow], float]:
    """Run runner over every pair, sort by proportion, print stats, and write the CSV.

    Shared tail end of dijkstra_report.txt's and a_star_geo_report.txt's main():
    everything past "build the runner" (timing the pairs loop, sorting,
    printing proportion mean/median, and writing the file) is identical
    between the two reports, so it lives here instead of being duplicated in
    shortest_paths_algorithms/reports/dijkstra_report.py and
    shortest_paths_algorithms/reports/a_star_report.py.

    args:
        graph: A directed, weighted graph.
        pairs: Every (source, target) platform pair to report on, from
            collect_platform_pairs.
        node_fmt: Callable to label a node (stop name and line).
        runner: Callable running one search from source to target, see
            ReportRunner above.
        output_path: Where to write the resulting CSV-style .txt file.
        fieldnames: Column order for the CSV, from report_fieldnames.
        iterations_label: Column name for each row's iterations count, e.g.
            "cut_iterations" or "a_star_iterations".

    returns:
        The sorted report rows, and the total elapsed time (seconds) spent
        running runner over every pair.
    """
    start: float
    rows: List[ReportRow]
    elapsed: float
    proportions: List[float]

    start = perf_counter()
    rows = [
        compute_report_row(graph, source, target, node_fmt, runner)
        for source, target in pairs
    ]
    elapsed = perf_counter() - start

    # NA-proportion rows (no path) sort after every real value; INF is only used
    # as the sort key here, never stored, so it never leaks into the report.
    rows.sort(
        key=lambda row: row.proportion if row.proportion is not None else float("inf")
    )

    proportions = [row.proportion for row in rows if row.proportion is not None]
    print(f"proportion mean: {statistics.mean(proportions):.5f}")
    print(f"proportion median: {statistics.median(proportions):.5f}")

    write_rows(
        output_path,
        fieldnames,
        (report_row_to_csv_dict(row, iterations_label) for row in rows),
    )
    return rows, elapsed
