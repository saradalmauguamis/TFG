"""Rank platform-to-platform edges by travel-time stdev, on the final stop_times.

The graph's `SW` edges (platform -> platform) get their weight from the mean
travel time observed in stop_times, where each sample is `arrival_b -
arrival_a` (the same convention `collect_pair_samples_by_trip_group` already
uses for every other directed-pair analysis in this codebase). This script
checks whether that mean is trustworthy: for every directed consecutive-stop
pair on every subway line, it computes mean + stdev + sample count from
`STOP_TIMES_FILE` (`stop_times_shared.txt`, the latest pipeline stage, post
shared-platform duplication), then ranks all edges by stdev (not by
directional or cross-line gap, which the other two analysis scripts already
cover).

Because this script reads the post-duplication stop_times, it uses
`scripts.basics.subway_route_names_stop_ids_artificial` (the per-line stop_id
lists rewritten for split shared platforms) rather than the original
`subway_route_names_stop_ids`, which still has lines sharing a stop_id and so
no longer matches the IDs in `stop_times_shared.txt`.

For the highest-stdev edges, a second targeted pass breaks their mean down by
hour (bucketed by arrival at the first stop of the pair, used as a
departure-hour proxy), to tell a real time-of-day pattern (rush vs off-peak)
apart from plain noise before trusting a single static mean as the edge
weight for shortest-path algorithms on the resulting weighted graph (Dijkstra
or otherwise).
"""

from __future__ import annotations

import sys
from pathlib import Path
from statistics import stdev
from typing import Dict, List, Optional, Sequence, Set, Tuple

_PROJECT_ROOT = str(Path(__file__).resolve().parents[2])
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from data_validation.gtfs_utils import (  # noqa: E402
    STOP_TIMES_FILE,
    STOPS_FILE,
    TRIPS_FILE,
    average_times_for_pairs,
    build_trip_groups_by_line,
    check_missing_files,
    collect_pair_door_run_samples_by_trip_group,
    collect_pair_samples_by_trip_group,
    collect_pair_samples_by_trip_group_hourly,
    load_stop_names,
    print_file_disclaimer,
    seconds_to_hms,
)
from scripts.basics import (  # noqa: E402
    subway_route_names_stop_ids_artificial,
    subway_routes_names_ids,
)

GroupKey = Tuple[str, int]  # (line_short_name, direction_id)
PairRecord = Tuple[float, int, float]  # (mean, count, stdev)
# (stdev, line_short_name, direction_id, (from_stop_id, to_stop_id), PairRecord)
RankedEdge = Tuple[float, str, int, Tuple[str, str], PairRecord]

TOP_K_HOURLY = 10
MIN_STDEV_TO_PRINT_SECONDS = 5.0


def rank_edges_by_stdev(
    group_pairs: Dict[GroupKey, List[Tuple[str, str]]],
    avg_by_group: Dict[GroupKey, Dict[Tuple[str, str], Optional[PairRecord]]],
) -> List[RankedEdge]:
    """Flatten every line/direction's edges into one list, ranked by stdev.

    args:
            group_pairs: Mapping from (line, direction_id) to its directed pairs.
            avg_by_group: Precomputed (mean, count, stdev) keyed by group.

    returns:
            Edges with at least one sample, sorted by descending stdev.
    """
    ranked: List[RankedEdge] = []

    for (line_short_name, direction_id), pairs in group_pairs.items():
        averages = avg_by_group.get((line_short_name, direction_id), {})
        for pair in pairs:
            record = averages.get(pair)
            if record is None:
                continue
            _, _, std = record
            ranked.append((std, line_short_name, direction_id, pair, record))

    ranked.sort(key=lambda item: (-item[0], item[1], item[2], item[3]))
    return ranked


