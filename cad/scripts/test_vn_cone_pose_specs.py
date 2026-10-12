"""Pure supplier inputs for platform/shaft/global-pose readers, without CAD.

Scalar regressions preserve the harvested model, not an inferred stock grade.
Whether a spec is pure is read from what importing it loads, in a fresh
interpreter, so native recipes are never imported into this process.
"""

from __future__ import annotations

import functools
import importlib
import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent
PURE_SPECS = (
    "vn_cone_pivot_screw_spec",
    "vn_cone_lock_knob_spec",
    "vn_swing_stop_screw_spec",
    "_mcmaster_94025a164",
    "vn_foot_screw_spec",
    "vn_fillister_screw_spec",
    "vn_transgear_latch_pin_spec",
)
NATIVE_ROOTS = frozenset({
    "diagnostics",
    "_com",
    "_session",
    "_visibility",
    "_telemetry",
    "_watchdog",
    "_holes",
    "_assembly",
    "_drawing_common",
    "_stock_fastener",
    "solidworks_mcp",
    "win32com",
    "pythoncom",
    "comtypes",
    "cadquery",
    "ctypes",
})
_LOADED_ROOTS = (
    "import importlib, json, sys; importlib.import_module(sys.argv[1]); "
    "print(json.dumps(sorted({name.split('.', 1)[0] for name in sys.modules})))"
)


@functools.cache
def _loaded_roots(module_name: str) -> frozenset[str]:
    """Top-level modules a fresh interpreter holds after importing ``module_name``."""
    result = subprocess.run(
        [sys.executable, "-c", _LOADED_ROOTS, module_name],
        cwd=SCRIPTS, capture_output=True, text=True, check=True,
    )
    return frozenset(json.loads(result.stdout))


def _native_roots(module_name: str) -> set[str]:
    return {
        root for root in _loaded_roots(module_name)
        if root in NATIVE_ROOTS or root.startswith(("build_", "draw_", "diag_"))
    }


def _pure_spec(module_name: str):
    return importlib.import_module(module_name)


@pytest.mark.parametrize("module_name", PURE_SPECS)
def test_pose_vendor_specs_load_no_native_module(module_name: str) -> None:
    assert not _native_roots(module_name)


@pytest.mark.parametrize(
    "module_name",
    (
        "diagnostics.diag_build_94025A164",
        "diagnostics.diag_build_90114A511",
        "diagnostics.diag_mcmaster_fillister",
        "diagnostics.diag_mcmaster_dowel",
    ),
)
def test_native_load_probe_has_a_real_native_positive_control(module_name: str) -> None:
    assert "diagnostics" in _native_roots(module_name)


@pytest.mark.parametrize(
    ("spec_name", "recipe_name", "scalars"),
    [
        (
            "_mcmaster_91829a560",
            "diagnostics.diag_build_91829A560",
            {
                "HEAD_DIA": 9.525,
                "HEAD_T": 4.7625,
                "SHOULDER_DIA": 6.35,
                "SHOULDER_LEN": 6.35,
                "THREAD_MAJOR": 4.826,
                "THREAD_LEN": 9.525,
                "UNDERHEAD_LEN": 15.875,
                "SLOT_W": 1.524,
                "SLOT_D": 1.905,
                "HEAD_CHAMFER": 0.309563,
                "TIP_CHAMFER": 0.43434,
                "UC_LAND_DIA": 3.3528,
                "UC_W": 1.6002,
                "PITCH": 1.058333,
                "REVS": 9.0,
            },
        ),
        (
            "_mcmaster_93585a190",
            "diagnostics.diag_build_93585A190",
            {
                "MAJOR_R": 3.175,
                "PITCH": 1.27,
                "LENGTH": 19.05,
                "HEAD_R": 7.9375,
                "HEAD_H": 12.7,
                "RIM_CHAMFER": 0.79375,
                "KNURL_COUNT": 131,
                "KNURL_CREST_W": 0.127,
                "KNURL_FLANK_DEG": 20.0,
                "RUNOUT_DEPTH": 2.54,
                "RUNOUT_DRAFT_DEG": 45.0,
                "TIP_CHAMFER": 0.9525,
            },
        ),
        (
            "_mcmaster_94025a164",
            "diagnostics.diag_build_94025A164",
            {
                "SS_MAJOR_R": 2.413,
                "SS_LEN": 9.525,
                "SS_HALF": 4.7625,
                "SS_PITCH": 0.79375,
                "SS_REVS": 14.0,
                "SS_CHAM_R": 2.155222,
                "SS_CHAM_H": 0.180498,
                "SS_TIP_R": 1.2065,
                "SS_CONE_Y": 3.556,
                "SS_SLOT_W": 0.804333,
                "SS_SLOT_D": 0.79375,
                "SS_CUT_TOP_R": 2.455963,
                "SS_CUT_TOP_W": 0.744141,
                "SS_CUT_ROOT_R": 1.897444,
                "SS_CUT_ROOT_W": 0.099219,
                "SS_CUT_CY": 5.903515625,
            },
        ),
    ],
)
def test_native_recipes_load_the_vendor_scalars(
    spec_name: str, recipe_name: str, scalars: dict[str, float]
) -> None:
    spec = _pure_spec(spec_name)
    for name, expected in scalars.items():
        assert getattr(spec, name) == pytest.approx(expected, rel=0.0, abs=1e-12)
    shared = _perturbed_recipe_values(spec_name, recipe_name)
    assert set(scalars) & set(shared), "the recipe reads none of the harvested scalars"
    for name, (used, authority) in shared.items():
        assert used == authority, f"{recipe_name} holds its own {name}"


