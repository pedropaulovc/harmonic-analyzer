r"""Reproduction script: platen support bar (book ch. 21/22, pp. 50-55, 62-63).

THE bar the platen rides on (book p.62 caption, singular): one rectangular
steel bar clamped across the two front columns by the two-piece column
clamps (build_sh_column_clamp_front.py and build_sh_column_clamp_back.py), carrying the hanging platen
(guides + locks on the platen back) and, on its own back face, the ch. 23
transgear hanger (pivot screw MHA-VN-041) and the latch hook (MHA-PD-014).
Cross-section 22 tall x 9 deep (ch22 back-side wear band + ch30 front
view); 452 long so the ends run ~29 past each column (ch30 p002).

Holes (all along local Z, the machine front-back axis):
* 4x clamp-screw counterbores flanking each column (x +-197 -+ 17.5):
  the screw heads sit sub-flush in the BAR's front face so the refitted platen
  can slide across the east clamp, and thread into the back clamp arc.
* the hanger's #8-32 blind pivot tap and the latch hook's two #4-40 base-screw
  through taps, all entering the back face (``pd_support_bar_spec``).

The hanger holes make the bar x-ASYMMETRIC, so it is authored MACHINE-
handed and placed on its exact machine transform.

Layout: bar axis along X, origin at the bar centre; height along Y,
depth along Z (front face local z -4.5, back face +4.5; named plane
``BackFace``). Dimensions: memory/paper-drive-rework.md E1/E2.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_pd_support_bar.py
"""

from __future__ import annotations

import math
import sys

from _appearance import apply_material
from _check import check
from _dimensions import drive_dimension, set_global
from _feature_tree import name_last_feature
from _part_checks import report_mass_properties, volume_check
from _part_save import save_part_and_images
from _rebuild import force_rebuild
from _session import run_build
from _sketch import SketchDims, ensure_fully_defined
from _sketch_circle import define_circle
from _sketch_rectangle import define_centered_rectangle
from _hole_spec import HoleSpec, blind_cut_dia_mm
from _holes import wizard_holes
from _visibility import blank_reference_geometry
from vn_clamp_screw_spec import HEAD_H as CLAMP_HEAD_H
from pd_support_bar_spec import (
    BACK_FACE_Z,
    BAR_DEPTH,
    BAR_HEIGHT,
    BRACKET_TAP_CSK_DIA,
    BRACKET_TAP_SPEC,
    BRACKET_TAP_X,
    HANGER_TAP_Y,
    PIVOT_TAP_CSK_DIA,
    PIVOT_TAP_DRILL_DEPTH,
    PIVOT_TAP_DRILL_DIA,
    PIVOT_TAP_X,
)

PART_NAME = "pd-support-bar"
MATERIAL = "Plain Carbon Steel"

BAR_LENGTH = 452.0  # ends at x +-226, ~29 past each Ø25.4 column (ch30 p002)

COLUMN_X = 197.0  # frame column line (frame assembly)
CLAMP_SCREW_DX = 17.5  # clamp screws flank each column
# The stock 90280A201 #8-32 clamp screws pass through #8 clearance holes.
# Their 3.9624-mm heads are recessed exactly 0.2 below the bar front: the
# right-shifted platen travels across the east clamp line, so proud heads
# would block its slide.
CLAMP_HEAD_RECESS = 0.2
CLAMP_CBORE_DIA = 8.5
CLAMP_CBORE_DEPTH = CLAMP_HEAD_H + CLAMP_HEAD_RECESS
CLAMP_THROUGH_HOLE_SPEC = HoleSpec("clearance", "#8")
CLAMP_HOLE_DIA = blind_cut_dia_mm(CLAMP_THROUGH_HOLE_SPEC)
CLAMP_HOLE_SPEC = HoleSpec(
    "counterbore_fillister",
    CLAMP_THROUGH_HOLE_SPEC.size,
    overrides_mm={
        "HoleDiameter": CLAMP_HOLE_DIA,
        "CounterBoreDiameter": CLAMP_CBORE_DIA,
        "CounterBoreDepth": CLAMP_CBORE_DEPTH,
    },
)

