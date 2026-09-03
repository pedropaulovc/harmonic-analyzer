r"""Reproduction script: harmonic analyzer base (book ch. 6 / legacy part).

Two-plate welded construction based on the legacy 18.0 x 11.0 x 0.5 in
flange and 17.5 x 10.5 x 1.5 in pad. The v2 post/carrier fit preserves their
both plates remain on the legacy centred footprint; the v2 post/carrier fit is
handled by the mechanism installation contracts.

Top-face seats: the cone-swing pivot/stop taps, the pinion-rig block/foot
taps, and (2026-09-02) the four blind #4-40 taps under the maker's nameplate's
corner screws -- stations derived from the plate's own hole pattern through
its mount transform (``nameplate_spec``), so the plate, the base and the
frame's screws can never drift apart.

Finishing (chamfer external, fillet internal; legacy 1/8-1/16 sizes): C3.18
x 45 breaks on the eight vertical plan corners, C1.59 x 45 breaks on both
plates' exposed top rims and the underside rim, and the R0.50 pad-to-flange
root fillet note 1 caps -- the one internal wall junction on the part
(ch06/ch30 photos: every exposed plate edge reads softened, none sharp).

Dimensions: cad/DIMENSIONS.md "Chapter 6" — annotated (high) footprint,
legacy thicknesses (photo-verify note).

Layout: plates are centred in X and Z. Top-plane sketches map sketch x,y -> global X,-Z and
stack along +Y. Top plate boss starts at the bottom plate's upper face via
extrude_at_offset (raw-COM stopgap until MCP Phase 3).

Run (SolidWorks already open)::

    uv run python cad\scripts\build_harmonic_base.py
"""

from __future__ import annotations

import math
import sys

from _common import (
    CASTING_GREEN,
    PANEL_BLACK,
    SketchDims,
    _dim_value_mm,
    _display_dimensions,
    _early_bound,
    _feature_by_name,
    add_line_chain,
    apply_color,
    apply_material,
    bbox_extent_check,
    check,
    define_rectilinear_chain,
    drive_dimension,
    ensure_fully_defined,
    extrude_at_offset,
    force_rebuild,
    name_last_feature,
    REFERENCES_DIR,
    report_mass_properties,
    run_build,
    save_part_and_images,
    set_global,
    volume_check,
)
from _drawing_marks import (
    _named_dimension,
    apply_drawing_properties,
    clear_dimensions_for_drawing,
    mark_dimensions_for_drawing,
)
from _holes import HoleSpec, blind_cut_dia_mm, blind_hole_volume_mm3, wizard_holes
from harmonic_base_spec import (
    BOTTOM_LENGTH,
    BOTTOM_THICKNESS,
    BOTTOM_WIDTH,
    DRAWING_DIMENSIONS,
    LIP_H,
    LIP_W,
    DRAWING_NOTES,
    SIDE_VIEW_NOTE,
    STACK_HEIGHT,
    TOP_LENGTH,
    TOP_THICKNESS,
    TOP_WIDTH,
)
import nameplate_spec
from cone_pivot_post_installation import (
    MECHANISM_X_SHIFT,
    MECHANISM_Z_SHIFT,
    POST_X_SHIFT,
    POST_Z_SHIFT,
)
from cone_pivot_screw_spec import (
    THREAD as PIVOT_THREAD,
    THREAD_TAIL_LEN as PIVOT_THREAD_ENGAGEMENT,
)
from rocker_arm_support_spec import SUPPORT_HOLD_DOWN_XZ

import _telemetry

PART_NAME = "harmonic-base"
MATERIAL = "Gray Cast Iron"  # see _common.apply_material docstring

# Plate nominal geometry (BOTTOM_*/TOP_*) lives in harmonic_base_spec -- the
# COM-free contract the drawing shares. DIMENSIONS.md ch6: 46 cm / 28 cm callouts
# = 18.1 x 11.0 in (annotated); legacy 18.0 x 11.0 kept, top plate 0.25 in reveal
# per side, thicknesses from the legacy HarmonicBase.cs (photo-verify M2 note).
IN = 25.4

# Rocker-support hold-down holes (machine = part-local: frame.SLDASM places the
# base unrotated at the origin).  The support contract transforms its unchanged
# four-hole foot pattern through the +90-degree installation and the v2 rear
# shift.  Base, support, and frame therefore cannot carry three drifting copies.
HOLE_DIA = 13.0  # 9/16 lag-screw shank O12 clearance
HOLE_XZ = SUPPORT_HOLD_DOWN_XZ
CBORE_DIA = 23.0  # lag head O22, recessed
CBORE_DEPTH = 6.5  # lag head 22 x 6 recessed 0.5
CBORE_XZ = HOLE_XZ  # all four heads counterbored

# Edge finishing (chamfer external, fillet internal; legacy 1/8-1/16 sizes).
# The machined plate gets 45-degree edge breaks on every external edge: the
# vertical plan corners at 1/8 in legs, the exposed top rims and the
# underside rim at 1/16 in (single-pass mill/file breaks). The one internal
# wall junction -- the pad side walls meeting the flange top face -- carries
# the R0.50 root fillet note 1 already caps (a cutter-corner radius). Every
# mechanism hole sits >= 26 from every plate edge; the closest seats to a rim
# are the nameplate taps (NAMEPLATE_SCREW_XZ), Ø2.26 at 12.5 in from the pad
# side and 5.5 inside the raised rim's inner wall -- still far clear of the
# 1.59 breaks, so no break touches a rim or seat.
# Plan corners are ROUNDED, not chamfered (2026-09 photo re-derive): every
# ch30 plate (p002/p003 front corners, p006 rear) shows the casting's vertical
# corners as one large radius running the full height, flange and pad
# together. 7/8 in on the flange; the pad's radius is 1/4 in smaller so the
# two arcs stay concentric across the 1/4 in reveal, and the raised rim's
# inner corners follow LIP_W further in.
FLANGE_CORNER_R = 0.875 * IN  # 22.225
PAD_CORNER_R = FLANGE_CORNER_R - (BOTTOM_LENGTH - TOP_LENGTH) / 2.0  # 15.875
RIM_CHAMFER = 0.0625 * IN  # 1.5875 legs, top rims + underside rim
PAD_ROOT_R = 0.5  # pad-to-flange root fillet (note 1: R0.50 MAX)

