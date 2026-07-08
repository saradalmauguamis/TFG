"""h_cheat: h(node, target) = actual optimal cost(node, target).

Technically admissible, but only because it already knows the answer: computing it
already requires solving the shortest-path problem A* is trying to solve, via
cut_dijkstra (shared with dijkstra_utils.py), so it is only useful to see how A*
behaves with a perfect heuristic (e.g. as a lower bound on iterations), never as a
practical heuristic.
"""

from __future__ import annotations
from functools import partial

from shortest_paths_algorithms.algorithms_utils import Graph, Node
from shortest_paths_algorithms.a_star.a_star_utils import Heuristic
from shortest_paths_algorithms.dijkstra.dijkstra_utils import cut_dijkstra


def h_cheat(node: Node, target: Node, graph: Graph) -> int:
    """Return the actual optimal cost from node to target, via cut_dijkstra.

    args:
        node: The node to compute the true remaining cost from.
        target: The target node.
        graph: A directed, weighted graph, as returned by build_graph_from_weights.

    returns:
        The true shortest-path distance from node to target (dist[target] from
        cut_dijkstra(graph, source=node, target=target), guaranteed optimal by
        the convergence theorem since target is settled before the search stops).
    """
    dist, _, _, _ = cut_dijkstra(graph, source=node, target=target, verbose=False)
    return dist[target]


def build_h_cheat(graph: Graph) -> Heuristic:
    """Bind graph into h_cheat, producing a plain Heuristic(node, target).

    args:
        graph: A directed, weighted graph, as returned by build_graph_from_weights.

    returns:
        h_cheat with graph pre-bound, matching
        Heuristic = Callable[[Node, Node], int] (a_star_utils.py).
    """
    return partial(h_cheat, graph=graph)
