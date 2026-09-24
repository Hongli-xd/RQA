# This run does NOT test the alpha-recency channel. Configuration error.

The channel's stated validity region is `tau << flush age`, with the rule
`tau <= flush/4` derived in experiments/distribution_channel_analysis.md
(S1: flush 81, tau 20 works, tau 60 already degrades to rho 0.316).

At this configuration (paper-medium batch structure, B=2500, R=1000, f_D=500,
N=100k) the measured flush age is **50**, so the rule gives tau ~= 12. The
driver that produced this run passed `--taus 40 60 90 140`, i.e. 0.8x, 1.2x,
1.8x and 2.8x the flush age - every one of them at or beyond the point where
the mechanism says the fake population stops sitting above tau and the
estimator must fail.

So the weak numbers here (E2 rho 0.26-0.37, Pearson 0.16-0.33, and a
shuffled-alpha null of +0.137 at tau=40 that does not cleanly separate from
the signal) are what the mechanism predicts OUTSIDE the validity region. They
are not evidence about the channel at this scale, in either direction.

The cross-scale test has to be redone with tau near flush/4. Kept here because
a misconfigured run that is quietly deleted is how a wrong number ends up in a
paper later.
