r"""Pure build-graph enumeration shared by the doit ``dodo.py`` and the legacy
``build_all.py`` shim.

This module holds only filesystem/string logic -- no SolidWorks, no COM -- so the
part/assembly enumeration and the part->assembly dependency scan are unit-testable
in plain CI. ``references_of`` is the inverse of ``dependents_of``: the former
yields a build script's prerequisites (the DAG edges doit consumes as
``file_dep``), the latter yields a part's downstream assemblies (what the legacy
``--rebuild`` deleted).

Lifted verbatim from the original ``build_all.py`` (constants + ``part_scripts`` /
``artefact_for`` / ``script_for`` / ``dependents_of``).
"""

from __future__ import annotations

import ast
import functools
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
CAD_OUT = SCRIPTS_DIR.parent / "out"

# Sub-assemblies in build order; the top-level harmonic-analyzer references the
# four subs, so it is last. doit derives ordering from file_dep, but this tuple
# still enumerates the assembly tasks.
ASSEMBLY_ORDER = ("frame", "drive_train", "channel", "output", "harmonic_analyzer")

# Throwaway motion/diagnostic deliverables that match build_*.py but produce no
# .SLDPRT part -- they consume/probe the saved assemblies (Basic Motion sweeps,
# mobility probes), they don't build the machine. Excluded from the part queue.
NON_PART_SCRIPTS = frozenset(
    {
        "build_motion_study.py",
        "build_motion_study_springs.py",
        "build_motion_setup_drives.py",
        "build_fourbar_test.py",
        "build_mobility_probe.py",
    }
)

# Post-assembly hooks: scripts that mutate an already-built assembly IN PLACE (no
# new artefact), run after their base assembly rather than in the part queue.
# Keyed by assembly stem; run in listed order.
#
# Empty: the engagement-CONFIGURATION mutators (cone_disengaged / operating) were
# removed -- every assembly now carries only its Default configuration. Re-add a
# stem -> (script, ...) entry here if a future in-place post-build step is needed.
POST_ASSEMBLY: dict[str, tuple[str, ...]] = {}
_POST_SCRIPT_NAMES = frozenset(s for v in POST_ASSEMBLY.values() for s in v)


def part_scripts() -> list[Path]:
    """Every build_*.py except the assemblies, config hooks, motion/diagnostic
    scripts and the orchestrator."""
    out = []
    for path in sorted(SCRIPTS_DIR.glob("build_*.py")):
        if (path.name in NON_PART_SCRIPTS or path.name in _POST_SCRIPT_NAMES
                or path.name.endswith("_assembly.py")):
            continue
        out.append(path)
    return out


def part_stems() -> list[str]:
    """Part stems (``build_<stem>.py`` -> ``<stem>``), undashed."""
    return [p.stem.removeprefix("build_") for p in part_scripts()]


def artefact_for(script: Path) -> Path:
    """The .SLDPRT/.SLDASM a build script produces (dashed artefact name)."""
    stem = script.stem.removeprefix("build_")
    if stem.endswith("_assembly"):
        name = stem.removesuffix("_assembly").replace("_", "-")
        return CAD_OUT / "sldasm" / f"{name}.SLDASM"
    return CAD_OUT / "sldprt" / f"{stem.replace('_', '-')}.SLDPRT"


def script_for(stem: str) -> Path:
    """The build script for a part/assembly stem (assemblies get _assembly)."""
    if stem in ASSEMBLY_ORDER:
        return SCRIPTS_DIR / f"build_{stem}_assembly.py"
    return SCRIPTS_DIR / f"build_{stem}.py"


def _references(asm_stem: str, candidate_stem: str) -> bool:
    """True when ``candidate_stem``'s dashed name appears as a ``"..."`` literal
    in ``asm_stem``'s build script.

    The single primitive both ``references_of`` and ``dependents_of`` share, so
    they are exact inverses. Prefix scan on ``"<dashed>`` (no closing quote), so
    a shared prefix over-matches (e.g. ``"cone-gear`` also hits
    ``"cone-gear-shaft"``); an extra edge costs at worst one extra refresh, never
    a stale artefact -- identical to the legacy behaviour.
    """
    dashed = candidate_stem.replace("_", "-")
    src = script_for(asm_stem).read_text(encoding="utf-8")
    return f'"{dashed}' in src


