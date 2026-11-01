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
    drawing_specification_violations,
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


def _literal_args(call: ast.Call) -> list[object]:
    return [arg.value for arg in call.args if isinstance(arg, ast.Constant)]


def _keyword(call: ast.Call, name: str) -> ast.expr:
    (value,) = (kw.value for kw in call.keywords if kw.arg == name)
    return value


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
        "ShoulderRadius": 3,
    }


def test_shoulder_root_prints_the_title_block_max_radius() -> None:
    """Rules 11 and 16: the shank-to-head corner is a modelled fillet whose
    size prints natively as R MAX. Nothing seats on the head's underside (the
    jam nut bears on the rod top and never reaches the shoulder), so the
    limit is the title block's INSIDE CORNERS R.040, the model stands at it,
    and at that limit the die keeps a pitch of worst-case run-out and the
    fillet ends inside the head."""
    import pn_vn_pen_adjust_nut_spec as jam_nut
    from _printed_tolerance import printed_band_mm

    band = printed_band_mm(2, unit=spec.UNIT)
    assert spec.SHOULDER_CORNER_R_MAX == pytest.approx(0.040 * 25.4)
    assert spec.SHOULDER_FILLET_R == spec.SHOULDER_CORNER_R_MAX
    assert spec.SHOULDER_FILLET_BAND == (0.0, -spec.SHOULDER_FILLET_R)
    assert spec.SHOULDER_FILLET_TOL_TYPE == 6  # swTolMAX
    assert spec.SHOULDER_FILLET_PLACES == 3
    limit = spec.PLAIN_SHANK_MIN - spec.THREAD_PITCH
    assert spec.SHOULDER_FILLET_R_LIMIT == pytest.approx(limit)
    assert spec.SHOULDER_FILLET_R <= limit
    assert spec.THREAD_MAJOR / 2.0 + spec.SHOULDER_FILLET_R < (
        (spec.HEAD_DIA - band) / 2.0
    )
    shortest_shank = (spec.OVERALL_LENGTH + spec.OVERALL_DEVIATIONS[0]) - (
        spec.HEAD_HEIGHT + band
    )
    assert spec.SHOULDER_OVER_ROD_TOP_MIN == pytest.approx(
        shortest_shank - pn_pen_rod_spec.STUD_TAP_SPEC.depth_mm
    )
    assert spec.SHOULDER_OVER_ROD_TOP_MIN > jam_nut.THICKNESS
    assert "ShoulderRadius" not in spec.DIMENSION_CALLOUTS
    source = _source(part)
    assert "tolerance.Type = SHOULDER_FILLET_TOL_TYPE" in source
    build_body = source[source.index("async def build(") :]
    assert build_body.index(
        "apply_drawing_precision(adapter, DRAWING_PRECISION)"
    ) < build_body.index("_shoulder_fillet_max_limit(adapter)")
    # The sheet proves the import kept the MAX type and the radial form, and
    # lays the radius out for whichever corner arc SolidWorks hung it on.
    draw_source = _source(drawing)
    assert "_dress_shoulder_radius(adapter, drawing_model, by_name, spt)" in (
        draw_source
    )
    assert "int(tolerance.Type) != SHOULDER_FILLET_TOL_TYPE" in draw_source
    assert set(drawing.UPPER_ARC_KEEP) == {"ShoulderRadius", "PlainDia"}


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
    source = _source(part)
    assert 'profile.record("PlainDia", \'"ThreadDia"\')' in source
    calls = {
        ast.literal_eval(call.args[-1]): [ast.unparse(arg) for arg in call.args[1:4]]
        for call in _calls(part, "add_diametric_linear_dimension")
    }
    assert calls["ThreadDia"] == [
        "axis",
        "thread",
        "(THREAD_R + 4.0, FULL_THREAD_LENGTH / 2.0)",
    ]
    # Same axis, same pick offset, on the plain segment's mid-height; to its
    # free (shoulder) end, which replaces the segment's vertical relation.
    assert calls["PlainDia"] == [
        "axis",
        "f'{shank}.end'",
        "(THREAD_R + 4.0, FULL_THREAD_LENGTH + PLAIN_SHANK / 2.0)",
    ]
    assert '("plain shank", shank, "vertical")' not in source
    assert "ShankDia" not in source
    assert not model_toleranced_dimensions(part)
    draw_source = _source(drawing)
    for gone in ("add_edge_dimension", "_face_silhouette_pair", "SetPrecision3"):
        assert gone not in draw_source
    assert "for name in sorted(REFERENCE_DIMENSIONS):" in draw_source
    (reference,) = _calls(drawing, "set_reference_dimension")
    assert ast.literal_eval(_keyword(reference, "diameter")) is True


