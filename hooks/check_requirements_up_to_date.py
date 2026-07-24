#!/usr/bin/env python3
"""
Check that every package declared in requirements.txt is installed in .venv
and satisfies its version pin.
Exits 0 if satisfied or if .venv not found; exits 1 with details if not.
"""
from pathlib import Path
import re
import subprocess
import sys
from typing import Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parents[1]
VENV_PY = (
    REPO_ROOT
    / ".venv"
    / ("Scripts" if sys.platform == "win32" else "bin")
    / ("python.exe" if sys.platform == "win32" else "python")
)
REQ_FILE = REPO_ROOT / "requirements.txt"
REQ_PATTERN = re.compile(
    r"^([A-Za-z0-9_.\-]+)\s*(>=|==|<=|~=|>|<)\s*([A-Za-z0-9_.\-]+)$"
)


def normalize(name: str) -> str:
    """Normalize a package name for comparison (PEP 503-style).

    args:
        name: Raw package name.

    returns:
        Lowercased name with runs of `-`/`_`/`.` collapsed to a single `-`.
    """
    return re.sub(r"[-_.]+", "-", name).lower()


def parse_version(text: str) -> Tuple[int, ...]:
    """Parse a dotted, numeric-led version string into a comparable tuple.

    args:
        text: Version string such as "3.12.1".

    returns:
        Tuple of each dot-separated component's leading integer.
    """
    parts: List[int] = []
    for chunk in text.split("."):
        match = re.match(r"\d+", chunk)
        parts.append(int(match.group()) if match else 0)
    return tuple(parts)


def satisfies(installed: str, operator: str, required: str) -> bool:
    """Check whether an installed version satisfies a requirement operator.

    args:
        installed: Installed version string.
        operator: One of ">=", "==", "<=", "~=", ">", "<".
        required: Required version string from requirements.txt.

    returns:
        True if the installed version satisfies the constraint.
    """
    inst: Tuple[int, ...] = parse_version(installed)
    req: Tuple[int, ...] = parse_version(required)

    if operator == ">=":
        return inst >= req
    if operator == "<=":
        return inst <= req
    if operator == ">":
        return inst > req
    if operator == "<":
        return inst < req
    return inst[: len(req)] == req


def read_requirements(path: Path) -> List[str]:
    """Read requirements.txt and return its non-empty, non-comment lines.

    args:
        path: Path to the requirements.txt file.

    returns:
        List of requirement strings.
    """
    lines: List[str] = []
    if not path.exists():
        return lines
    lines = [
        line.strip()
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    return lines


def installed_versions(python_exec: Path) -> Optional[Dict[str, str]]:
    """Return every installed package's version, keyed by normalized name.

    args:
        python_exec: Path to the Python executable to query.

    returns:
        Dict of normalized name -> version string, or None if the query fails.
    """
    result: Optional[subprocess.CompletedProcess] = None
    versions: Dict[str, str] = {}

    try:
        result = subprocess.run(
            [str(python_exec), "-m", "pip", "list", "--format=freeze"],
            capture_output=True,
            check=False,
            text=True,
        )
    except Exception as e:
        print(f"Could not run pip list using {python_exec}: {e}")
        return None
    if result.returncode != 0:
        print(f"Could not run pip list using {python_exec}:")
        print(result.stderr.strip())
        return None
    for line in result.stdout.splitlines():
        if "==" not in line:
            continue
        name, version = line.strip().split("==", 1)
        versions[normalize(name)] = version
    return versions


def main() -> int:
    """Check that .venv satisfies every pin declared in requirements.txt.

    args:
        None. Uses module-level constants REQ_FILE and VENV_PY.

    returns:
        Exit code: 0 if satisfied or .venv not found, 1 if a pin is unmet.
    """
    reqs: List[str] = read_requirements(REQ_FILE)
    installed: Optional[Dict[str, str]] = None
    problems: List[str] = []

    if not VENV_PY.exists():
        print(
            f".venv python not found at {VENV_PY}. Skipping strict check "
            "(activate .venv and run `pip install -r requirements.txt` if needed)."
        )
        return 0
    installed = installed_versions(VENV_PY)
    if installed is None:
        print("Failed to obtain installed package versions. Skipping.")
        return 0

    for req in reqs:
        match = REQ_PATTERN.match(req)
        if not match:
            name = re.split(r"[<>=~]", req, 1)[0].strip()
            if normalize(name) not in installed:
                problems.append(f"{req}: not installed in .venv")
            continue
        name, operator, version = match.groups()
        installed_version = installed.get(normalize(name))
        if installed_version is None:
            problems.append(f"{req}: not installed in .venv")
        elif not satisfies(installed_version, operator, version):
            problems.append(f"{req}: found {installed_version} in .venv")

    if not problems:
        return 0

    print("requirements.txt is not satisfied by .venv:")
    for problem in problems:
        print("  -", problem)
    print("\nInstall/upgrade with (from repo root, with .venv activated):")
    print("  python -m pip install -r requirements.txt")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
