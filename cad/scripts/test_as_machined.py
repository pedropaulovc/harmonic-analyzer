"""The as-machined report's host side, without FreeCAD: tool profiles, frames,
blanks, move pieces, the declaration's checks, pass accounting and the
gating summary. The FreeCAD end of it (seeded faults on a cut part) is
``test_as_machined_freecad.py``, outside every gate."""

from __future__ import annotations

import math
import tomllib
from pathlib import Path
from types import SimpleNamespace

import pytest

import _as_machined as am
import _cam_programs
import _gcode
import _process_plans
import export_features

IDENTITY = {"origin": [0.0, 0.0, 0.0], "axes": [[1, 0, 0], [0, 1, 0], [0, 0, 1]]}
# Setup Z along model -Z, X along model X: a part turned over about X.
FLIPPED = {"origin": [0.0, 0.0, 10.0], "axes": [[1, 0, 0], [0, -1, 0], [0, 0, -1]]}


def _job(tool, frame, keys, shape="endmill", dia=6.0, **extra):
    return {"tool": tool, "frame": frame, "shape": shape, "dia": dia, "ops": [[key, key, []] for key in keys], **extra}


def _recipe(programs, declare=None, mode="report", **extra):
    recipe = SimpleNamespace(PROGRAMS=programs, **extra)
    if declare is not None:
        recipe.as_machined = declare
        recipe.AS_MACHINED_MODE = mode
    return recipe


def _ctx(jobs, frames=None, numbers=None, manual=None):
    return {
        "frames": frames or {"top": IDENTITY, "bottom": FLIPPED},
        "jobs": jobs,
        "numbers": numbers or {job["tool"]: n for n, job in enumerate(jobs, 1)},
        "manual": manual or {},
    }


def _inputs(steps=None, plan=None):
    return SimpleNamespace(features={}, plan=plan or {"milling_material": "brass"}, shop={}, steps=steps or {"": "part.step"})


BLANK = {"frame": "top", "box": [[0, 20], [0, 10], [0, 12]]}


# --- tools -----------------------------------------------------------------


def test_tool_profiles_follow_the_job_shape():
    assert am.tool_profile({"tool": "em", "shape": "endmill", "dia": 12.7}, None) == [(6.35, 0.0)]
    drill = am.tool_profile({"tool": "d", "shape": "drill", "dia": 6.0, "tip_angle": 118.0}, None)
    assert drill[0] == (0.0, 0.0) and drill[1][0] == 3.0
    assert math.isclose(drill[1][1], 3.0 / math.tan(math.radians(59.0)))
    assert am.tool_profile({"tool": "r", "shape": "drill", "dia": 6.0, "tip_angle": 180.0}, None) == [(3.0, 0.0)]
    ball = am.tool_profile({"tool": "b", "shape": "ballend", "dia": 4.0}, None)
    assert ball[0] == (0.0, 0.0) and math.isclose(ball[-1][0], 2.0) and math.isclose(ball[-1][1], 2.0)


def test_the_spot_job_is_the_recipes_centre_drill():
    centre = {"pilot_mm": 2.0, "pilot_length_mm": 2.0, "body_mm": 5.0, "point_deg": 60.0}
    profile = am.tool_profile({"tool": "spot", "shape": "drill", "dia": 5.0, "tip_angle": 60.0}, centre)
    assert profile[0] == (0.0, 0.0)
    assert profile[1][0] == 1.0 and math.isclose(profile[1][1], 1.0 / math.tan(math.radians(59.0)))
    assert profile[2] == (1.0, 2.0)
    assert math.isclose(profile[3][1], 2.0 + 1.5 / math.tan(math.radians(30.0)))
    with pytest.raises(am.NotCovered, match="body"):
        am.tool_profile({"tool": "spot", "shape": "drill", "dia": 4.0, "tip_angle": 60.0}, centre)


def test_a_tool_without_a_profile_is_not_covered():
    with pytest.raises(am.NotCovered, match="slittingsaw"):
        am.tool_profile({"tool": "saw", "shape": "slittingsaw", "dia": 50.0}, None)


# --- frames and blanks -------------------------------------------------------