def test_every_marked_dimension_is_created_and_named_by_the_build() -> None:
    """Each printed name is recorded on the sketch whose feature the spec keys
    it under, so mark_dimensions_for_drawing finds exactly that set."""
    source = _source(part)
    for name in (
        "ThreadDia",
        "FullThreadLength",
        "HeadDia",
        "HeadHeight",
        "OverallLength",
    ):
        assert f'profile.record("{name}", \'"{name}"\')' in source
    assert 'station.record("HeadEndStation", \'"OverallLength"\')' in source
    assert 'station.record("EyeFromHeadEnd", EYE_FROM_HEAD_END_EXPR)' in source
    assert 'drive_jobs += profile.apply(adapter, "StudProfile")' in source
    assert 'drive_jobs += station.apply(adapter, "EyeStationReference")' in source
    assert 'drive_jobs = dims.apply(adapter, "ThreadLimitReference")' in source
    assert "drive_jobs += await _add_thread_limit(adapter)" in source
    assert part.EYE_Y_EXPR == '"OverallLength" - "HeadHeight" / 2'
    assert part.EYE_FROM_HEAD_END_EXPR == '"HeadHeight" / 2'
    assert "apply_drawing_precision(adapter, DRAWING_PRECISION)" in source
    assert "clear_dimensions_for_drawing(adapter)" in source
    assert (
        "mark_dimensions_for_drawing(adapter, feature_name, dimension_names)" in source
    )


def test_the_eye_station_is_located_from_the_head_end() -> None:
    """drawing-guidelines.md rule 11: the head's features from its own faced
    end. The reference line runs from the eye up to the head end; only its
    length (the eye's station from that face) is marked."""
    (line,) = (
        call
        for call in _calls(part, "add_line")
        if [ast.unparse(arg) for arg in call.args][1] == "EYE_Y"
    )
    assert [ast.unparse(arg) for arg in line.args] == [
        "0.0",
        "EYE_Y",
        "0.0",
        "OVERALL_LENGTH",
    ]
    assert "HeadEndStation" not in set().union(*spec.DRAWING_DIMENSIONS.values())


def test_profile_splits_the_thread_limit_off_the_plain_shank() -> None:
    """The full thread is its own profile segment (FullThreadLength measures
    it); the shoulder sits at the shank length."""
    source = _source(part)
    assert "(THREAD_R, FULL_THREAD_LENGTH)," in source
    assert "(THREAD_R, SHANK_LENGTH)," in source
    assert "(HEAD_R, SHANK_LENGTH)," in source
    assert (
        "end, thread, shank, shoulder, head, top, closure = await add_line_chain("
        in source
    )
    # The plain segment's x rides PlainDia (to its shoulder end), not a
    # vertical relation: its start is the thread's end.
    assert '("thread", thread, "vertical"),' in source


def test_a_split_line_rings_the_shank_at_the_thread_limit() -> None:
    """The revolve merges the collinear thread and plain-shank segments, so a
    projected split line (both directions: a full ring) at FullThreadLength
    leaves the real edge the side view draws and the FULL THREAD extension
    line lands on; the build checks the two faces' areas."""
    source = _source(part)
    assert "model.InsertSplitLineProject(False, False)" in source
    assert '_feature_by_name(adapter, created).Name = "ThreadLimitSplit"' in source
    assert 'dims.record("ThreadLimitStation", \'"FullThreadLength"\')' in source
    (split,) = (
        call
        for call in _calls(part, "add_line")
        if [ast.unparse(arg) for arg in call.args]
        == ["-reach", "FULL_THREAD_LENGTH", "reach", "FULL_THREAD_LENGTH"]
    )
    assert part._PLAIN_FACE_AREA == pytest.approx(
        math.pi * spec.THREAD_MAJOR * spec.PLAIN_SHANK
    )
    assert part._THREAD_FACE_AREA == pytest.approx(
        math.pi * spec.THREAD_MAJOR * spec.FULL_THREAD_LENGTH
    )
    assert not hasattr(part, "_SHANK_WITNESS_LEN")
    assert '"thread-limit split cuts nothing", stud_volume' in source


def test_feature_names_are_the_contract() -> None:
    named = [_literal_args(call)[0] for call in _calls(part, "name_last_feature")]
    assert sorted(named) == sorted(
        [
            "StudProfile",
            "Stud",
            "ThreadLimitReference",
            "ShoulderFillet",
            "EyeStationPlane",
            "EyeStationReference",
        ]
    )
    source = _source(part)
    build_body = source[source.index("async def build(") :]
    assert (
        build_body.index('"Stud")')
        < build_body.index("_add_thread_limit(adapter)")
        < build_body.index('"ShoulderFillet")')
        < build_body.index('"EyeStationPlane")')
    )
    (eye,) = _calls(part, "wizard_hole_on_cylinder")
    assert ast.literal_eval(_keyword(eye, "name")) == "EyeHole"
    assert ast.literal_eval(_keyword(eye, "point_planes")) == (
        "EyeStationPlane",
        "Front Plane",
    )
    assert ast.unparse(eye.args[1]) == "EYE_SPEC"
    # Radially into the head's cylinder at +X: the drill runs along X.
    assert ast.unparse(eye.args[2]) == "[HEAD_R, EYE_Y, 0.0]"
    (plane,) = _calls(part, "CreatePlaneParameters")
    assert ast.literal_eval(_keyword(plane, "base_plane")) == "Top Plane"
    assert ast.unparse(_keyword(plane, "offset")) == "EYE_Y"


