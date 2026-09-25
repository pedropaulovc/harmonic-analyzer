"""Behavioral release contracts for the separate MHA-058 grip crossrod."""

from __future__ import annotations

import re
from pathlib import Path

import pytest

import _config
import build_drive_train_assembly as assembly
import build_pinion_handle as part
import draw_pinion_handle as drawing
import pinion_handle_geometry as geometry
import pinion_arbor_spec as arbor
import pinion_handle_spec as spec
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS
from _drawing_registry import DRAWINGS_BY_NAME, DrawingLayout


def test_registry_slug_now_describes_the_separate_grip_crossrod() -> None:
    registered = DRAWINGS_BY_NAME["pinion_handle"]
    assert registered.artifact_stem == "pinion-handle"
    assert registered.layout == DrawingLayout.LANDSCAPE
    assert registered.script == Path(drawing.__file__).resolve()
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/pinion-handle.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/pinion-handle.pdf")
    assert drawing.PNG.as_posix().endswith("/png/pinion-handle_drawing.png")


def test_crossrod_preserves_released_geometry_and_local_origin() -> None:
    # R1: as-received Ø6 bar, bonded into MHA-102 (no longer a 6.0175 press rod).
    assert spec.ROD_DIA == pytest.approx(6.0)
    # Rule 6: the bond and its acceptance are the fit-up step, not notes.
    assert spec.DRAWING_NOTES == "USE COLD-FINISHED BAR AS RECEIVED."
    assert spec.ASSEMBLY_STEP == (
        "BOND MHA-058 INTO MHA-102 HEAD WITH LOCTITE 638; "
        "INSTALLED ROD SHALL NOT TURN OR SLIDE BY HAND."
    )
    assert "MATCH-REAM" not in spec.DRAWING_NOTES
    assert spec.ROD_DOWN == pytest.approx(32.0)
    assert spec.ROD_UP == pytest.approx(33.0)
    assert spec.ROD_SPAN == pytest.approx(65.0)
    assert spec.ROD_SPAN == pytest.approx(spec.ROD_DOWN + spec.ROD_UP)
    assert part.V_ROD == pytest.approx(
        3.141592653589793 * (spec.ROD_DIA / 2.0) ** 2 * spec.ROD_SPAN
    )

def _world_point(
    origin: tuple[float, float, float] | list[float],
    rows: list[list[float]],
    local: tuple[float, float, float],
) -> tuple[float, float, float]:
    return tuple(
        origin[axis]
        + local[0] * rows[0][axis]
        + local[1] * rows[1][axis]
        + local[2] * rows[2][axis]
        for axis in range(3)
    )


def _world_vector(
    rows: list[list[float]], local: tuple[float, float, float]
) -> tuple[float, float, float]:
    return _world_point((0.0, 0.0, 0.0), rows, local)


