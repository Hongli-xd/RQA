# F2: which pair feature separates true overlap from background chains?

trace `range_seed8_waffle.tsv`; scorable pairs 32 (9 true, 23 false); flush mode 50, detected episodes 54.

Labels RANK the features here; they do not set any threshold.

| feature | AUC | |AUC-0.5|+0.5 | direction | median (true) | median (false) |
| --- | --- | --- | --- | --- | --- |
| `poisson_z_max_cell` | 0.855 | 0.855 | high=true | 122.9817 | 2.6237 |
| `max_cell` **(baseline)** | 0.819 | 0.819 | high=true | 592.0 | 25.0 |
| `peak_frac` | 0.792 | 0.792 | high=true | 0.6388 | 0.2222 |
| `max_cell_over_min_miss` | 0.787 | 0.787 | high=true | 0.5187 | 0.0355 |
| `mass_per_child_batch` | 0.768 | 0.768 | high=true | 221.3333 | 65.0 |
| `poisson_z_total` | 0.763 | 0.763 | high=true | 23.3335 | 0.7119 |
| `mass_over_min_read_mass` | 0.758 | 0.758 | high=true | 0.0885 | 0.0276 |
| `excess_mass` | 0.758 | 0.758 | high=true | 402.88 | 9.64 |
| `dist_entropy` | 0.246 | 0.754 | low=true | 1.6477 | 2.9046 |
| `mass_over_evict_writes` | 0.754 | 0.754 | high=true | 0.0148 | 0.0046 |
| `obs_over_exp` | 0.754 | 0.754 | high=true | 2.7044 | 1.0526 |
| `mass` **(baseline)** | 0.744 | 0.744 | high=true | 664.0 | 207.0 |
| `mass_over_min_miss_mass` | 0.705 | 0.705 | high=true | 0.7435 | 0.2997 |
| `gap` | 0.367 | 0.633 | low=true | 22.0 | 26.0 |
| `alpha_sd` | 0.372 | 0.628 | low=true | 1.6455 | 3.6972 |
| `alpha_min` | 0.406 | 0.594 | low=true | 7.0 | 18.0 |
| `n_dist` | 0.575 | 0.575 | high=true | 14.0 | 14.0 |
| `alpha_mean` | 0.454 | 0.546 | low=true | 20.2201 | 23.1684 |
| `exp_mass` | 0.522 | 0.522 | high=true | 203.72 | 210.42 |
