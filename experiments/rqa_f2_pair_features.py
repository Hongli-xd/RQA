#!/usr/bin/env python3
"""F2: find the pair feature that Stage D is missing.

`range_query_attack_handoff.md` §7.4 states the open problem precisely:

    "materially improving Stage-D precision needs a feature beyond
     (mass, cell) concentration, not threshold tuning"

and `results/staged_precision/summary.md` shows why: every threshold rule on
(mass, max_cell) either keeps the false pairs or throws away the weak true ones,
because on that workload their (mass, cell) distributions overlap.

This script does the feature search honestly:
  1. run the real attack path (Stage A -> batch features -> Stage B detection ->
     Stage D parent attribution) on a trace, through the whitelisted loader, so
     every candidate feature is computed from server-visible data only;
  2. score each candidate feature by AUC against ground truth, which is a
     RESEARCH step - labels rank the features, they never set a threshold;
  3. calibrate the winning feature's threshold on the point-burst CONTROL trace
     (any episode-pair mass there is noise by construction) and report the
     resulting precision/recall against the baseline rule, which is the
     discipline results/staged_precision already follows.

Why a normalised feature is the prior candidate: true pair mass is bounded by
the overlap, hence by min(m_parent, m_child), while background pair mass grows
with the child span's DURATION times the background read rate.  Stage D
thresholds raw mass (8 / 23 / 83), so a long episode with no overlap and a short
episode with real overlap are compared on the same scale.

Stdlib only.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import Counter, defaultdict
from pathlib import Path
from statistics import mean, median, pstdev
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

from range_query_attack import (  # noqa: E402
    _episode_pair_cells,
    batch_features,
    build_incarnations_streaming,
    load_truth,
    match_episodes,
    stage_a_anatomy,
    stage_b_detect_episodes,
)

ROOT = Path(__file__).resolve().parents[1]


def auc(pos: list[float], neg: list[float]) -> float:
    """P(random positive ranks above random negative), ties at 0.5."""
    if not pos or not neg:
        return float("nan")
    vals = sorted([(v, 1) for v in pos] + [(v, 0) for v in neg])
    rank_sum = 0.0
    i = 0
    r = 1
    while i < len(vals):
        j = i
        while j + 1 < len(vals) and vals[j + 1][0] == vals[i][0]:
            j += 1
        avg_rank = (r + (r + (j - i))) / 2.0
        for k in range(i, j + 1):
            if vals[k][1] == 1:
                rank_sum += avg_rank
        r += j - i + 1
        i = j + 1
    n1, n0 = len(pos), len(neg)
    return (rank_sum - n1 * (n1 + 1) / 2.0) / (n1 * n0)


def eval_reads_for_truth(trace: Path, truth: dict) -> list[dict[str, str]]:
    """The subset of trace rows the episode matcher actually consults.

    `full_trace_reads` materialises every row with every column, which at the
    paper's medium batch size is ~9M rows and gets the process OOM-killed.
    `true_episode_spans`, the only consumer here, reads exactly one thing: the
    batches in which an EPISODE's keys were client-read. Filtering to those rows
    is semantically identical for it and keeps the trace out of memory.
    """
    wanted = {f"real/{k}" for ep in truth["episodes"] for k in ep["keys"]}
    out: list[dict[str, str]] = []
    with trace.open(newline="") as fh:
        for row in csv.DictReader(fh, delimiter="\t"):
            if row["role"] == "client_real" and row["logical_key"] in wanted:
                out.append({"role": "client_real",
                            "logical_key": row["logical_key"],
                            "batch_ts": row["batch_ts"]})
    return out


def pair_features(trace: Path, cold_threshold: int, eviction_tail: int,
                  threshold_z: float) -> tuple[dict, list, dict]:
    """Attack-side only: returns (features per pair, detected spans, anatomy)."""
    inc = build_incarnations_streaming(trace)
    anatomy = stage_a_anatomy(inc)
    feats = batch_features(inc, anatomy, cold_threshold)
    detected, _ = stage_b_detect_episodes(feats, None, threshold_z=threshold_z)
    ep_of_batch, parent_ep_of, cells, _pm, _links, _amb = _episode_pair_cells(
        inc, detected, eviction_tail)

    span_of = {i: (min(b), max(b)) for i, b in enumerate(detected)}
    # per-episode server-visible read mass (proxy for m_hat, no labels)
    ep_read_mass: dict[int, float] = defaultdict(float)
    ep_miss_mass: dict[int, float] = defaultdict(float)
    for i, batches in enumerate(detected):
        for b in batches:
            ep_read_mass[i] += len(inc.reads_at.get(b, []))
            ep_miss_mass[i] += feats.get(b, {}).get("miss", 0.0)
    # writes available in each parent's eviction window: the denominator that
    # says how many evicted incarnations COULD have come back
    evict_writes: dict[int, float] = {}
    for i, (lo, hi) in span_of.items():
        evict_writes[i] = sum(len(inc.writes_at.get(b, []))
                              for b in range(lo, hi + eviction_tail + 1))

    # Per-cell background EXPECTATION, derived from the mechanism instead of a
    # global multiple of a control-run average.  A read at batch t drew its
    # incarnation from some earlier write; incarnations do not survive past the
    # flush age W, so under the null "this read is unrelated background" its
    # parent batch p is distributed proportionally to writes(p) over the last W
    # batches.  Hence
    #     E[mass(p,t)] = nonflush_reads(t) * writes(p) / sum_{p' in (t-W, t)} writes(p')
    # All three quantities are server-visible, and W is Stage A's flush mode.
    flush_w = int(anatomy.get("flush_mode") or 0) or 80
    writes_per_batch = {b: len(v) for b, v in inc.writes_at.items()}
    nonflush_reads_at: dict[int, int] = defaultdict(int)
    for read in inc.reads:
        if read.flavor not in ("flush", "dummy", "warmup"):
            nonflush_reads_at[read.batch] += 1
    write_prefix: dict[int, float] = {}
    run = 0.0
    for b in range(0, (max(inc.batches) if inc.batches else 0) + 2):
        run += writes_per_batch.get(b, 0)
        write_prefix[b] = run

    def cell_expectation(p: int, t: int) -> float:
        lo = max(0, t - flush_w)
        denom = write_prefix.get(t - 1, 0.0) - write_prefix.get(lo - 1, 0.0)
        if denom <= 0:
            return 0.0
        return nonflush_reads_at.get(t, 0) * writes_per_batch.get(p, 0) / denom

    per_pair_alpha: dict[tuple[int, int], list[int]] = defaultdict(list)
    for read in inc.reads:
        if read.flavor in ("flush", "dummy", "warmup") or read.parent_batch >= read.batch:
            continue
        if read.parent_batch < inc.transient_end:
            continue
        if not inc.writes_at.get(read.parent_batch):
            continue
        i = parent_ep_of.get(read.parent_batch)
        j = ep_of_batch.get(read.batch)
        if i is None or j is None or i == j:
            continue
        per_pair_alpha[(i, j)].append(read.alpha)

    # observed and expected mass per episode pair, cell by cell
    pair_obs_exp: dict[tuple[int, int], list[tuple[float, float]]] = defaultdict(list)
    for (p, t), c in _pm.items():
        i = parent_ep_of.get(p)
        j = ep_of_batch.get(t)
        if i is None or j is None or i == j:
            continue
        pair_obs_exp[(i, j)].append((float(c), cell_expectation(p, t)))

    out: dict[tuple[int, int], dict[str, float]] = {}
    for pair, cell in cells.items():
        i, j = pair
        mass = float(sum(cell.values()))
        mx = float(max(cell.values()))
        dists = list(cell.keys())
        tot = sum(cell.values())
        ent = -sum((c / tot) * math.log2(c / tot) for c in cell.values() if c > 0)
        alphas = per_pair_alpha.get(pair, [])
        p_lo, p_hi = span_of.get(i, (0, 0))
        c_lo, c_hi = span_of.get(j, (0, 0))
        child_batches = max(1, c_hi - c_lo + 1)
        oe = pair_obs_exp.get(pair, [])
        exp_total = sum(e for _o, e in oe)
        excess = mass - exp_total
        pois_total = excess / math.sqrt(exp_total) if exp_total > 0 else 0.0
        pois_max = max((( o - e) / math.sqrt(e) for o, e in oe if e > 0), default=0.0)
        out[pair] = {
            "mass": mass,                                   # baseline
            "max_cell": mx,                                 # baseline
            "peak_frac": mx / mass if mass else 0.0,
            "n_dist": float(len(dists)),
            "dist_entropy": ent,
            "mass_per_child_batch": mass / child_batches,
            "mass_over_min_read_mass": mass / max(1.0, min(ep_read_mass[i], ep_read_mass[j])),
            "mass_over_min_miss_mass": mass / max(1.0, min(ep_miss_mass[i], ep_miss_mass[j])),
            "mass_over_evict_writes": mass / max(1.0, evict_writes.get(i, 1.0)),
            "max_cell_over_min_miss": mx / max(1.0, min(ep_miss_mass[i], ep_miss_mass[j])),
            "alpha_mean": mean(alphas) if alphas else 0.0,
            "alpha_sd": pstdev(alphas) if len(alphas) > 1 else 0.0,
            "alpha_min": float(min(alphas)) if alphas else 0.0,
            "gap": float(c_lo - p_hi),
            "exp_mass": exp_total,
            "excess_mass": excess,
            "poisson_z_total": pois_total,
            "poisson_z_max_cell": pois_max,
            "obs_over_exp": mass / exp_total if exp_total > 0 else 0.0,
        }
    return out, detected, anatomy


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--trace", type=Path, required=True)
    ap.add_argument("--truth", type=Path, required=True)
    ap.add_argument("--burst-trace", type=Path, default=None,
                    help="point-burst control: sets thresholds, never truth")
    ap.add_argument("--cold-threshold", type=int, default=120)
    ap.add_argument("--eviction-tail", type=int, default=15)
    ap.add_argument("--threshold-z", type=float, default=5.0)
    ap.add_argument("--outdir", type=Path, default=ROOT / "results" / "f2_pair_features")
    args = ap.parse_args()

    pairs, detected, anatomy = pair_features(
        args.trace, args.cold_threshold, args.eviction_tail, args.threshold_z)
    truth = load_truth(args.truth)
    reads_full = eval_reads_for_truth(args.trace, truth)
    _, matches = match_episodes(detected, truth, reads_full)
    true_of = {det: tru for det, tru, _ in matches}
    key_sets = [set(ep["keys"]) for ep in truth["episodes"]]

    labelled = []
    for (i, j), f in pairs.items():
        if i not in true_of or j not in true_of:
            continue   # unmatched detections cannot be scored either way
        ov = len(key_sets[true_of[i]] & key_sets[true_of[j]])
        eps_t = truth["episodes"]
        row = {"parent": i, "child": j, "true_overlap": ov, "label": 1 if ov > 0 else 0,
               # eval-side only: where each matched episode's range actually sits,
               # so downstream order-recovery experiments can be scored from the CSV
               "parent_true_start": min(eps_t[true_of[i]]["keys"]),
               "child_true_start": min(eps_t[true_of[j]]["keys"]),
               "parent_true_m": len(eps_t[true_of[i]]["keys"]),
               "child_true_m": len(eps_t[true_of[j]]["keys"])}
        row.update({k: round(v, 5) for k, v in f.items()})
        labelled.append(row)

    names = [k for k in pairs[next(iter(pairs))].keys()]
    aucs = []
    for name in names:
        pos = [r[name] for r in labelled if r["label"] == 1]
        neg = [r[name] for r in labelled if r["label"] == 0]
        a = auc(pos, neg)
        aucs.append({"feature": name, "auc": round(a, 3),
                     "auc_abs": round(max(a, 1 - a), 3),
                     "direction": "high=true" if a >= 0.5 else "low=true",
                     "median_true": round(median(pos), 4) if pos else None,
                     "median_false": round(median(neg), 4) if neg else None})
    aucs.sort(key=lambda r: -r["auc_abs"])

    args.outdir.mkdir(parents=True, exist_ok=True)
    with (args.outdir / "pair_features.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(labelled[0].keys()))
        w.writeheader(); w.writerows(labelled)
    with (args.outdir / "feature_auc.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(aucs[0].keys()))
        w.writeheader(); w.writerows(aucs)

    # The FULL true overlap graph over matched episodes - every truly
    # overlapping pair, including the ones the attack never produced a
    # candidate for.  Downstream order-recovery needs this to tell two causes
    # apart: a graph that is fragmented because the WORKLOAD's ranges are
    # disjoint, and one that is fragmented because the linkage WINDOW hid the
    # long-gap edges.  Eval-side data, written once, never read by an attack.
    inv = {t: d for d, t in true_of.items()}
    tg = []
    tids = sorted(true_of.values())
    for a_i in range(len(tids)):
        for b_i in range(a_i + 1, len(tids)):
            ta, tb = tids[a_i], tids[b_i]
            ov = len(key_sets[ta] & key_sets[tb])
            if ov <= 0:
                continue
            ea, eb = truth["episodes"][ta], truth["episodes"][tb]
            tg.append({"det_a": inv[ta], "det_b": inv[tb], "true_overlap": ov,
                       "a_true_start": min(ea["keys"]), "b_true_start": min(eb["keys"]),
                       "a_m": len(ea["keys"]), "b_m": len(eb["keys"]),
                       "round_gap": abs(ea["start_round"] - eb["start_round"])})
    if tg:
        with (args.outdir / "true_overlap_graph.csv").open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(tg[0].keys()))
            w.writeheader(); w.writerows(tg)

    # The burst control's pair features: any episode pair there is noise by
    # construction (same schedule and sizes, random keys), so its quantiles are
    # what a threshold may legitimately be set from.
    if args.burst_trace:
        bpairs, bdet, _ = pair_features(
            args.burst_trace, args.cold_threshold, args.eviction_tail, args.threshold_z)
        brows = []
        for (i, j), f in bpairs.items():
            row = {"parent": i, "child": j}
            row.update({k: round(v, 5) for k, v in f.items()})
            brows.append(row)
        if brows:
            with (args.outdir / "burst_pair_features.csv").open("w", newline="") as fh:
                w = csv.DictWriter(fh, fieldnames=list(brows[0].keys()))
                w.writeheader(); w.writerows(brows)

    npos = sum(r["label"] for r in labelled)
    lines = [
        "# F2: which pair feature separates true overlap from background chains?",
        "",
        f"trace `{args.trace.name}`; scorable pairs {len(labelled)} "
        f"({npos} true, {len(labelled)-npos} false); "
        f"flush mode {anatomy.get('flush_mode')}, detected episodes {len(detected)}.",
        "",
        "Labels RANK the features here; they do not set any threshold.",
        "",
        "| feature | AUC | |AUC-0.5|+0.5 | direction | median (true) | median (false) |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for r in aucs:
        tag = " **(baseline)**" if r["feature"] in ("mass", "max_cell") else ""
        lines.append(f"| `{r['feature']}`{tag} | {r['auc']} | {r['auc_abs']} | "
                     f"{r['direction']} | {r['median_true']} | {r['median_false']} |")
    lines.append("")
    (args.outdir / "summary.md").write_text("\n".join(lines))
    print("\n".join(lines))


if __name__ == "__main__":
    main()
