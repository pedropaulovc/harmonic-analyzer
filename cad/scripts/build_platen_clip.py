r"""Reproduction script: platen paper clip strip (book ch. 22, p. 55).

One of the two thin BRIGHT BRASS strips hugging the platen front's extreme
left/right edges, running from the TOP edge down ~112 (ch22 front photo);
the recording paper slides under them and a screw holds each end. Integral
outer-face seats consume the exact stock screw length while leaving the
strip's 1.2-mm spring section unchanged. Used twice in the assembly (vertical,
so the assembly rotates the +X-authored strip 90 about Z). Natural brass.

Dimensions: cad/DIMENSIONS.md "Chapter 22" — ch30-p002 Pose Studio fit,
scaled 0.8988 in the visible plane (low).

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
    define_circle,
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
from build_fillister_screw import HEAD_DIA, SHANK_DIA, SHANK_LEN
from build_platen import PLATE_THICKNESS, SOCKET_THREAD_ENGAGEMENT

PART_NAME = "platen-clip"
MATERIAL = "Brass"  # see _common.apply_material docstring

CLIP_LENGTH = 112.35  # ch30-p002 Pose Studio: 125 * 0.8988
CLIP_WIDTH = 8.988  # ch30-p002 Pose Studio: 10 * 0.8988
CLIP_THICKNESS = 1.2  # DIMENSIONS.md ch22: thin spring strip (low)
# Stock 90114A511 screws need 4.0 mm of #4-40 platen engagement. Two integral
# outer-face seat bosses make the remaining under-head stack exactly 2.35 mm,
# so the 6.35-mm shank ends flush at the platen back instead of protruding
# into the moving support-bar/clamp envelope.
SCREW_SEAT_STACK = SHANK_LEN - SOCKET_THREAD_ENGAGEMENT
SCREW_SEAT_BOSS_H = SCREW_SEAT_STACK - CLIP_THICKNESS
SCREW_SEAT_RADIAL_MARGIN = 0.2
SCREW_SEAT_DIA = HEAD_DIA + 2.0 * SCREW_SEAT_RADIAL_MARGIN
SCREW_HOLE_DIA = CLEARANCE_MM[("#4", "normal")]
# End screws pass through #4 normal-clearance holes in both bosses and strip.
HOLE_INSET = 7.1904  # ch30-p002 Pose Studio: 8 * 0.8988 from each end

if SCREW_SEAT_BOSS_H <= 0.0:
    raise AssertionError("stock fillister screw no longer requires a clip seat boss")
if abs(SCREW_SEAT_STACK + SOCKET_THREAD_ENGAGEMENT - SHANK_LEN) > 1e-9:
    raise AssertionError("clip/platen stack no longer finishes at the screw tip")
if abs(SOCKET_THREAD_ENGAGEMENT - PLATE_THICKNESS) > 1e-9:
    raise AssertionError("clip screw receiver no longer uses full platen thickness")
if SCREW_HOLE_DIA < SHANK_DIA:
    raise AssertionError("stock fillister shank does not clear the clip")


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations): strip plan size, end-screw hole, and
    # the inset that drives both hole stations. The mm suffix is load-bearing --
    # this is an INCH document and the equation manager reads BARE numbers in
    # document units (an unsuffixed 112.35 would be read as inches, blowing the
    # part up 25.4x in-plane). CLIP_THICKNESS is an extrude DEPTH (a feature
    # parameter, not a sketch dim), so its global is an editable knob that drives
    # nothing -- matching the exemplars.
    await set_global(adapter, "ClipLength", f"{CLIP_LENGTH}mm")
    await set_global(adapter, "ClipWidth", f"{CLIP_WIDTH}mm")
    await set_global(adapter, "ClipThickness", f"{CLIP_THICKNESS}mm")
    await set_global(adapter, "ScrewSeatDia", f"{SCREW_SEAT_DIA}mm")
    await set_global(adapter, "ScrewSeatBossH", f"{SCREW_SEAT_BOSS_H}mm")
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

    # Integral screw-seat bosses on the OUTER face (local -Z). They are part of
    # the clip, not separate spacers, so component count and pattern topology
    # remain unchanged. The seat diameter exceeds the stock head by 0.2 radial.
    seats = SketchDims()
    check("create_sketch screw seats", await adapter.create_sketch("Front"))
    await define_circle(
        adapter, HOLE_INSET, CLIP_WIDTH / 2.0, SCREW_SEAT_DIA / 2.0,
        "left screw seat", dims=seats,
        names=("LeftSeatX", "LeftSeatY", "LeftSeatDia"),
        drives=('"HoleInset"', '"HoleY"', '"ScrewSeatDia"'),
    )
    await define_circle(
        adapter, CLIP_LENGTH - HOLE_INSET, CLIP_WIDTH / 2.0, SCREW_SEAT_DIA / 2.0,
        "right screw seat", dims=seats,
        names=("RightSeatX", "RightSeatY", "RightSeatDia"),
        drives=('"HoleFarX"', '"HoleY"', '"ScrewSeatDia"'),
    )
    await ensure_fully_defined(adapter, "screw seat sketch")
    check("exit_sketch screw seats", await adapter.exit_sketch())
    name_last_feature(adapter, "ScrewSeatProfile")
    drive_jobs += seats.apply(adapter, "ScrewSeatProfile")
    check(
        "extrude screw seats",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=SCREW_SEAT_BOSS_H, reverse_direction=True)
        ),
    )
    name_last_feature(adapter, "ScrewSeats")
    v_seats = 2.0 * math.pi * (SCREW_SEAT_DIA / 2.0) ** 2 * SCREW_SEAT_BOSS_H
    v_with_seats = v_strip + v_seats
    await volume_check(adapter, "clip with screw seats", v_with_seats, 0.005 * v_strip)

    # End screw holes: ONE native Hole Wizard #4 clearance feature (2 points)
    # from the bosses' outer faces at local -Z. The cut passes through each
    # boss plus the base strip before the shank enters the platen receiver.
    hole_dia = SCREW_HOLE_DIA
    hole_cut = wizard_holes(
        adapter,
        HoleSpec("clearance", "#4"),
        [
            [HOLE_INSET, CLIP_WIDTH / 2.0, -SCREW_SEAT_BOSS_H],
            [CLIP_LENGTH - HOLE_INSET, CLIP_WIDTH / 2.0, -SCREW_SEAT_BOSS_H],
        ],
        (0.0, 0.0, -1.0),
        "end screw holes (#4 clearance)", name="ScrewHoles",
        placement_dims=[
            (("LeftX", '"HoleInset"'), ("LeftZ", '"HoleY"')),
            (("RightX", '"HoleFarX"'), ("RightZ", '"HoleY"')),
        ],
    )
    drive_jobs += hole_cut.placement_drive_jobs
    v_holes = (
        2.0
        * math.pi
        * (hole_dia / 2.0) ** 2
        * (CLIP_THICKNESS + SCREW_SEAT_BOSS_H)
    )
    v_final = v_with_seats - v_holes
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
