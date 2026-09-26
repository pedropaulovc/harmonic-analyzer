"""Offline contracts for the crank-pinion drawing.

The print is recreated under ``cad/docs/drawing-simplicity-policy.md``: a
removable 16T stock pinion with a hub boss and a match-drilled retention pin
carries no datums or frames, its turned sizes and lengths are native model
dimensions whose places and bands the PART owns, the pin hole is governed by
its matched-fit feature callout, and the tooth system it cannot dimension
lives in the gear-data block.
"""

from __future__ import annotations

import math
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
    }
    assert "draw_crank_pinion.py" in PRECISION_MIGRATED_DRAWINGS
    source = _source()
    assert "set_dimension_precision" not in source
    assert "SetPrecision3" not in source
    assert "DIMENSION_PRECISION" not in source
    assert "assert_imported_precision(" in source
    assert "apply_drawing_precision(adapter, DRAWING_PRECISION)" in _build_source()


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


def test_pin_hole_is_match_drilled_to_the_named_pin() -> None:
    # Rules 2 and 6: this matched fit is governed by its named pin and fit
    # acceptance, never by the model's nominal drill diameter.
    assert spec.PIN_HOLE_SPEC.kind == "drilled_fractional"
    assert spec.PIN_HOLE_SPEC.size == "1/8"
    assert spec.PIN_DIA == pytest.approx(3.175)
    assert spec.CRANKSHAFT_NUMBER == _config.parts("crankshaft")["number"]
    assert spec.PIN_NUMBER == _config.parts("crank-pinion-pin")["number"]
    assert "DRILL" in spec.PIN_HOLE_PROCESS
    assert "1/8" not in spec.PIN_HOLE_PROCESS
    assert f"{spec.PIN_DIA:.2f}" not in spec.PIN_HOLE_PROCESS
    assert not hasattr(spec, "PIN_DIA_BAND")
    assert "fit_class" not in _config.parts("crank-pinion-pin")
    # The pinion's hole clocking is the assembly's mesh seed, asserted there.
    assert spec.PIN_CLOCKING_DEG == pytest.approx(13.783608450714796)


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


def test_the_bore_is_the_only_feature_that_earns_a_band() -> None:
    # cad/docs/tolerance-policy.md: a feature is toleranced tighter than its
    # title-block general grade only through the named chain. On this part
    # exactly one feature can cite it -- the fit over the crankshaft -- and
    # the native Right-plane dimension carrying it is the one the sheet keeps.
    assert [name for name in dir(spec) if name.endswith("_BAND")] == ["BORE_DIA_BAND"]
    assert "BoreDia" in spec.DRAWING_DIMENSIONS["BossProfile"]
    # ... and it is the only three-decimal dimension for the same reason.
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


def test_outside_diameter_stays_at_the_general_grade() -> None:
    # The tip circle is NOT an accuracy feature (tolerance-policy.md scores
    # gear runout below 0.1 %/mm and the one-sided-load bullets forbid
    # tightening a clearance for accuracy). The crossed mesh is built with
    # fits.crank_mesh's 0.25 mm of centre-distance slack ON TOP of the tooth
    # system's own tip clearance, so the general .XX grade fits inside the
    # radial room and the tips still cannot bottom.
    assert not hasattr(spec, "OUTSIDE_DIA_BAND")
    assert spec.DRAWING_PRECISION_BY_NAME["OutsideDia"] == 2
    assert spec.MESH_C2C_SLACK_MM == _config.fit("crank_mesh")["c2c_slack_mm"]
    assert spec.TIP_CLEARANCE_MM == pytest.approx(0.152, abs=0.001)
    radial_room = spec.MESH_C2C_SLACK_MM + spec.TIP_CLEARANCE_MM
    general_radial = _config.title_block("linear_2pl")["value_in"] * 25.4 / 2.0
    assert general_radial < radial_room
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


