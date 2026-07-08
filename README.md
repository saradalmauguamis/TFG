# Modeling and Optimization of Routes in Barcelona's Public Transport Network

## Repository Structure

```
TFG/
├── data/
├── data_validation/
├── graph_inspection/
├── shortest_paths_algorithms/
├── scripts/
├── hooks/
├── .gitignore
├── .pre-commit-config.yaml
└── requirements.txt
```

- `data/` — GTFS pipeline data, organized by processing stage (`0_raw` → `6_weights`); see
  [`data_validation/README.md`](data_validation/README.md) and
  [`data_validation/WORKFLOW.md`](data_validation/WORKFLOW.md) for what reads/writes each stage.
- [`data_validation/`](data_validation/README.md) — pipeline for validating, processing, and
  analysing the GTFS subway data.
- [`graph_inspection/`](graph_inspection/README.md) — subway graph drawing and reporting tools.
- [`shortest_paths_algorithms/`](shortest_paths_algorithms/README.md) — Dijkstra and A* implementations.
- [`scripts/`](scripts/README.md) — reference data and standalone utilities shared across the
  other folders.
- [`hooks/`](hooks/README.md) — pre-commit hook scripts; see that README for what gets checked.
- `.gitignore` — files and folders excluded from version control.
- `.pre-commit-config.yaml` — pre-commit hook registration (see [`hooks/README.md`](hooks/README.md)).
- `requirements.txt` — pinned Python dependencies for `.venv`.

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

Pre-commit runs automatically on every `git commit`. See [`hooks/README.md`](hooks/README.md)
for the full list of checks.

### Run Pre-commit Manually

To check all files before committing:

```bash
pre-commit run --all-files
```

To check only staged files:

```bash
pre-commit run
```
