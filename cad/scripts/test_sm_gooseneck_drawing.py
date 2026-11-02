"""Offline flush end piece, blind tap, counterbore and weldment-note contracts."""

from __future__ import annotations

import ast
import asyncio
import math
from pathlib import Path
import re
from types import SimpleNamespace

import pytest

from _hole_spec import DRILL_POINT_H
import build_sm_gooseneck as part
import build_sm_gooseneck_spring_screw as screw_part
import draw_sm_gooseneck as drawing
import sm_gooseneck_geom as geom
import sm_gooseneck_spec as spec
import sm_gooseneck_spring_joint as joint


def _calls(module, *, name: str | None = None, attr: str | None = None) -> list:
    tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and (
            (name is not None and getattr(node.func, "id", None) == name)
            or (attr is not None and getattr(node.func, "attr", None) == attr)
        )
    ]


def test_end_piece_is_flush_and_the_tube_ends_on_its_head() -> None:
    # Owner ruling (#1951): flush with the tube OD, no step.
    assert geom.PLUG_DIA == geom.TUBE_DIA == 12.70
    assert part.PLUG_R == part.TUBE_R
    assert geom.TUBE_END_X - geom.ARM_END_X == pytest.approx(geom.PLUG_HEAD_LENGTH)
    assert geom.ARM_STRAIGHT == pytest.approx(
        geom.TUBE_STRAIGHT + geom.PLUG_HEAD_LENGTH
    )
    # The braze shank sits in the tube bore at its diametral clearance and
    # inside the straight, short of the bend tangent.
    clearance = geom.TUBE_BORE_DIA - joint.PLUG_SHANK_DIA
    assert joint.BRAZE_CLEARANCE_MIN <= clearance <= joint.BRAZE_CLEARANCE_MAX
    assert part.SHANK_R < part.TUBE_IR
    assert part.SHANK_END_X == pytest.approx(geom.TUBE_END_X + geom.PLUG_SHANK_LENGTH)
    assert part.SHANK_END_X < -geom.BEND_R
    assert geom.PLUG_LENGTH == geom.PLUG_HEAD_LENGTH + geom.PLUG_SHANK_LENGTH


def test_blind_tap_stays_inside_the_solid_end_piece() -> None:
    assert joint.TAP_SPEC.kind.startswith("tapped")
    assert joint.TAP_SPEC.size == "1/4-28"
    assert joint.TAP_SPEC.end == "blind"
    assert joint.TAP_SPEC.thread_class == "2B"
    assert part.TAP_DRILL_DIA == joint.TAP_DRILL_DIA
    assert joint.TAP_THREAD_DEPTH < joint.TAP_DRILL_DEPTH
    # The full drill Ø stays in the shortest head; the point stays in the end
    # piece, so the tube's bore never sees the drill.
    assert joint.TAP_DRILL_DEPTH_MAX <= joint.PLUG_HEAD_LENGTH_MIN
    tip = joint.TAP_DRILL_DEPTH_MAX + DRILL_POINT_H * joint.TAP_DRILL_DIA_MAX / 2.0
    assert tip < geom.PLUG_LENGTH
    taps = _calls(part, name="wizard_holes")
    assert len(taps) == 1
    # The tube is swept first; the end piece and its tap follow as their own
    # body, so the tap never reaches the tube's.
    sweeps = _calls(part, attr="create_sweep")
    assert sweeps
    assert taps[0].lineno > max(node.lineno for node in sweeps)


