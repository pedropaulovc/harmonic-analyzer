"""Positive control through headless FreeCAD: real G0 rapids, zigzag faces and
conventional edge passes from the CAM runtime and the ``grbl`` post.

Not in any ``check:*`` gate (see ``test_check_gate_enrollment.EXEMPT``): it
runs the local FreeCAD install, which no build dependency tracks, and the
build must not pay for a FreeCAD run. Run it by hand after changing
``cam_nc.py`` or ``_freecad_cam_runtime.py``, or after upgrading FreeCAD:
``uv run --frozen python -m pytest -q cad/scripts/test_cam_nc_freecad.py``.
It skips only when no FreeCAD 1.1+ is found.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import _gcode
import cam_nc

_MINI_RECIPE = '''
STEM = "mini"
PROGRAMS = (("P1_face", ("face",)), ("P2_edges", ("edges",)))


def build(ctx, rt):
    doc = rt.document()
    face_job = rt.job(doc, "face", [rt.box(doc, "face_model", (-25, 125), (0, 50), (0, 9))], ((0, 100), (0, 50), (0, 10)))
    tc = rt.tool_controller(doc, "3/4 in endmill", 2, "endmill", 19.05, 850, 172.7, 86.35, flutes=4)
    face = rt.face(face_job, tc, "face", rt.top_face(rt.model(face_job), 9), 10, 9, 15.24)
    edge_job = rt.job(doc, "edges", [rt.box(doc, "edge_model", (-10, 110), (0, 50), (-10, 0))], ((0, 100), (-3, 53), (-10, 0)))
    em = rt.tool_controller(doc, "1/2 in endmill", 1, "endmill", 12.7, 2250, 400, 63.5, flutes=2)
    edges = [
        rt.profile(edge_job, em, name, rt.straight_edge(rt.model(edge_job), y=y, z=0), "Outside", "CCW", 0, -5, 5, clearance=60)
        for name, y in (("front", 0), ("back", 50))
    ]
    rt.generate(doc)
    return {"ops": {"face": face, "edges": edges}}
'''


def test_freecad_posts_real_rapids_zigzag_faces_and_conventional_edges(tmp_path):
    """A 100 x 50 x 10 box faced with a 19.05 mm end mill, and two opposite
    edges profiled."""
    try:
        freecadcmd = cam_nc.resolve_freecadcmd()
    except cam_nc.FreeCadError as exc:
        pytest.skip(f"no usable FreeCAD: {exc}")
    recipe = tmp_path / "cam.py"
    recipe.write_text(_MINI_RECIPE, encoding="utf-8")
    programs = (("P1_face", ("face",)), ("P2_edges", ("edges",)))
    result = cam_nc.run_freecad(recipe, {"comment": "positive control"}, programs, tmp_path, freecadcmd, tmp_path / "freecadcmd.log")
    assert sorted(Path(f).name for f in result["files"]) == ["P1_face.nc", "P2_edges.nc"]
    assert Path(result["post"]).name == "grbl_post.py"
    face = _gcode.read_program(tmp_path / "P1_face.nc")
    assert any(m.motion is _gcode.Motion.RAPID and m.length > 0 for m in face.moves)
    assert face.spindle_rpm == {850.0}
    assert _gcode.check_face_passes(face, z=9.0, y=(0.0, 50.0), max_stepover=15.24, radius=9.525, span=50.0) == []
    assert _gcode.check_air_feed(face, 10.0) == []
    edges = _gcode.read_program(tmp_path / "P2_edges.nc")
    assert _gcode.check_air_feed(edges, 0.0) == []
    for final, raw, direction in ((-6.35, -9.35, 1.0), (56.35, 59.35, -1.0)):
        assert _gcode.check_side_passes(edges, "Y", final, raw, 3.0, direction, 50.0, 0.0) == [], final
