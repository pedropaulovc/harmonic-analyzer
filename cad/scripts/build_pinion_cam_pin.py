r"""Reproduction script: pinion cam-follower pin (book ch. 25; 2 used).

The bright stud pressed into each swing strap's WEST EDGE just below the
pivot bore (PR8; ``page001_img01`` back-tail close-up), protruding west
over the lift rod where it RESTS ON the eccentric cam collar
(build_pinion_cam.py) from above. Turning the lever spins the rod +
cams; the rising OD lifts this pin -- 15 west of the pivot at pivot-ish
height, so the lift rotates the strap east into mesh. The return spring
(build_pinion_spring.py) parks it back disengaged. PR5's Ø3 through-pin
in a tail cross-bore is retired: the photo reads a fatter (~Ø4-5) stud
at the pivot's height band, and a blind edge seat is the only geometry
that clears the Ø6.35 pivot bore there.

Layout: axis Z, root (seated) end at the ORIGIN, z 0..15: 4.0 presses
into the strap's blind edge bore, 13 proud after the v2 linkage closure; domed outer end (sagitta
0.8, the rod-end crown idiom). Axisymmetric about its local x = 0.  Shank and
crown are both Right-plane half-profiles (sketch u = -z), so the diameter,
length and crown radius all import into the *Right side view, where the pin
lies as it is turned (rule 7; machinist review of 7f7fc1717).

Dimensions: cad/config/dimensions.yaml "Chapter 25".

Run (SolidWorks already open)::

    uv run python cad\scripts\build_pinion_cam_pin.py
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
    dimension_between,
    drive_dimension,
    ensure_fully_defined,
    force_rebuild,
    name_bore_axis,
    name_last_feature,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_global,
    set_sketch_direct_db,
    volume_check,
)
from _drawing_marks import (
    add_diametric_linear_dimension,
    apply_drawing_precision,
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
    set_dimension_bilateral_tolerance,
    set_dimension_symmetric_tolerance,
)
from _fit_limits import deviations
from _part_pmi import author_part_pmi
from _saved_part_guard import require_saved_drawing_properties
from pinion_cam_pin_spec import (
    CAP_RADIUS_TOLERANCE_MM,
    CAP_SAG,
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    DRAWING_PRECISION,
    ISOMETRIC_VIEW_NOTE,
    PIN_DIA,
    PIN_DIA_BAND,
    PIN_LEN,
    PIN_LENGTH_TOLERANCE_MM,
    SURFACE_FINISHES,
)

PART_NAME = "pinion-cam-pin"
MATERIAL = "Plain Carbon Steel"  # bright steel, like the rods it works with
_SAVED_DRAWING_PROPERTIES = (
    "Number",
    "Material Specification",
    "Finish",
    "Quantity",
    "Manufacturing Notes",
    "Isometric View Note",
)

PIN_R = PIN_DIA / 2.0
CAP_R = (PIN_R**2 + CAP_SAG**2) / (2.0 * CAP_SAG)  # 2.9
V_CAP = math.pi * CAP_SAG**2 * (3.0 * CAP_R - CAP_SAG) / 3.0  # 5.29
V_PIN = math.pi * PIN_R**2 * PIN_LEN


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import RevolveParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations). The mm suffix is load-bearing (INCH
    # document; the equation manager reads bare numbers in document units).
    await set_global(adapter, "PinDia", f"{PIN_DIA}mm")
    await set_global(adapter, "PinLen", f"{PIN_LEN}mm")
    await set_global(adapter, "CapSag", f"{CAP_SAG}mm")

    drive_jobs: list[tuple[str, str]] = []

    # Shank half-profile on the Right plane (sketch u -> model -Z, v -> model
    # Y; the crank-pinion-pin idiom): the axis centerline from the seated end
    # at the origin to the crown root, and the rectangle above it.  Its two
    # dimensions are the print's two -- the length along the outline, the
    # diameter as a doubled centerline-to-outline dim -- so both import into
    # the *Right side view.
    pin = SketchDims()
    check("create_sketch pin", await adapter.create_sketch("Right"))
    set_sketch_direct_db(adapter, True)
    axis = check("axis centerline", await adapter.add_centerline(0.0, 0.0, -PIN_LEN, 0.0))
    profile_pts = [(0.0, 0.0), (0.0, PIN_R), (-PIN_LEN, PIN_R), (-PIN_LEN, 0.0)]
    profile_lines = await add_line_chain(adapter, profile_pts)
    set_sketch_direct_db(adapter, False)
    n = len(profile_lines)
    for i, line in enumerate(profile_lines):
        (_, y1), (_, y2) = profile_pts[i], profile_pts[(i + 1) % n]
        direction = "horizontal" if y1 == y2 else "vertical"
        check(
            f"pin {direction} {line}",
            await adapter.add_sketch_constraint(line, None, direction),
        )
    outline = profile_lines[1]
    await dimension_between(
        adapter,
        f"{outline}.start",
        f"{outline}.end",
        "horizontal_distance",
        PIN_LEN,
        "pin Depth",
    )
    pin.record("Depth", '"PinLen"')
    await add_diametric_linear_dimension(
        adapter, axis, outline, (-PIN_LEN / 4.0, PIN_R + 4.0), "PinDia"
    )
    pin.record("PinDia", '"PinDia"')
    await anchor_point_to_origin(
        adapter, f"{profile_lines[0]}.start", 0.0, 0.0, "pin seated end"
    )
    await ensure_fully_defined(adapter, "pin sketch")
    check("exit_sketch pin", await adapter.exit_sketch())
    name_last_feature(adapter, "PinProfile")
    drive_jobs += pin.apply(adapter, "PinProfile")
    check("revolve pin", await adapter.create_revolve(RevolveParameters(angle=360.0)))
    name_last_feature(adapter, "Pin")
    volume = await volume_check(adapter, "pin", V_PIN, 0.005 * V_PIN)

    # Domed outer end on the same Right plane (the MHA-060 back-cap idiom;
    # rim -> apex is the minor CCW lobe at a +Z end, u = -z).
    u_base, u_apex = -PIN_LEN, -(PIN_LEN + CAP_SAG)
    u_centre = -(PIN_LEN + CAP_SAG - CAP_R)
    cap = SketchDims()
    check("create_sketch cap", await adapter.create_sketch("Right"))
    set_sketch_direct_db(adapter, True)
    check("cap centerline", await adapter.add_centerline(u_base, 0.0, u_apex, 0.0))
    base = check("cap base", await adapter.add_line(u_base, 0.0, u_base, PIN_R))
    arc = check(
        "cap arc",
        await adapter.add_arc(u_centre, 0.0, u_base, PIN_R, u_apex, 0.0),
    )
    close = check("cap close", await adapter.add_line(u_apex, 0.0, u_base, 0.0))
    set_sketch_direct_db(adapter, False)
    check(
        "cap base vertical",
        await adapter.add_sketch_constraint(base, None, "vertical"),
    )
    check(
        "cap close horizontal",
        await adapter.add_sketch_constraint(close, None, "horizontal"),
    )
    check(
        "cap rim reach",
        await adapter.add_sketch_dimension(
            f"{base}.end", "origin", "vertical_distance", PIN_R
        ),
    )
    cap.record("CapRim", '"PinDia" / 2')
    check(
        "cap sagitta",
        await adapter.add_sketch_dimension(
            f"{close}.start", f"{close}.end", "horizontal_distance", CAP_SAG
        ),
    )
    cap.record("CapSagDim", '"CapSag"')
    check(
        "cap on axis",
        await adapter.add_sketch_constraint(
            f"{base}.start", "origin", "horizontal_points"
        ),
    )
    check(
        "cap station",
        await adapter.add_sketch_dimension(
            f"{base}.start", "origin", "horizontal_distance", PIN_LEN
        ),
    )
    cap.record("CapZ", '"PinLen"')
    check(
        "cap radius",
        await adapter.add_sketch_dimension(arc, None, "radial", CAP_R),
    )
    cap.record(
        "CapR",
        '("PinDia" / 2 * "PinDia" / 2 + "CapSag" * "CapSag") / (2 * "CapSag")',
    )
    await ensure_fully_defined(adapter, "cap sketch")
    check("exit_sketch cap", await adapter.exit_sketch())
    name_last_feature(adapter, "CapProfile")
    drive_jobs += cap.apply(adapter, "CapProfile")
    check("revolve cap", await adapter.create_revolve(RevolveParameters(angle=360.0)))
    name_last_feature(adapter, "Cap")
    volume = await volume_check(adapter, "cap", volume + V_CAP, 0.03 * V_CAP)

    # Named central axis (Axis1): mates coaxial to the strap's blind edge-bore
    # axis in the assembly, riding the p2 swing group.
    await name_bore_axis(adapter, "Right Plane", 0.0, "Top Plane", 0.0, "pin axis")

    # Deferred drive equations, then re-check neutrality (each evaluates to the
    # as-built value, so the geometry must not move).
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(adapter, "driven pin (equations neutral)", volume, 0.005 * V_PIN)

    # Manufacturing drawing support: mark exactly the print's dimensions and
    # stamp the make-critical title-block properties.
    set_dimension_bilateral_tolerance(
        adapter, "PinProfile", "PinDia", *deviations(PIN_DIA_BAND)
    )
    set_dimension_symmetric_tolerance(
        adapter, "PinProfile", "Depth", PIN_LENGTH_TOLERANCE_MM
    )
    set_dimension_symmetric_tolerance(
        adapter, "CapProfile", "CapR", CAP_RADIUS_TOLERANCE_MM
    )
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    author_part_pmi(adapter, surface_finishes=SURFACE_FINISHES)

    await apply_material(adapter, MATERIAL)
    await apply_color(adapter, POLISHED_STEEL)
    await report_mass_properties(adapter)
    apply_drawing_properties(
        adapter,
        PART_NAME,
        {
            "Manufacturing Notes": DRAWING_NOTES,
            "Isometric View Note": ISOMETRIC_VIEW_NOTE,
        },
    )
    artefacts = await save_part_and_images(adapter, PART_NAME)
    require_saved_drawing_properties(adapter, _SAVED_DRAWING_PROPERTIES)
    return artefacts


if __name__ == "__main__":
    sys.exit(run_build(build))
