"""Dijkstra's algorithm is based in Lluís Alsedà pseudo-code"""

from __future__ import annotations
import heapq
from time import perf_counter
from typing import Dict, List, Optional, Tuple

Node = str
Weight = int
Graph = Dict[Node, Dict[Node, Weight]]
INF = 10**18


def _run_dijkstra(
    graph: Graph,
    source: Node,
    verbose: bool = True,
    stop_at: Optional[Node] = None,
) -> Tuple[Dict[Node, int], Dict[Node, Optional[Node]], int]:
    """Run Dijkstra's algorithm and optionally stop when a target is settled.

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
    dist: Dict[Node, int] = {node: INF for node in nodes}
    parent: Dict[Node, Optional[Node]] = {
        node: None for node in nodes
    }  # Different in DO notes
    expanded: Dict[Node, bool] = {
        node: False for node in nodes
    }  # expanded[node] = True if the shortest path to node is already found

    dist[source] = 0
    pq: List[Tuple[int, Node]] = [
        (dist[source], source)
    ]  # Priority queue of (distance, node) pairs, ordered by distance
    iteration = 0

    while pq:  # It means "while the priority queue is not empty"
        best_dist, node = heapq.heappop(pq)

        # Skip already expanded nodes or stale queue entries (robustness check).
        # This check is not in the L.A.-pseudocode because it updates the priority and here
        # we can have multiple entries for the same node (that's why we need this check)
        if expanded[node] or best_dist != dist[node]:
            continue

        iteration += 1
        if verbose:
            print(f"\nIteration {iteration}: extract {node} with distance {best_dist}")

        expanded[node] = True

        if stop_at is not None and node == stop_at:
            break

        for adj, weight in graph[node].items():
            # For not going back to already expanded nodes. We have to think in the perspective
            # of starting from the source and going forward. We want the shortest path from the
            # source, not from any other node <-- also because if we considered adj before it's
            # because we found its shortest path already
            if expanded[adj]:
                continue

            new_cost = dist[node] + weight
            if new_cost < dist[adj]:
                old_cost = dist[adj]
                dist[adj] = new_cost
                parent[adj] = node
                heapq.heappush(pq, (new_cost, adj))
                if verbose:
                    old_shown = old_cost if old_cost != INF else "inf"
                    print(f"  -> update {adj}: {old_shown} -> {new_cost} via {node}")

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


def rebuild_path(
    parent: Dict[Node, Optional[Node]], source: Node, target: Node
) -> List[Node]:
    """Reconstruct shortest path from source to target using parent links.

    args:
        parent: A dictionary mapping each node to its parent in the shortest path.
        source: The starting node.
        target: The destination node.

    returns:
        A list of nodes representing the shortest path from source to target.
    """
    path: List[Node] = []
    current: Optional[Node] = target

    while (
        current is not None
    ):  # This would be different if I would have followed DO notes
        path.append(current)
        if current == source:
            break
        current = parent[current]

    if not path or path[-1] != source:
        return []

    path.reverse()
    return path


def build_example_graph(num_example: int) -> Graph:
    """Directed, weighted graph.

    args:
        num_example: The example number (1, 2, 3 or 4) to select which graph to return.

    returns:
        A graph represented as an adjacency list with weights.
    """
    if num_example == 1:  # DO 5th exercise
        return {
            "a": {"v1": 7, "v2": 8, "v3": 1},
            "v1": {"v6": 4, "v5": 4},
            "v2": {"v1": 6, "v3": 1, "v5": 3},
            "v3": {"v4": 6, "v5": 2},
            "v4": {"v5": 1, "v9": 2},
            "v5": {"v7": 4, "v8": 5, "v9": 1},
            "v6": {"v5": 1, "v7": 2},
            "v7": {"v8": 4, "b": 4},
            "v8": {"b": 1},
            "v9": {"v8": 3, "b": 6},
            "b": {},
        }

    if num_example == 2:  # DO class notes
        return {
            "v1": {"v2": 4, "v3": 2, "v4": 3},
            "v2": {"v6": 1},
            "v3": {"v5": 1, "v6": 5},
            "v4": {"v5": 2},
            "v5": {"v6": 2, "v9": 4},
            "v6": {"v7": 3, "v8": 2},
            "v7": {},
            "v8": {"v9": 1},
            "v9": {},
        }

    if (
        num_example == 3
    ):  # Internet example (undirected graph, so I add manually both directions)
        return {
            "v0": {"v1": 4, "v7": 8},
            "v1": {"v0": 4, "v2": 8, "v7": 11},
            "v2": {"v1": 8, "v3": 7, "v5": 4, "v8": 2},
            "v3": {"v2": 7, "v4": 9, "v5": 14},
            "v4": {"v3": 9, "v5": 10},
            "v5": {"v2": 4, "v3": 14, "v4": 10, "v6": 2},
            "v6": {"v5": 2, "v7": 1, "v8": 6},
            "v7": {"v0": 8, "v1": 11, "v6": 1, "v8": 7},
            "v8": {"v2": 2, "v6": 6, "v7": 7},
        }

    if num_example == 4:  # Internet example
        return {
            "A": {"B": 3, "C": 1},
            "B": {"D": 2, "T": 3},
            "C": {"D": 1, "R": 4},
            "D": {"S": 1},
            "E": {"H": 4},
            "F": {"W": 1},
            "G": {"F": 5},
            "H": {"F": 1, "G": 1, "X": 2},
            "I": {"K": 1},
            "J": {"I": 3, "K": 5, "L": 7},
            "K": {"L": 1},
            "L": {"V": 2},
            "M": {"N": 7},
            "N": {"P": 3},
            "O": {"U": 3},
            "P": {"O": 5, "Q": 2},
            "Q": {"A": 2},
            "R": {"M": 4},
            "S": {"F": 1},
            "T": {"E": 3},
            "U": {"J": 1},
            "V": {"M": 2},
            "W": {"I": 1},
            "X": {"I": 2},
        }

    else:
        raise ValueError(f"Invalid example number: {num_example}")


def print_distances(graph: Graph, dist: Dict[Node, int]) -> None:
    """Print the shortest distance from the source to every node in the graph.

    args:
        graph: A directed, weighted graph represented as an adjacency list.
        dist: A mapping from each node to its shortest distance from the source.
    """
    nodes = list(graph.keys())
    width = max(len(n) for n in nodes)
    print("\nShortest distances from source:")
    for node in nodes:
        value = dist[node]
        shown = value if value != INF else "inf"
        print(f"- {node:<{width}} : {shown}")


def print_path_summary(
    source: Node, target: Node, path: List[Node], dist: Dict[Node, int]
) -> None:
    """Print the rebuilt path from source to target and its total distance.

    args:
        source: The starting node.
        target: The destination node.
        path: The rebuilt path from source to target, or an empty list if none.
        dist: A mapping from each node to its shortest distance from the source.
    """
    if path:
        print(f"\nShortest path from {source} to {target}:")
        print("  ", " -> ".join(path))
        total = dist[target]
        shown_total = total if total != INF else "inf"
        print(f"Minimum distance found: {shown_total}")
    else:
        print(f"\nNo path found from {source} to {target}.")


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


def main() -> None:
    """Run Dijkstra's algorithm on multiple example graphs and display results."""

    examples = [(1, "a", "b"), (2, "v1", "v9"), (3, "v0", "v4"), (4, "A", "K")]
    graph: Graph
    start: float
    dist: Dict[Node, int]
    parent: Dict[Node, Optional[Node]]
    iterations: int
    path: List[Node]
    elapsed_ms: float
    cut_start: float
    cut_iterations: int
    cut_elapsed_ms: float

    print_disclaimer()

    for num_example, source, target in examples:
        print("\n\n" + "=" * 50)
        print(f"Running example {num_example}: source={source} target={target}")
        print("=" * 50)
        graph = build_example_graph(num_example=num_example)

        start = perf_counter()
        dist, parent, iterations = dijkstra(graph, source, verbose=True)
        elapsed_ms = (perf_counter() - start) * 1000
        path = rebuild_path(parent, source, target)

        cut_start = perf_counter()
        _, _, cut_iterations = cut_dijkstra(graph, source, target, verbose=False)
        cut_elapsed_ms = (perf_counter() - cut_start) * 1000

        print_distances(graph, dist)
        print_path_summary(source, target, path, dist)
        print_summary(iterations, elapsed_ms, cut_iterations, cut_elapsed_ms)


if __name__ == "__main__":
    main()