# Raised rim + black deck (2026-09 photo re-derive). Every plate that shows
# the base top -- ch11 p.21 (crank close-up), ch13 p.25 (cylinder-gear front),
# ch30 p002/p003/p006 -- reads it as a BLACK panel framed by a green lip
# standing a few mm proud of it, flush with the pad sides. The lip is a
# LIP_H-tall ring LIP_W wide on the pad's chamfered outline; the deck it
# frames stays at the pad top (STACK_HEIGHT), so nothing mounted on the base
# moves. The deck face is painted PANEL_BLACK at the FACE level (part and
# body stay casting green); the lip's inner edge clears the closest deck
# occupants -- tube-frame columns (|z| 124.7) and the nameplate (x 214.25) --
# by >= 1.0.
# LIP_W / LIP_H live in harmonic_base_spec (the drawing's side view needs the
# rim top for its silhouette pick).
RIM_INNER_R = PAD_CORNER_R - LIP_W  # 8.875: the deck pocket's plan corners

# Stamped serial number (2026-09-02, ch26 p.70 page001_img02/03): a hand-stamped
# "2" on the bright machined rim top beside the nameplate's +Z end. Cut from
# the vendored closed-region DXF (gen_base_serial_dxf.py regenerates it from
# these constants) on a plane at the rim top, SERIAL_DEPTH deep. It sits on
# the +X lip (the long-side rim the nameplate hugs), centred across LIP_W.
SERIAL_TEXT = "2"
SERIAL_HEIGHT_MM = 3.5  # p.70 macro: ~half the lip width (low)
SERIAL_DEPTH = 0.3  # a stamp, not an engraving
SERIAL_XZ = (TOP_LENGTH / 2.0 - LIP_W / 2.0, 62.0)  # (218.75, 62): lip centre, 12 past the plate end
SERIAL_MIRROR_Y = False  # flip if the seat's rim-top sketch frame reads the glyph mirrored
SERIAL_DXF = REFERENCES_DIR / "base-serial.dxf"
SERIAL_AREA_MM2 = 3.1029  # pinned from gen_base_serial_dxf's summary (net glyph area)
RIM_OVERLAP = 1.0  # the ring starts this far below the pad top so it merges

# Cone swing hardware, blind from the TOP face. MACHINE-handed part coords,
# and since #151 the drive-train derivation is machine-handed too, so the
# assembly asserts agreement DIRECTLY: pivot = cone_station(PIVOT_STATION).x
# (build_cone_pivot_screw), stop = disengaged east plate edge - shank radius
# (build_swing_stop_screw). (Pre-#151 the drive-train derived in the mirrored
# frame and these holes matched its NEGATED x -- the sign was interference-
# gate proven: holes at the wrong x left both screws in solid base, 190.0 +
# 75.4 mm^3, exactly the two embedded shank volumes.)
_FORMER_PIVOT_SCREW_XZ = (-89.16663981674521, 60.60437088764276)
PIVOT_SCREW_XZ = (
    _FORMER_PIVOT_SCREW_XZ[0] + POST_X_SHIFT,
    _FORMER_PIVOT_SCREW_XZ[1] + POST_Z_SHIFT,
)
# pivot seat: blind #10-24 UNC tap.  The screw's ground shoulder stops on
# the base top; only its distinct threaded tail enters this seat.
_FORMER_STOP_SCREW_XZ = (-141.14905420183916, -33.08089452405298)
STOP_SCREW_XZ = (
    _FORMER_STOP_SCREW_XZ[0] + POST_X_SHIFT,
    _FORMER_STOP_SCREW_XZ[1] + POST_Z_SHIFT,
)
# Past the DISENGAGED east taper edge, one O3.15 stop-shank radius outward.
# The v2-post cascade lengthened/widened the platform to 266 / east-half 24,
# which changes BOTH contributors in the drive-train derivation: the shallower
# west taper and outward lock seat shorten notch exit travel to 1.977850,
# hence disengage to 3.871203 deg, while the contact line at local z -105 has
# east half-width 17.052632.  The exact formula is reproduced by the offline
# base drawing test and guards the engaged-pose clearance.
# Disengage swing sweeps the plate EAST (machine -x); the first
# derivation sat 19 inside the engaged plate -- interference-gate proven.
# stop seat: #20 drill (O4.089, wizard) -- stop-screw O3.15 shank clearance
PIVOT_THREAD_BOTTOM_CLEARANCE = 2.0
PIVOT_HOLE_DEPTH = PIVOT_THREAD_ENGAGEMENT + PIVOT_THREAD_BOTTOM_CLEARANCE
STOP_SCREW_HOLE_DEPTH = 6.0
STOP_SCREW_DRILL_DEPTH = 9.0

