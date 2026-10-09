"""Offline contracts for the crank-pinion drawing.

The print is recreated under ``cad/docs/drawing-simplicity-policy.md``: a
custom 16T pinion with a hub boss and a match-drilled retention pin
carries no datums or frames, its turned sizes and lengths are native model
dimensions whose places and bands the PART owns, the pin hole is governed by
its matched-fit feature callout, and the tooth system it cannot dimension
lives in the gear-data block.
"""

from __future__ import annotations

import asyncio
import math
import re
from pathlib import Path

import pytest

import _config
import build_dt_crank_pinion as part
import dt_crank_pinion_spec as spec
import dt_crank_pinion_notes as notes
import dt_crank_drive_gear_spec as mate
import dt_crankshaft_spec
import draw_dt_crank_pinion as drawing
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS
from _drawing_registry import DRAWINGS_BY_NAME


def _source() -> str:
    return Path(drawing.__file__).read_text(encoding="utf-8")


def _build_source() -> str:
    return Path(part.__file__).read_text(encoding="utf-8")


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/dt-crank-pinion.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/dt-crank-pinion.pdf")
    assert drawing.PNG.as_posix().endswith("/png/dt-crank-pinion_drawing.png")
    assert DRAWINGS_BY_NAME["dt_crank_pinion"].script == Path(drawing.__file__).resolve()


def test_spec_is_the_single_source_of_the_marked_dimension_set() -> None:
    # The drift alarm: the part-side mark set and the drawing-side keep set are
    # BOTH the shared spec's map, so a rename in one script that is not
    # mirrored in the other fails here, offline.
    assert part.DRAWING_DIMENSIONS is spec.DRAWING_DIMENSIONS
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.FRONT_KEEP) | set(drawing.RIGHT_KEEP)
    assert (
        kept
        == marked
        == {
            "OutsideDia",
            "FaceWidth",
            "BoreDia",
            "BossDia",
            "OverallLength",
            "ShoulderLength",
            "TurnedDia",
        }
    )
    assert set(drawing.DIMENSION_CALLOUTS) <= kept
    # Turned part (rules 7 and 12): every diameter sits beside its axial extent
    # on the longitudinal section. The tip circle and bore are native
    # construction-reference dimensions in the Right-plane boss profile, not
    # numbers authored by the drawing; the end view is left dimension-free.
    assert drawing.FRONT_KEEP == {}
    assert set(drawing.RIGHT_KEEP) == {
        "OutsideDia",
        "BoreDia",
        "BossDia",
        "FaceWidth",
        "OverallLength",
        "ShoulderLength",
        "TurnedDia",
    }
    assert spec.DRAWING_DIMENSIONS["BossProfile"] == {
        "OutsideDia",
        "BoreDia",
        "BossDia",
        "OverallLength",
    }


def test_the_blank_sizes_are_native_model_dimensions() -> None:
    # Rule 1: the outside diameter and the face width are turned before a
    # cutter touches the part, so they are model dimensions of the gear blank
    # the shared helper builds -- named, driven and toleranced HERE, never
    # retyped into the gear-data block as text.
    build = _build_source()
    assert '"Boss-Extrude1").Name = "GearBlank"' in build
    assert '"Sketch1").Name = "GearBlankProfile"' in build
    assert 'name_dimensions(adapter, "GearBlank", ["FaceWidth"])' in build
    assert 'name_dimensions(adapter, "GearBlankProfile", ["OutsideDia"])' in build
    # Driven, so a default-name rename that resolved the wrong feature moves
    # the blank and the equation-neutral volume gate fails loud.
    assert '\'"FaceWidth"\'' in build
    assert '\'"OutsideDia"\'' in build
    assert 'set_global(adapter, "OutsideDia"' in build
    minimum_support = min(
        profile.support_radius_max_mm for _, profile in spec.STOCK_PROFILE_CORNERS
    )
    scale = 10**spec.DRAWING_PRECISION_BY_NAME["OutsideDia"]
    assert spec.OUTSIDE_DIA == math.floor(
        (2.0 * minimum_support - spec.OUTSIDE_DIA_TOLERANCE_MM) * scale
    ) / scale
    assert spec.FACE_WIDTH == part.FACE_WIDTH
    assert spec.BORE_DIA == pytest.approx(part.BORE_DIAMETER)
    assert "OUTSIDE DIAMETER" not in notes.GEAR_DATA
    assert "FACE WIDTH" not in notes.GEAR_DATA


def test_precision_is_authored_on_the_part_and_only_read_by_the_sheet() -> None:
    # Rule 2: the places a dimension prints are part of the tolerance it
    # claims, so the model owns them. The overall length is a look (the shaft
    # end recessed inside the boss), not a fit: one place like the face width.
    assert spec.DRAWING_PRECISION_BY_NAME == {
        "OutsideDia": 2,
        "FaceWidth": 1,
        "BoreDia": 3,
        "BossDia": 1,
        "OverallLength": 1,
        "ShoulderLength": 1,
        "TurnedDia": 2,
    }
    assert "draw_dt_crank_pinion.py" in PRECISION_MIGRATED_DRAWINGS
    source = _source()
    assert "set_dimension_precision" not in source
    assert "SetPrecision3" not in source
    assert "DIMENSION_PRECISION" not in source
    assert "assert_imported_precision(" in source
    assert "apply_drawing_precision(adapter, DRAWING_PRECISION)" in _build_source()


def test_grown_teeth_keep_the_south_seat_and_boss_length() -> None:
    # The tooth length follows the part spec; the W15 boss is sized from the
    # published pin, recess and printed allowances, not a former face pin.
    assert spec.FACE_WIDTH == part.FACE_WIDTH
    assert spec.BOSS_LENGTH == spec.ceil_to_places(
        2.0
        * (
            spec.PIN_EDGE_MIN_WORST
            + spec.SHAFT_END_RECESS_MAX
            + spec.PIN_DIA / 2.0
            + spec._PIN_EDGE_CLOSING_TERMS
        ),
        spec.BOSS_LENGTH_PLACES,
    )
    assert spec.OVERALL_LENGTH == pytest.approx(spec.FACE_WIDTH + spec.BOSS_LENGTH)
    assert spec.PIN_STATION == pytest.approx(spec.FACE_WIDTH + spec.BOSS_LENGTH / 2.0)
    # The turned band is a real band at every accepted size.
    shoulder_long = spec.SHOULDER_LENGTH + spec.SHOULDER_LENGTH_LIMITS[1]
    assert shoulder_long < spec.FACE_WIDTH + spec.FACE_WIDTH_LIMITS[0]
    assert spec.BOSS_DIA < spec.TURNED_DIA - spec.TURNED_DIA_TOLERANCE_MM
    assert (
        spec.TURNED_DIA + spec.TURNED_DIA_TOLERANCE_MM
        < spec.OUTSIDE_DIA - spec.OUTSIDE_DIA_TOLERANCE_MM
    )


def test_the_boss_is_the_root_circle_and_the_pin_hole_stays_in_its_wall() -> None:
    # ch12 p.19: the hub boss is the tooth-root cylinder carried on past the
    # face, so the boss needs no second turned diameter and the tooth root
    # relief runs out into it. The pin hole sits at the boss's mid-length,
    # clear of the tooth face and of the end break, on the pinion's own -X.
    assert spec.BOSS_DIA == pytest.approx(spec.ROOT_DIA)
    assert spec.OVERALL_LENGTH == pytest.approx(spec.FACE_WIDTH + spec.BOSS_LENGTH)
    assert spec.PIN_STATION == pytest.approx(spec.FACE_WIDTH + spec.BOSS_LENGTH / 2)
    assert spec.PIN_STATION - spec.PIN_DIA / 2 > spec.FACE_WIDTH
    assert spec.PIN_STATION + spec.PIN_DIA / 2 < spec.OVERALL_LENGTH - 0.5
    assert spec.PIN_LENGTH == spec.BOSS_DIA
    build = _build_source()
    assert "[-BOSS_DIA / 2.0, 0.0, PIN_STATION]" in build
    assert 'point_planes=("PinStationPlane", "Top Plane")' in build
    # The station is a model dimension (a plane offset driven from the same
    # knobs), but match drilling governs the printed location.
    assert '\'"FaceWidth" + "BossLength" / 2\'' in build




def _assert_four_fact_note(note: str, mate_number: str) -> None:
    """Rule 6 (Main, 2026-09-25): at most four lines, no dimensions, and --
    because each sheet stands alone -- all four facts of the matched fit:
    match drill at assembly with the named mate (and where it runs), ream to
    fit the named pin, the fit's acceptance, flush both sides."""
    lines = note.split("\n")
    text = " ".join(lines)
    assert len(lines) <= 4
    assert lines[0] == f"MATCH DRILL AT ASSY WITH {mate_number}"
    assert "BOSS MID-LENGTH" in lines[1]
    assert f"REAM TO FIT PIN {spec.PIN_NUMBER}" in text
    assert "LIGHT HAMMER FIT" in text and "NOT REMOVABLE BY HAND" in text
    assert "FLUSH BOTH SIDES" in text
    bare = text.replace(mate_number, "").replace(spec.PIN_NUMBER, "")
    assert not any(ch.isdigit() for ch in bare)


def test_both_sheets_carry_the_same_four_fact_pin_hole_note() -> None:
    # Machinist review of 4d4e038e3: the shaft's bare transfer note gave no
    # size, process or fit, and the pinion's four-line trim had dropped the
    # fit's acceptance. Both sheets carry all four facts; line breaks may differ
    # to fit their independent note fields.
    _assert_four_fact_note(drawing.PIN_HOLE_NOTE, spec.CRANKSHAFT_NUMBER)
    _assert_four_fact_note(spec.CRANKSHAFT_PIN_HOLE_PROCESS, spec.PINION_NUMBER)
    pinion = drawing.PIN_HOLE_NOTE.split("\n")
    assert drawing.PIN_HOLE_NOTE == spec.PIN_HOLE_PROCESS
    crankshaft_drawing = Path(drawing.__file__).with_name("draw_dt_crankshaft.py").read_text(
        encoding="utf-8"
    )
    assert "text=CRANKSHAFT_PIN_HOLE_PROCESS," in crankshaft_drawing
    # The four-line block (upper-left anchored; ~0.8h a character, ~1.7h a
    # line) stays under the border and above the section and isometric.
    height = drawing.PIN_HOLE_NOTE_HEIGHT
    x0, top = drawing.PIN_HOLE_CALLOUT
    right = x0 + 0.8 * height * max(map(len, pinion))
    bottom = top - 1.7 * height * len(pinion)
    assert top < drawing.SHEET_INNER_BORDER[3] and right < drawing.SHEET_INNER_BORDER[2]
    assert bottom > drawing.RIGHT_CENTER[1] + drawing.HALF_OD + 0.010
    assert bottom > drawing.ISO_CENTER[1] + drawing.HALF_OD + 0.010
    source = _source().replace("\r\n", "\n")
    assert "PIN_HOLE_NOTE,\n        text_xy=PIN_HOLE_CALLOUT," in source


def test_the_boss_end_takes_the_title_block_break_not_a_sized_chamfer() -> None:
    # Machinist review of 4d4e038e3: the 1.0 x 45 chamfer only imitated the
    # photo's rounding, and at its one-place grade it could reach the bore.
    spec_source = Path(spec.__file__).read_text(encoding="utf-8")
    for text in (_build_source(), _source(), spec_source):
        assert "BossChamfer" not in text
        assert "BOSS_CHAMFER" not in text
    assert "add_chamfer" not in _build_source()


def test_boss_dia_text_clears_its_extension_lines() -> None:
    # Machinist review of 4d4e038e3 (clarity): the diameter text at +0.020
    # sat on the upper extension line at +HALF_BOSS. The sheet-side check
    # reads the native display data; here the same predicate runs on the
    # layout, and rejects the reviewed placement.
    x_end = drawing._side_x(spec.OVERALL_LENGTH)
    x_dim = drawing.BOSS_DIA_TEXT_X
    y_axis = drawing.RIGHT_CENTER[1]
    height = 0.0035
    extension = [
        ((x_end, y_axis + side * drawing.HALF_BOSS), (x_dim + 0.002, y_axis + side * drawing.HALF_BOSS))
        for side in (1.0, -1.0)
    ]
    dimension_line = [((x_dim, y_axis - drawing.HALF_BOSS), (x_dim, y_axis + drawing.HALF_BOSS))]
    lines = extension + dimension_line
    gap = drawing.DIMENSION_TEXT_LINE_GAP
    reviewed = [(x_dim - 0.006, y_axis + 0.020, height)]
    assert drawing._text_line_crossings(reviewed, lines, gap) == [extension[0]]
    x, y = drawing.RIGHT_KEEP["BossDia"]
    assert drawing._text_line_crossings([(x - 0.006, y, height)], lines, gap) == []
    assert "_boss_dia_text_crossings(adapter, right_annotations)" in _source()


def test_isometric_clears_the_boss_dia_text() -> None:
    # Bound the current blank by its circumscribed radius, not a former
    # isometric's measured offsets. Native view extents still gate export.
    extent = (
        math.hypot(spec.OUTSIDE_DIA / 2.0, spec.OVERALL_LENGTH / 2.0)
        * drawing.VIEW_SCALE[0]
        / drawing.VIEW_SCALE[1]
        / 1000.0
        + 0.0056
    )
    text_right = (
        drawing.BOSS_DIA_TEXT_X
        + drawing.BOSS_DIA_TEXT_HALF_WIDTH
        + drawing.ISO_TEXT_CLEARANCE
    )
    assert drawing.ISO_CENTER[0] - extent >= text_right
    assert drawing.ISO_CENTER[0] + extent <= drawing.SHEET_INNER_BORDER[2]
    assert "_isometric_clears_boss_dia(iso)" in _source()


