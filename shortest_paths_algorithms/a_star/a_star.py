"""A* algorithm run on the real GTFS weighted graph (weights.txt), using a
geographic straight-line-distance heuristic.

Output_name: a_star_{GRAPH_MODE_LABEL}_{HEURISTIC_NAME}_{SOURCE}_to_{TARGET}.txt
saved into 'shortest_paths_algorithms/a_star/resources'

Aim:
shortest_paths_algorithms/a_star/a_star_utils.py implements A* generically, taking any
admissible heuristic h(node, target) as a parameter; the concrete heuristics
(h_geo, h_cheat, h_bcn) are built in shortest_paths_algorithms/a_star/heuristics/,
one module each; see their docstrings for their definitions. This script only
wires that machinery to the real subway graph: the graph itself (via
build_graph_from_weights, shared with dijkstra.py), the real stop coordinates,
and SOURCE/TARGET.

Methodology:
1. Build the real graph from WEIGHTS_FILE via build_graph_from_weights
   (shortest_paths_algorithms/algorithms_utils.py), shared with dijkstra.py.
2. Load every stop's (lat, lon) and compute v_max via load_node_coords and
   compute_v_max (shortest_paths_algorithms/a_star/heuristics/h_geo.py).
3. Build h via build_h_geo, build_h_cheat, or build_h_bcn, picked by
   HEURISTIC_NAME (shortest_paths_algorithms/a_star/heuristics/).
4. Run a_star(graph, SOURCE, TARGET, h) and print the reconstructed path and
   its weight, the same way dijkstra.py reports cut_dijkstra's result.

Note: unlike dijkstra.py, there is no "full" run to print a whole distances
table from (a_star_utils.py's a_star always stops as soon as the target is
extracted, same as cut_dijkstra; see its own docstring), so only
dist[TARGET] is guaranteed optimal here (by the convergence theorem); this
script reports that value and the path, not a full per-node distances table.
"""

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
    best_over_candidate_pairs,
    build_entrance_platform_lookups,
    build_graph_from_weights,
    finalize_path,
    print_graph_size,
    print_header,
    print_path_summary,
    report_missing_platform_candidates,
    resolve_search_endpoints,
    stop_label,
    with_adjusted_target_weight,
)
from shortest_paths_algorithms.config import (  # noqa: E402
    GRAPH_MODE,
    HEURISTIC_NAME,
    SOURCE,
    TARGET,
)
from a_star_utils import (  # noqa: E402
    H_BCN,
    H_CHEAT,
    H_GEO,
    Graph,
    Heuristic,
    Node,
    a_star,
)
from heuristics.h_geo import (  # noqa: E402
    Coord,
    build_h_geo,
    compute_v_max,
    load_node_coords,
)
from heuristics.h_cheat import build_h_cheat  # noqa: E402
from heuristics.h_bcn import DepthTable, build_depth_tables, build_h_bcn  # noqa: E402


def main() -> None:
    """Run A* on the real GTFS graph for SOURCE and TARGET and display the result."""
    graph: Graph
    coords: Dict[Node, Coord]
    v_max: float
    v_max_from: Node
    v_max_to: Node
    h: Heuristic
    g: Dict[Node, int]
    parent: Dict[Node, Optional[Node]]
    iterations: int
    path: List[Node]
    start: float
    elapsed_ms: float
    stop_names: Dict[str, str]
    stop_to_lines: Dict[str, List[str]]
    entrance_to_platform: Dict[str, Set[str]]
    entrance_plat_to: EntranceToPlatforms
    entrance_plat_from: EntranceToPlatforms
    depth_from: DepthTable
    depth_to: DepthTable
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

    node_fmt = partial(
        stop_label,
        stop_names=stop_names,
        stop_to_lines=stop_to_lines,
        entrance_to_platform=entrance_to_platform,
    )

    print_header(SOURCE, TARGET, graph_mode=GRAPH_MODE, node_fmt=node_fmt)

    graph = build_graph_from_weights(WEIGHTS_FILE, GRAPH_MODE)
    print_graph_size(graph)

    if HEURISTIC_NAME == H_CHEAT:
        # h_cheat only needs graph: coords/v_max are geography-only inputs
        # h_geo/h_bcn need, so skip computing them entirely for this heuristic.
        h = build_h_cheat(graph)
    else:
        coords = load_node_coords(STOPS_FILE)
        v_max, (v_max_from, v_max_to) = compute_v_max(graph, coords)
        print(
            f"v_max (fastest implied edge speed): {v_max:.3f} m/s ({v_max * 3.6:.1f} km/h)"
            f", found at edge {v_max_from} ({node_fmt(v_max_from)})"
            f" -> {v_max_to} ({node_fmt(v_max_to)})"
        )
        if HEURISTIC_NAME == H_GEO:
            h = build_h_geo(coords, v_max)
        elif HEURISTIC_NAME == H_BCN:
            depth_from, depth_to = build_depth_tables(graph)
            h = build_h_bcn(WEIGHTS_FILE, coords, v_max, depth_from, depth_to)
        else:
            raise ValueError(f"Unknown HEURISTIC_NAME: {HEURISTIC_NAME!r}")

    source_platforms, target_platforms, entry_total = resolve_search_endpoints(
        GRAPH_MODE, SOURCE, TARGET, entrance_plat_from, entrance_plat_to
    )
    if report_missing_platform_candidates(
        source_platforms, target_platforms, SOURCE, TARGET
    ):
        return

    start = perf_counter()
    algo_source, algo_target, g, parent, iterations, _ = best_over_candidate_pairs(
        graph,
        source_platforms,
        target_platforms,
        partial(a_star, h=h, verbose=True, node_fmt=node_fmt),
    )
    elapsed_ms = (perf_counter() - start) * 1000
    best_weight = g[algo_target]

    path = finalize_path(
        GRAPH_MODE, parent, algo_source, algo_target, SOURCE, TARGET, node_fmt
    )

    print_path_summary(
        SOURCE,
        TARGET,
        path,
        with_adjusted_target_weight(g, TARGET, best_weight, entry_total),
        dist_fmt=seconds_to_hms,
        node_fmt=node_fmt,
    )
    print(f"\nIterations needed: {iterations}")
    print(f"Elapsed time: {elapsed_ms:.3f} ms")


if __name__ == "__main__":
    resources_dir = Path(__file__).resolve().parent / "resources"
    resources_dir.mkdir(exist_ok=True)
    output_path = (
        resources_dir
        / f"a_star_{GRAPH_MODE_LABEL[GRAPH_MODE]}_{HEURISTIC_NAME}_{SOURCE}_to_{TARGET}.txt"
    )
    with output_path.open("w", encoding="utf-8") as file_handle:
        with redirect_stdout(file_handle):
            main()
    print(f"{output_path.name} generated into {output_path.relative_to(_PROJECT_ROOT)}")
