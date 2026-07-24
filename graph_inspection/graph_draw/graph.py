"""Draw the Barcelona's subway graph from the weighted edges and stop coordinates.

Nodes are GTFS stops, identified by their stop_id prefix:
    - "1." platform: an actual stop where trains arrive/depart.
    - "E." entry/exit: a street-level access point to a station.

Edges come from precomputed GTFS relationships in WEIGHTS_FILE (built by
data_validation/processing/6_weights.py), not from geographic proximity:
    - "SW" subway: platform-to-platform, from consecutive stops in
      stop_times.txt; weight is the mean scheduled travel time.
    - "PW" pathway: entry-to-platform (or vice versa), from pathways.txt;
      weight is the traversal_time.
    - "TF" transfer: platform-to-platform across lines, from transfers.txt;
      weight is the min_transfer_time.

A few stops are split into two synthetic platforms (one per line) that share the same
coordinates; SYNTHETIC_PLATFORM_JITTER_ANGLE hardcodes a manual offset for each so they're
drawn side-by-side instead of overlapping or crossing their own line. See that constant's
docstring for why this isn't derived automatically.
"""

import math
import random
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import networkx as nx
import pandas as pd

_PROJECT_ROOT = str(Path(__file__).resolve().parents[2])
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from data_validation.gtfs_utils import (  # noqa: E402
    EQUIVALENCES_FILE,
    ROUTES_FILE,
    STOPS_FILE,
    SUBWAY_WEIGHTS_FILE,
    WEIGHTS_FILE,
)

EDGE_STYLE_BY_TYPE = {
    "SW": "solid",
    "PW": "solid",
    "TF": "solid",
}
EDGE_TYPE_LABELS = {
    "PW": "Pathway (PW)",
    "TF": "Transfer (TF)",
}
NON_LINE_EDGE_COLOR = "#444444"
PW_EDGE_COLOR = "#bbbbbb"
EDGE_COLOR_BY_TYPE = {
    "PW": PW_EDGE_COLOR,
    "TF": NON_LINE_EDGE_COLOR,
}
EDGE_WIDTH_SCALE_BY_TYPE = {
    "SW": 2,
    "PW": 1.0,
    "TF": 1.2,
}
FALLBACK_LINE_COLOR = "#999999"
PLATFORM_NODE_COLOR = "#4477AA"
SYNTHETIC_PLATFORM_NODE_COLOR = "#FFD700"
ENTRY_NODE_COLOR = PW_EDGE_COLOR

JITTER_DEGREES = 0.0015

# Real entry-to-platform distances (from WEIGHTS_FILE's PW edges) range ~0.00008-0.0025
# degrees, mean ~0.00066: real, but reads as "on top of the platform" at whole-graph scale.
# This multiplies that real (platform -> entry) vector so the separation is visible; only
# applied when rendering the whole graph (CENTER_STOP_ID is None) since a zoomed-in view
# already shows the real distance clearly enough.
ENTRY_OFFSET_MULTIPLIER_WHOLE_GRAPH = 4

# Manual jitter angle (radians) for the synthetic platforms in the shared-platform groups
# produced by the L9/L10 split in EQUIVALENCES_FILE, keyed by stop_id. Each pair
# shares an axis (angle and angle + pi) so the two platforms sit side-by-side along their
# line instead of drifting across the other line's path (a derived angle was tried and
# produced visible crossings).
#
# NOT SCALABLE: this is tied to the current data_validation/processing output (specifically
# weights.txt and equivalences.txt). If that pipeline ever changes which stops get
# split or how, this table must be recomputed or removed; any duplicate-coordinate group
# without both members listed here falls back to a uniformly random offset.
SYNTHETIC_PLATFORM_JITTER_ANGLE: dict[str, float] = {
    # -- South --
    "1.9140": math.pi,
    "1.9141": 0,
    "1.9150": math.pi * 3 / 4,
    "1.9151": math.pi * 3 / 4 + math.pi,
    "1.9160": math.pi / 2,
    "1.9161": math.pi / 2 + math.pi,
    # -- North --
    "1.9300": math.pi,
    "1.9301": 0,
    "1.9320": math.pi,
    "1.9321": 0,
    "1.9330": math.pi,
    "1.9331": 0,
}

