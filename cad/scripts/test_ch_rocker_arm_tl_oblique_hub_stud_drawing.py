"""Offline contracts for the MHA-CH-06-TL-33 oblique-trammel hub stud."""

from __future__ import annotations

import ast
import math
from pathlib import Path

import pytest

import _config
import build_ch_rocker_arm_tl_oblique_hub_stud as part
import ch_rocker_arm_tl_oblique_hub_stud_spec as spec
import ch_rocker_arm_tl_oblique_trammel_spec as trammel
import draw_ch_rocker_arm_tl_oblique_hub_stud as drawing
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS, model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME
from _fit_ream_h7 import REAM_H7
from _hole_spec import THREAD_MAJOR_MM
from _inch_wall_limits import WALL_TARGET_MM
from _machinist_review_mode import MachinistReviewMode

STEM = "ch-rocker-arm-tl-oblique-hub-stud"
INCH = 25.4
_PART_SOURCE = Path(part.__file__).read_text(encoding="utf-8")


def test_registry_row_is_the_turned_stud() -> None:
    row = _config.parts(STEM)
    assert row["number"] == spec.NUMBER == "MHA-CH-06-TL-33"
    assert int(row["quantity"]) == spec.QUANTITY == 1
    assert row["drawing_unit"] == spec.UNIT == "in"
    assert "1018" in row["material_specification"]
    assert "supplier_skus" not in row
    # A literal, so verify's static PART_NAME scan registers the build.
    assert part.PART_NAME == spec.STEM == STEM
    assert part.MATERIAL == "Plain Carbon Steel"


def test_sheet_is_registered_and_enforced() -> None:
    sheet = DRAWINGS_BY_NAME["ch_rocker_arm_tl_oblique_hub_stud"]
    assert drawing.SPEC is sheet
    assert sheet.script == Path(drawing.__file__).resolve()
    assert sheet.source_kind == "part"
    assert sheet.artifact_stem == STEM
    assert drawing.MACHINIST_REVIEW is MachinistReviewMode.ENFORCE
    assert drawing.SLDDRW.as_posix().endswith(f"/slddrw/{STEM}.SLDDRW")
    assert sheet.script_name in PRECISION_MIGRATED_DRAWINGS


def test_owner_flange_and_gauge_pin_nose_are_kept() -> None:
    # The owner's literal 18 x 3 mm flange; the retired gauge pin's .4000
    # -.0001/0 nose and .080 +/-.008 proud.
    assert (spec.FLANGE_DIA, spec.FLANGE_THICK) == (18.0, 3.0)
    assert spec.DIA == pytest.approx(0.4 * INCH)
    assert spec.DIA_BAND == pytest.approx((0.0, -0.0001 * INCH))
    assert spec.TIP_SET == pytest.approx(0.080 * INCH)
    assert spec.TIP_SET_BAND == pytest.approx(0.008 * INCH)
    assert spec.NOSE_LENGTH == spec.TIP_SET
    # The literal flange prints .71 x .12 at the title block's .XX; the part
    # is accepted on the PRINTED nominal +/-.01, not on 18 x 3 +/-.254.
    assert spec.FLANGE_PLACES == 2
    assert spec.FLANGE_DIA_PRINTED == pytest.approx(0.71 * INCH)
    assert spec.FLANGE_THICK_PRINTED == pytest.approx(0.12 * INCH)
    assert spec.FLANGE_DIA_LIMITS == pytest.approx((17.780, 18.288))
    assert spec.FLANGE_THICK_LIMITS == pytest.approx((2.794, 3.302))
    assert not hasattr(spec, "FLANGE_BAND")
    # TL-21's seat width beside the HUB chamfer at the smallest printed flange.
    seat = (
        spec.FLANGE_DIA_LIMITS[0] / 2.0
        - (spec.CARRIER_BORE_DIA + REAM_H7[0]) / 2.0
        - 0.03 * INCH
    )
    assert seat >= WALL_TARGET_MM


