r"""Reproduction script: alignment pinion drum (book ch. 25).

The long brass pinion used to set the machine to sines or cosines: with
the cone set swung clear, a lever engages this drum with the cylinder
train so turning it "moves all the cylinder gears as one" (p. 66). 42
teeth (counted on the p. 67 plate), cut at the SAME diametral pitch as
the cylinder gears it must mesh with -- the train DP from machine.yaml
(49.82 since the OD-62.2 re-anchor; ch25's book-era DP 30 predates that
rescale and over-sizes the teeth ~66%, burying the drum 5.4 mm into
every cylinder gear) -- and a drum long enough to span all 20 stations
at once. Each end carries an integral Ø6.35 arbor stub
riding its swing bracket's top bore (build_pinion_bracket.py); the front
stub runs on through the strap to take the turning handle
(build_pinion_handle.py). The knurled end collars are simplified away.

Layout: axis Z, drum z 0..143.2, front stub z -57..0, back stub z
143.2..166.25.
The ch30/M6.8 model carries it in the DISENGAGED rest state (p. 68
"gap"), so no tooth-phase seed is needed.

Dimensions: cad/DIMENSIONS.md "Chapter 25"; tooth count from
cad/config/machine/alignment_pinion.yaml.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_alignment_pinion.py
"""

from __future__ import annotations

import math
import sys

import _config
from _common import (
    SketchDims,
    apply_material,
    check,
    define_circle,
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
from _gear import build_fixed_gear
from build_cone_gear import DP  # DP = train diametral_pitch (machine.yaml)

PART_NAME = "alignment-pinion"
MATERIAL = "Brass"  # p.67: brass drum, same finish as the cylinder train

TEETH = _config.machine("alignment_pinion", "teeth")  # ch25 plate count (high)
FACE_WIDTH = 143.2  # DIMENSIONS.md ch25: spans all 20 drum stations, but
# the back face (machine z +68.2) shaves the last 0.28 of the j = 19
# gear face (ends +68.48); documented in Appendix C (derived). (The old
# cone-knob post that once capped the drum + stub at machine z 74 is
# retired -- the back stub now runs on to +91.25, see STUB_BACK.)
STUB_DIA = 6.35  # arbor stubs riding the strap top bores (derived)
STUB_FRONT = 57.0  # LONG front stub (ch30 GT 2026-07-02): through the 5 strap
# and on south to machine z -132, seating 2 deep in the tee-handle hub bore --
# the GT puts the handle ball at z -144.07 +- 2.7, well clear of the platen
# front, so the stub cantilevers the handle far forward of the drum
STUB_BACK = 23.05  # through the 5 strap and on north to machine z +91.25 (GT
# pinion_back: the photos show the free stub end proud behind the back strap;
# the old cone-knob post that capped it at z 74 is retired)

STUB_R = STUB_DIA / 2.0


async def build(adapter) -> dict[str, str]:
    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations): the arbor stub diameter and, as
    # declared feature-parameter knobs, the drum face width and the two stub
    # lengths (the main session retunes these against the re-anchored drive
    # train). The mm suffix is load-bearing -- this is an INCH document and the
    # equation manager reads BARE numbers in document units (an unsuffixed 6.35 =
    # 6.35 in). TEETH stays a module constant -- build_fixed_gear cuts the blank/
    # gap/pattern with literal numerics, off this self-naming path.
    await set_global(adapter, "FaceWidth", f"{FACE_WIDTH}mm")
    await set_global(adapter, "StubDia", f"{STUB_DIA}mm")
    await set_global(adapter, "StubFront", f"{STUB_FRONT}mm")
    await set_global(adapter, "StubBack", f"{STUB_BACK}mm")

    drive_jobs: list[tuple[str, str]] = []

    v_gear = await build_fixed_gear(adapter, TEETH, FACE_WIDTH, dp=DP)

    # Front arbor stub z -8..0 (flip: offset 0, extrude -Z off the gear face).
    # On-axis circle (origin centre): only the diameter dim is recorded.
    front = SketchDims()
    check("create_sketch front stub", await adapter.create_sketch("Front"))
    await define_circle(
        adapter, 0.0, 0.0, STUB_R, "front stub", dims=front,
        names=("FrontStubCx", "FrontStubCz", "StubDia"),
        drives=(None, None, '"StubDia"'),
    )
    await ensure_fully_defined(adapter, "front stub sketch")
    check("exit_sketch front stub", await adapter.exit_sketch())
    name_last_feature(adapter, "FrontStubProfile")
    drive_jobs += front.apply(adapter, "FrontStubProfile")
    extrude_at_offset(adapter, STUB_FRONT, 0.0, flip=True)
    name_last_feature(adapter, "FrontStub")
    v_front = math.pi * STUB_R**2 * STUB_FRONT
    v_gear = await volume_check(adapter, "front stub", v_gear + v_front, 0.02 * v_front)

    # Back arbor stub z 143.2..148.7.
    back = SketchDims()
    check("create_sketch back stub", await adapter.create_sketch("Front"))
    await define_circle(
        adapter, 0.0, 0.0, STUB_R, "back stub", dims=back,
        names=("BackStubCx", "BackStubCz", "StubDia"),
        drives=(None, None, '"StubDia"'),
    )
    await ensure_fully_defined(adapter, "back stub sketch")
    check("exit_sketch back stub", await adapter.exit_sketch())
    name_last_feature(adapter, "BackStubProfile")
    drive_jobs += back.apply(adapter, "BackStubProfile")
    extrude_at_offset(adapter, STUB_BACK, FACE_WIDTH)
    name_last_feature(adapter, "BackStub")
    v_back = math.pi * STUB_R**2 * STUB_BACK
    expected = v_gear + v_back
    await volume_check(adapter, "back stub", expected, 0.02 * v_back)
    # The gear's central reference axis (Axis1@alignment-pinion, Top∩Right from
    # build_fixed_gear) is the pinion spin/lock axis used by the p2 swing group
    # in build_drive_train -- same convention as the cone gears.

    # Deferred drive equations (the two stub diameters), then re-check neutrality
    # (each evaluates to the as-built value, so the geometry must not move).
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven alignment pinion (equations neutral)", expected, 0.02 * v_back
    )

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
