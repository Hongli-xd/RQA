# Prior-matching identifiability ceiling

queries/cell=120, widths=2%-10% of domain, N=1,000,000, seed=7

`median_bits` = log2 of the number of value ranges consistent with one
observed volume: the positional entropy a single Stage-C cardinality
leaves. 0 bits = that query's range is pinned by volume alone.
`coverage` = fraction of queries whose true range still matches under the
auxiliary histogram (a coverage collapse means the matcher rejects the
truth, i.e. it returns a CONFIDENT WRONG answer).

## A_ceiling

| hist | d | eps | #ranges | median cand | median bits | frac unique | coverage | pair bits |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| uniform | 100 | 0.08 | 5,050 | 96.0 | 6.58 | 0.0 | 0.9417 | 10.04 |
| uniform | 100 | 0.048 | 5,050 | 95.0 | 6.57 | 0.0 | 0.9083 | 9.91 |
| uniform | 100 | 0.125 | 5,050 | 99.0 | 6.63 | 0.0 | 0.9583 | 11.38 |
| uniform | 1000 | 0.08 | 500,500 | 8,514.0 | 13.06 | 0.0 | 0.9833 | 23.15 |
| uniform | 1000 | 0.048 | 500,500 | 4,760.0 | 12.22 | 0.0 | 0.95 | 21.18 |
| uniform | 1000 | 0.125 | 500,500 | 13,216.0 | 13.69 | 0.0 | 0.9583 | 23.92 |
| census_age | 100 | 0.08 | 5,050 | 72.0 | 6.17 | 0.0 | 0.9667 | 8.88 |
| census_age | 100 | 0.048 | 5,050 | 45.5 | 5.51 | 0.0083 | 0.9833 | 8.09 |
| census_age | 100 | 0.125 | 5,050 | 90.0 | 6.49 | 0.0 | 0.925 | 9.68 |
| census_age | 1000 | 0.08 | 500,500 | 6,275.0 | 12.62 | 0.0 | 0.9833 | 22.07 |
| census_age | 1000 | 0.048 | 500,500 | 3,323.5 | 11.7 | 0.0 | 0.9583 | 20.25 |
| census_age | 1000 | 0.125 | 500,500 | 8,325.0 | 13.02 | 0.0 | 0.9417 | 22.99 |
| zipf | 100 | 0.08 | 5,050 | 35.5 | 5.15 | 0.0 | 0.9417 | 8.01 |
| zipf | 100 | 0.048 | 5,050 | 25.5 | 4.67 | 0.0083 | 0.9833 | 6.81 |
| zipf | 100 | 0.125 | 5,050 | 66.5 | 6.06 | 0.0 | 0.9667 | 9.23 |
| zipf | 1000 | 0.08 | 500,500 | 3,475.5 | 11.76 | 0.0 | 0.9417 | 21.24 |
| zipf | 1000 | 0.048 | 500,500 | 2,577.5 | 11.33 | 0.0 | 0.9583 | 19.7 |
| zipf | 1000 | 0.125 | 500,500 | 6,190.5 | 12.6 | 0.0 | 0.925 | 22.58 |
| lognormal | 100 | 0.08 | 5,050 | 28.0 | 4.81 | 0.0 | 0.975 | 7.6 |
| lognormal | 100 | 0.048 | 5,050 | 17.0 | 4.09 | 0.0 | 0.95 | 6.11 |
| lognormal | 100 | 0.125 | 5,050 | 45.0 | 5.49 | 0.0 | 0.9333 | 8.9 |
| lognormal | 1000 | 0.08 | 500,500 | 2,524.0 | 11.3 | 0.0 | 0.95 | 20.28 |
| lognormal | 1000 | 0.048 | 500,500 | 1,504.0 | 10.55 | 0.0 | 0.95 | 19.46 |
| lognormal | 1000 | 0.125 | 500,500 | 3,906.5 | 11.93 | 0.0 | 0.9583 | 22.13 |

## B_no_width_prior

| hist | d | eps | #ranges | median cand | median bits | frac unique | coverage | pair bits |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| uniform | 100 | 0.125 | 5,050 | 99.0 | 6.63 | 0.0 | 0.9167 | 9.86 |
| uniform | 1000 | 0.125 | 500,500 | 13,682.5 | 13.74 | 0.0 | 0.9417 | 23.52 |
| census_age | 100 | 0.125 | 5,050 | 131.5 | 7.04 | 0.0 | 0.8833 | 11.76 |
| census_age | 1000 | 0.125 | 500,500 | 12,887.5 | 13.65 | 0.0 | 0.95 | 24.73 |
| zipf | 100 | 0.125 | 5,050 | 128.5 | 7.01 | 0.0 | 0.9583 | 12.19 |
| zipf | 1000 | 0.125 | 500,500 | 14,450.5 | 13.82 | 0.0 | 0.9917 | 23.47 |
| lognormal | 100 | 0.125 | 5,050 | 154.5 | 7.27 | 0.0 | 0.9667 | 12.93 |
| lognormal | 1000 | 0.125 | 500,500 | 18,254.0 | 14.16 | 0.0 | 0.975 | 23.6 |

