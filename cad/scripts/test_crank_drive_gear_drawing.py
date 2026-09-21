"""Offline contracts for the crank-drive-gear drawing.

The print is recreated under ``cad/docs/drawing-simplicity-policy.md``: a 64T
helical gear slipped onto the cone shaft's land carries no datums and no frames,
its three turned sizes are native model dimensions whose places and bands the
PART owns, and the tooth system it cannot dimension -- helix angle, hand, tooth
thinning -- lives in the gear-data block.
"""

from __future__ import annotations

import math
from pathlib import Path

import pytest

import _config
import build_crank_drive_gear as part
import cone_gear_shaft_spec
import crank_drive_gear_notes as notes
import crank_drive_gear_spec as spec
import crank_pinion_spec as pinion_spec
import draw_crank_drive_gear as drawing
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS
from _drawing_registry import DRAWINGS_BY_NAME


def _source() -> str:
    return Path(drawing.__file__).read_text(encoding="utf-8")


def _build_source() -> str:
    return Path(part.__file__).read_text(encoding="utf-8")


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/crank-drive-gear.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/crank-drive-gear.pdf")
    assert drawing.PNG.as_posix().endswith("/png/crank-drive-gear_drawing.png")
    assert (
        DRAWINGS_BY_NAME["crank_drive_gear"].script == Path(drawing.__file__).resolve()
    )


def test_spec_is_the_single_source_of_the_marked_dimension_set() -> None:
    # The drift alarm: the part-side mark set and the drawing-side keep set are
    # BOTH the shared spec's map, so a rename in one script that is not
    # mirrored in the other fails here, offline.
    assert part.DRAWING_DIMENSIONS is spec.DRAWING_DIMENSIONS
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.FRONT_KEEP) | set(drawing.RIGHT_KEEP)
    assert kept == marked == {"OutsideDia", "FaceWidth", "BoreDia"}
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
    assert spec.OUTSIDE_DIA == pytest.approx(
        (part.TEETH + 2) / part.DP * spec.MM_PER_IN
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
        "FaceWidth": 1,
        "BoreDia": 3,
    }
    assert "draw_crank_drive_gear.py" in PRECISION_MIGRATED_DRAWINGS
    source = _source()
    assert "set_dimension_precision" not in source
    assert "SetPrecision3" not in source
    assert "DIMENSION_PRECISION" not in source
    assert "assert_imported_precision(" in source
    assert "apply_drawing_precision(adapter, DRAWING_PRECISION)" in _build_source()


def test_the_bore_is_the_only_feature_that_earns_a_band() -> None:
    # cad/docs/tolerance-policy.md: a feature is toleranced tighter than its
    # title-block general grade only through the named chain. On this part
    # exactly one feature can cite it -- the fit over the cone shaft's land.
    build = _build_source()
    assert build.count("set_dimension_bilateral_tolerance(") == 1
    assert '"BoreProfile", "BoreDia", *deviations(BORE_DIA_BAND)' in build
    assert [name for name in dir(spec) if name.endswith("_BAND")] == []
    assert [name for name in dir(part) if name.endswith("_BAND")] == ["BORE_DIA_BAND"]
    # ... and it is the only three-decimal dimension for the same reason.
    assert [
        name for name, places in spec.DRAWING_PRECISION_BY_NAME.items() if places > 2
    ] == ["BoreDia"]


