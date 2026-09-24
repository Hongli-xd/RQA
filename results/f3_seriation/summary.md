# F3: recovering the order of queried ranges by spectral seriation

Order is recovered from estimated overlap magnitudes only. No prior, no
auxiliary dataset, no plaintext. Scored as |Spearman| against the true range
starts, per connected component, sign-free (seriation is defined up to
reflection). Components come from the linkage window, which fragments the
graph by construction.

Components smaller than 4 nodes are dropped: chance dominates them.

| arm | comps | episodes ordered | largest comp | pair concordance | permutation null | above null |
| --- | --- | --- | --- | --- | --- | --- |
| baseline gate, mass weights | 23 | 167 | 18 | 0.675 | 0.616 | **+0.059** |
| baseline gate, topology only | 23 | 167 | 18 | 0.669 | 0.617 | **+0.053** |
| baseline gate, weights SHUFFLED (null) | 23 | 167 | 18 | 0.668 | 0.618 | **+0.050** |
| poisson gate, excess weights | 14 | 72 | 10 | 0.736 | 0.666 | **+0.069** |
| poisson gate, mass weights | 14 | 72 | 10 | 0.736 | 0.659 | **+0.077** |
| poisson gate, topology only | 14 | 72 | 10 | 0.712 | 0.663 | **+0.049** |
| poisson gate, weights SHUFFLED (null) | 14 | 72 | 10 | 0.727 | 0.662 | **+0.065** |
| ORACLE pairs, true overlap weights | 9 | 47 | 11 | 0.734 | 0.664 | **+0.069** |

`pair concordance` counts node PAIRS ordered correctly, reflection-free;
`permutation null` is the same statistic on random orders of the SAME
components, so `above null` is the only number that carries information.

Reading: the SHUFFLED arms are a second null - same components, same edges, the
magnitudes permuted. The `topology only` arms show what unweighted overlap
structure alone gives, so the gap between them and the weighted arms is what
magnitude estimation buys. The ORACLE arm is the ceiling if pair selection
and magnitudes were perfect, i.e. how much of the residual error is the
attack's and how much is seriation's.
