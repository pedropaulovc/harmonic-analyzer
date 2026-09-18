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
    _early_bound,
    add_line_chain,
    anchor_point_to_origin,
    apply_color,
    apply_material,
    bbox_extent_check,
    check,
    define_circle,
    define_rectilinear_chain,
    dimension_between,
    drive_dimension,
    ensure_fully_defined,
    extrude_at_offset,
    force_rebuild,
    name_last_feature,
    name_dimensions,
    REFERENCES_DIR,
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
    set_dimension_bilateral_tolerance,
)
from _holes import (
    DRILL_POINT_H,
    THREAD_MAJOR_MM,
    TAP_DRILL_MM,
    HoleSpec,
    blind_cut_dia_mm,
    blind_hole_volume_mm3,
    wizard_holes,
)
from _part_pmi import _resolve_faces, author_part_pmi
from harmonic_base_spec import (
    BOTTOM_LENGTH,
    BOTTOM_THICKNESS,
    BOTTOM_WIDTH,
    COLUMN_SOCKET_XZ,
    COLUMN_X,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION,
    LIP_H,
    LIP_W,
    DRAWING_NOTES,
    PART_SURFACE_FINISHES,
    SOCKET_BORE_FINISHES,
    SPOTFACE_DEPTH_BAND_MM,
    STACK_HEIGHT,
    TOP_LENGTH,
    TOP_THICKNESS,
    TOP_WIDTH,
)
import nameplate_spec
from cone_pivot_post_installation import (
    FRAME_FRONT_COLUMN_Z,
    MECHANISM_X_SHIFT,
    MECHANISM_Z_SHIFT,
    POST_X_SHIFT,
    POST_Z_SHIFT,
)
from build_cone_pivot_screw import (
    THREAD as PIVOT_THREAD,
    THREAD_TAIL_LEN as PIVOT_THREAD_ENGAGEMENT,
)
from build_cone_lock_knob import (
    COLLAR_DIA as LOCK_COLLAR_DIA,
    PLUG_TAP_LEAD as LOCK_PLUG_TAP_LEAD,
    STUD_BOTTOM_CLEARANCE as LOCK_STUD_BOTTOM_CLEARANCE,
    STUD_LEN as LOCK_STUD_LEN,
    THREAD as LOCK_THREAD,
)
from build_cone_swing_platform import PLATE_T, swing_hardware_geometry
from build_swing_stop_screw import (
    SHANK_DIA as STOP_SHANK_DIA,
    THREAD as STOP_THREAD,
)
from build_slotted_screw import SHANK_LEN as BLOCK_SCREW_LEN
from build_foot_screw import SHANK_LEN as FOOT_SCREW_LEN
from build_fillister_screw import SHANK_LEN as NAMEPLATE_SCREW_LEN
from build_swing_stop_screw import EMBED_LEN as STOP_ENGAGEMENT
from build_lag_screw import (
    BEARING_OFFSET as HOLD_DOWN_BEARING_OFFSET,
    SHANK_LEN as HOLD_DOWN_SCREW_LEN,
)
from pinion_pivot_block_spec import BLOCK_HEIGHT
from pinion_spring_geometry import THICK as SPRING_THICKNESS
from arbor_pedestal_spec import FOOT_HEIGHT as PEDESTAL_FLANGE_THICKNESS
from build_rocker_arm_support import FOOT_THICKNESS as SUPPORT_FOOT_THICKNESS
from rocker_arm_support_spec import SUPPORT_HOLD_DOWN_XZ
from frame_attachment_spec import (
    BASE_SCREW_SEAT_Z,
    BASE_SCREW_Y,
    CASTING_FULL_THREAD_DEPTH,
    CASTING_TAP_DRILL_DEPTH,
    COLUMN_SOCKET_DEPTH,
    COLUMN_SOCKET_DIAMETER,
    SCREW_SPOTFACE_DIAMETER,
)
from _visibility import blank_reference_geometry

import _telemetry


def _as_construction(adapter, entity_id: str) -> None:
    """Flag a registered sketch line as construction geometry.

    ``ConstructionGeometry`` is declared on the base ISketchSegment, not the
    derived ISketchLine the entity registry binds -- rebind before the set.
    """
    segment = _early_bound(adapter._sketch_entities[entity_id], "ISketchSegment")
    segment.ConstructionGeometry = True
    if not bool(segment.ConstructionGeometry):
        raise RuntimeError(f"{entity_id} did not take the construction flag")


def _verify_named_dimension(adapter, full_name: str, expected_mm: float) -> None:
    """Prove a renamed dimension is the one the recipe meant.

    ``name_dimensions`` renames by CREATION ORDER, so any feature that emits
    more than one display dimension can hand the name to the wrong value in
    silence -- an offset-start boss extrude emits its depth AND its start
    offset, and the two differ by twenty times here. Cheap to check, and the
    failure it catches would otherwise surface as a wrong number on a sheet.
    """
    raw = adapter.currentModel.Parameter(full_name)
    if raw is None:
        raise RuntimeError(f"no dimension named {full_name}")
    actual_mm = float(_early_bound(raw, "IDimension").SystemValue) * 1000.0
    if abs(actual_mm - expected_mm) > 1e-6:
        raise RuntimeError(
            f"{full_name} measures {actual_mm:g} mm, expected {expected_mm:g} mm"
        )


PART_NAME = "harmonic-base"
MATERIAL = "Gray Cast Iron"  # see _common.apply_material docstring

# Plate nominal geometry (BOTTOM_*/TOP_*) lives in harmonic_base_spec -- the
# COM-free contract the drawing shares. DIMENSIONS.md ch6: 46 cm / 28 cm callouts
# = 18.1 x 11.0 in (annotated); the length keeps the legacy 18.0 in and the
# thicknesses come from the legacy HarmonicBase.cs (photo-verify M2 note). The
# DEPTH deliberately no longer follows the 28 cm callout: harmonic_base_spec
# widens the pad to 274.5 (slab 287.2, same 0.25 in reveal per side) so the
# socket-to-rim deck land is equal on both axes -- asserted below, because
# only this module knows the column stations.
IN = 25.4

# The four column sockets, their stations and their bore surface finishes now
# live in harmonic_base_spec: the sheet may only source a surface-finish
# control from a part SPEC, and the bore size reaches that spec through the
# leaf module frame_column_stations. Bore diameters remain nominal CAD
# geometry -- match-fit production sockets to their assigned actual MHA-083
# tubes, not to a fixed diameter band.
BASE_SPOTFACE_PLANE_Z = TOP_WIDTH / 2.0
BASE_SPOTFACE_DEPTH = BASE_SPOTFACE_PLANE_Z - BASE_SCREW_SEAT_Z
BASE_CROSS_TAP_SPEC = HoleSpec(
    "tapped_bottoming",
    "#10-32",
    end="blind",
    depth_mm=CASTING_TAP_DRILL_DEPTH,
    thread_class="2B",
    overrides_mm={"ThreadDepth": CASTING_FULL_THREAD_DEPTH},
)
BASE_CROSS_TAP_DRILL_DIA = TAP_DRILL_MM[BASE_CROSS_TAP_SPEC.size]
BASE_SCREW_FACES = (("front", -1.0, True), ("rear", 1.0, False))
if BASE_SPOTFACE_DEPTH <= 0.0:
    raise AssertionError("base cross-screw spotface must cut inward from the side")
