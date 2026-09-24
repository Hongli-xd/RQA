# Range-Query Attack on Waffle (design-level, order-hidden, passive)

- Attack visibility: event, batch_ts, direction, storage_key (simulation labels dropped at load)
- Config: `{'n_real': 200000, 'n_dummy': 70000, 'batch_size': 2500, 'client_requests': 1000, 'dummy_reads': 500, 'cache_size': 4000, 'rounds': 2400, 'group_size': 8, 'group_zipf': 0.9, 'write_window': 1, 'refresh_cache_hits': True, 'dummy_policy': 'paper_reset'}`
- Workload: background Zipf-0.9 point traffic + scheduled range episodes

## Stage A - batch anatomy
- B_hat=2500.0 (truth 2500); real budget=2105.0 (truth 2000); f_D_hat=395 (truth 500)
- flush age mode alpha=102 window=[101, 103] (fakes self-identify); f_R_mean=1847.6; entangled=False

## Stage B - episode detection
- detected 71 episodes (truth 75.0): P=0.85 R=0.80 F1=0.82 IoU=0.39
- false-positive batches: 2

## Stage D - tracking
- episode-pair overlap: 227 pairs total mass 66865 (bg cell mean 0.1563)
- id-level links only where eviction cohorts have size 1: 0, precision 0.00

## Stage C - cardinality
- MAE vs visible target=98.0, median rel err=0.082, worst=0.780
- cached re-read components are invisible (mean undercount vs raw m: -29.6)

## Stage E - topology
- overlap matrix Pearson=0.455 Pearson(large pairs)=0.584 binary acc=0.975 (104 true overlapping pairs)
- overlap-recovery rate by inter-query gap:
  - gap 24: 2/2 recovered
  - gap 30: 1/1 recovered
  - gap 35: 4/4 recovered
  - gap 50: 1/1 recovered
  - gap 56: 1/1 recovered
  - gap 57: 1/1 recovered
  - gap 62: 1/1 recovered
  - gap 77: 2/2 recovered
  - gap 80: 1/1 recovered
  - gap 85: 1/1 recovered
  - gap 90: 2/2 recovered
  - gap 92: 3/3 recovered
  - gap 107: 1/1 recovered
  - gap 110: 0/1 recovered
  - gap 112: 0/4 recovered
  - gap 120: 0/2 recovered
  - gap 136: 0/2 recovered
  - gap 140: 0/1 recovered
  - gap 142: 0/2 recovered
  - gap 179: 0/1 recovered
  - gap 182: 0/3 recovered
  - gap 197: 0/2 recovered
  - gap 218: 0/1 recovered
  - gap 232: 0/3 recovered
  - gap 312: 0/1 recovered
  - gap 383: 0/1 recovered
  - gap 397: 0/1 recovered
  - gap 413: 0/1 recovered
  - gap 475: 0/1 recovered
  - gap 505: 0/1 recovered
  - gap 510: 0/1 recovered
  - gap 615: 0/1 recovered
  - gap 645: 0/1 recovered
- point-burst control burst mass=291833 vs range burst mass=275132: co-parent structure is range-specific, not a volume artifact
- permutation null overlap mean=25460.6 max=26042.0 vs attack total 133730

## Maximum-leakage statement supported by this run
- Passively (storage ids + batch timing only, order-hidden) the server
  recovers: batch anatomy (B, real budget, f_D, flush age), the
  range-query timeline, per-episode visible cardinality, and pairwise
  range-overlap structure via exact write/read timing arithmetic.
- Honest boundaries: id-level identity across incarnations stays
  hidden when eviction cohorts are wide; fully-cached re-queries and
  plaintext values are invisible at the storage level.
