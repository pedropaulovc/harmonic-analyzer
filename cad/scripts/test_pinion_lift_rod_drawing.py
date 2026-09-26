"""Offline contracts for the pinion-lift-rod drawing."""

from __future__ import annotations

from pathlib import Path

import build_pinion_lift_rod as part
import draw_pinion_lift_rod as drawing
import pinion_lever_geometry as lever
import pinion_lift_rod_spec
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS, model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/pinion-lift-rod.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/pinion-lift-rod.pdf")
    assert drawing.PNG.as_posix().endswith("/png/pinion-lift-rod_drawing.png")
    assert (
        DRAWINGS_BY_NAME["pinion_lift_rod"].script
        == Path(drawing.__file__).resolve()
    )
    assert "draw_pinion_lift_rod.py" in PRECISION_MIGRATED_DRAWINGS


def test_spec_is_the_single_source_of_drawing_dimensions() -> None:
    assert part.DRAWING_DIMENSIONS is pinion_lift_rod_spec.DRAWING_DIMENSIONS
    marked = set().union(*pinion_lift_rod_spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.FRONT_KEEP) | set(drawing.RIGHT_KEEP) | set(drawing.DETAIL_KEEP)
    assert kept == marked
    assert set(drawing.DETAIL_KEEP) == {"PinHoleDia", "PinHoleZ"}


def test_bearing_is_the_only_band_and_finish() -> None:
    # Rule 1-5: the rod turns in the blocks, so its diameter carries the shaft
    # band and its flank the one roughness symbol; everything else rides the
    # title block at the part-authored places.
    assert model_toleranced_dimensions(part) == {
        ("RodProfile", "RodDia"): "*deviations(ROD_DIA_BAND)"
    }
    (control,) = pinion_lift_rod_spec.SURFACE_FINISHES
    assert control.key == "bearing" and control.roughness_um == 1.6
    assert control.face.diameter_mm == pinion_lift_rod_spec.ROD_DIA
    assert pinion_lift_rod_spec.DRAWING_PRECISION_BY_NAME["RodDia"] == 2
    assert pinion_lift_rod_spec.DRAWING_PRECISION_BY_NAME["PinHoleZ"] == 1


def test_pin_hole_sits_at_the_lever_mid_engagement() -> None:
    # U36: the pin crosses the rod where it crosses the lever hub -- half the
    # hub's bore depth in from the front end, which seats on the bore floor.
    assert lever.ROD_PIN_HOLE_FROM_END == lever.BORE_DEPTH / 2.0 == 4.0
    callout = pinion_lift_rod_spec.PIN_HOLE_CALLOUT
    assert "MATCH-DRILL" in callout and "AT ASSEMBLY" in callout
    assert pinion_lift_rod_spec.LEVER_NUMBER in callout
    assert pinion_lift_rod_spec.PIN_NUMBER in callout
    assert drawing.DIMENSION_CALLOUTS["PinHoleDia"] == callout


def test_crown_and_hole_live_on_the_side_view_plane() -> None:
    # The side view looks along X, so the crown's SR and the pin hole are
    # sketched on the Right Plane to import there.
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert source.count('adapter.create_sketch("Right")') == 2
    assert 'set_dimension_prefix(adapter, "BackCapProfile", "CapR", "SR")' in source
    assert "CapR" in drawing.RIGHT_KEEP


def test_notes_are_short_and_carry_no_dimension() -> None:
    notes = pinion_lift_rod_spec.DRAWING_NOTES
    assert len(notes.splitlines()) <= 4
    assert not any(ch.isdigit() for ch in notes)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "add_feature_control_frame" not in source
    assert "add_native_axis_datum" not in source
    assert "SetPrecision3" not in source


def test_view_scales_are_explicit() -> None:
    assert drawing.SHEET_SCALE == (1.0, 1.0)
    assert drawing.DETAIL_SCALE == (5, 1)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "scale=(2, 1)" in source  # end view 2:1
    assert "scale=(1, 1)" in source  # side view true scale
    assert pinion_lift_rod_spec.END_VIEW_NOTE == "END VIEW SCALE 2:1"
    assert pinion_lift_rod_spec.ISOMETRIC_VIEW_NOTE == "ISOMETRIC VIEW SCALE 1:2"


def test_the_end_view_diameter_is_placed_inside_the_zone_frame_from_its_read_back() -> (
    None
):
    # pc-r7 machinist review: its shoulder ran past the inner border.
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    call = source[source.index("place_callout_clear(") :]
    call = call[: call.index("add_property_linked_note")]
    assert '== "RodDia"' in call
    assert "front_annotations" in call
