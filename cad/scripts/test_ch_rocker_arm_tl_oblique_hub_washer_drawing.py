"""Offline contracts for the MHA-CH-06-TL-52 oblique-trammel hub top-hat washer."""

from __future__ import annotations

import ast
import math
from pathlib import Path

import pytest

import _config
import build_ch_rocker_arm_tl_oblique_hub_washer as part
import ch_rocker_arm_tl_oblique_hub_washer_spec as spec
import ch_rocker_strap_notes as strap_notes
import ch_rocker_strap_spec as strap
import draw_ch_rocker_arm_tl_oblique_hub_washer as drawing
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS, model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME
from _inch_wall_limits import WALL_TARGET_MM
from _machinist_review_mode import MachinistReviewMode
from _mcmaster_91251a197 import DIMS as HUB_SCREW
from _printed_tolerance import edge_break_chamfer_mm, inside_corner_radius_mm
from ch_rocker_hub_fit import STRAP_HOLE_BAND

STEM = "ch-rocker-arm-tl-oblique-hub-washer"
INCH = 25.4
# ASME B18.3 #8 SHCS underhead fillet, largest transition diameter (.188 in).
SCREW_FILLET_DIA_MAX = 0.188 * INCH


def test_registry_row_is_the_turned_brass_washer() -> None:
    row = _config.parts(STEM)
    assert row["number"] == spec.NUMBER == "MHA-CH-06-TL-52"
    assert int(row["quantity"]) == spec.QUANTITY == 1
    assert row["drawing_unit"] == spec.UNIT == "in"
    assert "C36000" in row["material_specification"]
    assert "13/64" in row["process"] and "one chucking" in row["process"]
    # A literal, so verify's static PART_NAME scan registers the build.
    assert part.PART_NAME == spec.STEM == STEM
    assert part.MATERIAL == "Brass"


def test_sheet_is_registered_and_enforced() -> None:
    sheet = DRAWINGS_BY_NAME["ch_rocker_arm_tl_oblique_hub_washer"]
    assert drawing.SPEC is sheet
    assert sheet.script == Path(drawing.__file__).resolve()
    assert sheet.source_kind == "part"
    assert drawing.MACHINIST_REVIEW is MachinistReviewMode.ENFORCE
    assert sheet.script_name in PRECISION_MIGRATED_DRAWINGS


def test_owner_r4_top_hat_sizes() -> None:
    # Owner R4 rulings 2026-11-07: literal Ø11 flange, Ø9.95 ±.05 mm spigot
    # about .35 mm long, 13/64 drilled bore.
    assert spec.OD == 11.0
    assert spec.THICK == pytest.approx(0.06 * INCH)
    assert spec.SPIGOT_DIA == 9.95
    assert spec.SPIGOT_DIA_OWNER_LIMITS == (9.90, 10.00)
    assert spec.SPIGOT_LENGTH == pytest.approx(0.014 * INCH)
    assert abs(spec.SPIGOT_LENGTH - 0.35) < 0.01
    assert spec.BORE_DRILL == "13/64"
    assert spec.ID == pytest.approx(13.0 / 64.0 * INCH)
    assert spec.HEIGHT == pytest.approx(spec.THICK + spec.SPIGOT_LENGTH)


def test_only_the_spigot_carries_an_explicit_band_inside_the_owners() -> None:
    # Ø.3917 ±.0019 prints wholly inside 9.90-10.00 mm; every other size
    # takes a title-block row.
    assert model_toleranced_dimensions(part) == {
        ("WasherProfile", "SpigotDia"): "SPIGOT_DIA_TOL",
    }
    assert spec.SPIGOT_DIA_TOL == pytest.approx(0.0019 * INCH)
    assert spec.SPIGOT_DIA_LIMITS == pytest.approx((9.90092, 9.99744))
    low, high = spec.SPIGOT_DIA_OWNER_LIMITS
    assert low <= spec.SPIGOT_DIA_LIMITS[0] < spec.SPIGOT_DIA_LIMITS[1] <= high
    assert spec.OD_LIMITS == pytest.approx((10.8712, 11.1252))
    assert spec.THICK_LIMITS == pytest.approx((1.270, 1.778))
    assert spec.SPIGOT_LENGTH_LIMITS == pytest.approx((0.2286, 0.4826))
    assert spec.BORE_LIMITS == pytest.approx((5.1562, 5.2578))


