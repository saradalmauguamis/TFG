"""Check (or verify) arrival_time == departure_time cases in stop_times.

Default run (detect, `WORKFLOW.md` step 8): reads `stop_times_sequence.txt`
from `3_stop_sequence` and `trips_cleaned.txt` from `2_duplicated_trips`.
Identifies which (line, stop_id) pairs have `arrival_time == departure_time`,
broken down by terminal vs partial occurrence, then prints the mean/stdev
door time (departure - arrival) per partial stop and per line. Writes
`doors.txt` to `4_doors_time`, consumed by `processing/4_doors_time.py`:
canonical terminals (all trips have arr == dep) get their line mean door
time, partial stops get their per-stop mean, and the FM line (no observed
door times) falls back to the mean across all other lines.

Run with a `verify` argument (`WORKFLOW.md` step 10, after
`processing/4_doors_time.py` has run) to re-run the equality check on
`stop_times_doors.txt` from `4_doors_time`: no stop should still have
`arrival_time == departure_time`. Produces no output file.
"""

from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path
from statistics import mean, stdev
from typing import Dict, List, Set, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from subway_reference.subway_lines import (  # noqa: E402
    subway_route_names_stop_ids,
    subway_routes_names_ids,
)

from data_validation.gtfs_utils import (  # noqa: E402
    DOORS_FILE,
    STOP_TIMES_DOORS_FILE,
    STOP_TIMES_SEQUENCE_FILE,
    STOPS_SUBWAY_FILE,
    TRIPS_FILE,
    check_missing_files,
    load_stop_names,
    load_trip_sequence_bounds,
    load_trip_to_line,
    parse_time_to_seconds,
    print_file_disclaimer,
    read_dict_rows,
    round_half_up_mean,
    write_rows,
)

# (equal_count, terminal_count, total_count, sample_trip_ids, door_times)
ArrDepCounts = Tuple[int, int, int, List[str], List[int]]


def build_arr_dep_counts(
    stop_times_file: str, trips_file: str, rid_to_name: Dict[str, str]
) -> Dict[Tuple[str, str], ArrDepCounts]:
    """Build (line, stop_id) -> [equal_count, terminal_count, total_count, samples, door_times].

    args:
        stop_times_file: Path to the stop_times file to scan.
        trips_file: Path to the trips file used to resolve trip_id -> line.
        rid_to_name: Mapping from route_id to line name.

    returns:
        Mapping from (line, stop_id) to its arrival/departure counters.
    """
    trip_to_line = load_trip_to_line(trips_file, rid_to_name)
    trip_bounds = load_trip_sequence_bounds(stop_times_file, set(trip_to_line))

    counts: Dict[Tuple[str, str], ArrDepCounts] = defaultdict(lambda: [0, 0, 0, [], []])
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
        if not arrival or not departure:
            continue
        key = (line, stop_id)
        counts[key][2] += 1
        if arrival == departure:
            counts[key][0] += 1
            try:
                seq = int(row.get("stop_sequence", "").strip())
                min_seq, max_seq = trip_bounds.get(trip_id, (None, None))
                if (
                    min_seq is not None
                    and max_seq is not None
                    and (seq == min_seq or seq == max_seq)
                ):
                    counts[key][1] += 1
            except Exception:
                pass
            if len(counts[key][3]) < 5:
                counts[key][3].append(trip_id)
        else:
            try:
                door_time = parse_time_to_seconds(departure) - parse_time_to_seconds(
                    arrival
                )
                if door_time >= 0:
                    counts[key][4].append(door_time)
            except Exception:
                pass
    return counts


def print_arr_dep_table(
    counts: Dict[Tuple[str, str], ArrDepCounts], stop_names: Dict[str, str]
) -> None:
    """Print the per-(line, stop_id) arrival=departure summary table.

    Only stops with at least one arrival==departure occurrence are printed.

    args:
        counts: Mapping from build_arr_dep_counts.
        stop_names: Mapping from stop_id to stop_name.
    """
    col_line, col_stop_id, col_stop_name, col_equal, col_terminal, col_total = (
        6,
        12,
        40,
        18,
        10,
        8,
    )
    header = (
        f"{'line':<{col_line}} {'stop_id':<{col_stop_id}}"
        f" {'stop_name':<{col_stop_name}} {'arrival=departure':<{col_equal}}"
        f" {'terminal%':<{col_terminal}} {'total':<{col_total}} sample_trip_ids"
    )
    print(header)
    print("-" * len(header))

    for line in subway_routes_names_ids:
        for stop_id in subway_route_names_stop_ids.get(line, []):
            key = (line, stop_id)
            if key not in counts:
                continue
            equal_count, terminal_count, total_count, sample_trips, _ = counts[key]
            if equal_count == 0:
                continue
            stop_name = stop_names.get(stop_id, "(no name)")
            terminal_pct = f"{terminal_count / equal_count:.0%}"
            print(
                f"{line:<{col_line}} {stop_id:<{col_stop_id}}"
                f" {stop_name:<{col_stop_name}} {equal_count:<{col_equal}}"
                f" {terminal_pct:<{col_terminal}} {total_count:<{col_total}}"
                f" {', '.join(sample_trips)}"
            )


