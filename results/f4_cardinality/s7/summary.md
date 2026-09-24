# F4: error decomposition of Stage C's cardinality estimate

trace `range_seed7_waffle.tsv`; 73 matched episodes; median detected span 4 batches vs true 2.

Each arm replaces ONE input of the estimator with its ground-truth version.
The arm whose error drops is the one worth attacking.

| estimator | median rel. err | mean rel. err | what it isolates |
| --- | --- | --- | --- |
| deployed (recovered series, detected span) | **0.139** | 0.150 | - |
| integrate-to-baseline (attack-side, noise=3.0) | **0.111** | 0.125 | deferred background returning (median window 6 batches) |
| saturation-corrected [REJECTED] | 0.548 | 0.532 | a wrong model, kept as the record |
| true span, recovered series | 0.350 | 0.357 | Stage B's span error |
| detected span, true miss series | 0.093 | 0.111 | Stage A's series error |
| true span, true series | 0.326 | 0.325 | both |
| episode's own read mass (floor) | 0.000 | 0.007 | the background-subtraction floor |

Signed bias (median m_hat - target): deployed -9.0, integrate-to-baseline -3.0, saturation-corrected +42.2.

The last row is not an estimator: it counts only the reads that really
belong to the episode, so it is what perfect background separation would
give. Any residual there is the target definition itself (a key read
inside the span that was already counted as cached at the start).
