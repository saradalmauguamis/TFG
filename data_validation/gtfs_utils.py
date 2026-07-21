import os
import re
import sys
from collections import defaultdict
from pathlib import Path
from statistics import mean, stdev
from typing import (
    DefaultDict,
    Dict,
    Hashable,
    Iterable,
    List,
    Optional,
    Sequence,
    Set,
    Tuple,
)

# Ensure the project root is on sys.path so that shared scripts can be imported.
_PROJECT_ROOT = str(Path(__file__).resolve().parents[1])
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)


# -----------------------------
# Module setup
# -----------------------------

from scripts.utils import (  # noqa: E402
    read_dict_rows,
    read_header,
    round_half_up_mean,
    sniff_dialect,
    write_rows,
)


# -----------------------------
# Explicit re-exports
# -----------------------------

# Explicit re-exports for type checking and IDE support
__all__ = [
    # Shared CSV helpers
    "sniff_dialect",
    "read_dict_rows",
    "read_header",
    "round_half_up_mean",
    "write_rows",
    # Constants / paths
    "_DEFAULT_DATA_DIR",
    "BASE",
    "_DEFAULT_RAW_DATA_DIR",
    "RAW_BASE",
    "_DEFAULT_SUBWAY_DATA_DIR",
    "SUBWAY_BASE",
    "_DEFAULT_DUPLICATED_TRIPS_DATA_DIR",
    "DUPLICATED_TRIPS_BASE",
    "_DEFAULT_STOP_SEQUENCE_DATA_DIR",
    "STOP_SEQUENCE_BASE",
    "_DEFAULT_DOORS_DATA_DIR",
    "DOORS_BASE",
    "_DEFAULT_SHARED_PLATFORMS_DATA_DIR",
    "SHARED_PLATFORMS_BASE",
    "PATHWAYS_RAW_FILE",
    "PATHWAYS_FILE",
    "ROUTES_RAW_FILE",
    "ROUTES_FILE",
    "STOP_TIMES_RAW_FILE",
    "STOP_TIMES_SUBWAY_FILE",
    "STOP_TIMES_CLEANED_FILE",
    "STOP_TIMES_SEQUENCE_FILE",
    "STOP_TIMES_DOORS_FILE",
    "STOP_TIMES_FILE",
    "STOPS_RAW_FILE",
    "STOPS_SUBWAY_FILE",
    "STOPS_FILE",
    "TRANSFERS_RAW_FILE",
    "TRANSFERS_FILE",
    "TRIPS_RAW_FILE",
    "TRIPS_SUBWAY_FILE",
    "TRIPS_FILE",
    "TRIP_IDS_TO_ELIMINATE_FILE",
    "WRONG_STOP_SEQUENCES_FILE",
    "DOORS_FILE",
    "EQUIVALENCES_FILE",
    "_DEFAULT_WEIGHTS_DATA_DIR",
    "WEIGHTS_BASE",
    "SUBWAY_WEIGHTS_FILE",
    "WEIGHTS_FILE",
    "SECONDS_PER_DAY",
    # Regex / Patterns
    "PW_PAIR",
    # CSV / file helpers
    "check_missing_files",
    "print_file_disclaimer",
    # ID loaders
    "load_stop_ids",
    "load_stop_names",
    "load_pathway_ids",
    "load_route_ids",
    "load_trip_ids",
    "load_trip_ids_by_route",
    "load_from_stop_ids",
    "load_to_stop_ids",
    "load_nonempty_lines",
    # Time helpers
    "parse_time_to_seconds",
    "format_seconds",
    "seconds_to_hms",
    # Pathway / transfer helpers
    "iter_pathway_pairs",
    "load_transfer_pairs",
    "load_transfer_pairs_present",
    "load_stops_info",
    "load_platforms_by_name",
    "load_platform_pairs_present",
    # Platform graph helpers
    "build_platform_graph",
    "build_graph_and_coverage",
    "build_directed_entrance_edges",
    # Validation helpers
    "check_trip",
    "make_signature",
    "build_expected_adjacency",
    "load_trip_sequence_bounds",
    # Line / shared-platform helpers
    "load_trip_to_line",
    "build_stop_to_lines",
    "build_shared_platform_lines",
    "format_stop_label",
    "invert_entries",
    "label_entrance_by_platform",
    # Directed pair travel-time helpers
    "consecutive_pairs",
    "build_trip_groups_by_line",
    "collect_pair_samples_by_trip_group",
    "collect_pair_door_sw_samples_by_trip_group",
    "collect_pair_door_sw_samples_by_trip_group_hourly",
    "average_times_for_pairs",
    "build_stop_id_order_index",
    "load_transfer_weights",
]


# -----------------------------
# Constants / paths
# -----------------------------

_DEFAULT_DATA_DIR = Path(__file__).resolve().parents[1] / "data"
BASE = str(Path(os.environ.get("GTFS_DATA_DIR", str(_DEFAULT_DATA_DIR))).resolve())

_DEFAULT_RAW_DATA_DIR = _DEFAULT_DATA_DIR / "0_raw"
RAW_BASE = str(
    Path(os.environ.get("GTFS_RAW_DATA_DIR", str(_DEFAULT_RAW_DATA_DIR))).resolve()
)

_DEFAULT_SUBWAY_DATA_DIR = _DEFAULT_DATA_DIR / "1_subway"
SUBWAY_BASE = str(
    Path(
        os.environ.get("GTFS_SUBWAY_DATA_DIR", str(_DEFAULT_SUBWAY_DATA_DIR))
    ).resolve()
)

_DEFAULT_DUPLICATED_TRIPS_DATA_DIR = _DEFAULT_DATA_DIR / "2_duplicated_trips"
DUPLICATED_TRIPS_BASE = str(
    Path(
        os.environ.get(
            "GTFS_DUPLICATED_TRIPS_DATA_DIR", str(_DEFAULT_DUPLICATED_TRIPS_DATA_DIR)
        )
    ).resolve()
)

_DEFAULT_STOP_SEQUENCE_DATA_DIR = _DEFAULT_DATA_DIR / "3_stop_sequence"
STOP_SEQUENCE_BASE = str(
    Path(
        os.environ.get(
            "GTFS_STOP_SEQUENCE_DATA_DIR", str(_DEFAULT_STOP_SEQUENCE_DATA_DIR)
        )
    ).resolve()
)

_DEFAULT_DOORS_DATA_DIR = _DEFAULT_DATA_DIR / "4_doors_time"
DOORS_BASE = str(
    Path(os.environ.get("GTFS_DOORS_DATA_DIR", str(_DEFAULT_DOORS_DATA_DIR))).resolve()
)

