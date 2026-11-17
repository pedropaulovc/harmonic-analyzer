r"""Guard: a part recipe never reaches assembly-level code (no SolidWorks).

A part's cache key is its build script plus every repo-local module it
transitively imports (``module_deps_of``). If a part reached the assembly
helpers or the MHA-DT-00 step registry, every edit to them would rebuild the
~100 parts and the assemblies above them, so the ``check:partiso`` gate fails
loud on any such import, directly or through a helper.

    python cad/scripts/test_part_isolation.py     # or: pytest cad/scripts/test_part_isolation.py
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "cad" / "scripts"))

from _buildgraph import module_deps_of, part_scripts  # noqa: E402


def test_no_part_imports_main_assembly_helper():
    """No part reaches core or specialized assembly helpers transitively.

    Name the extracted providers even if they later stop importing core: their
    assembly-only policy must not depend on an incidental import back-edge.
    """
    assembly_helpers = {
        "_assembly", "_motion", "_assembly_patterns", "_assembly_couplings"
    }
    offenders = {
        script.name: sorted(Path(p).stem for p in module_deps_of(script)
                            if Path(p).stem in assembly_helpers)
        for script in part_scripts()
    }
    offenders = {k: v for k, v in offenders.items() if v}
    assert not offenders, (
        f"part scripts transitively import an assembly-level helper: {offenders}")


def test_no_part_reads_the_assembly_step_registry():
    """No part's recipe depends on MHA-DT-00's step numbering.

    A step pointer is sheet text, so renumbering the sequence re-keys the
    drawings that print it, never a part (Main's TbPB ruling 2, 2026-09-27:
    a part spec that imported ``drive_train_steps`` for its note re-keyed the
    part and the assemblies above it on every sequence edit).
    """
    offenders = sorted(
        script.name
        for script in part_scripts()
        if any(Path(p).stem == "dt_drive_train_steps" for p in module_deps_of(script))
    )
    assert not offenders, (
        "part scripts transitively import the MHA-DT-00 step registry "
        f"(drive_train_steps): {offenders}. Print the pointer from the drawing.")


def _main() -> int:
    test_no_part_imports_main_assembly_helper()
    test_no_part_reads_the_assembly_step_registry()
    print(f"OK  part-isolation: {len(part_scripts())} part scripts reach no assembly helper")
    return 0


if __name__ == "__main__":
    raise SystemExit(_main())
