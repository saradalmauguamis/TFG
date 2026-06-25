"""Rank platform-to-platform edges by travel-time stdev, on the final stop_times.

The graph's `sw` edges (platform -> platform) get their weight from the mean
travel time observed in stop_times, where each sample is `arrival_b -
arrival_a` (the same convention `collect_pair_samples_by_trip_group` already
uses for every other directed-pair analysis in this codebase). This script
checks whether that mean is trustworthy: for every directed consecutive-stop
pair on every subway line, it computes mean + stdev + sample count from
`STOP_TIMES_FILE` (`stop_times_shared.txt`, the latest pipeline stage, post
shared-platform duplication), then ranks all edges by stdev (not by
directional or cross-line gap, which the other two analysis scripts already
cover).

`total = arrival_b - arrival_a` conflates two physically different things:
dwell at the departure platform A (door open for boarding) and the actual
movement between A and B. Every edge printed is therefore decomposed into
`door` (`departure_a - arrival_a`) and `sw` (`arrival_b - departure_a`, the
pure run time a future `sw` edge weight should use), via
`collect_pair_door_sw_samples_by_trip_group`, to see how much of the stdev is
dwell-time noise versus genuine travel-time variance.

Because this script reads the post-duplication stop_times, it uses
`scripts.basics.subway_route_names_stop_ids_artificial` (the per-line stop_id
lists rewritten for split shared platforms) rather than the original
`subway_route_names_stop_ids`, which still has lines sharing a stop_id and so
no longer matches the IDs in `stop_times_shared.txt`.

For the highest-stdev edges, a second targeted pass breaks the same
total/door/sw decomposition down by hour (bucketed by arrival at the first
stop of the pair, used as a departure-hour proxy), to tell a real time-of-day
pattern (rush vs off-peak) apart from plain noise before trusting a single
static mean as the edge weight for shortest-path algorithms on the resulting
weighted graph (Dijkstra or otherwise).
"""

from __future__ import annotations

import sys
from contextlib import redirect_stdout
from pathlib import Path
from statistics import stdev
from typing import Dict, IO, List, Optional, Sequence, Set, Tuple

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
    collect_pair_door_sw_samples_by_trip_group,
    collect_pair_door_sw_samples_by_trip_group_hourly,
    collect_pair_samples_by_trip_group,
    load_stop_names,
    print_file_disclaimer,
    seconds_to_hms,
)
from scripts.basics import (  # noqa: E402
    subway_route_names_stop_ids_artificial,
    subway_routes_names_ids,
)

REPORT_FILE = Path(__file__).resolve().parent / "edge_stdev_report.txt"

GroupKey = Tuple[str, int]  # (line_short_name, direction_id)
PairRecord = Tuple[float, int, float]  # (mean, count, stdev)
# (stdev, line_short_name, direction_id, (from_stop_id, to_stop_id), PairRecord)
RankedEdge = Tuple[float, str, int, Tuple[str, str], PairRecord]

TOP_K_HOURLY = 6
MIN_STDEV_TO_PRINT_SECONDS_TOTAL = 10.0
MIN_STDEV_TO_PRINT_SECONDS_DOOR = 10.0
MIN_STDEV_TO_PRINT_SECONDS_SW = 5.0


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