def test_tap_starts_on_the_counterbore_floor_of_the_unmerged_end_piece() -> None:
    source = Path(part.__file__).read_text(encoding="utf-8")
    sweep = source.index("create_sweep")
    end_piece = source.index('name_last_feature(adapter, "EndPiece")')
    counterbore = source.index('name_last_feature(adapter, "Counterbore")')
    tap = source.index('name="ThreadBore"')
    assert sweep < end_piece < counterbore < tap
    # The end piece is its own body, so section A-A hatches it apart from the
    # tube (machinist review of 3c0b5d87c).
    revolve = source.rindex("create_revolve", 0, end_piece)
    assert "merge_result=False" in source[revolve:end_piece]
    assert "len(bodies) != 2" in source
    assert "[[COUNTERBORE_FLOOR_X, ARM_Y, 0.0]]" in source
    assert joint.TAP_SPEC.depth_mm == joint.TAP_DRILL_DEPTH_FROM_FLOOR
    assert joint.TAP_SPEC.overrides_mm == {
        "ThreadDepth": joint.TAP_THREAD_DEPTH_FROM_FLOOR
    }
    assert joint.TAP_DRILL_DEPTH == pytest.approx(
        joint.COUNTERBORE_DEPTH + joint.TAP_DRILL_DEPTH_FROM_FLOOR
    )
    assert part.COUNTERBORE_R * 2.0 == joint.COUNTERBORE_DIA
    assert part.COUNTERBORE_FLOOR_X == pytest.approx(
        geom.ARM_END_X + joint.COUNTERBORE_DEPTH
    )


@pytest.mark.parametrize("builder", [part, screw_part], ids=lambda m: m.__name__)
def test_every_direct_db_block_restores_inference_in_finally(builder) -> None:
    # Sketch inference is session state on the persistent seat: each block
    # that turns it off must restore it even when a native segment is
    # rejected, so every True is followed at once by a try whose finally
    # restores it, and nothing restores it outside a finally.  Shared by the
    # MHA-SM-01 post and the MHA-SM-04 screw builders.
    tree = ast.parse(Path(builder.__file__).read_text(encoding="utf-8"))

    def toggle(node: ast.AST) -> str | None:
        if (
            isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Call)
            and getattr(node.value.func, "id", "") == "set_sketch_direct_db"
        ):
            return ast.unparse(node.value.args[1])
        return None

    on = restored = 0
    finally_offs: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Try):
            finally_offs |= {
                id(stmt) for stmt in node.finalbody if toggle(stmt) == "False"
            }
    for node in ast.walk(tree):
        body = getattr(node, "body", None)
        if not isinstance(body, list):
            continue
        for index, stmt in enumerate(body):
            if toggle(stmt) == "True":
                on += 1
                following = body[index + 1]
                assert isinstance(following, ast.Try), ast.unparse(stmt)
                assert [toggle(s) for s in following.finalbody] == ["False"]
                restored += 1
    offs = [node for node in ast.walk(tree) if toggle(node) == "False"]
    assert {id(node) for node in offs} == finally_offs
    # The property, not the inventory: at least one block, each restored.
    assert on == restored == len(offs) >= 1


