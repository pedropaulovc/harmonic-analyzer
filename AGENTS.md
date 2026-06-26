# AGENTS.md — harmonic-analyzer

> [!IMPORTANT]
> **Start every session by invoking the `/developing-solidworks` skill — make it
> your first tool call, before answering or editing anything.** It loads the
> SolidWorks COM conventions and pitfalls the rest of this repo assumes you know;
> reading this file isn't a substitute for loading it. If you've already produced
> output this session without it, invoke it now rather than skipping it.

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

1. Invoke `/developing-solidworks` first (see the note at the top of this file).
2. Python tooling: always use `uv`.

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

## SolidWorks is the source of truth — CadQuery is local-only

This codebase builds its CAD **primarily with SolidWorks** via the COM API; the
SolidWorks parts/assemblies are the only artefacts that ship. When a SolidWorks
seat isn't available, you MAY use **CadQuery** as a head-less stand-in to
prototype or eyeball a part's geometry — but **for local development ONLY**.

**No CadQuery code may be merged.** Keep stand-ins out of commits and PRs; the
SolidWorks build script stays the single tracked source for every part. (Any
CadQuery file that lands on a branch must be removed before merge.)

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
| `check:math`, `check:config`, `check:graph`, `check:nameplate`, `check:recipe`, `check:cache` | **no** | no (parallel) |
| `cache_status` | **no** | no (diagnostic) |
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

## Remote build cache (cross-machine)

The cross-machine extension of the above: COM tasks are keyed by their
`file_dep` content hash and their outputs are pulled from / published to a shared
**Azure Blob** cache (over 443) instead of rebuilt on the SolidWorks seat.
Default role is `rw` — a clean checkout on an authorized seat pulls and publishes
with **zero setup**. Set/override a seat's role with `HARMONIC_CACHE_MODE` or a
gitignored `.harmonic-cache-mode` file at the repo root (`off`/`ro`/`rw`). Full
details — roles, auth, salt-busting, provisioning, caveats — in
[`DEVELOPING.md`](DEVELOPING.md).

**Debugging a miss.** A cache key is `sha256(epoch + salt + Σ(relpath, digest))`,
so a key that shifts unexpectedly is usually one dep digest moving. Three tools
make that visible without scrollback archaeology (all best-effort, never able to
fail a build):

- **`doit cache_status`** — per part/assembly: HIT/MISS (a backend presence probe,
  no download) + key + the per-dep digests, so *any miss is explainable in one
  command*. Positional args after `--`: label substrings to filter
  (`doit cache_status -- cone_gear`), `miss` (only misses), `all` (dump dep digests
  for every task, not just misses). A `DRIFT(...)` flag marks a task whose current
  key differs from the last key this seat published.
- **`HARMONIC_CACHE_DEBUG=1`** — during a real build, logs every `(digest, relpath)`
  feeding each key plus the final key, tagged by task.
- **`cad/out/reports/cache.jsonl`** — append-only event log (key + event:
  `store`/`restore_hit`/`restore_miss`/`restore_hit_drift`/…), so post-hoc debugging
  reads a file. On a HIT under a key this seat never published — the
  store-skip-on-hit drift that bit v0.9.0 — `restore` emits a `WARN` and a
  `restore_hit_drift` event.

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

`soundness` opens EVERY built (sub)assembly standalone and runs the shared health
battery on each (DOF / over-constrained / model-healthy-deep / interference /
gear-ratios / component-count). `subsystems` runs ONLY the subsystem-SPECIFIC gate
soundness doesn't — currently just the `channel` assembly's 20-way moving-stem
instance independence — so it opens only `channel`. (It used to re-open all 8 and
repeat the whole battery, ~95% duplicate COM work and the biggest spine time sink;
see `memory/release-perf-incremental.md`.) soundness runs first on the COM spine, so
the shared battery is always proven before subsystems.

## Stamps & incrementality

