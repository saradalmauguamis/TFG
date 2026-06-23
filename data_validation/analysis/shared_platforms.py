"""Compute average inter-platform times for L9/L10 shared platforms.

The objective of this script is to determine whether the travel time between the
shared platforms of L9 and L10 is the same, given a consecutive pair of stops
and a direction.

This script scans all matching trips for each route+direction and measures the
time between two consecutive platform stops (arrival at the first stop and
arrival at the second) from `stop_times_subway_cleaned.txt`. It averages those times
per line, direction and platform pair and prints comparisons between L9 and L10.
It also prints the number of samples and standard deviation for each average.

The cleaned inputs are expected under the repository at `../.src/gtfs/data/` relative to this file.
Raw GTFS source files live under `../.src/gtfs/data/0_raw/`.
"""

from __future__ import annotations

import pathlib
import sys
from collections import defaultdict
from statistics import mean, stdev
from typing import DefaultDict, Dict, List, Optional, Set, Tuple

# Ensure repository root is on sys.path so `scripts` package imports work when the
# script is executed directly (for example via a virtualenv python binary).
REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from data_validation.gtfs_utils import (  # noqa: E402
    SECONDS_PER_DAY,
    STOP_TIMES_FILE,
    STOPS_FILE,
    TRIPS_FILE,
    check_missing_files,
    print_file_disclaimer,
    load_stop_names,
    load_trip_ids_by_route,
    parse_time_to_seconds,
    read_dict_rows,
    seconds_to_hms,
)
from scripts.basics import (  # noqa: E402
    subway_route_names_stop_ids,
    subway_routes_names_ids,
)

lines_south = ("L9S", "L10S")
lines_north = ("L9N", "L10N")


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


def collect_pair_samples_for_line(
    line_short_name: str,
    direction_id: int,
    pairs: List[Tuple[str, str]],
) -> Dict[Tuple[str, str], List[int]]:
    """Collect travel-time samples for one line, direction, and stop pairs.

    args:
            line_short_name: Short name of the line, such as L9S.
            direction_id: Direction to inspect.
            pairs: Directed stop pairs to keep.

    returns:
            Dictionary mapping each requested pair to its travel-time samples.
    """
    route_id = subway_routes_names_ids.get(line_short_name)
    pair_set = set(pairs)
    target_stop_ids = {stop_id for pair in pairs for stop_id in pair}
    samples: DefaultDict[Tuple[str, str], List[int]] = defaultdict(list)
    trip_rows: DefaultDict[str, List[Tuple[int, str, str, str]]] = defaultdict(list)
    trip_ids_by_direction: Dict[int, Set[str]] = {}
    relevant_trip_ids: Set[str] = set()

    if not route_id:
        return {pair: [] for pair in pairs}

    trip_ids_by_direction = load_trip_ids_by_route(TRIPS_FILE, route_id)
    relevant_trip_ids = trip_ids_by_direction.get(direction_id, set())

    for row in read_dict_rows(STOP_TIMES_FILE):
        trip_id = row.get("trip_id", "")
        if trip_id not in relevant_trip_ids:
            continue

        stop_id = row.get("stop_id", "")
        sequence_text = row.get("stop_sequence", "")
        arrival_time = row.get("arrival_time", "")
        departure_time = row.get("departure_time", "")
        if not stop_id or not sequence_text:
            continue
        if stop_id not in target_stop_ids:
            continue

        try:
            stop_sequence = int(sequence_text)
        except ValueError:
            continue

        trip_rows[trip_id].append(
            (stop_sequence, stop_id, arrival_time, departure_time)
        )

    for rows in trip_rows.values():  # Implicit for each trip_id of trip_rows
        rows.sort(key=lambda item: item[0])
        for current_row, next_row in zip(rows, rows[1:]):
            current_sequence, current_stop_id, current_arrival, _ = current_row
            next_sequence, next_stop_id, next_arrival, _ = next_row
            if next_sequence != current_sequence + 1:
                continue
            pair = (current_stop_id, next_stop_id)
            if pair not in pair_set:
                continue
            if not current_arrival or not next_arrival:
                continue

            travel_time = parse_time_to_seconds(next_arrival) - parse_time_to_seconds(
                current_arrival
            )
            while travel_time < 0:  # Case of passing midnight, add 24h until positive
                travel_time += SECONDS_PER_DAY
            samples[pair].append(travel_time)

    return {pair: samples.get(pair, []) for pair in pairs}


