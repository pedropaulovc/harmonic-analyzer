r"""Reproduction script: rocker arm (book ch. 14, pp. 26-29; 20 used).

Thin matte-black steel strap on the common pivot shaft.  Its tail keeps the
ch30-derived concentric R800/R816 edges, tapered closure, and 5.588 mm radial
land.  The rod side is intentionally asymmetric: both arcs stop at a square
full-depth shoulder 5 mm before the retained pin, then a 5 mm-deep tongue
centred on that pin runs to a square free face 6 mm beyond it.  The tongue fits
the connecting rod's photographed two-prong clevis with 0.20 mm clearance per
broad face.

The 2.5 mm plate thickness, integral pivot hub, pivot bore, and #47 rod-pin
bore remain unchanged.  ROD_HOLE_X/Y preserve the level-arm, plumb-rod closure;
only the obsolete long rod-side taper/land boundary is replaced.

Dimensions: cad/config/dimensions.yaml, Chapter 14.  Arc radii and source master
spans come from the ch30 back view; the reduced tongue is photo-bounded by the
ch14 joint views.

Layout: pivot at the origin, tail at -X, connecting-rod tongue at +X, shared arc
centre 816 mm above the bottom datum, and all bores along local Z.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_rocker_arm.py
"""

from __future__ import annotations

import math
import sys


