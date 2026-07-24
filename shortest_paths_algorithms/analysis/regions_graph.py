"""Draw the Barcelona subway network colored by Center/Branch region, highlighting
the single bridge platform that reconnects each branch to the rest of the network.

Reuses graph_inspection/graph_draw/graph.py's graph loading (GTFS-derived edges,
weights, and the jittered synthetic-platform/entry positions) and recolors it
against shortest_paths_algorithms/barcelona_division.py's Center/Branches partition
instead of by subway line: every platform, every entry/exit, and every SW/TF/PW edge
touching it, is painted in its region's color, except the edge connecting a branch's
outermost platform to its bridge, which takes the branch's color (it's still part
of the branch, structurally), and the bridge platform itself, which is highlighted
in yellow, a color reserved from the region palette so it never doubles as a
region's color.
"""

import math
import sys
from pathlib import Path

import matplotlib.pyplot as plt
import networkx as nx

_PROJECT_ROOT = str(Path(__file__).resolve().parents[2])
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from graph_inspection.graph_draw.graph import load_graph  # noqa: E402
from shortest_paths_algorithms.barcelona_division import (  # noqa: E402
    Bridges,
    NODE_TO_BRANCH,
)
from shortest_paths_algorithms.paths import REGIONS_GRAPH_FILE  # noqa: E402

# Fixed hue order (never cycled), matching Branches' own definition order in
# barcelona_division.py, plus Center.
REGION_COLORS: dict[str, str] = {
    "Branch_L1": "#4a3aa7",
    "Branch_L2": "#e34948",
    "Branch_L5": "#008300",
    "Branch_L9S": "#e87ba4",
    "Branch_L9N": "#1baf7a",
    "Branch_L10S": "#2a78d6",
    "Branch_L11": "#eb6834",
    "Branch_FM": "#0088ad",
    "Center": "#a9b45f",
}

BRIDGE_COLOR = "#eda100"

BRIDGE_STOPS: set[str] = {stop for stops in Bridges.values() for stop in stops}

# Same weight->width formula as graph_draw/graph.py's EDGE_WIDTH_SCALE_BY_TYPE: SW
# and TF read at full scale, PW thinner, so SW keeps reading as the "trunk" line
# thickness it has in the original graph instead of a flat, weight-blind width.
EDGE_WIDTH_SCALE_BY_TYPE = {"SW": 1.0, "TF": 1.0, "PW": 0.4}


def node_region(stop_id: str) -> str:
    """Return stop_id's region name: its branch, or "Center" if not in a branch.

    args:
        stop_id: Platform stop_id (SW/TF/PW-platform-side edges only ever touch
            platforms, which are always covered by NODE_TO_BRANCH or Center).

    returns:
        A key of REGION_COLORS.
    """
    return NODE_TO_BRANCH.get(stop_id, "Center")


def region_edge_color(u: str, v: str) -> str:
    """Color an SW/TF edge: same-region color, or the branch's color if the edge
    crosses into Center (which can only be the branch's single bridge connection).

    args:
        u: Source platform stop_id.
        v: Target platform stop_id.

    returns:
        A value from REGION_COLORS.
    """
    region_u, region_v = node_region(u), node_region(v)
    if region_u == region_v:
        return REGION_COLORS[region_u]
    return REGION_COLORS[region_v if region_u == "Center" else region_u]


def pw_edge_color(u: str, v: str) -> str:
    """Color a PW edge by the region of whichever endpoint is the platform.

    args:
        u: One endpoint stop_id (platform or entry).
        v: The other endpoint stop_id.

    returns:
        A value from REGION_COLORS.
    """
    platform = v if str(u).startswith("E.") else u
    return REGION_COLORS[node_region(platform)]


def entry_node_color(entry_id: str, graph: nx.DiGraph) -> str:
    """Color an entry node the same as its PW edge: its connected platform's region color.

    args:
        entry_id: Entry/exit stop_id ("E." prefix).
        graph: Graph containing the entry's PW edge(s) to its platform(s).

    returns:
        A value from REGION_COLORS.
    """
    platform = next(
        neighbor
        for neighbor in set(graph.predecessors(entry_id))
        | set(graph.successors(entry_id))
        if str(neighbor).startswith("1.")
    )
    return REGION_COLORS[node_region(platform)]


