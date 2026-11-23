r"""Manufacturing drawing of the cone tip gears' phasing comb (MHA-DT-03-TL-02).

One sheet. The front view draws the flat U as it stands over the cone's tip,
south (T036, where both arms stand) left, the near (stepped) arm on top and
the spring arm below: every step's start from the south end, every blade's
depth from the near T030 blade's edge (the seat line) and the grip span from
it to the spring arm's T030 blade, all at the title block's bands. The
bottom view shows the stock's thickness. Each depth states its reason after
its value, the grip span its interference; there is no numbered note. A
shaded isometric gives the picture.

Run with SolidWorks open::

    uv run python cad\scripts\draw_dt_cone_gear_tl_phasing_comb.py dt-cone-gear-tl-phasing-comb
"""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import (
    dimension_name,
    place_view,
)

import _telemetry
import dt_cone_gear_tl_phasing_comb_spec as part
from _check import check
from _com import _early_bound
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    rebuild_drawing,
    stamp_drawing_summary,
)
from _drawing_dimensions import (
    assert_imported_precision,
    offset_dimension_text,
    set_dimension_callouts,
    set_reference_dimension,
)
from _drawing_hidden_sketches import curate_view_dimensions
from _drawing_notes import add_property_linked_note
from _drawing_projection import model_point_in_view
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_view_display import set_hidden_lines_removed
from _feature_requirements import part_metadata, requirement
from _gtol_cylinder import CylinderFace
from _gtol_planar import PlanarFace
from _machinist_review_mode import MachinistReviewMode
from _paths import CAD_ROOT
from _printed_limits import limits
from _session import run_build

# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME["dt_cone_gear_tl_phasing_comb"]
PART_STEM = SPEC.artifact_stem
SOURCE = CAD_ROOT / "out" / "sldprt" / f"{PART_STEM}.SLDPRT"
OUTPUTS = DrawingOutputs(
    slddrw=SPEC.outputs["slddrw"], pdf=SPEC.outputs["pdf"], png=SPEC.outputs["png"]
)
SLDDRW, PDF, PNG = OUTPUTS.slddrw, OUTPUTS.pdf, OUTPUTS.png

# A 3.64 x .90 U whose shallowest step is .045: at 3:1 the brass U's longer
# slot ran it into the right border, so 2:1, the next standard scale, which
# still shows every step and leaves the depths' words room on its left.
SHEET_SCALE = (2.0, 1.0)
VIEW_SCALE = (2, 1)
RATIO = VIEW_SCALE[0] / VIEW_SCALE[1]
ISO_SCALE = (1, 2)
# The model origin (the near arm's south end on the seat line) on the sheet;
# the bottom view projects straight below.
FRONT_ORIGIN = (0.135, 0.190)
BOTTOM_CENTER_Y = 0.105
# The isometric under the bottom view, left of the title block, its label
# under it.
ISO_CENTER = (0.150, 0.062)
ISO_NOTE_XY = (0.120, 0.040)


def front_xy(x_mm: float, y_mm: float) -> tuple[float, float]:
    """Sheet point of model (x, y) on the front view."""
    return FRONT_ORIGIN[0] + x_mm * RATIO / 1000.0, FRONT_ORIGIN[
        1
    ] + y_mm * RATIO / 1000.0


_POINTS = part.profile_points_mm()
SHEET_BOX = (
    *front_xy(min(x for x, _ in _POINTS), min(y for _, y in _POINTS)),
    *front_xy(max(x for x, _ in _POINTS), max(y for _, y in _POINTS)),
)

# --- Measured text (layout audit) ----------------------------------------------
# A vertical dimension whose text stands outside its extension lines prints
# the text left of its dimension line, the line at the text's right edge (r10
# render); text inside them is centred on the line. Widths (sheet m): a
# three-place value 10 mm, a two-place value 7.6 mm; a capital 2.5 mm (r11
# layout audit: 79.6 mm for 32 characters). A
# line of dimension text stands 5 mm in a block (value, then each callout
# line).
DEPTH_TEXT_WIDTH = 0.010
TWO_PLACE_TEXT_WIDTH = 0.0076
CHAR_WIDTH = 0.0025
LINE_HEIGHT = 0.005

