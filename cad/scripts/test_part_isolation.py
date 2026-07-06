r"""Guard: a PART build must never import assembly-level code (no SolidWorks).

This is the safety net for the two-tier submodule digest in ``dodo.py``. The PART
recipe digest (``_submodule_part_digest``) deliberately DROPS the assembly/motion COM
modules on the premise that a part only ever CALLS sketch/feature/export methods --
never an assembly/motion method -- so their content cannot alter a part's geometry and
must not rebuild the ~100 parts. That premise is only safe if it stays true, so this
test enforces it: if any part script (or a repo-local helper it transitively imports)
ever imports one of the excluded modules -- or the main-repo ``_assembly`` helper --
the ``check:partiso`` gate fails loud, forcing either the import to be removed or the
exclusion to be revisited.

The forbidden set is DERIVED from ``dodo._PART_DIGEST_EXCLUDE_FILES`` (the exact files
the part digest excludes), so the guard and the digest can never silently drift.

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
from _buildgraph import module_deps_of, part_scripts  # noqa: E402

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


def _hits(modules: set[str]) -> set[str]:
    """The forbidden imports present in ``modules`` (exact excluded-file match)."""
    files = _forbidden_file_modules()
    return {m for m in modules if m in files}


def _scan_set(part_script: Path) -> list[Path]:
    """The part script + every repo-local helper it transitively imports -- the only
    files whose import statements can introduce a part-side dependency."""
    return [part_script, *(Path(p) for p in module_deps_of(part_script))]


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
    offenders: dict[str, set[str]] = {}
    for script in part_scripts():
        for f in _scan_set(script):
            hit = _hits(_imported_modules(f))
            if hit:
                offenders.setdefault(f.name, set()).update(hit)
    assert not offenders, (
        "part-build code imports assembly-level submodule modules the PART digest "
        f"excludes (dodo._PART_DIGEST_EXCLUDE_*): {offenders}. Either drop the import "
        "or move the module out of the exclusion.")


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
    n = len(part_scripts())
    print(f"OK  part-isolation: {n} part scripts import no assembly-level module")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
