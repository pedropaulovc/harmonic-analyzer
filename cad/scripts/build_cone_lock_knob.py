r"""Reproduction script: cone platform lock knob (video 4/4 t00411 "knob").

The chrome thumb knob that clamps the cone SWING PLATFORM to the base:
"Unscrewing this knob allows the cone gear set to swing away from the
cylinder" (v4 6:48). It stands in the gap between the big-end pivot post
and the arbor pedestal (t00411/t00417); its stud drops through the
platform's open lock NOTCH (build_cone_swing_platform) into the base.
Tightened ON the plate it clamps the swing locked ENGAGED; with the plate
swung clear (the notch mouth is open at the lobe edge -- t00417 shows the
bolt standing past the plate end) screwing the washer down past plate-top
level fences the mouth and locks the plate DISENGAGED.

Shape per t00411: a thin washer flange under one straight-walled body
crowned by a dome -- washer + body stacked coaxial extrudes (the proven
blank; stepped REVOLVES fail to pattern/boolean), then a large top-edge
fillet forms the domed crown. Origin at the WASHER BOTTOM (the face that
seats on the plate top), stud extruded DOWNWARD ending flush with the
base top. DOCUMENTED DEVIATION: the thread engagement into the base is
not modeled -- the drive-train has no base component (the crank/arbor
pedestals' hold-down bolts set the precedent), and a longer stud would
interfere with harmonic-base in the top-level assembly's gate.

Dimensions photo-scaled vs the O24 post foot in v4_t00411.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_cone_lock_knob.py
"""

from __future__ import annotations

import math
import sys

from _fastener_catalog import fastener
from _common import (
    SketchDims,
    apply_material,
    check,
    define_circle,
    drive_dimension,
    ensure_fully_defined,
    force_rebuild,
    name_bore_axis,
    name_dimensions,
    name_last_feature,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_global,
    volume_check,
)
from _drawing_marks import (
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
    set_dimension_symmetric_tolerance,
)
from _part_pmi import author_part_pmi
from cone_lock_knob_spec import (
    BODY_DIA,  # knob body -- ONE straight wall (t00411: no mid step)
    BODY_TOP,  # body top above the washer seat; height ~ diameter
    DOME_R,  # top-edge fillet: the domed crown (leaves a O3 flat at the
    # apex, the still's slightly-flattened dome)
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    STUD_DIA,  # 1/4" clamp stud -- rides the platform's SLOT_W notch
    STUD_LEN,  # plate thickness exactly: stud ends FLUSH with the base
    SURFACE_FINISHES,
    # top (thread engagement into the absent base unmodeled, see docstring)
    WASHER_DIA,  # clamp washer flange, seats on the plate top
    WASHER_T,
    WASHER_THICKNESS_TOLERANCE_MM,
)

PART_NAME = "cone-lock-knob"
SPEC = fastener(PART_NAME)
MATERIAL = SPEC.material  # bright/chromed steel (the pinion-handle
# precedent for chrome-look hardware; v4_t00411 shows worn chrome plate)

def _dome_fillet_volume(body_r: float, r: float) -> float:
    """Removed volume of a radius-r fillet on a body_r cylinder's top rim.

    Pappus over the corner cross-section (square r^2 minus the quarter
    disc), centroid measured inward from the wall.
    """
    area = r * r * (1.0 - math.pi / 4.0)
    sq = r * r * (r / 2.0)
    disc = (math.pi * r * r / 4.0) * (r - 4.0 * r / (3.0 * math.pi))
    x_bar = (sq - disc) / area
    return 2.0 * math.pi * (body_r - x_bar) * area


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations). The mm suffix is load-bearing -- this
    # is an INCH document and the equation manager reads BARE numbers in
    # document units (an unsuffixed 18 = 18 in).
    await set_global(adapter, "WasherDia", f"{WASHER_DIA}mm")
    await set_global(adapter, "WasherT", f"{WASHER_T}mm")
    await set_global(adapter, "BodyDia", f"{BODY_DIA}mm")
    await set_global(adapter, "BodyTop", f"{BODY_TOP}mm")
    await set_global(adapter, "DomeR", f"{DOME_R}mm")
    await set_global(adapter, "StudDia", f"{STUD_DIA}mm")
    await set_global(adapter, "StudLen", f"{STUD_LEN}mm")

    drive_jobs: list[tuple[str, str]] = []

    # Coaxial stack UP from the washer seat (origin, Top plane). Both discs are
    # sketched at the origin and extruded from the same plane with a growing
    # extent (the thumb-screw blank trick): the smaller-diameter body adds
    # volume only past the washer it merges into, so each delta is analytic.
    v_expect = 0.0
    for label, dia, extent, delta, dia_name, dia_drive, depth_name in (
        ("washer", WASHER_DIA, WASHER_T,
         math.pi * (WASHER_DIA / 2.0) ** 2 * WASHER_T,
         "WasherDia", '"WasherDia"', "WasherT"),
        ("body", BODY_DIA, BODY_TOP,
         math.pi * (BODY_DIA / 2.0) ** 2 * (BODY_TOP - WASHER_T),
         "BodyDia", '"BodyDia"', "BodyTop"),
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
        depth_dim = name_dimensions(adapter, label.capitalize(), [depth_name])
        drive_jobs += [(depth_dim[0], f'"{depth_name}"')]
        v_expect += delta
        await volume_check(adapter, label, v_expect, 0.005 * v_expect)

    # Domed crown: one large fillet on the body's top rim (t00411's dome).
    check(
        "fillet dome",
        await adapter.add_fillet(DOME_R, [[BODY_DIA / 2.0, BODY_TOP, 0.0]]),
    )
    name_last_feature(adapter, "DomeCrown")
    dome_dim = name_dimensions(adapter, "DomeCrown", ["DomeR"])
    drive_jobs += [(dome_dim[0], '"DomeR"')]
    v_expect -= _dome_fillet_volume(BODY_DIA / 2.0, DOME_R)
    await volume_check(adapter, "dome crown", v_expect, 0.005 * v_expect)

    # Clamp stud DOWNWARD from the washer seat: through the platform's notch,
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
    stud_dim = name_dimensions(adapter, "Stud", ["StudLen"])
    drive_jobs += [(stud_dim[0], '"StudLen"')]
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
    set_dimension_symmetric_tolerance(
        adapter, "Washer", "WasherT", WASHER_THICKNESS_TOLERANCE_MM
    )

    # Vertical clamp axis for the assembly (locates by datums today; the axis
    # names the screw line for any future concentric mate).
    await name_bore_axis(adapter, "Front Plane", 0.0, "Right Plane", 0.0, "clamp axis")

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    author_part_pmi(adapter, surface_finishes=SURFACE_FINISHES)
    apply_drawing_properties(
        adapter,
        PART_NAME,
        {"Manufacturing Notes": DRAWING_NOTES},
    )
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
