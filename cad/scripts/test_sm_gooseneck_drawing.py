"""Offline contracts for MHA-SM-01, the bent gooseneck tube, and its sheet."""

from __future__ import annotations

import ast
import asyncio
import math
from pathlib import Path
import re
from types import SimpleNamespace

import pytest

import _config
from _machinist_review_mode import MachinistReviewMode
import build_sm_gooseneck as part
import draw_sm_gooseneck as drawing
import sm_gooseneck_geom as geom
import sm_gooseneck_spec as spec

_SOURCES = (part, spec, drawing)


def _tree(module) -> ast.Module:
    return ast.parse(Path(module.__file__).read_text(encoding="utf-8"))


def _calls(module, *, name: str | None = None, attr: str | None = None) -> list:
    return [
        node
        for node in ast.walk(_tree(module))
        if isinstance(node, ast.Call)
        and (
            (name is not None and getattr(node.func, "id", None) == name)
            or (attr is not None and getattr(node.func, "attr", None) == attr)
        )
    ]


def _recorded_equations(module) -> dict[str, str]:
    return {
        call.args[0].value: call.args[1].value
        for call in _calls(module, attr="record")
        if len(call.args) == 2 and isinstance(call.args[0], ast.Constant)
    }


def _global_equations(module) -> dict[str, str]:
    return {
        call.args[1].value: call.args[2].value
        for call in _calls(module, name="set_global")
        if all(isinstance(arg, ast.Constant) for arg in call.args[1:3])
    }


def _globals_mm() -> dict[str, float]:
    """The part's globals in model mm: the numeric ones as the build sets
    them, the equations evaluated on those."""
    values = {
        "TubeDia": geom.TUBE_DIA,
        "WallT": geom.WALL_T,
        "LegTop": geom.LEG_TOP,
        "LegBottom": geom.LEG_BOTTOM,
        "BendR": geom.BEND_R,
        "TubeEndX": geom.TUBE_END_X,
    }
    for name, expression in _global_equations(part).items():
        values[name] = _evaluate(expression, values)
    return values


def _evaluate(expression: str, values: dict[str, float]) -> float:
    literal = re.sub(r'"(\w+)"', lambda m: repr(values[m.group(1)]), expression)
    return eval(literal)  # noqa: S307 -- the builder's own literal


def test_gooseneck_is_one_bent_tube_ending_at_its_faced_arm_end() -> None:
    # Owner rulings 2026-11-08 (Pedro), #2315: the bent tube alone; its arm
    # end is the end plug's (MHA-SM-05) head length short of the end face.
    assert geom.TUBE_END_X - geom.ARM_END_X == pytest.approx(geom.PLUG_HEAD_LENGTH)
    assert geom.TUBE_STRAIGHT == pytest.approx(-geom.TUBE_END_X - geom.BEND_R)
    assert geom.TUBE_STRAIGHT > 0.0
    assert part.V_FINAL == pytest.approx(part.V_LEG + part.V_BEND + part.V_ARM)
    assert part.V_ARM == pytest.approx(part.RING_AREA * geom.TUBE_STRAIGHT)
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "len(bodies) != 1" in source
    # No end piece, tap, screw axis or sleeve: nothing is revolved, drilled or
    # given an assembly axis on the tube.
    for name in ("create_revolve", "wizard_holes", "name_bore_axis", "add_line_chain"):
        assert not _calls(part, name=name) and not _calls(part, attr=name), name
    features = {
        call.args[1].value
        for call in _calls(part, name="name_last_feature")
        if isinstance(call.args[1], ast.Constant)
    }
    assert features == {
        "LegProfile",
        "Leg",
        "BendPath",
        "BendProfile",
        "BendProfileFlipped",
        "BendArmSweep",
        "StationReference",
        "TubeOdReference",
        "OverallReference",
    }


