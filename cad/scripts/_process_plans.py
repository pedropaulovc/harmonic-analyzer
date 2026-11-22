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
"""

from __future__ import annotations

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


def family_plan_path(name: str) -> Path:
    """TRIAL (owner 2026-11-22): one shared plan for several near-twin parts,
    ``families/<name>/plan.toml``. A level below the ``<stem>/plan.toml`` glob,
    so it enrols no stem, has no task and ships nothing; only
    ``prechips_traveler.py --family <name>`` reads it."""
    return PROCESS_ROOT / "families" / name / "plan.toml"


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


def traveler_outputs(stem: str, out: Path = CAD_OUT) -> tuple[Path, ...]:
    """Every file the traveler task writes: the HTML sheets, then the PDF."""
    return (*traveler_paths(stem, out), traveler_pdf_path(stem, out))
