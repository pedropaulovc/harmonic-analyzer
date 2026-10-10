r"""Reproduction script: lever fulcrum shaft (MHA-CH-004; book ch. 17; 1 used).

Plain Ø6.35 (1/4") steel shaft: the top levers' common fulcrum at machine
(x, y) = (+199.9, 1061.4) (2026-08-02 top-frame rederive: rail top 1036.2 +
keeper axis rise 25.2). One diameter full length -- no journals, shoulders or
steps -- through the reamed bores of the two end keepers (MHA-CH-007). Each
end stands 0.5 past its keeper lug's outer face and finishes in a full
hemisphere (the bright dome of the ch. 17 p. 40 closeup): 161.35 tip to tip.
One set-screw flat per end, both on +Y, sits under the keeper's crown tap;
the two #1-72 cup-point set screws (MHA-VN-055) bearing on them are the
shaft's only axial and rotational location.

Dimensions: ``ch_fulcrum_shaft_spec`` (derived from ``ch_fulcrum_keeper_spec``);
cad/DIMENSIONS.md "Channel & top-frame layout".

Layout: shaft axis along Z, centred (tips at z +-80.675); flats face +Y. The
body is ONE Right-plane half-profile (two quarter-arc domes on a straight
O.D.) revolved about its on-axis close line (the mg_magnifying_lever capsule
idiom), so the diameter and tip-to-tip length import into the side view; the
two flats are one mid-plane cut from a second Right-plane sketch that also
carries the across-flat size.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_ch_fulcrum_shaft.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    SketchDims,
    _early_bound,
    add_line_chain,
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
)
from _fit_limits import deviations
from _part_pmi import author_part_pmi
from ch_fulcrum_shaft_spec import (
    ACROSS_FLAT,
    CYLINDER_HALF,
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    DRAWING_PRECISION,
    END_VIEW_NOTE,
    FLAT_DEPTH,
    FLAT_HEIGHT,
    FLAT_LENGTH,
    FLAT_PITCH,
    ISO_VIEW_NOTE,
    SHAFT_DIA,
    SHAFT_DIA_BAND,
    SHAFT_LENGTH,
    SHAFT_R,
    SURFACE_FINISHES,
)

PART_NAME = "ch-fulcrum-shaft"
MATERIAL = "Plain Carbon Steel"  # see _common.apply_material docstring

TIP = SHAFT_LENGTH / 2.0  # 80.675: dome apex off the centre
# Capsule: the straight O.D. between the dome centres plus one full sphere.
V_BODY = (
    math.pi * SHAFT_R**2 * (SHAFT_LENGTH - SHAFT_DIA) + 4.0 / 3.0 * math.pi * SHAFT_R**3
)
# Each flat removes a circular segment FLAT_DEPTH deep along FLAT_LENGTH of
# the straight O.D. (both lie inside z +-CYLINDER_HALF: the spec pins it).
_CHORD_OFFSET = SHAFT_R - FLAT_DEPTH
V_FLAT = FLAT_LENGTH * (
    SHAFT_R**2 * math.acos(_CHORD_OFFSET / SHAFT_R)
    - _CHORD_OFFSET * math.sqrt(SHAFT_R**2 - _CHORD_OFFSET**2)
)
# Flat rectangles: from the flat up past the O.D.; the cut runs mid-plane
# across the whole diameter.
FLAT_RECT_TOP = SHAFT_R + 0.5
FLAT_CUT_DEPTH = 2.0 * SHAFT_DIA


def _as_construction(adapter, entity_id: str) -> None:
    """Flag a registered sketch line as construction geometry (the setter is
    on ISketchSegment, not the ISketchLine the registry binds)."""
    segment = _early_bound(adapter._sketch_entities[entity_id], "ISketchSegment")
    segment.ConstructionGeometry = True
    if not bool(segment.ConstructionGeometry):
        raise RuntimeError(f"{entity_id} did not take the construction flag")


async def _shaft_profile(adapter) -> list[tuple[str, str]]:
    """The capsule half-profile, revolved into the body. Constraint accounting
    (12 point unknowns less the two arcs' equal-radius ties = 10): close line
    horizontal with the origin at its midpoint (3), O.D. line horizontal (1),
    each dome centre on the axis (2) and under its O.D. end (2), the
    tip-to-tip length (1) and the diameter (1)."""
    from solidworks_mcp.adapters.base import RevolveParameters

    dims = SketchDims()
    check("create_sketch shaft", await adapter.create_sketch("Right"))
    set_sketch_direct_db(adapter, True)
    axis = check(
        "shaft axis centerline", await adapter.add_centerline(-TIP, 0.0, TIP, 0.0)
    )
    top = check(
        "shaft O.D. line",
        await adapter.add_line(-CYLINDER_HALF, SHAFT_R, CYLINDER_HALF, SHAFT_R),
    )
    # add_arc sweeps CCW p1 -> p2: apex -> rim at +u, rim -> apex at -u.
    cap_pos = check(
        "shaft +u dome",
        await adapter.add_arc(CYLINDER_HALF, 0.0, TIP, 0.0, CYLINDER_HALF, SHAFT_R),
    )
    close = check("shaft close line", await adapter.add_line(TIP, 0.0, -TIP, 0.0))
    cap_neg = check(
        "shaft -u dome",
        await adapter.add_arc(-CYLINDER_HALF, 0.0, -CYLINDER_HALF, SHAFT_R, -TIP, 0.0),
    )
    set_sketch_direct_db(adapter, False)
    check(
        "shaft close horizontal",
        await adapter.add_sketch_constraint(close, None, "horizontal"),
    )
    check(
        "shaft centred on the origin",
        await adapter.add_sketch_constraint("origin", close, "midpoint"),
    )
    check(
        "shaft O.D. horizontal",
        await adapter.add_sketch_constraint(top, None, "horizontal"),
    )
    for cap, end, tag in ((cap_neg, "start", "-u"), (cap_pos, "end", "+u")):
        check(
            f"shaft {tag} dome centre on the axis",
            await adapter.add_sketch_constraint(
                f"{cap}.center", "origin", "horizontal_points"
            ),
        )
        check(
            f"shaft {tag} dome centre under the O.D. end",
            await adapter.add_sketch_constraint(
                f"{top}.{end}", f"{cap}.center", "vertical_points"
            ),
        )
    await dimension_between(
        adapter,
        f"{close}.start",
        f"{close}.end",
        "horizontal_distance",
        SHAFT_LENGTH,
        "shaft OverallLength",
    )
    dims.record("OverallLength", '"ShaftLength"')
    await add_diametric_linear_dimension(
        adapter, axis, top, (0.0, SHAFT_R + 5.0), "ShaftDia"
    )
    dims.record("ShaftDia", '"ShaftDia"')
    await ensure_fully_defined(adapter, "shaft sketch")
    check("exit_sketch shaft", await adapter.exit_sketch())
    name_last_feature(adapter, "ShaftProfile")
    drive_jobs = dims.apply(adapter, "ShaftProfile")
    check("revolve shaft", await adapter.create_revolve(RevolveParameters(angle=360.0)))
    name_last_feature(adapter, "Shaft")
    return drive_jobs


async def _flats(adapter) -> list[tuple[str, str]]:
    """The two set-screw flats: one mid-plane cut from two rectangles on the
    Right plane, each from the flat (v = FLAT_HEIGHT) up past the O.D.

    Constraint accounting (16 rectangle + 4 witness unknowns = 20): eight
    rectangle H/V relations; the +u flat's length, rise and station off the
    origin; the -u flat's length, rise, like-edge FlatPitch and flat-line
    alignment; and the construction witness from the +u flat's -u corner
    straight down to the far O.D. (vertical, under the corner, its foot
    ShaftDia/2 below the origin, its top on the axis) whose AcrossFlat dim
    sets both flats' height."""
    dims = SketchDims()
    half = FLAT_LENGTH / 2.0
    station = FLAT_PITCH / 2.0
    rect_pos = [
        (station - half, FLAT_HEIGHT),
        (station + half, FLAT_HEIGHT),
        (station + half, FLAT_RECT_TOP),
        (station - half, FLAT_RECT_TOP),
    ]
    rect_neg = [(u - FLAT_PITCH, v) for u, v in rect_pos]
    check("create_sketch flats", await adapter.create_sketch("Right"))
    set_sketch_direct_db(adapter, True)
    lines_pos = await add_line_chain(adapter, rect_pos)
    lines_neg = await add_line_chain(adapter, rect_neg)
    witness = check(
        "flat witness",
        await adapter.add_line(rect_pos[0][0], -SHAFT_R, rect_pos[0][0], 0.0),
    )
    set_sketch_direct_db(adapter, False)
    _as_construction(adapter, witness)
    for points, lines in ((rect_pos, lines_pos), (rect_neg, lines_neg)):
        for i, line in enumerate(lines):
            (_, v1), (_, v2) = points[i], points[(i + 1) % len(points)]
            direction = "horizontal" if v1 == v2 else "vertical"
            check(
                f"flat {direction} {line}",
                await adapter.add_sketch_constraint(line, None, direction),
            )
    check(
        "flat witness vertical",
        await adapter.add_sketch_constraint(witness, None, "vertical"),
    )
    flat_pos, rise_pos = lines_pos[0], lines_pos[1]
    flat_neg, rise_neg = lines_neg[0], lines_neg[1]
    corner = f"{flat_pos}.start"  # the +u flat's -u edge on the flat line
    await dimension_between(
        adapter,
        corner,
        f"{flat_pos}.end",
        "horizontal_distance",
        FLAT_LENGTH,
        "FlatLength",
    )
    dims.record("FlatLength", '"FlatLength"')
    await dimension_between(
        adapter,
        f"{rise_pos}.start",
        f"{rise_pos}.end",
        "vertical_distance",
        FLAT_RECT_TOP - FLAT_HEIGHT,
        "flat +u rise",
    )
    dims.record("FlatRise")
    await dimension_between(
        adapter,
        corner,
        "origin",
        "horizontal_distance",
        station - half,
        "flat station",
    )
    dims.record("FlatStation", '"FlatPitch" / 2 - "FlatLength" / 2')
    check(
        "flat witness under the corner",
        await adapter.add_sketch_constraint(
            f"{witness}.start", corner, "vertical_points"
        ),
    )
    await dimension_between(
        adapter,
        corner,
        f"{witness}.start",
        "vertical_distance",
        ACROSS_FLAT,
        "AcrossFlat",
    )
    dims.record("AcrossFlat", '"ShaftDia" - "FlatDepth"')
    await dimension_between(
        adapter,
        f"{witness}.start",
        "origin",
        "vertical_distance",
        SHAFT_R,
        "flat witness foot",
    )
    dims.record("WitnessFoot", '"ShaftDia" / 2')
    check(
        "flat witness top on the axis",
        await adapter.add_sketch_constraint(
            f"{witness}.end", "origin", "horizontal_points"
        ),
    )
    await dimension_between(
        adapter,
        f"{flat_neg}.start",
        f"{flat_neg}.end",
        "horizontal_distance",
        FLAT_LENGTH,
        "-u FlatLength",
    )
    dims.record("FlatLengthB", '"FlatLength"')
    await dimension_between(
        adapter,
        f"{rise_neg}.start",
        f"{rise_neg}.end",
        "vertical_distance",
        FLAT_RECT_TOP - FLAT_HEIGHT,
        "flat -u rise",
    )
    dims.record("FlatRiseB")
    # Like edge to like edge (each flat's -u end): the flat-centre spacing.
    await dimension_between(
        adapter,
        f"{flat_neg}.start",
        corner,
        "horizontal_distance",
        FLAT_PITCH,
        "FlatPitch",
    )
    dims.record("FlatPitch", '"FlatPitch"')
    check(
        "flats on one line",
        await adapter.add_sketch_constraint(
            f"{flat_neg}.start", corner, "horizontal_points"
        ),
    )
    await ensure_fully_defined(adapter, "flats sketch")
    check("exit_sketch flats", await adapter.exit_sketch())
    name_last_feature(adapter, "FlatProfile")
    drive_jobs = dims.apply(adapter, "FlatProfile")
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check(
        "cut flats",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=FLAT_CUT_DEPTH, both_directions=True)
        ),
    )
    name_last_feature(adapter, "SetScrewFlats")
    return drive_jobs


