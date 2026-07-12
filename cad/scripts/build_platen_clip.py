r"""Reproduction script: platen paper clip strip (book ch. 22, p. 55).

One of the two thin BRIGHT BRASS strips hugging the platen front's extreme
left/right edges, running from the TOP edge down ~125 (ch22 front photo);
the recording paper slides under them and a screw holds each end. Used
twice in the assembly (vertical, so the assembly rotates the +X-authored
strip 90 about Z). Natural brass -- no paint (they read bright against the
blackened platen; the old PANEL_BLACK made them invisible).

Dimensions: cad/DIMENSIONS.md "Chapter 22" — scaled from the p.55 front
photo vs the 140 mm height callout (low).

Layout: length along +X, width along +Y from the origin corner,
thickness extruded +Z; screw holes inset from the ends.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_platen_clip.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    SketchDims,
    add_line_chain,
    apply_material,
    check,
    define_rectilinear_chain,
    drive_dimension,
    ensure_fully_defined,
    force_rebuild,
    name_last_feature,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_global,
    volume_check,
)
from _holes import CLEARANCE_MM, HoleSpec, wizard_holes

PART_NAME = "platen-clip"
MATERIAL = "Brass"  # see _common.apply_material docstring

CLIP_LENGTH = 125.0  # DIMENSIONS.md ch22: ~0.9x plate height, p.55 (low)
CLIP_WIDTH = 10.0  # DIMENSIONS.md ch22 (low)
CLIP_THICKNESS = 1.2  # DIMENSIONS.md ch22: thin spring strip (low)
# End screws: the brass fillister clip screws (Ø2.9 shank) pass THROUGH, so
# each end hole is a #4 clearance Hole Wizard hole (normal fit Ø3.251; was a
# plain Ø3.0 cut) -- memory/fastener-policy-us-customary.
HOLE_INSET = 8.0  # from each end


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations): strip plan size, end-screw hole, and
    # the inset that drives both hole stations. The mm suffix is load-bearing --
    # this is an INCH document and the equation manager reads BARE numbers in
    # document units (an unsuffixed 125 would be read as 125 inches, blowing the
    # part up 25.4x in-plane). CLIP_THICKNESS is an extrude DEPTH (a feature
    # parameter, not a sketch dim), so its global is an editable knob that drives
    # nothing -- matching the exemplars.
    await set_global(adapter, "ClipLength", f"{CLIP_LENGTH}mm")
    await set_global(adapter, "ClipWidth", f"{CLIP_WIDTH}mm")
    await set_global(adapter, "ClipThickness", f"{CLIP_THICKNESS}mm")
    await set_global(adapter, "HoleInset", f"{HOLE_INSET}mm")
    await set_global(adapter, "HoleY", '"ClipWidth" / 2')
    await set_global(adapter, "HoleFarX", '"ClipLength" - "HoleInset"')
    # (The old HoleDia/HoleInset/HoleY/HoleFarX knobs are gone: the end holes
    # are now a native Hole Wizard #4 clearance feature placed by point, not
    # equation-driven sketch dims.)

    drive_jobs: list[tuple[str, str]] = []

    # Outline: corner-at-origin rectangle (NOT origin-centred), length along X,
    # width along Y. A rectilinear chain in line order bottom/right/top/left:
    # closure makes top + left redundant, so only the bottom length and the
    # right-edge width are dims; the origin anchor adds no dims (corner at 0,0).
    outline = SketchDims()
    check("create_sketch outline", await adapter.create_sketch("Front"))
    clip_rect = [
        (0.0, 0.0),
        (CLIP_LENGTH, 0.0),
        (CLIP_LENGTH, CLIP_WIDTH),
        (0.0, CLIP_WIDTH),
    ]
    lines = await add_line_chain(adapter, clip_rect)
    await define_rectilinear_chain(
        adapter, lines, clip_rect, label="clip outline", dims=outline,
        names=["Length", "Width"],
        drives=['"ClipLength"', '"ClipWidth"'],
    )
    await ensure_fully_defined(adapter, "clip outline")
    check("exit_sketch outline", await adapter.exit_sketch())
    name_last_feature(adapter, "ClipProfile")
    drive_jobs += outline.apply(adapter, "ClipProfile")
    check(
        "extrude clip",
        await adapter.create_extrusion(ExtrusionParameters(depth=CLIP_THICKNESS)),
    )
    name_last_feature(adapter, "ClipStrip")
    v_strip = CLIP_LENGTH * CLIP_WIDTH * CLIP_THICKNESS
    await volume_check(adapter, "clip strip", v_strip, 0.005 * v_strip)

    # End screw holes: ONE native Hole Wizard #4 clearance feature (2 points)
    # from the front face (local z 0, outward normal -Z). Left hole at the near
    # inset; right hole at length minus inset.
    hole_dia = CLEARANCE_MM[("#4", "normal")]
    hole_cut = wizard_holes(
        adapter,
        HoleSpec("clearance", "#4"),
        [
            [HOLE_INSET, CLIP_WIDTH / 2.0, 0.0],
            [CLIP_LENGTH - HOLE_INSET, CLIP_WIDTH / 2.0, 0.0],
        ],
        (0.0, 0.0, -1.0),
        "end screw holes (#4 clearance)", name="ScrewHoles",
        placement_dims=[
            (("LeftX", '"HoleInset"'), ("LeftZ", '"HoleY"')),
            (("RightX", '"HoleFarX"'), ("RightZ", '"HoleY"')),
        ],
    )
    drive_jobs += hole_cut.placement_drive_jobs
    v_holes = 2.0 * math.pi * (hole_dia / 2.0) ** 2 * CLIP_THICKNESS
    v_final = v_strip - v_holes
    await volume_check(adapter, "clip with holes", v_final, 0.005 * v_strip)

    # Apply the deferred drive equations after the model + a rebuild exists, then
    # re-check: every equation evaluates to the value just built, so geometry
    # must not move -- the re-check is the proof.
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(adapter, "driven clip (equations neutral)", v_final, 0.005 * v_strip)

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
