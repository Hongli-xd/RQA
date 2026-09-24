# F3: recovering the order of queried ranges by spectral seriation

Order is recovered from estimated overlap magnitudes only. No prior, no
auxiliary dataset, no plaintext. Scored as |Spearman| against the true range
starts, per connected component, sign-free (seriation is defined up to
reflection). Components come from the linkage window, which fragments the
graph by construction.

Components smaller than 4 nodes are dropped: chance dominates them.

| arm | comps | episodes ordered | largest comp | pair concordance | permutation null | above null |
| --- | --- | --- | --- | --- | --- | --- |
| baseline gate, mass weights | 8 | 233 | 80 | 1.000 | 0.545 | **+0.455** |
| baseline gate, topology only | 8 | 233 | 80 | 1.000 | 0.544 | **+0.456** |
| baseline gate, weights SHUFFLED (null) | 8 | 233 | 80 | 1.000 | 0.545 | **+0.455** |
| poisson gate, excess weights | 8 | 233 | 80 | 1.000 | 0.544 | **+0.456** |
| poisson gate, topology only | 8 | 233 | 80 | 1.000 | 0.544 | **+0.456** |
| poisson gate, weights SHUFFLED (null) | 8 | 233 | 80 | 1.000 | 0.544 | **+0.456** |
| ORACLE among candidates | 6 | 233 | 80 | 1.000 | 0.539 | **+0.460** |
| ORACLE full true graph | 5 | 233 | 80 | 1.000 | 0.537 | **+0.463** |

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
