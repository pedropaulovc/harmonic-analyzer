"""Behavioral release contracts for the integral MHA-102 pinion arbor."""

from __future__ import annotations

from pathlib import Path

import pytest

import _fit_limits
import build_pinion_arbor as part
import draw_pinion_arbor as drawing
import pinion_arbor_spec as spec
import pinion_handle_spec as crossrod
from _drawing_contract import PRECISION_MIGRATED_DRAWINGS, model_toleranced_dimensions
from _drawing_registry import DRAWINGS_BY_NAME


def test_required_drawing_paths_and_registry() -> None:
    assert drawing.SLDDRW.as_posix().endswith("/slddrw/pinion-arbor.SLDDRW")
    assert drawing.PDF.as_posix().endswith("/pdf/pinion-arbor.pdf")
    assert drawing.PNG.as_posix().endswith("/png/pinion-arbor_drawing.png")
    assert DRAWINGS_BY_NAME["pinion_arbor"].script == Path(drawing.__file__).resolve()


def test_spec_is_the_single_source_of_every_printed_dimension() -> None:
    assert part.DRAWING_DIMENSIONS is spec.DRAWING_DIMENSIONS
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    kept = (
        set(drawing.DONOR_KEEP)
        | set(drawing.PRINCIPAL_KEEP)
        | set(drawing.DETAIL_KEEP)
    )
    assert kept == marked
    assert set(spec.DRAWING_PRECISION_BY_NAME) == (
        marked | set(drawing.DIAMETER_POSITIONS)
    )
    assert {
        name: spec.DRAWING_PRECISION_BY_NAME[name]
        for name in ("HeadDia", "NeckDia")
    } == {"HeadDia": 1, "NeckDia": 1}
    # Every printed size is a native model import: nothing is sheet-derived.
    assert not hasattr(spec, "DRAWING_REFERENCE_PRECISION")
    assert set(drawing.DONOR_KEEP) == set(drawing.DIAMETER_POSITIONS)
    assert Path(drawing.__file__).name in PRECISION_MIGRATED_DRAWINGS


def test_integral_arbor_preserves_the_released_absolute_envelope() -> None:
    assert spec.HEAD_FRONT_Z == pytest.approx(-11.0)
    assert spec.HEAD_REAR_Z == pytest.approx(-2.0)
    assert spec.HEAD_CENTER_Z == pytest.approx(-6.5)
    assert spec.NECK_END_Z == pytest.approx(10.0)
    assert spec.SHAFT_LEN == pytest.approx(226.25)
    assert spec.HEAD_FRONT_Z - spec.HEAD_CAP_SAG == pytest.approx(-14.0)
    assert spec.SHAFT_LEN + spec.BACK_CAP_SAG == pytest.approx(227.45)
    assert spec.OVERALL_LEN == pytest.approx(241.45)
    assert spec.EXPOSED_SHAFT_LEN == pytest.approx(216.25)
    assert spec.BACK_RIM_FROM_HEAD_REAR == pytest.approx(228.25)
    assert spec.CROSS_HOLE_FROM_HEAD_REAR == pytest.approx(4.5)


def test_integral_head_owns_the_crossrod_interface() -> None:
    assert spec.HEAD_DIA == pytest.approx(15.0)
    assert spec.HEAD_LEN == pytest.approx(9.0)
    assert spec.NECK_DIA == pytest.approx(10.5)
    assert spec.NECK_LEN == pytest.approx(12.0)
    assert spec.CROSS_HOLE_DIA == pytest.approx(6.005)
    assert crossrod.ROD_DIA == pytest.approx(6.0175)
    assert crossrod.ROD_DIA > spec.CROSS_HOLE_DIA
    callout = drawing.DIMENSION_CALLOUTS["CrossHoleDia"]
    assert callout is spec.CROSS_HOLE_CALLOUT
    assert "MHA-058" in callout and "MIDPLANE" not in callout
    assert "ARBOR-PRESS" in callout
    assert "SHALL NOT TURN OR SLIDE BY HAND" in spec.DRAWING_NOTES
    assert spec.DRAWING_DIMENSIONS["CrossHoleReference"] == {
        "CrossHoleFromHeadRear"
    }


def test_running_journal_keeps_only_its_functional_size_and_finish() -> None:
    assert spec.SHAFT_DIA_BAND is _fit_limits.SHAFT_H
    assert model_toleranced_dimensions(part) == {
        ("ShaftProfile", "ShaftDia"): "*deviations(SHAFT_DIA_BAND)"
    }
    (finish,) = spec.SURFACE_FINISHES
    assert finish.key == "bearing"
    assert finish.roughness_um == 1.6
    assert finish.face.diameter_mm == spec.SHAFT_DIA
    assert "MHA-056" in spec.DRAWING_NOTES
    assert "BOND INTO MHA-002 WITH LOCTITE 638." in spec.DRAWING_NOTES
    assert "PRESSES INTO" not in spec.DRAWING_NOTES
    assert not hasattr(spec, "PART_DATUMS")
    assert not hasattr(spec, "GEOMETRIC_CONTROLS")


def test_retired_socket_and_retention_pin_are_not_exported() -> None:
    retired = {
        "RETENTION_HOLE_DIA",
        "RETENTION_PIN_STATION",
        "TUBE_ID",
        "TUBE_OD",
        "TUBE_LEN",
        "WALL_T",
    }
    assert retired.isdisjoint(vars(spec))
    assert "RETENTION PIN" not in spec.CROSS_HOLE_CALLOUT


def test_every_post_import_name_is_carried_by_a_kept_or_moved_dimension() -> None:
    """Offline audit of the names the sheet looks up after the model import."""
    carried = (
        set(drawing.DONOR_KEEP)
        | set(drawing.PRINCIPAL_KEEP)
        | set(drawing.DETAIL_KEEP)
    )
    assert set(drawing.DIMENSION_CALLOUTS) <= carried
    assert set(spec.DRAWING_PRECISION_BY_NAME) == carried
    assert set(drawing.DIAMETER_POSITIONS) <= carried
    assert {"CrossHoleDia", "HeadCapSagDim", "BackCapSagDim", "OverallLen"} <= carried
