"""Report, for every directed platform-to-platform route, how well an A* heuristic
(routing_algorithms/a_star/a_star_utils.py) actually performs.

Output_name: a_star_geo_report.txt (HEURISTIC_NAME="h_geo") or a_star_h_cheat_report.txt
(HEURISTIC_NAME="h_cheat"), saved into 'routing_algorithms/reports/resources'

This is the evaluation counterpart to a_star_need_report.py
(routing_algorithms/reports/a_star_need_report.py): that report used
cut_dijkstra to show, per pair, how far from ideal (proportion = path_vertices
/ cut_iterations) an uninformed search already is, to find where a heuristic
would help. This report reruns every one of those same pairs, but with A* and
one of the heuristics built in a_star_utils.py (picked via HEURISTIC_NAME), so
the exact same proportion metric can be compared side-by-side against
dijkstra_report.txt to see how much of that theoretical opportunity the
heuristic actually captures.

Columns (in this order):
source_name, target_name, proportion, source_id, target_id, a_star_iterations,
path_vertices, optimum_weight, path

Same meaning as in a_star_need_report.py, except a_star_iterations replaces
cut_iterations: the number of nodes extracted from A*'s Open queue before the
target was reached (a_star_utils.py's a_star, like cut_dijkstra, always stops
as soon as the target is extracted, so proportion = path_vertices /
a_star_iterations is "NA" when no path is found, and rows are sorted
ascending by proportion, NA last, exactly as in a_star_need_report.py).

Methodology:
1. Build the graph from WEIGHTS_FILE with build_graph_from_weights
   (routing_algorithms/algorithms_utils.py), shared with a_star.py.
2. Build h once for the whole run (graph-global, not per-pair) via build_h_geo
   or build_h_cheat, picked by HEURISTIC_NAME, both reused directly from
   a_star_utils.py.
3. Collect every directed pair of distinct platforms via
   collect_platform_pairs (routing_algorithms/reports/report_utils.py), shared
   with a_star_need_report.py.
4. Run a_star(graph, u, v, h, verbose=False) for each pair through
   run_platform_pair_report (routing_algorithms/reports/report_utils.py), which
   builds each row via compute_report_row (reconstructing the path via
   rebuild_path from routing_algorithms/algorithms_utils.py).
5. Sort all rows ascending by proportion, NA last, and write them to
   OUTPUT_PATH.

Note on parallelism: with HEURISTIC_NAME="h_geo", a single a_star call on this
graph takes well under 2ms even for a very long route like E.11101 (Residència
sanitària -- L1-Hospital de Bellvitge) --> to E.14001 (Sicília -- L1-Fondo),
which takes only ~1.7ms (measured empirically), so ~29k directed platform
pairs run in well under a minute single-threaded. Parallelising this one-off
analysis script wouldn't be worth the added complexity, so it is intentionally
left sequential, exactly as in a_star_need_report.py.

With HEURISTIC_NAME="h_cheat", that same route takes ~183ms instead (every
heuristic call triggers a fresh cut_dijkstra), since it is one of the worst
cases geographically; most pairs are far shorter, so the full run over all
29,070 platform pairs took 485.4s (~16.7ms average per pair), measured
empirically. That is still ~100x slower than h_geo's well-under-a-minute run,
but since a given h_cheat run is still only ever generated once (not on a
recurring/interactive basis), an 8-minute one-off cost is not worth adding
parallelism for either.
"""

from __future__ import annotations

import sys
from functools import partial
from pathlib import Path
from typing import Dict, List, Optional, Tuple

_PROJECT_ROOT = str(Path(__file__).resolve().parents[2])
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from scripts.basics import subway_route_names_stop_ids_artificial  # noqa: E402

from data_validation.gtfs_utils import (  # noqa: E402
    STOPS_FILE,
    WEIGHTS_FILE,
    build_stop_to_lines,
    check_missing_files,
    load_stop_names,
    print_file_disclaimer,
)
from routing_algorithms.algorithms_utils import (  # noqa: E402
    NodeFmt,
    build_graph_from_weights,
    stop_label,
)
from routing_algorithms.reports.report_utils import (  # noqa: E402
    ReportRow,
    ReportRunner,
    collect_platform_pairs,
    report_fieldnames,
    run_platform_pair_report,
)
from routing_algorithms.a_star.a_star_utils import (  # noqa: E402
    Coord,
    Graph,
    Heuristic,
    Node,
    a_star,
    build_h_cheat,
    build_h_geo,
    compute_v_max,
    load_node_coords,
)
from routing_algorithms.reports.paths import (  # noqa: E402
    A_STAR_CHEAT_REPORT_FILE,
    A_STAR_GEO_REPORT_FILE,
)

HEURISTIC_NAME = "h_cheat"  # "h_geo" or "h_cheat" to pick the heuristic built in main()
ITERATIONS_LABEL = "a_star_iterations"
OUTPUT_PATH = Path(
    A_STAR_GEO_REPORT_FILE if HEURISTIC_NAME == "h_geo" else A_STAR_CHEAT_REPORT_FILE
)
OUTPUT_NAME = OUTPUT_PATH.name
FIELDNAMES = report_fieldnames(ITERATIONS_LABEL)


def run_a_star(
    graph: Graph, source: Node, target: Node, h: Heuristic
) -> Tuple[Dict[Node, int], Dict[Node, Optional[Node]], int]:
    """Run a_star for one pair, dropping verbose output.

    args:
        graph: A directed, weighted graph.
        source: Platform stop_id to start from.
        target: Platform stop_id to reach.
        h: Admissible heuristic, shared across every pair (build_h_geo or
            build_h_cheat, per HEURISTIC_NAME).

    returns:
        (g, parent, a_star_iterations) for this pair.
    """
    return a_star(graph, source, target, h, verbose=False)


def build_run_a_star(h: Heuristic) -> ReportRunner:
    """Bind h into run_a_star, matching the ReportRunner shape run_platform_pair_report expects.

    args:
        h: Admissible heuristic, shared across every pair (build_h_geo or
            build_h_cheat, per HEURISTIC_NAME).

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
    h: Heuristic
    runner: ReportRunner
    pairs: List[Tuple[Node, Node]]

    stop_names = load_stop_names(STOPS_FILE)
    stop_to_lines = build_stop_to_lines(subway_route_names_stop_ids_artificial)
    node_fmt = partial(stop_label, stop_names=stop_names, stop_to_lines=stop_to_lines)

    graph = build_graph_from_weights(WEIGHTS_FILE)

    coords = load_node_coords(STOPS_FILE)
    v_max, (v_max_from, v_max_to) = compute_v_max(graph, coords)
    print(
        f"v_max (fastest implied edge speed): {v_max:.3f} m/s ({v_max * 3.6:.1f} km/h)"
        f" -- found at edge {v_max_from} ({node_fmt(v_max_from)})"
        f" -> {v_max_to} ({node_fmt(v_max_to)})"
    )
    if HEURISTIC_NAME == "h_geo":
        h = build_h_geo(coords, v_max)
    elif HEURISTIC_NAME == "h_cheat":
        h = build_h_cheat(graph)
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
