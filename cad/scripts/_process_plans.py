"""Locate prechips process plans and their generated travelers.

Each enrolled part has an authored ``cad/process/<stem>/plan.toml`` that the
latest prechips release renders on request (``prechips_traveler.py``), with the
shared ``cad/process/shop.toml``, into two standalone HTML travelers under
``cad/out/travelers/<stem>/``: the concise ``pro`` sheet and the ``hobby``
sheet with its setup pictures. Builds and releases do not render or ship them.
"""

from __future__ import annotations

from pathlib import Path

from export_features import OUT as CAD_OUT

TRAVELER_STEMS: tuple[str, ...] = (
    "ch_rocker_arm_tl_oblique_base_bar",
    "ch_rocker_arm_tl_oblique_end_bracket",
    "ch_rocker_arm_tl_oblique_feed_lever",
    "ch_rocker_arm_tl_oblique_riser",
    "ch_rocker_arm_tl_oblique_carrier",
)
PROCESS_ROOT = Path(__file__).resolve().parents[1] / "process"
SHOP_PATH = PROCESS_ROOT / "shop.toml"
# Each traveler file and the built-in prechips profile it is rendered with,
# from the same plan; ``pro`` first.
TRAVELER_PROFILES: dict[str, str] = {
    "traveler.html": "pro",
    "traveler-hobby.html": "hobby",
}


def plan_path(stem: str) -> Path:
    return PROCESS_ROOT / stem / "plan.toml"


def traveler_dir(stem: str, out: Path = CAD_OUT) -> Path:
    return Path(out) / "travelers" / stem


def traveler_paths(stem: str, out: Path = CAD_OUT) -> tuple[Path, ...]:
    """The part's traveler files, in ``TRAVELER_PROFILES`` order."""
    return tuple(traveler_dir(stem, out) / name for name in TRAVELER_PROFILES)
