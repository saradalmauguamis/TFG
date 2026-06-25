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
from statistics import median, stdev
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
# (cv, line_short_name, direction_id, (from_stop_id, to_stop_id), PairRecord, median)
RankedCV = Tuple[float, str, int, Tuple[str, str], PairRecord, float]
# (hourly_range_pct, line, direction, pair, PairRecord, range, min_hour,
# min_mean, max_hour, max_mean)
RankedHourlyRange = Tuple[
    float, str, int, Tuple[str, str], PairRecord, float, int, float, int, float
]

TOP_K_HOURLY = 6
MIN_STDEV_TO_PRINT_SECONDS_TOTAL = 10.0
MIN_STDEV_TO_PRINT_SECONDS_DOOR = 10.0
MIN_STDEV_TO_PRINT_SECONDS_SW = 5.0

# CV (stdev / mean) bucket boundaries. An edge is only printed in the CV
# ranking once it crosses into the "investigate" bucket, so the print
# threshold is just the top boundary, never a separate magic number.
CV_EXTREMELY_STABLE_MAX = 0.05
CV_STABLE_MAX = 0.10
CV_ACCEPTABLE_MAX = 0.15
MIN_CV_TO_PRINT = CV_ACCEPTABLE_MAX

# Hourly-range (range / mean) bucket boundaries, same one-source-of-truth
# reasoning as the CV thresholds above.
HOURLY_RANGE_EXCELLENT_MAX = 0.05
HOURLY_RANGE_REASONABLE_MAX = 0.15
MIN_HOURLY_RANGE_PCT_TO_PRINT = HOURLY_RANGE_REASONABLE_MAX


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


def cv_bucket(cv: float) -> str:
    """Return the stability label for a coefficient of variation.

    args:
            cv: Coefficient of variation (stdev / mean) for one edge.

    returns:
            Stability label, from "extremely stable" to "investigate".
    """
    if cv < CV_EXTREMELY_STABLE_MAX:
        return "extremely stable"
    if cv < CV_STABLE_MAX:
        return "stable"
    if cv < CV_ACCEPTABLE_MAX:
        return "acceptable"
    return "investigate"


def hourly_range_bucket(hourly_range_pct: float) -> str:
    """Return the time-of-day label for an hourly range percentage.

    args:
            hourly_range_pct: Hourly mean range, normalized by the overall mean.

    returns:
            Time-of-day label, from "static weight is excellent" to
            "time-dependent routing would help".
    """
    if hourly_range_pct < HOURLY_RANGE_EXCELLENT_MAX:
        return "static weight is excellent"
    if hourly_range_pct < HOURLY_RANGE_REASONABLE_MAX:
        return "static weight still reasonable"
    return "time-dependent routing would help"


def _format_pct(count: int, total: int) -> str:
    """Format count as a percentage of total, guarding division by zero.

    args:
            count: Numerator, e.g. edges in one bucket.
            total: Denominator, e.g. total edges.

    returns:
            Percentage string, e.g. "12.3%", or "0.0%" when total is zero.
    """
    return f"{count / total:.1%}" if total else "0.0%"


def rank_edges_by_cv(
    group_pairs: Dict[GroupKey, List[Tuple[str, str]]],
    avg_by_group: Dict[GroupKey, Dict[Tuple[str, str], Optional[PairRecord]]],
    samples_by_group: Dict[GroupKey, Dict[Tuple[str, str], List[int]]],
) -> List[RankedCV]:
    """Flatten every line/direction's edges into one list, ranked by CV.

    The median (alongside the mean already in `PairRecord`) is included
    because CV is a mean/stdev ratio, and the mean can be skewed by a few
    outlier trips; the median gives a more robust read of the "typical"
    travel time for the same edge.

    args:
            group_pairs: Mapping from (line, direction_id) to its directed pairs.
            avg_by_group: Precomputed (mean, count, stdev) keyed by group.
            samples_by_group: Raw travel-time samples keyed by group, used to
                    compute each edge's median.

    returns:
            Edges with at least one sample and a positive mean, sorted by
            descending CV.
    """
    ranked: List[RankedCV] = []

    for (line_short_name, direction_id), pairs in group_pairs.items():
        averages = avg_by_group.get((line_short_name, direction_id), {})
        samples = samples_by_group.get((line_short_name, direction_id), {})
        for pair in pairs:
            record = averages.get(pair)
            if record is None:
                continue
            mean_seconds, _, std = record
            if mean_seconds <= 0:
                continue
            cv = std / mean_seconds
            pair_samples = samples.get(pair, [])
            median_seconds = median(pair_samples) if pair_samples else mean_seconds
            ranked.append(
                (cv, line_short_name, direction_id, pair, record, median_seconds)
            )

    ranked.sort(key=lambda item: (-item[0], item[1], item[2], item[3]))
    return ranked


