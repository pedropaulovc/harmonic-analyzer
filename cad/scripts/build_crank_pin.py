r"""Reproduction script: crank tapered pin (book ch. 11, pp. 14-15).

The removable tapered pin that affixes the crank arm to the crankshaft —
pulled to swap the crankshaft gear. The ch11 close-ups (page001_img02 hero,
page002_img01 isolated pin) show four turned regions on one axis: the 1:48
tapered barrel with a bullet-nose small end, a turned neck carrying the
brass pull ring through a Ø2 cross-hole, and a short Ø8 cylindrical
mushroom pull-head with a full-radius domed front.

Dimensions: crank_pin_spec.py (photo-scaled, low, except the 1:48 taper
convention, med).

Layout: pin axis along +X, barrel big-end face at x=0 (small end at
x=45); the neck spans -3..0 and the head -9..-3, so the seated assembly
pose is expressed directly as the big-end-face station.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_crank_pin.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    POLISHED_STEEL,
    SketchDims,
    add_line_chain,
    apply_color,
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
    set_sketch_direct_db,
    volume_check,
)
from _drawing_marks import (
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from _holes import cross_hole_volume_mm3
from _saved_part_guard import require_saved_drawing_properties
from crank_pin_spec import (
    BIG_END_DIA,
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    END_VIEW_NOTE,
    HEAD_DIA,
    HEAD_DOME_R,
    HEAD_LEN,
    NECK_DIA,
    NECK_LEN,
    PIN_LENGTH,
    RING_HOLE_DIA,
    SMALL_END_DIA,
    TIP_DOME_R,
)

PART_NAME = "crank-pin"
MATERIAL = "Plain Carbon Steel"  # see _common.apply_material docstring


def _dome_fillet_volume(body_r: float, r: float) -> float:
    """Removed volume of a radius-r fillet on a body_r cylinder's end rim.

    Pappus over the corner cross-section (square r^2 minus the quarter
    disc), centroid measured inward from the wall (the cone-lock-knob
    dome-crown idiom).
    """
    area = r * r * (1.0 - math.pi / 4.0)
    sq = r * r * (r / 2.0)
    disc = (math.pi * r * r / 4.0) * (r - 4.0 * r / (3.0 * math.pi))
    x_bar = (sq - disc) / area
    return 2.0 * math.pi * (body_r - x_bar) * area


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters, RevolveParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations): length + the two end diameters, plus
    # the pull-hardware turns. The mm suffix is load-bearing (INCH document;
    # the equation manager reads bare numbers in document units).
    await set_global(adapter, "PinLength", f"{PIN_LENGTH}mm")
    await set_global(adapter, "BigEndDia", f"{BIG_END_DIA}mm")
    await set_global(adapter, "SmallEndDia", f"{SMALL_END_DIA}mm")
    await set_global(adapter, "NeckDia", f"{NECK_DIA}mm")
    await set_global(adapter, "NeckLen", f"{NECK_LEN}mm")
    await set_global(adapter, "HeadDia", f"{HEAD_DIA}mm")
    await set_global(adapter, "RingHoleDia", f"{RING_HOLE_DIA}mm")

    drive_jobs: list[tuple[str, str]] = []

    profile = SketchDims()
    check("create_sketch profile", await adapter.create_sketch("Front"))
    # Direct-to-DB: inferencing would snap the ~0.6 deg taper line to an
    # auto "horizontal" relation, flattening the frustum into a cylinder.
    set_sketch_direct_db(adapter, True)
    centerline = check(
        "add_centerline axis",
        await adapter.add_centerline(0.0, 0.0, PIN_LENGTH, 0.0),
    )
    lines = await add_line_chain(
        adapter,
        [
            (0.0, 0.0),
            (0.0, BIG_END_DIA / 2.0),
            (PIN_LENGTH, SMALL_END_DIA / 2.0),
            (PIN_LENGTH, 0.0),
        ],
    )
    set_sketch_direct_db(adapter, False)
    big_end, _taper, small_end, _axis_closure = lines
    # 8-DOF profile: the centerline merged into the (0, 0) /
    # (PIN_LENGTH, 0) chain ends, so horizontal + a length dim on it keep
    # the small end on the axis; the taper line rides its pinned
    # neighbours (no h/v on it -- that is the whole point of the frustum).
    check(
        "anchor big end",
        await adapter.add_sketch_constraint(f"{big_end}.start", "origin", "coincident"),
    )
    check(
        "axis horizontal",
        await adapter.add_sketch_constraint(centerline, None, "horizontal"),
    )
    # Record each manual dim into SketchDims as it is added (creation order):
    # length, then big-end radius, then small-end radius -- three display dims.
    check(
        "pin length",
        await adapter.add_sketch_dimension(centerline, None, "linear", PIN_LENGTH),
    )
    profile.record("Length", '"PinLength"')
    for label, ent, radius, name, drive in (
        ("big end", big_end, BIG_END_DIA / 2.0, "BigRadius", '"BigEndDia" / 2'),
        ("small end", small_end, SMALL_END_DIA / 2.0, "SmallRadius", '"SmallEndDia" / 2'),
    ):
        check(
            f"{label} vertical",
            await adapter.add_sketch_constraint(ent, None, "vertical"),
        )
        check(
            f"{label} radius",
            await adapter.add_sketch_dimension(ent, None, "linear", radius),
        )
        profile.record(name, drive)
    await ensure_fully_defined(adapter, "pin profile")
    check("exit_sketch profile", await adapter.exit_sketch())
    name_last_feature(adapter, "PinProfile")
    drive_jobs += profile.apply(adapter, "PinProfile")

    check(
        "revolve pin",
        await adapter.create_revolve(RevolveParameters(angle=360.0)),
    )
    name_last_feature(adapter, "Pin")

    # Conical frustum: V = pi*h/3 * (R1^2 + R1*R2 + R2^2).
    r1, r2 = BIG_END_DIA / 2.0, SMALL_END_DIA / 2.0
    v_pin = math.pi * PIN_LENGTH / 3.0 * (r1 * r1 + r1 * r2 + r2 * r2)
    await volume_check(adapter, "pin", v_pin, 0.005 * v_pin)
    expected = v_pin

    # Neck -3..0: Right-plane sketch (perpendicular to the pin axis), on-axis
    # circle, extruded -X from the barrel's big-end face. flip=True mirrors the
    # extrude to the -X side of the plane (verified by the merged-volume check:
    # a +X neck would vanish inside the barrel and fail loud).
    neck_dims = SketchDims()
    check("create_sketch neck", await adapter.create_sketch("Right"))
    await define_circle(
        adapter, 0.0, 0.0, NECK_DIA / 2.0, "neck", dims=neck_dims,
        names=("NeckCx", "NeckCy", "NeckDia"),
        drives=(None, None, '"NeckDia"'),
    )
    await ensure_fully_defined(adapter, "neck sketch")
    check("exit_sketch neck", await adapter.exit_sketch())
    name_last_feature(adapter, "NeckProfile")
    drive_jobs += neck_dims.apply(adapter, "NeckProfile")
    extrude_at_offset(adapter, NECK_LEN, 0.0, flip=True)
    name_last_feature(adapter, "Neck")
    expected += math.pi * (NECK_DIA / 2.0) ** 2 * NECK_LEN
    await volume_check(adapter, "neck", expected, 0.4)

    # Mushroom pull-head -9..-3 (same Right-plane on-axis circle idiom).
    head_dims = SketchDims()
    check("create_sketch head", await adapter.create_sketch("Right"))
    await define_circle(
        adapter, 0.0, 0.0, HEAD_DIA / 2.0, "head", dims=head_dims,
        names=("HeadCx", "HeadCy", "HeadDia"),
        drives=(None, None, '"HeadDia"'),
    )
    await ensure_fully_defined(adapter, "head sketch")
    check("exit_sketch head", await adapter.exit_sketch())
    name_last_feature(adapter, "HeadProfile")
    drive_jobs += head_dims.apply(adapter, "HeadProfile")
    extrude_at_offset(adapter, HEAD_LEN, NECK_LEN, flip=True)
    name_last_feature(adapter, "Head")
    expected += math.pi * (HEAD_DIA / 2.0) ** 2 * HEAD_LEN
    await volume_check(adapter, "head", expected, 1.6)

    # Domes: near-full-radius rim fillet on the head's front face (the
    # photographed mushroom dome) and a bullet-nose fillet on the small end.
    check(
        "fillet head dome",
        await adapter.add_fillet(
            HEAD_DOME_R, [[-(NECK_LEN + HEAD_LEN), HEAD_DIA / 2.0, 0.0]]
        ),
    )
    name_last_feature(adapter, "HeadDome")
    expected -= _dome_fillet_volume(HEAD_DIA / 2.0, HEAD_DOME_R)
    await volume_check(adapter, "head dome", expected, 1.0)
    check(
        "fillet tip nose",
        await adapter.add_fillet(TIP_DOME_R, [[PIN_LENGTH, SMALL_END_DIA / 2.0, 0.0]]),
    )
    name_last_feature(adapter, "TipNose")
    expected -= _dome_fillet_volume(SMALL_END_DIA / 2.0, TIP_DOME_R)
    await volume_check(adapter, "tip nose", expected, 1.5)

    # Ring cross-hole through the neck (Front-plane circle at mid-neck, cut
    # both directions -- only the neck lies in its path).
    ring_dims = SketchDims()
    check("create_sketch ring hole", await adapter.create_sketch("Front"))
    await define_circle(
        adapter, -NECK_LEN / 2.0, 0.0, RING_HOLE_DIA / 2.0, "ring hole",
        dims=ring_dims,
        names=("RingHoleX", "RingHoleY", "RingHoleDia"),
        # The station dim is unsigned in SolidWorks (the -1.5 renders as 1.5
        # with the direction geometric), so it stays a static dim -- only the
        # diameter is knob-driven.
        drives=(None, None, '"RingHoleDia"'),
    )
    await ensure_fully_defined(adapter, "ring hole sketch")
    check("exit_sketch ring hole", await adapter.exit_sketch())
    name_last_feature(adapter, "RingHoleProfile")
    drive_jobs += ring_dims.apply(adapter, "RingHoleProfile")
    check(
        "cut ring hole",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=2.0 * NECK_DIA, both_directions=True)
        ),
    )
    name_last_feature(adapter, "RingHole")
    expected -= cross_hole_volume_mm3(RING_HOLE_DIA, NECK_DIA)
    await volume_check(adapter, "ring hole", expected, 0.5)
    v_pin = expected

    # Deferred drive equations, then re-check neutrality (each evaluates to the
    # as-built value, so the geometry must not move).
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(adapter, "driven pin (equations neutral)", v_pin, 0.005 * v_pin)

    await apply_material(adapter, MATERIAL)
    # Photo: the turned pull head/neck read bright-polished (page002_img01);
    # the bare carbon-steel appearance renders the domed head near-black.
    await apply_color(adapter, POLISHED_STEEL)
    await report_mass_properties(adapter)
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    apply_drawing_properties(
        adapter,
        PART_NAME,
        {
            "Manufacturing Notes": DRAWING_NOTES,
            "End View Note": END_VIEW_NOTE,
        },
    )
    artefacts = await save_part_and_images(adapter, PART_NAME)
    require_saved_drawing_properties(
        adapter,
        (
            "Number", "Material Specification", "Finish", "Quantity",
            "Manufacturing Notes", "End View Note",
        ),
    )
    return artefacts


if __name__ == "__main__":
    sys.exit(run_build(build))
