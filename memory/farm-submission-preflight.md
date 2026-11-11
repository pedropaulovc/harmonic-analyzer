---
name: farm-submission-preflight
description: Before any `--executor farm` run, prove the pool checkout matches the deployed fleet with `farm.py agents` — a mismatch publishes to a prefix no worker reads and fails every leaf with `package_download`; the identity also depends on your `core.autocrlf`, and a worktree "pinned to the deployed commit" is not evidence
metadata:
  type: project
---

`--executor farm` depends on a **second repository with its own deploy cycle**
([`solidworks-pool`](https://github.com/pedropaulovc/solidworks-pool)). Two independent
things must line up before dispatching, and both fail in ways that look like something else.

## 1. The submitter's agent identity must equal the fleet's

A package is published under `sources/<source-identity>-<agent-identity>/`, and each worker
rebuilds that prefix from the agent **it** is running. A submitter whose pool checkout is
ahead of the fleet publishes where nobody looks, and every leaf dies with
`package_download: no package blobs under <prefix>/`. From the pool checkout:

```powershell
uv run --frozen python farm.py agents             # local identity vs what each worker reports
uv run --frozen python farm.py agent-release status --history
```

`agents` always exits 0 — the verdict is the caller's to act on. On a mismatch: either
`farm.py agent-release publish` (a ~110 KB blob write, no ARM, no restart, no lost seat —
workers self-update within the minute) or submit from a pool checkout at the deployed commit.

**Ask the fleet, never a worktree.** On 2026-09-18 a `sp-deployed` worktree pinned at
`9443240` implied the fleet was 87 commits / 13,520 lines behind. `agent-release status`
reported `9c442c5b`; the real delta was 30 commits. A pin is a claim about the past. Measure
with `git log --oneline <released-commit>..origin/main -- agent/ farm.py`.

## 2. Two traps make a FALSE mismatch look real

`agent_identity()` hashes **working-tree bytes**, and the pool's `.gitattributes` constrains
only `*.bicep` and `*.sh`. So the identity of one commit differs between a CRLF and an LF
checkout — for the commit deployed on 2026-09-18, `4ef98097659fb439` (CRLF) vs
`e7385f64abdbb2e7` (LF). The fleet runs the CRLF one, and the scheme holds today only because
every publisher so far had `core.autocrlf=true`. A Linux/macOS submitter, or a Windows one
with `autocrlf=false`/`input`, silently publishes where no worker reads — a failure
indistinguishable from version skew that **no amount of deploying can fix**.

The same mismatch makes `farm.py agents`/`publish`/`prepare` intermittently refuse a tree
`git status` calls clean: the guard asks git under a pinned `core.autocrlf=false` that
disagrees with the checkout, and git only re-hashes when the index stat-cache is cold. So it
appears after a pull, checkout or worktree operation, and vanishes after a plain `git status`
— which is why it reads as flaky. `touch agent/*.py` reproduces it on demand.

Tracked as [pool #88](https://github.com/pedropaulovc/solidworks-pool/issues/88).

## 3. Rebase before dispatching, not after a gate fails

A stale branch risks a green farm build that still conflicts, and a config or digest change
on `main` invalidates what was just built. `git fetch origin main && git log HEAD..origin/main`
is cheaper than a re-run of the closure.

## Budget the leaves

One attempt gets 15 min by default. That covers a warm leaf, not a cold one — the slowest
measured attempt was `part:fulcrum_keeper` at 61.5 min on a worker that had to sync the
package and start SolidWorks cold. Pass `--leaf-timeout <minutes>` on a cold run; the default
costs one retry and then a `platform`-style failure per slow leaf.
