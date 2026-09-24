# Prior-matching identifiability ceiling

queries/cell=80, widths=2%-10% of domain, N=1,000,000, seed=7

`median_bits` = log2 of the number of value ranges consistent with one
observed volume: the positional entropy a single Stage-C cardinality
leaves. 0 bits = that query's range is pinned by volume alone.
`coverage` = fraction of queries whose true range still matches under the
auxiliary histogram (a coverage collapse means the matcher rejects the
truth, i.e. it returns a CONFIDENT WRONG answer).

## A_ceiling

| hist | d | eps | #ranges | median cand | median bits | frac unique | coverage | pair bits |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| uniform | 100 | 0.03 | 5,050 | 94.0 | 6.55 | 0.0 | 0.9625 | 10.09 |
| uniform | 100 | 0.125 | 5,050 | 98.0 | 6.61 | 0.0 | 0.95 | 10.9 |
| uniform | 1000 | 0.03 | 500,500 | 3,678.0 | 11.84 | 0.0 | 0.95 | 19.81 |
| uniform | 1000 | 0.125 | 500,500 | 12,705.0 | 13.63 | 0.0 | 0.95 | 24.2 |
| uniform | 10000 | 0.03 | 50,005,000 | 338,184.0 | 18.37 | 0.0 | 0.975 | n/a (over cap) |
| uniform | 10000 | 0.125 | 50,005,000 | 1,309,273.0 | 20.32 | 0.0 | 0.95 | n/a (over cap) |
| census_age | 100 | 0.03 | 5,050 | 28.0 | 4.81 | 0.0 | 0.9625 | 6.14 |
| census_age | 100 | 0.125 | 5,050 | 89.0 | 6.48 | 0.0 | 0.95 | 10.07 |
| census_age | 1000 | 0.03 | 500,500 | 2,079.5 | 11.02 | 0.0 | 0.95 | 18.96 |
| census_age | 1000 | 0.125 | 500,500 | 9,304.0 | 13.18 | 0.0 | 0.9875 | 23.04 |
| census_age | 10000 | 0.03 | 50,005,000 | 212,343.5 | 17.7 | 0.0 | 1.0 | n/a (over cap) |
| census_age | 10000 | 0.125 | 50,005,000 | 797,317.5 | 19.6 | 0.0 | 0.9625 | n/a (over cap) |
| zipf | 100 | 0.03 | 5,050 | 17.0 | 4.09 | 0.0375 | 0.9125 | 5.17 |
| zipf | 100 | 0.125 | 5,050 | 66.5 | 6.06 | 0.0 | 0.95 | 9.51 |
| zipf | 1000 | 0.03 | 500,500 | 1,621.0 | 10.66 | 0.0 | 0.975 | 18.34 |
| zipf | 1000 | 0.125 | 500,500 | 7,318.5 | 12.84 | 0.0 | 0.975 | 23.46 |
| zipf | 10000 | 0.03 | 50,005,000 | 125,141.5 | 16.93 | 0.0 | 0.9625 | n/a (over cap) |
| zipf | 10000 | 0.125 | 50,005,000 | 605,366.5 | 19.21 | 0.0 | 0.9875 | n/a (over cap) |
| lognormal | 100 | 0.03 | 5,050 | 11.0 | 3.46 | 0.0 | 0.9375 | 4.12 |
| lognormal | 100 | 0.125 | 5,050 | 45.0 | 5.49 | 0.0 | 0.975 | 8.6 |
| lognormal | 1000 | 0.03 | 500,500 | 975.0 | 9.93 | 0.0 | 0.95 | 17.98 |
| lognormal | 1000 | 0.125 | 500,500 | 3,816.0 | 11.9 | 0.0 | 0.9625 | 22.1 |
| lognormal | 10000 | 0.03 | 50,005,000 | 90,004.5 | 16.46 | 0.0 | 0.975 | n/a (over cap) |
| lognormal | 10000 | 0.125 | 50,005,000 | 419,676.0 | 18.68 | 0.0 | 0.95 | n/a (over cap) |

## B_no_width_prior

