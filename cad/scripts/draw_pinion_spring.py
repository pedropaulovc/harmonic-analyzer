r"""Create the curated machinist drawing for the pinion return leaf spring.

NOT a coil spring: a bent 17-7 PH stainless leaf.  A 0.381 blank -- a 6.35
strip with a square screw pad at its free end -- formed as a flat screw-down
foot, an R3.3 bend up to a blade leaning back over the foot's bend, then an
R3.3 crest turning 25 deg out to a short free flat.  The solid is the installed shape;
the front view also shows the part's hidden FreeForm reference sketch as the
phantom free form, and the free crest and tip are baselined from the foot's
free end on it.  The projected top view carries the blank's pad, strip width
and hole; a 5:1 detail carries the crest.

Run with SolidWorks open::

    uv run python cad\scripts\draw_pinion_spring.py pinion-spring
"""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

import _drawing_hidden_sketches as hidden_sketches
import _telemetry
from _common import CAD_ROOT, _early_bound, _read_member, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_edge_dimension,
    add_native_hole_callout,
    add_property_linked_note,
    assert_imported_precision,
    curate_view_dimensions,
    finalize_drawing,
    model_point_in_view,
    new_project_drawing,
    read_required_properties,
    set_dimension_callouts,
    set_hidden_lines_removed,
    stamp_drawing_summary,
    view_name,
)
from _drawing_registry import DRAWINGS_BY_NAME
from pinion_spring_geometry import (
    BEND_CX,
    FLAT_TIP,
    FOOT_END,
    FOOT_TAN,
    FREE_FLAT_TIP,
    FREE_KINK_START,
    HOLE_DIA,
    HOLE_FROM_END,
    KINK_C,
    PAD_LEN,
    PAD_WIDTH,
    PAD_Z,
    R_KINK,
    THICK,
)
from pinion_spring_spec import DRAWING_DIMENSIONS, DRAWING_PRECISION_BY_NAME
from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import (
    add_note,
    auto_center_marks,
    place_view,
)


SPEC = DRAWINGS_BY_NAME["pinion_spring"]
PART_STEM = SPEC.artifact_stem
SOURCE = CAD_ROOT / "out" / "sldprt" / f"{PART_STEM}.SLDPRT"
OUTPUTS = DrawingOutputs(
    slddrw=SPEC.outputs["slddrw"],
    pdf=SPEC.outputs["pdf"],
    png=SPEC.outputs["png"],
)
SLDDRW = OUTPUTS.slddrw
PDF = OUTPUTS.pdf
PNG = OUTPUTS.png

SHEET_SCALE = (2.0, 1.0)
_S = SHEET_SCALE[0] / 1000.0

