"""Shared graph types, binary heap, and display utilities used by Dijkstra and A*."""

from __future__ import annotations
from typing import Callable, Dict, List, NamedTuple, Optional, Set, Tuple

from data_validation.gtfs_utils import (
    format_stop_label,
    label_entrance_by_platform,
    read_dict_rows,
)

Node = str
Weight = int
Graph = Dict[Node, Dict[Node, Weight]]
NodeFmt = Callable[[Node], str]  # labels a node, e.g. stop name and line via stop_label
INF = (
    10**18
)  # int equivalent of float('inf'); keeps dist/g arithmetic and equality in pure int


# ---------------------------------------------------------------------------
# Graph construction
# ---------------------------------------------------------------------------


def build_graph_from_weights(file_path: str) -> Graph:
    """Build a directed, weighted graph from a GTFS-style weights file.

    Shared by any script running against the real subway graph rather than a toy example.

    args:
        file_path: Path to a CSV with from_stop_id, to_stop_id, weight_seconds columns.

    returns:
        A graph represented as an adjacency list with weights, including
        sink-only nodes (no outgoing edges) so every stop_id is a key.
    """
    graph: Graph = {}
    for row in read_dict_rows(file_path):
        from_stop_id = row["from_stop_id"]
        to_stop_id = row["to_stop_id"]
        weight = int(row["weight_seconds"])
        graph.setdefault(from_stop_id, {})[to_stop_id] = weight
        graph.setdefault(to_stop_id, {})
    return graph


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


# ---------------------------------------------------------------------------
# Platform-to-platform reports (generic across dijkstra_report.txt and
# a_star_report.txt: cut_dijkstra and a_star both stop as soon as target is
# extracted, so both fit the same row shape via the ReportRunner they're
# wrapped into)
# ---------------------------------------------------------------------------


def na_or(value: object, fmt: str = "{}") -> str:
    """Return "NA" for a None value, otherwise the formatted value.

    args:
        value: The value to format, or None.
        fmt: A str.format template applied to value when it is not None.

    returns:
        "NA" if value is None, otherwise fmt.format(value).
    """
    return "NA" if value is None else fmt.format(value)


def collect_platform_pairs(graph: Graph) -> List[Tuple[Node, Node]]:
    """Return every directed pair of distinct platform vertices in the graph.

    args:
        graph: A directed, weighted graph (build_graph_from_weights output),
            keyed by every stop_id, including platforms (stop_ids starting with "1.").

    returns:
        Sorted list of (source, target) pairs with source != target, both platforms.
    """
    platforms = sorted(node for node in graph if node.startswith("1."))
    return [
        (source, target)
        for source in platforms
        for target in platforms
        if source != target
    ]


class ReportRow(NamedTuple):
    """One directed platform-to-platform route and its shortest-path outcome.

    Shared row shape for dijkstra_report.txt (cut_dijkstra) and
    a_star_report.txt (a_star): iterations means cut_iterations for the
    former and a_star_iterations for the latter -- report_fieldnames and
    report_row_to_csv_dict take the actual column name as a parameter so
    each report's output file still shows its own algorithm-specific label.
    """

    source_id: Node
    target_id: Node
    source_name: str
    target_name: str
    iterations: int
    path_vertices: Optional[int]
    optimum_weight: Optional[int]
    proportion: Optional[float]
    path: List[Node]


# Runs one search from source to target, returning (dist, parent, iterations):
# a thin wrapper around cut_dijkstra (dropping its 4th, `expanded` value) or
# around a_star (with its heuristic already bound), so compute_report_row
# doesn't need to know which algorithm it's calling.
ReportRunner = Callable[
    [Graph, Node, Node], Tuple[Dict[Node, int], Dict[Node, Optional[Node]], int]
]


def compute_report_row(
    graph: Graph, source: Node, target: Node, node_fmt: NodeFmt, runner: ReportRunner
) -> ReportRow:
    """Run a shortest-path search for one platform pair and build its ReportRow.

    args:
        graph: A directed, weighted graph.
        source: Platform stop_id to start from.
        target: Platform stop_id to reach.
        node_fmt: Callable to label a node (stop name and line).
        runner: Callable running one search from source to target, see
            ReportRunner above.

    returns:
        The ReportRow for this (source, target) pair.
    """
    dist, parent, iterations = runner(graph, source, target)
    path = rebuild_path(parent, source, target)

    path_vertices: Optional[int] = None
    optimum_weight: Optional[int] = None
    proportion: Optional[float] = None
    if path:
        path_vertices = len(path)
        optimum_weight = dist[target]
        proportion = path_vertices / iterations

    return ReportRow(
        source_id=source,
        target_id=target,
        source_name=node_fmt(source),
        target_name=node_fmt(target),
        iterations=iterations,
        path_vertices=path_vertices,
        optimum_weight=optimum_weight,
        proportion=proportion,
        path=path,
    )


