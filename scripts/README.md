# Scripts

General-purpose helpers and one-off utilities that don't belong to a specific pipeline stage.

```
scripts/
├── basics.py
├── stops_report.py
├── utils.py
└── from_txt_to_xlsx.py
```

---

### `basics.py`

Static reference data for Barcelona's subway lines: a `route_short_name` → `route_id` mapping
(`subway_routes_names_ids`), and the ordered sequence of platform `stop_id`s per line
(`subway_route_names_stop_ids`, plus an `_artificial` variant matching stop_ids after
`5_shared_platforms_duplication.py` splits shared platforms). Imported across `data_validation/`
and `shortest_paths_algorithms/` whenever a line's stop order is needed.

### `stops_report.py`

Builds a per-line, per-stop report combining stop names with their entrance/exit nodes, using
`subway_route_names_stop_ids` (or the artificial variant) from `basics.py` and pathway/stop data
from `data_validation/gtfs_utils.py`. Used to sanity-check that platform-entrance pathways
(`PW.platform_entrance` / `PW.entrance_platform`) are directionally consistent.

### `utils.py`

Generic CSV helpers (delimiter sniffing with a comma fallback), used by GTFS file readers
elsewhere in the repo.

### `from_txt_to_xlsx.py`

Converts GTFS `.txt` files into individual `.xlsx` files for manual inspection. `DATA_DIR` can
point at any pipeline stage folder under `data/` (e.g. `0_raw`, `1_subway`,
`5_shared_platforms_duplication`) or at a `shortest_paths_algorithms/reports/` folder such as
`REPORTS_BASE`. Can convert a single file or all `.txt` files in the folder; large files are split
across multiple `.xlsx` files automatically. Exports go to `data/excel_exports` by default, or
next to the source folder if `EXPORT_NEXT_TO_SOURCE` is set.
