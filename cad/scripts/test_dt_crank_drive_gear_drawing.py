"""Offline contracts for the crank-drive-gear drawing.

The print is recreated under ``cad/docs/drawing-simplicity-policy.md``: a 64T
helical gear slipped onto the cone shaft's land carries no datums and no frames,
its blank, bore and south-entry sizes are native model dimensions whose places
and bands the PART owns, and the tooth system it cannot dimension -- helix
angle, hand, tooth thinning -- lives in the gear-data block.
"""

from __future__ import annotations

import math
from pathlib import Path

import pytest

import _config
import build_dt_crank_drive_gear as part
import dt_cone_gear_shaft_spec
import cone_shaft_land_bands
import gear_seat_fit
import dt_crank_drive_gear_notes as notes
import dt_crank_drive_gear_spec as spec
import dt_crank_pinion_spec as pinion_spec
import draw_dt_crank_drive_gear as drawing
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS
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
        "OutsideDia", "FaceWidth", "BoreDia", "BoreAF", "BoreSouthChamferSize"
    }
    assert set(drawing.DIMENSION_CALLOUTS) <= kept


def test_the_outside_diameter_is_a_native_reference_sketch_dimension() -> None:
    # The helix recipe grows the teeth off a ROOT cylinder blank, so no solid
    # feature owns the tip circle -- and the OD is the first size the turner
    # sets. Rule 2's remedy is to MODEL it (a construction sketch whose one
    # driving dimension IS the value), not to type it into the data block.
    build = _build_source()
    assert 'name_last_feature(adapter, "OutsideDiaReference")' in build
    assert 'name_dimensions(adapter, "OutsideDiaReference", ["OutsideDia"])' in build
    assert "_as_construction(adapter, tip_ref)" in build
    assert '_verify_named_dimension(adapter, "OutsideDia@OutsideDiaReference"' in build
    assert "OutsideDiaReference" in spec.DRAWING_DIMENSIONS
    # #906: normal-defined -- the transverse pitch circle plus the CUTTER's
    # addendum on each side, the blank turned 0.05 long over it (R9-56).
    assert spec.LONG_ADDENDUM_MM == 0.05
    assert spec.OUTSIDE_DIA == pytest.approx(
        part.TEETH / part.DP * spec.MM_PER_IN
        + 2.0 * (spec.MM_PER_IN / spec.CUTTER_DIAMETRAL_PITCH + spec.LONG_ADDENDUM_MM)
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
    # Rule 2: the places a dimension prints are part of the tolerance it
    # claims, so the model owns them.
    assert spec.DRAWING_PRECISION_BY_NAME == {
        "OutsideDia": 2,
        "FaceWidth": 4,
        "BoreDia": 3,
        "BoreAF": 3,
        "BoreSouthChamferSize": 2,
    }
    assert "draw_dt_crank_drive_gear.py" in PRECISION_MIGRATED_DRAWINGS
    source = _source()
    assert "set_dimension_precision" not in source
    assert "SetPrecision3" not in source
    assert "DIMENSION_PRECISION" not in source
    assert "assert_imported_precision(" in source
    assert "apply_drawing_precision(adapter, DRAWING_PRECISION)" in _build_source()


def test_bore_bands_fit_both_sec1_land_dimensions_at_every_limit() -> None:
    land_upper, land_lower = cone_shaft_land_bands.SECTION_DIA_BANDS[1]
    bore_upper, bore_lower = spec.BORE_DIA_BAND
    assert (
        bore_lower - land_upper,
        bore_upper - land_lower,
    ) == pytest.approx(gear_seat_fit.GEAR_SEAT_CLEARANCE)
    assert spec.BORE_DIA == pytest.approx(dt_cone_gear_shaft_spec.SECTION_DIAS[1])
    assert spec.BORE_AF == cone_shaft_land_bands.SECTION_FLAT_AF[1] == 8.763
    bore_upper, bore_lower = spec.BORE_AF_BAND
    land_upper, land_lower = cone_shaft_land_bands.FLAT_AF_BAND
    assert (
        bore_lower - land_upper,
        bore_upper - land_lower,
    ) == pytest.approx(gear_seat_fit.FLAT_AF_CLEARANCE)
    assert spec.BORE_AF_BAND == pytest.approx((0.020, 0.010))
    assert set(spec.DRAWING_DIMENSIONS["BoreProfile"]) == {"BoreDia", "BoreAF"}
    assert set(spec.DRAWING_PRECISION["BoreProfile"]) == {"BoreDia", "BoreAF"}


def test_D_bore_cut_area_is_smaller_than_a_round_bore() -> None:
    r = spec.BORE_DIA / 2.0
    flat_x = spec.BORE_AF - r
    assert 0 < flat_x < r
    # The closing chord is to the +X side of centre; the remaining arc goes
    # through -X (not the short discarded cap on +X).
    assert 360.0 - 2.0 * math.degrees(math.acos(flat_x / r)) > 180.0
    segment = r * r * math.acos(flat_x / r) - flat_x * math.sqrt(r * r - flat_x * flat_x)
    assert segment > 0
    assert math.pi * r * r - segment > 0


def test_south_chamfer_covers_print_worst_end_mill_crescent() -> None:
    shaft_r = (
        dt_cone_gear_shaft_spec.SECTION_DIAS[1]
        + cone_shaft_land_bands.SECTION_DIA_BANDS[1][0]
    ) / 2
    flat_offset = (
        cone_shaft_land_bands.SECTION_FLAT_AF[1]
        + cone_shaft_land_bands.FLAT_AF_BAND[1]
        - shaft_r
    )
    half_chord = math.sqrt(shaft_r**2 - flat_offset**2)
    cutter_r = spec.MIN_FLAT_CUTTER_RADIUS
    assert cutter_r == 4.0  # minimum Ø8 cutter: anything larger leaves less runout

    def horn_plus_runout(y: float) -> float:
        return (
            math.sqrt(shaft_r**2 - y**2) - flat_offset
            + cutter_r - math.sqrt(cutter_r**2 - y**2)
        )

    # The derivative is y(1/sqrt(Rc²-y²)-1/sqrt(Rshaft²-y²))>0
    # throughout the half-chord because Rc<Rshaft: the corner is the max.
    samples = [horn_plus_runout(half_chord * i / 128) for i in range(129)]
    assert samples == sorted(samples)
    assert spec.MAX_FLAT_CRESCENT == pytest.approx(samples[-1])
    assert spec.MAX_FLAT_CRESCENT == pytest.approx(0.959821716, abs=1e-8)
    assert spec.BORE_SOUTH_CHAMFER == 1.00
    assert spec.BORE_SOUTH_CHAMFER_BAND == (0.10, 0.00)
    assert spec.MAX_FLAT_CRESCENT < spec.BORE_SOUTH_CHAMFER + spec.BORE_SOUTH_CHAMFER_BAND[1]


def test_chamfer_leaves_a_collar_bearing_annulus_and_flat_engagement() -> None:
    collar_min_r = (
        dt_cone_gear_shaft_spec.COLLAR_DIA
        + dt_cone_gear_shaft_spec.STOCK_DIA_BAND[1]
    ) / 2
    bore_max_r = (spec.BORE_DIA + spec.BORE_DIA_BAND[0]) / 2
    chamfer_max = spec.BORE_SOUTH_CHAMFER + spec.BORE_SOUTH_CHAMFER_BAND[0]
    annulus = collar_min_r - bore_max_r - chamfer_max
    assert spec.COLLAR_BEARING_ANNULUS == pytest.approx(annulus)
    assert annulus == pytest.approx(2.0221)
    assert spec.FACE_WIDTH - spec.BORE_SOUTH_CHAMFER == pytest.approx(6.2113)
    assert spec.FLAT_ENGAGEMENT_MIN == pytest.approx(
        spec.FACE_WIDTH + spec.FACE_WIDTH_BAND[1] - chamfer_max
    )
    assert spec.FLAT_ENGAGEMENT_MIN == pytest.approx(6.0863)
    assert spec.FLAT_ENGAGEMENT_MIN > 0


def test_chamfer_volume_tracks_both_D_bore_walls() -> None:
    radius = spec.BORE_DIA / 2
    flat_x = spec.BORE_AF - radius
    leg = spec.BORE_SOUTH_CHAMFER
    # Independent axial integration of the D-shaped section: the circular
    # arc and the straight flat both advance by the 45° leg at the mouth.
    def area(offset: float) -> float:
        r, chord = radius + offset, flat_x + offset
        return math.pi * r * r - (
            r * r * math.acos(chord / r)
            - chord * math.sqrt(r * r - chord * chord)
        )

    baseline = area(0)
    slices = 1024
    reference = sum(
        (area(leg * i / slices) - baseline) * (0.5 if i in (0, slices) else 1)
        for i in range(slices + 1)
    ) * leg / slices
    removed = part._bore_south_chamfer_volume(radius, flat_x, leg)
    assert removed == pytest.approx(reference, abs=0.001)
    assert 0 < removed < math.pi * leg**2 * (radius + leg / 3)


def test_outside_diameter_prints_the_tip_band_the_mesh_stack_takes() -> None:
    # User, 2026-09-26: the tip diameter prints +/-0.10 of its own on the
    # reference sketch the sheet imports; the fixed-centre mesh stack (user
    # ruling 2026-09-28) books that band at its closing corner.
    import crank_mesh_stack

    assert spec.OUTSIDE_DIA_TOLERANCE_MM == 0.10
    assert spec.DRAWING_PRECISION["OutsideDiaReference"]["OutsideDia"] == 2
    assert crank_mesh_stack.TIP_ROOT_BAND_RADIAL >= spec.OUTSIDE_DIA_TOLERANCE_MM / 2.0
    assert (
        'set_dimension_symmetric_tolerance(\n        adapter, "OutsideDiaReference", '
        '"OutsideDia", OUTSIDE_DIA_TOLERANCE_MM\n    )'
    ) in _build_source()
    # The stack interface fixes both ends: the 64T north face touches T120;
    # the 16T remains longer but needs a measured axial overlap, not a simple
    # difference of face-width nominal sizes.
    assert spec.FACE_WIDTH == 7.2113
    assert spec.FACE_WIDTH_BAND == (0.025, -0.025)
    assert spec.DRAWING_PRECISION["GearBlank"]["FaceWidth"] == 4
    assert pinion_spec.FACE_WIDTH == 11.6


def test_print_carries_no_gdt_or_basic_dimensions() -> None:
    # Rules 3-4: a gear on a shaft land is not on the GD&T allowlist, so the
    # end-face perpendicularity frame, the tooth-tip runout frame and the bore
    # datum are gone. The ONE roughness it keeps is rule 5's exception -- the
    # bore is a size-toleranced fit, and a fit depends on the peaks as well as
    # on the size.
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
    assert not hasattr(spec, "PART_DATUMS")
    assert [control.key for control in spec.SURFACE_FINISHES] == [
        "crank_drive_gear_bore"
    ]
    assert spec.SURFACE_FINISHES[0].face.diameter_mm == spec.BORE_DIA
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
        "PITCH DIAMETER (mm, REF)",
        "ROOT DIAMETER (mm, REF)",
        "WHOLE DEPTH (mm, REF)",
        "HELIX ANGLE AT PITCH DIAMETER",
        "CIRCULAR TOOTH THICKNESS AT PITCH DIA, NORMAL (mm), ACCEPT ON THIS PART",
        "TRANSVERSE BACKLASH WITH MHA-DT-010, ACCEPT AT ASSEMBLY (mm)",
        "TOOTH FORM",
        "MATES WITH",
    ):
        assert field in data, field
    # The retired pair-commissioning protocol (oil volumes, torque limits,
    # fixture runout, an ISO accuracy class no hobby shop can verify) may not
    # return with the thickness requirement.
    for banned in (
        "ISO 1328",
        "BASE-TANGENT SPAN",
        "TORQUE",
        "C2C",
        "NONCONJUGATE",
        "X.XX",
        "RUNOUT",
    ):
        assert banned not in data, banned
    # Each of the two rows that is NOT reference-only says where it is accepted,
    # so a part inspector is never asked to establish a pair result: the
    # thickness is checkable on this part with a gear-tooth caliper, while the
    # backlash depends on the operating centre distance and shaft angle, which
    # belong to the assembly. (codex iter1 blocked on exactly that ambiguity.)
    accepting = [
        line
        for line in data.splitlines()
        if "ACCEPT ON THIS PART" in line or "ACCEPT AT ASSEMBLY" in line
    ]
    assert len(accepting) == 2
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
    assert 'adapter, "Manufacturing Notes"' in source


