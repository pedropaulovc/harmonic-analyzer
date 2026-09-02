r"""Reproduction script: platen paper clip (book ch. 22, pp. 54-55).

One of the two bright brass paper holders hugging the platen front's extreme
left/right edges, running from the TOP edge down ~84. 2026-09-02 photo
re-derive (ch22 page001_img02 -- both holders on the platen back plate --
and page001_img03, the end close-up): each holder is TWO strips, not one:

* a BASE strip screwed to the platen at both ends (the two #4 fillister
  clip screws through its end holes, unchanged from the first pass);
* a thinner SLOTTED strip riding ON the base strip, the same screws passing
  through its long central slot so it can slide along the edge; its top end
  is bent up into a short LIP that flares away from the platen -- the paper's
  edge tucks under the strip through that mouth.

Modelled as ONE merged part (the two strips never come apart in use; the
sliding freedom is not a modelled DOF). Natural brass, no paint (they read
bright against the blackened platen). Used twice in paper-drive.SLDASM
(vertical: the assembly turns the +X-authored holder -90 about Z, origin at
the platen's top edge, so local +X runs DOWN the platen).

Layout: length along +X, width along +Y from the origin corner; thickness
along +Z with the FRONT face at z 0 (the screw heads seat there) and the
platen face at z CLIP_THICKNESS: base strip z BASE_T..CLIP_THICKNESS
(against the platen), slotted strip z 0..UPPER_T in front of it, lip rising
from the slotted strip's top end to z -LIP_H (away from the platen).

Dimensions: base strip as before (ch30-p002 Pose Studio fit, 0.8988 scale,
low); the upper strip, slot and lip are photo proportions off page001_img03
(strip width ~1:1 with the base, slot ~2/3 of the strip length and ~1/3 of
its width, lip ~1.5 high) -- low.

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
    extrude_at_offset,
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

CLIP_LENGTH = 83.5  # ch22 p.55 rear photo: 86.7 of the 140 mm plate (0.619) x PLATE_HEIGHT 134.82
CLIP_WIDTH = 8.988  # ch30-p002 Pose Studio: 10 * 0.8988
BASE_T = 1.0  # base strip thickness (against the platen)
UPPER_T = 0.8  # slotted strip thickness (in front of the base strip)
CLIP_THICKNESS = BASE_T + UPPER_T  # 1.8: the assembly's front-face stand-off from the platen
# End screws: the brass fillister clip screws (Ø2.9 shank) pass THROUGH, so
# each end hole is a #4 clearance Hole Wizard hole (normal fit Ø3.251; was a
# plain Ø3.0 cut) -- memory/fastener-policy-us-customary.
HOLE_INSET = 7.1904  # ch30-p002 Pose Studio: 8 * 0.8988 from each end
# Slotted upper strip (page001_img03): starts UPPER_X0 in from the top end
# (local x 0) and stops the same short of the bottom; its slot spans both
# screw stations with SLOT_MARGIN past each hole edge, SLOT_W wide (clears
# the Ø2.9 shank, narrower than the ~Ø4.6 fillister head that clamps it).
UPPER_X0 = 3.0
UPPER_LENGTH = CLIP_LENGTH - 2.0 * UPPER_X0  # 77.5
SLOT_W = 3.4
SLOT_MARGIN = 0.5
SLOT_X0 = HOLE_INSET - CLEARANCE_MM[("#4", "normal")] / 2.0 - SLOT_MARGIN  # 5.06
SLOT_X1 = CLIP_LENGTH - SLOT_X0  # 78.44
SLOT_LENGTH = SLOT_X1 - SLOT_X0
# Lip: the upper strip's top end bent away from the platen (-Z), LIP_H high.
LIP_H = 1.5

V_BASE = CLIP_LENGTH * CLIP_WIDTH * BASE_T
V_UPPER = UPPER_LENGTH * CLIP_WIDTH * UPPER_T
V_SLOT = SLOT_LENGTH * SLOT_W * UPPER_T
V_LIP = UPPER_T * CLIP_WIDTH * LIP_H
V_HOLES = 2.0 * math.pi * (CLEARANCE_MM[("#4", "normal")] / 2.0) ** 2 * BASE_T  # the slot already opens the upper strip
V_FINAL = V_BASE + V_UPPER - V_SLOT + V_LIP - V_HOLES

if not (SLOT_X0 > UPPER_X0 + 1.0 and SLOT_X1 < UPPER_X0 + UPPER_LENGTH - 1.0):
    raise AssertionError("platen clip slot must stay inside the upper strip with a 1 mm end land")
if SLOT_W <= CLEARANCE_MM[("#4", "normal")]:
    raise AssertionError("platen clip slot must be wider than the screw clearance hole")


async def _rect(adapter, label: str, name: str, rect: list[tuple[float, float]], dims: SketchDims, names, drives):
    check(f"create_sketch {label}", await adapter.create_sketch("Front"))
    lines = await add_line_chain(adapter, rect)
    await define_rectilinear_chain(adapter, lines, rect, label=label, dims=dims, names=names, drives=drives)
    await ensure_fully_defined(adapter, label)
    check(f"exit_sketch {label}", await adapter.exit_sketch())
    name_last_feature(adapter, name)


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations). The mm suffix is load-bearing -- this
    # is an INCH document and the equation manager reads BARE numbers in
    # document units. Thicknesses are extrude DEPTHS (feature parameters), so
    # their globals are editable knobs that drive nothing -- matching the
    # exemplars.
    await set_global(adapter, "ClipLength", f"{CLIP_LENGTH}mm")
    await set_global(adapter, "ClipWidth", f"{CLIP_WIDTH}mm")
    await set_global(adapter, "BaseT", f"{BASE_T}mm")
    await set_global(adapter, "UpperT", f"{UPPER_T}mm")
    await set_global(adapter, "HoleInset", f"{HOLE_INSET}mm")
    await set_global(adapter, "HoleY", '"ClipWidth" / 2')
    await set_global(adapter, "HoleFarX", '"ClipLength" - "HoleInset"')
    await set_global(adapter, "UpperX0", f"{UPPER_X0}mm")
    await set_global(adapter, "UpperLength", '"ClipLength" - 2 * "UpperX0"')
    await set_global(adapter, "SlotX0", f"{SLOT_X0}mm")
    await set_global(adapter, "SlotLength", '"ClipLength" - 2 * "SlotX0"')
    await set_global(adapter, "SlotW", f"{SLOT_W}mm")
    await set_global(adapter, "SlotY0", '("ClipWidth" - "SlotW") / 2')
    await set_global(adapter, "LipH", f"{LIP_H}mm")

    drive_jobs: list[tuple[str, str]] = []

    # 1. Base strip: corner-at-origin rectangle, length along X, width along Y,
    # extruded BASE_T from z BASE_T (the front face stays at z 0 for the upper
    # strip; the back face at CLIP_THICKNESS bears on the platen).
    outline = SketchDims()
    await _rect(
        adapter, "base outline", "BaseProfile",
        [(0.0, 0.0), (CLIP_LENGTH, 0.0), (CLIP_LENGTH, CLIP_WIDTH), (0.0, CLIP_WIDTH)],
        outline, ["Length", "Width"], ['"ClipLength"', '"ClipWidth"'],
    )
    drive_jobs += outline.apply(adapter, "BaseProfile")
    extrude_at_offset(adapter, BASE_T, UPPER_T)
    name_last_feature(adapter, "BaseStrip")
    await volume_check(adapter, "base strip", V_BASE, 0.005 * V_BASE)

    # 2. Slotted upper strip in front of it (z 0..UPPER_T), inset UPPER_X0 from
    # both ends. Its anchor corner is off the origin, so the chain emits the
    # anchor x as a dim (y = 0 is a relation).
    upper = SketchDims()
    await _rect(
        adapter, "upper outline", "UpperProfile",
        [(UPPER_X0, 0.0), (UPPER_X0 + UPPER_LENGTH, 0.0), (UPPER_X0 + UPPER_LENGTH, CLIP_WIDTH), (UPPER_X0, CLIP_WIDTH)],
        upper, ["UpperLength", "UpperWidth", "UpperX0"], ['"UpperLength"', '"ClipWidth"', '"UpperX0"'],
    )
    drive_jobs += upper.apply(adapter, "UpperProfile")
    check("extrude upper strip", await adapter.create_extrusion(ExtrusionParameters(depth=UPPER_T)))
    name_last_feature(adapter, "UpperStrip")
    await volume_check(adapter, "base + upper strips", V_BASE + V_UPPER, 0.005 * V_BASE)

    # 3. Slot through the upper strip only (mid-plane cut about z 0 reaching
    # +-UPPER_T: the front half cuts air, the back half stops at the base strip).
    slot = SketchDims()
    slot_y0 = (CLIP_WIDTH - SLOT_W) / 2.0
    await _rect(
        adapter, "slot", "SlotProfile",
        [(SLOT_X0, slot_y0), (SLOT_X1, slot_y0), (SLOT_X1, slot_y0 + SLOT_W), (SLOT_X0, slot_y0 + SLOT_W)],
        slot, ["SlotLength", "SlotW", "SlotX0", "SlotY0"], ['"SlotLength"', '"SlotW"', '"SlotX0"', '"SlotY0"'],
    )
    drive_jobs += slot.apply(adapter, "SlotProfile")
    check(
        "cut slot",
        await adapter.create_cut_extrude(ExtrusionParameters(depth=2.0 * UPPER_T, both_directions=True)),
    )
    name_last_feature(adapter, "Slot")
    await volume_check(adapter, "slotted", V_BASE + V_UPPER - V_SLOT, 0.005 * V_BASE)

    # 4. Lip: the upper strip's top end (x UPPER_X0..UPPER_X0 + UPPER_T) bent away
    # from the platen: a UPPER_T x CLIP_WIDTH rectangle extruded LIP_H toward -Z
    # from the front face (start offset -LIP_H, depth LIP_H, merging at z 0).
    lip = SketchDims()
    await _rect(
        adapter, "lip", "LipProfile",
        [(UPPER_X0, 0.0), (UPPER_X0 + UPPER_T, 0.0), (UPPER_X0 + UPPER_T, CLIP_WIDTH), (UPPER_X0, CLIP_WIDTH)],
        lip, ["LipT", "LipWidth", "LipX0"], ['"UpperT"', '"ClipWidth"', '"UpperX0"'],
    )
    drive_jobs += lip.apply(adapter, "LipProfile")
    extrude_at_offset(adapter, LIP_H, -LIP_H)
    name_last_feature(adapter, "Lip")
    await volume_check(adapter, "with lip", V_BASE + V_UPPER - V_SLOT + V_LIP, 0.005 * V_BASE)

    # 5. End screw holes: ONE native Hole Wizard #4 clearance feature (2 points)
    # from the front face (local z 0, outward normal -Z), through both strips;
    # in the upper strip they land inside the slot, so only the base strip loses
    # material.
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
    await volume_check(adapter, "clip", V_FINAL, 0.005 * V_BASE)

    # Apply the deferred drive equations after the whole model exists, then
    # re-check neutrality.
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(adapter, "driven clip (equations neutral)", V_FINAL, 0.005 * V_BASE)

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