def node_color(stop_id: str) -> str:
    """Color a platform node: yellow if it's a bridge, else its region's color.

    args:
        stop_id: Platform stop_id.

    returns:
        BRIDGE_COLOR or a value from REGION_COLORS.
    """
    if stop_id in BRIDGE_STOPS:
        return BRIDGE_COLOR
    return REGION_COLORS[node_region(stop_id)]


def draw_regions_graph(
    graph: nx.DiGraph, output_path: str | Path = REGIONS_GRAPH_FILE
) -> None:
    """Draw the whole graph colored by Center/Branch region and save it as a PNG.

    args:
        graph: Graph built by graph_inspection.graph_draw.graph.load_graph().
        output_path: Path to save the rendered PNG to.
    """
    pos = {n: d["pos"] for n, d in graph.nodes(data=True) if "pos" in d}
    graph = graph.subgraph(pos.keys())

    platform_nodes = [n for n in graph.nodes if not str(n).startswith("E.")]
    entry_nodes = [n for n in graph.nodes if str(n).startswith("E.")]
    bridge_nodes = [n for n in platform_nodes if n in BRIDGE_STOPS]
    non_bridge_platform_nodes = [n for n in platform_nodes if n not in BRIDGE_STOPS]

    _, ax = plt.subplots(figsize=(14, 14))
    legend_handles = [
        plt.Line2D(
            [0],
            [0],
            marker="o",
            color="none",
            markerfacecolor=color,
            markersize=10,
            label=region,
        )
        for region, color in REGION_COLORS.items()
    ] + [
        plt.Line2D(
            [0],
            [0],
            marker="D",
            color="none",
            markerfacecolor=BRIDGE_COLOR,
            markeredgecolor="#333333",
            markersize=10,
            label="Bridge vertices",
        ),
    ]

    edge_color_fn_by_type = {
        "SW": region_edge_color,
        "TF": region_edge_color,
        "PW": pw_edge_color,
    }
    # Compass: same convention as graph_inspection/graph_draw/graph.py's reference
    # graph, confirming the plot uses standard orientation (lon/lat as x/y, unflipped).
    compass_x, compass_y, arm = 0.20, 0.84, 0.03

    for edge_type, color_fn in edge_color_fn_by_type.items():
        type_edges = [
            (u, v) for u, v, d in graph.edges(data=True) if d["type"] == edge_type
        ]
        if not type_edges:
            continue
        edges_by_color: dict[str, list[tuple]] = {}
        for u, v in type_edges:
            edges_by_color.setdefault(color_fn(u, v), []).append((u, v))
        width_scale = EDGE_WIDTH_SCALE_BY_TYPE[edge_type]
        for color, edges in edges_by_color.items():
            widths = [
                math.log10(graph[u][v]["weight_seconds"] + 1) * width_scale
                for u, v in edges
            ]
            nx.draw_networkx_edges(
                graph,
                pos,
                edgelist=edges,
                width=widths,
                edge_color=color,
                arrows=False,
                ax=ax,
            )

    nx.draw_networkx_nodes(
        graph,
        pos,
        nodelist=entry_nodes,
        node_shape="s",
        node_size=6,
        node_color=[entry_node_color(n, graph) for n in entry_nodes],
        ax=ax,
    )
    nx.draw_networkx_nodes(
        graph,
        pos,
        nodelist=non_bridge_platform_nodes,
        node_shape="o",
        node_size=15,
        node_color=[node_color(n) for n in non_bridge_platform_nodes],
        ax=ax,
    )
    nx.draw_networkx_nodes(
        graph,
        pos,
        nodelist=bridge_nodes,
        node_shape="D",
        node_size=45,
        node_color=BRIDGE_COLOR,
        edgecolors="#333333",
        linewidths=1.2,
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

    ax.legend(
        handles=legend_handles,
        loc="lower right",
        bbox_to_anchor=(0.86, 0.08),
        fontsize=14,
    )

    ax.set_title("Barcelona Subway Network with Branches and Bridges")
    ax.set_axis_off()

    ax.text(
        0.01,
        0.01,
        "* Synthetic platform and entry/exit positions are artificially offset,"
        " not to real scale, for visual clarity.",
        transform=ax.transAxes,
        ha="left",
        va="bottom",
        fontsize=14,
        color="#666666",
    )

    plt.tight_layout()
    plt.savefig(output_path, dpi=200)
    plt.close()


if __name__ == "__main__":
    Path(REGIONS_GRAPH_FILE).parent.mkdir(parents=True, exist_ok=True)
    draw_regions_graph(load_graph())
