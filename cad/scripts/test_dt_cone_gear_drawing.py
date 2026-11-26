"""Offline behavioral contracts for the cone-gear batch drawing package."""

from __future__ import annotations

import inspect
import math
import re
from pathlib import Path

import pytest

import _config
import _drawing_leaders
import _cone_gear_geometry as geometry
import _cone_gear_native as native_gear
import _cone_gear_readback as readback
import _cone_gear_sheet as cone_sheet
import build_dt_cone_gear as part
import cone_land_key
import cone_tip_cluster
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
        range(12, int(_config.machine("gear_train", "fundamental_cone_teeth")) + 1, 6)
    )
    expected_names = tuple(f"T{teeth:03d}" for teeth in expected_teeth)
    assert spec.CONFIGURATION_TEETH == expected_teeth
    assert spec.CONFIGS == tuple(zip(expected_names, expected_teeth, strict=True))
    assert drawing.SHEET_NAMES == expected_names
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
    # No clock: the keyway shares the front view's drawn +X centreline with
    # the phase-0 tooth, at the title block's angle.
    round_bore = {"BoreCutDia"}
    keyed_bore = {"KeyedBoreDia", "KeywayWidth", "KeywayT"}
    assert marked == {
        "BlankDia",
        "FaceWidth",
        *round_bore,
        *keyed_bore,
        "ToothThickness",
        "FloorDia",
        "WebMin",
    }
    assert spec.DRAWING_DIMENSIONS[spec.BORE_SKETCH] == round_bore
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
        assert expected == marked - (round_bore if spec.keyed(teeth) else keyed_bore) - (
            set() if teeth == spec.WEB_REFERENCE_TEETH else {"WebMin"}
        )
        # A keyed bore prints whole in the bore view, and only there; a plain
        # round bore has no bore view and prints on the front view.
        bore = spec.DRAWING_DIMENSIONS[spec.bore_sketch(teeth)]
        if spec.keyed(teeth):
            assert set(drawing.bore_view_keep(teeth)) == bore
        else:
            assert drawing.bore_view_keep(teeth) == {}
            assert bore <= set(drawing.front_keep(teeth))
        # Diameters on the side view beside the face width (rule 11).
        assert set(drawing.right_keep(teeth)) == {"FaceWidth", "BlankDia"}


def test_model_owns_precision_for_every_printed_dimension() -> None:
    # Decimal inch (#290): four places carry every band and narrow floor
    # window exactly on the .0001 grid.
    assert spec.DRAWING_PRECISION_BY_NAME == {
        "BlankDia": 4,
        "FaceWidth": 4,
        "BoreCutDia": 4,

        "KeyedBoreDia": 4,
        "KeywayWidth": cone_land_key.KEYWAY_PLACES,
        "KeywayT": cone_land_key.KEYWAY_PLACES,
        "ToothThickness": 4,
        "FloorDia": 4,
        "WebMin": 4,
    }
    assert "draw_dt_cone_gear.py" in PRECISION_MIGRATED_DRAWINGS


def test_tip_diameter_carries_its_own_mesh_depth_band() -> None:
    # Ordinary undersize-only blank band (user ruling 2026-10-10, cones at
    # ordinary tolerances), every configuration alike.
    assert spec.BLANK_DIA_BAND == (0.0, -0.0508)
    assert all(spec.blank_dia_band(t) is spec.BLANK_DIA_BAND for t in spec.CONFIGURATION_TEETH)
    assert spec.BLANK_DIA_BAND[0] < spec.MODULE_MM / 2.0
    # The bores print their reamer's size with no band (fit audit
    # 2026-11-23): no configuration band rides them.
    assert readback._BANDED_DIMENSIONS == (
        (notes.BLANK_DIA_REFERENCE_SKETCH, "BlankDia", spec.blank_dia_band),
        (spec.TOOTH_REFERENCE_SKETCH, "ToothThickness", spec.tooth_thickness_band),
    )


def test_face_width_fills_the_seat_pitch_without_crossing_it() -> None:
    # Solid touching stack: twenty gears end to end on SEAT_PITCH centres.
    # The nominal is the seat pitch floored to 4 places, so it never prints
    # longer than the pitch; cone_gear_stack owns the stack's band.
    assert spec.FACE_WIDTH == math.floor(spec.SEAT_PITCH * 1e4) / 1e4
    assert spec.FACE_WIDTH <= spec.SEAT_PITCH < spec.FACE_WIDTH + 1e-4
    upper, lower = spec.FACE_WIDTH_BAND
    assert upper == -lower > 0.0  # centred, as the stack's partial bands need


def test_each_configuration_sheet_carries_its_own_drawing_number() -> None:
    number = str(_config.parts("dt-cone-gear")["number"])
    assert spec.configuration_number(number, 12) == f"{number}-T012"
    assert spec.configuration_number(number, 120) == f"{number}-T120"
    numbers = {spec.configuration_number(number, t) for t in spec.CONFIGURATION_TEETH}
    assert len(numbers) == len(spec.CONFIGURATION_TEETH)
    with pytest.raises(ValueError):
        spec.configuration_number(number, 6)


