"""Offline behavioral contracts for the cone-gear batch drawing package."""

from __future__ import annotations

import inspect
import math
import re
from pathlib import Path

import pytest
import yaml

import _config
import _drawing_leaders
import _cone_gear_geometry as geometry
import _cone_gear_readback as readback
import build_dt_cone_gear as part
import cone_land_key
import dt_cone_gear_notes as notes
import dt_cone_gear_shaft_spec
import dt_cone_gear_spec as spec
import draw_dt_cone_gear as drawing
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS
from _drawing_registry import DRAWINGS_BY_NAME
import _drawing_annotation_extent
from _layout_geometry import Box, Segment, segment_box_distance
from _pdf_ink import Glyph, PageInk, Span, Stroke


def test_required_drawing_paths_and_registry_entry() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/dt-cone-gear.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/dt-cone-gear.pdf")
    assert drawing.PNG.as_posix().endswith("/png/dt-cone-gear_drawing.png")
    assert DRAWINGS_BY_NAME["dt_cone_gear"].script == Path(drawing.__file__).resolve()


def test_every_configuration_has_one_complete_sheet_and_native_scale() -> None:
    expected_teeth = tuple(
        range(6, int(_config.machine("gear_train", "fundamental_cone_teeth")) + 1, 6)
    )
    expected_names = tuple(f"T{teeth:03d}" for teeth in expected_teeth)
    assert spec.CONFIGURATION_TEETH == expected_teeth
    assert spec.CONFIGS == tuple(zip(expected_names, expected_teeth, strict=True))
    assert drawing.GEAR_SHEET_NAMES == expected_names
    assert drawing.SHEET_NAMES == (*expected_names, notes.CUTTER_DETAIL_SHEET)
    assert set(drawing.SHEET_SCALES) == set(drawing.SHEET_NAMES)

    for teeth in expected_teeth:
        name = f"T{teeth:03d}"
        numerator, denominator = drawing.SHEET_SCALES[name]
        drawn_od = drawing.outside_dia_mm(teeth) * numerator / denominator
        # The smallest member is limited by the common configured face width;
        # every view must stay inside the existing useful-size envelope.
        assert 30.0 < drawn_od < 95.0
        assert drawing.rendered_half_od(teeth) == pytest.approx(drawn_od / 2000.0)


def test_part_and_drawing_share_the_complete_native_dimension_contract() -> None:
    assert part.DRAWING_DIMENSIONS is notes.DRAWING_DIMENSIONS
    assert drawing.DRAWING_DIMENSIONS is notes.DRAWING_DIMENSIONS
    assert part.DRAWING_PRECISION is notes.DRAWING_PRECISION
    assert part.REFERENCE_SKETCHES is notes.REFERENCE_SKETCHES
    # The print maps are the spec's with the tip diameter moved from the
    # blank's driving circle to its side-view witness (rule 11), nothing else.
    witness = notes.BLANK_DIA_REFERENCE_SKETCH
    assert notes.DRAWING_DIMENSIONS[witness] == {"BlankDia"}
    assert "BlankProfile" not in notes.DRAWING_DIMENSIONS
    assert {
        feature: names for feature, names in notes.DRAWING_DIMENSIONS.items()
        if feature != witness
    } == {
        feature: names for feature, names in spec.DRAWING_DIMENSIONS.items()
        if feature != "BlankProfile"
    }
    assert notes.DRAWING_PRECISION[witness] == spec.DRAWING_PRECISION["BlankProfile"]
    assert notes.REFERENCE_SKETCHES == (*spec.REFERENCE_SKETCHES, witness)
    marked = set().union(*notes.DRAWING_DIMENSIONS.values())
    d_bore = {"BoreCutDia", "BoreAF", "BoreFlatClock"}
    keyed_bore = {"KeyedBoreDia", "KeywayWidth", "KeywayT", "KeywayClock"}
    assert marked == {
        "BlankDia",
        "FaceWidth",
        *d_bore,
        *keyed_bore,
        "ToothThickness",
        "FloorDia",
        "WebMin",
    }
    assert spec.DRAWING_DIMENSIONS[spec.BORE_SKETCH] == d_bore
    assert spec.DRAWING_DIMENSIONS[spec.KEYED_BORE_SKETCH] == keyed_bore
    for teeth in spec.CONFIGURATION_TEETH:
        views = (
            drawing.front_keep(teeth),
            drawing.right_keep(teeth),
            drawing.bore_view_keep(teeth),
        )
        kept = [name for keep in views for name in keep]
        # Every marked dimension of the sheet's own bore prints exactly once
        # per sheet; RV-03's web MIN only on the T012 sheet it accepts.
        expected = drawing.sheet_dimension_names(teeth)
        assert sorted(kept) == sorted(expected)
        assert expected == marked - (d_bore if spec.keyed(teeth) else keyed_bore) - (
            set() if teeth == spec.WEB_REFERENCE_TEETH else {"WebMin"}
        )
        # The whole bore prints in the bore view, and only there.
        assert set(drawing.bore_view_keep(teeth)) == spec.DRAWING_DIMENSIONS[
            spec.bore_sketch(teeth)
        ]
        # Diameters on the side view beside the face width (rule 11).
        assert set(drawing.right_keep(teeth)) == {"FaceWidth", "BlankDia"}


def test_model_owns_precision_for_every_printed_dimension() -> None:
    # Decimal inch (#290): four places carry every band and narrow floor
    # window exactly on the .0001 grid; the clocks stay at one degree place.
    assert spec.DRAWING_PRECISION_BY_NAME == {
        "BlankDia": 4,
        "FaceWidth": 4,
        "BoreCutDia": 4,
        "BoreAF": 4,
        "BoreFlatClock": 1,
        "KeyedBoreDia": 4,
        "KeywayWidth": cone_land_key.KEYWAY_PLACES,
        "KeywayT": cone_land_key.KEYWAY_PLACES,
        "KeywayClock": 1,
        "ToothThickness": 4,
        "FloorDia": 4,
        "WebMin": 4,
    }
    assert "draw_dt_cone_gear.py" in PRECISION_MIGRATED_DRAWINGS


def test_tip_diameter_carries_its_own_mesh_depth_band() -> None:
    # Ordinary undersize-only blank band (user ruling 2026-10-10, cones at
    # ordinary tolerances); T006 keeps its own -.0008 band for the DT6-FORM1
    # relief, written into T006 alone.
    assert spec.BLANK_DIA_BAND == (0.0, -0.0508)
    assert spec.blank_dia_band(6) == spec.CUSTOM_SIX_BLANK_DIA_BAND == (0.0, -0.02032)
    assert all(spec.blank_dia_band(t) is spec.BLANK_DIA_BAND for t in spec.CONFIGURATION_TEETH if t != 6)
    assert spec.BLANK_DIA_BAND[0] < spec.MODULE_MM / 2.0
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert (
        'BLANK_DIA_REFERENCE_SKETCH, "BlankDia", *deviations(BLANK_DIA_BAND)' in source
    )
    assert (
        'set_dimension_prefix(adapter, BLANK_DIA_REFERENCE_SKETCH, "BlankDia", "<MOD-DIAM>")'
        in source
    )
    assert readback._BANDED_DIMENSIONS[0] == (
        notes.BLANK_DIA_REFERENCE_SKETCH, "BlankDia", spec.blank_dia_band
    )
    assert "_set_configuration_bands(adapter)" in source


def test_face_width_fills_the_seat_pitch_without_crossing_it() -> None:
    # Solid touching stack: twenty gears end to end on SEAT_PITCH centres.
    # The nominal is the seat pitch floored to 4 places, so it never prints
    # longer than the pitch; cone_gear_stack owns the stack's band.
    assert spec.FACE_WIDTH == math.floor(spec.SEAT_PITCH * 1e4) / 1e4
    assert spec.FACE_WIDTH <= spec.SEAT_PITCH < spec.FACE_WIDTH + 1e-4
    assert spec.FACE_WIDTH_BAND == (0.0254, -0.0254)
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert '"Blank", "FaceWidth", *deviations(FACE_WIDTH_BAND)' in source


def test_each_configuration_sheet_carries_its_own_drawing_number() -> None:
    number = str(_config.parts("dt-cone-gear")["number"])
    assert spec.configuration_number(number, 6) == f"{number}-T006"
    assert spec.configuration_number(number, 120) == f"{number}-T120"
    numbers = {spec.configuration_number(number, t) for t in spec.CONFIGURATION_TEETH}
    assert len(numbers) == len(spec.CONFIGURATION_TEETH)
    with pytest.raises(ValueError):
        spec.configuration_number(number, 7)
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert '"Number": configuration_number(part_number, teeth)' in source


@pytest.mark.parametrize("teeth, suffix", ((6, "T006"), (12, "T012"), (120, "T120")))
def test_two_digit_family_number_keeps_three_digit_tooth_configuration(
    teeth: int, suffix: str,
) -> None:
    assert spec.configuration_number(" mha-dt-03 ", teeth) == f"MHA-DT-03-{suffix}"


def test_bore_bands_are_the_current_derived_seat_fit_bands() -> None:
    assert spec.BORE_DIA_BAND == pytest.approx(
        (spec.BORE_BAND_FIT_UPPER, spec.BORE_BAND_LOWER)
    )
    assert spec.BORE_DIA_BAND[0] <= spec.terminal_web_bore_upper_mm()
    assert spec.BORE_DIA_BAND[0] - spec.BORE_DIA_BAND[1] >= 0.02 - 1e-9
    assert spec.BORE_AF_BAND == pytest.approx((0.02032, 0.01016))
    for teeth in spec.CONFIGURATION_TEETH:
        assert spec.bore_dia_mm(teeth) == pytest.approx(
            dt_cone_gear_shaft_spec.SECTION_DIAS[spec.land_section(teeth)]
        )
    # The keyway takes cone_land_key's bands: the milled-width row's
    # +.0020/-.0000 width and the milled-step row's +/-.0020 on T, plain
    # inch steps.
    assert cone_land_key.KEYWAY_WIDTH_BAND == (0.0508, 0.0)
    assert cone_land_key.KEYWAY_T_BAND == (0.0508, -0.0508)
    assert spec.KEYWAY_HALF_WIDTH_MM == cone_land_key.KEYWAY_WIDTH_MM / 2.0


def test_every_marked_owner_is_live_in_the_marking_configuration() -> None:
    # drawing:dt_cone_gear at 7f1dedc: BoreProfile, suppressed in T120 (the
    # configuration the part is marked and saved in) and marked with T024
    # active, imported none of its three dimensions on the T006 sheet. So the
    # D-bore stays live in every configuration, as on main, and only the keyed
    # bore is suppressed, on the D-bore configurations whose small bores it
    # cannot solve on; every marked owner is live in T120.
    d_features = {readback.BORE_CUT, spec.BORE_SKETCH}
    keyed_features = {readback.KEYED_BORE_CUT, spec.KEYED_BORE_SKETCH}
    marking = readback.MARKING_CONFIGURATION
    assert marking == f"T{max(spec.CONFIGURATION_TEETH):03d}"
    assert not set(readback.foreign_bore_features(marking)) & set(notes.DRAWING_DIMENSIONS)
    for name, teeth in spec.CONFIGS:
        foreign = set(readback.foreign_bore_features(name))
        assert foreign == (set() if spec.keyed(teeth) else keyed_features), name
        assert not foreign & d_features
        assert spec.bore_sketch(teeth) not in foreign
    assert readback.foreign_bore_features("Default") == ()
    # On the keyed configurations the live D (Ø.375, its flat on the
    # placeholder across-flat) lies inside the keyed bore's round part, which
    # both sketches take from "BoreDia": the union cut is the keyed bore.
    for teeth in spec.KEYED_TEETH:
        radius = spec.bore_dia_mm(teeth) / 2.0
        assert part.bore_af_in(teeth) * 25.4 == pytest.approx(cone_land_key.KEYSEAT_S_MM)
        assert 0.0 < cone_land_key.KEYSEAT_S_MM - radius < radius
    assert geometry.bore_area_mm2(30) == pytest.approx(
        math.pi * (spec.bore_dia_mm(30) / 2.0) ** 2 + spec.keyway_area_outside_bore_mm2(30)
    )
    # Marks, bands and places are written once, with the marking
    # configuration active and checked, never with a D-bore one.
    build = inspect.getsource(part.build)
    marks = build.index("mark_dimensions_for_drawing(")
    assert build.index("active_configuration_name(adapter) != MARKING_CONFIGURATION") < marks
    assert build.count("mark_dimensions_for_drawing(") == 1
    assert "_activate_configuration(model" not in build[marks:]
    # Dependents before parents: each cut is suppressed before its sketch.
    for features in (readback.D_BORE_FEATURES, readback.KEYED_BORE_FEATURES):
        assert features[0].endswith("Cut") and features[1].endswith("Profile")
    # Every bore feature the restriction names is authored by the build, and
    # every marked bore dimension's owner is one of them.
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "name_last_feature(adapter, BORE_SKETCH)" in source
    assert "name_last_feature(adapter, BORE_CUT)" in source
    assert "name_last_feature(adapter, KEYED_BORE_SKETCH)" in source
    assert "name_last_feature(adapter, KEYED_BORE_CUT)" in source
    for name in spec.DRAWING_DIMENSIONS[spec.KEYED_BORE_SKETCH]:
        assert f'keyed_bore.record("{name}"' in source, name
    for name in spec.DRAWING_DIMENSIONS[spec.BORE_SKETCH]:
        assert f'bore.record("{name}"' in source, name
    # The bores are restricted before any per-configuration global moves.
    build = inspect.getsource(part.build)
    assert build.index("_restrict_bores(adapter)") < build.index('name="BoreDia"')
    assert build.index("_author_keyed_bore(adapter)") < build.index("circular_pattern_feature")


