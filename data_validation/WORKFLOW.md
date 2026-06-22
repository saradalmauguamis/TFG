# Pipeline Workflow

`checks/` and `processing/` are split by *kind* of file, not by run order: a single processing
stage is often produced by running half a notebook, then a script, then jumping back into the
same notebook to verify. File numbering (`1_`, `2_`, ...) reflects the data stage, not the
sequence in which notebooks and scripts are executed. This page lists the actual run order, end
to end, from `0_raw` to `4_doors_time`.

---

1. **`processing/1_subway.py`** — `0_raw` → `1_subway`

   Extracts subway-only rows from `routes`, `stop_times`, `stops`, `trips`.

2. **`checks/2_pathways_checks.ipynb`** — pathway and platform connectivity checks

   Reads `pathways.txt`/`transfers.txt` from `0_raw` and `stops_subway.txt` from `1_subway`. No
   file output; purely a verification step.

3. **`checks/3_stop_times_checks.ipynb`** → *Duplicate full trip_id blocs in stop_times*

   Reads `stop_times_subway.txt`/`trips_subway.txt` from `1_subway`.
   → produces `trip_ids_to_eliminate.txt` in `2_duplicated_trips`.

4. **`processing/2_duplicated_trips.py`** — `1_subway` → `2_duplicated_trips`

   Consumes `trip_ids_to_eliminate.txt` (step 3) to remove duplicate trips, writing
   `stop_times_cleaned.txt` and `trips_cleaned.txt`.

5. **`checks/4_trips_checks.ipynb`** — trip metadata pairing checks

   Reads `routes_subway.txt` (`1_subway`) and `trips_cleaned.txt` (`2_duplicated_trips`). No file
   output; purely a verification step.

6. **`checks/3_stop_times_checks.ipynb`** → *Does stop_sequence increment by one?*

   Reads `stop_times_cleaned.txt` (step 4). No file output; verification only.

7. **`checks/3_stop_times_checks.ipynb`** → *The canonical stop sequence is followed correctly?*

   Reads `stop_times_cleaned.txt` (step 4).
   → produces `wrong_stop_sequences.txt` in `3_stop_sequence`.

8. **`processing/3_stop_sequence.py`** — `2_duplicated_trips` → `3_stop_sequence`

   Consumes `wrong_stop_sequences.txt` (step 7) to open sequence gaps, writing
   `stop_times_sequence.txt`.

9. **`checks/3_stop_times_checks.ipynb`** → *After the sequence fix* *(verification)*

   Re-runs the same canonical-order check on `stop_times_sequence.txt` (step 8); bad pairs should
   now be non-consecutive. No file output.

10. **`checks/3_stop_times_checks.ipynb`** → *Cases when arrival_time and departure_time is the
    same*

    Reads `stop_times_sequence.txt` (step 8) and `trips_cleaned.txt` (step 4).
    → produces `doors.txt` in `4_doors_time`.

11. **`processing/4_doors_time.py`** — `3_stop_sequence` → `4_doors_time`

    Consumes `doors.txt` (step 10) and `trips_cleaned.txt` (step 4) to adjust terminal-stop
    timestamps, writing `stop_times_doors.txt`.

12. **`checks/3_stop_times_checks.ipynb`** → *After the door-time fix* *(verification)*

    Re-runs the arrival/departure check on `stop_times_doors.txt` (step 11); no stop should still
    have `arrival_time == departure_time`. No file output.

13. **`checks/1_file_connection_checks.ipynb`** — file relationship checks

    Reads `pathways.txt` (`0_raw`), `routes_subway.txt`/`stops_subway.txt` (`1_subway`),
    `trips_cleaned.txt` (`2_duplicated_trips`), and `stop_times_doors.txt` (`4_doors_time`, the
    final output). Run last, since it validates the fully processed data, despite being numbered
    `1_`. No file output.

14. **`processing/5_L9_L10_data_duplication.py`** *(work in progress)* — resolves L9/L10
    duplication on top of the final `4_doors_time` output.

---

## Why the jumping around

`checks/3_stop_times_checks.ipynb` is interleaved with three processing scripts because each
script needs a check to first detect what to fix (e.g. `wrong_stop_sequences.txt`), and the same
notebook is then re-run after the fix to confirm it worked. See
[`checks/README.md`](checks/README.md) and [`processing/README.md`](processing/README.md) for
the per-file/per-question breakdown; this page only fixes the order.
