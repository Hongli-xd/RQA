#!/usr/bin/env python3
"""F3: recover the ORDER of queried ranges in the value domain from estimated
overlap magnitudes alone - no auxiliary data, no prior, no plaintext.

Why this is the interesting target
----------------------------------
Everything the attack recovered so far is workload metadata: when a range query
ran, how big it was, and which queries touched the same data.  The value domain
itself stayed hidden, and results/prior_matching/summary.md shows that matching
cardinalities against a census-style histogram cannot fix that: at the
cardinality error this attack achieves, the prior is worth 0.13 bit.

But range queries are intervals, and the overlap of two intervals is a monotone
function of how far apart they are.  So a set of pairwise overlap magnitudes is
a proximity matrix over the value domain, and recovering a 1-D order from a
proximity matrix is seriation - solvable without knowing any values at all.  If
this works, the server learns the relative arrangement of the queried ranges,
which is genuine (partial, order-only) value-domain structure rather than
metadata.

Method: spectral seriation.  Build the weighted graph over detected episodes,
split it into connected components (the linkage window fragments it by
construction), and order each component by the Fiedler vector of its weighted
Laplacian - the classical 1-D embedding, computed here with power iteration and
deflation against the constant vector, stdlib only.

Scoring: |Spearman| between the recovered order and the true range starts, per
component, sign-free because seriation is only defined up to reflection.

Nulls: (a) the same components with their edge weights shuffled, (b) the same
components with weights replaced by the pair COUNT alone (topology without
magnitude), so any gain from magnitude estimation is visible.

Inputs are the CSVs from rqa_f2_pair_features.py.  Attack-side columns build the
graph; `*_true_*` columns only score it.

Stdlib only.
"""

from __future__ import annotations

import argparse
import csv
import math
import random
from collections import defaultdict
from pathlib import Path
from statistics import mean, median

ROOT = Path(__file__).resolve().parents[1]


def spearman_abs(xs, ys) -> float:
    def rk(v):
        o = sorted(range(len(v)), key=lambda i: v[i])
        r = [0.0] * len(v)
        i = 0
        while i < len(o):
            j = i
            while j + 1 < len(o) and v[o[j + 1]] == v[o[i]]:
                j += 1
            for q in range(i, j + 1):
                r[o[q]] = (i + j) / 2 + 1
            i = j + 1
        return r
    rx, ry = rk(xs), rk(ys)
    mx, my = mean(rx), mean(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    den = math.sqrt(sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry))
    return abs(num / den) if den else 0.0


def components(nodes: list[int], edges: dict[tuple[int, int], float]) -> list[list[int]]:
    adj: dict[int, set[int]] = defaultdict(set)
    for (a, b) in edges:
        adj[a].add(b)
        adj[b].add(a)
    seen: set[int] = set()
    out = []
    for n in nodes:
        if n in seen:
            continue
        stack, comp = [n], []
        seen.add(n)
        while stack:
            x = stack.pop()
            comp.append(x)
            for y in adj[x]:
                if y not in seen:
                    seen.add(y)
                    stack.append(y)
        out.append(sorted(comp))
    return out


def fiedler_order(comp: list[int], edges: dict[tuple[int, int], float],
                  iters: int = 3000) -> list[int]:
    """Order `comp` by the Fiedler vector of its weighted Laplacian.

    Power-iterate on B = cI - L (c > max degree, so B is PSD and its top
    eigenvector is the constant one), deflating the constant vector every step;
    what survives is the eigenvector of L's second-smallest eigenvalue."""
    idx = {n: i for i, n in enumerate(comp)}
    k = len(comp)
    if k < 3:
        return comp
    w = [[0.0] * k for _ in range(k)]
    for (a, b), val in edges.items():
        if a in idx and b in idx:
            i, j = idx[a], idx[b]
            w[i][j] += val
            w[j][i] += val
    deg = [sum(row) for row in w]
    c = 2.0 * max(deg) + 1.0
    rng = random.Random(12345)
    v = [rng.uniform(-1, 1) for _ in range(k)]
    for _ in range(iters):
        # deflate the constant direction
        m = sum(v) / k
        v = [x - m for x in v]
        norm = math.sqrt(sum(x * x for x in v)) or 1.0
        v = [x / norm for x in v]
        # u = B v = c v - (D - W) v
        u = [c * v[i] - deg[i] * v[i] + sum(w[i][j] * v[j] for j in range(k))
             for i in range(k)]
        v = u
    m = sum(v) / k
    v = [x - m for x in v]
    return [n for _val, n in sorted(zip(v, comp))]


