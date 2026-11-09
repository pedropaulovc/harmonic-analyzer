"""Offline contracts for MHA-SM-05, the gooseneck end plug, and its drawing.

Owner rulings 2026-11-08 (Pedro), #2315: an independent part, bonded into
MHA-SM-01 with LOCTITE 638 at MHA-SM-00, tapped #10-24 blind before bonding
for the MHA-SM-VN-56 shoulder screw.
"""

from __future__ import annotations

import ast
import asyncio
import math
import re
from pathlib import Path
from types import SimpleNamespace

import pytest

import _config
import build_sm_gooseneck_end_plug as part
import draw_sm_gooseneck_end_plug as drawing
import sm_gooseneck_end_plug_spec as spec
import sm_gooseneck_geom as geom
import sm_gooseneck_spring_joint as joint
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS
from _drawing_registry import DRAWINGS_BY_NAME
from _hole_spec import DRILL_POINT_H
from _machinist_review_mode import MachinistReviewMode

IN = 25.4


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


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/sm-gooseneck-end-plug.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/sm-gooseneck-end-plug.pdf")
    entry = DRAWINGS_BY_NAME["sm_gooseneck_end_plug"]
    assert entry.script == Path(drawing.__file__).resolve()
    assert entry.layout == DRAWINGS_BY_NAME["sm_gooseneck"].layout
    assert "draw_sm_gooseneck_end_plug.py" in PRECISION_MIGRATED_DRAWINGS
    assert drawing.MACHINIST_REVIEW is MachinistReviewMode.ENFORCE


def test_registry_row_is_an_independent_bare_1018_part() -> None:
    row = _config.parts("sm-gooseneck-end-plug")
    assert row["number"] == spec.NUMBER == "MHA-SM-05"
    assert "component_of" not in row
    assert int(row["quantity"]) == 1
    assert row["drawing_unit"] == spec.UNIT == geom.SHEET_UNIT == "in"
    assert "1018" in str(row["material_specification"])
    assert "no plating" in str(row["finish"])
    assert part.MATERIAL == "Plain Carbon Steel"
    # The numbers the notes and callout name are the registries' own.
    assert _config.parts("sm-gooseneck")["number"] == spec.TUBE_NUMBER
    assert _config.parts("sm-vn-gooseneck-shoulder-screw")["number"] == spec.SCREW_NUMBER


def test_plug_is_flush_and_its_spigot_sits_in_the_bore() -> None:
    # Owner rulings 2026-11-08 (Pedro), #2315: head Ø.500 x .60 flush with
    # the tube, spigot Ø.363 x .42 at the bond window.
    assert geom.PLUG_DIA == geom.TUBE_DIA == pytest.approx(0.500 * IN)
    assert geom.PLUG_HEAD_LENGTH == pytest.approx(0.60 * IN)
    assert geom.PLUG_SHANK_LENGTH == pytest.approx(0.42 * IN)
    assert joint.PLUG_SHANK_DIA == pytest.approx(0.363 * IN)
    assert geom.TUBE_END_X - geom.ARM_END_X == pytest.approx(geom.PLUG_HEAD_LENGTH)
    clearance = geom.TUBE_BORE_DIA - joint.PLUG_SHANK_DIA
    assert joint.BOND_CLEARANCE_MIN <= clearance <= joint.BOND_CLEARANCE_MAX
    assert part.TAP_DRILL_R < part.SHANK_R < part.PLUG_R
    # The longest printed spigot stays short of the bend's exit tangent.
    assert spec.SPIGOT_LENGTH_MAX == pytest.approx(0.44 * IN)
    assert spec.SPIGOT_LENGTH_MIN == pytest.approx(0.40 * IN)
    assert spec.SPIGOT_LENGTH_MAX < geom.TUBE_STRAIGHT
    assert part.V_PLUG == pytest.approx(
        math.pi
        * (
            (geom.PLUG_DIA / 2.0) ** 2 * geom.PLUG_HEAD_LENGTH
            + (joint.PLUG_SHANK_DIA / 2.0) ** 2 * geom.PLUG_SHANK_LENGTH
        )
    )
    assert part.V_FINAL == pytest.approx(part.V_PLUG - part.V_TAP)


