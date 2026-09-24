# Attack-hyperparameter sensitivity scan (S1_n8k, seeds 7/8/9)

Each parameter is scanned independently at {0.5x, 1x, 2x} of its
default (all other parameters at defaults; 1x rows are the shared
all-default baseline run of that seed). Window = largest tested gap
with >=50% overlap recovery on the grid {20,45,90,200,(400)}.

Flip criteria (per seed, all levels):
- (a) |F1 - F1_1x| <= 0.15;
- (b) window estimate moves by <= 2 grid steps;
- (c) permutation-null mean < attack kept-overlap mass.

## track_span (default 80, flag `--track-span`)

| level | value | F1 (mean±sd) | P | R | C med.rel.err | window (per seed) | null mean | attack mass |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0.5x | 40 | 0.893±0.022 | 0.91±0.02 | 0.88±0.03 | 0.130±0.009 | 45/45/45 | 3.4±3.0 | 4861±260 |
| 1x | 80 | 0.895±0.025 | 0.92±0.02 | 0.88±0.03 | 0.125±0.021 | 45/45/45 | 2.4±1.4 | 4876±240 |
| 2x | 160 | 0.895±0.025 | 0.92±0.02 | 0.88±0.03 | 0.130±0.012 | 45/45/45 | 4.9±3.1 | 4864±232 |

- verdict: **NOT FLIPPED** 
- seed-to-seed F1 sd within levels: s7=0.003, s8=0.000, s9=0.000

## flush_frac (default 0.08, flag `--flush-frac`)

| level | value | F1 (mean±sd) | P | R | C med.rel.err | window (per seed) | null mean | attack mass |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0.5x | 0.04 | 0.870±0.031 | 0.88±0.04 | 0.86±0.03 | 0.104±0.010 | 45/45/45 | 4.8±4.7 | 5596±110 |
| 1x | 0.08 | 0.895±0.025 | 0.92±0.02 | 0.88±0.03 | 0.125±0.021 | 45/45/45 | 2.4±1.4 | 4876±240 |
| 2x | 0.16 | 0.872±0.008 | 0.91±0.01 | 0.84±0.01 | 0.183±0.010 | 45/45/45 | 1.7±1.3 | 4091±185 |

- verdict: **NOT FLIPPED** 
- seed-to-seed F1 sd within levels: s7=0.019, s8=0.006, s9=0.018

## local_bg (default 40, flag `--local-bg`)

| level | value | F1 (mean±sd) | P | R | C med.rel.err | window (per seed) | null mean | attack mass |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0.5x | 20 | 0.895±0.025 | 0.92±0.02 | 0.88±0.03 | 0.125±0.017 | 45/45/45 | 2.4±1.4 | 4876±240 |
| 1x | 40 | 0.895±0.025 | 0.92±0.02 | 0.88±0.03 | 0.125±0.021 | 45/45/45 | 2.4±1.4 | 4876±240 |
| 2x | 80 | 0.895±0.025 | 0.92±0.02 | 0.88±0.03 | 0.131±0.019 | 45/45/45 | 2.4±1.4 | 4876±240 |

- verdict: **NOT FLIPPED** 
- seed-to-seed F1 sd within levels: s7=0.000, s8=0.000, s9=0.000

## min_mass (default 30, flag `--min-mass`)

| level | value | F1 (mean±sd) | P | R | C med.rel.err | window (per seed) | null mean | attack mass |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0.5x | 15 | 0.898±0.021 | 0.91±0.02 | 0.88±0.03 | 0.131±0.013 | 45/45/45 | 2.4±1.4 | 4954±284 |
| 1x | 30 | 0.895±0.025 | 0.92±0.02 | 0.88±0.03 | 0.125±0.021 | 45/45/45 | 2.4±1.4 | 4876±240 |
| 2x | 60 | 0.895±0.025 | 0.92±0.02 | 0.88±0.03 | 0.125±0.021 | 45/45/45 | 2.4±1.4 | 4876±240 |

- verdict: **NOT FLIPPED** 
- seed-to-seed F1 sd within levels: s7=0.003, s8=0.007, s9=0.000

## window (default 50, flag `--window`)