def rank_edges_by_hourly_range(
    group_pairs: Dict[GroupKey, List[Tuple[str, str]]],
    avg_by_group: Dict[GroupKey, Dict[Tuple[str, str], Optional[PairRecord]]],
    door_hourly_by_group: Dict[GroupKey, Dict[Tuple[str, str], Dict[int, List[int]]]],
    sw_hourly_by_group: Dict[GroupKey, Dict[Tuple[str, str], Dict[int, List[int]]]],
) -> List[RankedHourlyRange]:
    """Rank edges by total hourly mean range, normalized by total mean.

    args:
            group_pairs: Mapping from (line, direction_id) to its directed pairs.
            avg_by_group: Precomputed total (mean, count, stdev) keyed by group.
            door_hourly_by_group: Door samples bucketed by hour, keyed by group.
            sw_hourly_by_group: Sw samples bucketed by hour, keyed by group.

    returns:
            Edges with at least two hours of data and a positive mean, sorted
            by descending hourly range percentage.
    """
    ranked: List[RankedHourlyRange] = []

    for (line_short_name, direction_id), pairs in group_pairs.items():
        group = (line_short_name, direction_id)
        averages = avg_by_group.get(group, {})
        for pair in pairs:
            record = averages.get(pair)
            if record is None:
                continue
            mean_seconds, _, _ = record
            if mean_seconds <= 0:
                continue

            door_hourly = door_hourly_by_group.get(group, {}).get(pair, {})
            sw_hourly = sw_hourly_by_group.get(group, {}).get(pair, {})
            hourly_means: Dict[int, float] = {}
            for hour in sorted(door_hourly):
                door_samples = door_hourly[hour]
                sw_samples = sw_hourly.get(hour, [])
                total_samples = [d + s for d, s in zip(door_samples, sw_samples)]
                if total_samples:
                    hourly_means[hour] = sum(total_samples) / len(total_samples)

            if len(hourly_means) < 2:
                continue

            min_hour = min(hourly_means, key=hourly_means.get)
            max_hour = max(hourly_means, key=hourly_means.get)
            hourly_range = hourly_means[max_hour] - hourly_means[min_hour]
            hourly_range_pct = hourly_range / mean_seconds
            ranked.append(
                (
                    hourly_range_pct,
                    line_short_name,
                    direction_id,
                    pair,
                    record,
                    hourly_range,
                    min_hour,
                    hourly_means[min_hour],
                    max_hour,
                    hourly_means[max_hour],
                )
            )

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


def print_cv_ranking(
    ranked: Sequence[RankedCV],
    stop_names: Dict[str, str],
    min_cv: float,
) -> None:
    """Print total travel-time CV ranking and stability summary.

    args:
            ranked: Edges sorted by descending CV, from `rank_edges_by_cv`.
            stop_names: Mapping from stop_id to stop_name.
            min_cv: Only print edges whose CV is at least this fraction.
    """
    buckets = {
        "extremely stable": 0,
        "stable": 0,
        "acceptable": 0,
        "investigate": 0,
    }
    total_edges = len(ranked)
    above_threshold: List[RankedCV] = [edge for edge in ranked if edge[0] >= min_cv]

    for cv, _, _, _, _, _ in ranked:
        buckets[cv_bucket(cv)] += 1

    def _pct(count: int) -> str:
        """Format a bucket count as a percentage of total_edges.

        args:
                count: Number of edges in the bucket.

        returns:
                Percentage string, e.g. "12.3%", or "0.0%" when there are no edges.
        """
        return _format_pct(count, total_edges)

    print("Edge stability by coefficient of variation")
    print("CV = stdev / mean, computed from total travel time.\n")
    print("Stability summary:")
    print(
        f"  CV < {CV_EXTREMELY_STABLE_MAX:.0%}     extremely stable: "
        f"{buckets['extremely stable']} ({_pct(buckets['extremely stable'])})"
    )
    print(
        f"  CV < {CV_STABLE_MAX:.0%}    stable: "
        f"{buckets['stable']} ({_pct(buckets['stable'])})"
    )
    print(
        f"  CV < {CV_ACCEPTABLE_MAX:.0%}    acceptable: "
        f"{buckets['acceptable']} ({_pct(buckets['acceptable'])})"
    )
    print(
        f"  CV >= {CV_ACCEPTABLE_MAX:.0%}   investigate: "
        f"{buckets['investigate']} ({_pct(buckets['investigate'])})\n"
    )

    print(
        f"Edges ranked by total CV (highest first, CV >= {min_cv:.0%}): "
        f"{len(above_threshold)} of {total_edges}"
    )
    if not above_threshold:
        print()
        return

    for index, (
        cv,
        line_short_name,
        direction_id,
        (a, b),
        (avg, count, std),
        median_seconds,
    ) in enumerate(above_threshold, start=1):
        label_a = f"{line_short_name}-{stop_names.get(a, a)}"
        label_b = f"{line_short_name}-{stop_names.get(b, b)}"
        print(
            f"{index}. {line_short_name} dir{direction_id}  {a} ({label_a}) -> "
            f"{b} ({label_b})  [CV={cv:.2%}: {cv_bucket(cv)}]"
        )
        print(
            f"     total  mean={seconds_to_hms(avg):>8} ({avg:.2f}s) "
            f"median={seconds_to_hms(median_seconds):>8} ({median_seconds:.2f}s) "
            f"cnt={count} stdev={std:.2f}s cv={cv:.2%}"
        )
    print()