def test_bore_finish_lands_lower_right_clear_of_the_cutting_line() -> None:
    # Eye pass of w15-3d3a9d762: dropped straight to the bore's bottom, the
    # finish leader started on the A-A cutting-plane line (x = FRONT_CENTER).
    import math

    import _drawing_leaders as leaders

    cx, cy = drawing.FRONT_CENTER
    r = spec.BORE_DIA * drawing.VIEW_SCALE[0] / 2000.0
    ax, ay = drawing.FINISH_ATTACH
    assert math.hypot(ax - cx, ay - cy) == pytest.approx(r)
    assert ax > cx and ay < cy
    reach = drawing.HALF_OD + 0.005  # the cutting line runs past the tips
    chain = [((cx, cy - reach), (cx, cy + reach))]
    arrows = [((cx, cy + side * reach), (cx + 0.012, cy + side * reach)) for side in (-1, 1)]
    old = [((cx + drawing.HALF_OD - 0.006, cy - 0.055), (cx, cy - r))]
    new = [(drawing.FINISH_SYMBOL, drawing.FINISH_ATTACH)]
    fit = [(drawing.BORE_FIT_NOTE, drawing.BORE_FIT_ATTACH)]
    assert leaders.leader_crossings({"old": old, "section": chain + arrows})
    leaders.assert_leaders_clear(
        {"BoreFinish": new, "BoreFit": fit, "SectionLine": chain + arrows},
        centre=(cx, cy),
        keep_out={},
        lands_within={
            "BoreFinish": drawing.BORE_LANDING,
            "BoreFit": drawing.BORE_LANDING,
            "SectionLine": drawing.SECTION_LINE_LANDING,
        },
        label="pinion end view layout",
    )
    # The symbol stays off the teeth and left of the section view.
    sx, sy = drawing.FINISH_SYMBOL
    assert math.hypot(sx - cx, sy - cy) > drawing.HALF_OD + 0.005
    assert sx + 0.015 < drawing._side_x(0.0)
    assert "_bore_leaders_clear_section_line(adapter, front, bore_fit, finish)" in _source()


def test_the_bore_fit_is_the_only_three_place_dimension() -> None:
    # Policy rule 2: the places a dimension prints select its band. Only the
    # fit over the crankshaft needs three, and the native Right-plane
    # dimension carrying it is the one the sheet keeps.
    assert "BoreDia" in spec.DRAWING_DIMENSIONS["BossProfile"]
    assert [
        name
        for name, places in spec.DRAWING_PRECISION_BY_NAME.items()
        if places > 2
    ] == ["BoreDia"]


def test_bore_band_is_derived_from_its_fit_class_not_written_by_hand() -> None:
    # A slip fit exists only if the size limits on BOTH mating features are
    # narrower than the clearance band they claim, so the bore's limits are
    # computed from the named fit class and the shaft's own published limits.
    # Move either input and the bore must move with it -- that is what this
    # pins, not the literal pair of numbers.
    low, high = _config.fit("shaft_in_bushing")["diametral_clearance_mm"]
    assert spec.BORE_DIAMETRAL_CLEARANCE == pytest.approx((low, high))
    shaft_upper, shaft_lower = dt_crankshaft_spec.PINION_SEAT_DIA_BAND
    assert spec.BORE_DIA == dt_crankshaft_spec.PINION_SEAT_DIA
    assert spec.BORE_DIA_BAND == (
        pytest.approx(shaft_lower + high),
        pytest.approx(shaft_upper + low),
    )
    bore_upper, bore_lower = spec.BORE_DIA_BAND
    minimum = bore_lower - shaft_upper
    maximum = bore_upper - shaft_lower
    assert (minimum, maximum) == (pytest.approx(low), pytest.approx(high))


def test_tip_diameter_band_is_carried_by_the_fixed_centre_mesh() -> None:
    # Each retained manufactured tip belongs to a named actual 3D corner.
    import crank_mesh_stack as mesh
    import crank_mesh_geometry as geometry

    assert spec.OUTSIDE_DIA_TOLERANCE_MM == 0.10
    assert spec.DRAWING_PRECISION_BY_NAME["OutsideDia"] == 2
    assert "OutsideDia" in spec.DRAWING_DIMENSIONS["BossProfile"]
    normal_module = _config.machine("gear_train", "crank_drive_normal_module_mm")
    assert spec.TIP_CLEARANCE_MM == pytest.approx(
        (spec.DEDENDUM_FACTOR - 1.0) * normal_module
    )
    # The face width is the one free length: one place, so the title block's
    # .X grade is the band it claims, and nothing contradicts it.
    assert spec.DRAWING_PRECISION["GearBlank"]["FaceWidth"] == 1
    payload = mesh.require_qualified()
    assert geometry.required_calibration_case_names() <= payload["cases"].keys()
    assert all(case["tight_backlash_lower_mm"] > 0.0 for case in payload["cases"].values())


def test_callouts_add_only_what_the_number_cannot_carry() -> None:
    # The native bore limits govern. The fit pointer identifies the mate,
    # publishes its shaft limits and states the resulting clearance, so the
    # shop can verify that both statements are the same acceptance criterion.
    low, high = spec.BORE_DIAMETRAL_CLEARANCE
    shaft_upper, shaft_lower = dt_crankshaft_spec.PINION_SEAT_DIA_BAND
    assert drawing.DIMENSION_CALLOUTS == {
        "BoreDia": spec.BORE_PROCESS_CALLOUT,
    }
    assert spec.BORE_PROCESS_CALLOUT == "REAM THRU"
    assert spec.BORE_FIT_CALLOUT == "\n".join(
        (
            "BORE LIMITS GOVERN",
            f"MATE SHAFT {spec.CRANKSHAFT_NUMBER}",
            f"(\N{DIAMETER SIGN}{dt_crankshaft_spec.PINION_SEAT_DIA:.3f} "
            f"+{shaft_upper:.3f}/{shaft_lower:.3f})",
            f"(DIA CLR {low:.3f}-{high:.3f} mm)",
        )
    )


def test_print_carries_no_gdt_or_basic_dimensions() -> None:
    # Rules 3-4: a removable stock pinion clamped to its crankshaft is not on
    # the GD&T allowlist, so no datum, frame or basic dimension survives. The
    # ONE roughness it keeps is rule 5's exception -- the bore is a
    # size-toleranced fit, and a fit depends on the peaks as well as the size.
    source = _source()
    for helper in (
        "add_datum_feature(",
        "add_feature_control_frame(",
        "set_basic_dimension(",
        "project_part_pmi(",
    ):
        assert helper not in source, helper
    assert not hasattr(spec, "GEOMETRIC_TOLERANCES_MM")
    assert not hasattr(spec, "GEOMETRIC_CONTROLS")
    assert [control.key for control in spec.SURFACE_FINISHES] == ["crank_pinion_bore"]
    assert spec.SURFACE_FINISHES[0].face.diameter_mm == spec.BORE_DIA
    assert "surface_finishes=SURFACE_FINISHES" in _build_source()


def test_tooth_system_and_pair_acceptance_match_current_geometry() -> None:
    profile = spec.STOCK_PROFILE
    assert part.STOCK_PROFILE is profile
    assert spec.PITCH_DIA == pytest.approx(2.0 * profile.pitch_radius_mm)
    normal_module = _config.machine("gear_train", "crank_drive_normal_module_mm")
    assert spec.MODULE_MM == normal_module
    assert spec.DIAMETRAL_PITCH == pytest.approx(spec.MM_PER_IN / normal_module)
    assert spec.PRESSURE_ANGLE_DEG == _config.machine(
        "gear_train", "crank_drive_pressure_angle_deg"
    )
    assert profile.radial_translation_mm == pytest.approx(
        profile.pitch_radius_mm - profile.template.pitch_radius_mm
    )
    assert spec.DEDENDUM_FACTOR == 1.25
    assert spec.WHOLE_DEPTH == pytest.approx(
        profile.blank_radius_mm - profile.root_radius_min_mm
    )
    assert spec.ROOT_DIA == spec.ROOT_DIA_MIN
    assert spec.ROOT_DIA_MIN == pytest.approx(2.0 * profile.root_radius_min_mm)
    assert spec.ROOT_DIA_MAX == pytest.approx(2.0 * profile.root_radius_max_mm)
    assert spec.ROOT_DIA_MIN < spec.ROOT_DIA_MAX
    assert spec.TRANSVERSE_CIRCULAR_TOOTH_THICKNESS == pytest.approx(
        profile.pitch_tooth_thickness_mm
    )
    assert spec.TOOL_PLUNGE_MM == pytest.approx(profile.plunge_mm)
    assert spec.CUTTER_NUMBER == profile.template.cutter_number != mate.CUTTER_NUMBER
    assert spec.CUTTER_TEETH_RANGE == profile.template.teeth_range
    assert profile.template.reference_teeth == spec.CUTTER_TEETH_RANGE[0] < spec.TEETH
    assert spec.CUTTER_TEETH_RANGE[0] <= spec.TEETH <= spec.CUTTER_TEETH_RANGE[1]
    data = dict(line.partition(":")[::2] for line in notes.GEAR_DATA.splitlines()[1:])
    assert "NORMAL = TRANSVERSE" in notes.GEAR_DATA
    assert f"#{spec.CUTTER_NUMBER}" in data["FORM CUTTER"]
    assert f"{profile.template.reference_teeth}T REFERENCE" in data["FORM CUTTER"]
    assert "FINITE STOCK" in data["TOOTH FORM"]
    span_row = next(line for line in notes.GEAR_DATA.splitlines() if "BASE TANGENT SPAN" in line)
    assert "ACCEPT ON THIS PART" in span_row and "REF" not in span_row
    lower, upper = spec.BASE_TANGENT_SPAN_LIMITS_MM
    assert f"{lower:.{spec.BASE_TANGENT_SPAN_PLACES}f} TO {upper:.{spec.BASE_TANGENT_SPAN_PLACES}f}" in span_row
    width_row = next(line for line in notes.GEAR_DATA.splitlines() if "CIRCULAR PITCH THICKNESS" in line)
    assert "REF" in width_row and "ACCEPT" not in width_row
    for obsolete in ("NONSTANDARD", "SAME CUTTER", "LONG ADDENDUM", "CONTACT RATIO"):
        assert obsolete not in notes.GEAR_DATA


def test_notes_carry_the_tooth_edge_override_not_an_obsolete_boss_shortfall() -> None:
    lines = spec.DRAWING_NOTES.split("\n")
    assert spec.TOOTH_EDGE_NOTE in lines
    assert spec.BOSS_WALL_WORST >= 2.0
    assert not any(line.startswith("BOSS WALL") for line in lines)
    # The T120 fit-up may turn the band down; the sheet states its floor.
    assert any(
        "TURNED BAND" in line and f"Ø{spec.TURNED_DIA_FITUP_MIN:.2f} MIN" in line
        for line in lines
    )
    assert len(lines) <= 4
    assert not hasattr(spec, "BOSS_WALL_EXCEPTION")
    for internal in ("EXCEPTION", "ACCEPTED", "RULING", "POLICY", "RULE "):
        assert internal not in spec.DRAWING_NOTES
    policy = (
        Path(spec.__file__).parents[1] / "docs" / "drawing-simplicity-policy.md"
    ).read_text(encoding="utf-8")
    assert not any(
        line.startswith("| MHA-DT-010 crank pinion boss |")
        for line in policy.splitlines()
    )
    notes = spec.DRAWING_NOTES
    assert spec.PIN_NUMBER not in notes
    assert "LIGHT DRIVE FIT" not in notes
    assert "FLUSH" not in notes
    assert "SUBSTITUTE" not in notes
    # Retired with the migration: generic method narration, heat-treatment
    # negatives, duplicate bore-fit text and pair commissioning protocol.
    for banned in (
        "CUT TEETH",
        "BORE BEFORE",
        "HARDNESS",
        "DIAMETRAL CLEARANCE",
        "ROOT DIAMETER",
        "COMMISSIONING",
        "ACCEPTANCE",
        "MHA-DT-007",
        "N*m",
        "RPM",
        "+/-",
    ):
        assert banned not in notes, banned


def test_sheet_runs_at_3_to_1_with_every_view_at_sheet_scale() -> None:
    # One scale for every view means the title block's SCALE field is the
    # whole truth and no view needs a scale note. The 24.4-mm boss-ended
    # blank must still clear its section dimensions and neighbouring views.
    assert drawing.SHEET_SCALE == (3.0, 1.0)
    assert drawing.VIEW_SCALE == (3, 1)
    assert drawing.SHEET_SCALE[0] == drawing.VIEW_SCALE[0]
    assert _source().count("scale=VIEW_SCALE") == 3
    assert not hasattr(spec, "ISOMETRIC_VIEW_NOTE")




