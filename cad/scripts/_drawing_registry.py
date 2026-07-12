"""Declarative registry for curated manufacturing drawings.

The registry is intentionally data-only.  Each drawing has its own statically
importable recipe so changing one print cannot invalidate every other print.
Both ``dodo.py`` and ``cut_release.py`` consume this module, keeping build and
release artifact lists in lockstep as the book's drawing set grows.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


SCRIPTS_DIR = Path(__file__).resolve().parent
CAD_ROOT = SCRIPTS_DIR.parent
DRAWING_STANDARDS_DIR = CAD_ROOT / "standards" / "drawings"
ASME_B_DRWDOT = DRAWING_STANDARDS_DIR / "asme-b-book.DRWDOT"
ASME_B_SLDDRT = DRAWING_STANDARDS_DIR / "asme-b-book.slddrt"


@dataclass(frozen=True)
class DrawingSpec:
    name: str
    part: str
    artifact_stem: str
    script_name: str

    @property
    def script(self) -> Path:
        return SCRIPTS_DIR / self.script_name

    @property
    def outputs(self) -> dict[str, Path]:
        return {
            "slddrw": CAD_ROOT / "out" / "slddrw" / f"{self.artifact_stem}.SLDDRW",
            "pdf": CAD_ROOT / "out" / "pdf" / f"{self.artifact_stem}.pdf",
            "png": CAD_ROOT / "out" / "png" / f"{self.artifact_stem}_drawing.png",
        }

    @property
    def assets(self) -> tuple[Path, ...]:
        return (ASME_B_DRWDOT, ASME_B_SLDDRT)


DRAWINGS: tuple[DrawingSpec, ...] = (
    DrawingSpec(
        name="platen_guide",
        part="platen_guide",
        artifact_stem="platen-guide",
        script_name="draw_platen_guide.py",
    ),
    DrawingSpec(
        name="crank_arm",
        part="crank_arm",
        artifact_stem="crank-arm",
        script_name="draw_crank_arm.py",
    ),
    DrawingSpec(
        name="rocker_arm_support",
        part="rocker_arm_support",
        artifact_stem="rocker-arm-support",
        script_name="draw_rocker_arm_support.py",
    ),
    DrawingSpec(
        name="lever_bushing",
        part="lever_bushing",
        artifact_stem="lever-bushing",
        script_name="draw_lever_bushing.py",
    ),
    DrawingSpec(
        name="fulcrum_shaft",
        part="fulcrum_shaft",
        artifact_stem="fulcrum-shaft",
        script_name="draw_fulcrum_shaft.py",
    ),
    DrawingSpec(
        name="top_crossbar",
        part="top_crossbar",
        artifact_stem="top-crossbar",
        script_name="draw_top_crossbar.py",
    ),
)

DRAWINGS_BY_NAME = {drawing.name: drawing for drawing in DRAWINGS}

if len(DRAWINGS_BY_NAME) != len(DRAWINGS):
    raise RuntimeError("drawing registry contains duplicate task names")

