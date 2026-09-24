# F1: the alpha-recency channel

trace `range_seed8_waffle.tsv`; spike window self-calibrated (bg_mult=4.0); local background half-window 40.

Target: how many of a detected episode's keys were client-read in the
preceding tau batches (a graded overlap magnitude).

| tau | spike | bg bin height | eps | eval ceiling rho | E1 ratio rho | E2 excess rho | E2 excess r | E2 shuffled-alpha null | E2 burst control |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| 40 | 49-51 | 5748 | 55 | 0.795 | 0.662 | **0.315** | 0.156 | 0.137 | 0.914 |
| 60 | 49-51 | 5748 | 55 | 0.0 | 0.0 | **0.255** | 0.168 | -0.226 | 0.918 |
| 90 | 49-51 | 5748 | 55 | 0.0 | 0.0 | **0.361** | 0.302 | -0.039 | 0.946 |
| 140 | 49-51 | 5748 | 55 | 0.0 | 0.0 | **0.372** | 0.325 | -0.182 | 0.945 |

## Spike-window robustness (perturbing the attack's own calibration)

| forced window | what it is | E1 ratio rho | E2 excess rho |
| --- | --- | --- | --- |
| 50-50 | narrowed (leaks fakes) | 0.03 | **0.315** |
| 49-51 | self-calibrated | 0.662 | **0.315** |
| 48-52 | widened | 0.729 | **0.315** |
| 45-58 | very wide | 0.714 | **0.315** |

E2 is invariant because for tau below the flush age the fake population
lies entirely above tau, so excluding it or not cannot change a count of
reads with alpha < tau; the window only ever touched E1's denominator.
E2 therefore needs no fake filter, only tau << flush age - and the flush
age is the quantity Stage A recovers most reliably (81/88, 50/50,
102/100, 256/256 across scales).

Baseline to beat: the existing attack's overlap MAGNITUDE quality is
Pearson 0.34-0.52 with Stage-D pair precision 0.40-0.50
(results/staged_precision/summary.md).

Honest reading:
- E1 is not inherently worse: with a correctly calibrated window it matches E2.
  What separates them is robustness, as the table above shows.
- E2 still conflates episode overlap with hot-key background traffic. That is
  where a popularity prior has a real job - subtracting the confound - as
  opposed to localising ranges, which the volume channel cannot do either
  (see results/prior_matching/summary.md).
- the burst control is NOT a false positive: E2 measures recency, which random
  bursts also exhibit when they happen to touch recently read hot keys. E2
  supports an overlap-MAGNITUDE claim, not a range-structure claim - the latter
  stays with Stage D's co-parent concentration. E2's own controls are the
  shuffled-alpha null (collapses) plus an overlap_bias=0 workload (not yet run).
- E2 gives magnitude only; WHICH earlier episode the overlap is with still
  requires Stage D. The two compose, neither replaces the other.
- one config, one seed, 24 episodes. The matrix (4 scales x 3 seeds) and the
  range-free control must reproduce this before it is a claim.
