from pathlib import Path
from typing import Dict, List

try:
    from scripts.utils import read_dict_rows
except ModuleNotFoundError:
    from utils import read_dict_rows


# Script location: <repo>/scripts/stops_ids_names.py
# GTFS folder:      <repo>/.src/gtfs/data
REPO_ROOT = Path(__file__).resolve().parents[1]
GTFS_DATA_DIR = REPO_ROOT / ".src" / "gtfs" / "data"
STOPS_FILE = GTFS_DATA_DIR / "stops.txt"

LINE_PREFIXES = ["1.1", "1.2", "1.3", "1.4", "1.5", "1.9"]


def collect_stops_by_prefix(
    stops_file: Path, line_prefixes: List[str]
) -> Dict[str, List[Dict[str, str]]]:
    """Group stop records by the first matching line prefix."""
    stops_by_prefix: Dict[str, List[Dict[str, str]]] = {
        prefix: [] for prefix in line_prefixes
    }

    for row in read_dict_rows(stops_file):
        stop_id = row.get("stop_id", "")
        stop_name = row.get("stop_name", "").strip()

        for prefix in line_prefixes:
            if stop_id.startswith(prefix):
                stops_by_prefix[prefix].append(
                    {"stop_id": stop_id, "stop_name": stop_name}
                )
                break

    return stops_by_prefix


def main() -> None:
    if not STOPS_FILE.exists():
        print("File not found:", STOPS_FILE)
        return

    print("Using STOPS file:", STOPS_FILE)
    grouped_stops = collect_stops_by_prefix(STOPS_FILE, LINE_PREFIXES)

    for prefix in LINE_PREFIXES:
        line_number = prefix.split(".")[-1]
        print(f"\nLínia {line_number}")

        sorted_items = sorted(grouped_stops[prefix], key=lambda item: item["stop_id"])
        if not sorted_items:
            print("(No results)")
            continue

        for item in sorted_items:
            print(f"{item['stop_id']} - {item['stop_name']}")


if __name__ == "__main__":
    main()
