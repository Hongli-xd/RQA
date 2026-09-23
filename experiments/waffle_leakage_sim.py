#!/usr/bin/env python3
"""Design-level leakage experiments for the Waffle paper draft.

The script intentionally avoids third-party dependencies. It is not meant to be
a cycle-accurate implementation of the Waffle codebase; it models the protocol
features that matter for the current claims:

* a bounded cache at the proxy,
* batched reads of client misses plus fake real/dummy objects,
* fake real/dummy selection by least timestamp, and
* one server incarnation per object between a write and the next read.

The output separates two levels of evidence:

* a definition-level counterexample where marginal alpha/lifetime histograms
  are exactly identical but batch-joint structure differs; and
* a Waffle-style simulation comparing independent and grouped workloads with
  the same per-key marginal popularity distribution.
"""

from __future__ import annotations

import argparse
import bisect
import csv
import heapq
import json
import math
import random
from collections import Counter, OrderedDict
from dataclasses import dataclass
from pathlib import Path
from statistics import mean, pstdev
from typing import Iterable, Sequence


ROOT = Path(__file__).resolve().parents[1]
RESULTS_DIR = ROOT / "results"


def percentile(values: Sequence[float], q: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = min(len(ordered) - 1, max(0, round((len(ordered) - 1) * q)))
    return float(ordered[idx])


def tv_distance(left: Counter[int], right: Counter[int]) -> float:
    """Total variation distance between two integer histograms."""
    n_left = sum(left.values())
    n_right = sum(right.values())
    if n_left == 0 and n_right == 0:
        return 0.0
    keys = set(left) | set(right)
    total = 0.0
    for key in keys:
        total += abs(left[key] / n_left - right[key] / n_right)
    return 0.5 * total


def pair_count_within_window(values: Sequence[int], window: int = 0) -> int:
    if len(values) < 2:
        return 0
    counts = Counter(values)
    count = sum(pair_total(freq) for freq in counts.values())
    if window <= 0:
        return count
    ordered = sorted(counts)
    for i, value in enumerate(ordered):
        j = i + 1
        while j < len(ordered) and ordered[j] - value <= window:
            count += counts[value] * counts[ordered[j]]
            j += 1
    return count


def pair_total(n: int) -> int:
    return n * (n - 1) // 2


def same_value_pair_rate(values: Sequence[int], window: int = 0) -> float:
    pairs = pair_total(len(values))
    if pairs == 0:
        return 0.0
    same = pair_count_within_window(values, window)
    return same / pairs if pairs else 0.0


def marginal_null_stats(batches: Sequence[Sequence[int]], window: int = 0) -> dict[str, float]:
    """Compare observed batch-pair rate to a random-batching marginal null."""
    total_batch_pairs = sum(pair_total(len(batch)) for batch in batches)
    if total_batch_pairs == 0:
        return {
            "observed": 0.0,
            "null_mean": 0.0,
            "null_excess": 0.0,
            "null_z": 0.0,
            "null_p_upper": 1.0,
        }

    observed_pairs = sum(pair_count_within_window(batch, window) for batch in batches)
    observed = observed_pairs / total_batch_pairs
    flat = [value for batch in batches for value in batch]
    global_pairs = pair_total(len(flat))
    null_mean = (
        pair_count_within_window(flat, window) / global_pairs if global_pairs else 0.0
    )

    variance = null_mean * (1.0 - null_mean) / total_batch_pairs
    if variance <= 0.0:
        z = 0.0
        p_upper = 1.0 if observed <= null_mean else 0.0
    else:
        z = (observed - null_mean) / math.sqrt(variance)
        p_upper = 0.5 * math.erfc(z / math.sqrt(2.0))

    return {
        "observed": observed,
        "null_mean": null_mean,
        "null_excess": observed - null_mean,
        "null_z": z,
        "null_p_upper": p_upper,
    }


def variance(values: Sequence[int]) -> float:
    if len(values) < 2:
        return 0.0
    avg = sum(values) / len(values)
    return sum((value - avg) ** 2 for value in values) / len(values)


class WeightedSampler:
    def __init__(self, weights: Sequence[float], rng: random.Random) -> None:
        total = float(sum(weights))
        if total <= 0:
            raise ValueError("weights must have positive sum")
        running = 0.0
        self.cdf: list[float] = []
        for weight in weights:
            running += weight / total
            self.cdf.append(running)
        self.cdf[-1] = 1.0
        self.rng = rng

    def sample(self) -> int:
        return bisect.bisect_left(self.cdf, self.rng.random())


def zipf_weights(n: int, exponent: float) -> list[float]:
    return [1.0 / ((i + 1) ** exponent) for i in range(n)]


class IndependentWorkload:
    def __init__(self, weights: Sequence[float], batch_requests: int, rng: random.Random) -> None:
        self.sampler = WeightedSampler(weights, rng)
        self.batch_requests = batch_requests

    def next_batch(self) -> list[int]:
        return [self.sampler.sample() for _ in range(self.batch_requests)]


class GroupedWorkload:
    def __init__(
        self,
        n_keys: int,
        group_size: int,
        group_weights: Sequence[float],
        batch_requests: int,
        rng: random.Random,
    ) -> None:
        if n_keys % group_size != 0:
            raise ValueError("n_keys must be divisible by group_size")
        self.group_size = group_size
        self.batch_requests = batch_requests
        self.sampler = WeightedSampler(group_weights, rng)

    def next_batch(self) -> list[int]:
        keys: list[int] = []
        while len(keys) < self.batch_requests:
            group = self.sampler.sample()
            start = group * self.group_size
            keys.extend(range(start, start + self.group_size))
        return keys[: self.batch_requests]


def grouped_marginal_weights(n_keys: int, group_size: int, group_weights: Sequence[float]) -> list[float]:
    weights = [0.0] * n_keys
    for group, group_weight in enumerate(group_weights):
        start = group * group_size
        per_key = group_weight / group_size
        for key in range(start, start + group_size):
            weights[key] = per_key
    return weights


@dataclass(frozen=True)
class WaffleConfig:
    n_real: int = 4096
    n_dummy: int = 2048
    batch_size: int = 128
    client_requests: int = 64
    dummy_reads: int = 16
    cache_size: int = 512
    rounds: int = 5000
    group_size: int = 8
    group_zipf: float = 0.9
    write_window: int = 1
    refresh_cache_hits: bool = True
    dummy_policy: str = "paper_reset"

    @property
    def real_reads_per_batch(self) -> int:
        return self.batch_size - self.dummy_reads


class PaperDummySelector:
    """Paper-level dummy lifecycle.

    Dummies are persistent server objects. A fake-dummy read chooses a dummy
    with the least timestamp, updates it to the current batch timestamp, and
    writes it back under a fresh storage incarnation. After all dummy objects
    have been consumed in an epoch, the next epoch receives fresh random
    tie-priorities.
    """

    def __init__(self, n_dummy: int, rng: random.Random) -> None:
        self.n_dummy = n_dummy
        self.rng = rng
        self.timestamps = [0] * n_dummy
        self.priorities = [self.rng.random() for _ in range(n_dummy)]
        self.heap: list[tuple[int, float, int]] = []
        self.seen_this_epoch: set[int] = set()
        self.reset_count = 0
        self._rebuild_heap()

    def _rebuild_heap(self) -> None:
        self.heap = [
            (self.timestamps[key], self.priorities[key], key)
            for key in range(self.n_dummy)
        ]
        heapq.heapify(self.heap)

    def _reset_epoch(self, current_ts: int) -> None:
        self.timestamps = [current_ts] * self.n_dummy
        self.priorities = [self.rng.random() for _ in range(self.n_dummy)]
        self.seen_this_epoch.clear()
        self.reset_count += 1
        self._rebuild_heap()

    def take(self, count: int, current_ts: int) -> tuple[list[int], int]:
        selected: list[int] = []
        selected_set: set[int] = set()
        resets = 0
        while len(selected) < count:
            if len(self.seen_this_epoch) == self.n_dummy:
                self._reset_epoch(current_ts)
                resets += 1
            while True:
                ts, priority, key = heapq.heappop(self.heap)
                if (
                    key not in selected_set
                    and ts == self.timestamps[key]
                    and priority == self.priorities[key]
                ):
                    break
            selected.append(key)
            selected_set.add(key)
            self.seen_this_epoch.add(key)
            self.timestamps[key] = current_ts
            self.priorities[key] = self.rng.random()
            heapq.heappush(self.heap, (self.timestamps[key], self.priorities[key], key))
        return selected, resets


class WaffleSim:
    def __init__(
        self,
        cfg: WaffleConfig,
        workload: IndependentWorkload | GroupedWorkload,
        seed: int,
        trace_prefix: str | None = None,
    ) -> None:
        if cfg.client_requests > cfg.real_reads_per_batch:
            raise ValueError("client_requests must be <= batch_size - dummy_reads")
        if cfg.cache_size < cfg.real_reads_per_batch + cfg.client_requests:
            raise ValueError("cache_size should satisfy Waffle's meaningful minimum")
        if cfg.cache_size > cfg.n_real:
            raise ValueError("cache_size cannot exceed n_real")
        if cfg.dummy_policy not in {"paper_reset", "least_timestamp_no_reset", "random_dummy"}:
            raise ValueError(f"unknown dummy policy: {cfg.dummy_policy}")
        self.cfg = cfg
        self.workload = workload
        self.rng = random.Random(seed)
        self.time = 0
        self.trace_prefix = trace_prefix
        self.trace_rows: list[dict[str, object]] = []
        self.storage_counter = 0

        initial_cache_keys = self.rng.sample(range(cfg.n_real), cfg.cache_size)
        initial_cache = set(initial_cache_keys)
        self.cache: OrderedDict[int, None] = OrderedDict((key, None) for key in initial_cache_keys)

        self.ts_real = [0] * cfg.n_real
        self.ts_dummy = [0] * cfg.n_dummy
        self.last_write_real: list[int | None] = [None if key in initial_cache else 0 for key in range(cfg.n_real)]
        self.last_write_dummy: list[int | None] = [0 for _ in range(cfg.n_dummy)]
        self.storage_real: list[str | None] = [None for _key in range(cfg.n_real)]
        self.storage_dummy: list[str | None] = [None for _key in range(cfg.n_dummy)]

        self.real_heap: list[tuple[int, float, int]] = []
        self.dummy_heap: list[tuple[int, float, int]] = []
        for key in range(cfg.n_real):
            heapq.heappush(self.real_heap, (self.ts_real[key], self.rng.random(), key))
            if key not in initial_cache:
                self._write_real_trace(key, 0, -1, 0, "initial_real")
        for key in range(cfg.n_dummy):
            heapq.heappush(self.dummy_heap, (self.ts_dummy[key], self.rng.random(), key))
            self._write_dummy_trace(key, 0, -1, 0, "initial_dummy")
        self.paper_dummy = PaperDummySelector(cfg.n_dummy, self.rng)
        self.dummy_resets = 0

        self.alpha_values: list[int] = []
        self.real_alpha_values: list[int] = []
        self.dummy_alpha_values: list[int] = []
        self.batch_mean_lifetime: list[float] = []
        self.batch_lifetime_variance: list[float] = []
        self.batch_same_write_rate: list[float] = []
        self.batch_same_lifetime_rate: list[float] = []
        self.batch_lifetimes: list[list[int]] = []
        self.batch_write_times: list[list[int]] = []
        self.client_batch_lifetimes: list[list[int]] = []
        self.client_batch_write_times: list[list[int]] = []
        self.client_batch_lifetime_variance: list[float] = []
        self.client_batch_same_write_rate: list[float] = []
        self.client_batch_same_lifetime_rate: list[float] = []
        self.cache_misses: list[int] = []

    def _next_storage_key(self, kind: str, key: int) -> str:
        self.storage_counter += 1
        prefix = self.trace_prefix or "waffle_sim"
        return f"{prefix}/{kind}/{key}/{self.storage_counter}"

    def _trace_row(
        self,
        batch_ts: int,
        aggregate_batch_id: int,
        index: int,
        role: str,
        direction: str,
        storage_key: str,
        logical_key: str,
        logical_op: str,
        read_count: int,
        fake_real_count: int,
        dummy_count: int,
        cache_misses: int,
    ) -> None:
        if self.trace_prefix is None:
            return
        self.trace_rows.append(
            {
                "event": "storage_access",
                "batch_ts": batch_ts,
                "worker_id": 0,
                "aggregate_batch_id": aggregate_batch_id,
                "index": index,
                "role": role,
                "direction": direction,
                "storage_key": storage_key,
                "logical_key": logical_key,
                "logical_op": logical_op,
                "read_count": read_count,
                "fake_real_count": fake_real_count,
                "dummy_count": dummy_count,
                "cache_misses": cache_misses,
            }
        )

    def _write_real_trace(
        self,
        key: int,
        batch_ts: int,
        aggregate_batch_id: int,
        index: int,
        role: str = "evicted_real",
    ) -> None:
        storage_key = self._next_storage_key("real", key)
        self.storage_real[key] = storage_key
        self._trace_row(
            batch_ts,
            aggregate_batch_id,
            index,
            role,
            "write",
            storage_key,
            f"real/{key}",
            "putback",
            self.cfg.batch_size,
            0,
            self.cfg.dummy_reads,
            0,
        )

    def _write_dummy_trace(
        self,
        key: int,
        batch_ts: int,
        aggregate_batch_id: int,
        index: int,
        role: str = "evicted_dummy",
    ) -> None:
        storage_key = self._next_storage_key("dummy", key)
        self.storage_dummy[key] = storage_key
        self._trace_row(
            batch_ts,
            aggregate_batch_id,
            index,
            role,
            "write",
            storage_key,
            f"dummy/{key}",
            "putback",
            self.cfg.batch_size,
            0,
            self.cfg.dummy_reads,
            0,
        )

    def _touch_cache(self, key: int) -> None:
        self.cache.move_to_end(key)

    def _select_fake_real(self, excluded: set[int]) -> int:
        deferred: list[tuple[int, float, int]] = []
        while True:
            ts, _, key = heapq.heappop(self.real_heap)
            if ts == self.ts_real[key] and key not in self.cache and key not in excluded:
                for item in deferred:
                    heapq.heappush(self.real_heap, item)
                return key
            if ts == self.ts_real[key]:
                deferred.append((ts, _, key))

    def _select_dummy(self, excluded: set[int]) -> int:
        while True:
            ts, _, key = heapq.heappop(self.dummy_heap)
            if ts == self.ts_dummy[key] and key not in excluded:
                return key

    def _select_dummies(self, count: int) -> list[int]:
        if self.cfg.dummy_policy == "paper_reset":
            selected, resets = self.paper_dummy.take(count, self.time)
            self.dummy_resets += resets
            return selected
        if self.cfg.dummy_policy == "random_dummy":
            return self.rng.sample(range(self.cfg.n_dummy), count)

        selected: list[int] = []
        dummy_set: set[int] = set()
        for _dummy in range(count):
            key = self._select_dummy(dummy_set)
            dummy_set.add(key)
            selected.append(key)
        return selected

    def _set_real_timestamp(self, key: int) -> None:
        self.ts_real[key] = self.time
        heapq.heappush(self.real_heap, (self.ts_real[key], self.rng.random(), key))

    def _set_dummy_timestamp(self, key: int) -> None:
        self.ts_dummy[key] = self.time
        heapq.heappush(self.dummy_heap, (self.ts_dummy[key], self.rng.random(), key))

    def _read_real(
        self,
        key: int,
        role: str,
        aggregate_batch_id: int,
        index: int,
        read_count: int,
        fake_real_count: int,
        cache_misses: int,
    ) -> tuple[int, int]:
        write_time = self.last_write_real[key]
        if write_time is None:
            raise RuntimeError(f"real key {key} was selected while cached")
        lifetime = self.time - write_time
        self.alpha_values.append(lifetime)
        self.real_alpha_values.append(lifetime)
        self.last_write_real[key] = None
        storage_key = self.storage_real[key]
        if storage_key is None:
            raise RuntimeError(f"real key {key} has no storage incarnation")
        self._trace_row(
            self.time,
            aggregate_batch_id,
            index,
            role,
            "read",
            storage_key,
            f"real/{key}",
            "get",
            read_count,
            fake_real_count,
            self.cfg.dummy_reads,
            cache_misses,
        )
        self.storage_real[key] = None
        return lifetime, write_time

    def _read_dummy(
        self,
        key: int,
        aggregate_batch_id: int,
        index: int,
        read_count: int,
        fake_real_count: int,
        cache_misses: int,
    ) -> tuple[int, int]:
        write_time = self.last_write_dummy[key]
        if write_time is None:
            raise RuntimeError(f"dummy key {key} has no server incarnation")
        lifetime = self.time - write_time
        self.alpha_values.append(lifetime)
        self.dummy_alpha_values.append(lifetime)
        storage_key = self.storage_dummy[key]
        if storage_key is None:
            raise RuntimeError(f"dummy key {key} has no storage incarnation")
        self._trace_row(
            self.time,
            aggregate_batch_id,
            index,
            "fake_dummy",
            "read",
            storage_key,
            f"dummy/{key}",
            "get",
            read_count,
            fake_real_count,
            self.cfg.dummy_reads,
            cache_misses,
        )
        self.storage_dummy[key] = None
        return lifetime, write_time

    def _evict_and_cache(self, key: int) -> None:
        if key in self.cache:
            self._touch_cache(key)
            return
        if len(self.cache) >= self.cfg.cache_size:
            evicted, _ = self.cache.popitem(last=False)
            self.last_write_real[evicted] = self.time
            self._write_real_trace(evicted, self.time, -1, 0)
        self.cache[key] = None

    def run(self) -> dict[str, float | int | list[float]]:
        for _ in range(self.cfg.rounds):
            self.time += 1
            requests = self.workload.next_batch()

            misses: list[int] = []
            dedup_misses: set[int] = set()
            for key in requests:
                if key in self.cache:
                    if self.cfg.refresh_cache_hits:
                        self._touch_cache(key)
                elif key not in dedup_misses:
                    dedup_misses.add(key)
                    misses.append(key)

            selected_real = list(misses)
            selected_real_roles = ["client_real"] * len(selected_real)
            selected_set = set(selected_real)

            for key in misses:
                self._set_real_timestamp(key)

            fake_real_count = self.cfg.real_reads_per_batch - len(selected_real)
            if fake_real_count < 0:
                raise RuntimeError("deduplicated cache misses exceeded real read budget")
            for _fake in range(fake_real_count):
                key = self._select_fake_real(selected_set)
                selected_set.add(key)
                selected_real.append(key)
                selected_real_roles.append("fake_real")
                self._set_real_timestamp(key)

            selected_dummy = self._select_dummies(self.cfg.dummy_reads)
            if len(set(selected_dummy)) != len(selected_dummy):
                raise RuntimeError("dummy selector returned duplicate dummy objects within a batch")
            for key in selected_dummy:
                self._set_dummy_timestamp(key)

            batch_lifetimes: list[int] = []
            batch_write_times: list[int] = []
            client_lifetimes: list[int] = []
            client_write_times: list[int] = []

            read_count = len(selected_real) + len(selected_dummy)
            aggregate_batch_id = self.time
            for index, (key, role) in enumerate(zip(selected_real, selected_real_roles)):
                lifetime, write_time = self._read_real(
                    key,
                    role,
                    aggregate_batch_id,
                    index,
                    read_count,
                    fake_real_count,
                    len(misses),
                )
                batch_lifetimes.append(lifetime)
                batch_write_times.append(write_time)
                if role == "client_real":
                    client_lifetimes.append(lifetime)
                    client_write_times.append(write_time)

            for dummy_index, key in enumerate(selected_dummy, start=len(selected_real)):
                lifetime, write_time = self._read_dummy(
                    key,
                    aggregate_batch_id,
                    dummy_index,
                    read_count,
                    fake_real_count,
                    len(misses),
                )
                batch_lifetimes.append(lifetime)
                batch_write_times.append(write_time)
                self.last_write_dummy[key] = self.time
                self._write_dummy_trace(key, self.time, -1, dummy_index)

            for key in selected_real:
                self._evict_and_cache(key)

            self.cache_misses.append(len(misses))
            self.batch_mean_lifetime.append(mean(batch_lifetimes))
            self.batch_lifetime_variance.append(variance(batch_lifetimes))
            self.batch_same_write_rate.append(same_value_pair_rate(batch_write_times, self.cfg.write_window))
            self.batch_same_lifetime_rate.append(same_value_pair_rate(batch_lifetimes, 0))
            self.batch_lifetimes.append(batch_lifetimes)
            self.batch_write_times.append(batch_write_times)
            self.client_batch_lifetimes.append(client_lifetimes)
            self.client_batch_write_times.append(client_write_times)
            self.client_batch_lifetime_variance.append(variance(client_lifetimes))
            self.client_batch_same_write_rate.append(
                same_value_pair_rate(client_write_times, self.cfg.write_window)
            )
            self.client_batch_same_lifetime_rate.append(same_value_pair_rate(client_lifetimes, 0))

        alpha_hist = Counter(self.alpha_values)
        same_write_null = marginal_null_stats(self.batch_write_times, self.cfg.write_window)
        same_lifetime_null = marginal_null_stats(self.batch_lifetimes, 0)
        return {
            "alpha_count": len(self.alpha_values),
            "alpha_mean": mean(self.alpha_values),
            "alpha_p50": percentile(self.alpha_values, 0.50),
            "alpha_p95": percentile(self.alpha_values, 0.95),
            "alpha_p99": percentile(self.alpha_values, 0.99),
            "alpha_max": max(self.alpha_values),
            "real_alpha_mean": mean(self.real_alpha_values),
            "dummy_alpha_mean": mean(self.dummy_alpha_values),
            "misses_per_batch": mean(self.cache_misses),
            "dummy_resets": self.dummy_resets,
            "batch_lifetime_variance": mean(self.batch_lifetime_variance),
            "batch_same_write_rate": mean(self.batch_same_write_rate),
            "batch_same_lifetime_rate": mean(self.batch_same_lifetime_rate),
            "client_batch_lifetime_variance": mean(self.client_batch_lifetime_variance),
            "client_batch_same_write_rate": mean(self.client_batch_same_write_rate),
            "client_batch_same_lifetime_rate": mean(self.client_batch_same_lifetime_rate),
            "batch_same_write_null_mean": same_write_null["null_mean"],
            "batch_same_write_null_excess": same_write_null["null_excess"],
            "batch_same_write_null_z": same_write_null["null_z"],
            "batch_same_write_null_p_upper": same_write_null["null_p_upper"],
            "batch_same_lifetime_null_mean": same_lifetime_null["null_mean"],
            "batch_same_lifetime_null_excess": same_lifetime_null["null_excess"],
            "batch_same_lifetime_null_z": same_lifetime_null["null_z"],
            "batch_same_lifetime_null_p_upper": same_lifetime_null["null_p_upper"],
            "alpha_hist": dict(alpha_hist),
        }

    def write_trace_tsv(self, path: Path) -> None:
        fields = [
            "event",
            "batch_ts",
            "worker_id",
            "aggregate_batch_id",
            "index",
            "role",
            "direction",
            "storage_key",
            "logical_key",
            "logical_op",
            "read_count",
            "fake_real_count",
            "dummy_count",
            "cache_misses",
        ]
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="") as handle:
            writer = csv.DictWriter(handle, fieldnames=fields, delimiter="\t", lineterminator="\n")
            writer.writeheader()
            writer.writerows(
                sorted(
                    self.trace_rows,
                    key=lambda row: (
                        int(row["batch_ts"]),
                        int(row["worker_id"]),
                        str(row["direction"]) != "write",
                        int(row["index"]),
                    ),
                )
            )


