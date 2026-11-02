r"""Reproduction script: knife bearing support (book ch. 18, pp. 42-43).

The hardened-steel bearing block that suspends the summing lever's knife edge from the
top-frame casting's integral crossbar (clamped to its underside by the MHA-SM-VN-52
#10-24 plain hex bolt, through a washer on the crossbar's faced top, threaded into
a bottoming tap in the block top, and keyed against turning by the two
MHA-SM-VN-53 dowels pressed into the crossbar, which slip into the block's
top-seat round hole and its slot open to the -X face; owner ruling 2026-10-24,
T+H3).
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
a CLOSE bore around the trunnion -- Ø.472 (#290: Ø12 on the inch grid) over
the 8.080 x 10.268 hex, so the upper shoulders clear by ~0.86 and the lower
ones by ~1.5.

There are TWO supports, one per trunnion (placed front/back in the assembly at
|z| ~ 87). This single part is built once and placed twice.

Layout (part-local): origin = the **knife-edge contact line** = the hex top
vertex ridge (placed at machine (15, 984.83, +-87)); local Z = the bore/trunnion
axis, +Y up, +X across. The bore centre sits ``R_BORE`` below the origin so the
bore's upper inner wall lands on the ridge (with a TOP_CLEAR sliver margin). The
block rises from below the bore up to the top-frame casting's faced underside
(999.7), its top seat clamped flush to it: the #10-24 bolt threads into a
.375 +/-.005 full-thread bottoming tap (drill .438) on the bore's vertical
centreline, whose charged pilot (Ø3.924, past the accepted Ø3.7973-3.8989)
at its sharpest accepted point leaves the .080 rule-17 target of metal over
the bore crown at worst case; the dowels' blind flat-floored round slip hole
(+X, datum B) and open slot (-X, datum C) sit .300 either side of the tap
axis along X, in a block 1.00 across.

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

from _appearance import apply_color, apply_material
from _document_units import apply_package_model_units
from _part_properties import part_drawing_unit
from _bore_axis import name_bore_axis
from _check import check
from _com import _early_bound
from _dimensions import drive_dimension, name_dimensions, set_global
from _feature_tree import name_last_feature
from _part_checks import report_mass_properties, volume_check
from _part_save import save_part_and_images
from _rebuild import force_rebuild
from _session import run_build
from _sketch import (
    SketchDims,
    add_line_chain,
    dimension_between,
    ensure_fully_defined,
    set_sketch_direct_db,
)
from _sketch_chains import define_rectilinear_chain
from _sketch_circle import define_circle
from sm_summing_lever_spec import HEX_H, HEX_W
from _fit_deviations import deviations
from _holes import (
    blind_hole_volume_mm3,
    find_planar_face,
    wizard_holes,
)
from _drawing_precision import apply_drawing_precision
from _drawing_marks import (
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from _drawing_tolerances import (
    set_dimension_bilateral_tolerance,
    set_dimension_symmetric_tolerance,
)
from _part_pmi import author_part_pmi
from sm_knife_mount_spec import (
    BLK_HALF_X,
    BORE_DIA_BAND,
    BORE_DIA_PLACES,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION,
    ISOMETRIC_VIEW_NOTE,
    PIN_HOLE_DEPTH,
    PIN_HOLE_DIA,
    PIN_HOLE_DIA_BAND,
    PIN_HOLE_X,
    SLOT_END_FROM_B,
    SLOT_WIDTH,
    SLOT_WIDTH_BAND,
    STUD_TAP_DIA,
    STUD_TAP_DRILL_DEPTH,
    STUD_TAP_SPEC,
    STUD_THREAD,
    SUPPORT_Z_THICK,
    SURFACE_FINISHES,
    UNIT,
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
R_BORE = sm_knife_mount_spec.R_BORE  # Ø.472 bore (2026-09-02 ch18 p.42 re-read:
# a CLOSE bore); the hex is 8.080 wide x 10.268 tall -> ~0.86 clear at the
# upper shoulders, ~1.5 at the lower ones, everywhere but the top vertex line
# Hex top vertex hangs this far below the bore upper inner wall: 0.261 puts
# the bore centre's BASIC height under the top seat on the inch grid,
# 14.866 - 0.261 + 5.9944 = 20.5994 (.811).
TOP_CLEAR = 0.261
# Bore centre BELOW the origin so only the upper wall reaches the ridge:
BORE_CY = TOP_CLEAR - R_BORE  # -5.7334 (bore top inner wall at local y +TOP_CLEAR)

# --- block (bearing body, held to the crossbar) ----------------------------
# SUPPORT_Z_THICK (.55) and BLK_HALF_X (1.00 across) are the spec's: the
# dowel pattern's webs size them.
WALL = 3.1242  # material below the bore: the block 1.17 tall
BLK_BOT = BORE_CY - R_BORE - WALL  # -14.852

# Mount: the block top seat is clamped to the top-frame casting underside (the
# integral crossbar's flush lower face, faced Ra 3.2 with the whole underside
# plane between the bosses, user ruling 2026-10-12) by the #10-24 knife-hanger
# bolt threaded into the block top (build_sm_summing_assembly).  999.7 is the
# finished plane: the facing cut comes out of casting allowance.
KNIFE_Y = 979.7  # machine y of the pivot centreline (build_sm_summing_assembly KNIFE)
CASTING_UNDERSIDE_Y = 999.7  # top-frame faced underside (integral crossbar)
MOUNT_GAP = 0.0  # seat clamped to the faced underside by the #10-24 bolt
CONTACT_Y = KNIFE_Y + RIDGE_Y  # machine y of the knife-edge contact line (984.834)
BLK_TOP = CASTING_UNDERSIDE_Y - CONTACT_Y - MOUNT_GAP  # local top (14.866)
if abs(BLK_TOP - sm_knife_mount_spec.BLK_TOP) > 0.005:
    raise AssertionError(
        f"knife-mount BLK_TOP {BLK_TOP:.4f} != spec {sm_knife_mount_spec.BLK_TOP}"
    )
if (
    abs(BORE_CY - sm_knife_mount_spec.BORE_CY) > 1e-9
    or abs(BLK_BOT - sm_knife_mount_spec.BLK_BOT) > 1e-9
):
    raise AssertionError(
        f"knife-mount bore centre {BORE_CY:.4f} / bottom {BLK_BOT:.4f} != spec"
    )
# The bore centre's BASIC height under the datum-A top seat, exactly as
# modelled: 14.866 + 5.7334 = 20.5994 (.811).  The sheet prints it
# (draw_sm_knife_mount) at the places that carry it unrounded.
BORE_CENTRE_DEPTH = BLK_TOP - BORE_CY
# The spec judges the tap's web at its mirror; re-judge it here at the
# derived top (2.110: the charged pilot envelope, Ø3.924, not the accepted
# Ø3.8989, at the sharpest accepted point, 117 deg).
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

# --- the MHA-SM-VN-53 slip seats: blind, flat-floored, in the top seat ------
_R_PIN = PIN_HOLE_DIA / 2.0
V_PIN = math.pi * _R_PIN**2 * PIN_HOLE_DEPTH
# The slot's half-round inner end and its straight run out through the -X
# face; the stadium's outer end is modelled past the face, in air.
SLOT_INNER_X = PIN_HOLE_X - SLOT_END_FROM_B  # -6.768
SLOT_OUTER_X = -(BLK_HALF_X + SLOT_WIDTH)  # -15.94, clear of the -X face
SLOT_FLAT = SLOT_INNER_X - SLOT_OUTER_X  # 9.172
if SLOT_OUTER_X + SLOT_WIDTH / 2.0 >= -BLK_HALF_X:
    raise AssertionError("the slot's modelled outer end reaches into the block")
V_SLOT = (
    (SLOT_INNER_X + BLK_HALF_X) * SLOT_WIDTH + math.pi * SLOT_WIDTH**2 / 8.0
) * PIN_HOLE_DEPTH
V_PINS = V_PIN + V_SLOT


def slot_stadium_points(
    centre: tuple[float, float], *, along_u: bool, half_flat: float, half_w: float
) -> tuple[tuple[float, float], ...]:
    """The slot's stadium in sketch ``(u, v)``, counter-clockwise.

    Returns ``(p1, p2, p3, p4, centre_b, centre_a)``: side a runs p1 -> p2,
    end b arcs (CCW, the ``add_arc`` sense) about centre_b from p2 to p3,
    side b runs p3 -> p4 and end a arcs about centre_a from p4 back to p1.
    The slot runs along sketch u when ``along_u``, else along v (the same
    shape turned a quarter, which keeps it counter-clockwise).  Moved here
    with the slot from ``build_fr_top_frame`` (owner ruling 2026-10-24, T+H3).
    """
    u0, v0 = centre

    def at(du: float, dv: float) -> tuple[float, float]:
        return (u0 + du, v0 + dv) if along_u else (u0 - dv, v0 + du)

    return (
        at(-half_flat, -half_w),
        at(half_flat, -half_w),
        at(half_flat, half_w),
        at(-half_flat, half_w),
        at(half_flat, 0.0),
        at(-half_flat, 0.0),
    )


async def _volume(adapter) -> float:
    res = await adapter.get_mass_properties()
    return res.data.volume if res.is_success else float("nan")


async def _mass(adapter) -> tuple[float, list[float]]:
    res = await adapter.get_mass_properties()
    if not res.is_success:
        raise RuntimeError(f"knife-mount mass properties failed: {res.error}")
    return float(res.data.volume), [float(c) for c in res.data.center_of_mass]


def _open_top_seat_sketch(
    adapter, stations_x: tuple[float, ...], on_seat: int
) -> tuple[list[tuple[float, float]], bool]:
    """Open a sketch ON the top seat; map points on the dowel line into it.

    The MHA-PD-18 latch-pin precedent (``build_pd_transgear_arm``
    ``_open_end_face_sketch``): a face sketch anchors the blind depth on the
    real seat edge.  The face's sketch axes are SolidWorks' choice, so the
    points map through ``ModelToSketchTransform``.  The first ``on_seat``
    stations lie on the seat and pick it; the rest may stand past its edge.
    Returns each station's sketch ``(u, v)`` in order and whether the sketch
    normal points OUT of the seat (+Y).
    """
    import pythoncom
    from win32com.client import VARIANT

    model = _early_bound(adapter.currentModel, "IModelDoc2")
    centres = [(x, BLK_TOP, 0.0) for x in stations_x]
    face = find_planar_face(
        model, (0.0, 1.0, 0.0), [list(c) for c in centres[:on_seat]]
    )
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

    mapped: list[tuple[float, float]] = []
    for centre in centres:
        u, v, w = to_sketch(centre)
        if abs(w) > 1e-4:
            raise RuntimeError(f"dowel-line point is {w:g} mm off the top-seat sketch")
        mapped.append((u, v))
    w_out = to_sketch((PIN_HOLE_X, BLK_TOP + 1.0, 0.0))[2]
    if abs(abs(w_out) - 1.0) > 1e-4:
        raise RuntimeError(f"top-seat sketch normal is not along Y (w {w_out:g})")
    return mapped, w_out > 0.0


async def _volume(adapter) -> float:
    res = await adapter.get_mass_properties()
    return res.data.volume if res.is_success else float("nan")


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import ExtrusionParameters

    check("create_part", await adapter.create_part())
    apply_package_model_units(adapter, part_drawing_unit(PART_NAME), label=PART_NAME)

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
    await set_global(adapter, "SlotWidth", f"{SLOT_WIDTH}mm")
    await set_global(adapter, "SlotEndFromB", f"{SLOT_END_FROM_B}mm")
    await set_global(adapter, "SlotFlat", f"{SLOT_FLAT}mm")
    await set_global(adapter, "BoreCy", '"TopClear" - "RBore"')
    await set_global(adapter, "BlkBot", '"BoreCy" - "RBore" - "Wall"')

    # Each sketch records its dim names + drive equations as the define_* helper
    # emits them; the equations are collected here and applied in one deferred
    # batch at the end (every target must resolve against the finished model).
    drive_jobs: list[tuple[str, str]] = []

    # 1. Bearing block: Front-plane rectangle, mid-plane extrude along Z (the
    #    bore/trunnion axis), straddling the trunnion mid. Asymmetric in Y (not
    #    origin-centred), so a generic rectilinear chain, not define_centered_*.
    #    Emission order (anchor vertex 0 at (BlkHalfX, BlkBot)): the width dim
    #    (seg 0, the bottom edge), the height dim (seg 1, the -X face), then
    #    the anchor dims (x, then z).  The height dim is on the -X face, the
    #    side the drawing prints it: on the +X face its extension lines ran
    #    across the front view to the left, under the bore's position-frame
    #    leader (layout audit leader-crosses-line, MHA-SM-02).
    block_dims = SketchDims()
    check("create_sketch block", await adapter.create_sketch("Front"))
    block_rect = [
        (BLK_HALF_X, BLK_BOT),
        (-BLK_HALF_X, BLK_BOT),
        (-BLK_HALF_X, BLK_TOP),
        (BLK_HALF_X, BLK_TOP),
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

    # Hanger-bolt tap: ONE native Hole Wizard #10-24 bottoming tapped hole in
    # the block top (drill STUD_TAP_DRILL_DEPTH, full thread to the spec's
    # ThreadDepth override), on the trunnion-axis centreline (both placement
    # coords are zero -> origin-axis relations, no placement dims). The
    # analytic expectation subtracts the nominal drill cylinder to its depth
    # plus its 118 deg point; even the charged pilot envelope at its sharpest
    # accepted point stops _TAP_WEB_WORST (2.110) above the bore crown, so
    # none of it overlaps the bore void.
    wizard_holes(
        adapter,
        STUD_TAP_SPEC,
        [[0.0, BLK_TOP, 0.0]],
        (0.0, 1.0, 0.0),
        f"knife-hanger bolt tapped hole ({STUD_THREAD})",
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

    # MHA-SM-VN-53 slip seats (owner ruling 2026-10-24, T+H3: the dowels
    # press into the crossbar and slip into this block): blind along -Y from
    # the top seat, a round hole PIN_HOLE_X +X of the tap axis (datum B) and
    # a slot along the dowel line -X of it (datum C), open through the -X
    # face.  One sketch, one plain cut-extrude, so both floors are flat at one
    # depth.  The slot is ONE closed stadium (two straight sides joined by
    # two tangent half-round ends, the ``build_fr_top_frame`` dowel-slot
    # pattern), its outer end modelled in air past the face; its inner end's
    # centre stands SlotEndFromB from B's centre along the line.
    before, com_before = await _mass(adapter)
    pin = SketchDims()
    (b_uv, inner_uv, outer_uv), normal_out = _open_top_seat_sketch(
        adapter, (PIN_HOLE_X, SLOT_INNER_X, SLOT_OUTER_X), on_seat=2
    )
    along_u = abs(outer_uv[0] - inner_uv[0]) > abs(outer_uv[1] - inner_uv[1])

    # The seat's sketch axes carry model x on one axis and z (= 0) on the
    # other: snap the across coordinate of every dowel-line point to zero.
    def on_line(uv: tuple[float, float], label: str) -> tuple[float, float]:
        across = uv[1] if along_u else uv[0]
        if abs(across) > 1e-4:
            raise RuntimeError(f"{label} mapped {across:g} mm off the dowel line")
        return (uv[0], 0.0) if along_u else (0.0, uv[1])

    b_uv = on_line(b_uv, "datum-B hole centre")
    inner_uv = on_line(inner_uv, "slot inner end")
    outer_uv = on_line(outer_uv, "slot outer end")
    b_circle = await define_circle(
        adapter,
        *b_uv,
        _R_PIN,
        f"datum-B slip hole x {PIN_HOLE_X:+.3f}",
        dims=pin,
        names=("PinHoleX", "PinHoleX", "PinHoleDia"),
        drives=('"PinHoleX"', '"PinHoleX"', '"PinHoleDia"'),
    )
    p1, p2, p3, p4, c_end_b, c_end_a = slot_stadium_points(
        ((inner_uv[0] + outer_uv[0]) / 2.0, (inner_uv[1] + outer_uv[1]) / 2.0),
        along_u=along_u,
        half_flat=SLOT_FLAT / 2.0,
        half_w=SLOT_WIDTH / 2.0,
    )
    set_sketch_direct_db(adapter, True)
    try:
        side_a = check("dowel slot side a", await adapter.add_line(*p1, *p2))
        end_b = check("dowel slot end b", await adapter.add_arc(*c_end_b, *p2, *p3))
        side_b = check("dowel slot side b", await adapter.add_line(*p3, *p4))
        end_a = check("dowel slot end a", await adapter.add_arc(*c_end_a, *p4, *p1))
    finally:
        set_sketch_direct_db(adapter, False)
    for join, a, b in (
        ("side a - end b", f"{side_a}.end", f"{end_b}.start"),
        ("end b - side b", f"{end_b}.end", f"{side_b}.start"),
        ("side b - end a", f"{side_b}.end", f"{end_a}.start"),
        ("end a - side a", f"{end_a}.end", f"{side_a}.start"),
    ):
        check(
            f"dowel slot {join}",
            await adapter.add_sketch_constraint(a, b, "coincident"),
        )
    along = "horizontal" if along_u else "vertical"
    for side in (side_a, side_b):
        check(
            f"dowel slot {side} {along}",
            await adapter.add_sketch_constraint(side, None, along),
        )
    for a, b in ((side_a, end_b), (end_b, side_b), (side_b, end_a), (end_a, side_a)):
        check(
            f"dowel slot {a} tangent {b}",
            await adapter.add_sketch_constraint(a, b, "tangent"),
        )
    inner_end = (
        end_b if math.dist(c_end_b, inner_uv) < math.dist(c_end_a, inner_uv) else end_a
    )
    inner_centre = c_end_b if inner_end == end_b else c_end_a
    if math.dist(inner_centre, inner_uv) > 1e-4 or not math.isclose(
        math.dist(b_uv, inner_uv), SLOT_END_FROM_B, abs_tol=1e-4
    ):
        raise RuntimeError(
            f"dowel slot inner end {inner_uv} is not {SLOT_END_FROM_B} from B {b_uv}"
        )
    # The inner end's centre on B's line, SlotEndFromB from B's centre.  Two
    # points take the point relation (``anchor_point_to_origin``'s
    # ``horizontal_points``): the line relation ``horizontal`` on two points
    # reported success and left the sketch under-defined (farm run
    # 20261024T132600239Z, part:sm_knife_mount).
    check(
        "dowel slot inner end on B's line",
        await adapter.add_sketch_constraint(
            f"{b_circle}.center",
            f"{inner_end}.center",
            "horizontal_points" if along_u else "vertical_points",
        ),
    )
    distance_kind = "horizontal_distance" if along_u else "vertical_distance"
    across_kind = "vertical_distance" if along_u else "horizontal_distance"
    # Emission order: the width across the sides, the near side's straight
    # run, then the inner end's station from B.
    await dimension_between(
        adapter,
        f"{side_a}.start",
        f"{side_b}.end",
        across_kind,
        SLOT_WIDTH,
        "dowel slot width",
    )
    pin.record("SlotWidth", '"SlotWidth"')
    await dimension_between(
        adapter,
        f"{side_a}.start",
        f"{side_a}.end",
        distance_kind,
        SLOT_FLAT,
        "dowel slot run",
    )
    pin.record("SlotFlat", '"SlotFlat"')
    await dimension_between(
        adapter,
        f"{b_circle}.center",
        f"{inner_end}.center",
        distance_kind,
        SLOT_END_FROM_B,
        "dowel slot inner end from B",
    )
    pin.record("SlotEndFromB", '"SlotEndFromB"')
    await ensure_fully_defined(adapter, "dowel slip-seat sketch")
    check("exit_sketch dowel slip seats", await adapter.exit_sketch())
    name_last_feature(adapter, "PinHoleProfile")
    drive_jobs += pin.apply(adapter, "PinHoleProfile")
    # A cut runs opposite the sketch normal unless reversed.
    check(
        "cut dowel slip seats",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=PIN_HOLE_DEPTH, reverse_direction=not normal_out)
        ),
    )
    name_last_feature(adapter, "PinHole")
    drive_jobs += [
        (name_dimensions(adapter, "PinHole", ["PinHoleDepth"])[0], '"PinHoleDepth"')
    ]
    expected -= V_PINS
    after, com_after = await _mass(adapter)
    if abs((before - after) - V_PINS) > 0.02 * V_PINS:
        raise RuntimeError(
            f"dowel slip seats removed {before - after:.2f} mm^3, expected "
            f"{V_PINS:.2f}: the hole or slot misplaced or cut the wrong way"
        )
    # The slot (-X) removes more than the round hole (+X), so the centre of
    # mass moves +X (a mirrored sketch moves it -X) and drops (the material
    # left the top).
    if com_after[0] <= com_before[0] or com_after[1] >= com_before[1]:
        raise RuntimeError(
            "dowel slip seats are not the +X hole and -X slot (COM "
            f"{com_before[0]:.4f}, {com_before[1]:.4f} -> "
            f"{com_after[0]:.4f}, {com_after[1]:.4f})"
        )
    _telemetry.success(
        f"dowel slip seats (top-seat sketch B {b_uv}, slot {inner_uv}) removed "
        f"{before - after:.2f} mm^3 (analytic {V_PINS:.2f})"
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

    # Explicit slip bands on datum B's Ø and datum C's width (their stations
    # and depth are governed by their places).  Each band is equal either
    # side, so it prints +/- on one row (ASME Y14.5 equal-bilateral form, the
    # crossbar's former slip hole and slot precedent): .1280 +/-.0007.
    for dim_name, band in (
        ("PinHoleDia", PIN_HOLE_DIA_BAND),
        ("SlotWidth", SLOT_WIDTH_BAND),
    ):
        lower, upper = deviations(band)
        if lower != -upper:
            raise AssertionError(f"the knife mount's {dim_name} band must be symmetric")
        set_dimension_symmetric_tolerance(
            adapter, "PinHoleProfile", dim_name, upper, display_unit=UNIT
        )
    # The bored knife bore's +.0012/0 band (sm_knife_mount_spec.BORE_DIA_BAND),
    # printed at its four places: Ø.4720 +.0012/.0000 THRU.
    set_dimension_bilateral_tolerance(
        adapter,
        "BoreProfile",
        "BoreDia",
        *deviations(BORE_DIA_BAND),
        places=BORE_DIA_PLACES,
        display_unit=UNIT,
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
