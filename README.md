# Modeling and Optimization of Routes in Barcelona's Public Transport Network

## Setup

Use the commands below for your operating system.

### 1. Create Virtual Environment

```bash
# macOS / Linux
python3 -m venv .venv

# Windows (PowerShell)
py -3 -m venv .venv
```

### 2. Activate Virtual Environment

```bash
# macOS / Linux
source .venv/bin/activate

# Windows (PowerShell)
.\.venv\Scripts\Activate.ps1
```

### 3. Install Dependencies

```bash
python -m pip install -r requirements.txt
```

### 4. Install Pre-commit Hook

```bash
python -m pip install pre-commit
pre-commit install
```

## Pre-commit Checks

Pre-commit runs automatically on every `git commit`. It checks:
- ✅ Trailing whitespace
- ✅ End-of-file formatting
- ✅ YAML and JSON syntax
- ✅ Python code with Black (formatting)
- ✅ Python linting with Flake8
- ✅ Function docstrings and descriptions
- ✅ `requirements.txt` matches `.venv` (pre-commit check)

### Run Pre-commit Manually

To check all files before committing:

```bash
pre-commit run --all-files
```

To check only staged files:

```bash
pre-commit run
```
