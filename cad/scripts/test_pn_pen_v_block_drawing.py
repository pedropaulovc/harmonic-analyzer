"""Offline contracts for the pen v-block part and its drawing."""

from __future__ import annotations

import math
import re
from pathlib import Path

import pytest

import build_pn_pen_v_block as part
import draw_pn_pen_v_block as drawing
import export_features
import pn_pen_v_block_spec as spec
from _drawing_registry import DRAWINGS_BY_NAME
from _gtol_face import FaceGeometry
from _hole_spec import TAP_DRILL_MM
from _printed_tolerance import printed_deviations

_VIEW_KEEPS = (
    drawing.FRONT_KEEP,
    drawing.RIGHT_KEEP,
    drawing.BOTTOM_KEEP,
    drawing.SECTION_KEEP,
)


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/pn-pen-v-block.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/pn-pen-v-block.pdf")
    assert drawing.PNG.as_posix().endswith("/png/pn-pen-v-block_drawing.png")
    assert DRAWINGS_BY_NAME["pn_pen_v_block"].script == Path(drawing.__file__).resolve()


def test_drawing_keeps_exactly_the_marked_dimensions() -> None:
    # The part marks the spec's map and the drawing keeps exactly its union,
    # each dimension in one view only.
    assert part.DRAWING_DIMENSIONS is spec.DRAWING_DIMENSIONS
    assert drawing.DRAWING_DIMENSIONS is spec.DRAWING_DIMENSIONS
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    kept = [name for keep in _VIEW_KEEPS for name in keep]
    assert len(kept) == len(set(kept))
    assert set(kept) == marked
    assert set(spec.DRAWING_PRECISION_BY_NAME) == marked
    assert drawing.DIMENSION_CALLOUTS is spec.DIMENSION_CALLOUTS
    assert drawing.DIMENSION_CALLOUTS_ABOVE is spec.DIMENSION_CALLOUTS_ABOVE
    assert set(spec.DIMENSION_CALLOUTS) <= marked
    assert set(spec.DIMENSION_CALLOUTS_ABOVE) <= marked
    for feature, name in spec.DIMENSION_PREFIXES:
        assert name in spec.DRAWING_DIMENSIONS[feature]


def test_every_feature_is_located_from_the_front_face() -> None:
    # drawing-guidelines.md rule 10: no feature across the depth by symmetry.
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert {
        "NeckZ0",
        "NeckZ1",
        "Depth",
        "VMouthZ0",
        "VMouthZ1",
        "ReliefZ0",
        "ReliefZ1",
        "PivotZ",
    } <= marked
    # One datum: the body's front face.  Every depth-wise station the print
    # states is a baseline from it.
    assert spec.depth_station(spec.BODY_Z0) == 0.0
    assert spec.depth_station(0.0) == spec.BODY_SIDE_STEP
    assert spec.depth_station(spec.BODY_Z1) == spec.BODY_DEPTH
    # Blind review final8 (the third time): printed in the paper-end view,
    # the neck's faces read as thin ribs.  The bottom view prints them, where
    # the neck's step is an outline change, from the outline's own baselines
    # off the body's front face; final9: the body's back face closes that row
    # (without it the neck's "20.10" read as the overall), so the V's sketch
    # keeps only the datum's stub and prints no depth.
    assert spec.DRAWING_DIMENSIONS["OutlineProfile"] == {
        "Length",
        "NeckZ0",
        "NeckZ1",
        "Depth",
    }
    assert not {"NeckZ0", "NeckZ1", "Depth"} & spec.DRAWING_DIMENSIONS["VGrooveProfile"]
    assert set(spec.REFERENCE_SKETCHES) <= set(spec.DRAWING_DIMENSIONS)
    # 3 mm past each end on paper.
    assert drawing._CENTERLINE_OVERSHOOT_MM * drawing._S == pytest.approx(0.003)


def test_hidden_reference_dimensions_reach_their_views() -> None:
    # Farm e7b8b6928: the plain targeted import delivered none of a hidden
    # sketch's dimensions (LighteningZ missing from the bottom view).  Every
    # view curates through _drawing_hidden_sketches, which shows a hidden
    # owner per view; the section, a derived view, is cut and curated while
    # the part shows its sketches, which lie in its cutting plane.
    assert set(spec.SECTION_REFERENCE_SKETCHES) <= set(spec.REFERENCE_SKETCHES)
    section_names = set().union(
        *(spec.DRAWING_DIMENSIONS[s] for s in spec.SECTION_REFERENCE_SKETCHES)
    )
    assert section_names <= set(drawing.SECTION_KEEP)
    for sketch in set(spec.REFERENCE_SKETCHES) - set(spec.SECTION_REFERENCE_SKETCHES):
        assert not spec.DRAWING_DIMENSIONS[sketch] & set(drawing.SECTION_KEEP)
    # The cutting line and the sketches' plane are the same x.
    assert {point[0] for point in drawing.SECTION_LINE_MODEL_MM} == {spec.PIVOT_BORE_X}


def test_relief_corners_print_r065_and_clear_the_grip_at_r070() -> None:
    # Owner ruling 2026-11-23, tool audit Q9: the relief's step corners print
    # 2X R.065 at three places (.060-.070, the title block's .XXX), naming
    # why they stand over INSIDE CORNERS R.040 MAX; at the band's greatest
    # they still clear the grip and the bore.
    assert spec.RELIEF_CORNER_R == pytest.approx(0.065 * 25.4)
    assert (spec.RELIEF_CORNER_R_MIN, spec.RELIEF_CORNER_R_MAX) == pytest.approx(
        (0.060 * 25.4, 0.070 * 25.4)
    )
    assert spec.DRAWING_PRECISION["ReliefProfile"]["ReliefCornerR"] == 3
    assert spec.DIMENSION_PREFIXES[("ReliefProfile", "ReliefCornerR")] == "2X R"
    assert spec.DIMENSION_CALLOUTS["ReliefCornerR"] == "NOTHING SEATS IN\nTHESE CORNERS"
    assert spec.RELIEF_CORNER_GRIP_MARGIN_MIN == pytest.approx(
        spec._GRIP_GAP_AT_BOTTOM - 0.070 * 25.4
    )
    assert spec.RELIEF_CORNER_GRIP_MARGIN_MIN >= 0.25


def test_relief_corner_callout_stands_off_the_part_beside_the_bottom_view() -> None:
    # Fan-out 2b-final (rule 14): inside the slot the three rows sat in the
    # bottom view's silhouette with the sheet right of it empty.  They stand
    # there now, right of the depth's line, over the title block, under the
    # paper-end view's rows; the leader rises from the near corner's centre
    # through the neck, clear of the V's mouth edge and under the ".08"'s
    # lower arrow (~6.2 mm from its extension line, measured on the 2b sheet).
    keep_x, keep_y = drawing.BOTTOM_KEEP["ReliefCornerR"]
    half_w, half_h = drawing._CORNER_TEXT_HALF_W, 0.0075
    left = keep_x - half_w
    depth_line = drawing.BOTTOM_KEEP["Depth"][0]
    assert left == pytest.approx(drawing._CORNER_TEXT_LEFT)
    assert left > depth_line + 0.005 > drawing._fx(0.0)
    assert keep_y - half_h > 0.0651 + 0.03  # the title block's top
    assert keep_y + half_h < drawing.RIGHT_KEEP["VMouthZ1"][1] - 0.0033 - 0.008
    assert keep_x + half_w < drawing.ISO_CENTER[0] - 0.0350 * 1.5 / 2.0 - 0.03
    centre_x, centre_y = drawing._CORNER_CENTRE
    shelf_y = keep_y - drawing._CORNER_SHELF_DROP
    slope = (shelf_y - centre_y) / (left - centre_x)
    assert 0.0 < slope < math.tan(math.radians(5.0))
    step_wall_y = centre_y + slope * (drawing._fx(spec.RELIEF_X0) - centre_x)
    assert step_wall_y > drawing._bz(spec.V_MOUTH_Z0) + 0.001
    neck_arrow_x = drawing.BOTTOM_KEEP["NeckZ0"][0]
    at_neck_arrow = centre_y + slope * (neck_arrow_x - centre_x)
    assert at_neck_arrow < drawing._bz(0.0) - 0.0062 - 0.0015


