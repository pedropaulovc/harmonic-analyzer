"""Behavioral release contracts for the separate MHA-058 grip crossrod."""

from __future__ import annotations

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
    assert spec.ROD_DIA == pytest.approx(6.0175)
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
    released_origin = (
        assembly.APINION_X,
        assembly.APINION_Y,
        -135.0 + assembly.MECHANISM_Z_SHIFT - (9.0 / 2.0 + 2.0),
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
    expected_axis = (-16.077263315132342, 90.518, -138.41241221957347)
    released_head_stations = (
        released_origin[2] - 9.0 / 2.0,
        released_origin[2] + 9.0 / 2.0,
        released_origin[2] - (9.0 / 2.0 + 3.0),
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
            -142.91241221957347,
            -133.91241221957347,
            -145.91241221957347,
            -121.91241221957347,
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
            (12.924585870040456, 76.99421562429762, -138.41241221957347),
        ),
        (
            (0.0, 33.0, 0.0),
            (-45.98542028734179, 104.46440263744309, -138.41241221957347),
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
