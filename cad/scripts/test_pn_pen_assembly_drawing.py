"""Offline contract for the pen fitter package (MHA-PN-000)."""

from pathlib import Path

import pytest

import build_pn_pen_assembly as builder
import draw_pn_pen_assembly as drawing
import pn_pen_adjust_screw_spec as stud
import pn_pen_assembly_notes as notes
import pn_pen_assembly_spec as spec
import pn_pen_explode_spec as explode
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
        "Default": explode.EXPLODED_VIEW_NAME,
        "Default Simplified": simplified_name(explode.EXPLODED_VIEW_NAME),
    }
    for configuration, name in drawing.EXPLODED_VIEW_NAMES.items():
        assert explode.exploded_view_name(configuration) == name
    with pytest.raises(ValueError):
        explode.exploded_view_name("Operational")


def _moves(stems: tuple[str, ...]) -> list[float]:
    """The summed world move of the explode steps that move exactly ``stems``."""
    moves = [0.0, 0.0, 0.0]
    for _label, step_stems, key, distance in explode.EXPLODE_STEPS:
        if step_stems == stems:
            moves["xyz".index(key)] += distance
    return moves


def _along(vector: list[float], axis: tuple[float, ...]) -> float:
    """``vector``'s length, asserting it runs along the unit ``axis``."""
    length = sum(value * value for value in vector) ** 0.5
    assert all(abs(v - length * a) < 1e-9 for v, a in zip(vector, axis)), (vector, axis)
    return length


def _block_axis(index: int, sign: float = 1.0) -> tuple[float, ...]:
    return tuple(sign * value for value in carriage.BLOCK_ROWS[index])


def test_exploded_octant_faces_the_set_screw_tap_and_explodes_along_it() -> None:
    assert drawing.EXPLODED_ORIENTATION == octant_view_name(*spec.EXPLODED_OCTANT)
    # The tap opens on the block's front face (local -Z, BODY_Z0).
    normal = _block_axis(2, -1.0)
    viewer = octant_axes(*spec.EXPLODED_OCTANT)[2]
    assert sum(n * v for n, v in zip(normal, viewer)) > 0.5
    # Straight out of the tap, and past the screw's own recess in it.
    length = _along(_moves((spec.ROD_SET_SCREW,)), normal)
    assert length > v_block.SET_SCREW_TAP_LENGTH + 2 * rod_set_screw.LENGTH


def test_rod_set_screw_trail_runs_up_the_tap_axis_to_its_mouth() -> None:
    out = _along(_moves((spec.ROD_SET_SCREW,)), _block_axis(2, -1.0))
    cup, mouth = notes.ROD_SET_SCREW_TRAIL
    trail = [b - a for a, b in zip(cup, mouth)]
    # Back along the screw's own way out, short of it by the tap's depth.
    length = _along(trail, _block_axis(2))
    assert abs(length - (out - v_block.SET_SCREW_TAP_LENGTH)) < 1e-6


def test_thumb_screw_explodes_down_its_tap_axis_clear_of_the_bottom_rail() -> None:
    """Machinist review 2026-10-17: the thumb screw sat under the V-block with
    no trail, its tap in the stirrup's bottom rail unshown."""
    # The tap's axis is the stirrup's (and the block's) vertical.
    assert _block_axis(1) == tuple(carriage.FRAME_ROWS[1])
    down = _along(_moves((spec.THUMB_SCREW,)), _block_axis(1, -1.0))
    engaged = carriage.MARKER_BOTTOM_LOCAL_Y - carriage.FRAME_ORIGIN_LOCAL[1]
    assert down == pytest.approx(engaged + explode.THUMB_SCREW_TRAIL_GAP)
    # The trail runs from the exploded tip straight up the axis to the tap's
    # mouth on the exploded bottom rail's underside.
    tip, mouth = notes.THUMB_SCREW_TRAIL
    trail = [b - a for a, b in zip(tip, mouth)]
    assert _along(trail, _block_axis(1)) == pytest.approx(explode.THUMB_SCREW_TRAIL_GAP)


def test_stirrup_slides_off_the_paper_end_with_its_thumb_screw_on_its_tap() -> None:
    """Machinist review 2026-10-17: the stirrup was drawn displaced diagonally,
    not along the neck it slides onto."""
    # Off the block, the stirrup moves in one step with its thumb screw, so the
    # screw stays on the rail's tap axis; no step moves the stirrup alone.
    frame_steps = {
        stems
        for _label, stems, _key, _d in explode.EXPLODE_STEPS
        if spec.FRAME in stems and spec.V_BLOCK not in stems
    }
    assert frame_steps == {(spec.FRAME, spec.THUMB_SCREW)}
    off = _along(_moves((spec.FRAME, spec.THUMB_SCREW)), _block_axis(0, -1.0))
    assert off == pytest.approx(carriage.FRAME_ORIGIN_LOCAL[0] + explode.STIRRUP_CLEAR)
    # In the octant view the slide-off axis lies in the sheet, running
    # sheet-right: the stirrup stands off the block's paper end at full length.
    sx, _sy, sz = spec.EXPLODED_OCTANT
    viewer = octant_axes(*spec.EXPLODED_OCTANT)[2]
    assert abs(sum(a * v for a, v in zip(_block_axis(0), viewer))) < 1e-12
    assert _block_axis(0, -1.0)[0] * sz + _block_axis(0, -1.0)[2] * -sx > 0.0
    face, end = notes.STIRRUP_TRAIL
    trail = [b - a for a, b in zip(face, end)]
    assert _along(trail, _block_axis(0)) == pytest.approx(explode.STIRRUP_CLEAR)


