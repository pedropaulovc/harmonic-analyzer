---
name: submodule-ci-coverage-gate
description: SolidworksMCP-python's `CI` workflow `test` job is chronically red (90% coverage gate, unmeetable in SW-free CI) — non-blocking; `pedro-ci` matrix is the real gate
metadata:
  type: reference
---

On the `SolidworksMCP-python` submodule (fork `pedropaulovc/...`), a PR shows TWO
test workflows:

- **`pedro-ci`** → `test (ubuntu-latest, 3.11)` + `test (windows-latest, 3.11)`.
  This is the REAL gate — platform-agnostic mock/SW-free tests. Expect green.
- **`CI`** → a plain `test` job that runs `make test` with a hard
  `--cov-fail-under=90`. It **always FAILS** with
  `Required test coverage of 90% not reached. Total coverage: ~29%` — because the
  SolidWorks-only tests (the bulk of coverage) can't run in a headless CI. The
  tests themselves PASS (e.g. 1925 passed, 51 skipped); only the coverage gate
  trips.

This `CI` failure is **chronic on `personal` itself** (every recent push shows
`failure CI` beside `success pedro-ci`) and is **NOT a required status check**
(PRs stay `mergeable: MERGEABLE`, `mergeStateStatus: UNSTABLE`). So a red plain
`test` check on a submodule PR is EXPECTED and benign — do NOT chase it, and do
NOT "fix" it by touching the coverage config (that's an inherited upstream-fork CI
concern, unrelated to any feature PR). Judge submodule PR health by the `pedro-ci`
matrix jobs + ruff on the changed files. Related: [[zero-late-binding-task]].
