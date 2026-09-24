# Range-Query Attack on Waffle (design-level, order-hidden, passive)

- Attack visibility: event, batch_ts, direction, storage_key (simulation labels dropped at load)
- Config: `{'n_real': 8192, 'n_dummy': 2048, 'batch_size': 128, 'client_requests': 64, 'dummy_reads': 16, 'cache_size': 512, 'rounds': 4000, 'group_size': 8, 'group_zipf': 0.9, 'write_window': 1, 'refresh_cache_hits': True, 'dummy_policy': 'paper_reset'}`
- Workload: background Zipf-0.9 point traffic + scheduled range episodes

## Stage A - batch anatomy
- B_hat=128.0 (truth 128); real budget=112.0 (truth 112); f_D_hat=16.0 (truth 16)
- flush age mode alpha=81 window=[80, 82] (fakes self-identify); f_R_mean=75.1; entangled=False

## Stage B - episode detection
- detected 74 episodes (truth 78.0): P=0.88 R=0.83 F1=0.86 IoU=0.47
- false-positive batches: 0

## Stage D - tracking
- episode-pair overlap: 77 pairs total mass 3815 (bg cell mean 0.0136)
- id-level links only where eviction cohorts have size 1: 0, precision 0.00

## Stage C - cardinality
- MAE vs visible target=11.8, median rel err=0.135, worst=0.450
- cached re-read components are invisible (mean undercount vs raw m: -13.8)

## Stage E - topology
- overlap matrix Pearson=0.379 Pearson(large pairs)=0.274 binary acc=0.975 (114 true overlapping pairs)
- overlap-recovery rate by inter-query gap:
  - gap 10: 2/2 recovered
  - gap 15: 2/2 recovered
  - gap 25: 2/3 recovered
  - gap 35: 3/3 recovered
  - gap 38: 2/2 recovered
  - gap 42: 1/1 recovered
  - gap 47: 1/1 recovered
  - gap 55: 1/1 recovered
  - gap 62: 2/2 recovered
  - gap 80: 0/1 recovered
  - gap 85: 0/1 recovered
  - gap 100: 0/2 recovered
  - gap 117: 0/1 recovered
  - gap 127: 0/2 recovered
  - gap 142: 0/2 recovered
  - gap 145: 0/1 recovered
  - gap 155: 0/1 recovered
  - gap 170: 0/2 recovered
  - gap 220: 0/1 recovered
  - gap 232: 0/2 recovered
  - gap 275: 0/1 recovered
  - gap 282: 0/1 recovered
  - gap 399: 0/1 recovered
  - gap 409: 0/1 recovered
  - gap 412: 0/1 recovered
  - gap 424: 0/1 recovered
  - gap 560: 0/1 recovered
  - gap 640: 0/1 recovered
  - gap 645: 0/1 recovered
  - gap 1835: 0/1 recovered
  - gap 2235: 0/1 recovered
  - gap 2288: 0/1 recovered
  - gap 2323: 0/1 recovered
- point-burst control burst mass=414 vs range burst mass=1929: co-parent structure is range-specific, not a volume artifact
- permutation null overlap mean=14.9 max=51.0 vs attack total 7630

## Maximum-leakage statement supported by this run
- Passively (storage ids + batch timing only, order-hidden) the server
  recovers: batch anatomy (B, real budget, f_D, flush age), the
  range-query timeline, per-episode visible cardinality, and pairwise
  range-overlap structure via exact write/read timing arithmetic.
- Honest boundaries: id-level identity across incarnations stays
  hidden when eviction cohorts are wide; fully-cached re-queries and
  plaintext values are invisible at the storage level.
