# Data Validation

Pipeline for validating, processing, and analysing the GTFS subway data.

See [`WORKFLOW.md`](WORKFLOW.md) for the end-to-end run order across notebooks and scripts.

```
data_validation/
├── gtfs_utils.py
├── checks/
│   ├── file_connection_checks.ipynb
│   ├── pathways_checks.ipynb
│   ├── stop_times_checks.ipynb
│   └── trips_checks.ipynb
├── processing/
│   ├── 1_subway.py
│   ├── 2_duplicated_trips.py
│   ├── 3_stop_sequence.py
│   ├── 4_doors_time.py
│   └── 5_L9_L10_data_duplication.py
└── analysis/
    ├── between_platforms.py
    └── shared_platforms.py
```

---

### `gtfs_utils.py`

Shared path constants, file I/O helpers, and data loading functions used across all subpackages.

---

### [`checks/`](checks/README.md) — data consistency validation

Notebooks that validate data at each stage of the pipeline. `file_connection_checks.ipynb`,
`pathways_checks.ipynb`, and `trips_checks.ipynb` are independent of pipeline order — they only
need `processing/1_subway.py` to have run. `stop_times_checks.ipynb` is the only one with a
fixed position, since it's interleaved with three processing scripts (see
[`WORKFLOW.md`](WORKFLOW.md)).

- `file_connection_checks.ipynb` — file relationship checks
- `pathways_checks.ipynb` — pathway and platform connectivity checks
- `stop_times_checks.ipynb` — stop_times consistency and sequence checks
- `trips_checks.ipynb` — trip metadata pairing checks

---

### [`processing/`](processing/README.md) — GTFS data transformation

Scripts that transform raw GTFS files into cleaned, stage-by-stage outputs.

- `1_subway.py` — extract subway-only rows
- `2_duplicated_trips.py` — remove duplicated trips
- `3_stop_sequence.py` — fix stop_sequence gaps
- `4_doors_time.py` — add door-open times to terminal stops
- `5_L9_L10_data_duplication.py` — resolve L9/L10 duplication *(work in progress)*

---

### [`analysis/`](analysis/README.md) — research questions

Read-only scripts that answer specific questions to help decide graph design.

- `between_platforms.py` — compare directional travel times between adjacent platforms
- `shared_platforms.py` — compare inter-platform travel times between L9 and L10
