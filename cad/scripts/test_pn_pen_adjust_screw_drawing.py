"""Offline contracts for the pen adjuster stud build and drawing."""

from __future__ import annotations

import ast
import math
from pathlib import Path

import pytest

import build_pn_pen_adjust_screw as part
import draw_pn_pen_adjust_screw as drawing
import pn_pen_adjust_screw_spec as spec
import pn_pen_rod_spec
from _drawing_contract import (
    PRECISION_MIGRATED_DRAWINGS,
    model_toleranced_dimensions,
)
from _drawing_registry import DRAWINGS_BY_NAME
from _hole_spec import HoleSpec, drill_process
from _holes import cross_hole_volume_mm3


def _source(module) -> str:
    return Path(module.__file__).read_text(encoding="utf-8")


def _calls(module, name: str) -> list[ast.Call]:
    tree = ast.parse(_source(module))
    return [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and (getattr(node.func, "id", None) or getattr(node.func, "attr", None)) == name
    ]


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/pn-pen-adjust-screw.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/pn-pen-adjust-screw.pdf")
    assert drawing.PNG.as_posix().endswith("/png/pn-pen-adjust-screw_drawing.png")
    entry = DRAWINGS_BY_NAME["pn_pen_adjust_screw"]
    assert entry.script == Path(drawing.__file__).resolve()
    assert entry.artifact_stem == part.PART_NAME


def test_spec_is_the_turned_brass_stud() -> None:
    assert spec.THREAD == pn_pen_rod_spec.STUD_THREAD == "#0-80"
    assert spec.THREAD_MAJOR == pytest.approx(1.524)
    assert spec.THREAD_PITCH == pytest.approx(25.4 / 80.0)
    assert spec.OVERALL_LENGTH == pytest.approx(26.0)
    assert (spec.HEAD_DIA, spec.HEAD_HEIGHT) == pytest.approx(
        (0.24 * 25.4, 0.32 * 25.4)
    )
    assert spec.SHANK_LENGTH == pytest.approx(26.0 - 0.32 * 25.4)
    assert spec.FULL_THREAD_LENGTH == pytest.approx(0.58 * 25.4)
    assert spec.PLAIN_SHANK == pytest.approx(26.0 - 0.90 * 25.4)
    assert spec.EYE_SPEC == HoleSpec("drilled_number", "#54")
    assert spec.EYE_DIA == pytest.approx(1.397)
    assert spec.EYE_FROM_HEAD_END == pytest.approx(0.16 * 25.4)
    assert spec.EYE_Y == pytest.approx(26.0 - 0.16 * 25.4)
    assert spec.THREAD_CALLOUT == "#0-80 UNF"


def test_every_wall_round_the_eye_clears_rule_17_at_worst_case() -> None:
    """drawing-guidelines.md rule 17: the eye's end, shoulder-side and side
    walls at the worst case of the printed bands (.XX on the station, the head
    height and the head Ø; DRILLED HOLES +.004 on the #54) stay >= the .080
    target."""
    from _inch_wall_limits import WALL_TARGET_MM
    from _printed_tolerance import drilled_oversize_mm, printed_band_mm

    band = printed_band_mm(2, unit=spec.UNIT)
    eye_r = (spec.EYE_DIA + drilled_oversize_mm(unit=spec.UNIT)) / 2.0
    end = spec.EYE_FROM_HEAD_END - band - eye_r
    shoulder = (spec.HEAD_HEIGHT - band) - (spec.EYE_FROM_HEAD_END + band) - eye_r
    side = (spec.HEAD_DIA - band) / 2.0 - eye_r
    assert (
        spec.EYE_END_WALL_MIN,
        spec.EYE_SHOULDER_WALL_MIN,
        spec.EYE_SIDE_WALL_MIN,
    ) == (
        pytest.approx(end),
        pytest.approx(shoulder),
        pytest.approx(side),
    )
    assert end == pytest.approx(3.0607)
    assert shoulder == pytest.approx(2.8067)
    assert side == pytest.approx(2.1717)
    assert min(end, shoulder, side) >= WALL_TARGET_MM


