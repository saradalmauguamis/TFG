"""h_bcn: a Barcelona region/bridge-aware admissible heuristic for a_star.py.

Unlike h_geo (straight-line distance / v_max, shortest_paths_algorithms/a_star/heuristics/h_geo.py),
h_bcn(node, target) exploits the network's actual Center/Branch topology
(shortest_paths_algorithms/barcelona_division.py): once node and target are reduced to
platforms, the true cost between them only ever needs h_geo across the dense
Center, since crossing into or out of a branch must go through that branch's
single bridge platform.

node/target may be a platform (1.*) or an entrance (E.*); h_bcn first reduces
both to the platform(s) they connect to via a directed pathway edge (plat_from
for node, plat_to for target), adding the fixed 60s pathway cost
(entry_cost) for whichever end is an entrance, then takes the cheapest
h_regions_cases estimate across every (node-side platform, target-side platform)
pair -- this preserves admissibility since h_regions_cases(p, q) is itself an
admissible estimate for every candidate pair, so the minimum over all pairs
can never exceed the true cost via whichever pair the optimal path actually uses.

Depends on shortest_paths_algorithms/barcelona_division.py (classify, compute_bridge,
Branches, Bridges) for the region split, data_validation/gtfs_utils.py
(build_directed_entrance_edges, invert_entries) for the plat_to/plat_from
lookups, and heuristics/h_geo.py's h_geo for the Center-crossing estimate.

depth_from_bridge/depth_to_bridge look up a stop_id directly in a flat
precalculated_depth_from/precalculated_depth_to table (built once by
build_depth_tables below) rather than nesting by branch: every platform
stop_id is already globally unique, so nesting by branch would only add an
unneeded indirection at lookup time.
"""

from __future__ import annotations

import sys
from functools import partial
from pathlib import Path
from typing import Dict, Set, Tuple

_PROJECT_ROOT = str(Path(__file__).resolve().parents[3])
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from data_validation.gtfs_utils import (  # noqa: E402
    build_directed_entrance_edges,
    invert_entries,
)
from shortest_paths_algorithms.algorithms_utils import INF, Graph, Node  # noqa: E402
from shortest_paths_algorithms.barcelona_division import (  # noqa: E402
    Branches,
    Bridges,
    classify,
    compute_bridge,
)
from shortest_paths_algorithms.a_star.a_star_utils import Heuristic  # noqa: E402
from shortest_paths_algorithms.a_star.heuristics.h_geo import Coord, h_geo  # noqa: E402

# entrance stop_id -> the platform stop_id(s) reachable via a directed pathway
# edge in that specific direction (see plat_to/plat_from below).
EntranceToPlatforms = Dict[str, Set[str]]

# platform stop_id -> precalculated depth, see depth_from_bridge/depth_to_bridge
# and build_depth_tables below.
DepthTable = Dict[str, int]


def plat_to(node: Node, entrance_plat_to: EntranceToPlatforms) -> Set[str]:
    """Return the platforms with a directed pathway arrow into node (1.x --> node).

    args:
        node: Platform or entrance stop_id.
        entrance_plat_to: Mapping from entrance stop_id to the platform
            stop_ids with a directed pathway edge into that entrance, i.e.
            invert_entries(platform_to_entrance) from
            build_directed_entrance_edges.

    returns:
        {node} if node is a platform; otherwise the platforms with an arrow
        into node (possibly empty, if node is an entrance no platform points to).
    """
    if not node.startswith("E."):
        return {node}
    return entrance_plat_to.get(node, set())


