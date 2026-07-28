# AGENTS.md — harmonic-analyzer

> [!IMPORTANT]
> **Start every session by invoking the `/developing-solidworks` skill — make it
> your first tool call, before answering or editing anything.** It loads the
> SolidWorks COM conventions and pitfalls the rest of this repo assumes you know;
> reading this file isn't a substitute for loading it. If you've already produced
> output this session without it, invoke it now rather than skipping it.

Orientation for coding agents. Pairs with `docs/pipeline/` (flow diagrams).

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

## Minimum merge gate (every PR)

A PR is not mergeable until ALL THREE hold — no exceptions, no partial
credit:

1. **Build green** — the full `uv run python -m doit -n 4` pipeline (every
   part, assembly and gate) passes on the PR's head. **One** successful build
   is the bar for changes to non-drawing code; a change to drawing code must
   additionally build the drawing fleet **twice in sequence**, since a drawing
   that only builds from a clean slate is not actually reproducible (parts and
   assemblies may come from the remote cache for both passes).
2. **Codex happy** — the Codex auto-review of the latest push found nothing
   (👍 reaction, or its findings were addressed and re-reviewed clean).
3. **Visual inspection of renders** — an eye pass over the rendered PNGs of
   every part/assembly the PR touched (regenerate them if stale or hard to
   read; move the camera off the standard axes when needed). The CAD gates
   prove volumes and mates, not that the geometry LOOKS like the machine —
   a shape can pass every check and still be visibly wrong.

**Stacked PRs share gates 1 and 3.** A successful build at the TOP of a stack
covers every PR in that stack, and so does the visual inspection of the renders
it produces — the top commit contains all of them, so building or eyeballing
each branch separately re-proves the same artefacts on one COM seat. Gate 2 is
NOT shared: Codex reviews each PR's own diff, so every PR in the stack still
needs its own clean review. Order the stack so the riskiest change sits on top —
if it fails, drop it off and gate the remainder, rather than having it block
everything beneath it. Merge bottom-up and do NOT pass `--delete-branch`:
deleting a parent branch auto-closes the children still targeting it.

**Rebase on `main` proactively, not reactively.** Check the branch against
`origin/main` (`git fetch origin main && git status`/`git log HEAD..origin/main`)
before starting new work on it, and always before kicking off a full
`uv run python -m doit -n 4` build — a stale branch risks a green build that
still conflicts or drifts (config/digest/cache-key changes on `main` invalidate
what you just built). Rebase (`git pull --rebase origin main`) as soon as you
find `main` has moved, rather than waiting for a merge conflict or a failed
gate to force it.

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

| group | needs SolidWorks | takes the COM seat lock |
|-------|:---:|:---:|
| `part:<stem>`, `assembly:<stem>` | yes | yes |
| `verify:soundness`, `verify:kinematics` | yes | yes |
| `export`, `release`, `preflight` | yes | yes |
| `check:math`, `check:config`, `check:graph`, `check:nameplate`, `check:recipe`, `check:cache`, `check:partiso` | **no** | no (parallel) |
| `check:verify_telemetry` | **no** | no (opt-in — NOT in build/release) |
| `cache_status` | **no** | no (diagnostic) |
| `build` (default), `build_bare` | meta | — |

- `build` is the **one** fully-safe entry: every part + assembly + every gate.
  (`verify.py` has no `--suite all` anymore — `build` replaced it.)
- `build_bare` = parts + assemblies only (fast, no gates, no export).
- `release` is opt-in: `doit release` defaults to the next `vNN`; pass an
  explicit tag/options after `--` (for example, `doit release -- v22 --draft`).

## The COM seat lock (do not break this)

One SolidWorks STA seat ⇒ COM tasks must never run concurrently. Serialization is
enforced at **runtime** by a cross-process **file lock** (`_com_seat` in `dodo.py`,
backed by `filelock`), NOT by fake `task_dep` edges. Every COM subprocess acquires
the machine-global seat lock right before it drives SolidWorks and releases it after,
so at most one COM task touches the seat at a time **even under `-n N`** — while the
SolidWorks-free `check:*` tasks (which never take the lock) fan out in parallel. The
lock lives under `%PROGRAMDATA%/harmonic-analyzer/com-seat.lock` (override with
`HARMONIC_COM_LOCK`) and, being machine-global, also serializes COM **across
worktrees and concurrent `doit` invocations** on the seat.

The task graph now carries only **real** dependency edges (an assembly's `file_dep`
on its parts, `verify`/`export` on the built `.SLDASM`, `release` on
`export`+`verify:*`+`preflight`+`check:*`), so the DAG reads true and a COM failure
no longer skips *unrelated* downstream COM tasks. (History: this replaced the old
`task_dep` **spine** — `_COM_TAIL`/`_spine_dep`/`_assert_spine_complete`, a
topological linearization of every COM task — which made the DAG lie and coupled
ordering to serialization. See `memory/com-seat-lock.md`.)

