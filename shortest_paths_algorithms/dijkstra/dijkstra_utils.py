"""Shared Dijkstra implementations, helpers, and display utilities."""

from __future__ import annotations
from typing import Dict, List, Optional, Set, Tuple

from shortest_paths_algorithms.algorithms_utils import (  # shared with a_star_utils.py
    INF,
    Graph,
    MinHeap,
    Node,
    NodeFmt,
    format_node_label,
)


# ---------------------------------------------------------------------------
# Dijkstra (MinHeap with decrease_priority)
# ---------------------------------------------------------------------------


def _run_dijkstra(
    graph: Graph,
    source: Node,
    verbose: bool = True,
    stop_at: Optional[Node] = None,
    node_fmt: Optional[NodeFmt] = None,
) -> Tuple[Dict[Node, int], Dict[Node, Optional[Node]], int, Dict[Node, bool]]:
    """Run Dijkstra's algorithm, following the Alsedà pseudocode exactly.

    The only intentional deviation: parent[source] is set to None instead of
    ∞, because Python has no natural ∞ sentinel for a node name.

    args:
        graph: A directed, weighted graph represented as an adjacency list.
        source: The starting node for the algorithm.
        verbose: Whether to print iterations and updates while running.
        stop_at: Optional node that stops the search when settled.
        node_fmt: Optional callable to label a node (e.g. stop name and line,
            via `format_stop_label`) in the verbose trace. Ignored when
            verbose is False.

    returns:
        distances: A mapping from each node to its shortest distance from the source.
        parents: A mapping from each node to its parent in the shortest path tree.
        iterations: Number of extracted nodes processed by the algorithm.
        expanded: A mapping from each node to whether it was extracted (settled)
            before the algorithm stopped. Only extracted nodes have an optimal
            distance, per the convergence theorem; when stop_at cuts the search
            short, some reached nodes may only have been relaxed, not extracted.
    """
    nodes = list(graph.keys())

    # Verbose lines are buffered and only printed once the run is over, so the
    # stop_id/label columns can be sized from the nodes actually visited this
    # run (few, for a cut search) instead of every node in the whole graph.
    log_lines: List[Tuple] = []
    visited: Set[Node] = set()

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
            log_lines.append(("extract", iteration, node, best_dist))
            visited.add(node)

        if stop_at is not None and node == stop_at:
            if verbose:
                log_lines.append(("goal",))
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
                    log_lines.append(("update", adj, old_shown, dist_aux, weight, node))
                    visited.update((adj, node))

    if verbose:
        _print_dijkstra_log(log_lines, visited, node_fmt)

    return dist, parent, iteration, expanded


def _print_dijkstra_log(
    log_lines: List[Tuple], visited: Set[Node], node_fmt: Optional[NodeFmt]
) -> None:
    """Flush _run_dijkstra()'s buffered verbose trace, labeling nodes via node_fmt.

    Mirrors a_star_utils.py's _print_a_star_log, so both algorithms' traces
    line up the same way when node_fmt is given.

    args:
        log_lines: Buffered ("extract"/"goal"/"update") entries recorded during the run.
        visited: All nodes seen, used to compute id/label column widths.
        node_fmt: Optional formatter mapping a node to a display label.
    """
    id_width = max((len(n) for n in visited), default=0)
    label_width = max((len(node_fmt(n)) for n in visited), default=0) if node_fmt else 0
    for entry in log_lines:
        if entry[0] == "extract":
            _, iteration_no, node, best_dist = entry
            node_label = format_node_label(node, node_fmt, label_width)
            print(
                f"\nIteration {iteration_no}: extract {node:<{id_width}}{node_label}"
                f" with distance {best_dist}"
            )
        elif entry[0] == "goal":
            print("  -> goal reached!")
        else:
            _, adj, old_shown, dist_aux, weight, via_node = entry
            adj_label = format_node_label(adj, node_fmt, label_width)
            via_label = format_node_label(via_node, node_fmt)
            print(
                f"  -> update {adj:<{id_width}}{adj_label}: {old_shown} ->"
                f" {dist_aux} (w={weight}) via {via_node}{via_label}"
            )