def run_counterexample(batch_size: int = 64, batches: int = 2000, short: int = 4, long: int = 64) -> dict[str, float]:
    clustered: list[list[int]] = []
    mixed: list[list[int]] = []
    for batch in range(batches):
        if batch % 2 == 0:
            clustered.append([short] * batch_size)
        else:
            clustered.append([long] * batch_size)
        mixed.append([short] * (batch_size // 2) + [long] * (batch_size - batch_size // 2))

    clustered_hist = Counter(value for batch in clustered for value in batch)
    mixed_hist = Counter(value for batch in mixed for value in batch)

    return {
        "marginal_tv": tv_distance(clustered_hist, mixed_hist),
        "clustered_alpha_max": max(clustered_hist),
        "mixed_alpha_max": max(mixed_hist),
        "clustered_same_lifetime_pair_rate": mean(same_value_pair_rate(batch, 0) for batch in clustered),
        "mixed_same_lifetime_pair_rate": mean(same_value_pair_rate(batch, 0) for batch in mixed),
        "clustered_batch_variance": mean(variance(batch) for batch in clustered),
        "mixed_batch_variance": mean(variance(batch) for batch in mixed),
    }


def build_workloads(cfg: WaffleConfig, seed: int) -> tuple[IndependentWorkload, GroupedWorkload]:
    groups = cfg.n_real // cfg.group_size
    group_weights = zipf_weights(groups, cfg.group_zipf)
    marginal_weights = grouped_marginal_weights(cfg.n_real, cfg.group_size, group_weights)
    independent = IndependentWorkload(marginal_weights, cfg.client_requests, random.Random(seed * 2 + 1))
    grouped = GroupedWorkload(
        cfg.n_real,
        cfg.group_size,
        group_weights,
        cfg.client_requests,
        random.Random(seed * 2 + 2),
    )
    return independent, grouped


def run_waffle_pair(cfg: WaffleConfig, seed: int) -> dict[str, object]:
    independent_workload, grouped_workload = build_workloads(cfg, seed)
    independent = WaffleSim(cfg, independent_workload, seed=seed * 10 + 1).run()
    grouped = WaffleSim(cfg, grouped_workload, seed=seed * 10 + 2).run()

    independent_hist = Counter({int(k): int(v) for k, v in independent["alpha_hist"].items()})
    grouped_hist = Counter({int(k): int(v) for k, v in grouped["alpha_hist"].items()})
    alpha_tv = tv_distance(independent_hist, grouped_hist)

    row: dict[str, object] = {
        "seed": seed,
        "alpha_tv": alpha_tv,
    }
    for prefix, result in (("independent", independent), ("grouped", grouped)):
        for key, value in result.items():
            if key == "alpha_hist":
                continue
            row[f"{prefix}_{key}"] = value
    for metric in ("batch_same_write", "batch_same_lifetime"):
        row[f"{metric}_null_excess_gap"] = (
            float(grouped[f"{metric}_null_excess"])
            - float(independent[f"{metric}_null_excess"])
        )
    return row


def summarize_rows(rows: Sequence[dict[str, object]]) -> dict[str, float]:
    numeric_keys = [key for key in rows[0] if key != "seed"]
    summary: dict[str, float] = {}
    for key in numeric_keys:
        values = [float(row[key]) for row in rows]
        summary[f"{key}_mean"] = mean(values)
        summary[f"{key}_std"] = pstdev(values) if len(values) > 1 else 0.0
    return summary


def cohen_d(left: Sequence[float], right: Sequence[float]) -> float:
    if len(left) < 2 or len(right) < 2:
        return 0.0
    left_std = pstdev(left)
    right_std = pstdev(right)
    pooled = math.sqrt((left_std**2 + right_std**2) / 2)
    if pooled == 0:
        return 0.0
    return (mean(right) - mean(left)) / pooled


def threshold_accuracy(independent_scores: Sequence[float], grouped_scores: Sequence[float]) -> float:
    """Accuracy of a one-dimensional threshold distinguisher.

    The threshold is selected from the two class means. This is intentionally
    simple: it measures whether a paper-friendly joint statistic separates the
    two workloads, not how well a tuned classifier can overfit the simulator.
    """
    if not independent_scores or not grouped_scores:
        return 0.0
    mean_ind = mean(independent_scores)
    mean_grp = mean(grouped_scores)
    threshold = (mean_ind + mean_grp) / 2
    grouped_is_high = mean_grp >= mean_ind
    correct = 0
    total = len(independent_scores) + len(grouped_scores)
    for score in independent_scores:
        correct += (score < threshold) if grouped_is_high else (score > threshold)
    for score in grouped_scores:
        correct += (score >= threshold) if grouped_is_high else (score <= threshold)
    return correct / total


def run_sweep(
    base_cfg: WaffleConfig,
    seeds: int,
    group_sizes: Sequence[int],
    zipfs: Sequence[float],
    cache_sizes: Sequence[int],
) -> list[dict[str, object]]:
    sweep_rows: list[dict[str, object]] = []
    for cache_size in cache_sizes:
        for group_size in group_sizes:
            if base_cfg.n_real % group_size != 0:
                continue
            for group_zipf in zipfs:
                cfg = WaffleConfig(
                    n_real=base_cfg.n_real,
                    n_dummy=base_cfg.n_dummy,
                    batch_size=base_cfg.batch_size,
                    client_requests=base_cfg.client_requests,
                    dummy_reads=base_cfg.dummy_reads,
                    cache_size=cache_size,
                    rounds=base_cfg.rounds,
                    group_size=group_size,
                        group_zipf=group_zipf,
                        write_window=base_cfg.write_window,
                        refresh_cache_hits=base_cfg.refresh_cache_hits,
                        dummy_policy=base_cfg.dummy_policy,
                    )
                rows = [run_waffle_pair(cfg, seed) for seed in range(seeds)]
                summary = summarize_rows(rows)
                independent_write_scores = [
                    float(row["independent_batch_same_write_rate"]) for row in rows
                ]
                grouped_write_scores = [
                    float(row["grouped_batch_same_write_rate"]) for row in rows
                ]
                independent_lifetime_scores = [
                    float(row["independent_batch_same_lifetime_rate"]) for row in rows
                ]
                grouped_lifetime_scores = [
                    float(row["grouped_batch_same_lifetime_rate"]) for row in rows
                ]
                sweep_rows.append(
                    {
                        "n_real": cfg.n_real,
                        "n_dummy": cfg.n_dummy,
                        "batch_size": cfg.batch_size,
                        "client_requests": cfg.client_requests,
                        "dummy_reads": cfg.dummy_reads,
                        "cache_size": cfg.cache_size,
                        "rounds": cfg.rounds,
                        "seeds": seeds,
                        "group_size": cfg.group_size,
                        "group_zipf": cfg.group_zipf,
                        "refresh_cache_hits": cfg.refresh_cache_hits,
                        "dummy_policy": cfg.dummy_policy,
                        "alpha_tv_mean": summary["alpha_tv_mean"],
                        "alpha_tv_std": summary["alpha_tv_std"],
                        "alpha_mean_gap": summary["grouped_alpha_mean_mean"]
                        - summary["independent_alpha_mean_mean"],
                        "misses_gap": summary["grouped_misses_per_batch_mean"]
                        - summary["independent_misses_per_batch_mean"],
                        "same_write_independent": summary[
                            "independent_batch_same_write_rate_mean"
                        ],
                        "same_write_grouped": summary["grouped_batch_same_write_rate_mean"],
                        "same_write_gap": summary["grouped_batch_same_write_rate_mean"]
                        - summary["independent_batch_same_write_rate_mean"],
                        "same_write_null_excess_gap": summary[
                            "grouped_batch_same_write_null_excess_mean"
                        ]
                        - summary["independent_batch_same_write_null_excess_mean"],
                        "same_write_grouped_null_p_upper": summary[
                            "grouped_batch_same_write_null_p_upper_mean"
                        ],
                        "same_write_effect_size": cohen_d(
                            independent_write_scores, grouped_write_scores
                        ),
                        "same_write_threshold_accuracy": threshold_accuracy(
                            independent_write_scores, grouped_write_scores
                        ),
                        "same_lifetime_independent": summary[
                            "independent_batch_same_lifetime_rate_mean"
                        ],
                        "same_lifetime_grouped": summary[
                            "grouped_batch_same_lifetime_rate_mean"
                        ],
                        "same_lifetime_gap": summary[
                            "grouped_batch_same_lifetime_rate_mean"
                        ]
                        - summary["independent_batch_same_lifetime_rate_mean"],
                        "same_lifetime_null_excess_gap": summary[
                            "grouped_batch_same_lifetime_null_excess_mean"
                        ]
                        - summary["independent_batch_same_lifetime_null_excess_mean"],
                        "same_lifetime_grouped_null_p_upper": summary[
                            "grouped_batch_same_lifetime_null_p_upper_mean"
                        ],
                        "same_lifetime_effect_size": cohen_d(
                            independent_lifetime_scores, grouped_lifetime_scores
                        ),
                        "same_lifetime_threshold_accuracy": threshold_accuracy(
                            independent_lifetime_scores, grouped_lifetime_scores
                        ),
                    }
                )
    return sweep_rows


def write_csv(path: Path, rows: Sequence[dict[str, object]]) -> None:
    with path.open("w", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0].keys()), lineterminator="\n")
        writer.writeheader()
        for row in rows:
            writer.writerow(row)


