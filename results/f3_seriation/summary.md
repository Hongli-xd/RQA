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
| baseline gate, topology only | 23 | 167 | 18 | 0.669 | 0.617 | **+0.052** |
| baseline gate, weights SHUFFLED (null) | 23 | 167 | 18 | 0.669 | 0.616 | **+0.053** |
| poisson gate, excess weights | 14 | 72 | 10 | 0.736 | 0.662 | **+0.074** |
| poisson gate, topology only | 14 | 72 | 10 | 0.712 | 0.665 | **+0.047** |
| poisson gate, weights SHUFFLED (null) | 14 | 72 | 10 | 0.725 | 0.667 | **+0.058** |
| ORACLE among candidates | 9 | 47 | 11 | 0.734 | 0.660 | **+0.073** |
| ORACLE full true graph | 18 | 120 | 13 | 0.899 | 0.618 | **+0.281** |

`pair concordance` counts node PAIRS ordered correctly, reflection-free;
`permutation null` is the same statistic on random orders of the SAME
components, so `above null` is the only number that carries information.

The two ORACLE arms answer different questions. `among candidates` keeps
true pairs only where the attack produced a candidate, so it inherits the
linkage window and isolates the WINDOW's effect. `full true graph` uses
every truly overlapping pair, so it isolates the workload GEOMETRY: if it
also fails, no amount of better estimation would have helped.

Reading: the SHUFFLED arms are a second null - same components, same edges, the
magnitudes permuted. The `topology only` arms show what unweighted overlap
structure alone gives, so the gap between them and the weighted arms is what
magnitude estimation buys. The ORACLE arm is the ceiling if pair selection
and magnitudes were perfect, i.e. how much of the residual error is the
attack's and how much is seriation's.