# --- Front view dimension text (sheet m) ---------------------------------------
# Left of the U, from the seat line: the grip span nearest, its text under
# the U left of its line; the spring arm's width further out, its text
# centred on its line inside its span. Further out the depths, the deepest
# nearest the U: each text stands left of its own line under its own
# extension line and a row under the shallower one's, so every line further
# out ends above it and every line nearer stands right of it. The U's height
# stands right of the bridge. Over the U, every length from the south end in
# rows, the shortest nearest, the U's length outermost.
GRIP_X = FRONT_ORIGIN[0] - 0.004
SPRING_X = FRONT_ORIGIN[0] - 0.010
DEPTH_X0 = FRONT_ORIGIN[0] - 0.011
DEPTH_TEXT_PITCH = 0.0055
DEPTH_LINE_PITCH = 0.004
HEIGHT_X = SHEET_BOX[2] + 0.007
ROW_Y0 = SHEET_BOX[3] + 0.006
ROW_PITCH = 0.0065


def depth_line_x(teeth: int) -> float:
    """The depth's dimension line, T006's (deepest) nearest the U."""
    order = part.BONDED_TEETH[::-1]
    return DEPTH_X0 - DEPTH_LINE_PITCH * order.index(teeth)


def depth_text_y(teeth: int) -> float:
    """Under the blade's own extension line and a row under the shallower
    blade's text."""
    y = math.inf
    for each in part.BONDED_TEETH[: part.BONDED_TEETH.index(teeth) + 1]:
        own = front_xy(0.0, -part.BLADE_DEPTH_MM[each])[1] - 0.001 - LINE_HEIGHT / 2.0
        y = min(own, y - DEPTH_TEXT_PITCH)
    return y


def _block_height(name: str) -> float:
    return (1 + len(part.CALLOUTS_BELOW.get(name, "").splitlines())) * LINE_HEIGHT


# Dimensions whose text stands outside, left of the line.
OUTSIDE_LEFT = frozenset(
    {"GripSpan", *(part.blade_depth_name(t) for t in part.BONDED_TEETH)}
)
ROWS = (
    *(part.blade_start_name(t) for t in part.BONDED_TEETH),
    "LevelEnd",
    "SlotLength",
    "SheetLength",
)


def front_keep() -> dict[str, tuple[float, float]]:
    keep: dict[str, tuple[float, float]] = {
        "GripSpan": (
            GRIP_X,
            SHEET_BOX[1] - 0.004 - _block_height("GripSpan") / 2.0,
        ),
        "SpringWidth": (
            SPRING_X,
            front_xy(0.0, -part.GRIP_SPAN - part.SPRING_WIDTH / 2.0)[1],
        ),
        "SheetHeight": (HEIGHT_X, (SHEET_BOX[1] + SHEET_BOX[3]) / 2.0),
    }
    for teeth in part.BONDED_TEETH:
        keep[part.blade_depth_name(teeth)] = (depth_line_x(teeth), depth_text_y(teeth))
    for row, name in enumerate(ROWS):
        end = part.GLOBALS[name]
        keep[name] = (front_xy(end / 2.0, 0.0)[0], ROW_Y0 + row * ROW_PITCH)
    return keep


FRONT_KEEP = front_keep()

# --- Bottom view ---------------------------------------------------------------
# The stock's thickness across the edge view, just left of the U's south end.
# Its arrows stand 2 mm apart, too close to hold the text, so the text (value,
# SHEET STOCK under it) stands off below and left on a leader, clear of both
# extension lines (pd-platen-clip's SheetDepth).
SHEET_THICK_X = SHEET_BOX[0] - 0.008
BOTTOM_KEEP = {"SheetThick": (SHEET_THICK_X, BOTTOM_CENTER_Y)}
OFFSET_TEXT = {"SheetThick": (SHEET_BOX[0] - 0.035, BOTTOM_CENTER_Y - 0.014)}

