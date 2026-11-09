"""Offline tap, wall and free-eye contracts for the gooseneck's shoulder screw.

Owner ruling 2026-11-08 (Pedro), #2144 item 11.4, supersedes #1951's clamped
eye: the purchased MHA-SM-VN-56 shoulder screw seats on the flush end face of
MHA-SM-01's solid Ø.500 end piece, its thread in a plain blind tap (no
counterbore, frames or datums), and the MHA-SM-VN-51 upper eye rides free on
its shoulder under the MHA-SM-VN-57 washer.  One owner minor stands against
rule 18: the catalogue thread's engagement (sm-gooseneck RV-04, pending the
owner's confirmation).  The sheet prints decimal inch (#290): every term is
charged at the limits it prints.
"""

from __future__ import annotations

import math
import runpy
from pathlib import Path

import pytest

import _config
import machinist_exceptions
import sm_gooseneck_geom as gooseneck
import sm_gooseneck_spec as gooseneck_spec
import sm_gooseneck_spring_joint as joint
import sm_vn_counter_spring_stock_geom as spring
import sm_vn_gooseneck_shoulder_screw_spec as screw
import sm_vn_gooseneck_shoulder_washer_spec as washer
from _buildgraph import config_files_of

IN = 25.4
# The inch title block's .010 edge break.
EDGE_BREAK = 0.010 * IN


def test_catalogue_screw_and_washer_are_the_ruled_parts() -> None:
    # Owner ruling 2026-11-08, #2144 item 11.4; both SKUs auto-selected after
    # the owner's ask timed out, pending owner confirmation.  McMaster
    # 91259A535, read live 2026-11-08 (1/4 x 3/8 shoulder, 10-24 x 3/8
    # thread, B18.3); the washer McMaster 93475A250 (DIN 125 M6), read live
    # the same day.
    assert screw.SKU == "91259A535"
    assert screw.SHOULDER_DIA == pytest.approx(0.250 * IN)
    assert screw.SHOULDER_LENGTH == pytest.approx(0.375 * IN)
    assert screw.THREAD == "#10-24" and screw.THREAD_CLASS == "3A"
    assert screw.THREAD_LENGTH == pytest.approx(0.375 * IN)
    assert washer.SKU == "93475A250"
    assert (washer.ID, washer.OD, washer.THICKNESS) == pytest.approx((6.4, 12.0, 1.6))
    # The OD window: 1.0 of the eye kept at the least OD (.453), clear of the
    # leading half-turn at the largest (about .476).
    assert 0.453 * IN <= washer.OD_MIN < washer.OD_MAX <= 0.476 * IN
    for row, spec in (
        ("sm-vn-gooseneck-shoulder-screw", screw),
        ("sm-vn-gooseneck-shoulder-washer", washer),
    ):
        registry = _config.parts(row)
        assert registry["supplier_skus"] == [spec.SKU]
        assert registry["drawing_unit"] == spec.UNIT
        assert registry["process"] == "purchased"


def test_washer_slides_on_the_shoulder_and_the_head_bears_on_it() -> None:
    shoulder_max = screw.SHOULDER_DIA + max(screw.SHOULDER_DIA_BAND)
    shoulder_min = screw.SHOULDER_DIA + min(screw.SHOULDER_DIA_BAND)
    assert joint.WASHER_SHOULDER_CLEARANCE_MIN == pytest.approx(washer.ID_MIN - shoulder_max)
    assert joint.WASHER_SHOULDER_CLEARANCE_MIN > 0.0
    float_max = (washer.ID_MAX - shoulder_min) / 2.0
    assert joint.WASHER_FLOAT_MAX == pytest.approx(float_max)
    overlap = screw.HEAD_DIA_MIN / 2.0 - washer.ID_MAX / 2.0 - float_max
    assert joint.HEAD_WASHER_OVERLAP_MIN == pytest.approx(overlap)
    assert joint.HEAD_WASHER_OVERLAP_MIN > 0.0


