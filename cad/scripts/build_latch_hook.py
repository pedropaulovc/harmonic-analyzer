r"""Reproduction script: transgear latch hook (book ch. 23 pp. 58-63; video 4/4).

The "small latch that allows the operator to disengage the gearing from the
platen" (ch23 text; p.58 "latch" callout; engineerguy 4/4 keyframes
v4_transgear_001 latched / _011 unlatched): NOT a long straight strip with
an eye (the 2026-09 first pass) but a SHORT CURVED SPRING-STEEL HOOK hanging
from the platen support bar's front face, screwed at its top and curving
down-and-inward toward the transgear disc, free at the bottom. The flex is
not modelled: the hook is shown at rest. In the video it hangs between the
rocker pivot ball and the disc (machine x ~ +52) from a bar front exposed
~12 mm below the platen's bottom edge; in this model the bar sits 22.5
ABOVE the platen bottom, hidden behind it, so the paper-drive assembly
hangs the hook beside the platen's -X edge instead (see LATCH_HOOK_X there
for the discrepancy and the edits that restore the photo pose).

Layout (part frame, sketch on the Front plane): screw-hole centre at the
origin; the strip's centreline is one arc of radius BEND_R starting tangent
to -Y at the origin and bending toward -X, of arc length ARC_LEN -- so the
free end sits ~25.4 below the screw with ~7.9 of inward run (R45 x 27 of
arc; the "27 below / 6 in" photo read is the chord of that bend). The strip
is STRIP_W wide (offset both sides of the centreline), full-round at the
free end (TIP_R) and rounded into a Ø EYE_DIA eye about the Ø HOLE_DIA screw
hole at the top: a 4.5-wide strip cannot carry a Ø4.4 hole, so the top is
blanked as a wider eye like the strip it replaced. Thickness STRIP_T,
extruded +Z from z = 0.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_latch_hook.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    POLISHED_STEEL,
    SketchDims,
    anchor_point_to_origin,
    apply_color,
    apply_material,
    check,
    define_circle,
    drive_dimension,
    ensure_fully_defined,
    force_rebuild,
    name_last_feature,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_global,
    set_sketch_direct_db,
    volume_check,
)

PART_NAME = "latch-hook"
MATERIAL = "Plain Carbon Steel"  # bright spring steel (p.58, video 4/4)

STRIP_W = 4.5  # keyframe v4_transgear_001: a narrow blade beside the disc
STRIP_T = 0.8  # spring strip
BEND_R = 45.0  # centreline bend radius
ARC_LEN = 27.0  # centreline length screw -> free tip (chord ~26.6)
EYE_DIA = 8.0  # round eye about the screw hole (1.8 wall around Ø4.4)
HOLE_DIA = 4.4  # #8 bracket-screw clearance

TIP_R = STRIP_W / 2.0
OUTER_R = BEND_R + STRIP_W / 2.0
INNER_R = BEND_R - STRIP_W / 2.0
EYE_R = EYE_DIA / 2.0
SWEEP = ARC_LEN / BEND_R  # rad
BEND_C = (-BEND_R, 0.0)  # bend centre: the strip bends toward -X


def _path(t: float) -> tuple[float, float]:
    """Centreline point at arc parameter ``t`` (0 at the screw hole)."""
    return (-BEND_R + BEND_R * math.cos(t), -BEND_R * math.sin(t))


TIP_C = _path(SWEEP)  # free-end round centre (-7.86, -25.40)
_U = (math.cos(SWEEP), -math.sin(SWEEP))  # bend centre -> tip, unit
TIP_OUTER = (TIP_C[0] + TIP_R * _U[0], TIP_C[1] + TIP_R * _U[1])
TIP_INNER = (TIP_C[0] - TIP_R * _U[0], TIP_C[1] - TIP_R * _U[1])


def _eye_join(r_band: float) -> tuple[float, float]:
    """Lower intersection of the eye circle with a band circle of radius
    ``r_band`` about the bend centre (the eye/strip corner on that flank)."""
    x = (r_band**2 - EYE_R**2 - BEND_R**2) / (2.0 * BEND_R)
    return (x, -math.sqrt(EYE_R**2 - x * x))


EYE_OUTER = _eye_join(OUTER_R)  # (2.13, -3.39)
EYE_INNER = _eye_join(INNER_R)  # (-2.37, -3.22)


def _outline(n: int = 2000) -> list[tuple[float, float]]:
    """Dense sample of the closed outline (outer flank down, tip round, inner
    flank up, eye over the top) for the shoelace area."""
    pts: list[tuple[float, float]] = []
    a_o = math.atan2(EYE_OUTER[1] - BEND_C[1], EYE_OUTER[0] - BEND_C[0])
    a_i = math.atan2(EYE_INNER[1] - BEND_C[1], EYE_INNER[0] - BEND_C[0])
    a_tip = -SWEEP
    for k in range(n + 1):  # outer flank: eye join -> tip (clockwise about C)
        a = a_o + (a_tip - a_o) * k / n
        pts.append((BEND_C[0] + OUTER_R * math.cos(a), BEND_C[1] + OUTER_R * math.sin(a)))
    b0 = math.atan2(_U[1], _U[0])
    for k in range(1, n + 1):  # tip round: outer -> inner, clockwise about TIP_C
        b = b0 - math.pi * k / n
        pts.append((TIP_C[0] + TIP_R * math.cos(b), TIP_C[1] + TIP_R * math.sin(b)))
    for k in range(1, n + 1):  # inner flank: tip -> eye join (counter-clockwise)
        a = a_tip + (a_i - a_tip) * k / n
        pts.append((BEND_C[0] + INNER_R * math.cos(a), BEND_C[1] + INNER_R * math.sin(a)))
    e0 = math.atan2(EYE_INNER[1], EYE_INNER[0])
    e1 = math.atan2(EYE_OUTER[1], EYE_OUTER[0])
    eye_sweep = (e0 - e1) % (2.0 * math.pi)  # clockwise, over the top (~292 deg)
    for k in range(1, n + 1):  # eye: inner join over the top to the outer join
        e = e0 - eye_sweep * k / n
        pts.append((EYE_R * math.cos(e), EYE_R * math.sin(e)))
    return pts


def _area(pts: list[tuple[float, float]]) -> float:
    s = 0.0
    for (x0, y0), (x1, y1) in zip(pts, pts[1:] + pts[:1]):
        s += x0 * y1 - x1 * y0
    return abs(s) / 2.0


_OUTLINE = _outline()
PROFILE_AREA = _area(_OUTLINE)  # ~168 mm^2
V_STRIP = PROFILE_AREA * STRIP_T
V_HOLE = math.pi * (HOLE_DIA / 2.0) ** 2 * STRIP_T
V_TOTAL = V_STRIP - V_HOLE

# Extents (part frame) for the assembly's clearance asserts.
X_MIN = min(x for x, _ in _OUTLINE)
X_MAX = max(x for x, _ in _OUTLINE)
Y_MIN = min(y for _, y in _OUTLINE)
Y_MAX = EYE_R


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations). mm suffix load-bearing (INCH document).
    await set_global(adapter, "StripW", f"{STRIP_W}mm")
    await set_global(adapter, "StripT", f"{STRIP_T}mm")
    await set_global(adapter, "BendR", f"{BEND_R}mm")
    await set_global(adapter, "EyeDia", f"{EYE_DIA}mm")
    await set_global(adapter, "HoleDia", f"{HOLE_DIA}mm")

    drive_jobs: list[tuple[str, str]] = []

    # Outline: four arcs, direct-to-DB (the eye/flank corners and the tip
    # joins are exact coordinates, not inferred), constrained explicitly:
    # eye centred on the origin + radius; outer/inner flanks concentric on
    # the anchored bend centre + radii; tip round centred on the anchored
    # centreline end + radius; four coincident joins. 4 arcs x 5 DOF = 20 =
    # 3 + 3 + 3 + 3 + 8 -- fully defined without tangency relations (the tip
    # round is tangent to both flanks by construction).
    # add_arc runs COUNTER-CLOCKWISE from its first to its second point
    # (CreateArc with the explicit CCW flag, so the eye's ~292 deg MAJOR arc
    # over the top is drawn as such, not as its minor complement).
    hook = SketchDims()
    check("create_sketch hook", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    outer = check(
        "outer flank",
        await adapter.add_arc(*BEND_C, *TIP_OUTER, *EYE_OUTER),
    )
    eye = check("eye round", await adapter.add_arc(0.0, 0.0, *EYE_OUTER, *EYE_INNER))
    inner = check(
        "inner flank",
        await adapter.add_arc(*BEND_C, *TIP_INNER, *EYE_INNER),
    )
    tip = check("tip round", await adapter.add_arc(*TIP_C, *TIP_INNER, *TIP_OUTER))
    set_sketch_direct_db(adapter, False)
    for label, a, b in (
        ("outer-eye join", f"{outer}.end", f"{eye}.start"),
        ("eye-inner join", f"{eye}.end", f"{inner}.end"),
        ("inner-tip join", f"{inner}.start", f"{tip}.start"),
        ("tip-outer join", f"{tip}.end", f"{outer}.start"),
    ):
        check(label, await adapter.add_sketch_constraint(a, b, "coincident"))
    check(
        "eye centre on origin",
        await adapter.add_sketch_constraint(f"{eye}.center", "origin", "coincident"),
    )
    check("eye radius", await adapter.add_sketch_dimension(eye, None, "radial", EYE_R))
    hook.record("EyeR", '"EyeDia" / 2')
    await anchor_point_to_origin(adapter, f"{outer}.center", *BEND_C, "bend centre")
    hook.record("BendCx", '"BendR"')
    check("outer radius", await adapter.add_sketch_dimension(outer, None, "radial", OUTER_R))
    hook.record("OuterR", '"BendR" + "StripW" / 2')
    check(
        "inner concentric with outer",
        await adapter.add_sketch_constraint(f"{inner}.center", f"{outer}.center", "coincident"),
    )
    check("inner radius", await adapter.add_sketch_dimension(inner, None, "radial", INNER_R))
    hook.record("InnerR", '"BendR" - "StripW" / 2')
    # The tip centre is trig-derived from the sweep: literal dims (no trig
    # equations -- the equation manager rejects several dim bindings).
    await anchor_point_to_origin(adapter, f"{tip}.center", *TIP_C, "tip centre")
    hook.record("TipCx")
    hook.record("TipCy")
    check("tip radius", await adapter.add_sketch_dimension(tip, None, "radial", TIP_R))
    hook.record("TipR", '"StripW" / 2')
    await ensure_fully_defined(adapter, "hook sketch")
    check("exit_sketch hook", await adapter.exit_sketch())
    name_last_feature(adapter, "HookProfile")
    drive_jobs += hook.apply(adapter, "HookProfile")
    check(
        "extrude hook",
        await adapter.create_extrusion(ExtrusionParameters(depth=STRIP_T)),
    )
    name_last_feature(adapter, "Hook")
    drive_jobs.append(("D1@Hook", '"StripT"'))
    expected = V_STRIP
    await volume_check(adapter, "hook strip", expected, 0.01 * V_STRIP)

    # Screw clearance hole through the eye (origin), cut both ways.
    hole = SketchDims()
    check("create_sketch hole", await adapter.create_sketch("Front"))
    await define_circle(
        adapter, 0.0, 0.0, HOLE_DIA / 2.0, "screw hole",
        dims=hole, names=("HoleCx", "HoleCz", "ScrewHoleDia"),
        drives=(None, None, '"HoleDia"'),
    )
    await ensure_fully_defined(adapter, "hole sketch")
    check("exit_sketch hole", await adapter.exit_sketch())
    name_last_feature(adapter, "HoleProfile")
    drive_jobs += hole.apply(adapter, "HoleProfile")
    check(
        "cut hole",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=2.0 * STRIP_T + 2.0, both_directions=True)
        ),
    )
    name_last_feature(adapter, "ScrewHole")
    expected -= V_HOLE
    await volume_check(adapter, "screw hole", expected, 0.02 * V_HOLE)

    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(adapter, "driven hook (equations neutral)", expected, 0.005 * expected)

    await apply_material(adapter, MATERIAL)
    await apply_color(adapter, POLISHED_STEEL)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
