"""Offline contract for the pen fitter package (MHA-PN-00)."""

import math
from pathlib import Path

import pytest

import build_pn_pen_assembly as builder
import draw_pn_pen_assembly as drawing
import pn_pen_adjust_screw_spec as stud
import pn_pen_assembly_sheet as notes
import pn_pen_assembly_spec as spec
import pn_pen_explode_spec as explode
import pn_pen_carriage_geom as carriage
import pn_pen_frame_spec as frame
import pn_pen_hanger_spec as hanger
import pn_pen_rod_spec as rod
import pn_pen_v_block_spec as v_block
import pn_vn_pen_marker_spec as marker
import sh_vn_arbor_set_screw_spec as rod_set_screw
import _mcmaster_99607a213 as thumb_screw
from _buildgraph import module_deps_of
from _drawing_common import is_pictorial_orientation
from _drawing_registry import DRAWINGS_BY_NAME
from _hole_spec import THREAD_MAJOR_MM
from _named_views import octant_axes
from _printed_tolerance import printed_band_mm, printed_deviations
from _simplified_names import simplified_name


def _engagements(stud_length: float, head_height: float) -> list[float]:
    """Thread in the rod for a stud of ``stud_length`` with its head top set
    ``head_height`` ±STUD_TOLERANCE_MM above the rod top."""
    band = spec.STUD_TOLERANCE_MM
    return [stud_length - (head_height + offset) for offset in (-band, band)]


def test_stud_set_from_its_measured_length_holds_engagement_at_both_extremes() -> None:
    # Code review C05: the head top is set the stud's measured length less the
    # nominal engagement. The stud prints 1.02 (.XX about the 26.0 closure)
    # and the rod tap's full thread .18 (.XX, ±.01).
    floor = 1.5 * THREAD_MAJOR_MM[stud.THREAD]
    depth = rod.STUD_TAP_SPEC.overrides_mm["ThreadDepth"] - printed_band_mm(
        2, unit=rod.UNIT
    )
    assert depth == pytest.approx(spec.TAP_THREAD_DEPTH_MIN) == pytest.approx(4.318)
    shortest, longest = spec.STUD_LENGTH_EXTREMES
    low, high = printed_deviations(stud.OVERALL_LENGTH, 2, unit=stud.UNIT)
    assert (shortest, longest) == pytest.approx(
        (stud.OVERALL_LENGTH + low, stud.OVERALL_LENGTH + high)
    )
    # Owner ruling: head = measured length less 3.2 (.126), ±.015; 22.8 nominal.
    assert rod.STUD_ENGAGEMENT == pytest.approx(3.2)
    assert spec.STUD_HEIGHT == pytest.approx(22.8)
    worst = [
        engagement
        for length in (shortest, longest)
        for engagement in _engagements(length, spec.stud_head_setting(length))
    ]
    assert min(worst) == pytest.approx(2.819) and min(worst) >= floor
    assert max(worst) == pytest.approx(3.581) and max(worst) < depth
    # The shortest accepted full thread still carries the deepest engagement,
    # the jam nut and the pen-height adjustment.
    assert stud.FULL_THREAD_LENGTH - printed_band_mm(2, unit=stud.UNIT) >= (
        max(worst) + stud.jam_nut.THICKNESS + stud.ADJUSTMENT_RANGE
    )


def test_stud_setting_prints_as_a_reference() -> None:
    assert notes.REFERENCE_DIMENSIONS == {spec.STUD_DIMENSION}
    assert spec.STUD_DIMENSION not in notes.DIMENSION_TOLERANCES
    assert spec.STUD_DIMENSION not in notes.TOLERANCE_PRECISION


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


def test_sheet_text_stays_out_of_the_assembly_recipe() -> None:
    # Recipe closures are file-granular: a wording edit in the sheet module
    # must re-key only the drawing, never the native pen assembly (code review
    # C03).
    def closure(module: object) -> set[str]:
        return {Path(path).name for path in module_deps_of(Path(module.__file__))}

    assembly = closure(builder)
    assert "pn_pen_assembly_spec.py" in assembly
    assert "pn_pen_assembly_sheet.py" not in assembly
    assert "pn_pen_assembly_sheet.py" in closure(drawing)
    for name in (
        "DRAWING_NUMBER",
        "ITEM",
        "REFERENCE_DIMENSIONS",
        "DIMENSION_TOLERANCES",
        "ANGULAR_TOLERANCES",
        "TOLERANCE_PRECISION",
        "DIMENSION_NOMINALS",
        "BOM_DESCRIPTIONS",
        "DIMENSION_CALLOUTS",
        "SETTINGS_NOTE",
        "ASSEMBLY_STEPS",
        "ASSEMBLY_CHECKS",
    ):
        assert not hasattr(spec, name), name
    assert not hasattr(explode, "exploded_point")


