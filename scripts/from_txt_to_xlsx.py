"""Convert GTFS `.txt` files to `.xlsx`.

Reads GTFS `.txt` files from `DATA_DIR` (a pipeline stage folder under
`data/`, configurable via the `GTFS_DATA_DIR` env var read by
`data_validation.gtfs_utils`) and exports them to `data/excel_exports`:
one `.xlsx` file per `.txt` table, plus a combined workbook with one sheet per
table. Large tables are split across multiple files/sheets to stay within
Excel's row limit.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path
from typing import List, Optional, Set

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from data_validation.gtfs_utils import BASE, check_missing_files  # noqa: E402
from routing_algorithms.reports.paths import REPORTS_BASE  # noqa: E402

# DATA_DIR defaults to the platform-to-platform reports; point it at any
# other `_DEFAULT_*_DATA_DIR` constant from data_validation.gtfs_utils (e.g.
# `_DEFAULT_RAW_DATA_DIR`, `_DEFAULT_SUBWAY_DATA_DIR`) to convert that stage
# instead, or at any other folder of comma-separated .txt files.
DATA_DIR = Path(REPORTS_BASE)

# Set this to a filename like 'trips.txt' to convert only one file.
# Set it to None to convert every .txt file in DATA_DIR.
TXT_FILE_NAME: Optional[str] = "dijkstra_report.txt"

# Excel limits one sheet to 1,048,576 rows total, including the header.
EXCEL_MAX_ROWS = 800_000
EXCEL_MAX_DATA_ROWS = EXCEL_MAX_ROWS - 1

# True writes .xlsx exports next to the source .txt (DATA_DIR/excel_exports,
# e.g. routing_algorithms/reports/resources/excel_exports); False writes them
# to the shared data/excel_exports folder alongside every other pipeline
# stage's exports.
EXPORT_NEXT_TO_SOURCE: bool = False

OUTPUT_DIR = (DATA_DIR if EXPORT_NEXT_TO_SOURCE else Path(BASE)) / "excel_exports"


def get_txt_files(data_dir: Path, txt_file_name: Optional[str]) -> List[Path]:
    """Return the list of .txt files to convert from data_dir.

    args:
        data_dir: Folder to look for .txt files in.
        txt_file_name: A single filename to convert, or None for all .txt files.

    returns:
        List of Path objects for the .txt files to process.
    """
    selected_file: Path
    all_txt_files = sorted(data_dir.glob("*.txt"))

    if not all_txt_files:
        raise FileNotFoundError(
            f"No .txt files were found in {data_dir}. "
            "Set GTFS_DATA_DIR if your data is in a different location."
        )

    if txt_file_name is None:
        return all_txt_files

    selected_file = (data_dir / txt_file_name).resolve()
    check_missing_files([str(selected_file)])
    return [selected_file]


def read_txt_table(file_path: Path) -> pd.DataFrame:
    """Read a GTFS TXT file using a robust fallback for encoding.

    args:
        file_path: Path to the .txt file to read.

    returns:
        DataFrame with the file contents.
    """
    try:
        return pd.read_csv(file_path, low_memory=False)
    except UnicodeDecodeError:
        return pd.read_csv(file_path, low_memory=False, encoding="latin1")


def write_excel_with_auto_split(df: pd.DataFrame, output_file: Path) -> List[Path]:
    """Write a DataFrame to Excel, splitting into multiple files if the row limit is exceeded.

    args:
        df: DataFrame to write.
        output_file: Target output .xlsx file path.

    returns:
        List of paths to the created output files.
    """
    output_files: List[Path] = []
    total_parts: int
    part_index: int
    start_row: int
    end_row: int
    part_df: pd.DataFrame
    part_file: Path

    if len(df) <= EXCEL_MAX_DATA_ROWS:
        df.to_excel(output_file, index=False)
        return [output_file]

    total_parts = math.ceil(len(df) / EXCEL_MAX_DATA_ROWS)
    for part_index in range(total_parts):
        start_row = part_index * EXCEL_MAX_DATA_ROWS
        end_row = start_row + EXCEL_MAX_DATA_ROWS
        part_df = df.iloc[start_row:end_row]
        part_file = output_file.with_name(
            f"{output_file.stem}_part{part_index + 1}{output_file.suffix}"
        )
        part_df.to_excel(part_file, index=False)
        output_files.append(part_file)

    return output_files


def convert_individual_files(txt_files: List[Path], output_dir: Path) -> pd.DataFrame:
    """Convert each .txt file to its own .xlsx file(s), printing progress.

    args:
        txt_files: .txt files to convert.
        output_dir: Folder to write the .xlsx file(s) into.

    returns:
        Summary DataFrame with one row per input file: input_txt, output_xlsx,
        rows, columns.
    """
    conversion_log: List[tuple] = []
    df: pd.DataFrame
    output_file: Path
    output_files: List[Path]

    for txt_file in txt_files:
        df = read_txt_table(txt_file)
        output_file = output_dir / f"{txt_file.stem}.xlsx"
        output_files = write_excel_with_auto_split(df, output_file)

        conversion_log.append(
            (
                txt_file.name,
                ", ".join(path.name for path in output_files),
                len(df),
                len(df.columns),
            )
        )
        print(
            f"Converted {txt_file.name} -> {', '.join(path.name for path in output_files)}"
        )

    return pd.DataFrame(
        conversion_log,
        columns=["input_txt", "output_xlsx", "rows", "columns"],
    )


def excel_sheet_name(base_name: str, used_names: Set[str]) -> str:
    """Create a valid, unique Excel sheet name (max 31 chars).

    args:
        base_name: Proposed name for the sheet.
        used_names: Set of sheet names already in use, modified in place.

    returns:
        A valid, unique Excel sheet name of at most 31 characters.
    """
    cleaned: str
    candidate: str
    counter: int
    suffix: str

    cleaned = base_name.replace("/", "_").replace("\\", "_").replace("*", "_")
    cleaned = (
        cleaned.replace("?", "_").replace("[", "_").replace("]", "_").replace(":", "_")
    )
    cleaned = cleaned[:31] if cleaned else "Sheet"

    candidate = cleaned
    counter = 1
    while candidate in used_names:
        suffix = f"_{counter}"
        candidate = f"{cleaned[:31 - len(suffix)]}{suffix}"
        counter += 1

    used_names.add(candidate)
    return candidate


def add_dataframe_to_writer(
    writer: pd.ExcelWriter,
    df: pd.DataFrame,
    base_name: str,
    used_sheet_names: Set[str],
) -> List[str]:
    """Write a DataFrame to one or more sheets when the Excel row limit is exceeded.

    args:
        writer: Open ExcelWriter to write sheets into.
        df: DataFrame to write.
        base_name: Base name for the sheet(s).
        used_sheet_names: Set of already-used sheet names, modified in place.

    returns:
        List of sheet names created.
    """
    total_parts: int
    sheet_names: List[str] = []
    sheet_name: str
    part_index: int
    start_row: int
    end_row: int
    part_df: pd.DataFrame
    part_base_name: str

    if len(df) <= EXCEL_MAX_DATA_ROWS:
        sheet_name = excel_sheet_name(base_name, used_sheet_names)
        df.to_excel(writer, sheet_name=sheet_name, index=False)
        return [sheet_name]

    total_parts = math.ceil(len(df) / EXCEL_MAX_DATA_ROWS)
    for part_index in range(total_parts):
        start_row = part_index * EXCEL_MAX_DATA_ROWS
        end_row = start_row + EXCEL_MAX_DATA_ROWS
        part_df = df.iloc[start_row:end_row]
        part_base_name = f"{base_name}_part{part_index + 1}"
        sheet_name = excel_sheet_name(part_base_name, used_sheet_names)
        part_df.to_excel(writer, sheet_name=sheet_name, index=False)
        sheet_names.append(sheet_name)

    return sheet_names


def build_combined_workbook(txt_files: List[Path], combined_file: Path) -> None:
    """Write every .txt file as one sheet each into a single combined workbook.

    args:
        txt_files: .txt files to include.
        combined_file: Target output .xlsx file path.
    """
    used_sheet_names: Set[str] = set()
    df: pd.DataFrame
    sheet_names: List[str]

    with pd.ExcelWriter(combined_file, engine="openpyxl") as writer:
        for txt_file in txt_files:
            df = read_txt_table(txt_file)
            sheet_names = add_dataframe_to_writer(
                writer, df, txt_file.stem, used_sheet_names
            )
            print(f"Added {txt_file.name} as: {', '.join(sheet_names)}")

    print(f"Combined workbook created: {combined_file}")


def main() -> None:
    """Convert configured GTFS .txt file(s) to individual and combined .xlsx workbooks."""
    txt_files: List[Path]
    summary_df: pd.DataFrame
    combined_file: Path

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    txt_files = get_txt_files(DATA_DIR, TXT_FILE_NAME)

    print(f"Input folder: {DATA_DIR}")
    print(f"Output folder: {OUTPUT_DIR}")
    print(
        f"Conversion mode: {'all .txt files' if TXT_FILE_NAME is None else 'single file'}"
    )
    for file_path in txt_files:
        print(f" - {file_path.name}")

    summary_df = convert_individual_files(txt_files, OUTPUT_DIR)
    print(summary_df.to_string(index=False))

    combined_file = OUTPUT_DIR / "gtfs_all_tables.xlsx"
    build_combined_workbook(txt_files, combined_file)


if __name__ == "__main__":
    raise SystemExit(main())
