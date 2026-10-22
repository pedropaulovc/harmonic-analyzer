"""Machine membership and drawing coverage contracts; no SolidWorks required."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

import _buildgraph as bg
import _config
import _drawing_registry as registry
import export_features

PART_DRAWING_EXEMPTIONS = {
    "pd_platen_paper": "consumable recording paper sheet; not manufactured",
}


def _components() -> dict[str, str]:
    """``component_of`` rows: a detail part a parent part may be built up from
    (subsystem-identities.md, "Components of a built-up part"). Stems in the
    build's underscore form."""
    return {
        stem.replace("-", "_"): str(row["component_of"]).replace("-", "_")
        for stem, row in _config.parts().items()
        if "component_of" in row
    }


def test_components_name_a_built_part_whose_notes_permit_the_construction():
    """A component is in the machine only through its parent, so the parent
    must exist and its own drawing notes must permit the built-up route
    (export_features: explicit BUILT_UP_PERMISSION_NOTE text)."""
    parts = set(bg.part_stems())
    components = _components()
    for component, parent in components.items():
        assert component in parts, f"{component}: component row without a build"
        assert parent in parts, (
            f"{component}: component_of names no built part {parent}"
        )
        assert parent not in components, f"{component}: nested component {parent}"
        assert (
            export_features.requirement_manifest(parent)["construction"]
            == "built_up_permitted"
        ), f"{component}: {parent}'s notes do not permit a built-up part"


def test_part_and_assembly_coverage():
    """Every built item belongs to the machine or shop, and has its own sheet.

    Shop fixtures (``bg.is_shop_fixture``) must belong to a registered assembly,
    may be placed only by a shop-fixture assembly, and never enter the machine
    tree through their assembly."""
    parts = set(bg.part_stems())
    assemblies = set(bg.ASSEMBLY_ORDER)
    assert parts, "part_stems() returned no parts"
    assert assemblies, "ASSEMBLY_ORDER contains no assemblies"
    assert registry.DRAWINGS_BY_NAME, "DRAWINGS_BY_NAME contains no drawings"
    assert bg.ASSEMBLY_ORDER[-1] == "ha_harmonic_analyzer", bg.ASSEMBLY_ORDER

    fixtures = {stem for stem in parts if bg.is_shop_fixture(stem)}
    fixture_assemblies = {stem for stem in assemblies if bg.is_shop_fixture(stem)}
    references = {stem: set(bg.references_of(stem)) for stem in bg.ASSEMBLY_ORDER}
    assembly_references = set().union(*references.values())
    machine_references = set().union(
        *(refs for stem, refs in references.items() if stem not in fixture_assemblies)
    )
    reachable = set()
    pending = [bg.ASSEMBLY_ORDER[-1]]
    while pending:
        stem = pending.pop()
        if stem in reachable:
            continue
        reachable.add(stem)
        if stem in assemblies:
            pending.extend(references[stem] - reachable)

    part_drawings = {
        row.part
        for row in registry.DRAWINGS_BY_NAME.values()
        if row.source_kind == "part"
    }
    assembly_drawings = {
        row.part
        for row in registry.DRAWINGS_BY_NAME.values()
        if row.source_kind == "assembly"
    }
    exemptions = set(PART_DRAWING_EXEMPTIONS)
    referenced_fixtures = fixtures & machine_references
    components = _components()
    reachable |= {stem for stem, parent in components.items() if parent in reachable}
    violations = {
        "orphans": parts - fixtures - reachable,
        "shop fixtures without registered assembly membership": fixtures
        - assembly_references,
        "shop fixtures referenced by machine assemblies (#1239)": referenced_fixtures,
        "shop-fixture assemblies in the machine tree": fixture_assemblies & reachable,
        "undrawn": parts - part_drawings - exemptions,
        "exemptions with drawings": exemptions & (part_drawings | assembly_drawings),
        "exemptions naming nonexistent parts": exemptions - parts,
        "assemblies without assembly drawings": assemblies - assembly_drawings,
    }
    failures = [
        f"{label}: {', '.join(sorted(stems))}"
        for label, stems in violations.items()
        if stems
    ]
    assert not failures, "Part coverage violations:\n" + "\n".join(failures)


@pytest.mark.parametrize("assembled", [False, True])
def test_shop_fixture_coverage_requires_any_registered_assembly(monkeypatch, assembled):
    fixture = "coverage_tl_fixture"
    fixture_assembly = next(
        stem for stem in bg.ASSEMBLY_ORDER if bg.is_shop_fixture(stem)
    )
    original_parts = bg.part_stems()
    original_references = bg.references_of
    monkeypatch.setattr(bg, "part_stems", lambda: [*original_parts, fixture])
    monkeypatch.setattr(
        registry,
        "DRAWINGS_BY_NAME",
        {
            **registry.DRAWINGS_BY_NAME,
            fixture: SimpleNamespace(part=fixture, source_kind="part"),
        },
    )

    def references_of(stem):
        references = set(original_references(stem))
        if assembled and stem == fixture_assembly:
            references.add(fixture)
        return references

    monkeypatch.setattr(bg, "references_of", references_of)
    if assembled:
        test_part_and_assembly_coverage()
    else:
        with pytest.raises(
            AssertionError,
            match="shop fixtures without registered assembly membership: " + fixture,
        ):
            test_part_and_assembly_coverage()