# Feature-export declarations (export_features; cad/docs/pipeline/
# features-travelers.md): what this sheet prints, in the part frame
# (build_dt_cone_gear_tl_phasing_comb: the U on the Front plane, x north from
# the south end, y outward through the near arm from the seat line (the near
# T030 blade's edge), the sheet extruded +Z from z = 0). Every step's start,
# the T006 level's end, the slot's length and the U's length run from the
# south end; every blade's depth and the grip span from the seat line; the
# spring arm's width from its inner edge and the U's height from the far
# edge. Lengths and widths take the title block's .XX row, the depths and the
# grip span its .XXX row; the thickness is the stock's reference, the sheet
# bought .020 +/-.002 (part.SHEET_LIMITS_MM). The declarations print nothing.
_P = part.DRAWING_PRECISION_BY_NAME
_SELF = "draw_dt_cone_gear_tl_phasing_comb"
_FAR_MM = part.GRIP_SPAN + part.SPRING_WIDTH
part_metadata(
    model_sources=("GLOBALS", "profile_points_mm"),
    precision_sources=("DRAWING_PRECISION", "DRAWING_PRECISION_BY_NAME"),
)


def _band(name: str) -> list[float]:
    """A printed sketch dimension's limits at its places."""
    return limits(part.GLOBALS[name], _P[name], unit=part.UNIT)


