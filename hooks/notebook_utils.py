"""Utilities for extracting Python source from Jupyter notebook cells."""

import json
from typing import List, Tuple


def extract_notebook_code_cells(filename: str) -> List[Tuple[int, str]]:
    """Extract source code from each code cell in a Jupyter notebook.

    args:
        filename: Path to the .ipynb file.

    returns:
        List of (cell_position, source_string) tuples for non-empty code cells,
        where cell_position is the 1-based global cell index in the notebook.
    """
    cells = []
    with open(filename, "r", encoding="utf-8") as f:
        notebook = json.load(f)
    for i, cell in enumerate(notebook.get("cells", []), start=1):
        if cell.get("cell_type") != "code":
            continue
        source = "".join(cell.get("source", []))
        if source.strip():
            cells.append((i, source))

    return cells
