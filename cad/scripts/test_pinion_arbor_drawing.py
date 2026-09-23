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
    assert set(spec.DRAWING_PRECISION_BY_NAME) == marked
    assert not hasattr(spec, "DRAWING_REFERENCE_PRECISION")
    assert {"HeadDia", "NeckDia", "ShaftDia"} == set(drawing.DONOR_KEEP)
    assert Path(drawing.__file__).name in PRECISION_MIGRATED_DRAWINGS


def test_integral_arbor_keeps_the_released_stations_around_a_longer_head() -> None:
    # Rule 12 (audit W6): the head grows 9.0 -> 10.5 about the released
    # crossrod station; the neck shoulder, shaft and back crown stay put.
    assert spec.HEAD_CENTER_Z == pytest.approx(-6.5)
    assert spec.HEAD_FRONT_Z == pytest.approx(-11.75)
    assert spec.HEAD_REAR_Z == pytest.approx(-1.25)
    assert spec.NECK_END_Z == pytest.approx(10.0)
    assert spec.SHAFT_LEN == pytest.approx(226.25)
    assert spec.HEAD_FRONT_Z - spec.HEAD_CAP_SAG == pytest.approx(-14.75)
    assert spec.SHAFT_LEN + spec.BACK_CAP_SAG == pytest.approx(227.45)
    assert spec.OVERALL_LEN == pytest.approx(242.2)
    assert spec.EXPOSED_SHAFT_LEN == pytest.approx(216.25)
    assert spec.BACK_RIM_FROM_HEAD_REAR == pytest.approx(227.5)


def test_crossrod_hole_is_centred_with_a_rule_12_web() -> None:
    # Printed centred on the head length: only HeadLen's .X band reaches the
    # web, never a separate station band.
    assert "CrossHoleReference" not in spec.DRAWING_DIMENSIONS
    assert "CENTRED ON HEAD LENGTH" in spec.CROSS_HOLE_CALLOUT
    assert spec.CROSS_HOLE_WEB_WORST == pytest.approx(1.7975)
    assert spec.CROSS_HOLE_WEB_WORST >= 1.5


def test_integral_head_owns_the_crossrod_interface() -> None:
    assert spec.HEAD_DIA == pytest.approx(15.0)
    assert spec.HEAD_LEN == pytest.approx(10.5)
    assert spec.NECK_DIA == pytest.approx(10.5)
    assert spec.NECK_LEN == pytest.approx(11.25)
    assert spec.CROSS_HOLE_DIA == pytest.approx(6.005)
    assert crossrod.ROD_DIA == pytest.approx(6.0175)
    assert crossrod.ROD_DIA > spec.CROSS_HOLE_DIA
    callout = drawing.DIMENSION_CALLOUTS["CrossHoleDia"]
    assert callout is spec.CROSS_HOLE_CALLOUT
    assert "MHA-058" in callout and "MIDPLANE" not in callout
    assert "ARBOR-PRESS" in callout
    assert "SHALL NOT TURN OR SLIDE BY HAND" in spec.DRAWING_NOTES


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