def test_blind_tap_stays_inside_the_head() -> None:
    assert joint.TAP_SPEC.kind.startswith("tapped")
    assert joint.TAP_SPEC.size == "#10-24"
    assert joint.TAP_SPEC.end == "blind"
    assert joint.TAP_SPEC.thread_class == "2B"
    assert joint.TAP_SPEC.depth_mm == joint.TAP_DRILL_DEPTH == pytest.approx(0.56 * IN)
    assert joint.TAP_SPEC.overrides_mm == {"ThreadDepth": joint.TAP_THREAD_DEPTH}
    assert joint.TAP_THREAD_DEPTH == pytest.approx(0.44 * IN)
    # The full drill Ø stays in the shortest head; its point stays in the plug.
    assert joint.TAP_DRILL_DEPTH_MAX <= joint.PLUG_HEAD_LENGTH_MIN
    tip = joint.TAP_DRILL_DEPTH_MAX + DRILL_POINT_H * joint.TAP_DRILL_DIA_MAX / 2.0
    assert tip < geom.PLUG_LENGTH
    assert part.V_TAP > 0.0


def test_tap_starts_on_the_end_face_centre_after_the_revolve() -> None:
    # Owner ruling 2026-11-08 (Pedro), #2144 item 11.4: a plain tap, no
    # counterbore, both depths from the end face at the origin, drilled +X.
    source = Path(part.__file__).read_text(encoding="utf-8")
    revolve = source.index('name_last_feature(adapter, "EndPlug")')
    tap = source.index('name="ThreadBore"')
    axis = source.index('name_last_feature(adapter, "SpringScrewAxis")')
    assert source.index("create_revolve") < revolve < tap < axis
    assert "Counterbore" not in source
    (call,) = _calls(part, name="wizard_holes")
    assert ast.unparse(call.args[2]) == "[[0.0, 0.0, 0.0]]"
    assert ast.unparse(call.args[3]) == "(-1.0, 0.0, 0.0)"
    keywords = {keyword.arg: ast.unparse(keyword.value) for keyword in call.keywords}
    assert keywords["placement_dims"] == "[((None, None), (None, None))]"
    assert keywords["expect_dia_mm"] == "TAP_DRILL_DIA"
    (axis_call,) = _calls(part, name="name_bore_axis")
    assert [ast.unparse(arg) for arg in axis_call.args[1:5]] == [
        "'Front Plane'",
        "0.0",
        "'Top Plane'",
        "0.0",
    ]
    assert "len(bodies) != 1" in source


def test_every_direct_db_block_restores_inference_in_finally() -> None:
    # Sketch inference is session state on the persistent seat: each block
    # that turns it off must restore it in a finally.
    tree = ast.parse(Path(part.__file__).read_text(encoding="utf-8"))

    def toggle(node: ast.AST) -> str | None:
        if (
            isinstance(node, ast.Expr)
            and isinstance(node.value, ast.Call)
            and getattr(node.value.func, "id", "") == "set_sketch_direct_db"
        ):
            return ast.unparse(node.value.args[1])
        return None

    on = 0
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
    assert on >= 1


def _recorded(module) -> set[str]:
    """Names recorded on SketchDims, literal or by the loop over its rows."""
    names = {
        call.args[0].value
        for call in _calls(module, attr="record")
        if isinstance(call.args[0], ast.Constant)
    }
    tree = ast.parse(Path(module.__file__).read_text(encoding="utf-8"))
    for loop in (node for node in ast.walk(tree) if isinstance(node, ast.For)):
        if any(
            getattr(call.func, "attr", None) == "record"
            for call in ast.walk(loop)
            if isinstance(call, ast.Call)
        ) and isinstance(loop.iter, ast.Tuple):
            names |= {
                row.elts[0].value
                for row in loop.iter.elts
                if isinstance(row, ast.Tuple) and isinstance(row.elts[0], ast.Constant)
            }
    return names


def test_profile_marks_exactly_the_printed_dimensions() -> None:
    # Head Ø and length, spigot Ø and overall length: the spigot's length is
    # their difference and prints no value of its own.
    names = {"PlugDia", "PlugHeadLength", "PlugShankDia", "PlugLength"}
    assert spec.DRAWING_DIMENSIONS == {spec.PROFILE: names}
    assert _recorded(part) == names
    assert spec.DRAWING_PRECISION_BY_NAME == {
        "PlugDia": 2,
        "PlugHeadLength": 2,
        "PlugLength": 2,
        "PlugShankDia": 3,
    }
    assert set(drawing.FRONT_KEEP) == names
    assert spec.REFERENCE_DIMENSIONS == {spec.PROFILE: frozenset({"PlugShankDia"})}
    assert spec.DIMENSION_CALLOUTS == {spec.PROFILE: {"PlugShankDia": "SEE NOTE 1"}}
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "set_dimension_precision" not in source
    assert "assert_imported_precision(" in source


