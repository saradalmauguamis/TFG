"""Build the weighted graph edges for the subway network.

`data_validation/analysis/directional_asymmetry.py` and
`data_validation/analysis/edge_weight_validation.py` motivated using
mean(total) (`arrival_b - arrival_a`) as the static weight for `sw` edges
(platform -> platform). This script computes that weight for every directed
platform pair observed in `STOP_TIMES_FILE` (`stop_times_shared.txt`), rounded
to whole seconds with `round_half_up_mean` (not a float mean, to avoid the
precision drift `statistics.mean`/`round()` can introduce), and writes it to
`subway_weights.txt`.

It then combines that file with the other two edge types of the graph -
transfers (`TF`, from `TRANSFERS_FILE`) and pathways from an entrance to a
platform (`PW`, from `PATHWAYS_FILE`, only rows where one side is an entrance
`E.*` and the other a platform `1.*`) - into a single `weights.txt`.

Outputs (written to `data/6_weights/`):
- subway_weights.txt: from_stop_id, to_stop_id, weight_seconds, line
- weights.txt:        from_stop_id, to_stop_id, weight_seconds, type

Both files are ordered by from_stop_id then to_stop_id, following the
canonical stop order of `subway_route_names_stop_ids_artificial`; stop_ids
outside that order (entrances) sort after every platform, alphabetically.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, List, Tuple

_PROJECT_ROOT = str(Path(__file__).resolve().parents[2])
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from data_validation.gtfs_utils import (  # noqa: E402
    PATHWAYS_FILE,
    STOP_TIMES_FILE,
    SUBWAY_WEIGHTS_FILE,
    TRANSFERS_FILE,
    TRIPS_FILE,
    WEIGHTS_FILE,
    build_stop_id_order_index,
    build_trip_groups_by_line,
    check_missing_files,
    collect_pair_samples_by_trip_group,
    load_transfer_weights,
    print_file_disclaimer,
    read_dict_rows,
    round_half_up_mean,
    write_rows,
)
from subway_reference.subway_lines import (  # noqa: E402
    subway_route_names_stop_ids_artificial,
    subway_routes_names_ids,
)

SubwayWeight = Tuple[
    str, str, int, str
]  # (from_stop_id, to_stop_id, weight_seconds, line)
WeightRow = Tuple[
    str, str, int, str
]  # (from_stop_id, to_stop_id, weight_seconds, type)


def compute_subway_weights(
    stop_times_file: str,
    route_names_stop_ids: Dict[str, List[str]],
    routes_names_ids: Dict[str, str],
    trips_file: str,
) -> List[SubwayWeight]:
    """Compute the sw (platform -> platform) weight for every directed pair.

    Each pair's weight is `round_half_up_mean` of its observed travel-time
    samples, pooled across every (line, direction) group producing that exact
    pair. In this dataset that is always a single line, since shared
    platforms get distinct stop_ids in `route_names_stop_ids` (the
    `_artificial` variant), but pooling stays correct even if that changes.

    args:
        stop_times_file: Path to stop_times_shared.txt.
        route_names_stop_ids: Mapping from line name to its ordered stop_id
            list (`subway_route_names_stop_ids_artificial`).
        routes_names_ids: Mapping from line name to route_id.
        trips_file: Path to the trips file used to resolve each trip's
            direction_id.

    returns:
        (from_stop_id, to_stop_id, weight_seconds, line) for every pair with
        at least one sample. `line` is every line that produced the pair,
        joined with "/" when pooled across more than one.
    """
    pooled_samples: Dict[Tuple[str, str], List[int]] = {}
    lines_by_pair: Dict[Tuple[str, str], List[str]] = {}
    weights: List[SubwayWeight] = []

    trip_id_to_group, group_pairs = build_trip_groups_by_line(
        route_names_stop_ids, routes_names_ids, trips_file
    )
    samples_by_group = collect_pair_samples_by_trip_group(
        stop_times_file, trip_id_to_group, group_pairs
    )

    for (line_short_name, _direction_id), pairs in samples_by_group.items():
        for pair, samples in pairs.items():
            if not samples:
                continue
            pooled_samples.setdefault(pair, []).extend(samples)
            lines = lines_by_pair.setdefault(pair, [])
            if line_short_name not in lines:
                lines.append(line_short_name)

    for pair, samples in pooled_samples.items():
        from_stop_id, to_stop_id = pair
        weight_seconds = round_half_up_mean(samples)
        line = "/".join(lines_by_pair[pair])
        weights.append((from_stop_id, to_stop_id, weight_seconds, line))
    return weights


def collect_entrance_pathway_weights(pathways_file: str) -> List[Tuple[str, str, int]]:
    """Collect entrance<->platform pathway edges and their traversal_time.

    args:
        pathways_file: Path to pathways_shared.txt.

    returns:
        (from_stop_id, to_stop_id, traversal_time) for every pathway row
        connecting an entrance (E.*) and a platform (1.*), in either
        direction, as written in the source row.
    """
    edges: List[Tuple[str, str, int]] = []
    for row in read_dict_rows(pathways_file):
        from_stop_id = row.get("from_stop_id", "").strip()
        to_stop_id = row.get("to_stop_id", "").strip()
        traversal_time = row.get("traversal_time", "").strip()
        if not from_stop_id or not to_stop_id or not traversal_time:
            continue
        entrance_to_platform = from_stop_id.startswith("E.") and to_stop_id.startswith(
            "1."
        )
        platform_to_entrance = from_stop_id.startswith("1.") and to_stop_id.startswith(
            "E."
        )
        if entrance_to_platform or platform_to_entrance:
            edges.append((from_stop_id, to_stop_id, int(traversal_time)))
    return edges


def sort_by_canonical_order(
    rows: List[Tuple[str, str, object, object]], order_index: Dict[str, int]
) -> None:
    """Sort (from_stop_id, to_stop_id, ...) rows in place by canonical stop order.

    args:
        rows: Rows whose first two fields are from_stop_id and to_stop_id.
        order_index: stop_id -> canonical rank, from `build_stop_id_order_index`.
    """
    missing_rank = len(order_index)
    rows.sort(
        key=lambda row: (
            order_index.get(row[0], missing_rank),
            row[0],
            order_index.get(row[1], missing_rank),
            row[1],
        )
    )


def write_subway_weights(
    output_path: str, weights: List[SubwayWeight], order_index: Dict[str, int]
) -> int:
    """Sort and write the sw edge weights to subway_weights.txt.

    args:
        output_path: Path to write subway_weights.txt.
        weights: (from_stop_id, to_stop_id, weight_seconds, line) rows.
        order_index: stop_id -> canonical rank, from `build_stop_id_order_index`.

    returns:
        Number of rows written.
    """
    fieldnames: List[str] = ["from_stop_id", "to_stop_id", "weight_seconds", "line"]
    rows: List[Dict[str, str]] = []

    sort_by_canonical_order(weights, order_index)
    rows = [
        {
            "from_stop_id": from_stop_id,
            "to_stop_id": to_stop_id,
            "weight_seconds": str(weight_seconds),
            "line": line,
        }
        for from_stop_id, to_stop_id, weight_seconds, line in weights
    ]
    write_rows(output_path, fieldnames, rows)
    return len(rows)


def write_weights(
    output_path: str,
    subway_weights: List[SubwayWeight],
    transfer_weights: List[Tuple[str, str, int]],
    pathway_weights: List[Tuple[str, str, int]],
    order_index: Dict[str, int],
) -> Dict[str, int]:
    """Combine sw/tf/pw edges, sort them and write weights.txt.

    args:
        output_path: Path to write weights.txt.
        subway_weights: (from_stop_id, to_stop_id, weight_seconds, line) rows,
            from `compute_subway_weights`.
        transfer_weights: (from_stop_id, to_stop_id, min_transfer_time) rows,
            from `load_transfer_weights`.
        pathway_weights: (from_stop_id, to_stop_id, traversal_time) rows, from
            `collect_entrance_pathway_weights`.
        order_index: stop_id -> canonical rank, from `build_stop_id_order_index`.

    returns:
        Row count written per type, keyed by "SW", "TF", "PW".
    """
    combined: List[WeightRow] = []
    fieldnames: List[str] = ["from_stop_id", "to_stop_id", "weight_seconds", "type"]
    rows: List[Dict[str, str]] = []
    counts: Dict[str, int] = {"SW": 0, "TF": 0, "PW": 0}

    combined = (
        [(a, b, w, "SW") for a, b, w, _line in subway_weights]
        + [(a, b, w, "TF") for a, b, w in transfer_weights]
        + [(a, b, w, "PW") for a, b, w in pathway_weights]
    )
    sort_by_canonical_order(combined, order_index)

    rows = [
        {
            "from_stop_id": from_stop_id,
            "to_stop_id": to_stop_id,
            "weight_seconds": str(weight_seconds),
            "type": edge_type,
        }
        for from_stop_id, to_stop_id, weight_seconds, edge_type in combined
    ]
    write_rows(output_path, fieldnames, rows)

    for _, _, _, edge_type in combined:
        counts[edge_type] += 1
    return counts


def main() -> None:
    """Compute sw edge weights and assemble the full weighted graph."""
    order_index: Dict[str, int] = {}
    subway_weights: List[SubwayWeight] = []
    subway_rows_written: int = 0
    transfer_weights: List[Tuple[str, str, int]] = []
    pathway_weights: List[Tuple[str, str, int]] = []
    counts: Dict[str, int] = {}

    check_missing_files([STOP_TIMES_FILE, TRIPS_FILE, TRANSFERS_FILE, PATHWAYS_FILE])
    print_file_disclaimer([STOP_TIMES_FILE, TRIPS_FILE, TRANSFERS_FILE, PATHWAYS_FILE])

    order_index = build_stop_id_order_index(subway_route_names_stop_ids_artificial)

    subway_weights = compute_subway_weights(
        STOP_TIMES_FILE,
        subway_route_names_stop_ids_artificial,
        subway_routes_names_ids,
        TRIPS_FILE,
    )
    subway_rows_written = write_subway_weights(
        SUBWAY_WEIGHTS_FILE, subway_weights, order_index
    )
    print(
        f"subway_weights.txt: rows_written={subway_rows_written} "
        f"-> {Path(SUBWAY_WEIGHTS_FILE).relative_to(_PROJECT_ROOT)}"
    )

    transfer_weights = list(load_transfer_weights(TRANSFERS_FILE))
    pathway_weights = collect_entrance_pathway_weights(PATHWAYS_FILE)
    counts = write_weights(
        WEIGHTS_FILE, subway_weights, transfer_weights, pathway_weights, order_index
    )
    print(
        f"weights.txt: SW={counts['SW']}, TF={counts['TF']}, PW={counts['PW']}, "
        f"total={sum(counts.values())} "
        f"-> {Path(WEIGHTS_FILE).relative_to(_PROJECT_ROOT)}"
    )


if __name__ == "__main__":
    main()
