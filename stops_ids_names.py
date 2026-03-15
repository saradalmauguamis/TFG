import csv
from pathlib import Path
from typing import Dict, Iterable, List


# Script location: <repo>/to change/02.08.py
# GTFS folder:      <repo>/.src/gtfs/data
REPO_ROOT = Path(__file__).resolve().parents[1]
GTFS_DATA_DIR = REPO_ROOT / ".src" / "gtfs" / "data"
STOPS_FILE = GTFS_DATA_DIR / "stops.txt"

LINE_PREFIXES = ["1.1", "1.2", "1.3", "1.4", "1.5", "1.9"]


def sniff_dialect(file_path: Path) -> type[csv.Dialect]:
    """Detect CSV delimiter; default to comma if detection fails."""
    try:
        with file_path.open("r", encoding="utf-8-sig", newline="") as file_handle:
            sample = file_handle.read(65536)
        return csv.Sniffer().sniff(sample, delimiters=",;\t")
    except Exception:
        class _DefaultDialect(csv.Dialect):
            delimiter = ","
            quotechar = '"'
            doublequote = True
            skipinitialspace = False
            lineterminator = "\n"
            quoting = csv.QUOTE_MINIMAL

        return _DefaultDialect


def read_dict_rows(file_path: Path) -> Iterable[Dict[str, str]]:
    """Yield rows as dictionaries with lowercase keys and stripped values."""
    dialect = sniff_dialect(file_path)
    with file_path.open("r", encoding="utf-8-sig", newline="") as file_handle:
        reader = csv.DictReader(file_handle, dialect=dialect)
        if reader.fieldnames is None:
            raise RuntimeError(f"File {file_path.name} has no header.")

        normalized_field_names = {
            name: name.lower().strip() for name in reader.fieldnames
        }

        for row in reader:
            cleaned_row: Dict[str, str] = {}
            for key, value in row.items():
                normalized_key = normalized_field_names.get(key, key).lower()
                normalized_value = (value if value is not None else "").strip()
                cleaned_row[normalized_key] = normalized_value
            yield cleaned_row


def collect_stops_by_prefix(
    stops_file: Path, line_prefixes: List[str]
) -> Dict[str, List[Dict[str, str]]]:
    """Group stop records by the first matching line prefix."""
    stops_by_prefix: Dict[str, List[Dict[str, str]]] = {prefix: [] for prefix in line_prefixes}

    for row in read_dict_rows(stops_file):
        stop_id = row.get("stop_id", "")
        stop_name = row.get("stop_name", "") or "(no name)"

        for prefix in line_prefixes:
            if stop_id.startswith(prefix):
                stops_by_prefix[prefix].append({"stop_id": stop_id, "stop_name": stop_name})
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
