---
name: submodule-preexisting-ruff-debt
description: SolidworksMCP-python has 216 pre-existing ruff errors in tests/, unrelated to any current PR; cleanup deferred
metadata:
  type: project
---

`SolidworksMCP-python` (the vendored COM-adapter submodule) has **216 ruff
errors** on `ruff check .`, all pre-existing on the base branch `personal` and
all in **test files never touched** by the flip/CreateMate work (e.g. `F841`
unused `mock_com` at `tests/test_coverage_pywin32_adapter_ext.py:119`, unused
`count1` at `tests/test_coverage_vector_rag_extended.py:111`). 156 are
auto-fixable (`ruff check --fix`), 42 more with `--unsafe-fixes`. (Count measured at submodule `b72ac309`; the pointer has since advanced to `d84537a` without resolving this — re-run `ruff check` on the current checkout before acting.)

**Why not folded into the flip PRs (#74/#75, merged 2026-06-22; this note logged 2026-07-02):** verified identical
216 on a clean `origin/personal` checkout, and `ruff check` on only the 9
changed files reports "All checks passed!". CI's `test` check passes without
gating these, so a repo-wide `--fix` would churn dozens of unrelated test files
into a mate/plane PR — scope creep against the "no unrelated changes in a PR"
principle. Left the stack clean; user was away when asked how to handle it, so
logged per the recommended "log & proceed".

**How to apply:** if picking this up, do it as a standalone hygiene PR off
`personal` (branch `pedro/<topic>`), not on the current stack. Related:
[[direct-script-build-stale-parts]] (the other deferred/pre-existing item from
the same session — that one was resolved by rebuilding stale parts).