_PRINTED = ("GLOBALS", "UNIT", (_SELF, "FRONT_KEEP"))
requirement(
    "south_end",
    kind="face",
    faces=(PlanarFace((-1.0, 0.0, 0.0), 0.0),),
    requirements=("plane",),
    fields={
        "plane": (
            {"frame": "model", "axis": "x", "value": 0.0},
            ("profile_points_mm",),
        ),
        "outward": ([-1.0, 0.0, 0.0], ("profile_points_mm",)),
    },
)
requirement(
    "north_end",
    kind="face",
    faces=(PlanarFace((1.0, 0.0, 0.0), part.SHEET_LENGTH),),
    requirements=("length",),
    fields={
        "plane": (
            {"frame": "model", "axis": "x", "value": part.SHEET_LENGTH},
            ("SHEET_LENGTH",),
        ),
        "outward": ([1.0, 0.0, 0.0], ("SHEET_LENGTH",)),
        "length": (_band("SheetLength"), _PRINTED),
        "length_nominal": (part.SHEET_LENGTH, ("SHEET_LENGTH",)),
        "length_from": ("south_end", ((_SELF, "FRONT_KEEP"),)),
    },
    precision={"length": _P["SheetLength"]},
)
requirement(
    "seat",
    kind="face",
    faces=(PlanarFace((0.0, -1.0, 0.0), 0.0),),
    requirements=("plane",),
    fields={
        "plane": (
            {"frame": "model", "axis": "y", "value": 0.0},
            ("profile_points_mm",),
        ),
        "outward": ([0.0, -1.0, 0.0], ("profile_points_mm",)),
    },
)
requirement(
    "spring_inner",
    kind="face",
    faces=(PlanarFace((0.0, 1.0, 0.0), -part.GRIP_SPAN),),
    requirements=("grip_span", "grip_callout"),
    fields={
        "plane": (
            {"frame": "model", "axis": "y", "value": -part.GRIP_SPAN},
            ("GRIP_SPAN",),
        ),
        "outward": ([0.0, 1.0, 0.0], ("GRIP_SPAN",)),
        "grip_span": (_band("GripSpan"), _PRINTED),
        "grip_span_nominal": (part.GRIP_SPAN, ("GRIP_SPAN",)),
        "grip_span_from": ("seat", ((_SELF, "FRONT_KEEP"),)),
        "grip_callout": (part.GRIP_TEXT, ("GRIP_TEXT", "CALLOUTS_BELOW")),
    },
    precision={"grip_span": _P["GripSpan"]},
)
requirement(
    "far_edge",
    kind="face",
    faces=(PlanarFace((0.0, -1.0, 0.0), _FAR_MM),),
    requirements=("spring_width",),
    fields={
        "plane": (
            {"frame": "model", "axis": "y", "value": -_FAR_MM},
            ("GRIP_SPAN", "SPRING_WIDTH"),
        ),
        "outward": ([0.0, -1.0, 0.0], ("SPRING_WIDTH",)),
        "spring_width": (_band("SpringWidth"), _PRINTED),
        "spring_width_nominal": (part.SPRING_WIDTH, ("SPRING_WIDTH",)),
        "spring_width_from": ("spring_inner", ((_SELF, "FRONT_KEEP"),)),
    },
    precision={"spring_width": _P["SpringWidth"]},
)
requirement(
    "back",
    kind="face",
    faces=(PlanarFace((0.0, 1.0, 0.0), part.ARM_WIDTH),),
    requirements=("height",),
    fields={
        "plane": (
            {"frame": "model", "axis": "y", "value": part.ARM_WIDTH},
            ("ARM_WIDTH",),
        ),
        "outward": ([0.0, 1.0, 0.0], ("ARM_WIDTH",)),
        "height": (_band("SheetHeight"), _PRINTED),
        "height_nominal": (part.SHEET_HEIGHT, ("SHEET_HEIGHT",)),
        "height_from": ("far_edge", ((_SELF, "FRONT_KEEP"),)),
    },
    precision={"height": _P["SheetHeight"]},
)
requirement(
    "slot_end",
    kind="slot",
    faces=(CylinderFace(part.GRIP_SPAN),),
    requirements=("slot_length", "slot_callout"),
    fields={
        "at": (
            [part.SLOT_LENGTH, -part.GRIP_SPAN / 2.0, 0.0],
            ("SLOT_LENGTH", "GRIP_SPAN"),
        ),
        "slot_length": (_band("SlotLength"), _PRINTED),
        "slot_length_nominal": (part.SLOT_LENGTH, ("SLOT_LENGTH",)),
        "slot_length_from": ("south_end", ((_SELF, "FRONT_KEEP"),)),
        "slot_callout": (part.DEPTH_SUFFIX["SlotLength"].strip(), ("DEPTH_SUFFIX",)),
        "end_radius_ref": (part.SLOT_END_RADIUS_MM, ("SLOT_END_RADIUS_MM",)),
    },
    precision={"slot_length": _P["SlotLength"]},
)
for _teeth in part.BONDED_TEETH:
    _start, _depth = part.blade_start_name(_teeth), part.blade_depth_name(_teeth)
    _south = part.BLADE_START_MM[_teeth]
    _deep = part.BLADE_DEPTH_MM[_teeth]
    _faces = [
        PlanarFace((-1.0, 0.0, 0.0), -_south),
        PlanarFace((0.0, -1.0, 0.0), _deep),
    ]
    _fields = {
        "at": ([_south, -_deep, 0.0], ("profile_points_mm", "step_corner_index")),
        "start": (_band(_start), _PRINTED),
        "start_nominal": (_south, ("BLADE_START_MM",)),
        "start_from": ("south_end", ((_SELF, "FRONT_KEEP"),)),
        "depth": (_band(_depth), _PRINTED),
        "depth_nominal": (_deep, ("BLADE_DEPTH_MM",)),
        "depth_from": ("seat", ((_SELF, "FRONT_KEEP"),)),
        "callout": (part.DEPTH_SUFFIX[_depth].lstrip(", "), ("DEPTH_SUFFIX",)),
    }
    _requirements = ["start", "depth", "callout"]
    _precision = {"start": _P[_start], "depth": _P[_depth]}
    if _teeth == part.GEARS[-1]:
        # The last level ends where its blade's return rises to the seat.
        _faces.append(PlanarFace((1.0, 0.0, 0.0), part.LEVEL_END_MM))
        _fields["level_end"] = (_band("LevelEnd"), _PRINTED)
        _fields["level_end_nominal"] = (part.LEVEL_END_MM, ("LEVEL_END_MM",))
        _fields["level_end_from"] = ("south_end", ((_SELF, "FRONT_KEEP"),))
        _requirements.append("level_end")
        _precision["level_end"] = _P["LevelEnd"]
    requirement(
        f"blade_{part.gear_tag(_teeth).lower()}",
        kind="profile",
        faces=tuple(_faces),
        requirements=tuple(_requirements),
        fields=_fields,
        precision=_precision,
    )
