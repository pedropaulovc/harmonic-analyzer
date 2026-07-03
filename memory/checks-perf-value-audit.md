---
name: checks-perf-value-audit
description: Telemetry+history audit of verify gates / offline checks — where soundness time goes and which gates never catch anything (gear-ratios is 50% of cost, 0 catches)
metadata:
  type: project
---

Audit (2026-07-03) of every verify gate + offline `check:*`, from 113 h of OTel
capture (`cad/out/reports/telemetry/traces.jsonl`, 24 k spans) cross-referenced
with conversation history + git log. Extends [[release-perf-incremental]].

**Where soundness time goes** (median real run ≈ **989 s**, ~99% of all verify cost;
offline `check:*` total ≈34 s, parallel/off-spine, negligible):
- **gear-ratios ≈ 493 s = 50%** of a run — one COM MateGroup walk (`gear.read_links`);
  `channel` alone = 256 s. And in the whole log corpus it has caught **zero** defects
  — the "gear ratio not transmitted" catches belong to the MOTION suite, not this
  static gate. Property is deterministic from tooth counts already proven by
  `check:math`. → **demote to release preflight (next to park-closure) or make it a
  fine-grained-dep gate** keyed on gear parts + `gear_train.yaml`.
- **3× redundant `ForceRebuild3` per assembly ≈ 247 s/run** — `assert_model_healthy`
  (`_assembly.py:1530`), `assert_components_fully_defined` (`:963`), and
  `assert_no_over_constrained` (`verify.py:275`) each deep-rebuild the SAME unchanged
  open model. Share one rebuild after open → save ~165 s/run. Caveat: health's
  rebuild may be deeper; validate equivalence on a seat (comment `_assembly.py:1795`
  already assumes the ordering).

**Gate value verdicts** (useful = caught a real defect):
- USEFUL, keep: `interference` (best — alignment-pinion in all 20 gears, no false
  alarms), `model-healthy` (caught 273 mate errors while DOF+interference green — was
  added because mate state was unguarded), `check:math`, `check:config`, `check:graph`.
- NOISE / drop: `component-count` (every failure a stale band or `GetComponents`
  gate bug — 0 real regressions); `check:verify_telemetry` (~30 s, 0 product catches,
  all 3 failures self-inflicted incl. a flaky wall-clock test deleted `c25fbc3`).
- INVISIBLE (never fire): `gear-ratios`, `channel-independence` (sole reason
  `verify:subsystems` still opens an assembly → fold into soundness, retire the
  suite), `park-closure`/`dof-*` (correct as proofs, not detectors), and the cheap
  `check:cache`/`freshness`/`flagonly`/`telemetry` (value was the underlying feature
  or RUNTIME tooling, not the test).

**Biggest gap is not a missing gate — there is NO CI.** Checks were repeatedly merged
red or shipped unwired (`freshness`/`flagonly` missing from `_CHECK_NAMES`;
`check:config` broken behind a green stamp) and the divergence was caught by
Codex/human review, not the gate. Wiring the ~10 cheap offline checks into a <40 s
parallel CI job on every push is the highest-value addition.

Full write-up: artifact published this session (favicon 📊, "Check & verify-gate
performance assessment"). **Perf changes above are OFFLINE-derived — rec 1&2 touch
COM gates and need a live seat run before merge** (see [[no-untested-failure-assumptions]]).