def test_tooth_thickness_is_a_toleranced_requirement_not_a_ref_consequence() -> None:
    # The generating numbers are REF because the cutter produces them, but the
    # tooth THICKNESS is the pair's one tooth-system acceptance size: the 16T it
    # runs against is cut to full thickness, so all of the mesh's backlash comes
    # off this gear's flanks. Its band is the named fit class read backwards,
    # which is why it is asymmetric about the nominal the model is cut to.
    low, high = _config.fit("gear_mesh", "backlash_mm")
    assert notes.BACKLASH_MM == [low, high]
    assert notes.TOOTH_THICKNESS_DEVIATIONS == (
        pytest.approx(spec.BACKLASH_MM - low),
        pytest.approx(-(high - spec.BACKLASH_MM)),
    )
    thickest = (
        spec.TRANSVERSE_CIRCULAR_TOOTH_THICKNESS + (notes.TOOTH_THICKNESS_DEVIATIONS[0])
    )
    thinnest = (
        spec.TRANSVERSE_CIRCULAR_TOOTH_THICKNESS + (notes.TOOTH_THICKNESS_DEVIATIONS[1])
    )
    # Over the whole band the assembled pair still meshes inside the fit class:
    # the thickest tooth leaves the minimum backlash, the thinnest the maximum.
    assert notes.STANDARD_TOOTH_THICKNESS - thickest == pytest.approx(low)
    assert notes.STANDARD_TOOTH_THICKNESS - thinnest == pytest.approx(high)
    data = notes.GEAR_DATA
    # #906: the caliper reads the band square to the helix.
    assert notes.NORMAL_TOOTH_THICKNESS_DEVIATIONS == (0.098, -0.049)
    assert f"{spec.NORMAL_CIRCULAR_TOOTH_THICKNESS:.3f} +0.098 / -0.049" in data
    assert spec.NORMAL_CIRCULAR_TOOTH_THICKNESS == pytest.approx(
        spec.TRANSVERSE_CIRCULAR_TOOTH_THICKNESS
        * math.cos(math.radians(spec.HELIX_ANGLE_DEG))
    )
    assert f"{low:.2f} TO {high:.2f}" in data
    # The fit-class read stays out of the SPEC for the same reason the bore band
    # does: the assemblies import the spec's tip circle, and a fit class must not
    # become a rebuild dependency of the frame.
    assert "gear_mesh" not in Path(spec.__file__).read_text(encoding="utf-8")