def print_partial_door_times(
    counts: Dict[Tuple[str, str], ArrDepCounts], stop_names: Dict[str, str]
) -> None:
    """Print mean/stdev door time for stops with partial arrival=departure.

    For stops where only some trips have arrival == departure (i.e. not
    canonical terminals), uses only the trips where they differ.

    args:
        counts: Mapping from build_arr_dep_counts.
        stop_names: Mapping from stop_id to stop_name.
    """
    col_line, col_stop_id, col_stop_name, col_mean, col_std = 6, 12, 40, 10, 10
    header = (
        f"{'line':<{col_line}} {'stop_id':<{col_stop_id}}"
        f" {'stop_name':<{col_stop_name}} {'mean(s)':<{col_mean}} {'stdev(s)':<{col_std}} n"
    )
    print(header)
    print("-" * len(header))

    for line in subway_routes_names_ids:
        for stop_id in subway_route_names_stop_ids.get(line, []):
            key = (line, stop_id)
            if key not in counts:
                continue
            equal_count, _, total_count, _, door_times = counts[key]
            if not (0 < equal_count < total_count and door_times):
                continue
            stop_name = stop_names.get(stop_id, "(no name)")
            m = mean(door_times)
            s = stdev(door_times) if len(door_times) > 1 else 0.0
            print(
                f"{line:<{col_line}} {stop_id:<{col_stop_id}}"
                f" {stop_name:<{col_stop_name}}"
                f" {m:<{col_mean}.2f} {s:<{col_std}.2f} {len(door_times)}"
            )


def print_line_door_times(stop_times_file: str, trips_file: str) -> None:
    """Print mean/stdev door time (dep - arr) per line, excluding arr == dep rows.

    args:
        stop_times_file: Path to the stop_times file to scan.
        trips_file: Path to the trips file used to resolve trip_id -> line.
    """
    rid_to_name: Dict[str, str] = {}
    trip_to_line: Dict[str, str] = {}
    door_times_by_line: Dict[str, List[int]] = {}
    col_line, col_mean, col_std = 6, 10, 10
    header = ""

    rid_to_name = {rid: name for name, rid in subway_routes_names_ids.items()}
    trip_to_line = load_trip_to_line(trips_file, rid_to_name)

    door_times_by_line = defaultdict(list)
    for row in read_dict_rows(stop_times_file):
        trip_id = row.get("trip_id", "").strip()
        line = trip_to_line.get(trip_id)
        if not line:
            continue
        arrival = row.get("arrival_time", "").strip()
        departure = row.get("departure_time", "").strip()
        if not arrival or not departure or arrival == departure:
            continue
        try:
            door_time = parse_time_to_seconds(departure) - parse_time_to_seconds(
                arrival
            )
            if door_time >= 0:
                door_times_by_line[line].append(door_time)
        except Exception:
            pass

    header = f"{'line':<{col_line}} {'mean(s)':<{col_mean}} {'stdev(s)':<{col_std}} n"
    print(header)
    print("-" * len(header))

    for line in subway_routes_names_ids:
        door_times = door_times_by_line.get(line, [])
        if not door_times:
            print(f"{line:<{col_line}} {'N/A':<{col_mean}} {'N/A':<{col_std}} 0")
            continue
        m = mean(door_times)
        s = stdev(door_times) if len(door_times) > 1 else 0.0
        print(
            f"{line:<{col_line}} {m:<{col_mean}.2f} {s:<{col_std}.2f} {len(door_times)}"
        )


