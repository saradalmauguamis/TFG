"""Check whether door time should be imputed per hour instead of flat.

`checks/stop_times/3_door_times_check.py` writes `doors.txt`: for every
(line, stop_id) with at least one `arrival_time == departure_time`
occurrence, it imputes a door time, two different ways:

  - "Partial" stops (some trips equal, some differ) use a single flat mean
    over every trip *at that stop* where the times differ, regardless of
    what hour that trip ran.
  - "Canonical" terminals (every trip at that stop has arrival == departure)
    have zero real samples of their own, so they borrow a single flat mean
    pooled from every *other* stop's real door times on the same line (the
    FM line, which has no real samples on any of its own stops, borrows the
    pool from every other line instead).

`edge_weight_validation.py` showed that for `sw` edges, a flat mean
sometimes hides a real rush/off-peak pattern. This script asks the same
question for door time, for both imputation paths above: does bucketing the
*real* door-time samples by hour reveal a genuine, well-supported
time-of-day pattern, or would it just trade a stable flat mean for a
handful of noisy per-hour means?

For partial stops, the per-hour samples are the real samples at that exact
stop. For the canonical-terminal/FM donor pool, the per-hour samples are
pooled across every other stop that has real samples (on the same line, or
across all non-FM lines for the FM fallback) - the same pool
`write_doors_file` already draws its flat mean from, just split by hour
instead of merged into one number.

An hour only counts as "qualifying" once it has at least
`MIN_SAMPLES_PER_HOUR` real samples - the same discipline
`edge_weight_validation.py` applies before trusting an hourly mean. A
stop/line with fewer than two qualifying hours can't be hour-bucketed at all
(most hours would just fall back to the flat mean anyway), regardless of
whether a real pattern exists. Among stops/lines that *do* have enough
hourly data, the hourly range (max hourly mean - min hourly mean, normalized
by the flat mean) tells apart a real time-of-day shift from noise, exactly
as it does for `sw` edges.
"""

from __future__ import annotations

import sys
from collections import defaultdict
from contextlib import redirect_stdout
from pathlib import Path
from statistics import mean, stdev
from typing import DefaultDict, Dict, IO, List, Optional, Sequence, Set, Tuple

_PROJECT_ROOT = str(Path(__file__).resolve().parents[2])
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from data_validation.gtfs_utils import (  # noqa: E402
    SECONDS_PER_DAY,
    STOP_TIMES_SEQUENCE_FILE,
    STOPS_SUBWAY_FILE,
    TRIPS_FILE,
    check_missing_files,
    load_stop_names,
    load_trip_to_line,
    parse_time_to_seconds,
    print_file_disclaimer,
    read_dict_rows,
    seconds_to_hms,
)
from scripts.basics import (  # noqa: E402
    subway_routes_names_ids,
)

REPORT_FILE = Path(__file__).resolve().parent / "door_time_hourly_validation_report.txt"

GroupKey = Tuple[str, str]  # (line, stop_id)
DailyRecord = Tuple[float, int, float]  # (mean, count, stdev)
# (hourly_range_pct, line, stop_id, DailyRecord, hourly_range, min_hours,
# min_mean, max_hours, max_mean, qualifying_hour_count). min_hours/max_hours
# list every hour tied for the minimum/maximum hourly mean, same convention
# as edge_weight_validation.py, since ties are common with low samples/hour.
RankedStop = Tuple[
    float, str, str, DailyRecord, float, List[int], float, List[int], float, int
]
# Same shape as RankedStop, minus stop_id: one entry per donor pool a
# canonical terminal (or the FM line) would draw its flat mean from.
# (hourly_range_pct, pool_label, DailyRecord, hourly_range, min_hours,
# min_mean, max_hours, max_mean, qualifying_hour_count).
RankedPool = Tuple[
    float, str, DailyRecord, float, List[int], float, List[int], float, int
]

