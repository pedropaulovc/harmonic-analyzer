"""Offline contracts for the crank-drive-gear drawing.

The print is recreated under ``cad/docs/drawing-guidelines.md``: a 64T
gear with straight inclined teeth slipped onto the cone shaft's land carries
no datums and no frames, its blank, bore and south-entry sizes are native
model dimensions whose places and bands the PART owns, and the tooth system
it cannot dimension -- the tooth line (inclination, hand, crossing station)
and exact finite stock tangent-span limits -- lives in the gear-data block.
"""

from __future__ import annotations

import math
from pathlib import Path

import pytest

import _config
import cone_land_key
import cone_line
import build_dt_crank_drive_gear as part
import dt_cone_gear_shaft_spec
import cone_shaft_land_bands
import gear_seat_fit
import dt_crank_drive_gear_notes as notes
import dt_crank_drive_gear_spec as spec
import dt_crank_pinion_spec as pinion_spec
import draw_dt_crank_drive_gear as drawing
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS
from _printed_tolerance import printed_band_mm
from _drawing_registry import DRAWINGS_BY_NAME


def _source() -> str:
    return Path(drawing.__file__).read_text(encoding="utf-8")


def _build_source() -> str:
    return Path(part.__file__).read_text(encoding="utf-8")


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/dt-crank-drive-gear.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/dt-crank-drive-gear.pdf")
    assert drawing.PNG.as_posix().endswith("/png/dt-crank-drive-gear_drawing.png")
    assert (
        DRAWINGS_BY_NAME["dt_crank_drive_gear"].script == Path(drawing.__file__).resolve()
    )


def test_spec_is_the_single_source_of_the_marked_dimension_set() -> None:
    # The drift alarm: the part-side mark set and the drawing-side keep set are
    # BOTH the shared spec's map, so a rename in one script that is not
    # mirrored in the other fails here, offline.
    assert part.DRAWING_DIMENSIONS is spec.DRAWING_DIMENSIONS
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.FRONT_KEEP) | set(drawing.SECTION_KEEP)
    assert kept == marked == {
        "OutsideDia", "FaceWidth", "BoreDia", "KeywayWidth", "KeywayT",
        "BoreSouthChamferSize",
    }
    assert set(drawing.DIMENSION_CALLOUTS) <= kept


def test_the_outside_diameter_is_a_native_reference_sketch_dimension() -> None:
    # The OD is the first size the turner sets; drawing-simplicity-policy.md
    # `How the repository implements the guidelines`'s remedy is to MODEL it (a
    # construction sketch whose one driving dimension IS the value), not to
    # type it into the data block.
    build = _build_source()
    assert 'name_last_feature(adapter, "OutsideDiaReference")' in build
    assert 'name_dimensions(adapter, "OutsideDiaReference", ["OutsideDia"])' in build
    assert "_as_construction(adapter, tip_ref)" in build
    assert '_verify_named_dimension(adapter, "OutsideDia@OutsideDiaReference"' in build
    assert "OutsideDiaReference" in spec.DRAWING_DIMENSIONS
    # The turned blank pays the retained OD band at both published span limits.
    minimum_support = min(
        profile.support_radius_max_mm for _, profile in spec.STOCK_PROFILE_CORNERS
    )
    assert spec.OUTSIDE_DIA == spec.floor_inch_mm(
        2.0 * minimum_support - spec.OUTSIDE_DIA_TOLERANCE_MM,
        spec.DRAWING_PRECISION_BY_NAME["OutsideDia"],
    )
    # ... and therefore never as text beside the generating data.
    assert "OUTSIDE DIAMETER" not in notes.GEAR_DATA
    assert "FACE WIDTH" not in notes.GEAR_DATA


def test_the_face_width_is_a_named_driven_blank_dimension() -> None:
    build = _build_source()
    assert '"Boss-Extrude1").Name = "GearBlank"' in build
    assert 'name_dimensions(adapter, "GearBlank", ["FaceWidth"])' in build
    # Driven, so a default-name rename that resolved the wrong feature moves
    # the blank and the equation-neutral volume gate fails loud.
    assert "'\"FaceWidth\"'" in build
    assert spec.FACE_WIDTH == part.FACE_WIDTH
    assert spec.BORE_DIA == pytest.approx(part.BORE_DIAMETER)


def test_precision_is_authored_on_the_part_and_only_read_by_the_sheet() -> None:
    # drawing-simplicity-policy.md `How the repository implements the guidelines`: the places a dimension prints are part of the tolerance it
    # claims, so the model owns them.
    assert "draw_dt_crank_drive_gear.py" in PRECISION_MIGRATED_DRAWINGS
    source = _source()
    assert "set_dimension_precision" not in source
    assert "SetPrecision3" not in source
    assert "DIMENSION_PRECISION" not in source
    assert "assert_imported_precision(" in source
    assert "apply_drawing_precision(adapter, DRAWING_PRECISION)" in _build_source()


def test_bore_band_fits_the_keyed_land_at_every_limit() -> None:
    land_upper, land_lower = cone_shaft_land_bands.SECTION_DIA_BANDS[1]
    bore_upper, bore_lower = spec.BORE_DIA_BAND
    assert (
        bore_lower - land_upper,
        bore_upper - land_lower,
    ) == pytest.approx(gear_seat_fit.GEAR_SEAT_CLEARANCE)
    assert spec.BORE_DIA == pytest.approx(dt_cone_gear_shaft_spec.SECTION_DIAS[1])
    assert spec.BORE_DIA == pytest.approx(cone_land_key.LAND_DIA_MM)
    assert spec.DRAWING_DIMENSIONS["BoreProfile"] == {"BoreDia", "KeywayWidth", "KeywayT"}
    assert spec.DRAWING_PRECISION["BoreProfile"] == {
        "BoreDia": 4,
        "KeywayWidth": cone_land_key.KEYWAY_PLACES,
        "KeywayT": cone_land_key.KEYWAY_PLACES,
    }


