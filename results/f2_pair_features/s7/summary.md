# F2: which pair feature separates true overlap from background chains?

trace `range_seed7_waffle.tsv`; scorable pairs 112 (52 true, 60 false); flush mode 81, detected episodes 77.

Labels RANK the features here; they do not set any threshold.

| feature | AUC | |AUC-0.5|+0.5 | direction | median (true) | median (false) |
| --- | --- | --- | --- | --- | --- |
| `poisson_z_max_cell` | 0.837 | 0.837 | high=true | 30.1406 | 2.8372 |
| `obs_over_exp` | 0.829 | 0.829 | high=true | 4.6344 | 2.3025 |
| `poisson_z_total` | 0.791 | 0.791 | high=true | 13.9658 | 4.4131 |
| `max_cell_over_min_miss` | 0.783 | 0.783 | high=true | 0.1919 | 0.0321 |
| `max_cell` **(baseline)** | 0.78 | 0.78 | high=true | 30.0 | 5.0 |
| `peak_frac` | 0.777 | 0.777 | high=true | 0.4819 | 0.1608 |
| `excess_mass` | 0.766 | 0.766 | high=true | 49.8765 | 16.7963 |
| `mass_over_min_read_mass` | 0.744 | 0.744 | high=true | 0.1575 | 0.0668 |
| `mass_over_evict_writes` | 0.741 | 0.741 | high=true | 0.0269 | 0.012 |
| `mass` **(baseline)** | 0.74 | 0.74 | high=true | 67.0 | 29.5 |
| `mass_per_child_batch` | 0.74 | 0.74 | high=true | 17.75 | 8.45 |
| `mass_over_min_miss_mass` | 0.735 | 0.735 | high=true | 0.4399 | 0.1998 |
| `dist_entropy` | 0.275 | 0.725 | low=true | 2.6088 | 3.6403 |
| `alpha_sd` | 0.364 | 0.636 | low=true | 3.7775 | 4.9879 |
| `gap` | 0.364 | 0.636 | low=true | 42.0 | 47.5 |
| `alpha_min` | 0.373 | 0.627 | low=true | 28.5 | 32.5 |
| `alpha_mean` | 0.383 | 0.617 | low=true | 39.7297 | 42.8658 |
| `exp_mass` | 0.451 | 0.549 | low=true | 11.6049 | 11.9753 |
| `n_dist` | 0.484 | 0.516 | low=true | 15.0 | 15.0 |
