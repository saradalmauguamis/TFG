"""Shared Dijkstra implementations, helpers, and display utilities."""

from __future__ import annotations
import heapq
from typing import Dict, List, Optional, Tuple

Node = str
Weight = int
Graph = Dict[Node, Dict[Node, Weight]]
INF = 10**18


# ---------------------------------------------------------------------------
# Binary heap priority queue with O(log n) decrease_priority
# ---------------------------------------------------------------------------


class MinHeap:
    """Binary heap priority queue using a consecutive levels vector (Alsedà, slide 96).

    The heap is stored as a flat Python list where levels are stored consecutively:
    first the unique element of level 0, then the two elements of level 1, etc.
    This avoids the complications of a bi-directional binary tree (Alsedà, slide 95).

    Mirrors the three operations named in the Alsedà pseudocode:
        add_with_priority  — enqueue (Alsedà, slide 87): O(log Q̄)
        extract_min        — dequeue (Alsedà, slide 87): O(log Q̄)
        decrease_priority  — requeue (Alsedà, slide 87): O(log Q̄)

    Heap property (Alsedà, slide 84): every parent <= its children. Siblings are unordered.
    This means index 0 is always the minimum, but the rest of the array
    is NOT fully sorted, so extract_min must be called to get each next minimum.

    Estimated average execution time (Alsedà, slide 33):
        |V|(T_EM + T_AwP) + (|E| - |V|) * T_DP
    """

    def __init__(self) -> None:
        """Initialize an empty heap.

        args:
            self: The MinHeap instance being initialized.
        """
        self._heap: List[Tuple[int, Node]] = []  # (dist, vertex) pairs
        self._pos: Dict[Node, int] = {}  # vertex --> index in heap (it starts in 0)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _swap(self, i: int, j: int) -> None:
        """Swap the heap entries at two indices and keep _pos in sync.

        args:
            self: The MinHeap instance being mutated.
            i: Index of the first entry to swap.
            j: Index of the second entry to swap.
        """
        u, v = self._heap[i], self._heap[j]
        self._heap[i], self._heap[j] = v, u
        self._pos[u[1]], self._pos[v[1]] = j, i

    def heapify_up(self, i: int) -> None:
        """Restore heap property upward from index i (Alsedà, slide 89: heapify_up).

        Used after add_with_priority and decrease_priority since the new distance
        can only be smaller — the heap property can only be violated upward.

        Parent index formula from Alsedà slide 88: parentOf(d,p) = (d-1, floor(p/2)),
        which translates to (i-1)//2 in the consecutive levels vector.

        args:
            self: The MinHeap instance being mutated.
            i: Index to start heapifying up from.
        """
        while i > 0:
            parent = (i - 1) // 2
            if self._heap[parent][0] > self._heap[i][0]:
                self._swap(parent, i)
                i = parent
            else:
                break

    def heapify_down(self, i: int) -> None:
        """Restore heap property downward from index i (Alsedà, slide 90: heapify_down).

        Used after extract_min, since moving the last node to the root preserves
        the shape property but may break the heap property (Alsedà, slide 94).
        Swaps with the smaller of the two children at each step (Alsedà, slide 90:
        'smallson'), since swapping with the larger would violate the heap property
        on that side.

        args:
            self: The MinHeap instance being mutated.
            i: Index to start heapifying down from.
        """
        n = len(self._heap)
        while True:
            smallest = i
            for child in (2 * i + 1, 2 * i + 2):
                if child < n and self._heap[child][0] < self._heap[smallest][0]:
                    smallest = child
            if smallest == i:
                break
            self._swap(i, smallest)
            i = smallest

    # ------------------------------------------------------------------
    # Public interface  (names match the pseudocode exactly)
    # ------------------------------------------------------------------

    def is_empty(self) -> bool:
        """Return whether the heap currently holds no entries.

        args:
            self: The MinHeap instance being queried.

        returns:
            True when the heap is empty, otherwise False.
        """
        return len(self._heap) == 0

    def add_with_priority(self, vertex: Node, dist: int) -> None:
        """Enqueue a new vertex with the given distance, in O(log Q̄) time.

        Corresponds to enqueue in Alsedà (slide 87): appends the new node to the
        last level of the heap (preserving the shape property), then heapify_up
        restores the heap property.

        This is the operation the pseudocode calls Pq.add_with_priority (Alsedà, slide 18).

        T_AwP time taken & run |V| times (each node enters the queue exactly once).

        args:
            self: The MinHeap instance being mutated.
            vertex: The vertex to enqueue.
            dist: The priority (distance) to enqueue the vertex with.
        """
        self._heap.append((dist, vertex))
        self._pos[vertex] = len(self._heap) - 1
        self.heapify_up(self._pos[vertex])

    def extract_min(self) -> Tuple[Node, int]:
        """Remove and return the vertex with smallest distance, in O(log Q̄) time.

        Corresponds to dequeue in Alsedà (slide 87) via the three-step procedure (slide 94):
        Step 1: Read the root node (minimum by heap property, Alsedà slide 85).
        Step 2: Replace root with last node — preserves shape property without search.
        Step 3: heapify_down from root — restores heap property.

        This is the operation the pseudocode calls Pq.extract_min (Alsedà, slide 18).

        T_EM time taken & run |V| times (the while loop runs for |V| repetitions).

        args:
            self: The MinHeap instance being mutated.

        returns:
            A (vertex, distance) pair for the previous minimum entry.
        """
        dist: int
        vertex: Node
        root_dist: int
        root_vertex: Node
        last_dist: int
        last_vertex: Node

        if len(self._heap) == 1:
            dist, vertex = self._heap.pop()
            del self._pos[vertex]
            return vertex, dist

        # Save the root <- this is what we'll return
        root_dist, root_vertex = self._heap[0]

        # Pop the last element and place it at the root
        last_dist, last_vertex = self._heap.pop()
        self._heap[0] = (last_dist, last_vertex)

        # Update _pos: root_vertex is gone, last_vertex moved to index 0
        del self._pos[root_vertex]
        self._pos[last_vertex] = 0

        self.heapify_down(0)
        return root_vertex, root_dist

    def decrease_priority(self, vertex: Node, new_dist: int) -> None:
        """Lower the distance of a vertex already in the queue, in O(log Q̄) time.

        Corresponds to requeue in Alsedà (slide 87): the shape property is maintained
        since no structural change occurs; only the heap property may be violated
        upward, so heapify_up suffices.

        This is the operation the pseudocode calls Pq.decrease_priority (Alsedà, slide 18).

        T_DP time taken & run |E| - |V| times (the relaxation loop runs at most |E| repetitions).

        args:
            self: The MinHeap instance being mutated.
            vertex: The vertex already present in the heap.
            new_dist: The new, smaller distance to assign to the vertex.
        """
        i = self._pos[vertex]
        self._heap[i] = (new_dist, vertex)
        self.heapify_up(i)  # new dist is smaller, so only go up


