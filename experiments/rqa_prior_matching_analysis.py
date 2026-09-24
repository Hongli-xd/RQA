#!/usr/bin/env python3
"""Identifiability analysis for an auxiliary-distribution (prior-matching)
stage on top of the RQA leakage.

Question being answered
-----------------------
The passive attack (`range_query_attack.py`) recovers, per detected range
episode, (i) a visible-cardinality estimate m_hat (Stage C, median relative
error 3-12.5%, systematically UNDER the raw m because cached re-reads are
invisible) and (ii) a noisy binary overlap graph over episodes inside the
linkage window (Stage D/E: within-window recall ~1.0, precision ~0.4-0.5).

If the adversary additionally holds a PRIOR over the attribute histogram
(`this is census data`, or a public correlated dataset), can it map those
observables back onto concrete value ranges?  This script computes the
information-theoretic ceiling of that step - i.e. how many candidate
ranges survive volume matching - BEFORE any estimator is written, so the
downstream stage is designed against a measured bound rather than hope.

This is the standard volume-matching primitive used by the SOTA range
reconstruction attacks (Grubbs-Lacharite-Minaud-Paterson CCS'18 elementary
volumes; Kornaropoulos-Papamanthou-Tamassia S&P'20/'21 for the
response-hiding / non-uniform-query setting).  What is measured here is
their *feasibility precondition* on this leakage profile: the size of the
volume-consistent candidate set under the noise this attack actually has.

Anti-cheating discipline
------------------------
Nothing here reads a simulator trace, a truth JSON, or a realized database.
The adversary side sees only: a volume estimate, a binary overlap flag, and
an AUXILIARY histogram.  The `--aux-*` options deliberately make the
auxiliary histogram DIFFERENT from the data-generating one (resampling
noise, smoothing, domain shift), because an attacker holding the exact
histogram of the target database is the known-data assumption that
Blackstone-Kamara-Moataz (NDSS'20) showed to be the load-bearing - and
usually unrealistic - part of leakage-abuse results.

Stdlib only.  Outputs a markdown + CSV under results/prior_matching/.
"""

from __future__ import annotations

import argparse
import bisect
import csv
import json
import math
import random
from pathlib import Path
from statistics import median
from typing import Sequence

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "results" / "prior_matching"


# ---------------------------------------------------------------------------
# Attribute histograms (the "what the database looks like" prior).
# ---------------------------------------------------------------------------

def hist_uniform(d: int, n_records: int) -> list[float]:
    """Flat histogram == the CURRENT rqa workload (1 record per key, ranges
    are contiguous key intervals).  Volume then determines only the WIDTH of
    a range and carries zero positional information: the analytic worst case
    for prior matching, and the reason the present artifact cannot host this
    attack without a workload change."""
    return [n_records / d] * d


def hist_census_age(d: int, n_records: int) -> list[float]:
    """Illustrative single-year age structure of a developed-country
    population (flat-ish 0-55, post-war bulges, sharp decay past 70).

    ILLUSTRATIVE, not a citation of real census counts: the shape is what
    the analysis depends on.  Use --hist-csv to plug in real published
    marginals (e.g. an ACS/Eurostat single-year-of-age table)."""
    raw = []
    for v in range(d):
        age = v * 100.0 / d
        base = 1.0
        if age < 18:
            base = 0.98
        elif age < 35:
            base = 1.06
        elif age < 55:
            base = 1.00
        elif age < 65:
            base = 0.92
        elif age < 75:
            base = 0.68
        elif age < 85:
            base = 0.36
        else:
            base = 0.12
        # mild smooth ripple: cohort effects
        base *= 1.0 + 0.06 * math.sin(age / 7.0)
        raw.append(base)
    s = sum(raw)
    return [r * n_records / s for r in raw]


def hist_zipf(d: int, n_records: int, alpha: float = 1.1) -> list[float]:
    """Heavy-tailed attribute (city population, income bucket, page views)."""
    raw = [1.0 / ((i + 1) ** alpha) for i in range(d)]
    s = sum(raw)
    return [r * n_records / s for r in raw]


def hist_lognormal(d: int, n_records: int, sigma: float = 0.9) -> list[float]:
    """Income-like: unimodal, right-skewed, long thin tail."""
    raw = []
    for i in range(d):
        x = (i + 0.5) / d * 6.0 + 0.05
        raw.append(math.exp(-((math.log(x)) ** 2) / (2 * sigma * sigma)) / x)
    s = sum(raw)
    return [r * n_records / s for r in raw]


HISTS = {
    "uniform": hist_uniform,
    "census_age": hist_census_age,
    "zipf": hist_zipf,
    "lognormal": hist_lognormal,
}


