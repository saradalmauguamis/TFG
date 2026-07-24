"""Region/bridge partition of the Barcelona subway graph, for a zone-aware h_bcn heuristic.

Every stop_id below is in the post-shared-platform-duplication ("artificial")
scheme, matching WEIGHTS_FILE (data_validation/gtfs_utils.py) and
subway_reference.subway_lines.subway_route_names_stop_ids_artificial, since that is the id
scheme the real graph (built via build_graph_from_weights, in
shortest_paths_algorithms/algorithms_utils.py) actually runs on.

- Branches: short stub segments of a line that only reconnect to the rest of
  the network through a single platform (their bridge). Lines without a stub
  (L3, L4, L10N) have no entry here.
- Bridges: for each branch, the single Center platform it reconnects through.
- Regions: "Branches" (as above) plus "Center", every platform stop not in
  any branch.

Every branch is a simple chain (verified against the real graph: every stop
has exactly one in-branch predecessor and successor, except the two ends,
which have one neighbor each, the bridge itself being one such end and not
part of the branch's tuple below), so each Branches[branch] tuple is ordered
outside --> inside: index 0 is the branch's outer end (farthest from the bridge),
the last index is the stop directly adjacent to the bridge. This ordering is
what shortest_paths_algorithms/a_star/heuristics/h_bcn.py's build_depth_tables
walks to compute depth_from_bridge/depth_to_bridge.
"""

from typing import Dict, Optional, Set

from subway_reference.subway_lines import subway_route_names_stop_ids_artificial

Branches = {
    "Branch_L1": ["1.111", "1.112", "1.113", "1.114", "1.115", "1.116"],
    "Branch_L2": ["1.227", "1.226"],
    "Branch_L5": ["1.509", "1.510", "1.511", "1.512", "1.513", "1.514", "1.555"],
    "Branch_L9S": [
        "1.901",
        "1.903",
        "1.904",
        "1.905",
        "1.906",
        "1.907",
        "1.909",
        "1.910",
        "1.911",
        "1.912",
        "1.913",
    ],
    "Branch_L9N": ["1.945", "1.944", "1.943"],
    "Branch_L10S": [
        "1.951",
        "1.952",
        "1.953",
        "1.954",
        "1.956",
        "1.957",
        "1.958",
        "1.959",
    ],
    "Branch_L11": ["1.1140", "1.1139", "1.1138", "1.1137"],
    "Branch_FM": ["1.9902"],
}

Bridges = {
    "Branch_L1": {"1.117"},
    "Branch_L2": {"1.225"},
    "Branch_L5": {"1.515"},
    "Branch_L9S": {"1.9140"},
    "Branch_L9N": {"1.942"},
    "Branch_L10S": {"1.9141"},
    "Branch_L11": {"1.1136"},
    "Branch_FM": {"1.9901"},
}

Platforms_Set = {
    stop_id
    for stop_ids in subway_route_names_stop_ids_artificial.values()
    for stop_id in stop_ids
}
_branch_vertices = {v for branch in Branches.values() for v in branch}

Regions = {
    "Branches": Branches,
    "Center": Platforms_Set - _branch_vertices,
}

# stop_id -> branch name, for every platform in a branch (absent means Center)
NODE_TO_BRANCH: Dict[str, str] = {
    stop_id: branch_name for branch_name, stops in Branches.items() for stop_id in stops
}
CENTER_NODES: Set[str] = Regions["Center"]


def find_branch(node: str) -> Optional[str]:
    """Return the branch name a platform belongs to, or None if it is in the Center.

    args:
        node: Platform stop_id to look up.

    returns:
        The branch name (a key of Branches/Bridges) node belongs to, or None
        when node is a Center platform (or any other stop_id not in Branches).
    """
    return NODE_TO_BRANCH.get(node)


def compute_bridge(node: str) -> str:
    """Return the single Center platform node's branch reconnects through.

    args:
        node: Platform stop_id belonging to a branch (see find_branch);
            callers must only invoke this for branch platforms, since Center
            platforms have no bridge.

    returns:
        The bridge stop_id for node's branch, from Bridges.
    """
    branch = find_branch(node)
    (bridge_stop,) = Bridges[branch]
    return bridge_stop


def classify(source_id: str, target_id: str) -> str:
    """Return which of the 5 Center/Branch cases (source_id, target_id) falls into.

    args:
        source_id: Platform stop_id the route starts from.
        target_id: Platform stop_id the route ends at.

    returns:
        One of "CC", "CB", "BC", "SB", "DB":
          CC - source and target both in the Center
          CB - source in the Center, target in a Branch
          BC - source in a Branch, target in the Center
          SB - source and target in the SAME Branch
          DB - source and target in DIFFERENT Branches
    """
    source_branch = NODE_TO_BRANCH.get(source_id)
    target_branch = NODE_TO_BRANCH.get(target_id)
    source_center = source_id in CENTER_NODES
    target_center = target_id in CENTER_NODES

    if source_center and target_center:
        return "CC"
    if source_center and target_branch is not None:
        return "CB"
    if source_branch is not None and target_center:
        return "BC"
    if source_branch is not None and target_branch is not None:
        return "SB" if source_branch == target_branch else "DB"
    raise ValueError(
        f"Could not classify pair ({source_id}, {target_id}): neither id is in"
        " Branches or Regions['Center']."
    )
