"""Locate prechips process plans, the shop directory and the generated travelers.

Each enrolled part has an authored ``cad/process/<stem>/plan.toml`` that the
latest prechips release renders (``prechips_traveler.py``), with the shared
shop directory ``cad/process/shop/``, into two standalone HTML travelers under
``cad/out/travelers/<stem>/``: the concise ``pro`` sheet and the ``hobby``
sheet with its setup pictures. The hobby sheet is also printed to
``<slug>-traveler.pdf`` beside them. ``build`` and ``release`` render every
enrolled part (``build_bare`` none); ``release`` ships those PDFs under the
bundle's ``travelers/``.

Enrolment is the plan file itself: a part is enrolled when its plan is not a
placeholder (``revision = "placeholder"``, the plans that only list a part's
tools until its traveler is written). No list names the enrolled parts.

A **family plan** (owner rulings 2026-11-24) is one plan for several near-twin
parts made on shared setups: ``cad/process/<family>/plan.toml`` binds each
part's feature manifest under prechips ``[[parts]]`` and none of those parts
has a plan directory of its own. Its stem is the family's, not a part's
(``sh_column_clamp`` for ``sh_column_clamp_front`` and ``sh_column_clamp_back``):
``family_parts`` gives the parts it binds and ``part_stems`` the parts any
plan serves. The family's task
renders the shared sheets and, for each part, a one-page placeholder that
points to the shared one, printed to that part's own ``<slug>-traveler.pdf``:
a release still holds a PDF under every enrolled part's name.
"""

from __future__ import annotations

import functools
import tomllib
from pathlib import Path

import _shop_equipment
from _paths import CAD_ROOT

CAD_OUT = CAD_ROOT / "out"
PROCESS_ROOT = CAD_ROOT / "process"
# The prechips shop: every ``*.toml`` directly in it (``shop_files``), merged
# by section; each plan names it as ``shop = "../shop"``.
SHOP_DIR = PROCESS_ROOT / "shop"
# A placeholder plan's ``revision``: the part is not enrolled.
PLACEHOLDER_REVISION = "placeholder"


def enrolled_stems(root: Path = PROCESS_ROOT) -> tuple[str, ...]:
    """The parts with a traveler: each ``<stem>/plan.toml`` under ``root`` whose
    ``revision`` is not ``PLACEHOLDER_REVISION``, sorted. A plan TOML cannot
    read fails here, naming it, so no plan is silently left out."""
    stems = []
    for plan in root.glob("*/plan.toml"):
        try:
            revision = tomllib.loads(plan.read_text(encoding="utf-8")).get("revision")
        except (OSError, UnicodeError, tomllib.TOMLDecodeError) as exc:
            raise ValueError(f"unreadable process plan {plan}: {exc}") from exc
        if revision != PLACEHOLDER_REVISION:
            stems.append(plan.parent.name)
    return tuple(sorted(stems))


TRAVELER_STEMS: tuple[str, ...] = enrolled_stems()
# Each traveler file and the built-in prechips profile it is rendered with,
# from the same plan; ``pro`` first.
TRAVELER_PROFILES: dict[str, str] = {
    "traveler.html": "pro",
    "traveler-hobby.html": "hobby",
}
# The profile whose sheet is printed to PDF and shipped in releases.
PDF_PROFILE = "hobby"


def plan_path(stem: str) -> Path:
    return PROCESS_ROOT / stem / "plan.toml"


def family_parts(stem: str, root: Path | None = None) -> dict[str, str]:
    """A family plan's parts: the id its ``[[parts]]`` gives each, to the
    registry stem whose feature manifest it binds
    (``.../out/features/<part stem>/features.toml``), in plan order. Empty
    for a one-part plan, and for a stem with no plan."""
    root = PROCESS_ROOT if root is None else root
    path = root / stem / "plan.toml"
    if not path.is_file():
        return {}
    return dict(_bound_parts(path, path.stat().st_mtime_ns, stem))


@functools.cache
def _bound_parts(path: Path, _mtime_ns: int, stem: str) -> tuple[tuple[str, str], ...]:
    """``family_parts`` of the plan at ``path``, parsed once per version of
    the file: task loading asks for every enrolled plan's parts many times."""
    plan = tomllib.loads(path.read_text(encoding="utf-8"))
    parts: dict[str, str] = {}
    for part in plan.get("parts", ()):
        manifest = Path(part["file"])
        if (
            manifest.name != "features.toml"
            or manifest.parent.parent.name != "features"
        ):
            raise ValueError(
                f"{stem}: part {part['id']!r} binds {part['file']!r}, "
                "not an out/features/<stem>/features.toml manifest"
            )
        parts[part["id"]] = manifest.parent.name
    if len(set(parts.values())) != len(parts):
        raise ValueError(f"{stem}: two [[parts]] bind one manifest")
    return tuple(parts.items())


