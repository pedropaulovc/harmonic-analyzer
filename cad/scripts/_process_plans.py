"""Locate prechips process plans and their generated travelers.

Each enrolled part has an authored ``cad/process/<stem>/plan.toml`` that the
installed prechips CLI renders, with the shared ``cad/process/shop.toml``, into
one standalone ``traveler.html`` under ``cad/out/travelers/<stem>/``.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from export_features import OUT as CAD_OUT

# The feed lever's plan (cad/process/ch_rocker_arm_tl_oblique_feed_lever/) is
# held unenrolled: prechips refuses its 11/32 drill below the drawing's hole
# band (cad/process/README.md).
TRAVELER_STEMS: tuple[str, ...] = (
    "ch_rocker_arm_tl_oblique_base_bar",
    "ch_rocker_arm_tl_oblique_end_bracket",
)
PROCESS_ROOT = Path(__file__).resolve().parents[1] / "process"
SHOP_PATH = PROCESS_ROOT / "shop.toml"
TRAVELER_NAME = "traveler.html"


def plan_path(stem: str) -> Path:
    return PROCESS_ROOT / stem / "plan.toml"


def traveler_dir(stem: str, out: Path = CAD_OUT) -> Path:
    return Path(out) / "travelers" / stem


def traveler_html(stem: str, out: Path = CAD_OUT) -> Path:
    return traveler_dir(stem, out) / TRAVELER_NAME


def traveler_complete(stem: str, out: Path = CAD_OUT) -> bool:
    return traveler_html(stem, out).is_file()


def stage_travelers(out: Path, stage: Path) -> list[Path]:
    """Copy every enrolled traveler into the release stage, failing on a missing one."""
    import _telemetry

    with _telemetry.span("release.travelers_stage", stems=len(TRAVELER_STEMS)):
        missing = [
            str(traveler_html(stem, out))
            for stem in TRAVELER_STEMS
            if not traveler_complete(stem, out)
        ]
        if missing:
            raise FileNotFoundError(
                "enrolled travelers were not generated; run their prechips tasks: "
                + ", ".join(missing)
            )
        staged = []
        for stem in TRAVELER_STEMS:
            target = traveler_html(stem, stage)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(traveler_html(stem, out), target)
            staged.append(target.parent)
        return staged
