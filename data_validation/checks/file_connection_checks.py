"""Check that file-level identifiers referenced across GTFS tables actually exist where expected.

Independent of run order (`WORKFLOW.md`): only needs `processing/1_subway.py`
to have run. Checks that all `stop_id` from `pathways`/`transfers`/`stop_times`
exist in `stops`, all `route_id` from `trips` exist in `routes`, and all
`trip_id` from `stop_times` exist in `trips`. Produces no output file.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import List, Set

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from data_validation.gtfs_utils import (  # noqa: E402
    PATHWAYS_RAW_FILE,
    ROUTES_FILE,
    STOPS_SUBWAY_FILE,
    STOP_TIMES_SUBWAY_FILE,
    TRANSFERS_RAW_FILE,
    TRIPS_SUBWAY_FILE,
    check_missing_files,
    load_from_stop_ids,
    load_route_ids,
    load_stop_ids,
    load_to_stop_ids,
    load_trip_ids,
    print_file_disclaimer,
)


def main() -> None:
    """Validate that stop_id, route_id, and trip_id references are consistent across files."""
    pathways_from_stop_ids: Set[str] = set()
    pathways_to_stop_ids: Set[str] = set()
    transfers_from_stop_ids: Set[str] = set()
    transfers_to_stop_ids: Set[str] = set()
    stop_times_stop_ids: Set[str] = set()
    stops_stop_ids: Set[str] = set()
    missing_pathways_from: List[str] = []
    missing_pathways_to: List[str] = []
    missing_transfers_from: List[str] = []
    missing_transfers_to: List[str] = []
    missing_stop_times: List[str] = []
    trips_route_ids: Set[str] = set()
    routes_route_ids: Set[str] = set()
    missing_route_ids: List[str] = []
    stop_times_trip_ids: Set[str] = set()
    trips_trip_ids: Set[str] = set()
    missing_trip_ids: List[str] = []

    check_missing_files(
        [
            PATHWAYS_RAW_FILE,
            TRANSFERS_RAW_FILE,
            STOP_TIMES_SUBWAY_FILE,
            STOPS_SUBWAY_FILE,
            TRIPS_SUBWAY_FILE,
            ROUTES_FILE,
        ]
    )

    pathways_from_stop_ids = load_from_stop_ids(PATHWAYS_RAW_FILE)
    pathways_to_stop_ids = load_to_stop_ids(PATHWAYS_RAW_FILE)
    transfers_from_stop_ids = load_from_stop_ids(TRANSFERS_RAW_FILE)
    transfers_to_stop_ids = load_to_stop_ids(TRANSFERS_RAW_FILE)
    stop_times_stop_ids = load_stop_ids(STOP_TIMES_SUBWAY_FILE)
    stops_stop_ids = load_stop_ids(STOPS_SUBWAY_FILE)

    print_file_disclaimer(
        [
            (PATHWAYS_RAW_FILE, "pathways"),
            (TRANSFERS_RAW_FILE, "transfers"),
            (STOP_TIMES_SUBWAY_FILE, "stop_times"),
            (STOPS_SUBWAY_FILE, "stops"),
            (TRIPS_SUBWAY_FILE, "trips"),
            (ROUTES_FILE, "routes"),
        ]
    )

    missing_pathways_from = sorted(
        ids for ids in pathways_from_stop_ids if ids not in stops_stop_ids
    )
    missing_pathways_to = sorted(
        ids for ids in pathways_to_stop_ids if ids not in stops_stop_ids
    )
    missing_transfers_from = sorted(
        ids for ids in transfers_from_stop_ids if ids not in stops_stop_ids
    )
    missing_transfers_to = sorted(
        ids for ids in transfers_to_stop_ids if ids not in stops_stop_ids
    )
    missing_stop_times = sorted(
        ids for ids in stop_times_stop_ids if ids not in stops_stop_ids
    )

    print(
        "\n----- All stop_id from 'pathways', 'transfers' and 'stop_times'"
        " exist in 'stops'? -----"
    )
    if not missing_pathways_from:
        print(" - All correct: no from_stop_id from 'pathways' is missing in 'stops'")
    else:
        print(
            f" - MISSING {len(missing_pathways_from)} from_stop_id from 'pathways' in 'stops':"
        )
        for sid in missing_pathways_from:
            print("   -", sid)

    if not missing_pathways_to:
        print(" - All correct: no to_stop_id from 'pathways' is missing in 'stops'")
    else:
        print(
            f" - MISSING {len(missing_pathways_to)} to_stop_id from 'pathways' in 'stops':"
        )
        for sid in missing_pathways_to:
            print("   -", sid)

    if not missing_transfers_from:
        print(" - All correct: no from_stop_id from 'transfers' is missing in 'stops'")
    else:
        print(
            f" - MISSING {len(missing_transfers_from)} from_stop_id from"
            f" 'transfers' in 'stops':"
        )
        for sid in missing_transfers_from:
            print("   -", sid)

    if not missing_transfers_to:
        print(" - All correct: no to_stop_id from 'transfers' is missing in 'stops'")
    else:
        print(
            f" - MISSING {len(missing_transfers_to)} to_stop_id from 'transfers' in 'stops':"
        )
        for sid in missing_transfers_to:
            print("   -", sid)

    if not missing_stop_times:
        print(" - All correct: no stop_id from 'stop_times' is missing in 'stops'")
    else:
        print(
            f" - MISSING {len(missing_stop_times)} stop_id from 'stop_times' in 'stops':"
        )
        for sid in missing_stop_times:
            print("   -", sid)

    print("\n----- All route_id from 'trips' exist in 'routes'? -----")
    trips_route_ids = load_route_ids(TRIPS_SUBWAY_FILE)
    routes_route_ids = load_route_ids(ROUTES_FILE)
    missing_route_ids = sorted(
        ids for ids in trips_route_ids if ids not in routes_route_ids
    )

    print(f"Unique route_id in 'trips': {len(trips_route_ids)}")
    print(f"Unique route_id in 'routes': {len(routes_route_ids)}")

    if not missing_route_ids:
        print("All correct: all route_id present in 'trips' also appear in 'routes'.")
    else:
        print(
            f"MISSING {len(missing_route_ids)} route_id"
            f" (present in 'trips' but not in 'routes'):"
        )
        for rid in missing_route_ids:
            print(f"- {rid}")

    stop_times_trip_ids = load_trip_ids(STOP_TIMES_SUBWAY_FILE)
    trips_trip_ids = load_trip_ids(TRIPS_SUBWAY_FILE)
    missing_trip_ids = sorted(
        ids for ids in stop_times_trip_ids if ids not in trips_trip_ids
    )

    print(f"Unique trip_id in 'stop_times': {len(stop_times_trip_ids)}")
    print(f"Unique trip_id in 'trips': {len(trips_trip_ids)}")

    print("\n----- All trip_id from 'stop_times' exist in 'trips'? -----")
    if not missing_trip_ids:
        print(
            "All correct: all trip_id present in 'stop_times' also appear in 'trips'."
        )
    else:
        print(
            f"MISSING {len(missing_trip_ids)} trip_id"
            f" (present in 'stop_times' but not in 'trips'):"
        )
        for tid in missing_trip_ids:
            print(f"- {tid}")


if __name__ == "__main__":
    raise SystemExit(main())
