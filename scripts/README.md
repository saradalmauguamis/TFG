# Scripts

General-purpose helpers and one-off utilities that don't belong to a specific pipeline stage.

```
scripts/
├── utils.py
└── from_txt_to_xlsx.py
```

---

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