# Every public number of the supplier spec is moved before the native recipe
# is imported, in a fresh interpreter; each one the recipe holds must follow.
_PERTURBED_VALUES = """
import importlib, json, numbers, sys
spec = importlib.import_module(sys.argv[1])
moved = {}
for name, value in list(vars(spec).items()):
    if name.isupper() and isinstance(value, numbers.Real) and not isinstance(value, bool):
        moved[name] = value + (1 if isinstance(value, int) else 0.5)
        setattr(spec, name, moved[name])
recipe = importlib.import_module(sys.argv[2])
print(json.dumps({n: [getattr(recipe, n), v] for n, v in moved.items() if hasattr(recipe, n)}))
"""


def _perturbed_recipe_values(spec_name: str, recipe_name: str) -> dict[str, list[float]]:
    result = subprocess.run(
        [sys.executable, "-c", _PERTURBED_VALUES, spec_name, recipe_name],
        cwd=SCRIPTS, capture_output=True, text=True, check=True,
    )
    return json.loads(result.stdout.splitlines()[-1])


_RECORDED_CUP = """
import asyncio, contextlib, json, sys
from unittest.mock import AsyncMock, MagicMock
import _mcmaster_94025a164 as spec
spec.SS_TIP_R += 0.5
import _sketch
import diagnostics.diag_build_94025A164 as recipe
chains = []
async def add_line_chain(_adapter, points, close=True):
    chains.append(points)
_sketch.add_line_chain = add_line_chain
for name in ("check", "name_last_feature", "insert_helix", "offset_plane", "thread_sweep_cut_modern"):
    setattr(recipe, name, MagicMock())
recipe.no_sketch_inference = lambda _adapter: contextlib.nullcontext()
recipe.volume_check = AsyncMock(side_effect=lambda _a, _l, expected, _t: expected)
recipe.bodies = lambda _adapter: [object()]
asyncio.run(recipe.build_94025A164(AsyncMock(currentSketchManager=MagicMock())))
print(json.dumps({"tip": spec.SS_TIP_R, "half": spec.SS_HALF, "profile": chains[0]}))
"""


def test_the_native_cup_recipe_draws_the_spec_tip_radius() -> None:
    """The real 94025A164 recipe, with recording doubles and a moved SS_TIP_R:
    its revolve profile's cup rim lands on the moved value."""
    result = subprocess.run(
        [sys.executable, "-c", _RECORDED_CUP], cwd=SCRIPTS,
        capture_output=True, text=True, check=True,
    )
    recorded = json.loads(result.stdout.splitlines()[-1])
    assert [recorded["tip"], -recorded["half"]] in recorded["profile"]


