"""Offline manufacturing contracts for the cone-swing-platform package."""

from __future__ import annotations

import math

import _config
import build_cone_pivot_screw
import build_cone_swing_platform as part
import cone_pivot_post_spec
import cone_swing_platform_spec as spec
import draw_cone_swing_platform as drawing
import pytest
from _gtol_spec import PlanarFace
from _hole_spec import blind_cut_dia_mm
from _surface_finish import MACHINED_UM, SEAT_UM




def test_every_marked_model_dimension_has_one_view_and_native_precision() -> None:
    assert part.DRAWING_DIMENSIONS is spec.DRAWING_DIMENSIONS
    marked = set().union(*spec.DRAWING_DIMENSIONS.values())
    view_sets = (
        set(drawing.PROFILE_KEEP),
        set(drawing.FEATURE_KEEP),
        set(drawing.NOTCH_KEEP),
        set(drawing.SECTION_KEEP),
        set(drawing.DETAIL_KEEP),
        set(drawing.SLOT_SECTION_KEEP),
    )
    kept = set().union(*view_sets)
    assert kept == marked
    assert sum(len(names) for names in view_sets) == len(kept)
    assert set(spec.DRAWING_PRECISION_BY_NAME) == marked
    assert spec.DRAWING_PRECISION_BY_NAME["PlateLenDim"] == 1
    assert set(spec.DRAWING_PRECISION_BY_NAME.values()) == {1, 2}


def test_pivot_preserves_native_close_clearance_hole() -> None:
    assert spec.PIVOT_HOLE_SPEC.kind == "clearance"
    assert spec.PIVOT_HOLE_SPEC.size == "1/4"
    assert spec.PIVOT_HOLE_SPEC.fit == "close"
    assert spec.PIVOT_HOLE_SPEC.end == "through_all"
    assert spec.PIVOT_HOLE_DIA == blind_cut_dia_mm(spec.PIVOT_HOLE_SPEC)
    assert spec.PIVOT_HOLE_DIA == pytest.approx(6.756)
    assert spec.PIVOT_HOLE_DIA > build_cone_pivot_screw.SHOULDER_DIA


def test_post_mount_pattern_is_derived_from_its_mating_post() -> None:
    assert spec.POST_ATTACHMENT_SPACING == cone_pivot_post_spec.ATTACHMENT_SPACING
    assert spec.POST_BLOCK_DIA == cone_pivot_post_spec.BLOCK_DIA
    assert part.POST_MOUNT_HALF_PITCH == spec.POST_ATTACHMENT_SPACING / 2.0
    assert math.isclose(
        math.hypot(
            part.POST_MOUNT_WEST_XZ[0] - part.POST_MOUNT_EAST_XZ[0],
            part.POST_MOUNT_WEST_XZ[1] - part.POST_MOUNT_EAST_XZ[1],
        ),
        spec.POST_ATTACHMENT_SPACING,
    )
    assert spec.POST_MOUNT_SPEC.kind == "tapped"
    assert spec.POST_MOUNT_SPEC.size == "1/4-20"
    assert spec.POST_MOUNT_SPEC.end == "through_all"
    assert spec.POST_MOUNT_TAP_DIA == blind_cut_dia_mm(spec.POST_MOUNT_SPEC)


def test_only_sliding_and_locating_surfaces_carry_roughness() -> None:
    by_key = {control.key: control for control in spec.SURFACE_FINISHES}
    assert set(by_key) == {"post_seat", "base_slide"}
    assert by_key["post_seat"].roughness_um == SEAT_UM
    assert by_key["post_seat"].face == PlanarFace(
        (0, 1, 0), spec.PLATE_THICKNESS
    )
    assert by_key["base_slide"].roughness_um == MACHINED_UM
    assert by_key["base_slide"].face == PlanarFace((0, -1, 0), 0.0)


def test_plate_and_nonfit_features_remain_at_general_grade() -> None:
    registry = _config.parts("cone-swing-platform")
    assert registry["tolerance_class"] == "machined_block"
    assert "mil-dtl-13924 class 1" in str(registry["finish"]).lower()
    assert "oil seal" in str(registry["finish"]).lower()
    assert int(registry["quantity"]) == 1
    assert spec.DRAWING_PRECISION["Plate"]["PlateThk"] == 2
    assert spec.DRAWING_PRECISION["PivotBearingRelief"]["PivotBearingReliefDepth"] == 2
    assert spec.DRAWING_PRECISION["PostMountHoles"] == {
        "PostMountWestX": 2,
        "PostMountWestZ": 2,
        "PostMountEastX": 2,
        "PostMountEastZ": 2,
    }