from _common import (
    SketchDims,
    anchor_point_to_origin,
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
    set_sketch_direct_db,
    volume_check,
)
from _holes import NUMBER_DRILL_MM, HoleSpec, wizard_holes
from _drawing_marks import (
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from _part_pmi import author_part_pmi
from _saved_part_guard import require_saved_drawing_properties
from rocker_arm_notes import DRAWING_NOTES, ISOMETRIC_VIEW_NOTE
from rocker_arm_notes import DRAWING_DIMENSIONS
from rocker_arm_spec import (
    ARM_DEPTH,
    ARM_THICKNESS,
    BOT_ARC_LEN,
    BOT_END_X,
    BOT_END_Y,
    CENTER_Y,
    CURVE_RADIUS,
    HUB_DIA,
    HUB_LENGTH,
    PIVOT_HOLE_DIA,
    R_BOTTOM,
    R_TOP,
    ROD_HOLE_ABOVE_BOTTOM,  # noqa: F401 -- re-exported for contract tests
    ROD_HOLE_X,
    ROD_HOLE_Y,
    ROD_STEP_BOTTOM_Y,
    ROD_STEP_FROM_PIN,
    ROD_STEP_TOP_Y,
    ROD_STEP_X,
    ROD_TONGUE_BEYOND_PIN,
    ROD_TONGUE_BOTTOM_Y,
    ROD_TONGUE_DEPTH,
    ROD_TONGUE_END_X,
    ROD_TONGUE_TOP_Y,
    SURFACE_FINISHES,
    TAIL_TIP_FACE,
    TAIL_TIP_X,
    TAIL_TIP_Y,
    TOP_ARC_LEN,
    TOP_END_X,
    TOP_END_Y,
)
import _config


PART_NAME = "rocker-arm"
MATERIAL = "Plain Carbon Steel"  # see _common.apply_material docstring

# The hub length is the station pitch: neighbouring arm hubs touch face to face.
if abs(HUB_LENGTH - _config.machine("channels", "station_pitch_mm")) > 1e-6:
    raise AssertionError(
        "rocker_arm_spec.HUB_LENGTH must equal the channel station pitch"
    )
HUB_PROUD = (HUB_LENGTH - ARM_THICKNESS) / 2.0
THROUGH_CUT_DEPTH = 20.0

_ALPHA_TOP = (TOP_ARC_LEN / 2.0) / R_TOP
_ALPHA_BOT = (BOT_ARC_LEN / 2.0) / R_BOTTOM
_ROD_ALPHA_TOP = math.asin(ROD_STEP_X / R_TOP)
_ROD_ALPHA_BOT = math.asin(ROD_STEP_X / R_BOTTOM)


def _bottom_point(x: float) -> tuple[float, float]:
    return (x, CENTER_Y - math.sqrt(R_BOTTOM**2 - x * x))


def _mid_y(x: float) -> float:
    by = _bottom_point(x)[1]
    ty = CENTER_Y - math.sqrt(R_TOP**2 - x * x)
    return (by + ty) / 2.0


def _strap_area() -> float:
    """Analytic profile area by shoelace over densely sampled circular edges.

    Boundary: rod shoulder bottom -> bottom arc -> tail tapered face -> retained
    tail radial land -> top arc -> rod shoulder top -> tongue top -> square free
    face -> tongue bottom -> rod shoulder bottom.
    """
    n = 200
    pts: list[tuple[float, float]] = []
    for i in range(n + 1):
        a = _ROD_ALPHA_BOT + (-_ALPHA_BOT - _ROD_ALPHA_BOT) * i / n
        pts.append((R_BOTTOM * math.sin(a), CENTER_Y - R_BOTTOM * math.cos(a)))
    pts.append((TAIL_TIP_X, TAIL_TIP_Y))
    for i in range(n + 1):
        a = -_ALPHA_TOP + (_ROD_ALPHA_TOP + _ALPHA_TOP) * i / n
        pts.append((R_TOP * math.sin(a), CENTER_Y - R_TOP * math.cos(a)))
    pts.extend(
        (
            (ROD_STEP_X, ROD_TONGUE_TOP_Y),
            (ROD_TONGUE_END_X, ROD_TONGUE_TOP_Y),
            (ROD_TONGUE_END_X, ROD_TONGUE_BOTTOM_Y),
            (ROD_STEP_X, ROD_TONGUE_BOTTOM_Y),
        )
    )
    area = 0.0
    for i in range(len(pts)):
        x1, y1 = pts[i]
        x2, y2 = pts[(i + 1) % len(pts)]
        area += x1 * y2 - x2 * y1
    return abs(area) / 2.0


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Editable primitives and derived boundary globals.  Units are explicit
    # because the document is inch-based.  The arc endpoint trig remains folded
    # in Python: live dimensionless trig is unreliable in the SW equation manager.
    await set_global(adapter, "CurveRadius", f"{CURVE_RADIUS}mm")
    await set_global(adapter, "ArmDepth", f"{ARM_DEPTH}mm")
    await set_global(adapter, "ArmThickness", f"{ARM_THICKNESS}mm")
    await set_global(adapter, "TailTipFace", f"{TAIL_TIP_FACE}mm")
    await set_global(adapter, "PivotHoleDia", f"{PIVOT_HOLE_DIA}mm")
    await set_global(adapter, "HubDia", f"{HUB_DIA}mm")
    await set_global(adapter, "HubLength", f"{HUB_LENGTH}mm")
    await set_global(adapter, "RodHoleX", f"{ROD_HOLE_X}mm")
    await set_global(adapter, "RodHoleY", f"{ROD_HOLE_Y}mm")
    await set_global(adapter, "RodStepFromPin", f"{ROD_STEP_FROM_PIN}mm")
    await set_global(adapter, "RodTongueBeyondPin", f"{ROD_TONGUE_BEYOND_PIN}mm")
    await set_global(adapter, "RodTongueDepth", f"{ROD_TONGUE_DEPTH}mm")
    # Hole diameters remain owned by their native Hole Wizard/table features.
    await set_global(adapter, "ThroughCutDepth", f"{THROUGH_CUT_DEPTH}mm")
    await set_global(adapter, "RTop", '"CurveRadius"')
    await set_global(adapter, "RBottom", '"CurveRadius" + "ArmDepth"')
    await set_global(adapter, "CenterY", '"CurveRadius" + "ArmDepth"')
    await set_global(adapter, "TopEndX", f"{TOP_END_X}mm")
    await set_global(adapter, "BottomEndX", f"{BOT_END_X}mm")
    await set_global(adapter, "RodStepX", '"RodHoleX" - "RodStepFromPin"')
    await set_global(adapter, "RodTongueEndX", '"RodHoleX" + "RodTongueBeyondPin"')
    await set_global(adapter, "RodTongueTopY", '"RodHoleY" + "RodTongueDepth" / 2')
    await set_global(adapter, "RodTongueBottomY", '"RodHoleY" - "RodTongueDepth" / 2')

    # Each sketch DECLARES its dim names + drive equations as it records them; the
    # drive equations are collected here and applied in one deferred batch at the
    # end (every equation target must resolve against the finished model).
    drive_jobs: list[tuple[str, str]] = []

    tail_b = (-BOT_END_X, BOT_END_Y)
    rod_b = (ROD_STEP_X, ROD_STEP_BOTTOM_Y)
    tail_t = (-TOP_END_X, TOP_END_Y)
    rod_t = (ROD_STEP_X, ROD_STEP_TOP_Y)
    tail_tip = (TAIL_TIP_X, TAIL_TIP_Y)
    tongue_top_root = (ROD_STEP_X, ROD_TONGUE_TOP_Y)
    tongue_top_end = (ROD_TONGUE_END_X, ROD_TONGUE_TOP_Y)
    tongue_bottom_end = (ROD_TONGUE_END_X, ROD_TONGUE_BOTTOM_Y)
    tongue_bottom_root = (ROD_STEP_X, ROD_TONGUE_BOTTOM_Y)

    strap = SketchDims()
    check("create_sketch strap", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    entities = [
        check(
            "strap bottom arc",
            await adapter.add_arc(0.0, CENTER_Y, *tail_b, *rod_b),
        ),
        check(
            "strap top arc",
            await adapter.add_arc(0.0, CENTER_Y, *tail_t, *rod_t),
        ),
        check("rod top shoulder", await adapter.add_line(*rod_t, *tongue_top_root)),
        check(
            "rod tongue top", await adapter.add_line(*tongue_top_root, *tongue_top_end)
        ),
        check(
            "rod free end", await adapter.add_line(*tongue_top_end, *tongue_bottom_end)
        ),
        check(
            "rod tongue bottom",
            await adapter.add_line(*tongue_bottom_end, *tongue_bottom_root),
        ),
        check(
            "rod bottom shoulder", await adapter.add_line(*tongue_bottom_root, *rod_b)
        ),
        check("strap tail tip", await adapter.add_line(*tail_t, *tail_tip)),
        check("strap tail end", await adapter.add_line(*tail_tip, *tail_b)),
    ]
    set_sketch_direct_db(adapter, False)
    (
        bottom_arc,
        top_arc,
        rod_top_shoulder,
        rod_tongue_top,
        rod_free_end,
        rod_tongue_bottom,
        rod_bottom_shoulder,
        tail_tip_line,
        _tail_end,
    ) = entities
    # The tail retains the radial land and taper.  On the rod side both arcs
    # terminate at RodStepX; vertical shoulders enter a centred 5 mm tongue with
    # horizontal flanks and a square free-end datum face.
    await anchor_point_to_origin(
        adapter, f"{bottom_arc}.center", 0.0, CENTER_Y, "arc centre"
    )
    # CenterY is at +y, so the unsigned vertical_distance drives positive.
    strap.record("CenterY", '"CenterY"')
    check(
        "concentric arcs",
        await adapter.add_sketch_constraint(
            f"{top_arc}.center", f"{bottom_arc}.center", "coincident"
        ),
    )
    check(
        "bottom radius",
        await adapter.add_sketch_dimension(bottom_arc, None, "radial", R_BOTTOM),
    )
    strap.record("BottomRadius", '"RBottom"')
    check(
        "top radius",
        await adapter.add_sketch_dimension(top_arc, None, "radial", R_TOP),
    )
    strap.record("TopRadius", '"RTop"')
    # Tail endpoint magnitudes retain their source master spans.  Both rod-side
    # arc endpoints instead drive to the common square shoulder X.
    check(
        "bottom tail x",
        await adapter.add_sketch_dimension(
            f"{bottom_arc}.start", "origin", "horizontal_distance", BOT_END_X
        ),
    )
    strap.record("BottomTailX", '"BottomEndX"')
    check(
        "bottom rod shoulder x",
        await adapter.add_sketch_dimension(
            f"{bottom_arc}.end", "origin", "horizontal_distance", ROD_STEP_X
        ),
    )
    strap.record("BottomRodStepX", '"RodStepX"')
    check(
        "top tail x",
        await adapter.add_sketch_dimension(
            f"{top_arc}.start", "origin", "horizontal_distance", TOP_END_X
        ),
    )
    strap.record("TopTailX", '"TopEndX"')
    check(
        "top rod shoulder x",
        await adapter.add_sketch_dimension(
            f"{top_arc}.end", "origin", "horizontal_distance", ROD_STEP_X
        ),
    )
    strap.record("TopRodStepX", '"RodStepX"')

    check(
        "tail tip radial",
        await adapter.add_sketch_constraint(
            f"{top_arc}.center", tail_tip_line, "coincident"
        ),
    )
    check(
        "tail tip length",
        await adapter.add_sketch_dimension(
            tail_tip_line, None, "linear", TAIL_TIP_FACE
        ),
    )
    strap.record("TailTipLen", '"TailTipFace"')

    for label, entity, relation in (
        ("top shoulder", rod_top_shoulder, "vertical"),
        ("tongue top", rod_tongue_top, "horizontal"),
        ("free end", rod_free_end, "vertical"),
        ("tongue bottom", rod_tongue_bottom, "horizontal"),
        ("bottom shoulder", rod_bottom_shoulder, "vertical"),
    ):
        check(
            f"rod {label} {relation}",
            await adapter.add_sketch_constraint(entity, None, relation),
        )
    check(
        "rod tongue top height",
        await adapter.add_sketch_dimension(
            f"{rod_tongue_top}.start",
            "origin",
            "vertical_distance",
            ROD_TONGUE_TOP_Y,
        ),
    )
    strap.record("RodTongueTopY", '"RodTongueTopY"')
    check(
        "rod tongue end x",
        await adapter.add_sketch_dimension(
            f"{rod_tongue_top}.end",
            "origin",
            "horizontal_distance",
            ROD_TONGUE_END_X,
        ),
    )
    strap.record("RodTongueEndX", '"RodTongueEndX"')
    check(
        "rod tongue depth",
        await adapter.add_sketch_dimension(
            rod_free_end, None, "linear", ROD_TONGUE_DEPTH
        ),
    )
    strap.record("RodTongueDepth", '"RodTongueDepth"')
    await ensure_fully_defined(adapter, "strap sketch")
    check("exit_sketch strap", await adapter.exit_sketch())
    name_last_feature(adapter, "StrapProfile")
    drive_jobs += strap.apply(adapter, "StrapProfile")
    check(
        "extrude strap",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=ARM_THICKNESS, both_directions=True)
        ),
    )
    name_last_feature(adapter, "Strap")
    v_strap = _strap_area() * ARM_THICKNESS
    await volume_check(adapter, "strap", v_strap, 0.01 * v_strap)

    # Integral pivot hub (2026-09-02, ch14 p.28): a O10 boss coaxial with the
    # pivot bore, HUB_LENGTH long mid-plane (= the station pitch), so it stands
    # HUB_PROUD of each strap face and touches the neighbour arms' hubs. The
    # circle (r 5 about (0, ArmDepth/2)) lies inside the 16-deep strap, so the
    # boss only ADDS the two proud discs. Cut BEFORE the pivot hole so the bore
    # runs through hub + strap.
    hub = SketchDims()
    check("create_sketch hub", await adapter.create_sketch("Front"))
    await define_circle(
        adapter,
        0.0,
        _mid_y(0.0),
        HUB_DIA / 2.0,
        "hub",
        dims=hub,
        names=("HubX", "HubZ", "HubDia"),
        drives=(None, '"ArmDepth" / 2', '"HubDia"'),
    )
    await ensure_fully_defined(adapter, "hub sketch")
    check("exit_sketch hub", await adapter.exit_sketch())
    name_last_feature(adapter, "HubProfile")
    drive_jobs += hub.apply(adapter, "HubProfile")
    check(
        "extrude hub",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=HUB_LENGTH, both_directions=True)
        ),
    )
    name_last_feature(adapter, "Hub")
    drive_jobs.append(("D1@Hub", '"HubLength"'))
    v_hub = math.pi * (HUB_DIA / 2.0) ** 2 * (HUB_LENGTH - ARM_THICKNESS)
    await volume_check(adapter, "strap + hub", v_strap + v_hub, 0.01 * v_strap)

    # Pivot pin hole on the axis (x 0), mid-depth. On-axis centre: define_circle
    # records only the centre-Z dim (the X is a relation) + the diameter -- TWO
    # dims, so the "X" name/drive slot is ignored. The centre sits at
    # _mid_y(0) = ArmDepth/2 (positive), so its unsigned dim drives positive.
    pivot = SketchDims()
    check("create_sketch pivot hole", await adapter.create_sketch("Front"))
    await define_circle(
        adapter,
        0.0,
        _mid_y(0.0),
        PIVOT_HOLE_DIA / 2.0,
        "pivot hole",
        dims=pivot,
        names=("PivotX", "PivotZ", "PivotDia"),
        drives=(None, '"ArmDepth" / 2', '"PivotHoleDia"'),
    )
    await ensure_fully_defined(adapter, "pivot hole sketch")
    check("exit_sketch pivot hole", await adapter.exit_sketch())
    name_last_feature(adapter, "PivotHoleProfile")
    drive_jobs += pivot.apply(adapter, "PivotHoleProfile")
    check(
        "cut pivot hole",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=THROUGH_CUT_DEPTH, both_directions=True)
        ),
    )
    name_last_feature(adapter, "PivotHole")
    # Named axis through the pivot bore (Axis1): assembly mates select it by
    # NAME (Right ∩ Top+8), view-independent -- an internal bore wall never
    # selects by screen-projected point. See _common.name_bore_axis.
    await name_bore_axis(
        adapter, "Right Plane", 0.0, "Top Plane", _mid_y(0.0), "pivot bore"
    )

    # Connecting-rod pin hole centred in the reduced rod-side tongue.  The
    # retained (ROD_HOLE_X, ROD_HOLE_Y) keeps the pin 5.533 mm above the curved
    # bottom reference and preserves the level-arm/plumb-rod closure.  Native
    # Hole Wizard starts on the +Z face and drills inward through the 2.5 mm plate.
    rod_cut = wizard_holes(
        adapter,
        HoleSpec("drilled_number", "#47"),
        [[ROD_HOLE_X, ROD_HOLE_Y, ARM_THICKNESS / 2.0]],
        (0.0, 0.0, 1.0),
        "rod pin hole (#47)",
        name="RodHole",
        placement_dims=[(("RodPinX", '"RodHoleX"'), ("RodPinY", '"RodHoleY"'))],
    )
    drive_jobs += rod_cut.placement_drive_jobs
    # Named axis through the rod-pin bore (Axis2 = (Right+ROD_HOLE_X) ∩ (Top+hole_y)).
    await name_bore_axis(
        adapter,
        "Right Plane",
        ROD_HOLE_X,
        "Top Plane",
        ROD_HOLE_Y,
        "rod bore",
        drive_a='"RodHoleX"',
        drive_b='"RodHoleY"',
        drive_jobs=drive_jobs,
    )
    # Named axis on the R800 top-edge arc CENTRE (Axis3 = Right ∩ Top+816, a
    # free-space datum 808 above the pivot bore, along Z like the bores). The
    # channel assembly holds the amplitude bar's foot axis at its as-solved
    # radius from this line (the J5 foot-on-arc coupling), so swinging the
    # rocker drives the bar + channel lever. Tied to "CenterY" so a GUI edit
    # of the arc radius/depth moves the coupling with it.
    await name_bore_axis(
        adapter,
        "Right Plane",
        0.0,
        "Top Plane",
        CENTER_Y,
        "arc centre",
        drive_b='"CenterY"',
        drive_jobs=drive_jobs,
    )

    # The pivot bore runs the full hub length; the rod bore only the 2.5 strap.
    rod_dia = NUMBER_DRILL_MM["#47"]
    v_pivot = math.pi * (PIVOT_HOLE_DIA / 2.0) ** 2 * HUB_LENGTH
    v_rod = math.pi * (rod_dia / 2.0) ** 2 * ARM_THICKNESS
    # _strap_area already includes the retained tail land and stepped tongue
    # boundary, so the bored-strap volume gate remains analytic.
    v_measured = await volume_check(
        adapter, "bored strap + hub", v_strap + v_hub - v_pivot - v_rod, 0.01 * v_strap
    )

    # Apply the deferred drive equations now -- after the whole model + a rebuild
    # exists, so every target resolves. Each equation evaluates to the value just
    # built, so the geometry must not move -- the re-check below (tight, vs the
    # MEASURED pre-drive volume) is the proof.
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven rocker-arm (equations neutral)", v_measured, 0.005 * v_strap
    )

    await apply_material(adapter, MATERIAL)
    await report_mass_properties(adapter)

    # Manufacturing drawing support: mark exactly the print's dimensions (the
    # drawing recipe imports the marked set and must find every one of these),
    # and stamp the make-critical title-block properties.
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    author_part_pmi(adapter, surface_finishes=SURFACE_FINISHES)
    apply_drawing_properties(
        adapter,
        PART_NAME,
        {
            "Manufacturing Notes": DRAWING_NOTES,
            "Isometric View Note": ISOMETRIC_VIEW_NOTE,
        },
    )
    artefacts = await save_part_and_images(adapter, PART_NAME)
    require_saved_drawing_properties(
        adapter,
        (
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
            "Isometric View Note",
        ),
    )
    return artefacts


if __name__ == "__main__":
    sys.exit(run_build(build))
