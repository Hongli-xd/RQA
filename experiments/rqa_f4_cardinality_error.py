#!/usr/bin/env python3
"""F4: where does Stage C's cardinality error actually come from?

Stage C estimates a range query's visible cardinality as

    m_hat = sum(miss over the detected batches) - local_background_median * n_batches

and reaches 3-12.5% median relative error.  That number is the gating quantity
for everything a prior could do: at 12.5% a census-shaped histogram is worth
0.13 bit of positional information, at 3% it is worth 1.74 bits
(results/prior_matching/summary.md).  So the question is not whether to improve
it but WHICH of its three inputs to improve.

The estimator has three error sources and they are separable:

  1. SPAN     - Stage B's detected batch interval is not the episode's true
                drain window, so mass is lost off the ends or background is
                swept in.
  2. SERIES   - the per-batch miss count is itself recovered, as
                real_budget - flush_count, and Stage A's flush accounting has a
                known systematic bias (f_D is underestimated, so the budget is
                over-estimated by a few percent).
  3. BACKGROUND - the local median over +-40 batches is a crude estimate of the
                background miss rate under the episode.

This script measures each by substitution: it recomputes m_hat with one input
replaced by its ground-truth version at a time, so the residual error names the
culprit rather than a guess naming it.

Discipline: the substituted quantities come from the labelled trace and exist
only to attribute error. Nothing here is an attack estimator, and no threshold
is set from any of it - it is a diagnostic that tells the next round of attack
work where to aim.

Stdlib only.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import defaultdict
from pathlib import Path
from statistics import median, mean
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))

from range_query_attack import (  # noqa: E402
    batch_features,
    build_incarnations,
    full_trace_reads,
    load_events,
    load_truth,
    match_episodes,
    stage_a_anatomy,
    stage_b_detect_episodes,
    visible_targets,
)

ROOT = Path(__file__).resolve().parents[1]


def saturation_corrected(series: dict[int, float], span: list[int], bg: float,
                         drain: float) -> float:
    """REJECTED arm, kept because it is the instructive failure.

    The reasoning was: the proxy drains a fixed number of queued requests per
    batch, an episode's keys jump that queue, so in a saturated batch the
    background contributes nothing while the deployed estimator still subtracts
    a full local median from it.  That gives

        miss_b = e_b + bg * (1 - e_b / R)   =>   e_b = (miss_b - bg) / (1 - bg / R)

    and it is wrong, by a factor of four on this workload (0.55 median relative
    error against the deployed 0.14).  Displaced background requests are not
    destroyed, they are DEFERRED: the queue keeps them and drains them in the
    following batches.  So the mass returns, and inflating by 1/(1 - bg/R) -
    2.7x here, since bg is around 40 of a 64-request drain - double-counts it.

    The same fact explains why substituting the TRUE (narrower) drain window
    makes the estimate worse, not better: a window that ends when the episode's
    own keys stop arriving cuts off the deferred background before it returns.
    Integrating to baseline instead is the arm that follows from this.
    """
    if drain <= 0 or bg >= drain:
        return max(0.0, sum(series.get(b, 0.0) for b in span) - bg * len(span))
    scale = 1.0 / (1.0 - bg / drain)
    return max(0.0, sum(max(0.0, series.get(b, 0.0) - bg) for b in span) * scale)


def integrate_to_baseline(series: dict[int, float], span: list[int], bg: float,
                          noise: float, all_batches: list[int],
                          max_extend: int = 20, quiet_needed: int = 2) -> tuple[float, int]:
    """Stage C over a window extended until the excess returns to background.

    The episode both adds its own misses and defers background ones, so its
    footprint in the miss series is longer than the batches in which its keys
    arrive.  Extend the detected span outward while batches still stand above
    background by more than the series' own noise scale, stopping after
    `quiet_needed` consecutive quiet batches.  Everything here is attack-side:
    the background level and the noise scale both come from the miss series.
    """
    lo, hi = min(span), max(span)
    bset = set(all_batches)
    quiet = 0
    end = hi
    for b in range(hi + 1, hi + max_extend + 1):
        if b not in bset:
            break
        if series.get(b, 0.0) > bg + noise:
            end = b
            quiet = 0
        else:
            quiet += 1
            if quiet >= quiet_needed:
                break
    quiet = 0
    start = lo
    for b in range(lo - 1, lo - max_extend - 1, -1):
        if b not in bset:
            break
        if series.get(b, 0.0) > bg + noise:
            start = b
            quiet = 0
        else:
            quiet += 1
            if quiet >= quiet_needed:
                break
    win = [b for b in range(start, end + 1) if b in bset]
    return max(0.0, sum(series.get(b, 0.0) - bg for b in win)), len(win)


def excess(series: dict[int, float], span: list[int], local_bg: int,
           all_batches: list[int]) -> tuple[float, float]:
    """Stage C's estimator over an arbitrary span and miss series."""
    sset = set(span)
    lo, hi = min(span), max(span)
    outside = [series.get(b, 0.0) for b in all_batches
               if lo - local_bg <= b <= hi + local_bg and b not in sset]
    bg = median(outside) if outside else 0.0
    mass = sum(series.get(b, 0.0) for b in span)
    return max(0.0, mass - bg * len(span)), bg


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--trace", type=Path, required=True)
    ap.add_argument("--truth", type=Path, required=True)
    ap.add_argument("--cold-threshold", type=int, default=300)
    ap.add_argument("--threshold-z", type=float, default=5.0)
    ap.add_argument("--local-bg", type=int, default=40)
    ap.add_argument("--client-requests", type=int, default=64)
    ap.add_argument("--outdir", type=Path, default=ROOT / "results" / "f4_cardinality")
    args = ap.parse_args()

    inc = build_incarnations(load_events(args.trace))
    anatomy = stage_a_anatomy(inc)
    inc.transient_end = int(anatomy["transient_end"])
    feats = batch_features(inc, anatomy, args.cold_threshold)
    detected, _ = stage_b_detect_episodes(feats, None, threshold_z=args.threshold_z)
    all_batches = sorted(feats)

    truth = load_truth(args.truth)
    reads = full_trace_reads(args.trace)
    _, matches = match_episodes(detected, truth, reads)
    targets, raw_m = visible_targets(truth, reads)

    # --- ground-truth versions of the estimator's inputs ------------------
    # SERIES: the labelled per-batch client-miss count
    true_series: dict[int, float] = defaultdict(float)
    for row in reads:
        if row["role"] == "client_real":
            true_series[int(row["batch_ts"])] += 1.0
    # note: a client_real read IS a miss by construction (hits never reach the
    # server), so this is the exact series Stage A is trying to recover.

    # SPAN: the batches in which each true episode's keys were actually read
    key_batches: dict[int, list[int]] = defaultdict(list)
    for row in reads:
        if row["role"] == "client_real":
            key_batches[int(row["logical_key"].split("/")[1])].append(int(row["batch_ts"]))
    true_span: dict[int, list[int]] = {}
    for ep in truth["episodes"]:
        start, keys = ep["start_round"], ep["keys"]
        hit = []
        for k in keys:
            for b in key_batches.get(k, []):
                if start <= b <= start + max(4, math.ceil(len(keys) / args.client_requests) + 3):
                    hit.append(b)
        true_span[ep["episode_id"]] = sorted(set(hit)) or [start]

    rec_series = {b: feats[b]["miss"] for b in all_batches}
    # attack-side drain estimate: a batch that is entirely client misses hits the
    # per-batch request limit, so a high quantile of the miss series finds it.
    ms = sorted(rec_series.values())
    drain_hat = ms[int(0.995 * (len(ms) - 1))] if ms else 0.0
    # robust noise scale of the miss series (attack-side): MAD about the median
    _med = median(ms) if ms else 0.0
    noise_scale = 1.4826 * median([abs(v - _med) for v in ms]) if ms else 0.0

    rows = []
    for det_id, true_id, iou in matches:
        span_det = sorted(detected[det_id])
        span_tru = true_span[true_id]
        tgt = targets[true_id]
        if tgt <= 0:
            continue
        m_current, bg_c = excess(rec_series, span_det, args.local_bg, all_batches)
        m_sat = saturation_corrected(rec_series, span_det, bg_c, drain_hat)
        m_int, win_len = integrate_to_baseline(rec_series, span_det, bg_c,
                                               noise_scale, all_batches)
        m_fix_span, _ = excess(rec_series, span_tru, args.local_bg, all_batches)
        m_fix_series, _ = excess(true_series, span_det, args.local_bg, all_batches)
        m_fix_both, _ = excess(true_series, span_tru, args.local_bg, all_batches)
        # background substitution: the true background is the client-miss mass in
        # the span that does NOT belong to this episode
        ep_keys = set(truth["episodes"][true_id]["keys"])
        own = 0
        for row in reads:
            if row["role"] != "client_real":
                continue
            b = int(row["batch_ts"])
            if b in set(span_det) and int(row["logical_key"].split("/")[1]) in ep_keys:
                own += 1
        rows.append({
            "episode": det_id, "iou": round(iou, 3), "target_visible": tgt,
            "raw_m": raw_m[true_id],
            "batches_det": len(span_det), "batches_true": len(span_tru),
            "m_current": round(m_current, 1),
            "m_fix_span": round(m_fix_span, 1),
            "m_fix_series": round(m_fix_series, 1),
            "m_fix_both": round(m_fix_both, 1),
            "m_ideal_own_mass": own,
            "err_current": round(abs(m_current - tgt) / tgt, 4),
            "err_fix_span": round(abs(m_fix_span - tgt) / tgt, 4),
            "err_fix_series": round(abs(m_fix_series - tgt) / tgt, 4),
            "err_fix_both": round(abs(m_fix_both - tgt) / tgt, 4),
            "err_own_mass": round(abs(own - tgt) / tgt, 4),
            "m_saturation": round(m_sat, 1),
            "err_saturation": round(abs(m_sat - tgt) / tgt, 4),
            "m_integrate": round(m_int, 1), "win_len": win_len,
            "err_integrate": round(abs(m_int - tgt) / tgt, 4),
        })

    if not rows:
        print("no matched episodes to score")
        return
    args.outdir.mkdir(parents=True, exist_ok=True)
    with (args.outdir / "cardinality_error.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader(); w.writerows(rows)

    def med(k):
        return median(r[k] for r in rows)

    lines = [
        "# F4: error decomposition of Stage C's cardinality estimate",
        "",
        f"trace `{args.trace.name}`; {len(rows)} matched episodes; "
        f"median detected span {med('batches_det'):.0f} batches vs true {med('batches_true'):.0f}.",
        "",
        "Each arm replaces ONE input of the estimator with its ground-truth version.",
        "The arm whose error drops is the one worth attacking.",
        "",
        "| estimator | median rel. err | mean rel. err | what it isolates |",
        "| --- | --- | --- | --- |",
        f"| deployed (recovered series, detected span) | **{med('err_current'):.3f}** | "
        f"{mean(r['err_current'] for r in rows):.3f} | - |",
        f"| integrate-to-baseline (attack-side, noise={noise_scale:.1f}) | "
        f"**{med('err_integrate'):.3f}** | {mean(r['err_integrate'] for r in rows):.3f} | "
        f"deferred background returning (median window {med('win_len'):.0f} batches) |",
        f"| saturation-corrected [REJECTED] | "
        f"{med('err_saturation'):.3f} | {mean(r['err_saturation'] for r in rows):.3f} | "
        f"a wrong model, kept as the record |",
        f"| true span, recovered series | {med('err_fix_span'):.3f} | "
        f"{mean(r['err_fix_span'] for r in rows):.3f} | Stage B's span error |",
        f"| detected span, true miss series | {med('err_fix_series'):.3f} | "
        f"{mean(r['err_fix_series'] for r in rows):.3f} | Stage A's series error |",
        f"| true span, true series | {med('err_fix_both'):.3f} | "
        f"{mean(r['err_fix_both'] for r in rows):.3f} | both |",
        f"| episode's own read mass (floor) | {med('err_own_mass'):.3f} | "
        f"{mean(r['err_own_mass'] for r in rows):.3f} | the background-subtraction floor |",
        "",
        f"Signed bias (median m_hat - target): deployed "
        f"{median(r['m_current'] - r['target_visible'] for r in rows):+.1f}, "
        f"integrate-to-baseline "
        f"{median(r['m_integrate'] - r['target_visible'] for r in rows):+.1f}, "
        f"saturation-corrected "
        f"{median(r['m_saturation'] - r['target_visible'] for r in rows):+.1f}.",
        "",
        "The last row is not an estimator: it counts only the reads that really",
        "belong to the episode, so it is what perfect background separation would",
        "give. Any residual there is the target definition itself (a key read",
        "inside the span that was already counted as cached at the start).",
        "",
    ]
    (args.outdir / "summary.md").write_text("\n".join(lines))
    print("\n".join(lines))


if __name__ == "__main__":
    main()