def test_native_tooth_inspection_reads_the_actual_installed_cutter() -> None:
    # Ordinary +/-.003 thickness band about the cutter's standard-depth
    # thickness; T006 alone is thin-only (DT6-FORM1 relief clearance).
    assert spec.TOOTH_THICKNESS_BAND == (0.0762, -0.0762)
    assert spec.tooth_thickness_band(6) == spec.CUSTOM_SIX_TOOTH_THICKNESS_BAND == (0.0, -0.04064)
    for teeth in spec.CONFIGURATION_TEETH:
        _upper, lower = spec.tooth_thickness_band(teeth)
        profile = spec.stock_form_profile(teeth)
        assert profile.pitch_tooth_thickness_mm == pytest.approx(spec.tooth_thickness_mm(teeth))
        assert 2.0 * profile.blank_radius_mm == pytest.approx(spec.outside_dia_mm(teeth))
        assert profile.pitch_tooth_thickness_mm + lower > 0.0
        assert readback._expected_configuration_volume(teeth) == pytest.approx((
            math.pi * profile.blank_radius_mm**2
            - teeth * profile.gap_area_mm2 - geometry.bore_area_mm2(teeth)
        ) * spec.FACE_WIDTH)
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert "*deviations(TOOTH_THICKNESS_BAND)" in source
    assert "FloorDip" not in source
    assert "gear_facts(" not in source
    assert "gap_area_in_disc(" not in source

def test_each_sheet_gets_its_own_actual_cutting_recipe() -> None:
    for teeth in spec.CONFIGURATION_TEETH:
        data = notes.gear_data(teeth)
        assert data.startswith("GEAR DATA\n")
        assert f"T{teeth:03d}" in data
        assert f"{spec.DIAMETRAL_PITCH:.2f} / {spec.PRESSURE_ANGLE_DEG:.1f}\u00b0" in data
        for physical_recipe in (
            "CUTTER", "CUTTER PLUNGE FROM BLANK OD", "WHOLE DEPTH",
            "TOOTH FORM", "BACKLASH WITH MATE", "ROOT RADIAL MIN/MAX", "WEB",
            "OVER 2 PINS",
        ):
            assert physical_recipe in data, (teeth, physical_recipe)
        # ENFORCE round 1 of #971: "TOOL T" told the shop how to set the
        # cutter (rule 7); the plunge stays, a reference depth.
        assert "TOOL T" not in data
        # Stock cutters by number and range; T006's space is the last sheet.
        last = len(spec.CONFIGURATION_TEETH) + 1
        cutter = f"NOT STOCK; FORM = TOOTH SPACE, SHEET {last}" if teeth == 6 else " INVOLUTE GEAR CUTTER, "
        assert cutter in data, teeth
        assert ("RELIEF BELOW R.0603" in data) == (teeth == 6)
        assert "TIF" not in data
        assert notes.CYLINDER_MATE_NUMBER in data
        # Rule 26 (screen of f21dfcdd2ba7): no private gear phrases.
        for obsolete in (
            "CONTACT RATIO", "RANGE ONLY", "MATCH FLANKS", "LONG ADDENDUM",
            "TEMPLATE", "FINITE", "RADIAL BELOW BASE", "ABOVE-BASE", "INCLINED",
        ):
            assert obsolete not in data
        assert len(data.splitlines()) * 0.00351 <= drawing.GEAR_DATA_HEIGHT


def test_native_gap_features_are_distinct_and_preserve_real_template_topology() -> None:
    features = [name for teeth in spec.CONFIGURATION_TEETH for name in spec.tooth_features(teeth)]
    assert len(set(features)) == 3 * len(spec.CONFIGURATION_TEETH)
    assert len(spec.SIMPLIFIED_FEATURES) == 2 * len(spec.CONFIGURATION_TEETH)
    assert spec.SIMPLIFIED_FEATURES_BY_CONFIGURATION == {
        f"T{teeth:03d}": spec.tooth_features(teeth)[1:] for teeth in spec.CONFIGURATION_TEETH
    }
    for teeth in spec.CONFIGURATION_TEETH:
        profile = spec.stock_form_profile(teeth)
        core = profile.cut_order_native_segments(
            unit_scale=1.0 / spec.MM_PER_IN, clearance_radius_mm=geometry.R_CLEAR_MM
        )
        expected_entities = 8 if profile.template.root_radius_mm < profile.template.base_radius_mm else 6
        assert len(core) == expected_entities
        native = part.native_gap_segments(teeth)
        assert [row[0] for row in native] == [segment.name for segment in core]
        for (_name, x, y), segment in zip(native, core, strict=True):
            assert segment.x in x and segment.y in x
            assert segment.x in y and segment.y in y
        if teeth != 6:
            assert profile.template.reference_teeth <= teeth
            assert profile.template.reference_teeth in (12, 17, 21, 26, 35, 55)
        assert all(name.endswith(f"T{teeth:03d}") for name in spec.tooth_features(teeth))
        assert profile.contains_material(
            profile.pitch_radius_mm, 0.0, rotate_rad=math.pi / teeth
        ), f"T{teeth:03d} must seed a physical tooth on +X"
        phase = math.pi / teeth
        for (_name, x_expression, y_expression), segment in zip(native, core, strict=True):
            for t in (0.0, 0.25, 0.5, 0.75, 1.0):
                variables = {"t": t, "cos": math.cos, "sin": math.sin}
                observed = (
                    eval(x_expression, {"__builtins__": {}}, variables),
                    eval(y_expression, {"__builtins__": {}}, variables),
                )
                x, y = segment.point(t)
                expected = (
                    (math.cos(phase) * x - math.sin(phase) * y) / spec.MM_PER_IN,
                    (math.sin(phase) * x + math.cos(phase) * y) / spec.MM_PER_IN,
                )
                assert observed == pytest.approx(expected, abs=1e-12)


def test_root_envelope_is_the_actual_translated_arc_not_a_bisector_circle() -> None:
    for teeth in spec.CONFIGURATION_TEETH:
        profile = spec.stock_form_profile(teeth)
        assert spec.floor_radius_min_mm(teeth) == pytest.approx(profile.root_radius_min_mm)
        assert spec.floor_radius_max_mm(teeth) == pytest.approx(profile.root_radius_max_mm)
        minimum, maximum = spec.floor_limits_mm(teeth)
        assert minimum <= 2.0 * profile.root_radius_min_mm + 1e-9
        assert maximum >= 2.0 * profile.root_radius_max_mm - 1e-9
        inch = minimum / spec.MM_PER_IN
        assert inch == pytest.approx(round(inch, 4), abs=1e-12)
        if abs(profile.radial_translation_mm) > 1e-9:
            assert profile.root_radius_min_mm < profile.root_radius_max_mm
    assert drawing.DIMENSION_CALLOUTS["FloorDia"].splitlines()[0] == "ROOT ENVELOPE"


def test_tight_bands_name_their_mates_once_in_flagged_notes() -> None:
    """ENFORCE round 1 of #971: each tight band names its mate and fit at
    the callout (rule 4). Screen of f21dfcdd2ba7: a mate serving several
    dimensions is named once, in one numbered note those dimensions flag,
    and a callout carries at most two lines of words (rule 7). ENFORCE
    round 2: a multi-line callout above a value never prints, so every
    above-callout is one line."""
    callouts, above = drawing.DIMENSION_CALLOUTS, drawing.CALLOUTS_ABOVE
    bore_flag, teeth_flag = drawing.BORE_NOTE_FLAG, drawing.TEETH_NOTE_FLAG
    for name in ("BoreCutDia", "BoreAF", "KeyedBoreDia", "KeywayWidth", "KeywayT"):
        assert bore_flag in callouts[name].splitlines(), name
    # The clocks' ±.25° says why once, over the value (rules 4 and 7): note 1
    # states the bore's fit only, so a flag to it explained nothing.
    assert above["BoreFlatClock"] == above["KeywayClock"] == drawing.CLOCK_REASON
    assert len(drawing.CLOCK_REASON.split()) <= 6
    assert len(drawing.CLOCK_REASON) <= len(callouts["KeywayClock"])
    # A size reads from its witnesses: the keyway's T carries its flag only.
    assert callouts["KeywayT"] == bore_flag
    assert above["BlankDia"] == teeth_flag
    assert callouts["FloorDia"].splitlines() == ["ROOT ENVELOPE", teeth_flag]
    assert "MHA-DT-04" in callouts["FaceWidth"]
    assert set(above) == {"ToothThickness", "BlankDia", "BoreFlatClock", "KeywayClock"}
    assert all("\n" not in text for text in above.values())
    # The mates appear once each, in the notes; no dimension repeats them.
    for text in (*callouts.values(), *above.values()):
        assert notes.CYLINDER_MATE_NUMBER not in text, text
        assert drawing.KEY_MATE not in text, text
    for name in (
        "BoreCutDia", "BoreAF", "BoreFlatClock",
        "KeyedBoreDia", "KeywayWidth", "KeywayT", "KeywayClock",
    ):
        assert "MHA-DT-04" not in callouts[name] + above.get(name, "")
    # The round keyed bore is a fit bore: REAM is its one process word
    # (rule 7); the D-bores take none (RV-02), the keyway none.
    assert callouts["KeyedBoreDia"].splitlines()[0] == "REAM THRU"
    for name in ("BoreCutDia", "BoreAF", "KeywayWidth", "KeywayT"):
        assert "REAM" not in callouts[name] and "BROACH" not in callouts[name], name
    # Two lines of words on the thickness: its name over the value, the flag
    # under it (offset text prints the last sheet's rows on every sheet, so
    # neither carries a size).
    thickness_rows = [above["ToothThickness"], *callouts["ToothThickness"].splitlines()]
    assert thickness_rows == ["CIRCULAR TOOTH THICKNESS", teeth_flag]
    assert drawing.TOOTH_THICKNESS_ROWS == tuple(thickness_rows)
    for teeth in spec.CONFIGURATION_TEETH:
        data = notes.gear_data(teeth)
        assert f"T{teeth:03d} / {teeth}" in data
        assert f"DIAMETRAL PITCH / PRESSURE ANGLE:  {spec.DIAMETRAL_PITCH:.2f}" in data
        pitch = spec.inch_text(teeth * spec.MODULE_MM, 4)
        assert f"PITCH DIAMETER (REF):  {pitch}" in data
    # The bore diameter's rows stay as narrow as its value, clear of the
    # flat's witness on T006/T012 (r2: a 20-character row crossed it).
    assert max(map(len, callouts["BoreCutDia"].splitlines())) <= 10


def test_numbered_notes_state_the_bore_fit_from_both_parts_limits() -> None:
    """Note 1 is the bore's matched sliding fit on its MHA-DT-04 land (and,
    keyed, the MHA-DT-VN-71 key's), with the clearances the parts' printed
    limits give (REF); note 2 names the mesh and the over-pins and backlash
    acceptances."""
    import cone_shaft_land_bands as lands

    for teeth in spec.CONFIGURATION_TEETH:
        land = lands.SECTION_DIA_BANDS[spec.land_section(teeth)]
        (round_min, round_max), (second_min, second_max) = drawing.bore_clearances_mm(teeth)
        assert round_min == pytest.approx(spec.BORE_DIA_BAND[1] - land[0])
        assert round_max == pytest.approx(spec.BORE_DIA_BAND[0] - land[1])
        assert 0.0 < round_min < round_max
        text = drawing.sheet_notes(teeth)
        lines = text.splitlines()
        # The mate by name and number, and the land it fits (rule 4).
        shaft = str(_config.parts("dt-cone-gear-shaft")["title"]).upper()
        dia = f"\u00d8{spec.inch_text(spec.bore_dia_mm(teeth), 4)} LAND"
        if spec.keyed(teeth):
            # The key slides in the keyway at every printed limit.
            assert (second_min, second_max) == cone_land_key.KEYWAY_SIDE_CLEARANCE_MM
            assert 0.0 <= second_min < second_max
            assert lines[0] == (
                f"1. SLIDING FIT ON {shaft} MHA-DT-04, {dia}, AND KEY {drawing.KEY_MATE}:"
            )
            second = "KEYWAY TO KEY"
            assert "ACROSS FLAT" not in text
        else:
            assert second_min == pytest.approx(spec.BORE_AF_BAND[1] - lands.FLAT_AF_BAND[0])
            assert second_max == pytest.approx(spec.BORE_AF_BAND[0] - lands.FLAT_AF_BAND[1])
            assert 0.0 < second_min < second_max
            flat = f"{spec.inch_text(spec.bore_flat_af_mm(teeth), 4)} ACROSS FLAT"
            assert lines[0].startswith(f"1. SLIDING FIT ON {shaft} MHA-DT-04, {dia}, {flat}")
            second = "ACROSS FLAT"
            assert drawing.KEY_MATE not in text
        assert lines[2].startswith(f"2. TEETH MESH WITH {notes.CYLINDER_MATE_NUMBER}")
        # The teeth's do-not-cut rides the note flagged to them (rule 7).
        assert lines[3].endswith(notes.TOOTH_EDGE_NOTE)
        clearance = (
            f"(CLEARANCE {spec.inch_text(round_min, 4)}-{spec.inch_text(round_max, 4)} ON \u00d8, "
            f"{spec.inch_text(second_min, 4)}-{spec.inch_text(second_max, 4)} {second})"
        )
        assert clearance in text
        # The sheet's only notes, at most four lines (rule 7), top-left, above
        # the front view and its root envelope's stack, and left of Gear Data
        # (2.5 mm text: 3.51 mm a line, 1.79 mm a character).
        assert len(lines) <= 4
        x, y = drawing.NUMBERED_NOTES_POS
        top = max(
            drawing.FRONT_CENTER[1] + drawing.rendered_half_od(teeth),
            drawing.front_keep(teeth)["FloorDia"][1] + drawing.FLOOR_STACK_HALF_HEIGHT,
        )
        assert y - len(lines) * 0.00351 > top + 0.010
        assert x + max(map(len, lines)) * 0.00179 < drawing.GEAR_DATA_POS[0] - 0.005


def test_refused_rows_block_the_complete_native_family(monkeypatch: pytest.MonkeyPatch) -> None:
    visited = []

    def profile(teeth: int) -> object:
        visited.append(teeth)
        if teeth in (6, 18, 120):
            raise ValueError("finite support refused")
        return object()

    monkeypatch.setattr(part, "stock_form_profile", profile)
    with pytest.raises(RuntimeError, match="cutter-native cone family is unqualified") as caught:
        part.require_complete_stock_family()
    assert visited == list(spec.CONFIGURATION_TEETH)
    for teeth in (6, 18, 120):
        assert f"T{teeth:03d}: finite support refused" in str(caught.value)