def test_bore_band_is_derived_from_its_fit_class_not_written_by_hand() -> None:
    # A slip fit exists only if the size limits on BOTH mating features are
    # narrower than the clearance band they claim, so the bore's limits are
    # computed from the named fit class and the shaft land's own published
    # limits. Move either input and the bore must move with it -- that is what
    # this pins, not the literal pair of numbers.
    low, high = _config.fit("shaft_in_bushing")["diametral_clearance_mm"]
    land_upper, land_lower = cone_gear_shaft_spec.SECTION_DIA_BAND
    assert spec.BORE_DIA == pytest.approx(cone_gear_shaft_spec.SECTION_DIAS[1])
    assert part.BORE_DIA_BAND == (
        pytest.approx(land_lower + high),
        pytest.approx(land_upper + low),
    )
    bore_upper, bore_lower = part.BORE_DIA_BAND
    minimum = bore_lower - land_upper
    maximum = bore_upper - land_lower
    assert (minimum, maximum) == (pytest.approx(low), pytest.approx(high))
    # The fit-class read stays OUT of the shared spec: it is imported by the
    # assemblies that need OUTSIDE_DIA, and a _config.fit there would make
    # tolerances.yaml a rebuild dependency of the frame (test_dodo_recipe's
    # fine-grained-config contract).
    assert "_config.fit(" not in Path(spec.__file__).read_text(encoding="utf-8")


def test_outside_diameter_stays_at_the_general_grade() -> None:
    # The tip circle is NOT an accuracy feature (tolerance-policy.md scores
    # gear runout below 0.1 %/mm and the one-sided-load bullets forbid
    # tightening a clearance for accuracy). The crossed mesh is built with
    # fits.crank_mesh's 0.25 mm of centre-distance slack ON TOP of the tooth
    # system's own tip clearance, so the general .XX grade fits inside the
    # radial room and the tips still cannot bottom.
    assert not hasattr(spec, "OUTSIDE_DIA_BAND")
    assert spec.DRAWING_PRECISION["OutsideDiaReference"]["OutsideDia"] == 2
    slack = _config.fit("crank_mesh")["c2c_slack_mm"]
    assert spec.TIP_CLEARANCE_MM == pytest.approx(0.155, abs=0.001)
    radial_room = slack + spec.TIP_CLEARANCE_MM
    general_radial = _config.title_block("linear_2pl")["value_in"] * 25.4 / 2.0
    assert general_radial < radial_room
    # The face width is the one free length: one place, so the title block's
    # .X grade is the band it claims, and the mating pinion's face is wider
    # than this one by more than that band at every allowed axial position.
    assert spec.DRAWING_PRECISION["GearBlank"]["FaceWidth"] == 1
    face_band = _config.title_block("linear_1pl")["value_in"] * 25.4
    assert pinion_spec.FACE_WIDTH - spec.FACE_WIDTH > face_band


def test_bore_callout_states_the_process_and_how_far_it_goes() -> None:
    # Rule 7: the Ø and its limits come from the dimension; the callout adds
    # only the two facts the number cannot carry.
    assert drawing.DIMENSION_CALLOUTS == {"BoreDia": "REAM THRU"}


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
        "DIAMETRAL PITCH, TRANSVERSE",
        "MODULE, TRANSVERSE (mm, REF)",
        "PRESSURE ANGLE, TRANSVERSE",
        "PITCH DIAMETER (mm, REF)",
        "ROOT DIAMETER (mm, REF)",
        "WHOLE DEPTH (mm, REF)",
        "HELIX ANGLE AT PITCH DIAMETER",
        "CIRCULAR TOOTH THICKNESS AT PITCH DIA, TRANSVERSE (mm)",
        "TRANSVERSE BACKLASH ASSEMBLED WITH MHA-025 (mm)",
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
    assert f"{spec.TRANSVERSE_CIRCULAR_TOOTH_THICKNESS:.3f} +0.100 / -0.050" in data
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
    assert spec.TOTAL_TWIST_DEG == pytest.approx(3.08, abs=0.01)


