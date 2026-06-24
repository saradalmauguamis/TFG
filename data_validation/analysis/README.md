# Data Analysis

Read-only scripts that answer specific research questions about the data. They print results but do not write any files.

---

### `directional_asymmetry.py` — directional travel time comparison

Reads: `stop_times_doors.txt` from `.src/gtfs/data/4_doors_time`

> Used to decide whether the graph needs to be directed or can be undirected: compares average a→b vs b→a travel time for each adjacent platform pair.

---

### `shared_platforms.py` — shared-platform travel time comparison

Reads:
- `stop_times_doors.txt` from `.src/gtfs/data/4_doors_time`
- `stops_subway.txt`from `.src/gtfs/data/1_subway`
- `trips_cleaned.txt` from `.src/gtfs/data/2_duplicated_trips`

> Used to decide whether it is necessary to duplicate the shared platforms so each line gets its own edge weight.

Compares average travel times across whichever lines share a platform. Shared platforms are derived automatically from `subway_route_names_stop_ids` (`scripts/basics.py`), grouped by the exact set of lines serving each one — no line names are hardcoded, so this generalizes to however many lines (and platforms) end up sharing stops.

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