FM_FALLBACK_LABEL = "FM fallback (pooled non-FM lines)"

# An hour only counts toward the hourly-range comparison once it has this
# many real samples; below that, its per-hour mean is too noisy to trust at
# all and would just fall back to the flat mean in practice anyway.
MIN_SAMPLES_PER_HOUR = 5

# Hourly-range (range / mean) bucket boundary, same value and reasoning as
# edge_weight_validation.py's HOURLY_RANGE_REASONABLE_MAX, so the two
# analyses stay comparable.
HOURLY_RANGE_REASONABLE_MAX = 0.15

SECTION_BANNER_WIDTH = 70


def _print_section_header(title: str) -> None:
    """Print a section title inside a banner, to visually separate report sections.

    args:
            title: Section title, printed upper-case between two divider lines.
    """
    divider = "=" * SECTION_BANNER_WIDTH
    print(f"\n{divider}")
    print(title.upper())
    print(f"{divider}\n")


def _format_pct(count: int, total: int) -> str:
    """Format count as a percentage of total, guarding division by zero.

    args:
            count: Numerator, e.g. stops in one bucket.
            total: Denominator, e.g. total stops.

    returns:
            Percentage string, e.g. "12.3%", or "0.0%" when total is zero.
    """
    return f"{count / total:.1%}" if total else "0.0%"


def collect_door_time_data(
    stop_times_file: str, trips_file: str, rid_to_name: Dict[str, str]
) -> Tuple[Dict[GroupKey, Tuple[int, int]], Dict[GroupKey, Dict[int, List[int]]]]:
    """Build per-(line, stop_id) equal/total counts and hourly door samples.

    Mirrors `3_door_times_check.py`'s `build_arr_dep_counts`, but buckets the
    real door-time samples (from trips where arrival != departure) by the
    arrival hour at that stop, instead of keeping one flat list.

    args:
            stop_times_file: Path to the stop_times file to scan.
            trips_file: Path to the trips file used to resolve trip_id -> line.
            rid_to_name: Mapping from route_id to line name.

    returns:
            Tuple of (counts, door_samples_by_hour). `counts` maps
            (line, stop_id) to (equal_count, total_count). `door_samples_by_hour`
            maps (line, stop_id) to {hour: door_time samples}, hour in [0, 23].
    """
    trip_to_line = load_trip_to_line(trips_file, rid_to_name)
    counts: DefaultDict[GroupKey, List[int]] = defaultdict(lambda: [0, 0])
    door_samples_by_hour: DefaultDict[GroupKey, DefaultDict[int, List[int]]] = (
        defaultdict(lambda: defaultdict(list))
    )
    final_counts: Dict[GroupKey, Tuple[int, int]] = {}
    final_hourly: Dict[GroupKey, Dict[int, List[int]]] = {}

    for row in read_dict_rows(stop_times_file):
        trip_id = row.get("trip_id", "").strip()
        line = trip_to_line.get(trip_id)
        if not line:
            continue
        stop_id = row.get("stop_id", "").strip()
        if not stop_id:
            continue
        arrival = row.get("arrival_time", "").strip()
        departure = row.get("departure_time", "").strip()
        if not arrival or not departure:
            continue

        key = (line, stop_id)
        counts[key][1] += 1
        if arrival == departure:
            counts[key][0] += 1
            continue

        try:
            arrival_seconds = parse_time_to_seconds(arrival)
            door_time = parse_time_to_seconds(departure) - arrival_seconds
        except Exception:
            continue
        if door_time < 0:
            continue

        hour = (arrival_seconds % SECONDS_PER_DAY) // 3600
        door_samples_by_hour[key][hour].append(door_time)

    final_counts = {key: (vals[0], vals[1]) for key, vals in counts.items()}
    final_hourly = {key: dict(hours) for key, hours in door_samples_by_hour.items()}
    return final_counts, final_hourly


