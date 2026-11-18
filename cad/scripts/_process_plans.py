"""Locate prechips process plans and their generated travelers.

Each enrolled part has an authored ``cad/process/<stem>/plan.toml`` that the
latest prechips release renders (``prechips_traveler.py``), with the shared
``cad/process/shop.toml``, into two standalone HTML travelers under
``cad/out/travelers/<stem>/``: the concise ``pro`` sheet and the ``hobby``
sheet with its setup pictures. The hobby sheet is also printed to
``<slug>-traveler.pdf`` beside them. ``build`` and ``release`` render every
enrolled part (``build_bare`` none); ``release`` ships those PDFs under the
bundle's ``travelers/``.
"""

from __future__ import annotations

from pathlib import Path

from export_features import OUT as CAD_OUT

# The parts with a traveler, enrolled by the CNC migration. The rocker strap
# is the first (2026-11-17), then the magnifying clamp.
TRAVELER_STEMS: tuple[str, ...] = ("ch_rocker_strap", "mg_magnifying_clamp")
PROCESS_ROOT = Path(__file__).resolve().parents[1] / "process"
SHOP_PATH = PROCESS_ROOT / "shop.toml"
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
