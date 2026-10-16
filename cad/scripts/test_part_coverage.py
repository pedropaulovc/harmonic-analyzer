"""Machine membership and drawing coverage contracts; no SolidWorks required."""

from __future__ import annotations

import _buildgraph as bg
import _drawing_registry as registry

PART_DRAWING_EXEMPTIONS = {
    "pd_platen_paper": "consumable recording paper sheet; not manufactured",
}


def test_part_and_assembly_coverage():
    """Every built item belongs to the machine or shop, and has its own sheet."""
    parts = set(bg.part_stems())
    assemblies = set(bg.ASSEMBLY_ORDER)
    assert parts, "part_stems() returned no parts"
    assert assemblies, "ASSEMBLY_ORDER contains no assemblies"
    assert registry.DRAWINGS_BY_NAME, "DRAWINGS_BY_NAME contains no drawings"

    fixtures = {stem for stem in parts if "_tl_" in stem}
    references = {stem: set(bg.references_of(stem)) for stem in bg.ASSEMBLY_ORDER}
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
    referenced_fixtures = fixtures & set().union(*references.values())
    violations = {
        "orphans": parts - fixtures - reachable,
        "shop fixtures referenced by assemblies (#1239)": referenced_fixtures,
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