def test_frames_must_be_rigid():
    flipped = am.frame(FLIPPED, "bottom")
    p = (3.0, 4.0, 5.0)
    assert flipped.to_model(flipped.to_setup(p)) == pytest.approx(p)
    assert flipped.to_setup((0.0, 0.0, 10.0)) == pytest.approx((0.0, 0.0, 0.0))
    with pytest.raises(am.NotCovered, match="mirror"):
        am.frame({"origin": [0, 0, 0], "axes": [[1, 0, 0], [0, 1, 0], [0, 0, -1]]}, "m")
    with pytest.raises(am.NotCovered, match="orthonormal"):
        am.frame({"origin": [0, 0, 0], "axes": [[1, 0, 0], [0, 2, 0], [0, 0, 1]]}, "s")


def _span(blank, axis):
    values = [p[axis] for p in am.blank_corners(blank)]
    return pytest.approx((min(values), max(values)))


def test_the_blank_length_band_moves_the_face_away_from_the_kept_one():
    frames = {"bottom": am.frame(FLIPPED, "bottom")}
    spec = {"frame": "bottom", "box": [[0, 20], [-10, 0], [-12, 0.5]],
            "length": {"axis": "z", "keep": "max", "mm": {"nominal": 12.5, "min": 12.0, "max": 13.0}}}
    found, lengths = am.blanks(spec, frames)
    assert lengths == {"nominal": 12.5, "min": 12.0, "max": 13.0}
    # Setup z = 10 - model z: the kept face (setup z 0.5) is model z 9.5.
    assert _span(found["min"], 2) == (9.5, 21.5)
    assert _span(found["max"], 2) == (9.5, 22.5)
    assert _span(found["nominal"], 1) == (0.0, 10.0)
    # Extruded from the far face (setup z -12.5, model z 22.5) toward the kept one.
    assert found["max"][0]["dir"] == pytest.approx([0.0, 0.0, -13.0])
    plain, none = am.blanks({"frame": "bottom", "box": [[0, 1], [0, 1], [0, 1]]}, frames)
    assert list(plain) == ["nominal"] and none is None
    with pytest.raises(am.NotCovered, match="no frame"):
        am.blanks({"frame": "side", "box": [[0, 1], [0, 1], [0, 1]]}, frames)


def test_a_bar_section_blank_is_a_prism_along_its_axis():
    frames = {"top": am.frame(IDENTITY, "top")}
    hexagon = [[math.cos(k * math.pi / 3), math.sin(k * math.pi / 3)] for k in range(6)]
    spec = {"frame": "top", "prism": {"axis": "x", "polygon": hexagon, "span": [0, 30]},
            "length": {"axis": "x", "keep": "min", "mm": {"nominal": 30.0, "min": 29.0}}}
    found, _lengths = am.blanks(spec, frames)
    # The section (y, z) at x = 0, extruded along +x by each length.
    assert found["nominal"][0]["base"][1] == pytest.approx([0.0, 0.5, math.sqrt(3) / 2])
    assert found["min"][0]["dir"] == pytest.approx([29.0, 0.0, 0.0])
    turned = {"frame": "top", "prism": [{"axis": "x", "polygon": hexagon, "span": [0, 30]},
                                        {"axis": "x", "polygon": [[0.2, 0], [0, 0.2], [-0.2, 0]], "span": [30, 35]}]}
    union, none = am.blanks(turned, frames)
    assert len(union["nominal"]) == 2 and none is None
    assert max(p[0] for p in am.blank_corners(union["nominal"])) == pytest.approx(35.0)
    with pytest.raises(am.NotCovered, match="no length band"):
        am.blanks({**turned, "length": spec["length"]}, frames)
    with pytest.raises(am.NotCovered, match="own axis"):
        am.blanks({**spec, "length": {**spec["length"], "axis": "z"}}, frames)


# --- moves -------------------------------------------------------------------


def _program(tmp_path: Path, text: str) -> _gcode.Program:
    path = tmp_path / "P.nc"
    path.write_text(text, encoding="utf-8")
    return _gcode.read_program(path)


