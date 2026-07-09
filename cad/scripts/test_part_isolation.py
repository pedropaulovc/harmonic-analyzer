r"""Guard: a build must never import a submodule module its digest tier excludes.

This is the safety net for the three-tier submodule digest in ``dodo.py``:
  * The PART recipe digest (``_submodule_part_digest``) DROPS the assembly/motion COM
    modules AND the drawing module, on the premise that a part only ever CALLS
    sketch/feature/export methods -- never an assembly/motion/drawing method.
  * The ASSEMBLY recipe digest (``_submodule_assembly_digest``) drops only the drawing
    module -- assemblies DO call assembly/motion, but never drawing.
Those premises are only safe if they stay true, so this test enforces them: if any
part script imports an excluded (assembly/motion/drawing/MCP-server) module -- or the
main-repo ``_assembly`` helper -- OR any assembly script imports the drawing module,
the ``check:partiso`` gate fails loud, forcing either the import to be removed or the
exclusion to be revisited.

The forbidden sets are DERIVED from ``dodo._PART_DIGEST_EXCLUDE_FILES`` and
``dodo._ASSEMBLY_DIGEST_EXCLUDE_FILES`` (the exact files each digest excludes), so the
guard and the digests can never silently drift.

Note on the transitive mixin load: importing ``PyWin32Adapter`` DOES pull
``adapters.solidworks.assembly`` / ``.motion`` in as mixin bases -- that is expected
and benign (a part only ever CALLS sketch/feature/export methods; assembly/motion
import base/com_variant, never the reverse, so their bodies can't leak into a part's
geometry). This guard checks for a DIRECT import in part-build code, which is the
signal that a part started actually depending on assembly-level behaviour.

Scope note (codex #191): ONLY assembly/motion are excluded -- their exclusion rests on
"not-CALLED", which is fully checkable from repo-local code here. The MCP-server tree
(``tools/``/``agents/``/``ui/``/``server*``) is NOT excluded; excluding it would rest
on "not-REACHED through the submodule's own import graph", which this repo-local scan
cannot verify, so those modules stay in the part digest.

    python cad/scripts/test_part_isolation.py     # or: pytest cad/scripts/test_part_isolation.py
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "cad" / "scripts"))
sys.path.insert(0, str(REPO_ROOT))

import _telemetry  # noqa: E402,F401  (import for import-time consistency w/ siblings)
import dodo  # noqa: E402  (source of truth for the excluded submodule files)
from _buildgraph import module_deps_of, part_scripts, script_for  # noqa: E402

# dodo's exclude tags are PACKAGE-relative (relative to ``solidworks_mcp/``), so the
# full import name is just the package prefix + the dotted tag.
_PKG = "solidworks_mcp"


def _tag_to_module(tag: str) -> str:
    """``adapters/solidworks/assembly.py`` -> ``solidworks_mcp.adapters.solidworks.
    assembly``; a dir tag (``tools/``) -> ``solidworks_mcp.tools`` (the package
    prefix a forbidden import starts with)."""
    rel = tag.rstrip("/").removesuffix(".py")
    return f"{_PKG}.{rel.replace('/', '.')}"


def _forbidden_file_modules() -> frozenset[str]:
    return frozenset(_tag_to_module(t) for t in dodo._PART_DIGEST_EXCLUDE_FILES)


def _forbidden_assembly_modules() -> frozenset[str]:
    return frozenset(_tag_to_module(t) for t in dodo._ASSEMBLY_DIGEST_EXCLUDE_FILES)


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
    files whose import statements can introduce a build-side dependency (works for a
    part OR an assembly script)."""
    return [script, *(Path(p) for p in module_deps_of(script))]


def _assembly_scripts() -> list[Path]:
    """Every assembly build script, resolved exactly as dodo's assembly recipe does
    (``script_for`` over ``ASSEMBLY_ORDER``)."""
    return [script_for(stem) for stem in dodo.ASSEMBLY_ORDER]


def _submodule_py_files() -> list[Path]:
    """Every ``.py`` under the vendored submodule's ``solidworks_mcp`` package."""
    root = dodo.SUBMODULE_SRC
    return sorted(root.rglob("*.py")) if root.is_dir() else []


def _package_of(path: Path) -> str:
    """Dotted package CONTAINING a submodule file, e.g.
    ``adapters/solidworks/base.py`` -> ``solidworks_mcp.adapters.solidworks`` (and an
    ``__init__.py`` maps to its own package the same way)."""
    rel = path.resolve().relative_to(dodo.SUBMODULE_SRC.parent.resolve())
    return ".".join(rel.with_suffix("").parts[:-1])


