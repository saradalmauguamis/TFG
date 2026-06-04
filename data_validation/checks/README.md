# Split Data Checks

- `commons.py`: shared imports, path bootstrap, and reusable helpers.

- `1_file_connection_checks.ipynb`: file relationship checks.
  - All `stop_id` from `pathways` and `stop_times` exist in `stops`?
  - All `route_id` from `trips` exist in `routes`?
  - All `trip_id` from `stop_times` exist in `trips`?

- `2_pathways_checks.ipynb`: pathway and platform connectivity checks.
  - All transfers from `transfers` are within `pathways`?
  - Each pathway `PW.a_b` has its inverse `PW.b_a`?
  - `traversal_time` is the same for both directions?
  - `traversal_time` is present, numeric, and multiple of 15?
  - Each entrance (`E.*`) is connected to a platform (`1.*`)?
  - Each platform (`1.*`) is connected to an entrance (`E.*`)?
  - There is a pathway between each pair of platforms of the same stop?

- `3_stop_times_checks.ipynb`: stop_times consistency and sequence checks.
  - Are there trips with identical stop_times content? (duplicates)
    → produces `trip_ids_to_eliminate.txt` in `src/gtfs/data/2_duplicated_trips` → used by `data_validation/processing/2_duplicated_trips.py`
  - Does `stop_sequence` increment by one for all trips?
  - Do trips follow the canonical stop order for their route?
    → produces `wrong_stop_sequences.txt` in `.src/gtfs/data/3_stop_sequence` → used by `data_validation/processing/3_stop_sequence.py`
  - After the sequence fix, do the bad pairs show non-consecutive sequence numbers? *(verification)*
  - Which stops have the same arrival and departure time? *(work in progress)*

- `4_trips_checks.ipynb`: trip metadata pairing checks.
  - Are `direction_id` and `trip_headsign` correctly paired per route?