def test_native_root_readback_measures_the_offcentre_arc(monkeypatch: pytest.MonkeyPatch) -> None:
    from stock_form_cutter import CutterTemplate, StockFormProfile

    template = CutterTemplate(12, spec.DIAMETRAL_PITCH, spec.PRESSURE_ANGLE_DEG)
    profile = StockFormProfile(12, template, template.tip_radius_mm + 0.05, 0.1)
    root = next(segment for segment in profile.native_segments(
        unit_scale=1.0, clearance_radius_mm=geometry.R_CLEAR_MM
    ) if segment.kind == "root_arc")

    z = part.FACE_WIDTH / 1000.0

    class Edge:
        def __init__(self, index: int) -> None:
            angle = (2 * index + 1) * math.pi / profile.teeth
            cosine, sine = math.cos(angle), math.sin(angle)
            self.points = []
            for t in (0.0, 0.5, 1.0):
                x, y = root.point(t)
                self.points.append((cosine * x - sine * y, sine * x + cosine * y))
            self.queries = []

        def GetCurve(self) -> object:
            return object()

        def GetCurveParams2(self) -> tuple[float, ...]:
            (x0, y0), (x1, y1) = self.points[0], self.points[-1]
            return x0 / 1000.0, y0 / 1000.0, z, x1 / 1000.0, y1 / 1000.0, z, 0.0, 1.0

        def GetClosestPointOn(self, x: float, y: float, z: float) -> tuple[float, ...]:
            self.queries.append((x, y, z))
            if x == y == 0.0:
                point = min(self.points, key=lambda point: math.hypot(*point))
            else:
                point = self.points[1]
            return point[0] / 1000.0, point[1] / 1000.0, z, 0.0, 0.0

    class Line:
        """A tooth-flank edge: it runs along the gear axis, never a root."""

        def GetCurve(self) -> object:
            return object()

        def GetCurveParams2(self) -> tuple[float, ...]:
            return 0.004, 0.0, 0.0, 0.004, 0.0, z, 0.0, 1.0

    class Face:
        def __init__(self, z_mm: float, edges: list) -> None:
            self.z, self.edges = z_mm / 1000.0, edges

        def GetBox(self) -> tuple[float, ...]:
            return -0.01, -0.01, self.z, 0.01, 0.01, self.z

        def GetEdges(self) -> list:
            return self.edges

    edges = [Edge(index) for index in range(profile.teeth)]
    flank = type("Flank", (), {"GetBox": lambda self: (-0.01, -0.01, 0.0, 0.01, 0.01, z)})()
    faces = [Face(0.0, []), flank, Face(part.FACE_WIDTH, [Line(), *edges])]
    body = type("Body", (), {"GetFaces": lambda self: faces})()
    monkeypatch.setattr(readback, "stock_form_profile", lambda _teeth: profile)
    minimum, maximum, count = readback._native_root_envelope_mm(body, teeth=profile.teeth)
    assert count == profile.teeth
    assert minimum == pytest.approx(profile.root_radius_min_mm)
    assert maximum == pytest.approx(profile.root_radius_max_mm)
    assert minimum < maximum
    assert all(len(edge.queries) == 2 for edge in edges)
    # A gap that did not cut through leaves its root off the far face.
    faces[-1].edges.pop()
    with pytest.raises(RuntimeError, match="native root arcs on the exit face"):
        readback._native_root_envelope_mm(body, teeth=profile.teeth)


def test_root_envelope_reads_the_body_and_failures_name_their_call() -> None:
    # f68549253: the reopened audit passed the IPartDoc where the reader calls
    # IBody2.GetFaces, and every configuration failed as an anonymous
    # DISP_E_MEMBERNOTFOUND.
    try:
        readback._exit_face(object())
    except AttributeError as exc:
        site = readback._failure_site(exc)
    assert '_com_invoke(body, "IBody2", "GetFaces")' in site
    assert "in _exit_face" in site


def test_custom_six_detail_reproduces_complete_finite_core_grinding_curves() -> None:
    from dataclasses import replace

    installed = spec.stock_form_profile(6)
    template = installed.template
    tool = replace(
        installed, blank_radius_mm=template.tip_radius_mm, radial_translation_mm=0.0
    )
    detail = notes.custom_cutter_detail()
    assert template.cutter_number is None
    assert template.name == notes.CUTTER_DETAIL_SHEET == "DT6-FORM1"
    assert drawing.SHEET_NAMES[-1] == notes.CUTTER_DETAIL_SHEET
    assert "CUSTOM GROUND FORM" in detail
    assert "NO UPPER CONTINUATION" in detail
    assert "ROOT ARC; DRUM-TIP TROCHOID RELIEF TO TIF; N6 WORKING INVOLUTE" in detail
    normalized = re.sub(r"\s+", "", detail)
    required = []
    for segment in tool.native_segments(
        unit_scale=1.0, clearance_radius_mm=template.tip_radius_mm + 1.0
    ):
        if segment.kind in {"root_arc", "relief", "flank"}:
            required.append(segment.kind)
            assert re.sub(r"\s+", "", segment.x) in normalized
            assert re.sub(r"\s+", "", segment.y) in normalized
    assert sorted(required) == ["flank", "flank", "relief", "relief", "root_arc"]
    assert "closing_ray" not in detail
    assert "clearance_arc" not in detail
    assert "STOCK #8" not in detail
    assert max(map(len, detail.splitlines())) <= notes.CUTTER_DETAIL_LINE_CHARS


def test_custom_six_sheet_defines_the_tooth_space_point_by_point() -> None:
    """The last sheet defines the T006 tooth space (one-sided form
    tolerance), which is DT6-FORM1's edge; the gear is accepted by sheet 1's
    note 2. ENFORCE round 1 of #971: as a tool drawing it carried the gear's
    title block and told the shop how to inspect its tool. Round 6 of the
    fan-out (rule 7): the rows sat in a 29-line free-text block; they are a
    headed table, P1-P17, with at most four note lines on the sheet."""
    profile = spec.stock_form_profile(6)
    template = profile.template
    table = drawing.form_table_rows()
    assert table[0] == ("POINT", "R", "X", "Y")
    title = drawing.form_sheet_title()
    notes_text = drawing.form_sheet_notes()
    lines = [title, *notes_text.splitlines()]
    assert len(lines) <= 4
    # It reads as the second sheet of the T006 drawing, not a part of its own.
    assert title.startswith(f"{notes.T006_NUMBER} TOOTH SPACE, INCH")
    assert "CONTINUED FROM SHEET 1" in title
    assert drawing.SHEET_NAMES[0] == "T006"
    # The band, flagged to the note naming its mate and acceptance, once.
    assert notes_text.splitlines()[-1] == (
        f"{spec.CUSTOM_SIX_FORM_TOLERANCE_NOTE}, SEE SHEET 1 NOTE {drawing.TEETH_NOTE_NUMBER}."
    )
    assert drawing.sheet_notes(6).splitlines()[2].startswith(
        f"{drawing.TEETH_NOTE_NUMBER}. TEETH MESH WITH {notes.CYLINDER_MATE_NUMBER}"
    )
    data = "\n".join([*lines, *(" ".join(row) for row in table)])
    assert notes.CYLINDER_MATE_NUMBER not in data and "BACKLASH" not in data
    assert "WIDE ONLY" not in data
    assert "(REF)" not in data
    assert "COMPARATOR" not in data and "TIF" not in data
    assert "INSPECT" not in data and "TOOL" not in data and "GRIND" not in data
    # How the points connect is labelled on DETAIL B, by zone.
    zones = [text for text, _xy, _tip in drawing.form_zone_labels()]
    assert zones == [
        "ROOT ARC R.0433, P1-P2",
        "STRAIGHT LINES P2-P12",
        "INVOLUTE, BASE R.0587, P12-P17",
    ]
    # Wide, never narrow (the one-sided band), by half the T006 thinning
    # band (0/-.0016 on thickness).
    assert spec.CUSTOM_SIX_FORM_TOLERANCE_MM == pytest.approx(0.02032)
    assert spec.CUSTOM_SIX_FORM_TOLERANCE_NOTE == "FORM TOLERANCE: X +.0008 / -.0000"
    points = spec.custom_six_form_points_mm()

    def inch(value: float) -> str:
        return spec.inch_text(value, drawing.FORM_PLACES)

    assert table[1:] == [
        (f"P{number}", inch(r), inch(x), inch(y))
        for number, (r, x, y) in enumerate(points, 1)
    ]
    root = template.root_radius_mm
    junction = template.relief_junction_radius_mm
    assert points[0] == (root, 0.0, 0.0)
    assert points[-1][0] == profile.blank_radius_mm
    # X and Y print on the .0001 in grid, rounded to the nearest.
    resolution = 0.00005 * spec.MM_PER_IN * math.sqrt(2.0)

    def model_xy(radius: float) -> tuple[float, float]:
        angle = spec.custom_six_gap_half_angle_rad(radius)
        return radius * math.sin(angle), radius * math.cos(angle) - root

    # The tip arc ends where the relief leaves the root circle; the straight
    # lines end at the junction row, and every row above it is on the involute.
    split = next(i for i, (r, _, _) in enumerate(points) if abs(r - junction) < resolution)
    relief, involute = points[1:split + 1], points[split + 1:]
    assert math.dist(relief[0][1:], model_xy(root)) < resolution
    assert math.dist(relief[-1][1:], model_xy(junction)) < resolution
    # The corner rows round outward (ceil X, floor Y) a full .0001 in step.
    assert all(r >= root - 2.0 * resolution for r, _, _ in relief)
    for radius, x, y in involute:
        assert junction < radius and (x, y) == pytest.approx(model_xy(radius), abs=resolution)
    # The straight lines never cut inside the model relief (a line point sits
    # at no smaller polar angle than the relief at its radius), and stand at
    # most 0.006 off it (the rounding of their ends aside).
    curve = [model_xy(root + (junction - root) * i / 2000) for i in range(2001)]
    inside, offset = 0.0, 0.0
    for (_, x0, y0), (_, x1, y1) in zip(relief, relief[1:]):
        for index in range(21):
            x = x0 + (x1 - x0) * index / 20
            y = y0 + (y1 - y0) * index / 20
            radius = math.hypot(x, y + root)
            distance = min(math.dist((x, y), point) for point in curve)
            offset = max(offset, distance)
            if root < radius < junction and math.atan2(x, y + root) < (
                spec.custom_six_gap_half_angle_rad(radius)
            ):
                inside = max(inside, distance)
    assert inside < resolution
    assert offset < 0.006
    # Closed-form cross-checks against the native profile: the pitch and
    # blank-OD rows are the tool's pitch thickness and the profile's tip chord.
    by_radius = {round(r, 6): x for r, x, _ in involute}
    pitch_half_gap = math.asin(by_radius[round(profile.pitch_radius_mm, 6)] / profile.pitch_radius_mm)
    thickness = profile.pitch_radius_mm * (profile.angular_pitch_rad - 2.0 * pitch_half_gap)
    assert thickness == pytest.approx(profile.pitch_tooth_thickness_mm, abs=3e-3)
    assert by_radius[round(profile.blank_radius_mm, 6)] == pytest.approx(
        profile.blank_radius_mm * math.sin(profile.tip_half_angle_rad), abs=resolution
    )
    # Relief and involute meet at the junction row.
    assert template.relief_half_angle_rad(junction) == pytest.approx(
        spec.custom_six_gap_half_angle_rad(junction + 1e-9), abs=1e-6
    )
    assert "(t)" not in data and "sin" not in data and "SOURCE" not in data
    # Every decimal prints at 4 inch places.
    for number in re.findall(r"\d*\.\d+", data):
        assert len(number.split(".")[1]) == 4, number
    # Title over the table, the table's rows, then the two notes under it,
    # all above the title block (2.5 mm text, 3.51 mm a line).
    assert drawing.FORM_TITLE_POS[1] - 0.00351 > drawing.FORM_TABLE_POS[1]
    table_bottom = drawing.FORM_TABLE_POS[1] - len(table) * drawing.FORM_TABLE_ROW_HEIGHT
    notes_x, notes_y = drawing.form_notes_pos()
    assert notes_x == drawing.FORM_TABLE_POS[0] and notes_y < table_bottom - 0.002
    assert notes_y - len(notes_text.splitlines()) * 0.00351 > 0.100
    # Every cell fits its column (1.79 mm a character at 2.5 mm).
    for row in table:
        for text, width in zip(row, drawing.FORM_TABLE_COLUMN_WIDTHS, strict=True):
            assert len(text) * 0.00179 + 0.002 < width, text


def test_over_pins_acceptance_matches_the_closed_form_involute() -> None:
    """The standard even-count over-pins formula agrees with the sampled
    model flank where that flank is the gear's own involute (T006's
    DT6-FORM1, T012's 12T template), and the thin limit reads below the
    thick one. ENFORCE round 1 of #971: every sheet carries the row, not T006
    only; the stock gears' 1.00 pin lands on the flank and stands proud. A
    stock cutter cuts its template's form, thinner up the flank than the
    gear's own involute away from the template count, so there the pins read
    up to ~0.015 under the formula and the row follows the model."""
    for teeth in spec.CONFIGURATION_TEETH:
        assert teeth % 2 == 0, teeth
        profile = spec.stock_form_profile(teeth)
        pitch_dia = 2.0 * profile.pitch_radius_mm
        alpha = math.radians(spec.PRESSURE_ANGLE_DEG)
        base_dia = pitch_dia * math.cos(alpha)
        pin = spec.over_pins_pin_dia_mm(teeth)
        assert pin == (1.1938 if teeth == 6 else 1.016)

        def involute(angle: float) -> float:
            return math.tan(angle) - angle

        target = (
            profile.pitch_tooth_thickness_mm / pitch_dia + involute(alpha)
            + pin / base_dia - math.pi / teeth
        )
        low, high = 0.0, 1.4
        for _ in range(80):
            middle = (low + high) / 2.0
            low, high = (middle, high) if involute(middle) < target else (low, middle)
        closed_form = base_dia / math.cos(low) + pin
        nominal, contact_radius, interior = spec._over_pins_mm(profile, pin)
        assert interior, teeth
        assert base_dia / 2.0 <= contact_radius < profile.blank_radius_mm, teeth
        if profile.template.cutter_number is None or profile.template.reference_teeth == teeth:
            assert nominal == pytest.approx(closed_form, abs=2e-4), teeth
        else:
            assert closed_form - 0.02 < nominal <= closed_form + 2e-4, teeth
        assert nominal / 2.0 > profile.blank_radius_mm, teeth
        minimum, maximum = spec.over_pins_limits_mm(teeth)
        assert minimum < nominal < maximum + 1e-3, teeth
        row = (
            f"OVER 2 PINS \u00d8{spec.inch_text(pin, 3)}, OPPOSITE GAPS:  "
            f"{spec.inch_text(minimum, 4)} TO {spec.inch_text(maximum, 4)}"
        )
        assert row in notes.gear_data(teeth), teeth
    minimum, maximum = spec.over_pins_limits_mm(6)
    assert maximum - minimum == pytest.approx(0.063, abs=0.002)