# What gets drawn is controlled by these module-level constants instead of CLI flags.

# Set to True to also draw entry/exit nodes and PW/TF edges, not just platforms and SW.
SHOW_ALL_NODES_AND_EDGES = True

# Only applies when SHOW_ALL_NODES_AND_EDGES is False: also draw TF edges, as solid grey lines.
SHOW_TF_EDGES = True

# stop_id to (like "1.133") zoom into, or None to draw the whole graph.
CENTER_STOP_ID: str | None = None
# Half-width of the zoom window in degrees (0.004 ~ 400m). Only used when CENTER_STOP_ID is set.
RADIUS_DEGREES = 0.004

# The PNG is saved to resources/graph.png, or resources/graph_zoom_<stop>.png when zoomed.


def load_line_colors() -> dict[str, str]:
    """Map subway line short name (e.g. "L1") to its "#RRGGBB" route_color.

    returns:
        Mapping from route_short_name to a "#RRGGBB" color string.
    """
    routes = pd.read_csv(ROUTES_FILE)
    return {
        row["route_short_name"]: f"#{row['route_color']}"
        for _, row in routes.iterrows()
    }


def load_edge_lines() -> dict[tuple[str, str], str]:
    """Map a directed (from_stop_id, to_stop_id) SW pair to its line short name.

    returns:
        Mapping from a directed stop pair to its subway line short name.
    """
    subway_edges = pd.read_csv(
        SUBWAY_WEIGHTS_FILE, dtype={"from_stop_id": str, "to_stop_id": str}
    )
    return {
        (row["from_stop_id"], row["to_stop_id"]): row["line"]
        for _, row in subway_edges.iterrows()
    }


def load_synthetic_platform_ids() -> set[str]:
    """List platform stop_ids artificially created to split a shared platform per line.

    returns:
        The set of "new_stop_id" values from EQUIVALENCES_FILE.
    """
    equivalences = pd.read_csv(EQUIVALENCES_FILE, dtype={"new_stop_id": str})
    return set(equivalences["new_stop_id"])


def load_graph(amplify_entries: bool = True) -> nx.DiGraph:
    """Build the directed stop graph with geographic positions and line colors.

    args:
        amplify_entries: Whether to amplify_entry_offsets (see its docstring) so
            entry/exit positions read as separate from their platform. Defaults to True
            for whole-graph callers (regions_graph.py, extracted_nodes_graph.py, this
            module's own __main__ when unzoomed); a zoomed view already shows the real
            distance clearly enough, so draw_graph's own __main__ call passes False then.

    returns:
        Graph with each edge tagged by weight_seconds, type and (for SW
        edges) line, and each node tagged with a jittered (lon, lat) "pos".
    """
    edges = pd.read_csv(WEIGHTS_FILE, dtype={"from_stop_id": str, "to_stop_id": str})
    stops = pd.read_csv(STOPS_FILE, dtype={"stop_id": str})
    edge_lines = load_edge_lines()
    graph = nx.DiGraph()
    coords = stops.set_index("stop_id")[["stop_lon", "stop_lat"]]
    rng = random.Random(0)
    groups: dict[tuple[float, float], list[str]] = {}

    for _, row in edges.iterrows():
        line = edge_lines.get((row["from_stop_id"], row["to_stop_id"]))
        graph.add_edge(
            row["from_stop_id"],
            row["to_stop_id"],
            weight_seconds=row["weight_seconds"],
            type=row["type"],
            line=line,
        )

    for node in graph.nodes:
        if node not in coords.index:
            continue
        lon, lat = coords.loc[node, ["stop_lon", "stop_lat"]]
        groups.setdefault((lon, lat), []).append(node)

    for (lon, lat), members in groups.items():
        if len(members) == 1:
            graph.nodes[members[0]]["pos"] = (lon, lat)
            continue

        if all(member in SYNTHETIC_PLATFORM_JITTER_ANGLE for member in members):
            for member in members:
                angle = SYNTHETIC_PLATFORM_JITTER_ANGLE[member]
                graph.nodes[member]["pos"] = (
                    lon + (JITTER_DEGREES / 2) * math.cos(angle),
                    lat + (JITTER_DEGREES / 2) * math.sin(angle),
                )
            continue

        # Not one of the known shared-platform groups: fall back to a random offset.
        members = sorted(members)
        graph.nodes[members[0]]["pos"] = (lon, lat)
        for i, member in enumerate(members[1:], start=1):
            angle = rng.uniform(0, 2 * math.pi)
            graph.nodes[member]["pos"] = (
                lon + JITTER_DEGREES * i * math.cos(angle),
                lat + JITTER_DEGREES * i * math.sin(angle),
            )

    if amplify_entries:
        amplify_entry_offsets(graph, ENTRY_OFFSET_MULTIPLIER_WHOLE_GRAPH)

    return graph


