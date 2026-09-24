#!/usr/bin/env python3
"""F2b: turn the winning pair feature into a decision rule, and score it against
the deployed baseline under this repo's own acceptance criteria.

Inputs are the CSVs written by rqa_f2_pair_features.py: the range run's
labelled pair features, and the point-burst control's pair features.

Discipline (same as results/staged_precision):
  * every THRESHOLD is a quantile of the BURST CONTROL distribution - the burst
    workload has the same schedule and episode sizes with random keys, so any
    episode-pair aggregate in it is noise by construction;
  * ground truth enters only to score the arms afterwards;
  * acceptance: within-window recall must not drop by more than 0.05, and
    precision must go up. A rule that buys precision by dropping weak true
    links is REJECTED, which is what killed the q99 mass rule previously.

Arms:
  baseline   mass >= 8 and max_cell >= 4                (deployed today)
  +peak      baseline and peak_frac  >= burst quantile  (scale-free concentration)
  +entropy   baseline and dist_entropy <= burst quantile
  peak_only  peak_frac >= burst quantile, no mass floor

Stdlib only.
"""

from __future__ import annotations

import argparse
import csv
import math
from pathlib import Path
from statistics import median

ROOT = Path(__file__).resolve().parents[1]


def read_csv(path: Path) -> list[dict[str, float]]:
    with path.open() as fh:
        rows = []
        for r in csv.DictReader(fh):
            rows.append({k: (float(v) if v not in ("", None) else 0.0) for k, v in r.items()})
        return rows


def quantile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    v = sorted(values)
    idx = min(len(v) - 1, max(0, int(round(q * (len(v) - 1)))))
    return v[idx]


def pearson(xs, ys) -> float:
    if len(xs) < 3:
        return 0.0
    mx, my = sum(xs) / len(xs), sum(ys) / len(ys)
    num = sum((a - mx) * (b - my) for a, b in zip(xs, ys))
    den = math.sqrt(sum((a - mx) ** 2 for a in xs) * sum((b - my) ** 2 for b in ys))
    return num / den if den else 0.0


