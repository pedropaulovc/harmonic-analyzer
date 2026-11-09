"""Issue #290 cutover: every drawn package declares its ``drawing_unit`` explicitly.

Each part row (``cad/config/parts/<stem>.yaml``) and assembly contract
(``cad/config/assemblies/<stem>.yaml``) states ``drawing_unit: in``; only the
metric-only supplier packages on ``METRIC_PACKAGES`` state ``drawing_unit: mm``
(drawing-simplicity-policy.md, "How the repository implements the
guidelines"). A part with no sheet (``test_part_coverage.
PART_DRAWING_EXEMPTIONS``) need not declare one, but any unit it does declare
obeys the same rules. ``_package_units.drawing_unit`` still resolves an omitted
key to ``mm``, so this reads each package's own raw row, never the resolved
unit. Pure YAML; no SolidWorks.
"""

from __future__ import annotations

from pathlib import Path

import yaml

import _buildgraph as bg
from test_part_coverage import PART_DRAWING_EXEMPTIONS

# Metric-only supplier packages: package -> why its sheet stays millimetres.
# Each reason cites one of its row's ``supplier_skus``.
METRIC_PACKAGES: dict[str, str] = {
    "parts/ch-rocker-arm-tl-vn-oblique-carriage-screw": (
        "DIN 912 / ISO 4762 M4 x 20 socket head screw (McMaster-Carr 91290A168) "
        "into the HGH15CA carriage's vendor-cut M4 holes, the fastener policy's "
        "vendor-cut metric exception"
    ),
    "parts/ch-rocker-arm-tl-vn-oblique-handwheel": (
        "HARFINGTON 50 mm handwheel with an 8 mm bore (Amazon B0DJ3DZT86) for the "
        "Tr8 leadscrew"
    ),
    "parts/ch-rocker-arm-tl-vn-oblique-leadscrew-kit": (
        "ReliaBot T8 Tr8x2 lead screw cut to 410 mm and its brass flange nut "
        "(Amazon B085DDHJTW), the Tr8 metric-only vendor line (owner ruling 4, "
        "2026-11-01)"
    ),
    "parts/ch-rocker-arm-tl-vn-oblique-pillow-block": (
        "uxcell KP08 pillow block with an 8 mm bore insert bearing (Amazon "
        "B0D2L8M4QR), a metric-only vendor line (owner ruling 4, 2026-11-01)"
    ),
    "parts/ch-rocker-arm-tl-vn-oblique-rail-kit": (
        "NUIBBYED HGR15 rail and HGH15CA carriage kit, 450 mm (Amazon B0C4DJNL33), "
        "a metric-only vendor line (owner ruling 4, 2026-11-01)"
    ),
    "parts/sm-vn-gooseneck-shoulder-washer": (
        "DIN 125 M6 washer (McMaster-Carr 93475A250), 6.4 ID x 12.0 OD, the "
        "only stock bore and OD inside the counter eye's retention and half-turn "
        "clearance window (owner ruling 2026-11-08, #2144 item 11.4)"
    ),
}

_UNITS = ("in", "mm")
_MISSING = object()


def _source(package: str) -> str:
    return f"cad/config/{package}.yaml"


def _undrawn_parts() -> set[str]:
    """``PART_DRAWING_EXEMPTIONS`` (underscore build stems) as packages."""
    return {f"parts/{stem.replace('_', '-')}" for stem in PART_DRAWING_EXEMPTIONS}


def _load(path: Path) -> object:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {}


def _package_rows() -> dict[str, object]:
    """Package (``parts/<stem>`` / ``assemblies/<stem>``) -> its own raw row.

    ``parts/_defaults.yaml`` is registry metadata, not a package. A part file
    holds exactly its own row, as ``_config`` requires."""
    rows: dict[str, object] = {}
    for path in map(Path, bg.parts_registry_files()):
        if path.name == "_defaults.yaml":
            continue
        doc = _load(path)
        assert isinstance(doc, dict) and set(doc) == {path.stem}, (
            f"{_source(f'parts/{path.stem}')}: must define exactly the part "
            f"{path.stem!r}"
        )
        rows[f"parts/{path.stem}"] = doc[path.stem]
    for path in map(Path, bg.assembly_contract_files()):
        rows[f"assemblies/{path.stem}"] = _load(path)
    return rows


def _declarations() -> dict[str, object]:
    """Package -> its declared ``drawing_unit`` (``_MISSING`` when absent)."""
    declared: dict[str, object] = {}
    for package, row in _package_rows().items():
        assert isinstance(row, dict), f"{_source(package)}: row is not a mapping"
        declared[package] = row.get("drawing_unit", _MISSING)
    return declared


def test_census_covers_both_families_and_every_allowlisted_package():
    rows = _package_rows()
    for family in ("parts", "assemblies"):
        assert any(package.startswith(f"{family}/") for package in rows), (
            f"no {family} packages found under cad/config/{family}/"
        )
    absent = sorted(set(METRIC_PACKAGES) - set(rows))
    assert not absent, f"METRIC_PACKAGES names packages with no YAML row: {absent}"
    absent = sorted(_undrawn_parts() - set(rows))
    assert not absent, f"PART_DRAWING_EXEMPTIONS names parts with no YAML row: {absent}"
    for package, reason in METRIC_PACKAGES.items():
        skus = [str(sku) for sku in rows[package].get("supplier_skus") or []]
        assert any(sku in reason for sku in skus), (
            f"{package}: METRIC_PACKAGES reason cites none of its supplier_skus "
            f"{skus}: {reason!r}"
        )


def test_every_drawn_package_declares_a_valid_drawing_unit():
    undrawn = _undrawn_parts()
    problems = []
    for package, unit in sorted(_declarations().items()):
        if unit is _MISSING:
            if package in undrawn:
                continue
            problems.append(
                f"{package} ({_source(package)}): declares no drawing_unit; the "
                "mm fallback is not a declaration"
            )
        elif unit not in _UNITS:
            problems.append(
                f"{package} ({_source(package)}): drawing_unit {unit!r} is not "
                f"one of {_UNITS}"
            )
    assert not problems, "\n".join(problems)


def test_only_allowlisted_metric_supplier_packages_declare_millimetres():
    problems = []
    for package, unit in sorted(_declarations().items()):
        if unit not in _UNITS:
            continue  # test_every_drawn_package_declares_a_valid_drawing_unit
        expected = "mm" if package in METRIC_PACKAGES else "in"
        if unit == expected:
            continue
        if expected == "in":
            problems.append(
                f"{package} ({_source(package)}): declares 'mm' but is not a "
                "metric-only supplier package on METRIC_PACKAGES"
            )
        else:
            problems.append(
                f"{package} ({_source(package)}): on METRIC_PACKAGES but declares "
                f"{unit!r}; declare 'mm' or drop it from the allowlist"
            )
    assert not problems, "\n".join(problems)