def print_ranked_edges(
    ranked: Sequence[RankedEdge],
    avg_total_by_group: Dict[GroupKey, Dict[Tuple[str, str], Optional[PairRecord]]],
    avg_door_by_group: Dict[GroupKey, Dict[Tuple[str, str], Optional[PairRecord]]],
    avg_sw_by_group: Dict[GroupKey, Dict[Tuple[str, str], Optional[PairRecord]]],
    stop_names: Dict[str, str],
    min_stdev: float,
    metric_label: str,
) -> None:
    """Print edges ranked by descending stdev, with their total/door/sw decomposition.

    For every edge printed (stdev >= min_stdev), prints `total`, `door`
    (`departure_a - arrival_a`) and `sw` (`arrival_b - departure_a`), looked
    up from the precomputed `avg_total_by_group`/`avg_door_by_group`/
    `avg_sw_by_group` (built once in `main` over every edge, so this can be
    called for several rankings without recomputing). `ranked`'s own
    embedded record is only the metric `ranked` was sorted by (e.g. door
    stdev when ranking by door), not necessarily `total`, so all three lines
    are looked up independently rather than read off the ranked tuple.

    args:
            ranked: Edges sorted by descending stdev of the metric being ranked.
            avg_total_by_group: Total (mean, count, stdev) per group/pair.
            avg_door_by_group: Door (mean, count, stdev) per group/pair.
            avg_sw_by_group: Sw (mean, count, stdev) per group/pair.
            stop_names: Mapping from stop_id to stop_name.
            min_stdev: Only print edges whose stdev is at least this many seconds.
            metric_label: Name of the metric `ranked` is sorted by (e.g. "total",
                    "door", "sw"), used in the header line.
    """
    above_threshold: List[RankedEdge] = [
        edge for edge in ranked if edge[0] >= min_stdev
    ]

    print(
        f"Edges ranked by {metric_label} stdev (highest first, stdev >= "
        f"{min_stdev:.0f}s): {len(above_threshold)} of {len(ranked)}"
    )
    if not above_threshold:
        print()
        return

    print("(door = departure_a - arrival_a; sw = arrival_b - departure_a)\n")
    for index, (std, line_short_name, direction_id, (a, b), _) in enumerate(
        above_threshold, start=1
    ):
        label_a = f"{line_short_name}-{stop_names.get(a, a)}"
        label_b = f"{line_short_name}-{stop_names.get(b, b)}"
        print(
            f"{index}. {line_short_name} dir{direction_id}  {a} ({label_a}) -> "
            f"{b} ({label_b})  [{metric_label} stdev={std:.2f}s]"
        )

        group = (line_short_name, direction_id)
        total_record = avg_total_by_group.get(group, {}).get((a, b))
        door_record = avg_door_by_group.get(group, {}).get((a, b))
        sw_record = avg_sw_by_group.get(group, {}).get((a, b))
        if total_record is not None:
            total_avg, total_count, total_std = total_record
            print(
                f"     total  {seconds_to_hms(total_avg):>8} ({total_avg:.2f}s) "
                f"cnt={total_count} stdev={total_std:.2f}s"
            )
        if door_record is not None:
            door_avg, door_count, door_std = door_record
            print(
                f"     door   {seconds_to_hms(door_avg):>8} ({door_avg:.2f}s) "
                f"cnt={door_count} stdev={door_std:.2f}s"
            )
        if sw_record is not None:
            sw_avg, sw_count, sw_std = sw_record
            print(
                f"     sw     {seconds_to_hms(sw_avg):>8} ({sw_avg:.2f}s) "
                f"cnt={sw_count} stdev={sw_std:.2f}s"
            )
        print()


def print_hourly_breakdown(
    ranked: Sequence[RankedEdge],
    stop_names: Dict[str, str],
    top_k: int,
) -> None:
    """Print an hour-bucket total/door/sw breakdown for the top-stdev edges.

    The hour bucket is the arrival hour at the first stop of each pair (a
    departure-hour proxy, since stop_times only carries arrival_time for
    intermediate platforms). Door and sw are bucketed in lockstep by
    `collect_pair_door_sw_samples_by_trip_group_hourly`, so the per-hour total
    is derived as their elementwise sum, and all three (total/door/sw) are
    printed per hour: a wide spread *within* a single hour (not just a shift
    *between* hours) can itself be door- or sw-driven.

    args:
            ranked: Edges sorted by descending stdev.
            stop_names: Mapping from stop_id to stop_name.
            top_k: Number of highest-stdev edges to break down by hour.
    """
    top_edges: Sequence[RankedEdge] = ranked[:top_k]
    trip_id_to_group: Dict[str, GroupKey] = {}
    group_pairs: Dict[GroupKey, List[Tuple[str, str]]] = {}
    restricted_group_pairs: Dict[GroupKey, List[Tuple[str, str]]] = {}
    door_hourly_by_group: Dict[
        GroupKey, Dict[Tuple[str, str], Dict[int, List[int]]]
    ] = {}
    sw_hourly_by_group: Dict[GroupKey, Dict[Tuple[str, str], Dict[int, List[int]]]] = {}

    if not top_edges:
        return

    trip_id_to_group, group_pairs = build_trip_groups_by_line(
        subway_route_names_stop_ids_artificial, subway_routes_names_ids, TRIPS_FILE
    )
    for _, line_short_name, direction_id, pair, _ in top_edges:
        group = (line_short_name, direction_id)
        restricted_group_pairs.setdefault(group, []).append(pair)

    door_hourly_by_group, sw_hourly_by_group = (
        collect_pair_door_sw_samples_by_trip_group_hourly(
            STOP_TIMES_FILE, trip_id_to_group, restricted_group_pairs
        )
    )

    print(
        f"Hour-of-day total/door/sw breakdown for the top {len(top_edges)} highest-stdev edges:"
    )
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
            f"\n{index}. {line_short_name} dir{direction_id}  {a} ({label_a}) -> "
            f"{b} ({label_b})"
        )
        print(
            f"     overall total  {seconds_to_hms(avg):>8} ({avg:.2f}s) "
            f"cnt={count} stdev={std:.2f}s"
        )

        group = (line_short_name, direction_id)
        door_hourly = door_hourly_by_group.get(group, {}).get((a, b), {})
        sw_hourly = sw_hourly_by_group.get(group, {}).get((a, b), {})
        print()
        for hour in sorted(door_hourly):
            door_samples = door_hourly[hour]
            sw_samples = sw_hourly.get(hour, [])
            total_samples = [d + s for d, s in zip(door_samples, sw_samples)]

            total_avg = sum(total_samples) / len(total_samples)
            total_std = stdev(total_samples) if len(total_samples) > 1 else 0.0
            door_avg = sum(door_samples) / len(door_samples)
            door_std = stdev(door_samples) if len(door_samples) > 1 else 0.0
            sw_avg = sum(sw_samples) / len(sw_samples)
            sw_std = stdev(sw_samples) if len(sw_samples) > 1 else 0.0

            print(f"     {hour:02d}:00")
            print(
                f"       total  {seconds_to_hms(total_avg):>8} "
                f"({total_avg:.2f}s) cnt={len(total_samples)} stdev={total_std:.2f}s"
            )
            print(
                f"       door   {seconds_to_hms(door_avg):>8} "
                f"({door_avg:.2f}s) cnt={len(door_samples)} stdev={door_std:.2f}s"
            )
            print(
                f"       sw     {seconds_to_hms(sw_avg):>8} "
                f"({sw_avg:.2f}s) cnt={len(sw_samples)} stdev={sw_std:.2f}s"
            )
            print()


