# Split Data Checks

Each notebook is keyed to one GTFS file or concept — `pathways_checks.ipynb` to
`pathways`/`transfers`, `stop_times_checks.ipynb` to `stop_times`, `trips_checks.ipynb` to
`trips`. `file_connection_checks.ipynb` is the deliberate exception: its entire purpose is
checking that `stop_id`/`route_id`/`trip_id` references agree *across* files, so it's the one
notebook that has to span more than one `.txt`.

Independent of run order — `file_connection_checks.ipynb`, `pathways_checks.ipynb`,
`trips_checks.ipynb`, and the *Does stop_sequence increment by one?* block of
`stop_times_checks.ipynb` only need `processing/1_subway.py` to have run; they don't gate each
other or the rest of the pipeline. The rest of `stop_times_checks.ipynb` is tied to a fixed
position, since it's interleaved with `processing/2_duplicated_trips.py`,
`processing/3_stop_sequence.py`, and `processing/4_doors_time.py` (see
[`WORKFLOW.md`](../WORKFLOW.md)).

- `file_connection_checks.ipynb`: file relationship checks.
  - All `stop_id` from `pathways` and `stop_times` exist in `stops`?
  - All `route_id` from `trips` exist in `routes`?
  - All `trip_id` from `stop_times` exist in `trips`?

- `pathways_checks.ipynb`: pathway and platform connectivity checks.
  - All transfers from `transfers` are within `pathways`?
  - Each pathway `PW.a_b` has its inverse `PW.b_a`?
  - `traversal_time` is the same for both directions?
  - `traversal_time` is present, numeric, and multiple of 15?
  - Each entrance (`E.*`) is connected to a platform (`1.*`)?
  - Each platform (`1.*`) is connected to an entrance (`E.*`)?
  - There is a pathway between each pair of platforms of the same stop?

- `stop_times_checks.ipynb`: stop_times consistency and sequence checks.
  - **Does stop_sequence increment by one?** *(independent — only needs `1_subway`)*
    - Does `stop_sequence` increment by one for all trips?
  - **Duplicate full trip_id blocs in stop_times** *(independent — only needs `1_subway`)*
    - Are there trips with identical stop_times content? (duplicates)
      → produces `trip_ids_to_eliminate.txt` in `src/gtfs/data/2_duplicated_trips` → used by `data_validation/processing/2_duplicated_trips.py`
  - **The canonical stop sequence is followed correctly?** *(needs `2_duplicated_trips`)*
    - Do trips follow the canonical stop order for their route?
      → produces `wrong_stop_sequences.txt` in `.src/gtfs/data/3_stop_sequence` → used by `data_validation/processing/3_stop_sequence.py`
    - After the sequence fix, do the bad pairs show non-consecutive sequence numbers? *(verification, needs `3_stop_sequence`)*
  - **Cases when arrival_time and departure_time is the same** *(needs `3_stop_sequence`)*
    - Which stops have `arrival_time == departure_time`?
    - For partial `arrival == departure` stops: mean and stdev of door time (departure − arrival).
    - Per-line mean and stdev of door time, excluding `arrival == departure` rows.
    - Writes `doors.txt` in `.src/gtfs/data/4_doors_time/` with one row per `(stop_id, line)` that has any `arrival == departure` occurrence.
      → used by `data_validation/processing/4_doors_time.py`
    - After the door-time fix, does any stop still have `arrival_time == departure_time`? *(verification, needs `4_doors_time`)*

- `trips_checks.ipynb`: trip metadata pairing checks.
  - Are `direction_id` and `trip_headsign` correctly paired per route?