def test_every_sketch_faces_the_side_view() -> None:
    """All marked dimensions live on Right-plane sketches: the *Right side
    view, which sees the X eye end-on, imports them natively."""
    source = _source(part)
    assert source.count('create_sketch("Right")') == 3
    assert 'create_sketch("Front")' not in source
    assert 'create_sketch("Top")' not in source
    draw_source = _source(drawing)
    assert '"*Right", *SIDE_CENTER, scale=VIEW_SCALE' in draw_source
    assert drawing.SIDE_VIEW_ANGLE == -math.pi / 2.0
    assert "RevolveParameters(angle=360.0)" in source
    assert len(_calls(part, "create_revolve")) == 1


def test_stud_axis_is_axis1_through_the_origin() -> None:
    (axis,) = _calls(part, "name_bore_axis")
    assert _literal_args(axis)[:4] == ["Front Plane", 0.0, "Right Plane", 0.0]
    assert 'if stud_axis != "Axis1":' in _source(part)


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
    # About 1.4 mm^3 of a ~260 mm^3 stud at R.040.
    assert 0.0 < part.V_FILLET < 2.0
    assert part.V_TOTAL == pytest.approx(stud + part.V_FILLET - part.V_EYE)
    source = _source(part)
    assert 'volume_check(adapter, "stud", V_STUD,' in source
    assert 'volume_check(adapter, "eye cross hole", V_TOTAL,' in source
    assert '"cosmetic thread cuts nothing", driven, 1e-6' in source
    assert 'stud_volume = await volume_check(adapter, "stud", V_STUD,' in source
    assert '"shoulder root fillet", stud_volume + V_FILLET, 0.5 * V_FILLET' in source


def test_cosmetic_thread_runs_the_full_thread_only() -> None:
    (thread,) = _calls(part, "AddThreadParameters")
    assert ast.unparse(_keyword(thread, "edge_point")) == "[THREAD_R, 0.0, 0.0]"
    assert ast.unparse(_keyword(thread, "size")) == "THREAD"
    assert ast.literal_eval(_keyword(thread, "end_type")) == "blind"
    assert ast.unparse(_keyword(thread, "depth")) == "FULL_THREAD_LENGTH"
    assert "import_cosmetic_threads(adapter, iso)" in _source(drawing)


def test_no_gdt_no_pmi_no_roughness() -> None:
    """drawing-simplicity-policy.md rule 5: the stud is not on the GD&T
    allowlist; rule 6: nothing on it runs, slides or locates."""
    for module in (part, drawing):
        source = _source(module)
        for forbidden in (
            "author_part_pmi",
            "PART_DATUMS",
            "GEOMETRIC_CONTROLS",
            "_gtol",
            "add_datum_feature(",
            "add_feature_control_frame(",
            "set_basic_dimension",
            "add_surface_finish(",
            "SURFACE_FINISHES",
        ):
            assert forbidden not in source, (module.__name__, forbidden)
    assert model_toleranced_dimensions(part) == {}
    assert "add_view_centerline(" in _source(drawing)


def test_eye_prints_the_native_wizard_callout() -> None:
    (callout,) = _calls(drawing, "add_native_hole_callout")
    assert ast.unparse(_keyword(callout, "process")) == "drill_process(EYE_SPEC)"
    assert drill_process(spec.EYE_SPEC) == "#54 DRILL"
    assert "auto_center_marks(adapter, side, holes=True" in _source(drawing)


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

    source = _source(part)
    assert "apply_drawing_properties(adapter, PART_NAME)" in source
    assert (
        "require_saved_drawing_properties(adapter, _SAVED_DRAWING_PROPERTIES)" in source
    )
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
    draw_source = _source(drawing)
    assert (
        "assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)"
        in draw_source
    )
    assert "draw_pn_pen_adjust_screw.py" in PRECISION_MIGRATED_DRAWINGS
    assert not drawing_specification_violations(draw_source, filename=drawing.__file__)


def test_side_view_layout_reads_like_the_lathe() -> None:
    """Threaded end left, head right; lengths below in two rows (full thread
    and head, then the overall), the eye's station above from the head end;
    the eye callout up-left so its leader crosses no dimension or extension
    line; everything inside the B-size border."""
    assert drawing.SHEET_SCALE == (6.0, 1.0)
    assert '"*Isometric", *ISO_CENTER, scale=VIEW_SCALE' in _source(drawing)
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