async def build(adapter) -> dict[str, str]:
    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations). The mm suffix is load-bearing -- this
    # is an INCH document and the equation manager reads BARE numbers in
    # document units (an unsuffixed 161.35 = 161.35 in).
    await set_global(adapter, "ShaftDia", f"{SHAFT_DIA}mm")
    await set_global(adapter, "ShaftLength", f"{SHAFT_LENGTH}mm")
    await set_global(adapter, "FlatLength", f"{FLAT_LENGTH}mm")
    await set_global(adapter, "FlatPitch", f"{FLAT_PITCH}mm")
    await set_global(adapter, "FlatDepth", f"{FLAT_DEPTH}mm")

    drive_jobs = await _shaft_profile(adapter)
    volume = await volume_check(adapter, "shaft", V_BODY, 0.005 * V_BODY)
    drive_jobs += await _flats(adapter)
    volume = await volume_check(
        adapter, "set-screw flats", volume - 2.0 * V_FLAT, 0.03 * 2.0 * V_FLAT
    )

    # Deferred drive equations, then re-check neutrality (each evaluates to the
    # as-built value, so the geometry must not move).
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven shaft (equations neutral)", volume, 0.001 * volume
    )

    # The levers ride this axis by name.  A point on the O.D. is a
    # view-dependent pick that grazes the silhouette in the standard views,
    # where the lever bores' edges sit 0.075 mm off it (#916).
    await name_bore_axis(adapter, "Right Plane", 0.0, "Top Plane", 0.0, "shaft axis")
    name_last_feature(adapter, "shaft axis")

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)
    set_dimension_bilateral_tolerance(
        adapter, "ShaftProfile", "ShaftDia", *deviations(SHAFT_DIA_BAND)
    )
    # Decimal places belong to the model dimension, not to the sheet.
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    # The bearing O.D.'s roughness lives on the MODEL as a plain annotation.
    author_part_pmi(adapter, surface_finishes=SURFACE_FINISHES)
    apply_drawing_properties(
        adapter,
        PART_NAME,
        {
            "Manufacturing Notes": DRAWING_NOTES,
            "End View Note": END_VIEW_NOTE,
            "Iso View Note": ISO_VIEW_NOTE,
        },
    )
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
