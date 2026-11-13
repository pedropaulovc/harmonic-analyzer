r"""Create the cylinder gears' cam turning fixture kit's fitter sheets (MHA-DT-12-TL-00).

The kit is the fixture body (item 1, MHA-DT-12-TL-01) with its pressed stub
(item 2) and clock pin (item 3), and the clamp washer (item 4) and screw
(item 5) that hold each MHA-DT-12 gear while its cam is turned in the lathe
(issue #2361). The gear is the workpiece: never placed in the model, drawn
in phantom on the exploded sheet only.

Sheet 1: the top view (items 4 and 5 off) with the cam throw and the clock
pin's station from the register axis as native reference dimensions, the
front view projected under it at the same 1:1 with item 1 ballooned, the
shaded isometric with items 2-5 ballooned, the BOM, the kit's one-time
presses, the three fitting steps (the gear is turned CLOCKWISE in the top
view onto item 3 before item 5 is tightened: the cut then pushes it harder
onto the pin) and the checks.
Sheet 2: the exploded right view, items 4 and 5 and the phantom gear drawn
off the stub's axis in fitting order. Numbers come from
``dt_cylinder_gear_tl_cam_fixture_spec``; this recipe never edits the source
assembly.

Run only through the supervised farm launcher:
``drawing:dt_cylinder_gear_tl_cam_turning_assembly``.
"""

from __future__ import annotations

import argparse
import math
import sys
from collections.abc import Callable
from typing import Any

import _config
import _telemetry
import dt_cylinder_gear_spec as gear
import dt_cylinder_gear_tl_cam_fixture_spec as fixture
from _assembly_contract import assembly_contract
from _check import check
from _com import _early_bound
from _drawing_balloons import (
    BalloonAnchor,
    add_component_bom_balloons,
    assert_balloon_landings,
    isolate_drawing_view_components,
)
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    rebuild_drawing,
    set_high_quality_shaded_with_edges,
)
from _drawing_dimensions import set_reference_dimension
from _drawing_edge_dimensions import add_edge_dimension, assert_dimension_measures
from _drawing_leader_notes import add_leader_note
from _drawing_projection import model_points_in_view
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_sheets import create_blank_drawing_sheets
from _drawing_tables import insert_bom_table
from _drawing_types import DRAWING_TEMPLATES, DrawingLayout
from _drawing_view_configuration import (
    ViewRole,
    apply_view_configuration,
    assert_full_detail_view,
)
from _drawing_view_display import set_hidden_lines_removed
from _machinist_review_mode import MachinistReviewMode
from _mcmaster_91251a337 import DIMS as SCREW
from _session import run_build
from _transgear_zone_line import require_placed, sketch_lines
from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import add_note, place_view

# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE
SPEC = DRAWINGS_BY_NAME["dt_cylinder_gear_tl_cam_turning_assembly"]
ARTIFACT_STEM = SPEC.artifact_stem
SOURCE = SPEC.source
OUTPUTS = DrawingOutputs(
    slddrw=SPEC.outputs["slddrw"],
    pdf=SPEC.outputs["pdf"],
    png=SPEC.outputs["png"],
)
if SPEC.layout is not DrawingLayout.LANDSCAPE:
    raise AssertionError("the cam turning kit sheets must remain landscape")

CONTRACT = assembly_contract("dt-cylinder-gear-tl-cam-turning")
DRAWING_NUMBER = CONTRACT.number
SHEET_SCALE = (1.0, 1.0)
DETAIL_SCALE = (2.0, 1.0)
ISO_SCALE = (1.0, 2.0)
SHEET_NAMES = ("ASSEMBLY", "EXPLODED VIEW")
SHEET_LAYOUTS = {name: DrawingLayout.LANDSCAPE for name in SHEET_NAMES}
SHEET_SCALES = {SHEET_NAMES[0]: SHEET_SCALE, SHEET_NAMES[1]: DETAIL_SCALE}
_TEMPLATE = DRAWING_TEMPLATES[DrawingLayout.LANDSCAPE]
SHEET_INNER_BORDER = (
    0.0127,
    0.0127,
    _TEMPLATE.width_m - 0.0127,
    _TEMPLATE.height_m - 0.0127,
)

