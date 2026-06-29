# Modeling and Optimization of Routes in Barcelona's Public Transport Network

## Repository Structure

```
TFG/
├── data_validation/      # GTFS data validation, processing, and analysis pipeline
├── routing_algotithms/   # Shortest-path algorithms and graph drawing
├── scripts/              # General-purpose helpers not tied to a pipeline stage
└── hooks/                # Pre-commit hook scripts
```

- [`data_validation/`](data_validation/README.md) — pipeline for validating, processing, and
  analysing the GTFS subway data.
- [`routing_algotithms/`](routing_algotithms/README.md) — Dijkstra and A* implementations, plus a
  subway graph drawing script.
- [`scripts/`](scripts/README.md) — reference data and standalone utilities shared across the
  other folders.
- [`hooks/`](hooks/README.md) — pre-commit hook scripts; see that README for what gets checked.

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
for the full list of checks and how to run them manually.
