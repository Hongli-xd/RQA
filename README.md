# RQA: Range-Query Attack on Waffle

Passive, order-hidden, multi-stage attack that quantifies what a Waffle-backed
range-query deployment leaks to the storage server. Design-level evidence
(simulator); see `experiments/range_query_attack_handoff.md` for the full
honest handoff/review document (conditions, algorithm, results, 12 known
weaknesses, TODO).

## Contents

| file | role |
|---|---|
| `experiments/waffle_leakage_sim.py` | Waffle design-level simulator (batched reads, least-timestamp fake selection, dummy epochs, write-once-read-once incarnations); dependency, run unmodified |
| `experiments/range_query_attack.py` | the five-stage attack: (A) passive batch anatomy incl. fake-flush self-identification, (B) range-episode detection, (C) cardinality recovery, (D) cross-incarnation tracking via exact write/read timing arithmetic, (E) overlap topology + linkage-window law |
| `experiments/rqa_scaling_matrix.py` | experiment matrix orchestrator (4 scales x 3 seeds + background-rate mechanism discrimination) with Wilson CIs and the window ~ (N-C)/f_R law fit |
| `experiments/range_query_attack_handoff.md` | handoff & audit document (written inside the parent artifact repo; result paths and cross-references refer to that context) |

## Adversary model

Passive persistent storage-server observer. Sees per-batch multisets of
storage ids (PRF outputs) and timestamps only. Attack parser whitelists
exactly `event, batch_ts, direction, storage_key`; simulation labels are
dropped at load time, ground truth is used only by `eval_*` functions.
Within-batch order is assumed scrambled (all features are order-hidden).

## Quick start

```bash
# single attack run (small config; writes results/ on demand)
python3 experiments/range_query_attack.py \
  --rounds 4000 --episode-every 45 --m-min 40 --m-max 160 \
  --overlap-bias 0.5 --outdir results/rqa_repro

# the paper's MEDIUM-security parameters (Table 2, scaled 1:5)
python3 experiments/range_query_attack.py --paper-medium \
  --outdir results/rqa_repro_med

# full publication matrix (~70 min at 3-way parallelism)
python3 experiments/rqa_scaling_matrix.py --jobs 3
python3 experiments/rqa_scaling_matrix.py --aggregate-only   # re-aggregate
```

Stdlib only (no third-party dependencies). Outputs land under `results/`
(git-ignored: traces are large).

## Headline results (design-level)

- Fake padding self-identifies: least-timestamp selection produces a
  flush-age alpha mode; the server passively recovers B, f_D, and the
  per-batch client-miss series.
- Range-query timeline: F1 0.50-0.90 across scales; visible cardinality:
  3-12.5% median error.
- Cross-query linkage: 100% recovery inside a window that obeys
  window ~ 0.75 x (N-C)/f_R (R^2 = 0.960 over 14 runs); beyond the window
  the evidence is destroyed by the fake sweep itself (mechanism experiment:
  4x background traffic does not shrink the window).
- Not recovered: plaintext, record-level identity, long-gap linkage,
  fully-cached re-queries.
