"""A* algorithm implementation based on Lluís Alsedà pseudocode (slide 45)."""

from __future__ import annotations
from functools import partial
from math import cos, radians, sqrt
from typing import Callable, Dict, Optional, Tuple

from data_validation.gtfs_utils import load_stops_info
from routing_algorithms.algorithms_utils import (  # shared with dijkstra_utils.py
    INF,
    Graph,
    MinHeap,
    Node,
)

Heuristic = Callable[[Node, Node], int]

EARTH_RADIUS_M = 6_371_000.0  # mean Earth radius, used for the flat local projection
Coord = Tuple[float, float]  # (stop_lat, stop_lon) in degrees


# ---------------------------------------------------------------------------
# Geographic heuristic: h(node, target) = straight_line_distance(node, target) / v_max
# ---------------------------------------------------------------------------


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
    the ratio the a_star() admissibility proof (a_star.py module docstring)
    relies on.

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
    an int (flooring can only shrink h, so admissibility is preserved) to
    match Heuristic = Callable[[Node, Node], int] above.

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
        Heuristic = Callable[[Node, Node], int] above.
    """
    return partial(heuristic, coords=coords, v_max=v_max)


def a_star(
    graph: Graph,
    start: Node,
    goal: Node,
    h: Heuristic,
    verbose: bool = True,
) -> Tuple[Dict[Node, int], Dict[Node, Optional[Node]], int]:
    """Run A* algorithm from start to goal using heuristic h.

    Follows the Alsedà pseudocode (slide 45) exactly. Stops as soon as goal
    is extracted from the Open queue, which is guaranteed optimal when h is
    admissible (Alsedà, slide 45: 'if current is goal then return g, parent').

    Unlike Dijkstra, there is no 'full' version that explores all nodes: A* is
    specifically designed for the routing problem (start -> goal), so a single
    function suffices.

    args:
        graph: A directed, weighted graph represented as an adjacency list.
        start: The starting node.
        goal: The target node to find the shortest path to.
        h: Admissible heuristic function h(vertex, goal) -> estimated cost.
        verbose: Whether to print iterations and updates while running.

    returns:
        g: A mapping from each visited node to its shortest distance from start.
        parent: A mapping from each visited node to its parent in the shortest path.
        iterations: Number of nodes extracted from the Open queue.
    """
    nodes = list(graph.keys())

    Open = MinHeap()
    parent: Dict[Node, Optional[Node]] = {
        node: None for node in nodes
    }  # pseudocode: parent[G.order] <- uninitialized
    g: Dict[Node, int] = {node: INF for node in nodes}  # pseudocode: g[G.order] <- ∞

    iteration = 0

    g[start] = 0  # pseudocode: g[start] <- 0
    # parent[start] stays None (pseudocode uses ∞ as sentinel, same convention as Dijkstra)

    f_start = g[start] + h(start, goal)
    Open.add_with_priority(
        start, f_start
    )  # pseudocode: Open.add_with_priority(start, g, h)

    while not Open.is_empty():  # pseudocode: while not Open.IsEmpty do
        current, _ = Open.extract_min()  # pseudocode: current <- Open.extract_min(g, h)

        iteration += 1
        if verbose:
            print(
                f"\nIteration {iteration}: extract {current}"
                f" with g={g[current]} and h={h(current, goal)},"
                f" f={g[current] + h(current, goal)}"
            )

        if current == goal:  # pseudocode: if current is goal then return g, parent
            if verbose:
                print("  -> goal reached!")
            return g, parent, iteration

        for adj, weight in graph[
            current
        ].items():  # pseudocode: for each adj ∈ current.neighbours do
            adj_new_try_gScore = (
                g[current] + weight
            )  # pseudocode: adj_new_try_gScore <- g[current] + ω(current, adj)

            if (
                adj_new_try_gScore < g[adj]
            ):  # pseudocode: if adj_new_try_gScore < g[adj] then
                old_g = g[adj]
                parent[adj] = current  # pseudocode: parent[adj] <- current
                g[adj] = adj_new_try_gScore  # pseudocode: g[adj] <- adj_new_try_gScore

                f_adj = g[adj] + h(adj, goal)  # f = g + h, passed as priority

                if not Open.belongs_to(
                    adj
                ):  # pseudocode: if not Open.BelongsTo(adj) then
                    Open.add_with_priority(
                        adj, f_adj
                    )  # pseudocode: Open.add_with_priority(adj, g, h)
                else:
                    Open.requeue_with_priority(
                        adj, f_adj
                    )  # pseudocode: else Open.requeue_with_priority(adj, g, h)

                if verbose:
                    old_shown = old_g if old_g != INF else "inf"
                    print(
                        f"  -> update {adj}: g {old_shown} -> {adj_new_try_gScore}"
                        f" (w={weight}), h={h(adj, goal)}, f={f_adj} via {current}"
                    )

    return g, parent, iteration  # pseudocode: return failure
