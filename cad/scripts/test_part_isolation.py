r"""Guard: a build must never import code its recipe-digest tier excludes (no SolidWorks).

This is the safety net for the THREE-tier submodule digest in ``dodo.py``:

  * The PART recipe digest (``_submodule_part_digest``) DROPS {assembly.py, motion.py,
    drawing.py} on the premise that a part only ever CALLS sketch/feature/export
    methods -- never an assembly/motion/drawing method -- so their content cannot alter
    a part's geometry and must not rebuild the ~100 parts.
  * The ASSEMBLY recipe digest (``_submodule_assembly_digest``) DROPS drawing.py on the
    premise that no assembly build imports the ``IDrawingDoc`` helpers -- only a
    ``draw_*`` drawing script does -- so a drawing.py edit must not rebuild the ~8
    assemblies.

Those premises are only safe if they stay true, so this test enforces both: if any part
script imports an assembly/motion/drawing module (or the main-repo ``_assembly``
helper), or any assembly script imports the drawing module -- directly or through a
repo-local helper it transitively imports -- the ``check:partiso`` gate fails loud,
forcing either the import to be removed or the exclusion to be revisited.

The forbidden sets are DERIVED from ``dodo._PART_DIGEST_EXCLUDE_FILES`` /
``dodo._ASSEMBLY_DIGEST_EXCLUDE_FILES`` (the exact files each digest excludes), so the
guard and the digests can never silently drift.

Note on the transitive mixin load: importing ``PyWin32Adapter`` DOES pull
``adapters.solidworks.assembly`` / ``.motion`` in as mixin bases -- that is expected
and benign (a part only ever CALLS sketch/feature/export methods; assembly/motion
import base/com_variant, never the reverse, so their bodies can't leak into a part's
geometry). drawing.py is NOT even mixed in (standalone module-level functions), so it
is not loaded by any adapter at all. This guard checks for a DIRECT import in build
code, which is the signal that a build started actually depending on that behaviour.

Scope note (codex #191): the MCP-server tree (``tools/``/``agents/``/``ui/``/
``server*``) is NOT excluded from any digest; excluding it would rest on "not-REACHED
through the submodule's own import graph", which this repo-local scan cannot verify.
assembly/motion/drawing exclusions rest on "not-IMPORTED by that tier's build scripts",
which IS checkable here.

    python cad/scripts/test_part_isolation.py     # or: pytest cad/scripts/test_part_isolation.py
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "cad" / "scripts"
sys.path.insert(0, str(REPO_ROOT / "cad" / "scripts"))
sys.path.insert(0, str(REPO_ROOT))

import _telemetry  # noqa: E402,F401  (import for import-time consistency w/ siblings)
import dodo  # noqa: E402  (source of truth for the excluded submodule files)
from _buildgraph import ASSEMBLY_ORDER, module_deps_of, part_scripts  # noqa: E402

# dodo's exclude tags are PACKAGE-relative (relative to ``solidworks_mcp/``), so the
# full import name is just the package prefix + the dotted tag.
_PKG = "solidworks_mcp"


def _tag_to_module(tag: str) -> str:
    """``adapters/solidworks/assembly.py`` -> ``solidworks_mcp.adapters.solidworks.
    assembly``; a dir tag (``tools/``) -> ``solidworks_mcp.tools`` (the package
    prefix a forbidden import starts with)."""
    rel = tag.rstrip("/").removesuffix(".py")
    return f"{_PKG}.{rel.replace('/', '.')}"


def _modules_of(tags: frozenset[str]) -> frozenset[str]:
    return frozenset(_tag_to_module(t) for t in tags)


def _forbidden_file_modules() -> frozenset[str]:
    return _modules_of(dodo._PART_DIGEST_EXCLUDE_FILES)


def _assembly_scripts() -> list[Path]:
    """Every assembly build script (``build_<stem>_assembly.py``), matching the set
    dodo.task_check's ``partiso`` file_dep folds."""
    return [SCRIPTS_DIR / f"build_{s}_assembly.py" for s in ASSEMBLY_ORDER]