def print_door_run_decomposition(
    ranked: Sequence[RankedEdge],
    stop_names: Dict[str, str],
    top_k: int,
) -> None:
    """Split each top-stdev edge's travel time into door time at A and run time A->B.

    `total = arrival_b - arrival_a` (what `ranked` was computed from) conflates
    dwell at the departure platform with actual movement between platforms.
    This prints both components separately, computed via
    `collect_pair_door_run_samples_by_trip_group`, to see how much of the
    overall stdev is dwell-time noise versus genuine travel-time variance.

    args:
            ranked: Edges sorted by descending stdev.
            stop_names: Mapping from stop_id to stop_name.
            top_k: Number of highest-stdev edges to decompose.
    """
    top_edges: Sequence[RankedEdge] = ranked[:top_k]
    trip_id_to_group: Dict[str, GroupKey] = {}
    group_pairs: Dict[GroupKey, List[Tuple[str, str]]] = {}
    restricted_group_pairs: Dict[GroupKey, List[Tuple[str, str]]] = {}
    door_by_group: Dict[GroupKey, Dict[Tuple[str, str], List[int]]] = {}
    run_by_group: Dict[GroupKey, Dict[Tuple[str, str], List[int]]] = {}
    avg_door_by_group: Dict[GroupKey, Dict[Tuple[str, str], Optional[PairRecord]]] = {}
    avg_run_by_group: Dict[GroupKey, Dict[Tuple[str, str], Optional[PairRecord]]] = {}

    if not top_edges:
        return

    trip_id_to_group, group_pairs = build_trip_groups_by_line(
        subway_route_names_stop_ids_artificial, subway_routes_names_ids, TRIPS_FILE
    )
    for _, line_short_name, direction_id, pair, _ in top_edges:
        group = (line_short_name, direction_id)
        restricted_group_pairs.setdefault(group, []).append(pair)

    door_by_group, run_by_group = collect_pair_door_run_samples_by_trip_group(
        STOP_TIMES_FILE, trip_id_to_group, restricted_group_pairs
    )
    avg_door_by_group = {
        group: average_times_for_pairs(samples)
        for group, samples in door_by_group.items()
    }
    avg_run_by_group = {
        group: average_times_for_pairs(samples)
        for group, samples in run_by_group.items()
    }

    print(
        f"Door time (dwell at A) vs run time (A->B) for the top {len(top_edges)} "
        "highest-stdev edges:"
    )
    print("(door = departure_a - arrival_a; run = arrival_b - departure_a)\n")
    for index, (
        std,
        line_short_name,
        direction_id,
        (a, b),
        (avg, count, _),
    ) in enumerate(top_edges, start=1):
        label_a = f"{line_short_name}-{stop_names.get(a, a)}"
        label_b = f"{line_short_name}-{stop_names.get(b, b)}"
        print(
            f"{index}. {line_short_name} dir{direction_id}  {a} ({label_a}) -> "
            f"{b} ({label_b})"
        )
        print(
            f"     total  {seconds_to_hms(avg):>8} ({avg:.2f}s) "
            f"cnt={count} stdev={std:.2f}s"
        )

        group = (line_short_name, direction_id)
        door_record = avg_door_by_group.get(group, {}).get((a, b))
        run_record = avg_run_by_group.get(group, {}).get((a, b))
        if door_record is not None:
            door_avg, door_count, door_std = door_record
            print(
                f"     door   {seconds_to_hms(door_avg):>8} ({door_avg:.2f}s) "
                f"cnt={door_count} stdev={door_std:.2f}s"
            )
        if run_record is not None:
            run_avg, run_count, run_std = run_record
            print(
                f"     run    {seconds_to_hms(run_avg):>8} ({run_avg:.2f}s) "
                f"cnt={run_count} stdev={run_std:.2f}s"
            )
        print()


def print_hourly_breakdown(
    ranked: Sequence[RankedEdge],
    stop_names: Dict[str, str],
    top_k: int,
) -> None:
    """Print an hour-bucket breakdown for the top-stdev edges.

    The hour bucket is the arrival hour at the first stop of each pair (a
    departure-hour proxy, since stop_times only carries arrival_time for
    intermediate platforms). Both the per-hour mean and stdev are printed,
    since a wide spread *within* a single hour (not just a shift *between*
    hours) also drives the overall stdev up.

    args:
            ranked: Edges sorted by descending stdev.
            stop_names: Mapping from stop_id to stop_name.
            top_k: Number of highest-stdev edges to break down by hour.
    """
    top_edges: Sequence[RankedEdge] = ranked[:top_k]
    trip_id_to_group: Dict[str, GroupKey] = {}
    group_pairs: Dict[GroupKey, List[Tuple[str, str]]] = {}
    restricted_group_pairs: Dict[GroupKey, List[Tuple[str, str]]] = {}
    hourly_by_group: Dict[GroupKey, Dict[Tuple[str, str], Dict[int, List[int]]]] = {}

    if not top_edges:
        return

    trip_id_to_group, group_pairs = build_trip_groups_by_line(
        subway_route_names_stop_ids_artificial, subway_routes_names_ids, TRIPS_FILE
    )
    for _, line_short_name, direction_id, pair, _ in top_edges:
        group = (line_short_name, direction_id)
        restricted_group_pairs.setdefault(group, []).append(pair)

    hourly_by_group = collect_pair_samples_by_trip_group_hourly(
        STOP_TIMES_FILE, trip_id_to_group, restricted_group_pairs
    )

    print(f"Hour-of-day breakdown for the top {len(top_edges)} highest-stdev edges:")
    print("(hour = arrival at the first stop of the pair, a departure-hour proxy)\n")
    for index, (
        std,
        line_short_name,
        direction_id,
        (a, b),
        (avg, count, _),
    ) in enumerate(top_edges, start=1):
        label_a = f"{line_short_name}-{stop_names.get(a, a)}"
        label_b = f"{line_short_name}-{stop_names.get(b, b)}"
        print(
            f"{index}. {line_short_name} dir{direction_id}  {a} ({label_a}) -> "
            f"{b} ({label_b})"
        )
        print(
            f"     overall  {seconds_to_hms(avg):>8} ({avg:.2f}s) "
            f"cnt={count} stdev={std:.2f}s"
        )

        hourly = hourly_by_group.get((line_short_name, direction_id), {}).get(
            (a, b), {}
        )
        for hour in sorted(hourly):
            samples = hourly[hour]
            hour_avg = sum(samples) / len(samples)
            hour_std = stdev(samples) if len(samples) > 1 else 0.0
            print(
                f"     {hour:02d}:00  {seconds_to_hms(hour_avg):>8} ({hour_avg:.2f}s) "
                f"cnt={len(samples)} stdev={hour_std:.2f}s"
            )
        print()


