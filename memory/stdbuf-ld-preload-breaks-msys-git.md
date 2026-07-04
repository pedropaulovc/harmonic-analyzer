---
name: stdbuf-ld-preload-breaks-msys-git
description: Never wrap a git-pushing pipeline in stdbuf on Git-for-Windows — its LD_PRELOAD kills the credential helper's sh.exe and pushes fail as anonymous
metadata:
  type: feedback
---

Wrapping a long pipeline in `stdbuf -oL -eL` on this machine (Git for Windows /
MSYS) exports `LD_PRELOAD=C:\Program Files\Git\usr\lib\coreutils\libstdbuf.so`
— a WINDOWS-style path. Every MSYS `sh.exe`/`bash.exe` spawned anywhere below
(git's credential-helper shim, hook shells) splits that value on `:`, tries to
load a library literally named `C`, and dies with
`fatal error - error while loading shared libraries: C: cannot open shared
object file`. `git push` then falls back to anonymous HTTPS and fails with
`remote: No anonymous write access.`

It cost two full 43-minute `doit release -- v0.14.0` runs (2026-07-04): the
release pipeline itself was green both times; only the final `git push origin
<tag>` inside `cut_release.py` died, and only because the *outer* launch was
`stdbuf ... uv run python -m doit release`.

**Why:** `stdbuf` works via LD_PRELOAD, which is inherited by the entire
process tree — the poison surfaces arbitrarily deep, far from the wrapper.

**How to apply:** for Python pipelines use `PYTHONUNBUFFERED=1` alone (that is
sufficient for live logs); reserve `stdbuf` for leaf commands that never spawn
git/MSYS children. Repro/verify: `stdbuf -oL git push --dry-run origin main`
fails, plain `git push --dry-run origin main` works.

Related follow-up (unfixed): `cut_release.py` is not resumable — its
"tag already exists" guard (cut_release.py:259) aborts a re-run after any
publish-side failure, forcing `git tag -d` + remote tag delete + a full
~43 min rebuild. See [[release-perf-incremental]].
