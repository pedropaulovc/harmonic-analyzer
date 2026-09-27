"""Guard: assembly builds select mate entities by name, never by a point (no SolidWorks).

``IModelDocExtension::SelectByID2`` with an empty name selects a FACE by casting
the point through the graphics view, so the entity it returns depends on the
seat's window size, zoom and orientation.  #916's collar seat picked 0.33 mm
outside the shaft collar: one farm seat selected the post's boss face, another
the collar's O.D., and the drive train failed there.  Every assembly mate now
names its entities (a named plane or axis in the part), and this guard keeps a
point pick from coming back.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent
ASSEMBLY_BUILDS = sorted(SCRIPTS.glob("build_*_assembly.py")) + [
    SCRIPTS / "_assembly_postbuild.py"
]


def _point_picks(tree: ast.AST) -> list[str]:
    """Calls that select by point: ``bore_axis_ref(...)``, a ``MateEntityRef``
    given ``point=``, and ``SelectByID2`` with an empty name."""
    found = []
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        name = func.id if isinstance(func, ast.Name) else getattr(func, "attr", "")
        if name == "bore_axis_ref":
            found.append(f"line {node.lineno}: bore_axis_ref")
        elif name == "MateEntityRef" and any(k.arg == "point" for k in node.keywords):
            found.append(f"line {node.lineno}: MateEntityRef(point=...)")
        elif (
            name == "SelectByID2"
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and node.args[0].value == ""
        ):
            found.append(f"line {node.lineno}: SelectByID2('', ...)")
    return found


def test_the_guard_sees_every_point_pick_form() -> None:
    tree = ast.parse(
        "bore_axis_ref([1.0, 2.0, 3.0])\n"
        "MateEntityRef(entity_type='FACE', point=[0, 0, 0])\n"
        "model.Extension.SelectByID2('', 'FACE', 0.1, 0.2, 0.3, False, 0, None, 0)\n"
        "named_ref('CollarFace@shaft-1', 'PLANE')\n"
        "model.Extension.SelectByID2('Top Plane', 'PLANE', 0, 0, 0, False, 0, None, 0)\n"
    )
    assert [p.split(": ")[1] for p in _point_picks(tree)] == [
        "bore_axis_ref",
        "MateEntityRef(point=...)",
        "SelectByID2('', ...)",
    ]


@pytest.mark.parametrize("script", ASSEMBLY_BUILDS, ids=lambda p: p.name)
def test_assembly_build_selects_by_name(script: Path) -> None:
    tree = ast.parse(script.read_text(encoding="utf-8"), filename=str(script))
    assert _point_picks(tree) == []
