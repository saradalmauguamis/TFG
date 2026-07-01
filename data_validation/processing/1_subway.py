"""Build GTFS subway extracts from the subway input files.

This script reads the subway GTFS files from ``data/0_raw`` and writes
filtered ``*_subway.txt`` files into data/1_subway.

Rows whose first column starts with ``2.`` are removed.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path
from typing import Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from data_validation.gtfs_utils import (  # noqa: E402
    RAW_BASE,
    ROUTES_RAW_FILE,
    STOP_TIMES_RAW_FILE,
    STOPS_RAW_FILE,
    TRIPS_RAW_FILE,
    _DEFAULT_SUBWAY_DATA_DIR,
    check_missing_files,
    print_file_disclaimer,
)
from scripts.utils import sniff_dialect  # noqa: E402


SOURCE_FILES = (
    ROUTES_RAW_FILE,
    STOP_TIMES_RAW_FILE,
    STOPS_RAW_FILE,
    TRIPS_RAW_FILE,
)


def dotted_numeric_sort_key(value: str) -> Tuple[int, int, int]:
    """Sort dotted identifiers by their first three numeric parts.

    args:
        value: Dotted identifier to convert into a sortable numeric key.

    returns:
        Tuple with the first three numeric parts, using zero for missing parts.
    """
    parts = (value or "").split(".")
    first = int(parts[0]) if len(parts) > 0 and parts[0].isdigit() else 0
    second = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
    third = int(parts[2]) if len(parts) > 2 and parts[2].isdigit() else 0
    return first, second, third


def clean_file(source_path: Path, destination_dir: Path) -> Tuple[int, int, int, Path]:
    """Filter one GTFS file and write the subway-only extract.

    args:
            source_path: Raw GTFS file path.
            destination_dir: Directory where the filtered file is written.

    returns:
            Tuple with total rows, removed rows, kept rows, and output path.
    """
    dialect = sniff_dialect(source_path)
    output_path = destination_dir / f"{source_path.stem}_subway.txt"
    base_name = source_path.stem
    total_rows = 0
    kept_rows = 0
    removed_rows = 0
    filtered_rows = []

    destination_dir.mkdir(parents=True, exist_ok=True)

    with source_path.open("r", encoding="utf-8-sig", newline="") as input_handle:
        reader = csv.DictReader(input_handle, dialect=dialect)
        if not reader.fieldnames:
            raise RuntimeError(f"File {source_path.name} has no header.")

        fieldnames = list(reader.fieldnames)
        first_column = fieldnames[0]

        with output_path.open("w", encoding="utf-8", newline="") as output_handle:
            writer = csv.DictWriter(
                output_handle,
                fieldnames=fieldnames,
                dialect=dialect,
                extrasaction="ignore",
            )
            writer.writeheader()

            for row in reader:
                total_rows += 1
                first_value = (row.get(first_column) or "").strip()
                if first_value.startswith("2."):
                    continue
                filtered_rows.append(row)
                kept_rows += 1

    if base_name == "stop_times":
        filtered_rows.sort(
            key=lambda row: (
                dotted_numeric_sort_key(row.get("trip_id", "") or ""),
                (
                    int(row.get("stop_sequence", "") or 10**9)
                    if str(row.get("stop_sequence", "") or "").isdigit()
                    else 10**9
                ),
            )
        )
    elif base_name == "trips":
        filtered_rows.sort(
            key=lambda row: (
                dotted_numeric_sort_key(row.get("route_id", "") or ""),
                row.get("direction_id", "") or "",
                dotted_numeric_sort_key(row.get("trip_id", "") or ""),
            )
        )

    with output_path.open("w", encoding="utf-8", newline="") as output_handle:
        writer = csv.DictWriter(
            output_handle,
            fieldnames=fieldnames,
            dialect=dialect,
            extrasaction="ignore",
        )
        writer.writeheader()
        writer.writerows(filtered_rows)

    removed_rows = total_rows - kept_rows
    return total_rows, removed_rows, kept_rows, output_path


def main() -> None:
    """Run the processing pipeline for all configured source files.

    This implementation reads the raw GTFS files from `RAW_BASE`
    and writes filtered subway extracts into a `subway` directory under
    `BASE` as `{stem}_subway.txt`."""

    source_paths = [Path(RAW_BASE) / name for name in SOURCE_FILES]
    destination_dir = _DEFAULT_SUBWAY_DATA_DIR

    check_missing_files([str(path) for path in source_paths])

    print_file_disclaimer(source_paths)

    destination_dir.mkdir(parents=True, exist_ok=True)

    for source_path in source_paths:
        total_rows, removed_rows, kept_rows, output_path = clean_file(
            source_path, destination_dir
        )
        print(
            f"\n    -{source_path.name}: total={total_rows}, removed={removed_rows}, "
            f"kept={kept_rows} -> {output_path.relative_to(PROJECT_ROOT)}"
        )

    return None


if __name__ == "__main__":
    raise SystemExit(main())
