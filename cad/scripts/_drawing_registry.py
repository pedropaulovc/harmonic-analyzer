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
    DrawingSpec(
        name="pen_v_block",
        part="pen_v_block",
        artifact_stem="pen-v-block",
        script_name="draw_pen_v_block.py",
    ),
    DrawingSpec(
        name="crank_pin",
        part="crank_pin",
        artifact_stem="crank-pin",
        script_name="draw_crank_pin.py",
    ),
    DrawingSpec(
        name="pen_rod",
        part="pen_rod",
        artifact_stem="pen-rod",
        script_name="draw_pen_rod.py",
    ),
    DrawingSpec(
        name="magnifying_lever",
        part="magnifying_lever",
        artifact_stem="magnifying-lever",
        script_name="draw_magnifying_lever.py",
    ),
    DrawingSpec(
        name="magnifying_vertical_rod",
        part="magnifying_vertical_rod",
        artifact_stem="magnifying-vertical-rod",
        script_name="draw_magnifying_vertical_rod.py",
    ),
    DrawingSpec(
        name="magnifying_clamp",
        part="magnifying_clamp",
        artifact_stem="magnifying-clamp",
        script_name="draw_magnifying_clamp.py",
    ),
    DrawingSpec(
        name="knife_mount",
        part="knife_mount",
        artifact_stem="knife-mount",
        script_name="draw_knife_mount.py",
    ),
    DrawingSpec(
        name="wheel_bar",
        part="wheel_bar",
        artifact_stem="wheel-bar",
        script_name="draw_wheel_bar.py",
    ),
    DrawingSpec(
        name="magnifying_wheel",
        part="magnifying_wheel",
        artifact_stem="magnifying-wheel",
        script_name="draw_magnifying_wheel.py",
    ),
    DrawingSpec(
        name="magnifying_bracket",
        part="magnifying_bracket",
        artifact_stem="magnifying-bracket",
        script_name="draw_magnifying_bracket.py",
    ),
    DrawingSpec(
        name="lever_wire",
        part="lever_wire",
        artifact_stem="lever-wire",
        script_name="draw_lever_wire.py",
    ),
    DrawingSpec(
        name="rocker_arm",
        part="rocker_arm",
        artifact_stem="rocker-arm",
        script_name="draw_rocker_arm.py",
    ),
    DrawingSpec(
        name="connecting_rod",
        part="connecting_rod",
        artifact_stem="connecting-rod",
        script_name="draw_connecting_rod.py",
    ),
    DrawingSpec(
        name="channel_lever",
        part="channel_lever",
        artifact_stem="channel-lever",
        script_name="draw_channel_lever.py",
    ),
    DrawingSpec(
        name="amplitude_bar",
        part="amplitude_bar",
        artifact_stem="amplitude-bar",
        script_name="draw_amplitude_bar.py",
    ),
    DrawingSpec(
        name="counter_spring",
        part="counter_spring",
        artifact_stem="counter-spring",
        script_name="draw_counter_spring.py",
    ),
    DrawingSpec(
        name="channel_spring_installed",
        part="channel_spring_installed",
        artifact_stem="channel-spring-installed",
        script_name="draw_channel_spring_installed.py",
    ),
    DrawingSpec(
        name="spring_hook",
        part="spring_hook",
        artifact_stem="spring-hook",
        script_name="draw_spring_hook.py",
    ),
    DrawingSpec(
        name="summing_lever",
        part="summing_lever",
        artifact_stem="summing-lever",
        script_name="draw_summing_lever.py",
    ),
    DrawingSpec(
        name="boss_hook",
        part="boss_hook",
        artifact_stem="boss-hook",
        script_name="draw_boss_hook.py",
    ),
    DrawingSpec(
        name="output_fixture",
        part="output_fixture",
        artifact_stem="output-fixture",
        script_name="draw_output_fixture.py",
    ),
    DrawingSpec(
        name="pen_frame",
        part="pen_frame",
        artifact_stem="pen-frame",
        script_name="draw_pen_frame.py",
    ),
    DrawingSpec(
        name="pen_hanger",
        part="pen_hanger",
        artifact_stem="pen-hanger",
        script_name="draw_pen_hanger.py",
    ),
    DrawingSpec(
        name="pen_wire",
        part="pen_wire",
        artifact_stem="pen-wire",
        script_name="draw_pen_wire.py",
    ),
    DrawingSpec(
        name="gooseneck",
        part="gooseneck",
        artifact_stem="gooseneck",
        script_name="draw_gooseneck.py",
    ),
    DrawingSpec(
        name="gooseneck_clamp",
        part="gooseneck_clamp",
        artifact_stem="gooseneck-clamp",
        script_name="draw_gooseneck_clamp.py",
    ),
    DrawingSpec(
        name="measuring_stick",
        part="measuring_stick",
        artifact_stem="measuring-stick",
        script_name="draw_measuring_stick.py",
    ),
    DrawingSpec(
        name="cylinder_gear",
        part="cylinder_gear",
        artifact_stem="cylinder-gear",
        script_name="draw_cylinder_gear.py",
    ),
    DrawingSpec(
        name="cone_gear",
        part="cone_gear",
        artifact_stem="cone-gear",
        script_name="draw_cone_gear.py",
    ),
    DrawingSpec(
        name="crank_drive_gear",
        part="crank_drive_gear",
        artifact_stem="crank-drive-gear",
        script_name="draw_crank_drive_gear.py",
    ),
    DrawingSpec(
        name="crank_pinion",
        part="crank_pinion",
        artifact_stem="crank-pinion",
        script_name="draw_crank_pinion.py",
    ),
    DrawingSpec(
        name="alignment_pinion",
        part="alignment_pinion",
        artifact_stem="alignment-pinion",
        script_name="draw_alignment_pinion.py",
    ),
    DrawingSpec(
        name="rack_pinion",
        part="rack_pinion",
        artifact_stem="rack-pinion",
        script_name="draw_rack_pinion.py",
    ),
    DrawingSpec(
        name="transgear_feed_pinion",
        part="transgear_feed_pinion",
        artifact_stem="transgear-feed-pinion",
        script_name="draw_transgear_feed_pinion.py",
    ),
    DrawingSpec(
        name="transgear_pinion",
        part="transgear_pinion",
        artifact_stem="transgear-pinion",
        script_name="draw_transgear_pinion.py",
    ),
    DrawingSpec(
        name="crankshaft",
        part="crankshaft",
        artifact_stem="crankshaft",
        script_name="draw_crankshaft.py",
    ),
    DrawingSpec(
        name="harmonic_base",
        part="harmonic_base",
        artifact_stem="harmonic-base",
        script_name="draw_harmonic_base.py",
    ),
    DrawingSpec(
        name="top_frame",
        part="top_frame",
        artifact_stem="top-frame",
        script_name="draw_top_frame.py",
    ),
    DrawingSpec(
        name="tube_frame",
        part="tube_frame",
        artifact_stem="tube-frame",
        script_name="draw_tube_frame.py",
    ),
    DrawingSpec(
        name="cone_swing_platform",
        part="cone_swing_platform",
        artifact_stem="cone-swing-platform",
        script_name="draw_cone_swing_platform.py",
    ),
    DrawingSpec(
        name="fillister_screw",
        part="fillister_screw",
        artifact_stem="fillister-screw",
        script_name="draw_fillister_screw.py",
    ),
    DrawingSpec(
        name="foot_screw",
        part="foot_screw",
        artifact_stem="foot-screw",
        script_name="draw_foot_screw.py",
    ),
    DrawingSpec(
        name="bracket_screw",
        part="bracket_screw",
        artifact_stem="bracket-screw",
        script_name="draw_bracket_screw.py",
    ),
    DrawingSpec(
        name="clamp_screw",
        part="clamp_screw",
        artifact_stem="clamp-screw",
        script_name="draw_clamp_screw.py",
    ),
    DrawingSpec(
        name="slotted_screw",
        part="slotted_screw",
        artifact_stem="slotted-screw",
        script_name="draw_slotted_screw.py",
    ),
    DrawingSpec(
        name="lag_screw",
        part="lag_screw",
        artifact_stem="lag-screw",
        script_name="draw_lag_screw.py",
    ),
    DrawingSpec(
        name="cone_pivot_screw",
        part="cone_pivot_screw",
        artifact_stem="cone-pivot-screw",
        script_name="draw_cone_pivot_screw.py",
    ),
    DrawingSpec(
        name="cone_tip_pinch_screw",
        part="cone_tip_pinch_screw",
        artifact_stem="cone-tip-pinch-screw",
        script_name="draw_cone_tip_pinch_screw.py",
    ),
    DrawingSpec(
        name="hanger_screw",
        part="hanger_screw",
        artifact_stem="hanger-screw",
        script_name="draw_hanger_screw.py",
    ),
    DrawingSpec(
        name="hex_bolt",
        part="hex_bolt",
        artifact_stem="hex-bolt",
        script_name="draw_hex_bolt.py",
    ),
    DrawingSpec(
        name="pen_set_screw",
        part="pen_set_screw",
        artifact_stem="pen-set-screw",
        script_name="draw_pen_set_screw.py",
    ),
    DrawingSpec(
        name="swing_stop_screw",
        part="swing_stop_screw",
        artifact_stem="swing-stop-screw",
        script_name="draw_swing_stop_screw.py",
    ),
    DrawingSpec(
        name="thumb_screw",
        part="thumb_screw",
        artifact_stem="thumb-screw",
        script_name="draw_thumb_screw.py",
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

