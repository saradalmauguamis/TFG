# TFG - GTFS Data Processing

Project for processing and converting GTFS transit data.

## Setup

### 1. Create Virtual Environment

```powershell
python -m venv .venv
```

### 2. Activate Virtual Environment

```powershell
.\.venv\Scripts\activate
```

### 3. Install Dependencies

```powershell
pip install -r requirements.txt
```

### 4. Install Pre-commit Hook

```powershell
.\.venv\Scripts\python.exe -m pip install pre-commit
.\.venv\Scripts\python.exe -m pre-commit install
```

## Pre-commit Checks

Pre-commit runs automatically on every `git commit`. It checks:
- ✅ Trailing whitespace
- ✅ End-of-file formatting
- ✅ YAML and JSON syntax
- ✅ Python code with Black (formatting)
- ✅ Python linting with Flake8

### Run Pre-commit Manually

To check all files before committing:

```powershell
.\.venv\Scripts\pre-commit.exe run --all-files
```

To check only staged files:

```powershell
.\.venv\Scripts\pre-commit.exe run
```

## Notebooks

- `from_txt_to_xlsx.ipynb` - Convert GTFS `.txt` files to Excel `.xlsx`
- `data-comprovations/data_comprovations.ipynb` - Data validation checks

## Configuration

- `.pre-commit-config.yaml` - Pre-commit hook configuration
