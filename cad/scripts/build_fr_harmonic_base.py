r"""Reproduction script: harmonic analyzer base (book ch. 6 / legacy part).

Two-plate welded construction based on the legacy 18.0 x 11.0 x 0.5 in
flange and 17.5 x 10.5 x 1.5 in pad. The v2 post/carrier fit preserves their
both plates remain on the legacy centred footprint; the v2 post/carrier fit is
handled by the mechanism installation contracts.

Top-face seats: the cone-swing pivot/stop taps, the pinion-rig block/foot
taps, and (2026-09-02) the four blind #4-40 taps under the maker's nameplate's
corner screws -- stations derived from the plate's own hole pattern through
its mount transform (``fr_nameplate_spec``), so the plate, the base and the
frame's screws can never drift apart.

Black deck and underside pocket (user ruling 2026-10-09, ch30 p002/p003/p006
and ch26 p.71 photos): the black panel is a machined pad DECK_RISE proud of
the green casting top, which carries the four column sockets on its land;
underneath, one cored pocket inside a perimeter wall, crossed by two relieved
ribs, with bosses round the sockets and hanging under every blind deck seat.

Finishing (chamfer external, fillet internal; legacy 1/8-1/16 sizes): rounded
full-height plan corners, C1.59 x 45 breaks on both plates' exposed top rims
and the underside rim, a C0.79 break on the deck, the R0.50 pad-to-flange
root fillet note 1 caps, and casting fillets on the pocket's reentrant
junctions (ch06/ch30 photos: every exposed plate edge reads softened).

Dimensions: cad/DIMENSIONS.md "Chapter 6" — annotated (high) footprint,
legacy thicknesses (photo-verify note).

Layout: plates are centred in X and Z. Top-plane sketches map sketch x,y -> global X,-Z and
stack along +Y. Top plate boss starts at the bottom plate's upper face via
extrude_at_offset (raw-COM stopgap until MCP Phase 3).

Run (SolidWorks already open)::

    uv run python cad\scripts\build_fr_harmonic_base.py
"""

from __future__ import annotations

import math
import sys
from dataclasses import dataclass, replace

import numpy as np

from _common import (
    CASTING_GREEN,
    PANEL_BLACK,
    SketchDims,
    _early_bound,
    add_line_chain,
    anchor_point_to_origin,
    anchor_point_to_point,
    apply_color,
    apply_material,
    bbox_extent_check,
    blank_reference_sketches,
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
    OUT_PNG,
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
    set_dimension_prefix,
)
from _holes import (
    DRILL_POINT_H,
    THREAD_MAJOR_MM,
    HoleSpec,
    blind_cut_dia_mm,
    blind_hole_volume_mm3,
    wizard_holes,
)
from _fit_limits import deviations
from _part_pmi import _resolve_faces, author_part_pmi
from fr_harmonic_base_spec import (
    BOTTOM_LENGTH,
    BOTTOM_THICKNESS,
    BOTTOM_WIDTH,
    CASTING_FILLET_R,
    COLUMN_SOCKET_XZ,
    COLUMN_X,
    DECK_CORNER_R,
    DECK_EDGE_BREAK,
    DECK_HALF_X,
    DECK_HALF_Z,
    DECK_LENGTH,
    DECK_RISE,
    DECK_WIDTH,
    DEEP_BOSS_BOTTOM_Y,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION,
    GREEN_TOP,
    HANGING_BOSS_MIN_DIA,
    PART_SURFACE_FINISHES,
    POCKET_CEILING_Y,
    POCKET_HALF_X,
    POCKET_HALF_Z,
    POCKET_WALL,
    RIB_RELIEF,
    RIB_THICKNESS,
    SHALLOW_BOSS_BOTTOM_Y,
    SOCKET_BOSS_DIA,
    SOCKET_BORE_FINISHES,
    SPOTFACE_DEPTH_BAND_MM,
    STACK_HEIGHT,
    TOP_LENGTH,
    TOP_THICKNESS,
    TOP_WIDTH,
    UNDERSIDE_PAD_PREFIXES,
)
import fr_nameplate_spec
from dt_cone_pivot_post_installation import (
    FRAME_FRONT_COLUMN_Z,
    MECHANISM_X_SHIFT,
    MECHANISM_Z_SHIFT,
)
from cone_line import PIVOT_XZ as PIVOT_SCREW_XZ
from vn_cone_pivot_screw_spec import (
    THREAD as PIVOT_THREAD,
    THREAD_TAIL_LEN as PIVOT_THREAD_ENGAGEMENT,
)
from vn_cone_lock_knob_spec import (
    HEAD_DIA as LOCK_HEAD_DIA,
    PLUG_TAP_LEAD as LOCK_PLUG_TAP_LEAD,
    STUD_BOTTOM_CLEARANCE as LOCK_STUD_BOTTOM_CLEARANCE,
    STUD_LEN as LOCK_STUD_LEN,
    THREAD as LOCK_THREAD,
)
from dt_cone_swing_platform_geometry import PLATE_T, swing_hardware_geometry
from vn_swing_stop_screw_spec import (
    CONTACT_DIA as STOP_CONTACT_DIA,
    THREAD as STOP_THREAD,
)
from vn_slotted_screw_spec import SHANK_LEN as BLOCK_SCREW_LEN
from vn_foot_screw_spec import SHANK_LEN as FOOT_SCREW_LEN
from vn_fillister_screw_spec import SHANK_LEN as NAMEPLATE_SCREW_LEN
from vn_swing_stop_screw_spec import EMBED_LEN as STOP_ENGAGEMENT
from dt_pinion_pivot_block_geometry import BLOCK_HEIGHT, SCREW_HALF_SPACING
from pinion_rig_layout import BLOCK_SEAT_Z, SPRING_PAD_Z
from dt_pinion_spring_section import (
    SCREW_EAST_OF_PIVOT as SPRING_SCREW_EAST,
    THICK as SPRING_THICKNESS,
    THICK_BAND as SPRING_THICKNESS_BAND,
)
from dt_arbor_pedestal_spec import (
    SCREW_Z as PEDESTAL_LEDGE_SCREW_Z,
    STRAP_INNER_Z as PEDESTAL_STRAP_INNER_Z,
)
from fr_rocker_arm_support_spec import SUPPORT_HOLD_DOWN_XZ
from fr_harmonic_base_fasteners import (
    BASE_CROSS_TAP_DRILL_DIA,
    BASE_CROSS_TAP_SPEC,
    HOLD_DOWN_BEARING_OFFSET,
    HOLD_DOWN_DRILL_DEPTH,
    HOLD_DOWN_ENGAGEMENT,
    HOLD_DOWN_PITCH,
    HOLD_DOWN_SEAT_SPEC,
    HOLD_DOWN_TAP_DRILL_DIA,
    HOLD_DOWN_THREAD,
    HOLD_DOWN_THREAD_DEPTH,
    NAMEPLATE_SCREW_DRILL_DEPTH,
    NAMEPLATE_SCREW_HOLE_DEPTH,
    NAMEPLATE_SCREW_XZ,
    PEDESTAL_SCREW_ENGAGEMENT,
    SEAT_DEPTH_BAND,
    SEAT_DEPTH_STEP,
    SEAT_TIP_RESERVE,
    SUPPORT_FOOT_THICKNESS,
    seat_drill_depth,
    seat_thread_depth,
    title_block_band_mm,
)
from fr_frame_attachment_spec import (
    BASE_SCREW_SEAT_Z,
    BASE_SCREW_Y,
    CASTING_TAP_DRILL_DEPTH,
    COLUMN_SOCKET_DEPTH,
    COLUMN_SOCKET_DIAMETER,
    SCREW_SPOTFACE_DIAMETER,
)
from frame_column_stations import COLUMN_SOCKET_MATCH_BORE_MAX
from _visibility import blank_reference_geometry

import _config

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


PART_NAME = "fr-harmonic-base"
MATERIAL = "Gray Cast Iron"  # see _common.apply_material docstring

# Plate nominal geometry (BOTTOM_*/TOP_*) lives in fr_harmonic_base_spec -- the
# COM-free contract the drawing shares. DIMENSIONS.md ch6: 46 cm / 28 cm callouts
# = 18.1 x 11.0 in (annotated); the length keeps the legacy 18.0 in and the
# thicknesses come from the legacy HarmonicBase.cs (photo-verify M2 note). The
# DEPTH deliberately no longer follows the 28 cm callout: fr_harmonic_base_spec
# widens the pad to 274.5 (slab 287.2, same 0.25 in reveal per side) so the
# socket-to-pad-edge land is equal on both axes -- asserted below, because
# only this module knows the column stations.
IN = 25.4

# The four column sockets, their stations and their bore surface finishes now
# live in fr_harmonic_base_spec: the sheet may only source a surface-finish
# control from a part SPEC, and the bore size reaches that spec through the
# leaf module frame_column_stations. Bore diameters remain nominal CAD
# geometry -- match-fit production sockets to their assigned actual MHA-FR-003
# tubes, not to a fixed diameter band.
BASE_SPOTFACE_PLANE_Z = TOP_WIDTH / 2.0
BASE_SPOTFACE_DEPTH = BASE_SPOTFACE_PLANE_Z - BASE_SCREW_SEAT_Z
BASE_SCREW_FACES = (("front", -1.0, True), ("rear", 1.0, False))


if BASE_SPOTFACE_DEPTH <= 0.0:
    raise AssertionError("base cross-screw spotface must cut inward from the side")

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
# mechanism hole sits >= 26 from every plate edge; the closest seats to a deck
# edge are the nameplate taps (NAMEPLATE_SCREW_XZ), Ø2.26 about 8 inside the
# deck's west edge -- clear of its 0.79 break, so no break touches a seat.
# Plan corners are ROUNDED, not chamfered (2026-09 photo re-derive): every
# ch30 plate (p002/p003 front corners, p006 rear) shows the casting's vertical
# corners as one large radius running the full height, flange and pad
# together. 7/8 in on the flange; the pad's radius is 1/4 in smaller so the
# two arcs stay concentric across the 1/4 in reveal.
FLANGE_CORNER_R = 0.875 * IN  # 22.225
PAD_CORNER_R = FLANGE_CORNER_R - (BOTTOM_LENGTH - TOP_LENGTH) / 2.0  # 15.875
RIM_CHAMFER = 0.0625 * IN  # 1.5875 legs, top rims + underside rim
PAD_ROOT_R = 0.5  # pad-to-flange root fillet; modelled, never called out

# Black deck + green land (user ruling 2026-10-09; ch11 p.21, ch13 p.25 and
# ch30 p002/p003/p006 show a BLACK panel on the green casting top). The raised
# rim of the 2026-09 re-derive is gone: the panel is a machined pad DECK_RISE
# proud of the green top, centred on it, so the nameplate and every seat stay
# on the deck at STACK_HEIGHT while the column sockets open on the green land.
# The deck face is painted PANEL_BLACK at the FACE level (part and body stay
# casting green). DECK_* live in fr_harmonic_base_spec.

# Stamped serial number (2026-09-02, ch26 p.70 page001_img02/03): a hand-stamped
# "2" on the bright machined deck. Cut from the vendored closed-region DXF
# (gen_base_serial_dxf.py regenerates it from these constants) on a plane at
# the deck top, SERIAL_DEPTH deep. Since the 2026-10-09 ruling it sits in the
# deck's north-west (+X, +Z) corner, SERIAL_INSET in from both deck edges --
# clear of the nameplate on the deck's west end and of the corner's break.
SERIAL_TEXT = "2"
SERIAL_HEIGHT_MM = 3.5  # p.70 macro: a small hand stamp
SERIAL_DEPTH = 0.3  # a stamp, not an engraving
SERIAL_INSET = 6.0
SERIAL_XZ = (DECK_HALF_X - SERIAL_INSET, DECK_HALF_Z - SERIAL_INSET)  # (161.0, 124.25)
SERIAL_MIRROR_Y = (
    False  # flip if the seat's deck-top sketch frame reads the glyph mirrored
)
SERIAL_DXF = REFERENCES_DIR / "base-serial.dxf"
SERIAL_AREA_MM2 = 3.1029  # pinned from gen_base_serial_dxf's summary (net glyph area)

