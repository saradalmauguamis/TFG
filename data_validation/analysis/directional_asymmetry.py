"""Compare directional travel times between adjacent platforms, per subway line.

The script uses stop_times_doors.txt and trips_cleaned.txt.

The aim of this script is to determine whether it is necessary a directed graph.

For each subway line in `subway_reference.subway_lines.subway_route_names_stop_ids`, trips are
restricted to that line's own route_id, and the consecutive stop pairs of its
canonical stop order are compared direction_id=0 (a -> b) against
direction_id=1 (b -> a). All lines share a single pass over stop_times_doors.txt,
then their pairs are ranked together by the absolute gap between the two
directions, with the largest gaps printed first.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Set, Tuple

_PROJECT_ROOT = str(Path(__file__).resolve().parents[2])
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from data_validation.gtfs_utils import (  # noqa: E402
    STOP_TIMES_DOORS_FILE,
    STOPS_SUBWAY_FILE,
    TRIPS_FILE,
    average_times_for_pairs,
    build_trip_groups_by_line,
    check_missing_files,
    collect_pair_samples_by_trip_group,
    load_stop_names,
    print_file_disclaimer,
    seconds_to_hms,
)
from subway_reference.subway_lines import (  # noqa: E402
    subway_route_names_stop_ids,
    subway_routes_names_ids,
)

PairRecord = Tuple[float, int, float]
RankedPair = Tuple[float, str, Tuple[str, str], PairRecord, PairRecord]
GroupKey = Tuple[str, int]  # (line_short_name, direction_id)

TOP_N_PAIRS_TO_PRINT = 160


def rank_all_pairs(
    group_pairs: Dict[GroupKey, List[Tuple[str, str]]],
    avg_by_group: Dict[GroupKey, Dict[Tuple[str, str], PairRecord]],
) -> List[RankedPair]:
    """Rank every line's stop pairs together by the gap between its directions.

    args:
            group_pairs: Mapping from (line, direction_id) to its directed pairs.
            avg_by_group: Precomputed averages keyed by (line, direction_id).

    returns:
            Pairs with both directions sampled, tagged with their line name.
    """
    ranked: List[RankedPair] = []
    for line_short_name in subway_route_names_stop_ids:
        pairs_dir0 = group_pairs.get((line_short_name, 0))
        if not pairs_dir0:
            continue

        averages_dir0 = avg_by_group.get((line_short_name, 0), {})
        averages_dir1 = avg_by_group.get((line_short_name, 1), {})
        for pair in pairs_dir0:
            record_dir0 = averages_dir0.get(pair)
            record_dir1 = averages_dir1.get((pair[1], pair[0]))
            if record_dir0 is None or record_dir1 is None:
                continue
            gap = abs(record_dir0[0] - record_dir1[0])
            ranked.append((gap, line_short_name, pair, record_dir0, record_dir1))

    return ranked


def print_ranked_pairs(
    ranked: Sequence[RankedPair],
    stop_names: Dict[str, str],
) -> None:
    """Print the directional comparison table, largest gap first.

    args:
            ranked: All lines' pairs, sorted by descending gap.
            stop_names: Mapping from stop_id to stop_name.
    """
    print("Top pairs by absolute directional difference:")
    for index, (
        gap,
        line_short_name,
        (a, b),
        (avg0, cnt0, std0),
        (avg1, cnt1, std1),
    ) in enumerate(ranked, start=1):
        label_a = f"{line_short_name}-{stop_names.get(a, a)}"
        label_b = f"{line_short_name}-{stop_names.get(b, b)}"
        print(f"{index}. {a} ({label_a}) -> {b} ({label_b})")
        print(
            f"     dir0  {seconds_to_hms(avg0):>8} ({avg0:.2f}s) "
            f"cnt={cnt0} stdev={std0:.2f}s"
        )
        print(
            f"     dir1  {seconds_to_hms(avg1):>8} ({avg1:.2f}s) "
            f"cnt={cnt1} stdev={std1:.2f}s"
        )
        print(f"     diff  {seconds_to_hms(gap):>8} ({gap:.2f}s)")
        print()


def main() -> None:
    """Run the directional asymmetry analysis."""
    relevant_stop_ids: Set[str] = set()
    stop_names: Dict[str, str] = {}
    trip_id_to_group: Dict[str, GroupKey] = {}
    group_pairs: Dict[GroupKey, List[Tuple[str, str]]] = {}
    samples_by_group: Dict[GroupKey, Dict[Tuple[str, str], List[int]]] = {}
    avg_by_group: Dict[GroupKey, Dict[Tuple[str, str], Optional[PairRecord]]] = {}
    ranked: List[RankedPair] = []

    check_missing_files([STOP_TIMES_DOORS_FILE, STOPS_SUBWAY_FILE, TRIPS_FILE])
    print_file_disclaimer([STOP_TIMES_DOORS_FILE, STOPS_SUBWAY_FILE, TRIPS_FILE])

    relevant_stop_ids = {
        stop_id
        for stop_ids in subway_route_names_stop_ids.values()
        for stop_id in stop_ids
    }
    stop_names = load_stop_names(STOPS_SUBWAY_FILE, relevant_stop_ids)

    trip_id_to_group, group_pairs = build_trip_groups_by_line(
        subway_route_names_stop_ids, subway_routes_names_ids, TRIPS_FILE
    )
    samples_by_group = collect_pair_samples_by_trip_group(
        STOP_TIMES_DOORS_FILE, trip_id_to_group, group_pairs
    )
    avg_by_group = {
        group: average_times_for_pairs(samples)
        for group, samples in samples_by_group.items()
    }

    ranked = rank_all_pairs(group_pairs, avg_by_group)
    ranked.sort(key=lambda item: (-item[0], item[1], item[2]))

    print(f"Number of stop pairs with both directions defined: {len(ranked)}\n")
    print_ranked_pairs(ranked[:TOP_N_PAIRS_TO_PRINT], stop_names)


if __name__ == "__main__":
    main()
