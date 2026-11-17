"""Positive control through headless FreeCAD: real G0 rapids, zigzag faces and
conventional edge passes from the CAM runtime and the ``grbl`` post, and
sections joined into one file at an M0 speed stop and at M6 tool changes.

Not in any ``check:*`` gate (see ``dodo._UNGATED``): it
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

_PROGRAMS = (
    ("P1_face", ("face",)), ("P2_edges", ("edges",)), ("P3_two_speeds", (("front",), ("back",))),
    ("P4_three_tools", (("face",), ("probe",), ("front",))), ("P5_face_inset", ("face_inset",)),
)
_MINI_RECIPE = f'''
STEM = "mini"
PROGRAMS = {_PROGRAMS!r}
''' + '''


def build(ctx, rt):
    doc = rt.document()
    face_job = rt.job(doc, "face", [rt.box(doc, "face_model", (-25, 125), (0, 50), (0, 9))], ((0, 100), (0, 50), (0, 10)))
    tc = rt.tool_controller(doc, "3/4 in endmill", 2, "endmill", 19.05, 850, 172.7, 86.35, flutes=4)
    face = rt.face(face_job, tc, "face", rt.top_face(rt.model(face_job), 9), 10, 9, 15.24)
    # P5: the box raised so its top line sits one 15.24 step inside the stock
    # (the base-bar recipe's _face_layout): four lines from the bottom, the
    # top one coinciding with the box's own edge line.
    inset_job = rt.job(doc, "face_inset", [rt.box(doc, "inset_model", (-25, 125), (50 - 4 * 15.24, 50 + 19.05 - 15.24), (0, 9))],
                       ((0, 100), (0, 50), (0, 10)))
    tc5 = rt.tool_controller(doc, "3/4 in endmill", 2, "endmill", 19.05, 850, 172.7, 86.35, flutes=4)
    face_inset = rt.face(inset_job, tc5, "face_inset", rt.top_face(rt.model(inset_job), 9), 10, 9, 15.24)
    edge_job = rt.job(doc, "edges", [rt.box(doc, "edge_model", (-10, 110), (0, 50), (-10, 0))], ((0, 100), (-3, 53), (-10, 0)))
    em = rt.tool_controller(doc, "1/2 in endmill", 1, "endmill", 12.7, 2250, 400, 63.5, flutes=2)
    edges = [
        rt.profile(edge_job, em, name, rt.straight_edge(rt.model(edge_job), y=y, z=0), "Outside", "CCW", 0, -5, 5, clearance=60)
        for name, y in (("front", 0), ("back", 50))
    ]
    # P3: the same tool at two spindle speeds, one job each, joined at an M0.
    sections = {}
    for name, y, rpm in (("front", 0, 2250), ("back", 50, 1250)):
        job = rt.job(doc, name, [rt.box(doc, f"{name}_model", (-10, 110), (0, 50), (-10, 0))], ((0, 100), (-3, 53), (-10, 0)))
        tc1 = rt.tool_controller(doc, "1/2 in endmill", 1, "endmill", 12.7, rpm, 400, 63.5, flutes=2)
        sections[name] = rt.profile(job, tc1, name, rt.straight_edge(rt.model(job), y=y, z=0), "Outside", "CCW", 0, -5, 5, clearance=60)
    rt.generate(doc)
    # P4: a manual section (the recipe's own G-code, spindle off) between two tools.
    probe = {"tool": 8, "label": "probe", "setting": "SPINDLE OFF - PROBE IN", "gcode": ["G0 Z20.000"]}
    return {"ops": {"face": face, "edges": edges, **sections, "probe": probe, "face_inset": face_inset}}
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
    result = cam_nc.run_freecad(recipe, {"comment": "positive control"}, _PROGRAMS, tmp_path, freecadcmd, tmp_path / "freecadcmd.log")
    assert sorted(Path(f).name for f in result["files"]) == [
        "P1_face.nc", "P2_edges.nc", "P3_two_speeds.nc", "P4_three_tools.nc", "P5_face_inset.nc"]
    assert Path(result["post"]).name == "grbl_post.py"
    face = _gcode.read_program(tmp_path / "P1_face.nc")
    assert any(m.motion is _gcode.Motion.RAPID and m.length > 0 for m in face.moves)
    assert face.spindle_rpm == {850.0}
    # FreeCAD's MillFace cuts the box's edge line first: flush with the stock,
    # that pass takes the cutter's full 19.05 mm.
    kwargs = {"z": 9.0, "y": (0.0, 50.0), "max_engagement": 15.24, "radius": 9.525, "span": 50.0}
    assert [f.detail for f in _gcode.check_face_passes(face, **kwargs)] == ["pass at Y 40.475 engages 19.050 > 15.240"]
    inset = _gcode.read_program(tmp_path / "P5_face_inset.nc")
    assert _gcode.check_face_passes(inset, **kwargs, overhang=0.5) == []
    assert len({round(m.end[1], 3) for m in inset.cutting if abs(m.end[0] - m.start[0]) > 50.0}) == 4
    assert _gcode.check_air_feed(face, 10.0) == []
    edges = _gcode.read_program(tmp_path / "P2_edges.nc")
    assert _gcode.check_air_feed(edges, 0.0) == []
    for final, raw, direction in ((-6.35, -9.35, 1.0), (56.35, 59.35, -1.0)):
        assert _gcode.check_side_passes(edges, "Y", final, raw, 3.0, direction, 50.0, 0.0) == [], final
    # Two sections joined at one commented M0 above the stock, no second
    # preamble or postamble.
    joined = _gcode.read_program(tmp_path / "P3_two_speeds.nc")
    assert _gcode.check_pauses(joined, 0.0, 1) == []
    assert _gcode.check_spindle(joined, [[2250, 1250]]) == []
    text = (tmp_path / "P3_two_speeds.nc").read_text(encoding="utf-8")
    assert text.count("(Begin preamble)") == 1 and text.count("(Begin postamble)") == 1
    assert [line for line in text.splitlines() if line.strip() == "M2"] == ["M2"]
    # Three tools: T2 loaded before the file, then M6 T8 (manual, spindle off)
    # and M6 T1, each after an M5 and its operator comment; the comments name
    # the recipe's tool label, not FreeCAD's de-duplicated one ("...001").
    three = _gcode.read_program(tmp_path / "P4_three_tools.nc")
    assert _gcode.check_tool_changes(three, 10.0, [8, 1]) == []
    assert _gcode.check_spindle(three, [850, [], 2250]) == []
    text = (tmp_path / "P4_three_tools.nc").read_text(encoding="utf-8")
    assert "%msg TOOL CHANGE: T1 1/2 in endmill, SET SPINDLE TO 2250 RPM" in text
    assert "%msg TOOL CHANGE: T8 probe, SPINDLE OFF - PROBE IN" in text
    assert not any(line.startswith("%msg TOOL CHANGE:") and "001" in line for line in text.splitlines())