def test_geometry_cascade_and_interference_guards_stay_explicit() -> None:
    assert part.PLATE_LEN == pytest.approx(223.3541869456341)
    assert part.POST_SOUTH_MARGIN == pytest.approx(3.175)
    assert part.PLATE_SOUTH_Z == pytest.approx(-216.3541869456341)
    assert part.POST_MAIN_DIA == spec.POST_BLOCK_DIA
    assert part.POST_FOOT_CONTAINMENT >= 0.25
    assert spec.PIVOT_BEARING_RELIEF_DIAMETER == pytest.approx(10.50)
    assert part.PLATE_T - spec.PIVOT_BEARING_THICKNESS == pytest.approx(
        spec.PIVOT_BEARING_RELIEF_DEPTH
    )
    assert spec.CRANK_GEAR_PLATFORM_CLEARANCE > 0.5


def test_pivot_relief_runs_out_through_the_north_edge() -> None:
    """Rule-12 W18 (d): no web is left between the relief and the north edge.

    As a closed Ø10.50 spotface 7.0 from the edge it left 1.75 nominal, under
    the 2.0 target.  Open to the edge, the web does not exist; the relief's
    sketch closes PIVOT_RELIEF_RUNOUT past it, and the width still gives the
    stock 3/8 head its radial clearance.
    """
    half = spec.PIVOT_BEARING_RELIEF_DIAMETER / 2.0
    closed_web = part.NORTH_OVERHANG - half
    assert closed_web < 2.0  # positive control: the closed spotface failed
    assert part.PIVOT_RELIEF_RUNOUT > 0.0
    head_dia = build_cone_pivot_screw.HEAD_DIA
    assert (spec.PIVOT_BEARING_RELIEF_DIAMETER - head_dia) / 2.0 >= (
        spec.PIVOT_HEAD_RADIAL_CLEARANCE - 1e-9
    )
    assert spec.PIVOT_RELIEF_FIT_REQUIREMENT.startswith(
        "TOP PIVOT RELIEF: MATCH DEPTH TO FINISHED PLATE"
    )
    # Only the NW fillet reaches over the 10.50 strip, and only by a sliver.
    overlaps = {
        label: part._north_fillet_relief_overlap(label, r)
        for label, _x, _z, r in part._CORNERS
    }
    assert overlaps["NE"] == 0.0 and overlaps["SW"] == 0.0 and overlaps["SE"] == 0.0
    assert 0.0 < overlaps["NW"] < part._corner_fillet_area("NW", 8.0)


def test_disengaged_collar_margin_survives_general_bands() -> None:
    """Linear worst case at .X plate outline and .XX base holes keeps 2.0 mm (U27)."""
    general, base_axis = 0.8, 0.51
    east_slope = (part.EAST_HALF_S - part.HALF_WIDTH_N) / part.PLATE_LEN
    stop_x = -(part.HALF_WIDTH_N + east_slope * (part.NORTH_OVERHANG - part.STOP_LOCAL_Z))
    normal = (-1.0, east_slope)
    norm = math.hypot(*normal)
    lever = abs(part.STOP_LOCAL_Z * normal[0] - stop_x * normal[1]) / norm
    stop_gain = part.SLOT_R / lever
    east_edge = stop_gain * general
    west_edge = general
    stop_hole = stop_gain * base_axis * (abs(normal[0]) + abs(normal[1])) / norm
    stud_hole = base_axis * (abs(part._SLOT_TX) + abs(part._SLOT_TZ))
    diameters = 0.35
    worst = part.DISENGAGE_COLLAR_MARGIN - (
        east_edge + west_edge + stop_hole + stud_hole + diameters
    )
    assert worst >= 2.0
    assert set(spec.DRAWING_PRECISION["PlateProfile"].values()) == {1}


def _boxes_overlap(a: tuple[float, ...], b: tuple[float, ...]) -> bool:
    return a[0] < b[2] and b[0] < a[2] and a[1] < b[3] and b[1] < a[3]