def test_dimension_text_lands_clear_of_the_views_and_the_title_block() -> None:
    # Offline layout guard: every dimension is extended OUT of the silhouette
    # it measures, and nothing crosses into the title block's bottom-right
    # corner of the B sheet.
    half_od = drawing.HALF_OD
    assert half_od == pytest.approx(spec.OUTSIDE_DIA * drawing.VIEW_SCALE[0] / 2000.0)
    assert drawing.FRONT_KEEP == {}
    half_boss = drawing.HALF_BOSS
    assert half_boss == pytest.approx(spec.BOSS_DIA * drawing.VIEW_SCALE[0] / 2000.0)
    outside_x, outside_y = drawing.RIGHT_KEEP["OutsideDia"]
    assert min(drawing._side_x(0.0), drawing._side_x(spec.FACE_WIDTH)) < outside_x
    assert outside_x < max(drawing._side_x(0.0), drawing._side_x(spec.FACE_WIDTH))
    assert outside_y > drawing.RIGHT_CENTER[1] + half_od + 0.008
    boss_x, boss_y = drawing.RIGHT_KEEP["BossDia"]
    assert drawing._side_x(spec.OVERALL_LENGTH) < boss_x
    assert boss_x < drawing.ISO_CENTER[0] - half_od - 0.010
    assert boss_y == pytest.approx(drawing.RIGHT_CENTER[1])
    # The bore diameter stands off the toothed face, clear of the end view, with
    # its text above the section: right of the boss its extension lines ran
    # the bore's full length and fenced the pin-hole leader out of the hole.
    bore_x, bore_y = drawing.RIGHT_KEEP["BoreDia"]
    assert drawing.FRONT_CENTER[0] + half_od < bore_x < drawing._side_x(0.0)
    assert bore_y > outside_y + 0.010
    for name in ("ShoulderLength", "FaceWidth", "OverallLength"):
        assert drawing.RIGHT_KEEP[name][1] < drawing.RIGHT_CENTER[1] - half_od, name
    # Baseline-stacked from the south face, shortest innermost.
    assert (
        drawing.RIGHT_KEEP["ShoulderLength"][1]
        > drawing.RIGHT_KEEP["FaceWidth"][1]
        > drawing.RIGHT_KEEP["OverallLength"][1]
    )
    # The turned diameter reads above its band, clear of the tip diameter.
    turned_x, turned_y = drawing.RIGHT_KEEP["TurnedDia"]
    assert drawing._side_x(spec.SHOULDER_LENGTH) < turned_x < drawing._side_x(spec.FACE_WIDTH)
    assert turned_y > outside_y + 0.010
    # The pin-hole note hangs above-right of the section. Its leader reaches
    # the sectioned cross-hole through the boss instead of crossing its own
    # text, the toothed rectangle, or the outside-diameter extension line.
    assert drawing.PIN_HOLE_CALLOUT[1] > drawing.RIGHT_CENTER[1] + half_od + 0.040
    assert abs(drawing.PIN_HOLE_EDGE[1] - drawing.RIGHT_CENTER[1]) == pytest.approx(
        spec.PIN_DIA * drawing.VIEW_SCALE[0] / 2000.0
    )
    assert drawing.PIN_HOLE_EDGE[0] == pytest.approx(drawing._side_x(spec.PIN_STATION))
    assert drawing.PIN_HOLE_EDGE[0] < drawing.PIN_HOLE_CALLOUT[0]
    assert drawing.PIN_HOLE_CALLOUT[0] < drawing.ISO_CENTER[0] - half_od - 0.010
    # The bore-fit note stays left of the end view; its short pointer enters
    # radially through the upper-left tooth gap and lands on the bore circle.
    assert drawing.BORE_FIT_NOTE[0] < drawing.FRONT_CENTER[0] - half_od
    bore_dx = drawing.BORE_FIT_ATTACH[0] - drawing.FRONT_CENTER[0]
    bore_dy = drawing.BORE_FIT_ATTACH[1] - drawing.FRONT_CENTER[1]
    assert math.hypot(bore_dx, bore_dy) == pytest.approx(
        spec.BORE_DIA * drawing.VIEW_SCALE[0] / 2000.0
    )
    assert bore_dx < 0 < bore_dy
    positions = (
        *drawing.FRONT_KEEP.values(),
        *drawing.RIGHT_KEEP.values(),
        drawing.PIN_HOLE_CALLOUT,
        drawing.BORE_FIT_NOTE,
        (0.016, 0.258),  # gear-data note anchor
        (0.016, 0.082),  # manufacturing-notes anchor
    )
    for x, y in positions:
        assert 0.012 < x < 0.420
        assert 0.012 < y < 0.267
        assert not (x > 0.216 and y < 0.070), (x, y)  # title-block keep-out
    # The three views march left to right without overlapping: face view,
    # longitudinal section (half the overall length each side), isometric.
    half_len = spec.OVERALL_LENGTH * drawing.VIEW_SCALE[0] / 2000.0
    assert (
        drawing.FRONT_CENTER[0] + half_od < drawing.RIGHT_CENTER[0] - half_len - 0.010
    )
    assert drawing.RIGHT_CENTER[0] + half_len < drawing.ISO_CENTER[0] - half_od - 0.010


def test_part_stamps_make_critical_properties() -> None:
    build = _build_source()
    assert "apply_drawing_properties" in build
    assert "clear_dimensions_for_drawing" in build
    import _config

    config = _config.parts("dt-crank-pinion")
    material = "SAE 1018 CF bar, ASTM A108-24"
    assert config["material"] == material
    assert config["material_specification"] == material
    # The FINISH field states the surface condition only: how the teeth are
    # made is the PROCESS row's job, and saying it twice is the
    # over-specification rule 4 bans (codex machinist review, 2026-09-20).
    assert config["finish"] == "oiled"
    assert not any(
        word in config["finish"].lower() for word in ("cut", "hob", "shaper", "machin")
    )
    assert "gear cutting" in config["process"]
    assert int(config["quantity"]) == 1


def test_w15_boss_hides_the_shaft_end_and_walls_the_pin_at_every_limit() -> None:
    # The photo asks for the shortest printable boss, but neither the
    # match-drilled pin nor the existing W15 print-worst floors may change.
    import build_dt_drive_train_assembly as bdt

    printed = float(str(_config.title_block("linear_1pl")["display"]).lstrip("±"))
    assert spec.OVERALL_LENGTH_GRADE_MM == pytest.approx(printed)
    assert spec.DRAWING_PRECISION["BossProfile"]["OverallLength"] == spec.OVERALL_LENGTH_PLACES
    assert spec.DRAWING_PRECISION["GearBlank"]["FaceWidth"] == spec.FACE_WIDTH_PLACES
    # Both lengths print exactly, so no rounded nominal eats the margin.
    assert spec.OVERALL_LENGTH == round(spec.OVERALL_LENGTH, spec.OVERALL_LENGTH_PLACES)
    assert spec.SHAFT_END_RECESS_MIN <= bdt.PINION_RECESS_NOMINAL <= spec.SHAFT_END_RECESS_MAX
    assert sum(bdt.PINION_PIN_EDGE_STACK.values()) >= spec.PIN_EDGE_MIN_WORST
    assert dt_crankshaft_spec._SHORTER_PIN_EDGE_WORST < spec.PIN_EDGE_MIN_WORST
    assert spec.PIN_AXIAL_LIGAMENT_WORST >= spec.PIN_AXIAL_LIGAMENT_FLOOR_MM
    # The seat feeler is directly against the restored boss north face.
    assert spec.SEAT_FEELER_MM == pytest.approx(0.25)
    concentric = bdt.PINION_T120_CONCENTRIC
    assert concentric["shoulder air"] >= bdt.T120_PINION_AIR_FLOOR
    assert concentric["turned band radial"] >= bdt.T120_TURNED_BAND_RADIAL_FLOOR
    assert bdt.CRANK_ROW_ENGAGEMENT_FRACTION_WORST >= bdt.ROW_ENGAGEMENT_MIN
    assert sum(bdt.PINION_RECESS_STACK.values()) >= spec.SHAFT_END_RECESS_MIN_WORST
    # The unfaced recess cannot be justified by a former inch stock grade.
    # Carry the actual printed allowance and the current shaft/pinion sizes.
    edge_recess = spec.SHAFT_END_RECESS_MIN_WORST + spec.OVERALL_LENGTH_GRADE_MM
    under = bdt.pinion_recess_stack(
        edge_recess - spec.printed_band_mm(spec.OVERALL_LENGTH_PLACES),
        dt_crankshaft_spec.SHAFT_LENGTH,
        spec.OVERALL_LENGTH,
    )
    assert sum(under.values()) < spec.SHAFT_END_RECESS_MIN_WORST


def test_root_diameter_boss_meets_the_current_printed_wall_target() -> None:
    # Retain option C's root-circle boss and native bore band. Standard full
    # depth now supplies the wall target without a thin-wall exception.
    _, bore_upper = spec.deviations(spec.BORE_DIA_BAND)
    printed_boss = round(spec.BOSS_DIA, spec.BOSS_DIA_PLACES)
    row = spec.printed_band_mm(spec.BOSS_DIA_PLACES)
    worst = (printed_boss - row - (spec.BORE_DIA + bore_upper)) / 2.0
    assert spec.BOSS_DIA == pytest.approx(spec.ROOT_DIA)
    assert spec.BOSS_WALL_WORST == pytest.approx(worst)
    assert worst >= 2.0 > spec.BOSS_WALL_FLOOR_MM
    assert spec.DRAWING_PRECISION["BossProfile"]["BossDia"] == spec.BOSS_DIA_PLACES



def _cylinder(radius_mm: float, z_low: float, z_high: float):
    from _part_pmi import _SURFACE_CYLINDER, _FaceGeometry

    return _FaceGeometry(
        face=None,
        identity=_SURFACE_CYLINDER,
        parameters=(0.0, 0.0, 0.0, 0.0, 0.0, -1.0, radius_mm / 1000.0),
        outward_normal=None,
        box=(-0.009, -0.009, z_low / 1000.0, 0.009, 0.009, z_high / 1000.0),
    )


def test_boss_gate_face_is_the_outboard_stub_not_a_gap_floor() -> None:
    """The runtime boss gate's decision: the relieved gap floors share the
    boss radius over the teeth only, so a pinion whose boss dropped (diag v3,
    d6ca08eb7) has no face the gate accepts; an intact one has exactly one."""
    from _part_pmi import _face_matches

    radius = spec.BOSS_DIA / 2.0
    gap_floors = [_cylinder(radius, 0.0, spec.FACE_WIDTH) for _ in range(spec.TEETH)]
    boss = _cylinder(radius, spec.FACE_WIDTH, spec.OVERALL_LENGTH)
    bore = _cylinder(spec.BORE_DIA / 2.0, 0.0, spec.OVERALL_LENGTH)

    def accepted(faces):
        return [face for face in faces if _face_matches(face, part.BOSS_GATE_FACE)]

    assert accepted([*gap_floors, bore, boss]) == [boss]
    assert accepted([*gap_floors, bore]) == []
    # A boss short of the gate station, or off-size by more than 1 um, fails.
    assert accepted([_cylinder(radius, spec.FACE_WIDTH, spec.FACE_WIDTH + 1.0)]) == []
    assert accepted([_cylinder(radius + 0.001, spec.FACE_WIDTH, spec.OVERALL_LENGTH)]) == []
    assert part.BOSS_GATE_TOL_MM == 0.001
    assert spec.FACE_WIDTH < part.BOSS_GATE_FACE.contains_z_mm < spec.OVERALL_LENGTH


class _Surface:
    Identity = 4002  # swSurfaceTypes_e.CYLINDER_TYPE

    def __init__(self, radius_mm: float) -> None:
        self.CylinderParams = (0.0, 0.0, 0.0, 0.0, 0.0, -1.0, radius_mm / 1000.0)


class _Face:
    def __init__(self, radius_mm: float, z_low: float, z_high: float) -> None:
        self.surface = _Surface(radius_mm)
        self.box = (-0.009, -0.009, z_low / 1000.0, 0.009, 0.009, z_high / 1000.0)
        self.next: _Face | None = None

    def GetSurface(self) -> _Surface:
        return self.surface

    def GetBox(self) -> tuple[float, ...]:
        return self.box

    def GetNextFace(self) -> _Face | None:
        return self.next


class _Body:
    def __init__(self, z_high: float, faces: list[_Face]) -> None:
        self.z_high = z_high
        for face, following in zip(faces, [*faces[1:], None]):
            face.next = following
        self.first = faces[0] if faces else None

    def GetExtremePoint(self, _x: float, _y: float, z: float):
        return (True, 0.0, 0.0, self.z_high / 1000.0 if z > 0.0 else 0.0)

    def GetFirstFace(self) -> _Face | None:
        return self.first


class _Seat:
    def __init__(self, body: _Body) -> None:
        self.body = body
        self.currentModel = self

    def GetBodies2(self, _kind: int, _visible_only: bool) -> list[_Body]:
        return [self.body]

    def _attempt(self, operation, default=None):
        return operation()


@pytest.fixture
def _plain_binding(monkeypatch):
    import _common
    import _part_pmi

    for module in (_common, _part_pmi):
        monkeypatch.setattr(module, "_early_bound", lambda obj, _interface: obj)


def _pinion(z_high: float, *, boss: bool) -> _Seat:
    radius = spec.BOSS_DIA / 2.0
    faces = [_Face(radius, 0.0, spec.FACE_WIDTH) for _ in range(spec.TEETH)]
    faces.append(_Face(spec.BORE_DIA / 2.0, 0.0, z_high))
    if boss:
        faces.append(_Face(radius, spec.FACE_WIDTH - 0.05, z_high))
    return _Seat(_Body(z_high, faces))


def test_boss_gate_passes_an_intact_pinion(_plain_binding) -> None:
    asyncio.run(part.assert_boss_present(_pinion(spec.OVERALL_LENGTH, boss=True), "intact"))


