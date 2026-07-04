"""Report, for every directed entrance-to-entrance route, how much a heuristic could help.

Output_name: dijkstra_report.txt saved into 'routing_algorithms/dijkstra/resources'

Written as a standard comma-separated GTFS-style .txt file so it can be converted to
.xlsx by scripts/from_txt_to_xlsx.py.

Columns (in this order):
source_name, target_name, proportion, source_id, target_id, cut_iterations,
path_vertices, optimum_weight, path

- source_name / target_name: labels for source/target given by the same
  node_fmt (stop_names + line + entrance-by-platform) used in dijkstra.py.
- source_id / target_id: their stop_ids.
- path: output of rebuild_path (routing_algorithms/algorithms_utils.py), raw
  stop_ids joined by " -> ". "NA" if no path is found.
- path_vertices: len(path). "NA" if no path is found.
- cut_iterations: number of iterations returned by cut_dijkstra
  (routing_algorithms/dijkstra/dijkstra_utils.py). Always a value (>= 1), even
  when no path is found, since the source itself is always extracted first.
- proportion: path_vertices / cut_iterations. "NA" if no path is found. Always
  <= 1 (see "Aim" below). Rows are ordered ascending by this value, with NA rows last.
- optimum_weight: weight of the path found, in seconds, unformatted. "NA" if
  no path is found.

Aim and objective:
As this graph is pretty small, only a good heuristic can improve Dijkstra. To think
a good heuristic, first we have to analise which situation we have towards us. Instead
of writing a general heuristic, we have to focus on the particular characteristics of
this graph; it should be stressed that this part is the only one not scalable from the
whole pipeline.
The only places where a heuristic can improve Dijkstra is in those routes where we have
considered (extracted) too many vertices compared to the number that finally belong
to the path. That is because the best heuristic is the one that at each vertex returns the
minimal distance until the target. This, obviously, is not an applicable heuristic because if
we knew the shortest path, then we wouldn't need to find any shortest path, it just doesn't
make sense. But this best-case heuristic is useful to understand the difference between
the number of vertices in the path and the number of vertices extracted (VERY IMPORTANT
POINT HERE: what matters to us is the number of vertices expanded, and by Dijkstra's
Convergence Theorem (Alsedà, slide 25) the minimal distance to a vertex is found exactly
once it is extracted, which is equivalent to saying that the number of iterations matches
the number of vertices extracted from the heap (i.e. any vertex is extracted once, and may
be re-added to the heap and later extracted again only if it belongs to a different run).
This best-case heuristic would have the same number of
iterations as vertices in the path. I.e. a proportion near 1 means Dijkstra is being
ultra efficient already, while a low proportion near 0 is where we should focus our
attention to see whether a heuristic could improve Dijkstra there without hurting the
routes that already sit near 1.
Important: we only compute routes from an entrance to an entrance, since that is the
route an actual user takes, and it is how routes are modelled/optimised in Barcelona's
subway network.

Methodology:
1. Build the graph from WEIGHTS_FILE with build_graph_from_weights
   (routing_algorithms/algorithms_utils.py), shared with dijkstra.py.
2. Restrict the graph's vertex set to entries (stop_ids starting with "E.").
3. Build every directed pair (u, v) of distinct entries.
4. Run cut_dijkstra(graph, u, v, verbose=False) for each pair (no changes needed
   in dijkstra_utils.py, cut_dijkstra already supports a silent run), then rebuild_path
   to get the path (or lack of one).
5. Compute the columns above from that pair's (dist, parent, cut_iterations, path).
6. Sort all rows ascending by proportion, NA last, and write them to dijkstra_report.txt.

Note on parallelism: a single cut_dijkstra call on this graph takes well under 1ms
(measured empirically, ~0.7ms), so ~250k directed entry pairs run in a few minutes
single-threaded. Parallelising this one-off analysis script wouldn't be worth the added
complexity, so it is intentionally left sequential.
"""

from __future__ import annotations

import sys
from functools import partial
from pathlib import Path
from time import perf_counter
from typing import Dict, List, NamedTuple, Optional, Set, Tuple

_PROJECT_ROOT = str(Path(__file__).resolve().parents[2])
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from scripts.basics import subway_route_names_stop_ids_artificial  # noqa: E402

from data_validation.gtfs_utils import (  # noqa: E402
    PATHWAYS_FILE,
    STOPS_FILE,
    WEIGHTS_FILE,
    build_graph_and_coverage,
    build_stop_to_lines,
    check_missing_files,
    invert_entries,
    load_pathway_ids,
    load_stop_names,
    print_file_disclaimer,
    write_rows,
)
from routing_algorithms.algorithms_utils import (  # noqa: E402
    Node,
    NodeFmt,
    build_graph_from_weights,
    rebuild_path,
    stop_label,
)
from dijkstra_utils import Graph, cut_dijkstra  # noqa: E402

OUTPUT_NAME = "dijkstra_report.txt"
OUTPUT_PATH = Path(__file__).resolve().parent / "resources" / OUTPUT_NAME
FIELDNAMES = [
    "source_name",
    "target_name",
    "proportion",
    "source_id",
    "target_id",
    "cut_iterations",
    "path_vertices",
    "optimum_weight",
    "path",
]


