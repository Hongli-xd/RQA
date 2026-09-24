#!/usr/bin/env python3
"""F0 precondition probe: is there a POPULARITY -> VISIBILITY channel in Waffle?

Why this comes first
--------------------
A prior-matching stage ("the adversary knows this is census data") needs the
data/query distribution to reach a server-visible quantity.  Reading Waffle's
own mechanism (Algorithm 1, as encoded in this repo's audited simulator) there
are only a few places where it could:

  M1  fake reals are drawn from the UNCACHED pool by least access timestamp,
      so cache membership decides who is swept and who is skipped;
  M2  only cache MISSES are visible, so a range query's visible cardinality is
      m * (1 - cached fraction of its keys);
  M4  but `_evict_and_cache` is applied to every selected real - client misses
      AND fake reals - so each batch inserts (B - f_D) keys into a cache of
      size C and evicts as many.

M4 predicts that the cache is flushed every  C / (B - f_D)  batches by the fake
sweep itself, i.e. it is a SWEEP BUFFER, not a popularity set.  If that holds,
the popularity -> visibility channel is dead: a range's visible fraction tells
the adversary nothing about WHERE in the popularity order the range sits, and
the only distributional handle left on a single episode is the value histogram
(whose ceiling is measured by rqa_prior_matching_analysis.py).  If it fails -
if hot keys really do sit in the cache - then the visible fraction localises a
range directly, which would be a much stronger channel than volume matching.

Either way the answer gates the design, so it is measured before any estimator
is written.

Discipline
----------
This is a MECHANISM STUDY, not an attack stage: it deliberately reads the
simulation labels (role, logical_key) to establish ground truth about the cache.
Nothing here may be copied into `range_query_attack.py`'s attack path.  The one
attack-side quantity it reports is the SPREAD of the invisible fraction across
episodes, because a stable spread is what an attack could calibrate out.

Stdlib only.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
from collections import defaultdict
from pathlib import Path
from statistics import mean, median, pstdev

ROOT = Path(__file__).resolve().parents[1]


def spearman(xs, ys) -> float:
    def ranks(v):
        order = sorted(range(len(v)), key=lambda i: v[i])
        r = [0.0] * len(v)
        i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and v[order[j + 1]] == v[order[i]]:
                j += 1
            avg = (i + j) / 2.0 + 1.0
            for k in range(i, j + 1):
                r[order[k]] = avg
            i = j + 1
        return r
    rx, ry = ranks(xs), ranks(ys)
    mx, my = mean(rx), mean(ry)
    num = sum((a - mx) * (b - my) for a, b in zip(rx, ry))
    den = math.sqrt(sum((a - mx) ** 2 for a in rx) * sum((b - my) ** 2 for b in ry))
    return num / den if den else 0.0


def load_rows(trace: Path):
    with trace.open() as fh:
        for row in csv.DictReader(fh, delimiter="\t"):
            yield row


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--trace", type=Path, required=True)
    ap.add_argument("--truth", type=Path, required=True)
    ap.add_argument("--n-real", type=int, default=8192)
    ap.add_argument("--cache-size", type=int, default=512)
    ap.add_argument("--batch-size", type=int, default=128)
    ap.add_argument("--dummy-reads", type=int, default=16)
    ap.add_argument("--zipf", type=float, default=0.9)
    ap.add_argument("--outdir", type=Path, default=ROOT / "results" / "f0_cache_channel")
    args = ap.parse_args()

    # --- reconstruct per-key cache residence from the labelled trace --------
    # A read of a real key (client or fake) is followed by _evict_and_cache, so
    # the key is cached from that batch until an `evicted_real` write appears.
    cached_from: dict[int, int] = {}
    residence: dict[int, int] = defaultdict(int)
    spells: dict[int, int] = defaultdict(int)
    reads: dict[int, int] = defaultdict(int)
    client_reads: dict[int, int] = defaultdict(int)
    t_max = 0
    for row in load_rows(args.trace):
        lk = row["logical_key"]
        if not lk.startswith("real/"):
            continue
        key = int(lk.split("/")[1])
        t = int(row["batch_ts"])
        t_max = max(t_max, t)
        role, direction = row["role"], row["direction"]
        if direction == "read":
            reads[key] += 1
            if role == "client_real":
                client_reads[key] += 1
            cached_from[key] = t
        elif role == "evicted_real":
            start = cached_from.pop(key, None)
            if start is not None and t >= start:
                residence[key] += t - start
                spells[key] += 1
    for key, start in cached_from.items():
        residence[key] += max(0, t_max - start)
        spells[key] += 1

    predicted_flush = args.cache_size / max(1, (args.batch_size - args.dummy_reads))
    spell_lengths = [residence[k] / spells[k] for k in spells if spells[k]]
    p_cached = {k: residence[k] / max(1, t_max) for k in range(args.n_real)}

    # --- popularity: the workload samples key ids by zipf rank -------------
    weights = [1.0 / ((i + 1) ** args.zipf) for i in range(args.n_real)]
    wsum = sum(weights)
    weights = [w / wsum for w in weights]

    decile_rows = []
    per = max(1, args.n_real // 10)
    for dec in range(10):
        lo, hi = dec * per, min(args.n_real, (dec + 1) * per)
        ks = list(range(lo, hi))
        decile_rows.append({
            "popularity_decile": dec + 1,
            "key_range": f"{lo}-{hi-1}",
            "mean_zipf_weight": sum(weights[lo:hi]) / len(ks),
            "mean_p_cached": mean(p_cached[k] for k in ks),
            "mean_reads": mean(reads[k] for k in ks),
            "mean_client_reads": mean(client_reads[k] for k in ks),
        })

    ks = list(range(args.n_real))
    rho_pop_cached = spearman([weights[k] for k in ks], [p_cached[k] for k in ks])
    rho_pop_reads = spearman([weights[k] for k in ks], [reads[k] for k in ks])

    # --- per-episode invisible fraction vs the episode's popularity --------
    truth = json.loads(args.truth.read_text())
    # cache state at episode start, reconstructed exactly as eval_c does
    events: dict[int, list[tuple[int, str]]] = defaultdict(list)
    for row in load_rows(args.trace):
        lk = row["logical_key"]
        if not lk.startswith("real/"):
            continue
        if row["role"] in ("client_real", "fake_real", "evicted_real"):
            events[int(lk.split("/")[1])].append((int(row["batch_ts"]), row["role"]))
    for k in events:
        events[k].sort()

    ep_rows = []
    for ep in truth["episodes"]:
        start, keys = ep["start_round"], ep["keys"]
        visible = 0
        for k in keys:
            prior = [e for e in events.get(k, []) if e[0] < start]
            if not prior or prior[-1][1] == "evicted_real":
                visible += 1
        beta = 1.0 - visible / max(1, len(keys))
        ep_rows.append({
            "episode": ep["episode_id"], "start": start, "m": len(keys),
            "visible": visible, "invisible_fraction": round(beta, 4),
            "mean_key_id": mean(keys),
            "mean_zipf_weight": mean(weights[k] for k in keys),
        })

    betas = [r["invisible_fraction"] for r in ep_rows]
    rho_beta_pop = spearman([r["mean_zipf_weight"] for r in ep_rows], betas)

    args.outdir.mkdir(parents=True, exist_ok=True)
    with (args.outdir / "popularity_deciles.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(decile_rows[0].keys()))
        w.writeheader(); w.writerows(decile_rows)
    with (args.outdir / "episode_visibility.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(ep_rows[0].keys()))
        w.writeheader(); w.writerows(ep_rows)

    out = [
        "# F0 probe: popularity -> visibility channel in Waffle",
        "",
        "MECHANISM STUDY (reads simulation labels on purpose; not an attack stage).",
        "",
        f"- trace: `{args.trace.name}`, batches: {t_max}, N={args.n_real}, C={args.cache_size}, "
        f"B={args.batch_size}, f_D={args.dummy_reads}",
        "",
        "## M4: is the cache a popularity set or a sweep buffer?",
        "",
        f"- predicted cache flush period C/(B-f_D) = {predicted_flush:.2f} batches",
        f"- measured mean cache spell = {mean(spell_lengths):.2f} batches "
        f"(median {median(spell_lengths):.2f}, sd {pstdev(spell_lengths):.2f}, n={len(spell_lengths)})",
        f"- a key is cached {100*mean(p_cached.values()):.2f}% of the time on average "
        f"(C/N = {100*args.cache_size/args.n_real:.2f}%)",
        "",
        "## Does popularity buy cache residence?",
        "",
        f"- Spearman(zipf weight, P(cached)) = {rho_pop_cached:+.3f}",
        f"- Spearman(zipf weight, total reads) = {rho_pop_reads:+.3f}  "
        "(reads are dominated by the fake sweep, which is popularity-BLIND)",
        "",
        "| popularity decile | keys | mean zipf weight | mean P(cached) | mean reads | mean client reads |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for r in decile_rows:
        out.append(f"| {r['popularity_decile']} | {r['key_range']} | {r['mean_zipf_weight']:.2e} | "
                   f"{r['mean_p_cached']:.4f} | {r['mean_reads']:.1f} | {r['mean_client_reads']:.2f} |")
    out += [
        "",
        "## Does a range's position in the popularity order change what the server sees?",
        "",
        f"- episodes: {len(ep_rows)}",
        f"- invisible fraction beta: mean {mean(betas):.4f}, median {median(betas):.4f}, "
        f"sd {pstdev(betas):.4f}, min {min(betas):.4f}, max {max(betas):.4f}",
        f"- Spearman(episode mean zipf weight, beta) = {rho_beta_pop:+.3f}",
        "",
        "Reading: |rho| near 0 with a small sd(beta) means the visible cardinality is",
        "a nearly position-independent multiple of m - the adversary can calibrate the",
        "bias away (helping Stage C) but learns nothing about WHERE the range is from",
        "it.  A large |rho| would mean the opposite: visibility localises the range.",
        "",
    ]
    (args.outdir / "summary.md").write_text("\n".join(out))
    print("\n".join(out))


if __name__ == "__main__":
    main()