**Invariant:** any new COM-touching task MUST run its SolidWorks subprocess inside
`_com_seat(...)` — for a part/assembly action wrap the `_exec` call; for a
`_run`/`_run_stamped` gate pass `com=True`. A COM task that skips it would race the
STA seat. This is enforced loud at runtime: a doit-launched build that reaches
`sw.connect` without `HARMONIC_COM_SEAT` set raises in `_common.run_build` (the
successor to the removed `_assert_spine_complete` tripwire). The cache RESTORE/STORE
(Azure transfers) run **outside** the lock, so cache hits stay parallel; only the COM
subprocess holds the seat.

**Serializes but does NOT isolate:** SolidWorks keys open documents by *filename* and
carries session-global state, so the lock is a safety belt — not a green light for
genuinely-independent concurrent builds on one machine. Still: never hand-launch two
SolidWorks build scripts at once.

Tradeoff (documented, accepted): under a cold `-n N` full build, workers that grab a
COM task block on the seat, so the `check:*` gates can be starved toward the end of
the run (they still run N-wide once COM drains) — a few tens of seconds on a ~25 min
cold build; the incremental/cache-hit common case keeps restores parallel.

## COM watchdog — crash + wedge detection

Every COM subprocess runs a daemon watchdog thread (`_watchdog.py`;
`_common.run_build` starts it right before `sw.connect` and stops it after
`sw.disconnect`) so a dead SolidWorks can never hold the seat forever. Three
signals, two fatal, one log-only:

- **Crash — fatal, exit 86.** A NEW `sldexitapp.exe` process (SolidWorks' own
  crash-report handler; owner of the `#32770` dialog titled "SOLIDWORKS Design" /
  "…has encountered a problem… Generating crash report") means SLDWORKS.exe
  crashed. Do NOT wait on the Windows event log: sldexitapp intercepts WER, so
  the `AppCrash_sldworks.exe` entry lands only once the report completes
  (observed stuck 8.5 h+) — process appearance is the earliest reliable event.
  A pid already alive when the watchdog starts is a stale dialog from an earlier
  crash and is ignored (warned once), so a healthy new SolidWorks can build next
  to a lingering dialog.
- **Op timeout — fatal, exit 87.** No telemetry activity — span boundary or log
  record (`_telemetry.last_activity()`, poked by every span/log) — for
  `HARMONIC_COM_OP_TIMEOUT` seconds (default 900). Calibrated from ~3 weeks of
  `traces.jsonl`: the longest single healthy COM op on record is ~230 s
  (`verify.rebuild`), so 15 min is ~4× headroom — while whole COM tasks
  legitimately run ~27 min (`assembly:summing`), which is why the timeout keys
  on per-op activity, never on process lifetime. Any task-level watchdog must
  use ≥ 40 min.
- **Hung window — log-only, never fatal.** A SLDWORKS.exe top-level window
  failing `IsHungAppWindow` gets a throttled `!!` warn (once per 5 min):
  SolidWorks legitimately stops pumping messages while resolving complex
  geometry, so "not Responding" alone is too noisy to kill on — but the warn
  makes a wedge visible in the log timeline before the op timeout fires.

A fatal signal logs `xx`, flushes telemetry, and hard-exits (`os._exit`) — the
main thread is blocked inside the dead COM call, so only a process exit frees
it. The doit parent then fails the task, and since the seat lock is held by the
PARENT's `_com_seat`, the machine-global seat releases cleanly. Kill switch:
`HARMONIC_COM_WATCHDOG=0`. Recovery after exit 86: clear the crash dialog,
relaunch SolidWorks via the 3DEXPERIENCE Platform desktop shortcut (never
COM-start it), rerun the build. The fatal/log-only contract is pinned by
`check:watchdog` (`test_watchdog.py`).

**Every watchdog action is traceable post-hoc.** All watchdog records carry the
`watchdog_signal` attribute, so `logs.jsonl` yields the full story with one
filter (`rg watchdog_signal … | jq …`): one "COM watchdog armed" info per COM
session (timeout/poll/baseline pids — its absence means the session ran
unprotected), throttled hung-window warns with `hung_s`/`idle_s`, a "responsive
again" info closing each hung episode, and on a fatal an error carrying
`reason`/`idle_s`/`last_op`/`exit_code`. Fatals ALSO emit a `watchdog.abort`
ERROR span (same attrs) so `traces.jsonl` shows the abort even though the
watchdog thread has no ambient span context. `last_op` is
`_telemetry.last_activity_op()` — the heartbeat remembers *what* last poked it
(`span-start <name>` / `span-end <name>` / `log <head>`), so an idle-timeout
abort names the COM operation it was wedged inside, no scrollback needed.

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
A refresh whose mass-properties fingerprint is IDENTICAL to the last gated
save (and that auto-repaired nothing) skips the three health/DOF/interference
gates — they would re-prove what that save already proved (measured 274 s of
a 780 s no-op top-assembly refresh) — while `verify:soundness` independently
re-proves every saved assembly on each build.