def test_wire_explodes_up_then_straight_to_the_sheet_left() -> None:
    moves = _moves((spec.WIRE,))
    sx, _sy, sz = spec.EXPLODED_OCTANT
    # The octant view's sheet-right is (sz, 0, -sx); the aside pair runs
    # against it with no out-of-plane part.
    assert moves[1] > 0.0
    assert moves[0] * sz + moves[2] * -sx < 0.0
    assert moves[0] * -sx + moves[2] * -sz == 0.0
    assert drawing.BALLOON_ANCHORS[spec.WIRE].point_mm is not None


def test_explode_module_qualifies_for_the_explode_tier() -> None:
    from _refresh_tier import explode_plan

    plan = explode_plan("pn_pen")
    assert (plan.decline, plan.module, plan.function) == (
        "",
        "_pn_pen_explode",
        "create_pn_explode",
    )
    # The global explode axes' helper is the explode's alone, as in pd.
    assert {Path(path).name for path in plan.closure} == {
        "_pn_pen_explode.py",
        "pn_pen_explode_spec.py",
        "_assembly_patterns.py",
    }


def test_hanger_balloon_lands_mid_strap_clear_of_the_hanger_screw() -> None:
    """Machinist gate 2026-10-17: walked, the hanger's leader ran along screw
    11's shank to the strap's top corner, beside balloon 11's arrow."""
    import pn_pen_hanger_spec as hanger

    x, y, z = drawing.BALLOON_ANCHORS[spec.HANGER].point_mm
    sx, _sy, sz = spec.EXPLODED_OCTANT
    # On the strap's sheet-rightmost long edge: the -x side's straight line
    # from the top corner to the foot corner, on the bar-seat face. The
    # octant's sheet-right is (sz, 0, -sx), so -x and +z both run sheet-right.
    assert (sz, -sx) == (-1, 1)
    (top_x, top_y), (foot_x, foot_y) = hanger.STRAP_OUTLINE[1], hanger.STRAP_OUTLINE[2]
    assert top_x == min(hanger.STRAP_TOP_X) and foot_x == min(hanger.STRAP_BOT_X)
    t = (y - top_y) / (foot_y - top_y)
    assert x == top_x + t * (foot_x - top_x)
    assert z == max(hanger.STRAP_Z)
    # Mid-length: well below the screw hole and above the upper U guide.
    assert t == 0.5
    assert y < hanger.SCREW_HOLE_XY[1] - 50.0
    assert y > max(hanger.GUIDE_PLATE_YS) + hanger.GUIDE_PLATE_T + 30.0


def test_rod_balloon_lands_low_on_its_viewer_corner() -> None:
    """Final build b9ae: anchored 40 mm up the square, the rod's bearing from
    the exploded view's centre sat just anticlockwise of thumb screw 6's tip,
    so leader 2 crossed leader 6. 15 mm up turns it past the thumb screw's."""
    import pn_pen_rod_spec as rod

    x, y, z = drawing.BALLOON_ANCHORS[spec.ROD].point_mm
    sx, _sy, sz = spec.EXPLODED_OCTANT
    # The square's vertical corner nearest the viewer, on the square itself.
    assert (x, z) == (sx * rod.ROD_SECTION / 2.0, sz * rod.ROD_SECTION / 2.0)
    assert y == 15.0
    assert 0.0 < y < rod.SQUARE_LENGTH / 4.0


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


def test_stirrup_detail_shows_the_window_and_the_thumb_screw_tap_off_the_title_block() -> None:
    """Machinist review 2026-10-17: the stirrup's window and the thumb screw's
    tap in its bottom rail showed nowhere the reader could read them; the
    exploded view sees the stirrup edge-on."""
    detail = drawing.STIRRUP_DETAIL
    assert detail in drawing.DETAILS and detail.feature is None
    assert {spec.FRAME, spec.THUMB_SCREW, spec.V_BLOCK} <= detail.stems
    # The crop reaches the thumb screw's head below the rail and the block top.
    head_y = carriage.THUMB_SCREW_POS[1]
    block_top_y = carriage.BLOCK_TOP_Y
    centre_y = detail.model_centre[1]
    assert centre_y - detail.radius_mm < head_y and centre_y + detail.radius_mm > block_top_y
    # Front views project Z away: the centre sits on the stirrup's mid-depth.
    frame_mid = carriage.block_to_machine(
        (carriage.FRAME_X_CENTER_LOCAL, 0.0, v_block.DEPTH_MID_Z)
    )
    assert detail.model_centre[0] == pytest.approx(frame_mid[0])
    x, y = detail.centre
    r = detail.crop_radius
    assert drawing._sheet_findings((x - r, y - r, x + r, y + r)) == []
    # Under the as-shipped note's top line and clear of DETAIL C's circle.
    assert y + r < drawing.SETTINGS_NOTE_XY[1]
    c = drawing.CARRIAGE_DETAIL
    assert (x - c.centre[0]) ** 2 + (y - c.centre[1]) ** 2 > (r + c.crop_radius) ** 2
    assert detail.label_xy[0] > x + r


def test_text_blocks_respect_the_measured_note_width() -> None:
    for block, width in (
        (drawing.ASSEMBLY_STEPS, drawing.STEPS_LINE_WIDTH),
        (drawing.ASSEMBLY_CHECKS, drawing.STEPS_LINE_WIDTH),
        (drawing.SETTINGS_NOTE, drawing.SETTINGS_NOTE_WIDTH),
    ):
        assert max(len(line) for line in block.splitlines()) <= width
