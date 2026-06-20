# Pipeline Consolidation & Parallelism Refactor

Status: **IMPLEMENTED** on branch `claude/gallant-gauss-3ezj8k`. Diagrams in this
dir (`build_flow_current.*`, `build_flow_target.*`).

## Goal

Bring the *entire* pipeline — part → assembly → verify → export → release —
under one `doit` graph, and unlock parallelism for every SolidWorks-free stage,
**without changing how SolidWorks COM work is serialized** (one STA seat).

## Mechanism: the COM spine

COM tasks stay subprocess-per-task, one connection at a time. A linear `task_dep`
**spine** chains every COM task (`_COM_TAIL` + `_spine_dep` in `dodo.py`):

```
part:a → … → assembly:harmonic_analyzer → verify:soundness → verify:subsystems
        → verify:kinematics → export → release
```

At most one COM task is ever runnable ⇒ the seat is never contended even under
`doit -n N`. SolidWorks-free `check:*` tasks sit off the spine and fan out.
`_assert_spine_complete()` is the tripwire that replaced the old `-n` hard-fail.
Tradeoff: a COM failure mid-spine skips later COM tasks that run; fix-and-rerun.

## Tasks (implemented)

| task | zone | gate/target |
|------|------|-------------|
| `part:<stem>` (×77), `assembly:<stem>` (×5) | COM (spine) | `.SLDPRT` / `.SLDASM` |
| `verify:soundness` / `verify:subsystems` / `verify:kinematics` | COM (spine) | stamp `cad/out/reports/verify-*.ok` |
| `check:math` / `check:config` / `check:graph` / `check:nameplate` / `check:recipe` | offline (parallel) | stamp `check-*.ok` |
| `export` | COM (spine) | `boxes/harmonic-analyzer.json` |
| `release` | COM (spine tail, opt-in) | GitHub release |
| `build` (**default**) | meta | every part + assembly + every gate |
| `build_bare` | meta | parts + assemblies only |

Group prefix encodes SolidWorks-dependence: `verify:*` need SW, `check:*` do not.

## Naming changes shipped

`verify.py --suite` renamed and the misleading `all` aggregate **removed**
(`doit build` is the one fully-safe entry):

| old | new |
|-----|-----|
| static | soundness |
| isolation | subsystems |
| motion | kinematics |
| truth | math |
| config | config (kept) |
| all | (removed) |

## Files changed

`dodo.py` (spine + `task_verify`/`task_check`/`task_export`/`task_release`/
`task_build`/`task_build_bare`, `default_tasks=["build"]`); `cad/scripts/verify.py`
(suite rename + `all` removal); `README.md`, `CLAUDE.md`, new `AGENTS.md`;
docstring pointers in `export_models.py` / `cut_release.py`; suite-name references
in `docs/motion-policy.md`, `cad/config/machine.yaml`, `.gitignore`. New dep:
`pytest` (one-off `pip install doit pillow pytest`).

## Verified offline (no SolidWorks)

`doit list --all` shows all tasks; `doit info build` / `build_bare` show correct
`task_dep`; `doit list --deps` builds with no cycle; `check:graph` / `check:nameplate`
/ `check:recipe` run green through doit with incremental stamps; `py_compile` clean.

## Deferred (need a SolidWorks seat to validate)

- `transcode:<stem>` — split BMP capture from Pillow transcode.
- `diff:<stem>` — per-changed-part render fan-out extracted from `cut_release`
  (the biggest release-time parallel win).