def test_only_the_reference_value_is_bracketed_under_its_callout(monkeypatch) -> None:
    class Display:
        def __init__(self) -> None:
            self.ShowParenthesis = False
            self.text: dict[int, str] = {}

        def SetText(self, slot: int, text: str) -> None:
            self.text[slot] = text

        def GetText(self, slot: int) -> str:
            return self.text.get(slot, "")

    displays: dict[str, Display] = {}

    def named(_adapter, _feature, names):
        return {name: (displays.setdefault(name, Display()), None) for name in names}

    monkeypatch.setattr(part, "_named_dimensions", named)
    part._author_dimension_callouts(None)
    part._author_reference_dimensions(None)
    display = displays["PlugShankDia"]
    assert (display.GetText(1), display.GetText(2)) == ("(<MOD-DIAM>", ")")
    assert display.GetText(4) == "SEE NOTE 1"
    assert not display.ShowParenthesis


def test_one_flag_note_states_the_fit_and_the_joint() -> None:
    lines = spec.DRAWING_NOTES.splitlines()
    assert lines == [
        "1. TURN SPIGOT TO MEASURED MHA-SM-01 BORE, CLEARANCE .004-.009,",
        "   FOR ITS LOCTITE 638 BOND INTO MHA-SM-01 AT MHA-SM-00",
    ]
    # No sequence note: the sheet shows the plug alone, so it leaves the
    # bench tapped; the bond is MHA-SM-00 STEP 8 (#2315, no RV-02).
    assert "BEFORE" not in spec.DRAWING_NOTES
    declared = _config.parts("sm-gooseneck-end-plug")["machinist_exceptions"]
    assert [entry["id"] for entry in declared] == ["RV-01"]
    # Rule 7: each line ends left of the title block (x 0.216) at the sheet's
    # ~2.42 mm a character.
    assert drawing.NOTES_XY[0] + 0.00242 * max(map(len, lines)) < 0.214
    # The joint's window in plain inch steps, rounded inward at three places.
    window = "-".join(
        f"{inches:.3f}".lstrip("0")
        for inches in (
            math.ceil(round(joint.BOND_CLEARANCE_MIN / IN * 1e3, 6)) / 1e3,
            math.floor(round(joint.BOND_CLEARANCE_MAX / IN * 1e3, 6)) / 1e3,
        )
    )
    assert spec.BOND_WINDOW == window == ".004-.009"
    numbers = {line.split(".", 1)[0] for line in lines if not line.startswith(" ")}
    assert numbers == {"1"}
    printed = " ".join(spec.DIMENSION_CALLOUTS_BY_NAME.values())
    assert set(re.findall(r"SEE NOTE (\d)", printed)) <= numbers
    notes = " ".join(spec.DRAWING_NOTES.split()).upper()
    # No torch, no plating, no sleeve (owner rulings 2026-11-08, #2315).
    for word in ("BRAZE", "BAG-7", "FLUX", "PLATE", "SLEEVE", "BEND"):
        assert word not in notes
    assert "<MOD-DIAM>" not in notes and "Ø" not in notes


def test_tap_callout_states_geometry_and_its_mate_within_four_rows() -> None:
    rows = spec.TAP_CALLOUT_BELOW.splitlines()
    assert rows == ["FOR MHA-SM-VN-56", "ENGAGEMENT .220 MIN (1.16D)"]
    assert max(map(len, rows)) <= 39
    assert spec.TAP_CALLOUT_PRECISION == {
        "hw-tapdrldia": 3,
        "hw-threaddepth": 2,
        "hw-tapdrldepth": 2,
    }
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    for call in (
        "_require_saved_tap(adapter.currentModel)",
        "omit_title_block_thread_class(tap_callout",
        "set_hole_callout_precision(",
        "_set_tap_callout_below(tap_callout, TAP_CALLOUT_BELOW)",
    ):
        assert call in source
    for token in ("add_feature_control_frame", "add_datum_feature", "create_section_view"):
        assert token not in source