# Cone swing hardware, blind from the TOP face. MACHINE-handed part coords.
# The platform recipe owns the shared lock/stop contact calculation; the base
# supplies its installed pivot station (cone_line.PIVOT_XZ, the swing pivot
# on the cone journal line) and exact purchased-hardware diameters.
SWING_HARDWARE_GEOMETRY = swing_hardware_geometry(
    PIVOT_SCREW_XZ,
    lock_head_dia=LOCK_HEAD_DIA,
    stop_contact_dia=STOP_CONTACT_DIA,
)
LOCK_KNOB_XZ = SWING_HARDWARE_GEOMETRY.lock_xz
STOP_SCREW_XZ = SWING_HARDWARE_GEOMETRY.stop_xz

# Blind #10-24 UNC-2B bottoming tap: only the 9.525-mm threaded tail enters.
# Sized at the printed worst case: full threads clear the tip by 0.25 at
# their low limit, and the drill keeps the bottoming tap's two-pitch lead.
PIVOT_SCREW_HOLE_DEPTH = seat_thread_depth(PIVOT_THREAD_ENGAGEMENT)
PIVOT_SCREW_DRILL_DEPTH = seat_drill_depth(
    PIVOT_SCREW_HOLE_DEPTH, PIVOT_THREAD, "tapped_bottoming"
)

# The 19.05-mm stock stud enters 12.70 through the platform, or its full
# length when the head fences the disengaged notch on the bare base.
# Full threads clear that deepest pose by 0.25 at their printed low limit;
# a five-pitch plug-tap lead fits below them, before the drill point.
LOCK_STUD_ENGAGEMENT = LOCK_STUD_LEN - PLATE_T
LOCK_SCREW_HOLE_DEPTH = seat_thread_depth(LOCK_STUD_LEN)
LOCK_SCREW_DRILL_DEPTH = seat_drill_depth(LOCK_SCREW_HOLE_DEPTH, LOCK_THREAD, "tapped")
if LOCK_SCREW_HOLE_DEPTH - SEAT_DEPTH_BAND - LOCK_STUD_LEN < LOCK_STUD_BOTTOM_CLEARANCE:
    raise AssertionError("cone lock seat loses the knob's stud clearance at its low limit")
if LOCK_SCREW_DRILL_DEPTH - LOCK_SCREW_HOLE_DEPTH < LOCK_PLUG_TAP_LEAD:
    raise AssertionError("cone lock seat drill loses the knob's plug-tap lead")

# The stop (the foot screw's #4-40 x 3/8 stock) is screwed fully home: its
# head seats on the base top and its whole height bears on the platform edge.
# Full thread clears the full-shank embed at the printed low limit; the drill
# keeps the plug tap's five-pitch lead below the high limit.
STOP_SCREW_HOLE_DEPTH = seat_thread_depth(STOP_ENGAGEMENT)
STOP_SCREW_DRILL_DEPTH = seat_drill_depth(STOP_SCREW_HOLE_DEPTH, STOP_THREAD, "tapped")

# Alignment-pinion rig hold-downs, blind from the TOP face in the same
# machine-handed convention: four #8-32 seats under the two pivot blocks
# and one #4-40 seat under the spring foot (the arbor pedestals moved to their
# own #8-32 group, PEDESTAL_SCREW_XZ, with U34c).
# The block and spring seats follow the user-authoritative 32T rig's parked
# tip gap (U28, 2026-09-23: 2.2425, the park-out that seats the 120T tips at
# the drum's base-circle root) and the U28 block re-layout -- screws +-8.5
# about the pivot bore, block mid-depth 5.125 in from each outer face; the
# drum-axis pedestal seats remain unchanged.  Ruling (c) (user, 2026-09-24):
# the block and spring-foot z stations are pinion_rig_layout's -- the front
# block stands one feeler off the front strap, the spring foot's pad one
# leaf off the back block, and the whole rig where the rig-set leaf D off gear
# j = 19 puts it (RIG_AFT_SHIFT, user ruling P1-2).
_FORMER_BLOCK_SCREW_X = (-17.226441649810653, -0.22644164981065273)  # east, west
BLOCK_SCREW_XZ = tuple(
    (x + MECHANISM_X_SHIFT, z) for z in BLOCK_SEAT_Z for x in _FORMER_BLOCK_SCREW_X
)
# Rule 12 (audit E10): stock 31.75-mm (#8-32 x 1-1/4) slotted screws penetrate
# 11.25 mm below each 20.5-mm block -- 10.74 = 2.58D at the BlockHeight .XX
# band.  The full-thread depth keeps the screw off the bottom at the worst
# case (12.75 - 0.8 .X depth band >= 11.25 + 0.51 block band, 0.19 spare).
BLOCK_SCREW_HOLE_DEPTH = 12.75
# The drill keeps the bottoming tap's two #8-32 pitches (1.5875 mm) past the
# deepest printed thread; 15.0 left 1.23 at the .XX worst case.
BLOCK_SCREW_DRILL_DEPTH = seat_drill_depth(
    BLOCK_SCREW_HOLE_DEPTH, "#8-32", "tapped_bottoming"
)
_FORMER_FOOT_SCREW_XZ = (
    # spring foot: SPRING_SCREW_EAST of the swing pivot bore, which stands
    # SCREW_HALF_SPACING west of the east block screw -- outboard of the back
    # strap (re-derived 2026-09-24; the drive train asserts it; z:
    # pinion_rig_layout)
    (
        _FORMER_BLOCK_SCREW_X[0] + SCREW_HALF_SPACING - SPRING_SCREW_EAST,
        SPRING_PAD_Z - MECHANISM_Z_SHIFT,
    ),
)
FOOT_SCREW_XZ = tuple(
    (x + MECHANISM_X_SHIFT, z + MECHANISM_Z_SHIFT) for x, z in _FORMER_FOOT_SCREW_XZ
)
# The stock 9.525-mm foot screw penetrates deepest below the THINNEST spring
# strip the stock band allows (#859 ruling 4: 17-7 PH 0.015 in, 2325K19); the
# seat is sized at its printed worst case for a #4-40 bottoming tap.
SPRING_THICKNESS_MIN = SPRING_THICKNESS + deviations(SPRING_THICKNESS_BAND)[0]
FOOT_SCREW_HOLE_DEPTH = seat_thread_depth(FOOT_SCREW_LEN - SPRING_THICKNESS_MIN)
FOOT_SCREW_DRILL_DEPTH = seat_drill_depth(
    FOOT_SCREW_HOLE_DEPTH, "#4-40", "tapped_bottoming"
)

# U34c (dt-bank-pedestal-layout-20260923 rev 3, H1): one MHA-VN-032 #8-32 x 3/4
# fillister holds each arbor pedestal through its ledge hole. Machine frame,
# like NAMEPLATE_SCREW_XZ (no _FORMER_ twin; the mechanism shift is already in
# the drive train's stations): the drum axis x, and z = each strap inner face
# -+ the 19.0 from that face to the ledge hole. The strap faces are the
# cylinder bank's own stack (#743, cylinder_bank_layout FRONT/BACK
# _STRAP_INNER_Z). The seats are TRANSFERRED from the fitted pedestals at
# assembly, so the print gives no position. These are literals because the
# base cannot import the drive train (it imports the base), and importing the
# bank layout would make the frame read machine/channels.yaml (its station
# ladder; test_config_deps_recipe_digest_skips_unread_yaml); the drive train
# asserts them against its own derivation within 0.05 and
# test_dt_drive_train_support_layout pins them within 0.005.
_DRUM_AXIS_X = -54.7 + MECHANISM_X_SHIFT
_PEDESTAL_STRAP_FACE_Z = (-72.019, 73.062)
_PEDESTAL_LEDGE_OFFSET = PEDESTAL_STRAP_INNER_Z - PEDESTAL_LEDGE_SCREW_Z  # 19.0
PEDESTAL_SCREW_XZ = (
    (_DRUM_AXIS_X, _PEDESTAL_STRAP_FACE_Z[0] - _PEDESTAL_LEDGE_OFFSET),
    (_DRUM_AXIS_X, _PEDESTAL_STRAP_FACE_Z[1] + _PEDESTAL_LEDGE_OFFSET),
)
# Rule 12 (audit E15), judged at the printed worst case: flange 5.0 +-0.8,
# screw 19.05 +0/-0.76 (B18.6.3), these depths +-0.8 (.X). The longest screw
# in the thinnest flange reaches 14.85; 16.0 - 0.8 keeps it 0.35 off the
# incomplete threads (>= 0.25 tip reserve). The drill keeps two #8-32 pitches
# of bottoming-tap lead beyond the deepest thread at the worst case too:
# 19.5 - 0.8 >= 16.0 + 0.8 + 1.5875. Minimum engagement 12.49 = 3.0D.
PEDESTAL_SCREW_HOLE_DEPTH = 16.0
PEDESTAL_SCREW_DRILL_DEPTH = 19.5
# A transferred seat lands where the fitted pedestal stands, within the
# study's +-2 x / +-5 z fit-up bound of nominal; the wall checks book it.
PEDESTAL_TRANSFER_XZ = (2.0, 5.0)
PEDESTAL_TRANSFER_ENVELOPE = math.hypot(*PEDESTAL_TRANSFER_XZ)

# Maker's nameplate seats: stations and depths in fr_harmonic_base_fasteners.
# The plate lies flat on the deck, so its seats are cut from the deck face.
if abs(fr_nameplate_spec.MOUNT_BACK_Y - STACK_HEIGHT) > 1e-9:
    raise AssertionError(
        f"nameplate back face y {fr_nameplate_spec.MOUNT_BACK_Y} is not on the deck "
        f"({STACK_HEIGHT}); its seats are cut from the deck face"
    )
if fr_nameplate_spec.MOUNT_NORMAL != (0.0, 1.0, 0.0):
    raise AssertionError(
        f"nameplate front normal {fr_nameplate_spec.MOUNT_NORMAL} is not the deck's +Y"
    )
# The whole plate (its bounding corners, both faces) must lie flat on the
# raised deck, inside its edge break by >= 1.0, or a corner would overhang the
# step down to the green land (user ruling 2026-10-09: 4.0 inside the west edge).
_NAMEPLATE_CORNERS_XZ = tuple(
    (pt[0], pt[2])
    for pt in (
        fr_nameplate_spec.mount_point((x, y, 0.0))
        for x in (0.0, fr_nameplate_spec.PLATE_WIDTH)
        for y in (0.0, fr_nameplate_spec.PLATE_HEIGHT)
    )
)
NAMEPLATE_DECK_CLEARANCE = min(
    min(DECK_HALF_X - abs(x), DECK_HALF_Z - abs(z)) for x, z in _NAMEPLATE_CORNERS_XZ
)
if NAMEPLATE_DECK_CLEARANCE - DECK_EDGE_BREAK < 1.0:
    raise AssertionError(
        f"nameplate footprint {_NAMEPLATE_CORNERS_XZ} sits only "
        f"{NAMEPLATE_DECK_CLEARANCE:.2f} inside the deck edge (need >= 1.0 past "
        f"its {DECK_EDGE_BREAK:.2f} break)"
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
PEDESTAL_SEAT_SPEC = HoleSpec(
    "tapped_bottoming",
    "#8-32",
    end="blind",
    depth_mm=PEDESTAL_SCREW_DRILL_DEPTH,
    thread_class="2B",
    overrides_mm={"ThreadDepth": PEDESTAL_SCREW_HOLE_DEPTH},
)
# Rule 12 (E15) at the printed worst case, not just the nominal the stock-fit
# guard checks: the shallowest drill still keeps two pitches of bottoming-tap
# lead past the deepest thread (the reach side is asserted by the drive train
# against BASE_PEDESTAL_HOLE_DEPTH).
_PEDESTAL_DEPTH_BAND = 0.8  # .X
_PEDESTAL_TAP_LEAD = 2 * 25.4 / float(PEDESTAL_SEAT_SPEC.size.rsplit("-", 1)[1])
if (
    PEDESTAL_SCREW_DRILL_DEPTH - _PEDESTAL_DEPTH_BAND
    < PEDESTAL_SCREW_HOLE_DEPTH + _PEDESTAL_DEPTH_BAND + _PEDESTAL_TAP_LEAD
):
    raise AssertionError(
        "pedestal hold-down drill loses the bottoming-tap lead at the worst case"
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
PEDESTAL_SCREW_HOLE_DIA = blind_cut_dia_mm(PEDESTAL_SEAT_SPEC)
NAMEPLATE_SCREW_HOLE_DIA = blind_cut_dia_mm(NAMEPLATE_SEAT_SPEC)

# Socket cylinders occupy Y=25.4..47.8, overlapping the deepest vertical-seat
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
        (PEDESTAL_SCREW_XZ, PEDESTAL_SCREW_HOLE_DIA),
        (NAMEPLATE_SCREW_XZ, NAMEPLATE_SCREW_HOLE_DIA),
    )
    for occupant in occupants
)
if COLUMN_SOCKET_NEAREST_OCCUPANT_WALL < 1.0:
    raise AssertionError(
        "base column socket leaves less than 1 mm wall to another base cavity"
    )
