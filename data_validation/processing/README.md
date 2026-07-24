# Data Processing Pipeline

Each script is a self-contained step that reads from one data stage and writes the cleaned result to the next.

---

### `1_subway.py` — extract subway-only rows

`data/0_raw` → `data/1_subway`

| Input | Output |
|---|---|
| `routes.txt` | `routes_subway.txt` |
| `stop_times.txt` | `stop_times_subway.txt` |
| `stops.txt` | `stops_subway.txt` |
| `trips.txt` | `trips_subway.txt` |

Rows whose first column starts with `2.` (bus network) are removed.

---

### `2_duplicated_trips.py` — remove duplicated trips

`data/1_subway` → `data/2_duplicated_trips`

| Input | Output |
|---|---|
| `stop_times_subway.txt` | `stop_times_cleaned.txt` |
| `trips_subway.txt` | `trips_cleaned.txt` |

Also reads `trip_ids_to_eliminate.txt` from `data/2_duplicated_trips`, produced by `data_validation/checks/stop_times/1_duplicate_trips_check.py`.

---

### `3_stop_sequence.py` — fix stop_sequence gaps

`data/2_duplicated_trips` → `data/3_stop_sequence`

| Input | Output |
|---|---|
| `stop_times_cleaned.txt` | `stop_times_sequence.txt` |

Also reads `wrong_stop_sequences.txt` from `data/3_stop_sequence`, produced by `data_validation/checks/stop_times/2_canonical_sequence_check.py`.

For each trip, `wrong_stop_sequences.txt` lists the breaks where two consecutive stops are not adjacent in the canonical route order (as `seq_a`/`seq_b` pairs). For every such break, the script opens a gap: the breaking stop and every stop after it in that trip have their `stop_sequence` incremented by one. Breaks accumulate, i.e., a stop that comes after two break points ends up with its original sequence plus two. This lets downstream graph builders distinguish physically non-adjacent stops from adjacent ones, without changing arrival/departure times.

---

### `4_doors_time.py` — add door-open times to terminal stops

`data/3_stop_sequence` → `data/4_doors_time`

| Input | Output |
|---|---|
| `stop_times_sequence.txt` | `stop_times_doors.txt` |

Also reads `doors.txt` and `trips_cleaned.txt`, produced by `data_validation/checks/stop_times/3_door_times_check.py` and `2_duplicated_trips.py` respectively.

For every row where `arrival_time == departure_time` at a terminal stop, the script adjusts the synthetic timestamp using the door-open duration from `doors.txt` (keyed by `stop_id` and line):
- first stop (min `stop_sequence`): `arrival_time = departure_time − door_seconds`
- last stop (max `stop_sequence`): `departure_time = arrival_time + door_seconds`

`door_seconds` in `doors.txt` is assigned per `(stop_id, line)` by the notebook:
- partial stops (only some trips have `arrival_time == deparature_time`): per-stop mean of the non-zero-dwell trips
- canonical terminal stops (all trips have `arrival_time == deparature_time`): line mean door time
- FM line (no observed door times): mean across all other lines as fallback

### `5_shared_platforms_duplication.py` — split shared platforms into one stop_id per line

`data/0_raw` + `data/1_subway` + `data/4_doors_time` → `data/5_shared_platforms`

| Input | Output |
|---|---|
| `pathways.txt` | `pathways_shared.txt` |
| `stop_times_doors.txt` | `stop_times_shared.txt` |
| `stops_subway.txt` | `stops_shared.txt` |
| `transfers.txt` | `transfers_shared.txt` |
| — | `equivalences.txt` |

Also reads `trips_cleaned.txt` from `data/2_duplicated_trips` to resolve each stop_times row's trip to its line.

Shared platforms (stops served by more than one line, e.g. the L9S/L10S and L9N/L10N overlaps) are detected generically from `subway_reference/subway_lines.py`'s `subway_route_names_stop_ids`; no line names are hardcoded, so any future shared platform is picked up automatically. Each shared `stop_id` (e.g. `1.930`) is split into one new id per serving line (`1.9300`, `1.9301`, ...):

- **STOPS / PATHWAYS / TRANSFERS**: one duplicated row per line. PATHWAYS/TRANSFERS additionally get a direct correspondence edge between every pair of a platform's new ids, using the minimum `min_transfer_time` found in `transfers.txt` as the traversal time.
- **STOP_TIMES**: the shared `stop_id` is *replaced* (not duplicated) with the single new id matching that row's own trip's line, since a trip belongs to exactly one line.
- **`equivalences.txt`**: a lookup table of `original_stop_id, line, new_stop_id` for every split platform, so the mapping can be looked back up later.

### `6_weights.py` — build the weighted graph edges

`data/5_shared_platforms` (+ `data/2_duplicated_trips` trips) → `data/6_weights`

| Input | Output |
|---|---|
| `stop_times_shared.txt` | `subway_weights.txt` |
| `transfers_shared.txt` | — |
| `pathways_shared.txt` | — |
| — | `weights.txt` |

Also reads `trips_cleaned.txt` from `data/2_duplicated_trips` to resolve each trip's line and
direction.

Motivated by `analysis/directional_asymmetry.py` (directed edges) and
`analysis/edge_weight_validation.py` (whether `mean(total)` is a trustworthy static weight for `sw`
edges).

- **`subway_weights.txt`** (`from_stop_id, to_stop_id, weight_seconds, line`): the `sw` (platform →
  platform) edge weight for every directed pair observed in `stop_times_shared.txt`, computed as
  `round_half_up_mean` of the observed travel times (`arrival_b - arrival_a`), pooled across every
  `(line, direction_id)` group that produces that exact pair. `round_half_up_mean` (integer-only
  arithmetic) is used instead of a float mean to avoid the precision drift `statistics.mean`/`round()`
  can introduce.
- **`weights.txt`** (`from_stop_id, to_stop_id, weight_seconds, type`): the full set of graph edges,
  combining `subway_weights.txt` (`type=SW`) with two more edge types: `TF` (transfers, weight =
  `min_transfer_time` from `transfers_shared.txt`) and `PW` (entrance ↔ platform pathways, weight =
  `traversal_time` from `pathways_shared.txt`, restricted to rows where one side is an entrance
  (`E.*`) and the other a platform (`1.*`)).


---

## File transformation summary

Each line traces one logical file across the stages where it actually exists (stages it skips are omitted, so chains have different lengths):

- **pathways**: `0_raw/pathways.txt` → `5_shared_platforms/pathways_shared.txt`
- **routes**: `0_raw/routes.txt` → `1_subway/routes_subway.txt`
- **stop_times**: `0_raw/stop_times.txt` → `1_subway/stop_times_subway.txt` → `2_duplicated_trips/stop_times_cleaned.txt` → `3_stop_sequence/stop_times_sequence.txt` → `4_doors_time/stop_times_doors.txt` → `5_shared_platforms/stop_times_shared.txt`
- **stops**: `0_raw/stops.txt` → `1_subway/stops_subway.txt` → `5_shared_platforms/stops_shared.txt`
- **transfers**: `0_raw/transfers.txt` → `5_shared_platforms/transfers_shared.txt`
- **trips**: `0_raw/trips.txt` → `1_subway/trips_subway.txt` → `2_duplicated_trips/trips_cleaned.txt`
- **equivalences** *(new, no upstream file)*: `5_shared_platforms/equivalences.txt`
- **subway_weights** *(new, no upstream file)*: `6_weights/subway_weights.txt`
- **weights** *(new, no upstream file)*: `6_weights/weights.txt`
