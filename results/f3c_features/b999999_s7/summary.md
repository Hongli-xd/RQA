# F2: which pair feature separates true overlap from background chains?

trace `sliding_seed7_waffle.tsv`; scorable pairs 124 (8 true, 116 false); flush mode 81, detected episodes 77.

Labels RANK the features here; they do not set any threshold.

| feature | AUC | |AUC-0.5|+0.5 | direction | median (true) | median (false) |
| --- | --- | --- | --- | --- | --- |
| `peak_frac` | 0.626 | 0.626 | high=true | 0.5 | 0.2188 |
| `alpha_mean` | 0.612 | 0.612 | high=true | 72.5227 | 38.5992 |
| `alpha_sd` | 0.405 | 0.595 | low=true | 0.8664 | 4.7377 |
| `dist_entropy` | 0.441 | 0.559 | low=true | 1.6977 | 3.2802 |
| `obs_over_exp` | 0.447 | 0.553 | low=true | 2.1308 | 2.1586 |
| `alpha_min` | 0.551 | 0.551 | high=true | 71.5 | 30.0 |
| `poisson_z_total` | 0.466 | 0.534 | low=true | 2.039 | 3.7392 |
| `max_cell` **(baseline)** | 0.53 | 0.53 | high=true | 3.5 | 4.0 |
| `mass` **(baseline)** | 0.525 | 0.525 | high=true | 8.5 | 21.5 |
| `mass_over_evict_writes` | 0.525 | 0.525 | high=true | 0.0033 | 0.0093 |
| `exp_mass` | 0.525 | 0.525 | high=true | 4.5741 | 9.4074 |
| `max_cell_over_min_miss` | 0.477 | 0.523 | low=true | 0.0168 | 0.0278 |
| `n_dist` | 0.48 | 0.52 | low=true | 3.5 | 12.0 |
| `gap` | 0.485 | 0.515 | low=true | 85.5 | 43.5 |
| `mass_over_min_miss_mass` | 0.486 | 0.514 | low=true | 0.0401 | 0.1803 |
| `mass_over_min_read_mass` | 0.487 | 0.513 | low=true | 0.0145 | 0.0573 |
| `poisson_z_max_cell` | 0.493 | 0.507 | low=true | 1.9653 | 2.6804 |
| `excess_mass` | 0.503 | 0.503 | high=true | 3.9815 | 12.0864 |
| `mass_per_child_batch` | 0.498 | 0.502 | low=true | 1.6667 | 7.0 |
