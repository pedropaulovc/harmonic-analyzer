"""Positive and negative controls for the as-machined report through headless
FreeCAD: a 40 x 20 x 10 block with a 6 mm through hole, faced from a blank
12 thick (10.8-12.5 band) and drilled, its programs clean and with seeded
faults. The faults are the column clamp trial's (2026-11-25), restated on a
part small enough to cut in seconds: a face pass stopped short, a hole moved,
a face level too deep, a rapid through the part, and a drill run deeper into
the air below a through hole (which must find nothing).

Not in any ``check:*`` gate (see ``dodo._UNGATED``): it runs the local
FreeCAD install, which no build dependency tracks. Run it by hand after
changing ``_as_machined.py`` or ``_freecad_as_machined.py``, or after
upgrading FreeCAD:
``uv run --frozen python -m pytest -q cad/scripts/test_as_machined_freecad.py``.
It skips only when no FreeCAD 1.1+ is found.
"""

from __future__ import annotations

import os
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest

import _as_machined as am
import cam_nc

_PART = """
import os
import Part
import FreeCAD
block = Part.makeBox(40, 20, 10)
hole = Part.makeCylinder(3, 20, FreeCAD.Vector(30, 10, -5))
block.cut(hole).exportStep(os.environ["MINI_STEP"])
"""
_FACE = """G90 G17 G21
M6 T1
G0 X-8 Y2 Z15
G1 Z11 F300
G1 X48
G1 Y10
G1 X-8
G1 Y18
G1 X48
G1 Z10
G1 X-8
G1 Y10
G1 X48
G1 Y2
G1 X-8
G0 Z15
"""
_HOLE = """G90 G17 G21
M6 T2
G0 X30 Y10 Z15
G0 Z11
G1 Z-3 F50
G0 Z15
"""
IDENTITY = {"origin": [0.0, 0.0, 0.0], "axes": [[1, 0, 0], [0, 1, 0], [0, 0, 1]]}


@pytest.fixture(scope="module")
def freecadcmd():
    try:
        return cam_nc.resolve_freecadcmd()
    except cam_nc.FreeCadError as exc:
        pytest.skip(f"no usable FreeCAD: {exc}")


@pytest.fixture(scope="module")
def step(freecadcmd, tmp_path_factory):
    work = tmp_path_factory.mktemp("mini")
    script, path = work / "part.py", work / "mini.step"
    script.write_text(_PART, encoding="utf-8")
    subprocess.run([str(freecadcmd), str(script)], env={**os.environ, "MINI_STEP": str(path)},
                   cwd=work, capture_output=True, timeout=300, check=False)
    assert path.is_file(), "FreeCAD wrote no mini STEP"
    return path


def _report(freecadcmd, step, tmp_path, face=_FACE, hole=_HOLE):
    (tmp_path / "P1_face.nc").write_text(face, encoding="utf-8")
    (tmp_path / "P2_hole.nc").write_text(hole, encoding="utf-8")
    recipe = SimpleNamespace(
        PROGRAMS=(("P1_face", ("face",)), ("P2_hole", ("hole",))),
        AS_MACHINED_MODE=am.MODE_REPORT,
        as_machined=lambda ctx, inputs: {"parts": {"": {"blank": {
            "frame": "top", "box": [[0, 40], [0, 20], [0, 12]],
            "length": {"axis": "z", "keep": "min", "mm": {"nominal": 12.0, "min": 10.8, "max": 12.5}},
        }}}},
    )
    ctx = {
        "frames": {"top": IDENTITY},
        "jobs": [
            {"tool": "em", "frame": "top", "shape": "endmill", "dia": 12.7, "ops": [["face", "face", []]]},
            {"tool": "drill", "frame": "top", "shape": "drill", "dia": 6.0, "tip_angle": 118.0, "ops": [["hole", "hole", []]]},
        ],
        "numbers": {"em": 1, "drill": 2},
        "manual": {},
    }
    inputs = SimpleNamespace(features={}, plan={"milling_material": "aluminum_6061"}, shop={}, steps={"": str(step)})
    out = am.report("mini", recipe, ctx, inputs, tmp_path, lambda: freecadcmd)
    assert out["covered"] and "error" not in out, out.get("error")
    return out, out["parts"][""]["variants"]


def test_clean_programs_cut_the_cad_part(freecadcmd, step, tmp_path):
    out, variants = _report(freecadcmd, step, tmp_path)
    nominal = variants["nominal"]
    assert nominal["volume_mm3"]["cad"] == pytest.approx(8000 - 90 * 3.14159265, rel=1e-6)
    assert abs(nominal["volume_mm3"]["difference"]) < 0.01
    assert nominal["cog_offset_mm"] < 1e-3
    assert nominal["over_noise"] == [] and nominal["rapid_cuts"] == []
    assert am.failures(out) == [] and out["picture"] is None
    assert nominal["mass_g"]["cad"] == pytest.approx(nominal["volume_mm3"]["cad"] * 2.70 / 1000)
    removed = {p["program"]: p["removed_mm3"] for p in nominal["programs"]}
    assert removed["P1_face"] == pytest.approx(40 * 20 * 2, rel=1e-6)
    assert removed["P2_hole"] == pytest.approx(10 * 9 * 3.14159265, rel=1e-4)
    # The thin blank: the first face level runs above it, three passes of air.
    assert nominal["air_passes"] == []
    thin = [(p["program"], p["move"], p["above_blank"]) for p in variants["min"]["air_passes"]]
    assert thin == [("P1_face", 2, True), ("P1_face", 4, True), ("P1_face", 6, True)]
    assert (tmp_path / am.REPORT_NAME).is_file()