# Alignment-pinion rig hold-downs (PR7 items 2/11/12), blind from the TOP face
# like the swing hardware and in the SAME machine-handed convention: four
# Ø4.2 holes under the two pivot blocks' bright slotted screws
# (build_pinion_pivot_block SCREW_* stations: block x -5.863 +/- 13.5 (2026-09
# short-strap rig, the blocks right under the drum), hole
# z = block z0 + depth/2 -- asserted directly at drive-train import) and two
# Ø3.2 holes under the black foot screws (build_foot_screw): the spring foot
# and the arbor-pedestal flange.
_FORMER_BLOCK_SCREW_XZ = (
    (-13.669764612476252, -98.0),  # front block, east screw
    (13.33023538752375, -98.0),  # front block, west screw
    (-13.669764612476252, 82.0),  # back block, east screw
    (13.33023538752375, 82.0),  # back block, west screw
)
BLOCK_SCREW_XZ = tuple(
    (x + MECHANISM_X_SHIFT, z + MECHANISM_Z_SHIFT) for x, z in _FORMER_BLOCK_SCREW_XZ
)
# block seats: #8-32 tap drill -- the slotted screws thread into the base
BLOCK_SCREW_HOLE_DEPTH = 3.5  # 22 shank - 18.75 block = 3.25 buried + 0.25 air
BLOCK_SCREW_DRILL_DEPTH = 7.0
_FORMER_FOOT_SCREW_XZ = (
    (13.179270253802283, 70.95),  # spring foot: 28 reach keeps its screw head
    # clear of the unchanged rocker-arm-support casting after the rig recenter
    (-54.7, -95.5),  # south arbor-pedestal flange (build_arbor_pedestal SCREW_Z)
    (-54.7, 102.5),  # NORTH arbor-pedestal flange (PR8, ch12 img09: the
    # mirrored base-standing clamp at z 97.5; ry180 flips its flange to +z)
)
FOOT_SCREW_XZ = tuple(
    (x + MECHANISM_X_SHIFT, z + MECHANISM_Z_SHIFT) for x, z in _FORMER_FOOT_SCREW_XZ
)
# foot seats: #4-40 tap drill -- the foot screws thread into the base
FOOT_SCREW_HOLE_DEPTH = 7.7  # 8.0 shank under the 0.8 spring strip + air
FOOT_SCREW_DRILL_DEPTH = 11.0

# Maker's nameplate seats (2026-09-02 ch26 p.71 re-derive: four brass slotted
# round-head screws hold the plate at its corners), blind from the TOP face
# like the other seats. The stations are the plate's four corner screw holes
# (nameplate_spec.SCREW_XY, plate-local) carried through the plate's mount
# transform into the machine frame -- nameplate_spec.MOUNT_HOLE_XZ, the ONE
# derivation the frame assembly's screw drops read too:
# (209.75, +/-45.5) and (163.75, +/-45.5). The plate is anchored to the pad's
# east edge, not to the mechanism, so unlike the swing/rig seats no
# MECHANISM/POST shift applies (no _FORMER_ twin). The plate lies flat on the
# deck (its back face at STACK_HEIGHT, gap 0 -- asserted below), so each
# screw axis runs -Y straight from the plate's front face into the deck.
NAMEPLATE_SCREW_XZ = nameplate_spec.MOUNT_HOLE_XZ
# nameplate seats: #4-40 tap drill -- the shared brass fillister-screw (4.0
# shank, Ø2.0 modelled minor) threads in through the 1.5 plate: 2.5 buried +
# 3.5 spare in a 6.0 thread, drill 3.0 deeper for the tap's runout (the
# STOP seat's 6.0/9.0 split).
NAMEPLATE_SCREW_HOLE_DEPTH = 6.0
NAMEPLATE_SCREW_DRILL_DEPTH = 9.0
if abs(nameplate_spec.MOUNT_BACK_Y - STACK_HEIGHT) > 1e-9:
    raise AssertionError(
        f"nameplate back face y {nameplate_spec.MOUNT_BACK_Y} is not on the deck "
        f"({STACK_HEIGHT}); its seats are cut from the deck face"
    )
if nameplate_spec.MOUNT_NORMAL != (0.0, 1.0, 0.0):
    raise AssertionError(
        f"nameplate front normal {nameplate_spec.MOUNT_NORMAL} is not the deck's +Y"
    )
# The whole plate (its four corners, both faces) must land on the deck INSIDE
# the raised rim's inner wall, or the seats would be cut through the lip.
_NAMEPLATE_CORNERS_XZ = tuple(
    (pt[0], pt[2])
    for pt in (
        nameplate_spec.mount_point((x, y, 0.0))
        for x in (0.0, nameplate_spec.PLATE_WIDTH)
        for y in (0.0, nameplate_spec.PLATE_HEIGHT)
    )
)
NAMEPLATE_RIM_CLEARANCE = min(
    min(TOP_LENGTH / 2.0 - LIP_W - abs(x), TOP_WIDTH / 2.0 - LIP_W - abs(z))
    for x, z in _NAMEPLATE_CORNERS_XZ
)
if NAMEPLATE_RIM_CLEARANCE < 1.0:
    raise AssertionError(
        f"nameplate footprint {_NAMEPLATE_CORNERS_XZ} clears the rim's inner wall by "
        f"only {NAMEPLATE_RIM_CLEARANCE:.2f} (need >= 1.0)"
    )

