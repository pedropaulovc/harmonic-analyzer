"""Offline manufacturing contracts for the cone-tip-block drawing."""

from __future__ import annotations

from pathlib import Path

import build_cone_tip_block as part
import cone_tip_block_spec
import draw_cone_tip_block as drawing
from _drawing_registry import DRAWINGS_BY_NAME
from _hole_spec import blind_cut_dia_mm
from _surface_finish import SEAT_UM


def test_required_drawing_paths() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/cone-tip-block.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/cone-tip-block.pdf")
    assert drawing.PNG.as_posix().endswith("/png/cone-tip-block_drawing.png")
    assert DRAWINGS_BY_NAME["cone_tip_block"].script == Path(drawing.__file__).resolve()


def test_tip_passage_is_the_adjuster_cup_clearance_envelope() -> None:
    """The block admits the tip; it must not become a second bearing journal."""
    assert part.SHAFT_PASSAGE_DIA == cone_tip_block_spec.SHAFT_PASSAGE_DIA
    assert part.SHAFT_PASSAGE_DIA == 2.0 * part.SHAFT_PASSAGE_RADIUS
    assert part.SHAFT_PASSAGE_DIA < part.ADJUSTER_BORE_DIA
    callout = drawing.DIMENSION_CALLOUTS["PassageDiaDim"].upper()
    assert "THRU" in callout
    assert "CLEARANCE" in callout

def test_adjuster_tap_has_lead_beyond_the_required_full_thread() -> None:
    """A blind tap cannot deliver full threads to its drill shoulder."""
    spec = part.ADJUSTER_BORE_SPEC
    thread_depth = spec.overrides_mm["ThreadDepth"]
    assert 0.0 < thread_depth < spec.depth_mm
    assert thread_depth == cone_tip_block_spec.ADJUSTER_THREAD_DEPTH


def test_pinch_joint_uses_entry_clearance_and_opposite_jaw_thread() -> None:
    """The screw must pass one jaw and engage the other, not bind in both."""
    tap = part.PINCH_BORE_SPEC
    clearance = part.PINCH_CLEARANCE_SPEC
    assert tap is cone_tip_block_spec.PINCH_BORE_SPEC
    assert tap.kind == "tapped"
    assert tap.size == cone_tip_block_spec.PINCH_THREAD
    assert tap.end == "through_all"
    assert clearance is cone_tip_block_spec.PINCH_CLEARANCE_SPEC
    assert clearance.kind == "clearance"
    assert clearance.size == "#4"
    assert clearance.fit == "normal"
    assert clearance.end == "blind"
    assert clearance.depth_mm == (part.BLOCK_X - part.SLIT_W) / 2.0
    assert part.PINCH_BORE_DIA == blind_cut_dia_mm(tap)
    assert part.PINCH_CLEARANCE_DIA == blind_cut_dia_mm(clearance)
    assert part.PINCH_CLEARANCE_DIA > part.PINCH_BORE_DIA


def test_pinch_spacing_closes_every_print_tolerance_stack() -> None:
    """The user-approved relative axis control prevents both breakout and collision."""
    assert abs(part.PINCH_BORE_Y - part.ADJUSTER_AXIS_HEIGHT - part.PINCH_RISE) < 1e-12
    assert abs(
        cone_tip_block_spec.BLOCK_HEIGHT
        - cone_tip_block_spec.SLIT_DEPTH
        - cone_tip_block_spec.SLIT_FLOOR
    ) < 1e-12
    assert (
        cone_tip_block_spec.WORST_CLEARANCE_TO_ADJUSTER_MM
        >= cone_tip_block_spec.MIN_CLEARANCE_TO_ADJUSTER_MM
    )
    assert cone_tip_block_spec.WORST_SCREW_ENVELOPE_GAP_MM > 0.0
    assert (
        cone_tip_block_spec.WORST_TOP_LIGAMENT_MM
        >= cone_tip_block_spec.MIN_TOP_LIGAMENT_MM
    )
    assert (
        cone_tip_block_spec.WORST_ADJUSTER_SIDE_LIGAMENT_MM
        >= cone_tip_block_spec.MIN_SIDE_LIGAMENT_MM
    )
    assert (
        cone_tip_block_spec.WORST_PINCH_DEPTH_LIGAMENT_MM
        >= cone_tip_block_spec.MIN_SIDE_LIGAMENT_MM
    )
    tap_bottom = part.PINCH_BORE_Y - part.PINCH_BORE_DIA / 2.0
    assert cone_tip_block_spec.SLIT_FLOOR <= tap_bottom


def test_foot_seat_is_the_only_locating_surface_finish() -> None:
    (finish,) = cone_tip_block_spec.SURFACE_FINISHES
    assert finish.key == "foot_seat"
    assert finish.roughness_um == SEAT_UM
    assert finish.face.normal == (0, -1, 0)
    assert finish.face.offset_mm == 0.0


def test_part_config_preserves_manufacturing_metadata() -> None:
    import _config

    config = _config.parts("cone-tip-block")
    assert "1018" in str(config["material_specification"])
    assert "1018" in str(config["material"])
    assert config["finish"]
    assert int(config["quantity"]) == 1
