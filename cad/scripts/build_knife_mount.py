r"""Reproduction script: knife bearing support (book ch. 18, pp. 42-43).

The hardened-steel bearing block that suspends the summing lever's knife edge from the
top-frame casting's integral crossbar (hung by a 1/2-13 knife-hanger stud
threaded into the block top). The lever rocks as a FIRST-CLASS LEVER on the **top vertex line
of its hexagonal pivot trunnions** (build_summing_lever ``_hex_collar``); each
trunnion overhangs the lever body into one of these supports.

DESIGN (user direction, 2026-06-17, refs: ch30-p003, bore.png, ch18 p.43 photo):
a **circular bore around the hex trunnion**, so that *only the top knife edge
of the trunnion* contacts the bore -- the upper inner wall of the bore meets
the hex's top vertex line while every other facet clears. This is the true
knife-edge suspension: line contact at the ridge, free to rock, replacing the
M6.4 "diamond knife-bar in the lever tube bore" (which clashed with the lever's
solid pivot cylinder once the bore was removed). 2026-09-02 user re-read of
ch18 p.42: the block is an UNPAINTED HEAT-TREATED STEEL block (not brass) with
a CLOSE bore around the trunnion -- Ø12 over the 8.653 x 10.268 hex.  At
finished-size limits it clears the observed ±1.6-degree rocking sweep.

There are TWO supports, one per trunnion (placed front/back in the assembly at
|z| ~ 87). This single part is built once and placed twice.

Layout (part-local): origin = the **knife-edge contact line** = the hex top
vertex ridge (placed at machine (15, 984.83, +-87)); local Z = the bore/trunnion
axis, +Y up, +X across. The bore centre sits ``R_BORE`` below the origin so the
bore's upper inner wall lands on the ridge. The block rises from below the bore
up to just under the top-frame casting underside (999.7); the shortened hanger
stud engages 5.8735 mm of the block-top tap. A conventional 118-degree tap drill
retains at least 0.50 mm of uninterrupted material above the bore at limits.

The named "knife axis" is the contact ridge line itself (part origin); the
assembly mates the lever's knife ridge (``Axis3@summing-lever``) coincident to
it, so the lever rocks about the true knife edge (not the cylinder centre).

Dimensions: cad/DIMENSIONS.md ch. 18. Bore size remains low-confidence
photo-derived geometry; its hard constraints are ridge contact and the observed
rocking sweep at finished-size limits.

Run (SolidWorks already open)::

    uv run python cad\scripts\build_knife_mount.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    SketchDims,
    _early_bound,
    add_line_chain,
    anchor_point_to_origin,
    apply_color,
    apply_material,
    check,
    define_circle,
    define_rectilinear_chain,
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
from summing_lever_spec import HEX_H, HEX_W
from _holes import blind_hole_volume_mm3, wizard_holes
from _drawing_marks import (
    apply_drawing_precision,
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
    set_dimension_symmetric_tolerance,
)
from _part_pmi import author_part_pmi
from knife_mount_spec import (
    BORE_DIAMETER_TOLERANCE_MM,
    BORE_FROM_TOP,
    DRAWING_DIMENSIONS,
    DRAWING_NOTES,
    DRAWING_PRECISION,
    ISOMETRIC_VIEW_NOTE,
    MATING_HEX_SIZE_PLUS_MM,
    REQUIRED_ROCK_SWEEP_DEG,
    STUD_TAP_CROWN_WEB_MM,
    STUD_TAP_DIA,
    STUD_TAP_DRILL_DEPTH_DEVIATIONS_MM,
    STUD_TAP_DRILL_DEPTH_MM,
    STUD_TAP_POINT_HEIGHT_MM,
    STUD_TAP_SPEC,
    STUD_TAP_THREAD_DEPTH_DEVIATIONS_MM,
    STUD_TAP_THREAD_DEPTH_MM,
    STUD_TAP_WORST_CASE_CROWN_WEB_MM,
    STUD_TAP_WORST_CASE_RUNOUT_MM,
    SURFACE_FINISHES,
)

import _telemetry

PART_NAME = "knife-mount"
# ch18 p.42 (2026-09-02 user re-read): an unpainted HEAT-TREATED steel block,
# not the brass of the earlier registry/DFM pass.
MATERIAL = "Plain Carbon Steel"
HARDENED_STEEL = (0.30, 0.30, 0.31)  # dark heat-treated grey, left unpainted

# --- knife-edge geometry (kept in sync with the lever's hex trunnion) -------
RIDGE_Y = HEX_H / 2.0  # hex top vertex above the pivot/cylinder centreline (5.134)

# --- bore: close around the hex trunnion, actual top-ridge line contact -----
R_BORE = 6.0  # Ø12 bore around the 8.653 x 10.268 hex trunnion
TOP_CLEAR = 0.0  # bore crown is tangent to the lever's top-vertex knife ridge
BORE_CY = TOP_CLEAR - R_BORE  # -6.0; upper inner wall lies on the knife axis

# --- block (bearing body, held to the crossbar) ----------------------------
SUPPORT_Z_THICK = 14.0  # axial length straddling the trunnion mid (low)
BLK_HALF_X = 12.0  # bore wall + flank (24 across, photo-scaled)
WALL = 3.0  # material below the bore
BLK_BOT = BORE_CY - R_BORE - WALL  # -15.0

# Mount: the block top seat hangs MOUNT_GAP below the top-frame casting
# underside (the integral crossbar's flush lower face); the knife-hanger stud
# threaded into the block top carries the hang (build_summing_assembly).
KNIFE_Y = 979.7  # machine y of the pivot centreline (build_summing_assembly KNIFE)
CASTING_UNDERSIDE_Y = 999.7  # top-frame casting underside (integral crossbar)
MOUNT_GAP = 0.25  # design clearance to the casting (sliver-flag margin)
CONTACT_Y = KNIFE_Y + RIDGE_Y  # machine y of the knife-edge contact line (984.834)
BLK_TOP = CASTING_UNDERSIDE_Y - CONTACT_Y - MOUNT_GAP  # local top (14.62)

THROUGH_CUT_DEPTH = SUPPORT_Z_THICK + 4.0  # > the block thickness, both directions

# --- hanger-stud tap: 1/2-13 UNC-2B blind in the block top ------------------
# A conventional 118-degree drill and bottoming tap accept the 5.5-mm-shortened
# hanger stud while their native depth bands preserve an uninterrupted crown.


def _as_construction(adapter, entity_id: str) -> None:
    """Make a reference-sketch line construction geometry and verify it."""
    segment = _early_bound(adapter._sketch_entities[entity_id], "ISketchSegment")
    segment.ConstructionGeometry = True
    if not bool(segment.ConstructionGeometry):
        raise RuntimeError(f"{entity_id} did not take the construction flag")


def _verify_named_dimension(adapter, full_name: str, expected_mm: float) -> None:
    """Prove a creation-order rename landed on the intended reference value."""
    dimension = adapter.currentModel.Parameter(full_name)
    if dimension is None:
        raise RuntimeError(f"missing model dimension {full_name!r}")
    actual_mm = abs(float(_early_bound(dimension, "IDimension").SystemValue)) * 1000.0
    if abs(actual_mm - expected_mm) > 1e-6:
        raise RuntimeError(
            f"{full_name} measured {actual_mm:g}, expected {expected_mm:g} mm"
        )



def _minimum_hex_rock_clearance_mm() -> float:
    """Return the worst noncontact-vertex clearance over the required sweep."""
    bore_radius = R_BORE - BORE_DIAMETER_TOLERANCE_MM / 2.0
    width = HEX_W + MATING_HEX_SIZE_PLUS_MM
    height = HEX_H + MATING_HEX_SIZE_PLUS_MM
    vertices = (
        (-width / 2.0, -height / 4.0),
        (-width / 2.0, -3.0 * height / 4.0),
        (0.0, -height),
        (width / 2.0, -3.0 * height / 4.0),
        (width / 2.0, -height / 4.0),
    )
    sweep = math.radians(REQUIRED_ROCK_SWEEP_DEG)
    clearance = math.inf
    for x, y in vertices:
        candidates = [-sweep, sweep]
        stationary = math.atan2(x, y)
        for half_turn in range(-2, 3):
            angle = stationary + half_turn * math.pi
            if -sweep <= angle <= sweep:
                candidates.append(angle)
        maximum_radius = max(
            math.sqrt(
                x * x
                + y * y
                + bore_radius * bore_radius
                + 2.0
                * bore_radius
                * (x * math.sin(angle) + y * math.cos(angle))
            )
            for angle in candidates
        )
        clearance = min(clearance, bore_radius - maximum_radius)
    return clearance


def _tolerance_hole_depth(
    adapter,
    feature_name: str,
    dimension_token: str,
    deviations_mm: tuple[float, float],
) -> None:
    """Apply and read back one native Hole Wizard depth tolerance in the part."""
    feature = adapter._model.FeatureByName(feature_name)
    if feature is None:
        raise RuntimeError(f"missing Hole Wizard feature {feature_name!r}")
    feature = _early_bound(feature, "IFeature")
    matches = []
    display = feature.GetFirstDisplayDimension()
    while display is not None:
        display = _early_bound(display, "IDisplayDimension")
        dimension = display.GetDimension()
        if dimension is not None:
            dimension = _early_bound(dimension, "IDimension")
            normalized = "".join(
                character
                for character in str(dimension.FullName).lower()
                if character.isalnum()
            )
            if dimension_token in normalized:
                matches.append((display, dimension))
        display = feature.GetNextDisplayDimension(display)
    if len(matches) != 1:
        raise RuntimeError(
            f"{feature_name}: expected one {dimension_token} display dimension, "
            f"found {len(matches)}"
        )
    display, dimension = matches[0]
    lower_mm, upper_mm = deviations_mm
    tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
    tolerance.Type = 2  # swTolBILAT
    if not tolerance.SetValues(lower_mm / 1000.0, upper_mm / 1000.0):
        raise RuntimeError(
            f"{feature_name} {dimension_token}: rejected native depth tolerance"
        )
    lower = float(tolerance.GetMinValue()) * 1000.0
    upper = float(tolerance.GetMaxValue()) * 1000.0
    if abs(lower - lower_mm) > 1e-9 or abs(upper - upper_mm) > 1e-9:
        raise RuntimeError(
            f"{feature_name} {dimension_token}: tolerance readback "
            f"{lower:+.3f}/{upper:+.3f} mm"
        )
    display.SetPrecision3(2, -1, 2, -1)
    if (
        int(display.GetPrimaryPrecision2()) != 2
        or int(display.GetPrimaryTolPrecision2()) != 2
    ):
        raise RuntimeError(
            f"{feature_name} {dimension_token}: depth precision did not persist"
        )


async def _volume(adapter) -> float:
    res = await adapter.get_mass_properties()
    return res.data.volume if res.is_success else float("nan")


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations): the bore radius + its top clearance,
    # the block half-width / wall / axial thickness, and the local block top. The
    # derived globals (BoreCy / BlkBot) are equations of the primitives so the
    # bore centre and block bottom track when a primitive changes. The mm suffix
    # is load-bearing -- this is an INCH document and the equation manager reads
    # BARE numbers in document units (an unsuffixed 12.7 = 12.7 in, 25.4x too big).
    await set_global(adapter, "RBore", f"{R_BORE}mm")
    await set_global(adapter, "TopClear", f"{TOP_CLEAR}mm")
    await set_global(adapter, "SupportZThick", f"{SUPPORT_Z_THICK}mm")
    await set_global(adapter, "BlkHalfX", f"{BLK_HALF_X}mm")
    await set_global(adapter, "Wall", f"{WALL}mm")
    await set_global(adapter, "BlkTop", f"{BLK_TOP}mm")
    await set_global(adapter, "BoreCy", '"TopClear" - "RBore"')
    await set_global(adapter, "BlkBot", '"BoreCy" - "RBore" - "Wall"')

    # Each sketch records its dim names + drive equations as the define_* helper
    # emits them; the equations are collected here and applied in one deferred
    # batch at the end (every target must resolve against the finished model).
    drive_jobs: list[tuple[str, str]] = []

    # 1. Bearing block: Front-plane rectangle, mid-plane extrude along Z (the
    #    bore/trunnion axis), straddling the trunnion mid. Asymmetric in Y (not
    #    origin-centred), so a generic rectilinear chain, not define_centered_*.
    #    Emission order (anchor vertex 0 at (-BlkHalfX, BlkBot)): the width dim
    #    (seg 0), the height dim (seg 1), then the anchor dims (x, then z).
    block_dims = SketchDims()
    check("create_sketch block", await adapter.create_sketch("Front"))
    block_rect = [
        (-BLK_HALF_X, BLK_BOT),
        (BLK_HALF_X, BLK_BOT),
        (BLK_HALF_X, BLK_TOP),
        (-BLK_HALF_X, BLK_TOP),
    ]
    block = await add_line_chain(adapter, block_rect)
    await define_rectilinear_chain(
        adapter,
        block,
        block_rect,
        label="block",
        dims=block_dims,
        names=["BlockWidth", "BlockHeight", "BlockAnchorX", "BlockAnchorZ"],
        drives=[
            '2 * "BlkHalfX"',
            '"BlkTop" - "BlkBot"',
            '"BlkHalfX"',
            '-"BlkBot"',
        ],
    )
    await ensure_fully_defined(adapter, "block sketch")
    check("exit_sketch block", await adapter.exit_sketch())
    name_last_feature(adapter, "BlockProfile")
    drive_jobs += block_dims.apply(adapter, "BlockProfile")
    check(
        "extrude block",
        await adapter.create_extrusion(
            ExtrusionParameters(depth=SUPPORT_Z_THICK, both_directions=True)
        ),
    )
    name_last_feature(adapter, "Block")
    depth_dim = name_dimensions(adapter, "Block", ["Depth"])
    drive_jobs += [(depth_dim[0], '"SupportZThick"')]
    expected = 2.0 * BLK_HALF_X * (BLK_TOP - BLK_BOT) * SUPPORT_Z_THICK
    vol = await _volume(adapter)
    _telemetry.info(f"volume after block: {vol:.1f} mm^3 (analytic {expected:.1f})")
    if abs(vol - expected) > 0.005 * expected:
        raise RuntimeError(f"block volume {vol:.1f} != {expected:.1f}")

    # 2. Circular bore through the block (the trunnion rides inside; only the
    #    hex top vertex nears the upper inner wall). Centred TOP_CLEAR below the
    #    ridge so the rest of the hex clears. On the Y-axis (x 0): only the
    #    centre-Z + diameter are dims (the X is a relation).
    bore_dims = SketchDims()
    check("create_sketch bore", await adapter.create_sketch("Front"))
    await define_circle(
        adapter,
        0.0,
        BORE_CY,
        R_BORE,
        "knife bore",
        dims=bore_dims,
        names=("BoreCx", "BoreCz", "BoreDia"),
        drives=(None, '-"BoreCy"', '2 * "RBore"'),
    )
    await ensure_fully_defined(adapter, "bore sketch")
    check("exit_sketch bore", await adapter.exit_sketch())
    name_last_feature(adapter, "BoreProfile")
    drive_jobs += bore_dims.apply(adapter, "BoreProfile")
    check(
        "cut knife bore",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=THROUGH_CUT_DEPTH, both_directions=True)
        ),
    )
    name_last_feature(adapter, "KnifeBore")
    expected -= math.pi * R_BORE**2 * SUPPORT_Z_THICK
    vol = await _volume(adapter)
    _telemetry.info(f"volume after bore: {vol:.1f} mm^3 (analytic {expected:.1f})")
    if abs(vol - expected) > 0.01 * expected:
        raise RuntimeError(f"bore volume {vol:.1f} != {expected:.1f}")

    # The bore crown and lever ridge share the named knife axis: actual contact,
    # not the former 0.25-mm modeled gap.
    hex_top = 0.0
    contact_error = (BORE_CY + R_BORE) - hex_top
    if abs(contact_error) > 1e-9:
        raise RuntimeError(f"knife contact error is {contact_error:.6f} mm")
    # Every noncontact vertex must remain inside the minimum finished bore for
    # the complete observed rock range, with both trunnion sizes at maximum
    # material.  The former static 0.5-mm shoulder threshold had no mechanical
    # basis and rejected the valid nominal contact geometry.
    rock_clearance = _minimum_hex_rock_clearance_mm()
    if rock_clearance <= 0.0:
        raise RuntimeError(
            "hex trunnion interferes with the knife bore over "
            f"+/-{REQUIRED_ROCK_SWEEP_DEG:g} degrees: "
            f"{rock_clearance:.6f} mm clearance at limits"
        )
    _telemetry.info(
        "knife trunnion clearance at size and motion limits: "
        f"{rock_clearance:.6f} mm"
    )

    # Hanger-stud tap: native 1/2-13 blind bottoming tap on the trunnion-axis
    # centreline.  HoleWizard5 reads depth as the cylindrical drill shoulder;
    # its ordinary 118-degree point ends above the functional bore crown.
    tap_runout = STUD_TAP_DRILL_DEPTH_MM - STUD_TAP_THREAD_DEPTH_MM
    two_pitches = 2.0 * 25.4 / 13.0
    if tap_runout < two_pitches or STUD_TAP_WORST_CASE_RUNOUT_MM < two_pitches:
        raise RuntimeError(
            "stud tap has insufficient bottoming-tap lead: "
            f"{tap_runout:.4f} mm nominal, "
            f"{STUD_TAP_WORST_CASE_RUNOUT_MM:.4f} mm at limits"
        )
    tap_crown_web = (
        BLK_TOP
        - (BORE_CY + R_BORE)
        - STUD_TAP_DRILL_DEPTH_MM
        - STUD_TAP_POINT_HEIGHT_MM
    )
    if abs(tap_crown_web - STUD_TAP_CROWN_WEB_MM) > 1e-9:
        raise RuntimeError(
            "stud tap crown-web contract drifted: "
            f"model {tap_crown_web:.4f} mm, spec {STUD_TAP_CROWN_WEB_MM:.4f} mm"
        )
    if (
        tap_crown_web < 0.5
        or STUD_TAP_WORST_CASE_CROWN_WEB_MM < 0.5
    ):
        raise RuntimeError(
            "stud tap crown web is insufficient: "
            f"{tap_crown_web:.4f} mm nominal, "
            f"{STUD_TAP_WORST_CASE_CROWN_WEB_MM:.4f} mm at limits"
        )
    wizard_holes(
        adapter,
        STUD_TAP_SPEC,
        [[0.0, BLK_TOP, 0.0]],
        (0.0, 1.0, 0.0),
        "hanger-stud tapped hole (1/2-13)",
        name="StudTap",
        # no expect_dia_mm: a BLIND hole's definition reads 0.0 for both
        # diameter knobs on this seat (the tripwire is through-hole only);
        # the pinned dia is what HoleWizard5 was handed, and the volume
        # gate below proves the cut.
    )
    _tolerance_hole_depth(
        adapter,
        "StudTap",
        "tapdrilldepth",
        STUD_TAP_DRILL_DEPTH_DEVIATIONS_MM,
    )
    _tolerance_hole_depth(
        adapter,
        "StudTap",
        "threaddepth",
        STUD_TAP_THREAD_DEPTH_DEVIATIONS_MM,
    )
    expected -= blind_hole_volume_mm3(STUD_TAP_DIA, STUD_TAP_DRILL_DEPTH_MM)
    vol = await _volume(adapter)
    _telemetry.info(f"volume after stud tap: {vol:.1f} mm^3 (analytic {expected:.1f})")
    if abs(vol - expected) > 0.01 * expected:
        raise RuntimeError(f"stud tap volume {vol:.1f} != {expected:.1f}")

    # Named axis = the knife-edge contact ridge line (part origin, along Z). The
    # assembly mates Axis3@summing-lever (the hex ridge) coincident to it.
    await name_bore_axis(adapter, "Top Plane", 0.0, "Right Plane", 0.0, "knife axis")

    # Apply the deferred drive equations after the whole model + a rebuild
    # exists, then re-check: each equation evaluates to the value just built, so
    # the geometry must not move -- the re-check below is the proof.
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(
        adapter, "driven knife mount (equations neutral)", expected, 0.01 * expected
    )

    # Model-owned BASIC height for the knife-bore position control.  This
    # construction sketch adds no material and imports normally into the front
    # drawing view; unlike a drawing-native dimension, its nominal and decimal
    # places persist in the SLDPRT.
    check("create bore-height reference", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    bore_height_ref = check(
        "bore-height reference line",
        await adapter.add_line(0.0, BLK_TOP, 0.0, BORE_CY),
    )
    set_sketch_direct_db(adapter, False)
    _as_construction(adapter, bore_height_ref)
    check(
        "bore-height reference vertical",
        await adapter.add_sketch_constraint(bore_height_ref, None, "vertical"),
    )
    await dimension_between(
        adapter,
        f"{bore_height_ref}.start",
        f"{bore_height_ref}.end",
        "vertical_distance",
        BORE_FROM_TOP,
        "bore height from top seat",
    )
    await anchor_point_to_origin(
        adapter,
        f"{bore_height_ref}.start",
        0.0,
        BLK_TOP,
        "bore height reference",
    )
    await ensure_fully_defined(adapter, "bore-height reference sketch")
    check("exit bore-height reference", await adapter.exit_sketch())
    name_last_feature(adapter, "BoreHeightReference")
    name_dimensions(adapter, "BoreHeightReference", ["BoreFromTop"])
    _verify_named_dimension(
        adapter, "BoreFromTop@BoreHeightReference", BORE_FROM_TOP
    )

    await force_rebuild(adapter)
    await volume_check(
        adapter, "knife mount after reference sketches", expected, 0.01 * expected
    )

    await apply_material(adapter, MATERIAL)
    # ch18 p.42: heat-treated and left unpainted -- a dark grey, not the
    # database steel's bright render nor the frame's green.
    await apply_color(adapter, HARDENED_STEEL)
    await report_mass_properties(adapter)

    # Manufacturing drawing support: mark exactly the print's dimensions and
    # stamp the make-critical title-block properties.
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    set_dimension_symmetric_tolerance(
        adapter,
        "BoreProfile",
        "BoreDia",
        BORE_DIAMETER_TOLERANCE_MM,
    )
    author_part_pmi(adapter, surface_finishes=SURFACE_FINISHES)
    apply_drawing_properties(
        adapter,
        PART_NAME,
        {
            "Manufacturing Notes": DRAWING_NOTES,
            "Isometric View Note": ISOMETRIC_VIEW_NOTE,
        },
    )
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