def test_pieces_of_plunges_ramps_helices_and_moves_above_the_blank(tmp_path):
    program = _program(tmp_path, "\n".join([
        "G90 G17", "G0 X0 Y0 Z5", "G1 Z-1 F100", "G1 X10 Z-1.1", "G2 X10 Y0 Z-1.5 I-5 J0", "G1 X20 Y0 Z-1.5",
        "G0 Z20", "G1 X30 F100",
    ]))
    plunge, ramp, helix, flat, _up, high = (am.pieces(m, 0.0) for m in program.moves[1:])
    assert plunge == [{"kind": "stand", "x": 0.0, "y": 0.0, "z": -1.0}]
    assert len(ramp) == math.ceil(0.1 / am.RAMP_DZ_MM) and ramp[-1]["z"] == pytest.approx(-1.1)
    assert max(p["z"] for p in ramp) <= -1.0
    # The tool stands at the ramp's two ends only.
    assert [p["caps"] for p in ramp] == [[True, False], [False, False], [False, False], [False, False], [False, True]]
    # A full helical turn, cut at its upper Z.
    assert len(helix) == 1 and helix[0]["kind"] == "arc" and helix[0]["z"] == -1.1
    assert helix[0]["sweep"] == pytest.approx(-2 * math.pi) and helix[0]["r"] == pytest.approx(5.0)
    assert flat == [{"kind": "seg", "a": [10.0, 0.0], "b": [20.0, 0.0], "z": -1.5, "caps": [True, True]}]
    assert high == []


def test_pieces_at_or_above_the_blank_top_are_dropped(tmp_path):
    """A ramp in from above the top and a helix from above it: only what
    runs below the top, the ramp's run capped at its two ends; the helix as
    chords, since its upper Z (the one an arc is cut at) is above the top."""
    program = _program(tmp_path, "\n".join([
        "G90 G17", "G0 X0 Y0 Z0.5", "G1 X1 Z-0.05 F100", "G0 X5 Y0 Z1", "G2 X5 Y0 Z-1 I-5 J0",
    ]))
    ramp, _rapid, helix = (am.pieces(m, 0.0) for m in program.moves[1:])
    assert len(ramp) == 3 and all(p["z"] < 0.0 for p in ramp)
    assert [p["caps"] for p in ramp] == [[True, False], [False, False], [False, True]]
    assert helix and {p["kind"] for p in helix} == {"seg"} and all(p["z"] < 0.0 for p in helix)
    assert helix[0]["caps"][0] and helix[-1]["caps"][1]


def test_the_tool_does_not_cut_again_where_it_already_stood(tmp_path):
    """Plunge and two strokes on from where it stood; a rise (it stood at
    its foot: nothing to cut) and a stroke at the new Z (never stood there);
    the stroke back with another tool."""
    program = _program(tmp_path, "\n".join([
        "G90 G17", "G0 X0 Y0 Z5", "G1 Z-1 F100", "G1 X10", "G1 Y10", "G1 Z-0.5", "G1 X0",
        "M6 T2", "G1 X10 Y10 Z-0.5",
    ]))
    setup = SimpleNamespace(entry_tool=1)
    moves, _uncut = am.program_moves(program, setup, 0.0, {1: [(3.0, 0.0)], 2: [(3.0, 0.0)]})
    caps = [(m["index"], [p.get("caps") for p in m["pieces"]]) for m in moves]
    assert caps == [(1, [None]), (2, [[False, True]]), (3, [[False, True]]), (5, [[True, True]]), (6, [[True, True]])]


def test_moves_run_with_the_tool_of_the_last_tool_change(tmp_path):
    program = _program(tmp_path, "G0 X0 Y0 Z5\nG1 Z1 F10\nM6 T3\nG1 Z0\nM6 T4\nG1 Z-1\n")
    assert am.move_tools(program, 9) == [9, 9, 3, 4]


def test_air_passes_and_cutting_rapids(tmp_path):
    program = _program(tmp_path, "\n".join([
        "G0 X0 Y0 Z5", "G1 Z0 F100", "G1 X30", "G1 Y2", "G1 X0", "G0 Z5", "G0 X40 Y0 Z-1", "G1 X80 Z-1",
    ]))
    profiles = {1: [(3.0, 0.0)]}
    # Sent: every move but the last (wholly above the blank in this example).
    sent = [1, 2, 3, 4, 5, 6]
    removed = [0.5, 40.0, 0.0, 0.0, 0.0, 2.5]
    air, rapids = am.passes(program, 1, sent, removed, profiles)
    # X30 -> X0 back over cut ground (30 mm >= the 6 mm tool) and the last pass
    # (not sent: above the blank). The 2 mm step-over is a link, not a pass.
    assert [(p["move"], p["above_blank"]) for p in air] == [(4, False), (7, True)]
    assert air[0]["minutes"] == pytest.approx(30.0 / 100)
    assert [(r["move"], r["removed_mm3"]) for r in rapids] == [(6, 2.5)]


