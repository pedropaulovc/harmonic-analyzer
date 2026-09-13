"""Offline contracts for the top-frame geometry and drawing."""

from __future__ import annotations

import math
from pathlib import Path

import build_top_frame as part
import draw_top_frame as drawing
import top_frame_spec
from _drawing_registry import DRAWINGS_BY_NAME
from frame_attachment_spec import (
    CAP_MOUTH_Y,
    CAP_RECESS_DEPTH,
    CAP_RECESS_DIAMETER,
    CASTING_FULL_THREAD_DEPTH,
    CASTING_TAP_DRILL_DEPTH,
    COLUMN_SOCKET_DIAMETER,
    TOP_SCREW_SEAT_Z,
    TOP_SCREW_Y,
    TUBE_CROSS_HOLE_DIAMETER,
)
from tube_frame_cap_spec import MAX_OUTER_DIAMETER


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/top-frame.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/top-frame.pdf")
    assert drawing.PNG.as_posix().endswith("/png/top-frame_drawing.png")
    assert DRAWINGS_BY_NAME["top_frame"].script == Path(drawing.__file__).resolve()


def test_drawing_keeps_plan_and_section_manufacturing_dimensions() -> None:
    assert part.DRAWING_DIMENSIONS is top_frame_spec.DRAWING_DIMENSIONS
    marked = set().union(*top_frame_spec.DRAWING_DIMENSIONS.values())
    assert set(drawing.TOP_KEEP) | set(drawing.SECTION_KEEP) == marked
    assert marked == {"Width", "Depth", "CapRecessDia", "CapRecessDepth"}
    assert "FIT MHA-133" in drawing.DIMENSION_CALLOUTS["CapRecessDia"]
    assert "CAP SEATS ON TUBE END" in drawing.DIMENSION_CALLOUTS["CapRecessDepth"]


def test_corner_bores_and_cap_recesses_form_a_clear_matched_stack() -> None:
    assert part.BORE_DIA == COLUMN_SOCKET_DIAMETER == 25.5
    assert part.CAP_RECESS_DIAMETER == CAP_RECESS_DIAMETER
    assert part.CAP_RECESS_DEPTH == CAP_RECESS_DEPTH
    assert CAP_RECESS_DIAMETER > MAX_OUTER_DIAMETER
    assert math.isclose(
        part.CAP_RECESS_DIAMETRAL_CLEARANCE,
        CAP_RECESS_DIAMETER - MAX_OUTER_DIAMETER,
        abs_tol=1e-12,
    )
    assert part.CAP_RECESS_FLOOR_Y - part.SIDE_TAP_DRILL_DIA / 2.0 > 0.0
    assert part.CAP_RECESS_DIAMETER_BAND == (0.20, 0.0)
    assert part.CAP_RECESS_DEPTH_BAND == (0.30, 0.0)
    recess_floor_world = TOP_SCREW_Y + part.CAP_RECESS_FLOOR_Y
    assert math.isclose(CAP_MOUTH_Y - recess_floor_world, 1.50875, abs_tol=1e-9)
    assert math.isclose(
        recess_floor_world - (TOP_SCREW_Y + TUBE_CROSS_HOLE_DIAMETER / 2.0),
        3.95,
        abs_tol=1e-9,
    )


def test_four_cross_taps_are_bottoming_10_32_with_tooling_lead() -> None:
    assert len(part.SIDE_SCREW_XS) * len(part.SIDE_SCREW_FACES) == 4
    assert part.SIDE_TAP_SPEC.kind == "tapped_bottoming"
    assert part.SIDE_TAP_SPEC.size == "#10-32"
    assert part.SIDE_TAP_SPEC.thread_class == "2B"
    assert part.SIDE_TAP_SPEC.depth_mm == CASTING_TAP_DRILL_DEPTH
    assert part.SIDE_TAP_SPEC.overrides_mm["ThreadDepth"] == CASTING_FULL_THREAD_DEPTH
    pitch = 25.4 / 32.0
    assert CASTING_TAP_DRILL_DEPTH - CASTING_FULL_THREAD_DEPTH >= 2.0 * pitch
    assert part.SPOTFACE_FLOOR == TOP_SCREW_SEAT_Z
    full_seat_limit = abs(part.FRONT_COLUMN_Z) + math.sqrt(
        (part.BOSS_DIA / 2.0) ** 2 - (part.SPOTFACE_DIA / 2.0) ** 2
    )
    assert part.SPOTFACE_FLOOR < full_seat_limit


def test_ring_envelope_and_section_view_are_explicit() -> None:
    assert part.FRONT_COLUMN_Z == -112.0
    assert part.REAR_COLUMN_Z == 112.0
    assert part.COLUMN_X == 197.0
    assert part.RING_HEIGHT == 36.5
    assert part.BOSS_DIA == 52.2
    assert math.isclose(2.0 * drawing.PLAN_HALF_X, 446.2, abs_tol=1e-9)
    assert math.isclose(2.0 * drawing.PLAN_HALF_Z, 276.2, abs_tol=1e-9)
    assert drawing.SHEET_SCALE == (1.0, 2.0)
    assert top_frame_spec.SECTION_VIEW_NOTE == "SECTION A-A SCALE 1:4"


def test_part_registry_keeps_casting_finish_requirements() -> None:
    import _config

    config = _config.parts("top-frame")
    assert config["material"] == config["material_specification"]
    assert config["material_specification"] == "LOW-CARBON STEEL OR GRAY IRON"
    finish = str(config["finish"]).lower()
    assert "sspc-sp3" in finish
    assert "alkyd primer/green enamel" in finish
    assert "75-125um dft" in finish
    assert int(config["quantity"]) == 1