@pytest.mark.parametrize("teeth, suffix", ((12, "T012"), (18, "T018"), (120, "T120")))
def test_two_digit_family_number_keeps_three_digit_tooth_configuration(
    teeth: int, suffix: str,
) -> None:
    assert spec.configuration_number(" mha-dt-03 ", teeth) == f"MHA-DT-03-{suffix}"


def test_bore_bands_are_the_current_derived_seat_fit_bands() -> None:
    assert spec.BORE_DIA_BAND == pytest.approx(
        (spec.BORE_BAND_FIT_UPPER, spec.BORE_BAND_LOWER)
    )
    assert spec.BORE_DIA_BAND[0] - spec.BORE_DIA_BAND[1] >= 0.02 - 1e-9
    # Each land seat is reamed with the owned over reamer, the land's
    # nominal plus the seat class's lower deviation (.2510, .3760), and its
    # analysis band is the class's spread about that size: the absolute
    # limits are the seat class's on the land.
    for teeth in (24, *spec.KEYED_TEETH):
        land = 2 if teeth == 24 else spec.KEYED_LAND
        land_dia = dt_cone_gear_shaft_spec.SECTION_DIAS[land]
        assert spec.bore_dia_mm(teeth) == pytest.approx(land_dia + spec.BORE_DIA_BAND[1])
        upper, lower = spec.bore_dia_band(teeth)
        assert spec.bore_dia_mm(teeth) + lower == pytest.approx(land_dia + spec.BORE_DIA_BAND[1])
        assert spec.bore_dia_mm(teeth) + upper == pytest.approx(land_dia + spec.BORE_DIA_BAND[0])
    assert spec.bore_dia_mm(24) == pytest.approx(0.2510 * 25.4)
    assert spec.bore_dia_mm(30) == pytest.approx(0.3760 * 25.4)
    # The keyway takes cone_land_key's bands: the 1/16 A broach's
    # +.0020/-.0000 width (its analysis band; the sheet prints (.0625) REF,
    # machinist review r1, farm run 20261124T110807008Z) and +/-.003 on T (the
    # one-pass broach's reach, no tighter than the milled-step row), plain
    # inch steps.
    assert cone_land_key.KEYWAY_WIDTH_BAND == (0.0508, 0.0)
    assert cone_land_key.KEYWAY_T_BAND == (0.0762, -0.0762)
    assert spec.KEYWAY_HALF_WIDTH_MM == cone_land_key.KEYWAY_WIDTH_MM / 2.0


def test_native_tooth_inspection_reads_the_actual_installed_cutter() -> None:
    # Ordinary +/-.003 thickness band about the cutter's standard-depth
    # thickness; T006 alone is thin-only (DT6-FORM1 relief clearance), and
    # T012/T018/T024 thick-only, +.003/-0, which leaves them the standard
    # (N + 2)/DP blank (owner ruling 2026-11-22, #2473 option G).
    assert spec.TOOTH_THICKNESS_BAND == (0.0762, -0.0762)
    assert spec.tooth_thickness_band(6) == spec.CUSTOM_SIX_TOOTH_THICKNESS_BAND == (0.0, -0.04064)
    assert spec.THICK_ONLY_TEETH == spec.ROUND_BORE_TEETH == (12, 18, 24)
    for teeth in spec.CONFIGURATION_TEETH:
        thick_only = teeth in spec.THICK_ONLY_TEETH
        assert spec.tooth_thickness_band(teeth) == (
            (0.0762, 0.0) if thick_only else (0.0762, -0.0762)
        )
        # A thick-only gear's blank is what the cutter's form supports at
        # standard depth, within .0005 in of the standard (N + 2)/DP; a thin
        # limit sinks the cutter and costs every other gear .007 or more.
        under_standard = (teeth + 2) * spec.MODULE_MM - spec.outside_dia_mm(teeth)
        assert (under_standard < 0.0005 * 25.4) is thick_only, teeth
        assert thick_only or under_standard > 0.007 * 25.4, teeth
    assert {
        teeth: round(spec.outside_dia_mm(teeth) / 25.4, 4)
        for teeth in spec.THICK_ONLY_TEETH
    } == {12: 0.2916, 18: 0.4164, 24: 0.5412}
    assert {
        teeth: tuple(round(v / 25.4, 4) for v in spec.over_pins_limits_mm(teeth))
        for teeth in spec.THICK_ONLY_TEETH
    } == {12: (0.3116, 0.3182), 18: (0.4376, 0.4446), 24: (0.5632, 0.5704)}
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

