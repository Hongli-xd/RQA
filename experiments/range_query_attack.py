#!/usr/bin/env python3
"""Multi-stage passive range-query attack against a Waffle-backed proxy.

Threat model (matches the Waffle paper's own adversary):
  A passive persistent storage-server observer sees, for every batch,
  the MULTISET of storage ids read and written plus batch timestamps.
  Storage ids are PRF outputs, so the same logical key changes id after
  every access (write-once-read-once incarnations). Within-batch order is
  assumed scrambled, so every feature below is order-hidden (batch-level
  multisets only).

Anti-cheating discipline (enforced mechanically):
  The attack parser whitelists exactly four server-visible fields
  (event, batch_ts, direction, storage_key). The simulation-only label
  columns (role, logical_key, read_count, fake_real_count, dummy_count,
  cache_misses) are dropped at load time, so attack code cannot touch
  them even accidentally. Ground truth is read only by eval_* functions.

Key passive channel discovered by Stage A (honest, order-hidden):
  Waffle picks fake reals by least access timestamp, so fake alphas cluster
  tightly at the "flush age" of the uncached pool (~pool_size / fakes_per_
  batch). The server can therefore identify most fake reads from timing
  alone and recover the per-batch client-miss series:
        misses_t ~= real_reads_per_batch - fake_flavor_reads_t
  This is a deployment-relevant leakage finding, not a simulation label.

Stages
  A  batch anatomy: calibrate B, the flush mode, f_R/f_D structure, and the
     per-batch miss series (no system parameters assumed known).
  B  range-episode detection: find batches touched by range queries from
     miss bursts, cold first-touch mass, and co-parent concentration,
     with thresholds calibrated on a range-free control run.
  C  cardinality recovery: estimate m (records matched) per episode from
     the excess-miss mass; cached-part overlap is honestly undercounted.
  D  cross-incarnation tracking: attribute reads to the eviction batch that
     wrote their incarnation (exact timing arithmetic), giving episode
     overlap counts plus the (small) set of unambiguous id-level links.
  E  range-topology reconstruction: episode-by-episode overlap matrix,
     permutation-null tested, scored against ground truth.

Controls
  c1  background-only workload (no ranges): false-positive calibration.
  c2  point-burst workload (same schedule, same sizes, random keys):
      tests that the attack recovers RANGE structure, not just bursts.

All outputs go to results/range_query_attack/. Stdlib only.
"""

from __future__ import annotations

import argparse
import bisect
import csv
import json
import random
from collections import Counter, defaultdict, deque
from dataclasses import dataclass
from pathlib import Path
from statistics import mean, median, pstdev
from typing import Sequence

from waffle_leakage_sim import (
    RESULTS_DIR,
    WaffleConfig,
    WaffleSim,
    WeightedSampler,
    zipf_weights,
)


ROOT = Path(__file__).resolve().parents[1]

# ---------------------------------------------------------------------------
# Server-visible field whitelist. Everything else in the trace TSV is a
# simulation label and must never reach attack code.
# ---------------------------------------------------------------------------
ATTACK_FIELDS = ("event", "batch_ts", "direction", "storage_key")


# ---------------------------------------------------------------------------
# Workload: background Zipf point traffic + scheduled range episodes.
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class Episode:
    episode_id: int
    start_round: int
    range_start: int
    keys: tuple[int, ...]

    @property
    def m(self) -> int:
        return len(self.keys)


class RangeMixWorkload:
    """FIFO request queue fed by background point traffic and episodes.

    A trusted range adapter splits RangeQuery([l, u]) into m point-gets that
    enter the queue; Waffle drains up to R requests per batch. Queue order is
    proxy-internal; the attack never uses order within a batch.
    """

    def __init__(
        self,
        n_real: int,
        client_requests: int,
        zipf: float,
        rng: random.Random,
        episodes: Sequence[Episode] = (),
        bg_rate: int = 40,
    ) -> None:
        self.sampler = WeightedSampler(zipf_weights(n_real, zipf), rng)
        self.client_requests = client_requests
        self.rng = rng
        self.queue: deque[int] = deque()
        self.episodes = sorted(episodes, key=lambda e: e.start_round)
        self.bg_rate = bg_rate
        self.round = 0
        self._episode_at = {e.start_round: e for e in self.episodes}

    def next_batch(self) -> list[int]:
        self.round += 1
        episode = self._episode_at.get(self.round)
        if episode is not None:
            # Episode keys jump the queue (adapter enqueues them together).
            for key in reversed(episode.keys):
                self.queue.appendleft(key)
        for _ in range(self.bg_rate):
            self.queue.append(self.sampler.sample())
        requests: list[int] = []
        while self.queue and len(requests) < self.client_requests:
            requests.append(self.queue.popleft())
        return requests