# The four seat specs, hoisted to module level so the drive-train assembly can
# import the TRUE wizard cut diameters for its clearance assertions (the old
# hand-authored *_HOLE_DIA constants are derived from the specs now -- one
# chokepoint, no drift).
PIVOT_SEAT_SPEC = HoleSpec(
    "tapped",
    PIVOT_THREAD,
    end="blind",
    depth_mm=PIVOT_HOLE_DEPTH,
    thread_class="2B",
)
STOP_SEAT_SPEC = HoleSpec(
    "tapped",
    "#8-32",
    end="blind",
    depth_mm=STOP_SCREW_DRILL_DEPTH,
    overrides_mm={"ThreadDepth": STOP_SCREW_HOLE_DEPTH},
)
BLOCK_SEAT_SPEC = HoleSpec(
    "tapped",
    "#8-32",
    end="blind",
    depth_mm=BLOCK_SCREW_DRILL_DEPTH,
    overrides_mm={"ThreadDepth": BLOCK_SCREW_HOLE_DEPTH},
)
FOOT_SEAT_SPEC = HoleSpec(
    "tapped",
    "#4-40",
    end="blind",
    depth_mm=FOOT_SCREW_DRILL_DEPTH,
    overrides_mm={"ThreadDepth": FOOT_SCREW_HOLE_DEPTH},
)
NAMEPLATE_SEAT_SPEC = HoleSpec(
    "tapped",
    "#4-40",
    end="blind",
    depth_mm=NAMEPLATE_SCREW_DRILL_DEPTH,
    overrides_mm={"ThreadDepth": NAMEPLATE_SCREW_HOLE_DEPTH},
)
PIVOT_SCREW_HOLE_DIA = blind_cut_dia_mm(PIVOT_SEAT_SPEC)  # 3.797 tap drill
STOP_SCREW_HOLE_DIA = blind_cut_dia_mm(STOP_SEAT_SPEC)  # #8-32 tap drill
BLOCK_SCREW_HOLE_DIA = blind_cut_dia_mm(BLOCK_SEAT_SPEC)  # #8-32 tap drill
FOOT_SCREW_HOLE_DIA = blind_cut_dia_mm(FOOT_SEAT_SPEC)  # #4-40 tap drill
NAMEPLATE_SCREW_HOLE_DIA = blind_cut_dia_mm(NAMEPLATE_SEAT_SPEC)  # #4-40 tap drill

MM3_PER_IN3 = IN**3


def _pos_drive(global_name: str, sketch_value: float) -> str:
    """Positive equation for an unsigned centre-distance dimension."""
    return f'-"{global_name}"' if sketch_value < 0.0 else f'"{global_name}"'


async def _volume(adapter) -> float:
    res = await adapter.get_mass_properties()
    return res.data.volume if res.is_success and res.data else float("nan")


def _fillet_section_area(r: float) -> float:
    """Cross-section a radius-r fillet adds to a square reentrant edge."""
    return (1.0 - math.pi / 4.0) * r * r


def _plan_perimeter(length: float, width: float, corner_r: float) -> float:
    """Outline length of a length x width rectangle with corner_r plan corners.

    A rim section swept along this outline removes (or, for a root fillet,
    adds) area x perimeter; the corner arcs are tangent to the sides, so
    there are no vertex patches to absorb.
    """
    return 2.0 * (length + width) - 8.0 * corner_r + 2.0 * math.pi * corner_r


def _corner_removal(corner_r: float, height: float) -> float:
    """Volume four plan-corner fillets of corner_r remove from a height-tall
    rectangular prism (or ADD when the corners are reentrant)."""
    return 4.0 * _fillet_section_area(corner_r) * height


async def _define_fixed_edge_rectangle(
    adapter,
    *,
    half_x: float,
    front_z: float,
    rear_z: float,
    label: str,
    dims: SketchDims,
    width_name: str,
    depth_name: str,
    width_drive: str,
    depth_drive: str,
    half_x_drive: str,
    rear_z_drive: str,
) -> None:
    """Fully define an X-centred rectangle with fixed front/rear Z edges.

    A Top-plane sketch's second coordinate is machine ``-Z``.  Anchoring the
    rear-west corner and driving the full depth keeps the plate footprint
    explicitly tied to the shared width contract.
    """
    points = [
        (-half_x, -rear_z),
        (half_x, -rear_z),
        (half_x, -front_z),
        (-half_x, -front_z),
    ]
    lines = await add_line_chain(adapter, points)
    await define_rectilinear_chain(
        adapter,
        lines,
        points,
        label=label,
        dims=dims,
        names=[width_name, depth_name, f"{width_name}West", f"{depth_name}Rear"],
        drives=[width_drive, depth_drive, half_x_drive, rear_z_drive],
    )


def _name_depth_dimension(
    adapter, feature_name: str, name: str, depth_mm: float
) -> None:
    """Rename an extrude's DEPTH display dimension to ``name`` and prove it.

    The two plate thicknesses are feature parameters (extrude depths), not
    sketch dimensions, and the drawing's keep map is keyed on the bare
    dimension name -- two features both called ``D1`` cannot be told apart
    there.  ``TopPlate`` is a ``FeatureExtrusion3`` with a start offset, so
    the depth is not guaranteed to be the FIRST display dimension; the depth
    is picked by VALUE, renamed, then read back by its new name (unique on the
    feature) and re-checked against ``depth_mm`` so a wrong pick fails the
    build loud instead of printing the offset as a thickness.
    """
    feature = _feature_by_name(adapter, feature_name)
    matches = [
        dimension
        for dimension in _display_dimensions(feature, feature_name)
        if abs(_dim_value_mm(dimension) - depth_mm) <= 1e-6
    ]
    if len(matches) != 1:
        raise RuntimeError(
            f"{feature_name}: expected exactly one {depth_mm:g} mm depth "
            f"dimension to rename to {name!r}, found {len(matches)}"
        )
    matches[0].Name = name
    _display, dimension = _named_dimension(adapter, feature_name, name)
    value = _dim_value_mm(dimension)
    if abs(value - depth_mm) > 1e-6:
        raise RuntimeError(
            f"{name}@{feature_name} reads {value:.4f} mm after the rename, "
            f"expected the {depth_mm:.4f} mm depth"
        )
    _telemetry.success(f"depth dim {name}@{feature_name} = {value:.4g} mm")