def test_each_sheet_gets_its_own_actual_cutting_recipe() -> None:
    for teeth in spec.CONFIGURATION_TEETH:
        data = notes.gear_data(teeth)
        assert data.startswith("GEAR DATA\n")
        assert f"T{teeth:03d}" in data
        assert f"{spec.DIAMETRAL_PITCH:.2f} / {spec.PRESSURE_ANGLE_DEG:.1f}\u00b0" in data
        for physical_recipe in (
            "CUTTER", "CUTTER PLUNGE FROM BLANK OD", "WHOLE DEPTH",
            "TOOTH FORM", "BACKLASH WITH MATE", "WEB",
            "OVER 2 PINS",
        ):
            assert physical_recipe in data, (teeth, physical_recipe)
        # The Ø ROOT ENVELOPE limits alone control the root: a REF radial
        # MIN/MAX restated them (T012's equalled CUTTER ROOT ARC R) under a
        # non-standard name (machinist review of the C1-keyed round 7).
        assert "ROOT RADIAL" not in data
        # ENFORCE round 1 of #971: "TOOL T" told the shop how to set the
        # cutter (rule 7); the plunge stays, a reference depth.
        assert "TOOL T" not in data
        # Stock cutters by number and range on every sheet.
        assert " INVOLUTE GEAR CUTTER, " in data, teeth
        assert "NOT STOCK" not in data
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
        native = native_gear.native_gap_segments(teeth)
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
    for name in ("BoreCutDia", "KeyedBoreDia", "KeywayWidth", "KeywayT"):
        assert bore_flag in callouts[name].splitlines(), name

    # A size reads from its witnesses: the keyway's T carries its flag only.
    assert callouts["KeywayT"] == bore_flag
    assert above["BlankDia"] == teeth_flag
    assert callouts["FloorDia"].splitlines() == ["ROOT ENVELOPE", teeth_flag]
    assert "MHA-DT-04" in callouts["FaceWidth"]
    assert set(above) == {"ToothThickness", "BlankDia"}
    # No clock is dimensioned, so no clock callout carries words (rule 7).
    assert not any("Clock" in name for name in (*callouts, *above))
    assert all("\n" not in text for text in above.values())
    # The mates appear once each, in the notes; no dimension repeats them.
    for text in (*callouts.values(), *above.values()):
        assert notes.CYLINDER_MATE_NUMBER not in text, text
        assert drawing.KEY_MATE not in text, text
    for name in (
        "BoreCutDia", "KeyedBoreDia", "KeywayWidth", "KeywayT",
    ):
        assert "MHA-DT-04" not in callouts[name] + above.get(name, "")
    # Both round bores are fit bores: REAM is their one process word
    # (rule 7); the keyway takes none.
    assert callouts["KeyedBoreDia"].splitlines()[0] == "REAM THRU"
    assert callouts["BoreCutDia"].splitlines()[0] == "REAM THRU"
    for name in ("KeywayWidth", "KeywayT"):
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
    # The bore diameter's rows stay as narrow as its value.
    assert max(map(len, callouts["BoreCutDia"].splitlines())) <= 10


def test_numbered_notes_state_the_bore_fit_from_both_parts_limits() -> None:
    """Note 1 is the bore's fit (rule 4, form 2): every bore is reamed, and
    the note names its mate, which is turned to it last (MHA-DT-04's land,
    by its diameter, or MHA-DT-37's spigot); the keyed bore's key slides in
    its keyway. The acceptance and the bond's clearance print on the mate's
    sheet: no clearance, no compound and no method here. Note 2 names the
    mesh and the over-pins and backlash acceptances."""
    import cone_shaft_land_bands as lands

    shaft = str(_config.parts("dt-cone-gear-shaft")["title"]).upper()
    tip_gear = _config.parts("dt-cone-tip-gear")
    for teeth in spec.CONFIGURATION_TEETH:
        text = drawing.sheet_notes(teeth)
        lines = text.splitlines()
        if spec.keyed(teeth):
            land = lands.SECTION_DIA_BANDS[spec.KEYED_LAND]
            (round_min, round_max), (second_min, second_max) = drawing.bore_clearances_mm(teeth)
            # The analysis clearance is the seat class's, unchanged.
            assert round_min == pytest.approx(spec.BORE_DIA_BAND[1] - land[0])
            assert round_max == pytest.approx(spec.BORE_DIA_BAND[0] - land[1])
            assert 0.0 < round_min < round_max
            dia = f"\u00d8{spec.inch_text(spec.BORE_DIA, 4)} LAND"
            assert (second_min, second_max) == cone_land_key.KEYWAY_SIDE_CLEARANCE_MM
            assert lines[0] == (
                f"1. SLIDING FIT: {shaft} MHA-DT-04 {dia} IS TURNED TO THIS BORE;"
            )
            assert lines[1] == (
                f"   KEYWAY: 1/16 BROACH; KEY {drawing.KEY_MATE} SLIDES IN, NO ROCK."
            )
            assert "CLEARANCE" not in text
            assert "MEASURED" not in text
            notes_from = 2
        else:
            low, high = spec.bond_clearance_mm(teeth)
            # A bond: never interference, never past the compound's largest gap.
            assert 0.0 <= low < high <= cone_tip_cluster.RETAINING_COMPOUND_MAX_GAP_MM
            if teeth in spec.SPIGOT_TEETH:
                # MHA-DT-37 prints the spigot's band (D51 as amended): it
                # is not turned to this bore.
                mate = f"{str(tip_gear['title']).upper()} {tip_gear['number']} SPIGOT"
                clearance = f"{spec.inch_text(low, 4)}-{spec.inch_text(high, 4)}"
                assert lines[0] == f"1. BONDED SLIP FIT ON {mate} (CLEARANCE {clearance})."
            else:
                land_name = f"\u00d8{spec.inch_text(spec.LAND_2_DIA, 4)} LAND"
                mate = f"{shaft} MHA-DT-04 {land_name}"
                assert lines[0] == f"1. BONDED SLIP FIT: {mate} IS TURNED TO THIS BORE."
            assert drawing.KEY_MATE not in text
            # Rule 23: the mate's sheet gives the bond's clearance; the grade
            # and method are MHA-DT-00's bonding step's.
            assert "LOCTITE" not in text
            notes_from = 1
        assert "ACROSS FLAT" not in text
        assert lines[notes_from].startswith(f"2. TEETH MESH WITH {notes.CYLINDER_MATE_NUMBER}")
        # The teeth's do-not-cut rides the note flagged to them (rule 7).
        assert lines[notes_from + 1].endswith(notes.TOOTH_EDGE_NOTE)
        # The sheet's only notes, at most four lines (rule 7), top-left, above
        # the front view and its root envelope's stack, and left of Gear Data
        # (2.5 mm text: 3.51 mm a line, 1.79 mm a character).
        assert len(lines) <= 4
        x, y = drawing.NUMBERED_NOTES_POS
        top = max(
            drawing.FRONT_CENTER[1] + drawing.rendered_half_od(teeth),
            drawing.front_keep(teeth)["FloorDia"][1]
            + cone_sheet.FLOOR_STACK_HALF_HEIGHT,
        )
        assert y - len(lines) * 0.00351 > top + 0.010
        assert x + max(map(len, lines)) * 0.00179 < drawing.GEAR_DATA_POS[0] - 0.005


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


