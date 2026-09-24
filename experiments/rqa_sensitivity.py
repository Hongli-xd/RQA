#!/usr/bin/env python3
"""Hyperparameter sensitivity scan for the Waffle range-query attack.

For every attack-side hyperparameter exposed by Task 0
(track_span, flush_frac, local_bg, min_mass, window, gap, min_pair_mass,
max_cell, eviction_tail) this script independently scans {0.5x, 1x, 2x}
while keeping all other parameters at their defaults, on the S1_n8k
configuration (see rqa_scaling_matrix.CONFIGS) with seeds 7, 8, 9.

Per (parameter, level, seed) it records:
  * Stage B detection F1 (plus precision/recall),
  * Stage C median relative cardinality error,
  * Stage E window estimate (largest tested gap with >=50% recovery),
  * permutation-null mean overlap mass and the attack's own total
    kept overlap mass (the null-vs-attack separation check).

Efficiency: traces depend only on simulation parameters, never on attack
hyperparameters, so all runs for one seed share one trace cache directory
(results/sensitivity/_traces_s{seed}); only the attack stages are re-run.

Flip criteria (documented in results/sensitivity/summary.md):
  (a) |F1 - F1_1x| <= 0.15 at every level (absolute, per seed),
  (b) the window estimate never moves by more than 2 grid steps
      on the tested gap grid,
  (c) null mean < attack total overlap mass in every run.

Stdlib only. Outputs: results/sensitivity/{sensitivity.csv,summary.md}.
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from statistics import mean, pstdev

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "experiments" / "range_query_attack.py"
OUTDIR = ROOT / "results" / "sensitivity"

# S1_n8k (identical to rqa_scaling_matrix.CONFIGS entry of that name).
S1_SIM_ARGS = [
    "--n-real", "8192", "--n-dummy", "2048", "--batch-size", "128",
    "--client-requests", "64", "--dummy-reads", "16", "--cache-size", "512",
    "--rounds", "4000", "--warmup", "400", "--episode-every", "45",
    "--m-min", "40", "--m-max", "160", "--bg-rate", "40",
    "--cold-threshold", "300", "--overlap-bias", "0.5",
    "--requery-gaps", "20,45,90,200", "--null-trials", "10",
    "--threshold-z", "5",
]

# (canonical name, CLI flag, default, kind) - defaults equal the values that
# were hard-coded before Task 0 parameterisation.
PARAMS: list[tuple[str, str, float, str]] = [
    ("track_span", "--track-span", 80, "int"),
    ("flush_frac", "--flush-frac", 0.08, "float"),
    ("local_bg", "--local-bg", 40, "int"),
    ("min_mass", "--min-mass", 30.0, "float"),
    ("window", "--window", 50, "int"),
    ("gap", "--gap", 3, "int"),
    ("min_pair_mass", "--min-pair-mass", 8.0, "float"),
    ("max_cell", "--max-cell", 4, "int"),
    ("eviction_tail", "--eviction-tail", 15, "int"),
]

MULTIPLIERS = (0.5, 1.0, 2.0)


def level_label(mult: float) -> str:
    return f"{mult:g}x"
SEEDS = (7, 8, 9)

GAP_OF_BUCKET = {"0-30": 20, "31-60": 45, "61-120": 90, "121-240": 200, "240+": 400}
WINDOW_GRID = [20, 45, 90, 200, 400]


def level_value(base: float, mult: float, kind: str) -> float | int:
    raw = base * mult
    if kind == "int":
        return max(1, int(round(raw)))
    return raw


def window_estimate(boundary: dict) -> float:
    """Largest tested gap with >=50% recovery; supports both the legacy
    bucket format ('0-30': [n, hit]) and the per-gap format ('45': [n,hit])."""
    best = 0.0
    for key, val in boundary.items():
        n_pair, hit = int(val[0]), int(val[1])
        if n_pair == 0:
            continue
        gap = GAP_OF_BUCKET.get(key)
        if gap is None:
            try:
                gap = float(key)
            except ValueError:
                continue
        if hit / n_pair >= 0.5:
            best = max(best, gap)
    return best


def window_level(window: float) -> int:
    """Index of the window on the tested grid; -1 if nothing recovered."""
    if window <= 0:
        return -1
    for i, g in enumerate(WINDOW_GRID):
        if abs(window - g) < 1e-9:
            return i
    # window between grid points (dense-grid runs): count how many grid
    # steps below it
    return max(0, sum(1 for g in WINDOW_GRID if g < window) - 1)


def metrics_of(state: dict) -> dict:
    sb = state.get("stage_b", {}).get("eval", {})
    sc = state.get("stage_c", {}).get("eval", {})
    se = state.get("stage_e", {})
    sd = state.get("stage_d", {})
    boundary = se.get("eval", {}).get("boundary_by_gap", {})
    overlap_counts = sd.get("overlap_counts", {})
    return {
        "f1": sb.get("f1", 0.0),
        "precision": sb.get("precision", 0.0),
        "recall": sb.get("recall", 0.0),
        "n_detected": sb.get("detected", 0.0),
        "true_episodes": sb.get("true_episodes", 0.0),
        "c_median_rel_err": sc.get("median_rel_err_vs_visible", 0.0),
        "c_n": sc.get("n", 0.0),
        "window_est": window_estimate(boundary),
        "null_mean": se.get("null", {}).get("null_overlap_mean", 0.0),
        "attack_overlap_mass": sum(v for v in overlap_counts.values()),
        "n_est_pairs": sum(1 for v in overlap_counts.values() if v > 0),
        "pearson": se.get("eval", {}).get("pearson", 0.0),
        "pearson_large": se.get("eval", {}).get("pearson_large_overlap", 0.0),
        "n_pairs_scored": se.get("eval", {}).get("pairs", 0.0),
        "true_pos_pairs": se.get("eval", {}).get("positive_pairs", 0.0),
        "est_pos_pairs": se.get("eval", {}).get("estimated_positive_pairs", 0.0),
    }


def state_path(param: str, level: str, seed: int) -> Path:
    return OUTDIR / "states" / f"{param}_{level}_s{seed}.json"


def run_one(seed: int, param: str | None, level: str, extra: list[str]) -> Path:
    """Run the attack script once for this seed; traces are cached in the
    seed's shared directory, so only attack stages are recomputed."""
    trace_dir = OUTDIR / f"_traces_s{seed}"
    target = state_path(param or "baseline", level, seed)
    if target.exists():
        return target
    cmd = [
        sys.executable, str(SCRIPT),
        "--seed", str(seed), "--outdir", str(trace_dir), *S1_SIM_ARGS,
    ] + extra
    trace_dir.mkdir(parents=True, exist_ok=True)
    (OUTDIR / "states").mkdir(parents=True, exist_ok=True)
    start = time.time()
    proc = subprocess.run(cmd, stdout=subprocess.DEVNULL,
                          stderr=subprocess.STDOUT, cwd=ROOT)
    if proc.returncode != 0:
        raise RuntimeError(f"run failed: {param} {level} seed {seed}")
    shutil.copyfile(trace_dir / "attack_state.json", target)
    print(f"[sens] {param or 'baseline'} {level} seed={seed} "
          f"({time.time() - start:.0f}s)", flush=True)
    return target


