from __future__ import annotations

import heapq
from time import perf_counter
from typing import Dict, List, Optional, Tuple

Node = str
Weight = int
Graph = Dict[Node, Dict[Node, Weight]]
INF = 10**18


def print_iteration_header(
    current_iteration: int, current_node: Node, current_dist: int
) -> None:
    """Print a visual separator and the current iteration header.

    args:
        current_iteration: Current iteration number.
        current_node: Node extracted from the priority queue.
        current_dist: Distance associated with the extracted node.
    """
    print("\n" + "=" * 50)
    print(
        f"Iteration {current_iteration}: extract {current_node} with distance {current_dist}"
    )
    print("=" * 50)


def dijkstra(
    graph: Graph, source: Node, verbose: bool = True
) -> Tuple[Dict[Node, int], Dict[Node, Optional[Node]]]:
    """Run Dijkstra's algorithm from source and return distance and parent maps.
    (Lluis Alsedà pseudocode)

    args:
        graph: A directed, weighted graph represented as an adjacency list.
        source: The starting node for the algorithm.
        verbose: Whether to print iterations and updates while running.

    returns:
        distances: A mapping from each node to its shortest distance from the source.
        parents: A mapping from each node to its parent in the shortest path tree.
    """
    nodes = list(graph.keys())
    dist: Dict[Node, int] = {node: INF for node in nodes}
    parent: Dict[Node, Optional[Node]] = {
        node: None for node in nodes
    }  # Different in DO notes
    expanded: Dict[Node, bool] = {node: False for node in nodes}

    dist[source] = 0
    pq: List[Tuple[int, Node]] = [
        (0, source)
    ]  # Priority queue of (distance, node) pairs, ordered by distance
    iteration = 0
    print(f"Starting Dijkstra's algorithm from source: {source}")

    while pq:  # It means "while the priority queue is not empty"
        best_dist, node = heapq.heappop(pq)

        # Skip stale queue entries or already expanded nodes
        if expanded[node] or best_dist != dist[node]:
            continue

        iteration += 1
        if verbose:
            print_iteration_header(iteration, node, best_dist)

        expanded[node] = True

        for adj, weight in graph[node].items():
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

    return dist, parent


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

    returns:
        A graph represented as an adjacency list with weights.
    """
    if num_example == 1:
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
    else:
        return {
            "a": {"v2": 4, "v3": 2, "v4": 3},
            "v2": {"v6": 1},
            "v3": {"v5": 1, "v6": 5},
            "v4": {"v5": 2},
            "v5": {"v6": 2, "b": 4},
            "v6": {"v7": 3, "v8": 2},
            "v7": {},
            "v8": {"b": 1},
            "b": {},
        }


def main() -> None:
    for num_example in [1, 2]:
        print(f"\n{'#' * 60}\nRunning example {num_example}...\n{'#' * 60}")
        graph = build_example_graph(num_example=num_example)
        source = "a"
        target = "b"

        start = perf_counter()
        dist, parent = dijkstra(graph, source, verbose=True)
        path = rebuild_path(parent, source, target)
        elapsed_ms = (perf_counter() - start) * 1000

        print("Shortest distances from source:")
        for node in graph:
            value = dist[node]
            shown = value if value != INF else "inf"
            print(f"- {node}: {shown}")

        if path:
            print(f"\nShortest path from {source} to {target}: {' -> '.join(path)}")
            total = dist[target]
            shown_total = total if total != INF else "inf"
            print(f"Minimum distance found: {shown_total}")
        else:
            print(f"\nNo path found from {source} to {target}.")

        print(f"Execution time: {elapsed_ms:.3f} ms")


if __name__ == "__main__":
    main()