def _hourly_range_from_samples(
    hourly_samples: Dict[int, List[int]], min_samples_per_hour: int
) -> Optional[Tuple[DailyRecord, float, List[int], float, List[int], float, int]]:
    """Compute the daily/hourly stats shared by the stop and pool rankings.

    args:
            hourly_samples: Real samples bucketed by hour for one stop or pool.
            min_samples_per_hour: Minimum samples an hour needs to count as
                    "qualifying" rather than too noisy to trust.

    returns:
            None if there are no samples, a non-positive mean, or fewer than
            2 qualifying hours (hourly bucketing isn't feasible). Otherwise
            (DailyRecord, hourly_range, min_hours, min_mean, max_hours,
            max_mean, qualifying_hour_count).
    """
    all_samples: List[int] = []
    daily_mean = 0.0
    daily_count = 0
    daily_std = 0.0
    qualifying_hourly_means: Dict[int, float] = {}
    min_mean = 0.0
    max_mean = 0.0
    min_hours: List[int] = []
    max_hours: List[int] = []
    hourly_range = 0.0

    all_samples = [sample for samples in hourly_samples.values() for sample in samples]
    if not all_samples:
        return None

    daily_mean = mean(all_samples)
    daily_count = len(all_samples)
    daily_std = stdev(all_samples) if daily_count > 1 else 0.0
    if daily_mean <= 0:
        return None

    qualifying_hourly_means = {
        hour: mean(samples)
        for hour, samples in hourly_samples.items()
        if len(samples) >= min_samples_per_hour
    }
    if len(qualifying_hourly_means) < 2:
        return None

    min_mean = min(qualifying_hourly_means.values())
    max_mean = max(qualifying_hourly_means.values())
    min_hours = sorted(h for h, m in qualifying_hourly_means.items() if m == min_mean)
    max_hours = sorted(h for h, m in qualifying_hourly_means.items() if m == max_mean)
    hourly_range = max_mean - min_mean

    return (
        (daily_mean, daily_count, daily_std),
        hourly_range,
        min_hours,
        min_mean,
        max_hours,
        max_mean,
        len(qualifying_hourly_means),
    )


def rank_partial_stops_by_hourly_range(
    counts: Dict[GroupKey, Tuple[int, int]],
    door_samples_by_hour: Dict[GroupKey, Dict[int, List[int]]],
    min_samples_per_hour: int,
) -> Tuple[List[RankedStop], int]:
    """Classify partial stops by whether hourly bucketing is even feasible.

    A "partial" stop has `0 < equal_count < total_count`: some trips have
    real door-time samples, so there is something to bucket by hour, unlike
    canonical terminals.

    args:
            counts: Mapping from build (line, stop_id) -> (equal_count, total_count).
            door_samples_by_hour: Real door-time samples bucketed by hour.
            min_samples_per_hour: Minimum samples an hour needs to count as
                    "qualifying" rather than too noisy to trust.

    returns:
            Tuple of (ranked stops with >= 2 qualifying hours, sorted by
            descending hourly range percentage; count of partial stops with
            fewer than 2 qualifying hours, for which hourly bucketing isn't
            feasible regardless of whether a real pattern exists).
    """
    ranked: List[RankedStop] = []
    infeasible_count = 0

    for key, (equal_count, total_count) in counts.items():
        if not (0 < equal_count < total_count):
            continue
        stats = _hourly_range_from_samples(
            door_samples_by_hour.get(key, {}), min_samples_per_hour
        )
        if stats is None:
            infeasible_count += 1
            continue

        (
            daily_record,
            hourly_range,
            min_hours,
            min_mean,
            max_hours,
            max_mean,
            n_hours,
        ) = stats
        hourly_range_pct = hourly_range / daily_record[0]

        line, stop_id = key
        ranked.append(
            (
                hourly_range_pct,
                line,
                stop_id,
                daily_record,
                hourly_range,
                min_hours,
                min_mean,
                max_hours,
                max_mean,
                n_hours,
            )
        )

    ranked.sort(key=lambda item: (-item[0], item[1], item[2]))
    return ranked, infeasible_count


