import csv
from pathlib import Path
from typing import Dict, Iterable, List, Sequence, Union


class _DefaultDialect(csv.Dialect):
    """Comma-delimited fallback dialect used when sniffing fails."""

    delimiter = ","
    quotechar = '"'
    doublequote = True
    skipinitialspace = False
    lineterminator = "\n"
    quoting = csv.QUOTE_MINIMAL


def sniff_dialect(file_path: Union[str, Path]) -> type[csv.Dialect]:
    """Detect CSV delimiter; default to comma if detection fails.

    args:
        file_path: Path to the CSV file.

    returns:
        A CSV dialect class compatible with the input file.
    """
    file_path = Path(file_path)
    try:
        with file_path.open("r", encoding="utf-8-sig", newline="") as file_handle:
            sample = file_handle.read(65536)
        return csv.Sniffer().sniff(sample, delimiters=",;\t")
    except Exception:
        return _DefaultDialect


def read_header(file_path: Union[str, Path]) -> List[str]:
    """Return lowercase, stripped header field names for a CSV file.

    args:
        file_path: Path to the CSV file.

    returns:
        Header field names in file order.
    """
    file_path = Path(file_path)
    dialect = sniff_dialect(file_path)
    with file_path.open("r", encoding="utf-8-sig", newline="") as file_handle:
        reader = csv.DictReader(file_handle, dialect=dialect)
        if reader.fieldnames is None:
            raise RuntimeError(f"File {file_path.name} has no header.")
        return [name.lower().strip() for name in reader.fieldnames]


def read_dict_rows(file_path: Union[str, Path]) -> Iterable[Dict[str, str]]:
    """Yield rows as dictionaries with lowercase keys and stripped values.

    args:
        file_path: Path to the CSV file.

    returns:
        An iterator of cleaned row dictionaries.
    """
    file_path = Path(file_path)
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


def round_half_up_mean(values: Sequence[int]) -> int:
    """Round-half-up mean of a sequence of integers, computed without floats.

    Python's round() rounds half-to-even, and statistics.mean() returns a
    float whose binary representation can drift off an exact .5 boundary.
    Rewriting floor(total/n + 0.5) as (2*total + n) // (2*n) avoids both
    issues by staying in exact integer arithmetic.

    args:
        values: Sequence of integers to average.

    returns:
        Round-half-up integer mean, or 0 for an empty sequence.
    """
    count = len(values)
    total = sum(values)
    if not count:
        return 0
    return (2 * total + count) // (2 * count)


def write_rows(
    output_path: Union[str, Path],
    fieldnames: Sequence[str],
    rows: Iterable[Dict[str, str]],
) -> None:
    """Write rows to a CSV file, creating the parent directory if needed.

    args:
        output_path: Destination file path.
        fieldnames: Column order to write.
        rows: Row dictionaries to write.
    """
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", encoding="utf-8", newline="") as file_handle:
        writer = csv.DictWriter(file_handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