def markdown_table(rows: Iterable[Sequence[object]]) -> str:
    rows = list(rows)
    header = rows[0]
    sep = ["---"] * len(header)
    out = ["| " + " | ".join(str(cell) for cell in header) + " |"]
    out.append("| " + " | ".join(sep) + " |")
    for row in rows[1:]:
        out.append("| " + " | ".join(str(cell) for cell in row) + " |")
    return "\n".join(out)


def write_summary(path: Path, cfg: WaffleConfig, counterexample: dict[str, float], rows: Sequence[dict[str, object]]) -> None:
    summary = summarize_rows(rows)

    def fmt(key: str) -> str:
        return f"{summary[key + '_mean']:.4f} +/- {summary[key + '_std']:.4f}"

    table = markdown_table(
        [
            ["metric", "independent", "grouped", "gap"],
            [
                "alpha mean",
                fmt("independent_alpha_mean"),
                fmt("grouped_alpha_mean"),
                f"{summary['grouped_alpha_mean_mean'] - summary['independent_alpha_mean_mean']:.4f}",
            ],
            [
                "alpha p95",
                fmt("independent_alpha_p95"),
                fmt("grouped_alpha_p95"),
                f"{summary['grouped_alpha_p95_mean'] - summary['independent_alpha_p95_mean']:.4f}",
            ],
            [
                "cache misses / batch",
                fmt("independent_misses_per_batch"),
                fmt("grouped_misses_per_batch"),
                f"{summary['grouped_misses_per_batch_mean'] - summary['independent_misses_per_batch_mean']:.4f}",
            ],
            [
                "batch lifetime variance",
                fmt("independent_batch_lifetime_variance"),
                fmt("grouped_batch_lifetime_variance"),
                f"{summary['grouped_batch_lifetime_variance_mean'] - summary['independent_batch_lifetime_variance_mean']:.4f}",
            ],
            [
                "same-write pair rate",
                fmt("independent_batch_same_write_rate"),
                fmt("grouped_batch_same_write_rate"),
                f"{summary['grouped_batch_same_write_rate_mean'] - summary['independent_batch_same_write_rate_mean']:.4f}",
            ],
            [
                "same-write null excess",
                fmt("independent_batch_same_write_null_excess"),
                fmt("grouped_batch_same_write_null_excess"),
                f"{summary['grouped_batch_same_write_null_excess_mean'] - summary['independent_batch_same_write_null_excess_mean']:.4f}",
            ],
            [
                "same-lifetime pair rate",
                fmt("independent_batch_same_lifetime_rate"),
                fmt("grouped_batch_same_lifetime_rate"),
                f"{summary['grouped_batch_same_lifetime_rate_mean'] - summary['independent_batch_same_lifetime_rate_mean']:.4f}",
            ],
            [
                "same-lifetime null excess",
                fmt("independent_batch_same_lifetime_null_excess"),
                fmt("grouped_batch_same_lifetime_null_excess"),
                f"{summary['grouped_batch_same_lifetime_null_excess_mean'] - summary['independent_batch_same_lifetime_null_excess_mean']:.4f}",
            ],
            [
                "alpha TV distance",
                "-",
                "-",
                fmt("alpha_tv"),
            ],
        ]
    )

    text = f"""# Waffle leakage simulation summary

Configuration:

```json
{json.dumps(cfg.__dict__, indent=2, sort_keys=True)}
```

## Definition-level counterexample

The two traces below have exactly the same marginal lifetime histogram and the
same maximum alpha, but their batch-level joint structure is distinguishable.

```json
{json.dumps(counterexample, indent=2, sort_keys=True)}
```

Interpretation: an alpha histogram can be identical while the observer's
within-batch view is not. This supports the paper's claim that alpha/beta
uniformity is a marginal condition, not an access-sequence indistinguishability
definition.

## Waffle-style simulation

The grouped workload samples query groups from a Zipf distribution. The
independent workload samples individual keys from the exact per-key marginal
distribution induced by those groups, so any difference is due to grouping, not
to a different popularity vector.

{table}

The `null excess` rows subtract the exact pair rate expected if the observed
write times or lifetimes were randomly repartitioned into the same batch sizes.
They therefore test whether the batch boundaries carry joint information beyond
the marginal multiset alone.

Per-seed details are in `results/waffle_sim_rows.csv`.
"""
    path.write_text(text)


