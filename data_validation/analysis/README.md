# Data Analysis

Read-only scripts that answer specific research questions about the data. They print results but do not write any files.

---

### `between_platforms.py` — directional travel time comparison

Reads: `stop_times_sequence.txt` from `.src/gtfs/data/3_stop_sequence`

> Used to decide whether the graph needs to be directed or can be undirected: compares average a→b vs b→a travel time for each adjacent platform pair.

---

### `L9_L10.py` — L9 / L10 shared platform travel times

Reads:
- `stop_times_sequence.txt` from `.src/gtfs/data/3_stop_sequence`
- `trips_cleaned.txt` from `.src/gtfs/data/2_duplicated_trips`

> Used to decide whether it is necessary to duplicate artificially the shared stops to avoid having the same edge weight regardless of the line: compares average travel times between L9 and L10 on their shared platforms.

Shared platforms analysed:

**South (L9S / L10S)**

| Stop ID | Name |
|---|---|
| 1.914 | Can Tries \| Gornal |
| 1.915 | Torrassa |
| 1.916 | Collblanc |

**North (L9N / L10N)**

| Stop ID | Name |
|---|---|
| 1.930 | La Sagrera |
| 1.932 | Onze de Setembre |
| 1.933 | Bon Pastor |
