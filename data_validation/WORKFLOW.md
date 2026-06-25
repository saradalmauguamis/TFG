# Pipeline Workflow

`checks/` and `processing/` are split by *kind* of file, not by run order. This page lists the
actual run order, end to end, from `0_raw` to `5_shared_platforms`.

There are two kinds of steps here:

- **Core pipeline** — a strict sequential chain. Each step's output is required by the next, so
  these must run in order.
- **Independent checks** — `checks/file_connection_checks.ipynb`, `checks/pathways_checks.ipynb`,
  `checks/trips_checks.ipynb`, and `checks/stop_times/sequence_increment_check.py` only need
  `processing/1_subway.py` to have run. They don't produce any file consumed downstream, don't
  gate each other, and can run in any order (or be skipped) without affecting the rest of the
  pipeline.

---

## Core pipeline

1. **`processing/1_subway.py`** — `0_raw` → `1_subway`

   Extracts subway-only rows from `routes`, `stop_times`, `stops`, `trips`.

2. **`checks/stop_times/1_duplicate_trips_check.py`** → *Duplicate full trip_id blocs in stop_times*

   ```bash
   python data_validation/checks/stop_times/1_duplicate_trips_check.py
   ```

   Reads `stop_times_subway.txt`/`trips_subway.txt` from `1_subway`.
   → produces `trip_ids_to_eliminate.txt` in `2_duplicated_trips`.

3. **`processing/2_duplicated_trips.py`** — `1_subway` → `2_duplicated_trips`

   Consumes `trip_ids_to_eliminate.txt` (step 2) to remove duplicate trips, writing
   `stop_times_cleaned.txt` and `trips_cleaned.txt`.

4. **`checks/stop_times/1_duplicate_trips_check.py verify`** *(verification)*

   ```bash
   python data_validation/checks/stop_times/1_duplicate_trips_check.py verify
   ```

   Re-runs the same duplicate-detection check on `stop_times_cleaned.txt`/`trips_cleaned.txt`
   (step 3); no signature should now map to 2+ trip_id. No file output.

5. **`checks/stop_times/2_canonical_sequence_check.py`** → *The canonical stop sequence is
   followed correctly?*

   ```bash
   python data_validation/checks/stop_times/2_canonical_sequence_check.py
   ```

   Reads `stop_times_cleaned.txt` (step 3).
   → produces `wrong_stop_sequences.txt` in `3_stop_sequence`.

6. **`processing/3_stop_sequence.py`** — `2_duplicated_trips` → `3_stop_sequence`

   Consumes `wrong_stop_sequences.txt` (step 5) to open sequence gaps, writing
   `stop_times_sequence.txt`.

7. **`checks/stop_times/2_canonical_sequence_check.py verify`** *(verification)*

   ```bash
   python data_validation/checks/stop_times/2_canonical_sequence_check.py verify
   ```

   Re-runs the same canonical-order check on `stop_times_sequence.txt` (step 6); bad pairs should
   now be non-consecutive. No file output.

8. **`checks/stop_times/3_door_times_check.py`** → *Cases when arrival_time and departure_time is
   the same*

   ```bash
   python data_validation/checks/stop_times/3_door_times_check.py
   ```

   Reads `stop_times_sequence.txt` (step 6) and `trips_cleaned.txt` (step 3).
   → produces `doors.txt` in `4_doors_time`.

9. **`processing/4_doors_time.py`** — `3_stop_sequence` → `4_doors_time`

   Consumes `doors.txt` (step 8) and `trips_cleaned.txt` (step 3) to adjust terminal-stop
   timestamps, writing `stop_times_doors.txt`.

10. **`checks/stop_times/3_door_times_check.py verify`** *(verification)*

    ```bash
    python data_validation/checks/stop_times/3_door_times_check.py verify
    ```

    Re-runs the arrival/departure check on `stop_times_doors.txt` (step 9); no stop should still
    have `arrival_time == departure_time`. No file output.

11. **`processing/5_shared_platforms_duplication.py`** — `4_doors_time` (+ `0_raw` pathways/transfers,
    `1_subway` stops, `2_duplicated_trips` trips) → `5_shared_platforms`

    Splits every platform shared by more than one line (detected generically from
    `scripts/basics.py`, not hardcoded) into one stop_id per line across stops, pathways,
    transfers, and stop_times, plus an `equivalences_shared.txt` lookup table. See
    [`processing/README.md`](processing/README.md) for the per-file behavior. Motivated by
    `analysis/shared_platforms.py` below.

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
- **`checks/stop_times/sequence_increment_check.py`** — reads
  `stop_times_subway.txt`/`trips_subway.txt` (`1_subway`); duplicates don't affect a trip's own
  sequence continuity, so it doesn't need step 2's deduplication.

---

## Decision-support analyses

Read-only scripts in [`analysis/`](analysis/README.md). Unlike *Independent checks*, these need
the pipeline through step 9 (`stop_times_doors.txt`), not just step 1 — they don't produce any
file consumed downstream, but answer design questions for the graph build.

- **`analysis/shared_platforms.py`** — reads `stop_times_doors.txt` (step 9), `stops_subway.txt`
  (`1_subway`), `trips_cleaned.txt` (step 3). Compared travel times across lines sharing a
  platform (e.g. L9S/L10S, L9N/L10N) and found they differ, which is what motivated step 11.
- **`analysis/directional_asymmetry.py`** — same inputs. A separate, unrelated question: compared
  a→b vs b→a travel times to decide the graph needs directed edges. Doesn't motivate step 11.

---

## Why the core pipeline jumps around

The `checks/stop_times/` scripts are interleaved with three processing scripts because each
script needs a check to first detect what to fix (e.g. `wrong_stop_sequences.txt`), and the same
check script is then re-run with `verify` after the fix to confirm it worked. See
[`checks/README.md`](checks/README.md) and [`processing/README.md`](processing/README.md) for
the per-file/per-question breakdown; this page only fixes the order.