Gates produce no CAD artefact, so each writes a stamp under `cad/out/reports/`
(`verify-*.ok` / `check-*.ok`) as its doit target — re-runs only when a `file_dep`
changes. `cad/out/` is gitignored.

## Observability — OpenTelemetry (do not `print`)

The pipeline is instrumented with **OpenTelemetry**, not `print()`. `cad/scripts/
_telemetry.py` is the spine; it is **preconfigured on import** (console logging +
tracing, zero env, no collector) and re-exported through `_common`, so the ~170
scripts that `from _common import log, check` are instrumented unchanged.

- **Log, don't print.** Use the severity helpers — `_telemetry.debug` (`..`),
  `.info` (`--`), `.success` (the old `  OK  `), `.warn` (`!!`), `.error` (`xx`).
  Each prints the historical glyph line to **stderr** *and* emits a correlated
  OTel log record at the matching `SeverityNumber`. `_common.log`/`check` are thin
  aliases (`log`→`debug`, a passing `check`→`success`). New code must not add bare
  `print()` for status — reserve `print` for machine-readable stdout a caller pipes.
- **Spans, no gaps.** Wrap work in `with _telemetry.span("name", **attrs):` — it
  sets status OK on clean exit and, on an exception, records it + sets ERROR before
  re-raising, so a failure is never a silent hole. The build is a TREE of operation
  spans, not a monolith: the per-step `_common` helpers (`define_circle`,
  `extrude_at_offset`, `volume_check`, `save_part_and_images`, …) carry an
  `@_telemetry.traced("sketch.circle", label_param="label")` decorator, so each
  becomes a child span automatically. `verify.Report.gate` opens one per gate.
  **Any new COM-touching entry point must open a span** (mirrors the COM-spine
  invariant): an unparented operation is a gap. Add `@traced` to a new operation
  helper rather than leaving it inside the parent span unsegmented.
- **One span per build, no duplicate layer.** `dodo._run` opens a span NAMED for
  the doit task (`part:cone_gear`, `verify:soundness`). `run_build` uses
  `_telemetry.build_session`, which *continues* that span when the spine injected a
  parent context (operation spans attach straight to the task span — no second
  `build.<target>` layer) and opens a local `build.<target>` root only
  when a build script is run standalone. So a build is one tree, never two
  stacked roots for the same part.
- **Cross-process trace continuity.** `dodo._run` injects W3C trace context
  (`TRACEPARENT`) into each subprocess env via `_telemetry.inject_env`; the build
  script's `build_session` extracts it, so the doit task and the process it
  spawns are **one** end-to-end trace. Preserve `env=_telemetry.inject_env()` on any
  new subprocess launch.
- **Where it goes.** Console (stderr) by default; full span/log JSON is also
  captured (best-effort, never fatal) under `cad/out/reports/telemetry/`
  (`traces.jsonl` / `logs.jsonl`, gitignored). Pass `configure(console=False)` to
  suppress the console channels without touching capture.
- Safety net: `cad/scripts/test_telemetry.py` (SolidWorks-free) asserts the
  severity split, no-gap span status, log↔trace correlation, and cross-process
  propagation. Run it after editing `_telemetry.py`.

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
  inside the already-serial release job — not worth extracting.) The release PNG
  cost is instead addressed by an **incremental render cache** keyed on
  resolved-geometry fingerprint (`cut_release._png_key`), so a geometry-unchanged
  release re-renders nothing. (STEP/STL are still SaveAs3-exported per document —
  `cad/out` is the manifest-driven render cache, not the full per-document neutral
  set, so it cannot be copied wholesale.) See `memory/release-perf-incremental.md`.
- **`diff:<stem>` per-part doit fan-out — not a fit.** `render_diff` renders the
  *whole* assembly in 4 views, not per-part images; the expensive, parallelizable
  work is the Hausdorff loop, which is now parallelized inside the script (above)
  rather than as separate doit tasks.