def part_stems(stem: str, root: Path | None = None) -> tuple[str, ...]:
    """The registry parts a plan serves: a family plan's parts, else the
    plan's own stem."""
    return tuple(family_parts(stem, root).values()) or (stem,)


def part_view(plan: dict, part_id: str) -> dict:
    """One part's reading of a family ``plan``: the plan's ``parameters`` with
    the part's own laid over them (as prechips binds them) and only the
    setups and operations the part goes through: those that name this part
    or none, and a setup that lists it in ``serves`` (the bolted pair's bore
    prints the back's values and holds the front too), whose operations it
    takes unless they name another part. An operation naming the part inside
    another part's setup stays, in that setup. This is what a CAM recipe and
    the stock list read for one half of a family."""
    own = next(part for part in plan["parts"] if part["id"] == part_id)

    def mine(table: dict, default: str | None = None) -> bool:
        return table.get("part", default) in (None, part_id)

    setups = []
    for setup in plan.get("setups", ()):
        served = part_id in setup.get("serves", ())
        operations = [
            operation
            for operation in setup.get("operations", ())
            if mine(operation, None if served else setup.get("part"))
        ]
        if mine(setup) or served or operations:
            setups.append({**setup, "operations": operations})
    return {
        **{key: value for key, value in plan.items() if key != "parts"},
        "parameters": plan.get("parameters", {}) | own.get("parameters", {}),
        "setups": setups,
    }


def shop_files(directory: Path | None = None) -> tuple[Path, ...]:
    """The shop's files as prechips reads them: every ``*.toml`` directly in
    ``directory`` (default ``SHOP_DIR``) whose name does not start with ``.``,
    in name order."""
    directory = SHOP_DIR if directory is None else directory
    return tuple(
        sorted(
            path
            for path in directory.glob("*.toml")
            if path.is_file() and not path.name.startswith(".")
        )
    )


def load_shop(directory: Path | None = None) -> dict:
    """Section -> key -> record over every ``shop_files`` file, as prechips
    (0.11.10 and later) merges a shop directory: a key in two files is refused,
    naming both. Every HA reader of the shop goes through here."""
    directory = SHOP_DIR if directory is None else directory
    files = shop_files(directory)
    if not files:
        raise FileNotFoundError(f"no shop .toml files in {directory}")
    return _shop_equipment.merge(files)


def traveler_dir(stem: str, out: Path = CAD_OUT) -> Path:
    return Path(out) / "travelers" / stem


def traveler_paths(stem: str, out: Path = CAD_OUT) -> tuple[Path, ...]:
    """The part's HTML traveler files, in ``TRAVELER_PROFILES`` order."""
    return tuple(traveler_dir(stem, out) / name for name in TRAVELER_PROFILES)


def traveler_pdf_name(stem: str) -> str:
    """``<slug>-traveler.pdf``: the slug is the dashed stem the part's files carry."""
    return f"{stem.replace('_', '-')}-traveler.pdf"


def traveler_pdf_path(stem: str, out: Path = CAD_OUT) -> Path:
    """The ``PDF_PROFILE`` sheet printed to PDF, the file a release ships."""
    return traveler_dir(stem, out) / traveler_pdf_name(stem)


def placeholder_paths(stem: str, out: Path = CAD_OUT) -> dict[str, tuple[Path, Path]]:
    """A family plan's placeholders, by part id: each part's one-page pointer
    to the shared sheet as HTML and as the PDF a release ships under the
    part's own name, ``<part slug>-traveler.pdf``, beside the shared sheets.
    Empty for a one-part plan."""
    directory = traveler_dir(stem, out)
    return {
        part_id: (
            directory / f"{part.replace('_', '-')}-traveler.html",
            directory / traveler_pdf_name(part),
        )
        for part_id, part in family_parts(stem).items()
    }


def traveler_pdf_paths(stem: str, out: Path = CAD_OUT) -> tuple[Path, ...]:
    """Every PDF a release ships for the plan: its sheet, then a family's
    placeholder for each part."""
    return (
        traveler_pdf_path(stem, out),
        *(pdf for _html, pdf in placeholder_paths(stem, out).values()),
    )


def traveler_outputs(stem: str, out: Path = CAD_OUT) -> tuple[Path, ...]:
    """Every file the traveler task writes: the HTML sheets, then the PDF,
    then a family's placeholder HTML and PDF for each part."""
    return (
        *traveler_paths(stem, out),
        traveler_pdf_path(stem, out),
        *(path for pair in placeholder_paths(stem, out).values() for path in pair),
    )


# One enrolled plan per part: a family's parts have no plan of their own.
_served = [part for stem in TRAVELER_STEMS for part in part_stems(stem)]
if _twice := sorted({part for part in _served if _served.count(part) > 1}):
    raise ValueError(f"parts served by more than one enrolled plan: {_twice}")