def scan_seed(seed: int) -> None:
    # Baseline (all defaults) is the shared 1x point for every parameter and
    # generates the seed's trace cache.
    run_one(seed, None, "1x", [])
    for name, flag, base, kind in PARAMS:
        for mult in MULTIPLIERS:
            if mult == 1.0:
                continue  # shared baseline
            value = level_value(base, mult, kind)
            run_one(seed, name, level_label(mult), [flag, str(value)])


def collect() -> list[dict]:
    rows: list[dict] = []
    for name, _flag, base, kind in PARAMS:
        for mult in MULTIPLIERS:
            level = level_label(mult)
            for seed in SEEDS:
                path = state_path(
                    "baseline" if mult == 1.0 else name, level, seed
                )
                state = json.loads(path.read_text())
                row = {
                    "param": name,
                    "level": level,
                    "mult": mult,
                    "value": base if mult == 1.0 else level_value(base, mult, kind),
                    "seed": seed,
                }
                row.update(metrics_of(state))
                rows.append(row)
    return rows


def fmt_std(vals: list[float], digits: int = 3) -> str:
    if len(vals) < 2:
        return f"{mean(vals):.{digits}f}"
    return f"{mean(vals):.{digits}f}±{pstdev(vals):.{digits}f}"


def analyze(rows: list[dict]) -> tuple[list[dict], list[str]]:
    """Flip analysis per parameter."""
    verdicts: list[dict] = []
    lines: list[str] = []
    by_param: dict[str, dict[str, dict[int, dict]]] = {}
    for r in rows:
        by_param.setdefault(r["param"], {}).setdefault(
            r["level"], {})[r["seed"]] = r
    for name, _flag, base, kind in PARAMS:
        levels = by_param[name]
        base_seed = {s: levels["1x"][s] for s in SEEDS}
        flips: list[str] = []
        for level in ("0.5x", "2x"):
            for s in SEEDS:
                r = levels[level][s]
                b = base_seed[s]
                if abs(r["f1"] - b["f1"]) > 0.15:
                    flips.append(
                        f"F1 {level} seed{s}: {b['f1']:.3f}->{r['f1']:.3f}")
                if abs(window_level(r["window_est"])
                       - window_level(b["window_est"])) > 2:
                    flips.append(
                        f"window {level} seed{s}: {b['window_est']:.0f}->"
                        f"{r['window_est']:.0f}")
                if not r["null_mean"] < r["attack_overlap_mass"]:
                    flips.append(f"null>=attack {level} seed{s}")
        verdicts.append({
            "param": name, "base": base,
            "n_flips": len(flips), "flips": flips,
            "safe_levels": [
                lv for lv in ("0.5x", "1x", "2x")
                if not any(f.startswith(f"{metric} {lv}") for metric in ("F1", "window", "null")
                           for f in flips)
            ],
        })
    return verdicts, lines