def test_tooth_space_sheet_plots_the_table_beside_it() -> None:
    """ENFORCE rounds 3 and 4 of #971: the cropped, rotated illustration
    showed no CL, axes or stations, and the table alone left the sheet
    bunched in a corner (rule 15). The plot draws the table's own rows, with
    CL, X axis, origin and R stations, between the table and the border. The
    sheet's T006 view only feeds the title block, hidden."""
    source = inspect.getsource(drawing.build)
    assert '"*Front", *CUTTER_SOURCE_VIEW_CENTER' in source
    assert "_hide_title_block_source(adapter, source_view)" in source
    assert "_draw_form_plot(adapter)" in source
    flank = drawing.form_plot_flank_mm()
    rows = spec.custom_six_form_points_mm()
    junction = spec.stock_form_profile(6).template.relief_junction_radius_mm
    relief = [(x, y) for radius, x, y in rows[1:] if radius <= junction + 1e-9]
    # The relief rows are the plot's vertices (straight lines row to row);
    # above the junction the plot samples the involute the rows lie on.
    assert flank[: len(relief)] == relief
    for radius, x, y in rows[1 + len(relief):]:
        half = spec.custom_six_gap_half_angle_rad(radius)
        assert (x, y) == pytest.approx(
            (radius * math.sin(half), radius * math.cos(half) - rows[0][0]), abs=1.5e-3
        )
    assert flank[-1] == pytest.approx(rows[-1][1:], abs=1.5e-3)
    # The table and its title and notes at 2.5 mm (1.79 mm a character).
    texts = [drawing.form_sheet_title(), *drawing.form_sheet_notes().splitlines()]
    table_right = max(
        drawing.FORM_TABLE_POS[0] + sum(drawing.FORM_TABLE_COLUMN_WIDTHS),
        drawing.FORM_TITLE_POS[0] + max(map(len, texts)) * 0.00179,
    )
    plotted = [drawing.form_plot_xy(side * x, y) for x, y in flank for side in (1, -1)]
    for key, reach in drawing.FORM_PLOT_STATION_REACH_MM.items():
        radius = rows[-1][0] if key == "blank" else spec.stock_form_profile(6).template.relief_junction_radius_mm
        plotted.append(drawing.form_plot_xy(*drawing.form_plot_station_mm(radius, reach)))
    boxes = []
    for text, (left, top) in drawing.form_plot_labels():
        width = max(map(len, text.splitlines())) * 0.0026
        box = (left, top - 0.0046 * len(text.splitlines()), left + width, top)
        boxes.append((text, box, box, None))
    # Point tags and zone labels at 2.5 mm, each with a leader to its point:
    # the audit's native box spans the text and the leader's landing.
    for text, xy, tip in (*drawing.form_point_tags(), *drawing.form_zone_labels()):
        boxes.append((text, _tag_text_box(text, xy), _tag_native_box(text, xy, tip), tip))
    for _text, _box, (x0, y0, x1, y1), _tip in boxes:
        plotted += [(x0, y0), (x1, y1)]
    xs, ys = zip(*plotted)
    assert min(xs) > table_right + 0.020
    assert max(xs) < 0.415
    # Above the title block (top 0.064) and below the border (0.267).
    assert min(ys) > 0.070 and max(ys) < 0.262
    # Native boxes 2 mm apart, no leader through another label's text, and
    # no text on the drawn flank.
    assert not _tag_overlaps(boxes, _TAG_CLEAR)
    flank_points = plotted[: 2 * len(flank)]
    for text, (x0, y0, x1, y1), _native, tip in boxes:
        assert not any(
            x0 - 0.001 < x < x1 + 0.001 and y0 - 0.001 < y < y1 + 0.001
            for x, y in flank_points
        ), text
        if tip is None:
            continue
        start = (min(max(tip[0], x0), x1), (y0 + y1) / 2.0)
        leader = Segment(*start, *tip)
        for other, other_box, _native_other, _ in boxes:
            if other != text:
                assert segment_box_distance(leader, Box(*other_box)) > 0.0005, (text, other)
    # Every point is tagged or inside a labelled zone's range.
    tagged = {int(text[1:]) for text, _xy, _tip in drawing.form_point_tags()}
    root_end, junction_row = drawing.form_zones()
    assert {1, root_end, junction_row, len(rows)} <= tagged
    assert junction_row == min(
        range(1, len(rows) + 1), key=lambda number: abs(rows[number - 1][0] - junction)
    )


# A DETAIL B tag's native extent as the layout audit read it (round 7 of the
# fan-out, run 20261108T032608040Z, sheet mm): the text from 0.4 mm left of
# and 0.2 mm over its top-left point, 1.8 mm a character (2.5 mm text), down
# 3.4 mm, joined with the leader's landing.
_TAG_LEFT, _TAG_TOP, _TAG_CHAR, _TAG_DEPTH = 0.0004, 0.0002, 0.0018, 0.0034
_TAG_CLEAR = 0.002


def _tag_text_box(text: str, xy: tuple[float, float]) -> tuple[float, float, float, float]:
    left, top = xy
    return (left - _TAG_LEFT, top - _TAG_DEPTH, left + len(text) * _TAG_CHAR, top + _TAG_TOP)


def _tag_native_box(
    text: str, xy: tuple[float, float], tip: tuple[float, float]
) -> tuple[float, float, float, float]:
    x0, y0, x1, y1 = _tag_text_box(text, xy)
    return (min(x0, tip[0]), min(y0, tip[1]), max(x1, tip[0]), max(y1, tip[1]))


def _tag_overlaps(boxes, clear: float) -> set[frozenset[str]]:
    """Pairs of labels whose native boxes stand under ``clear`` apart (0: the
    audit's own test, overlap)."""
    found = set()
    for index, (text, _box, native, _tip) in enumerate(boxes):
        for other, _other_box, other_native, _ in boxes[index + 1:]:
            if not (
                native[2] + clear <= other_native[0]
                or other_native[2] + clear <= native[0]
                or native[3] + clear <= other_native[1]
                or other_native[3] + clear <= native[1]
            ):
                found.add(frozenset((text, other)))
    return found


def test_tag_box_model_reproduces_the_round_7_overlaps() -> None:
    """Positive control: round 7's offsets, through the model, give the
    audit's three overlaps and boxes that cover what it measured."""
    round_7 = {
        1: ("P1 (X0 Y0)", (0.010, -0.012)),
        2: ("P2", (0.002, -0.0037)),
        12: ("P12", (-0.011, 0.005)),
        13: ("P13", (-0.010, 0.007)),
        14: ("P14", (-0.012, 0.007)),
        15: ("P15", (-0.012, 0.007)),
        16: ("P16", (-0.011, 0.007)),
        17: ("P17", (-0.011, 0.0075)),
    }
    measured_mm = {
        "P1 (X0 Y0)": (280.0, 124.6, 305.8, 140.1),
        "P2": (290.7, 132.4, 296.3, 139.3),
        "P12": (295.9, 169.4, 306.7, 174.5),
        "P13": (298.9, 173.2, 309.2, 180.1),
        "P15": (317.4, 191.3, 329.4, 198.2),
        "P16": (326.9, 196.0, 338.1, 202.9),
    }
    points = spec.custom_six_form_points_mm()
    boxes = []
    for number, (text, (dx, dy)) in round_7.items():
        _r, x, y = points[number - 1]
        tip = drawing.form_plot_xy(x, y)
        xy = (tip[0] + dx, tip[1] + dy)
        boxes.append((text, None, _tag_native_box(text, xy, tip), tip))
    by_text = {text: native for text, _box, native, _tip in boxes}
    for text, (x0, y0, x1, y1) in measured_mm.items():
        model = by_text[text]
        # The model covers the native box, at most 2.5 mm wider.
        for got, want in zip(model, (x0, y0, x1, y1)):
            assert abs(got * 1000.0 - want) < 2.5, (text, model)
        assert model[0] * 1000 <= x0 + 0.5 and model[1] * 1000 <= y0 + 0.5, text
        assert model[2] * 1000 >= x1 - 0.5 and model[3] * 1000 >= y1 - 0.5, text
    assert _tag_overlaps(boxes, 0.0) == {
        frozenset(("P1 (X0 Y0)", "P2")),
        frozenset(("P12", "P13")),
        frozenset(("P15", "P16")),
    }


def test_configuration_owned_bores_and_title_block_alloys_cover_the_family() -> None:
    registry = _config.parts("dt-cone-gear")
    assert spec.BODY_MATERIAL_SPEC == registry["material_specification"]
    assert spec.TIP_MATERIAL_SPEC == registry["material_tip_specification"]
    assert spec.TIP_MATERIAL_SPEC != spec.BODY_MATERIAL_SPEC
    # Brass and manganese bronze take no coating; the field says so rather
    # than reading as a missing value.  "Gear teeth cut; polished" (before
    # e44791855) was a method, and polishing would round the tooth edges
    # sheet note 2 forbids breaking.
    assert registry["finish"] == "AS MACHINED, UNCOATED"
    assert str(registry["finish"]).strip().upper() not in {"", "NONE", "N/A"}
    for teeth in spec.CONFIGURATION_TEETH:
        assert part.bore_dia_in(teeth) * spec.MM_PER_IN == pytest.approx(
            spec.bore_dia_mm(teeth)
        )
        expected = spec.TIP_MATERIAL_SPEC if teeth <= 24 else spec.BODY_MATERIAL_SPEC
        assert spec.material_specification(teeth) == expected


def test_notes_state_no_bore_joint_method_or_review_record() -> None:
    # drawing-guidelines.md rule 7 (notes: few, flagged, never a method): native D-bore dimensions carry its fit, and the Gear Data block
    # reports actual cutter/mesh facts separately. The part's manufacturing
    # note carries no review history or waived floors; the teeth's do-not-cut
    # moved to the note flagged to them (sheet note 2).
    expected = notes.DRAWING_NOTES.splitlines()
    assert "T-CONFIGURATION" not in notes.DRAWING_NOTES
    assert "EDGE" not in notes.DRAWING_NOTES
    assert not hasattr(notes, "ATTACHMENT")
    # The gear sheets print only their numbered notes (round 4 of the
    # fan-out: the part's QTY/sheet-21 line pointed at another part on sheets
    # 2-20 and made five note lines). Sheet 1 sends the cutter and the relief
    # to sheet 21 in GEAR DATA, and sheet 21 opens with T006's number.
    build = inspect.getsource(drawing.build)
    assert '"Manufacturing Notes"' not in build
    sheet = f"SHEET {len(spec.CONFIGURATION_TEETH) + 1}"
    assert notes.gear_data(6).count(sheet) == 2
    assert drawing.form_sheet_title().startswith(notes.T006_NUMBER)
    for teeth in spec.CONFIGURATION_TEETH:
        text = notes.drawing_notes(teeth)
        assert text.splitlines() == expected
        for review_or_method in (
            "SOLDER",
            "BRAZE",
            "LOCTITE",
            "BOND",
            "KEYWAY",
            "AT ASSEMBLY",
            "EXCEPTION",
            "BOOK FIDELITY",
            "CONTACT RATIO",
            "WEB",
        ):
            assert review_or_method not in text
        for unsupported in ("PIN", "SET SCREW", "HUB"):
            assert unsupported not in text
        for retired in ("RUNOUT", "DATUM", "+/-", "PITCH DIA="):
            assert retired not in text
    assert notes.CYLINDER_MATE_NUMBER == _config.parts("dt-cylinder-gear")["number"]
    source = Path(part.__file__).read_text(encoding="utf-8")
    assert '"Manufacturing Notes": drawing_notes(teeth)' in source


@pytest.mark.parametrize("teeth", spec.CONFIGURATION_TEETH)
def test_actual_web_prints_as_a_fact(teeth: int) -> None:
    data = notes.gear_data(teeth)
    web = notes.root_to_bore_web_min_mm(teeth)
    if spec.keyed(teeth):
        required = spec.keyway_web_required_mm(teeth)
    else:
        required = spec.WEB_EXCEPTIONS_MM.get(teeth, spec.MACHINED_WEB_TARGET_MM)
    assert web >= required - 1e-9
    printed = spec.inch_text(spec.inch_grid_mm(web, 4, math.floor), 4)
    assert f"WEB MIN (REF):  {printed}" in data


@pytest.mark.parametrize("teeth", spec.CONFIGURATION_TEETH)
def test_each_sheet_prints_the_tooth_runout_the_mesh_stack_books(teeth: int) -> None:
    import cone_set_stack

    assert (
        f"TOOTH CUTTING SETUP, ACCEPT AT SETUP:  {spec.inch_text(cone_set_stack.TOOTH_RUNOUT_TIR_MM, 3)} "
        "TIR MAX TO FINISHED BORE"
    ) in notes.gear_data(teeth)


_REVIEW_RECORD_TEXT = re.compile(
    r"RULE \d|U\d\d|EXCEPTION|BOOK FIDELITY|POLICY|RULING"
)


@pytest.mark.parametrize("teeth", spec.CONFIGURATION_TEETH)
def test_no_sheet_prints_a_review_record(teeth: int) -> None:
    # Rulings, exceptions and policy rules are provenance for the design
    # review (finding-rulings.md, code comments); a machinist cannot act on
    # them, so neither printed text block may carry one.
    for printed in (notes.drawing_notes(teeth), notes.gear_data(teeth)):
        assert not _REVIEW_RECORD_TEXT.search(printed), printed


