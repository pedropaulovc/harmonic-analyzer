r"""Reproduction script: magnifier subassembly (book ch. 20-21).

The amplification stage: the magnifying lever takes the summing lever's tiny
motion and the magnifying wheel multiplies it again (via the wire to the pen),
in machine coordinates (assembly origin = base origin; the output side is -Z).

* magnifying-bracket (ground, bolted under the coefficients plate) carrying the
  magnifying-lever on its collar bore (revolute about X); the clamp + thumb
  screw + vertical rod + output-fixture ride the lever as one rigid body at the
  set magnification radius (the output fixture is where WIRE 1 to the wheel hub
  hooks).
* wheel-bar (HALF-width, clamped at ONE column with a free end past the pen
  hanger) + its column-clamp + pinch screw.
* wheel-axle (structure) carrying the magnifying-wheel, which spins on its stud
  (revolute); the wheel rim drives the pen rod via WIRE 2.

Cross-subassembly fits (checked at the top level): the column-clamp rides the
O25.4 column (frame.SLDASM); the pen-hanger (pen.SLDASM) clamps the wheel-bar,
and the wheel rim -> pen-rod wire couples this sub to the pen.

Documented simplifications (Appendix C): the magnifying clamp's thumb screw is
modeled backed-out (the tip is tangent to the lever rod -- a seated screw would
overlap it); the output fixture's clamp screw is omitted (its cross hole doubles
as the wire hook); the wires are flexible elements, not modeled.

Fix-all strategy (M6.2): every structural component inserted at its exact final
transform and fixed; the lever + wheel are left free and constrained by mates;
transforms asserted by read-back; zero interference.

Dimensions: cad/DIMENSIONS.md ch. 20-21.

Run (SolidWorks already open)::

    C:\src\SolidworksMCP-python\.venv\Scripts\python.exe cad\scripts\build_magnifier_assembly.py
"""

from __future__ import annotations

import sys

from _common import (
    check,
    run_build,
)
from _assembly import (
    angle_driver,
    assert_components_fully_defined,
    check_no_interference,
    coincident_mate,
    component_origin,
    distance_driver,
    lock_mate,
    named_ref,
    place_component,
    save_assembly_and_images,
)
from _transforms import IDENTITY, ROT_X_NEG90, ROT_Y_POS90, rot_z_rows

ASM_NAME = "magnifier"

# --- machine anchors ---------------------------------------------------------
BAR_Z = -133.9  # support-bar centres: column line -112 - clamp offset 21.9
BAR_FRONT_Z = BAR_Z - 5.0  # -138.9: bar front face = platen back face
WHEEL_BAR_Y = 565.0
COLUMN_X = 197.0
COLUMN_Z = -112.0

# --- magnifying group --------------------------------------------------------
# Rod at the plate centreline (990) so it is coplanar with the coefficients plate
# (raised from 985); the bracket flange butts the plate front face. The clamp +
# vertical rod ride up with it (CLAMP_POS and VROD_TOP_Y derive from LEVER_ROD_Y).
LEVER_ROD_Y = 990.0
LEVER_ROD_Z = -85.0
CLAMP_X = -150.0  # sliding clamp default position (p.46/48 insets)
from build_magnifying_clamp import (  # noqa: E402
    BLOCK_DEPTH as CLAMP_DEPTH,
    LEVER_BORE_Y as CLAMP_BORE_Y,
    ROD_BORE_X as CLAMP_ROD_DX,
)

CLAMP_POS = (
    CLAMP_X - CLAMP_DEPTH / 2.0,  # local z 0..12 -> machine x (Ry+90)
    LEVER_ROD_Y - CLAMP_BORE_Y,
    LEVER_ROD_Z,
)
VROD_Z = LEVER_ROD_Z - CLAMP_ROD_DX  # -91.5 (local +x -> machine -z)
VROD_TOP_Y = LEVER_ROD_Y + 5.0  # dome inside the clamp's rod bore (rides the rod)
FIXTURE_Y0 = 926.0  # collar y 926..934 on the vertical rod