def _imported_modules(path: Path) -> set[str]:
    """Every fully-qualified module name imported ANYWHERE in ``path`` (top-level or
    lazily inside a function): ``import a.b.c`` and ``from a.b import c`` (absolute
    only -- relative imports can't reach the submodule)."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            names.add(node.module)
            names.update(f"{node.module}.{a.name}" for a in node.names)
    return names


def _hits(modules: set[str], forbidden: frozenset[str]) -> set[str]:
    """The forbidden imports present in ``modules`` (exact excluded-file match)."""
    return {m for m in modules if m in forbidden}


def _scan_set(script: Path) -> list[Path]:
    """The build script + every repo-local helper it transitively imports -- the only
    files whose import statements can introduce a dependency for that build."""
    return [script, *(Path(p) for p in module_deps_of(script))]


def _offenders(scripts, forbidden: frozenset[str]) -> dict[str, set[str]]:
    """Map each build script (or transitively-imported helper) to the forbidden
    submodule modules it directly imports."""
    out: dict[str, set[str]] = {}
    for script in scripts:
        for f in _scan_set(script):
            hit = _hits(_imported_modules(f), forbidden)
            if hit:
                out.setdefault(f.name, set()).update(hit)
    return out


def test_forbidden_set_is_nonempty():
    """Sanity: both derivations actually produced module names (else a guard is a
    no-op and every build would 'pass' vacuously)."""
    part_forbidden = _forbidden_file_modules()
    assert part_forbidden, "no excluded-file modules derived from dodo (part)"
    assert "solidworks_mcp.adapters.solidworks.assembly" in part_forbidden
    assert "solidworks_mcp.adapters.solidworks.motion" in part_forbidden
    assert "solidworks_mcp.adapters.solidworks.drawing" in part_forbidden

    asm_forbidden = _modules_of(dodo._ASSEMBLY_DIGEST_EXCLUDE_FILES)
    assert asm_forbidden == frozenset({"solidworks_mcp.adapters.solidworks.drawing"}), (
        f"assembly digest should exclude only drawing.py, got {asm_forbidden}")


def test_no_part_imports_assembly_level_submodule():
    """No part-build file directly imports an excluded (assembly/motion/drawing)
    submodule module -- the invariant that makes the part digest's exclusion safe."""
    offenders = _offenders(part_scripts(), _forbidden_file_modules())
    assert not offenders, (
        "part-build code imports submodule modules the PART digest excludes "
        f"(dodo._PART_DIGEST_EXCLUDE_FILES): {offenders}. Either drop the import "
        "or move the module out of the exclusion.")


def test_no_assembly_imports_drawing_submodule():
    """No assembly-build file directly imports drawing.py -- the invariant that makes
    the ASSEMBLY digest's drawing.py exclusion safe. drawing.py is not mixed into the
    adapter, so an assembly reaching it would be a real new dependency, not a benign
    transitive mixin load."""
    offenders = _offenders(_assembly_scripts(),
                           _modules_of(dodo._ASSEMBLY_DIGEST_EXCLUDE_FILES))
    assert not offenders, (
        "assembly-build code imports the drawing submodule module the ASSEMBLY digest "
        f"excludes (dodo._ASSEMBLY_DIGEST_EXCLUDE_FILES): {offenders}. Either drop the "
        "import or move drawing.py out of the exclusion.")


def test_no_part_imports_main_assembly_helper():
    """No part pulls in the main-repo ``_assembly`` helper (the assembly-level mate/
    gate glue). If one did, editing ``_assembly.py`` would rebuild parts -- and the
    module_deps_of closure would carry it, contradicting the part/assembly split."""
    offenders = {
        script.name: sorted(Path(p).stem for p in module_deps_of(script)
                            if Path(p).stem in {"_assembly", "_motion"})
        for script in part_scripts()
    }
    offenders = {k: v for k, v in offenders.items() if v}
    assert not offenders, (
        f"part scripts transitively import an assembly-level helper: {offenders}")


def _main() -> int:
    test_forbidden_set_is_nonempty()
    test_no_part_imports_assembly_level_submodule()
    test_no_assembly_imports_drawing_submodule()
    test_no_part_imports_main_assembly_helper()
    n, m = len(part_scripts()), len(_assembly_scripts())
    print(f"OK  part-isolation: {n} part scripts import no assembly/motion/drawing "
          f"module; {m} assembly scripts import no drawing module")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
