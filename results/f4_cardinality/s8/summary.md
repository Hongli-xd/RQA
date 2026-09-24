# F4: error decomposition of Stage C's cardinality estimate

trace `range_seed8_waffle.tsv`; 69 matched episodes; median detected span 4 batches vs true 2.

Each arm replaces ONE input of the estimator with its ground-truth version.
The arm whose error drops is the one worth attacking.

| estimator | median rel. err | mean rel. err | what it isolates |
| --- | --- | --- | --- |
| deployed (recovered series, detected span) | **0.095** | 0.144 | - |
| integrate-to-baseline (attack-side, noise=3.0) | **0.058** | 0.099 | deferred background returning (median window 6 batches) |
| saturation-corrected [REJECTED] | 0.587 | 0.552 | a wrong model, kept as the record |
| true span, recovered series | 0.388 | 0.365 | Stage B's span error |
| detected span, true miss series | 0.086 | 0.105 | Stage A's series error |
| true span, true series | 0.328 | 0.323 | both |
| episode's own read mass (floor) | 0.000 | 0.016 | the background-subtraction floor |

Signed bias (median m_hat - target): deployed -8.0, integrate-to-baseline +0.0, saturation-corrected +43.7.

The last row is not an estimator: it counts only the reads that really
belong to the episode, so it is what perfect background separation would
give. Any residual there is the target definition itself (a key read
inside the span that was already counted as cached at the start).
