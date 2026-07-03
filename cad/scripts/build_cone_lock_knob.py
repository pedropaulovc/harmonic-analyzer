r"""Reproduction script: cone platform lock knob (video 4/4 t00411 "knob").

The chrome thumb knob that clamps the cone SWING PLATFORM to the base:
"Unscrewing this knob allows the cone gear set to swing away from the
cylinder" (v4 6:48). It stands in the gap between the big-end pivot post
and the arbor pedestal (t00411/t00417); its stud drops through the
platform's lock SLOT (build_cone_swing_platform) into the base, so
tightening it clamps the plate at either slot end -- locked ENGAGED or
locked DISENGAGED -- and loosening frees the p1 swing.

Stacked coaxial extrudes (thumb-screw recipe -- stepped REVOLVES fail to
pattern/boolean, stacked extrusions are the proven blank): washer flange,
body, and a stepped cap standing in for the domed top. Origin at the
WASHER BOTTOM (the face that seats on the plate top), stud extruded
DOWNWARD ending flush with the base top. DOCUMENTED DEVIATION: the thread
engagement into the base is not modeled -- the drive-train has no base
component (the crank/arbor pedestals' hold-down bolts set the precedent),
and a longer stud would interfere with harmonic-base in the top-level
assembly's gate.

Dimensions photo-scaled vs the O24 post foot in v4_t00411 (low).

Run (SolidWorks already open)::

    uv run python cad\scripts\build_cone_lock_knob.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    SketchDims,
    apply_material,
    check,
    define_circle,
    drive_dimension,
    ensure_fully_defined,
    force_rebuild,
    name_bore_axis,
    name_last_feature,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_global,
    volume_check,
)

PART_NAME = "cone-lock-knob"
MATERIAL = "Plain Carbon Steel"  # bright/chromed steel (the pinion-handle
# precedent for chrome-look hardware; v4_t00411 shows worn chrome plate)

WASHER_DIA = 20.0  # clamp washer flange, seats on the plate top (low)
WASHER_T = 1.5
BODY_DIA = 16.0  # knob body (low)
BODY_TOP = 11.5  # body top above the washer seat
CAP_DIA = 12.0  # stepped cap standing in for the domed top (low)
CAP_TOP = 13.5
STUD_DIA = 6.35  # 1/4" clamp stud -- rides the platform's SLOT_W slot
STUD_LEN = 6.35  # plate thickness exactly: stud ends FLUSH with the base
# top (thread engagement into the absent base unmodeled, see docstring)


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations). The mm suffix is load-bearing -- this
    # is an INCH document and the equation manager reads BARE numbers in
    # document units (an unsuffixed 20 = 20 in).
    await set_global(adapter, "WasherDia", f"{WASHER_DIA}mm")
    await set_global(adapter, "WasherT", f"{WASHER_T}mm")
    await set_global(adapter, "BodyDia", f"{BODY_DIA}mm")
    await set_global(adapter, "BodyTop", f"{BODY_TOP}mm")
    await set_global(adapter, "CapDia", f"{CAP_DIA}mm")
    await set_global(adapter, "CapTop", f"{CAP_TOP}mm")
    await set_global(adapter, "StudDia", f"{STUD_DIA}mm")
    await set_global(adapter, "StudLen", f"{STUD_LEN}mm")

    drive_jobs: list[tuple[str, str]] = []

    # Coaxial stack UP from the washer seat (origin, Top plane). Every disc is
    # sketched at the origin and extruded from the same plane with a growing
    # extent (the thumb-screw blank trick): a smaller-diameter disc adds volume
    # only past the taller neighbour it merges into, so each delta is analytic.
    v_expect = 0.0
    for label, dia, extent, delta, dia_name, dia_drive in (
        ("washer", WASHER_DIA, WASHER_T,
         math.pi * (WASHER_DIA / 2.0) ** 2 * WASHER_T,
         "WasherDia", '"WasherDia"'),
        ("body", BODY_DIA, BODY_TOP,
         math.pi * (BODY_DIA / 2.0) ** 2 * (BODY_TOP - WASHER_T),
         "BodyDia", '"BodyDia"'),
        ("cap", CAP_DIA, CAP_TOP,
         math.pi * (CAP_DIA / 2.0) ** 2 * (CAP_TOP - BODY_TOP),
         "CapDia", '"CapDia"'),
    ):
        sd = SketchDims()
        check(f"create_sketch {label}", await adapter.create_sketch("Top"))
        await define_circle(
            adapter, 0.0, 0.0, dia / 2.0, label, dims=sd,
            names=(f"{label}Cx", f"{label}Cz", dia_name),
            drives=(None, None, dia_drive),
        )
        await ensure_fully_defined(adapter, f"{label} sketch")
        check(f"exit_sketch {label}", await adapter.exit_sketch())
        name_last_feature(adapter, f"{label.capitalize()}Profile")
        drive_jobs += sd.apply(adapter, f"{label.capitalize()}Profile")
        check(
            f"extrude {label}",
            await adapter.create_extrusion(ExtrusionParameters(depth=extent)),
        )
        name_last_feature(adapter, label.capitalize())
        v_expect += delta
        await volume_check(adapter, label, v_expect, 0.005 * v_expect)

    # Clamp stud DOWNWARD from the washer seat: through the platform's slot,
    # ending flush with the base top.
    stud = SketchDims()
    check("create_sketch stud", await adapter.create_sketch("Top"))
    await define_circle(
        adapter, 0.0, 0.0, STUD_DIA / 2.0, "stud", dims=stud,
        names=("studCx", "studCz", "StudDia"),
        drives=(None, None, '"StudDia"'),
    )
    await ensure_fully_defined(adapter, "stud sketch")
    check("exit_sketch stud", await adapter.exit_sketch())
    name_last_feature(adapter, "StudProfile")
    drive_jobs += stud.apply(adapter, "StudProfile")
    check(
        "extrude stud (down)",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=STUD_LEN, reverse_direction=True)
        ),
    )
    name_last_feature(adapter, "Stud")
    v_expect += math.pi * (STUD_DIA / 2.0) ** 2 * STUD_LEN
    await volume_check(adapter, "stud", v_expect, 0.005 * v_expect)

    # Apply the deferred drive equations after the model + a rebuild exist, then
    # re-check: every equation evaluates to the value just built, so geometry
    # must not move.
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven knob (equations neutral)", v_expect, 0.005 * v_expect
    )

    # Vertical clamp axis for the assembly (locates by datums today; the axis
    # names the screw line for any future concentric mate).
    await name_bore_axis(adapter, "Front Plane", 0.0, "Right Plane", 0.0, "clamp axis")

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