BODY = fixture.PART_NAME
STUB = "dt-cylinder-gear-tl-vn-cam-stub"
CLOCK_PIN = "dt-cylinder-gear-tl-vn-cam-clock-pin"
WASHER = "dt-cylinder-gear-tl-vn-cam-clamp-washer"
SCREW_STEM = "dt-cylinder-gear-tl-vn-cam-clamp-screw"
# The kit's insertion order, which the BOM numbers its items by.
BOM_COMPONENTS = (BODY, STUB, CLOCK_PIN, WASHER, SCREW_STEM)
BOM_ITEMS = {stem: str(index + 1) for index, stem in enumerate(BOM_COMPONENTS)}
# Each item's drawing Number, the BOM's PART NUMBER cell.
BOM_PART_NUMBERS = {
    BODY: fixture.PART_NUMBER,
    STUB: fixture.STUB_NUMBER,
    CLOCK_PIN: fixture.CLOCK_PIN_NUMBER,
    WASHER: str(_config.parts("dt-cylinder-gear-tl-vn-cam-clamp-washer")["number"]),
    SCREW_STEM: str(_config.parts("dt-cylinder-gear-tl-vn-cam-clamp-screw")["number"]),
}
BOM_DESCRIPTIONS = {
    BODY: "CAM TURNING FIXTURE BODY",
    STUB: "STUB, 3/8 X 3/4 PULL-OUT DOWEL, 10-32 TAPPED",
    CLOCK_PIN: "CLOCK PIN, .0375 GAUGE PIN CUT TO LENGTH",
    WASHER: "NO. 10 FLAT WASHER",
    SCREW_STEM: "10-32 X 5/16 SHCS",
}
BOM_COMPONENT_IDENTITIES: dict[str, tuple[str, str | None]] = {
    stem: (stem, None) for stem in BOM_COMPONENTS
}
# Item 1 balloons in the front view, items 2-5 in the shaded isometric. A
# side view sees every round item's rims edge-on, each drawn as one line
# across the item's axis, and on a short line no anchor holds: run
# 20261112T203156536Z walked item 2 to its top rim 1.42 mm (sheet) in from
# the line's end and the leader read back on the end (_assert_leader_lands,
# limit 0.2 mm); frozen points on those rims then probed as no edge at all
# (run 20261113T012650242Z, item 5's head top; run 20261113T042822797Z,
# item 2's top rim .025 short of the line's end). Item 1's walked rim point
# on its long rim line landed where asked (runs 20261112T203156536Z and
# 20261113T085510850Z, then in the right view). The isometric draws every
# bought item's rims as ellipses, so each walks its own body there (run
# 20261113T085510850Z placed all four), as the fly cutter's set screw does
# on its end-on bottom view (draw_dt_cone_tip_gear_tl_cutter_assembly).
BALLOON_ANCHORS = {stem: BalloonAnchor() for stem in BOM_COMPONENTS}
FRONT_ITEMS = (BODY,)
ISO_ITEMS = (STUB, CLOCK_PIN, WASHER, SCREW_STEM)
if FRONT_ITEMS + ISO_ITEMS != BOM_COMPONENTS:
    raise AssertionError("every BOM row is ballooned once")
BALLOON_MARGIN = 0.012


def _kit(body_xyz: tuple[float, float, float]) -> tuple[float, float, float]:
    """A body-frame point (mm) in the kit frame, metres for the projection."""
    return tuple(value / 1000.0 for value in fixture.kit_point(body_xyz))


# Sheet metres, sheet 1. The top view and the front view are one third-angle
# pair at the sheet's 1:1: each is placed by the register's face centre at
# the same x, so the top view projects straight up off the front view (run
# 20261113T085510850Z's review: a 1:1 top view over a 2:1 right view turned
# 90 deg is no projected pair). The front view shows the clock pin behind
# the stub; sheet 2's exploded right view shows it. The isometric sits
# under them with its balloon ring inside the left border and clear of the
# title block (x >= 0.216 m, y <= 0.066 m): run 20261113T085510850Z rang
# items 2 and 4 outside the border from x .045; run 20261113T171903296Z,
# from (.060, .052), still put item 2's circle 1.67 mm over it (left edge
# x 11.0 mm) and item 5's 1.38 mm from the front view's item 1. The
# isometric moved 14 mm right and 5 mm down (item 2's edge at about 25 mm,
# 12 mm inside) and the front view 15 mm up (items 1 and 5 about 15 mm apart,
# centre to centre), every view and balloon translating with its view. The
# BOM, steps and checks fill the right half, the steps under the BOM's
# two-line rows (run 20261113T085510850Z printed them over rows 4 and 5
# from y .214).
TOP_CENTER = (0.090, 0.200)
FRONT_CENTER = (TOP_CENTER[0], 0.135)
ISO_CENTER = (0.074, 0.047)
TOP_CAPTION_XY = (0.140, 0.255)
FRONT_CAPTION_XY = (0.150, 0.115)
ISO_NOTE_XY = (0.119, 0.035)
BOM_ANCHOR = (0.219, 0.262)
STEPS_XY = (0.219, 0.184)
CHECKS_XY = (0.219, 0.112)
# The view placing point: the register axis on the body's front face.
REGISTER_FACE_MM = (0.0, 0.0, fixture.THICKNESS)
TOP_CAPTION = "TOP VIEW\nITEMS 4 AND 5 OFF"
FRONT_CAPTION = "FRONT VIEW"
ISO_NOTE = f"ISOMETRIC VIEW SCALE {ISO_SCALE[0]:g}:{ISO_SCALE[1]:g}"

