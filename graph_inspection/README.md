# Graph Inspection

Read-only tools that visualize and summarize the final weighted graph in
[`data/6_weights/weights.txt`](../data/6_weights/weights.txt), produced by
[`data_validation/processing/6_weights.py`](../data_validation/processing/README.md). Neither tool
implements a routing algorithm; see [`routing_algorithms/`](../routing_algorithms/README.md)
(Dijkstra, A*) for that.

```
graph_inspection/
├── graph_draw/
│   ├── graph.py
│   └── resources/
├── graph_report.py
└── subway_maps/
```

---

### `graph_draw/graph.py`

Draws Barcelona's subway graph (platforms, entries, and SW/PW/TF edges) as a PNG, using the
GTFS-derived weighted edges and stop coordinates. What gets drawn is controlled by module-level
constants instead of CLI flags:

- `SHOW_ALL_NODES_AND_EDGES`: also draw entry/exit nodes and PW/TF edges, not just platforms and
  SW.
- `SHOW_TF_EDGES`: when the above is `False`, also draw TF edges (solid grey lines).
- `CENTER_STOP_ID` / `RADIUS_DEGREES`: zoom the plot around a given stop_id. The PNG is saved to
  `graph.png`, or `graph_zoom_<stop>.png` when zoomed.

`resources/` holds the PNG(s) it generates.

### `graph_report.py`

Prints vertex/arrow/edge counts for `weights.txt`, split by kind (entry vs. platform, SW/TF/PW)
and by whether they involve a "duplicated" stop_id: one of the artificial per-line platforms
`5_shared_platforms_duplication.py` creates for a platform shared by several lines (see
`EQUIVALENCES_FILE`, `data/5_shared_platforms/equivalences.txt`). A vertex is any stop_id in
`weights.txt`; an arrow is one directed row; an edge is an undirected arrow pair (a->b and b->a
count as one edge). Ends with a reminder of what each vertex/edge kind means.

### `subway_maps/`

Reference JPGs of Barcelona's subway lines (one per line, plus the full network map), used for
visual cross-checking against `graph_draw.py`'s output and against the GTFS data more generally.

---

## The Graph

Vertices are stop_ids: an entry (`E.*`) is reachable from street level, a platform (`1.*`) is
where trains stop. Edges are directed rows of `weights.txt`, of three types:

- `SW` (platform -> platform): estimated train travel time.
- `TF` (platform <-> platform, same stop, different line): walking transfer time.
- `PW` (entry <-> platform, same stop): walking time.

A few design decisions shape this graph:

- **Directed.** Motivated by `data_validation/analysis/directional_asymmetry.py`, which found a->b and b->a
  travel times differ enough that collapsing them into a single undirected weight would lose
  real signal.
- **Synthetic per-line platforms.** Motivated by `data_validation/analysis/shared_platforms.py`, which found
  travel time through a platform shared by several lines differs per line, so
  `5_shared_platforms_duplication.py` splits such a stop_id into one per line instead of merging
  them (see `data/5_shared_platforms/equivalences.txt` file).
- **Weight = mean(travel time).** Motivated by `data_validation/analysis/edge_weight_validation.py`, which
  validated that a static mean is trustworthy for most `SW` edges, checked both for overall
  variability and time-of-day structure.

See [`data_validation/analysis/README.md`](../data_validation/analysis/README.md) and
[`data_validation/WORKFLOW.md`](../data_validation/WORKFLOW.md) for the full rationale and how
these three analyses fit into the pipeline order.
