# AGENTS.md — harmonic-analyzer

Orientation for coding agents. Pairs with `docs/pipeline/` (flow diagrams + the
refactor plan).

## Clone with submodules

This repo has submodules (e.g. `references`). Always clone recursively so they
are pulled in:

```
git clone --recurse-submodules <repo-url>
```

Already cloned without `--recurse-submodules`? Initialize them in place:

```
git submodule update --init --recursive
```

## Every new session (do this first)

**You MUST invoke the `/developing-solidworks` skill at the start of every
session**, before any SolidWorks/build work — it carries the SolidWorks COM
conventions and pitfalls this project depends on.

Python tooling: always use `uv`.

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

The venv is `C:\src\SolidworksMCP-python\.venv`. One-off install:
`…\.venv\Scripts\python.exe -m pip install doit pillow pytest` (pillow backs PNG
export/trim; pytest backs the `check:*` unit tests).

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
under `-n N`** — while `check:*` tasks (off the spine) run in parallel. Corollary:
never launch two SolidWorks build scripts by hand at once.

**Invariant:** any new COM-touching task MUST be inserted into the spine
(extend `_COM_TAIL` / the spine order and give it `_spine_dep(...)`). A gap lets
two COM tasks run at once and deadlocks the seat. `_assert_spine_complete()` is a
tripwire, not a full proof — think before you add. The SolidWorks-free tasks must
**not** be on the spine, or you lose the parallelism.

Tradeoff (documented, accepted): a COM failure mid-spine skips the later COM
tasks in that run. Fix and re-run; doit re-runs only what is still stale.

## Incremental rebuilds — refresh vs full

doit hashes script + config **content** (immune to git/worktree mtime churn) and
propagates a part → assembly DAG. When only a part changed, the dependent
assembly is *refreshed* — reopen + per-config `ForceRebuild3` + health/DOF/
interference gates + in-place `Save3` (seconds) — instead of a from-scratch
re-insert/re-mate (~500 s). It escalates to a *full* rebuild (+ any post-assembly
hooks) when the assembly script / `_common.py` / a hook changed, or the target is
missing. Force a full rebuild of one assembly by deleting its `.SLDASM` target,
then `doit assembly:<stem>`.

**Fail loud.** A refresh that hits a dangling mate, free DOF, or interference
exits non-zero and leaves the `.SLDASM` untouched — never a stale artefact.

## Fine-grained config deps

Each part/assembly depends on ONLY the `cad/config` files it actually reads,
derived by static analysis of its `_config.<accessor>` calls (`config_files_of`
in `_buildgraph.py`); `dodo.py` honors it as the file_dep + assembly-recipe set.
The config is split per-subsystem (`cad/config/machine/<subsystem>.yaml` +
`_base.yaml`) and per-part (`cad/config/parts/<dashed-name>.yaml` +
`_defaults.yaml`); `_config._doc` re-aggregates them transparently, so
accessors/verify/provenance are unchanged. Net: editing one part's registry row
rebuilds only that part; a `machine channels.active_count` edit (in
`machine/channels.yaml`) skips the gear parts (they read `machine/gear_train.yaml`);
the narrative `dimensions.yaml` (read by no part) rebuilds nothing. It is
CONSERVATIVE — any `_config` use the analyzer can't classify falls back to the
whole config — so it can only over-rebuild, never skip a real change. Don't add a
new `_config` accessor without mapping it in `_buildgraph` (`check:graph`'s
coverage test fails loud otherwise).

## Verify suites (renamed)

`verify.py --suite <x>` where `<x>` ∈ {`soundness`, `subsystems`, `kinematics`,
`math`, `config`}. `math`/`config` need no SolidWorks (wrapped as `check:*`); the
other three open the model (wrapped as `verify:*`). Old names static/isolation/
motion/truth and the `all` aggregate are gone.

## Stamps & incrementality

Gates produce no CAD artefact, so each writes a stamp under `cad/out/reports/`
(`verify-*.ok` / `check-*.ok`) as its doit target — re-runs only when a `file_dep`
changes. `cad/out/` is gitignored.

## Release-diff parallelism

`comparisons/tools/render_diff.py` (the SolidWorks-free diff `cut_release` runs)
parallelizes its per-mesh Hausdorff classification across a process pool
(`--jobs`, default auto). `cut_release` benefits with no change. `--jobs 1`
forces serial (debugging / a fallback if the spawn-mode pool misbehaves).

## Considered but NOT done (with reasons)

- **`transcode:<stem>` — dropped.** The build writes PNGs via a single COM
  `export_image()` call (`_common.save_part_and_images`); there is no separable
  Pillow/BMP step in the build path to move off the seat, so there is nothing to
  parallelize. (BMP→Pillow transcode exists only in `cut_release._export_pngs`,
  inside the already-serial release job — not worth extracting.)
- **`diff:<stem>` per-part doit fan-out — not a fit.** `render_diff` renders the
  *whole* assembly in 4 views, not per-part images; the expensive, parallelizable
  work is the Hausdorff loop, which is now parallelized inside the script (above)
  rather than as separate doit tasks.