def test_keyway_takes_the_key_and_leaves_the_web_target() -> None:
    # The keyway's numbers are cone_land_key's, not a fork.
    assert (spec.KEYWAY_WIDTH, spec.KEYWAY_WIDTH_BAND) == (
        cone_land_key.KEYWAY_WIDTH_MM, cone_land_key.KEYWAY_WIDTH_BAND
    )
    assert (spec.KEYWAY_T, spec.KEYWAY_T_BAND) == (
        cone_land_key.KEYWAY_T_MM, cone_land_key.KEYWAY_T_BAND
    )
    # The key slides in the keyway and clears its top at every limit.
    width_min = spec.KEYWAY_WIDTH + spec.KEYWAY_WIDTH_BAND[1]
    key_max = cone_land_key.KEY_SIZE_MM + cone_land_key.KEY_STOCK_BAND[0]
    assert width_min >= key_max
    t_min = spec.KEYWAY_T + spec.KEYWAY_T_BAND[1]
    s_max = cone_land_key.KEYSEAT_S_MM + cone_land_key.KEYSEAT_S_BAND[0]
    assert t_min - s_max - key_max > 0.0
    # The key keeps half its largest height in the keyseat at the keyseat's
    # edge: the smallest land, the widest keyseat, and S at its largest from
    # that land's far side (Codjiflo review of #2331).
    land_r_min = (
        cone_land_key.LAND_DIA_MM + cone_shaft_land_bands.GEAR_SEAT_BAND[1]
    ) / 2
    seat_half_max = (
        cone_land_key.KEYSEAT_WIDTH_MM + cone_land_key.KEYSEAT_WIDTH_BAND[0]
    ) / 2
    edge_depth = math.sqrt(land_r_min**2 - seat_half_max**2) - (s_max - land_r_min)
    assert cone_land_key.KEYSEAT_EDGE_DEPTH_MIN_MM == pytest.approx(edge_depth)
    assert edge_depth >= key_max / 2
    # The keyway top sits outside the bore, on +X.
    assert spec.BORE_DIA / 2 < spec.KEYWAY_TOP_OFFSET < spec.ROOT_DIA_MIN / 2
    # Rule 17: the web from the keyway's widest, deepest corner (T max, bore
    # min) to the minimum root circle meets the .080 target.
    corner = math.hypot(
        t_min + (spec.KEYWAY_T_BAND[0] - spec.KEYWAY_T_BAND[1])
        - (spec.BORE_DIA + spec.BORE_DIA_BAND[1]) / 2,
        (spec.KEYWAY_WIDTH + spec.KEYWAY_WIDTH_BAND[0]) / 2,
    )
    assert spec.KEYWAY_CORNER_RADIUS_MAX == pytest.approx(corner)
    assert spec.KEYWAY_WEB_MIN == pytest.approx(spec.ROOT_DIA_MIN / 2 - corner)
    assert spec.KEYWAY_WEB_MIN >= 0.080 * 25.4


def test_keyed_bore_area_matches_a_sampled_profile() -> None:
    radius = spec.BORE_DIA / 2
    half = spec.KEYWAY_WIDTH / 2
    top_x = spec.KEYWAY_TOP_OFFSET
    # Independent midpoint integration across y of the keyhole's chord.
    slices = 4000
    dy = 2 * radius / slices
    reference = 0.0
    for i in range(slices):
        y = -radius + (i + 0.5) * dy
        chord = math.sqrt(radius * radius - y * y)
        right = max(chord, top_x) if abs(y) <= half else chord
        reference += (chord + right) * dy
    assert part._keyed_bore_area(radius, half, top_x) == pytest.approx(reference, abs=0.005)


def test_south_chamfer_clears_the_collar_root_and_prints_title_block_band() -> None:
    grade = printed_band_mm(2, unit=spec.UNIT)
    assert spec.BORE_SOUTH_CHAMFER_MIN == pytest.approx(spec.BORE_SOUTH_CHAMFER - grade)
    assert spec.BORE_SOUTH_CHAMFER_MAX == pytest.approx(spec.BORE_SOUTH_CHAMFER + grade)
    assert spec.DRAWING_PRECISION["BoreSouthChamfer"]["BoreSouthChamferSize"] == 2
    # The mirrored collar root is the shaft spec's.
    assert spec._SHAFT_COLLAR_ROOT_RADIUS_MAX == pytest.approx(
        dt_cone_gear_shaft_spec.COLLAR_ROOT_RADIUS_MAX
    )
    assert spec.BORE_SOUTH_CHAMFER_MIN > dt_cone_gear_shaft_spec.COLLAR_ROOT_RADIUS_MAX
    assert '"BoreSouthChamfer", "BoreSouthChamferSize"' not in _build_source()


def test_chamfer_leaves_a_collar_bearing_annulus_and_bore_engagement() -> None:
    collar_min_r = (
        dt_cone_gear_shaft_spec.COLLAR_DIA
        + dt_cone_gear_shaft_spec.STOCK_DIA_BAND[1]
    ) / 2
    bore_max_r = (spec.BORE_DIA + spec.BORE_DIA_BAND[0]) / 2
    chamfer_max = spec.BORE_SOUTH_CHAMFER_MAX
    annulus = collar_min_r - bore_max_r - chamfer_max
    assert spec.COLLAR_BEARING_ANNULUS == pytest.approx(annulus)
    assert annulus > 0.0
    assert spec.FACE_WIDTH - spec.BORE_SOUTH_CHAMFER > spec.BORE_ENGAGEMENT_MIN
    assert spec.BORE_ENGAGEMENT_MIN == pytest.approx(
        spec.FACE_WIDTH + spec.FACE_WIDTH_BAND[1] - chamfer_max
    )
    assert spec.BORE_ENGAGEMENT_MIN > 0


def test_chamfer_volume_excludes_the_keyway() -> None:
    radius = spec.BORE_DIA / 2
    half = spec.KEYWAY_WIDTH / 2
    top_x = spec.KEYWAY_TOP_OFFSET
    leg = spec.BORE_SOUTH_CHAMFER

    # Independent: at each depth, the grown annulus less the keyway slot,
    # integrated across y by midpoints.
    def added(offset: float) -> float:
        grown = radius + offset
        slices = 800
        dy = 2 * grown / slices
        total = 0.0
        for i in range(slices):
            y = -grown + (i + 0.5) * dy
            outer = math.sqrt(grown * grown - y * y)
            inner = math.sqrt(max(radius * radius - y * y, 0.0))
            ring = 2 * (outer - inner)
            if abs(y) <= half:
                # The slot covers x in [inner, top_x] on +X.
                ring -= max(0.0, min(outer, top_x) - inner)
            total += ring * dy
        return total

    slices = 64
    reference = sum(
        added(leg * (i + 0.5) / slices) for i in range(slices)
    ) * leg / slices
    removed = part._bore_south_chamfer_volume(radius, half, top_x, leg)
    assert removed == pytest.approx(reference, rel=0.01)
    assert 0 < removed < math.pi * leg**2 * (radius + leg / 3)


def test_outside_diameter_prints_the_tip_band_the_mesh_stack_takes() -> None:
    # User, 2026-09-26: the tip diameter prints a band of its own on the
    # reference sketch the sheet imports; the fixed-centre mesh stack (user
    # ruling 2026-09-28) books that band at its closing corner.
    import crank_mesh_stack

    assert crank_mesh_stack.TIP_ROOT_BAND_RADIAL >= spec.OUTSIDE_DIA_TOLERANCE_MM / 2.0
    # The stack interface fixes both ends: the 64T north face touches T120;
    # the 16T remains longer but needs a measured axial overlap, not a simple
    # difference of face-width nominal sizes.
    t120_south = (
        cone_line.SHAFT_T120_STATION
        + cone_line.CONE_FACE_STATION_REFERENCE / 2.0
        - math.floor(cone_line.SEAT_PITCH * 1e4) / 1e4
    )
    gear_south = (
        spec.LAYOUT_CENTRE_STATION
        - spec.LAYOUT_FACE_WIDTH / 2.0
        + spec.SOUTH_FACE_SHIFT_NORTH
    )
    assert spec.FACE_WIDTH == round(t120_south - gear_south, 4)
    assert pinion_spec.FACE_WIDTH > spec.FACE_WIDTH