requirement(
    "underside",
    kind="face",
    faces=(PlanarFace((0.0, 0.0, -1.0), 0.0),),
    requirements=("plane",),
    fields={
        "plane": ({"frame": "model", "axis": "z", "value": 0.0}, ("SHEET_THICK",)),
        "outward": ([0.0, 0.0, -1.0], ("SHEET_THICK",)),
    },
)
requirement(
    "top",
    kind="face",
    faces=(PlanarFace((0.0, 0.0, 1.0), part.SHEET_THICK),),
    requirements=("thickness_ref", "stock", "stock_thickness"),
    fields={
        "plane": (
            {"frame": "model", "axis": "z", "value": part.SHEET_THICK},
            ("SHEET_THICK",),
        ),
        "outward": ([0.0, 0.0, 1.0], ("SHEET_THICK",)),
        "thickness_ref": (part.SHEET_THICK, ("SHEET_THICK", (_SELF, "BOTTOM_KEEP"))),
        "stock": (part.STOCK_TEXT, ("STOCK_TEXT",)),
        "stock_thickness": (
            [part.SHEET_LIMITS_MM[0], part.SHEET_LIMITS_MM[2]],
            ("SHEET_LIMITS_MM",),
        ),
        "stock_thickness_nominal": (part.SHEET_THICK, ("SHEET_THICK",)),
    },
    precision={"thickness_ref": _P["SheetThick"], "stock_thickness": _P["SheetThick"]},
)


def text_blocks() -> dict[str, tuple[float, float, float, float]]:
    """(left, bottom, right, top) of each dimension's text: its value's line
    (with any suffix) and its callout's lines, centred on its keep or offset
    point, or left of its line when it stands outside."""
    blocks = {}
    for name, (x, y) in (FRONT_KEEP | BOTTOM_KEEP).items():
        callout = part.CALLOUTS_BELOW.get(name, "").splitlines()
        places = part.DRAWING_PRECISION_BY_NAME[name]
        value = DEPTH_TEXT_WIDTH if places == 3 else TWO_PLACE_TEXT_WIDTH
        value += CHAR_WIDTH * len(part.DEPTH_SUFFIX.get(name, ""))
        width = max([value, *(len(line) * CHAR_WIDTH for line in callout)])
        x, y = OFFSET_TEXT.get(name, (x, y))
        left = x - width if name in OUTSIDE_LEFT else x - width / 2.0
        half = (1 + len(callout)) * LINE_HEIGHT / 2.0
        blocks[name] = (left, y - half, left + width, y + half)
    return blocks


def sheet_dimension_names() -> set[str]:
    return set().union(*part.DRAWING_DIMENSIONS.values())


_DIMENSION_TEXT_SUFFIX = 2  # swDimensionTextParts_e.swDimensionTextSuffix


def _set_suffixes(adapter: Any, annotations: list[Any]) -> None:
    """Each depth's function after its value, on its line (rules 3 and 4)."""
    remaining = dict(part.DEPTH_SUFFIX)
    for annotation in annotations:
        name = dimension_name(adapter, annotation)
        text = remaining.pop(name, None)
        if text is None:
            continue
        display = _early_bound(
            _early_bound(annotation, "IAnnotation").GetSpecificAnnotation(),
            "IDisplayDimension",
        )
        display.SetText(_DIMENSION_TEXT_SUFFIX, text)
        if str(display.GetText(_DIMENSION_TEXT_SUFFIX)) != text:
            raise RuntimeError(
                f"{name}: suffix reads back {display.GetText(_DIMENSION_TEXT_SUFFIX)!r}"
            )
    if remaining:
        raise RuntimeError(f"depth suffixes not applied: {sorted(remaining)}")
    rebuild_drawing(adapter, label="depth suffixes")


