"""Check relationships and invariants around pathways, entrances, and platform connectivity.

Independent of run order (`WORKFLOW.md`): only needs `processing/1_subway.py`
to have run. Validates platform-to-platform pathway/transfer parity, inverse
pathway symmetry, traversal_time agreement and format, traversal_time == 60
for entrance-to-platform pathways, entrance-to-platform coverage, and
same-stop platform transfers. Produces no output file.
"""

from __future__ import annotations

import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List, Set, Tuple

PROJECT_ROOT = Path(__file__).resolve().parents[2]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from subway_reference.subway_lines import subway_route_names_stop_ids  # noqa: E402

from data_validation.gtfs_utils import (  # noqa: E402
    PATHWAYS_RAW_FILE,
    PW_PAIR,
    STOPS_SUBWAY_FILE,
    TRANSFERS_RAW_FILE,
    build_graph_and_coverage,
    build_platform_graph,
    build_stop_to_lines,
    check_missing_files,
    format_stop_label,
    iter_pathway_pairs,
    load_pathway_ids,
    load_platform_pairs_present,
    load_platforms_by_name,
    load_stop_ids,
    load_stop_names,
    load_stops_info,
    load_transfer_pairs_present,
    print_file_disclaimer,
    read_dict_rows,
)


def main() -> None:
    """Validate pathway connectivity, symmetry, traversal times, and platform coverage."""
    pathways_ids: Set[str] = set()
    pathway_platform_pairs: Set[Tuple[str, str]] = set()
    transfer_pairs: Set[Tuple[str, str]] = set()
    missing_pathway_for_transfer: List[Tuple[str, str]] = []
    missing_transfer_for_pathway: List[Tuple[str, str]] = []
    stops_info_with_coords: Dict[str, Tuple[str, str, str]] = {}
    candidate_pids: Set[str] = set()
    missing_inverse: List[Tuple[str, str, str, str]] = []
    traversal_by_pid: Dict[str, str] = {}
    compared_pairs: Set[Tuple[str, str]] = set()
    mismatches: List[Tuple[str, str, str, str]] = []
    missing_reverse_pairs = 0
    total_rows = 0
    valid_pw_rows = 0
    missing_traversal: List[str] = []
    non_numeric: List[Tuple[str, str]] = []
    not_multiple_15: List[Tuple[str, int]] = []
    e_stops_info: Dict[str, Tuple[str, str, str]] = {}
    entrance_to_platforms: Dict[str, Set[str]] = defaultdict(set)
    platform_counts: Counter = Counter()
    missing_entrances: List[str] = []
    stop_ids: Set[str] = set()
    stop_names: Dict[str, str] = {}
    stop_to_lines: Dict[str, List[str]] = {}
    one_stops: List[str] = []
    platform_graph: Dict[str, Set[str]] = {}
    one_to_entries: Dict[str, Set[str]] = {}
    covered_platforms: Set[str] = set()
    missing_platforms: List[str] = []
    name_to_ones: Dict[str, List[str]] = {}
    total_ones = 0
    groups_multi: Dict[str, List[str]] = {}
    missing_pairs: List[Tuple[str, str, str]] = []
    entrance_platform_pairs = 0
    not_60: List[Tuple[str, str]] = []

    check_missing_files([PATHWAYS_RAW_FILE, STOPS_SUBWAY_FILE, TRANSFERS_RAW_FILE])

    print_file_disclaimer(
        [
            (PATHWAYS_RAW_FILE, "pathways"),
            (STOPS_SUBWAY_FILE, "stops"),
            (TRANSFERS_RAW_FILE, "transfers"),
        ]
    )

    pathways_ids = load_pathway_ids(PATHWAYS_RAW_FILE)

    # Check that platform-to-platform pathways ('PW.1.x_1.y') and 'transfers' rows
    # are exactly the same set of (1.*, 1.*) pairs, not just one contained in the other.
    pathway_platform_pairs = load_platform_pairs_present(PATHWAYS_RAW_FILE)
    transfer_pairs = load_transfer_pairs_present(TRANSFERS_RAW_FILE)
    missing_pathway_for_transfer = sorted(transfer_pairs - pathway_platform_pairs)
    missing_transfer_for_pathway = sorted(pathway_platform_pairs - transfer_pairs)

    print("\n----- Platform-to-platform pathways and 'transfers' match exactly? -----")
    print(f"Platform-to-platform pairs in 'pathways': {len(pathway_platform_pairs)}")
    print(f"Pairs in 'transfers': {len(transfer_pairs)}")

    if not missing_pathway_for_transfer and not missing_transfer_for_pathway:
        print(
            "All correct: 'pathways' platform-to-platform pairs and 'transfers'"
            " contain exactly the same pairs."
        )
    else:
        if missing_pathway_for_transfer:
            print(
                f"MISSING {len(missing_pathway_for_transfer)} pathway(s) for transfer pairs"
                " (present in 'transfers' but no 'PW.a_b'/'PW.b_a' pathway):"
            )
            for a, b in missing_pathway_for_transfer:
                print(f"- from_stop_id={a!r}, to_stop_id={b!r}")
        if missing_transfer_for_pathway:
            print(
                f"MISSING {len(missing_transfer_for_pathway)} transfer(s) for pathway pairs"
                " (present in 'pathways' but no row in 'transfers'):"
            )
            for a, b in missing_transfer_for_pathway:
                print(f"- from_stop_id={a!r}, to_stop_id={b!r}")

    stops_info_with_coords = load_stops_info(STOPS_SUBWAY_FILE)
    candidate_pids = {pid for pid in pathways_ids if PW_PAIR.match(pid) is not None}
    missing_inverse = []
    for pid in sorted(candidate_pids):
        m = PW_PAIR.match(pid)
        a, b = m.group("a"), m.group("b")
        reverse_id = f"PW.{b}_{a}"
        if reverse_id not in pathways_ids:
            missing_inverse.append((pid, reverse_id, a, b))

    # Check symmetry in pathways: for each PW.x_y, check that PW.y_x exists.
    # If the inverse is missing, show stop_name and coordinates (lat/lon) for a and b.
    print("\n----- Each pathway 'PW.a_b' has its inverse 'PW.b_a'? -----")
    print(f"Candidates with format 'PW.a_b': {len(candidate_pids)}")
    if not missing_inverse:
        print("All correct: for each pathway 'PW.x_y' there also exists 'PW.y_x'.")
    else:
        print(f"MISSING {len(missing_inverse)} inverse pathways (showing all):")
        for pid, rid, a, b in missing_inverse:
            print(f"- Exists {pid!r} but missing its inverse {rid!r}")
            a_name, a_lat, a_lon = stops_info_with_coords.get(a, ("(no name)", "", ""))
            b_name, b_lat, b_lon = stops_info_with_coords.get(b, ("(no name)", "", ""))
            print(f"  · {a} - {a_name} (lat={a_lat}, lon={a_lon})")
            print(f"  · {b} - {b_name} (lat={b_lat}, lon={b_lon})")

    traversal_by_pid = {}
    for r in read_dict_rows(PATHWAYS_RAW_FILE):
        pid = r.get("pathway_id", "").strip()
        if pid in candidate_pids:
            traversal_by_pid[pid] = r.get("traversal_time", "").strip()

    compared_pairs = set()
    mismatches = []
    for pid, a, b in iter_pathway_pairs(PATHWAYS_RAW_FILE):
        reverse_id = f"PW.{b}_{a}"
        pair_key = tuple(sorted((pid, reverse_id)))
        if pair_key in compared_pairs:
            continue
        compared_pairs.add(pair_key)
        if reverse_id not in traversal_by_pid:
            missing_reverse_pairs += 1
            continue
        t_ab = traversal_by_pid.get(pid, "")
        t_ba = traversal_by_pid[reverse_id]
        if t_ab != t_ba:
            mismatches.append((pid, t_ab, reverse_id, t_ba))

    print("\n----- traversal_time in 'pathways' is the same for both directions? -----")
    print(
        f"Pairs compared (with reverse present): {len(compared_pairs) - missing_reverse_pairs}"
    )
    if missing_reverse_pairs:
        print(
            f"Skipped {missing_reverse_pairs} pairs because reverse pathway is missing."
        )
    if not mismatches:
        print(
            "All correct: traversal_time matches between 'PW.a_b' and 'PW.b_a'"
            " for all comparable pairs."
        )
    else:
        print(f"MISSING equal traversal_time in {len(mismatches)} pathway pairs:")
        for pid, t_ab, reverse_id, t_ba in sorted(mismatches):
            print(
                f"- {pid}: traversal_time={t_ab!r} | {reverse_id}: traversal_time={t_ba!r}"
            )

    total_rows = 0
    valid_pw_rows = 0
    missing_traversal = []
    non_numeric = []
    not_multiple_15 = []
    for r in read_dict_rows(PATHWAYS_RAW_FILE):
        total_rows += 1
        pid = r.get("pathway_id", "").strip()
        if not pid or PW_PAIR.match(pid) is None:
            continue
        valid_pw_rows += 1
        t_raw = r.get("traversal_time", "").strip()
        if not t_raw:
            missing_traversal.append(pid)
            continue
        try:
            t_val = int(t_raw)
        except Exception:
            non_numeric.append((pid, t_raw))
            continue
        if t_val % 15 != 0:
            not_multiple_15.append((pid, t_val))

    print(
        "\n----- traversal_time in 'pathways' is present, numeric,"
        " and multiple of 15 for all PW pathways? -----"
    )
    print(f"Total rows in 'pathways': {total_rows}")
    print(f"Rows with pathway_id format 'PW.a_b': {valid_pw_rows}")
    if not missing_traversal and not non_numeric and not not_multiple_15:
        print(
            "All correct: traversal_time is present, numeric,"
            " and multiple of 15 for all PW pathways."
        )
    else:
        if missing_traversal:
            print(f"MISSING traversal_time in {len(missing_traversal)} pathways:")
            for pid in sorted(missing_traversal):
                print(f"- {pid}")
        if non_numeric:
            print(f"NON-NUMERIC traversal_time in {len(non_numeric)} pathways:")
            for pid, raw in sorted(non_numeric):
                print(f"- {pid}: traversal_time={raw!r}")
        if not_multiple_15:
            print(f"NOT multiple of 15 in {len(not_multiple_15)} pathways:")
            for pid, t_val in sorted(not_multiple_15):
                print(f"- {pid}: traversal_time={t_val}")

    # Check that every entrance-to-platform pathway ('PW.E.xxx_1.yyy' or 'PW.1.yyy_E.xxx')
    # has traversal_time == 60.
    entrance_platform_pairs = 0
    not_60 = []
    for pid in sorted(candidate_pids):
        m = PW_PAIR.match(pid)
        a, b = m.group("a"), m.group("b")
        if (a.startswith("E.") and b.startswith("1.")) or (
            a.startswith("1.") and b.startswith("E.")
        ):
            entrance_platform_pairs += 1
            t_raw = traversal_by_pid.get(pid, "")
            if t_raw != "60":
                not_60.append((pid, t_raw))

    print("\n----- traversal_time is 60 for all entrance-to-platform pathways? -----")
    print(
        "Entrance-to-platform pathways ('PW.E.xxx_1.yyy' or 'PW.1.yyy_E.xxx'):"
        f" {entrance_platform_pairs}"
    )
    if not not_60:
        print(
            "All correct: traversal_time is 60 for all entrance-to-platform pathways."
        )
    else:
        print(f"NOT 60 in {len(not_60)} entrance-to-platform pathways:")
        for pid, t_raw in sorted(not_60):
            print(f"- {pid}: traversal_time={t_raw!r}")

    # Check how many platforms ('1.*') each entrance ('E.*') is connected to.
    # A platform counts as connected if either 'PW.E.xxx_1.yyy' or 'PW.1.yyy_E.xxx'
    # exists (a single direction is enough; symmetry is validated separately above).
    print(
        "\n----- How many platforms is each entrance connected to in 'pathways'? -----"
    )
    e_stops_info = {}
    for r in read_dict_rows(STOPS_SUBWAY_FILE):
        sid = r.get("stop_id", "").strip()
        if not sid or not sid.startswith("E."):
            continue
        e_stops_info[sid] = (
            r.get("stop_name", "").strip(),
            r.get("stop_lat", "").strip(),
            r.get("stop_lon", "").strip(),
        )

    entrance_to_platforms = defaultdict(set)
    for pid in pathways_ids:
        m = PW_PAIR.match(pid)
        if not m:
            continue
        a, b = m.group("a"), m.group("b")
        if a.startswith("E.") and b.startswith("1."):
            entrance_to_platforms[a].add(b)
        elif b.startswith("E.") and a.startswith("1."):
            entrance_to_platforms[b].add(a)

    platform_counts = Counter(
        len(entrance_to_platforms.get(e, set())) for e in e_stops_info
    )
    missing_entrances = [e for e in e_stops_info if not entrance_to_platforms.get(e)]
    print(f"Entrances (E.*): {len(e_stops_info)}")
    print("Distribution of entrances by nre of connected platforms:")
    for nre_platforms, nre_entrances in sorted(platform_counts.items()):
        label = "platform" if nre_platforms == 1 else "platforms"
        print(f"    - {nre_platforms} {label}: {nre_entrances}")

    if not missing_entrances:
        print(
            "All correct: each E.* has at least one pathway"
            " 'PW.E.xxx_1.yyy' or 'PW.1.yyy_E.xxx'."
        )
    else:
        print(
            f"MISSING {len(missing_entrances)} E.* without any pathway to 1.*"
            " (showing all):"
        )
        for e in missing_entrances:
            name, lat, lon = e_stops_info.get(e, ("(no name)", "", ""))
            print(f"- {e} - {name} (lat={lat}, lon={lon})")

    # Check that each stop_id starting with '1.' (platform) has at least one
    # pathway with an entrance 'E.'. That is, look for 'PW.1.xxx_E.yyy' or
    # 'PW.E.yyy_1.xxx' for each '1.xxx'. If one is missing, show the stop_name
    # and suggest a neighboring platform (1.*) with its entrance (E.*) and names,
    # using 'transfers' (rather than re-deriving platform-platform pairs from
    # 'pathways') since the check above already guarantees they're the same pairs.
    print("\n----- Each platform is connected to an entrance in 'pathways'? -----")
    stop_ids = load_stop_ids(STOPS_SUBWAY_FILE)
    stop_names = load_stop_names(STOPS_SUBWAY_FILE)
    stop_to_lines = build_stop_to_lines(subway_route_names_stop_ids)
    one_stops = [s for s in stop_ids if s.startswith("1.")]
    platform_graph = build_platform_graph(transfer_pairs)
    one_to_entries, covered_platforms = build_graph_and_coverage(pathways_ids)
    missing_platforms = [s for s in one_stops if s not in covered_platforms]
    print(f"Total stops: {len(stop_ids)}")
    print(f"Platforms (1.*): {len(one_stops)}")
    print(
        f"Platforms with at least one pathway to an entrance (E.*): {len(covered_platforms)}"
    )
    if not missing_platforms:
        print(
            "All correct: each 1.* has at least one pathway"
            " 'PW.1.xxx_E.yyy' or 'PW.E.yyy_1.xxx'."
        )
    else:
        print(
            f"MISSING {len(missing_platforms)} platforms without any pathway to any entrance"
            " (showing all):"
        )
        for s in missing_platforms:
            nom = stop_names.get(s, "(no name)")
            print(f"- {s} - {format_stop_label(s, nom, stop_to_lines)}")
            sugg = [
                n
                for n in sorted(platform_graph.get(s, set()))
                if n in one_to_entries and one_to_entries[n]
            ]
            if sugg:
                print("    Connected to platforms that do have at least one entrance:")
                for n in sugg:
                    n_nom = stop_names.get(n, "(no name)")
                    entries = sorted(one_to_entries[n])
                    e = entries[0]
                    e_nom = stop_names.get(e, "(no name)")
                    print(
                        f"    · {n} - {format_stop_label(n, n_nom, stop_to_lines)}"
                        f" -> entrance {e} - {e_nom}"
                    )
            else:
                print(
                    "    (Not connected to any platform 1.* that has an entrance E.*)"
                )

    # Check that all platforms (1.*) with the same stop_name have transfers between each pair.
    # Example: if 1.339, 1.434 and 1.1136 exist with the same name, transfers are needed between
    # each pair (we only check one direction per pair; reciprocity is already validated above).
    # Uses 'transfers' as the source of platform-to-platform pairs, same reasoning as above.
    print(
        "\n----- There is a transfer between each pair of platforms of the same stop"
        " in 'transfers'? -----"
    )
    name_to_ones = load_platforms_by_name(STOPS_SUBWAY_FILE)
    total_ones = sum(len(v) for v in name_to_ones.values())
    groups_multi = {name: ids for name, ids in name_to_ones.items() if len(ids) >= 2}
    print(f"Total platforms (1.*): {total_ones}")
    print(f"Stops with multiple platforms (same name): {len(groups_multi)}")
    missing_pairs = []
    for name, ids in sorted(groups_multi.items()):
        for u, v in [
            (a, b) for i, a in enumerate(sorted(ids)) for b in sorted(ids)[i + 1 :]
        ]:
            if (u, v) not in transfer_pairs:
                missing_pairs.append((name, u, v))
    if not missing_pairs:
        print(
            "All correct: for each stop with multiple platforms,"
            " there are transfers between all platform pairs."
        )
    else:
        print(
            f"MISSING transfers between {len(missing_pairs)} platform pairs"
            " within the same stop (showing all):"
        )
        for name, u, v in missing_pairs:
            print(f"- {name}: missing transfer between {u} and {v}")


if __name__ == "__main__":
    raise SystemExit(main())
