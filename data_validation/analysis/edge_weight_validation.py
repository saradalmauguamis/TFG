"""Validate whether mean(total) is a trustworthy static edge weight, on the final stop_times.

The graph's `sw` edges (platform -> platform) get their weight from the mean
travel time observed in stop_times, where each sample is `arrival_b -
arrival_a` (the same convention `collect_pair_samples_by_trip_group` already
uses for every other directed-pair analysis in this codebase). This script
checks whether that mean is trustworthy, for every directed consecutive-stop
pair on every subway line, two ways: overall variability (CV = stdev / mean)
and time-of-day structure (hourly range, the gap between the highest and
lowest hourly mean). The two aren't independent (see the printed
explanation), computed from `STOP_TIMES_FILE` (`stop_times_shared.txt`, the
latest pipeline stage, post shared-platform duplication).

`total = arrival_b - arrival_a` conflates two physically different things:
dwell at the departure platform A (door open for boarding) and the actual
movement between A and B. The edge weight stays `total`, since that's the
real time to get from A to B; every flagged edge is decomposed into `door`
(`departure_a - arrival_a`) and `sw` (`arrival_b - departure_a`, time spent
actually moving) only as a diagnostic, via
`collect_pair_door_sw_samples_by_trip_group`, to see how much of the stdev is
dwell-time noise versus genuine travel-time variance.

Because this script reads the post-duplication stop_times, it uses
`subway_reference.subway_lines.subway_route_names_stop_ids_artificial` (the per-line stop_id
lists rewritten for split shared platforms) rather than the original
`subway_route_names_stop_ids`, which still has lines sharing a stop_id and so
no longer matches the IDs in `stop_times_shared.txt`.

For the edges that actually crossed the CV or hourly-range threshold, a
second targeted pass breaks the same total/door/sw decomposition down by
hour (bucketed by arrival at the first stop of the pair, used as a
departure-hour proxy), so a reader can see the real per-hour pattern behind
the CV/hourly-range numbers before trusting (or not) a single static mean as
the edge weight for shortest-path algorithms on the resulting weighted graph
(Dijkstra or otherwise).
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
from subway_reference.subway_lines import (  # noqa: E402
    subway_route_names_stop_ids_artificial,
    subway_routes_names_ids,
)

REPORT_FILE = Path(__file__).resolve().parent / "edge_weight_validation_report.txt"

GroupKey = Tuple[str, int]  # (line_short_name, direction_id)
PairRecord = Tuple[float, int, float]  # (mean, count, stdev)
# (cv, line_short_name, direction_id, (from_stop_id, to_stop_id), PairRecord, median)
RankedCV = Tuple[float, str, int, Tuple[str, str], PairRecord, float]
# (hourly_range_pct, line, direction, pair, PairRecord, range, min_hours,
# min_mean, max_hours, max_mean)
RankedHourlyRange = Tuple[
    float,
    str,
    int,
    Tuple[str, str],
    PairRecord,
    float,
    List[int],
    float,
    List[int],
    float,
]

TOP_K_HOURLY_CV = 2
TOP_K_HOURLY_TIME = 2

# CV (stdev / mean) bucket boundaries
CV_EXTREMELY_STABLE_MAX = 0.05
CV_STABLE_MAX = 0.10
CV_ACCEPTABLE_MAX = 0.15
MIN_CV_TO_PRINT = CV_ACCEPTABLE_MAX

SECTION_BANNER_WIDTH = 70

# Hourly-range (range / mean) bucket boundaries
HOURLY_RANGE_EXCELLENT_MAX = 0.05
HOURLY_RANGE_REASONABLE_MAX = 0.15
MIN_HOURLY_RANGE_PCT_TO_PRINT = HOURLY_RANGE_REASONABLE_MAX

# Minimum share of (door_stdev + sw_stdev) one side must hold to call it
# "dominant"; below this (e.g. 51/49) neither side is worth singling out.
DOMINANT_STDEV_SHARE_MIN = 0.70

_LINE_ORDER = {
    line: index for index, line in enumerate(subway_route_names_stop_ids_artificial)
}

_OBJECTIVE_EXPLANATION = (
    "Is mean(total) per sw edge (platform -> platform) a trustworthy "
    "static weight for shortest-path algorithms on the weighted graph? "
    "We test this two ways.\n"
    "  1. Overall variability (CV). Is the spread small relative "
    "to the mean, regardless of cause?\n"
    "  2. Time-of-day structure (hourly range). Does the mean hide a "
    "rush/off-peak pattern a static weight would wash out?\n"
    "The edge weight itself stays total ('arrival_b - arrival_a'). "
    "Every flagged edge also gets it split into door ('departure_a - "
    "arrival_a', dwell at the boarding platform) and sw ('arrival_b - "
    "departure_a', time spent actually moving between platforms), as a "
    "diagnostic for *why* it's noisy, not as a third thing being proven.\n"
)

_INDEPENDENCE_EXPLANATION = (
    "These two tests are not independent. CV is computed from samples "
    "pooled across the whole day, so it reacts to both true randomness "
    "within an hour and a real rush/off-peak shift between hours. An "
    "edge can have a stable mean within every hour and still fail CV "
    "purely because those per-hour means differ from each other. The "
    "hourly-range test isolates that second cause specifically: it's "
    "what tells you whether a CV failure comes from genuine time-of-day "
    "structure (fixable with time-dependent routing) or from noise "
    "that's present even within a single hour (not fixable that way).\n"
)


def _print_section_header(title: str) -> None:
    """Print a section title inside a banner, to visually separate report sections.

    args:
            title: Section title, printed upper-case between two divider lines.
    """
    divider = "=" * SECTION_BANNER_WIDTH
    print(f"\n{divider}")
    print(title.upper())
    print(f"{divider}\n")


def cv_bucket(cv: float) -> str:
    """Return the stability label for a coefficient of variation.

    args:
            cv: Coefficient of variation (stdev / mean) for one edge.

    returns:
            Stability label, from "extremely stable" to "unstable".
    """
    if cv < CV_EXTREMELY_STABLE_MAX:
        return "extremely stable"
    if cv < CV_STABLE_MAX:
        return "stable"
    if cv < CV_ACCEPTABLE_MAX:
        return "acceptable"
    return "unstable"


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
    return f"{count / total:.2%}" if total else "0.0%"


def _stop_labels(stop_names: Dict[str, str], a: str, b: str) -> Tuple[str, str]:
    """Look up display labels for both stops in a directed pair.

    args:
            stop_names: Mapping from stop_id to stop_name.
            a: From-stop_id.
            b: To-stop_id.

    returns:
            (label_a, label_b), each the stop_name or, if unknown, the stop_id.
    """
    return stop_names.get(a, a), stop_names.get(b, b)


def _door_sw_records(
    avg_door_by_group: Dict[GroupKey, Dict[Tuple[str, str], Optional[PairRecord]]],
    avg_sw_by_group: Dict[GroupKey, Dict[Tuple[str, str], Optional[PairRecord]]],
    group: GroupKey,
    pair: Tuple[str, str],
) -> Tuple[Optional[PairRecord], Optional[PairRecord]]:
    """Look up an edge's door and sw records for one group/pair.

    args:
            avg_door_by_group: Door (mean, count, stdev) per group/pair.
            avg_sw_by_group: Sw (mean, count, stdev) per group/pair.
            group: (line_short_name, direction_id).
            pair: (from_stop_id, to_stop_id).

    returns:
            (door_record, sw_record), either None when missing.
    """
    return avg_door_by_group.get(group, {}).get(pair), avg_sw_by_group.get(
        group, {}
    ).get(pair)


def _dominant_stdev(
    door_record: Optional[PairRecord], sw_record: Optional[PairRecord]
) -> Optional[str]:
    """Return whether door or sw holds most of the combined stdev, when both are known.

    Dominance is by *share* of door_stdev + sw_stdev, not just which is
    larger: a 51/49 split isn't meaningfully "dominated" by either side, so
    it's reported as neither (see `DOMINANT_STDEV_SHARE_MIN`).

    args:
            door_record: Door (mean, count, stdev), or None if missing.
            sw_record: Sw (mean, count, stdev), or None if missing.

    returns:
            "door" or "sw" if one holds at least `DOMINANT_STDEV_SHARE_MIN` of
            the combined stdev, otherwise None (including when either record
            is missing or both stdevs are zero).
    """
    door_std: float = 0.0
    sw_std: float = 0.0
    total_std: float = 0.0

    if door_record is None or sw_record is None:
        return None
    door_std, sw_std = door_record[2], sw_record[2]
    total_std = door_std + sw_std
    if total_std <= 0:
        return None
    if door_std / total_std >= DOMINANT_STDEV_SHARE_MIN:
        return "door"
    if sw_std / total_std >= DOMINANT_STDEV_SHARE_MIN:
        return "sw"
    return None


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
            by descending hourly range percentage. min_hours/max_hours list
            every hour tied for the minimum/maximum hourly mean, rather than
            an arbitrary single hour, since ties are common with low sample
            counts per hour.
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

            min_mean = min(hourly_means.values())
            max_mean = max(hourly_means.values())
            min_hours = sorted(h for h, m in hourly_means.items() if m == min_mean)
            max_hours = sorted(h for h, m in hourly_means.items() if m == max_mean)
            hourly_range = max_mean - min_mean
            hourly_range_pct = hourly_range / mean_seconds
            ranked.append(
                (
                    hourly_range_pct,
                    line_short_name,
                    direction_id,
                    pair,
                    record,
                    hourly_range,
                    min_hours,
                    min_mean,
                    max_hours,
                    max_mean,
                )
            )

    ranked.sort(key=lambda item: (-item[0], item[1], item[2], item[3]))
    return ranked


def print_cv_ranking(
    ranked: Sequence[RankedCV],
    avg_door_by_group: Dict[GroupKey, Dict[Tuple[str, str], Optional[PairRecord]]],
    avg_sw_by_group: Dict[GroupKey, Dict[Tuple[str, str], Optional[PairRecord]]],
    stop_names: Dict[str, str],
    min_cv: float,
) -> None:
    """Print total travel-time CV ranking and stability summary.

    For every edge printed (CV >= min_cv), also prints the `door`
    (`departure_a - arrival_a`) and `sw` (`arrival_b - departure_a`) mean and
    stdev, looked up from `avg_door_by_group`/`avg_sw_by_group`, plus which
    of the two has the larger stdev (with both numbers shown alongside, so
    the comparison being made is explicit), so a reader can tell at a glance
    whether a noisy edge's variance comes from boarding/alighting dwell or
    from genuine run-time variance.

    args:
            ranked: Edges sorted by descending CV, from `rank_edges_by_cv`.
            avg_door_by_group: Door (mean, count, stdev) per group/pair.
            avg_sw_by_group: Sw (mean, count, stdev) per group/pair.
            stop_names: Mapping from stop_id to stop_name.
            min_cv: Only print edges whose CV is at least this fraction.
    """
    buckets = {
        "extremely stable": 0,
        "stable": 0,
        "acceptable": 0,
        "unstable": 0,
    }
    total_edges = len(ranked)
    above_threshold: List[RankedCV] = [edge for edge in ranked if edge[0] >= min_cv]

    for cv, _, _, _, _, _ in ranked:
        buckets[cv_bucket(cv)] += 1

    _print_section_header("Edge stability by coefficient of variation")
    print("CV = stdev / mean, computed from total travel time.\n")
    print("Stability summary:")
    print(
        f"  CV < {CV_EXTREMELY_STABLE_MAX:.0%}                       extremely stable: "
        f"{buckets['extremely stable']} ({_format_pct(buckets['extremely stable'], total_edges)})"
    )
    print(
        f"  {CV_EXTREMELY_STABLE_MAX:.0%} <= CV < {CV_STABLE_MAX:.0%}                stable: "
        f"{buckets['stable']} ({_format_pct(buckets['stable'], total_edges)})"
    )
    print(
        f"  {CV_STABLE_MAX:.0%} <= CV < {CV_ACCEPTABLE_MAX:.0%}                acceptable: "
        f"{buckets['acceptable']} ({_format_pct(buckets['acceptable'], total_edges)})"
    )
    print(
        f"  {CV_ACCEPTABLE_MAX:.0%} <= CV                      unstable: "
        f"{buckets['unstable']} ({_format_pct(buckets['unstable'], total_edges)})\n"
    )

    print(
        f"Edges ranked by total CV (highest first, {min_cv:.0%} <= CV): "
        f"{len(above_threshold)} of {total_edges} "
        f"({_format_pct(len(above_threshold), total_edges)})"
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
        label_a, label_b = _stop_labels(stop_names, a, b)
        print(
            f"{index}. {line_short_name} dir{direction_id}  {a} ({label_a}) -> "
            f"{b} ({label_b})  [CV={cv:.2%}: {cv_bucket(cv)}]"
        )
        print(
            f"     total  mean={seconds_to_hms(avg)} ({avg:.2f}s) "
            f"median={seconds_to_hms(median_seconds)} ({median_seconds:.2f}s) "
            f"cnt={count} stdev={std:.2f}s cv={cv:.2%}"
        )

        door_record, sw_record = _door_sw_records(
            avg_door_by_group, avg_sw_by_group, (line_short_name, direction_id), (a, b)
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
        dominant = _dominant_stdev(door_record, sw_record)
        if dominant is not None:
            print(
                f"     -> stdev dominated by {dominant} "
                f"(door={door_record[2]:.2f}s vs sw={sw_record[2]:.2f}s)"
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

    _print_section_header("Time-of-day variation by hourly range")
    print(
        "Hourly range = max(hourly mean) - min(hourly mean), normalized by "
        "overall total mean.\n"
    )
    print("Time-of-day summary:")
    print(
        f"  hourly range < {HOURLY_RANGE_EXCELLENT_MAX:.0%}     "
        "static weight is excellent: "
        f"{buckets['static weight is excellent']} "
        f"({_format_pct(buckets['static weight is excellent'], total_edges)})"
    )
    print(
        f"  {HOURLY_RANGE_EXCELLENT_MAX:.0%} <= hourly range < {HOURLY_RANGE_REASONABLE_MAX:.0%}   "
        "static weight still reasonable: "
        f"{buckets['static weight still reasonable']} "
        f"({_format_pct(buckets['static weight still reasonable'], total_edges)})"
    )
    print(
        f"  {HOURLY_RANGE_REASONABLE_MAX:.0%} <= hourly range  "
        "time-dependent routing would help: "
        f"{buckets['time-dependent routing would help']} "
        f"({_format_pct(buckets['time-dependent routing would help'], total_edges)})\n"
    )

    print(
        "Edges ranked by total hourly range percentage "
        f"(highest first, range >= {min_hourly_range_pct:.0%}): "
        f"{len(above_threshold)} of {total_edges} "
        f"({_format_pct(len(above_threshold), total_edges)})"
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
        min_hours,
        min_mean,
        max_hours,
        max_mean,
    ) in enumerate(above_threshold, start=1):
        label_a, label_b = _stop_labels(stop_names, a, b)
        min_hours_str = ", ".join(f"{hour:02d}:00" for hour in min_hours)
        max_hours_str = ", ".join(f"{hour:02d}:00" for hour in max_hours)
        print(
            f"{index}. {line_short_name} dir{direction_id}  {a} ({label_a}) -> "
            f"{b} ({label_b})  "
            f"[range={hourly_range:.2f}s, {hourly_range_pct:.2%}]"
        )
        print(
            f"     overall total  {seconds_to_hms(avg):>8} ({avg:.2f}s) "
            f"cnt={count} stdev={std:.2f}s"
        )
        print(
            f"     min hourly mean  {min_hours_str}  "
            f"{seconds_to_hms(min_mean):>8} ({min_mean:.2f}s)"
        )
        print(
            f"     max hourly mean  {max_hours_str}  "
            f"{seconds_to_hms(max_mean):>8} ({max_mean:.2f}s)"
        )
    print()


def _print_edge_summary(
    index: int,
    line_short_name: str,
    direction_id: int,
    pair: Tuple[str, str],
    avg: float,
    count: int,
    std: float,
    avg_door_by_group: Dict[GroupKey, Dict[Tuple[str, str], Optional[PairRecord]]],
    avg_sw_by_group: Dict[GroupKey, Dict[Tuple[str, str], Optional[PairRecord]]],
    stop_names: Dict[str, str],
    extra_summary: str,
    extra_lines: Sequence[str] = (),
) -> None:
    """Print one edge's header plus its overall total/door/sw summary.

    args:
            index: 1-based position of this edge within its section.
            line_short_name: Subway line, e.g. "L1".
            direction_id: 0 or 1.
            pair: (from_stop_id, to_stop_id).
            avg: Overall mean total travel time, in seconds.
            count: Overall sample count.
            std: Overall total stdev, in seconds.
            avg_door_by_group: Door (mean, count, stdev) per group/pair.
            avg_sw_by_group: Sw (mean, count, stdev) per group/pair.
            stop_names: Mapping from stop_id to stop_name.
            extra_summary: Test-specific suffix appended to the overall
                    total line (CV or hourly range, depending on caller).
            extra_lines: Extra lines printed after the door/sw summary,
                    e.g. min/max hourly mean for the hourly-range section.
    """
    a, b = pair
    label_a, label_b = _stop_labels(stop_names, a, b)
    door_record, sw_record = _door_sw_records(
        avg_door_by_group, avg_sw_by_group, (line_short_name, direction_id), pair
    )

    print(
        f"\n{index}. {line_short_name} dir{direction_id}  {a} ({label_a}) -> "
        f"{b} ({label_b})"
    )
    print(
        f"     overall total  {seconds_to_hms(avg):>8} ({avg:.2f}s) "
        f"cnt={count} stdev={std:.2f}s{extra_summary}"
    )

    if door_record is not None:
        door_avg, door_count, door_std = door_record
        print(
            f"     overall door   {seconds_to_hms(door_avg):>8} "
            f"({door_avg:.2f}s) cnt={door_count} stdev={door_std:.2f}s"
        )
    if sw_record is not None:
        sw_avg, sw_count, sw_std = sw_record
        print(
            f"     overall sw     {seconds_to_hms(sw_avg):>8} "
            f"({sw_avg:.2f}s) cnt={sw_count} stdev={sw_std:.2f}s"
        )
    for line_text in extra_lines:
        print(line_text)


def _print_hour_table(
    line_short_name: str,
    direction_id: int,
    pair: Tuple[str, str],
    door_hourly_by_group: Dict[GroupKey, Dict[Tuple[str, str], Dict[int, List[int]]]],
    sw_hourly_by_group: Dict[GroupKey, Dict[Tuple[str, str], Dict[int, List[int]]]],
) -> None:
    """Print the per-hour total/door/sw breakdown table for one edge.

    args:
            line_short_name: Subway line, e.g. "L1".
            direction_id: 0 or 1.
            pair: (from_stop_id, to_stop_id).
            door_hourly_by_group: Door samples bucketed by hour, keyed by group.
            sw_hourly_by_group: Sw samples bucketed by hour, keyed by group.
    """
    group = (line_short_name, direction_id)
    door_hourly = door_hourly_by_group.get(group, {}).get(pair, {})
    sw_hourly = sw_hourly_by_group.get(group, {}).get(pair, {})
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


def print_hourly_breakdown(
    ranked_cv: Sequence[RankedCV],
    ranked_hourly_range: Sequence[RankedHourlyRange],
    avg_door_by_group: Dict[GroupKey, Dict[Tuple[str, str], Optional[PairRecord]]],
    avg_sw_by_group: Dict[GroupKey, Dict[Tuple[str, str], Optional[PairRecord]]],
    stop_names: Dict[str, str],
    top_k_cv: int,
    top_k_time: int,
    min_cv: float,
    min_hourly_range_pct: float,
) -> None:
    """Print an hour-bucket total/door/sw breakdown for the top CV and hourly-range edges.

    The hour bucket is the arrival hour at the first stop of each pair (a
    departure-hour proxy, since stop_times only carries arrival_time for
    intermediate platforms). Door and sw are bucketed in lockstep by
    `collect_pair_door_sw_samples_by_trip_group_hourly`, so the per-hour total
    is derived as their elementwise sum, and all three (total/door/sw) are
    printed per hour: a wide spread *within* a single hour (not just a shift
    *between* hours) can itself be door- or sw-driven.

    Only edges that actually crossed their respective threshold (min_cv,
    min_hourly_range_pct) are eligible, even if top_k_cv/top_k_time allow
    more: there is no point breaking a stable/static-fine edge down by hour
    just to fill a quota.

    A top-CV edge can also be among the top hourly-range edges (the two tests
    aren't independent, see the explanation above). When that happens, the
    edge's overall summary (including its hourly min/max, in the
    hourly-range section) is still printed both times, but the per-hour
    total/door/sw table itself is only printed once, under the CV section,
    with the hourly-range section pointing back to it instead of repeating
    it.

    args:
            ranked_cv: Edges sorted by descending CV, from `rank_edges_by_cv`.
            ranked_hourly_range: Edges sorted by descending total hourly
                    range percentage, from `rank_edges_by_hourly_range`.
            avg_door_by_group: Door (mean, count, stdev) per group/pair.
            avg_sw_by_group: Sw (mean, count, stdev) per group/pair.
            stop_names: Mapping from stop_id to stop_name.
            top_k_cv: Max number of highest-CV edges to break down by hour.
            top_k_time: Max number of highest hourly-range edges to break
                    down by hour.
            min_cv: CV threshold an edge must reach to be eligible.
            min_hourly_range_pct: Hourly range percentage threshold an edge
                    must reach to be eligible.
    """
    top_cv_edges: Sequence[RankedCV] = [
        edge for edge in ranked_cv if edge[0] >= min_cv
    ][:top_k_cv]
    top_time_edges: Sequence[RankedHourlyRange] = [
        edge for edge in ranked_hourly_range if edge[0] >= min_hourly_range_pct
    ][:top_k_time]
    trip_id_to_group: Dict[str, GroupKey] = {}
    _: Dict[GroupKey, List[Tuple[str, str]]] = {}
    restricted_group_pairs: Dict[GroupKey, List[Tuple[str, str]]] = {}
    door_hourly_by_group: Dict[
        GroupKey, Dict[Tuple[str, str], Dict[int, List[int]]]
    ] = {}
    sw_hourly_by_group: Dict[GroupKey, Dict[Tuple[str, str], Dict[int, List[int]]]] = {}
    printed_at: Dict[Tuple[str, int, Tuple[str, str]], int] = {}

    if not top_cv_edges and not top_time_edges:
        return

    trip_id_to_group, _ = build_trip_groups_by_line(
        subway_route_names_stop_ids_artificial, subway_routes_names_ids, TRIPS_FILE
    )
    for _, line_short_name, direction_id, pair, *_ in list(top_cv_edges) + list(
        top_time_edges
    ):
        group = (line_short_name, direction_id)
        group_pairs_for_group = restricted_group_pairs.setdefault(group, [])
        if pair not in group_pairs_for_group:
            group_pairs_for_group.append(pair)

    door_hourly_by_group, sw_hourly_by_group = (
        collect_pair_door_sw_samples_by_trip_group_hourly(
            STOP_TIMES_FILE, trip_id_to_group, restricted_group_pairs
        )
    )

    _print_section_header("Hour-of-day breakdown for top CV edges")
    print(
        "Hour-of-day total/door/sw breakdown for the top "
        f"{len(top_cv_edges)} highest-CV edges (CV >= {min_cv:.0%}):\n"
    )
    for index, (
        cv,
        line_short_name,
        direction_id,
        pair,
        (avg, count, std),
        _,
    ) in enumerate(top_cv_edges, start=1):
        printed_at[(line_short_name, direction_id, pair)] = index
        _print_edge_summary(
            index,
            line_short_name,
            direction_id,
            pair,
            avg,
            count,
            std,
            avg_door_by_group,
            avg_sw_by_group,
            stop_names,
            f" cv={cv:.2%}",
        )
        _print_hour_table(
            line_short_name,
            direction_id,
            pair,
            door_hourly_by_group,
            sw_hourly_by_group,
        )

    _print_section_header("Hour-of-day breakdown for top hourly-range edges")
    print(
        "Hour-of-day total/door/sw breakdown for the top "
        f"{len(top_time_edges)} highest hourly-range edges "
        f"(hourly range >= {min_hourly_range_pct:.0%}):\n"
    )
    for index, (
        hourly_range_pct,
        line_short_name,
        direction_id,
        pair,
        (avg, count, std),
        hourly_range,
        min_hours,
        min_mean,
        max_hours,
        max_mean,
    ) in enumerate(top_time_edges, start=1):
        key = (line_short_name, direction_id, pair)
        min_hours_str = ", ".join(f"{hour:02d}:00" for hour in min_hours)
        max_hours_str = ", ".join(f"{hour:02d}:00" for hour in max_hours)
        extra_lines = [
            f"     min hourly mean  {min_hours_str}  "
            f"{seconds_to_hms(min_mean):>8} ({min_mean:.2f}s)",
            f"     max hourly mean  {max_hours_str}  "
            f"{seconds_to_hms(max_mean):>8} ({max_mean:.2f}s)",
        ]
        _print_edge_summary(
            index,
            line_short_name,
            direction_id,
            pair,
            avg,
            count,
            std,
            avg_door_by_group,
            avg_sw_by_group,
            stop_names,
            f" hourly_range={hourly_range:.2f}s ({hourly_range_pct:.2%})",
            extra_lines,
        )
        if key in printed_at:
            print(
                f"     (hour-by-hour breakdown already shown above as CV "
                f"breakdown #{printed_at[key]})"
            )
            continue
        _print_hour_table(
            line_short_name,
            direction_id,
            pair,
            door_hourly_by_group,
            sw_hourly_by_group,
        )


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
    have to scan every edge listing to find the conclusion. Each flagged
    edge is annotated with *which* test flagged it (CV, hourly range, or
    both), since a CV failure and an hourly-range failure call for different
    fixes (see the printed explanation) and aren't interchangeable just
    because both ended up in the same list. Door/sw dominance is left to the
    CV ranking above, where it's printed alongside the actual numbers.

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
    unstable_cv = sum(1 for cv, *_ in ranked_cv if cv_bucket(cv) == "unstable")
    acceptable_cv = total_cv_edges - stable_cv - unstable_cv

    total_hourly_edges = len(ranked_hourly_range)
    time_dependent = sum(
        1
        for pct, *_ in ranked_hourly_range
        if hourly_range_bucket(pct) == "time-dependent routing would help"
    )
    static_ok = total_hourly_edges - time_dependent

    cv_by_key: Dict[Tuple[str, int, Tuple[str, str]], float] = {
        (line, direction, pair): cv for cv, line, direction, pair, *_ in ranked_cv
    }
    hourly_by_key: Dict[Tuple[str, int, Tuple[str, str]], float] = {
        (line, direction, pair): pct
        for pct, line, direction, pair, *_ in ranked_hourly_range
    }

    flagged_keys = {key for key, cv in cv_by_key.items() if cv >= min_cv} | {
        key for key, pct in hourly_by_key.items() if pct >= min_hourly_range_pct
    }
    flagged_edges = sorted(
        flagged_keys,
        key=lambda key: (
            _LINE_ORDER.get(key[0], len(_LINE_ORDER)),
            key[1],
            key[2],
        ),
    )
    passing_edges = total_cv_edges - len(flagged_edges)

    _print_section_header("Summary")
    print(f"{total_cv_edges} sw edges analyzed.\n")
    print(
        f"Stability (CV): {stable_cv} stable/extremely stable "
        f"({_format_pct(stable_cv, total_cv_edges)}), {acceptable_cv} "
        f"acceptable ({_format_pct(acceptable_cv, total_cv_edges)}), "
        f"{unstable_cv} unstable "
        f"({_format_pct(unstable_cv, total_cv_edges)})."
    )
    print(
        f"Time-of-day: {static_ok} edges have a static weight that's fine "
        f"({_format_pct(static_ok, total_hourly_edges)}), {time_dependent} "
        "would benefit from time-dependent routing "
        f"({_format_pct(time_dependent, total_hourly_edges)})."
    )
    print(
        f"\nVerdict: mean(total) is a trustworthy static weight for "
        f"{passing_edges} of {total_cv_edges} edges "
        f"({_format_pct(passing_edges, total_cv_edges)}). The remaining "
        f"{len(flagged_edges)} ({_format_pct(len(flagged_edges), total_cv_edges)}) "
        "need revisiting, and not necessarily with the same fix. See which "
        "test flagged each one below."
    )

    if not flagged_edges:
        return

    print(
        f"\nEdges needing attention ({len(flagged_edges)}, high CV or high hourly range):"
    )
    for line_short_name, direction_id, (a, b) in flagged_edges:
        key = (line_short_name, direction_id, (a, b))
        label_a, label_b = _stop_labels(stop_names, a, b)

        reasons: List[str] = []
        cv = cv_by_key.get(key)
        if cv is not None and cv >= min_cv:
            reasons.append(f"CV={cv:.2%}")
        hourly_pct = hourly_by_key.get(key)
        if hourly_pct is not None and hourly_pct >= min_hourly_range_pct:
            reasons.append(f"hourly range={hourly_pct:.2%}")

        reasons_str = f"  [{', '.join(reasons)}]" if reasons else ""
        print(
            f"  - {line_short_name} dir{direction_id}  {a} ({label_a}) -> "
            f"{b} ({label_b}){reasons_str}"
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
    """Rank sw edges by CV and hourly range."""
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
    ranked_cv: List[RankedCV] = []
    ranked_hourly_range: List[RankedHourlyRange] = []
    relevant_stop_ids: Set[str] = set()
    stop_names: Dict[str, str] = {}

    _print_section_header("Objective")
    print(_OBJECTIVE_EXPLANATION)
    print(_INDEPENDENCE_EXPLANATION)

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

    ranked_cv = rank_edges_by_cv(group_pairs, avg_by_group, samples_by_group)

    door_hourly_by_group, sw_hourly_by_group = (
        collect_pair_door_sw_samples_by_trip_group_hourly(
            STOP_TIMES_FILE, trip_id_to_group, group_pairs
        )
    )
    ranked_hourly_range = rank_edges_by_hourly_range(
        group_pairs, avg_by_group, door_hourly_by_group, sw_hourly_by_group
    )

    print(f"Number of edges with at least one sample: {len(ranked_cv)}\n")
    print_cv_ranking(
        ranked_cv, avg_door_by_group, avg_sw_by_group, stop_names, MIN_CV_TO_PRINT
    )
    print_hourly_range_ranking(
        ranked_hourly_range, stop_names, MIN_HOURLY_RANGE_PCT_TO_PRINT
    )
    print_hourly_breakdown(
        ranked_cv,
        ranked_hourly_range,
        avg_door_by_group,
        avg_sw_by_group,
        stop_names,
        TOP_K_HOURLY_CV,
        TOP_K_HOURLY_TIME,
        MIN_CV_TO_PRINT,
        MIN_HOURLY_RANGE_PCT_TO_PRINT,
    )
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