# Nominal model-space land from each bore to the pad edge, on the green top
# the sockets open on (user ruling 2026-10-09). Its worst case is proven
# below. TOP_WIDTH is sized so this land is EQUAL on both axes: the 2026-09
# blind machinist review rejected the former 10.5 in pad, whose land in Z
# could not survive the coordinate stack while every table dimension stayed
# in tolerance.
COLUMN_SOCKET_LAND_X = min(
    TOP_LENGTH / 2.0 - abs(x) - COLUMN_SOCKET_DIAMETER / 2.0
    for x, _z in COLUMN_SOCKET_XZ
)
COLUMN_SOCKET_LAND_Z = min(
    TOP_WIDTH / 2.0 - abs(z) - COLUMN_SOCKET_DIAMETER / 2.0
    for _x, z in COLUMN_SOCKET_XZ
)
if abs(COLUMN_SOCKET_LAND_X - COLUMN_SOCKET_LAND_Z) > 1e-9:
    raise AssertionError(
        "base socket land is not equal on both axes: "
        f"x={COLUMN_SOCKET_LAND_X}, z={COLUMN_SOCKET_LAND_Z}"
    )
# The sockets stand on the green land, clear of the raised deck's side wall:
# a positive gap along either axis separates bore and deck.
COLUMN_SOCKET_DECK_GAP = min(
    max(
        abs(x) - COLUMN_SOCKET_DIAMETER / 2.0 - DECK_HALF_X,
        abs(z) - COLUMN_SOCKET_DIAMETER / 2.0 - DECK_HALF_Z,
    )
    for x, z in COLUMN_SOCKET_XZ
)
if COLUMN_SOCKET_DECK_GAP < 1.0:
    raise AssertionError("base column socket crowds the raised deck")

# The finished land between each bore and the pad edge's break must stay
# 1.0 wide and continuous (2026-09 blind machinist review). It used to be
# a sheet note ("1.0 MIN ... AFTER MATCHING AND EDGE BREAK"), which put a
# dimension in a note (hb-render-4 eye pass); the stack below proves every
# in-tolerance part meets it, so the sheet needs no note.
COLUMN_SOCKET_LAND_MIN = 1.0


def _general_band_mm() -> float:
    """The title block's .X band: the loosest general tolerance it defines.

    The lengths print one place; the hole-table coordinates
    print at least one, so this band bounds every location term.
    """
    return title_block_band_mm("linear_1pl")


def _edge_break_mm() -> float:
    row = _config.title_block("edge_break")
    return max(float(row["radius_mm"]), float(row["chamfer_max_mm"]))


def column_socket_land_stack(nominal: float) -> dict[str, float]:
    """Worst-case finished green land from a bore to the pad edge's break.

    One axis, from its owning sources. The table locates the bore from the
    flange edge; the pad edge's place on the flange follows from the two
    printed plate lengths, each of which moves one edge by half its band.
    The bore is matched to its tube up to COLUMN_SOCKET_MATCH_BORE_MAX and
    takes the title block's largest edge break; the pad edge carries the
    modelled top-rim chamfer, whose printed leg may run a full band long.
    """
    band = _general_band_mm()
    edge_break = _edge_break_mm()
    return {
        "nominal": nominal,
        "flange length": -band / 2.0,
        "pad length": -band / 2.0,
        "bore location": -band,
        "matched bore": -(COLUMN_SOCKET_MATCH_BORE_MAX - COLUMN_SOCKET_DIAMETER) / 2.0,
        "bore edge break": -edge_break,
        "pad edge chamfer": -(RIM_CHAMFER + band),
    }


def _stack_text(stack: dict[str, float]) -> str:
    terms = ", ".join(f"{name} {value:+.3f}" for name, value in stack.items())
    return f"{terms} = {sum(stack.values()):.3f}"


COLUMN_SOCKET_LAND_STACKS = {
    "x": column_socket_land_stack(COLUMN_SOCKET_LAND_X),
    "z": column_socket_land_stack(COLUMN_SOCKET_LAND_Z),
}


def column_socket_break_even_bore(stack: dict[str, float]) -> float:
    """The largest matched bore for which ``stack`` still leaves the minimum
    land: the ceiling plus twice the stack's radial slack over the minimum.
    It shows how far COLUMN_SOCKET_MATCH_BORE_MAX, a functional judgement
    rather than a printed or vendor limit, sits inside what the land allows.
    """
    return COLUMN_SOCKET_MATCH_BORE_MAX + 2.0 * (
        sum(stack.values()) - COLUMN_SOCKET_LAND_MIN
    )


COLUMN_SOCKET_BREAK_EVEN_BORE = min(
    column_socket_break_even_bore(stack) for stack in COLUMN_SOCKET_LAND_STACKS.values()
)
for _axis, _stack in COLUMN_SOCKET_LAND_STACKS.items():
    if sum(_stack.values()) < COLUMN_SOCKET_LAND_MIN:
        raise AssertionError(
            f"base socket land ({_axis}), worst case: {_stack_text(_stack)} "
            f"< {COLUMN_SOCKET_LAND_MIN}; break-even matched bore "
            f"{column_socket_break_even_bore(_stack):.2f} is under the "
            f"{COLUMN_SOCKET_MATCH_BORE_MAX} ceiling"
        )


def require_blind_seat_fit(
    label: str,
    seat: HoleSpec,
    engagement: float,
    *,
    tip_reserve: float = SEAT_TIP_RESERVE,
    band: float = SEAT_DEPTH_BAND,
) -> None:
    """Keep a stock screw in full threads above a manufacturable tap lead,
    with both printed depths at the worst case of their ``band``."""
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
    diameter = THREAD_MAJOR_MM[seat.size]
    if engagement < diameter:
        raise AssertionError(
            f"{label}: less than one diameter of full-thread engagement"
        )
    if engagement < 1.5 * diameter - 1e-9:
        raise AssertionError(
            f"{label}: screw engages {engagement / diameter:.3f}D, under 1.5D"
        )
    if thread_depth - band < 1.5 * diameter - 1e-9:
        raise AssertionError(
            f"{label}: full thread {thread_depth - band:.3f} at its printed low "
            f"limit is under 1.5D ({1.5 * diameter:.3f})"
        )
    if thread_depth - band - engagement < tip_reserve - 1e-9:
        raise AssertionError(
            f"{label}: screw bottoms before seating in full threads at the "
            f"printed low limit ({thread_depth:.2f} - {band:.2f})"
        )
    pitch = 25.4 / float(seat.size.rsplit("-", 1)[1])
    lead_pitches = 2.0 if seat.kind == "tapped_bottoming" else 5.0
    if seat.depth_mm - band - (thread_depth + band) < lead_pitches * pitch - 1e-9:
        tap = "bottoming" if seat.kind == "tapped_bottoming" else "plug"
        raise AssertionError(
            f"{label}: drill lacks {lead_pitches:g}-pitch {tap}-tap lead"
        )


# Guard the deepest installed stock insertion in all eight native seat groups.
for _label, _seat, _engagement in (
    ("rocker support", HOLD_DOWN_SEAT_SPEC, HOLD_DOWN_ENGAGEMENT),
    ("cone pivot", PIVOT_SEAT_SPEC, PIVOT_THREAD_ENGAGEMENT),
    ("cone lock", LOCK_SEAT_SPEC, LOCK_STUD_LEN),
    ("swing stop", STOP_SEAT_SPEC, STOP_ENGAGEMENT),
    ("pinion block", BLOCK_SEAT_SPEC, BLOCK_SCREW_LEN - BLOCK_HEIGHT),
    ("spring foot", FOOT_SEAT_SPEC, FOOT_SCREW_LEN - SPRING_THICKNESS_MIN),
    (
        "pedestal hold-down",
        PEDESTAL_SEAT_SPEC,
        PEDESTAL_SCREW_ENGAGEMENT,
    ),
    (
        "nameplate",
        NAMEPLATE_SEAT_SPEC,
        NAMEPLATE_SCREW_LEN - fr_nameplate_spec.PLATE_THICKNESS,
    ),
):
    require_blind_seat_fit(_label, _seat, _engagement)

# Underside pocket (user ruling 2026-10-09). Every blind deck seat drills
# deeper than the POCKET_SKIN under the deck could back, so each seat group
# hangs a cast boss from the pocket ceiling down to one of two cast levels.
# One size serves every seat: max(HANGING_BOSS_MIN_DIA, 2.5 x the largest
# tap drill). Round where a seat stands alone; where seats crowd each other
# or the wall, a pad of the same width covers the group (the pinion-block
# pairs, whose round bosses would leave a 1.0 core between them), the
# transferred pedestal seats' fit-up envelope, or ties the seat to the wall
# (the cone lock, whose round boss would leave a 5.2 core).
_HANGING_DRILL_DIAS = (
    HOLD_DOWN_TAP_DRILL_DIA,
    PIVOT_SCREW_HOLE_DIA,
    LOCK_SCREW_HOLE_DIA,
    STOP_SCREW_HOLE_DIA,
    BLOCK_SCREW_HOLE_DIA,
    FOOT_SCREW_HOLE_DIA,
    PEDESTAL_SCREW_HOLE_DIA,
    NAMEPLATE_SCREW_HOLE_DIA,
)
HANGING_BOSS_DIA = max(HANGING_BOSS_MIN_DIA, 2.5 * max(_HANGING_DRILL_DIAS))  # 16.0
HANGING_BOSS_HALF = HANGING_BOSS_DIA / 2.0
# The pinion-block pads run from one pair's outer seat to the other's, a boss
# radius past each; the pedestal pads cover the +-5 z transfer envelope.
BLOCK_PAD_LENGTH = (
    max(x for x, _z in BLOCK_SCREW_XZ)
    - min(x for x, _z in BLOCK_SCREW_XZ)
    + HANGING_BOSS_DIA
)  # 33.0
PEDESTAL_PAD_LENGTH = 26.0
# The cone-lock pad runs from a boss radius past the seat into the mid-wall.
LOCK_PAD_WALL_Z = -(POCKET_HALF_Z + POCKET_WALL / 2.0)
# Ribs and lugs end mid-wall, so a +-0.8 shift of the pocket outline never
# opens a slot between them and the wall.
RIB_HALF_LENGTH_X = POCKET_HALF_X + POCKET_WALL / 2.0
RIB_HALF_LENGTH_Z = POCKET_HALF_Z + POCKET_WALL / 2.0


@dataclass(frozen=True)
class HangingSeat:
    """One blind seat group and the cast boss or pad backing it."""

    label: str
    seat: HoleSpec
    stations: tuple[tuple[float, float], ...]
    boss_bottom_y: float
    # Boss metal from each seat axis in x / z, and the seat's own fit-up
    # envelope (transferred seats land anywhere inside it).
    half_x: float = HANGING_BOSS_HALF
    half_z: float = HANGING_BOSS_HALF
    envelope: tuple[float, float] = (0.0, 0.0)

    @property
    def drill_dia(self) -> float:
        return blind_cut_dia_mm(self.seat)

    @property
    def tip_y(self) -> float:
        """Height of the drill point's tip: the cylinder AND the 118-degree point."""
        return STACK_HEIGHT - self.seat.depth_mm - self.drill_dia / 2.0 * DRILL_POINT_H

    @property
    def floor_wall(self) -> float:
        """Metal under the drill tip, down to the boss bottom."""
        return self.tip_y - self.boss_bottom_y

    @property
    def side_wall(self) -> float:
        """Thinnest boss wall beside the drill, anywhere in the envelope."""
        return (
            min(self.half_x - self.envelope[0], self.half_z - self.envelope[1])
            - self.drill_dia / 2.0
        )