def test_full_thread_covers_engagement_nut_and_adjustment() -> None:
    """The shortest accepted full thread (title-block .XX band) still carries
    the rod engagement, the jam nut and the adjustment; the worst-case
    printed stack (the overall length at its printed 1.02 +/-.01) still
    leaves the die a pitch of run-out under the head (drawing-guidelines.md
    rule 16)."""
    import pn_vn_pen_adjust_nut_spec as jam_nut
    from _printed_tolerance import printed_band_mm

    band = printed_band_mm(2, unit=spec.UNIT)
    assert band == pytest.approx(0.254)
    assert spec.FULL_THREAD_LENGTH - band >= (
        pn_pen_rod_spec.STUD_ENGAGEMENT + jam_nut.THICKNESS + spec.ADJUSTMENT_RANGE
    )
    overall_min = (1.02 - 0.01) * 25.4
    assert spec.OVERALL_LENGTH + spec.OVERALL_DEVIATIONS[0] == pytest.approx(
        overall_min
    )
    worst_plain = (
        overall_min - (spec.HEAD_HEIGHT + band) - (spec.FULL_THREAD_LENGTH + band)
    )
    assert worst_plain == pytest.approx(spec.PLAIN_SHANK_MIN)
    assert worst_plain >= spec.THREAD_PITCH


def test_spec_is_the_single_source_of_drawing_dimensions() -> None:
    assert part.DRAWING_DIMENSIONS is spec.DRAWING_DIMENSIONS
    assert part.DRAWING_PRECISION is spec.DRAWING_PRECISION
    assert drawing.DRAWING_DIMENSIONS is spec.DRAWING_DIMENSIONS
    assert drawing.DRAWING_PRECISION_BY_NAME is spec.DRAWING_PRECISION_BY_NAME
    assert spec.DRAWING_DIMENSIONS == {
        "StudProfile": {
            "ThreadDia",
            "FullThreadLength",
            "HeadDia",
            "HeadHeight",
            "OverallLength",
            "PlainDia",
        },
        "EyeStationReference": {"EyeFromHeadEnd"},
        "ShoulderFillet": {"ShoulderRadius"},
    }
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert set(drawing.SIDE_KEEP) == marked
    assert {
        feature: set(names) for feature, names in spec.DRAWING_PRECISION.items()
    } == spec.DRAWING_DIMENSIONS
    assert spec.DRAWING_PRECISION_BY_NAME == {
        "ThreadDia": 3,
        "FullThreadLength": 2,
        "HeadDia": 2,
        "HeadHeight": 2,
        "OverallLength": 2,
        "PlainDia": 3,
        "EyeFromHeadEnd": 2,
        "ShoulderRadius": 2,
    }


def test_shoulder_root_prints_its_own_nominal_radius() -> None:
    """Rules 11 and 16: the shank-to-head corner is a modelled fillet whose
    radius prints natively as its own nominal at the title block's .XX: not
    the INSIDE CORNERS R.040 MAX restated. Nothing seats on the head's
    underside (the jam nut bears on the rod top and never reaches the
    shoulder). At its printed largest the fillet stays inside the INSIDE
    CORNERS limit, the die keeps a pitch of worst-case run-out and the fillet
    ends inside the head."""
    import pn_vn_pen_adjust_nut_spec as jam_nut
    from _printed_tolerance import printed_band_mm

    band = printed_band_mm(2, unit=spec.UNIT)
    assert spec.SHOULDER_FILLET_PLACES == 2
    assert spec.SHOULDER_FILLET_R / 25.4 == pytest.approx(0.02)
    largest = spec.SHOULDER_FILLET_R + band
    assert spec.SHOULDER_FILLET_R_PRINTED_MAX == pytest.approx(largest)
    assert largest <= spec.SHOULDER_CORNER_R_MAX == pytest.approx(0.040 * 25.4)
    limit = spec.PLAIN_SHANK_MIN - spec.THREAD_PITCH
    assert spec.SHOULDER_FILLET_R_LIMIT == pytest.approx(limit)
    assert largest <= limit
    assert spec.THREAD_MAJOR / 2.0 + largest < (spec.HEAD_DIA - band) / 2.0
    shortest_shank = (spec.OVERALL_LENGTH + spec.OVERALL_DEVIATIONS[0]) - (
        spec.HEAD_HEIGHT + band
    )
    assert spec.SHOULDER_OVER_ROD_TOP_MIN == pytest.approx(
        shortest_shank - pn_pen_rod_spec.STUD_TAP_SPEC.depth_mm
    )
    assert spec.SHOULDER_OVER_ROD_TOP_MIN > jam_nut.THICKNESS
    assert "ShoulderRadius" not in spec.DIMENSION_CALLOUTS
    assert set(drawing.UPPER_ARC_KEEP) == {"ShoulderRadius", "PlainDia"}