def test_pivot_bore_drops_wholly_into_the_slot_at_its_printed_limits() -> None:
    import pn_pen_carriage_geom as carriage
    import pn_vn_pen_marker_spec as marker

    # Review final4: with the step at 10.0 the reamed bore's edge stood 0.5
    # off it, and at the printed limits broke 0.8 into the step wall.  Both
    # stations are baselines from the paper end.
    worst_edge = (
        spec.PIVOT_BORE_X
        + _printed_devs(spec.PIVOT_BORE_X, "PivotX")[0]
        - (spec.PIVOT_BORE_DIA + spec.PIVOT_BORE_BAND[0]) / 2.0
    )
    worst_step = spec.RELIEF_X0 + _printed_devs(spec.RELIEF_X0, "ReliefX0")[1]
    assert spec.PIVOT_BORE_STEP_CLEARANCE_PRINTED_MIN == pytest.approx(
        worst_edge - worst_step
    )
    assert spec.PIVOT_BORE_STEP_CLEARANCE_PRINTED_MIN > 0.0
    # The grip seats on the whole V, spans it, and its body clears the
    # corner arcs.
    grip_length = marker.BARREL_END_Y - marker.BARREL_START_Y
    start, end = carriage.MARKER_GRIP_LOCAL_X
    assert end - start == pytest.approx(grip_length)
    seat = min(end, spec.RELIEF_X0) - max(start, 0.0)
    assert seat == spec.RELIEF_X0
    # The marker body's shoulder (its widest section, BODY_FRONT_DIA) must not
    # meet the step's corner arcs.  At the bottom face, where the body is
    # widest in the slot, its chord stands 1.909 off each slot wall and an
    # R.070 arc reaches 1.778 into the slot, so the body clears the arcs in plan
    # wherever it starts (0.131).  It also starts past where the arcs end, with
    # the step at its printed far limit, by the interference margin.  At
    # R.070 that is 0.559 clear (owner ruling 2026-11-23, tool audit Q9).  The
    # 1.5 held here before (074069092e) pinned that day's layout (the grip
    # ending 2.5 past the step, less R.040); no function asked for it.
    body_gap = spec.RELIEF_WIDTH / 2.0 - spec._BODY_HALF_CHORD_AT_BOTTOM
    assert body_gap - spec.RELIEF_CORNER_R_MAX == pytest.approx(0.131, abs=1e-3)
    worst_step = spec.RELIEF_X0 + _printed_devs(spec.RELIEF_X0, "ReliefX0")[1]
    body_past_arcs = end - (worst_step + spec.RELIEF_CORNER_R_MAX)
    assert body_past_arcs == pytest.approx(0.559, abs=1e-3)
    assert body_past_arcs >= carriage.CLEARANCE
    assert carriage.plan_cg_residual_mm() <= 0.25


def test_pivot_chamfer_clears_the_rod_fillet_as_a_min_limit() -> None:
    import _config
    import pn_pen_rod_spec as rod

    fillet_reach = rod.SHOULDER_FILLET_R * (2.0 - math.sqrt(2.0))
    assert spec.PIVOT_BORE_TOP_CHAMFER - fillet_reach >= 0.1
    mouth_r = (spec.PIVOT_BORE_DIA + spec.PIVOT_BORE_BAND[0]) / 2.0
    largest = spec.PIVOT_BORE_TOP_CHAMFER + spec.PIVOT_CHAMFER_BAND[0]
    assert mouth_r + largest < (rod.ROD_SECTION + rod.SECTION_BAND[1]) / 2.0
    assert spec.PIVOT_CHAMFER_TOL_TYPE == 5  # swTolMIN
    assert (
        "PivotReference",
        "PivotChamferSize",
        spec.PIVOT_BORE_TOP_CHAMFER,
        spec.PIVOT_CHAMFER_BAND,
        spec.PIVOT_CHAMFER_TOL_TYPE,
        "MIN",
    ) in part._SINGLE_LIMITS
    rod_number = _config.parts("pn-pen-rod")["number"]
    assert rod_number in spec.DIMENSION_CALLOUTS_ABOVE["PivotChamferSize"]
    for text in (
        spec.DIMENSION_CALLOUTS["PivotChamferSize"],
        spec.DIMENSION_CALLOUTS_ABOVE["PivotChamferSize"],
    ):
        assert not re.search(r"\d\.\d", text)


def _seat_by_bisector(
    z0: float, z1: float, front_deg: float, back_deg: float, width: float, r: float
) -> dict[str, float]:
    """The grip seated in one V, by another route than the spec's: its axis on
    the flanks' bisector, R / sin(half the included angle) under the apex;
    each round's centre on its corner's bisector, its arc sampled."""

    def unit(v: tuple[float, float]) -> tuple[float, float]:
        length = math.hypot(*v)
        return (v[0] / length, v[1] / length)

    grip_r = spec.marker.BARREL_DIA / 2.0
    t0, t1 = math.tan(math.radians(front_deg)), math.tan(math.radians(back_deg))
    apex = ((t0 * z0 + t1 * z1) / (t0 + t1), 0.0)
    apex = (apex[0], t0 * (apex[0] - z0))
    down = (unit((z0 - apex[0], -apex[1])), unit((z1 - apex[0], -apex[1])))
    bisector = unit((down[0][0] + down[1][0], down[0][1] + down[1][1]))
    half = (math.pi - math.radians(front_deg) - math.radians(back_deg)) / 2.0
    reach = grip_r / math.sin(half)
    axis = (apex[0] + bisector[0] * reach, apex[1] + bisector[1] * reach)
    drop = width / (1.0 / t0 + 1.0 / t1)
    flat_y = apex[1] - drop
    corners = ((apex[0] - drop / t0, flat_y), (apex[0] + drop / t1, flat_y))
    nearest, flat_tangents, contacts, flank_tops = [], [], [], []
    for corner, flank, inward in zip(corners, down, (1.0, -1.0)):
        split = unit((inward + flank[0], flank[1]))
        interior = math.acos(inward * flank[0])
        reach_r = r / math.sin(interior / 2.0)
        centre = (corner[0] + split[0] * reach_r, corner[1] + split[1] * reach_r)
        along = (centre[0] - corner[0]) * flank[0] + (centre[1] - corner[1]) * flank[1]
        on_flank = (corner[0] + along * flank[0], corner[1] + along * flank[1])
        on_flat = (centre[0], flat_y)
        start, end = (
            math.atan2(p[1] - centre[1], p[0] - centre[0]) for p in (on_flat, on_flank)
        )
        nearest.append(
            min(
                math.hypot(
                    centre[0] + r * math.cos(start + (end - start) * k / 400) - axis[0],
                    centre[1] + r * math.sin(start + (end - start) * k / 400) - axis[1],
                )
                for k in range(401)
            )
        )
        flat_tangents.append(on_flat[0])
        flank_tops.append(on_flank[1])
        # The grip's contact line: the axis's foot on the flank.
        foot = (axis[0] - corner[0]) * flank[0] + (axis[1] - corner[1]) * flank[1]
        contacts.append(corner[1] + foot * flank[1])
    body_r = spec.marker.BODY_FRONT_DIA / 2.0
    return {
        "axis_z": axis[0],
        "axis_y": axis[1],
        "chord": math.sqrt(body_r**2 - axis[1] ** 2),
        "flat": flat_y - (axis[1] + grip_r),
        "round": min(nearest) - grip_r,
        "contact": min(
            min(contacts), *(top - y for top, y in zip(flank_tops, contacts))
        ),
        "straight": flat_tangents[1] - flat_tangents[0],
    }


def _printed_devs(model_station: float, name: str) -> tuple[float, float]:
    """(lower, upper) of a printed dimension about its model value, the
    sheet printing the model rounded to the spec's places in its unit."""
    return printed_deviations(
        model_station, spec.DRAWING_PRECISION_BY_NAME[name], unit=spec.UNIT
    )


def _printed_seats() -> list[dict[str, float]]:
    from _printed_tolerance import angular_band_deg

    station = spec.depth_station
    angles = (
        spec.V_FLANK_ANGLE_DEG - angular_band_deg(unit=spec.UNIT),
        spec.V_FLANK_ANGLE_DEG + angular_band_deg(unit=spec.UNIT),
    )
    z0_devs = _printed_devs(station(spec.V_MOUTH_Z0), "VMouthZ0")
    z1_devs = _printed_devs(station(spec.V_MOUTH_Z1), "VMouthZ1")
    width_devs = _printed_devs(spec.V_FLAT_WIDTH, "VFlatWidth")
    return [
        _seat_by_bisector(z0, z1, front, back, width, spec.INSIDE_CORNER_R_MAX)
        for z0 in (spec.V_MOUTH_Z0 + dev for dev in z0_devs)
        for z1 in (spec.V_MOUTH_Z1 + dev for dev in z1_devs)
        for front in angles
        for back in angles
        for width in (spec.V_FLAT_WIDTH + dev for dev in width_devs)
    ]