# ---------------------------------------------------------------------------
# Auxiliary-histogram degradation: the attacker's copy is NEVER the truth.
# ---------------------------------------------------------------------------

def degrade(
    hist: Sequence[float],
    rng: random.Random,
    sample_frac: float,
    smooth: int,
    shift: float,
) -> list[float]:
    """Turn a data-generating histogram into a *correlated public dataset*.

    sample_frac : multinomial resampling at this fraction (finite-sample
                  noise of a public release / a different survey year)
    smooth      : boxcar width, i.e. the public release is bucketed coarser
                  than the attribute domain
    shift       : multiplicative drift with a smooth trend (population drift
                  between the auxiliary year and the target year)
    """
    out = list(hist)
    total = sum(out)
    if sample_frac > 0:
        k = max(1, int(total * sample_frac))
        # Poissonised multinomial: independent Poisson counts, same mean shape
        out = [max(0.0, rng.gauss(c * sample_frac, math.sqrt(max(c * sample_frac, 1e-9))))
               / sample_frac for c in out]
        del k
    if shift:
        n = len(out)
        out = [c * (1.0 + shift * math.sin(3.0 * math.pi * i / n)) for i, c in enumerate(out)]
    if smooth > 1:
        n = len(out)
        sm = []
        half = smooth // 2
        for i in range(n):
            lo, hi = max(0, i - half), min(n, i + half + 1)
            sm.append(sum(out[lo:hi]) / (hi - lo))
        out = sm
    s = sum(out)
    return [c * total / s for c in out]


# ---------------------------------------------------------------------------
# Volume matching: how many ranges are consistent with an observed volume?
# ---------------------------------------------------------------------------

def prefix_sums(hist: Sequence[float]) -> list[float]:
    p = [0.0]
    for c in hist:
        p.append(p[-1] + c)
    return p


def count_candidates(
    prefix: Sequence[float],
    v_lo: float,
    v_hi: float,
    w_min: int,
    w_max: int,
) -> int:
    """#{(l,u) : volume in [v_lo,v_hi], width in [w_min,w_max]}.

    prefix is non-decreasing, so for each left edge the admissible right
    edges form one contiguous index band -> two binary searches per left
    edge, O(d log d) per query."""
    d = len(prefix) - 1
    total = 0
    for a in range(d):
        blo = bisect.bisect_left(prefix, prefix[a] + v_lo, a + 1, d + 1)
        bhi = bisect.bisect_right(prefix, prefix[a] + v_hi, a + 1, d + 1)
        blo = max(blo, a + w_min)
        bhi = min(bhi, a + w_max + 1)
        if bhi > blo:
            total += bhi - blo
    return total


def candidate_list(
    prefix: Sequence[float],
    v_lo: float,
    v_hi: float,
    w_min: int,
    w_max: int,
    cap: int = 200000,
) -> list[tuple[int, int]]:
    d = len(prefix) - 1
    out: list[tuple[int, int]] = []
    for a in range(d):
        blo = bisect.bisect_left(prefix, prefix[a] + v_lo, a + 1, d + 1)
        bhi = bisect.bisect_right(prefix, prefix[a] + v_hi, a + 1, d + 1)
        blo = max(blo, a + w_min)
        bhi = min(bhi, a + w_max + 1)
        for b in range(blo, bhi):
            out.append((a, b))
            if len(out) >= cap:
                return out
    return out


CAND_CAP = 20000


def count_intersecting_pairs(
    c1: Sequence[tuple[int, int]], c2: Sequence[tuple[int, int]]
) -> int:
    """#{(r1,r2) in c1 x c2 : r1 and r2 intersect}, in O(|c1| log|c2|).

    Counted by complement: half-open [x,y) intervals miss iff y1 <= x2 or
    y2 <= x1, and those two events are disjoint, so two binary searches on
    the sorted left/right edges of c2 suffice."""
    xs2 = sorted(x for x, _ in c2)
    ys2 = sorted(y for _, y in c2)
    n2 = len(c2)
    disjoint = 0
    for (x1, y1) in c1:
        disjoint += n2 - bisect.bisect_left(xs2, y1)   # x2 >= y1
        disjoint += bisect.bisect_right(ys2, x1)       # y2 <= x1
    return len(c1) * n2 - disjoint


