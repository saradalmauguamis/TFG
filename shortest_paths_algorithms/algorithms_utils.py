"""Shared graph types, binary heap, and display utilities used by Dijkstra and A*."""

from __future__ import annotations
from typing import Callable, Dict, List, Optional, Set, Tuple

from data_validation.gtfs_utils import (
    format_stop_label,
    invert_entries,
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
# Graph mode: which edges a search actually runs over.
# ---------------------------------------------------------------------------
# FULL_GRAPH keeps every edge (SW/TF/PW), so entrances (E.*) are reachable
# directly, exactly like WEIGHTS_FILE itself. WITHOUT_ENTRANCES_GRAPH drops PW
# (entrance<->platform pathway) rows, isolating every entrance, so a search must
# then be run against platform endpoints only, see resolve_platform_candidates/
# restore_entrance_endpoints below for accepting entrance SOURCE/TARGET anyway.
GraphMode = str
FULL_GRAPH: GraphMode = "full_graph"
WITHOUT_ENTRANCES_GRAPH: GraphMode = "without_entrances_graph"
_EXCLUDED_TYPES_BY_MODE: Dict[GraphMode, Set[str]] = {
    FULL_GRAPH: frozenset(),
    WITHOUT_ENTRANCES_GRAPH: frozenset({"PW"}),
}
# Short label per mode, for output filenames (dijkstra.py, a_star.py, and the
# reports/ scripts all name their output after whichever mode produced it).
GRAPH_MODE_LABEL: Dict[GraphMode, str] = {
    FULL_GRAPH: "full",
    WITHOUT_ENTRANCES_GRAPH: "no_pw",
}


def build_graph_from_weights(
    file_path: str, graph_mode: GraphMode = FULL_GRAPH
) -> Graph:
    """Build a directed, weighted graph from a GTFS-style weights file.

    Shared by any script running against the real subway graph rather than a toy example.

    args:
        file_path: Path to a CSV with from_stop_id, to_stop_id, weight_seconds columns.
        graph_mode: FULL_GRAPH or WITHOUT_ENTRANCES_GRAPH (see module docstring
            above); rows whose "type" column falls in that mode's excluded set
            are skipped. Ignored for files with no "type" column, e.g.
            SUBWAY_WEIGHTS_FILE.

    returns:
        A graph represented as an adjacency list with weights, including
        sink-only nodes (no outgoing edges) so every stop_id is a key.
    """
    graph: Graph = {}
    excluded_types = _EXCLUDED_TYPES_BY_MODE[graph_mode]
    for row in read_dict_rows(file_path):
        if row.get("type") in excluded_types:
            continue
        from_stop_id = row["from_stop_id"]
        to_stop_id = row["to_stop_id"]
        weight = int(row["weight_seconds"])
        graph.setdefault(from_stop_id, {})[to_stop_id] = weight
        graph.setdefault(to_stop_id, {})
    return graph


def build_graph_and_coverage_from_weights(
    file_path: str,
) -> Tuple[Dict[str, Set[str]], Set[str]]:
    """Build platform-entrance coverage information from a weights file's PW rows.

    Same output shape as data_validation.gtfs_utils.build_graph_and_coverage, but
    reads WEIGHTS_FILE's own "type" column directly instead of re-parsing
    PATHWAYS_FILE's "PW.a_b" pathway_id strings: weights.txt already carries every
    PW edge as a plain (from_stop_id, to_stop_id) row, so there is no need for a
    second file or a second parsing step to get the same information.

    args:
        file_path: Path to WEIGHTS_FILE (from_stop_id, to_stop_id, weight_seconds,
            type columns).

    returns:
        Tuple containing two elements:

        - `platform_to_entries` (Dict[str, Set[str]]): mapping from a platform stop ID
            to the set of entrance stop IDs (IDs starting with `E.`) that connect to that
            platform. Only platform<->entrance PW edges are recorded here.

        - `covered_platforms` (Set[str]): set of platform stop IDs that have at least
            one connected entrance (i.e., the keys of `platform_to_entries`).
    """
    platform_to_entries: Dict[str, Set[str]] = {}
    covered_platforms: Set[str] = set()

    for row in read_dict_rows(file_path):
        if row.get("type") != "PW":
            continue
        from_stop_id = row["from_stop_id"]
        to_stop_id = row["to_stop_id"]

        if from_stop_id.startswith("1.") and to_stop_id.startswith("E."):
            platform_to_entries.setdefault(from_stop_id, set()).add(to_stop_id)
            covered_platforms.add(from_stop_id)
        elif to_stop_id.startswith("1.") and from_stop_id.startswith("E."):
            platform_to_entries.setdefault(to_stop_id, set()).add(from_stop_id)
            covered_platforms.add(to_stop_id)

    return platform_to_entries, covered_platforms


def build_directed_entrance_edges_from_weights(
    file_path: str,
) -> Tuple[Dict[str, Set[str]], Dict[str, Set[str]]]:
    """Build directed platform<->entrance edges from a weights file's PW rows.

    Same output shape as data_validation.gtfs_utils.build_directed_entrance_edges,
    but reads WEIGHTS_FILE's own "type" column directly instead of re-parsing
    PATHWAYS_FILE's "PW.a_b" pathway_id strings, for the same reason as
    build_graph_and_coverage_from_weights above.

    args:
        file_path: Path to WEIGHTS_FILE (from_stop_id, to_stop_id, weight_seconds,
            type columns).

    returns:
        Tuple of (platform_to_entrance, entrance_to_platform), both mapping a
        platform stop_id to the set of entrance stop_ids reachable via a PW row
        in that direction only.
    """
    platform_to_entrance: Dict[str, Set[str]] = {}
    entrance_to_platform: Dict[str, Set[str]] = {}

    for row in read_dict_rows(file_path):
        if row.get("type") != "PW":
            continue
        from_stop_id = row["from_stop_id"]
        to_stop_id = row["to_stop_id"]

        if from_stop_id.startswith("1.") and to_stop_id.startswith("E."):
            platform_to_entrance.setdefault(from_stop_id, set()).add(to_stop_id)
        elif from_stop_id.startswith("E.") and to_stop_id.startswith("1."):
            entrance_to_platform.setdefault(to_stop_id, set()).add(from_stop_id)

    return platform_to_entrance, entrance_to_platform


# entrance stop_id -> the platform stop_id(s) reachable via a directed pathway
# edge in that specific direction (see plat_to/plat_from below).
EntranceToPlatforms = Dict[Node, Set[Node]]


def plat_to(node: Node, entrance_plat_to: EntranceToPlatforms) -> Set[Node]:
    """Return the platforms with a directed pathway arrow into node (1.x --> node).

    args:
        node: Platform or entrance stop_id.
        entrance_plat_to: Mapping from entrance stop_id to the platform
            stop_ids with a directed pathway edge into that entrance, i.e.
            invert_entries(platform_to_entrance) from
            build_directed_entrance_edges_from_weights.

    returns:
        {node} if node is a platform; otherwise the platforms with an arrow
        into node (possibly empty, if node is an entrance no platform points to).
    """
    if not node.startswith("E."):
        return {node}
    return entrance_plat_to.get(node, set())


def plat_from(node: Node, entrance_plat_from: EntranceToPlatforms) -> Set[Node]:
    """Return the platforms node has a directed pathway arrow into (node --> 1.x).

    args:
        node: Platform or entrance stop_id.
        entrance_plat_from: Mapping from entrance stop_id to the platform
            stop_ids that entrance has a directed pathway edge into, i.e.
            invert_entries(entrance_to_platform) from
            build_directed_entrance_edges_from_weights.

    returns:
        {node} if node is a platform; otherwise the platforms node has an
        arrow into (possibly empty, if node is an entrance leading nowhere).
    """
    if not node.startswith("E."):
        return {node}
    return entrance_plat_from.get(node, set())


def entry_cost(node: Node) -> int:
    """Return the fixed pathway cost for node, if it is an entrance.

    All pathways have a weight of 60 (data_validation/checks/pathways_checks.py).

    args:
        node: Platform or entrance stop_id.

    returns:
        60 if node is an entrance, otherwise 0.
    """
    return 60 if node.startswith("E.") else 0


def resolve_platform_candidates(
    source: Node,
    target: Node,
    entrance_plat_from: EntranceToPlatforms,
    entrance_plat_to: EntranceToPlatforms,
) -> Tuple[Set[Node], Set[Node], int]:
    """Reduce source/target to candidate platforms for a WITHOUT_ENTRANCES_GRAPH search.

    Only meaningful when running a search on WITHOUT_ENTRANCES_GRAPH: entrances
    are isolated there, so the search itself must run between platforms, then
    have its path endpoints restored (restore_entrance_endpoints) and its
    weight adjusted by the returned entry_total. source/target may each already
    be a platform (returned as-is via plat_from/plat_to) or an entrance
    (reduced to the platform(s) it connects to in that direction). Either set
    coming back empty means that end has no PW edge in that direction, so no
    path exists no matter which candidate is tried, mirroring h_bcn's own INF
    return for the same situation (a_star/heuristics/h_bcn.py). A set with more
    than one candidate (a platform reachable via more than one directed PW edge)
    is returned as-is too: the caller is expected to try every candidate and
    keep whichever is cheapest, exactly like h_bcn takes the min h_regions_cases
    estimate across every (node-side platform, target-side platform) pair.

    args:
        source: The query's original source (platform or entrance).
        target: The query's original target (platform or entrance).
        entrance_plat_from: Mapping from entrance stop_id to the platforms it
            has a directed pathway edge into, see plat_from.
        entrance_plat_to: Mapping from entrance stop_id to the platforms with a
            directed pathway edge into it, see plat_to.

    returns:
        (source_platforms, target_platforms, entry_total): the candidate
        platform(s) for source/target (each possibly empty), and the fixed
        extra weight (0, 60, or 120) for whichever end(s) are actually
        entrances. entry_cost is a flat per-pathway constant, so entry_total
        does not depend on which candidate platform is eventually used.
    """
    return (
        plat_from(source, entrance_plat_from),
        plat_to(target, entrance_plat_to),
        entry_cost(source) + entry_cost(target),
    )


def restore_entrance_endpoints(
    path: List[Node], source: Node, target: Node
) -> List[Node]:
    """Prepend/append the original entrance endpoints onto a platform-only path.

    Counterpart to resolve_platform_candidates: once a search on
    WITHOUT_ENTRANCES_GRAPH finds a platform-to-platform path, this restores
    whichever original endpoint(s) were actually entrances, in the same spirit
    as apply_liceu_entrance_fix's path post-processing, applied after it.

    args:
        path: The rebuilt platform-to-platform path (via rebuild_path), or an
            empty list if none was found.
        source: The query's original source (platform or entrance).
        target: The query's original target (platform or entrance).

    returns:
        `path` unchanged if empty; otherwise `path` with `source` prepended
        and/or `target` appended, whichever differs from the path's current
        matching end (a platform source/target is already its own reduction,
        so nothing is added on that side).
    """
    fixed: List[Node]

    if not path:
        return path
    fixed = list(path)
    if fixed[0] != source:
        fixed.insert(0, source)
    if fixed[-1] != target:
        fixed.append(target)
    return fixed


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
        decrease_priority      —  requeue_with_priority (both use decrease_priority here)
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
        (slide 18) and Open.requeue_with_priority in A* (slide 45); both use this
        single method here.

        T_DP time taken & run |E| - |V| times (relaxation loop runs at most |E| times).

        args:
            vertex: The vertex already present in the heap.
            new_priority: The new, smaller priority to assign to the vertex.
        """
        i = self._pos[vertex]
        self._heap[i] = (new_priority, vertex)
        self.heapify_up(i)  # new priority is smaller, so only go up


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
# Liceu direction fix (generic across Dijkstra and A*)
#
# Liceu (platform 1.325, between Drassanes 1.324 and Catalunya 1.326 on L3) is
# the only stop in Barcelona's subway where changing direction means going
# upstairs to a different street entrance: each of its 3 entrance pairs has
# one member serving only the Drassanes-bound direction and one serving only
# the Catalunya-bound direction, even though both hang off the same platform
# node in the graph. Neither Dijkstra nor A* knows about this, so a computed
# path may end (or start) at the entrance for the wrong direction; this fix
# is a display-only patch applied to the already-rebuilt path afterwards.
# Since both entrances in a pair sit a few meters apart off the same platform,
# the walking time between them is treated as equal, so the previously
# computed weight (from/to the original, wrong-direction entrance) is still
# reported as-is: only the entrance shown in the path changes, not the weight.
# ---------------------------------------------------------------------------

LICEU_PLATFORM: Node = "1.325"
LICEU_DIRECTION_NEIGHBOR: Dict[Node, int] = {"1.324": 0, "1.326": 1}
LICEU_ENTRANCE_PAIRS: List[Tuple[Node, Node]] = [
    ("E.32511", "E.32501"),
    ("E.1032531", "E.1032521"),
    ("E.32531", "E.32521"),
]
LICEU_ENTRANCE_DIRECTION: Dict[Node, int] = {}
LICEU_ENTRANCE_PAIR: Dict[Node, Node] = {}
for _direction_0_entrance, _direction_1_entrance in LICEU_ENTRANCE_PAIRS:
    LICEU_ENTRANCE_DIRECTION[_direction_0_entrance] = 0
    LICEU_ENTRANCE_DIRECTION[_direction_1_entrance] = 1
    LICEU_ENTRANCE_PAIR[_direction_0_entrance] = _direction_1_entrance
    LICEU_ENTRANCE_PAIR[_direction_1_entrance] = _direction_0_entrance


def _print_liceu_disclaimer(
    original: Node, replacement: Node, role: str, node_fmt: Optional[NodeFmt]
) -> None:
    """Explain why `original` was swapped for `replacement` in the printed path.

    args:
        original: The requested entrance, which only serves the wrong direction.
        replacement: The entrance actually enforced instead.
        role: "enter" (source case) or "exit" (target case), for the message.
        node_fmt: Optional callable to label a node, see `format_node_label`.
    """
    print(
        f"\nNOTE: Liceu is the only stop in Barcelona's subway where changing "
        f"direction means going upstairs to a different street entrance, so "
        f"{original}{format_node_label(original, node_fmt)} only serves the "
        f"opposite direction. You are enforced to {role} through "
        f"{replacement}{format_node_label(replacement, node_fmt)} instead, a "
        f"few meters away; the walking time between the two is treated as "
        f"equal, so the weight reported below is unaffected."
    )


def apply_liceu_entrance_fix(
    path: List[Node], node_fmt: Optional[NodeFmt] = None
) -> List[Node]:
    """Swap a path's Liceu entrance endpoint(s) for the one matching its direction.

    If the target is one of the 6 special entrances, the vertex before it is
    always LICEU_PLATFORM; the vertex before that (1.324 or 1.326) reveals the
    direction the path arrives from, and thus which entrance is actually usable.
    Symmetrically for the source, using the 2nd and 3rd vertices. Both ends are
    checked independently, so a path that's wrong on both ends gets both fixed.
    Prints a disclaimer (see `_print_liceu_disclaimer`) for each swap made.

    args:
        path: The rebuilt path from `rebuild_path`, left untouched if shorter
            than 3 nodes or if neither endpoint is a Liceu special entrance.
        node_fmt: Optional callable to label a node in the disclaimer, e.g.
            stop name and line, via `format_stop_label`.

    returns:
        `path`, with its source and/or target replaced by the entrance
        matching the direction the path actually travels, if needed.
    """
    fixed: List[Node]
    required_direction: Optional[int]
    entrance: Node
    replacement: Node

    if len(path) < 3:
        return path
    fixed = list(path)

    if fixed[-2] == LICEU_PLATFORM:
        required_direction = LICEU_DIRECTION_NEIGHBOR.get(fixed[-3])
        entrance = fixed[-1]
        if required_direction is not None and LICEU_ENTRANCE_DIRECTION.get(
            entrance
        ) not in (None, required_direction):
            replacement = LICEU_ENTRANCE_PAIR[entrance]
            _print_liceu_disclaimer(entrance, replacement, "exit", node_fmt)
            fixed[-1] = replacement

    if fixed[1] == LICEU_PLATFORM:
        required_direction = LICEU_DIRECTION_NEIGHBOR.get(fixed[2])
        entrance = fixed[0]
        if required_direction is not None and LICEU_ENTRANCE_DIRECTION.get(
            entrance
        ) not in (None, required_direction):
            replacement = LICEU_ENTRANCE_PAIR[entrance]
            _print_liceu_disclaimer(entrance, replacement, "enter", node_fmt)
            fixed[0] = replacement

    return fixed


# ---------------------------------------------------------------------------
# Graph-mode query orchestration
# ---------------------------------------------------------------------------


def build_entrance_platform_lookups(
    file_path: str,
) -> Tuple[Dict[Node, Set[Node]], EntranceToPlatforms, EntranceToPlatforms]:
    """Build every entrance/platform lookup a query script needs, from WEIGHTS_FILE.

    Bundles the two build_*_from_weights calls (plus the invert_entries calls
    their directed output needs) that dijkstra.py/a_star.py otherwise both
    repeat: one undirected lookup for node_fmt's entrance labeling, two
    directed ones for resolve_search_endpoints/resolve_platform_candidates.

    args:
        file_path: Path to WEIGHTS_FILE.

    returns:
        (entrance_to_platform, entrance_plat_to, entrance_plat_from):
        entrance_to_platform is the undirected entrance->platform(s) mapping
        stop_label expects; entrance_plat_to/entrance_plat_from are the
        directed mappings plat_to/plat_from expect (see
        resolve_platform_candidates).
    """
    platform_to_entries: Dict[Node, Set[Node]]
    directed_platform_to_entrance: Dict[Node, Set[Node]]
    directed_entrance_to_platform: Dict[Node, Set[Node]]

    platform_to_entries, _ = build_graph_and_coverage_from_weights(file_path)
    directed_platform_to_entrance, directed_entrance_to_platform = (
        build_directed_entrance_edges_from_weights(file_path)
    )
    return (
        invert_entries(platform_to_entries),
        invert_entries(directed_platform_to_entrance),
        invert_entries(directed_entrance_to_platform),
    )


def resolve_search_endpoints(
    graph_mode: GraphMode,
    source: Node,
    target: Node,
    entrance_plat_from: EntranceToPlatforms,
    entrance_plat_to: EntranceToPlatforms,
) -> Tuple[Set[Node], Set[Node], int]:
    """Resolve the platform(s) a search should actually run between.

    FULL_GRAPH runs directly between source/target (no reduction needed,
    entrances are reachable there); WITHOUT_ENTRANCES_GRAPH reduces them via
    resolve_platform_candidates, since entrances are isolated on that graph.

    args:
        graph_mode: FULL_GRAPH or WITHOUT_ENTRANCES_GRAPH.
        source: The query's original source (platform or entrance).
        target: The query's original target (platform or entrance).
        entrance_plat_from: Mapping from entrance stop_id to the platforms it
            has a directed pathway edge into, see plat_from.
        entrance_plat_to: Mapping from entrance stop_id to the platforms with a
            directed pathway edge into it, see plat_to.

    returns:
        (source_platforms, target_platforms, entry_total), see
        resolve_platform_candidates.
    """
    if graph_mode == WITHOUT_ENTRANCES_GRAPH:
        return resolve_platform_candidates(
            source, target, entrance_plat_from, entrance_plat_to
        )
    return {source}, {target}, 0


def report_missing_platform_candidates(
    source_platforms: Set[Node], target_platforms: Set[Node], source: Node, target: Node
) -> bool:
    """Print a "no path possible" message if either candidate set is empty.

    args:
        source_platforms: Candidate source platform(s), from resolve_search_endpoints.
        target_platforms: Candidate target platform(s), from resolve_search_endpoints.
        source: The query's original source (platform or entrance), for the message.
        target: The query's original target (platform or entrance), for the message.

    returns:
        True if either set is empty (message already printed, caller should
        bail out of its search without running anything); False otherwise.
    """
    if source_platforms and target_platforms:
        return False
    print(
        f"\nNo path possible: {source} or {target} has no pathway in the"
        " needed direction."
    )
    return True


def finalize_path(
    graph_mode: GraphMode,
    parent: Dict[Node, Optional[Node]],
    algo_source: Node,
    algo_target: Node,
    source: Node,
    target: Node,
    node_fmt: Optional[NodeFmt] = None,
) -> List[Node]:
    """Rebuild and fully post-process a search's path, for either graph mode.

    Combines rebuild_path, apply_liceu_entrance_fix, and (on
    WITHOUT_ENTRANCES_GRAPH) restore_entrance_endpoints into the single call
    every query script needs after its search loop finds the best candidate pair.

    args:
        graph_mode: FULL_GRAPH or WITHOUT_ENTRANCES_GRAPH.
        parent: Parent links from whichever search found algo_source/algo_target.
        algo_source: The platform (or, on FULL_GRAPH, entrance) the search
            actually ran from.
        algo_target: The platform (or, on FULL_GRAPH, entrance) the search
            actually ran to.
        source: The query's original source (platform or entrance).
        target: The query's original target (platform or entrance).
        node_fmt: Optional callable to label a node in apply_liceu_entrance_fix's
            disclaimer, see its own docstring.

    returns:
        The fully rebuilt and restored path, or an empty list if none was found.
    """
    path = apply_liceu_entrance_fix(
        rebuild_path(parent, algo_source, algo_target), node_fmt
    )
    if graph_mode == WITHOUT_ENTRANCES_GRAPH:
        path = restore_entrance_endpoints(path, source, target)
    return path


def with_adjusted_target_weight(
    dist: Dict[Node, int], target: Node, best_weight: int, entry_total: int
) -> Dict[Node, int]:
    """Return a copy of dist with target's weight adjusted by entry_total.

    On WITHOUT_ENTRANCES_GRAPH, best_weight is the raw platform-to-platform
    weight and entry_total is the fixed PW cost resolve_search_endpoints
    already computed for whichever end(s) are entrances (0 on FULL_GRAPH,
    since entry_total is always 0 there); this bakes that adjustment into a
    dist/g copy so print_path_summary's dist[target] lookup reports the true
    entrance-to-entrance weight without mutating the original dist/g mapping.

    args:
        dist: The winning candidate's dist (Dijkstra) or g (A*) mapping.
        target: The query's original target (platform or entrance): the key
            being adjusted, which may not even be a key of dist (e.g. an
            entrance absent from a WITHOUT_ENTRANCES_GRAPH search's own dist).
        best_weight: The raw weight found between algo_source/algo_target, or
            INF if no path was found.
        entry_total: The fixed extra weight for the actual query's endpoints,
            from resolve_search_endpoints.

    returns:
        A copy of dist with dist[target] = best_weight + entry_total, unless
        best_weight is INF (no path found), in which case dist is copied as-is.
    """
    adjusted = dict(dist)
    if best_weight != INF:
        adjusted[target] = best_weight + entry_total
    return adjusted


SearchFn = Callable[
    [Graph, Node, Node],
    Tuple[Dict[Node, int], Dict[Node, Optional[Node]], int, Dict[Node, bool]],
]


def best_over_candidate_pairs(
    graph: Graph,
    source_platforms: Set[Node],
    target_platforms: Set[Node],
    search: SearchFn,
) -> Tuple[
    Node, Node, Dict[Node, int], Dict[Node, Optional[Node]], int, Dict[Node, bool]
]:
    """Run a target-directed search once per (source, target) candidate pair, keeping the cheapest.

    Shared by any target-directed algorithm (cut_dijkstra or a_star, unlike
    plain dijkstra(); see dijkstra_utils.best_over_source_candidates) that
    stops early at one specific target and so needs a fresh run per (source,
    target) pair, rather than one run per source. a_star.py binds `search` to
    a_star with h/verbose pre-bound via functools.partial; extracted_nodes_graph.py
    binds it to cut_dijkstra with verbose pre-bound the same way.

    args:
        graph: A directed, weighted graph.
        source_platforms: Candidate source platform(s), from resolve_search_endpoints.
        target_platforms: Candidate target platform(s), from resolve_search_endpoints.
        search: Callable(graph, source, target) -> (dist_or_g, parent,
            iterations, expanded), e.g. cut_dijkstra or a_star with their other
            arguments already pre-bound via functools.partial.

    returns:
        (best_source, best_target, dist, parent, iterations, expanded): the
        winning candidate pair and search's own output for that pair.
    """
    best_weight = INF
    best_source: Node = next(iter(source_platforms))
    best_target: Node = next(iter(target_platforms))
    dist: Dict[Node, int] = {}
    parent: Dict[Node, Optional[Node]] = {}
    iterations = 0
    expanded: Dict[Node, bool] = {}
    first_candidate = True

    for candidate_source in source_platforms:
        for candidate_target in target_platforms:
            (
                candidate_dist,
                candidate_parent,
                candidate_iterations,
                candidate_expanded,
            ) = search(graph, candidate_source, candidate_target)
            candidate_weight = candidate_dist[candidate_target]
            if first_candidate or candidate_weight < best_weight:
                best_weight = candidate_weight
                dist, parent, iterations, expanded = (
                    candidate_dist,
                    candidate_parent,
                    candidate_iterations,
                    candidate_expanded,
                )
                best_source, best_target = candidate_source, candidate_target
                first_candidate = False

    return best_source, best_target, dist, parent, iterations, expanded


# ---------------------------------------------------------------------------
# Path and node display (generic across Dijkstra and A*)
# ---------------------------------------------------------------------------


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
            platform(s) it connects to, e.g. invert_entries(platform_to_entries)
            from `build_graph_and_coverage_from_weights`.
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
    graph_mode: Optional[GraphMode] = None,
    width: int = 50,
    node_fmt: Optional[NodeFmt] = None,
) -> None:
    """Print a large banner announcing the run's source (and target, if given).

    args:
        source: The starting node for the run.
        target: When provided, the banner also names the destination node.
        graph_mode: When provided (FULL_GRAPH or WITHOUT_ENTRANCES_GRAPH, see
            module docstring above), printed under the banner so it's clear
            which graph a run's iteration counts/timings belong to.
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
    if graph_mode is not None:
        print(f"Graph mode: {graph_mode}\n")


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