# ---------------------------------------------------------------------------
# Dijkstra — old version (stdlib heapq, lazy deletion)
# ---------------------------------------------------------------------------


def _run_dijkstra_old(
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


def dijkstra_old(
    graph: Graph, source: Node, verbose: bool = True
) -> Tuple[Dict[Node, int], Dict[Node, Optional[Node]], int]:
    """Run the old Dijkstra's algorithm from source and return distance and parent maps.

    args:
        graph: A directed, weighted graph represented as an adjacency list.
        source: The starting node for the algorithm.
        verbose: Whether to print iterations and updates while running.

    returns:
        distances: A mapping from each node to its shortest distance from the source.
        parents: A mapping from each node to its parent in the shortest path tree.
        iterations: Number of extracted nodes processed by the algorithm.
    """
    return _run_dijkstra_old(graph, source, verbose=verbose, stop_at=None)


def cut_dijkstra_old(
    graph: Graph, source: Node, target: Node, verbose: bool = True
) -> Tuple[Dict[Node, int], Dict[Node, Optional[Node]], int]:
    """Run the old Dijkstra's algorithm and stop when the target is settled.

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
    return _run_dijkstra_old(graph, source, verbose=verbose, stop_at=target)


# ---------------------------------------------------------------------------
# Dijkstra — new version (MinHeap with decrease_priority)
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
    iteration = int

    dist[source] = 0
    # parent[source] stays None  (pseudocode uses ∞ as "no parent" sentinel)

    pq.add_with_priority(source, dist[source])

    iteration = 0

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
                if dist[adj] == INF:  # pseudocode: if dist[adj] = ∞
                    pq.add_with_priority(adj, dist_aux)  # first time seeing adj
                else:
                    pq.decrease_priority(
                        adj, dist_aux
                    )  # already in queue, update in place

                dist[adj] = dist_aux  # pseudocode: dist[adj] <- dist_aux
                parent[adj] = node  # pseudocode: parent[adj] <- node

                if verbose:
                    old = best_dist if dist[node] == best_dist else dist[node]
                    print(f"  -> update {adj}: {old} -> {dist_aux} via {node}")

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
# Path reconstruction and display
# ---------------------------------------------------------------------------


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

    while current is not None:
        path.append(current)
        if current == source:
            break
        current = parent[current]

    if not path or path[-1] != source:
        return []

    path.reverse()
    return path


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
        shown = (
            value if value != INF else "inf"
        )  # Later exclude the inf ones? To know which ones have been considered
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
