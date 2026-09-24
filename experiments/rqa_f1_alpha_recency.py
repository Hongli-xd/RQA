#!/usr/bin/env python3
"""F1: the alpha-recency channel - a new observable derived from Waffle's own
write-back mechanism rather than transplanted from the SSE attack literature.

Where it comes from (mechanism, not analogy)
--------------------------------------------
Waffle is write-once-read-once: every access rewrites the object under a fresh
PRF id, so each incarnation has an exactly measurable age

        alpha = t_read - t_write   (server-visible integer arithmetic)

and `_evict_and_cache` rewrites an object when the LRU evicts it, about
C/(B - f_D) batches after it was last touched.  Hence, per real object:

  * nobody asked for it -> its next read is the least-timestamp FAKE sweep and
    alpha lands on the pool flush age (N-C)/f_R: the sharp spike Stage A already
    calibrates in order to subtract fakes;
  * a client asked for it -> alpha is that object's client inter-arrival gap
    minus its cache residence, i.e. a SHORT alpha.

Stage A keeps the spike and discards everything else.  The discarded short-alpha
population is precisely the set of objects accessed recently, so counting it
inside a detected episode estimates HOW MANY of that episode's keys were
touched in the recent past - a graded overlap magnitude, which is the weakest
quantity in the existing attack (Stage E magnitude Pearson 0.34-0.52, Stage D
pair precision 0.40-0.50).

Two estimator designs are scored, because the obvious one is unsound:

  E1 fraction  = short-alpha reads / all non-spike reads in the span.
     Whatever fraction of fakes leaks past the spike filter lands in its
     DENOMINATOR, and the leak grows with the span length, so E1 inherits the
     spike calibration's error.  Given a correct window it performs as well as
     E2; given a window that leaks 17% of fakes it drops from 0.84 to 0.61.
  E2 excess    = short-alpha reads in the span minus the LOCAL background rate
     (median over batches +-`local_bg`, span excluded), exactly the discipline
     Stage C uses for cardinality.  E2 has no denominator, and for tau below the
     flush age the fake population lies entirely ABOVE tau, so E2 needs no fake
     filter at all: the spike-robustness table below shows it is invariant to
     the window.  That removes a whole hyperparameter dependency from the stage,
     which is why E2 is the deployed arm.

Anti-cheating audit (this file's own history is the cautionary case)
-------------------------------------------------------------------
An earlier version of this probe hard-coded the spike window as 78..84.  That
number was read off a role-labelled alpha histogram, i.e. it was ground truth
laundered into the attack, and it inflated the correlation from 0.27 to 0.80.
The window is now calibrated the way Stage A must calibrate it: take the alpha
mode, measure the SMOOTH background bin height well below the mode, and widen
while bins stand above `spike_bg_mult` x that background.  No label is consulted,
and `--spike-window` exists only to reproduce the contaminated run on demand.

  * `est_*` columns: batch timestamps, storage ids and the self-calibrated spike
    window only.
  * `true_*` / `own_*` columns: label-derived, used solely to score, in the
    `eval_*` role this repo already separates.
  * nulls/controls in the same run: `alpha_shuffled` keeps every alpha value and
    batch but destroys which object each belongs to; the point-burst trace keeps
    the schedule and episode sizes while removing range structure.

Stdlib only.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import random
from collections import defaultdict
from pathlib import Path
from statistics import mean, median

ROOT = Path(__file__).resolve().parents[1]


def pearson(xs, ys) -> float:
    if len(xs) < 3:
        return 0.0
    mx, my = mean(xs), mean(ys)
    num = sum((a - mx) * (b - my) for a, b in zip(xs, ys))
    den = math.sqrt(sum((a - mx) ** 2 for a in xs) * sum((b - my) ** 2 for b in ys))
    return num / den if den else 0.0


def spearman(xs, ys) -> float:
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
    return pearson(rk(xs), rk(ys))


def load_incarnations(trace: Path):
    """(batch_ts, role, key, alpha) per real read. role/key are label columns and
    are handed only to the eval half."""
    wtime: dict[str, int] = {}
    out = []
    with trace.open() as fh:
        for row in csv.DictReader(fh, delimiter="\t"):
            sk = row["storage_key"]
            if row["direction"] == "write":
                wtime[sk] = int(row["batch_ts"])
                continue
            if not row["logical_key"].startswith("real/"):
                continue
            t = int(row["batch_ts"])
            w = wtime.get(sk)
            if w is not None:
                out.append((t, row["role"], int(row["logical_key"].split("/")[1]), t - w))
    return out


def flush_window(alphas, bg_mult: float = 4.0, lo_cut: int = 3) -> tuple[int, int, float]:
    """Self-calibrated flush spike: (lo, hi, background bin height).

    The spike sits on top of a smooth client-read background.  Estimate that
    background as the median bin height over [mode/3, 2*mode/3] - far enough
    below the spike to be uncontaminated, close enough to share its scale - then
    widen the window while bins exceed `bg_mult` x background.  Attack-side
    only: it reads the alpha histogram, nothing else.
    """
    hist: dict[int, int] = defaultdict(int)
    for a in alphas:
        if a > lo_cut:
            hist[a] += 1
    if not hist:
        return (0, 0, 0.0)
    mode = max(hist, key=lambda a: hist[a])
    band = [hist.get(a, 0) for a in range(max(lo_cut + 1, mode // 3), max(lo_cut + 2, 2 * mode // 3))]
    bg = median(band) if band else 0.0
    floor = max(bg * bg_mult, hist[mode] * 0.001)
    lo = hi = mode
    while hist.get(lo - 1, 0) > floor:
        lo -= 1
    while hist.get(hi + 1, 0) > floor:
        hi += 1
    return (lo, hi, bg)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--trace", type=Path, required=True)
    ap.add_argument("--truth", type=Path, required=True)
    ap.add_argument("--control-trace", type=Path, default=None)
    ap.add_argument("--control-truth", type=Path, default=None)
    ap.add_argument("--client-requests", type=int, default=64)
    ap.add_argument("--taus", type=int, nargs="+", default=[20, 30, 40, 60])
    ap.add_argument("--local-bg", type=int, default=40,
                    help="local background half-window, as Stage C uses")
    ap.add_argument("--spike-bg-mult", type=float, default=4.0)
    ap.add_argument("--spike-window", type=int, nargs=2, default=None,
                    help="force the spike window (reproduces the contaminated run)")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--outdir", type=Path, default=ROOT / "results" / "f1_alpha_recency")
    args = ap.parse_args()
    rng = random.Random(args.seed)

    def score(trace: Path, truth_path: Path, tau: int, shuffle: bool):
        reads = load_incarnations(trace)
        if args.spike_window:
            spike_lo, spike_hi = args.spike_window
            bg_height = float("nan")
        else:
            spike_lo, spike_hi, bg_height = flush_window(
                [a for *_x, a in reads], args.spike_bg_mult)
        if shuffle:
            alphas = [a for *_x, a in reads]
            rng.shuffle(alphas)
            reads = [(t, r, k, a) for (t, r, k, _), a in zip(reads, alphas)]

        short_per_batch: dict[int, int] = defaultdict(int)
        nonspike_per_batch: dict[int, int] = defaultdict(int)
        by_batch: dict[int, list[tuple[str, int, int]]] = defaultdict(list)
        client_hist: dict[int, list[int]] = defaultdict(list)
        for t, role, k, a in sorted(reads):
            by_batch[t].append((role, k, a))
            if role == "client_real":
                client_hist[k].append(t)
            if not (spike_lo <= a <= spike_hi):
                nonspike_per_batch[t] += 1
                if a < tau:
                    short_per_batch[t] += 1
        batches = sorted(by_batch)

        truth = json.loads(truth_path.read_text())
        rows = []
        for ep in truth["episodes"]:
            start, keys = ep["start_round"], list(ep["keys"])
            kset = set(keys)
            span = list(range(start, start + max(1, math.ceil(len(keys) / args.client_requests)) + 2))
            sset = set(span)
            lo, hi = min(span), max(span)
            outside = [short_per_batch[b] for b in batches
                       if lo - args.local_bg <= b <= hi + args.local_bg and b not in sset]
            bg = median(outside) if outside else 0.0
            short_mass = sum(short_per_batch[b] for b in span)
            nonspike_mass = sum(nonspike_per_batch[b] for b in span)
            own = [a for b in span for (role, k, a) in by_batch.get(b, [])
                   if k in kset and role == "client_real"]
            if len(own) < 10:
                continue
            true_recent = sum(1 for k in keys
                              if any(start - tau <= t < start for t in client_hist.get(k, [])))
            rows.append({
                "episode": ep["episode_id"], "m": len(keys), "batches": len(span),
                "true_recent_count": true_recent,
                "true_recent_frac": true_recent / len(keys),
                "own_frac_short": sum(1 for a in own if a < tau) / len(own),
                # E1: ratio (kept as the negative control)
                "e1_frac_short": short_mass / max(1, nonspike_mass),
                # E2: local-background-subtracted excess count
                "e2_short_excess": max(0.0, short_mass - bg * len(span)),
                "bg_local": bg,
            })
        return rows, (spike_lo, spike_hi, bg_height)

    results = []
    per_ep_dump = None
    for tau in args.taus:
        rows, spike = score(args.trace, args.truth, tau, shuffle=False)
        null_rows, _ = score(args.trace, args.truth, tau, shuffle=True)
        tcount = [r["true_recent_count"] for r in rows]
        tfrac = [r["true_recent_frac"] for r in rows]
        rec = {
            "tau": tau, "spike": f"{spike[0]}-{spike[1]}", "spike_bg_height": spike[2],
            "episodes": len(rows),
            "eval_ceiling_rho": round(spearman(tfrac, [r["own_frac_short"] for r in rows]), 3),
            "E1_frac_rho": round(spearman(tfrac, [r["e1_frac_short"] for r in rows]), 3),
            "E2_excess_rho": round(spearman(tcount, [r["e2_short_excess"] for r in rows]), 3),
            "E2_excess_r": round(pearson(tcount, [r["e2_short_excess"] for r in rows]), 3),
            "E2_null_shuffled_rho": round(
                spearman([r["true_recent_count"] for r in null_rows],
                         [r["e2_short_excess"] for r in null_rows]), 3),
        }
        if args.control_trace and args.control_truth:
            crows, _ = score(args.control_trace, args.control_truth, tau, shuffle=False)
            rec["E2_burst_control_rho"] = round(
                spearman([r["true_recent_count"] for r in crows],
                         [r["e2_short_excess"] for r in crows]), 3)
            rec["burst_episodes"] = len(crows)
        results.append(rec)
        if per_ep_dump is None:
            per_ep_dump = (tau, rows)

    # Spike-window robustness: perturb the attack's OWN calibration (no labels)
    # and watch which estimator moves.
    robust = []
    if not args.spike_window:
        tau0 = args.taus[0]
        base_lo, base_hi = flush_window(
            [a for *_x, a in load_incarnations(args.trace)], args.spike_bg_mult)[:2]
        for dlo, dhi, label in [(1, -1, "narrowed (leaks fakes)"), (0, 0, "self-calibrated"),
                                (-1, 1, "widened"), (-4, 7, "very wide")]:
            forced = (base_lo + dlo, base_hi + dhi)
            saved = args.spike_window
            args.spike_window = forced
            rows_r, _ = score(args.trace, args.truth, tau0, shuffle=False)
            args.spike_window = saved
            tc = [r["true_recent_count"] for r in rows_r]
            tf = [r["true_recent_frac"] for r in rows_r]
            robust.append({
                "tau": tau0, "window": f"{forced[0]}-{forced[1]}", "label": label,
                "E1_frac_rho": round(spearman(tf, [r["e1_frac_short"] for r in rows_r]), 3),
                "E2_excess_rho": round(spearman(tc, [r["e2_short_excess"] for r in rows_r]), 3),
            })

    args.outdir.mkdir(parents=True, exist_ok=True)
    if robust:
        with (args.outdir / "spike_robustness.csv").open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(robust[0].keys()))
            w.writeheader(); w.writerows(robust)
    with (args.outdir / "alpha_recency.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(results[0].keys()))
        w.writeheader(); w.writerows(results)
    tau0, rows0 = per_ep_dump
    with (args.outdir / f"per_episode_tau{tau0}.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows0[0].keys()))
        w.writeheader(); w.writerows(rows0)

    lines = [
        "# F1: the alpha-recency channel",
        "",
        f"trace `{args.trace.name}`; spike window self-calibrated "
        f"(bg_mult={args.spike_bg_mult}); local background half-window {args.local_bg}.",
        "",
        "Target: how many of a detected episode's keys were client-read in the",
        "preceding tau batches (a graded overlap magnitude).",
        "",
        "| tau | spike | bg bin height | eps | eval ceiling rho | E1 ratio rho | "
        "E2 excess rho | E2 excess r | E2 shuffled-alpha null | E2 burst control |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for r in results:
        lines.append(
            f"| {r['tau']} | {r['spike']} | {r['spike_bg_height']:.0f} | {r['episodes']} | "
            f"{r['eval_ceiling_rho']} | {r['E1_frac_rho']} | **{r['E2_excess_rho']}** | "
            f"{r['E2_excess_r']} | {r['E2_null_shuffled_rho']} | "
            f"{r.get('E2_burst_control_rho', 'n/a')} |")
    if robust:
        lines += ["", "## Spike-window robustness (perturbing the attack's own calibration)",
                  "", f"| forced window | what it is | E1 ratio rho | E2 excess rho |",
                  "| --- | --- | --- | --- |"]
        for r in robust:
            lines.append(f"| {r['window']} | {r['label']} | {r['E1_frac_rho']} | "
                         f"**{r['E2_excess_rho']}** |")
        lines += ["",
                  "E2 is invariant because for tau below the flush age the fake population",
                  "lies entirely above tau, so excluding it or not cannot change a count of",
                  "reads with alpha < tau; the window only ever touched E1's denominator.",
                  "E2 therefore needs no fake filter, only tau << flush age - and the flush",
                  "age is the quantity Stage A recovers most reliably (81/88, 50/50,",
                  "102/100, 256/256 across scales)."]
    lines += [
        "",
        "Baseline to beat: the existing attack's overlap MAGNITUDE quality is",
        "Pearson 0.34-0.52 with Stage-D pair precision 0.40-0.50",
        "(results/staged_precision/summary.md).",
        "",
        "Honest reading:",
        "- E1 is not inherently worse: with a correctly calibrated window it matches E2.",
        "  What separates them is robustness, as the table above shows.",
        "- E2 still conflates episode overlap with hot-key background traffic. That is",
        "  where a popularity prior has a real job - subtracting the confound - as",
        "  opposed to localising ranges, which the volume channel cannot do either",
        "  (see results/prior_matching/summary.md).",
        "- the burst control is NOT a false positive: E2 measures recency, which random",
        "  bursts also exhibit when they happen to touch recently read hot keys. E2",
        "  supports an overlap-MAGNITUDE claim, not a range-structure claim - the latter",
        "  stays with Stage D's co-parent concentration. E2's own controls are the",
        "  shuffled-alpha null (collapses) plus an overlap_bias=0 workload (not yet run).",
        "- E2 gives magnitude only; WHICH earlier episode the overlap is with still",
        "  requires Stage D. The two compose, neither replaces the other.",
        "- one config, one seed, 24 episodes. The matrix (4 scales x 3 seeds) and the",
        "  range-free control must reproduce this before it is a claim.",
        "",
    ]
    (args.outdir / "summary.md").write_text("\n".join(lines))
    print("\n".join(lines))


if __name__ == "__main__":
    main()