# Front view (XY): the profile -- the foot along the bottom running right to
# its free end, the blade rising at the left and leaning back over the bend.
# Views centre on their bounding boxes; the profile spans the crest's outer
# face to the foot's free end and the foot's underside to the free tip.
_PROFILE_MIN_X = KINK_C[0] - (R_KINK + THICK)
FRONT_BBOX_CX = (_PROFILE_MIN_X + FOOT_END[0]) / 2.0
FRONT_BBOX_CY = (FLAT_TIP[1] + THICK) / 2.0
FRONT_CENTER = (0.110, 0.118)
# Third-angle projection: the top view sits ABOVE the front and shares its X
# station (both views span the same model x range), so the pad and hole read
# straight up from the profile's free end.
TOP_CENTER = (FRONT_CENTER[0], 0.210)
ISO_CENTER = (0.350, 0.150)
# Detail A is a cropped 5:1 *Front MODEL view, not a native detail view.  The
# native detail's targeted import of SpringProfile brought FlatLen in pc-r11
# and pc-r12 but only KinkR in pc-r13 (leaf 20260927T001822Z-1-ba1f4546),
# with the same script and a dimensionally identical part; a cropped model
# view takes a targeted import like any principal view (MHA-102's detail A,
# 522920510; draw_crank_arm's top view).  Its crop circle's centre is where
# pc-r12 printed the native detail's.
DETAIL_CENTER = (0.240, 0.184)
DETAIL_SCALE = (5, 1)
DETAIL_RATIO = DETAIL_SCALE[0] / DETAIL_SCALE[1]
# The kink detail's fence: centred between the kink centre and the free tip,
# large enough to take the whole kink arc and the flat (3.06 at R3.3).
DETAIL_FOCUS = (
    (KINK_C[0] + FLAT_TIP[0]) / 2.0,
    (KINK_C[1] + FLAT_TIP[1]) / 2.0,
)
DETAIL_RADIUS_MM = 3.5
DETAIL_CROP_RADIUS = DETAIL_RATIO * DETAIL_RADIUS_MM / 1000.0
DETAIL_LETTER = "A"
# A model view has no native label the API can show, so the label is a note
# the view owns, in the native detail label's words, its top edge this far
# under the crop circle (where pc-r12's native label sat).
DETAIL_LABEL_TEXT = (
    f"DETAIL {DETAIL_LETTER}\nSCALE {DETAIL_SCALE[0]} : {DETAIL_SCALE[1]}"
)
DETAIL_LABEL_DROP = 0.007
DETAIL_LABEL_XY = (
    DETAIL_CENTER[0],
    DETAIL_CENTER[1] - DETAIL_CROP_RADIUS - DETAIL_LABEL_DROP,
)
# The fence's "A" goes WEST of the fence, level with its centre: above it,
# it sat on the FREE, TO KINK TANGENT row (stacktop-dbe47ae3, spring-r1).
# West of the fence is open sheet; the free-form phantom runs on the fence's
# west edge.
PARENT_LETTER_OFFSET = (-(DETAIL_RADIUS_MM * _S + 0.005), 0.0)
# swCropViewErrors_e.swCropViewErrors_NoError
CROP_NO_ERROR = 1
# The kink focus must land within 0.1 mm of DETAIL_CENTER after the move.
DETAIL_POSITION_TOL_M = 1e-4
NOTE_CENTRING_TOL_M = 0.001
NOTE_CENTRING_PASSES = 2


def _front_x(model_x_mm: float) -> float:
    return FRONT_CENTER[0] + (model_x_mm - FRONT_BBOX_CX) * _S


def _front_y(model_y_mm: float) -> float:
    return FRONT_CENTER[1] + (model_y_mm - FRONT_BBOX_CY) * _S