def test_same_sku_fillister_row_has_one_pure_authority() -> None:
    stop = _pure_spec("vn_swing_stop_screw_spec")
    for name, expected in {
        "SHANK_DIA": 2.8448,
        "SHANK_LEN": 9.525,
        "HEAD_H": 2.7178,
        "HEAD_DIA": 4.6482,
        "THREAD_PITCH": 0.635,
        "EMBED_LEN": 9.525,
        "PROUD_LEN": 0.0,
        "CONTACT_DIA": 4.6482,
    }.items():
        assert getattr(stop, name) == pytest.approx(expected, rel=0.0, abs=1e-12)
    vendor = _pure_spec("_mcmaster_90280a108")
    assert len(vendor.FILLISTER_SIZE) == 5
    # Every same-SKU reader holds the vendor row itself, not a copy.
    for consumer in (
        "vn_swing_stop_screw_spec",
        "vn_foot_screw_spec",
        "vn_latch_hook_bracket_screw_spec",
    ):
        assert _pure_spec(consumer).FILLISTER_SIZE is vendor.FILLISTER_SIZE


def test_pivot_bands_are_actual_supplier_limits_with_explicit_order() -> None:
    pivot = _pure_spec("vn_cone_pivot_screw_spec")
    fit = _pure_spec("_fit_deviations")
    assert "https://www.mcmaster.com/91829A560/" in pivot.SOURCE
    assert "2026-10-08" in pivot.SOURCE
    assert pivot.SHOULDER_DIA_BAND == (0.0, -0.0254)
    assert pivot.SHOULDER_LEN_BAND == (0.0508, 0.0)
    for nominal, band, expected_min, expected_max in (
        (pivot.SHOULDER_DIA, pivot.SHOULDER_DIA_BAND, 6.3246, 6.35),
        (pivot.SHOULDER_LEN, pivot.SHOULDER_LEN_BAND, 6.35, 6.4008),
    ):
        lower, upper = fit.deviations(band)
        assert nominal + lower == pytest.approx(expected_min, abs=1e-12)
        assert nominal + upper == pytest.approx(expected_max, abs=1e-12)
        with pytest.raises(ValueError, match="fit band is inverted"):
            fit.deviations(tuple(reversed(band)))


def test_public_nominals_and_unknown_supplier_grades_are_not_conflated() -> None:
    pivot = _pure_spec("vn_cone_pivot_screw_spec")
    lock = _pure_spec("vn_cone_lock_knob_spec")
    lock_vendor = _pure_spec("_mcmaster_93585a190")
    stop = _pure_spec("vn_swing_stop_screw_spec")
    cup = _pure_spec("_mcmaster_94025a164")
    assert pivot.HEAD_H == pivot.HEAD_T
    assert pivot.THREAD_TAIL_LEN == pivot.THREAD_LEN
    assert pivot.THREAD_SOLID_DIA == pivot.THREAD_MAJOR
    assert pivot.THREAD == "#10-24"
    assert lock.HEAD_DIA == 2.0 * lock_vendor.HEAD_R == 15.875
    assert lock.STUD_DIA == 2.0 * lock_vendor.MAJOR_R == 6.35
    assert lock.STUD_LEN == lock_vendor.LENGTH == 19.05
    assert lock.THREAD_PITCH == lock_vendor.PITCH == 1.27
    assert lock.THREAD == "1/4-20"
    assert stop.THREAD == "#4-40"
    assert cup.THREAD == "#10-32"
    assert cup.BODY_LEN == cup.SS_LEN == 9.525
    assert cup.BODY_DIA == 2.0 * cup.SS_MAJOR_R == 4.826
    assert cup.CUP_DIA == 2.0 * cup.SS_TIP_R == 2.413
    assert cup.CUP_DEPTH == cup.SS_CUP_DEPTH == cup.SS_HALF - cup.SS_CONE_Y
    assert cup.CUP_DEPTH == pytest.approx(1.2065, abs=1e-12)
    assert cup.CUP_DEPTH == pytest.approx(cup.SS_TIP_R, abs=1e-12)
    assert cup.SS_CUT_CY == cup.SS_HALF + cup.SS_PITCH + 7.0 * cup.SS_PITCH / 16.0
    for spec, names in (
        (pivot, ("HEAD_DIA_BAND", "HEAD_H_BAND")),
        (lock, ("HEAD_DIA_BAND", "HEAD_H_BAND", "STUD_DIA_BAND", "STUD_LEN_BAND")),
        (stop, ("SHANK_DIA_BAND",)),
        (cup, ("BODY_DIA_BAND", "BODY_LEN_BAND", "CUP_DIA_BAND", "CUP_DEPTH_BAND")),
    ):
        for name in names:
            assert getattr(spec, name) is None, f"unprovided supplier grade: {name}"


