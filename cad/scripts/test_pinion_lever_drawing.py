"""Offline contracts for the pinion-engage-lever drawing."""

from __future__ import annotations

from pathlib import Path

import build_pinion_lever as lever
import draw_pinion_lever as drawing
import pinion_lever_geometry
import pinion_lever_spec
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS, model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/pinion-lever.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/pinion-lever.pdf")
    assert drawing.PNG.as_posix().endswith("/png/pinion-lever_drawing.png")
    assert DRAWINGS_BY_NAME["pinion_lever"].script == Path(drawing.__file__).resolve()
    assert "draw_pinion_lever.py" in PRECISION_MIGRATED_DRAWINGS


def test_spec_is_the_single_source_of_the_marked_dimension_set() -> None:
    assert lever.DRAWING_DIMENSIONS is pinion_lever_spec.DRAWING_DIMENSIONS
    assert lever.SURFACE_FINISHES is pinion_lever_spec.SURFACE_FINISHES
    marked = set().union(*pinion_lever_spec.DRAWING_DIMENSIONS.values())
    keeps = (drawing.FRONT_KEEP, drawing.TOP_KEEP, drawing.DETAIL_KEEP)
    kept = set().union(*keeps)
    assert kept == marked
    assert sum(len(keep) for keep in keeps) == len(marked)  # each dimension once
    assert set(drawing.DIMENSION_CALLOUTS) <= kept
    # The hub's axial stations all read from face B in the one side detail.
    assert {"BoreDepth", "EndWall", "GripFromB", "PinHoleFromB", "PinHoleDia"} == set(
        drawing.DETAIL_KEEP
    )


def test_bore_band_is_a_slip_fit_on_the_lift_rod() -> None:
    # U36: the pin carries the torque, so the bore only slides on the h-band
    # rod.  Codex P2 (#844): the repo's REAM_SLIDE band, never line-to-line.
    from _fit_limits import REAM_SLIDE, SHAFT_H
    from pinion_lift_rod_spec import ROD_DIA

    assert pinion_lever_spec.BORE_BAND == REAM_SLIDE
    low, high = (
        pinion_lever_spec.BORE + pinion_lever_spec.BORE_BAND[1],
        pinion_lever_spec.BORE + pinion_lever_spec.BORE_BAND[0],
    )
    assert (round(low, 6), round(high, 6)) == (6.36, 6.375)
    min_clearance = low - (ROD_DIA + SHAFT_H[0])
    assert min_clearance > 0.0
    assert round(min_clearance, 6) == 0.01
    assert model_toleranced_dimensions(lever) == {
        ("BarrelProfile", "HubBore"): "*deviations(BORE_BAND)",
        ("Wall", "EndWall"): "END_WALL_TOLERANCE_MM",
    }
    assert pinion_lever_spec.DRAWING_PRECISION_BY_NAME["HubBore"] == 3
    assert pinion_lever_spec.DRAWING_PRECISION_BY_NAME["EndWall"] == 2
    assert pinion_lever_spec.WALL_T - pinion_lever_spec.END_WALL_TOLERANCE_MM >= 1.5


def test_grip_rod_is_a_straight_six() -> None:
    # User ruling 2026-09-24 (ch25 page002_img07): the photo's "6 mm" sits
    # beside the hub and root and tip read the same width -- no taper.
    assert pinion_lever_geometry.ROD_DIA == 6.0
    assert not hasattr(pinion_lever_geometry, "ROD_ROOT_DIA")
    assert not hasattr(pinion_lever_geometry, "ROD_TIP_DIA")
    assert pinion_lever_spec.DRAWING_DIMENSIONS["RodProfile"] == {"RodTipY", "RodDia"}
    assert pinion_lever_spec.DRAWING_PRECISION_BY_NAME["RodDia"] == 1
    # The rod's base stays clear of the bore and the pin hole it rises over.
    assert pinion_lever_geometry.ROD_Y0 > pinion_lever_geometry.BORE / 2.0
    assert pinion_lever_geometry.ROD_Y0 > pinion_lever_geometry.PIN_HOLE_DIA / 2.0
    # The rod's z band stays inside the hub.
    assert pinion_lever_geometry.ROD_DIA < pinion_lever_geometry.HUB_LEN


def test_pin_hole_sits_at_mid_engagement_and_is_match_drilled() -> None:
    geometry = pinion_lever_geometry
    assert geometry.PIN_HOLE_DIA == 25.4 / 16.0
    assert geometry.PIN_HOLE_FROM_MOUTH == geometry.BORE_DEPTH / 2.0 == 4.0
    assert geometry.PIN_HOLE_Z == geometry.HUB_LEN / 2.0 - geometry.PIN_HOLE_FROM_MOUTH
    callout = drawing.DIMENSION_CALLOUTS["PinHoleDia"]
    assert callout == pinion_lever_spec.PIN_HOLE_CALLOUT
    assert "MATCH-DRILL" in callout and "AT ASSEMBLY" in callout
    assert pinion_lever_spec.LIFT_ROD_NUMBER in callout
    assert pinion_lever_spec.PIN_NUMBER in callout
    assert pinion_lever_spec.LIFT_ROD_NUMBER in drawing.DIMENSION_CALLOUTS["HubBore"]


def test_sheet_carries_no_gdt_finish_or_literal_precision() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    for forbidden in (
        "add_feature_control_frame",
        "add_datum_feature",
        "add_native_axis_datum",
        "add_surface_finish",
        "add_attached_note",
        "SetPrecision3",
    ):
        assert forbidden not in source, forbidden
    assert pinion_lever_spec.SURFACE_FINISHES == ()
    assert "assert_imported_precision" in source
    assert source.count("dimensions_by_feature=DRAWING_DIMENSIONS") == 3


def test_notes_are_short_and_carry_no_dimension() -> None:
    notes = pinion_lever_spec.DRAWING_NOTES
    assert len(notes.splitlines()) <= 4
    assert not any(ch.isdigit() for ch in notes)
    assert "EDGE-BREAK" in notes
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source


def test_sheet_runs_at_1_to_1_with_a_3_to_1_hub_detail() -> None:
    assert drawing.SHEET_SCALE == (1.0, 1.0)
    assert drawing.DETAIL_SCALE == (3, 1)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "scale=(1, 1)" in source
    assert pinion_lever_spec.ISOMETRIC_VIEW_NOTE == "ISOMETRIC VIEW SCALE 1:1"
    assert 'add_property_linked_note(adapter, "Isometric View Note"' in source


def test_part_stamps_make_critical_drawing_properties() -> None:
    source = Path(lever.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    assert "apply_drawing_precision" in source
    import _config

    spec = _config.parts("pinion-lever")
    assert spec["material"] == spec["material_specification"]
    assert spec["material_specification"]
    assert spec["finish"]
    assert "fit_class" not in spec
    assert int(spec["quantity"]) == 1
