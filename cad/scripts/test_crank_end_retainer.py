"""Offline geometry and assembly contracts for the coaxial crank-end retainer."""

from __future__ import annotations

from pathlib import Path

import _config
import build_drive_train_assembly as drive
import crank_end_retainer_spec as retainer
from _fastener_catalog import DriveStyle, HeadStyle, fastener
from _holes import (
    DRILL_POINT_H,
    TAP_DRILL_MM,
    THREAD_MAJOR_MM,
    HoleSpec,
    _blind_tap_thread_depth_m,
)
from _interference_contracts import allowed_interference_pairs
from crank_arm_spec import ARM_WIDTH


SCRIPTS = Path(__file__).resolve().parent


def test_broad_annular_cap_matches_the_crank_arm_boss() -> None:
    assert retainer.WASHER_OD == ARM_WIDTH == 16.0
    assert 0.0 < retainer.WASHER_ID < retainer.SCREW_HEAD_DIA < retainer.WASHER_OD
    assert retainer.WASHER_ID - THREAD_MAJOR_MM["#0-80"] >= 0.25
    assert retainer.WASHER_THICK == 1.0
    inventory = _config.parts("crank-end-washer")
    washer = __import__("build_crank_end_washer")
    assert washer.MATERIAL == inventory["material"]
    assert inventory["number"] == "MHA-131"
    assert int(inventory["quantity"]) == 1


def test_dedicated_screw_is_the_registered_short_slotted_hardware() -> None:
    screw = fastener("crank-retainer-screw")
    assert screw.thread == retainer.SCREW_THREAD == "#0-80"
    assert screw.length_mm == retainer.SCREW_SHANK_LEN
    assert screw.model_diameter_mm == retainer.SCREW_SHANK_DIA
    assert screw.head is HeadStyle.FILLISTER
    assert screw.drive is DriveStyle.SLOT
    assert screw.material == "Brass"
    assert (SCRIPTS / "build_crank_end_washer.py").is_file()
    source = (SCRIPTS / "build_crank_retainer_screw.py").read_text(encoding="utf-8")
    assert "extrude_at_offset(adapter, SCREW_HEAD_H, 0.0, flip=True)" in source
    inventory = _config.parts("crank-retainer-screw")
    assert inventory["number"] == "MHA-132"
    assert int(inventory["quantity"]) == 1
    assert "#0-80" in str(inventory["process"])


def test_shaft_tap_and_screw_stop_before_the_finished_taper() -> None:
    assert retainer.SHAFT_TAP_DRILL_DIA == TAP_DRILL_MM["#0-80"]
    assert abs(retainer.FINISHED_TAPER_NEAR_END - 1.1546875) < 1e-12
    assert retainer.SHAFT_TAP_TO_FINISHED_TAPER_WEB >= retainer.MIN_TAP_TO_TAPER_WEB
    assert abs(retainer.SHAFT_TAP_TO_FINISHED_TAPER_WEB - 0.21687537000000012) < 1e-12
    assert retainer.SHAFT_TAP_POINT_END == (
        retainer.SHAFT_TAP_DRILL_DEPTH
        + retainer.SHAFT_TAP_DRILL_DIA / 2.0 * DRILL_POINT_H
    )
    shaft_tap = HoleSpec(
        "tapped_bottoming",
        retainer.SCREW_THREAD,
        end="blind",
        depth_mm=retainer.SHAFT_TAP_DRILL_DEPTH,
        overrides_mm={"ThreadDepth": retainer.SHAFT_THREAD_DEPTH},
    )
    assert _blind_tap_thread_depth_m(shaft_tap) == (
        retainer.SHAFT_THREAD_DEPTH / 1000.0
    )
    default_depth = HoleSpec(
        "tapped_bottoming",
        retainer.SCREW_THREAD,
        end="blind",
        depth_mm=retainer.SHAFT_TAP_DRILL_DEPTH,
    )
    assert _blind_tap_thread_depth_m(default_depth) == (
        retainer.SHAFT_TAP_DRILL_DEPTH / 1000.0
    )
    shaft_source = (SCRIPTS / "build_crankshaft.py").read_text(encoding="utf-8")
    assert '"tapped_bottoming"' in shaft_source
    assert "crank-end retaining tap (#0-80 bottoming)" in shaft_source
    assert 0.0 < retainer.SCREW_ENGAGEMENT <= retainer.SHAFT_THREAD_DEPTH
    assert retainer.SCREW_ENGAGED_TURNS >= retainer.MIN_ENGAGED_TURNS
    assert (
        retainer.SCREW_ENGAGEMENT + retainer.MIN_SCREW_TO_TAPER_CLEARANCE
        < retainer.FINISHED_TAPER_NEAR_END
    )
    assert abs(retainer.SCREW_TO_FINISHED_TAPER_CLEARANCE - 0.6046875) < 1e-12
    assert (
        drive.CRANK_RETAINER_TIP_Z + retainer.MIN_SCREW_TO_TAPER_CLEARANCE
        < drive.CRANK_TAPER_NEAR_END_Z
    )
    assert not any(
        "crank-end-washer" in pair or "crank-retainer-screw" in pair
        for pair in allowed_interference_pairs("drive-train")
    )


def test_assembly_inventory_and_exact_coaxial_seats_are_pinned() -> None:
    assert drive.CRANK_END_COMPONENT_STEMS == (
        "crank-end-washer",
        "crank-retainer-screw",
    )
    assert drive.CRANK_END_WASHER_Z0 == drive.CRANK_ARM_Z0 - retainer.WASHER_THICK
    assert drive.CRANK_RETAINER_SCREW_Z0 == drive.CRANK_END_WASHER_Z0
    assert drive.CRANK_RETAINER_TIP_Z == (
        drive.CRANK_ARM_Z0 + retainer.SCREW_ENGAGEMENT
    )


def test_assembly_rigidly_locks_both_retainer_components_without_a_new_dof() -> None:
    source = (SCRIPTS / "build_drive_train_assembly.py").read_text(encoding="utf-8")
    for token in (
        "CRANK_END_COMPONENT_STEMS[0]",
        "CRANK_END_COMPONENT_STEMS[1]",
        'label="crank-end washer rigidly retained on shaft"',
        'label="crank-end screw rigidly retained through washer"',
        "assert_free_dof_necessity(\n        adapter,\n        4,",
    ):
        assert token in source
