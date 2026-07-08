"""A* algorithm on a small example graph with a hardcoded heuristic."""

from __future__ import annotations
import sys
from pathlib import Path
from typing import Dict

_PROJECT_ROOT = str(Path(__file__).resolve().parents[2])
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from shortest_paths_algorithms.algorithms_utils import (  # noqa: E402
    print_distances,
    print_graph_size,
    print_path_summary,
    rebuild_path,
)
from a_star_utils import Graph, Node, a_star  # noqa: E402

SOURCE = "A"
TARGET = "D"

# Heuristic estimate from each node to TARGET, hardcoded (Alsedà, slide 45: h).
HEURISTIC: Dict[Node, int] = {
    "A": 3,
    "B": 2,
    "C": 1,
    "D": 0,
}


def build_example_graph() -> Graph:
    """Directed, weighted graph with two routes from A to D.

    returns:
        A graph represented as an adjacency list with weights.
    """
    return {
        "A": {"B": 1, "C": 3},
        "B": {"C": 1, "D": 4},
        "C": {"D": 1},
        "D": {},
    }


def h(node: Node, _goal: Node) -> int:
    """Return the hardcoded heuristic estimate from node to goal.

    args:
        node: The node to estimate the remaining distance from.
        _goal: The target node; unused since HEURISTIC is precomputed for TARGET.

    returns:
        The hardcoded heuristic value for node.
    """
    return HEURISTIC[node]


def main() -> None:
    """Run A* on the example graph from SOURCE to TARGET and display the result."""
    graph = build_example_graph()
    g, parent, iterations, _ = a_star(graph, SOURCE, TARGET, h, verbose=True)
    path = rebuild_path(parent, SOURCE, TARGET)

    print_graph_size(graph)
    print_distances(graph, g, show_unreachable=False, source=SOURCE)
    print_path_summary(SOURCE, TARGET, path, g)
    print(f"\nIterations needed: {iterations}")


if __name__ == "__main__":
    main()