def test_print_carries_no_gdt_basic_dimensions_or_roughness() -> None:
    # drawing-guidelines.md rule 5 (avoid excessive GD&T): a gear on a shaft
    # land is not on the GD&T allowlist, so the end-face perpendicularity
    # frame, the tooth-tip runout frame and the bore datum are gone. Rule 6
    # puts no roughness on a gear's seat bore: it does not run.
    source = _source()
    for helper in (
        "add_datum_feature(",
        "add_feature_control_frame(",
        "set_basic_dimension(",
        "project_part_pmi(",
        "add_surface_finish(",
    ):
        assert helper not in source, helper
    assert not hasattr(spec, "GEOMETRIC_TOLERANCES_MM")
    assert not hasattr(spec, "GEOMETRIC_CONTROLS")
    assert not hasattr(spec, "PART_DATUMS")
    assert spec.SURFACE_FINISHES == ()
    assert "surface_finishes=SURFACE_FINISHES" in _build_source()


def test_gear_data_block_is_the_tooth_system_and_nothing_else() -> None:
    data = notes.GEAR_DATA
    for field in (
        "GEAR DATA",
        "NUMBER OF TEETH",
        "DIAMETRAL PITCH, NORMAL (CUTTER)",
        "PRESSURE ANGLE, NORMAL (CUTTER)",
        "DIAMETRAL PITCH, TRANSVERSE (REF)",
        "PRESSURE ANGLE, TRANSVERSE (REF)",
        "PITCH DIAMETER (REF)",
        "ROOT DIAMETER (REF)",
        "FORM CUTTER:  #2, 55-134T, FOR 69.185 VIRTUAL TEETH (REF)",
        "TOOTH LINE:  STRAIGHT, 13.0 DEG RIGHT HAND FROM AXIS",
        "TOOTH SPACES CENTRED ON AXIS AT:  .07 FROM CHAMFERED BORE FACE",
        f"BASE TANGENT SPAN OVER {spec.BASE_TANGENT_SPAN_TEETH} TEETH, NORMAL, ACCEPT ON THIS PART",
        "TRANSVERSE BACKLASH WITH MHA-DT-10, ACCEPT AT ASSEMBLY",
        "TOOTH FORM",
        "TOOTH EDGES",
        "TOOTH RUNOUT TO BORE",
        "MATES WITH",
    ):
        assert field in data, field
    # The retired pair-commissioning protocol (oil volumes, torque limits,
    # fixture runout, an ISO accuracy class no hobby shop can verify) may not
    # return with the thickness requirement.
    for banned in (
        "ISO 1328",
        "TORQUE",
        "C2C",
        "NONCONJUGATE",
        "X.XX",
        "FIXTURE RUNOUT",
        "NONSTANDARD",
        "SAME CUTTER",
        "LONG ADDENDUM",
    ):
        assert banned not in data, banned
    # Exact stock span is checked on the part; backlash belongs to the actual
    # assembly, never a circular-caliper shortcut.
    accepting = [
        line
        for line in data.splitlines()
        if any(owner in line for owner in ("ACCEPT ON THIS PART", "ACCEPT AT ASSEMBLY"))
    ]
    assert len(accepting) == 2
    assert "ACCEPT AT SETUP" not in data
    for line in accepting:
        assert "REF" not in line
    # ... and no OTHER row claims an acceptance band. A tooth count, the
    # cutter's pitch and the pressure angle are definitional; a row that
    # carries limits without saying who checks them is the defect.
    for line in data.splitlines()[1:]:
        if line in accepting:
            continue
        _, _, value = line.partition(":")
        assert " +" not in value and " TO " not in value, line
    source = _source()
    assert 'adapter, "Gear Data"' in source
    assert "Manufacturing Notes" not in source
    assert "Manufacturing Notes" not in _build_source()


@pytest.mark.parametrize("part_spec", (spec, pinion_spec))
def test_exact_stock_span_limits_book_printed_corners_on_the_inch_grid(part_spec) -> None:
    from stock_form_cutter import translation_for_pitch_tooth_thickness

    profile = part_spec.STOCK_PROFILE
    # The 64T band is booked about its standard-depth thickness; the 16T's
    # about its modelled thickness.
    if part_spec is spec:
        reference = spec.STANDARD_TRANSVERSE_TOOTH_THICKNESS
        deviations = spec.TOOTH_THICKNESS_DEVIATIONS
    else:
        reference = profile.pitch_tooth_thickness_mm
        deviations = (
            part_spec.TOOTH_THICKNESS_UPPER_DEVIATION,
            part_spec.TOOTH_THICKNESS_LOWER_DEVIATION,
        )
    raw_profiles = tuple(
        part_spec.stock_profile(tooth_thickness_mm=reference + deviation)
        for deviation in deviations
    )
    raw_spans = tuple(
        form.tangent_span_mm(part_spec.BASE_TANGENT_SPAN_TEETH, normal_plane=True)
        for form in raw_profiles
    )
    scale = 10**part_spec.BASE_TANGENT_SPAN_PLACES
    lower, upper = part_spec.BASE_TANGENT_SPAN_LIMITS_MM
    # Both ends rounded UP onto the printed inch grid: the lower never admits
    # a tooth thinner than the source allows, the upper keeps the nominal (the
    # thickest source tooth) accepted (codjiflo review of a9b4ad8a9).
    assert (lower, upper) == tuple(
        math.ceil(round(raw / part_spec.MM_PER_IN * scale, 6)) / scale * part_spec.MM_PER_IN
        for raw in (min(raw_spans), max(raw_spans))
    )
    assert min(raw_spans) <= lower and max(raw_spans) <= upper
    nominal = profile.tangent_span_mm(part_spec.BASE_TANGENT_SPAN_TEETH, normal_plane=True)
    assert lower <= nominal <= upper
    printed = notes.accept_limits_text(part_spec.BASE_TANGENT_SPAN_LIMITS_MM, 4)
    printed_low, printed_high = (
        float(value) * part_spec.MM_PER_IN for value in printed.split(" TO ")
    )
    assert printed_low <= nominal <= printed_high
    assert part_spec.BASE_TANGENT_SPAN_MM == pytest.approx(nominal)
    assert len(part_spec.STOCK_PROFILE_CORNERS) == 2 * 2
    for label, corner in part_spec.STOCK_PROFILE_CORNERS:
        span = corner.tangent_span_mm(part_spec.BASE_TANGENT_SPAN_TEETH, normal_plane=True)
        assert span == pytest.approx(lower if "span lower" in label else upper, abs=1e-9)
        assert corner.radial_translation_mm == pytest.approx(
            translation_for_pitch_tooth_thickness(
                part_spec.TEETH, part_spec.CUTTER_TEMPLATE, corner.pitch_tooth_thickness_mm,
                corner.helix_angle_deg,
            )
        )
        assert corner.blank_radius_mm <= (
            corner.support_radius_max_mm - corner.geometry_error_bound_mm
        )
        assert corner.tip_land_mm > 0.0
        with pytest.raises(ValueError, match="FINITE cutter support"):
            part_spec.stock_profile(
                outside_dia_mm=2.0 * (corner.support_radius_max_mm + 1.0 / scale),
                tooth_thickness_mm=corner.pitch_tooth_thickness_mm,
            )
    # Preserve the source capability, without interpreting it as ideal flank thinning.
    if part_spec is spec:
        assert deviations == tuple(
            _config.fit("crank_mesh", "gear64_tooth_thickness_deviations_mm")
        )
    assert not hasattr(part_spec, "BACKLASH_MM")
    assert not hasattr(notes, "NORMAL_TOOTH_THICKNESS_DEVIATIONS")


