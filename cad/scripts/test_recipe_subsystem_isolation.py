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
    for builder in builders:
        assert builder.is_file(), f"missing part builder: {builder}"
        assert builder.resolve().parent == SCRIPTS_DIR, builder
        assert builder.name.startswith("build_"), builder
        assert builder.name not in NON_PART_SCRIPTS, builder
        assert not builder.name.endswith("_assembly.py"), builder
        assert not builder.stem.startswith("build_motion_"), builder
        assert not builder.stem.endswith("_probe"), builder
    return {
        builder.stem: frozenset(Path(dep).stem for dep in module_deps_of(builder))
        for builder in builders
    }


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