_FOOT_MID_X = (FOOT_END[0] + FREE_KINK_START[0]) / 2.0
_PROFILE_TOP = _front_y(max(FLAT_TIP[1], FREE_FLAT_TIP[1]))
_PAD_EAST = _front_x(FOOT_END[0])
# Half the printed width of each qualified dimension's widest text line, as
# pc-r12's render measured it (sheet metres, 11.8 px/mm).  A text wider than
# its own dimension goes east of the foot end's extension line, which the
# FootLen, FreeKinkH and FreeTipH rows share: centred between the extension
# lines, pc-r12 printed those lines through FREE, BEND and TANGENT.
QUALIFIER_HALF_WIDTH = {
    "FREE, TO KINK TANGENT": 0.026,
    "TO BEND TANGENT": 0.021,
    "FREE, TO TIP": 0.013,
}
TEXT_TO_EXTENSION_GAP = 0.003
_KINK_TEXT_X = _PAD_EAST + TEXT_TO_EXTENSION_GAP + QUALIFIER_HALF_WIDTH["FREE, TO KINK TANGENT"]
FRONT_KEEP = {
    "FootLen": (
        _PAD_EAST + TEXT_TO_EXTENSION_GAP + QUALIFIER_HALF_WIDTH["TO BEND TANGENT"],
        _front_y(0.0) - 0.010,
    ),
    "BendR": (_front_x(BEND_CX) - 0.032, _front_y(0.0) - 0.004),
    # The free locations, on the FreeForm phantom.  FreeKinkV's dimension
    # line runs where its text sits, east of the foot end.
    "FreeKinkV": (_KINK_TEXT_X, _front_y(FREE_KINK_START[1] / 2.0)),
    # Clear of the kink fence's native "A" label, which SolidWorks sets just
    # above the fence (spring-r1 put the 15.0 text on it), with a text gap
    # between the two and the top view lifted to make room.  FREE, TO TIP
    # fits between its extension lines; the kink row's text does not.
    "FreeKinkH": (_KINK_TEXT_X, _PROFILE_TOP + 0.020),
    "FreeTipH": (_front_x(_FOOT_MID_X), _PROFILE_TOP + 0.038),
}
# The vertical extension lines each qualified row's text sits among: its own
# two, and the foot end's, which runs past every row.
FRONT_ROW_EXTENSION_X = {
    "FootLen": (_front_x(FOOT_TAN[0]), _PAD_EAST),
    "FreeKinkV": (_PAD_EAST,),
    "FreeKinkH": (_front_x(FREE_KINK_START[0]), _PAD_EAST),
    "FreeTipH": (_front_x(FREE_FLAT_TIP[0]), _PAD_EAST),
}
TOP_KEEP = {
    "PadLen": (_front_x(FOOT_END[0] - PAD_LEN / 2.0), TOP_CENTER[1] + 0.021),
    # Outboard of the hole-edge 4.75 (HOLE_EDGE_TEXT_XY) so the two stack apart.
    "PadWidth": (_PAD_EAST + 0.030, TOP_CENTER[1]),
    "StripWidth": (_front_x(_PROFILE_MIN_X) - 0.018, TOP_CENTER[1]),
}
DETAIL_KEEP = {
    # The flick turns right (east) in this view: the radius leader goes
    # upper-left of the fence, the flat's length to its right.
    "KinkR": (0.205, 0.232),
    "FlatLen": (0.282, 0.200),
}
DIMENSION_CALLOUTS = {
    "FootLen": "TO BEND TANGENT",
    "FreeKinkH": "FREE, TO KINK TANGENT",
    "FreeKinkV": "FREE, TO KINK TANGENT",
    "FreeTipH": "FREE, TO TIP",
}
HOLE_END_TEXT_XY = (_front_x(FOOT_END[0] - HOLE_FROM_END / 2.0), TOP_CENTER[1] + 0.031)
HOLE_EDGE_TEXT_XY = (_PAD_EAST + 0.012, TOP_CENTER[1] + 0.004)
# Below the pad: above it the leader crossed the 4.50 and 9.50 pad
# dimensions on its way down to the hole.  The note centres on this point, so
# it sits east of the pad, clear of the FREE, TO TIP text below the top view.
HOLE_CALLOUT_XY = (_PAD_EAST + 0.035, TOP_CENTER[1] - 0.019)
# The #4 normal clearance (3.264 mm = 0.1285 in) is a No. 30 drill; the shop
# reaches for the number, the native size compartment still prints the diameter.
HOLE_PROCESS = "#30 DRILL"
# The pad hole where build_pinion_spring's Hole Wizard puts it (model mm): on
# the foot's top face, centred across the pad, which stands PAD_Z off the
# strip's centre plane.  The callout picks its rim at the +z quadrant.  pc-r11
# (0c5636eab) picked z HOLE_DIA/2, the rim while the pad was centred on the
# strip; once 6c9d4f476 moved the pad, that point sat 0.06 mm from the hole's
# centre, and SelectByID2 found no edge there.
HOLE_CENTER = (FOOT_END[0] - HOLE_FROM_END, THICK, PAD_Z)
HOLE_EDGE_PICK = (HOLE_CENTER[0], HOLE_CENTER[1], HOLE_CENTER[2] + HOLE_DIA / 2.0)


def _activate_view(adapter: Any, view: Any, *, label: str) -> str:
    """Make ``view`` the active view (sketch entities and notes land in it)."""
    name = view_name(adapter, view)
    if not _early_bound(adapter.currentModel, "IDrawingDoc").ActivateView(name):
        raise RuntimeError(f"failed to activate the {label} {name!r}")
    adapter.currentModel.ClearSelection2(True)
    return name