def test_the_data_block_states_the_tooth_line_as_it_stated_the_helix() -> None:
    # Owner ruling 2026-11-10 on #2332 (option A): straight teeth inclined
    # to the axis. No view shows a tooth's line on a drawn edge, so the
    # inclination, hand and crossing station print in the data block, as
    # the helix angle did (machinist review of farm proof r3 on #2482
    # refused a native 13 deg between reference rays in section A-A).
    data = notes.GEAR_DATA
    assert (
        f"TOOTH LINE:  STRAIGHT, {spec.TOOTH_INCLINATION_DEG:.1f} DEG RIGHT HAND FROM AXIS; "
        "AXES CROSSED WITH MHA-DT-10"
    ) in data
    assert (
        f"TOOTH SPACES CENTRED ON AXIS AT:  "
        f"{spec.inch_text(spec.TOOTH_SPACE_CROSSING, 2)} FROM CHAMFERED BORE FACE"
    ) in data
    for retired in ("HELIX", "LEAD", "SCREW SWEEP", "SECTION A-A"):
        assert retired not in data, retired
    lines = data.splitlines()
    assert len(lines) == 19
    assert lines[-1] == "MATES WITH:  CRANK PINION MHA-DT-10, 16T SPUR"
    assert "ToothLineReference" not in spec.DRAWING_DIMENSIONS
    assert "ToothLineReference" not in _build_source()
    # The ordinary +/-1 deg keeps the mid-face worst-corner crossed-mesh
    # backlash positive: the 64T normal pitch moves p_t sin(beta) per radian.
    import crank_mesh_stack
    transverse_pitch = math.pi * spec.PITCH_DIA / spec.TEETH
    pitch_shift = transverse_pitch * math.sin(
        math.radians(spec.TOOTH_INCLINATION_DEG)
    ) * math.radians(spec.TOOTH_INCLINATION_TOLERANCE_DEG)
    assert pitch_shift < crank_mesh_stack.standard_check().backlash_min_mm / 2.0
    # The hand follows the tooth line: azimuth advances counter-clockwise
    # about +z with increasing z (test_straight_gash).
    assert spec.TOOTH_HAND == "RIGHT HAND"
    assert spec.TOOTH_INCLINATION_DEG == pytest.approx(spec.STOCK_PROFILE.helix_angle_deg)
    assert spec.TOOTH_INCLINATION_DEG == spec.TOOTH_SPACE.inclination_deg


def test_gear_data_numbers_track_the_part_geometry() -> None:
    assert spec.TEETH == part.TEETH == spec.STOCK_PROFILE.teeth
    assert part.TOOTH_SPACE_FORM is spec.TOOTH_SPACE_FORM
    assert spec.CUTTER_TEMPLATE.diametral_pitch == spec.CUTTER_DIAMETRAL_PITCH
    assert spec.PITCH_DIA == pytest.approx(spec.TEETH * spec.MODULE_MM)
    # The pair shares normal pitch and pressure angle, but not cutter numbers.
    # The inclined teeth's transverse quantities and full depth follow its
    # normal system.
    cos_incline = math.cos(math.radians(spec.TOOTH_INCLINATION_DEG))
    assert spec.CUTTER_DIAMETRAL_PITCH == pytest.approx(spec.DIAMETRAL_PITCH / cos_incline)
    assert spec.CUTTER_DIAMETRAL_PITCH == pytest.approx(
        spec.MM_PER_IN / _config.machine("gear_train", "crank_drive_normal_module_mm")
    )
    assert math.tan(math.radians(spec.PRESSURE_ANGLE_DEG)) * cos_incline == pytest.approx(
        math.tan(math.radians(spec.CUTTER_PRESSURE_ANGLE_DEG))
    )
    assert spec.CUTTER_DIAMETRAL_PITCH == pinion_spec.DIAMETRAL_PITCH
    assert spec.CUTTER_PRESSURE_ANGLE_DEG == pinion_spec.PRESSURE_ANGLE_DEG
    assert spec.CUTTER_PRESSURE_ANGLE_DEG == _config.machine(
        "gear_train", "crank_drive_pressure_angle_deg"
    )
    assert spec.CUTTER_NUMBER == 2 != pinion_spec.CUTTER_NUMBER
    assert spec.CUTTER_TEETH_RANGE == (55, 134)
    assert spec.VIRTUAL_TEETH == pytest.approx(spec.TEETH / cos_incline**3)
    assert (
        spec.CUTTER_TEETH_RANGE[0] <= spec.VIRTUAL_TEETH <= spec.CUTTER_TEETH_RANGE[1]
    )
    assert not hasattr(spec, "HELIX_LEAD_MM")
    assert f"{spec.VIRTUAL_TEETH:.{spec.GEAR_DATA_REFERENCE_PLACES}f}" in notes.GEAR_DATA
    assert "flank_bound_mm=NATIVE_FLANK_BOUND_MM" in _build_source()
    profile = spec.STOCK_PROFILE
    assert spec.DEDENDUM_FACTOR == 1.25
    # Standard depth puts the cutter's reference pitch line on the gear's pitch
    # circle; the part is modelled at the thin-only band's maximum-material limit.
    standard = spec.stock_profile(tooth_thickness_mm=spec.STANDARD_TRANSVERSE_TOOTH_THICKNESS)
    assert standard.radial_translation_mm == pytest.approx(
        profile.pitch_radius_mm - profile.template.pitch_radius_mm
    )
    assert profile.pitch_tooth_thickness_mm == pytest.approx(
        spec.STANDARD_TRANSVERSE_TOOTH_THICKNESS + max(spec.TOOTH_THICKNESS_DEVIATIONS)
    )
    assert spec.WHOLE_DEPTH == pytest.approx(
        profile.blank_radius_mm - profile.root_radius_min_mm
    )
    assert spec.ROOT_DIA == spec.ROOT_DIA_MIN
    assert spec.ROOT_DIA_MIN == pytest.approx(2.0 * profile.root_radius_min_mm)
    assert spec.ROOT_DIA_MAX == pytest.approx(2.0 * profile.root_radius_max_mm)
    assert spec.ROOT_DIA_MIN < spec.ROOT_DIA_MAX
    assert spec.TOOL_PLUNGE_MM == pytest.approx(profile.plunge_mm)
    assert spec.TRANSVERSE_CIRCULAR_TOOTH_THICKNESS == pytest.approx(
        profile.pitch_tooth_thickness_mm
    )
    # The finite lower-count stock tool is deliberately not an ideal N64 profile.
    assert spec.CUTTER_TEMPLATE.reference_teeth == spec.CUTTER_TEETH_RANGE[0] < spec.TEETH
    assert spec.WHOLE_DEPTH < (1.0 + spec.DEDENDUM_FACTOR) * spec.NORMAL_MODULE_MM
    assert spec.NORMAL_MODULE_MM == pytest.approx(pinion_spec.MODULE_MM)


