"""Detect (or verify) duplicate trip_id blocs in stop_times.

Default run (detect, `WORKFLOW.md` step 2): reads `stop_times_subway.txt`/
`trips_subway.txt` from `1_subway` and groups trip_ids that share an
identical ordered stop-event signature. When duplicates are found, writes
`trip_ids_to_eliminate.txt` to `2_duplicated_trips` (one trip_id kept per
group), consumed by `processing/2_duplicated_trips.py`.

Run with a `verify` argument (`WORKFLOW.md` step 4, after
`processing/2_duplicated_trips.py` has run) to re-run the same check on
`stop_times_cleaned.txt`/`trips_cleaned.txt` from `2_duplicated_trips`: since
exactly one representative trip_id was kept per duplicate-signature group, no
signature should now map to 2+ trip_ids. Produces no output file.
"""

from __future__ import annotations

import os
import sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, List, Set, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from data_validation.gtfs_utils import (  # noqa: E402
    STOP_TIMES_CLEANED_FILE,
    STOP_TIMES_SUBWAY_FILE,
    TRIP_IDS_TO_ELIMINATE_FILE,
    TRIPS_FILE,
    TRIPS_SUBWAY_FILE,
    check_missing_files,
    load_trip_ids,
    make_signature,
    print_file_disclaimer,
    read_dict_rows,
)

StopEvent = Tuple[int, str, str, str]


def build_trip_stop_events(
    stop_times_file: str, trip_ids: Set[str]
) -> Tuple[Dict[str, List[StopEvent]], int]:
    """Read stop_times and group ordered stop-event tuples by trip_id.

    args:
        stop_times_file: Path to the stop_times CSV file.
        trip_ids: Set of trip_id values to include.

    returns:
        Tuple of (mapping from trip_id to its (seq, arrival, departure, stop_id) tuples,
        total rows read from the file).
    """
    trips_rows: Dict[str, List[StopEvent]] = defaultdict(list)
    total_rows = 0
    for row in read_dict_rows(stop_times_file):
        total_rows += 1
        trip_id = row.get("trip_id", "")
        if trip_id not in trip_ids:
            continue
        try:
            stop_sequence = int(row.get("stop_sequence", ""))
        except Exception:
            stop_sequence = 10**9
        trips_rows[trip_id].append(
            (
                stop_sequence,
                row.get("arrival_time", ""),
                row.get("departure_time", ""),
                row.get("stop_id", ""),
            )
        )
    return trips_rows, total_rows


def group_trips_by_signature(
    trips_rows: Dict[str, List[StopEvent]]
) -> Dict[Tuple[StopEvent, ...], List[str]]:
    """Group trip_ids that share an identical ordered stop-event signature.

    args:
        trips_rows: Mapping from trip_id to its stop-event tuples, from `build_trip_stop_events`.

    returns:
        Mapping from signature to the list of trip_ids sharing it.
    """
    signature_to_trip_ids: Dict[Tuple[StopEvent, ...], List[str]] = defaultdict(list)
    max_workers = min(8, (os.cpu_count() or 4))
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(make_signature, item): item[0]
            for item in trips_rows.items()
        }
        for future in as_completed(futures):
            trip_id, signature = future.result()
            signature_to_trip_ids[signature].append(trip_id)
    return signature_to_trip_ids


def find_duplicate_groups(
    signature_to_trip_ids: Dict[Tuple[StopEvent, ...], List[str]]
) -> List[Tuple[Tuple[StopEvent, ...], List[str]]]:
    """Return signature groups with 2+ trip_ids, sorted by group size then trip_ids.

    args:
        signature_to_trip_ids: Mapping from signature to trip_ids, from `group_trips_by_signature`.

    returns:
        List of (signature, sorted trip_ids) for groups with at least 2 trip_ids.
    """
    duplicate_groups = [
        (signature, sorted(trip_ids_for_signature))
        for signature, trip_ids_for_signature in signature_to_trip_ids.items()
        if len(trip_ids_for_signature) >= 2
    ]
    duplicate_groups.sort(key=lambda item: (len(item[1]), item[1]))
    return duplicate_groups


