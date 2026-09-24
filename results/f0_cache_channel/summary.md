# F0 probe: popularity -> visibility channel in Waffle

MECHANISM STUDY (reads simulation labels on purpose; not an attack stage).

- trace: `range_seed7_waffle.tsv`, batches: 1500, N=8192, C=512, B=128, f_D=16

## M4: is the cache a popularity set or a sweep buffer?

- predicted cache flush period C/(B-f_D) = 4.57 batches
- measured mean cache spell = 4.71 batches (median 4.47, sd 16.85, n=8192)
- a key is cached 6.24% of the time on average (C/N = 6.25%)

## Does popularity buy cache residence?

- Spearman(zipf weight, P(cached)) = +0.586
- Spearman(zipf weight, total reads) = +0.635  (reads are dominated by the fake sweep, which is popularity-BLIND)

| popularity decile | keys | mean zipf weight | mean P(cached) | mean reads | mean client reads |
| --- | --- | --- | --- | --- | --- |
| 1 | 0-818 | 8.14e-04 | 0.1153 | 34.7 | 26.05 |
| 2 | 819-1637 | 1.13e-04 | 0.0618 | 21.0 | 6.81 |
| 3 | 1638-2456 | 6.97e-05 | 0.0583 | 19.6 | 4.10 |
| 4 | 2457-3275 | 5.12e-05 | 0.0566 | 19.0 | 2.95 |
| 5 | 3276-4094 | 4.07e-05 | 0.0566 | 19.0 | 2.88 |
| 6 | 4095-4913 | 3.40e-05 | 0.0556 | 18.6 | 2.27 |
| 7 | 4914-5732 | 2.92e-05 | 0.0549 | 18.3 | 1.63 |
| 8 | 5733-6551 | 2.57e-05 | 0.0547 | 18.2 | 1.40 |
| 9 | 6552-7370 | 2.29e-05 | 0.0549 | 18.3 | 1.45 |
| 10 | 7371-8189 | 2.07e-05 | 0.0551 | 18.4 | 1.65 |

## Does a range's position in the popularity order change what the server sees?

- episodes: 24
- invisible fraction beta: mean 0.0523, median 0.0400, sd 0.0924, min 0.0000, max 0.4773
- Spearman(episode mean zipf weight, beta) = +0.249

Reading: |rho| near 0 with a small sd(beta) means the visible cardinality is
a nearly position-independent multiple of m - the adversary can calibrate the
bias away (helping Stage C) but learns nothing about WHERE the range is from
it.  A large |rho| would mean the opposite: visibility localises the range.