def test_over_pins_acceptance_matches_the_closed_form_involute() -> None:
    """The standard even-count over-pins formula agrees with the sampled
    model flank where that flank is the gear's own involute (T012's 12T
    template), and the thin limit reads below the thick one. ENFORCE round 1
    of #971: every sheet carries the row; the stock gears' 1.00 pin lands on
    the flank and stands proud. A stock cutter cuts its template's form,
    thinner up the flank than the gear's own involute away from the template
    count, so there the pins read up to ~0.015 under the formula and the row
    follows the model."""
    for teeth in spec.CONFIGURATION_TEETH:
        assert teeth % 2 == 0, teeth
        profile = spec.stock_form_profile(teeth)
        pitch_dia = 2.0 * profile.pitch_radius_mm
        alpha = math.radians(spec.PRESSURE_ANGLE_DEG)
        base_dia = pitch_dia * math.cos(alpha)
        pin = spec.over_pins_pin_dia_mm(teeth)
        assert pin == 1.016

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
        if teeth in spec.THICK_ONLY_TEETH:
            # The nominal thickness is the thin limit: the least reading is
            # the nominal's, rounded inward by under one printed step.
            assert nominal <= minimum < nominal + 1e-4 * 25.4 < maximum, teeth
        else:
            assert minimum < nominal < maximum + 1e-3, teeth
        row = (
            f"OVER 2 PINS \u00d8{spec.inch_text(pin, 3)}, OPPOSITE GAPS:  "
            f"{spec.inch_text(minimum, 4)} TO {spec.inch_text(maximum, 4)}"
        )
        assert row in notes.gear_data(teeth), teeth


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
    # drawing-guidelines.md rule 7 (notes: few, flagged, never a method): native bore dimensions carry its fit, and the Gear Data block
    # reports actual cutter/mesh facts separately. The part's manufacturing
    # note carries no review history or waived floors; the teeth's do-not-cut
    # moved to the note flagged to them (sheet note 2).
    expected = notes.DRAWING_NOTES.splitlines()
    assert "T-CONFIGURATION" not in notes.DRAWING_NOTES
    assert "EDGE" not in notes.DRAWING_NOTES
    assert not hasattr(notes, "ATTACHMENT")
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

    data = notes.gear_data(teeth)
    booked = cone_set_stack.cone_tooth_runout_tir_mm(teeth)
    if teeth in spec.SPIGOT_TEETH:
        # Owner ruling 2026-11-21 (#3219 option D): T012/T018 are accepted on
        # tooth-space runout to the bore, a pin in every space.
        assert "ACCEPT AT SETUP" not in data
        match = re.search(
            r"^TOOTH SPACE RUNOUT TO BORE:  (\.\d{4}) TIR MAX, \u00d8(\.\d{3}) PIN, "
            rf"ALL {teeth} SPACES$",
            data,
            re.MULTILINE,
        )
        assert match, data
        printed_tir = float(match.group(1)) * spec.MM_PER_IN
        assert booked - 0.0001 * spec.MM_PER_IN < printed_tir <= booked + 1e-9
        assert float(match.group(2)) * spec.MM_PER_IN == pytest.approx(
            spec.over_pins_pin_dia_mm(teeth)
        )
        assert f"\u00d8{match.group(2)}, OPPOSITE GAPS" in data
    else:
        # Machinist review of #3324 r1: a finished-part row, not a setup.
        assert booked == cone_set_stack.TOOTH_RUNOUT_TIR_MM
        assert "ACCEPT AT SETUP" not in data
        assert f"TOOTH RUNOUT TO BORE:  {spec.inch_text(booked, 3)} TIR MAX" in data


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
        tail_y = witness_y + cone_sheet.DIMENSION_ARROW_LENGTH
        shelf_y = floor_y - cone_sheet.FLOOR_STACK_HALF_HEIGHT
        assert shelf_y - tail_y >= _drawing_leaders.ARROW_TEXT_CLEARANCE - 1e-9, teeth
        assert (
            floor_y + cone_sheet.FLOOR_STACK_HALF_HEIGHT
            < drawing.GEAR_DATA_POS[1] - drawing.GEAR_DATA_HEIGHT
        )
        # The shelf rises only where the tail needs it: every other sheet
        # keeps the stack's usual place.
        usual = drawing.FRONT_CENTER[1] + 0.6 * half_od + cone_sheet.FLOOR_DIA_RISE
        assert floor_y >= usual - 1e-12
        if floor_y > usual:
            assert shelf_y - tail_y == pytest.approx(_drawing_leaders.ARROW_TEXT_CLEARANCE)
        # The thickness text's shelf, budgeted with the block the last print
        # measured: its leader (from the line's midpoint on the bore axis to
        # the shelf's start) keeps the fleet's text air off the C of CIRCULAR
        # and the bottom row, the block tops out under the root-envelope
        # stack's shelf and ends left of the side view.
        thickness_x, thickness_y = drawing.tooth_thickness_shelf(teeth)
        assert thickness_x - line_x == pytest.approx(
            cone_sheet.TOOTH_THICKNESS_TEXT_GAP
        )
        leader = Segment(line_x, drawing.FRONT_CENTER[1], thickness_x, thickness_y)
        for x0, y0, x1, y1 in (_THICKNESS_C_GLYPH, _THICKNESS_BOTTOM_GLYPH):
            glyph = Box(
                thickness_x + x0, thickness_y + y0, thickness_x + x1, thickness_y + y1
            )
            assert segment_box_distance(leader, glyph) >= (
                cone_sheet.TOOTH_THICKNESS_TEXT_AIR + _THICKNESS_AIR_MARGIN
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
# [11.1, 53.5] mm about x 30.0), and the two-line title.
_BORE_DIA_TEXT_LEFT_REACH = 0.0189
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


def test_front_view_carries_a_round_bore_callout_clear_of_its_neighbours() -> None:
    """Round 2 machinist review of the C1-keyed sheets (rule 1): DETAIL A only
    enlarged T012..T024's plain round bore, so the diameter reads on the
    front view, its block (measured extents) upper left of the gear: outside
    the tip circle, inside the border, under the numbered notes, left of the
    root envelope's stack and above T012's web text."""
    for teeth in spec.CONFIGURATION_TEETH:
        if spec.keyed(teeth):
            assert "BoreCutDia" not in drawing.front_keep(teeth)
            continue
        x, y = drawing.front_keep(teeth)["BoreCutDia"]
        assert (x, y) == drawing.front_bore_dia_xy(teeth)
        half_width = drawing.FRONT_BORE_DIA_TEXT_HALF_WIDTH
        box = Box(x - half_width, y - drawing.FRONT_BORE_DIA_TEXT_DROP, x + half_width, y + 0.009)
        cx, cy = drawing.FRONT_CENTER
        nearest = (min(max(cx, box.xmin), box.xmax), min(max(cy, box.ymin), box.ymax))
        half_od = drawing.rendered_half_od(teeth)
        assert math.dist(nearest, drawing.FRONT_CENTER) >= half_od + 0.004, teeth
        # The leader runs up left, the one diagonal no other front-view line takes.
        corner_angle = math.degrees(math.atan2(box.ymin - cy, box.xmax - cx))
        assert corner_angle == pytest.approx(drawing.FRONT_BORE_DIA_ANGLE_DEG, abs=5.0)
        assert (
            abs(math.remainder(corner_angle - spec.WEB_REFERENCE_ANGLE_DEG, 360.0))
            >= 90.0 - 1e-9
        )
        assert box.xmin > _ZONE_MARGIN
        notes_bottom = drawing.NUMBERED_NOTES_POS[1] - len(
            drawing.sheet_notes(teeth).splitlines()
        ) * 0.00351
        assert box.ymax < notes_bottom - 0.005, teeth
        floor_x = drawing.front_keep(teeth)["FloorDia"][0]
        assert box.xmax < floor_x - 0.019 - 0.005, teeth
        if teeth == spec.WEB_REFERENCE_TEETH:
            assert box.ymin > drawing.web_min_text_xy()[1] + 0.010


def test_bore_view_enlarges_every_keyed_bore_clear_of_its_neighbours() -> None:
    ladder = [n / d for n, d in drawing.BORE_VIEW_SCALE_LADDER]
    cx, cy = drawing.BORE_VIEW_CENTER
    for teeth in spec.CONFIGURATION_TEETH:
        if not spec.keyed(teeth):
            continue
        dia_name = "KeyedBoreDia"
        numerator, denominator = drawing._SCALE_BY_TEETH[teeth]
        sheet_ratio = numerator / denominator
        view_numerator, view_denominator = drawing.bore_view_scale(teeth)
        ratio = view_numerator / view_denominator
        bore = spec.bore_dia_mm(teeth)
        # Enlarged past the sheet, to the smallest ladder ratio that renders
        # the bore legibly.
        assert ratio > sheet_ratio
        assert bore * ratio / 1000.0 >= drawing.BORE_VIEW_BORE_MIN
        assert all(
            bore * smaller / 1000.0 < drawing.BORE_VIEW_BORE_MIN
            for smaller in ladder
            if sheet_ratio < smaller < ratio
        )
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
        title_top = drawing.bore_view_label_top(teeth)
        assert title_top - _BORE_TITLE_HEIGHT > _ZONE_MARGIN + 0.001
        assert drawing.bore_view_label(teeth).splitlines() == [
            "DETAIL A",
            f"SCALE {view_numerator:g} : {view_denominator:g}",
        ]
        # The keyway is at least 2.5 mm deep on paper.
        flat = spec.keyway_top_offset_mm(teeth) * ratio / 1000.0
        assert abs(bore * ratio / 2000.0 - flat) >= 0.0025, teeth
        # The T text stands wholly right of the keyway top's witness, left of
        # the title block, above the title, which stays inside the border.
        af_x, af_y = keep["KeywayT"]
        assert af_x - drawing.BORE_VIEW_AF_HALF_WIDTH > cx + flat + 0.002
        assert af_x + drawing.BORE_VIEW_AF_HALF_WIDTH < 0.216
        assert af_y < cy - crop
        assert af_y - 2.0 * _BORE_TEXT_HALF_HEIGHT > title_top

        ctt_x, ctt_y = drawing.tooth_thickness_shelf(teeth)
        ctt_box = (
            ctt_x,
            ctt_y,
            ctt_x + _THICKNESS_SHELF_LENGTH,
            ctt_y + _THICKNESS_INK_HEIGHT,
        )

        # The keyway width's block stands right of the crop circle, under its
        # lower witness and arrow, clear of T's block and the thickness text.
        width_x, width_y = keep["KeywayWidth"]
        half_width = spec.KEYWAY_HALF_WIDTH_MM * ratio / 1000.0
        width_box = (
            width_x - drawing.KEYWAY_WIDTH_TEXT_HALF_WIDTH,
            width_y - drawing.KEYWAY_WIDTH_TEXT_HALF_HEIGHT,
            width_x + drawing.KEYWAY_WIDTH_TEXT_HALF_WIDTH,
            width_y + drawing.KEYWAY_WIDTH_TEXT_HALF_HEIGHT,
        )
        assert width_box[0] >= cx + crop + 0.002 - 1e-12
        assert width_box[3] <= cy - half_width - drawing.KEYWAY_WIDTH_TEXT_DROP - (
            _drawing_leaders.ARROW_TEXT_CLEARANCE
        ) + 1e-12
        t_box = (
            af_x - drawing.BORE_VIEW_AF_HALF_WIDTH,
            af_y - 2.0 * _BORE_TEXT_HALF_HEIGHT,
            af_x + drawing.BORE_VIEW_AF_HALF_WIDTH,
            af_y + 2.0 * _BORE_TEXT_HALF_HEIGHT,
        )
        for other in (t_box, ctt_box):
            assert _drawing_annotation_extent.boxes_clear(width_box, other), teeth


# The front view's +X centre-mark line as printed (sheet metres): r3, the
# template's lines with no extension; r4, T006 asked for 1.948 mm more.
# The keyed sheets' measured ends (their bores are PR 1's); the additive
# model was proved on PR 1's T006 sheet (r4: 1.948 mm asked, 143.7 mm printed).
_CENTRE_LINE_R3_ENDS = {30: 0.1268, 60: 0.1195, 120: 0.1123}


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


def test_the_bore_view_crop_rim_is_picked_clear_of_the_keyed_bore() -> None:
    """Machinist review of run 20261122T215628806Z-4c985630476a4af3977b78cbe1520d58
    (rule 9): DETAIL A drew no keyway top on any keyed sheet. The crop
    circle's rim point, picked on +X, snapped to the keyway top's midpoint
    1.7 mm inside it. Its ray now stands clear of every point of the bore
    profile; the drawn circle is read back (cone_sheet.sketch_view_circle)."""
    angle = math.radians(drawing.BORE_VIEW_CROP_RIM_ANGLE_DEG)
    for teeth in spec.CONFIGURATION_TEETH:
        if not spec.keyed(teeth):
            continue
        ratio = drawing._bore_view_ratio(teeth)
        crop = drawing.bore_view_crop_radius(teeth)
        rim = (crop * math.cos(angle), crop * math.sin(angle))
        bore_radius = spec.bore_dia_mm(teeth) / 2.0
        half = spec.KEYWAY_HALF_WIDTH_MM
        top = spec.keyway_top_offset_mm(teeth)
        side = math.sqrt(bore_radius**2 - half**2)
        points_mm = [
            (0.0, 0.0),
            (-bore_radius, 0.0),
            (0.0, bore_radius),
            (0.0, -bore_radius),
            (top, 0.0),
            (top, half),
            (top, -half),
            (side, half),
            (side, -half),
        ]
        nearest = min(
            math.dist(rim, (x * ratio / 1000.0, y * ratio / 1000.0))
            for x, y in points_mm
        )
        on_keyway_axis = crop - top * ratio / 1000.0
        assert on_keyway_axis < 0.002, teeth  # the snap that happened
        assert nearest >= 0.008, (teeth, nearest)
        # The bore's arc itself is the nearest ink to the rim point.
        assert crop - bore_radius * ratio / 1000.0 >= 0.004, teeth


def test_front_view_draws_the_centreline_the_flat_and_its_tooth_share() -> None:
    """Machinist review of the C1-keyed sheets (rule 10; PR 2 round 2): the
    clock '90° ±.25° TO TOOTH CENTERLINE' in DETAIL A named a tooth no view
    drew there. The clock is now the centreline the flat (keyway) and the
    phase-0 tooth share on the front view (gap bisectors rotate by pi/N, so
    a tooth centres on +X, the flat's or keyway's normal), at the title
    block's angle, and no sheet dimensions it. The bore centre mark's +X
    line runs from the rim through that tooth past the tip, and stops short
    of the thickness dimension's line, whose midpoint on the axis starts the
    leader to the thickness text; the text keeps the printed-air check's
    2 mm on every sheet (r4: T006's line ran 0.81 mm under the C)."""
    assert not any("Clock" in name for name in spec.DRAWING_PRECISION_BY_NAME)
    # The template's lines run CENTRE_MARK_LINE_BASE_MM past the rim at each
    # sheet's scale, and an extension adds to that (r4's T006 line).
    for teeth, printed in _CENTRE_LINE_R3_ENDS.items():
        assert _printed_centre_line_end(teeth, 0.0) == pytest.approx(printed, abs=0.0003)
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
            cone_sheet.TOOTH_THICKNESS_TEXT_AIR + _THICKNESS_AIR_MARGIN
        ), teeth


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
    """Rule 9 (screen of f21dfcdd2ba7): the keyed bore view is DETAIL A, its
    boundary ringing the bore on every keyed front view; a round-bore sheet
    has no enlarged view and no boundary. The letter stands outside its
    boundary, clear of the lines round it."""
    for teeth in spec.CONFIGURATION_TEETH:
        details = drawing.front_details(teeth)
        if not spec.keyed(teeth):
            assert details == ()
            continue
        assert [detail.letter for detail in details] == ["A"]
        bore = details[0]
        centre, radius = drawing.front_detail_on_sheet(teeth, bore)
        assert centre == pytest.approx(drawing.FRONT_CENTER)
        numerator, denominator = drawing._SCALE_BY_TEETH[teeth]
        ratio = numerator / denominator
        root = spec.floor_limits_mm(teeth)[0] * ratio / 2000.0
        assert spec.bore_dia_mm(teeth) * ratio / 2000.0 < radius < root
        # The letter sits in the web, clear of the boundary, the root
        # envelope and both centre-mark arms.
        letter = _letter_box(cone_sheet.detail_letter_xy(bore, centre, radius))
        inner, outer = _corner_radii(letter, centre)
        assert inner >= radius + _LETTER_AIR, teeth
        assert outer <= root - _LETTER_AIR, teeth
        assert letter.xmin > centre[0] + _LETTER_AIR and letter.ymax < centre[1] - _LETTER_AIR
        # T012's web dimension runs down left; the letter stands down right.
        assert abs(math.remainder(bore.letter_angle_deg - spec.WEB_REFERENCE_ANGLE_DEG, 360.0)) >= 90.0