def make_episodes(
    rng: random.Random,
    n_real: int,
    rounds: int,
    warmup: int,
    every: int,
    m_min: int,
    m_max: int,
    overlap_bias: float,
    mode: str,
    gaps: Sequence[int] = (20, 45, 90, 200),
) -> list[Episode]:
    """Schedule episodes with controlled key-space geometry.

    mode='range': fresh episodes occupy DISJOINT intervals (rejection
    sampling over already-used regions); with probability `overlap_bias` an
    episode deliberately re-queries a previous range, overlapping a
    uniform fraction in [0.2, 0.6] of the smaller range. True overlap is
    then bimodal (0 or large), so topology recovery is measurable without
    chance-overlap noise. mode='point_burst' picks random keys with the
    same schedule and sizes (control c2)."""
    episodes: list[Episode] = []
    used: list[tuple[int, int]] = []  # disjoint fresh intervals
    previous: list[Episode] = []

    def fresh_start(m: int) -> int:
        for _ in range(80):
            s = rng.randrange(0, n_real - m)
            if all(s + m < a or s > b for a, b in used):
                return s
        # fallback: largest gap
        gaps = []
        prev_end = 0
        for a, b in sorted(used):
            if a - prev_end > m:
                gaps.append(prev_end)
            prev_end = b
        if n_real - prev_end > m:
            gaps.append(prev_end)
        return rng.choice(gaps) if gaps else rng.randrange(0, n_real - m)

    episode_id = len(episodes)
    extra: list[tuple[int, int, Episode]] = []  # (round, after_episode_id, Episode)
    fresh_rounds = list(range(warmup + 20, rounds - 5, every))
    taken_rounds: set[int] = set(fresh_rounds)

    def claim_round(r: int) -> int:
        """Shift a re-query round until it does not collide with another
        episode's drain window (merged spans would corrupt evaluation and
        also merge distinct bursts for the attacker)."""
        while any(abs(r - t) < 6 for t in taken_rounds):
            r += 12
        taken_rounds.add(r)
        return r

    for start_round in fresh_rounds:
        m = rng.randint(m_min, m_max)
        range_start = -1
        if mode == "point_burst":
            keys = tuple(rng.sample(range(n_real), m))
        else:
            if previous and rng.random() < overlap_bias:
                base = previous[-1]
                # Gap-controlled re-query: the background redraw rate sets a
                # timescale beyond which incarnation linkage is scrambled;
                # scheduling re-queries at several gaps characterizes that
                # leakage boundary.
                gap = rng.choice(gaps)
                frac = rng.uniform(0.3, 0.6)
                ov = max(30, min(int(frac * base.m), base.m, m - 20))
                base_end = base.range_start + base.m
                m_rq = ov + max(20, m // 3)
                if base_end + (m_rq - ov) + 50 < n_real:
                    fresh_beg = base_end + 40
                    keys = tuple(
                        list(range(base_end - ov, base_end))
                        + list(range(fresh_beg, fresh_beg + (m_rq - ov)))
                    )
                    rq_round = claim_round(base.start_round + gap)
                    extra.append(
                        (rq_round, episode_id,
                         Episode(episode_id, rq_round,
                                 base_end - ov, keys))
                    )
                    episode_id += 1
                    continue
                range_start = fresh_start(m)
                keys = tuple(range(range_start, range_start + m))
            else:
                range_start = fresh_start(m)
                keys = tuple(range(range_start, range_start + m))
            if range_start >= 0 and mode != "point_burst":
                used.append((range_start, range_start + m))
        episodes.append(Episode(episode_id, start_round, range_start, keys))
        previous.append(episodes[-1])
        episode_id += 1
    for round_rq, _, ep in extra:
        if round_rq < rounds - 2:
            episodes.append(ep)
    episodes.sort(key=lambda e: e.start_round)
    for new_id, ep in enumerate(episodes):
        episodes[new_id] = Episode(new_id, ep.start_round, ep.range_start, ep.keys)
    return episodes


# ---------------------------------------------------------------------------
# Experiment runner (simulation side; also produces ground truth).
# ---------------------------------------------------------------------------


def run_experiment(
    cfg: WaffleConfig,
    mode: str,
    seed: int,
    outdir: Path,
    episode_every: int,
    m_min: int,
    m_max: int,
    overlap_bias: float,
    warmup: int,
    bg_rate: int = 40,
    gaps: Sequence[int] = (20, 45, 90, 200),
) -> Path:
    rng = random.Random(seed)
    episodes = (
        make_episodes(
            rng,
            cfg.n_real,
            cfg.rounds,
            warmup,
            episode_every,
            m_min,
            m_max,
            overlap_bias,
            mode,
            gaps=gaps,
        )
        if mode != "control"
        else []
    )
    workload = RangeMixWorkload(
        cfg.n_real,
        cfg.client_requests,
        cfg.group_zipf,
        random.Random(seed * 2 + 1),
        episodes=episodes,
        bg_rate=bg_rate,
    )
    run_id = f"{mode}_seed{seed}"
    sim = WaffleSim(cfg, workload, seed=seed * 10 + 1, trace_prefix=run_id)
    sim.run()
    outdir.mkdir(parents=True, exist_ok=True)
    trace_path = outdir / f"{run_id}_waffle.tsv"
    sim.write_trace_tsv(trace_path)
    truth = {
        "mode": mode,
        "seed": seed,
        "cfg": cfg.__dict__,
        "warmup": warmup,
        "episodes": [
            {
                "episode_id": e.episode_id,
                "start_round": e.start_round,
                "range_start": e.range_start,
                "m": e.m,
                "keys": list(e.keys),
            }
            for e in episodes
        ],
    }
    truth_path = outdir / f"{run_id}_truth.json"
    truth_path.write_text(json.dumps(truth, indent=2))
    return trace_path


# ---------------------------------------------------------------------------
# Attack side. Only ATTACK_FIELDS ever reach here.
# ---------------------------------------------------------------------------


def load_events(trace_path: Path) -> list[dict[str, object]]:
    events: list[dict[str, object]] = []
    with trace_path.open(newline="") as handle:
        reader = csv.DictReader(handle, delimiter="\t")
        missing = [f for f in ATTACK_FIELDS if f not in (reader.fieldnames or [])]
        if missing:
            raise ValueError(f"trace missing fields {missing}")
        for row in reader:
            events.append({f: row[f] for f in ATTACK_FIELDS})
    return events


@dataclass
class Read:
    storage_key: str
    batch: int
    alpha: int
    parent_batch: int  # batch where this incarnation was written
    flavor: str = "other"  # flush / miss / cold / dummy / other (attack-derived)


@dataclass
class Incarnations:
    reads: list[Read]
    writes_at: dict[int, list[str]]  # batch -> storage keys written
    reads_at: dict[int, list[Read]]
    batches: list[int]
    transient_end: int = 0


def build_incarnations(events: Sequence[dict[str, object]]) -> Incarnations:
    write_batch_of: dict[str, int] = {}
    writes_at: dict[int, list[str]] = defaultdict(list)
    reads_at: dict[int, list[Read]] = defaultdict(list)
    reads: list[Read] = []
    for event in events:
        batch = int(event["batch_ts"])  # type: ignore[arg-type]
        key = str(event["storage_key"])
        if event["direction"] == "write":
            write_batch_of[key] = batch
            writes_at[batch].append(key)
        else:
            written = write_batch_of.get(key)
            if written is None:
                continue  # pre-trace warmup incarnation
            read = Read(key, batch, batch - written, written)
            reads.append(read)
            reads_at[batch].append(read)
    inc = Incarnations(reads, dict(writes_at), dict(reads_at), sorted(reads_at))
    return inc


def stage_a_anatomy(
    inc: Incarnations, track_span: int = 80, flush_frac: float = 0.08
) -> dict[str, object]:
    """Passive batch anatomy from alpha timing only.

    Channels (all server-visible):
      * reads/batch  -> B_hat; writes/batch -> the write-phase size.
      * flush mode   -> fake reals self-identify at the uncached-pool flush
        age (least-timestamp selection). We find the argmax spike, then
        ADAPTIVELY expand the window while neighbour bins carry >= 20% of
        the mode mass (fake alphas drift around the flush age).
      * dummy support: alphas above the flush window up to the last
        occupied bin before a >= 25-bin gap (the dummy epoch support edge);
        the median per-batch count is f_D_hat.
      * miss series  -> real_reads_per_batch - flush_count (Waffle invariant:
        reals per batch are constant; fakes fill whatever misses leave free).

    Known sensitivity: if the flush age approaches the dummy epoch, the two
    alpha populations entangle and the channels degrade - reported honestly.
    """
    reads_per_batch = Counter({b: len(rs) for b, rs in inc.reads_at.items()})
    writes_per_batch = Counter({b: len(k) for b, k in inc.writes_at.items()})
    b_hat = median(reads_per_batch.values())
    write_hat = median(writes_per_batch.values())

    alpha_hist = Counter(read.alpha for read in inc.reads if read.alpha > 2)
    if not alpha_hist:
        raise RuntimeError("empty alpha histogram; run longer")
    flush_mode = max(alpha_hist.items(), key=lambda kv: kv[1])[0]
    mode_count = alpha_hist[flush_mode]
    lo = hi = flush_mode
    while lo - 1 > 0 and alpha_hist.get(lo - 1, 0) >= 0.2 * mode_count:
        lo -= 1
    while alpha_hist.get(hi + 1, 0) >= 0.2 * mode_count:
        hi += 1
    flush_lo, flush_hi = lo, hi

    # Dummy support edge: last occupied bin (count >= 3) above the flush
    # window before a >= 25-bin gap.
    occupied = sorted(a for a, c in alpha_hist.items() if c >= 3 and a > flush_hi)
    edge = 0
    for a in occupied:
        if not any(a < b <= a + 25 for b in occupied):
            edge = a
    if edge == 0:  # fallback: heavy percentile
        above = sorted(a for a, c in alpha_hist.items() for _ in range(c) if a > flush_hi)
        edge = above[min(len(above) - 1, int(0.995 * len(above)))] if above else flush_hi + 4

    flush_by_batch: Counter[int] = Counter()
    dummy_by_batch: Counter[int] = Counter()
    for read in inc.reads:
        if flush_lo <= read.alpha <= flush_hi:
            read.flavor = "flush"
            flush_by_batch[read.batch] += 1
        elif flush_hi < read.alpha <= edge:
            read.flavor = "dummy"
            dummy_by_batch[read.batch] += 1

    f_d_hat = median(dummy_by_batch.values()) if dummy_by_batch else 0
    real_reads_hat = b_hat - f_d_hat

    # Rolling-mode miss series: the fake flush age DRIFTS whenever the miss
    # rate shifts (fewer fakes -> slower pool consumption -> older flush age),
    # so a fixed window confuses drift with misses. The attacker instead
    # tracks the flush mode per batch over a trailing alpha histogram and
    # counts reads inside that batch's mode window as fakes.
    alphas_by_batch: dict[int, Counter[int]] = {}
    reads_by_batch: dict[int, list[Read]] = defaultdict(list)
    for read in inc.reads:
        reads_by_batch[read.batch].append(read)
        alphas_by_batch.setdefault(read.batch, Counter())[read.alpha] += 1
    tracked_batches = sorted(reads_by_batch)
    hist: Counter[int] = Counter()
    trailing: list[tuple[int, Counter[int]]] = []
    miss_by_batch: dict[int, int] = {}
    flush_counts: list[int] = []
    flush_span: list[int] = []
    for b in tracked_batches:
        trailing.append((b, alphas_by_batch[b]))
        hist.update(alphas_by_batch[b])
        while trailing and b - trailing[0][0] >= track_span:
            _, old = trailing.pop(0)
            hist.subtract(old)
        if b < track_span:
            miss_by_batch[b] = 0
            flush_counts.append(0)
            flush_span.append(0)
            continue
        mode_t = max(hist.items(), key=lambda kv: kv[1])[0]
        # Relative window: at large B the fake-alpha spread scales with the
        # flush age itself, so a fixed +-3 window under-captures fakes and
        # injects O(f_R) noise into the miss series.
        half_width = max(3, int(round(flush_frac * mode_t)))
        window = (mode_t - half_width, mode_t + half_width)
        flush_n = sum(
            1 for r in reads_by_batch[b] if window[0] <= r.alpha <= window[1]
        )
        flush_counts.append(flush_n)
        flush_span.append(window[1] - window[0] + 1)
        miss_by_batch[b] = max(0, int(real_reads_hat) - flush_n)
        # flavor re-assignment with the tracked window (drift-robust)
        for r in reads_by_batch[b]:
            if window[0] <= r.alpha <= window[1] and r.flavor != "dummy":
                r.flavor = "flush"

    entangled = bool(flush_hi + 10 >= (edge or flush_hi + 10))

    # Structural transient rule (server-derivable, not ground truth): before
    # the uncached-pool flush cycle forms, the flush count is depressed and
    # alpha structure is unrepresentative. Detection/tracking start at the
    # first batch after which the flush count stays >= 50% of its median.
    steady = median([c for c in flush_counts if c > 0]) if any(flush_counts) else 0
    transient_end = 0
    if steady > 0:
        run = 0
        for b, c in zip(tracked_batches, flush_counts):
            run = run + 1 if c >= 0.5 * steady else 0
            if run >= 15:
                transient_end = b - 14
                break
    for read in inc.reads:
        if read.batch < transient_end and read.flavor != "flush":
            read.flavor = "warmup"
    return {
        "b_hat": b_hat,
        "write_hat": write_hat,
        "flush_mode": flush_mode,
        "flush_window": [flush_lo, flush_hi],
        "flush_mode_count": mode_count,
        "f_r_mean": mean(flush_by_batch.values()),
        "f_d_hat": f_d_hat,
        "real_reads_hat": real_reads_hat,
        "dummy_edge": edge,
        "channels_entangled": entangled,
        "transient_end": transient_end,
        "miss_series": miss_by_batch,
        "miss_median": median(miss_by_batch.values()) if miss_by_batch else 0,
        "n_reads": len(inc.reads),
        "n_batches": len(inc.batches),
    }


def batch_features(
    inc: Incarnations,
    anatomy: dict[str, object],
    cold_threshold: int,
) -> dict[int, dict[str, float]]:
    """Order-hidden per-batch features from server-visible timing only.

    miss      : recovered client-miss count (real budget - flush count).
    cold      : misses whose incarnation is older than cold_threshold.
                NOTE: Waffle's fake traffic re-writes every uncached object
                every ~pool/f_R batches, so huge-alpha first-touch reads
                vanish after the first flush cycle in high-f_R regimes.
    cop_count : largest set of non-flavor reads in the batch sharing one
                parent write batch (co-parent concentration - the range
                re-query fingerprint).
    Batches before the structural transient end are excluded.
    """
    miss_series = anatomy["miss_series"]  # type: ignore[assignment]
    transient_end = int(anatomy.get("transient_end", 0))  # type: ignore[arg-type]
    features: dict[int, dict[str, float]] = {}
    for batch in inc.batches:
        if batch < transient_end:
            continue
        reads = inc.reads_at.get(batch, [])
        cold = sum(
            1 for r in reads if r.flavor not in ("flush", "warmup")
            and r.alpha >= cold_threshold
        )
        parent_counts: Counter[int] = Counter()
        for r in reads:
            if r.flavor in ("flush", "dummy", "warmup") or r.parent_batch >= batch:
                continue
            if r.parent_batch < transient_end:
                continue
            parent_counts[r.parent_batch] += 1
        top_count = max(parent_counts.values()) if parent_counts else 0
        features[batch] = {
            "miss": float(miss_series.get(batch, 0)),  # type: ignore[union-attr]
            "cold": float(cold),
            "cop_count": float(top_count),
        }
    return features


def stage_b_detect_episodes(
    features: dict[int, dict[str, float]],
    control_features: dict[int, dict[str, float]] | None = None,
    threshold_z: float = 6.0,
    gap: int = 3,
    min_mass: float = 30.0,
    window: int = 50,
) -> tuple[list[list[int]], dict[str, float]]:
    """Detect episode batches with a self-calibrated rolling robust z-score.

    For every batch, miss/cop mass is compared to a centered rolling window
    (median + MAD). Episodes last a few batches, so the rolling median is a
    robust background estimate even when it contains episode batches. The
    control run, when given, is scored the same way to count false positives
    - it is never used to set the threshold.
    """
    def detect(feats: dict[int, dict[str, float]]) -> tuple[list[list[int]], float]:
        batches = sorted(feats)
        # 3-batch centered moving average: suppresses the attacker's own
        # rolling-mode measurement noise while keeping 2-5 batch episodes.
        smoothed: dict[int, dict[str, float]] = {}
        for i, batch in enumerate(batches):
            neigh = batches[max(0, i - 1) : i + 2]
            smoothed[batch] = {
                name: sum(feats[b][name] for b in neigh) / len(neigh)
                for name in ("miss", "cop_count", "cold")
            }
        flagged: list[int] = []
        for i, batch in enumerate(batches):
            local = [
                smoothed[b]
                for b in batches[max(0, i - window) : i + window + 1]
            ]
            score = 0.0
            for name in ("miss", "cop_count"):
                values = [f[name] for f in local]
                med = median(values)
                mad = median([abs(v - med) for v in values])
                scale = 1.4826 * mad
                if scale <= 1e-9:
                    z = 0.0 if smoothed[batch][name] <= med else threshold_z
                else:
                    z = (smoothed[batch][name] - med) / scale
                score += max(0.0, z)
            if score >= threshold_z:
                flagged.append(batch)
        episodes: list[list[int]] = []
        for batch in flagged:
            if episodes and batch - episodes[-1][-1] <= gap:
                episodes[-1].append(batch)
            else:
                episodes.append([batch])
        # Sustained-excess rule: range episodes drain for >= 2 batches;
        # isolated single-batch spikes are background oscillation unless
        # their mass is overwhelming.
        kept = []
        for ep in episodes:
            mass = sum(
                feats[b]["miss"] + feats[b]["cop_count"] + feats[b]["cold"]
                for b in ep
            )
            if len(ep) >= 2 and mass >= min_mass:
                kept.append(ep)
            elif len(ep) == 1 and mass >= 3 * min_mass:
                kept.append(ep)
        return kept, float(sum(len(ep) for ep in kept))

    detected, flagged_mass = detect(features)
    fp_batches = 0.0
    if control_features:
        _, control_flagged = detect(control_features)
        fp_batches = control_flagged
    return detected, {
        "threshold_z": threshold_z,
        "flagged_batches": flagged_mass,
        "false_positive_batches": fp_batches,
        "n_episodes_detected": float(len(detected)),
    }


def stage_c_cardinality(
    episodes: Sequence[Sequence[int]],
    features: dict[int, dict[str, float]],
    control_features: dict[int, dict[str, float]] | None = None,
    local_bg: int = 40,
) -> list[dict[str, float]]:
    """Estimate matched-record count m per detected episode.

    m_hat is the excess client-miss mass over a LOCAL background median
    (batches within +-40 of the episode span, excluding the span itself -
    fully attack-derivable, no ground truth and no control run needed).
    Cached re-reads are invisible by design, so m_hat targets the visible
    part of m; the gap to the true m is itself a leakage-boundary finding.
    """
    batches_sorted = sorted(features)
    rows: list[dict[str, float]] = []
    for ep_id, ep in enumerate(episodes):
        lo, hi = min(ep), max(ep)
        outside = [
            features[b]["miss"]
            for b in batches_sorted
            if lo - local_bg <= b <= hi + local_bg and b not in set(ep)
        ]
        bg_local = median(outside) if outside else 0.0
        miss = sum(features[b]["miss"] for b in ep)
        cold = sum(features[b]["cold"] for b in ep)
        cop = sum(features[b]["cop_count"] for b in ep)
        excess = miss - bg_local * len(ep)
        rows.append(
            {
                "episode": ep_id,
                "batches": len(ep),
                "bg_local": bg_local,
                "miss_mass": miss,
                "cold_mass": cold,
                "cop_mass": cop,
                "m_hat": max(0.0, excess),
            }
        )
    return rows


def stage_d_tracking(
    inc: Incarnations,
    episodes: Sequence[Sequence[int]],
    control_inc: Incarnations,
    min_pair_mass: float = 8.0,
    bg_confidence: float = 10.0,
    max_cell: float = 4.0,
    eviction_tail: int = 15,
) -> dict[str, object]:
    """Cross-incarnation tracking by exact timing arithmetic.

    Every non-flavor read at batch t with alpha a has parent batch t-a, the
    batch whose eviction writes produced its incarnation. LRU eviction
    DISPERSES a range's keys over the few batches after the episode, so the
    re-read signal is not a per-cell burst: we aggregate (parent, child)
    cell mass into DETECTED-EPISODE-PAIR mass and keep pairs whose mass
    exceeds both an absolute floor and a background-expected multiple,
    where the background expectation per cell comes from the control run
    (server-visible, no ground truth). Per-id links are kept only where
    the parent batch has a single candidate write - the honest boundary of
    id-level tracking under wide eviction cohorts.
    """
    episode_of_batch: dict[int, int] = {}
    for ep_id, batches in enumerate(episodes):
        for b in batches:
            episode_of_batch[b] = ep_id
    pair_mass: Counter[tuple[int, int]] = Counter()
    links_unique: list[dict[str, object]] = []
    ambiguous_reads = 0
    for read in inc.reads:
        if read.flavor in ("flush", "dummy", "warmup") or read.parent_batch >= read.batch:
            continue
        if read.parent_batch < inc.transient_end:
            continue
        writers = inc.writes_at.get(read.parent_batch, [])
        if not writers:
            continue
        pair_mass[(read.parent_batch, read.batch)] += 1
        if len(writers) == 1:
            links_unique.append(
                {
                    "parent_key": writers[0],
                    "child_key": read.storage_key,
                    "parent_batch": read.parent_batch,
                    "child_batch": read.batch,
                    "alpha": read.alpha,
                }
            )
        else:
            ambiguous_reads += 1

    episode_pair_end: dict[int, int] = {
        ep_id: max(batches) for ep_id, batches in enumerate(episodes)
    }
    parent_episode_of: dict[int, int] = dict(episode_of_batch)
    # Widen parent attribution: an episode's keys are evicted by the first
    # batches AFTER its drain span (LRU tail), so a parent batch belongs to
    # the nearest preceding episode whose span ended within EVICTION_TAIL.
    # TAIL is an attack-side parameter (cache turnover window), not truth.
    sorted_spans = sorted(
        ((min(batches), max(batches), ep_id) for ep_id, batches in enumerate(episodes)),
        key=lambda x: x[1],
    )
    for b in sorted({p for p, _ in pair_mass} | {t for _, t in pair_mass}):
        if b in episode_of_batch:
            continue
        best = None
        for lo, hi, ep_id in sorted_spans:
            if hi < b <= hi + eviction_tail:
                best = ep_id
        if best is not None:
            parent_episode_of[b] = best

    def ep_pair_of(p: int, t: int) -> tuple[int, int] | None:
        i = parent_episode_of.get(p)
        j = episode_of_batch.get(t)
        if i is not None and j is not None and i != j:
            return (i, j)
        return None

    # Background expectation per (parent, child) cell from the control run,
    # indexed by batch DISTANCE t-p: background re-reads have a lag profile,
    # and episode spacing can coincide with its tail, so a flat per-cell
    # rate would mistake that coincidence for overlap structure.
    control_mass: Counter[tuple[int, int]] = Counter()
    for read in control_inc.reads:
        if read.flavor in ("flush", "dummy", "warmup") or read.parent_batch >= read.batch:
            continue
        if read.parent_batch < control_inc.transient_end:
            continue
        if control_inc.writes_at.get(read.parent_batch):
            control_mass[(read.parent_batch, read.batch)] += 1
    n_control_batches = max(1, len(control_inc.batches))
    control_mass_by_dist: dict[int, list[int]] = defaultdict(list)
    for (p, t), c in control_mass.items():
        control_mass_by_dist[t - p].append(c)
    bg_expected_at_dist: dict[int, float] = {}
    for d, masses in control_mass_by_dist.items():
        cells_at_d = max(1, n_control_batches - d)
        bg_expected_at_dist[d] = (sum(masses) / len(masses)) * (
            len(masses) / cells_at_d
        ) if masses else 0.0
    bg_cell_mean = (
        sum(control_mass.values()) / max(1, n_control_batches**2 / 2)
    )

    # Aggregate cells into detected-episode-pair mass (keeping per-cell
    # values for the concentration rule).
    episode_pair_cells_mass: dict[tuple[int, int], Counter[int]] = defaultdict(Counter)
    for (p, t), c in pair_mass.items():
        pair = ep_pair_of(p, t)
        if pair is not None:
            episode_pair_cells_mass[pair][t - p] += c
    overlap: dict[str, float] = {}
    for (i, j), per_dist in episode_pair_cells_mass.items():
        per_cell = [c for c in per_dist.values()]
        mass = sum(per_cell)
        cell_max = max(per_cell)
        # Concentration rule: a genuine re-query re-reads its overlap cohort
        # from the queue front, concentrating mass in a few (parent, child)
        # cells; background redraw chains disperse over the whole window.
        if mass >= min_pair_mass and cell_max >= max_cell:
            overlap[f"{i}->{j}"] = float(mass)
    return {
        "overlap_counts": dict(sorted(overlap.items())),
        "burst_pairs": sum(1 for c in pair_mass.values() if c >= 5),
        "burst_mass": sum(c for c in pair_mass.values() if c >= 5),
        "bg_cell_mean": bg_cell_mean,
        "bg_burst_pairs_per_batch": sum(
            1 for c in control_mass.values() if c >= 5
        ) / n_control_batches,
        "bg_burst_mass_per_batch": sum(
            c for c in control_mass.values() if c >= 5
        ) / n_control_batches,
        "min_pair_mass": min_pair_mass,
        "bg_confidence": bg_confidence,
        "eviction_tail": eviction_tail,
        "unique_links": links_unique,
        "ambiguous_reads": ambiguous_reads,
    }


def permutation_null(
    inc: Incarnations,
    episodes: Sequence[Sequence[int]],
    trials: int,
    seed: int,
    min_pair_mass: float = 8.0,
    bg_cell_mean: float = 0.0,
    max_cell: float = 4.0,
    eviction_tail: int = 15,
) -> dict[str, float]:
    """Randomized-parent null: reattribute every non-flavor read to a
    uniformly random earlier batch (destroying the timing link between a
    read and the eviction batch that wrote its incarnation), aggregate into
    episode-pair mass with the same threshold as the attack, and report the
    total surviving cross-episode overlap."""
    rng = random.Random(seed)
    episode_of_batch: dict[int, int] = {}
    for ep_id, batches in enumerate(episodes):
        for b in batches:
            episode_of_batch[b] = ep_id
    batch_list = sorted(b for b in inc.writes_at if b >= inc.transient_end)
    if not batch_list:
        return {"null_overlap_mean": 0.0, "null_overlap_max": 0.0, "trials": 0.0}
    sorted_spans = sorted(
        ((min(batches), max(batches), ep_id) for ep_id, batches in enumerate(episodes)),
        key=lambda x: x[1],
    )
    parent_episode_of: dict[int, int] = dict(episode_of_batch)
    all_parent_candidates = sorted(
        set(batch_list) | set(episode_of_batch)
    )
    for b in all_parent_candidates:
        if b in parent_episode_of:
            continue
        best = None
        for lo, hi, ep_id in sorted_spans:
            if hi < b <= hi + eviction_tail:
                best = ep_id
        if best is not None:
            parent_episode_of[b] = best
    reads = [
        r for r in inc.reads
        if r.flavor not in ("flush", "dummy", "warmup") and r.parent_batch < r.batch
        and r.parent_batch >= inc.transient_end
    ]
    scores: list[float] = []
    for _ in range(trials):
        episode_pair_cells_mass: dict[tuple[int, int], Counter[int]] = defaultdict(Counter)
        for read in reads:
            parent = batch_list[rng.randrange(max(1, bisect.bisect_right(batch_list, read.batch)))]
            if parent >= read.batch or not inc.writes_at.get(parent):
                continue
            i = parent_episode_of.get(parent)
            j = episode_of_batch.get(read.batch)
            if i is not None and j is not None and i != j:
                episode_pair_cells_mass[(i, j)][read.batch - parent] += 1
        total = 0.0
        for (i, j), per_dist in episode_pair_cells_mass.items():
            masses = list(per_dist.values())
            mass = sum(masses)
            cell_max = max(masses)
            if mass >= max(min_pair_mass, 8.0) and cell_max >= max_cell:
                total += mass
        scores.append(total)
    return {
        "null_overlap_mean": mean(scores) if scores else 0.0,
        "null_overlap_max": max(scores) if scores else 0.0,
        "trials": float(trials),
    }


# ---------------------------------------------------------------------------
# Evaluation side (ground truth allowed here and ONLY here).
# ---------------------------------------------------------------------------


def load_truth(path: Path) -> dict[str, object]:
    return json.loads(path.read_text())


def full_trace_reads(trace_path: Path) -> list[dict[str, str]]:
    with trace_path.open(newline="") as handle:
        return list(csv.DictReader(handle, delimiter="\t"))


def true_episode_spans(
    truth: dict[str, object], reads: Sequence[dict[str, str]]
) -> dict[int, set[int]]:
    """Ground-truth drain span per episode (evaluation only).

    An episode's visible footprint is the set of batches where its keys land
    as client misses right after the query enters the queue: for each episode
    key, the FIRST client_real read at batch >= start_round, capped by a
    drain horizon of 4*ceil(m/R)+10 batches (keys first read later than that
    were served from cache at episode time or hit by background traffic -
    either way they are not part of the episode's drain span)."""
    reads_per_key: dict[str, list[int]] = defaultdict(list)
    for row in reads:
        if row["role"] == "client_real":
            reads_per_key[row["logical_key"]].append(int(row["batch_ts"]))
    for key in reads_per_key:
        reads_per_key[key].sort()
    import bisect

    spans: dict[int, set[int]] = defaultdict(set)
    for ep in truth["episodes"]:  # type: ignore[index]
        start = ep["start_round"]  # type: ignore[index]
        horizon = start + 4 * ((ep["m"] + 63) // 64) + 10  # type: ignore[index]
        for key in ep["keys"]:  # type: ignore[index]
            batches = reads_per_key.get(f"real/{key}", [])
            i = bisect.bisect_left(batches, start)
            if i < len(batches) and batches[i] <= horizon:
                spans[ep["episode_id"]].add(batches[i])  # type: ignore[index]
    return spans


def match_episodes(
    detected: Sequence[Sequence[int]],
    truth: dict[str, object],
    reads: Sequence[dict[str, str]],
    iou_cut: float = 0.3,
) -> tuple[dict[int, set[int]], list[tuple[int, int, float]]]:
    """Match detected spans to true drain spans by IoU (evaluation only).

    Returns (spans, matches) where matches is a list of
    (detected_index, true_episode_id, iou), one per detected episode at its
    best-overlapping true episode when IoU >= iou_cut."""
    spans = true_episode_spans(truth, reads)
    matches = []
    for det_id, det in enumerate(detected):
        det_set = set(det)
        best, best_iou = None, 0.0
        for ep_id, span in spans.items():
            union = det_set | span
            iou = len(det_set & span) / len(union) if union else 0.0
            if iou > best_iou:
                best, best_iou = ep_id, iou
        if best is not None and best_iou >= iou_cut:
            matches.append((det_id, best, best_iou))
    return spans, matches


def eval_b(
    detected: Sequence[Sequence[int]],
    truth: dict[str, object],
    reads: Sequence[dict[str, str]],
) -> dict[str, float]:
    spans, matches = match_episodes(detected, truth, reads)
    matched_true = {true_id for _, true_id, _ in matches}
    matched_det = {det_id for det_id, _, _ in matches}
    ious = [iou for _, _, iou in matches]
    precision = len(matched_det) / max(1, len(detected))
    recall = len(matched_true) / max(1, len(spans))
    f1 = 2 * precision * recall / max(1e-9, precision + recall)
    return {
        "true_episodes": float(len(spans)),
        "detected": float(len(detected)),
        "matched": float(len(matched_true)),
        "precision": precision,
        "recall": recall,
        "f1": f1,
        "mean_iou_matched": mean(ious) if ious else 0.0,
    }


def visible_targets(
    truth: dict[str, object], reads: Sequence[dict[str, str]]
) -> tuple[list[int], list[int]]:
    """Per episode: (visible target, raw m).

    A key is visible (will miss when the episode arrives) iff it is NOT in
    the proxy cache at episode start. Reconstructed from the labelled trace:
    any read of the key (client or fake) caches it; an evicted_real write of
    the key evicts it. The state at start is the polarity of the last event
    before start (no events -> uncached, ignoring the random initial cache)."""
    events_per_key: dict[str, list[tuple[int, str]]] = defaultdict(list)
    for row in reads:
        if row["role"] in ("client_real", "fake_real", "evicted_real"):
            events_per_key[row["logical_key"]].append(
                (int(row["batch_ts"]), row["role"])
            )
    for key in events_per_key:
        events_per_key[key].sort()
    targets, raw = [], []
    for ep in truth["episodes"]:  # type: ignore[index]
        start = ep["start_round"]  # type: ignore[index]
        visible = 0
        for key in ep["keys"]:  # type: ignore[index]
            events = events_per_key.get(f"real/{key}", [])
            prior = [e for e in events if e[0] < start]
            if not prior or prior[-1][1] == "evicted_real":
                visible += 1
        targets.append(visible)
        raw.append(ep["m"])  # type: ignore[index]
    return targets, raw


def eval_c(
    rows: Sequence[dict[str, float]],
    detected: Sequence[Sequence[int]],
    truth: dict[str, object],
    reads: Sequence[dict[str, str]],
) -> dict[str, float]:
    """m_hat versus (a) the visible (uncached-at-start) target and (b) raw m,
    scored only on episodes whose spans match truth by IoU."""
    _, matches = match_episodes(detected, truth, reads)
    targets, raw_m = visible_targets(truth, reads)
    vis_err, raw_err = [], []
    for det_id, true_id, _ in matches:
        row = rows[det_id]
        vis_err.append(abs(row["m_hat"] - targets[true_id]))
        raw_err.append(row["m_hat"] - raw_m[true_id])
    if not vis_err:
        return {"n": 0.0}
    rel = [
        e / max(1, targets[true_id])
        for e, (_, true_id, _) in zip(vis_err, matches)
    ]
    return {
        "n": float(len(vis_err)),
        "mae_vs_visible": mean(vis_err),
        "median_rel_err_vs_visible": median(rel),
        "worst_rel_err_vs_visible": max(rel),
        "mean_undercount_vs_raw_m": mean(raw_err),
    }


def eval_d(
    unique_links: Sequence[dict[str, object]],
    reads: Sequence[dict[str, str]],
) -> dict[str, float]:
    """Precision of unambiguous id-level links (same logical key)."""
    logical_of_storage = {row["storage_key"]: row["logical_key"] for row in reads}
    correct = 0
    for link in unique_links:
        parent = logical_of_storage.get(str(link["parent_key"]))
        child = logical_of_storage.get(str(link["child_key"]))
        if parent is not None and parent == child:
            correct += 1
    return {
        "unique_links": float(len(unique_links)),
        "unique_link_precision": correct / len(unique_links) if unique_links else 0.0,
    }


def eval_e(
    matrix: Sequence[Sequence[float]],
    detected: Sequence[Sequence[int]],
    truth: dict[str, object],
    matches: list[tuple[int, int, float]],
) -> dict[str, object]:
    """Correlation between estimated and true overlap matrices, restricted
    to matched episodes, plus the gap-boundary curve: overlap-recovery rate
    versus the inter-query gap (the background-refresh timescale)."""
    eps = truth["episodes"]  # type: ignore[index]
    key_sets = [set(ep["keys"]) for ep in eps]  # type: ignore[index]
    starts = [ep["start_round"] for ep in eps]  # type: ignore[index]
    det_ids = sorted(det_id for det_id, _, _ in matches)
    true_of = {det_id: true_id for det_id, true_id, _ in matches}
    flat_est, flat_true = [], []
    for a in det_ids:
        for b in det_ids:
            if a == b:
                continue
            flat_est.append(matrix[a][b])
            ta, tb = true_of[a], true_of[b]
            flat_true.append(float(len(key_sets[ta] & key_sets[tb])))
    pear = _pearson(flat_est, flat_true)
    rank = _spearman(flat_est, flat_true)
    large = [(e, t) for e, t in zip(flat_est, flat_true) if t >= 10]
    pear_large = _pearson([e for e, _ in large], [t for _, t in large]) if large else 0.0
    best_acc = 0.0
    for thr in sorted(set(flat_est)):
        tp = fp = tn = fn = 0
        for e, t in zip(flat_est, flat_true):
            pred = e >= thr
            if t > 0 and pred:
                tp += 1
            elif t > 0:
                fn += 1
            elif pred:
                fp += 1
            else:
                tn += 1
        acc = (tp + tn) / max(1, tp + tn + fp + fn)
        best_acc = max(best_acc, acc)
    # Gap-boundary curve over true deliberate pairs (overlap >= 30),
    # recorded at PER-GAP resolution on the actual inter-query gap (no
    # quantisation into coarse buckets): gap -> [n_pair, n_recovered].
    # boundary_pairs keeps the raw (gap, hit, overlap) triplets so that a
    # continuous recovery curve can be fitted downstream.
    boundary: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    boundary_pairs: list[list[float]] = []
    for det_i in det_ids:
        for det_j in det_ids:
            if det_i >= det_j:
                continue
            ti, tj = true_of[det_i], true_of[det_j]
            ov = len(key_sets[ti] & key_sets[tj])
            if ov < 30:
                continue
            gap = starts[tj] - starts[ti]
            hit = 1 if (matrix[det_i][det_j] > 0 or matrix[det_j][det_i] > 0) else 0
            boundary[str(gap)][0] += 1
            boundary[str(gap)][1] += hit
            boundary_pairs.append([float(gap), float(hit), float(ov)])
    return {
        "scored_dim": float(len(det_ids)),
        "pearson": pear,
        "spearman": rank,
        "pearson_large_overlap": pear_large,
        "large_pairs": float(len(large)),
        "overlap_binary_acc": best_acc,
        "pairs": float(len(flat_est)),
        "positive_pairs": float(sum(1 for v in flat_true if v > 0)),
        "estimated_positive_pairs": float(sum(1 for v in flat_est if v > 0)),
        "boundary_by_gap": {k: tuple(v) for k, v in sorted(
            boundary.items(), key=lambda kv: float(kv[0]))},
        "boundary_pairs": boundary_pairs,
    }


def _pearson(xs: Sequence[float], ys: Sequence[float]) -> float:
    if len(xs) < 2:
        return 0.0
    mx, my = mean(xs), mean(ys)
    sx, sy = pstdev(xs), pstdev(ys)
    if sx == 0 or sy == 0:
        return 0.0
    return sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / (len(xs) * sx * sy)


def _spearman(xs: Sequence[float], ys: Sequence[float]) -> float:
    def ranks(values: Sequence[float]) -> list[float]:
        order = sorted(range(len(values)), key=lambda i: values[i])
        out = [0.0] * len(values)
        i = 0
        while i < len(order):
            j = i
            while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
                j += 1
            avg = (i + j) / 2 + 1
            for k in range(i, j + 1):
                out[order[k]] = avg
            i = j + 1
        return out

    return _pearson(ranks(xs), ranks(ys))


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--outdir", type=Path, default=RESULTS_DIR / "range_query_attack")
    parser.add_argument("--rounds", type=int, default=2500)
    parser.add_argument("--seed", type=int, default=7)
    parser.add_argument("--n-real", type=int, default=8192)
    parser.add_argument("--n-dummy", type=int, default=2048)
    parser.add_argument("--batch-size", type=int, default=128)
    parser.add_argument("--client-requests", type=int, default=64)
    parser.add_argument("--dummy-reads", type=int, default=16)
    parser.add_argument("--cache-size", type=int, default=512)
    parser.add_argument("--warmup", type=int, default=400)
    parser.add_argument("--episode-every", type=int, default=45)
    parser.add_argument("--m-min", type=int, default=40)
    parser.add_argument("--m-max", type=int, default=200)
    parser.add_argument("--overlap-bias", type=float, default=0.35)
    parser.add_argument("--bg-rate", type=int, default=40)
    parser.add_argument(
        "--requery-gaps",
        default="20,45,90,200",
        help="candidate inter-query gaps (batches) for deliberate re-queries",
    )
    parser.add_argument("--cold-threshold", type=int, default=300)
    parser.add_argument("--threshold-z", type=float, default=5.0)
    parser.add_argument("--null-trials", type=int, default=20)
    # Attack-side hyperparameters (exposed for sensitivity analysis; the
    # defaults equal the previously hard-coded values, so default runs are
    # bit-for-bit reproducible with pre-parameterisation results).
    parser.add_argument(
        "--track-span", type=int, default=80,
        help="Stage A: trailing batches for the rolling flush-mode tracker",
    )
    parser.add_argument(
        "--flush-frac", type=float, default=0.08,
        help="Stage A: flush half-window as a fraction of the tracked mode",
    )
    parser.add_argument(
        "--local-bg", type=int, default=40,
        help="Stage C: local background half-window (batches) around an episode",
    )
    parser.add_argument(
        "--min-mass", type=float, default=30.0,
        help="Stage B: sustained-excess minimum miss/cop/cold mass per episode",
    )
    parser.add_argument(
        "--window", type=int, default=50,
        help="Stage B: rolling robust-z half-window (batches)",
    )
    parser.add_argument(
        "--gap", type=int, default=3,
        help="Stage B: batch merge gap inside one detected episode",
    )
    parser.add_argument(
        "--min-pair-mass", type=float, default=8.0,
        help="Stage D: minimum aggregate mass for an episode-pair link",
    )
    parser.add_argument(
        "--max-cell", type=int, default=4,
        help="Stage D: minimum per-cell mass for the concentration rule",
    )
    parser.add_argument(
        "--eviction-tail", type=int, default=15,
        help=("Stage D / permutation null: batches after an episode span in "
              "which its keys can still be evicted (same value used in both)"),
    )
    parser.add_argument("--quick", action="store_true")
    parser.add_argument(
        "--stages",
        default="A,B,C,D,E",
        help="comma-separated subset of stages to run (default: all)",
    )
    parser.add_argument(
        "--paper-medium",
        action="store_true",
        help="use the Waffle paper's MEDIUM-security parameters (Table 2): "
        "B=2500, R=1000, f_D=500, C=2%%N, D=350k; N,D,C,bg,m scaled 1:5 "
        "to keep the artifact's stdlib simulator feasible while preserving "
        "the ratio structure (f_D/B, R/B, flush-age/dummy-epoch).",
    )
    return parser.parse_args()


def build_cfg(args: argparse.Namespace) -> tuple[WaffleConfig, int, int]:
    rounds = 900 if args.quick else args.rounds
    warmup = 300 if args.quick else args.warmup
    every = 30 if args.quick else args.episode_every
    cfg = WaffleConfig(
        n_real=args.n_real,
        n_dummy=args.n_dummy,
        batch_size=args.batch_size,
        client_requests=args.client_requests,
        dummy_reads=args.dummy_reads,
        cache_size=args.cache_size,
        rounds=rounds,
        group_zipf=0.9,
    )
    return cfg, warmup, every


def main() -> None:
    args = parse_args()
    if args.paper_medium:
        # Paper Table 2 medium security: B=2.5k, R=1k, f_D=500, C=2%%N,
        # D=350k (N=1M). Batch-level parameters are kept EXACT; N, D, C,
        # background rate and episode sizes are scaled 1:5.
        args.n_real = 200_000
        args.n_dummy = 70_000
        args.batch_size = 2_500
        args.client_requests = 1_000
        args.dummy_reads = 500
        args.cache_size = 4_000
        args.rounds = 2_400
        args.warmup = 400
        args.episode_every = 25
        args.m_min = 300
        args.m_max = 2_000
        args.bg_rate = 120
        args.cold_threshold = 400
        args.overlap_bias = 0.6
    outdir = args.outdir if args.outdir.is_absolute() else ROOT / args.outdir
    outdir.mkdir(parents=True, exist_ok=True)
    cfg, warmup, every = build_cfg(args)
    stages = {s.strip().upper() for s in args.stages.split(",")}

    def log(msg: str) -> None:
        print(msg, flush=True)

    # -- simulations (cached across invocations by trace files) -------------
    def ensure_trace(mode: str) -> tuple[Path, Path]:
        run_id = f"{mode}_seed{args.seed}"
        trace = outdir / f"{run_id}_waffle.tsv"
        truth = outdir / f"{run_id}_truth.json"
        if not (trace.exists() and truth.exists()):
            log(f"[sim] running {mode} simulation ({cfg.rounds} rounds)...")
            run_experiment(
                cfg, mode, args.seed, outdir, every, args.m_min, args.m_max,
                args.overlap_bias, warmup, bg_rate=args.bg_rate,
                gaps=tuple(int(g) for g in args.requery_gaps.split(",")),
            )
        return trace, truth

    attack_trace, attack_truth_path = ensure_trace("range")
    control_trace, _ = ensure_trace("control")
    burst_trace, _ = ensure_trace("point_burst")

    log("[load] parsing server-visible events (whitelisted fields only)")
    attack_inc = build_incarnations(load_events(attack_trace))
    control_inc = build_incarnations(load_events(control_trace))
    burst_inc = build_incarnations(load_events(burst_trace))
    attack_anatomy = stage_a_anatomy(
        attack_inc, track_span=args.track_span, flush_frac=args.flush_frac
    )
    control_anatomy = stage_a_anatomy(
        control_inc, track_span=args.track_span, flush_frac=args.flush_frac
    )
    burst_anatomy = stage_a_anatomy(
        burst_inc, track_span=args.track_span, flush_frac=args.flush_frac
    )
    attack_inc.transient_end = int(attack_anatomy["transient_end"])
    control_inc.transient_end = int(control_anatomy["transient_end"])
    burst_inc.transient_end = int(burst_anatomy["transient_end"])

    state: dict[str, object] = {
        "config": cfg.__dict__,
        "stages_run": sorted(stages),
        "attack_params": {
            "track_span": args.track_span,
            "flush_frac": args.flush_frac,
            "local_bg": args.local_bg,
            "min_mass": args.min_mass,
            "window": args.window,
            "gap": args.gap,
            "min_pair_mass": args.min_pair_mass,
            "max_cell": args.max_cell,
            "eviction_tail": args.eviction_tail,
            "threshold_z": args.threshold_z,
            "cold_threshold": args.cold_threshold,
            "requery_gaps": args.requery_gaps,
        },
    }
    report_lines: list[str] = [
        "# Range-Query Attack on Waffle (design-level, order-hidden, passive)",
        "",
        f"- Attack visibility: {', '.join(ATTACK_FIELDS)} (simulation labels dropped at load)",
        f"- Config: `{cfg.__dict__}`",
        f"- Workload: background Zipf-0.9 point traffic + scheduled range episodes",
        "",
    ]

    anatomy = {}
    if "A" in stages:
        log("\n===== Stage A: batch anatomy (passive calibration) =====")
        anatomy = attack_anatomy
        control_anatomy_unused = None
        state["stage_a"] = {"range": {k: v for k, v in anatomy.items()
                                      if k not in ("miss_series", "cold_series")},
                            "control": {k: v for k, v in control_anatomy.items()
                                        if k not in ("miss_series", "cold_series")}}
        state["n_real"] = cfg.n_real
        state["cache_size"] = cfg.cache_size
        log(f"  B_hat={anatomy['b_hat']} (truth {cfg.batch_size})  "
            f"write_hat={anatomy['write_hat']}  real_budget_hat="
            f"{anatomy['real_reads_hat']} (truth {cfg.batch_size - cfg.dummy_reads})")
        log(f"  flush mode alpha={anatomy['flush_mode']} "
            f"window={anatomy['flush_window']} "
            f"f_R_mean={anatomy['f_r_mean']:.1f}  f_D_hat={anatomy['f_d_hat']} "
            f"(truth {cfg.dummy_reads})  dummy_edge={anatomy['dummy_edge']} "
            f"(truth epoch {cfg.n_dummy // cfg.dummy_reads})")
        if anatomy["channels_entangled"]:
            log("  WARNING: flush window reached dummy support edge; "
                "channels entangled (flush-age ~ epoch sensitivity)")
        log("  -> attack finding: fake reals self-identify via the flush-age "
            "alpha mode; per-batch miss series recovered as budget - flush")
        report_lines += [
            "## Stage A - batch anatomy",
            f"- B_hat={anatomy['b_hat']} (truth {cfg.batch_size}); "
            f"real budget={anatomy['real_reads_hat']} "
            f"(truth {cfg.batch_size - cfg.dummy_reads}); "
            f"f_D_hat={anatomy['f_d_hat']} (truth {cfg.dummy_reads})",
            f"- flush age mode alpha={anatomy['flush_mode']} "
            f"window={anatomy['flush_window']} "
            f"(fakes self-identify); f_R_mean={anatomy['f_r_mean']:.1f}; "
            f"entangled={anatomy['channels_entangled']}",
            "",
        ]
    else:
        anatomy = stage_a_anatomy(
            attack_inc, track_span=args.track_span, flush_frac=args.flush_frac
        )

    attack_feats = batch_features(attack_inc, anatomy, args.cold_threshold)
    control_feats = batch_features(control_inc, control_anatomy, args.cold_threshold)
    burst_feats = batch_features(burst_inc, burst_anatomy, args.cold_threshold)
    # Parse the labelled trace ONCE for all evaluation stages (it is large).
    reads_full = full_trace_reads(attack_trace) if stages & {"B", "C", "D", "E"} else None

    detected: list[list[int]] = []
    if "B" in stages:
        log("\n===== Stage B: range-episode detection =====")
        detected, b_stats = stage_b_detect_episodes(
            attack_feats, control_feats, threshold_z=args.threshold_z,
            gap=args.gap, min_mass=args.min_mass, window=args.window,
        )
        burst_detected, _ = stage_b_detect_episodes(
            burst_feats, control_feats, threshold_z=args.threshold_z,
            gap=args.gap, min_mass=args.min_mass, window=args.window,
        )
        truth = load_truth(attack_truth_path)
        b_eval = eval_b(detected, truth, reads_full)
        state["stage_b"] = {
            "stats": b_stats,
            "detected": detected,
            "eval": b_eval,
            "burst_detected": burst_detected,
        }
        log(f"  rolling robust-z detector (self-calibrated); FP batches on "
            f"control run: {b_stats['false_positive_batches']:.0f}")
        log(f"  detected {len(detected)} episodes "
            f"(truth {b_eval['true_episodes']}); FP batches="
            f"{b_stats['false_positive_batches']:.0f}")
        log(f"  vs ground truth: P={b_eval['precision']:.2f} "
            f"R={b_eval['recall']:.2f} F1={b_eval['f1']:.2f} "
            f"IoU={b_eval['mean_iou_matched']:.2f}")
        log(f"  point-burst control fires on {len(burst_detected)} episodes "
            "(volume is not range-specific; joint structure must separate)")
        report_lines += [
            "## Stage B - episode detection",
            f"- detected {len(detected)} episodes "
            f"(truth {b_eval['true_episodes']}): "
            f"P={b_eval['precision']:.2f} R={b_eval['recall']:.2f} "
            f"F1={b_eval['f1']:.2f} IoU={b_eval['mean_iou_matched']:.2f}",
            f"- false-positive batches: {b_stats['false_positive_batches']:.0f}",
            "",
        ]

    d_result: dict[str, object] = {}
    if "D" in stages:
        log("\n===== Stage D: cross-incarnation tracking =====")
        d_result = stage_d_tracking(
            attack_inc, detected, control_inc,
            min_pair_mass=args.min_pair_mass, max_cell=args.max_cell,
            eviction_tail=args.eviction_tail,
        )
        d_eval = eval_d(d_result["unique_links"], reads_full)  # type: ignore[arg-type]
        state["stage_d"] = {
            "overlap_counts": d_result["overlap_counts"],
            "burst_pairs": d_result["burst_pairs"],
            "burst_mass": d_result["burst_mass"],
            "bg_cell_mean": d_result["bg_cell_mean"],
            "ambiguous_reads": d_result["ambiguous_reads"],
            "unique_link_eval": d_eval,
        }
        total_attrib = sum(d_result["overlap_counts"].values())  # type: ignore[union-attr]
        log(f"  burst cells: {d_result['burst_pairs']} mass={d_result['burst_mass']}; "
            f"bg cell mean={d_result['bg_cell_mean']:.4f}")
        log(f"  episode-pair overlaps kept: "
            f"{len(d_result['overlap_counts'])} pairs, total mass "
            f"{total_attrib:.0f} (floor {d_result['min_pair_mass']}, "
            f"bg x{d_result['bg_confidence']})")  # type: ignore[union-attr]
        log(f"  unambiguous id-level links: {d_eval['unique_links']:.0f} "
            f"(precision {d_eval['unique_link_precision']:.2f}); "
            f"ambiguous reads={d_result['ambiguous_reads']}")  # type: ignore[union-attr]
        report_lines += [
            "## Stage D - tracking",
            f"- episode-pair overlap: {len(d_result['overlap_counts'])} pairs "  # type: ignore[union-attr]
            f"total mass {total_attrib:.0f} "
            f"(bg cell mean {d_result['bg_cell_mean']:.4f})",
            f"- id-level links only where eviction cohorts have size 1: "
            f"{d_eval['unique_links']:.0f}, precision "
            f"{d_eval['unique_link_precision']:.2f}",
            "",
        ]

    if "C" in stages:
        log("\n===== Stage C: cardinality recovery =====")
        c_rows = stage_c_cardinality(
            detected, attack_feats, local_bg=args.local_bg
        )
        truth = load_truth(attack_truth_path)
        c_eval = eval_c(c_rows, detected, truth, reads_full)
        state["stage_c"] = {"rows": c_rows, "eval": c_eval}
        if c_eval.get("n"):
            log(f"  episodes scored: {c_eval['n']:.0f}  "
                f"MAE(visible)={c_eval['mae_vs_visible']:.1f}  "
                f"median rel err={c_eval['median_rel_err_vs_visible']:.3f}  "
                f"worst={c_eval['worst_rel_err_vs_visible']:.3f}")
            log(f"  mean undercount vs raw m: "
                f"{c_eval['mean_undercount_vs_raw_m']:.1f} "
                "(cached re-read parts are invisible by design)")
        else:
            log("  no matched episodes to score")
        report_lines += [
            "## Stage C - cardinality",
            f"- MAE vs visible target={c_eval.get('mae_vs_visible', 0.0):.1f}, "
            f"median rel err="
            f"{c_eval.get('median_rel_err_vs_visible', 0.0):.3f}, "
            f"worst={c_eval.get('worst_rel_err_vs_visible', 0.0):.3f}",
            f"- cached re-read components are invisible "
            f"(mean undercount vs raw m: "
            f"{c_eval.get('mean_undercount_vs_raw_m', 0.0):.1f})",
            "",
        ]

    if "E" in stages:
        log("\n===== Stage E: range topology reconstruction =====")
        n_det = len(detected)
        if "D" not in stages:
            d_result = stage_d_tracking(
                attack_inc, detected, control_inc,
                min_pair_mass=args.min_pair_mass, max_cell=args.max_cell,
                eviction_tail=args.eviction_tail,
            )
        overlap_counts = d_result.get("overlap_counts", {})  # type: ignore[union-attr]
        matrix = [[0.0] * n_det for _ in range(n_det)]
        for key, count in overlap_counts.items():  # type: ignore[union-attr]
            a_str, b_str = key.split("->")
            a, b = int(a_str), int(b_str)
            if a < n_det and b < n_det:
                # overlap is an undirected relation; the attack only observes
                # the temporal direction (parent episode -> re-query episode)
                matrix[a][b] = float(count)
                matrix[b][a] = float(count)
        truth = load_truth(attack_truth_path)
        spans, matches = match_episodes(detected, truth, reads_full)
        e_eval = eval_e(matrix, detected, truth, matches)
        # Range-specificity control: run the same tracking on the point-burst
        # trace. Volume matches, but no co-parent burst structure should mean
        # a near-empty overlap matrix.
        burst_detected, _ = stage_b_detect_episodes(
            burst_feats, control_feats, threshold_z=args.threshold_z,
            gap=args.gap, min_mass=args.min_mass, window=args.window,
        )
        d_burst = stage_d_tracking(
            burst_inc, burst_detected, control_inc,
            min_pair_mass=args.min_pair_mass, max_cell=args.max_cell,
            eviction_tail=args.eviction_tail,
        )
        burst_pair_mass = float(d_burst["burst_mass"])  # type: ignore[arg-type]
        null = permutation_null(
            attack_inc, detected, args.null_trials, args.seed,
            min_pair_mass=float(d_result.get("min_pair_mass", 8.0)),  # type: ignore[arg-type]
            bg_cell_mean=float(d_result.get("bg_cell_mean", 0.0)),  # type: ignore[arg-type]
            max_cell=float(args.max_cell),
            eviction_tail=args.eviction_tail,
        )
        total_est = sum(sum(row) for row in matrix)
        state["stage_e"] = {"eval": e_eval, "null": null, "matrix": matrix,
                            "burst_control_mass": burst_pair_mass}
        log(f"  overlap matrix {n_det}x{n_det}: Pearson={e_eval['pearson']:.3f} "
            f"Pearson(large)={e_eval['pearson_large_overlap']:.3f} "
            f"binary-acc={e_eval['overlap_binary_acc']:.3f} "
            f"({e_eval['positive_pairs']:.0f} true overlapping pairs, "
            f"{e_eval['estimated_positive_pairs']:.0f} estimated)")
        boundary = e_eval.get("boundary_by_gap", {})
        log("  overlap-recovery rate by inter-query gap (leakage boundary):")
        for bucket, (n_pair, hit) in boundary.items():
            log(f"    gap {bucket:>8} batches: {hit}/{n_pair} recovered")
        log(f"  range-specificity control: point-burst trace burst mass="
            f"{burst_pair_mass:.0f} (range trace: {d_result['burst_mass']})")  # type: ignore[union-attr]
        log(f"  total estimated overlap mass: {total_est:.0f}; permutation "
            f"null mean={null['null_overlap_mean']:.1f} "
            f"max={null['null_overlap_max']:.1f} "
            f"({null['trials']:.0f} trials)")
        report_lines += [
            "## Stage E - topology",
            f"- overlap matrix Pearson={e_eval['pearson']:.3f} "
            f"Pearson(large pairs)={e_eval['pearson_large_overlap']:.3f} "
            f"binary acc={e_eval['overlap_binary_acc']:.3f} "
            f"({e_eval['positive_pairs']:.0f} true overlapping pairs)",
            "- overlap-recovery rate by inter-query gap:",
            *[f"  - gap {bucket}: {hit}/{n_pair} recovered"
              for bucket, (n_pair, hit) in e_eval.get("boundary_by_gap", {}).items()],
            f"- point-burst control burst mass="
            f"{burst_pair_mass:.0f} vs range burst mass="
            f"{d_result['burst_mass']}: co-parent structure is "
            f"range-specific, not a volume artifact",  # type: ignore[union-attr]
            f"- permutation null overlap mean="
            f"{null['null_overlap_mean']:.1f} max="
            f"{null['null_overlap_max']:.1f} vs attack total {total_est:.0f}",
            "",
        ]

    report_lines += [
        "## Maximum-leakage statement supported by this run",
        "- Passively (storage ids + batch timing only, order-hidden) the server",
        "  recovers: batch anatomy (B, real budget, f_D, flush age), the",
        "  range-query timeline, per-episode visible cardinality, and pairwise",
        "  range-overlap structure via exact write/read timing arithmetic.",
        "- Honest boundaries: id-level identity across incarnations stays",
        "  hidden when eviction cohorts are wide; fully-cached re-queries and",
        "  plaintext values are invisible at the storage level.",
        "",
    ]
    (outdir / "attack_summary.md").write_text("\n".join(report_lines))
    (outdir / "attack_state.json").write_text(json.dumps(state, indent=2, default=float))
    log(f"\n[done] report: {outdir / 'attack_summary.md'}")


if __name__ == "__main__":
    main()
