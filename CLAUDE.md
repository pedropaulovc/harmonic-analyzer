
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
  build → verify → export → release. Run it with the Windows SolidWorks build venv python
  (`C:\src\SolidworksMCP-python\.venv\Scripts\python.exe -m doit`); SolidWorks must already be
  open. Install once: `…\.venv\Scripts\python.exe -m pip install doit pillow pytest` (pillow
  backs PNG export/trim; pytest backs the `check:*` unit tests).
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