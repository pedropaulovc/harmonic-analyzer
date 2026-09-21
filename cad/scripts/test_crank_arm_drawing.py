"""Offline contracts for the separate-hub crank-arm drawing."""

from __future__ import annotations

from pathlib import Path

import pytest

import build_crank_arm as arm
import build_drive_train_assembly as drive
import crank_arm_spec as spec
import crank_hub_geometry as geometry
import draw_crank_arm as drawing
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS, model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME
from _hole_spec import drill_process


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/crank-arm.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/crank-arm.pdf")
    assert drawing.PNG.as_posix().endswith("/png/crank-arm_drawing.png")
    assert DRAWINGS_BY_NAME["crank_arm"].script == Path(drawing.__file__).resolve()


def test_arm_is_a_matched_receiver_for_the_separate_hub() -> None:
    assert spec.ARM_WIDTH == geometry.ARM_WIDTH == 18.1
    assert spec.ARM_THICKNESS == geometry.ARM_THICKNESS == 8.0
    assert spec.HUB_SEAT_DIA == geometry.HUB_SEAT_DIA == 15.0
    assert spec.HALF_WIDTH == pytest.approx(9.05)
    assert spec.HUB_SEAT_CALLOUT.startswith("MATCH-FIT TO ASSIGNED MHA-137")
    assert "LIGHT ARBOR-PRESS" in spec.HUB_SEAT_CALLOUT
    assert not hasattr(spec, "SHAFT_BORE_DIA")
    assert not hasattr(spec, "PIN_HOLE_SPEC")


def test_axial_seam_key_is_six_oclock_and_stops_halfway_through_arm() -> None:
    assert spec.AXIAL_PIN_DIA == geometry.AXIAL_PIN_DIA == 3.4
    assert spec.AXIAL_PIN_LENGTH == geometry.AXIAL_PIN_LENGTH == spec.ARM_THICKNESS / 2.0
    assert spec.AXIAL_PIN_X == geometry.AXIAL_PIN_RADIUS_FROM_AXIS == 7.5
    assert spec.AXIAL_PIN_Y == 0.0
    assert drive.CRANK_HUB_PIN_ORIGIN == pytest.approx(
        [drive.X_CRANK, drive.Y_CRANK - 7.5, drive.CRANK_FACE_Z]
    )
    assert drive.CRANK_HUB_PIN_ROWS == drive.IDENTITY


def test_spec_is_the_single_source_of_the_marked_dimension_set() -> None:
    assert arm.DRAWING_DIMENSIONS is spec.DRAWING_DIMENSIONS
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.FRONT_KEEP) | set(drawing.RIGHT_KEEP) | set(drawing.TOP_KEEP)
    assert kept == marked
    assert set(drawing.DIMENSION_CALLOUTS) == {"HubSeatDia"}
    assert drawing.DIMENSION_CALLOUTS["HubSeatDia"] == spec.HUB_SEAT_CALLOUT
    assert drawing.TOP_KEEP == {}


def test_reference_dimensions_remain_model_owned() -> None:
    assert spec.DRAWING_DIMENSIONS["StationReference"] == {
        "PivotStation",
        "AnchorStation",
        "AnchorOffset",
        "AxisOffset",
        "Width",
    }
    assert spec.DRAWING_DIMENSIONS["HubSeatProfile"] == {"HubSeatDia"}
    assert spec.HALF_WIDTH - spec.ANCHOR_SCREW_Y == pytest.approx(4.55)
    assert spec.ARM_END_X + spec.HALF_WIDTH == pytest.approx(94.05)
    assert spec.DRAWING_REFERENCE_PRECISION == {"overall length reference": 1}


def test_punch_and_seam_operations_are_notes_not_fake_dimensions() -> None:
    notes = spec.DRAWING_NOTES
    assert "PUNCH ALIGNMENT WITNESS" in notes
    assert "AXIAL SEAM" in notes
    assert "MHA-138" in notes
    assert "MHA-024" not in notes
    assert "DIMPLE" not in notes
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert all("Fiducial" not in name for name in marked)
    assert all("AxialPin" not in name for name in marked)


def test_sheet_uses_imported_part_precision_and_no_gdt() -> None:
    assert drawing.SHEET_SCALE == (2.0, 1.0)
    assert spec.ISOMETRIC_VIEW_NOTE == "ISOMETRIC VIEW SCALE 1:1"
    assert set(spec.DRAWING_PRECISION_BY_NAME) == set().union(
        *spec.DRAWING_DIMENSIONS.values()
    )
    assert set(spec.DRAWING_PRECISION_BY_NAME.values()) == {1}
    assert Path(drawing.__file__).name in PRECISION_MIGRATED_DRAWINGS
    assert model_toleranced_dimensions(arm) == {}
    assert spec.SURFACE_FINISHES == ()
    assert not hasattr(spec, "GEOMETRIC_TOLERANCES_MM")


def test_anchor_callout_defers_thread_class_to_title_block() -> None:
    class NativeCallout:
        definition = "<hw-threaddesc> <hw-threadclass> <HOLE-DEPTH> <hw-threaddepth>"

        def GetText(self, part: int) -> str:
            assert part == 5
            return self.definition

        def SetText(self, part: int, text: str) -> None:
            assert part == 1
            self.definition = text

    callout = NativeCallout()
    drawing._omit_title_block_thread_class(callout)
    assert callout.definition == "<hw-threaddesc> <HOLE-DEPTH> <hw-threaddepth>"
    with pytest.raises(ValueError):
        drill_process(spec.ANCHOR_HOLE_SPEC)


def test_assembly_keeps_common_face_and_established_inboard_stations() -> None:
    assert drive.CRANK_FACE_Z == -183.0
    assert drive.CRANKSHAFT_Z0 == drive.CRANK_HUB_Z0 == drive.CRANK_ARM_Z0 == -183.0
    assert drive.CRANK_ARM_ORIGIN_Z == -175.0
    assert drive.CRANK_PIN_Z == -171.0
    assert drive.CRANK_HUB_REAR_Z == -163.0
    assert drive.REMOVABLE_Z0 - drive.CRANK_HUB_REAR_Z == pytest.approx(5.5)
    assert drive.CRANKSHAFT_Z0 + drive.CRANKSHAFT_LENGTH == pytest.approx(-53.0)


def test_stock_anchor_still_clamps_eye_without_bottoming() -> None:
    import build_crank_pin_eye as eye
    import build_fillister_screw as screw

    wire_front = drive.EYE_Z - eye.WIRE_DIA / 2.0
    wire_back = drive.EYE_Z + eye.WIRE_DIA / 2.0
    assert drive.ANCHOR_HEAD_Z == pytest.approx(wire_front)
    assert drive.CRANK_ARM_Z0 - wire_back == pytest.approx(0.02)
    insertion = drive.ANCHOR_HEAD_Z + screw.SHANK_LEN - drive.CRANK_ARM_Z0
    assert insertion == pytest.approx(5.33)
    assert screw.SHANK_DIA < insertion <= spec.ANCHOR_HOLE_SPEC.overrides_mm["ThreadDepth"]
    assert spec.ANCHOR_HOLE_SPEC.depth_mm - insertion == pytest.approx(1.17)
    assert drive.ANCHOR_BACK_WALL >= 0.5


def test_part_registry_retains_make_critical_properties() -> None:
    import _config

    part = _config.parts("crank-arm")
    assert part["number"] == "MHA-020"
    assert part["material"] == part["material_specification"]
    assert part["finish"]
    assert int(part["quantity"]) == 1