def test_notes_do_not_substitute_for_native_fit_dimensions() -> None:
    # The one shop requirement the title block's edge break would violate is
    # a gear-data row, not a free-floating note.
    assert not hasattr(notes, "DRAWING_NOTES")
    assert any(
        line.startswith("TOOTH EDGES:") and "DO NOT BREAK" in line
        for line in notes.GEAR_DATA.splitlines()
    )
    assert notes.SHAFT_MATE_NUMBER == _config.parts("dt-cone-gear-shaft")["number"]
    assert notes.KEY_MATE_NUMBER == _config.parts("dt-vn-cone-shaft-key")["number"]
    assert drawing.SHAFT_MATE_NAME == _config.parts("dt-cone-gear-shaft")["title"].upper()
    assert not hasattr(notes, "ATTACHMENT_PROCESS")
    assert not hasattr(notes, "ATTACHMENT_ALTERNATIVE")


def test_bore_and_keyway_dimensions_link_one_matched_fit_note() -> None:
    # The round band (.0008 wide) is narrower than the turned-diameter row, so
    # the fit route is a matched fit to the measured keyed land of MHA-DT-04
    # with an acceptance (rule 4). One feature, several tight dimensions: the
    # mates print once, in note 1, and every bore and keyway dimension links
    # it. The round bore takes rule 12's REAM now no flat is left to cut away.
    link = f"SEE NOTE {drawing.BORE_FIT_NOTE_NUMBER}"
    assert drawing.DIMENSION_CALLOUTS["BoreDia"] == f"REAM THRU\n{link}"
    # The keyway's width and T print the bare flag, as the keyed cone gears'
    # sheets do for the same keyway (rule 25: sheets agree).
    import draw_dt_cone_gear as cone_drawing

    for name in ("KeywayWidth", "KeywayT"):
        assert drawing.DIMENSION_CALLOUTS[name] == link, name
        assert (
            drawing.DIMENSION_CALLOUTS[name] == cone_drawing.DIMENSION_CALLOUTS[name]
        ), name
    for name in ("BoreDia", "KeywayWidth", "KeywayT"):
        callout = drawing.DIMENSION_CALLOUTS[name]
        assert notes.SHAFT_MATE_NUMBER not in callout, name
        assert notes.KEY_MATE_NUMBER not in callout, name
        assert "CLEARANCE" not in callout, name
    note = " ".join(line.strip() for line in drawing.BORE_FIT_NOTE.splitlines())
    assert note.startswith(f"{drawing.BORE_FIT_NOTE_NUMBER}. ")
    # The land is named by what it is (its key), not by an undefined label.
    assert f"THE KEYED LAND OF CONE GEAR SHAFT {notes.SHAFT_MATE_NUMBER}" in note
    assert "LAND 1" not in note
    assert notes.KEY_MATE_NUMBER in note
    # The clearances print as REF in the keyed cone gears' form, off the
    # same limits (draw_dt_cone_gear.sheet_notes on the same land).
    import draw_dt_cone_gear as cone_drawing

    (round_lo, round_hi), (key_lo, key_hi) = cone_drawing.bore_clearances_mm(30)
    reference = (
        f"(CLEARANCE {spec.inch_text(round_lo, 4)}-{spec.inch_text(round_hi, 4)} "
        f"ON \u00d8, {spec.inch_text(key_lo, 4)}-{spec.inch_text(key_hi, 4)} KEYWAY TO KEY)"
    )
    assert reference in " ".join(
        line.strip() for line in cone_drawing.sheet_notes(30).splitlines()
    )
    assert reference in note
    assert note.endswith("SLIDES ON, NO ROCK.")
    # Every line ends left of the keyway width's text above the block.
    assert max(len(line) for line in drawing.SHEET_NOTES.splitlines()) <= 51
    assert "FLAT" not in drawing.SHEET_NOTES
    assert len(drawing.SHEET_NOTES.splitlines()) <= 4
    assert "add_note(adapter, SHEET_NOTES, *NOTES_XY)" in _source()


def test_section_caption_prints_no_sheet_scale_and_names_the_turn() -> None:
    # Rule 9: a view's scale prints only when it differs from the sheet's;
    # A-A is at the sheet's 3:2, so its caption keeps only its name and
    # letter. A rotated view says so, in a note under the caption.
    assert drawing.SECTION_CAPTION_TEXT == "<VLNAME> <VLLABEL>"
    assert drawing.ROTATION_NOTE == "ROTATED 90\N{DEGREE SIGN} CCW"
    source = _source()
    assert "note.PropertyLinkedText = SECTION_CAPTION_TEXT" in source
    assert "add_note(adapter, ROTATION_NOTE, *ROTATION_NOTE_XY)" in source
    assert "SetUserPreferenceString(84" not in source
    assert "SCALE" not in drawing.ROTATION_NOTE



def test_sheet_runs_at_3_to_2_with_every_view_at_sheet_scale() -> None:
    # A 65 mm disc on a B sheet: at 1:1 two thirds of the sheet was empty and
    # the 64 teeth did not read as teeth. One scale for every view means the
    # title block's SCALE field is the whole truth and no view needs a note.
    assert drawing.SHEET_SCALE == (3.0, 2.0)
    assert drawing.VIEW_SCALE == (3, 2)
    assert _source().count("scale=VIEW_SCALE") == 3
    assert not hasattr(spec, "ISOMETRIC_VIEW_NOTE")