def test_gear_data_states_the_helix_and_its_hand() -> None:
    # The two tooth-system facts no view of this gear can settle and a mirrored
    # or straight-cut part would get wrong.
    data = notes.GEAR_DATA
    assert f"{spec.HELIX_ANGLE_DEG:.1f} DEG RIGHT HAND" in data
    assert "HELICAL INVOLUTE" in data
    # The hand follows the recipe's twist sense: the tooth azimuth advances
    # counter-clockwise about +z with increasing z (_gear._TWIST_CCW = +1).
    assert spec.HELIX_HAND == "RIGHT HAND"
    assert spec.HELIX_ANGLE_DEG == pytest.approx(part.HELIX_DEG)
    assert spec.BACKLASH_MM == pytest.approx(part.BACKLASH_MM)


def test_gear_data_numbers_track_the_part_geometry() -> None:
    assert spec.TEETH == part.TEETH
    assert spec.DIAMETRAL_PITCH == pytest.approx(part.DP)
    assert spec.PRESSURE_ANGLE_DEG == pytest.approx(part.PA_DEG)
    assert spec.PITCH_DIA == pytest.approx(spec.TEETH * spec.MODULE_MM)
    # #906: ONE cutter, set over at the helix. Its normal DP and pressure
    # angle are the pinion's; the transverse ones follow; the depth is the
    # cutter's, so it is a full-depth tooth of the NORMAL module.
    cos_helix = math.cos(math.radians(spec.HELIX_ANGLE_DEG))
    assert spec.CUTTER_DIAMETRAL_PITCH == pytest.approx(spec.DIAMETRAL_PITCH / cos_helix)
    assert spec.CUTTER_DIAMETRAL_PITCH == pytest.approx(26.30595, abs=1e-5)
    assert math.tan(math.radians(spec.PRESSURE_ANGLE_DEG)) * cos_helix == pytest.approx(
        math.tan(math.radians(spec.CUTTER_PRESSURE_ANGLE_DEG))
    )
    assert spec.CUTTER_DIAMETRAL_PITCH == pinion_spec.DIAMETRAL_PITCH
    assert spec.CUTTER_PRESSURE_ANGLE_DEG == pinion_spec.PRESSURE_ANGLE_DEG
    assert 'depth_dp=CUTTER_DIAMETRAL_PITCH' in _build_source()
    assert spec.WHOLE_DEPTH == pytest.approx(
        2.157 * spec.NORMAL_MODULE_MM + spec.LONG_ADDENDUM_MM
    )
    assert spec.ROOT_DIA == pytest.approx(spec.PITCH_DIA - 2.0 * 1.157 * spec.NORMAL_MODULE_MM)
    assert spec.TRANSVERSE_CIRCULAR_TOOTH_THICKNESS == pytest.approx(
        math.pi * spec.MODULE_MM / 2.0 - spec.BACKLASH_MM
    )
    # The mesh invariant the thinning exists for, in the plane a crossed
    # helical pair meshes in: this gear's normal tooth plus its straight
    # pinion's tooth leave exactly the normal backlash inside one normal
    # circular pitch -- the pinion's own circular pitch.
    assert (
        spec.NORMAL_CIRCULAR_TOOTH_THICKNESS
        + pinion_spec.TRANSVERSE_CIRCULAR_TOOTH_THICKNESS
    ) == pytest.approx(math.pi * spec.NORMAL_MODULE_MM - spec.BACKLASH_MM * cos_helix)
    assert spec.NORMAL_MODULE_MM == pytest.approx(pinion_spec.MODULE_MM)