# Each seat ends on the SHALLOW level when that still backs its drill tip,
# else on the DEEP one. The spring foot is the one exception: its round boss
# would cross the north pinion-block pad in the same shallow sketch, so it
# hangs to the deep level, which backs it all the more.
HANGING_SEATS = (
    HangingSeat("rocker support", HOLD_DOWN_SEAT_SPEC, HOLE_XZ, DEEP_BOSS_BOTTOM_Y),
    HangingSeat(
        "cone pivot", PIVOT_SEAT_SPEC, (PIVOT_SCREW_XZ,), SHALLOW_BOSS_BOTTOM_Y
    ),
    HangingSeat("cone lock", LOCK_SEAT_SPEC, (LOCK_KNOB_XZ,), DEEP_BOSS_BOTTOM_Y),
    HangingSeat("swing stop", STOP_SEAT_SPEC, (STOP_SCREW_XZ,), SHALLOW_BOSS_BOTTOM_Y),
    HangingSeat("pinion block", BLOCK_SEAT_SPEC, BLOCK_SCREW_XZ, SHALLOW_BOSS_BOTTOM_Y),
    HangingSeat("spring foot", FOOT_SEAT_SPEC, FOOT_SCREW_XZ, DEEP_BOSS_BOTTOM_Y),
    HangingSeat(
        "pedestal hold-down",
        PEDESTAL_SEAT_SPEC,
        PEDESTAL_SCREW_XZ,
        DEEP_BOSS_BOTTOM_Y,
        half_z=PEDESTAL_PAD_LENGTH / 2.0,
        envelope=PEDESTAL_TRANSFER_XZ,
    ),
    HangingSeat(
        "nameplate", NAMEPLATE_SEAT_SPEC, NAMEPLATE_SCREW_XZ, SHALLOW_BOSS_BOTTOM_Y
    ),
)


def require_hanging_boss(seat: HangingSeat) -> None:
    """Back one blind seat at the printed worst case (policy rule 12).

    Under the tip: 1.5 thread diameters at nominal, and the 2.0 wall target
    once the printed depth runs deep and the cast level runs high by their
    bands. Beside the drill: the 2.0 target once the boss outline (.X size,
    half its band per side) and the seat location (.X) both run against it.
    """
    band = _general_band_mm()
    major = THREAD_MAJOR_MM[seat.seat.size]
    if not RIB_RELIEF <= seat.boss_bottom_y < POCKET_CEILING_Y:
        raise AssertionError(f"{seat.label}: boss bottom outside the pocket")
    if seat.floor_wall < 1.5 * major - 1e-9:
        raise AssertionError(
            f"{seat.label}: {seat.floor_wall:.2f} under the drill tip is less than "
            f"1.5D ({1.5 * major:.2f}) above its boss bottom"
        )
    if seat.floor_wall - SEAT_DEPTH_BAND - band < 2.0 - 1e-9:
        raise AssertionError(
            f"{seat.label}: boss floor under the drill tip thins under 2.0 at the "
            "worst case"
        )
    if seat.side_wall - band - band / 2.0 < 2.0 - 1e-9:
        raise AssertionError(
            f"{seat.label}: boss side wall {seat.side_wall:.2f} thins under 2.0 at "
            "the worst case"
        )


def _shallow_level_backs(seat: HangingSeat) -> bool:
    try:
        require_hanging_boss(replace(seat, boss_bottom_y=SHALLOW_BOSS_BOTTOM_Y))
    except AssertionError:
        return False
    return True


for _hanging in HANGING_SEATS:
    require_hanging_boss(_hanging)
    if (
        _hanging.boss_bottom_y != SHALLOW_BOSS_BOTTOM_Y
        and _hanging.label != "spring foot"
        and _shallow_level_backs(_hanging)
    ):
        raise AssertionError(f"{_hanging.label}: the shallow level already backs it")
HANGING_SEAT_WALLS = {
    seat.label: {"floor": seat.floor_wall, "side": seat.side_wall}
    for seat in HANGING_SEATS
}
_HANGING_BY_LABEL = {seat.label: seat for seat in HANGING_SEATS}
PIVOT_DRILL_BOTTOM_WALL = _HANGING_BY_LABEL["cone pivot"].floor_wall
LOCK_DRILL_BOTTOM_WALL = _HANGING_BY_LABEL["cone lock"].floor_wall
STOP_DRILL_BOTTOM_WALL = _HANGING_BY_LABEL["swing stop"].floor_wall
PEDESTAL_DRILL_BOTTOM_WALL = _HANGING_BY_LABEL["pedestal hold-down"].floor_wall

# The #10-32 cross taps run from the pad's front/rear faces through the
# socket and on past the Ø41.5 socket boss, so each ends in a lug hung from
# the ceiling to the shallow level: from the tap axis's far side (a boss
# radius off it) out into the mid-wall, and from the socket centre inward a
# lug length that keeps 1.5D past the drill tip.
CROSS_TAP_LUG_WIDTH = 27.0  # x: 189.0 -> 216.0, 5.75 into the 12.0 wall
CROSS_TAP_LUG_LENGTH = 37.0  # z: 112.0 -> 75.0
CROSS_TAP_LUG_INNER_X = COLUMN_X - HANGING_BOSS_HALF
CROSS_TAP_LUG_INNER_Z = abs(FRAME_FRONT_COLUMN_Z) - CROSS_TAP_LUG_LENGTH
_CROSS_TAP_MAJOR = THREAD_MAJOR_MM[BASE_CROSS_TAP_SPEC.size]
CROSS_TAP_TIP_Z = (
    BASE_SCREW_SEAT_Z
    - CASTING_TAP_DRILL_DEPTH
    - BASE_CROSS_TAP_DRILL_DIA / 2.0 * DRILL_POINT_H
)
CROSS_TAP_LUG_WALLS = {
    "past tip": CROSS_TAP_TIP_Z - CROSS_TAP_LUG_INNER_Z,
    "under drill": BASE_SCREW_Y
    - BASE_CROSS_TAP_DRILL_DIA / 2.0
    - SHALLOW_BOSS_BOTTOM_Y,
    "beside drill": COLUMN_X - CROSS_TAP_LUG_INNER_X - BASE_CROSS_TAP_DRILL_DIA / 2.0,
}
if not (
    POCKET_HALF_X + 1.0
    < CROSS_TAP_LUG_INNER_X + CROSS_TAP_LUG_WIDTH
    < TOP_LENGTH / 2.0 - 1.0
):
    raise AssertionError("cross-tap lug must end inside the pocket wall")
if CROSS_TAP_LUG_WALLS["past tip"] < 1.5 * _CROSS_TAP_MAJOR:
    raise AssertionError("cross-tap lug ends less than 1.5D past the drill tip")
if min(CROSS_TAP_LUG_WALLS.values()) - 1.5 * _general_band_mm() < 2.0:
    raise AssertionError("cross-tap lug wall thins under 2.0 at the worst case")

# The socket bosses: 1/2 x (boss - bore) of wall round each bore, and the
# boss swallows the pocket's plan corner, so the pocket needs no corner radius.
SOCKET_BOSS_WALL = (SOCKET_BOSS_DIA - COLUMN_SOCKET_DIAMETER) / 2.0
if (
    SOCKET_BOSS_WALL
    - (COLUMN_SOCKET_MATCH_BORE_MAX - COLUMN_SOCKET_DIAMETER) / 2.0
    - _general_band_mm()
    < 2.0
):
    raise AssertionError("socket boss wall thins under 2.0 at the worst case")
for _x, _z in COLUMN_SOCKET_XZ:
    if (
        math.hypot(POCKET_HALF_X - abs(_x), POCKET_HALF_Z - abs(_z))
        >= SOCKET_BOSS_DIA / 2.0
    ):
        raise AssertionError("socket boss no longer covers the pocket's plan corner")
# Under the deck and under the green land, the ceiling keeps a full skin.
if min(POCKET_CEILING_Y - BASE_SCREW_Y, GREEN_TOP - POCKET_CEILING_Y) < 0.0:
    raise AssertionError(
        "pocket ceiling below the cross-tap axis or above the green land"
    )

# The pocket's hanging features in plan, machine (x, z): ("disc", x, z, r)
# or ("rect", x0, x1, z0, z1). The build sketches exactly these; the volume
# checks, the paint areas and the drawing read them from here.
PocketShape = tuple


def _disc(xz: tuple[float, float], radius: float) -> PocketShape:
    return ("disc", xz[0], xz[1], radius)


def _rect(x_span: tuple[float, float], z_span: tuple[float, float]) -> PocketShape:
    return ("rect", *sorted(x_span), *sorted(z_span))


SOCKET_BOSS_SHAPES = tuple(_disc(xz, SOCKET_BOSS_DIA / 2.0) for xz in COLUMN_SOCKET_XZ)
LONG_RIB_SHAPE = _rect(
    (-RIB_HALF_LENGTH_X, RIB_HALF_LENGTH_X), (-RIB_THICKNESS / 2.0, RIB_THICKNESS / 2.0)
)
CROSS_RIB_SHAPE = _rect(
    (-RIB_THICKNESS / 2.0, RIB_THICKNESS / 2.0), (-RIB_HALF_LENGTH_Z, RIB_HALF_LENGTH_Z)
)
DEEP_BOSS_CENTRES = (*HOLE_XZ, *FOOT_SCREW_XZ)
LOCK_PAD_SHAPE = _rect(
    (LOCK_KNOB_XZ[0] - HANGING_BOSS_HALF, LOCK_KNOB_XZ[0] + HANGING_BOSS_HALF),
    (LOCK_PAD_WALL_Z, LOCK_KNOB_XZ[1] + HANGING_BOSS_HALF),
)
PEDESTAL_PAD_SHAPES = tuple(
    _rect(
        (x - HANGING_BOSS_HALF, x + HANGING_BOSS_HALF),
        (z - PEDESTAL_PAD_LENGTH / 2.0, z + PEDESTAL_PAD_LENGTH / 2.0),
    )
    for x, z in PEDESTAL_SCREW_XZ
)
DEEP_BOSS_SHAPES = (
    *(_disc(xz, HANGING_BOSS_HALF) for xz in DEEP_BOSS_CENTRES),
    LOCK_PAD_SHAPE,
    *PEDESTAL_PAD_SHAPES,
)
SHALLOW_BOSS_CENTRES = (PIVOT_SCREW_XZ, STOP_SCREW_XZ, *NAMEPLATE_SCREW_XZ)
BLOCK_PAD_SHAPES = tuple(
    _rect(
        (
            min(x for x, _z in BLOCK_SCREW_XZ) - HANGING_BOSS_HALF,
            max(x for x, _z in BLOCK_SCREW_XZ) + HANGING_BOSS_HALF,
        ),
        (z - HANGING_BOSS_HALF, z + HANGING_BOSS_HALF),
    )
    for z in sorted({z for _x, z in BLOCK_SCREW_XZ})
)
SHALLOW_BOSS_SHAPES = (
    *(_disc(xz, HANGING_BOSS_HALF) for xz in SHALLOW_BOSS_CENTRES),
    *BLOCK_PAD_SHAPES,
)
CROSS_TAP_LUG_SHAPES = tuple(
    _rect(
        (
            math.copysign(CROSS_TAP_LUG_INNER_X, x),
            math.copysign(CROSS_TAP_LUG_INNER_X + CROSS_TAP_LUG_WIDTH, x),
        ),
        (z - math.copysign(CROSS_TAP_LUG_LENGTH, z), z),
    )
    for x, z in COLUMN_SOCKET_XZ
)
for _seat in HANGING_SEATS:
    _shapes = (
        DEEP_BOSS_SHAPES
        if _seat.boss_bottom_y == DEEP_BOSS_BOTTOM_Y
        else SHALLOW_BOSS_SHAPES
    )
    for _sx, _sz in _seat.stations:
        if not any(
            (
                shape[0] == "disc"
                and math.dist((_sx, _sz), shape[1:3]) < 1e-9
                and shape[3] >= _seat.half_x
            )
            or (
                shape[0] == "rect"
                and min(_sx - shape[1], shape[2] - _sx) >= _seat.half_x - 1e-9
                and min(_sz - shape[3], shape[4] - _sz) >= _seat.half_z - 1e-9
            )
            for shape in _shapes
        ):
            raise AssertionError(
                f"{_seat.label} seat ({_sx:.2f}, {_sz:.2f}) has no hanging boss "
                "of its half-size on its level"
            )