def _callout_dimension(name: str, texts: dict[int, str]) -> object:
    from types import SimpleNamespace

    display = SimpleNamespace(
        GetText=lambda part: texts.get(part, ""),
        SetText=lambda part, text: texts.__setitem__(part, text),
    )
    return SimpleNamespace(name=name, GetSpecificAnnotation=lambda: display)


def test_settled_callouts_refuse_a_bare_dimension(monkeypatch: pytest.MonkeyPatch) -> None:
    # Farm proof 6fda5a4: T012..T024 printed the reamed bore's Ø and band
    # without REAM THRU / SEE NOTE 1, and T012 the web without its words,
    # their shared callouts reset by the keyed sheets' whole-model side-view
    # import (machinist review FIX, rules 4, 7, 12).
    from types import SimpleNamespace

    sheets: list[str] = []
    ddoc = SimpleNamespace(ActivateSheet=lambda name: sheets.append(name) or True)
    monkeypatch.setattr(drawing, "_early_bound", lambda obj, _iface: obj)
    monkeypatch.setattr(drawing, "dimension_name", lambda _adapter, item: item.name)
    adapter = SimpleNamespace(currentModel=ddoc)
    assert drawing.DIMENSION_CALLOUTS["BoreCutDia"].splitlines() == [
        "REAM THRU", drawing.BORE_NOTE_FLAG,
    ]
    below = {name: drawing.DIMENSION_CALLOUTS[name] for name in ("BoreCutDia", "WebMin")}
    printed = [
        _callout_dimension("BoreCutDia", {4: " "}),
        _callout_dimension("WebMin", {4: below["WebMin"].replace("\n", "\r\n")}),
    ]
    sheet = [("T012", printed, below, {})]
    with pytest.raises(RuntimeError, match="settling rebuild") as failure:
        drawing._assert_settled_callouts(adapter, sheet)
    message = str(failure.value)
    assert "T012 BoreCutDia: ' '" in message
    assert "T012 WebMin" not in message
    # A dimension the sheet does not hold is a fault, not a pass.
    with pytest.raises(RuntimeError, match="T030 KeyedBoreDia: not on the sheet"):
        drawing._assert_settled_callouts(
            adapter, [("T030", [], {"KeyedBoreDia": drawing.DIMENSION_CALLOUTS["KeyedBoreDia"]}, {})]
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
        "return finalize_drawing("
    )
    assert "_assert_settled_callouts(adapter, sheet_callouts)" in source


