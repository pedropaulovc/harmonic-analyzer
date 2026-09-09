---
name: git-stash-solidworks-locked-template
description: Never `git stash` while SolidWorks has a tracked binary (DRWDOT/PRTDOT/SLDPRT) open — the stash commits but the reset fails on the locked file, leaving the working tree half-reverted
metadata:
  type: feedback
---

2026-09-02, mid-sweep with ~270 uncommitted files: `git stash` to bisect a
test failure while a drawing build had `harmonic-analyzer.DRWDOT` open. Git
created the stash entry, then died on `unable to unlink old
'cad/templates/harmonic-analyzer.DRWDOT': Invalid argument` and `Could not
reset index file to revision 'HEAD'` — but it had ALREADY reverted every
other file to HEAD. `git stash pop` then refused (the locked file counted as
a local change). The seat build that was running picked up the reverted
scripts and failed against the new template.

**Why:** Windows holds an exclusive lock on documents SolidWorks has open;
git's checkout is not atomic across files, so a locked binary aborts the reset
part-way with no rollback.

**How to apply:**
- Bisect with a worktree (`git worktree add`) or `git diff`/`git show`, never
  `git stash`, while a COM build may be holding a template or part.
- Recovery: first check the locked file with
  `git diff --stat 'stash@{0}' -- 'cad/templates/harmonic-analyzer.DRWDOT'`
  (the working copy usually already equals the stash). Then, from PowerShell,
  build a NUL-delimited list with an exact top-level literal exclusion and let
  Git consume that list directly:

  ```powershell
  $locked = 'cad/templates/harmonic-analyzer.DRWDOT'
  $pathspec = Join-Path $env:TEMP "stash-restore-$PID.pathspec"
  git diff --name-only -z --output="$pathspec" HEAD 'stash@{0}' -- . ":(top,literal,exclude)$locked"
  git checkout 'stash@{0}' --pathspec-from-file="$pathspec" --pathspec-file-nul
  git reset
  Remove-Item -LiteralPath $pathspec
  ```

  Git writes and reads the NUL-delimited pathspec file itself, so spaces and
  other shell-sensitive characters in filenames are preserved. Verify
  `git diff --stat 'stash@{0}'` is empty before dropping the stash.
- Kill every build that was running at any point during the stash/reset window,
  treat all of its outputs as untrusted, and rebuild from a restored, verified
  working tree. Because the reset is partial and non-atomic, an overlapping
  build may have consumed any mixture of pre-stash and reverted files.