def evaluate(rows: list[dict[str, float]], keep, window_gap: float):
    tp = fp = fn = 0
    win_tp = win_fn = 0
    est, est_x, tru = [], [], []
    for r in rows:
        k = keep(r)
        label = r["label"] > 0
        if label and k:
            tp += 1
        elif label and not k:
            fn += 1
        elif not label and k:
            fp += 1
        if label and r["gap"] <= window_gap:
            if k:
                win_tp += 1
            else:
                win_fn += 1
        # magnitude arm: kept pairs carry `mass` as the overlap estimate, as
        # Stage E does; dropped pairs carry 0.  `excess_mass` (observed minus the
        # per-cell background expectation) is scored alongside it, because the
        # same expectation model that gates the pair also de-biases its size.
        est.append(r["mass"] if k else 0.0)
        est_x.append(max(0.0, r.get("excess_mass", 0.0)) if k else 0.0)
        tru.append(r["true_overlap"])
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    return {
        "precision": round(prec, 3), "recall": round(rec, 3),
        "f1": round(2 * prec * rec / (prec + rec), 3) if prec + rec else 0.0,
        "within_window_recall": round(win_tp / (win_tp + win_fn), 3) if win_tp + win_fn else 0.0,
        "tp": tp, "fp": fp, "fn": fn,
        "magnitude_pearson": round(pearson(est, tru), 3),
        "magnitude_pearson_excess": round(pearson(est_x, tru), 3),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--seed-dirs", type=Path, nargs="+", required=True,
                    help="directories holding pair_features.csv + burst_pair_features.csv")
    ap.add_argument("--window-gap", type=float, default=70.0,
                    help="within-window gap bound (S1 window estimate, attack-side)")
    ap.add_argument("--quantiles", type=float, nargs="+", default=[0.5, 0.9, 0.99])
    ap.add_argument("--outdir", type=Path, default=ROOT / "results" / "f2_decision_rule")
    args = ap.parse_args()

    results = []
    for d in args.seed_dirs:
        rows = read_csv(d / "pair_features.csv")
        burst = read_csv(d / "burst_pair_features.csv")
        # burst noise conditioned on passing the deployed gates - the population a
        # new threshold has to cut into
        bn = [b for b in burst if b["mass"] >= 8 and b["max_cell"] >= 4]
        base = evaluate(rows, lambda r: r["mass"] >= 8 and r["max_cell"] >= 4, args.window_gap)
        base["arm"] = "baseline"; base["seed_dir"] = d.name; base["threshold"] = ""
        base["burst_noise_pairs"] = len(bn)
        results.append(base)
        for q in args.quantiles:
            th_peak = quantile([b["peak_frac"] for b in bn], q)
            th_ent = quantile([b["dist_entropy"] for b in bn], 1 - q)
            th_pois = quantile([b["poisson_z_max_cell"] for b in bn], q)
            th_ratio = quantile([b["obs_over_exp"] for b in bn], q)
            for arm, keep, th in [
                (f"+peak q{int(q*100)}",
                 lambda r, t=th_peak: r["mass"] >= 8 and r["max_cell"] >= 4 and r["peak_frac"] >= t,
                 th_peak),
                (f"+entropy q{int(q*100)}",
                 lambda r, t=th_ent: r["mass"] >= 8 and r["max_cell"] >= 4 and r["dist_entropy"] <= t,
                 th_ent),
                (f"+poisson q{int(q*100)}",
                 lambda r, t=th_pois: (r["mass"] >= 8 and r["max_cell"] >= 4
                                       and r["poisson_z_max_cell"] >= t), th_pois),
                (f"+obs_over_exp q{int(q*100)}",
                 lambda r, t=th_ratio: (r["mass"] >= 8 and r["max_cell"] >= 4
                                        and r["obs_over_exp"] >= t), th_ratio),
                (f"poisson_only q{int(q*100)}",
                 lambda r, t=th_pois: r["poisson_z_max_cell"] >= t, th_pois),
                (f"peak_only q{int(q*100)}",
                 lambda r, t=th_peak: r["peak_frac"] >= t, th_peak),
            ]:
                res = evaluate(rows, keep, args.window_gap)
                res["arm"] = arm; res["seed_dir"] = d.name
                res["threshold"] = round(th, 4); res["burst_noise_pairs"] = len(bn)
                results.append(res)

    args.outdir.mkdir(parents=True, exist_ok=True)
    cols = ["seed_dir", "arm", "threshold", "burst_noise_pairs", "precision", "recall", "f1",
            "within_window_recall", "tp", "fp", "fn", "magnitude_pearson",
            "magnitude_pearson_excess"]
    with (args.outdir / "decision_rule.csv").open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        for r in results:
            w.writerow({c: r.get(c, "") for c in cols})

    arms = sorted({r["arm"] for r in results}, key=lambda a: (a != "baseline", a))
    lines = ["# F2b: decision rule from the burst-calibrated concentration feature",
             "",
             f"within-window bound: gap <= {args.window_gap:g} batches. "
             "Thresholds are burst-control quantiles; truth only scores.",
             "",
             "| arm | seeds | precision | recall | F1 | within-window recall | "
             "dP vs base | dR_win vs base | mag Pearson (mass) | mag Pearson (excess) |",
             "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    base_by_dir = {r["seed_dir"]: r for r in results if r["arm"] == "baseline"}
    for arm in arms:
        sel = [r for r in results if r["arm"] == arm]
        if not sel:
            continue
        def avg(k):
            return sum(r[k] for r in sel) / len(sel)
        dp = avg("precision") - sum(base_by_dir[r["seed_dir"]]["precision"] for r in sel) / len(sel)
        dr = (sum(base_by_dir[r["seed_dir"]]["within_window_recall"] for r in sel) / len(sel)
              - avg("within_window_recall"))
        flag = " OK" if dr <= 0.05 and dp > 0 else (" VIOLATES recall" if dr > 0.05 else " no gain")
        lines.append(f"| `{arm}` | {len(sel)} | {avg('precision'):.3f} | {avg('recall'):.3f} | "
                     f"{avg('f1'):.3f} | {avg('within_window_recall'):.3f} | {dp:+.3f} | "
                     f"{dr:+.3f} |{flag} | {avg('magnitude_pearson'):.3f} | "
                     f"{avg('magnitude_pearson_excess'):.3f} |")
    lines += ["",
              "Acceptance: within-window recall drop <= 0.05 AND precision up.",
              "Baseline for the magnitude column: the deployed attack reaches",
              "Pearson 0.34-0.52 (results/staged_precision/summary.md).",
              ""]
    (args.outdir / "summary.md").write_text("\n".join(lines))
    print("\n".join(lines))


if __name__ == "__main__":
    main()
