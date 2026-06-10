r"""Reproduction script: pinion gear drum (book ch. 25, pp. 66-69).

A single long toothed drum (42 teeth, ~150 mm) that meshes the whole cylinder
gear set at once -- engaged via a small ball-handle lever during setup to turn
all 20 cylinder gears together and align their 3 mm notches (top = cosine,
rotated 90 deg = sine).

Same gear system as the cone/cylinder sets (DP 30, PA 14.5 deg -- the tip-
radius ratio to the meshing 120T cylinder gear confirms the common DP); the
tooth ring reuses the cone gear's live-validated equation-curve technique at
fixed N = 42 (literal numeric expressions, document units = inches, radians).

No bore/mounting is modeled: the book gives no bore data and the drum mounts
through the setup-lever pivot hardware, which is authored with the other
Phase-3-dependent parts (plan M4d) -- same deferral pattern as the cone-gear
stepped shaft (DIMENSIONS.md Appendix C #7).

Dimensions: cad/DIMENSIONS.md "Chapter 25".

Layout: drum axis = Z through the origin, drum z = 0..150 mm.

Run (SolidWorks already open)::

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\build_pinion_drum.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    IN,
    apply_material,
    check,
    define_circle,
    ensure_fully_defined,
    report_mass_properties,
    run_build,
    save_part_and_images,
)
from build_cone_gear import R_CLEAR_IN, gap_area_in_disc, gear_facts
from build_cylinder_gear import equation_curve, fmt, volume_check

PART_NAME = "pinion-drum"
MATERIAL = "Brass"  # ch. 25 photos: brass drum

TEETH = 42  # DIMENSIONS.md ch25: counted, frame v4_pinion_018 (high)
DRUM_LENGTH = 150.0  # mm, ch25: spans the 20 x 7.5 mm cylinder stack (med)

FACTS = gear_facts(TEETH)  # inches; OD (42+2)/30 = 1.467" (high)
RA_MM = FACTS["Ra"] * IN  # 18.627


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import (
        CircularPatternParameters,
        CreateAxisParameters,
        ExtrusionParameters,
    )

    check("create_part", await adapter.create_part())

    # Drum blank: disc at tip radius, z = 0..DRUM_LENGTH.
    check("create_sketch blank", await adapter.create_sketch("Front"))
    await define_circle(adapter, 0.0, 0.0, RA_MM, "drum blank")
    await ensure_fully_defined(adapter, "blank sketch")
    check("exit_sketch blank", await adapter.exit_sketch())
    check(
        "extrude blank",
        await adapter.create_extrusion(ExtrusionParameters(depth=DRUM_LENGTH)),
    )
    v_blank = math.pi * RA_MM**2 * DRUM_LENGTH
    await volume_check(adapter, "blank", v_blank, 0.005 * v_blank)

    # One tooth gap (six equation curves, see build_cone_gear's derivation).
    rb, ra = fmt(FACTS["Rb"]), fmt(FACTS["Ra"])
    th_l, th_u = fmt(FACTS["ThetaL"]), fmt(FACTS["ThetaU"])
    rc = fmt(R_CLEAR_IN)
    u = f"({fmt(FACTS['Tmax'])} * t)"
    ph_low = f"({u} - {fmt(FACTS['Delta'])})"
    ph_up = f"({u} + {fmt(FACTS['Gamma'] - FACTS['Delta'])})"
    a1, a2 = FACTS["Delta"], FACTS["Gamma"] - FACTS["Delta"]
    check("create_sketch gap", await adapter.create_sketch("Front"))
    gap_curves = [
        await equation_curve(
            adapter,
            "lower flank (tooth 0 upper, mirrored involute)",
            f"{rb} * (cos{ph_low} + {u} * sin{ph_low})",
            f"{rb} * ({u} * cos{ph_low} - sin{ph_low})",
        ),
        await equation_curve(
            adapter,
            "upper flank (tooth 1 lower involute)",
            f"{rb} * (cos{ph_up} + {u} * sin{ph_up})",
            f"{rb} * (sin{ph_up} - {u} * cos{ph_up})",
        ),
        await equation_curve(
            adapter,
            "base chord A2->A1",
            f"{rb} * ((1 - t) * {fmt(math.cos(a2))} + t * {fmt(math.cos(a1))})",
            f"{rb} * ((1 - t) * {fmt(math.sin(a2))} + t * {fmt(math.sin(a1))})",
        ),
        await equation_curve(
            adapter,
            "lower radial extension B1->clearance",
            f"({ra} + t * ({rc} - {ra})) * {fmt(math.cos(FACTS['ThetaL']))}",
            f"({ra} + t * ({rc} - {ra})) * {fmt(math.sin(FACTS['ThetaL']))}",
        ),
        await equation_curve(
            adapter,
            "outer clearance arc",
            f"{rc} * cos({th_l} + t * ({th_u} - {th_l}))",
            f"{rc} * sin({th_l} + t * ({th_u} - {th_l}))",
        ),
        await equation_curve(
            adapter,
            "upper radial extension clearance->B2",
            f"({rc} + t * ({ra} - {rc})) * {fmt(math.cos(FACTS['ThetaU']))}",
            f"({rc} + t * ({ra} - {rc})) * {fmt(math.sin(FACTS['ThetaU']))}",
        ),
    ]
    await ensure_fully_defined(adapter, "gap sketch", fix_entities=gap_curves)
    check("exit_sketch gap", await adapter.exit_sketch())
    gap_cut = await adapter.create_cut_extrude(
        ExtrusionParameters(depth=DRUM_LENGTH + 1.0)
    )
    check("cut tooth gap", gap_cut)

    # Pattern the gap 42x about Z (axis-candidate walk, see build_cone_gear).
    check(
        "create_axis Z (Top x Right)",
        await adapter.create_axis(
            CreateAxisParameters(mode="two_planes", planes=["Top Plane", "Right Plane"])
        ),
    )
    adapter._zoom_to_fit(adapter.currentModel)
    candidates = [[0.0, 0.0, DRUM_LENGTH / 2.0]]
    for angle_deg in (-45.0, -90.0, -135.0, 135.0, 45.0):
        a = math.radians(angle_deg)
        candidates.append(
            [RA_MM * math.cos(a), RA_MM * math.sin(a), DRUM_LENGTH / 2.0]
        )
    pattern = None
    for point in candidates:
        res = await adapter.circular_pattern_feature(
            CircularPatternParameters(
                axis_point=point,
                features=[gap_cut.data.name],
                count=TEETH,
            )
        )
        if res.is_success:
            pattern = res
            print(f"  OK  circular pattern axis via point {point}")
            break
        print(f"  ..  axis candidate {point} failed: {res.error}")
    if pattern is None:
        raise RuntimeError("circular pattern: no axis candidate selectable")

    v_drum = v_blank - TEETH * gap_area_in_disc(TEETH) * IN**2 * DRUM_LENGTH
    await volume_check(adapter, "toothed drum", v_drum, 0.01 * v_drum)

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