def write_doors_file(counts: Dict[Tuple[str, str], ArrDepCounts]) -> int:
    """Write doors.txt: (stop_id, line, door_seconds) for every stop with arr==dep.

    args:
        counts: Mapping from build_arr_dep_counts.

    returns:
        Number of rows written.
    """
    door_times_by_line: Dict[str, List[int]] = {}
    all_other_times: List[int] = []
    fm_fallback = 0
    rows: List[Dict[str, object]] = []

    door_times_by_line = defaultdict(list)
    for (line, _), (_, _, _, _, door_times) in counts.items():
        door_times_by_line[line].extend(door_times)

    all_other_times = [
        t for line, times in door_times_by_line.items() if line != "FM" for t in times
    ]
    fm_fallback = round_half_up_mean(all_other_times)

    rows = []
    for line in subway_routes_names_ids:
        for stop_id in subway_route_names_stop_ids.get(line, []):
            key = (line, stop_id)
            if key not in counts:
                continue
            equal_count, _, total_count, _, door_times = counts[key]
            if equal_count == 0:
                continue
            if equal_count == total_count:
                line_times = door_times_by_line.get(line, [])
                door_seconds = (
                    fm_fallback if not line_times else round_half_up_mean(line_times)
                )
            else:
                door_seconds = round_half_up_mean(door_times)
            rows.append(
                {"stop_id": stop_id, "line": line, "door_seconds": door_seconds}
            )

    write_rows(DOORS_FILE, ["stop_id", "line", "door_seconds"], rows)
    return len(rows)


def main(verify: bool = False) -> None:
    """Detect arrival==departure stops and write doors.txt, or verify the fix.

    args:
        verify: When True, check `stop_times_doors.txt` (after
            `processing/4_doors_time.py`) for leftover arrival==departure
            rows instead of detecting fresh ones; does not write `doors.txt`.
    """
    stop_times_file = STOP_TIMES_DOORS_FILE if verify else STOP_TIMES_SEQUENCE_FILE
    rid_to_name: Dict[str, str] = {}
    counts: Dict[Tuple[str, str], ArrDepCounts] = {}
    equal_stop_ids: Set[str] = set()
    stop_names: Dict[str, str] = {}
    rows_written = 0

    check_missing_files([stop_times_file, TRIPS_FILE, STOPS_SUBWAY_FILE])
    print_file_disclaimer(
        [
            (stop_times_file, "stop_times"),
            (TRIPS_FILE, "trips"),
            (STOPS_SUBWAY_FILE, "stops"),
        ]
    )

    rid_to_name = {rid: name for name, rid in subway_routes_names_ids.items()}
    counts = build_arr_dep_counts(stop_times_file, TRIPS_FILE, rid_to_name)
    equal_stop_ids = {sid for (_, sid), (eq, *_) in counts.items() if eq > 0}

    if verify:
        print(
            "Checking that no stop still has arrival_time == departure_time"
            " after the door-time fix:\n"
        )
        if not equal_stop_ids:
            print(
                "All correct: no stop has arrival_time == departure_time"
                " after applying door times."
            )
            return
        stop_names = load_stop_names(STOPS_SUBWAY_FILE, stop_ids=equal_stop_ids)
        print(
            f"FOUND {len(equal_stop_ids)} stops still with arrival_time == departure_time:"
        )
        print_arr_dep_table(counts, stop_names)
        return

    stop_names = load_stop_names(STOPS_SUBWAY_FILE, stop_ids=equal_stop_ids)
    print(
        "Which (line, stop_id) pairs have arrival_time == departure_time, what fraction"
        " of those occurrences happen at a terminal stop, and (for non-canonical terminals)"
        " the door time of the trips where they differ:\n"
    )
    print_arr_dep_table(counts, stop_names)
    print()
    print(
        "For stops where only SOME trips have arrival == departure (not canonical"
        " terminals), mean/stdev door time using only the trips where they differ:\n"
    )
    print_partial_door_times(counts, stop_names)
    print()
    print(
        "Per-line mean/stdev door time (departure - arrival), excluding"
        " arrival == departure rows:\n"
    )
    print_line_door_times(stop_times_file, TRIPS_FILE)
    print()
    print(
        "Writing doors.txt: one row per (stop_id, line) with any arrival == departure"
        " occurrence. Canonical terminals (all trips equal) get their line mean door time,"
        " partial stops get their per-stop mean, FM falls back to the mean of all other"
        " lines.\n"
    )
    rows_written = write_doors_file(counts)
    print(
        f"doors.txt written to {Path(DOORS_FILE).relative_to(PROJECT_ROOT)} ({rows_written} rows)"
    )


if __name__ == "__main__":
    raise SystemExit(main(verify="verify" in sys.argv[1:]))
