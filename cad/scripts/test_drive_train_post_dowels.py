"""#917 S1: the MHA-151 dowel pair in the drive-train assembly (SolidWorks-free).

The pins ride the swing plate, pressed into its reams, and their upper ends
slip into the post's blind reams.  These pin the relation the build asserts at
import and the registrations the assembly gates read.
"""

from __future__ import annotations

from pathlib import Path

import pytest

import build_drive_train_assembly as bdt
import cone_post_dowel_spec as dowel
import cone_swing_platform_spec as plate
import drive_train_assembly_spec as layout
from _assembly import _ALLOWED_FREE_STEMS
from _interference_contracts import _DRIVE_TRAIN_ALLOWED_PAIRS
from draw_drive_train_assembly import BOM_DESCRIPTIONS, BOM_PART_NUMBERS


def test_plate_and_post_reams_are_one_pattern_in_the_machine() -> None:
    assert bdt.POST_DOWEL_PATTERN_MISMATCH < 1e-3


def test_each_pin_is_pressed_to_its_recess_and_clears_the_post_ream_floor() -> None:
    assert bdt.POST_DOWEL_PLATE_ENGAGEMENT == pytest.approx(
        plate.PLATE_THICKNESS - dowel.POST_DOWEL_RECESS
    )
    assert bdt.POST_DOWEL_POST_ENGAGEMENT == pytest.approx(6.6)
    assert bdt.POST_DOWEL_POST_ENGAGEMENT < dowel.POST_DOWEL_BLIND_DEPTH
    # Centre plane above PlateTop: recess + half length - plate thickness.
    assert bdt._POST_DOWEL_ABOVE_PLATE_TOP == pytest.approx(0.25)


def test_the_build_inserts_and_mates_both_pins_on_the_plate_reams() -> None:
    source = Path(bdt.__file__).read_text(encoding="utf-8")
    assert "for axis_name, (dowel_x, dowel_z) in PLAT_DOWEL_AXES:" in source
    assert 'named_ref(f"{axis_name}@{platform}", "AXIS")' in source
    assert 'named_ref(f"ScrewAxis@{dowel}", "AXIS")' in source
    assert 'named_ref(f"PlateTop@{platform}", "PLANE")' in source
    assert "anti-spin" in source


def test_the_press_fit_is_a_bounded_interference_contract() -> None:
    for n in (1, 2):
        pair = frozenset((f"cone-post-dowel-{n}", "cone-swing-platform-1"))
        limit = _DRIVE_TRAIN_ALLOWED_PAIRS[pair]
        assert 0.38 < limit < 0.43
    assert not any(
        "cone-post-dowel-1" in pair and "cone-pivot-post-1" in pair
        for pair in _DRIVE_TRAIN_ALLOWED_PAIRS
    )


def test_the_pins_ride_the_swing_and_print_on_the_bom() -> None:
    assert "cone-post-dowel" in _ALLOWED_FREE_STEMS["drive-train"]
    assert BOM_PART_NUMBERS["cone-post-dowel"] == "MHA-151"
    assert "98381A304" in BOM_DESCRIPTIONS["cone-post-dowel"]
    assert "cone-post-dowel" in layout.CLUSTERS["cone-crank"]


def test_the_pin_seats_by_its_mid_length_plane_and_is_read_back_tight() -> None:
    """Main's confirmations on the BDT hunk: (i) the 0.25 press-depth distance
    assumes the dowel's Top Plane is its mid-length plane, so the build reads
    the ends from the part; (ii) the mate guard's 0.5 tolerance equals what a
    flipped 0.25 moves the pin, so the seated height is read back to 1e-3."""
    import build_cone_post_dowel as pin

    assert pin.PIN_END_Y == (-dowel.POST_DOWEL_LENGTH / 2.0, dowel.POST_DOWEL_LENGTH / 2.0)
    assert pin.TRANSFORM == pin.RigidTransform()
    from _common import _MATE_TOL_MM

    assert 2.0 * bdt._POST_DOWEL_ABOVE_PLATE_TOP >= _MATE_TOL_MM
    source = Path(bdt.__file__).read_text(encoding="utf-8")
    assert "if abs(seated[1] - dowel_o[1]) > 1e-3:" in source