def test_counterbore_callouts_floor_the_wall_from_the_joint() -> None:
    # A stated minimum is rounded DOWN, so the print never promises more
    # wall than the joint's worst case leaves (drawing-guidelines rule 20):
    # inches, to the sheet's .001.
    floored = math.floor(joint.COUNTERBORE_WALL_MIN / 25.4 * 1000.0) / 1000.0
    assert spec.COUNTERBORE_WALL_CALLOUT == (
        f"C'BORE WALL {floored:.3f} MIN".replace(" 0.", " .")
    )
    assert floored * 25.4 <= joint.COUNTERBORE_WALL_MIN
    callouts = spec.DIMENSION_CALLOUTS_BY_NAME
    # The wall rides under the head Ø, its outer bound, with the Ø max's job:
    # the stated wall holds at the counterbore's largest size (owner ruling
    # on machinist review r7: keep both bands, state each max's job).
    plug_rows = callouts["PlugDia"].splitlines()
    wall_row = plug_rows.index(spec.COUNTERBORE_WALL_CALLOUT)
    assert plug_rows[wall_row + 1 :] == ["AT C'BORE MAX"]
    # Each LIMIT band names its mate and its max's job on its own callout
    # (machinist review r8, farm run 20261101T035809796Z).
    assert callouts["CounterboreDia"] == spec.COUNTERBORE_DIA_CALLOUT
    assert spec.COUNTERBORE_DIA_CALLOUT.splitlines() == [
        f"MIN CLEARS {spec.SCREW_NUMBER}",
        "RUN-OUT; MAX SETS WALL",
    ]
    # The axis limit, a radial offset between named axes, rides the floor
    # corner's block under its reason.
    assert spec.COUNTERBORE_AXIS_CALLOUT.splitlines() == [
        "C'BORE AXIS TO TAP AXIS",
        f"{joint.COUNTERBORE_AXIS_OFFSET_MAX / 25.4:.3f} MAX RADIAL".lstrip("0"),
    ]
    assert "WITHIN" not in spec.COUNTERBORE_AXIS_CALLOUT
    assert callouts["CounterboreFloorCornerR"] == spec.COUNTERBORE_FLOOR_CALLOUT
    assert spec.COUNTERBORE_FLOOR_CALLOUT.splitlines() == [
        "CLEARS RUN-OUT;",
        *spec.COUNTERBORE_AXIS_CALLOUT.splitlines(),
    ]
    # The floor corner's limit is its own native radial dimension, not text
    # under the depth (codjiflo P2 on #1997); the depth names its MIN's mate
    # in one row above its stacked pair (rule 4).
    assert "CounterboreDepth" not in callouts
    assert spec.DIMENSION_CALLOUTS_ABOVE_BY_NAME == {
        "CounterboreDepth": f"MIN CLEARS {spec.SCREW_NUMBER} RUN-OUT"
    }
    assert "\n" not in spec.COUNTERBORE_DEPTH_CALLOUT
    marked = {name for names in spec.DRAWING_DIMENSIONS.values() for name in names}
    assert set(callouts) | set(spec.DIMENSION_CALLOUTS_ABOVE_BY_NAME) <= marked
    for by_feature in (spec.DIMENSION_CALLOUTS, spec.DIMENSION_CALLOUTS_ABOVE):
        for feature, by_name in by_feature.items():
            assert set(by_name) <= set(spec.DRAWING_DIMENSIONS[feature])


def test_counterbore_blocks_stand_between_their_neighbours() -> None:
    # r8 (farm run 20261101T035809796Z) inked the Ø's stacked pair and two
    # rows 19.2 mm tall, centred 0.45 mm above the keep, rows 5.6 mm apart;
    # the extension lines stand on the modelled Ø (its MIN) at 3:1.
    rows = len(spec.COUNTERBORE_DIA_CALLOUT.splitlines())
    height = 0.0137 + (rows - 1) * 0.0056
    centre = drawing.SECTION_KEEP["CounterboreDia"][1] + 0.00045
    half_span = joint.COUNTERBORE_DIA / 2.0 * drawing._SECTION_S
    lower, upper = drawing._SY0 - half_span, drawing._SY0 + half_span
    clearance = 0.0007
    assert centre - height / 2.0 >= lower + clearance
    assert centre + height / 2.0 <= upper - clearance
    # Positive control: cca02b34c's single value and three rows (~20.4 mm)
    # was struck by the lower line.
    assert 0.0036 + 3 * 0.0056 > upper - lower - 2 * clearance
    # The floor corner's block (value 3.6 mm, rows 5.56 mm apart, centred on
    # its keep, its shoulder 0.9 mm under) between the Ø's upper dimension
    # line, which ends 6.3 mm over the upper extension line, and the depth's
    # shoulder (r8: y 243.7 mm, 6.3 mm under the depth's keep y 250.05).
    floor_rows = len(spec.COUNTERBORE_FLOOR_CALLOUT.splitlines())
    floor_height = 0.0036 + floor_rows * 0.00556
    floor_y = drawing.SECTION_KEEP["CounterboreFloorCornerR"][1]
    shoulder = floor_y - floor_height / 2.0 - 0.0009
    assert shoulder >= upper + 0.0063 + 0.0025
    assert floor_y + floor_height / 2.0 <= 0.2437 - 0.0025
    # Each row no longer than r8's 55.5 mm "C'BORE AXIS TO TAP AXIS" (23
    # characters), which stood inside the left border and the end face.
    for callout in (spec.COUNTERBORE_DIA_CALLOUT, spec.COUNTERBORE_FLOOR_CALLOUT):
        assert max(map(len, callout.splitlines())) <= spec.COUNTERBORE_ROW_MAX_CHARS
    assert spec.COUNTERBORE_ROW_MAX_CHARS == len("C'BORE AXIS TO TAP AXIS")


