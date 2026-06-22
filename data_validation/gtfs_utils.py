import os
import re
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set, Tuple

# Ensure the project root is on sys.path so that shared scripts can be imported.
_PROJECT_ROOT = str(Path(__file__).resolve().parents[1])
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)


# -----------------------------
# Module setup
# -----------------------------

from scripts.utils import read_dict_rows, read_header, sniff_dialect  # noqa: E402


# -----------------------------
# Explicit re-exports
# -----------------------------

# Explicit re-exports for type checking and IDE support
__all__ = [
    # Shared CSV helpers
    "sniff_dialect",
    "read_dict_rows",
    "read_header",
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
    "PATHWAYS_FILE",
    "ROUTES_RAW_FILE",
    "ROUTES_FILE",
    "STOP_TIMES_RAW_FILE",
    "STOP_TIMES_SUBWAY_FILE",
    "STOP_TIMES_CLEANED_FILE",
    "STOP_TIMES_SEQUENCE_FILE",
    "STOP_TIMES_FILE",
    "WRONG_STOP_SEQUENCES_FILE",
    "DOORS_FILE",
    "STOPS_RAW_FILE",
    "STOPS_FILE",
    "TRANSFERS_FILE",
    "TRIPS_RAW_FILE",
    "TRIPS_SUBWAY_FILE",
    "TRIPS_FILE",
    "TRIP_IDS_TO_ELIMINATE_FILE",
    "SECONDS_PER_DAY",
    # Regex / Patterns
    "PW_PAIR",
    # CSV / file helpers
    "check_missing_files",
    "print_file_disclaimer",
    "get_first_nonempty",
    # Loaders / parsers
    "load_stop_ids",
    "load_stop_names",
    "load_pathway_ids",
    "load_route_ids",
    "load_trip_ids",
    "load_trip_ids_by_route",
    "load_from_stop_ids",
    "load_to_stop_ids",
    "load_nonempty_lines",
    "parse_time_to_seconds",
    "format_seconds",
    "seconds_to_hms",
    # Pathway / transfer helpers
    "iter_pathway_pairs",
    "load_transfer_pairs",
    "load_stops_info",
    # Platform helpers
    "load_platforms_by_name",
    "load_platform_pairs_present",
    # Graph builders
    "build_graph_and_coverage",
    # Validation helpers
    "check_trip",
    "make_signature",
    # Additional helpers for route/trip sequence checks
    "collect_trip_stop_ids",
    "build_expected_adjacency",
    "is_contiguous_subsequence",
    "load_trip_sequence_bounds",
    "load_trip_to_line",
    "build_stop_to_lines",
    "format_stop_label",
]


# -----------------------------
# Constants / paths
# -----------------------------

_DEFAULT_DATA_DIR = Path(__file__).resolve().parents[1] / ".src" / "gtfs" / "data"
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

PATHWAYS_FILE = os.path.join(RAW_BASE, "pathways.txt")

ROUTES_RAW_FILE = os.path.join(RAW_BASE, "routes.txt")
ROUTES_FILE = os.path.join(SUBWAY_BASE, "routes_subway.txt")

STOP_TIMES_RAW_FILE = os.path.join(RAW_BASE, "stop_times.txt")
STOP_TIMES_SUBWAY_FILE = os.path.join(SUBWAY_BASE, "stop_times_subway.txt")
STOP_TIMES_CLEANED_FILE = os.path.join(DUPLICATED_TRIPS_BASE, "stop_times_cleaned.txt")
# STOP_TIMES_FILE = os.path.join(STOP_SEQUENCE_BASE, "stop_times_sequence.txt")
# STOP_TIMES_DOORS_FILE = os.path.join(DOORS_BASE, "stop_times_doors.txt")
STOP_TIMES_SEQUENCE_FILE = os.path.join(STOP_SEQUENCE_BASE, "stop_times_sequence.txt")
STOP_TIMES_FILE = os.path.join(DOORS_BASE, "stop_times_doors.txt")

WRONG_STOP_SEQUENCES_FILE = os.path.join(STOP_SEQUENCE_BASE, "wrong_stop_sequences.txt")
DOORS_FILE = os.path.join(DOORS_BASE, "doors.txt")

STOPS_RAW_FILE = os.path.join(RAW_BASE, "stops.txt")
STOPS_FILE = os.path.join(SUBWAY_BASE, "stops_subway.txt")

TRANSFERS_FILE = os.path.join(RAW_BASE, "transfers.txt")

