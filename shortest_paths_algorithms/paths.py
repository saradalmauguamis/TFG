"""Paths shared across shortest_paths_algorithms/, mirroring the constants section of
data_validation/gtfs_utils.py: a single source of truth so reports/a_star_need_report.py,
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

DIJKSTRA_REPORT_FILE = os.path.join(REPORTS_BASE, "dijkstra_report.txt")
A_STAR_GEO_REPORT_FILE = os.path.join(REPORTS_BASE, "a_star_geo_report.txt")
A_STAR_CHEAT_REPORT_FILE = os.path.join(REPORTS_BASE, "a_star_h_cheat_report.txt")
A_STAR_BCN_REPORT_FILE = os.path.join(REPORTS_BASE, "a_star_h_bcn_report.txt")
ALGORITHMS_COMPARISON_REPORT_FILE = os.path.join(
    str(_ANALYSIS_RESOURCES_DIR), "algorithms_comparison_report.txt"
)
REGIONS_GRAPH_FILE = os.path.join(
    str(_ANALYSIS_RESOURCES_DIR), "barcelona_regions_graph.png"
)
# Directory, not a fixed filename: analysis/extracted_nodes_graph.py names each PNG
# after its own REGION_CASE/SOURCE/TARGET constants, built locally like a_star.py
# and dijkstra.py already do for their own parameterized output filenames.
EXTRACTED_NODES_DIR = os.path.join(str(_ANALYSIS_RESOURCES_DIR), "extracted_nodes")
