#!/usr/bin/env python3
"""Window refinement: dense gap grid + logistic inflection estimate.

Replaces the quantised window estimate ("largest tested gap with >=50%
recovery" on a 4-5 point grid) with:

  1. a dense re-query grid {15,25,35,50,65,80,100,130,170,220,300,400}
     (make_episodes already accepts arbitrary gap lists; the grid is a
     workload-scheduling choice, not an attack parameter), and
  2. a hand-written maximum-likelihood logistic fit of the recovery
     probability  recovery(gap) = 1 / (1 + exp(k * (gap - w)))  on the
     raw (actual_gap, recovered?) truth pairs, fitted by Newton/IRLS on
     the linear re-parameterisation p = sigmoid(b + c*gap), k = -c,
     w = -b/c.  The inflection w is the leakage window; a >=200x
     nonparametric bootstrap over truth pairs gives its 95% CI.

Runs (fresh, this script): S1_n8k seeds 7/8/9 and S3_n500k seed 7 on the
dense grid, plus S2_n200k seed 7 and S3_n500k seed 7 on the legacy grid
(to compare old quantised vs new windows on identical traces-configs).
S1 legacy-grid baselines are reused from the sensitivity scan states.

Outputs (results/window_refine/):
  per_gap_recovery.csv  - pooled per-gap (n_pair, recovered, rate)
  window_fit.csv        - per config: w, k, bootstrap CI, quantised windows
  law_refit.csv         - per run: sweep time vs windows (old/new), ratios
  curve_<config>.txt    - ASCII recovery-vs-gap curves
  summary.md            - findings incl. monotonicity check and law refit

Stdlib only.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import random
import subprocess
import sys
from pathlib import Path
from statistics import mean

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "experiments" / "range_query_attack.py"
OUTDIR = ROOT / "results" / "window_refine"

DENSE_GAPS = (15, 25, 35, 50, 65, 80, 100, 130, 170, 220, 300, 400)
LEGACY_GAPS = {"S1_n8k": "20,45,90,200", "S2_n200k": "20,45,90,200",
               "S3_n500k": "20,45,90,200,400"}
DENSE_GAPS_STR = ",".join(str(g) for g in DENSE_GAPS)

BASE_MEDIUM = dict(
    n_dummy=70_000, batch_size=2500, client_requests=1000,
    dummy_reads=500, warmup=400, every=25, m_min=300, m_max=2000,
)
CONFIGS: dict[str, dict] = {
    "S1_n8k": dict(n_real=8192, n_dummy=2048, batch_size=128,
                   client_requests=64, dummy_reads=16, cache_size=512,
                   rounds=4000, warmup=400, every=45, m_min=40, m_max=160,
                   bg=40, cold=300, bias=0.5),
    "S2_n200k": dict(n_real=200_000, cache_size=4000, bg=120, cold=400,
                     bias=0.6, rounds=2400, **BASE_MEDIUM),
    "S3_n500k": dict(n_real=500_000, cache_size=10_000, bg=120, cold=800,
                     bias=0.7, rounds=1800, **BASE_MEDIUM),
}

RUNS: list[tuple[str, int, str]] = [
    # (config, seed, grid) - grid 'dense' or 'legacy'
    ("S1_n8k", 7, "dense"), ("S1_n8k", 8, "dense"), ("S1_n8k", 9, "dense"),
    ("S2_n200k", 7, "dense"), ("S2_n200k", 7, "legacy"),
    ("S3_n500k", 7, "dense"), ("S3_n500k", 7, "legacy"),
]
BOOTSTRAP_N = 500  # >= 200 required
BOOTSTRAP_SEED = 20260924


def sim_args(cfg: dict, seed: int, grid: str) -> list[str]:
    gaps = DENSE_GAPS_STR if grid == "dense" else LEGACY_GAPS[cfg_name_of(cfg)]
    return [
        "--seed", str(seed),
        "--n-real", str(cfg["n_real"]),
        "--n-dummy", str(cfg["n_dummy"]),
        "--batch-size", str(cfg["batch_size"]),
        "--client-requests", str(cfg["client_requests"]),
        "--dummy-reads", str(cfg["dummy_reads"]),
        "--cache-size", str(cfg["cache_size"]),
        "--rounds", str(cfg["rounds"]),
        "--warmup", str(cfg["warmup"]),
        "--episode-every", str(cfg["every"]),
        "--m-min", str(cfg["m_min"]),
        "--m-max", str(cfg["m_max"]),
        "--bg-rate", str(cfg["bg"]),
        "--cold-threshold", str(cfg["cold"]),
        "--overlap-bias", str(cfg["bias"]),
        "--requery-gaps", gaps,
        "--null-trials", "10", "--threshold-z", "5",
    ]


def cfg_name_of(cfg: dict) -> str:
    return {8192: "S1_n8k", 200_000: "S2_n200k", 500_000: "S3_n500k"}[cfg["n_real"]]


def run_dir(name: str, seed: int, grid: str) -> Path:
    return OUTDIR / f"{name}_s{seed}_{grid}"


def launch_missing() -> None:
    for name, seed, grid in RUNS:
        outdir = run_dir(name, seed, grid)
        if (outdir / "attack_state.json").exists():
            continue
        cmd = [sys.executable, str(SCRIPT), "--outdir", str(outdir),
               *sim_args(CONFIGS[name], seed, grid)]
        print(f"[refine] running {name} s{seed} {grid}", flush=True)
        proc = subprocess.run(cmd, cwd=ROOT, stdout=subprocess.DEVNULL,
                              stderr=subprocess.STDOUT)
        if proc.returncode != 0:
            raise RuntimeError(f"run failed: {name} s{seed} {grid}")


# ---------------------------------------------------------------------------
# Logistic fit: recovery(gap) = 1/(1+exp(k*(gap-w))) = sigmoid(b + c*gap)
# with b = k*w, c = -k.  Newton/IRLS on the concave binomial log-likelihood.
# ---------------------------------------------------------------------------

def sigmoid(z: float) -> float:
    if z >= 0:
        return 1.0 / (1.0 + math.exp(-min(z, 700.0)))
    ez = math.exp(max(z, -700.0))
    return ez / (1.0 + ez)


def irls_fit(gaps: list[float], hits: list[float],
             iters: int = 2000, tol: float = 1e-10, c_cap: float = 50.0
             ) -> tuple[float, float, str]:
    """Return (b, c, kind) for p = sigmoid(b + c*gap), kind in
    {'converged', 'capped', 'stalled'}.  Convergence is judged on the
    inflection w = -b/c (Newton on near-separated data moves b and c
    slowly along a flat-likelihood ridge, but w settles quickly)."""
    b = c = 0.0
    kind = "stalled"
    w_prev = float("inf")
    for _ in range(iters):
        s11 = s12 = s22 = g1 = g2 = 0.0
        for g, y in zip(gaps, hits):
            p = sigmoid(b + c * g)
            w = p * (1.0 - p) + 1e-12
            s11 += w
            s12 += w * g
            s22 += w * g * g
            g1 += y - p
            g2 += (y - p) * g
        det = s11 * s22 - s12 * s12
        if det <= 1e-14:
            break
        db = (g1 * s22 - g2 * s12) / det
        dc = (g2 * s11 - g1 * s12) / det
        b += db
        c += dc
        if abs(c) > c_cap:
            # rescale b so that w = -b/c stays at the current inflection
            w_now = -b / c if c else 0.0
            c = math.copysign(c_cap, c)
            b = -w_now * c
            kind = "capped"
            continue
        if c != 0.0:
            w_now = -b / c
            if abs(w_now - w_prev) < 1e-6 and abs(db) + abs(dc) < 1e-3:
                kind = "converged"
                break
            w_prev = w_now
    if kind == "stalled" and abs(c) >= 5.0:
        # Hessian collapsed because probabilities saturated (perfect
        # separation): the inflection is identified, the slope is not.
        kind = "capped"
    return b, c, kind


def separation_interval(pairs: list[tuple[float, float]]) -> tuple[float, float] | None:
    """If the data is monotonically separated (every recovered pair sits at
    a smaller gap than every unrecovered pair), return (max recovered gap,
    min unrecovered gap) - the interval that brackets the true window."""
    hits = [g for g, h in pairs if h >= 0.5]
    misses = [g for g, h in pairs if h < 0.5]
    if not hits or not misses:
        return None
    hi, lo = max(hits), min(misses)
    return (hi, lo) if hi < lo else None


def fit_window(pairs: list[tuple[float, float]]) -> dict:
    """Fit recovery(gap); pairs = [(actual_gap, hit)]. Returns w, k, kind."""
    gaps = [p[0] for p in pairs]
    hits = [p[1] for p in pairs]
    b, c, kind = irls_fit(gaps, hits)
    if c == 0.0:
        return {"w": None, "k": None, "kind": "stalled",
                "note": "degenerate fit (slope 0)"}
    k = -c
    w = -b / c
    sep = separation_interval(pairs)
    if sep:
        # separated (or nearly separated) data: any w inside (sep[0],
        # sep[1]) achieves the same likelihood; use the midpoint as the
        # point estimate and let the bootstrap span the interval
        kind = "capped" if kind != "converged" else kind
        w = (sep[0] + sep[1]) / 2.0
    return {"w": w, "k": k, "b": b, "c": c, "kind": kind,
            "separation": sep}


def bootstrap_window(pairs: list[tuple[float, float]], n_boot: int,
                     seed: int) -> tuple[list[float], int]:
    """Percentile bootstrap of w. Returns (w_samples, n_failed).  Capped
    (near-separated) fits are ACCEPTED: the cap localises w inside the
    separation interval, so the CI honestly spans the identifiable range."""
    rng = random.Random(seed)
    ws: list[float] = []
    failed = 0
    n = len(pairs)
    gmax = max(p[0] for p in pairs)
    for _ in range(n_boot):
        sample = [pairs[rng.randrange(n)] for _ in range(n)]
        fit = fit_window(sample)
        if fit["w"] is None or fit["kind"] == "stalled" \
                or not (0 < fit["w"] < 2 * gmax):
            failed += 1
            continue
        if fit["separation"] is not None:
            # flat likelihood inside the interval: draw w uniformly so the
            # CI reflects the genuinely unidentified range
            lo, hi = fit["separation"]
            ws.append(lo + (hi - lo) * rng.random())
        else:
            ws.append(fit["w"])
    return ws, failed


def percentile(vals: list[float], q: float) -> float:
    if not vals:
        return float("nan")
    s = sorted(vals)
    idx = min(len(s) - 1, max(0, round((len(s) - 1) * q)))
    return s[idx]


def quantized_window(pairs: list[tuple[float, float]], grid: list[float],
                     rate_cut: float = 0.5) -> float:
    """Legacy estimator: largest grid gap whose binned rate >= rate_cut.
    Each pair is assigned to its NEAREST grid point (actual gaps can be
    shifted by the scheduler's collision avoidance)."""
    binned: dict[float, list[int]] = {}
    for gap, hit in pairs:
        g = nearest_grid(gap, grid)
        binned.setdefault(g, [0, 0])
        binned[g][0] += 1
        binned[g][1] += int(hit)
    best = 0.0
    for g, (n, hit) in binned.items():
        if n >= 1 and hit / n >= rate_cut:
            best = max(best, g)
    return best


def nearest_grid(gap: float, grid: list[float]) -> float:
    return min(grid, key=lambda g: abs(g - gap))


GAP_OF_BUCKET = {"0-30": 20, "31-60": 45, "61-120": 90,
                 "121-240": 200, "240+": 400}


def load_pairs_and_meta(state_path: Path) -> dict:
    state = json.loads(state_path.read_text())
    ev = state.get("stage_e", {}).get("eval", {})
    pairs = [(p[0], p[1]) for p in ev.get("boundary_pairs", [])]
    if not pairs:
        # legacy-format state (pre per-gap eval_e): reconstruct bucket-level
        # pairs at the bucket's representative gap - sufficient for the
        # quantised window estimator, which was itself bucket-based.
        for key, val in ev.get("boundary_by_gap", {}).items():
            gap = GAP_OF_BUCKET.get(key)
            if gap is None:
                try:
                    gap = float(key)
                except ValueError:
                    continue
            n_pair, hit = int(val[0]), int(val[1])
            pairs.extend([(float(gap), 1.0)] * hit)
            pairs.extend([(float(gap), 0.0)] * (n_pair - hit))
    a = state.get("stage_a", {}).get("range", {})
    budget = a.get("real_reads_hat", 0)
    miss_med = a.get("miss_median", 0)
    f_r_est = max(1.0, budget - miss_med)
    n_real = state.get("n_real", 0)
    cache = state.get("cache_size", 0)
    return {
        "pairs": pairs,
        "sweep_theory": (n_real - cache) / f_r_est if n_real else float("nan"),
        "flush_age": a.get("flush_mode", 0),
        "f1": state.get("stage_b", {}).get("eval", {}).get("f1", 0.0),
    }


def ascii_curve(rows: list[tuple[float, int, int]], width: int = 50) -> str:
    lines = ["gap    n   rate  curve"]
    for gap, n, hit in rows:
        rate = hit / n if n else 0.0
        bar = "#" * int(round(rate * width))
        lines.append(f"{gap:>4}  {n:>3}  {rate:.2f}  {bar}")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--aggregate-only", action="store_true")
    args = parser.parse_args()
    if not args.aggregate_only:
        launch_missing()
    OUTDIR.mkdir(parents=True, exist_ok=True)

    # ---- collect per-run data -------------------------------------------
    runs_meta: list[dict] = []
    for name, seed, grid in RUNS:
        meta = load_pairs_and_meta(run_dir(name, seed, grid) / "attack_state.json")
        meta.update({"config": name, "seed": seed, "grid": grid})
        grid_vals = list(DENSE_GAPS) if grid == "dense" else \
            [int(g) for g in LEGACY_GAPS[name].split(",")]
        meta["window_quant"] = quantized_window(meta["pairs"], grid_vals)
        # dense-grid quantized window also computed on the dense grid for
        # same-run comparison (independent of which grid the run used)
        meta["window_quant_dense"] = quantized_window(meta["pairs"], list(DENSE_GAPS))
        runs_meta.append(meta)
    # S1 legacy baselines from the sensitivity scan (Task 1)
    sens = ROOT / "results" / "sensitivity" / "states"
    for seed in (7, 8, 9):
        p = sens / f"baseline_1x_s{seed}.json"
        if p.exists():
            meta = load_pairs_and_meta(p)
            meta.update({"config": "S1_n8k", "seed": seed, "grid": "legacy"})
            meta["window_quant"] = quantized_window(
                meta["pairs"], [20, 45, 90, 200])
            meta["window_quant_dense"] = quantized_window(meta["pairs"], list(DENSE_GAPS))
            runs_meta.append(meta)

    # ---- per-config pooled fit -------------------------------------------
    fit_rows: list[dict] = []
    curve_rows: list[dict] = []
    for name in ("S1_n8k", "S2_n200k", "S3_n500k"):
        dense_runs = [m for m in runs_meta
                      if m["config"] == name and m["grid"] == "dense"]
        if not dense_runs:
            continue
        pooled: list[tuple[float, float]] = []
        for m in dense_runs:
            pooled.extend(m["pairs"])
        pooled.sort()

        # per-gap table (binned to the nearest dense grid point)
        binned: dict[float, list[int]] = {}
        for gap, hit in pooled:
            binned.setdefault(nearest_grid(gap, list(DENSE_GAPS)), [0, 0])
            binned[nearest_grid(gap, list(DENSE_GAPS))][0] += 1
            binned[nearest_grid(gap, list(DENSE_GAPS))][1] += int(hit)
        curve = sorted(binned.items())
        for gap, (n, hit) in curve:
            curve_rows.append({
                "config": name, "gap": int(gap), "n_pair": n,
                "recovered": hit,
                "rate": round(hit / n, 3) if n else "",
            })
        (OUTDIR / f"curve_{name}.txt").write_text(
            f"# recovery vs gap ({name}, dense grid, pooled over runs)\n"
            + ascii_curve([(g, n, h) for g, (n, h) in curve]) + "\n")

        # monotonicity diagnostic on adjacent gaps with n >= 5
        viol = []
        for (g1, (n1, h1)), (g2, (n2, h2)) in zip(curve, curve[1:]):
            if n1 >= 5 and n2 >= 5 and h2 / n2 > h1 / n1:
                viol.append(f"{g1:g}({h1}/{n1})->{g2:g}({h2}/{n2})")
        hi = max((h / n for g, (n, h) in curve if n >= 5 and g <= 50), default=0.0)
        lo = min((h / n for g, (n, h) in curve if n >= 5 and g >= 170), default=1.0)
        clean = (not viol) and hi >= 0.8 and lo <= 0.2

        # logistic fit + bootstrap on the raw pairs
        fit = fit_window(pooled)
        sep = fit.get("separation")
        row = {
            "config": name, "n_runs": len(dense_runs),
            "n_pairs": len(pooled),
            "window_quant_dense": quantized_window(pooled, list(DENSE_GAPS)),
            "monotonicity_violations": ";".join(viol) if viol else "none",
            "clean_sigmoid": clean,
            "fit_kind": fit["kind"],
            "separation_interval": (f"({sep[0]:g},{sep[1]:g})" if sep
                                     else ""),
        }
        if fit["w"] is not None and fit["kind"] in ("converged", "capped"):
            ws, failed = bootstrap_window(pooled, BOOTSTRAP_N, BOOTSTRAP_SEED)
            row.update({
                "w": round(fit["w"], 1),
                "k": round(fit["k"], 4),
                "w_boot_mean": round(mean(ws), 1) if ws else "",
                "w_ci95_lo": round(percentile(ws, 0.025), 1) if ws else "",
                "w_ci95_hi": round(percentile(ws, 0.975), 1) if ws else "",
                "n_boot_failed": failed,
            })
        else:
            row.update({"w": "", "k": "", "w_boot_mean": "",
                        "w_ci95_lo": "", "w_ci95_hi": "",
                        "n_boot_failed": ""})
        fit_rows.append(row)

    with (OUTDIR / "per_gap_recovery.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(curve_rows[0].keys()))
        writer.writeheader()
        writer.writerows(curve_rows)
    with (OUTDIR / "window_fit.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(fit_rows[0].keys()))
        writer.writeheader()
        writer.writerows(fit_rows)

    # ---- law refit: window vs sweep time, three estimators ----------------
    law_rows: list[dict] = []
    for m in runs_meta:
        if m["grid"] == "legacy":
            continue  # law points come from the dense runs
        law_rows.append({
            "config": m["config"], "seed": m["seed"],
            "flush_age": m["flush_age"],
            "sweep_theory": round(m["sweep_theory"], 1),
            "window_old_grid": next(
                (x["window_quant"] for x in runs_meta
                 if x["config"] == m["config"] and x["grid"] == "legacy"
                 and x["seed"] == m["seed"]), ""),
            "window_dense_quant": m["window_quant_dense"],
            "f1": round(m["f1"], 3),
        })
    fits = {}
    fr = {r["config"]: r for r in fit_rows}
    for col in ("window_old_grid", "window_dense_quant"):
        xs, ys = [], []
        for r in law_rows:
            y = r.get(col)
            if isinstance(y, (int, float)) and y:
                xs.append(r["sweep_theory"])
                ys.append(float(y))
        if xs:
            slope = sum(x * y for x, y in zip(xs, ys)) / sum(x * x for x in xs)
            ss_res = sum((y - slope * x) ** 2 for x, y in zip(xs, ys))
            ss_tot = sum((y - mean(ys)) ** 2 for y in ys)
            fits[col] = (slope, 1 - ss_res / ss_tot if ss_tot else 0.0, len(xs))
    # logistic-w fit: one pooled w per config (x = mean sweep of its runs)
    xs, ys = [], []
    for name in fr:
        w = fr[name].get("w")
        if isinstance(w, (int, float)) and w != "":
            sweeps = [r["sweep_theory"] for r in law_rows if r["config"] == name]
            if sweeps:
                xs.append(mean(sweeps))
                ys.append(float(w))
    if xs:
        slope = sum(x * y for x, y in zip(xs, ys)) / sum(x * x for x in xs)
        ss_res = sum((y - slope * x) ** 2 for x, y in zip(xs, ys))
        ss_tot = sum((y - mean(ys)) ** 2 for y in ys)
        fits["w_logistic"] = (slope, 1 - ss_res / ss_tot if ss_tot else 0.0, len(xs))
    with (OUTDIR / "law_refit.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(law_rows[0].keys()))
        writer.writeheader()
        writer.writerows(law_rows)

    # ---- summary ---------------------------------------------------------
    lines = [
        "# Window refinement: dense gap grid + logistic inflection estimate",
        "",
        f"Dense grid: {list(DENSE_GAPS)}; make_episodes already accepts",
        "arbitrary gap lists, so this is purely a workload-scheduling change",
        "(no attack-code change; the CLI default grid stays 20,45,90,200 so",
        "pre-existing results reproduce bit-for-bit).",
        "",
        "recovery(gap) = 1/(1+exp(k*(gap-w))) fitted by Newton/IRLS (stdlib",
        "only) on the raw (actual gap, recovered?) truth pairs; w is the",
        f"50%-recovery inflection = the leakage window. Bootstrap: {BOOTSTRAP_N}",
        "resamples of the truth pairs, percentile CI.",
        "",
        "## Per-config fit (dense grid, pooled over runs)",
        "",
    ]
    cols = list(fit_rows[0].keys())
    lines.append("| " + " | ".join(cols) + " |")
    lines.append("|" + "---|" * len(cols))
    for r in fit_rows:
        lines.append("| " + " | ".join(str(r[c]) for c in cols) + " |")
    lines += [
        "",
        "Notes: `window_quant_dense` = largest dense-grid gap with >=50%",
        "recovery (still a quantised lower bound); `clean_sigmoid` requires",
        "no monotonicity violation between adjacent gaps (n>=5), >=80%",
        "recovery at gap<=50 and <=20% at gap>=170.",
        "",
        "## ASCII recovery curves",
        "",
    ]
    for name in ("S1_n8k", "S2_n200k", "S3_n500k"):
        p = OUTDIR / f"curve_{name}.txt"
        if p.exists():
            lines += [f"### {name}", "", "```", p.read_text().rstrip(), "```", ""]
    lines += ["## Old (quantised) vs new (logistic) window", "",
              "| config | legacy-grid window | dense-grid window | logistic w [95% CI] |",
              "| --- | --- | --- | --- |"]
    for name in ("S1_n8k", "S2_n200k", "S3_n500k"):
        frn = fr.get(name, {})
        legacy = [m["window_quant"] for m in runs_meta
                  if m["config"] == name and m["grid"] == "legacy"]
        legacy_s = "/".join(f"{v:g}" for v in legacy) if legacy else "-"
        wtxt = "-"
        if frn.get("w") != "":
            wtxt = (f"{frn.get('w')} [{frn.get('w_ci95_lo')}, "
                    f"{frn.get('w_ci95_hi')}]")
            if frn.get("fit_kind") == "capped":
                wtxt += f" (near-separated; interval {frn.get('separation_interval')})"
        lines.append(f"| {name} | {legacy_s} | "
                     f"{frn.get('window_quant_dense', '-')} | {wtxt} |")
    lines += [
        "",
        "## Scaling-law refit (window vs sweep time (N-C)/f_R, through origin)",
        "",
        "| window estimator | slope | R^2 | points |",
        "| --- | --- | --- | --- |",
    ]
    for key, label in (("window_old_grid", "legacy-grid quantised"),
                       ("window_dense_quant", "dense-grid quantised"),
                       ("w_logistic", "logistic w (dequantised)")):
        if key in fits:
            slope, r2, n = fits[key]
            lines.append(f"| {label} | {slope:.3f} | {r2:.3f} | {n} |")
    lines += [
        "",
        "Per-run law points: `law_refit.csv`. Caveats: the refit spans",
        "fewer runs than the original 14-run matrix (S1 x3 seeds, S2, S3),",
        "and each config's logistic w is pooled over its runs, so R^2 here",
        "is not directly comparable in sample size to the original 0.960.",
        "",
    ]
    (OUTDIR / "summary.md").write_text("\n".join(lines))
    print(f"[refine] wrote {OUTDIR / 'summary.md'}")


if __name__ == "__main__":
    main()