def amplify_entry_offsets(graph: nx.DiGraph, multiplier: float) -> None:
    """Scale up each entry's real-world offset from its connected platform(s).

    Real GTFS entry coordinates sit only a few meters from their platform (mean ~0.00066
    degrees, see graph_draw's ENTRY_OFFSET_MULTIPLIER_WHOLE_GRAPH comment), which reads as
    directly on top of it at whole-graph scale. This multiplies the existing
    (platform -> entry) vector by `multiplier`, keeping its real direction but making the
    separation visible; entries that are naturally farther from their platform stay
    proportionally farther after scaling.

    args:
        graph: Graph with "pos" already set on every node from real coordinates, and PW
            edges connecting each entry to its platform(s).
        multiplier: Factor to scale each platform->entry vector by.
    """
    rng = random.Random(1)
    for node, data in graph.nodes(data=True):
        if not str(node).startswith("E.") or "pos" not in data:
            continue
        platform_positions = [
            graph.nodes[neighbor]["pos"]
            for neighbor in set(graph.predecessors(node)) | set(graph.successors(node))
            if str(neighbor).startswith("1.") and "pos" in graph.nodes[neighbor]
        ]
        if not platform_positions:
            continue
        platform_lon = sum(p[0] for p in platform_positions) / len(platform_positions)
        platform_lat = sum(p[1] for p in platform_positions) / len(platform_positions)
        entry_lon, entry_lat = data["pos"]
        dx, dy = entry_lon - platform_lon, entry_lat - platform_lat
        if math.hypot(dx, dy) < 1e-12:
            angle = rng.uniform(0, 2 * math.pi)
            dx, dy = JITTER_DEGREES * math.cos(angle), JITTER_DEGREES * math.sin(angle)
        graph.nodes[node]["pos"] = (
            platform_lon + dx * multiplier,
            platform_lat + dy * multiplier,
        )


