# Scripts

General-purpose helpers and one-off utilities that don't belong to a specific pipeline stage.

```
scripts/
├── basics.py
├── stops_report.py
├── utils.py
└── from_txt_to_xlsx.ipynb
```

---

### `basics.py`

Static reference data for Barcelona's subway lines: a `route_short_name` → `route_id` mapping
(`subway_routes_names_ids`), and the ordered sequence of platform `stop_id`s per line
(`subway_route_names_stop_ids`, plus an `_artificial` variant matching stop_ids after
`5_shared_platforms_duplication.py` splits shared platforms). Imported across `data_validation/`
and `routing_algotithms/` whenever a line's stop order is needed.

### `stops_report.py`

Builds a per-line, per-stop report combining stop names with their entrance/exit nodes, using
`subway_route_names_stop_ids` (or the artificial variant) from `basics.py` and pathway/stop data
from `data_validation/gtfs_utils.py`. Used to sanity-check that platform-entrance pathways
(`PW.platform_entrance` / `PW.entrance_platform`) are directionally consistent.

### `utils.py`

Generic CSV helpers — delimiter sniffing with a comma fallback — used by GTFS file readers
elsewhere in the repo.

### `from_txt_to_xlsx.ipynb`

Converts GTFS `.txt` files into `.xlsx` workbooks for manual inspection. Any folder under `.src/gtfs/data/`
can be converted — set `DATA_DIR` to the pipeline stage you want (e.g. `0_raw`, `1_subway`,
`5_shared_platforms_duplication`). Can convert a single file or all `.txt` files in the data
folder; large files are split across multiple sheets automatically.
