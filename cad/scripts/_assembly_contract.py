"""Per-assembly build contracts: ``cad/config/assemblies/<dashed-stem>.yaml``.

Data that belongs to ONE assembly -- its learned flip-seed polarities and its
free-DOF contract (freed DOF count, required and allowed under-constrained
families) -- used to live in shared module-level tables in ``_assembly.py`` and
``verify.py``. Every assembly's recipe carries the former and every soundness
gate the latter, so a one-line seed for drive-train re-keyed all eight
assemblies and every gate downstream of them. One file per assembly lets
``dodo.py`` depend each assembly task (and its soundness gate) on its OWN file
only: any script
whose import closure reaches this module gets the ``"assemblies/*"`` config
token, which dodo narrows to the task's own row (see ``_config_deps``).

Deliberately NOT an accessor in ``_config``: editing ``_config.py`` re-keys
every part in the fleet, and no part reads this data.
"""

from __future__ import annotations

import functools
from dataclasses import dataclass
from pathlib import Path

import yaml

CONTRACT_DIR = Path(__file__).resolve().parent.parent / "config" / "assemblies"

_REQUIRED_KEYS = frozenset(
    {"flip_invert", "allowed_free_stems", "required_free_stems", "free_dof"}
)
_KNOWN_KEYS = _REQUIRED_KEYS | {"free_dof_per_active_channel"}


@dataclass(frozen=True)
class AssemblyContract:
    """One assembly's contract, loaded from its YAML file.

    ``flip_invert``: ``_assembly._flip_sig`` signatures (plus any ``@<diag>``
    orientation suffix) whose distance drivers seat on the side OPPOSITE the
    plain sign rule -- exactly the signatures THIS assembly's build queries. A
    signature two assemblies both exercise is listed in both files.
    ``allowed_free_stems``: the exact component families allowed to read
    under-constrained (freed operational DOF plus everything coupled to them),
    shared by the incremental refresh and the ``verify:soundness`` gate.
    ``required_free_stems``: one family per freed DOF that must ITSELF read
    under-constrained (the necessity direction of the soundness gate).
    ``free_dof`` (+ ``free_dof_per_active_channel`` x the active channel count):
    the operational DOF the saved model ships free.
    """

    stem: str
    path: Path
    flip_invert: frozenset[str]
    allowed_free_stems: tuple[str, ...]
    required_free_stems: tuple[str, ...]
    free_dof: int
    free_dof_per_active_channel: int


def contract_path(stem: str) -> Path:
    """The contract file of a DASHED assembly stem (``"drive-train"``)."""
    return CONTRACT_DIR / f"{stem}.yaml"


def _string_list(path: Path, key: str, value: object) -> tuple[str, ...]:
    if not isinstance(value, list) or not all(isinstance(v, str) and v for v in value):
        raise ValueError(f"{path}: {key} must be a list of non-empty strings")
    duplicates = sorted({v for v in value if value.count(v) > 1})
    if duplicates:
        raise ValueError(f"{path}: {key} lists {duplicates} more than once")
    return tuple(value)


def _count(path: Path, key: str, value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{path}: {key} must be a non-negative integer")
    return value


@functools.lru_cache(maxsize=None)
def assembly_contract(stem: str) -> AssemblyContract:
    """Load and validate one assembly's contract. A missing file RAISES: an
    empty seed set would seat every inverted reference on the wrong side and
    fail its mates with a misleading message."""
    path = contract_path(stem)
    if not path.is_file():
        raise FileNotFoundError(
            f"assembly contract missing: {path} -- every assembly in "
            "_buildgraph.ASSEMBLY_ORDER needs one (empty lists are fine)"
        )
    doc = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    if not isinstance(doc, dict):
        raise ValueError(f"{path}: expected a mapping")
    missing = sorted(_REQUIRED_KEYS - doc.keys())
    unknown = sorted(doc.keys() - _KNOWN_KEYS)
    if missing or unknown:
        raise ValueError(f"{path}: missing keys {missing}, unknown keys {unknown}")
    return AssemblyContract(
        stem=stem,
        path=path,
        flip_invert=frozenset(_string_list(path, "flip_invert", doc["flip_invert"])),
        allowed_free_stems=_string_list(
            path, "allowed_free_stems", doc["allowed_free_stems"]
        ),
        required_free_stems=_string_list(
            path, "required_free_stems", doc["required_free_stems"]
        ),
        free_dof=_count(path, "free_dof", doc["free_dof"]),
        free_dof_per_active_channel=_count(
            path,
            "free_dof_per_active_channel",
            doc.get("free_dof_per_active_channel", 0),
        ),
    )


def contract_files() -> list[Path]:
    """Every assembly contract file (the ``"assemblies/*"`` family)."""
    return sorted(CONTRACT_DIR.glob("*.yaml"))
