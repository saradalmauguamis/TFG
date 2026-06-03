"""Common helpers shared by the split data-check notebooks."""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, Iterable, List, Tuple


def add_project_root_to_path() -> Path:
    """Add the project root to sys.path and return it.

    returns:
        Path of the project root that was added to `sys.path`.
    """
    current = Path.cwd().resolve()
    if (current / "data_validation" / "gtfs_utils.py").exists():
        project_root = current
    elif (current / "gtfs_utils.py").exists() and current.name == "data_validation":
        project_root = current.parent
    else:
        project_root = Path(__file__).resolve().parents[2]

    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    return project_root


PROJECT_ROOT = add_project_root_to_path()

import scripts.basics as basics  # noqa: E402


def stop_sort_key(stop_id: str) -> Tuple[int, str]:
    """Sort stop identifiers by their numeric suffix when possible.

    args:
        stop_id: Stop identifier string, possibly with a dot-separated suffix.

    returns:
        Tuple where first element is the numeric suffix (or a large number when
        not numeric) and second element is the original stop id for tie-breaking.
    """
    _, _, suffix = stop_id.partition(".")
    try:
        return int(suffix), stop_id
    except Exception:
        return 10**9, stop_id


def ordered_stop_ids(stop_ids: Iterable[str]) -> List[str]:
    """Return stop identifiers sorted with the numeric suffix order used in the data.

    args:
        stop_ids: Iterable of stop identifier strings.

    returns:
        List of cleaned and sorted stop identifier strings.
    """
    cleaned = [sid.strip() for sid in stop_ids if sid and sid.strip()]
    return sorted(cleaned, key=stop_sort_key)


def route_id_to_name() -> Dict[str, str]:
    """Return the canonical mapping route_id -> route_name for subway lines.

    returns:
        Mapping from route id to route name for subway routes.
    """
    return {rid: name for name, rid in basics.subway_routes_names_ids.items()}


def ordered_subway_stops(route_name: str) -> List[str]:
    """Return the canonical ordered stop list for a subway route name.

    args:
        route_name: Canonical route name (e.g. 'L1').

    returns:
        Ordered list of stop identifiers for the given route, in the canonical
        direction (direction_id=0). Reverse for direction_id=1.
    """
    return list(basics.subway_route_names_stop_ids.get(route_name, []))
