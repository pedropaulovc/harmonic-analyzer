"""Offline contracts for MHA-SM-01, the bent gooseneck tube, and its sheet."""

from __future__ import annotations

import ast
import math
from pathlib import Path
import re

import pytest

import _config
from _machinist_review_mode import MachinistReviewMode
import _shop_equipment
import build_sm_gooseneck as part
import draw_sm_gooseneck as drawing
from machinist_exceptions import load_exceptions
import sm_gooseneck_geom as geom
import sm_gooseneck_spec as spec

_SOURCES = (part, spec, drawing)


def _tree(module) -> ast.Module:
    return ast.parse(Path(module.__file__).read_text(encoding="utf-8"))


def test_gooseneck_is_one_bent_tube_ending_at_its_faced_arm_end() -> None:
    # Owner rulings 2026-11-08 (Pedro), #2315: the bent tube alone; its arm
    # end is the end plug's (MHA-SM-05) head length short of the end face.
    assert geom.TUBE_END_X - geom.ARM_END_X == pytest.approx(geom.PLUG_HEAD_LENGTH)
    assert geom.TUBE_STRAIGHT == pytest.approx(-geom.TUBE_END_X - geom.BEND_R)
    assert geom.TUBE_STRAIGHT > 0.0
    assert part.V_FINAL == pytest.approx(part.V_LEG + part.V_BEND + part.V_ARM)
    assert part.V_ARM == pytest.approx(part.RING_AREA * geom.TUBE_STRAIGHT)


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
    assert geom.TUBE_STRAIGHT / 25.4 == pytest.approx(0.469, abs=0.0005)


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
    assert set(spec.DIMENSION_CALLOUTS_BY_NAME) == {"BendRadius", "TubeOdRef"}
    assert spec.DIMENSION_CALLOUTS_BY_NAME["BendRadius"] == "TUBE CENTERLINE"
    # The stock wall is the supplier's size: its value prints only as a
    # bracketed reference, never as a bare (toleranced) three-place size.
    wall = spec.DIMENSION_CALLOUTS_BY_NAME["TubeOdRef"]
    stock_wall = f"{geom.WALL_T / geom.MM_PER_IN:.3f}".removeprefix("0")
    assert f"({stock_wall})" in wall and "STOCK" in wall
    assert wall.replace(f"({stock_wall})", "").count(stock_wall) == 0


def test_references_and_the_governing_end_sizes() -> None:
    # Owner ruling 2026-11-14 (Pedro), #2401: only where the tube's two ends
    # finish matters.  Both ends are sawn and faced after the bend, so the
    # overall height (foot face to arm top) and reach (faced arm end to the
    # leg's outer side) govern; the bend radius and the lengths to its
    # tangents are references, as is the stock Ø.
    assert spec.REFERENCE_DIMENSIONS == {
        "TubeOdReference": frozenset({"TubeOdRef"}),
        "StationReference": frozenset({"ArmStraight", "LegLength"}),
        "BendPath": frozenset({"BendRadius"}),
    }
    for feature, names in spec.REFERENCE_DIMENSIONS.items():
        assert names <= spec.DRAWING_DIMENSIONS[feature]
    referenced = set().union(*spec.REFERENCE_DIMENSIONS.values())
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert marked - referenced == {"OverallHeight", "OverallReach"}
    # The reach sits at the title block's .XX row.  The height prints at two
    # places (a one-place tie) but the foot only has to leave the leg
    # spanning the hub, so its own band is looser than the .XX row's.
    assert spec.DRAWING_PRECISION_BY_NAME["OverallReach"] == 2
    assert spec.DRAWING_PRECISION_BY_NAME["OverallHeight"] == 2
    assert spec.OVERALL_HEIGHT_TOLERANCE_MM > 0.01 * geom.MM_PER_IN
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
    assert set(displays) == {"TubeOdRef", "ArmStraight", "LegLength", "BendRadius"}
    tube = displays["TubeOdRef"]
    assert (tube.GetText(1), tube.GetText(2)) == ("(<MOD-DIAM>", ")")
    assert not tube.ShowParenthesis
    # A custom prefix replaces SolidWorks' own R, so the radius carries it.
    radius = displays["BendRadius"]
    assert (radius.GetText(1), radius.GetText(2)) == ("(R", ")")
    assert not radius.ShowParenthesis
    for name in ("ArmStraight", "LegLength"):
        assert displays[name].ShowParenthesis
        assert displays[name].text == {}


