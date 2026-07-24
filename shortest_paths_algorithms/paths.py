"""Paths shared across shortest_paths_algorithms/, mirroring the constants section of
data_validation/gtfs_utils.py: a single source of truth so reports/dijkstra_report.py,
reports/a_star_report.py, analysis/algorithms_comparison.py, and
scripts/from_txt_to_xlsx.py all point at the same files instead of each
recomputing the same path.
"""

import os
from pathlib import Path

_DEFAULT_REPORTS_DATA_DIR = Path(__file__).resolve().parent / "reports" / "resources"
REPORTS_BASE = str(
    Path(
        os.environ.get("ROUTING_REPORTS_DATA_DIR", str(_DEFAULT_REPORTS_DATA_DIR))
    ).resolve()
)
_ANALYSIS_RESOURCES_DIR = Path(__file__).resolve().parent / "analysis" / "resources"

# Each report is generated once per graph mode (FULL_GRAPH or
# WITHOUT_ENTRANCES_GRAPH, see shortest_paths_algorithms/algorithms_utils.py),
# so every report file below comes in a "full"/"no_pw" pair.
DIJKSTRA_REPORT_FULL_FILE = os.path.join(REPORTS_BASE, "dijkstra_full_report.txt")
DIJKSTRA_REPORT_NO_PW_FILE = os.path.join(REPORTS_BASE, "dijkstra_no_pw_report.txt")
A_STAR_GEO_REPORT_FULL_FILE = os.path.join(REPORTS_BASE, "a_star_full_geo_report.txt")
A_STAR_GEO_REPORT_NO_PW_FILE = os.path.join(REPORTS_BASE, "a_star_no_pw_geo_report.txt")
A_STAR_CHEAT_REPORT_FULL_FILE = os.path.join(
    REPORTS_BASE, "a_star_full_h_cheat_report.txt"
)
A_STAR_CHEAT_REPORT_NO_PW_FILE = os.path.join(
    REPORTS_BASE, "a_star_no_pw_h_cheat_report.txt"
)
A_STAR_BCN_REPORT_FULL_FILE = os.path.join(REPORTS_BASE, "a_star_full_h_bcn_report.txt")
A_STAR_BCN_REPORT_NO_PW_FILE = os.path.join(
    REPORTS_BASE, "a_star_no_pw_h_bcn_report.txt"
)
# algorithms_comparison.py builds two variants: FULL_FILE aggregates only the
# full-graph reports, COMBINED_FILE aggregates full and no_pw side by side
# (see its HEURISTIC_REPORTS_BY_MODE), not a "full"/"no_pw" pair like the
# per-heuristic reports above, since COMBINED_FILE contains both at once.
ALGORITHMS_COMPARISON_REPORT_FULL_FILE = os.path.join(
    str(_ANALYSIS_RESOURCES_DIR), "algorithms_comparison_full_report.txt"
)
ALGORITHMS_COMPARISON_REPORT_COMBINED_FILE = os.path.join(
    str(_ANALYSIS_RESOURCES_DIR), "algorithms_comparison_combined_report.txt"
)
REGIONS_GRAPH_FILE = os.path.join(
    str(_ANALYSIS_RESOURCES_DIR), "barcelona_regions_graph.png"
)
# Directory, not a fixed filename: analysis/extracted_nodes_graph.py names each PNG
# after its own REGION_CASE/SOURCE/TARGET constants, built locally like a_star.py
# and dijkstra.py already do for their own parameterized output filenames.
EXTRACTED_NODES_DIR = os.path.join(str(_ANALYSIS_RESOURCES_DIR), "extracted_nodes")