def test_nose_band_names_its_mate_and_float() -> None:
    # The tight band against MHA-CH-13's .4000 +.0005/0 hub hole prints its
    # actual radial float (NOSE_CLEARANCE upper / 2); the strap hole's limits
    # print REF (the strap's sheet controls them). No allocation claim here.
    assert spec.STRAP_HOLE_LIMITS == pytest.approx((0.4 * INCH, 0.4005 * INCH))
    assert spec.NOSE_CLEARANCE == pytest.approx((0.0, 0.0006 * INCH))
    assert not hasattr(spec, "EDGE_TO_HUB_ALLOCATION")
    callout = spec.DIMENSION_CALLOUTS["NoseDia"]
    assert callout == (
        "LOCATES STRAP MHA-CH-13 HUB\nHOLE (.4000-.4005 REF):\n.0003 MAX RADIAL FLOAT"
    )
    assert "ALLOCATION" not in callout
    assert "TOP OF RISER " + spec.RISER_NUMBER in spec.DIMENSION_CALLOUTS["FitLength"]


def test_end_view_is_the_true_nose_end_projection() -> None:
    # Third angle: the nose (+Z) end's view stands on the nose's side. "*Left"
    # draws +Z right and its right-side view is "*Front", the nose face.
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'place_view(adapter, str(SOURCE), "*Left", *SIDE_CENTER' in source
    assert 'place_view(adapter, str(SOURCE), "*Front", *END_CENTER' in source
    assert drawing._sx(spec.LENGTH) > drawing._sx(0.0)
    assert drawing.END_CENTER[0] > drawing._sx(spec.LENGTH)
    assert drawing.SIDE_KEEP["NoseDia"][0] > drawing._sx(spec.LENGTH)
    # The fit-up text leaves its .79 span on a leader, clear of the end view.
    fit_x, fit_y = drawing.FIT_LENGTH_TEXT_XY
    assert fit_x > drawing._sx(spec.LENGTH)
    assert fit_y < drawing._BELOW


def test_shank_slips_in_the_carrier_bore_and_spans_carrier_and_riser() -> None:
    assert spec.SHANK_DIA == pytest.approx(0.3995 * INCH)
    assert spec.SHANK_DIA_BAND == pytest.approx((0.0, -0.0005 * INCH))
    low, high = spec.SHANK_CLEARANCE
    assert low == pytest.approx(0.0005 * INCH)
    assert high == pytest.approx(0.0015 * INCH)
    assert spec.CARRIER_BORE_DIA == pytest.approx(0.4 * INCH)
    assert REAM_H7 == pytest.approx((0.0005 * INCH, 0.0))
    assert spec.SHANK_LENGTH == pytest.approx(trammel.CARRIER_THICK + trammel.RISER_THICK)
    assert spec.LENGTH == pytest.approx(
        spec.FLANGE_THICK + spec.SHANK_LENGTH + spec.NOSE_LENGTH
    )
    assert spec.FIT_LENGTH == pytest.approx(spec.SHANK_LENGTH + spec.NOSE_LENGTH)


def test_supply_covers_the_thickest_carrier_and_riser() -> None:
    # Rule 19: the proud is faced at assembly; the supply length reaches it
    # with the carrier and riser both at their .XX band's top.
    worst = (
        trammel.CARRIER_THICK
        + trammel.CARRIER_THICK_BAND
        + trammel.RISER_THICK
        + trammel.RISER_THICK_BAND
        + spec.TIP_SET
        + spec.TIP_SET_BAND
    )
    assert spec.SUPPLY_LENGTH_MIN >= worst
    assert spec.SUPPLY_LENGTH_MIN - worst < 0.01 * INCH
    assert spec.SUPPLY_LENGTH_MIN == pytest.approx(0.82 * INCH)
    assert spec.SUPPLY_LENGTH_TOL_TYPE == 5
    assert spec.SUPPLY_LENGTH_BAND[1] == 0.0 < spec.SUPPLY_LENGTH_BAND[0]
    assert "FIT AT ASSEMBLY" in spec.DIMENSION_CALLOUTS["FitLength"]
    assert spec.DIMENSION_CALLOUTS["SupplyLength"] == "SUPPLY"