def pool_door_samples_by_line(
    door_samples_by_hour: Dict[GroupKey, Dict[int, List[int]]],
) -> Dict[str, Dict[int, List[int]]]:
    """Pool every stop's real hourly door samples into one bucket per line.

    This is the same pool `write_doors_file` draws its flat per-line mean
    from (every real sample on the line, regardless of which stop or
    whether that stop is partial or canonical), just kept split by hour.

    args:
            door_samples_by_hour: Real door-time samples bucketed by hour,
                    keyed by (line, stop_id).

    returns:
            Mapping from line to its pooled {hour: samples}.
    """
    pooled: DefaultDict[str, DefaultDict[int, List[int]]] = defaultdict(
        lambda: defaultdict(list)
    )
    for (line, _), hourly in door_samples_by_hour.items():
        for hour, samples in hourly.items():
            pooled[line][hour].extend(samples)
    return {line: dict(hourly) for line, hourly in pooled.items()}


def rank_pools_by_hourly_range(
    pooled_by_line: Dict[str, Dict[int, List[int]]], min_samples_per_hour: int
) -> Tuple[List[RankedPool], int]:
    """Classify each canonical-terminal/FM donor pool by hourly feasibility.

    One pool per line (every other stop's real samples on that line), plus
    one extra pool for the FM fallback (every real sample on every non-FM
    line, the same pool `write_doors_file` uses for FM's canonical
    terminals, which have no real samples on any FM stop).

    args:
            pooled_by_line: Real door-time samples pooled per line, bucketed
                    by hour, from `pool_door_samples_by_line`.
            min_samples_per_hour: Minimum samples an hour needs to count as
                    "qualifying" rather than too noisy to trust.

    returns:
            Tuple of (ranked pools with >= 2 qualifying hours, sorted by
            descending hourly range percentage; count of pools with fewer
            than 2 qualifying hours).
    """
    ranked: List[RankedPool] = []
    infeasible_count = 0
    pools: Dict[str, Dict[int, List[int]]] = {}

    fm_fallback_pool: DefaultDict[int, List[int]] = defaultdict(list)
    for line, hourly in pooled_by_line.items():
        if line == "FM":
            continue
        for hour, samples in hourly.items():
            fm_fallback_pool[hour].extend(samples)

    pools = dict(pooled_by_line)
    pools[FM_FALLBACK_LABEL] = dict(fm_fallback_pool)

    for label, hourly in pools.items():
        stats = _hourly_range_from_samples(hourly, min_samples_per_hour)
        if stats is None:
            infeasible_count += 1
            continue

        (
            daily_record,
            hourly_range,
            min_hours,
            min_mean,
            max_hours,
            max_mean,
            n_hours,
        ) = stats
        hourly_range_pct = hourly_range / daily_record[0]
        ranked.append(
            (
                hourly_range_pct,
                label,
                daily_record,
                hourly_range,
                min_hours,
                min_mean,
                max_hours,
                max_mean,
                n_hours,
            )
        )

    ranked.sort(key=lambda item: (-item[0], item[1]))
    return ranked, infeasible_count