def test_boss_gate_fails_loud_on_the_silent_drop_diag_v3_saw(_plain_binding) -> None:
    # d6ca08eb7 s0: after a ForceRebuild3 that reported success, with What's
    # Wrong silent about the boss, the solid ended at the tooth face.
    dropped = _pinion(spec.FACE_WIDTH, boss=False)
    with pytest.raises(RuntimeError, match="overall length: z-extent"):
        asyncio.run(part.assert_boss_present(dropped, "dropped"))


def test_boss_gate_wants_the_boss_cylinder_not_just_the_length(_plain_binding) -> None:
    boss_less = _pinion(spec.OVERALL_LENGTH, boss=False)
    with pytest.raises(RuntimeError, match="hub boss: face spec"):
        asyncio.run(part.assert_boss_present(boss_less, "boss-less"))


def test_turned_band_clears_t120_and_each_negative_control_flips() -> None:
    # Printed end-play and cone-float corners retain each current floor.
    # A missing shoulder section cannot be made present by length alone;
    # negative controls must first reach a real T120 section.
    import build_dt_drive_train_assembly as bdt

    def nominal_axes(**geometry) -> dict[str, float]:
        return bdt.pinion_t120_clearances(pose_radial=0.0, pose_axial=0.0, **geometry)

    clear = nominal_axes()
    assert clear == bdt.PINION_T120_CONCENTRIC
    assert clear["shoulder air"] >= bdt.T120_PINION_AIR_FLOOR
    assert clear["turned band radial"] >= bdt.T120_TURNED_BAND_RADIAL_FLOOR
    # Supported carrying row is independently certified by actual stock 3D.
    assert bdt.CRANK_ROW_ENGAGEMENT_FRACTION_WORST >= bdt.ROW_ENGAGEMENT_MIN
    # Increasing the turned radius consumes the measured radial margin.
    oversize = nominal_axes(
        turned_dia=spec.TURNED_DIA
        + 2.0 * (clear["turned band radial"] - bdt.T120_TURNED_BAND_RADIAL_FLOOR + 0.01)
    )
    assert oversize["turned band radial"] < bdt.T120_TURNED_BAND_RADIAL_FLOOR
    longer = nominal_axes(shoulder_length=spec.FACE_WIDTH)
    no_band = nominal_axes(shoulder_length=None)
    if clear["shoulder air"] == math.inf:
        assert longer["shoulder air"] == no_band["shoulder air"] == math.inf
    else:
        assert longer["shoulder air"] <= clear["shoulder air"]
        assert no_band["shoulder air"] <= longer["shoulder air"]
    # Enclose actual south-face rim points at every printed corner, then
    # consume the resulting finite axial air. This is a real section-domain
    # negative control, not a fictitious length transition through infinity.
    shifts, heights = bdt._cone_corners(bdt._CONE_FLOATS, bdt._CRANK_HEIGHT_BAND)
    section_reach = max(
        math.hypot(
            bdt.cone_station(bdt._T120_SOUTH_FACE_STATION + shift)[0] - bdt.X_CRANK,
            bdt.Y_DRIVE - (bdt.Y_CRANK + height),
        )
        for shift, height in zip(shifts, heights, strict=True)
    ) + bdt._TIP120
    closing_radial_pose = (
        section_reach - bdt._PINION_TIP_R_MAX + bdt.T120_PINION_AIR_FLOOR
    )
    reached = bdt.pinion_t120_clearances(
        pose_radial=closing_radial_pose, pose_axial=0.0
    )
    assert math.isfinite(reached["shoulder air"])
    closed = bdt.pinion_t120_clearances(
        pose_radial=closing_radial_pose,
        pose_axial=max(reached["shoulder air"], 0.0),
    )
    assert closed["shoulder air"] < bdt.T120_PINION_AIR_FLOOR


def test_actual_64t_rows_are_frozen_exact_qualified_physical_cases() -> None:
    from dataclasses import FrozenInstanceError

    import crank_mesh_stack as mesh
    import crank_mesh_requirements as requirements

    payload = mesh.require_qualified()
    import build_dt_drive_train_assembly as bdt

    assert bdt.CRANK_MESH_QUALIFICATION is payload
    assert set(bdt.CRANK_ROW_QUALIFICATIONS) == set(payload["cases"])
    assert bdt.CRANK_ROW_QUALIFICATIONS["nominal"] == mesh.row_qualification("nominal")
    for name, case in payload["cases"].items():
        row = bdt.CRANK_ROW_QUALIFICATIONS[name]
        assert isinstance(row, mesh.RowQualification)
        assert row.case_name == name
        pose = case["placement"]
        for field in ("driver_face_mm", "driven_face_mm", "driver_origin_mm", "driven_origin_mm"):
            assert getattr(row, field) == tuple(pose[field])
        for field in ("driver_frame", "driven_frame"):
            assert getattr(row, field) == tuple(tuple(axis) for axis in pose[field])
        assert row.driver_shoulder_z_mm == pose["driver_shoulder_z_mm"]
        assert row.driver_turned_radius_mm == pose["driver_turned_radius_mm"]
        assert row.supported_driven_station_intervals_mm == tuple(
            tuple(interval) for interval in case["row_available_intervals_mm"]
        )
        assert row.row_fraction_lower == case["row_available_fraction_lower"]
        assert row.row_fraction_lower >= requirements.ROW_ENGAGEMENT_MIN
        assert row.coverage_lower == case["stock_form_coverage_lower"]
        assert row.coverage_lower >= requirements.STOCK_FORM_COVERAGE_MIN
        assert row.continuous_carrier
        with pytest.raises(FrozenInstanceError):
            row.row_fraction_lower = 1.0
    worst = min(row.row_fraction_lower for row in bdt.CRANK_ROW_QUALIFICATIONS.values())
    assert bdt.CRANK_ROW_ENGAGEMENT_FRACTION_WORST == worst == mesh.ROW_ENGAGEMENT_FRACTION_WORST


def test_actual_64t_row_corners_retain_short_faces_and_fitup_band() -> None:
    import crank_mesh_geometry as geometry
    import crank_mesh_stack as mesh

    payload = mesh.require_qualified()
    assert geometry.required_calibration_case_names() <= payload["cases"].keys()
    opened = mesh.row_qualification("booked_open")
    fitup = mesh.row_qualification("turned_fitup_floor")
    assert opened.driver_face_mm[1] - opened.driver_face_mm[0] == pytest.approx(
        spec.FACE_WIDTH + min(spec.FACE_WIDTH_BAND)
    )
    assert opened.driver_shoulder_z_mm == pytest.approx(
        spec.SHOULDER_LENGTH + min(spec.SHOULDER_LENGTH_BAND)
    )
    assert opened.driver_turned_radius_mm == pytest.approx(
        (spec.TURNED_DIA - spec.TURNED_DIA_TOLERANCE_MM) / 2.0
    )
    assert fitup.driver_turned_radius_mm == spec.TURNED_DIA_FITUP_MIN / 2.0
    assert opened.driven_face_mm[1] - opened.driven_face_mm[0] == pytest.approx(
        mate.FACE_WIDTH + max(mate.FACE_WIDTH_BAND)
    )
    assert payload["geometry_sha256"] == mesh.geometry_sha256()