def test_title_block_bands_keep_walls_lands_and_clear_the_marker_body() -> None:
    import pn_pen_frame_spec as frame
    from _inch_wall_limits import WALL_TARGET_MM

    # #290: every depth-wise station prints the inch title block's .XX as a
    # baseline from the body's front face.  The V's mouth stations are the
    # 12.0 closure, printed rounded: each is judged at its printed limits.
    station = spec.depth_station
    dev = {
        "NeckZ0": _printed_devs(station(0.0), "NeckZ0"),
        "NeckZ1": _printed_devs(station(spec.NECK_DEPTH), "NeckZ1"),
        "Depth": _printed_devs(spec.BODY_DEPTH, "Depth"),
        "VMouthZ0": _printed_devs(station(spec.V_MOUTH_Z0), "VMouthZ0"),
        "VMouthZ1": _printed_devs(station(spec.V_MOUTH_Z1), "VMouthZ1"),
        "ReliefZ0": _printed_devs(station(spec.RELIEF_Z0), "ReliefZ0"),
        "ReliefZ1": _printed_devs(station(spec.RELIEF_Z1), "ReliefZ1"),
    }
    relief_z0, relief_z1 = station(spec.RELIEF_Z0), station(spec.RELIEF_Z1)
    near_wall = relief_z0 + dev["ReliefZ0"][0]
    far_wall = spec.BODY_DEPTH + dev["Depth"][0] - (relief_z1 + dev["ReliefZ1"][1])
    near_land = (station(spec.V_MOUTH_Z0) + dev["VMouthZ0"][0]) - (
        station(0.0) + dev["NeckZ0"][1]
    )
    far_land = (station(spec.NECK_DEPTH) + dev["NeckZ1"][0]) - (
        station(spec.V_MOUTH_Z1) + dev["VMouthZ1"][1]
    )
    assert spec.RELIEF_NEAR_WALL_PRINTED_MIN == pytest.approx(near_wall)
    assert spec.RELIEF_FAR_WALL_PRINTED_MIN == pytest.approx(far_wall)
    assert spec.V_NEAR_LAND_PRINTED_MIN == pytest.approx(near_land)
    assert spec.V_FAR_LAND_PRINTED_MIN == pytest.approx(far_land)
    # Rule 17: every wall and land clears the .080 target at the print's
    # worst case.
    for name, wall in (
        ("near_wall", near_wall),
        ("far_wall", far_wall),
        ("near_land", near_land),
        ("far_land", far_land),
    ):
        assert round(wall, 6) >= WALL_TARGET_MM, name
    # The seated body clears both relief walls over the V's printed corners
    # (each mouth edge at its printed limits, each flank at +/-1 deg on its
    # own, so the V may lean and its axis shift toward either wall).
    seats = _printed_seats()
    near = min(
        seat["axis_z"] - seat["chord"] - (spec.RELIEF_Z0 + dev["ReliefZ0"][1])
        for seat in seats
    )
    far = min(
        (spec.RELIEF_Z1 + dev["ReliefZ1"][0]) - seat["axis_z"] - seat["chord"]
        for seat in seats
    )
    assert spec.BODY_NEAR_CLEARANCE_PRINTED_MIN == pytest.approx(near)
    assert spec.BODY_FAR_CLEARANCE_PRINTED_MIN == pytest.approx(far)
    assert min(near, far) > 0.25
    # The neck slides through the stirrup's window at its printed limits.
    neck = spec.NECK_DEPTH + dev["NeckZ1"][1] - dev["NeckZ0"][0]
    assert spec.NECK_WIDTH_PRINTED_MAX == pytest.approx(neck)
    assert neck < frame.WINDOW_WIDTH_PRINTED_MIN


def test_end_view_prints_the_v_edges_in_one_baseline_row() -> None:
    # Rule 10: one datum (the body's front face, the end view's left edge),
    # every station a baseline from it, nested shortest-innermost: each
    # station right of and each row under the last, so an outer extension
    # line never crosses an inner dimension line.  Blind review final9: the
    # depth prints in the bottom view, closing the neck faces' row.
    keep = drawing.RIGHT_KEEP
    assert "Depth" not in keep
    order = ("VMouthZ0", "VMouthZ1")
    stations = (spec.V_MOUTH_Z0, spec.V_MOUTH_Z1)
    xs = [drawing._rz(z) for z in stations]
    assert xs == sorted(xs)
    rows = [keep[name][1] for name in order]
    assert rows[0] - rows[1] == pytest.approx(drawing._END_ROW)
    assert rows[0] < drawing._ry(0.0) - 0.005
    # ~3 mm a character at the sheet's text height: the V's front edge's
    # "5.1" inside its span.
    datum = drawing._rz(spec.BODY_Z0)
    mouth_text = keep["VMouthZ0"][0]
    assert datum + 0.001 < mouth_text - 0.0045
    assert mouth_text + 0.0045 < drawing._rz(spec.V_MOUTH_Z0) - 0.001
    # The lower row's line (~3.3 mm under its text) stays over the bottom
    # view's front edge and the neck faces' datum extension line (y 0.128).
    assert keep["VMouthZ1"][1] - 0.0033 > drawing._bz(spec.BODY_Z0) + 0.003


def test_bottom_view_prints_the_neck_step_where_it_is_an_outline_change() -> None:
    # Blind review final8, the third time: in the paper-end view the neck's
    # faces (edge-on lines inside the body's outline) read as thin ribs,
    # 0.79 thick at worst case.  The bottom view shows the step on both long
    # edges; its faces print there, a baseline row from the body's front face
    # right of the paper end, nested shortest-innermost.  Final9: alone,
    # "20.10" read as the overall depth; the body's back face closes the row.
    keep = drawing.BOTTOM_KEEP
    paper_end = drawing._fx(0.0)
    front = drawing._bz(spec.BODY_Z0)
    back = drawing._bz(spec.BODY_Z1)
    neck_front = drawing._bz(0.0)
    neck_back = drawing._bz(spec.NECK_DEPTH)
    (x0, y0), (x1, y1), (x2, y2) = keep["NeckZ0"], keep["NeckZ1"], keep["Depth"]
    assert paper_end < x0 < x1 < x2
    assert x1 - x0 == pytest.approx(drawing._END_ROW)
    # "2.10" (~8.7 mm) inside its 8.4 mm span, off the paper end and left of
    # the back face's line; "20.10" (~11.8 mm) at mid-span, 2 mm clear of the
    # depth's line; "22.2" (~8 mm) lower, between the neck's back edge and
    # the mid-depth, clear of "20.10" and of the back face's line.
    half_neck_text, half_back_text, half_depth_text = 0.00435, 0.0059, 0.004
    assert x0 - half_neck_text > paper_end + 0.001
    assert x0 + half_neck_text < x1 - 0.002
    assert y0 - 0.0019 > neck_front + 0.002
    assert y0 + 0.0019 < front - 0.002
    assert y1 == pytest.approx((front + neck_back) / 2.0)
    assert x1 + half_back_text < x2 - 0.002
    assert x2 - half_depth_text > x1 + 0.0035
    assert y2 + 0.0019 < y1 - 0.0019 - 0.015
    assert neck_back < y2 < drawing._bz(drawing._CZ)
    # The drilled diameter's callout (measured as the reamed one's five rows,
    # ~35 x 32 mm about its keep; it prints three now) stands below them:
    # right of the depth's line and its extension line's end (~1.3 mm past
    # it), left of the title block (x 0.2158), over the border, under "22.2".
    pivot_x, pivot_y = keep["PivotDia"]
    left, bottom = pivot_x - 0.017, pivot_y - 0.016
    assert left > x2 + 0.0013 + 0.001
    assert pivot_x - 0.016 > x2 + 0.003  # the size row, beside the line
    assert pivot_x + 0.018 < 0.2158 - 0.003
    assert bottom > 0.0127 + 0.01
    assert pivot_y + 0.016 < y2 - 0.0019 - 0.004
    # #30 DRILL THRU and one line naming the mate (rule 7).
    assert spec.DIMENSION_CALLOUTS["PivotDia"].count("\n") == 1
    # Its leader, from the bore's near rim to the block's lower left, passes
    # the paper end's extension line between the neck's back corner and the
    # depth's extension line, and under the depth line's end: it crosses no
    # dimension line.
    centre = (drawing._fx(spec.PIVOT_BORE_X), drawing._bz(drawing._CZ))
    slope = (bottom - centre[1]) / (left - centre[0])
    at_paper_end = centre[1] + slope * (paper_end - centre[0])
    assert back + 0.003 < at_paper_end < neck_back - 0.003
    assert centre[1] + slope * (x2 - centre[0]) < back - 0.003
    # Under the view, the stations from the paper end and the overall
    # length: one baseline row nested shortest-innermost, each text inside
    # its span, the outermost line (~2.9 mm under its text) over the border.
    order = ("ReliefX0", "PivotX", "Length")
    spans = (spec.RELIEF_X0, spec.PIVOT_BORE_X, spec.BLOCK_LENGTH)
    rows = [keep[name][1] for name in order]
    for upper, lower in zip(rows, rows[1:], strict=False):
        assert upper - lower == pytest.approx(drawing._PAPER_ROW)
    assert rows[0] + 0.0017 < back - 0.003
    assert rows[-1] - 0.0029 > 0.0127 + 0.003
    for name, span in zip(order, spans, strict=True):
        assert drawing._fx(span) + 0.005 < keep[name][0] < paper_end - 0.005, name
    assert at_paper_end > rows[0] + 0.0017 + 0.005