def test_notes_do_not_substitute_for_native_fit_dimensions() -> None:
    assert notes.DRAWING_NOTES == "DO NOT BREAK OR CHAMFER EDGES ON TOOTH FLANKS, TIPS OR ROOTS."
    assert notes.SHAFT_MATE_NUMBER == _config.parts("dt-cone-gear-shaft")["number"]
    assert drawing.SHAFT_MATE_NAME == _config.parts("dt-cone-gear-shaft")["title"].upper()
    assert not hasattr(notes, "ATTACHMENT_PROCESS")
    assert not hasattr(notes, "ATTACHMENT_ALTERNATIVE")


def test_sheet_runs_at_3_to_2_with_every_view_at_sheet_scale() -> None:
    # A 65 mm disc on a B sheet: at 1:1 two thirds of the sheet was empty and
    # the 64 teeth did not read as teeth. One scale for every view means the
    # title block's SCALE field is the whole truth and no view needs a note.
    assert drawing.SHEET_SCALE == (3.0, 2.0)
    assert drawing.VIEW_SCALE == (3, 2)
    assert _source().count("scale=VIEW_SCALE") == 3
    assert not hasattr(spec, "ISOMETRIC_VIEW_NOTE")


def test_hidden_lines_are_off_and_helical_tangent_edges_are_dropped() -> None:
    # The face view shows the arc and flat in solid lines, and the centre
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
# The native section caption, "SECTION A-A" over its scale, stands 16.5 mm
# tall on the crank-pinion sheet and is placed by its top centre.
_CAPTION_HEIGHT = 0.0165


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
        drawing.MANUFACTURING_NOTES_POS,
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
    # The AF callout and the chamfer stand in the lane between the tooth tips
    # and the section's south face, the chamfer under the AF block.
    af = _text_box(drawing.FRONT_KEEP["BoreAF"], drawing.AF_CALLOUT, "8.763 +0.020")
    chamfer = _text_box(
        drawing.SECTION_KEEP["BoreSouthChamferSize"],
        drawing.DIMENSION_CALLOUTS["BoreSouthChamferSize"],
        "1.00 +0.10",
    )
    section_left = sx - face_half - _VIEW_OUTLINE_PAD
    for box in (af, chamfer):
        assert _box_distance(box, drawing.FRONT_CENTER) > half_od + _VIEW_OUTLINE_PAD + 0.003
        assert box[2] < section_left - 0.003
    assert chamfer[3] < af[1] - 0.003
    # The chamfer's leg dimension runs off the south face at bore height.
    assert sy - half_od < drawing.SECTION_KEEP["BoreSouthChamferSize"][1] < sy
    # The caption hangs under the section and over the title block.
    cap_x, cap_top = drawing.SECTION_CAPTION_XY
    assert cap_x == pytest.approx(sx)
    assert cap_top < sy - half_od - 0.005
    assert cap_top - _CAPTION_HEIGHT > _TITLE_BLOCK_TOP + 0.003


