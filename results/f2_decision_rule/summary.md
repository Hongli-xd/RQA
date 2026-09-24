# F2b: decision rule from the burst-calibrated concentration feature

within-window bound: gap <= 70 batches. Thresholds are burst-control quantiles; truth only scores.

| arm | seeds | precision | recall | F1 | within-window recall | dP vs base | dR_win vs base | mag Pearson (mass) | mag Pearson (excess) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| `baseline` | 3 | 0.464 | 0.795 | 0.580 | 0.855 | +0.000 | +0.000 | no gain | 0.372 | 0.465 |
| `+entropy q50` | 3 | 0.554 | 0.783 | 0.646 | 0.843 | +0.090 | +0.012 | OK | 0.489 | 0.529 |
| `+entropy q90` | 3 | 0.726 | 0.469 | 0.520 | 0.503 | +0.262 | +0.352 | VIOLATES recall | 0.501 | 0.504 |
| `+entropy q99` | 3 | 0.167 | 0.006 | 0.012 | 0.007 | -0.297 | +0.848 | VIOLATES recall | -0.011 | -0.010 |
| `+obs_over_exp q50` | 3 | 0.548 | 0.772 | 0.637 | 0.831 | +0.084 | +0.024 | OK | 0.439 | 0.497 |
| `+obs_over_exp q90` | 3 | 0.716 | 0.705 | 0.710 | 0.760 | +0.252 | +0.095 | VIOLATES recall | 0.541 | 0.554 |
| `+obs_over_exp q99` | 3 | 0.764 | 0.600 | 0.665 | 0.650 | +0.300 | +0.205 | VIOLATES recall | 0.542 | 0.551 |
| `+peak q50` | 3 | 0.569 | 0.777 | 0.655 | 0.836 | +0.105 | +0.019 | OK | 0.499 | 0.534 |
| `+peak q90` | 3 | 0.782 | 0.606 | 0.660 | 0.655 | +0.318 | +0.200 | VIOLATES recall | 0.581 | 0.581 |
| `+peak q99` | 3 | 0.903 | 0.392 | 0.545 | 0.423 | +0.439 | +0.432 | VIOLATES recall | 0.539 | 0.538 |
| `+poisson q50` | 3 | 0.578 | 0.735 | 0.642 | 0.798 | +0.114 | +0.057 | VIOLATES recall | 0.447 | 0.503 |
| `+poisson q90` | 3 | 0.721 | 0.651 | 0.680 | 0.708 | +0.257 | +0.147 | VIOLATES recall | 0.524 | 0.544 |
| `+poisson q99` | 3 | 0.782 | 0.626 | 0.689 | 0.679 | +0.318 | +0.176 | VIOLATES recall | 0.546 | 0.557 |
| `peak_only q50` | 3 | 0.498 | 0.971 | 0.656 | 0.969 | +0.034 | -0.114 | OK | 0.525 | 0.552 |
| `peak_only q90` | 3 | 0.606 | 0.661 | 0.611 | 0.667 | +0.142 | +0.188 | VIOLATES recall | 0.581 | 0.581 |
| `peak_only q99` | 3 | 0.653 | 0.411 | 0.504 | 0.423 | +0.189 | +0.432 | VIOLATES recall | 0.536 | 0.537 |
| `poisson_only q50` | 3 | 0.576 | 0.779 | 0.659 | 0.848 | +0.112 | +0.007 | OK | 0.454 | 0.508 |
| `poisson_only q90` | 3 | 0.724 | 0.657 | 0.686 | 0.715 | +0.260 | +0.140 | VIOLATES recall | 0.525 | 0.545 |
| `poisson_only q99` | 3 | 0.782 | 0.626 | 0.689 | 0.679 | +0.318 | +0.176 | VIOLATES recall | 0.546 | 0.557 |

Acceptance: within-window recall drop <= 0.05 AND precision up.
Baseline for the magnitude column: the deployed attack reaches
Pearson 0.34-0.52 (results/staged_precision/summary.md).
