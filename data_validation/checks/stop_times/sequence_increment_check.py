"""Check that stop_sequence increments by one for every subway trip.

Reads `stop_times_subway.txt`/`trips_subway.txt` from `1_subway`. Independent
of the rest of the core pipeline: trip duplicates don't affect a trip's own
sequence continuity, so this only needs `processing/1_subway.py` to have run.
Produces no output file.
"""

from __future__ import annotations

import os
import sys
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, List, Set

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from data_validation.gtfs_utils import (  # noqa: E402
    STOP_TIMES_SUBWAY_FILE,
    TRIPS_SUBWAY_FILE,
    check_missing_files,
    check_trip,
    load_trip_ids,
    print_file_disclaimer,
    read_dict_rows,
)


def main() -> None:
    """Check that each trip has stop_sequence values that increment by one."""
    trip_ids: Set[str] = set()
    seq_by_trip: Dict[str, Set[int]] = {}
    dict_seq: Dict[str, List[int]] = {}
    violations_total = 0
    max_workers = 0

    check_missing_files([STOP_TIMES_SUBWAY_FILE, TRIPS_SUBWAY_FILE])

    print_file_disclaimer(
        [
            (STOP_TIMES_SUBWAY_FILE, "stop_times"),
            (TRIPS_SUBWAY_FILE, "trips"),
        ]
    )

    trip_ids = load_trip_ids(TRIPS_SUBWAY_FILE)

    print(f"Number of trip_id in 'trips': {len(trip_ids)}")

    seq_by_trip = defaultdict(set)
    for row in read_dict_rows(STOP_TIMES_SUBWAY_FILE):
        trip_id = row.get("trip_id", "")
        if trip_id not in trip_ids:
            continue
        try:
            seq = int(row.get("stop_sequence", ""))
        except Exception:
            continue
        seq_by_trip[trip_id].add(seq)

    dict_seq = {
        trip_id: sorted(seq_by_trip.get(trip_id, set())) for trip_id in trip_ids
    }

    max_workers = min(8, (os.cpu_count() or 4))
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(check_trip, trip_id, dict_seq[trip_id]): trip_id
            for trip_id in trip_ids
        }
        for future in as_completed(futures):
            messages = future.result()
            violations_total += len(messages)
            for message in messages:
                print(message)

    if violations_total == 0:
        print(
            "Correct: all trips in 'trips' have stop_sequence in 'stop_times'"
            " that increments by one."
        )
    else:
        print(f"Total violations detected: {violations_total}")


if __name__ == "__main__":
    raise SystemExit(main())
