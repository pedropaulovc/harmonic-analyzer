r"""Reproduction script: cone tip block (book ch. 12, p. 18; video 4/4 stills).

The small adjuster-support block at the thin end of the cone shaft. It stands
on the swing platform beside the pivot and carries the threaded, cup-ended
end-play adjuster; the external brass spacer supports the shaft at the south
face and the adjuster cup supports its tip. The block and whole cone set swing
as one unit about the platform's pivot axis.

Dimensions estimated from the p.18 top-down and the v4_t00393 still
(low). The adjuster axis above the block base is ADJUSTER_AXIS_HEIGHT; the platform
adds PLATE_T and the fit-up shim pack (SHIM_NOMINAL, U30) under the foot, and
ADJUSTER_AXIS_HEIGHT + SHIM_NOMINAL + PLATE_T must equal the drive height above
the base top -- asserted module-level in build_drive_train_assembly. One
hidden #6-32 socket head cap screw holds the foot down through the platform.

Layout: block standing on the Top plane, plan centred on the origin,
adjuster axis along Z at y = ADJUSTER_AXIS_HEIGHT (the assembly rotates the
block about Y to align it with the cone axis). Named "adjuster axis" for the
view-independent coaxial mate to the cup-ended screw.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_cone_tip_block.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    PANEL_BLACK,
    SketchDims,
    _early_bound,
    anchor_point_to_origin,
    apply_color,
    apply_material,
    check,
    define_centered_rectangle,
    define_circle,
    dimension_between,
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
    apply_drawing_precision,
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from cone_tip_block_spec import (
    ADJUSTER_BORE_SPEC,
    ADJUSTER_BORE_DIA,
    ADJUSTER_AXIS_HEIGHT,
    BLOCK_HEIGHT,
    BLOCK_X,
    BLOCK_Z,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION,
    FOOT_BORE_DIA,
    FOOT_BORE_SPEC,
    MIN_WEB_MM,
    PINCH_CLEARANCE_DIA,
    PINCH_BORE_SPEC,
    PINCH_BORE_DIA,
    PINCH_CLEARANCE_SPEC,
    PINCH_HEIGHT,
    PINCH_RISE,
    SHAFT_PASSAGE_DIA,
    SLIT_DEPTH,
    SLIT_W,
    SURFACE_FINISHES,
    WORST_SCREW_ENVELOPE_GAP_MM,
    WORST_SLIT_MOUTH_WEB_MM,
    WORST_TOP_LIGAMENT_MM,
)
from _hole_spec import DRILL_POINT_H
from _holes import blind_hole_volume_mm3, wizard_holes
from _part_pmi import author_part_pmi

PART_NAME = "cone-tip-block"
MATERIAL = "Plain Carbon Steel"  # black-finished steel, like the platform it rides

# Geometry envelope comes from cone_tip_block_spec — the drawing's single
# source of the marked dimensions — so a spec correction rebuilds the SLDPRT
# from the same values the print annotates (BLOCK_X/BLOCK_Z/BLOCK_HEIGHT,
# threads, pinch height, slit width).
# --- adjuster + pinch lock (item 5, v4_t00471 / 7:49) ------------------------
# Native 5/16-18 blind tapped adjuster receiver from the north face. Its
# tap-drill diameter is manufacturing geometry, distinct from the purchased
# screw's true major-diameter solid.
SHAFT_PASSAGE_RADIUS = SHAFT_PASSAGE_DIA / 2.0

ADJUSTER_BORE_DEPTH = ADJUSTER_BORE_SPEC.depth_mm
# McMaster 90280A110 is a #4-40 screw. The near jaw receives a normal-fit #4
# clearance hole; the far jaw carries the coaxial #4-40 UNC-2B thread.
PINCH_BORE_Y = PINCH_HEIGHT

# The print-level guards in the spec include every applicable tolerance band.
# These nominal checks catch a model/feature drift before the native build.
if PINCH_BORE_Y - PINCH_BORE_DIA / 2.0 < ADJUSTER_AXIS_HEIGHT + ADJUSTER_BORE_DIA / 2.0:
    raise AssertionError("pinch tap-drill clips the adjuster tap-drill")
if BLOCK_HEIGHT - PINCH_BORE_Y - PINCH_CLEARANCE_DIA / 2.0 < MIN_WEB_MM:
    raise AssertionError("pinch clearance leaves too little nominal top wall")
if round(WORST_SLIT_MOUTH_WEB_MM, 6) < MIN_WEB_MM or WORST_SCREW_ENVELOPE_GAP_MM <= 0.0:
    raise AssertionError("approved pinch-to-adjuster web no longer closes")
if round(WORST_TOP_LIGAMENT_MM, 6) < MIN_WEB_MM:
    raise AssertionError("approved worst-case top ligament no longer closes")
if BLOCK_HEIGHT - SLIT_DEPTH > PINCH_BORE_Y - PINCH_BORE_DIA / 2.0:
    raise AssertionError("top slit does not cross the pinch bore")


def _slit_removed() -> float:
    """Slit volume net of the already-void bores it crosses: the adjuster
    counterbore band, its blind-tap 118-degree DRILL-POINT cone, and the shaft
    clearance passage. The cone and passage are concentric, so each south-side
    slice subtracts their union, never both. This is a clearance passage, not
    the removed fictional journal fit. The drill-point term is load-bearing;
    omitting it caused the first wizard build to miss volume by 4.1 mm^3."""
    r_cb = ADJUSTER_BORE_DIA / 2.0
    y_cb, y_bot = ADJUSTER_AXIS_HEIGHT, BLOCK_HEIGHT - SLIT_DEPTH
    x_half = SLIT_W / 2.0

    def a_void(r: float) -> float:
        """In-slit void area of a concentric circle of radius r at bore height:
        integral over |x| < min(x_half, r) of (circle top - max(slit bottom,
        circle bottom)), Simpson."""
        if r <= 0.0:
            return 0.0
        lim = min(x_half, r)
        h = lim / 200.0
        xs = [-lim + k * h for k in range(401)]

        def f(x: float) -> float:
            s = math.sqrt(max(r * r - x * x, 0.0))
            return max((y_cb + s) - max(y_bot, y_cb - s), 0.0)

        simpson = f(xs[0]) + f(xs[-1]) + 4.0 * sum(f(x) for x in xs[1:-1:2]) \
            + 2.0 * sum(f(x) for x in xs[2:-1:2])
        return simpson * h / 3.0

    point_h = r_cb * DRILL_POINT_H  # 118-degree point height past the shoulder
    v = SLIT_W * BLOCK_Z * SLIT_DEPTH
    v -= a_void(r_cb) * ADJUSTER_BORE_DEPTH  # counterbore band already void
    # Past the shoulder the void is the union of the tapered drill point and
    # the through passage.
    n_z = 400
    dz = (BLOCK_Z - ADJUSTER_BORE_DEPTH) / n_z
    acc = 0.0
    for k in range(n_z + 1):
        z = k * dz  # 0 at the shoulder
        r_cone = r_cb * max(1.0 - z / point_h, 0.0)
        a = a_void(max(r_cone, SHAFT_PASSAGE_RADIUS))
        acc += a * (0.5 if k in (0, n_z) else 1.0)
    v -= acc * dz
    return v

def _as_construction(adapter, entity_id: str) -> None:
    segment = _early_bound(adapter._sketch_entities[entity_id], "ISketchSegment")
    segment.ConstructionGeometry = True
    if not bool(segment.ConstructionGeometry):
        raise RuntimeError(f"{entity_id} did not take the construction flag")


async def _author_reference_dimension(
    adapter,
    *,
    plane: str,
    start: tuple[float, float],
    end: tuple[float, float],
    orientation: str,
    dimension_type: str,
    value_mm: float,
    feature_name: str,
    dimension_name: str,
    drive_expression: str,
) -> None:
    """Author one construction-only, model-owned drawing location."""
    check(
        f"create_sketch {feature_name}",
        await adapter.create_sketch(plane),
    )
    set_sketch_direct_db(adapter, True)
    reference = check(
        f"{feature_name} line",
        await adapter.add_line(*start, *end),
    )
    set_sketch_direct_db(adapter, False)
    _as_construction(adapter, reference)
    check(
        f"{feature_name} {orientation}",
        await adapter.add_sketch_constraint(reference, None, orientation),
    )
    await dimension_between(
        adapter,
        f"{reference}.start",
        f"{reference}.end",
        dimension_type,
        value_mm,
        feature_name,
    )
    await anchor_point_to_origin(
        adapter,
        f"{reference}.start",
        *start,
        feature_name,
    )
    await ensure_fully_defined(adapter, f"{feature_name} sketch")
    check(f"exit_sketch {feature_name}", await adapter.exit_sketch())
    name_last_feature(adapter, feature_name)
    full_name = name_dimensions(
        adapter, feature_name, [dimension_name]
    )[0]
    await drive_dimension(adapter, full_name, drive_expression)
    await force_rebuild(adapter)

async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import CreatePlaneParameters, ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations). The mm suffix is load-bearing -- this
    # is an INCH document and the equation manager reads BARE numbers in
    # document units (an unsuffixed 14 = 14 in).
    await set_global(adapter, "BlockX", f"{BLOCK_X}mm")
    await set_global(adapter, "BlockZ", f"{BLOCK_Z}mm")
    await set_global(adapter, "BlockHeight", f"{BLOCK_HEIGHT}mm")
    await set_global(adapter, "AdjusterAxisHeight", f"{ADJUSTER_AXIS_HEIGHT}mm")
    await set_global(adapter, "ShaftPassageDia", f"{SHAFT_PASSAGE_DIA}mm")
    # (The old AdjusterBoreDia/PinchBoreDia knobs are gone: both are now native
    # Hole Wizard TAPPED features whose diameters come from the ANSI-inch tap
    # tables, not driven dims.)
    await set_global(adapter, "SlitW", f"{SLIT_W}mm")
    await set_global(adapter, "SlitDepth", f"{SLIT_DEPTH}mm")
    await set_global(adapter, "PinchRise", f"{PINCH_RISE}mm")
    await set_global(adapter, "PassageCenter", '"BlockX" / 2')
    await set_global(adapter, "PinchDepthCenter", '"BlockZ" / 2')
    await set_global(adapter, "FootTapX", '"BlockX" / 2')
    await set_global(adapter, "FootTapZ", '"BlockZ" / 2')
    await set_global(
        adapter, "PinchBoreY", '"AdjusterAxisHeight" + "PinchRise"'
    )

    drive_jobs: list[tuple[str, str]] = []

    # Origin-centred rectangular footprint on the Top plane.
    block = SketchDims()
    check("create_sketch block", await adapter.create_sketch("Top"))
    await define_centered_rectangle(
        adapter, BLOCK_X / 2.0, BLOCK_Z / 2.0, "block", dims=block,
        name_width="Width", drive_width='"BlockX"',
        name_depth="Depth", drive_depth='"BlockZ"',
    )
    await ensure_fully_defined(adapter, "block sketch")
    check("exit_sketch block", await adapter.exit_sketch())
    name_last_feature(adapter, "BlockProfile")
    drive_jobs += block.apply(adapter, "BlockProfile")
    check(
        "extrude block",
        await adapter.create_extrusion(ExtrusionParameters(depth=BLOCK_HEIGHT)),
    )
    name_last_feature(adapter, "Block")
    # Name the extrude DEPTH so the block height is a markable drawing dimension.
    block_depth_dim = name_dimensions(adapter, "Block", ["BlockHt"])
    drive_jobs += [(block_depth_dim[0], '"BlockHeight"')]
    v_block = BLOCK_X * BLOCK_Z * BLOCK_HEIGHT
    volume = await volume_check(adapter, "block", v_block, 0.005 * v_block)

    # Non-bearing shaft-tip passage, coaxial with the adjuster. The external
    # brass bushing supports the Ø0.794 tip; this opening only admits the tip
    # to the exact 94025A150 conical cup apex. It is cut first so the later
    # blind-tap volume subtracts only material not already removed here.
    passage = SketchDims()
    check("create_sketch shaft passage", await adapter.create_sketch("Front"))
    await define_circle(
        adapter,
        0.0,
        ADJUSTER_AXIS_HEIGHT,
        SHAFT_PASSAGE_RADIUS,
        "shaft passage",
        dims=passage,
        names=("PassageX", "PassageZ", "PassageDiaDim"),
        drives=(None, '"AdjusterAxisHeight"', '"ShaftPassageDia"'),
    )
    await ensure_fully_defined(adapter, "shaft-passage sketch")
    check("exit_sketch shaft passage", await adapter.exit_sketch())
    name_last_feature(adapter, "PassageProfile")
    drive_jobs += passage.apply(adapter, "PassageProfile")
    check(
        "cut shaft passage",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=BLOCK_Z + 4.0, both_directions=True)
        ),
    )
    name_last_feature(adapter, "ShaftPassage")
    v_passage = math.pi * SHAFT_PASSAGE_RADIUS**2 * BLOCK_Z
    volume = await volume_check(
        adapter, "shaft clearance passage", volume - v_passage, 0.02 * v_passage
    )

    # Adjuster interface (v4_t00471 / 7:49): ONE native Hole Wizard blind
    # 5/16-18 TAPPED hole from the NORTH face (z = +BLOCK_Z/2), concentric with
    # the cone shaft, ADJUSTER_BORE_DEPTH deep -- the partially hollow slotted
    # adjuster screw threads in here and the shaft tip rests in its (own) cup
    # (axial end-play takeup). Drilled while the body is still simple (block +
    # cup-ended screw supports the shaft tip. Removed volume is the blind
    # tap-drill cylinder plus its standard drill point.
    adjuster_cut = wizard_holes(
        adapter, ADJUSTER_BORE_SPEC,
        [[0.0, ADJUSTER_AXIS_HEIGHT, BLOCK_Z / 2.0]],
        (0.0, 0.0, 1.0),
        f"adjuster tapped hole ({ADJUSTER_BORE_SPEC.size} blind)",
        name="AdjusterBore",
        placement_dims=[((None, None), ("CbZ", '"AdjusterAxisHeight"'))],
    )
    drive_jobs += adjuster_cut.placement_drive_jobs
    point_h = (ADJUSTER_BORE_DIA / 2.0) * DRILL_POINT_H
    radius_ratio = SHAFT_PASSAGE_RADIUS / (ADJUSTER_BORE_DIA / 2.0)
    passage_point_overlap = math.pi * (
        SHAFT_PASSAGE_RADIUS**2 * point_h * (1.0 - radius_ratio)
        + point_h * SHAFT_PASSAGE_RADIUS**3 / (3.0 * (ADJUSTER_BORE_DIA / 2.0))
    )
    passage_overlap = (
        math.pi * SHAFT_PASSAGE_RADIUS**2 * ADJUSTER_BORE_DEPTH
        + passage_point_overlap
    )
    v_cb = (
        blind_hole_volume_mm3(ADJUSTER_BORE_DIA, ADJUSTER_BORE_DEPTH)
        - passage_overlap
    )
    volume = await volume_check(adapter, "adjuster bore", volume - v_cb, 0.03 * v_cb)

    # Top slit + perpendicular pinch screw: the 1.2-wide slit runs below the
    # cross-bore so the exact McMaster 90280A110 #4-40 screw can squeeze the
    # two jaws around the adjuster thread.
    check("create_plane BlockTop", await adapter.create_plane(
        CreatePlaneParameters(mode="offset", base_plane="Top Plane",
                              offset=BLOCK_HEIGHT)))
    name_last_feature(adapter, "BlockTop")
    slit = SketchDims()
    check("create_sketch slit", await adapter.create_sketch("BlockTop"))
    await define_centered_rectangle(
        adapter, SLIT_W / 2.0, BLOCK_Z / 2.0 + 1.0, "slit", dims=slit,
        name_width="SlitW", drive_width='"SlitW"',
        name_depth="SlitSpan", drive_depth=None,
    )
    await ensure_fully_defined(adapter, "slit sketch")
    check("exit_sketch slit", await adapter.exit_sketch())
    name_last_feature(adapter, "SlitProfile")
    drive_jobs += slit.apply(adapter, "SlitProfile")
    check("cut slit", await adapter.create_cut_extrude(
        ExtrusionParameters(depth=SLIT_DEPTH)))  # default cut dir = down into the block
    name_last_feature(adapter, "TopSlit")
    slit_depth_dim = name_dimensions(adapter, "TopSlit", ["SlitDepth"])[0]
    drive_jobs.append((slit_depth_dim, '"SlitDepth"'))
    volume = await volume_check(
        adapter, "top slit", volume - _slit_removed(), 0.02 * _slit_removed()
    )

    # Pinch screw cross-bore: native #4-40 tap through both jaws, followed by a
    # normal-fit #4 clearance through the +X near jaw only. The screw slips
    # through the head-side jaw and pulls against threads in the far jaw.
    # Both features run along local X at (y = PINCH_BORE_Y, z = 0) from the +X
    # block face. The slit splits the cylinder into two solid halves, so the
    # through cut removes tap-drill area over (BLOCK_X - SLIT_W) of material.
    pinch_cut = wizard_holes(
        adapter, PINCH_BORE_SPEC,
        [[BLOCK_X / 2.0, PINCH_BORE_Y, 0.0]],
        (1.0, 0.0, 0.0),
        f"pinch tapped hole ({PINCH_BORE_SPEC.size})",
        name="PinchBore",
        placement_dims=[((None, None), ("PinchZ", '"PinchBoreY"'))],
    )
    drive_jobs += pinch_cut.placement_drive_jobs
    v_pinch = math.pi * (PINCH_BORE_DIA / 2.0) ** 2 * (BLOCK_X - SLIT_W)
    volume = await volume_check(adapter, "pinch bore", volume - v_pinch, 0.05 * v_pinch)

    pinch_clearance = wizard_holes(
        adapter, PINCH_CLEARANCE_SPEC,
        [[BLOCK_X / 2.0, PINCH_BORE_Y, 0.0]],
        (1.0, 0.0, 0.0),
        f"pinch near-jaw clearance ({PINCH_CLEARANCE_SPEC.size} normal)",
        name="PinchClearance",
        expect_dia_mm=PINCH_CLEARANCE_DIA,
        placement_dims=[((None, None), ("PinchZ", '"PinchBoreY"'))],
    )
    drive_jobs += pinch_clearance.placement_drive_jobs
    near_jaw = (BLOCK_X - SLIT_W) / 2.0
    v_clearance = math.pi * (
        (PINCH_CLEARANCE_DIA / 2.0) ** 2 - (PINCH_BORE_DIA / 2.0) ** 2
    ) * near_jaw
    volume = await volume_check(
        adapter, "pinch clearance", volume - v_clearance, 0.08 * v_clearance
    )

    # U30 hold-down: one native #6-32 blind tap up into the foot centre. The
    # #6-32 socket head cap screw comes up through the platform's counterbored
    # lateral slot; the slot and the shim pack under the foot absorb the
    # block's fit-up alignment, so the tap needs no location tighter than the
    # footprint it is centred in.
    wizard_holes(
        adapter, FOOT_BORE_SPEC,
        [[0.0, 0.0, 0.0]],
        (0.0, -1.0, 0.0),
        f"foot hold-down tapped hole ({FOOT_BORE_SPEC.size} blind)",
        name="FootBore",
    )
    v_foot = blind_hole_volume_mm3(FOOT_BORE_DIA, FOOT_BORE_SPEC.depth_mm)
    volume = await volume_check(adapter, "foot tap", volume - v_foot, 0.03 * v_foot)

    # Named bore axis for the view-independent coaxial mate: the shaft tip
    # positions this block (coaxial + axial distance), no face picks.
    await name_bore_axis(
        adapter, "Top Plane", ADJUSTER_AXIS_HEIGHT, "Right Plane", 0.0,
        "adjuster axis", drive_a='"AdjusterAxisHeight"', drive_jobs=drive_jobs,
    )
    # Second named axis (Axis2): the pinch-screw cross-bore, along local X at
    # the slit -- the assembly locates the pinch screw on it.
    await name_bore_axis(
        adapter, "Top Plane", PINCH_BORE_Y, "Front Plane", 0.0, "pinch axis",
        drive_a='"PinchBoreY"', drive_jobs=drive_jobs,
    )

    # Apply the deferred drive equations after the model + reference axes exist,
    # then re-check: every equation evaluates to the value just built, so geometry
    # must not move.
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(adapter, "driven block (equations neutral)", volume, 0.01 * v_cb)

    # Model-owned functional interfaces: construction-only dimensions carry
    # every centre location that a machinist must set from a finished face.
    await _author_reference_dimension(
        adapter,
        plane="Front",
        start=(BLOCK_X / 2.0, ADJUSTER_AXIS_HEIGHT),
        end=(0.0, ADJUSTER_AXIS_HEIGHT),
        orientation="horizontal",
        dimension_type="horizontal_distance",
        value_mm=BLOCK_X / 2.0,
        feature_name="PassageCenterReference",
        dimension_name="PassageCenter",
        drive_expression='"PassageCenter"',
    )
    await _author_reference_dimension(
        adapter,
        plane="Right",
        start=(-BLOCK_Z / 2.0, PINCH_BORE_Y),
        end=(0.0, PINCH_BORE_Y),
        orientation="horizontal",
        dimension_type="horizontal_distance",
        value_mm=BLOCK_Z / 2.0,
        feature_name="PinchDepthReference",
        dimension_name="PinchDepthCenter",
        drive_expression='"PinchDepthCenter"',
    )
    await _author_reference_dimension(
        adapter,
        plane="Right",
        start=(0.0, ADJUSTER_AXIS_HEIGHT),
        end=(0.0, PINCH_BORE_Y),
        orientation="vertical",
        dimension_type="vertical_distance",
        value_mm=PINCH_RISE,
        feature_name="PinchRiseReference",
        dimension_name="PinchRise",
        drive_expression='"PinchRise"',
    )
    # The foot tap sits at the foot centre (it is placed at the origin); these
    # two construction-only dimensions locate it from the -X and -Z faces.
    await _author_reference_dimension(
        adapter,
        plane="Top",
        start=(-BLOCK_X / 2.0, 0.0),
        end=(0.0, 0.0),
        orientation="horizontal",
        dimension_type="horizontal_distance",
        value_mm=BLOCK_X / 2.0,
        feature_name="FootTapXReference",
        dimension_name="FootTapX",
        drive_expression='"FootTapX"',
    )
    await _author_reference_dimension(
        adapter,
        plane="Top",
        start=(0.0, -BLOCK_Z / 2.0),
        end=(0.0, 0.0),
        orientation="vertical",
        dimension_type="vertical_distance",
        value_mm=BLOCK_Z / 2.0,
        feature_name="FootTapZReference",
        dimension_name="FootTapZ",
        drive_expression='"FootTapZ"',
    )
    # Model-owned places are applied only after the reference sketches exist.
    apply_drawing_precision(adapter, DRAWING_PRECISION)

    await apply_material(adapter, MATERIAL)
    await apply_color(adapter, PANEL_BLACK)
    await report_mass_properties(adapter)
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    author_part_pmi(adapter, surface_finishes=SURFACE_FINISHES)
    apply_drawing_properties(adapter, PART_NAME)
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