def draw_graph(
    graph: nx.DiGraph,
    center_stop_id: str | None = None,
    radius_degrees: float = 0.004,
    output_path: str | Path = Path(__file__).resolve().parent
    / "resources"
    / "graph.png",
) -> None:
    """Draw the stop graph and save it as a PNG, optionally zoomed on a stop.

    args:
        graph: Graph built by `load_graph`.
        center_stop_id: If given, zoom the plot around this stop_id.
        radius_degrees: Half-width of the zoom window in degrees.
        output_path: Path to save the rendered PNG to.
    """
    legend_handles: list[plt.Line2D] = []
    _ = None
    ax: plt.Axes | None = None
    compass_x = 0.0
    compass_y = 0.0
    arm = 0.0
    footnote = ""

    pos = {n: d["pos"] for n, d in graph.nodes(data=True) if "pos" in d}
    graph = graph.subgraph(pos.keys())
    zoomed = center_stop_id is not None
    fig_size = (10, 10) if zoomed else (14, 14)
    node_scale = 6 if zoomed else 1
    line_colors = load_line_colors()
    synthetic_platform_ids = load_synthetic_platform_ids()
    platform_nodes = [
        n
        for n in graph.nodes
        if not str(n).startswith("E.") and n not in synthetic_platform_ids
    ]
    synthetic_platform_nodes = [
        n
        for n in graph.nodes
        if not str(n).startswith("E.") and n in synthetic_platform_ids
    ]
    entry_nodes = (
        [n for n in graph.nodes if str(n).startswith("E.")]
        if SHOW_ALL_NODES_AND_EDGES
        else []
    )
    edge_styles = (
        EDGE_STYLE_BY_TYPE
        if SHOW_ALL_NODES_AND_EDGES
        else (
            {"SW": EDGE_STYLE_BY_TYPE["SW"], "TF": EDGE_STYLE_BY_TYPE["TF"]}
            if SHOW_TF_EDGES
            else {"SW": EDGE_STYLE_BY_TYPE["SW"]}
        )
    )
    node_type_handles = [
        plt.Line2D(
            [0],
            [0],
            marker="o",
            color="none",
            markerfacecolor=PLATFORM_NODE_COLOR,
            markersize=10,
            label="Platform",
        ),
    ]
    if SHOW_ALL_NODES_AND_EDGES:
        node_type_handles.append(
            plt.Line2D(
                [0],
                [0],
                marker="s",
                color="none",
                markerfacecolor=ENTRY_NODE_COLOR,
                markersize=8,
                label="Entry/Exit",
            )
        )
    node_type_handles.append(
        plt.Line2D(
            [0],
            [0],
            marker="o",
            color="none",
            markerfacecolor=SYNTHETIC_PLATFORM_NODE_COLOR,
            markersize=14,
            label="Synthetic platform",
        )
    )

    legend_handles = (
        [
            plt.Line2D([0], [0], color=color, lw=4, label=line)
            for line, color in line_colors.items()
        ]
        + [
            plt.Line2D(
                [0],
                [0],
                color=EDGE_COLOR_BY_TYPE[edge_type],
                lw=2,
                linestyle=style,
                label=EDGE_TYPE_LABELS[edge_type],
            )
            for edge_type, style in edge_styles.items()
            if edge_type != "SW"
        ]
        + node_type_handles
    )
    _, ax = plt.subplots(figsize=fig_size)
    # Compass: confirms the plot uses standard orientation (lon/lat plotted directly as
    # x/y, unflipped), since there's no other visual cue once the axes are turned off.
    compass_x, compass_y, arm = 0.20, 0.84, 0.03

    nx.draw_networkx_nodes(
        graph,
        pos,
        nodelist=platform_nodes,
        node_shape="o",
        node_size=15 * node_scale,
        node_color=PLATFORM_NODE_COLOR,
        ax=ax,
    )
    nx.draw_networkx_nodes(
        graph,
        pos,
        nodelist=synthetic_platform_nodes,
        node_shape="o",
        node_size=15 * node_scale,
        node_color=SYNTHETIC_PLATFORM_NODE_COLOR,
        ax=ax,
    )
    nx.draw_networkx_nodes(
        graph,
        pos,
        nodelist=entry_nodes,
        node_shape="s",
        node_size=6 * node_scale,
        node_color=ENTRY_NODE_COLOR,
        ax=ax,
    )

    for edge_type, style in edge_styles.items():
        type_edges = [
            (u, v) for u, v, d in graph.edges(data=True) if d["type"] == edge_type
        ]
        if not type_edges:
            continue

        if edge_type == "SW":
            edges_by_line: dict[str | None, list[tuple]] = {}
            for u, v in type_edges:
                line = graph[u][v]["line"]
                edges_by_line.setdefault(line, []).append((u, v))
            for line, edges in edges_by_line.items():
                color = line_colors.get(line, FALLBACK_LINE_COLOR)
                nx.draw_networkx_edges(
                    graph,
                    pos,
                    edgelist=edges,
                    style=style,
                    width=node_scale * EDGE_WIDTH_SCALE_BY_TYPE["SW"],
                    edge_color=color,
                    arrows=False,
                    ax=ax,
                )
        else:
            width_scale = EDGE_WIDTH_SCALE_BY_TYPE[edge_type]
            nx.draw_networkx_edges(
                graph,
                pos,
                edgelist=type_edges,
                style=style,
                width=node_scale * width_scale,
                edge_color=EDGE_COLOR_BY_TYPE[edge_type],
                arrows=False,
                ax=ax,
            )

    ax.legend(
        handles=legend_handles,
        loc="lower right",
        bbox_to_anchor=(0.86, 0.08),
        fontsize=14,
    )

    if zoomed:
        center_lon, center_lat = pos[center_stop_id]
        ax.set_xlim(center_lon - radius_degrees, center_lon + radius_degrees)
        ax.set_ylim(center_lat - radius_degrees, center_lat + radius_degrees)
        visible = {
            n: p
            for n, p in pos.items()
            if center_lon - radius_degrees <= p[0] <= center_lon + radius_degrees
            and center_lat - radius_degrees <= p[1] <= center_lat + radius_degrees
        }
        nx.draw_networkx_labels(
            graph,
            visible,
            labels={n: n for n in visible},
            font_size=7,
            ax=ax,
        )

    ax.plot(
        [compass_x - arm, compass_x + arm],
        [compass_y, compass_y],
        color="black",
        lw=1,
        transform=ax.transAxes,
    )
    ax.plot(
        [compass_x, compass_x],
        [compass_y - arm, compass_y + arm],
        color="black",
        lw=1,
        transform=ax.transAxes,
    )
    for label, (dx, dy) in {
        "N": (0, arm * 1.8),
        "S": (0, -arm * 1.8),
        "E": (arm * 1.8, 0),
        "W": (-arm * 1.8, 0),
    }.items():
        ax.annotate(
            label,
            xy=(compass_x + dx, compass_y + dy),
            xycoords="axes fraction",
            ha="center",
            va="center",
            fontsize=10,
            fontweight="bold",
        )

    ax.set_title(
        "Barcelona's subway graph"
    )  # "Barcelona's subway graph (node shape = platform/entry, line style = edge type)"
    ax.set_axis_off()

    footnote = (
        "* Synthetic platform positions are artificially offset so they sit side-by-side"
        " instead of overlapping."
    )
    if not zoomed and entry_nodes:
        footnote += (
            " Entry/exit positions are artificially exaggerated (not to real scale)"
            " for visual clarity."
        )
    ax.text(
        0.01,
        0.01,
        footnote,
        transform=ax.transAxes,
        ha="left",
        va="bottom",
        fontsize=9,
        color="#666666",
    )

    plt.tight_layout()
    plt.savefig(output_path, dpi=200)
    plt.close()


if __name__ == "__main__":
    resources_dir = Path(__file__).resolve().parent / "resources"
    resources_dir.mkdir(exist_ok=True)
    if CENTER_STOP_ID is not None:
        output_path = resources_dir / f"graph_zoom_{CENTER_STOP_ID}.png"
    else:
        output_path = resources_dir / "graph.png"

    g = load_graph(amplify_entries=CENTER_STOP_ID is None)
    draw_graph(
        g,
        center_stop_id=CENTER_STOP_ID,
        radius_degrees=RADIUS_DEGREES,
        output_path=output_path,
    )
