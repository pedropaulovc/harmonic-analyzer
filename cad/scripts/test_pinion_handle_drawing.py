"""Behavioral release contracts for the separate MHA-058 grip crossrod."""

from __future__ import annotations

from pathlib import Path

import pytest

import _config
import build_pinion_handle as part
import draw_pinion_handle as drawing
import pinion_handle_geometry as geometry
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
    assert "MHA-136" not in spec.DRAWING_NOTES


def test_part_metadata_names_the_grip_crossrod_work() -> None:
    config = _config.parts("pinion-handle")
    assert config["title"] == "Pinion Grip Cross Rod"
    assert "cold-finished steel rod" in str(config["material_specification"])
    assert "crossrod" in str(config["process"])
    assert int(config["quantity"]) == 1
