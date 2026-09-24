# Range-Query Attack on Waffle (design-level, order-hidden, passive)

- Attack visibility: event, batch_ts, direction, storage_key (simulation labels dropped at load)
- Config: `{'n_real': 500000, 'n_dummy': 70000, 'batch_size': 2500, 'client_requests': 1000, 'dummy_reads': 500, 'cache_size': 10000, 'rounds': 1800, 'group_size': 8, 'group_zipf': 0.9, 'write_window': 1, 'refresh_cache_hits': True, 'dummy_policy': 'paper_reset'}`
- Workload: background Zipf-0.9 point traffic + scheduled range episodes

## Stage A - batch anatomy
- B_hat=2500.0 (truth 2500); real budget=2473.5 (truth 2000); f_D_hat=26.5 (truth 500)
- flush age mode alpha=255 window=[254, 256] (fakes self-identify); f_R_mean=1478.4; entangled=False

## Stage B - episode detection
- detected 54 episodes (truth 54.0): P=0.83 R=0.83 F1=0.83 IoU=0.42
- false-positive batches: 4

## Stage D - tracking
- episode-pair overlap: 416 pairs total mass 94418 (bg cell mean 0.4882)
- id-level links only where eviction cohorts have size 1: 0, precision 0.00

## Stage C - cardinality
- MAE vs visible target=91.3, median rel err=0.062, worst=0.719
- cached re-read components are invisible (mean undercount vs raw m: -94.4)

## Stage E - topology
- overlap matrix Pearson=0.634 Pearson(large pairs)=0.577 binary acc=0.972 (92 true overlapping pairs)
- overlap-recovery rate by inter-query gap:
  - gap 15: 2/2 recovered
  - gap 24: 1/1 recovered
  - gap 27: 1/1 recovered
  - gap 35: 2/2 recovered
  - gap 40: 1/1 recovered
  - gap 47: 1/1 recovered
  - gap 50: 3/3 recovered
  - gap 54: 1/1 recovered
  - gap 57: 1/1 recovered
  - gap 59: 1/1 recovered
  - gap 62: 2/2 recovered
  - gap 77: 1/1 recovered
  - gap 80: 1/1 recovered
  - gap 85: 1/1 recovered
  - gap 89: 1/1 recovered
  - gap 90: 1/1 recovered
  - gap 92: 1/1 recovered
  - gap 97: 1/1 recovered
  - gap 104: 1/1 recovered
  - gap 112: 2/2 recovered
  - gap 116: 1/1 recovered
  - gap 120: 2/2 recovered
  - gap 134: 1/1 recovered
  - gap 136: 1/1 recovered
  - gap 142: 2/2 recovered
  - gap 147: 1/1 recovered
  - gap 151: 1/1 recovered
  - gap 166: 1/1 recovered
  - gap 170: 2/2 recovered
  - gap 178: 1/1 recovered
  - gap 182: 1/1 recovered
  - gap 196: 1/1 recovered
  - gap 197: 1/1 recovered
  - gap 232: 2/2 recovered
  - gap 312: 0/2 recovered
- point-burst control burst mass=446750 vs range burst mass=444463: co-parent structure is range-specific, not a volume artifact
- permutation null overlap mean=66848.7 max=67758.0 vs attack total 188836

## Maximum-leakage statement supported by this run
- Passively (storage ids + batch timing only, order-hidden) the server
  recovers: batch anatomy (B, real budget, f_D, flush age), the
  range-query timeline, per-episode visible cardinality, and pairwise
  range-overlap structure via exact write/read timing arithmetic.
- Honest boundaries: id-level identity across incarnations stays
  hidden when eviction cohorts are wide; fully-cached re-queries and
  plaintext values are invisible at the storage level.