# Reference dimensions in the top view: the throw and the clock pin's
# station, each from the register's centre (the lathe axis once item 1 is
# indicated true), at the body sheet's printed places.
REFERENCE_PLACES = fixture.POSITION_PLACES
_R = fixture.BODY_DIA / 2.0
_STUB_R = fixture.DOWEL_DIA / 2.0
_PIN_R = fixture.PIN_DIA / 2.0
_STUB_TOP = fixture.THICKNESS + fixture.STUB_STAND
_PIN_TOP = fixture.THICKNESS + fixture.PIN_STAND
REGISTER_PICK = (-_R, 0.0, fixture.THICKNESS)
STUB_PICK = (-_STUB_R, -fixture.STUB_OFFSET, _STUB_TOP)
PIN_PICK = (fixture.PIN_X - _PIN_R, fixture.PIN_Y, _PIN_TOP)
# name -> (second pick, orientation, expected mm, text offset from TOP_CENTER)
REFERENCE_DIMENSIONS = {
    "cam throw": (STUB_PICK, "vertical", fixture.STUB_OFFSET, (0.052, -0.004)),
    "clock pin height": (PIN_PICK, "vertical", fixture.PIN_Y, (0.052, 0.012)),
    "clock pin offset": (PIN_PICK, "horizontal", -fixture.PIN_X, (-0.012, 0.052)),
}

KIT_STEPS = "\n".join(
    (
        "KIT ASSEMBLY (ONCE)",
        "K1. PRESS ITEM 2 INTO ITEM 1 FROM THE FACE SEEN IN THE TOP VIEW,",
        f"    TAPPED END OUT, UNTIL IT STANDS {fixture.STUB_STAND_TEXT} ABOVE THE FACE",
        "    (CALIPER DEPTH ROD).",
        "K2. PRESS ITEM 3 TO THE FLOOR OF ITS HOLE.",
    )
)
# At most three fitting steps; the turning direction before clamping is
# CUT_TURNS_GEAR_CLOCKWISE's (spec).
FITTING_STEPS = "\n".join(
    (
        "FITTING STEPS (ONE GEAR AT A TIME; ITEM 1 STAYS IN THE 4-JAW,",
        "ITS REGISTER INDICATED TRUE)",
        "1. SLIDE THE GEAR'S BORE ONTO ITEM 2, CAM BOSS AWAY FROM ITEM 1,",
        "   ITS NOTCHED TOOTH SPACE OVER ITEM 3 (SHEET 2).",
        "2. TURN THE GEAR CLOCKWISE IN THE TOP VIEW UNTIL THE NOTCHED",
        "   SPACE STOPS ON ITEM 3, AND HOLD IT THERE.",
        "3. FIT ITEM 5 THROUGH ITEM 4 INTO ITEM 2; TIGHTEN FIRMLY (5/32 KEY).",
        "   ITEM 5 ENGAGES ITEM 2'S THREAD",
        f"   {fixture.SCREW_ENGAGEMENT_TEXT}.",
    )
)
ASSEMBLY_STEPS = f"{KIT_STEPS}\n{FITTING_STEPS}"
ASSEMBLY_CHECKS = "\n".join(
    (
        "CHECKS",
        "1. WITH ITEM 1'S REGISTER TRUE, A 1 IN DIAL INDICATOR ON ITEM 2",
        f"   READS {fixture.STUB_RUNOUT_TEXT} TIR.",
        "2. A GEAR'S NOTCHED SPACE ENTERS ITEM 3 WITH THE GEAR FLAT ON ITEM 1.",
        "3. ITEMS 2 AND 3 DO NOT MOVE BY HAND.",
        "4. AFTER STEP 3 THE GEAR DOES NOT TURN BY HAND.",
    )
)
if (
    not fixture.CUT_TURNS_GEAR_CLOCKWISE
    or "CLOCKWISE IN THE TOP VIEW" not in FITTING_STEPS
):
    raise AssertionError("step 2 must turn the gear the way the cut pushes it")

