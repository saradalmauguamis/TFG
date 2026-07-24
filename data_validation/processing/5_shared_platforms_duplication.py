"""Duplicate shared platforms into one stop_id per line.

`data_validation/analysis/shared_platforms.py` showed that platforms shared
by more than one line (currently L9S/L10S and L9N/L10N) have different
travel times depending on the line, so the graph must not merge them into a
single node. This script splits every shared stop_id into one new stop_id per
line that serves it, detected generically via
`gtfs_utils.build_shared_platform_lines` from
`subway_reference.subway_lines.subway_route_names_stop_ids`, so it is not hardcoded to L9/L10
and stays reproducible and scalable if the network grows new shared platforms
in the future, and rewrites every file that references the original stop_id.

Naming: e.g. stop_id `1.930`, shared by lines `[L9N, L10N]`, becomes `1.9300`
(L9N) and `1.9301` (L10N). The original stop_id is dropped everywhere.

Inputs and outputs (outputs are written to `data/5_shared_platforms/`):
- pathways.txt          -> pathways_shared.txt
- stop_times_doors.txt  -> stop_times_shared.txt
- stops_subway.txt      -> stops_shared.txt
- transfers.txt         -> transfers_shared.txt
- (none)                -> equivalences.txt

EQUIVALENCES: a lookup table with one row per (original_stop_id, line,
new_stop_id), so the mapping this script applies can be looked back up later
without re-deriving it.

STOPS: every row for a shared stop_id is replaced by one row per line, same
fields except stop_id (the new id) and stop_code (the new id without the
leading "1.").

PATHWAYS / TRANSFERS: these describe physical infrastructure (entrance <->
platform, platform <-> platform), not trips, so a row touching a shared
platform on one side is duplicated once per line, replacing only that side's
stop_id. (No row in the source data has a shared platform on both sides; that
case is rejected rather than silently mishandled.) For every shared platform,
a direct correspondence pathway/transfer is also added between each pair of
its new ids, using the minimum `min_transfer_time` found in transfers.txt as
the traversal time, and `pathway_mode=2`/`transfer_type=2` (a walking
transfer), matching the convention already used for other line-to-line
correspondences in this dataset.

STOP_TIMES: a stop_id at a shared platform is replaced by the new stop_id of
the line that trip belongs to (resolved via `load_trip_to_line`, exactly as
`4_doors_time.py` already does for door times), not duplicated like the
other files, since each row belongs to a single trip on a single line.
"""

from __future__ import annotations

import itertools
import sys
from pathlib import Path
from typing import Dict, List, Tuple

_PROJECT_ROOT = str(Path(__file__).resolve().parents[2])
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from data_validation.gtfs_utils import (  # noqa: E402
    EQUIVALENCES_FILE,
    PATHWAYS_FILE,
    PATHWAYS_RAW_FILE,
    STOP_TIMES_DOORS_FILE,
    STOP_TIMES_FILE,
    STOPS_FILE,
    STOPS_SUBWAY_FILE,
    TRANSFERS_FILE,
    TRANSFERS_RAW_FILE,
    TRIPS_FILE,
    build_shared_platform_lines,
    check_missing_files,
    load_trip_to_line,
    print_file_disclaimer,
    read_dict_rows,
    read_header,
    write_rows,
)
from subway_reference.subway_lines import (  # noqa: E402
    subway_route_names_stop_ids,
    subway_routes_names_ids,
)

NewIdByStopLine = Dict[Tuple[str, str], str]


def build_new_stop_ids(
    shared_platform_lines: Dict[str, List[str]]
) -> Tuple[NewIdByStopLine, Dict[str, str]]:
    """Assign one new stop_id per (shared stop_id, line) pair.

    args:
            shared_platform_lines: Shared stop_id -> ordered list of lines.

    returns:
            Tuple of ((stop_id, line) -> new_id, new_id -> line).
    """
    new_id_by_stop_line: NewIdByStopLine = {}
    line_by_new_id: Dict[str, str] = {}
    for stop_id, lines in shared_platform_lines.items():
        for index, line in enumerate(lines):
            new_id = f"{stop_id}{index}"
            new_id_by_stop_line[(stop_id, line)] = new_id
            line_by_new_id[new_id] = line
    return new_id_by_stop_line, line_by_new_id