# Every other vertical cavity keeps a full drill diameter of plan wall.
PIVOT_NEAREST_CAVITY_WALL = min(
    math.dist(PIVOT_SCREW_XZ, xz) - (PIVOT_SCREW_HOLE_DIA + dia) / 2.0
    for points, dia in (
        (HOLE_XZ, THREAD_MAJOR_MM[HOLD_DOWN_THREAD]),
        ((LOCK_KNOB_XZ,), LOCK_SCREW_HOLE_DIA),
        ((STOP_SCREW_XZ,), STOP_SCREW_HOLE_DIA),
        (BLOCK_SCREW_XZ, BLOCK_SCREW_HOLE_DIA),
        (FOOT_SCREW_XZ, FOOT_SCREW_HOLE_DIA),
        (PEDESTAL_SCREW_XZ, PEDESTAL_SCREW_HOLE_DIA),
        (NAMEPLATE_SCREW_XZ, NAMEPLATE_SCREW_HOLE_DIA),
    )
    for xz in points
)
if PIVOT_NEAREST_CAVITY_WALL < PIVOT_SCREW_HOLE_DIA:
    raise AssertionError("cone-pivot drill crowds another base cavity")

# Bounding the hold-down thread-major envelopes over their full height
# catches wall breakout rather than only tap-drill overlap.
LOCK_NEAREST_CAVITY_WALL = min(
    math.dist(LOCK_KNOB_XZ, xz) - (LOCK_SCREW_HOLE_DIA + dia) / 2.0
    for points, dia in (
        (HOLE_XZ, THREAD_MAJOR_MM[HOLD_DOWN_THREAD]),
        ((PIVOT_SCREW_XZ,), PIVOT_SCREW_HOLE_DIA),
        ((STOP_SCREW_XZ,), STOP_SCREW_HOLE_DIA),
        (BLOCK_SCREW_XZ, BLOCK_SCREW_HOLE_DIA),
        (FOOT_SCREW_XZ, FOOT_SCREW_HOLE_DIA),
        (PEDESTAL_SCREW_XZ, PEDESTAL_SCREW_HOLE_DIA),
        (NAMEPLATE_SCREW_XZ, NAMEPLATE_SCREW_HOLE_DIA),
    )
    for xz in points
)
if LOCK_NEAREST_CAVITY_WALL < LOCK_SCREW_HOLE_DIA:
    raise AssertionError("cone-lock drill crowds another base cavity")

STOP_NEAREST_CAVITY_WALL = min(
    math.dist(STOP_SCREW_XZ, xz) - (STOP_SCREW_HOLE_DIA + dia) / 2.0
    for points, dia in (
        (HOLE_XZ, THREAD_MAJOR_MM[HOLD_DOWN_THREAD]),
        ((PIVOT_SCREW_XZ,), PIVOT_SCREW_HOLE_DIA),
        ((LOCK_KNOB_XZ,), LOCK_SCREW_HOLE_DIA),
        (BLOCK_SCREW_XZ, BLOCK_SCREW_HOLE_DIA),
        (FOOT_SCREW_XZ, FOOT_SCREW_HOLE_DIA),
        (PEDESTAL_SCREW_XZ, PEDESTAL_SCREW_HOLE_DIA),
        (NAMEPLATE_SCREW_XZ, NAMEPLATE_SCREW_HOLE_DIA),
    )
    for xz in points
)
if STOP_NEAREST_CAVITY_WALL < STOP_SCREW_HOLE_DIA:
    raise AssertionError("swing-stop drill crowds another base cavity")

# The transferred pedestal seats: every neighbouring cavity and the deck's
# edge with the seat anywhere in its fit-up envelope.
PEDESTAL_NEAREST_CAVITY_WALL = (
    min(
        math.dist(seat, xz) - (PEDESTAL_SCREW_HOLE_DIA + dia) / 2.0
        for seat in PEDESTAL_SCREW_XZ
        for points, dia in (
            (HOLE_XZ, THREAD_MAJOR_MM[HOLD_DOWN_THREAD]),
            ((PIVOT_SCREW_XZ,), PIVOT_SCREW_HOLE_DIA),
            ((LOCK_KNOB_XZ,), LOCK_SCREW_HOLE_DIA),
            ((STOP_SCREW_XZ,), STOP_SCREW_HOLE_DIA),
            (BLOCK_SCREW_XZ, BLOCK_SCREW_HOLE_DIA),
            (FOOT_SCREW_XZ, FOOT_SCREW_HOLE_DIA),
            (NAMEPLATE_SCREW_XZ, NAMEPLATE_SCREW_HOLE_DIA),
            (COLUMN_SOCKET_XZ, COLUMN_SOCKET_DIAMETER),
        )
        for xz in points
    )
    - PEDESTAL_TRANSFER_ENVELOPE
)
if PEDESTAL_NEAREST_CAVITY_WALL < PEDESTAL_SCREW_HOLE_DIA:
    raise AssertionError("a transferred pedestal seat can crowd another base cavity")
PEDESTAL_DECK_LAND = (
    min(DECK_HALF_Z - abs(z) for _x, z in PEDESTAL_SCREW_XZ)
    - PEDESTAL_SCREW_HOLE_DIA / 2.0
    - PEDESTAL_TRANSFER_XZ[1]
)
if PEDESTAL_DECK_LAND < PEDESTAL_SCREW_HOLE_DIA:
    raise AssertionError("a transferred pedestal seat can crowd the deck edge")

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


def _rounded_rect_area(length: float, width: float, corner_r: float) -> float:
    """Plan area of a length x width rectangle with corner_r plan corners."""
    return length * width - 4.0 * _fillet_section_area(corner_r)


def _disc_rect_area(
    centre: tuple[float, float],
    radius: float,
    x_span: tuple[float, float],
    z_span: tuple[float, float],
) -> float:
    """Plan area a disc shares with an axis-aligned rectangle (chord sum)."""
    cx, cz = centre
    x0, x1 = max(x_span[0], cx - radius), min(x_span[1], cx + radius)
    if x1 <= x0:
        return 0.0
    x = np.linspace(x0, x1, 20001)
    half = np.sqrt(np.clip(radius * radius - (x - cx) ** 2, 0.0, None))
    chord = np.clip(
        np.minimum(cz + half, z_span[1]) - np.maximum(cz - half, z_span[0]), 0.0, None
    )
    return float(np.trapezoid(chord, x))


def _boss_wall_fillet_area(boss_r: float, inset: float, fillet_r: float) -> float:
    """Plan area one fillet adds where a vertical boss meets a pocket wall.

    The boss centre sits ``inset`` (< boss_r) inside the wall face. With the
    centre at the origin and the face on v = inset, the polygon origin ->
    fillet centre -> wall tangent -> boss/wall corner holds the fillet's
    material plus one sector of each circle.
    """
    cu = math.sqrt((boss_r + fillet_r) ** 2 - (inset - fillet_r) ** 2)
    cv = inset - fillet_r
    wu = math.sqrt(boss_r**2 - inset**2)
    polygon = 0.5 * abs(cu * inset - cv * cu + cu * inset - inset * wu)
    boss_sector = math.atan2(inset, wu) - math.atan2(cv, cu)
    fillet_sector = math.acos(-cv / math.hypot(cu, cv))
    return polygon - 0.5 * boss_r**2 * boss_sector - 0.5 * fillet_r**2 * fillet_sector


POCKET_PLAN_AREA = 4.0 * POCKET_HALF_X * POCKET_HALF_Z
_POCKET_SPAN_X = (-POCKET_HALF_X, POCKET_HALF_X)
_POCKET_SPAN_Z = (-POCKET_HALF_Z, POCKET_HALF_Z)


def _socket_boss_pocket_areas() -> list[float]:
    """Each socket boss's plan area inside the pocket (the rest is wall)."""
    return [
        _disc_rect_area(xz, SOCKET_BOSS_DIA / 2.0, _POCKET_SPAN_X, _POCKET_SPAN_Z)
        for xz in COLUMN_SOCKET_XZ
    ]


def _pocket_fillet_areas() -> list[float]:
    """The eight boss-to-wall fillets: each socket boss meets one end wall
    and one side wall."""
    return [
        _boss_wall_fillet_area(SOCKET_BOSS_DIA / 2.0, inset, CASTING_FILLET_R)
        for x, z in COLUMN_SOCKET_XZ
        for inset in (POCKET_HALF_X - abs(x), POCKET_HALF_Z - abs(z))
    ]


def _span_overlap(a: tuple[float, float], b: tuple[float, float]) -> float:
    return max(0.0, min(a[1], b[1]) - max(a[0], b[0]))


def _clip_to_pocket(rect: PocketShape) -> PocketShape:
    _kind, x0, x1, z0, z1 = rect
    return (
        "rect",
        max(x0, -POCKET_HALF_X),
        min(x1, POCKET_HALF_X),
        max(z0, -POCKET_HALF_Z),
        min(z1, POCKET_HALF_Z),
    )


def _pocket_shape_overlap(a: PocketShape, b: PocketShape) -> float:
    """Plan area two hanging shapes share INSIDE the pocket opening."""
    if a[0] == "disc" and b[0] == "disc":
        if math.dist(a[1:3], b[1:3]) < a[3] + b[3]:
            raise AssertionError(f"round pocket bosses {a} and {b} overlap")
        return 0.0
    if a[0] == "rect" and b[0] == "rect":
        a, b = _clip_to_pocket(a), _clip_to_pocket(b)
        return _span_overlap(a[1:3], b[1:3]) * _span_overlap(a[3:5], b[3:5])
    disc, rect = (a, b) if a[0] == "disc" else (b, a)
    rect = _clip_to_pocket(rect)
    return _disc_rect_area(disc[1:3], disc[3], rect[1:3], rect[3:5])


_POCKET_SHAPE: PocketShape = ("rect", *_POCKET_SPAN_X, *_POCKET_SPAN_Z)


