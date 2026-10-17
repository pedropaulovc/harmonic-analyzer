"""Offline contract for the pen fitter package (MHA-PN-000)."""

from pathlib import Path

import pytest

import build_pn_pen_assembly as builder
import draw_pn_pen_assembly as drawing
import pn_pen_adjust_screw_spec as stud
import pn_pen_assembly_notes as notes
import pn_pen_assembly_spec as spec
import pn_pen_carriage_geom as carriage
import pn_pen_rod_spec as rod
import pn_pen_v_block_spec as v_block
import vn_pen_rod_set_screw_spec as rod_set_screw
from _buildgraph import module_deps_of
from _drawing_registry import DRAWINGS_BY_NAME
from _hole_spec import THREAD_MAJOR_MM
from _named_views import octant_axes, octant_view_name
from _printed_tolerance import printed_band_mm
from _simplified_names import simplified_name


def _engagements(stud_length: float, head_height: float) -> list[float]:
    """Thread in the rod for a stud of ``stud_length`` with its head top set
    ``head_height`` ±STUD_TOLERANCE_MM above the rod top."""
    band = spec.STUD_TOLERANCE_MM
    return [stud_length - (head_height + offset) for offset in (-band, band)]


def test_stud_set_from_its_measured_length_holds_engagement_at_both_extremes() -> None:
    # Code review C05: the stud prints 26.0 (.X, ±0.8) and the rod tap's full
    # thread 4.50 (.XX, ±0.51). Between 1.5 D and the shallowest accepted
    # thread lie 1.70, and the stud band alone spans 1.6.
    floor = 1.5 * THREAD_MAJOR_MM[stud.THREAD]
    depth = rod.STUD_TAP_SPEC.overrides_mm["ThreadDepth"] - printed_band_mm(2)
    assert depth == pytest.approx(spec.TAP_THREAD_DEPTH_MIN) == pytest.approx(3.99)
    shortest, longest = spec.STUD_LENGTH_EXTREMES
    assert (shortest, longest) == pytest.approx(
        (stud.OVERALL_LENGTH - printed_band_mm(1), stud.OVERALL_LENGTH + printed_band_mm(1))
    )
    # Owner ruling: head = measured length less 3.2, ±0.4; 22.8 nominal.
    assert rod.STUD_ENGAGEMENT == pytest.approx(3.2)
    assert spec.STUD_HEIGHT == pytest.approx(22.8)
    worst = [
        engagement
        for length in (shortest, longest)
        for engagement in _engagements(length, spec.stud_head_setting(length))
    ]
    assert min(worst) == pytest.approx(2.8) and min(worst) >= floor
    assert max(worst) == pytest.approx(3.6) and max(worst) < depth
    # Any one fixed head height, the old 22.0 or the new nominal, fails one
    # end of the stud band: the setting has to follow the measured length.
    for fixed in (22.0, spec.STUD_HEIGHT):
        reach = [e for n in (shortest, longest) for e in _engagements(n, fixed)]
        assert min(reach) < floor or max(reach) >= depth, fixed
    # The shortest accepted full thread still carries the deepest engagement,
    # the jam nut and the pen-height adjustment.
    assert stud.FULL_THREAD_LENGTH - printed_band_mm(1) >= (
        max(worst) + stud.jam_nut.THICKNESS + stud.ADJUSTMENT_RANGE
    )


def test_stud_setting_prints_as_a_reference_with_the_measured_length_rule() -> None:
    assert spec.REFERENCE_DIMENSIONS == {spec.STUD_DIMENSION}
    assert spec.STUD_DIMENSION not in spec.DIMENSION_TOLERANCES
    assert spec.STUD_DIMENSION not in spec.TOLERANCE_PRECISION
    builder_source = Path(builder.__file__).read_text(encoding="utf-8")
    assert "spec.STUD_TOLERANCE_MM" not in builder_source
    assert notes.DIMENSION_CALLOUTS[spec.STUD_DIMENSION].endswith(
        "STUD LENGTH\nLESS 3.2 ±0.4"
    )
    steps = " ".join(notes.ASSEMBLY_STEPS)
    assert "THE STUD'S MEASURED LENGTH LESS 3.2 ±0.4 ABOVE THE ROD TOP" in steps
    assert "22.8 FOR A 26.0 STUD" in steps
    assert "22.0" not in steps