def print_hourly_range_ranking(
    ranked: Sequence[RankedHourlyRange],
    stop_names: Dict[str, str],
    min_hourly_range_pct: float,
) -> None:
    """Print total hourly range ranking and time-of-day summary.

    args:
            ranked: Edges sorted by descending hourly range percentage, from
                    `rank_edges_by_hourly_range`.
            stop_names: Mapping from stop_id to stop_name.
            min_hourly_range_pct: Only print edges whose hourly range
                    percentage is at least this fraction.
    """
    buckets = {
        "static weight is excellent": 0,
        "static weight still reasonable": 0,
        "time-dependent routing would help": 0,
    }
    total_edges = len(ranked)
    above_threshold: List[RankedHourlyRange] = [
        edge for edge in ranked if edge[0] >= min_hourly_range_pct
    ]

    for hourly_range_pct, _, _, _, _, _, _, _, _, _ in ranked:
        buckets[hourly_range_bucket(hourly_range_pct)] += 1

    def _pct(count: int) -> str:
        """Format a bucket count as a percentage of total_edges.

        args:
                count: Number of edges in the bucket.

        returns:
                Percentage string, e.g. "12.3%", or "0.0%" when there are no edges.
        """
        return _format_pct(count, total_edges)

    print("Time-of-day variation by hourly range")
    print(
        "Hourly range = max(hourly mean) - min(hourly mean), normalized by "
        "overall total mean.\n"
    )
    print("Time-of-day summary:")
    print(
        f"  hourly range < {HOURLY_RANGE_EXCELLENT_MAX:.0%}     "
        "static weight is excellent: "
        f"{buckets['static weight is excellent']} "
        f"({_pct(buckets['static weight is excellent'])})"
    )
    print(
        f"  hourly range < {HOURLY_RANGE_REASONABLE_MAX:.0%}    "
        "static weight still reasonable: "
        f"{buckets['static weight still reasonable']} "
        f"({_pct(buckets['static weight still reasonable'])})"
    )
    print(
        f"  hourly range >= {HOURLY_RANGE_REASONABLE_MAX:.0%}   "
        "time-dependent routing would help: "
        f"{buckets['time-dependent routing would help']} "
        f"({_pct(buckets['time-dependent routing would help'])})\n"
    )

    print(
        "Edges ranked by total hourly range percentage "
        f"(highest first, range >= {min_hourly_range_pct:.0%}): "
        f"{len(above_threshold)} of {total_edges}"
    )
    if not above_threshold:
        print()
        return

    for index, (
        hourly_range_pct,
        line_short_name,
        direction_id,
        (a, b),
        (avg, count, std),
        hourly_range,
        min_hour,
        min_mean,
        max_hour,
        max_mean,
    ) in enumerate(above_threshold, start=1):
        label_a = f"{line_short_name}-{stop_names.get(a, a)}"
        label_b = f"{line_short_name}-{stop_names.get(b, b)}"
        print(
            f"{index}. {line_short_name} dir{direction_id}  {a} ({label_a}) -> "
            f"{b} ({label_b})  "
            f"[range={hourly_range:.2f}s, {hourly_range_pct:.2%}: "
            f"{hourly_range_bucket(hourly_range_pct)}]"
        )
        print(
            f"     overall total  {seconds_to_hms(avg):>8} ({avg:.2f}s) "
            f"cnt={count} stdev={std:.2f}s"
        )
        print(
            f"     min hourly mean  {min_hour:02d}:00  "
            f"{seconds_to_hms(min_mean):>8} ({min_mean:.2f}s)"
        )
        print(
            f"     max hourly mean  {max_hour:02d}:00  "
            f"{seconds_to_hms(max_mean):>8} ({max_mean:.2f}s)"
        )
    print()