def hanging_volume(
    shapes: tuple[PocketShape, ...],
    earlier: tuple[PocketShape, ...],
    bottom_y: float,
) -> float:
    """Volume one hanging feature adds from ``bottom_y`` to the ceiling.

    Its in-pocket plan area less what the ``earlier`` features (all reaching
    at least as low) already fill there. Shapes of one sketch never overlap,
    and no new shape sits where two earlier ones cross (the ribs' crossing
    is the only such place, and nothing hangs there).
    """
    for i, shape in enumerate(shapes):
        for other in shapes[i + 1 :]:
            if _pocket_shape_overlap(shape, other) > 0.0:
                raise AssertionError(
                    f"one sketch's pocket shapes overlap: {shape}, {other}"
                )
    area = sum(_pocket_shape_overlap(shape, _POCKET_SHAPE) for shape in shapes) - sum(
        _pocket_shape_overlap(shape, prior) for shape in shapes for prior in earlier
    )
    return area * (POCKET_CEILING_Y - bottom_y)


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
    # The deck's flat ends where its break starts; the underside is the
    # perimeter foot inside the underside break: the flange outline less the
    # pocket opening, plus the socket bosses and pocket fillets that come
    # down flush with it. Seat openings and the stamp are well inside the band.
    deck_flat = _rounded_rect_area(
        DECK_LENGTH - 2.0 * DECK_EDGE_BREAK,
        DECK_WIDTH - 2.0 * DECK_EDGE_BREAK,
        DECK_CORNER_R - DECK_EDGE_BREAK,
    )
    foot = (
        _rounded_rect_area(
            BOTTOM_LENGTH - 2.0 * RIM_CHAMFER,
            BOTTOM_WIDTH - 2.0 * RIM_CHAMFER,
            FLANGE_CORNER_R - RIM_CHAMFER,
        )
        - POCKET_PLAN_AREA
        + sum(_socket_boss_pocket_areas())
        + sum(_pocket_fillet_areas())
    )
    expected_areas = {
        "deck": deck_flat * 1e-6,
        "underside": foot * 1e-6,
        "flange_west": flange_end_width * flange_side_height * 1e-6,
        "flange_east": flange_end_width * flange_side_height * 1e-6,
        "flange_rear": flange_face_width * flange_side_height * 1e-6,
        "flange_front": flange_face_width * flange_side_height * 1e-6,
    }
    # Each socket bore wall loses two small windows where the cross tap passes
    # through it (~1.3% of the cylinder), well inside the 5% band below.
    expected_areas.update(
        {
            control.key: math.pi * COLUMN_SOCKET_DIAMETER * COLUMN_SOCKET_DEPTH * 1e-6
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
            _telemetry.info(
                f"{key} face qualified ({area * 1e6:.0f} mm^2), body colour"
            )
            continue
        face.MaterialPropertyValues = values
        back = tuple(float(value) for value in (face.MaterialPropertyValues or ())[:3])
        if len(back) != 3 or any(
            abs(actual - wanted) > 1 / 255 for actual, wanted in zip(back, PANEL_BLACK)
        ):
            raise RuntimeError(f"{key} black face colour did not persist: {back}")
        _telemetry.info(f"{key} face painted black ({area * 1e6:.0f} mm^2)")


REFERENCE_SKETCHES = ("HeightReference", "CrossTapReference")


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
    await set_global(adapter, "DeckRise", f"{DECK_RISE}mm")
    await set_global(adapter, "DeckLength", f"{DECK_LENGTH}mm")
    await set_global(adapter, "DeckWidth", f"{DECK_WIDTH}mm")
    await set_global(adapter, "PocketWall", f"{POCKET_WALL}mm")
    await set_global(adapter, "PocketSkin", f"{STACK_HEIGHT - POCKET_CEILING_Y}mm")
    await set_global(
        adapter, "PocketDepth", '"BottomThickness" + "TopThickness" - "PocketSkin"'
    )
    await set_global(adapter, "RibThickness", f"{RIB_THICKNESS}mm")
    await set_global(adapter, "RibRelief", f"{RIB_RELIEF}mm")
    await set_global(adapter, "SocketBossDia", f"{SOCKET_BOSS_DIA}mm")
    await set_global(adapter, "HangingBossDia", f"{HANGING_BOSS_DIA}mm")
    await set_global(adapter, "DeepBossBottom", f"{DEEP_BOSS_BOTTOM_Y}mm")
    await set_global(adapter, "ShallowBossBottom", f"{SHALLOW_BOSS_BOTTOM_Y}mm")
    await set_global(adapter, "BlockPadLength", f"{BLOCK_PAD_LENGTH}mm")
    await set_global(adapter, "PedestalPadLength", f"{PEDESTAL_PAD_LENGTH}mm")
    await set_global(adapter, "LugWidth", f"{CROSS_TAP_LUG_WIDTH}mm")
    await set_global(adapter, "LugLength", f"{CROSS_TAP_LUG_LENGTH}mm")
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
    # The pad stops at the green land; the deck rises from it below.
    extrude_at_offset(adapter, GREEN_TOP - BOTTOM_THICKNESS, BOTTOM_THICKNESS)
    name_last_feature(adapter, "TopPlate")
    pad_height_dim = name_dimensions(adapter, "TopPlate", ["PadHeight"])
    _verify_named_dimension(adapter, "PadHeight@TopPlate", GREEN_TOP - BOTTOM_THICKNESS)
    drive_jobs.append((pad_height_dim[0], '"TopThickness" - "DeckRise"'))
    after = await _volume(adapter)
    _telemetry.info(f"volume after top plate: {after:.1f} mm^3")

    # Black deck (user ruling 2026-10-09, see DECK_RISE): a DECK_LENGTH x
    # DECK_WIDTH pad centred on the pad, boss-extruded from the green land so
    # its depth dimension IS the printed rise. Every deck seat is cut after it,
    # so each starts on the deck face.
    deck = SketchDims()
    check("create_sketch deck", await adapter.create_sketch("Top"))
    await _define_fixed_edge_rectangle(
        adapter,
        half_x=DECK_HALF_X,
        front_z=-DECK_HALF_Z,
        rear_z=DECK_HALF_Z,
        label="deck",
        dims=deck,
        width_name="DeckLen",
        depth_name="DeckWid",
        width_drive='"DeckLength"',
        depth_drive='"DeckWidth"',
        half_x_drive='"DeckLength" / 2',
        rear_z_drive='"DeckWidth" / 2',
    )
    await ensure_fully_defined(adapter, "deck sketch")
    check("exit_sketch deck", await adapter.exit_sketch())
    name_last_feature(adapter, "DeckProfile")
    drive_jobs += deck.apply(adapter, "DeckProfile")
    extrude_at_offset(adapter, DECK_RISE, GREEN_TOP)
    name_last_feature(adapter, "Deck")
    deck_dims = name_dimensions(adapter, "Deck", ["DeckRise", "DeckStart"])
    _verify_named_dimension(adapter, "DeckRise@Deck", DECK_RISE)
    _verify_named_dimension(adapter, "DeckStart@Deck", GREEN_TOP)
    drive_jobs += [
        (deck_dims[0], '"DeckRise"'),
        (deck_dims[1], '"BottomThickness" + "TopThickness" - "DeckRise"'),
    ]
    v_deck = DECK_LENGTH * DECK_WIDTH * DECK_RISE
    after = await volume_check(adapter, "deck", after + v_deck, 0.002 * v_deck + 5.0)
    total = STACK_HEIGHT

    # Underside pocket (same ruling, see POCKET_WALL): one cored pocket cut up
    # from the underside to the ceiling, then the bosses, ribs and lugs grown
    # back down into it from the ceiling, deepest-reaching first. All of it
    # precedes the seats, so every hole still cuts solid metal and keeps its
    # analytic volume. Each hanging feature's volume is its in-pocket plan
    # area (hanging_volume) over its height.
    pocket = SketchDims()
    check("create_sketch pocket", await adapter.create_sketch("Top"))
    await _define_fixed_edge_rectangle(
        adapter,
        half_x=POCKET_HALF_X,
        front_z=-POCKET_HALF_Z,
        rear_z=POCKET_HALF_Z,
        label="pocket",
        dims=pocket,
        width_name="PocketLen",
        depth_name="PocketWid",
        width_drive='"TopLength" - 2 * "PocketWall"',
        depth_drive='"TopWidth" - 2 * "PocketWall"',
        half_x_drive='"TopLength" / 2 - "PocketWall"',
        rear_z_drive='"TopWidth" / 2 - "PocketWall"',
    )
    await ensure_fully_defined(adapter, "pocket sketch")
    check("exit_sketch pocket", await adapter.exit_sketch())
    name_last_feature(adapter, "PocketProfile")
    drive_jobs += pocket.apply(adapter, "PocketProfile")
    # The Top plane IS the underside, so the cut runs up (+Y) into the part.
    check(
        "cut underside pocket",
        await adapter.create_cut_extrude(
            ExtrusionParameters(depth=POCKET_CEILING_Y, reverse_direction=True)
        ),
    )
    name_last_feature(adapter, "Pocket")
    pocket_depth_dim = name_dimensions(adapter, "Pocket", ["PocketDepth"])
    _verify_named_dimension(adapter, "PocketDepth@Pocket", POCKET_CEILING_Y)
    drive_jobs.append((pocket_depth_dim[0], '"PocketDepth"'))
    v_pocket = POCKET_PLAN_AREA * POCKET_CEILING_Y
    after = await volume_check(
        adapter, "underside pocket", after - v_pocket, 0.002 * v_pocket + 10.0
    )

    # Full-height bosses round the four sockets, merged into the walls; each
    # swallows a pocket corner, so the pocket needs no plan-corner radius.
    socket_bosses = SketchDims()
    check("create_sketch socket bosses", await adapter.create_sketch("Top"))
    for i, (x, z) in enumerate(COLUMN_SOCKET_XZ):
        await define_circle(
            adapter,
            x,
            -z,
            SOCKET_BOSS_DIA / 2.0,
            f"socket boss ({x:+.0f}, {z:+.0f})",
            dims=socket_bosses,
            names=(
                f"SocketBoss{i}X",
                f"SocketBoss{i}Z",
                "SocketBossDia" if i == 0 else f"SocketBoss{i}Dia",
            ),
            drives=('"ColumnX"', '"ColumnZ"', '"SocketBossDia"'),
        )
    await ensure_fully_defined(adapter, "socket boss sketch")
    check("exit_sketch socket bosses", await adapter.exit_sketch())
    name_last_feature(adapter, "SocketBossProfile")
    drive_jobs += socket_bosses.apply(adapter, "SocketBossProfile")
    check(
        "extrude socket bosses",
        await adapter.create_extrusion(ExtrusionParameters(depth=POCKET_CEILING_Y)),
    )
    name_last_feature(adapter, "SocketBosses")
    boss_height_dim = name_dimensions(adapter, "SocketBosses", ["SocketBossHeight"])
    drive_jobs.append((boss_height_dim[0], '"PocketDepth"'))
    hung: tuple[PocketShape, ...] = ()
    v_hang = hanging_volume(SOCKET_BOSS_SHAPES, hung, 0.0)
    hung += SOCKET_BOSS_SHAPES
    after = await volume_check(
        adapter, "socket bosses", after + v_hang, 0.005 * v_hang + 10.0
    )

    # Two ribs on the centre lines, RIB_RELIEF clear of the bench and ending
    # mid-wall. Each is an offset-start boss, so its start offset IS the relief.
    for tag, rib_shape, label, half_x, half_z, names, drives in (
        (
            "LongRib",
            LONG_RIB_SHAPE,
            "long rib (z = 0)",
            RIB_HALF_LENGTH_X,
            RIB_THICKNESS / 2.0,
            ("LongRibLength", "LongRibThickness"),
            ('"TopLength" - "PocketWall"', '"RibThickness"'),
        ),
        (
            "CrossRib",
            CROSS_RIB_SHAPE,
            "cross rib (x = 0)",
            RIB_THICKNESS / 2.0,
            RIB_HALF_LENGTH_Z,
            ("CrossRibThickness", "CrossRibLength"),
            ('"RibThickness"', '"TopWidth" - "PocketWall"'),
        ),
    ):
        rib = SketchDims()
        check(f"create_sketch {label}", await adapter.create_sketch("Top"))
        # A line chain, not define_centered_rectangle: that native center
        # rectangle runs sketch inference, and the cross rib's 131.25 ends
        # snapped to the deck edges at 130.25 seen through the Top plane
        # (farm leaf 2026-10-10: depth read back 260.5, the dimension became
        # driven, and the CrossRibLength equation failed the rebuild).
        points = [
            (-half_x, -half_z),
            (half_x, -half_z),
            (half_x, half_z),
            (-half_x, half_z),
        ]
        lines = await add_line_chain(adapter, points)
        await define_rectilinear_chain(
            adapter,
            lines,
            points,
            label=label,
            dims=rib,
            names=[*names, *(f"{n}Half" for n in names)],
            # Anchor dims (x, z) hold the rib centred as its spans change.
            drives=[*drives, *(f"({d}) / 2" for d in drives)],
        )
        await ensure_fully_defined(adapter, f"{label} sketch")
        check(f"exit_sketch {label}", await adapter.exit_sketch())
        name_last_feature(adapter, f"{tag}Profile")
        drive_jobs += rib.apply(adapter, f"{tag}Profile")
        extrude_at_offset(adapter, POCKET_CEILING_Y - RIB_RELIEF, RIB_RELIEF)
        name_last_feature(adapter, tag)
        # The sheet's section B-B cuts at constant x and so slices the LONG
        # rib: that rib carries the printed RibRelief.
        relief_name = "RibRelief" if tag == "LongRib" else f"{tag}Relief"
        rib_dims = name_dimensions(adapter, tag, [f"{tag}Height", relief_name])
        _verify_named_dimension(
            adapter, f"{tag}Height@{tag}", POCKET_CEILING_Y - RIB_RELIEF
        )
        _verify_named_dimension(adapter, f"{relief_name}@{tag}", RIB_RELIEF)
        drive_jobs += [
            (rib_dims[0], '"PocketDepth" - "RibRelief"'),
            (rib_dims[1], '"RibRelief"'),
        ]
        v_hang = hanging_volume((rib_shape,), hung, RIB_RELIEF)
        hung += (rib_shape,)
        after = await volume_check(
            adapter, label, after + v_hang, 0.005 * v_hang + 10.0
        )

    # Hanging bosses under the blind deck seats and the lugs under the cross
    # taps (HANGING_SEATS, CROSS_TAP_LUG_SHAPES): one sketch per cast level.
    #
    # The rect pads and the lugs stand under seats the hole table does not
    # locate (transfer seats) or under cross taps, so the drawing places them
    # from the table's own X0 Y0: the flange's rear-west theoretical sharp
    # corner, one datum per view (drawing policy rule 7). Each sketch carries
    # that corner as a point, and every such feature is dimensioned FROM it,
    # so the printed locations are these sketches' own driving dims (Codex P2
    # on #1310: the pads printed no size or place).
    async def _table_origin(dims: SketchDims, tag: str) -> str:
        """Add and anchor this sketch's X0 Y0 point; return its entity id."""
        manager = adapter.currentSketchManager
        previous = bool(manager.AddToDB)
        # Inference would snap the point onto the flange profile's corner,
        # adding a relation that over-defines the anchor dims below.
        manager.AddToDB = True
        try:
            raw = manager.CreatePoint(
                -BOTTOM_LENGTH / 2000.0, -BOTTOM_WIDTH / 2000.0, 0.0
            )
        finally:
            manager.AddToDB = previous
        if raw is None:
            raise RuntimeError(f"{tag}: X0 Y0 point creation failed")
        origin = adapter._register_sketch_entity("Point", raw)
        await anchor_point_to_origin(
            adapter, origin, -BOTTOM_LENGTH / 2.0, -BOTTOM_WIDTH / 2.0, f"{tag} X0 Y0"
        )
        dims.record(f"{tag}OriginX", '"BottomLength" / 2')
        dims.record(f"{tag}OriginY", '"BottomWidth" / 2')
        return origin

    def _from_origin(x: float, sketch_y: float) -> tuple[float, float]:
        """Hole-table (X, Y) of a Top-plane sketch point (sketch y = -z)."""
        return x + BOTTOM_LENGTH / 2.0, sketch_y + BOTTOM_WIDTH / 2.0

    async def _pad(
        dims: SketchDims,
        shape: PocketShape,
        label: str,
        names: list[str | None],
        drives: list[str | None],
        *,
        origin: str,
        location: tuple[str, str],
        corner: int = 0,
        sizes: tuple[int, int] = (0, 1),
    ) -> None:
        """Sketch one rect shape: x size on line ``sizes[0]``, then z size on
        line ``sizes[1]`` (each the side the drawing can see), then vertex
        ``corner`` (default the NW one, nearest X0 Y0) at its table X and Y."""
        _kind, x0, x1, z0, z1 = shape
        points = [(x0, -z1), (x1, -z1), (x1, -z0), (x0, -z0)]
        lines = await add_line_chain(adapter, points)
        directions = ("horizontal", "vertical", "horizontal", "vertical")
        for line, direction in zip(lines, directions, strict=True):
            check(
                f"{label} {direction} {line}",
                await adapter.add_sketch_constraint(line, None, direction),
            )
        # One size per direction; H/V and closure supply the other two sides.
        for line, kind, span, name, drive in (
            (lines[sizes[0]], "horizontal_distance", x1 - x0, names[0], drives[0]),
            (lines[sizes[1]], "vertical_distance", z1 - z0, names[1], drives[1]),
        ):
            await dimension_between(
                adapter, f"{line}.start", f"{line}.end", kind, span, f"{label} {line}"
            )
            dims.record(name, drive)
        await anchor_point_to_point(
            adapter,
            origin,
            f"{lines[corner]}.start",
            *_from_origin(*points[corner]),
            f"{label} from X0 Y0",
        )
        dims.record(location[0])
        dims.record(location[1])

    async def _hanging_feature(
        tag: str,
        profile: str,
        shapes: tuple[PocketShape, ...],
        bottom_y: float,
        bottom_name: str,
        bottom_drive: str,
        sketch_shapes,
    ) -> float:
        sketch = SketchDims()
        check(f"create_sketch {tag}", await adapter.create_sketch("Top"))
        await sketch_shapes(sketch)
        await ensure_fully_defined(adapter, f"{tag} sketch")
        check(f"exit_sketch {tag}", await adapter.exit_sketch())
        name_last_feature(adapter, profile)
        drive_jobs.extend(sketch.apply(adapter, profile))
        extrude_at_offset(adapter, POCKET_CEILING_Y - bottom_y, bottom_y)
        name_last_feature(adapter, tag)
        dims = name_dimensions(adapter, tag, [f"{tag}Height", bottom_name])
        _verify_named_dimension(
            adapter, f"{tag}Height@{tag}", POCKET_CEILING_Y - bottom_y
        )
        _verify_named_dimension(adapter, f"{bottom_name}@{tag}", bottom_y)
        drive_jobs.extend(
            [
                (dims[0], f'"PocketDepth" - "{bottom_drive}"'),
                (dims[1], f'"{bottom_drive}"'),
            ]
        )
        nonlocal hung
        volume = hanging_volume(shapes, hung, bottom_y)
        hung += shapes
        return volume

    async def _deep_sketch(sketch: SketchDims) -> None:
        origin = await _table_origin(sketch, "DeepBoss")
        for i, (x, z) in enumerate(DEEP_BOSS_CENTRES):
            await define_circle(
                adapter,
                x,
                -z,
                HANGING_BOSS_HALF,
                f"deep boss ({x:+.1f}, {z:+.1f})",
                dims=sketch,
                names=(
                    f"DeepBoss{i}X",
                    f"DeepBoss{i}Z",
                    "HangingBossDia" if i == 0 else f"DeepBoss{i}Dia",
                ),
                drives=(None, None, '"HangingBossDia"'),
            )
        await _pad(
            sketch,
            LOCK_PAD_SHAPE,
            "cone-lock pad",
            ["LockPadWidth", "LockPadLength"],
            ['"HangingBossDia"', None],
            origin=origin,
            location=("LockPadX", "LockPadY"),
        )
        for i, shape in enumerate(PEDESTAL_PAD_SHAPES):
            await _pad(
                sketch,
                shape,
                f"pedestal pad {i}",
                [
                    f"PedestalPad{i}Width",
                    "PedestalPadLength" if i == 0 else f"PedestalPad{i}Length",
                ],
                ['"HangingBossDia"', '"PedestalPadLength"'],
                origin=origin,
                location=(f"PedestalPad{i}X", f"PedestalPad{i}Y"),
                # The front edge and the west side: the lock pad's end and
                # the front block pad's Y line keep the others' air.
                sizes=(2, 3),
            )

    v_hang = await _hanging_feature(
        "DeepBosses",
        "DeepBossProfile",
        DEEP_BOSS_SHAPES,
        DEEP_BOSS_BOTTOM_Y,
        "DeepBossBottom",
        "DeepBossBottom",
        _deep_sketch,
    )
    after = await volume_check(
        adapter, "deep bosses", after + v_hang, 0.005 * v_hang + 10.0
    )

    async def _shallow_sketch(sketch: SketchDims) -> None:
        origin = await _table_origin(sketch, "ShallowBoss")
        for i, (x, z) in enumerate(SHALLOW_BOSS_CENTRES):
            await define_circle(
                adapter,
                x,
                -z,
                HANGING_BOSS_HALF,
                f"shallow boss ({x:+.1f}, {z:+.1f})",
                dims=sketch,
                names=(f"ShallowBoss{i}X", f"ShallowBoss{i}Z", f"ShallowBoss{i}Dia"),
                drives=(None, None, '"HangingBossDia"'),
            )
        for i, shape in enumerate(BLOCK_PAD_SHAPES):
            await _pad(
                sketch,
                shape,
                f"pinion-block pad {i}",
                [
                    "BlockPadLength" if i == 0 else f"BlockPad{i}Length",
                    f"BlockPad{i}Width",
                ],
                ['"BlockPadLength"', '"HangingBossDia"'],
                origin=origin,
                location=(f"BlockPad{i}X", f"BlockPad{i}Y"),
                # The front pad's Y from its front edge: its back edge lies
                # 0.4 from the front pedestal pad's. The width on the west
                # side, the east end standing in the cross rib.
                corner=3 if i == 0 else 0,
                sizes=(0, 3),
            )

    v_hang = await _hanging_feature(
        "ShallowBosses",
        "ShallowBossProfile",
        SHALLOW_BOSS_SHAPES,
        SHALLOW_BOSS_BOTTOM_Y,
        "ShallowBossBottom",
        "ShallowBossBottom",
        _shallow_sketch,
    )
    after = await volume_check(
        adapter, "shallow bosses", after + v_hang, 0.005 * v_hang + 10.0
    )

    async def _lug_sketch(sketch: SketchDims) -> None:
        origin = await _table_origin(sketch, "Lug")
        for i, shape in enumerate(CROSS_TAP_LUG_SHAPES):
            _kind, x0, x1, z0, z1 = shape
            points = [(x0, -z1), (x1, -z1), (x1, -z0), (x0, -z0)]
            # A lug's outer end and outer side merge into the wall and the
            # socket boss; only its inner corner stands in the open pocket.
            inner = min(range(4), key=lambda k: (abs(points[k][0]), abs(points[k][1])))
            await _pad(
                sketch,
                shape,
                f"cross-tap lug {i}",
                [
                    "LugWidth" if i == 0 else f"Lug{i}Width",
                    "LugLength" if i == 0 else f"Lug{i}Length",
                ],
                ['"LugWidth"', '"LugLength"'],
                origin=origin,
                location=(f"Lug{i}X", f"Lug{i}Y"),
                corner=inner,
            )

    v_hang = await _hanging_feature(
        "CrossTapLugs",
        "CrossTapLugProfile",
        CROSS_TAP_LUG_SHAPES,
        SHALLOW_BOSS_BOTTOM_Y,
        "LugBottom",
        "ShallowBossBottom",
        _lug_sketch,
    )
    after = await volume_check(
        adapter, "cross-tap lugs", after + v_hang, 0.005 * v_hang + 10.0
    )

    # Casting fillets on the eight socket-boss-to-wall junctions (the
    # pocket's only reentrant vertical edges that run to the underside). The
    # end-wall junctions run up only to the lug bottom, the lug covering them
    # above; the side-wall junctions run the full pocket depth.
    boss_r = SOCKET_BOSS_DIA / 2.0
    fillet_picks: list[list[float]] = []
    fillet_heights: list[float] = []
    for x, z in COLUMN_SOCKET_XZ:
        sx, sz = math.copysign(1.0, x), math.copysign(1.0, z)
        end_inset = POCKET_HALF_X - abs(x)
        side_inset = POCKET_HALF_Z - abs(z)
        fillet_picks += [
            [
                sx * POCKET_HALF_X,
                SHALLOW_BOSS_BOTTOM_Y / 2.0,
                z - sz * math.sqrt(boss_r**2 - end_inset**2),
            ],
            [
                x - sx * math.sqrt(boss_r**2 - side_inset**2),
                POCKET_CEILING_Y / 2.0,
                sz * POCKET_HALF_Z,
            ],
        ]
        fillet_heights += [SHALLOW_BOSS_BOTTOM_Y, POCKET_CEILING_Y]
    check(
        "fillet pocket boss junctions",
        await adapter.add_fillet(CASTING_FILLET_R, fillet_picks, propagate=False),
    )
    name_last_feature(adapter, "PocketFillets")
    name_dimensions(adapter, "PocketFillets", ["PocketFilletRadius"])
    v_fillets = sum(
        area * height
        for area, height in zip(_pocket_fillet_areas(), fillet_heights, strict=True)
    )
    after = await volume_check(
        adapter, "pocket fillets", after + v_fillets, 0.05 * v_fillets + 5.0
    )

    # Four blind native 1/4-20 UNC-2B seats from the support deck. The screws
    # bear on their vendor-modeled under-head washer faces and pass through
    # the support's 5/16 clearance drills: 6.35 mm foot + 12.422187 mm (1.956D)
    # engagement, sized at the printed band's worst case (HOLD_DOWN_THREAD_DEPTH,
    # HOLD_DOWN_DRILL_DEPTH) with a five-pitch plug-tap lead past the thread.
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
    # includes cylinder plus point. Every seat, the nameplate's included,
    # stands on the raised deck, so each is cut from the deck face (y =
    # STACK_HEIGHT) into the boss hanging under it.
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
            f"swing-stop tapped seat ({STOP_THREAD})",
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
            "foot-screw bottoming-tapped seat (#4-40)",
        ),
        (
            "PedestalSeats",
            PEDESTAL_SEAT_SPEC,
            PEDESTAL_SCREW_XZ,
            "arbor-pedestal hold-down bottoming-tapped seats (#8-32)",
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

    # Four blind column sockets from the green land beside the deck, nominal
    # Ø25.50: production bores are matched to their assigned actual MHA-FR-003
    # tubes, so the drawing prints the size as reference only. Each bottoms
    # inside its full-height socket boss.
    socket_plane = check(
        "create_plane column socket mouths",
        await adapter.create_plane(
            CreatePlaneParameters(
                mode="offset", base_plane="Top Plane", offset=GREEN_TOP
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

    # Plan corners: one full-height radius per plate. The pad FIRST (one side
    # face, so one edge from the flange top to the green land) at
    # PAD_CORNER_R, then the flange's four vertical corner edges at the
    # concentric FLANGE_CORNER_R -- in that order: the flange arc passes 0.19
    # inside the pad's square corner, so filleting the flange while the pad
    # corner is still square has to cut the pad and SolidWorks refuses
    # ("Failed to create fillet", seat build); rounded first, the pad corner
    # sits 6.35 inside the flange arc. Then the deck's four corners at
    # DECK_CORNER_R (the photographed panel reads round-cornered).
    check(
        "fillet pad plan corners",
        await adapter.add_fillet(
            PAD_CORNER_R,
            [
                [
                    sx * TOP_LENGTH / 2.0,
                    (BOTTOM_THICKNESS + GREEN_TOP) / 2.0,
                    sz * TOP_WIDTH / 2.0,
                ]
                for sx in (-1.0, 1.0)
                for sz in (-1.0, 1.0)
            ],
        ),
    )
    name_last_feature(adapter, "PadCorners")
    name_dimensions(adapter, "PadCorners", ["PadCornerRadius"])
    v_pad_corners = _corner_removal(PAD_CORNER_R, GREEN_TOP - BOTTOM_THICKNESS)
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
        "fillet deck plan corners",
        await adapter.add_fillet(
            DECK_CORNER_R,
            [
                [sx * DECK_HALF_X, GREEN_TOP + DECK_RISE / 2.0, sz * DECK_HALF_Z]
                for sx in (-1.0, 1.0)
                for sz in (-1.0, 1.0)
            ],
        ),
    )
    name_last_feature(adapter, "DeckCorners")
    name_dimensions(adapter, "DeckCorners", ["DeckCornerRadius"])
    v_deck_corners = _corner_removal(DECK_CORNER_R, DECK_RISE)
    after = await volume_check(
        adapter,
        "deck plan corners",
        after - v_deck_corners,
        0.02 * v_deck_corners + 2.0,
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
    # pad's outer edge round the green land.
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
            + _rim_points(TOP_LENGTH / 2.0, GREEN_TOP, TOP_WIDTH / 2.0, PAD_CORNER_R),
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

    # Deck edge: a 1/32 in x 45-degree break round the deck's top loop, half
    # the plates' rim break, so most of the DECK_RISE step stays square.
    check(
        "chamfer deck edge",
        await adapter.add_chamfer(
            DECK_EDGE_BREAK,
            _rim_points(DECK_HALF_X, STACK_HEIGHT, DECK_HALF_Z, DECK_CORNER_R),
        ),
    )
    name_last_feature(adapter, "DeckEdgeBreak")
    name_dimensions(adapter, "DeckEdgeBreak", ["DeckEdgeChamfer"])
    v_deck_break = (
        DECK_EDGE_BREAK**2
        / 2.0
        * _plan_perimeter(DECK_LENGTH, DECK_WIDTH, DECK_CORNER_R)
    )
    after = await volume_check(
        adapter, "deck edge break", after - v_deck_break, 0.02 * v_deck_break + 2.0
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

    # Stamped serial "2" in the deck's NW corner: import the closed-region DXF
    # onto a plane at the deck top (STACK_HEIGHT) and cut it mid-plane both
    # ways (the up side cuts air), removing net-area x SERIAL_DEPTH -- bounded
    # like the nameplate engraving (no closed form for the traced glyph).
    if not SERIAL_DXF.is_file():
        raise RuntimeError(f"serial DXF not found: {SERIAL_DXF}")
    serial_plane = check(
        "create_plane deck top",
        await adapter.create_plane(
            CreatePlaneParameters(
                mode="offset", base_plane="Top Plane", offset=STACK_HEIGHT
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

    # REFERENCE sketches. The flange-to-deck height is a manufacturing value
    # the sheet prints, so policy rule 2 says the model owns it -- but it is
    # no feature's dimension: the 38.1 spans three features. It therefore
    # gets a hidden one-line sketch whose single driving dimension IS the
    # value, marked for drawing like any other. The line is construction and
    # BLANKED once built:
    # shown, the height line stood as a tick with two endpoint dots on the
    # base's end face in every assembly render (top iso, asm round d60107b3).
    # A blanked sketch's dimensions never reach a plain InsertModelAnnotations3
    # (the first build failed with "geometry top view is missing model
    # dimensions: ['RimWidth']"), so draw_fr_harmonic_base imports them through
    # _drawing_hidden_sketches.curate_view_dimensions, which shows each owner
    # sketch in its own view only. The pocket wall needs no such sketch: the
    # sheet prints the pocket's own PocketLen/PocketWid in the bottom view.

    # On the left silhouette (x = -BOTTOM_LENGTH/2), where the front view's
    # flange-to-deck dimension has always drawn its witness lines.
    check("create_sketch height reference", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    height_ref = check(
        "flange-to-deck reference line",
        await adapter.add_line(
            -BOTTOM_LENGTH / 2.0, BOTTOM_THICKNESS, -BOTTOM_LENGTH / 2.0, STACK_HEIGHT
        ),
    )
    set_sketch_direct_db(adapter, False)
    _as_construction(adapter, height_ref)
    check(
        "flange-to-deck reference vertical",
        await adapter.add_sketch_constraint(height_ref, None, "vertical"),
    )
    await dimension_between(
        adapter,
        f"{height_ref}.start",
        f"{height_ref}.end",
        "vertical_distance",
        TOP_THICKNESS,
        "flange-to-deck reference",
    )
    await anchor_point_to_origin(
        adapter,
        f"{height_ref}.start",
        -BOTTOM_LENGTH / 2.0,
        BOTTOM_THICKNESS,
        "flange-to-deck reference",
    )
    await ensure_fully_defined(adapter, "flange-to-deck reference sketch")
    check("exit_sketch height reference", await adapter.exit_sketch())
    name_last_feature(adapter, "HeightReference")
    name_dimensions(adapter, "HeightReference", ["FlangeToDeck"])
    _verify_named_dimension(adapter, "FlangeToDeck@HeightReference", TOP_THICKNESS)

    # The cross-tap X stations, chained from the flange's west face (the hole
    # table's X0) to the first tap and on to the second, along the tap axis.
    # The taps share their X with the A1-A4 bores, but the table locates only
    # the bores, and "ON A1-A4 X CENTRES" in the tap callout was a location
    # in a note (hb-render-4 eye pass). Chained, not baselined: the front
    # view has one free dimension row beneath it.
    check("create_sketch cross-tap reference", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    tap_edge_ref = check(
        "cross-tap edge reference line",
        await adapter.add_line(
            -BOTTOM_LENGTH / 2.0, BASE_SCREW_Y, -COLUMN_X, BASE_SCREW_Y
        ),
    )
    tap_pitch_ref = check(
        "cross-tap pitch reference line",
        await adapter.add_line(-COLUMN_X, BASE_SCREW_Y, COLUMN_X, BASE_SCREW_Y),
    )
    set_sketch_direct_db(adapter, False)
    for line in (tap_edge_ref, tap_pitch_ref):
        _as_construction(adapter, line)
        check(
            f"cross-tap reference {line} horizontal",
            await adapter.add_sketch_constraint(line, None, "horizontal"),
        )
    check(
        "cross-tap reference chain",
        await adapter.add_sketch_constraint(
            f"{tap_edge_ref}.end", f"{tap_pitch_ref}.start", "coincident"
        ),
    )
    await dimension_between(
        adapter,
        f"{tap_edge_ref}.start",
        f"{tap_edge_ref}.end",
        "horizontal_distance",
        BOTTOM_LENGTH / 2.0 - COLUMN_X,
        "cross-tap X from flange edge",
    )
    await dimension_between(
        adapter,
        f"{tap_pitch_ref}.start",
        f"{tap_pitch_ref}.end",
        "horizontal_distance",
        2.0 * COLUMN_X,
        "cross-tap pitch",
    )
    await anchor_point_to_origin(
        adapter,
        f"{tap_edge_ref}.start",
        -BOTTOM_LENGTH / 2.0,
        BASE_SCREW_Y,
        "cross-tap reference",
    )
    await ensure_fully_defined(adapter, "cross-tap reference sketch")
    check("exit_sketch cross-tap reference", await adapter.exit_sketch())
    name_last_feature(adapter, "CrossTapReference")
    name_dimensions(adapter, "CrossTapReference", ["CrossTapX", "CrossTapPitch"])
    _verify_named_dimension(
        adapter, "CrossTapX@CrossTapReference", BOTTOM_LENGTH / 2.0 - COLUMN_X
    )
    _verify_named_dimension(adapter, "CrossTapPitch@CrossTapReference", 2.0 * COLUMN_X)
    blank_reference_sketches(adapter, REFERENCE_SKETCHES)
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
        adapter,
        "BaseSpotFaceRear",
        "SpotFaceDepth",
        *deviations(SPOTFACE_DEPTH_BAND_MM),
    )
    # A pair's shared size or coordinate prints once, as "2X": the count is
    # specification, so the part owns it like the places.
    for (feature_name, dimension_name), prefix in UNDERSIDE_PAD_PREFIXES.items():
        set_dimension_prefix(adapter, feature_name, dimension_name, prefix)
    author_part_pmi(adapter, surface_finishes=PART_SURFACE_FINISHES)
    apply_drawing_properties(adapter, PART_NAME)
    return await _save_with_annotation_free_render(adapter)


_SW_DISPLAY_ANNOTATIONS = 31  # swUserPreferenceToggle_e.swDisplayAnnotations
_SW_DETAILING_NO_OPTION = 0  # swUserPreferenceOption_e.swDetailingNoOptionSpecified


async def _save_with_annotation_free_render(adapter) -> dict[str, str]:
    """Save the part, then render its isometric with model annotations hidden.

    The part-owned surface-finish PMI is model annotation, so the isometric
    showed "A1-A4 BORES Ra 3.2" and "FLANGE EDGES, 4 SIDES" floating in 3D over
    the casting. The part is saved first with its annotations shown; only the
    image hides them, and the teardown closes the document without saving, so
    the display toggle never reaches the .SLDPRT the drawing reads.
    """
    artefacts = await save_part_and_images(adapter, PART_NAME, views=())
    model = _early_bound(adapter.currentModel, "IModelDoc2")
    extension = _early_bound(model.Extension, "IModelDocExtension")
    toggle = (_SW_DISPLAY_ANNOTATIONS, _SW_DETAILING_NO_OPTION)
    extension.SetUserPreferenceToggle(*toggle, False)
    if extension.GetUserPreferenceToggle(*toggle):
        raise RuntimeError("harmonic-base render: model annotations are still displayed")
    image = (OUT_PNG / PART_NAME / f"{PART_NAME}_isometric.png").resolve()
    check(
        "export_image isometric (annotations hidden)",
        await adapter.export_image(
            {
                "file_path": str(image),
                "format_type": "png",
                "width": 1600,
                "height": 1000,
                "view_orientation": "isometric",
            }
        ),
    )
    artefacts["isometric"] = str(image)
    return artefacts


if __name__ == "__main__":
    sys.exit(run_build(build))
