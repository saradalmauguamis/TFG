"""Loads shortest_paths_algorithms/config.yaml once and exposes its values, so
dijkstra.py, a_star.py, extracted_nodes_graph.py, and the reports/ scripts all
read SOURCE/TARGET/GRAPH_MODE/HEURISTIC_NAME from the same place instead of
each hardcoding its own copy. Mirrors paths.py's role for file paths.
"""

from __future__ import annotations
from pathlib import Path
from typing import Any, Dict

import yaml

_CONFIG_PATH = Path(__file__).resolve().parent / "config.yaml"
with open(_CONFIG_PATH, "r", encoding="utf-8") as _f:
    _CONFIG: Dict[str, Any] = yaml.safe_load(_f)

SOURCE: str = _CONFIG["source"]
TARGET: str = _CONFIG["target"]
GRAPH_MODE: str = _CONFIG["graph_mode"]
HEURISTIC_NAME: str = _CONFIG["heuristic_name"]