@pytest.mark.parametrize(
    "consumer", ("build_dt_drive_train_assembly", "test_drive_train_tip_adjuster_seat"),
)
def test_adjuster_data_consumers_do_not_load_the_native_wrapper(consumer: str) -> None:
    loaded = _loaded_roots(consumer)
    assert "_mcmaster_94025a164" in loaded
    assert "build_vn_cone_tip_adjuster" not in loaded


def test_adjuster_thread_limits_are_qualified_separately_from_its_cup() -> None:
    cup = _pure_spec("_mcmaster_94025a164")
    assert cup.THREAD == "#10-32"
    assert cup.THREAD_CLASS == "2A"
    assert "https://www.mcmaster.com/94025A164/" in cup.THREAD_FIT_SOURCE
    assert "steelmasters.co.nz" in cup.THREAD_LIMITS_SOURCE
    assert cup.THREAD_MAJOR_MAX_MM == 0.1891 * 25.4
    assert cup.EXTERNAL_PITCH_DIA_MIN_MM == 0.1658 * 25.4
    # Preserve the ideal supplier CAD instead of redimensioning it to a limit.
    assert cup.BODY_DIA == 4.826
    assert cup.THREAD_MAJOR_MAX_MM < cup.BODY_DIA
    assert cup.CUP_DIA_BAND is None
    assert cup.CUP_DEPTH_BAND is None


def test_stop_thread_limits_are_separate_from_its_nominal_profile() -> None:
    stop = _pure_spec("vn_swing_stop_screw_spec")
    assert stop.THREAD == "#4-40"
    assert stop.THREAD_CLASS == "2A"
    assert "https://www.mcmaster.com/90280A108/" in stop.THREAD_FIT_SOURCE
    assert "steelmasters.co.nz" in stop.THREAD_LIMITS_SOURCE
    assert stop.THREAD_MAJOR_MAX_MM == 0.1112 * 25.4
    assert stop.EXTERNAL_PITCH_DIA_MIN_MM == 0.0925 * 25.4
    # Keep the harvested ideal profile; thread limits do not grade its head.
    assert stop.SHANK_DIA == 2.8448
    assert stop.THREAD_MAJOR_MAX_MM < stop.SHANK_DIA


def test_stop_standard_envelopes_are_sourced_without_changing_native_nominals() -> None:
    stop = _pure_spec("vn_swing_stop_screw_spec")
    fit = _pure_spec("_fit_deviations")
    assert stop.STOCK_STANDARD == "ASME B18.6.3"
    assert "Machinery's%20Handbook" in stop.HEAD_LIMITS_SOURCE
    assert "optimas.com" in stop.LENGTH_LIMITS_SOURCE
    for name, inches in {
        "HEAD_DIA_MIN_MM": 0.166,
        "HEAD_DIA_MAX_MM": 0.183,
        "HEAD_SIDE_MIN_MM": 0.069,
        "HEAD_SIDE_MAX_MM": 0.079,
        "HEAD_TOTAL_MIN_MM": 0.088,
        "HEAD_TOTAL_MAX_MM": 0.107,
        "SLOT_DEPTH_MAX_MM": 0.048,
        "LENGTH_SHORT_ALLOWANCE_MM": 0.02,
    }.items():
        assert getattr(stop, name) == pytest.approx(inches * 25.4, abs=1e-12)
    assert stop.LENGTH_MIN_MM == pytest.approx((0.375 - 0.02) * 25.4, abs=1e-12)
    assert stop.LENGTH_MAX_MM == stop.SHANK_LEN == 9.525
    assert stop.HEAD_DIA == 4.6482
    assert stop.HEAD_H == 2.7178
    assert stop.HEAD_BEARING_RADIUS_MIN_MM == pytest.approx(1.89738, abs=1e-12)
    assert stop.UNSLOTTED_HEAD_HEIGHT_MIN_MM == pytest.approx(1.016, abs=1e-12)
    assert stop.FULL_THREAD_START_MAX_MM == 2.0 * stop.THREAD_PITCH
    # Qualify the handbook's actual nominal-length range for its two-pitch rule.
    assert stop.SHANK_LEN > 3.0 * stop.SHANK_DIA
    assert stop.SHANK_LEN <= 1.125 * 25.4
    for nominal, band, minimum, maximum in (
        (stop.HEAD_DIA, stop.HEAD_DIA_BAND, stop.HEAD_DIA_MIN_MM, stop.HEAD_DIA_MAX_MM),
        (stop.HEAD_H, stop.HEAD_H_BAND, stop.HEAD_TOTAL_MIN_MM, stop.HEAD_TOTAL_MAX_MM),
        (stop.SHANK_LEN, stop.SHANK_LEN_BAND, stop.LENGTH_MIN_MM, stop.LENGTH_MAX_MM),
    ):
        lower, upper = fit.deviations(band)
        assert nominal + lower == pytest.approx(minimum, abs=1e-12)
        assert nominal + upper == pytest.approx(maximum, abs=1e-12)
        with pytest.raises(ValueError, match="fit band is inverted"):
            fit.deviations(tuple(reversed(band)))


