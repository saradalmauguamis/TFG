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
    EQUIVALENCES_SHARED_FILE,
    ROUTES_FILE,
    STOPS_FILE,
    SUBWAY_WEIGHTS_FILE,
    WEIGHTS_FILE,
)

EDGE_STYLE_BY_TYPE = {
    "SW": "solid",
    "PW": "dotted",
    "TF": "dashed",
}
EDGE_TYPE_LABELS = {
    "PW": "Pathway (PW)",
    "TF": "Transfer (TF)",
}
NON_LINE_EDGE_COLOR = "#444444"
FALLBACK_LINE_COLOR = "#999999"
PLATFORM_NODE_COLOR = "#4477AA"
SYNTHETIC_PLATFORM_NODE_COLOR = "#FFD700"

JITTER_DEGREES = 0.0015

# Manual jitter angle (radians) for the synthetic platforms in the shared-platform groups
# produced by the L9/L10 split in EQUIVALENCES_SHARED_FILE, keyed by stop_id. Each pair
# shares an axis (angle and angle + pi) so the two platforms sit side-by-side along their
# line instead of drifting across the other line's path (a derived angle was tried and
# produced visible crossings).
#
# NOT SCALABLE: this is tied to the current data_validation/processing output (specifically
# weights.txt and equivalences_shared.txt). If that pipeline ever changes which stops get
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
SHOW_ALL_NODES_AND_EDGES = False

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
        The set of "new_stop_id" values from EQUIVALENCES_SHARED_FILE.
    """
    equivalences = pd.read_csv(EQUIVALENCES_SHARED_FILE, dtype={"new_stop_id": str})
    return set(equivalences["new_stop_id"])


def load_graph() -> nx.DiGraph:
    """Build the directed stop graph with geographic positions and line colors.

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

    return graph


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
            {"SW": EDGE_STYLE_BY_TYPE["SW"], "TF": "solid"}
            if SHOW_TF_EDGES
            else {"SW": EDGE_STYLE_BY_TYPE["SW"]}
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
                color=NON_LINE_EDGE_COLOR,
                lw=2,
                linestyle=style,
                label=EDGE_TYPE_LABELS[edge_type],
            )
            for edge_type, style in edge_styles.items()
            if edge_type != "SW"
        ]
        + [
            plt.Line2D(
                [0],
                [0],
                marker="o",
                color="none",
                markerfacecolor=SYNTHETIC_PLATFORM_NODE_COLOR,
                markersize=14,
                label="Synthetic platform",
            )
        ]
    )
    _, ax = plt.subplots(figsize=fig_size)
    # Compass: confirms the plot uses standard orientation (lon/lat plotted directly as
    # x/y, unflipped), since there's no other visual cue once the axes are turned off.
    compass_x, compass_y, arm = 0.06, 0.92, 0.03

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
        node_size=10 * node_scale,
        node_color="#4477AA",
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
                widths = [
                    math.log10(graph[u][v]["weight_seconds"] + 1) * node_scale
                    for u, v in edges
                ]
                color = line_colors.get(line, FALLBACK_LINE_COLOR)
                nx.draw_networkx_edges(
                    graph,
                    pos,
                    edgelist=edges,
                    style=style,
                    width=widths,
                    edge_color=color,
                    arrows=False,
                    ax=ax,
                )
        else:
            widths = [
                math.log10(graph[u][v]["weight_seconds"] + 1) * node_scale
                for u, v in type_edges
            ]
            nx.draw_networkx_edges(
                graph,
                pos,
                edgelist=type_edges,
                style=style,
                width=widths,
                edge_color=NON_LINE_EDGE_COLOR,
                arrows=False,
                ax=ax,
            )

    ax.legend(handles=legend_handles, loc="lower right", fontsize=14)

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

    g = load_graph()
    draw_graph(
        g,
        center_stop_id=CENTER_STOP_ID,
        radius_degrees=RADIUS_DEGREES,
        output_path=output_path,
    )
