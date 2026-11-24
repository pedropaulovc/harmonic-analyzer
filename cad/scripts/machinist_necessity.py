"""A drawing package's necessity register (drawing-guidelines rule 4).

Every REAM and every band tighter than the title block answers "what fails on
this one machine if it is .002 in loose?". The answer is not printed on the
sheet (owner ruling 2026-11-24: "In the part's registry file, not on the
sheet. The sheet stays clean; the reviewer fails a tight feature that has no
registry reason."). It is declared per drawing in
``cad/config/necessity/<dashed-drawing-stem>.yaml`` (an assembly drawing keeps
its ``-assembly`` suffix):

    necessity:
      - id: N-01
        feature: "sheet 1, front view, .159 ±.002 ridge height"
        kind: trace
        reason: "sets the lever arm ratio"
        source: "sm_summing_lever_spec.RIDGE_HEIGHT_BAND"

The register is a sibling of ``cad/config/parts/<dashed>.yaml`` and of the
assembly contract, not a key inside them: both are content-hashed inputs of the
package's SolidWorks leaves, so a reason written there would rebuild the part
and its drawing. Only the machinist review reads this file.

``kind`` is one of rule 4's kinds. ``reason`` is the few words the reviewer
weighs against that kind; ``source`` optionally cites the spec constant,
issue or ruling behind it. The review prompt receives every entry for its
package; a REAM or tight band that no entry covers has no answer.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

# Rule 4's kinds, in the rule's order.
KINDS = {
    "trace": "play, out-of-roundness, run-out, or an error in a lever arm, "
    "throw or ratio, that reaches the pen trace or a reading",
    "mesh": "a gear mesh's centre distance or run-out",
    "gap": "a running gap or stack that closes, or a wall that falls under "
    "rule 17, at the looser size",
    "joint": "a fixed joint that must hold with no bond, pin, key or screw",
    "bought_seat": "a groove or seat cut to the installation size its maker "
    "gives for a bought part",
}
REASON_WORD_LIMIT = 10
_REQUIRED = ("id", "feature", "kind", "reason")


@dataclass(frozen=True)
class NecessityEntry:
    id: str
    feature: str
    kind: str
    reason: str
    source: str | None


def register_path(config_root: Path, name: str) -> Path:
    """The register of drawing package ``name`` (underscored or dashed)."""
    return config_root / "necessity" / f"{name.replace('_', '-')}.yaml"


def _entry(value: object, path: Path, index: int) -> NecessityEntry:
    where = f"{path} necessity[{index}]"
    if not isinstance(value, dict):
        raise ValueError(f"{where}: must be a mapping")
    unknown = set(value) - {*_REQUIRED, "source"}
    if unknown:
        raise ValueError(f"{where}: unknown keys {sorted(unknown)}")

    def text(key: str) -> str:
        field = value.get(key)
        if not isinstance(field, str) or not field.strip():
            raise ValueError(f"{where}: {key} must be a non-empty string")
        return field.strip()

    entry = NecessityEntry(
        **{key: text(key) for key in _REQUIRED},
        source=text("source") if "source" in value else None,
    )
    if entry.kind not in KINDS:
        raise ValueError(
            f"{where}: kind must be one of {tuple(KINDS)}, got {entry.kind!r}"
        )
    words = len(entry.reason.split())
    if words > REASON_WORD_LIMIT:
        raise ValueError(
            f"{where}: reason is {words} words; the limit is {REASON_WORD_LIMIT}"
        )
    return entry


def load_necessity(config_root: Path, name: str) -> tuple[NecessityEntry, ...]:
    """The entries drawing package ``name`` declares; () when it has no
    register. A malformed register is an error: a typo must never silently
    remove the answer a tight feature depends on."""
    path = register_path(config_root, name)
    if not path.is_file():
        return ()
    doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(doc, dict) or set(doc) != {"necessity"}:
        raise ValueError(f"{path}: must hold exactly the key 'necessity'")
    section = doc["necessity"]
    if not isinstance(section, list) or not section:
        raise ValueError(f"{path}: necessity must be a non-empty list")
    entries = tuple(_entry(value, path, index) for index, value in enumerate(section))
    ids = [entry.id for entry in entries]
    if len(set(ids)) != len(ids):
        raise ValueError(f"{path}: necessity ids must be unique")
    return entries