def write_outputs(rows: list[dict]) -> None:
    OUTDIR.mkdir(parents=True, exist_ok=True)
    fields = list(rows[0].keys())
    with (OUTDIR / "sensitivity.csv").open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows(rows)

    verdicts, _ = analyze(rows)
    by_param: dict[str, dict[str, list[dict]]] = {}
    for r in rows:
        by_param.setdefault(r["param"], {}).setdefault(r["level"], []).append(r)

    lines = [
        "# Attack-hyperparameter sensitivity scan (S1_n8k, seeds 7/8/9)",
        "",
        "Each parameter is scanned independently at {0.5x, 1x, 2x} of its",
        "default (all other parameters at defaults; 1x rows are the shared",
        "all-default baseline run of that seed). Window = largest tested gap",
        "with >=50% overlap recovery on the grid {20,45,90,200,(400)}.",
        "",
        "Flip criteria (per seed, all levels):",
        "- (a) |F1 - F1_1x| <= 0.15;",
        "- (b) window estimate moves by <= 2 grid steps;",
        "- (c) permutation-null mean < attack kept-overlap mass.",
        "",
    ]
    for name, flag, base, kind in PARAMS:
        levels = by_param[name]
        v = next(x for x in verdicts if x["param"] == name)
        lines += [
            f"## {name} (default {base:g}, flag `{flag}`)",
            "",
            "| level | value | F1 (mean±sd) | P | R | C med.rel.err | window (per seed) | null mean | attack mass |",
            "| --- | --- | --- | --- | --- | --- | --- | --- | --- |",
        ]
        for level in ("0.5x", "1x", "2x"):
            rs = levels[level]
            f1s = [r["f1"] for r in rs]
            precs = [r["precision"] for r in rs]
            recs = [r["recall"] for r in rs]
            cerrs = [r["c_median_rel_err"] for r in rs]
            nulls = [r["null_mean"] for r in rs]
            masss = [r["attack_overlap_mass"] for r in rs]
            wins = "/".join(f"{r['window_est']:.0f}" for r in rs)
            lines.append(
                f"| {level} | {rs[0]['value']:g} | {fmt_std(f1s)} | "
                f"{fmt_std(precs, 2)} | {fmt_std(recs, 2)} | "
                f"{fmt_std(cerrs)} | {wins} | {fmt_std(nulls, 1)} | "
                f"{fmt_std(masss, 0)} |")
        seed_sd = {
            s: pstdev([
                next(r for r in by_param[name][lv] if r["seed"] == s)["f1"]
                for lv in ("0.5x", "1x", "2x")
            ]) for s in SEEDS}
        verdict = "NOT FLIPPED" if v["n_flips"] == 0 else "FLIPPED"
        lines += [
            "",
            f"- verdict: **{verdict}** "
            + ("" if v["n_flips"] == 0 else f"({v['n_flips']} criterion violations)")
            + (f"; details: {'; '.join(v['flips'])}" if v["flips"] else ""),
            f"- seed-to-seed F1 sd within levels: "
            + ", ".join(f"s{s}={sd:.3f}" for s, sd in seed_sd.items()),
            "",
        ]
    any_flip = [v for v in verdicts if v["n_flips"] > 0]
    lines += ["## Overall", ""]
    if not any_flip:
        lines += [
            "No parameter flipped the conclusion at 0.5x/2x: detection F1,",
            "window estimate and null separation are all within the criteria",
            "above, for every seed. The design-level conclusion is robust to",
            "these 9 attack hyperparameters on the S1 workload family.",
        ]
    else:
        lines += ["Parameters with flips and their tested safe levels:"]
        for v in any_flip:
            lines.append(
                f"- **{v['param']}** (default {v['base']:g}): safe levels among "
                f"tested = {v['safe_levels']}; violations: {'; '.join(v['flips'])}")
    lines += [
        "",
        "Note: only three levels per parameter were tested (0.5x/1x/2x);",
        "'safe interval' claims are limited to the tested levels - values",
        "between them are untested interpolation.",
        "",
        f"Raw per-run metrics: `sensitivity.csv` ({len(rows)} runs).",
    ]
    (OUTDIR / "summary.md").write_text("\n".join(lines))
    print(f"[sens] wrote {OUTDIR / 'summary.md'} and sensitivity.csv")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jobs", type=int, default=3,
                        help="parallel seeds (each seed's runs are sequential"
                             " and share its trace cache)")
    parser.add_argument("--aggregate-only", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not args.aggregate_only:
        with ThreadPoolExecutor(max_workers=args.jobs) as pool:
            list(pool.map(scan_seed, SEEDS))
    rows = collect()
    write_outputs(rows)


if __name__ == "__main__":
    main()