def test_the_eye_rides_free_between_end_face_and_washer() -> None:
    # The loop's free envelope is the eye gap the native seat rests on the
    # end face, and its room is the shoulder less the washer and the head
    # fillet's stand-off, at the worst limits.
    assert joint.LOOP_ENVELOPE == gooseneck.SPRING_EYE_GAP
    space_min = (
        screw.SHOULDER_LENGTH
        + min(screw.SHOULDER_LENGTH_BAND)
        - washer.THICKNESS_MAX
        - joint.WASHER_SEAT_STANDOFF_MAX
    )
    space_max = screw.SHOULDER_LENGTH + max(screw.SHOULDER_LENGTH_BAND) - washer.THICKNESS_MIN
    assert joint.EYE_AXIAL_PLAY_MIN == pytest.approx(space_min - gooseneck.SPRING_EYE_GAP)
    assert joint.EYE_AXIAL_PLAY_MAX == pytest.approx(space_max - gooseneck.SPRING_EYE_GAP)
    assert 0.0 < joint.EYE_AXIAL_PLAY_MIN < joint.EYE_AXIAL_PLAY_MAX
    assert joint.EYE_AXIAL_PLAY_MIN == pytest.approx(2.587, abs=0.001)
    assert joint.EYE_AXIAL_PLAY_MAX == pytest.approx(3.371, abs=0.001)
    # B18.3's head fillet (Ø.276 MAX transition from the Ø.227 MIN neck) can
    # stand the washer's inner edge off the head face, never by more than the
    # fillet's radius.
    fillet_r = (screw.HEAD_FILLET_TRANSITION_DIA_MAX - screw.SHOULDER_NECK_DIA_MIN) / 2.0
    assert 0.0 < joint.WASHER_SEAT_STANDOFF_MAX < fillet_r
    # The eye swivels on the largest shoulder, and the round wire rides over
    # the under-head neck's step.
    assert joint.EYE_SHOULDER_CLEARANCE_MIN == pytest.approx(
        spring.EYE_ID_MM - screw.SHOULDER_DIA - max(screw.SHOULDER_DIA_BAND)
    )
    assert joint.EYE_SHOULDER_CLEARANCE_MIN > 0.0
    assert joint.SHOULDER_NECK_STEP_MAX < spring.WIRE_RADIUS_MM


def test_the_washer_retains_the_eye_the_bare_head_would_not() -> None:
    assert joint.WASHER_RETENTION_MIN == pytest.approx((washer.OD_MIN - spring.EYE_ID_MM) / 2.0)
    assert joint.WASHER_RETENTION_MIN >= joint.RETENTION_TARGET == 1.0
    assert joint.HEAD_ONLY_RETENTION_MIN < joint.RETENTION_TARGET


def test_plain_tap_depths_and_the_screw_tip() -> None:
    assert joint.TAP_SPEC.size == screw.THREAD_SIZE == "#10-24"
    assert joint.TAP_SPEC.thread_class == "2B"
    assert joint.TAP_SPEC.depth_mm == joint.TAP_DRILL_DEPTH
    assert joint.TAP_SPEC.overrides_mm == {"ThreadDepth": joint.TAP_THREAD_DEPTH}
    assert joint.TAP_DRILL_DIA == pytest.approx(0.1495 * IN, abs=0.001)  # #25
    assert (joint.TAP_THREAD_DEPTH, joint.TAP_DRILL_DEPTH) == pytest.approx((0.44 * IN, 0.56 * IN))
    band = 0.01 * IN  # the title block's .XX
    assert joint.TAP_DEPTH_BAND == pytest.approx(band)
    # The shoulder seats on the end face: the tip stands the catalogue thread
    # length deep, inside the shallowest full thread.
    assert joint.TIP_THREAD_MARGIN_MIN == pytest.approx(0.43 * IN - screw.THREAD_LENGTH)
    assert joint.TIP_THREAD_MARGIN_MIN > 0.0
    # The bottoming tap's 1.5-pitch lead past the deepest thread stays in the
    # shallowest drill, and the full-Ø drill stays in the shortest head.
    lead = 1.5 * screw.PITCH
    assert joint.TAP_LEAD_DRILL_MARGIN_MIN == pytest.approx(0.55 * IN - (0.45 * IN + lead))
    assert joint.TAP_LEAD_DRILL_MARGIN_MIN >= 0.0
    assert joint.TAP_DRILL_DEPTH_MAX <= joint.PLUG_HEAD_LENGTH_MIN


def test_engagement_is_the_catalogue_thread_and_its_minor() -> None:
    full_end = screw.THREAD_LENGTH - 1.5 * screw.PITCH
    start = max(screw.THREAD_NECK_WIDTH_MAX, EDGE_BREAK)
    assert joint.ENGAGEMENT_MIN == pytest.approx(min(full_end, 0.43 * IN) - start)
    assert joint.ENGAGEMENT_MIN == pytest.approx(0.2295 * IN)
    assert joint.ENGAGEMENT_MIN < 1.5 * screw.MAJOR_DIA
    assert joint.ENGAGEMENT_CALLOUT_MIN == 0.229
    assert joint.ENGAGEMENT_CALLOUT_D == 1.20
    assert joint.ENGAGEMENT_CALLOUT_MIN * IN <= joint.ENGAGEMENT_MIN
    assert joint.ENGAGEMENT_CALLOUT_D * screw.MAJOR_DIA <= joint.ENGAGEMENT_MIN