def print_feasibility_summary(
    total_partial_stops: int,
    infeasible_count: int,
    ranked: Sequence[RankedStop],
    min_hourly_range_pct: float,
) -> None:
    """Print how many partial stops could even be hour-bucketed, and how many would benefit.

    args:
            total_partial_stops: Number of (line, stop_id) keys with
                    `0 < equal_count < total_count`.
            infeasible_count: Partial stops with fewer than 2 qualifying hours
                    (hourly bucketing isn't possible regardless of any real pattern).
            ranked: Feasible stops (>= 2 qualifying hours), sorted by descending
                    hourly range percentage.
            min_hourly_range_pct: Hourly range percentage a stop must reach for
                    hourly bucketing to plausibly be worth it over a flat mean.
    """
    feasible_count = len(ranked)
    would_help = sum(1 for item in ranked if item[0] >= min_hourly_range_pct)
    negligible = feasible_count - would_help

    _print_section_header("Feasibility summary")
    print(f"{total_partial_stops} partial stops analyzed.\n")
    print(
        f"Not enough hourly data to bucket at all: {infeasible_count} "
        f"({_format_pct(infeasible_count, total_partial_stops)}) - fewer than "
        f"2 hours with >= {MIN_SAMPLES_PER_HOUR} real samples, so most/all "
        "hours would fall back to the flat mean anyway."
    )
    print(
        f"Enough hourly data, but flat mean is already fine: {negligible} "
        f"({_format_pct(negligible, total_partial_stops)}) - hourly range < "
        f"{min_hourly_range_pct:.0%} of the flat mean, i.e. bucketing by hour "
        "would mostly trade real signal for sampling noise."
    )
    print(
        f"Enough hourly data AND a real time-of-day shift: {would_help} "
        f"({_format_pct(would_help, total_partial_stops)}) - these are the "
        "only stops where hour-bucketed door time would plausibly improve on "
        "the current flat mean.\n"
    )
    print(
        f"Verdict: out of {total_partial_stops} partial stops, hourly door-time "
        f"imputation would help {would_help} "
        f"({_format_pct(would_help, total_partial_stops)}); the rest would gain "
        "nothing or trade stability for noise."
    )


def print_ranked_stops(
    ranked: Sequence[RankedStop],
    stop_names: Dict[str, str],
    min_hourly_range_pct: float,
) -> None:
    """Print partial stops ranked by descending hourly range percentage.

    args:
            ranked: Feasible stops (>= 2 qualifying hours), sorted by descending
                    hourly range percentage.
            stop_names: Mapping from stop_id to stop_name.
            min_hourly_range_pct: Only print stops whose hourly range percentage
                    is at least this fraction.
    """
    above_threshold = [item for item in ranked if item[0] >= min_hourly_range_pct]

    _print_section_header("Partial stops ranked by hourly range")
    print(
        "Hourly range = max(qualifying hourly mean) - min(qualifying hourly "
        f"mean), normalized by the flat daily mean (range >= "
        f"{min_hourly_range_pct:.0%}): {len(above_threshold)} of {len(ranked)} "
        f"feasible stops ({_format_pct(len(above_threshold), len(ranked))})\n"
    )
    if not above_threshold:
        return

    for index, (
        hourly_range_pct,
        line,
        stop_id,
        (daily_mean, daily_count, daily_std),
        hourly_range,
        min_hours,
        min_mean,
        max_hours,
        max_mean,
        qualifying_hours,
    ) in enumerate(above_threshold, start=1):
        label = f"{stop_names.get(stop_id, stop_id)}"
        min_hours_str = ", ".join(f"{hour:02d}:00" for hour in min_hours)
        max_hours_str = ", ".join(f"{hour:02d}:00" for hour in max_hours)
        print(
            f"{index}. {line}  {stop_id} ({label})  "
            f"[range={hourly_range:.2f}s, {hourly_range_pct:.2%}, "
            f"{qualifying_hours} qualifying hours]"
        )
        print(
            f"     flat mean        {seconds_to_hms(daily_mean):>8} "
            f"({daily_mean:.2f}s) cnt={daily_count} stdev={daily_std:.2f}s"
        )
        print(
            f"     min hourly mean  {min_hours_str}  "
            f"{seconds_to_hms(min_mean):>8} ({min_mean:.2f}s)"
        )
        print(
            f"     max hourly mean  {max_hours_str}  "
            f"{seconds_to_hms(max_mean):>8} ({max_mean:.2f}s)\n"
        )