def _sketch_circle(
    adapter: Any,
    view: Any,
    center: tuple[float, float],
    radius: float,
    *,
    label: str,
    add_to_db: bool = False,
) -> Any:
    """Sketch a circle in the ACTIVE ``view``'s own sketch from sheet points.

    The sheet points go through the view sketch's ModelToSketchTransform (the
    recipe the native fence and draw_crank_arm's crop used).  Without
    ``add_to_db`` the circle is left SELECTED, which is what Crop2 consumes.
    """
    sketch = _early_bound(_early_bound(view, "IView").GetSketch(), "ISketch")
    transform = _early_bound(sketch.ModelToSketchTransform, "IMathTransform")
    utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    points = []
    for x, y in (center, (center[0] + radius, center[1])):
        point = _early_bound(
            utility.CreatePoint(double_array([x, y, 0.0])), "IMathPoint"
        )
        projected = _early_bound(point.MultiplyTransform(transform), "IMathPoint")
        points.append(tuple(float(value) for value in projected.ArrayData))
    manager = _early_bound(adapter.currentModel.SketchManager, "ISketchManager")
    previous_add_to_db = bool(manager.AddToDB)
    manager.AddToDB = add_to_db
    try:
        circle = manager.CreateCircle(*points[0], *points[1])
    finally:
        manager.AddToDB = previous_add_to_db
    if circle is None:
        raise RuntimeError(f"failed to sketch the {label} circle")
    return circle


def _mark_kink_on_front(adapter: Any, front: Any) -> tuple[float, float]:
    """Circle detail A's region on the front view; returns its sheet centre.

    The fence the native detail was cut from, now a plain view-sketch circle
    drawn direct to the database in the outline's black.
    """
    _activate_view(adapter, front, label="formed-profile view")
    center = model_point_in_view(
        adapter,
        front,
        (DETAIL_FOCUS[0] / 1000.0, DETAIL_FOCUS[1] / 1000.0, 0.0),
        label="kink detail centre",
    )
    circle = _sketch_circle(
        adapter,
        front,
        center,
        DETAIL_RADIUS_MM * _S,
        label="kink-detail mark",
        add_to_db=True,
    )
    segment = _early_bound(circle, "ISketchSegment")
    segment.Color = 0  # COLORREF black, not the under-defined sketch blue.
    if int(segment.Color) != 0:
        raise RuntimeError("kink-detail mark circle colour did not persist")
    adapter.currentModel.ClearSelection2(True)
    adapter.currentModel.EditRebuild3()
    return center