def test_summing_interference_row_is_the_seated_thread() -> None:
    # _sm_summing_interference keeps the thread length as a literal so a
    # screw edit does not re-key the summing gate; it must stay the whole
    # catalogue thread, all of it inside the tap's full thread.
    import _sm_summing_interference
    from _hole_spec import TAP_DRILL_MM, THREAD_MAJOR_MM

    assert _sm_summing_interference._GOOSENECK_THREAD_LENGTH == pytest.approx(
        screw.THREAD_LENGTH
    )
    assert screw.THREAD_LENGTH < joint.TAP_THREAD_DEPTH_MIN
    assert THREAD_MAJOR_MM[screw.THREAD] == pytest.approx(screw.MAJOR_DIA)
    assert TAP_DRILL_MM[screw.THREAD] == pytest.approx(joint.TAP_DRILL_DIA)


def test_full_worst_case_walls_meet_the_target() -> None:
    runoff = (joint.TAP_THREAD_DEPTH_MAX + joint.TAP_LEAD) * math.tan(math.radians(0.3))
    wall = (
        (gooseneck.PLUG_DIA - 0.010 * IN) / 2.0
        - (screw.MAJOR_DIA + 0.025) / 2.0
        - 0.005 * IN
        - joint.DRILL_WANDER_MAX
        - runoff
        - 2.0 * EDGE_BREAK
    )
    assert joint.PLUG_WALL_MIN == pytest.approx(wall)
    assert joint.PLUG_WALL_MIN == pytest.approx(2.9943, abs=1e-4)
    assert joint.PLUG_WALL_MIN >= joint.PLUG_WALL_TARGET == pytest.approx(0.080 * IN)
    assert joint.DRILL_POINT_SHANK_WALL_MIN >= joint.PLUG_WALL_TARGET
    # No frame and no datum: the tap's axis carries the .XXX row's offset.
    assert joint.THREAD_AXIS_OFFSET_MAX == pytest.approx(0.005 * IN)


def _declared(package: str):
    return {
        entry.id: entry.kind
        for entry in machinist_exceptions.load_exceptions(
            _config.CONFIG_DIR, package, "part"
        )
    }


def test_engagement_minor_is_declared_and_required(monkeypatch) -> None:
    declared = _declared("sm_gooseneck")
    assert declared["RV-04"] == "minor"
    # The counterbore wall and the run-out note retired with the counterbore.
    assert "RV-01" not in declared and "RV-03" not in declared
    joint.owner_minor(_config.parts("sm-gooseneck"), "RV-04", "sm_gooseneck")
    real = _config.parts

    def without(accept: bool):
        def parts(stem=None):
            row = real(stem)
            if stem != "sm-gooseneck":
                return row
            entries = [dict(entry) for entry in row["machinist_exceptions"]]
            if accept:
                for entry in entries:
                    entry["kind"] = "accept"
            else:
                entries = [entry for entry in entries if entry["id"] != "RV-04"]
            return {**row, "machinist_exceptions": entries}

        return parts

    for accept in (False, True):
        with pytest.raises(AssertionError, match="sm_gooseneck: no owner minor RV-04"):
            joint.owner_minor(without(accept)("sm-gooseneck"), "RV-04", "sm_gooseneck")
    monkeypatch.setattr(_config, "parts", without(False))
    with pytest.raises(AssertionError, match="sm_gooseneck: no owner minor RV-04"):
        runpy.run_path(gooseneck_spec.__file__)


def test_registry_reads_stay_scoped() -> None:
    # The joint and the two vendor specs read no registry row, so the channel
    # seats importing the joint through settled_spring_seats never re-key on
    # a part's row; the gooseneck spec reads its own row and the screw's.
    for module in (joint, screw, washer):
        tokens = config_files_of(Path(module.__file__))
        assert "**" not in tokens
        assert not {token for token in tokens if token.startswith("parts/")}
    tokens = config_files_of(Path(gooseneck_spec.__file__))
    assert "**" not in tokens
    assert {"parts/sm-gooseneck.yaml", "parts/sm-vn-gooseneck-shoulder-screw.yaml"} <= set(tokens)
    assert gooseneck_spec.UNIT == gooseneck.SHEET_UNIT == joint.UNIT == "in"
