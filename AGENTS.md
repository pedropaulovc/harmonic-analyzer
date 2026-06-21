# AGENTS.md — harmonic-analyzer

Orientation for coding agents. Pairs with `CLAUDE.md` (git workflow + build
rules) and `docs/pipeline/` (flow diagrams + the refactor plan).

## Initialize the project (uv)

This repo is a **uv project** (`pyproject.toml` + `uv.lock` at the root). One
command builds the environment from the lockfile — no manual `pip install`:

```
git submodule update --init   # fetch ./SolidworksMCP-python (the COM adapter, branch `personal`)
uv sync                       # core deps + the dev group (pytest) — everything the pipeline needs
```

`uv sync` creates `.venv/` (gitignored) and installs everything pinned in
`uv.lock`: `doit`, `pyyaml`, `pillow`, `numpy`, `trimesh`, `matplotlib`,
`pytest`, plus the Windows COM bindings (`pywin32`, `comtypes`) and the
**`solidworks-mcp-python`** package — wired in as an *editable path source*
(`[tool.uv.sources]` → `./SolidworksMCP-python`), since `verify.py` /
`_common.py` / `_assembly.py` all `from solidworks_mcp …`. That package is
vendored as a **git submodule** (tracking branch `personal`), so
`git submodule update --init` must run before the first `uv sync`. After editing
`pyproject.toml`, re-run `uv sync`; commit `pyproject.toml` **and** `uv.lock`
(never `.venv/`).

## The pipeline is one doit graph

`dodo.py` (repo root) drives the **whole** pipeline: build → verify → export →
release. There is no separate orchestrator and no hand-run scripts for the happy
path — every stage is a doit task. Run it through uv (SolidWorks already open for
the COM tasks):

```
uv run python -m doit             # = `build`: everything + every gate
uv run python -m doit -n 4        # same, check:* fanned out in parallel
uv run python -m doit build_bare  # quick: parts + assemblies only
uv run python -m doit check:math  # one SolidWorks-free gate (no SW needed)
```

The SolidWorks-free `check:*` gates and the comparison/diff tooling run from this
`.venv` with nothing else installed; the COM tasks (`part:`/`assembly:`/
`verify:*`/`export`/`release`) additionally need SolidWorks open on this machine.

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
