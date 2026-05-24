import csv
from pathlib import Path
from typing import Dict, Iterable, Union


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

        class _DefaultDialect(csv.Dialect):
            delimiter = ","
            quotechar = '"'
            doublequote = True
            skipinitialspace = False
            lineterminator = "\n"
            quoting = csv.QUOTE_MINIMAL

        return _DefaultDialect


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
