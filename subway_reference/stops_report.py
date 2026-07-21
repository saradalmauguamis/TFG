import sys
from pathlib import Path
from typing import Any, Dict, List, Set

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from subway_reference.subway_lines import (  # noqa: E402
    subway_route_names_stop_ids,
    subway_route_names_stop_ids_artificial,
)
from data_validation.gtfs_utils import (  # noqa: E402
    PATHWAYS_FILE as PATHWAYS_SHARED_FILE,
    PATHWAYS_RAW_FILE,
    STOPS_FILE as STOPS_SHARED_FILE,
    STOPS_SUBWAY_FILE,
    build_directed_entrance_edges,
    check_missing_files,
    load_pathway_ids,
    load_stop_names,
    print_file_disclaimer,
)

# Set to True to inspect stop_ids after `5_shared_platforms_duplication.py`
# (i.e. `subway_route_names_stop_ids_artificial`, against the `*_shared.txt`
# files); False inspects the raw subway stage (`subway_route_names_stop_ids`).
USE_ARTIFICIAL = True
SHOW_ENTRANCES = True

ROUTE_STOP_IDS = (
    subway_route_names_stop_ids_artificial
    if USE_ARTIFICIAL
    else subway_route_names_stop_ids
)
STOPS_FILE = Path(STOPS_SHARED_FILE if USE_ARTIFICIAL else STOPS_SUBWAY_FILE)
PATHWAYS_FILE = Path(PATHWAYS_SHARED_FILE if USE_ARTIFICIAL else PATHWAYS_RAW_FILE)


def _entrance_direction(entrance_id: str, forward: Set[str], backward: Set[str]) -> str:
    """Classify a platform-entrance edge by which direction(s) exist.

    args:
        entrance_id: Entrance stop_id being classified.
        forward: Entrance IDs reachable from the platform (PW.platform_entrance).
        backward: Entrance IDs that can reach the platform (PW.entrance_platform).

    returns:
        "both", "platform_to_entrance" or "entrance_to_platform" depending on
        which direction(s) of the pathway exist between the platform and the
        entrance.
    """
    in_forward = entrance_id in forward
    in_backward = entrance_id in backward
    if in_forward and in_backward:
        return "both"
    if in_forward:
        return "platform_to_entrance"
    if in_backward:
        return "entrance_to_platform"
    return "both"


def build_expanded_dictionary(
    stops_file: Path, pathways_file: Path, stop_ids_by_line: Dict[str, List[str]]
) -> Dict[str, Dict[str, List[Dict[str, Any]]]]:
    """Build a per-line expanded index with names and entrances.

    args:
        stops_file: Path to the stops file for the selected pipeline stage.
        pathways_file: Path to the pathways file for the selected pipeline stage.
        stop_ids_by_line: Mapping of line label to platform stop IDs in order.

    returns:
        Mapping where each line label maps to a dict with key `stops` whose value is
        a list of stop records. Each stop record contains `stop_id`, `name` and
        `entrances` (a list of dicts with `id`, `name` and `direction`, where
        `direction` is "both", "platform_to_entrance" or "entrance_to_platform").
    """
    expanded: Dict[str, Dict[str, List[Dict[str, Any]]]] = {}
    stops_list: List[Dict[str, Any]] = []
    line_name: str
    ids: List[str]
    stop_id: str
    name: str
    forward: Set[str]
    backward: Set[str]
    entrance_ids: List[str]
    entrances: List[Dict[str, str]]

    stop_names = load_stop_names(str(stops_file))
    platform_to_entrance, entrance_to_platform = build_directed_entrance_edges(
        load_pathway_ids(str(pathways_file))
    )

    # Build expanded per-line structure
    for line_name, ids in stop_ids_by_line.items():
        stops_list = []
        for stop_id in ids:
            name = stop_names.get(stop_id, "")
            forward = platform_to_entrance.get(stop_id, set())
            backward = entrance_to_platform.get(stop_id, set())
            entrance_ids = sorted(forward | backward)
            entrances = [
                {
                    "id": eid,
                    "name": stop_names.get(eid, ""),
                    "direction": _entrance_direction(eid, forward, backward),
                }
                for eid in entrance_ids
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
    direction: str = ""
    suffix: str = ""

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
            direction = ent.get("direction", "both")
            suffix = ""
            if direction == "platform_to_entrance":
                suffix = " (only platform --> entry pathway)"
            elif direction == "entrance_to_platform":
                suffix = " (only entry --> platform pathway)"
            print(f"     - {ent_id} - {ent_name}{suffix}")


def main() -> None:
    """Print grouped Barcelona subway stops and, optionally, entrances."""
    expanded: Dict[str, Dict[str, List[Dict[str, Any]]]]

    check_missing_files([str(STOPS_FILE), str(PATHWAYS_FILE)])
    print_file_disclaimer([str(STOPS_FILE), str(PATHWAYS_FILE)])

    print(
        "Printing stops and optional entrances of each line of Barcelona subway "
        f"(show_entrances={SHOW_ENTRANCES}, use_artificial={USE_ARTIFICIAL})"
    )
    expanded = build_expanded_dictionary(STOPS_FILE, PATHWAYS_FILE, ROUTE_STOP_IDS)

    for route_name in ROUTE_STOP_IDS:
        print_expanded_line(
            line_name=route_name,
            line_data=expanded.get(route_name, {}),
            show_entrances=SHOW_ENTRANCES,
        )


if __name__ == "__main__":
    main()