def test_settled_keyway_width_stays_ref(monkeypatch: pytest.MonkeyPatch) -> None:
    # Codjiflo 3549-r5: a later sheet's whole-model import could clear the
    # keyway width's REF parentheses; they are written again after the last
    # import and read back after the settling rebuild.
    from types import SimpleNamespace

    ddoc = SimpleNamespace(ActivateSheet=lambda _name: True)
    monkeypatch.setattr(drawing, "_early_bound", lambda obj, _iface: obj)
    monkeypatch.setattr(drawing, "dimension_name", lambda _adapter, item: item.name)
    monkeypatch.setattr(drawing, "set_dimension_callouts", lambda *_a, **_k: None)
    adapter = SimpleNamespace(currentModel=ddoc)
    width = _callout_dimension("KeywayWidth", {})
    sheet = [("T030", [width], {}, {})]
    with pytest.raises(RuntimeError, match="T030 KeywayWidth: \\('', ''\\)"):
        drawing._assert_settled_callouts(adapter, sheet)
    with pytest.raises(RuntimeError, match="T030: 0 KeywayWidth dimensions printed"):
        drawing._assert_settled_callouts(adapter, [("T030", [], {}, {})])
    monkeypatch.setattr(
        drawing,
        "set_reference_dimension",
        lambda _adapter, item, *, label: (
            item.GetSpecificAnnotation().SetText(1, "("),
            item.GetSpecificAnnotation().SetText(2, ")"),
        ),
    )
    drawing._rewrite_callouts(adapter, sheet)
    drawing._assert_settled_callouts(adapter, sheet)
    drawing._assert_settled_callouts(adapter, [("T024", [], {}, {})])


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
    rows = drawing.TOOTH_THICKNESS_ROWS
    air, nearest = cone_sheet.tooth_thickness_text_air(hung, rows, sheet="T012")
    assert air == pytest.approx(0.00025 - _PEN / 2.0, abs=1e-7)
    assert air < cone_sheet.TOOTH_THICKNESS_TEXT_AIR
    assert "glyph" in nearest
    shelf = drawing.tooth_thickness_shelf(12)
    tail = cone_sheet.DIMENSION_ARROW_LENGTH
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
    air, _nearest = cone_sheet.tooth_thickness_text_air(shelved, rows, sheet="T012")
    assert air >= cone_sheet.TOOTH_THICKNESS_TEXT_AIR
    with pytest.raises(ValueError, match="T012: thickness row .* printed 0 times"):
        cone_sheet.tooth_thickness_text_air(
            replace(shelved, spans=shelved.spans[1:]), rows, sheet="T012"
        )
    with pytest.raises(ValueError, match="T012: no shelf"):
        cone_sheet.tooth_thickness_text_air(
            replace(shelved, strokes=shelved.strokes[1:]), rows, sheet="T012"
        )


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

    matching = _Drawing(cone_sheet.DIMENSION_ARROW_LENGTH)
    cone_sheet.assert_dimension_arrow_length(matching)
    # swDetailingArrowLength, swDetailingNoOptionSpecified
    assert matching.Extension.calls == [(26, 0)]
    with pytest.raises(RuntimeError, match="drawing arrow length reads 3.175 mm"):
        cone_sheet.assert_dimension_arrow_length(_Drawing(0.003175))


# The functional root callout's widest row (the mate's, seventeen characters)
# is wider than either value.
_FLOOR_TEXT_HALF_WIDTH = (
    max(map(len, drawing.DIMENSION_CALLOUTS["FloorDia"].splitlines())) * 0.00185 / 2.0
)


def test_the_reopened_audit_reads_each_band_with_its_own_configuration_active(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The reopened audit reads every configuration's bands with that
    configuration active, and a failure names the call that raised (a raw
    COM error carries no member name, f68549253)."""
    from types import SimpleNamespace

    active: list[str] = []
    banded: list[tuple[str, str, int]] = []

    def activate(configuration: str) -> SimpleNamespace:
        active.append(configuration)
        return SimpleNamespace(is_success=True, data={"rebuilt": True}, error=None)

    def topology(_adapter, configuration, teeth, *, phase, measure_roots):
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
        readback.assert_saved_configuration_topology(adapter)
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
    # T012's .0674 web (RV-03) is separate from the ordinary target.
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