def test_hidden_lines_are_off_and_helical_tangent_edges_are_dropped() -> None:
    # The face view shows the bore and keyway in solid lines, and the centre
    # section cuts the bore open, so hidden edges add no requirement; the
    # helical flanks project dense tangent curves, removed from orthographic
    # views only.
    source = _source()
    assert (
        "for view in (front, section, iso):\n        set_hidden_lines_removed" in source
    )
    assert "set_hidden_lines_visible" not in source
    assert '_hide_tangent_edges(front, "front")' in source
    assert '_hide_tangent_edges(section, "section")' in source
    assert "_hide_tangent_edges(iso" not in source
    assert "SetDisplayTangentEdges2(0)" in source
    assert "GetDisplayTangentEdges2()" in source


# Dimension text centres on its keep point. Metrics off the round-bore 3:2 64T
# sheet of farm run 20260929T061401240Z (e0f6636): "(0.025-0.105 DIAMETRAL"
# is 52 mm for 22 characters, the five-line bore block stands 25 mm tall, and
# the title block's top edge is at 64.7 mm. A stacked tolerance puts the
# value on two lines.
_CHAR_WIDTH = 0.00236
_LINE_HEIGHT = 0.005
_TITLE_BLOCK_TOP = 0.0647
# Outline pad the layout audit adds round an uncropped view (cone-gear T084).
_VIEW_OUTLINE_PAD = 0.0056
# The native section caption, "SECTION A-A" alone, stands about 7 mm tall
# (its 6.35 mm SECTION letters) and is placed by its top centre; the turn's
# note hangs under it at the default note height.
_CAPTION_HEIGHT = 0.007
_NOTE_HEIGHT = 0.0035
# A free note at the document's default height: capitals about 2.6 mm a
# character (draw_mg_magnifying_wheel's rotation note) on a 6 mm line pitch.
_NOTE_CHAR_DEFAULT = 0.0026
_NOTE_PITCH_DEFAULT = 0.006


def _text_box(xy: tuple[float, float], callout: str, value: str) -> tuple[float, ...]:
    lines = callout.lstrip().split("\n")
    width = _CHAR_WIDTH * max(len(value), *(len(line) for line in lines))
    height = _LINE_HEIGHT * (2 + len(lines))
    return (xy[0] - width / 2, xy[1] - height / 2, xy[0] + width / 2, xy[1] + height / 2)


def _box_distance(box: tuple[float, ...], point: tuple[float, float]) -> float:
    dx = max(box[0] - point[0], 0.0, point[0] - box[2])
    dy = max(box[1] - point[1], 0.0, point[1] - box[3])
    return math.hypot(dx, dy)


def test_dimension_text_lands_clear_of_the_views_and_the_title_block() -> None:
    # Offline layout guard: every dimension is leadered or extended OUT of the
    # silhouette it measures, and nothing crosses into the title block's
    # bottom-right corner of the B sheet.
    half_od = drawing.HALF_OD
    assert half_od == pytest.approx(spec.OUTSIDE_DIA * 3 / (2 * 2000.0))
    for name, (x, y) in drawing.FRONT_KEEP.items():
        reach = math.hypot(x - drawing.FRONT_CENTER[0], y - drawing.FRONT_CENTER[1])
        assert reach > half_od + 0.010, name
    sx, sy = drawing.SECTION_CENTER
    face_half = drawing.FACE_WIDTH_HALF
    assert drawing.SECTION_KEEP["FaceWidth"][1] > sy + half_od
    positions = (
        *drawing.FRONT_KEEP.values(),
        *drawing.SECTION_KEEP.values(),
        drawing.GEAR_DATA_POS,
    )
    for x, y in positions:
        assert 0.012 < x < 0.420
        assert 0.012 < y < 0.267
        assert not (x > 0.216 and y < 0.070), (x, y)  # title-block keep-out
    # The three views march left to right without overlapping: face view,
    # centre section, isometric.
    assert drawing.FRONT_CENTER[0] + half_od < sx - face_half
    assert sx + face_half < drawing.ISO_CENTER[0] - half_od
    # The gear-data column stays left of every dimension the face view places.
    assert drawing.GEAR_DATA_POS[0] < min(x for x, _ in drawing.FRONT_KEEP.values())
    # The keyway T callout and the chamfer stand in the lane between the tooth
    # tips and the section's south face, the chamfer under T. The leg's text
    # sits left of its dimension line, which stands at the keep x (r1 of #1641
    # read the text's right edge back at the keep); the keyway width's text
    # sits right of its dimension line, on the shelf the line turns into
    # (farm proof of #2331 at 7f1dedc: line at the keep x, shelf to the right).
    keyway_t = _text_box(
        drawing.FRONT_KEEP["KeywayT"], drawing.KEYWAY_T_CALLOUT, "0.4030 \N{PLUS-MINUS SIGN}0.0035"
    )
    width_keep = drawing.FRONT_KEEP["KeywayWidth"]
    centred = _text_box(width_keep, drawing.KEYWAY_WIDTH_CALLOUT, "0.0625 +0.0020")
    shift = width_keep[0] - centred[0]
    keyway_width = (centred[0] + shift, centred[1], centred[2] + shift, centred[3])
    chamfer_keep = drawing.SECTION_KEEP["BoreSouthChamferSize"]
    centred = _text_box(
        chamfer_keep, drawing.DIMENSION_CALLOUTS["BoreSouthChamferSize"], "1.50"
    )
    shift = chamfer_keep[0] - centred[2]
    chamfer = (centred[0] + shift, centred[1], centred[2] + shift, centred[3])
    section_left = sx - face_half - _VIEW_OUTLINE_PAD
    for box in (keyway_t, keyway_width, chamfer):
        assert _box_distance(box, drawing.FRONT_CENTER) > half_od + _VIEW_OUTLINE_PAD + 0.003
        assert box[2] < section_left - 0.003
    assert chamfer[3] < keyway_t[1] - 0.003
    assert keyway_width[3] < chamfer[1] - 0.003
    # Under the teeth the width's text stands over the numbered notes.
    assert keyway_width[1] > drawing.NOTES_XY[1] + 0.002
    assert keyway_width[2] < 0.216 - 0.003  # left of the title block
    # The chamfer's leg dimension runs off the south face at bore height.
    assert sy - half_od < drawing.SECTION_KEEP["BoreSouthChamferSize"][1] < sy
    # The caption hangs under the section and over the title block, the
    # turn's note centred under it and still clear of the title block.
    cap_x, cap_top = drawing.SECTION_CAPTION_XY
    assert cap_x == pytest.approx(sx)
    assert cap_top < sy - half_od - 0.005
    rotation_x, rotation_top = drawing.ROTATION_NOTE_XY
    rotation_width = len(drawing.ROTATION_NOTE) * drawing.ROTATION_NOTE_CHAR
    assert rotation_x + rotation_width / 2.0 == pytest.approx(cap_x)
    assert rotation_top < cap_top - _CAPTION_HEIGHT
    assert rotation_top - _NOTE_HEIGHT > _TITLE_BLOCK_TOP + 0.003
    assert rotation_top - _NOTE_HEIGHT > 0.070  # the title-block keep-out's top
    # The numbered notes stand at the lower left: under the round bore's
    # callout and the face view, left of the title block, inside the border.
    notes_left, notes_top = drawing.NOTES_XY
    note_lines = drawing.SHEET_NOTES.splitlines()
    notes_right = notes_left + _NOTE_CHAR_DEFAULT * max(len(line) for line in note_lines)
    notes_bottom = notes_top - _NOTE_PITCH_DEFAULT * len(note_lines)
    bore = _text_box(drawing.FRONT_KEEP["BoreDia"], drawing.BORE_CALLOUT, "9.525 +0.046")
    assert notes_top < bore[1] - 0.003
    assert notes_top < drawing.FRONT_CENTER[1] - half_od - 0.005
    assert notes_left > 0.0127 and notes_bottom > 0.0127 + 0.003
    assert notes_right < 0.216 - 0.003  # left of the title block