def print_duplicate_groups_summary(
    duplicate_groups: List[Tuple[Tuple[StopEvent, ...], List[str]]]
) -> None:
    """Print a group-size histogram with one example group per size.

    args:
        duplicate_groups: Output of `find_duplicate_groups`.
    """
    total_duplicate_trip_ids = 0
    duplicate_group_sizes: Dict[int, int] = {}

    if not duplicate_groups:
        print(
            "No pair/group of trip_id with identical sequence and schedules was found."
        )
        return

    total_duplicate_trip_ids = sum(len(trip_ids) for _, trip_ids in duplicate_groups)
    print(
        f"\nFound {len(duplicate_groups)} groups of trip_id with identical content "
        f"({total_duplicate_trip_ids} trip_id in total)."
    )

    for _, trip_ids_for_signature in duplicate_groups:
        group_size = len(trip_ids_for_signature)
        duplicate_group_sizes[group_size] = duplicate_group_sizes.get(group_size, 0) + 1
    for group_size in sorted(duplicate_group_sizes):
        print(f"Groups with {group_size} trip_id: {duplicate_group_sizes[group_size]}")
        for _, trip_ids_for_signature in duplicate_groups:
            if len(trip_ids_for_signature) == group_size:
                suffix = "..." if len(trip_ids_for_signature) > 5 else ""
                print(
                    f"  Example group with {group_size} trip_id:"
                    f" {trip_ids_for_signature[:5]}{suffix}"
                )
                break


def main(verify: bool = False) -> None:
    """Detect duplicate trip_id blocs, or verify none remain after deduplication.

    args:
        verify: When True, check the post-deduplication files for leftover
            duplicates instead of detecting fresh ones; does not write
            `trip_ids_to_eliminate.txt`.
    """
    stop_times_file = STOP_TIMES_SUBWAY_FILE
    trips_file = TRIPS_SUBWAY_FILE
    trip_id_set: Set[str] = set()
    trips_rows: Dict[str, List[StopEvent]] = {}
    total_rows = 0
    signature_to_trip_ids: Dict[Tuple[StopEvent, ...], List[str]] = {}
    duplicate_groups: List[Tuple[Tuple[StopEvent, ...], List[str]]] = []
    trip_ids_to_eliminate: List[str] = []
    total_duplicate_trip_ids = 0

    if verify:
        stop_times_file = STOP_TIMES_CLEANED_FILE
        trips_file = TRIPS_FILE

    check_missing_files([stop_times_file, trips_file])
    print_file_disclaimer(
        [
            (stop_times_file, "stop_times"),
            (trips_file, "trips"),
        ]
    )

    trip_id_set = load_trip_ids(trips_file)
    print(f"Unique trip_id in 'trips': {len(trip_id_set)}")

    trips_rows, total_rows = build_trip_stop_events(stop_times_file, trip_id_set)
    print(f"Total rows read from 'stop_times': {total_rows}")
    print(f"trip_id with at least one row in 'stop_times': {len(trips_rows)}")

    signature_to_trip_ids = group_trips_by_signature(trips_rows)
    duplicate_groups = find_duplicate_groups(signature_to_trip_ids)
    print_duplicate_groups_summary(duplicate_groups)

    if verify or not duplicate_groups:
        return

    trip_ids_to_eliminate = [
        trip_id
        for _, trip_ids_for_signature in duplicate_groups
        for trip_id in trip_ids_for_signature[1:]
    ]
    total_duplicate_trip_ids = sum(len(g) for _, g in duplicate_groups)

    with open(TRIP_IDS_TO_ELIMINATE_FILE, "w", encoding="utf-8") as file_handle:
        for trip_id in sorted(trip_ids_to_eliminate):
            file_handle.write(trip_id + "\n")

    print(
        f"\nTrip_id kept from groups (1 per group):"
        f" {total_duplicate_trip_ids - len(trip_ids_to_eliminate)}"
    )
    print(f"Trip_id to eliminate: {len(trip_ids_to_eliminate)}")
    print(
        f"Total valid trip_id after removing duplicates:"
        f" {len(trip_id_set) - len(trip_ids_to_eliminate)}"
    )
    print(
        f"{Path(TRIP_IDS_TO_ELIMINATE_FILE).name} generated in"
        f" {Path(TRIP_IDS_TO_ELIMINATE_FILE).relative_to(PROJECT_ROOT).parent}"
    )


if __name__ == "__main__":
    raise SystemExit(main(verify="verify" in sys.argv[1:]))
