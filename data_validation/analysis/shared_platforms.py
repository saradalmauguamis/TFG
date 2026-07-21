"""Compute average inter-platform times for shared platforms.

The objective of this script is to determine whether the travel time between
a platform shared by several lines is the same for each line, given a
consecutive pair of stops and a direction.

Shared platforms are detected generically via
`gtfs_utils.build_shared_platform_lines` (no line names are hardcoded), then
grouped by the exact tuple of lines that serve each one. This script scans
`stop_times_doors.txt` once for all matching trips across every route+direction
and measures the time between two consecutive platform stops (arrival at the
first stop and arrival at the second). It averages those times per line,
direction and platform pair, and prints one row per line for each pair, plus
the spread (max - min) across whichever lines have data. This generalizes to
however many lines share a given platform, not just two.

The cleaned inputs are expected under `data/` at the repository root.
Raw GTFS source files live under `data/0_raw/`.
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
    STOP_TIMES_DOORS_FILE,
    STOPS_SUBWAY_FILE,
    TRIPS_FILE,
    average_times_for_pairs,
    build_shared_platform_lines,
    check_missing_files,
    print_file_disclaimer,
    collect_pair_samples_by_trip_group,
    consecutive_pairs,
    load_stop_names,
    load_trip_ids_by_route,
    seconds_to_hms,
)
from subway_reference.subway_lines import (  # noqa: E402
    subway_route_names_stop_ids,
    subway_routes_names_ids,
)

GroupKey = Tuple[str, int]  # (line_short_name, direction_id)
PairRecord = Tuple[float, int, float]


def group_shared_stops_by_lines(
    shared_platform_lines: Dict[str, List[str]]
) -> Dict[Tuple[str, ...], List[str]]:
    """Group shared stop_ids by the exact tuple of lines that serve them.

    args:
            shared_platform_lines: Shared stop_id -> ordered list of lines,
                from `build_shared_platform_lines`.

    returns:
            Mapping from a tuple of line names to the shared stop_ids they
            serve together, in the route order `build_shared_platform_lines`
            preserves.
    """
    stops_by_lines: Dict[Tuple[str, ...], List[str]] = {}
    for stop_id, lines in shared_platform_lines.items():
        stops_by_lines.setdefault(tuple(lines), []).append(stop_id)
    return stops_by_lines


def build_pairs_by_lines(
    stops_by_lines: Dict[Tuple[str, ...], List[str]]
) -> Dict[Tuple[str, ...], List[Tuple[str, str]]]:
    """Turn each line group's ordered stops into consecutive directed pairs.

    args:
            stops_by_lines: Line-tuple -> ordered shared stop_ids.

    returns:
            Line-tuple -> consecutive directed stop pairs.
    """
    return {
        line_names: consecutive_pairs(stop_ids)
        for line_names, stop_ids in stops_by_lines.items()
    }


def build_trip_groups(
    pairs_by_lines: Dict[Tuple[str, ...], List[Tuple[str, str]]]
) -> Tuple[Dict[str, GroupKey], Dict[GroupKey, List[Tuple[str, str]]]]:
    """Map every relevant trip to its (line, direction) group and its pairs.

    args:
            pairs_by_lines: Line-tuple -> consecutive directed stop pairs.

    returns:
            Tuple of (trip_id -> group key, group key -> directed stop pairs),
            so a single stop_times scan can serve every line and direction.
    """
    trip_id_to_group: Dict[str, GroupKey] = {}
    group_pairs: Dict[GroupKey, List[Tuple[str, str]]] = {}

    for line_names, pairs_dir0 in pairs_by_lines.items():
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
    line_names: Tuple[str, ...],
    pairs: List[Tuple[str, str]],
    stop_names: Dict[str, str],
    avg_by_group: Dict[GroupKey, Dict[Tuple[str, str], Optional[PairRecord]]],
) -> None:
    """Print the comparison table for one group of lines sharing platforms.

    args:
            line_names: Lines that share this group's platforms.
            pairs: Base stop pairs for the group.
            stop_names: Mapping from stop_id to stop_name.
            avg_by_group: Precomputed averages keyed by (line_name, direction_id).
    """
    print(f"-------{'/'.join(line_names)}-------")
    for direction in (0, 1):
        print(f"Direction_id={direction}---")
        directed_pairs = pairs if direction == 0 else [(b, a) for a, b in pairs]

        for pair in directed_pairs:
            a, b = pair
            name_a = stop_names.get(a, a)
            name_b = stop_names.get(b, b)
            records = {
                line: avg_by_group.get((line, direction), {}).get(pair)
                for line in line_names
            }

            print(f"  {a} ({name_a}) -> {b} ({name_b})")
            for line in line_names:
                record = records[line]
                if record is None:
                    print(f"    {line:<5} {'N/A':>8} (N/A)")
                else:
                    avg, count, std = record
                    time_hms = seconds_to_hms(avg)
                    print(
                        f"    {line:<5} {time_hms:>8} ({avg:.2f}s) "
                        f"cnt={count} stdev={std:.2f}s"
                    )

            averages = [record[0] for record in records.values() if record is not None]
            if len(averages) >= 2:
                diff = max(averages) - min(averages)
                print(f"    diff  {seconds_to_hms(diff):>8} ({diff:.2f}s)")
            else:
                print(f"    diff  {'N/A':>8} (N/A)")
            print()


def main() -> None:
    """Print travel-time comparisons for every shared-platform line group."""
    shared_platform_lines: Dict[str, List[str]] = {}
    stops_by_lines: Dict[Tuple[str, ...], List[str]] = {}
    pairs_by_lines: Dict[Tuple[str, ...], List[Tuple[str, str]]] = {}
    relevant_stop_ids: Set[str] = set()
    stop_names: Dict[str, str] = {}
    trip_id_to_group: Dict[str, GroupKey] = {}
    group_pairs: Dict[GroupKey, List[Tuple[str, str]]] = {}
    samples_by_group: Dict[GroupKey, Dict[Tuple[str, str], List[int]]] = {}
    avg_by_group: Dict[GroupKey, Dict[Tuple[str, str], Optional[PairRecord]]] = {}
    check_missing_files([STOP_TIMES_DOORS_FILE, STOPS_SUBWAY_FILE, TRIPS_FILE])

    print_file_disclaimer([STOP_TIMES_DOORS_FILE, STOPS_SUBWAY_FILE, TRIPS_FILE])

    shared_platform_lines = build_shared_platform_lines(subway_route_names_stop_ids)
    stops_by_lines = group_shared_stops_by_lines(shared_platform_lines)
    pairs_by_lines = build_pairs_by_lines(stops_by_lines)

    relevant_stop_ids: Set[str] = {
        stop_id
        for pairs in pairs_by_lines.values()
        for pair in pairs
        for stop_id in pair
    }
    stop_names = load_stop_names(STOPS_SUBWAY_FILE, relevant_stop_ids)

    trip_id_to_group, group_pairs = build_trip_groups(pairs_by_lines)
    samples_by_group = collect_pair_samples_by_trip_group(
        STOP_TIMES_DOORS_FILE, trip_id_to_group, group_pairs
    )
    avg_by_group = {
        group: average_times_for_pairs(samples)
        for group, samples in samples_by_group.items()
    }

    for index, (line_names, pairs) in enumerate(pairs_by_lines.items()):
        if index:
            print()
        print_section(line_names, pairs, stop_names, avg_by_group)


if __name__ == "__main__":
    main()
