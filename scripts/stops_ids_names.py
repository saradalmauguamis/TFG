import sys
from pathlib import Path
from typing import Any, Dict, List, Set

from basics import subway_route_names_stop_ids

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from data_validation.gtfs_utils import (  # noqa: E402
    PATHWAYS_FILE as GTFS_PATHWAYS_FILE,
    STOPS_FILE as GTFS_STOPS_FILE,
    build_graph_and_coverage,
    check_missing_files,
    load_pathway_ids,
    load_stop_names,
)

STOPS_FILE = Path(GTFS_STOPS_FILE)
PATHWAYS_FILE = Path(GTFS_PATHWAYS_FILE)

SHOW_ENTRANCES = True


def build_expanded_dictionary(
    stops_file: Path, pathways_file: Path, stop_ids_by_line: Dict[str, Set[str]]
) -> Dict[str, Dict[str, List[Dict[str, Any]]]]:
    """Build a per-line expanded index with names and entrances.

    args:
        stops_file: Path to `stops.txt`.
        pathways_file: Path to `pathways.txt`.
        stop_ids_by_line: Mapping of line label to platform stop IDs.

    returns:
        Mapping where each line label maps to a dict with key `stops` whose value is
        a list of stop records. Each stop record contains `stop_id`, `name` and
        `entrances` (a list of dicts with `id` and `name`).
    """
    expanded: Dict[str, Dict[str, List[Dict[str, Any]]]] = {}
    stops_list: List[Dict[str, Any]] = []
    line_name: str
    ids: Set[str]
    stop_id: str
    name: str
    entrance_ids: List[str]
    entrances: List[Dict[str, str]]

    stop_names = load_stop_names(str(stops_file))
    _, platform_to_entrances, _ = build_graph_and_coverage(
        load_pathway_ids(str(pathways_file))
    )

    # Build expanded per-line structure
    for line_name, ids in stop_ids_by_line.items():
        stops_list = []
        for stop_id in sorted(ids):
            name = stop_names.get(stop_id, "")
            entrance_ids = sorted(platform_to_entrances.get(stop_id, set()))
            entrances = [
                {"id": eid, "name": stop_names.get(eid, "")} for eid in entrance_ids
            ]
            stops_list.append(
                {"stop_id": stop_id, "name": name, "entrances": entrances}
            )
        expanded[line_name] = {"stops": stops_list}
    return expanded


def print_expanded_line(
    line_name: str, line_data: Dict[str, Any], show_entrances: bool
) -> None:
    """Print one line from an expanded per-line index.

    args:
        line_name: Line label (e.g. "L1") to print.
        line_data: Expanded per-line dict returned by `build_expanded_dictionary`.
        show_entrances: Whether to print entrance rows beneath each platform stop.
    """
    stops: List[Dict[str, Any]] = []
    stop: Dict[str, Any]
    ent_id: str = ""
    ent_name: str = ""

    print("\n\n" + "=" * 50)
    print(f"{line_name}")
    print("=" * 50)
    stops = line_data.get("stops", [])
    if not stops:
        print("(No results)")
        return

    for stop in stops:
        print(f"{stop['stop_id']} - {stop['name']}")
        if not show_entrances:
            continue
        for ent in stop.get("entrances", []):
            ent_id = ent.get("id", "")
            ent_name = ent.get("name", "(no name)") or "(no name)"
            print(f"     - {ent_id} - {ent_name}")


def main() -> None:
    """Print grouped Barcelona subway stops and, optionally, entrances."""
    expanded: Dict[str, Dict[str, List[Dict[str, Any]]]]

    check_missing_files([str(STOPS_FILE), str(PATHWAYS_FILE)])

    print("Printing stops and optional entrances of each line of Barcelona subway")
    expanded = build_expanded_dictionary(
        STOPS_FILE, PATHWAYS_FILE, subway_route_names_stop_ids
    )

    for route_name in subway_route_names_stop_ids:
        print_expanded_line(
            line_name=route_name,
            line_data=expanded.get(route_name, {}),
            show_entrances=SHOW_ENTRANCES,
        )


if __name__ == "__main__":
    main()