def plat_from(node: Node, entrance_plat_from: EntranceToPlatforms) -> Set[str]:
    """Return the platforms node has a directed pathway arrow into (node --> 1.x).

    args:
        node: Platform or entrance stop_id.
        entrance_plat_from: Mapping from entrance stop_id to the platform
            stop_ids that entrance has a directed pathway edge into, i.e.
            invert_entries(entrance_to_platform) from
            build_directed_entrance_edges.

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


def depth_from_bridge(node: str, precalculated_depth_from: DepthTable) -> int:
    """Return the precalculated cost of the bridge --> node path within its branch.

    args:
        node: Platform stop_id belonging to a branch (see barcelona_division.find_branch).
        precalculated_depth_from: platform stop_id -> bridge --> node cost,
            from build_depth_tables.

    returns:
        The precalculated bridge --> node cost.
    """
    return precalculated_depth_from[node]


def depth_to_bridge(node: str, precalculated_depth_to: DepthTable) -> int:
    """Return the precalculated cost of the node --> bridge path within its branch.

    args:
        node: Platform stop_id belonging to a branch (see barcelona_division.find_branch).
        precalculated_depth_to: platform stop_id -> node --> bridge cost,
            from build_depth_tables.

    returns:
        The precalculated node --> bridge cost.
    """
    return precalculated_depth_to[node]


def build_depth_tables(graph: Graph) -> Tuple[DepthTable, DepthTable]:
    """Compute depth_from_bridge/depth_to_bridge for every branch platform.

    Each Branches[branch] list is already ordered outside --> inside (outer
    end first, bridge-adjacent stop last, see barcelona_division.py), so
    prepending the bridge and reversing gives the bridge-outward chain
    [bridge, ..., outer end]. Since every branch is a simple chain (verified
    against the real graph: every stop has exactly one in-branch predecessor
    and successor, endpoints have one), a single walk along that chain,
    accumulating the forward edge weight for depth_from_bridge and the
    reverse edge weight for depth_to_bridge at each step, gives the exact
    (not just admissible-lower-bound) cost -- no shortest-path search
    (Dijkstra/BFS) needed, since there is only ever one possible path.

    args:
        graph: The real subway graph, as returned by build_graph_from_weights.

    returns:
        (precalculated_depth_from, precalculated_depth_to), each mapping
        every platform stop_id in every branch to its depth; Center
        platforms and bridges are absent from both, since h_regions_cases
        only calls depth_from_bridge/depth_to_bridge on branch platforms.
    """
    precalculated_depth_from: DepthTable = {}
    precalculated_depth_to: DepthTable = {}

    for branch_name, outer_to_bridge_stops in Branches.items():
        (bridge,) = Bridges[branch_name]
        chain = [bridge, *reversed(outer_to_bridge_stops)]  # bridge, ..., outer end

        cumulative_from = 0
        cumulative_to = 0
        for prev, curr in zip(chain, chain[1:]):
            cumulative_from += graph[prev][curr]
            precalculated_depth_from[curr] = cumulative_from
            cumulative_to += graph[curr][prev]
            precalculated_depth_to[curr] = cumulative_to

    return precalculated_depth_from, precalculated_depth_to


def h_regions_cases(
    p: str,
    q: str,
    coords: Dict[Node, Coord],
    v_max: float,
    precalculated_depth_from: DepthTable,
    precalculated_depth_to: DepthTable,
) -> int:
    """Return the admissible Center/Branch-aware estimate from platform p to platform q.

    By construction p and q are platforms: p is a platform reachable from the
    heuristic's node, q a platform leading to its target. Dispatches on
    classify(p, q) (shortest_paths_algorithms/barcelona_division.py):
      CC - both in the Center: direct h_geo(p, q).
      SB - same branch: p and q sit along the same single-path stub off their
        bridge, so the direct cost is just the difference in depth, in
        whichever direction q lies relative to p.
      CB - Center --> Branch: cross the Center to q's bridge (h_geo, still
        admissible), then the exact bridge --> q cost within the branch.
      BC - Branch --> Center: exact p --> bridge cost within the branch, then
        cross the Center to q (h_geo).
      DB - different branches: exact p --> bridge(p), cross the Center between
        the two bridges (h_geo), then exact bridge(q) --> q.

    args:
        p: Platform stop_id reachable from the heuristic's node.
        q: Platform stop_id leading to the heuristic's target.
        coords: Mapping from node to its (lat, lon) coordinates, for h_geo.
        v_max: Fastest implied speed (m/s) across any edge, for h_geo.
        precalculated_depth_from: platform stop_id -> bridge --> node cost.
        precalculated_depth_to: platform stop_id -> node --> bridge cost.

    returns:
        An admissible lower bound on the true cost from p to q.
    """
    case = classify(p, q)

    if case == "CC":
        return h_geo(p, q, coords, v_max)

    if case == "SB":
        depth_from_p = depth_from_bridge(p, precalculated_depth_from)
        depth_from_q = depth_from_bridge(q, precalculated_depth_from)
        if depth_from_p < depth_from_q:
            # q is further from the bridge than p: p must go outward, away from the Center.
            return depth_from_q - depth_from_p
        # q is at least as close to the bridge as p: p must go inward, toward the Center.
        return depth_to_bridge(p, precalculated_depth_to) - depth_to_bridge(
            q, precalculated_depth_to
        )

    if case == "CB":
        return h_geo(p, compute_bridge(q), coords, v_max) + depth_from_bridge(
            q, precalculated_depth_from
        )

    if case == "BC":
        return depth_to_bridge(p, precalculated_depth_to) + h_geo(
            compute_bridge(p), q, coords, v_max
        )

    # case == "DB": must leave p's branch through its bridge, cross the Center to
    # q's branch's bridge, then go from that bridge into q's branch to reach q.
    return (
        depth_to_bridge(p, precalculated_depth_to)
        + h_geo(compute_bridge(p), compute_bridge(q), coords, v_max)
        + depth_from_bridge(q, precalculated_depth_from)
    )


def h_bcn(
    node: Node,
    target: Node,
    entrance_plat_to: EntranceToPlatforms,
    entrance_plat_from: EntranceToPlatforms,
    coords: Dict[Node, Coord],
    v_max: float,
    precalculated_depth_from: DepthTable,
    precalculated_depth_to: DepthTable,
) -> int:
    """Return the admissible h_bcn estimate of the cheapest path from node to target.

    args:
        node: The node to estimate the remaining cost from (platform or entrance).
        target: The target node (platform or entrance).
        entrance_plat_to: Mapping from entrance stop_id to the platforms with a
            directed pathway edge into that entrance, see plat_to.
        entrance_plat_from: Mapping from entrance stop_id to the platforms that
            entrance has a directed pathway edge into, see plat_from.
        coords: Mapping from node to its (lat, lon) coordinates, for h_geo.
        v_max: Fastest implied speed (m/s) across any edge, for h_geo.
        precalculated_depth_from: platform stop_id -> bridge --> node cost.
        precalculated_depth_to: platform stop_id -> node --> bridge cost.

    returns:
        0 if node == target (needed for admissibility); INF if target is
        unreachable (no platform points into it) or node leads nowhere (no
        platform it points into); otherwise entry_cost(node) + the cheapest
        h_regions_cases estimate across every (node-side platform, target-side
        platform) pair + entry_cost(target).
    """
    target_platforms: Set[str]
    node_platforms: Set[str]
    h_aux: int

    if node == target:
        return 0

    target_platforms = plat_to(target, entrance_plat_to)
    if not target_platforms:
        return INF

    node_platforms = plat_from(node, entrance_plat_from)
    if not node_platforms:
        return INF

    h_aux = min(
        h_regions_cases(
            p, q, coords, v_max, precalculated_depth_from, precalculated_depth_to
        )
        for p in node_platforms
        for q in target_platforms
    )
    return entry_cost(node) + h_aux + entry_cost(target)


def build_h_bcn(
    pathway_ids: Set[str],
    coords: Dict[Node, Coord],
    v_max: float,
    precalculated_depth_from: DepthTable,
    precalculated_depth_to: DepthTable,
) -> Heuristic:
    """Bind pathway/region lookups into h_bcn, producing a plain Heuristic(node, target).

    args:
        pathway_ids: Pathway IDs to parse into the plat_to/plat_from lookups,
            e.g. load_pathway_ids(PATHWAYS_FILE).
        coords: Mapping from node to its (lat, lon) coordinates, for h_geo.
        v_max: Fastest implied speed (m/s) across any edge, for h_geo.
        precalculated_depth_from: platform stop_id -> bridge --> node cost.
        precalculated_depth_to: platform stop_id -> node --> bridge cost.

    returns:
        h_bcn with every lookup pre-bound, matching
        Heuristic = Callable[[Node, Node], int].
    """
    platform_to_entrance, entrance_to_platform = build_directed_entrance_edges(
        pathway_ids
    )
    entrance_plat_to = invert_entries(platform_to_entrance)
    entrance_plat_from = invert_entries(entrance_to_platform)
    return partial(
        h_bcn,
        entrance_plat_to=entrance_plat_to,
        entrance_plat_from=entrance_plat_from,
        coords=coords,
        v_max=v_max,
        precalculated_depth_from=precalculated_depth_from,
        precalculated_depth_to=precalculated_depth_to,
    )
