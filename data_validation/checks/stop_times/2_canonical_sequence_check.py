"""Check (or verify) that subway trips follow the canonical stop sequence.

Default run (detect, `WORKFLOW.md` step 5): reads `stop_times_cleaned.txt`/
`trips_cleaned.txt` from `2_duplicated_trips` and `stops_subway.txt` from
`1_subway`. For each trip, compares each consecutive stop pair (gap of
exactly one in `stop_sequence`) against the expected order from
`subway_reference.subway_lines.subway_route_names_stop_ids` (reversed when
`direction_id == 1`). Writes `wrong_stop_sequences.txt` to `3_stop_sequence`,
consumed by `processing/3_stop_sequence.py`.

Run with a `verify` argument (`WORKFLOW.md` step 7, after
`processing/3_stop_sequence.py` has run) to re-run the same check on
`stop_times_sequence.txt` from `3_stop_sequence`: the same trips will still
appear as having non-canonical order (the stops themselves have not
changed), but the bad pairs should now show non-consecutive stop_sequence
numbers, confirming the gap was correctly inserted. Produces no output file.
"""

from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Set, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from subway_reference.subway_lines import (  # noqa: E402
    subway_route_names_stop_ids,
    subway_routes_names_ids,
)

from data_validation.gtfs_utils import (  # noqa: E402
    STOP_TIMES_CLEANED_FILE,
    STOP_TIMES_SEQUENCE_FILE,
    STOPS_SUBWAY_FILE,
    TRIPS_FILE,
    WRONG_STOP_SEQUENCES_FILE,
    build_expected_adjacency,
    check_missing_files,
    load_stop_names,
    print_file_disclaimer,
    read_dict_rows,
    write_rows,
)

BadPair = Tuple[int, str, int, str]
FlaggedTrip = Tuple[str, str, str, str, List[BadPair]]


def build_trip_to_route_dir(
    trips_file: str, rid_to_name: Dict[str, str]
) -> Tuple[Dict[str, Tuple[str, str]], int]:
    """Read trips and return a mapping of trip_id to (route_id, direction_id).

    args:
        trips_file: Path to the trips CSV file.
        rid_to_name: Mapping from route_id to route short name.

    returns:
        Tuple of the mapping dict and the count of matched rows.
    """
    trip_to_route_dir: Dict[str, Tuple[str, str]] = {}
    matched_rows = 0
    for row in read_dict_rows(trips_file):
        trip_id = row.get("trip_id", "").strip()
        if not trip_id:
            continue
        route_id = row.get("route_id", "").strip()
        if route_id not in rid_to_name:
            continue
        matched_rows += 1
        trip_to_route_dir[trip_id] = (
            route_id,
            row.get("direction_id", "").strip() or "",
        )
    return trip_to_route_dir, matched_rows


def build_trip_seq_rows(
    stop_times_file: str, trip_ids: Set[str]
) -> Dict[str, List[Tuple[int, str]]]:
    """Read stop_times and return a mapping of trip_id to sorted (seq, stop_id) rows.

    args:
        stop_times_file: Path to the stop_times CSV file.
        trip_ids: Set of trip_id values to include.

    returns:
        Mapping from trip_id to its stops sorted by stop_sequence.
    """
    trip_seq_rows = defaultdict(list)
    for row in read_dict_rows(stop_times_file):
        trip_id = row.get("trip_id", "").strip()
        if trip_id not in trip_ids:
            continue
        stop_id = row.get("stop_id", "").strip()
        if not stop_id:
            continue
        try:
            stop_sequence = int(row.get("stop_sequence", "").strip())
        except Exception:
            continue
        trip_seq_rows[trip_id].append((stop_sequence, stop_id))
    for trip_id in trip_seq_rows:
        trip_seq_rows[trip_id].sort(key=lambda item: item[0])
    return trip_seq_rows


def detect_canonical_violations(
    trip_seq_rows: Dict[str, List[Tuple[int, str]]],
    trip_to_route_dir: Dict[str, Tuple[str, str]],
    rid_to_name: Dict[str, str],
    route_names_stop_ids: Dict[str, List[str]],
) -> List[FlaggedTrip]:
    """Return trips whose consecutive stops break the canonical route order.

    Only stop_sequence pairs with a gap of exactly one are checked. Pairs
    separated by a larger gap are considered intentionally non-adjacent and skipped.

    args:
        trip_seq_rows: Mapping from trip_id to sorted (seq, stop_id) rows.
        trip_to_route_dir: Mapping from trip_id to (route_id, direction_id).
        rid_to_name: Mapping from route_id to route short name.
        route_names_stop_ids: Mapping from route name to canonical stop order.

    returns:
        List of (route_name, route_id, trip_id, direction_id, bad_pairs).
    """
    flagged: List[FlaggedTrip] = []
    for trip_id, seq_rows in trip_seq_rows.items():
        route_id, direction_id = trip_to_route_dir.get(trip_id, (None, None))
        if not route_id:
            continue
        route_name = rid_to_name.get(route_id)
        expected_order = list(route_names_stop_ids.get(route_name, []))
        if not expected_order:
            continue
        if direction_id == "1":
            expected_order = list(reversed(expected_order))
        adjacency = build_expected_adjacency(expected_order)
        bad_pairs: List[BadPair] = []
        for index in range(len(seq_rows) - 1):
            seq_a, stop_a = seq_rows[index]
            seq_b, stop_b = seq_rows[index + 1]
            if seq_b != seq_a + 1:
                continue
            if adjacency.get(stop_a) != stop_b:
                bad_pairs.append((seq_a, stop_a, seq_b, stop_b))
        if bad_pairs:
            flagged.append((route_name, route_id, trip_id, direction_id, bad_pairs))
    return flagged