**Idempotent — artefact bytes don't drive rebuilds.** Saving an assembly makes
SolidWorks rewrite volatile save metadata into every nested `.SLDPRT`/`.SLDASM`
(the parent-md5 cascade), so a part's *bytes* legitimately churn after its `part:`
task — and after a lower assembly — recorded them. To stop that churn from
re-refreshing every dependent on each build, `ContentChecker._digest` keys a
`.SLDPRT`/`.SLDASM` on its **producing task's build-input recipe** (script + helper
closure + config it reads, folded transitively through referenced artefacts), not
its output bytes — see `_stable_artefact_digest` in `dodo.py`. A real
script/config/referenced-part change still flips the digest; pure save-churn does
not, so a no-change `doit build` is now a true no-op (no phantom refreshes). It is
one chokepoint, so doit staleness, the verify freshness guard (which reuses this
`ContentChecker`), and the remote cache key (also `_digest`) stay in lockstep — and
the cache now hits cross-machine despite per-build PID/save churn. (The recipe digest
is built from **repo-relative** path tags via `_rel_tag`, so it is identical across
checkout roots — an absolute tag would shift every assembly's key per seat and
silently kill cross-machine hits.) *Migration:* this shifts every assembly's cache
key and each artefact dep's stored digest once; the build self-heals over one run
(one rebuild re-stamps the ledger), or run `doit reset-dep` to migrate the `.doit.db`
in place without a rebuild.

> [!NOTE]
> **Recipe digest and CAD identity are separate signals.** The recipe-derived
> `.SLDPRT`/`.SLDASM` digest stays byte-churn-immune for idempotent doit freshness,
> while each built/restored artefact also gets an exact SHA-256 execution token.
> Assemblies depend on their immediate children’s tokens: a same-recipe from-scratch
> rebuild (new PIDs) therefore refreshes dependents, and an assembly cache entry only
> hits against the exact child identities/rebuild stamps it was saved with. Assembly
> tokens propagate this through subassemblies to the top. Pure parent-save metadata
> churn does not restamp tokens, so it still cannot create phantom rebuild cascades.

## Remote build cache (cross-machine)

The cross-machine extension of the above: COM tasks are keyed by their
`file_dep` content hash and their outputs are pulled from / published to a shared
**Azure Blob** cache (over 443) instead of rebuilt on the SolidWorks seat.
Default role is `rw` — a clean checkout on an authorized seat pulls and publishes
with **zero setup**. Set/override a seat's role with `HARMONIC_REMOTE_CACHE_MODE`
or a gitignored `.harmonic-remote-cache-mode` file at the repo root
(`off`/`ro`/`rw`). Full
details — roles, auth, salt-busting, provisioning, caveats — in
[`DEVELOPING.md`](DEVELOPING.md).

**Per-seat part order — two cold builders split the work, not duplicate it.**
Parts have no inter-part deps, so the order in which their tasks are offered to the
scheduler is free. Two seats cold-building in the *same* order march in lock-step,
each MISS the shared cache on the same next part and build it in parallel (N seats ⇒
N× the COM work). So `task_part` YIELDS the parts in a **per-seat permutation**
(`_seat_part_order` in `dodo.py`) and `build` lists them the same way: seat A climbs
one way, seat B another, so by the time the slower seat reaches a part the faster one
has usually published it (a HIT) — the fleet builds each part ~once. With the spine
gone this is a best-effort **scheduling hint**: correctness comes from the COM seat
lock plus a **re-probe of the cache after the seat is acquired** (`_cached_part_action`
/ `build_or_refresh` restore again under the lock, in case a peer published while we
waited), so an imperfectly-honored order costs a little cache-split efficiency, never
a duplicated or skipped build. The seed is the **hostname** (via `hashlib`, *not* the
PYTHONHASHSEED-salted builtin `hash()`, so it is identical across the parent and every
`-n` worker). `HARMONIC_BUILD_ORDER_SEED` overrides it. Order never feeds a cache key
or digest — it is purely scheduling, so permuting is always safe.

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

## Three-tier submodule digest (part vs assembly vs drawing)

The vendored `SolidworksMCP-python` submodule is a runtime input of every COM task,
so its source content is folded into each task's recipe/cache key (issue #144 —
`_submodule_digest` in `dodo.py`). But it is NOT one blob — three tiers, each dropping
the modules that tier's build scripts never call:

- **drawing tasks fold the WHOLE tree** (`_submodule_digest` — the only tier with
  `drawing.py`);
- **assemblies fold the tree MINUS `drawing.py`** (`_submodule_assembly_digest` — see
  `_ASSEMBLY_DIGEST_EXCLUDE_FILES`);
- **parts fold the tree MINUS `{assembly.py, motion.py, drawing.py}`**
  (`_submodule_part_digest` — see `_PART_DIGEST_EXCLUDE_FILES`).