if CASTING_TAP_DRILL_DEPTH - CASTING_FULL_THREAD_DEPTH < 2.0 * 25.4 / 32.0:
    raise AssertionError("base cross tap lacks two-pitch bottoming-tap lead")

# Rocker-support hold-down seats (machine = part-local: frame.SLDASM places the
# base unrotated at the origin). The support contract transforms its unchanged
# four-hole foot pattern through the +90-degree installation and the v2 rear
# shift. Base, support, and frame therefore cannot carry drifting copies.
#
# The selected 1/4-20 x 5/8 screw bears on the bottom of its vendor-modeled
# 0.277813 mm under-head washer transition. That physical bearing face crosses
# the 6.35 mm support foot and leaves 9.247187 mm (1.456D) of engagement in
# this base. Usable full thread extends 0.25 mm beyond the screw tip so it
# cannot bottom before the head seats. A machine plug tap then needs four lead
# threads plus one pitch of margin: cylindrical tap-drill depth = full-thread
# depth + 5P = 15.847187 mm. Keep all three lengths explicit; they are
# different assembly/manufacturing constraints.
HOLD_DOWN_THREAD = "1/4-20"
HOLD_DOWN_THREAD_CLASS = "2B"
HOLD_DOWN_PITCH = IN / 20.0
HOLD_DOWN_ENGAGEMENT = (
    HOLD_DOWN_SCREW_LEN - SUPPORT_FOOT_THICKNESS - HOLD_DOWN_BEARING_OFFSET
)
HOLD_DOWN_TIP_CLEARANCE = 0.25
HOLD_DOWN_THREAD_DEPTH = HOLD_DOWN_ENGAGEMENT + HOLD_DOWN_TIP_CLEARANCE
HOLD_DOWN_DRILL_DEPTH = HOLD_DOWN_THREAD_DEPTH + 5.0 * HOLD_DOWN_PITCH
HOLD_DOWN_SEAT_SPEC = HoleSpec(
    "tapped",
    HOLD_DOWN_THREAD,
    end="blind",
    depth_mm=HOLD_DOWN_DRILL_DEPTH,
    thread_class=HOLD_DOWN_THREAD_CLASS,
    overrides_mm={"ThreadDepth": HOLD_DOWN_THREAD_DEPTH},
)
HOLD_DOWN_TAP_DRILL_DIA = blind_cut_dia_mm(HOLD_DOWN_SEAT_SPEC)
HOLE_XZ = SUPPORT_HOLD_DOWN_XZ

# Edge finishing (chamfer external, fillet internal; legacy 1/8-1/16 sizes).
# The machined plate gets 45-degree edge breaks on every external edge: the
# vertical plan corners at 1/8 in legs, the exposed top rims and the
# underside rim at 1/16 in (single-pass mill/file breaks). The one internal
# wall junction -- the pad side walls meeting the flange top face -- carries a
# 0.5 root fillet, which is NOT a print requirement: a 0.5 mm internal root
# cannot be measured with hobby-shop kit (it needs an optical comparator or a
# radius gauge under magnification), so the sheet carries no radius callout
# and the deck cutter's own corner defines it (2026-09 review). Every
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
PAD_ROOT_R = 0.5  # pad-to-flange root fillet; modelled, never called out

# Raised rim + black deck (2026-09 photo re-derive). Every plate that shows
# the base top -- ch11 p.21 (crank close-up), ch13 p.25 (cylinder-gear front),
# ch30 p002/p003/p006 -- reads it as a BLACK panel framed by a green lip
# standing a few mm proud of it, flush with the pad sides. The lip is a
# LIP_H-tall ring LIP_W wide on the pad's chamfered outline; the deck it
# frames stays at the pad top (STACK_HEIGHT), so nothing mounted on the base
# moves. The deck face is painted PANEL_BLACK at the FACE level (part and
# body stay casting green); the lip's inner edge clears the closest deck
# occupants by >= 1.0 -- the tube-frame column sockets (wall at |z| 124.75,
# now 5.5 clear after the pad widening) and the nameplate's plate corner
# (x 214.25, 1.0 clear, the binding case).
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
SERIAL_XZ = (
    TOP_LENGTH / 2.0 - LIP_W / 2.0,
    62.0,
)  # (218.75, 62): lip centre, 12 past the plate end
SERIAL_MIRROR_Y = (
    False  # flip if the seat's rim-top sketch frame reads the glyph mirrored
)
SERIAL_DXF = REFERENCES_DIR / "base-serial.dxf"
SERIAL_AREA_MM2 = 3.1029  # pinned from gen_base_serial_dxf's summary (net glyph area)

# Cone swing hardware, blind from the TOP face. MACHINE-handed part coords.
# The platform recipe owns the shared lock/stop contact calculation; the base
# supplies its installed pivot station and exact purchased-hardware diameters.
_FORMER_PIVOT_SCREW_XZ = (-89.16663981674521, 60.60437088764276)
PIVOT_SCREW_XZ = (
    _FORMER_PIVOT_SCREW_XZ[0] + POST_X_SHIFT,
    _FORMER_PIVOT_SCREW_XZ[1] + POST_Z_SHIFT,
)
SWING_HARDWARE_GEOMETRY = swing_hardware_geometry(
    PIVOT_SCREW_XZ,
    lock_collar_dia=LOCK_COLLAR_DIA,
    stop_shank_dia=STOP_SHANK_DIA,
)
LOCK_KNOB_XZ = SWING_HARDWARE_GEOMETRY.lock_xz
STOP_SCREW_XZ = SWING_HARDWARE_GEOMETRY.stop_xz

# Blind #10-24 UNC-2B bottoming tap: only the 9.525-mm threaded tail enters.
# Full threads extend 0.25 past the tip; the 12-mm cylindrical drill leaves
# 2.225 mm for the bottoming tap's two-pitch lead before the drill point.
PIVOT_THREAD_BOTTOM_CLEARANCE = 0.25
PIVOT_SCREW_HOLE_DEPTH = PIVOT_THREAD_ENGAGEMENT + PIVOT_THREAD_BOTTOM_CLEARANCE
PIVOT_SCREW_DRILL_DEPTH = 12.0

# The 19.05-mm stock stud enters 12.70 through the platform, or its full
# length when the collar fences the disengaged notch on the bare base.
# Full threads clear that deepest pose by 0.25; a five-pitch plug-tap lead
# fits below them, before the separate 118-degree drill point.
LOCK_STUD_ENGAGEMENT = LOCK_STUD_LEN - PLATE_T
LOCK_SCREW_HOLE_DEPTH = LOCK_STUD_LEN + LOCK_STUD_BOTTOM_CLEARANCE
LOCK_SCREW_DRILL_DEPTH = LOCK_SCREW_HOLE_DEPTH + LOCK_PLUG_TAP_LEAD

