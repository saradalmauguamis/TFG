"""Compute average inter-platform times for L9/L10 shared platforms.

The objective of this script is to determine whether the travel time between the
shared platforms of L9 and L10 is the same, given a consecutive pair of stops
and a direction.

This script scans `stop_times_doors.txt` once for all matching trips across every
route+direction and measures the time between two consecutive platform stops
(arrival at the first stop and arrival at the second). It averages those times
per line, direction and platform pair and prints comparisons between L9 and L10.
It also prints the number of samples and standard deviation for each average.

The cleaned inputs are expected under the repository at `../.src/gtfs/data/` relative to this file.
Raw GTFS source files live under `../.src/gtfs/data/0_raw/`.
"""

from __future__ import annotations

import pathlib
import sys
from typing import Dict, List, Optional, Set, Tuple

# Ensure repository root is on sys.path so `scripts` package imports work when the
# script is executed directly (for example via a virtualenv python binary).
REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from data_validation.gtfs_utils import (  # noqa: E402
    STOP_TIMES_FILE,
    STOPS_FILE,
    TRIPS_FILE,
    average_times_for_pairs,
    check_missing_files,
    print_file_disclaimer,
    collect_pair_samples_by_trip_group,
    load_stop_names,
    load_trip_ids_by_route,
    seconds_to_hms,
)
from scripts.basics import (  # noqa: E402
    subway_route_names_stop_ids,
    subway_routes_names_ids,
)

lines_south = ("L9S", "L10S")
lines_north = ("L9N", "L10N")

GroupKey = Tuple[str, int]  # (line_short_name, direction_id)
SectionData = Tuple[str, Tuple[str, str], List[Tuple[str, str]]]


def shared_platform_pairs(line_a: str, line_b: str) -> List[Tuple[str, str]]:
    """Derive consecutive directed stop pairs shared between two lines.

    args:
            line_a: Line whose stop order determines pair order.
            line_b: Line to intersect against.

    returns:
            Consecutive stop_id pairs, ordered as in line_a, restricted to stops
            present in both lines.
    """
    stops_a = subway_route_names_stop_ids.get(line_a, [])
    stops_b = set(subway_route_names_stop_ids.get(line_b, []))
    shared = [stop_id for stop_id in stops_a if stop_id in stops_b]
    return list(zip(shared, shared[1:]))


def build_trip_groups(
    section_data: Tuple[SectionData, ...],
) -> Tuple[Dict[str, GroupKey], Dict[GroupKey, List[Tuple[str, str]]]]:
    """Map every relevant trip to its (line, direction) group and its pairs.

    args:
            section_data: Per-section (name, line_names, pairs_dir0) tuples.

    returns:
            Tuple of (trip_id -> group key, group key -> directed stop pairs),
            so a single stop_times scan can serve every line and direction.
    """
    trip_id_to_group: Dict[str, GroupKey] = {}
    group_pairs: Dict[GroupKey, List[Tuple[str, str]]] = {}

    for _, line_names, pairs_dir0 in section_data:
        pairs_dir1 = [(b, a) for a, b in pairs_dir0]
        for line_name in line_names:
            route_id = subway_routes_names_ids.get(line_name)
            if not route_id:
                continue
            trip_ids_by_direction = load_trip_ids_by_route(TRIPS_FILE, route_id)
            for trip_id in trip_ids_by_direction.get(0, set()):
                trip_id_to_group[trip_id] = (line_name, 0)
            for trip_id in trip_ids_by_direction.get(1, set()):
                trip_id_to_group[trip_id] = (line_name, 1)
            group_pairs[(line_name, 0)] = pairs_dir0
            group_pairs[(line_name, 1)] = pairs_dir1

    return trip_id_to_group, group_pairs


def print_section(
    section_name: str,
    line_names: Tuple[str, str],
    pairs: List[Tuple[str, str]],
    stop_names: Dict[str, str],
    avg_by_group: Dict[
        GroupKey, Dict[Tuple[str, str], Optional[Tuple[float, int, float]]]
    ],
) -> None:
    """Print the comparison table for one section.

    args:
            section_name: Section label to print.
            line_names: Two line names to compare.
            pairs: Base stop pairs for the section.
            stop_names: Mapping from stop_id to stop_name.
            avg_by_group: Precomputed averages keyed by (line_name, direction_id).
    """
    print(f"-------{section_name}-------")
    for direction in (0, 1):
        print(f"Direction_id={direction}---")
        directed_pairs = pairs if direction == 0 else [(b, a) for a, b in pairs]

        for pair in directed_pairs:
            a, b = pair
            name_a = stop_names.get(a, a)
            name_b = stop_names.get(b, b)
            rec1 = avg_by_group.get((line_names[0], direction), {}).get(pair)
            rec2 = avg_by_group.get((line_names[1], direction), {}).get(pair)
            diff = (
                abs(rec1[0] - rec2[0])
                if rec1 is not None and rec2 is not None
                else None
            )
            print(f"  {a} ({name_a}) -> {b} ({name_b})")
            # Line 1
            if rec1 is None:
                print(f"    {line_names[0]:<5} {'N/A':>8} (N/A)")
            else:
                avg1, cnt1, std1 = rec1
                time_hms = seconds_to_hms(avg1)
                print(
                    f"    {line_names[0]:<5} {time_hms:>8} ({avg1:.2f}s) "
                    f"cnt={cnt1} stdev={std1:.2f}s"
                )
            # Line 2
            if rec2 is None:
                print(f"    {line_names[1]:<5} {'N/A':>8} (N/A)")
            else:
                avg2, cnt2, std2 = rec2
                time_hms = seconds_to_hms(avg2)
                print(
                    f"    {line_names[1]:<5} {time_hms:>8} ({avg2:.2f}s) "
                    f"cnt={cnt2} stdev={std2:.2f}s"
                )
            # Diff
            if diff is None:
                print(f"    diff  {'N/A':>8} (N/A)")
            else:
                print(f"    diff  {seconds_to_hms(diff):>8} ({diff:.2f}s)")
            print()


def main() -> None:
    """Print travel-time comparisons for the shared platforms in L9 and L10."""
    section_data: Tuple[SectionData, ...] = (
        ("South", lines_south, shared_platform_pairs(*lines_south)),
        ("North", lines_north, shared_platform_pairs(*lines_north)),
    )
    all_pairs = None
    relevant_stop_ids = None
    stop_names = None
    trip_id_to_group = None
    group_pairs = None
    samples_by_group = None
    avg_by_group = None

    check_missing_files([TRIPS_FILE, STOP_TIMES_FILE, STOPS_FILE])

    print_file_disclaimer([TRIPS_FILE, STOP_TIMES_FILE, STOPS_FILE])

    all_pairs = [pair for _, _, pairs in section_data for pair in pairs]
    relevant_stop_ids: Set[str] = {stop_id for pair in all_pairs for stop_id in pair}
    stop_names = load_stop_names(STOPS_FILE, relevant_stop_ids)

    trip_id_to_group, group_pairs = build_trip_groups(section_data)
    samples_by_group = collect_pair_samples_by_trip_group(
        STOP_TIMES_FILE, trip_id_to_group, group_pairs
    )
    avg_by_group = {
        group: average_times_for_pairs(samples)
        for group, samples in samples_by_group.items()
    }

    for index, (section_name, line_names, pairs) in enumerate(section_data):
        if index:
            print()
        print_section(section_name, line_names, pairs, stop_names, avg_by_group)


if __name__ == "__main__":
    main()