def test_no_gdt_and_no_surface_finish() -> None:
    # ENFORCE round 1 of #971: a gear's D-bore does not run (rule 6), so
    # its Ra 1.6 went; the title block covers the rest.
    assert not hasattr(spec, "GEOMETRIC_TOLERANCES_MM")
    assert not hasattr(spec, "GEOMETRIC_CONTROLS")
    assert not hasattr(spec, "PART_DATUMS")
    assert not hasattr(spec, "SURFACE_FINISHES")
    assert not hasattr(drawing, "bore_finish_xy")
    for module in (drawing, part):
        source = Path(module.__file__).read_text(encoding="utf-8")
        assert "add_surface_finish" not in source
        assert "author_part_pmi" not in source


# The tip diameter's block (SEE NOTE 2 over the value and its band) spans
# 6.4 mm either side of its point (front-view ink, run 20261107T103503238Z);
# the face width's block tops out 10.1 mm over its point (T120 ink, run
# 20261107T121234299Z: "+.0010" at 110.9 mm, point 100.8 mm).
_BLANK_DIA_TEXT_HALF_HEIGHT = 0.0064
_FACE_WIDTH_TEXT_RISE = 0.0101


def test_every_sheet_layout_keeps_views_dimensions_and_title_block_separate() -> None:
    for teeth in spec.CONFIGURATION_TEETH:
        half_od = drawing.rendered_half_od(teeth)
        half_face = drawing.rendered_half_face_width(teeth)
        front = drawing.front_keep(teeth)
        right = drawing.right_keep(teeth)
        bore = drawing.bore_view_keep(teeth)
        for x, y in (*front.values(), *right.values(), *bore.values()):
            assert 0.012 < x < 0.420
            assert 0.012 < y < 0.267
            assert not (x > 0.216 and y < 0.070)
        assert drawing.FRONT_CENTER[0] + half_od < drawing.RIGHT_CENTER[0] - half_face
        assert drawing.RIGHT_CENTER[0] + half_face < drawing.ISO_CENTER[0] - half_od
        # The tip diameter across the side view (rule 11): its text right of
        # the face, between the arrows at the tip radius, clear of the iso
        # view, and above the face width's block.
        blank_x, blank_y = right["BlankDia"]
        blank_half = drawing.BLANK_DIA_TEXT_HALF_WIDTH
        assert blank_x - blank_half >= drawing.RIGHT_CENTER[0] + half_face + 0.003
        assert blank_x + blank_half < drawing.ISO_CENTER[0] - half_od - 0.015
        assert abs(blank_y - drawing.RIGHT_CENTER[1]) + _BLANK_DIA_TEXT_HALF_HEIGHT < half_od
        assert right["FaceWidth"][1] + _FACE_WIDTH_TEXT_RISE < (
            blank_y - _BLANK_DIA_TEXT_HALF_HEIGHT - 0.005
        )
        # Third-angle projection: the side view shares the front bore axis.
        assert drawing.RIGHT_CENTER[1] == drawing.FRONT_CENTER[1]
        # The Gear Data block clears the largest side view, and the face-width
        # dimension hangs BELOW the side view -- the native layout audit
        # missed the text collision this replaced on T084 and T108-T120.
        assert (
            drawing.GEAR_DATA_POS[1] - drawing.GEAR_DATA_HEIGHT
            > drawing.RIGHT_CENTER[1] + half_od + 0.008
        )
        assert right["FaceWidth"][1] < drawing.RIGHT_CENTER[1] - half_od - 0.008
        # The face-width text never sits on its extension lines (#834
        # machinist review, sheets 5-20): centred only where the face spans
        # the text plus a clearance each side, otherwise wholly right of the
        # right extension line and still clear of the iso view.
        text_x = right["FaceWidth"][0]
        text_half = drawing.FACE_WIDTH_TEXT_WIDTH / 2.0
        clearance = drawing.FACE_WIDTH_TEXT_CLEARANCE
        if drawing.face_width_text_inside(teeth):
            assert text_x == pytest.approx(drawing.RIGHT_CENTER[0])
            assert half_face - text_half >= clearance
        else:
            assert text_x - text_half >= drawing.RIGHT_CENTER[0] + half_face + clearance
            assert text_x + text_half < drawing.ISO_CENTER[0] - half_od - 0.005
        # The thickness line stands right of the tip circle; its text stands
        # on its own shelf further right (budgeted below).
        line_x = front["ToothThickness"][0]
        assert line_x > drawing.FRONT_CENTER[0] + half_od
        # The gap-floor limit stack (two 3-place values plus "GAP FLOOR",
        # ~17 x 11 mm) stands right of the tip circle, above the thickness
        # witness, left of the side view and below the Gear Data block.
        floor_x, floor_y = front["FloorDia"]
        assert floor_x - _FLOOR_TEXT_HALF_WIDTH > drawing.FRONT_CENTER[0] + half_od
        assert floor_x + _FLOOR_TEXT_HALF_WIDTH < drawing.RIGHT_CENTER[0] - half_face - 0.020
        # The shelf under "GAP FLOOR" keeps the fleet's arrow-to-text
        # clearance from the thickness dimension's upper arrow tail: one
        # template arrow length past the witness, which stands half the arc
        # thickness above the bore axis at sheet scale (an upper bound on the
        # chord it witnesses).
        numerator, denominator = drawing._SCALE_BY_TEETH[teeth]
        witness_y = (
            drawing.FRONT_CENTER[1]
            + spec.tooth_thickness_mm(teeth) * numerator / (denominator * 2000.0)
        )
        tail_y = witness_y + drawing.DIMENSION_ARROW_LENGTH
        shelf_y = floor_y - drawing.FLOOR_STACK_HALF_HEIGHT
        assert shelf_y - tail_y >= _drawing_leaders.ARROW_TEXT_CLEARANCE - 1e-9, teeth
        assert (
            floor_y + drawing.FLOOR_STACK_HALF_HEIGHT
            < drawing.GEAR_DATA_POS[1] - drawing.GEAR_DATA_HEIGHT
        )
        # The shelf rises only where the tail needs it: every other sheet
        # keeps the stack's usual place.
        usual = (
            drawing.FRONT_CENTER[1] + 0.6 * half_od + drawing.FLOOR_DIA_RISE
        )
        assert floor_y >= usual - 1e-12
        if floor_y > usual:
            assert shelf_y - tail_y == pytest.approx(_drawing_leaders.ARROW_TEXT_CLEARANCE)
        # The thickness text's shelf, budgeted with the block the last print
        # measured: its leader (from the line's midpoint on the bore axis to
        # the shelf's start) keeps the fleet's text air off the C of CIRCULAR
        # and the bottom row, the block tops out under the root-envelope
        # stack's shelf and ends left of the side view.
        thickness_x, thickness_y = drawing.tooth_thickness_shelf(teeth)
        assert thickness_x - line_x == pytest.approx(drawing.TOOTH_THICKNESS_TEXT_GAP)
        leader = Segment(line_x, drawing.FRONT_CENTER[1], thickness_x, thickness_y)
        for x0, y0, x1, y1 in (_THICKNESS_C_GLYPH, _THICKNESS_BOTTOM_GLYPH):
            glyph = Box(
                thickness_x + x0, thickness_y + y0, thickness_x + x1, thickness_y + y1
            )
            assert segment_box_distance(leader, glyph) >= (
                drawing.TOOTH_THICKNESS_TEXT_AIR + _THICKNESS_AIR_MARGIN
            ), teeth
        top = thickness_y + _THICKNESS_INK_HEIGHT
        assert top + 0.002 <= floor_y - _FLOOR_SHELF_DROP, teeth
        assert thickness_x + _THICKNESS_SHELF_LENGTH + 0.003 < (
            drawing.RIGHT_CENTER[0] - half_face
        ), teeth


# The thickness block as run 20261024T091056564Z printed it on every sheet,
# relative to its shelf's start (sheet metres): the shelf 64.21 mm long, the
# ink 24.66 mm tall, the C of CIRCULAR 0.25 mm in and 6.49 mm up, the bottom
# row's first glyph at least 3.0 mm in (T084's longer pitch diameter) and
# 0.9 mm up; and the root-envelope stack's shelf 10.08 mm under its anchor.
# They stay the budget's bounds now the block is a row shorter, its name on
# top and its flag, a short centred row, at the bottom: the ink is lower, the
# C stands higher and the bottom row's first glyph farther in, each farther
# from the leader that closes on the shelf's start.
_THICKNESS_SHELF_LENGTH = 0.06421
_THICKNESS_INK_HEIGHT = 0.02466
_THICKNESS_C_GLYPH = (0.00025, 0.00649, 0.00353, 0.01006)
_THICKNESS_BOTTOM_GLYPH = (0.0030, 0.0009, 0.0065, 0.0045)
_FLOOR_SHELF_DROP = 0.01008
# The budget keeps half a millimetre beyond the printed-air check, for the
# leader's half stroke and the native shelf's placement tolerance.
_THICKNESS_AIR_MARGIN = 0.0005


# Text extents in the bore view, sheet metres: the stacked diameter reaches
# 18.9 mm left and 23.5 mm right of its position with the inch seat band
# (+0.04572/+0.02540; layout audit of farm run 20261031T160216760Z, box
# [11.1, 53.5] mm about x 30.0), and the two-line title. The clock text's
# measured block is drawing.BORE_CLOCK_TEXT_HALF_WIDTH/HEIGHT.
_BORE_DIA_TEXT_LEFT_REACH = 0.0189
_BORE_DIA_TEXT_RIGHT_REACH = 0.0235
_BORE_TEXT_HALF_HEIGHT = 0.005
_BORE_TITLE_HEIGHT = 0.008
# The layout audit compares IView.GetOutline boxes, which pad the geometry:
# ~5.5 mm round an uncropped view (T084 front [54.8, 99.8, 155.2, 200.2]
# about a 44.66 mm half tip circle) and 10.1-10.75 mm past a bore view's crop
# circle (T006-T024 and T030+ sheets; 11.3 is taken as the pad), inside the
# sheet format's 12.7 mm zone band (_drawing_sheet_region.sheet_drawable_region;
# farm run 20260929T061328212Z at 70d2e52).
_FRONT_OUTLINE_PAD = 0.0056
_CROPPED_OUTLINE_PAD = 0.0113
_ZONE_MARGIN = 0.0127


def test_bore_view_enlarges_every_bore_clear_of_its_neighbours() -> None:
    ladder = [n / d for n, d in drawing.BORE_VIEW_SCALE_LADDER]
    cx, cy = drawing.BORE_VIEW_CENTER
    for teeth in spec.CONFIGURATION_TEETH:
        keyed = spec.keyed(teeth)
        dia_name, af_name = ("KeyedBoreDia", "KeywayT") if keyed else ("BoreCutDia", "BoreAF")
        clock_name = drawing.clock_dimension_name(teeth)
        assert clock_name == ("KeywayClock" if keyed else "BoreFlatClock")
        numerator, denominator = drawing._SCALE_BY_TEETH[teeth]
        sheet_ratio = numerator / denominator
        view_numerator, view_denominator = drawing.bore_view_scale(teeth)
        ratio = view_numerator / view_denominator
        bore = spec.bore_dia_mm(teeth)
        # Enlarged past the sheet, to the smallest ladder ratio that renders
        # the bore legibly, with the flat (keyway) at least 2.5 mm deep on
        # paper.
        assert ratio > sheet_ratio
        assert bore * ratio / 1000.0 >= drawing.BORE_VIEW_BORE_MIN
        assert all(
            bore * smaller / 1000.0 < drawing.BORE_VIEW_BORE_MIN
            for smaller in ladder
            if sheet_ratio < smaller < ratio
        )
        flat = spec.bore_clock_offset_mm(teeth) * ratio / 1000.0
        depth = abs(bore * ratio / 2000.0 - flat)
        assert depth >= 0.0025, teeth
        crop = drawing.bore_view_crop_radius(teeth)
        # The crop takes the whole bore, a keyway's corners included.
        assert crop > spec.bore_reach_mm(teeth) * ratio / 1000.0 >= bore * ratio / 2000.0
        # The crop circle stands inside the border and clear of the front
        # view's tip circle, and the boxes the audit compares stay apart: the
        # views overlap in x, so the bore view's box must sit under the front
        # view's on every sheet (T084 met it at y 0.066 with a 7 mm margin).
        assert cx - crop - _CROPPED_OUTLINE_PAD > _ZONE_MARGIN
        assert cy - crop - _CROPPED_OUTLINE_PAD > _ZONE_MARGIN
        half_od = drawing.rendered_half_od(teeth)
        assert math.dist((cx, cy), drawing.FRONT_CENTER) > crop + half_od + 0.010
        front_bottom = drawing.FRONT_CENTER[1] - half_od - _FRONT_OUTLINE_PAD
        assert cy + crop + _CROPPED_OUTLINE_PAD + 0.002 < front_bottom, teeth
        keep = drawing.bore_view_keep(teeth)
        for x, y in keep.values():
            assert math.dist((x, y), drawing.FRONT_CENTER) > half_od + 0.015
        dia_x, dia_y = keep[dia_name]
        assert dia_x - _BORE_DIA_TEXT_LEFT_REACH > _ZONE_MARGIN
        assert dia_y - _BORE_TEXT_HALF_HEIGHT > cy + crop - 0.003
        # The across-flat (T) text stands wholly right of the flat's
        # (keyway top's) witness, left of the title block, above the title,
        # which stays inside the border, and under the clock's text.
        af_x, af_y = keep[af_name]
        assert af_x - drawing.BORE_VIEW_AF_HALF_WIDTH > cx + flat + 0.002
        assert af_x + drawing.BORE_VIEW_AF_HALF_WIDTH < 0.216
        assert af_y < cy - crop
        title_top = drawing.bore_view_label_top(teeth)
        assert af_y - 2.0 * _BORE_TEXT_HALF_HEIGHT > title_top
        assert title_top - _BORE_TITLE_HEIGHT > _ZONE_MARGIN + 0.001
        assert af_y + 2.0 * _BORE_TEXT_HALF_HEIGHT < keep[clock_name][1] - 0.010
        # The clock text stands wholly right of the circle and clear of the
        # thickness callout's shelved block.
        clock_x, clock_y = keep[clock_name]
        # Its two-line block (measured half-extents) stands an arrow length
        # plus clearance above the axis line, where the arc's arrowhead ends
        # under the text, and clear of the crop circle.
        assert clock_y - drawing.BORE_CLOCK_TEXT_HALF_HEIGHT >= (
            cy + drawing.BORE_CLOCK_ARROW_LENGTH + _drawing_leaders.ARROW_TEXT_CLEARANCE - 1e-12
        ), teeth
        assert clock_x - drawing.BORE_CLOCK_TEXT_HALF_WIDTH >= cx + crop + 0.002 - 1e-12, teeth
        ctt_x, ctt_y = drawing.tooth_thickness_shelf(teeth)
        clock_box = (
            clock_x - drawing.BORE_CLOCK_TEXT_HALF_WIDTH,
            clock_y - drawing.BORE_CLOCK_TEXT_HALF_HEIGHT,
            clock_x + drawing.BORE_CLOCK_TEXT_HALF_WIDTH,
            clock_y + drawing.BORE_CLOCK_TEXT_HALF_HEIGHT,
        )
        ctt_box = (
            ctt_x,
            ctt_y,
            ctt_x + _THICKNESS_SHELF_LENGTH,
            ctt_y + _THICKNESS_INK_HEIGHT,
        )
        assert _drawing_annotation_extent.boxes_clear(clock_box, ctt_box), teeth
        # The clock's arc centres where the flat (keyway top) crosses the
        # axis and swings through its text, in the quadrant right of it and
        # above the axis: clear of the diameter's upper-left lane and under
        # the front view. Left in the sketch's upper-left quadrant, it
        # crossed the diameter's shoulder on every 4:1 sheet.
        vx, vy = drawing.bore_clock_vertex(teeth)
        assert (vx, vy) == pytest.approx((cx + flat, cy))
        assert clock_x > vx and clock_y > vy
        reach = math.dist((vx, vy), (clock_x, clock_y))
        assert dia_x + _BORE_DIA_TEXT_RIGHT_REACH < clock_box[0] - 0.005
        assert vy + reach + 0.003 < front_bottom, teeth
        assert drawing.bore_view_label(teeth).splitlines() == [
            "DETAIL A",
            f"SCALE {view_numerator:g} : {view_denominator:g}",
        ]
        if not keyed:
            continue
        # The keyway width's block stands right of the crop circle, under its
        # lower witness and arrow, clear of the clock's and T's blocks; its
        # witnesses stay inside the clock's arc.
        width_x, width_y = keep["KeywayWidth"]
        half_width = spec.KEYWAY_HALF_WIDTH_MM * ratio / 1000.0
        width_box = (
            width_x - drawing.KEYWAY_WIDTH_TEXT_HALF_WIDTH,
            width_y - drawing.KEYWAY_WIDTH_TEXT_HALF_HEIGHT,
            width_x + drawing.KEYWAY_WIDTH_TEXT_HALF_WIDTH,
            width_y + drawing.KEYWAY_WIDTH_TEXT_HALF_HEIGHT,
        )
        assert width_box[0] >= cx + crop + 0.002 - 1e-12
        assert width_box[3] <= cy - half_width - drawing.BORE_CLOCK_ARROW_LENGTH - (
            _drawing_leaders.ARROW_TEXT_CLEARANCE
        ) + 1e-12
        t_box = (
            af_x - drawing.BORE_VIEW_AF_HALF_WIDTH,
            af_y - 2.0 * _BORE_TEXT_HALF_HEIGHT,
            af_x + drawing.BORE_VIEW_AF_HALF_WIDTH,
            af_y + 2.0 * _BORE_TEXT_HALF_HEIGHT,
        )
        for other in (clock_box, t_box, ctt_box):
            assert _drawing_annotation_extent.boxes_clear(width_box, other), teeth
        assert math.dist((vx, vy), (width_x, vy + half_width)) < reach
        # The width's arrows stand outside its witnesses: its dimension line
        # runs a document arrow length up past the upper witness at the
        # text's x, under the clock's block. The block stands clear above
        # that line's end (it struck the O of TOOTH on every keyed sheet of
        # the C1-keyed farm review: line top 69.5 mm, block row 67.2 mm).
        line_top = cy + half_width + drawing.DIMENSION_ARROW_LENGTH
        assert clock_box[0] < width_x < clock_box[2]
        assert clock_box[1] >= line_top + drawing.KEYWAY_WIDTH_LINE_CLEARANCE - 1e-12, teeth