def test_no_plug_tap_sleeve_or_braze_terms_remain() -> None:
    banned = re.compile(r"\b(?:SLEEVE|BRAZE|PLUG|TAP)_")
    for module in _SOURCES:
        text = Path(module.__file__).read_text(encoding="utf-8")
        assert not banned.findall(text), module.__name__
    for module in (part, spec):
        names = {node.id for node in ast.walk(_tree(module)) if isinstance(node, ast.Name)}
        assert not {name for name in names if banned.match(name)}
    printed = " ".join(
        (spec.DRAWING_NOTES, *spec.DIMENSION_CALLOUTS_BY_NAME.values())
    ).upper()
    for word in ("BRAZE", "BAG-7", "LOCTITE", "PLATE", "MASK", "SLEEVE", "TAP", "PLUG"):
        assert word not in printed, word


def test_globals_drive_the_built_arm_and_overall_sizes() -> None:
    values = _globals_mm()
    assert values["ArmY"] == pytest.approx(geom.ARM_Y)
    assert values["ArmStraight"] == pytest.approx(geom.TUBE_STRAIGHT)
    equations = _recorded_equations(part)
    # The swept arm and the printed arm straight run to the faced arm end.
    assert equations["TubeStraight"] == equations["ArmStraight"] == '"ArmStraight"'
    height = geom.ARM_Y + geom.TUBE_DIA / 2.0 - geom.LEG_BOTTOM
    reach = geom.TUBE_DIA / 2.0 - geom.TUBE_END_X
    assert _evaluate(equations["OverallHeight"], values) == pytest.approx(height)
    assert _evaluate(equations["OverallReach"], values) == pytest.approx(reach)
    assert _evaluate(equations["LegLength"], values) == pytest.approx(geom.LEG_LENGTH)
    assert _evaluate(equations["OverallFootRadius"], values) == pytest.approx(
        geom.TUBE_DIA / 2.0
    )
    assert height / 25.4 == pytest.approx(19.65)
    assert reach / 25.4 == pytest.approx(3.719, abs=0.0005)
    assert geom.TUBE_STRAIGHT / 25.4 == pytest.approx(0.469, abs=0.0005)
    # The reference sketches are hidden in the part and shown only by the
    # elevation.
    blanked = {call.args[1].value for call in _calls(part, name="blank_sketch")}
    assert blanked == {"StationReference", "TubeOdReference", "OverallReference"}


def test_every_direct_db_block_restores_inference_in_finally() -> None:
    # Sketch inference is session state on the persistent seat: each block
    # that turns it off must restore it even when a native segment is
    # rejected, so every True is followed at once by a try whose finally
    # restores it, and nothing restores it outside a finally.
    tree = _tree(part)

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


def test_sheet_places_every_marked_dimension_at_its_places() -> None:
    marked = {name for names in spec.DRAWING_DIMENSIONS.values() for name in names}
    assert marked == {
        "LegLength",
        "ArmStraight",
        "TubeOdRef",
        "OverallHeight",
        "OverallReach",
        "BendRadius",
    }
    assert set(drawing.FRONT_KEEP) == marked
    assert set(spec.DRAWING_PRECISION_BY_NAME) == marked
    assert spec.DRAWING_PRECISION_BY_NAME == {
        "LegLength": 1,
        "BendRadius": 1,
        "ArmStraight": 2,
        "OverallHeight": 2,
        "OverallReach": 2,
        "TubeOdRef": 3,
    }
    for feature, by_name in spec.DIMENSION_CALLOUTS.items():
        assert set(by_name) <= spec.DRAWING_DIMENSIONS[feature]
    assert spec.DIMENSION_CALLOUTS_BY_NAME == {
        "BendRadius": "TUBE CENTERLINE",
        "TubeOdRef": ".065 WALL STOCK",
    }


