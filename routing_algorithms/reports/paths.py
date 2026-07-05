"""Paths for the platform-to-platform comparison reports, mirroring the
constants section of data_validation/gtfs_utils.py: a single source of truth
so a_star_need_report.py, a_star_report.py, and scripts/from_txt_to_xlsx.py
all point at the same files instead of each recomputing the same path.
"""

import os
from pathlib import Path

_DEFAULT_REPORTS_DATA_DIR = Path(__file__).resolve().parent / "resources"
REPORTS_BASE = str(
    Path(
        os.environ.get("ROUTING_REPORTS_DATA_DIR", str(_DEFAULT_REPORTS_DATA_DIR))
    ).resolve()
)

DIJKSTRA_REPORT_FILE = os.path.join(REPORTS_BASE, "dijkstra_report.txt")
A_STAR_REPORT_FILE = os.path.join(REPORTS_BASE, "a_star_report.txt")
