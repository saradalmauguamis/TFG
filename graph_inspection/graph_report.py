"""Report vertex/edge counts for the weighted subway graph in WEIGHTS_FILE.

`data_validation/processing/6_weights.py` builds `WEIGHTS_FILE`
(`data/6_weights/weights.txt`), one row per directed edge
(`from_stop_id, to_stop_id, weight_seconds, type`) of the final routing
graph. This script summarizes that file: how many vertices/arrows it has,
split by kind (entry vs platform, SW/TF/PW), plus how many of each are
"duplicated": artifacts of `5_shared_platforms_duplication.py` splitting a
platform shared by several lines into one stop_id per line (see
`EQUIVALENCES_FILE`, `data/5_shared_platforms/equivalences.txt`).

Vocabulary used below:
- vertex: any stop_id appearing in `from_stop_id`/`to_stop_id`. An entry
  (`E.*`) is reachable from street level; a platform (`1.*`) is where trains
  stop.
- arrow: one directed row of `WEIGHTS_FILE` (a->b and b->a are two arrows).
- edge: an undirected arrow pair, i.e. {a, b} counted once regardless of how
  many directed arrows connect them.
- duplicated vertex: a stop_id listed as a `new_stop_id` in
  `EQUIVALENCES_FILE` (the artificial per-line stop_id created for a shared
  platform).
- duplicated arrow/edge: one whose `from_stop_id` or `to_stop_id` is a
  duplicated vertex.

How each number is computed:
- Vertices: the set of `from_stop_id`/`to_stop_id` values in `WEIGHTS_FILE`,
  split by the `E.`/`1.` prefix. Duplicated vertices are the subset also
  present as a `new_stop_id` in `EQUIVALENCES_FILE`.
- Arrows: row counts, overall and per `type` value.
- Edges: unique unordered `{from_stop_id, to_stop_id}` pairs, overall and
  per `type`.
- Duplicated arrows/edges: the same arrow/edge counts, restricted to rows
  touching a duplicated vertex, overall and per type.
- Arrow capacity: how full the graph is versus the maximum it could hold. In
  an undirected simple graph on `|V|` vertices, the max number of edges is
  `(|V|-1)*|V|/2` (every vertex pairs with every other vertex once). A
  directed simple graph (no self-loops, no parallel arrows) allows an arrow in
  *both* directions per pair, so its max is `(|V|-1)*|V|`. We report the
  actual arrow count as a percentage of that maximum.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from data_validation.gtfs_utils import (  # noqa: E402
    EQUIVALENCES_FILE,
    WEIGHTS_FILE,
    check_missing_files,
    print_file_disclaimer,
    read_dict_rows,
)

WeightRow = Dict[str, str]
EDGE_TYPES = ("SW", "TF", "PW")


def pct(part: int, total: int) -> str:
    """Format part as a percentage of total, e.g. "74.6%".

    args:
        part: The sub-count.
        total: The whole count part is a fraction of.

    returns:
        Formatted percentage string, or "0.0%" if total is 0.
    """
    return f"{part / total:.1%}" if total else "0.0%"


def collect_vertices(rows: List[WeightRow]) -> Set[str]:
    """Return every stop_id appearing as a from_stop_id or to_stop_id.

    args:
        rows: WEIGHTS_FILE rows.

    returns:
        Set of unique stop_ids.
    """
    return {row["from_stop_id"] for row in rows} | {row["to_stop_id"] for row in rows}


def load_duplicated_stop_ids(equivalences_file: str) -> Set[str]:
    """Return the set of artificial per-line stop_ids created by shared-platform splitting.

    args:
        equivalences_file: Path to EQUIVALENCES_FILE.

    returns:
        Set of new_stop_id values, one per (original stop_id, line) split.
    """
    return {row["new_stop_id"] for row in read_dict_rows(equivalences_file)}


def unordered_pairs(rows: List[WeightRow]) -> Set[Tuple[str, str]]:
    """Return the unique undirected {from_stop_id, to_stop_id} pairs in rows.

    args:
        rows: WEIGHTS_FILE rows (or a filtered subset of them).

    returns:
        Set of (a, b) pairs with a <= b, one per undirected edge.
    """
    return {tuple(sorted((row["from_stop_id"], row["to_stop_id"]))) for row in rows}


def rows_by_type(rows: List[WeightRow]) -> Dict[str, List[WeightRow]]:
    """Split rows into SW/TF/PW buckets by their type column.

    args:
        rows: WEIGHTS_FILE rows (or a filtered subset of them).

    returns:
        Mapping from type ("SW", "TF", "PW") to its rows.
    """
    buckets: Dict[str, List[WeightRow]] = {edge_type: [] for edge_type in EDGE_TYPES}
    for row in rows:
        buckets[row["type"]].append(row)
    return buckets


def print_vertex_report(vertices: Set[str], duplicated_vertices: Set[str]) -> None:
    """Print the vertex section: total/entries/platforms, then duplicated ones.

    args:
        vertices: Every stop_id in WEIGHTS_FILE.
        duplicated_vertices: Subset of vertices that are artificial per-line
            stop_ids (from EQUIVALENCES_FILE).
    """
    entries: Set[str] = {v for v in vertices if v.startswith("E.")}
    platforms: Set[str] = {v for v in vertices if v.startswith("1.")}
    duplicated_entries: Set[str] = {
        v for v in duplicated_vertices if v.startswith("E.")
    }
    duplicated_platforms: Set[str] = {
        v for v in duplicated_vertices if v.startswith("1.")
    }

    total = len(vertices)
    print(f"Nre of vertices: {total}")
    print(f"    - Nre of entries: {len(entries)} ({pct(len(entries), total)})")
    print(f"    - Nre of platforms: {len(platforms)} ({pct(len(platforms), total)})")
    print(
        f"    - Total nre of duplicated vertices: {len(duplicated_vertices)} "
        f"({pct(len(duplicated_vertices), total)})"
    )
    print(f"        - Nre of duplicated entries: {len(duplicated_entries)}")
    print(f"        - Nre of duplicated platforms: {len(duplicated_platforms)}")


def print_type_breakdown(
    rows: List[WeightRow],
    indent: str,
    label_prefix: str = "",
    total: int | None = None,
) -> None:
    """Print the arrows/edges count for SW, TF and PW within rows.

    args:
        rows: Arrow rows to break down (either all arrows or the duplicated
            subset).
        indent: Leading whitespace for the "Nre of {type} arrows" lines; the
            nested edges line gets 4 more spaces.
        label_prefix: Text inserted before "{type} arrows/edges", e.g.
            "duplicated " when breaking down the duplicated-arrow subset.
        total: When given, the "Nre of {type} arrows" line also shows this
            count's percentage of total. Omitted for the duplicated-arrow
            breakdown, where a percentage isn't meaningful yet.
    """
    buckets: Dict[str, List[WeightRow]] = rows_by_type(rows)
    type_rows: List[WeightRow] = []
    for edge_type in EDGE_TYPES:
        type_rows = buckets[edge_type]
        count_str = (
            f"{len(type_rows)} ({pct(len(type_rows), total)})"
            if total is not None
            else f"{len(type_rows)}"
        )
        print(f"{indent}- Nre of {label_prefix}{edge_type} arrows: {count_str}")
        print(
            f"{indent}    - Nre of {label_prefix}{edge_type} edges: "
            f"{len(unordered_pairs(type_rows))}"
        )


def print_arrow_report(rows: List[WeightRow], duplicated_vertices: Set[str]) -> None:
    """Print the arrow/edge section: total, per-type, then duplicated ones.

    args:
        rows: Every WEIGHTS_FILE row.
        duplicated_vertices: Stop_ids whose incident arrows/edges count as
            duplicated (from EQUIVALENCES_FILE).
    """
    duplicated_rows: List[WeightRow] = [
        row
        for row in rows
        if row["from_stop_id"] in duplicated_vertices
        or row["to_stop_id"] in duplicated_vertices
    ]

    print(f"Nre of arrows: {len(rows)}")
    print(f"    - Nre of edges (unordered pairs): {len(unordered_pairs(rows))}")
    print_type_breakdown(rows, indent="        ", total=len(rows))
    print(
        f"        - Nre of duplicated arrows: {len(duplicated_rows)} "
        f"({pct(len(duplicated_rows), len(rows))})"
    )
    print(
        f"            - Nre of duplicated edges: {len(unordered_pairs(duplicated_rows))}"
    )
    print_type_breakdown(
        duplicated_rows, indent="                ", label_prefix="duplicated "
    )


def print_capacity_report(rows: List[WeightRow], vertices: Set[str]) -> None:
    """Print how many arrows the graph has versus the maximum it could hold.

    A directed simple graph on `|V|` vertices (no self-loops, no parallel
    arrows) allows at most one arrow per ordered pair of distinct vertices,
    i.e. `(|V|-1)*|V|` arrows in total (the directed counterpart of the
    undirected max-edges formula `(|V|-1)*|V|/2`).

    args:
        rows: Every WEIGHTS_FILE row.
        vertices: Every stop_id in WEIGHTS_FILE.
    """
    max_arrows = (len(vertices) - 1) * len(vertices)
    print(
        f"Arrow capacity: {len(rows)} / {max_arrows} possible directed arrows "
        f"(|V|*(|V|-1) with |V|={len(vertices)}) -> {pct(len(rows), max_arrows)}"
    )


def print_disclaimer() -> None:
    """Print the closing reminder explaining vertex/edge vocabulary."""
    print(
        "\nReminder: an entry is a vertex reachable by the user from street "
        "level. To go from an entry to another entry, we may pass through "
        "platform vertices (where the subway train travels).\n"
        "SW edges' weight is the (estimated) time it takes a train to travel "
        "from one platform to another.\n"
        "TF edges' weight is the time to walk from a platform of one line to "
        "a platform of the same stop but another line.\n"
        "PW edges' weight is the time to walk from an entry to a platform of "
        "the same stop, or the reverse.\n"
        "Duplicated is the proxy we used to make each platform belong to "
        "only one line."
    )


def main() -> None:
    """Print vertex/arrow/edge counts for WEIGHTS_FILE, split by kind and duplication."""
    rows: List[WeightRow] = []
    vertices: Set[str] = set()
    duplicated_vertices: Set[str] = set()

    check_missing_files([WEIGHTS_FILE, EQUIVALENCES_FILE])
    print_file_disclaimer([WEIGHTS_FILE, EQUIVALENCES_FILE])

    rows = list(read_dict_rows(WEIGHTS_FILE))
    vertices = collect_vertices(rows)
    duplicated_vertices = (
        load_duplicated_stop_ids(EQUIVALENCES_FILE) & vertices
    )  # Set intersection: keep only new_stop_ids that actually appear in WEIGHTS_FILE

    print_vertex_report(vertices, duplicated_vertices)
    print_arrow_report(rows, duplicated_vertices)
    print_capacity_report(rows, vertices)
    print_disclaimer()


if __name__ == "__main__":
    main()
