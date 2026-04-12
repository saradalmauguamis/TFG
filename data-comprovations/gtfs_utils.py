import os
import re
import sys
from pathlib import Path
from typing import Dict, Iterable, List, Set, Tuple

# Ensure the project root is on sys.path so that `utils` can be imported normally.
_PROJECT_ROOT = str(Path(__file__).resolve().parents[1])
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from utils import read_dict_rows, sniff_dialect  # noqa: E402


# Constants and paths
BASE = os.path.join(os.path.dirname(os.path.abspath("")), ".src", "gtfs", "data")
PATHWAYS_FILE = os.path.join(BASE, "pathways.txt")
TRANSFERS_FILE = os.path.join(BASE, "transfers.txt")
STOPS_FILE = os.path.join(BASE, "stops.txt")
STOP_TIMES_FILE = os.path.join(BASE, "stop_times.txt")
STOP_TIMES_CLEANED_FILE = os.path.join(BASE, "stop_times_cleaned.txt")
TRIPS_FILE = os.path.join(BASE, "trips.txt")
TRIPS_CLEANED_FILE = os.path.join(BASE, "trips_cleaned.txt")
ROUTES_FILE = os.path.join(BASE, "routes.txt")

# Route terminals by route_id: (first_terminal_stop_id, last_terminal_stop_id)
ROUTE_TERMINAL_STOPS: Dict[str, Tuple[str, str]] = {
    "1.1.1": ("1.111", "1.140"),
    "1.2.1": ("1.210", "1.227"),
    "1.3.1": ("1.314", "1.339"),
    "1.4.1": ("1.413", "1.434"),
    "1.5.1": ("1.509", "1.534"),
    "1.91.1": ("1.901", "1.918"),
    "1.94.1": ("1.930", "1.945"),
    "1.101.1": ("1.951", "1.916"),
    "1.104.1": ("1.930", "1.936"),
    "1.11.1": ("1.1136", "1.1140"),
    "1.99.1": ("1.9901", "1.9902"),
}


# Regex pattern PW_PAIR
PW_PAIR = re.compile(r"^PW\.(?P<a>[^_]+)_(?P<b>[^\s]+)$")


# CSV/file helpers
def check_missing_files(list_of_files: List[str]) -> None:
    """Print any paths that do not exist."""
    missing_files = [path for path in list_of_files if not os.path.exists(path)]
    if missing_files:
        print("The following files were not found:")
        for path in missing_files:
            print(" -", path)


def get_first_nonempty(row: Dict[str, str], *names: str) -> str:
    """Return the first non-empty value found for the given field names."""
    for name in names:
        value = row.get(name, "").strip()
        if value:
            return value
    return ""


# Loaders/parsers
def load_stop_ids(file_path: str) -> Set[str]:
    """Return the set of stop_id values from a file."""
    stop_ids: Set[str] = set()
    for row in read_dict_rows(file_path):
        stop_id = row.get("stop_id", "").strip()
        if stop_id:
            stop_ids.add(stop_id)
    return stop_ids


def load_stop_names(file_path: str) -> Dict[str, str]:
    """Return a mapping of stop_id to stop_name."""
    stop_names: Dict[str, str] = {}
    for row in read_dict_rows(file_path):
        stop_id = row.get("stop_id", "").strip()
        stop_name = row.get("stop_name", "").strip()
        if stop_id:
            stop_names[stop_id] = stop_name
    return stop_names


def load_pathway_ids(file_path: str) -> Set[str]:
    """Return the set of pathway_id values from a file."""
    pathway_ids: Set[str] = set()
    for row in read_dict_rows(file_path):
        pathway_id = row.get("pathway_id", "").strip()
        if pathway_id:
            pathway_ids.add(pathway_id)
    return pathway_ids


def load_route_ids(file_path: str) -> Set[str]:
    """Return the set of route_id values from a file."""
    route_ids: Set[str] = set()
    for row in read_dict_rows(file_path):
        route_id = row.get("route_id", "").strip()
        if route_id:
            route_ids.add(route_id)
    return route_ids


def load_trip_ids(file_path: str) -> Set[str]:
    """Return the set of trip_id values from a file."""
    trip_ids: Set[str] = set()
    for row in read_dict_rows(file_path):
        trip_id = row.get("trip_id", "").strip()
        if trip_id:
            trip_ids.add(trip_id)
    return trip_ids


def load_from_stop_ids(file_path: str) -> Set[str]:
    """Return the set of from_stop_id values from a file."""
    stop_ids: Set[str] = set()
    for row in read_dict_rows(file_path):
        stop_id = row.get("from_stop_id", "").strip()
        if stop_id:
            stop_ids.add(stop_id)
    return stop_ids