Net: a bump touching only `assembly.py`/`motion.py` rebuilds the ~8 assemblies but
leaves all ~100 parts cached; a bump touching only `drawing.py` rebuilds just the (few)
drawing tasks, not the parts or assemblies. The three sidecars are distinct files
(`.solidworks-mcp-submodule.digest` / `-assembly.digest` / `-part.digest`).

Each exclusion is SAFE because the dropped module is never **CALLED** by that tier's
build scripts:
- `assembly.py`/`motion.py` — a part only ever calls sketch/feature/export methods, so
  their content can't change a part's geometry (they ARE loaded, via the PyWin32Adapter
  mixin, but loading ≠ calling). Assemblies DO call them, so they stay in the assembly +
  drawing tiers.
- `drawing.py` — a stronger case: it is NOT even mixed into the adapter (standalone
  module-level `IDrawingDoc` helpers), so nothing in a part OR assembly build graph
  imports it; only a `draw_*` drawing script does. Hence it drops from both the part and
  assembly digests (matching `drawing.py`'s own docstring).

`check:partiso` (`test_part_isolation.py`) ENFORCES both directions loud: it derives its
forbidden sets straight from `dodo._PART_DIGEST_EXCLUDE_FILES` /
`_ASSEMBLY_DIGEST_EXCLUDE_FILES` and fails if any part script imports an
assembly/motion/drawing module (or the main-repo `_assembly` helper), or any assembly
script imports the drawing module — each checked across the full `module_deps_of`
closure.

Only assembly/motion/drawing are excluded — **the MCP-server surface (`tools/`/`agents/`/
`ui/`/`server*.py`) deliberately stays IN every digest** (codex #191). Excluding it would
rest on a "not-REACHED through the submodule's own import graph" claim (a part-relevant
module like `base.py` could start importing `solidworks_mcp.tools`), which the
repo-local guard cannot see — so those modules are kept, accepting an over-rebuild on a
rare MCP-tooling bump rather than risking a stale part. (drawing.py's exclusion instead
rests on "not-IMPORTED by any part/assembly build script", which IS repo-local
checkable.)

## Verify suites (renamed)

`verify.py --suite <x>` where `<x>` ∈ {`soundness`, `kinematics`, `math`,
`config`}. `math`/`config` need no SolidWorks (wrapped as `check:*`); the other two
open the model (wrapped as `verify:*`). Old names static/isolation/motion/truth,
the `all` aggregate, and the separate `subsystems` suite are gone.

`soundness` opens EVERY built (sub)assembly standalone and runs the shared health
battery on each: **one shared re-solve** (`verify.rebuild`) after open, then DOF /
over-constrained / model-healthy-deep / interference reading that resolved model
(the three gates that each used to `ForceRebuild3` now share one — `resolve=False`;
model-healthy gets the shared rebuild's result). Three former members left the
every-build battery: **gear-ratios** is DEMOTED to the release preflight (it was ~50%
of a run and re-proves a property the tooth-count config already fixes, which
`check:math` validates analytically); **channel-independence** (the retired
`subsystems` suite's one unique gate) is FOLDED IN — soundness already opens
`channel`, so it runs there; and **component-count is REMOVED** (every failure it
ever raised was a stale band or a gate bug, never a real regression — `_COMPONENT_BAND`
stays as reference data). The **DOF gate splits by whether the assembly has
freed operational DOF** (see "Default-free DOF" below): an assembly with freed
DOF (drive-train + channel + magnifier + paper-drive + summing + pen) is
checked by the **free-DOF set gate** (`assert_free_dof_necessity`) — at least
the expected number of top-level components read under-constrained, each freed
DOF's own family among them (necessity), AND, where the assembly's allowed
coupled-family list is pinned (`verify._ALLOWED_FREE_STEMS`), no component
OUTSIDE that list reads under-constrained (the exact-set direction — an
unintended freedom, e.g. a dropped mate on a structural part, fails soundness
loud). Every assembly with nothing freed gets the strict 0-DOF check,
unchanged. All NON-DOF gates always run on the as-built model. gear-ratios
runs at release only, in `preflight_release.py`, on the reopened `drive-train`
+ `channel` (the only assemblies carrying real gear meshes).
(History: `subsystems` used to re-open all 8 and repeat the whole battery — ~95%
duplicate COM work — then was trimmed to only `channel`-independence, and is now
folded into soundness entirely; see `memory/release-perf-incremental.md` and
`memory/checks-perf-value-audit.md`.)

## Default-free DOF (operational kinematics)

The default build saves a **working kinematic model**, NOT a frozen one: the
predetermined operational DOF are left FREE. That is drive-train's **crank spin**
(drag the crank in the saved `.SLDASM` and the whole geared train turns),
**cone-platform swing** (the p1 disengage: the plate — carrying the cone set AND
the crank rig on the merged column — swings on its pivot screw), **pinion engage
swing** (PR8: the strap+pinion rigid group swings on the torque shaft — the p2
setup motion, formerly park-driven at the engaged pose) **and lift-rod/cam spin**
(PR8: the eccentric-cam engage path; 4 DOF total for drive-train), plus channel's
**3 DOF per active channel** (rocker swing +
connecting-rod follow + amplitude-bar slide; 2026-07-07 the **channel lever is
COUPLED**, not separately freed: the J5 foot-on-arc mate — the amplitude bar's
foot axis held at its as-solved radius from the rocker's arc-centre axis
`Axis3@rocker` — closes the rocker → bar → lever chain, so dragging the rocker
articulates the whole channel and the lever reads under-constrained WITH it;
the old J4 hard spin pin is gone), plus magnifier's **lever
knife-rock + lever-wire swing/spin** (3 DOF, 2026-07-04: the lever pivots about
the summing bar's knife-edge ridge — engineerguy video 2/4+4/4, ~6 mm tip arc —
carrying the clamp/vertical-rod/fixture group AND the magnifying-bracket
(2026-07-07: the bracket AFFIXES the rod to the rocking summing bar, so it is
lock-mated to the lever, not grounded — its collar carries the rod concentric
at every rock angle); the lever-wire ball-joints at the fixture hook and rides
the hub drum at its 0.25 stand-off tangency; and the **WIRE-1 yoke mate** — the
wheel's `WireYokePoint` held coincident to the lever-wire's `YokePlane`, the
linearized inextensible-wire constraint — turns the magnifying wheel with it;
the wheel is COUPLED, not separately freed), plus summing's **lever knife-edge
rock** (1 DOF, 2026-07-07: the summing lever rocks live on the knife-mount
ridge, the lock-mated boss-hook riding it), plus pen's **carriage travel**
(1 DOF, 2026-07-07: the rod + lock-mated marker/pen-wire slide vertically in
the v-block; the shipped model carries NO F5 pen-driver equation —
`verify:kinematics` authors the travel drive transiently from the DOF manifest
(`DRIVE_pen_travel`), installs the chained-Fourier equation on it, sweeps
`CrankDeg`, and discards unsaved), plus paper-drive's **crank spin**
(1 DOF, 2026-07-05: the crank-end T12 sprocket spins free; a native **Belt/Chain
feature** (`adapter.insert_belt_chain`, EngageBelt) couples it to the knob T24 at
the 12:24 chain ratio, and a **rack-pinion mate** feeds the platen off the knob
axis at the NET through-train travel `NET_RACK_TRAVEL_PER_KNOB_REV` — knob T24 and
knob are COUPLED, the platen feed is COUPLED, not separately freed). paper-drive's
engaged path is a documented KINEMATIC coupling at the faithful ch30 rest geometry:
the intermediate transgear (fine-pinion → 96T disc) keeps its 13.1 mm rest gap and
the coupling spans it — the single latch arm cannot serve both the 66.05 rest and
51.0 engaged centre distances (DIMENSIONS.md Appendix C #8's open kinematic riddle),
so the engage is coupled, not geometrically meshed. The motion/mobility
diagnostics treat every freed (absent-driver) DOF as already-free
(`build_motion_setup_drives.py`).

The mechanism is the **kinematic DOF manifest**. A freed DOF gets NO driver
mate at all — every part is inserted on its exact Python-solved transform and
the real contact mates hold it, so the saved pose is deterministic without
full definition. The build only RECORDS each freed DOF's drive spec
(`free_dof_key=…` on the `*_driver` helpers → `_assembly` records
`entities`/scalars/rest value/mate side) into a sidecar `.<stem>.dof.json`
beside the `.SLDASM` (a cached assembly output, so it rides the remote cache).
`verify:kinematics` (and the mobility/motion diagnostics) author those specs
TRANSIENTLY (`_assembly_postbuild.author_dof_drives`, mates named
`DRIVE_<key>`) to pin or sweep a DOF on a reopened model, then discard the
model **without saving** — the shipped `.SLDASM` stays the free kinematic
model.

(History: this replaced the two-sided "park driver" machinery — deferred
`PARK_*` mates, a `locked` build mode in `build_lock.yaml`, and a release
0-DOF closure proof (`assert_park_closure`). Killed 2026-07-09: placement
already made the build deterministic, the closure re-proved what insertion
fixed, and the replay path was a recurring bug source. See
`memory/default-free-dof-park-drivers.md`.)

There is **no scalar DOF API** in SolidWorks COM. `soundness` proves the free
set from both directions with one status walk (`assert_free_dof_necessity`):
≥ N components under-constrained with each freed DOF's family present
(necessity), and — where `verify._ALLOWED_FREE_STEMS` pins the assembly's
coupled families — no component outside that list under-constrained (exact
set). As a hand-run diagnostic, `build_mobility_probe.py` authors the manifest
drives to reconstitute a 0-DOF baseline, then suppresses each to show it frees
its own part family.

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
- **Log vs event — a moment IN a span is a span event.** A fact that belongs to a
  span's timeline (a cache hit/miss, a mate flip-recovery, a transient drive
  authored) is recorded with `_telemetry.event("name", **attrs)` — an OTel
  **span event** on the current span — not (only) a standalone log record. It shows
  *when within the span* it happened and carries structured attrs, and is a no-op
  when no span is recording (so a caller never guards). Keep a `warn`/`error` LOG
  for anything a human scanning the console must see (a cache miss is BOTH: a `warn`
  log so it stands out, and a `cache.miss` event so the trace shows it right before
  the build it triggered). Use a plain log for narration that isn't tied to one
  span's lifetime.
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
- **Right granularity — segment the slow, don't span the trivial.** Two failure
  modes, both regressions: (1) a long gate that is ONE opaque span — the bulk of
  its wall-clock hidden in an unspanned region (the `no-over-constrained`,
  `gear-ratios`, `component-count` gates were each a single 80-90 s black box).
  Split the expensive COM sub-steps into named child spans (`over.rebuild` /
  `over.scan`, `gear.read_links`, `count.read`, `verify.open`), exactly as
  `gate.dof`/`gate.health` already do. (2) a tight loop that opens a span PER
  item — `dof.check` per component, `health.whats_wrong` per target — flooding the
  trace with hundreds of near-instant "OK" leaves (335 + 343 in one soundness
  pass) that drown the signal. Do NOT span per item: keep ONE span around the loop
  and record the aggregate (counts) as attributes; per-item lines stay `debug`
  logs, and offenders are named in the raised error the gate span records. (The
  retired park-closure gate was the canonical positive example: its per-driver
  suppress/re-engage cycling split into `park.*` phase child spans instead of
  one multi-minute black box — apply the same segmentation to any future
  multi-phase COM gate.)
- **Descriptive span names, not generic ones.** A waterfall of 40 identical
  `mate distance` rows is unreadable. The single mate chokepoint (`_assembly._mate`)
  names its span for the caller's descriptive `label` (`mate top@crank_pin <-> …`),
  keeping the mate `kind` as an attribute. Prefer a name that says WHICH thing over
  one that says only the operation TYPE.
- **The build body is one `<kind>.build` phase span.** `dodo._exec` opens a span
  NAMED for the doit task (`task part:cone_gear`, `task assembly:drive_train`) — the
  build subprocess CONTINUES it via the injected `TRACEPARENT`. Inside the
  subprocess `run_build` opens ONE inner `part.build` / `assembly.build` phase span
  around the `build()` body (a sibling of `sw.connect` / `sw.disconnect`), so the
  ~40 mates + gates read as children of `assembly.build drive-train` instead of a
  flat run under the task span. This is a PHASE, not the removed `build.<target>`
  ROOT layer that mirrored the task span 1:1 — connect/teardown stay OUTSIDE it.
  `build_session` still *continues* the injected doit task span (no second root)
  and opens a local `build.<target>` root only when a build script runs standalone.
  Non-build entries (`verify.py`, `export_models.py`, the `diagnostics/` probes) get
  no phase wrapper (`kind is None`) — their gates already self-group.
- **Resource = pipeline stage.** The OTel resource `service.name` (the Aspire
  "resource" column) is set PER PROCESS to its stage — `part-build` /
  `assembly-build` / `verify-<suite>` / `check-<gate>` / `export` / `release` —
  under the shared `service.namespace = harmonic-analyzer`, so a trace groups by
  subsystem instead of every span reading one umbrella name. `dodo._exec` injects
  `OTEL_SERVICE_NAME` (the standard OTel var, from `_stage_name`) into each
  subprocess env, so the child is labelled the moment it imports `_telemetry`; a
  standalone script self-labels via `_telemetry.set_service(...)` (fallback-only —
  it never clobbers an inherited label; `force=True` overrides; it rebuilds the
  providers, resetting OTel's one-shot provider guard, since the resource is fixed
  at provider creation). Add a new stage to `_stage_name` when a new task family
  appears. The doit PARENT's `task <label>` span uses `_stage_name` too (via
  `service=` on `_telemetry.span`), so a task and the subprocess it spawns share one
  resource — `task part:cone_gear` reads `part-build`, `task assembly:pen` reads
  `assembly-build`, a drawing reads `drawing-export` — instead of the task reading
  the umbrella name while its own children read the stage. `harmonic-analyzer` is
  now a namespace and a fallback for an unmapped label, not a span label.
    - **`build-infra` owns the seat + cache spans.** Queueing for the COM seat and
      pulling/publishing artefacts belong to no pipeline stage, so `com.seat.wait`,
      `cache.probe` and `cache.store` are attributed to a `build-infra` resource
      (`_telemetry.BUILD_INFRA_SERVICE`) — NOT to the stage their task belongs to —
      so the resource column answers "how much of this build was queue and transfer,
      not work?" in one filter. Together with the stage-labelled `task` span above,
      every span now names either the stage doing the work or the infrastructure
      serving it. A resource is fixed per
      provider, so this is a SECOND `TracerProvider` in the same process
      (`_provider_for_service`), sharing the primary's span processors — one console
      stream, one `traces.jsonl`, one OTLP exporter. Pass `service=` to
      `_telemetry.span` to put a span there; it changes only the resource, never the
      parent/child shape. (Aux providers are built with `shutdown_on_exit=False` and
      skipped by `shutdown()`: they don't own their processors, and double-shutting
      them just re-closes every exporter.)
- **A COM task is a CHAIN of top-level spans, one per phase — never one span that
  swallows the lot.** A cached part/assembly/drawing task emits, all as siblings:
  `cache.probe <label>` (the remote-cache restore attempt — on a HIT this IS the
  task, an Azure download, so the task never vanishes from the trace),
  `com.seat.wait <label>` (blocking on the COM seat), `cache.reprobe <label>` (the
  under-seat re-probe — a peer may have published while we queued, and on a hit that
  is another full download, so it is never inside the work span), `task <label>` (the
  work, starting once the seat is HELD) and `cache.store <label>` (the publish, whose
  `cache` attribute carries the outcome `_cache.store` returns —
  `stored`/`skip`/`empty`/`error`/`off` — since a swallowed upload failure must not
  look like a successful publish). Each
  phase is then timed for what it is: the `task` span can no longer absorb queueing
  or network transfer, so "how long does this part take to build?" is finally
  answerable from `traces.jsonl` — which is what the watchdog calibration and every
  perf audit read. Without the split, the same part read 40 s on an idle seat and
  20 min behind a cold assembly build.
    - `_com_seat` opens the wait span and hands the caller the seconds blocked; the
      `task` span carries them as `seat_wait_s` (`_tag_seat_wait`), so the queue is
      answerable from the task span alone. On release — the `task` span having
      already closed — the seat's TOTAL elapsed time goes to a **log** record with
      `wait_s`/`held_s`/`elapsed_s` fields, not a span event.
    - **Do not nest these.** Putting the wait inside the task span is what this
      replaced, and so is the interim fix that moved the task span's start forward
      to elide the wait: mutating a live span's start is not a spec'd operation
      (start time is recorded at CREATION; only a creation-time `start_time` may
      back-date it), and it left the pre-wait cache events dangling before their own
      span's start. Sibling spans need no timestamp surgery.
    - Cost, accepted: sibling ROOT spans are separate traces (a root has no parent,
      so "sibling" and "one trace" cannot both hold). Correlate by the `label`
      attribute every phase span carries.
- **Cache decisions stay on the phase spans.** A HIT/MISS/STORE is a `cache.*` **span
  event** + a `cache` attribute on the phase span that made the decision (`hit`/`miss`
  on `cache.probe`, `hit-after-wait`/`miss` on `task`), so a miss and the build it
  triggered are backtraceable from the signals, not just the console. A
  miss/drift/soft-error is a `warn` (`!!`), not routine `info` — it is the signal for
  "why did this rebuild?". (`_artifact_cache.py`; still also appended to
  `cache.jsonl`.)
- **Cross-process trace continuity.** `dodo._exec` (the span-less core `_run` and
  the cached part/assembly actions both call) injects W3C trace context
  (`TRACEPARENT`) into each subprocess env via `_telemetry.inject_env`; the build
  script's `build_session` extracts it, so the doit task and the process it
  spawns are **one** end-to-end trace. Preserve `env=_telemetry.inject_env()` on any
  new subprocess launch.
- **The process boundary itself is billed, not dark.** Between a task span starting
  and the child's first span (`sw.connect`) sat ~2–5 s of nothing: process creation,
  interpreter boot, and the import graph (`solidworks_mcp` + `_common` ≈ 0.75 s idle,
  more under `-n` contention). `inject_env` now also stamps `HARMONIC_SPAWN_NS` with
  the launch instant, and the child's `build_session`/`run_pipeline_span` calls
  `_telemetry.record_process_startup()` once, drawing `proc.startup` with children
  `proc.launch` (spawn → `_telemetry` import) and `proc.import` (→ first span). The
  spans are back-dated with OTel's creation-time `start_time`, which is exactly its
  documented use ("SHOULD only be set when span creation time has already passed") —
  no live span is mutated. A process nobody stamped (standalone run) or a stale
  inherited stamp (>1 h) records nothing.
- **Telemetry must not cost seat time.** Two measured traps, both fixed, both worth
  remembering before adding an exporter: (1) the OTLP default endpoint is a **literal
  loopback address, never the name `localhost`** — on Windows `localhost` resolves to
  `::1` first and the Aspire dashboard is IPv4, so the first POST ate a ~2 s failed
  connect *per process* (twice: spans and logs), measured 2.05 s vs 0.003 s for
  `127.0.0.1`; `_resolve_otlp_endpoint` tries IPv4 then the v6 loopback, both literal.
  (2) OTLP export is **batched** (`BatchSpanProcessor` / `BatchLogRecordProcessor`) so
  it never runs on the calling thread — a build subprocess holds the COM seat for its
  whole life, so any synchronous export is seat time. Console + `.jsonl` stay on
  Simple processors (live console; capture that cannot lose a record to a queue). The
  batch trade is safe only because `shutdown()` flushes BOTH providers and runs on both
  exit paths (`run_build`'s tail, and the watchdog before `os._exit`) — keep it that
  way. Net: ~4 s per process of pure telemetry overhead removed, on ~110 COM tasks.
- **Where it goes.** Console (stderr) by default; full span/log JSON is also
  captured (best-effort, never fatal) under `cad/out/reports/telemetry/`
  (`traces.jsonl` / `logs.jsonl`, gitignored). Pass `configure(console=False)` to
  suppress the console channels without touching capture.
- **Debug from the capture, not scrollback.** Each line of those two files is one
  OTel record: `traces.jsonl` spans carry `name`, start/end, `status`, the task
  `attributes` (label, cmd) and a `resource` whose `service.name` is the pipeline
  stage; `logs.jsonl` records carry `severity_text`/`body` plus the correlated
  trace/span ids. When diagnosing a failed, slow, or mysteriously-rebuilt task,
  query these with `rg`/`jq` (filter by span name, ERROR status, stage, or a
  trace id lifted from a log line) — and pair them with the per-task console logs
  teed under `cad/out/logs/` — rather than scraping the doit console output.
- Safety net: `cad/scripts/test_telemetry.py` (SolidWorks-free, `check:telemetry`)
  asserts the severity split, no-gap span status, log↔trace correlation, and
  cross-process propagation. Run it after editing `_telemetry.py`.
  `cad/scripts/test_verify_telemetry.py` (`check:verify_telemetry`) pins the verify-
  gate span SHAPE — it drives the REAL gates through a mock SolidWorks whose COM
  calls sleep at durations calibrated from the release logs (`HARMONIC_MOCK_SCALE`,
  default 0.01 of real; `… --demo` prints the real console span tree), asserting
  the per-item floods stay collapsed and the slow gates keep their child spans. Run
  it after editing a verify gate's span structure (`verify.py` / `_assembly.py`).

## Release-diff parallelism

`comparisons/tools/render_diff.py` (the SolidWorks-free diff `cut_release` runs)
parallelizes its per-mesh Hausdorff classification across a process pool
(`--jobs`, default auto). `cut_release` benefits with no change. `--jobs 1`
forces serial (debugging / a fallback if the spawn-mode pool misbehaves).

## Comparison gallery — produced on export, shipped in the release bundle

The reference-photo comparison gallery (this model overlaid on Michelson's ch30
photos) is **derived**: its CAD renders, composites, RMS scores, `index.html` and
even the prepared reference crops drift as the model (or a crop param) changes.
Tracking them dirtied the tree on every rebuild and shipped a stale showcase, so
the whole gallery is now **gitignored and regenerated** —
`comparisons/{ref,render,composite}/`, `comparisons/scores.json`,
`comparisons/index.html`. Only the **source** stays tracked:
`comparisons/manifest.json` (the pose/align source of truth), `ATTRIBUTION.md`
(CC BY credits) and `tools/`; the reference *photos* live in the pinned
`references` submodule and their crops are re-derived by `prepare_reference`.
Because nothing tracked is rewritten, the refresh can never dirty the worktree
the release tag pins (an earlier version kept `ref/` tracked and could publish a
dirty tree — Codex P2).

**Produced by the `export` stage, shipped by `release`.** The gallery is refreshed
inside the export task, not the release: `export_models.refresh_comparison_gallery`
runs **once the STLs are written** (the tail of `export_models.main`, so the
offline renderer reads settled geometry), `--stale-only` so only pairs whose
geometry changed re-render. It first **prunes** any render/composite/score/ref
whose pair id left the manifest (targeted, so it does *not* force a full
re-render) — so a removed/renamed pair leaves nothing stale and the pair count
stays honest. `cut_release.py:stage_comparisons` then simply **copies** that
gallery — plus `ATTRIBUTION.md`, so the redistributed CC BY imagery stays credited
— under the bundle's `comparisons/`. Each release therefore publishes a fresh,
self-contained snapshot (`open comparisons/index.html`).

Both steps are **best-effort** on the Blender front: the renderer lives on a
separate GPU seat, so an `export` run on the SolidWorks seat logs a `warn`
(`export.comparisons` span, `refreshed=false`) and skips; `stage_comparisons` then
finds no gallery and ships the bundle without it (`release.comparisons`,
`staged=false`) — or, if an *old* gallery lingers, ships it with a loud
`STALE vs geometry` warning rather than silently publishing stale renders. Refresh
it standalone anytime — unchanged — with
`uv run comparisons/tools/render_offline.py` (Blender), then `gallery.py`.

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
