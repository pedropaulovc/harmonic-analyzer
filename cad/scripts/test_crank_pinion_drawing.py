"""Offline contracts for the crank-pinion drawing.

The print is recreated under ``cad/docs/drawing-simplicity-policy.md``: a
removable 16T stock pinion carries no datums, frames or roughness symbols, its
three turned sizes are native model dimensions whose places and bands the PART
owns, and the tooth system it cannot dimension lives in the gear-data block.
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
    assert kept == marked == {"OutsideDia", "FaceWidth", "BoreDia"}
    assert set(drawing.DIMENSION_CALLOUTS) <= kept


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
    }
    assert "draw_crank_pinion.py" in PRECISION_MIGRATED_DRAWINGS
    source = _source()
    assert "set_dimension_precision" not in source
    assert "SetPrecision3" not in source
    assert "DIMENSION_PRECISION" not in source
    assert "assert_imported_precision(" in source
    assert "apply_drawing_precision(adapter, DRAWING_PRECISION)" in _build_source()


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


def test_bore_callout_states_the_process_and_how_far_it_goes() -> None:
    # Rule 7: the Ø and its limits come from the dimension; the callout adds
    # only the two facts the number cannot carry.
    assert drawing.DIMENSION_CALLOUTS == {"BoreDia": "REAM THRU"}


def test_print_carries_no_gdt_finish_or_basic_dimensions() -> None:
    # Rules 3-5: a removable stock pinion clamped to its crankshaft is not on
    # the GD&T allowlist, and nothing runs on its bore or its faces.
    source = _source()
    for helper in (
        "add_datum_feature(",
        "add_feature_control_frame(",
        "add_surface_finish(",
        "set_basic_dimension(",
        "project_part_pmi(",
    ):
        assert helper not in source, helper
    assert not hasattr(spec, "GEOMETRIC_TOLERANCES_MM")
    assert not hasattr(spec, "GEOMETRIC_CONTROLS")
    assert spec.SURFACE_FINISHES == ()
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


def test_notes_carry_one_part_specific_fact_and_never_the_title_block() -> None:
    notes = spec.DRAWING_NOTES
    # The title block orders every sharp edge broken R0.25 / 0.25 chamfer max.
    # On a 2.13 whole-depth tooth that is a quarter of the tooth, so the print
    # states the exception -- the only thing this part's notes have to say.
    assert notes == "DO NOT BREAK OR CHAMFER EDGES ON TOOTH FLANKS, TIPS OR ROOTS."
    assert "\n" not in notes
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


def test_sheet_runs_at_5_to_1_with_every_view_at_sheet_scale() -> None:
    # A 17.8 mm part on a B sheet: at the old 3:1 the three views huddled in
    # one corner. One scale for every view means the title block's SCALE field
    # is the whole truth and no view needs a scale note.
    assert drawing.SHEET_SCALE == (5.0, 1.0)
    assert drawing.VIEW_SCALE == (5, 1)
    assert _source().count("scale=VIEW_SCALE") == 3
    assert not hasattr(spec, "ISOMETRIC_VIEW_NOTE")


def test_hidden_lines_are_off_in_every_view() -> None:
    # The only internal feature is a straight reamed bore whose callout says
    # THRU: hidden edges in the side view would add ink, not facts.
    source = _source()
    assert "for view in (front, right, iso):\n        set_hidden_lines_removed" in source
    assert "set_hidden_lines_visible" not in source


def test_dimension_text_lands_clear_of_the_views_and_the_title_block() -> None:
    # Offline layout guard: every dimension is leadered or extended OUT of the
    # silhouette it measures, and nothing crosses into the title block's
    # bottom-right corner of the B sheet.
    half_od = drawing.HALF_OD
    assert half_od == pytest.approx(spec.OUTSIDE_DIA * 5 / 2000.0)
    for name, (x, y) in drawing.FRONT_KEEP.items():
        reach = math.hypot(x - drawing.FRONT_CENTER[0], y - drawing.FRONT_CENTER[1])
        assert reach > half_od + 0.010, name
    for name, (x, y) in drawing.RIGHT_KEEP.items():
        assert y < drawing.RIGHT_CENTER[1] - half_od, name
    positions = (
        *drawing.FRONT_KEEP.values(),
        *drawing.RIGHT_KEEP.values(),
        (0.016, 0.258),  # gear-data note anchor
        (0.016, 0.082),  # manufacturing-notes anchor
    )
    for x, y in positions:
        assert 0.012 < x < 0.420
        assert 0.012 < y < 0.267
        assert not (x > 0.216 and y < 0.070), (x, y)  # title-block keep-out
    # The three views march left to right without overlapping: face view, side
    # view, isometric.
    assert drawing.FRONT_CENTER[0] + half_od < drawing.RIGHT_CENTER[0] - 0.027
    assert drawing.RIGHT_CENTER[0] + 0.027 < drawing.ISO_CENTER[0] - half_od


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