## C_public_aux

| hist | d | eps | #ranges | median cand | median bits | frac unique | coverage | pair bits |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| uniform | 100 | 0.125 | 5,050 | 129.5 | 7.02 | 0.0 | 0.825 | 10.85 |
| uniform | 1000 | 0.125 | 500,500 | 14,152.5 | 13.79 | 0.0 | 0.8167 | 24.42 |
| census_age | 100 | 0.125 | 5,050 | 87.0 | 6.44 | 0.0 | 0.7583 | 9.78 |
| census_age | 1000 | 0.125 | 500,500 | 10,243.5 | 13.32 | 0.0 | 0.7083 | 23.15 |
| zipf | 100 | 0.125 | 5,050 | 55.0 | 5.78 | 0.0 | 0.825 | 8.48 |
| zipf | 1000 | 0.125 | 500,500 | 5,905.0 | 12.53 | 0.0 | 0.625 | 22.47 |
| lognormal | 100 | 0.125 | 5,050 | 42.0 | 5.39 | 0.0 | 0.7333 | 8.6 |
| lognormal | 1000 | 0.125 | 500,500 | 3,668.5 | 11.84 | 0.0 | 0.6167 | 22.09 |

## D_unmodelled_bias

| hist | d | eps | #ranges | median cand | median bits | frac unique | coverage | pair bits |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| uniform | 100 | 0.125 | 5,050 | 183.0 | 7.52 | 0.0 | 0.6333 | 10.78 |
| uniform | 1000 | 0.125 | 500,500 | 12,786.0 | 13.64 | 0.0 | 0.5667 | 23.65 |
| census_age | 100 | 0.125 | 5,050 | 86.0 | 6.43 | 0.0 | 0.5417 | 8.71 |
| census_age | 1000 | 0.125 | 500,500 | 9,238.0 | 13.17 | 0.0 | 0.65 | 23.19 |
| zipf | 100 | 0.125 | 5,050 | 63.5 | 5.99 | 0.0 | 0.5583 | 9.39 |
| zipf | 1000 | 0.125 | 500,500 | 6,152.0 | 12.59 | 0.0 | 0.575 | 22.35 |
| lognormal | 100 | 0.125 | 5,050 | 45.0 | 5.49 | 0.0 | 0.5167 | 8.57 |
| lognormal | 1000 | 0.125 | 500,500 | 3,852.0 | 11.91 | 0.0 | 0.6333 | 21.97 |

## E_modelled_bias

| hist | d | eps | #ranges | median cand | median bits | frac unique | coverage | pair bits |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| uniform | 100 | 0.125 | 5,050 | 99.0 | 6.63 | 0.0 | 0.9333 | 11.25 |
| uniform | 1000 | 0.125 | 500,500 | 14,968.0 | 13.87 | 0.0 | 0.9583 | 24.24 |
| census_age | 100 | 0.125 | 5,050 | 95.0 | 6.57 | 0.0 | 0.95 | 9.63 |
| census_age | 1000 | 0.125 | 500,500 | 8,654.5 | 13.08 | 0.0 | 0.9667 | 23.45 |
| zipf | 100 | 0.125 | 5,050 | 66.0 | 6.04 | 0.0 | 0.9417 | 9.33 |
| zipf | 1000 | 0.125 | 500,500 | 6,213.5 | 12.6 | 0.0 | 0.9333 | 22.43 |
| lognormal | 100 | 0.125 | 5,050 | 45.0 | 5.49 | 0.0 | 0.9583 | 8.54 |
| lognormal | 1000 | 0.125 | 500,500 | 3,886.0 | 11.92 | 0.0 | 0.9667 | 22.07 |

## G_prior_gain: bits the prior's skew actually buys

`gain` = median_bits(uniform control) - median_bits(this prior) at the
same domain size and tolerance: the positional information the prior
contributes beyond knowing the range's width.  A gain near 0 means the
prior is worthless at that measurement noise.

| hist | d | eps | bits (uniform control) | bits (this prior) | gain |
| --- | --- | --- | --- | --- | --- |
| census_age | 100 | 0.08 | 6.58 | 6.17 | 0.41 |
| census_age | 100 | 0.048 | 6.57 | 5.51 | 1.06 |
| census_age | 100 | 0.125 | 6.63 | 6.49 | 0.14 |
| census_age | 1000 | 0.08 | 13.06 | 12.62 | 0.44 |
| census_age | 1000 | 0.048 | 12.22 | 11.7 | 0.52 |
| census_age | 1000 | 0.125 | 13.69 | 13.02 | 0.67 |
| zipf | 100 | 0.08 | 6.58 | 5.15 | 1.43 |
| zipf | 100 | 0.048 | 6.57 | 4.67 | 1.9 |
| zipf | 100 | 0.125 | 6.63 | 6.06 | 0.57 |
| zipf | 1000 | 0.08 | 13.06 | 11.76 | 1.3 |
| zipf | 1000 | 0.048 | 12.22 | 11.33 | 0.89 |
| zipf | 1000 | 0.125 | 13.69 | 12.6 | 1.09 |
| lognormal | 100 | 0.08 | 6.58 | 4.81 | 1.77 |
| lognormal | 100 | 0.048 | 6.57 | 4.09 | 2.48 |
| lognormal | 100 | 0.125 | 6.63 | 5.49 | 1.14 |
| lognormal | 1000 | 0.08 | 13.06 | 11.3 | 1.76 |
| lognormal | 1000 | 0.048 | 12.22 | 10.55 | 1.67 |
| lognormal | 1000 | 0.125 | 13.69 | 11.93 | 1.76 |

