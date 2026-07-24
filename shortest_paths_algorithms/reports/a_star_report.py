"""Report, for every directed platform-to-platform route, how well an A* heuristic
(shortest_paths_algorithms/a_star/a_star_utils.py) actually performs.

Output_name: a_star_{full,no_pw}_geo_report.txt (HEURISTIC_NAME="h_geo"),
a_star_{full,no_pw}_h_cheat_report.txt (HEURISTIC_NAME="h_cheat"), or
a_star_{full,no_pw}_h_bcn_report.txt (HEURISTIC_NAME="h_bcn"), with the full/no_pw
half picked by GRAPH_MODE (see shortest_paths_algorithms/algorithms_utils.py),
saved into 'shortest_paths_algorithms/reports/resources'

This is the evaluation counterpart to dijkstra_report.py
(shortest_paths_algorithms/reports/dijkstra_report.py): that report used
cut_dijkstra to show, per pair, how far from ideal (proportion = path_vertices
/ cut_iterations) an uninformed search already is, to find where a heuristic
would help. This report reruns every one of those same pairs, but with A* and
one of the heuristics built in shortest_paths_algorithms/a_star/heuristics/ (picked
via HEURISTIC_NAME), so
the exact same proportion metric can be compared side-by-side against
dijkstra_report.txt to see how much of that theoretical opportunity the
heuristic actually captures.

Columns (in this order):
source_name, target_name, proportion, source_id, target_id, a_star_iterations,
path_vertices, optimum_weight, path

Same meaning as in dijkstra_report.py, except a_star_iterations replaces
cut_iterations: the number of nodes extracted from A*'s Open queue before the
target was reached (a_star_utils.py's a_star, like cut_dijkstra, always stops
as soon as the target is extracted, so proportion = path_vertices /
a_star_iterations is "NA" when no path is found, and rows are sorted
ascending by proportion, NA last, exactly as in dijkstra_report.py).

Methodology:
1. Build the graph from WEIGHTS_FILE with build_graph_from_weights
   (shortest_paths_algorithms/algorithms_utils.py), shared with a_star.py.
2. Build h once for the whole run (graph-global, not per-pair) via build_h_geo,
   build_h_cheat, or build_h_bcn, picked by HEURISTIC_NAME, all reused directly
   from shortest_paths_algorithms/a_star/heuristics/.
3. Collect every directed pair of distinct platforms via
   collect_platform_pairs (shortest_paths_algorithms/reports/report_utils.py), shared
   with dijkstra_report.py.
4. Run a_star(graph, u, v, h, verbose=False) for each pair through
   run_platform_pair_report (shortest_paths_algorithms/reports/report_utils.py), which
   builds each row via compute_report_row (reconstructing the path via
   rebuild_path from shortest_paths_algorithms/algorithms_utils.py).
5. Sort all rows ascending by proportion, NA last, and write them to
   OUTPUT_PATH.

Note on parallelism: none of the three heuristics need it. Measured
empirically on a very long route (E.11101, Residència sanitària -- L1-Hospital
de Bellvitge, to E.14001, Sicília -- L1-Fondo, one of the worst cases
geographically): a single a_star call takes ~1.7ms with HEURISTIC_NAME="h_geo",
~3ms with "h_bcn" (still pure arithmetic and dict lookups, no shortest-path
solve), and ~183ms with "h_cheat" (every call triggers a fresh cut_dijkstra).
Across all 29,070 directed platform pairs, that's well under a minute for
h_geo, 11.8s for h_bcn, and 485.4s (~16.7ms average per pair) for h_cheat;
even that worst case is only an 8-minute one-off cost, not worth adding
parallelism for, so this script is intentionally left sequential, exactly as
in dijkstra_report.py. Those h_cheat figures were themselves measured with
GRAPH_MODE=FULL_GRAPH, the worst case for it (entrances included means a
larger graph for every internal cut_dijkstra call), so the same conclusion
holds a fortiori on WITHOUT_ENTRANCES_GRAPH, where h_cheat's cut_dijkstra
calls run over a smaller graph and so are only faster.
"""

