---
name: gate-test-enrollment
description: A new cad/scripts/test_*.py runs in NO gate unless enrolled in dodo.py's recipe_tests allowlist — check:recipe stays GREEN over a test nothing executes
metadata:
  type: project
---

`check:recipe` runs an **explicit allowlist**, not pytest discovery:
`recipe_tests` in `dodo.py` (~line 1714) lists files by hand plus ONE glob,
`SCRIPTS_DIR.glob("test_*_drawing.py")`. A new `cad/scripts/test_*.py` whose
name misses that glob is executed by **no gate at all** — and the gate still
reports green, so "check:recipe passed" is not evidence your new test ran.

Why this bites rather than merely annoys: the failure is invisible from where
you are working. You add a test, run `check:recipe`, see green, and conclude it
is covered. Discovered 2026-07-25 (PR #416, found by Codex, not by the build):
`test_assembly_drawing_batch_contract.py` had never been enrolled while its two
siblings `test_cone_drawing_batch_contract.py` and
`test_pen_summing_drawing_batch_contract.py` were. Reducing the channel assembly
drawing to a three-view diagram left it reading `ASSEMBLY_NOTES` /
`BOM_COMPONENTS` / `BOM_PART_NUMBERS` that the sheet no longer defined — an
`AttributeError` at import, i.e. it would have failed on collection — and every
`check:*` gate passed anyway. Enrolling it took the suite 898 → 912 tests, so
14 assertions had been dead for as long as the file existed.

**How to apply:** after adding a test file under `cad/scripts/`, confirm it is
either named `test_<stem>_drawing.py` (auto-enrolled by the glob) or added to
`recipe_tests` explicitly. Verify by the TEST COUNT moving, not by the gate
being green — run `uv run python -m doit check:recipe` before and after and
check the `N passed` number changed. Do not trust a green gate as proof of
coverage.

Related: [[no-untested-failure-assumptions]],
[[load-bearing-claims-need-repro]].