def test_references_and_the_governing_arm_size() -> None:
    # The tube's stock Ø and the overall height are references; the arm end
    # is sawn and faced after the bend (#2315), so the overall reach to real
    # faces governs and the arm straight to the bend's tangent is reference.
    assert spec.REFERENCE_DIMENSIONS == {
        "TubeOdReference": frozenset({"TubeOdRef"}),
        "StationReference": frozenset({"ArmStraight"}),
        "OverallReference": frozenset({"OverallHeight"}),
    }
    for feature, names in spec.REFERENCE_DIMENSIONS.items():
        assert names <= spec.DRAWING_DIMENSIONS[feature]
    referenced = set().union(*spec.REFERENCE_DIMENSIONS.values())
    assert {"LegLength", "BendRadius", "OverallReach"}.isdisjoint(referenced)
    # The tube Ø's reference line runs on the leg, below the bend tangent.
    low = spec.TUBE_OD_REF_Y - spec.TUBE_OD_REF_SPAN / 2.0
    high = spec.TUBE_OD_REF_Y + spec.TUBE_OD_REF_SPAN / 2.0
    assert geom.LEG_BOTTOM < low < high < geom.LEG_TOP


def test_only_the_reference_value_is_bracketed_when_a_callout_rides_it(
    monkeypatch,
) -> None:
    # Machinist review of 6b67c9516: ShowParenthesis bracketed a whole block,
    # so its callout read as reference.
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
    part._author_reference_dimensions(None)
    assert set(displays) == {"TubeOdRef", "ArmStraight", "OverallHeight"}
    tube = displays["TubeOdRef"]
    assert (tube.GetText(1), tube.GetText(2)) == ("(<MOD-DIAM>", ")")
    assert not tube.ShowParenthesis
    for name in ("ArmStraight", "OverallHeight"):
        assert displays[name].ShowParenthesis
        assert displays[name].text == {}


def test_note_states_the_bend_acceptance_without_method_or_sizes() -> None:
    lines = spec.DRAWING_NOTES.splitlines()
    assert 1 <= len(lines) <= 4
    assert all(re.match(r"\d\. ", line) for line in lines)
    notes = " ".join(spec.DRAWING_NOTES.split())
    assert "OVALITY 5% MAX" in notes and "NO KINKS" in notes
    # Rule 7 (machinist review of the v49 release): the short acceptance
    # prints at its leader on the bend, the part's note without its number
    # and "BEND:", so no numbered note stands alone in the corner.
    acceptance = " ".join(drawing.BEND_ACCEPTANCE.split())
    assert notes == f"1. BEND: {acceptance}"
    assert len(drawing.BEND_ACCEPTANCE.splitlines()) <= 2
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' not in source
    # Geometry, not method (rule 7): no tool, no bend order, no tail.
    for word in ("DIE", "SAW", "TAIL", "FACE", "THEN", "JOIN", "CURE"):
        assert word not in notes, word
    # The title block owns material and finish (rule 2).
    for word in ("4130", "POLISH", "OIL", "WAX"):
        assert word not in notes, word
    # Sizes and tolerances are native model dimensions, never note text.
    assert re.search(r"\b\d+\.\d{1,2}\b", notes) is None, notes
    assert "<MOD-DIAM>" not in notes and "Ø" not in notes
    # A callout carries at most two lines of words (rule 7).
    for name, text in spec.DIMENSION_CALLOUTS_BY_NAME.items():
        assert len(text.splitlines()) <= 2, name


def test_title_block_material_and_finish_come_from_the_registry_row() -> None:
    row = _config.parts("sm-gooseneck")
    assert row["number"] == "MHA-SM-01"
    assert row["drawing_unit"] == spec.UNIT == geom.SHEET_UNIT == "in"
    assert "OnlineMetals 7322" in row["material_specification"]
    finish = str(row["finish"]).lower()
    assert "polished bare" in finish and "oil or wax" in finish
    assert "machinist_exceptions" not in row
    # apply_drawing_properties stamps the row's fields; the build passes only
    # the sheet's own notes.
    properties = _calls(part, name="apply_drawing_properties")
    assert len(properties) == 1
    extra = ast.literal_eval(
        ast.unparse(properties[0].args[2]).replace("DRAWING_NOTES", "'n'").replace(
            "ISOMETRIC_VIEW_NOTE", "'i'"
        )
    )
    assert set(extra) == {"Manufacturing Notes", "Isometric View Note"}


