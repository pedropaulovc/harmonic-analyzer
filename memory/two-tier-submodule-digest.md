---
name: two-tier-submodule-digest
description: THREE-tier SolidworksMCP submodule digest — parts exclude {assembly,motion,drawing}, assemblies exclude {drawing}, the opt-in drawing task folds the whole tree; check:partiso enforces both exclusions
metadata:
  type: project
---

**Now THREE tiers (2026-07-08, drawing pipeline PR).** A third tier was added for the
opt-in `drawing` task so drawing-code edits rebuild NEITHER parts NOR assemblies:
- **Parts** fold `_submodule_part_digest()` = tree MINUS `_PART_DIGEST_EXCLUDE_FILES` =
  {`assembly.py`, `motion.py`, `drawing.py`}.
- **Assemblies** fold `_submodule_assembly_digest()` (`_submodule_assembly_dep()` sidecar
  `-assembly.digest`) = tree MINUS `_ASSEMBLY_DIGEST_EXCLUDE_FILES` = {`drawing.py`}.
  `_recipe_files` points assemblies at this, NOT the whole-tree `_submodule_dep()`.
- **The `drawing` task** folds `_submodule_digest()` = the WHOLE tree (conservative; one
  opt-in task).
- SAFE because `drawing.py` is module-level functions (NOT a mixin) — no part/assembly
  build imports it. `check:partiso` gained an ASSEMBLY-isolation test (derives from
  `_ASSEMBLY_DIGEST_EXCLUDE_FILES`) mirroring the part guard.
- Proven: editing `drawing.py` leaves part+assembly digests UNCHANGED, only the full
  digest moves (call the uncached `_digest_submodule_files` primitive — the
  `_submodule_*_digest()` wrappers memoize, so re-calling in one process is a no-op and
  a naive isolation test falsely reads "unchanged" for all three).
- MIGRATION: introducing the assembly-tier sidecar shifted every assembly's remote-cache
  key once (8 assemblies read MISS in `cache_status`), but locally the recipe digest is
  unchanged so doit keeps them up-to-date — the default build is unaffected; the cache
  self-heals on the next clean build.

**Original two-tier design (2026-07-05) below — still the load-bearing rationale.**

**The bug (2026-07-05):** a submodule bump that touched only assembly-level code
(`adapters/solidworks/assembly.py`) made ~84 UNCHANGED parts go cache-MISS and rebuild
— because `_submodule_digest()` folded the WHOLE submodule tree into EVERY part's
recipe/cache key. An assembly-only change should never rebuild a part.

**The fix — two-tier digest in `dodo.py`:**
- **Parts** fold `_submodule_part_dep()` → `_submodule_part_digest()` = the whole tree
  MINUS the two assembly/motion COM modules. `_PART_DIGEST_EXCLUDE_FILES` =
  {`adapters/solidworks/assembly.py`, `adapters/solidworks/motion.py`}. Tags are
  PACKAGE-relative (`_is_part_relevant_submodule_file` keys off
  `relative_to(SUBMODULE_SRC)`, not `_rel_tag`, so it works in the test sandbox too).
- **Assemblies** keep `_submodule_dep()` → `_submodule_digest()` = the WHOLE tree
  (conservative; only ~8 of them).
- Distinct sidecars: `.solidworks-mcp-submodule.digest` vs `-part.digest`.

**Why it's SAFE (the load-bearing invariant):** a part only ever CALLS
sketch/feature/export methods — never an assembly/motion method. `assembly.py`/
`motion.py` ARE loaded transitively (PyWin32Adapter mixes them in) but loading ≠
calling; those modules import `base`/`com_variant`, never the reverse, so their content
can't propagate into a part's geometry. This "not-CALLED" basis is fully checkable from
repo-local code.

**Only assembly/motion are excluded (codex #191, round 2).** The MCP-server surface
(`tools/`/`agents/`/`ui/`/`server*.py`) was initially excluded too, but Codex flagged
that the repo-local guard can't verify the submodule's OWN internal import graph: a
part-relevant submodule file (e.g. `base.py`) could start importing `solidworks_mcp.
tools`, and the exclusion would silently go stale. Rather than add a submodule-closure
walk, we narrowed the exclusion to just assembly/motion (whose safety rests on
not-CALLED, not not-REACHED) and kept the server tree IN the part digest — accepting an
over-rebuild on a rare tooling bump over any stale-part risk.

**Enforced loud:** `check:partiso` (`cad/scripts/test_part_isolation.py`, offline gate,
in `_CHECK_NAMES`) derives its forbidden-import set straight from
`dodo._PART_DIGEST_EXCLUDE_FILES` and fails if any part script (or a repo-local helper
it transitively imports, via `module_deps_of`) DIRECTLY imports an excluded module or
the main-repo `_assembly` helper. Its `file_dep` is the FULL transitive helper closure
(not just part scripts), so a helper gaining a forbidden import re-runs the gate even
when no part script changes (codex #191, round 1). Verified: 95 part scripts, 0
offenders.

**Caveat:** this session's submodule branch also changed `base.py`/`com_variant.py`/
`sketch.py` (part-RELEVANT), so parts still rebuilt once here; the fix prevents FUTURE
assembly-only bumps from doing so. Full design in AGENTS.md "Two-tier submodule digest".
Related: [[incremental-builds-validation]], [[submodule-pointer-drift]],
[[belt-chain-feature-com-binding]].