# The front view's +X centre-mark line as printed (sheet metres): r3, the
# template's lines with no extension; r4, T006 asked for 1.948 mm more.
_CENTRE_LINE_R3_ENDS = {6: 0.1281, 12: 0.1224, 30: 0.1268, 60: 0.1195, 120: 0.1123}
_CENTRE_LINE_R4_T006 = (1.948, 0.1437)


def _printed_centre_line_end(teeth: int, extension_mm: float) -> float:
    ratio = drawing._front_ratio(teeth)
    rim = drawing.FRONT_CENTER[0] + spec.bore_dia_mm(teeth) * ratio / 2000.0
    return rim + (drawing.CENTRE_MARK_LINE_BASE_MM + extension_mm) * ratio / 1000.0


def _centre_line_text_air(teeth: int, end_x: float) -> float:
    """Air from the +X line (rim to ``end_x`` on the bore axis) to the
    thickness block as the shelf model bounds it."""
    shelf_x, shelf_y = drawing.tooth_thickness_shelf(teeth)
    block = Box(
        shelf_x, shelf_y, shelf_x + _THICKNESS_SHELF_LENGTH, shelf_y + _THICKNESS_INK_HEIGHT
    )
    axis_y = drawing.FRONT_CENTER[1]
    return segment_box_distance(Segment(drawing.FRONT_CENTER[0], axis_y, end_x, axis_y), block)


def test_front_view_draws_the_tooth_centreline_the_clock_refers_to() -> None:
    """Machinist review of the C1-keyed sheets (rule 10): the clock's '90°
    ±.25° TO TOOTH CENTERLINE' named a line drawn nowhere. The front view's
    bore centre mark's +X line runs from the bore's rim through the phase-0
    tooth (gap bisectors rotate by pi/N, so a tooth centres on +X, the
    flat's or keyway's normal) past the tip, and stops short of the
    thickness dimension's line, whose midpoint on the axis starts the
    leader to the thickness text; the text keeps the printed-air check's
    2 mm on every sheet (r4: T006's line ran 0.81 mm under the C)."""
    # The template's lines run CENTRE_MARK_LINE_BASE_MM past the rim at each
    # sheet's scale, and an extension adds to that (r4's T006 line).
    for teeth, printed in _CENTRE_LINE_R3_ENDS.items():
        assert _printed_centre_line_end(teeth, 0.0) == pytest.approx(printed, abs=0.0003)
    extension, printed = _CENTRE_LINE_R4_T006
    assert _printed_centre_line_end(6, extension) == pytest.approx(printed, abs=0.0003)
    assert _centre_line_text_air(6, printed) < drawing.TOOTH_THICKNESS_TEXT_AIR
    for teeth in spec.CONFIGURATION_TEETH:
        arms = drawing.front_centre_mark_arms_mm(teeth)
        assert set(arms) <= {3}, teeth
        assert all(length > 0.0 for length in arms.values()), teeth
        end_x = _printed_centre_line_end(teeth, arms.get(3, 0.0))
        assert end_x == pytest.approx(drawing.front_centre_line_end_x(teeth))
        tip_x = drawing.FRONT_CENTER[0] + drawing.rendered_half_od(teeth)
        assert end_x >= tip_x + drawing.CENTRE_LINE_OVERRUN - 1e-9, teeth
        line_x = drawing.front_keep(teeth)["ToothThickness"][0]
        assert end_x <= line_x - drawing.CENTRE_LINE_DIMENSION_AIR + 1e-9, teeth
        assert _centre_line_text_air(teeth, end_x) >= (
            drawing.TOOTH_THICKNESS_TEXT_AIR + _THICKNESS_AIR_MARGIN
        ), teeth
    source = inspect.getsource(drawing.build)
    assert "arms_mm=front_centre_mark_arms_mm(teeth)" in source


# The detail letter's ink at DETAIL_LETTER_HEIGHT, half its width and height
# (sheet metres), and the air it keeps to the lines round it.
_LETTER_HALF = (0.0011, 0.00135)
_LETTER_AIR = 0.0003


def _letter_box(xy: tuple[float, float]) -> Box:
    return Box(
        xy[0] - _LETTER_HALF[0], xy[1] - _LETTER_HALF[1],
        xy[0] + _LETTER_HALF[0], xy[1] + _LETTER_HALF[1],
    )


def _corner_radii(box: Box, centre: tuple[float, float]) -> tuple[float, float]:
    """Nearest and farthest distance of ``box``'s corners from ``centre``."""
    radii = [
        math.dist(corner, centre)
        for corner in ((box.xmin, box.ymin), (box.xmin, box.ymax), (box.xmax, box.ymin), (box.xmax, box.ymax))
    ]
    return min(radii), max(radii)


def test_enlarged_views_are_lettered_with_boundaries_on_the_front_view() -> None:
    """Rule 9 (screen of f21dfcdd2ba7): the bore view is DETAIL A, its
    boundary ringing the bore on every front view; sheet 21's plot is
    DETAIL B, its boundary ringing T006's 12 o'clock tooth space. Each
    letter stands outside its boundary, clear of the lines round it."""
    for teeth in spec.CONFIGURATION_TEETH:
        details = drawing.front_details(teeth)
        assert [detail.letter for detail in details] == (["A", "B"] if teeth == 6 else ["A"])
        bore = details[0]
        centre, radius = drawing.front_detail_on_sheet(teeth, bore)
        assert centre == pytest.approx(drawing.FRONT_CENTER)
        numerator, denominator = drawing._SCALE_BY_TEETH[teeth]
        ratio = numerator / denominator
        root = spec.floor_limits_mm(teeth)[0] * ratio / 2000.0
        assert spec.bore_dia_mm(teeth) * ratio / 2000.0 < radius < root
        # The letter sits in the web, clear of the boundary, the root
        # envelope and both centre-mark arms.
        letter = _letter_box(drawing.detail_letter_xy(bore, centre, radius))
        inner, outer = _corner_radii(letter, centre)
        assert inner >= radius + _LETTER_AIR, teeth
        assert outer <= root - _LETTER_AIR, teeth
        assert letter.xmin > centre[0] + _LETTER_AIR and letter.ymax < centre[1] - _LETTER_AIR
        # T012's web dimension runs down left; the letter stands down right.
        assert abs(math.remainder(bore.letter_angle_deg - spec.WEB_REFERENCE_ANGLE_DEG, 360.0)) >= 90.0
    form = drawing.front_details(6)[1]
    a_centre, a_radius = drawing.front_detail_on_sheet(6, drawing.front_details(6)[0])
    b_centre, b_radius = drawing.front_detail_on_sheet(6, form)
    # B takes the whole 12 o'clock space (its root and both tip corners) and
    # stands clear of A's ring.
    root_mm = spec.stock_form_profile(6).template.root_radius_mm
    _radius, corner_x, corner_y = spec.custom_six_form_points_mm()[-1]
    for x_mm, y_mm in ((0.0, root_mm), (corner_x, corner_y + root_mm), (-corner_x, corner_y + root_mm)):
        assert math.dist((x_mm, y_mm), form.centre_mm) < form.radius_mm
    assert math.dist(a_centre, b_centre) > a_radius + b_radius + 0.0005
    # Its letter stands outside the tip circle, left of the root envelope's
    # block and under it.
    letter = _letter_box(drawing.detail_letter_xy(form, b_centre, b_radius))
    inner, _outer = _corner_radii(letter, b_centre)
    assert inner >= b_radius + _LETTER_AIR
    assert _corner_radii(letter, a_centre)[0] > drawing.rendered_half_od(6) + _LETTER_AIR
    floor_x, floor_y = drawing.front_keep(6)["FloorDia"]
    assert letter.xmax < floor_x - _FLOOR_TEXT_HALF_WIDTH - 0.005
    assert letter.ymax < floor_y + drawing.FLOOR_STACK_HALF_HEIGHT
    # The plot on the last sheet carries the same letter and its scale.
    assert drawing.form_plot_label().splitlines() == [
        "DETAIL B (SHEET 1)", f"SCALE {drawing.FORM_PLOT_SCALE:g} : 1",
    ]
    assert drawing.form_plot_labels()[0][0] == drawing.form_plot_label()
    source = inspect.getsource(drawing.build)
    assert "_mark_front_details(adapter, front, teeth" in source
    # The root envelope's leader stops on its near rim (the tip diameter
    # left the front view for the side view).
    assert 'set_near_side_diameter(found[0], f"{configuration} FloorDia")' in source


def test_the_d_clock_is_authored_in_the_quadrant_its_sheets_print() -> None:
    """drawing:dt_cone_gear at 5994f29 and 5a4e41cb5: each D sheet imported
    BoreFlatClock between the flat and the -X centreline (arcs 90..180 deg),
    flipped it right of the flat (0..90 deg), and the settling rebuild drew
    all four (T006-T024) back; a model-side SupplementaryAngle left the
    import unchanged. The clock is now dimensioned against a construction
    ray from the flat/axis crossing along +X, its text right of the flat and
    above the axis, so the sketch's own quadrant is the printed one."""
    import ast

    tree = ast.parse(inspect.getsource(part.build).lstrip())
    calls = [node for node in ast.walk(tree) if isinstance(node, ast.Call)]

    def call_named(name: str, label: str) -> ast.Call:
        found = [
            call for call in calls
            if ast.unparse(call.func).endswith(name)
            and any(isinstance(a, ast.Constant) and a.value == label for a in ast.walk(call))
        ]
        assert len(found) == 1, (name, label)
        return found[0]

    ray = next(
        call.args[1] for call in calls
        if ast.unparse(call.func) == "check"
        and isinstance(call.args[0], ast.Constant) and call.args[0].value == "bore clock ray"
    )
    ray_call = ray.value if isinstance(ray, ast.Await) else ray
    assert ast.unparse(ray_call.func).endswith("add_centerline")
    x0, y0, x1, y1 = (ast.unparse(arg) for arg in ray_call.args)
    # From the flat/axis crossing, along +X, on the axis.
    assert (x0, y0, y1) == ("flat_x", "0.0", "0.0")
    assert x1.startswith("flat_x + ")
    relations = {
        tuple(ast.unparse(item) for item in row.elts[1:])
        for row in ast.walk(tree)
        if isinstance(row, ast.Tuple) and len(row.elts) == 4
        and isinstance(row.elts[0], ast.Constant) and "clock ray" in str(row.elts[0].value)
    }
    assert relations == {
        ("f'{clock_ray}.start'", "f'{clock_line}.end'", "'coincident'"),
        ("clock_ray", "None", "'horizontal'"),
        ("clock_ray", "clock_line", "'equal'"),
    }
    clock = call_named("add_angular_reference_dimension", "bore flat clock")
    first, second, text = (ast.unparse(arg) for arg in clock.args[1:4])
    assert (first, second) == ("bore_flat", "clock_ray")
    # Text right of the flat and above the axis: that quadrant is the clock.
    assert text == "(flat_x + 0.3 * bore_radius, 0.4 * flat_half)"
    assert not any(ast.unparse(call.func).endswith("SupplementaryAngle") for call in calls)
    assert drawing.clock_dimension_name(6) == "BoreFlatClock"


