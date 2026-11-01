"""Offline contracts for the pinion-lift-rod drawing."""

from __future__ import annotations

from pathlib import Path

import pytest

import _config

import build_dt_pinion_lift_rod as part
import draw_dt_pinion_lift_rod as drawing
import dt_pinion_lever_geometry as lever
import dt_pinion_lift_rod_spec
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS, model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/dt-pinion-lift-rod.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/dt-pinion-lift-rod.pdf")
    assert drawing.PNG.as_posix().endswith("/png/dt-pinion-lift-rod_drawing.png")
    assert (
        DRAWINGS_BY_NAME["dt_pinion_lift_rod"].script
        == Path(drawing.__file__).resolve()
    )
    assert "draw_dt_pinion_lift_rod.py" in PRECISION_MIGRATED_DRAWINGS


def test_spec_is_the_single_source_of_drawing_dimensions() -> None:
    assert part.DRAWING_DIMENSIONS is dt_pinion_lift_rod_spec.DRAWING_DIMENSIONS
    marked = set().union(*dt_pinion_lift_rod_spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.RIGHT_KEEP) | set(drawing.DETAIL_KEEP)
    assert kept == marked
    assert set(drawing.DETAIL_KEEP) == {"PinHoleDia", "PinHoleZ"}


def test_bearing_is_the_only_band_and_finish() -> None:
    # drawing-guidelines.md rule 2 (the title block is the general specification) and drawing-guidelines.md rule 6 (roughness symbols only where a surface runs, slides or locates): the rod turns in the blocks, so its diameter carries the shaft
    # band and its flank the one roughness symbol; everything else rides the
    # title block at the part-authored places.
    assert model_toleranced_dimensions(part) == {
        ("RodProfile", "RodDia"): "*deviations(ROD_DIA_BAND)"
    }
    (control,) = dt_pinion_lift_rod_spec.SURFACE_FINISHES
    assert control.key == "bearing" and control.roughness_um == 1.6
    assert control.face.diameter_mm == dt_pinion_lift_rod_spec.ROD_DIA
    assert dt_pinion_lift_rod_spec.DRAWING_PRECISION_BY_NAME["RodDia"] == 4
    assert dt_pinion_lift_rod_spec.DRAWING_PRECISION_BY_NAME["PinHoleZ"] == 2


def test_pin_hole_sits_at_the_lever_mid_engagement() -> None:
    # U36: the pin crosses the rod where it crosses the lever hub -- half the
    # hub's bore depth in from the front end, which seats on the bore floor.
    assert lever.ROD_PIN_HOLE_FROM_END == lever.BORE_DEPTH / 2.0
    assert lever.ROD_PIN_HOLE_FROM_END == pytest.approx(0.16 * 25.4)
    assert dt_pinion_lift_rod_spec.LEVER_NUMBER in dt_pinion_lift_rod_spec.PIN_HOLE_CALLOUT


def test_the_lathe_sizes_live_on_the_side_view_plane() -> None:
    # drawing-guidelines.md rule 11 (turned parts read like the lathe): one
    # Right-Plane half-profile carries the diameter, body, crown and overall,
    # so they all import into the side view; the pin hole shares that plane.
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert source.count('adapter.create_sketch("Right")') == 2
    assert 'create_sketch("Front")' not in source
    assert "create_revolve" in source
    assert 'set_dimension_prefix(adapter, "RodProfile", "CapR", "SR")' in source
    assert set(dt_pinion_lift_rod_spec.DRAWING_DIMENSIONS["RodProfile"]) == set(
        drawing.RIGHT_KEEP
    )
    assert '"*Front"' not in Path(drawing.__file__).read_text(encoding="utf-8")


def test_the_overall_is_a_reference_and_the_body_length_controls() -> None:
    # Rule 10: the overall to the crown apex is real and conspicuous, printed
    # in parentheses; the body length carries the .XX band the rig stack reads.
    assert dt_pinion_lift_rod_spec.DRAWING_REFERENCE_DIMENSIONS == {"RodOverall"}
    assert dt_pinion_lift_rod_spec.DRAWING_PRECISION["RodProfile"]["RodBody"] == 2
    # Below the rod, the overall outermost.
    assert drawing.RIGHT_KEEP["RodOverall"][1] < drawing.RIGHT_KEEP["RodBody"][1]
    assert drawing.RIGHT_KEEP["RodBody"][1] < drawing.RIGHT_CENTER[1]


def test_the_body_length_exception_names_the_rig_stacks() -> None:
    # Owner ruling 2026-10-19 (RV-01): the rim-flush rig stacks read the body
    # length, so the review's "tolerance the overall" fix is declared away.
    import pinion_rig_layout
    from machinist_exceptions import load_exceptions

    (entry,) = load_exceptions(_config.CONFIG_DIR, "dt_pinion_lift_rod", "part")
    assert (entry.id, entry.kind) == ("RV-01", "accept")
    spec = dt_pinion_lift_rod_spec
    assert "body length" in entry.where and "reference overall" in entry.where
    assert spec.CAP_R == pytest.approx(0.19 * 25.4)
    assert "SR.19" in entry.where
    for stack in ("lift_rod_seat_stack", "lever_north_travel_stack"):
        assert stack in entry.reason
        assert callable(getattr(pinion_rig_layout, stack))


def test_the_bearing_band_names_its_mate() -> None:
    # drawing-guidelines.md rule 4 (tighten only for function, and name the
    # mate): the h band and Ra ride the bore the rod runs in.
    block = _config.parts("dt-pinion-pivot-block")
    assert dt_pinion_lift_rod_spec.PIVOT_BLOCK_NUMBER == block["number"]
    callout = dt_pinion_lift_rod_spec.ROD_DIA_CALLOUT
    assert f"RUNNING FIT IN {block['number']} LIFT BORES" in callout
    assert "GROUND STOCK OK" in callout
    assert drawing.DIMENSION_CALLOUTS["RodDia"] == callout
    assert "\n" in callout  # multi-line: below the value, where it prints


def test_the_sheet_has_no_general_notes() -> None:
    # Machinist review r1: the crown note floated far from the feature it
    # governs; the SR on the side view defines the crown.
    assert not hasattr(dt_pinion_lift_rod_spec, "DRAWING_NOTES")
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "Manufacturing Notes" not in source
    assert "add_feature_control_frame" not in source
    assert "add_native_axis_datum" not in source
    assert "SetPrecision3" not in source


def test_view_scales_are_explicit() -> None:
    assert drawing.SHEET_SCALE == (1.0, 1.0)
    assert drawing.DETAIL_SCALE == (5, 1)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "scale=(1, 1)" in source  # side view true scale
    assert dt_pinion_lift_rod_spec.ISOMETRIC_VIEW_NOTE == "ISOMETRIC VIEW SCALE 1:2"