def print_pool_feasibility_summary(
    total_pools: int,
    infeasible_count: int,
    ranked: Sequence[RankedPool],
    min_hourly_range_pct: float,
) -> None:
    """Print how many canonical-terminal/FM donor pools could be hour-bucketed.

    args:
            total_pools: Number of donor pools analyzed (one per line, plus
                    the FM fallback pool).
            infeasible_count: Pools with fewer than 2 qualifying hours
                    (hourly bucketing isn't possible regardless of any real pattern).
            ranked: Feasible pools (>= 2 qualifying hours), sorted by
                    descending hourly range percentage.
            min_hourly_range_pct: Hourly range percentage a pool must reach
                    for hourly bucketing to plausibly be worth it over a flat
                    mean.
    """
    feasible_count = len(ranked)
    would_help = sum(1 for item in ranked if item[0] >= min_hourly_range_pct)
    negligible = feasible_count - would_help

    _print_section_header("Canonical terminal / FM donor pool feasibility")
    print(
        f"{total_pools} donor pools analyzed (one per line that has real "
        f"door-time samples, plus '{FM_FALLBACK_LABEL}'). A canonical "
        "terminal's imputed door time is currently `round_half_up_mean` of "
        "its line's pool (or the FM fallback pool, for FM); this checks "
        "whether splitting that same pool by hour would change anything.\n"
    )
    print(
        f"Not enough hourly data to bucket at all: {infeasible_count} "
        f"({_format_pct(infeasible_count, total_pools)}) - fewer than 2 "
        f"hours with >= {MIN_SAMPLES_PER_HOUR} real samples."
    )
    print(
        f"Enough hourly data, but flat mean is already fine: {negligible} "
        f"({_format_pct(negligible, total_pools)}) - hourly range < "
        f"{min_hourly_range_pct:.0%} of the flat mean."
    )
    print(
        f"Enough hourly data AND a real time-of-day shift: {would_help} "
        f"({_format_pct(would_help, total_pools)}) - these are the only "
        "pools where hour-bucketing a canonical terminal's donor mean would "
        "plausibly improve on the current flat mean.\n"
    )
    print(
        f"Verdict: out of {total_pools} donor pools, hourly imputation for "
        f"canonical terminals (and FM) would help {would_help} "
        f"({_format_pct(would_help, total_pools)}); the rest would gain "
        "nothing or trade stability for noise."
    )