def _cropped_kink_view(adapter: Any) -> Any:
    """Detail A: a standalone 5:1 *Front model view cropped to the kink.

    Place *Front at 5:1; move it so the kink focus lands on DETAIL_CENTER
    (checked to DETAIL_POSITION_TOL_M); activate it; sketch the fence's 5:1
    circle in its own sketch and Crop2 while the circle is still selected,
    with the circle as its outline, as the native detail printed it.  Crop
    status, IsCropped and the outline style are read back and raise.  The
    part hides FreeForm, so the view shows the installed crest alone.
    """
    draw = adapter.currentModel
    view = _early_bound(
        place_view(adapter, str(SOURCE), "*Front", *DETAIL_CENTER, scale=DETAIL_SCALE),
        "IView",
    )
    ratio = tuple(float(value) for value in view.ScaleRatio)
    if ratio != tuple(float(value) for value in DETAIL_SCALE):
        raise RuntimeError(f"kink detail scale {ratio!r}, expected {DETAIL_SCALE!r}")
    focus = (DETAIL_FOCUS[0] / 1000.0, DETAIL_FOCUS[1] / 1000.0, 0.0)
    center = model_point_in_view(adapter, view, focus, label="kink detail focus")
    position = tuple(float(value) for value in view.Position)
    target = [position[axis] + DETAIL_CENTER[axis] - center[axis] for axis in range(2)]
    if not view.SetViewPosition(double_array(target), False):
        raise RuntimeError("failed to move the kink detail onto its sheet position")
    draw.EditRebuild3()
    center = model_point_in_view(adapter, view, focus, label="kink detail focus")
    if math.dist(center, DETAIL_CENTER) > DETAIL_POSITION_TOL_M:
        raise RuntimeError(f"kink focus sits at {center!r}, not {DETAIL_CENTER!r}")
    uncropped = tuple(float(value) for value in view.GetOutline())
    name = _activate_view(adapter, view, label="kink detail")
    _sketch_circle(adapter, view, center, DETAIL_CROP_RADIUS, label="kink-detail crop")
    status = int(view.Crop2(False, False, 1))
    draw.ClearSelection2(True)
    draw.EditRebuild3()
    view.UpdateViewDisplayGeometry()
    cropped = bool(view.IsCropped())
    outline = tuple(float(value) for value in view.GetOutline())
    _telemetry.info(
        f"pinion-spring: kink detail {name!r} {ratio[0]:g}:{ratio[1]:g}, Crop2 "
        f"status {status}, IsCropped {cropped}, outline "
        f"{tuple(round(value * 1000, 1) for value in outline)} mm",
        crop_status=status,
        cropped=cropped,
    )
    if status != CROP_NO_ERROR or not cropped:
        raise RuntimeError(
            f"kink detail is not cropped: Crop2 status {status}, IsCropped {cropped}"
        )
    # The uncropped 5:1 view spans the whole ~47 mm spring (~235 mm on the
    # sheet), the crop 35 mm, so a crop that took at least halves the height.
    if (
        len(outline) != 4
        or len(uncropped) != 4
        or outline[3] - outline[1] > (uncropped[3] - uncropped[1]) / 2.0
    ):
        raise RuntimeError(
            f"kink-detail crop did not take: outline {outline!r}, before {uncropped!r}"
        )
    boundary = (bool(view.CropViewJaggedOutline), bool(view.CropViewNoOutline))
    if boundary != (False, False):
        raise RuntimeError(
            f"kink detail's crop boundary is not its plain circle: jagged, "
            f"no-outline {boundary!r}"
        )
    return view


def _plain_text(text: str) -> str:
    """A note's words with its line breaks and spacing folded to single spaces."""
    return " ".join(str(text).split())


def _note_box(note: Any, *, label: str) -> tuple[float, float, float, float]:
    """``INote.GetExtent``'s lower-left and upper-right corners, sheet metres."""
    values = tuple(float(value) for value in (note.GetExtent() or ()))
    if len(values) != 6 or not all(map(math.isfinite, values)):
        raise RuntimeError(f"{label}: invalid note extent {values!r}")
    box = (values[0], values[1], values[3], values[4])
    if box[0] >= box[2] or box[1] >= box[3]:
        raise RuntimeError(f"{label}: empty note extent {values!r}")
    return box


def _note_centring_error(
    box: tuple[float, float, float, float],
    center_x: float,
    top: float | None,
    center_y: float | None,
) -> tuple[float, float]:
    """How far a note's extent sits from its target: its horizontal centre
    against ``center_x``, and its top edge against ``top`` or else its
    vertical centre against ``center_y``."""
    error_x = (box[0] + box[2]) / 2.0 - center_x
    if top is not None:
        return error_x, box[3] - top
    if center_y is None:
        raise ValueError("a centred note needs a top edge or a centre height")
    return error_x, (box[1] + box[3]) / 2.0 - center_y


