"""Draw, over the whole subway graph, which nodes/edges cut-Dijkstra and each A*
heuristic (h_geo, h_bcn, h_cheat) actually extracted while searching SOURCE -> TARGET.

The whole graph (graph_inspection/graph_draw/graph.py's load_graph, same source as
routing_algorithms/analysis/regions_graph.py) is painted light grey first, then each
algorithm's extracted nodes and shortest-path-tree edges (parent links) are layered on
top of it, in a fixed order: Cut-Dijkstra, then A* (h_geo), A* (h_bcn), A* (h_cheat) --
COLOR_BY_HEURISTIC's own order (routing_algorithms/analysis/algorithms_comparison.py),
reused here directly so a heuristic's color always means the same thing across every
chart in this package. Later layers paint over earlier ones wherever two algorithms
extract the same node/edge.

`expanded` (which nodes were extracted before the search stopped) is not part of either
algorithm's pseudocode -- see a_star_utils.py's a_star() and dijkstra_utils.py's
_run_dijkstra() for where it's tracked purely for this kind of traceability -- but
`parent` already is, for both algorithms.

Output_name: {REGION_CASE}_{SOURCE}_to_{TARGET}.png saved into
'routing_algorithms/analysis/resources/extracted_nodes' (EXTRACTED_NODES_DIR,
routing_algorithms/paths.py). REGION_CASE is a free-form label (e.g. one of
barcelona_division.classify's CC/CB/BC/SB/DB cases) used only for the filename, not
recomputed from SOURCE/TARGET -- set it by hand to whatever case that pair demonstrates.

Since the deliverable is the PNG alone (no companion .txt report), everything that would
otherwise be printed -- the shortest path (stop id + name, same format as
print_path_summary in routing_algorithms/algorithms_utils.py, but one node per line
instead of joined by "->") and each algorithm's iterations/proportion
(path_vertices / iterations, same metric as routing_algorithms/reports/) -- is drawn
directly on the figure: the path as a sidebar in the plot's top-left corner,
iterations/proportion folded into each algorithm's own legend entry.
"""

from __future__ import annotations

import math
import sys
from functools import partial
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

import matplotlib.pyplot as plt
import networkx as nx

_PROJECT_ROOT = str(Path(__file__).resolve().parents[2])
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

from scripts.basics import subway_route_names_stop_ids_artificial  # noqa: E402

from data_validation.gtfs_utils import (  # noqa: E402
    PATHWAYS_FILE,
    STOPS_FILE,
    WEIGHTS_FILE,
    build_graph_and_coverage,
    build_stop_to_lines,
    check_missing_files,
    invert_entries,
    load_pathway_ids,
    load_stop_names,
    print_file_disclaimer,
)
from graph_inspection.graph_draw.graph import load_graph  # noqa: E402
from routing_algorithms.algorithms_utils import (  # noqa: E402
    Graph,
    Node,
    NodeFmt,
    apply_liceu_entrance_fix,
    build_graph_from_weights,
    format_node_label,
    print_graph_size,
    rebuild_path,
    stop_label,
)
from routing_algorithms.analysis.algorithms_comparison import (  # noqa: E402
    COLOR_BY_HEURISTIC,
    LEGEND_LABEL_BY_HEURISTIC,
)
from routing_algorithms.analysis.regions_graph import (  # noqa: E402
    EDGE_WIDTH_SCALE_BY_TYPE,
)
from routing_algorithms.a_star.a_star_utils import Heuristic, a_star  # noqa: E402
from routing_algorithms.a_star.heuristics.h_geo import (  # noqa: E402
    Coord,
    build_h_geo,
    compute_v_max,
    load_node_coords,
)
from routing_algorithms.a_star.heuristics.h_cheat import build_h_cheat  # noqa: E402
from routing_algorithms.a_star.heuristics.h_bcn import (  # noqa: E402
    DepthTable,
    build_depth_tables,
    build_h_bcn,
)
from routing_algorithms.dijkstra.dijkstra_utils import cut_dijkstra  # noqa: E402
from routing_algorithms.paths import EXTRACTED_NODES_DIR  # noqa: E402

SOURCE = "1.417"
TARGET = "1.314"
REGION_CASE = (
    "CC"  # free-form label for this pair's case (e.g. classify's CC/CB/BC/SB/DB)
)

# One run per (label, parent, expanded, iterations): parent/expanded come straight out
# of cut_dijkstra/a_star, iterations is that run's own extracted-node count.
Run = Tuple[Dict[Node, Optional[Node]], Dict[Node, bool], int]

BASE_COLOR = (
    "#cccccc"  # unvisited nodes/edges, painted first, everything else layers on top
)
BASE_PLATFORM_NODE_SIZE = 15
BASE_ENTRY_NODE_SIZE = 6
EXTRACTED_PLATFORM_NODE_SIZE = 20
EXTRACTED_ENTRY_NODE_SIZE = 10

