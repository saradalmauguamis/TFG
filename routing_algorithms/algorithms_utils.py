"""Shared graph types, binary heap, and display utilities used by Dijkstra and A*."""

from __future__ import annotations
from typing import Callable, Dict, List, Optional, Tuple

Node = str
Weight = int
Graph = Dict[Node, Dict[Node, Weight]]
INF = (
    10**18
)  # int equivalent of float('inf'); keeps dist/g arithmetic and equality in pure int


# ---------------------------------------------------------------------------
# Binary heap priority queue with O(log₂ n) decrease_priority
# ---------------------------------------------------------------------------


class MinHeap:
    """Binary heap priority queue using a consecutive levels vector (Alsedà, slide 96).

    The heap is stored as a flat Python list where levels are stored consecutively:
    first the unique element of level 0, then the two elements of level 1, etc.
    This avoids the complications of a bi-directional binary tree (Alsedà, slide 95).

    Mirrors the operations named in the Alsedà pseudocodes:
        Dijkstra (slide 18)       A* (slide 45)
        add_with_priority      —  add_with_priority
        extract_min            —  extract_min
        decrease_priority      —  requeue_with_priority
        (implicit via dist=∞)  —  belongs_to

    All three mutating operations run in O(log₂ Q̄) time (Alsedà, slide 34).

    Heap property (Alsedà, slide 84): every parent <= its children. Siblings are
    unordered. This means index 0 is always the minimum, but the rest of the array
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

        Used after add_with_priority and decrease_priority since the new priority
        can only be smaller, so the heap property can only be violated upward.

        Parent index (i-1)//2 is the translation of parentOf(d,p) = (d-1, floor(p/2))
        (Alsedà, slide 88) into the 1-dimensional consecutive levels vector position
        (2^d - 1) + p (Alsedà, slide 96).

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
        Swaps with the smallson (smaller of the two children) at each step
        (Alsedà, slide 90), since swapping with the larger would violate the heap
        property on that side.

        Children indices 2i+1 and 2i+2 are the translation of
        leftchildOf(d,p) = (d+1, 2p) and rightchildOf(d,p) = (d+1, 2p+1)
        (Alsedà, slide 88) into the 1-dimensional consecutive levels vector position
        (2^d - 1) + p (Alsedà, slide 96).

        args:
            self: The MinHeap instance being mutated.
            i: Index to start heapifying down from.
        """
        n = len(self._heap)
        while True:
            smallson = i
            for child in (2 * i + 1, 2 * i + 2):
                if child < n and self._heap[child][0] < self._heap[smallson][0]:
                    smallson = child
            if smallson == i:
                break
            self._swap(i, smallson)
            i = smallson

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

    def belongs_to(self, vertex: Node) -> bool:
        """Return whether vertex is currently in the queue (Alsedà, slide 45: BelongsTo).

        Needed in A* because g[adj] is overwritten before the membership check,
        so g[adj] == INF can no longer serve as a proxy for 'not yet enqueued'
        (unlike in Dijkstra where dist is checked before being overwritten).
        Runs in O(1) via the _pos index.

        args:
            vertex: The vertex to check membership for.

        returns:
            True if vertex is currently in the Open queue, otherwise False.
        """
        return vertex in self._pos

    def add_with_priority(self, vertex: Node, priority: int) -> None:
        """Enqueue a new vertex with the given priority, in O(log₂ Q̄) time.

        Corresponds to enqueue in Alsedà (slide 87): appends the new node to the
        last level of the heap (preserving the shape property), then heapify_up
        restores the heap property.

        Called with priority=dist in Dijkstra (slide 18: Pq.add_with_priority)
        and priority=f=g+h in A* (slide 45: Open.add_with_priority).

        T_AwP time taken & run |V| times (each node enters the queue exactly once).

        args:
            vertex: The vertex to enqueue.
            priority: The priority value (dist for Dijkstra, f=g+h for A*).
        """
        self._heap.append((priority, vertex))
        self._pos[vertex] = len(self._heap) - 1
        self.heapify_up(self._pos[vertex])

    def extract_min(self) -> Tuple[Node, int]:
        """Remove and return the vertex with smallest priority, in O(log₂ Q̄) time.

        Corresponds to dequeue in Alsedà (slide 87) via the three-step procedure
        (slide 94):
        Step 1: Read the root node (minimum by heap property, Alsedà slide 85).
        Step 2: Replace root with last node, which preserves the shape property without search.
        Step 3: heapify_down from root, which restores the heap property.

        Called as Pq.extract_min in Dijkstra (slide 18) and Open.extract_min in
        A* (slide 45). In A* the pseudocode writes extract_min(g, h) because the
        priority f=g+h is computed at extraction time in the notes' formulation;
        here f is stored at insertion/requeue time so no arguments are needed.

        T_EM time taken & run |V| times (the while loop runs for |V| repetitions).

        args:
            self: The MinHeap instance being operated on.

        returns:
            A (vertex, priority) pair for the extracted minimum entry.
        """
        dist: int
        vertex: Node
        root_priority: int
        root_vertex: Node
        last_priority: int
        last_vertex: Node

        if len(self._heap) == 1:
            dist, vertex = self._heap.pop()
            del self._pos[vertex]
            return vertex, dist

        # Step 1: save the root, since this is what we'll return
        root_priority, root_vertex = self._heap[0]

        # Step 2: pop the last element and place it at the root
        last_priority, last_vertex = self._heap.pop()
        self._heap[0] = (last_priority, last_vertex)

        # Update _pos: root_vertex is gone, last_vertex moved to index 0
        del self._pos[root_vertex]
        self._pos[last_vertex] = 0

        # Step 3: restore heap property
        self.heapify_down(0)
        return root_vertex, root_priority

    def decrease_priority(self, vertex: Node, new_priority: int) -> None:
        """Lower the priority of a vertex already in the queue, in O(log₂ Q̄) time.

        Corresponds to requeue in Alsedà (slide 87): the shape property is maintained
        since no structural change occurs; only the heap property may be violated
        upward, so heapify_up suffices.

        This is the operation the pseudocode calls Pq.decrease_priority in Dijkstra
        (slide 18). For A*, use requeue_with_priority instead.

        T_DP time taken & run |E| - |V| times (relaxation loop runs at most |E| times).

        args:
            vertex: The vertex already present in the heap.
            new_priority: The new, smaller priority to assign to the vertex.
        """
        i = self._pos[vertex]
        self._heap[i] = (new_priority, vertex)
        self.heapify_up(i)  # new priority is smaller, so only go up

    def requeue_with_priority(self, vertex: Node, new_priority: int) -> None:
        """Requeue a vertex with a lower f-value, in O(log₂ Q̄) time.

        Corresponds to requeue in Alsedà (slide 87). This is the operation the
        A* pseudocode calls Open.requeue_with_priority (Alsedà, slide 45).
        Functionally identical to decrease_priority and named separately to match
        the A* pseudocode terminology exactly.

        args:
            vertex: The vertex already present in the Open queue.
            new_priority: The new, smaller f=g+h value to assign to the vertex.
        """
        self.decrease_priority(vertex, new_priority)


