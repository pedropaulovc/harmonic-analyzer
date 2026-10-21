"""Offline fitted-retainer contracts; no recipe execution or COM connection."""

from __future__ import annotations

import ast
import copy
import math
from pathlib import Path

import pytest

import _config
import ch_rocker_arm_tl_oblique_pivot_retainer_spec as spec
import ch_rocker_arm_tl_oblique_retention_hardware_spec as hardware
import ch_rocker_arm_tl_oblique_retention_spec as retention
import draw_ch_rocker_arm_tl_oblique_pivot_retainer as drawing
import export_features
from _machinist_review_mode import MachinistReviewMode
from test_pd_transgear_adapter_contract import _adapter_calls, _adapter_methods, _missing, _signature

STEM = "ch_rocker_arm_tl_oblique_pivot_retainer"
DASHED = STEM.replace("_", "-")
RECIPE = Path(__file__).with_name(f"build_{STEM}.py")


def test_installed_thickness_is_calculated_not_the_supply_minimum() -> None:
    assert (spec.OUTER_DIA, spec.BORE_DIA, spec.SUPPLY_MIN_THICKNESS) == (24.0, 10.2, 7.0)
    assert spec.THICKNESS == retention.TOP_WASHER_NOMINAL_THICKNESS
    assert spec.CLEVIS_DIA == hardware.CLEVIS_DIA
    assert spec.CLEVIS_DIA != 3.0 / 16.0 * 25.4
    expected = spec.CROSS_HOLE_FROM_SEAT + spec.CROSS_HOLE_DIA / 2.0 - hardware.CLEVIS_DIA - spec.CARRIER_THICKNESS - sum(retention.TOP_RUNNING_GAP) / 2.0
    assert spec.THICKNESS == pytest.approx(expected)
    assert spec.THICKNESS == pytest.approx(4.1641)
    assert spec.THICKNESS < spec.SUPPLY_MIN_THICKNESS < spec.STOCK_THICKNESS
    assert spec.VOLUME_MM3 == pytest.approx(math.pi / 4.0 * (24.0**2 - 10.2**2) * expected)
    supply_volume = math.pi / 4.0 * (24.0**2 - 10.2**2) * spec.SUPPLY_MIN_THICKNESS
    assert spec.VOLUME_MM3 < supply_volume


def test_loaded_gap_uses_the_upper_tangent_and_whole_clevis_diameter() -> None:
    gap = spec.loaded_running_gap(spec.THICKNESS)
    assert gap == pytest.approx(0.175)
    assert spec.require_loaded_running_gap(spec.THICKNESS) == pytest.approx(gap)
    # A centre-line or lower-tangent assumption omits actual upward travel.
    centre_assumption = spec.CROSS_HOLE_FROM_SEAT - spec.CLEVIS_DIA / 2.0 - spec.CARRIER_THICKNESS - spec.THICKNESS
    missing_travel = (spec.CROSS_HOLE_DIA - spec.CLEVIS_DIA) / 2.0
    assert gap - centre_assumption == pytest.approx(missing_travel)
    assert missing_travel > 0.15


@pytest.mark.parametrize("gap", [0.10, 0.175, 0.25])
def test_actual_fitted_gap_limits_are_accepted(gap: float) -> None:
    stack = spec.CROSS_HOLE_FROM_SEAT + spec.CROSS_HOLE_DIA / 2.0 - spec.CLEVIS_DIA - spec.CARRIER_THICKNESS
    assert spec.require_loaded_running_gap(stack - gap) == pytest.approx(gap)


@pytest.mark.parametrize("thickness,actual", [
    (7.0, {}), (3.0, {}), (5.0, {}),
    (spec.THICKNESS, {"cross_hole_from_seat": spec.CROSS_HOLE_FROM_SEAT + 0.8}),
    (spec.THICKNESS, {"cross_hole_dia": spec.CROSS_HOLE_DIA + 0.4}),
    (spec.THICKNESS, {"carrier_thickness": spec.CARRIER_THICKNESS - 0.8}),
    (spec.THICKNESS, {"clevis_dia": spec.CLEVIS_DIA - 0.3}),
])
def test_fixed_stock_and_changed_actual_stack_are_not_false_fit_acceptances(thickness, actual) -> None:
    with pytest.raises(ValueError, match="upper-edge-loaded"):
        spec.require_loaded_running_gap(thickness, **actual)


