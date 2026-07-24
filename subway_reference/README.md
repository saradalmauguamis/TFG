# Subway Reference

Static reference data and read-only reports about Barcelona's subway lines/stops themselves, as
opposed to the processed GTFS pipeline (`data_validation/`) or the derived weighted graph
(`graph_inspection/`, `shortest_paths_algorithms/`).

```
subway_reference/
├── subway_lines.py
├── stops_report.py
├── stops_report.txt
└── subway_maps/
```

---

### `subway_lines.py`

Static reference data for Barcelona's subway lines: a `route_short_name` → `route_id` mapping
(`subway_routes_names_ids`), and the ordered sequence of platform `stop_id`s per line
(`subway_route_names_stop_ids`, plus an `_artificial` variant matching stop_ids after
`5_shared_platforms_duplication.py` splits shared platforms). Imported across `data_validation/`
and `shortest_paths_algorithms/` whenever a line's stop order is needed.

### `stops_report.py`

Builds a per-line, per-stop report combining stop names with their entrance/exit nodes, using
`subway_route_names_stop_ids` (or the artificial variant) from `subway_lines.py` and pathway/stop
data from `data_validation/gtfs_utils.py`. Used to sanity-check that platform-entrance pathways
(`PW.platform_entrance` / `PW.entrance_platform`) are directionally consistent. `stops_report.txt`
is a generated snapshot of its output (`use_artificial=False`, `show_entrances=True`).

### `subway_maps/`

Reference JPGs of Barcelona's subway lines (one per line, plus the full network map), used for
visual cross-checking against [`graph_inspection/graph_draw/graph.py`](../graph_inspection/README.md)'s
output and against the GTFS data more generally.
