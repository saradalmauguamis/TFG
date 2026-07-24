"""A* algorithm implementation based on Lluís Alsedà pseudocode (slide 45).

The admissible heuristics pluggable into a_star() below (h_geo, h_cheat,
h_bcn) live in shortest_paths_algorithms/a_star/heuristics/, one module each; this
file only holds the algorithm-agnostic core shared by all of them: the
Heuristic type and a_star() itself.
"""

from __future__ import annotations
from typing import Callable, Dict, List, Optional, Set, Tuple

from shortest_paths_algorithms.algorithms_utils import (  # shared with dijkstra_utils.py
    INF,
    Graph,
    MinHeap,
    Node,
    NodeFmt,
    format_node_label,
)

Heuristic = Callable[[Node, Node], int]

# ---------------------------------------------------------------------------
# Heuristic name: which build_h_* heuristic a_star.py/a_star_report.py picks.
# ---------------------------------------------------------------------------
HeuristicName = str
H_GEO: HeuristicName = "h_geo"
H_CHEAT: HeuristicName = "h_cheat"
H_BCN: HeuristicName = "h_bcn"


def a_star(
    graph: Graph,
    start: Node,
    goal: Node,
    h: Heuristic,
    verbose: bool = True,
    node_fmt: Optional[NodeFmt] = None,
) -> Tuple[Dict[Node, int], Dict[Node, Optional[Node]], int, Dict[Node, bool]]:
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
        node_fmt: Optional callable to label a node (e.g. stop name and line,
            via `stop_label`) in the verbose trace, same as
            dijkstra_utils.py's _run_dijkstra. Ignored when verbose is False.

    returns:
        g: A mapping from each visited node to its shortest distance from start.
        parent: A mapping from each visited node to its parent in the shortest path.
        iterations: Number of nodes extracted from the Open queue.
        expanded: A mapping from each node to whether it was extracted from Open
            before the search stopped. Not part of the Alsedà pseudocode (A*
            never needs a closed-set check with an admissible heuristic); tracked
            purely so callers can later visualize which nodes A* actually settled,
            same as dijkstra_utils.py's expanded.
    """
    nodes = list(graph.keys())

    # Verbose lines are buffered and only printed once the run is over, so the
    # node_id/label columns can be sized from the nodes actually visited this
    # run, same as dijkstra_utils.py's _run_dijkstra.
    log_lines: List[Tuple] = []
    visited: Set[Node] = set()

    Open = MinHeap()
    parent: Dict[Node, Optional[Node]] = {
        node: None for node in nodes
    }  # pseudocode: parent[G.order] <- uninitialized
    g: Dict[Node, int] = {node: INF for node in nodes}  # pseudocode: g[G.order] <- ∞
    expanded: Dict[Node, bool] = {
        node: False for node in nodes
    }  # not in the pseudocode (see expanded's docstring above)

    iteration = 0

    g[start] = 0  # pseudocode: g[start] <- 0
    # parent[start] stays None (pseudocode uses ∞ as sentinel, same convention as Dijkstra)

    f_start = g[start] + h(start, goal)
    Open.add_with_priority(
        start, f_start
    )  # pseudocode: Open.add_with_priority(start, g, h)

    while not Open.is_empty():  # pseudocode: while not Open.IsEmpty do
        current, _ = Open.extract_min()  # pseudocode: current <- Open.extract_min(g, h)
        expanded[current] = (
            True  # not in the pseudocode (see expanded's docstring above)
        )

        iteration += 1
        if verbose:
            log_lines.append(
                ("extract", iteration, current, g[current], h(current, goal))
            )
            visited.add(current)

        if current == goal:  # pseudocode: if current is goal then return g, parent
            if verbose:
                log_lines.append(("goal",))
                _print_a_star_log(log_lines, visited, node_fmt)
            return g, parent, iteration, expanded

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
                    Open.decrease_priority(
                        adj, f_adj
                    )  # pseudocode: else Open.requeue_with_priority(adj, g, h)

                if verbose:
                    old_shown = old_g if old_g != INF else "inf"
                    log_lines.append(
                        (
                            "update",
                            adj,
                            old_shown,
                            adj_new_try_gScore,
                            weight,
                            h(adj, goal),
                            f_adj,
                            current,
                        )
                    )
                    visited.update((adj, current))

    if verbose:
        _print_a_star_log(log_lines, visited, node_fmt)
    return g, parent, iteration, expanded  # pseudocode: return failure


def _print_a_star_log(
    log_lines: List[Tuple], visited: Set[Node], node_fmt: Optional[NodeFmt]
) -> None:
    """Flush a_star()'s buffered verbose trace, labeling nodes via node_fmt.

    Mirrors dijkstra_utils.py's _run_dijkstra end-of-run print block, so both
    algorithms' traces line up the same way when node_fmt is given.

    args:
        log_lines: Buffered ("extract"/"goal"/"update") entries recorded during the run.
        visited: All nodes seen, used to compute id/label column widths.
        node_fmt: Optional formatter mapping a node to a display label.
    """
    id_width = max((len(n) for n in visited), default=0)
    label_width = max((len(node_fmt(n)) for n in visited), default=0) if node_fmt else 0
    for entry in log_lines:
        if entry[0] == "extract":
            _, iteration_no, current, g_current, h_current = entry
            current_label = format_node_label(current, node_fmt, label_width)
            print(
                f"\nIteration {iteration_no}: extract {current:<{id_width}}{current_label}"
                f" with g={g_current} and h={h_current}, f={g_current + h_current}"
            )
        elif entry[0] == "goal":
            print("  -> goal reached!")
        else:
            _, adj, old_shown, adj_new_try_gScore, weight, h_adj, f_adj, current = entry
            adj_label = format_node_label(adj, node_fmt, label_width)
            via_label = format_node_label(current, node_fmt)
            print(
                f"  -> update {adj:<{id_width}}{adj_label}: g {old_shown} ->"
                f" {adj_new_try_gScore} (w={weight}), h={h_adj}, f={f_adj}"
                f" via {current}{via_label}"
            )