# --- declaration ---------------------------------------------------------------


def _decl(**part):
    return lambda ctx, inputs: {"parts": {"": {"blank": BLANK, **part}}}


def test_the_route_follows_programs_in_their_jobs_frames():
    jobs = [_job("em", "top", ["face"]), _job("drill", "bottom", ["hole"], shape="drill", tip_angle=118.0)]
    ctx = _ctx(jobs, manual={"tap": {"tool": 7}}, numbers={"em": 1, "drill": 2, "guide": 7})
    programs = (("P1", ("face",)), ("P2", (("hole",),)), ("P3", ("tap",)))
    decl = am.declaration(_recipe(programs, _decl()), ctx, _inputs())
    (part,) = decl.parts
    assert [(s.program, s.frame_key, s.entry_tool) for s in part.setups] == [("P1", "top", 1), ("P2", "bottom", 2), ("P3", None, None)]
    assert decl.uncut_tools == (7,) and set(decl.profiles) == {1, 2}
    assert part.density == am.DENSITY_G_CM3["brass"] and part.step == "part.step"


@pytest.mark.parametrize(
    ("recipe", "reason"),
    [
        (_recipe((("P1", ("face",)),)), "declares no as_machined"),
        (_recipe((("P1", ("face",)),), AS_MACHINED_NOT_COVERED="turned first"), "turned first"),
        (_recipe((("P1", ("face",)),), _decl(), mode="maybe"), "AS_MACHINED_MODE"),
        (_recipe((("P1", ("face",)), ("P2", ("hole",))), _decl(route=[["P1", "top"]])), r"neither routed nor skipped: \['P2'\]"),
        (_recipe((("P1", ("face",)),), lambda c, i: {"parts": {"": {"blank": BLANK}}, "skip": {"P9": "x"}}), "skip names no program"),
        (_recipe((("P1", ("face", "hole")),), _decl()), "several frames"),
        (_recipe((("P1", ("face",)),), _decl(route=[["P1", "side"]])), "no frame of the recipe"),
        (_recipe((("P1", ("face",)),), lambda c, i: {"parts": {"front": {"blank": BLANK}}}), "declares parts"),
    ],
)
def test_what_the_declaration_refuses(recipe, reason):
    ctx = _ctx([_job("em", "top", ["face"]), _job("drill", "bottom", ["hole"], shape="drill", tip_angle=118.0)])
    with pytest.raises(am.NotCovered, match=reason):
        am.declaration(recipe, ctx, _inputs())


def test_skipped_programs_and_declared_tools():
    programs = (("P0", ("fixture",)), ("P1", ("face",)))
    ctx = _ctx([_job("em", "fixture", ["fixture"]), _job("saw", "top", ["face"], shape="slittingsaw", dia=50.0)],
               frames={"top": IDENTITY}, numbers={"em": 1, "saw": 2})
    declare = lambda c, i: {"parts": {"": {"blank": BLANK}}, "skip": {"P0": "faces the fixture"},  # noqa: E731
                            "tools": {2: [[25.0, 0.0], [25.0, 1.6], [8.0, 1.6]]}}
    decl = am.declaration(_recipe(programs, declare), ctx, _inputs())
    assert decl.skipped == {"P0": "faces the fixture"}
    assert [s.program for s in decl.parts[0].setups] == ["P1"]
    assert decl.profiles[2] == [(25.0, 0.0), (25.0, 1.6), (8.0, 1.6)]


# --- summary -------------------------------------------------------------------


def _out(**variant):
    base = {"over_noise": [], "unexplained": [], "expected": [], "rapid_cuts": [], "air_passes": [], "max_left_mm": 0.0,
            "max_gouge_mm": 0.0, "cog_offset_mm": 0.0, "volume_mm3": {"difference": -0.1}}
    return {"stem": "s", "covered": True, "mode": "report", "seconds": 1.0,
            "parts": {"": {"variants": {"nominal": {**base, **variant}}}}}