def test_notes_state_stock_process_and_intent_without_sizes() -> None:
    lines = spec.DRAWING_NOTES.splitlines()
    # Rule 7: four lines at most, each ending left of the title block
    # (x 0.216) from NOTES_XY at the sheet's ~2.42 mm a character (farm run
    # 20261028T005208028Z: the 80-character line ended at x 0.210).
    assert len(lines) <= 4
    assert all(re.match(r"\d\. ", line) for line in lines)
    assert drawing.NOTES_XY[0] + 0.00242 * max(map(len, lines)) < 0.214
    notes = " ".join(spec.DRAWING_NOTES.split())
    # The joint's window in inches, rounded inward at four places.
    window = "-".join(
        f"{inches:.4f}".lstrip("0")
        for inches in (
            math.ceil(round(joint.BRAZE_CLEARANCE_MIN / 25.4 * 1e4, 6)) / 1e4,
            math.floor(round(joint.BRAZE_CLEARANCE_MAX / 25.4 * 1e4, 6)) / 1e4,
        )
    )
    assert window == ".0040-.0098"
    for phrase in (
        "TUBE 1/2 OD X 0.065 WALL, ONLINEMETALS 7322",
        "SLEEVE 5/8 OD X 0.058 WALL, 7324",
        # The stock is as supplied: its catalogue tolerance governs, unprinted.
        "BOTH AS SUPPLIED, SUPPLIER TOL.",
        "SLEEVE: CONTINUOUS BRAZE FILLET EACH END",
        "BRAZE BAg-7 (AWS A5.8)",
        "END PIECE: FULL-PENETRATION BRAZE OR LOCTITE 638",
        # Owner ruling 2026-10-27 (#1997): join before bending.
        "JOIN END PIECE, COOL OR FULLY CURE, THEN BEND",
        "OVALITY 5% MAX",
    ):
        assert phrase in notes, phrase
    # The shank and sleeve callouts state the joint's window on their own
    # features and name no method (rule 7: a matched fit goes on the feature).
    assert spec.SHANK_FIT_CALLOUT == f"FIT TO TUBE BORE,\n{window} DIAMETRAL\nCLEARANCE"
    assert (
        spec.SLEEVE_FIT_CALLOUT == f"STOCK; FIT ON TUBE,\n{window} DIAMETRAL\nCLEARANCE"
    )
    assert spec.DIMENSION_CALLOUTS["SleeveProfile"] == {
        "SleeveDia": spec.SLEEVE_FIT_CALLOUT
    }
    # A note names no tool (rule 7): R3.0 is the native bend radius.
    assert "DIE" not in notes
    # Sizes and tolerances are native model dimensions, never note text.
    assert re.search(r"\b\d+\.\d{1,2}\b", notes) is None, notes
    assert "<MOD-DIAM>" not in notes and "Ø" not in notes
    assert "THRU" not in notes.upper()


