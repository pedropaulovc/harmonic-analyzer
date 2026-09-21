"""Offline contracts for the crank-pinion drawing.

The print is recreated under ``cad/docs/drawing-simplicity-policy.md``: a
removable 16T stock pinion with a hub boss and a match-drilled retention pin
carries no datums or frames, its turned sizes and lengths are native model
dimensions whose places and bands the PART owns, the pin hole is a native
callout carrying the match-drill statement, and the tooth system it cannot
dimension lives in the gear-data block.
"""

from __future__ import annotations

import math
from pathlib import Path

import pytest

import _config
import build_crank_pinion as part
import crank_pinion_spec as spec
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
            "PinStation",
        }
    )
    assert set(drawing.DIMENSION_CALLOUTS) <= kept
    # Turned part (rule 7): diameters on the face view, lengths from the one
    # faced end on the side view.
    assert set(drawing.FRONT_KEEP) == {"OutsideDia", "BoreDia", "BossDia"}
    assert set(drawing.RIGHT_KEEP) == {
        "FaceWidth",
        "PinStation",
        "OverallLength",
        "BossChamfer",
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
    # claims, so the model owns them.
    assert spec.DRAWING_PRECISION_BY_NAME == {
        "OutsideDia": 2,
        "FaceWidth": 1,
        "BoreDia": 3,
        "BossDia": 2,
        "OverallLength": 2,
        "BossChamfer": 1,
        "PinStation": 2,
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
    # knobs), never a value typed on the sheet.
    assert '\'"FaceWidth" + "BossLength" / 2\'' in build


def test_pin_hole_is_match_drilled_with_the_named_mate() -> None:
    # Rules 2 and 6: a matched fit names the mate by number and states the
    # acceptance, on the feature callout; the pin is the hole's own drill.
    assert spec.PIN_HOLE_SPEC.kind == "drilled_fractional"
    assert spec.PIN_HOLE_SPEC.size == "1/8"
    assert spec.PIN_DIA == pytest.approx(3.175)
    assert spec.CRANKSHAFT_NUMBER == _config.parts("crankshaft")["number"]
    assert spec.PIN_NUMBER == _config.parts("crank-pinion-pin")["number"]
    assert spec.PIN_HOLE_PROCESS.split("\n") == [
        "MATCH DRILL AT ASSY WITH",
        f"CRANKSHAFT {spec.CRANKSHAFT_NUMBER}",
        "1/8 DRILL",
    ]
    # The crankshaft's print says the same thing back, naming this pinion.
    assert spec.CRANKSHAFT_PIN_HOLE_PROCESS.split("\n") == [
        "MATCH DRILL AT ASSY WITH",
        f"CRANK PINION {_config.parts('crank-pinion')['number']}",
        "1/8 DRILL",
    ]
    source = _source()
    assert "process=PIN_HOLE_PROCESS" in source
    assert "edge_xy=PIN_HOLE_EDGE" in source
    # No fit class, no band, no three-place number anywhere near the pin: the
    # match-drilled hole IS the fit (tolerance-policy.md: not a critical chain).
    assert not hasattr(spec, "PIN_DIA_BAND")
    assert "fit_class" not in _config.parts("crank-pinion-pin")
    # The pinion's hole clocking is the assembly's mesh seed, asserted there.
    assert spec.PIN_CLOCKING_DEG == pytest.approx(13.703608450714796)


def test_the_bore_is_the_only_feature_that_earns_a_band() -> None:
    # cad/docs/tolerance-policy.md: a feature is toleranced tighter than its
    # title-block general grade only through the named chain. On this part
    # exactly one feature can cite it -- the fit over the crankshaft.
    build = _build_source()
    assert build.count("set_dimension_bilateral_tolerance(") == 1
    assert '"BoreProfile", "BoreDia", *deviations(BORE_DIA_BAND)' in build
    assert [name for name in dir(spec) if name.endswith("_BAND")] == ["BORE_DIA_BAND"]
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
    assert spec.DRAWING_PRECISION["GearBlankProfile"]["OutsideDia"] == 2
    assert spec.MESH_C2C_SLACK_MM == _config.fit("crank_mesh")["c2c_slack_mm"]
    assert spec.TIP_CLEARANCE_MM == pytest.approx(0.155, abs=0.001)
    radial_room = spec.MESH_C2C_SLACK_MM + spec.TIP_CLEARANCE_MM
    general_radial = _config.title_block("linear_2pl")["value_in"] * 25.4 / 2.0
    assert general_radial < radial_room
    # The face width is the one free length: one place, so the title block's
    # .X grade is the band it claims, and nothing contradicts it.
    assert spec.DRAWING_PRECISION["GearBlank"]["FaceWidth"] == 1


def test_callouts_add_only_what_the_number_cannot_carry() -> None:
    # Rule 7: the Ø and its limits come from the dimension; the bore's callout
    # adds the process and how far it goes, the end break's its angle.
    assert drawing.DIMENSION_CALLOUTS == {
        "BoreDia": "REAM THRU",
        "BossChamfer": "X 45 DEG",
    }


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
        "CIRCULAR TOOTH THICKNESS (mm, REF)",
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
    # Generating data only: no acceptance number lives here, so no row may
    # carry a tolerance of its own (rule 6) and no pair-commissioning protocol
    # may return.
    assert "+/-" not in data
    assert "+0" not in data
    assert "ISO 1328" not in data
    assert "BASE-TANGENT SPAN" not in data
    assert "PAIR" not in data
    assert "TORQUE" not in data
    assert "X.XX" not in data
    source = _source()
    assert 'adapter, "Gear Data"' in source
    assert 'adapter, "Manufacturing Notes"' in source


def test_notes_carry_two_part_specific_facts_and_never_the_title_block() -> None:
    notes = spec.DRAWING_NOTES
    # The title block orders every sharp edge broken R0.25 / 0.25 chamfer max.
    # On a 2.13 whole-depth tooth that is a quarter of the tooth, so the print
    # states the exception; the other line is the matched pin fit's
    # acceptance (rule 6's match-drill-at-assembly case), which names the pin
    # by number and carries no number of its own -- the callout owns the hole.
    lines = notes.split("\n")
    assert lines[0] == "DO NOT BREAK OR CHAMFER EDGES ON TOOTH FLANKS, TIPS OR ROOTS."
    assert "\n".join(lines[1:]) == spec.PIN_FIT_NOTE
    assert spec.PIN_NUMBER in spec.PIN_FIT_NOTE
    assert "LIGHT DRIVE FIT" in spec.PIN_FIT_NOTE
    assert "FLUSH" in spec.PIN_FIT_NOTE
    assert not any(
        ch.isdigit() for ch in spec.PIN_FIT_NOTE.replace(spec.PIN_NUMBER, "")
    )
    assert len(lines) <= 4  # rule 6: at most four short lines
    assert max(len(line) for line in lines) <= 66  # clear of the title block
    # Retired with the migration: general tolerances, method instructions, a
    # heat-treatment negative, a duplicate of the bore fit, and the pair
    # commissioning protocol that was not part acceptance at all.
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


def test_hidden_lines_are_off_in_every_view() -> None:
    # Rule 7: the reamed bore's callout says THRU and the pin cross-hole is a
    # standard drill fully defined by its callout, with its exit circle solid
    # on the side view where its station is dimensioned. Hidden edges would
    # add ink, not facts.
    source = _source()
    assert "for view in (front, right, iso):\n        set_hidden_lines_removed" in source
    assert "set_hidden_lines_visible" not in source


def test_dimension_text_lands_clear_of_the_views_and_the_title_block() -> None:
    # Offline layout guard: every dimension is leadered or extended OUT of the
    # silhouette it measures, and nothing crosses into the title block's
    # bottom-right corner of the B sheet.
    half_od = drawing.HALF_OD
    assert half_od == pytest.approx(spec.OUTSIDE_DIA * 4 / 2000.0)
    for name, (x, y) in drawing.FRONT_KEEP.items():
        reach = math.hypot(x - drawing.FRONT_CENTER[0], y - drawing.FRONT_CENTER[1])
        assert reach > half_od + 0.010, name
    for name, (x, y) in drawing.RIGHT_KEEP.items():
        assert y < drawing.RIGHT_CENTER[1] - half_od, name
    # The side view's three lengths are baseline-stacked from the toothed face
    # (rule 7): shortest nearest the part, overall length outermost.
    assert (
        drawing.RIGHT_KEEP["FaceWidth"][1]
        > drawing.RIGHT_KEEP["PinStation"][1]
        > drawing.RIGHT_KEEP["OverallLength"][1]
    )
    # The pin-hole callout hangs above the side view, its leader landing on
    # the hole's rim inside the boss silhouette.
    assert drawing.PIN_HOLE_CALLOUT[1] > drawing.RIGHT_CENTER[1] + half_od + 0.020
    assert abs(drawing.PIN_HOLE_EDGE[1] - drawing.RIGHT_CENTER[1]) == pytest.approx(
        spec.PIN_DIA * 4 / 2000.0
    )
    assert drawing.PIN_HOLE_EDGE[0] == pytest.approx(drawing._side_x(spec.PIN_STATION))
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
