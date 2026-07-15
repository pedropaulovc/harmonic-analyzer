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
TEMPLATES_DIR = CAD_ROOT / "templates"
# Hand-made in SolidWorks (title block, tolerance block, embedded ASME B sheet
# format) -- NOT generated; see cad/templates/README.md. The template
# embeds its own sheet format, so there is no separate .slddrt.
PROJECT_DRWDOT = TEMPLATES_DIR / "harmonic-analyzer.DRWDOT"


@dataclass(frozen=True)
class DrawingSpec:
    name: str
    part: str
    artifact_stem: str
    script_name: str
    # "part" (default) draws a cad/out/sldprt SLDPRT; "assembly" draws the
    # cad/out/sldasm SLDASM of the assembly build named by ``part``.
    source_kind: str = "part"

    @property
    def script(self) -> Path:
        return SCRIPTS_DIR / self.script_name

    @property
    def source(self) -> Path:
        """The authoritative CAD model this drawing documents.

        Build scripts emit dashed artefact names (``fulcrum_shaft`` ->
        ``fulcrum-shaft.SLDPRT``, ``pen`` -> ``pen.SLDASM``), so the source stem
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
    def assets(self) -> tuple[Path, ...]:
        return (PROJECT_DRWDOT,)


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
        name="cone_tip_bushing",
        part="cone_tip_bushing",
        artifact_stem="cone-tip-bushing",
        script_name="draw_cone_tip_bushing.py",
    ),
    DrawingSpec(
        name="pivot_bushing",
        part="pivot_bushing",
        artifact_stem="pivot-bushing",
        script_name="draw_pivot_bushing.py",
    ),
    DrawingSpec(
        name="fulcrum_shaft",
        part="fulcrum_shaft",
        artifact_stem="fulcrum-shaft",
        script_name="draw_fulcrum_shaft.py",
    ),
    DrawingSpec(
        name="pivot_shaft",
        part="pivot_shaft",
        artifact_stem="pivot-shaft",
        script_name="draw_pivot_shaft.py",
    ),
    DrawingSpec(
        name="top_crossbar",
        part="top_crossbar",
        artifact_stem="top-crossbar",
        script_name="draw_top_crossbar.py",
    ),
    DrawingSpec(
        name="pen_assembly",
        part="pen",
        artifact_stem="pen-assembly",
        script_name="draw_pen_assembly.py",
        source_kind="assembly",
    ),
    DrawingSpec(
        name="pinion_lift_rod",
        part="pinion_lift_rod",
        artifact_stem="pinion-lift-rod",
        script_name="draw_pinion_lift_rod.py",
    ),
    DrawingSpec(
        name="cylinder_gear_shaft",
        part="cylinder_gear_shaft",
        artifact_stem="cylinder-gear-shaft",
        script_name="draw_cylinder_gear_shaft.py",
    ),
    DrawingSpec(
        name="cone_lock_knob",
        part="cone_lock_knob",
        artifact_stem="cone-lock-knob",
        script_name="draw_cone_lock_knob.py",
    ),
    DrawingSpec(
        name="pinion_arbor",
        part="pinion_arbor",
        artifact_stem="pinion-arbor",
        script_name="draw_pinion_arbor.py",
    ),
    DrawingSpec(
        name="pen_marker",
        part="pen_marker",
        artifact_stem="pen-marker",
        script_name="draw_pen_marker.py",
    ),
    DrawingSpec(
        name="transgear_stub",
        part="transgear_stub",
        artifact_stem="transgear-stub",
        script_name="draw_transgear_stub.py",
    ),
    DrawingSpec(
        name="guide_lock",
        part="guide_lock",
        artifact_stem="guide-lock",
        script_name="draw_guide_lock.py",
    ),
    DrawingSpec(
        name="wheel_axle",
        part="wheel_axle",
        artifact_stem="wheel-axle",
        script_name="draw_wheel_axle.py",
    ),
    DrawingSpec(
        name="column_clamp_front",
        part="column_clamp_front",
        artifact_stem="column-clamp-front",
        script_name="draw_column_clamp_front.py",
    ),
    DrawingSpec(
        name="pinion_pivot_block",
        part="pinion_pivot_block",
        artifact_stem="pinion-pivot-block",
        script_name="draw_pinion_pivot_block.py",
    ),
)

DRAWINGS_BY_NAME = {drawing.name: drawing for drawing in DRAWINGS}

if len(DRAWINGS_BY_NAME) != len(DRAWINGS):
    raise RuntimeError("drawing registry contains duplicate task names")

for _drawing in DRAWINGS:
    if _drawing.source_kind not in ("part", "assembly"):
        raise RuntimeError(
            f"drawing {_drawing.name!r} has unknown source_kind "
            f"{_drawing.source_kind!r}"
        )