# The shared 25.4-mm stock stop keeps its original 9.875-mm exposed height.
# A 16-mm full thread clears the 15.525-mm embed; 4 mm below it accommodates
# the #8-32 plug tap's five-pitch lead (3.96875), before the drill point.
STOP_SCREW_HOLE_DEPTH = 16.0
STOP_SCREW_DRILL_DEPTH = 20.0

# Alignment-pinion rig hold-downs, blind from the TOP face in the same
# machine-handed convention: four #8-32 seats under the two pivot blocks
# (2026-09 short-strap rig, the blocks right under the drum) and three #4-40
# seats under the spring foot and both arbor-pedestal flanges.
_FORMER_BLOCK_SCREW_XZ = (
    (-13.669764612476252, -98.0),  # front block, east screw
    (13.33023538752375, -98.0),  # front block, west screw
    (-13.669764612476252, 82.0),  # back block, east screw
    (13.33023538752375, 82.0),  # back block, west screw
)
BLOCK_SCREW_XZ = tuple(
    (x + MECHANISM_X_SHIFT, z + MECHANISM_Z_SHIFT) for x, z in _FORMER_BLOCK_SCREW_XZ
)
# Stock 25.4-mm slotted screws penetrate 6.65 mm below each 18.75-mm block.
BLOCK_SCREW_HOLE_DEPTH = 6.9  # stock engagement + 0.25 tip reserve
BLOCK_SCREW_DRILL_DEPTH = 10.0
# Bottoming tap: 3.1 mm runout exceeds two #8-32 pitches (1.5875 mm).
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
# The stock 9.525-mm foot screw penetrates 8.725 mm below the 0.8-mm spring.
FOOT_SCREW_HOLE_DEPTH = 8.975  # stock engagement + 0.25 tip reserve
FOOT_SCREW_DRILL_DEPTH = 11.0
# Bottoming tap: 2.025 mm runout exceeds two #4-40 pitches (1.27 mm).

# Maker's nameplate seats (2026-09-02 ch26 p.71 re-derive: four brass slotted
# fillister-head screws hold the plate at its corners), blind from the TOP face
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
# The stock brass fillister's 6.35-mm shank passes through the 1.5-mm plate,
# engaging 4.85 mm of the existing 6.0-mm #4-40 thread. The drill extends
# 3.0 mm deeper for the bottoming tap's two-pitch lead (1.27 mm).
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

# Native tapped seats. Physical thread compatibility is carried by each named
# HoleSpec designation; tap-drill diameters remain manufacturing geometry and
# are not compared to purchased fasteners' major-diameter solids.
PIVOT_SEAT_SPEC = HoleSpec(
    "tapped_bottoming",
    PIVOT_THREAD,
    end="blind",
    depth_mm=PIVOT_SCREW_DRILL_DEPTH,
    thread_class="2B",
    overrides_mm={"ThreadDepth": PIVOT_SCREW_HOLE_DEPTH},
)
LOCK_SEAT_SPEC = HoleSpec(
    "tapped",
    LOCK_THREAD,
    end="blind",
    depth_mm=LOCK_SCREW_DRILL_DEPTH,
    thread_class="2B",
    overrides_mm={"ThreadDepth": LOCK_SCREW_HOLE_DEPTH},
)
STOP_SEAT_SPEC = HoleSpec(
    "tapped",
    STOP_THREAD,
    end="blind",
    depth_mm=STOP_SCREW_DRILL_DEPTH,
    thread_class="2B",
    overrides_mm={"ThreadDepth": STOP_SCREW_HOLE_DEPTH},
)
BLOCK_SEAT_SPEC = HoleSpec(
    "tapped_bottoming",
    "#8-32",
    end="blind",
    depth_mm=BLOCK_SCREW_DRILL_DEPTH,
    thread_class="2B",
    overrides_mm={"ThreadDepth": BLOCK_SCREW_HOLE_DEPTH},
)
FOOT_SEAT_SPEC = HoleSpec(
    "tapped_bottoming",
    "#4-40",
    end="blind",
    depth_mm=FOOT_SCREW_DRILL_DEPTH,
    thread_class="2B",
    overrides_mm={"ThreadDepth": FOOT_SCREW_HOLE_DEPTH},
)
NAMEPLATE_SEAT_SPEC = HoleSpec(
    "tapped_bottoming",
    "#4-40",
    end="blind",
    depth_mm=NAMEPLATE_SCREW_DRILL_DEPTH,
    thread_class="2B",
    overrides_mm={"ThreadDepth": NAMEPLATE_SCREW_HOLE_DEPTH},
)
PIVOT_SCREW_HOLE_DIA = blind_cut_dia_mm(PIVOT_SEAT_SPEC)
LOCK_SCREW_HOLE_DIA = blind_cut_dia_mm(LOCK_SEAT_SPEC)
STOP_SCREW_HOLE_DIA = blind_cut_dia_mm(STOP_SEAT_SPEC)
BLOCK_SCREW_HOLE_DIA = blind_cut_dia_mm(BLOCK_SEAT_SPEC)
FOOT_SCREW_HOLE_DIA = blind_cut_dia_mm(FOOT_SEAT_SPEC)
NAMEPLATE_SCREW_HOLE_DIA = blind_cut_dia_mm(NAMEPLATE_SEAT_SPEC)

# Socket cylinders occupy Y=25.4..50.8, overlapping the deepest vertical-seat
# envelopes. Check plan walls against every known base cavity, not just the
# visually nearest nameplate holes.
COLUMN_SOCKET_NEAREST_OCCUPANT_WALL = min(
    math.dist(socket, occupant) - (COLUMN_SOCKET_DIAMETER + occupant_dia) / 2.0
    for socket in COLUMN_SOCKET_XZ
    for occupants, occupant_dia in (
        (HOLE_XZ, THREAD_MAJOR_MM[HOLD_DOWN_THREAD]),
        ((PIVOT_SCREW_XZ,), PIVOT_SCREW_HOLE_DIA),
        ((LOCK_KNOB_XZ,), LOCK_SCREW_HOLE_DIA),
        ((STOP_SCREW_XZ,), STOP_SCREW_HOLE_DIA),
        (BLOCK_SCREW_XZ, BLOCK_SCREW_HOLE_DIA),
        (FOOT_SCREW_XZ, FOOT_SCREW_HOLE_DIA),
        (NAMEPLATE_SCREW_XZ, NAMEPLATE_SCREW_HOLE_DIA),
    )
    for occupant in occupants
)
if COLUMN_SOCKET_NEAREST_OCCUPANT_WALL < 1.0:
    raise AssertionError(
        "base column socket leaves less than 1 mm wall to another base cavity"
    )
