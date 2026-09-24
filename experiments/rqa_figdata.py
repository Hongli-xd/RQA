#!/usr/bin/env python3
"""Collect every result in this line of work into one JSON for the figures.

Reads the committed CSV/MD outputs plus (optionally) one trace for the alpha
histogram, and writes results/figures/figdata.json.  Keeping the figure inputs
in one reproducible artifact means a plot can never disagree with the table it
came from.

Stdlib only.
"""

from __future__ import annotations

import argparse
import csv
import json
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RES = ROOT / "results"


def rows(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open() as fh:
        return list(csv.DictReader(fh))


def alpha_hist(trace: Path, max_alpha: int = 130) -> list[dict]:
    """alpha histogram split by role. The SPLIT is a label-derived overlay used
    to explain the mechanism in the figure; the attack only ever sees the total."""
    wtime: dict[str, int] = {}
    hist: dict[int, dict[str, int]] = defaultdict(lambda: {"client": 0, "fake": 0, "dummy": 0})
    with trace.open() as fh:
        for row in csv.DictReader(fh, delimiter="\t"):
            sk = row["storage_key"]
            if row["direction"] == "write":
                wtime[sk] = int(row["batch_ts"])
                continue
            w = wtime.get(sk)
            if w is None:
                continue
            a = int(row["batch_ts"]) - w
            if a > max_alpha:
                continue
            role = row["role"]
            bucket = "client" if role == "client_real" else ("fake" if role == "fake_real" else "dummy")
            hist[a][bucket] += 1
    return [{"alpha": a, **hist[a]} for a in sorted(hist)]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--trace", type=Path, default=RES / "f2_runs/s7/range_seed7_waffle.tsv")
    ap.add_argument("--out", type=Path, default=RES / "figures" / "figdata.json")
    args = ap.parse_args()

    data = {
        "alpha_hist": alpha_hist(args.trace) if args.trace.exists() else [],
        "f0_deciles": rows(RES / "f0_cache_channel/popularity_deciles.csv"),
        "f1_tau_sweep": rows(RES / "f1_alpha_recency/alpha_recency.csv"),
        "f1_spike_robustness": rows(RES / "f1_alpha_recency/spike_robustness.csv"),
        "f1_per_episode": rows(RES / "f1_alpha_recency/per_episode_tau20.csv"),
        "f2_auc": {d.name: rows(d / "feature_auc.csv")
                   for d in sorted(p for p in (RES / "f2_pair_features").glob("s*") if p.is_dir())},
        "f2b_decision": rows(RES / "f2_decision_rule/decision_rule.csv"),
        "f3_seriation": rows(RES / "f3_seriation/seriation.csv"),
        "prior_identifiability": rows(RES / "prior_matching/identifiability.csv"),
        "prior_chain": rows(RES / "prior_matching/chain_entropy.csv"),
        "constants": {
            "flush_period_predicted": 512 / 112,
            "flush_period_measured": 4.71,
            "retention_threshold_p_star": 112 / (64 * 512),
            "retention_rank": 27,
            "n_real": 8192,
            "stage_e_baseline_pearson": [0.34, 0.52],
            "stage_d_baseline_precision": [0.40, 0.50],
        },
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(data, separators=(",", ":")))
    print(f"wrote {args.out} ({args.out.stat().st_size/1024:.0f} KiB)")
    for k, v in data.items():
        if isinstance(v, list):
            print(f"  {k}: {len(v)} rows")
        elif isinstance(v, dict) and k == "f2_auc":
            print(f"  {k}: {[f'{n}:{len(r)}' for n, r in v.items()]}")


if __name__ == "__main__":
    main()