def print_hourly_breakdown(
    ranked: Sequence[RankedHourlyRange],
    stop_names: Dict[str, str],
    top_k: int,
) -> None:
    """Print an hour-bucket total/door/sw breakdown for top hourly-range edges.

    The hour bucket is the arrival hour at the first stop of each pair (a
    departure-hour proxy, since stop_times only carries arrival_time for
    intermediate platforms). Door and sw are bucketed in lockstep by
    `collect_pair_door_sw_samples_by_trip_group_hourly`, so the per-hour total
    is derived as their elementwise sum, and all three (total/door/sw) are
    printed per hour: a wide spread *within* a single hour (not just a shift
    *between* hours) can itself be door- or sw-driven.

    args:
            ranked: Edges sorted by descending total hourly range percentage.
            stop_names: Mapping from stop_id to stop_name.
            top_k: Number of highest hourly-range edges to break down by hour.
    """
    top_edges: Sequence[RankedHourlyRange] = ranked[:top_k]
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
    for _, line_short_name, direction_id, pair, _, _, _, _, _, _ in top_edges:
        group = (line_short_name, direction_id)
        restricted_group_pairs.setdefault(group, []).append(pair)

    door_hourly_by_group, sw_hourly_by_group = (
        collect_pair_door_sw_samples_by_trip_group_hourly(
            STOP_TIMES_FILE, trip_id_to_group, restricted_group_pairs
        )
    )

    print(
        "Hour-of-day total/door/sw breakdown for the top "
        f"{len(top_edges)} highest hourly-range edges:"
    )
    print("(hour = arrival at the first stop of the pair, a departure-hour proxy)\n")
    for index, (
        hourly_range_pct,
        line_short_name,
        direction_id,
        (a, b),
        (avg, count, std),
        hourly_range,
        _,
        _,
        _,
        _,
    ) in enumerate(top_edges, start=1):
        label_a = f"{line_short_name}-{stop_names.get(a, a)}"
        label_b = f"{line_short_name}-{stop_names.get(b, b)}"
        print(
            f"\n{index}. {line_short_name} dir{direction_id}  {a} ({label_a}) -> "
            f"{b} ({label_b})"
        )
        print(
            f"     overall total  {seconds_to_hms(avg):>8} ({avg:.2f}s) "
            f"cnt={count} stdev={std:.2f}s "
            f"hourly_range={hourly_range:.2f}s ({hourly_range_pct:.2%})"
        )

        group = (line_short_name, direction_id)
        door_hourly = door_hourly_by_group.get(group, {}).get((a, b), {})
        sw_hourly = sw_hourly_by_group.get(group, {}).get((a, b), {})
        print()
        for hour in sorted(door_hourly):
            door_samples = door_hourly[hour]
            sw_samples = sw_hourly.get(hour, [])
            total_samples = [d + s for d, s in zip(door_samples, sw_samples)]
            if not total_samples:
                continue

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


