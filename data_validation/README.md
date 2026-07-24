# Data Validation

Pipeline for validating, processing, and analysing the GTFS subway data, with the aim of
building the weighted graph used by [`shortest_paths_algorithms/`](../shortest_paths_algorithms/README.md).

See [`WORKFLOW.md`](WORKFLOW.md) for the end-to-end run order across scripts.

```
data_validation/
├── gtfs_utils.py
├── checks/
│   ├── file_connection_checks.py
│   ├── pathways_checks.py
│   ├── stop_times/
│   │   ├── sequence_increment_check.py
│   │   ├── 1_duplicate_trips_check.py
│   │   ├── 2_canonical_sequence_check.py
│   │   └── 3_door_times_check.py
│   └── trips_checks.py
├── processing/
│   ├── 1_subway.py
│   ├── 2_duplicated_trips.py
│   ├── 3_stop_sequence.py
│   ├── 4_doors_time.py
│   ├── 5_shared_platforms_duplication.py
│   └── 6_weights.py
└── analysis/
    ├── shared_platforms.py
    ├── directional_asymmetry.py
    └── edge_weight_validation.py
```

---

### `gtfs_utils.py`

Shared path constants, file I/O helpers, and data loading functions used across all subpackages.

---

### [`checks/`](checks/README.md) — data consistency validation

Scripts that validate data at each stage of the
pipeline. `file_connection_checks.py`, `pathways_checks.py`, and `trips_checks.py` are
independent of pipeline order: they only need `processing/1_subway.py` to have run. `stop_times/`
is the only one with a fixed position, since most of its scripts are interleaved with three
processing scripts (see [`WORKFLOW.md`](WORKFLOW.md)).

- `file_connection_checks.py` — file relationship checks
- `pathways_checks.py` — pathway and platform connectivity checks
- `stop_times/` — stop_times consistency and sequence checks, one script per check
- `trips_checks.py` — trip metadata pairing checks

---

### [`processing/`](processing/README.md) — GTFS data transformation

Scripts that transform raw GTFS files into cleaned, stage-by-stage outputs.

- `1_subway.py` — extract subway-only rows
- `2_duplicated_trips.py` — remove duplicated trips
- `3_stop_sequence.py` — fix stop_sequence gaps
- `4_doors_time.py` — add door-open times to terminal stops
- `5_shared_platforms_duplication.py` — split shared platforms into one stop_id per line
- `6_weights.py` — build the weighted graph edges (`sw`, `tf`, `pw`)

---

### [`analysis/`](analysis/README.md) — research questions

Read-only scripts that answer specific questions to help decide graph design.

- `shared_platforms.py` — compare inter-platform travel times across lines sharing a platform
- `directional_asymmetry.py` — compare directional travel times between adjacent platforms
- `edge_weight_validation.py` — validate whether mean(total) travel time is a trustworthy static edge weight