def print_ranked_pools(
    ranked: Sequence[RankedPool], min_hourly_range_pct: float
) -> None:
    """Print donor pools ranked by descending hourly range percentage.

    args:
            ranked: Feasible pools (>= 2 qualifying hours), sorted by
                    descending hourly range percentage.
            min_hourly_range_pct: Only print pools whose hourly range
                    percentage is at least this fraction.
    """
    above_threshold = [item for item in ranked if item[0] >= min_hourly_range_pct]

    _print_section_header("Donor pools ranked by hourly range")
    print(
        "Hourly range = max(qualifying hourly mean) - min(qualifying hourly "
        f"mean), normalized by the flat pool mean (range >= "
        f"{min_hourly_range_pct:.0%}): {len(above_threshold)} of {len(ranked)} "
        f"feasible pools ({_format_pct(len(above_threshold), len(ranked))})\n"
    )
    if not above_threshold:
        return

    for index, (
        hourly_range_pct,
        label,
        (daily_mean, daily_count, daily_std),
        hourly_range,
        min_hours,
        min_mean,
        max_hours,
        max_mean,
        qualifying_hours,
    ) in enumerate(above_threshold, start=1):
        min_hours_str = ", ".join(f"{hour:02d}:00" for hour in min_hours)
        max_hours_str = ", ".join(f"{hour:02d}:00" for hour in max_hours)
        print(
            f"{index}. {label}  "
            f"[range={hourly_range:.2f}s, {hourly_range_pct:.2%}, "
            f"{qualifying_hours} qualifying hours]"
        )
        print(
            f"     flat mean        {seconds_to_hms(daily_mean):>8} "
            f"({daily_mean:.2f}s) cnt={daily_count} stdev={daily_std:.2f}s"
        )
        print(
            f"     min hourly mean  {min_hours_str}  "
            f"{seconds_to_hms(min_mean):>8} ({min_mean:.2f}s)"
        )
        print(
            f"     max hourly mean  {max_hours_str}  "
            f"{seconds_to_hms(max_mean):>8} ({max_mean:.2f}s)\n"
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
    """Check whether hour-bucketed door time would beat the flat mean, for both imputation paths."""
    rid_to_name: Dict[str, str] = {}
    counts: Dict[GroupKey, Tuple[int, int]] = {}
    door_samples_by_hour: Dict[GroupKey, Dict[int, List[int]]] = {}
    ranked: List[RankedStop] = []
    ranked_pools: List[RankedPool] = []
    infeasible_count = 0
    infeasible_pool_count = 0
    stop_names: Dict[str, str] = {}
    total_partial_stops = 0
    relevant_stop_ids: Set[str] = set()
    pooled_by_line: Dict[str, Dict[int, List[int]]] = {}
    total_pools = 0

    _print_section_header("Objective")
    print(
        "`doors.txt` imputes door time two ways: partial stops (some trips "
        "have arrival_time == departure_time, some don't) get a flat mean "
        "from every trip *at that stop* where the times differ; canonical "
        "terminals (every trip equal) have no real samples of their own, so "
        "they borrow a flat mean pooled from every other stop on the line "
        "(or, for FM, from every other line). Does bucketing the underlying "
        "real samples by hour reveal a genuine time-of-day pattern worth "
        "using instead of either flat mean, or is there just not enough "
        "data per hour to trust it?\n"
    )

    check_missing_files([STOP_TIMES_SEQUENCE_FILE, TRIPS_FILE, STOPS_SUBWAY_FILE])
    print_file_disclaimer(
        [
            (STOP_TIMES_SEQUENCE_FILE, "stop_times"),
            (TRIPS_FILE, "trips"),
            (STOPS_SUBWAY_FILE, "stops"),
        ]
    )

    rid_to_name = {rid: name for name, rid in subway_routes_names_ids.items()}
    counts, door_samples_by_hour = collect_door_time_data(
        STOP_TIMES_SEQUENCE_FILE, TRIPS_FILE, rid_to_name
    )

    total_partial_stops = sum(
        1
        for equal_count, total_count in counts.values()
        if 0 < equal_count < total_count
    )
    ranked, infeasible_count = rank_partial_stops_by_hourly_range(
        counts, door_samples_by_hour, MIN_SAMPLES_PER_HOUR
    )

    relevant_stop_ids = {stop_id for _, stop_id in counts}
    stop_names = load_stop_names(STOPS_SUBWAY_FILE, stop_ids=relevant_stop_ids)

    print_feasibility_summary(
        total_partial_stops, infeasible_count, ranked, HOURLY_RANGE_REASONABLE_MAX
    )
    print_ranked_stops(ranked, stop_names, HOURLY_RANGE_REASONABLE_MAX)

    pooled_by_line = pool_door_samples_by_line(door_samples_by_hour)
    ranked_pools, infeasible_pool_count = rank_pools_by_hourly_range(
        pooled_by_line, MIN_SAMPLES_PER_HOUR
    )
    total_pools = len(pooled_by_line) + 1  # +1 for the FM fallback pool.

    print_pool_feasibility_summary(
        total_pools, infeasible_pool_count, ranked_pools, HOURLY_RANGE_REASONABLE_MAX
    )
    print_ranked_pools(ranked_pools, HOURLY_RANGE_REASONABLE_MAX)


if __name__ == "__main__":
    with open(REPORT_FILE, "w", encoding="utf-8") as report_handle:
        with redirect_stdout(_Tee(sys.stdout, report_handle)):
            main()
    print(f"\nFull report written to {REPORT_FILE}")