def test_shoulder_radius_leader_runs_through_the_centre_to_the_arc() -> None:
    """The R text stands in the quarter opposite each arc (the arc's own
    quarter is material), on the radial line through the centre, so the
    inside, opposite-side arrow touches the drawn arc from the concave side;
    the text's right end sits left of the bend, and the leader passes clear
    of the head-height extension line and right of the full-thread
    dimension's line end."""
    for side, keep in (
        ("lower", drawing.SIDE_KEEP["ShoulderRadius"]),
        ("upper", drawing.UPPER_ARC_KEEP["ShoulderRadius"]),
    ):
        cx, cy = drawing.SHOULDER_CENTRES[side]
        angle = math.radians(drawing.SHOULDER_LEADER_DEG[side])
        # The arc is the quarter facing the corner (+x, toward the axis);
        # the leader's direction lies in the opposite quarter.
        toward_axis = 1.0 if side == "lower" else -1.0
        assert math.cos(angle) < 0.0
        assert math.sin(angle) * toward_axis < 0.0
        right_end = keep[0] + drawing._SHOULDER_R_TEXT_WIDTH / 2.0
        bend = (right_end + drawing.RADIAL_BEND_GAP, keep[1] - drawing.RADIAL_BEND_DROP)
        # The bend lies on the radial line through the centre.
        assert math.atan2(bend[1] - cy, bend[0] - cx) == pytest.approx(
            math.atan2(math.sin(angle), math.cos(angle))
        )
        assert bend[0] < drawing.SHOULDER_X - 0.002
    lower_bend_x = (
        drawing.SIDE_KEEP["ShoulderRadius"][0]
        + drawing._SHOULDER_R_TEXT_WIDTH / 2.0
        + drawing.RADIAL_BEND_GAP
    )
    assert lower_bend_x > drawing.FULL_THREAD_X + 0.002


def test_plain_shank_diameter_prints_as_a_reference() -> None:
    """The plain shank's Ø is the thread blank: a StudProfile diametric
    dimension on the plain segment (the ThreadDia recipe, same axis and pick
    offset), driven by ThreadDia, printed parenthesised with no band. The
    drawing adds no dimension of its own: the silhouette route failed twice
    on the farm (no lower flank through the pick; AddDimension refused the
    pair)."""
    assert spec.REFERENCE_DIMENSIONS == frozenset({"PlainDia"})
    assert spec.REFERENCE_DIMENSIONS <= spec.DRAWING_DIMENSIONS["StudProfile"]
    assert not hasattr(spec, "DRAWING_REFERENCE_PRECISION")
    assert not model_toleranced_dimensions(part)


def test_every_marked_dimension_is_created_and_named_by_the_build() -> None:
    """Each printed name is recorded on the sketch whose feature the spec keys
    it under, so mark_dimensions_for_drawing finds exactly that set."""
    assert part.EYE_Y_EXPR == '"OverallLength" - "HeadHeight" / 2'
    assert part.EYE_FROM_HEAD_END_EXPR == '"HeadHeight" / 2'


def test_the_eye_station_is_located_from_the_head_end() -> None:
    """drawing-guidelines.md rule 11: the head's features from its own faced
    end. The reference line runs from the eye up to the head end; only its
    length (the eye's station from that face) is marked."""
    assert "HeadEndStation" not in set().union(*spec.DRAWING_DIMENSIONS.values())


