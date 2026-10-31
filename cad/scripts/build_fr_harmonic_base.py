r"""Reproduction script: harmonic analyzer base (book ch. 6 / legacy part).

The native part is the stepped, raised-rim gray-iron base defined by
``fr_harmonic_base_spec``. Its flange, pad and deck share centred X/Z axes;
the column sockets set the pad width and its finished deck lands.

Top-face seats include the cone-swing pivot/lock/stop taps, the parked
pinion-rig block and spring-foot taps, the fitted arbor-pedestal seats,
and the maker's nameplate taps. The live cone line, parked rig, cylinder
bank and plate mount transform own those stations: no former gear-train
world coordinates are copied into the native Hole Wizard cuts.

Black deck and underside pocket (user ruling 2026-10-09, ch30 p002/p003/p006
and ch26 p.71 photos): the black panel is a machined pad DECK_RISE proud of
the green casting top, which carries the four column sockets on its land;
underneath, one cored pocket inside a perimeter wall, crossed by two relieved
ribs, full-height socket bosses and the retained frame cross-tap lugs.

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

import numpy as np

from _appearance import CASTING_GREEN, PANEL_BLACK, apply_color, apply_material
from _check import check
from _com import _early_bound
from _document_units import apply_package_model_units
from _dimensions import drive_dimension, name_dimensions, set_global
from _extrude import extrude_at_offset
from _feature_tree import name_last_feature
from _part_checks import bbox_extent_check, report_mass_properties, volume_check
from _part_properties import part_drawing_unit
from _part_save import save_part_and_images
from _paths import OUT_PNG, REFERENCES_DIR
from _printed_tolerance import edge_break_chamfer_mm, edge_break_radius_mm
from _inch_wall_limits import WALL_TARGET_MM
from _rebuild import force_rebuild
from _session import run_build
from _sketch import (
    SketchDims,
    add_line_chain,
    anchor_point_to_origin,
    anchor_point_to_point,
    blank_reference_sketches,
    dimension_between,
    ensure_fully_defined,
    set_sketch_direct_db,
)
from _sketch_chains import define_rectilinear_chain
from _sketch_circle import define_circle
from _drawing_precision import _named_dimension, apply_drawing_precision
from _drawing_marks import apply_drawing_properties, clear_dimensions_for_drawing, mark_dimensions_for_drawing
from _drawing_tolerances import (
    set_dimension_bilateral_tolerance,
    set_dimension_symmetric_tolerance,
)
from _drawing_prefix import set_dimension_prefix
from _holes import (
    DRILL_POINT_H,
    THREAD_MAJOR_MM,
    HoleSpec,
    blind_cut_dia_mm,
    wizard_holes,
)
from _fit_deviations import deviations
from _gtol_face_resolve import resolve_faces
from _part_pmi import author_part_pmi
from fr_harmonic_base_spec import (
    BOTTOM_LENGTH,
    BOTTOM_THICKNESS,
    BOTTOM_WIDTH,
    COLUMN_SOCKET_XZ,
    COLUMN_X,
    CROSS_RIB_CENTER_X,
    DECK_CORNER_R,
    DECK_EDGE_BREAK,
    DECK_HALF_X,
    DECK_HALF_Z,
    DECK_LENGTH,
    DECK_RISE,
    DECK_WIDTH,
    CROSS_TAP_LUG_BOTTOM_Y,
    CROSS_TAP_LUG_INNER_X,
    CROSS_TAP_LUG_INNER_Z,
    CROSS_TAP_LUG_LENGTH,
    CROSS_TAP_LUG_WIDTH,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION,
    GREEN_TOP,
    LINEAR_BAND_MM,
    MM_PER_IN,
    PART_SURFACE_FINISHES,
    PIVOT_SEAT_DIMENSIONS,
    PIVOT_SEAT_POSITION_BAND_MM,
    POCKET_CEILING_Y,
    POCKET_CORNER_FILLET_R,
    POCKET_FILLET_TOL_TYPE,
    POCKET_HALF_X,
    POCKET_HALF_Z,
    POCKET_WALL,
    RIB_RELIEF,
    RIB_THICKNESS,
    SOCKET_BOSS_DIA,
    SOCKET_BORE_FINISHES,
    SPOTFACE_DEPTH_BAND_MM,
    STACK_HEIGHT,
    TOP_LENGTH,
    TOP_THICKNESS,
    TOP_WIDTH,
    UNDERSIDE_LOCATION_PREFIXES,
    UNIT,
)
import fr_nameplate_spec
from _cone_axis_constants import (
    FRAME_FRONT_COLUMN_Z,
)
from cone_line import PIVOT_XZ as PIVOT_SCREW_XZ
from cone_line import X_DRUM
from cylinder_bank_layout import (
    BACK_STRAP_INNER_Z as BANK_BACK_STRAP_INNER_Z,
    FRONT_STRAP_INNER_Z as BANK_FRONT_STRAP_INNER_Z,
)
from dt_vn_cone_pivot_screw_spec import (
    MIN_USEFUL_ENGAGEMENT_MM as PIVOT_MIN_USEFUL_ENGAGEMENT,
    THREAD as PIVOT_THREAD,
    THREAD_TAIL_LEN as PIVOT_THREAD_ENGAGEMENT,
)
from _mcmaster_91829a560 import TIP_CHAMFER as PIVOT_TIP_CHAMFER, UC_SPAN as PIVOT_THREAD_START
from dt_vn_cone_lock_knob_spec import (
    HEAD_DIA as LOCK_HEAD_DIA,
    STUD_LEN as LOCK_STUD_LEN,
    THREAD as LOCK_THREAD,
    require_seat_fit as require_lock_seat_fit,
)
from dt_cone_swing_platform_geometry import PLATE_T, swing_hardware_geometry
from dt_swing_stop_screw_spec import (
    CONTACT_DIA as STOP_CONTACT_DIA,
    THREAD as STOP_THREAD,
    FULL_THREAD_START_MAX_MM as SMALL_SCREW_THREAD_START_MAX,
    LENGTH_MIN_MM as SMALL_SCREW_LENGTH_MIN,
    LENGTH_MAX_MM as SMALL_SCREW_LENGTH_MAX,
    TIP_CHAMFER as SMALL_SCREW_TIP_CHAMFER,
)
from dt_vn_slotted_screw_spec import SHANK_LEN as BLOCK_SCREW_LEN, TIP_CHAMFER as BLOCK_TIP_CHAMFER
from dt_vn_pedestal_hold_down_screw_spec import TIP_CHAMFER as PEDESTAL_TIP_CHAMFER
from fr_vn_lag_screw_spec import TIP_CHAMFER as HOLD_DOWN_TIP_CHAMFER
from dt_pinion_pivot_block_geometry import (
    BLOCK_HEIGHT,
    BLOCK_HEIGHT_BAND,
    SCREW_HALF_SPACING,
)
from pinion_rig_layout import BLOCK_SEAT_Z, SPRING_PAD_Z
from pinion_rig_park_geometry import PIVOT_X as PINION_PIVOT_X
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
    ThroughSeatMaterial,
    HOLD_DOWN_INSERTION_MIN_MM,
    HOLD_DOWN_INSERTION_MAX_MM,
    HOLD_DOWN_SEAT_SPEC,
    HOLD_DOWN_TAP_DRILL_DIA,
    HOLD_DOWN_THREAD,
    NAMEPLATE_SEAT_SPEC,
    NAMEPLATE_SCREW_XZ,
    PEDESTAL_INSERTION_MIN_MM,
    PEDESTAL_INSERTION_MAX_MM,
    retained_material_segments_mm,
    through_seat_material,
    through_seat_pocket_clearances_mm,
    require_stop_seat_fit,
    require_through_seat_fit,
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
MATERIAL = "Gray Cast Iron"  # see _appearance.apply_material docstring

# Plate nominal geometry (BOTTOM_*/TOP_*) lives in fr_harmonic_base_spec -- the
# COM-free contract the drawing shares. DIMENSIONS.md ch6: 46 cm / 28 cm callouts
# = 18.1 x 11.0 in (annotated); the length keeps the legacy 18.0 in and the
# thicknesses come from the legacy HarmonicBase.cs (photo-verify M2 note). The
# DEPTH deliberately no longer follows the 28 cm callout: fr_harmonic_base_spec
# widens the pad to 10.808 (slab 11.308, same 0.25 in reveal per side) so the
# socket-to-pad-edge land is equal on both axes -- asserted below.
IN = 25.4
# The minimum land between neighbouring cavities, bores and edges (.040).
LAND_FLOOR_MM = 1.016

# The four column sockets, their stations and their bore surface finishes now
# live in fr_harmonic_base_spec: the sheet may only source a surface-finish
# control from a part SPEC, and the bore size reaches that spec through the
# leaf module frame_column_stations. Bore diameters remain nominal CAD
# geometry -- match-fit production sockets to their assigned actual MHA-FR-03
# tubes, not to a fixed diameter band.
BASE_SPOTFACE_PLANE_Z = TOP_WIDTH / 2.0
BASE_SPOTFACE_DEPTH = BASE_SPOTFACE_PLANE_Z - BASE_SCREW_SEAT_Z
BASE_SCREW_FACES = (("front", -1.0, True), ("rear", 1.0, False))


if BASE_SPOTFACE_DEPTH <= 0.0:
    raise AssertionError("base cross-screw spotface must cut inward from the side")

HOLE_XZ = SUPPORT_HOLD_DOWN_XZ

# Edge finishing (chamfer external, fillet internal).
# The machined plate gets 45-degree edge breaks on every external edge: the
# exposed top rims and the underside rim at .063 legs (single-pass mill/file
# breaks). The one internal
# wall junction -- the pad side walls meeting the flange top face -- carries a
# 0.5 root fillet, which is NOT a print requirement: a 0.5 mm internal root
# cannot be measured with hobby-shop kit (it needs an optical comparator or a
# radius gauge under magnification), so the sheet carries no radius callout
# and the deck cutter's own corner defines it (2026-09 review). Every
# mechanism hole sits >= 26 from every plate edge; the closest seats to a deck
# edge are the nameplate taps (NAMEPLATE_SCREW_XZ), about .3 inside the
# deck's west edge -- clear of its .031 break, so no break touches a seat.
# Plan corners are ROUNDED, not chamfered (2026-09 photo re-derive): every
# ch30 plate (p002/p003 front corners, p006 rear) shows the casting's vertical
# corners as one large radius running the full height, flange and pad
# together. .88 on the flange; the pad's radius is .25 smaller so the
# two arcs stay concentric across the .25 reveal.
FLANGE_CORNER_R = 22.352  # .88
PAD_CORNER_R = FLANGE_CORNER_R - (BOTTOM_LENGTH - TOP_LENGTH) / 2.0  # .63
RIM_CHAMFER = 1.6002  # .063 legs, top rims + underside rim
PAD_ROOT_R = 0.5  # pad-to-flange root fillet; modelled, never called out

# Black deck + green land (user ruling 2026-10-09; ch11 p.21, ch13 p.25 and
# ch30 p002/p003/p006 show a BLACK panel on the green casting top). The raised
# rim of the 2026-09 re-derive is gone: the panel is a machined pad DECK_RISE
# proud of the green top, centred on it, so the nameplate and every seat stay
# on the deck at STACK_HEIGHT while the column sockets open on the green land.
# The deck face is painted PANEL_BLACK at the FACE level (part and body stay
# casting green). DECK_* live in fr_harmonic_base_spec.

# Stamped serial number (2026-09-02, ch26 p.70 page001_img02/03): a hand-stamped
# "2" on the deck. Cut from the vendored closed-region DXF
# (gen_base_serial_dxf.py regenerates it from these constants) on a plane at
# the deck top, SERIAL_DEPTH deep. Since the 2026-10-09 ruling it sits in the
# deck's north-west (+X, +Z) corner, about 6 mm (.24) in from both deck edges
# -- clear of the nameplate on the deck's west end and of the corner's break.
# The stamp prints APPROX AS SHOWN, so its station stays put (and its DXF
# unchanged) rather than following the deck's inch edges.
SERIAL_TEXT = "2"
SERIAL_HEIGHT_MM = 3.5  # p.70 macro: a small hand stamp
SERIAL_DEPTH = 0.3  # a stamp, not an engraving
SERIAL_XZ = (161.0, 124.25)
# Top-sketch (sx, sy) maps to model (sx, STACK_HEIGHT, -sy), and native *Top
# projects model (X, Z) to paper (X, -Z). Keep glyph +Y along sketch +Y:
# the native R7 PDF confirmed the former setting vertically reflected the "2".
SERIAL_MIRROR_Y = True
SERIAL_DXF = REFERENCES_DIR / "base-serial.dxf"
SERIAL_AREA_MM2 = 3.1029  # pinned from gen_base_serial_dxf's summary (net glyph area)

# Cone swing hardware, through-tapped from the TOP face. MACHINE-handed coords.
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

# The shoulder screw's unchanged threaded tail enters the through-tapped deck.
# The stock lock stud inserts 12.70 through the platform, or19.05 in its
# bare-base fencing pose. Insertion is not synonymous with engaged thread.
LOCK_STUD_ENGAGEMENT = LOCK_STUD_LEN - PLATE_T

# Alignment-pinion rig hold-downs: four through #8-32 seats under the two
# pivot blocks and one through #4-40 spring-foot seat. Pedestal seats retain
# their separate transferred #8-32 group.
# The parked rig's live pivot supplies the machine-X datum; the shared rig
# stack supplies both block mid-depth stations. The base's native seats
# follow pitch/gap changes without a second former-world-coordinate model.
BLOCK_SCREW_XZ = tuple(
    (PINION_PIVOT_X + dx, z)
    for z in BLOCK_SEAT_Z
    for dx in (-SCREW_HALF_SPACING, SCREW_HALF_SPACING)
)
# Physical insertion at the shortest printed block. Useful thread and any
# underside protrusion are checked against retained material, not drill depth.
BLOCK_SCREW_MAX_INSERTION = BLOCK_SCREW_LEN - BLOCK_HEIGHT + BLOCK_HEIGHT_BAND
# The spring screw is SCREW_EAST_OF_PIVOT east of the same parked pivot,
# with its pad's transferred machine-Z station supplied by the rig stack.
FOOT_SCREW_XZ = ((PINION_PIVOT_X - SPRING_SCREW_EAST, SPRING_PAD_Z),)
# Keep the real stock spring thickness interval; no blind tap lead remains.
SPRING_THICKNESS_MIN = SPRING_THICKNESS + deviations(SPRING_THICKNESS_BAND)[0]

# Each transferred arbor-pedestal seat follows the live cylinder bank's
# strap inner face and the pedestal's own ledge offset. Use exact geometry,
# not rounded study coordinates: the assembly still checks the independent
# pedestal placement against these native base cuts.
_PEDESTAL_LEDGE_OFFSET = PEDESTAL_STRAP_INNER_Z - PEDESTAL_LEDGE_SCREW_Z  # 19.0
PEDESTAL_SCREW_XZ = (
    (X_DRUM, BANK_FRONT_STRAP_INNER_Z - _PEDESTAL_LEDGE_OFFSET),
    (X_DRUM, BANK_BACK_STRAP_INNER_Z + _PEDESTAL_LEDGE_OFFSET),
)
# The setup offsets use the same live seat stations as the physical cuts.
# Top-plane sketch/table Y is machine -Z; retain the signs for point placement
# and use unsigned native dimensions, as every point-distance sketch does.
PIVOT_NEAR_PEDESTAL_XZ = min(
    PEDESTAL_SCREW_XZ, key=lambda xz: math.dist(xz, PIVOT_SCREW_XZ)
)
PIVOT_SEAT_OFFSETS_MM = (
    PIVOT_SCREW_XZ[0] - PIVOT_NEAR_PEDESTAL_XZ[0],
    PIVOT_NEAR_PEDESTAL_XZ[1] - PIVOT_SCREW_XZ[1],
)
# A transferred seat lands where the fitted pedestal stands, within the
# study's +-2 x / +-5 z fit-up bound of nominal; the wall checks book it.
PEDESTAL_TRANSFER_XZ = (2.0, 5.0)
PEDESTAL_TRANSFER_ENVELOPE = math.hypot(*PEDESTAL_TRANSFER_XZ)

# Maker's nameplate seat stations and native spec live in the pure fasteners module.
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
# raised deck, inside its edge break by >= .040, or a corner would overhang the
# step down to the green land (user ruling 2026-10-09: .16 inside the west edge).
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
if NAMEPLATE_DECK_CLEARANCE - DECK_EDGE_BREAK < LAND_FLOOR_MM:
    raise AssertionError(
        f"nameplate footprint {_NAMEPLATE_CORNERS_XZ} sits only "
        f"{NAMEPLATE_DECK_CLEARANCE:.3f} mm inside the deck edge (need >= "
        f"{LAND_FLOOR_MM} past its {DECK_EDGE_BREAK:.4f} break)"
    )

# Native tapped seats. Physical thread compatibility is carried by each named
# HoleSpec designation; tap-drill diameters remain manufacturing geometry and
# are not compared to purchased fasteners' major-diameter solids.
PIVOT_SEAT_SPEC = HoleSpec("tapped_bottoming", PIVOT_THREAD, thread_class="2B")
LOCK_SEAT_SPEC = HoleSpec("tapped", LOCK_THREAD, thread_class="2B")
STOP_SEAT_SPEC = HoleSpec("tapped", STOP_THREAD, thread_class="2B")
BLOCK_SEAT_SPEC = HoleSpec("tapped_bottoming", "#8-32", thread_class="2B")
FOOT_SEAT_SPEC = HoleSpec("tapped_bottoming", "#4-40", thread_class="2B")
PEDESTAL_SEAT_SPEC = HoleSpec("tapped_bottoming", "#8-32", thread_class="2B")
PIVOT_SCREW_HOLE_DIA = blind_cut_dia_mm(PIVOT_SEAT_SPEC)
LOCK_SCREW_HOLE_DIA = blind_cut_dia_mm(LOCK_SEAT_SPEC)
STOP_SCREW_HOLE_DIA = blind_cut_dia_mm(STOP_SEAT_SPEC)
BLOCK_SCREW_HOLE_DIA = blind_cut_dia_mm(BLOCK_SEAT_SPEC)
FOOT_SCREW_HOLE_DIA = blind_cut_dia_mm(FOOT_SEAT_SPEC)
PEDESTAL_SCREW_HOLE_DIA = blind_cut_dia_mm(PEDESTAL_SEAT_SPEC)
NAMEPLATE_SCREW_HOLE_DIA = blind_cut_dia_mm(NAMEPLATE_SEAT_SPEC)

# Socket cylinders occupy Y=1.00..1.88, overlapping the deepest vertical-seat
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
if COLUMN_SOCKET_NEAREST_OCCUPANT_WALL < LAND_FLOOR_MM:
    raise AssertionError(
        "base column socket leaves less than .040 wall to another base cavity"
    )
# Nominal model-space land from each bore to the pad edge, on the green top
# the sockets open on (user ruling 2026-10-09). Its worst case is proven
# below. TOP_WIDTH is sized so this land is EQUAL on both axes to the .001
# grid (half a step, .0005): the 2026-09 blind machinist review rejected the
# former 10.5 in pad, whose land in Z could not survive the coordinate stack
# while every table dimension stayed in tolerance.
COLUMN_SOCKET_LAND_X = min(
    TOP_LENGTH / 2.0 - abs(x) - COLUMN_SOCKET_DIAMETER / 2.0
    for x, _z in COLUMN_SOCKET_XZ
)
COLUMN_SOCKET_LAND_Z = min(
    TOP_WIDTH / 2.0 - abs(z) - COLUMN_SOCKET_DIAMETER / 2.0
    for _x, z in COLUMN_SOCKET_XZ
)
if abs(COLUMN_SOCKET_LAND_X - COLUMN_SOCKET_LAND_Z) > 0.0005 * MM_PER_IN:
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
if COLUMN_SOCKET_DECK_GAP < LAND_FLOOR_MM:
    raise AssertionError("base column socket crowds the raised deck")

# The finished land between each bore and the pad edge's break must stay
# .040 wide and continuous (2026-09 blind machinist review). It used to be
# a sheet note ("MIN ... AFTER MATCHING AND EDGE BREAK"), which put a
# dimension in a note (hb-render-4 eye pass); the stack below proves every
# in-tolerance part meets it, so the sheet needs no note.
COLUMN_SOCKET_LAND_MIN = LAND_FLOOR_MM


def _general_band_mm() -> float:
    """The .XX band: the loosest general tolerance the sheet prints.

    Every length and plan station prints .XX or .XXX and the hole-table
    coordinates print .XXX, so this band bounds every location term.
    """
    return LINEAR_BAND_MM


def _edge_break_mm() -> float:
    return max(edge_break_radius_mm(unit=UNIT), edge_break_chamfer_mm(unit=UNIT))


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


# These lengths stay tied to the unchanged perimeter walls.
# Ribs and lugs end mid-wall, so a band shift of the pocket outline never
# opens a slot between them and the wall.
RIB_HALF_LENGTH_X = POCKET_HALF_X + POCKET_WALL / 2.0
RIB_HALF_LENGTH_Z = POCKET_HALF_Z + POCKET_WALL / 2.0


# Per-hole material is established below after the retained footprint shapes.
# Horizontal frame cross taps retain their lugs and blind end conditions.
_CROSS_TAP_MAJOR = THREAD_MAJOR_MM[BASE_CROSS_TAP_SPEC.size]
# The print specifies a MIN drill depth, not a maximum blind-drill depth. Tip/past-tip
# checks therefore cover the nominal native drill only, not an unbounded
# manufactured deep end. The finite backing envelope is checked separately.
CROSS_TAP_TIP_Z = (
    BASE_SCREW_SEAT_Z
    - CASTING_TAP_DRILL_DEPTH
    - BASE_CROSS_TAP_DRILL_DIA / 2.0 * DRILL_POINT_H
)
CROSS_TAP_LUG_WALLS = {
    "past tip": CROSS_TAP_TIP_Z - CROSS_TAP_LUG_INNER_Z,
    "under drill": BASE_SCREW_Y
    - BASE_CROSS_TAP_DRILL_DIA / 2.0
    - CROSS_TAP_LUG_BOTTOM_Y,
    "beside drill": COLUMN_X - CROSS_TAP_LUG_INNER_X - BASE_CROSS_TAP_DRILL_DIA / 2.0,
}
if not (
    POCKET_HALF_X + LAND_FLOOR_MM
    < CROSS_TAP_LUG_INNER_X + CROSS_TAP_LUG_WIDTH
    < TOP_LENGTH / 2.0 - LAND_FLOOR_MM
):
    raise AssertionError("cross-tap lug must end inside the pocket wall")
if CROSS_TAP_LUG_WALLS["past tip"] < 1.5 * _CROSS_TAP_MAJOR:
    raise AssertionError("cross-tap lug ends less than 1.5D past the drill tip")
if min(CROSS_TAP_LUG_WALLS.values()) - 1.5 * _general_band_mm() < WALL_TARGET_MM:
    raise AssertionError("cross-tap nominal drill/lug wall allowance falls under .080")

# The socket bosses: 1/2 x (boss - bore) of wall round each bore, and the
# boss swallows the pocket's plan corner, so the pocket needs no corner radius.
SOCKET_BOSS_WALL = (SOCKET_BOSS_DIA - COLUMN_SOCKET_DIAMETER) / 2.0
if (
    SOCKET_BOSS_WALL
    - (COLUMN_SOCKET_MATCH_BORE_MAX - COLUMN_SOCKET_DIAMETER) / 2.0
    - _general_band_mm()
    < WALL_TARGET_MM
):
    raise AssertionError("socket boss wall thins under .080 at the worst case")
for _x, _z in COLUMN_SOCKET_XZ:
    if (
        math.hypot(POCKET_HALF_X - abs(_x), POCKET_HALF_Z - abs(_z))
        >= SOCKET_BOSS_DIA / 2.0
    ):
        raise AssertionError("socket boss no longer covers the pocket's plan corner")


def cross_tap_backing_margins_mm(band_mm: float) -> dict[str, float]:
    """Conservative .080 backing margins, without optional fillet credit.

    The lug joins the skin at the same ceiling plane, wherever that plane
    falls relative to the cross-tap axis. Erode the guaranteed lug, socket
    and wall footprints by .080 and require their intervals to overlap.
    Socket-bore air and the open spotface entrance are intentional; neither
    is credited as thread material. The printed MIN drill has no deep limit.
    """
    radius = max(_CROSS_TAP_MAJOR, BASE_CROSS_TAP_DRILL_DIA + band_mm) / 2.0
    axis_x_radius = radius + band_mm
    socket_radius = (
        SOCKET_BOSS_DIA / 2.0
        - band_mm / 2.0
        - math.sqrt(2.0) * band_mm
        - WALL_TARGET_MM
    )
    socket_half_z = math.sqrt(socket_radius**2 - axis_x_radius**2)
    return {
        "lug/skin join": POCKET_CEILING_Y - CROSS_TAP_LUG_BOTTOM_Y - 2.0 * band_mm,
        "green skin": GREEN_TOP - POCKET_CEILING_Y - 2.0 * band_mm - WALL_TARGET_MM,
        "below thread": (
            BASE_SCREW_Y - radius - CROSS_TAP_LUG_BOTTOM_Y - 2.0 * band_mm - WALL_TARGET_MM
        ),
        "above thread": GREEN_TOP - BASE_SCREW_Y - radius - 2.0 * band_mm - WALL_TARGET_MM,
        "lug inner X": (
            COLUMN_X - axis_x_radius - CROSS_TAP_LUG_INNER_X - band_mm - WALL_TARGET_MM
        ),
        "lug outer X": (
            CROSS_TAP_LUG_INNER_X + CROSS_TAP_LUG_WIDTH
            - 2.0 * band_mm - COLUMN_X - axis_x_radius - WALL_TARGET_MM
        ),
        "wall outer X": (
            TOP_LENGTH / 2.0 - band_mm - COLUMN_X - axis_x_radius - WALL_TARGET_MM
        ),
        "lug/socket join": socket_half_z - band_mm - WALL_TARGET_MM,
        "socket/wall join": min(
            abs(z) + socket_half_z - POCKET_HALF_Z - band_mm - WALL_TARGET_MM
            for _, z in COLUMN_SOCKET_XZ
        ),
    }


CROSS_TAP_BACKING_MARGINS = cross_tap_backing_margins_mm(_general_band_mm())
if (
    CROSS_TAP_BACKING_MARGINS["lug/skin join"] <= 0.0
    or min(CROSS_TAP_BACKING_MARGINS.values()) < 0.0
):
    raise AssertionError(
        f"cross-tap lug/skin/socket/wall backing fails: {CROSS_TAP_BACKING_MARGINS}"
    )

# Retained underside shapes in machine (x,z): ("disc",x,z,r) or
# ("rect",x0,x1,z0,z1). These are the exact sketch/volume/drawing footprints.
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
    (CROSS_RIB_CENTER_X - RIB_THICKNESS / 2.0, CROSS_RIB_CENTER_X + RIB_THICKNESS / 2.0),
    (-RIB_HALF_LENGTH_Z, RIB_HALF_LENGTH_Z),
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

# One inventory for all18 unchanged deck stations and their real retained metal.
# Material contracts include each transfer rectangle, not only nominal axes.
THROUGH_SEAT_GROUPS = (
    ("SupportHoldDownSeats", HOLD_DOWN_SEAT_SPEC, HOLE_XZ, (0.0, 0.0)),
    ("PivotSeat", PIVOT_SEAT_SPEC, (PIVOT_SCREW_XZ,), (0.0, 0.0)),
    ("LockSeat", LOCK_SEAT_SPEC, (LOCK_KNOB_XZ,), (0.0, 0.0)),
    ("StopSeat", STOP_SEAT_SPEC, (STOP_SCREW_XZ,), (0.0, 0.0)),
    ("BlockScrewHoles", BLOCK_SEAT_SPEC, BLOCK_SCREW_XZ, (0.0, 0.0)),
    ("FootScrewHoles", FOOT_SEAT_SPEC, FOOT_SCREW_XZ, (0.0, 0.0)),
    ("PedestalSeats", PEDESTAL_SEAT_SPEC, PEDESTAL_SCREW_XZ, PEDESTAL_TRANSFER_XZ),
    ("NameplateSeats", NAMEPLATE_SEAT_SPEC, NAMEPLATE_SCREW_XZ, (0.0, 0.0)),
)
THROUGH_SEAT_MATERIAL: dict[str, tuple[ThroughSeatMaterial, ...]] = {
    tag: tuple(through_seat_material(seat, xz, envelope_xz=envelope) for xz in stations)
    for tag, seat, stations, envelope in THROUGH_SEAT_GROUPS
}
if sum(len(stations) for _tag, _seat, stations, _envelope in THROUGH_SEAT_GROUPS) != 18:
    raise AssertionError("base must retain all18 deck-seat stations")

# Complete circular exits, not just nominal axes: scan every drill/thread,
# transfer rectangle, wall, rib, socket, lug and all 28 finite R MAX patches.
THROUGH_SEAT_POCKET_CLEARANCES = {
    tag: tuple(through_seat_pocket_clearances_mm(seat, xz, envelope_xz=envelope)
               for xz in stations)
    for tag, seat, stations, envelope in THROUGH_SEAT_GROUPS
}
for _tag, _clearances in THROUGH_SEAT_POCKET_CLEARANCES.items():
    for _i, _gaps in enumerate(_clearances):
        if min(_gaps.values()) <= 0.0:
            raise AssertionError(f"{_tag}[{_i}]: interrupted through exit {_gaps}")
        # The relocation specifically requires .080 around the block seats;
        # other unchanged hardware retains its existing wall/fillet contracts.
        if _tag == "BlockScrewHoles" and min(_gaps.values()) < WALL_TARGET_MM:
            raise AssertionError(f"{_tag}[{_i}]: block-seat air falls below .080 {_gaps}")
        _segments = THROUGH_SEAT_MATERIAL[_tag][_i].nominal_segments_mm
        if len(_segments) != 1 or max(
            abs(_segments[0][0]), abs(_segments[0][1] - (STACK_HEIGHT - POCKET_CEILING_Y)),
        ) > 1e-9:
            raise AssertionError(f"{_tag}[{_i}]: expected skin-only through axis, got {_segments}")

# Capacity is a female-material condition, not a fictitious screw insertion.
# Real hardware windows remain separate so inherited installed-joint rulings
# (including the nameplate's accepted short engagement) are not overwritten.
for _tag, _seat, _stations, _envelope in THROUGH_SEAT_GROUPS:
    for _material in THROUGH_SEAT_MATERIAL[_tag]:
        _capacity = sum(end - start for start, end in _material.guaranteed_segments_mm)
        if _capacity < 1.5 * THREAD_MAJOR_MM[_seat.size] - 1e-9:
            raise AssertionError(f"{_tag}: retained full-form capacity {_capacity:.4f} <1.5D")

# Real stock/source-model overlap, distinct from female capacity. No unprovided
# supplier tolerances are manufactured from title-block rows. Known printed
# grips and the stop/foot's qualified same-SKU length limits are included.
# The pivot retains its existing inspected >=1D acceptance; its vendor
# shoulder undercut and tip already preclude1.5D before this geometry change.
_SPRING_THICKNESS_MAX = SPRING_THICKNESS + deviations(SPRING_THICKNESS_BAND)[1]
_NOMINAL_STOCK_WINDOWS = (
    ("SupportHoldDownSeats", HOLD_DOWN_INSERTION_MIN_MM,
     HOLD_DOWN_INSERTION_MAX_MM, HOLD_DOWN_TIP_CHAMFER, 0.0, 1.5),
    ("PivotSeat", PIVOT_THREAD_ENGAGEMENT, PIVOT_THREAD_ENGAGEMENT,
     PIVOT_TIP_CHAMFER, PIVOT_THREAD_START,
     PIVOT_MIN_USEFUL_ENGAGEMENT / THREAD_MAJOR_MM[PIVOT_THREAD]),
    ("BlockScrewHoles", BLOCK_SCREW_LEN - BLOCK_HEIGHT - BLOCK_HEIGHT_BAND,
     BLOCK_SCREW_MAX_INSERTION, BLOCK_TIP_CHAMFER, 0.0, 1.5),
    ("FootScrewHoles", SMALL_SCREW_LENGTH_MIN - _SPRING_THICKNESS_MAX,
     SMALL_SCREW_LENGTH_MAX - SPRING_THICKNESS_MIN, SMALL_SCREW_TIP_CHAMFER,
     max(0.0, SMALL_SCREW_THREAD_START_MAX - SPRING_THICKNESS_MIN), 1.5),
    ("PedestalSeats", PEDESTAL_INSERTION_MIN_MM,
     PEDESTAL_INSERTION_MAX_MM,
     PEDESTAL_TIP_CHAMFER, 0.0, 1.5),
)
THROUGH_SEAT_SOURCE_MODEL_FITS = {}
for _tag, _insert_min, _insert_max, _tip, _start, _minimum in _NOMINAL_STOCK_WINDOWS:
    _seat = next(seat for tag, seat, _stations, _bounds in THROUGH_SEAT_GROUPS if tag == _tag)
    THROUGH_SEAT_SOURCE_MODEL_FITS[_tag] = tuple(
        require_through_seat_fit(
            f"{_tag} source-model stock", _seat, material,
            insertion_min_mm=_insert_min, insertion_max_mm=_insert_max,
            tip_loss_mm=_tip, full_thread_start_mm=_start,
            minimum_engagement_diameters=_minimum,
        )
        for material in THROUGH_SEAT_MATERIAL[_tag]
    )
require_lock_seat_fit(
    LOCK_SEAT_SPEC, PLATE_T, LOCK_STUD_LEN, material=THROUGH_SEAT_MATERIAL["LockSeat"][0]
)
require_stop_seat_fit(STOP_SEAT_SPEC, PLATE_T, material=THROUGH_SEAT_MATERIAL["StopSeat"][0])
# Nameplate external-thread acceptance remains the existing inspected RV-03
# contract, evaluated by the frame with its actual .XXX plate limits. This
# receiver still has the same female capacity/clearance and native readback
# checks as every other through seat; it does not acquire a new1.5D screw rule.

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
        _boss_wall_fillet_area(SOCKET_BOSS_DIA / 2.0, inset, POCKET_CORNER_FILLET_R)
        for x, z in COLUMN_SOCKET_XZ
        for inset in (POCKET_HALF_X - abs(x), POCKET_HALF_Z - abs(z))
    ]


def _disc_rect_corners(
    centre: tuple[float, float], radius: float, rect: PocketShape
) -> list[tuple[float, float, float]]:
    """Where a round boss's cylinder crosses a rect feature's faces inside
    the pocket: (x, z, inset) per crossing, the inset being the boss centre's
    signed distance to that face, positive on the face's air side (the
    convention _boss_wall_fillet_area takes)."""
    cx, cz = centre
    _kind, x0, x1, z0, z1 = rect
    found = []
    for along_x, value, side, lo, hi in (
        (False, x0, -1.0, z0, z1),
        (False, x1, 1.0, z0, z1),
        (True, z0, -1.0, x0, x1),
        (True, z1, 1.0, x0, x1),
    ):
        across, along = (cz, cx) if along_x else (cx, cz)
        inset = side * (across - value)
        if abs(inset) >= radius:
            continue
        half = math.sqrt(radius**2 - inset**2)
        for t in (along - half, along + half):
            x, z = (t, value) if along_x else (value, t)
            if lo < t < hi and abs(x) < POCKET_HALF_X and abs(z) < POCKET_HALF_Z:
                found.append((x, z, inset))
    return found


def _pocket_corner_fillets(fillet_r: float) -> list[tuple[list[float], float, float]]:
    """(pick,edge length,plan section) for retained rib and lug reentrants.

    Socket-to-wall junctions remain in PocketFillets. Only the cross rib's
    wall and long-rib junctions translate in X; no corner is removed.
    """
    square = _fillet_section_area(fillet_r)
    half_rib = RIB_THICKNESS / 2.0
    corners: list[tuple[float, float, float, float]] = []  # x, z, bottom, area
    for sa in (-1.0, 1.0):
        for sb in (-1.0, 1.0):
            corners += [
                (sa * POCKET_HALF_X, sb * half_rib, RIB_RELIEF, square),
                (CROSS_RIB_CENTER_X + sa * half_rib, sb * POCKET_HALF_Z, RIB_RELIEF, square),
                (CROSS_RIB_CENTER_X + sa * half_rib, sb * half_rib, RIB_RELIEF, square),
            ]
    for (x, z), lug in zip(COLUMN_SOCKET_XZ, CROSS_TAP_LUG_SHAPES, strict=True):
        lug_z = z - math.copysign(CROSS_TAP_LUG_LENGTH, z)
        corners.append(
            (math.copysign(POCKET_HALF_X, x), lug_z, CROSS_TAP_LUG_BOTTOM_Y, square)
        )
        for cx, cz, inset in _disc_rect_corners((x, z), SOCKET_BOSS_DIA / 2.0, lug):
            area = _boss_wall_fillet_area(SOCKET_BOSS_DIA / 2.0, inset, fillet_r)
            corners.append((cx, cz, CROSS_TAP_LUG_BOTTOM_Y, area))
    return [
        ([x, (bottom + POCKET_CEILING_Y) / 2.0, z], POCKET_CEILING_Y - bottom, area)
        for x, z, bottom, area in corners
    ]


def _pocket_corner_fillet_volume(fillet_r: float) -> float:
    """Metal the PocketCornerFillets feature adds: section x edge length."""
    return sum(
        length * area for _pick, length, area in _pocket_corner_fillets(fillet_r)
    )


# Every vertical reentrant pocket corner, both fillet features: the count the
# one "R MAX" dimension prints.
POCKET_FILLET_COUNT = len(_pocket_fillet_areas()) + len(
    _pocket_corner_fillets(POCKET_CORNER_FILLET_R)
)


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


def _through_holes_volume_mm3(seat: HoleSpec, stations) -> float:
    """Integrate actual retained metal over each circular tap-drill footprint.

    These18 stations and their full transferred envelopes are inside the deck,
    west of the socket/lug regions. In that domain the only additional metal
    is perimeter wall, either rib and their square reentrant fillets. Reject a
    future footprint reaching the socket/lug domain rather than silently using
    a skin-only approximation there. Gaussian disk quadrature retains partial
    rib/wall intersections and adds no nonexistent118-degree drill point.
    """
    radius = blind_cut_dia_mm(seat) / 2.0
    nodes, weights = np.polynomial.legendre.leggauss(256)
    dx = radius * nodes[:, None]
    chord = np.sqrt(radius * radius - dx * dx)
    dz = chord * nodes[None, :]
    area_weights = radius * weights[:, None] * chord * weights[None, :]
    total = 0.0
    half = RIB_THICKNESS / 2.0
    fillet = POCKET_CORNER_FILLET_R
    for x, z in stations:
        if abs(x) + radius >= CROSS_TAP_LUG_INNER_X - fillet:
            raise AssertionError("deck-seat volume footprint reaches socket/lug domain")
        xx, zz = x + dx, z + dz
        bottom = np.full(dz.shape, POCKET_CEILING_Y)
        bottom = np.where((np.abs(xx) >= POCKET_HALF_X) | (np.abs(zz) >= POCKET_HALF_Z), 0.0, bottom)
        bottom = np.where((np.abs(xx - CROSS_RIB_CENTER_X) <= half) | (np.abs(zz) <= half), np.minimum(bottom, RIB_RELIEF), bottom)
        for sx in (-1.0, 1.0):
            for sz in (-1.0, 1.0):
                for cx, cz, ax, az in (
                    (sx * POCKET_HALF_X, sz * half, -sx, sz),
                    (CROSS_RIB_CENTER_X + sx * half, sz * POCKET_HALF_Z, sx, -sz),
                    (CROSS_RIB_CENTER_X + sx * half, sz * half, sx, sz),
                ):
                    u, v = (xx - cx) * ax, (zz - cz) * az
                    patch = (u >= 0) & (u <= fillet) & (v >= 0) & (v <= fillet) & (
                        (u - fillet) ** 2 + (v - fillet) ** 2 >= fillet ** 2
                    )
                    bottom = np.where(patch, np.minimum(bottom, RIB_RELIEF), bottom)
        total += float(np.sum(area_weights * (STACK_HEIGHT - bottom)))
    return total


def _native_vertical_segments(adapter, points, label: str):
    """Read finite solid intervals from high-precision native vertical rays.

    ENTRY_EXIT | NORMALS (5) fixes GetRayIntersectionsPoints to nine doubles per
    hit: BodyIndex, RayIndex, IntersectionType, x, y, z, nx, ny, nz. The integer
    RayIntersections return counts intersections, not rays or array elements.
    All nine fields must be finite; missing bodies, malformed/stale arrays,
    grazing hits and unmatched exits fail closed. None is an empty readback
    only for an integral zero count, and zero hits are accepted only with the
    surrounding retained-material positive controls.
    """
    from solidworks_mcp.adapters.com_variant import dispatch_array, double_array

    model = _early_bound(adapter.currentModel, "IModelDoc2")
    part = _early_bound(adapter.currentModel, "IPartDoc")
    bodies = part.GetBodies2(0, False)  # swSolidBody, include hidden bodies
    if not isinstance(bodies, (tuple, list)) or len(bodies) != 1:
        raise RuntimeError(f"{label}: expected one actual solid body")
    extension = _early_bound(model.Extension, "IModelDocExtension")
    starts = [value for x, z in points for value in (x / 1000.0, (STACK_HEIGHT + 5.0) / 1000.0, z / 1000.0)]
    vectors = [value for _point in points for value in (0.0, -1.0, 0.0)]
    options = 4 | 1  # swRayPtsOptsENTRY_EXIT | swRayPtsOptsNORMALS
    record_width = 9
    reported_count = extension.RayIntersections(
        dispatch_array(list(bodies)), double_array(starts), double_array(vectors),
        options, 1e-9, 1e-8, True,  # SI tolerances; high precision
    )
    raw = model.GetRayIntersectionsPoints()
    try:
        raw_length = len(raw) if raw is not None else None
    except Exception:
        raw_length = None

    def readback_error(message, **details):
        # Preserve native types without repr-ing an unbounded/unknown VARIANT.
        count_type = type(reported_count)
        if count_type in (float, bool, type(None)) or (
            count_type is int and reported_count.bit_length() <= 64
        ):
            count_value = repr(reported_count)
        elif count_type is str:
            count_value = repr(reported_count[:80])
        else:
            count_value = f"<{count_type.__name__}>"
        diagnostics = {
            "raw_type": type(raw).__name__,
            "reported_count": count_value,
            "reported_count_type": count_type.__name__,
            "raw_length": raw_length,
            "expected_record_width": record_width,
            "options": options,
            "ray_count": len(points),
            **details,
        }
        return RuntimeError(f"{label}: {message}; native_ray_readback={diagnostics!r}")

    if type(reported_count) not in (int, float):
        raise readback_error("nonintegral native intersection count")
    try:
        count = int(reported_count)
    except (ValueError, OverflowError) as exc:
        raise readback_error(
            "nonintegral native intersection count",
            conversion_error_type=type(exc).__name__,
        ) from exc
    if reported_count != count:
        raise readback_error("nonintegral native intersection count")
    if count < 0 or (
        raw is not None and (
            not isinstance(raw, (tuple, list)) or raw_length != record_width * count
        )
    ) or (raw is None and count != 0):
        raise readback_error("malformed native ray-intersection readback")
    # Keep raw unchanged for diagnostics, including a native None at zero hits.
    records = () if raw is None else raw
    hits = [[] for _point in points]
    for offset in range(0, len(records), record_width):
        record_index = offset // record_width
        values = []
        for field_index, value in enumerate(records[offset:offset + record_width]):
            try:
                values.append(float(value))
            except Exception as exc:
                # Conversion errors can echo huge native values in their text.
                raise readback_error(
                    "malformed native ray-intersection record",
                    record_index=record_index, field_index=field_index,
                    field_type=type(value).__name__,
                    conversion_error_type=type(exc).__name__,
                ) from None
        if not all(math.isfinite(v) for v in values):
            raise readback_error(
                "non-finite native intersection", record_index=record_index,
                nonfinite_fields=tuple(i for i, value in enumerate(values) if not math.isfinite(value)),
            )
        body_i, ray_i, flags, x, y, z, _nx, _ny, _nz = values
        index = int(ray_i)
        if body_i != 0 or ray_i != index or not 0 <= index < len(points):
            raise readback_error("native ray/body index out of bounds", record_index=record_index)
        if math.dist((x * 1000.0, z * 1000.0), points[index]) > 0.001:
            raise readback_error("ray intersection is off its requested axis", record_index=record_index)
        mode = int(flags) & (16 | 32)  # swRayPtsResultsENTER/EXIT
        if flags != int(flags) or mode not in (16, 32) or int(flags) & ~(1 | 16 | 32):
            raise readback_error("ambiguous/grazing native material boundary", record_index=record_index)
        hits[index].append((STACK_HEIGHT - y * 1000.0, mode))
    result = []
    for index, ray_hits in enumerate(hits):
        ray_hits.sort()
        if len(ray_hits) % 2 or any(
            flag != (16 if i % 2 == 0 else 32)
            for i, (_depth, flag) in enumerate(ray_hits)
        ):
            raise readback_error("unpaired native material entry/exit", ray_index=index)
        segments = tuple((ray_hits[i][0], ray_hits[i + 1][0]) for i in range(0, len(ray_hits), 2))
        if any(end <= start for start, end in segments):
            raise readback_error("native material interval is empty/reversed", ray_index=index)
        result.append(segments)
    return tuple(result)


def _require_native_segments(actual, expected, label: str) -> None:
    if len(actual) != len(expected) or any(
        abs(a - b) > 0.005
        for segment, wanted in zip(actual, expected, strict=True)
        for a, b in zip(segment, wanted, strict=True)
    ):
        raise RuntimeError(f"{label}: actual material {actual} != retained contract {expected}")


def _material_probe_points(seat: HoleSpec, stations, envelope=(0.0, 0.0)):
    radius = THREAD_MAJOR_MM[seat.size] / 2.0 + 0.05
    offsets = ((0.0, 0.0),) if envelope == (0.0, 0.0) else (
        (0.0, 0.0), *((sx * envelope[0], sz * envelope[1])
                      for sx in (-1.0, 1.0) for sz in (-1.0, 1.0))
    )
    return tuple(
        (x + ex + radius * math.cos(angle), z + ez + radius * math.sin(angle))
        for x, z in stations
        for ex, ez in offsets
        for angle in (0.071 + i * math.tau / 16 for i in range(16))
    )


def _verify_uncut_material(adapter, tag: str, seat: HoleSpec, stations) -> None:
    envelope = next(bounds for name, _seat, _stations, bounds in THROUGH_SEAT_GROUPS if name == tag)
    points = tuple(stations) + _material_probe_points(seat, stations, envelope)
    for point, segments in zip(points, _native_vertical_segments(adapter, points, tag), strict=True):
        expected = ((0.0, STACK_HEIGHT - POCKET_CEILING_Y),)
        _require_native_segments(retained_material_segments_mm(*point), expected, f"{tag} source at {point}")
        _require_native_segments(segments, expected, f"{tag} at {point}")


def _verify_through_breakthrough(adapter, tag: str, seat: HoleSpec, stations) -> None:
    """Prove an open bore and its real retained bounds, not just Wizard flags."""
    radius = blind_cut_dia_mm(seat) / 2.0
    air_points = tuple(
        (x + scale * radius * math.cos(angle), z + scale * radius * math.sin(angle))
        for x, z in stations for scale in (0.0, 0.9)
        for angle in (0.071 + i * math.tau / 8 for i in range(8))
    )
    if any(_native_vertical_segments(adapter, air_points, f"{tag} breakthrough")):
        raise RuntimeError(f"{tag}: bore retains material below its entry (not through)")
    wall_points = _material_probe_points(seat, stations)
    for point, segments in zip(wall_points, _native_vertical_segments(adapter, wall_points, f"{tag} wall control"), strict=True):
        expected = ((0.0, STACK_HEIGHT - POCKET_CEILING_Y),)
        _require_native_segments(retained_material_segments_mm(*point), expected, f"{tag} source wall at {point}")
        _require_native_segments(segments, expected, f"{tag} wall at {point}")
    part = _early_bound(adapter.currentModel, "IPartDoc")
    bodies = part.GetBodies2(0, False)
    faces = _early_bound(bodies[0], "IBody2").GetFaces()
    if not isinstance(faces, (tuple, list)) or not faces:
        raise RuntimeError(f"{tag}: no actual trimmed cylinder faces")
    found = set()
    for raw_face in faces:
        face = _early_bound(raw_face, "IFace2")
        surface = _early_bound(face.GetSurface(), "ISurface")
        if surface is None:
            raise RuntimeError(f"{tag}: native face has no surface")
        if not surface.IsCylinder():
            continue
        cylinder = tuple(float(v) for v in surface.CylinderParams)
        if len(cylinder) != 7 or not all(math.isfinite(v) for v in cylinder):
            raise RuntimeError(f"{tag}: invalid native cylinder parameters")
        if abs(cylinder[6] * 1000.0 - radius) > 0.005:
            continue
        if abs(abs(cylinder[4]) - 1.0) > 1e-8 or max(abs(cylinder[3]), abs(cylinder[5])) > 1e-8:
            continue
        for i, (x, z) in enumerate(stations):
            if math.dist((1000 * cylinder[0], 1000 * cylinder[2]), (x, z)) > 0.005:
                continue
            complete = True
            for depth in (0.05, (STACK_HEIGHT - POCKET_CEILING_Y) / 2.0,
                          STACK_HEIGHT - POCKET_CEILING_Y - 0.05):
                for angle in (0.071 + j * math.tau / 16 for j in range(16)):
                    target = (x + radius * math.cos(angle), STACK_HEIGHT - depth,
                              z + radius * math.sin(angle))
                    closest = face.GetClosestPointOn(*(value / 1000.0 for value in target))
                    if not isinstance(closest, (tuple, list)) or len(closest) != 5 or not all(
                        math.isfinite(float(v)) for v in closest
                    ):
                        raise RuntimeError(f"{tag}: finite cylinder closest-point unavailable")
                    if math.dist(tuple(1000 * float(v) for v in closest[:3]), target) > 0.005:
                        complete = False
            if complete:
                found.add(i)
    if found != set(range(len(stations))):
        raise RuntimeError(f"{tag}: missing retained tap-drill cylinder at stations {set(range(len(stations))) - found}")


def _verify_rib_material(adapter) -> None:
    """Read both retained ribs, their shared crossing and end-wall joins.

    Skin-only controls west of the shifted rib reject the former placement.
    Solid controls independently reject a deleted/shortened rib even when
    every seat still breaks through correctly.
    """
    for name, expected in (
        ("CrossRibX@CrossRibProfile",
         BOTTOM_LENGTH / 2.0 + CROSS_RIB_CENTER_X - RIB_THICKNESS / 2.0),
        ("CrossRibThickness@CrossRibProfile", RIB_THICKNESS),
        ("CrossRibLength@CrossRibProfile", 2.0 * RIB_HALF_LENGTH_Z),
        ("CrossRibHeight@CrossRib", POCKET_CEILING_Y - RIB_RELIEF),
        ("CrossRibRelief@CrossRib", RIB_RELIEF),
    ):
        _verify_named_dimension(adapter, name, expected)
    controls = (
        *((CROSS_RIB_CENTER_X, sz * POCKET_HALF_Z / 2.0, STACK_HEIGHT - RIB_RELIEF)
          for sz in (-1.0, 1.0)),
        *((sx * POCKET_HALF_X / 2.0, 0.0, STACK_HEIGHT - RIB_RELIEF)
          for sx in (-1.0, 1.0)),
        (CROSS_RIB_CENTER_X, 0.0, STACK_HEIGHT - RIB_RELIEF),
        *((CROSS_RIB_CENTER_X, sz * (POCKET_HALF_Z + POCKET_WALL / 4.0), STACK_HEIGHT)
          for sz in (-1.0, 1.0)),
        *((CROSS_RIB_CENTER_X - RIB_THICKNESS, sz * POCKET_HALF_Z / 2.0,
           STACK_HEIGHT - POCKET_CEILING_Y) for sz in (-1.0, 1.0)),
    )
    points = tuple((x, z) for x, z, _depth in controls)
    for (x, z, depth), actual in zip(
        controls, _native_vertical_segments(adapter, points, "retained rib controls"), strict=True,
    ):
        _require_native_segments(actual, ((0.0, depth),), f"retained rib at {(x, z)}")


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


# Only these two qualified planes are blacked by the registry Finish field;
# the qualified socket bores keep the body colour.
BLACK_FINISH_KEYS = ("deck", "underside")


async def _paint_machined_faces_black(adapter) -> None:
    """Qualify every spec-owned finish face, then black the two painted planes.

    Every remaining control's face is area-checked, so a wrong deck, underside
    or socket-wall selection fails before its finish control can be authored.
    """
    from solidworks_mcp.adapters.com_variant import double_array

    faces = resolve_faces(
        adapter.currentModel,
        {control.key: control.face for control in PART_SURFACE_FINISHES},
    )
    # The deck's flat ends where its break starts; the underside is the
    # perimeter foot inside the underside break: the flange outline less the
    # pocket opening, plus the socket bosses and pocket fillets that come
    # down flush with it. The deck area subtracts every opening and the stamp.
    deck_flat = _rounded_rect_area(
        DECK_LENGTH - 2.0 * DECK_EDGE_BREAK,
        DECK_WIDTH - 2.0 * DECK_EDGE_BREAK,
        DECK_CORNER_R - DECK_EDGE_BREAK,
    )
    deck_openings = sum(
        len(stations) * math.pi * (blind_cut_dia_mm(seat) / 2.0) ** 2
        for _tag, seat, stations, _envelope in THROUGH_SEAT_GROUPS
    )
    deck_flat -= deck_openings + SERIAL_AREA_MM2
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


HEIGHT_REFERENCE_ORIGIN = (-BOTTOM_LENGTH / 2.0, 0.0)
HEIGHT_REFERENCE_STATIONS = (
    (
        "GreenTopHeight",
        -TOP_LENGTH / 2.0,
        GREEN_TOP,
        '("BottomLength" - "TopLength") / 2',
        '"BottomThickness" + "TopThickness" - "DeckRise"',
    ),
    (
        "CrossScrewAxisHeight",
        -COLUMN_X,
        BASE_SCREW_Y,
        '"BottomLength" / 2 - "ColumnX"',
        '"BaseScrewY"',
    ),
)


async def _build_height_reference(adapter) -> None:
    """Locate the green land and cross-screw axis from one underside datum.

    Point-only construction geometry keeps the two .X heights independent,
    with no grey height lines in the drawing or changes to the physical solid.
    """
    check("create_sketch height reference", await adapter.create_sketch("Front"))
    manager = adapter.currentSketchManager
    previous = bool(manager.AddToDB)
    manager.AddToDB = True
    points = []
    try:
        coordinates = [
            HEIGHT_REFERENCE_ORIGIN,
            *((x, height) for _name, x, height, _dx, _dy in HEIGHT_REFERENCE_STATIONS),
        ]
        for x, y in coordinates:
            raw = manager.CreatePoint(x / 1000.0, y / 1000.0, 0.0)
            if raw is None:
                raise RuntimeError("height reference point creation failed")
            points.append(adapter._register_sketch_entity("Point", raw))
    finally:
        manager.AddToDB = previous

    dims = SketchDims()
    await anchor_point_to_origin(
        adapter, points[0], *HEIGHT_REFERENCE_ORIGIN, "height reference underside datum"
    )
    dims.record("HeightOriginX", '"BottomLength" / 2')
    for point, (name, x, height, x_drive, height_drive) in zip(
        points[1:], HEIGHT_REFERENCE_STATIONS, strict=True
    ):
        await anchor_point_to_point(
            adapter, points[0], point, x - HEIGHT_REFERENCE_ORIGIN[0], height,
            f"height reference {name}",
        )
        dims.record(f"{name}X", x_drive)
        dims.record(name, height_drive)
    await ensure_fully_defined(adapter, "height reference sketch")
    check("exit_sketch height reference", await adapter.exit_sketch())
    name_last_feature(adapter, "HeightReference")
    for dim_name, expr in dims.apply(adapter, "HeightReference"):
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    for name, _x, height, _dx, _dy in HEIGHT_REFERENCE_STATIONS:
        _verify_named_dimension(adapter, f"{name}@HeightReference", height)


async def _build_pivot_seat_reference(adapter) -> None:
    """Own D1's setup offsets without adding a wire or changing the solid.

    Two sketch points coincide in projection with the actual pedestal and
    pivot axes. Globals follow the same stations as the Hole Wizard cuts;
    only the two point-to-point offsets are marked for drawing.
    """
    near_x, near_z = PIVOT_NEAR_PEDESTAL_XZ
    near_y = -near_z
    anchor_names = ("PivotPedestalX", "PivotPedestalY")
    for name, value in zip(anchor_names, (near_x, near_y), strict=True):
        await set_global(adapter, name, f"{value}mm")
    for name, value in zip(PIVOT_SEAT_DIMENSIONS, PIVOT_SEAT_OFFSETS_MM, strict=True):
        await set_global(adapter, name, f"{value}mm")

    check("create_sketch pivot seat reference", await adapter.create_sketch("Top"))
    manager = adapter.currentSketchManager
    previous = bool(manager.AddToDB)
    manager.AddToDB = True
    points = []
    try:
        for label, (x, z) in (
            ("pedestal", PIVOT_NEAR_PEDESTAL_XZ),
            ("pivot", PIVOT_SCREW_XZ),
        ):
            raw = manager.CreatePoint(x / 1000.0, -z / 1000.0, 0.0)
            if raw is None:
                raise RuntimeError(f"pivot seat reference: {label} point creation failed")
            points.append(adapter._register_sketch_entity("Point", raw))
    finally:
        manager.AddToDB = previous

    dims = SketchDims()
    await anchor_point_to_origin(
        adapter, points[0], near_x, near_y, "pivot reference pedestal"
    )
    for name, value in zip(anchor_names, (near_x, near_y), strict=True):
        if abs(value) >= 1e-9:
            dims.record(name, _pos_drive(name, value))
    for name, direction, value in zip(
        PIVOT_SEAT_DIMENSIONS,
        ("horizontal_distance", "vertical_distance"),
        PIVOT_SEAT_OFFSETS_MM,
        strict=True,
    ):
        await dimension_between(
            adapter, points[0], points[1], direction, abs(value), f"pivot reference {name}"
        )
        dims.record(name, _pos_drive(name, value))
    await ensure_fully_defined(adapter, "pivot seat reference sketch")
    check("exit_sketch pivot seat reference", await adapter.exit_sketch())
    name_last_feature(adapter, "PivotSeatReference")
    for dim_name, expr in dims.apply(adapter, "PivotSeatReference"):
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    for name, value in zip(PIVOT_SEAT_DIMENSIONS, PIVOT_SEAT_OFFSETS_MM, strict=True):
        _verify_named_dimension(adapter, f"{name}@PivotSeatReference", abs(value))


REFERENCE_SKETCHES = (
    "HeightReference",
    "CrossTapReference",
    "PlanReference",
    "PivotSeatReference",
)


async def build(adapter) -> dict[str, str]:
    from solidworks_mcp.adapters.base import (
        CreatePlaneParameters,
        ExtrusionParameters,
        ImportDxfDwgParameters,
    )

    check("create_part", await adapter.create_part())
    apply_package_model_units(adapter, part_drawing_unit(PART_NAME), label=PART_NAME)

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
    await set_global(adapter, "CrossRibCenterX", f"{CROSS_RIB_CENTER_X}mm")
    await set_global(adapter, "RibRelief", f"{RIB_RELIEF}mm")
    await set_global(adapter, "SocketBossDia", f"{SOCKET_BOSS_DIA}mm")
    await set_global(adapter, "CrossTapLugBottom", f"{CROSS_TAP_LUG_BOTTOM_Y}mm")
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
    # from the underside to the ceiling, then retained sockets/ribs/lugs grown
    # back down into it. Through-seat volumes integrate this actual material;
    # an interrupted rib/wall is not mistaken for a uniform skin or blind drill.
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

    # Retained lugs and ribs are located from the hole table's own X0 Y0.
    # The flange's rear-west theoretical sharp corner remains their datum.
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
        location_drives: tuple[str | None, str | None] = (None, None),
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
        dims.record(location[0], location_drives[0])
        dims.record(location[1], location_drives[1])

    # Both ribs keep their full span, RIB_RELIEF clear of the bench and ending
    # mid-wall. Each is an offset-start boss, so its start offset IS the relief.
    # Each rib's NW corner is placed from X0 Y0 (CrossRibX locates the cross
    # rib's west face, LongRibY the long rib's rear face). The cross rib alone
    # translates by the spec-owned CrossRibCenterX; no local reliefs are cut.
    for tag, rib_shape, label, names, drives, location_drives in (
        (
            "LongRib",
            LONG_RIB_SHAPE,
            "long rib (z = 0)",
            ("LongRibLength", "LongRibThickness"),
            ('"TopLength" - "PocketWall"', '"RibThickness"'),
            (
                '("BottomLength" - ("TopLength" - "PocketWall")) / 2',
                '("BottomWidth" - "RibThickness") / 2',
            ),
        ),
        (
            "CrossRib",
            CROSS_RIB_SHAPE,
            f"cross rib (x = {CROSS_RIB_CENTER_X:g})",
            ("CrossRibThickness", "CrossRibLength"),
            ('"RibThickness"', '"TopWidth" - "PocketWall"'),
            (
                '("BottomLength" - "RibThickness") / 2 + "CrossRibCenterX"',
                '("BottomWidth" - ("TopWidth" - "PocketWall")) / 2',
            ),
        ),
    ):
        rib = SketchDims()
        check(f"create_sketch {label}", await adapter.create_sketch("Top"))
        origin = await _table_origin(rib, tag)
        # A line chain (_pad), not define_centered_rectangle: that native
        # center rectangle runs sketch inference, and the cross rib's 131.25
        # ends snapped to the deck edges at 130.25 seen through the Top plane
        # (farm leaf 2026-10-10: depth read back 260.5, the dimension became
        # driven, and the CrossRibLength equation failed the rebuild).
        await _pad(
            rib,
            rib_shape,
            label,
            list(names),
            list(drives),
            origin=origin,
            location=(f"{tag}X", f"{tag}Y"),
            location_drives=location_drives,
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

    # Retained cross-tap lugs keep their exact sketch geometry and bottom level.
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
        CROSS_TAP_LUG_BOTTOM_Y,
        "LugBottom",
        "CrossTapLugBottom",
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
                CROSS_TAP_LUG_BOTTOM_Y / 2.0,
                z - sz * math.sqrt(boss_r**2 - end_inset**2),
            ],
            [
                x - sx * math.sqrt(boss_r**2 - side_inset**2),
                POCKET_CEILING_Y / 2.0,
                sz * POCKET_HALF_Z,
            ],
        ]
        fillet_heights += [CROSS_TAP_LUG_BOTTOM_Y, POCKET_CEILING_Y]
    check(
        "fillet pocket boss junctions",
        await adapter.add_fillet(POCKET_CORNER_FILLET_R, fillet_picks, propagate=False),
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

    # The same radius on every retained rib/lug reentrant edge, so the one
    # R MAX dimension on PocketFillets continues to cover all of them.
    # No two of these edges share a vertex; each ends at sharp horizontal edges,
    # nothing propagates.
    corner_fillets = _pocket_corner_fillets(POCKET_CORNER_FILLET_R)
    check(
        "fillet pocket rib and lug corners",
        await adapter.add_fillet(
            POCKET_CORNER_FILLET_R,
            [pick for pick, _length, _area in corner_fillets],
            propagate=False,
        ),
    )
    name_last_feature(adapter, "PocketCornerFillets")
    v_corner_fillets = _pocket_corner_fillet_volume(POCKET_CORNER_FILLET_R)
    # 2 % + 5 (about 77 mm^3 at R.23): a dropped rib corner (about 255 mm^3)
    # fails the step; check() on add_fillet guards the shallower corners.
    after = await volume_check(
        adapter,
        "pocket corner fillets",
        after + v_corner_fillets,
        0.02 * v_corner_fillets + 5.0,
    )

    # Four native through 1/4-20 UNC-2B seats. Read the uncut casting first,
    # then prove real breakthrough and retained cylinder bounds after cutting.
    pre_holes = await _volume(adapter)
    _verify_uncut_material(adapter, "SupportHoldDownSeats", HOLD_DOWN_SEAT_SPEC, HOLE_XZ)
    fastener_cut = wizard_holes(
        adapter,
        HOLD_DOWN_SEAT_SPEC,
        [[x, STACK_HEIGHT, z] for x, z in HOLE_XZ],
        (0.0, 1.0, 0.0),
        "rocker-support through tapped seats (1/4-20 UNC-2B)",
        name="SupportHoldDownSeats",
        expect_dia_mm=HOLD_DOWN_TAP_DRILL_DIA,
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
    v_holes = _through_holes_volume_mm3(HOLD_DOWN_SEAT_SPEC, HOLE_XZ)
    _verify_through_breakthrough(adapter, "SupportHoldDownSeats", HOLD_DOWN_SEAT_SPEC, HOLE_XZ)
    _telemetry.info(
        f"volume after support seats: {after:.1f} mm^3 (removed analytic {v_holes:.1f})"
    )
    if abs((pre_holes - after) - v_holes) > 0.02 * v_holes:
        raise RuntimeError(
            f"support seats removed {pre_holes - after:.1f}, expected {v_holes:.1f}"
        )

    # Remaining native through-tapped groups retain all stations/thread classes.
    # Volume integrates the actual skin/rib/wall footprint; no drill point or
    # obsolete island metal is counted.
    for tag, spec, xz, label in (
        (
            "PivotSeat",
            PIVOT_SEAT_SPEC,
            (PIVOT_SCREW_XZ,),
            f"cone-pivot screw through-tapped seat ({PIVOT_THREAD} UNC-2B)",
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
            "pinion-pivot-block through-tapped seats (#8-32)",
        ),
        (
            "FootScrewHoles",
            FOOT_SEAT_SPEC,
            FOOT_SCREW_XZ,
            "foot-screw through-tapped seat (#4-40)",
        ),
        (
            "PedestalSeats",
            PEDESTAL_SEAT_SPEC,
            PEDESTAL_SCREW_XZ,
            "arbor-pedestal hold-down through-tapped seats (#8-32)",
        ),
        (
            "NameplateSeats",
            NAMEPLATE_SEAT_SPEC,
            NAMEPLATE_SCREW_XZ,
            "nameplate fillister-screw through-tapped seats (#4-40)",
        ),
    ):
        _verify_uncut_material(adapter, tag, spec, xz)
        wizard_holes(
            adapter,
            spec,
            [[sx, total, sz] for sx, sz in xz],
            (0.0, 1.0, 0.0),
            label,
            name=tag,
            expect_dia_mm=blind_cut_dia_mm(spec),
        )
        after_cut = await _volume(adapter)
        v_cut = _through_holes_volume_mm3(spec, xz)
        _verify_through_breakthrough(adapter, tag, spec, xz)
        if abs((after - after_cut) - v_cut) > 0.02 * v_cut:
            raise RuntimeError(
                f"{tag} removed {after - after_cut:.1f}, expected {v_cut:.1f}"
            )
        after = after_cut

    # Four blind column sockets from the green land beside the deck, nominal
    # Ø25.50: production bores are matched to their assigned actual MHA-FR-03
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
    _verify_rib_material(adapter)
    # Deferred equations must not close a hole or move its material boundary.
    for tag, seat, stations, _envelope in THROUGH_SEAT_GROUPS:
        _verify_through_breakthrough(adapter, tag, seat, stations)

    # Reference sketches own manufacturing dimensions with no single source
    # feature dimension. Save them blanked and import through the existing
    # hidden-owner curate in each drawing view. HeightReference uses points:
    # both the green land and cross-screw axis start on the faced underside,
    # so their .X bands cannot accumulate through flange/deck dimensions.
    await _build_height_reference(adapter)

    # The cross-tap X stations, each a baseline from the flange's west face
    # (the hole table's X0) along the tap axis, both from one start point.
    # The taps share their X with the A1-A4 bores, but the table locates only
    # the bores, and "ON A1-A4 X CENTRES" in the tap callout was a location
    # in a note (hb-render-4 eye pass).
    check("create_sketch cross-tap reference", await adapter.create_sketch("Front"))
    set_sketch_direct_db(adapter, True)
    tap_edge_ref = check(
        "cross-tap edge reference line",
        await adapter.add_line(
            -BOTTOM_LENGTH / 2.0, BASE_SCREW_Y, -COLUMN_X, BASE_SCREW_Y
        ),
    )
    tap_far_ref = check(
        "cross-tap far reference line",
        await adapter.add_line(
            -BOTTOM_LENGTH / 2.0, BASE_SCREW_Y, COLUMN_X, BASE_SCREW_Y
        ),
    )
    set_sketch_direct_db(adapter, False)
    for line in (tap_edge_ref, tap_far_ref):
        _as_construction(adapter, line)
        check(
            f"cross-tap reference {line} horizontal",
            await adapter.add_sketch_constraint(line, None, "horizontal"),
        )
    check(
        "cross-tap reference baseline",
        await adapter.add_sketch_constraint(
            f"{tap_edge_ref}.start", f"{tap_far_ref}.start", "coincident"
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
        f"{tap_far_ref}.start",
        f"{tap_far_ref}.end",
        "horizontal_distance",
        BOTTOM_LENGTH / 2.0 + COLUMN_X,
        "cross-tap far X from flange edge",
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
    name_dimensions(adapter, "CrossTapReference", ["CrossTapX", "CrossTapFarX"])
    _verify_named_dimension(
        adapter, "CrossTapX@CrossTapReference", BOTTOM_LENGTH / 2.0 - COLUMN_X
    )
    _verify_named_dimension(
        adapter, "CrossTapFarX@CrossTapReference", BOTTOM_LENGTH / 2.0 + COLUMN_X
    )

    # The plan stations of the pad, the deck and the underside pocket from
    # the hole table's X0 Y0 (the flange's rear-west theoretical sharp
    # corner). The plates are centred, so their own Len/Wid dims fix only
    # their sizes; these baselines, each from the one X0 Y0 point along the
    # flange's rear edge (X) or west edge (Y), place them from the datum
    # every other plan location is measured from. Driven by the plate
    # globals, so a footprint edit moves the printed stations with it.
    # Top-plane sketch y is machine -Z: the rear edge lies at y = -width/2.
    plan = SketchDims()
    plan_x0, plan_y0 = -BOTTOM_LENGTH / 2.0, -BOTTOM_WIDTH / 2.0
    plan_rows = (
        (
            "PadX",
            "horizontal",
            (BOTTOM_LENGTH - TOP_LENGTH) / 2.0,
            '("BottomLength" - "TopLength") / 2',
        ),
        (
            "PadY",
            "vertical",
            (BOTTOM_WIDTH - TOP_WIDTH) / 2.0,
            '("BottomWidth" - "TopWidth") / 2',
        ),
        (
            "DeckX",
            "horizontal",
            BOTTOM_LENGTH / 2.0 - DECK_HALF_X,
            '("BottomLength" - "DeckLength") / 2',
        ),
        (
            "DeckY",
            "vertical",
            BOTTOM_WIDTH / 2.0 - DECK_HALF_Z,
            '("BottomWidth" - "DeckWidth") / 2',
        ),
        (
            "PocketX",
            "horizontal",
            BOTTOM_LENGTH / 2.0 - POCKET_HALF_X,
            '("BottomLength" - "TopLength") / 2 + "PocketWall"',
        ),
        (
            "PocketY",
            "vertical",
            BOTTOM_WIDTH / 2.0 - POCKET_HALF_Z,
            '("BottomWidth" - "TopWidth") / 2 + "PocketWall"',
        ),
    )
    check("create_sketch plan reference", await adapter.create_sketch("Top"))
    set_sketch_direct_db(adapter, True)
    plan_lines = []
    for name, direction, value, _drive in plan_rows:
        end_x = plan_x0 + (value if direction == "horizontal" else 0.0)
        end_y = plan_y0 + (value if direction == "vertical" else 0.0)
        plan_lines.append(
            check(
                f"plan reference {name} line",
                await adapter.add_line(plan_x0, plan_y0, end_x, end_y),
            )
        )
    set_sketch_direct_db(adapter, False)
    for line, (name, direction, _value, _drive) in zip(
        plan_lines, plan_rows, strict=True
    ):
        _as_construction(adapter, line)
        check(
            f"plan reference {name} {direction}",
            await adapter.add_sketch_constraint(line, None, direction),
        )
    for line in plan_lines[1:]:
        check(
            f"plan reference {line} from X0 Y0",
            await adapter.add_sketch_constraint(
                f"{line}.start", f"{plan_lines[0]}.start", "coincident"
            ),
        )
    await anchor_point_to_origin(
        adapter, f"{plan_lines[0]}.start", plan_x0, plan_y0, "plan reference X0 Y0"
    )
    plan.record("PlanOriginX", '"BottomLength" / 2')
    plan.record("PlanOriginY", '"BottomWidth" / 2')
    for line, (name, direction, value, drive) in zip(
        plan_lines, plan_rows, strict=True
    ):
        await dimension_between(
            adapter,
            f"{line}.start",
            f"{line}.end",
            f"{direction}_distance",
            value,
            f"plan reference {name}",
        )
        plan.record(name, drive)
    await ensure_fully_defined(adapter, "plan reference sketch")
    check("exit_sketch plan reference", await adapter.exit_sketch())
    name_last_feature(adapter, "PlanReference")
    # The main drive batch ran before the reference sketches existed.
    for dim_name, expr in plan.apply(adapter, "PlanReference"):
        await drive_dimension(adapter, dim_name, expr)
    await force_rebuild(adapter)
    for name, _direction, value, _drive in plan_rows:
        _verify_named_dimension(adapter, f"{name}@PlanReference", value)
    await _build_pivot_seat_reference(adapter)
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
    # and the drawing only reads them back (drawing-simplicity-policy.md `How the repository implements the guidelines`). Same for the one
    # dimension whose band is not the title block's: a spotface may run deep,
    # never shallow, or the screw head rocks on an unfaced ring.
    apply_drawing_precision(adapter, DRAWING_PRECISION)
    set_dimension_bilateral_tolerance(
        adapter,
        "BaseSpotFaceRear",
        "SpotFaceDepth",
        *deviations(SPOTFACE_DEPTH_BAND_MM),
    )
    for dimension_name in PIVOT_SEAT_DIMENSIONS:
        set_dimension_symmetric_tolerance(
            adapter, "PivotSeatReference", dimension_name, PIVOT_SEAT_POSITION_BAND_MM
        )
    # Every pocket corner fillet prints as one single limit, "R.23 MAX":
    # swTolMAX prints the nominal then MAX, so the modelled radius IS the max.
    _display, fillet_radius = _named_dimension(
        adapter, "PocketFillets", "PocketFilletRadius"
    )
    tolerance = _early_bound(fillet_radius.Tolerance, "IDimensionTolerance")
    tolerance.Type = POCKET_FILLET_TOL_TYPE
    if int(tolerance.Type) != POCKET_FILLET_TOL_TYPE:
        raise RuntimeError(
            "PocketFilletRadius@PocketFillets: MAX limit did not persist"
        )
    # A pair's shared size or coordinate prints once, as "2X": the count is
    # specification, so the part owns it like the places.
    for (feature_name, dimension_name), prefix in UNDERSIDE_LOCATION_PREFIXES.items():
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