def _com_get(obj, name: str):
    """Read a zero-argument COM member that pywin32's late-bound dispatch may
    expose either as a method (``GetBox()``) or as a property value (the
    ``'tuple' object is not callable`` trap seen on IFace2.GetBox)."""
    value = getattr(obj, name)
    return value() if callable(value) else value


async def _paint_deck_black(adapter, deck_y_mm: float) -> None:
    """Face-level PANEL_BLACK on the deck the rim frames: the largest planar
    +Y face lying at ``deck_y_mm`` (the pad top inside the lip; the lip's own
    top sits LIP_H higher, the seat floors face -Y or are conical). Walks the
    body's faces instead of a coordinate pick -- ``SelectByID2`` face picks
    are view-dependent. Face appearances sit above the body colour in the
    display hierarchy, so the rest of the casting stays green."""
    from solidworks_mcp.adapters.com_variant import double_array

    doc = adapter.currentModel
    part_h = _early_bound(doc, "IPartDoc")
    bodies = part_h.GetBodies2(0, True) or []
    target = None
    target_area = 0.0
    y_m = deck_y_mm / 1000.0
    for body in bodies:
        for face in _com_get(body, "GetFaces") or []:
            normal = face.Normal
            if not normal or float(normal[1]) < 0.99:
                continue
            box = _com_get(face, "GetBox")
            if not box or abs(float(box[4]) - y_m) > 1e-6 or abs(float(box[1]) - y_m) > 1e-6:
                continue
            area = float(_com_get(face, "GetArea"))
            if area > target_area:
                target, target_area = face, area
    if target is None:
        raise RuntimeError(f"deck face at y {deck_y_mm} not found")
    a_deck = (TOP_LENGTH - 2.0 * LIP_W) * (TOP_WIDTH - 2.0 * LIP_W) * 1e-6
    if abs(target_area - a_deck) > 0.05 * a_deck:
        raise RuntimeError(
            f"deck face area {target_area * 1e6:.0f} mm^2 != {a_deck * 1e6:.0f} (minus seats)"
        )
    values = double_array([*PANEL_BLACK, 1.0, 1.0, 0.3, 0.31, 0.0, 0.0])
    target.MaterialPropertyValues = values
    back = tuple(float(v) for v in (target.MaterialPropertyValues or ())[:3])
    if len(back) != 3 or any(abs(b - w) > 1 / 255 for b, w in zip(back, PANEL_BLACK)):
        raise RuntimeError(f"deck face colour readback mismatch: {back}")
    _telemetry.info(f"deck face painted black ({target_area * 1e6:.0f} mm^2)")


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import (
        CreatePlaneParameters,
        ExtrusionParameters,
        ImportDxfDwgParameters,
    )

    check("create_part", await adapter.create_part())

    # Editable knobs (Tools > Equations): the two plate footprints + thicknesses.
    # The mm suffix is load-bearing -- this is an INCH document and the equation
    # manager reads BARE numbers in document units (an unsuffixed 457.2 = 457
    # inches and blows the part up 25.4x). The thicknesses are extrude/offset
    # feature parameters (not sketch dims), exposed here as editable constants
    # even though nothing in drive_jobs drives them.
    await set_global(adapter, "BottomLength", f"{BOTTOM_LENGTH}mm")
    await set_global(adapter, "BottomWidth", f"{BOTTOM_WIDTH}mm")
    await set_global(adapter, "BottomThickness", f"{BOTTOM_THICKNESS}mm")
    await set_global(adapter, "TopLength", f"{TOP_LENGTH}mm")
    await set_global(adapter, "TopWidth", f"{TOP_WIDTH}mm")
    await set_global(adapter, "TopThickness", f"{TOP_THICKNESS}mm")
    for i, (x, z) in enumerate(HOLE_XZ):
        await set_global(adapter, f"Hole{i}X", f"{x}mm")
        await set_global(adapter, f"Hole{i}Z", f"{-z}mm")

    # Each sketch DECLARES its dim names + drive equations inline; a per-sketch
    # SketchDims records each dim in the helper's emission order. Drive equations
    # are collected here and applied in one deferred batch at the end (every
    # target must resolve against the finished model).
    drive_jobs: list[tuple[str, str]] = []

    # Bottom plate: centred on the origin.
    bottom = SketchDims()
    check("create_sketch bottom", await adapter.create_sketch("Top"))
    await _define_fixed_edge_rectangle(
        adapter,
        half_x=BOTTOM_LENGTH / 2.0,
        front_z=-BOTTOM_WIDTH / 2.0,
        rear_z=BOTTOM_WIDTH / 2.0,
        label="bottom plate",
        dims=bottom,
        width_name="BottomLen",
        depth_name="BottomWid",
        width_drive='"BottomLength"',
        depth_drive='"BottomWidth"',
        half_x_drive='"BottomLength" / 2',
        rear_z_drive='"BottomWidth" / 2',
    )
    await ensure_fully_defined(adapter, "bottom plate sketch")
    check("exit_sketch bottom", await adapter.exit_sketch())
    name_last_feature(adapter, "BottomProfile")
    drive_jobs += bottom.apply(adapter, "BottomProfile")
    check(
        "extrude bottom",
        await adapter.create_extrusion(ExtrusionParameters(depth=BOTTOM_THICKNESS)),
    )
    name_last_feature(adapter, "BottomPlate")
    # The flange thickness is the print's marked FlangeT (harmonic_base_spec
    # DRAWING_DIMENSIONS), shown on the front elevation.
    _name_depth_dimension(adapter, "BottomPlate", "FlangeT", BOTTOM_THICKNESS)
    _telemetry.info(f"volume after bottom plate: {await _volume(adapter):.1f} mm^3")
    # Top plate shares the centred legacy footprint and starts on the flange.
    top = SketchDims()
    check("create_sketch top", await adapter.create_sketch("Top"))
    await _define_fixed_edge_rectangle(
        adapter,
        half_x=TOP_LENGTH / 2.0,
        front_z=-TOP_WIDTH / 2.0,
        rear_z=TOP_WIDTH / 2.0,
        label="top plate",
        dims=top,
        width_name="TopLen",
        depth_name="TopWid",
        width_drive='"TopLength"',
        depth_drive='"TopWidth"',
        half_x_drive='"TopLength" / 2',
        rear_z_drive='"TopWidth" / 2',
    )
    await ensure_fully_defined(adapter, "top plate sketch")
    check("exit_sketch top", await adapter.exit_sketch())
    name_last_feature(adapter, "TopProfile")
    drive_jobs += top.apply(adapter, "TopProfile")
    extrude_at_offset(adapter, TOP_THICKNESS, BOTTOM_THICKNESS)
    name_last_feature(adapter, "TopPlate")
    # The pad thickness is the print's marked PadT: the offset extrude carries
    # both the depth and the 12.7 start offset, so the depth is found by value.
    _name_depth_dimension(adapter, "TopPlate", "PadT", TOP_THICKNESS)
    _telemetry.info(f"volume after top plate: {await _volume(adapter):.1f} mm^3")

    # M6.10 fastener holes + lag-head recesses: ONE native Hole Wizard
    # counterbored 9/16 FILLISTER feature (4 placement points) drilled from
    # the UNDERSIDE face, so the model carries the real fastener designation
    # (memory/fastener-policy-us-customary; fillister = the round slotted head
    # -- the hex-bolt table SKIPS 9/16, and the lag screw's round Ø22 head IS
    # a fillister shape). The through Ø13 / recess Ø23x6.5 are the
    # PHOTO-MEASURED artefact dims -- the standard table would cut Ø14.7/Ø21.4
    # and visibly move the underside -- preserved as explicit definition
    # overrides. CBORE_XZ == HOLE_XZ (all four heads recessed), so the pair of
    # concentric cuts collapses into the one counterbore feature.
    total = BOTTOM_THICKNESS + TOP_THICKNESS
    pre_holes = await _volume(adapter)
    fastener_cut = wizard_holes(
        adapter,
        HoleSpec(
            "counterbore_fillister",
            "9/16",
            overrides_mm={
                "HoleDiameter": HOLE_DIA,
                "CounterBoreDiameter": CBORE_DIA,
                "CounterBoreDepth": CBORE_DEPTH,
            },
        ),
        [[x, 0.0, z] for x, z in HOLE_XZ],
        (0.0, -1.0, 0.0),
        "lag-screw counterbored holes (9/16)",
        name="FastenerHoles",
        placement_dims=[
            (
                (f"Hole{i}Cx", _pos_drive(f"Hole{i}X", x)),
                (f"Hole{i}Cz", _pos_drive(f"Hole{i}Z", -z)),
            )
            for i, (x, z) in enumerate(HOLE_XZ)
        ],
    )
    drive_jobs += fastener_cut.placement_drive_jobs
    after = await _volume(adapter)
    v_holes = len(HOLE_XZ) * (
        math.pi * (HOLE_DIA / 2.0) ** 2 * total
        + math.pi * ((CBORE_DIA / 2.0) ** 2 - (HOLE_DIA / 2.0) ** 2) * CBORE_DEPTH
    )
    _telemetry.info(
        f"volume after fastener holes: {after:.1f} mm^3 (removed analytic {v_holes:.1f})"
    )
    if abs((pre_holes - after) - v_holes) > 0.02 * v_holes:
        raise RuntimeError(
            f"fastener holes removed {pre_holes - after:.1f}, expected {v_holes:.1f}"
        )

    # Cone swing hardware + alignment-pinion rig seats + nameplate seats: native
    # Hole Wizard blind holes from the top face. The pivot, stop, block, foot
    # and nameplate screws all thread into their matching tapped base seats; the
    # platform itself swings on the pivot screw's shoulder. A wizard blind hole
    # ends in a 118-degree drill point, so the analytic expectation is
    # blind_hole_volume_mm3 (cylinder + point). The nameplate seats are cut
    # from the same deck face the plate lies on (NAMEPLATE_SCREW_XZ derivation
    # above) -- before the rim, which would otherwise be the +Y face at the
    # pad outline and confuse the face walk.
    for tag, spec, xz, label in (
        (
            "PivotSeat",
            PIVOT_SEAT_SPEC,
            (PIVOT_SCREW_XZ,),
            f"cone-pivot screw tapped seat ({PIVOT_THREAD} UNC)",
        ),
        (
            "StopSeat",
            STOP_SEAT_SPEC,
            (STOP_SCREW_XZ,),
            "swing-stop tapped seat (#8-32)",
        ),
        (
            "BlockScrewHoles",
            BLOCK_SEAT_SPEC,
            BLOCK_SCREW_XZ,
            "pinion-pivot-block tapped seats (#8-32)",
        ),
        (
            "FootScrewHoles",
            FOOT_SEAT_SPEC,
            FOOT_SCREW_XZ,
            "foot-screw tapped seats (#4-40)",
        ),
        (
            "NameplateSeats",
            NAMEPLATE_SEAT_SPEC,
            NAMEPLATE_SCREW_XZ,
            "nameplate fillister-screw tapped seats (#4-40)",
        ),
    ):
        dia = blind_cut_dia_mm(spec)
        wizard_holes(
            adapter,
            spec,
            [[sx, total, sz] for sx, sz in xz],
            (0.0, 1.0, 0.0),
            label,
            name=tag,
        )
        after_cut = await _volume(adapter)
        v_cut = len(xz) * blind_hole_volume_mm3(dia, spec.depth_mm)
        if abs((after - after_cut) - v_cut) > 0.02 * v_cut:
            raise RuntimeError(
                f"{tag} removed {after - after_cut:.1f}, expected {v_cut:.1f}"
            )
        after = after_cut

    # Raised rim FIRST (2026-09 photo re-derive, see LIP_W): one ring feature
    # -- outer rectangle on the pad's plan outline, inner rectangle LIP_W in --
    # boss-extruded from RIM_OVERLAP below the pad top to LIP_H above it, so
    # it merges into the pad and its outer faces continue the pad sides. Net
    # material: the ring over LIP_H. Top-plane sketch: (x, y) -> (X, -Z).
    half_x, half_z = TOP_LENGTH / 2.0, TOP_WIDTH / 2.0
    outer_pts = [
        (-half_x, -half_z), (half_x, -half_z), (half_x, half_z), (-half_x, half_z),
    ]
    inner_pts = [
        (-half_x + LIP_W, -half_z + LIP_W), (half_x - LIP_W, -half_z + LIP_W),
        (half_x - LIP_W, half_z - LIP_W), (-half_x + LIP_W, half_z - LIP_W),
    ]
    check("create_sketch rim", await adapter.create_sketch("Top"))
    outer_lines = await add_line_chain(adapter, outer_pts)
    inner_lines = await add_line_chain(adapter, inner_pts)
    await define_rectilinear_chain(adapter, outer_lines, outer_pts, label="rim outer")
    await define_rectilinear_chain(adapter, inner_lines, inner_pts, label="rim inner")
    await ensure_fully_defined(adapter, "rim sketch")
    check("exit_sketch rim", await adapter.exit_sketch())
    name_last_feature(adapter, "RimProfile")
    extrude_at_offset(adapter, RIM_OVERLAP + LIP_H, total - RIM_OVERLAP)
    name_last_feature(adapter, "Rim")
    a_ring = TOP_LENGTH * TOP_WIDTH - (TOP_LENGTH - 2.0 * LIP_W) * (TOP_WIDTH - 2.0 * LIP_W)
    v_lip = a_ring * LIP_H
    after = await volume_check(adapter, "raised rim", after + v_lip, 0.01 * v_lip + 5.0)
    deck_top = total + LIP_H

    # Plan corners: one full-height radius per plate. The pad + rim FIRST (one
    # merged side face, so one edge from the flange top to the rim top) at
    # PAD_CORNER_R, then the flange's four vertical corner edges at the
    # concentric FLANGE_CORNER_R -- in that order: the flange arc passes 0.19
    # inside the pad's square corner, so filleting the flange while the pad
    # corner is still square has to cut the pad and SolidWorks refuses
    # ("Failed to create fillet", seat build); rounded first, the pad corner
    # sits 6.35 inside the flange arc. Then the rim's four reentrant inner
    # corners at RIM_INNER_R so the lip stays LIP_W wide round the corner.
    check(
        "fillet pad plan corners",
        await adapter.add_fillet(
            PAD_CORNER_R,
            [
                [sx * TOP_LENGTH / 2.0, (BOTTOM_THICKNESS + deck_top) / 2.0, sz * TOP_WIDTH / 2.0]
                for sx in (-1.0, 1.0)
                for sz in (-1.0, 1.0)
            ],
        ),
    )
    name_last_feature(adapter, "PadCorners")
    v_pad_corners = _corner_removal(PAD_CORNER_R, deck_top - BOTTOM_THICKNESS)
    after = await volume_check(
        adapter, "pad plan corners", after - v_pad_corners, 0.01 * v_pad_corners + 2.0
    )
    check(
        "fillet flange plan corners",
        await adapter.add_fillet(
            FLANGE_CORNER_R,
            [
                [sx * BOTTOM_LENGTH / 2.0, BOTTOM_THICKNESS / 2.0, sz * BOTTOM_WIDTH / 2.0]
                for sx in (-1.0, 1.0)
                for sz in (-1.0, 1.0)
            ],
        ),
    )
    name_last_feature(adapter, "FlangeCorners")
    v_flange_corners = _corner_removal(FLANGE_CORNER_R, BOTTOM_THICKNESS)
    after = await volume_check(
        adapter, "flange plan corners", after - v_flange_corners, 0.01 * v_flange_corners + 2.0
    )
    check(
        "fillet rim inner corners",
        await adapter.add_fillet(
            RIM_INNER_R,
            [
                [
                    sx * (TOP_LENGTH / 2.0 - LIP_W),
                    total + LIP_H / 2.0,
                    sz * (TOP_WIDTH / 2.0 - LIP_W),
                ]
                for sx in (-1.0, 1.0)
                for sz in (-1.0, 1.0)
            ],
        ),
    )
    name_last_feature(adapter, "RimInnerCorners")
    v_rim_corners = _corner_removal(RIM_INNER_R, LIP_H)  # reentrant: ADDS
    after = await volume_check(
        adapter, "rim inner corners", after + v_rim_corners, 0.05 * v_rim_corners + 2.0
    )

    def _rim_points(
        half_x: float, y_rim: float, half_z: float, corner_r: float
    ) -> list[list[float]]:
        """One rim loop: four side-edge midpoints + four corner-arc midpoints."""
        arc_x = half_x - corner_r + corner_r / math.sqrt(2.0)
        arc_z = half_z - corner_r + corner_r / math.sqrt(2.0)
        return [
            [0.0, y_rim, -half_z],
            [0.0, y_rim, half_z],
            [half_x, y_rim, 0.0],
            [-half_x, y_rim, 0.0],
        ] + [
            [sx * arc_x, y_rim, sz * arc_z]
            for sx in (-1.0, 1.0)
            for sz in (-1.0, 1.0)
        ]

    # Top rims: 1/16 in x 45-degree breaks on the flange's reveal rim and the
    # raised rim's top outer perimeter.
    check(
        "chamfer top rims",
        await adapter.add_chamfer(
            RIM_CHAMFER,
            _rim_points(BOTTOM_LENGTH / 2.0, BOTTOM_THICKNESS, BOTTOM_WIDTH / 2.0, FLANGE_CORNER_R)
            + _rim_points(TOP_LENGTH / 2.0, deck_top, TOP_WIDTH / 2.0, PAD_CORNER_R),
        ),
    )
    name_last_feature(adapter, "TopRimBreaks")
    rim_area = RIM_CHAMFER**2 / 2.0
    v_rims = rim_area * (
        _plan_perimeter(BOTTOM_LENGTH, BOTTOM_WIDTH, FLANGE_CORNER_R)
        + _plan_perimeter(TOP_LENGTH, TOP_WIDTH, PAD_CORNER_R)
    )
    after = await volume_check(
        adapter, "top rim breaks", after - v_rims, 0.02 * v_rims + 5.0
    )

    # Underside rim: the same 1/16 in break around the bottom face perimeter.
    check(
        "chamfer underside rim",
        await adapter.add_chamfer(
            RIM_CHAMFER,
            _rim_points(BOTTOM_LENGTH / 2.0, 0.0, BOTTOM_WIDTH / 2.0, FLANGE_CORNER_R),
        ),
    )
    name_last_feature(adapter, "BottomEdgeBreak")
    v_break = rim_area * _plan_perimeter(BOTTOM_LENGTH, BOTTOM_WIDTH, FLANGE_CORNER_R)
    after = await volume_check(
        adapter, "underside edge break", after - v_break, 0.02 * v_break + 5.0
    )

    # Pad root: the one INTERNAL wall junction -- the pad sides meeting the
    # flange top face -- filleted at the R0.50 note 1 caps (the cutter-corner
    # radius that machining the reveal leaves anyway). Reentrant: ADDS
    # material along the pad's rounded base outline.
    check(
        "fillet pad root",
        await adapter.add_fillet(
            PAD_ROOT_R,
            _rim_points(TOP_LENGTH / 2.0, BOTTOM_THICKNESS, TOP_WIDTH / 2.0, PAD_CORNER_R),
        ),
    )
    name_last_feature(adapter, "PadRootFillet")
    v_root = _fillet_section_area(PAD_ROOT_R) * _plan_perimeter(
        TOP_LENGTH, TOP_WIDTH, PAD_CORNER_R
    )
    after = await volume_check(
        adapter, "pad root fillet", after + v_root, 0.05 * v_root + 3.0
    )

    # Stamped serial "2" on the rim top: import the closed-region DXF onto a
    # plane at the rim top (STACK_HEIGHT + LIP_H) and cut it mid-plane both ways
    # (the up side cuts air), removing net-area x SERIAL_DEPTH -- bounded like
    # the nameplate engraving (no closed form for the traced glyph).
    if not SERIAL_DXF.is_file():
        raise RuntimeError(f"serial DXF not found: {SERIAL_DXF}")
    serial_plane = check(
        "create_plane rim top",
        await adapter.create_plane(
            CreatePlaneParameters(mode="offset", base_plane="Top Plane", offset=STACK_HEIGHT + LIP_H)
        ),
    )
    pre_serial = float((await adapter.get_mass_properties()).data.volume)
    check(
        "import serial DXF",
        await adapter.import_dxf_dwg(
            ImportDxfDwgParameters(
                file_path=str(SERIAL_DXF),
                plane=getattr(serial_plane, "name", serial_plane),
                scale=1.0,
                position=[0.0, 0.0],
                merge_points=True,
            )
        ),
    )
    name_last_feature(adapter, "SerialSketch")
    check(
        "cut serial",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=2.0 * SERIAL_DEPTH, both_directions=True)
        ),
    )
    name_last_feature(adapter, "Serial")
    removed = pre_serial - float((await adapter.get_mass_properties()).data.volume)
    v_serial = SERIAL_AREA_MM2 * SERIAL_DEPTH
    _telemetry.info(f"serial stamp removed {removed:.3f} mm^3 (DXF net area {SERIAL_AREA_MM2} x {SERIAL_DEPTH} = {v_serial:.3f})")
    if not 0.75 * v_serial <= removed <= 1.25 * v_serial:
        raise RuntimeError(f"serial stamp removed {removed:.3f} mm^3, expected ~{v_serial:.3f}")
    after -= removed

    # Apply the deferred drive equations after the whole model exists, then
    # re-check neutrality against the as-built volume. Frame components are
    # inserted at verified transforms and lock-mated, so the old DeckTop,
    # CboreSeat, and eight per-hole construction planes/axes are unnecessary.
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(adapter, "driven base (equations neutral)", after, 0.005 * after)

    await apply_material(adapter, MATERIAL)
    await apply_color(adapter, CASTING_GREEN)
    await _paint_deck_black(adapter, total)

    # Verify the annotated footprint without view-dependent screen picks.
    await bbox_extent_check(
        adapter, "base length (annotated 46 cm / 18 in)", "x", BOTTOM_LENGTH
    )
    await bbox_extent_check(adapter, "base depth (28 cm plate)", "z", BOTTOM_WIDTH)

    await report_mass_properties(adapter)
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    apply_drawing_properties(
        adapter,
        PART_NAME,
        {
            "Manufacturing Notes": DRAWING_NOTES,
            "Side View Note": SIDE_VIEW_NOTE,
        },
    )
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