# Nominal model-space sanity only: this does not validate manufactured
# tolerance combinations. DRAWING_NOTES governs finished-part land acceptance.
# TOP_WIDTH is sized so this land is EQUAL on both axes: the 2026-09 blind
# machinist review rejected the former 10.5 in pad, whose 1.6 mm land in Z
# could not survive the coordinate stack behind the 1.0 MIN finished-land
# note while every table dimension stayed in tolerance.
COLUMN_SOCKET_LAND_X = min(
    TOP_LENGTH / 2.0 - LIP_W - abs(x) - COLUMN_SOCKET_DIAMETER / 2.0
    for x, _z in COLUMN_SOCKET_XZ
)
COLUMN_SOCKET_LAND_Z = min(
    TOP_WIDTH / 2.0 - LIP_W - abs(z) - COLUMN_SOCKET_DIAMETER / 2.0
    for _x, z in COLUMN_SOCKET_XZ
)
COLUMN_SOCKET_RIM_CLEARANCE = min(COLUMN_SOCKET_LAND_X, COLUMN_SOCKET_LAND_Z)
if abs(COLUMN_SOCKET_LAND_X - COLUMN_SOCKET_LAND_Z) > 1e-9:
    raise AssertionError(
        "base deck land is not equal on both axes: "
        f"x={COLUMN_SOCKET_LAND_X}, z={COLUMN_SOCKET_LAND_Z}"
    )
if COLUMN_SOCKET_RIM_CLEARANCE < 1.0:
    raise AssertionError("base column socket crowds the raised rim")


def require_blind_seat_fit(
    label: str, seat: HoleSpec, engagement: float, *, tip_reserve: float = 0.25
) -> None:
    """Keep a stock screw in full threads above a manufacturable tap lead."""
    if seat.kind not in ("tapped", "tapped_bottoming") or seat.end != "blind":
        raise AssertionError(f"{label}: base seat must be a native blind tap")
    thread_depth = seat.overrides_mm.get("ThreadDepth", seat.depth_mm)
    if not math.isfinite(tip_reserve) or tip_reserve <= 0.0:
        raise AssertionError(f"{label}: tip reserve must be finite and positive")
    if not all(
        math.isfinite(value) and value > 0.0
        for value in (engagement, thread_depth, seat.depth_mm)
    ):
        raise AssertionError(
            f"{label}: engagement and depths must be finite and positive"
        )
    if engagement < THREAD_MAJOR_MM[seat.size]:
        raise AssertionError(
            f"{label}: less than one diameter of full-thread engagement"
        )
    if thread_depth - engagement < tip_reserve - 1e-9:
        raise AssertionError(f"{label}: screw bottoms before seating in full threads")
    pitch = 25.4 / float(seat.size.rsplit("-", 1)[1])
    lead_pitches = 2.0 if seat.kind == "tapped_bottoming" else 5.0
    if seat.depth_mm - thread_depth < lead_pitches * pitch - 1e-9:
        tap = "bottoming" if seat.kind == "tapped_bottoming" else "plug"
        raise AssertionError(
            f"{label}: drill lacks {lead_pitches:g}-pitch {tap}-tap lead"
        )


# Guard the deepest installed stock insertion in all seven native seat groups.
# The foot group also serves the thicker pedestal flange, with less insertion.
for _label, _seat, _engagement in (
    ("rocker support", HOLD_DOWN_SEAT_SPEC, HOLD_DOWN_ENGAGEMENT),
    ("cone pivot", PIVOT_SEAT_SPEC, PIVOT_THREAD_ENGAGEMENT),
    ("cone lock", LOCK_SEAT_SPEC, LOCK_STUD_LEN),
    ("swing stop", STOP_SEAT_SPEC, STOP_ENGAGEMENT),
    ("pinion block", BLOCK_SEAT_SPEC, BLOCK_SCREW_LEN - BLOCK_HEIGHT),
    ("spring foot", FOOT_SEAT_SPEC, FOOT_SCREW_LEN - SPRING_THICKNESS),
    ("pedestal foot", FOOT_SEAT_SPEC, FOOT_SCREW_LEN - PEDESTAL_FLANGE_THICKNESS),
    (
        "nameplate",
        NAMEPLATE_SEAT_SPEC,
        NAMEPLATE_SCREW_LEN - nameplate_spec.PLATE_THICKNESS,
    ),
):
    require_blind_seat_fit(_label, _seat, _engagement)

# Include each blind drill's deeper cylindrical cut and separate 118-degree
# point in the upper-pad wall checks. Full-height cavity envelopes
# conservatively bound every neighboring bore, irrespective of start face.
PIVOT_DRILL_BOTTOM_WALL = (
    TOP_THICKNESS
    - PIVOT_SEAT_SPEC.depth_mm
    - PIVOT_SCREW_HOLE_DIA / 2.0 * DRILL_POINT_H
)
if PIVOT_DRILL_BOTTOM_WALL < 1.5 * PIVOT_SCREW_HOLE_DIA:
    raise AssertionError(
        "cone-pivot drill leaves less than 1.5 diameters of upper-pad wall"
    )
PIVOT_NEAREST_CAVITY_WALL = min(
    math.dist(PIVOT_SCREW_XZ, xz) - (PIVOT_SCREW_HOLE_DIA + dia) / 2.0
    for points, dia in (
        (HOLE_XZ, THREAD_MAJOR_MM[HOLD_DOWN_THREAD]),
        ((LOCK_KNOB_XZ,), LOCK_SCREW_HOLE_DIA),
        ((STOP_SCREW_XZ,), STOP_SCREW_HOLE_DIA),
        (BLOCK_SCREW_XZ, BLOCK_SCREW_HOLE_DIA),
        (FOOT_SCREW_XZ, FOOT_SCREW_HOLE_DIA),
        (NAMEPLATE_SCREW_XZ, NAMEPLATE_SCREW_HOLE_DIA),
    )
    for xz in points
)
if PIVOT_NEAREST_CAVITY_WALL < PIVOT_SCREW_HOLE_DIA:
    raise AssertionError("cone-pivot drill crowds another base cavity")

# The deeper lock drill must remain in the solid upper pad and clear every
# other vertical cavity. Bounding the hold-down thread-major envelopes over
# their full height catches wall breakout rather than only tap-drill overlap.
LOCK_DRILL_BOTTOM_WALL = (
    TOP_THICKNESS - LOCK_SCREW_DRILL_DEPTH - LOCK_SCREW_HOLE_DIA / 2.0 * DRILL_POINT_H
)
if LOCK_DRILL_BOTTOM_WALL < 1.5 * LOCK_SCREW_HOLE_DIA:
    raise AssertionError(
        "cone-lock drill leaves less than 1.5 diameters of upper-pad wall"
    )
LOCK_NEAREST_CAVITY_WALL = min(
    math.dist(LOCK_KNOB_XZ, xz) - (LOCK_SCREW_HOLE_DIA + dia) / 2.0
    for points, dia in (
        (HOLE_XZ, THREAD_MAJOR_MM[HOLD_DOWN_THREAD]),
        ((PIVOT_SCREW_XZ,), PIVOT_SCREW_HOLE_DIA),
        ((STOP_SCREW_XZ,), STOP_SCREW_HOLE_DIA),
        (BLOCK_SCREW_XZ, BLOCK_SCREW_HOLE_DIA),
        (FOOT_SCREW_XZ, FOOT_SCREW_HOLE_DIA),
        (NAMEPLATE_SCREW_XZ, NAMEPLATE_SCREW_HOLE_DIA),
    )
    for xz in points
)
if LOCK_NEAREST_CAVITY_WALL < LOCK_SCREW_HOLE_DIA:
    raise AssertionError("cone-lock drill crowds another base cavity")