def test_sheet_layout_keeps_views_and_text_apart() -> None:
    keep = drawing.FRONT_KEEP
    half = geom.PLUG_DIA / 2.0 * drawing._S
    end_right = drawing.END_CENTER[0] + half
    # The head Ø stands between the end view and the end face.
    assert end_right + 0.008 < keep["PlugDia"][0] < drawing.END_FACE_X
    # The spigot Ø stands right of the spigot, short of the isometric.
    assert drawing.SPIGOT_END_X < keep["PlugShankDia"][0] < drawing.ISO_CENTER[0] - 0.050
    # The lengths stack over the part, the overall outermost.
    assert drawing.TOP_Y < keep["PlugHeadLength"][1] < keep["PlugLength"][1]
    # The tap callout and the views stay inside the border, the notes under
    # the views and left of the title block.
    assert drawing.TAP_CALLOUT_XY[1] < 0.266
    # The centred callout's widest line (~0.066) clears the left border
    # (~0.015) and ends short of the side view's stacked lengths.
    assert drawing.TAP_CALLOUT_XY[0] - 0.033 > 0.020
    assert drawing.TAP_CALLOUT_XY[0] + 0.033 < drawing.END_FACE_X - 0.010
    assert drawing.NOTES_XY[1] < drawing.FRONT_CENTER[1] - half - 0.020
    assert drawing.SPIGOT_END_X - drawing.END_FACE_X == pytest.approx(
        geom.PLUG_LENGTH * drawing._S
    )


@pytest.fixture
def saved_tap(monkeypatch):
    """Read-only saved feature with independently specified native tap metadata."""
    monkeypatch.setattr(drawing, "_early_bound", lambda value, _interface: value)
    definition = SimpleNamespace(
        FastenerSize="#10-24",
        ThreadClass="2B",
        ThreadEndCondition=0,  # blind
        EndCondition=0,
        TapDrillDiameter=0.003797,  # native model length units are metres
        TapDrillDepth=0.014224,  # .56 in
        ThreadDepth=0.011176,  # .44 in
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
        ("EndCondition", 1, "EndCondition"),
        ("TapDrillDiameter", 0.0, "tap drill"),
        ("TapDrillDiameter", 0.003791, "tap drill"),
        ("TapDrillDiameter", math.nan, "tap drill"),
        ("TapDrillDepth", 0.0141, "tap drill depth"),
        ("ThreadDepth", 0.0113, "thread depth"),
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


def test_the_part_carries_every_property_its_drawing_requires(monkeypatch) -> None:
    import _drawing_marks
    import _part_properties

    (call,) = _calls(drawing, name="read_required_properties")
    required = ast.literal_eval(
        next(k.value for k in call.keywords if k.arg == "required")
    )
    carried = dict(_part_properties.part_properties(part.PART_NAME))
    stamped: dict[str, str] = {}
    monkeypatch.setattr(
        _drawing_marks,
        "apply_custom_properties",
        lambda _adapter, props: stamped.update(props),
    )
    _drawing_marks.apply_drawing_properties(
        None,
        part.PART_NAME,
        {
            "Manufacturing Notes": spec.DRAWING_NOTES,
            "Isometric View Note": spec.ISOMETRIC_VIEW_NOTE,
        },
    )
    carried.update(stamped)
    missing = [name for name in required if not str(carried.get(name) or "").strip()]
    assert missing == []
    assert set(required) <= set(part._SAVED_DRAWING_PROPERTIES)


def _mass_adapter(volume: float):
    async def get_mass_properties():
        return SimpleNamespace(
            is_success=True, error=None, data=SimpleNamespace(volume=volume)
        )

    return SimpleNamespace(get_mass_properties=get_mass_properties)


@pytest.mark.parametrize("volume", [math.nan, math.inf, -math.inf])
def test_build_stops_on_a_non_finite_volume_read(volume):
    adapter = _mass_adapter(volume)
    with pytest.raises(RuntimeError, match="non-finite volume"):
        asyncio.run(part._volume(adapter))
    with pytest.raises(RuntimeError, match="non-finite volume|volume -?inf"):
        asyncio.run(part._volume_check(adapter, "end plug", 100.0, 1.0))
    assert asyncio.run(part._volume(_mass_adapter(100.0))) == 100.0