def report_fieldnames(iterations_label: str) -> List[str]:
    """Return a report's CSV column order, naming the iterations column.

    args:
        iterations_label: Column name for the iterations count, e.g.
            "cut_iterations" or "a_star_iterations".

    returns:
        Column names for write_rows, in report column order.
    """
    return [
        "source_name",
        "target_name",
        "proportion",
        "source_id",
        "target_id",
        iterations_label,
        "path_vertices",
        "optimum_weight",
        "path",
    ]


def report_row_to_csv_dict(row: ReportRow, iterations_label: str) -> Dict[str, str]:
    """Convert one ReportRow into the string dict write_rows expects.

    args:
        row: A single report row.
        iterations_label: Column name for row.iterations, e.g.
            "cut_iterations" or "a_star_iterations" (must match the label
            passed to report_fieldnames for the same report).

    returns:
        Dict keyed by report_fieldnames(iterations_label), "NA" standing in
        for every missing value.
    """
    path_str = "NA" if not row.path else " -> ".join(row.path)
    return {
        "source_name": row.source_name,
        "target_name": row.target_name,
        "proportion": na_or(row.proportion, "{:.5f}"),
        "source_id": row.source_id,
        "target_id": row.target_id,
        iterations_label: str(row.iterations),
        "path_vertices": na_or(row.path_vertices),
        "optimum_weight": na_or(row.optimum_weight),
        "path": path_str,
    }


def stop_label(
    node: Node,
    stop_names: Dict[str, str],
    stop_to_lines: Dict[str, List[str]],
    entrance_to_platform: Optional[Dict[str, Set[str]]] = None,
) -> str:
    """Combine a stop's name and line(s) into one label, via format_stop_label.

    Shared between Dijkstra and A* (both bind these mappings with
    `functools.partial` to get a plain node_fmt callable for the print helpers).

    args:
        node: The stop_id to label.
        stop_names: Mapping from stop_id to stop_name, from `load_stop_names`.
        stop_to_lines: Mapping from stop_id to line names, from `build_stop_to_lines`.
        entrance_to_platform: Optional mapping from entrance stop_id to the
            platform(s) it connects to, from `build_directed_entrance_edges`.
            When given, an E.* node is labeled via `label_entrance_by_platform`
            (its own stop_name is uninformative on its own); otherwise it falls
            back to its plain stop_name, like any other node without a line.

    returns:
        "{line1}-{line2}-...-{stop_name}" for a platform on a line; the
        connected platform's label for an entrance (with entrance_to_platform);
        otherwise the plain stop_name, or "(no name)" if node has no entry.
    """
    if entrance_to_platform is not None and node in entrance_to_platform:
        return label_entrance_by_platform(
            node, entrance_to_platform, stop_names, stop_to_lines
        )
    return format_stop_label(node, stop_names.get(node, "(no name)"), stop_to_lines)


def format_node_label(node: Node, node_fmt: Optional[NodeFmt], width: int = 0) -> str:
    """Return a space-prefixed, parenthesized label for a node, or "" without node_fmt.

    Shared by every print helper below so a node's label (e.g. stop name and
    line) lines up in its own column wherever it's shown, instead of each
    caller re-deriving the same " (label)" formatting.

    args:
        node: The node to label.
        node_fmt: Optional callable producing the label text (e.g. stop name
            and line, via `format_stop_label`). When None, returns "".
        width: Minimum width to left-pad the label text to, for column alignment.

    returns:
        " (label)" (padded to width) when node_fmt is given, otherwise "".
    """
    if not node_fmt:
        return ""
    return f" ({node_fmt(node):<{width}})"


