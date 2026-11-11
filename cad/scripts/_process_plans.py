"""Locate prechips process plans and their generated travelers.

Each enrolled part has an authored ``cad/process/<stem>/plan.toml`` that the
installed prechips CLI renders, with the shared ``cad/process/shop.toml``, into
two standalone HTML travelers under ``cad/out/travelers/<stem>/``: the concise
``pro`` sheet and the ``hobby`` sheet with its setup pictures.
"""

from __future__ import annotations

import shutil
import tomllib
from pathlib import Path

from export_features import OUT as CAD_OUT, bundle_paths

# The feed lever's plan (cad/process/ch_rocker_arm_tl_oblique_feed_lever/) is
# held unenrolled: prechips refuses its 11/32 drill below the drawing's hole
# band (cad/process/README.md).
TRAVELER_STEMS: tuple[str, ...] = (
    "ch_rocker_arm_tl_oblique_base_bar",
    "ch_rocker_arm_tl_oblique_end_bracket",
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


def traveler_complete(stem: str, out: Path = CAD_OUT) -> bool:
    return all(path.is_file() for path in traveler_paths(stem, out))


def traveler_header(stem: str, stage: Path) -> str:
    """The ``<drawing number>; <revision>`` line a traveler rendered from the
    staged manifest prints in its sheet header."""
    manifest, _step = bundle_paths(stem, stage)
    drawing = tomllib.loads(manifest.read_text(encoding="utf-8"))["drawing"]
    return f"{drawing['number']}; {drawing['revision']}"


def stage_travelers(out: Path, stage: Path) -> list[Path]:
    """Copy every enrolled part's travelers into the release stage.

    Refuses, before copying anything, when a traveler is missing or does not
    print its part's drawing number and revision from the manifest already
    staged under ``stage/features/<stem>/`` (a traveler left from an older
    export)."""
    import _telemetry

    with _telemetry.span("release.travelers_stage", stems=len(TRAVELER_STEMS)):
        missing = [
            str(path)
            for stem in TRAVELER_STEMS
            if not traveler_complete(stem, out)
            for path in traveler_paths(stem, out)
            if not path.is_file()
        ]
        if missing:
            raise FileNotFoundError(
                "enrolled travelers were not generated; run their prechips tasks: "
                + ", ".join(missing)
            )
        stale = []
        for stem in TRAVELER_STEMS:
            header = traveler_header(stem, stage)
            stale.extend(
                f"{path} (expected {header!r})"
                for path in traveler_paths(stem, out)
                if header not in path.read_text(encoding="utf-8")
            )
        if stale:
            raise ValueError(
                "travelers do not match the staged feature manifests; rerun their "
                "prechips tasks: " + ", ".join(stale)
            )
        staged = []
        for stem in TRAVELER_STEMS:
            target = traveler_dir(stem, stage)
            target.mkdir(parents=True, exist_ok=True)
            for path in traveler_paths(stem, out):
                shutil.copyfile(path, target / path.name)
            staged.append(target)
        return staged
