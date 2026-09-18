# Running a one-off COM operation

Mid-incident playbook for the question *"I need SolidWorks to do ONE thing —
how do I run it from here?"*. This checkout has **no local seat**: every
SolidWorks-touching task runs on the farm
(`build.py --executor farm`, [`../../build.py`](../../build.py)).

Read the surrounding rules once, not here: task groups and the seat contract in
[`../../AGENTS.md`](../../AGENTS.md) ("Task groups", "The COM seat lock", "COM
watchdog"), cache roles and miss-debugging in
[`../../DEVELOPING.md`](../../DEVELOPING.md), the doit entry points in
[`BUILDING.md`](BUILDING.md), and drawing-specific session hygiene in
[`solidworks-drawing-layout-tuning.md`](solidworks-drawing-layout-tuning.md)
("Synchronous builds and session hygiene"). This file only covers the
*ad-hoc* path those docs do not: one operation, now, outside a normal build.

## 1. Decide the route

**First: does it need a seat at all?** It does if it drives COM — opens, reads,
rebuilds, saves or exports a `.SLDPRT`/`.SLDASM`/`.SLDDRW`. It does not for the
`check:*` gates, `cache_status`, `gallery` (Blender), or any offline test; those
run locally and in parallel, and never take the seat lock (`AGENTS.md`, "Task
groups"). Half of all "I need a seat" questions end here.

If it needs a seat, pick ONE of four:

| route | when | how |
|---|---|---|
| **A — dispatch the existing task** | the thing you want IS a doit task, or its artefact is a task's output | `.\build.cmd <task>` (`./build` on a POSIX shell) = `uv run python build.py --executor farm <task>` |
| **B — throwaway-branch leaf** | you need ad-hoc COM code, not an existing task | add ONE `_cached_com_action` task on a throwaway branch, push it, dispatch it as in A |
| **C — attach-only diagnostics probe** | interactive investigation on a machine that HAS a licensed running seat | `dodo._com_seat` + `run_owned_diagnostic` ([`../scripts/diagnostics/_owned_native_session.py`](../scripts/diagnostics/_owned_native_session.py)) |
| **D — don't** | you only want to *look* at a model or drawing | audit the artefact offline; never launch a build to inspect one |

Route **C is unavailable from this checkout** — it attaches to an already
running `SldWorks.Application` in the Running Object Table
(`win32com.client.GetActiveObject`), which requires a licensed seat on the same
machine. The only seats left are the farm workers, and driving one directly is
a `solidworks-pool` operation, not a harmonic-analyzer one. Its invariants
(§2) still bind whoever runs it there.

### Route A — dispatch an existing task

```powershell
.\build.cmd part:cone_gear            # one leaf on the farm
.\build.cmd --leaf-timeout 90 build   # whole closure, 90 min per attempt
```

`build.py`'s farm preflight (`_farm_preflight`) refuses to start unless:

- the tree is clean, **including submodules** (`git status --porcelain=v1
  --untracked-files=all` plus `git submodule status --recursive`);
- `HEAD` is reachable from `origin/*` after a pruning fetch — the farm clones
  from `origin`, so push first (any branch will do);
- the remote cache is `ro` or `rw` (`_artifact_cache.enabled()`) — the farm
  hands results back **through the cache**, so `off` cannot work;
- `farm.py publish --commit <sha>` succeeds (run for you, from
  `$SOLIDWORKS_POOL_HOME`, default `../solidworks-pool`). The worker
  independently re-verifies that the commit is served by the approved
  repository, or fails the leaf `source_unapproved`.

It then sets `HARMONIC_SW_AUTOSTART=0` locally (no local SolidWorks is touched)
and, unless you passed `-n`/`--process` yourself, adds `-n 8`
(`HARMONIC_FARM_PARALLELISM`) so leaves overlap.

Leaf budget: 15 min per attempt by default, clamped to 60 s–3 h
(`_farm.clamp_leaf_timeout_s`). A cold leaf measured 61.5 min, so pass
`--leaf-timeout <minutes>` for anything cold; the default costs one retry and
then a failure per slow leaf.

`check:*` tasks stay LOCAL even under `--executor farm`: farm dispatch happens
only inside `_cached_com_action`, and `check:*` tasks go through `_run`, which
has no seat and no farm path. (The farm protocol admits `check:` leaves with
no cache key, but nothing in this repo submits one.)

### Route B — a throwaway-branch leaf

A farm leaf is *a doit task name*. There is no "run this script on a worker"
endpoint, so ad-hoc COM code becomes one cache-keyed task, on a branch you
throw away afterwards. Non-negotiable shape:

1. **Route it through `_cached_com_action(label, cmd, file_deps, outputs,
   log_stem, stamp=None)`.** It is the only way in (§2).
2. **Name it under an admitted prefix.** The worker rejects anything else
   (`execute_rejected`): `part:`, `assembly:`, `drawing:`, `verify:`,
   `verify_soundness:`, `check:`, `package:`, or the bare names `export` /
   `preflight`. `build` and `release` may be *packaged* but never *executed* as
   a leaf. Widening that set changes the pool's `agent_identity` and needs a
   fleet redeploy — so pick a name inside it instead.
3. **Declare machine-stable `file_dep`s and put every output under
   `cad/out/`.** The cache refuses to extract anything else, and an absolute
   local path or a timestamp in the dep list makes the submitter and the worker
   compute different keys — every leaf then fails "farm reported success but
   cache key … is absent".
4. **Produce something cacheable.** A verdict-only task passes `stamp=` and
   that stamp IS the cached artefact. A leaf that stores nothing under its key
   fails `cache_missing` even when the COM work succeeded.
5. Commit, push to `origin`, dispatch (`./build <your:task>`), then delete the
   branch. The published source package is keyed by commit + submodule pins,
   so a fixup means a new commit and a new publish.

## 2. Invariants an ad-hoc COM operation must not break

- **The seat lock is machine-global.** `%PROGRAMDATA%/harmonic-analyzer/com-seat.lock`
  (override `HARMONIC_COM_LOCK`), `filelock`-backed, taken by `dodo._com_seat`.
  It serializes COM across worktrees and concurrent `doit` invocations on one
  machine — that is why a worker's leaf and a hand-run probe on the same
  machine cannot collide. Blocking on it is normal: `com.seat.wait <label>` is
  its own span, and the holder is logged every 30 s. Never ask a sibling
  whether the seat is free; submit and queue.
- **A read-only probe takes the lock too.** The lock serializes, it does not
  isolate: SolidWorks keys open documents by FILENAME, so a probe that opens
  `top-frame.SLDDRW` also loads `top-frame.SLDPRT` read-only, and a concurrent
  `part:top_frame` build binds to that resident copy and dies in a plain
  `Select2` (three builds lost this way, 2026-09-16 — see
  `drawing_layout_audit.py`'s module docstring).
- **One way in.** `_cached_com_action` is the single COM entry point: it probes
  the cache, dispatches a farm leaf when the executor is `farm`, otherwise
  takes the seat, re-probes under it, runs `_exec_com` and stores the result.
  `_run`/`_run_stamped` have no `com` parameter and no seat access. Enforced at
  runtime, not by review: a COM process launched under doit (`TRACEPARENT`
  set) that reaches `sw.connect` without `HARMONIC_COM_SEAT` raises in
  `_common.run_build`.
- **The lock holder owns the session: start empty, leave empty.**
  `run_build` discards every open document at connect and *fails* if a
  `cad/out` document survives; at teardown it closes them again. Leaving one
  resident is the expensive mistake, and the chain is worth knowing because it
  fails far from its cause:

  1. a resident document share-locks its file past the COM session;
  2. the NEXT task's cache restore runs OUTSIDE the seat, before any
     connect-time discard, so its extract fails with `PermissionError`;
  3. "just build locally" mints a fresh `.execution` identity token
     (`sha256` of the artefact bytes) that no other seat can reproduce;
  4. every dependent keys on that token, so their cache keys fork off the
     fleet's — observed 2026-09-17 on worker 4, which rebuilt
     `measuring_stick` behind an open top-assembly drawing and failed its leaf
     `cache_missing`.

  Step 2 is therefore NOT swallowed: `_artifact_cache.restore` raises
  `RestoreLocked` rather than falling through. Locally the seat-holder runs
  `release_seat_documents.py` (an empty `run_build` session — the discard IS
  the work) and re-probes once; still locked after that is fatal. Under the
  farm executor the submitter holds no seat to release, so it fails loud.
- **A probe attaches, never launches.** `HARMONIC_SW_AUTOSTART=0` plus a held
  `HARMONIC_COM_SEAT` (both asserted by `run_owned_diagnostic`), open
  read-only + silent, close what you opened by path, prove the session is
  empty. Keep it short and one-shot: a held session blocks every sibling.

## 3. Cache hazards

- **Use `rw` for anything a farm leaf will consume.** In `ro` the local build
  pulls but never publishes (`store` records `store_skip`). The artefact exists
  on your disk with an `.execution` token only you have, so a leaf whose task
  depends on it cannot reproduce your key: the worker rebuilds the dependency,
  gets a different identity token, publishes under its own key, and the
  helper's probe for YOUR key comes back absent. The worker spends a second
  full run with `--always-execute` first (that is the `attempts: 2` you see),
  then fails `cache_missing` — which is non-retryable, so it kills the build.
  Same trap with `HARMONIC_REMOTE_CACHE_MODE=off`, except the farm preflight
  catches that one up front.
- **Reading a moved key** (full detail in `DEVELOPING.md`, "Debugging a miss"):
  `uv run python -m doit cache_status -- <substring>` for `HIT`/`MISS` + the
  `(digest, relpath)` list behind a miss and a `DRIFT(last published …)` flag;
  `cad/out/reports/cache.jsonl` for the append-only event log
  (`store`/`store_skip`/`restore_hit`/`restore_miss`/`restore_locked`/
  `restore_hit_drift`/…); `HARMONIC_CACHE_DEBUG=1` on the run you are
  diagnosing to log every key input as it is computed. A key is
  `sha256(epoch + salt + Σ(relpath, digest))`, so an unexpected shift is
  almost always ONE dep digest moving — diff the two dep lists, do not reason
  about it.
- A miss is routine and never fails a build; a *locked restore* is the one
  exception (above).

## 4. Getting evidence when it fails

**Local half** (the submitter, even in farm mode):

- `cad/out/logs/<log_stem>.log` — the per-task console tee (only for tasks that
  pass a `log_stem`; otherwise output is inherited straight to the terminal).
- `cad/out/reports/telemetry/traces.jsonl` and `logs.jsonl` — every span and
  log record as JSON; query them with `rg`/`jq` instead of scraping the console
  (`AGENTS.md`, "Observability"). What matters for an ad-hoc operation: the
  phase spans are SIBLINGS — `cache.probe` → `com.seat.wait` →
  `cache.reprobe` → `task` → `cache.store` — so a slow leaf is attributable to
  queueing, Azure transfer or real work without arithmetic, and correlating
  them means filtering on the `label` attribute, not on a parent span.
- Watchdog story, one filter: every watchdog record carries the
  `watchdog_signal` attribute. Absence of the one "COM watchdog armed" info per
  COM session means that session ran unprotected.

  ```powershell
  rg watchdog_signal cad/out/reports/telemetry/logs.jsonl | jq -c '.body'
  ```

**Farm half.** The failure message `_farm_build` raises already names worker,
category, exit code and log blob. The workflow id is
`leaf:<task>:<64-hex cache key>:<clamped timeout>s`
(`_farm.workflow_id`; for a `check:` leaf the key slot is the first 16 chars of
the source identity). From the pool checkout:

```powershell
uv run --frozen --project ../solidworks-pool python ../solidworks-pool/farm.py status "leaf:part:cone_gear:<64hex>:900s"
uv run --frozen --project ../solidworks-pool python ../solidworks-pool/farm.py logs   "leaf:part:cone_gear:<64hex>:900s"
```

**A failure OUTSIDE the recipe has no leaf log.** `farm.py logs` needs
`log_blob`, and the worker only publishes one once it has actually run the
build helper. Everything earlier or elsewhere — admission
(`source_unapproved`, `invalid_request`, `incompatible`), package validation,
an exhausted drain handoff, or any control-plane fault — comes back through
`control.failed_result`, which sets `log_blob=None` (and `exit_code=None`,
`attempt=0`). `farm.py logs` then reports "published no log": that is not a
missing log, it is the answer. Read the control-plane result instead
(`farm.py status`, whose `failure: [<category>] <message>` line carries it) and
`farm.py workers` for pollers and backlog. `log_blob` is also `None` when the
upload itself failed — log publication never fails a leaf, and the worker logs
`log_upload_failed` instead.

Failure categories, and what they mean for you:

| category | retried? | read it as |
|---|---|---|
| `task_failed` | no | your recipe failed with a working seat — a real bug |
| `cache_missing` | no | the leaf succeeded but your key is absent (§3) |
| `execute_rejected` | no | the task name/graph/key was refused (route B rules) |
| `restore_mismatch` | no | the worker's restored workspace is not the requested commit/submodule pins, or is not clean |
| `incompatible`, `invalid_request` | no | protocol/schema/budget disagreement between this checkout and the fleet |
| `source_unapproved` | no | the commit is not served by the approved repository — push it there |
| `platform_unavailable` | yes | the seat, not the recipe: SolidWorks gone after a failed leaf, or present but owning a blocking dialog |
| `cache_unreachable` | yes | the worker could not probe the cache |
| `infrastructure` | yes | not one of the named categories — the control plane retried (3 attempts) and the last one still failed |

## 5. Watchdog exit codes

Every COM subprocess arms a daemon watchdog around the whole session
([`../scripts/_watchdog.py`](../scripts/_watchdog.py); armed right before
`sw.connect`, stopped after `sw.disconnect`). A fatal signal flushes telemetry
and hard-exits, because the main thread is blocked inside a dead COM call:

| exit | signal | recovery |
|---:|---|---|
| **86** | crash — a NEW `sldexitapp.exe` (SolidWorks' own crash-report handler) appeared | automatic: `_exec_com` waits 60/120/240 s, force-recovers (kill → relaunch) and retries, up to 3 retries |
| **87** | op timeout — no span boundary or log record for `HARMONIC_COM_OP_TIMEOUT` s (default 900) | same automatic path; if it repeats, the wedged op is named in the abort record's `last_op` |
| **88** | modal dialog — a `#32770` "SOLIDWORKS Design" box owned by `sldworks.exe` disabling the main frame, surviving two polls | same automatic path (the watchdog never clicks); the box text rides `dialog_text`. The memory box means the seat was already dying |

A hung window (`IsHungAppWindow`) is **log-only** — SolidWorks legitimately
stops pumping messages while solving geometry — but the throttled warn makes a
wedge visible before 87 fires.

By hand, on a machine with a seat: clear the crash dialog, relaunch SolidWorks
via the 3DEXPERIENCE Platform desktop shortcut (never COM-start it), rerun.
On the farm you do none of that — a leaf that exits 86/87/88 and leaves no
`sldworks.exe`, or leaves one owning a blocking dialog, is classified
`platform_unavailable` and retried on a fresh attempt; only a failure with a
healthy seat is `task_failed`. Kill switch for local debugging:
`HARMONIC_COM_WATCHDOG=0` (`HARMONIC_COM_OP_TIMEOUT=0` disables just the idle
timeout). Do not leave either off in anything you dispatch — a dead seat then
holds its lock until something else notices.

Pre-emptive half: every COM call site runs `_sw_preflight` under the seat lock
and force-restarts SolidWorks before the task when `sldworks.exe`'s private
bytes exceed `HARMONIC_SW_MAX_COMMIT_GB` (default 40), because commit charge
grows across a day of builds until SolidWorks pops the low-memory modal itself.
