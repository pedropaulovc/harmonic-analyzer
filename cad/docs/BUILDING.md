# Building the model

The CAD model is generated headlessly from a clean checkout. Every task that
drives COM needs a SolidWorks seat, and there are two ways to have one:

- **A local licensed seat.** SolidWorks installed and running on this machine,
  launched via the 3DEXPERIENCE desktop shortcut rather than `sldworks.exe`
  directly. This is what the `uv run python -m doit` examples below assume.
- **A seatless submitter.** No SolidWorks here at all: `build.py --executor
  farm` dispatches each cache-missing COM task as a farm leaf and restores what
  the worker published. An agent-driven farm build has its own launch contract —
  see [supervised farm launches](../../DEVELOPING.md#supervised-farm-launches).

The SolidWorks-free `check:*` gates, `gallery` and the comparison tooling need
no seat under either arrangement.

For orientation on how the code is organized, read
[`../../AGENTS.md`](../../AGENTS.md); for machine-local workflow (the remote
build cache, auth, provisioning) and the supervised farm-launch contract read
[`../../DEVELOPING.md`](../../DEVELOPING.md).

## One-off setup

```powershell
git submodule update --init --recursive
uv sync
```

## The pipeline is one doit graph

The **entire** pipeline — build → verify → export → release — is one
[`doit`](https://pydoit.org) graph (`dodo.py` at the repo root). doit hashes
script + config content (immune to git/worktree mtime churn) to decide what is
stale, and propagates a part → assembly dependency DAG. When only a part
changed, the dependent assembly is **refreshed** (reopen + per-config
`ForceRebuild3` + health/DOF/interference gates + in-place save — seconds)
instead of rebuilt from scratch (re-insert + re-mate ~122 components — ~500 s).
A refresh that hits a dangling mate, free DOF, or interference **fails loud**
(non-zero exit, the `.SLDASM` left untouched).

Tasks are grouped by whether they need SolidWorks — the prefix tells you at a
glance:

| group | needs SW? | where it runs | what it does |
|-------|:---:|---|--------------|
| `part:<stem>` / `assembly:<stem>` / `drawing:<stem>` | yes | local seat or farm leaf | build/refresh a part, assembly or drawing |
| `verify_soundness:<stem>` / `verify:kinematics` | yes | local seat or farm leaf | DOF/interference/health gates per (sub)assembly · motion-study pen sweep |
| `verify:soundness` | no (aggregator) | local | fans out to the `verify_soundness:<stem>` leaves; drives no COM itself |
| `preflight` / `export` / `package:release` | yes | local seat or farm leaf | release preflight (gear ratios) · neutral STEP/STL/glTF + scene-graph export · Pack-and-Go |
| `check:math` / `check:config` / `check:graph` / `check:nameplate` / `check:numerals` / `check:recipe` / `check:cache` / `check:partiso` / `check:budget` | **no** | local only | Fourier math · config audit · pure-python unit tests |
| `gallery` | **no** (Blender + GPU) | local only | refresh the photo-vs-CAD comparison gallery; no farm worker has Blender |
| `release` | meta | local (publishes) | stages, diffs, tags and publishes; its COM half is the separate `package:release` leaf |
| **`build`** | yes | either executor | **every** part + assembly + **every** gate — the one fully-safe entry |
| `build_bare` | yes | either executor | parts + assemblies only — a quick rebuild |

These examples run on a **local seat**. For the farm, replace
`uv run python -m doit` with `build.py --executor farm` and follow
[supervised farm launches](../../DEVELOPING.md#supervised-farm-launches) —
the same task names select the same closure.

```powershell
# The one fully-safe build: every part + assembly + every gate (= default task)
uv run python -m doit

# Same, but fan the SolidWorks-free check:* gates out across 4 workers while the
# COM build/verify stream stays serial (safe — see "Parallelism" below)
uv run python -m doit -n 4

# Quick rebuild — parts + assemblies only, no gates or export
uv run python -m doit build_bare

# Just one part (doit selection does NOT run reverse dependents — the dependent
# .SLDASM/renders stay stale until you run plain `doit` or select them explicitly)
uv run python -m doit part:cone_gear

# Just one assembly (+ its stale prerequisites), or a single gate
uv run python -m doit assembly:paper_drive
uv run python -m doit verify:soundness        # one SW gate
uv run python -m doit check:math              # one offline gate

# Neutral export, then cut the next vNN release (explicit tag after `--` is optional)
uv run python -m doit export
uv run python -m doit release

# Inspect the graph / clean
uv run python -m doit list --all
uv run python -m doit clean
```

`cad/config/release.yaml` reserves the Revision stamped into every native CAD
file and linked drawing title block. A successful publish advances it to the
next `vNN`; commit and merge that tracked version bump before the next release.

## Parallelism

There is one SolidWorks STA seat per machine, so COM work must stay serial on it
— but the SolidWorks-*free* `check:*` gates need not. Serialization is enforced
at runtime by a cross-process **file lock** (the COM seat lock): every COM
subprocess grabs it before driving SolidWorks, so at most one COM task touches
the seat **even under `-n N`**, while `check:*` tasks (which never take the
lock) fan out in parallel. The lock is machine-global
(`%PROGRAMDATA%/harmonic-analyzer/com-seat.lock`, override `HARMONIC_COM_LOCK`),
so it also serializes COM across worktrees on the seat. Outputs land in
`cad/out/` (gitignored).

The same lock is what bounds a farm worker: it serializes that worker's own COM
session, not the fleet. Different workers hold different seats and run different
leaves at the same time, which is why a farm submitter keeps several leaves in
flight. Run `build.py --executor farm` yourself and it adds `-n 8`
(`HARMONIC_FARM_PARALLELISM`) unless you pass `-n`/`--process`; the supervised
launcher passes `-n 4` explicitly, so a supervised run keeps four in flight.

## Forcing a full rebuild of one assembly

Bypass the cheap refresh by deleting its target — a missing target makes doit
take the FULL branch (hooks included):

```powershell
del cad\out\sldasm\paper-drive.SLDASM
uv run python -m doit assembly:paper_drive
```

## Repository layout

```
cad/               everything about the CAD reconstruction
  scripts/         Python reproduction scripts (build_<part>.py, build_<sub>_assembly.py),
                   shared helpers (_common.py, _gear.py, _chain.py); refresh_assembly.py,
                   _buildgraph.py (the doit build graph lives in dodo.py at the repo root)
  scripts/diagnostics/   archived one-off probe/diag scripts (not part of the build)
  config/          YAML source-of-truth for parametrics, tolerances, materials (data layer)
  docs/            design policies: motion, tolerance, assumptions, known limitations,
                   machining DFM, and this file; docs/images holds the tracked renders
                   and photographs (docs/images/README.md says how to remake each one)
  comparisons/     photo-vs-CAD alignment + render pipeline (manifest-driven)
  out/             generated artefacts — gitignored, regenerated by doit (dodo.py)
references/        source book, video keyframes, manuals (git submodule)
research/          per-phase research notes
book/              the machining book (Quarto)
logbook/           the machining curriculum and practice log
web/               the interactive simulator (Vite + three.js)
kickstarter/       campaign planning
ai-story/          the write-up of building this with AI agents
dodo.py            doit build graph (part→assembly DAG; refresh vs full rebuild)
```

## Toolchain (pinned)

A book supplement must reproduce for years, so the toolchain is pinned like a
compiler:

- **SolidWorks**: 3DEXPERIENCE for Makers, **R2026x** — the COM API surface and
  file format change yearly; readers need a compatible release.
- **Python**: managed by `uv` from `pyproject.toml` + `uv.lock` (always `uv` +
  venv, never `--system`).
