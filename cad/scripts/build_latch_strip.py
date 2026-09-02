r"""Reproduction script: transgear latch strip (book ch. 23 pp. 58-63; video 4/4).

The "small latch that allows the operator to disengage the gearing from the
platen" (ch23 text; p.58 "latch" callout; engineerguy 4/4 v4_transgear_001-
008): a flat bright spring-steel strip screwed to the platen support bar's
front face, hanging down beside the 120T disc and ending in an eye that
drops over the knob shaft's turned seat. It is the spring lock of the swing
cluster -- in the video a finger bends the strip's free end forward off the
seat and the whole gear cluster then swings on the stud (slack chain, gear
swap). The flex itself is not modelled: the strip is shown latched.

Layout (part frame): eye centre at the origin, strip up +Y to the screw hole
at (0, SCREW_Y), STRIP_W wide with full-round ends, STRIP_T thick extruded +Z
from z = 0; an integral SPACER_T boss around the screw hole packs the strip's
top out to the bar face (the strip plane sits in front of the bar so its eye
can reach the seat between the third gear and the knob-shaft shoulder).

Run (SolidWorks already open)::

    uv run python cad\scripts\build_latch_strip.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    POLISHED_STEEL,
    SketchDims,
    add_line_chain,
    anchor_point_to_origin,
    apply_color,
    apply_material,
    check,
    define_circle,
    define_rectilinear_chain,
    drive_dimension,
    ensure_fully_defined,
    extrude_at_offset,
    force_rebuild,
    name_last_feature,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_global,
    set_sketch_direct_db,
    volume_check,
)

PART_NAME = "latch-strip"
MATERIAL = "Plain Carbon Steel"  # bright spring steel strip (p.58)

STRIP_W = 12.0  # ch23 page002_img04: a shade wider than the knob-shaft seat's boss
STRIP_T = 1.0  # spring strip; fits the 1.5 seat band with 0.25 air each side
SCREW_Y = 54.367  # eye centre -> bar mid-height (paper-drive: BAR_CY - KNOB_SHAFT_XY[1])
EYE_DIA = 5.4  # drops over the O5 turned third-gear seat of the knob shaft
SCREW_HOLE_DIA = 4.4  # #8 bracket-screw clearance
SPACER_T = 4.25  # packs the strip's top out to the bar's front face
SPACER_H = 10.0  # boss height about the screw hole

END_R = STRIP_W / 2.0
V_STRIP = (STRIP_W * SCREW_Y + math.pi * END_R**2) * STRIP_T
V_SPACER = STRIP_W * SPACER_H * SPACER_T
V_EYE = math.pi * (EYE_DIA / 2.0) ** 2 * STRIP_T
V_SCREW_HOLE = math.pi * (SCREW_HOLE_DIA / 2.0) ** 2 * (STRIP_T + SPACER_T)
V_TOTAL = V_STRIP + V_SPACER - V_EYE - V_SCREW_HOLE


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations). mm suffix load-bearing (INCH document).
    await set_global(adapter, "StripW", f"{STRIP_W}mm")
    await set_global(adapter, "StripT", f"{STRIP_T}mm")
    await set_global(adapter, "ScrewY", f"{SCREW_Y}mm")
    await set_global(adapter, "EyeDia", f"{EYE_DIA}mm")
    await set_global(adapter, "ScrewHoleDia", f"{SCREW_HOLE_DIA}mm")
    await set_global(adapter, "SpacerT", f"{SPACER_T}mm")
    await set_global(adapter, "SpacerH", f"{SPACER_H}mm")

    drive_jobs: list[tuple[str, str]] = []

    # Stadium outline: two vertical flanks, full-round ends about the eye
    # (origin) and the screw hole (0, SCREW_Y). Direct-to-DB, constrained
    # explicitly: both arc centres anchored, both radii dimensioned, the
    # flanks vertical and the four joins coincident.
    strip = SketchDims()
    check("create_sketch strip", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    bottom = check(
        "bottom round",
        await adapter.add_arc(0.0, 0.0, -END_R, 0.0, END_R, 0.0),
    )
    right = check("right flank", await adapter.add_line(END_R, 0.0, END_R, SCREW_Y))
    top = check(
        "top round",
        await adapter.add_arc(0.0, SCREW_Y, END_R, SCREW_Y, -END_R, SCREW_Y),
    )
    left = check("left flank", await adapter.add_line(-END_R, SCREW_Y, -END_R, 0.0))
    set_sketch_direct_db(adapter, False)
    for label, ent in (("right flank", right), ("left flank", left)):
        check(f"{label} vertical", await adapter.add_sketch_constraint(ent, None, "vertical"))
    for label, a, b in (
        ("bottom-right join", f"{bottom}.end", f"{right}.start"),
        ("right-top join", f"{right}.end", f"{top}.start"),
        ("top-left join", f"{top}.end", f"{left}.start"),
        ("left-bottom join", f"{left}.end", f"{bottom}.start"),
    ):
        check(label, await adapter.add_sketch_constraint(a, b, "coincident"))
    check(
        "eye centre on origin",
        await adapter.add_sketch_constraint(f"{bottom}.center", "origin", "coincident"),
    )
    check("bottom radius", await adapter.add_sketch_dimension(bottom, None, "radial", END_R))
    strip.record("BottomR", '"StripW" / 2')
    await anchor_point_to_origin(adapter, f"{top}.center", 0.0, SCREW_Y, "screw-hole centre")
    strip.record("ScrewRise", '"ScrewY"')
    check("top radius", await adapter.add_sketch_dimension(top, None, "radial", END_R))
    strip.record("TopR", '"StripW" / 2')
    await ensure_fully_defined(adapter, "strip sketch")
    check("exit_sketch strip", await adapter.exit_sketch())
    name_last_feature(adapter, "StripProfile")
    drive_jobs += strip.apply(adapter, "StripProfile")
    check(
        "extrude strip",
        await adapter.create_extrusion(ExtrusionParameters(depth=STRIP_T)),
    )
    name_last_feature(adapter, "Strip")
    drive_jobs.append(("D1@Strip", '"StripT"'))
    expected = V_STRIP
    await volume_check(adapter, "strip", expected, 0.005 * V_STRIP)

    # Spacer boss on the back of the strip's top, packing it out to the bar.
    spacer = SketchDims()
    check("create_sketch spacer", await adapter.create_sketch("Front"))
    s_rect = [
        (-END_R, SCREW_Y - SPACER_H / 2.0),
        (END_R, SCREW_Y - SPACER_H / 2.0),
        (END_R, SCREW_Y + SPACER_H / 2.0),
        (-END_R, SCREW_Y + SPACER_H / 2.0),
    ]
    s_lines = await add_line_chain(adapter, s_rect)
    await define_rectilinear_chain(
        adapter, s_lines, s_rect, label="spacer", dims=spacer,
        names=["SpacerW", "SpacerH", "SpacerAnchorX", "SpacerAnchorZ"],
        drives=['"StripW"', '"SpacerH"', '"StripW" / 2', '"ScrewY" - "SpacerH" / 2'],
    )
    await ensure_fully_defined(adapter, "spacer sketch")
    check("exit_sketch spacer", await adapter.exit_sketch())
    name_last_feature(adapter, "SpacerProfile")
    drive_jobs += spacer.apply(adapter, "SpacerProfile")
    extrude_at_offset(adapter, SPACER_T, STRIP_T)
    name_last_feature(adapter, "Spacer")
    expected += V_SPACER
    await volume_check(adapter, "spacer", expected, 0.005 * V_SPACER)

    # Eye over the knob-shaft seat (origin) and the screw clearance hole, both
    # cut through everything along Z.
    holes = SketchDims()
    check("create_sketch holes", await adapter.create_sketch("Front"))
    await define_circle(
        adapter, 0.0, 0.0, EYE_DIA / 2.0, "eye",
        dims=holes, names=("EyeCx", "EyeCz", "EyeDia"), drives=(None, None, '"EyeDia"'),
    )
    await define_circle(
        adapter, 0.0, SCREW_Y, SCREW_HOLE_DIA / 2.0, "screw hole",
        dims=holes, names=("ScrewCx", "ScrewCz", "ScrewHoleDia"),
        drives=(None, '"ScrewY"', '"ScrewHoleDia"'),
    )
    await ensure_fully_defined(adapter, "holes sketch")
    check("exit_sketch holes", await adapter.exit_sketch())
    name_last_feature(adapter, "HoleProfile")
    drive_jobs += holes.apply(adapter, "HoleProfile")
    check(
        "cut holes",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=2.0 * (STRIP_T + SPACER_T) + 2.0, both_directions=True)
        ),
    )
    name_last_feature(adapter, "Holes")
    expected -= V_EYE + V_SCREW_HOLE
    await volume_check(adapter, "eye + screw hole", expected, 0.02 * (V_EYE + V_SCREW_HOLE))

    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(adapter, "driven strip (equations neutral)", expected, 0.005 * expected)

    await apply_material(adapter, MATERIAL)
    await apply_color(adapter, POLISHED_STEEL)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
