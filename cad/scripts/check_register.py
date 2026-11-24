"""The check register (tolerance-policy.md, "Checks in spec modules and tests").

A numeric check in a spec, geometry or stack module or in a test (a floor, a
limit, a budget, a guard that raises) says what fails on the machine just
past it, what sets its number and on which basis it is summed. Those answers
are data beside the code, in ``cad/config/checks/<dashed-module-stem>.yaml``,
named for the module that asserts the check:

    checks:
      - id: C-01
        check: "FEED_CONTACT_RATIO_FLOOR"
        kind: mesh
        reason: "a tooth pair lets go; the feed hitches"
        source: "delegated ruling 2026-11-11 (Main), issue #2416"
        basis: after_setting

``check`` is the constant, or the guard's message, as the module's source
spells it. ``kind`` is one of the necessity register's kinds, or ``wall`` or
``thread`` (guidelines rules 17 and 18: owner-ruled thresholds, not necessity
answers, so rule 4's list is not widened). ``reason`` is at most ten words.
``source`` is required: a ruling with its date, a supplier's figure, a
standard's clause, or the module that computes the number. ``basis`` is the
class the check is summed on.

Code review and this module's test read the register; nothing that builds
does. A spec module that read its own entries would turn every reason into a
SolidWorks rebuild (``test_dodo_recipe`` forbids it). The loader is not part
of ``machinist_necessity.py`` because that module's bytes key every machinist
review. A necessity entry whose ``source`` cites a check is weighed by code
review, not here: a cited constant may be a band, which is no check.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import yaml

import machinist_necessity

KINDS = (*machinist_necessity.KINDS, "wall", "thread")
BASES = ("worst_case", "after_setting", "measured")
REASON_WORD_LIMIT = machinist_necessity.REASON_WORD_LIMIT
_KEYS = ("id", "check", "kind", "reason", "source", "basis")


@dataclass(frozen=True)
class CheckEntry:
    id: str
    check: str
    kind: str
    reason: str
    source: str
    basis: str


def register_dir(config_root: Path) -> Path:
    return config_root / "checks"


def module_for(path: Path, scripts_dir: Path) -> Path:
    """The module a register file is named for."""
    return scripts_dir / f"{path.stem.replace('-', '_')}.py"


def _entry(value: object, path: Path, index: int) -> CheckEntry:
    where = f"{path} checks[{index}]"
    if not isinstance(value, dict) or set(value) != set(_KEYS):
        raise ValueError(f"{where}: must be a mapping with exactly the keys {_KEYS}")
    for key in _KEYS:
        if not isinstance(value[key], str) or not value[key].strip():
            raise ValueError(f"{where}: {key} must be a non-empty string")
    entry = CheckEntry(**{key: value[key].strip() for key in _KEYS})
    if entry.kind not in KINDS:
        raise ValueError(f"{where}: kind must be one of {KINDS}, got {entry.kind!r}")
    if entry.basis not in BASES:
        raise ValueError(f"{where}: basis must be one of {BASES}, got {entry.basis!r}")
    words = len(entry.reason.split())
    if words > REASON_WORD_LIMIT:
        raise ValueError(
            f"{where}: reason is {words} words; the limit is {REASON_WORD_LIMIT}"
        )
    return entry


def load_checks(path: Path) -> tuple[CheckEntry, ...]:
    """The entries of one register file. A malformed file is an error."""
    doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(doc, dict) or set(doc) != {"checks"}:
        raise ValueError(f"{path}: must hold exactly the key 'checks'")
    section = doc["checks"]
    if not isinstance(section, list) or not section:
        raise ValueError(f"{path}: checks must be a non-empty list")
    entries = tuple(_entry(value, path, index) for index, value in enumerate(section))
    for field in ("id", "check"):
        values = [getattr(entry, field) for entry in entries]
        if len(set(values)) != len(values):
            raise ValueError(f"{path}: {field} values must be unique")
    return entries


def problems(config_root: Path, scripts_dir: Path) -> list[str]:
    """Every way the register disagrees with the code it describes: a file
    named for no module, and a ``check`` its module's source no longer
    spells (a whole name for a constant; the literal text for a message)."""
    found: list[str] = []
    for path in sorted(register_dir(config_root).glob("*.yaml")):
        module = module_for(path, scripts_dir)
        if not module.is_file():
            found.append(f"{path.name}: no module {module.name}")
            continue
        source = module.read_text(encoding="utf-8")
        entries = load_checks(path)
        found.extend(
            f"{path.name}: {entry.id} names {entry.check!r}, which {module.name} "
            "does not contain"
            for entry in entries
            if not re.search(rf"(?<!\w){re.escape(entry.check)}(?!\w)", source)
        )
    return found
