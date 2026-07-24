"""Apply door-open times to terminal stops in stop_times.

Reads doors.txt from DOORS_BASE (one row per (stop_id, line)) and
stop_times_sequence.txt. For every row where arrival_time == departure_time
the script looks up the door-open duration for that (stop_id, line) pair and
adjusts whichever timestamp is synthetic:

  - first stop of the trip (min stop_sequence): arrival_time = departure_time - door_seconds
  - last stop of the trip  (max stop_sequence): departure_time = arrival_time + door_seconds

All other rows are passed through unchanged. Output is written to
stop_times_doors.txt in DOORS_BASE.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from subway_reference.subway_lines import subway_routes_names_ids  # noqa: E402
from data_validation.gtfs_utils import (  # noqa: E402
    _PROJECT_ROOT,
    DOORS_FILE,
    STOP_TIMES_SEQUENCE_FILE,
    STOP_TIMES_DOORS_FILE,
    TRIPS_FILE,
    check_missing_files,
    print_file_disclaimer,
    load_trip_to_line,
    load_trip_sequence_bounds,
    parse_time_to_seconds,
    format_seconds,
    read_dict_rows,
    read_header,
    write_rows,
)


def load_door_seconds(file_path: str) -> Dict[Tuple[str, str], int]:
    """Return a mapping of (stop_id, line) to door_seconds from doors.txt.

    args:
        file_path: Path to doors.txt.

    returns:
        Mapping from (stop_id, line) to door open time in seconds.
    """
    door_seconds: Dict[Tuple[str, str], int] = {}
    for row in read_dict_rows(file_path):
        stop_id = row.get("stop_id", "").strip()
        line = row.get("line", "").strip()
        secs_text = row.get("door_seconds", "").strip()
        if not stop_id or not line or not secs_text:
            continue
        try:
            door_seconds[(stop_id, line)] = int(secs_text)
        except ValueError:
            continue
    return door_seconds


def apply_door_times(
    input_path: str,
    output_path: str,
    trip_to_line: Dict[str, str],
    trip_bounds: Dict[str, Tuple[int, int]],
    door_seconds: Dict[Tuple[str, str], int],
) -> Tuple[int, int]:
    """Read stop_times, adjust arr/dep for terminal arr==dep rows, and write output.

    For first stops (min stop_sequence): arrival_time = departure_time - door_seconds.
    For last stops  (max stop_sequence): departure_time = arrival_time + door_seconds.

    args:
        input_path: Path to stop_times_sequence.txt.
        output_path: Path where stop_times_doors.txt will be written.
        trip_to_line: Mapping from trip_id to line name.
        trip_bounds: Mapping from trip_id to (min_seq, max_seq).
        door_seconds: Mapping from (stop_id, line) to door open seconds.

    returns:
        Tuple of (total_rows, modified_rows).
    """
    total_rows = 0
    modified_rows = 0
    rows_out = []
    fieldnames = read_header(input_path)

    for row in read_dict_rows(input_path):
        total_rows += 1
        arrival = row.get("arrival_time", "")
        departure = row.get("departure_time", "")

        if not arrival or not departure or arrival != departure:
            rows_out.append(row)
            continue

        trip_id = row.get("trip_id", "")
        stop_id = row.get("stop_id", "")
        line = trip_to_line.get(trip_id)
        bounds = trip_bounds.get(trip_id)

        if not line or not bounds:
            rows_out.append(row)
            continue

        try:
            seq = int(row.get("stop_sequence", ""))
        except ValueError:
            rows_out.append(row)
            continue

        min_seq, max_seq = bounds
        if seq != min_seq and seq != max_seq:
            rows_out.append(row)
            continue

        door = door_seconds.get((stop_id, line))
        if door is None:
            rows_out.append(row)
            continue

        dep_secs = parse_time_to_seconds(departure)
        if seq == min_seq:
            row["arrival_time"] = format_seconds(dep_secs - door)
        else:
            row["departure_time"] = format_seconds(dep_secs + door)
        modified_rows += 1
        rows_out.append(row)

    write_rows(output_path, fieldnames, rows_out)

    return total_rows, modified_rows


def main() -> None:
    """Apply door-open times to terminal stops and write stop_times_doors.txt."""
    door_seconds: Dict[Tuple[str, str], int] = {}
    rid_to_name: Dict[str, str] = {}
    trip_to_line: Dict[str, str] = {}
    trip_bounds: Dict[str, Tuple[int, int]] = {}
    total = 0
    modified = 0

    check_missing_files([DOORS_FILE, STOP_TIMES_SEQUENCE_FILE, TRIPS_FILE])
    print_file_disclaimer(
        [
            (DOORS_FILE, "doors"),
            (STOP_TIMES_SEQUENCE_FILE, "stop_times_sequence"),
            (TRIPS_FILE, "trips"),
        ]
    )

    door_seconds = load_door_seconds(DOORS_FILE)
    print(f"Door entries loaded: {len(door_seconds)}")

    rid_to_name = {rid: name for name, rid in subway_routes_names_ids.items()}
    trip_to_line = load_trip_to_line(TRIPS_FILE, rid_to_name)
    trip_bounds = load_trip_sequence_bounds(STOP_TIMES_SEQUENCE_FILE, set(trip_to_line))

    total, modified = apply_door_times(
        STOP_TIMES_SEQUENCE_FILE,
        STOP_TIMES_DOORS_FILE,
        trip_to_line,
        trip_bounds,
        door_seconds,
    )
    print(
        f"\n    {Path(STOP_TIMES_SEQUENCE_FILE).name}: total_rows={total},"
        f" modified_rows={modified}, unmodified_rows={total - modified}"
        f" -> {Path(STOP_TIMES_DOORS_FILE).relative_to(_PROJECT_ROOT)}"
    )


if __name__ == "__main__":
    raise SystemExit(main())