def print_ranked_edges(
    ranked: Sequence[RankedEdge],
    stop_names: Dict[str, str],
    min_stdev: float,
) -> None:
    """Print edges ranked by descending stdev, above a minimum threshold.

    args:
            ranked: Edges sorted by descending stdev.
            stop_names: Mapping from stop_id to stop_name.
            min_stdev: Only print edges whose stdev is at least this many seconds.
    """
    above_threshold: List[RankedEdge] = [
        edge for edge in ranked if edge[0] >= min_stdev
    ]

    print(
        f"Edges ranked by travel-time stdev (highest first, stdev >= "
        f"{min_stdev:.0f}s): {len(above_threshold)} of {len(ranked)}"
    )
    for index, (
        std,
        line_short_name,
        direction_id,
        (a, b),
        (avg, count, _),
    ) in enumerate(above_threshold, start=1):
        label_a = f"{line_short_name}-{stop_names.get(a, a)}"
        label_b = f"{line_short_name}-{stop_names.get(b, b)}"
        print(
            f"{index}. {line_short_name} dir{direction_id}  {a} ({label_a}) -> "
            f"{b} ({label_b})"
        )
        print(
            f"     mean  {seconds_to_hms(avg):>8} ({avg:.2f}s) "
            f"cnt={count} stdev={std:.2f}s"
        )
    print()


def main() -> None:
    """Rank SW edges by stdev and break down the noisiest ones by hour."""
    trip_id_to_group: Dict[str, GroupKey] = {}
    group_pairs: Dict[GroupKey, List[Tuple[str, str]]] = {}
    samples_by_group: Dict[GroupKey, Dict[Tuple[str, str], List[int]]] = {}
    avg_by_group: Dict[GroupKey, Dict[Tuple[str, str], Optional[PairRecord]]] = {}
    ranked: List[RankedEdge] = []
    relevant_stop_ids: Set[str] = set()
    stop_names: Dict[str, str] = {}

    print(
        "We rank the subway SW edges (platform -> platform) by travel-time "
        "stdev, to see whether the mean is a trustworthy weight for "
        "shortest-path algorithms on the weighted graph, or hides a real "
        "time-of-day pattern.\n"
    )

    check_missing_files([STOP_TIMES_FILE, STOPS_FILE, TRIPS_FILE])
    print_file_disclaimer([STOP_TIMES_FILE, STOPS_FILE, TRIPS_FILE])

    relevant_stop_ids = {
        stop_id
        for stop_ids in subway_route_names_stop_ids_artificial.values()
        for stop_id in stop_ids
    }
    stop_names = load_stop_names(STOPS_FILE, relevant_stop_ids)

    trip_id_to_group, group_pairs = build_trip_groups_by_line(
        subway_route_names_stop_ids_artificial, subway_routes_names_ids, TRIPS_FILE
    )
    samples_by_group = collect_pair_samples_by_trip_group(
        STOP_TIMES_FILE, trip_id_to_group, group_pairs
    )
    avg_by_group = {
        group: average_times_for_pairs(samples)
        for group, samples in samples_by_group.items()
    }

    ranked = rank_edges_by_stdev(group_pairs, avg_by_group)

    print(f"Number of edges with at least one sample: {len(ranked)}\n")
    print_ranked_edges(ranked, stop_names, MIN_STDEV_TO_PRINT_SECONDS)
    print_door_run_decomposition(ranked, stop_names, TOP_K_HOURLY)
    print_hourly_breakdown(ranked, stop_names, TOP_K_HOURLY)


if __name__ == "__main__":
    main()