STOP_DRILL_BOTTOM_WALL = (
    TOP_THICKNESS - STOP_SCREW_DRILL_DEPTH - STOP_SCREW_HOLE_DIA / 2.0 * DRILL_POINT_H
)
if STOP_DRILL_BOTTOM_WALL < 1.5 * STOP_SCREW_HOLE_DIA:
    raise AssertionError(
        "swing-stop drill leaves less than 1.5 diameters of upper-pad wall"
    )
STOP_NEAREST_CAVITY_WALL = min(
    math.dist(STOP_SCREW_XZ, xz) - (STOP_SCREW_HOLE_DIA + dia) / 2.0
    for points, dia in (
        (HOLE_XZ, THREAD_MAJOR_MM[HOLD_DOWN_THREAD]),
        ((PIVOT_SCREW_XZ,), PIVOT_SCREW_HOLE_DIA),
        ((LOCK_KNOB_XZ,), LOCK_SCREW_HOLE_DIA),
        (BLOCK_SCREW_XZ, BLOCK_SCREW_HOLE_DIA),
        (FOOT_SCREW_XZ, FOOT_SCREW_HOLE_DIA),
        (NAMEPLATE_SCREW_XZ, NAMEPLATE_SCREW_HOLE_DIA),
    )
    for xz in points
)
if STOP_NEAREST_CAVITY_WALL < STOP_SCREW_HOLE_DIA:
    raise AssertionError("swing-stop drill crowds another base cavity")

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


def _interrupted_cross_hole_removal(
    hole_dia: float, cylindrical_depth: float, socket_dia: float
) -> float:
    """Volume cut from casting by a blind cross hole interrupted by a socket."""
    hole_r = hole_dia / 2.0
    socket_r = socket_dia / 2.0
    step = 0.001
    volume = 0.0
    x = -hole_r
    while x < hole_r:
        dx = x + step / 2.0
        hole_chord = 2.0 * math.sqrt(max(0.0, hole_r * hole_r - dx * dx))
        socket_span = 2.0 * math.sqrt(max(0.0, socket_r * socket_r - dx * dx))
        volume += hole_chord * (cylindrical_depth - socket_span) * step
        x += step
    # The 118-degree point lies wholly in the far casting wall.
    volume += math.pi / 3.0 * hole_r**3 * DRILL_POINT_H
    return volume


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


def _com_get(obj, name: str):
    """Read a zero-argument COM member that pywin32's late-bound dispatch may
    expose either as a method (``GetBox()``) or as a property value (the
    ``'tuple' object is not callable`` trap seen on IFace2.GetBox)."""
    value = getattr(obj, name)
    return value() if callable(value) else value


# Only these two qualified planes are blacked by the registry Finish field; the
# flange perimeter faces carry the same seat grade but keep the body colour.
BLACK_FINISH_KEYS = ("deck", "underside")


