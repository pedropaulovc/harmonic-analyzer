"""Owner-declared machinist-review exceptions, one register per drawing package.

Known, owner-accepted departures are declared per drawing in
``cad/config/exceptions/<dashed-drawing-stem>.yaml`` (an assembly drawing keeps
its ``-assembly`` suffix, as the necessity register does), never in one central
list:

    machinist_exceptions:
      - id: RV-001
        where: "sheet 1, front view, 25.20 overall length"
        finding: "tight clearance band with no named mate (rule 4)"
        reason: "CLEARS callout names the mate; owner accepts callout-local naming"
        kind: accept

The register is a sibling of ``cad/config/parts/<dashed>.yaml`` and of the
assembly contract, not a key inside them: both are content-hashed inputs of the
package's SolidWorks leaves, so rewording one entry there rebuilt the part or
assembly and everything downstream of it (#3663). Only the machinist review
and tests read this file; no build closure does.

``kind`` is an enum: ``accept`` (do not file the finding at all) or ``minor``
(file it at most under minor, never gating). The review prompt receives every
declared exception for its package; a would-be finding that matches one is not
a finding.

TEMPORARY (#3663): a package not yet moved still declares under its registry
row in ``cad/config/parts/<dashed>.yaml`` or at the top level of its assembly
contract. ``load_exceptions`` reads that place too and refuses a package that
declares in both; ``cad/config/machinist-review/exceptions-unmoved.yaml`` lists
them, and the edit that next changes such a file moves its block here.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

KINDS = ("accept", "minor")


@dataclass(frozen=True)
class MachinistException:
    id: str
    where: str
    finding: str
    reason: str
    kind: str


def _entry(value: object, path: Path, index: int) -> MachinistException:
    where = f"{path} machinist_exceptions[{index}]"
    if not isinstance(value, dict):
        raise ValueError(f"{where}: must be a mapping")
    unknown = set(value) - {"id", "where", "finding", "reason", "kind"}
    if unknown:
        raise ValueError(f"{where}: unknown keys {sorted(unknown)}")
    fields = {}
    for key in ("id", "where", "finding", "reason", "kind"):
        field = value.get(key)
        if not isinstance(field, str) or not field.strip():
            raise ValueError(f"{where}: {key} must be a non-empty string")
        fields[key] = field.strip()
    if fields["kind"] not in KINDS:
        raise ValueError(f"{where}: kind must be one of {KINDS}, got {fields['kind']!r}")
    return MachinistException(**fields)


def register_path(config_root: Path, name: str) -> Path:
    """The register of drawing package ``name`` (underscored or dashed)."""
    return config_root / "exceptions" / f"{name.replace('_', '-')}.yaml"


def legacy_path(config_root: Path, name: str, kind: str) -> tuple[Path, str]:
    """TEMPORARY (#3663): the build-contract file a package not yet moved
    declares in, and the key its entries sit under there."""
    dashed = name.replace("_", "-")
    if kind == "part":
        return config_root / "parts" / f"{dashed}.yaml", dashed
    # Assembly drawings keep the "-assembly" suffix; their contract is named
    # by the bare stem (BUILDING.md).
    stem = dashed.removesuffix("-assembly")
    return config_root / "assemblies" / f"{stem}.yaml", stem


def load_exceptions(config_root: Path, name: str, kind: str) -> tuple[MachinistException, ...]:
    """A part or assembly package's declared exceptions; () when the package
    declares none. Traveler declarations are found by
    ``machinist_review_traveler.load_exceptions``.

    A missing register is not an error: most packages declare nothing.
    A malformed declaration is an error — a typo must never silently widen
    or narrow what the reviewer ignores — and so is a package that declares
    both in its register and in its build contract.
    """
    path = register_path(config_root, name)
    declared = _load_register(path)
    legacy, stem = legacy_path(config_root, name, kind)
    unmoved = load_exceptions_file(legacy, stem)
    if declared and unmoved:
        raise ValueError(
            f"{path} and {legacy} both declare machinist_exceptions: "
            f"move the whole block to {path}"
        )
    return declared or unmoved


def _load_register(path: Path) -> tuple[MachinistException, ...]:
    if not path.is_file():
        return ()
    doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(doc, dict) or set(doc) != {"machinist_exceptions"}:
        raise ValueError(f"{path}: must hold exactly the key 'machinist_exceptions'")
    section = doc["machinist_exceptions"]
    if not isinstance(section, list) or not section:
        raise ValueError(f"{path}: machinist_exceptions must be a non-empty list")
    return _entries(section, path)


def load_exceptions_file(path: Path, stem: str) -> tuple[MachinistException, ...]:
    """The ``machinist_exceptions`` declared in ``path``, under ``stem`` or at
    top level; () when the file is absent or declares none."""
    if not path.is_file():
        return ()
    doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(doc, dict):
        raise ValueError(f"{path}: config must be a mapping")
    section = None
    for holder in (doc.get(stem), doc):
        if isinstance(holder, dict) and "machinist_exceptions" in holder:
            section = holder["machinist_exceptions"]
            break
    if section is None:
        return ()
    if not isinstance(section, list):
        raise ValueError(f"{path}: machinist_exceptions must be a list")
    return _entries(section, path)


def _entries(section: list, path: Path) -> tuple[MachinistException, ...]:
    entries = tuple(_entry(value, path, index) for index, value in enumerate(section))
    ids = [entry.id for entry in entries]
    if len(set(ids)) != len(ids):
        raise ValueError(f"{path}: machinist_exceptions ids must be unique")
    return entries
