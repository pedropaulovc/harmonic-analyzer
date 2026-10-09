"""Pure supplier inputs for platform/shaft/global-pose readers, without CAD.

Scalar regressions preserve the harvested model, not an inferred stock grade.
Native recipes are inspected as source only; they are never imported here.
"""

from __future__ import annotations

import ast
import importlib
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parent
PURE_SPECS = (
    "vn_cone_pivot_screw_spec",
    "vn_cone_lock_knob_spec",
    "vn_swing_stop_screw_spec",
    "vn_cone_tip_adjuster_spec",
    "vn_foot_screw_spec",
)


def _source_tree(module_name: str) -> ast.Module:
    path = SCRIPTS / f"{module_name.replace('.', '/')}.py"
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def _imports(tree: ast.Module) -> set[str]:
    modules = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            modules.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            modules.add(node.module)
    return modules


def _pure_local_closure(module_name: str) -> set[str]:
    """Inspect every local import edge before allowing a runtime fact read."""
    pending = {module_name}
    visited = set()
    forbidden_roots = {
        "diagnostics",
        "_common",
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
    }
    while pending:
        current = pending.pop()
        if current in visited:
            continue
        visited.add(current)
        for imported in _imports(_source_tree(current)):
            root = imported.split(".", 1)[0]
            assert root not in forbidden_roots and not root.startswith(
                ("build_", "diag_")
            ), f"native import in pure closure: {current} -> {imported}"
            local = SCRIPTS / f"{imported.replace('.', '/')}.py"
            if local.is_file():
                pending.add(imported)
    return visited


def _pure_spec(module_name: str):
    _pure_local_closure(module_name)
    return importlib.import_module(module_name)


def _top_level_assignments(tree: ast.Module) -> dict[str, ast.expr]:
    declarations = {}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            targets, value = node.targets, node.value
        elif isinstance(node, ast.AnnAssign):
            targets, value = [node.target], node.value
        else:
            continue
        for target in targets:
            if isinstance(target, ast.Name):
                assert target.id not in declarations, f"duplicate authority {target.id}"
                declarations[target.id] = value
    return declarations


@pytest.mark.parametrize("module_name", PURE_SPECS)
def test_pose_vendor_specs_have_no_native_import_closure(module_name: str) -> None:
    closure = _pure_local_closure(module_name)
    assert module_name in closure
    assert _pure_spec(module_name).__name__ == module_name


def test_pure_closure_guard_has_a_real_native_positive_control() -> None:
    with pytest.raises(AssertionError, match="native import in pure closure"):
        _pure_local_closure("diagnostics.diag_build_94025A164")