# --- wheel -------------------------------------------------------------------
WHEEL_X = -53.0
WHEEL_BAR_X0 = -92.0  # wheel-bar centre: span -192 (west clamp) .. +8
from build_wheel_axle import FLANGE_LEN, STUD_LEN  # noqa: E402

WHEEL_MID_Z = BAR_FRONT_Z - FLANGE_LEN - (STUD_LEN - 4.0) / 2.0  # -146.9:
# the 10-wide hub sits flush between the flange face and the tip collar

# --- M6.10 fasteners ---------------------------------------------------------
# Column-clamp pinch screw on the wheel-bar clamp's back face (z -88), backed
# out: the shank tip (-94.2) stays 0.2 inside the back-wall hole and 0.3 off
# the column surface (the four platen-rail-clamp pinch screws live in
# paper-drive.SLDASM).
PINCH_SCREW_Z = -88.0


async def build(adapter) -> dict[str, str]:
    check("create_assembly", await adapter.create_assembly())

    # --- magnifying group ----------------------------------------------------
    # Bracket = ground (bolted under the plate). The lever rides its collar bore
    # as a revolute about X; the rock (Rx, driven by the summing lever in the M6
    # Motion study) is a suppressible angle snapshot. Both rod axis and collar
    # axis are local X (Front∩Top), collinear at machine (985, -85). Axial slide
    # pinned on the Right plane (x~200, non-degenerate); rock via Top-plane angle
    # (Y-normal, mirror-invariant -> no flip, unlike the dy=0 off-axis spin).
    mb = await place_component(adapter, "magnifying-bracket",
                               [-40.0, LEVER_ROD_Y, LEVER_ROD_Z],
                               [0.0, 0.0, 0.0], IDENTITY)
    ml = await place_component(adapter, "magnifying-lever",
                               [-200.0, LEVER_ROD_Y, LEVER_ROD_Z],
                               [0.0, 0.0, 0.0], IDENTITY, ground=False)
    ml_o = component_origin(adapter, ml)
    await coincident_mate(adapter, named_ref(f"Axis1@{ml}", "AXIS"),
                          named_ref(f"Axis1@{mb}", "AXIS"),
                          label="mag-lever collar pivot", verify=(ml, ml_o))
    await distance_driver(adapter, named_ref(f"Right Plane@{ml}", "PLANE"),
                          named_ref("Right Plane", "PLANE"), abs(ml_o[0]),
                          label="mag-lever axial", verify=(ml, ml_o))
    await angle_driver(adapter, named_ref(f"Top Plane@{ml}", "PLANE"),
                       named_ref("Top Plane", "PLANE"), 0.0,
                       label="mag-lever rock snapshot", verify=(ml, ml_o))
    # The clamp + vertical rod + output fixture + thumb screw are clamped to the
    # lever at the set magnification radius (the thumb screw locks the clamp on
    # the rod): they ride the lever as one rigid body. The output fixture is
    # where WIRE 1 to the wheel hub hooks -- its (mostly vertical) travel as the
    # lever rotates is what drives the magnifying wheel in the Motion study, so
    # these must move WITH the lever, not stay fixed. Lock each to the lever.
    # Ry(+90): the clamp's lever bore (local Z) turns onto the rod axis (X).
    clamp = await place_component(adapter, "magnifying-clamp", list(CLAMP_POS),
                                  [0.0, 90.0, 0.0], ROT_Y_POS90, ground=False)
    await lock_mate(adapter, named_ref(f"Front Plane@{clamp}", "PLANE"),
                    named_ref(f"Front Plane@{ml}", "PLANE"),
                    label="mag-clamp locked to lever")
    # Backed-out thumb screw: shank tip tangent to the rod top (a seated
    # screw would overlap the rod it pinches -- see module docstring).
    tscrew = await place_component(adapter, "thumb-screw",
                                   [CLAMP_X, LEVER_ROD_Y + 3.0 + 12.0 + 5.0, LEVER_ROD_Z],
                                   [0.0, 0.0, -90.0], rot_z_rows(-90.0), ground=False,
                                   label="thumb-screw (clamp)")
    await lock_mate(adapter, named_ref(f"Front Plane@{tscrew}", "PLANE"),
                    named_ref(f"Front Plane@{clamp}", "PLANE"),
                    label="thumb-screw locked to clamp")
    vrod = await place_component(adapter, "magnifying-vertical-rod",
                                 [CLAMP_X, VROD_TOP_Y, VROD_Z],
                                 [0.0, 0.0, -90.0], rot_z_rows(-90.0), ground=False)
    await lock_mate(adapter, named_ref(f"Front Plane@{vrod}", "PLANE"),
                    named_ref(f"Front Plane@{clamp}", "PLANE"),
                    label="vertical-rod locked to clamp")
    fixture = await place_component(adapter, "output-fixture",
                                    [CLAMP_X, FIXTURE_Y0, VROD_Z],
                                    [0.0, 0.0, 0.0], IDENTITY, ground=False)
    await lock_mate(adapter, named_ref(f"Front Plane@{fixture}", "PLANE"),
                    named_ref(f"Front Plane@{vrod}", "PLANE"),
                    label="output-fixture locked to vertical-rod")

    # --- wheel bar + clamp ---------------------------------------------------
    # Magnifying-wheel bar: HALF-width (every ch30 plate shows it clamped
    # at ONE column with a free end just past the pen hanger -- M6.8
    # 8-view pass). Span -192..+8 covers the axle (-53) and the hanger
    # strap top (-19..-3).
    await place_component(adapter, "wheel-bar", [WHEEL_BAR_X0, WHEEL_BAR_Y, BAR_Z],
                          [0.0, 0.0, 0.0], IDENTITY)
    await place_component(adapter, "column-clamp", [-COLUMN_X, WHEEL_BAR_Y, COLUMN_Z],
                          [0.0, 90.0, 0.0], ROT_Y_POS90,
                          label=f"column-clamp (wheel x{-COLUMN_X:.0f})")

    # --- magnifying wheel ----------------------------------------------------
    # Rx(-90): the axle's +Y axis points -Z (flange on the bar front face).
    # The axle is structure (fixed); the wheel spins on its stud (revolute).
    ax = await place_component(adapter, "wheel-axle",
                               [WHEEL_X, WHEEL_BAR_Y, BAR_FRONT_Z],
                               [-90.0, 0.0, 0.0], ROT_X_NEG90)
    wh = await place_component(adapter, "magnifying-wheel",
                               [WHEEL_X, WHEEL_BAR_Y, WHEEL_MID_Z], [0.0, 0.0, 0.0],
                               IDENTITY, ground=False)
    wh_o = component_origin(adapter, wh)
    # Revolute: radial coincident (wheel axis Z || axle stud Z) + axial
    # distance(Front, |z|) + angle(Right, 0) rock snapshot. Probed FULLY(3),
    # no flip (probe_wheel.py).
    await coincident_mate(adapter, named_ref(f"Axis1@{wh}", "AXIS"),
                          named_ref(f"Axis1@{ax}", "AXIS"),
                          label="magnifying-wheel pivot", verify=(wh, wh_o))
    await distance_driver(adapter, named_ref(f"Front Plane@{wh}", "PLANE"),
                          named_ref("Front Plane", "PLANE"), abs(wh_o[2]),
                          label="magnifying-wheel axial", verify=(wh, wh_o))
    await angle_driver(adapter, named_ref(f"Right Plane@{wh}", "PLANE"),
                       named_ref("Right Plane", "PLANE"), 0.0,
                       label="magnifying-wheel rock snapshot", verify=(wh, wh_o))

    # --- fastener (M6.10) ----------------------------------------------------
    await place_component(adapter, "pinch-screw",
                          [-COLUMN_X, WHEEL_BAR_Y, PINCH_SCREW_Z],
                          [0.0, 0.0, 0.0], IDENTITY,
                          label=f"pinch-screw (wheel clamp x{-COLUMN_X:.0f})")

    assert_components_fully_defined(adapter)
    check_no_interference(adapter)
    return await save_assembly_and_images(adapter, ASM_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