| hist | d | eps | #ranges | median cand | median bits | frac unique | coverage | pair bits |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| uniform | 100 | 0.125 | 5,050 | 139.0 | 7.12 | 0.0 | 0.95 | 10.75 |
| uniform | 1000 | 0.125 | 500,500 | 14,984.0 | 13.87 | 0.0 | 0.925 | 24.31 |
| uniform | 10000 | 0.125 | 50,005,000 | 1,510,823.0 | 20.53 | 0.0 | 0.9125 | n/a (over cap) |
| census_age | 100 | 0.125 | 5,050 | 127.5 | 6.99 | 0.0 | 0.975 | 12.31 |
| census_age | 1000 | 0.125 | 500,500 | 12,996.5 | 13.67 | 0.0 | 0.9625 | 24.41 |
| census_age | 10000 | 0.125 | 50,005,000 | 1,441,442.0 | 20.46 | 0.0 | 0.9875 | n/a (over cap) |
| zipf | 100 | 0.125 | 5,050 | 139.5 | 7.12 | 0.0 | 0.925 | 10.72 |
| zipf | 1000 | 0.125 | 500,500 | 14,255.0 | 13.8 | 0.0 | 0.9 | 23.36 |
| zipf | 10000 | 0.125 | 50,005,000 | 1,341,431.0 | 20.36 | 0.0 | 0.925 | n/a (over cap) |
| lognormal | 100 | 0.125 | 5,050 | 147.5 | 7.2 | 0.0 | 0.95 | 13.37 |
| lognormal | 1000 | 0.125 | 500,500 | 16,000.0 | 13.97 | 0.0 | 0.9625 | 24.65 |
| lognormal | 10000 | 0.125 | 50,005,000 | 1,171,043.5 | 20.16 | 0.0 | 0.95 | n/a (over cap) |

## C_public_aux

| hist | d | eps | #ranges | median cand | median bits | frac unique | coverage | pair bits |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| uniform | 100 | 0.125 | 5,050 | 131.5 | 7.04 | 0.0 | 0.8375 | 10.83 |
| uniform | 1000 | 0.125 | 500,500 | 13,989.5 | 13.77 | 0.0 | 0.675 | 24.31 |
| uniform | 10000 | 0.125 | 50,005,000 | 1,328,378.5 | 20.34 | 0.0 | 0.75 | n/a (over cap) |
| census_age | 100 | 0.125 | 5,050 | 86.0 | 6.43 | 0.0 | 0.8 | 10.11 |
| census_age | 1000 | 0.125 | 500,500 | 8,802.0 | 13.1 | 0.0 | 0.875 | 22.92 |
| census_age | 10000 | 0.125 | 50,005,000 | 935,803.5 | 19.84 | 0.0 | 0.7125 | n/a (over cap) |
| zipf | 100 | 0.125 | 5,050 | 53.5 | 5.74 | 0.0 | 0.725 | 9.51 |
| zipf | 1000 | 0.125 | 500,500 | 6,085.0 | 12.57 | 0.0 | 0.7375 | 22.24 |
| zipf | 10000 | 0.125 | 50,005,000 | 492,694.5 | 18.91 | 0.0 | 0.175 | n/a (over cap) |
| lognormal | 100 | 0.125 | 5,050 | 41.5 | 5.38 | 0.0 | 0.7 | 8.74 |
| lognormal | 1000 | 0.125 | 500,500 | 3,654.5 | 11.84 | 0.0 | 0.7875 | 21.84 |
| lognormal | 10000 | 0.125 | 50,005,000 | 372,411.0 | 18.51 | 0.0 | 0.6375 | n/a (over cap) |

## D_unmodelled_bias

| hist | d | eps | #ranges | median cand | median bits | frac unique | coverage | pair bits |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| uniform | 100 | 0.125 | 5,050 | 98.0 | 6.61 | 0.0 | 0.625 | 11.17 |
| uniform | 1000 | 0.125 | 500,500 | 11,895.5 | 13.54 | 0.0 | 0.6 | 24.16 |
| uniform | 10000 | 0.125 | 50,005,000 | 1,250,700.0 | 20.25 | 0.0 | 0.5875 | n/a (over cap) |
| census_age | 100 | 0.125 | 5,050 | 89.0 | 6.48 | 0.0 | 0.5375 | 9.37 |
| census_age | 1000 | 0.125 | 500,500 | 7,944.5 | 12.96 | 0.0 | 0.5375 | 22.59 |
| census_age | 10000 | 0.125 | 50,005,000 | 912,111.0 | 19.8 | 0.0 | 0.5 | n/a (over cap) |
| zipf | 100 | 0.125 | 5,050 | 65.5 | 6.03 | 0.0 | 0.6125 | 9.24 |
| zipf | 1000 | 0.125 | 500,500 | 6,263.0 | 12.61 | 0.0 | 0.5625 | 22.24 |
| zipf | 10000 | 0.125 | 50,005,000 | 504,318.5 | 18.94 | 0.0 | 0.525 | n/a (over cap) |
| lognormal | 100 | 0.125 | 5,050 | 45.5 | 5.51 | 0.0 | 0.5875 | 8.8 |
| lognormal | 1000 | 0.125 | 500,500 | 3,908.0 | 11.93 | 0.0 | 0.6125 | 22.03 |
| lognormal | 10000 | 0.125 | 50,005,000 | 375,612.5 | 18.52 | 0.0 | 0.525 | n/a (over cap) |

