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


def test_the_cone_crank_sequence_presses_the_pins_recessed_from_the_constant() -> None:
    """Main's MHA-151 eye pass: the install moved off the part sheet into the
    step that fits MHA-016 to MHA-091, with the recess read from
    POST_DOWEL_RECESS, never retyped."""
    import draw_drive_train_assembly as drawing

    steps = " ".join(drawing.CONE_CRANK_STEPS.split())
    assert "PRESS 2X MHA-151 INTO MHA-091" in steps
    assert f"RECESSED {dowel.POST_DOWEL_RECESS:.2f} INTO ITS SLIDE FACE, NEVER PROUD" in steps
    assert "MATCH-DRILL THE DOWEL PAIR" in steps
    # It sits in step 2, before step 3.
    assert steps.index("2. ") < steps.index("PRESS 2X MHA-151") < steps.index("3. THREAD MHA-097")
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "{POST_DOWEL_RECESS:.2f}" in source
    assert "RECESSED 0.25" not in source


def test_both_ream_callouts_name_the_mating_part_on_their_sheets() -> None:
    """Guard: each sheet prints its dowel ream with the MATCH-DRILL/REAM
    prefix naming the mating part (cone_post_dowel_spec)."""
    import draw_cone_pivot_post
    import draw_cone_swing_platform

    assert dowel.PLATE_DOWEL_CALLOUT.startswith("MATCH-DRILL/REAM WITH\nMHA-016")
    assert dowel.POST_DOWEL_CALLOUT.startswith("MATCH-DRILL/REAM WITH\nMHA-091")
    for module, name in (
        (draw_cone_swing_platform, "PLATE_DOWEL_CALLOUT"),
        (draw_cone_pivot_post, "FOOT_DOWEL_PREFIX"),
    ):
        assert f"process={name}," in Path(module.__file__).read_text(encoding="utf-8")
    # The post's prefix is the spec's, re-wrapped: same words, same order.
    assert draw_cone_pivot_post.FOOT_DOWEL_PREFIX.split() == dowel.POST_DOWEL_CALLOUT.split()


def test_step_2_dowels_the_post_before_the_screws_are_tightened() -> None:
    """Codex on #929 (PRRT_kwDOPHDy386mOPDM): step 2 screwed MHA-016 down and
    never fitted the dowels.  The order is: MHA-142 finger-tight, the post
    positioned at fit-up, the pair match-drilled through MHA-091 into
    MHA-016 and reamed per each print, MHA-151 pressed in from below and
    recessed, MHA-016 slipped over them, and only then the screws tightened.
    The printed engagement is the platform spec's floored worst case, not a
    retyped range."""
    import cone_swing_platform_spec as platform
    import draw_drive_train_assembly as drawing

    steps = " ".join(drawing.CONE_CRANK_STEPS.split())
    step2 = steps[steps.index("2. ") : steps.index("3. THREAD MHA-097")]
    order = (
        "FINGER-TIGHT",
        "AT FIT-UP",
        "MATCH-DRILL THE DOWEL PAIR",
        "THROUGH MHA-091 INTO MHA-016",
        "REAM EACH PART PER ITS PRINT",
        "PRESS 2X MHA-151 INTO MHA-091 FROM BELOW",
        f"RECESSED {dowel.POST_DOWEL_RECESS:.2f} INTO ITS SLIDE FACE, NEVER PROUD",
        "SLIP MHA-016 OVER THEM",
        "TIGHTEN BOTH",
    )
    positions = [step2.find(phrase) for phrase in order]
    assert -1 not in positions, dict(zip(order, positions))
    assert positions == sorted(positions), dict(zip(order, positions))
    assert "SCREW MHA-016 TO MHA-091" not in step2
    # The floor, and nothing of our governance (Main, S1 round 5).
    assert f"ENGAGEMENT {platform.POST_MOUNT_ENGAGEMENT_PRINTED:.2f}D MIN." in step2
    assert "RULE" not in step2 and "EXCEPTION" not in step2
    assert "5.92" not in step2
    source = Path(drawing.__file__).read_text(encoding="utf-8")
    assert "{POST_MOUNT_ENGAGEMENT_PRINTED:.2f}D MIN" in source