def dijkstra(
    graph: Graph,
    source: Node,
    verbose: bool = True,
    node_fmt: Optional[NodeFmt] = None,
) -> Tuple[Dict[Node, int], Dict[Node, Optional[Node]], int, Dict[Node, bool]]:
    """Run Dijkstra's algorithm from source and return distance and parent maps.

    args:
        graph: A directed, weighted graph represented as an adjacency list.
        source: The starting node for the algorithm.
        verbose: Whether to print iterations and updates while running.
        node_fmt: Optional callable to label a node (e.g. stop name and line)
            in the verbose trace.

    returns:
        distances: A mapping from each node to its shortest distance from the source.
        parents: A mapping from each node to its parent in the shortest path tree.
        iterations: Number of extracted nodes processed by the algorithm.
        expanded: A mapping from each node to whether it was extracted. All
            reachable nodes end up extracted in a full run.
    """
    return _run_dijkstra(
        graph, source, verbose=verbose, stop_at=None, node_fmt=node_fmt
    )


def cut_dijkstra(
    graph: Graph,
    source: Node,
    target: Node,
    verbose: bool = True,
    node_fmt: Optional[NodeFmt] = None,
) -> Tuple[Dict[Node, int], Dict[Node, Optional[Node]], int, Dict[Node, bool]]:
    """Run Dijkstra's algorithm and stop when the target is settled.

    args:
        graph: A directed, weighted graph represented as an adjacency list.
        source: The starting node for the algorithm.
        target: The target node that stops the search when settled.
        verbose: Whether to print iterations and updates while running.
        node_fmt: Optional callable to label a node (e.g. stop name and line)
            in the verbose trace.

    returns:
        distances: A mapping from each node to its distance from the source (not
            all optimal, see expanded).
        parents: A mapping from each node to its parent in the shortest path tree.
        iterations: Number of extracted nodes processed by the algorithm.
        expanded: A mapping from each node to whether it was extracted before the
            target was reached. Only these nodes have an optimal distance.
    """
    return _run_dijkstra(
        graph, source, verbose=verbose, stop_at=target, node_fmt=node_fmt
    )


def best_over_source_candidates(
    graph: Graph,
    source_platforms: Set[Node],
    target_platforms: Set[Node],
) -> Tuple[Node, Node, Dict[Node, int], Dict[Node, Optional[Node]], int]:
    """Run a full dijkstra() once per candidate source, keeping the cheapest pair.

    Only meaningful when source_platforms/target_platforms hold more than one
    candidate each, i.e. WITHOUT_ENTRANCES_GRAPH reduced an entrance endpoint
    to more than one directed-PW-edge platform (algorithms_utils.
    resolve_search_endpoints/resolve_platform_candidates); with the usual
    single-candidate sets, the loop below just runs once.

    dijkstra(graph, source) already gives the distance to every node reachable
    from source in one run, so unlike cut_dijkstra/a_star (target-directed,
    stop early at one specific target, so a fresh run is needed per (source,
    target) pair), only one run per source_platforms candidate is needed here,
    regardless of how many target_platforms candidates there are.

    args:
        graph: A directed, weighted graph.
        source_platforms: Candidate source platform(s).
        target_platforms: Candidate target platform(s).

    returns:
        (best_source, best_target, dist, parent, iterations): the winning
        candidate pair, and the full dijkstra() output from its winning run
        (dist/parent cover every node reachable from best_source, not just
        best_target: the caller can read best_weight back out as
        dist[best_target]).
    """
    best_weight = INF
    best_source: Node = next(iter(source_platforms))
    best_target: Node = next(iter(target_platforms))
    dist: Dict[Node, int] = {}
    parent: Dict[Node, Optional[Node]] = {}
    iterations = 0
    first_candidate = True

    for candidate_source in source_platforms:
        candidate_dist, candidate_parent, candidate_iterations, _ = dijkstra(
            graph, candidate_source, verbose=False
        )
        for candidate_target in target_platforms:
            candidate_weight = candidate_dist[candidate_target]
            if first_candidate or candidate_weight < best_weight:
                best_weight = candidate_weight
                dist, parent, iterations = (
                    candidate_dist,
                    candidate_parent,
                    candidate_iterations,
                )
                best_source, best_target = candidate_source, candidate_target
                first_candidate = False

    return best_source, best_target, dist, parent, iterations


# ---------------------------------------------------------------------------
# Display (Dijkstra/cut_dijkstra-specific; generic helpers live in
# shortest_paths_algorithms/algorithms_utils.py)
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
        "  • Remind that matching iteration counts don't mean equal work: normal"
        " Dijkstra always relaxes every remaining edge to compute ALL distances,"
        " while cut_dijkstra stops the instant the target is settled"
    )