# ---------------------------------------------------------------------------
# Path reconstruction and display (generic across Dijkstra and A*)
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

    # If target is unreachable, its parent chain hits None (never relaxed) before
    # reaching source, so the loop exits here instead of appending None.
    while current is not None:
        path.append(current)
        if current == source:
            break
        current = parent[current]

    # Catches that unreachable case: path[-1] is target, not source.
    if not path or path[-1] != source:
        return []

    path.reverse()
    return path


def print_graph_size(graph: Graph) -> None:
    """Print the number of vertices and edges in the graph.

    args:
        graph: A directed, weighted graph represented as an adjacency list.
    """
    num_vertices = len(graph)
    num_edges = sum(len(adjacency) for adjacency in graph.values())
    print(f"Graph size: |V| = {num_vertices}, |E| = {num_edges}")


def print_distances(
    graph: Graph,
    dist: Dict[Node, int],
    show_unreachable: bool = True,
    source: Optional[Node] = None,
    dist_fmt: Optional[Callable[[int], str]] = None,
) -> None:
    """Print the shortest distance from the source to every node in the graph.

    args:
        graph: A directed, weighted graph represented as an adjacency list.
        dist: A mapping from each node to its shortest distance from the source.
        show_unreachable: Whether to also print nodes still at distance INF.
        source: When provided, the header names the source node explicitly.
        dist_fmt: Optional callable to format distance values (e.g. seconds_to_hms).
            When omitted, raw integers are printed.
    """
    nodes = list(graph.keys())
    width = max(len(n) for n in nodes)
    label = source if source is not None else "source"
    print(f"\nShortest distances from {label}:")
    for node in nodes:
        value = dist[node]
        if value == INF and not show_unreachable:
            continue
        shown: object = (
            "inf" if value == INF else (dist_fmt(value) if dist_fmt else value)
        )
        print(f"- {node:<{width}} : {shown}")


def print_path_summary(
    source: Node,
    target: Node,
    path: List[Node],
    dist: Dict[Node, int],
    dist_fmt: Optional[Callable[[int], str]] = None,
) -> None:
    """Print the rebuilt path from source to target and weight.

    args:
        source: The starting node.
        target: The destination node.
        path: The rebuilt path from source to target, or an empty list if none.
        dist: A mapping from each node to its shortest distance from the source.
        dist_fmt: Optional callable to format the total distance (e.g. seconds_to_hms).
            When omitted, the raw integer is printed.
    """
    if path:
        print(f"\nShortest path from {source} to {target}:")
        print("  ", " -> ".join(path))
        total = dist[target]
        shown_total: object = (
            "inf" if total == INF else (dist_fmt(total) if dist_fmt else total)
        )
        print(f"Optimum weight: {shown_total}")
    else:
        print(f"\nNo path found from {source} to {target}.")