# The gear-data block at its 2.5 mm note height, measured on farm run
# 20261001T110844152Z: rows 3.50 mm apart from a cap top 0.3 mm under the
# anchor, the last row's descenders 0.6 mm under top - rows * pitch, and the
# 95-character tooth-thickness row 165 mm wide (1.74 mm a character). The tip
# diameter's "Ø65.21 ±0.1" printed 26.2 mm wide and 3.9 mm tall.
_NOTE_LINE_PITCH = 0.0035
_NOTE_DESCENDER = 0.0006
_NOTE_CHAR_WIDTH = 0.00174
_TIP_DIA_TEXT = f"Ø{spec.OUTSIDE_DIA:.2f} ±{spec.OUTSIDE_DIA_TOLERANCE_MM:g}"
_TIP_DIA_TEXT_HEIGHT = 0.0039


def _gear_data_box() -> tuple[float, ...]:
    rows = notes.GEAR_DATA.splitlines()
    left, top = drawing.GEAR_DATA_POS
    width = _NOTE_CHAR_WIDTH * max(len(row) for row in rows)
    bottom = top - len(rows) * _NOTE_LINE_PITCH - _NOTE_DESCENDER
    return (left, bottom, left + width, top)


def _tip_dia_text_box(centre: tuple[float, float]) -> tuple[float, ...]:
    half_w = _CHAR_WIDTH * len(_TIP_DIA_TEXT) / 2.0
    half_h = _TIP_DIA_TEXT_HEIGHT / 2.0
    x, y = centre
    return (x - half_w, y - half_h, x + half_w, y + half_h)


def test_tip_diameter_block_stands_clear_of_the_gear_data_teeth_and_section() -> None:
    # The tip value with its mesh callout under it hangs up and right of the
    # teeth: right of every gear-data row at its height, over the tooth tips
    # with room for the leader's shoulder, and left of the face-width block.
    block = _gear_data_box()
    tip_keep = drawing.FRONT_KEEP["OutsideDia"]
    tip = _text_box(tip_keep, drawing.TIP_DIA_CALLOUT, _TIP_DIA_TEXT)
    rows = notes.GEAR_DATA.splitlines()
    left, top = drawing.GEAR_DATA_POS
    for index, row in enumerate(rows):
        row_top = top - index * _NOTE_LINE_PITCH
        row_bottom = row_top - _NOTE_LINE_PITCH - _NOTE_DESCENDER
        if row_bottom < tip[3] and row_top > tip[1]:
            assert left + _NOTE_CHAR_WIDTH * len(row) < tip[0] - 0.005, row
    assert block[3] > tip[3]
    assert _box_distance(tip, drawing.FRONT_CENTER) > drawing.HALF_OD + 0.005
    face = _text_box(
        drawing.SECTION_KEEP["FaceWidth"], drawing.FACE_WIDTH_CALLOUT, "7.2244 ±0.025"
    )
    assert tip[2] < face[0] - 0.005
    # The face-width block stands above the section and left of its south
    # witness line, so neither witness line runs through its text.
    sx, sy = drawing.SECTION_CENTER
    assert face[1] > sy + drawing.HALF_OD
    assert face[2] < sx - drawing.FACE_WIDTH_HALF


def test_part_stamps_make_critical_properties() -> None:
    build = _build_source()
    assert "apply_drawing_properties" in build
    assert "clear_dimensions_for_drawing" in build

    config = _config.parts("dt-crank-drive-gear")
    # The FINISH field states the surface condition only: how the teeth are
    # made is the PROCESS row's job, and saying it twice is over-specification.
    assert config["finish"] == "oiled"
    assert not any(
        word in config["finish"].lower() for word in ("cut", "hob", "shaper", "machin")
    )
    assert "gear cutting" in config["process"]
    assert int(config["quantity"]) == 1


def test_outside_dia_reference_is_saved_hidden_and_imported_per_view() -> None:
    # #880: a reference sketch owns printed dimensions but no geometry, so the
    # part saves it hidden (no assembly instance renders it) and the drawing
    # shows it per view through _drawing_hidden_sketches to import them.
    build = Path(part.__file__).read_text(encoding="utf-8")
    blank = 'blank_sketch(adapter, "OutsideDiaReference")'
    assert blank in build
    assert build.index(blank) < build.rindex("save_simplified_part(adapter, PART_NAME")
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "from _drawing_hidden_sketches import curate_view_dimensions" in source
    assert "    curate_view_dimensions,\n" not in source.replace("\r\n", "\n")
    assert "OutsideDiaReference" in spec.DRAWING_DIMENSIONS