def test_settled_clock_check_refuses_outside_arrow_stubs() -> None:
    """Run 20261010T073917031Z's arc readbacks (sheet mm): T006's clock drew
    one arc between its legs, broken by its text; T120's, its arrows left
    smart, drew two 10 deg stubs outside them and no arc. The clock is forced
    arrows-inside, and finalize re-reads every sheet's arcs after settling."""

    def arc(vertex, radius, start, end):
        steps = 12
        return (
            vertex,
            [
                (
                    vertex[0] + radius * math.cos(math.radians(start + (end - start) * i / steps)),
                    vertex[1] + radius * math.sin(math.radians(start + (end - start) * i / steps)),
                )
                for i in range(steps + 1)
            ],
        )

    good_vertex = (0.05292, 0.060)
    good = [arc(good_vertex, 0.04642, 0.0, 11.0), arc(good_vertex, 0.04642, 18.0, 90.0)]
    assert drawing.clock_arc_faults(good, good_vertex) == []
    bad_vertex = (0.068, 0.060)
    bad = [arc(bad_vertex, 0.03503, -10.2, 0.0), arc(bad_vertex, 0.03503, 90.0, 100.2)]
    faults = drawing.clock_arc_faults(bad, bad_vertex)
    assert any("outside the quadrant" in fault for fault in faults)
    assert any("sweep" in fault for fault in faults)
    assert drawing.clock_arc_faults([], bad_vertex) == ["no arc"]
    assert drawing.ARROWS_INSIDE == 0  # swDimensionArrowsSide_e.swDimArrowsInside


def test_settled_clocks_refuse_stub_arcs_on_any_sheet(monkeypatch: pytest.MonkeyPatch) -> None:
    from types import SimpleNamespace

    sheets: list[str] = []
    ddoc = SimpleNamespace(ActivateSheet=lambda name: sheets.append(name) or True)
    monkeypatch.setattr(drawing, "_early_bound", lambda obj, _iface: obj)
    monkeypatch.setattr(drawing, "_clock_arcs", lambda display: display)
    clocks = [("T012", [], 12), ("T018", [], 18)]
    with pytest.raises(RuntimeError, match=r"settling rebuild:\nT012: no arc\nT018: no arc"):
        drawing._assert_settled_clocks(SimpleNamespace(currentModel=ddoc), clocks)
    assert sheets == ["T012", "T018"]


def _callout_dimension(name: str, texts: dict[int, str]) -> object:
    from types import SimpleNamespace

    display = SimpleNamespace(
        GetText=lambda part: texts.get(part, ""),
        SetText=lambda part, text: texts.__setitem__(part, text),
    )
    return SimpleNamespace(name=name, GetSpecificAnnotation=lambda: display)


def test_settled_callouts_refuse_a_bare_dimension(monkeypatch: pytest.MonkeyPatch) -> None:
    # Farm run 20261110T005033414Z: the D sheets printed BoreCutDia, BoreAF
    # and BoreFlatClock bare, their shared callouts reset by the keyed sheets'
    # whole-model side-view import.
    from types import SimpleNamespace

    sheets: list[str] = []
    ddoc = SimpleNamespace(ActivateSheet=lambda name: sheets.append(name) or True)
    monkeypatch.setattr(drawing, "_early_bound", lambda obj, _iface: obj)
    monkeypatch.setattr(drawing, "dimension_name", lambda _adapter, item: item.name)
    adapter = SimpleNamespace(currentModel=ddoc)
    below = {name: drawing.DIMENSION_CALLOUTS[name] for name in ("BoreCutDia", "BoreAF", "BoreFlatClock")}
    above = {"BoreFlatClock": drawing.CALLOUTS_ABOVE["BoreFlatClock"]}
    printed = {
        "BoreCutDia": _callout_dimension("BoreCutDia", {4: below["BoreCutDia"].replace("\n", "\r\n")}),
        "BoreAF": _callout_dimension("BoreAF", {4: " "}),
        "BoreFlatClock": _callout_dimension("BoreFlatClock", {}),
    }
    sheet = [("T006", list(printed.values()), below, above)]
    with pytest.raises(RuntimeError, match="settling rebuild") as failure:
        drawing._assert_settled_callouts(adapter, sheet)
    message = str(failure.value)
    assert "T006 BoreCutDia" not in message
    for fault in ("T006 BoreAF: ' '", "T006 BoreFlatClock: ''"):
        assert fault in message
    # A dimension the sheet does not hold is a fault, not a pass.
    with pytest.raises(RuntimeError, match="T012 KeyedBoreDia: not on the sheet"):
        drawing._assert_settled_callouts(
            adapter, [("T012", [], {"KeyedBoreDia": drawing.DIMENSION_CALLOUTS["KeyedBoreDia"]}, {})]
        )
    # Written again after the last sheet's import, the same sheet passes.
    monkeypatch.setattr(
        drawing, "set_dimension_callouts",
        lambda _adapter, items, texts, location="below": [
            item.GetSpecificAnnotation().SetText(4 if location == "below" else 3, texts[item.name])
            for item in items if item.name in texts
        ],
    )
    drawing._rewrite_callouts(adapter, sheet)
    drawing._assert_settled_callouts(adapter, sheet)
    source = inspect.getsource(drawing.build)
    assert source.index("_rewrite_callouts(adapter, sheet_callouts)") < source.index(
        "return await finalize_drawing("
    )
    assert "_assert_settled_callouts(adapter, sheet_callouts)" in source


# The T012 thickness callout, each PDF text run's ink relative to its shelf's
# start (sheet metres): run 20261024T091056564Z's print, its name row moved
# over the value and its flag, recentred, under it. The root envelope's flag
# prints just above the block and the tip diameter's far left of it.
_T012_THICKNESS_RUNS = (
    ("CIRCULARTOOTHTHICKNESS", (0.00025, 0.01560, 0.06391, 0.01917)),
    ("0.831", (0.01856, 0.00650, 0.02898, 0.01007)),
    ("+", (0.03160, 0.01158, 0.03390, 0.01391)),
    ("-", (0.03213, 0.00765, 0.03338, 0.00794)),
    ("0.075", (0.03432, 0.01097, 0.04560, 0.01454)),
    ("0.075", (0.03432, 0.00645, 0.04560, 0.01001)),
    ("SEENOTE2", (0.01960, 0.00078, 0.04460, 0.00456)),
    ("SEENOTE2", (0.02500, 0.02800, 0.05000, 0.03178)),
    ("SEENOTE2", (-0.12000, 0.06000, -0.09500, 0.06378)),
)
# Its dimension's pen and the witnesses' half spacing at 6:1, as printed.
_PEN = 0.00013
_T012_HALF_WITNESS = 0.00249


def _line(x0: float, y0: float, x1: float, y1: float) -> Stroke:
    return Stroke(x0, y0, x1, y1, _PEN, (0, 0, 0), False, False, True)


def _t012_thickness_page(
    shelf: tuple[float, float], lines: list[tuple[float, float, float, float]]
) -> PageInk:
    x, y = shelf
    spans = []
    for text, (x0, y0, x1, y1) in _T012_THICKNESS_RUNS:
        glyph = Glyph(text[0], x + x0, y + y0, x + x1, y + y1)
        spans.append(
            Span(text, glyph.xmin, glyph.ymin, glyph.xmax, glyph.ymax, (glyph,))
        )
    strokes = (
        _line(x, y, x + _THICKNESS_SHELF_LENGTH, y),
        *(_line(*line) for line in lines),
    )
    glyphs = tuple(glyph for span in spans for glyph in span.glyphs)
    return PageInk(0.4318, 0.2794, glyphs, tuple(spans), strokes)


def test_text_air_refuses_the_line_hung_text_and_passes_the_shelf() -> None:
    """Machinist review of 2056e3344: the line dropping from the 3 o'clock
    tooth to the text it hung ran 0.19 mm off the C of CIRCULAR on every
    sheet. On its own shelf the offset leader leaves the line's midpoint."""
    from dataclasses import replace

    line_x = drawing.front_keep(12)["ToothThickness"][0]
    axis_y = drawing.FRONT_CENTER[1]
    lower = axis_y - _T012_HALF_WITNESS
    hung = _t012_thickness_page((line_x, 0.09286), [(line_x, 0.09286, line_x, lower)])
    air, nearest = drawing.tooth_thickness_text_air(hung, 12)
    assert air == pytest.approx(0.00025 - _PEN / 2.0, abs=1e-7)
    assert air < drawing.TOOTH_THICKNESS_TEXT_AIR
    assert "glyph" in nearest
    shelf = drawing.tooth_thickness_shelf(12)
    tail = drawing.DIMENSION_ARROW_LENGTH
    shelved = _t012_thickness_page(
        shelf,
        [
            (line_x, axis_y, *shelf),
            (line_x, lower, line_x, lower - tail),
            (
                line_x,
                axis_y + _T012_HALF_WITNESS,
                line_x,
                axis_y + _T012_HALF_WITNESS + tail,
            ),
        ],
    )
    air, _nearest = drawing.tooth_thickness_text_air(shelved, 12)
    assert air >= drawing.TOOTH_THICKNESS_TEXT_AIR
    with pytest.raises(ValueError, match="printed 0 times"):
        drawing.tooth_thickness_text_air(replace(shelved, spans=shelved.spans[1:]), 12)
    with pytest.raises(ValueError, match="no shelf"):
        drawing.tooth_thickness_text_air(
            replace(shelved, strokes=shelved.strokes[1:]), 12
        )


def test_export_is_refused_on_the_sheet_whose_thickness_text_a_line_strikes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pages = [object()] * len(drawing.SHEET_NAMES)
    monkeypatch.setattr(drawing, "read_pdf_ink", lambda _path: pages)
    struck = {18: 0.0015}
    monkeypatch.setattr(
        drawing,
        "tooth_thickness_text_air",
        lambda _page, teeth: (struck.get(teeth, 0.003), f"T{teeth:03d} nearest"),
    )
    with pytest.raises(
        RuntimeError, match=r"strikes the thickness text.*\nT018: T018 nearest$"
    ):
        drawing.assert_tooth_thickness_text_air(drawing.PDF)
    struck.clear()
    drawing.assert_tooth_thickness_text_air(drawing.PDF)
    checked: list[object] = []
    monkeypatch.setattr(drawing, "assert_tooth_thickness_text_air", checked.append)
    for phase in ("before_pdf_save", "after_drawing_save", "after_png_save"):
        drawing._check_exported_pdf(phase)
    assert checked == []
    drawing._check_exported_pdf("after_pdf_save")
    assert checked == [drawing.PDF]
    build = inspect.getsource(drawing.build)
    assert "checkpoint=_check_exported_pdf" in build
    assert build.index("_shelve_tooth_thickness(") > build.index("CALLOUTS_ABOVE")