def test_section_looks_the_same_way_as_the_paper_end_view() -> None:
    # Review r3 (rule 10 clarity): A-A mirrored the end view, so the V and the
    # relief read as located from opposite faces.  Both now put the body's
    # front face left.
    assert drawing._rz(spec.BODY_Z0) < drawing._rz(spec.BODY_Z1)
    assert drawing._sz(spec.BODY_Z0) < drawing._sz(spec.BODY_Z1)
    assert drawing._sz(drawing._CZ) == pytest.approx(drawing.SECTION_CENTER[0])
    # Both walls a baseline pair from the front face: the near wall's "3.1"
    # inside its span, the far wall's "19.1" between the near wall's
    # extension line and its own, the height right of the far wall.
    keep = drawing.SECTION_KEEP
    front = drawing._sz(spec.BODY_Z0)
    near_wall = drawing._sz(spec.RELIEF_Z0)
    far_wall = drawing._sz(spec.RELIEF_Z1)
    assert front + 0.001 < keep["ReliefZ0"][0] - 0.0045
    assert keep["ReliefZ0"][0] + 0.0045 < near_wall - 0.001
    assert near_wall + 0.003 < keep["ReliefZ1"][0] - 0.006
    assert keep["ReliefZ1"][0] + 0.006 < far_wall - 0.003
    assert keep["ReliefZ1"][1] < keep["ReliefZ0"][1]
    assert keep["ReliefHeight"][0] > drawing._sz(spec.BODY_Z1)
    assert keep["ReliefHeight"][0] + 0.006 < 0.4191 - 0.005
    assert front < keep["PivotZ"][0] < drawing._sz(drawing._CZ)
    rim = drawing._sz(
        drawing._CZ + spec.PIVOT_BORE_DIA / 2.0 + spec.PIVOT_BORE_TOP_CHAMFER
    )
    # Review r5: with its text right of the far rim the chamfer's line ran
    # under its whole text block to 1 mm off the border.  Text left: the
    # line runs out to the left end of its ~72 mm above-row, clear of the
    # tap callout (~71 mm centred on TAP_CALLOUT_XY), over PivotZ's text (top
    # ~1.7 mm over its keep) and its extension lines, the block 5 mm or more
    # under the top border (0.2667).
    chamfer_x, chamfer_y = keep["PivotChamferSize"]
    tap_right = drawing.TAP_CALLOUT_XY[0] + 0.0355
    assert chamfer_x + 0.012 < rim
    assert chamfer_x - 0.036 > tap_right + 0.005
    assert chamfer_y - 0.0084 > keep["PivotZ"][1] + 0.0017 + 0.004
    assert chamfer_y + 0.0075 < 0.2667 - 0.005
    assert chamfer_y > keep["PivotZ"][1] + 0.012
    assert drawing.SECTION_CAPTION_XY[1] < keep["ReliefZ1"][1] - 0.0033 - 0.003


def test_holes_are_native_wizard_features_with_native_callouts() -> None:
    assert spec.SET_SCREW_TAP_SPEC.kind == "tapped"
    assert spec.SET_SCREW_TAP_SPEC.end == "through_next"
    # The pivot bore is drilled (owner ruling 2026-11-24, fit audit question
    # 20): no size carries a native band.
    assert not hasattr(spec, "DRAWING_BANDS")


def test_pivot_callout_names_its_drill_and_its_mate() -> None:
    import _config

    rod_number = _config.parts("pn-pen-rod")["number"]
    callout = spec.DIMENSION_CALLOUTS["PivotDia"]
    # Rule 4: a drilled hole prints the named drill; the mate by number.
    assert callout.startswith(f"{spec.PIVOT_BORE_DRILL} DRILL THRU")
    assert spec.PIVOT_BORE_DRILL == "#30"
    assert rod_number in callout
    assert not re.search(r"\d\.\d", callout)
    assert "REAM" not in callout and "FIT" not in callout
    assert len(callout.splitlines()[1:]) <= 2


def test_tap_callout_reads_size_first_and_ends_in_the_pivot_bore() -> None:
    # Review r11 (rule 12): "TAP 4-40 UNC THRU" read as drilled through the
    # block, so both native rows end INTO PIVOT BORE; r13: "Ø 2.26 ..." had no
    # process word, so the drill row says DRILL; the fan-out screen (rule 26):
    # size first, then process, then depth.  Only text around the variables
    # changes, so size and thread stay associative.
    original = {
        5: "<hw-threaddesc> <hw-thru>",
        6: "",
        7: "<MOD-DIAM><hw-tapdrldia> <hw-thru>",
        8: "",
    }
    rewritten = drawing._tap_callout_definitions(original)
    assert rewritten == {
        5: "<hw-threaddesc> INTO PIVOT BORE",
        6: "",
        7: "<MOD-DIAM><hw-tapdrldia> DRILL INTO PIVOT BORE",
        8: "",
    }
    # Both rows in one part: the drill row alone takes the word.
    joined = drawing._tap_callout_definitions(
        {
            5: "<hw-threaddesc> <hw-thru>",
            6: "",
            7: "",
            8: "<MOD-DIAM><hw-thrutapdrldia> <hw-thru>\nCOAXIAL",
        }
    )
    assert joined[8] == "<MOD-DIAM><hw-thrutapdrldia> DRILL INTO PIVOT BORE\nCOAXIAL"
    # Precision goes to whichever drill-size variable the callout carries.
    assert drawing._tap_drill_variable(rewritten) == "hw-tapdrldia"
    assert drawing._tap_drill_variable(joined) == "hw-thrutapdrldia"
    with pytest.raises(RuntimeError):
        drawing._tap_drill_variable({5: "<hw-threaddesc>", 7: "DRILL"})
    for bad in (
        {5: "<hw-threaddesc> <hw-thru>", 6: "", 7: "", 8: ""},
        {5: "<hw-thru>", 6: "", 7: "<hw-thru>", 8: ""},
        {5: "<hw-threaddesc> <hw-thru>", 7: "<hw-thru>"},
        # No drill row, a process prefix, one already worded, or a drill row
        # sharing the thread's row.
        {5: "<hw-threaddesc> <hw-thru>", 6: "", 7: "<hw-thru>", 8: ""},
        {
            5: "TAP <hw-threaddesc> <hw-thru>",
            6: "",
            7: "<MOD-DIAM><hw-tapdrldia> <hw-thru>",
            8: "",
        },
        {
            5: "<hw-threaddesc> <hw-thru>",
            6: "",
            7: "<MOD-DIAM><hw-tapdrldia> DRILL <hw-thru>",
            8: "",
        },
        {
            5: "<hw-tapdrldia> <hw-threaddesc> <hw-thru> <hw-thru>",
            6: "",
            7: "",
            8: "",
        },
    ):
        with pytest.raises(RuntimeError):
            drawing._tap_callout_definitions(bad)
    assert not re.search(r"\d", drawing._TAP_END + drawing._DRILL_WORD)
    # The readback, on resolved text as the sheet prints it.
    assert drawing._tap_callout_resolved(
        "4-40 UNC INTO PIVOT BORE\n\nØ2.26 DRILL INTO PIVOT BORE\n"
    )
    for printed in (
        "4-40 UNC INTO PIVOT BORE\n\nØ2.26 INTO PIVOT BORE\n",
        "TAP 4-40 UNC INTO PIVOT BORE\n\nØ2.26 DRILL INTO PIVOT BORE\n",
        "4-40 UNC INTO PIVOT BORE\n\nDRILL Ø2.26 INTO PIVOT BORE\n",
        "4-40 UNC THRU\n\nØ2.26 DRILL INTO PIVOT BORE\n",
    ):
        assert not drawing._tap_callout_resolved(printed), printed