# --- sheet 2: the exploded view ----------------------------------------------
# The kit's right view at 2:1 with items 1-3 seated; the phantom gear, item 4
# and item 5 drawn off item 2's axis in fitting order, each GAP above the
# last. Kit-frame millimetres: the right view's horizontal is kit Z, its
# vertical kit Y; item 2's axis stands at kit z = +STUB_OFFSET.
EXPLODED_CENTER = (0.120, 0.100)
GAP = 8.0
AXIS_Z = fixture.STUB_OFFSET
GEAR_Y0 = _STUB_TOP + GAP
GEAR_DISC_TOP = GEAR_Y0 + gear.FACE_WIDTH
GEAR_TOP = GEAR_Y0 + gear.OVERALL_THICKNESS
GEAR_TIP_R = gear.OUTSIDE_DIA / 2.0
CAM_R = gear.CAM_DIA / 2.0
WASHER_Y0 = GEAR_TOP + GAP
WASHER_TOP = WASHER_Y0 + fixture.WASHER_MODEL_THICKNESS
SCREW_SEAT_Y = WASHER_TOP + GAP
SCREW_TIP_Y = SCREW_SEAT_Y - SCREW.length
SCREW_TOP_Y = SCREW_SEAT_Y + SCREW.head_h
AXIS_OVERRUN = 3.0
# Line fonts (swLineStyles_e / swLineWeights_e): the gear in thin phantom,
# the loose items as visible outlines, the axis a thin centre line.
PHANTOM_STYLE, PHANTOM_WIDTH = 2, 0
ITEM_STYLE, ITEM_WIDTH = 0, 1
AXIS_STYLE, AXIS_WIDTH = 4, 0

Point3 = tuple[float, float, float]


def _yz(y: float, z: float) -> Point3:
    return (0.0, y, z)


def _box(
    name: str, y0: float, y1: float, z0: float, z1: float
) -> dict[str, tuple[Point3, Point3]]:
    return {
        f"{name} bottom": (_yz(y0, z0), _yz(y0, z1)),
        f"{name} top": (_yz(y1, z0), _yz(y1, z1)),
        f"{name} side 1": (_yz(y0, z0), _yz(y1, z0)),
        f"{name} side 2": (_yz(y0, z1), _yz(y1, z1)),
    }


def exploded_lines() -> dict[str, dict[str, tuple[Point3, Point3]]]:
    """Every line the exploded view adds, by font, kit mm (x, y, z)."""
    # The gear: its disc about item 2's axis (its bore), its cam boss about
    # the lathe axis (kit z = 0), as turned.
    phantom = {
        **_box(
            "gear disc",
            GEAR_Y0,
            GEAR_DISC_TOP,
            AXIS_Z - GEAR_TIP_R,
            AXIS_Z + GEAR_TIP_R,
        ),
        **_box("gear cam", GEAR_DISC_TOP, GEAR_TOP, -CAM_R, CAM_R),
    }
    washer_r = fixture.WASHER_OD / 2.0
    head_r = SCREW.head_dia / 2.0
    major_r = SCREW.major_dia / 2.0
    items = {
        **_box("washer", WASHER_Y0, WASHER_TOP, AXIS_Z - washer_r, AXIS_Z + washer_r),
        **_box(
            "screw head", SCREW_SEAT_Y, SCREW_TOP_Y, AXIS_Z - head_r, AXIS_Z + head_r
        ),
        "screw tip": (
            _yz(SCREW_TIP_Y, AXIS_Z - major_r),
            _yz(SCREW_TIP_Y, AXIS_Z + major_r),
        ),
        "screw shank 1": (
            _yz(SCREW_TIP_Y, AXIS_Z - major_r),
            _yz(SCREW_SEAT_Y, AXIS_Z - major_r),
        ),
        "screw shank 2": (
            _yz(SCREW_TIP_Y, AXIS_Z + major_r),
            _yz(SCREW_SEAT_Y, AXIS_Z + major_r),
        ),
    }
    axes = {
        "stub axis": (
            _yz(fixture.THICKNESS - AXIS_OVERRUN, AXIS_Z),
            _yz(SCREW_TOP_Y + AXIS_OVERRUN, AXIS_Z),
        )
    }
    return {"phantom": phantom, "item": items, "axis": axes}