def test_stock_diameters_print_as_untoleranced_references() -> None:
    # Machinist review of main 31cea0b73 (owner ruling 2026-10-31): the as-
    # supplied tube and sleeve Ø print as native reference dimensions, no
    # band; the supplier's tolerance governs and the walls stay designations.
    assert spec.REFERENCE_DIMENSIONS == {
        "TubeOdReference": frozenset({"TubeOdRef"}),
        "SleeveProfile": frozenset({"SleeveDia"}),
        "OverallReference": frozenset({"OverallHeight", "OverallReach"}),
    }
    for feature, names in spec.REFERENCE_DIMENSIONS.items():
        assert names <= spec.DRAWING_DIMENSIONS[feature]
        assert set(names) <= set(drawing.FRONT_KEEP)
    # The reference line runs on the bare leg, between the sleeve and the bend.
    low = spec.TUBE_OD_REF_Y - spec.TUBE_OD_REF_SPAN / 2.0
    high = spec.TUBE_OD_REF_Y + spec.TUBE_OD_REF_SPAN / 2.0
    assert geom.SLEEVE_TOP < low < high < geom.LEG_TOP


def _recorded_equations(module) -> dict[str, str]:
    return {
        call.args[0].value: call.args[1].value
        for call in _calls(module, attr="record")
        if len(call.args) == 2 and isinstance(call.args[0], ast.Constant)
    }


def test_overall_height_and_reach_print_as_two_place_references() -> None:
    # Machinist review r5 of farm run 20261101T004958072Z: the leg length and
    # arm straight stop at the bend's tangents, so the bent part needs overall
    # sizes to real faces, printed as references beside the governing tangent
    # ones.  Two places: the snapped leg puts the height at 19.650 in, a
    # one-place tie.
    names = {"OverallHeight", "OverallReach"}
    assert spec.DRAWING_DIMENSIONS["OverallReference"] == names
    assert spec.REFERENCE_DIMENSIONS["OverallReference"] == names
    assert spec.DRAWING_PRECISION["OverallReference"] == dict.fromkeys(names, 2)
    assert names <= set(drawing.FRONT_KEEP)
    # The equations, evaluated on the part's globals, are the faces' spans.
    globals_mm = {
        "ArmY": geom.LEG_TOP + geom.BEND_R,
        "TubeDia": geom.TUBE_DIA,
        "LegBottom": geom.LEG_BOTTOM,
        "ArmEndX": geom.ARM_END_X,
    }
    equations = _recorded_equations(part)

    def evaluate(name: str) -> float:
        expression = re.sub(
            r'"(\w+)"', lambda m: repr(globals_mm[m.group(1)]), equations[name]
        )
        return eval(expression)  # noqa: S307 -- the builder's own literal

    height = geom.ARM_Y + geom.TUBE_DIA / 2.0 - geom.LEG_BOTTOM
    reach = geom.TUBE_DIA / 2.0 - geom.ARM_END_X
    assert evaluate("OverallHeight") == pytest.approx(height)
    assert evaluate("OverallReach") == pytest.approx(reach)
    assert height / 25.4 == pytest.approx(19.65)
    assert reach / 25.4 == pytest.approx(4.319, abs=0.0005)
    # The sketch is hidden in the part and shown only by the elevation.
    blanked = {call.args[1].value for call in _calls(part, name="blank_sketch")}
    assert "OverallReference" in blanked


def test_overall_references_stand_clear_of_the_elevation_dimensions() -> None:
    keep = drawing.FRONT_KEEP
    height_x, height_y = keep["OverallHeight"]
    reach_x, reach_y = keep["OverallReach"]
    # Outermost on the leg's right, short of the isometric's left edge (x
    # 0.358 in farm run 20261101T004958072Z), its text away from the leg's.
    assert keep["LegLength"][0] + 0.015 <= height_x <= drawing.ISO_CENTER[0] - 0.030
    assert abs(height_y - keep["LegLength"][1]) >= 0.015
    assert drawing.FOOT_Y < height_y < drawing._front_y(geom.ARM_Y + geom.TUBE_DIA / 2)
    # Over the arm straight, under the view label (bottom y 0.258).
    assert keep["ArmStraight"][1] + 0.005 <= reach_y <= 0.258 - 0.0045
    assert drawing.END_FACE_X < reach_x < drawing._front_x(geom.TUBE_DIA / 2)
    # The arm straight's text (11.3 mm wide at 27.16, farm run
    # 20261101T022045634Z; 1.07 is narrower) ends one
    # text clearance (1.78 mm) left of the end face's shared extension line.
    assert keep["ArmStraight"][0] + 0.0113 / 2 + 0.00178 <= drawing.END_FACE_X


