# AGENTS.md — harmonic-analyzer

Orientation for coding agents. Pairs with `CLAUDE.md` (git workflow + build
rules) and `docs/pipeline/` (flow diagrams + the refactor plan).

## The pipeline is one doit graph

`dodo.py` (repo root) drives the **whole** pipeline: build → verify → export →
release. There is no separate orchestrator and no hand-run scripts for the happy
path — every stage is a doit task. Run with the Windows SolidWorks build venv
python, SolidWorks already open:

```
…\.venv\Scripts\python.exe -m doit            # = `build`: everything + every gate
…\.venv\Scripts\python.exe -m doit -n 4       # same, check:* fanned out in parallel
…\.venv\Scripts\python.exe -m doit build_bare # quick: parts + assemblies only
```

One-off install: `… -m pip install doit pillow pytest`.

## Task groups — the prefix tells you if SolidWorks is needed

| group | needs SolidWorks | on the COM spine |
|-------|:---:|:---:|
| `part:<stem>`, `assembly:<stem>` | yes | yes |
| `verify:soundness`, `verify:subsystems`, `verify:kinematics` | yes | yes |
| `export`, `release` | yes | yes |
| `check:math`, `check:config`, `check:graph`, `check:nameplate`, `check:recipe` | **no** | no (parallel) |
| `build` (default), `build_bare` | meta | — |

- `build` is the **one** fully-safe entry: every part + assembly + every gate.
  (`verify.py` has no `--suite all` anymore — `build` replaced it.)
- `build_bare` = parts + assemblies only (fast, no gates, no export).
- `release` is opt-in: `doit release -- v0.2.0 [--draft]`.

## The COM spine (do not break this)

One SolidWorks STA seat ⇒ COM tasks must never run concurrently. Instead of
forbidding `-n`, `dodo.py` chains every COM task into a single linear `task_dep`
**spine** (`_COM_TAIL` + `_spine_dep` in `dodo.py`), a topological linearization
of the COM sub-DAG:

```
part:a → … → assembly:harmonic_analyzer → verify:soundness → verify:subsystems
        → verify:kinematics → export → release
```

So at most one COM task is ever *ready* — the seat is never contended **even
under `-n N`** — while `check:*` tasks (off the spine) run in parallel.

**Invariant:** any new COM-touching task MUST be inserted into the spine
(extend `_COM_TAIL` / the spine order and give it `_spine_dep(...)`). A gap lets
two COM tasks run at once and deadlocks the seat. `_assert_spine_complete()` is a
tripwire, not a full proof — think before you add. The SolidWorks-free tasks must
**not** be on the spine, or you lose the parallelism.

Tradeoff (documented, accepted): a COM failure mid-spine skips the later COM
tasks in that run. Fix and re-run; doit re-runs only what is still stale.

## Verify suites (renamed)

`verify.py --suite <x>` where `<x>` ∈ {`soundness`, `subsystems`, `kinematics`,
`math`, `config`}. `math`/`config` need no SolidWorks (wrapped as `check:*`); the
other three open the model (wrapped as `verify:*`). Old names static/isolation/
motion/truth and the `all` aggregate are gone.

## Stamps & incrementality

Gates produce no CAD artefact, so each writes a stamp under `cad/out/reports/`
(`verify-*.ok` / `check-*.ok`) as its doit target — re-runs only when a `file_dep`
changes. `cad/out/` is gitignored.

## Deferred (not yet implemented)

- `transcode:<stem>` — split BMP capture from Pillow transcode.
- `diff:<stem>` — per-changed-part render fan-out, extracted from `cut_release`.

Both are SolidWorks-free parallel wins but touch `_common.py` / `cut_release.py`
internals; land them only when runnable against a real SolidWorks seat.