# Labels: what each leader names and the kit-frame point its tip lands on.
GEAR_LABEL = "MHA-DT-12 GEAR (THE WORKPIECE)\nCAM BOSS AWAY FROM ITEM 1"
SCREW_LABEL = "ITEM 5"
WASHER_LABEL = "ITEM 4"
STUB_LABEL = "ITEM 2, TAPPED END OUT"
PIN_LABEL = "ITEM 3, IN THE GEAR'S\nNOTCHED TOOTH SPACE"
BODY_LABEL = "ITEM 1, IN THE 4-JAW"
EXPLODED_CAPTION = "EXPLODED RIGHT VIEW - FITTING STEPS ON SHEET 1"
LABEL_TIPS: dict[str, Point3] = {
    SCREW_LABEL: _yz((SCREW_SEAT_Y + SCREW_TOP_Y) / 2.0, AXIS_Z - SCREW.head_dia / 2.0),
    WASHER_LABEL: _yz((WASHER_Y0 + WASHER_TOP) / 2.0, AXIS_Z - fixture.WASHER_OD / 2.0),
    GEAR_LABEL: _yz((GEAR_Y0 + GEAR_DISC_TOP) / 2.0, AXIS_Z - GEAR_TIP_R),
    STUB_LABEL: _yz(fixture.THICKNESS + fixture.STUB_STAND / 2.0, AXIS_Z - _STUB_R),
    PIN_LABEL: _yz(_PIN_TOP, -fixture.PIN_Y),
    BODY_LABEL: _yz(fixture.THICKNESS / 2.0, -_R),
}
# Sheet metres: every label stands in one column right of the view, its
# rows in the tips' top-to-bottom order, at least a label's height apart;
# the caption top-left, clear of the view.
LABEL_COLUMN_X = 0.300
CAPTION_XY = (0.030, 0.255)
LABEL_GAP = 0.006
CHAR_WIDTH = 0.00255  # default-format note text, per character
LINE_PITCH = 0.0046


def _add_note(adapter: Any, text: str, xy: tuple[float, float], *, label: str) -> None:
    note = add_note(adapter, text, *xy)
    if note is None:
        raise RuntimeError(f"failed to place the cam turning kit {label}")
    printed = (
        str(_early_bound(note, "INote").GetText() or "")
        .replace("\r\n", "\n")
        .replace("\r", "\n")
    )
    if printed != text:
        raise RuntimeError(f"cam turning kit {label} printed as {printed!r}")


def _bom_items(adapter: Any, table: Any) -> dict[str, str]:
    """Each part's ITEM NO. as the BOM prints it, read off its PART NUMBER
    row; the steps cite items 1-5 in insertion order."""
    table = _early_bound(table, "ITableAnnotation")

    def cell(row: int, column: int) -> str:
        return str(
            adapter._attempt(lambda: table.DisplayedText2(row, column, True)) or ""
        ).strip()

    header = [cell(0, column).upper() for column in range(int(table.ColumnCount))]
    items = [index for index, text in enumerate(header) if text.startswith("ITEM NO")]
    numbers = [index for index, text in enumerate(header) if text == "PART NUMBER"]
    if (
        int(table.RowCount) != 1 + len(BOM_COMPONENTS)
        or len(items) != 1
        or len(numbers) != 1
    ):
        raise RuntimeError(
            f"cam turning kit BOM is not {len(BOM_COMPONENTS)} item rows: {header!r}"
        )
    stems = {number: stem for stem, number in BOM_PART_NUMBERS.items()}
    printed = {
        stems.get(cell(row, numbers[0]), cell(row, numbers[0])): cell(row, items[0])
        for row in range(1, int(table.RowCount))
    }
    if printed != BOM_ITEMS:
        raise RuntimeError(
            f"cam turning kit BOM numbers its parts {printed!r}, not {BOM_ITEMS!r}"
        )
    return printed


