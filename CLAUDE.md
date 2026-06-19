
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
- **`doit` (`dodo.py` at the repo root) is the build entrypoint** — it replaced the hand-rolled
  `build_all.py` orchestrator (removed). Run it with the Windows SolidWorks build venv python
  (`C:\src\SolidworksMCP-python\.venv\Scripts\python.exe -m doit`); SolidWorks must already be
  open. Install once: `…\.venv\Scripts\python.exe -m pip install doit pillow` (pillow backs the
  PNG export + README-render trim that both the full build and the refresh tail run).
- **Refresh vs full.** doit hashes script + config content (immune to git/worktree mtime churn)
  and propagates a part → assembly DAG. When only a part changed, the dependent assembly is
  *refreshed* — reopen + per-config `ForceRebuild3` + health/DOF/interference gates + in-place
  `Save3` (seconds) — instead of a from-scratch re-insert/re-mate (~500 s). It escalates to a
  *full* rebuild (+ engagement-config hooks) when the assembly script / `_common.py` / a hook
  changed, or the target is missing. Force a full rebuild of one assembly by deleting its
  `.SLDASM` target, then `doit assembly:<stem>`.
- **Fail loud.** A refresh that hits a dangling mate, free DOF, or interference exits non-zero
  and leaves the `.SLDASM` untouched — never a stale artefact.
- **Serial only — NEVER pass `-n`/`-P`** (doit's parallel flags). A single SolidWorks STA
  session means parallel tasks deadlock the COM seat; `dodo.py` hard-fails if it sees them.
  Corollary: never run two SolidWorks build scripts at once.