def test_integral_cutover_preserves_head_axis_and_crossrod_world_transform() -> None:
    # Released construction: MHA-058's component origin was the head/crossrod
    # axis, with the old Ø15x9 head followed by a 2 mm wall.  New construction:
    # that head centre is MHA-102 local z=-6.5; MHA-058 keeps its own origin.
    # Codex #854/#858 P1 (Main): the assembly shows the fit-up stack, where the
    # back stop puts the drum -- and the arbor it is bonded on -- 0.25 aft of
    # the released -135.0 arbor station, and RIG_AFT_SHIFT a further 0.97 (user
    # ruling P1-2: what the rig-set leaf D off g19 leaves, for j = 19's full
    # face with margin).  Every released station below moves by exactly that,
    # and nothing else about the cutover changes.
    import pinion_rig_layout as rig

    fitup_shift = assembly.ARBOR_Z0 - (-135.0 + assembly.MECHANISM_Z_SHIFT)
    assert fitup_shift == pytest.approx(0.25 + rig.RIG_AFT_SHIFT, abs=1e-9)
    released_origin = (
        assembly.APINION_X,
        assembly.APINION_Y,
        -135.0 + assembly.MECHANISM_Z_SHIFT - (9.0 / 2.0 + 2.0) + fitup_shift,
    )
    new_head_axis = _world_point(
        (assembly.APINION_X, assembly.APINION_Y, assembly.ARBOR_Z0),
        assembly.ARBOR_ROWS,
        (0.0, 0.0, arbor.HEAD_CENTER_Z),
    )
    new_crossrod_axis = _world_point(
        (assembly.APINION_X, assembly.APINION_Y, assembly.HANDLE_Z),
        assembly.HANDLE_ROWS,
        (0.0, 0.0, 0.0),
    )
    rod_axis = _world_vector(assembly.HANDLE_ROWS, (0.0, 1.0, 0.0))
    bore_axis = _world_vector(assembly.ARBOR_ROWS, (0.0, 1.0, 0.0))
    shaft_axis = _world_vector(assembly.ARBOR_ROWS, (0.0, 0.0, 1.0))
    expected_grip_axis = (
        -0.9063077870366499,
        0.42261826174069944,
        0.0,
    )
    # x follows the drum's parked station: U28 (2026-09-23) parks it with a
    # 2.2425 tip gap to the review-first 32T drum's 8.667 tip radius.
    expected_axis = (-18.383940352466745, 90.518, -137.18811169145133)
    # Rule 12 (audit W6): the head grows 9.0 -> 10.5 about the released
    # centre, so both faces and the crown move 0.75 out; the neck shoulder
    # (the released head rear + 2 wall + 10) stays put.
    released_head_stations = (
        released_origin[2] - 10.5 / 2.0,
        released_origin[2] + 10.5 / 2.0,
        released_origin[2] - (10.5 / 2.0 + 3.0),
        released_origin[2] + 9.0 / 2.0 + 2.0 + 10.0,
    )
    integral_head_stations = (
        assembly.ARBOR_Z0 + arbor.HEAD_FRONT_Z,
        assembly.ARBOR_Z0 + arbor.HEAD_REAR_Z,
        assembly.ARBOR_Z0 + arbor.HEAD_FRONT_Z - arbor.HEAD_CAP_SAG,
        assembly.ARBOR_Z0 + arbor.NECK_END_Z,
    )
    assert integral_head_stations == pytest.approx(
        released_head_stations, abs=1e-12
    )
    assert integral_head_stations == pytest.approx(
        (
            -142.43811169145133,
            -131.93811169145133,
            -145.43811169145133,
            -120.68811169145133,
        ),
        abs=1e-12,
    )
    assert released_origin == pytest.approx(expected_axis, abs=1e-12)
    assert new_head_axis == pytest.approx(released_origin, abs=1e-12)
    assert new_crossrod_axis == pytest.approx(released_origin, abs=1e-12)
    assert rod_axis == pytest.approx(expected_grip_axis, abs=1e-12)
    assert bore_axis == pytest.approx(rod_axis, abs=1e-12)
    assert shaft_axis == pytest.approx((0.0, 0.0, 1.0), abs=1e-12)

    for local, expected in (
        (
            (0.0, -32.0, 0.0),
            (10.617908832706053, 76.99421562429762, -137.18811169145133),
        ),
        (
            (0.0, 33.0, 0.0),
            (-48.29209732467619, 104.46440263744309, -137.18811169145133),
        ),
    ):
        released_endpoint = _world_point(released_origin, assembly.HANDLE_ROWS, local)
        new_endpoint = _world_point(
            (assembly.APINION_X, assembly.APINION_Y, assembly.HANDLE_Z),
            assembly.HANDLE_ROWS,
            local,
        )
        assert released_endpoint == pytest.approx(expected, abs=1e-12)
        assert new_endpoint == pytest.approx(released_endpoint, abs=1e-12)


def test_spec_is_the_single_source_of_every_printed_dimension() -> None:
    assert part.DRAWING_DIMENSIONS is spec.DRAWING_DIMENSIONS
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    kept = set(drawing.DONOR_KEEP) | set(drawing.PRINCIPAL_KEEP)
    assert marked == kept == {"RodDia", "RodSpan"}
    assert spec.DRAWING_PRECISION_BY_NAME == {"RodDia": 1, "RodSpan": 1}
    assert Path(drawing.__file__).name in PRECISION_MIGRATED_DRAWINGS


def test_retired_head_socket_and_retention_exports_are_absent() -> None:
    retired = {
        "GRIP_DIA",
        "GRIP_LEN",
        "CAP_SAG",
        "CAP_RADIUS",
        "ROD_HOLE_DIA",
        "TUBE_ID",
        "TUBE_LEN",
        "TUBE_OD",
        "WALL_T",
        "RETENTION_PIN_DIA",
        "RETENTION_PIN_LEN",
        "RETENTION_PIN_CENTER_Z",
    }
    assert retired.isdisjoint(vars(geometry))
    assert retired.isdisjoint(vars(spec))


def test_part_metadata_names_the_grip_crossrod_work() -> None:
    config = _config.parts("pinion-handle")
    assert config["title"] == "Pinion Grip Cross Rod"
    assert "cold-finished steel rod" in str(config["material_specification"])
    assert "crossrod" in str(config["process"])
    assert int(config["quantity"]) == 1


def test_no_note_line_carries_a_dimension() -> None:
    """Rule 6 (Codex P1 on #814): the Ø6 bar size lives in the registry's
    material specification and the imported RodDia, never in a note."""
    for line in spec.DRAWING_NOTES.splitlines():
        text = re.sub(r"MHA-\d+", "", line).replace(arbor.RETAINING_COMPOUND, "")
        assert not re.search(r"\d", text), line
    assert "USE COLD-FINISHED BAR AS RECEIVED." in spec.DRAWING_NOTES
    assert "6 mm" in _config.parts("pinion-handle")["material_specification"]