def _centred_view_note(
    adapter: Any,
    view: Any,
    text: str,
    *,
    center_x: float,
    top: float | None = None,
    center_y: float | None = None,
    label: str,
) -> tuple[float, float, float, float]:
    """Insert a note owned by ``view``, centred on ``center_x`` by its extent.

    A note lands in the ACTIVE view, so the view is activated first.  The
    rendered extent (INote.GetExtent) is read and the note moved by the
    centring error; ``top`` pins its top edge, ``center_y`` its middle.  A
    note that does not centre, or lands in another view, raises.
    """
    _activate_view(adapter, view, label=label)
    y = top if top is not None else center_y
    note = add_note(adapter, text, center_x, y)
    if note is None:
        raise RuntimeError(f"failed to add the {label} note")
    note = _early_bound(note, "INote")
    annotation = _early_bound(note.GetAnnotation(), "IAnnotation")
    box = _note_box(note, label=label)
    for _ in range(NOTE_CENTRING_PASSES):
        error_x, error_y = _note_centring_error(box, center_x, top, center_y)
        if max(abs(error_x), abs(error_y)) <= NOTE_CENTRING_TOL_M / 10.0:
            break
        position = tuple(
            float(value) for value in _read_member(annotation, "GetPosition")
        )
        if not annotation.SetPosition2(
            position[0] - error_x, position[1] - error_y, 0.0
        ):
            raise RuntimeError(f"failed to centre the {label} note")
        adapter.currentModel.EditRebuild3()
        box = _note_box(note, label=label)
    error_x, error_y = _note_centring_error(box, center_x, top, center_y)
    _telemetry.info(
        f"pinion-spring: {label} note {text!r} extent "
        f"({box[0] * 1000:.1f}, {box[1] * 1000:.1f})-({box[2] * 1000:.1f}, "
        f"{box[3] * 1000:.1f}) mm",
        label=label,
    )
    if max(abs(error_x), abs(error_y)) > NOTE_CENTRING_TOL_M:
        raise RuntimeError(
            f"{label} note did not centre: off by ({error_x * 1000:.2f}, "
            f"{error_y * 1000:.2f}) mm"
        )
    first_line = _plain_text(text.split("\n")[0])
    texts = [
        _plain_text(_early_bound(found, "INote").GetText() or "")
        for found in (_early_bound(view, "IView").GetNotes() or ())
    ]
    if sum(found.startswith(first_line) for found in texts) != 1:
        raise RuntimeError(
            f"{label} note did not land in its view: its notes are {texts!r}"
        )
    return box


def _label_kink_detail(
    adapter: Any, detail: Any, front: Any, mark: tuple[float, float]
) -> None:
    """Label detail A under its crop circle and letter its mark on the front."""
    drawing = _early_bound(adapter.currentModel, "IDrawingDoc")
    sheet = _early_bound(drawing.GetCurrentSheet(), "ISheet")
    if not sheet.SetScale(*SHEET_SCALE, False, False):
        raise RuntimeError("failed to pin sheet scale before labelling the kink detail")
    _centred_view_note(
        adapter,
        detail,
        DETAIL_LABEL_TEXT,
        center_x=DETAIL_LABEL_XY[0],
        top=DETAIL_LABEL_XY[1],
        label="kink-detail label",
    )
    _centred_view_note(
        adapter,
        front,
        DETAIL_LETTER,
        center_x=mark[0] + PARENT_LETTER_OFFSET[0],
        center_y=mark[1] + PARENT_LETTER_OFFSET[1],
        label="kink-detail letter",
    )