def test_every_printed_dimension_has_a_model_owner_and_authored_places() -> None:
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    assert marked == set(spec.DRAWING_PRECISION_BY_NAME)
    assert marked == set(drawing.FACE_KEEP) | set(drawing.PROFILE_KEEP)
    assert not set(drawing.FACE_KEEP) & set(drawing.PROFILE_KEEP)
    assert spec.DRAWING_DIMENSIONS[spec.SUPPLY_REFERENCE] == {"SupplyThickness"}
    assert spec.DRAWING_DIMENSIONS["Washer"] == {"FinishedThickness"}
    assert spec.DRAWING_PRECISION_BY_NAME["FinishedThickness"] == spec.THICKNESS_PLACES == 2
    assert "REF" in spec.DIMENSION_CALLOUTS["FinishedThickness"]
    assert "UPPER CROSS-HOLE EDGE" in spec.DIMENSION_CALLOUTS["FinishedThickness"]
    assert "SUPPLY" in spec.DIMENSION_CALLOUTS["SupplyThickness"]
    assert spec.DRAWING_NOTES == ""
    assert drawing.MACHINIST_REVIEW is MachinistReviewMode.ENFORCE


def test_setup_note_does_not_hide_pin_projection_or_claim_tooling_clearance() -> None:
    assert spec.PIN_PROJECTION_ABOVE_PLATE == 12.5
    assert spec.PIN_PROJECTION_ABOVE_WORK == retention.PIN_PROJECTION_ABOVE_WORK_NOMINAL
    assert "12.5 ABOVE CARRIER" in spec.SETUP_NOTE
    assert f"{spec.PIN_PROJECTION_ABOVE_WORK:.1f} ABOVE WORK TOP" in spec.SETUP_NOTE
    assert "BOTH RETAINERS LOCKED" in spec.SETUP_NOTE
    assert "FRESH COTTERS" in spec.SETUP_NOTE
    assert "ACCEPT ACTUAL INSTALLED TOOLHOLDER / SPINDLE CLEARANCE" in spec.SETUP_NOTE
    assert spec.AXIS_NAME == "RetainerAxis" and spec.BOTTOM_PLANE == "Front Plane"
    assert spec.TOP_PLANE == "RetainerTop"
    assert len(spec.SURFACE_FINISHES) == 1
    assert spec.SURFACE_FINISHES[0].key == "carrier_running_face"


def test_manifest_preserves_actual_fitted_acceptance_not_a_fake_thickness_band() -> None:
    features = export_features.requirement_manifest(STEM)["features"]
    assert features["outside"]["dia_nominal"] == 24.0
    assert features["journal_clearance"]["dia"] == pytest.approx([10.2, 10.3])
    assert features["fitted_top"]["note"] == spec.DIMENSION_CALLOUTS["FinishedThickness"]
    assert "thickness" not in features["fitted_top"]
    assert features["carrier_running_face"]["note"] == spec.SETUP_NOTE


def test_native_recipe_models_the_finished_annulus_and_distinct_supply_allowance() -> None:
    source = RECIPE.read_text(encoding="utf-8")
    tree = ast.parse(source, filename=str(RECIPE))
    calls = _adapter_calls(tree)
    assert {"create_part", "create_sketch", "exit_sketch", "create_extrusion", "create_plane"} <= {call.func.attr for call in calls}
    assert not _missing(tree)
    for call in calls:
        _, method = _adapter_methods()[call.func.attr]
        _signature(method).bind(call.func.value, *call.args, **{kw.arg: kw.value for kw in call.keywords})
    mutant = copy.deepcopy(tree)
    extrusion = next(call for call in _adapter_calls(mutant) if call.func.attr == "create_extrusion")
    extrusion.func.attr = "create_extrude"
    assert _missing(mutant) == {"create_extrude"}


def test_configuration_identity_and_fitting_process() -> None:
    row = _config.parts(DASHED)
    assert row["number"] == "MHA-CH-06-TL-31" and row["quantity"] == 2
    assert "3/8" in row["material_specification"]
    assert len(row["finish"]) <= 40 and "\n" not in row["finish"]
    assert "UPPER" in row["process"] and "not a 7 mm finished" in row["process"]