from __future__ import annotations

import sys
from functools import partial
from pathlib import Path
from typing import Dict, List, Optional, Tuple

_PROJECT_ROOT = str(Path(__file__).resolve().parents[2])
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from subway_reference.subway_lines import (  # noqa: E402
    subway_route_names_stop_ids_artificial,
)

from data_validation.gtfs_utils import (  # noqa: E402
    STOPS_FILE,
    WEIGHTS_FILE,
    build_stop_to_lines,
    check_missing_files,
    load_stop_names,
    print_file_disclaimer,
)
from shortest_paths_algorithms.algorithms_utils import (  # noqa: E402
    FULL_GRAPH,
    WITHOUT_ENTRANCES_GRAPH,
    NodeFmt,
    build_graph_from_weights,
    stop_label,
)
from shortest_paths_algorithms.config import (  # noqa: E402
    GRAPH_MODE,
    HEURISTIC_NAME,
)
from shortest_paths_algorithms.reports.report_utils import (  # noqa: E402
    ReportRow,
    ReportRunner,
    collect_platform_pairs,
    report_fieldnames,
    run_platform_pair_report,
)
from shortest_paths_algorithms.a_star.a_star_utils import (  # noqa: E402
    H_BCN,
    H_CHEAT,
    H_GEO,
    Graph,
    Heuristic,
    Node,
    a_star,
)
from shortest_paths_algorithms.a_star.heuristics.h_geo import (  # noqa: E402
    Coord,
    build_h_geo,
    compute_v_max,
    load_node_coords,
)
from shortest_paths_algorithms.a_star.heuristics.h_cheat import (  # noqa: E402
    build_h_cheat,
)
from shortest_paths_algorithms.a_star.heuristics.h_bcn import (  # noqa: E402
    DepthTable,
    build_depth_tables,
    build_h_bcn,
)
from shortest_paths_algorithms.paths import (  # noqa: E402
    A_STAR_BCN_REPORT_FULL_FILE,
    A_STAR_BCN_REPORT_NO_PW_FILE,
    A_STAR_CHEAT_REPORT_FULL_FILE,
    A_STAR_CHEAT_REPORT_NO_PW_FILE,
    A_STAR_GEO_REPORT_FULL_FILE,
    A_STAR_GEO_REPORT_NO_PW_FILE,
)

ITERATIONS_LABEL = "a_star_iterations"
_REPORT_FILE_BY_HEURISTIC_AND_MODE = {
    (H_GEO, FULL_GRAPH): A_STAR_GEO_REPORT_FULL_FILE,
    (H_GEO, WITHOUT_ENTRANCES_GRAPH): A_STAR_GEO_REPORT_NO_PW_FILE,
    (H_CHEAT, FULL_GRAPH): A_STAR_CHEAT_REPORT_FULL_FILE,
    (H_CHEAT, WITHOUT_ENTRANCES_GRAPH): A_STAR_CHEAT_REPORT_NO_PW_FILE,
    (H_BCN, FULL_GRAPH): A_STAR_BCN_REPORT_FULL_FILE,
    (H_BCN, WITHOUT_ENTRANCES_GRAPH): A_STAR_BCN_REPORT_NO_PW_FILE,
}
OUTPUT_PATH = Path(_REPORT_FILE_BY_HEURISTIC_AND_MODE[(HEURISTIC_NAME, GRAPH_MODE)])
OUTPUT_NAME = OUTPUT_PATH.name
FIELDNAMES = report_fieldnames(ITERATIONS_LABEL)


