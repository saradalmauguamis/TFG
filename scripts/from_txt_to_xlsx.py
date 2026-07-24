"""Convert GTFS `.txt` files to `.xlsx`.

Reads GTFS `.txt` files from `INPUT_DIR` and exports them to `OUTPUT_DIR`:
one `.xlsx` file per `.txt` table. Large tables are split across multiple
files to stay within Excel's row limit.
"""

from __future__ import annotations

import math
import sys
from pathlib import Path
from typing import List, Optional

import pandas as pd

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from data_validation.gtfs_utils import (  # noqa: E402,F401
    BASE,
    DOORS_BASE,
    DUPLICATED_TRIPS_BASE,
    RAW_BASE,
    SHARED_PLATFORMS_BASE,
    STOP_SEQUENCE_BASE,
    SUBWAY_BASE,
    WEIGHTS_BASE,
    check_missing_files,
)
from shortest_paths_algorithms.paths import (  # noqa: E402,F401
    ALGORITHMS_COMPARISON_REPORT_FULL_FILE,
    REPORTS_BASE,
)

# Pick exactly ONE input directory by uncommenting it (leave the rest commented).
INPUT_DIR = Path(RAW_BASE)  # data/0_raw
# INPUT_DIR = Path(SUBWAY_BASE)  # data/1_subway
# INPUT_DIR = Path(DUPLICATED_TRIPS_BASE)  # data/2_duplicated_trips
# INPUT_DIR = Path(STOP_SEQUENCE_BASE)  # data/3_stop_sequence
# INPUT_DIR = Path(DOORS_BASE)  # data/4_doors_time
# INPUT_DIR = Path(SHARED_PLATFORMS_BASE)  # data/5_shared_platforms
# INPUT_DIR = Path(WEIGHTS_BASE)  # data/6_weights
# INPUT_DIR = Path(REPORTS_BASE)  # reports/resources (platform-to-platform reports)
# INPUT_DIR = Path(ALGORITHMS_COMPARISON_REPORT_FULL_FILE).parent  # analysis/resources

# Set this to a filename like 'trips.txt' to convert only one file.
# Set it to None to convert every .txt file in INPUT_DIR.
TXT_FILE_NAME: Optional[str] = "pathways.txt"

# Excel limits one sheet to 1,048,576 rows total, including the header.
EXCEL_MAX_ROWS = 800_000
EXCEL_MAX_DATA_ROWS = EXCEL_MAX_ROWS - 1

# Pick exactly ONE output directory by uncommenting it (leave the rest commented).
OUTPUT_DIR = Path(BASE) / "excel_exports"  # shared data/excel_exports folder
# OUTPUT_DIR = INPUT_DIR / "excel_exports"  # next to the source .txt


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
            "Set INPUT_DIR to a different location."
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


def main() -> None:
    """Convert configured GTFS .txt file(s) to individual .xlsx files."""
    txt_files: List[Path]
    summary_df: pd.DataFrame

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    txt_files = get_txt_files(INPUT_DIR, TXT_FILE_NAME)

    print(f"Input folder: {INPUT_DIR}")
    print(f"Output folder: {OUTPUT_DIR}")
    print(
        f"Conversion mode: {'all .txt files' if TXT_FILE_NAME is None else 'single file'}"
    )
    for file_path in txt_files:
        print(f" - {file_path.name}")

    summary_df = convert_individual_files(txt_files, OUTPUT_DIR)
    print(summary_df.to_string(index=False))


if __name__ == "__main__":
    raise SystemExit(main())