class _Tee:
    """Write to several streams at once, so stdout can also feed a report file."""

    def __init__(self, *streams: IO[str]) -> None:
        """Store the streams every write/flush call will be forwarded to.

        args:
                *streams: Writable text streams to mirror output to.
        """
        self._streams = streams

    def write(self, data: str) -> None:
        """Write the same data to every stream.

        args:
                data: Text chunk to write.
        """
        for stream in self._streams:
            stream.write(data)

    def flush(self) -> None:
        """Flush every stream.

        args:
                self: The Tee instance whose streams will be flushed.
        """
        for stream in self._streams:
            stream.flush()


def main() -> None:
    """Rank sw edges by stdev (total/door/sw) and break down the noisiest ones by hour."""
    trip_id_to_group: Dict[str, GroupKey] = {}
    group_pairs: Dict[GroupKey, List[Tuple[str, str]]] = {}
    samples_by_group: Dict[GroupKey, Dict[Tuple[str, str], List[int]]] = {}
    door_by_group: Dict[GroupKey, Dict[Tuple[str, str], List[int]]] = {}
    sw_by_group: Dict[GroupKey, Dict[Tuple[str, str], List[int]]] = {}
    avg_by_group: Dict[GroupKey, Dict[Tuple[str, str], Optional[PairRecord]]] = {}
    avg_door_by_group: Dict[GroupKey, Dict[Tuple[str, str], Optional[PairRecord]]] = {}
    avg_sw_by_group: Dict[GroupKey, Dict[Tuple[str, str], Optional[PairRecord]]] = {}
    ranked_total: List[RankedEdge] = []
    ranked_door: List[RankedEdge] = []
    ranked_sw: List[RankedEdge] = []
    relevant_stop_ids: Set[str] = set()
    stop_names: Dict[str, str] = {}

    print(
        "We rank the subway sw edges (platform -> platform) by travel-time "
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

    door_by_group, sw_by_group = collect_pair_door_sw_samples_by_trip_group(
        STOP_TIMES_FILE, trip_id_to_group, group_pairs
    )
    avg_door_by_group = {
        group: average_times_for_pairs(samples)
        for group, samples in door_by_group.items()
    }
    avg_sw_by_group = {
        group: average_times_for_pairs(samples)
        for group, samples in sw_by_group.items()
    }

    ranked_total = rank_edges_by_stdev(group_pairs, avg_by_group)
    ranked_door = rank_edges_by_stdev(group_pairs, avg_door_by_group)
    ranked_sw = rank_edges_by_stdev(group_pairs, avg_sw_by_group)

    print(f"Number of edges with at least one sample: {len(ranked_total)}\n")
    print_ranked_edges(
        ranked_total,
        avg_by_group,
        avg_door_by_group,
        avg_sw_by_group,
        stop_names,
        MIN_STDEV_TO_PRINT_SECONDS_TOTAL,
        "total",
    )
    print_ranked_edges(
        ranked_door,
        avg_by_group,
        avg_door_by_group,
        avg_sw_by_group,
        stop_names,
        MIN_STDEV_TO_PRINT_SECONDS_DOOR,
        "door",
    )
    print_ranked_edges(
        ranked_sw,
        avg_by_group,
        avg_door_by_group,
        avg_sw_by_group,
        stop_names,
        MIN_STDEV_TO_PRINT_SECONDS_SW,
        "sw",
    )
    print_hourly_breakdown(ranked_total, stop_names, TOP_K_HOURLY)


if __name__ == "__main__":
    with open(REPORT_FILE, "w", encoding="utf-8") as report_handle:
        with redirect_stdout(_Tee(sys.stdout, report_handle)):
            main()
    print(f"\nFull report written to {REPORT_FILE}")