def chain_consistent_count(
    cand_sets: Sequence[Sequence[tuple[int, int]]]
) -> float:
    """#assignments of one candidate range per episode that satisfy the
    binary "consecutive episodes overlap" constraints, exactly, via a chain
    DP.  The re-query structure this attack recovers IS a path (a base
    episode and its re-queries), so the constraint graph factorises and the
    count needs no search.

    Only BINARY overlap is used, never an overlap magnitude: Stage E's
    magnitude estimates correlate at Pearson 0.34-0.52 with truth, which is
    too weak to carry an equality constraint.
    """
    if not cand_sets:
        return 0.0
    f = [1.0] * len(cand_sets[0])
    prev = list(cand_sets[0])
    for cur in cand_sets[1:]:
        # weights of prev sorted by right edge and by left edge, with prefix sums
        by_y = sorted(range(len(prev)), key=lambda i: prev[i][1])
        by_x = sorted(range(len(prev)), key=lambda i: prev[i][0])
        ys = [prev[i][1] for i in by_y]
        xs = [prev[i][0] for i in by_x]
        pre_y = [0.0]
        for i in by_y:
            pre_y.append(pre_y[-1] + f[i])
        pre_x = [0.0]
        for i in by_x:
            pre_x.append(pre_x[-1] + f[i])
        total = pre_y[-1]
        nf = []
        for (x, y) in cur:
            # disjoint iff y' <= x (prev entirely left) or x' >= y (entirely right)
            left = pre_y[bisect.bisect_right(ys, x)]
            right = total - pre_x[bisect.bisect_left(xs, y)]
            nf.append(max(0.0, total - left - right))
        f, prev = nf, list(cur)
        if sum(f) == 0.0:
            return 0.0
    return sum(f)


# ---------------------------------------------------------------------------
# Enumeration-free chain DP.
#
# The enumerative DP above costs O(|C| log|C|) per episode, and the candidate
# set grows as |C| ~ 2*eps*w*d (validated against the sweep: d=1000/eps=0.03
# predicts 3,600 vs 3,678 measured).  With the attribute domain equal to the
# key space, the Waffle paper's medium configuration (1:5 scaled, d=200k,
# w~1150, eps=0.125) gives |C| ~ 5.8e7 per episode, i.e. ~4 GiB just to hold
# the pairs - and ~96 GiB unscaled at N=1e6.  Enumeration is therefore not an
# option at deployment scale.
#
# It is also not necessary.  Two structural facts collapse the cost to O(d):
#
#   (1) BANDS.  Prefix sums are non-decreasing, so for each left edge x the
#       volume-consistent right edges form ONE contiguous band [Lo(x),Hi(x)),
#       and Lo,Hi are themselves non-decreasing.  C is thus represented by 2d
#       integers instead of |C| pairs, and the transpose (for each right edge
#       y, the left edges whose band contains y) is contiguous too.
#
#   (2) SEPARABILITY.  Two ranges are disjoint iff y' <= x or x' >= y, so
#           f_i(x,y) = T_{i-1} - A_{i-1}(x) - B_{i-1}(y)
#       where A is a function of x alone and B of y alone.  The DP state is
#       therefore never a function over pairs: it is a constant plus two
#       1-D arrays, and each step is prefix/suffix sums over those arrays.
#
# Cost per episode: O(d log d) to build the bands (bisect; the monotonicity
# in (1) admits an O(d) two-pointer) and O(d) for the DP step, with O(d)
# memory and no dependence on |C|.  `--self-check` asserts it reproduces the
# enumerative count exactly on small domains.
# ---------------------------------------------------------------------------


def candidate_bands(
    prefix: Sequence[float],
    v_lo: float,
    v_hi: float,
    w_min: int,
    w_max: int,
) -> tuple[list[int], list[int]]:
    """Per left edge x, the contiguous band of admissible right edges
    [Lo(x), Hi(x)) in prefix-index space (y = x+width, so y in [x+1, d]).

    Both Lo and Hi are non-decreasing because `prefix` is."""
    d = len(prefix) - 1
    lo_arr, hi_arr = [0] * d, [0] * d
    for x in range(d):
        base = prefix[x]
        lo = bisect.bisect_left(prefix, base + v_lo, x + 1, d + 1)
        hi = bisect.bisect_right(prefix, base + v_hi, x + 1, d + 1)
        lo = max(lo, x + w_min)
        hi = min(hi, x + w_max + 1, d + 1)
        if hi < lo:
            hi = lo
        lo_arr[x], hi_arr[x] = lo, hi
    return lo_arr, hi_arr


def band_mass(lo_arr: Sequence[int], hi_arr: Sequence[int]) -> int:
    """|C| without materialising it."""
    return sum(h - l for l, h in zip(lo_arr, hi_arr))