class ReportRow(NamedTuple):
    """One directed entrance-to-entrance route and its cut_dijkstra outcome."""

    source_id: Node
    target_id: Node
    source_name: str
    target_name: str
    cut_iterations: int
    path_vertices: Optional[int]
    optimum_weight: Optional[int]
    proportion: Optional[float]
    path: List[Node]


def collect_entry_pairs(graph: Graph) -> List[Tuple[Node, Node]]:
    """Return every directed pair of distinct entrance vertices in the graph.

    args:
        graph: A directed, weighted graph (build_graph_from_weights output),
            keyed by every stop_id, including entries (stop_ids starting with "E.").

    returns:
        Sorted list of (source, target) pairs with source != target, both entries.
    """
    entries = sorted(node for node in graph if node.startswith("E."))
    return [
        (source, target) for source in entries for target in entries if source != target
    ]


def compute_report_row(
    graph: Graph, source: Node, target: Node, node_fmt: NodeFmt
) -> ReportRow:
    """Run cut_dijkstra for one entrance pair and compute this report's columns.

    args:
        graph: A directed, weighted graph.
        source: Entrance stop_id to start from.
        target: Entrance stop_id to reach.
        node_fmt: Callable to label a node (stop name and line), as in dijkstra.py.

    returns:
        The ReportRow for this (source, target) pair.
    """
    dist, parent, cut_iterations, _ = cut_dijkstra(graph, source, target, verbose=False)
    path = rebuild_path(parent, source, target)

    path_vertices: Optional[int] = None
    optimum_weight: Optional[int] = None
    proportion: Optional[float] = None
    if path:
        path_vertices = len(path)
        optimum_weight = dist[target]
        proportion = path_vertices / cut_iterations

    return ReportRow(
        source_id=source,
        target_id=target,
        source_name=node_fmt(source),
        target_name=node_fmt(target),
        cut_iterations=cut_iterations,
        path_vertices=path_vertices,
        optimum_weight=optimum_weight,
        proportion=proportion,
        path=path,
    )


def _na_or(value: object, fmt: str = "{}") -> str:
    """Return "NA" for a None value, otherwise the formatted value.

    args:
        value: The value to format, or None.
        fmt: A str.format template applied to value when it is not None.

    returns:
        "NA" if value is None, otherwise fmt.format(value).
    """
    return "NA" if value is None else fmt.format(value)


def row_to_csv_dict(row: ReportRow) -> Dict[str, str]:
    """Convert one ReportRow into the string dict write_rows expects.

    args:
        row: A single report row.

    returns:
        Dict keyed by FIELDNAMES, "NA" standing in for every missing value.
    """
    path_str = "NA" if not row.path else " -> ".join(row.path)
    return {
        "source_name": row.source_name,
        "target_name": row.target_name,
        "proportion": _na_or(row.proportion, "{:.5f}"),
        "source_id": row.source_id,
        "target_id": row.target_id,
        "cut_iterations": str(row.cut_iterations),
        "path_vertices": _na_or(row.path_vertices),
        "optimum_weight": _na_or(row.optimum_weight),
        "path": path_str,
    }


def main() -> Tuple[List[ReportRow], float]:
    """Compute the entrance-to-entrance dijkstra report and write it to OUTPUT_NAME.

    returns:
        The sorted report rows, and the total elapsed time (seconds) spent
        running cut_dijkstra over every entry pair.
    """
    graph: Graph
    stop_names: Dict[str, str]
    stop_to_lines: Dict[str, List[str]]
    entrance_to_platform: Dict[str, Set[str]]
    pairs: List[Tuple[Node, Node]]
    rows: List[ReportRow]
    elapsed: float

    stop_names = load_stop_names(STOPS_FILE)
    stop_to_lines = build_stop_to_lines(subway_route_names_stop_ids_artificial)
    platform_to_entries, _ = build_graph_and_coverage(load_pathway_ids(PATHWAYS_FILE))
    entrance_to_platform = invert_entries(platform_to_entries)
    node_fmt = partial(
        stop_label,
        stop_names=stop_names,
        stop_to_lines=stop_to_lines,
        entrance_to_platform=entrance_to_platform,
    )

    graph = build_graph_from_weights(WEIGHTS_FILE)
    pairs = collect_entry_pairs(graph)

    start = perf_counter()
    rows = [
        compute_report_row(graph, source, target, node_fmt) for source, target in pairs
    ]
    elapsed = perf_counter() - start

    # NA-proportion rows (no path) sort after every real value; INF is only used
    # as the sort key here, never stored, so it never leaks into the report.
    rows.sort(
        key=lambda row: row.proportion if row.proportion is not None else float("inf")
    )

    write_rows(OUTPUT_PATH, FIELDNAMES, (row_to_csv_dict(row) for row in rows))
    return rows, elapsed


if __name__ == "__main__":
    check_missing_files([WEIGHTS_FILE, STOPS_FILE, PATHWAYS_FILE])
    print_file_disclaimer([WEIGHTS_FILE, STOPS_FILE, PATHWAYS_FILE])

    print(f"Starting {OUTPUT_NAME} generation...")
    report_rows, elapsed_seconds = main()
    print(
        f"{OUTPUT_PATH.name} generated into"
        f" {OUTPUT_PATH.relative_to(_PROJECT_ROOT)} with {len(report_rows)} rows"
        f" (took {elapsed_seconds:.1f}s)"
    )