def test_v_is_its_flank_angles_mouth_and_apex_flat_with_a_reference_height() -> None:
    import pn_pen_carriage_geom as carriage

    # Review r11 (rules 3/10): the V's angle prints driving at the title
    # block's +/-1 deg; final review: both mouth edges from the front face.
    # Blind review (rule 16): the apex is a flat a cutter leaves, its width
    # driving at .X and its height a driven reference.  Blind review (rule
    # 1): an included angle left both flanks free to tilt together, so each
    # flank prints its own angle to the bottom face, "2X 45°".
    assert spec.V_FLANK_ANGLE_DEG == 45.0
    assert spec.V_ANGLE_DEG == 90.0
    assert spec.V_MOUTH_WIDTH == 12.0
    assert (spec.V_MOUTH_Z0 + spec.V_MOUTH_Z1) / 2.0 == spec.DEPTH_MID_Z
    assert spec.RELIEF_WIDTH == pytest.approx(15.748)  # .62
    assert (spec.RELIEF_Z0 + spec.RELIEF_Z1) / 2.0 == spec.DEPTH_MID_Z
    assert (spec.BODY_Z0 + spec.BODY_Z1) / 2.0 == spec.DEPTH_MID_Z
    # The theoretical apex still seats the grip; the flat stands 1.0 under it.
    assert spec.V_APEX_Y == 6.0
    assert spec.MARKER_AXIS_Y == pytest.approx(6.0 - 5.3 * math.sqrt(2.0))
    assert spec.V_FLAT_WIDTH == 2.032  # .08
    assert spec.V_FLAT_Y == pytest.approx(4.984)
    assert spec.V_GROOVE_AREA == pytest.approx(36.0 - 2.032 * 1.016 / 2.0)
    assert carriage.BLOCK_BOTTOM_Y == pytest.approx(366.2)
    assert spec.REFERENCE_DIMENSIONS == (("VGrooveProfile", "VFlatY"),)
    assert {
        "VFlankAngle",
        "VFlatWidth",
        "VFlatY",
        "VMouthZ0",
        "VMouthZ1",
    } == spec.DRAWING_DIMENSIONS["VGrooveProfile"]
    assert spec.DRAWING_DIMENSIONS["ReliefReference"] == {
        "ReliefZ0",
        "ReliefZ1",
        "ReliefHeight",
    }

    # The flat's reference height reads what the printed mouth stations, flat
    # width and 45° flanks close to (machinist review c03368c: (.196) against
    # (.67 - .19 - .08) / 2 = .20).
    def printed(mm: float, name: str) -> float:
        return round(mm / 25.4, spec.DRAWING_PRECISION_BY_NAME[name])

    mouth = printed(spec.depth_station(spec.V_MOUTH_Z1), "VMouthZ1") - printed(
        spec.depth_station(spec.V_MOUTH_Z0), "VMouthZ0"
    )
    closure = (
        (mouth - printed(spec.V_FLAT_WIDTH, "VFlatWidth"))
        / 2.0
        / math.tan(math.radians(spec.V_FLANK_ANGLE_DEG))
    )
    assert printed(spec.V_FLAT_Y, "VFlatY") == pytest.approx(closure)
    # The grip seats on both flanks: each flank at its own printed limit,
    # each mouth edge and the flat at their printed .XX limits, it stays 0.96
    # under the flat, each contact line at least 2.03 up its flank and inside
    # its straight run.
    seats = _printed_seats()
    assert len(seats) == 32
    flat = min(seat["flat"] for seat in seats)
    assert spec.V_FLAT_GRIP_CLEARANCE_PRINTED_MIN == pytest.approx(flat)
    assert flat == pytest.approx(0.964, abs=1e-3)
    contact = min(seat["contact"] for seat in seats)
    assert spec.V_CONTACT_MARGIN_PRINTED_MIN == pytest.approx(contact)
    assert contact == pytest.approx(2.026, abs=1e-3)
    nominal = _seat_by_bisector(
        spec.V_MOUTH_Z0,
        spec.V_MOUTH_Z1,
        spec.V_FLANK_ANGLE_DEG,
        spec.V_FLANK_ANGLE_DEG,
        spec.V_FLAT_WIDTH,
        spec.V_APEX_FILLET_R,
    )
    assert nominal["axis_y"] == pytest.approx(spec.MARKER_AXIS_Y)
    assert nominal["flat"] == pytest.approx(1.179, abs=1e-3)
    assert spec.V_CONTACT_Y < spec.V_FLAT_Y
    # The spec's seat agrees with this one at every printed corner.
    for mine, theirs in zip(seats, spec.V_PRINTED_CORNERS, strict=True):
        assert (mine["axis_z"], mine["axis_y"]) == pytest.approx(theirs.axis)
        assert mine["flat"] == pytest.approx(theirs.flat_clearance)
        assert mine["round"] == pytest.approx(theirs.round_clearance, abs=1e-6)
        assert mine["contact"] == pytest.approx(theirs.contact_margin)
        assert mine["straight"] == pytest.approx(theirs.flat_straight)
    # Each angle's text point (which picks the wedge it measures) lies
    # between the bottom face's line and its flank's line, so each measures
    # the flank's 45 deg, not its 135: the unprinted front one in the groove
    # just over its mouth corner, the printed back one in the vertically
    # opposite wedge, under the bottom face beyond the back mouth corner
    # (blind review final9: the drawing keeps its arc out of the view).
    points = part._flank_angle_text_points()
    for (u, v), mouth_z, sign in zip(
        points,
        (spec.V_MOUTH_Z0, spec.V_MOUTH_Z1),
        (1.0, -1.0),
        strict=True,
    ):
        run = sign * (-u - mouth_z)
        assert 0.0 < v / run < math.tan(math.radians(spec.V_FLANK_ANGLE_DEG))
    assert points[0][1] > 0.0 > points[1][1]


def test_apex_flat_rounds_clear_the_grip_at_the_title_block_corner() -> None:
    # Blind re-review (rule 16): the flat met the flanks in sharp internal
    # corners.  They print no radius: at the title block's INSIDE CORNERS
    # R.040 MAX the grip still clears the rounds and seats on the straight
    # flanks, so nothing needs a tighter limit (machinist review 8c9a0a7).
    # The model carries a .020 chamfer-mill tip.
    assert spec.V_APEX_FILLET_R == 0.508  # .020
    assert spec.V_APEX_FILLET_R <= spec.INSIDE_CORNER_R_MAX
    assert "VApexFillets" not in spec.DRAWING_DIMENSIONS
    # Worst case: the rounds at R.040, each flank's angle, each mouth edge and
    # the flat at their printed limits.  The grip clears the rounds by 0.85
    # (the flat by 0.96), and the narrowest flat still runs straight between
    # the two tangent points.
    seats = _printed_seats()
    clearance = spec.V_APEX_FILLET_GRIP_CLEARANCE_PRINTED_MIN
    assert clearance == pytest.approx(0.849, abs=1e-3)
    assert clearance == pytest.approx(min(seat["round"] for seat in seats), abs=1e-6)
    assert min(clearance, spec.V_FLAT_GRIP_CLEARANCE_PRINTED_MIN) >= 0.25
    straight = spec.V_FLAT_STRAIGHT_PRINTED_MIN
    assert straight == pytest.approx(min(seat["straight"] for seat in seats))
    assert straight == pytest.approx(0.915, abs=1e-3)
    # The rounds' section and the groove's finished section feed the volumes.
    assert spec.V_APEX_FILLET_AREA == pytest.approx(
        2.0 * 0.508**2 * (math.tan(math.pi / 8.0) - math.pi / 8.0)
    )
    assert spec.V_GROOVE_SECTION == pytest.approx(
        spec.V_GROOVE_AREA - spec.V_APEX_FILLET_AREA
    )


