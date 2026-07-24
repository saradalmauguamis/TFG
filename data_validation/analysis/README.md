# Data Analysis

Read-only scripts that answer specific research questions about the data. Most print results without writing files; `edge_weight_validation.py` also writes its full printed report to disk, since it's long enough to be worth keeping around for reference.

---

### `shared_platforms.py` — shared-platform travel time comparison

Reads:
- `stop_times_doors.txt` from `data/4_doors_time`
- `stops_subway.txt`from `data/1_subway`
- `trips_cleaned.txt` from `data/2_duplicated_trips`

> Used to decide whether it is necessary to duplicate the shared platforms so each line gets its own edge weight.

Compares average travel times across whichever lines share a platform. Shared platforms are derived automatically from `subway_route_names_stop_ids` (`subway_reference/subway_lines.py`), grouped by the exact set of lines serving each one; no line names are hardcoded, so this generalizes to however many lines (and platforms) end up sharing stops.

Shared platforms currently detected:

**L9S / L10S**

| Stop ID | Name |
|---|---|
| 1.914 | Can Tries \| Gornal |
| 1.915 | Torrassa |
| 1.916 | Collblanc |

**L9N / L10N**

| Stop ID | Name |
|---|---|
| 1.930 | La Sagrera |
| 1.932 | Onze de Setembre |
| 1.933 | Bon Pastor |

---

### `directional_asymmetry.py` — directional travel time comparison

Reads: `stop_times_doors.txt` from `data/4_doors_time`

> Used to decide whether the graph needs to be directed or can be undirected: compares average a→b vs b→a travel time for each adjacent platform pair.

---

### `edge_weight_validation.py` — sw edge weight trustworthiness

Reads: `stop_times_shared.txt`/`stops_shared.txt` from `data/5_shared_platforms`, `trips_cleaned.txt` from `data/2_duplicated_trips`

> Used to decide whether `mean(total)` per directed platform-to-platform pair (`total = arrival_b - arrival_a`) is a trustworthy static weight for the `sw` edges of the shortest-path graph, or whether it needs a different treatment (better averaging, or a time-dependent weight).

For every directed consecutive-stop pair on every subway line, computes mean/stdev/CV from `total`, then ranks by CV (is the spread small relative to the mean?), and separately checks for a real rush/off-peak pattern via an hourly breakdown (does the mean hide a time-of-day shift a static weight would wash out?). Edges that cross the CV threshold also get `total` split into `door` (`departure_a - arrival_a`, dwell at the boarding platform) and `sw` (`arrival_b - departure_a`, time actually spent moving) as a diagnostic for *why* they're noisy; the edge weight itself stays `total`. Ends with a verdict: how many edges pass, how many need attention, and which test (CV, hourly range, or both) flagged each one.
