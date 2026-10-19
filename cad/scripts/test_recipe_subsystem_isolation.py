"""Source-only recipe boundaries for the six hub splits in issue #1638.

Each independently named hub test can land with its implementation. Closures use
exactly the production part inventory and dependency walker used by the recipes;
assemblies, motion studies and diagnostic probes are not part of this contract.
"""

from __future__ import annotations

from dataclasses import dataclass
from fnmatch import fnmatchcase
from pathlib import Path

import pytest

from _buildgraph import NON_PART_SCRIPTS, module_deps_of, part_scripts

SCRIPTS_DIR = Path(__file__).resolve().parent


@dataclass(frozen=True)
class Contract:
    selectors: tuple[str, ...]
    anchors: tuple[str, ...]
    forbidden: tuple[str, ...]
    # Exceptions name the precise builder/module edge, not an entire closure.
    mates: tuple[tuple[str, str], ...] = ()


@pytest.fixture(scope="module")
def part_closures() -> dict[str, frozenset[str]]:
    builders = part_scripts()
    assert builders, "canonical production part inventory is empty"
    assert len(builders) == len(set(builders)), "duplicate canonical part builders"
    closures: dict[str, frozenset[str]] = {}
    for builder in builders:
        assert builder.is_file(), f"missing part builder: {builder}"
        assert builder.resolve().parent == SCRIPTS_DIR, builder
        assert builder.name.startswith("build_"), builder
        assert builder.name not in NON_PART_SCRIPTS, builder
        assert not builder.name.endswith("_assembly.py"), builder
        assert not builder.stem.startswith("build_motion_"), builder
        assert not builder.stem.endswith("_probe"), builder
        deps = frozenset(Path(dep).stem for dep in module_deps_of(builder))
        assert deps, f"empty production part dependency closure: {builder.stem}"
        closures[builder.stem] = deps
    return closures


def assert_isolated(closures: dict[str, frozenset[str]], contract: Contract) -> None:
    """Fail closed on missing selectors/anchors, then report builder -> modules."""
    assert contract.selectors and contract.forbidden and contract.anchors
    selected: set[str] = set()
    for selector in contract.selectors:
        matches = {name for name in closures if fnmatchcase(name, selector)}
        assert matches, f"no production part builders match {selector!r}"
        anchors = {name for name in contract.anchors if fnmatchcase(name, selector)}
        assert anchors, f"selector {selector!r} has no required anchor builder"
        assert anchors <= matches, (
            f"missing production anchors for {selector!r}: {sorted(anchors - matches)}"
        )
        selected.update(matches)
    assert set(contract.anchors) <= selected, "anchor outside contract selectors"
    mates = set(contract.mates)
    for builder, module in mates:
        assert builder in selected, f"mate exception outside selector: {builder}"
        assert any(fnmatchcase(module, pattern) for pattern in contract.forbidden), (
            f"mate exception outside forbidden modules: {builder} -> {module}"
        )
        assert module in closures[builder], (
            f"stale physical-mate exception: {builder} -> {module}; remove it"
        )
    violations = {
        builder: sorted(
            module
            for module in closures[builder]
            if any(fnmatchcase(module, pattern) for pattern in contract.forbidden)
            and (builder, module) not in mates
        )
        for builder in sorted(selected)
    }
    violations = {
        builder: modules for builder, modules in violations.items() if modules
    }
    assert not violations, "cross-subsystem recipe dependencies:\n" + "\n".join(
        f"  {builder} -> {', '.join(modules)}"
        for builder, modules in violations.items()
    )


@pytest.mark.parametrize(
    "contract",
    [
        Contract(
            selectors=("build_mg_*", "build_pd_*"),
            anchors=("build_mg_magnifying_wheel", "build_pd_support_bar"),
            forbidden=("sh_column_clamp_front_geom",),
            # The support bar physically mates the clamp; its screw-slot and
            # clearance budget uses sh_column_clamp_fit's clamp geometry.
            mates=(("build_pd_support_bar", "sh_column_clamp_front_geom"),),
        )
    ],
    ids=["support-bar"],
)
def test_support_bar_isolation(part_closures, contract: Contract) -> None:
    assert_isolated(part_closures, contract)


@pytest.mark.parametrize(
    "contract",
    [
        Contract(
            selectors=("build_dt_crank*", "build_dt_vn_crank*"),
            anchors=(
                "build_dt_crank_hub",
                "build_dt_crank_pinion",
                "build_dt_crankshaft",
                "build_dt_vn_crank_hub_pin",
                "build_dt_vn_crank_seat_drive_pin",
            ),
            forbidden=("pd_transgear_*_spec", "paper_drive_*"),
        ),
        Contract(
            selectors=("build_pd_*",),
            anchors=("build_pd_transgear_removable",),
            forbidden=(
                "dt_crank_hub_geometry",
                "dt_crank_pinion_spec",
                "dt_crankshaft_spec",
            ),
        ),
    ],
    ids=["crank-to-paper-drive", "paper-drive-to-crank"],
)
def test_crank_transgear_isolation(part_closures, contract: Contract) -> None:
    assert_isolated(part_closures, contract)


@pytest.mark.parametrize(
    "contract",
    [
        Contract(
            selectors=("build_mg_*",),
            anchors=(
                "build_mg_magnifying_wheel",
                "build_mg_wheel_axle",
                "build_mg_wheel_axle_spacer",
            ),
            forbidden=(
                "pd_vn_transgear_pivot_screw_spec",
                "pd_vn_transgear_arm_plate_locating_pin_spec",
            ),
        )
    ],
    ids=["transgear-pivot-interface"],
)
def test_transgear_pivot_isolation(part_closures, contract: Contract) -> None:
    assert_isolated(part_closures, contract)


@pytest.mark.parametrize(
    "contract",
    [
        Contract(
            selectors=(
                "build_mg_*",
                "build_pn_*",
                "build_vn_*",
                "build_pd_platen_rack",
            ),
            anchors=(
                "build_mg_magnifying_wheel",
                "build_pn_pen_hanger",
                "build_vn_chain_inner_link",
                "build_pd_platen_rack",
            ),
            forbidden=("paper_drive_geom", "mg_magnifying_wheel_geom"),
            mates=(
                # The wheel's own builder owns this geometry.
                ("build_mg_magnifying_wheel", "mg_magnifying_wheel_geom"),
                # The axle journal mates the wheel bore.
                ("build_mg_wheel_axle", "mg_magnifying_wheel_geom"),
                # The spacer contacts the wheel hub's back face.
                ("build_mg_wheel_axle_spacer", "mg_magnifying_wheel_geom"),
                # The drum press-fits the wheel spigot.
                ("build_mg_wheel_drum", "mg_magnifying_wheel_geom"),
                # The wire wraps/ties the wheel and clears its hub, spokes and rim.
                ("build_vn_lever_wire", "mg_magnifying_wheel_geom"),
            ),
        )
    ],
    ids=["platen-rack"],
)
def test_platen_rack_isolation(part_closures, contract: Contract) -> None:
    assert_isolated(part_closures, contract)


@pytest.mark.parametrize(
    "contract",
    [
        Contract(
            selectors=("build_dt_*",),
            anchors=("build_dt_pinion_arbor",),
            forbidden=("ch_rocker_arm_spec",),
        )
    ],
    ids=["rocker-rod"],
)
def test_rocker_rod_isolation(part_closures, contract: Contract) -> None:
    assert_isolated(part_closures, contract)