def test_nose_tap_meets_rules_12_17_and_18() -> None:
    assert spec.TAP_SPEC.kind == "tapped"
    assert spec.TAP_SPEC.size == "#10-24"
    assert spec.TAP_SPEC.end == "blind"
    assert spec.TAP_SPEC.depth_mm == spec.TAP_DRILL_DEPTH == pytest.approx(0.65 * INCH)
    assert spec.TAP_SPEC.overrides_mm == {"ThreadDepth": spec.TAP_FULL_DEPTH}
    assert spec.TAP_FULL_DEPTH == pytest.approx(0.46 * INCH)
    assert spec.TAP_FULL_DEPTH_MIN >= 1.5 * THREAD_MAJOR_MM["#10-24"]
    assert spec.TAP_LEAD_ROOM_PITCHES >= 3.0
    assert spec.TAP_WALL >= WALL_TARGET_MM
    assert spec.TAP_POINT_BOTTOM_Z > spec.FLANGE_THICK


def test_root_radius_is_a_max_limit_inside_the_flange_seat() -> None:
    assert spec.ROOT_FILLET_R == pytest.approx(0.008 * INCH)
    assert spec.ROOT_FILLET_BAND == (0.0, -spec.ROOT_FILLET_R)
    assert spec.ROOT_FILLET_TOL_TYPE == 6
    assert spec.SHANK_DIA / 2.0 + spec.ROOT_FILLET_R < spec.FLANGE_DIA / 2.0
    assert spec.CARRIER_NUMBER in spec.DIMENSION_CALLOUTS["RootRadius"]


def test_bands_are_model_owned_and_name_their_mates() -> None:
    assert spec.DRAWING_BANDS == {
        ("ShankProfile", "ShankDia"): spec.SHANK_DIA_BAND,
        ("NoseProfile", "NoseDia"): spec.DIA_BAND,
    }
    assert model_toleranced_dimensions(part) == {
        ("feature_name", "dimension_name"): "*deviations(band)"
    }
    assert "for (feature_name, dimension_name), band in DRAWING_BANDS.items():" in (
        _PART_SOURCE
    )
    assert spec.CARRIER_NUMBER in spec.DIMENSION_CALLOUTS["ShankDia"]
    assert spec.STRAP_NUMBER in spec.DIMENSION_CALLOUTS["NoseDia"]


def test_every_marked_dimension_is_kept_on_the_side_view_at_model_places() -> None:
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert set(drawing.SIDE_KEEP) == marked
    assert set(spec.DIMENSION_CALLOUTS) <= marked
    assert {
        (feature, name) for feature, names in spec.DRAWING_PRECISION.items() for name in names
    } == {
        (feature, name) for feature, names in spec.DRAWING_DIMENSIONS.items() for name in names
    }
    assert spec.DRAWING_PRECISION_BY_NAME == {
        "FlangeDia": 2,
        "FlangeThick": 2,
        "ShankDia": 4,
        "ShankLength": 2,
        "NoseDia": 4,
        "RootRadius": 3,
        "FitLength": 2,
        "SupplyLength": 2,
    }
    assert part.DRAWING_DIMENSIONS is spec.DRAWING_DIMENSIONS
    assert part.DRAWING_PRECISION is spec.DRAWING_PRECISION


def test_model_volume_terms() -> None:
    assert part.V_FLANGE == pytest.approx(math.pi * 9.0**2 * 3.0)
    assert part.V_NOSE == pytest.approx(math.pi * (spec.DIA / 2.0) ** 2 * spec.NOSE_LENGTH)
    assert 0.0 < part.V_FILLET < 1.0  # a .008 root spandrel revolved at r ~5 mm


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


def test_no_finish_symbol_and_no_gdt() -> None:
    names = set(_calls(drawing.__file__))
    assert not names & {
        "add_datum_feature",
        "add_feature_control_frame",
        "add_surface_finish_symbol",
    }