def test_failures_name_unexplained_regions_gone_expectations_and_cutting_rapids():
    assert am.failures(_out()) == []
    out = _out(unexplained=[{"kind": "left", "thickness_mm": 0.5, "extent_mm": [[0, 1], [0, 1], [0, 1]]},
                            {"kind": "gouge", "thickness_mm": None, "extent_mm": [[0, 1], [0, 1], [0, 1]]}],
               expected=[{"name": "tap", "kind": "left", "stale": True}, {"name": "aim", "kind": "gouge", "stale": False}],
               rapid_cuts=[{"program": "P1", "move": 4, "removed_mm3": 2.0}])
    assert am.failures(out) == [
        "s nominal: unexplained left 0.500 mm in [[0, 1], [0, 1], [0, 1]]",
        "s nominal: unexplained gouge unmeasured in [[0, 1], [0, 1], [0, 1]]",
        "s nominal: expected 'tap' (left) is gone",
        "s nominal: rapid P1 move 4 removed 2.000 mm3",
    ]
    assert am.failures({"stem": "s", "covered": True, "error": "boom"}) == ["s: the report failed: boom"]
    attrs = am.headline(out)
    assert attrs["as_machined.unexplained"] == 2 and attrs["as_machined.stale_expected"] == 1
    attrs = am.headline(_out(max_left_mm=0.2, air_passes=[{}, {}]))
    assert attrs["as_machined.max_left_mm"] == 0.2 and attrs["as_machined.air_passes"] == 2
    assert am.headline({"covered": False, "reason": "r", "seconds": 0.0})["as_machined.reason"] == "r"


def test_a_gating_recipe_fails_when_not_covered_or_aimed_outside_its_band():
    not_covered = {"stem": "s", "covered": False, "reason": "programs neither routed nor skipped: ['P9']"}
    assert am.failures({**not_covered, "mode": am.MODE_REPORT}) == []
    assert am.failures({**not_covered, "mode": am.MODE_GATE}) == [
        "s: not covered: programs neither routed nor skipped: ['P9']"]
    aim = {"band_mm": [98.0, 99.5], "cad_mm": 99.0, "aim_mm": 100.0, "in_band": False, "cad_in_band": True}
    out = _out(expected=[{"name": "length aim", "kind": "left", "stale": False, "aim": aim}])
    assert am.failures(out) == ["s nominal: expected 'length aim' aims at 100.0 outside its band [98.0, 99.5]"]


def _region(kind, depth, box):
    return {"kind": kind, "thickness_mm": depth, "at_mm": None, "volume_mm3": 1.0, "extent_mm": box}


def test_expected_differences_explain_regions_in_their_box_and_report_aims_and_gone_ones():
    expects = am.expected([
        {"name": "taps", "kind": "left", "within": [[0, 10], [0, 10], [-5, 0]], "reason": "hand taps", "max_mm": 0.8},
        {"name": "length aim", "kind": "gouge", "within": [[99, 101], [0, 10], [-5, 0]], "reason": "band middle",
         "aim": {"band_mm": [98.0, 99.5], "cad_mm": 100.0, "aim_mm": 99.0}},
        {"name": "thin sheet", "kind": "gouge", "within": [[0, 100], [0, 10], [-1, 0]], "reason": "as rolled",
         "variants": ["min"]},
    ], {}, ["nominal", "min", "max"])
    over = [_region("left", 0.5, [[1, 2], [1, 2], [-3, 0]]),  # a tap
            _region("left", 0.9, [[1, 2], [1, 2], [-3, 0]]),  # deeper than taps allow
            _region("gouge", 1.02, [[99.5, 100], [0, 10], [-5, 0]]),  # the aim, 1.0 deep
            _region("gouge", 0.5, [[0, 50], [0, 10], [-1, 0]])]  # the sheet: min only
    unexplained, rows = am.explain("nominal", over, {"left": [{"volume_mm3": 0.1, "extent_mm": [[3, 4], [3, 4], [-1, 0]]}],
                                                     "gouge": []}, expects)
    assert [r["expected"] for r in over] == ["taps", None, "length aim", None]
    assert [(r["thickness_mm"], r["kind"]) for r in unexplained] == [(0.9, "left"), (0.5, "gouge")]
    assert [(r["name"], r["regions"], r["stale"]) for r in rows] == [("taps", 2, False), ("length aim", 1, False)]
    assert rows[1]["aim"]["in_band"] and not rows[1]["aim"]["cad_in_band"]
    unexplained, rows = am.explain("min", [], {"left": [], "gouge": []}, expects)
    assert unexplained == [] and [r["name"] for r in rows if r["stale"]] == ["taps", "length aim", "thin sheet"]