def test_shelving_moves_the_text_by_its_measured_shelf_and_keeps_the_line(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from types import SimpleNamespace

    teeth = 12
    line_x = drawing.front_keep(teeth)["ToothThickness"][0]
    target = drawing.tooth_thickness_shelf(teeth)
    display = SimpleNamespace(OffsetText=False)
    annotation = SimpleNamespace(GetSpecificAnnotation=lambda: display)
    state = {
        "shelf": (target[0] + 0.003, target[1] - 0.002),
        "lines": [((line_x, 0.1525), (line_x, 0.1588)), ((line_x, 0.150), target)],
    }
    calls: list[tuple[object, ...]] = []

    def offset(_adapter: object, _annotations: object, positions: dict) -> None:
        display.OffsetText = True
        calls.append(("offset", positions["ToothThickness"]))

    def ink(_adapter: object, _annotation: object, *, label: str) -> SimpleNamespace:
        x, y = state["shelf"]
        return SimpleNamespace(text=(x, y, x + 0.064, y + 0.025))

    def move(
        _adapter: object, _annotation: object, dx: float, dy: float, *, label: str
    ) -> None:
        calls.append(("move", dx, dy))
        state["shelf"] = (state["shelf"][0] + dx, state["shelf"][1] + dy)

    monkeypatch.setattr(drawing, "_early_bound", lambda obj, _iface: obj)
    monkeypatch.setattr(
        drawing, "dimension_name", lambda _adapter, _a: "ToothThickness"
    )
    monkeypatch.setattr(drawing, "offset_dimension_text", offset)
    monkeypatch.setattr(drawing, "callout_ink", ink)
    monkeypatch.setattr(drawing, "move_annotation", move)
    monkeypatch.setattr(drawing, "dimension_segments", lambda _a: state["lines"])
    drawing._shelve_tooth_thickness(None, [annotation], teeth, label="T012")
    assert calls == [
        (
            "offset",
            (
                target[0] + drawing.TOOTH_THICKNESS_SEED[0],
                target[1] + drawing.TOOTH_THICKNESS_SEED[1],
            ),
        ),
        ("move", pytest.approx(-0.003), pytest.approx(0.002)),
    ]
    # A line that followed its text off the tooth is refused.
    state["lines"] = [((line_x + 0.03, 0.1), (line_x + 0.03, 0.12))]
    with pytest.raises(RuntimeError, match="left the tooth"):
        drawing._shelve_tooth_thickness(None, [annotation], teeth, label="T012")


def test_dimension_arrow_length_is_read_from_the_drawing() -> None:
    """The layout's arrow length is the drawing's own, not a remembered one."""

    class _Extension:
        def __init__(self, value: float) -> None:
            self.value = value
            self.calls: list[tuple[int, int]] = []

        def GetUserPreferenceDouble(self, pref: int, option: int) -> float:  # noqa: N802
            self.calls.append((pref, option))
            return self.value

    class _Drawing:
        def __init__(self, value: float) -> None:
            self.Extension = _Extension(value)

    matching = _Drawing(drawing.DIMENSION_ARROW_LENGTH)
    drawing._assert_dimension_arrow_length(matching)
    # swDetailingArrowLength, swDetailingNoOptionSpecified
    assert matching.Extension.calls == [(26, 0)]
    with pytest.raises(RuntimeError, match="drawing arrow length reads 3.175 mm"):
        drawing._assert_dimension_arrow_length(_Drawing(0.003175))


# The functional root callout's widest row (the mate's, seventeen characters)
# is wider than either value.
_FLOOR_TEXT_HALF_WIDTH = (
    max(map(len, drawing.DIMENSION_CALLOUTS["FloorDia"].splitlines())) * 0.00185 / 2.0
)


class _FakeFeature:
    def __init__(self, visible: int) -> None:
        self.Visible = visible


class _FakePart:
    """A part document that records sketch blanks and reports visibility."""

    def __init__(self, *, hides: bool) -> None:
        self.hides = hides
        self.selected: list[tuple[str, str]] = []
        self.blanked: list[str] = []
        self.Extension = self

    def ClearSelection2(self, _all: bool) -> None:
        pass

    def SelectByID2(self, name: str, kind: str, *_args: object) -> bool:
        self.selected.append((name, kind))
        return True

    def BlankSketch(self) -> None:
        self.blanked.append(self.selected[-1][0])

    def FeatureByName(self, name: str) -> _FakeFeature:
        # swVisibilityState_e: 1 hidden, 2 shown
        return _FakeFeature(1 if self.hides and name in self.blanked else 2)


class _FakeAdapter:
    def __init__(self, model: object) -> None:
        self.currentModel = model


def test_the_part_saves_every_authoring_sketch_hidden() -> None:
    """#950's save gate: a shown construction sketch renders in the part images
    and in every assembly that places a gear, so the part blanks each before
    its first save and reads the blank back."""
    model = _FakePart(hides=True)
    part._blank_reference_sketches(_FakeAdapter(model))
    sketches = [*spec.REFERENCE_SKETCHES, notes.BLANK_DIA_REFERENCE_SKETCH]
    assert model.selected == [(sketch, "SKETCH") for sketch in sketches]
    assert model.blanked == sketches
    source = Path(part.__file__).read_text(encoding="utf-8")
    body = source[source.index("async def build(") :]
    assert body.index("_suppress_rows_and_hide_references(adapter, pattern_axis)") < body.index(
        "await adapter.save_file("
    )
    assert "blank_reference_geometry(" not in body
    assert "assert_reference_geometry_hidden_in_every_configuration(adapter, PART_NAME)" in body


def test_hide_and_show_is_set_with_each_configuration_active(monkeypatch: pytest.MonkeyPatch) -> None:
    """7e88be269 T006 image: blanked with T120 active only, the axis and both
    sketches rendered in every other configuration."""
    from types import SimpleNamespace

    events: list[tuple[str, ...]] = []
    suppressed = SimpleNamespace(IsSuppressed2=lambda *_args: (True,))
    model = SimpleNamespace(
        GetConfigurationNames=lambda: [c for c, _t in spec.CONFIGS],
        FeatureByName=lambda _name: suppressed,
    )
    monkeypatch.setattr(part, "_early_bound", lambda obj, _iface: obj)
    monkeypatch.setattr(part, "_activate_configuration", lambda _m, c: events.append(("activate", c)))
    monkeypatch.setattr(part, "blank_reference_geometry", lambda _a, refs: events.append(("blank", *refs[0])))
    monkeypatch.setattr(part, "_blank_reference_sketches", lambda _a: events.append(("sketches",)))
    part._suppress_rows_and_hide_references(SimpleNamespace(currentModel=model), "Axis1")
    assert events == [
        event
        for configuration, _teeth in spec.CONFIGS
        for event in (("activate", configuration), ("blank", "Axis1", "AXIS"), ("sketches",))
    ]


def test_a_blank_that_does_not_take_fails_the_part_build() -> None:
    with pytest.raises(RuntimeError, match="still visible after BlankSketch"):
        part._blank_reference_sketches(_FakeAdapter(_FakePart(hides=False)))


class _FakeTolerance:
    def __init__(self, accept: bool = True) -> None:
        self.Type = 0
        self.accept = accept
        self.calls: list[tuple[float, float, int, list[str]]] = []

    def SetValues2(self, lower: float, upper: float, which: int, names: object) -> bool:
        self.calls.append((lower, upper, which, list(names.value)))
        return self.accept


def _patch_floor_dimension(monkeypatch: pytest.MonkeyPatch, tolerance: object) -> None:
    dimension = type("Dimension", (), {"Tolerance": tolerance})()

    def named(_adapter: object, feature: str, name: str) -> tuple[object, object]:
        assert (feature, name) == (spec.GAP_FLOOR_SKETCH, "FloorDia")
        return object(), dimension

    monkeypatch.setattr(readback, "_named_dimension", named)


def test_each_configuration_stores_its_own_gap_floor_limits(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """#834 Codex P1: the floor band is a native per-configuration LIMIT, one
    SetValues2 per configuration naming only that configuration."""
    tolerance = _FakeTolerance()
    _patch_floor_dimension(monkeypatch, tolerance)
    part._set_gap_floor_limits(object())
    assert tolerance.Type == 3  # swTolLIMIT
    assert [call[3] for call in tolerance.calls] == [[name] for name, _ in spec.CONFIGS]
    for (lower, upper, which, _names), (_name, teeth) in zip(
        tolerance.calls, spec.CONFIGS, strict=True
    ):
        assert which == 3  # swSetValue_InSpecificConfigurations
        nominal = 2.0 * spec.floor_radius_min_mm(teeth)
        minimum, maximum = spec.floor_limits_mm(teeth)
        assert nominal + lower * 1000.0 == pytest.approx(minimum, abs=1e-9)
        assert nominal + upper * 1000.0 == pytest.approx(maximum, abs=1e-9)
        assert lower <= 0.0 < upper


def test_a_rejected_configuration_limit_fails_the_part_build(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_floor_dimension(monkeypatch, _FakeTolerance(accept=False))
    with pytest.raises(RuntimeError, match="FloorDia@T006: SetValues2 rejected"):
        part._set_gap_floor_limits(object())


def test_every_configuration_stores_its_own_blank_and_thickness_band(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """part:dt_cone_gear at 039e557da: the T006-only write's immediate readback
    returned T006's band. The FloorDia form instead: all twenty written, T006
    its own, then each read back in the reopened audit with itself active."""
    tolerances = {"BlankDia": _FakeTolerance(), "ToothThickness": _FakeTolerance()}

    def named(_adapter: object, _feature: str, name: str) -> tuple[object, object]:
        return object(), type("Dimension", (), {"Tolerance": tolerances[name]})()

    monkeypatch.setattr(part, "_named_dimension", named)
    part._set_configuration_bands(object())
    for name, band_for in (
        ("BlankDia", spec.blank_dia_band),
        ("ToothThickness", spec.tooth_thickness_band),
    ):
        calls = tolerances[name].calls
        assert [call[3] for call in calls] == [[c] for c, _ in spec.CONFIGS]
        for (lower, upper, which, _names), (_c, teeth) in zip(calls, spec.CONFIGS, strict=True):
            assert which == 3
            upper_mm, lower_mm = band_for(teeth)
            assert (lower * 1000.0, upper * 1000.0) == pytest.approx((lower_mm, upper_mm))


def test_the_reopened_audit_reads_each_band_with_its_own_configuration_active(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The reopened audit reads every configuration's bands with that
    configuration active, and a failure names the call that raised (a raw
    COM error carries no member name, f68549253)."""
    import asyncio
    from types import SimpleNamespace

    active: list[str] = []
    banded: list[tuple[str, str, int]] = []

    async def activate(configuration: str) -> SimpleNamespace:
        active.append(configuration)
        return SimpleNamespace(is_success=True, data={"rebuilt": True}, error=None)

    async def topology(_adapter, configuration, teeth, *, phase, measure_roots):
        assert measure_roots and active[-1] == configuration
        return float(teeth), configuration, ()

    def bands(_adapter, configuration, teeth):
        banded.append((active[-1], configuration, teeth))
        if teeth == spec.CONFIGS[0][1]:
            raise AttributeError("member not found")

    monkeypatch.setattr(readback, "_configuration_topology", topology)
    monkeypatch.setattr(readback, "_assert_configuration_bands", bands)
    adapter = SimpleNamespace(set_active_configuration=activate)
    with pytest.raises(RuntimeError) as failure:
        asyncio.run(readback.assert_saved_configuration_topology(adapter))
    assert sorted(banded) == sorted((c, c, t) for c, t in spec.CONFIGS)
    message = str(failure.value)
    assert f"{spec.CONFIGS[0][0]}: AttributeError at line" in message
    assert "_assert_configuration_bands(adapter, configuration, teeth)" in message
    assert message.count("AttributeError") == 1


def test_each_authoring_sketch_shows_in_one_view() -> None:
    """The tooth and floor sketches' dimensions live on the front view, which
    takes the sketches by the opt-in import; the tip-diameter witness's on
    the side view (rule 11); the iso and bore views show the part as saved."""
    for sketch in (spec.TOOTH_REFERENCE_SKETCH, spec.GAP_FLOOR_SKETCH):
        owned = spec.DRAWING_DIMENSIONS[sketch]
        for teeth in spec.CONFIGURATION_TEETH:
            assert owned <= set(drawing.front_keep(teeth))
            assert not owned & set(drawing.right_keep(teeth))
            assert not owned & set(drawing.bore_view_keep(teeth))
    owned = notes.DRAWING_DIMENSIONS[notes.BLANK_DIA_REFERENCE_SKETCH]
    for teeth in spec.CONFIGURATION_TEETH:
        assert owned <= set(drawing.right_keep(teeth))
        assert not owned & set(drawing.front_keep(teeth))
        assert not owned & set(drawing.bore_view_keep(teeth))
    source = inspect.getsource(drawing.build)
    assert 'keep={"BlankDia": side_keep["BlankDia"]}' in source


def test_invalid_family_member_is_rejected() -> None:
    with pytest.raises(ValueError):
        spec.bore_dia_mm(7)
    with pytest.raises(ValueError):
        spec.floor_radius_max_mm(7)
    with pytest.raises(ValueError):
        spec.floor_radius_min_mm(7)
    with pytest.raises(ValueError):
        spec.outside_dia_mm(7)
    with pytest.raises(ValueError):
        spec.tooth_thickness_mm(7)
    with pytest.raises(ValueError):
        notes.drawing_notes(7)
    with pytest.raises(ValueError):
        spec.material_specification(7)
    with pytest.raises(ValueError):
        notes.gear_data(7)


def test_root_to_bore_webs_keep_the_floor_and_target_guards() -> None:
    # Printed root MIN against the outward-rounded maximum bore, not a nominal
    # floor; a keyed gear's against its keyway's top corner (cone_land_key).
    # T006's approved 0.62 web is separate from the ordinary 2.0 target.
    for teeth in spec.CONFIGURATION_TEETH:
        web = notes.root_to_bore_web_min_mm(teeth)
        if spec.keyed(teeth):
            assert web == pytest.approx(spec.keyway_web_min_mm(teeth))
            assert web >= spec.keyway_web_required_mm(teeth) - 1e-9
            assert web >= spec.MACHINED_WEB_FLOOR_MM, (teeth, web)
            continue
        if teeth in spec.WEB_EXCEPTIONS_MM:
            assert web >= spec.WEB_EXCEPTIONS_MM[teeth] - 1e-9
            continue
        assert web >= spec.MACHINED_WEB_TARGET_MM, (teeth, web)
    # The flat is a chord of the round bore on the axis's +X side: it only
    # ever leaves material, so no D's web is thinner than the round side's.
    for teeth in spec.D_BORE_TEETH:
        assert 0.0 < spec.bore_flat_offset_mm(teeth) < spec.bore_dia_mm(teeth) / 2.0
    # The terminal gear remains bounded by its current spec-owned special
    # web floor; neither a stale historical pin nor a new approval is used.
    terminal = spec.CONFIGURATION_TEETH[0]
    assert notes.root_to_bore_web_min_mm(terminal) >= (
        spec.WEB_EXCEPTIONS_MM[terminal] - 1e-9
    )
    for teeth in spec.CONFIGURATION_TEETH:
        section = spec.land_section(teeth)
        assert spec.bore_dia_mm(teeth) == pytest.approx(
            dt_cone_gear_shaft_spec.SECTION_DIAS[section]
        )


def test_dimensions_record_gear_bores_row_follows_the_spec() -> None:
    # The narrative record is read by no part, so nothing rebuilds when the
    # bores move: it kept the pre-S1 map (9.5 on T024-T120) after U40.  It
    # must name every round seat, its gears and its across-flat.
    groups: dict[float, list[int]] = {}
    for teeth in spec.CONFIGURATION_TEETH:
        groups.setdefault(spec.bore_dia_mm(teeth), []).append(teeth)
    record = yaml.safe_load(
        (Path(part.__file__).resolve().parents[1] / "config" / "dimensions.yaml")
        .read_text(encoding="utf-8")
    )
    rows = []
    stack = [record]
    while stack:
        node = stack.pop()
        if isinstance(node, dict):
            stack.extend(node.values())
        elif isinstance(node, list):
            if node and isinstance(node[0], str) and node[0].startswith("Gear bores"):
                rows.append(node)
            stack.extend(node)
    assert len(rows) == 1
    row = rows[0][1]
    printed_bores = sorted({float(value) for value in re.findall(r"Ø(\d+\.\d+)", row)})
    assert printed_bores == pytest.approx(sorted(groups))
    for bore, teeth in groups.items():
        span = f"T{teeth[0]:03d}" if len(teeth) == 1 else f"T{teeth[0]:03d}–T{teeth[-1]:03d}"
        assert span in row, span
        if spec.keyed(teeth[0]):
            assert f"{cone_land_key.KEYWAY_T_MM:.3f}" in row, bore
        else:
            assert f"{spec.bore_flat_af_mm(teeth[0]):.3f}" in row, bore
