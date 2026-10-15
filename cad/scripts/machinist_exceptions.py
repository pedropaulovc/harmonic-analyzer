"""Owner-declared machinist-review exceptions, stored per package config.

Known, owner-accepted departures live next to the thing they concern — in
``cad/config/parts/<dashed-name>.yaml`` or
``cad/config/assemblies/<dashed-stem>.yaml`` under the package's key — never
in one central list:

    dt-crank-hub:
      number: MHA-DT-031
      ...
      machinist_exceptions:
        - id: RV-001
          where: "sheet 1, front view, 25.20 overall length"
          finding: "tight clearance band with no named mate (rule 4)"
          reason: "CLEARS callout names the mate; owner accepts callout-local naming"
          kind: accept

``kind`` is an enum: ``accept`` (do not file the finding at all) or ``minor``
(file it at most under minor, never gating). The review prompt receives every
declared exception for its package; a would-be finding that matches one is not
a finding.
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


def load_exceptions(config_root: Path, name: str, kind: str) -> tuple[MachinistException, ...]:
    """The package's declared exceptions; () when the package declares none.

    A missing config file is not an error: most packages declare nothing.
    A malformed declaration is an error — a typo must never silently widen
    or narrow what the reviewer ignores.
    """
    dashed = name.replace("_", "-")
    subdir = "parts" if kind == "part" else "assemblies"
    path = config_root / subdir / f"{dashed}.yaml"
    if not path.is_file():
        return ()
    doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(doc, dict):
        raise ValueError(f"{path}: config must be a mapping")
    section = None
    for holder in (doc.get(dashed), doc):
        if isinstance(holder, dict) and "machinist_exceptions" in holder:
            section = holder["machinist_exceptions"]
            break
    if section is None:
        return ()
    if not isinstance(section, list):
        raise ValueError(f"{path}: machinist_exceptions must be a list")
    entries = tuple(_entry(value, path, index) for index, value in enumerate(section))
    ids = [entry.id for entry in entries]
    if len(set(ids)) != len(ids):
        raise ValueError(f"{path}: machinist_exceptions ids must be unique")
    return entries
