"""Dijkstra's algorithm run on the real GTFS weighted graph (weights.txt)."""

from __future__ import annotations
import sys
from contextlib import redirect_stdout
from functools import partial
from pathlib import Path
from time import perf_counter
from typing import Dict, List, Optional, Set

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
    seconds_to_hms,
)
from routing_algorithms.algorithms_utils import (  # noqa: E402
    NodeFmt,
    apply_liceu_entrance_fix,
    build_graph_from_weights,
    print_distances,
    print_graph_size,
    print_header,
    print_path_summary,
    rebuild_path,
    stop_label,
)
from dijkstra_utils import (  # noqa: E402
    Graph,
    Node,
    cut_dijkstra,
    dijkstra,
    print_disclaimer,
    print_summary,
)

SOURCE = "E.50901"
TARGET = "E.55501"


def main() -> None:
    """Run Dijkstra's algorithm on the real GTFS graph for SOURCE and TARGET."""
    graph: Graph
    dist: Dict[Node, int]
    parent: Dict[Node, Optional[Node]]
    iterations: int
    path: List[Node]
    start: float
    elapsed_ms: float
    cut_dist: Dict[Node, int]
    cut_iterations: int
    cut_expanded: Dict[Node, bool]
    cut_start: float
    cut_elapsed_ms: float
    stop_names: Dict[str, str]
    stop_to_lines: Dict[str, List[str]]
    platform_to_entries: Dict[str, Set[str]]
    entrance_to_platform: Dict[str, Set[str]]
    node_fmt: NodeFmt
    _: object

    check_missing_files([WEIGHTS_FILE, STOPS_FILE, PATHWAYS_FILE])
    print_file_disclaimer([WEIGHTS_FILE, STOPS_FILE, PATHWAYS_FILE])

    stop_names = load_stop_names(STOPS_FILE)
    stop_to_lines = build_stop_to_lines(subway_route_names_stop_ids_artificial)
    platform_to_entries, _ = build_graph_and_coverage(load_pathway_ids(PATHWAYS_FILE))
    entrance_to_platform = invert_entries(platform_to_entries)

    # partial() bakes stop_names/stop_to_lines/entrance_to_platform into
    # stop_label as fixed keyword args, turning it into the single-argument
    # NodeFmt every print helper below expects as node_fmt
    node_fmt = partial(
        stop_label,
        stop_names=stop_names,
        stop_to_lines=stop_to_lines,
        entrance_to_platform=entrance_to_platform,
    )

    print_header(SOURCE, TARGET, node_fmt=node_fmt)
    print_disclaimer()

    graph = build_graph_from_weights(WEIGHTS_FILE)
    print_graph_size(graph)

    start = perf_counter()
    dist, parent, iterations, _ = dijkstra(graph, SOURCE, verbose=False)
    elapsed_ms = (perf_counter() - start) * 1000
    path = apply_liceu_entrance_fix(rebuild_path(parent, SOURCE, TARGET), node_fmt)

    cut_start = perf_counter()
    cut_dist, _, cut_iterations, cut_expanded = cut_dijkstra(
        graph, SOURCE, TARGET, verbose=True, node_fmt=node_fmt
    )
    cut_elapsed_ms = (perf_counter() - cut_start) * 1000

    print_distances(
        graph,
        cut_dist,
        show_unreachable=False,
        source=SOURCE,
        dist_fmt=seconds_to_hms,
        label="cut",
        expanded=cut_expanded,
        node_fmt=node_fmt,
    )
    print_path_summary(
        SOURCE, TARGET, path, dist, dist_fmt=seconds_to_hms, node_fmt=node_fmt
    )
    print_summary(iterations, elapsed_ms, cut_iterations, cut_elapsed_ms)


if __name__ == "__main__":
    resources_dir = Path(__file__).resolve().parent / "resources"
    resources_dir.mkdir(exist_ok=True)
    output_path = resources_dir / f"dijkstra_{SOURCE}_to_{TARGET}.txt"
    with output_path.open("w", encoding="utf-8") as file_handle:
        with redirect_stdout(file_handle):
            main()
    print(f"{output_path.name} generated into {output_path.relative_to(_PROJECT_ROOT)}")
