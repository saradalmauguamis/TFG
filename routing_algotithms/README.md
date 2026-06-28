# Routing Algorithms

```
routing_algotithms/
├── a*/
│   └── a*_example.py
├── dijkstra/
│   └── dijkstra_example.py
└── graph_draw/
    └── graph.py
```

## graph_draw/graph.py

Draws Barcelona's subway graph (platforms, entries, and SW/PW/TF edges) as a PNG, using
the GTFS-derived weighted edges and stop coordinates.

Run it with:

```
python -m routing_algotithms.graph_draw.graph
```

What gets drawn is controlled by module-level constants instead of CLI flags:
- `SHOW_ALL_NODES_AND_EDGES`: also draw entry/exit nodes and PW/TF edges, not just platforms and SW.
- `SHOW_TF_EDGES`: when the above is `False`, also draw TF edges (solid grey lines).
- `CENTER_STOP_ID` / `RADIUS_DEGREES`: zoom the plot around a given stop_id. The PNG is saved
  to `graph.png`, or `graph_zoom_<stop>.png` when zoomed.
