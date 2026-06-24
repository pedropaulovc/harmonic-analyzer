r"""Reproduction script: rocker-arm support (manual feature-tree replay).

An exact feature-tree replay of ``rocker-arm-support-manual.SLDPRT`` -- a
thin-walled cast bracket: a trapezoidal wedge (wide foot, narrow top) stood
**Z-up**, lightened by a square window that opens on the two slanted ±X faces,
with a mounting foot drilled by four tapped holes and the window rim broken by
a fillet + chamfer.

The original is hand-built; this rebuilds it feature-for-feature (matching the
seven-feature tree Boss-Extrude1 → Cut-Extrude2/3/4 → Fillet3 → Tapped Holes →
Chamfer2) rather than as a simplified parametric equivalent. Every cut profile
lives on the **Top plane** (sketch-y → model -Z) and extrudes along Y; the per-
stage ``volume_check`` targets are the real part's measured volumes, so any
geometry drift fails loudly:

    Boss-Extrude1 1 271 363 | Cut-Extrude2 622 708 | Cut-Extrude3 434 257
    Cut-Extrude4   245 806 | Fillet3      246 685 | Holes        243 665
    Chamfer2       240 512

Geometry (mm), all from the source part:

* **Boss** -- trapezoid, wide foot ``X ±31.75`` at ``Z=-88.9`` tapering to
  ``X ±8.4665`` at ``Z=+88.9``; mid-plane extrude 177.8 (``Y ±88.9``).
* **Cut-Extrude2** -- 127 mm square (``±63.5``), mid-plane depth 127 -> the
  central cavity, leaving 6.35 mm shell walls.
* **Cut-Extrude3 / 4** -- the −X then +X half of the 165.1 mm square
  (``±82.55``), mid-plane depth 165.1 -> the two side windows, leaving the
  central square-ring frame web at ``X ±3.175``.
* **Fillet3** -- R12.7 on the four inner-frame corner edges (concave: adds
  material).
* **Holes** -- 4× Ø12.3 tap-drill (9/16-12 tapped) up through the foot, on the
  Front plane at ``(±17.46, ±60.32)``.
* **Chamfer2** -- 1.27 mm / 45° on the 12 inner-frame opening edges plus the
  two slant faces, the two trapezoid faces, and one fillet face, with tangent
  propagation -- i.e. the whole window rim.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_rocker_arm_support_manual.py
"""

from __future__ import annotations

import sys

from _common import (
    add_line_chain,
    apply_material,
    check,
    name_last_feature,
    report_mass_properties,
    run_build,
    save_part_and_images,
    volume_check,
)

PART_NAME = "rocker-arm-support-manual"
MATERIAL = "AISI 1020 Steel, Cold Rolled"  # source part's database material

# Trapezoid (Sketch1) -- wide foot / narrow top, half-extents in mm.
WIDE = 31.75       # foot half-width (X) at Z=-88.9
NARROW = 8.4665    # top half-width (X) at Z=+88.9
HALF_Z = 88.9      # trapezoid half-height (Z)
BOSS_DEPTH = 177.8  # mid-plane extrude along Y (Y ±88.9)

CAV = 63.5         # 127 mm square half (Cut-Extrude2)
CAV_DEPTH = 127.0  # mid-plane cavity depth
BIG = 82.55        # 165.1 mm square half (Cut-Extrude3/4)
BIG_DEPTH = 165.1  # mid-plane window depth
WEB = 3.175        # central web half-thickness (X) left between the two windows

FILLET_R = 12.7
FILLET_EDGES = [  # four inner-frame corner edges (run along X through the web)
    [0.0, 63.5, 63.5], [0.0, -63.5, 63.5],
    [0.0, 63.5, -63.5], [0.0, -63.5, -63.5],
]

HOLE_DIA = 12.3    # 9/16-12 tap-drill diameter
HOLES = [(17.46, 60.32), (-17.46, 60.32), (17.46, -60.32), (-17.46, -60.32)]

