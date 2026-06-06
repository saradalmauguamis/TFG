# Data Processing Pipeline

Each script is a self-contained step that reads from one data stage and writes the cleaned result to the next.

---

### `1_subway.py` — extract subway-only rows

`.src/gtfs/data/0_original` → `.src/gtfs/data/1_subway`

| Input | Output |
|---|---|
| `routes.txt` | `routes_subway.txt` |
| `stop_times.txt` | `stop_times_subway.txt` |
| `stops.txt` | `stops_subway.txt` |
| `trips.txt` | `trips_subway.txt` |

Rows whose first column starts with `2.` (bus network) are removed.

---

### `2_duplicated_trips.py` — remove duplicated trips

`.src/gtfs/data/1_subway` → `.src/gtfs/data/2_duplicated_trips`

| Input | Output |
|---|---|
| `stop_times_subway.txt` | `stop_times_cleaned.txt` |
| `trips_subway.txt` | `trips_cleaned.txt` |

Also reads `trip_ids_to_eliminate.txt` from `.src/gtfs/data/2_duplicated_trips`, produced by `data_validation/checks/3_stop_times_checks.ipynb`.

---

### `3_stop_sequence.py` — fix stop_sequence gaps

`.src/gtfs/data/2_duplicated_trips` → `.src/gtfs/data/3_stop_sequence`

| Input | Output |
|---|---|
| `stop_times_cleaned.txt` | `stop_times_sequence.txt` |

Also reads `wrong_stop_sequences.txt` from `.src/gtfs/data/3_stop_sequence`, produced by `data_validation/checks/3_stop_times_checks.ipynb`.

---

### `4_doors_time.py` — add door-open times to terminal stops

`.src/gtfs/data/3_stop_sequence` → `.src/gtfs/data/4_doors`

| Input | Output |
|---|---|
| `stop_times_sequence.txt` | `stop_times_doors.txt` |

Also reads `doors.txt` and `trips_cleaned.txt`, produced by `data_validation/checks/3_stop_times_checks.ipynb` and `2_duplicated_trips.py` respectively.

For every row where `arrival_time == departure_time` at a terminal stop, the script adjusts the synthetic timestamp using the door-open duration from `doors.txt` (keyed by `stop_id` and line):
- first stop (min `stop_sequence`): `arrival_time = departure_time − door_seconds`
- last stop (max `stop_sequence`): `departure_time = arrival_time + door_seconds`

`door_seconds` in `doors.txt` is assigned per `(stop_id, line)` by the notebook:
- partial stops (only some trips have `arr == dep`): per-stop mean of the non-zero-dwell trips
- canonical terminal stops (all trips have `arr == dep`): line mean door time
- FM line (no observed door times): mean across all other lines as fallback

### `5_L9_L10_data_duplication.py` — resolve L9/L10 duplication *(work in progress)*

---

## File transformation summary

```
0_original           1_subway                2_duplicated_trips      3_stop_sequence         4_doors

pathways
routes               routes_subway
stop_times           stop_times_subway       stop_times_cleaned      stop_times_sequence     stop_times_doors
stops                stops_subway
transfers
trips                trips_subway            trips_cleaned
```
