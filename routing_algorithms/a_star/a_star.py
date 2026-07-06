"""A* algorithm run on the real GTFS weighted graph (weights.txt), using a
geographic straight-line-distance heuristic.

Output_name: a_star_{HEURISTIC_NAME}_{SOURCE}_to_{TARGET}.txt saved into
'routing_algorithms/a_star/resources'

Aim:
routing_algorithms/a_star/a_star_utils.py implements A* generically, taking any
admissible heuristic h(node, target) as a parameter, and also builds the
concrete geographic heuristic used here (straight_line_distance, v_max,
build_h_geo -- see that module's docstrings for their definitions and the
admissibility proof). This script only wires that machinery to the real
subway graph: the graph itself (via build_graph_from_weights, shared with
dijkstra.py), the real stop coordinates, and SOURCE/TARGET.

Methodology:
1. Build the real graph from WEIGHTS_FILE via build_graph_from_weights
   (routing_algorithms/algorithms_utils.py), shared with dijkstra.py.
2. Load every stop's (lat, lon) and compute v_max via load_node_coords and
   compute_v_max (routing_algorithms/a_star/a_star_utils.py).
3. Build h via build_h_geo (routing_algorithms/a_star/a_star_utils.py).
4. Run a_star(graph, SOURCE, TARGET, h) and print the reconstructed path and
   its weight, the same way dijkstra.py reports cut_dijkstra's result.

Note: unlike dijkstra.py, there is no "full" run to print a whole distances
table from (a_star_utils.py's a_star always stops as soon as the target is
extracted, same as cut_dijkstra -- see its own docstring), so only
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
    print_graph_size,
    print_header,
    print_path_summary,
    rebuild_path,
    stop_label,
)
from a_star_utils import (  # noqa: E402
    Coord,
    Graph,
    Heuristic,
    Node,
    a_star,
    build_h_cheat,
    build_h_geo,
    compute_v_max,
    load_node_coords,
)

SOURCE = "E.11101"
TARGET = "E.14001"
HEURISTIC_NAME = "h_cheat"  # "h_geo" or "h_cheat" to pick the heuristic built in main()


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

    node_fmt = partial(
        stop_label,
        stop_names=stop_names,
        stop_to_lines=stop_to_lines,
        entrance_to_platform=entrance_to_platform,
    )

    print_header(SOURCE, TARGET, node_fmt=node_fmt)

    graph = build_graph_from_weights(WEIGHTS_FILE)
    print_graph_size(graph)

    coords = load_node_coords(STOPS_FILE)
    v_max, (v_max_from, v_max_to) = compute_v_max(graph, coords)
    print(
        f"v_max (fastest implied edge speed): {v_max:.3f} m/s ({v_max * 3.6:.1f} km/h)"
        f" -- found at edge {v_max_from} ({node_fmt(v_max_from)})"
        f" -> {v_max_to} ({node_fmt(v_max_to)})"
    )
    if HEURISTIC_NAME == "h_geo":
        h = build_h_geo(coords, v_max)
    elif HEURISTIC_NAME == "h_cheat":
        h = build_h_cheat(graph)
    else:
        raise ValueError(f"Unknown HEURISTIC_NAME: {HEURISTIC_NAME!r}")

    start = perf_counter()
    g, parent, iterations = a_star(graph, SOURCE, TARGET, h, verbose=True)
    elapsed_ms = (perf_counter() - start) * 1000
    path = apply_liceu_entrance_fix(rebuild_path(parent, SOURCE, TARGET), node_fmt)

    print_path_summary(
        SOURCE, TARGET, path, g, dist_fmt=seconds_to_hms, node_fmt=node_fmt
    )
    print(f"\nIterations needed: {iterations}")
    print(f"Elapsed time: {elapsed_ms:.3f} ms")


if __name__ == "__main__":
    resources_dir = Path(__file__).resolve().parent / "resources"
    resources_dir.mkdir(exist_ok=True)
    output_path = resources_dir / f"a_star_{HEURISTIC_NAME}_{SOURCE}_to_{TARGET}.txt"
    with output_path.open("w", encoding="utf-8") as file_handle:
        with redirect_stdout(file_handle):
            main()
    print(f"{output_path.name} generated into {output_path.relative_to(_PROJECT_ROOT)}")
