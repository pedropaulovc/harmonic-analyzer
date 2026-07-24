"""Offline contracts for the crank-arm drawing."""

from __future__ import annotations

import math
from pathlib import Path

import crank_arm_spec
import draw_crank_arm as drawing
import build_crank_arm as arm
from _drawing_registry import DRAWINGS_BY_NAME
from _holes import NUMBER_DRILL_MM


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/crank-arm.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/crank-arm.pdf")
    assert drawing.PNG.as_posix().endswith("/png/crank-arm_drawing.png")
    assert DRAWINGS_BY_NAME["crank_arm"].script == Path(drawing.__file__).resolve()


def test_spec_is_the_single_source_of_the_marked_dimension_set() -> None:
    # The drift alarm: the part-side mark set and the drawing-side keep set are BOTH
    # the shared spec's map. build re-exports the SAME object (so it marks exactly the
    # spec), and the drawing keeps exactly its union across the per-view keep-maps --
    # a rename in one script that isn't mirrored in the other fails here, offline.
    assert arm.DRAWING_DIMENSIONS is crank_arm_spec.DRAWING_DIMENSIONS
    marked = set().union(*crank_arm_spec.DRAWING_DIMENSIONS.values())
    kept = (
        set(drawing.FRONT_KEEP) | set(drawing.RIGHT_KEEP) | set(drawing.TOP_KEEP)
    )
    assert kept == marked
    # A callout can only annotate a dimension the print actually shows.
    assert set(drawing.DIMENSION_CALLOUTS) <= kept
    # The drawing's view math reads the spec's nominal spans, not a divergent copy.
    assert (drawing.ARM_END_X, drawing.HALF_WIDTH) == (
        crank_arm_spec.ARM_END_X,
        crank_arm_spec.HALF_WIDTH,
    )


def test_sheet_runs_at_2_to_1_with_1_to_1_isometric() -> None:
    assert drawing.SHEET_SCALE == (2.0, 1.0)
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "scale=(1, 1)" in source  # the isometric override
    assert crank_arm_spec.ISOMETRIC_VIEW_NOTE == "ISOMETRIC VIEW SCALE 1:1"
    assert 'add_property_linked_note(adapter, "Isometric View Note"' in source


def test_linked_notes_define_a_complete_individual_part() -> None:
    notes = crank_arm_spec.DRAWING_NOTES
    assert "3/8 IN" in drawing.DIMENSION_CALLOUTS["ShaftBoreDia"]
    assert "15/64 DRILL THRU" in notes
    assert "HANDLE PIVOT CENTRED" not in notes
    assert "FINISHED SIZE FOR THIS PART" in notes
    assert "MHA-026" not in notes and "MHA-024" not in notes
    assert "OUTSIDE THIS PART DRAWING" not in notes
    assert "MATCH-REAM" not in notes
    assert "NOT INDIVIDUAL PART ACCEPTANCE" not in notes
    assert "NO. 2" not in notes
    assert '3: "crank arm; manufacturing drawing; straight cross-hole"' in Path(
        drawing.__file__
    ).read_text(encoding="utf-8")
    # General tolerances live in the title block ONLY -- a second general
    # tolerance in the notes would conflict with it.
    assert "LINEAR +/-" not in notes
    assert "HOLE CENTRES" not in notes
    # Pedro 2026-07-10: drawings spec the closest US-customary fastener, not
    # the period British Association series.
    assert "BA" not in notes
    assert "X.XX" not in notes
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert 'add_property_linked_note(adapter, "Manufacturing Notes"' in source
    assert "_NOTES_" not in source


def test_hole_states_are_annotated() -> None:
    callouts = drawing.DIMENSION_CALLOUTS
    assert callouts["ShaftBoreDia"].startswith("THRU")
    assert callouts["DimpleDia"] == "0.5 DEEP"
    assert crank_arm_spec.PIN_HOLE_DIA == NUMBER_DRILL_MM["#14"]
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert source.count("add_native_hole_callout(") == 2
    assert 'label="crank-arm cross-hole"' in source


def test_native_gdt_replaces_form_orientation_notes() -> None:
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert source.count("add_datum_feature(") == 3
    assert source.count("add_feature_control_frame(") == 3
    assert "characteristic=\"parallelism\"" in source
    assert "characteristic=\"position\"" in source
    assert "add_surface_finish(" in source


