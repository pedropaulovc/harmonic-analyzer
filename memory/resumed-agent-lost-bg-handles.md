---
name: resumed-agent-lost-bg-handles
description: "A subagent resumed from transcript loses its background-task handles — 'waiting on the build notification' then sleeps forever; coordinator must OS-verify processes (tasklist + log mtimes) when an agent waits suspiciously long"
metadata:
  type: feedback
---

During the 2026-07-21 drawing-batch fan-out, two forks that had been killed
(session usage limit) and later resumed via SendMessage-from-transcript ended
their turns with "waiting on the build completion notification". The
notification NEVER fires for them: the resumed incarnation no longer owns the
background task, so the harness has nothing to re-invoke it with. Both builds
had in fact been dead/finished for 1–2 h while the agents slept. Pedro caught
it by eye ("i don't see any subagents running").

**Why:** background-task ⇄ agent bindings do not survive a transcript resume
(and possibly not an API-error kill either). The agent's plan "the bg job
re-invokes me" silently becomes false after any resume.

**How to apply (coordinator):**
- When a subagent has been quiet longer than its awaited work should take,
  don't trust its "waiting" state — verify on the OS: `Get-CimInstance
  Win32_Process -Filter "Name like 'python%'"` (command lines show the
  worktree) + newest `cad/out/logs/*` mtime in that worktree. No process +
  stale logs = the agent is waiting on a phantom.
- Wake it with the evidence and an explicit "do not wait; verify from disk and
  proceed" instruction. A completed doit build makes re-running doit a cheap
  no-op, so "verify by re-run" is safe.
- After resuming any agent that had launched background work, assume its
  handles are gone: tell it in the resume message to re-verify its processes
  from the OS instead of waiting for notifications.