def test_notes_carry_only_the_tooth_edge_and_boss_wall_exceptions() -> None:
    lines = spec.DRAWING_NOTES.split("\n")
    # The gear-data table already defines the nonstandard tooth system. One
    # note overrides the title block's destructive edge break; the other
    # states the option-C named exception, its number from the spec's own
    # worst-case wall (drawing-simplicity-policy.md, "Named exceptions").
    assert lines == [
        "DO NOT BREAK OR CHAMFER EDGES ON TOOTH FLANKS, TIPS OR ROOTS.",
        f"BOSS WALL {spec.BOSS_WALL_WORST:.2f} MIN AT BORE.",
    ]
    assert lines[1] == "BOSS WALL 1.67 MIN AT BORE."
    assert len(lines) <= 4
    policy = (
        Path(spec.__file__).parents[1] / "docs" / "drawing-simplicity-policy.md"
    ).read_text(encoding="utf-8")
    assert "| MHA-025 crank pinion boss |" in policy
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
    # A 17.8 x 24.9 mm part on a B sheet (W15): at 4:1 the section's boss-end
    # dimensions ran into the isometric, so 3:1 is the largest scale that lays
    # out. One scale for every view means the title block's SCALE field is the
    # whole truth and no view needs a scale note.
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
    bore_x, bore_y = drawing.RIGHT_KEEP["BoreDia"]
    assert bore_x > drawing._side_x(0.0) + 0.010
    assert bore_x < drawing.ISO_CENTER[0] - half_od - 0.010
    assert bore_y == pytest.approx(drawing.RIGHT_CENTER[1])
    for name in ("FaceWidth", "OverallLength"):
        assert drawing.RIGHT_KEEP[name][1] < drawing.RIGHT_CENTER[1] - half_od, name
    assert (
        drawing.RIGHT_KEEP["FaceWidth"][1]
        > drawing.RIGHT_KEEP["OverallLength"][1]
    )
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
    # Main rulings 2026-09-25 (W15, option 1): the boss is sized so the pin keeps
    # 4.5 of shaft beyond it nominally and 2.0 in the worst case, and the shaft
    # end stays 0.25 inside the boss with every length at its PRINTED limit.
    import build_drive_train_assembly as bdt

    printed = float(str(_config.title_block("linear_1pl")["display"]).lstrip("±"))
    assert spec.OVERALL_LENGTH_GRADE_MM == pytest.approx(printed) == pytest.approx(0.8)
    assert spec.DRAWING_PRECISION["BossProfile"]["OverallLength"] == spec.OVERALL_LENGTH_PLACES
    assert spec.DRAWING_PRECISION["GearBlank"]["FaceWidth"] == spec.FACE_WIDTH_PLACES
    # Both lengths print exactly, so no rounded nominal eats the margin.
    assert spec.OVERALL_LENGTH == pytest.approx(24.9)
    assert spec.OVERALL_LENGTH == round(spec.OVERALL_LENGTH, spec.OVERALL_LENGTH_PLACES)
    assert spec.BOSS_LENGTH == pytest.approx(14.5)
    assert spec.PIN_STATION == pytest.approx(spec.FACE_WIDTH + spec.BOSS_LENGTH / 2.0)
    assert spec.PIN_STATION == pytest.approx(17.65)
    assert bdt.PINION_RECESS_NOMINAL == pytest.approx(crankshaft_spec.SHAFT_END_RECESS)
    assert spec.SHAFT_END_RECESS_MIN <= bdt.PINION_RECESS_NOMINAL <= spec.SHAFT_END_RECESS_MAX
    assert bdt.PINION_PIN_EDGE_NOMINAL_ACTUAL >= spec.PIN_EDGE_TO_SHAFT_END_NOMINAL
    edge = bdt.PINION_PIN_EDGE_STACK
    assert edge == {
        "nominal": pytest.approx(4.523, abs=1e-3),
        "shaft length": pytest.approx(-0.40),
        "seat gap": pytest.approx(-0.75),
        # The pin is laid out at the boss mid-length on the ACTUAL part, so a
        # long face and overall length (each +0.8 printed) move it north.
        "boss mid-length": pytest.approx(-0.80),
        "pin layout": pytest.approx(-0.25),
        "drill oversize": pytest.approx(-0.05),
    }
    assert sum(edge.values()) == pytest.approx(2.273, abs=1e-3)
    assert sum(edge.values()) >= spec.PIN_EDGE_MIN_WORST
    # The seat gap is a (low, high) range starting at the one feeler MHA-A03
    # sets, not a fit band.
    # #906 moved the 1.0 upper end into the spec; the value is unchanged, so
    # sourcing it there left the BDT stacks value-neutral.
    assert spec.SEAT_GAP_MAX_MM == 1.0
    assert bdt.PINION_BOSS_NORTH_GAP_RANGE == (spec.SEAT_FEELER_MM, 1.0)
    assert not hasattr(bdt, "PINION_BOSS_NORTH_GAP_BAND")
    recess = bdt.PINION_RECESS_STACK
    assert recess == {
        "nominal": pytest.approx(1.1395, abs=1e-4),
        "pinion overall length": pytest.approx(-0.80),
        "seat gap": pytest.approx(0.0),
        "shaft length": pytest.approx(0.0),
    }
    assert sum(recess.values()) >= spec.SHAFT_END_RECESS_MIN_WORST
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
    # #893: the leaf log carries both sums, since the asserts are import-time.
    build = Path(bdt.__file__).read_text(encoding="utf-8")
    assert "{_stack_text(PINION_PIN_EDGE_STACK)} >= {PINION_PIN_EDGE_MIN_WORST}" in build
    assert "{_stack_text(PINION_RECESS_STACK)} >= {PINION_RECESS_MIN_WORST}" in build


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
