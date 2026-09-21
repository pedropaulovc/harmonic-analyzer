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
            "BossChamfer",
        }
    )
    assert set(drawing.DIMENSION_CALLOUTS) <= kept
    # Turned part (rule 7): every diameter sits beside its axial extent on the
    # side view. The tip circle and bore are native construction-reference
    # dimensions in the Right-plane boss profile, not numbers authored by the
    # drawing; the end view is left dimension-free.
    assert drawing.FRONT_KEEP == {}
    assert set(drawing.RIGHT_KEEP) == {
        "OutsideDia",
        "BoreDia",
        "BossDia",
        "FaceWidth",
        "OverallLength",
        "BossChamfer",
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
        "BossChamfer": 1,
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
    assert spec.PIN_STATION + spec.PIN_DIA / 2 < spec.OVERALL_LENGTH - spec.BOSS_CHAMFER
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
    assert spec.PIN_HOLE_PROCESS.split("\n") == [
        "MATCH DRILL AT BOSS MID-LENGTH",
        f"AT ASSY WITH CRANKSHAFT {spec.CRANKSHAFT_NUMBER}",
        f"REAM TO FIT PIN {spec.PIN_NUMBER}",
        "SEAT BY LIGHT HAND-HAMMER TAPS",
        "NOT REMOVABLE BY HAND",
        "FLUSH BOTH SIDES",
    ]
    assert spec.CRANKSHAFT_PIN_HOLE_PROCESS.split("\n") == [
        f"MATCH DRILL AT ASSY WITH CRANK PINION {spec.PINION_NUMBER}",
        "AT PINION BOSS MID-LENGTH",
        f"REAM TO FIT PIN {spec.PIN_NUMBER}",
        "SEAT BY LIGHT HAND-HAMMER TAPS",
        "NOT REMOVABLE BY HAND",
        "FLUSH BOTH SIDES",
    ]
    assert "DRILL" in spec.PIN_HOLE_PROCESS
    assert "1/8" not in spec.PIN_HOLE_PROCESS
    assert f"{spec.PIN_DIA:.2f}" not in spec.PIN_HOLE_PROCESS
    assert not hasattr(spec, "PIN_DIA_BAND")
    assert "fit_class" not in _config.parts("crank-pinion-pin")
    # The pinion's hole clocking is the assembly's mesh seed, asserted there.
    assert spec.PIN_CLOCKING_DEG == pytest.approx(13.703608450714796)


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
    shaft_upper, shaft_lower = crankshaft_spec.SHAFT_DIA_BAND
    assert spec.BORE_DIA == crankshaft_spec.SHAFT_DIA
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
    assert spec.TIP_CLEARANCE_MM == pytest.approx(0.155, abs=0.001)
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
    shaft_upper, shaft_lower = crankshaft_spec.SHAFT_DIA_BAND
    assert drawing.DIMENSION_CALLOUTS == {
        "BoreDia": spec.BORE_PROCESS_CALLOUT,
        "BossChamfer": "X 45 DEG",
    }
    assert spec.BORE_PROCESS_CALLOUT == "REAM THRU"
    assert spec.BORE_FIT_CALLOUT == "\n".join(
        (
            "BORE LIMITS GOVERN",
            f"MATE SHAFT {spec.CRANKSHAFT_NUMBER}",
            f"(\N{DIAMETER SIGN}{crankshaft_spec.SHAFT_DIA:.3f} "
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


def test_gear_data_block_is_the_tooth_system_and_nothing_else() -> None:
    data = spec.GEAR_DATA
    for field in (
        "GEAR DATA",
        "NUMBER OF TEETH",
        "DIAMETRAL PITCH",
        "MODULE (mm, REF)",
        "PRESSURE ANGLE",
        "PITCH DIAMETER (mm, REF)",
        "WHOLE DEPTH (mm, REF)",
        "CIRCULAR TOOTH THICKNESS (mm)",
        "TOOTH FORM",
        "MATES WITH",
    ):
        assert field in data, field
    assert data.count("\n") == 9  # title + 9 rows, one screenful beside the views
    assert spec.DIAMETRAL_PITCH == pytest.approx(part.DP)
    assert spec.PRESSURE_ANGLE_DEG == pytest.approx(part.PA_DEG)
    assert spec.TEETH == part.TEETH
    assert spec.PITCH_DIA == pytest.approx(spec.TEETH * spec.MODULE_MM)
    assert spec.WHOLE_DEPTH == pytest.approx(2.157 * spec.MODULE_MM)
    assert spec.TRANSVERSE_CIRCULAR_TOOTH_THICKNESS == pytest.approx(
        math.pi * spec.MODULE_MM / 2.0
    )
    # The explicit one-sided limit reuses MHA-021's established 0.020 mm
    # tooth-control capability instead of inheriting the title block's
    # +/-0.13 mm. Convert the mate's normal-span lower limit to transverse
    # thinning and prove the actual pair range. The custom crossed-mesh study
    # proves zero collision at 0.100 mm effective thinning, so the worst
    # max-thickness pair must retain the documented 0.050 mm margin.
    assert "CIRCULAR TOOTH THICKNESS (mm, REF)" not in data
    assert (
        f"CIRCULAR TOOTH THICKNESS (mm):  "
        f"{spec.TRANSVERSE_CIRCULAR_TOOTH_THICKNESS:.3f} "
        f"+{spec.TOOTH_THICKNESS_UPPER_DEVIATION:.3f}/"
        f"{spec.TOOTH_THICKNESS_LOWER_DEVIATION:.3f}"
    ) in data
    mate_span_scale = math.cos(math.radians(mate.HELIX_ANGLE_DEG)) * math.cos(
        mate.NORMAL_PRESSURE_ANGLE_RAD
    )
    mate_extra_thinning = 0.020 / mate_span_scale
    pair_minimum = (
        mate.BACKLASH_MM - spec.TOOTH_THICKNESS_UPPER_DEVIATION
    )
    pair_maximum = (
        mate.BACKLASH_MM
        - spec.TOOTH_THICKNESS_LOWER_DEVIATION
        + mate_extra_thinning
    )
    assert pair_minimum == pytest.approx(0.150)
    assert pair_maximum == pytest.approx(0.191091, abs=1e-6)
    assert pair_minimum - 0.100 == pytest.approx(0.050)
    assert "+/-" not in data
    assert "ISO 1328" not in data
    assert "BASE-TANGENT SPAN" not in data
    assert "PAIR" not in data
    assert "TORQUE" not in data
    assert "X.XX" not in data


def test_notes_carry_only_the_tooth_edge_exception() -> None:
    notes = spec.DRAWING_NOTES
    # The gear-data table already defines the nonstandard tooth system. The
    # only separate note overrides the title block's destructive edge break.
    assert notes == "DO NOT BREAK OR CHAMFER EDGES ON TOOTH FLANKS, TIPS OR ROOTS."
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


def test_sheet_runs_at_4_to_1_with_every_view_at_sheet_scale() -> None:
    # A 17.8 x 17.28 mm part on a B sheet: 4:1 is the largest scale whose
    # isometric still clears the right border. One scale for every view means
    # the title block's SCALE field is the whole truth and no view needs a
    # scale note.
    assert drawing.SHEET_SCALE == (4.0, 1.0)
    assert drawing.VIEW_SCALE == (4, 1)
    assert _source().count("scale=VIEW_SCALE") == 3
    assert not hasattr(spec, "ISOMETRIC_VIEW_NOTE")




def test_dimension_text_lands_clear_of_the_views_and_the_title_block() -> None:
    # Offline layout guard: every dimension is extended OUT of the silhouette
    # it measures, and nothing crosses into the title block's bottom-right
    # corner of the B sheet.
    half_od = drawing.HALF_OD
    assert half_od == pytest.approx(spec.OUTSIDE_DIA * 4 / 2000.0)
    assert drawing.FRONT_KEEP == {}
    half_boss = drawing.HALF_BOSS
    assert half_boss == pytest.approx(spec.BOSS_DIA * 4 / 2000.0)
    outside_x, outside_y = drawing.RIGHT_KEEP["OutsideDia"]
    assert drawing._side_x(spec.FACE_WIDTH) < outside_x < drawing._side_x(0.0)
    assert outside_y > drawing.RIGHT_CENTER[1] + half_od + 0.008
    boss_x, boss_y = drawing.RIGHT_KEEP["BossDia"]
    assert drawing.FRONT_CENTER[0] + half_od + 0.010 < boss_x
    assert boss_x < drawing._side_x(spec.OVERALL_LENGTH) - 0.010
    assert boss_y == pytest.approx(drawing.RIGHT_CENTER[1])
    bore_x, bore_y = drawing.RIGHT_KEEP["BoreDia"]
    assert bore_x > drawing._side_x(0.0) + 0.010
    assert bore_x < drawing.ISO_CENTER[0] - half_od - 0.010
    assert bore_y == pytest.approx(drawing.RIGHT_CENTER[1])
    for name in ("FaceWidth", "OverallLength"):
        assert drawing.RIGHT_KEEP[name][1] < drawing.RIGHT_CENTER[1] - half_od, name
    # The boss diameter reads on its vertical line left of the hub. The end
    # break sits separately above and nearer the actual chamfer.
    chamfer_x, chamfer_y = drawing.RIGHT_KEEP["BossChamfer"]
    assert boss_x < chamfer_x < drawing._side_x(spec.OVERALL_LENGTH)
    assert chamfer_y > drawing.RIGHT_CENTER[1] + half_boss + 0.008
    assert (
        drawing.RIGHT_KEEP["FaceWidth"][1]
        > drawing.RIGHT_KEEP["OverallLength"][1]
    )
    # The pin-hole note hangs above-right of the side view so its leader runs
    # down-left, away from the text, before landing on the hole rim.
    assert drawing.PIN_HOLE_CALLOUT[1] > drawing.RIGHT_CENTER[1] + half_od + 0.040
    assert abs(drawing.PIN_HOLE_EDGE[1] - drawing.RIGHT_CENTER[1]) == pytest.approx(
        spec.PIN_DIA * 4 / 2000.0
    )
    assert drawing.PIN_HOLE_EDGE[0] == pytest.approx(drawing._side_x(spec.PIN_STATION))
    assert drawing.PIN_HOLE_CALLOUT[0] > drawing._side_x(0.0) + 0.030
    positions = (
        *drawing.FRONT_KEEP.values(),
        *drawing.RIGHT_KEEP.values(),
        drawing.PIN_HOLE_CALLOUT,
        (0.016, 0.258),  # gear-data note anchor
        (0.016, 0.082),  # manufacturing-notes anchor
    )
    for x, y in positions:
        assert 0.012 < x < 0.420
        assert 0.012 < y < 0.267
        assert not (x > 0.216 and y < 0.070), (x, y)  # title-block keep-out
    # The three views march left to right without overlapping: face view, side
    # view (half the overall length each side of its centre), isometric.
    half_len = spec.OVERALL_LENGTH * 4 / 2000.0
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