def test_pen_package_keeps_registry_outputs() -> None:
    registered = DRAWINGS_BY_NAME["pn_pen_assembly"]
    assert registered.source_kind == "assembly"
    assert registered.part == "pn_pen"
    assert drawing.SOURCE == registered.source
    assert drawing.OUTPUTS == drawing.OUTPUTS.__class__(
        registered.outputs["slddrw"],
        registered.outputs["pdf"],
        registered.outputs["png"],
    )
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "build_simple_three_view_drawing" not in source


def test_sheet_text_stays_out_of_the_assembly_recipe() -> None:
    # Recipe closures are file-granular: a wording edit in the notes must
    # re-key only the drawing, never the native pen assembly (code review C03).
    def closure(module: object) -> set[str]:
        return {Path(path).name for path in module_deps_of(Path(module.__file__))}

    assembly = closure(builder)
    assert "pn_pen_assembly_spec.py" in assembly
    assert "pn_pen_assembly_notes.py" not in assembly
    assert "pn_pen_assembly_notes.py" in closure(drawing)
    for name in (
        "BOM_DESCRIPTIONS",
        "DIMENSION_CALLOUTS",
        "SETTINGS_NOTE",
        "ASSEMBLY_STEPS",
        "ASSEMBLY_CHECKS",
    ):
        assert not hasattr(spec, name), name


def test_pen_package_is_three_landscape_sheets_at_half_scale() -> None:
    assert drawing.SHEET_NAMES == (
        "ASSEMBLED VIEWS + SETTINGS",
        "EXPLODED VIEW + BOM",
        "ASSEMBLY STEPS",
    )
    assert set(drawing.SHEET_LAYOUTS.values()) == {
        DRAWINGS_BY_NAME["pn_pen_assembly"].layout
    }
    assert set(drawing.SHEET_SCALES.values()) == {(1.0, 2.0)}
    assert drawing.EXPLODED_SCALES[0] == drawing.SHEET_SCALE


def test_bom_covers_every_family_in_builder_order_with_registry_identity() -> None:
    assert drawing.BOM_COMPONENTS == spec.BOM_ORDER
    assert set(drawing.BALLOON_ANCHORS) == set(spec.BOM_ORDER)
    assert [spec.ITEM[stem] for stem in spec.BOM_ORDER] == list(
        range(1, len(spec.BOM_ORDER) + 1)
    )
    # The builder inserts the hanger, the rod, then the riders in RIDERS
    # order, then the hanger screw and its nuts: the BOM's item order.
    riders = tuple(stem for stem, *_ in builder.RIDERS)
    assert spec.BOM_ORDER[2 : 2 + len(riders)] == riders
    assert all(
        number.startswith("MHA-") for number in drawing.BOM_PART_NUMBERS.values()
    )
    assert drawing.BOM_SKUS[spec.HANGER] == drawing.MADE_PART_SKU
    assert drawing.BOM_SKUS[spec.HANGER_JAM_NUT] != drawing.MADE_PART_SKU


def test_explode_names_match_the_builder() -> None:
    assert drawing.EXPLODED_VIEW_NAMES == {
        "Default": spec.EXPLODED_VIEW_NAME,
        "Default Simplified": simplified_name(spec.EXPLODED_VIEW_NAME),
    }
    for configuration, name in drawing.EXPLODED_VIEW_NAMES.items():
        assert builder.pn_exploded_view_name(configuration) == name


def test_exploded_octant_faces_the_set_screw_tap_and_explodes_along_it() -> None:
    assert drawing.EXPLODED_ORIENTATION == octant_view_name(*spec.EXPLODED_OCTANT)
    # The tap opens on the block's front face (local -Z, BODY_Z0).
    rows = carriage.BLOCK_ROWS
    normal = tuple(-rows[2][axis] for axis in range(3))
    viewer = octant_axes(*spec.EXPLODED_OCTANT)[2]
    assert sum(n * v for n, v in zip(normal, viewer)) > 0.5
    moves = [0.0, 0.0, 0.0]
    for _label, stems, key, distance in spec.EXPLODE_STEPS:
        if stems == (spec.ROD_SET_SCREW,):
            moves["xyz".index(key)] += distance
    length = sum(value * value for value in moves) ** 0.5
    # Straight out of the tap, and past the screw's own recess in it.
    assert all(abs(m / length - n) < 1e-9 for m, n in zip(moves, normal))
    assert length > v_block.SET_SCREW_TAP_LENGTH + 2 * rod_set_screw.LENGTH


