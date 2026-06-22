# Pipeline Workflow

`checks/` and `processing/` are split by *kind* of file, not by run order. This page lists the
actual run order, end to end, from `0_raw` to `4_doors_time`.

There are two kinds of steps here:

- **Core pipeline** — a strict sequential chain. Each step's output is required by the next, so
  these must run in order.
- **Independent checks** — `checks/file_connection_checks.ipynb`, `checks/pathways_checks.ipynb`,
  `checks/trips_checks.ipynb`, and the *Does stop_sequence increment by one?* block of
  `checks/stop_times_checks.ipynb` only need `processing/1_subway.py` to have run. They don't
  produce any file consumed downstream, don't gate each other, and can run in any order (or be
  skipped) without affecting the rest of the pipeline.

---

## Core pipeline

1. **`processing/1_subway.py`** — `0_raw` → `1_subway`

   Extracts subway-only rows from `routes`, `stop_times`, `stops`, `trips`.

2. **`checks/stop_times_checks.ipynb`** → *Duplicate full trip_id blocs in stop_times*

   Reads `stop_times_subway.txt`/`trips_subway.txt` from `1_subway`.
   → produces `trip_ids_to_eliminate.txt` in `2_duplicated_trips`.

3. **`processing/2_duplicated_trips.py`** — `1_subway` → `2_duplicated_trips`

   Consumes `trip_ids_to_eliminate.txt` (step 2) to remove duplicate trips, writing
   `stop_times_cleaned.txt` and `trips_cleaned.txt`.

4. **`checks/stop_times_checks.ipynb`** → *The canonical stop sequence is followed correctly?*

   Reads `stop_times_cleaned.txt` (step 3).
   → produces `wrong_stop_sequences.txt` in `3_stop_sequence`.

5. **`processing/3_stop_sequence.py`** — `2_duplicated_trips` → `3_stop_sequence`

   Consumes `wrong_stop_sequences.txt` (step 4) to open sequence gaps, writing
   `stop_times_sequence.txt`.

6. **`checks/stop_times_checks.ipynb`** → *After the sequence fix* *(verification)*

   Re-runs the same canonical-order check on `stop_times_sequence.txt` (step 5); bad pairs should
   now be non-consecutive. No file output.

7. **`checks/stop_times_checks.ipynb`** → *Cases when arrival_time and departure_time is the
   same*

   Reads `stop_times_sequence.txt` (step 5) and `trips_cleaned.txt` (step 3).
   → produces `doors.txt` in `4_doors_time`.

8. **`processing/4_doors_time.py`** — `3_stop_sequence` → `4_doors_time`

   Consumes `doors.txt` (step 7) and `trips_cleaned.txt` (step 3) to adjust terminal-stop
   timestamps, writing `stop_times_doors.txt`.

9. **`checks/stop_times_checks.ipynb`** → *After the door-time fix* *(verification)*

   Re-runs the arrival/departure check on `stop_times_doors.txt` (step 8); no stop should still
   have `arrival_time == departure_time`. No file output.

10. **`processing/5_L9_L10_data_duplication.py`** *(work in progress)* — resolves L9/L10
    duplication on top of the final `4_doors_time` output.

---

## Independent checks

Run anytime after step 1 of the core pipeline. None of these produce a file consumed elsewhere.

- **`checks/file_connection_checks.ipynb`** — reads `pathways.txt` (`0_raw`, no subway-filtered
  equivalent exists because all available pathways are already only for the subway) and
  `routes_subway.txt`/`stops_subway.txt`/`stop_times_subway.txt`/`trips_subway.txt` (`1_subway`).
- **`checks/pathways_checks.ipynb`** — reads `pathways.txt`/`transfers.txt` (`0_raw`, no
  subway-filtered equivalent exists because all available pathways/transfers are already only
  for the subway) and `stops_subway.txt` (`1_subway`).
- **`checks/trips_checks.ipynb`** — reads `routes_subway.txt`/`trips_subway.txt` (`1_subway`).
- **`checks/stop_times_checks.ipynb`** → *Does stop_sequence increment by one?* — reads
  `stop_times_subway.txt`/`trips_subway.txt` (`1_subway`); duplicates don't affect a trip's own
  sequence continuity, so it doesn't need step 2's deduplication.

---

## Why the core pipeline jumps around

`checks/stop_times_checks.ipynb` is interleaved with three processing scripts because each
script needs a check to first detect what to fix (e.g. `wrong_stop_sequences.txt`), and the same
notebook is then re-run after the fix to confirm it worked. See
[`checks/README.md`](checks/README.md) and [`processing/README.md`](processing/README.md) for
the per-file/per-question breakdown; this page only fixes the order.
