"""Fix stop_sequence gaps for out-of-order stops in subway trips.

This script reads `wrong_stop_sequences.txt` from `STOP_SEQUENCE_BASE`, produced
by running `data_validation/checks/stop_times/2_canonical_sequence_check.py`,
and uses it to adjust stop_sequence values in `stop_times_cleaned.txt`.

For each break in a trip (two consecutive stops not adjacent in the canonical
route order) the sequence number of the breaking stop and every stop after it
in that trip are incremented by one. This opens a gap in the numbering so that
downstream graph builders can distinguish physically non-adjacent stops from
adjacent ones.

When a trip has several breaks, the increments accumulate. Each break point
shifts every stop at or after that position by one extra step. So a stop that
comes after two break points ends up with its original sequence plus two. For
example, if a trip has breaks at positions 4 and 7, a stop originally at
sequence 9 ends up at 11 (9 + 2), while a stop at sequence 5 ends up at 6
(5 + 1), and a stop at sequence 3 stays at 3 (3 + 0).

The adjusted file is written as `stop_times_sequence.txt` in `STOP_SEQUENCE_BASE`.
"""

from __future__ import annotations

import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from data_validation.gtfs_utils import (  # noqa: E402
    _PROJECT_ROOT,
    STOP_TIMES_CLEANED_FILE,
    STOP_TIMES_SEQUENCE_FILE,
    WRONG_STOP_SEQUENCES_FILE,
    check_missing_files,
    print_file_disclaimer,
    read_dict_rows,
    read_header,
    write_rows,
)


def load_break_points(file_path: str) -> Dict[str, List[int]]:
    """Return break-point sequences per trip from wrong_stop_sequences.txt.

    args:
        file_path: Path to the wrong_stop_sequences CSV file.

    returns:
        Mapping from trip_id to a sorted list of seq_b values (the sequences
        where a gap must be opened).
    """
    break_points: Dict[str, List[int]] = defaultdict(list)
    for row in read_dict_rows(file_path):
        trip_id = row.get("trip_id", "")
        seq_b_text = row.get("seq_b", "")
        if not trip_id or not seq_b_text:
            continue
        try:
            seq_b = int(seq_b_text)
        except ValueError:
            continue
        break_points[trip_id].append(seq_b)

    return {tid: sorted(seqs) for tid, seqs in break_points.items()}


def adjusted_sequence(original_seq: int, break_points: List[int]) -> int:
    """Compute the new stop_sequence after applying all break-point shifts.

    Each break point shifts every stop at or after that position by one extra
    step. A stop that falls at or after k break points ends up with its original
    sequence plus k. For example, with break points at 4 and 7, a stop at
    original sequence 9 receives a shift of 2 and becomes 11.

    args:
        original_seq: The original stop_sequence value.
        break_points: Sorted list of break-point sequences for the trip.

    returns:
        The adjusted stop_sequence.
    """
    shift = sum(1 for bp in break_points if bp <= original_seq)
    return original_seq + shift


def write_adjusted_stop_times(
    input_path: str,
    output_path: str,
    break_points_by_trip: Dict[str, List[int]],
) -> Tuple[int, int, int]:
    """Read stop_times, adjust sequences for affected trips, and write output.

    args:
        input_path: Path to the input stop_times CSV file.
        output_path: Path where the adjusted stop_times CSV is written.
        break_points_by_trip: Mapping from trip_id to sorted break-point sequences.

    returns:
        Tuple of (total_rows, modified_rows, unmodified_rows).
    """
    total_rows = 0
    modified_rows = 0
    rows_out: list[dict[str, str]] = []
    fieldnames = read_header(input_path)

    for row in read_dict_rows(input_path):
        total_rows += 1
        trip_id = row.get("trip_id", "")
        break_points = break_points_by_trip.get(trip_id)
        if not break_points:
            rows_out.append(row)
            continue

        seq_text = row.get("stop_sequence", "")
        try:
            original_seq = int(seq_text)
        except ValueError:
            rows_out.append(row)
            continue

        new_seq = adjusted_sequence(original_seq, break_points)
        if new_seq != original_seq:
            row["stop_sequence"] = str(new_seq)
            modified_rows += 1
        rows_out.append(row)

    write_rows(output_path, fieldnames, rows_out)

    return total_rows, modified_rows, total_rows - modified_rows


def main() -> None:
    """Adjust stop_sequence values for trips with non-adjacent canonical stops."""

    break_points_by_trip: Dict[str, List[int]] = {}
    total_bad_pairs = 0
    total = 0
    modified = 0
    unmodified = 0

    check_missing_files([WRONG_STOP_SEQUENCES_FILE, STOP_TIMES_CLEANED_FILE])
    print_file_disclaimer([WRONG_STOP_SEQUENCES_FILE, STOP_TIMES_CLEANED_FILE])

    break_points_by_trip = load_break_points(WRONG_STOP_SEQUENCES_FILE)
    total_bad_pairs = sum(len(bps) for bps in break_points_by_trip.values())
    print(
        f"Trips with sequence breaks: {len(break_points_by_trip)}"
        f" ({total_bad_pairs} bad pairs)"
    )

    total, modified, unmodified = write_adjusted_stop_times(
        STOP_TIMES_CLEANED_FILE, STOP_TIMES_SEQUENCE_FILE, break_points_by_trip
    )
    print(
        f"\n    {Path(STOP_TIMES_CLEANED_FILE).name}: total_rows={total},"
        f" modified_rows={modified}, unmodified_rows={unmodified}"
        f" -> {Path(STOP_TIMES_SEQUENCE_FILE).relative_to(_PROJECT_ROOT)}"
    )


if __name__ == "__main__":
    raise SystemExit(main())