def print_executive_summary(
    ranked_cv: Sequence[RankedCV],
    ranked_hourly_range: Sequence[RankedHourlyRange],
    stop_names: Dict[str, str],
    min_cv: float,
    min_hourly_range_pct: float,
) -> None:
    """Print a compact stability/time-of-day summary and the edges to review.

    Collapses the CV and hourly-range sections above into a few lines, plus
    the union of edges that crossed either threshold, so a reader doesn't
    have to scan every edge listing to find the conclusion.

    args:
            ranked_cv: Edges sorted by descending CV, from `rank_edges_by_cv`.
            ranked_hourly_range: Edges sorted by descending hourly range
                    percentage, from `rank_edges_by_hourly_range`.
            stop_names: Mapping from stop_id to stop_name.
            min_cv: CV threshold an edge must reach to be flagged.
            min_hourly_range_pct: Hourly range percentage threshold an edge
                    must reach to be flagged.
    """
    total_cv_edges = len(ranked_cv)
    stable_cv = sum(
        1 for cv, *_ in ranked_cv if cv_bucket(cv) in ("extremely stable", "stable")
    )
    investigate_cv = sum(1 for cv, *_ in ranked_cv if cv_bucket(cv) == "investigate")
    acceptable_cv = total_cv_edges - stable_cv - investigate_cv

    total_hourly_edges = len(ranked_hourly_range)
    time_dependent = sum(
        1
        for pct, *_ in ranked_hourly_range
        if hourly_range_bucket(pct) == "time-dependent routing would help"
    )
    static_ok = total_hourly_edges - time_dependent

    flagged_keys = {
        (line, direction, pair)
        for cv, line, direction, pair, *_ in ranked_cv
        if cv >= min_cv
    } | {
        (line, direction, pair)
        for pct, line, direction, pair, *_ in ranked_hourly_range
        if pct >= min_hourly_range_pct
    }
    flagged_edges = sorted(flagged_keys)

    print("=== Summary ===")
    print(f"{total_cv_edges} sw edges analyzed.\n")
    print(
        f"Stability (CV): {stable_cv} stable/extremely stable "
        f"({_format_pct(stable_cv, total_cv_edges)}), {acceptable_cv} "
        f"acceptable ({_format_pct(acceptable_cv, total_cv_edges)}), "
        f"{investigate_cv} need investigation "
        f"({_format_pct(investigate_cv, total_cv_edges)})."
    )
    print(
        f"Time-of-day: {static_ok} edges have a static weight that's fine "
        f"({_format_pct(static_ok, total_hourly_edges)}), {time_dependent} "
        "would benefit from time-dependent routing "
        f"({_format_pct(time_dependent, total_hourly_edges)})."
    )

    if not flagged_edges:
        print("\nNo edges crossed either threshold; no edges need attention.")
        return

    print(
        f"\nEdges needing attention ({len(flagged_edges)}, high CV or high hourly range):"
    )
    for line_short_name, direction_id, (a, b) in flagged_edges:
        label_a = f"{line_short_name}-{stop_names.get(a, a)}"
        label_b = f"{line_short_name}-{stop_names.get(b, b)}"
        print(
            f"  - {line_short_name} dir{direction_id}  {a} ({label_a}) -> {b} ({label_b})"
        )


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
    """Rank sw edges by stdev, CV and hourly range."""
    trip_id_to_group: Dict[str, GroupKey] = {}
    group_pairs: Dict[GroupKey, List[Tuple[str, str]]] = {}
    samples_by_group: Dict[GroupKey, Dict[Tuple[str, str], List[int]]] = {}
    door_by_group: Dict[GroupKey, Dict[Tuple[str, str], List[int]]] = {}
    sw_by_group: Dict[GroupKey, Dict[Tuple[str, str], List[int]]] = {}
    avg_by_group: Dict[GroupKey, Dict[Tuple[str, str], Optional[PairRecord]]] = {}
    avg_door_by_group: Dict[GroupKey, Dict[Tuple[str, str], Optional[PairRecord]]] = {}
    avg_sw_by_group: Dict[GroupKey, Dict[Tuple[str, str], Optional[PairRecord]]] = {}
    door_hourly_by_group: Dict[
        GroupKey, Dict[Tuple[str, str], Dict[int, List[int]]]
    ] = {}
    sw_hourly_by_group: Dict[GroupKey, Dict[Tuple[str, str], Dict[int, List[int]]]] = {}
    ranked_total: List[RankedEdge] = []
    ranked_door: List[RankedEdge] = []
    ranked_sw: List[RankedEdge] = []
    ranked_cv: List[RankedCV] = []
    ranked_hourly_range: List[RankedHourlyRange] = []
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
    ranked_cv = rank_edges_by_cv(group_pairs, avg_by_group, samples_by_group)

    door_hourly_by_group, sw_hourly_by_group = (
        collect_pair_door_sw_samples_by_trip_group_hourly(
            STOP_TIMES_FILE, trip_id_to_group, group_pairs
        )
    )
    ranked_hourly_range = rank_edges_by_hourly_range(
        group_pairs, avg_by_group, door_hourly_by_group, sw_hourly_by_group
    )

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
    print_cv_ranking(ranked_cv, stop_names, MIN_CV_TO_PRINT)
    print_hourly_range_ranking(
        ranked_hourly_range, stop_names, MIN_HOURLY_RANGE_PCT_TO_PRINT
    )
    print_hourly_breakdown(ranked_hourly_range, stop_names, TOP_K_HOURLY)
    print_executive_summary(
        ranked_cv,
        ranked_hourly_range,
        stop_names,
        MIN_CV_TO_PRINT,
        MIN_HOURLY_RANGE_PCT_TO_PRINT,
    )


if __name__ == "__main__":
    with open(REPORT_FILE, "w", encoding="utf-8") as report_handle:
        with redirect_stdout(_Tee(sys.stdout, report_handle)):
            main()
    print(f"\nFull report written to {REPORT_FILE}")
