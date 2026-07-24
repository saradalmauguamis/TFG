# Shortest Paths Algorithms Workflow

Unlike [`data_validation/WORKFLOW.md`](../data_validation/WORKFLOW.md), this isn't a workflow of
data stages with a required run order; it's the trail of ideas and intuitions behind each step,
from a plain Dijkstra up to an A* variant that, per iteration, finds 0.39 vertices of the shortest
path (up from 0.06 at the start).

Each new heuristic follows the same three-beat pattern: build it, report its
vertices-in-path/iterations ratio, then sanity-check it against the other algorithms' optimum path
weight to make sure it's still finding correct shortest paths.

---

## 1. Baseline: Dijkstra

1. **[`dijkstra/dijkstra_utils.py`](dijkstra/dijkstra_utils.py)** — build Dijkstra's algorithm.
2. **[`dijkstra/dijkstra_example.py`](dijkstra/dijkstra_example.py)** — run it on small hand-built
   examples to check the implementation makes sense before trusting it on real data.
3. **[`dijkstra/dijkstra.py`](dijkstra/dijkstra.py)** — apply it to the real graph, built from the
   edge weights produced by
   **[`data_validation/processing/6_weights.py`](../data_validation/processing/6_weights.py)**.

Dijkstra alone gives no sense of whether its iteration count is *good*. It needs a reference to be
judged against, which motivates A*.

## 2. A reference ceiling: A*_cheat

4. **[`a_star/a_star_utils.py`](a_star/a_star_utils.py)** — build A*.
5. **[`a_star/a_star_example.py`](a_star/a_star_example.py)** — same sanity pass on toy examples.
6. **[`a_star/heuristics/h_cheat.py`](a_star/heuristics/h_cheat.py)** — a "cheating" heuristic that
   knows the true remaining distance in advance. It isn't usable in practice, but gives an upper
   bound on how good a heuristic could possibly make A* perform.
7. **[`a_star/a_star.py`](a_star/a_star.py)** — apply A* to the real graph.
8. **[`reports/dijkstra_report.py`](reports/dijkstra_report.py)** and
   **[`reports/a_star_report.py`](reports/a_star_report.py)** — report vertices found in the
   shortest path per iteration, for each algorithm.
9. **[`reports/optimum_weight_check.py`](reports/optimum_weight_check.py)** — sanity check: verify
   every algorithm agrees on the optimum path weight for the same queries.

Dijkstra means 0.06, A*_cheat means 0.99. The gap between them shows there's real room for a
heuristic to reduce iterations: 0.99 is the ceiling, not a target.

## 3. A first real heuristic: A*_geo

10. **[`a_star/heuristics/h_geo.py`](a_star/heuristics/h_geo.py)** — a straight-line geographic
    distance heuristic, built and reported the same way (report, then the optimum-weight sanity
    check).

Mean 0.12, better than Dijkstra, but still far from the 0.99 ceiling shown by A*_cheat.

## 4. Exploiting the graph's own structure

Rather than a purely geometric heuristic, the next idea was to lean on characteristics specific to
this graph.

11. **[`barcelona_division.py`](barcelona_division.py)** — classify every source/target pair into
    one of five cases based on where they sit relative to Barcelona's center and branch lines:
    `CC` (center → center), `CB` (center → branch), `BC` (branch → center), `SB` (same branch),
    `DB` (different branches). **[`analysis/regions_graph.py`](analysis/regions_graph.py)** plots
    these regions.
12. **[`analysis/algorithms_comparison.py`](analysis/algorithms_comparison.py)** — break down each
    algorithm's metrics by these five cases, rather than only looking at a single global mean.
13. **[`a_star/heuristics/h_bcn.py`](a_star/heuristics/h_bcn.py)** — a heuristic informed by that
    division (A*_bcn), reported and sanity-checked the same way as the previous two.
14. **[`analysis/algorithms_comparison.py`](analysis/algorithms_comparison.py)** again — global mean
    improves to 0.19. **[`analysis/extracted_nodes_graph.py`](analysis/extracted_nodes_graph.py)**
    visualizes which nodes each algorithm actually expands, to see *why*.

## 5. Cutting the graph: removing entrance-only edges

15. **[`../graph_inspection/graph_report.py`](../graph_inspection/graph_report.py)** shows nearly
    three-quarters of the graph's vertices are station entrances. Entrances only ever matter at the
    very start and end of a path, yet the algorithms were spending most of their iterations
    checking them. The entry cost already added in `h_bcn` isn't enough to fix this, and it can't be
    raised further without breaking the heuristic's admissibility. The fix instead has to be at the
    graph level: filter out the `PW` (pathway) edges from the weights file so entrances stop being
    routinely expanded. This produces two graph variants, `full_graph` and
    `without_entrances_graph`, selectable via `graph_mode` in
    **[`config.yaml`](config.yaml)**.
16. For each algorithm, repeat the full cycle on the reduced graph: report, then the
    optimum-weight sanity check.
17. **[`analysis/algorithms_comparison.py`](analysis/algorithms_comparison.py)** — final comparison:
    every algorithm improves on the reduced graph.

## Outcome

Starting point, Dijkstra on the full graph: mean 0.06 (100 iterations find only 6 vertices of the
shortest path). End point, A*_bcn on the `without_entrances_graph`: mean 0.39, driven first by a
region-aware heuristic tailored to this network's center/branch structure, then by removing the
entrance vertices that were diluting every algorithm's iterations regardless of heuristic.