# The gear-data block at its 2.5 mm note height, measured on farm run
# 20261001T110844152Z: rows 3.50 mm apart from a cap top 0.3 mm under the
# anchor, the last row's descenders 0.6 mm under top - rows * pitch, and the
# 95-character tooth-thickness row 165 mm wide (1.74 mm a character). The tip
# diameter's "Ø65.21 ±0.1" printed 26.2 mm wide and 3.9 mm tall.
_NOTE_LINE_PITCH = 0.0035
_NOTE_DESCENDER = 0.0006
_NOTE_CHAR_WIDTH = 0.00174
_TIP_DIA_TEXT = "Ø65.21 ±0.1"
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


def test_tip_diameter_text_hangs_under_every_gear_data_row_and_over_the_teeth() -> None:
    # R9-56's contact-ratio row grew the block down through "Ø65.21 ±0.1",
    # which sat a fixed 16 mm over the tooth tips (machinist review, farm run
    # 20261001T110844152Z). The text now hangs under the block's last row, so
    # a further row moves it down -- until it would land on the teeth.
    block = _gear_data_box()
    assert "CONTACT RATIO WITH MHA-DT-010" in notes.GEAR_DATA.splitlines()[-1]
    tip = _tip_dia_text_box(drawing.FRONT_KEEP["OutsideDia"])
    # The text sits under the block's columns, so its clearance is vertical.
    assert block[0] < tip[0] < block[2]
    assert block[1] - tip[3] >= 0.003
    # ... and over the tooth-tip circle, with room for the leader's shoulder.
    assert _box_distance(tip, drawing.FRONT_CENTER) > drawing.HALF_OD + 0.005
    # The fixed placement, 16 mm over the tips, that the contact-ratio row
    # printed through.
    cx, cy = drawing.FRONT_CENTER
    old = _tip_dia_text_box((cx - 0.035, cy + drawing.HALF_OD + 0.016))
    assert old[3] > block[1]


