# Split Data Checks

Each script/folder is keyed to one GTFS file or concept: `pathways_checks.py` to
`pathways`/`transfers`, `stop_times/` to `stop_times`, `trips_checks.py` to `trips`.
`file_connection_checks.py` is the deliberate exception: its entire purpose is checking that
`stop_id`/`route_id`/`trip_id` references agree *across* files, so it's the one script that has
to span more than one `.txt`.

Independent of run order: `file_connection_checks.py`, `pathways_checks.py`,
`trips_checks.py`, and `stop_times/sequence_increment_check.py` only need
`processing/1_subway.py` to have run; they don't gate each other or the rest of the pipeline. The
rest of `stop_times/` is tied to a fixed position, since it's interleaved with
`processing/2_duplicated_trips.py`, `processing/3_stop_sequence.py`, and
`processing/4_doors_time.py` (see [`WORKFLOW.md`](../WORKFLOW.md)).

- `file_connection_checks.py`: file relationship checks.
  - All `stop_id` from `pathways`, `transfers`, and `stop_times` exist in `stops`?
  - All `route_id` from `trips` exist in `routes`?
  - All `trip_id` from `stop_times` exist in `trips`?

- `pathways_checks.py`: pathway and platform connectivity checks.
  - Platform-to-platform `pathways` and `transfers` contain exactly the same pairs?
  - Each pathway `PW.a_b` has its inverse `PW.b_a`?
  - `traversal_time` is the same for both directions? → since platform-to-platform pairs match
    exactly, this also covers `min_transfer_time` in `transfers`
  - `traversal_time` is present, numeric, and multiple of 15? → since platform-to-platform pairs
    match exactly, this also covers `min_transfer_time` in `transfers`
  - `traversal_time` is 60 for all entrance-to-platform pathways (`PW.E.xxx_1.yyy` /
    `PW.1.yyy_E.xxx`)?
  - How many platforms (`1.*`) is each entrance (`E.*`) connected to? (distribution, plus which
    entrances have none)
  - Each platform (`1.*`) is connected to an entrance (`E.*`)?
  - There is a transfer between each pair of platforms of the same stop?

- `stop_times/`: stop_times consistency and sequence checks, one script per check, numbered in
  pipeline run order. Each numbered script takes an optional `verify` argument to re-run the same
  check after its paired processing step, instead of detecting/writing fresh, e.g.:

  ```bash
  python data_validation/checks/stop_times/1_duplicate_trips_check.py          # detect
  python data_validation/checks/stop_times/1_duplicate_trips_check.py verify   # verify
  ```

  See [`WORKFLOW.md`](../WORKFLOW.md) for where each detect/verify pair fits in the full pipeline.
  - `sequence_increment_check.py` *(independent — only needs `1_subway`)*
    - Does `stop_sequence` increment by one for all trips?
  - `1_duplicate_trips_check.py` *(independent — only needs `1_subway`)*
    - Are there trips with identical stop_times content? (duplicates)
      → produces `trip_ids_to_eliminate.txt` in `data/2_duplicated_trips` → used by `data_validation/processing/2_duplicated_trips.py`
    - `verify`: after deduplication, does any signature still map to 2+ trip_id? *(needs `2_duplicated_trips`)*
  - `2_canonical_sequence_check.py` *(needs `2_duplicated_trips`)*
    - Do trips follow the canonical stop order for their route?
      → produces `wrong_stop_sequences.txt` in `data/3_stop_sequence` → used by `data_validation/processing/3_stop_sequence.py`
    - `verify`: after the sequence fix, do the bad pairs show non-consecutive sequence numbers? *(needs `3_stop_sequence`)*
  - `3_door_times_check.py` *(needs `3_stop_sequence`)*
    - Which stops have `arrival_time == departure_time`?
    - For partial `arrival == departure` stops: mean and stdev of door time (departure − arrival).
    - Per-line mean and stdev of door time, excluding `arrival == departure` rows.
    - Writes `doors.txt` in `data/4_doors_time/` with one row per `(stop_id, line)` that has any `arrival == departure` occurrence.
      → used by `data_validation/processing/4_doors_time.py`
    - `verify`: after the door-time fix, does any stop still have `arrival_time == departure_time`? *(needs `4_doors_time`)*

- `trips_checks.py`: trip metadata pairing checks.
  - Are `direction_id` and `trip_headsign` correctly paired per route?
