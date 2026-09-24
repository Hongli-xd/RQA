# Range-Query Attack on Waffle (design-level, order-hidden, passive)

- Attack visibility: event, batch_ts, direction, storage_key (simulation labels dropped at load)
- Config: `{'n_real': 8192, 'n_dummy': 2048, 'batch_size': 128, 'client_requests': 64, 'dummy_reads': 16, 'cache_size': 512, 'rounds': 900, 'group_size': 8, 'group_zipf': 0.9, 'write_window': 1, 'refresh_cache_hits': True, 'dummy_policy': 'paper_reset'}`
- Workload: background Zipf-0.9 point traffic + scheduled range episodes

## Stage A - batch anatomy
- B_hat=128.0 (truth 128); real budget=113.0 (truth 112); f_D_hat=15.0 (truth 16)
- flush age mode alpha=81 window=[80, 84] (fakes self-identify); f_R_mean=78.1; entangled=False

## Stage B - episode detection
- detected 19 episodes (truth 20.0): P=0.89 R=0.85 F1=0.87 IoU=0.44
- false-positive batches: 0

## Stage D - tracking
- episode-pair overlap: 36 pairs total mass 2010 (bg cell mean 0.0541)
- id-level links only where eviction cohorts have size 1: 0, precision 0.00

## Stage C - cardinality
- MAE vs visible target=23.0, median rel err=0.164, worst=0.446
- cached re-read components are invisible (mean undercount vs raw m: -24.3)

## Stage E - topology
- overlap matrix Pearson=0.584 Pearson(large pairs)=0.695 binary acc=0.941 (24 true overlapping pairs)
- overlap-recovery rate by inter-query gap:
  - gap 0-30: 2/2 recovered
  - gap 121-240: 0/3 recovered
  - gap 31-60: 5/5 recovered
  - gap 61-120: 0/2 recovered
- point-burst control burst mass=85 vs range burst mass=546: co-parent structure is range-specific, not a volume artifact
- permutation null overlap mean=96.0 max=178.0 vs attack total 4020

## Maximum-leakage statement supported by this run
- Passively (storage ids + batch timing only, order-hidden) the server
  recovers: batch anatomy (B, real budget, f_D, flush age), the
  range-query timeline, per-episode visible cardinality, and pairwise
  range-overlap structure via exact write/read timing arithmetic.
- Honest boundaries: id-level identity across incarnations stays
  hidden when eviction cohorts are wide; fully-cached re-queries and
  plaintext values are invisible at the storage level.