_DEFAULT_SHARED_PLATFORMS_DATA_DIR = _DEFAULT_DATA_DIR / "5_shared_platforms"
SHARED_PLATFORMS_BASE = str(
    Path(
        os.environ.get(
            "GTFS_SHARED_PLATFORMS_DATA_DIR", str(_DEFAULT_SHARED_PLATFORMS_DATA_DIR)
        )
    ).resolve()
)

_DEFAULT_WEIGHTS_DATA_DIR = _DEFAULT_DATA_DIR / "6_weights"
WEIGHTS_BASE = str(
    Path(
        os.environ.get("GTFS_WEIGHTS_DATA_DIR", str(_DEFAULT_WEIGHTS_DATA_DIR))
    ).resolve()
)

PATHWAYS_RAW_FILE = os.path.join(RAW_BASE, "pathways.txt")
PATHWAYS_FILE = os.path.join(SHARED_PLATFORMS_BASE, "pathways_shared.txt")

ROUTES_RAW_FILE = os.path.join(RAW_BASE, "routes.txt")
ROUTES_FILE = os.path.join(SUBWAY_BASE, "routes_subway.txt")

STOP_TIMES_RAW_FILE = os.path.join(RAW_BASE, "stop_times.txt")
STOP_TIMES_SUBWAY_FILE = os.path.join(SUBWAY_BASE, "stop_times_subway.txt")
STOP_TIMES_CLEANED_FILE = os.path.join(DUPLICATED_TRIPS_BASE, "stop_times_cleaned.txt")
STOP_TIMES_SEQUENCE_FILE = os.path.join(STOP_SEQUENCE_BASE, "stop_times_sequence.txt")
STOP_TIMES_DOORS_FILE = os.path.join(DOORS_BASE, "stop_times_doors.txt")
STOP_TIMES_FILE = os.path.join(SHARED_PLATFORMS_BASE, "stop_times_shared.txt")

STOPS_RAW_FILE = os.path.join(RAW_BASE, "stops.txt")
STOPS_SUBWAY_FILE = os.path.join(SUBWAY_BASE, "stops_subway.txt")
STOPS_FILE = os.path.join(SHARED_PLATFORMS_BASE, "stops_shared.txt")

TRANSFERS_RAW_FILE = os.path.join(RAW_BASE, "transfers.txt")
TRANSFERS_FILE = os.path.join(SHARED_PLATFORMS_BASE, "transfers_shared.txt")

TRIPS_RAW_FILE = os.path.join(RAW_BASE, "trips.txt")
TRIPS_SUBWAY_FILE = os.path.join(SUBWAY_BASE, "trips_subway.txt")
TRIPS_FILE = os.path.join(DUPLICATED_TRIPS_BASE, "trips_cleaned.txt")

TRIP_IDS_TO_ELIMINATE_FILE = os.path.join(
    DUPLICATED_TRIPS_BASE, "trip_ids_to_eliminate.txt"
)
WRONG_STOP_SEQUENCES_FILE = os.path.join(STOP_SEQUENCE_BASE, "wrong_stop_sequences.txt")
DOORS_FILE = os.path.join(DOORS_BASE, "doors.txt")
EQUIVALENCES_FILE = os.path.join(SHARED_PLATFORMS_BASE, "equivalences.txt")

SUBWAY_WEIGHTS_FILE = os.path.join(WEIGHTS_BASE, "subway_weights.txt")
WEIGHTS_FILE = os.path.join(WEIGHTS_BASE, "weights.txt")


SECONDS_PER_DAY = 24 * 60 * 60


# -----------------------------
# Regex / Patterns
# -----------------------------
PW_PAIR = re.compile(r"^PW\.(?P<a>[^_]+)_(?P<b>[^\s]+)$")


# -----------------------------
# CSV / file helpers
# -----------------------------
def print_file_disclaimer(
    paths: List[str | Path | Tuple[str | Path, str]],
) -> None:
    """Print the disclaimer header and the name/parent of each path.

    Each entry can be a plain path or a (path, label) tuple. When a label is
    given the line reads " - filename as 'label' from parent".

    args:
        paths: Sequence of paths or (path, label) tuples to include in the disclaimer.
    """
    print(
        "Disclaimer: for coherence we will consider the next file(s) from "
        f"{Path(BASE).relative_to(_PROJECT_ROOT)}:"
    )
    for entry in paths:
        if isinstance(entry, tuple):
            path, label = entry
            print(f" - {Path(path).name} as '{label}' from /{Path(path).parent.name}")
        else:
            print(f" - {Path(entry).name} from /{Path(entry).parent.name}")
    print("\n")


def check_missing_files(list_of_files: List[str]) -> None:
    """Verify that all files exist, raising an exception if any are missing.

    args:
        list_of_files: File paths that must exist.

    raises:
        FileNotFoundError: If any files in the list do not exist.
    """
    missing_files = [path for path in list_of_files if not os.path.exists(path)]
    if missing_files:
        print("The following files were not found:")
        for path in missing_files:
            print(" -", Path(path).relative_to(_PROJECT_ROOT))
        raise FileNotFoundError(f"Missing {len(missing_files)} required file(s).")


# -----------------------------
# ID loaders
# -----------------------------
def load_stop_ids(file_path: str) -> Set[str]:
    """Return the set of stop_id values from a file.

    args:
        file_path: Input GTFS file path.

    returns:
        Unique stop identifiers.
    """
    stop_ids: Set[str] = set()
    for row in read_dict_rows(file_path):
        stop_id = row.get("stop_id", "").strip()
        if stop_id:
            stop_ids.add(stop_id)
    return stop_ids


def load_stop_names(
    file_path: str, stop_ids: Optional[Set[str]] = None
) -> Dict[str, str]:
    """Return a mapping of stop_id to stop_name.

    args:
        file_path: Input stops file path.
        stop_ids: If provided, only return entries for these stop_id values.

    returns:
        Dictionary keyed by stop_id with stop_name values.
    """
    stop_names: Dict[str, str] = {}
    for row in read_dict_rows(file_path):
        stop_id = row.get("stop_id", "").strip()
        if not stop_id:
            continue
        if stop_ids is not None and stop_id not in stop_ids:
            continue
        stop_names[stop_id] = row.get("stop_name", "").strip()
    return stop_names


def load_pathway_ids(file_path: str) -> Set[str]:
    """Return the set of pathway_id values from a file.

    args:
        file_path: Input pathways file path.

    returns:
        Unique pathway identifiers.
    """
    pathway_ids: Set[str] = set()
    for row in read_dict_rows(file_path):
        pathway_id = row.get("pathway_id", "").strip()
        if pathway_id:
            pathway_ids.add(pathway_id)
    return pathway_ids


