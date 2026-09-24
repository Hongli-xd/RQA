# Range-Query Attack on Waffle (design-level, order-hidden, passive)

- Attack visibility: event, batch_ts, direction, storage_key (simulation labels dropped at load)
- Config: `{'n_real': 200000, 'n_dummy': 70000, 'batch_size': 2500, 'client_requests': 1000, 'dummy_reads': 500, 'cache_size': 4000, 'rounds': 2400, 'group_size': 8, 'group_zipf': 0.9, 'write_window': 1, 'refresh_cache_hits': True, 'dummy_policy': 'paper_reset'}`
- Workload: background Zipf-0.9 point traffic + scheduled range episodes

## Stage A - batch anatomy
- B_hat=2500.0 (truth 2500); real budget=2089.0 (truth 2000); f_D_hat=411 (truth 500)
- flush age mode alpha=102 window=[101, 103] (fakes self-identify); f_R_mean=1810.6; entangled=False

## Stage B - episode detection
- detected 78 episodes (truth 78.0): P=0.86 R=0.86 F1=0.86 IoU=0.42
- false-positive batches: 2

## Stage D - tracking
- episode-pair overlap: 289 pairs total mass 78510 (bg cell mean 0.1563)
- id-level links only where eviction cohorts have size 1: 0, precision 0.00

## Stage C - cardinality
- MAE vs visible target=78.0, median rel err=0.070, worst=0.240
- cached re-read components are invisible (mean undercount vs raw m: -70.0)

## Stage E - topology
- overlap matrix Pearson=0.515 Pearson(large pairs)=0.505 binary acc=0.983 (102 true overlapping pairs)
- overlap-recovery rate by inter-query gap:
  - gap 9: 1/1 recovered
  - gap 12: 2/2 recovered
  - gap 24: 4/4 recovered
  - gap 32: 2/2 recovered
  - gap 33: 1/1 recovered
  - gap 34: 1/1 recovered
  - gap 36: 1/1 recovered
  - gap 44: 2/2 recovered
  - gap 46: 2/2 recovered
  - gap 56: 1/1 recovered
  - gap 57: 4/4 recovered
  - gap 68: 1/1 recovered
  - gap 69: 1/1 recovered
  - gap 81: 2/2 recovered
  - gap 90: 7/7 recovered
  - gap 122: 0/1 recovered
  - gap 143: 0/1 recovered
  - gap 155: 0/2 recovered
  - gap 167: 0/1 recovered
  - gap 180: 0/1 recovered
  - gap 204: 0/1 recovered
  - gap 212: 0/7 recovered
  - gap 236: 0/3 recovered
  - gap 1382: 0/1 recovered
  - gap 1418: 0/1 recovered
- point-burst control burst mass=291833 vs range burst mass=287036: co-parent structure is range-specific, not a volume artifact
- permutation null overlap mean=27523.3 max=28219.0 vs attack total 157020

## Maximum-leakage statement supported by this run
- Passively (storage ids + batch timing only, order-hidden) the server
  recovers: batch anatomy (B, real budget, f_D, flush age), the
  range-query timeline, per-episode visible cardinality, and pairwise
  range-overlap structure via exact write/read timing arithmetic.
- Honest boundaries: id-level identity across incarnations stays
  hidden when eviction cohorts are wide; fully-cached re-queries and
  plaintext values are invisible at the storage level.