async def _paint_machined_faces_black(adapter) -> None:
    """Qualify every spec-owned finish face, then black the two painted planes.

    Every control's face is area-checked, so the native part proves the face
    selection for the four flange perimeter sides as well -- a plane picked at
    the wrong offset (the top plate's side instead of the flange's) fails here
    rather than shipping a roughness symbol on the wrong surface.
    """
    from solidworks_mcp.adapters.com_variant import double_array

    faces = _resolve_faces(
        adapter.currentModel,
        {control.key: control.face for control in PART_SURFACE_FINISHES},
    )
    # The flange sides are bounded by the four corner arcs and the two 1/16 in
    # rim breaks, so neither dimension is the raw plate envelope.
    flange_side_height = BOTTOM_THICKNESS - 2.0 * RIM_CHAMFER
    flange_end_width = BOTTOM_WIDTH - 2.0 * FLANGE_CORNER_R
    flange_face_width = BOTTOM_LENGTH - 2.0 * FLANGE_CORNER_R
    expected_areas = {
        "deck": (TOP_LENGTH - 2.0 * LIP_W) * (TOP_WIDTH - 2.0 * LIP_W) * 1e-6,
        "underside": BOTTOM_LENGTH * BOTTOM_WIDTH * 1e-6,
        "flange_west": flange_end_width * flange_side_height * 1e-6,
        "flange_east": flange_end_width * flange_side_height * 1e-6,
        "flange_rear": flange_face_width * flange_side_height * 1e-6,
        "flange_front": flange_face_width * flange_side_height * 1e-6,
    }
    # Each socket bore wall loses two small windows where the cross tap passes
    # through it (~1.3% of the cylinder), well inside the 5% band below.
    expected_areas.update(
        {
            control.key: math.pi
            * COLUMN_SOCKET_DIAMETER
            * COLUMN_SOCKET_DEPTH
            * 1e-6
            for control in SOCKET_BORE_FINISHES
        }
    )
    values = double_array([*PANEL_BLACK, 1.0, 1.0, 0.3, 0.31, 0.0, 0.0])
    for key, face in faces.items():
        area = float(face.GetArea())
        expected = expected_areas[key]
        if abs(area - expected) > 0.05 * expected:
            raise RuntimeError(
                f"{key} face area {area * 1e6:.0f} mm^2 != "
                f"{expected * 1e6:.0f} (minus openings/edge breaks)"
            )
        if key not in BLACK_FINISH_KEYS:
            _telemetry.info(f"{key} face qualified ({area * 1e6:.0f} mm^2), body colour")
            continue
        face.MaterialPropertyValues = values
        back = tuple(float(value) for value in (face.MaterialPropertyValues or ())[:3])
        if len(back) != 3 or any(
            abs(actual - wanted) > 1 / 255 for actual, wanted in zip(back, PANEL_BLACK)
        ):
            raise RuntimeError(f"{key} black face colour did not persist: {back}")
        _telemetry.info(f"{key} face painted black ({area * 1e6:.0f} mm^2)")


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
    # feature parameters (not sketch dims); they are named after the features
    # are created, then driven in the deferred batch below.
    await set_global(adapter, "BottomLength", f"{BOTTOM_LENGTH}mm")
    await set_global(adapter, "BottomWidth", f"{BOTTOM_WIDTH}mm")
    await set_global(adapter, "BottomThickness", f"{BOTTOM_THICKNESS}mm")
    await set_global(adapter, "TopLength", f"{TOP_LENGTH}mm")
    await set_global(adapter, "TopWidth", f"{TOP_WIDTH}mm")
    await set_global(adapter, "TopThickness", f"{TOP_THICKNESS}mm")
    await set_global(adapter, "ColumnX", f"{COLUMN_X}mm")
    await set_global(adapter, "ColumnZ", f"{abs(FRAME_FRONT_COLUMN_Z)}mm")
    await set_global(adapter, "SocketDia", f"{COLUMN_SOCKET_DIAMETER}mm")
    await set_global(adapter, "SocketDepth", f"{COLUMN_SOCKET_DEPTH}mm")
    await set_global(adapter, "BaseScrewY", f"{BASE_SCREW_Y}mm")
    await set_global(adapter, "SpotFaceDia", f"{SCREW_SPOTFACE_DIAMETER}mm")
    await set_global(adapter, "SpotFaceDepth", f"{BASE_SPOTFACE_DEPTH}mm")
    for i, (x, z) in enumerate(HOLE_XZ):
        await set_global(adapter, f"Hole{i}X", f"{x}mm")
        await set_global(adapter, f"Hole{i}Z", f"{-z}mm")

    # Each sketch DECLARES its dim names + drive equations inline; a per-sketch
    # SketchDims records each dim in the helper's emission order. Drive equations
    # are collected here and applied in one deferred batch at the end (every
    # target must resolve against the finished model).
    drive_jobs: list[tuple[str, str]] = []
    ref_planes: list[str] = []

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
    bottom_thickness_dim = name_dimensions(adapter, "BottomPlate", ["BottomThickness"])
    drive_jobs.append((bottom_thickness_dim[0], '"BottomThickness"'))
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
    top_thickness_dim = name_dimensions(adapter, "TopPlate", ["TopThickness"])
    drive_jobs.append((top_thickness_dim[0], '"TopThickness"'))
    _telemetry.info(f"volume after top plate: {await _volume(adapter):.1f} mm^3")
    total = STACK_HEIGHT

    # Four blind native 1/4-20 UNC-2B seats from the support deck. The screws
    # bear on their vendor-modeled under-head washer faces and pass through
    # the support's 5/16 clearance drills: 6.35 mm foot + 9.247187 mm (1.456D)
    # engagement, with 0.25 mm thread beyond each tip. The separate 15.847187 mm
    # cylindrical drill depth leaves five pitches for plug-tap lead and margin.
    pre_holes = await _volume(adapter)
    fastener_cut = wizard_holes(
        adapter,
        HOLD_DOWN_SEAT_SPEC,
        [[x, STACK_HEIGHT, z] for x, z in HOLE_XZ],
        (0.0, 1.0, 0.0),
        "rocker-support blind tapped seats (1/4-20 UNC-2B)",
        name="SupportHoldDownSeats",
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
    v_holes = len(HOLE_XZ) * blind_hole_volume_mm3(
        HOLD_DOWN_TAP_DRILL_DIA, HOLD_DOWN_DRILL_DEPTH
    )
    _telemetry.info(
        f"volume after support seats: {after:.1f} mm^3 (removed analytic {v_holes:.1f})"
    )
    if abs((pre_holes - after) - v_holes) > 0.02 * v_holes:
        raise RuntimeError(
            f"support seats removed {pre_holes - after:.1f}, expected {v_holes:.1f}"
        )

    # Cone swing hardware + alignment-pinion rig seats + nameplate seats:
    # native Hole Wizard blind holes from the top face. The pivot, lock,
    # stop, block, foot, and nameplate screws thread into their named tapped
    # seats; the platform swings on the pivot screw's shoulder. A blind wizard
    # hole ends in a 118-degree drill point, so the analytic expectation
    # includes cylinder plus point. The nameplate seats are cut from the same
    # deck face the plate lies on (NAMEPLATE_SCREW_XZ derivation above), before
    # the rim would become the +Y face at the pad outline and confuse the
    # face walk.
    for tag, spec, xz, label in (
        (
            "PivotSeat",
            PIVOT_SEAT_SPEC,
            (PIVOT_SCREW_XZ,),
            f"cone-pivot screw bottoming-tapped seat ({PIVOT_THREAD} UNC-2B)",
        ),
        (
            "LockSeat",
            LOCK_SEAT_SPEC,
            (LOCK_KNOB_XZ,),
            f"cone-lock knob tapped seat ({LOCK_THREAD} UNC-2B)",
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
            "pinion-pivot-block bottoming-tapped seats (#8-32)",
        ),
        (
            "FootScrewHoles",
            FOOT_SEAT_SPEC,
            FOOT_SCREW_XZ,
            "foot-screw bottoming-tapped seats (#4-40)",
        ),
        (
            "NameplateSeats",
            NAMEPLATE_SEAT_SPEC,
            NAMEPLATE_SCREW_XZ,
            "nameplate fillister-screw bottoming-tapped seats (#4-40)",
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

    # Four blind column sockets from the deck. Their Ø25.50 +0.05/0 limits
    # match MHA-083's Ø25.40 +0/-0.05 OD for 0.10..0.20 diametral clearance.
    socket_plane = check(
        "create_plane column socket mouths",
        await adapter.create_plane(
            CreatePlaneParameters(
                mode="offset", base_plane="Top Plane", offset=STACK_HEIGHT
            )
        ),
    )
    socket_plane_name = str(getattr(socket_plane, "name", socket_plane))
    ref_planes.append(socket_plane_name)
    sockets = SketchDims()
    check(
        "create_sketch column sockets", await adapter.create_sketch(socket_plane_name)
    )
    for i, (x, z) in enumerate(COLUMN_SOCKET_XZ):
        await define_circle(
            adapter,
            x,
            -z,
            COLUMN_SOCKET_DIAMETER / 2.0,
            f"column socket ({x:+.0f}, {z:+.0f})",
            dims=sockets,
            names=(
                f"Socket{i}X",
                f"Socket{i}Z",
                "SocketDia" if i == 0 else f"Socket{i}Dia",
            ),
            drives=(
                '"ColumnX"',
                '"ColumnZ"',
                '"SocketDia"',
            ),
        )
    await ensure_fully_defined(adapter, "column socket sketch")
    check("exit_sketch column sockets", await adapter.exit_sketch())
    name_last_feature(adapter, "ColumnSocketProfile")
    drive_jobs += sockets.apply(adapter, "ColumnSocketProfile")
    check(
        "cut blind column sockets",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=COLUMN_SOCKET_DEPTH, reverse_direction=False)
        ),
    )
    name_last_feature(adapter, "ColumnSockets")
    socket_depth_dim = name_dimensions(adapter, "ColumnSockets", ["SocketDepth"])
    drive_jobs.append((socket_depth_dim[0], '"SocketDepth"'))
    v_sockets = (
        len(COLUMN_SOCKET_XZ)
        * math.pi
        * (COLUMN_SOCKET_DIAMETER / 2.0) ** 2
        * COLUMN_SOCKET_DEPTH
    )
    after = await volume_check(
        adapter, "column sockets", after - v_sockets, 0.005 * v_sockets + 10.0
    )

    # Ø9 spot seats on the front/rear pad faces, then bottoming-tapped paths
    # continue through the near casting, interrupted socket, and far casting.
    v_spot = math.pi * (SCREW_SPOTFACE_DIAMETER / 2.0) ** 2 * BASE_SPOTFACE_DEPTH
    for side, sign, reverse in BASE_SCREW_FACES:
        spot_plane = check(
            f"create_plane base spotface {side}",
            await adapter.create_plane(
                CreatePlaneParameters(
                    mode="offset",
                    base_plane="Front Plane",
                    offset=sign * BASE_SPOTFACE_PLANE_Z,
                )
            ),
        )
        spot_plane_name = str(getattr(spot_plane, "name", spot_plane))
        ref_planes.append(spot_plane_name)
        spot = SketchDims()
        check(
            f"create_sketch base spotface {side}",
            await adapter.create_sketch(spot_plane_name),
        )
        for i, x in enumerate((-COLUMN_X, COLUMN_X)):
            await define_circle(
                adapter,
                x,
                BASE_SCREW_Y,
                SCREW_SPOTFACE_DIAMETER / 2.0,
                f"base spotface {side} ({x:+.0f})",
                dims=spot,
                names=(
                    f"Spot{i}X",
                    f"Spot{i}Y",
                    "SpotFaceDia" if i == 0 else f"Spot{i}Dia",
                ),
                drives=(
                    '"ColumnX"',
                    '"BaseScrewY"',
                    '"SpotFaceDia"',
                ),
            )
        await ensure_fully_defined(adapter, f"base spotface {side} sketch")
        check(f"exit_sketch base spotface {side}", await adapter.exit_sketch())
        profile_name = f"BaseSpotFace{side.capitalize()}Profile"
        name_last_feature(adapter, profile_name)
        drive_jobs += spot.apply(adapter, profile_name)
        check(
            f"cut base spotface {side}",
            await adapter.create_cut_extrude(
                ExtrusionParameters(
                    depth=BASE_SPOTFACE_DEPTH, reverse_direction=reverse
                )
            ),
        )
        feature_name = f"BaseSpotFace{side.capitalize()}"
        name_last_feature(adapter, feature_name)
        spot_depth_dim = name_dimensions(adapter, feature_name, ["SpotFaceDepth"])
        drive_jobs.append((spot_depth_dim[0], '"SpotFaceDepth"'))
        after = await volume_check(
            adapter,
            f"base spotfaces {side}",
            after - 2.0 * v_spot,
            0.01 * v_spot + 2.0,
        )

        z_face = sign * BASE_SCREW_SEAT_Z
        tap_points = [[x, BASE_SCREW_Y, z_face] for x in (-COLUMN_X, COLUMN_X)]
        wizard_holes(
            adapter,
            BASE_CROSS_TAP_SPEC,
            tap_points,
            (0.0, 0.0, sign),
            f"base frame cross taps {side}",
            name=f"BaseCrossTaps{side.capitalize()}",
            expect_dia_mm=BASE_CROSS_TAP_DRILL_DIA,
        )
        v_cross = _interrupted_cross_hole_removal(
            BASE_CROSS_TAP_DRILL_DIA,
            CASTING_TAP_DRILL_DEPTH,
            COLUMN_SOCKET_DIAMETER,
        )
        after = await volume_check(
            adapter,
            f"base cross taps {side}",
            after - 2.0 * v_cross,
            0.015 * v_cross + 3.0,
        )

    # Raised rim FIRST (2026-09 photo re-derive, see LIP_W): one ring feature
    # -- outer rectangle on the pad's plan outline, inner rectangle LIP_W in --
    # boss-extruded from the pad's top face, so it merges into the pad and its
    # outer faces continue the pad sides. The extrude starts ON that face (it
    # used to start 1.0 below it) because its depth dimension IS the rim step
    # the drawing prints: policy rule 2 puts the printed nominal in the model,
    # and a depth carrying a merge allowance is not the value the shop holds.
    # Same solid either way -- the allowance lay inside existing material.
    # Net material: the ring over LIP_H. Top-plane sketch: (x, y) -> (X, -Z).
    half_x, half_z = TOP_LENGTH / 2.0, TOP_WIDTH / 2.0
    outer_pts = [
        (-half_x, -half_z),
        (half_x, -half_z),
        (half_x, half_z),
        (-half_x, half_z),
    ]
    inner_pts = [
        (-half_x + LIP_W, -half_z + LIP_W),
        (half_x - LIP_W, -half_z + LIP_W),
        (half_x - LIP_W, half_z - LIP_W),
        (-half_x + LIP_W, half_z - LIP_W),
    ]
    check("create_sketch rim", await adapter.create_sketch("Top"))
    outer_lines = await add_line_chain(adapter, outer_pts)
    inner_lines = await add_line_chain(adapter, inner_pts)
    await define_rectilinear_chain(adapter, outer_lines, outer_pts, label="rim outer")
    await define_rectilinear_chain(adapter, inner_lines, inner_pts, label="rim inner")
    await ensure_fully_defined(adapter, "rim sketch")
    check("exit_sketch rim", await adapter.exit_sketch())
    name_last_feature(adapter, "RimProfile")
    extrude_at_offset(adapter, LIP_H, total)
    name_last_feature(adapter, "Rim")
    name_dimensions(adapter, "Rim", ["RimHeight"])
    _verify_named_dimension(adapter, "RimHeight@Rim", LIP_H)
    a_ring = TOP_LENGTH * TOP_WIDTH - (TOP_LENGTH - 2.0 * LIP_W) * (
        TOP_WIDTH - 2.0 * LIP_W
    )
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
                [
                    sx * TOP_LENGTH / 2.0,
                    (BOTTOM_THICKNESS + deck_top) / 2.0,
                    sz * TOP_WIDTH / 2.0,
                ]
                for sx in (-1.0, 1.0)
                for sz in (-1.0, 1.0)
            ],
        ),
    )
    name_last_feature(adapter, "PadCorners")
    name_dimensions(adapter, "PadCorners", ["PadCornerRadius"])
    v_pad_corners = _corner_removal(PAD_CORNER_R, deck_top - BOTTOM_THICKNESS)
    after = await volume_check(
        adapter, "pad plan corners", after - v_pad_corners, 0.01 * v_pad_corners + 2.0
    )
    check(
        "fillet flange plan corners",
        await adapter.add_fillet(
            FLANGE_CORNER_R,
            [
                [
                    sx * BOTTOM_LENGTH / 2.0,
                    BOTTOM_THICKNESS / 2.0,
                    sz * BOTTOM_WIDTH / 2.0,
                ]
                for sx in (-1.0, 1.0)
                for sz in (-1.0, 1.0)
            ],
        ),
    )
    name_last_feature(adapter, "FlangeCorners")
    name_dimensions(adapter, "FlangeCorners", ["FlangeCornerRadius"])
    v_flange_corners = _corner_removal(FLANGE_CORNER_R, BOTTOM_THICKNESS)
    after = await volume_check(
        adapter,
        "flange plan corners",
        after - v_flange_corners,
        0.01 * v_flange_corners + 2.0,
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
    name_dimensions(adapter, "RimInnerCorners", ["RimInnerCornerRadius"])
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
            [sx * arc_x, y_rim, sz * arc_z] for sx in (-1.0, 1.0) for sz in (-1.0, 1.0)
        ]

    # Top rims: 1/16 in x 45-degree breaks on the flange's reveal rim and the
    # raised rim's top outer perimeter.
    check(
        "chamfer top rims",
        await adapter.add_chamfer(
            RIM_CHAMFER,
            _rim_points(
                BOTTOM_LENGTH / 2.0,
                BOTTOM_THICKNESS,
                BOTTOM_WIDTH / 2.0,
                FLANGE_CORNER_R,
            )
            + _rim_points(TOP_LENGTH / 2.0, deck_top, TOP_WIDTH / 2.0, PAD_CORNER_R),
        ),
    )
    name_last_feature(adapter, "TopRimBreaks")
    name_dimensions(adapter, "TopRimBreaks", ["TopRimChamfer"])
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
    name_dimensions(adapter, "BottomEdgeBreak", ["BottomEdgeChamfer"])
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
            _rim_points(
                TOP_LENGTH / 2.0, BOTTOM_THICKNESS, TOP_WIDTH / 2.0, PAD_CORNER_R
            ),
        ),
    )
    name_last_feature(adapter, "PadRootFillet")
    name_dimensions(adapter, "PadRootFillet", ["PadRootRadius"])
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
            CreatePlaneParameters(
                mode="offset", base_plane="Top Plane", offset=STACK_HEIGHT + LIP_H
            )
        ),
    )
    ref_planes.append(str(getattr(serial_plane, "name", serial_plane)))
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
    _telemetry.info(
        f"serial stamp removed {removed:.3f} mm^3 (DXF net area {SERIAL_AREA_MM2} x {SERIAL_DEPTH} = {v_serial:.3f})"
    )
    if not 0.75 * v_serial <= removed <= 1.25 * v_serial:
        raise RuntimeError(
            f"serial stamp removed {removed:.3f} mm^3, expected ~{v_serial:.3f}"
        )
    after -= removed

    # Apply the deferred drive equations after the whole model exists, then
    # re-check neutrality against the as-built volume.
    await force_rebuild(adapter)
    for dim_name, expr in drive_jobs:
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    await volume_check(adapter, "driven base (equations neutral)", after, 0.005 * after)

    # Two REFERENCE sketches. The rim width and the flange-to-rim height are
    # manufacturing values the sheet prints, so policy rule 2 says the model
    # owns them -- but neither is any feature's dimension: the rim ring's
    # width is the gap between two loops of one profile, and the 40.6 spans
    # three features. Each therefore gets a hidden one-line sketch whose
    # single driving dimension IS the value, marked for drawing like any
    # other. Construction, not hidden: a BLANKED sketch's dimensions never reach
    # InsertModelAnnotations3 (first build failed with "geometry top view is
    # missing model dimensions: ['RimWidth']"), while construction geometry
    # imports normally and is never drawn in a view.
    check("create_sketch rim-width reference", await adapter.create_sketch("Top"))
    # Direct-to-DB for the geometry: this line lies ON the sketch X axis and
    # runs horizontally, so creation-time inference would snap in exactly the
    # relations the explicit ones below add and leave the sketch OVER-defined.
    set_sketch_direct_db(adapter, True)
    rim_ref = check(
        "rim width reference line",
        await adapter.add_line(TOP_LENGTH / 2.0, 0.0, TOP_LENGTH / 2.0 - LIP_W, 0.0),
    )
    set_sketch_direct_db(adapter, False)
    _as_construction(adapter, rim_ref)
    check(
        "rim width reference horizontal",
        await adapter.add_sketch_constraint(rim_ref, None, "horizontal"),
    )
    await dimension_between(
        adapter,
        f"{rim_ref}.start",
        f"{rim_ref}.end",
        "horizontal_distance",
        LIP_W,
        "rim width reference",
    )
    await anchor_point_to_origin(
        adapter, f"{rim_ref}.start", TOP_LENGTH / 2.0, 0.0, "rim width reference"
    )
    await ensure_fully_defined(adapter, "rim width reference sketch")
    check("exit_sketch rim-width reference", await adapter.exit_sketch())
    name_last_feature(adapter, "RimWidthReference")
    name_dimensions(adapter, "RimWidthReference", ["RimWidth"])
    _verify_named_dimension(adapter, "RimWidth@RimWidthReference", LIP_W)

    # On the left silhouette (x = -BOTTOM_LENGTH/2), where the front view's
    # flange-to-rim dimension has always drawn its witness lines.
    check("create_sketch height reference", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    height_ref = check(
        "flange-to-rim reference line",
        await adapter.add_line(
            -BOTTOM_LENGTH / 2.0, BOTTOM_THICKNESS, -BOTTOM_LENGTH / 2.0, deck_top
        ),
    )
    set_sketch_direct_db(adapter, False)
    _as_construction(adapter, height_ref)
    check(
        "flange-to-rim reference vertical",
        await adapter.add_sketch_constraint(height_ref, None, "vertical"),
    )
    await dimension_between(
        adapter,
        f"{height_ref}.start",
        f"{height_ref}.end",
        "vertical_distance",
        deck_top - BOTTOM_THICKNESS,
        "flange-to-rim reference",
    )
    await anchor_point_to_origin(
        adapter,
        f"{height_ref}.start",
        -BOTTOM_LENGTH / 2.0,
        BOTTOM_THICKNESS,
        "flange-to-rim reference",
    )
    await ensure_fully_defined(adapter, "flange-to-rim reference sketch")
    check("exit_sketch height reference", await adapter.exit_sketch())
    name_last_feature(adapter, "HeightReference")
    name_dimensions(adapter, "HeightReference", ["FlangeToRim"])
    _verify_named_dimension(
        adapter, "FlangeToRim@HeightReference", deck_top - BOTTOM_THICKNESS
    )
    blank_reference_geometry(adapter, tuple((name, "PLANE") for name in ref_planes))
    await apply_material(adapter, MATERIAL)
    await apply_color(adapter, CASTING_GREEN)
    await _paint_machined_faces_black(adapter)

    # Verify the annotated footprint without view-dependent screen picks.
    await bbox_extent_check(
        adapter, "base length (annotated 46 cm / 18 in)", "x", BOTTOM_LENGTH
    )
    await bbox_extent_check(adapter, "base depth (widened pad slab)", "z", BOTTOM_WIDTH)

    await report_mass_properties(adapter)
    clear_dimensions_for_drawing(adapter)
    for feature_name, dimension_names in DRAWING_DIMENSIONS.items():
        mark_dimensions_for_drawing(adapter, feature_name, dimension_names)
    # Decimal places are the tolerance statement, so they are authored HERE
    # and the drawing only reads them back (policy rule 2). Same for the one
    # dimension whose band is not the title block's: a spotface may run deep,
    # never shallow, or the screw head rocks on an unfaced ring.
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    set_dimension_bilateral_tolerance(
        adapter, "BaseSpotFaceRear", "SpotFaceDepth", *SPOTFACE_DEPTH_BAND_MM
    )
    author_part_pmi(adapter, surface_finishes=PART_SURFACE_FINISHES)
    apply_drawing_properties(
        adapter,
        PART_NAME,
        {
            "Manufacturing Notes": DRAWING_NOTES,
        },
    )
    return await save_part_and_images(adapter, PART_NAME)


if __name__ == "__main__":
    sys.exit(run_build(build))
