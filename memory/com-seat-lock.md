---
name: com-seat-lock
description: COM serialization is a runtime cross-process file lock (_com_seat/filelock), NOT the old task_dep spine — every SolidWorks subprocess grabs the machine-global seat before driving COM; DAG now carries only real edges
metadata:
  type: project
---

The single SolidWorks STA seat is serialized at RUNTIME by a cross-process **file
lock** (`_com_seat` in `dodo.py`, backed by `filelock`), replacing the old linear
`task_dep` **spine** (`_COM_TAIL`/`_spine_dep`/`_assert_spine_complete`) — done
2026-07-11 (branch `refactor-com-seat-lock`). Every COM subprocess acquires the lock
right before it drives SolidWorks and releases after, so ≤1 COM task touches the seat
at a time even under `doit -n N`; the SolidWorks-free `check:*` gates never take the
lock, so they still fan out. Lock path: `%PROGRAMDATA%/harmonic-analyzer/com-seat.lock`
(override `HARMONIC_COM_LOCK`) — **machine-global**, so it also serializes COM across
worktrees / concurrent `doit` invocations on one seat (the spine only serialized within
one invocation). `filelock` uses OS advisory locks (msvcrt/fcntl) → auto-released when
the holder dies, no stale lockfile. Verified cross-process on Windows (3 procs, no
overlapping hold windows).

**Why:** the spine injected FAKE dep edges (`part:A "depends on" part:B` purely to
serialize), so the DAG lied and a mid-spine COM failure skipped *unrelated* downstream
COM tasks. With the lock, the graph carries only REAL edges — assembly `file_dep` on
its parts; `verify`/`export` on the built `.SLDASM`; `export` gated on `verify:*` (its
gallery/STL side-effects must not come from a model that fails soundness); `release` on
`export`+`preflight`+`verify:*`+`check:*` (all explicit now the spine no longer pulls
them transitively).

**How to apply (invariant):** any new COM-touching task MUST run its SolidWorks
subprocess inside `_com_seat(...)` — wrap the `_exec` for a part/assembly action, or
pass `com=True` to `_run`/`_run_stamped` for a gate. Enforced LOUD at runtime: a
doit-launched build (TRACEPARENT injected) that reaches `sw.connect` without
`HARMONIC_COM_SEAT` set raises in `_common.run_build` — the successor to
`_assert_spine_complete`. Cache RESTORE/STORE (Azure transfers) run OUTSIDE the lock so
hits stay parallel; parts/assemblies **re-probe the cache after acquiring the seat** so a
peer that published while we waited is picked up (this + the lock is what makes
[[per-seat-part-order]] a safe best-effort hint, not a correctness requirement). Holds
the seat across an assembly build + its POST_ASSEMBLY hooks (one acquire) so nothing
interleaves into the post-build state. Tradeoff: cold `-n N` builds can starve `check:*`
toward the end (workers block on the seat) — tens of seconds on a ~25 min cold build.
**The seat wait is its own top-level span** (2026-07-26): blocking is queueing, not
work, so `_com_seat` opens `com.seat.wait <label>` for the wait and the `task <label>`
span starts once the seat is HELD — SIBLINGS, never nested (a cached task is a chain:
`cache.probe` → `com.seat.wait` → `task` → `cache.store`, each top-level). Otherwise
the same part reads 40 s idle vs 20 min behind a cold assembly, and anything timed off
`traces.jsonl` (watchdog calibration, perf audits) measures contention. `_com_seat`
yields the seconds blocked so the task span carries `seat_wait_s`; release LOGS the
seat's total elapsed (`wait_s`/`held_s`/`elapsed_s`) — no span is in scope by then, so
the old `com.seat.acquired`/`com.seat` events are gone. Rejected on the way here:
discounting the wait by moving the live task span's `_start_time` forward — not a
spec'd operation (start time is recorded at creation) and it dangled the pre-wait cache
events before their own span's start. Accepted cost: sibling roots are separate traces;
correlate on the `label` attribute.
**Serializes but does NOT isolate** — SolidWorks keys open docs by filename + carries
session state, so it is a safety belt, not a green light for independent parallel builds
(see [[parallel-sw-instances-investigation]]). Tests: `test_dodo_recipe.py`
(`check:recipe`) pins `_com_seat` acquire/env/release, reentrancy, no-inter-COM-task_dep,
and the export/release gate edges.
