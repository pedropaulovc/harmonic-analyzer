r"""Reproduction script: knife bearing support (book ch. 18, pp. 42-43).

The hardened-steel bearing block that suspends the summing lever's knife edge from the
top-frame casting's integral crossbar (clamped to its underside by the MHA-VN-024
#6-32 socket head cap screw threaded into a bottoming tap in the block top, and
keyed against turning by the MHA-VN-051 dowel pressed into the top seat).
The lever rocks as a FIRST-CLASS LEVER on the **top vertex line
of its hexagonal pivot trunnions** (build_sm_summing_lever ``_hex_collar``); each
trunnion overhangs the lever body into one of these supports.

DESIGN (user direction, 2026-06-17, refs: ch30-p003, bore.png, ch18 p.43 photo):
a **circular bore around the hex trunnion**, so that *only the top knife edge
of the trunnion* nears the bore -- the upper inner wall of the bore comes down
to the hex's top vertex line while every other facet clears. This is the true
knife-edge suspension: line contact at the ridge, free to rock, replacing the
M6.4 "diamond knife-bar in the lever tube bore" (which clashed with the lever's
solid pivot cylinder once the bore was removed). 2026-09-02 user re-read of
ch18 p.42: the block is an UNPAINTED HEAT-TREATED STEEL block (not brass) with
a CLOSE bore around the trunnion -- Ø12 over the 8.653 x 10.268 hex, so the
across-corners diagonal clears by ~0.87 and the shoulders by ~0.6.

There are TWO supports, one per trunnion (placed front/back in the assembly at
|z| ~ 87). This single part is built once and placed twice.

Layout (part-local): origin = the **knife-edge contact line** = the hex top
vertex ridge (placed at machine (15, 984.83, +-87)); local Z = the bore/trunnion
axis, +Y up, +X across. The bore centre sits ``R_BORE`` below the origin so the
bore's upper inner wall lands on the ridge (with a TOP_CLEAR sliver margin). The
block rises from below the bore up to the top-frame casting underside (999.7),
its top seat clamped flush to it: the #6-32 screw threads into a 9.7 full-thread
bottoming tap (drill 10.9) on the bore's vertical centreline, which leaves 2.0
of metal over the bore crown at worst case; the dowel's blind flat-bottom reamed
hole sits 6.350 along +X from the tap axis.

The named "knife axis" is the contact ridge line itself (part origin); the
assembly mates the lever's knife ridge (``Axis3@sm-summing-lever``) coincident to
it, so the lever rocks about the true knife edge (not the cylinder centre).

Dimensions: cad/DIMENSIONS.md ch. 18. Bore/clearance: low confidence (tune vs
ch30 parity); the only hard constraint is "only the top edge contacts".

Run (SolidWorks already open)::

    uv run python cad\scripts\build_sm_knife_mount.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    SketchDims,
    _early_bound,
    add_line_chain,
    apply_color,
    apply_material,
    check,
    define_circle,
    define_rectilinear_chain,
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
from sm_summing_lever_spec import HEX_H, HEX_W
from _fit_limits import deviations
from _holes import (
    blind_hole_volume_mm3,
    find_planar_face,
    wizard_holes,
)
from _drawing_marks import (
    apply_drawing_precision,
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
    set_dimension_bilateral_tolerance,
)
from _part_pmi import author_part_pmi
from sm_knife_mount_spec import (
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION,
    ISOMETRIC_VIEW_NOTE,
    PIN_HOLE_DEPTH,
    PIN_HOLE_DIA,
    PIN_HOLE_DIA_BAND,
    PIN_HOLE_X,
    STUD_TAP_DIA,
    STUD_TAP_DRILL_DEPTH,
    STUD_TAP_SPEC,
    SURFACE_FINISHES,
)
import sm_knife_mount_spec

import _telemetry

PART_NAME = "sm-knife-mount"
# ch18 p.42 (2026-09-02 user re-read): an unpainted HEAT-TREATED steel block,
# not the brass of the earlier registry/DFM pass.
MATERIAL = "Plain Carbon Steel"
HARDENED_STEEL = (0.30, 0.30, 0.31)  # dark heat-treated grey, left unpainted

# --- knife-edge geometry (kept in sync with the lever's hex trunnion) -------
RIDGE_Y = HEX_H / 2.0  # hex top vertex above the pivot/cylinder centreline (5.134)

# --- bore: close around the hex trunnion, top-edge contact only ------------
R_BORE = 6.0  # Ø12 bore (2026-09-02 ch18 p.42 re-read: a CLOSE bore, down from
# the Ø16 of the 2026-09 page001_img01 pass); the hex is 8.653 wide x 10.268
# tall (~Ø10.3 across-corners) -> ~0.87 clear on the diagonal, ~0.6 at the
# shoulders, everywhere but the top vertex line
TOP_CLEAR = 0.25  # hex top vertex hangs this far below the bore upper inner wall
# Bore centre BELOW the origin so only the upper wall reaches the ridge:
BORE_CY = TOP_CLEAR - R_BORE  # -5.75 (bore top inner wall at local y +TOP_CLEAR)

# --- block (bearing body, held to the crossbar) ----------------------------
SUPPORT_Z_THICK = 14.0  # axial length straddling the trunnion mid (low)
BLK_HALF_X = 12.0  # bore wall + flank (24 across, photo-scaled)
WALL = 3.0  # material below the bore
BLK_BOT = BORE_CY - R_BORE - WALL  # -14.75

# Mount: the block top seat is clamped to the top-frame casting underside (the
# integral crossbar's flush lower face) by the #6-32 knife-hanger screw threaded
# into the block top (build_sm_summing_assembly).
KNIFE_Y = 979.7  # machine y of the pivot centreline (build_sm_summing_assembly KNIFE)
CASTING_UNDERSIDE_Y = 999.7  # top-frame casting underside (integral crossbar)
MOUNT_GAP = 0.0  # seat clamped to the casting underside by the #6-32 screw
CONTACT_Y = KNIFE_Y + RIDGE_Y  # machine y of the knife-edge contact line (984.834)
BLK_TOP = CASTING_UNDERSIDE_Y - CONTACT_Y - MOUNT_GAP  # local top (14.87)
if abs(BLK_TOP - sm_knife_mount_spec.BLK_TOP) > 0.005:
    raise AssertionError(
        f"knife-mount BLK_TOP {BLK_TOP:.4f} != spec {sm_knife_mount_spec.BLK_TOP}"
    )
# The spec judges the tap's web at its rounded mirror; the derived top is
# 0.004 lower, so re-judge it here (2.038).
_TAP_WEB_WORST = sm_knife_mount_spec.tap_web_worst(
    BLK_TOP,
    sm_knife_mount_spec.STUD_TAP_DRILL_DEPTH,
    sm_knife_mount_spec.STUD_TAP_DIA,
)
if _TAP_WEB_WORST < sm_knife_mount_spec.STUD_TAP_WEB_MIN:
    raise AssertionError(
        f"knife-mount tap point leaves {_TAP_WEB_WORST:.3f} over the bore crown"
    )

THROUGH_CUT_DEPTH = SUPPORT_Z_THICK + 4.0  # > the block thickness, both directions

# --- the MHA-VN-051 dowel hole: blind, flat-floored, reamed in the top seat --
_R_PIN = PIN_HOLE_DIA / 2.0
V_PIN = math.pi * _R_PIN**2 * PIN_HOLE_DEPTH


async def _volume(adapter) -> float:
    res = await adapter.get_mass_properties()
    return res.data.volume if res.is_success else float("nan")


async def _mass(adapter) -> tuple[float, list[float]]:
    res = await adapter.get_mass_properties()
    if not res.is_success:
        raise RuntimeError(f"knife-mount mass properties failed: {res.error}")
    return float(res.data.volume), [float(c) for c in res.data.center_of_mass]


def _open_top_seat_sketch(adapter) -> tuple[float, float, bool]:
    """Open a sketch ON the top seat; map the dowel-hole centre into it.

    The MHA-PD-018 latch-pin precedent (``build_pd_transgear_arm``
    ``_open_end_face_sketch``): a face sketch anchors the blind depth on the
    real seat edge.  The face's sketch axes are SolidWorks' choice, so the
    centre maps through ``ModelToSketchTransform``.  Returns the sketch
    ``(u, v)`` and whether the sketch normal points OUT of the seat (+Y).
    """
    import pythoncom
    from win32com.client import VARIANT

    model = _early_bound(adapter.currentModel, "IModelDoc2")
    centre = (PIN_HOLE_X, BLK_TOP, 0.0)
    face = find_planar_face(model, (0.0, 1.0, 0.0), [list(centre)])
    model.ClearSelection2(True)
    if not _early_bound(face, "IEntity").Select2(False, 0):
        raise RuntimeError("dowel hole: top seat Select2 failed")
    adapter.currentSketchManager = model.SketchManager
    adapter._reset_sketch_entity_registry()
    model.SketchManager.InsertSketch(True)
    active = adapter.currentModel.GetActiveSketch2()
    if active is None:
        raise RuntimeError("dowel hole: no active sketch on the top seat")
    adapter.currentSketch = active
    adapter._sketch_count += 1
    adapter._last_sketch_name = str(active.Name)
    sketch = _early_bound(active, "ISketch")
    math_util = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    xform = _early_bound(sketch.ModelToSketchTransform, "IMathTransform")

    def to_sketch(model_mm: tuple[float, float, float]) -> tuple[float, ...]:
        point = math_util.CreatePoint(
            VARIANT(
                pythoncom.VT_ARRAY | pythoncom.VT_R8, [c / 1000.0 for c in model_mm]
            )
        )
        mapped = _early_bound(
            _early_bound(point, "IMathPoint").MultiplyTransform(xform), "IMathPoint"
        )
        return tuple(c * 1000.0 for c in mapped.ArrayData)

    u, v, w = to_sketch(centre)
    if abs(w) > 1e-4:
        raise RuntimeError(f"dowel hole centre is {w:g} mm off the top-seat sketch")
    w_out = to_sketch((PIN_HOLE_X, BLK_TOP + 1.0, 0.0))[2]
    if abs(abs(w_out) - 1.0) > 1e-4:
        raise RuntimeError(f"top-seat sketch normal is not along Y (w {w_out:g})")
    return u, v, w_out > 0.0


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
    await set_global(adapter, "PinHoleX", f"{PIN_HOLE_X}mm")
    await set_global(adapter, "PinHoleDia", f"{PIN_HOLE_DIA}mm")
    await set_global(adapter, "PinHoleDepth", f"{PIN_HOLE_DEPTH}mm")
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

    # Sanity: hex must fit the bore with only the top vertex near the wall.
    hex_top = 0.0  # ridge = origin
    gap_top = (BORE_CY + R_BORE) - hex_top
    if not 0.0 < gap_top < 0.5:
        raise RuntimeError(f"top-edge gap {gap_top:.3f} mm out of (0, 0.5)")
    # widest hex point (shoulder at +-HEX_W/2, y = -RIDGE_Y +- HEX_H/4) must
    # clear the bore wall.
    for sy in (-RIDGE_Y + HEX_H / 4.0, -RIDGE_Y - HEX_H / 4.0):
        d = math.hypot(HEX_W / 2.0, sy - BORE_CY)
        if d > R_BORE - 0.5:
            raise RuntimeError(
                f"hex shoulder {d:.3f} mm too close to Ø{2 * R_BORE} bore"
            )

    # Hanger-screw tap: ONE native Hole Wizard #6-32 bottoming tapped hole in
    # the block top (drill STUD_TAP_DRILL_DEPTH, full thread to the spec's
    # ThreadDepth override), on the trunnion-axis centreline (both placement
    # coords are zero -> origin-axis relations, no placement dims). The
    # analytic expectation subtracts the drill cylinder to its depth plus the
    # drill point; the point stops STUD_TAP_WEB_WORST (2.04) above the bore
    # crown, so none of it overlaps the bore void.
    wizard_holes(
        adapter,
        STUD_TAP_SPEC,
        [[0.0, BLK_TOP, 0.0]],
        (0.0, 1.0, 0.0),
        "knife-hanger screw tapped hole (#6-32)",
        name="StudTap",
        # no expect_dia_mm: a BLIND hole's definition reads 0.0 for both
        # diameter knobs on this seat (the tripwire is through-hole only);
        # the pinned dia is what HoleWizard5 was handed, and the volume
        # gate below proves the cut.
    )
    expected -= blind_hole_volume_mm3(STUD_TAP_DIA, STUD_TAP_DRILL_DEPTH)
    vol = await _volume(adapter)
    _telemetry.info(f"volume after stud tap: {vol:.1f} mm^3 (analytic {expected:.1f})")
    if abs(vol - expected) > 0.01 * expected:
        raise RuntimeError(f"stud tap volume {vol:.1f} != {expected:.1f}")

    # MHA-VN-051 dowel hole: blind along -Y from the top seat, PIN_HOLE_X along
    # +X from the tap axis (the MHA-PD-018 latch-pin hole precedent). A plain
    # cut-extrude, so the floor is flat: the dowel is pressed onto it (a
    # wizard drill point would leave a cone under the pressed end).
    before, com_before = await _mass(adapter)
    pin = SketchDims()
    u, v, normal_out = _open_top_seat_sketch(adapter)
    # The seat's sketch axes carry model x on one axis and z (= 0) on the
    # other; the one nonzero centre offset is the station from the tap axis.
    if abs(abs(u) - PIN_HOLE_X) < 1e-4 and abs(v) < 1e-4:
        v = 0.0
    elif abs(abs(v) - PIN_HOLE_X) < 1e-4 and abs(u) < 1e-4:
        u = 0.0
    else:
        raise RuntimeError(
            f"dowel-hole centre mapped to unexpected sketch ({u:g}, {v:g})"
        )
    await define_circle(
        adapter,
        u,
        v,
        _R_PIN,
        "dowel hole",
        dims=pin,
        names=("PinHoleX", "PinHoleX", "PinHoleDia"),
        drives=('"PinHoleX"', '"PinHoleX"', '"PinHoleDia"'),
    )
    await ensure_fully_defined(adapter, "dowel hole sketch")
    check("exit_sketch dowel hole", await adapter.exit_sketch())
    name_last_feature(adapter, "PinHoleProfile")
    drive_jobs += pin.apply(adapter, "PinHoleProfile")
    # A cut runs opposite the sketch normal unless reversed.
    check(
        "cut dowel hole",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=PIN_HOLE_DEPTH, reverse_direction=not normal_out)
        ),
    )
    name_last_feature(adapter, "PinHole")
    drive_jobs += [
        (name_dimensions(adapter, "PinHole", ["PinHoleDepth"])[0], '"PinHoleDepth"')
    ]
    expected -= V_PIN
    after, com_after = await _mass(adapter)
    if abs((before - after) - V_PIN) > 0.02 * V_PIN:
        raise RuntimeError(
            f"dowel hole removed {before - after:.2f} mm^3, expected "
            f"{V_PIN:.2f}: circle misplaced or cut the wrong way"
        )
    # Material removed at +X moves the centre of mass toward -X.
    if com_after[0] >= com_before[0]:
        raise RuntimeError(
            f"dowel hole missed the +X station (COM x {com_before[0]:.4f} -> "
            f"{com_after[0]:.4f})"
        )
    _telemetry.success(
        f"dowel hole (top-seat sketch {u:+g}, {v:+g}) removed "
        f"{before - after:.2f} mm^3 (analytic {V_PIN:.2f})"
    )

    # Named axis = the knife-edge contact ridge line (part origin, along Z). The
    # assembly mates Axis3@sm-summing-lever (the hex ridge) coincident to it.
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

    await apply_material(adapter, MATERIAL)
    # ch18 p.42: heat-treated and left unpainted -- a dark grey, not the
    # database steel's bright render nor the frame's green.
    await apply_color(adapter, HARDENED_STEEL)
    await report_mass_properties(adapter)

    # Explicit band on the dowel ream (the station and depth are governed by
    # their places); then the places the sheet prints (DRAWING_PRECISION).
    set_dimension_bilateral_tolerance(
        adapter, "PinHoleProfile", "PinHoleDia", *deviations(PIN_HOLE_DIA_BAND)
    )
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    # Manufacturing drawing support: mark exactly the print's dimensions and
    # stamp the make-critical title-block properties.
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    author_part_pmi(adapter, surface_finishes=SURFACE_FINISHES)
    apply_drawing_properties(
        adapter,
        PART_NAME,
        {"Isometric View Note": ISOMETRIC_VIEW_NOTE},
    )
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
