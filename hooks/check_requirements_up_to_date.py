#!/usr/bin/env python3
"""
Check that .venv pip freeze equals requirements.txt.
Exits 0 if equal or if .venv not found; exits 1 with message if different.
"""
from pathlib import Path
import subprocess
import sys
from typing import List, Optional

REPO_ROOT = Path(__file__).resolve().parents[1]
VENV_PY = (
    REPO_ROOT
    / ".venv"
    / ("Scripts" if sys.platform == "win32" else "bin")
    / ("python.exe" if sys.platform == "win32" else "python")
)
REQ_FILE = REPO_ROOT / "requirements.txt"


def read_requirements(path: Path) -> List[str]:
    """Read `requirements.txt` and return list of non-empty, non-comment lines.

    Tries common encodings and falls back to a permissive decode to avoid
    crashing on BOM or platform-specific encodings.

    args:
        path: Path to the requirements.txt file.

    returns:
        List of package requirement strings (non-empty, non-comment lines).
    """
    lines: List[str] = []
    text: Optional[str] = None
    if not path.exists():
        return []
    # Try common encodings: utf-8, utf-8-sig (BOM), then latin-1 as a fallback.
    for enc in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            text = path.read_text(encoding=enc)
            break
        except UnicodeDecodeError:
            continue
    if text is None:
        # Last resort: open in binary and decode ignoring errors
        try:
            raw = path.read_bytes()
            text = raw.decode("utf-8", errors="ignore")
        except Exception:
            return []

    lines = [
        line.strip()
        for line in text.splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    return lines


def pip_freeze(python_exec: Path) -> Optional[List[str]]:
    """Run pip freeze using the provided Python executable.

    args:
        python_exec: Path to the Python executable to run pip freeze with.

    returns:
        List of package strings from pip freeze output, or None if execution fails.
    """
    try:
        out = subprocess.check_output(
            [str(python_exec), "-m", "pip", "freeze"], stderr=subprocess.STDOUT
        )
        return [
            line.decode("utf-8").strip() for line in out.splitlines() if line.strip()
        ]
    except Exception as e:
        print(f"Could not run pip freeze using {python_exec}: {e}")
        return None


def main() -> int:
    """Check that requirements.txt matches .venv pip freeze.

    args:
        None. Uses module-level constants REQ_FILE and VENV_PY.

    returns:
        Exit code: 0 if requirements match or .venv not found, 1 if mismatch detected.
    """
    frozen = None
    frozen_list: List[str] = []
    set_req: set[str] = set()
    set_frozen: set[str] = set()
    added: List[str] = []
    removed: List[str] = []

    reqs: List[str] = read_requirements(REQ_FILE)
    if not VENV_PY.exists():
        print(
            f".venv python not found at {VENV_PY}. Skipping strict check "
            "(activate .venv and run `pip freeze > requirements.txt` if needed)."
        )
        return 0
    frozen = pip_freeze(VENV_PY)
    if frozen is None:
        print("Failed to obtain pip freeze output. Skipping.")
        return 0
    # frozen is Optional[List[str]]; at this point it's not None
    frozen_list = frozen
    if frozen_list == reqs:
        return 0
    set_req = set(reqs)
    set_frozen = set(frozen_list)
    added = sorted(set_frozen - set_req)
    removed = sorted(set_req - set_frozen)
    print("requirements.txt is OUT OF DATE with .venv pip freeze.")
    if added:
        print("\nPackages present in .venv but missing from requirements.txt:")
        for p in added:
            print("  +", p)
    if removed:
        print("\nPackages present in requirements.txt but not in .venv:")
        for p in removed:
            print("  -", p)
    print("\nUpdate requirements with (from repo root):")
    print("  activate the virtual environment for your OS")
    print("  python -m pip freeze > requirements.txt")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
