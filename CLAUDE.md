
## Git Workflow - CRITICAL REQUIREMENTS
⚠️ **STRICT ADHERENCE REQUIRED** - These git workflow rules are mandatory and must be followed exactly:

- **Auto-commit after EVERY change**: You MUST commit immediately after ANY file modification, no matter how small - NO EXCEPTIONS. This includes:
  - Single line edits
  - Configuration changes
  - Code refactoring
  - ANY file creation or deletion
- **Run git operations on the background**: ALWAYS run git commands on the background so productivity is not impacted - NEVER call git directly from main thread
- **Commit first, ask questions later**: Do NOT wait for user confirmation before committing. Commit immediately after making changes
- **Push frequently**: Push after every few commits or when completing a logical unit of work
- **Include lint/test status in commits**: Run lint before committing. If there are failures, fix them if possible or note in commit message and proceed
- You must use uv if using python tools

## Building the model
- **`doit` (`dodo.py` at the repo root) is the single entrypoint for the WHOLE pipeline** —
  build → verify → export → release. This repo is a **uv project**: `uv sync` once (reads
  `pyproject.toml` + `uv.lock`, creates `.venv/`), then run via `uv run python -m doit`;
  SolidWorks must already be open for the COM tasks. The lockfile pins `doit`, `pillow` (PNG
  export/trim), `pytest` (the `check:*` unit tests), `numpy`/`trimesh`/`matplotlib` (diff
  tooling), the COM bindings (`pywin32`, `comtypes`), and the sibling `solidworks-mcp-python`
  package (editable path source — `verify.py`/`_common.py`/`_assembly.py` import it).
  `solidworks-mcp-python` is a git submodule (`./SolidworksMCP-python`, branch `personal`) — run
  `git submodule update --init` before the first `uv sync`.
- **One safe entry: `doit build`** (= the default task) runs every part + assembly + EVERY
  gate. `doit build_bare` is the quick parts+assemblies-only rebuild. `doit export` / `doit
  release -- vX.Y.Z` are opt-in. Task groups are named by SolidWorks-dependence:
  `verify:*` (soundness/subsystems/kinematics) and `part:`/`assembly:`/`export`/`release`
  need SW; `check:*` (math/config/graph/nameplate/recipe) are SolidWorks-free.
- **Refresh vs full.** doit hashes script + config content (immune to git/worktree mtime churn)
  and propagates a part → assembly DAG. When only a part changed, the dependent assembly is
  *refreshed* — reopen + per-config `ForceRebuild3` + health/DOF/interference gates + in-place
  `Save3` (seconds) — instead of a from-scratch re-insert/re-mate (~500 s). It escalates to a
  *full* rebuild (+ any post-assembly hooks) when the assembly script / `_common.py` / a hook
  changed, or the target is missing. Force a full rebuild of one assembly by deleting its
  `.SLDASM` target, then `doit assembly:<stem>`.
- **Fine-grained config deps.** Each part/assembly depends on ONLY the `cad/config` files it
  actually reads, derived by static analysis of its `_config.<accessor>` calls (`config_files_of`
  in `_buildgraph.py`); dodo.py honors it as the file_dep + assembly-recipe set. `machine.yaml`
  and `parts.yaml` are SPLIT per-subsystem (`machine/<subsystem>.yaml` + `_base.yaml`) and
  per-part (`parts/<dashed-name>.yaml` + `_defaults.yaml`); `_config._doc` re-aggregates them
  transparently, so accessors/verify/provenance are unchanged. Net: editing one part's registry
  row rebuilds only that part; a `machine channels.active_count` edit (in `machine/channels.yaml`)
  skips the gear parts (they read `machine/gear_train.yaml`); the narrative `dimensions.yaml`
  (read by no part) rebuilds nothing. It is CONSERVATIVE — any `_config` use the analyzer can't
  classify falls back to the whole config — so it can only over-rebuild, never skip a real change.
  Don't add a new `_config` accessor without mapping it in `_buildgraph` (`check:graph`'s
  coverage test fails loud otherwise). After this change first lands (file_dep paths moved), run
  `doit reset-dep` once to migrate the DB in place WITHOUT a rebuild — the artefacts are current
  (values are byte-identical, only the files moved).
- **Fail loud.** A refresh that hits a dangling mate, free DOF, or interference exits non-zero
  and leaves the `.SLDASM` untouched — never a stale artefact.
- **Parallelism via the COM spine — `-n` is now SAFE.** A single SolidWorks STA seat still
  means COM work must be serial, but `dodo.py` enforces that with a linear `task_dep` *spine*
  through every COM task (parts → assemblies → verify:* → export → release), so at most one
  COM task is ever runnable even under `doit -n N`. The SolidWorks-free `check:*` tasks sit
  off the spine and fan out in parallel. Do NOT remove a COM task's spine edge or add a new
  COM task without extending `_COM_TAIL`/`_spine_dep` in `dodo.py` (a gap would let two COM
  tasks run at once and deadlock the seat). Corollary still holds: never launch two SolidWorks
  build scripts by hand at once.