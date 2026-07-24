"""Dijkstra's algorithm, based on Lluís Alsedà's pseudo-code, run on small example graphs to
understand how the algorithm works before trusting it on real data."""

from __future__ import annotations
import sys
from pathlib import Path
from time import perf_counter
from typing import Dict, List, Optional

_PROJECT_ROOT = str(Path(__file__).resolve().parents[2])
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from shortest_paths_algorithms.algorithms_utils import (  # noqa: E402
    print_distances,
    print_graph_size,
    print_path_summary,
    rebuild_path,
)
from dijkstra_utils import (  # noqa: E402
    Graph,
    Node,
    cut_dijkstra,
    dijkstra,
    print_disclaimer,
    print_summary,
)


def build_example_graph(num_example: int) -> Graph:
    """Directed, weighted graph.

    args:
        num_example: The example number (1, 2, 3 or 4) to select which graph to return.

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
    if num_example == 2:
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
    if num_example == 3:
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
    if num_example == 4:
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
    raise ValueError(f"Invalid example number: {num_example}")


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
        print_graph_size(graph)

        start = perf_counter()
        dist, parent, iterations, _ = dijkstra(graph, source, verbose=True)
        elapsed_ms = (perf_counter() - start) * 1000
        path = rebuild_path(parent, source, target)

        cut_start = perf_counter()
        _, _, cut_iterations, _ = cut_dijkstra(graph, source, target, verbose=False)
        cut_elapsed_ms = (perf_counter() - cut_start) * 1000

        print_distances(graph, dist)
        print_path_summary(source, target, path, dist)
        print_summary(iterations, elapsed_ms, cut_iterations, cut_elapsed_ms)


if __name__ == "__main__":
    main()