def references_of(asm_stem: str) -> list[str]:
    """Part + sub-assembly stems this assembly's build script references.

    These are the prerequisite artefacts (the DAG edges): ``output`` references
    its leaf parts; ``harmonic_analyzer`` references the four sub-assemblies
    (build_harmonic_analyzer_assembly.SUBASSEMBLIES). doit turns each into a
    ``file_dep`` on the referenced ``.SLDPRT``/sub-``.SLDASM`` target, so order
    and the refresh/full decision fall out of the graph.
    """
    candidates = part_stems() + [a for a in ASSEMBLY_ORDER if a != asm_stem]
    return [stem for stem in candidates if _references(asm_stem, stem)]


@functools.lru_cache(maxsize=1)
def _local_helper_modules() -> dict[str, Path]:
    """The ``_*.py`` helper modules a build script may import, by module name.

    Excludes ``_buildgraph.py`` (the build-GRAPH helper, not a geometry input)
    and ``__init__``-style/private tooling that isn't an importable helper.
    """
    out: dict[str, Path] = {}
    for p in sorted(SCRIPTS_DIR.glob("_*.py")):
        if p.name in {"_buildgraph.py", "_extract.py", "_rewrite_imports.py"}:
            continue
        out[p.stem] = p
    return out


@functools.lru_cache(maxsize=None)
def _direct_helper_imports(path: Path) -> frozenset[str]:
    """Local helper module names imported ANYWHERE in ``path`` (top-level or
    lazily inside a function, e.g. ``_common``'s ``import _config``). An absolute
    or dotted import keeps only its leading segment so ``import _common`` and
    ``from _common import x`` both resolve to ``_common``."""
    helpers = _local_helper_modules()
    found: set[str] = set()
    tree = ast.parse(path.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                found.add(a.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.level == 0 and node.module:
                found.add(node.module.split(".")[0])
    return frozenset(found & helpers.keys())


def module_deps_of(script: Path) -> list[str]:
    """Resolved paths of every local ``_*.py`` helper ``script`` transitively
    imports -- the EXACT geometry-input edges for doit's ``file_dep``.

    This replaces the old blanket "every ``_*.py`` is a dep of every build"
    rule: a leaf part that imports only ``_common`` no longer rebuilds when an
    assembly-only helper (``_assembly``) or an unrelated one (``_gear``) changes.
    Because it follows REAL Python imports transitively (``_chain_link -> _chain
    -> _common``; ``_common -> _config``), it can never under-invalidate so long
    as a script imports what it uses -- which Python enforces at run time.
    """
    helpers = _local_helper_modules()
    result: set[str] = set()
    frontier = set(_direct_helper_imports(script.resolve()))
    while frontier:
        mod = frontier.pop()
        if mod in result:
            continue
        result.add(mod)
        frontier |= set(_direct_helper_imports(helpers[mod].resolve())) - result
    return sorted(str(helpers[m].resolve()) for m in result)


def dependents_of(stem: str) -> list[str]:
    """Assembly stems whose build script references this part/assembly (legacy).

    The inverse of ``references_of``, preserved verbatim from ``build_all.py`` for
    parity (and the ``--rebuild`` shim). Includes the transitive top-add: any part
    pulled into a sub-assembly also flows up to harmonic_analyzer, so the top is
    appended whenever a direct dependent exists. The doit graph does not need this
    transitive edge -- it propagates through ``output.SLDASM -> harmonic-analyzer
    .SLDASM`` -- so ``references_of`` is the DIRECT inverse only.
    """
    deps = [asm for asm in ASSEMBLY_ORDER if asm != stem and _references(asm, stem)]
    if deps and "harmonic_analyzer" not in deps:
        deps.append("harmonic_analyzer")
    return deps
