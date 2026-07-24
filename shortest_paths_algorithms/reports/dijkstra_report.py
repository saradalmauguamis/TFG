"""Report, for every directed platform-to-platform route, how much a heuristic could help.

Output_name: dijkstra_{full,no_pw}_report.txt (GRAPH_MODE-dependent, see
shortest_paths_algorithms/algorithms_utils.py) saved into
'shortest_paths_algorithms/reports/resources'

Written as a standard comma-separated GTFS-style .txt file so it can be converted to
.xlsx by scripts/from_txt_to_xlsx.py.

Columns (in this order):
source_name, target_name, proportion, source_id, target_id, cut_iterations,
path_vertices, optimum_weight, path

- source_name / target_name: labels for source/target given by the same
  node_fmt (stop_names + line) used in dijkstra.py.
- source_id / target_id: their stop_ids.
- path: output of rebuild_path (shortest_paths_algorithms/algorithms_utils.py), raw
  stop_ids joined by " -> ". "NA" if no path is found.
- path_vertices: len(path). "NA" if no path is found.
- cut_iterations: number of iterations returned by cut_dijkstra
  (shortest_paths_algorithms/dijkstra/dijkstra_utils.py). Always a value (>= 1), even
  when no path is found, since the source itself is always extracted first.
- proportion: path_vertices / cut_iterations. "NA" if no path is found. Always
  <= 1 (see "Aim" below). Rows are ordered ascending by this value, with NA rows last.
- optimum_weight: weight of the path found, in seconds, unformatted. "NA" if
  no path is found.

Aim and objective:
As this graph is pretty small, only a good heuristic can improve Dijkstra. To think
a good heuristic, first we have to analise which situation we have towards us. Instead
of writing a general heuristic, we have to focus on the particular characteristics of
this graph; it should be stressed that this part is the only one not scalable from the
whole pipeline.
The only places where a heuristic can improve Dijkstra is in those routes where we have
considered (extracted) too many vertices compared to the number that finally belong
to the path. That is because the best heuristic is the one that at each vertex returns the
minimal distance until the target. This, obviously, is not an applicable heuristic because if
we knew the shortest path, then we wouldn't need to find any shortest path, it just doesn't
make sense. But this best-case heuristic is useful to understand the difference between
the number of vertices in the path and the number of vertices extracted (VERY IMPORTANT
POINT HERE: what matters to us is the number of vertices expanded, and by Dijkstra's
Convergence Theorem (Alsedà, slide 25) the minimal distance to a vertex is found exactly
once it is extracted, which is equivalent to saying that the number of iterations matches
the number of vertices extracted from the heap (i.e. any vertex is extracted once, and may
be re-added to the heap and later extracted again only if it belongs to a different run).
This best-case heuristic would have the same number of
iterations as vertices in the path. I.e. a proportion near 1 means Dijkstra is being
ultra efficient already, while a low proportion near 0 is where we should focus our
attention to see whether a heuristic could improve Dijkstra there without hurting the
routes that already sit near 1.

Why platforms instead of entrances:
a real user journey goes from an entrance to an entrance, not platform to platform, so
this report is technically a proxy: an entrance-to-entrance path is exactly its
underlying platform-to-platform path with one fixed extra hop bolted onto each end
(entrance -> first platform, last platform -> entrance). That hop shifts path_vertices
and cut_iterations by a small constant, so proportion barely moves, except when
cut_iterations is itself tiny, i.e. exactly where proportion is already near 1.
That is precisely the region we do not need precision in: proportion is computed for
every pair so we can see which pairs sit near 1 (Dijkstra already efficient there)
versus which sit near 0 (where a heuristic is worth designing), but it is only the
low-proportion pairs we actually need to focus on to think about that heuristic, and
there cut_iterations is in the hundreds, where a small constant shift is negligible.
Restricting to platforms is also a large reduction on its own: 502 entries give
251,502 directed entry pairs, versus 171 platforms giving 29,070 directed platform
pairs, an ~8.65x smaller file, far easier to scan and draw conclusions from.

Methodology:
1. Build the graph from WEIGHTS_FILE with build_graph_from_weights
   (shortest_paths_algorithms/algorithms_utils.py), shared with dijkstra.py.
2. Restrict the graph's vertex set to platforms (stop_ids starting with "1.")
   via collect_platform_pairs (shortest_paths_algorithms/reports/report_utils.py).
3. Run cut_dijkstra(graph, u, v, verbose=False) for each pair through
   run_platform_pair_report (shortest_paths_algorithms/reports/report_utils.py), which
   builds each row via compute_report_row (reconstructing the path via
   rebuild_path from shortest_paths_algorithms/algorithms_utils.py).
4. Sort all rows ascending by proportion, NA last, and write them to
   OUTPUT_PATH.

Note on parallelism: a single cut_dijkstra call on this graph takes well under
1ms even for a very long route like E.11101 (Residència sanitària -- L1-Hospital
de Bellvitge) --> to E.14001 (Sicília -- L1-Fondo), which takes only ~0.7ms
(measured empirically), so ~29k directed platform pairs run in well under a
minute single-threaded. Parallelising this one-off analysis script wouldn't be worth
the added complexity, so it is intentionally left sequential.
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
    Node,
    NodeFmt,
    build_graph_from_weights,
    stop_label,
)
from shortest_paths_algorithms.config import GRAPH_MODE  # noqa: E402
from shortest_paths_algorithms.reports.report_utils import (  # noqa: E402
    ReportRow,
    ReportRunner,
    collect_platform_pairs,
    report_fieldnames,
    run_platform_pair_report,
)
from shortest_paths_algorithms.dijkstra.dijkstra_utils import (  # noqa: E402
    Graph,
    cut_dijkstra,
)
from shortest_paths_algorithms.paths import (  # noqa: E402
    DIJKSTRA_REPORT_FULL_FILE,
    DIJKSTRA_REPORT_NO_PW_FILE,
)

ITERATIONS_LABEL = "cut_iterations"
_REPORT_FILE_BY_MODE = {
    FULL_GRAPH: DIJKSTRA_REPORT_FULL_FILE,
    WITHOUT_ENTRANCES_GRAPH: DIJKSTRA_REPORT_NO_PW_FILE,
}
OUTPUT_PATH = Path(_REPORT_FILE_BY_MODE[GRAPH_MODE])
OUTPUT_NAME = OUTPUT_PATH.name
FIELDNAMES = report_fieldnames(ITERATIONS_LABEL)


def run_cut_dijkstra(
    graph: Graph, source: Node, target: Node
) -> Tuple[Dict[Node, int], Dict[Node, Optional[Node]], int]:
    """Run cut_dijkstra for one pair, dropping its 4th (`expanded`) return value.

    Matches the ReportRunner shape run_platform_pair_report expects
    (shortest_paths_algorithms/reports/report_utils.py).

    args:
        graph: A directed, weighted graph.
        source: Platform stop_id to start from.
        target: Platform stop_id to reach.

    returns:
        (dist, parent, cut_iterations) for this pair.
    """
    dist, parent, iterations, _ = cut_dijkstra(graph, source, target, verbose=False)
    return dist, parent, iterations


def main() -> Tuple[List[ReportRow], float]:
    """Compute the platform-to-platform dijkstra report and write it to OUTPUT_NAME.

    returns:
        The sorted report rows, and the total elapsed time (seconds) spent
        running cut_dijkstra over every platform pair.
    """
    graph: Graph
    stop_names: Dict[str, str]
    stop_to_lines: Dict[str, List[str]]
    node_fmt: NodeFmt
    runner: ReportRunner
    pairs: List[Tuple[Node, Node]]

    stop_names = load_stop_names(STOPS_FILE)
    stop_to_lines = build_stop_to_lines(subway_route_names_stop_ids_artificial)
    node_fmt = partial(stop_label, stop_names=stop_names, stop_to_lines=stop_to_lines)

    graph = build_graph_from_weights(WEIGHTS_FILE, GRAPH_MODE)
    pairs = collect_platform_pairs(graph)
    runner = run_cut_dijkstra

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
