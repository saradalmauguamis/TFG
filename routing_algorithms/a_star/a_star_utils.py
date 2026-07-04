"""A* algorithm implementation based on Lluís Alsedà pseudocode (slide 45)."""

from __future__ import annotations
from typing import Callable, Dict, Optional, Tuple

from routing_algorithms.algorithms_utils import (  # shared with dijkstra_utils.py
    INF,
    Graph,
    MinHeap,
    Node,
)

Heuristic = Callable[[Node, Node], int]


def a_star(
    graph: Graph,
    start: Node,
    goal: Node,
    h: Heuristic,
    verbose: bool = True,
) -> Tuple[Dict[Node, int], Dict[Node, Optional[Node]], int]:
    """Run A* algorithm from start to goal using heuristic h.

    Follows the Alsedà pseudocode (slide 45) exactly. Stops as soon as goal
    is extracted from the Open queue — guaranteed optimal when h is admissible
    (Alsedà, slide 45: 'if current is goal then return g, parent').

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
    # MAYBE CHANGE IT TO FLOAT??

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
