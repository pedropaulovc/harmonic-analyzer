"""Geometry-independent contracts for measured native annotation footprints."""

from dataclasses import replace
import math
import sys
from types import SimpleNamespace

import pytest
from _drawing_view_packing import Rect

from _drawing_annotation_bounds import (
    NativeSnapshot,
    Segment,
    TextRun,
    bounds_from_snapshot,
    font_cell_extent,
    _gdi_cell,
    _native_snapshot,
)


def test_native_stroke_witness_preserves_internal_geometry_and_print_width():
    lines = (
        Segment((0.01, 0.02), (0.03, 0.02), 0.00018),
        Segment((0.02, 0.01), (0.02, 0.03), 0.00018),
    )
    measured = bounds_from_snapshot(snapshot(kind=15, text_runs=(), lines=lines))
    assert measured.native_strokes == lines
    # Moving an interior endpoint leaves the bounding rectangle unchanged but
    # must be detectable by a native geometry witness.
    interior = Segment((0.014, 0.025), (0.025, 0.025), 0.00018)
    before = bounds_from_snapshot(
        snapshot(kind=15, text_runs=(), lines=(*lines, interior))
    )
    after = bounds_from_snapshot(
        snapshot(
            kind=15,
            text_runs=(),
            lines=(*lines, replace(interior, start=(0.015, 0.025))),
        )
    )
    assert before.body == after.body
    assert before.native_strokes != after.native_strokes
    shifted = tuple(
        Segment(
            (line.start[0] + 0.006, line.start[1] - 0.004),
            (line.end[0] + 0.006, line.end[1] - 0.004),
            line.width_m,
        )
        for line in lines
    )
    translated = bounds_from_snapshot(snapshot(kind=15, text_runs=(), lines=shifted))
    assert translated.native_strokes == shifted


def test_leader_decoration_boxes_remain_available_for_text_collision_checks():
    decoration = Rect(0.045, 0.015, 0.049, 0.019)
    measured = bounds_from_snapshot(snapshot(leader_boxes=(decoration,)))
    assert measured.leader_decorations == (decoration,)
    assert measured.envelope.xmax >= decoration.xmax


def _all_around_snapshot(
    monkeypatch,
    *,
    side,
    all_around=lambda: True,
    circle_offset=0.0,
    sweep="closed",
    unsupported_counts=(0, 0, 0),
):
    """Sanitized channel-lever DetailItem350 native side-switch fixture."""
    import _drawing_annotation_bounds as module

    monkeypatch.setattr(module, "_early_bound", lambda value, interface: value)
    original_x = 0.229100000042
    anchor_x, elbow_x = original_x, 0.222750000042
    if side == "right":
        anchor_x, elbow_x = 0.06324632791085244, 0.10834424444129764
    anchor_y, elbow_y = 0.159750000025, 0.156250000025
    width = 0.03874791653044521
    frame = rectangle(anchor_x, anchor_y - 0.007, anchor_x + width, anchor_y)
    start_x = anchor_x if side == "left" else anchor_x + width
    leader = ((start_x, elbow_y, 0), (elbow_x, elbow_y, 0), (original_x, anchor_y, 0))
    circle = (
        -1,
        0,
        0,
        0,
        elbow_x + circle_offset + 0.00175,
        elbow_y,
        0,
        elbow_x + circle_offset + (0.00175 if sweep == "closed" else -0.00175),
        elbow_y,
        0,
        elbow_x + circle_offset,
        elbow_y,
        0,
        0,
        0,
        1,
        1,
    )
    data = SimpleNamespace(
        GetTextCount=lambda: 0,
        GetLineCount=lambda: len(frame),
        GetLineAtIndex3=lambda index: (
            -1,
            0,
            0,
            0,
            *frame[index].start,
            0,
            *frame[index].end,
            0,
        ),
        GetArcCount=lambda: 1,
        GetArcAtIndex2=lambda index: circle,
        GetPolyLineCount=lambda: 0,
        GetTriangleCount=lambda: 0,
        GetArrowHeadCount=lambda: 0,
        GetPolygonCount=lambda: 0,
        GetEllipseCount=lambda: unsupported_counts[0],
        GetParabolaCount=lambda: unsupported_counts[1],
        GetPointCount=lambda: unsupported_counts[2],
    )
    annotation = SimpleNamespace(
        GetType=lambda: 5,
        GetName=lambda: "DetailItem350",
        GetDisplayData=lambda: data,
        GetLeaderCount=lambda: 1,
        GetMultiJogLeaderCount=lambda: 0,
        GetLeaderPointsAtIndex=lambda index: tuple(
            value for point in leader for value in point
        ),
        GetLeaderAllAround=all_around,
        GetPosition=lambda: (anchor_x, anchor_y, 0),
    )
    return _native_snapshot(annotation)


