import sys
from pathlib import Path
from typing import Dict, List, Set

try:
    from scripts.utils import read_dict_rows
except ModuleNotFoundError:
    from utils import read_dict_rows

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from data_validation.gtfs_utils import (  # noqa: E402
    PATHWAYS_FILE as GTFS_PATHWAYS_FILE,
    STOPS_FILE as GTFS_STOPS_FILE,
    build_graph_and_coverage,
    check_missing_files,
    load_pathway_ids,
    load_stops_info,
)

STOPS_FILE = Path(GTFS_STOPS_FILE)
PATHWAYS_FILE = Path(GTFS_PATHWAYS_FILE)

LINE_PREFIXES = ["1.1", "1.2", "1.3", "1.4", "1.5", "1.9"]
SHOW_ENTRANCES = True


def collect_stops_by_prefix(
    stops_file: Path, line_prefixes: List[str]
) -> Dict[str, List[Dict[str, str]]]:
    """Group stop records by the first matching line prefix.

    args:
        stops_file: Path to stops.txt.
        line_prefixes: Prefixes used to classify stop_id values.

    returns:
        A mapping from prefix to matching stop records.
    """
    stops_by_prefix: Dict[str, List[Dict[str, str]]] = {
        prefix: [] for prefix in line_prefixes
    }

    for row in read_dict_rows(stops_file):
        stop_id = row.get("stop_id", "")
        stop_name = row.get("stop_name", "").strip()

        for prefix in line_prefixes:
            if stop_id.startswith(prefix):
                stops_by_prefix[prefix].append(
                    {"stop_id": stop_id, "stop_name": stop_name}
                )
                break

    return stops_by_prefix


def collect_entrances_by_stop_id() -> Dict[str, Set[str]]:
    """Return platform stop IDs mapped to their entrance stop IDs.

    returns:
        Mapping from platform stop_id to the set of linked entrance stop_ids.
    """
    _, platform_to_entrances, _ = build_graph_and_coverage(
        load_pathway_ids(str(PATHWAYS_FILE))
    )
    return {
        stop_id: set(entrances) for stop_id, entrances in platform_to_entrances.items()
    }


def print_line_stops(
    prefix: str,
    grouped_stops: Dict[str, List[Dict[str, str]]],
    stop_info: Dict[str, tuple[str, str, str]],
    entrances_by_stop_id: Dict[str, Set[str]],
    show_entrances: bool,
) -> None:
    """Print one subway line with optional entrances for each platform stop.

    args:
        prefix: Line prefix (e.g. "1.1") to identify the subway line.
        grouped_stops: Mapping from prefix to list of stops in that line.
        stop_info: Mapping from stop_id to (name, lat, lon) tuple.
        entrances_by_stop_id: Mapping from platform stop_id to entrance stop_ids.
        show_entrances: Whether to print entrance stops beneath each platform stop.
    """
    line_number = prefix.split(".")[-1]
    print(f"\nLine {line_number}")

    sorted_items = sorted(grouped_stops[prefix], key=lambda item: item["stop_id"])
    if not sorted_items:
        print("(No results)")
        return

    for item in sorted_items:
        print(f"{item['stop_id']} - {item['stop_name']}")
        if not show_entrances:
            continue

        entrance_ids = sorted(entrances_by_stop_id.get(item["stop_id"], set()))
        for entrance_id in entrance_ids:
            entrance_name = stop_info.get(entrance_id, ("(no name)", "", ""))[0]
            print(f"     - {entrance_id} - {entrance_name}")


def main() -> None:
    """Print grouped Barcelona subway stops and, optionally, entrances.

    returns:
        None. Output is printed to stdout.
    """

    check_missing_files([str(STOPS_FILE)])

    print("Printing stops and optional entrances of each line of Barcelona subway")
    grouped_stops = collect_stops_by_prefix(STOPS_FILE, LINE_PREFIXES)
    stop_info = load_stops_info(str(STOPS_FILE))
    entrances_by_stop_id = collect_entrances_by_stop_id()

    for prefix in LINE_PREFIXES:
        print_line_stops(
            prefix=prefix,
            grouped_stops=grouped_stops,
            stop_info=stop_info,
            entrances_by_stop_id=entrances_by_stop_id,
            show_entrances=SHOW_ENTRANCES,
        )


if __name__ == "__main__":
    main()
