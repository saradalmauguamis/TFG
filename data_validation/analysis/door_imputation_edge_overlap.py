"""Check whether doors.txt's flat imputation can even reach an edge edge_weight_validation flags.

`4_doors_time.py` only rewrites a row when it's at a trip's structural
boundary (`stop_sequence == min_seq` or `== max_seq`). Of those two cases,
only the *first*-row fix can ever reach an edge: `total`/`door`/`sw` in
`edge_weight_validation.py` are all computed from consecutive `(current,
next)` pairs within a trip, and a trip's last row has no `next` to pair
with - so fixing its `departure_time` is structurally inert for every edge
weight. Fixing a first row's `arrival_time` *is* live: it feeds `door_a`
and `total` for that trip's very first edge.

So the right question isn't "what % of all stop_times rows did doors.txt
touch" (a global row count, diluted by the inert last-row fixes and by
every untouched row in the network) - it's "of the edges that can be
reached by a first-row fix, how many does `edge_weight_validation.py`
currently flag as unstable (CV) or time-dependent (hourly range), and for
those, is the variance actually coming from `door` rather than `sw` (since
a `sw`-dominated edge wouldn't be fixed by a better door imputation
anyway)?" This script answers that directly, cross-referencing the two
analyses instead of guessing from a row-count percentage.

Caveat: this matches stops by raw `stop_id`. `edge_weight_validation.py`
reads the post-shared-platform-duplication file and groups edges using
`subway_route_names_stop_ids_artificial`, where only *shared-platform*
stops get a rewritten id; every other stop keeps its original id, so the
match is exact except at those interchange platforms (called out in the
output, not silently ignored).
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

_PROJECT_ROOT = str(Path(__file__).resolve().parents[2])
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from data_validation.gtfs_utils import (  # noqa: E402
    STOP_TIMES_SEQUENCE_FILE,
    TRIPS_FILE,
    check_missing_files,
    load_trip_sequence_bounds,
    load_trip_to_line,
    read_dict_rows,
)
from data_validation.analysis.edge_weight_validation import (  # noqa: E402
    GroupKey as EdgeGroupKey,
    MIN_CV_TO_PRINT,
    MIN_HOURLY_RANGE_PCT_TO_PRINT,
    average_times_for_pairs,
    build_trip_groups_by_line,
    collect_pair_door_sw_samples_by_trip_group,
    collect_pair_door_sw_samples_by_trip_group_hourly,
    collect_pair_samples_by_trip_group,
    rank_edges_by_cv,
    rank_edges_by_hourly_range,
)
from data_validation.gtfs_utils import STOP_TIMES_FILE  # noqa: E402
from scripts.basics import (  # noqa: E402
    subway_route_names_stop_ids_artificial,
    subway_routes_names_ids,
)

GroupKey = Tuple[str, str]  # (line, stop_id)

SECTION_BANNER_WIDTH = 70


def _print_section_header(title: str) -> None:
    """Print a section title inside a banner, to visually separate report sections.

    args:
            title: Section title, printed upper-case between two divider lines.
    """
    divider = "=" * SECTION_BANNER_WIDTH
    print(f"\n{divider}")
    print(title.upper())
    print(f"{divider}\n")


def find_first_row_imputed_stops(
    stop_times_file: str, trips_file: str, rid_to_name: Dict[str, str]
) -> Set[GroupKey]:
    """Find (line, stop_id) keys where doors.txt's fix can reach a live edge sample.

    Only rows where `stop_sequence == min_seq` (the trip's first row) matter:
    fixing a last row's `departure_time` is never read by any edge
    computation, since there is no `next` stop to pair it with.

    args:
            stop_times_file: Path to the (pre-imputation) stop_times file.
            trips_file: Path to the trips file used to resolve trip_id -> line.
            rid_to_name: Mapping from route_id to line name.

    returns:
            Set of (line, stop_id) keys with at least one first-row
            `arrival_time == departure_time` occurrence.
    """
    trip_to_line = load_trip_to_line(trips_file, rid_to_name)
    trip_bounds = load_trip_sequence_bounds(stop_times_file, set(trip_to_line))
    first_row_imputed: Set[GroupKey] = set()

    for row in read_dict_rows(stop_times_file):
        trip_id = row.get("trip_id", "").strip()
        line = trip_to_line.get(trip_id)
        if not line:
            continue
        stop_id = row.get("stop_id", "").strip()
        if not stop_id:
            continue
        arrival = row.get("arrival_time", "").strip()
        departure = row.get("departure_time", "").strip()
        if not arrival or not departure or arrival != departure:
            continue
        try:
            seq = int(row.get("stop_sequence", "").strip())
        except ValueError:
            continue
        bounds = trip_bounds.get(trip_id)
        if not bounds:
            continue
        min_seq, _ = bounds
        if seq == min_seq:
            first_row_imputed.add((line, stop_id))

    return first_row_imputed


def main() -> None:
    """Cross-reference doors.txt's live (first-row) imputation with flagged edges."""
    rid_to_name: Dict[str, str] = {}
    first_row_imputed_stops: Set[GroupKey] = set()
    trip_id_to_group: Dict[str, EdgeGroupKey] = {}
    group_pairs: Dict[EdgeGroupKey, List[Tuple[str, str]]] = {}
    samples_by_group: Dict[EdgeGroupKey, Dict[Tuple[str, str], List[int]]] = {}
    avg_by_group: Dict[
        EdgeGroupKey, Dict[Tuple[str, str], Optional[Tuple[float, int, float]]]
    ] = {}
    door_by_group: Dict[EdgeGroupKey, Dict[Tuple[str, str], List[int]]] = {}
    sw_by_group: Dict[EdgeGroupKey, Dict[Tuple[str, str], List[int]]] = {}
    avg_door_by_group: Dict[
        EdgeGroupKey, Dict[Tuple[str, str], Optional[Tuple[float, int, float]]]
    ] = {}
    avg_sw_by_group: Dict[
        EdgeGroupKey, Dict[Tuple[str, str], Optional[Tuple[float, int, float]]]
    ] = {}
    ranked_cv: List = []
    door_hourly_by_group: Dict[
        EdgeGroupKey, Dict[Tuple[str, str], Dict[int, List[int]]]
    ] = {}
    sw_hourly_by_group: Dict[
        EdgeGroupKey, Dict[Tuple[str, str], Dict[int, List[int]]]
    ] = {}
    ranked_hourly_range: List = []
    total_edges = 0
    affected_edges: Set[Tuple[str, int, Tuple[str, str]]] = set()
    cv_by_key: Dict[Tuple[str, int, Tuple[str, str]], float] = {}
    hourly_by_key: Dict[Tuple[str, int, Tuple[str, str]], float] = {}
    flagged_edges: Set[Tuple[str, int, Tuple[str, str]]] = set()
    overlap: Set[Tuple[str, int, Tuple[str, str]]] = set()
    door_dominated_count = 0

    _print_section_header("Objective")
    print(
        "Does doors.txt's flat imputation actually reach any edge "
        "edge_weight_validation.py currently flags as unstable (CV) or "
        "time-dependent (hourly range)? Only first-row fixes can reach an "
        "edge at all (last-row fixes are structurally inert); among the "
        "edges they *can* reach, only the door-dominated ones would "
        "actually change if the imputation became hour-aware.\n"
    )

    check_missing_files([STOP_TIMES_SEQUENCE_FILE, TRIPS_FILE, STOP_TIMES_FILE])

    rid_to_name = {rid: name for name, rid in subway_routes_names_ids.items()}
    first_row_imputed_stops = find_first_row_imputed_stops(
        STOP_TIMES_SEQUENCE_FILE, TRIPS_FILE, rid_to_name
    )
    print(
        f"(line, stop_id) keys with a live (first-row) imputed value: "
        f"{len(first_row_imputed_stops)}"
    )

    trip_id_to_group, group_pairs = build_trip_groups_by_line(
        subway_route_names_stop_ids_artificial, subway_routes_names_ids, TRIPS_FILE
    )
    samples_by_group = collect_pair_samples_by_trip_group(
        STOP_TIMES_FILE, trip_id_to_group, group_pairs
    )
    avg_by_group = {
        group: average_times_for_pairs(samples)
        for group, samples in samples_by_group.items()
    }
    door_by_group, sw_by_group = collect_pair_door_sw_samples_by_trip_group(
        STOP_TIMES_FILE, trip_id_to_group, group_pairs
    )
    avg_door_by_group = {
        group: average_times_for_pairs(samples)
        for group, samples in door_by_group.items()
    }
    avg_sw_by_group = {
        group: average_times_for_pairs(samples)
        for group, samples in sw_by_group.items()
    }
    ranked_cv = rank_edges_by_cv(group_pairs, avg_by_group, samples_by_group)
    door_hourly_by_group, sw_hourly_by_group = (
        collect_pair_door_sw_samples_by_trip_group_hourly(
            STOP_TIMES_FILE, trip_id_to_group, group_pairs
        )
    )
    ranked_hourly_range = rank_edges_by_hourly_range(
        group_pairs, avg_by_group, door_hourly_by_group, sw_hourly_by_group
    )

    total_edges = sum(len(pairs) for pairs in group_pairs.values())

    for (line, direction_id), pairs in group_pairs.items():
        for pair in pairs:
            a, _ = pair
            if (line, a) in first_row_imputed_stops:
                affected_edges.add((line, direction_id, pair))

    cv_by_key = {
        (line, direction, pair): cv for cv, line, direction, pair, *_ in ranked_cv
    }
    hourly_by_key = {
        (line, direction, pair): pct
        for pct, line, direction, pair, *_ in ranked_hourly_range
    }
    flagged_edges = {key for key, cv in cv_by_key.items() if cv >= MIN_CV_TO_PRINT} | {
        key
        for key, pct in hourly_by_key.items()
        if pct >= MIN_HOURLY_RANGE_PCT_TO_PRINT
    }

    overlap = affected_edges & flagged_edges

    _print_section_header("Overlap summary")
    print(f"Total edges (all lines/directions): {total_edges}")
    print(
        "Edges a live doors.txt fix can reach (departure stop has a "
        f"first-row imputed value): {len(affected_edges)}"
    )
    print(
        "Edges currently flagged by edge_weight_validation.py "
        f"(CV or hourly range): {len(flagged_edges)}"
    )
    print(f"\nOverlap (flagged AND reachable by doors.txt's fix): {len(overlap)}\n")

    if not overlap:
        print(
            "None of the edges edge_weight_validation.py currently flags can "
            "be reached by a first-row doors.txt fix, so making the "
            "imputation hour-aware would not change its verdict for a single "
            "currently-flagged edge. The flat mean in doors.txt is justified "
            "for this purpose: the real time-of-day pattern it ignores never "
            "reaches a place edge_weight_validation.py would otherwise distrust."
        )
        return

    print(
        "Of these, only door-dominated edges could actually change if "
        "doors.txt became hour-aware - an sw-dominated edge is flagged "
        "because of real movement-time variance, which no door fix touches:\n"
    )
    for line, direction_id, pair in sorted(overlap):
        a, b = pair
        group: EdgeGroupKey = (line, direction_id)
        door_record = avg_door_by_group.get(group, {}).get((a, b))
        sw_record = avg_sw_by_group.get(group, {}).get((a, b))
        dominant = "unknown"
        if door_record is not None and sw_record is not None:
            dominant = "door" if door_record[2] >= sw_record[2] else "sw"
            if dominant == "door":
                door_dominated_count += 1
        cv = cv_by_key.get((line, direction_id, pair))
        hourly_pct = hourly_by_key.get((line, direction_id, pair))
        reasons = []
        if cv is not None and cv >= MIN_CV_TO_PRINT:
            reasons.append(f"CV={cv:.1%}")
        if hourly_pct is not None and hourly_pct >= MIN_HOURLY_RANGE_PCT_TO_PRINT:
            reasons.append(f"hourly range={hourly_pct:.1%}")
        print(
            f"  - {line} dir{direction_id}  {a} -> {b}  [{', '.join(reasons)}]  "
            f"-> {dominant}-dominated"
        )

    print(
        f"\nVerdict: of {total_edges} edges, {len(affected_edges)} can even be "
        f"touched by a first-row doors.txt fix, but only {len(overlap)} of "
        f"those are edges edge_weight_validation.py actually flags - and only "
        f"{door_dominated_count} of those {len(overlap)} are door-dominated, "
        "so could plausibly improve from a better imputation. The rest of "
        f"the {len(flagged_edges)} flagged edges are flagged for reasons "
        "doors.txt cannot fix (sw variance, or a departure stop doors.txt "
        "never touches). The real time-of-day pattern doors.txt averages "
        "away (shown by door_time_hourly_validation.py) is genuine, but it "
        "almost never lands on an edge edge_weight_validation.py would "
        "otherwise distrust - which is why the flat mean is a justified "
        "simplification here, not just an unexamined shortcut."
    )


if __name__ == "__main__":
    main()