def load_route_ids(file_path: str) -> Set[str]:
    """Return the set of route_id values from a file.

    args:
        file_path: Input routes file path.

    returns:
        Unique route identifiers.
    """
    route_ids: Set[str] = set()
    for row in read_dict_rows(file_path):
        route_id = row.get("route_id", "").strip()
        if route_id:
            route_ids.add(route_id)
    return route_ids


def load_trip_ids(file_path: str) -> Set[str]:
    """Return the set of trip_id values from a file.

    args:
        file_path: Input trips file path.

    returns:
        Unique trip identifiers.
    """
    trip_ids: Set[str] = set()
    for row in read_dict_rows(file_path):
        trip_id = row.get("trip_id", "").strip()
        if trip_id:
            trip_ids.add(trip_id)
    return trip_ids


def load_trip_ids_by_route(file_path: str, route_id: str) -> Dict[int, Set[str]]:
    """Return all trip_ids for a route, grouped by direction_id.

    args:
        file_path: Input trips file path.
        route_id: Route identifier to filter trips.

    returns:
        Dictionary mapping direction_id values to sets of trip_ids.
    """
    trip_ids: Dict[int, Set[str]] = {0: set(), 1: set()}
    for row in read_dict_rows(file_path):
        if row.get("route_id") != route_id:
            continue
        trip_id = row.get("trip_id", "").strip()
        if not trip_id:
            continue
        direction_text = row.get("direction_id", "").strip()
        if not direction_text:
            continue
        try:
            direction_id = int(direction_text)
        except ValueError:
            continue
        if direction_id in trip_ids:
            trip_ids[direction_id].add(trip_id)
    return trip_ids


def load_from_stop_ids(file_path: str) -> Set[str]:
    """Return the set of from_stop_id values from a file.

    args:
        file_path: Input transfers file path.

    returns:
        Unique from_stop_id values.
    """
    stop_ids: Set[str] = set()
    for row in read_dict_rows(file_path):
        stop_id = row.get("from_stop_id", "").strip()
        if stop_id:
            stop_ids.add(stop_id)
    return stop_ids


def load_to_stop_ids(file_path: str) -> Set[str]:
    """Return the set of to_stop_id values from a file.

    args:
        file_path: Input transfers file path.

    returns:
        Unique to_stop_id values.
    """
    stop_ids: Set[str] = set()
    for row in read_dict_rows(file_path):
        stop_id = row.get("to_stop_id", "").strip()
        if stop_id:
            stop_ids.add(stop_id)
    return stop_ids


def load_nonempty_lines(file_path: str) -> Set[str]:
    """Return the set of non-empty stripped lines from a text file.

    args:
        file_path: Input plain-text file path.

    returns:
        Unique non-empty lines.
    """
    values: Set[str] = set()
    with open(file_path, "r", encoding="utf-8") as file_handle:
        for line in file_handle:
            value = line.strip()
            if value:
                values.add(value)
    return values


# -----------------------------
# Time helpers
# -----------------------------
def parse_time_to_seconds(value: str) -> int:
    """Convert a GTFS HH:MM:SS time string to seconds.

    Supports negative times (e.g. ``-00:00:21``) produced by the door-time
    pipeline for stops that depart before the reference midnight.

    args:
        value: Time text in ``[-]HH:MM:SS`` format.

    returns:
        Total seconds represented by the input time (negative if prefixed with ``-``).
    """
    stripped = value.strip()
    negative = stripped.startswith("-")
    unsigned = stripped[1:] if negative else stripped
    hours_text, minutes_text, seconds_text = unsigned.split(":")
    total = int(hours_text) * 3600 + int(minutes_text) * 60 + int(seconds_text)
    return -total if negative else total


