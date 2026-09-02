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
- Recovery: `git diff --stat stash@{0} -- <locked file>` (working copy usually
  already equals the stash), then `git checkout stash@{0} -- $(git diff
  --name-only HEAD stash@{0} | grep -v <locked>)` and `git reset` to unstage;
  verify `git diff --stat stash@{0}` is empty before dropping the stash.
- Kill any seat build started in the window; its inputs were HEAD's.
