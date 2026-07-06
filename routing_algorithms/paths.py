"""Paths shared across routing_algorithms/, mirroring the constants section of
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
ALGORITHMS_COMPARISON_REPORT_FILE = os.path.join(
    str(_ANALYSIS_RESOURCES_DIR), "algorithms_comparison_report.txt"
)
