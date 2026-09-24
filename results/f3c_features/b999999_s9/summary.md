# F2: which pair feature separates true overlap from background chains?

trace `sliding_seed9_waffle.tsv`; scorable pairs 123 (3 true, 120 false); flush mode 81, detected episodes 75.

Labels RANK the features here; they do not set any threshold.

| feature | AUC | |AUC-0.5|+0.5 | direction | median (true) | median (false) |
| --- | --- | --- | --- | --- | --- |
| `mass_per_child_batch` | 0.714 | 0.714 | high=true | 13.0 | 8.0 |
| `max_cell` **(baseline)** | 0.69 | 0.69 | high=true | 7.0 | 4.0 |
| `max_cell_over_min_miss` | 0.688 | 0.688 | high=true | 0.0374 | 0.027 |
| `mass_over_min_miss_mass` | 0.656 | 0.656 | high=true | 0.2781 | 0.2 |
| `mass_over_min_read_mass` | 0.651 | 0.651 | high=true | 0.1016 | 0.0664 |
| `poisson_z_max_cell` | 0.631 | 0.631 | high=true | 2.7765 | 2.6804 |
| `poisson_z_total` | 0.622 | 0.622 | high=true | 4.5723 | 3.6914 |
| `obs_over_exp` | 0.622 | 0.622 | high=true | 2.4179 | 2.2333 |
| `excess_mass` | 0.621 | 0.621 | high=true | 24.1358 | 11.2346 |
| `mass_over_evict_writes` | 0.607 | 0.607 | high=true | 0.0188 | 0.0086 |
| `mass` **(baseline)** | 0.604 | 0.604 | high=true | 41.0 | 20.5 |
| `peak_frac` | 0.596 | 0.596 | high=true | 0.5 | 0.2042 |
| `gap` | 0.404 | 0.596 | low=true | 43.0 | 44.0 |
| `exp_mass` | 0.572 | 0.572 | high=true | 10.4198 | 8.2593 |
| `alpha_mean` | 0.556 | 0.556 | high=true | 38.8049 | 40.092 |
| `n_dist` | 0.511 | 0.511 | high=true | 12.0 | 11.0 |
| `dist_entropy` | 0.489 | 0.511 | low=true | 2.6136 | 3.3157 |
| `alpha_sd` | 0.496 | 0.504 | low=true | 4.1096 | 4.3727 |
| `alpha_min` | 0.504 | 0.504 | high=true | 30.0 | 30.0 |