def _move_model_point(
    adapter: Any,
    view: Any,
    point_m: tuple[float, float, float],
    target: tuple[float, float],
    *,
    label: str,
) -> None:
    """Move ``view`` so the kit point lands on ``target`` (sheet m), by the
    register, not by the view's box (draw_dt_cone_gear_tl_indexing_assembly)."""
    view = _early_bound(view, "IView")
    here = model_points_in_view(adapter, view, [point_m], label=label)[0]
    position = tuple(float(value) for value in view.Position)
    moved = [position[i] + target[i] - here[i] for i in range(2)]
    if not view.SetViewPosition(double_array(moved), False):
        raise RuntimeError(f"failed to move the {label}")
    rebuild_drawing(adapter, label=f"place {label}")
    here = model_points_in_view(adapter, view, [point_m], label=label)[0]
    if math.dist(here, target) > 1e-4:
        raise RuntimeError(f"{label}: register sits at {here!r}, not {target!r}")


def _kit_view(
    adapter: Any,
    name: str,
    center: tuple[float, float],
    scale: tuple[float, float],
    stems: frozenset[str],
) -> Any:
    """One view of ``stems``, the register's face centre on ``center``."""
    label = f"cam turning kit {name}"
    view = place_view(adapter, str(SOURCE), name, *center, scale=scale)
    view = isolate_drawing_view_components(
        adapter, view, visible_stems=stems, label=label
    )
    _move_model_point(adapter, view, _kit(REGISTER_FACE_MM), center, label=label)
    return view


def _reference_dimensions(adapter: Any, view: Any) -> Callable[[], None]:
    """The throw and the clock pin's station, each a native driven dimension
    from the register's circle to the stub's or pin's circle, parenthesized
    as reference and checked against the spec."""
    names = list(REFERENCE_DIMENSIONS)
    picks = model_points_in_view(
        adapter,
        view,
        [_kit(REGISTER_PICK), *(_kit(REFERENCE_DIMENSIONS[n][0]) for n in names)],
        label="cam turning kit reference picks",
    )
    register = picks[0]
    authored = []
    for name, second in zip(names, picks[1:], strict=True):
        _pick, orientation, expected_mm, offset = REFERENCE_DIMENSIONS[name]
        label = f"cam turning kit {name}"
        # add_edge_dimension returns the raw dispatch: GetAnnotation on it
        # is "Member not found" natively (run 6f63c0c9), so bind it as the
        # passing sheets do (draw_dt_cone_tip_gear._add_overall_reference).
        display = _early_bound(
            add_edge_dimension(
                adapter,
                view,
                p0=register,
                p1=second,
                text_xy=(TOP_CENTER[0] + offset[0], TOP_CENTER[1] + offset[1]),
                label=label,
                orientation=orientation,
            ),
            "IDisplayDimension",
        )
        # Value-only: the picks are circle rims at exact projected model
        # points; the register, stub and pin are the only circles there.
        assert_dimension_measures(
            adapter, display, expected_mm=expected_mm, label=label
        )
        display = _early_bound(
            set_reference_dimension(adapter, display.GetAnnotation(), label=label),
            "IDisplayDimension",
        )
        display.SetPrecision3(REFERENCE_PLACES, -1, -1, -1)
        if int(display.GetPrimaryPrecision2()) != REFERENCE_PLACES:
            raise RuntimeError(f"{label} precision did not persist")
        authored.append((label, display, expected_mm))

    def settled() -> None:
        for label, display, expected_mm in authored:
            assert_dimension_measures(
                adapter, display, expected_mm=expected_mm, label=f"{label} settled"
            )
            if (str(display.GetText(1) or ""), str(display.GetText(2) or "")) != (
                "(",
                ")",
            ):
                raise RuntimeError(f"{label} is no longer a reference dimension")

    return settled