## E_modelled_bias

| hist | d | eps | #ranges | median cand | median bits | frac unique | coverage | pair bits |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| uniform | 100 | 0.125 | 5,050 | 99.0 | 6.63 | 0.0 | 0.95 | 10.04 |
| uniform | 1000 | 0.125 | 500,500 | 11,430.0 | 13.48 | 0.0 | 0.9625 | 24.19 |
| uniform | 10000 | 0.125 | 50,005,000 | 1,318,747.5 | 20.33 | 0.0 | 0.9375 | n/a (over cap) |
| census_age | 100 | 0.125 | 5,050 | 92.5 | 6.53 | 0.0 | 0.9375 | 9.93 |
| census_age | 1000 | 0.125 | 500,500 | 8,264.5 | 13.01 | 0.0 | 0.9625 | 23.16 |
| census_age | 10000 | 0.125 | 50,005,000 | 896,568.5 | 19.77 | 0.0 | 0.9625 | n/a (over cap) |
| zipf | 100 | 0.125 | 5,050 | 76.5 | 6.26 | 0.0 | 0.975 | 9.88 |
| zipf | 1000 | 0.125 | 500,500 | 5,575.0 | 12.44 | 0.0 | 0.9125 | 22.63 |
| zipf | 10000 | 0.125 | 50,005,000 | 660,597.0 | 19.33 | 0.0 | 0.9625 | n/a (over cap) |
| lognormal | 100 | 0.125 | 5,050 | 44.0 | 5.46 | 0.0 | 0.9625 | 8.54 |
| lognormal | 1000 | 0.125 | 500,500 | 4,315.0 | 12.08 | 0.0 | 0.925 | 22.18 |
| lognormal | 10000 | 0.125 | 50,005,000 | 390,278.5 | 18.57 | 0.0 | 0.95 | n/a (over cap) |

## G_prior_gain: bits the prior's skew actually buys

`gain` = median_bits(uniform control) - median_bits(this prior) at the
same domain size and tolerance: the positional information the prior
contributes beyond knowing the range's width.  A gain near 0 means the
prior is worthless at that measurement noise.