def test_face_view_leaders_have_separate_landings() -> None:
    # The round diameter and keyway dimensions need room around the bore; the
    # tip-diameter arrow belongs on the near tooth silhouette, and only the
    # keyway T dimension (it spans the axis) may meet the A-A cutting line.
    import _drawing_leaders as leaders

    cx, cy = drawing.FRONT_CENTER
    r = drawing.BORE_SHEET_RADIUS
    assert r == pytest.approx(spec.BORE_DIA * 1.5 / 2000.0)
    tip_text = drawing.FRONT_KEEP["OutsideDia"]
    bore_text = drawing.FRONT_KEEP["BoreDia"]
    t_text = drawing.FRONT_KEEP["KeywayT"]
    width_text = drawing.FRONT_KEEP["KeywayWidth"]
    assert bore_text[0] < cx and bore_text[1] < cy
    assert t_text[0] > cx and t_text[1] > cy
    assert width_text[0] > cx and width_text[1] < cy - drawing.HALF_OD
    assert tip_text[0] > cx and tip_text[1] > cy + drawing.HALF_OD
    angle = math.atan2(bore_text[1] - cy, bore_text[0] - cx)
    bore = [(bore_text, (cx + r * math.cos(angle), cy + r * math.sin(angle)))]
    sheet = drawing.VIEW_SCALE[0] / (1000 * drawing.VIEW_SCALE[1])
    top_x = spec.KEYWAY_TOP_OFFSET * sheet
    half_width = spec.KEYWAY_WIDTH / 2 * sheet
    # T: extension lines up from 1 mm off the far wall and the keyway top on
    # the axis to 1 mm past its dimension line, which runs out to the text.
    tx, ty = t_text
    keyway_t = [
        ((cx - r, cy + 0.001), (cx - r, ty + 0.001)),
        ((cx + top_x, cy + 0.001), (cx + top_x, ty + 0.001)),
        ((cx - r, ty), (tx, ty)),
    ]
    # The keyway width's ink as the farm read it: extension lines from 1 mm
    # off the keyway's top corners to 1 mm past the vertical dimension line at
    # the keep x, two outside arrows' lines, the lower one running down to a
    # shelf 10 mm under the keep, and no ink between the arrows.
    wx, wy = width_text
    ext_gap = 0.001
    keyway_width = [
        ((cx + top_x + ext_gap, cy - half_width), (wx + ext_gap, cy - half_width)),
        ((cx + top_x + ext_gap, cy + half_width), (wx + ext_gap, cy + half_width)),
        ((wx + 0.025, wy - 0.010), (wx, wy - 0.010)),
        ((wx, wy - 0.010), (wx, cy - half_width)),
        ((wx, cy + half_width), (wx, cy + half_width + 0.0064)),
    ]
    # The broken leader leaves the shelf under the callout's last line at
    # its end nearer the gear, aimed at the centre.
    tip_box = _text_box(tip_text, drawing.TIP_DIA_CALLOUT, _TIP_DIA_TEXT)
    near_end = (tip_box[0], tip_box[1])
    aim = math.atan2(near_end[1] - cy, near_end[0] - cx)
    rim = (math.cos(aim) * drawing.HALF_OD, math.sin(aim) * drawing.HALF_OD)
    old_tip = [(near_end, (cx - rim[0], cy - rim[1]))]
    new_tip = [(near_end, (cx + rim[0], cy + rim[1]))]
    reach = drawing.HALF_OD + drawing.SECTION_LINE_OVERRUN
    # The chain and, 2 mm in from each end, the A-A arrows' 12 mm stems on
    # the keyway side (farm proof of #2331): the stem the width's extension
    # line struck when the width stood past the teeth.
    stem_x = reach - 0.002
    cutting_line = [
        ((cx - reach, cy), (cx + reach, cy)),
        ((cx - stem_x, cy + 0.012), (cx - stem_x, cy)),
        ((cx + stem_x, cy + 0.012), (cx + stem_x, cy)),
    ]
    assert leaders.distance_to_point(old_tip[0], (cx, cy)) < drawing.TIP_DIA_KEEP_OUT
    leaders.assert_leaders_clear(
        {"OutsideDia": new_tip, "BoreDia": bore, "KeywayT": keyway_t,
         "KeywayWidth": keyway_width},
        centre=(cx, cy),
        keep_out={"OutsideDia": drawing.TIP_DIA_KEEP_OUT},
        lands_within={
            "OutsideDia": drawing.TIP_DIA_LANDING,
            "BoreDia": drawing.BORE_LANDING,
            "KeywayT": drawing.BORE_LANDING,
            "KeywayWidth": drawing.BORE_LANDING,
        },
        label="gear bore layout",
    )
    leaders.assert_leaders_clear(
        {
            "OutsideDia": new_tip,
            "BoreDia": bore,
            "KeywayWidth": keyway_width,
            "SectionLine": cutting_line,
        },
        centre=(cx, cy),
        keep_out={},
        lands_within={
            "OutsideDia": drawing.TIP_DIA_LANDING,
            "BoreDia": drawing.BORE_LANDING,
            "KeywayWidth": drawing.BORE_LANDING,
            "SectionLine": drawing.SECTION_LINE_LANDING,
        },
        label="gear leaders vs A-A",
    )
    # The cut runs along the bore axis through the keyway: the tip leader stays
    # above it, the bore leader below it.
    assert min(new_tip[0][0][1], new_tip[0][1][1]) > cy + 0.005
    assert max(bore[0][0][1], bore[0][1][1]) < cy


def test_both_shop_gears_state_the_source_owned_tooth_runout_not_a_form_class() -> None:
    import dt_crank_pinion_notes as pinion_notes

    setup_tir = _config.fit("crank_mesh", "tooth_cutting_runout_tir_mm")
    for part_spec, part_notes in ((spec, notes), (pinion_spec, pinion_notes)):
        assert part_spec.TOOTH_RUNOUT_TIR_MM == setup_tir
        assert "AGMA" not in part_notes.GEAR_DATA
        assert not hasattr(part_spec, "GEOMETRIC_CONTROLS")
        assert not hasattr(part_spec, "GEOMETRIC_TOLERANCES_MM")
    # Each finished-bore eccentricity is half its own stated TIR.
    assert (spec.TOOTH_RUNOUT_TIR_MM + pinion_spec.TOOTH_RUNOUT_TIR_MM) / 2.0 == setup_tir
    # The 64T: one GEAR DATA row accepts the finished part's tooth runout to
    # its bore at crank_mesh's value, with no setup or workholding words;
    # under the shop's runout row (.001 per inch of the Ø2.8 blank) it names
    # its mate, whose backlash row is the mesh's acceptance.
    tir = spec.inch_text(spec.TOOTH_RUNOUT_TIR_MM, 3)
    lines = notes.GEAR_DATA.splitlines()
    runout_rows = [line for line in lines if "TIR" in line]
    assert len(runout_rows) == 1
    runout_row = runout_rows[0]
    assert "RUNOUT TO BORE" in runout_row and f"{tir} TIR MAX" in runout_row
    for method in ("SETUP", "ARBOR", "FIXTURE", "INDICATE"):
        assert method not in runout_row, method
    assert spec.TOOTH_RUNOUT_TIR_MM < 0.001 * spec.OUTSIDE_DIA
    assert "MHA-DT-10" in runout_row
    assert any(line.startswith("TRANSVERSE BACKLASH WITH MHA-DT-10") for line in lines)
    # The 64T's block keeps main's 19 lines (the tooth line and its crossing
    # station replaced the helix and lead rows). The tooth-line row, 81
    # characters, is now its widest; farm r7 printed it clear of the tooth
    # tips. An extra line or a wider row runs its last rows into the tips.
    assert len(lines) == 19
    assert max(len(line) for line in lines) <= 81
    assert len(runout_row) <= max(len(line) for line in lines if line is not runout_row)