def print_canonical_violations(
    flagged: List[FlaggedTrip], stop_names: Dict[str, str]
) -> None:
    """Print each flagged trip with its out-of-order stop pairs.

    args:
        flagged: Output of detect_canonical_violations.
        stop_names: Mapping from stop_id to stop_name.
    """
    for route_name, route_id, trip_id, direction_id, bad_pairs in flagged:
        print(
            f"- route={route_name!r} route_id={route_id} trip_id={trip_id}"
            f" direction={direction_id} bad_pairs={len(bad_pairs)}"
        )
        for seq_a, stop_a, seq_b, stop_b in bad_pairs:
            print(
                f"    bad order: [{seq_a}] {stop_a} ({stop_names.get(stop_a, '(no name)')}) -> "
                f"[{seq_b}] {stop_b} ({stop_names.get(stop_b, '(no name)')})"
            )


def main(verify: bool = False) -> None:
    """Detect canonical stop-order violations, or verify the sequence fix opened gaps.

    args:
        verify: When True, check `stop_times_sequence.txt` (after
            `processing/3_stop_sequence.py`) instead of `stop_times_cleaned.txt`;
            does not write `wrong_stop_sequences.txt`.
    """
    stop_times_file = STOP_TIMES_SEQUENCE_FILE if verify else STOP_TIMES_CLEANED_FILE
    rid_to_name: Dict[str, str] = {}
    trip_to_route_dir: Dict[str, Tuple[str, str]] = {}
    matched_rows = 0
    available_route_ids: List[str] = []
    suffix = ""
    trip_ids: Set[str] = set()
    trip_seq_rows: Dict[str, List[Tuple[int, str]]] = {}
    stop_names: Dict[str, str] = {}
    flagged: List[FlaggedTrip] = []
    rows: List[Dict[str, object]] = []

    check_missing_files([TRIPS_FILE, stop_times_file, STOPS_SUBWAY_FILE])
    print_file_disclaimer(
        [
            (stop_times_file, "stop_times"),
            (STOPS_SUBWAY_FILE, "stops"),
            (TRIPS_FILE, "trips"),
        ]
    )

    rid_to_name = {rid: name for name, rid in subway_routes_names_ids.items()}
    trip_to_route_dir, matched_rows = build_trip_to_route_dir(TRIPS_FILE, rid_to_name)

    if not trip_to_route_dir:
        available_route_ids = sorted(
            {
                row.get("route_id", "").strip()
                for row in read_dict_rows(TRIPS_FILE)
                if row.get("route_id", "").strip()
            }
        )
        suffix = "" if len(available_route_ids) <= 20 else " ..."
        print("No subway trips found in 'trips' for the canonical mappings.")
        print(f"Trips rows matching subway route_ids: {matched_rows}")
        print(
            f"Available route_id values in 'trips': {available_route_ids[:20]}{suffix}"
        )
        return

    trip_ids = set(trip_to_route_dir)
    trip_seq_rows = build_trip_seq_rows(stop_times_file, trip_ids)
    stop_names = load_stop_names(STOPS_SUBWAY_FILE)
    flagged = detect_canonical_violations(
        trip_seq_rows, trip_to_route_dir, rid_to_name, subway_route_names_stop_ids
    )

    if verify:
        if not flagged:
            print(
                "All checked subway trips follow an allowed contiguous stop sequence."
            )
            return
        print(f"FOUND {len(flagged)} trips with unexpected stop sequences:")
        print_canonical_violations(flagged, stop_names)
        return

    rows = [
        {
            "trip_id": trip_id,
            "stop_a": stop_a,
            "stop_b": stop_b,
            "seq_a": seq_a,
            "seq_b": seq_b,
        }
        for _, _, trip_id, _, bad_pairs in flagged
        for seq_a, stop_a, seq_b, stop_b in bad_pairs
    ]
    write_rows(
        WRONG_STOP_SEQUENCES_FILE,
        ["trip_id", "stop_a", "stop_b", "seq_a", "seq_b"],
        rows,
    )

    if not flagged:
        print("All checked subway trips follow an allowed contiguous stop sequence.")
        print(
            f"{Path(WRONG_STOP_SEQUENCES_FILE).name} (empty) written"
            f" to {Path(WRONG_STOP_SEQUENCES_FILE).relative_to(PROJECT_ROOT)}"
        )
        return

    print(f"FOUND {len(flagged)} trips with unexpected stop sequences:")
    print_canonical_violations(flagged, stop_names)
    print(
        f"\n{Path(WRONG_STOP_SEQUENCES_FILE).name} written"
        f" to {Path(WRONG_STOP_SEQUENCES_FILE).relative_to(PROJECT_ROOT)}"
        f" ({len(rows)} rows)"
    )


if __name__ == "__main__":
    raise SystemExit(main(verify="verify" in sys.argv[1:]))
