"""The CAD-owned shop inventory, cad/config/shop-equipment/*.toml, as one document.

The records are split across files by topic; ``load`` merges every file's
top-level sections (machines, gauges, tools, fixtures, holders, consumables,
stock, dro, cnc, measured_cuts, measured_cutters), so a reader sees one table
per section whichever file holds
a record. A record key in two files is refused, naming both. Every reader of
the inventory goes through here; none opens a file by path.

No COM leaf's cache key holds these files, so no part, assembly, drawing,
soundness, feature or export closure may import this module (check:recipe,
test_shop_file_readers_stay_outside_every_com_leaf).
"""

from __future__ import annotations

import tomllib
from collections.abc import Iterable
from pathlib import Path

from _paths import CAD_ROOT

DIRECTORY = CAD_ROOT / "config" / "shop-equipment"


class DuplicateRecordError(ValueError):
    pass


def files(directory: Path = DIRECTORY) -> tuple[Path, ...]:
    """The inventory's TOML files, in name order."""
    return tuple(sorted(directory.glob("*.toml")))


def load(directory: Path = DIRECTORY) -> dict:
    """Section -> record key -> record, merged over every file (``merge``)."""
    return merge(files(directory))


def merge(paths: Iterable[Path]) -> dict:
    """Section -> record key -> record, merged over ``paths``; a record key in
    two files is refused. The prechips shop directory merges the same way
    (``_process_plans.load_shop``).

    A top-level value that is not a table of records (an array of tables such
    as ``[[stock]]``, or a scalar) is refused, naming its file and section.
    """
    merged: dict[str, dict] = {}
    found_in: dict[tuple[str, str], Path] = {}
    for path in paths:
        document = tomllib.loads(path.read_text(encoding="utf-8"))
        for section, records in document.items():
            if not isinstance(records, dict):
                raise ValueError(
                    f"{path.name}: {section} is a {type(records).__name__}, "
                    "not a table of records"
                )
            table = merged.setdefault(section, {})
            for key, record in records.items():
                first = found_in.setdefault((section, key), path)
                if first != path:
                    raise DuplicateRecordError(
                        f"{section}.{key} is in both {first.name} and {path.name}"
                    )
                table[key] = record
    return merged
