# Data Validation

Pipeline for validating, processing, and analysing the GTFS subway data.

```
data_validation/
├── gtfs_utils.py
├── checks/
│   ├── 1_file_connection_checks.ipynb
│   ├── 2_pathways_checks.ipynb
│   ├── 3_stop_times_checks.ipynb
│   └── 4_trips_checks.ipynb
├── processing/
│   ├── 1_subway.py
│   ├── 2_duplicated_trips.py
│   ├── 3_stop_sequence.py
│   ├── 4_doors_time.py
│   └── 5_L9_L10_data_duplication.py
└── analysis/
    ├── between_platforms.py
    └── L9_L10.py
```

---

### `gtfs_utils.py`

Shared path constants, file I/O helpers, and data loading functions used across all subpackages.

---

### [`checks/`](checks/README.md) — data consistency validation

Notebooks that validate data at each stage of the pipeline.

- `1_file_connection_checks.ipynb` — file relationship checks
- `2_pathways_checks.ipynb` — pathway and platform connectivity checks
- `3_stop_times_checks.ipynb` — stop_times consistency and sequence checks
- `4_trips_checks.ipynb` — trip metadata pairing checks

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
- `L9_L10.py` — compare inter-platform travel times between L9 and L10