def average_times_for_line(
    line_short_name: str,
    direction_id: int,
    pairs: List[Tuple[str, str]],
) -> Dict[Tuple[str, str], Optional[Tuple[float, int, float]]]:
    """Return average travel time per directed pair for one line and direction.

    args:
            line_short_name: Short name of the line, such as L9S.
            direction_id: Direction to inspect.
            pairs: Directed stop pairs to average.

    returns:
            Dictionary mapping each pair to its average travel time, sample count,
            and standard deviation, or None.
    """
    pair_samples = collect_pair_samples_for_line(line_short_name, direction_id, pairs)
    # Return tuple (mean_seconds, count, stdev) or None when no samples
    results: Dict[Tuple[str, str], Optional[Tuple[float, int, float]]] = {}
    for pair, samples in pair_samples.items():
        if not samples:
            results[pair] = None
            continue
        count = len(samples)
        avg = mean(samples)
        std = stdev(samples) if count > 1 else 0.0
        results[pair] = (avg, count, std)
    return results


def print_section(
    section_name: str,
    line_names: Tuple[str, str],
    pairs: List[Tuple[str, str]],
    stop_names: Dict[str, str],
) -> None:
    """Print the comparison table for one section.

    args:
            section_name: Section label to print.
            line_names: Two line names to compare.
            pairs: Base stop pairs for the section.
            stop_names: Mapping from stop_id to stop_name.
    """
    # Mapping: line name --> {(stop_a, stop_b): (avg_seconds, count, stdev) or None}
    line_pair_avgs: Dict[
        str, Dict[Tuple[str, str], Optional[Tuple[float, int, float]]]
    ] = {}
    directed_pairs: List[Tuple[str, str]] = []

    print(f"-------{section_name}-------")
    for direction in (0, 1):
        print(f"Direction_id={direction}---")
        directed_pairs = pairs if direction == 0 else [(b, a) for a, b in pairs]
        for line_name in line_names:
            line_pair_avgs[line_name] = average_times_for_line(
                line_name, direction, directed_pairs
            )

        for pair in directed_pairs:
            a, b = pair
            name_a = stop_names.get(a, a)
            name_b = stop_names.get(b, b)
            rec1 = line_pair_avgs[line_names[0]].get(pair)
            rec2 = line_pair_avgs[line_names[1]].get(pair)
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
    section_data = (
        ("South", lines_south, shared_platform_pairs(*lines_south)),
        ("North", lines_north, shared_platform_pairs(*lines_north)),
    )
    all_pairs: List[Tuple[str, str]] = []
    relevant_stop_ids: Set[str] = set()
    stop_names: Dict[str, str] = {}

    check_missing_files([TRIPS_FILE, STOP_TIMES_FILE, STOPS_FILE])

    print_file_disclaimer([TRIPS_FILE, STOP_TIMES_FILE, STOPS_FILE])

    all_pairs = [pair for _, _, pairs in section_data for pair in pairs]
    relevant_stop_ids = {stop_id for pair in all_pairs for stop_id in pair}
    stop_names = load_stop_names(STOPS_FILE, relevant_stop_ids)

    for index, (section_name, line_names, pairs) in enumerate(section_data):
        if index:
            print()
        print_section(section_name, line_names, pairs, stop_names)


if __name__ == "__main__":
    main()