def test_pen_package_is_three_landscape_sheets_at_half_scale() -> None:
    assert drawing.SHEET_NAMES == (
        "ASSEMBLED VIEWS + SETTINGS",
        "EXPLODED VIEW + BOM",
        "FINISHED ASSEMBLY",
    )
    assert set(drawing.SHEET_LAYOUTS.values()) == {
        DRAWINGS_BY_NAME["pn_pen_assembly"].layout
    }
    assert set(drawing.SHEET_SCALES.values()) == {(1.0, 2.0)}
    assert drawing.EXPLODED_SCALES[0] == drawing.SHEET_SCALE


def test_bom_covers_every_family_in_builder_order_with_registry_identity() -> None:
    assert drawing.BOM_COMPONENTS == tuple(
        drawing.BOM_ROW_KEYS[stem] for stem in spec.BOM_ORDER
    )
    assert set(drawing.BALLOON_ANCHORS) == set(drawing.BOM_COMPONENTS)
    assert [notes.ITEM[stem] for stem in spec.BOM_ORDER] == list(
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


def _dot(a: tuple[float, ...], b: tuple[float, ...]) -> float:
    return sum(x * y for x, y in zip(a, b))


def _sheet(direction: tuple[float, ...], axes=None) -> tuple[float, float]:
    """``direction`` (model) on the exploded view's sheet: (right, up)."""
    right, up, _toward = axes or spec.EXPLODED_VIEW_AXES
    return _dot(direction, right), _dot(direction, up)


def _placed(rows, local: tuple[float, ...]) -> tuple[float, ...]:
    """A part-local direction in model coordinates (``rows``: images of the
    local axes)."""
    return tuple(sum(local[i] * rows[i][j] for i in range(3)) for j in range(3))


def test_exploded_camera_is_the_isometric_turned_about_y() -> None:
    assert drawing.EXPLODED_ORIENTATION == spec.EXPLODED_VIEW
    # Placed, styled and audited as a pictorial.
    assert is_pictorial_orientation(spec.EXPLODED_VIEW)
    assert spec.EXPLODED_VIEW_STANDARD == 7
    turn = spec.EXPLODED_VIEW_TURN
    assert turn[1] == (0.0, 1.0, 0.0)
    for axis, turned in zip(octant_axes(1, 1, 1), spec.EXPLODED_VIEW_AXES):
        assert turned == pytest.approx(_placed(turn, axis), abs=1e-12)
    right, up, toward = spec.EXPLODED_VIEW_AXES
    # Orthonormal and right-handed, model +Y straight up the sheet.
    for a in spec.EXPLODED_VIEW_AXES:
        assert _dot(a, a) == pytest.approx(1.0)
    assert _dot(right, up) == pytest.approx(0.0, abs=1e-12)
    assert _dot(up, toward) == pytest.approx(0.0, abs=1e-12)
    cross = (
        up[1] * toward[2] - up[2] * toward[1],
        up[2] * toward[0] - up[0] * toward[2],
        up[0] * toward[1] - up[1] * toward[0],
    )
    assert cross == pytest.approx(right, abs=1e-12)
    assert right[1] == pytest.approx(0.0, abs=1e-12) and up[1] > 0.0


def test_exploded_view_draws_the_set_screw_way_out_off_the_vertical() -> None:
    """Machinist review, farm run 20261023T222629630Z: from the REAR-TOP-LEFT
    octant the screw's way out of the front-face tap drew straight down the
    sheet, parallel to the block's verticals, and read as a screw entering
    the block's bottom face."""
    # The tap opens on the block's front face (local -Z, BODY_Z0).
    normal = _block_axis(2, -1.0)
    assert _dot(normal, spec.EXPLODED_VIEW_AXES[2]) > 0.5
    # Straight out of the tap, and past the screw's own recess in it.
    length = _along(_moves((spec.ROD_SET_SCREW,)), normal)
    assert length > v_block.SET_SCREW_TAP_LENGTH + 2 * rod_set_screw.LENGTH
    # On the sheet the way out runs well off the vertical model +Y draws.
    x, y = _sheet(normal)
    assert math.degrees(math.atan2(abs(x), abs(y))) > 30.0
    # The old octant (the negative control) drew it vertical.
    x, _y = _sheet(normal, octant_axes(-1, 1, -1))
    assert x == pytest.approx(0.0, abs=1e-12)


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
    # In the exploded view the slide-off axis runs sheet-right, nearly in the
    # sheet, off the paper end the reader sees: the stirrup stands off the
    # block's paper end at full length.
    x, y = _sheet(_block_axis(0, -1.0))
    assert x > 0.9 and abs(y) < 0.25
    assert _dot(_block_axis(0, -1.0), spec.EXPLODED_VIEW_AXES[2]) > 0.0
    face, end = notes.STIRRUP_TRAIL
    trail = [b - a for a, b in zip(face, end)]
    assert _along(trail, _block_axis(0)) == pytest.approx(explode.STIRRUP_CLEAR)


def test_wire_explodes_up_then_to_the_sheet_left() -> None:
    moves = _moves((spec.WIRE,))
    # Up off the eye, then an equal horizontal X/-Z pair that draws to the
    # reader's left, rising far less than it runs.
    assert moves[1] > 0.0
    assert moves[0] == -moves[2] > 0.0
    x, y = _sheet((moves[0], 0.0, moves[2]))
    assert x < 0.0 and abs(y) < abs(x) / 3.0
    assert drawing.BALLOON_ANCHORS[drawing.WIRE_ROW].point_mm is not None


def test_hanger_balloon_lands_mid_strap_clear_of_the_hanger_screw() -> None:
    """Machinist gate 2026-10-17: walked, the hanger's leader ran along screw
    11's shank to the strap's top corner, beside balloon 11's arrow."""
    x, y, z = drawing.BALLOON_ANCHORS[spec.HANGER].point_mm
    right = spec.EXPLODED_VIEW_AXES[0]
    # On the strap's sheet-rightmost long edge: the -x side's straight line
    # from the top corner to the foot corner, on the bar-seat face. The
    # view's sheet-right runs -x and +z.
    assert right[0] < 0.0 < right[2]
    (top_x, top_y), (foot_x, foot_y) = hanger.STRAP_OUTLINE[1], hanger.STRAP_OUTLINE[2]
    assert top_x == min(hanger.STRAP_TOP_X) and foot_x == min(hanger.STRAP_BOT_X)
    t = (y - top_y) / (foot_y - top_y)
    assert x == top_x + t * (foot_x - top_x)
    assert z == max(hanger.STRAP_Z)
    # Mid-length: well below the screw hole and above the upper U guide.
    assert t == 0.5
    assert y < hanger.SCREW_HOLE_XY[1] - 50.0
    assert y > max(hanger.GUIDE_PLATE_YS) + hanger.GUIDE_PLATE_T + 30.0


def test_rod_balloon_lands_on_its_sheet_right_corner() -> None:
    """Machinist review, farm run 20261023T222629630Z: anchored 15 mm up the
    square, leader 2 ran down across the v-block."""
    import pn_pen_rod_spec as rod

    x, y, z = drawing.BALLOON_ANCHORS[spec.ROD].point_mm
    right, _up, toward = spec.EXPLODED_VIEW_AXES
    # The square's sheet-right vertical corner, a silhouette: one of its two
    # faces toward the reader.
    half = rod.ROD_SECTION / 2.0
    assert (x, z) == (math.copysign(half, right[0]), math.copysign(half, right[2]))
    assert (x * toward[0] > 0.0) != (z * toward[2] > 0.0)
    assert y == drawing.ROD_ANCHOR_Y == 63.0
    assert 0.0 < y < rod.SQUARE_LENGTH


def test_thumb_screw_shows_clear_below_the_stirrup_rail_on_the_sheet() -> None:
    """Machinist review, farm run 20261023T222629630Z: 10 mm below the rail,
    the tip hid behind the rail's near half on the sheet, so the screw read as
    still threaded in."""
    up = spec.EXPLODED_VIEW_AXES[1]
    rail = [
        notes.exploded_point(
            spec.FRAME,
            carriage.block_to_machine((bx, carriage.FRAME_ORIGIN_LOCAL[1], bz)),
        )
        for bx in (carriage.FRAME_X0_LOCAL, carriage.FRAME_X0_LOCAL + frame.FRAME_DEPTH)
        for bz in (
            carriage.FRAME_ORIGIN_LOCAL[2],
            carriage.FRAME_ORIGIN_LOCAL[2] + frame.OUTER_WIDTH,
        )
    ]
    tip, _mouth = notes.THUMB_SCREW_TRAIL
    # Model mm; 4 mm on the sheet at 1:2.
    assert min(_dot(corner, up) for corner in rail) - _dot(tip, up) > 8.0


def test_stirrup_and_thumb_screw_balloons_land_on_their_own_parts() -> None:
    """Machinist review, farm run 20261023T222629630Z: walked, balloons 5 and
    6 landed side by side on the stirrup's bottom rail."""
    right, _up, toward = spec.EXPLODED_VIEW_AXES
    # The stirrup's: an outer vertical edge, the sheet-rightmost of the four,
    # three quarters up.
    x, y, z = drawing.BALLOON_ANCHORS[spec.FRAME].point_mm
    edges = [
        (ex, ez) for ex in (0.0, frame.OUTER_WIDTH) for ez in (0.0, frame.FRAME_DEPTH)
    ]
    assert (x, z) in edges and y == 0.75 * frame.OUTER_HEIGHT
    rows = carriage.FRAME_ROWS
    assert (x, z) == max(
        edges, key=lambda e: _dot(_placed(rows, (e[0], 0.0, e[1])), right)
    )
    # The thumb screw's: the knob's top rim, the head chamfer's inner edge on
    # the face the collar rises from, on the side toward the reader's lower right.
    x, y, z = drawing.BALLOON_ANCHORS[spec.THUMB_SCREW].point_mm
    assert x == thumb_screw.TS_HEAD_H
    assert math.hypot(y, z) == pytest.approx(
        thumb_screw.TS_HEAD_R - thumb_screw.HEAD_DIA / 16.0
    )
    side = _placed(carriage.THUMB_SCREW_ROWS, (0.0, y, z))
    assert _dot(side, right) > 0.0 and _dot(side, toward) > 0.0


def test_block_and_marker_balloons_land_off_the_rod_set_screw() -> None:
    """Walked in the turned view, the block's far-end corner and the marker's
    nib stand straight above the rod set screw, so their leaders ran past it."""
    x, y, z = drawing.BALLOON_ANCHORS[spec.V_BLOCK].point_mm
    # The front face's bottom edge, under the tap.
    assert (x, y, z) == (v_block.PIVOT_BORE_X, 0.0, v_block.BODY_Z0)
    x, y, z = drawing.BALLOON_ANCHORS[spec.MARKER].point_mm
    station, radius = marker.PROFILE[-4]
    # The edge round the back end, nearest the reader.
    assert y == station and math.hypot(x, z) == pytest.approx(radius)
    assert station > marker.OVERALL_LENGTH * 0.9
    # Its radial direction is the reader's, less the marker's axial part.
    toward = spec.EXPLODED_VIEW_AXES[2]
    axis = tuple(carriage.MARKER_ROWS[1])
    radial = tuple(t - _dot(toward, axis) * a for t, a in zip(toward, axis))
    facing = _placed(carriage.MARKER_ROWS, (x / radius, 0.0, z / radius))
    assert facing == pytest.approx(tuple(r / math.hypot(*radial) for r in radial))


def test_every_setting_is_printed_with_a_callout_beside_its_detail() -> None:
    printed = {
        name for points in drawing.DIMENSION_TEXT_POINTS.values() for name in points
    } | set(drawing.RIGHT_TEXT_POINTS)
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


def test_rod_travel_prints_on_right_and_the_check_cites_it() -> None:
    """Machinist review R5 (rule 22): the rod's travel acceptance printed only
    in ASSEMBLY.md. RIGHT carries it natively, a band about the block top's
    rest station below the upper guide top, the same stroke the check cites."""
    assert drawing.RIGHT_TEXT_POINTS == {spec.TRAVEL_DIMENSION: notes.TRAVEL_TEXT_POINT}
    assert spec.TRAVEL_REFERENCE == pytest.approx(
        hanger.GUIDE_SPAN_Y[1] - carriage.BLOCK_TOP_Y
    )
    assert notes.DIMENSION_TOLERANCES[spec.TRAVEL_DIMENSION] == pytest.approx(
        carriage.PEN_TRAVEL_HALF_MM, abs=0.005 * 25.4
    )
    # The text stands sheet-right of the rod (machine -Z in a Right view),
    # level with the span, clear of the U guides' noses.
    _x, y, z = notes.TRAVEL_TEXT_POINT
    (_u, top), (_u2, bottom) = spec.TRAVEL_LINE
    assert bottom < y < top
    nose = carriage.PEN_Z_MID - hanger.GUIDE_NOSE
    assert z < nose
    check = notes.ASSEMBLY_CHECKS[0]
    assert "OVER ITS ±.59 TRAVEL" in check
    assert "(RIGHT VIEW: BLOCK TOP 2.74 ±.59 BELOW THE UPPER GUIDE TOP)" in check


def test_each_detail_title_carries_its_letter_and_any_other_direction() -> None:
    keys = {detail.key for detail in drawing.DETAILS}
    assert set(drawing.BOUNDED_ON) <= keys
    assert drawing.LETTERED_LEFT <= set(drawing.BOUNDED_ON)
    for detail in drawing.DETAILS:
        lines = detail.title.splitlines()
        kind = "VIEW" if detail is drawing.CARRIAGE_DETAIL else "DETAIL"
        assert lines[0].startswith(f"{kind} {notes.DETAIL_LETTERS[detail.key]}")
        # A circled detail enlarges what its circle holds: drawn from its
        # parent view's direction, unturned, its title naming no other.
        if detail.key in drawing.BOUNDED_ON:
            assert detail.orientation == drawing.BOUNDED_ON[detail.key]
            assert detail.axis_points is None and detail.turn_cw_deg is None
            assert " - FROM " not in lines[0] and "ROTATED" not in detail.title
        else:
            # The turned plan, named by its viewing arrow: its title says
            # which way it looks and how far it is turned.
            assert detail is drawing.CARRIAGE_DETAIL
            assert " - FROM ABOVE" in lines[0]
            assert lines[1] == f"ROTATED {detail.turn_cw_deg:g} DEG CW"
    assert len(set(notes.DETAIL_LETTERS.values())) == len(drawing.DETAILS)


def test_carriage_turn_is_the_marker_axis_angle_in_the_plan() -> None:
    # The plan as placed draws machine X along sheet +x, machine -Z along +y.
    (x0, _, z0), (x1, _, z1) = drawing.CARRIAGE_DETAIL.axis_points
    angle = math.degrees(math.atan2(z0 - z1, x1 - x0))
    assert drawing.CARRIAGE_DETAIL.turn_cw_deg == pytest.approx(angle, abs=1e-6)
    assert 0.0 < angle < 90.0


def test_carriage_viewing_arrow_points_down_onto_the_block_clear_of_d() -> None:
    """Machinist review, farm run 20261024T091056564Z: C and D had no mark on
    any parent view. D is circled on FRONT; C's arrow points down onto the
    block top beside it."""
    x, y, z = notes.CARRIAGE_ARROW_TIP
    assert z == carriage.PEN_Z_MID
    # Over the block top, nib-ward of the rod and its square.
    assert y > carriage.BLOCK_TOP_Y
    assert x < carriage.PEN_ROD_X - carriage.ROD_HALF_DIAGONAL
    # FRONT projects Z away: the tip stands off D's circle by the clearance.
    d = drawing.STIRRUP_DETAIL
    scale = drawing.SHEET_SCALE[0] / drawing.SHEET_SCALE[1] / 1000.0
    gap = math.dist((x, y), d.model_centre[:2]) - d.radius_mm
    assert gap * scale >= drawing.VIEW_ARROW_CIRCLE_CLEARANCE


def test_stirrup_detail_shows_the_window_and_the_thumb_screw_tap_off_the_title_block() -> None:
    """Machinist review 2026-10-17: the stirrup's window and the thumb screw's
    tap in its bottom rail showed nowhere the reader could read them; the
    exploded view then saw the stirrup edge-on."""
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


def test_settings_note_respects_the_measured_note_width() -> None:
    assert max(map(len, drawing.SETTINGS_NOTE.splitlines())) <= drawing.SETTINGS_NOTE_WIDTH