def test_a_split_line_rings_the_shank_at_the_thread_limit() -> None:
    """The revolve merges the collinear thread and plain-shank segments, so a
    projected split line (both directions: a full ring) at FullThreadLength
    leaves the real edge the side view draws and the FULL THREAD extension
    line lands on; the build checks the two faces' areas."""
    assert part._PLAIN_FACE_AREA == pytest.approx(
        math.pi * spec.THREAD_MAJOR * spec.PLAIN_SHANK
    )
    assert part._THREAD_FACE_AREA == pytest.approx(
        math.pi * spec.THREAD_MAJOR * spec.FULL_THREAD_LENGTH
    )
    assert not hasattr(part, "_SHANK_WITNESS_LEN")


def test_every_sketch_faces_the_side_view() -> None:
    """All marked dimensions live on Right-plane sketches: the *Right side
    view, which sees the X eye end-on, imports them natively."""
    assert drawing.SIDE_VIEW_ANGLE == -math.pi / 2.0


def test_volumes_are_analytic() -> None:
    r_thread, r_head = spec.THREAD_MAJOR / 2.0, spec.HEAD_DIA / 2.0
    stud = math.pi * (r_thread**2 * spec.SHANK_LENGTH + r_head**2 * spec.HEAD_HEIGHT)
    assert part.V_STUD == pytest.approx(stud)
    assert part.V_EYE == pytest.approx(
        cross_hole_volume_mm3(spec.EYE_DIA, spec.HEAD_DIA)
    )
    # The eye is smaller than the full drill cylinder through the head.
    assert part.V_EYE < math.pi * (spec.EYE_DIA / 2.0) ** 2 * spec.HEAD_DIA
    r_fillet = spec.SHOULDER_FILLET_R
    spandrel = r_fillet**2 * (1.0 - math.pi / 4.0)
    centroid_r = r_thread + r_fillet * (10.0 - 3.0 * math.pi) / (3.0 * (4.0 - math.pi))
    assert part.V_FILLET == pytest.approx(2.0 * math.pi * centroid_r * spandrel)
    # About 0.3 mm^3 of a ~260 mm^3 stud at R.02.
    assert 0.0 < part.V_FILLET < 2.0
    assert part.V_TOTAL == pytest.approx(stud + part.V_FILLET - part.V_EYE)


def test_no_gdt_no_pmi_no_roughness() -> None:
    """drawing-simplicity-policy.md rule 5: the stud is not on the GD&T
    allowlist; rule 6: nothing on it runs, slides or locates."""
    assert model_toleranced_dimensions(part) == {}


def test_eye_prints_the_native_wizard_callout() -> None:
    assert drill_process(spec.EYE_SPEC) == "#54 DRILL"


def test_thread_callout_rides_the_model_and_no_notes() -> None:
    """The thread prints as its designation on the native major-diameter
    dimension (no Ø1.524, no class: the title block's THREADS row owns it),
    the full-thread length as a native dimension with a word callout; no
    general note (the title block's edge-break covers the eye)."""
    assert spec.DIMENSION_TEXT == {"ThreadDia": "#0-80 UNF"}
    assert spec.DIMENSION_CALLOUTS == {"FullThreadLength": "FULL THREAD"}
    for text in (*spec.DIMENSION_TEXT.values(), *spec.DIMENSION_CALLOUTS.values()):
        assert "2A" not in text and "." not in text
    assert not any(c.isdigit() for c in spec.DIMENSION_CALLOUTS["FullThreadLength"])
    draw_source = _source(drawing)
    assert "set_dimension_text(adapter, annotations, DIMENSION_TEXT)" in draw_source
    assert (
        "set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS, "
        'location="below")'
    ) in draw_source
    assert not _calls(drawing, "add_attached_note")
    assert spec.DRAWING_NOTES == ""
    for module in (part, drawing):
        assert "Manufacturing Notes" not in _source(module)
        assert "add_property_linked_note" not in _source(module)


