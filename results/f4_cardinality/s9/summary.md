# F4: error decomposition of Stage C's cardinality estimate

trace `range_seed9_waffle.tsv`; 68 matched episodes; median detected span 4 batches vs true 2.

Each arm replaces ONE input of the estimator with its ground-truth version.
The arm whose error drops is the one worth attacking.

| estimator | median rel. err | mean rel. err | what it isolates |
| --- | --- | --- | --- |
| deployed (recovered series, detected span) | **0.141** | 0.160 | - |
| integrate-to-baseline (attack-side, noise=3.0) | **0.103** | 0.131 | deferred background returning (median window 6 batches) |
| saturation-corrected [REJECTED] | 0.523 | 0.541 | a wrong model, kept as the record |
| true span, recovered series | 0.378 | 0.374 | Stage B's span error |
| detected span, true miss series | 0.100 | 0.123 | Stage A's series error |
| true span, true series | 0.344 | 0.336 | both |
| episode's own read mass (floor) | 0.000 | 0.005 | the background-subtraction floor |

Signed bias (median m_hat - target): deployed -9.8, integrate-to-baseline -0.5, saturation-corrected +43.6.

The last row is not an estimator: it counts only the reads that really
belong to the episode, so it is what perfect background separation would
give. Any residual there is the target definition itself (a key read
inside the span that was already counted as cached at the start).