@pytest.mark.parametrize("counts", [(1, 0, 0), (0, 2, 0), (0, 0, 1), (-1, 0, 0)])
def test_unsupported_native_primitive_inventory_cannot_be_silently_omitted(
    monkeypatch, counts
):
    with pytest.raises(ValueError, match="native primitive inventory"):
        _all_around_snapshot(monkeypatch, side="left", unsupported_counts=counts)


def test_native_all_around_circle_follows_elbow_without_deforming_frame(monkeypatch):
    before = bounds_from_snapshot(_all_around_snapshot(monkeypatch, side="left"))
    after = bounds_from_snapshot(_all_around_snapshot(monkeypatch, side="right"))
    delta = (0.06324632791085244 - 0.229100000042, 0)
    assert after.body.bounds == pytest.approx(before.body.translated(delta).bounds)
    assert before.body.xmin == pytest.approx(0.229100000042)
    assert before.envelope.xmin == pytest.approx(0.221000000042)
    assert after.envelope.xmax >= 0.11009424444129765
    assert len(_all_around_snapshot(monkeypatch, side="right").leader_boxes) == 1


def test_arc_at_elbow_is_not_excluded_without_native_all_around_flag(monkeypatch):
    native = _all_around_snapshot(monkeypatch, side="left", all_around=lambda: False)
    assert len(native.primitive_boxes) == 1
    assert native.leader_boxes == ()
    assert bounds_from_snapshot(native).body.xmin == pytest.approx(0.221000000042)


@pytest.mark.parametrize("circle_offset,sweep", [(0.002, "closed"), (0.0, "partial")])
def test_only_complete_circle_at_native_elbow_is_leader_decoration(
    monkeypatch, circle_offset, sweep
):
    native = _all_around_snapshot(
        monkeypatch, side="left", circle_offset=circle_offset, sweep=sweep
    )
    assert len(native.primitive_boxes) == 1
    assert native.leader_boxes == ()


def text(value="LONG QUANTITY BELOW FRAME", position=(0.05, 0.04), angle=0):
    return TextRun(value, position, 0.0035, "Century Gothic", angle, 1, 0)


def rectangle(x0, y0, x1, y1):
    points = ((x0, y0), (x1, y0), (x1, y1), (x0, y1))
    return tuple(Segment(a, b) for a, b in zip(points, (*points[1:], points[0])))


def snapshot(**changes):
    values = dict(
        name="GTol1",
        kind=5,
        anchor=(0.05, 0.05),
        text_runs=(text(),),
        lines=rectangle(0.05, 0.05, 0.07, 0.057),
        leaders=(),
        primitive_boxes=(),
        note_extent=None,
        format_signature=("Century Gothic", 0.0035, 13, False, 1.0, False, False),
    )
    values.update(changes)
    return NativeSnapshot(**values)


def metrics(run, signature):
    return Rect(0.0, 0.0, 0.060, 0.006)


def test_quantity_text_extends_body_beyond_native_frame():
    result = bounds_from_snapshot(snapshot(), text_extent=metrics)
    assert result.body.bounds == pytest.approx((0.05, 0.04, 0.11, 0.057))
    assert result.text_runs[0].value == "LONG QUANTITY BELOW FRAME"


def test_leader_is_excluded_from_body_but_retained_in_envelope():
    leader = Segment((0.05, 0.0535), (0.01, 0.01))
    sample = snapshot(
        lines=(*rectangle(0.05, 0.05, 0.07, 0.057), leader), leaders=(leader,)
    )
    result = bounds_from_snapshot(sample, text_extent=metrics)
    assert result.body.xmin == 0.05
    assert result.envelope.xmin == 0.01
    assert leader in result.leader_segments


def test_moving_native_callout_body_keeps_fixed_attachment_in_envelope():
    fixed = (0.01, 0.01)
    old_leaders = (
        Segment((0.05, 0.0535), (0.04, 0.0535)),
        Segment((0.04, 0.0535), fixed),
    )
    before = bounds_from_snapshot(
        snapshot(
            lines=(*rectangle(0.05, 0.05, 0.07, 0.057), *old_leaders),
            leaders=old_leaders,
        ),
        text_extent=metrics,
    )
    new_leaders = (
        Segment((0.09, 0.0735), (0.08, 0.0735)),
        Segment((0.08, 0.0735), fixed),
    )
    after = bounds_from_snapshot(
        snapshot(
            anchor=(0.09, 0.07),
            text_runs=(text(position=(0.09, 0.06)),),
            lines=(*rectangle(0.09, 0.07, 0.11, 0.077), *new_leaders),
            leaders=new_leaders,
        ),
        text_extent=metrics,
    )
    assert after.body.bounds == pytest.approx(
        before.body.translated((0.04, 0.02)).bounds
    )
    assert after.envelope.xmin == fixed[0]
    assert after.envelope.ymin == fixed[1]