def test_part_stamps_make_critical_properties() -> None:
    import _config

    assert part._SAVED_DRAWING_PROPERTIES == (
        "Number",
        "Material Specification",
        "Finish",
        "Quantity",
    )
    assert part.MATERIAL == "Brass"
    row = _config.parts(part.PART_NAME)
    assert row["number"] == "MHA-PN-07"
    assert row["material"] == "Brass"
    assert "brass" in row["material_specification"].lower()
    assert row["finish"]
    assert "DEBUR" not in row["finish"].upper()
    assert int(row["quantity"]) == 1
    numbers = [str(other["number"]) for other in _config.parts().values()]
    assert numbers.count("MHA-PN-07") == 1


def test_the_part_owns_the_printed_precision() -> None:
    assert "draw_pn_pen_adjust_screw.py" in PRECISION_MIGRATED_DRAWINGS


def test_side_view_layout_reads_like_the_lathe() -> None:
    """Threaded end left, head right; lengths below in two rows (full thread
    and head, then the overall), the eye's station above from the head end;
    the eye callout up-left so its leader crosses no dimension or extension
    line; everything inside the B-size border."""
    assert drawing.SHEET_SCALE == (6.0, 1.0)
    assert (
        drawing.THREAD_END_X
        < drawing.FULL_THREAD_X
        < drawing.SHOULDER_X
        < drawing.EYE_X
        < drawing.TOP_X
    )
    assert drawing.TOP_X - drawing.THREAD_END_X == pytest.approx(
        spec.OVERALL_LENGTH * drawing._S
    )
    keep = drawing.SIDE_KEEP
    head_bottom = drawing.AXIS_Y - drawing.HEAD_HALF
    head_top = drawing.AXIS_Y + drawing.HEAD_HALF
    assert keep["FullThreadLength"][1] == keep["HeadHeight"][1] < head_bottom
    # Row 2 a callout line plus a text height below row 1.
    assert keep["FullThreadLength"][1] - keep["OverallLength"][1] >= 0.015
    assert (
        keep["FullThreadLength"][1]
        < keep["ThreadDia"][1]
        < drawing.AXIS_Y - drawing.THREAD_HALF
    )
    assert drawing.THREAD_END_X < keep["ThreadDia"][0] < drawing.FULL_THREAD_X
    assert keep["EyeFromHeadEnd"][1] > head_top
    assert drawing.EYE_X < keep["EyeFromHeadEnd"][0] < drawing.TOP_X
    assert keep["HeadDia"][0] > drawing.TOP_X
    # The plain shank's reference Ø: above the plain shank (below it the
    # FULL THREAD extension line drops to row 1), over the head's top
    # silhouette, under the eye callout's text row.
    shank_x, shank_y = keep["PlainDia"]
    assert drawing.FULL_THREAD_X < shank_x < drawing.SHOULDER_X
    assert head_top < shank_y < drawing.EYE_CALLOUT_XY[1] - 0.008
    # The eye callout: text right end left of the eye's centre (the station
    # dimension's extension line), above the head, clear of the threaded end.
    half_width = drawing._EYE_CALLOUT_TEXT_WIDTH / 2.0
    assert drawing.EYE_CALLOUT_XY[0] + half_width < drawing.EYE_X
    assert drawing.EYE_CALLOUT_XY[0] - half_width > drawing.THREAD_END_X
    assert head_top < drawing.EYE_CALLOUT_XY[1]
    rim_x, rim_y = drawing.EYE_RIM_PICK
    assert math.hypot(rim_x - drawing.EYE_X, rim_y - drawing.AXIS_Y) == pytest.approx(
        drawing.EYE_HALF
    )
    # Up-left quadrant, so the leader never reaches the extension line rising
    # through the eye's centre.
    assert rim_x < drawing.EYE_X and rim_y > drawing.AXIS_Y
    assert drawing.THREAD_END_X > 0.020
    # The isometric's ~145 mm height stays inside the border and title block.
    assert drawing.ISO_CENTER[1] - 0.075 > 0.065
    assert drawing.ISO_CENTER[1] + 0.075 < 0.267