def test_spigot_locates_loose_in_mains_strap_hole() -> None:
    # The product interface is main's unchanged Ø.4000 +.0005/0 strap hole.
    assert spec.STRAP_HOLE_LIMITS == pytest.approx(
        (strap.HOLE_DIA + STRAP_HOLE_BAND[1], strap.HOLE_DIA + STRAP_HOLE_BAND[0])
    )
    assert spec.STRAP_HOLE_LIMITS == pytest.approx((10.16, 10.1727))
    assert spec.SPIGOT_FLOAT_MIN > 0.0
    assert spec.SPIGOT_FLOAT_MAX == pytest.approx((10.1727 - 9.90092) / 2.0)
    callout = spec.DIMENSION_CALLOUTS["SpigotDia"]
    assert spec.STRAP_NUMBER == strap.NUMBER == "MHA-CH-13"
    assert f"STRAP {strap.NUMBER}" in callout
    assert "(.4000-.4005 REF)" in callout


def test_local_edge_limits_keep_a_cylindrical_locating_land() -> None:
    # The title block's default break and inside corner would each consume
    # the shortest .014 spigot, so both are overridden on the sheet.
    assert edge_break_chamfer_mm(unit=spec.UNIT) >= spec.SPIGOT_LENGTH_LIMITS[0]
    assert inside_corner_radius_mm(unit=spec.UNIT) > spec.SPIGOT_LENGTH_LIMITS[1]
    assert spec.FLANGE_EDGE_BREAK_MAX == pytest.approx(0.005 * INCH)
    assert spec.SPIGOT_ROOT_RADIUS_MAX == pytest.approx(0.003 * INCH)
    # The root fillet stays inside the sharp hole edge: the flange seats flat
    # with the largest spigot centred in the smallest hole.
    assert spec.SPIGOT_DIA_LIMITS[1] + 2.0 * spec.SPIGOT_ROOT_RADIUS_MAX < (
        spec.STRAP_HOLE_LIMITS[0]
    )
    assert spec.ROOT_SEAT_CLEARANCE_MIN == pytest.approx(
        (10.16 - 9.99744) / 2.0 - 0.0762
    )
    assert spec.SPIGOT_END_EDGE_BREAK_MAX == 0.0
    # The strap prints both hub-hole edges sharp: no entry break to charge.
    assert "BOTH EDGES SHARP" in strap_notes.HOLE_EDGE_CALLOUT
    assert spec.STRAP_HOLE_ENTRY_BREAK_MAX == 0.0
    assert spec.SPIGOT_LAND_MIN == pytest.approx(
        spec.SPIGOT_LENGTH_LIMITS[0] - spec.SPIGOT_ROOT_RADIUS_MAX
    )
    assert spec.SPIGOT_LAND_MIN > 0.0
    od = spec.DIMENSION_CALLOUTS["WasherOd"]
    assert od.splitlines()[-1] == "BREAK EDGES .005 MAX"
    length = spec.DIMENSION_CALLOUTS["SpigotLength"]
    assert "END EDGE SHARP, NO BURR" in length
    assert "ROOT R.003 MAX: SEATS" in length
    assert "FLAT" in length
    assert "LOCATING LAND" in length


def test_bore_clears_the_8_32_shcs_and_its_fillet() -> None:
    assert spec.DIMENSION_CALLOUTS["WasherBore"] == "13/64 DRILL THRU"
    assert spec.BORE_LIMITS[0] > SCREW_FILLET_DIA_MAX > HUB_SCREW.major_dia
    assert spec.OD_LIMITS[0] > HUB_SCREW.head_dia
    assert spec.WALL_MIN >= WALL_TARGET_MM
    assert spec.WALL_MIN == pytest.approx(
        (spec.SPIGOT_DIA_LIMITS[0] - spec.BORE_LIMITS[1]) / 2.0
    )


def test_od_keeps_its_xxx_row_for_the_cutter_floor_and_says_so() -> None:
    assert spec.OD_PLACES == 3
    assert spec.CUTTER_CLEARANCE_MIN == 1.5
    od = spec.DIMENSION_CALLOUTS["WasherOd"]
    assert "1.5 MM MIN" in od and "STRAP CUTTER" in od and spec.JIG_NUMBER in od


