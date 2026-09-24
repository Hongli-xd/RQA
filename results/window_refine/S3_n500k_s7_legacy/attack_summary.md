# Range-Query Attack on Waffle (design-level, order-hidden, passive)

- Attack visibility: event, batch_ts, direction, storage_key (simulation labels dropped at load)
- Config: `{'n_real': 500000, 'n_dummy': 70000, 'batch_size': 2500, 'client_requests': 1000, 'dummy_reads': 500, 'cache_size': 10000, 'rounds': 1800, 'group_size': 8, 'group_zipf': 0.9, 'write_window': 1, 'refresh_cache_hits': True, 'dummy_policy': 'paper_reset'}`
- Workload: background Zipf-0.9 point traffic + scheduled range episodes

## Stage A - batch anatomy
- B_hat=2500.0 (truth 2500); real budget=2476.0 (truth 2000); f_D_hat=24 (truth 500)
- flush age mode alpha=256 window=[252, 256] (fakes self-identify); f_R_mean=1795.1; entangled=False

## Stage B - episode detection
- detected 54 episodes (truth 52.0): P=0.69 R=0.71 F1=0.70 IoU=0.41
- false-positive batches: 4

## Stage D - tracking
- episode-pair overlap: 422 pairs total mass 90704 (bg cell mean 0.4882)
- id-level links only where eviction cohorts have size 1: 0, precision 0.00

## Stage C - cardinality
- MAE vs visible target=110.0, median rel err=0.053, worst=0.574
- cached re-read components are invisible (mean undercount vs raw m: -101.2)

## Stage E - topology
- overlap matrix Pearson=0.626 Pearson(large pairs)=0.447 binary acc=0.967 (76 true overlapping pairs)
- overlap-recovery rate by inter-query gap:
  - gap 12: 1/1 recovered
  - gap 22: 1/1 recovered
  - gap 24: 2/2 recovered
  - gap 32: 1/1 recovered
  - gap 34: 0/1 recovered
  - gap 44: 1/1 recovered
  - gap 46: 1/1 recovered
  - gap 48: 1/1 recovered
  - gap 56: 1/1 recovered
  - gap 57: 1/1 recovered
  - gap 58: 1/1 recovered
  - gap 68: 1/1 recovered
  - gap 90: 3/4 recovered
  - gap 93: 1/1 recovered
  - gap 119: 1/1 recovered
  - gap 122: 1/1 recovered
  - gap 146: 1/1 recovered
  - gap 179: 1/1 recovered
  - gap 180: 2/2 recovered
  - gap 200: 1/1 recovered
  - gap 204: 1/1 recovered
  - gap 212: 3/4 recovered
  - gap 236: 1/2 recovered
  - gap 260: 0/1 recovered
  - gap 319: 0/1 recovered
  - gap 355: 0/1 recovered
  - gap 379: 0/1 recovered
  - gap 412: 0/2 recovered
- point-burst control burst mass=446750 vs range burst mass=443088: co-parent structure is range-specific, not a volume artifact
- permutation null overlap mean=60339.2 max=60549.0 vs attack total 181408

## Maximum-leakage statement supported by this run
- Passively (storage ids + batch timing only, order-hidden) the server
  recovers: batch anatomy (B, real budget, f_D, flush age), the
  range-query timeline, per-episode visible cardinality, and pairwise
  range-overlap structure via exact write/read timing arithmetic.
- Honest boundaries: id-level identity across incarnations stays
  hidden when eviction cohorts are wide; fully-cached re-queries and
  plaintext values are invisible at the storage level.