CHAMFER = 1.27     # leg, 45°
CHAMFER_EDGES = [  # 12 inner-frame opening edges, both web faces (X = ±WEB)
    [-3.175, 0.0, -63.5], [-3.175, 63.5, 0.0], [-3.175, 59.78, 59.78],
    [-3.175, 0.0, 63.5], [-3.175, -63.5, 0.0], [-3.175, -59.78, -59.78],
    [3.175, 0.0, -63.5], [3.175, -59.78, -59.78], [3.175, -63.5, 0.0],
    [3.175, -59.78, 59.78], [3.175, 0.0, 63.5], [3.175, 63.5, 0.0],
]
CHAMFER_FACES = [  # whole faces whose every edge is chamfered (tangent-propagated)
    [31.24, 0.0, -85.0], [-31.24, 0.0, -85.0],  # ±X slant window surrounds
    [0.0, 88.9, 0.0], [0.0, -88.9, 0.0],        # front / back trapezoid faces
    [0.0, 59.78, -59.78],                        # one inner fillet face
]


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # 1. Boss: trapezoid on the Top plane (sketch-y -> model -Z, so the wide
    #    foot sits at Z=-88.9), mid-plane extruded 177.8 along Y.
    check("sketch boss", await adapter.create_sketch("Top"))
    await add_line_chain(adapter, [
        (-WIDE, HALF_Z), (WIDE, HALF_Z), (NARROW, -HALF_Z), (-NARROW, -HALF_Z),
    ])
    check("exit boss", await adapter.exit_sketch())
    name_last_feature(adapter, "Sketch1")
    check("boss", await adapter.create_extrusion(
        ExtrusionParameters(depth=BOSS_DEPTH, both_directions=True)))
    name_last_feature(adapter, "Boss-Extrude1")
    await volume_check(adapter, "Boss-Extrude1", 1_271_363, 200)

    # 2. Cut-Extrude2: 127 mm square, mid-plane 127 -> central cavity.
    check("sketch cut2", await adapter.create_sketch("Top"))
    await add_line_chain(adapter, [(-CAV, -CAV), (CAV, -CAV), (CAV, CAV), (-CAV, CAV)])
    check("exit cut2", await adapter.exit_sketch())
    name_last_feature(adapter, "Sketch2")
    check("cut2", await adapter.create_cut_extrude(
        ExtrusionParameters(depth=CAV_DEPTH, both_directions=True)))
    name_last_feature(adapter, "Cut-Extrude2")
    await volume_check(adapter, "Cut-Extrude2", 622_708, 200)

    # 3. Cut-Extrude3: −X half of the 165.1 mm square, mid-plane 165.1 -> left
    #    window (leaves the web at X=-WEB).
    check("sketch cut3", await adapter.create_sketch("Top"))
    await add_line_chain(adapter, [
        (-BIG, -BIG), (-WEB, -BIG), (-WEB, BIG), (-BIG, BIG)])
    check("exit cut3", await adapter.exit_sketch())
    name_last_feature(adapter, "Sketch3")
    check("cut3", await adapter.create_cut_extrude(
        ExtrusionParameters(depth=BIG_DEPTH, both_directions=True)))
    name_last_feature(adapter, "Cut-Extrude3")
    await volume_check(adapter, "Cut-Extrude3", 434_257, 200)

    # 4. Cut-Extrude4: +X half, mid-plane 165.1 -> right window.
    check("sketch cut4", await adapter.create_sketch("Top"))
    await add_line_chain(adapter, [
        (WEB, -BIG), (BIG, -BIG), (BIG, BIG), (WEB, BIG)])
    check("exit cut4", await adapter.exit_sketch())
    name_last_feature(adapter, "Sketch4")
    check("cut4", await adapter.create_cut_extrude(
        ExtrusionParameters(depth=BIG_DEPTH, both_directions=True)))
    name_last_feature(adapter, "Cut-Extrude4")
    await volume_check(adapter, "Cut-Extrude4", 245_806, 200)

    # 5. Fillet3: R12.7 on the four inner-frame corner edges (concave -> adds).
    check("fillet", await adapter.add_fillet(FILLET_R, FILLET_EDGES))
    name_last_feature(adapter, "Fillet3")
    await volume_check(adapter, "Fillet3", 246_685, 200)

    # 6. Holes: 4× Ø12.3 on the Front plane, both-directions deep. Only the foot
    #    band (Z -88.9..-82.55) carries material along the bore, so this drills
    #    the tapped-hole through-bores. (Cosmetic 9/16-12 thread not modeled.)
    check("sketch holes", await adapter.create_sketch("Front"))
    for hx, hy in HOLES:
        check(f"hole ({hx},{hy})", await adapter.add_circle(hx, hy, HOLE_DIA / 2.0))
    check("exit holes", await adapter.exit_sketch())
    name_last_feature(adapter, "Sketch5")
    check("cut holes", await adapter.create_cut_extrude(
        ExtrusionParameters(depth=200.0, both_directions=True)))
    name_last_feature(adapter, "9/16-12 Tapped Hole1")
    await volume_check(adapter, "Holes", 243_665, 200)

    # 7. Chamfer2: 1.27 mm / 45° around the whole window rim -- the 12 inner-
    #    frame opening edges plus the slant/trapezoid/fillet faces, tangent-
    #    propagated.
    check("chamfer", await adapter.add_chamfer(
        CHAMFER, CHAMFER_EDGES, face_points=CHAMFER_FACES, tangent_propagation=True))
    name_last_feature(adapter, "Chamfer2")
    await volume_check(adapter, "Chamfer2", 240_512, 200)

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