def build(rows, weight_key: str, keep) -> tuple[list[int], dict[tuple[int, int], float]]:
    nodes = sorted({int(r["parent"]) for r in rows} | {int(r["child"]) for r in rows})
    edges: dict[tuple[int, int], float] = {}
    for r in rows:
        if not keep(r):
            continue
        a, b = int(r["parent"]), int(r["child"])
        if a == b:
            continue
        key = (min(a, b), max(a, b))
        val = 1.0 if weight_key == "count" else max(0.0, r.get(weight_key, 0.0))
        edges[key] = edges.get(key, 0.0) + val
    return nodes, {k: v for k, v in edges.items() if v > 0}


def concordance(order: list[int], true_start: dict[int, float]) -> float:
    """Fraction of node PAIRS whose recovered relative order matches truth,
    reflection-free via max(c, 1-c).

    Pair concordance is used instead of per-component Spearman because with the
    small components the linkage window produces (k = 3..6), |Spearman| of a
    RANDOM order already averages ~0.5-0.75: for k=3 it can only take the values
    0.5 and 1.0. Aggregating over pairs and comparing against a same-size
    permutation null is the only way to read these components honestly."""
    k = len(order)
    conc = tot = 0
    for i in range(k):
        for j in range(i + 1, k):
            a, b = order[i], order[j]
            if true_start[a] == true_start[b]:
                continue
            tot += 1
            if true_start[a] < true_start[b]:
                conc += 1
    if tot == 0:
        return 0.5
    c = conc / tot
    return max(c, 1.0 - c)


def time_order_baseline(rows, true_start, min_size: int = 4, null_draws: int = 400,
                        rng=None):
    """Order the episodes by DETECTION TIME and score that.

    This is the arm that has to be reported next to every other one.  Detected
    episode ids are assigned in batch order, so this ordering uses nothing but
    the timeline Stage B already produces - no overlap graph, no magnitudes, no
    seriation.  If a workload issues its range scans in value order, this
    baseline alone scores 1.000, and any seriation result measured on it is
    measuring the schedule rather than the leakage."""
    nodes = sorted({int(r["parent"]) for r in rows} | {int(r["child"]) for r in rows})
    if len(nodes) < min_size:
        return {"components": 0, "nodes_ordered": 0, "max_comp": 0,
                "concordance": None, "null_concordance": None, "above_null": None}
    obs = concordance(nodes, true_start)
    acc = 0.0
    rng = rng or random.Random(0)
    for _ in range(null_draws):
        perm = nodes[:]
        rng.shuffle(perm)
        acc += concordance(perm, true_start)
    null = acc / null_draws
    return {"components": 1, "nodes_ordered": len(nodes), "max_comp": len(nodes),
            "concordance": round(obs, 3), "null_concordance": round(null, 3),
            "above_null": round(obs - null, 3)}


