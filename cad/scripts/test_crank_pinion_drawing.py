"""Offline contracts for the crank-pinion drawing.

The print is recreated under ``cad/docs/drawing-simplicity-policy.md``: a
removable 16T stock pinion with a hub boss and a match-drilled retention pin
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
import build_crank_pinion as part
import crank_pinion_spec as spec
import crank_drive_gear_spec as mate
import crankshaft_spec
import draw_crank_pinion as drawing
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS
from _drawing_registry import DRAWINGS_BY_NAME


def _source() -> str:
    return Path(drawing.__file__).read_text(encoding="utf-8")


def _build_source() -> str:
    return Path(part.__file__).read_text(encoding="utf-8")


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/crank-pinion.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/crank-pinion.pdf")
    assert drawing.PNG.as_posix().endswith("/png/crank-pinion_drawing.png")
    assert DRAWINGS_BY_NAME["crank_pinion"].script == Path(drawing.__file__).resolve()


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
    assert spec.OUTSIDE_DIA == pytest.approx(
        (part.TEETH + 2) / part.DP * spec.MM_PER_IN
    )
    assert spec.FACE_WIDTH == part.FACE_WIDTH
    assert spec.BORE_DIA == pytest.approx(part.BORE_DIAMETER)
    assert "OUTSIDE DIAMETER" not in spec.GEAR_DATA
    assert "FACE WIDTH" not in spec.GEAR_DATA


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
    assert "draw_crank_pinion.py" in PRECISION_MIGRATED_DRAWINGS
    source = _source()
    assert "set_dimension_precision" not in source
    assert "SetPrecision3" not in source
    assert "DIMENSION_PRECISION" not in source
    assert "assert_imported_precision(" in source
    assert "apply_drawing_precision(adapter, DRAWING_PRECISION)" in _build_source()


def test_grown_teeth_keep_the_south_seat_and_boss_length() -> None:
    # c'' variant B (user ruling 2026-09-30): the teeth grow 1.8 north of the
    # 9.5 face; the boss keeps its 14.0 so the W15 pin wall is unchanged, and
    # the south seat on MHA-016 does not move.
    assert spec.FACE_WIDTH == pytest.approx(9.5 + 1.8)
    assert spec.BOSS_LENGTH == pytest.approx(14.0)
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
    # fit's acceptance. One source (pin_hole_note) now prints on both sheets;
    # only the opening pair names the other part and where the hole runs.
    _assert_four_fact_note(drawing.PIN_HOLE_NOTE, spec.CRANKSHAFT_NUMBER)
    _assert_four_fact_note(spec.CRANKSHAFT_PIN_HOLE_PROCESS, spec.PINION_NUMBER)
    pinion = drawing.PIN_HOLE_NOTE.split("\n")
    shaft = spec.CRANKSHAFT_PIN_HOLE_PROCESS.split("\n")
    assert pinion[2:] == shaft[2:] == list(spec.PIN_FIT_LINES)
    assert drawing.PIN_HOLE_NOTE == spec.PIN_HOLE_PROCESS
    crankshaft_drawing = Path(drawing.__file__).with_name("draw_crankshaft.py").read_text(
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
    # Eye pass of f0c105531: at ISO_CENTER x 0.345 the isometric began under
    # the boss diameter's text (0.3014 +- 0.0066). The sheet-side check reads
    # the view's bounding box, which w15-301f4bf4e read back as
    # (0.3091, 0.4109) at centre 0.360 -- wider than the drawn silhouette, so
    # 0.360 failed it. Those offsets carry over to any centre at 3:1.
    left_offset, right_offset = 0.3091023168 - 0.360, 0.4108976832 - 0.360
    text_right = (
        drawing.BOSS_DIA_TEXT_X + drawing.BOSS_DIA_TEXT_HALF_WIDTH + drawing.ISO_TEXT_CLEARANCE
    )
    assert 0.360 + left_offset < text_right
    assert 0.345 + left_offset < text_right
    assert drawing.ISO_CENTER[0] + left_offset >= text_right
    assert drawing.ISO_CENTER[0] + right_offset <= drawing.SHEET_INNER_BORDER[2]
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
    shaft_upper, shaft_lower = crankshaft_spec.PINION_SEAT_DIA_BAND
    assert spec.BORE_DIA == crankshaft_spec.PINION_SEAT_DIA
    assert spec.BORE_DIA_BAND == (
        pytest.approx(shaft_lower + high),
        pytest.approx(shaft_upper + low),
    )
    bore_upper, bore_lower = spec.BORE_DIA_BAND
    minimum = bore_lower - shaft_upper
    maximum = bore_upper - shaft_lower
    assert (minimum, maximum) == (pytest.approx(low), pytest.approx(high))


def test_tip_diameter_band_is_carried_by_the_fixed_centre_mesh() -> None:
    # Tip enlargement consumes radial room even with no adjustable fit-up.
    import crank_mesh_stack

    assert spec.OUTSIDE_DIA_TOLERANCE_MM == 0.10
    assert spec.DRAWING_PRECISION_BY_NAME["OutsideDia"] == 2
    assert "OutsideDia" in spec.DRAWING_DIMENSIONS["BossProfile"]
    assert spec.TIP_CLEARANCE_MM == pytest.approx(0.152, abs=0.001)
    assert crank_mesh_stack.TIP_ROOT_BAND_RADIAL >= spec.OUTSIDE_DIA_TOLERANCE_MM / 2.0
    assert crank_mesh_stack.TIGHT_BACKLASH_MM > 0.0
    # The face width is the one free length: one place, so the title block's
    # .X grade is the band it claims, and nothing contradicts it.
    assert spec.DRAWING_PRECISION["GearBlank"]["FaceWidth"] == 1


def test_callouts_add_only_what_the_number_cannot_carry() -> None:
    # The native bore limits govern. The fit pointer identifies the mate,
    # publishes its shaft limits and states the resulting clearance, so the
    # shop can verify that both statements are the same acceptance criterion.
    low, high = spec.BORE_DIAMETRAL_CLEARANCE
    shaft_upper, shaft_lower = crankshaft_spec.PINION_SEAT_DIA_BAND
    assert drawing.DIMENSION_CALLOUTS == {
        "BoreDia": spec.BORE_PROCESS_CALLOUT,
    }
    assert spec.BORE_PROCESS_CALLOUT == "REAM THRU"
    assert spec.BORE_FIT_CALLOUT == "\n".join(
        (
            "BORE LIMITS GOVERN",
            f"MATE SHAFT {spec.CRANKSHAFT_NUMBER}",
            f"(\N{DIAMETER SIGN}{crankshaft_spec.PINION_SEAT_DIA:.3f} "
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
    assert spec.DIAMETRAL_PITCH == pytest.approx(part.DP)
    assert spec.PRESSURE_ANGLE_DEG == pytest.approx(part.PA_DEG)
    assert spec.TEETH == part.TEETH
    assert spec.PITCH_DIA == pytest.approx(spec.TEETH * spec.MODULE_MM)
    assert spec.WHOLE_DEPTH == pytest.approx(2.157 * spec.MODULE_MM)
    assert spec.TRANSVERSE_CIRCULAR_TOOTH_THICKNESS == pytest.approx(
        math.pi * spec.MODULE_MM / 2.0
    )

    # The pinion must not consume the discrete voxel/phase study's unverified
    # margin: it checks nominal 0.150 mm tooth thinning and samples 0.100 mm
    # only at the nominal c2c/helix/shaft/offset/bore stack. Keep the maximum
    # pinion tooth nominal and reuse MHA-021's established 0.020 mm one-sided
    # tooth-control capability. MHA-021 is cut normal-defined by this gear's
    # own cutter (#906), so its normal pressure angle IS the cutter's; convert
    # its normal-span lower limit with it.
    normal_pressure_angle_rad = math.radians(mate.CUTTER_PRESSURE_ANGLE_DEG)
    assert math.tan(normal_pressure_angle_rad) == pytest.approx(
        math.tan(math.radians(mate.PRESSURE_ANGLE_DEG))
        * math.cos(math.radians(mate.HELIX_ANGLE_DEG))
    )
    mate_span_scale = math.cos(math.radians(mate.HELIX_ANGLE_DEG)) * math.cos(
        normal_pressure_angle_rad
    )
    mate_extra_thinning = 0.020 / mate_span_scale
    pair_minimum = mate.BACKLASH_MM - spec.TOOTH_THICKNESS_UPPER_DEVIATION
    pair_maximum = (
        mate.BACKLASH_MM
        - spec.TOOTH_THICKNESS_LOWER_DEVIATION
        + mate_extra_thinning
    )
    assert pair_minimum == pytest.approx(0.150)
    assert pair_maximum == pytest.approx(0.191120, abs=1e-6)


def test_notes_carry_the_tooth_edge_override_and_the_boss_wall_fact() -> None:
    lines = spec.DRAWING_NOTES.split("\n")
    # The gear-data table already defines the nonstandard tooth system. One
    # note overrides the title block's destructive edge break; the other
    # states the option-C thin boss wall as a plain fact from the spec's own
    # worst case, rounded down. The policy requires the sheet to state its
    # named exception (Codex #857 P2), but exception and ruling labels never
    # print (fleet ruling, 2026-09-26); the policy row keeps the provenance.
    assert spec.TOOTH_EDGE_NOTE in lines
    wall = f"{math.floor(spec.BOSS_WALL_WORST * 100.0) / 100.0:.2f}"
    assert wall == "1.67"
    assert any(line.startswith("BOSS WALL") and f"{wall} MIN" in line for line in lines)
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
    row = next(
        line for line in policy.splitlines()
        if line.startswith("| MHA-025 crank pinion boss |")
    )
    assert f"wall {math.floor(spec.BOSS_WALL_WORST * 1000.0) / 1000.0:.3f}" in row
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
        "MHA-021",
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

    config = _config.parts("crank-pinion")
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
    import build_drive_train_assembly as bdt

    printed = float(str(_config.title_block("linear_1pl")["display"]).lstrip("±"))
    assert spec.OVERALL_LENGTH_GRADE_MM == pytest.approx(printed)
    assert spec.DRAWING_PRECISION["BossProfile"]["OverallLength"] == spec.OVERALL_LENGTH_PLACES
    assert spec.DRAWING_PRECISION["GearBlank"]["FaceWidth"] == spec.FACE_WIDTH_PLACES
    # Both lengths print exactly, so no rounded nominal eats the margin.
    assert spec.OVERALL_LENGTH == round(spec.OVERALL_LENGTH, spec.OVERALL_LENGTH_PLACES)
    assert spec.SHAFT_END_RECESS_MIN <= bdt.PINION_RECESS_NOMINAL <= spec.SHAFT_END_RECESS_MAX
    assert sum(bdt.PINION_PIN_EDGE_STACK.values()) >= spec.PIN_EDGE_MIN_WORST
    assert crankshaft_spec._SHORTER_PIN_EDGE_WORST < spec.PIN_EDGE_MIN_WORST
    assert spec.PIN_AXIAL_LIGAMENT_WORST >= spec.PIN_AXIAL_LIGAMENT_FLOOR_MM
    # The seat feeler is directly against the restored boss north face.
    assert spec.SEAT_FEELER_MM == pytest.approx(0.25)
    concentric = bdt.PINION_T120_CONCENTRIC
    assert concentric["shoulder air"] >= bdt.T120_PINION_AIR_FLOOR
    assert concentric["turned band radial"] >= bdt.T120_TURNED_BAND_RADIAL_FLOOR
    assert bdt.CRANK_ROW_ENGAGEMENT_FRACTION >= bdt.CRANK_ROW_ENGAGEMENT_FLOOR
    assert sum(bdt.PINION_RECESS_STACK.values()) >= spec.SHAFT_END_RECESS_MIN_WORST
    # Codex P2 on #892: 4d4e038e3 (recess 1.02, pinion 24.615 printed 24.6,
    # shaft 136.6345 printed 136.6) passed only against the inch grade 0.762;
    # at the printed +/-0.8 and printed nominals its recess is 0.240.
    shipped = bdt.pinion_recess_stack(1.02, 136.6345, 24.615)
    assert shipped["pinion overall length"] == pytest.approx(-0.815)
    assert shipped["shaft length"] == pytest.approx(0.0345)
    assert sum(shipped.values()) == pytest.approx(0.2395, abs=1e-4)
    assert sum(shipped.values()) < spec.SHAFT_END_RECESS_MIN_WORST
    assert 1.02 - 0.03 * 25.4 >= spec.SHAFT_END_RECESS_MIN_WORST
    # The ruled g = 5.935 grew the boss and the shaft equally, keeping the old
    # 0.32 recess: at the printed row the shaft end then stands proud.
    equal_growth_recess = 113.039505572 + 17.28 - 130.0
    assert sum(bdt.pinion_recess_stack(equal_growth_recess, 130.0, 17.28).values()) < 0.25


def test_boss_wall_is_the_ruled_option_c_exception() -> None:
    # USER RULING 2026-09-25 (MHA-025 boss option C): the boss stays at the
    # tooth root; its worst wall at the printed row over the bore's upper
    # limit is under the 2.0 target and held above the 1.5 floor.
    bore_lower, bore_upper = spec.deviations(spec.BORE_DIA_BAND)
    printed_boss = round(spec.BOSS_DIA, spec.BOSS_DIA_PLACES)
    worst = (printed_boss - 0.8 - (spec.BORE_DIA + bore_upper)) / 2.0
    assert spec.BOSS_DIA == pytest.approx(spec.ROOT_DIA)
    assert spec.BOSS_WALL_WORST == pytest.approx(worst) == pytest.approx(1.6725, abs=1e-3)
    assert spec.BOSS_WALL_FLOOR_MM <= spec.BOSS_WALL_WORST < 2.0
    assert spec.DRAWING_PRECISION["BossProfile"]["BossDia"] == spec.BOSS_DIA_PLACES
    assert "USER RULING 2026-09-25, MHA-025 boss option C" in Path(spec.__file__).read_text(
        encoding="utf-8"
    )



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
    # c'' variant B (user ruling 2026-09-30), print-worst at both end-play
    # extremes and every cone-stack float, T120 and the crank on their
    # nominal axes: shoulder air, turned-band radial and the row (stub teeth
    # counted, reading (ii)) each hold their floor, and each fails when its
    # own geometry is taken away.
    import build_drive_train_assembly as bdt

    def nominal_axes(**geometry) -> dict[str, float]:
        return bdt.pinion_t120_clearances(pose_radial=0.0, pose_axial=0.0, **geometry)

    clear = nominal_axes()
    assert clear == bdt.PINION_T120_CONCENTRIC
    assert clear["shoulder air"] >= bdt.T120_PINION_AIR_FLOOR
    assert clear["turned band radial"] >= bdt.T120_TURNED_BAND_RADIAL_FLOOR
    # Each corner's own row width (Codex P2 on #1154).
    assert bdt.CRANK_ROW_ENGAGEMENT_UNFLOATED == pytest.approx(0.9726, abs=2e-3)
    assert bdt.CRANK_ROW_ENGAGEMENT_FRACTION == pytest.approx(0.8620, abs=2e-3)
    # Turned to the tip-circle row's +0.60, the band reaches T120.
    oversize = nominal_axes(turned_dia=spec.TURNED_DIA + 0.60)
    assert oversize["turned band radial"] < bdt.T120_TURNED_BAND_RADIAL_FLOOR
    # A shoulder 1.0 longer, or no turned band at all, runs into T120.
    longer = nominal_axes(shoulder_length=spec.SHOULDER_LENGTH + 1.0)
    assert longer["shoulder air"] < bdt.T120_PINION_AIR_FLOOR
    no_band = nominal_axes(shoulder_length=None)
    assert no_band["shoulder air"] < bdt.T120_PINION_AIR_FLOOR
    # Grown only 1.4, the floated row drops under 85%.
    short = bdt.crank_row_engagement(
        9.5 + 1.4, bdt._PINION_FACE_BAND, bdt.CONE_FLOAT_NORTH
    )
    assert short < bdt.CRANK_ROW_ENGAGEMENT_FLOOR


def test_t120_radial_carries_every_fit_offset_and_axis_pose() -> None:
    # Codex P1 on #1154: T120 held concentric on the nominal cone axis read
    # 0.251 radial at the old turned 16.21, but its 0.105 seat clearance
    # alone lets it sit (0.025, 0.046165) off centre, and the crank journal,
    # 16T bore, runout, cone shaft and both post bores move the pair further.
    # The budget is re-derived here from the fits, summed at print-worst.
    import build_drive_train_assembly as bdt
    import cone_line
    import cone_pivot_post_spec as post
    import crank_mesh_stack as mesh
    from gear_seat_fit import GEAR_SEAT_CLEARANCE

    codex_offset = math.hypot(0.025, 0.046165)
    assert codex_offset <= GEAR_SEAT_CLEARANCE[1] / 2.0 + 1e-6
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
    # The old band: Codex's corner alone takes it under the floor.
    assert concentric(16.21) - codex_offset < floor
    # With every offset and pose summed the printed band is under the floor,
    # at least as far as the hand budget takes it (the named exception's
    # radial figure).
    assert concentric(spec.TURNED_DIA) - budget < floor
    assert bdt.T120_TURNED_BAND_RADIAL <= concentric(spec.TURNED_DIA) - budget + 1e-9


def _t120_policy_row() -> str:
    policy = (
        Path(spec.__file__).parents[1] / "docs" / "drawing-simplicity-policy.md"
    ).read_text(encoding="utf-8")
    rows = [
        line
        for line in policy.split("\n## Named exceptions", 1)[1].splitlines()
        if line.startswith("| MHA-025") and "T120" in line.split("|")[1]
    ]
    assert len(rows) == 1
    return rows[0]


def test_t120_shortfall_is_the_named_exception_the_policy_states() -> None:
    # User ruling 2026-09-30 on Codex P1 (#1154): the band stays Ø16.21 and
    # the shoulder 8.5.  At the arithmetic worst of every fit offset and axis
    # pose the pair can close on T120 by the row's figures (worst case and
    # RSS), and the sheets state the build's figures rounded down.
    import build_drive_train_assembly as bdt

    air, radial = bdt.T120_SHOULDER_AIR, bdt.T120_TURNED_BAND_RADIAL
    assert air == pytest.approx(-0.0905, abs=5e-4)
    assert radial == pytest.approx(-0.1157, abs=5e-4)
    assert bdt.T120_SHOULDER_AIR_STATED_WORST == math.floor(air * 100.0) / 100.0
    assert (
        bdt.T120_TURNED_BAND_RADIAL_STATED_WORST == math.floor(radial * 100.0) / 100.0
    )
    rss = bdt.pinion_t120_clearances(
        pose_radial=math.hypot(*(r for r, _ in bdt.T120_POSE_TERMS.values())),
        pose_axial=math.hypot(*(a for _, a in bdt.T120_POSE_TERMS.values())),
    )
    assert rss["shoulder air"] == pytest.approx(0.1210, abs=5e-4)
    assert rss["turned band radial"] == pytest.approx(0.1052, abs=5e-4)
    # 0.02 more band or 0.1 more shoulder takes the pair past what the
    # sheets state.
    wider = bdt.pinion_t120_clearances(turned_dia=spec.TURNED_DIA + 0.02)
    assert wider["turned band radial"] < bdt.T120_TURNED_BAND_RADIAL_STATED_WORST
    longer = bdt.pinion_t120_clearances(shoulder_length=spec.SHOULDER_LENGTH + 0.1)
    assert longer["shoulder air"] < bdt.T120_SHOULDER_AIR_STATED_WORST
    # The row states the build's figures, the fit-up feeler and its limits.
    row = _t120_policy_row()
    concentric = bdt.PINION_T120_CONCENTRIC
    for figure in (
        f"air −{-air:.3f}",
        f"radial −{-radial:.3f}",
        f"−{-bdt.T120_SHOULDER_AIR_STATED_WORST:.2f} / "
        f"−{-bdt.T120_TURNED_BAND_RADIAL_STATED_WORST:.2f}",
        f"+{rss['shoulder air']:.2f} / +{rss['turned band radial']:.2f}",
        f"+{concentric['shoulder air']:.3f} / +{concentric['turned band radial']:.3f}",
        f"{spec.T120_FITUP_FEELER_MM:.2f} feeler",
        f"Ø{spec.TURNED_DIA_FITUP_MIN:.2f} MIN",
        f"{spec.SHOULDER_LENGTH_FITUP_MIN:.1f} MIN",
    ):
        assert figure in row, figure


def test_t120_shoulder_air_is_no_higher_than_a_point_between_rim_samples() -> None:
    # Codex P1 on #1154 (review 2): a 0.05-deg sampling of T120's south rim
    # read the worst shoulder air -0.0851 and passed a stated -0.09, but the
    # rim point at 94.055 deg, between two samples, lies inside the 16T's
    # reach at -0.0904.
    import build_drive_train_assembly as bdt

    shift = (
        min(bdt._CONE_BOSS_NORTH_BAND)
        + min(bdt._COLLAR_WIDTH_BAND)
        + min(bdt._GEAR64_FACE_LIMITS)
    )
    dy = min(bdt._CRANK_HEIGHT_BAND)
    theta = math.radians(94.055)
    centre = bdt.cone_station(bdt._T120_SOUTH_FACE_STATION + shift)
    offset = bdt._TIP120 * math.cos(theta)
    x = centre[0] + offset * bdt.COS_I
    y = bdt.Y_DRIVE + bdt._TIP120 * math.sin(theta)
    z = centre[2] - offset * bdt.SIN_I
    reach = (
        bdt.R16 + bdt.ADD16 + max(bdt._PINION_TIP_RADIUS_BAND) + bdt.T120_POSE_RADIAL
    )
    assert math.hypot(x - bdt.X_CRANK, y - (bdt.Y_CRANK + dy)) <= reach
    shoulder_top = (
        bdt._POST_BOSS_NORTH
        + max(bdt._BOSS_NORTH_BAND)
        + bdt.PINION_SEAT_FEELER
        + max(bdt.PINION_END_PLAY)
        + spec.SHOULDER_LENGTH
        + max(bdt._PINION_SHOULDER_BAND)
    )
    witness = z - bdt.T120_POSE_AXIAL - shoulder_top
    assert witness == pytest.approx(-0.090422, abs=2e-6)
    assert bdt.T120_SHOULDER_AIR <= witness
    assert bdt.T120_SHOULDER_AIR_STATED_WORST <= witness


def test_t120_search_never_looks_outside_the_section() -> None:
    # Codex P2 on #1154 (review 3): the search priced a point outside T120's
    # section with a finite penalty, so its objective rose to 955.6 there and
    # fell again to 157.9, and golden section's convexity no longer held.  The
    # section's interval is found first and only its points are searched,
    # its ends included; the worst case stays the same.
    import numpy as np

    import build_drive_train_assembly as bdt

    lo, hi = np.array([0.0]), np.array([10.0])

    # Inside p <= 3 the objective falls to -3 at the end; outside it is far
    # lower, low enough that any finite penalty of 100 per mm would win.
    def objective(p: np.ndarray) -> np.ndarray:
        return np.where(p <= 3.0, -p, -1000.0 + p)

    least = bdt._convex_min_where(objective, (lambda p: p - 3.0,), lo, hi)
    assert least[0] == pytest.approx(-3.0, abs=1e-9)
    nowhere = bdt._convex_min_where(objective, (lambda p: p + 1.0,), lo, hi)
    assert nowhere[0] == math.inf
    assert bdt.T120_SHOULDER_AIR == pytest.approx(-0.090474, abs=2e-6)
    assert bdt.T120_TURNED_BAND_RADIAL == pytest.approx(-0.115742, abs=2e-6)


def test_t120_fit_up_closes_and_both_sheets_state_it() -> None:
    # Either fit-up cut, taken to its limit, passes the feeler at every
    # corner of the same stack; the minimum band is an actual size.
    import build_drive_train_assembly as bdt
    import draw_drive_train_assembly as drawing
    import drive_train_steps

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
    number = drive_train_steps.step_number("crank-mesh-checked")
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
    # Codex P2 on #1154 (review 2): a check that took up only MHA-026's play
    # passed a Ø16.043 band with the cone shaft centred in the post boss; once
    # that play closed the band kept 0.018.  The check pushes MHA-025 and
    # T120 toward each other, so it reads that band as it runs.
    import build_drive_train_assembly as bdt

    feeler = spec.T120_FITUP_FEELER_MM
    up = bdt._PINION_TURNED_RADIUS_UP

    def radial(read, dia: float) -> float:
        return read(turned_dia=dia - 2.0 * up)["turned band radial"]

    def cone_centred(**geometry) -> dict[str, float]:
        return bdt.t120_fitup_reading(pushed=(spec.PINION_NUMBER,), **geometry)

    # The actual band that just passes with the cone shaft centred.
    passing = spec.TURNED_DIA + 2.0 * (radial(cone_centred, spec.TURNED_DIA) - feeler)
    assert passing == pytest.approx(16.0431, abs=1e-3)
    assert radial(cone_centred, passing) == pytest.approx(feeler, abs=1e-9)
    in_service = radial(bdt.pinion_t120_clearances, passing)
    cone_play = bdt.T120_POSE_TERMS["cone shaft float in the post boss"][0]
    assert in_service == pytest.approx(feeler - cone_play, abs=1e-9)
    # The printed check reads it at that service worst and stops the feeler.
    assert radial(bdt.t120_fitup_reading, passing) == pytest.approx(
        in_service, abs=1e-9
    )
    assert radial(bdt.t120_fitup_reading, passing) < feeler


def test_t120_turn_down_floor_keeps_the_band_in_mesh() -> None:
    # Codex P1 on #1154 (review 2): turned to the old Ø15.48 floor the band
    # has no contact at the open centres (path -0.63), yet the row still
    # counted it.  The check stops the feeler on the band only with the crank
    # low, where the 16T:64T centres close; the floor meshes there and clears
    # the feeler at every corner, and a floor that does not mesh leaves the
    # row the full-OD shoulder alone.
    import build_drive_train_assembly as bdt

    feeler = spec.T120_FITUP_FEELER_MM
    height = bdt.T120_BAND_CHECK_CRANK_HEIGHT
    low, high = bdt._CRANK_HEIGHT_BAND
    assert low < height < high

    def band_reading(crank_height: float) -> float:
        return bdt.t120_fitup_reading(crank_heights=(crank_height,))[
            "turned band radial"
        ]

    assert band_reading(height) == pytest.approx(feeler, abs=1e-9)
    assert band_reading(height + 0.01) > feeler > band_reading(height - 0.01)
    floor_path = bdt.crank_band_contact_path(spec.TURNED_DIA_FITUP_MIN, height)
    assert floor_path > 0.0
    assert bdt.CRANK_BAND_CONTACT_PATHS["fit-up floor"] == floor_path
    assert bdt.CRANK_BAND_CONTACT_PATHS["printed"] > 0.0
    # The printed floor sits inside the joint window: over the diameter that
    # loses contact at that height, under the one that clears the feeler.
    feeler_max = spec.TURNED_DIA_FITUP_MIN + 2.0 * (
        bdt.T120_FITUP_LIMIT_CLEARANCES["turned band radial"] - feeler
    )
    assert bdt.crank_band_contact_path(feeler_max, high) < 0.0
    assert bdt.crank_band_contact_path(feeler_max, height) > floor_path
    # The old floor: no contact at that height, and the row keeps only the
    # full-OD shoulder, under 85%.
    assert bdt.crank_band_contact_path(15.48, height) < 0.0
    row = bdt.crank_row_engagement(*bdt.crank_row_teeth(15.48), bdt.CONE_FLOAT_NORTH)
    assert row == pytest.approx(bdt.CRANK_ROW_FULL_DEPTH_FRACTION)
    assert row < bdt.CRANK_ROW_ENGAGEMENT_FLOOR
    assert bdt.crank_row_teeth(spec.TURNED_DIA_FITUP_MIN) == (
        spec.FACE_WIDTH,
        bdt._PINION_FACE_BAND,
    )


def _sentences(text: str) -> list[str]:
    """The sentences of sheet text, whatever its line breaks."""
    return [part for part in re.split(r"[.;]\s+|[.;]$", " ".join(text.split())) if part]


_FEATURE = re.compile(r"\b(BAND|SHOULDER)\b")
_SHORTFALL = re.compile(r"(?<![\w.])-\d+\.\d+")


def _t120_shortfalls(text: str) -> dict[str, set[float]]:
    """The negative figures each sentence naming T120 ties to the band and
    to the shoulder: each figure goes to the nearer of the two words."""
    found: dict[str, set[float]] = {"BAND": set(), "SHOULDER": set()}
    for sentence in _sentences(text):
        if "T120" not in sentence:
            continue
        words = [
            (match.span(), match.group(1)) for match in _FEATURE.finditer(sentence)
        ]
        for figure in _SHORTFALL.finditer(sentence):
            # Characters between the figure and the word, either side of it.
            gaps = [
                (max(start - figure.end(), figure.start() - end), word)
                for (start, end), word in words
            ]
            found[min(gaps)[1]].add(round(float(figure.group()), 2))
    return found


# MHA-A03's crank step, which carries the T120 check.  The part spec never
# reads the step registry (test_part_isolation), so the key lives here.
_T120_CHECK_STEP_KEY = "crank-mesh-checked"


def _crank_step() -> str:
    import draw_drive_train_assembly as drawing
    import drive_train_steps

    number = drive_train_steps.step_number(_T120_CHECK_STEP_KEY)
    step = drawing.CONE_CRANK_STEPS.split(f"\n{number}. ", 1)[1]
    return step.split(f"\n{number + 1}. ")[0]


def test_both_sheets_state_the_t120_shortfall_the_build_derives() -> None:
    # Codex P2 on #1154 (review 2): the policy has both affected sheets state
    # the shortfall and its value; the tagged emitters print the build's
    # worst-case figures, rounded down.  Codex P3 (review 3): each sheet must
    # tie each figure to its own feature, however the sentence is worded.
    import build_drive_train_assembly as bdt

    band = round(math.floor(bdt.T120_TURNED_BAND_RADIAL * 100.0) / 100.0, 2)
    shoulder = round(math.floor(bdt.T120_SHOULDER_AIR * 100.0) / 100.0, 2)
    assert band != shoulder
    for text in (spec.DRAWING_NOTES, _crank_step()):
        assert _t120_shortfalls(text) == {"BAND": {band}, "SHOULDER": {shoulder}}


def test_each_t120_cut_answers_only_its_own_failed_reading() -> None:
    # Codex P1 on #1154 (review 3): at crank +0.300 the band reads 0.1817 and
    # passes while the shoulder reads 0.0636 and fails.  A check that let
    # either failure turn the band down would cut it to Ø15.78 there, where
    # its 16T:64T contact path is -0.0667: no contact, yet the row counted it.
    import build_drive_train_assembly as bdt

    witness = bdt.t120_fitup_reading(crank_heights=(0.300,))
    assert witness["turned band radial"] == pytest.approx(0.181654, abs=2e-6)
    assert witness["shoulder air"] == pytest.approx(0.063603, abs=2e-6)
    assert bdt.t120_fitup_cuts(witness) == {"shoulder air"}
    assert bdt.crank_band_contact_path(spec.TURNED_DIA_FITUP_MIN, 0.300) < 0.0
    # Facing the shoulder alone closes that check.
    faced = bdt.t120_fitup_reading(
        crank_heights=(0.300,), shoulder_length=spec.SHOULDER_LENGTH_FITUP_MIN
    )
    assert bdt.t120_fitup_cuts(faced) == frozenset()
    # Wherever the check does call for the band, the floor keeps contact.
    low, high = bdt._CRANK_HEIGHT_BAND
    turned = [
        height
        for height in (low + (high - low) * i / 40.0 for i in range(41))
        if "turned band radial"
        in bdt.t120_fitup_cuts(bdt.t120_fitup_reading(crank_heights=(height,)))
    ]
    assert turned and max(turned) <= bdt.T120_BAND_CHECK_CRANK_HEIGHT
    assert all(
        bdt.crank_band_contact_path(spec.TURNED_DIA_FITUP_MIN, height) > 0.0
        for height in turned
    )
    # Both sheets give each cut its own condition: the turn-down floor is
    # stated with the band and its check only, the facing floor with the
    # shoulder only.  The part sheet points at the MHA-A03 T120 check, which
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
    import drive_train_steps

    assert any(
        turn_down in sentence
        and drive_train_steps.DRAWING_NUMBER in sentence
        and "T120" in sentence
        for sentence in _sentences(spec.DRAWING_NOTES)
    )
    assert not re.search(r"STEP\s+\d", spec.DRAWING_NOTES)


def test_crank_step_runs_free_only_after_the_t120_check_closes() -> None:
    # Codex P2 on #1154 (review 3): the step asked for a full revolution that
    # must never bind before the T120 check, yet the unadjusted pair may rub
    # (-0.10 / -0.12).  The seat is set and the check closed first; the
    # free-running revolution follows, then the match-drill.
    import draw_drive_train_assembly as drawing

    step = " ".join(_crank_step().split())
    seat = step.index(f"{drawing.PINION_SEAT_FEELER:.2f} OFF")
    check = step.index(f"{spec.T120_FITUP_FEELER_MM:.2f} FEELER")
    cuts = max(
        step.index(f"Ø{spec.TURNED_DIA_FITUP_MIN:.2f} MIN"),
        step.index(f"{spec.SHOULDER_LENGTH_FITUP_MIN:.1f} MIN"),
    )
    free = step.index("BIND")
    assert seat < check < cuts < free < step.index("MATCH-DRILL")


def test_both_gear_sheets_print_the_worst_contact_ratio_rounded_down() -> None:
    # User ruling 2026-09-30: the 16T:64T contact ratio is under rule 12's
    # 1.1 at the open corner, and both GEAR DATA blocks state it, never
    # claiming more than the mesh gives.
    import build_drive_train_assembly as bdt
    import crank_drive_gear_notes

    worst = bdt.CRANK_MESH_CONTACT_RATIO_WORST
    printed = crank_drive_gear_notes.WORST_CONTACT_RATIO
    assert printed == math.floor(worst * 100.0) / 100.0
    assert worst < 1.1 < bdt.CRANK_MESH_CONTACT_RATIO_NOMINAL
    assert bdt.CRANK_MESH_CONTACT_RATIO_NOMINAL == pytest.approx(1.3846, abs=1e-3)
    assert f"{printed:.2f}" in spec.GEAR_DATA
    assert f"{printed:.2f}" in crank_drive_gear_notes.GEAR_DATA