def run_a_star(
    graph: Graph, source: Node, target: Node, h: Heuristic
) -> Tuple[Dict[Node, int], Dict[Node, Optional[Node]], int]:
    """Run a_star for one pair, dropping verbose output and its 4th (`expanded`) return value.

    Matches the ReportRunner shape run_platform_pair_report expects
    (shortest_paths_algorithms/reports/report_utils.py), same as dijkstra_report.py's
    run_cut_dijkstra drops cut_dijkstra's own `expanded` value.

    args:
        graph: A directed, weighted graph.
        source: Platform stop_id to start from.
        target: Platform stop_id to reach.
        h: Admissible heuristic, shared across every pair (build_h_geo,
            build_h_cheat, or build_h_bcn, per HEURISTIC_NAME).

    returns:
        (g, parent, a_star_iterations) for this pair.
    """
    g, parent, iterations, _ = a_star(graph, source, target, h, verbose=False)
    return g, parent, iterations


def build_run_a_star(h: Heuristic) -> ReportRunner:
    """Bind h into run_a_star, matching the ReportRunner shape run_platform_pair_report expects.

    args:
        h: Admissible heuristic, shared across every pair (build_h_geo,
            build_h_cheat, or build_h_bcn, per HEURISTIC_NAME).

    returns:
        run_a_star with h pre-bound, i.e. Callable(graph, source, target) ->
        (g, parent, a_star_iterations).
    """
    return partial(run_a_star, h=h)


def main() -> Tuple[List[ReportRow], float]:
    """Compute the platform-to-platform A* report and write it to OUTPUT_NAME.

    returns:
        The sorted report rows, and the total elapsed time (seconds) spent
        running a_star over every platform pair.
    """
    graph: Graph
    stop_names: Dict[str, str]
    stop_to_lines: Dict[str, List[str]]
    node_fmt: NodeFmt
    coords: Dict[Node, Coord]
    v_max: float
    v_max_from: Node
    v_max_to: Node
    depth_from: DepthTable
    depth_to: DepthTable
    h: Heuristic
    runner: ReportRunner
    pairs: List[Tuple[Node, Node]]

    stop_names = load_stop_names(STOPS_FILE)
    stop_to_lines = build_stop_to_lines(subway_route_names_stop_ids_artificial)
    node_fmt = partial(stop_label, stop_names=stop_names, stop_to_lines=stop_to_lines)

    graph = build_graph_from_weights(WEIGHTS_FILE, GRAPH_MODE)

    if HEURISTIC_NAME == H_CHEAT:
        # h_cheat only needs graph; coords/v_max are geography-only inputs
        # h_geo/h_bcn need, so skip computing them entirely for this heuristic.
        h = build_h_cheat(graph)
    else:
        coords = load_node_coords(STOPS_FILE)
        v_max, (v_max_from, v_max_to) = compute_v_max(graph, coords)
        print(
            f"v_max (fastest implied edge speed): {v_max:.3f} m/s ({v_max * 3.6:.1f} km/h)"
            f" -- found at edge {v_max_from} ({node_fmt(v_max_from)})"
            f" -> {v_max_to} ({node_fmt(v_max_to)})"
        )
        if HEURISTIC_NAME == H_GEO:
            h = build_h_geo(coords, v_max)
        elif HEURISTIC_NAME == H_BCN:
            depth_from, depth_to = build_depth_tables(graph)
            h = build_h_bcn(WEIGHTS_FILE, coords, v_max, depth_from, depth_to)
        else:
            raise ValueError(f"Unknown HEURISTIC_NAME: {HEURISTIC_NAME!r}")
    runner = build_run_a_star(h)

    pairs = collect_platform_pairs(graph)

    return run_platform_pair_report(
        graph, pairs, node_fmt, runner, OUTPUT_PATH, FIELDNAMES, ITERATIONS_LABEL
    )


if __name__ == "__main__":
    check_missing_files([WEIGHTS_FILE, STOPS_FILE])
    print_file_disclaimer([WEIGHTS_FILE, STOPS_FILE])

    print(f"Starting {OUTPUT_NAME} generation...")
    report_rows, elapsed_seconds = main()
    print(
        f"{OUTPUT_PATH.name} generated into"
        f" {OUTPUT_PATH.relative_to(_PROJECT_ROOT)} with {len(report_rows)} rows"
        f" (took {elapsed_seconds:.1f}s)"
    )