def test_v_dimension_text_stays_off_the_part_in_the_end_view() -> None:
    # Blind review final8 (rule 14): from under the bottom face, outside the
    # wedge it measures, the flanks' "2X 45°" drew its arc 40 mm about the
    # back mouth corner, from the flank round through the depth row's text to
    # its own.  Final9: in the groove's own wedge the arc, through the text,
    # ran into its "4".  The arc now stands short in the vertically opposite
    # wedge, under the bottom face right of the back mouth corner, where the
    # build's sketch measures it, and the text is offset right of the view
    # under the bottom face's line; the flat's width prints over the top face
    # and its height right of the body.
    keep = drawing.RIGHT_KEEP
    arc_x, arc_y = keep["VFlankAngle"]
    corner = (drawing._rz(spec.V_MOUTH_Z1), drawing._ry(0.0))
    bearing = math.degrees(math.atan2(arc_y - corner[1], arc_x - corner[0]))
    assert bearing == pytest.approx(-spec.V_FLANK_ANGLE_DEG / 2.0)
    # The sketch's text point (u = -z, v = y) picks the same wedge.
    _front_text, (u, v) = part._flank_angle_text_points()
    sketch_bearing = math.degrees(math.atan2(v, -u - spec.V_MOUTH_Z1))
    assert -spec.V_FLANK_ANGLE_DEG < sketch_bearing < 0.0
    # The arc, about the corner, is short (room for its two arrows) and out
    # of the view: it lands on the bottom face's drawn edge short of the
    # body's back corner and on the flank's extension past the mouth corner,
    # all of it right of the back edge's extension line, which drops from
    # the corner.
    run = math.hypot(arc_x - corner[0], arc_y - corner[1])
    assert 0.008 <= run <= 0.015
    flank = math.radians(spec.V_FLANK_ANGLE_DEG)
    assert corner[0] + run < drawing._rz(spec.BODY_Z1) - 0.003
    assert corner[0] + run * math.cos(flank) > corner[0] + 0.006
    assert corner[1] - run * math.sin(flank) > keep["VMouthZ1"][1] + 0.0017
    # "2X 45°" ~13.6 x 3.8 mm (final8), offset right of the body's back face
    # and under the bottom face's line (which the flat height's lower
    # extension line carries on to its line), left of section A-A's front
    # face and its extension lines, no lower than its caption; its leader
    # from the arc runs under the body's back corner.  Release review
    # 41bbeec: level with the near wall's "3.1" line, its shelf ended 1 mm
    # short of that line's outside arrow and read as one line; the shelf
    # (~2.7 mm under the text's centre) stands >= 4 mm off both of section
    # A-A's under-face lines (~3.3 mm under their keeps).
    text_x, text_y = drawing.FLANK_ANGLE_TEXT_XY
    half_w, half_h = 0.007, 0.0019
    assert text_x - half_w > drawing._rz(spec.BODY_Z1) + 0.005
    assert text_y + half_h < corner[1] - 0.005
    assert text_x + half_w < drawing._sz(spec.BODY_Z0) - 0.008
    assert text_y - half_h > drawing.SECTION_CAPTION_XY[1]
    shelf = text_y - 0.0027
    for name in ("ReliefZ0", "ReliefZ1"):
        assert abs(shelf - (drawing.SECTION_KEEP[name][1] - 0.0033)) >= 0.004
    left = (text_x - half_w, text_y)
    slope = (left[1] - arc_y) / (left[0] - arc_x)
    at_back = arc_y + slope * (drawing._rz(spec.BODY_Z1) - arc_x)
    assert at_back < corner[1] - 0.003
    # The flat's width: under the flat, inside the V's opening, so its
    # extension lines drop through air (round 3 review: over the view they
    # crossed the whole end face).  Its text (~7 x 3.5 mm) and its line
    # (~3.3 mm under the keep, arrows ~3 mm past the extension lines) stay
    # between the flanks and over the bottom face.
    width_x, width_y = keep["VFlatWidth"]
    assert width_x == pytest.approx(drawing._rz(drawing._CZ))
    flat_y = drawing._ry(spec.V_FLAT_Y)
    line_y = width_y - 0.0033
    assert width_y + 0.0017 < flat_y - 0.003
    assert line_y > drawing._ry(0.0) + 0.005
    flat_half = spec.V_FLAT_WIDTH / 2.0 * drawing._S
    # 45 degree flanks: the opening's half-width grows by the drop under the
    # flat.
    assert flat_half + (flat_y - (width_y + 0.0017)) > 0.0035 + 0.002
    assert flat_half + (flat_y - line_y) > flat_half + 0.003 + 0.002
    # The flat's height: right of the body's back face, inside the gap to
    # section A-A.
    height_x, height_y = keep["VFlatY"]
    assert height_x > drawing._rz(spec.BODY_Z1) + 0.008
    assert height_x + 0.006 < drawing._sz(spec.BODY_Z0) - 0.008
    assert drawing._ry(0.0) < height_y < drawing._ry(spec.V_FLAT_Y)


def test_v_runs_past_the_step_so_no_knife_edge_shows_in_the_end_view() -> None:
    # Review final2: a closed triangle at each V mouth lip in the paper-end
    # view, which hiding tangent edges did not remove.  It was brass: stopped
    # at the step, the V left a sliver under each flank where the corner arc
    # curved away from the step.  The simplified E's wider slot stands both
    # corner arcs outside the V's mouth, and the cut still runs on to where
    # they end: past the step the V lies wholly inside the slot.
    near_corner_z = spec.RELIEF_Z0 + spec.RELIEF_CORNER_R_MAX
    far_corner_z = spec.RELIEF_Z1 - spec.RELIEF_CORNER_R_MAX
    assert near_corner_z < spec.V_MOUTH_Z0 < spec.V_MOUTH_Z1 < far_corner_z
    assert spec.V_CUT_LENGTH == spec.RELIEF_X0 + spec.RELIEF_CORNER_R
    assert spec.V_APEX_Y < spec.RELIEF_HEIGHT


def test_section_shows_the_tap_thread_on_a_visible_thin_layer() -> None:
    # Review final2: section A-A drew the tapped hole as a plain drill.  The
    # section imports its cosmetic thread (at least one instance) and moves
    # it onto a thin continuous visible layer, read back; SolidWorks' own
    # tapped-hole note from that import is deleted there.
    assert drawing._COSMETIC_THREAD_ANNOTATION == 1
    assert drawing.TAPPED_HOLE_NOTE == "#4-40 Tapped Hole"


def test_analytic_volumes_match_the_carriage_mass_model() -> None:
    import pn_pen_carriage_geom as carriage

    # The E: the neck .35 x .70, the body .68 x .86, 18.0 tall.
    assert part.V_BLOCK == pytest.approx(
        (8.89 * 17.78 + (26.162 - 8.89) * 21.844) * 18.0
    )
    # Cut one corner radius past the step, the V's run there lies in the slot:
    # the relief removes that much less.  The apex flat leaves its tip
    # standing; its two R.020 rounds give back 0.011 mm^2 more along the
    # whole cut.
    assert part.V_GROOVE == pytest.approx(
        spec.V_GROOVE_AREA * (8.89 + spec.RELIEF_CORNER_R)
    )
    assert part.V_APEX_FILLETS == pytest.approx(
        spec.V_APEX_FILLET_AREA * spec.V_CUT_LENGTH
    )
    # Past the step the V's section is its triangle less the tip the apex
    # rounds leave, over one corner radius.
    assert part.V_GROOVE_PAST_STEP == pytest.approx(
        spec.V_GROOVE_SECTION * spec.RELIEF_CORNER_R
    )
    # The carriage mass model carries the relief's two R.065 step corners
    # (owner ruling 2026-11-23, tool audit Q9) and leaves the bore's top
    # chamfer, under 0.05% of the block.
    assert part.V_RELIEF + part.V_RELIEF_CORNERS + part.V_GROOVE_PAST_STEP == (
        pytest.approx(15.748 * 6.604 * (26.162 - 8.89))
    )
    corner_r, relief_h = spec.RELIEF_CORNER_R, spec.RELIEF_HEIGHT
    assert part.V_RELIEF_CORNERS == pytest.approx(
        2.0 * (1.0 - math.pi / 4.0) * corner_r**2 * relief_h
    )
    assert 0.0 < part.V_PIVOT_CHAMFER < 0.0005 * part.V_TOTAL
    bore_length = spec.BLOCK_HEIGHT - spec.RELIEF_HEIGHT
    assert part.V_PIVOT_BORE == pytest.approx(
        math.pi * (spec.PIVOT_BORE_DIA / 2.0) ** 2 * bore_length
    )
    tap_r = TAP_DRILL_MM[spec.SET_SCREW_TAP_SPEC.size] / 2.0
    # The exact tap reaches past the #30 bore wall's 9.29 from the front face
    # on its axis, never past the bore axis.
    assert spec.SET_SCREW_TAP_LENGTH == pytest.approx(9.29005)
    assert (
        math.pi * tap_r**2 * spec.SET_SCREW_TAP_LENGTH
        < part.V_SET_SCREW_TAP
        < math.pi * tap_r**2 * (spec.DEPTH_MID_Z - spec.BODY_Z0)
    )
    block_mass = sum(
        mass
        for name, mass, _x, _z in carriage.plan_mass_items()
        if name.startswith("v-block ")
    )
    sliver = part.V_SET_SCREW_TAP - math.pi * tap_r**2 * spec.SET_SCREW_TAP_LENGTH
    carriage_volume = block_mass / carriage.BRASS_G_PER_MM3 - sliver
    assert carriage_volume == pytest.approx(part.V_TOTAL + part.V_PIVOT_CHAMFER)