# SOURCE/TARGET are painted last, in their own reserved colors/shapes (neither used by
# BASE_COLOR nor any COLOR_BY_HEURISTIC value), so they stay visible above every algorithm
# layer no matter which algorithms extracted them.
SOURCE_COLOR = "#1a1a1a"
TARGET_COLOR = "#e6007e"
ENDPOINT_NODE_SIZE = 160


def draw_base_layer(
    ax: plt.Axes, graph: nx.DiGraph, pos: Dict[Node, Tuple[float, float]]
) -> None:
    """Paint every node and edge of the whole subway graph BASE_COLOR (light grey).

    args:
        ax: Axes to draw onto.
        graph: The positioned subway graph (load_graph output, already restricted to
            nodes with a "pos", same as regions_graph.py).
        pos: node -> (lon, lat), from graph's own "pos" node attribute.
    """
    platform_nodes = [n for n in graph.nodes if not str(n).startswith("E.")]
    entry_nodes = [n for n in graph.nodes if str(n).startswith("E.")]

    for edge_type, width_scale in EDGE_WIDTH_SCALE_BY_TYPE.items():
        type_edges = [
            (u, v) for u, v, d in graph.edges(data=True) if d["type"] == edge_type
        ]
        if not type_edges:
            continue
        widths = [
            math.log10(graph[u][v]["weight_seconds"] + 1) * width_scale
            for u, v in type_edges
        ]
        nx.draw_networkx_edges(
            graph,
            pos,
            edgelist=type_edges,
            width=widths,
            edge_color=BASE_COLOR,
            arrows=False,
            ax=ax,
        )

    nx.draw_networkx_nodes(
        graph,
        pos,
        nodelist=platform_nodes,
        node_shape="o",
        node_size=BASE_PLATFORM_NODE_SIZE,
        node_color=BASE_COLOR,
        ax=ax,
    )
    nx.draw_networkx_nodes(
        graph,
        pos,
        nodelist=entry_nodes,
        node_shape="s",
        node_size=BASE_ENTRY_NODE_SIZE,
        node_color=BASE_COLOR,
        ax=ax,
    )


def extracted_nodes_and_edges(
    expanded: Dict[Node, bool],
    parent: Dict[Node, Optional[Node]],
    graph: nx.DiGraph,
) -> Tuple[List[Node], List[Tuple[Node, Node]]]:
    """Return one algorithm's settled nodes and the shortest-path-tree edges linking them.

    args:
        expanded: node -> whether it was extracted, from cut_dijkstra/a_star.
        parent: node -> its parent in the shortest-path tree, from the same run.
        graph: The positioned subway graph, already restricted to nodes with a "pos".

    returns:
        (nodes, edges): extracted nodes present in graph, and each one's (parent, node)
        edge, restricted to edges that exist in graph (a parent link only ever comes
        from a real graph edge, so this should never drop any in practice).
    """
    nodes = [
        node for node, is_expanded in expanded.items() if is_expanded and node in graph
    ]
    edges = [
        (parent[node], node)
        for node in nodes
        if parent[node] is not None and graph.has_edge(parent[node], node)
    ]
    return nodes, edges