def test_part_stamps_make_critical_properties() -> None:
    build = _build_source()
    assert "apply_drawing_properties" in build
    assert "clear_dimensions_for_drawing" in build

    config = _config.parts("dt-crank-drive-gear")
    material = "SAE 1018 CF bar, ASTM A108-24"
    assert config["material"] == material
    assert config["material_specification"] == material
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


def test_bore_finish_reads_at_note_height_and_leaders_have_separate_landings() -> None:
    # The round diameter, AF and finish all need room around the D-bore;
    # the tip-diameter arrow belongs on the near tooth silhouette, and only
    # the AF dimension (it spans the axis) may meet the A-A cutting line.
    import _drawing_leaders as leaders

    assert drawing.FINISH_CHAR_HEIGHT == 0.0025  # the Gear Data / notes height

    cx, cy = drawing.FRONT_CENTER
    r = drawing.BORE_SHEET_RADIUS
    assert r == pytest.approx(spec.BORE_DIA * 1.5 / 2000.0)
    ax, ay = drawing.FINISH_ATTACH
    assert math.hypot(ax - cx, ay - cy) == pytest.approx(r)
    assert ax > cx and ay < cy  # lower right, opposite the bore callout
    tip_text = drawing.FRONT_KEEP["OutsideDia"]
    bore_text = drawing.FRONT_KEEP["BoreDia"]
    af_text = drawing.FRONT_KEEP["BoreAF"]
    assert bore_text[0] < cx and bore_text[1] < cy
    assert af_text[0] > cx and af_text[1] > cy
    angle = math.atan2(bore_text[1] - cy, bore_text[0] - cx)
    bore = [(bore_text, (cx + r * math.cos(angle), cy + r * math.sin(angle)))]
    flat_x = (spec.BORE_AF - spec.BORE_DIA / 2) * drawing.VIEW_SCALE[0] / (
        1000 * drawing.VIEW_SCALE[1]
    )
    af = [(af_text, (cx + flat_x, cy))]
    # The broken leader leaves the text's near end aimed at the centre
    # ("65.11 +/-0.1" is 28 mm wide on the round-bore sheet).
    near_end = (tip_text[0] + 0.014, tip_text[1])
    aim = math.atan2(near_end[1] - cy, near_end[0] - cx)
    rim = (math.cos(aim) * drawing.HALF_OD, math.sin(aim) * drawing.HALF_OD)
    old_tip = [(near_end, (cx - rim[0], cy - rim[1]))]
    new_tip = [(near_end, (cx + rim[0], cy + rim[1]))]
    finish = [(drawing.FINISH_SYMBOL, drawing.FINISH_ATTACH)]
    reach = drawing.HALF_OD + drawing.SECTION_LINE_OVERRUN
    cutting_line = [((cx - reach, cy), (cx + reach, cy))]
    assert leaders.distance_to_point(old_tip[0], (cx, cy)) < drawing.TIP_DIA_KEEP_OUT
    leaders.assert_leaders_clear(
        {"OutsideDia": new_tip, "BoreDia": bore, "BoreAF": af, "BoreFinish": finish},
        centre=(cx, cy),
        keep_out={"OutsideDia": drawing.TIP_DIA_KEEP_OUT},
        lands_within={
            "OutsideDia": drawing.TIP_DIA_LANDING,
            "BoreDia": drawing.BORE_LANDING,
            "BoreAF": drawing.BORE_LANDING,
            "BoreFinish": drawing.BORE_LANDING,
        },
        label="gear bore layout",
    )
    leaders.assert_leaders_clear(
        {
            "OutsideDia": new_tip,
            "BoreDia": bore,
            "BoreFinish": finish,
            "SectionLine": cutting_line,
        },
        centre=(cx, cy),
        keep_out={},
        lands_within={
            "OutsideDia": drawing.TIP_DIA_LANDING,
            "BoreDia": drawing.BORE_LANDING,
            "BoreFinish": drawing.BORE_LANDING,
            "SectionLine": drawing.SECTION_LINE_LANDING,
        },
        label="gear leaders vs A-A",
    )
    # The cut runs along the bore axis through the flat: the tip leader stays
    # above it, the bore and finish leaders below it.
    assert min(new_tip[0][0][1], new_tip[0][1][1]) > cy + 0.005
    for name, segments in (("BoreDia", bore), ("BoreFinish", finish)):
        assert max(segments[0][0][1], segments[0][1][1]) < cy, name