def test_sheet_is_the_elevation_and_isometric_only() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    for token in (
        "create_section_view",
        "CreateDetailViewAt",
        "add_native_hole_callout",
        '"*Left"',
        "Crop2",
        "FaceHatch",
    ):
        assert token not in source, token
    views = [
        call.args[2].value
        for call in _calls(drawing, name="place_view")
        if isinstance(call.args[2], ast.Constant)
    ]
    assert views == ["*Front", "*Isometric"]
    assert drawing.MACHINIST_REVIEW is MachinistReviewMode.ENFORCE
    assert spec.ISOMETRIC_VIEW_NOTE == "ISOMETRIC VIEW SCALE 1:4"
    assert drawing.ISO_SCALE == (1, 4)


def test_elevation_dimensions_stand_clear_of_each_other_and_the_title_block() -> None:
    keep = drawing.FRONT_KEEP
    height_x, height_y = keep["OverallHeight"]
    reach_x, reach_y = keep["OverallReach"]
    # Outermost on the leg's right, short of the title block's left edge
    # (x 0.216) and the isometric, its text away from the leg length's.
    assert keep["LegLength"][0] + 0.015 <= height_x <= 0.216 - 0.010
    assert height_x <= drawing.ISO_CENTER[0] - 0.030
    assert abs(height_y - keep["LegLength"][1]) >= 0.015
    assert drawing.FOOT_Y < height_y < drawing._front_y(geom.ARM_Y + geom.TUBE_DIA / 2)
    # Over the arm straight, inside the sheet's top border.
    assert keep["ArmStraight"][1] + 0.005 <= reach_y <= 0.258
    assert drawing.ARM_END_X < reach_x < drawing._front_x(geom.TUBE_DIA / 2)
    # The arm straight's text (~12 mm wide at (.47)) ends one text clearance
    # (1.78 mm) left of the faced arm end's shared extension line.
    assert keep["ArmStraight"][0] + 0.012 / 2 + 0.00178 <= drawing.ARM_END_X
    # The tube Ø crosses the leg on its left, level with the leg length.
    assert keep["TubeOdRef"][0] < drawing.LEG_AXIS_X < keep["LegLength"][0]
    assert keep["TubeOdRef"][1] == keep["LegLength"][1]
    # The elevation's foot stands above the title block's top (y 0.066).
    assert drawing.FOOT_Y > 0.066


def test_bend_acceptance_leader_lands_on_the_bend_clear_of_the_tube() -> None:
    tip_x, tip_y = drawing.BEND_NOTE_TIP
    centre = (drawing._front_x(-geom.BEND_R), drawing._front_y(geom.LEG_TOP))
    inner_r = (geom.BEND_R - geom.TUBE_DIA / 2.0) * drawing._S
    assert math.dist((tip_x, tip_y), centre) == pytest.approx(inner_r)
    assert tip_x > centre[0] and tip_y > centre[1]
    # The two-row block (~2.42 mm a character, ~9 mm tall) stands inside
    # the bend: left of the leg's inner edge, under the arm, over the tube
    # Ø's text and right of the sheet's left border.
    left, top = drawing.BEND_NOTE_XY
    right = left + 0.00242 * max(map(len, drawing.BEND_ACCEPTANCE.splitlines()))
    leg_inner = drawing.LEG_AXIS_X - geom.TUBE_DIA / 2.0 * drawing._S
    assert 0.016 < left and right + 0.005 < leg_inner
    assert top < drawing.ARM_AXIS_Y - geom.TUBE_DIA / 2.0 * drawing._S - 0.020
    assert top - 0.009 > drawing.FRONT_KEEP["TubeOdRef"][1] + 0.010


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
        asyncio.run(part._volume_check(adapter, "bend + arm", 100.0, 1.0))
    assert asyncio.run(part._volume(_mass_adapter(100.0))) == 100.0