def test_neck_edge_breaks_print_and_clear_the_stirrup_and_the_body() -> None:
    import pn_pen_carriage_geom as carriage
    import pn_pen_frame_spec as frame

    # Owner seat ruling 2026-11-23: "break the v-block neck's two top edges
    # .080 x 45° (.075 to .085, cut with the 1/4 in 90° chamfer mill that
    # part already uses)".  One prints for both, in the paper-end view, at
    # three places (the title block's +/-.005), its 45° in words, and why it
    # is there above it.
    assert spec.NECK_EDGE_BREAK == pytest.approx(0.080 * 25.4)
    assert (spec.NECK_EDGE_BREAK_MIN, spec.NECK_EDGE_BREAK_MAX) == pytest.approx(
        (0.075 * 25.4, 0.085 * 25.4)
    )
    assert spec.DRAWING_DIMENSIONS["NeckBreakProfile"] == {"NeckBreak"}
    assert spec.DRAWING_PRECISION_BY_NAME["NeckBreak"] == 3
    assert spec.DIMENSION_PREFIXES[("NeckBreakProfile", "NeckBreak")] == "2X "
    assert spec.DIMENSION_CALLOUTS["NeckBreak"] == "X 45°"
    assert spec.DIMENSION_CALLOUTS_ABOVE["NeckBreak"] == "CLEARS MHA-PN-01"
    assert "NeckBreak" in drawing.RIGHT_KEEP
    # The shortest leg clears the stirrup's window corners at their greatest
    # R.070 by 0.127, and the full break runs to .33, past the stirrup's far
    # face at its printed .32.
    assert spec.NECK_EDGE_BREAK_MIN - frame.WINDOW_CORNER_R_MAX == pytest.approx(
        0.127, abs=1e-3
    )
    assert spec.NECK_BREAK_FULL_X == pytest.approx(0.33 * 25.4)
    assert carriage.window_corner_ride_max(carriage.STIRRUP_REAR_FACE_LIMITS[1]) == 0.0
    # The chamfer mill stops short of the step at its printed nearest (.34),
    # so its cone on the top face stays inside the body's side faces; its
    # run-out keeps the target to the bore's chamfer (5.42) and to the rod
    # shoulder's circle (3.97), and stops 0.23 short of the set-screw thread.
    step_min = spec.RELIEF_X0 + _printed_devs(spec.RELIEF_X0, "ReliefX0")[0]
    assert spec.NECK_BREAK_FULL_X < step_min
    reach = math.sqrt(
        spec.NECK_EDGE_BREAK**2 - (spec.RELIEF_X0 - spec.NECK_BREAK_FULL_X) ** 2
    )
    assert reach < spec.BODY_SIDE_STEP
    assert spec.NECK_BREAK_BORE_CHAMFER_WALL_MIN == pytest.approx(5.424, abs=1e-3)
    assert spec.NECK_BREAK_ROD_SHOULDER_GAP_MIN == pytest.approx(3.975, abs=1e-3)
    assert spec.NECK_BREAK_TAP_GAP_MIN == pytest.approx(0.2285, abs=1e-4)
    # The top flat the stirrup's rail rests on keeps .51 at the printed worst.
    assert spec.NECK_TOP_FLAT_PRINTED_MIN == pytest.approx(0.51 * 25.4)
    # Volumes: each break's triangle to the stop, and its run-out, the cone's
    # quarter on the neck's side plus, past the step, its body-side part
    # (a quadrature of the disc at each height; a sampling agrees to 0.3%).
    leg, stop = spec.NECK_EDGE_BREAK, spec.NECK_BREAK_FULL_X
    assert spec.NECK_BREAK_VOLUME == pytest.approx(leg * leg / 2.0 * stop)
    quarter = math.pi * leg**3 / 12.0
    assert quarter < spec.NECK_BREAK_RUNOUT_VOLUME < 2.0 * quarter
    assert spec.NECK_BREAK_RUNOUT_VOLUME == pytest.approx(3.408, abs=1e-3)
    assert stop < spec.NECK_BREAK_RUNOUT_X < stop + leg
    assert part.V_NECK_BREAKS == pytest.approx(2.0 * spec.NECK_BREAK_VOLUME)
    assert part.V_NECK_BREAK_RUNOUTS == pytest.approx(
        2.0 * spec.NECK_BREAK_RUNOUT_VOLUME
    )


def test_sheet_runs_at_4_to_1_with_3_to_2_isometric() -> None:
    assert drawing.SHEET_SCALE == (4.0, 1.0)
    assert drawing.VIEW_SCALE == (4, 1)
    # Review r5: at 1:1 the iso's tap mouth and bore read as polygons.
    assert drawing.ISO_SCALE == spec.ISOMETRIC_VIEW_SCALE == (3, 2)
    assert spec.ISOMETRIC_VIEW_NOTE == "ISOMETRIC VIEW SCALE 3:2"
    # Its ink, estimated from the block's box (the old 36 x 18 x 18 block's
    # estimate, 38.2 wide, matched the 38.3 measured at 1:1): 35.0 x 34.9 at
    # 1:1, x1.5, centred 1.8 mm under its centre as measured.  It clears the
    # ream callout (~44 mm either side of its keep), the end view's depth
    # extension line, the title block (top 0.0651) and, along its sloping top,
    # the section caption's left end (x ~0.337, bottom ~0.118); the note
    # beside it stays 5 mm inside the border (0.4188).
    half_w, half_h = 0.0350 * 1.5 / 2.0, 0.0349 * 1.5 / 2.0
    ink_cy = drawing.ISO_CENTER[1] - 0.0018
    left, right = drawing.ISO_CENTER[0] - half_w, drawing.ISO_CENTER[0] + half_w
    assert left > drawing.BOTTOM_KEEP["PivotDia"][0] + 0.017 + 0.005
    assert left > drawing._rz(spec.BODY_Z1) + 0.005
    assert ink_cy - half_h > 0.0651 + 0.003
    top_vertex_x = left + 0.45 * 2.0 * half_w
    ink_top_at_caption = (
        ink_cy + half_h - (0.337 - top_vertex_x) * math.tan(math.radians(30.0))
    )
    assert ink_top_at_caption < drawing.SECTION_CAPTION_XY[1] - 0.015 - 0.003
    assert drawing.ISO_NOTE_XY[0] > right + 0.004
    assert drawing.ISO_NOTE_XY[0] + 0.059 < 0.4188 - 0.005


def test_no_note_block_no_gdt_no_roughness() -> None:
    # Material and finish ride the title block; the sheet has nothing else to say.
    assert spec.DRAWING_NOTES == ""


def test_part_stamps_make_critical_drawing_properties() -> None:
    import _config

    registry = _config.parts("pn-pen-v-block")
    assert "brass" in str(registry["material_specification"]).lower()
    assert "bright brass" in str(registry["finish"]).lower()
    assert int(registry["quantity"]) == 1


def test_set_screw_tap_wall_to_the_step_is_stated_at_its_printed_worst_case() -> None:
    # Rule 17: over the step's .08 the #4-40 thread (major .112) stands off
    # the step face by the station gap less its major radius.  At the
    # printed worst case (tap station .48, step .36) that is .064: over the
    # floor, under the target (RV-01), stated natively as .064 MIN.
    import pn_pen_carriage_geom as carriage
    import pn_pen_frame_spec as frame
    from _hole_spec import THREAD_MAJOR_MM
    from _inch_wall_limits import WALL_FLOOR_MM, WALL_TARGET_MM
    from _recording_geometry import PAPER_FRONT_Z

    band = 0.01 * 25.4
    major_r = THREAD_MAJOR_MM[spec.SET_SCREW_TAP_SPEC.size] / 2.0
    wall = (spec.PIVOT_BORE_X - band) - (spec.RELIEF_X0 + band) - major_r
    assert wall == pytest.approx(0.064 * 25.4, abs=0.001)
    assert WALL_FLOOR_MM <= wall < WALL_TARGET_MM
    assert spec.TAP_WALL_MIN_MM == pytest.approx(0.064 * 25.4)
    assert spec.TAP_WALL_MIN_MM == pytest.approx(wall, abs=0.001)
    assert spec.TAP_WALL_MIN_TOL_TYPE == 5  # swTolType_e.swTolMIN
    assert spec.TAP_WALL_MIN_BAND[1] == 0.0
    assert spec.TAP_WALL_MIN_MM + spec.TAP_WALL_MIN_BAND[0] == pytest.approx(
        (spec.PIVOT_BORE_X + band) - (spec.RELIEF_X0 - band) - major_r
    )
    # The reference line runs from the thread's major diameter toward the
    # step and stops short of it.
    assert spec.TAP_WALL_START_X == pytest.approx(spec.PIVOT_BORE_X - major_r)
    assert spec.TAP_WALL_START_X - spec.TAP_WALL_MIN_MM > spec.RELIEF_X0
    # Why the geometry stays: reaching the target needs this much more gap
    # between the tap and the step.  The step can't come toward the paper end
    # (the stirrup slides on the neck with less slack), and moving the bore
    # toward the free end carries the stirrup toward the paper by the shift
    # times cos(yaw), more than the carriage's paper clearance at its printed
    # worst case.
    shortfall = WALL_TARGET_MM - wall
    neck_slack = spec.RELIEF_X0 - (
        carriage.FRAME_X0_LOCAL + frame.FRAME_DEPTH + 4.0 * carriage.CLEARANCE
    )
    paper_slack = PAPER_FRONT_Z - max(
        carriage.paper_side_points_printed_worst().values()
    )
    yaw = math.radians(carriage.PEN_BLOCK_YAW_DEG)
    assert 0.0 <= neck_slack < shortfall
    assert 0.0 <= paper_slack < shortfall * math.cos(yaw)


