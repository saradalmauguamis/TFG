"""Region/bridge partition of the Barcelona subway graph, for a zone-aware h_bcn heuristic.

Every stop_id below is in the post-shared-platform-duplication ("artificial")
scheme, matching WEIGHTS_FILE (data_validation/gtfs_utils.py) and
scripts.basics.subway_route_names_stop_ids_artificial, since that is the id
scheme the real graph (built via build_graph_from_weights, in
routing_algorithms/algorithms_utils.py) actually runs on.

- Branches: short stub segments of a line that only reconnect to the rest of
  the network through a single platform (their bridge). Lines without a stub
  (L3, L4, L10N) have no entry here.
- Bridges: for each branch, the single Center platform it reconnects through.
- Regions: "Branches" (as above) plus "Center", every platform stop not in
  any branch.
"""

from scripts.basics import subway_route_names_stop_ids_artificial

# These are unordered sets
Branches = {
    "Branch_L1": {"1.111", "1.112", "1.113", "1.114", "1.115", "1.116"},
    "Branch_L2": {"1.226", "1.227"},
    "Branch_L5": {"1.509", "1.510", "1.511", "1.512", "1.513", "1.514", "1.555"},
    "Branch_L9S": {
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
    },
    "Branch_L9N": {"1.943", "1.944", "1.945"},
    "Branch_L10S": {
        "1.951",
        "1.952",
        "1.953",
        "1.954",
        "1.956",
        "1.957",
        "1.958",
        "1.959",
    },
    "Branch_L11": {"1.1137", "1.1138", "1.1139", "1.1140"},
    "Branch_FM": {"1.9902"},
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
