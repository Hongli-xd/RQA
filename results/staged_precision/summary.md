# Stage-D overlap-pair precision: metrics + burst-calibrated thresholds

## Calibration data source (discipline statement)

Thresholds are derived ONLY from server-visible data: the
point-burst control trace (same schedule/sizes, random keys - any
episode-pair aggregate there is noise by construction) plus the
attack's own detections on it. Range-episode ground truth is read
only by the eval-side metrics. No truth participates in setting
any threshold VALUE. The choice among candidate quantiles
(q10/q50/q99) is guided by the task's acceptance constraints
(within-window recall drop <= 0.05, precision up) - the deployed
rule is the strongest quantile rule satisfying them.

## Burst-noise distributions (per seed)

- seed 7: burst-noise episode pairs n=122 (n passing the cell>=4 gate: 72); mass q50/q99 = 23/83; cell q99 = 9, max cell = 12; conditional (cell>=4) mass q10 = 10
- seed 8: burst-noise episode pairs n=139 (n passing the cell>=4 gate: 80); mass q50/q99 = 21/78; cell q99 = 9, max cell = 10; conditional (cell>=4) mass q10 = 8
- seed 9: burst-noise episode pairs n=127 (n passing the cell>=4 gate: 70); mass q50/q99 = 24/78; cell q99 = 9, max cell = 10; conditional (cell>=4) mass q10 = 12

## Arm comparison (fixed window = baseline window estimate 70/84/68 batches for seeds 7/8/9)

*dR_win = within-window recall change vs baseline (positive = loss); acceptance requires <= 0.05 per seed; dP_all = overall precision change.*

### baseline (min_pair_mass=8, max_cell=4)

| seed | P_all | R_all | F1_all | P_win | R_win | dR_win | dP_all | pearson | pearson_large | FP |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 7 | 0.482 | 0.423 | 0.451 | 0.532 | 0.911 | +0.000 | +0.000 | 0.521 | 0.302 | 44 |
| 8 | 0.486 | 0.312 | 0.380 | 0.500 | 0.673 | +0.000 | +0.000 | 0.358 | 0.166 | 37 |
| 9 | 0.400 | 0.473 | 0.433 | 0.456 | 0.963 | +0.000 | +0.000 | 0.524 | 0.547 | 39 |

- mean within-window recall drop: +0.000 (per-seed max +0.000; <= 0.05 OK)
- mean overall precision change: +0.000 (NOT improved)

### R1_q99_noise_envelope (min_pair_mass=83, max_cell=9)

| seed | P_all | R_all | F1_all | P_win | R_win | dR_win | dP_all | pearson | pearson_large | FP |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 7 | 1.000 | 0.155 | 0.268 | 1.000 | 0.333 | +0.578 | +0.518 | 0.473 | 0.420 | 0 |
| 8 | 0.786 | 0.098 | 0.175 | 0.786 | 0.211 | +0.462 | +0.300 | 0.283 | 0.185 | 3 |
| 9 | 0.750 | 0.164 | 0.269 | 0.750 | 0.333 | +0.630 | +0.350 | 0.490 | 0.575 | 3 |

- mean within-window recall drop: +0.556 (per-seed max +0.630; VIOLATES 0.05)
- mean overall precision change: +0.389 (improved)

### R2_conditional_mass_q10 (min_pair_mass=10, max_cell=4)

| seed | P_all | R_all | F1_all | P_win | R_win | dR_win | dP_all | pearson | pearson_large | FP |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 7 | 0.500 | 0.423 | 0.458 | 0.532 | 0.911 | +0.000 | +0.018 | 0.521 | 0.302 | 41 |
| 8 | 0.486 | 0.312 | 0.380 | 0.500 | 0.673 | +0.000 | +0.000 | 0.358 | 0.166 | 37 |
| 9 | 0.406 | 0.473 | 0.437 | 0.456 | 0.963 | +0.000 | +0.006 | 0.524 | 0.547 | 38 |

- mean within-window recall drop: +0.000 (per-seed max +0.000; <= 0.05 OK)
- mean overall precision change: +0.008 (improved)

### R3_unconditional_mass_q50 (min_pair_mass=23, max_cell=4)

| seed | P_all | R_all | F1_all | P_win | R_win | dR_win | dP_all | pearson | pearson_large | FP |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 7 | 0.506 | 0.402 | 0.448 | 0.534 | 0.867 | +0.044 | +0.024 | 0.518 | 0.298 | 38 |
| 8 | 0.444 | 0.250 | 0.320 | 0.444 | 0.538 | +0.135 | -0.042 | 0.340 | 0.156 | 35 |
| 9 | 0.431 | 0.455 | 0.443 | 0.481 | 0.926 | +0.037 | +0.031 | 0.521 | 0.539 | 33 |

- mean within-window recall drop: +0.072 (per-seed max +0.135; VIOLATES 0.05)
- mean overall precision change: +0.004 (improved)

## Verdict

- R1 (q99 noise-envelope): precision rises to 0.845 but within-window recall drops up to 0.630 - REJECTED by the recall constraint. Genuine weak links (small overlap cohorts, mass 11-32, cell 4) live inside the burst-noise envelope on this workload; rejecting 99% of noise also rejects them.
- R3 (unconditional q50 mass floor): recall drop up to 0.135 - REJECTED; the unconditional noise median is too coarse because most noise never passes the cell gate.
- R2 (conditional q10 mass floor, DEPLOYED): max within-window recall drop 0.000 (<= 0.05 OK); mean overall precision change +0.008 (improved); per-seed changes s7=+0.018, s8=+0.000, s9=+0.006.
- Pearson(large-overlap): baseline mean 0.339 vs R2 0.339 - does not improve under R2 (reported as required).

Honest finding: on S1 the FP mass and the weak-but-true link mass
overlap heavily; the reachable precision gain under the recall
constraint is small (a few percent). The large precision headroom
visible at q99 is unreachable without losing weak true links -
materially improving Stage-D precision needs a feature beyond
(mass, cell) concentration, not threshold tuning.

Raw per-run table: staged_precision.csv.