def print_header(
    source: Node,
    target: Optional[Node] = None,
    width: int = 50,
    node_fmt: Optional[NodeFmt] = None,
) -> None:
    """Print a large banner announcing the run's source (and target, if given).

    args:
        source: The starting node for the run.
        target: When provided, the banner also names the destination node.
        width: Minimum length of the "=" separator line; widened to fit the
            title when the (possibly labeled) title is longer.
        node_fmt: Optional callable to label a node (e.g. stop name and line,
            via `format_stop_label`). When omitted, only raw node ids are shown.
    """
    title: str
    line: str

    title = f"From {source}{format_node_label(source, node_fmt)}"
    if target is not None:
        title += f" --> to {target}{format_node_label(target, node_fmt)}"
    line = "=" * (max(width, len(title)) + 2)
    print(f"{line}\n{title}\n{line}\n\n")


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
    label: str = "dijkstra",
    expanded: Optional[Dict[Node, bool]] = None,
    node_fmt: Optional[NodeFmt] = None,
) -> None:
    """Print the distance (and stop label, if node_fmt is given) from the source
    to every node in the graph, ordered by ascending distance found.

    args:
        graph: A directed, weighted graph represented as an adjacency list.
        dist: A mapping from each node to its distance from the source.
        show_unreachable: Whether to also print nodes still at distance INF.
        source: When provided, the header names the source node explicitly.
        dist_fmt: Optional callable to format distance values (e.g. seconds_to_hms).
            When omitted, raw integers are printed.
        label: "dijkstra" for a full run, where every reachable node's distance is
            final. "cut" for cut_dijkstra, where the search stops as soon as the
            target is extracted, so some reached nodes were only relaxed and never
            extracted: by the convergence theorem their distance isn't guaranteed
            optimal yet, unlike already-extracted ones.
        expanded: Required when label="cut". Marks, per node, whether it was
            extracted before the search stopped (and so has an optimal distance).
        node_fmt: Optional callable to label a node (e.g. stop name and line,
            via `format_stop_label`). When omitted, only the raw node id is shown.
    """
    source_label: object
    header_suffix: str
    suffix: str
    rows: List[Tuple[int, Node]]
    id_width: int
    label_width: int

    source_label = source if source is not None else "source"
    header_suffix = format_node_label(source, node_fmt) if source is not None else ""
    suffix = " (format: HH:MM:SS)" if dist_fmt else ""
    if label == "cut":
        print(
            f"\nDistances found from {source_label}{header_suffix} before extracting"
            f" the target (cut Dijkstra, not all optimal yet):{suffix}"
        )
    else:
        print(f"\nOptimum weight from {source_label}{header_suffix}:{suffix}")

    rows = [
        (dist[node], node) for node in graph if dist[node] != INF or show_unreachable
    ]
    rows.sort(key=lambda row: row[0])
    if not rows:
        return

    id_width = max(len(node) for _, node in rows)
    label_width = (
        max((len(node_fmt(node)) for _, node in rows), default=0) if node_fmt else 0
    )

    for value, node in rows:
        shown: object = (
            "inf" if value == INF else (dist_fmt(value) if dist_fmt else value)
        )
        status = ""
        if (
            label == "cut" and expanded is not None
        ):  # last condition = if expanded has been provided
            status = (
                " (extracted --> optimum)"
                if expanded[node]
                else " "  # relaxed only --> not guaranteed optimum
            )
        node_label = format_node_label(node, node_fmt, label_width)
        print(f"- {node:<{id_width}}{node_label} : {shown}{status}")


def print_path_summary(
    source: Node,
    target: Node,
    path: List[Node],
    dist: Dict[Node, int],
    dist_fmt: Optional[Callable[[int], str]] = None,
    node_fmt: Optional[NodeFmt] = None,
) -> None:
    """Print the rebuilt path from source to target and weight.

    args:
        source: The starting node.
        target: The destination node.
        path: The rebuilt path from source to target, or an empty list if none.
        dist: A mapping from each node to its shortest distance from the source.
        dist_fmt: Optional callable to format the total distance (e.g. seconds_to_hms).
            When omitted, the raw integer is printed.
        node_fmt: Optional callable to label a node (e.g. stop name and line,
            via `format_stop_label`). When provided, each node in the path is
            printed on its own line for readability.
    """
    source_suffix = format_node_label(source, node_fmt)
    target_suffix = format_node_label(target, node_fmt)
    if path:
        print(
            f"\nShortest path (not necessarily unique) from {source}{source_suffix}"
            f" to {target}{target_suffix}:"
        )
        if node_fmt:
            print(
                "  "
                + "\n  -> ".join(
                    f"{node}{format_node_label(node, node_fmt)}" for node in path
                )
            )
        else:
            print("  ", " -> ".join(path))
        total = dist[target]
        shown_total: object = (
            "inf" if total == INF else (dist_fmt(total) if dist_fmt else total)
        )
        suffix = " (format: HH:MM:SS)" if dist_fmt else ""
        print(f"Optimum weight: {shown_total}{suffix}")
    else:
        print(
            f"\nNo path found from {source}{source_suffix} to {target}{target_suffix}."
        )
