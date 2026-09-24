# Range-Query Attack on Waffle (design-level, order-hidden, passive)

- Attack visibility: event, batch_ts, direction, storage_key (simulation labels dropped at load)
- Config: `{'n_real': 8192, 'n_dummy': 2048, 'batch_size': 128, 'client_requests': 64, 'dummy_reads': 16, 'cache_size': 512, 'rounds': 4000, 'group_size': 8, 'group_zipf': 0.9, 'write_window': 1, 'refresh_cache_hits': True, 'dummy_policy': 'paper_reset'}`
- Workload: background Zipf-0.9 point traffic + scheduled range episodes

## Stage A - batch anatomy
- B_hat=128.0 (truth 128); real budget=112.0 (truth 112); f_D_hat=16.0 (truth 16)
- flush age mode alpha=81 window=[80, 82] (fakes self-identify); f_R_mean=73.7; entangled=False

## Stage B - episode detection
- detected 72 episodes (truth 80.0): P=0.85 R=0.76 F1=0.80 IoU=0.45
- false-positive batches: 0

## Stage D - tracking
- episode-pair overlap: 68 pairs total mass 3629 (bg cell mean 0.0136)
- id-level links only where eviction cohorts have size 1: 0, precision 0.00

## Stage C - cardinality
- MAE vs visible target=13.1, median rel err=0.138, worst=0.439
- cached re-read components are invisible (mean undercount vs raw m: -15.8)

## Stage E - topology
- overlap matrix Pearson=0.393 Pearson(large pairs)=0.301 binary acc=0.958 (168 true overlapping pairs)
- overlap-recovery rate by inter-query gap:
  - gap 6: 1/1 recovered
  - gap 10: 1/1 recovered
  - gap 12: 2/2 recovered
  - gap 15: 2/2 recovered
  - gap 18: 1/1 recovered
  - gap 20: 1/1 recovered
  - gap 25: 1/1 recovered
  - gap 27: 1/1 recovered
  - gap 35: 3/3 recovered
  - gap 56: 1/1 recovered
  - gap 59: 1/1 recovered
  - gap 62: 4/4 recovered
  - gap 73: 1/1 recovered
  - gap 74: 0/1 recovered
  - gap 80: 0/2 recovered
  - gap 90: 0/1 recovered
  - gap 96: 0/1 recovered
  - gap 100: 0/2 recovered
  - gap 102: 0/1 recovered
  - gap 107: 0/1 recovered
  - gap 108: 0/1 recovered
  - gap 112: 0/1 recovered
  - gap 117: 0/1 recovered
  - gap 124: 0/1 recovered
  - gap 130: 0/1 recovered
  - gap 142: 0/2 recovered
  - gap 145: 0/1 recovered
  - gap 150: 0/1 recovered
  - gap 154: 0/1 recovered
  - gap 158: 0/1 recovered
  - gap 168: 0/1 recovered
  - gap 170: 0/2 recovered
  - gap 180: 0/1 recovered
  - gap 209: 0/1 recovered
  - gap 215: 0/1 recovered
  - gap 217: 0/1 recovered
  - gap 219: 0/1 recovered
  - gap 220: 0/1 recovered
  - gap 226: 0/1 recovered
  - gap 232: 0/2 recovered
  - gap 238: 0/1 recovered
  - gap 244: 0/1 recovered
  - gap 265: 0/1 recovered
  - gap 270: 0/1 recovered
  - gap 275: 0/1 recovered
  - gap 282: 0/1 recovered
  - gap 300: 0/4 recovered
  - gap 377: 0/1 recovered
  - gap 387: 0/1 recovered
  - gap 389: 0/1 recovered
  - gap 399: 0/1 recovered
  - gap 412: 0/1 recovered
  - gap 424: 0/1 recovered
  - gap 435: 0/1 recovered
  - gap 1108: 0/1 recovered
  - gap 2105: 0/1 recovered
  - gap 3131: 0/1 recovered
  - gap 3143: 0/1 recovered
  - gap 3255: 0/1 recovered
  - gap 3530: 0/1 recovered
- point-burst control burst mass=319 vs range burst mass=2236: co-parent structure is range-specific, not a volume artifact
- permutation null overlap mean=7.9 max=24.0 vs attack total 7258

## Maximum-leakage statement supported by this run
- Passively (storage ids + batch timing only, order-hidden) the server
  recovers: batch anatomy (B, real budget, f_D, flush age), the
  range-query timeline, per-episode visible cardinality, and pairwise
  range-overlap structure via exact write/read timing arithmetic.
- Honest boundaries: id-level identity across incarnations stays
  hidden when eviction cohorts are wide; fully-cached re-queries and
  plaintext values are invisible at the storage level.