def test_detail_band_clears_border_title_block_and_captions() -> None:
    """Detail B, its label and callouts, and the relief note share one band.

    Extents are the ones the layout audit logged on the farm (runs 2b643c17
    and e86bf319): the native label is 31.5 x 16.2 mm; the relief note
    0.0947 x 0.0176 m from its upper-left anchor; a vertical dimension's
    text hangs OUTWARD from its line -- the counterbore callout (value and
    four lines) spans x..x+0.042 by y-0.016..y+0.015, the through-slot
    callout x-0.035..x+0.003 by y-0.010..y+0.009.  e86bf319 failed on the
    label alone (8.9 mm through the bottom border); its callouts also ran
    under the title block and the plan caption, which the audit's nominal
    dimension boxes cannot see.  At 1:1 (7959e994) the texts also crossed
    the detail circle, so the circle and the 11.00 / 2.00 texts (~12 x 5 mm,
    right of / centred on their anchors) are boxed too.
    """
    border_bottom, title_block = 0.0127, (0.216, 0.0, 0.4318, 0.066)
    captions = (
        (0.0449, 0.0805, 0.1059, 0.0853),
        (0.1497, 0.0805, 0.2185, 0.0853),
    )
    label_x, label_y = drawing.DETAIL_LABEL_LOWER_LEFT
    label = (label_x, label_y, label_x + 0.0315, label_y + 0.0162)
    note_x, note_y = drawing.RELIEF_NOTE_XY
    relief = (note_x, note_y - 0.0176, note_x + 0.0947, note_y)
    cbore_x, cbore_y = drawing.DETAIL_KEEP["TipCboreW"]
    cbore = (cbore_x, cbore_y - 0.016, cbore_x + 0.042, cbore_y + 0.015)
    slot_x, slot_y = drawing.DETAIL_KEEP["TipSlotW"]
    slot = (slot_x - 0.035, slot_y - 0.010, slot_x + 0.003, slot_y + 0.009)
    cx, cy = drawing.DETAIL_CENTER
    r = drawing.DETAIL_SHEET_RADIUS
    circle = (cx - r, cy - r, cx + r, cy + r)
    z_x, z_y = drawing.DETAIL_KEEP["TipSlotZ"]
    slot_z = (z_x + 0.001, z_y - 0.0025, z_x + 0.013, z_y + 0.0025)
    east_x, east_y = drawing.DETAIL_KEEP["TipSlotEastCx"]
    west_x, west_y = drawing.DETAIL_KEEP["TipSlotWestCx"]
    east = (east_x - 0.006, east_y - 0.0025, east_x + 0.006, east_y + 0.0025)
    west = (west_x - 0.006, west_y - 0.0025, west_x + 0.006, west_y + 0.0025)
    boxes = {
        "label": label,
        "relief": relief,
        "cbore": cbore,
        "slot": slot,
        "circle": circle,
        "slot z": slot_z,
        "east 2.00": east,
        "west 2.00": west,
    }
    for name, box in boxes.items():
        assert box[1] > border_bottom + 0.001, name
        assert box[0] > 0.0127 + 0.001, name
        assert not _boxes_overlap(box, title_block), name
        for caption in captions:
            assert not _boxes_overlap(box, caption), (name, caption)
    names = list(boxes)
    for i, first in enumerate(names):
        for second in names[i + 1 :]:
            assert not _boxes_overlap(boxes[first], boxes[second]), (first, second)
    # Positive control: e86bf319's layout fails this very check.
    old_label = (0.1443, 0.0038, 0.1758, 0.0200)
    old_cbore = (0.196, 0.072 - 0.016, 0.196 + 0.042, 0.072 + 0.015)
    assert old_label[1] < border_bottom
    assert _boxes_overlap(old_cbore, title_block)
    assert _boxes_overlap(old_cbore, captions[1])


def test_slot_section_pocket_clears_its_neighbours() -> None:
    """Section C-C, its label and its depth text fit the pocket they are given.

    Neighbour boxes are the extents the layout audit logged on the farm
    (runs 2b643c17 and e86bf319): the notch plan, its caption, the relief
    dimension RD1, and section A-A's outline, finish symbol and thickness
    text.  The strip is the plate edge-on at 1:1 plus SolidWorks' ~4 mm
    outline padding; the native label measured 46.5 x 16.2 mm.
    """
    neighbours = {
        "notch view": (0.2394, 0.1286, 0.2806, 0.2514),
        "notch caption": (0.2448, 0.0805, 0.3045, 0.0853),
        "RD1": (0.1900, 0.1042, 0.2460, 0.1077),
        "section A-A": (0.3246, 0.1081, 0.3854, 0.1319),
        "A-A finish": (0.3160, 0.1056, 0.3276, 0.1081),
        "A-A thickness": (0.3084, 0.1322, 0.3245, 0.1357),
        "title block": (0.216, 0.0, 0.4318, 0.066),
    }
    half = drawing.SLOT_SECTION_HALF_SPAN_MM / 1000.0 + 0.004
    cx, cy = drawing.SLOT_SECTION_CENTER
    strip = (cx - half, cy - 0.0072, cx + half, cy + 0.0072)
    lx, ly = drawing.SLOT_SECTION_LABEL_LOWER_LEFT
    label = (lx, ly, lx + 0.0465, ly + 0.0162)
    dx, dy = drawing.SLOT_SECTION_KEEP["TipCboreDepth"]
    depth = (dx - 0.012, dy - 0.004, dx, dy + 0.004)
    ours = {"C-C strip": strip, "C-C label": label, "depth text": depth}
    for name, box in ours.items():
        for other, neighbour in neighbours.items():
            assert not _boxes_overlap(box, neighbour), (name, other)
    assert not _boxes_overlap(strip, label)
    # Positive control: the pocket is real -- moving the strip onto the
    # notch caption row is caught.
    moved = (strip[0], 0.078, strip[2], 0.092)
    assert _boxes_overlap(moved, neighbours["notch caption"])
