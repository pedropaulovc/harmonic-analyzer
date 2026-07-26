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
0.8, the rod-end crown idiom). Axisymmetric about its local x = 0.

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
    apply_color,
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
    set_sketch_direct_db,
    volume_check,
)
from _drawing_marks import (
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from _saved_part_guard import require_saved_drawing_properties
from pinion_cam_pin_spec import (
    CAP_SAG,
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    END_VIEW_NOTE,
    PIN_DIA,
    PIN_LEN,
)

PART_NAME = "pinion-cam-pin"
MATERIAL = "Plain Carbon Steel"  # bright steel, like the rods it works with
_SAVED_DRAWING_PROPERTIES = (
    "Number",
    "Material Specification",
    "Finish",
    "Quantity",
    "Manufacturing Notes",
    "End View Note",
)

PIN_R = PIN_DIA / 2.0
CAP_R = (PIN_R**2 + CAP_SAG**2) / (2.0 * CAP_SAG)  # 2.9
V_CAP = math.pi * CAP_SAG**2 * (3.0 * CAP_R - CAP_SAG) / 3.0  # 5.29
V_PIN = math.pi * PIN_R**2 * PIN_LEN


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters, RevolveParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations). The mm suffix is load-bearing (INCH
    # document; the equation manager reads bare numbers in document units).
    await set_global(adapter, "PinDia", f"{PIN_DIA}mm")
    await set_global(adapter, "PinLen", f"{PIN_LEN}mm")
    await set_global(adapter, "CapSag", f"{CAP_SAG}mm")

    drive_jobs: list[tuple[str, str]] = []

    # On-axis pin (origin centre), extruded root -> +Z.
    pin = SketchDims()
    check("create_sketch pin", await adapter.create_sketch("Front"))
    await define_circle(
        adapter, 0.0, 0.0, PIN_R, "pin", dims=pin,
        names=("PinCx", "PinCz", "PinDia"),
        drives=(None, None, '"PinDia"'),
    )
    await ensure_fully_defined(adapter, "pin sketch")
    check("exit_sketch pin", await adapter.exit_sketch())
    name_last_feature(adapter, "PinProfile")
    drive_jobs += pin.apply(adapter, "PinProfile")
    check(
        "extrude pin",
        await adapter.create_extrusion(ExtrusionParameters(depth=PIN_LEN)),
    )
    name_last_feature(adapter, "Pin")
    depth_dim = name_dimensions(adapter, "Pin", ["Depth"])
    drive_jobs += [(depth_dim[0], '"PinLen"')]
    volume = await volume_check(adapter, "pin", V_PIN, 0.005 * V_PIN)

    # Domed outer end (the arbor back-cap idiom; apex -> rim is the minor CCW
    # lobe at a +Z end).
    v_base, v_apex = -PIN_LEN, -(PIN_LEN + CAP_SAG)
    v_centre = -(PIN_LEN + CAP_SAG - CAP_R)
    cap = SketchDims()
    check("create_sketch cap", await adapter.create_sketch("Top"))
    set_sketch_direct_db(adapter, True)
    check("cap centerline", await adapter.add_centerline(0.0, v_base, 0.0, v_apex))
    base = check("cap base", await adapter.add_line(0.0, v_base, PIN_R, v_base))
    arc = check(
        "cap arc",
        await adapter.add_arc(0.0, v_centre, 0.0, v_apex, PIN_R, v_base),
    )
    close = check("cap close", await adapter.add_line(0.0, v_apex, 0.0, v_base))
    set_sketch_direct_db(adapter, False)
    check("cap base horizontal", await adapter.add_sketch_constraint(base, None, "horizontal"))
    check("cap close vertical", await adapter.add_sketch_constraint(close, None, "vertical"))
    check(
        "cap rim reach",
        await adapter.add_sketch_dimension(
            f"{base}.end", "origin", "horizontal_distance", PIN_R
        ),
    )
    cap.record("CapRim", '"PinDia" / 2')
    check(
        "cap sagitta",
        await adapter.add_sketch_dimension(
            f"{close}.start", f"{close}.end", "vertical_distance", CAP_SAG
        ),
    )
    cap.record("CapSagDim", '"CapSag"')
    check(
        "cap on axis",
        await adapter.add_sketch_constraint(f"{base}.start", "origin", "vertical_points"),
    )
    check(
        "cap station",
        await adapter.add_sketch_dimension(
            f"{base}.start", "origin", "vertical_distance", PIN_LEN
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
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)

    await apply_material(adapter, MATERIAL)
    await apply_color(adapter, POLISHED_STEEL)
    await report_mass_properties(adapter)
    apply_drawing_properties(
        adapter,
        PART_NAME,
        {
            "Manufacturing Notes": DRAWING_NOTES,
            "End View Note": END_VIEW_NOTE,
        },
    )
    artefacts = await save_part_and_images(adapter, PART_NAME)
    require_saved_drawing_properties(adapter, _SAVED_DRAWING_PROPERTIES)
    return artefacts


if __name__ == "__main__":
    sys.exit(run_build(build))