@pytest.mark.parametrize("bad, why", [
    ({"kind": "left", "within": [[0, 1], [0, 1], [0, 1]], "reason": "r"}, "name"),
    ({"name": "a", "kind": "both", "within": [[0, 1], [0, 1], [0, 1]], "reason": "r"}, "kind"),
    ({"name": "a", "kind": "left", "within": [[0, 1], [0, 1], [0, 1]], "reason": " "}, "reason"),
    ({"name": "a", "kind": "left", "within": [[1, 0], [0, 1], [0, 1]], "reason": "r"}, "increasing"),
    ({"name": "a", "kind": "left", "within": [[0, 1], [0, 1], [0, 1]], "reason": "r", "variants": ["long"]}, "variants"),
    ({"name": "a", "kind": "left", "within": [[0, 1], [0, 1], [0, 1]], "reason": "r", "frame": "side"}, "frame"),
])
def test_an_expected_difference_states_what_it_is_and_why(bad, why):
    with pytest.raises(am.NotCovered, match=why):
        am.expected([bad], {}, ["nominal"])


def test_an_expected_box_in_a_setup_frame_is_its_model_bound_box():
    side = am.frame({"origin": [10, 0, 0], "axes": [[0, 1, 0], [0, 0, 1], [1, 0, 0]]}, "side")
    (e,) = am.expected([{"name": "a", "kind": "left", "within": [[0, 1], [0, 2], [0, 3]], "reason": "r",
                         "frame": "side"}], {"side": side}, ["nominal"])
    assert e.within == ((10.0, 13.0), (0.0, 1.0), (0.0, 2.0))


def test_every_recipe_states_its_coverage_one_way():
    """A recipe declares (with a mode) or says why not; never both."""
    for stem in _cam_programs.CAM_STEMS:
        recipe = _cam_programs.load_recipe(stem)
        declares = hasattr(recipe, "as_machined")
        assert declares == hasattr(recipe, "AS_MACHINED_MODE"), stem
        assert not (declares and hasattr(recipe, "AS_MACHINED_NOT_COVERED")), stem
        if declares:
            assert recipe.AS_MACHINED_MODE in am.MODES, stem


def _declaring_stems() -> list[str]:
    return [stem for stem in _cam_programs.CAM_STEMS if hasattr(_cam_programs.load_recipe(stem), "as_machined")]


@pytest.mark.parametrize("stem", _declaring_stems())
def test_every_declaration_resolves_against_its_recipes_current_context(stem):
    """A recipe's as_machined() reads its own context(): a context change
    that leaves it reading a key no longer there (a reamer that became a
    drill) fails here, not first in the report after a merge. The context
    is the recipe's own on the drawings' requirement manifests (no FreeCAD,
    no SolidWorks), as its process test builds it."""
    recipe = _cam_programs.load_recipe(stem)
    plan = tomllib.loads(_process_plans.plan_path(stem).read_text(encoding="utf-8"))
    shop = _process_plans.load_shop()
    family = _process_plans.family_parts(stem)
    if family:
        features = {pid: export_features.requirement_manifest(part) for pid, part in family.items()}
        views = {pid: _process_plans.part_view(plan, pid) for pid in family}
        steps = {pid: f"{part}.step" for pid, part in family.items()}
        ctx = recipe.context(features, views, shop, steps)
        inputs = SimpleNamespace(features=features, plan=views, shop=shop, steps=steps)
    else:
        features = export_features.requirement_manifest(stem)
        ctx = recipe.context(features, plan, shop, f"{stem}.step")
        inputs = SimpleNamespace(features=features, plan=plan, shop=shop, steps={"": f"{stem}.step"})
    decl = am.declaration(recipe, ctx, inputs)
    assert decl.parts and all(part.blanks and part.setups for part in decl.parts), stem


def test_cam_nc_never_fails_a_report_mode_task_on_its_report(monkeypatch, tmp_path):
    import cam_nc

    def boom(*_args, **_kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(am, "report", boom)
    recipe = SimpleNamespace(AS_MACHINED_MODE=am.MODE_REPORT)
    found = cam_nc.as_machined("s", recipe, {}, _inputs(), tmp_path, lambda: Path("freecadcmd"))
    assert found == ["s: the report failed: disk full"]