def test_gear_data_numbers_track_the_part_geometry() -> None:
    assert spec.TEETH == part.TEETH
    assert spec.DIAMETRAL_PITCH == pytest.approx(part.DP)
    assert spec.PRESSURE_ANGLE_DEG == pytest.approx(part.PA_DEG)
    assert spec.PITCH_DIA == pytest.approx(spec.TEETH * spec.MODULE_MM)
    assert spec.WHOLE_DEPTH == pytest.approx(2.157 * spec.MODULE_MM)
    assert spec.ROOT_DIA == pytest.approx(
        (part.TEETH - 2.0 * 1.157) / part.DP * spec.MM_PER_IN
    )
    assert spec.TRANSVERSE_CIRCULAR_TOOTH_THICKNESS == pytest.approx(
        math.pi * spec.MODULE_MM / 2.0 - spec.BACKLASH_MM
    )
    # The mesh invariant the thinning exists for: this gear's tooth plus its
    # straight pinion's tooth leave exactly the backlash inside one circular
    # pitch.
    assert (
        spec.TRANSVERSE_CIRCULAR_TOOTH_THICKNESS
        + pinion_spec.TRANSVERSE_CIRCULAR_TOOTH_THICKNESS
    ) == pytest.approx(math.pi * spec.MODULE_MM - spec.BACKLASH_MM)


def test_notes_carry_the_part_specific_facts_and_never_the_title_block() -> None:
    text = notes.DRAWING_NOTES
    lines = text.splitlines()
    # The title block orders every sharp edge broken R0.25 / 0.25 chamfer max.
    # On a 2.13 whole-depth tooth that is more than a tenth of the tooth, so
    # the print states the exception.
    assert lines[0] == "DO NOT BREAK OR CHAMFER EDGES ON TOOTH FLANKS, TIPS OR ROOTS."
    # The attachment (rule-11 flag closed 2026-09-21): the bore is the only
    # attachment feature on the part, so the joint to the shaft land is the
    # entire torque path -- a machinist who reams the bore and ships it has
    # made the wrong part. The note must NAME the mate and STATE the joining
    # methods, which rule 6 allows only because here the process IS the
    # requirement. Each method is one swappable constant (the user approved a
    # retaining compound alongside filler metal on 2026-09-21), so this pins
    # what the sentence has to carry, not the wording of either method.
    assert "PLAIN BORE, NO KEYWAY" in lines[1]
    assert notes.ATTACHMENT_PROCESS in lines[1]
    assert notes.SHAFT_MATE_NUMBER in lines[1]
    assert notes.ATTACHMENT_ALTERNATIVE in text
    # Both routes are permitted, so the line that offers the alternative has
    # to read as a permission, not as a second instruction.
    assert "ACCEPTABLE" in notes.ATTACHMENT_ALTERNATIVE
    # The mate is the cone gear shaft, whatever the registry calls it -- and
    # not this gear's own number.
    assert notes.SHAFT_MATE_NUMBER == _config.parts("cone-gear-shaft")["number"]
    assert notes.SHAFT_MATE_NUMBER != _config.parts("crank-drive-gear")["number"]
    # Rule 6, "never a dimension": the ONLY digits allowed anywhere in the
    # notes block are the mate's part number and the compound designations. A
    # size, a limit, a depth or a station typed into a note is what this pins.
    named = text.replace(notes.SHAFT_MATE_NUMBER, "").replace(
        notes.ATTACHMENT_ALTERNATIVE, ""
    )
    assert not any(ch.isdigit() for ch in named)
    # Rule 6's budget: at most four short lines, each short enough to clear
    # the title-block keep-out from the notes anchor at x = 16 mm.
    assert len(lines) == 3
    assert all(len(line) <= 90 for line in lines)
    # The attachment note must not re-print the bore that the face view
    # already dimensions and bands, and must not invent an axial requirement:
    # the assembly leaves ~1.1 mm of air to T120 (a frozen 10.0 mm reference
    # face against the real 8.0), so the station is an assembly fact.
    for banned in ("9.525", "BUTTED", "T120", "FLUSH"):
        assert banned not in text, banned
    # Retired with the migration: the general-tolerance restatements, the
    # method instructions, the heat-treatment negative, the duplicate of the
    # bore fit, the hand-of-helix narration the data block now states, and the
    # pair commissioning protocol that was never part acceptance.
    for banned in (
        "CUT TEETH",
        "HARDNESS",
        "DIAMETRAL CLEARANCE",
        "ROOT DIAMETER",
        "ROOT FLOOR",
        "POSITIVE HELIX",
        "COMMISSIONING",
        "ACCEPTANCE",
        "MHA-025",
        "N*m",
        "RPM",
        "+/-",
    ):
        assert banned not in text, banned