def _place_point(
    adapter: Any,
    view: Any,
    point_mm: tuple[float, float, float],
    target: tuple[float, float],
    *,
    label: str,
) -> None:
    """Move ``view`` so the model point lands on ``target`` (sheet m)."""
    view = _early_bound(view, "IView")
    point = tuple(value / 1000.0 for value in point_mm)
    here = model_point_in_view(adapter, view, point, label=label)
    position = tuple(float(value) for value in view.Position)
    moved = [position[i] + target[i] - here[i] for i in range(2)]
    if not view.SetViewPosition(double_array(moved), False):
        raise RuntimeError(f"failed to move the {label}")
    rebuild_drawing(adapter, label=f"place {label}")
    here = model_point_in_view(adapter, view, point, label=label)
    if math.dist(here, target) > 1e-4:
        raise RuntimeError(f"{label}: point sits at {here!r}, not {target!r}")


def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source phasing comb missing: {SOURCE}")
    check("open phasing comb", adapter.open_model(str(SOURCE)))
    required = (
        "Number",
        "Material Specification",
        "Finish",
        "Quantity",
        "Isometric View Note",
    )
    read_required_properties(
        adapter.currentModel, ("Revision", "Title", *required), required=required
    )
    drawing, _sheet = new_project_drawing(
        adapter,
        property_view=PART_STEM,
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        unit=part.UNIT,
    )
    stamp_drawing_summary(
        adapter,
        drawing,
        {
            0: "Cone Tip Gear Phasing Comb Drawing",
            1: "Harmonic Analyzer shop tooling drawing",
            2: "Harmonic Analyzer Project",
            3: "cone tip gear phasing comb; flat sheet U, one blade each, T030-T006; MHA-DT-03-TL-02",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_ORIGIN, scale=VIEW_SCALE)
    bottom = place_view(
        adapter,
        str(SOURCE),
        "*Bottom",
        FRONT_ORIGIN[0],
        BOTTOM_CENTER_Y,
        scale=VIEW_SCALE,
    )
    # finalize_drawing shades the pictorial isometric with edges.
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    _place_point(adapter, front, (0.0, 0.0, 0.0), FRONT_ORIGIN, label="front view")
    # Projection-aligned below the front view, the sheet's mid-thickness on
    # BOTTOM_CENTER_Y.
    _place_point(
        adapter,
        bottom,
        (0.0, 0.0, part.SHEET_THICK / 2.0),
        (FRONT_ORIGIN[0], BOTTOM_CENTER_Y),
        label="bottom view",
    )
    for view in (front, bottom, iso):
        set_hidden_lines_removed(adapter, view)
    annotations: list[Any] = []
    for view, keep, label in (
        (front, FRONT_KEEP, "front view"),
        (bottom, BOTTOM_KEEP, "bottom view"),
    ):
        annotations += curate_view_dimensions(
            adapter,
            view,
            keep=keep,
            view_label=label,
            dimensions_by_feature=part.DRAWING_DIMENSIONS,
        )
    printed = {dimension_name(adapter, annotation) for annotation in annotations}
    if printed != sheet_dimension_names():
        raise RuntimeError(
            f"sheet prints {sorted(printed)}, the part marks {sorted(sheet_dimension_names())}"
        )
    set_dimension_callouts(adapter, annotations, part.CALLOUTS_BELOW)
    _set_suffixes(adapter, annotations)
    # The sheet's thickness is the stock's, a reference over SHEET STOCK.
    references = [
        (dimension_name(adapter, item), item)
        for item in annotations
        if dimension_name(adapter, item) in part.REFERENCE_DIMENSIONS
    ]
    if sorted(name for name, _ in references) != sorted(part.REFERENCE_DIMENSIONS):
        raise RuntimeError(
            f"expected one native stock thickness: {sorted(part.REFERENCE_DIMENSIONS)}"
        )
    for name, item in references:
        set_reference_dimension(adapter, item, label=f"{name} stock thickness")
    offset_dimension_text(adapter, annotations, OFFSET_TEXT)
    assert_imported_precision(adapter, annotations, part.DRAWING_PRECISION_BY_NAME)
    for view in (front, bottom, iso):
        set_hidden_lines_removed(adapter, view)
    drawing.ClearSelection2(True)
    _early_bound(drawing, "IDrawingDoc").EditSheet()
    add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_XY)
    return finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Cone Tip Gear Phasing Comb Drawing",
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