def compute_min_transfer_time(transfers_file: str) -> int:
    """Return the minimum min_transfer_time found in transfers.txt.

    args:
            transfers_file: Path to transfers.txt.

    returns:
            Minimum min_transfer_time in seconds.
    """
    times = [
        int(row["min_transfer_time"])
        for row in read_dict_rows(transfers_file)
        if row.get("min_transfer_time")
    ]
    return min(times)


def write_equivalences(
    output_path: str,
    shared_platform_lines: Dict[str, List[str]],
    new_id_by_stop_line: NewIdByStopLine,
) -> int:
    """Write a lookup table of original_stop_id -> (line, new_stop_id).

    args:
            output_path: Path to write equivalences.txt.
            shared_platform_lines: Shared stop_id -> ordered list of lines.
            new_id_by_stop_line: (stop_id, line) -> new stop_id.

    returns:
            Number of rows written.
    """
    fieldnames = ["original_stop_id", "line", "new_stop_id"]
    rows = [
        {
            "original_stop_id": stop_id,
            "line": line,
            "new_stop_id": new_id_by_stop_line[(stop_id, line)],
        }
        for stop_id, lines in shared_platform_lines.items()
        for line in lines
    ]
    write_rows(output_path, fieldnames, rows)
    return len(rows)


def duplicate_stops(
    input_path: str,
    output_path: str,
    shared_platform_lines: Dict[str, List[str]],
    new_id_by_stop_line: NewIdByStopLine,
) -> Tuple[int, int]:
    """Split each shared stop's row into one row per line serving it.

    args:
            input_path: Path to stops_subway.txt.
            output_path: Path to write stops_shared.txt.
            shared_platform_lines: Shared stop_id -> ordered list of lines.
            new_id_by_stop_line: (stop_id, line) -> new stop_id.

    returns:
            Tuple of (total_rows, rows_created_for_shared_platforms).
    """
    fieldnames = read_header(input_path)
    rows_out: List[Dict[str, str]] = []
    total = 0
    created = 0

    for row in read_dict_rows(input_path):
        total += 1
        stop_id = row.get("stop_id", "")
        lines = shared_platform_lines.get(stop_id)
        if not lines:
            rows_out.append(row)
            continue

        for line in lines:
            new_id = new_id_by_stop_line[(stop_id, line)]
            new_row = dict(row)
            new_row["stop_id"] = new_id
            new_row["stop_code"] = new_id.split(".", 1)[1] if "." in new_id else new_id
            rows_out.append(new_row)
            created += 1

    write_rows(output_path, fieldnames, rows_out)
    return total, created


def _shared_side(
    row: Dict[str, str],
    shared_platform_lines: Dict[str, List[str]],
) -> Tuple[str, List[str], str]:
    """Return which side of a from/to row touches a shared platform, if any.

    args:
            row: Row with from_stop_id/to_stop_id columns.
            shared_platform_lines: Shared stop_id -> ordered list of lines.

    returns:
            Tuple of (shared_stop_id, its lines, column name), or ("", [], "")
            if neither side is shared.

    raises:
            NotImplementedError: If both sides are shared platforms; this
                combination does not occur in the source data and is not handled.
    """
    from_id = row.get("from_stop_id", "")
    to_id = row.get("to_stop_id", "")
    from_lines = shared_platform_lines.get(from_id)
    to_lines = shared_platform_lines.get(to_id)

    if from_lines and to_lines:
        raise NotImplementedError(
            f"Row {from_id} -> {to_id} has shared platforms on both ends; "
            "this case is not handled."
        )
    if from_lines:
        return from_id, from_lines, "from_stop_id"
    if to_lines:
        return to_id, to_lines, "to_stop_id"
    return "", [], ""