def _place_sheet(adapter: Any) -> Callable[[], None]:
    fixture_only = frozenset({BODY, STUB, CLOCK_PIN})
    top = _kit_view(adapter, "*Top", TOP_CENTER, SHEET_SCALE, fixture_only)
    front = _kit_view(
        adapter, "*Front", FRONT_CENTER, SHEET_SCALE, frozenset(BOM_COMPONENTS)
    )
    for view, name in ((top, "*Top"), (front, "*Front")):
        set_hidden_lines_removed(adapter, view)
        apply_view_configuration(adapter, view, label=f"cam turning kit {name}")
    iso = _kit_view(
        adapter, "*Isometric", ISO_CENTER, ISO_SCALE, frozenset(BOM_COMPONENTS)
    )
    set_high_quality_shaded_with_edges(adapter, iso, label="cam turning kit isometric")
    apply_view_configuration(
        adapter, iso, role=ViewRole.FULL_DETAIL, label="cam turning kit *Isometric"
    )
    assert_full_detail_view(adapter, label="cam turning kit")

    table = insert_bom_table(
        adapter,
        front,
        anchor_xy=BOM_ANCHOR,
        expected_components=BOM_COMPONENTS,
        descriptions=BOM_DESCRIPTIONS,
        component_identities=BOM_COMPONENT_IDENTITIES,
        part_number_property="Number",
        label="cam turning kit",
    )
    items = _bom_items(adapter, table)
    landings = []
    for view, stems, label in (
        (front, FRONT_ITEMS, "cam turning kit front balloons"),
        (iso, ISO_ITEMS, "cam turning kit isometric balloons"),
    ):
        landings += add_component_bom_balloons(
            adapter,
            view,
            items=tuple((stem, items[stem]) for stem in stems),
            anchors=BALLOON_ANCHORS,
            label=label,
            margin=BALLOON_MARGIN,
            explode_offsets={},
        )
    if len(landings) != len(BOM_COMPONENTS):
        raise RuntimeError(
            f"cam turning kit carries {len(landings)} balloons, "
            f"expected {len(BOM_COMPONENTS)}"
        )
    references_settled = _reference_dimensions(adapter, top)
    for text, xy, label in (
        (ASSEMBLY_STEPS, STEPS_XY, "steps"),
        (ASSEMBLY_CHECKS, CHECKS_XY, "checks"),
        (TOP_CAPTION, TOP_CAPTION_XY, "top view caption"),
        (FRONT_CAPTION, FRONT_CAPTION_XY, "front view caption"),
        (ISO_NOTE, ISO_NOTE_XY, "isometric scale note"),
    ):
        _add_note(adapter, text, xy, label=label)

    def settled() -> None:
        assert_balloon_landings(adapter, landings)
        references_settled()

    return settled


def _activate_sheet(adapter: Any, name: str) -> None:
    ddoc = _early_bound(adapter.currentModel, "IDrawingDoc")
    if not ddoc.ActivateSheet(name):
        raise RuntimeError(f"failed to activate cam turning kit sheet {name!r}")
    actual = str(_early_bound(ddoc.GetCurrentSheet(), "ISheet").GetName() or "")
    if actual != name:
        raise RuntimeError(f"cam turning kit sheet is {actual!r}, expected {name!r}")


Box = tuple[float, float, float, float]


def _text_size(text: str) -> tuple[float, float]:
    lines = text.splitlines()
    return max(map(len, lines)) * CHAR_WIDTH, len(lines) * LINE_PITCH


def exploded_label_positions(
    tips: dict[str, tuple[float, float]],
) -> dict[str, tuple[float, float]]:
    """Each label's upper-left corner (sheet metres): one column right of the
    view, in the tips' top-to-bottom order, each starting level with its tip
    or lower so no two overlap; the caption top-left."""
    positions: dict[str, tuple[float, float]] = {}
    floor = math.inf
    for text in sorted(tips, key=lambda key: -tips[key][1]):
        top = min(tips[text][1] + LINE_PITCH / 2.0, floor)
        positions[text] = (LABEL_COLUMN_X, top)
        floor = top - _text_size(text)[1] - LABEL_GAP
    positions[EXPLODED_CAPTION] = CAPTION_XY
    return positions


def label_boxes(positions: dict[str, tuple[float, float]]) -> dict[str, Box]:
    """Each label's estimated box (x0, y0, x1, y1) from its upper-left."""
    boxes = {}
    for text, (x, y) in positions.items():
        width, height = _text_size(text)
        boxes[text] = (x, y - height, x + width, y)
    return boxes


