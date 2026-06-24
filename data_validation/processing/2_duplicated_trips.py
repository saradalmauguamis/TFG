"""Remove duplicated subway trips and rewrite the cleaned GTFS extracts.

This script loads the trip IDs listed in `trip_ids_to_eliminate.txt` and uses
them to filter rows from:

- `stop_times_subway.txt`
- `trips_subway.txt`

The filtered files are written next to the inputs as:

- `stop_times_subway_cleaned.txt`
- `trips_subway_cleaned.txt`
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Set, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from data_validation.gtfs_utils import (  # noqa: E402
    STOP_TIMES_SUBWAY_FILE,
    STOP_TIMES_CLEANED_FILE,
    TRIP_IDS_TO_ELIMINATE_FILE,
    TRIPS_SUBWAY_FILE,
    TRIPS_FILE,
    check_missing_files,
    print_file_disclaimer,
    load_nonempty_lines,
    read_dict_rows,
    read_header,
    write_rows,
)


def write_cleaned_file(
    input_path: str,
    output_path: str,
    eliminated_trip_ids: Set[str],
) -> Tuple[int, int, int, str]:
    """Filter one input file and write the cleaned output file.

    args:
        input_path: Path to the subway GTFS input file.
        output_path: Path where the cleaned GTFS file is written.
        eliminated_trip_ids: Trip identifiers to remove from the input file.

    returns:
        Tuple with total rows, removed rows, kept rows, and output path.
    """
    total_rows = 0
    kept_rows: list[dict[str, str]] = []
    removed_rows = 0

    fieldnames = read_header(input_path)
    for row in read_dict_rows(input_path):
        total_rows += 1
        trip_id = row.get("trip_id", "")
        if trip_id in eliminated_trip_ids:
            continue
        kept_rows.append(row)

    write_rows(output_path, fieldnames, kept_rows)

    removed_rows = total_rows - len(kept_rows)
    return total_rows, removed_rows, len(kept_rows), output_path


def main() -> None:
    """Create cleaned stop_times and trips files after removing duplicated trip IDs."""
    trip_ids_path = TRIP_IDS_TO_ELIMINATE_FILE
    stop_times_input = STOP_TIMES_SUBWAY_FILE
    trips_input = TRIPS_SUBWAY_FILE
    eliminated_trip_ids = set()
    stop_times_output = STOP_TIMES_CLEANED_FILE
    trips_output = TRIPS_FILE

    check_missing_files([trip_ids_path, stop_times_input, trips_input])

    print_file_disclaimer([trip_ids_path, stop_times_input, trips_input])

    eliminated_trip_ids = load_nonempty_lines(trip_ids_path)
    print(f"\nTrip_id to eliminate: {len(eliminated_trip_ids)}")

    for input_path, output_path in (
        (stop_times_input, stop_times_output),
        (trips_input, trips_output),
    ):
        total_rows, removed_rows, kept_rows, saved_path = write_cleaned_file(
            input_path, output_path, eliminated_trip_ids
        )
        print(
            f"\n    - {Path(input_path).name}: total={total_rows}, removed={removed_rows}, "
            f"kept={kept_rows} -> {Path(saved_path).relative_to(PROJECT_ROOT)}"
        )

    return None


if __name__ == "__main__":
    raise SystemExit(main())
