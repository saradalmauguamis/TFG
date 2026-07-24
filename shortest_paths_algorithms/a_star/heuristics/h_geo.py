"""h_geo: h(node, target) = straight_line_distance(node, target) / v_max.

Admissible since v_max (compute_v_max) is the fastest implied speed across
any single edge in the real graph, so straight_line_distance / v_max can
never overestimate the true travel time along any path.
"""

from __future__ import annotations
from functools import partial
from math import cos, radians, sqrt
from typing import Dict, Tuple

from data_validation.gtfs_utils import load_stops_info
from shortest_paths_algorithms.algorithms_utils import Graph, Node
from shortest_paths_algorithms.a_star.a_star_utils import Heuristic

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
    the ratio h_geo's admissibility (module docstring above) relies on.

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


def h_geo(node: Node, target: Node, coords: Dict[Node, Coord], v_max: float) -> int:
    """Return the admissible geographic heuristic estimate from node to target.

    h_geo(node, target) = straight_line_distance(node, target) / v_max, floored
    to an int (flooring can only shrink h, so admissibility is preserved) to
    match Heuristic = Callable[[Node, Node], int] (a_star_utils.py).

    args:
        node: The node to estimate the remaining cost from.
        target: The target node.
        coords: Mapping from node to its (lat, lon) coordinates.
        v_max: Fastest implied speed (m/s) across any edge, from compute_v_max.

    returns:
        straight_line_distance(node, target) / v_max, floored to an int.
    """
    return int(straight_line_distance(coords[node], coords[target]) / v_max)


def build_h_geo(coords: Dict[Node, Coord], v_max: float) -> Heuristic:
    """Bind coords and v_max into h_geo, producing a plain Heuristic(node, target).

    args:
        coords: Mapping from node to its (lat, lon) coordinates.
        v_max: Fastest implied speed (m/s) across any edge, from compute_v_max.

    returns:
        h_geo with coords and v_max pre-bound, matching
        Heuristic = Callable[[Node, Node], int] (a_star_utils.py).
    """
    return partial(h_geo, coords=coords, v_max=v_max)
