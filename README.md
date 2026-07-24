# Modeling and Optimization of Routes in Barcelona's Public Transport Network

## About

This repository implements and compares shortest path algorithms for the Barcelona subway
network, built from official GTFS data provided by TMB, including the Montjuïc Funicular. It
investigates strategies to reduce the number of iterations needed to reach the optimal route,
developing a network-specific heuristic based on the topology of the Barcelona metro system and
a graph reduction technique, and comparing them against Dijkstra's algorithm and A* with a
conventional geometric heuristic. Combining these strategies achieves an approximately 6.5-fold
reduction in iterations compared with the initial solution based on Dijkstra's algorithm.

The work splits into two main phases: [`data_validation/`](data_validation/README.md) builds and
validates the weighted graph from raw GTFS data, with
[`data_validation/WORKFLOW.md`](data_validation/WORKFLOW.md) walking through the end-to-end run
order across scripts; and [`shortest_paths_algorithms/`](shortest_paths_algorithms/README.md)
implements and compares the search algorithms and heuristics, with
[`shortest_paths_algorithms/WORKFLOW.md`](shortest_paths_algorithms/WORKFLOW.md) walking through
the reasoning behind each one.

## Repository Structure

```
TFG/
├── data/
├── data_validation/
├── graph_inspection/
├── shortest_paths_algorithms/
├── subway_reference/
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
- [`shortest_paths_algorithms/`](shortest_paths_algorithms/README.md) — Dijkstra and A*
  implementations; see [`shortest_paths_algorithms/WORKFLOW.md`](shortest_paths_algorithms/WORKFLOW.md)
  for the reasoning trail behind each heuristic.
- [`subway_reference/`](subway_reference/README.md) — static reference data, maps, and reports
  about Barcelona's subway lines/stops, shared across the other folders.
- [`scripts/`](scripts/README.md) — standalone utilities shared across the other folders.
- [`hooks/`](hooks/README.md) — pre-commit hook scripts; see that README for what gets checked.
- `.gitignore` — files and folders excluded from version control.
- `.pre-commit-config.yaml` — pre-commit hook registration (see [`hooks/README.md`](hooks/README.md)).
- `requirements.txt` — direct Python dependencies for `.venv`.

## Setup

Requires Python 3.10+. On macOS, the `python3` on `PATH` is often Apple's older bundled system
Python (3.9 or earlier), which is too old for this project's dependencies; check with
`python3 --version` first, and if it's below 3.10, install a newer Python (e.g.
`brew install python@3.12`) and use that interpreter (e.g. `python3.12`) in the step below instead
of the bare `python3`.

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

`requirements.txt` pins minimum versions, not exact ones, so this installs on any Python/OS. See
the comment at the top of that file for the exact versions the thesis's reported results were
produced with, in case a re-run ever needs to rule out a library-version difference.

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