def _hole_locations(adapter: Any, top: Any) -> None:
    """Locate the pad hole from the foot's free end and the pad's lower edge.

    The Hole Wizard placement sketch cannot carry a datum point (rule 7), so the
    print dimensions the hole from the blank's own edges with driven sheet
    dimensions picked on both features; they print at the .XX row.
    """
    hole_x = (FOOT_END[0] - HOLE_FROM_END) / 1000.0
    hole_r = HOLE_DIA / 2000.0
    top_y = THICK / 1000.0
    edge_picks = {
        sign: model_point_in_view(
            adapter,
            top,
            (hole_x, top_y, (PAD_Z + sign * PAD_WIDTH / 2.0) / 1000.0),
            label=f"pad long edge z{sign:+g}",
        )
        for sign in (-1.0, 1.0)
    }
    lower = min(edge_picks, key=lambda sign: edge_picks[sign][1])
    locations = (
        (
            "hole from the foot's free end",
            model_point_in_view(
                adapter,
                top,
                (
                    FOOT_END[0] / 1000.0,
                    top_y,
                    (PAD_Z - lower * PAD_WIDTH / 4.0) / 1000.0,
                ),
                label="pad free end",
            ),
            model_point_in_view(
                adapter,
                top,
                (hole_x + hole_r, top_y, PAD_Z / 1000.0),
                label="hole east edge",
            ),
            HOLE_END_TEXT_XY,
            "horizontal",
            HOLE_FROM_END,
        ),
        (
            "hole from the pad's lower edge",
            (edge_picks[lower][0] - 0.004, edge_picks[lower][1]),
            model_point_in_view(
                adapter,
                top,
                (hole_x, top_y, PAD_Z / 1000.0 + lower * hole_r),
                label="hole lower edge",
            ),
            HOLE_EDGE_TEXT_XY,
            "vertical",
            PAD_WIDTH / 2.0,
        ),
    )
    for label, p0, p1, text_xy, orientation, expected in locations:
        display = add_edge_dimension(
            adapter,
            top,
            p0=p0,
            p1=p1,
            text_xy=text_xy,
            label=label,
            orientation=orientation,
        )
        display = _early_bound(display, "IDisplayDimension")
        dimension = _early_bound(display.GetDimension2(0), "IDimension")
        measured_mm = abs(float(dimension.SystemValue) * 1000.0)
        if abs(measured_mm - expected) > 1e-5:
            raise RuntimeError(
                f"{label} measured {measured_mm:g}, expected {expected:g} mm"
            )


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open pinion-spring source", await adapter.open_model(str(SOURCE)))
    read_required_properties(
        adapter.currentModel,
        (
            "Number",
            "Revision",
            "Title",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
            "Isometric View Note",
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
            "Isometric View Note",
        ),
    )
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Pinion Return Leaf Spring Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "pinion return spring; bent stainless leaf; formed blank",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(2, 1))
    top = place_view(adapter, str(SOURCE), "*Top", *TOP_CENTER, scale=(2, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(1, 1))
    # Rule 7: nothing on this part is communicated by a hidden line -- the
    # hole is defined by its callout -- so every view is hidden-lines-removed.
    for view in (front, top, iso):
        set_hidden_lines_removed(adapter, view)

    # The kink detail is created and dimensioned FIRST, while nothing is on
    # the sheet: KinkR and FlatLen live in SpringProfile with the profile's
    # FootLen and BendR, so the profile's targeted import delivers them too.
    # pc-r10 (37495ac47) ran the profile first and deleted the pair; the
    # detail's import then brought KinkR back but not FlatLen.  A dimension
    # already on the sheet is never imported again (the arbor's detail A
    # imports first for the same reason), so the profile's import now skips
    # the pair the detail holds.
    detail = _cropped_kink_view(adapter)
    set_hidden_lines_removed(adapter, detail)
    detail_annotations = curate_view_dimensions(
        adapter,
        detail,
        keep=DETAIL_KEEP,
        view_label="kink detail",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    # The front view imports the part-hidden FreeForm reference sketch, so it
    # takes the opt-in curation that shows it (the phantom) in this view only.
    front_annotations = hidden_sketches.curate_view_dimensions(
        adapter,
        front,
        keep=FRONT_KEEP,
        view_label="formed profile",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    top_annotations = curate_view_dimensions(
        adapter,
        top,
        keep=TOP_KEEP,
        view_label="blank top",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    annotations = [*front_annotations, *top_annotations, *detail_annotations]
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS)
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    # The fence and the labels go on once every import is done, so nothing
    # of the front view's own sketch is near its import.
    mark = _mark_kink_on_front(adapter, front)
    _label_kink_detail(adapter, detail, front, mark)

    if not auto_center_marks(adapter, top, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center marks to top view")
    _hole_locations(adapter, top)
    hole_edge = model_point_in_view(
        adapter,
        top,
        (
            HOLE_EDGE_PICK[0] / 1000.0,
            HOLE_EDGE_PICK[1] / 1000.0,
            HOLE_EDGE_PICK[2] / 1000.0,
        ),
        label="pad hole edge",
    )
    add_native_hole_callout(
        adapter,
        top,
        edge_xy=hole_edge,
        callout_xy=HOLE_CALLOUT_XY,
        label="spring pad clearance hole",
        process=HOLE_PROCESS,
    )

    add_property_linked_note(adapter, "Manufacturing Notes", 0.020, 0.058)
    add_property_linked_note(adapter, "Isometric View Note", 0.325, 0.115)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Pinion Return Leaf Spring Manufacturing Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