def draw_algorithm_layer(
    ax: plt.Axes,
    graph: nx.DiGraph,
    pos: Dict[Node, Tuple[float, float]],
    nodes: List[Node],
    edges: List[Tuple[Node, Node]],
    color: str,
) -> None:
    """Paint one algorithm's extracted nodes and shortest-path-tree edges in color.

    args:
        ax: Axes to draw onto.
        graph: The positioned subway graph.
        pos: node -> (lon, lat).
        nodes: This algorithm's extracted nodes, from extracted_nodes_and_edges.
        edges: This algorithm's (parent, node) edges, from extracted_nodes_and_edges.
        color: This algorithm's color, from COLOR_BY_HEURISTIC.
    """
    platform_nodes = [n for n in nodes if not str(n).startswith("E.")]
    entry_nodes = [n for n in nodes if str(n).startswith("E.")]

    if edges:
        widths = [
            math.log10(graph[u][v]["weight_seconds"] + 1)
            * EDGE_WIDTH_SCALE_BY_TYPE[graph[u][v]["type"]]
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

    if platform_nodes:
        nx.draw_networkx_nodes(
            graph,
            pos,
            nodelist=platform_nodes,
            node_shape="o",
            node_size=EXTRACTED_PLATFORM_NODE_SIZE,
            node_color=color,
            ax=ax,
        )
    if entry_nodes:
        nx.draw_networkx_nodes(
            graph,
            pos,
            nodelist=entry_nodes,
            node_shape="s",
            node_size=EXTRACTED_ENTRY_NODE_SIZE,
            node_color=color,
            ax=ax,
        )


def draw_endpoints(
    ax: plt.Axes, graph: nx.DiGraph, pos: Dict[Node, Tuple[float, float]]
) -> None:
    """Paint SOURCE and TARGET last, in their own reserved colors/shapes, above every
    algorithm layer -- a triangle for SOURCE, a star for TARGET, both white-edged so
    they read clearly even sitting on top of a same-colored algorithm node.

    args:
        ax: Axes to draw onto.
        graph: The positioned subway graph, already restricted to nodes with a "pos".
        pos: node -> (lon, lat).
    """
    nx.draw_networkx_nodes(
        graph,
        pos,
        nodelist=[SOURCE],
        node_shape="^",
        node_size=ENDPOINT_NODE_SIZE,
        node_color=SOURCE_COLOR,
        edgecolors="white",
        linewidths=1.2,
        ax=ax,
    )
    nx.draw_networkx_nodes(
        graph,
        pos,
        nodelist=[TARGET],
        node_shape="*",
        node_size=ENDPOINT_NODE_SIZE,
        node_color=TARGET_COLOR,
        edgecolors="white",
        linewidths=1.2,
        ax=ax,
    )


def format_path_lines(path: List[Node], node_fmt: NodeFmt) -> List[str]:
    """Return one "stop_id (label)" line per node in path, for the sidebar text.

    Same stop id + name format as print_path_summary's node_fmt mode
    (routing_algorithms/algorithms_utils.py), but one plain line per node instead of
    "->"-joined, since the sidebar's top-to-bottom order already implies the sequence.

    args:
        path: The rebuilt shortest path from SOURCE to TARGET.
        node_fmt: Callable to label a node (stop name and line), see stop_label.

    returns:
        One line per node in path, in order.
    """
    return [f"{node}{format_node_label(node, node_fmt)}" for node in path]


def legend_label_with_stats(label: str, iterations: int, proportion: float) -> str:
    """Return an algorithm's legend text, with its iterations/proportion folded in.

    args:
        label: A key of LEGEND_LABEL_BY_HEURISTIC (e.g. "a_star_h_bcn").
        iterations: Number of nodes this algorithm extracted before stopping.
        proportion: path_vertices / iterations for this run.

    returns:
        e.g. "A* (h_bcn) (18 it, prop=0.61)".
    """
    return (
        f"{LEGEND_LABEL_BY_HEURISTIC[label]} ({iterations} it, prop={proportion:.2f})"
    )


def main() -> None:
    """Run cut-Dijkstra and the three A* heuristics for SOURCE -> TARGET and draw the PNG."""
    graph: Graph
    coords: Dict[Node, Coord]
    v_max: float
    pathway_ids: Set[str]
    depth_from: DepthTable
    depth_to: DepthTable
    heuristics: Dict[str, Heuristic]
    runs: Dict[str, Run]
    stop_names: Dict[str, str]
    stop_to_lines: Dict[str, List[str]]
    platform_to_entries: Dict[str, Set[str]]
    entrance_to_platform: Dict[str, Set[str]]
    node_fmt: NodeFmt
    dijkstra_parent: Dict[Node, Optional[Node]]
    dijkstra_expanded: Dict[Node, bool]
    dijkstra_iterations: int
    path: List[Node]
    path_vertices: int
    nx_graph: nx.DiGraph
    pos: Dict[Node, Tuple[float, float]]
    fig: plt.Figure
    ax: plt.Axes
    legend_handles: List[plt.Line2D]
    output_dir: Path
    output_path: Path
    _: object

    check_missing_files([WEIGHTS_FILE, STOPS_FILE, PATHWAYS_FILE])
    print_file_disclaimer([WEIGHTS_FILE, STOPS_FILE, PATHWAYS_FILE])

    stop_names = load_stop_names(STOPS_FILE)
    stop_to_lines = build_stop_to_lines(subway_route_names_stop_ids_artificial)
    pathway_ids = load_pathway_ids(PATHWAYS_FILE)
    platform_to_entries, _ = build_graph_and_coverage(pathway_ids)
    entrance_to_platform = invert_entries(platform_to_entries)
    node_fmt = partial(
        stop_label,
        stop_names=stop_names,
        stop_to_lines=stop_to_lines,
        entrance_to_platform=entrance_to_platform,
    )

    graph = build_graph_from_weights(WEIGHTS_FILE)
    print_graph_size(graph)

    coords = load_node_coords(STOPS_FILE)
    v_max, _ = compute_v_max(graph, coords)
    depth_from, depth_to = build_depth_tables(graph)
    heuristics = {
        "a_star_h_geo": build_h_geo(coords, v_max),
        "a_star_h_bcn": build_h_bcn(pathway_ids, coords, v_max, depth_from, depth_to),
        "a_star_h_cheat": build_h_cheat(graph),
    }

    print(f"Running Cut-Dijkstra {SOURCE} -> {TARGET}...")
    _, dijkstra_parent, dijkstra_iterations, dijkstra_expanded = cut_dijkstra(
        graph, SOURCE, TARGET, verbose=False
    )
    runs = {"Dijkstra": (dijkstra_parent, dijkstra_expanded, dijkstra_iterations)}
    for label, h in heuristics.items():
        print(f"Running {LEGEND_LABEL_BY_HEURISTIC[label]} {SOURCE} -> {TARGET}...")
        _, parent, iterations, expanded = a_star(
            graph, SOURCE, TARGET, h, verbose=False
        )
        runs[label] = (parent, expanded, iterations)

    path = apply_liceu_entrance_fix(
        rebuild_path(dijkstra_parent, SOURCE, TARGET), node_fmt
    )
    if not path:
        raise ValueError(f"No path found from {SOURCE} to {TARGET}; nothing to draw.")
    path_vertices = len(path)

    nx_graph = load_graph()
    pos = {n: d["pos"] for n, d in nx_graph.nodes(data=True) if "pos" in d}
    nx_graph = nx_graph.subgraph(pos.keys())

    fig, ax = plt.subplots(figsize=(18, 14))
    draw_base_layer(ax, nx_graph, pos)

    legend_handles = [
        plt.Line2D(
            [0],
            [0],
            marker="o",
            color="none",
            markerfacecolor=BASE_COLOR,
            markersize=10,
            label="Unvisited",
        )
    ]
    # COLOR_BY_HEURISTIC's own order: Cut-Dijkstra, then h_geo, h_bcn, h_cheat, so later
    # layers (painted last) sit on top wherever two algorithms extract the same node/edge.
    for label in COLOR_BY_HEURISTIC:
        parent, expanded, iterations = runs[label]
        color = COLOR_BY_HEURISTIC[label]
        nodes, edges = extracted_nodes_and_edges(expanded, parent, nx_graph)
        draw_algorithm_layer(ax, nx_graph, pos, nodes, edges, color)

        proportion = path_vertices / iterations
        print(
            f"{LEGEND_LABEL_BY_HEURISTIC[label]}: iterations={iterations},"
            f" proportion={proportion:.5f}"
        )
        legend_handles.append(
            plt.Line2D(
                [0],
                [0],
                marker="o",
                color="none",
                markerfacecolor=color,
                markersize=10,
                label=legend_label_with_stats(label, iterations, proportion),
            )
        )
    legend_handles.append(
        plt.Line2D(
            [0],
            [0],
            marker="s",
            color="none",
            markerfacecolor=BASE_COLOR,
            markeredgecolor="#333333",
            markersize=8,
            label="Entry/Exit",
        )
    )

    draw_endpoints(ax, nx_graph, pos)
    legend_handles.append(
        plt.Line2D(
            [0],
            [0],
            marker="^",
            color="none",
            markerfacecolor=SOURCE_COLOR,
            markeredgecolor="white",
            markersize=11,
            label=f"Source ({SOURCE})",
        )
    )
    legend_handles.append(
        plt.Line2D(
            [0],
            [0],
            marker="*",
            color="none",
            markerfacecolor=TARGET_COLOR,
            markeredgecolor="white",
            markersize=14,
            label=f"Target ({TARGET})",
        )
    )
    ax.legend(
        handles=legend_handles,
        loc="lower right",
        bbox_to_anchor=(0.86, 0.08),
        fontsize=14,
    )

    # Sidebar sits inside the axes (not a separate figure margin), in the plot's own
    # top-left empty corner -- same "inside the square" placement as the legend.
    ax.text(
        0.01,
        0.98,
        f"Shortest path ({path_vertices} vertices):\n"
        + "\n".join(format_path_lines(path, node_fmt)),
        transform=ax.transAxes,
        fontsize=11,
        va="top",
        ha="left",
        family="monospace",
    )

    fig.suptitle(
        f"{REGION_CASE} case: extracted nodes from {SOURCE} to {TARGET}",
        y=0.995,
        fontsize=14,
        color="#0b0b0b",
    )
    ax.set_axis_off()

    ax.text(
        0.01,
        0.01,
        "Cut-Dijkstra, then A* (h_geo), A* (h_bcn), A* (h_cheat), painted in that order",
        transform=ax.transAxes,
        ha="left",
        va="bottom",
        fontsize=14,
        color="#666666",
    )

    fig.tight_layout(rect=(0.01, 0.01, 1, 0.96))

    output_dir = Path(EXTRACTED_NODES_DIR)
    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{REGION_CASE}_{SOURCE}_to_{TARGET}.png"
    fig.savefig(output_path, dpi=200)
    plt.close(fig)
    print(f"{output_path.name} generated into {output_path.relative_to(_PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
