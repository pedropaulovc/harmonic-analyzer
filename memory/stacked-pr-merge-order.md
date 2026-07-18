---
name: stacked-pr-merge-order
description: "gh pr merge --delete-branch on a stacked PR's base closes the child PR instead of retargeting it — retarget children first"
metadata:
  node_type: memory
  type: feedback
---

Merging a stacked PR's PARENT with `gh pr merge --delete-branch` auto-CLOSES
any child PR whose base is the deleted branch — GitHub does not retarget the
child. This bit lane B on 2026-07-04: #152 (pr2-platform-lock-knob) merged
with branch deletion and silently closed #148 (pr3-brackets, stacked on it);
it had to be reopened by hand and retargeted to main.

**Why:** GitHub's auto-close-on-base-delete predates its (partial) base
retargeting; deletion wins.

**How to apply:** before merging any PR that other open PRs use as a base:
1. `gh pr edit <child> --base <new-base>` (usually `main` or the next branch
   down) for EVERY child stacked on it,
2. then `gh pr merge --delete-branch` the parent.
The PR-lifecycle monitors show a `finished: CLOSED` (not MERGED) event when
this happens — reopen with `gh pr reopen`, retarget, and the diff is intact
as long as the child branch itself still exists (rebasing it onto the new
base first keeps the diff exactly the child's own changes).

**2026-07-18 recurrence (#339/#340) + full recovery recipe.** Hit again — the
memory existed but was not consulted before `gh pr merge 339 --merge
--delete-branch`; #340 (based on it) went CLOSED. Recovery when the base
branch is already deleted (a closed PR can neither be retargeted nor
reopened while its base is gone):
1. restore the base ref: `git push origin <merged-tip-sha>:refs/heads/<base-branch>`,
2. `gh pr reopen <child>`,
3. `gh pr edit <child> --base main`,
4. delete the restored branch again: `git push origin :refs/heads/<base-branch>`.
Diff and review state (Codex 👍) survive intact.
