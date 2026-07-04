"""Dijkstra's algorithm run on the real GTFS weighted graph (weights.txt)."""

from __future__ import annotations
import sys
from contextlib import redirect_stdout
from pathlib import Path
from time import perf_counter
from typing import Dict, List, Optional

_PROJECT_ROOT = str(Path(__file__).resolve().parents[2])
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from data_validation.gtfs_utils import (  # noqa: E402
    WEIGHTS_FILE,
    check_missing_files,
    read_dict_rows,
    seconds_to_hms,
)
from routing_algorithms.algorithms_utils import (  # noqa: E402
    print_distances,
    print_graph_size,
    print_path_summary,
    rebuild_path,
)
from dijkstra_utils import (  # noqa: E402
    Graph,
    Node,
    cut_dijkstra,
    dijkstra,
    print_disclaimer,
    print_summary,
)

SOURCE = "E.12001"
TARGET = "1.120"


def build_graph_from_weights(file_path: str) -> Graph:
    """Build a directed, weighted graph from a GTFS-style weights file.

    args:
        file_path: Path to a CSV with from_stop_id, to_stop_id, weight_seconds columns.

    returns:
        A graph represented as an adjacency list with weights, including
        sink-only nodes (no outgoing edges) so every stop_id is a key.
    """
    graph: Graph = {}
    for row in read_dict_rows(file_path):
        from_stop_id = row["from_stop_id"]
        to_stop_id = row["to_stop_id"]
        weight = int(row["weight_seconds"])
        graph.setdefault(from_stop_id, {})[to_stop_id] = weight
        graph.setdefault(to_stop_id, {})
    return graph


def main() -> None:
    """Run Dijkstra's algorithm on the real GTFS graph for SOURCE and TARGET."""
    graph: Graph
    dist: Dict[Node, int]
    parent: Dict[Node, Optional[Node]]
    iterations: int
    path: List[Node]
    start: float
    elapsed_ms: float
    cut_start: float
    cut_iterations: int
    cut_elapsed_ms: float
    _: object

    print_disclaimer()
    check_missing_files([WEIGHTS_FILE])

    graph = build_graph_from_weights(WEIGHTS_FILE)
    print_graph_size(graph)

    start = perf_counter()
    dist, parent, iterations = dijkstra(graph, SOURCE, verbose=True)
    elapsed_ms = (perf_counter() - start) * 1000
    path = rebuild_path(parent, SOURCE, TARGET)

    cut_start = perf_counter()
    _, _, cut_iterations = cut_dijkstra(graph, SOURCE, TARGET, verbose=False)
    cut_elapsed_ms = (perf_counter() - cut_start) * 1000

    print_distances(
        graph, dist, show_unreachable=False, source=SOURCE, dist_fmt=seconds_to_hms
    )
    print_path_summary(SOURCE, TARGET, path, dist, dist_fmt=seconds_to_hms)
    print_summary(iterations, elapsed_ms, cut_iterations, cut_elapsed_ms)


if __name__ == "__main__":
    resources_dir = Path(__file__).resolve().parent / "resources"
    resources_dir.mkdir(exist_ok=True)
    output_path = resources_dir / f"dijkstra_{SOURCE}_to_{TARGET}.txt"
    with output_path.open("w", encoding="utf-8") as file_handle:
        with redirect_stdout(file_handle):
            main()
    print(f"{output_path.name} generated into {output_path.relative_to(_PROJECT_ROOT)}")