def test_tap_callout_states_geometry_and_its_mate_within_four_rows() -> None:
    # The native callout's two rows plus these stay within the layout
    # audit's four-row limit; each row is finished geometry, not method.
    rows = spec.TAP_CALLOUT_BELOW.splitlines()
    assert len(rows) == 2
    # The counterbore depth's max sets the drill's deepest point, depths
    # running from its floor (owner ruling via Main on machinist review r7:
    # this job replaces the floor datum's wording).  The row is the drilled
    # hole's finished extent, not a process step: no wander.
    assert rows[0] == f"FOR {spec.SCREW_NUMBER}; DEEPEST DRILL AT C'BORE MAX"
    axis_limit = f"{joint.THREAD_AXIS_OFFSET_MAX / 25.4:.3f}".lstrip("0")
    assert rows[1] == f"THREAD AXIS TO TUBE OD AXIS {axis_limit} MAX RADIAL"
    assert joint.TAP_DRILL_DEPTH_MAX > joint.COUNTERBORE_DEPTH_MAX
    # At most three characters past r7's 39-character row (103.9 mm, x 106.1-
    # 210.0 mm; ~105.3 mm in Century Gothic's metrics): ~1 mm more each side
    # stays left of the arm straight's text.
    assert len(rows[0]) <= len(f"FOR {spec.SCREW_NUMBER}; DEPTHS FROM C'BORE FLOOR") + 3
    assert "WANDER" not in spec.TAP_CALLOUT_BELOW
    assert "BRAZE" not in spec.TAP_CALLOUT_BELOW
    assert spec.SCREW_NUMBER in spec.DIMENSION_CALLOUTS_BY_NAME["CounterboreDia"]
    printed = " ".join((spec.DRAWING_NOTES, spec.TAP_CALLOUT_BELOW)).upper()
    assert "PURCHASED" not in printed and "INTEGRAL" not in printed
    assert "THREADLOCKER" not in printed  # spring-eye clamping belongs to the assembly


def test_sheet_places_every_marked_dimension_at_its_places() -> None:
    marked = {name for names in spec.DRAWING_DIMENSIONS.values() for name in names}
    assert set(drawing.FRONT_KEEP) | set(drawing.SECTION_KEEP) == marked
    assert not set(drawing.FRONT_KEEP) & set(drawing.SECTION_KEEP)
    assert set(spec.DRAWING_DIMENSIONS["EndPieceProfile"]) | set(
        spec.DRAWING_DIMENSIONS["CounterboreProfile"]
    ) == set(drawing.SECTION_KEEP)
    assert set(spec.DRAWING_PRECISION_BY_NAME) == marked
    assert {
        name for name, places in spec.DRAWING_PRECISION_BY_NAME.items() if places == 1
    } == spec.ONE_PLACE_DIMENSIONS
    # Section A-A keeps only the end piece: its crop runs past the shank,
    # short of the bend; its full cut's line runs past where the plane leaves
    # the bend's outer wall, short of the leg.
    start, end = drawing.SECTION_CROP_X_MM
    assert start < geom.ARM_END_X < part.SHANK_END_X < end < -geom.BEND_R
    bend_cut_end = -geom.BEND_R + math.sqrt(
        (geom.BEND_R + geom.TUBE_DIA / 2.0) ** 2 - geom.BEND_R**2
    )
    line_start, line_end = drawing.SECTION_LINE_X_MM
    assert line_start == start and bend_cut_end < line_end < 0.0