def test_note_states_the_bend_acceptance_without_method_or_sizes() -> None:
    lines = spec.DRAWING_NOTES.splitlines()
    assert 1 <= len(lines) <= 4
    assert all(re.match(r"\d\. ", line) for line in lines)
    notes = " ".join(spec.DRAWING_NOTES.split())
    # #2401: NO KINKS only; no fit or load at the bend needs an ovality limit.
    assert "NO KINKS" in notes and "OVALITY" not in notes and "%" not in notes
    # Rule 7 (machinist review of the v49 release): the short acceptance
    # prints at its leader on the bend, the part's note without its number
    # and "BEND:", so no numbered note stands alone in the corner.
    acceptance = " ".join(drawing.BEND_ACCEPTANCE.split())
    assert notes == f"1. BEND: {acceptance}"
    assert len(drawing.BEND_ACCEPTANCE.splitlines()) <= 2
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
    # Owner ruling 2026-11-17 (Pedro): the reach's .XX is the plumb station
    # of the counter spring, accepted against the over-specification finding.
    (exception,) = load_exceptions(_config.CONFIG_DIR, "sm-gooseneck", "part")
    assert exception.kind == "accept"
    assert "3.72" in exception.where
    assert '"3.72 at .XX stays; it plumbs the vertical spring"' in exception.reason


def test_shop_stock_row_covers_the_bent_tube_and_its_tail() -> None:
    equipment = _shop_equipment.load()
    (row,) = [
        row
        for row in equipment["stock"].values()
        if "MHA-SM-01" in row.get("note", "") and row.get("form") == "round_tube"
    ]
    assert "OnlineMetals part 7322" in row["cite"][0]
    assert row["od_mm"] == pytest.approx(geom.TUBE_DIA)
    assert row["wall_mm"] == pytest.approx(geom.WALL_T)
    # Leg, the bend's centreline arc and the arm straight, plus the owner's
    # ~2 in tail at the arm end (#2315) and ~1 in to face the foot (both ends
    # are faced after the bend, #2401), inside the supplier's -1/8 in cut
    # tolerance, and about 23 in left over for a trial bend to 90° on the form,
    # long enough to pull by hand like the blank (owner ruling 2026-11-22,
    # option A, https://github.com/pedropaulovc/harmonic-analyzer/issues/2401#issuecomment-7085840331, superseding
    # #2401's 36 in).
    developed = geom.LEG_LENGTH + math.pi / 2.0 * geom.BEND_R + geom.TUBE_STRAIGHT
    part_length = developed + 3.0 * geom.MM_PER_IN
    assert row["length_mm"] == pytest.approx(48.0 * geom.MM_PER_IN)
    assert row["length_mm"] - 3.175 - part_length >= 22.0 * geom.MM_PER_IN
    # The form it is bent on is a shop record, made in the shop, not bought.
    form = equipment["fixtures"]["sm-gooseneck-bend-form"]
    assert form["supply"] == "shop_made" and form["status"] == "to_make"


def test_sheet_is_the_elevation_and_isometric_only() -> None:
    assert drawing.MACHINIST_REVIEW is MachinistReviewMode.ENFORCE
    assert spec.ISOMETRIC_VIEW_NOTE == "ISOMETRIC VIEW SCALE 1:4"
    assert drawing.ISO_SCALE == (1, 4)
    # The pictorial looks into the faced arm end (part -X), so its open bore
    # shows the tube the (.065) WALL STOCK callout names.
    assert spec.ISOMETRIC_OCTANT == (-1, 1, 1)
    for module in (part, drawing):
        names = {
            node.id for node in ast.walk(_tree(module)) if isinstance(node, ast.Name)
        }
        assert "ISOMETRIC_OCTANT" in names, module.__name__
    assert '"*Isometric"' not in Path(drawing.__file__).read_text(encoding="utf-8")


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


def test_bend_acceptance_leader_lands_on_the_bend_clear_of_the_radius_line() -> None:
    tip_x, tip_y = drawing.BEND_NOTE_TIP
    centre = (drawing._front_x(-geom.BEND_R), drawing._front_y(geom.LEG_TOP))
    inner_r = (geom.BEND_R - geom.TUBE_DIA / 2.0) * drawing._S
    assert math.dist((tip_x, tip_y), centre) == pytest.approx(inner_r)
    assert tip_x > centre[0] and tip_y > centre[1]
    # The one-row block (~2.65 mm a glyph; farm run 20261112T194827228Z
    # printed "OVALITY 5% MAX," 39.4 mm wide) stands left of the faced arm end
    # and under the arm.
    left, top = drawing.BEND_NOTE_XY
    right = left + 0.00265 * max(map(len, drawing.BEND_ACCEPTANCE.splitlines()))
    arm_inner = drawing.ARM_AXIS_Y - geom.TUBE_DIA / 2.0 * drawing._S
    assert 0.016 < left and right + 0.003 < drawing.ARM_END_X
    assert top + 0.004 < arm_inner
    assert top - 0.010 > drawing.FRONT_KEEP["TubeOdRef"][1] + 0.010
    # The R3.0 dimension's line runs in from the leg's tangent toward the
    # bend's centre (the run's leader 35° up crossed it, machinist review
    # r1-r3): the leader, from its start to the tip, stays well above it.
    start_y = top - 0.006
    assert min(start_y, tip_y) > centre[1] + 0.010