def format_seconds(value: float) -> str:
    """Format a duration in seconds as HH:MM:SS with optional sign.

    args:
        value: Duration in seconds.

    returns:
        Formatted duration string.
    """
    sign = "-" if value < 0 else ""
    rounded = int(round(abs(value)))
    hours, remainder = divmod(rounded, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{sign}{hours:02d}:{minutes:02d}:{seconds:02d}"


def seconds_to_hms(value: float) -> str:
    """Format a duration in seconds as M:SS or H:MM:SS.

    args:
        value: Duration in seconds.

    returns:
        Formatted duration string.
    """
    rounded = int(round(value))
    hours, remainder = divmod(abs(rounded), 3600)
    minutes, seconds = divmod(remainder, 60)
    prefix = "-" if rounded < 0 else ""
    if hours:
        return f"{prefix}{hours:d}:{minutes:02d}:{seconds:02d}"
    return f"{prefix}{minutes:d}:{seconds:02d}"


# -----------------------------
# Pathway / transfer helpers
# -----------------------------
def iter_pathway_pairs(file_path: str) -> Iterable[Tuple[str, str, str]]:
    """Yield (pathway_id, a, b) for rows matching the pathway pattern PW.a_b.

    args:
        file_path: Input pathways file path.

    returns:
        Iterator of parsed pathway triples.
    """
    for row in read_dict_rows(file_path):
        pathway_id = row.get("pathway_id", "").strip()
        if not pathway_id:
            continue
        match = PW_PAIR.match(pathway_id)
        if not match:
            continue
        yield pathway_id, match.group("a"), match.group("b")


def load_transfer_pairs(file_path: str) -> Iterable[Tuple[str, str]]:
    """Yield (from_stop_id, to_stop_id) pairs from transfers.txt.

    args:
        file_path: Input transfers file path.

    returns:
        Iterator of transfer stop pairs.
    """
    for row in read_dict_rows(file_path):
        from_stop_id = row.get("from_stop_id", "").strip()
        to_stop_id = row.get("to_stop_id", "").strip()
        if from_stop_id or to_stop_id:
            yield from_stop_id, to_stop_id


def load_transfer_weights(file_path: str) -> Iterable[Tuple[str, str, int]]:
    """Yield (from_stop_id, to_stop_id, min_transfer_time) from transfers.txt.

    args:
        file_path: Input transfers file path.

    returns:
        Iterator of transfer stop pairs with their min_transfer_time, in
        seconds.
    """
    for row in read_dict_rows(file_path):
        from_stop_id = row.get("from_stop_id", "").strip()
        to_stop_id = row.get("to_stop_id", "").strip()
        min_transfer_time = row.get("min_transfer_time", "").strip()
        if from_stop_id and to_stop_id and min_transfer_time:
            yield from_stop_id, to_stop_id, int(min_transfer_time)


def load_stops_info(file_path: str) -> Dict[str, Tuple[str, str, str]]:
    """Return stop_id -> (stop_name, stop_lat, stop_lon).

    args:
        file_path: Input stops file path.

    returns:
        Mapping of stop_id to name and coordinates.
    """
    stops_info: Dict[str, Tuple[str, str, str]] = {}
    for row in read_dict_rows(file_path):
        stop_id = row.get("stop_id", "").strip()
        if not stop_id:
            continue
        stops_info[stop_id] = (
            row.get("stop_name", "").strip(),
            row.get("stop_lat", "").strip(),
            row.get("stop_lon", "").strip(),
        )
    return stops_info


def load_platforms_by_name(file_path: str) -> Dict[str, List[str]]:
    """Return stop_name -> sorted unique platform stop_id list for 1.* platforms.

    args:
        file_path: Input stops file path.

    returns:
        Mapping from stop_name to sorted platform stop IDs.
    """
    platforms_by_name: Dict[str, List[str]] = {}
    for row in read_dict_rows(file_path):
        stop_id = row.get("stop_id", "").strip()
        stop_name = row.get("stop_name", "").strip()
        if not stop_id:
            continue
        if stop_id.startswith("1."):
            platforms_by_name.setdefault(stop_name, []).append(stop_id)

    for stop_name in list(platforms_by_name.keys()):
        platforms_by_name[stop_name] = sorted(set(platforms_by_name[stop_name]))
    return platforms_by_name


def load_platform_pairs_present(file_path: str) -> Set[Tuple[str, str]]:
    """Return undirected platform pairs (1.*, 1.*) linked by a pathway.

    args:
        file_path: Input pathways file path.

    returns:
        Set of sorted platform-stop pairs.
    """
    pairs: Set[Tuple[str, str]] = set()
    for _, stop_a, stop_b in iter_pathway_pairs(file_path):
        if stop_a.startswith("1.") and stop_b.startswith("1."):
            first, second = sorted((stop_a, stop_b))
            pairs.add((first, second))
    return pairs


def load_transfer_pairs_present(file_path: str) -> Set[Tuple[str, str]]:
    """Return undirected platform pairs (1.*, 1.*) present in transfers.txt.

    args:
        file_path: Input transfers file path.

    returns:
        Set of sorted platform-stop pairs.
    """
    pairs: Set[Tuple[str, str]] = set()
    for stop_a, stop_b in load_transfer_pairs(file_path):
        if stop_a and stop_b:
            first, second = sorted((stop_a, stop_b))
            pairs.add((first, second))
    return pairs


# -----------------------------
# Platform graph helpers
# -----------------------------
def _add_platform_edge(
    platform_graph: Dict[str, Set[str]], stop_a: str, stop_b: str
) -> None:
    """Add an undirected edge between two platform stops.

    args:
        platform_graph: Adjacency map being populated.
        stop_a: First platform stop ID.
        stop_b: Second platform stop ID.
    """
    platform_graph.setdefault(stop_a, set()).add(stop_b)
    platform_graph.setdefault(stop_b, set()).add(stop_a)


def _add_entry(
    platform_to_entries: Dict[str, Set[str]],
    covered_platforms: Set[str],
    platform_stop: str,
    entrance_stop: str,
) -> None:
    """Record an entrance that connects to a platform stop.

    args:
        platform_to_entries: Mapping of platforms to connected entrances.
        covered_platforms: Set of platforms already covered by entrances.
        platform_stop: Platform stop ID.
        entrance_stop: Entrance stop ID.
    """
    platform_to_entries.setdefault(platform_stop, set()).add(entrance_stop)
    covered_platforms.add(platform_stop)


def build_platform_graph(platform_pairs: Set[Tuple[str, str]]) -> Dict[str, Set[str]]:
    """Build an undirected platform (1.*) adjacency map from canonical pairs.

    args:
        platform_pairs: Set of sorted (stop_a, stop_b) platform pairs, e.g. from
            `load_transfer_pairs_present` or `load_platform_pairs_present`.

    returns:
        Adjacency map of platform stop IDs to the set of directly connected
        platform stop IDs. Edges are undirected: when two platforms are
        connected both appear in each other's adjacency set.
    """
    platform_graph: Dict[str, Set[str]] = {}
    for stop_a, stop_b in platform_pairs:
        _add_platform_edge(platform_graph, stop_a, stop_b)
    return platform_graph


def build_graph_and_coverage(
    pathway_ids: Set[str],
) -> Tuple[Dict[str, Set[str]], Set[str]]:
    """Build platform-entrance coverage information from pathways.

    args:
        pathway_ids: Pathway IDs to parse and classify.

    returns:
        Tuple containing two elements:

        - `platform_to_entries` (Dict[str, Set[str]]): mapping from a platform stop ID
            to the set of entrance stop IDs (IDs starting with `E.`) that connect to that
            platform. Only platform<->entrance pathway edges are recorded here.

        - `covered_platforms` (Set[str]): set of platform stop IDs that have at least
            one connected entrance (i.e., the keys of `platform_to_entries`).
    """
    platform_to_entries: Dict[str, Set[str]] = {}
    covered_platforms: Set[str] = set()

    for pathway_id in pathway_ids:
        match = PW_PAIR.match(pathway_id)
        if not match:
            continue
        stop_a, stop_b = match.group("a"), match.group("b")

        if stop_a.startswith("1.") and stop_b.startswith("E."):
            _add_entry(platform_to_entries, covered_platforms, stop_a, stop_b)
        elif stop_b.startswith("1.") and stop_a.startswith("E."):
            _add_entry(platform_to_entries, covered_platforms, stop_b, stop_a)

    return platform_to_entries, covered_platforms


def invert_entries(entries_by_key: Dict[str, Set[str]]) -> Dict[str, Set[str]]:
    """Invert a one-to-many mapping, e.g. platform_to_entries -> entrance_to_platforms.

    args:
        entries_by_key: Mapping from a key to its set of associated values,
            e.g. `platform_to_entries` from `build_graph_and_coverage`.

    returns:
        Mapping from each value back to the set of keys it was found under.
    """
    inverted: Dict[str, Set[str]] = {}
    for key, values in entries_by_key.items():
        for value in values:
            inverted.setdefault(value, set()).add(key)
    return inverted


def build_directed_entrance_edges(
    pathway_ids: Set[str],
) -> Tuple[Dict[str, Set[str]], Dict[str, Set[str]]]:
    """Build directed platform<->entrance edges, keyed by platform stop_id.

    Keeps the two pathway directions separate so a caller can detect a
    one-way-only connection (e.g. `PW.E.xxx_1.yyy` present without its
    inverse `PW.1.yyy_E.xxx`).

    args:
        pathway_ids: Pathway IDs to parse and classify.

    returns:
        Tuple of (platform_to_entrance, entrance_to_platform), both mapping a
        platform stop_id to the set of entrance stop_ids reachable via a
        pathway row in that direction only.
    """
    platform_to_entrance: Dict[str, Set[str]] = {}
    entrance_to_platform: Dict[str, Set[str]] = {}

    for pathway_id in pathway_ids:
        match = PW_PAIR.match(pathway_id)
        if not match:
            continue
        stop_a, stop_b = match.group("a"), match.group("b")

        if stop_a.startswith("1.") and stop_b.startswith("E."):
            platform_to_entrance.setdefault(stop_a, set()).add(stop_b)
        elif stop_a.startswith("E.") and stop_b.startswith("1."):
            entrance_to_platform.setdefault(stop_b, set()).add(stop_a)

    return platform_to_entrance, entrance_to_platform


# -----------------------------
# Validation helpers
# -----------------------------
def check_trip(trip_id: str, seqs_sorted: List[int]) -> List[str]:
    """Check whether stop_sequence increases by one for a trip.

    args:
        trip_id: Trip identifier used in messages.
        seqs_sorted: stop_sequence values sorted in ascending order.

    returns:
        Validation messages for detected sequence gaps.
    """
    messages: List[str] = []
    last_seq = None
    for seq in seqs_sorted:
        if last_seq is not None and seq != last_seq + 1:
            messages.append(
                f"Trip_id {trip_id}: stop_sequence does not increment by one ({last_seq} -> {seq})"
            )
        last_seq = seq
    return messages


def make_signature(
    item: Tuple[str, List[Tuple[int, str, str, str]]]
) -> Tuple[str, Tuple[Tuple[int, str, str, str], ...]]:
    """Build a canonical signature for a trip from its ordered stop events.

    args:
        item: Pair of trip_id and raw stop event rows.

    returns:
        Pair of trip_id and sorted immutable event signature.
    """
    trip_id, rows = item
    normalized = tuple(sorted(rows, key=lambda value: value[0]))
    return trip_id, normalized


def build_expected_adjacency(route_stop_ids: List[str]) -> Dict[str, str]:
    """Build a forward adjacency map from a canonical ordered stop list.

    For route_stop_ids = [s0, s1, s2] returns {s0: s1, s1: s2}.

    args:
        route_stop_ids: Ordered list of stop_id strings for the route.

    returns:
        Mapping from stop_id to the next stop_id along the route.
    """
    adj: Dict[str, str] = {}
    for a, b in zip(route_stop_ids, route_stop_ids[1:]):
        adj[a] = b
    return adj


def load_trip_sequence_bounds(
    file_path: str, trip_ids: Set[str]
) -> Dict[str, Tuple[int, int]]:
    """Return the min and max stop_sequence for each trip_id.

    args:
        file_path: Path to the stop_times file.
        trip_ids: Set of trip_id values to include.

    returns:
        Mapping from trip_id to (min_seq, max_seq).
    """
    bounds: Dict[str, Tuple[int, int]] = {}
    for row in read_dict_rows(file_path):
        trip_id = row.get("trip_id", "").strip()
        if trip_id not in trip_ids:
            continue
        try:
            seq = int(row.get("stop_sequence", "").strip())
        except Exception:
            continue
        if trip_id not in bounds:
            bounds[trip_id] = (seq, seq)
        else:
            lo, hi = bounds[trip_id]
            bounds[trip_id] = (min(lo, seq), max(hi, seq))
    return bounds


# -----------------------------
# Line / shared-platform helpers
# -----------------------------
def load_trip_to_line(file_path: str, rid_to_name: Dict[str, str]) -> Dict[str, str]:
    """Return a mapping of trip_id to subway line name.

    args:
        file_path: Path to the trips file.
        rid_to_name: Mapping from route_id to line name (e.g. {"1.1.1": "L1"}).

    returns:
        Mapping from trip_id to line name for subway trips only.
    """
    trip_to_line: Dict[str, str] = {}
    for row in read_dict_rows(file_path):
        trip_id = row.get("trip_id", "").strip()
        route_id = row.get("route_id", "").strip()
        line = rid_to_name.get(route_id)
        if trip_id and line:
            trip_to_line[trip_id] = line
    return trip_to_line


def build_stop_to_lines(
    route_names_stop_ids: Dict[str, List[str]]
) -> Dict[str, List[str]]:
    """Invert a route name -> stop_id list mapping into stop_id -> line names.

    Lines are appended in the iteration order of `route_names_stop_ids`, so a
    stop present in multiple lines keeps that canonical order (e.g. L9S before L10S).

    args:
        route_names_stop_ids: Mapping from line name to its ordered stop_id list,
            e.g. `subway_reference.subway_lines.subway_route_names_stop_ids`.

    returns:
        Mapping from stop_id to the list of line names it belongs to.
    """
    stop_to_lines: Dict[str, List[str]] = {}
    for line_name, stop_ids in route_names_stop_ids.items():
        for stop_id in stop_ids:
            lines = stop_to_lines.setdefault(stop_id, [])
            if line_name not in lines:
                lines.append(line_name)
    return stop_to_lines


def build_shared_platform_lines(
    route_names_stop_ids: Dict[str, List[str]]
) -> Dict[str, List[str]]:
    """Return shared stop_id -> ordered list of lines serving it.

    args:
        route_names_stop_ids: Mapping from line name to its ordered stop_id list,
            e.g. `subway_reference.subway_lines.subway_route_names_stop_ids`.

    returns:
        `build_stop_to_lines` restricted to stop_ids served by more than one line.
    """
    stop_to_lines = build_stop_to_lines(route_names_stop_ids)
    return {
        stop_id: lines for stop_id, lines in stop_to_lines.items() if len(lines) > 1
    }


def format_stop_label(
    stop_id: str, stop_name: str, stop_to_lines: Dict[str, List[str]]
) -> str:
    """Prefix a stop name with its line(s), e.g. "L9S-L10S-Torrassa".

    args:
        stop_id: Platform stop_id to look up.
        stop_name: Stop name to prefix.
        stop_to_lines: Mapping from stop_id to line names, from `build_stop_to_lines`.

    returns:
        "{line1}-{line2}-...-{stop_name}", or plain `stop_name` if no lines are found.
    """
    lines = stop_to_lines.get(stop_id)
    if not lines:
        return stop_name
    return f"{'-'.join(lines)}-{stop_name}"


def label_entrance_by_platform(
    entrance_id: str,
    entrance_to_platform: Dict[str, Set[str]],
    stop_names: Dict[str, str],
    stop_to_lines: Dict[str, List[str]],
) -> str:
    """Label an entrance by the platform(s) it connects to, via format_stop_label.

    An entrance's own stop_name (e.g. a street name) is uninformative unless
    you already know that entrance; the connected platform's line-prefixed
    name (e.g. "L3-Trinitat Nova") is what actually locates it in the network.
    Platforms sharing the same stop_name (e.g. two directional platforms of
    the same station) have their lines merged under that one name instead of
    repeating it, e.g. "L9N/L10N-Onze de Setembre" rather than
    "L9N-Onze de Setembre / L10N-Onze de Setembre".

    args:
        entrance_id: Entrance stop_id (E.*) to label.
        entrance_to_platform: Mapping from entrance stop_id to the platform
            stop_ids (1.*) it connects to, i.e. `invert_entries` applied to
            `build_graph_and_coverage`'s platform_to_entries.
        stop_names: Mapping from stop_id to stop_name, from `load_stop_names`.
        stop_to_lines: Mapping from stop_id to line names, from `build_stop_to_lines`.

    returns:
        "{entrance stop_name} -- {platform format_stop_label(s)}", one label
        per distinct platform stop_name (merging lines of same-named
        platforms), joined by " / " when an entrance serves more than one
        distinctly-named platform; plain entrance stop_name if it isn't
        connected to any platform.
    """
    entrance_name: str
    platforms: List[str]
    platforms_by_name: Dict[str, List[str]]
    labels: List[str]

    entrance_name = stop_names.get(entrance_id, "(no name)")
    platforms = sorted(entrance_to_platform.get(entrance_id, ()))
    if not platforms:
        return entrance_name

    platforms_by_name = {}
    for platform in platforms:
        name = stop_names.get(platform, "(no name)")
        platforms_by_name.setdefault(name, []).append(platform)

    labels = []
    for name, same_name_platforms in platforms_by_name.items():
        if len(same_name_platforms) == 1:
            labels.append(
                format_stop_label(same_name_platforms[0], name, stop_to_lines)
            )
            continue
        lines: List[str] = []
        for platform in same_name_platforms:
            for line in stop_to_lines.get(platform, ()):
                if line not in lines:
                    lines.append(line)
        labels.append(f"{'/'.join(lines)}-{name}" if lines else name)

    return f"{entrance_name} -- {' / '.join(labels)}"


# -----------------------------
# Directed pair travel-time helpers
# -----------------------------
def consecutive_pairs(stop_ids: Sequence[str]) -> List[Tuple[str, str]]:
    """Return consecutive directed stop pairs for an ordered stop list.

    args:
        stop_ids: Canonical stop order for a line (or a sub-sequence of it,
            e.g. only the stops shared by a group of lines).

    returns:
        Directed pairs (a, b) for each consecutive position in stop_ids.
    """
    return list(zip(stop_ids, stop_ids[1:]))


def build_trip_groups_by_line(
    route_names_stop_ids: Dict[str, List[str]],
    routes_names_ids: Dict[str, str],
    trips_file: str,
) -> Tuple[Dict[str, Tuple[str, int]], Dict[Tuple[str, int], List[Tuple[str, str]]]]:
    """Map every trip on each line to its (line, direction_id) group and pairs.

    Shared by every per-line/direction breakdown (directional asymmetry, edge
    stdev, ...): each line's canonical stop order becomes direction_id=0's
    directed pairs, and the reverse order becomes direction_id=1's, with every
    trip assigned to its group via `load_trip_ids_by_route`.

    args:
        route_names_stop_ids: Mapping from line name to its ordered stop_id
            list, e.g. `subway_reference.subway_lines.subway_route_names_stop_ids` (or its
            `_artificial` post-duplication variant, for analyses that read
            stop_times after shared-platform duplication).
        routes_names_ids: Mapping from line name to route_id, e.g.
            `subway_reference.subway_lines.subway_routes_names_ids`.
        trips_file: Path to the trips file used to resolve each trip's
            direction_id.

    returns:
        Tuple of (trip_id -> (line, direction_id), (line, direction_id) ->
        directed stop pairs), so a single stop_times scan can serve every
        line and direction.
    """
    trip_id_to_group: Dict[str, Tuple[str, int]] = {}
    group_pairs: Dict[Tuple[str, int], List[Tuple[str, str]]] = {}

    for line_short_name, stop_ids in route_names_stop_ids.items():
        route_id = routes_names_ids.get(line_short_name)
        if not route_id:
            continue

        pairs_dir0 = consecutive_pairs(stop_ids)
        pairs_dir1 = [(b, a) for a, b in pairs_dir0]
        trip_ids_by_direction = load_trip_ids_by_route(trips_file, route_id)
        for trip_id in trip_ids_by_direction.get(0, set()):
            trip_id_to_group[trip_id] = (line_short_name, 0)
        for trip_id in trip_ids_by_direction.get(1, set()):
            trip_id_to_group[trip_id] = (line_short_name, 1)
        group_pairs[(line_short_name, 0)] = pairs_dir0
        group_pairs[(line_short_name, 1)] = pairs_dir1

    return trip_id_to_group, group_pairs


def _wrapped_diff(later: str, earlier: str) -> int:
    """Return `later - earlier` in seconds, adding 24h while negative.

    Stop times are clock-of-day strings, so a trip crossing midnight makes a
    naive subtraction negative; adding `SECONDS_PER_DAY` until non-negative
    recovers the actual elapsed duration.

    args:
        later: HH:MM:SS time at the later point.
        earlier: HH:MM:SS time at the earlier point.

    returns:
        Elapsed seconds between the two times, always non-negative.
    """
    diff = parse_time_to_seconds(later) - parse_time_to_seconds(earlier)
    while diff < 0:
        diff += SECONDS_PER_DAY
    return diff


def _collect_trip_rows(
    stop_times_file: str,
    trip_id_to_group: Dict[str, Hashable],
    group_stop_ids: Dict[Hashable, Set[str]],
    include_departure: bool,
) -> DefaultDict[str, List[Tuple]]:
    """Scan stop_times once, keeping only rows relevant to a known group.

    Shared by every `collect_pair_*_by_trip_group*` variant below, since they
    all need the same per-trip (stop_sequence, stop_id, arrival_time[,
    departure_time]) rows before walking consecutive pairs.

    args:
        stop_times_file: Path to the stop_times file to scan.
        trip_id_to_group: Mapping from trip_id to its group key. Trips absent
            from this mapping are skipped.
        group_stop_ids: Mapping from group key to the stop_ids relevant to
            that group; rows for stops outside this set are skipped.
        include_departure: Whether to also collect `departure_time` (needed
            by the door/sw split, not by plain travel-time collection).

    returns:
        Mapping from trip_id to its unsorted rows.
    """
    trip_rows: DefaultDict[str, List[Tuple]] = defaultdict(list)
    for row in read_dict_rows(stop_times_file):
        trip_id = row.get("trip_id", "")
        group = trip_id_to_group.get(trip_id)
        if group is None or group not in group_stop_ids:
            continue

        stop_id = row.get("stop_id", "")
        sequence_text = row.get("stop_sequence", "")
        arrival_time = row.get("arrival_time", "")
        if not stop_id or not sequence_text:
            continue
        if stop_id not in group_stop_ids[group]:
            continue

        try:
            stop_sequence = int(sequence_text)
        except ValueError:
            continue

        if include_departure:
            departure_time = row.get("departure_time", "")
            trip_rows[trip_id].append(
                (stop_sequence, stop_id, arrival_time, departure_time)
            )
        else:
            trip_rows[trip_id].append((stop_sequence, stop_id, arrival_time))
    return trip_rows


def _iter_consecutive_pair_rows(
    trip_rows: DefaultDict[str, List[Tuple]],
    trip_id_to_group: Dict[str, Hashable],
    group_pair_sets: Dict[Hashable, Set[Tuple[str, str]]],
) -> Iterable[Tuple[Hashable, Tuple[str, str], Tuple, Tuple]]:
    """Yield (group, pair, current_row, next_row) for each valid transition.

    A transition is valid when stop_sequence increments by exactly one and
    the resulting directed stop pair belongs to its group's pair set;
    non-consecutive or unmatched adjacencies are skipped, matching the
    behaviour of the original per-function loops.

    args:
        trip_rows: Per-trip rows, as returned by `_collect_trip_rows`.
        trip_id_to_group: Mapping from trip_id to its group key.
        group_pair_sets: Mapping from group key to its set of directed stop
            pairs.

    returns:
        Iterator of (group, pair, current_row, next_row) tuples.
    """
    for trip_id, rows in trip_rows.items():
        group = trip_id_to_group[trip_id]
        if group not in group_pair_sets:
            continue
        pair_set = group_pair_sets[group]
        rows.sort(key=lambda item: item[0])
        for current_row, next_row in zip(rows, rows[1:]):
            if next_row[0] != current_row[0] + 1:
                continue
            pair = (current_row[1], next_row[1])
            if pair not in pair_set:
                continue
            yield group, pair, current_row, next_row


def collect_pair_samples_by_trip_group(
    stop_times_file: str,
    trip_id_to_group: Dict[str, Hashable],
    group_pairs: Dict[Hashable, List[Tuple[str, str]]],
) -> Dict[Hashable, Dict[Tuple[str, str], List[int]]]:
    """Collect travel-time samples for several trip groups in one file pass.

    Each trip belongs to exactly one group (for example a (line, direction_id)
    pair), so several route/direction breakdowns can share a single scan of a
    potentially large stop_times file instead of one scan per group.

    args:
        stop_times_file: Path to the stop_times file to scan.
        trip_id_to_group: Mapping from trip_id to its group key. Trips absent
            from this mapping are skipped.
        group_pairs: Mapping from group key to the directed stop pairs
            relevant to that group; non-consecutive or unmatched adjacencies
            are ignored.

    returns:
        Mapping from group key to {pair: observed travel times in seconds},
        with every pair from group_pairs present (possibly with an empty list).
    """
    group_pair_sets = {group: set(pairs) for group, pairs in group_pairs.items()}
    group_stop_ids = {
        group: {stop_id for pair in pairs for stop_id in pair}
        for group, pairs in group_pairs.items()
    }
    trip_rows = _collect_trip_rows(
        stop_times_file, trip_id_to_group, group_stop_ids, include_departure=False
    )

    samples: Dict[Hashable, DefaultDict[Tuple[str, str], List[int]]] = {
        group: defaultdict(list) for group in group_pairs
    }
    for group, pair, current_row, next_row in _iter_consecutive_pair_rows(
        trip_rows, trip_id_to_group, group_pair_sets
    ):
        current_arrival, next_arrival = current_row[2], next_row[2]
        if not current_arrival or not next_arrival:
            continue
        samples[group][pair].append(_wrapped_diff(next_arrival, current_arrival))

    return {
        group: {pair: samples[group].get(pair, []) for pair in pairs}
        for group, pairs in group_pairs.items()
    }


def collect_pair_door_sw_samples_by_trip_group(
    stop_times_file: str,
    trip_id_to_group: Dict[str, Hashable],
    group_pairs: Dict[Hashable, List[Tuple[str, str]]],
) -> Tuple[
    Dict[Hashable, Dict[Tuple[str, str], List[int]]],
    Dict[Hashable, Dict[Tuple[str, str], List[int]]],
]:
    """Split each pair's travel time into door time at A and sw (run) time A->B.

    For a directed pair (A, B), `collect_pair_samples_by_trip_group` measures
    `arrival_B - arrival_A`, which conflates two physically different things:
    the dwell at the departure platform A (door open for boarding) and the
    actual movement between A and B. This splits them using `departure_time`
    at A: `door_time = departure_A - arrival_A` and
    `sw_time = arrival_B - departure_A` (so `door_time + sw_time` equals the
    travel time `collect_pair_samples_by_trip_group` would have reported).
    `sw_time` is named for the graph's `sw` (platform-to-platform) edge type,
    since it is the pure run time a future `sw` edge weight should use.

    args:
        stop_times_file: Path to the stop_times file to scan.
        trip_id_to_group: Mapping from trip_id to its group key. Trips absent
            from this mapping are skipped.
        group_pairs: Mapping from group key to the directed stop pairs
            relevant to that group; non-consecutive or unmatched adjacencies
            are ignored.

    returns:
        Tuple of (door_samples_by_group, sw_samples_by_group), each shaped
        like `collect_pair_samples_by_trip_group`'s return value so
        `average_times_for_pairs` can be applied directly to either.
    """
    group_pair_sets = {group: set(pairs) for group, pairs in group_pairs.items()}
    group_stop_ids = {
        group: {stop_id for pair in pairs for stop_id in pair}
        for group, pairs in group_pairs.items()
    }
    trip_rows = _collect_trip_rows(
        stop_times_file, trip_id_to_group, group_stop_ids, include_departure=True
    )

    door_samples: Dict[Hashable, DefaultDict[Tuple[str, str], List[int]]] = {
        group: defaultdict(list) for group in group_pairs
    }
    sw_samples: Dict[Hashable, DefaultDict[Tuple[str, str], List[int]]] = {
        group: defaultdict(list) for group in group_pairs
    }
    door_by_group: Dict[Hashable, Dict[Tuple[str, str], List[int]]] = {}
    sw_by_group: Dict[Hashable, Dict[Tuple[str, str], List[int]]] = {}

    for group, pair, current_row, next_row in _iter_consecutive_pair_rows(
        trip_rows, trip_id_to_group, group_pair_sets
    ):
        current_arrival, current_departure = current_row[2], current_row[3]
        next_arrival = next_row[2]
        if not current_arrival or not current_departure or not next_arrival:
            continue

        door_samples[group][pair].append(
            _wrapped_diff(current_departure, current_arrival)
        )
        sw_samples[group][pair].append(_wrapped_diff(next_arrival, current_departure))

    door_by_group = {
        group: {pair: door_samples[group].get(pair, []) for pair in pairs}
        for group, pairs in group_pairs.items()
    }
    sw_by_group = {
        group: {pair: sw_samples[group].get(pair, []) for pair in pairs}
        for group, pairs in group_pairs.items()
    }
    return door_by_group, sw_by_group


def collect_pair_door_sw_samples_by_trip_group_hourly(
    stop_times_file: str,
    trip_id_to_group: Dict[str, Hashable],
    group_pairs: Dict[Hashable, List[Tuple[str, str]]],
) -> Tuple[
    Dict[Hashable, Dict[Tuple[str, str], Dict[int, List[int]]]],
    Dict[Hashable, Dict[Tuple[str, str], Dict[int, List[int]]]],
]:
    """Like `collect_pair_door_sw_samples_by_trip_group`, bucketed by hour.

    The hour bucket is the arrival hour at A (a departure-hour proxy), same
    convention as the rest of this module's hour-bucketed helpers. Door and
    sw samples within the same hour bucket are appended in lockstep (one
    pair per trip occurrence), so `zip`-ing the two lists for a given hour
    gives the matching per-trip total (`door + sw`).

    args:
        stop_times_file: Path to the stop_times file to scan.
        trip_id_to_group: Mapping from trip_id to its group key. Trips absent
            from this mapping are skipped.
        group_pairs: Mapping from group key to the directed stop pairs
            relevant to that group; non-consecutive or unmatched adjacencies
            are ignored.

    returns:
        Tuple of (door_hourly_by_group, sw_hourly_by_group), each mapping
        group key to {pair: {departure_hour: samples}}.
    """
    group_pair_sets = {group: set(pairs) for group, pairs in group_pairs.items()}
    group_stop_ids = {
        group: {stop_id for pair in pairs for stop_id in pair}
        for group, pairs in group_pairs.items()
    }
    trip_rows = _collect_trip_rows(
        stop_times_file, trip_id_to_group, group_stop_ids, include_departure=True
    )

    door_samples: Dict[
        Hashable, DefaultDict[Tuple[str, str], DefaultDict[int, List[int]]]
    ] = {group: defaultdict(lambda: defaultdict(list)) for group in group_pairs}
    sw_samples: Dict[
        Hashable, DefaultDict[Tuple[str, str], DefaultDict[int, List[int]]]
    ] = {group: defaultdict(lambda: defaultdict(list)) for group in group_pairs}
    door_hourly_by_group: Dict[
        Hashable, Dict[Tuple[str, str], Dict[int, List[int]]]
    ] = {}
    sw_hourly_by_group: Dict[Hashable, Dict[Tuple[str, str], Dict[int, List[int]]]] = {}

    for group, pair, current_row, next_row in _iter_consecutive_pair_rows(
        trip_rows, trip_id_to_group, group_pair_sets
    ):
        current_arrival, current_departure = current_row[2], current_row[3]
        next_arrival = next_row[2]
        if not current_arrival or not current_departure or not next_arrival:
            continue

        hour = (parse_time_to_seconds(current_arrival) % SECONDS_PER_DAY) // 3600
        door_samples[group][pair][hour].append(
            _wrapped_diff(current_departure, current_arrival)
        )
        sw_samples[group][pair][hour].append(
            _wrapped_diff(next_arrival, current_departure)
        )

    door_hourly_by_group = {
        group: {pair: dict(door_samples[group].get(pair, {})) for pair in pairs}
        for group, pairs in group_pairs.items()
    }
    sw_hourly_by_group = {
        group: {pair: dict(sw_samples[group].get(pair, {})) for pair in pairs}
        for group, pairs in group_pairs.items()
    }
    return door_hourly_by_group, sw_hourly_by_group


def build_stop_id_order_index(
    route_names_stop_ids: Dict[str, List[str]]
) -> Dict[str, int]:
    """Flatten a line -> stop_id list mapping into one canonical rank per stop_id.

    Walks `route_names_stop_ids` the same way `subway_reference/stops_report.py` already
    does (line by line, then stop by stop), so sorting by this index lines up
    with that canonical order. The first line to mention a stop_id wins its
    rank.

    args:
        route_names_stop_ids: Mapping from line name to its ordered stop_id
            list, e.g. `subway_reference.subway_lines.subway_route_names_stop_ids_artificial`.

    returns:
        Mapping from stop_id to its 0-based canonical rank. Stop_ids outside
        `route_names_stop_ids` (e.g. entrances) have no entry; sort callers
        should fall back to `index.get(stop_id, len(index))` to push them
        after every platform.
    """
    order_index: Dict[str, int] = {}
    for stop_ids in route_names_stop_ids.values():
        for stop_id in stop_ids:
            if stop_id not in order_index:
                order_index[stop_id] = len(order_index)
    return order_index


def average_times_for_pairs(
    pair_samples: Dict[Tuple[str, str], List[int]]
) -> Dict[Tuple[str, str], Optional[Tuple[float, int, float]]]:
    """Return average travel time, sample count and stdev per directed pair.

    args:
        pair_samples: Mapping of directed stop pairs to travel-time samples.

    returns:
        Mapping from each pair to (mean_seconds, count, stdev), or None when
        no samples were observed for that pair.
    """
    results: Dict[Tuple[str, str], Optional[Tuple[float, int, float]]] = {}
    for pair, samples in pair_samples.items():
        if not samples:
            results[pair] = None
            continue
        count = len(samples)
        avg = mean(samples)
        std = stdev(samples) if count > 1 else 0.0
        results[pair] = (avg, count, std)
    return results