@pytest.mark.parametrize(
    ("fault", "face", "hole", "kinds"),
    [
        ("F1 face pass stopped short", _FACE.replace("G1 Y2\nG1 X-8", "G1 Y2\nG1 X20"), _HOLE, {"left"}),
        ("F2 hole moved 0.5 mm", _FACE, _HOLE.replace("X30 Y10", "X30.5 Y10"), {"left", "gouge"}),
        ("F3 face level 0.3 mm deep", _FACE.replace("G1 Z10", "G1 Z9.7"), _HOLE, {"gouge"}),
        # The plug touches the CAD along every edge: its 3 mm depth shows only
        # inside its end faces (the mesh of a cylinder has no inner vertices).
        ("F7 hole not drilled", _FACE, _HOLE.replace("G1 Z-3 F50\n", ""), {"left"}),
    ],
)
def test_seeded_shape_faults_show_over_the_noise_line(freecadcmd, step, tmp_path, fault, face, hole, kinds):
    out, variants = _report(freecadcmd, step, tmp_path, face, hole)
    found = {r["kind"] for r in variants["nominal"]["over_noise"]}
    assert found == kinds, fault
    assert am.failures(out)
    assert out["picture"] == am.PICTURE_NAME and (tmp_path / am.PICTURE_NAME).is_file()


def test_a_rapid_through_the_part_is_a_cutting_rapid(freecadcmd, step, tmp_path):
    hole = _HOLE.replace("G0 X30 Y10 Z15\nG0 Z11", "G0 X5 Y10 Z15\nG0 Z5\nG0 X30\nG0 Z11")
    out, variants = _report(freecadcmd, step, tmp_path, hole=hole)
    # The rapid down into the top at X5, then the rapid along through it to X30.
    cuts = variants["nominal"]["rapid_cuts"]
    assert [(c["program"], c["to"]) for c in cuts] == [("P2_hole", [5.0, 10.0, 5.0]), ("P2_hole", [30.0, 10.0, 5.0])]
    assert all(c["removed_mm3"] > 1.0 for c in cuts)
    assert any("rapid P2_hole" in line for line in am.failures(out))


def test_a_drill_deeper_into_the_air_below_a_through_hole_finds_nothing(freecadcmd, step, tmp_path):
    out, variants = _report(freecadcmd, step, tmp_path, hole=_HOLE.replace("Z-3", "Z-4"))
    assert variants["nominal"]["over_noise"] == [] and variants["nominal"]["rapid_cuts"] == []
    assert am.failures(out) == []


def test_an_undrilled_hole_under_a_strip_left_shows_its_depth(freecadcmd, step, tmp_path):
    """The face 0.1 mm high and the hole not drilled: one region, the strip
    and the plug under it; its thickness is the plug's (about its 3 mm
    radius), not the strip's 0.1 mm."""
    face = _FACE.replace("G1 Z10", "G1 Z10.1")
    out, variants = _report(freecadcmd, step, tmp_path, face=face, hole=_HOLE.replace("G1 Z-3 F50\n", ""))
    (region,) = variants["nominal"]["over_noise"]
    assert region["kind"] == "left" and region["thickness_mm"] > 2.5


def test_programs_past_the_move_cap_are_cut_in_one_boolean(freecadcmd, step, tmp_path, monkeypatch):
    """Every program cut in one boolean: the same part, the same material
    each program removed, the same thin-blank air passes, and the same rapid
    through the part (it shares material with the part after the program)."""
    monkeypatch.setattr(am, "MOVE_CAP", 0)
    (tmp_path / "clean").mkdir()
    _out, variants = _report(freecadcmd, step, tmp_path / "clean")
    nominal = variants["nominal"]
    assert abs(nominal["volume_mm3"]["difference"]) < 0.01 and nominal["over_noise"] == []
    assert all(p["accounting"].startswith("batched") for p in nominal["programs"])
    assert {p["program"]: round(p["removed_mm3"]) for p in nominal["programs"]} == {"P1_face": 1600, "P2_hole": 283}
    assert [(p["move"], p["above_blank"]) for p in variants["min"]["air_passes"]] == [(2, True), (4, True), (6, True)]
    (tmp_path / "rapid").mkdir()
    hole = _HOLE.replace("G0 X30 Y10 Z15\nG0 Z11", "G0 X5 Y10 Z15\nG0 Z5\nG0 X30\nG0 Z11")
    _out, variants = _report(freecadcmd, step, tmp_path / "rapid", hole=hole)
    cuts = variants["nominal"]["rapid_cuts"]
    assert [(c["program"], c["to"]) for c in cuts] == [("P2_hole", [5.0, 10.0, 5.0]), ("P2_hole", [30.0, 10.0, 5.0])]
