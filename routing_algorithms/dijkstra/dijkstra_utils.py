"""Shared Dijkstra implementations, helpers, and display utilities."""

from __future__ import annotations
from typing import Dict, Optional, Tuple

from routing_algorithms.algorithms_utils import (  # shared with a_star_utils.py
    INF,
    Graph,
    MinHeap,
    Node,
)


# ---------------------------------------------------------------------------
# Dijkstra (MinHeap with decrease_priority)
# ---------------------------------------------------------------------------


def _run_dijkstra(
    graph: Graph,
    source: Node,
    verbose: bool = True,
    stop_at: Optional[Node] = None,
) -> Tuple[Dict[Node, int], Dict[Node, Optional[Node]], int]:
    """Run Dijkstra's algorithm, following the Alsedà pseudocode exactly.

    The only intentional deviation: parent[source] is set to None instead of
    ∞, because Python has no natural ∞ sentinel for a node name.

    args:
        graph: A directed, weighted graph represented as an adjacency list.
        source: The starting node for the algorithm.
        verbose: Whether to print iterations and updates while running.
        stop_at: Optional node that stops the search when settled.

    returns:
        distances: A mapping from each node to its shortest distance from the source.
        parents: A mapping from each node to its parent in the shortest path tree.
        iterations: Number of extracted nodes processed by the algorithm.
    """
    nodes = list(graph.keys())

    pq = MinHeap()
    expanded: Dict[Node, bool] = {
        node: False for node in nodes
    }  # expanded[node] = True if the shortest path to node is already found
    dist: Dict[Node, int] = {
        node: INF for node in nodes
    }  # distances vector from source to every node
    parent: Dict[Node, Optional[Node]] = {
        node: None for node in nodes
    }  # previous vertices in an optimal path

    iteration = 0

    dist[source] = 0
    # parent[source] stays None  (pseudocode uses ∞ as "no parent" sentinel)

    pq.add_with_priority(source, dist[source])

    while not pq.is_empty():  # pseudocode: while not Pq.IsEmpty
        node, best_dist = pq.extract_min()  # pseudocode: node <- Pq.extract_min()
        expanded[node] = True  # pseudocode: expanded[node] <- true

        iteration += 1
        if verbose:
            print(f"\nIteration {iteration}: extract {node} with distance {best_dist}")

        if stop_at is not None and node == stop_at:
            break

        for adj, weight in graph[
            node
        ].items():  # pseudocode: for each adj ∈ node.neighbours
            if expanded[adj]:  # pseudocode: and not expanded[adj]
                continue
            # If we considered adj before it's because we found its shortest path already

            dist_aux = (
                dist[node] + weight
            )  # pseudocode: dist_aux <- dist[node] + ω(node,adj)

            # Relaxation step
            if dist[adj] > dist_aux:  # pseudocode: if dist[adj] > dist_aux
                old_dist_adj = dist[
                    adj
                ]  # captured before overwriting, for verbose output

                if dist[adj] == INF:  # pseudocode: if dist[adj] = ∞
                    pq.add_with_priority(adj, dist_aux)  # first time seeing adj
                else:
                    pq.decrease_priority(
                        adj, dist_aux
                    )  # already in queue, update in place

                dist[adj] = dist_aux  # pseudocode: dist[adj] <- dist_aux
                parent[adj] = node  # pseudocode: parent[adj] <- node

                if verbose:
                    old_shown = old_dist_adj if old_dist_adj != INF else "inf"
                    print(
                        f"  -> update {adj}: {old_shown} -> {dist_aux} (w={weight}) via {node}"
                    )

    return dist, parent, iteration


def dijkstra(
    graph: Graph, source: Node, verbose: bool = True
) -> Tuple[Dict[Node, int], Dict[Node, Optional[Node]], int]:
    """Run Dijkstra's algorithm from source and return distance and parent maps.

    args:
        graph: A directed, weighted graph represented as an adjacency list.
        source: The starting node for the algorithm.
        verbose: Whether to print iterations and updates while running.

    returns:
        distances: A mapping from each node to its shortest distance from the source.
        parents: A mapping from each node to its parent in the shortest path tree.
        iterations: Number of extracted nodes processed by the algorithm.
    """
    return _run_dijkstra(graph, source, verbose=verbose, stop_at=None)


def cut_dijkstra(
    graph: Graph, source: Node, target: Node, verbose: bool = True
) -> Tuple[Dict[Node, int], Dict[Node, Optional[Node]], int]:
    """Run Dijkstra's algorithm and stop when the target is settled.

    args:
        graph: A directed, weighted graph represented as an adjacency list.
        source: The starting node for the algorithm.
        target: The target node that stops the search when settled.
        verbose: Whether to print iterations and updates while running.

    returns:
        distances: A mapping from each node to its shortest distance from the source.
        parents: A mapping from each node to its parent in the shortest path tree.
        iterations: Number of extracted nodes processed by the algorithm.
    """
    return _run_dijkstra(graph, source, verbose=verbose, stop_at=target)


# ---------------------------------------------------------------------------
# Display (Dijkstra/cut_dijkstra-specific; generic helpers live in
# routing_algorithms/algorithms_utils.py)
# ---------------------------------------------------------------------------


def print_summary(
    iterations: int, elapsed_ms: float, cut_iterations: int, cut_elapsed_ms: float
) -> None:
    """Print the iteration counts and execution times for both algorithm runs.

    args:
        iterations: Number of iterations taken by the normal Dijkstra run.
        elapsed_ms: Execution time in milliseconds for the normal Dijkstra run.
        cut_iterations: Number of iterations taken by the cut_dijkstra run.
        cut_elapsed_ms: Execution time in milliseconds for the cut_dijkstra run.
    """
    print(f"Iterations needed: normal={iterations} | cut={cut_iterations}")
    print(f"Execution time: normal={elapsed_ms:.3f} ms | cut={cut_elapsed_ms:.3f} ms")


def print_disclaimer() -> None:
    """Print a disclaimer about the limitations of the execution time comparisons."""
    print(
        "Disclaimer: Execution time comparisons provide only a rough reference and"
        " should not be taken as precise benchmarks. Key factors affecting timings:"
    )
    print("  • Verbose output (print statements) significantly impacts execution time")
    print(
        "  • When iterations match, normal Dijkstra computes ALL distances, while"
        " cut_dijkstra computes only distances needed to reach the target"
    )