def chain_consistent_count_banded(
    prefix: Sequence[float],
    windows: Sequence[tuple[float, float]],
    w_min: int,
    w_max: int,
) -> float:
    """Same quantity as chain_consistent_count, in O(k*d log d) time and O(d)
    memory: the number of assignments of one volume-consistent range per
    episode such that consecutive episodes' ranges intersect.

    `windows` is the per-episode volume tolerance interval (v_lo, v_hi).
    """
    d = len(prefix) - 1
    const, a_arr, b_arr = 1.0, [0.0] * d, [0.0] * (d + 1)
    total = 0.0
    for (v_lo, v_hi) in windows:
        lo_arr, hi_arr = candidate_bands(prefix, v_lo, v_hi, w_min, w_max)
        # prefix sums of the two 1-D state arrays
        pre_a = [0.0] * (d + 1)
        for i in range(d):
            pre_a[i + 1] = pre_a[i] + a_arr[i]
        pre_b = [0.0] * (d + 2)
        for i in range(d + 1):
            pre_b[i + 1] = pre_b[i] + b_arr[i]
        # t(x): mass of this episode's candidates sharing left edge x
        t_arr = [0.0] * d
        for x in range(d):
            n = hi_arr[x] - lo_arr[x]
            if n:
                t_arr[x] = (const - a_arr[x]) * n - (pre_b[hi_arr[x]] - pre_b[lo_arr[x]])
        total = sum(t_arr)
        if total <= 0.0:
            return 0.0
        # u(y): same mass grouped by right edge, via the transposed bands.
        # {x : y in band(x)} = [bisect_right(hi_arr, y), bisect_right(lo_arr, y))
        u_arr = [0.0] * (d + 1)
        for y in range(1, d + 1):
            x_lo = bisect.bisect_right(hi_arr, y)
            x_hi = bisect.bisect_right(lo_arr, y)
            m = x_hi - x_lo
            if m > 0:
                u_arr[y] = (const - b_arr[y]) * m - (pre_a[x_hi] - pre_a[x_lo])
        # next state: f'(x,y) = total - A(x) - B(y)
        a_next = [0.0] * d            # A(x) = sum of mass with y <= x
        run = 0.0
        for x in range(d):
            run += u_arr[x]
            a_next[x] = run
        b_next = [0.0] * (d + 1)      # B(y) = sum_{x >= y} t(x)
        suf = 0.0
        for y in range(d, -1, -1):
            if y < d:
                suf += t_arr[y]      # accumulate t(y) BEFORE storing: x >= y, not x > y
            b_next[y] = suf
        const, a_arr, b_arr = total, a_next, b_next
    return total


def run_chain_case(
    hist_name: str,
    d: int,
    n_records: int,
    eps: float,
    k_max: int,
    n_chains: int,
    w_frac: tuple[float, float],
    rng: random.Random,
    aux_sample_frac: float = 0.0,
    aux_smooth: int = 1,
    aux_shift: float = 0.0,
) -> list[dict[str, object]]:
    """Residual positional entropy of a chain of k linked episodes.

    A chain is what Stage D actually delivers inside the linkage window: a
    base range plus re-queries that share a large prefix of it.  Each extra
    linked episode adds one volume observation AND one overlap constraint.
    """
    true_hist = HISTS[hist_name](d, n_records)
    aux_hist = degrade(true_hist, rng, aux_sample_frac, aux_smooth, aux_shift)
    p_true, p_aux = prefix_sums(true_hist), prefix_sums(aux_hist)
    w_min = max(1, int(w_frac[0] * d))
    w_max = max(w_min + 1, int(w_frac[1] * d))

    out: list[dict[str, object]] = []
    n_capped = 0
    per_k: dict[int, list[float]] = {k: [] for k in range(1, k_max + 1)}
    per_k_indep: dict[int, list[float]] = {k: [] for k in range(1, k_max + 1)}
    truth_in: dict[int, list[int]] = {k: [] for k in range(1, k_max + 1)}

    for _ in range(n_chains):
        # build a true chain: each episode re-queries 30-60% of the previous
        w = rng.randint(w_min, w_max)
        a = rng.randrange(0, max(1, d - w))
        ranges = [(a, a + w)]
        for _ in range(k_max - 1):
            pa, pb = ranges[-1]
            w2 = rng.randint(w_min, w_max)
            ov = max(1, int(rng.uniform(0.3, 0.6) * min(pb - pa, w2)))
            na = max(0, min(d - w2 - 1, pb - ov))
            ranges.append((na, na + w2))
        cands = []
        capped = False
        for (x, y) in ranges:
            v = p_true[y] - p_true[x]
            v_obs = v * (1.0 + rng.gauss(0.0, eps / 2.0))
            lo, hi = v_obs * (1 - eps), v_obs * (1 + eps)
            exact = count_candidates(p_aux, lo, hi, w_min, w_max)
            if exact > CAND_CAP:
                capped = True
                break
            cands.append(candidate_list(p_aux, lo, hi, w_min, w_max, cap=CAND_CAP))
        if capped:
            # Enumerating the candidate set is infeasible at this domain size,
            # and a TRUNCATED list would silently bias the DP (it keeps only
            # the smallest left edges), so the cell is reported as n/a rather
            # than as a number.
            n_capped += 1
            continue
        for k in range(1, k_max + 1):
            cnt = chain_consistent_count(cands[:k])
            per_k[k].append(math.log2(max(1.0, cnt)))
            per_k_indep[k].append(sum(math.log2(max(1, len(c))) for c in cands[:k]))
            ok = all((p_aux[y] - p_aux[x]) >= 0 and (x, y) in set(cands[i])
                     for i, (x, y) in enumerate(ranges[:k]))
            truth_in[k].append(1 if ok else 0)

    for k in range(1, k_max + 1):
        if not per_k[k]:
            out.append({
                "hist": hist_name, "d": d, "eps": eps, "k": k,
                "joint_bits": None, "independent_bits": None,
                "bits_saved_by_links": None, "bits_per_episode": None,
                "truth_survives": None, "chains_scored": 0,
                "chains_skipped_cap": n_capped,
            })
            continue
        out.append({
            "hist": hist_name, "d": d, "eps": eps, "k": k,
            "joint_bits": round(median(per_k[k]), 2),
            "independent_bits": round(median(per_k_indep[k]), 2),
            "bits_saved_by_links": round(median(per_k_indep[k]) - median(per_k[k]), 2),
            "bits_per_episode": round(median(per_k[k]) / k, 2),
            "truth_survives": round(sum(truth_in[k]) / max(1, len(truth_in[k])), 3),
            "chains_scored": len(per_k[k]),
            "chains_skipped_cap": n_capped,
        })
    return out


