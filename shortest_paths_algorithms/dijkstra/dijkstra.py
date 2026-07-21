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

from subway_reference.subway_lines import (  # noqa: E402
    subway_route_names_stop_ids_artificial,
)

from data_validation.gtfs_utils import (  # noqa: E402
    STOPS_FILE,
    WEIGHTS_FILE,
    build_stop_to_lines,
    check_missing_files,
    load_stop_names,
    print_file_disclaimer,
    seconds_to_hms,
)
from shortest_paths_algorithms.algorithms_utils import (  # noqa: E402
    GRAPH_MODE_LABEL,
    EntranceToPlatforms,
    NodeFmt,
    build_entrance_platform_lookups,
    build_graph_from_weights,
    finalize_path,
    print_distances,
    print_graph_size,
    print_header,
    print_path_summary,
    report_missing_platform_candidates,
    resolve_search_endpoints,
    stop_label,
    with_adjusted_target_weight,
)
from shortest_paths_algorithms.config import GRAPH_MODE, SOURCE, TARGET  # noqa: E402
from dijkstra_utils import (  # noqa: E402
    Graph,
    Node,
    best_over_source_candidates,
    cut_dijkstra,
    print_disclaimer,
    print_summary,
)


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
    entrance_to_platform: Dict[str, Set[str]]
    entrance_plat_to: EntranceToPlatforms
    entrance_plat_from: EntranceToPlatforms
    node_fmt: NodeFmt
    source_platforms: Set[Node]
    target_platforms: Set[Node]
    entry_total: int
    algo_source: Node
    algo_target: Node
    best_weight: int
    _: object

    check_missing_files([WEIGHTS_FILE, STOPS_FILE])
    print_file_disclaimer([WEIGHTS_FILE, STOPS_FILE])

    stop_names = load_stop_names(STOPS_FILE)
    stop_to_lines = build_stop_to_lines(subway_route_names_stop_ids_artificial)
    entrance_to_platform, entrance_plat_to, entrance_plat_from = (
        build_entrance_platform_lookups(WEIGHTS_FILE)
    )

    # partial() bakes stop_names/stop_to_lines/entrance_to_platform into
    # stop_label as fixed keyword args, turning it into the single-argument
    # NodeFmt every print helper below expects as node_fmt
    node_fmt = partial(
        stop_label,
        stop_names=stop_names,
        stop_to_lines=stop_to_lines,
        entrance_to_platform=entrance_to_platform,
    )

    print_header(SOURCE, TARGET, graph_mode=GRAPH_MODE, node_fmt=node_fmt)
    print_disclaimer()

    graph = build_graph_from_weights(WEIGHTS_FILE, GRAPH_MODE)
    print_graph_size(graph)

    source_platforms, target_platforms, entry_total = resolve_search_endpoints(
        GRAPH_MODE, SOURCE, TARGET, entrance_plat_from, entrance_plat_to
    )
    if report_missing_platform_candidates(
        source_platforms, target_platforms, SOURCE, TARGET
    ):
        return

    start = perf_counter()
    algo_source, algo_target, dist, parent, iterations = best_over_source_candidates(
        graph, source_platforms, target_platforms
    )
    elapsed_ms = (perf_counter() - start) * 1000
    best_weight = dist[algo_target]

    path = finalize_path(
        GRAPH_MODE, parent, algo_source, algo_target, SOURCE, TARGET, node_fmt
    )

    cut_start = perf_counter()
    cut_dist, _, cut_iterations, cut_expanded = cut_dijkstra(
        graph, algo_source, algo_target, verbose=True, node_fmt=node_fmt
    )
    cut_elapsed_ms = (perf_counter() - cut_start) * 1000

    print_distances(
        graph,
        cut_dist,
        show_unreachable=False,
        source=algo_source,
        dist_fmt=seconds_to_hms,
        label="cut",
        expanded=cut_expanded,
        node_fmt=node_fmt,
    )
    print_path_summary(
        SOURCE,
        TARGET,
        path,
        with_adjusted_target_weight(dist, TARGET, best_weight, entry_total),
        dist_fmt=seconds_to_hms,
        node_fmt=node_fmt,
    )
    print_summary(iterations, elapsed_ms, cut_iterations, cut_elapsed_ms)


if __name__ == "__main__":
    resources_dir = Path(__file__).resolve().parent / "resources"
    resources_dir.mkdir(exist_ok=True)
    output_path = (
        resources_dir
        / f"dijkstra_{GRAPH_MODE_LABEL[GRAPH_MODE]}_{SOURCE}_to_{TARGET}.txt"
    )
    with output_path.open("w", encoding="utf-8") as file_handle:
        with redirect_stdout(file_handle):
            main()
    print(f"{output_path.name} generated into {output_path.relative_to(_PROJECT_ROOT)}")