def test_stop_inspection_floor_is_shared_by_the_nominal_seat_check(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stop = _pure_spec("vn_swing_stop_screw_spec")
    holes = _pure_spec("_hole_spec")
    assert stop.MIN_USEFUL_ENGAGEMENT_MM == 4.27
    assert "Functional installation inspection" in stop.MIN_USEFUL_ENGAGEMENT_SOURCE
    assert "full-form" in stop.MIN_USEFUL_ENGAGEMENT_SOURCE
    seat = holes.HoleSpec(
        "tapped",
        stop.THREAD,
        end="blind",
        depth_mm=14.0,
        overrides_mm={"ThreadDepth": 10.0},
    )
    stop.require_seat_fit(seat, 5.0)
    # Between the unrounded old 1D floor and the real inspected minimum:
    # the nominal guard must use the same rounded-up acceptance.
    monkeypatch.setattr(
        stop,
        "EMBED_LEN",
        stop.TIP_CHAMFER + (stop.SHANK_DIA + stop.MIN_USEFUL_ENGAGEMENT_MM) / 2.0,
    )
    with pytest.raises(AssertionError, match="minimum useful thread engagement"):
        stop.require_seat_fit(seat, 5.0)


def test_pivot_thread_limits_and_installed_inspection_are_separately_qualified() -> None:
    pivot = _pure_spec("vn_cone_pivot_screw_spec")
    assert pivot.THREAD == "#10-24"
    assert pivot.THREAD_CLASS == "2A"
    assert pivot.THREAD_FIT_SOURCE == pivot.SOURCE
    assert "steelmasters.co.nz" in pivot.THREAD_LIMITS_SOURCE
    assert pivot.THREAD_MAJOR_MAX_MM == 0.1890 * 25.4
    assert pivot.EXTERNAL_PITCH_DIA_MIN_MM == 0.1586 * 25.4
    assert pivot.MIN_USEFUL_ENGAGEMENT_MM == 4.83
    assert "Functional installation inspection" in pivot.MIN_USEFUL_ENGAGEMENT_SOURCE
    assert "shoulder fully seated" in pivot.MIN_USEFUL_ENGAGEMENT_SOURCE
    # The thread limits and inspection floor never redimension the vendor CAD.
    assert pivot.THREAD_SOLID_DIA == pivot.THREAD_MAJOR == 4.826
    assert pivot.THREAD_MAJOR_MAX_MM < pivot.THREAD_SOLID_DIA
    assert pivot.THREAD_TAIL_LEN == 9.525
    assert pivot.SHOULDER_DIA_BAND == (0.0, -0.0254)
    assert pivot.SHOULDER_LEN_BAND == (0.0508, 0.0)
    assert pivot.HEAD_DIA_BAND is None
    assert pivot.HEAD_H_BAND is None
