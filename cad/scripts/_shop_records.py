"""Record-granular reads of the shop's TOML records (issue #2852).

Build closures read ``cad/config/shop-equipment.toml`` and
``cad/process/shop.toml`` only through :func:`shop_record`, with literal file,
table and key arguments. ``_buildgraph.shop_records_selected`` finds those
literals statically, and ``dodo`` folds a digest of exactly the selected
records into each COM leaf's cache key, so a record edit re-keys only its
consumers and an unrelated record or a new table re-keys none. A read the
analysis cannot attribute (a runtime argument) keeps the whole file.

Under doit, ``HARMONIC_SHOP_RECORDS`` names the records (and whole files) the
task's key folds; :func:`shop_record` refuses anything else, so a hidden read
fails the build instead of reusing an artefact keyed without its input.
Unset (tests, offline checks, unnarrowed tasks), every record is readable.

Kept apart from ``_config``: editing this module re-keys only its consumers.
"""

from __future__ import annotations

import copy
import datetime
import functools
import json
import os
import tomllib
from pathlib import Path
from typing import Any

from _paths import CAD_ROOT

# The shop files by the name a literal read uses.
SHOP_FILES: dict[str, Path] = {
    "shop-equipment.toml": CAD_ROOT / "config" / "shop-equipment.toml",
    "shop.toml": CAD_ROOT / "process" / "shop.toml",
}
ENV = "HARMONIC_SHOP_RECORDS"


def _path(file: str) -> Path:
    try:
        return SHOP_FILES[file]
    except KeyError as exc:
        raise KeyError(f"unknown shop file {file!r}; expected one of {sorted(SHOP_FILES)}") from exc


@functools.cache
def _document(file: str) -> dict[str, Any]:
    return tomllib.loads(_path(file).read_text(encoding="utf-8"))


def lookup(document: dict[str, Any], table: str, key: str) -> Any:
    """``document[table][key]``, or ``None`` when absent (a table that is not a
    table also reads as absent)."""
    section = document.get(table)
    return section.get(key) if isinstance(section, dict) else None


def guard_value(records: frozenset[tuple[str, str, str]], files: frozenset[str]) -> str:
    """The ``HARMONIC_SHOP_RECORDS`` value allowing ``records`` and whole ``files``."""
    return json.dumps(
        {"files": sorted(files), "records": sorted(list(record) for record in records)},
        separators=(",", ":"),
    )


def _allowed(file: str, table: str, key: str) -> bool:
    raw = os.environ.get(ENV)
    if raw is None:
        return True
    guard = json.loads(raw)
    return file in guard["files"] or [file, table, key] in guard["records"]


def shop_record(file: str, table: str, key: str) -> Any:
    """One shop record, ``[<table>.<key>]`` of ``file`` (a copy: callers may not
    share mutations). Call it with literal arguments so the build graph can key
    the read."""
    path = _path(file)
    if not _allowed(file, table, key):
        raise KeyError(
            f"shop record {file}:{table}.{key} is outside this build's cache key "
            f"({ENV}={os.environ.get(ENV)!r}); read it through a literal "
            "shop_record(...) call in the build's import closure"
        )
    value = lookup(_document(file), table, key)
    if value is None:
        raise KeyError(f"shop record {table}.{key} is not in {path}")
    return copy.deepcopy(value)


def _canonical(value: Any) -> Any:
    if isinstance(value, (datetime.date, datetime.time)):
        return {"toml": type(value).__name__, "value": value.isoformat()}
    raise TypeError(f"unexpected TOML value {value!r}")


def records_recipe(records: frozenset[tuple[str, str, str]]) -> str:
    """Canonical text of the selected records' parsed values (``None`` when
    absent, so adding a selected record moves it; a read naming an unknown file
    fails at run time instead of here). Comments, formatting and every other
    record are outside it."""
    documents = {
        file: _document(file) if file in SHOP_FILES else {}
        for file in sorted({file for file, _, _ in records})
    }
    return json.dumps(
        [
            [file, table, key, lookup(documents[file], table, key)]
            for file, table, key in sorted(records)
        ],
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=True,
        default=_canonical,
    )
