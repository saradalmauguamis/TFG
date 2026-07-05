"""A* algorithm run on the real GTFS weighted graph (weights.txt), using a
geographic straight-line-distance heuristic.

Output_name: a_star_{SOURCE}_to_{TARGET}.txt saved into 'routing_algorithms/a_star/resources'

Aim:
routing_algorithms/a_star/a_star_utils.py implements A* generically, taking any
admissible heuristic h(node, target) as a parameter. This script supplies both
pieces needed to run it against the real subway graph: the graph itself (via
build_graph_from_weights, shared with dijkstra.py) and a concrete geographic
heuristic built from each stop's (lat, lon).

Heuristic definition:
h(node, target) = straight_line_distance(node, target) / v_max, where v_max is
the fastest implied speed (in m/s) across any single edge already present in
the graph: v_max = max over every edge (u, v) in WEIGHTS_FILE of
straight_line_distance(u, v) / weight_seconds(u, v).

Why this is admissible: for any real path v0 -> ... -> vk with total weight
T = sum(w_i), each edge on it satisfies straight_line_distance(v_i, v_i+1) <=
v_max * w_i (v_max is by definition the max of that ratio over every graph
edge, including these). Summing over the path and applying the triangle
inequality (straight_line_distance(node, target) <= sum of
straight_line_distance(v_i, v_i+1)) gives
straight_line_distance(node, target) <= v_max * T for any path, in particular
the optimal one, so h(node, target) <= T always: h never overestimates the
true remaining cost, whichever path turns out to be optimal.

straight_line_distance treats the small Barcelona area as locally flat
(equirectangular projection: longitude scaled by cos(mean latitude) before
applying Pythagoras, then converted from degrees to meters), rather than raw
Euclidean distance on unscaled (lat, lon) degrees. This still fits the "assume
the earth is flat" brief, and both versions are equally admissible by the
proof above (it only requires computing v_max and h with the exact same
distance function) -- the reason to prefer the corrected one is that it makes
v_max physically interpretable (printed in km/h below) and gives a tighter,
more informative heuristic, since raw degrees mis-weight east-west vs
north-south travel at this latitude (1 degree of longitude is only ~75% the
length of 1 degree of latitude here).

Methodology:
1. Build the real graph from WEIGHTS_FILE via build_graph_from_weights
   (routing_algorithms/algorithms_utils.py), shared with dijkstra.py.
2. Load every stop's (lat, lon) via load_stops_info (data_validation/gtfs_utils.py).
3. Compute v_max by scanning every edge already present in the graph.
4. Build h as a closure over the coordinates and v_max, floored to an int (a
   floor can only shrink h, so it cannot break admissibility) to match
   a_star_utils.py's Heuristic = Callable[[Node, Node], int] contract.
5. Run a_star(graph, SOURCE, TARGET, h) and print the reconstructed path and
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
from math import cos, radians, sqrt
from pathlib import Path
from time import perf_counter
from typing import Dict, List, Optional, Set, Tuple

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
    load_stops_info,
    print_file_disclaimer,
    seconds_to_hms,
)
from routing_algorithms.algorithms_utils import (  # noqa: E402
    NodeFmt,
    build_graph_from_weights,
    print_graph_size,
    print_header,
    print_path_summary,
    rebuild_path,
    stop_label,
)
from a_star_utils import Graph, Heuristic, Node, a_star  # noqa: E402

SOURCE = "E.50901"
TARGET = "E.55501"

EARTH_RADIUS_M = 6_371_000.0  # mean Earth radius, used for the flat local projection
Coord = Tuple[float, float]  # (stop_lat, stop_lon) in degrees


def straight_line_distance(coord_a: Coord, coord_b: Coord) -> float:
    """Return the flat-earth straight-line distance between two points, in meters.

    Treats the (small) area covered by the graph as locally flat: longitude is
    scaled by cos(mean latitude) before applying Pythagoras, so that degrees
    of longitude and latitude are weighted by their actual physical length at
    this latitude, then the result is converted from degrees to meters.

    args:
        coord_a: (stop_lat, stop_lon) in degrees for the first point.
        coord_b: (stop_lat, stop_lon) in degrees for the second point.

    returns:
        The estimated straight-line distance between the two points, in meters.
    """
    lat_a, lon_a = coord_a
    lat_b, lon_b = coord_b
    mean_lat_rad = radians((lat_a + lat_b) / 2)

    dx = radians(lon_b - lon_a) * cos(mean_lat_rad) * EARTH_RADIUS_M
    dy = radians(lat_b - lat_a) * EARTH_RADIUS_M
    return sqrt(dx * dx + dy * dy)


def load_node_coords(file_path: str) -> Dict[Node, Coord]:
    """Return stop_id -> (stop_lat, stop_lon) in degrees, for every stop in file_path.

    args:
        file_path: Path to a GTFS-style stops file (STOPS_FILE).

    returns:
        Mapping from stop_id to its (lat, lon) coordinates, built on top of
        load_stops_info (data_validation/gtfs_utils.py).
    """
    return {
        stop_id: (float(lat), float(lon))
        for stop_id, (_, lat, lon) in load_stops_info(file_path).items()
    }


def compute_v_max(
    graph: Graph, coords: Dict[Node, Coord]
) -> Tuple[float, Tuple[Node, Node]]:
    """Return the fastest implied speed (m/s) across any single edge in graph.

    Scans every directed edge already in the graph (built from WEIGHTS_FILE)
    and takes the maximum of straight_line_distance(u, v) / weight(u, v),
    the ratio a_star's admissibility proof (module docstring) relies on.

    args:
        graph: A directed, weighted graph, as returned by build_graph_from_weights.
        coords: Mapping from every node in graph to its (lat, lon) coordinates.

    returns:
        The maximum straight-line-distance-per-second observed across all
        edges, together with the (u, v) edge that achieves it.
    """
    # max() over (ratio, (u, v)) tuples compares lexicographically by ratio
    # first, so it returns the whole winning tuple, not just the ratio.
    return max(
        (straight_line_distance(coords[u], coords[v]) / weight, (u, v))
        for u, adjacency in graph.items()
        for v, weight in adjacency.items()
    )


def heuristic(node: Node, target: Node, coords: Dict[Node, Coord], v_max: float) -> int:
    """Return the admissible heuristic estimate from node to target.

    h(node, target) = straight_line_distance(node, target) / v_max, floored to
    an int to match a_star_utils.py's Heuristic = Callable[[Node, Node], int]
    (flooring can only shrink h, so admissibility is preserved).

    args:
        node: The node to estimate the remaining cost from.
        target: The target node.
        coords: Mapping from node to its (lat, lon) coordinates.
        v_max: Fastest implied speed (m/s) across any edge, from compute_v_max.

    returns:
        straight_line_distance(node, target) / v_max, floored to an int.
    """
    return int(straight_line_distance(coords[node], coords[target]) / v_max)


def build_heuristic(coords: Dict[Node, Coord], v_max: float) -> Heuristic:
    """Bind coords and v_max into heuristic, producing a plain Heuristic(node, target).

    args:
        coords: Mapping from node to its (lat, lon) coordinates.
        v_max: Fastest implied speed (m/s) across any edge, from compute_v_max.

    returns:
        heuristic with coords and v_max pre-bound, matching
        a_star_utils.py's Heuristic = Callable[[Node, Node], int].
    """
    return partial(heuristic, coords=coords, v_max=v_max)


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
    h = build_heuristic(coords, v_max)

    start = perf_counter()
    g, parent, iterations = a_star(graph, SOURCE, TARGET, h, verbose=True)
    elapsed_ms = (perf_counter() - start) * 1000
    path = rebuild_path(parent, SOURCE, TARGET)

    print_path_summary(
        SOURCE, TARGET, path, g, dist_fmt=seconds_to_hms, node_fmt=node_fmt
    )
    print(f"\nIterations needed: {iterations}")
    print(f"Elapsed time: {elapsed_ms:.3f} ms")


if __name__ == "__main__":
    resources_dir = Path(__file__).resolve().parent / "resources"
    resources_dir.mkdir(exist_ok=True)
    output_path = resources_dir / f"a_star_{SOURCE}_to_{TARGET}.txt"
    with output_path.open("w", encoding="utf-8") as file_handle:
        with redirect_stdout(file_handle):
            main()
    print(f"{output_path.name} generated into {output_path.relative_to(_PROJECT_ROOT)}")
