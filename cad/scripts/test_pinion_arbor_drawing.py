"""Behavioral release contracts for the simplicity-policy pinion arbor."""

from __future__ import annotations

from pathlib import Path

import pytest

import _fit_limits
import build_pinion_arbor as part
import draw_pinion_arbor as drawing
import pinion_arbor_spec as spec
import pinion_handle_pin_spec as pin_spec
import pinion_handle_spec as handle_spec
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
    kept = set(drawing.DONOR_KEEP) | set(drawing.PRINCIPAL_KEEP)
    assert kept == marked
    assert set(spec.DRAWING_PRECISION_BY_NAME) == marked
    assert Path(drawing.__file__).name in PRECISION_MIGRATED_DRAWINGS


def test_running_journal_keeps_only_its_functional_size_and_finish() -> None:
    assert spec.SHAFT_DIA_BAND is _fit_limits.SHAFT_H
    assert model_toleranced_dimensions(part) == {
        ("ShaftProfile", "ShaftDia"): "*deviations(SHAFT_DIA_BAND)"
    }
    (finish,) = spec.SURFACE_FINISHES
    assert finish.key == "bearing"
    assert finish.roughness_um == 1.6
    assert finish.face.diameter_mm == spec.SHAFT_DIA
    assert not hasattr(spec, "PART_DATUMS")
    assert not hasattr(spec, "GEOMETRIC_CONTROLS")


def test_retention_hole_matches_the_handle_and_dedicated_pin() -> None:
    assert spec.RETENTION_HOLE_DIA == pytest.approx(handle_spec.RETENTION_PIN_DIA)
    assert spec.RETENTION_HOLE_DIA == pytest.approx(pin_spec.PIN_DIA)
    assert spec.RETENTION_PIN_STATION == pytest.approx(
        handle_spec.RETENTION_PIN_STATION_FROM_FLOOR
    )
    assert pin_spec.PIN_LEN == pytest.approx(handle_spec.TUBE_OD)
    callout = drawing.DIMENSION_CALLOUTS["RetentionHoleDia"]
    assert callout is spec.RETENTION_HOLE_CALLOUT
    assert "PINION HANDLE MHA-058" in callout
    assert "RETENTION PIN MHA-136" in callout
    assert "LIGHT DRIVE FIT" in callout
    assert "NOT HAND-REMOVABLE" in callout


def test_crown_is_model_dimensioned_without_geometric_frames() -> None:
    radius, sag = spec.SHAFT_DIA / 2.0, spec.CAP_SAG
    assert spec.CAP_R == pytest.approx((radius * radius + sag * sag) / (2.0 * sag))
    assert drawing.DIMENSION_CALLOUTS["CapSagDim"] == "SR7.3 CROWN"
    assert "CapSagDim" in drawing.PRINCIPAL_KEEP
    assert drawing.DIMENSION_CALLOUTS["Depth"] == "TO CROWN ROOT"


def test_every_printed_dimension_has_authored_precision() -> None:
    assert spec.DRAWING_PRECISION_BY_NAME == {
        "ShaftDia": 2,
        "Depth": 1,
        "CapSagDim": 1,
        "RetentionHoleDia": 1,
        "RetentionPinStation": 1,
    }


def test_registry_retains_make_critical_material_and_finish() -> None:
    import _config

    config = _config.parts("pinion-arbor")
    assert "1018" in str(config["material_specification"])
    assert config["finish"] == "oiled"
    assert int(config["quantity"]) == 1
