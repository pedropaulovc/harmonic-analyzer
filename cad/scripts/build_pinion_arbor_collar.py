r"""Reproduction script: pinion-arbor collar (book ch. 25; MHA-144, R1a).

The ch25 photos show a sleeve on the arbor outboard of the front strap with a
flush pin end about 10 out (page001_img01, page002_img07).  User ruling R1a
(2026-09-24): a plain turned steel collar, Ø15 x 20 with a drilled Ø8 bore,
cross-pinned to MHA-102 with the rig's 1/16 in slotted spring pin through a
hole centred on its length.  It is a northward walk-out backstop behind the
drum's bond; the gap stack lives in ``pinion_arbor_collar_spec``.

Layout: bore axis Z through the origin, collar z 0..COLLAR_LEN; the pin hole
runs along local Y at z PIN_HOLE_Z -- the arbor's crossrod axis, so the
assembly places both parts in one frame.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_pinion_arbor_collar.py
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
    volume_check,
)
from _drawing_marks import (
    apply_drawing_precision,
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
    set_dimension_bilateral_tolerance,
)
from _fit_limits import deviations
from _named_views import name_octant_views
from _saved_part_guard import require_saved_drawing_properties
from _visibility import blank_reference_geometry
from pinion_arbor_collar_geometry import (
    BORE,
    COLLAR_LEN,
    COLLAR_OD,
    PIN_HOLE_Z,
)
from pinion_arbor_collar_spec import (
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    DRAWING_PRECISION,
    ISOMETRIC_VIEW_NOTE,
    PIN_HOLE,
    PIN_HOLE_BAND,
)

PART_NAME = "pinion-arbor-collar"
MATERIAL = "Plain Carbon Steel"  # AISI 1018 bar, as MHA-102
_SAVED_DRAWING_PROPERTIES = (
    "Number",
    "Material Specification",
    "Finish",
    "Quantity",
    "Manufacturing Notes",
    "Isometric View Note",
)

COLLAR_R = COLLAR_OD / 2.0
BORE_R = BORE / 2.0
PIN_R = PIN_HOLE / 2.0

V_COLLAR = math.pi * (COLLAR_R**2 - BORE_R**2) * COLLAR_LEN


def _pin_hole_removed() -> float:
    """Volume the through pin hole takes out of both walls: Simpson over x in
    [-pin_r, pin_r] of chord(x) along z times the wall depth along y."""
    n = 2000
    h = 2.0 * PIN_R / n

    def f(x: float) -> float:
        chord = 2.0 * math.sqrt(max(PIN_R**2 - x * x, 0.0))
        wall = math.sqrt(max(COLLAR_R**2 - x * x, 0.0)) - math.sqrt(
            max(BORE_R**2 - x * x, 0.0)
        )
        return chord * wall

    s = f(-PIN_R) + f(PIN_R)
    s += 4.0 * sum(f(-PIN_R + (2 * k - 1) * h) for k in range(1, n // 2 + 1))
    s += 2.0 * sum(f(-PIN_R + 2 * k * h) for k in range(1, n // 2))
    return 2.0 * s * h / 3.0


V_PIN_HOLE = _pin_hole_removed()


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations). The mm suffix is load-bearing (INCH
    # document; the equation manager reads bare numbers in document units).
    await set_global(adapter, "CollarOd", f"{COLLAR_OD}mm")
    await set_global(adapter, "CollarLen", f"{COLLAR_LEN}mm")
    await set_global(adapter, "BoreDia", f"{BORE}mm")
    await set_global(adapter, "PinHoleDia", f"{PIN_HOLE}mm")

    drive_jobs: list[tuple[str, str]] = []

    collar = SketchDims()
    check("create_sketch collar", await adapter.create_sketch("Front"))
    await define_circle(
        adapter,
        0.0,
        0.0,
        COLLAR_R,
        "collar",
        dims=collar,
        names=("CollarCx", "CollarCy", "CollarOd"),
        drives=(None, None, '"CollarOd"'),
    )
    await ensure_fully_defined(adapter, "collar sketch")
    check("exit_sketch collar", await adapter.exit_sketch())
    name_last_feature(adapter, "CollarProfile")
    drive_jobs += collar.apply(adapter, "CollarProfile")
    check(
        "extrude collar",
        await adapter.create_extrusion(ExtrusionParameters(depth=COLLAR_LEN)),
    )
    name_last_feature(adapter, "Collar")
    drive_jobs += [(name_dimensions(adapter, "Collar", ["Depth"])[0], '"CollarLen"')]
    v_solid = math.pi * COLLAR_R**2 * COLLAR_LEN
    await volume_check(adapter, "collar", v_solid, 0.005 * v_solid)

    bore = SketchDims()
    check("create_sketch bore", await adapter.create_sketch("Front"))
    await define_circle(
        adapter,
        0.0,
        0.0,
        BORE_R,
        "bore",
        dims=bore,
        names=("BoreCx", "BoreCy", "BoreDia"),
        drives=(None, None, '"BoreDia"'),
    )
    await ensure_fully_defined(adapter, "bore sketch")
    check("exit_sketch bore", await adapter.exit_sketch())
    name_last_feature(adapter, "BoreProfile")
    drive_jobs += bore.apply(adapter, "BoreProfile")
    check(
        "cut bore",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=2.5 * COLLAR_LEN, both_directions=True)
        ),
    )
    name_last_feature(adapter, "Bore")
    volume = await volume_check(adapter, "bore", V_COLLAR, 0.005 * V_COLLAR)

    # The spring-pin hole through both walls, on the Top plane through the
    # axis (sketch (u, v) -> (X, -Z)), centred on the length.
    pin = SketchDims()
    check("create_sketch pin hole", await adapter.create_sketch("Top"))
    await define_circle(
        adapter,
        0.0,
        -PIN_HOLE_Z,
        PIN_R,
        "pin hole",
        dims=pin,
        names=("PinHoleCx", "PinHoleCz", "PinHoleDia"),
        drives=(None, '"CollarLen" / 2', '"PinHoleDia"'),
    )
    await ensure_fully_defined(adapter, "pin-hole sketch")
    check("exit_sketch pin hole", await adapter.exit_sketch())
    name_last_feature(adapter, "PinHoleProfile")
    drive_jobs += pin.apply(adapter, "PinHoleProfile")
    check(
        "cut pin hole",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=COLLAR_OD + 2.0, both_directions=True)
        ),
    )
    name_last_feature(adapter, "PinHole")
    volume -= V_PIN_HOLE
    await volume_check(adapter, "pin hole", volume, 0.05 * V_PIN_HOLE)

    collar_axis = await name_bore_axis(
        adapter, "Top Plane", 0.0, "Right Plane", 0.0, "collar bore axis"
    )

    # Deferred drive equations, then re-check neutrality.
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven collar (equations neutral)", volume, 0.01 * V_COLLAR
    )

    # Manufacturing drawing support: only the pin hole's tighter band rides
    # the model.  The Ø8 bore is a plain drilled hole, so the title block's
    # DRILLED HOLES row governs it and the dimension restates nothing (policy
    # rule 1, Codex on #860).  The places are the part's (policy rule 2).
    set_dimension_bilateral_tolerance(
        adapter, "PinHoleProfile", "PinHoleDia", *deviations(PIN_HOLE_BAND)
    )
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    name_octant_views(adapter, label=PART_NAME)
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
            "Isometric View Note": ISOMETRIC_VIEW_NOTE,
        },
    )
    blank_reference_geometry(adapter, ((collar_axis, "AXIS"),))
    artefacts = await save_part_and_images(adapter, PART_NAME)
    require_saved_drawing_properties(adapter, _SAVED_DRAWING_PROPERTIES)
    return artefacts


if __name__ == "__main__":
    sys.exit(run_build(build))