def duplicate_pathways(
    input_path: str,
    output_path: str,
    shared_platform_lines: Dict[str, List[str]],
    new_id_by_stop_line: NewIdByStopLine,
    line_by_new_id: Dict[str, str],
    min_transfer_time: int,
) -> Tuple[int, int, int]:
    """Duplicate shared-platform pathways per line and add correspondences.

    args:
            input_path: Path to pathways.txt.
            output_path: Path to write pathways_shared.txt.
            shared_platform_lines: Shared stop_id -> ordered list of lines.
            new_id_by_stop_line: (stop_id, line) -> new stop_id.
            line_by_new_id: new stop_id -> line.
            min_transfer_time: Traversal time to use for correspondence rows.

    returns:
            Tuple of (total_rows, rows_created_for_shared_platforms,
            correspondence_rows_created).
    """
    fieldnames = read_header(input_path)
    rows_out: List[Dict[str, str]] = []
    total = 0
    created = 0
    correspondences = 0

    for row in read_dict_rows(input_path):
        total += 1
        shared_id, lines, side = _shared_side(row, shared_platform_lines)
        if not lines:
            rows_out.append(row)
            continue

        for line in lines:
            new_row = dict(row)
            new_row[side] = new_id_by_stop_line[(shared_id, line)]
            new_row["pathway_id"] = (
                f"PW.{new_row['from_stop_id']}_{new_row['to_stop_id']}"
            )
            rows_out.append(new_row)
            created += 1

    for stop_id, lines in shared_platform_lines.items():
        new_ids = [new_id_by_stop_line[(stop_id, line)] for line in lines]
        for a, b in itertools.permutations(new_ids, 2):
            rows_out.append(
                {
                    "pathway_id": f"PW.{a}_{b}",
                    "from_stop_id": a,
                    "to_stop_id": b,
                    "pathway_mode": "2",
                    "is_bidirectional": "0",
                    "traversal_time": str(min_transfer_time),
                    "signposted_as": (
                        f"Correspondència {line_by_new_id[a]} - {line_by_new_id[b]}"
                    ),
                }
            )
            correspondences += 1

    write_rows(output_path, fieldnames, rows_out)
    return total, created, correspondences


def duplicate_transfers(
    input_path: str,
    output_path: str,
    shared_platform_lines: Dict[str, List[str]],
    new_id_by_stop_line: NewIdByStopLine,
    min_transfer_time: int,
) -> Tuple[int, int, int]:
    """Duplicate shared-platform transfers per line and add correspondences.

    args:
            input_path: Path to transfers.txt.
            output_path: Path to write transfers_shared.txt.
            shared_platform_lines: Shared stop_id -> ordered list of lines.
            new_id_by_stop_line: (stop_id, line) -> new stop_id.
            min_transfer_time: Transfer time to use for correspondence rows.

    returns:
            Tuple of (total_rows, rows_created_for_shared_platforms,
            correspondence_rows_created).
    """
    fieldnames = read_header(input_path)
    rows_out: List[Dict[str, str]] = []
    total = 0
    created = 0
    correspondences = 0

    for row in read_dict_rows(input_path):
        total += 1
        shared_id, lines, side = _shared_side(row, shared_platform_lines)
        if not lines:
            rows_out.append(row)
            continue

        for line in lines:
            new_row = dict(row)
            new_row[side] = new_id_by_stop_line[(shared_id, line)]
            rows_out.append(new_row)
            created += 1

    for stop_id, lines in shared_platform_lines.items():
        new_ids = [new_id_by_stop_line[(stop_id, line)] for line in lines]
        for a, b in itertools.permutations(new_ids, 2):
            rows_out.append(
                {
                    "from_stop_id": a,
                    "to_stop_id": b,
                    "transfer_type": "2",
                    "min_transfer_time": str(min_transfer_time),
                }
            )
            correspondences += 1

    write_rows(output_path, fieldnames, rows_out)
    return total, created, correspondences


def replace_shared_stop_ids_in_stop_times(
    input_path: str,
    output_path: str,
    shared_platform_lines: Dict[str, List[str]],
    new_id_by_stop_line: NewIdByStopLine,
    trip_to_line: Dict[str, str],
) -> Tuple[int, int]:
    """Replace shared stop_ids in stop_times with the trip's own line id.

    args:
            input_path: Path to stop_times_doors.txt.
            output_path: Path to write stop_times_shared.txt.
            shared_platform_lines: Shared stop_id -> ordered list of lines.
            new_id_by_stop_line: (stop_id, line) -> new stop_id.
            trip_to_line: trip_id -> line name.

    returns:
            Tuple of (total_rows, rows_replaced).
    """
    fieldnames = read_header(input_path)
    rows_out: List[Dict[str, str]] = []
    total = 0
    replaced = 0

    for row in read_dict_rows(input_path):
        total += 1
        stop_id = row.get("stop_id", "")
        if stop_id in shared_platform_lines:
            line = trip_to_line.get(row.get("trip_id", ""))
            new_id = new_id_by_stop_line.get((stop_id, line)) if line else None
            if new_id:
                row = dict(row)
                row["stop_id"] = new_id
                replaced += 1
        rows_out.append(row)

    write_rows(output_path, fieldnames, rows_out)
    return total, replaced


