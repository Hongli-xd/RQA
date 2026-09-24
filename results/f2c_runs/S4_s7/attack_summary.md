# Range-Query Attack on Waffle (design-level, order-hidden, passive)

- Attack visibility: event, batch_ts, direction, storage_key (simulation labels dropped at load)
- Config: `{'n_real': 100000, 'n_dummy': 70000, 'batch_size': 2500, 'client_requests': 1000, 'dummy_reads': 500, 'cache_size': 4000, 'rounds': 1800, 'group_size': 8, 'group_zipf': 0.9, 'write_window': 1, 'refresh_cache_hits': True, 'dummy_policy': 'paper_reset'}`
- Workload: background Zipf-0.9 point traffic + scheduled range episodes

## Stage A - batch anatomy
- B_hat=2500.0 (truth 2500); real budget=1997.0 (truth 2000); f_D_hat=503.0 (truth 500)
- flush age mode alpha=50 window=[49, 50] (fakes self-identify); f_R_mean=1716.6; entangled=False

## Maximum-leakage statement supported by this run
- Passively (storage ids + batch timing only, order-hidden) the server
  recovers: batch anatomy (B, real budget, f_D, flush age), the
  range-query timeline, per-episode visible cardinality, and pairwise
  range-overlap structure via exact write/read timing arithmetic.
- Honest boundaries: id-level identity across incarnations stays
  hidden when eviction cohorts are wide; fully-cached re-queries and
  plaintext values are invisible at the storage level.
