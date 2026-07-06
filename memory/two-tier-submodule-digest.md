---
name: two-tier-submodule-digest
description: Parts fold only the part-relevant SolidworksMCP submodule slice (excl. assembly/motion/MCP-server), assemblies fold the whole tree — check:partiso enforces parts never import asm-level code
metadata:
  type: project
---

**The bug (2026-07-05):** a submodule bump that touched only assembly-level code
(`adapters/solidworks/assembly.py`) made ~84 UNCHANGED parts go cache-MISS and rebuild
— because `_submodule_digest()` folded the WHOLE submodule tree into EVERY part's
recipe/cache key. An assembly-only change should never rebuild a part.

**The fix — two-tier digest in `dodo.py`:**
- **Parts** fold `_submodule_part_dep()` → `_submodule_part_digest()` = the whole tree
  MINUS the assembly/motion COM modules and the MCP-server surface. Exclude list =
  `_PART_DIGEST_EXCLUDE_FILES` (`adapters/solidworks/assembly.py`, `.../motion.py`,
  `server.py`, `server_cli_fixed.py`) + `_PART_DIGEST_EXCLUDE_DIRS` (`tools/`,
  `agents/`, `ui/`). Tags are PACKAGE-relative (`_is_part_relevant_submodule_file`
  keys off `relative_to(SUBMODULE_SRC)`, not `_rel_tag`, so it works in the test
  sandbox too).
- **Assemblies** keep `_submodule_dep()` → `_submodule_digest()` = the WHOLE tree
  (conservative; only ~8 of them).
- Distinct sidecars: `.solidworks-mcp-submodule.digest` vs `-part.digest`.

**Why it's SAFE (the load-bearing invariant):** no part build ever imports an
assembly-level module. `assembly.py`/`motion.py` ARE loaded transitively (PyWin32Adapter
mixes them in) but a part only ever CALLS sketch/feature/export methods; those modules
import `base`/`com_variant`, never the reverse, so an assembly-method body change can't
propagate into the calls a part makes. `tools/agents/ui/server` aren't imported by any
build code at all.

**Enforced loud:** `check:partiso` (`cad/scripts/test_part_isolation.py`, offline gate,
in `_CHECK_NAMES`) derives its forbidden-import set straight from
`dodo._PART_DIGEST_EXCLUDE_*` and fails if any part script (or a repo-local helper it
transitively imports, via `module_deps_of`) DIRECTLY imports an excluded module or the
main-repo `_assembly` helper. So the exclusion can't silently go stale. Verified green:
95 part scripts, 0 offenders.

**Caveat:** this session's submodule branch also changed `base.py`/`com_variant.py`/
`sketch.py` (part-RELEVANT), so parts still rebuilt once here; the fix prevents FUTURE
assembly-only bumps from doing so. Full design in AGENTS.md "Two-tier submodule digest".
Related: [[incremental-builds-validation]], [[submodule-pointer-drift]],
[[belt-chain-feature-com-binding]].