@pytest.fixture
def saved_tap(monkeypatch):
    """Read-only saved feature with independently specified native tap metadata."""
    monkeypatch.setattr(drawing, "_early_bound", lambda value, _interface: value)
    definition = SimpleNamespace(
        FastenerSize="1/4-28",
        ThreadClass="2B",
        ThreadEndCondition=0,  # blind
        EndCondition=0,
        TapDrillDiameter=0.00541,  # native model length units are metres
        TapDrillDepth=0.017272,  # .68 in
        ThreadDepth=0.014732,  # .58 in
    )
    feature = SimpleNamespace(
        GetTypeName2=lambda: "HoleWzd",
        GetDefinition=lambda: definition,
    )
    model = SimpleNamespace(
        FeatureByName=lambda name: feature if name == "ThreadBore" else None,
    )
    return model, feature, definition


@pytest.mark.parametrize("offset_mm", [-0.004, 0.0, 0.004])
@pytest.mark.parametrize("field", ["TapDrillDiameter", "TapDrillDepth", "ThreadDepth"])
def test_saved_native_receiver_accepts_the_blind_tap(saved_tap, field, offset_mm):
    model, _feature, definition = saved_tap
    setattr(definition, field, getattr(definition, field) + offset_mm / 1000.0)
    drawing._require_saved_tap(model)


@pytest.mark.parametrize(
    ("field", "value", "diagnostic"),
    [
        ("FastenerSize", "1/4-20", "thread size"),
        ("ThreadClass", "", "ThreadClass"),
        ("ThreadClass", "3B", "ThreadClass"),
        ("ThreadEndCondition", 1, "ThreadEndCondition"),
        ("ThreadEndCondition", 2, "ThreadEndCondition"),
        ("EndCondition", 1, "EndCondition"),
        ("EndCondition", 2, "EndCondition"),
        ("TapDrillDiameter", 0.0, "tap drill"),
        ("TapDrillDiameter", 0.005404, "tap drill"),
        ("TapDrillDiameter", 0.005416, "tap drill"),
        ("TapDrillDiameter", math.nan, "tap drill"),
        ("TapDrillDepth", 0.0171, "tap drill depth"),
        ("TapDrillDepth", 0.0200, "tap drill depth"),
        ("ThreadDepth", 0.0147, "thread depth"),
        ("ThreadDepth", 0.0122, "thread depth"),
    ],
)
def test_saved_native_receiver_rejects_lost_thread_metadata(
    saved_tap, field, value, diagnostic
):
    model, _feature, definition = saved_tap
    setattr(definition, field, value)
    with pytest.raises(RuntimeError, match=diagnostic):
        drawing._require_saved_tap(model)


@pytest.mark.parametrize("fault", ["missing", "plain_cut", "no_definition"])
def test_saved_receiver_requires_a_native_hole_feature(saved_tap, fault):
    model, feature, _definition = saved_tap
    if fault == "missing":
        model.FeatureByName = lambda _name: None
    elif fault == "plain_cut":
        feature.GetTypeName2 = lambda: "Cut"
    else:
        feature.GetDefinition = lambda: None
    with pytest.raises(RuntimeError):
        drawing._require_saved_tap(model)


def _mass_adapter(volume: float):
    async def get_mass_properties():
        return SimpleNamespace(
            is_success=True, error=None, data=SimpleNamespace(volume=volume)
        )

    return SimpleNamespace(get_mass_properties=get_mass_properties)


@pytest.mark.parametrize("volume", [math.nan, math.inf, -math.inf])
def test_build_stops_on_a_non_finite_volume_read(volume):
    # NaN passes |vol - expected| > tol, the shared volume_check's included
    # (codjiflo rounds 5 and 6 on #1997).
    adapter = _mass_adapter(volume)
    with pytest.raises(RuntimeError, match="non-finite volume"):
        asyncio.run(part._volume(adapter))
    # The shared check already rejects an infinite read; NaN needs the guard.
    with pytest.raises(RuntimeError, match="non-finite volume|volume -?inf"):
        asyncio.run(part._volume_check(adapter, "end piece", 100.0, 1.0))
    assert asyncio.run(part._volume(_mass_adapter(100.0))) == 100.0