def score_arm(rows, weight_key, keep, true_start, rng, shuffle=False,
              min_size: int = 4, null_draws: int = 400):
    nodes, edges = build(rows, weight_key, keep)
    if shuffle:
        vals = list(edges.values())
        rng.shuffle(vals)
        edges = {k: v for k, v in zip(edges.keys(), vals)}
    comps = [c for c in components(nodes, edges) if len(c) >= min_size]
    obs_num = null_num = den = 0.0
    sizes = []
    for comp in comps:
        k = len(comp)
        pairs = k * (k - 1) / 2.0
        order = fiedler_order(comp, edges)
        obs = concordance(order, true_start)
        # same-size permutation null, Monte Carlo, reflection-free like the observed
        acc = 0.0
        for _ in range(null_draws):
            perm = comp[:]
            rng.shuffle(perm)
            acc += concordance(perm, true_start)
        obs_num += obs * pairs
        null_num += (acc / null_draws) * pairs
        den += pairs
        sizes.append(k)
    if not sizes:
        return {"components": 0, "nodes_ordered": 0, "max_comp": 0,
                "concordance": None, "null_concordance": None, "above_null": None}
    return {
        "components": len(sizes),
        "nodes_ordered": sum(sizes),
        "max_comp": max(sizes),
        "concordance": round(obs_num / den, 3),
        "null_concordance": round(null_num / den, 3),
        "above_null": round((obs_num - null_num) / den, 3),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed-dirs", type=Path, nargs="+", required=True)
    ap.add_argument("--poisson-threshold", type=float, default=None,
                    help="burst-calibrated poisson_z_max_cell floor; if omitted it is "
                         "taken as the q90 of the run's own burst control")
    ap.add_argument("--min-comp", type=int, default=4,
                    help="ignore components smaller than this (chance dominates them)")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--outdir", type=Path, default=ROOT / "results" / "f3_seriation")
    args = ap.parse_args()
    rng = random.Random(args.seed)

    all_rows = []
    for d in args.seed_dirs:
        with (d / "pair_features.csv").open() as fh:
            rows = [{k: float(v) for k, v in r.items()} for r in csv.DictReader(fh)]
        with (d / "burst_pair_features.csv").open() as fh:
            burst = [{k: float(v) for k, v in r.items()} for r in csv.DictReader(fh)]
        bn = [b for b in burst if b["mass"] >= 8 and b["max_cell"] >= 4]
        th = args.poisson_threshold
        if th is None:
            vals = sorted(b["poisson_z_max_cell"] for b in bn)
            th = vals[int(0.9 * (len(vals) - 1))] if vals else 0.0
        true_start = {}
        for r in rows:
            true_start[int(r["parent"])] = r["parent_true_start"]
            true_start[int(r["child"])] = r["child_true_start"]

        # The FULL true overlap graph (every truly overlapping pair, including
        # those the attack never produced a candidate for). Without it the only
        # available "oracle" is true pairs AMONG CANDIDATES, which the linkage
        # window has already filtered - an oracle that inherits the very
        # limitation the experiment is trying to isolate.
        tg_path = d / "true_overlap_graph.csv"
        true_graph = []
        if tg_path.exists():
            with tg_path.open() as fh:
                true_graph = [{k: float(v) for k, v in r.items()} for r in csv.DictReader(fh)]
        for r in true_graph:
            true_start[int(r["det_a"])] = r["a_true_start"]
            true_start[int(r["det_b"])] = r["b_true_start"]

        base_keep = lambda r: r["mass"] >= 8 and r["max_cell"] >= 4
        pois_keep = lambda r, t=th: (r["mass"] >= 8 and r["max_cell"] >= 4
                                     and r["poisson_z_max_cell"] >= t)
        oracle_keep = lambda r: r["label"] > 0

        arms = [
            ("baseline gate, mass weights", rows, "mass", base_keep, False),
            ("baseline gate, topology only", rows, "count", base_keep, False),
            ("baseline gate, weights SHUFFLED (null)", rows, "mass", base_keep, True),
            ("poisson gate, excess weights", rows, "excess_mass", pois_keep, False),
            ("poisson gate, topology only", rows, "count", pois_keep, False),
            ("poisson gate, weights SHUFFLED (null)", rows, "excess_mass", pois_keep, True),
            # oracle restricted to what the attack could see: isolates the WINDOW
            ("ORACLE among candidates", rows, "true_overlap", oracle_keep, False),
        ]
        if true_graph:
            # oracle over the FULL true graph: isolates the GEOMETRY
            arms.append(("ORACLE full true graph", true_graph, "true_overlap",
                         lambda r: True, False))
        tb = time_order_baseline(rows, true_start, min_size=args.min_comp, rng=rng)
        tb.update({"seed_dir": d.name, "arm": "TIME-ORDER baseline (no overlap used)",
                   "poisson_threshold": round(th, 3)})
        all_rows.append(tb)
        for name, src, wk, keep, sh in arms:
            if not src:
                continue
            src2 = src
            if src is true_graph:
                src2 = [{"parent": r["det_a"], "child": r["det_b"],
                         "true_overlap": r["true_overlap"]} for r in true_graph]
            res = score_arm(src2, wk, keep, true_start, rng, shuffle=sh,
                            min_size=args.min_comp)
            res.update({"seed_dir": d.name, "arm": name, "poisson_threshold": round(th, 3)})
            all_rows.append(res)

    args.outdir.mkdir(parents=True, exist_ok=True)
    cols = ["seed_dir", "arm", "poisson_threshold", "components", "nodes_ordered",
            "max_comp", "concordance", "null_concordance", "above_null"]
    with (args.outdir / "seriation.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        for r in all_rows:
            w.writerow({c: r.get(c, "") for c in cols})

    lines = ["# F3: recovering the order of queried ranges by spectral seriation",
             "",
             "Order is recovered from estimated overlap magnitudes only. No prior, no",
             "auxiliary dataset, no plaintext. Scored as |Spearman| against the true range",
             "starts, per connected component, sign-free (seriation is defined up to",
             "reflection). Components come from the linkage window, which fragments the",
             "graph by construction.",
             "",
             f"Components smaller than {args.min_comp} nodes are dropped: chance dominates them.",
             "",
             "| arm | comps | episodes ordered | largest comp | pair concordance | "
             "permutation null | above null |",
             "| --- | --- | --- | --- | --- | --- | --- |"]
    by_arm = defaultdict(list)
    for r in all_rows:
        by_arm[r["arm"]].append(r)
    for arm in ["TIME-ORDER baseline (no overlap used)"] + [a[0] for a in arms]:
        sel = [r for r in by_arm[arm] if r["components"]]
        if not sel:
            lines.append(f"| {arm} | 0 | - | - | - | - |")
            continue
        lines.append(
            f"| {arm} | {sum(r['components'] for r in sel)} | "
            f"{sum(r['nodes_ordered'] for r in sel)} | {max(r['max_comp'] for r in sel)} | "
            f"{mean(r['concordance'] for r in sel):.3f} | "
            f"{mean(r['null_concordance'] for r in sel):.3f} | "
            f"**{mean(r['above_null'] for r in sel):+.3f}** |")
    lines += ["",
              "`pair concordance` counts node PAIRS ordered correctly, reflection-free;",
              "`permutation null` is the same statistic on random orders of the SAME",
              "components. The number that carries information is the gain over the",
              "TIME-ORDER baseline, not over the permutation null: sorting episodes by",
              "when they were detected costs the attacker nothing, and on a workload that",
              "scans in value order it already scores 1.000.",
              "",
              "The two ORACLE arms answer different questions. `among candidates` keeps",
              "true pairs only where the attack produced a candidate, so it inherits the",
              "linkage window and isolates the WINDOW's effect. `full true graph` uses",
              "every truly overlapping pair, so it isolates the workload GEOMETRY: if it",
              "also fails, no amount of better estimation would have helped.",
              "",
              "Reading: the SHUFFLED arms are a second null - same components, same edges, the",
              "magnitudes permuted. The `topology only` arms show what unweighted overlap",
              "structure alone gives, so the gap between them and the weighted arms is what",
              "magnitude estimation buys. The ORACLE arm is the ceiling if pair selection",
              "and magnitudes were perfect, i.e. how much of the residual error is the",
              "attack's and how much is seriation's.",
              ""]
    (args.outdir / "summary.md").write_text("\n".join(lines))
    print("\n".join(lines))


if __name__ == "__main__":
    main()
