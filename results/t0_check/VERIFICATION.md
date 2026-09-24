# Task 0 verification: parameterisation is behaviour-preserving

Command (both arms): `python3 experiments/range_query_attack.py --quick --seed 7 --outdir <dir>`

- `results/t0_check_orig/`: run with the ORIGINAL code (commit 1e7f02f).
- `results/t0_check/`:   run with the hardening code, all default parameters.

Two checks, at two code states:

1. **At the Task-0 commit (2e5f161)** - the required acceptance: the two
   arms' `attack_state.json` were BYTE-IDENTICAL after removing the single
   added transparency key `attack_params` (sorted-JSON diff, zero
   differences). stage_b eval f1 = 0.8718 in both; stage_e
   boundary_by_gap identical pair-for-pair. A separate run with
   non-default values (--track-span 40 --flush-frac 0.16 --local-bg 20
   --min-mass 15 --window 25 --gap 2 --min-pair-mass 4 --max-cell 2
   --eviction-tail 8) changes the output (f1 0.8718 -> 0.8571),
   confirming the new CLI knobs are live.

2. **Re-run at the final code state (post Task-2/3)**, this archive: the
   state is again identical across arms EXCEPT the intentionally changed
   stage-e boundary FORMAT (Task 2: 5 hardcoded string buckets ->
   per-actual-gap recording, plus the new boundary_pairs /
   overlap_pair_metrics / window_est keys). Verified by normalising both
   sides to pair level: stages A/B/C/D and all other stage-e fields are
   identical; recovered totals 7/12 vs 7/12 with the same hit/miss
   bucket pattern.

Large trace/tsv/json artifacts stay untracked per .gitignore; the
attack_summary.md files in these directories are the durable evidence.
