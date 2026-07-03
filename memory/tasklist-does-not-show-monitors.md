---
name: tasklist-does-not-show-monitors
description: TaskList only shows the todo list — monitors/background jobs need an OS process sweep, and pre-/clear ones survive invisibly
metadata:
  type: feedback
---

`TaskList` shows only the shared todo list. Monitors, background shells, and subagents
never appear in it, and monitors started before a `/clear` keep running under the
*previous* session ID, invisible to the current session's task tooling. (2026-07-02: I
declared "no monitors" from an empty `TaskList` during `/m`; the user then found a live
`doit build` monitor from the pre-`/clear` session.)

**Why:** An empty `TaskList` is not evidence of a clean background state — a false
"validated empty" leaves watchers emitting events into a session that knows nothing
about them.

**How to apply:** To verify no monitors/background jobs remain, sweep OS processes for
command lines referencing `…/claude/<project>/<session-id>/tasks/<task-id>.output`
(typically `bash`/`tail`/`sleep`). Try `TaskStop <task-id>` first; for pre-`/clear`
orphans, kill the pipeline processes directly, then re-sweep to zero. The `/m` skill
(worktree-reset) now documents this in step 1.