def load_to_stop_ids(file_path: str) -> Set[str]:
    """Return the set of to_stop_id values from a file."""
    stop_ids: Set[str] = set()
    for row in read_dict_rows(file_path):
        stop_id = row.get("to_stop_id", "").strip()
        if stop_id:
            stop_ids.add(stop_id)
    return stop_ids


# Validation helpers 
def check_trip(trip_id: str, seqs_sorted: List[int]) -> List[str]:
    """Check whether stop_sequence increases by one for a trip."""
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
    """Build a canonical signature for a trip from its ordered stop events."""
    trip_id, rows = item
    normalized = tuple(sorted(rows, key=lambda value: value[0]))
    return trip_id, normalized


def iter_pathway_pairs(file_path: str) -> Iterable[Tuple[str, str, str]]:
    """Yield (pathway_id, a, b) for rows matching the pathway pattern PW.a_b."""
    for row in read_dict_rows(file_path):
        pathway_id = row.get("pathway_id", "").strip()
        if not pathway_id:
            continue
        match = PW_PAIR.match(pathway_id)
        if not match:
            continue
        yield pathway_id, match.group("a"), match.group("b")


def load_transfer_pairs(file_path: str) -> Iterable[Tuple[str, str]]:
    """Yield (from_stop_id, to_stop_id) pairs from transfers.txt."""
    for row in read_dict_rows(file_path):
        from_stop_id = row.get("from_stop_id", "").strip()
        to_stop_id = row.get("to_stop_id", "").strip()
        if from_stop_id or to_stop_id:
            yield from_stop_id, to_stop_id


def load_stops_info(file_path: str) -> Dict[str, Tuple[str, str, str]]:
    """Return stop_id -> (stop_name, stop_lat, stop_lon)."""
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
    """Return stop_name -> sorted unique platform stop_id list for 1.* platforms."""
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
    """Return undirected platform pairs (1.*, 1.*) linked by a pathway."""
    pairs: Set[Tuple[str, str]] = set()
    for _, stop_a, stop_b in iter_pathway_pairs(file_path):
        if stop_a.startswith("1.") and stop_b.startswith("1."):
            first, second = sorted((stop_a, stop_b))
            pairs.add((first, second))
    return pairs


# The platform graph helper that was still embedded later in the notebook
def build_graph_and_coverage(
    pathway_ids: Set[str],
) -> Tuple[Dict[str, Set[str]], Dict[str, Set[str]], Set[str]]:
    """Build the platform graph and entrance coverage information."""
    platform_graph: Dict[str, Set[str]] = {}
    platform_to_entries: Dict[str, Set[str]] = {}
    covered_platforms: Set[str] = set()

    def add_platform_edge(stop_a: str, stop_b: str) -> None:
        platform_graph.setdefault(stop_a, set()).add(stop_b)
        platform_graph.setdefault(stop_b, set()).add(stop_a)

    def add_entry(platform_stop: str, entrance_stop: str) -> None:
        platform_to_entries.setdefault(platform_stop, set()).add(entrance_stop)
        covered_platforms.add(platform_stop)

    for pathway_id in pathway_ids:
        match = PW_PAIR.match(pathway_id)
        if not match:
            continue
        stop_a, stop_b = match.group("a"), match.group("b")

        if stop_a.startswith("1.") and stop_b.startswith("1."):
            add_platform_edge(stop_a, stop_b)

        if stop_a.startswith("1.") and stop_b.startswith("E."):
            add_entry(stop_a, stop_b)
        elif stop_b.startswith("1.") and stop_a.startswith("E."):
            add_entry(stop_b, stop_a)

    return platform_graph, platform_to_entries, covered_platforms


# Explicit re-exports for type checking and IDE support
__all__ = [
    # Shared CSV helpers from root utils
    "sniff_dialect",
    "read_dict_rows",
    # Constants
    "BASE",
    "PATHWAYS_FILE",
    "TRANSFERS_FILE",
    "STOPS_FILE",
    "STOP_TIMES_FILE",
    "STOP_TIMES_CLEANED_FILE",
    "TRIPS_FILE",
    "TRIPS_CLEANED_FILE",
    "ROUTES_FILE",
    "ROUTE_TERMINAL_STOPS",
    "PW_PAIR",
    # Functions
    "check_missing_files",
    "get_first_nonempty",
    "load_stop_ids",
    "load_stop_names",
    "load_pathway_ids",
    "load_route_ids",
    "load_trip_ids",
    "load_from_stop_ids",
    "load_to_stop_ids",
    "check_trip",
    "make_signature",
    "iter_pathway_pairs",
    "load_transfer_pairs",
    "load_stops_info",
    "load_platforms_by_name",
    "load_platform_pairs_present",
    "build_graph_and_coverage",
]


