# Range-Query Attack on Waffle (design-level, order-hidden, passive)

- Attack visibility: event, batch_ts, direction, storage_key (simulation labels dropped at load)
- Config: `{'n_real': 8192, 'n_dummy': 2048, 'batch_size': 128, 'client_requests': 64, 'dummy_reads': 16, 'cache_size': 512, 'rounds': 4000, 'group_size': 8, 'group_zipf': 0.9, 'write_window': 1, 'refresh_cache_hits': True, 'dummy_policy': 'paper_reset'}`
- Workload: background Zipf-0.9 point traffic + scheduled range episodes

## Stage A - batch anatomy
- B_hat=128.0 (truth 128); real budget=114.0 (truth 112); f_D_hat=14.0 (truth 16)
- flush age mode alpha=81 window=[80, 83] (fakes self-identify); f_R_mean=79.7; entangled=False

## Stage B - episode detection
- detected 76 episodes (truth 80.0): P=0.91 R=0.86 F1=0.88 IoU=0.47
- false-positive batches: 0

## Stage C - cardinality
- MAE vs visible target=7.2, median rel err=0.048, worst=0.645
- cached re-read components are invisible (mean undercount vs raw m: -4.3)

## Maximum-leakage statement supported by this run
- Passively (storage ids + batch timing only, order-hidden) the server
  recovers: batch anatomy (B, real budget, f_D, flush age), the
  range-query timeline, per-episode visible cardinality, and pairwise
  range-overlap structure via exact write/read timing arithmetic.
- Honest boundaries: id-level identity across incarnations stays
  hidden when eviction cohorts are wide; fully-cached re-queries and
  plaintext values are invisible at the storage level.
