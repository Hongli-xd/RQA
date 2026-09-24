# Range-Query Attack on Waffle (design-level, order-hidden, passive)

- Attack visibility: event, batch_ts, direction, storage_key (simulation labels dropped at load)
- Config: `{'n_real': 8192, 'n_dummy': 2048, 'batch_size': 128, 'client_requests': 64, 'dummy_reads': 16, 'cache_size': 512, 'rounds': 4000, 'group_size': 8, 'group_zipf': 0.9, 'write_window': 1, 'refresh_cache_hits': True, 'dummy_policy': 'paper_reset'}`
- Workload: background Zipf-0.9 point traffic + scheduled range episodes

## Stage A - batch anatomy
- B_hat=128.0 (truth 128); real budget=112.0 (truth 112); f_D_hat=16.0 (truth 16)
- flush age mode alpha=81 window=[80, 82] (fakes self-identify); f_R_mean=74.8; entangled=False

## Stage B - episode detection
- detected 74 episodes (truth 79.0): P=0.93 R=0.87 F1=0.90 IoU=0.44
- false-positive batches: 0

## Stage D - tracking
- episode-pair overlap: 82 pairs total mass 4897 (bg cell mean 0.0135)
- id-level links only where eviction cohorts have size 1: 0, precision 0.00

## Stage C - cardinality
- MAE vs visible target=13.9, median rel err=0.119, worst=0.433
- cached re-read components are invisible (mean undercount vs raw m: -12.5)

## Stage E - topology
- overlap matrix Pearson=0.492 Pearson(large pairs)=0.455 binary acc=0.975 (138 true overlapping pairs)
- overlap-recovery rate by inter-query gap:
  - gap 10: 1/1 recovered
  - gap 12: 2/2 recovered
  - gap 15: 1/1 recovered
  - gap 25: 5/5 recovered
  - gap 27: 0/1 recovered
  - gap 28: 1/1 recovered
  - gap 35: 3/3 recovered
  - gap 38: 1/1 recovered
  - gap 47: 1/1 recovered
  - gap 62: 2/2 recovered
  - gap 65: 3/3 recovered
  - gap 70: 1/1 recovered
  - gap 74: 1/1 recovered
  - gap 75: 4/4 recovered
  - gap 80: 0/1 recovered
  - gap 100: 0/8 recovered
  - gap 110: 0/1 recovered
  - gap 112: 0/1 recovered
  - gap 142: 0/2 recovered
  - gap 145: 0/1 recovered
  - gap 170: 0/2 recovered
  - gap 200: 0/1 recovered
  - gap 226: 0/1 recovered
  - gap 238: 0/1 recovered
  - gap 240: 0/1 recovered
  - gap 242: 0/1 recovered
  - gap 270: 0/1 recovered
  - gap 275: 0/1 recovered
  - gap 300: 0/2 recovered
  - gap 412: 0/1 recovered
  - gap 1250: 0/1 recovered
  - gap 1325: 0/1 recovered
  - gap 1790: 0/1 recovered
  - gap 1838: 0/1 recovered
  - gap 2035: 0/1 recovered
- point-burst control burst mass=423 vs range burst mass=2320: co-parent structure is range-specific, not a volume artifact
- permutation null overlap mean=4.5 max=13.0 vs attack total 9794

## Maximum-leakage statement supported by this run
- Passively (storage ids + batch timing only, order-hidden) the server
  recovers: batch anatomy (B, real budget, f_D, flush age), the
  range-query timeline, per-episode visible cardinality, and pairwise
  range-overlap structure via exact write/read timing arithmetic.
- Honest boundaries: id-level identity across incarnations stays
  hidden when eviction cohorts are wide; fully-cached re-queries and
  plaintext values are invisible at the storage level.
