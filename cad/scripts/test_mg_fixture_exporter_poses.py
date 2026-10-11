"""The web exporters' drawing-free fixture poses equal the recipe's placements.

Original: ``build_mg_magnifier_assembly``'s ``FIXTURE_*`` constants (the
placements mg-magnifier.SLDASM is built from). New: the same poses rederived by
``web/scripts/native_identity_source.output_fixture_installation`` from
``mg_output_fixture_geom`` + thumb-screw stock + ``_transforms`` only, so the
exporters never import the COM recipe for the fixture or its second thumb
screw. SolidWorks-free; lives here because the web runner imports the CAD tree
with ``--no-project`` and cannot load the recipe module.
"""

from __future__ import annotations

import importlib.util
import math
from pathlib import Path

import build_mg_magnifier_assembly as assembly
import mg_lever_wire_geom as wire
import mg_output_fixture_geom as fixture
import _mcmaster_91882a221 as thumb
import _transforms as transforms
from mg_magnifying_vertical_rod_geom import ROD_DIA

_SPEC = importlib.util.spec_from_file_location(
    "native_identity_source",
    Path(__file__).resolve().parents[2] / "web" / "scripts" / "native_identity_source.py",
)
_SOURCE = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_SOURCE)

REST = _SOURCE.output_fixture_installation(wire.CLAMP_X, fixture, ROD_DIA, thumb, transforms)


def _same(actual, expected) -> bool:
    return len(actual) == len(expected) and all(
        math.isclose(a, b, abs_tol=1e-9) for a, b in zip(actual, expected, strict=True)
    )


def _same_rows(actual, expected) -> bool:
    return len(actual) == 3 and all(_same(a, b) for a, b in zip(actual, expected, strict=True))


def test_fixture_pose_matches_the_recipe_placement() -> None:
    assert _same(REST["fixturePositionMm"], assembly.FIXTURE_POSITION)
    assert _same_rows(REST["fixtureRows"], assembly.FIXTURE_ROWS)


def test_yaw_is_the_owner_yaw_about_the_vertical_rod_not_the_old_identity() -> None:
    # The pre-hex collar sat at IDENTITY on a bottom origin; the hex body yaws
    # about the vertical rod (machine Y) by the owner's solved angle.
    rows = REST["fixtureRows"]
    # Pure Ry: row0 = [cos b, 0, -sin b], row2 = [sin b, 0, cos b].
    measured_deg = math.degrees(math.atan2(-rows[0][2], rows[0][0]))
    wrapped = (measured_deg - 180.0 - fixture.FIXTURE_YAW_DEG + 180.0) % 360.0 - 180.0
    assert math.isclose(wrapped, 0.0, abs_tol=1e-9), measured_deg
    assert not math.isclose(fixture.FIXTURE_YAW_DEG % 360.0, 0.0, abs_tol=1e-9)
    # Vertical extent is yaw-invariant (local Y stays machine Y), so the
    # exporters' rod-engagement band uses the hex half-extent unrotated.
    assert _same(rows[1], [0.0, 1.0, 0.0])
    assert _same_rows(rows, transforms.rows_from_euler([0.0, 180.0 + fixture.FIXTURE_YAW_DEG, 0.0]))


def test_rotated_hook_lands_on_the_lever_wire_start() -> None:
    assert _same(REST["hookMm"], wire.WIRE_START)
    assert _same(REST["hookMm"], assembly.HUB_WIRE_START)


def test_second_thumb_screw_pose_matches_the_recipe_placement() -> None:
    assert _same(REST["screwPositionMm"], assembly.FIXTURE_SCREW_POSITION)
    assert _same_rows(REST["screwRows"], assembly.FIXTURE_SCREW_ROWS)
    # Shank runs from the outer head face back along the fixture axis to a tip
    # tangent to the vertical rod; the collar stands off the spigot face.
    rows = REST["fixtureRows"]
    assert _same(
        REST["screwTipMm"],
        [p + ROD_DIA / 2.0 * rows[0][k] for k, p in enumerate(REST["fixturePositionMm"])],
    )
    shank = REST["screwShankLocalMm"]
    tip_from_screw = [
        origin + sum(shank[i] * REST["screwRows"][i][axis] for i in range(3))
        for axis, origin in enumerate(REST["screwPositionMm"])
    ]
    assert _same(tip_from_screw, REST["screwTipMm"])
    collar_x = ROD_DIA / 2.0 + thumb.SHANK_LEN
    assert collar_x > fixture.SPIGOT_FACE_X
    assert math.isclose(collar_x - fixture.SPIGOT_FACE_X, assembly.FIXTURE_SCREW_STANDOFF, abs_tol=1e-9)