@pytest.mark.parametrize(
    ("spec_name", "recipe_name", "scalars"),
    [
        (
            "vn_cone_pivot_screw_spec",
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
            "vn_cone_lock_knob_spec",
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
            "vn_cone_tip_adjuster_spec",
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
def test_native_recipes_consume_one_preserved_scalar_authority(
    spec_name: str, recipe_name: str, scalars: dict[str, float]
) -> None:
    spec = _pure_spec(spec_name)
    recipe = _source_tree(recipe_name)
    imports = [
        node
        for node in recipe.body
        if isinstance(node, ast.ImportFrom) and node.module == spec_name
    ]
    assert len(imports) == 1
    imported = {alias.name for alias in imports[0].names}
    assert set(scalars) <= imported
    assert not set(scalars) & _top_level_assignments(recipe).keys()
    assert set(scalars) <= _top_level_assignments(_source_tree(spec_name)).keys()
    for name, expected in scalars.items():
        assert getattr(spec, name) == pytest.approx(expected, rel=0.0, abs=1e-12)


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
    assert len(stop.FILLISTER_SIZE) == 5
    recipe = _source_tree("diagnostics.diag_mcmaster_fillister")
    row_imports = [
        alias
        for node in recipe.body
        if isinstance(node, ast.ImportFrom)
        and node.module == "vn_swing_stop_screw_spec"
        for alias in node.names
        if alias.name == "FILLISTER_SIZE"
    ]
    assert len(row_imports) == 1
    row_name = row_imports[0].asname or row_imports[0].name
    table = _top_level_assignments(recipe)["FILLISTER_SIZES"]
    assert isinstance(table, ast.Dict)
    matching_rows = [
        value
        for key, value in zip(table.keys, table.values, strict=True)
        if isinstance(key, ast.Constant) and key.value == "90280A108"
    ]
    assert len(matching_rows) == 1
    assert isinstance(matching_rows[0], ast.Name)
    assert matching_rows[0].id == row_name
    # Both same-SKU consumers read the row, not the native table or a copy.
    for consumer in ("vn_foot_screw_spec", "vn_latch_hook_bracket_screw_spec"):
        tree = _source_tree(consumer)
        assert "vn_swing_stop_screw_spec" in _imports(tree)
        assert not any(name.startswith("diagnostics") for name in _imports(tree))
        unpacked = [
            node.value
            for node in tree.body
            if isinstance(node, ast.Assign)
            and any(isinstance(target, ast.Tuple) for target in node.targets)
        ]
        assert len(unpacked) == 1
        assert isinstance(unpacked[0], ast.Name)
        assert unpacked[0].id == "FILLISTER_SIZE"
    foot = _pure_spec("vn_foot_screw_spec")
    assert foot.FILLISTER_SIZE is stop.FILLISTER_SIZE


def test_pivot_bands_are_actual_supplier_limits_with_explicit_order() -> None:
    pivot = _pure_spec("vn_cone_pivot_screw_spec")
    fit = _pure_spec("_fit_limits")
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
    stop = _pure_spec("vn_swing_stop_screw_spec")
    cup = _pure_spec("vn_cone_tip_adjuster_spec")
    assert pivot.HEAD_H == pivot.HEAD_T
    assert pivot.THREAD_TAIL_LEN == pivot.THREAD_LEN
    assert pivot.THREAD_SOLID_DIA == pivot.THREAD_MAJOR
    assert pivot.THREAD == "#10-24"
    assert lock.HEAD_DIA == 2.0 * lock.HEAD_R == 15.875
    assert lock.STUD_DIA == 2.0 * lock.MAJOR_R == 6.35
    assert lock.STUD_LEN == lock.LENGTH == 19.05
    assert lock.THREAD_PITCH == lock.PITCH == 1.27
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


def test_adjuster_data_consumers_do_not_read_the_native_wrapper() -> None:
    consumers = {
        "build_dt_drive_train_assembly": {"BODY_LEN", "CUP_DEPTH", "CUP_DIA", "THREAD"},
        "test_drive_train_tip_adjuster_seat": {"CUP_DEPTH", "CUP_DIA"},
    }
    for consumer, expected_names in consumers.items():
        tree = _source_tree(consumer)
        assert "build_vn_cone_tip_adjuster" not in _imports(tree)
        actual = {
            alias.name
            for node in tree.body
            if isinstance(node, ast.ImportFrom)
            and node.module == "vn_cone_tip_adjuster_spec"
            for alias in node.names
        }
        assert expected_names <= actual
    wrapper = _source_tree("build_vn_cone_tip_adjuster")
    native_imports = [
        node
        for node in wrapper.body
        if isinstance(node, ast.ImportFrom)
        and node.module == "diagnostics.diag_build_94025A164"
    ]
    assert len(native_imports) == 1
    assert {alias.name for alias in native_imports[0].names} == {"build_94025A164"}
    assert "vn_cone_tip_adjuster_spec" in _imports(wrapper)
    assert not {"BODY_LEN", "BODY_DIA", "CUP_DEPTH", "CUP_DIA", "THREAD"} & (
        _top_level_assignments(wrapper).keys()
    )


def test_adjuster_thread_limits_are_qualified_separately_from_its_cup() -> None:
    cup = _pure_spec("vn_cone_tip_adjuster_spec")
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
    fit = _pure_spec("_fit_limits")
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
    assert stop.MIN_USEFUL_ENGAGEMENT_MM == 2.85
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