def test_native_arrow_footprint_changes_envelope_not_callout_body():
    result = bounds_from_snapshot(
        snapshot(leader_boxes=(Rect(0.001, 0.002, 0.009, 0.01),)), text_extent=metrics
    )
    assert result.body.xmin == 0.05
    assert result.envelope.xmin == 0.001


def test_datum_stem_not_reported_by_native_leader_api_stays_outside_body():
    stem = Segment((0.06, 0.02), (0.06, 0.05))
    sample = snapshot(
        kind=2,
        lines=(*rectangle(0.05, 0.05, 0.07, 0.057), stem),
        text_runs=(text("A", (0.055, 0.051)),),
    )
    result = bounds_from_snapshot(
        sample, text_extent=lambda *_: Rect(0.0, 0.0, 0.004, 0.005)
    )
    assert result.body.ymin == 0.05
    assert result.envelope.ymin == 0.02
    assert stem in result.leader_segments


def test_native_sf_body_uses_actual_strokes_not_nominal_legacy_box():
    sample = snapshot(
        kind=7,
        text_runs=(text("Ra 1.6", (0.08, 0.065)),),
        lines=(Segment((0.06, 0.04), (0.09, 0.08)),),
    )
    result = bounds_from_snapshot(
        sample, text_extent=lambda *_: Rect(0.0, 0.0, 0.012, 0.005)
    )
    assert result.body.bounds == pytest.approx((0.06, 0.04, 0.092, 0.08))


def test_shifted_drawing_keeps_native_sheet_coordinates_without_adding_anchor():
    sample = snapshot()
    delta = (0.11, -0.02)
    shifted = replace(
        sample,
        anchor=tuple(a + b for a, b in zip(sample.anchor, delta)),
        text_runs=tuple(
            replace(t, position=tuple(a + b for a, b in zip(t.position, delta)))
            for t in sample.text_runs
        ),
        lines=tuple(
            Segment(
                tuple(a + b for a, b in zip(s.start, delta)),
                tuple(a + b for a, b in zip(s.end, delta)),
            )
            for s in sample.lines
        ),
    )
    before = bounds_from_snapshot(sample, text_extent=metrics)
    after = bounds_from_snapshot(shifted, text_extent=metrics)
    assert after.body.bounds == pytest.approx(before.body.translated(delta).bounds)


def test_rotated_text_cell_is_transformed_about_its_native_reference():
    sample = snapshot(
        lines=(), kind=4, text_runs=(text("10.00", (0.1, 0.2), math.pi / 2),)
    )
    result = bounds_from_snapshot(
        sample, text_extent=lambda *_: Rect(0.0, 0.0, 0.012, 0.005)
    )
    assert result.body.bounds == pytest.approx((0.095, 0.2, 0.1, 0.212))


@pytest.mark.parametrize(
    "change", ({"reference": 0}, {"inverted": 1}, {"height_m": float("nan")})
)
def test_unproven_text_frame_fails_instead_of_guessing(change):
    with pytest.raises(ValueError):
        bounds_from_snapshot(
            snapshot(text_runs=(replace(text(), **change),)), text_extent=metrics
        )


def test_symbol_tokens_are_native_geometry_not_literal_font_strings():
    sample = snapshot(text_runs=(text("<MOD-DIAM>", (0.051, 0.051)),))
    result = bounds_from_snapshot(
        sample,
        text_extent=lambda *_: pytest.fail("symbol passed to font metrics"),
        symbol_extent=lambda _: (0.15, 0.0, 0.85, 1.0),
    )
    assert result.text_boxes[0].bounds == pytest.approx((0.05, 0.05, 0.07, 0.057))


def test_unframed_diameter_cell_uses_native_advance_to_next_value():
    sample = snapshot(
        kind=4,
        lines=(),
        text_runs=(text("<MOD-DIAM>", (0.05, 0.04)), text("9.525", (0.055, 0.04005))),
    )
    result = bounds_from_snapshot(
        sample, text_extent=metrics, symbol_extent=lambda _: (0.15, 0.0, 0.85, 1.0)
    )
    assert result.text_boxes[0].bounds == pytest.approx((0.05, 0.04, 0.055, 0.04605))


