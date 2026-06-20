# Pipeline Consolidation & Parallelism Refactor — Plan

Status: APPROVED design (diagrams in this dir). Implementation in progress on
branch `claude/gallant-gauss-3ezj8k`.

## Goal

Bring the *entire* pipeline — part build → assembly → verify → neutral export →
diff → bundle → tag → GitHub release — under a single `doit` graph, and unlock
parallelism for every stage that does **not** touch SolidWorks, **without
changing how SolidWorks COM work is serialized**.

## The one hard constraint (unchanged)

There is one SolidWorks STA COM seat. COM work stays exactly as today:
subprocess-per-task, one connection live at a time. We do **not** introduce a
shared in-process executor, a COM lock, or `-P thread`. The serialization
*mechanism* is untouched.

## Mechanism: the COM "spine" (replaces the `-n` hard-fail)

doit runs tasks that are *simultaneously ready* in parallel. We add a linear
chain of `task_dep` edges through every COM task — a topological linearization
of the existing COM sub-DAG:

```
part:a → part:b → … → assembly:frame → … → assembly:harmonic_analyzer
       → verify:static → verify:isolation → verify:motion → export → release
```

Because each COM task waits on its predecessor, **at most one COM task is ever
ready**, so the seat is never contended — identical runtime behavior to today's
serial run, enforced by DAG edges instead of the global `-n=1`. SolidWorks-free
tasks (`verify:truth`, `verify:config`, and future `transcode`/`diff` fan-out)
depend only on their real artifacts, *not* the spine, so they run in parallel
under `doit -n N`.

`_guard_serial` is replaced by `_assert_spine_complete`: it asserts every COM
task has a spine predecessor (except the first) so a forgotten edge can never
silently expose the seat to `-n`.

### Accepted tradeoff

A COM failure mid-spine blocks the COM tasks after it within that run (even
independent parts). Fix-and-rerun recovers; doit skips up-to-date tasks. This is
the price of single-command parallelism and is documented in README/CLAUDE.

## Task graph (target)

| Task | Zone | file_dep | target / gate |
|------|------|----------|---------------|
| `part:<stem>` (×77) | COM (spine) | build script + helpers + YAML | `.SLDPRT` |
| `assembly:<stem>` (×5) | COM (spine) | recipe + referenced parts | `.SLDASM` |
| `verify:static` | COM (spine) | built `.SLDASM`s | stamp `cad/out/reports/verify-static.ok` |
| `verify:isolation` | COM (spine) | built `.SLDASM`s | stamp |
| `verify:motion` | COM (spine) | `output.SLDASM` + `pen_driver.py` | stamp |
| `verify:truth` | **green** | `truth_model.py` | stamp |
| `verify:config` | **green** | config YAML + `DIMENSIONS.md` | stamp + `tolerance_audit.csv` |
| `export` | COM (spine) | all `.SLDPRT`/`.SLDASM` | `boxes/harmonic-analyzer.json` |
| `release` | COM (spine tail) + publish | export + verify stamps | GitHub release (opt-in) |
| `build` (alias) | meta | parts + assemblies + `verify:static` | — |

### Entry points

- `doit build`  → parts + assemblies + `verify:static` (the requested
  build-only job: **no STL/STEP, no Pack-and-Go**; downstream tasks are never
  pulled in because doit only runs *upstream* prerequisites).
- `doit verify` → the remaining suites.
- `doit` (bare) → `default_tasks = ["build"]`.
- `doit export` → neutral exports.
- `doit release` → full pipeline through `gh release create` (opt-in).
- All of the above accept `-n N`; COM stays serial via the spine.

## Scope of THIS change (offline-verifiable)

Implemented now — the orchestration layer + docs, all verifiable here via
`doit list/--deps/info` (no SolidWorks needed; actions are not executed):

1. `dodo.py`: spine builder, `task_verify`, `task_export`, `task_release`,
   `task_build` alias, `default_tasks=["build"]`, guard→spine-completeness
   assertion. COM scripts are wrapped (CmdAction/subprocess), internals
   untouched.
2. Docs: `README.md`, `CLAUDE.md`, new `AGENTS.md` (build-repo orientation).
3. Docstrings: `dodo.py` module + new functions; one-line "doit task: …"
   pointers added to `verify.py` / `export_models.py` / `cut_release.py`.

### Deferred to later phases (require `_common.py` / `cut_release.py` internal
refactors that cannot be validated without SolidWorks)

- `transcode:<stem>` extraction (split BMP capture from Pillow transcode so the
  seat advances while Pillow works).
- `diff:<stem>` per-changed-part fan-out (extract `render_diff` out of
  `cut_release` into parallel green tasks — the biggest release-time win).

These are SW-free wins but touch capture/release internals; landing them blind
is unsafe, so they ship once runnable against a real seat.

## Validation here

- `python3 -m doit list --all` shows the new tasks.
- `python3 -m doit info build` / `info release` shows correct `task_dep`.
- `python3 -m doit list --deps` shows the spine edges.
- doit errors loudly on any dependency cycle → proves the spine is a valid topo
  order.
- `python3 -m py_compile` on every edited script.

## Diagrams

- `build_flow_current.{mmd,png}` — pipeline as-is.
- `build_flow_target.{mmd,png}` — single-pass + COM-spine target (this plan).