CLAMP_HOLE_X = tuple(
    s * (COLUMN_X + d) for s in (-1.0, 1.0) for d in (-CLAMP_SCREW_DX, CLAMP_SCREW_DX)
)


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import CreatePlaneParameters, ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations): the section and the length. The
    # mm suffix is load-bearing -- this is an INCH document and the equation
    # manager reads BARE numbers in document units (an unsuffixed 452 = 452 in).
    # (The old ClampHoleDia/BracketHoleDia knobs are gone: the screw holes are
    # now native Hole Wizard features whose diameters come from the ANSI-inch
    # clearance/tap tables, not driven dims.)
    await set_global(adapter, "BarHeight", f"{BAR_HEIGHT}mm")
    await set_global(adapter, "BarDepth", f"{BAR_DEPTH}mm")
    await set_global(adapter, "BarLength", f"{BAR_LENGTH}mm")

    drive_jobs: list[tuple[str, str]] = []

    # Bar profile: width along X = length, height along Y; depth extruded along Z.
    bar = SketchDims()
    check("create_sketch bar", await adapter.create_sketch("Front"))
    await define_centered_rectangle(
        adapter, BAR_LENGTH / 2.0, BAR_HEIGHT / 2.0, "bar", dims=bar,
        name_width="Length", drive_width='"BarLength"',
        name_depth="Height", drive_depth='"BarHeight"',
    )
    await ensure_fully_defined(adapter, "bar sketch")
    check("exit_sketch bar", await adapter.exit_sketch())
    name_last_feature(adapter, "BarProfile")
    drive_jobs += bar.apply(adapter, "BarProfile")
    check(
        "extrude bar",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=BAR_DEPTH, both_directions=True)
        ),
    )
    name_last_feature(adapter, "Bar")

    expected = BAR_HEIGHT * BAR_DEPTH * BAR_LENGTH
    await volume_check(adapter, "bar", expected, 0.005 * expected)

    # Clamp-screw holes, through along Z at the bar's mid-height, drilled from
    # the bar FRONT face (local z = -BAR_DEPTH/2, where the clamp-screw heads
    # sit -- ch30 p002), while the bar is still a plain prism: one native Hole
    # Wizard feature, 4 clamp-screw #8 COUNTERBORES flanking the columns.
    front_z = -BAR_DEPTH / 2.0
    clamp_dia = CLAMP_HOLE_DIA
    wizard_holes(
        adapter, CLAMP_HOLE_SPEC,
        [[x, 0.0, front_z] for x in CLAMP_HOLE_X],
        (0.0, 0.0, -1.0), "clamp-screw counterbores (#8)", name="ClampHoles",
    )
    v_holes = len(CLAMP_HOLE_X) * (
        math.pi * (clamp_dia / 2.0) ** 2 * BAR_DEPTH
        + math.pi
        * ((CLAMP_CBORE_DIA / 2.0) ** 2 - (clamp_dia / 2.0) ** 2)
        * CLAMP_CBORE_DEPTH
    )
    expected -= v_holes
    await volume_check(adapter, "bar with clamp holes", expected, 0.02 * v_holes)

    # Latch hook's base screws: two #4-40 taps THROUGH from the back face (their
    # exits on the front face lie under the platen footprint), then a
    # 90-degree countersink on both mouths of each.
    bracket_dia = blind_cut_dia_mm(BRACKET_TAP_SPEC)
    wizard_holes(
        adapter, BRACKET_TAP_SPEC,
        [[x, HANGER_TAP_Y, BACK_FACE_Z] for x in BRACKET_TAP_X],
        (0.0, 0.0, 1.0),
        f"latch-hook base-screw taps ({BRACKET_TAP_SPEC.size} through)",
        name="BracketTaps",
    )
    r_bracket = bracket_dia / 2.0
    v_bracket = len(BRACKET_TAP_X) * math.pi * r_bracket**2 * BAR_DEPTH
    expected -= v_bracket
    await volume_check(adapter, "bar with bracket taps", expected, 0.03 * v_bracket)
    bracket_csk = (BRACKET_TAP_CSK_DIA - bracket_dia) / 2.0
    check(
        "countersink bracket-tap mouths",
        await adapter.add_chamfer(
            bracket_csk,
            [
                [x + r_bracket, HANGER_TAP_Y, z_face]
                for x in BRACKET_TAP_X
                for z_face in (-BACK_FACE_Z, BACK_FACE_Z)
            ],
        ),
    )
    name_last_feature(adapter, "BracketTapCountersinks")
    v_bracket_csk = (
        2 * len(BRACKET_TAP_X) * math.pi * bracket_csk**2 * (r_bracket + bracket_csk / 3.0)
    )
    expected -= v_bracket_csk
    await volume_check(
        adapter, "bracket-tap countersinks", expected, 0.03 * v_bracket_csk + 0.05
    )

    # Hanger pivot: the #8-32 tap drill is FLAT-bottomed (drill + end mill), so
    # it is a plain blind cut from the back face rather than a wizard tap,
    # whose 118-degree point would eat the floor under it.
    check(
        f"create_plane BackFace (Front Plane, +{BACK_FACE_Z})",
        await adapter.create_plane(
            CreatePlaneParameters(mode="offset", base_plane="Front Plane", offset=BACK_FACE_Z)
        ),
    )
    name_last_feature(adapter, "BackFace")
    pivot = SketchDims()
    check("create_sketch pivot tap drill", await adapter.create_sketch("BackFace"))
    await define_circle(
        adapter,
        PIVOT_TAP_X,
        HANGER_TAP_Y,
        PIVOT_TAP_DRILL_DIA / 2.0,
        "pivot tap drill",
        dims=pivot,
        names=("PivotTapX", "PivotTapY", "PivotTapDrillDia"),
        drives=(None, None, None),
    )
    await ensure_fully_defined(adapter, "pivot tap drill sketch")
    check("exit_sketch pivot tap drill", await adapter.exit_sketch())
    name_last_feature(adapter, "PivotTapProfile")
    drive_jobs += pivot.apply(adapter, "PivotTapProfile")
    # BackFace's normal is +Z, out of the bar, so the default cut runs -Z into
    # it.  Reversed, the cut missed the body and flipped its side to cut,
    # leaving 21422 of 88036 mm^3 (run 20261001T011714683Z).
    check(
        "cut pivot tap drill (flat, blind)",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=PIVOT_TAP_DRILL_DEPTH)
        ),
    )
    name_last_feature(adapter, "PivotTap")
    r_pivot = PIVOT_TAP_DRILL_DIA / 2.0
    v_pivot = math.pi * r_pivot**2 * PIVOT_TAP_DRILL_DEPTH
    expected -= v_pivot
    await volume_check(adapter, "bar with pivot tap drill", expected, 0.03 * v_pivot)
    pivot_csk = (PIVOT_TAP_CSK_DIA - PIVOT_TAP_DRILL_DIA) / 2.0
    check(
        "countersink pivot-tap mouth",
        await adapter.add_chamfer(
            pivot_csk, [[PIVOT_TAP_X + r_pivot, HANGER_TAP_Y, BACK_FACE_Z]]
        ),
    )
    name_last_feature(adapter, "PivotTapCountersink")
    v_pivot_csk = math.pi * pivot_csk**2 * (r_pivot + pivot_csk / 3.0)
    expected -= v_pivot_csk
    await volume_check(
        adapter, "pivot-tap countersink", expected, 0.03 * v_pivot_csk + 0.05
    )
    blank_reference_geometry(adapter, (("BackFace", "PLANE"),))

    # Apply the deferred drive equations after the model exists, then re-check:
    # every equation evaluates to the value just built, so geometry must not move.
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(adapter, "driven bar (equations neutral)", expected, 0.005 * expected)

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
