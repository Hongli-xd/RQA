# F2: which pair feature separates true overlap from background chains?

trace `sliding_seed8_waffle.tsv`; scorable pairs 122 (4 true, 118 false); flush mode 81, detected episodes 76.

Labels RANK the features here; they do not set any threshold.

| feature | AUC | |AUC-0.5|+0.5 | direction | median (true) | median (false) |
| --- | --- | --- | --- | --- | --- |
| `peak_frac` | 0.744 | 0.744 | high=true | 0.7308 | 0.2113 |
| `obs_over_exp` | 0.735 | 0.735 | high=true | 3.3225 | 2.1507 |
| `dist_entropy` | 0.284 | 0.716 | low=true | 1.3727 | 3.4327 |
| `alpha_sd` | 0.354 | 0.646 | low=true | 2.5045 | 4.3559 |
| `exp_mass` | 0.36 | 0.64 | low=true | 4.7099 | 8.3765 |
| `n_dist` | 0.403 | 0.597 | low=true | 6.5 | 12.0 |
| `poisson_z_max_cell` | 0.584 | 0.584 | high=true | 10.942 | 2.6143 |
| `poisson_z_total` | 0.574 | 0.574 | high=true | 5.4651 | 3.5317 |
| `mass_over_evict_writes` | 0.439 | 0.561 | low=true | 0.0082 | 0.008 |
| `mass_over_min_read_mass` | 0.444 | 0.556 | low=true | 0.0521 | 0.066 |
| `mass` **(baseline)** | 0.447 | 0.553 | low=true | 20.0 | 18.5 |
| `mass_over_min_miss_mass` | 0.459 | 0.541 | low=true | 0.1664 | 0.2007 |
| `alpha_min` | 0.462 | 0.538 | low=true | 50.0 | 30.0 |
| `max_cell` **(baseline)** | 0.53 | 0.53 | high=true | 9.5 | 3.0 |
| `gap` | 0.476 | 0.524 | low=true | 64.0 | 44.0 |
| `excess_mass` | 0.52 | 0.52 | high=true | 15.321 | 10.0124 |
| `alpha_mean` | 0.517 | 0.517 | high=true | 56.0297 | 39.3142 |
| `max_cell_over_min_miss` | 0.514 | 0.514 | high=true | 0.0789 | 0.0272 |
| `mass_per_child_batch` | 0.49 | 0.51 | low=true | 6.6667 | 6.7917 |