def main() -> None:
    """Duplicate shared platforms across stops, pathways, transfers and stop_times."""
    shared_platform_lines: Dict[str, List[str]] = {}
    new_id_by_stop_line: NewIdByStopLine = {}
    line_by_new_id: Dict[str, str] = {}
    min_transfer_time = 0
    equivalences_created = 0
    rid_to_name: Dict[str, str] = {}
    trip_to_line: Dict[str, str] = {}
    stops_total = 0
    stops_created = 0
    pathways_total = 0
    pathways_created = 0
    pathways_correspondences = 0
    transfers_total = 0
    transfers_created = 0
    transfers_correspondences = 0
    stop_times_total = 0
    stop_times_replaced = 0

    check_missing_files(
        [
            PATHWAYS_RAW_FILE,
            STOP_TIMES_DOORS_FILE,
            STOPS_SUBWAY_FILE,
            TRANSFERS_RAW_FILE,
            TRIPS_FILE,
        ]
    )
    print_file_disclaimer(
        [
            PATHWAYS_RAW_FILE,
            STOP_TIMES_DOORS_FILE,
            STOPS_SUBWAY_FILE,
            TRANSFERS_RAW_FILE,
            TRIPS_FILE,
        ]
    )

    shared_platform_lines = build_shared_platform_lines(subway_route_names_stop_ids)
    print(f"Shared platforms detected: {shared_platform_lines}\n")

    new_id_by_stop_line, line_by_new_id = build_new_stop_ids(shared_platform_lines)
    min_transfer_time = compute_min_transfer_time(TRANSFERS_RAW_FILE)

    equivalences_created = write_equivalences(
        EQUIVALENCES_FILE, shared_platform_lines, new_id_by_stop_line
    )
    print(f"equivalences.txt: rows_created={equivalences_created}\n")

    rid_to_name = {rid: name for name, rid in subway_routes_names_ids.items()}
    trip_to_line = load_trip_to_line(TRIPS_FILE, rid_to_name)

    stops_total, stops_created = duplicate_stops(
        STOPS_SUBWAY_FILE, STOPS_FILE, shared_platform_lines, new_id_by_stop_line
    )
    print(
        f"stops_subway.txt: total_rows={stops_total}, rows_created={stops_created} "
        "-> stops_shared.txt"
    )

    pathways_total, pathways_created, pathways_correspondences = duplicate_pathways(
        PATHWAYS_RAW_FILE,
        PATHWAYS_FILE,
        shared_platform_lines,
        new_id_by_stop_line,
        line_by_new_id,
        min_transfer_time,
    )
    print(
        f"pathways.txt: total_rows={pathways_total}, rows_created={pathways_created}, "
        f"correspondence_rows_created={pathways_correspondences} -> pathways_shared.txt"
    )

    transfers_total, transfers_created, transfers_correspondences = duplicate_transfers(
        TRANSFERS_RAW_FILE,
        TRANSFERS_FILE,
        shared_platform_lines,
        new_id_by_stop_line,
        min_transfer_time,
    )
    print(
        f"transfers.txt: total_rows={transfers_total}, rows_created={transfers_created}, "
        f"correspondence_rows_created={transfers_correspondences} -> transfers_shared.txt"
    )

    stop_times_total, stop_times_replaced = replace_shared_stop_ids_in_stop_times(
        STOP_TIMES_DOORS_FILE,
        STOP_TIMES_FILE,
        shared_platform_lines,
        new_id_by_stop_line,
        trip_to_line,
    )
    print(
        f"stop_times_doors.txt: total_rows={stop_times_total}, "
        f"rows_replaced={stop_times_replaced} -> stop_times_shared.txt"
    )


if __name__ == "__main__":
    main()