def test_tap_wall_stands_under_the_front_view_clear_of_every_line() -> None:
    # The reference line lies at the tap's height between the thread and the
    # step; its line stands under the bottom face, between the station's
    # extension lines (the tap's axis, the paper end) and over the station's
    # row.  Its two-row text (~21 x 9 mm, value over the anchor, TAP WALL
    # under) is offset on a leader right of the extension lines, clear of the
    # view, the station's text and its paper-end extension line.
    start, end = (
        drawing._fx(spec.TAP_WALL_START_X),
        drawing._fx(spec.TAP_WALL_START_X - spec.TAP_WALL_MIN_MM),
    )
    line_x, line_y = drawing.FRONT_KEEP["TapWallMin"]
    assert line_x == pytest.approx((start + end) / 2.0)
    assert drawing._fx(spec.PIVOT_BORE_X) + 0.004 < start < end < drawing._fx(0.0)
    bottom = drawing._fy(0.0)
    station_y = drawing.FRONT_KEEP["SetScrewX"][1]
    # The keep is the line (farm 20261101T085904510Z): it stands off section
    # line A's arrow, drawn at the cutting line's bottom end, which its
    # outside leg ran along at the same y.
    arrow_y = drawing._fy(drawing.SECTION_LINE_MODEL_MM[0][1])
    assert line_y < arrow_y - 0.004
    assert station_y + 0.0017 < line_y - 0.005
    x, y = drawing.TAP_WALL_TEXT_XY
    half_w = 0.0105
    assert x - half_w > end + 0.003 + 0.002  # past the line's outside arrow
    assert x + half_w < drawing._fx(0.0) - 0.005
    assert y + 0.0035 < bottom - 0.003
    assert y - 0.0045 > station_y + 0.0017 + 0.005
    # The station row clears the bottom view's top (body front face) edge.
    assert station_y - 0.0033 - 0.004 > drawing._bz(spec.BODY_Z0)


def _in(value_in: float) -> float:
    return value_in * 25.4


_FEATURE_KINDS = {
    "paper_end": "face",
    "bottom_face": "face",
    "body_front": "face",
    "far_end": "face",
    "top_face": "face",
    "neck_front": "face",
    "neck_back": "face",
    "body_back": "face",
    "neck_steps": "face",
    "neck_edge_breaks": "chamfer",
    "v_groove": "vee",
    "relief": "slot",
    "pivot_bore": "hole",
    "set_screw_tap": "threaded_hole",
}


def _plane(normal: tuple[float, float, float], offset_mm: float) -> FaceGeometry:
    point = tuple(value * offset_mm / 1000 for value in normal)
    return FaceGeometry(None, 4001, (*normal, *point), normal, ())


def _cylinder(
    dia_mm: float, axis: tuple[float, float, float], box_mm: tuple[float, ...]
) -> FaceGeometry:
    box = tuple(value / 1000 for value in box_mm)
    return FaceGeometry(None, 4002, (0.0, 0.0, 0.0, *axis, dia_mm / 2000), None, box)


def test_the_block_is_a_feature_export_part_with_one_owner_per_face() -> None:
    assert "pn_pen_v_block" in export_features.SUPPORTED_PARTS
    manifest = export_features.requirement_manifest("pn_pen_v_block")
    kinds = {name: feature["kind"] for name, feature in manifest["features"].items()}
    assert kinds == _FEATURE_KINDS
    assert manifest["construction"] == "one_piece"
    assert manifest["notes"]["manufacturing"] == []
    selectors = export_features.feature_selectors("pn_pen_v_block")
    s = math.sqrt(0.5)
    r = spec.RELIEF_CORNER_R
    x0, z0, z1 = spec.RELIEF_X0, spec.RELIEF_Z0, spec.RELIEF_Z1
    bore_r = spec.PIVOT_BORE_DIA / 2
    tap = TAP_DRILL_MM[spec.SET_SCREW_TAP_SPEC.size]
    tr = tap / 2
    x, y, mid = spec.PIVOT_BORE_X, spec.SET_SCREW_Y, spec.DEPTH_MID_Z
    expected = {
        "paper_end": [_plane((-1.0, 0.0, 0.0), 0.0)],
        "bottom_face": [_plane((0.0, -1.0, 0.0), 0.0)],
        "body_front": [_plane((0.0, 0.0, -1.0), -spec.BODY_Z0)],
        "far_end": [_plane((1.0, 0.0, 0.0), spec.BLOCK_LENGTH)],
        "top_face": [_plane((0.0, 1.0, 0.0), spec.BLOCK_HEIGHT)],
        "neck_front": [_plane((0.0, 0.0, -1.0), 0.0)],
        "neck_back": [_plane((0.0, 0.0, 1.0), spec.NECK_DEPTH)],
        "body_back": [_plane((0.0, 0.0, 1.0), spec.BODY_Z1)],
        "neck_steps": [_plane((-1.0, 0.0, 0.0), -x0)],
        "neck_edge_breaks": [
            _plane((0.0, s, -s), s * (spec.BLOCK_HEIGHT - spec.NECK_EDGE_BREAK)),
            _plane(
                (0.0, s, s),
                s * (spec.BLOCK_HEIGHT - spec.NECK_EDGE_BREAK + spec.NECK_DEPTH),
            ),
        ],
        "v_groove": [
            _plane((0.0, -s, s), s * spec.V_MOUTH_Z0),
            _plane((0.0, -s, -s), -s * spec.V_MOUTH_Z1),
            _plane((0.0, -1.0, 0.0), -spec.V_FLAT_Y),
        ],
        "relief": [
            _plane((0.0, -1.0, 0.0), -spec.RELIEF_HEIGHT),
            _plane((0.0, 0.0, 1.0), z0),
            _plane((0.0, 0.0, -1.0), -z1),
            _plane((1.0, 0.0, 0.0), x0),
            _cylinder(
                2 * r,
                (0.0, 1.0, 0.0),
                (x0, 0.0, z0, x0 + r, spec.RELIEF_HEIGHT, z0 + r),
            ),
            _cylinder(
                2 * r,
                (0.0, 1.0, 0.0),
                (x0, 0.0, z1 - r, x0 + r, spec.RELIEF_HEIGHT, z1),
            ),
        ],
        "pivot_bore": [
            _cylinder(
                spec.PIVOT_BORE_DIA,
                (0.0, 1.0, 0.0),
                (
                    x - bore_r,
                    spec.RELIEF_HEIGHT,
                    mid - bore_r,
                    x + bore_r,
                    spec.BLOCK_HEIGHT,
                    mid + bore_r,
                ),
            )
        ],
        "set_screw_tap": [
            _cylinder(
                tap,
                (0.0, 0.0, 1.0),
                (x - tr, y - tr, spec.BODY_Z0, x + tr, y + tr, mid - bore_r),
            )
        ],
    }
    for name, faces in expected.items():
        for face in faces:
            owners = [
                owner
                for owner, specs in selectors.items()
                if any(selector.matches(face) for selector in specs)
            ]
            assert owners == [name], name


def test_block_feature_bands_are_the_printed_ones() -> None:
    features = export_features.requirement_manifest("pn_pen_v_block")["features"]
    assert features["far_end"]["length"] == pytest.approx([_in(1.02), _in(1.04)])
    assert features["top_face"]["height"] == pytest.approx([_in(0.70), _in(0.72)])
    assert features["neck_front"]["station"] == pytest.approx([_in(0.07), _in(0.09)])
    assert features["neck_back"]["station"] == pytest.approx([_in(0.77), _in(0.79)])
    assert features["body_back"]["depth"] == pytest.approx([_in(0.85), _in(0.87)])
    assert features["neck_steps"]["station"] == pytest.approx([_in(0.34), _in(0.36)])
    breaks = features["neck_edge_breaks"]
    assert breaks["leg"] == pytest.approx([_in(0.075), _in(0.085)])
    assert breaks["angle_deg"] == 45.0 and breaks["count"] == 2
    assert breaks["edges"] == ["neck_front", "neck_back"]
    assert breaks["full_to_x"] == pytest.approx(_in(0.33))
    assert breaks["note"] == "CLEARS MHA-PN-01"
    vee = features["v_groove"]
    assert vee["flank_angle_deg"] == pytest.approx([44.0, 46.0])
    assert vee["flat_width"] == pytest.approx([_in(0.07), _in(0.09)])
    assert vee["mouth_near"] == pytest.approx([_in(0.18), _in(0.20)])
    assert vee["mouth_far"] == pytest.approx([_in(0.66), _in(0.68)])
    relief = features["relief"]
    assert relief["near_wall"] == pytest.approx([_in(0.11), _in(0.13)])
    assert relief["far_wall"] == pytest.approx([_in(0.73), _in(0.75)])
    assert relief["height"] == pytest.approx([_in(0.25), _in(0.27)])
    bore = features["pivot_bore"]
    assert bore["process"] == "drill" and bore["thru"] is True
    assert bore["dia"] == pytest.approx([_in(0.1285), _in(0.1325)], abs=1e-4)
    assert bore["station"] == pytest.approx([_in(0.48), _in(0.50)])
    assert bore["depth_station"] == pytest.approx([_in(0.42), _in(0.44)])
    assert bore["top_chamfer"] == pytest.approx([_in(0.012), _in(0.016)])
    tap = features["set_screw_tap"]
    assert tap["thread"] == "#4-40 UNC-2B" and tap["into"] == "pivot_bore"
    assert tap["dia"] == pytest.approx([_in(0.089), _in(0.093)], abs=1e-3)
    assert tap["height"] == pytest.approx([_in(0.46), _in(0.48)])
    assert tap["wall_min"][0] == pytest.approx(_in(0.064), abs=1e-3)
