r"""Build the rocker arm's rod-hole diamond pin (MHA-CH-006-TL-03; shop fixture).

A turned 4140 HT body (collar, neck and bonded slip-fit shank) with a bought
gauge pin bonded into its reamed bore; the pin's two stoned flats leave two
round lands that orient the rocker arm in its rod-pin hole
(``ch_rocker_arm_tl_diamond_pin_spec``). One is made.

Layout (the inventory's fixture frame): pin axis model +Z, origin at the neck
face, +Z down into the plate. Every body feature is a Front-plane circle: the
collar and shank extrude +Z by their stations from the neck face, the neck is
an annular cut +Z, the ream a cut +Z. The pin is a SEPARATE solid (bonded,
not merged): its lands extrude -Z by the land height, its bonded length +Z
inside the ream, and the flats cut -Z, where only the pin exists.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_ch_rocker_arm_tl_diamond_pin.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    SketchDims,
    _early_bound,
    add_line_chain,
    anchor_point_to_origin,
    apply_material,
    check,
    define_circle,
    dimension_between,
    drive_dimension,
    ensure_fully_defined,
    force_rebuild,
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
from _saved_part_guard import require_saved_drawing_properties
from ch_rocker_arm_tl_diamond_pin_spec import (
    COLLAR_DIA,
    COLLAR_END,
    COLLAR_END_BAND,
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    DRAWING_PRECISION,
    FLATS_AF,
    ISOMETRIC_VIEW_NOTE,
    LAND_BAND,
    LAND_DIA,
    LAND_HEIGHT,
    LAND_HEIGHT_BAND,
    NECK_DIA,
    NECK_LENGTH,
    OVERALL_LENGTH,
    PIN_LENGTH,
    REAM_BAND,
    REAM_DEPTH,
    REAM_DIA,
    SHANK_BAND,
    SHANK_DIA,
)

PART_NAME = "ch-rocker-arm-tl-diamond-pin"
MATERIAL = "Plain Carbon Steel"  # the registry row names the 4140 HT bar
_SAVED_DRAWING_PROPERTIES = (
    "Number",
    "Material Specification",
    "Finish",
    "Quantity",
    "Manufacturing Notes",
    "Isometric View Note",
)

NECK_RELIEF_DIA = COLLAR_DIA + 1.5  # annular cut's outer circle, clear of the collar
FLAT_REACH = 1.2  # flat-cut rectangle width beyond the flat, clear of the land
FLAT_SPAN = 3.0  # flat-cut rectangle height, clear of the land


def _area(dia: float) -> float:
    return math.pi * (dia / 2.0) ** 2


def _segment_area(radius: float, offset: float) -> float:
    """Area a flat at ``offset`` from the axis takes off a disc of ``radius``."""
    return radius**2 * math.acos(offset / radius) - offset * math.sqrt(radius**2 - offset**2)


V_COLLAR = _area(COLLAR_DIA) * COLLAR_END
V_SHANK = V_COLLAR + _area(SHANK_DIA) * (OVERALL_LENGTH - COLLAR_END)
V_NECK = V_SHANK - (_area(COLLAR_DIA) - _area(NECK_DIA)) * NECK_LENGTH
V_BODY = V_NECK - _area(REAM_DIA) * REAM_DEPTH
V_PIN = V_BODY + _area(LAND_DIA) * PIN_LENGTH
V_TOTAL = V_PIN - 2.0 * _segment_area(LAND_DIA / 2.0, FLATS_AF / 2.0) * LAND_HEIGHT


def _require_bodies(adapter, count: int, *, label: str) -> None:
    bodies = tuple(
        _early_bound(adapter.currentModel, "IPartDoc").GetBodies2(0, False) or ()
    )
    if len(bodies) != count:
        raise RuntimeError(f"{label}: expected {count} solid bodies, found {len(bodies)}")


async def _circle_sketch(
    adapter, label: str, dia: float, profile: str, name: str, drive: str, *, plane: str = "Front"
):
    dims = SketchDims()
    check(f"create_sketch {label}", await adapter.create_sketch(plane))
    await define_circle(
        adapter,
        0.0,
        0.0,
        dia / 2.0,
        label,
        dims=dims,
        names=(None, None, name),
        drives=(None, None, drive),
    )
    await ensure_fully_defined(adapter, f"{label} sketch")
    check(f"exit_sketch {label}", await adapter.exit_sketch())
    name_last_feature(adapter, profile)
    return dims.apply(adapter, profile)


async def _flats_sketch(adapter) -> list[tuple[str, str]]:
    """Two rectangles whose inner edges are the flats, centred by a
    construction line between the flats' midpoints (its length IS FlatsAF)."""
    c = FLATS_AF / 2.0
    outer = c + FLAT_REACH
    h = FLAT_SPAN / 2.0
    dims = SketchDims()
    check("create_sketch flats", await adapter.create_sketch("Front"))
    flats = []
    for side, points in (
        ("R", [(c, -h), (outer, -h), (outer, h), (c, h)]),
        ("L", [(-c, h), (-outer, h), (-outer, -h), (-c, -h)]),
    ):
        first, edge, second, flat = await add_line_chain(adapter, points)
        for line, direction in (
            (first, "horizontal"),
            (edge, "vertical"),
            (second, "horizontal"),
            (flat, "vertical"),
        ):
            check(
                f"flat {side} {direction} {line}",
                await adapter.add_sketch_constraint(line, None, direction),
            )
        await dimension_between(
            adapter, f"{first}.start", f"{first}.end", "horizontal_distance",
            FLAT_REACH, f"flat {side} reach",
        )
        dims.record(f"FlatReach{side}")
        await dimension_between(
            adapter, f"{flat}.start", f"{flat}.end", "vertical_distance",
            FLAT_SPAN, f"flat {side} span",
        )
        dims.record(f"FlatSpan{side}")
        flats.append(flat)
    (across,) = await add_line_chain(adapter, [(-c, 0.0), (c, 0.0)], close=False)
    segment = _early_bound(adapter._sketch_entities[across], "ISketchSegment")
    segment.ConstructionGeometry = True
    if not bool(segment.ConstructionGeometry):
        raise RuntimeError("flats across line did not take the construction flag")
    check(
        "flats across horizontal",
        await adapter.add_sketch_constraint(across, None, "horizontal"),
    )
    check(
        "flats across meets the right flat",
        await adapter.add_sketch_constraint(f"{across}.end", flats[0], "midpoint"),
    )
    check(
        "flats across meets the left flat",
        await adapter.add_sketch_constraint(f"{across}.start", flats[1], "midpoint"),
    )
    await dimension_between(
        adapter, f"{across}.start", f"{across}.end", "horizontal_distance",
        FLATS_AF, "across flats",
    )
    dims.record("FlatsAF", '"FlatsAF"')
    await anchor_point_to_origin(adapter, f"{across}.end", c, 0.0, "flats centre")
    dims.record("FlatsHalf", '"FlatsAF" / 2')
    await ensure_fully_defined(adapter, "flats sketch")
    check("exit_sketch flats", await adapter.exit_sketch())
    name_last_feature(adapter, "FlatsProfile")
    return dims.apply(adapter, "FlatsProfile")


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import CreatePlaneParameters, ExtrusionParameters

    check("create_part", await adapter.create_part())

    # The mm suffix is load-bearing: the equation manager reads bare numbers
    # in document units.
    for knob, value in (
        ("CollarDia", COLLAR_DIA),
        ("CollarEnd", COLLAR_END),
        ("ShankDia", SHANK_DIA),
        ("OverallLength", OVERALL_LENGTH),
        ("NeckDia", NECK_DIA),
        ("NeckLength", NECK_LENGTH),
        ("ReamDia", REAM_DIA),
        ("ReamDepth", REAM_DEPTH),
        ("LandDia", LAND_DIA),
        ("LandHeight", LAND_HEIGHT),
        ("FlatsAF", FLATS_AF),
    ):
        await set_global(adapter, knob, f"{value}mm")

    drive_jobs = await _circle_sketch(
        adapter, "collar", COLLAR_DIA, "CollarProfile", "CollarDia", '"CollarDia"'
    )
    check("extrude collar", await adapter.create_extrusion(ExtrusionParameters(depth=COLLAR_END)))
    name_last_feature(adapter, "Collar")
    drive_jobs.append((name_dimensions(adapter, "Collar", ["CollarEnd"])[0], '"CollarEnd"'))
    await volume_check(adapter, "collar", V_COLLAR, 0.005 * V_COLLAR)

    drive_jobs += await _circle_sketch(
        adapter, "shank", SHANK_DIA, "ShankProfile", "ShankDia", '"ShankDia"'
    )
    check(
        "extrude shank",
        await adapter.create_extrusion(ExtrusionParameters(depth=OVERALL_LENGTH)),
    )
    name_last_feature(adapter, "Shank")
    drive_jobs.append(
        (name_dimensions(adapter, "Shank", ["OverallLength"])[0], '"OverallLength"')
    )
    await volume_check(adapter, "shank", V_SHANK, 0.005 * V_SHANK)

    # The neck: an annulus cut from the neck face INTO the body (+Z, against
    # the cut default, so reversed explicitly; build_dt_cone_pivot_post).
    neck = SketchDims()
    check("create_sketch neck", await adapter.create_sketch("Front"))
    await define_circle(
        adapter, 0.0, 0.0, NECK_DIA / 2.0, "neck",
        dims=neck, names=(None, None, "NeckDia"), drives=(None, None, '"NeckDia"'),
    )
    await define_circle(
        adapter, 0.0, 0.0, NECK_RELIEF_DIA / 2.0, "neck relief",
        dims=neck, names=(None, None, "NeckReliefDia"), drives=(None, None, None),
    )
    await ensure_fully_defined(adapter, "neck sketch")
    check("exit_sketch neck", await adapter.exit_sketch())
    name_last_feature(adapter, "NeckProfile")
    drive_jobs += neck.apply(adapter, "NeckProfile")
    check(
        "cut neck",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=NECK_LENGTH, reverse_direction=True)
        ),
    )
    name_last_feature(adapter, "Neck")
    drive_jobs.append((name_dimensions(adapter, "Neck", ["NeckLength"])[0], '"NeckLength"'))
    await volume_check(adapter, "neck", V_NECK, 0.005 * V_NECK)

    drive_jobs += await _circle_sketch(
        adapter, "ream", REAM_DIA, "ReamProfile", "ReamDia", '"ReamDia"'
    )
    check(
        "cut ream",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=REAM_DEPTH, reverse_direction=True)
        ),
    )
    name_last_feature(adapter, "Ream")
    drive_jobs.append((name_dimensions(adapter, "Ream", ["ReamDepth"])[0], '"ReamDepth"'))
    await volume_check(adapter, "reamed body", V_BODY, 0.005 * V_BODY)
    _require_bodies(adapter, 1, label="body")

    # The bonded gauge pin: ONE separate solid (merge off), sketched on a
    # plane at the land tip and extruded +Z down into the ream by its length.
    check(
        "create_plane LandTipPlane",
        await adapter.create_plane(
            CreatePlaneParameters(mode="offset", base_plane="Front Plane", offset=-LAND_HEIGHT)
        ),
    )
    name_last_feature(adapter, "LandTipPlane")
    tip_dim = name_dimensions(adapter, "LandTipPlane", ["LandTipStation"])
    drive_jobs.append((tip_dim[0], '"LandHeight"'))
    drive_jobs += await _circle_sketch(
        adapter, "lands", LAND_DIA, "LandProfile", "LandDia", '"LandDia"', plane="LandTipPlane"
    )
    check(
        "extrude pin",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=PIN_LENGTH, merge_result=False)
        ),
    )
    name_last_feature(adapter, "Pin")
    name_dimensions(adapter, "Pin", ["PinLength"])
    await volume_check(adapter, "pin", V_PIN, 0.005 * V_PIN)
    _require_bodies(adapter, 2, label="body and pin")

    # The flats cut -Z (the cut default) from the neck face to the tip: only
    # the pin's lands live there, so the body is untouched; a pin extruded the
    # wrong way off its tip plane leaves nothing here and fails the volume.
    # The cut's depth IS the printed land height.
    drive_jobs += await _flats_sketch(adapter)
    check("cut flats", await adapter.create_cut_extrude(ExtrusionParameters(depth=LAND_HEIGHT)))
    name_last_feature(adapter, "Flats")
    drive_jobs.append((name_dimensions(adapter, "Flats", ["LandHeight"])[0], '"LandHeight"'))
    await volume_check(adapter, "diamond pin", V_TOTAL, 0.005 * V_TOTAL)
    _require_bodies(adapter, 2, label="diamond pin")

    await force_rebuild(adapter)
    for dimension_name, expression in drive_jobs:
        await drive_dimension(adapter, dimension_name, expression)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven diamond pin (equations neutral)", V_TOTAL, 0.005 * V_TOTAL
    )
    _require_bodies(adapter, 2, label="driven diamond pin")

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    for feature, dimension, band in (
        ("LandProfile", "LandDia", LAND_BAND),
        ("Flats", "LandHeight", LAND_HEIGHT_BAND),
        ("ShankProfile", "ShankDia", SHANK_BAND),
        ("ReamProfile", "ReamDia", REAM_BAND),
        ("Collar", "CollarEnd", COLLAR_END_BAND),
    ):
        set_dimension_bilateral_tolerance(adapter, feature, dimension, *deviations(band))
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
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