def test_shaft_axis_datum_pick_is_radial_with_its_symbol() -> None:
    centre = (drawing._sheet_x(0.0), drawing.FRONT_CENTER[1])
    rim_vector = (
        drawing.DATUM_B_RIM[0] - centre[0],
        drawing.DATUM_B_RIM[1] - centre[1],
    )
    leader_vector = (
        drawing.DATUM_B_SYMBOL[0] - drawing.DATUM_B_RIM[0],
        drawing.DATUM_B_SYMBOL[1] - drawing.DATUM_B_RIM[1],
    )
    assert math.isclose(
        math.hypot(*rim_vector), drawing.DATUM_B_RADIUS, abs_tol=1e-12
    )
    assert math.isclose(
        rim_vector[0] * leader_vector[1] - rim_vector[1] * leader_vector[0],
        0.0,
        abs_tol=1e-12,
    )
    assert rim_vector[0] * leader_vector[0] + rim_vector[1] * leader_vector[1] > 0
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "edge_xy=DATUM_B_RIM" in source
    assert "symbol_xy=DATUM_B_SYMBOL" in source
    assert "shoulder=True" in source
    assert "position_tolerance_m=0.001" in source


def test_handle_pivot_has_basic_transverse_location_from_datum_c() -> None:
    assert crank_arm_spec.HALF_WIDTH == 8.0
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "handle_transverse = add_edge_dimension(" in source
    assert 'orientation="vertical"' in source
    assert "set_arc_endpoints_to_center(\n        adapter, handle_transverse" in source
    assert "set_basic_dimension(\n        adapter, handle_transverse" in source


def test_cross_hole_has_basic_datum_a_station_and_position_control() -> None:
    assert crank_arm_spec.ARM_THICKNESS / 2.0 == 4.0
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "pin_station = add_edge_dimension(" in source
    assert 'label="cross-hole station from datum A"' in source
    assert "set_arc_endpoints_to_center(\n        adapter, pin_station" in source
    assert "set_basic_dimension(\n        adapter, pin_station" in source
    assert 'label="cross-hole true position"' in source
    assert 'datums=("A", "B")' in source
    assert "CROSS-HOLE AXIS INTERSECTS DATUM AXIS B." in crank_arm_spec.DRAWING_NOTES
    assert "MATCH-REAM" not in crank_arm_spec.DRAWING_NOTES


def test_dimple_has_both_nominal_location_coordinates() -> None:
    assert crank_arm_spec.DIMPLE_X == 30.0
    assert crank_arm_spec.HALF_WIDTH == 8.0
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert '"DimpleX":' in source
    assert "dimple_transverse = add_edge_dimension(" in source
    assert 'label="dimple transverse location from datum C"' in source
    assert "set_arc_endpoints_to_center(\n        adapter,\n        dimple_transverse" in source


def test_gtol_annotations_are_migrated_to_current_xml_format() -> None:
    common = Path(drawing.__file__).with_name("_drawing_common.py").read_text(
        encoding="utf-8"
    )
    assert "CanConvertFormat()" in common
    assert "ConvertFormat()" in common
    assert "GetFormat()) != 2" in common
    assert common.index("SetFrameSymbols2") < common.index("ConvertFormat()")
    assert "if not migrated and not frame.SetSymbolXml(xml)" in common
    assert "annotation.SetAttachedEntities(dispatch_array([edge]))" in common
    # Bent, not straight: a straight leader runs at whatever angle the
    # anchor-to-frame vector takes, which is what drove the Ra symbol's leader
    # across two views. IGtol::SetLeader cannot ask for bent, so the ordinary
    # path goes through IAnnotation::SetLeader3 and checks its int status.
    assert "annotation.SetLeader3(" in common
    assert "_LEADER_BENT," in common
    assert "gtol.SetLeader(True, 0, False, False)" not in common
    # DIMENSION and source MODEL_FACE registration are flow-dependent (0 or 1
    # depending on insertion order); drawing edges/faces still register as 1.
    assert 'indirect_entity_types = {"DIMENSION", "MODEL_FACE"}' in common
    assert "entity_type in indirect_entity_types" in common
    assert "not bool(gtol.IsAttached())" in common
    assert "int(gtol.GetLeaderCount()) != 1" in common


def test_wizard_holes_are_not_fake_marked_dimensions() -> None:
    assert "BoreProfile" not in arm.DRAWING_DIMENSIONS
    assert "PinHoleProfile" not in arm.DRAWING_DIMENSIONS
    source = Path(arm.__file__).read_text(encoding="utf-8")
    assert 'HoleSpec("drilled_fractional", "15/64")' in source
    assert 'HoleSpec("drilled_number", "#14")' in source


def test_part_stamps_make_critical_drawing_properties() -> None:
    source = Path(arm.__file__).read_text(encoding="utf-8")
    assert "apply_drawing_properties" in source
    assert "clear_dimensions_for_drawing" in source
    import _config

    spec = _config.parts("crank-arm")
    expected = "SAE 1018 CF bar, ASTM A108-24"
    assert spec["material"] == expected
    assert spec["material_specification"] == expected
    assert spec["finish"]
    assert int(spec["quantity"]) == 1