def _resolved_imports(path: Path) -> set[str]:
    """Absolute module names imported by ``path``, RESOLVING relative imports against
    the file's package. Submodule code uses relative imports (``from .drawing import
    X``), which ``_imported_modules`` (absolute-only) would miss -- so this resolver is
    what makes the submodule-reachability guard sound."""
    tree = ast.parse(path.read_text(encoding="utf-8"))
    pkg = _package_of(path)
    names: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0:
                base = node.module or ""
            else:
                parts = pkg.split(".")
                kept = parts[: len(parts) - (node.level - 1)] if node.level - 1 <= len(parts) else []
                base = ".".join([*kept, node.module] if node.module else kept)
            if base:
                names.add(base)
                names.update(f"{base}.{a.name}" for a in node.names)
    return names


def test_forbidden_set_is_nonempty():
    """Sanity: the derivation actually produced module names (else the guard is a
    no-op and every part would 'pass' vacuously)."""
    forbidden = _forbidden_file_modules()
    assert forbidden, "no excluded-file modules derived from dodo"
    assert "solidworks_mcp.adapters.solidworks.assembly" in forbidden
    assert "solidworks_mcp.adapters.solidworks.motion" in forbidden


def test_no_part_imports_assembly_level_submodule():
    """No part-build file directly imports an excluded (assembly/motion/MCP-server)
    submodule module -- the invariant that makes the part digest's exclusion safe."""
    forbidden = _forbidden_file_modules()
    offenders: dict[str, set[str]] = {}
    for script in part_scripts():
        for f in _scan_set(script):
            hit = _hits(_imported_modules(f), forbidden)
            if hit:
                offenders.setdefault(f.name, set()).update(hit)
    assert not offenders, (
        "part-build code imports assembly-level submodule modules the PART digest "
        f"excludes (dodo._PART_DIGEST_EXCLUDE_*): {offenders}. Either drop the import "
        "or move the module out of the exclusion.")


def test_assembly_forbidden_set_is_nonempty():
    """Sanity for the ASSEMBLY tier: the derivation produced module names (else the
    assembly guard is a vacuous no-op)."""
    forbidden = _forbidden_assembly_modules()
    assert forbidden, "no excluded-file modules derived from dodo (assembly tier)"
    assert "solidworks_mcp.adapters.solidworks.drawing" in forbidden


def test_no_assembly_imports_drawing_submodule():
    """No assembly-build file (script + its repo-local closure, incl. ``_assembly`` /
    ``_motion``) imports the drawing submodule module the ASSEMBLY digest excludes --
    the invariant that makes the drawing tier's exclusion safe (a drawing-module bump
    must rebuild NEITHER parts NOR assemblies)."""
    forbidden = _forbidden_assembly_modules()
    offenders: dict[str, set[str]] = {}
    for script in _assembly_scripts():
        for f in _scan_set(script):
            hit = _hits(_imported_modules(f), forbidden)
            if hit:
                offenders.setdefault(f.name, set()).update(hit)
    assert not offenders, (
        "assembly-build code imports the drawing submodule module the ASSEMBLY digest "
        f"excludes (dodo._ASSEMBLY_DIGEST_EXCLUDE_FILES): {offenders}. Either drop the "
        "import or move the module out of the exclusion.")


def test_no_submodule_file_imports_drawing_module():
    """The drawing module is dropped from BOTH the part and assembly submodule digests
    on the basis that NOTHING inside the submodule imports it (only main-repo drawing
    build scripts do). This guard proves that basis from the submodule's OWN import
    graph -- which the repo-local part/assembly scan cannot see (codex #213): if an
    INCLUDED submodule file (e.g. ``base.py`` / ``pywin32_adapter.py``) imported the
    drawing module, a later drawing-ONLY edit would be invisible to those digests,
    leaving cached parts/assemblies stale even though runtime behaviour changed.
    Resolves relative imports (submodule code uses them), so it catches ``from .drawing
    import X`` as well as the absolute path."""
    drawing_mod = _tag_to_module("adapters/solidworks/drawing.py")
    assert drawing_mod == "solidworks_mcp.adapters.solidworks.drawing"
    drawing_file = (dodo.SUBMODULE_SRC / "adapters" / "solidworks" / "drawing.py").resolve()
    files = _submodule_py_files()
    assert files, "no submodule .py files found -- guard would pass vacuously"
    offenders: dict[str, str] = {}
    for f in files:
        if f.resolve() == drawing_file:
            continue  # the module itself
        if drawing_mod in _resolved_imports(f):
            offenders[str(f.relative_to(dodo.SUBMODULE_SRC))] = drawing_mod
    assert not offenders, (
        f"submodule file(s) import the drawing module {drawing_mod!r} that the part AND "
        f"assembly digests EXCLUDE: {offenders}. Drawing-only edits would then be invisible "
        "to those digests (stale cached parts/assemblies). Either stop importing it from "
        "included submodule code, or drop drawing.py from the digest exclude sets.")


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
    test_no_part_imports_main_assembly_helper()
    test_assembly_forbidden_set_is_nonempty()
    test_no_assembly_imports_drawing_submodule()
    n = len(part_scripts())
    a = len(_assembly_scripts())
    print(f"OK  part-isolation: {n} part scripts import no assembly-level module; "
          f"{a} assembly scripts import no drawing module")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
