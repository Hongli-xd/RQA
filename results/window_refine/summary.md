# Window refinement: dense gap grid + logistic inflection estimate

Dense grid: [15, 25, 35, 50, 65, 80, 100, 130, 170, 220, 300, 400]; make_episodes already accepts
arbitrary gap lists, so this is purely a workload-scheduling change
(no attack-code change; the CLI default grid stays 20,45,90,200 so
pre-existing results reproduce bit-for-bit).

recovery(gap) = 1/(1+exp(k*(gap-w))) fitted by Newton/IRLS (stdlib
only) on the raw (actual gap, recovered?) truth pairs; w is the
50%-recovery inflection = the leakage window. Bootstrap: 500
resamples of the truth pairs, percentile CI.

## Per-config fit (dense grid, pooled over runs)

| config | n_runs | n_pairs | window_quant_dense | monotonicity_violations | clean_sigmoid | fit_kind | separation_interval | w | k | w_boot_mean | w_ci95_lo | w_ci95_hi | n_boot_failed |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| S1_n8k | 3 | 179 | 65 | 25(10/12)->35(13/13) | False | converged |  | 76.3 | 0.1048 | 75.9 | 69.4 | 80.7 | 0 |
| S2_n200k | 1 | 52 | 80 | none | False | capped | (107,110) | 108.5 | 13.0019 | 106.0 | 93.2 | 111.6 | 0 |
| S3_n500k | 1 | 46 | 220 | none | False | capped | (232,312) | 272.0 | 0.5518 | 271.2 | 224.0 | 310.6 | 55 |

Notes: `window_quant_dense` = largest dense-grid gap with >=50%
recovery (still a quantised lower bound); `clean_sigmoid` requires
no monotonicity violation between adjacent gaps (n>=5), >=80%
recovery at gap<=50 and <=20% at gap>=170.

## ASCII recovery curves

### S1_n8k

```
# recovery vs gap (S1_n8k, dense grid, pooled over runs)
gap    n   rate  curve
  15   16  1.00  ##################################################
  25   12  0.83  ##########################################
  35   13  1.00  ##################################################
  50    4  1.00  ##################################################
  65   13  1.00  ##################################################
  80   13  0.46  #######################
 100   19  0.00  
 130   16  0.00  
 170   11  0.00  
 220   18  0.00  
 300   14  0.00  
 400   30  0.00
```

### S2_n200k

```
# recovery vs gap (S2_n200k, dense grid, pooled over runs)
gap    n   rate  curve
  25    3  1.00  ##################################################
  35    4  1.00  ##################################################
  50    3  1.00  ##################################################
  65    1  1.00  ##################################################
  80    6  1.00  ##################################################
 100    9  0.44  ######################
 130    7  0.00  
 170    4  0.00  
 220    6  0.00  
 300    1  0.00  
 400    8  0.00
```

### S3_n500k

```
# recovery vs gap (S3_n500k, dense grid, pooled over runs)
gap    n   rate  curve
  15    2  1.00  ##################################################
  25    2  1.00  ##################################################
  35    3  1.00  ##################################################
  50    6  1.00  ##################################################
  65    3  1.00  ##################################################
  80    5  1.00  ##################################################
 100    5  1.00  ##################################################
 130    8  1.00  ##################################################
 170    6  1.00  ##################################################
 220    4  1.00  ##################################################
 300    2  0.00
```

## Old (quantised) vs new (logistic) window

| config | legacy-grid window | dense-grid window | logistic w [95% CI] |
| --- | --- | --- | --- |
| S1_n8k | 45/45/45 | 65 | 76.3 [69.4, 80.7] |
| S2_n200k | 90 | 80 | 108.5 [93.2, 111.6] (near-separated; interval (107,110)) |
| S3_n500k | 200 | 220 | 272.0 [224.0, 310.6] (near-separated; interval (232,312)) |

## Scaling-law refit (window vs sweep time (N-C)/f_R, through origin)

| window estimator | slope | R^2 | points |
| --- | --- | --- | --- |
| legacy-grid quantised | 0.731 | 0.914 | 5 |
| dense-grid quantised | 0.839 | 0.987 | 5 |
| logistic w (dequantised) | 1.047 | 0.988 | 3 |

Per-run law points: `law_refit.csv`. Caveats: the refit spans
fewer runs than the original 14-run matrix (S1 x3 seeds, S2, S3),
and each config's logistic w is pooled over its runs, so R^2 here
is not directly comparable in sample size to the original 0.960.
