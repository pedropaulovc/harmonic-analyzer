---
name: gh-resolves-submodule-to-upstream
description: Inside SolidworksMCP-python, `gh` defaults to the UPSTREAM repo (andrewbartels1), so `gh pr view N` says "Could not resolve" for PRs that really exist — always pass `--repo pedropaulovc/SolidworksMCP-python`
metadata:
  type: reference
---

The `SolidworksMCP-python` submodule is a fork. Its `origin` remote points at
`pedropaulovc/SolidworksMCP-python`, but `gh` resolves the repo from the fork
RELATIONSHIP, not from `origin`, and picks the parent:

```
$ cd SolidworksMCP-python && gh repo view --json nameWithOwner -q .nameWithOwner
andrewbartels1/SolidworksMCP-python      # <- NOT origin
```

**Why this is expensive:** the failure is a *false negative that looks
authoritative*. `gh pr view 90` returns
`GraphQL: Could not resolve to a PullRequest with the number of 90`, which reads
exactly like "that PR was never created" — so on 2026-07-25 I concluded PR #90
didn't exist, went to re-create it, and only found it because
`gh pr create` answered `a pull request for branch ... already exists`. Likewise
`gh pr create` without `--repo` fails with the nonsense cluster
`Head sha can't be blank, Base sha can't be blank, No commits between ...`
even when `git ls-remote` plainly shows the branch on origin with the right SHA.

**Rule:** every `gh` call made from inside the submodule passes
`--repo pedropaulovc/SolidworksMCP-python` explicitly — `pr view`, `pr create`,
`pr checks`, `run view`. When a `gh` result contradicts what `git ls-remote` /
`git rev-parse` show, suspect repo resolution before believing the PR is
missing.

**Fork-only path guard:** a submodule branch cut off `personal` carries the
fork-only files (`FORK.md`, `.gitattributes`, `.github/workflows/pedro-*.yml`,
`scripts/sync-upstream.*`, `scripts/provision-fork.sh`) in its diff vs `main`,
so the `guard` job fails with "Branch touches fork-only path". That guard exists
to catch a branch that MEANT to target upstream. For genuinely fork-local work
the documented suppression is to **name the branch `pedro/...`**. Note the check
run is keyed to the COMMIT SHA, so renaming a branch does not re-run the guard —
the stale red result sticks until the SHA changes.

Related: [[submodule-ci-coverage-gate]] (the chronically-red plain `test` job on
the same PRs), [[submodule-pointer-drift]].
