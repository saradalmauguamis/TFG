"""Check route-level trip metadata consistency, especially headsign and direction mapping.

Independent of run order (`WORKFLOW.md`): only needs `processing/1_subway.py`
to have run. For each route_id, validates that there are exactly two observed
trip_headsign values and that each maps to a distinct direction_id. Produces
no output file.
"""

from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Set

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from data_validation.gtfs_utils import (  # noqa: E402
    ROUTES_FILE,
    TRIPS_SUBWAY_FILE,
    check_missing_files,
    print_file_disclaimer,
    read_dict_rows,
)


def main() -> None:
    """Validate trip_headsign and direction_id pairing consistency per route."""
    route_short_name: Dict[str, str] = {}
    by_route: Dict[str, Dict[str, Set[str]]] = {}
    total_trip_rows = 0
    considered_trip_rows = 0
    routes_without_trips: List[str] = []
    ok_routes = 0
    problematic_routes = 0

    check_missing_files([ROUTES_FILE, TRIPS_SUBWAY_FILE])

    print_file_disclaimer(
        [
            (ROUTES_FILE, "routes"),
            (TRIPS_SUBWAY_FILE, "trips"),
        ]
    )

    print("\n----- direction_id and trip_headsign from 'trips' are paired? -----")

    for r in read_dict_rows(ROUTES_FILE):
        rid = r.get("route_id", "").strip()
        route_short_name[rid] = r.get("route_short_name", "").strip()

    if not route_short_name:
        print("No route_id found in 'routes'.")
        return

    by_route = defaultdict(lambda: defaultdict(set))
    for r in read_dict_rows(TRIPS_SUBWAY_FILE):
        total_trip_rows += 1
        rid = r.get("route_id", "").strip()
        if rid not in route_short_name:
            continue
        considered_trip_rows += 1
        headsign = r.get("trip_headsign", "").strip()
        direction = r.get("direction_id", "").strip()
        by_route[rid][headsign].add(direction)

    print(f"Number of routes in scope: {len(route_short_name)}")
    print(f"Total rows in 'trips': {total_trip_rows}")
    print(f"Rows considered (route_id in scope): {considered_trip_rows}")

    routes_without_trips = sorted(
        rid for rid in route_short_name if rid not in by_route
    )
    if routes_without_trips:
        print(
            f"WARNING: {len(routes_without_trips)} routes in scope have no trips in 'trips'."
        )
        for rid in routes_without_trips:
            print(f"- {rid} ({route_short_name.get(rid, '')})")

    for rid in sorted(by_route):
        short_name = route_short_name.get(rid, "")
        hd_map = by_route[rid]
        headsigns = sorted(hd_map.keys())
        all_dirs = sorted({d for dirs in hd_map.values() for d in dirs})

        print(f"\nRoute {rid} ({short_name}):")
        print(f"- trip_headsign values: {len(headsigns)}")
        print(f"- direction_id values: {len(all_dirs)}")

        issues: List[str] = []
        if len(headsigns) != 2:
            issues.append(f"expected 2 trip_headsign values, found {len(headsigns)}")
        if len(all_dirs) != 2:
            issues.append(f"expected 2 direction_id values, found {len(all_dirs)}")

        mapping: Dict[str, str] = {}
        ambiguous = []
        for h in headsigns:
            dirs = sorted(d for d in hd_map[h] if d != "")
            if len(dirs) == 1:
                mapping[h] = dirs[0]
            else:
                ambiguous.append((h, dirs))

        for h, dirs in ambiguous:
            issues.append(
                f"headsign {h!r} maps to multiple direction_id values: {dirs}"
            )

        if len(mapping) == 2 and len(set(mapping.values())) != 2:
            issues.append("both trip_headsign values map to the same direction_id")

        if not issues and len(mapping) == 2:
            h1, h2 = sorted(mapping.keys())
            print("All correct:")
            print(f"- {h1!r} -> direction_id={mapping[h1]!r}")
            print(f"- {h2!r} -> direction_id={mapping[h2]!r}")
            ok_routes += 1
        else:
            problematic_routes += 1
            print(f"MISSING clear headsign-direction pairing for route {rid}:")
            for msg in issues:
                print(f"- {msg}")
            for h in sorted(hd_map.keys()):
                print(f"- {h!r} appears with direction_id values: {sorted(hd_map[h])}")

    print("\nSummary:")
    print(f"- Routes checked with trips: {len(by_route)}")
    print(f"- Routes with clear pairing: {ok_routes}")
    print(f"- Routes with issues: {problematic_routes}")


if __name__ == "__main__":
    raise SystemExit(main())