def write_sweep_summary(path: Path, sweep_rows: Sequence[dict[str, object]]) -> None:
    ranked = sorted(
        sweep_rows,
        key=lambda row: (
            float(row["same_write_threshold_accuracy"]),
            abs(float(row["same_write_effect_size"])),
            abs(float(row["same_write_gap"])),
        ),
        reverse=True,
    )
    top = ranked[:8]
    weak = list(reversed(ranked[-8:]))
    rows = [
        [
            "cache",
            "group",
            "zipf",
            "alpha TV",
            "write gap",
            "life-null gap",
            "write d",
            "write acc",
            "life gap",
            "life acc",
        ]
    ]
    for row in top:
        rows.append(
            [
                row["cache_size"],
                row["group_size"],
                row["group_zipf"],
                f"{float(row['alpha_tv_mean']):.3f}",
                f"{float(row['same_write_gap']):.4f}",
                f"{float(row['same_lifetime_null_excess_gap']):.4f}",
                f"{float(row['same_write_effect_size']):.2f}",
                f"{float(row['same_write_threshold_accuracy']):.2f}",
                f"{float(row['same_lifetime_gap']):.4f}",
                f"{float(row['same_lifetime_threshold_accuracy']):.2f}",
            ]
        )

    weak_rows = [
        [
            "cache",
            "group",
            "zipf",
            "alpha TV",
            "write gap",
            "life-null gap",
            "write d",
            "write acc",
            "life gap",
            "life acc",
        ]
    ]
    for row in weak:
        weak_rows.append(
            [
                row["cache_size"],
                row["group_size"],
                row["group_zipf"],
                f"{float(row['alpha_tv_mean']):.3f}",
                f"{float(row['same_write_gap']):.4f}",
                f"{float(row['same_lifetime_null_excess_gap']):.4f}",
                f"{float(row['same_write_effect_size']):.2f}",
                f"{float(row['same_write_threshold_accuracy']):.2f}",
                f"{float(row['same_lifetime_gap']):.4f}",
                f"{float(row['same_lifetime_threshold_accuracy']):.2f}",
            ]
        )

    aggregate_rows = [["slice", "avg write acc", "avg write gap", "avg life-null gap", "avg alpha TV"]]
    aggregate_rows.append(
        [
            "all",
            f"{mean(float(row['same_write_threshold_accuracy']) for row in sweep_rows):.2f}",
            f"{mean(float(row['same_write_gap']) for row in sweep_rows):.4f}",
            f"{mean(float(row['same_lifetime_null_excess_gap']) for row in sweep_rows):.4f}",
            f"{mean(float(row['alpha_tv_mean']) for row in sweep_rows):.3f}",
        ]
    )
    for key in ("group_size", "group_zipf", "cache_size"):
        values = sorted({row[key] for row in sweep_rows}, key=lambda value: float(value))
        for value in values:
            subset = [row for row in sweep_rows if row[key] == value]
            aggregate_rows.append(
                [
                    f"{key}={value}",
                    f"{mean(float(row['same_write_threshold_accuracy']) for row in subset):.2f}",
                    f"{mean(float(row['same_write_gap']) for row in subset):.4f}",
                    f"{mean(float(row['same_lifetime_null_excess_gap']) for row in subset):.4f}",
                    f"{mean(float(row['alpha_tv_mean']) for row in subset):.3f}",
                ]
            )

    best = top[0] if top else {}
    negative_gaps = sum(float(row["same_write_gap"]) < 0 for row in sweep_rows)
    perfect_acc = sum(float(row["same_write_threshold_accuracy"]) == 1.0 for row in sweep_rows)
    text = f"""# Waffle joint-leakage sweep

This sweep varies group size, group-skew, and cache size while keeping the
independent workload matched to the grouped workload's per-key marginal
distribution. The distinguisher is intentionally simple: classify a run as
grouped when its average same-write pair rate is above a threshold halfway
between the independent and grouped means. The life-null gap subtracts the
exact marginal-null same-lifetime excess of the independent baseline from that
of the grouped workload.

## Aggregate view

Across {len(sweep_rows)} configurations, {perfect_acc} have perfect
same-write-threshold separation under the current seed budget, and
{negative_gaps} have a negative same-write gap. Negative gaps are not a failure
of the marginal-vs-joint claim; they mean this particular one-dimensional score
is not monotone in every operating point.

{markdown_table(aggregate_rows)}

## Top configurations by same-write threshold accuracy

{markdown_table(rows)}

## Weakest configurations by same-write threshold accuracy

{markdown_table(weak_rows)}

## Notes

- Full rows are in `results/waffle_sweep_rows.csv`.
- The best observed configuration is:

```json
{json.dumps(best, indent=2, sort_keys=True)}
```
"""
    path.write_text(text)