| hist | d | eps | bits (uniform control) | bits (this prior) | gain |
| --- | --- | --- | --- | --- | --- |
| census_age | 100 | 0.03 | 6.55 | 4.81 | 1.74 |
| census_age | 100 | 0.125 | 6.61 | 6.48 | 0.13 |
| census_age | 1000 | 0.03 | 11.84 | 11.02 | 0.82 |
| census_age | 1000 | 0.125 | 13.63 | 13.18 | 0.45 |
| census_age | 10000 | 0.03 | 18.37 | 17.7 | 0.67 |
| census_age | 10000 | 0.125 | 20.32 | 19.6 | 0.72 |
| zipf | 100 | 0.03 | 6.55 | 4.09 | 2.46 |
| zipf | 100 | 0.125 | 6.61 | 6.06 | 0.55 |
| zipf | 1000 | 0.03 | 11.84 | 10.66 | 1.18 |
| zipf | 1000 | 0.125 | 13.63 | 12.84 | 0.79 |
| zipf | 10000 | 0.03 | 18.37 | 16.93 | 1.44 |
| zipf | 10000 | 0.125 | 20.32 | 19.21 | 1.11 |
| lognormal | 100 | 0.03 | 6.55 | 3.46 | 3.09 |
| lognormal | 100 | 0.125 | 6.61 | 5.49 | 1.12 |
| lognormal | 1000 | 0.03 | 11.84 | 9.93 | 1.91 |
| lognormal | 1000 | 0.125 | 13.63 | 11.9 | 1.73 |
| lognormal | 10000 | 0.03 | 18.37 | 16.46 | 1.91 |
| lognormal | 10000 | 0.125 | 20.32 | 18.68 | 1.64 |

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
| uniform | 100 | 1 | 6.61 | 6.61 | 0.0 | 6.61 | 0.933 | 30 |
| uniform | 100 | 2 | 10.91 | 14.1 | 3.19 | 5.45 | 0.9 | 30 |
| uniform | 100 | 3 | 14.53 | 20.78 | 6.26 | 4.84 | 0.833 | 30 |
| uniform | 100 | 4 | 18.06 | 28.05 | 9.98 | 4.52 | 0.833 | 30 |
| uniform | 100 | 5 | 21.87 | 34.91 | 13.03 | 4.37 | 0.833 | 30 |
| uniform | 100 | 6 | 25.61 | 41.9 | 16.29 | 4.27 | 0.833 | 30 |
| uniform | 1000 | 1 | 13.59 | 13.59 | 0.0 | 13.59 | 0.895 | 19 |
| uniform | 1000 | 2 | 23.99 | 27.08 | 3.09 | 11.99 | 0.895 | 19 |
| uniform | 1000 | 3 | 34.41 | 40.53 | 6.13 | 11.47 | 0.895 | 19 |
| uniform | 1000 | 4 | 43.91 | 53.71 | 9.8 | 10.98 | 0.895 | 19 |
| uniform | 1000 | 5 | 54.35 | 67.58 | 13.23 | 10.87 | 0.895 | 19 |
| uniform | 1000 | 6 | 64.53 | 80.81 | 16.29 | 10.75 | 0.737 | 19 |
| uniform | 10000 | 1 | n/a | n/a | n/a | n/a | n/a | 0 scored / 30 over cap |
| uniform | 10000 | 2 | n/a | n/a | n/a | n/a | n/a | 0 scored / 30 over cap |
| uniform | 10000 | 3 | n/a | n/a | n/a | n/a | n/a | 0 scored / 30 over cap |
| uniform | 10000 | 4 | n/a | n/a | n/a | n/a | n/a | 0 scored / 30 over cap |
| uniform | 10000 | 5 | n/a | n/a | n/a | n/a | n/a | 0 scored / 30 over cap |
| uniform | 10000 | 6 | n/a | n/a | n/a | n/a | n/a | 0 scored / 30 over cap |
| census_age | 100 | 1 | 6.53 | 6.53 | 0.0 | 6.53 | 0.967 | 30 |
| census_age | 100 | 2 | 9.81 | 12.88 | 3.06 | 4.91 | 0.967 | 30 |
| census_age | 100 | 3 | 12.66 | 19.44 | 6.78 | 4.22 | 0.967 | 30 |
| census_age | 100 | 4 | 15.48 | 25.77 | 10.29 | 3.87 | 0.933 | 30 |
| census_age | 100 | 5 | 18.72 | 32.2 | 13.48 | 3.74 | 0.833 | 30 |
| census_age | 100 | 6 | 22.02 | 38.05 | 16.03 | 3.67 | 0.8 | 30 |
| census_age | 1000 | 1 | 13.25 | 13.25 | 0.0 | 13.25 | 0.967 | 30 |
| census_age | 1000 | 2 | 23.23 | 26.07 | 2.84 | 11.61 | 0.933 | 30 |
| census_age | 1000 | 3 | 33.44 | 39.33 | 5.89 | 11.15 | 0.933 | 30 |
| census_age | 1000 | 4 | 43.98 | 52.61 | 8.63 | 11.0 | 0.867 | 30 |
| census_age | 1000 | 5 | 53.42 | 64.99 | 11.57 | 10.68 | 0.833 | 30 |
| census_age | 1000 | 6 | 64.4 | 78.06 | 13.66 | 10.73 | 0.733 | 30 |
| census_age | 10000 | 1 | n/a | n/a | n/a | n/a | n/a | 0 scored / 30 over cap |
| census_age | 10000 | 2 | n/a | n/a | n/a | n/a | n/a | 0 scored / 30 over cap |
| census_age | 10000 | 3 | n/a | n/a | n/a | n/a | n/a | 0 scored / 30 over cap |
| census_age | 10000 | 4 | n/a | n/a | n/a | n/a | n/a | 0 scored / 30 over cap |
| census_age | 10000 | 5 | n/a | n/a | n/a | n/a | n/a | 0 scored / 30 over cap |
| census_age | 10000 | 6 | n/a | n/a | n/a | n/a | n/a | 0 scored / 30 over cap |
| zipf | 100 | 1 | 6.0 | 6.0 | 0.0 | 6.0 | 0.833 | 30 |
| zipf | 100 | 2 | 9.05 | 11.78 | 2.73 | 4.52 | 0.833 | 30 |
| zipf | 100 | 3 | 12.6 | 17.81 | 5.21 | 4.2 | 0.833 | 30 |
| zipf | 100 | 4 | 15.76 | 24.02 | 8.26 | 3.94 | 0.767 | 30 |
| zipf | 100 | 5 | 18.91 | 30.24 | 11.33 | 3.78 | 0.767 | 30 |
| zipf | 100 | 6 | 22.49 | 36.32 | 13.83 | 3.75 | 0.733 | 30 |
| zipf | 1000 | 1 | 12.82 | 12.82 | 0.0 | 12.82 | 0.967 | 30 |
| zipf | 1000 | 2 | 22.41 | 25.13 | 2.72 | 11.2 | 0.933 | 30 |
| zipf | 1000 | 3 | 32.8 | 38.19 | 5.4 | 10.93 | 0.9 | 30 |
| zipf | 1000 | 4 | 42.8 | 50.91 | 8.11 | 10.7 | 0.867 | 30 |
| zipf | 1000 | 5 | 52.28 | 63.32 | 11.04 | 10.46 | 0.867 | 30 |
| zipf | 1000 | 6 | 62.55 | 75.91 | 13.36 | 10.43 | 0.867 | 30 |
| zipf | 10000 | 1 | n/a | n/a | n/a | n/a | n/a | 0 scored / 30 over cap |
| zipf | 10000 | 2 | n/a | n/a | n/a | n/a | n/a | 0 scored / 30 over cap |
| zipf | 10000 | 3 | n/a | n/a | n/a | n/a | n/a | 0 scored / 30 over cap |
| zipf | 10000 | 4 | n/a | n/a | n/a | n/a | n/a | 0 scored / 30 over cap |
| zipf | 10000 | 5 | n/a | n/a | n/a | n/a | n/a | 0 scored / 30 over cap |
| zipf | 10000 | 6 | n/a | n/a | n/a | n/a | n/a | 0 scored / 30 over cap |
| lognormal | 100 | 1 | 5.48 | 5.48 | 0.0 | 5.48 | 0.9 | 30 |
| lognormal | 100 | 2 | 8.59 | 11.15 | 2.55 | 4.3 | 0.833 | 30 |
| lognormal | 100 | 3 | 11.85 | 16.75 | 4.9 | 3.95 | 0.767 | 30 |
| lognormal | 100 | 4 | 14.81 | 22.33 | 7.51 | 3.7 | 0.767 | 30 |
| lognormal | 100 | 5 | 17.92 | 27.81 | 9.88 | 3.58 | 0.733 | 30 |
| lognormal | 100 | 6 | 19.99 | 33.33 | 13.34 | 3.33 | 0.7 | 30 |
| lognormal | 1000 | 1 | 12.12 | 12.12 | 0.0 | 12.12 | 0.933 | 30 |
| lognormal | 1000 | 2 | 22.1 | 24.2 | 2.09 | 11.05 | 0.933 | 30 |
| lognormal | 1000 | 3 | 32.24 | 36.1 | 3.86 | 10.75 | 0.867 | 30 |
| lognormal | 1000 | 4 | 42.52 | 47.95 | 5.44 | 10.63 | 0.8 | 30 |
| lognormal | 1000 | 5 | 51.6 | 59.89 | 8.29 | 10.32 | 0.8 | 30 |
| lognormal | 1000 | 6 | 61.52 | 71.82 | 10.29 | 10.25 | 0.8 | 30 |
| lognormal | 10000 | 1 | n/a | n/a | n/a | n/a | n/a | 0 scored / 30 over cap |
| lognormal | 10000 | 2 | n/a | n/a | n/a | n/a | n/a | 0 scored / 30 over cap |
| lognormal | 10000 | 3 | n/a | n/a | n/a | n/a | n/a | 0 scored / 30 over cap |
| lognormal | 10000 | 4 | n/a | n/a | n/a | n/a | n/a | 0 scored / 30 over cap |
| lognormal | 10000 | 5 | n/a | n/a | n/a | n/a | n/a | 0 scored / 30 over cap |
| lognormal | 10000 | 6 | n/a | n/a | n/a | n/a | n/a | 0 scored / 30 over cap |