def test_sheet_runs_at_3_to_2_with_every_view_at_sheet_scale() -> None:
    # A 65 mm disc on a B sheet: at 1:1 two thirds of the sheet was empty and
    # the 64 teeth did not read as teeth. One scale for every view means the
    # title block's SCALE field is the whole truth and no view needs a note.
    assert drawing.SHEET_SCALE == (3.0, 2.0)
    assert drawing.VIEW_SCALE == (3, 2)
    assert _source().count("scale=VIEW_SCALE") == 3
    assert not hasattr(spec, "ISOMETRIC_VIEW_NOTE")


def test_hidden_lines_are_off_and_helical_tangent_edges_are_dropped() -> None:
    # The only internal feature is a straight reamed bore whose callout says
    # THRU. The 64 helical flanks, by contrast, project 128 tangent curves
    # across the side view's 12 mm face -- dropped on both orthographic views,
    # kept on the isometric, where the helix is what is being shown.
    source = _source()
    assert (
        "for view in (front, right, iso):\n        set_hidden_lines_removed" in source
    )
    assert "set_hidden_lines_visible" not in source
    assert '_hide_tangent_edges(front, "front")' in source
    assert '_hide_tangent_edges(right, "side")' in source
    assert "_hide_tangent_edges(iso" not in source
    assert "SetDisplayTangentEdges2(0)" in source
    assert "GetDisplayTangentEdges2()" in source


def test_dimension_text_lands_clear_of_the_views_and_the_title_block() -> None:
    # Offline layout guard: every dimension is leadered or extended OUT of the
    # silhouette it measures, and nothing crosses into the title block's
    # bottom-right corner of the B sheet.
    half_od = drawing.HALF_OD
    assert half_od == pytest.approx(spec.OUTSIDE_DIA * 3 / (2 * 2000.0))
    for name, (x, y) in drawing.FRONT_KEEP.items():
        reach = math.hypot(x - drawing.FRONT_CENTER[0], y - drawing.FRONT_CENTER[1])
        assert reach > half_od + 0.010, name
    for name, (x, y) in drawing.RIGHT_KEEP.items():
        assert y > drawing.RIGHT_CENTER[1] + half_od, name
    positions = (
        *drawing.FRONT_KEEP.values(),
        *drawing.RIGHT_KEEP.values(),
        drawing.GEAR_DATA_POS,
        drawing.MANUFACTURING_NOTES_POS,
    )
    for x, y in positions:
        assert 0.012 < x < 0.420
        assert 0.012 < y < 0.267
        assert not (x > 0.216 and y < 0.070), (x, y)  # title-block keep-out
    # The three views march left to right without overlapping: face view, side
    # view, isometric.
    face_half = drawing.FACE_WIDTH_HALF
    assert drawing.FRONT_CENTER[0] + half_od < drawing.RIGHT_CENTER[0] - face_half
    assert drawing.RIGHT_CENTER[0] + face_half < drawing.ISO_CENTER[0] - half_od
    # The gear-data column stays left of every dimension the face view places.
    assert drawing.GEAR_DATA_POS[0] < min(x for x, _ in drawing.FRONT_KEEP.values())


def test_part_stamps_make_critical_properties() -> None:
    build = _build_source()
    assert "apply_drawing_properties" in build
    assert "clear_dimensions_for_drawing" in build

    config = _config.parts("crank-drive-gear")
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