def _place_exploded_sheet(adapter: Any) -> Callable[[], None]:
    """Sheet 2: items 1-3 seated in the right view, the phantom gear and
    items 4 and 5 drawn off item 2's axis in fitting order, labelled
    (rule 22)."""
    label = "cam turning kit exploded view"
    _activate_sheet(adapter, SHEET_NAMES[1])
    view = _kit_view(
        adapter,
        "*Right",
        EXPLODED_CENTER,
        DETAIL_SCALE,
        frozenset({BODY, STUB, CLOCK_PIN}),
    )
    set_hidden_lines_removed(adapter, view)
    apply_view_configuration(adapter, view, label=label)
    groups = exploded_lines()
    fonts = {
        "phantom": (PHANTOM_STYLE, PHANTOM_WIDTH),
        "item": (ITEM_STYLE, ITEM_WIDTH),
        "axis": (AXIS_STYLE, AXIS_WIDTH),
    }
    sketched = {}
    for group, lines in groups.items():
        keys = list(lines)
        sheet = model_points_in_view(
            adapter,
            view,
            [
                tuple(value / 1000.0 for value in point)
                for key in keys
                for point in lines[key]
            ],
            label=f"{label} {group}",
        )
        style, width = fonts[group]
        sketched[group] = sketch_lines(
            adapter,
            view,
            {key: (sheet[2 * i], sheet[2 * i + 1]) for i, key in enumerate(keys)},
            style=style,
            width=width,
            label=f"{label} {group}",
        )
    rebuild_drawing(adapter, label=label)

    def assert_lines(stage: str) -> None:
        for group, lines in sketched.items():
            style, width = fonts[group]
            require_placed(
                adapter,
                lines,
                style=style,
                width=width,
                label=f"{label} {group}",
                stage=stage,
            )

    assert_lines("drawn")
    texts = list(LABEL_TIPS)
    points = model_points_in_view(
        adapter,
        view,
        [tuple(value / 1000.0 for value in LABEL_TIPS[text]) for text in texts],
        label=f"{label} label tips",
    )
    tips = dict(zip(texts, points, strict=True))
    positions = exploded_label_positions(tips)
    for text, (x0, y0, x1, y1) in label_boxes(positions).items():
        if (
            x0 < SHEET_INNER_BORDER[0]
            or x1 > SHEET_INNER_BORDER[2]
            or y0 < SHEET_INNER_BORDER[1]
            or y1 > SHEET_INNER_BORDER[3]
        ):
            raise RuntimeError(f"{label}: {text!r} would leave the border")
    for text in texts:
        add_leader_note(
            adapter,
            text,
            text_xy=positions[text],
            attach_xy=tips[text],
            label=f"{label}: {text.splitlines()[0]}",
            view=view,
        )
    _activate_sheet(adapter, SHEET_NAMES[1])
    _add_note(adapter, EXPLODED_CAPTION, positions[EXPLODED_CAPTION], label="caption")
    return lambda: assert_lines("settled")


@_telemetry.traced("drawing.dt_cylinder_gear_tl_cam_turning_assembly")
async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source assembly is missing: {SOURCE}")

    check("open cam turning kit drawing source", await adapter.open_model(str(SOURCE)))
    properties = read_required_properties(
        _early_bound(adapter.currentModel, "IModelDoc2"),
        ("Number", "Revision", "Title", "Material Specification", "Finish", "Quantity"),
        required=("Number", "Revision", "Material Specification", "Finish", "Quantity"),
    )
    if properties["Number"] != DRAWING_NUMBER:
        raise RuntimeError(
            f"cam turning kit source Number {properties['Number']!r} != {DRAWING_NUMBER!r}"
        )
    new_project_drawing(
        adapter, layout=SPEC.layout, scale=SHEET_SCALE, unit=CONTRACT.drawing_unit
    )
    create_blank_drawing_sheets(adapter, SHEET_NAMES, label="cam turning kit package")
    ddoc = _early_bound(adapter.currentModel, "IDrawingDoc")
    for name in SHEET_NAMES:
        _activate_sheet(adapter, name)
        sheet = _early_bound(ddoc.GetCurrentSheet(), "ISheet")
        if not sheet.SetScale(*SHEET_SCALES[name], False, False):
            raise RuntimeError(f"failed to set cam turning kit sheet scale: {name}")
    _activate_sheet(adapter, SHEET_NAMES[0])
    sheet_settled = _place_sheet(adapter)
    exploded_settled = _place_exploded_sheet(adapter)

    def settled() -> None:
        sheet_settled()
        exploded_settled()

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        layout=SPEC.layout,
        pdf_title="Cylinder Gear Cam Turning Fixture Kit Assembly Drawing",
        scale=SHEET_SCALE,
        expected_sheet_names=SHEET_NAMES,
        sheet_layouts=SHEET_LAYOUTS,
        sheet_scales=SHEET_SCALES,
        settled_checks=(settled,),
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[ARTIFACT_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
