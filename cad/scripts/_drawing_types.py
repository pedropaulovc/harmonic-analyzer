"""Shared drawing types: templates, layouts, the row schema and report paths.

Kept apart from the row table in ``_drawing_registry``: helpers that need only
these types (``_drawing_common``, the layout audit/collect, the purchased and
supplier sheet helpers) import this module, so adding or editing one registry
row cannot re-key every drawing that reaches them.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path


SCRIPTS_DIR = Path(__file__).resolve().parent
CAD_ROOT = SCRIPTS_DIR.parent
TEMPLATES_DIR = CAD_ROOT / "templates"
# Each drawing's layout-audit report (``_drawing_layout_audit``): a declared
# drawing-task target, so it rides the remote cache with the sheet it audits.
LAYOUT_REPORT_DIR = CAD_ROOT / "out" / "reports" / "layout-audit"


def layout_report_path(artifact_stem: str) -> Path:
    return LAYOUT_REPORT_DIR / f"{artifact_stem}.json"


class DrawingLayout(StrEnum):
    LANDSCAPE = "landscape"
    PORTRAIT = "portrait"


@dataclass(frozen=True)
class DrawingTemplateSpec:
    path: Path
    width_m: float
    height_m: float
    dpi: int
    pixel_size: tuple[int, int]
    title_block_left_m: float
    title_block_top_m: float


# Hand-made in SolidWorks (title block, tolerance block, embedded ASME B sheet
# format) -- NOT generated; see cad/templates/README.md. Both orientations embed
# their own sheet formats, so there are no separate .slddrt runtime dependencies.
DRAWING_TEMPLATES = {
    DrawingLayout.LANDSCAPE: DrawingTemplateSpec(
        path=TEMPLATES_DIR / "harmonic-analyzer-landscape.DRWDOT",
        width_m=0.4318,
        height_m=0.2794,
        dpi=300,
        pixel_size=(5100, 3300),
        title_block_left_m=0.216,
        title_block_top_m=0.066,
    ),
    DrawingLayout.PORTRAIT: DrawingTemplateSpec(
        path=TEMPLATES_DIR / "harmonic-analyzer-portrait.DRWDOT",
        width_m=0.2794,
        height_m=0.4318,
        dpi=300,
        pixel_size=(3300, 5100),
        title_block_left_m=0.0636,
        title_block_top_m=0.066,
    ),
}


@dataclass(frozen=True)
class DrawingSpec:
    name: str
    part: str
    artifact_stem: str
    script_name: str
    layout: DrawingLayout
    # "part" (default) draws a cad/out/sldprt SLDPRT; "assembly" draws the
    # cad/out/sldasm SLDASM of the assembly build named by ``part``.
    source_kind: str = "part"
    additional_layouts: tuple[DrawingLayout, ...] = ()

    @property
    def script(self) -> Path:
        return SCRIPTS_DIR / self.script_name

    @property
    def source(self) -> Path:
        """The authoritative CAD model this drawing documents.

        Build scripts emit dashed artefact names (``ch_fulcrum_shaft`` ->
        ``ch-fulcrum-shaft.SLDPRT``, ``pn_pen`` -> ``pn-pen.SLDASM``), so the source stem
        is the dashed ``part``.
        """
        stem = self.part.replace("_", "-")
        if self.source_kind == "assembly":
            return CAD_ROOT / "out" / "sldasm" / f"{stem}.SLDASM"
        return CAD_ROOT / "out" / "sldprt" / f"{stem}.SLDPRT"

    @property
    def outputs(self) -> dict[str, Path]:
        return {
            "slddrw": CAD_ROOT / "out" / "slddrw" / f"{self.artifact_stem}.SLDDRW",
            "pdf": CAD_ROOT / "out" / "pdf" / f"{self.artifact_stem}.pdf",
            "png": CAD_ROOT / "out" / "png" / f"{self.artifact_stem}_drawing.png",
        }

    @property
    def layout_report(self) -> Path:
        """The layout-audit report: a task target, but not a release output."""
        return layout_report_path(self.artifact_stem)

    @property
    def assets(self) -> tuple[Path, ...]:
        layouts = dict.fromkeys((self.layout, *self.additional_layouts))
        return tuple(DRAWING_TEMPLATES[layout].path for layout in layouts)
