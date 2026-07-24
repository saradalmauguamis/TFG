"""Draw, over the whole subway graph, which nodes/edges cut-Dijkstra and each A*
heuristic (h_geo, h_bcn, h_cheat) actually extracted while searching SOURCE -> TARGET.

The whole graph (graph_inspection/graph_draw/graph.py's load_graph, same source as
shortest_paths_algorithms/analysis/regions_graph.py) is painted light grey first, then each
algorithm's extracted nodes and shortest-path-tree edges (parent links) are layered on
top of it, in a fixed order: Cut-Dijkstra, then A*_geo, A*_bcn, A*_cheat, following
COLOR_BY_HEURISTIC's own order (shortest_paths_algorithms/analysis/algorithms_comparison.py),
reused here directly so a heuristic's color always means the same thing across every
chart in this package. Later layers paint over earlier ones wherever two algorithms
extract the same node/edge.

`expanded` (which nodes were extracted before the search stopped) is not part of either
algorithm's pseudocode (see a_star_utils.py's a_star() and dijkstra_utils.py's
_run_dijkstra() for where it's tracked purely for this kind of traceability), but
`parent` already is, for both algorithms.

Output_name: {region_case}_{GRAPH_MODE_LABEL}_{SOURCE}_to_{TARGET}.png ({region_case}_
{GRAPH_MODE_LABEL}_bcn_{SOURCE}_to_{TARGET}.png when SHOW_H_BCN is True) saved into
'shortest_paths_algorithms/analysis/resources/extracted_nodes' (EXTRACTED_NODES_DIR,
shortest_paths_algorithms/paths.py). region_case (one of barcelona_division.classify's
CC/CB/BC/SB/DB cases) is computed from the actual (algo_source, algo_target) platform
pair cut-Dijkstra resolves SOURCE/TARGET to (see best_over_candidate_pairs), and also
drives resolve_bridge_highlights: whichever endpoint(s) region_case names as a branch
(TARGET for CB/SB/DB, SOURCE for BC/SB/DB) get their branch's bridge platform (find_branch/
compute_bridge, same lookup regions_graph.py uses) marked with a diamond in BRIDGE_COLOR.

Since the deliverable is the PNG alone (no companion .txt report), everything that would
otherwise be printed is drawn directly on the figure: the shortest path (stop id + name, same
format as print_path_summary in shortest_paths_algorithms/algorithms_utils.py, but one node
per line instead of joined by "->") as a sidebar in the plot's top-left corner, and each
algorithm's iterations/proportion (path_vertices / iterations, same metric as
shortest_paths_algorithms/reports/, except iterations is bumped by entrance_endpoint_shift()
whenever GRAPH_MODE is WITHOUT_ENTRANCES_GRAPH and SOURCE/TARGET are entrances, so the
denominator accounts for the same restored endpoints finalize_path already added to
path_vertices; see entrance_endpoint_shift's own docstring) folded into each algorithm's own
legend entry.
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

from subway_reference.subway_lines import (  # noqa: E402
    subway_route_names_stop_ids_artificial,
)

from data_validation.gtfs_utils import (  # noqa: E402
    STOPS_FILE,
    WEIGHTS_FILE,
    build_stop_to_lines,
    check_missing_files,
    load_stop_names,
    print_file_disclaimer,
    seconds_to_hms,
)
from graph_inspection.graph_draw.graph import load_graph  # noqa: E402
from shortest_paths_algorithms.algorithms_utils import (  # noqa: E402
    FULL_GRAPH,
    GRAPH_MODE_LABEL,
    INF,
    WITHOUT_ENTRANCES_GRAPH,
    EntranceToPlatforms,
    Graph,
    Node,
    NodeFmt,
    best_over_candidate_pairs,
    build_entrance_platform_lookups,
    build_graph_from_weights,
    finalize_path,
    format_node_label,
    print_graph_size,
    report_missing_platform_candidates,
    resolve_search_endpoints,
    stop_label,
    with_adjusted_target_weight,
)
from shortest_paths_algorithms.analysis.algorithms_comparison import (  # noqa: E402
    COLOR_BY_HEURISTIC,
    LEGEND_LABEL_BY_HEURISTIC,
)
from shortest_paths_algorithms.analysis.regions_graph import (  # noqa: E402
    BRIDGE_COLOR,
    EDGE_WIDTH_SCALE_BY_TYPE,
)
from shortest_paths_algorithms.barcelona_division import (  # noqa: E402
    classify,
    compute_bridge,
    find_branch,
)
from shortest_paths_algorithms.config import GRAPH_MODE, SOURCE, TARGET  # noqa: E402
from shortest_paths_algorithms.a_star.a_star_utils import (  # noqa: E402
    Heuristic,
    a_star,
)
from shortest_paths_algorithms.a_star.heuristics.h_geo import (  # noqa: E402
    Coord,
    build_h_geo,
    compute_v_max,
    load_node_coords,
)
from shortest_paths_algorithms.a_star.heuristics.h_cheat import (  # noqa: E402
    build_h_cheat,
)
from shortest_paths_algorithms.a_star.heuristics.h_bcn import (  # noqa: E402
    DepthTable,
    build_depth_tables,
    build_h_bcn,
    plat_from,
    plat_to,
)
from shortest_paths_algorithms.dijkstra.dijkstra_utils import cut_dijkstra  # noqa: E402
from shortest_paths_algorithms.paths import EXTRACTED_NODES_DIR  # noqa: E402

# Toggle to include/exclude h_bcn from the run and the figure/legend below.
SHOW_H_BCN = True

# Toggle to include/exclude the region_case branch-bridge diamond and its legend entry.
SHOW_BRIDGE = True

# Human-readable GRAPH_MODE label for the figure's title, distinct from
# GRAPH_MODE_LABEL's terse "full"/"no_pw" used in the output filename.
GRAPH_MODE_TITLE = {
    FULL_GRAPH: "with the full graph",
    WITHOUT_ENTRANCES_GRAPH: "without entrances in the graph",
}

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
ENDPOINT_NODE_SIZE = 400

# Whichever of SOURCE/TARGET region_case names as a branch endpoint (see
# resolve_bridge_highlights) gets its branch's bridge platform marked with a diamond in
# BRIDGE_COLOR, the same color regions_graph.py reserves for "bridge", so it reads as
# the same concept across every chart in this package.
BRIDGE_NODE_SIZE = 200


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
    algorithm layer: a triangle for SOURCE, a star for TARGET, both white-edged so
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


def resolve_bridge_highlights(
    region_case: str,
    entrance_plat_to: Dict[str, Set[str]],
    entrance_plat_from: Dict[str, Set[str]],
) -> List[Node]:
    """Return the bridge platform(s) region_case calls out for SOURCE and/or TARGET.

    Mirrors barcelona_division.classify's naming: region_case names TARGET's branch
    whenever its second letter is B (CB/SB/DB) and SOURCE's whenever its first letter is B
    (BC/SB/DB); see shortest_paths_algorithms/barcelona_division.py's classify docstring for the
    5-case table. Whichever endpoint(s) region_case names, resolved to platform(s) through
    h_bcn's own plat_to/plat_from (so an entry/exit maps to exactly the platforms h_bcn
    itself would route it through, instead of a separate ad-hoc lookup), find_branch/
    compute_bridge (also barcelona_division.py, the same lookup regions_graph.py uses to
    highlight bridges) give the single Center platform each branch platform's branch
    reconnects through.

    args:
        region_case: This SOURCE/TARGET pair's classify() case, from main().
        entrance_plat_to: entry stop_id -> platforms with a directed pathway arrow into it,
            see h_bcn.plat_to; only consulted when TARGET is an entry/exit.
        entrance_plat_from: entry stop_id -> platforms it has a directed pathway arrow
            into, see h_bcn.plat_from; only consulted when SOURCE is an entry/exit.

    returns:
        Distinct bridge stop_ids to highlight: 0 (CC, or an entry with no resolvable
        platform), 1 (CB/BC, or SB since source and target share one branch's one bridge),
        or up to 2 (DB, different branches).
    """
    bridges: Set[Node] = set()
    if region_case in ("CB", "SB", "DB"):
        for platform in plat_to(TARGET, entrance_plat_to):
            if find_branch(platform) is not None:
                bridges.add(compute_bridge(platform))
    if region_case in ("BC", "SB", "DB"):
        for platform in plat_from(SOURCE, entrance_plat_from):
            if find_branch(platform) is not None:
                bridges.add(compute_bridge(platform))
    return list(bridges)


def format_path_lines(path: List[Node], node_fmt: NodeFmt) -> List[str]:
    """Return one "stop_id (label)" line per node in path, for the sidebar text.

    Same stop id + name format as print_path_summary's node_fmt mode
    (shortest_paths_algorithms/algorithms_utils.py), but one plain line per node instead of
    "->"-joined, since the sidebar's top-to-bottom order already implies the sequence.

    args:
        path: The rebuilt shortest path from SOURCE to TARGET.
        node_fmt: Callable to label a node (stop name and line), see stop_label.

    returns:
        One line per node in path, in order.
    """
    return [f"{node}{format_node_label(node, node_fmt)}" for node in path]


def resolve_classify_endpoints(path: List[Node]) -> Tuple[Node, Node]:
    """Return the (source-side, target-side) platform classify() should use.

    classify (barcelona_division.py) only accepts platforms, but SOURCE/TARGET
    may be entrances: on FULL_GRAPH entrances are reachable directly, so
    algo_source/algo_target (best_over_candidate_pairs' output) can themselves
    be entrances there, unlike WITHOUT_ENTRANCES_GRAPH where they're always
    already-reduced platforms (see resolve_search_endpoints). Either way,
    finalize_path's path runs entrance -> platform -> ... -> platform ->
    entrance whenever an endpoint is an entrance, so its second/second-to-last
    vertex is the platform actually used to enter/exit through.

    args:
        path: The finalized SOURCE -> TARGET path, from finalize_path.

    returns:
        (source_platform, target_platform): path[0]/path[-1] as-is when
        already a platform, otherwise path[1]/path[-2].
    """
    source_platform = path[1] if path[0].startswith("E.") else path[0]
    target_platform = path[-2] if path[-1].startswith("E.") else path[-1]
    return source_platform, target_platform


def entrance_endpoint_shift() -> int:
    """Return how many of SOURCE/TARGET are entrances restored onto the path.

    On WITHOUT_ENTRANCES_GRAPH, finalize_path's restore_entrance_endpoints (see
    algorithms_utils.py) prepends/appends whichever of SOURCE/TARGET is an entrance,
    since entrances aren't part of the search graph there and so never get extracted
    by any algorithm. Counting them in path_vertices without a matching bump to
    iterations would inflate proportion for entrance endpoints relative to platform
    ones. On FULL_GRAPH entrances are in the search graph and do get genuinely
    extracted, so no shift applies there.

    returns:
        0, 1 or 2: how many of SOURCE/TARGET are entrances, only on
        WITHOUT_ENTRANCES_GRAPH (always 0 on FULL_GRAPH).
    """
    if GRAPH_MODE != WITHOUT_ENTRANCES_GRAPH:
        return 0
    return int(SOURCE.startswith("E.")) + int(TARGET.startswith("E."))


def legend_label_with_stats(label: str, iterations: int, proportion: float) -> str:
    """Return an algorithm's legend text, with its iterations/proportion folded in.

    args:
        label: A key of LEGEND_LABEL_BY_HEURISTIC (e.g. "a_star_h_bcn").
        iterations: Number of nodes this algorithm extracted before stopping,
            plus entrance_endpoint_shift (so it matches proportion's denominator).
        proportion: path_vertices / iterations for this run.

    returns:
        e.g. "A*_bcn (18 it, prop=0.61)".
    """
    return (
        f"{LEGEND_LABEL_BY_HEURISTIC[label]} ({iterations} it, prop={proportion:.2f})"
    )


def draw_and_save_figure(
    runs: Dict[str, Run],
    path: List[Node],
    path_vertices: int,
    entrance_plat_to: Dict[str, Set[str]],
    entrance_plat_from: Dict[str, Set[str]],
    node_fmt: NodeFmt,
    region_case: str,
    optimum_weight_text: str,
) -> Path:
    """Draw every algorithm's extracted layer over the whole subway graph and save the PNG.

    Layers the whole subway network (base layer), each algorithm's extracted
    nodes/edges (in COLOR_BY_HEURISTIC's fixed order), SOURCE/TARGET, and any
    region_case bridge highlight, then the legend and the shortest-path
    sidebar; see the module docstring for the full picture.

    args:
        runs: label -> (parent, expanded, iterations), one entry per algorithm
            (Cut-Dijkstra + the three A* heuristics), see Run.
        path: The rebuilt SOURCE -> TARGET path (via finalize_path), for the
            sidebar.
        path_vertices: len(path), used for each algorithm's proportion.
        entrance_plat_to: entry stop_id -> platforms with a directed pathway
            edge into it, for resolve_bridge_highlights.
        entrance_plat_from: entry stop_id -> platforms it has a directed
            pathway edge into, for resolve_bridge_highlights.
        node_fmt: Callable to label a node (stop name and line), for the
            sidebar.
        region_case: This SOURCE/TARGET pair's classify() case, from main().
        optimum_weight_text: "Optimum weight: ..." line, same format as
            print_path_summary (algorithms_utils.py), for the sidebar.

    returns:
        The path the PNG was saved to.
    """
    nx_graph: nx.DiGraph
    pos: Dict[Node, Tuple[float, float]]
    fig: plt.Figure
    ax: plt.Axes
    legend_handles: List[plt.Line2D]
    parent: Dict[Node, Optional[Node]]
    expanded: Dict[Node, bool]
    iterations: int
    color: str
    nodes: List[Node]
    edges: List[Tuple[Node, Node]]
    proportion: float
    bridge_nodes: List[Node]
    output_dir: Path
    bcn_tag: str
    output_path: Path
    shift: int

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
    shift = entrance_endpoint_shift()
    for label in COLOR_BY_HEURISTIC:
        if label == "a_star_h_bcn" and not SHOW_H_BCN:
            continue
        parent, expanded, iterations = runs[label]
        color = COLOR_BY_HEURISTIC[label]
        nodes, edges = extracted_nodes_and_edges(expanded, parent, nx_graph)
        draw_algorithm_layer(ax, nx_graph, pos, nodes, edges, color)

        iterations += shift
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

    if SHOW_BRIDGE:
        bridge_nodes = resolve_bridge_highlights(
            region_case, entrance_plat_to, entrance_plat_from
        )
        if bridge_nodes:
            nx.draw_networkx_nodes(
                nx_graph,
                pos,
                nodelist=bridge_nodes,
                node_shape="D",
                node_size=BRIDGE_NODE_SIZE,
                node_color=BRIDGE_COLOR,
                edgecolors="white",
                linewidths=1.2,
                ax=ax,
            )
            legend_handles.append(
                plt.Line2D(
                    [0],
                    [0],
                    marker="D",
                    color="none",
                    markerfacecolor=BRIDGE_COLOR,
                    markeredgecolor="white",
                    markersize=10,
                    label="Branch bridge",
                )
            )

    ax.legend(
        handles=legend_handles,
        loc="lower right",
        bbox_to_anchor=(0.86, 0.08),
        fontsize=14,
    )

    # Sidebar sits inside the axes (not a separate figure margin), in the plot's own
    # top-left empty corner, the same "inside the square" placement as the legend.
    ax.text(
        0.01,
        0.98,
        f"Shortest path ({path_vertices} vertices):\n"
        + "\n".join(format_path_lines(path, node_fmt))
        + f"\n{optimum_weight_text}",
        transform=ax.transAxes,
        fontsize=11,
        va="top",
        ha="left",
        family="monospace",
    )

    fig.suptitle(
        f"{region_case} case ({GRAPH_MODE_TITLE[GRAPH_MODE]}):"
        f" extracted nodes from {node_fmt(SOURCE)} to {node_fmt(TARGET)}",
        y=0.995,
        fontsize=14,
        color="#0b0b0b",
    )
    ax.set_axis_off()

    ax.text(
        0.01,
        0.01,
        "Cut-Dijkstra, then A*_geo, "
        + ("A*_bcn, " if SHOW_H_BCN else "")
        + "A*_cheat, painted in that order",
        transform=ax.transAxes,
        ha="left",
        va="bottom",
        fontsize=14,
        color="#666666",
    )

    fig.tight_layout(rect=(0.01, 0.01, 1, 0.96))

    output_dir = Path(EXTRACTED_NODES_DIR)
    output_dir.mkdir(parents=True, exist_ok=True)
    bcn_tag = "bcn_" if SHOW_H_BCN else ""
    output_path = (
        output_dir
        / f"{region_case}_{GRAPH_MODE_LABEL[GRAPH_MODE]}_{bcn_tag}{SOURCE}_to_{TARGET}.png"
    )
    fig.savefig(output_path, dpi=200)
    plt.close(fig)
    return output_path


def main() -> None:
    """Run cut-Dijkstra and the three A* heuristics for SOURCE -> TARGET and draw the PNG."""
    graph: Graph
    coords: Dict[Node, Coord]
    v_max: float
    depth_from: DepthTable
    depth_to: DepthTable
    heuristics: Dict[str, Heuristic]
    runs: Dict[str, Run]
    stop_names: Dict[str, str]
    stop_to_lines: Dict[str, List[str]]
    entrance_to_platform: Dict[str, Set[str]]
    entrance_plat_to: EntranceToPlatforms
    entrance_plat_from: EntranceToPlatforms
    node_fmt: NodeFmt
    source_platforms: Set[Node]
    target_platforms: Set[Node]
    entry_total: int
    algo_source: Node
    algo_target: Node
    region_case: str
    dijkstra_dist: Dict[Node, int]
    dijkstra_parent: Dict[Node, Optional[Node]]
    dijkstra_expanded: Dict[Node, bool]
    dijkstra_iterations: int
    best_weight: int
    total: int
    optimum_weight_text: str
    path: List[Node]
    path_vertices: int
    output_path: Path
    _: object

    check_missing_files([WEIGHTS_FILE, STOPS_FILE])
    print_file_disclaimer([WEIGHTS_FILE, STOPS_FILE])

    stop_names = load_stop_names(STOPS_FILE)
    stop_to_lines = build_stop_to_lines(subway_route_names_stop_ids_artificial)
    entrance_to_platform, entrance_plat_to, entrance_plat_from = (
        build_entrance_platform_lookups(WEIGHTS_FILE)
    )
    node_fmt = partial(
        stop_label,
        stop_names=stop_names,
        stop_to_lines=stop_to_lines,
        entrance_to_platform=entrance_to_platform,
    )

    graph = build_graph_from_weights(WEIGHTS_FILE, GRAPH_MODE)
    print_graph_size(graph)

    coords = load_node_coords(STOPS_FILE)
    v_max, _ = compute_v_max(graph, coords)
    depth_from, depth_to = build_depth_tables(graph)
    heuristics = {
        "a_star_h_geo": build_h_geo(coords, v_max),
        "a_star_h_cheat": build_h_cheat(graph),
    }
    if SHOW_H_BCN:
        heuristics["a_star_h_bcn"] = build_h_bcn(
            WEIGHTS_FILE, coords, v_max, depth_from, depth_to
        )

    source_platforms, target_platforms, entry_total = resolve_search_endpoints(
        GRAPH_MODE, SOURCE, TARGET, entrance_plat_from, entrance_plat_to
    )
    if report_missing_platform_candidates(
        source_platforms, target_platforms, SOURCE, TARGET
    ):
        raise ValueError(
            f"No path possible from {SOURCE} to {TARGET}; nothing to draw."
        )

    # Cut-Dijkstra resolves which candidate (source, target) platform pair to
    # actually use (see algorithms_utils.resolve_platform_candidates): every
    # algorithm below then reruns against that same fixed pair, so they stay
    # directly comparable against the same route.
    print(f"Running Cut-Dijkstra {SOURCE} -> {TARGET}...")
    (
        algo_source,
        algo_target,
        dijkstra_dist,
        dijkstra_parent,
        dijkstra_iterations,
        dijkstra_expanded,
    ) = best_over_candidate_pairs(
        graph,
        source_platforms,
        target_platforms,
        partial(cut_dijkstra, verbose=False),
    )
    best_weight = dijkstra_dist[algo_target]
    total = with_adjusted_target_weight(
        dijkstra_dist, TARGET, best_weight, entry_total
    )[TARGET]
    optimum_weight_text = (
        f"Optimum weight: {'inf' if total == INF else seconds_to_hms(total)}"
        " (format: HH:MM:SS)"
    )

    runs = {"Dijkstra": (dijkstra_parent, dijkstra_expanded, dijkstra_iterations)}
    for label, h in heuristics.items():
        print(f"Running {LEGEND_LABEL_BY_HEURISTIC[label]} {SOURCE} -> {TARGET}...")
        _, parent, iterations, expanded = a_star(
            graph, algo_source, algo_target, h, verbose=False
        )
        runs[label] = (parent, expanded, iterations)

    path = finalize_path(
        GRAPH_MODE,
        runs["a_star_h_cheat"][0],
        algo_source,
        algo_target,
        SOURCE,
        TARGET,
        node_fmt,
    )
    if not path:
        raise ValueError(f"No path found from {SOURCE} to {TARGET}; nothing to draw.")
    path_vertices = len(path)
    region_case = classify(*resolve_classify_endpoints(path))

    output_path = draw_and_save_figure(
        runs,
        path,
        path_vertices,
        entrance_plat_to,
        entrance_plat_from,
        node_fmt,
        region_case,
        optimum_weight_text,
    )
    print(f"{output_path.name} generated into {output_path.relative_to(_PROJECT_ROOT)}")


if __name__ == "__main__":
    main()