def test_unframed_unknown_symbol_has_no_nominal_box():
    sample = snapshot(
        kind=4,
        lines=(),
        text_runs=(text("<MOD-OTHER>"), text("9.525", (0.055, 0.04005))),
    )
    with pytest.raises(ValueError, match="uncalibrated"):
        bounds_from_snapshot(
            sample, text_extent=metrics, symbol_extent=lambda _: (0.15, 0.0, 0.85, 1.0)
        )


def test_unknown_symbol_fails_without_a_native_definition():
    with pytest.raises(ValueError, match="symbol"):
        bounds_from_snapshot(
            snapshot(text_runs=(text("<UNKNOWN-TOKEN>"),)), text_extent=metrics
        )


def test_note_uses_documented_native_sheet_extent():
    sample = snapshot(
        kind=6, text_runs=(), lines=(), note_extent=(0.02, 0.03, 0.06, 0.04)
    )
    assert bounds_from_snapshot(sample, text_extent=metrics).body.bounds == (
        0.02,
        0.03,
        0.06,
        0.04,
    )


def test_rich_note_uses_native_extent_not_uncalibrated_base_font():
    sample = snapshot(
        kind=6,
        text_runs=(replace(text(), font="Arial"),),
        lines=(),
        note_extent=(0.02, 0.03, 0.06, 0.04),
        format_signature=(),
    )
    assert bounds_from_snapshot(
        sample, text_extent=lambda *_: pytest.fail("remeasured rich note")
    ).body.bounds == (0.02, 0.03, 0.06, 0.04)


def test_native_center_mark_strokes_are_measured_instead_of_assumed_inside_view():
    sample = snapshot(
        kind=13,
        text_runs=(),
        lines=(
            Segment((0.01, 0.02), (0.09, 0.02)),
            Segment((0.05, 0.01), (0.05, 0.03)),
        ),
    )
    assert bounds_from_snapshot(sample).envelope.bounds == (0.01, 0.01, 0.09, 0.03)


def test_lone_centerline_has_native_print_thickness_not_invented_layout_width():
    sample = snapshot(
        kind=15, text_runs=(), lines=(Segment((0.05, 0.01), (0.05, 0.08), 0.00018),)
    )
    assert bounds_from_snapshot(sample).body.bounds == pytest.approx(
        (0.04991, 0.00991, 0.05009, 0.08009)
    )


@pytest.mark.skipif(sys.platform != "win32", reason="Windows GDI positive control")
def test_actual_missing_gdi_font_is_not_silently_substituted():
    with pytest.raises(ValueError, match="substituted"):
        _gdi_cell("Missing CAD Font 7192", "Ra 1.6")


def test_nonrectangular_dimension_extensions_do_not_expand_text_body():
    sample = snapshot(kind=4, lines=(Segment((0.01, 0.01), (0.05, 0.04)),))
    result = bounds_from_snapshot(sample, text_extent=metrics)
    assert result.body.bounds == pytest.approx((0.05, 0.04, 0.11, 0.046))
    assert result.envelope.bounds == pytest.approx((0.01, 0.01, 0.11, 0.046))


@pytest.mark.parametrize(
    "signature",
    (
        ("Arial", 0.0035, 13, False, 1.0, False, False),
        ("Century Gothic", 0.0035, 10, False, 1.0, False, False),
        ("Century Gothic", 0.0035, 13, False, 1.0, True, False),
    ),
)
def test_uncalibrated_font_or_height_mapping_is_rejected(signature):
    with pytest.raises(ValueError):
        font_cell_extent(text(), signature)


@pytest.mark.skipif(sys.platform != "win32", reason="Windows GDI calibration witness")
def test_real_gdi_metric_matches_saved_basic_dimension_cell():
    # Matching PDF transform and native frame were independently captured by
    # probe_drawing_annotation_bounds, not derived from this function.
    cell = font_cell_extent(text("24.00"), snapshot().format_signature)
    assert cell.xmax - cell.xmin == pytest.approx(0.0116375, abs=0.00006)
    assert cell.ymax - cell.ymin == pytest.approx(0.00555625, abs=0.00006)


@pytest.mark.skipif(sys.platform != "win32", reason="Windows GDI positive control")
def test_actual_font_side_bearing_covers_negative_j_overhang():
    assert _gdi_cell("Century Gothic", "j").xmin < 0