def test_rod_set_screw_trail_runs_up_the_tap_axis_to_its_mouth() -> None:
    moves = [0.0, 0.0, 0.0]
    for _label, stems, key, distance in spec.EXPLODE_STEPS:
        if stems == (spec.ROD_SET_SCREW,):
            moves["xyz".index(key)] += distance
    cup, mouth = notes.ROD_SET_SCREW_TRAIL
    trail = [b - a for a, b in zip(cup, mouth)]
    out = sum(value * value for value in moves) ** 0.5
    length = sum(value * value for value in trail) ** 0.5
    # Back along the screw's own way out, short of it by the tap's depth.
    assert all(abs(t + m * length / out) < 1e-9 for t, m in zip(trail, moves))
    assert abs(length - (out - v_block.SET_SCREW_TAP_LENGTH)) < 1e-6


def test_wire_explodes_up_then_straight_to_the_sheet_left() -> None:
    moves = [0.0, 0.0, 0.0]
    for _label, stems, key, distance in spec.EXPLODE_STEPS:
        if stems == (spec.WIRE,):
            moves["xyz".index(key)] += distance
    sx, _sy, sz = spec.EXPLODED_OCTANT
    # The octant view's sheet-right is (sz, 0, -sx); the aside pair runs
    # against it with no out-of-plane part.
    assert moves[1] > 0.0
    assert moves[0] * sz + moves[2] * -sx < 0.0
    assert moves[0] * -sx + moves[2] * -sz == 0.0
    assert drawing.BALLOON_ANCHORS[spec.WIRE].point_mm is not None


def test_every_setting_is_printed_with_a_callout_beside_its_detail() -> None:
    printed = {
        name for points in drawing.DIMENSION_TEXT_POINTS.values() for name in points
    }
    marked = {name for names in spec.DRAWING_DIMENSIONS.values() for name in names}
    assert printed == marked == set(notes.DIMENSION_CALLOUTS)
    details = {detail.key: detail for detail in drawing.DETAILS}
    for key, points in drawing.DIMENSION_TEXT_POINTS.items():
        detail = details[key]
        assert detail.feature is not None
        for xyz in points.values():
            # The plan detail projects Y away; the front detail projects Z.
            # A text may stand outside the crop circle (the nib preset's sits
            # beyond the nib tip), but beside it, not across the sheet.
            axes = (0, 2) if detail.orientation == "*Top" else (0, 1)
            offset = [xyz[axis] - detail.model_centre[axis] for axis in axes]
            assert sum(value * value for value in offset) ** 0.5 < 2 * detail.radius_mm


def test_each_detail_title_carries_its_letter_and_any_other_direction() -> None:
    keys = {detail.key for detail in drawing.DETAILS}
    assert drawing.BOUNDED_ON_RIGHT <= keys
    for detail in drawing.DETAILS:
        first = detail.title.splitlines()[0]
        assert first.startswith(f"DETAIL {notes.DETAIL_LETTERS[detail.key]}")
        # A detail circled on RIGHT enlarges what the circle holds: drawn from
        # the right, unturned, its title naming no other direction.
        if detail.key in drawing.BOUNDED_ON_RIGHT:
            assert detail.orientation == "*Right" and detail.axis_points is None
            assert " - FROM " not in first
        else:
            assert " - FROM " in first
    assert len(set(notes.DETAIL_LETTERS.values())) == len(drawing.DETAILS)


def test_text_blocks_respect_the_measured_note_width() -> None:
    for block, width in (
        (drawing.ASSEMBLY_STEPS, drawing.STEPS_LINE_WIDTH),
        (drawing.ASSEMBLY_CHECKS, drawing.STEPS_LINE_WIDTH),
        (drawing.SETTINGS_NOTE, drawing.SETTINGS_NOTE_WIDTH),
    ):
        assert max(len(line) for line in block.splitlines()) <= width
