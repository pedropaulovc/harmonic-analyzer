"""Printed-text rulings a clean merge can carry in silently (#877 round 4).

A conflict marks a merge that needs a ruling; stale printed text that merges
cleanly does not. The #877 checklist's printed-text rows are therefore pinned
here as assertions on the merge head. A row whose fix has not reached #877 yet
is a strict xfail naming the PR that brings it. When that PR merges, the xfail
XPASSes and fails the suite until its marker is removed, and from then on a
regression fails outright.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

import pytest
import yaml

SCRIPTS = Path(__file__).resolve().parent
PARTS = SCRIPTS.parent / "config" / "parts"

# Printed text cites no internal governance (Main, S1 round 5; fleet ruling
# 2026-09-26 from the #857 Codex P2): rule numbers, ruling ids (U41), policy,
# rulings, exceptions, "accepted", book fidelity.  S1's drive-train package
# audit covers RULE n, Unn, POLICY, RULING and NAMED/ACCEPTED EXCEPTION; this
# one also bans a bare EXCEPTION(S), a bare ACCEPTED and BOOK FIDELITY, over
# every part print's text.
INTERNAL_REFERENCE = re.compile(
    r"\bRULE\s*\d+|\bU\d{2,}\b|\bPOLIC(?:Y|IES)\b|\bRULINGS?\b"
    r"|\bEXCEPTIONS?\b|\bACCEPTED\b|\bBOOK\s+FIDELITY\b",
    re.IGNORECASE,
)
# Registry fields a sheet prints: the title block's MATERIAL and FINISH cells
# and a purchased part's installation notes.
PRINTED_FIELDS = ("material_specification", "finish", "installation_notes")
# Module-level constants that hold sheet text.
PRINTED_CONSTANT = re.compile(
    r"^[A-Z0-9_]*(?:NOTES?|STEPS?|CALLOUTS?|HEADING|CAPTION|CHECKS|PLACEHOLDER)$"
)


def _strings(node: ast.AST) -> list[str]:
    return [
        child.value
        for child in ast.walk(node)
        if isinstance(child, ast.Constant) and isinstance(child.value, str)
    ]


def _docstrings(tree: ast.Module) -> set[int]:
    return {
        id(node.body[0].value)
        for node in ast.walk(tree)
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
        and node.body
        and isinstance(node.body[0], ast.Expr)
        and isinstance(node.body[0].value, ast.Constant)
    }


def printed_constants() -> dict[str, str]:
    """``module.NAME`` -> the literal text of every printed-text constant.

    A ``*_notes.py`` module exists to hold sheet text, so every string in it
    (docstrings aside) counts, including the ones its helpers return."""
    found: dict[str, str] = {}
    for path in sorted(SCRIPTS.glob("*.py")):
        if path.name.startswith("test_"):
            continue
        tree = ast.parse(path.read_text(encoding="utf-8"))
        if path.stem.endswith("_notes"):
            skip = _docstrings(tree)
            found[f"{path.stem}.*"] = " ".join(
                child.value
                for child in ast.walk(tree)
                if isinstance(child, ast.Constant)
                and isinstance(child.value, str)
                and id(child) not in skip
            )
        for node in tree.body:
            targets = (
                node.targets
                if isinstance(node, ast.Assign)
                else [node.target]
                if isinstance(node, ast.AnnAssign) and node.value is not None
                else []
            )
            for target in targets:
                if isinstance(target, ast.Name) and PRINTED_CONSTANT.match(target.id):
                    found[f"{path.stem}.{target.id}"] = " ".join(_strings(node.value))
    return found


def printed_registry_fields() -> dict[str, str]:
    found: dict[str, str] = {}
    for path in sorted(PARTS.glob("*.yaml")):
        doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        for stem, row in doc.items():
            if not isinstance(row, dict):
                continue
            for field in PRINTED_FIELDS:
                if row.get(field):
                    found[f"{stem}.{field}"] = str(row[field])
    return found


def _internal_hits(texts: dict[str, str]) -> dict[str, list[str]]:
    hits = {
        name: INTERNAL_REFERENCE.findall(" ".join(text.split()))
        for name, text in texts.items()
    }
    return {name: found for name, found in hits.items() if found}


def test_the_internal_reference_pattern_catches_what_it_forbids() -> None:
    for sample, banned in (
        ("THIN WEB: EXCEPTION.", "EXCEPTION"),
        ("TWO EXCEPTIONS APPLY.", "EXCEPTIONS"),
        ("SHORTFALL ACCEPTED.", "ACCEPTED"),
        ("SEE RULING.", "RULING"),
        ("SEE RULINGS.", "RULINGS"),
        ("PER POLICY.", "POLICY"),
        ("BOOK FIDELITY.", "BOOK FIDELITY"),
        ("TO RULE 12.", "RULE 12"),
        ("PER U41.", "U41"),
    ):
        assert INTERNAL_REFERENCE.findall(sample) == [banned], sample
    for sample in ("THRU", "UNC-2B", "58-60 HRC", "RULED SURFACE", "ACCEPT 2.3-2.7"):
        assert not INTERNAL_REFERENCE.search(sample), sample


def test_the_scan_reaches_known_printed_text() -> None:
    constants = printed_constants()
    assert "knife_mount_spec.DRAWING_NOTES" in constants
    assert "draw_drive_train_assembly.CHECKS" in constants
    assert "knife-mount.material_specification" in printed_registry_fields()


@pytest.mark.xfail(
    strict=True,
    reason="#929 (S1) states the post-mount floor plainly on the platform note and "
    "step 2; #857 deletes post-mount-screw installation_notes (b8355fcde); "
    "#834 drops cone_gear_notes' ACCEPTED EXCEPTION lines (b8406ef77)",
)
def test_no_printed_text_cites_an_internal_rule_or_ruling() -> None:
    assert not _internal_hits({**printed_constants(), **printed_registry_fields()})


@pytest.mark.xfail(strict=True, reason="#857 deletes it (b8355fcde)")
def test_post_mount_screw_prints_no_installation_notes() -> None:
    row = yaml.safe_load((PARTS / "post-mount-screw.yaml").read_text(encoding="utf-8"))
    assert "installation_notes" not in row["post-mount-screw"]


@pytest.mark.xfail(strict=True, reason="#932 tbspec wording (checklist, knife-mount)")
def test_knife_mount_prints_its_heat_treatment_in_finish_only() -> None:
    import knife_mount_spec

    row = yaml.safe_load((PARTS / "knife-mount.yaml").read_text(encoding="utf-8"))
    row = row["knife-mount"]
    # The ruling's contract, not its wording: MATERIAL names the O1 steel,
    # FINISH carries the hardness and the unpainted state, the notes neither.
    assert re.search(r"\bO1\b", row["material_specification"])
    assert "HRC" not in row["material_specification"].upper()
    assert re.search(r"58-60\s*HRC", row["finish"], re.IGNORECASE)
    assert "UNPAINTED" in row["finish"].upper()
    notes = knife_mount_spec.DRAWING_NOTES.upper()
    assert "HRC" not in notes and "UNPAINTED" not in notes


def test_cone_swing_platform_prints_no_minimum_stock_note() -> None:
    """U41: the plate is 1/4 x 2-1/2 bar as supplied, thickness 6.35 REF.
    #932 adds "5/16 IN STOCK MIN." on main; at #877 that note and its pin go."""
    texts = {
        name: text
        for name, text in printed_constants().items()
        if name.startswith(("cone_swing_platform", "draw_cone_swing_platform"))
    }
    assert texts
    for name, text in texts.items():
        assert "5/16 IN STOCK" not in text.upper(), name
