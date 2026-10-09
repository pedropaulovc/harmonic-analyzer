"""Behavioral release contracts for the separate MHA-DT-015 grip crossrod."""

from __future__ import annotations

import math
import re
from pathlib import Path

import pytest

import _config
import build_dt_drive_train_assembly as assembly
import build_dt_pinion_handle as part
import draw_dt_pinion_handle as drawing
import dt_pinion_handle_geometry as geometry
import dt_pinion_arbor_geometry as arbor_geometry
import dt_pinion_arbor_spec as arbor
import dt_pinion_handle_spec as spec
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS
from _drawing_registry import DRAWINGS_BY_NAME, DrawingLayout
from dt_cone_pivot_post_installation import MECHANISM_Z_SHIFT


def test_registry_slug_now_describes_the_separate_grip_crossrod() -> None:
    registered = DRAWINGS_BY_NAME["dt_pinion_handle"]
    assert registered.artifact_stem == "dt-pinion-handle"
    assert registered.layout == DrawingLayout.LANDSCAPE
    assert registered.script == Path(drawing.__file__).resolve()
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/dt-pinion-handle.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/dt-pinion-handle.pdf")
    assert drawing.PNG.as_posix().endswith("/png/dt-pinion-handle_drawing.png")


def test_crossrod_preserves_released_geometry_and_local_origin() -> None:
    # R1: as-received Ø6 bar, bonded into MHA-DT-022 (no longer a 6.0175 press rod).
    assert spec.ROD_DIA == pytest.approx(6.0)
    # Rule 6: the bond and its acceptance are the fit-up step, not notes.
    assert spec.DRAWING_NOTES == "USE COLD-FINISHED BAR AS RECEIVED."
    assert spec.ASSEMBLY_STEP == (
        "BOND MHA-DT-015 INTO MHA-DT-022 HEAD WITH LOCTITE 638; "
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
    # Released construction: MHA-DT-015's component origin was the head/crossrod
    # axis, with the old Ø15x9 head followed by a 2 mm wall.  New construction:
    # that head centre is MHA-DT-022 local z=-6.5; MHA-DT-015 keeps its own origin.
    # Codex #854/#858 P1 (Main): the assembly shows the fit-up stack, where the
    # back stop puts the drum -- and the arbor it is bonded on -- 0.25 aft of
    # the released arbor station, plus RIG_AFT_SHIFT set from the configured
    # g19 datum (user ruling P1-2: rig-set leaf D keeps its full face with
    # margin). Train pitch edits move the datum, not the cutover's local
    # head or crossrod geometry.
    import pinion_rig_layout as rig
    import pinion_rig_park_geometry as park

    fitup_shift = assembly.ARBOR_Z0 - (-135.0 + MECHANISM_Z_SHIFT)
    assert fitup_shift == pytest.approx(0.25 + rig.RIG_AFT_SHIFT, abs=1e-9)
    released_origin = (
        assembly.APINION_X,
        assembly.APINION_Y,
        -135.0 + MECHANISM_Z_SHIFT - (9.0 / 2.0 + 2.0) + fitup_shift,
    )
    new_head_axis = _world_point(
        (assembly.APINION_X, assembly.APINION_Y, assembly.ARBOR_Z0),
        assembly.ARBOR_ROWS,
        (0.0, 0.0, arbor_geometry.HEAD_CENTER_Z),
    )
    new_crossrod_axis = _world_point(
        (assembly.APINION_X, assembly.APINION_Y, assembly.HANDLE_Z),
        assembly.HANDLE_ROWS,
        (0.0, 0.0, 0.0),
    )
    rod_axis = _world_vector(assembly.HANDLE_ROWS, (0.0, 1.0, 0.0))
    bore_axis = _world_vector(assembly.ARBOR_ROWS, (0.0, 1.0, 0.0))
    shaft_axis = _world_vector(assembly.ARBOR_ROWS, (0.0, 0.0, 1.0))
    grip_angle = math.radians(65.0)  # released grip clock from vertical
    expected_grip_axis = (-math.sin(grip_angle), math.cos(grip_angle), 0.0)
    # Park on the configured level line of centres, with the specified tip
    # gap. Axially the back drum face is leaf D off the configured bank datum;
    # the original drum-to-arbor bond station and head centre stay local.
    module_mm = 25.4 / _config.machine("gear_train", "diametral_pitch")
    expected_arbor_z = (
        rig.G19_BACK_FACE_Z
        + rig.RIG_SET_LEAF_D
        - rig.DRUM_LEN
        - arbor_geometry.DRUM_FRONT_Z_AS_BUILT
        - arbor_geometry.DRUM_AFT_SHIFT
    )
    expected_axis = (
        park.X_DRUM
        + (int(_config.machine("gear_train", "cylinder_teeth")) + 2) * module_mm / 2.0
        + (int(_config.machine("alignment_pinion", "teeth")) + 2) * module_mm / 2.0
        + _config.machine("alignment_pinion", "disengaged_tip_gap_mm"),
        park.Y_DRIVE,
        expected_arbor_z - (9.0 / 2.0 + 2.0),
    )
    # Rule 12 (audit W6) grew the head 9.0 -> 10.5 and the machinist review of
    # 7f7fc1717 (Main's option 2) to 11.5, each about the released centre, so
    # both faces and the crown move 1.25 out.  The neck shoulder (the released
    # head rear + 2 wall + 10) moves 0.25 forward, so every turned length on
    # the MHA-DT-022 print lands on .X.
    released_head_stations = (
        released_origin[2] - 11.5 / 2.0,
        released_origin[2] + 11.5 / 2.0,
        released_origin[2] - (11.5 / 2.0 + 3.0),
        released_origin[2] + 9.0 / 2.0 + 2.0 + 10.0 - 0.25,
    )
    integral_head_stations = (
        assembly.ARBOR_Z0 + arbor_geometry.HEAD_FRONT_Z,
        assembly.ARBOR_Z0 + arbor_geometry.HEAD_REAR_Z,
        assembly.ARBOR_Z0 + arbor_geometry.HEAD_FRONT_Z - arbor_geometry.HEAD_CAP_SAG,
        assembly.ARBOR_Z0 + arbor_geometry.NECK_END_Z,
    )
    assert integral_head_stations == pytest.approx(
        released_head_stations, abs=1e-12
    )
    assert integral_head_stations == pytest.approx(
        (
            expected_axis[2] - 11.5 / 2.0,
            expected_axis[2] + 11.5 / 2.0,
            expected_axis[2] - (11.5 / 2.0 + 3.0),
            expected_axis[2] + 9.0 / 2.0 + 2.0 + 10.0 - 0.25,
        ),
        abs=1e-12,
    )
    assert released_origin == pytest.approx(expected_axis, abs=1e-12)
    assert new_head_axis == pytest.approx(released_origin, abs=1e-12)
    assert new_crossrod_axis == pytest.approx(released_origin, abs=1e-12)
    assert rod_axis == pytest.approx(expected_grip_axis, abs=1e-12)
    assert bore_axis == pytest.approx(rod_axis, abs=1e-12)
    assert shaft_axis == pytest.approx((0.0, 0.0, 1.0), abs=1e-12)

    for distance in (-spec.ROD_DOWN, spec.ROD_UP):
        local = (0.0, distance, 0.0)
        expected = tuple(
            expected_axis[axis] + distance * expected_grip_axis[axis]
            for axis in range(3)
        )
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


def test_view_group_is_centred_on_the_sheet_field() -> None:
    """Machinist review of 7f7fc1717: the profile, dimensions and isometric
    sat low and right.  The group's vertical span now centres on the field
    between the title block and the inner border."""
    lowest = drawing.PRINCIPAL_KEEP["RodSpan"][1]
    highest = max(drawing.ROD_DIAMETER_XY[1], drawing.ISO_NOTE_XY[1])
    field_mid = sum(drawing.FIELD_Y) / 2.0
    assert abs((lowest + highest) / 2.0 - field_mid) <= 0.005
    assert drawing.PRINCIPAL_CENTER[1] == pytest.approx(field_mid, abs=0.010)
    # The profile's left end stands in the left half of the sheet's width.
    from dt_pinion_handle_geometry import ROD_SPAN

    rod_half = ROD_SPAN * drawing.SHEET_SCALE[0] / 2000.0
    assert drawing.PRINCIPAL_CENTER[0] - rod_half < 0.110


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
    config = _config.parts("dt-pinion-handle")
    assert config["title"] == "Pinion Grip Cross Rod"
    assert "cold-finished steel rod" in str(config["material_specification"])
    assert "crossrod" in str(config["process"])
    assert int(config["quantity"]) == 1


def test_no_note_line_carries_a_dimension() -> None:
    """Rule 6 (Codex P1 on #814): the Ø6 bar size lives in the registry's
    material specification and the imported RodDia, never in a note."""
    for line in spec.DRAWING_NOTES.splitlines():
        text = re.sub(r"MHA-[A-Z]{2}-\d{3}(?:-T\d{3})?", "", line).replace(arbor.RETAINING_COMPOUND, "")
        assert not re.search(r"\d", text), line
    assert "USE COLD-FINISHED BAR AS RECEIVED." in spec.DRAWING_NOTES
    assert "6 mm" in _config.parts("dt-pinion-handle")["material_specification"]