## F_chain: linked episodes (Stage-D window) shrink the space

`joint_bits` = log2 #assignments of value ranges to the k linked
episodes consistent with all observed volumes AND the binary overlap
constraints; `independent_bits` is the same without the links.
`truth_survives` = fraction of chains where the true assignment is
still in every candidate set (hard-constraint soundness).

Rows with `n/a` are domains where the volume-consistent candidate set
is too large to enumerate exactly (> CAND_CAP); a truncated set would
bias the DP, so no number is reported for them.

| hist | d | k | joint bits | indep bits | saved | bits/episode | truth survives | chains |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| uniform | 100 | 1 | 7.52 | 7.52 | 0.0 | 7.52 | 0.95 | 20 |
| uniform | 100 | 2 | 10.85 | 14.17 | 3.32 | 5.43 | 0.9 | 20 |
| uniform | 100 | 3 | 15.21 | 21.24 | 6.03 | 5.07 | 0.8 | 20 |
| uniform | 100 | 4 | 18.75 | 28.29 | 9.54 | 4.69 | 0.75 | 20 |
| uniform | 1000 | 1 | 13.78 | 13.78 | 0.0 | 13.78 | 0.929 | 14 |
| uniform | 1000 | 2 | 24.3 | 27.36 | 3.06 | 12.15 | 0.857 | 14 |
| uniform | 1000 | 3 | 34.81 | 40.96 | 6.14 | 11.6 | 0.857 | 14 |
| uniform | 1000 | 4 | 45.62 | 54.8 | 9.18 | 11.41 | 0.857 | 14 |
| census_age | 100 | 1 | 6.88 | 6.88 | 0.0 | 6.88 | 0.9 | 20 |
| census_age | 100 | 2 | 10.34 | 13.43 | 3.08 | 5.17 | 0.9 | 20 |
| census_age | 100 | 3 | 13.71 | 20.12 | 6.41 | 4.57 | 0.9 | 20 |
| census_age | 100 | 4 | 17.6 | 26.91 | 9.31 | 4.4 | 0.9 | 20 |
| census_age | 1000 | 1 | 13.31 | 13.31 | 0.0 | 13.31 | 1.0 | 20 |
| census_age | 1000 | 2 | 23.32 | 26.38 | 3.06 | 11.66 | 1.0 | 20 |
| census_age | 1000 | 3 | 32.73 | 39.29 | 6.56 | 10.91 | 0.85 | 20 |
| census_age | 1000 | 4 | 43.4 | 52.41 | 9.01 | 10.85 | 0.85 | 20 |
| zipf | 100 | 1 | 6.44 | 6.44 | 0.0 | 6.44 | 0.95 | 20 |
| zipf | 100 | 2 | 8.75 | 11.9 | 3.15 | 4.38 | 0.9 | 20 |
| zipf | 100 | 3 | 12.34 | 18.16 | 5.82 | 4.11 | 0.9 | 20 |
| zipf | 100 | 4 | 15.67 | 24.33 | 8.66 | 3.92 | 0.8 | 20 |
| zipf | 1000 | 1 | 12.48 | 12.48 | 0.0 | 12.48 | 0.9 | 20 |
| zipf | 1000 | 2 | 22.6 | 25.11 | 2.51 | 11.3 | 0.8 | 20 |
| zipf | 1000 | 3 | 32.29 | 37.34 | 5.06 | 10.76 | 0.8 | 20 |
| zipf | 1000 | 4 | 42.46 | 49.57 | 7.11 | 10.62 | 0.8 | 20 |
| lognormal | 100 | 1 | 5.44 | 5.44 | 0.0 | 5.44 | 0.95 | 20 |
| lognormal | 100 | 2 | 8.85 | 10.92 | 2.08 | 4.42 | 0.9 | 20 |
| lognormal | 100 | 3 | 12.42 | 16.34 | 3.92 | 4.14 | 0.85 | 20 |
| lognormal | 100 | 4 | 15.57 | 21.76 | 6.19 | 3.89 | 0.8 | 20 |
| lognormal | 1000 | 1 | 12.12 | 12.12 | 0.0 | 12.12 | 0.95 | 20 |
| lognormal | 1000 | 2 | 22.34 | 24.03 | 1.7 | 11.17 | 0.8 | 20 |
| lognormal | 1000 | 3 | 31.85 | 36.22 | 4.37 | 10.62 | 0.7 | 20 |
| lognormal | 1000 | 4 | 42.35 | 48.04 | 5.68 | 10.59 | 0.7 | 20 |