TRIPS_RAW_FILE = os.path.join(RAW_BASE, "trips.txt")
TRIPS_SUBWAY_FILE = os.path.join(SUBWAY_BASE, "trips_subway.txt")
TRIPS_FILE = os.path.join(DUPLICATED_TRIPS_BASE, "trips_cleaned.txt")

TRIP_IDS_TO_ELIMINATE_FILE = os.path.join(
    DUPLICATED_TRIPS_BASE, "trip_ids_to_eliminate.txt"
)


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


def get_first_nonempty(row: Dict[str, str], *names: str) -> str:
    """Return the first non-empty value found for the given field names.

    args:
        row: Row dictionary to inspect.
        *names: Candidate field names in priority order.

    returns:
        The first non-empty value, or an empty string.
    """
    for name in names:
        value = row.get(name, "").strip()
        if value:
            return value
    return ""


# -----------------------------
# Loaders / parsers
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


def build_graph_and_coverage(
    pathway_ids: Set[str],
) -> Tuple[Dict[str, Set[str]], Dict[str, Set[str]], Set[str]]:
    """Build the platform graph and entrance coverage information.

    args:
        pathway_ids: Pathway IDs to parse and classify.

        returns:
                Tuple containing three elements:

                - `platform_graph` (Dict[str, Set[str]]): adjacency map of platform stop IDs
                    (IDs starting with `1.`) to the set of directly connected platform stop IDs.
                    Edges are undirected: when two platforms are connected both appear in each
                    other's adjacency set.

                - `platform_to_entries` (Dict[str, Set[str]]): mapping from a platform stop ID
                    to the set of entrance stop IDs (IDs starting with `E.`) that connect to that
                    platform. Only platform↔entrance pathway edges are recorded here.

                - `covered_platforms` (Set[str]): set of platform stop IDs that have at least
                    one connected entrance (i.e., the keys of `platform_to_entries`).
    """
    platform_graph: Dict[str, Set[str]] = {}
    platform_to_entries: Dict[str, Set[str]] = {}
    covered_platforms: Set[str] = set()

    for pathway_id in pathway_ids:
        match = PW_PAIR.match(pathway_id)
        if not match:
            continue
        stop_a, stop_b = match.group("a"), match.group("b")

        if stop_a.startswith("1.") and stop_b.startswith("1."):
            _add_platform_edge(platform_graph, stop_a, stop_b)

        if stop_a.startswith("1.") and stop_b.startswith("E."):
            _add_entry(platform_to_entries, covered_platforms, stop_a, stop_b)
        elif stop_b.startswith("1.") and stop_a.startswith("E."):
            _add_entry(platform_to_entries, covered_platforms, stop_b, stop_a)

    return platform_graph, platform_to_entries, covered_platforms


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


# -----------------------------
# Additional helpers for route/trip sequence checks
# -----------------------------
def collect_trip_stop_ids(file_path: str, trip_ids: Set[str]) -> Dict[str, List[str]]:
    """Collect ordered stop_id lists for trips in `trip_ids` from a stop_times file.

    args:
        file_path: Path to stop_times (cleaned) file.
        trip_ids: Set of trip_id strings to collect.

    returns:
        Mapping trip_id -> ordered list of stop_id (sorted by stop_sequence).
    """
    rows_by_trip: Dict[str, List[Tuple[int, str]]] = {}
    result: Dict[str, List[str]] = {}

    for r in read_dict_rows(file_path):
        tid = r.get("trip_id", "").strip()
        if tid not in trip_ids:
            continue
        seq_s = r.get("stop_sequence", "").strip()
        sid = r.get("stop_id", "").strip()
        try:
            seq = int(seq_s)
        except Exception:
            seq = 10**9
        rows_by_trip.setdefault(tid, []).append((seq, sid))

    for tid, rows in rows_by_trip.items():
        rows.sort(key=lambda x: x[0])
        result[tid] = [sid for _, sid in rows]
    return result


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


def is_contiguous_subsequence(seq: List[str], full: List[str]) -> bool:
    """Return True if `seq` appears as a contiguous subsequence inside `full`.

    args:
        seq: Candidate subsequence list.
        full: Full list to search within.

    returns:
        True if `seq` is a contiguous subsequence of `full`, else False.
    """
    n = len(seq)
    m = len(full)
    if n == 0:
        return True
    if n > m:
        return False
    for i in range(m - n + 1):
        if full[i : i + n] == seq:
            return True
    return False


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
            e.g. `scripts.basics.subway_route_names_stop_ids`.

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