def parse_int_list(value: str) -> list[int]:
    return [int(part.strip()) for part in value.split(",") if part.strip()]


def parse_float_list(value: str) -> list[float]:
    return [float(part.strip()) for part in value.split(",") if part.strip()]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["single", "sweep"], default="single")
    parser.add_argument("--rounds", type=int, default=5000)
    parser.add_argument("--seeds", type=int, default=5)
    parser.add_argument("--n-real", type=int, default=4096)
    parser.add_argument("--n-dummy", type=int, default=2048)
    parser.add_argument("--batch-size", type=int, default=128)
    parser.add_argument("--client-requests", type=int, default=64)
    parser.add_argument("--dummy-reads", type=int, default=16)
    parser.add_argument("--cache-size", type=int, default=512)
    parser.add_argument("--group-size", type=int, default=8)
    parser.add_argument("--group-zipf", type=float, default=0.9)
    parser.add_argument("--sweep-group-sizes", default="2,4,8,16")
    parser.add_argument("--sweep-zipfs", default="0.5,0.9,1.2")
    parser.add_argument("--sweep-cache-sizes", default="384,512,768")
    parser.add_argument("--dummy-policy", default="paper_reset")
    cache_hits = parser.add_mutually_exclusive_group()
    cache_hits.add_argument(
        "--refresh-cache-hits",
        dest="refresh_cache_hits",
        action="store_true",
        help="Move GET cache hits to the MRU position. This is the default paper-level mode.",
    )
    cache_hits.add_argument(
        "--no-refresh-cache-hits",
        dest="refresh_cache_hits",
        action="store_false",
        help="Do not refresh GET cache hits; implementation-like control for the inspected public code.",
    )
    parser.set_defaults(refresh_cache_hits=True)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    cfg = WaffleConfig(
        n_real=args.n_real,
        n_dummy=args.n_dummy,
        batch_size=args.batch_size,
        client_requests=args.client_requests,
        dummy_reads=args.dummy_reads,
        cache_size=args.cache_size,
        rounds=args.rounds,
        group_size=args.group_size,
        group_zipf=args.group_zipf,
        refresh_cache_hits=args.refresh_cache_hits,
        dummy_policy=args.dummy_policy,
    )

    RESULTS_DIR.mkdir(exist_ok=True)
    counterexample = run_counterexample()
    if args.mode == "single":
        rows = [run_waffle_pair(cfg, seed) for seed in range(args.seeds)]
        write_csv(RESULTS_DIR / "waffle_sim_rows.csv", rows)
        write_summary(RESULTS_DIR / "waffle_sim_summary.md", cfg, counterexample, rows)
        print((RESULTS_DIR / "waffle_sim_summary.md").relative_to(ROOT))
    else:
        sweep_rows = run_sweep(
            cfg,
            args.seeds,
            parse_int_list(args.sweep_group_sizes),
            parse_float_list(args.sweep_zipfs),
            parse_int_list(args.sweep_cache_sizes),
        )
        write_csv(RESULTS_DIR / "waffle_sweep_rows.csv", sweep_rows)
        write_sweep_summary(RESULTS_DIR / "waffle_sweep_summary.md", sweep_rows)
        print((RESULTS_DIR / "waffle_sweep_summary.md").relative_to(ROOT))


if __name__ == "__main__":
    main()