@pytest.fixture(scope="module")
def bounded_crank_contract_payload() -> dict:
    """Synthetic receiver evidence, never an engineering/native certificate.

    Exact source profiles, manufactured corners and full world placements
    are real inputs. Positive bounded contact observations are deliberately
    synthetic so refusal/mutation logic remains executable while the actual
    engineering study is refused. No production module imports this fixture.
    """
    import hashlib
    import json

    import crank_mesh_geometry as geometry
    import crank_mesh_stack as mesh

    def profile_record(profile) -> dict:
        return {
            "teeth": profile.teeth,
            "reference_teeth": profile.template.reference_teeth,
            "dp": profile.template.diametral_pitch,
            "pa_deg": profile.template.pressure_angle_deg,
            "blank_radius_mm": profile.blank_radius_mm,
            "radial_translation_mm": profile.radial_translation_mm,
            "helix_angle_deg": profile.helix_angle_deg,
        }

    drivers = {"nominal": spec.STOCK_PROFILE, **dict(spec.STOCK_PROFILE_CORNERS)}
    driven = {"nominal": mate.STOCK_PROFILE, **dict(mate.STOCK_PROFILE_CORNERS)}
    placements = geometry.calibration_case_placements()
    domains = geometry.calibration_case_domains()
    pitch = 2.0 * math.pi / spec.TEETH
    surface_error = 0.001
    phase_error = surface_error / (spec.PITCH_DIA / 2.0)
    phase_motion = 0.0001
    root_air_lower = 0.02  # Synthetic positive bound, not a production root-air floor.
    low, high = -0.025, -0.005
    cases = {}
    for source in geometry.calibration_case_parameters():
        name = source["name"]
        pose = placements[name]
        domain = domains[name]
        p16 = drivers[source["driver_profile_label"]]
        p64 = driven[source["driven_profile_label"]]
        face_low, face_high = pose["driven_face_mm"]
        width = face_high - face_low
        intervals = [[face_low + 0.05 * width, face_high - 0.05 * width]]
        station = (face_low + face_high) / 2.0
        driver_z = sum(pose["driver_face_mm"]) / 2.0
        driver_radius = p16.pitch_radius_mm
        world_point = [
            pose["driver_origin_mm"][axis]
            + pose["driver_frame"][axis][0] * driver_radius
            + pose["driver_frame"][axis][2] * driver_z
            for axis in range(3)
        ]
        normal = [pose["driver_frame"][axis][0] for axis in range(3)]

        def contact(offset: float, tooth: int) -> dict:
            return {
                "phase_offset_rad": offset,
                "driven_tooth": tooth,
                "segment": "finite_flank",
                "kind": "flank",
                "parameter": 0.5,
                "station_mm": station,
                "world_point_mm": list(world_point),
                "driver_radius_mm": driver_radius,
                "driver_z_mm": driver_z,
                "driven_normal_world": [-value for value in normal],
                "driver_normal_world": list(normal),
                "opposed_normal_residual": 0.0,
                "common_normal_supported": True,
                "common_normal_error_bound": 1e-12,
                "driven_per_driver_velocity": -spec.TEETH / mate.TEETH,
            }

        rows = []
        for index in range(65):
            tooth = 0 if index < 32 else 1
            rows.append({
                "driver_phase_rad": index * pitch / 64.0,
                "lower_rad": low,
                "upper_rad": high,
                "error_rad": phase_error,
                "phase_error_rad": phase_motion / driver_radius,
                "surface_numerical_resolved": True,
                "surface_extrema_enclosures_rad": [{
                    "side": side,
                    "lower_rad": edge - phase_error / 2,
                    "upper_rad": edge,
                    "branches": [[tooth, edge - phase_error / 2, edge]],
                    "unwitnessed_branch_lower_rad": [],
                    "numerical_tolerance_rad": phase_error,
                    "relaxed_incumbent_rad": edge - phase_error / 2,
                    "achieved_residual_rad": 0.0,
                    "terminal_lower_rad": None,
                    "terminal_boxes": 0,
                    "branch_numerics": [{
                        "tooth": tooth,
                        "lower_rad": edge - phase_error / 2,
                        "relaxed_incumbent_rad": edge - phase_error / 2,
                        "achieved_residual_rad": 0.0,
                        "terminal_lower_rad": None,
                        "terminal_boxes": 0,
                    }],
                    "radial_pose_error_mm": domain["radial_error_mm"],
                    "axial_pose_error_mm": domain["axial_error_mm"],
                } for side, edge in (("lower", -low), ("upper", high))],
                "root_free_intervals_rad": [[-pitch / 2.0, pitch / 2.0]],
                "free_intervals_rad": [[
                    low + phase_error + phase_motion / driver_radius,
                    high - phase_error - phase_motion / driver_radius,
                ]],
                "root_sweep": {
                    "free_inner": [[-pitch / 2.0, pitch / 2.0]],
                    "free_outer": [[-pitch / 2.0, pitch / 2.0]],
                    "offset_domain_rad": [-pitch / 2.0, pitch / 2.0],
                    # Matching inner/outer sets have no angular set uncertainty.
                    "angular_uncertainty_rad": 0.0,
                    "driver_pitch_displacement_uncertainty_mm": 0.0,
                    "geometric_uncertainty_mm": surface_error,
                    "radial_error_mm": domain["radial_error_mm"],
                    "axial_error_mm": domain["axial_error_mm"],
                    "required_root_air_mm": domain["required_root_air_mm"],
                    "root_air_lower_bound_mm": root_air_lower,
                    "root_max_radial_clearance_screen_mm": None,
                    "witnesses": [],
                    "enclosure_uncertainty": [],
                    "uncertain_boxes": 0,
                    "boxes": 1,
                    "status": "resolved",
                    "containment_proof": "synthetic complete outer-solid enclosure",
                    "reason": "",
                    "root_is_carrying": False,
                    "native_solid_certificate": False,
                },
                "lower_contact": contact(low, tooth),
                "upper_contact": contact(high, tooth),
                "branch_intervals": [[tooth, low, high]],
                "boxes": 1,
                "root_contact": False,
                # Covers half the uniform phase cell, within the branch window.
                "branch_phase_reserves_rad": [[tooth, 0.004]],
                "supported_branch_contacts": [{
                    "tooth": tooth,
                    "contacts": [
                        {"side": "lower", "contact": contact(low, tooth)},
                        {"side": "upper", "contact": contact(high, tooth)},
                    ],
                }],
                "row_intervals_mm": [list(interval) for interval in intervals],
            })
        cases[name] = {
            "case": name,
            "metric": "STOCK-FORM COVERAGE",
            "is_conjugate": False,
            "driver_profile": profile_record(p16),
            "driven_profile": profile_record(p64),
            "placement": pose,
            "pose_domain": domain,
            "phase_rows": rows,
            "phase_components_rad": [[
                low + phase_error + phase_motion / driver_radius,
                high - phase_error - phase_motion / driver_radius,
            ]],
            "phase_window_rad": [low + 2.0 * phase_error, high - 2.0 * phase_error],
            "phase_seed_rad": (low + high) / 2.0,
            "stock_form_coverage_lower": 1.0,
            "coverage_definition": "synthetic bounded supported branch union / physical pitch",
            "continuous_carrying_contact": True,
            "uncovered_phase_rad": 0.0,
            "phase_reserve_rad": 0.001,
            "noncarrying_pair_normal_gap_upper_mm": 0.002,
            "handovers": [{
                "continuous": True,
                "side": side,
                "phase_rad": 31.5 * pitch / 64.0,
                "phase_bracket_rad": [31.0 * pitch / 64.0, 32.0 * pitch / 64.0],
                "pair": [0, 1],
                "pitch_displacement_jump_upper_mm": 0.003,
                "contact": contact(offset, 1),
            } for side, offset in (("lower", low), ("upper", high))],
            "row_available_fraction_lower": 0.89,
            "row_available_intervals_mm": intervals,
            "qualified": True,
            "tight_backlash_lower_mm": (high - low - 2.0 * phase_error) * driver_radius - 2.0 * phase_motion,
            "loose_backlash_upper_mm": (high - low + 2.0 * phase_error) * driver_radius + 2.0 * phase_motion,
            "no_overlap_at_samples": True,
            "parametric_driven_mechanical_datum_te_rad": [
                -spec.TEETH / mate.TEETH * row["lower_rad"] for row in rows
            ],
            "parametric_actual_driver_phase_rad": [row["driver_phase_rad"] - low for row in rows],
            "numerical_error_bounds": {
                "surface_mm": surface_error,
                "phase_motion_mm": phase_motion,
                "root_surface_mm": surface_error,
                "geom_ball_mm": 0.0,
                "radial_mm": domain["radial_error_mm"],
                "axial_mm": domain["axial_error_mm"],
                "te_rad": (2.0 * surface_error + phase_motion) / driver_radius * spec.TEETH / mate.TEETH,
            },
            "native_certificate": False,
        }
    # Hash synthetic labels, NOT diagnostic files. These unit identities may
    # never be mistaken for an actual collector's deployed-source manifest.
    engine_sources = {
        name: hashlib.sha256(f"synthetic receiver fixture: {name}".encode()).hexdigest()
        for name in (
            "crank_mesh_backlash_study.py", "crossed_mesh_study.py",
            "stock_form_contact_3d.py", "stock_form_root_angles.py", "stock_form_root_sweep.py",
            "stock_form_contact_continuation.py",
        )
    }
    return {
        "qualified": True,
        "geometry_sha256": mesh.geometry_sha256(),
        "measurement_engine_sources_sha256": engine_sources,
        "measurement_engine_sha256": hashlib.sha256(
            json.dumps(engine_sources, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest(),
        "measurement_engine_provenance": "synthetic unit-fixture labels; not source bytes",
        "refusal": None,
        "cases": cases,
        "phase_window_rad": [-0.020, -0.010],
        "phase_seed_deg": math.degrees(-0.015),
    }


def _crank_case_mutation(payload: dict, case_name: str = "nominal") -> dict:
    """Copy only the mutated case; the full source family remains present."""
    from copy import deepcopy

    result = dict(payload, cases=dict(payload["cases"]))
    result["cases"][case_name] = deepcopy(payload["cases"][case_name])
    return result


@pytest.mark.parametrize("mutation", ["non_unit", "false_opposition"])
def test_crank_receiver_reconstructs_claimed_common_normal(mutation, bounded_crank_contract_payload) -> None:
    import crank_mesh_stack as mesh

    payload = _crank_case_mutation(bounded_crank_contract_payload)
    proof = payload["cases"]["nominal"]["phase_rows"][0]["lower_contact"]
    if mutation == "non_unit":
        proof["driven_normal_world"] = [2*value for value in proof["driven_normal_world"]]
    else:
        proof["driven_normal_world"] = list(proof["driver_normal_world"])
    with pytest.raises(ValueError, match="common-normal"):
        mesh.require_qualified(payload)


@pytest.mark.parametrize("mutation", [
    "missing", "unpaid_width", "dropped_pose", "duplicate_branch", "outside_tooth",
    "detached_branch_lower", "detached_side_incumbent",
])
def test_crank_receiver_refuses_unpaid_surface_enclosures(mutation, bounded_crank_contract_payload) -> None:
    import crank_mesh_stack as mesh

    payload = _crank_case_mutation(bounded_crank_contract_payload)
    row = payload["cases"]["nominal"]["phase_rows"][0]
    if mutation == "missing":
        del row["surface_extrema_enclosures_rad"]
    else:
        enclosure = row["surface_extrema_enclosures_rad"][0]
        if mutation == "unpaid_width":
            enclosure["lower_rad"] = enclosure["upper_rad"] - 2 * row["error_rad"]
        elif mutation == "dropped_pose":
            enclosure["radial_pose_error_mm"] = 0.0
        elif mutation == "duplicate_branch":
            enclosure["branches"].append(list(enclosure["branches"][0]))
        elif mutation == "detached_branch_lower":
            proof = enclosure["branch_numerics"][0]
            proof["lower_rad"] -= row["error_rad"]
            proof["relaxed_incumbent_rad"] = proof["lower_rad"]
        elif mutation == "detached_side_incumbent":
            enclosure["relaxed_incumbent_rad"] -= row["error_rad"]
        else:
            enclosure["branches"][0][0] = mate.TEETH
    with pytest.raises(ValueError):
        mesh.require_qualified(payload)


@pytest.mark.parametrize("mutation", ["reversed", "overlap", "inner_outside_outer", "partial_pitch"])
def test_crank_receiver_checks_unselected_root_components(mutation, bounded_crank_contract_payload) -> None:
    import crank_mesh_stack as mesh

    payload = _crank_case_mutation(bounded_crank_contract_payload)
    root = payload["cases"]["nominal"]["phase_rows"][0]["root_sweep"]
    half = math.pi / spec.TEETH
    if mutation == "reversed":
        root["free_outer"].append([half / 2, half / 4])
    elif mutation == "overlap":
        root["free_outer"].append([half / 4, half / 2])
    elif mutation == "inner_outside_outer":
        root["free_outer"] = [[-half, half / 2]]
    else:
        root["offset_domain_rad"] = [-half, half / 2]
    with pytest.raises(ValueError):
        mesh.require_qualified(payload)


def test_bounded_full_crank_payload_executes_row_factory(monkeypatch, bounded_crank_contract_payload) -> None:
    from dataclasses import FrozenInstanceError

    import crank_mesh_geometry as geometry
    import crank_mesh_stack as mesh

    payload = bounded_crank_contract_payload
    assert mesh.require_qualified(payload) is payload
    assert set(payload["cases"]) == geometry.required_calibration_case_names()
    monkeypatch.setattr(mesh, "CALIBRATION", payload)
    # The full family is validated above. Exercise the factory across each
    # physical case category without re-validating that family quadratically.
    names = (
        "nominal", "booked_closed", "booked_open", "centre_minus", "centre_plus",
        "turned_fitup_floor",
        next(name for name in payload["cases"] if name.startswith("profile_corner_")),
        next(name for name in payload["cases"] if name.startswith("axis_corner_")),
    )
    for name in names:
        row = mesh.row_qualification(name)
        assert isinstance(row, mesh.RowQualification)
        assert row.case_name == name
        assert row.row_fraction_lower == 0.89
        assert row.coverage_lower == 1.0
        assert row.continuous_carrier
        assert row.supported_driven_station_intervals_mm
        assert row.driver_origin_mm == tuple(payload["cases"][name]["placement"]["driver_origin_mm"])
        with pytest.raises(FrozenInstanceError):
            row.driver_turned_radius_mm = 0.0
    with pytest.raises(ValueError, match="row qualification"):
        mesh.row_qualification("unmeasured_hypothetical_face")


def test_crank_requires_every_source_owned_case(bounded_crank_contract_payload) -> None:
    import crank_mesh_geometry as geometry
    import crank_mesh_stack as mesh

    for name in geometry.required_calibration_case_names():
        payload = dict(bounded_crank_contract_payload, cases=dict(bounded_crank_contract_payload["cases"]))
        del payload["cases"][name]
        with pytest.raises(ValueError):
            mesh.require_qualified(payload)


@pytest.mark.parametrize("path,value", [
    (("qualified",), False),
    (("metric",), "CONTACT RATIO"),
    (("is_conjugate",), True),
    (("native_certificate",), True),
    (("tight_backlash_lower_mm",), 0.0),
    (("tight_backlash_lower_mm",), math.nan),
    (("loose_backlash_upper_mm",), math.inf),
    (("stock_form_coverage_lower",), 0.6199),
    (("stock_form_coverage_lower",), math.nan),
    (("row_available_fraction_lower",), 0.8499),
    (("row_available_fraction_lower",), math.nan),
    (("continuous_carrying_contact",), False),
    (("uncovered_phase_rad",), 0.000001),
    (("uncovered_phase_rad",), math.nan),
    (("handovers", 0, "continuous"), False),
    (("handovers", 0, "pitch_displacement_jump_upper_mm"), 0.005001),
    (("handovers", 0, "pitch_displacement_jump_upper_mm"), math.nan),
    (("handovers", 0, "pitch_displacement_jump_upper_mm"), -0.001),
    (("handovers", 0, "contact"), None),
    (("handovers",), []),
    (("phase_rows",), []),
    (("phase_rows", 0, "driver_phase_rad"), 0.001),
    (("phase_rows", 64, "driver_phase_rad"), 0.1),
    (("phase_rows", 64, "lower_contact", "driven_tooth"), 0),
    (("phase_rows", 64, "upper_contact", "driven_tooth"), 2),
    (("phase_rows", 2, "driver_phase_rad"), 0.0),
    (("phase_rows", 2, "lower_rad"), math.nan),
    (("phase_rows", 2, "upper_rad"), -0.030),
    (("phase_rows", 2, "error_rad"), -0.001),
    (("phase_rows", 2, "root_contact"), True),
    (("phase_rows", 2, "phase_error_rad"), -0.001),
    (("phase_rows", 2, "root_free_intervals_rad"), []),
    (("phase_rows", 2, "root_free_intervals_rad"), [[0.01, 0.02]]),
    (("phase_rows", 2, "free_intervals_rad"), []),
    (("phase_rows", 2, "free_intervals_rad"), [[0.01, 0.02]]),
    (("phase_rows", 2, "driver_phase_rad"), 0.013),
    (("phase_rows", 2, "root_sweep", "status"), "unresolved"),
    (("phase_rows", 2, "root_sweep", "root_is_carrying"), True),
    (("phase_rows", 2, "root_sweep", "root_air_lower_bound_mm"), -0.001),
    (("phase_rows", 2, "root_sweep", "root_air_lower_bound_mm"), None),
    (("phase_rows", 2, "root_sweep", "required_root_air_mm"), 0.03),
    (("phase_rows", 2, "root_sweep", "geometric_uncertainty_mm"), 0.002),
    (("phase_rows", 2, "root_sweep", "geometric_uncertainty_mm"), math.nan),
    (("phase_rows", 2, "root_sweep", "native_solid_certificate"), True),
    (("phase_components_rad",), []),
    (("phase_components_rad",), [[0.01, 0.02]]),
    (("phase_rows", 2, "lower_contact"), None),
    (("phase_rows", 2, "upper_contact", "kind"), "axial_face"),
    (("phase_rows", 2, "lower_contact", "kind"), "root_arc"),
    (("phase_rows", 2, "lower_contact", "kind"), "root_corner"),
    (("phase_rows", 2, "supported_branch_contacts"), []),
    (("phase_rows", 2, "branch_phase_reserves_rad"), [[63, 0.01]]),
    (("phase_rows", 2, "branch_phase_reserves_rad"), [[0, 0.0]]),
    (("phase_rows", 2, "supported_branch_contacts", 0, "tooth"), 63),
    (("phase_rows", 2, "supported_branch_contacts", 0, "contacts"), []),
    (("phase_rows", 2, "supported_branch_contacts", 0, "contacts", 0, "contact", "driven_tooth"), 63),
    (("phase_rows", 2, "lower_contact", "world_point_mm"), [math.inf, 0.0, 0.0]),
    (("phase_rows", 2, "lower_contact", "common_normal_supported"), False),
    (("phase_rows", 2, "upper_contact", "common_normal_supported"), False),
    (("phase_rows", 2, "lower_contact", "common_normal_error_bound"), -1e-12),
    (("phase_rows", 2, "lower_contact", "common_normal_error_bound"), math.nan),
    (("phase_rows", 2, "lower_contact", "opposed_normal_residual"), 1e-11),
    (("phase_rows", 2, "lower_contact", "driven_per_driver_velocity"), math.nan),
    (("numerical_error_bounds", "surface_mm"), -0.001),
    (("numerical_error_bounds", "phase_motion_mm"), math.nan),
    (("numerical_error_bounds",), {}),
    (("pose_domain", "radial_error_mm"), 0.0),
    (("pose_domain", "axial_error_mm"), 0.0),
    (("pose_domain", "all_runout_angles"), False),
    (("pose_domain", "components_mm"), []),
    (("pose_domain", "required_root_air_mm"), 0.02),
    (("numerical_error_bounds", "radial_mm"), 0.0),
    (("numerical_error_bounds", "axial_mm"), 0.0),
    (("row_available_intervals_mm",), []),
    (("row_available_intervals_mm",), [[-0.1, 0.1]]),
    (("row_available_intervals_mm",), [[-1.0, 1.0], [0.0, 2.0]]),
    (("row_available_intervals_mm",), [[-100.0, 100.0]]),
    (("placement", "driver_face_mm"), [0.0, 0.0]),
    (("placement", "driver_shoulder_z_mm"), 0.0),
    (("placement", "driver_turned_radius_mm"), 0.0),
    (("placement", "driver_origin_mm"), [0.0, 0.0, 0.0]),
    (("placement", "driven_origin_mm"), [0.0, 0.0, 0.0]),
    (("placement", "driver_frame"), [[0.0] * 3] * 3),
    (("placement", "driven_frame"), [[0.0] * 3] * 3),
    (("driver_profile", "teeth"), 15),
    (("driver_profile", "reference_teeth"), 16),
    (("driver_profile", "blank_radius_mm"), 0.0),
    (("driven_profile", "teeth"), 69),
    (("driven_profile", "helix_angle_deg"), 0.0),
    (("driven_profile", "radial_translation_mm"), 0.0),
    (("phase_window_rad",), [-0.019, -0.016]),
    (("phase_rows", 2, "lower_contact", "kind"), "axial_interior"),
])
def test_full_crank_contract_mutations_refuse(path, value, bounded_crank_contract_payload) -> None:
    import crank_mesh_stack as mesh

    payload = _crank_case_mutation(bounded_crank_contract_payload)
    target = payload["cases"]["nominal"]
    for field in path[:-1]:
        target = target[field]
    target[path[-1]] = value
    with pytest.raises(ValueError):
        mesh.require_qualified(payload)


@pytest.mark.parametrize("field,value", [
    ("common_normal_supported", False),
    ("kind", "root_corner"),
    ("kind", "root_arc"),
    ("kind", "axial_face"),
])
def test_crank_coverage_cannot_count_unsupported_branch_proofs(
    field, value, bounded_crank_contract_payload
) -> None:
    import crank_mesh_stack as mesh

    payload = _crank_case_mutation(bounded_crank_contract_payload)
    proof = payload["cases"]["nominal"]["phase_rows"][2]["supported_branch_contacts"][0]
    for witness in proof["contacts"]:
        witness["contact"][field] = value
    with pytest.raises(ValueError):
        mesh.require_qualified(payload)


def test_all_crank_corners_share_one_machined_retention_clock() -> None:
    import crank_mesh_geometry as geometry

    placements = geometry.calibration_case_placements()
    clock = placements["nominal"]["driver_clocking_rad"]
    assert all(pose["driver_clocking_rad"] == clock for pose in placements.values())


@pytest.mark.parametrize("field", ["driver_clocking_rad", "driven_clocking_rad"])
def test_a_reclocked_corner_cannot_reuse_the_crank_certificate(field, bounded_crank_contract_payload) -> None:
    import crank_mesh_stack as mesh

    payload = _crank_case_mutation(bounded_crank_contract_payload, "booked_open")
    pose = payload["cases"]["booked_open"]["placement"]
    pose[field] += 0.001
    with pytest.raises(ValueError, match="placement"):
        mesh.require_qualified(payload)


@pytest.mark.parametrize("field", [
    "qualified", "geometry_sha256", "cases", "phase_window_rad", "phase_seed_deg",
    "measurement_engine_sources_sha256", "measurement_engine_sha256",
])
def test_missing_crank_payload_fields_refuse(field, bounded_crank_contract_payload) -> None:
    import crank_mesh_stack as mesh

    payload = dict(bounded_crank_contract_payload)
    del payload[field]
    with pytest.raises(ValueError):
        mesh.require_qualified(payload)


@pytest.mark.parametrize("field", [
    "qualified", "metric", "is_conjugate", "native_certificate", "driver_profile",
    "driven_profile", "placement", "phase_rows", "phase_window_rad",
    "tight_backlash_lower_mm", "loose_backlash_upper_mm", "stock_form_coverage_lower",
    "row_available_fraction_lower", "row_available_intervals_mm",
    "continuous_carrying_contact", "uncovered_phase_rad", "handovers", "numerical_error_bounds",
    "phase_components_rad", "pose_domain",
])
def test_missing_crank_case_fields_refuse(field, bounded_crank_contract_payload) -> None:
    import crank_mesh_stack as mesh

    payload = _crank_case_mutation(bounded_crank_contract_payload)
    del payload["cases"]["nominal"][field]
    with pytest.raises(ValueError):
        mesh.require_qualified(payload)


def test_crank_pose_domains_are_exact_source_owned_not_corner_only(bounded_crank_contract_payload) -> None:
    import crank_mesh_geometry as geometry

    domains = geometry.calibration_case_domains()
    assert set(domains) == geometry.required_calibration_case_names()
    for name, case in bounded_crank_contract_payload["cases"].items():
        domain = domains[name]
        assert case["pose_domain"] == domain
        assert domain["all_runout_angles"]
        assert domain["components_mm"]
        assert domain["radial_error_mm"] > 0.0
        assert domain["axial_error_mm"] > 0.0
        assert case["numerical_error_bounds"]["radial_mm"] == domain["radial_error_mm"]
        assert case["numerical_error_bounds"]["axial_mm"] == domain["axial_error_mm"]
        for row in case["phase_rows"]:
            assert row["root_sweep"]["required_root_air_mm"] == domain["required_root_air_mm"]


@pytest.mark.parametrize("field", ["phase_window_rad", "phase_seed_deg", "geometry_sha256"])
def test_common_crank_phase_and_identity_mutations_refuse(field, bounded_crank_contract_payload) -> None:
    import crank_mesh_stack as mesh

    mutations = {"phase_window_rad": [-0.030, -0.010], "phase_seed_deg": math.nan, "geometry_sha256": "0" * 64}
    payload = dict(bounded_crank_contract_payload)
    payload[field] = mutations[field]
    with pytest.raises(ValueError):
        mesh.require_qualified(payload)


@pytest.mark.parametrize("source_name", [
    "crank_mesh_backlash_study.py", "crossed_mesh_study.py",
    "stock_form_contact_3d.py", "stock_form_root_angles.py", "stock_form_root_sweep.py",
    "stock_form_contact_continuation.py",
])
def test_missing_crank_engine_source_manifest_refuses(source_name, bounded_crank_contract_payload) -> None:
    import crank_mesh_stack as mesh

    payload = dict(bounded_crank_contract_payload)
    sources = dict(payload["measurement_engine_sources_sha256"])
    del sources[source_name]
    payload["measurement_engine_sources_sha256"] = sources
    with pytest.raises(ValueError, match="measurement-engine identity"):
        mesh.require_qualified(payload)


@pytest.mark.parametrize("digest", ["", "0" * 63, "G" * 64, "A" * 64, None])
def test_malformed_crank_engine_source_digest_refuses(digest, bounded_crank_contract_payload) -> None:
    import crank_mesh_stack as mesh

    payload = dict(bounded_crank_contract_payload)
    sources = dict(payload["measurement_engine_sources_sha256"])
    sources["stock_form_contact_3d.py"] = digest
    payload["measurement_engine_sources_sha256"] = sources
    with pytest.raises(ValueError, match="measurement-engine identity"):
        mesh.require_qualified(payload)


def test_stale_crank_engine_manifest_digest_refuses(bounded_crank_contract_payload) -> None:
    import crank_mesh_stack as mesh

    payload = dict(bounded_crank_contract_payload)
    payload["measurement_engine_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="provenance"):
        mesh.require_qualified(payload)
    payload = dict(bounded_crank_contract_payload)
    sources = dict(payload["measurement_engine_sources_sha256"])
    sources["stock_form_contact_3d.py"] = "0" * 64
    payload["measurement_engine_sources_sha256"] = sources
    with pytest.raises(ValueError, match="provenance"):
        mesh.require_qualified(payload)


def test_unregistered_crank_engine_source_refuses(bounded_crank_contract_payload) -> None:
    import crank_mesh_stack as mesh

    payload = dict(bounded_crank_contract_payload)
    sources = dict(payload["measurement_engine_sources_sha256"])
    sources["ideal_contact_ratio_fallback.py"] = "0" * 64
    payload["measurement_engine_sources_sha256"] = sources
    with pytest.raises(ValueError, match="measurement-engine identity"):
        mesh.require_qualified(payload)


@pytest.mark.parametrize("path", [
    ("placement", "driver_face_mm"),
    ("placement", "driven_face_mm"),
    ("placement", "driver_shoulder_z_mm"),
    ("placement", "driver_turned_radius_mm"),
    ("placement", "driver_origin_mm"),
    ("placement", "driven_origin_mm"),
    ("placement", "driver_frame"),
    ("placement", "driven_frame"),
    ("placement", "driver_clocking_rad"),
    ("placement", "driven_clocking_rad"),
    ("driver_profile", "teeth"),
    ("driver_profile", "reference_teeth"),
    ("driver_profile", "blank_radius_mm"),
    ("driver_profile", "radial_translation_mm"),
    ("driven_profile", "helix_angle_deg"),
    ("phase_rows", 2, "driver_phase_rad"),
    ("phase_rows", 2, "lower_rad"),
    ("phase_rows", 2, "upper_rad"),
    ("phase_rows", 2, "error_rad"),
    ("phase_rows", 2, "root_contact"),
    ("phase_rows", 2, "lower_contact"),
    ("phase_rows", 2, "upper_contact"),
    ("phase_rows", 2, "lower_contact", "kind"),
    ("phase_rows", 2, "lower_contact", "world_point_mm"),
    ("phase_rows", 2, "lower_contact", "driven_normal_world"),
    ("phase_rows", 2, "lower_contact", "driver_normal_world"),
    ("phase_rows", 2, "lower_contact", "common_normal_supported"),
    ("phase_rows", 2, "lower_contact", "common_normal_error_bound"),
    ("phase_rows", 2, "lower_contact", "opposed_normal_residual"),
    ("phase_rows", 2, "lower_contact", "driven_per_driver_velocity"),
    ("phase_rows", 2, "supported_branch_contacts"),
    ("phase_rows", 2, "branch_phase_reserves_rad"),
    ("phase_rows", 2, "supported_branch_contacts", 0, "tooth"),
    ("phase_rows", 2, "supported_branch_contacts", 0, "contacts"),
    ("phase_rows", 2, "supported_branch_contacts", 0, "contacts", 0, "side"),
    ("phase_rows", 2, "supported_branch_contacts", 0, "contacts", 0, "contact"),
    ("phase_rows", 2, "phase_error_rad"),
    ("phase_rows", 2, "root_free_intervals_rad"),
    ("phase_rows", 2, "free_intervals_rad"),
    ("phase_rows", 2, "root_sweep"),
    ("phase_rows", 2, "root_sweep", "status"),
    ("phase_rows", 2, "root_sweep", "root_is_carrying"),
    ("phase_rows", 2, "root_sweep", "required_root_air_mm"),
    ("phase_rows", 2, "root_sweep", "root_air_lower_bound_mm"),
    ("phase_rows", 2, "root_sweep", "geometric_uncertainty_mm"),
    ("phase_rows", 2, "root_sweep", "native_solid_certificate"),
    ("phase_rows", 2, "root_sweep", "free_inner"),
    ("phase_rows", 2, "root_sweep", "free_outer"),
    ("phase_rows", 2, "root_sweep", "offset_domain_rad"),
    ("handovers", 0, "continuous"),
    ("handovers", 0, "pitch_displacement_jump_upper_mm"),
    ("handovers", 0, "contact"),
    ("handovers", 0, "side"),
    ("handovers", 0, "pair"),
    ("handovers", 0, "phase_bracket_rad"),
    ("numerical_error_bounds", "surface_mm"),
    ("numerical_error_bounds", "phase_motion_mm"),
    ("numerical_error_bounds", "te_rad"),
    ("pose_domain", "radial_error_mm"),
    ("pose_domain", "axial_error_mm"),
    ("pose_domain", "all_runout_angles"),
    ("pose_domain", "components_mm"),
    ("pose_domain", "angularity_full_cone"),
    ("pose_domain", "required_root_air_mm"),
    ("numerical_error_bounds", "radial_mm"),
    ("numerical_error_bounds", "axial_mm"),
])
def test_missing_crank_nested_contract_fields_refuse(path, bounded_crank_contract_payload) -> None:
    import crank_mesh_stack as mesh

    payload = _crank_case_mutation(bounded_crank_contract_payload)
    target = payload["cases"]["nominal"]
    for field in path[:-1]:
        target = target[field]
    del target[path[-1]]
    with pytest.raises(ValueError):
        mesh.require_qualified(payload)


def test_row_factory_refuses_unqualified_before_reading_placement(monkeypatch) -> None:
    import crank_mesh_stack as mesh

    monkeypatch.setattr(mesh, "CALIBRATION", {"qualified": False, "refusal": "synthetic unqualified"})
    with pytest.raises(ValueError, match="synthetic unqualified"):
        mesh.row_qualification("nominal")


@pytest.mark.parametrize("owner,field", [
    ("pinion", "FACE_WIDTH"),
    ("pinion", "SHOULDER_LENGTH"),
    ("pinion", "TURNED_DIA"),
    ("pinion", "TURNED_DIA_FITUP_MIN"),
    ("pinion", "SEAT_GAP_MAX_MM"),
    ("pinion", "BASE_TANGENT_SPAN_LIMITS_MM"),
    ("pinion", "TOOTH_RUNOUT_TIR_MM"),
    ("gear64", "FACE_WIDTH"),
    ("gear64", "BASE_TANGENT_SPAN_LIMITS_MM"),
    ("gear64", "TOOTH_RUNOUT_TIR_MM"),
    ("geometry", "POST_ANGLE_DEG"),
    ("geometry", "CONE_FLOAT_NORTH"),
    ("geometry", "FRAME_DY"),
    ("geometry", "GEAR_AXIS_SHIFT"),
])
def test_hypothetical_crank_geometry_refuses_stale_rows(
    owner, field, monkeypatch, bounded_crank_contract_payload
) -> None:
    import crank_mesh_geometry as geometry
    import crank_mesh_stack as mesh

    payload = bounded_crank_contract_payload
    mesh.require_qualified(payload)
    monkeypatch.setattr(mesh, "CALIBRATION", payload)
    module = {"pinion": geometry.pinion, "gear64": geometry.gear64, "geometry": geometry}[owner]
    previous = getattr(module, field)
    changed = tuple(value + 0.01 for value in previous) if isinstance(previous, tuple) else previous + 0.01
    monkeypatch.setattr(module, field, changed)
    assert mesh.geometry_sha256() != payload["geometry_sha256"]
    with pytest.raises(ValueError, match="stale"):
        mesh.require_qualified(payload)
    with pytest.raises(ValueError, match="stale"):
        mesh.row_qualification("nominal")


def test_64t_pitch_cylinder_slice_law_is_only_a_physical_frame_construction() -> None:
    import build_dt_drive_train_assembly as bdt
    from cone_line import COS_I, SIN_I, cone_station

    for shift in (-mate.FACE_WIDTH / 2.0, 0.0, mate.FACE_WIDTH / 2.0 + bdt.CONE_FLOAT_NORTH):
        centre = cone_station(bdt.GEAR64_CENTRE_STATION + shift)
        alpha = math.atan2(bdt.Y_CRANK - bdt.Y_DRIVE, (centre[0] - bdt.X_CRANK) * COS_I)
        expected = centre[2] + bdt.R64 * math.cos(alpha) * SIN_I
        assert bdt.gear64_contact_z(shift) == pytest.approx(expected, abs=1e-9)
    translated = bdt.gear64_contact_z(0.0) + bdt.CONE_FLOAT_NORTH * COS_I
    assert not math.isclose(bdt.gear64_contact_z(bdt.CONE_FLOAT_NORTH), translated, abs_tol=1e-9)


def test_64t_row_carries_every_axis_pose() -> None:
    # Codex P2 on #1154 (R9-56): the row ignored the axis poses that move the
    # 64T's teeth along the crank axis against the 16T's.  The budget is
    # re-derived here from the fits, summed at print-worst: the 16T side at
    # its tip radius, the 64T's rim moved in the cone frame.
    import build_dt_drive_train_assembly as bdt
    import cone_line
    import dt_cone_pivot_post_spec as post
    import dt_crank_drive_gear_spec as gear64
    import crank_mesh_stack as mesh
    from gear_seat_fit import GEAR_SEAT_CLEARANCE

    running = _config.fit("shaft_in_bushing")["diametral_clearance_mm"][1]
    angle = math.tan(math.radians(post.CRANK_BORE_ANGLE_LIMIT_DEG))
    sin_i = math.sin(math.radians(cone_line.INCLINE_DEG))
    cos_i = math.cos(math.radians(cone_line.INCLINE_DEG))
    tip16 = bdt._PINION_TIP_R_MAX
    crank_side = (
        running / mesh.CRANK_BEARING_LENGTH
        + spec.BORE_DIAMETRAL_CLEARANCE[1] / spec.OVERALL_LENGTH
        + angle
    ) * tip16
    rim = (gear64.OUTSIDE_DIA + gear64.OUTSIDE_DIA_TOLERANCE_MM) / 2.0
    overhang = bdt._GEAR64_OVERHANG
    cone_radial = (
        GEAR_SEAT_CLEARANCE[1] / 2.0
        + running / 2.0
        + running / post.CONE_BOSS_LENGTH * overhang
        + (overhang + post.CONE_BOSS_LENGTH / 2.0) * angle
    )
    cone_axial = (running / post.CONE_BOSS_LENGTH + angle) * rim
    budget = crank_side + cone_radial * sin_i + cone_axial * cos_i
    assert bdt.CRANK_ROW_POSE_AXIAL == pytest.approx(budget, abs=1e-9)
    assert budget > 0.0
    codex = (
        bdt.CRANK_ROW_POSE_TERMS["16T bore on the crankshaft"]
        + bdt.CRANK_ROW_POSE_TERMS["cone shaft float in the post boss"]
    )
    assert 0.0 < codex <= budget


def test_t120_radial_carries_every_fit_offset_and_axis_pose() -> None:
    # Every fit and angular pose enters at print-worst; a nominally clear
    # band near the clearance threshold must not ignore the gear's seat float.
    import build_dt_drive_train_assembly as bdt
    import cone_line
    import dt_cone_pivot_post_spec as post
    import crank_mesh_stack as mesh
    from gear_seat_fit import GEAR_SEAT_CLEARANCE

    seat_float = GEAR_SEAT_CLEARANCE[1] / 2.0
    assert seat_float > 0.0
    running = _config.fit("shaft_in_bushing")["diametral_clearance_mm"][1]
    angle = math.tan(math.radians(post.CRANK_BORE_ANGLE_LIMIT_DEG))
    sin_i = math.sin(math.radians(cone_line.INCLINE_DEG))
    band_end = mesh.CRANK_OVERHANG + mesh.PINION_HALF_FACE_MAX
    lever = mesh.MESH_LEVER + mesh.PINION_HALF_FACE_MAX
    crank_side = (
        running / 2.0
        + running / mesh.CRANK_BEARING_LENGTH * band_end
        + spec.BORE_DIAMETRAL_CLEARANCE[1] / 2.0
        + mesh.TOOTH_RUNOUT_TIR_MM / 2.0
        + lever * angle
    )
    rim, overhang = bdt._TIP120, bdt._T120_OVERHANG
    cone_radial = (
        GEAR_SEAT_CLEARANCE[1] / 2.0
        + running / 2.0
        + running / post.CONE_BOSS_LENGTH * overhang
        + (overhang + post.CONE_BOSS_LENGTH / 2.0) * angle
    )
    cone_axial = running / post.CONE_BOSS_LENGTH * rim + rim * angle
    budget = crank_side + cone_radial + cone_axial * sin_i
    assert bdt.T120_POSE_RADIAL >= budget - 1e-9

    def concentric(turned_dia: float) -> float:
        return bdt.pinion_t120_clearances(
            turned_dia=turned_dia, pose_radial=0.0, pose_axial=0.0
        )["turned band radial"]

    floor = bdt.T120_TURNED_BAND_RADIAL_FLOOR
    # Derive the negative control from the current clearance threshold,
    # rather than reusing a diameter that belongs to another tooth system.
    marginal = (
        spec.TURNED_DIA + 2.0 * (concentric(spec.TURNED_DIA) - floor) - seat_float
    )
    assert concentric(marginal) > floor
    assert concentric(marginal) - seat_float < floor
    assert bdt.T120_TURNED_BAND_RADIAL <= concentric(spec.TURNED_DIA) - budget + 1e-9


def _assert_no_t120_shortfall_waiver() -> None:
    policy = (
        Path(spec.__file__).parents[1] / "docs" / "drawing-simplicity-policy.md"
    ).read_text(encoding="utf-8")
    rows = [
        line
        for line in policy.split("\n## Named exceptions", 1)[1].splitlines()
        if line.startswith("| MHA-DT-010") and "T120" in line.split("|")[1]
    ]
    assert not rows
    source = Path(spec.__file__).read_text(encoding="utf-8")
    assert "Named exception: MHA-DT-010 turned band" not in source


def test_t120_clearance_facts_match_the_ordinary_floors_without_a_waiver() -> None:
    # The current envelope passes the ordinary clearance floors. Its finite
    # printed fact is exact and rounded down; an absent section is not a size.
    import build_dt_drive_train_assembly as bdt

    air, radial = bdt.T120_SHOULDER_AIR, bdt.T120_TURNED_BAND_RADIAL
    assert math.isfinite(radial)
    assert radial >= bdt.T120_TURNED_BAND_RADIAL_FLOOR
    assert air >= bdt.T120_PINION_AIR_FLOOR
    assert spec.T120_SHOULDER_AIR_WORST == (
        math.floor(air * 100.0) / 100.0 if math.isfinite(air) else math.inf
    )
    assert spec.T120_TURNED_BAND_RADIAL_WORST == math.floor(radial * 100.0) / 100.0
    rss = bdt.pinion_t120_clearances(
        pose_radial=math.hypot(*(r for r, _ in bdt.T120_POSE_TERMS.values())),
        pose_axial=math.hypot(*(a for _, a in bdt.T120_POSE_TERMS.values())),
    )
    assert rss["shoulder air"] >= air
    assert rss["turned band radial"] >= radial
    # Increasing either feature consumes only its own stated margin.
    wider = bdt.pinion_t120_clearances(
        turned_dia=spec.TURNED_DIA
        + 2.0 * (radial - spec.T120_TURNED_BAND_RADIAL_WORST + 0.01)
    )
    assert wider["turned band radial"] < spec.T120_TURNED_BAND_RADIAL_WORST
    if math.isfinite(air):
        longer = bdt.pinion_t120_clearances(
            shoulder_length=spec.SHOULDER_LENGTH
            + air
            - spec.T120_SHOULDER_AIR_WORST
            + 0.01
        )
        assert longer["shoulder air"] < spec.T120_SHOULDER_AIR_WORST
    else:
        assert air == math.inf
        assert "NO AXIAL OVERLAP" in spec.DRAWING_NOTES
    _assert_no_t120_shortfall_waiver()


def test_t120_shoulder_air_bounds_every_reachable_south_rim_point() -> None:
    # Half-step samples do not define the answer: the continuous section
    # search must bound them, or prove that the entire section is absent.
    import numpy as np

    import build_dt_drive_train_assembly as bdt

    shifts, heights = bdt._cone_corners(bdt._CONE_FLOATS, bdt._CRANK_HEIGHT_BAND)
    reach = bdt._PINION_TIP_R_MAX + bdt.T120_POSE_RADIAL
    if bdt.T120_SHOULDER_AIR == math.inf:
        assert np.isposinf(
            bdt._t120_lowest(bdt._T120_SOUTH_FACE_STATION + shifts, heights, reach)
        ).all()
        assert spec.T120_SHOULDER_AIR_WORST == math.inf
        return
    shift = (
        min(bdt._CONE_BOSS_NORTH_BAND)
        + min(bdt._COLLAR_WIDTH_BAND)
        + min(bdt._GEAR64_FACE_LIMITS)
    )
    dy = min(bdt._CRANK_HEIGHT_BAND)
    theta = np.deg2rad((np.arange(7200) + 0.5) * 0.05)
    centre = bdt.cone_station(bdt._T120_SOUTH_FACE_STATION + shift)
    offset = bdt._TIP120 * np.cos(theta)
    x = centre[0] + offset * bdt.COS_I
    y = bdt.Y_DRIVE + bdt._TIP120 * np.sin(theta)
    z = centre[2] - offset * bdt.SIN_I
    inside = np.hypot(x - bdt.X_CRANK, y - (bdt.Y_CRANK + dy)) <= reach
    assert inside.any()
    shoulder_top = (
        bdt._POST_BOSS_NORTH
        + max(bdt._BOSS_NORTH_BAND)
        + bdt.PINION_SEAT_FEELER
        + max(bdt.PINION_END_PLAY)
        + spec.SHOULDER_LENGTH
        + max(bdt._PINION_SHOULDER_BAND)
    )
    witness = float(z[inside].min()) - bdt.T120_POSE_AXIAL - shoulder_top
    assert bdt.T120_SHOULDER_AIR <= witness
    assert spec.T120_SHOULDER_AIR_WORST <= witness


def test_t120_search_never_looks_outside_the_section() -> None:
    # Codex P2 on #1154 (review 3): the search priced a point outside T120's
    # section with a finite penalty, so its objective rose to 955.6 there and
    # fell again to 157.9, and golden section's convexity no longer held.  The
    # section's interval is found first and only its points are searched,
    # its ends included; the worst case stays the same.
    import numpy as np

    import build_dt_drive_train_assembly as bdt

    lo, hi = np.array([0.0]), np.array([10.0])

    # Inside p <= 3 the objective falls to -3 at the end; outside it is far
    # lower, low enough that any finite penalty of 100 per mm would win.
    def objective(p: np.ndarray) -> np.ndarray:
        return np.where(p <= 3.0, -p, -1000.0 + p)

    least = bdt._convex_min_where(objective, (lambda p: p - 3.0,), lo, hi)
    assert least[0] == pytest.approx(-3.0, abs=1e-9)
    nowhere = bdt._convex_min_where(objective, (lambda p: p + 1.0,), lo, hi)
    assert nowhere[0] == math.inf


def test_t120_fit_up_closes_and_both_sheets_state_it() -> None:
    # Either fit-up cut, taken to its limit, passes the feeler at every
    # corner of the same stack; the minimum band is an actual size.
    import build_dt_drive_train_assembly as bdt
    import draw_dt_drive_train_assembly as drawing
    import dt_drive_train_steps

    feeler = spec.T120_FITUP_FEELER_MM
    turned_down = bdt.t120_fitup_reading(
        turned_dia=spec.TURNED_DIA_FITUP_MIN - 2.0 * bdt._PINION_TURNED_RADIUS_UP
    )
    faced_back = bdt.t120_fitup_reading(shoulder_length=spec.SHOULDER_LENGTH_FITUP_MIN)
    assert turned_down["turned band radial"] >= feeler
    assert faced_back["shoulder air"] >= feeler
    # The shoulder's fit-up limit is its printed short limit.
    assert spec.SHOULDER_LENGTH_FITUP_MIN == pytest.approx(
        spec.SHOULDER_LENGTH + spec.SHOULDER_LENGTH_LIMITS[0]
    )
    # The part sheet permits the turn-down to its floor.
    turn_down = f"Ø{spec.TURNED_DIA_FITUP_MIN:.2f} MIN"
    assert turn_down in spec.DRAWING_NOTES
    # The drive-train crank step checks the pair before the pin is drilled.
    number = dt_drive_train_steps.step_number("crank-mesh-checked")
    step = drawing.CONE_CRANK_STEPS.split(f"\n{number}. ", 1)[1]
    step = " ".join(step.split(f"\n{number + 1}. ")[0].split())
    check = step.index(f"{feeler:.2f} FEELER")
    drill = step.index("MATCH-DRILL")
    # The push names both parts the check closes on, before the reading; the
    # wording around them is free (Codex P3 on #1154, review 4).
    push = step.index("PUSH")
    sentence = step[push : step.index(";", push)]
    assert all(part in sentence for part in spec.T120_FITUP_PUSHED)
    assert push < check < drill
    assert check < step.index(turn_down) < drill
    assert check < step.index(f"{spec.SHOULDER_LENGTH_FITUP_MIN:.1f} MIN") < drill


def test_t120_fit_up_stops_a_band_that_would_pass_and_then_close() -> None:
    # Codex P2 on #1154 (review 2): a check that took up only MHA-DT-011's play
    # passed a Ø16.043 band with the cone shaft centred in the post boss; once
    # that play closed the band kept 0.018.  The check pushes MHA-DT-010 and
    # T120 toward each other, so it reads that band as it runs.
    import build_dt_drive_train_assembly as bdt

    feeler = spec.T120_FITUP_FEELER_MM
    up = bdt._PINION_TURNED_RADIUS_UP

    def radial(read, dia: float) -> float:
        return read(turned_dia=dia - 2.0 * up)["turned band radial"]

    def cone_centred(**geometry) -> dict[str, float]:
        return bdt.t120_fitup_reading(pushed=(spec.PINION_NUMBER,), **geometry)

    # The actual band that just passes with the cone shaft centred.
    passing = spec.TURNED_DIA + 2.0 * (radial(cone_centred, spec.TURNED_DIA) - feeler)
    assert passing > spec.PITCH_DIA
    assert radial(cone_centred, passing) == pytest.approx(feeler, abs=1e-9)
    in_service = radial(bdt.pinion_t120_clearances, passing)
    cone_play = bdt.T120_POSE_TERMS["cone shaft float in the post boss"][0]
    assert in_service == pytest.approx(feeler - cone_play, abs=1e-9)
    # The printed check reads it at that service worst and stops the feeler.
    assert radial(bdt.t120_fitup_reading, passing) == pytest.approx(
        in_service, abs=1e-9
    )
    assert radial(bdt.t120_fitup_reading, passing) < feeler


def test_t120_turn_down_height_and_actual_fitup_row_are_separate_gates() -> None:
    # Retain the physical feeler-height transition, and require the exact
    # independently measured turned-fitup row instead of interpolating lengths.
    import build_dt_drive_train_assembly as bdt

    feeler = spec.T120_FITUP_FEELER_MM
    height = bdt.T120_BAND_CHECK_CRANK_HEIGHT
    low, high = bdt._CRANK_HEIGHT_BAND
    assert low <= height <= high

    def band_reading(crank_height: float) -> float:
        return bdt.t120_fitup_reading(crank_heights=(crank_height,))[
            "turned band radial"
        ]

    if band_reading(low) >= feeler:
        assert height == pytest.approx(low, abs=1e-12)
        assert band_reading(high) >= feeler
    elif band_reading(high) < feeler:
        assert height == pytest.approx(high, abs=1e-12)
    else:
        assert band_reading(height) == pytest.approx(feeler, abs=1e-9)
        assert band_reading(height + 0.01) > feeler > band_reading(height - 0.01)
    import crank_mesh_stack as mesh
    import crank_mesh_requirements as requirements

    mesh.require_qualified()
    row = mesh.row_qualification("turned_fitup_floor")
    assert row.driver_turned_radius_mm == spec.TURNED_DIA_FITUP_MIN / 2.0
    assert row.row_fraction_lower >= requirements.ROW_ENGAGEMENT_MIN
    assert row.coverage_lower >= requirements.STOCK_FORM_COVERAGE_MIN
    assert row.continuous_carrier


def _sentences(text: str) -> list[str]:
    """The sentences of sheet text, whatever its line breaks."""
    return [part for part in re.split(r"[.;]\s+|[.;]$", " ".join(text.split())) if part]


def _t120_clearance_facts(text: str) -> dict[str, set[float]]:
    """Finite clearance figures are attached to their own named feature."""
    found: dict[str, set[float]] = {"BAND": set(), "SHOULDER": set()}
    for feature, figure in re.findall(r"\b(BAND|SHOULDER)\s+([+-]?\d+\.\d+)\b", text):
        found[feature].add(float(figure))
    return found


# MHA-DT-000's crank step, which carries the T120 check.  The part spec never
# reads the step registry (test_part_isolation), so the key lives here.
_T120_CHECK_STEP_KEY = "crank-mesh-checked"


def _crank_step() -> str:
    import draw_dt_drive_train_assembly as drawing
    import dt_drive_train_steps

    number = dt_drive_train_steps.step_number(_T120_CHECK_STEP_KEY)
    step = drawing.CONE_CRANK_STEPS.split(f"\n{number}. ", 1)[1]
    return step.split(f"\n{number + 1}. ")[0]


def test_both_sheets_state_current_t120_clearance_and_absent_sections() -> None:
    # Each finite fact belongs to its own feature. A missing shoulder section
    # is stated as absence, never as an infinite size or an obsolete shortfall.
    import build_dt_drive_train_assembly as bdt

    band = round(math.floor(bdt.T120_TURNED_BAND_RADIAL * 100.0) / 100.0, 2)
    shoulder = (
        {round(math.floor(bdt.T120_SHOULDER_AIR * 100.0) / 100.0, 2)}
        if math.isfinite(bdt.T120_SHOULDER_AIR)
        else set()
    )
    for text in (spec.DRAWING_NOTES, _crank_step()):
        assert _t120_clearance_facts(text) == {"BAND": {band}, "SHOULDER": shoulder}
        if not shoulder:
            assert "SHOULDER NO AXIAL OVERLAP" in text
        assert not re.search(r"\b(?:INF|NAN)\b|∞", text)


def test_each_t120_cut_answers_only_its_own_failed_reading() -> None:
    # A passing band's reading must never trigger its cut merely because
    # the independent shoulder reading fails.
    import build_dt_drive_train_assembly as bdt

    # Exercise every cut combination independently of whether the current
    # configuration needs a cut at any height.
    feeler = spec.T120_FITUP_FEELER_MM
    failing = math.nextafter(feeler, -math.inf)
    for reading, expected in (
        ({"turned band radial": feeler, "shoulder air": failing}, {"shoulder air"}),
        (
            {"turned band radial": failing, "shoulder air": feeler},
            {"turned band radial"},
        ),
        (
            {"turned band radial": failing, "shoulder air": failing},
            {"turned band radial", "shoulder air"},
        ),
        ({"turned band radial": feeler, "shoulder air": math.inf}, set()),
    ):
        assert bdt.t120_fitup_cuts(reading) == expected
    low, high = bdt._CRANK_HEIGHT_BAND
    heights = [low + (high - low) * i / 40.0 for i in range(41)]
    witnesses = [
        (height, bdt.t120_fitup_reading(crank_heights=(height,))) for height in heights
    ]
    shoulder_only = [
        (height, reading)
        for height, reading in witnesses
        if reading["turned band radial"] >= spec.T120_FITUP_FEELER_MM
        and reading["shoulder air"] < spec.T120_FITUP_FEELER_MM
    ]
    if not shoulder_only:
        assert all(reading["shoulder air"] >= feeler for _, reading in witnesses)
    for height, witness in shoulder_only:
        assert bdt.t120_fitup_cuts(witness) == {"shoulder air"}
        faced = bdt.t120_fitup_reading(
            crank_heights=(height,), shoulder_length=spec.SHOULDER_LENGTH_FITUP_MIN
        )
        assert bdt.t120_fitup_cuts(faced) == frozenset()
    # The physical cut-height domain is separate from stock-contact evidence.
    low, high = bdt._CRANK_HEIGHT_BAND
    turned = [
        height
        for height in (low + (high - low) * i / 40.0 for i in range(41))
        if "turned band radial"
        in bdt.t120_fitup_cuts(bdt.t120_fitup_reading(crank_heights=(height,)))
    ]
    assert max(turned, default=low) <= bdt.T120_BAND_CHECK_CRANK_HEIGHT + 1e-12
    if not turned:
        assert all(reading["turned band radial"] >= feeler for _, reading in witnesses)
    import crank_mesh_stack as mesh
    import crank_mesh_requirements as requirements

    mesh.require_qualified()
    fitup = mesh.row_qualification("turned_fitup_floor")
    assert fitup.driver_turned_radius_mm == spec.TURNED_DIA_FITUP_MIN / 2.0
    assert fitup.row_fraction_lower >= requirements.ROW_ENGAGEMENT_MIN
    # Both sheets give each cut its own condition: the turn-down floor is
    # stated with the band and its check only, the facing floor with the
    # shoulder only.  The part sheet points at the MHA-DT-000 T120 check, which
    # carries the band-only condition, by name and never by step number (a
    # sequence edit must not re-key the part).
    turn_down = f"Ø{spec.TURNED_DIA_FITUP_MIN:.2f} MIN"
    face_back = f"{spec.SHOULDER_LENGTH_FITUP_MIN:.1f} MIN"
    for text in (spec.DRAWING_NOTES, _crank_step()):
        for floor, own, other in (
            (turn_down, "BAND", "SHOULDER"),
            (face_back, "SHOULDER", "BAND"),
        ):
            for sentence in _sentences(text):
                if floor in sentence:
                    assert own in sentence and other not in sentence, sentence
    import dt_drive_train_steps

    assert any(
        turn_down in sentence
        and dt_drive_train_steps.DRAWING_NUMBER in sentence
        and "T120" in sentence
        for sentence in _sentences(spec.DRAWING_NOTES)
    )
    assert not re.search(r"STEP\s+\d", spec.DRAWING_NOTES)


def test_crank_step_runs_free_only_after_the_t120_check_closes() -> None:
    # Codex P2 on #1154 (review 3): the step asked for a full revolution that
    # must never bind before the T120 check, yet the unadjusted pair may rub
    # (-0.10 / -0.12).  The seat is set and the check closed first; the
    # free-running revolution follows, then the match-drill.
    import draw_dt_drive_train_assembly as drawing

    step = " ".join(_crank_step().split())
    seat = step.index(f"{drawing.PINION_SEAT_FEELER:.2f} OFF")
    check = step.index(f"{spec.T120_FITUP_FEELER_MM:.2f} FEELER")
    cuts = max(
        step.index(f"Ø{spec.TURNED_DIA_FITUP_MIN:.2f} MIN"),
        step.index(f"{spec.SHOULDER_LENGTH_FITUP_MIN:.1f} MIN"),
    )
    free = step.index("BIND")
    assert seat < check < cuts < free < step.index("MATCH-DRILL")


def test_both_gear_sheets_state_stock_mesh_requirements_not_a_fake_certificate() -> None:
    import crank_mesh_requirements as requirements
    import dt_crank_drive_gear_notes as gear_notes

    assert notes.STOCK_FORM_COVERAGE_ROW[1] == gear_notes.STOCK_FORM_COVERAGE_ROW[1]
    for module in (notes, gear_notes):
        data = module.GEAR_DATA
        assert "STOCK-FORM COVERAGE" in data
        assert f"{requirements.STOCK_FORM_COVERAGE_MIN:.2f} MIN" in data
        assert "NO UNCOVERED PHASE" in data
        assert f"HANDOVER JUMP {requirements.HANDOVER_JUMP_MAX_MM:.3f} mm MAX" in data
        assert "CONTACT RATIO" not in data
        assert not hasattr(module, "CONTACT_RATIO_ROW")
        assert not hasattr(module, "WORST_CONTACT_RATIO")
        assert "crank_mesh_stack" not in Path(module.__file__).read_text(encoding="utf-8")
    assert requirements.UNCOVERED_PHASE_MAX_RAD == 0.0