| level | value | F1 (mean±sd) | P | R | C med.rel.err | window (per seed) | null mean | attack mass |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0.5x | 25 | 0.879±0.012 | 0.88±0.01 | 0.88±0.01 | 0.120±0.019 | 45/45/45 | 4.6±4.5 | 4931±146 |
| 1x | 50 | 0.895±0.025 | 0.92±0.02 | 0.88±0.03 | 0.125±0.021 | 45/45/45 | 2.4±1.4 | 4876±240 |
| 2x | 100 | 0.889±0.016 | 0.91±0.01 | 0.87±0.02 | 0.117±0.021 | 45/45/45 | 2.2±1.1 | 4965±369 |

- verdict: **NOT FLIPPED** 
- seed-to-seed F1 sd within levels: s7=0.017, s8=0.010, s9=0.007

## gap (default 3, flag `--gap`)

| level | value | F1 (mean±sd) | P | R | C med.rel.err | window (per seed) | null mean | attack mass |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0.5x | 2 | 0.902±0.020 | 0.92±0.02 | 0.88±0.02 | 0.126±0.022 | 45/45/45 | 2.4±1.4 | 4872±246 |
| 1x | 3 | 0.895±0.025 | 0.92±0.02 | 0.88±0.03 | 0.125±0.021 | 45/45/45 | 2.4±1.4 | 4876±240 |
| 2x | 6 | 0.882±0.008 | 0.91±0.01 | 0.86±0.01 | 0.125±0.021 | 45/45/45 | 2.7±1.8 | 4813±169 |

- verdict: **NOT FLIPPED** 
- seed-to-seed F1 sd within levels: s7=0.019, s8=0.000, s9=0.009

## min_pair_mass (default 8, flag `--min-pair-mass`)

| level | value | F1 (mean±sd) | P | R | C med.rel.err | window (per seed) | null mean | attack mass |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0.5x | 4 | 0.895±0.025 | 0.92±0.02 | 0.88±0.03 | 0.125±0.021 | 45/45/45 | 2.4±1.4 | 4878±240 |
| 1x | 8 | 0.895±0.025 | 0.92±0.02 | 0.88±0.03 | 0.125±0.021 | 45/45/45 | 2.4±1.4 | 4876±240 |
| 2x | 16 | 0.895±0.025 | 0.92±0.02 | 0.88±0.03 | 0.125±0.021 | 45/45/45 | 0.0±0.0 | 4817±213 |

- verdict: **NOT FLIPPED** 
- seed-to-seed F1 sd within levels: s7=0.000, s8=0.000, s9=0.000

## max_cell (default 4, flag `--max-cell`)

| level | value | F1 (mean±sd) | P | R | C med.rel.err | window (per seed) | null mean | attack mass |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0.5x | 2 | 0.895±0.025 | 0.92±0.02 | 0.88±0.03 | 0.125±0.021 | 45/45/45 | 118.7±6.3 | 5271±277 |
| 1x | 4 | 0.895±0.025 | 0.92±0.02 | 0.88±0.03 | 0.125±0.021 | 45/45/45 | 2.4±1.4 | 4876±240 |
| 2x | 8 | 0.895±0.025 | 0.92±0.02 | 0.88±0.03 | 0.125±0.021 | 45/20/45 | 0.0±0.0 | 3358±313 |

- verdict: **NOT FLIPPED** 
- seed-to-seed F1 sd within levels: s7=0.000, s8=0.000, s9=0.000

## eviction_tail (default 15, flag `--eviction-tail`)

| level | value | F1 (mean±sd) | P | R | C med.rel.err | window (per seed) | null mean | attack mass |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 0.5x | 8 | 0.895±0.025 | 0.92±0.02 | 0.88±0.03 | 0.125±0.021 | 45/45/45 | 1.2±0.8 | 3559±232 |
| 1x | 15 | 0.895±0.025 | 0.92±0.02 | 0.88±0.03 | 0.125±0.021 | 45/45/45 | 2.4±1.4 | 4876±240 |
| 2x | 30 | 0.895±0.025 | 0.92±0.02 | 0.88±0.03 | 0.125±0.021 | 45/45/45 | 7.5±1.7 | 7088±231 |

- verdict: **NOT FLIPPED** 
- seed-to-seed F1 sd within levels: s7=0.000, s8=0.000, s9=0.000

## Overall

No parameter flipped the conclusion at 0.5x/2x: detection F1,
window estimate and null separation are all within the criteria
above, for every seed. The design-level conclusion is robust to
these 9 attack hyperparameters on the S1 workload family.

Note: only three levels per parameter were tested (0.5x/1x/2x);
'safe interval' claims are limited to the tested levels - values
between them are untested interpolation.

Raw per-run metrics: `sensitivity.csv` (81 runs).