def test_every_marked_dimension_has_one_view_and_model_places() -> None:
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert set(drawing.FRONT_KEEP) | set(drawing.RIGHT_KEEP) == marked
    assert not set(drawing.FRONT_KEEP) & set(drawing.RIGHT_KEEP)
    assert set(drawing.FRONT_KEEP) == spec.DRAWING_DIMENSIONS["BoreProfile"]
    assert set(drawing.RIGHT_KEEP) == spec.DRAWING_DIMENSIONS["WasherProfile"]
    assert spec.DRAWING_PRECISION_BY_NAME == {
        "WasherOd": 3,
        "WasherThickness": 2,
        "SpigotDia": 4,
        "SpigotLength": 3,
        "WasherBore": 3,
    }
    assert set(spec.DIMENSION_CALLOUTS) <= marked
    assert part.DRAWING_DIMENSIONS is spec.DRAWING_DIMENSIONS
    assert part.DRAWING_PRECISION is spec.DRAWING_PRECISION


def test_turned_profile_frame_and_volume() -> None:
    # Right-plane (u, v) = model (-Z, Y): head-side face at u = -THICK, seat
    # face at u = 0, spigot end at u = SPIGOT_LENGTH, closed on the axis.
    assert part.PROFILE_POINTS == [
        (-spec.THICK, 0.0),
        (-spec.THICK, spec.OD / 2.0),
        (0.0, spec.OD / 2.0),
        (0.0, spec.SPIGOT_DIA / 2.0),
        (spec.SPIGOT_LENGTH, spec.SPIGOT_DIA / 2.0),
        (spec.SPIGOT_LENGTH, 0.0),
    ]
    assert part.V_WASHER == pytest.approx(
        math.pi * ((spec.OD / 2.0) ** 2 - (spec.ID / 2.0) ** 2) * spec.THICK
        + math.pi * ((spec.SPIGOT_DIA / 2.0) ** 2 - (spec.ID / 2.0) ** 2)
        * spec.SPIGOT_LENGTH
    )
    # The mid-plane bore cut passes both the head-side face and the spigot end.
    assert part.BORE_CUT_DEPTH / 2.0 > max(spec.THICK, spec.SPIGOT_LENGTH)


def test_side_view_dimensions_sit_clear_of_the_part() -> None:
    s = drawing._S
    top = drawing.RIGHT_CENTER[1] + spec.OD / 2.0 * s
    assert drawing.HEAD_FACE_X < drawing.SEAT_FACE_X < drawing.SPIGOT_END_X
    assert drawing.SPIGOT_END_X - drawing.HEAD_FACE_X == pytest.approx(spec.HEIGHT * s)
    # Flange Ø left of the head-side face, spigot Ø right of the spigot end.
    assert drawing.HEAD_FACE_X - drawing.RIGHT_KEEP["WasherOd"][0] >= 0.030
    assert drawing.RIGHT_KEEP["SpigotDia"][0] - drawing.SPIGOT_END_X >= 0.030
    # Both lengths chain on one row above the part, text off the narrow spans.
    rows = {drawing.RIGHT_KEEP[name][1] for name in ("WasherThickness", "SpigotLength")}
    assert rows == {drawing._LENGTH_ROW_Y}
    assert drawing._LENGTH_ROW_Y - top >= 0.015
    assert drawing.LENGTH_TEXT_XY["WasherThickness"][0] < drawing.HEAD_FACE_X - 0.010
    assert drawing.LENGTH_TEXT_XY["SpigotLength"][0] > drawing.SPIGOT_END_X + 0.030


def _calls(path: str) -> dict[str, ast.Call]:
    tree = ast.parse(Path(path).read_text(encoding="utf-8"))
    return {
        node.func.id: node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
    }


def test_the_part_carries_every_property_its_drawing_requires(monkeypatch) -> None:
    import _drawing_marks
    import _part_properties

    required = ast.literal_eval(
        next(
            k.value
            for k in _calls(drawing.__file__)["read_required_properties"].keywords
            if k.arg == "required"
        )
    )
    carried = dict(_part_properties.part_properties(part.PART_NAME))
    stamped: dict[str, str] = {}
    monkeypatch.setattr(
        _drawing_marks,
        "apply_custom_properties",
        lambda _adapter, props: stamped.update(props),
    )
    _drawing_marks.apply_drawing_properties(None, part.PART_NAME)
    carried.update(stamped)
    missing = [name for name in required if not str(carried.get(name) or "").strip()]
    assert missing == []