# ---------------------------------------------------------------------------
# Experiment
# ---------------------------------------------------------------------------

def run_case(
    name: str,
    hist_name: str,
    d: int,
    n_records: int,
    eps: float,
    bias: float,
    modelled_bias: float,
    n_queries: int,
    w_frac: tuple[float, float],
    width_prior: bool,
    aux_sample_frac: float,
    aux_smooth: int,
    aux_shift: float,
    rng: random.Random,
    pair_probe: int = 40,
) -> dict[str, object]:
    """One (histogram, domain, noise) cell.

    The TRUE histogram generates the observed volumes; the AUXILIARY
    histogram (a degraded copy) is all the attacker matches against.
    """
    true_hist = HISTS[hist_name](d, n_records)
    aux_hist = degrade(true_hist, rng, aux_sample_frac, aux_smooth, aux_shift)
    p_true = prefix_sums(true_hist)
    p_aux = prefix_sums(aux_hist)

    w_min_q = max(1, int(w_frac[0] * d))
    w_max_q = max(w_min_q + 1, int(w_frac[1] * d))
    if width_prior:
        w_min_c, w_max_c = w_min_q, w_max_q
    else:
        w_min_c, w_max_c = 1, d

    amb: list[int] = []
    pair_over_cap = 0
    covered = 0
    unique = 0
    pair_amb: list[float] = []
    queries: list[tuple[int, int]] = []

    for _ in range(n_queries):
        w = rng.randint(w_min_q, w_max_q)
        a = rng.randrange(0, d - w)
        b = a + w
        queries.append((a, b))
        v_true = p_true[b] - p_true[a]
        # what Stage C actually hands over: biased down (invisible cached
        # re-reads) and noisy
        v_obs = v_true * (1.0 - bias) * (1.0 + rng.gauss(0.0, eps / 2.0))
        # attacker's inversion of the (partially) modelled bias
        v_hat = v_obs / max(1e-9, (1.0 - modelled_bias))
        lo, hi = v_hat * (1 - eps), v_hat * (1 + eps)
        n_c = count_candidates(p_aux, lo, hi, w_min_c, w_max_c)
        amb.append(n_c)
        if n_c == 1:
            unique += 1
        v_aux_true = p_aux[b] - p_aux[a]
        if lo <= v_aux_true <= hi:
            covered += 1

    # Pair constraint: two episodes the overlap graph links (binary only -
    # Stage E magnitudes are too weak to use, Pearson 0.34-0.52).  How much
    # does "these two ranges intersect" shrink the joint hypothesis space?
    probes = min(pair_probe, n_queries // 2)
    for i in range(probes):
        (a1, b1) = queries[2 * i]
        w2 = rng.randint(w_min_q, w_max_q)
        # a genuinely overlapping partner, as the workload's re-queries are
        ov = max(1, int(0.4 * min(b1 - a1, w2)))
        a2 = max(0, min(d - w2 - 1, b1 - ov))
        b2 = a2 + w2
        v1 = (p_true[b1] - p_true[a1]) * (1 - bias) / max(1e-9, 1 - modelled_bias)
        v2 = (p_true[b2] - p_true[a2]) * (1 - bias) / max(1e-9, 1 - modelled_bias)
        lo1, hi1 = v1 * (1 - eps), v1 * (1 + eps)
        lo2, hi2 = v2 * (1 - eps), v2 * (1 + eps)
        if (count_candidates(p_aux, lo1, hi1, w_min_c, w_max_c) > CAND_CAP
                or count_candidates(p_aux, lo2, hi2, w_min_c, w_max_c) > CAND_CAP):
            # Truncating the candidate lists would make the intersection count
            # meaningless (the cap keeps only the smallest left edges), so the
            # pair metric is reported as n/a at this domain size.
            pair_over_cap += 1
            continue
        c1 = candidate_list(p_aux, lo1, hi1, w_min_c, w_max_c, cap=CAND_CAP)
        c2 = candidate_list(p_aux, lo2, hi2, w_min_c, w_max_c, cap=CAND_CAP)
        if not c1 or not c2:
            continue
        pair_amb.append(math.log2(max(1, count_intersecting_pairs(c1, c2))))

    med = median(amb) if amb else 0
    return {
        "case": name,
        "hist": hist_name,
        "d": d,
        "eps": eps,
        "bias": bias,
        "modelled_bias": modelled_bias,
        "width_prior": int(width_prior),
        "aux_sample_frac": aux_sample_frac,
        "aux_smooth": aux_smooth,
        "aux_shift": aux_shift,
        "n_ranges_total": d * (d + 1) // 2,
        "median_candidates": med,
        "median_bits": round(math.log2(max(1, med)), 2),
        "p25_candidates": sorted(amb)[len(amb) // 4] if amb else 0,
        "p75_candidates": sorted(amb)[3 * len(amb) // 4] if amb else 0,
        "frac_unique": round(unique / max(1, len(amb)), 4),
        "coverage": round(covered / max(1, len(amb)), 4),
        "pair_median_bits": round(median(pair_amb), 2) if pair_amb else None,
        "pair_probes_over_cap": pair_over_cap,
        "single_median_bits_x2": round(2 * math.log2(max(1, med)), 2),
    }


def self_check(rng: random.Random, verbose: bool = True) -> bool:
    """Prove the banded O(d) DP returns exactly what the enumerative DP does.

    An optimisation that is not shown equivalent is not evidence, so this runs
    both implementations on the same candidate sets over several histograms,
    domains and tolerances and requires agreement to 1e-9 relative."""
    ok = True
    for hist_name in ("uniform", "census_age", "zipf", "lognormal"):
        for d in (40, 120, 400):
            hist = HISTS[hist_name](d, 100_000)
            prefix = prefix_sums(hist)
            w_min, w_max = max(1, d // 50), max(2, d // 10)
            for eps in (0.02, 0.08, 0.2):
                for _trial in range(3):
                    k = rng.randint(1, 5)
                    ranges = []
                    x = rng.randrange(0, max(1, d - w_max - 1))
                    for _ in range(k):
                        w = rng.randint(w_min, w_max)
                        x = max(0, min(d - w - 1, x + rng.randint(-w, w)))
                        ranges.append((x, x + w))
                    windows, cand = [], []
                    for (a, b) in ranges:
                        v = prefix[b] - prefix[a]
                        lo, hi = v * (1 - eps), v * (1 + eps)
                        windows.append((lo, hi))
                        cand.append(candidate_list(prefix, lo, hi, w_min, w_max, cap=CAND_CAP))
                    enum = chain_consistent_count(cand)
                    band = chain_consistent_count_banded(prefix, windows, w_min, w_max)
                    rel = abs(enum - band) / max(1.0, abs(enum))
                    if rel > 1e-9:
                        ok = False
                        print(f"  MISMATCH {hist_name} d={d} eps={eps} k={k}: "
                              f"enumerative={enum!r} banded={band!r} rel={rel:.3g}")
                    # the band representation must also reproduce |C| exactly
                    for (lo, hi), c in zip(windows, cand):
                        lo_arr, hi_arr = candidate_bands(prefix, lo, hi, w_min, w_max)
                        if band_mass(lo_arr, hi_arr) != len(c):
                            ok = False
                            print(f"  |C| MISMATCH {hist_name} d={d}: "
                                  f"banded={band_mass(lo_arr, hi_arr)} enumerated={len(c)}")
    if verbose:
        print("self-check: banded DP == enumerative DP" if ok else "self-check FAILED")
    return ok


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--domains", type=int, nargs="+", default=[100, 1000, 10000],
                    help="attribute domain sizes to sweep")
    ap.add_argument("--hists", nargs="+", default=["uniform", "census_age", "zipf", "lognormal"])
    ap.add_argument("--eps", type=float, nargs="+", default=[0.03, 0.125],
                    help="relative volume tolerance; defaults are the Stage-C "
                         "median relative errors measured in results/")
    ap.add_argument("--n-records", type=int, default=1_000_000)
    ap.add_argument("--queries", type=int, default=200)
    ap.add_argument("--w-frac", type=float, nargs=2, default=[0.02, 0.10],
                    help="range width as a fraction of the domain")
    ap.add_argument("--chain-k", type=int, default=5,
                    help="max number of linked episodes in the chain sweep")
    ap.add_argument("--chains", type=int, default=40)
    ap.add_argument("--self-check", action="store_true",
                    help="verify the banded DP against the enumerative one and exit")
    ap.add_argument("--bench", type=int, nargs="+", default=None,
                    help="time the banded DP at these domain sizes and exit")
    ap.add_argument("--seed", type=int, default=7)
    ap.add_argument("--outdir", type=Path, default=RESULTS)
    args = ap.parse_args()

    rng = random.Random(args.seed)
    if args.self_check:
        raise SystemExit(0 if self_check(rng) else 1)
    if args.bench:
        import time
        for d in args.bench:
            hist = HISTS["census_age"](d, 1_000_000)
            prefix = prefix_sums(hist)
            w = max(2, int(0.05 * d))
            lo_v = (prefix[w] - prefix[0])
            windows = [(lo_v * 0.875, lo_v * 1.125)] * 6
            t0 = time.time()
            cnt = chain_consistent_count_banded(prefix, windows, max(1, w // 2), w * 2)
            dt = time.time() - t0
            lo_arr, hi_arr = candidate_bands(prefix, windows[0][0], windows[0][1],
                                             max(1, w // 2), w * 2)
            print(f"d={d:>9,}  |C|={band_mass(lo_arr, hi_arr):>14,}  "
                  f"k=6 chain: {dt:7.2f}s  log2(count)={math.log2(max(1.0, cnt)):.1f}")
        raise SystemExit(0)
    rows: list[dict[str, object]] = []

    # A: ceiling - exact auxiliary histogram, no cache bias, width prior known
    for h in args.hists:
        for d in args.domains:
            for e in args.eps:
                rows.append(run_case(f"A_ceiling", h, d, args.n_records, e,
                                     bias=0.0, modelled_bias=0.0,
                                     n_queries=args.queries,
                                     w_frac=tuple(args.w_frac), width_prior=True,
                                     aux_sample_frac=0.0, aux_smooth=1, aux_shift=0.0,
                                     rng=rng))
    # B: no width prior (attacker does not know the query granularity)
    for h in args.hists:
        for d in args.domains:
            rows.append(run_case("B_no_width_prior", h, d, args.n_records, max(args.eps),
                                 bias=0.0, modelled_bias=0.0, n_queries=args.queries,
                                 w_frac=tuple(args.w_frac), width_prior=False,
                                 aux_sample_frac=0.0, aux_smooth=1, aux_shift=0.0, rng=rng))
    # C: realistic auxiliary (public correlated dataset, not the target DB)
    for h in args.hists:
        for d in args.domains:
            rows.append(run_case("C_public_aux", h, d, args.n_records, max(args.eps),
                                 bias=0.0, modelled_bias=0.0, n_queries=args.queries,
                                 w_frac=tuple(args.w_frac), width_prior=True,
                                 aux_sample_frac=0.02, aux_smooth=max(2, args.domains[0] // 50),
                                 aux_shift=0.10, rng=rng))
    # D: Stage-C cache bias left unmodelled (the undercount measured in results/)
    for h in args.hists:
        for d in args.domains:
            rows.append(run_case("D_unmodelled_bias", h, d, args.n_records, max(args.eps),
                                 bias=0.10, modelled_bias=0.0, n_queries=args.queries,
                                 w_frac=tuple(args.w_frac), width_prior=True,
                                 aux_sample_frac=0.0, aux_smooth=1, aux_shift=0.0, rng=rng))
    # E: same bias, correctly modelled by the attacker
    for h in args.hists:
        for d in args.domains:
            rows.append(run_case("E_modelled_bias", h, d, args.n_records, max(args.eps),
                                 bias=0.10, modelled_bias=0.10, n_queries=args.queries,
                                 w_frac=tuple(args.w_frac), width_prior=True,
                                 aux_sample_frac=0.0, aux_smooth=1, aux_shift=0.0, rng=rng))

    chain_rows: list[dict[str, object]] = []
    for h in args.hists:
        for d in args.domains:
            chain_rows += run_chain_case(h, d, args.n_records, max(args.eps),
                                         k_max=args.chain_k, n_chains=args.chains,
                                         w_frac=tuple(args.w_frac), rng=rng)

    args.outdir.mkdir(parents=True, exist_ok=True)
    with (args.outdir / "chain_entropy.csv").open("w", newline="") as fh:
        cw = csv.DictWriter(fh, fieldnames=list(chain_rows[0].keys()))
        cw.writeheader()
        cw.writerows(chain_rows)
    csv_path = args.outdir / "identifiability.csv"
    with csv_path.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)

    lines = ["# Prior-matching identifiability ceiling",
             "",
             f"queries/cell={args.queries}, widths={args.w_frac[0]:.0%}-{args.w_frac[1]:.0%} of domain, "
             f"N={args.n_records:,}, seed={args.seed}",
             "",
             "`median_bits` = log2 of the number of value ranges consistent with one",
             "observed volume: the positional entropy a single Stage-C cardinality",
             "leaves. 0 bits = that query's range is pinned by volume alone.",
             "`coverage` = fraction of queries whose true range still matches under the",
             "auxiliary histogram (a coverage collapse means the matcher rejects the",
             "truth, i.e. it returns a CONFIDENT WRONG answer).",
             ""]
    for case in ["A_ceiling", "B_no_width_prior", "C_public_aux", "D_unmodelled_bias", "E_modelled_bias"]:
        sel = [r for r in rows if r["case"] == case]
        if not sel:
            continue
        lines += [f"## {case}", "",
                  "| hist | d | eps | #ranges | median cand | median bits | frac unique | coverage | pair bits |",
                  "| --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
        for r in sel:
            lines.append(
                f"| {r['hist']} | {r['d']} | {r['eps']} | {r['n_ranges_total']:,} | "
                f"{r['median_candidates']:,} | {r['median_bits']} | {r['frac_unique']} | "
                f"{r['coverage']} | "
                f"{'n/a (over cap)' if r['pair_median_bits'] is None else r['pair_median_bits']} |")
        lines.append("")
    # The headline metric: what the SKEW of the prior buys over the uniform
    # control at the same domain and tolerance.  `uniform` is not a histogram
    # anyone would attack - it is the null model in which volume carries width
    # and nothing else, so every bit below it is a bit the prior contributed.
    lines += ["## G_prior_gain: bits the prior's skew actually buys",
              "",
              "`gain` = median_bits(uniform control) - median_bits(this prior) at the",
              "same domain size and tolerance: the positional information the prior",
              "contributes beyond knowing the range's width.  A gain near 0 means the",
              "prior is worthless at that measurement noise.",
              "",
              "| hist | d | eps | bits (uniform control) | bits (this prior) | gain |",
              "| --- | --- | --- | --- | --- | --- |"]
    base = {(r["d"], r["eps"]): r["median_bits"]
            for r in rows if r["case"] == "A_ceiling" and r["hist"] == "uniform"}
    for r in rows:
        if r["case"] != "A_ceiling" or r["hist"] == "uniform":
            continue
        b = base.get((r["d"], r["eps"]))
        if b is None:
            continue
        lines.append(f"| {r['hist']} | {r['d']} | {r['eps']} | {b} | "
                     f"{r['median_bits']} | {round(b - r['median_bits'], 2)} |")
    lines.append("")
    lines += ["## F_chain: linked episodes (Stage-D window) shrink the space",
              "",
              "`joint_bits` = log2 #assignments of value ranges to the k linked",
              "episodes consistent with all observed volumes AND the binary overlap",
              "constraints; `independent_bits` is the same without the links.",
              "`truth_survives` = fraction of chains where the true assignment is",
              "still in every candidate set (hard-constraint soundness).",
              "",
              "Rows with `n/a` are domains where the volume-consistent candidate set",
              "is too large to enumerate exactly (> CAND_CAP); a truncated set would",
              "bias the DP, so no number is reported for them.",
              "",
              "| hist | d | k | joint bits | indep bits | saved | bits/episode | truth survives | chains |",
              "| --- | --- | --- | --- | --- | --- | --- | --- | --- |"]
    for r in chain_rows:
        if r["joint_bits"] is None:
            lines.append(
                f"| {r['hist']} | {r['d']} | {r['k']} | n/a | n/a | n/a | n/a | n/a | "
                f"0 scored / {r['chains_skipped_cap']} over cap |")
            continue
        lines.append(
            f"| {r['hist']} | {r['d']} | {r['k']} | {r['joint_bits']} | "
            f"{r['independent_bits']} | {r['bits_saved_by_links']} | "
            f"{r['bits_per_episode']} | {r['truth_survives']} | {r['chains_scored']} |")
    lines.append("")
    (args.outdir / "summary.md").write_text("\n".join(lines))
    print("\n".join(lines))
    print(f"\nwrote {csv_path} and {args.outdir/'summary.md'}")


if __name__ == "__main__":
    main()
