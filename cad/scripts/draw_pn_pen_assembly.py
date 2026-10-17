r"""Create the three-sheet pen fitter package (MHA-PN-000).

Sheet 1 shows the pen assembled (front and right) beside three details that
carry its settings as the builder's driving, toleranced model dimensions:
DETAIL A the stud height and its jam nut (``StudSetting``), DETAIL B the
hanger screw's nut and jam nut, DETAIL C the pen yaw and nib preset
(``CarriageSetting``), with the as-shipped note; sheet 2 the builder-owned
``PN_EXPLODED`` presentation with the BOM (numbers, descriptions, vendor SKU,
quantity) and a balloon on every row; sheet 3 the finished isometric beside
the numbered assembly sequence and checks. Every setting and pose comes from
``pn_pen_assembly_spec``, every printed text and detail region from
``pn_pen_assembly_notes``, the rest from the part registry; this recipe only
lays the sheets out. It never edits the source assembly or its explodes.
"""

from __future__ import annotations

import argparse
import math
import sys
import textwrap
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import _config
import _telemetry
import pn_pen_adjust_screw_spec as stud
import pn_pen_assembly_notes as notes
import pn_pen_assembly_spec as spec
import pn_pen_hanger_spec as hanger
import pn_pen_rod_spec as rod
import vn_pen_wire_geom as wire
from _check import check
from _com import _early_bound
from _session import run_build
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
    set_high_quality_shaded_with_edges,
)
from _drawing_dimension_import import curate_view_dimensions
from _drawing_dimensions import assert_imported_precision, set_dimension_callouts
from _drawing_hidden_sketches import _show_base_view_sketches
from _drawing_projection import model_point_in_view
from _drawing_registry import DRAWING_TEMPLATES, DRAWINGS_BY_NAME, DrawingLayout
from _drawing_sheets import create_blank_drawing_sheets
from _drawing_tables import insert_bom_table
from _drawing_view_configuration import (
    ASSEMBLY_VIEW_CONFIGURATION,
    SIMPLIFIED_VIEW_CONFIGURATION,
    ViewRole,
    apply_view_configuration,
    assert_full_detail_view,
    set_view_exploded_state,
)
from _drawing_view_display import set_hidden_lines_removed
from _named_views import octant_view_name
from _simplified_names import simplified_name
from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import (
    add_note,
    dimension_name,
    place_view,
    view_name,
)


SPEC = DRAWINGS_BY_NAME["pn_pen_assembly"]
ARTIFACT_STEM = SPEC.artifact_stem
SOURCE = SPEC.source
OUTPUTS = DrawingOutputs(
    slddrw=SPEC.outputs["slddrw"],
    pdf=SPEC.outputs["pdf"],
    png=SPEC.outputs["png"],
)
SLDDRW = OUTPUTS.slddrw
PDF = OUTPUTS.pdf
PNG = OUTPUTS.png
PDF_TITLE = "Pen Assembly Drawing Package"

SHEET_NAMES = (
    "ASSEMBLED VIEWS + SETTINGS",
    "EXPLODED VIEW + BOM",
    "ASSEMBLY STEPS",
)
if SPEC.layout is not DrawingLayout.LANDSCAPE:
    raise AssertionError("the pen package sheets are landscape")
SHEET_LAYOUTS = {name: DrawingLayout.LANDSCAPE for name in SHEET_NAMES}
SHEET_SCALE = (1.0, 2.0)
SHEET_SCALES = {name: SHEET_SCALE for name in SHEET_NAMES}

# Sheet geometry, metres: the template's inner border and the title block in
# its lower-right corner. Every view outline, balloon ring, dimension and note
# stays inside the border and out of the title block (drawing-guidelines.md
# rule 13 (stay inside the border)).
_TEMPLATE = DRAWING_TEMPLATES[DrawingLayout.LANDSCAPE]
SHEET_INNER_BORDER = (
    0.0127,
    0.0127,
    _TEMPLATE.width_m - 0.0127,
    _TEMPLATE.height_m - 0.0127,
)
TITLE_BLOCK = (
    _TEMPLATE.title_block_left_m,
    0.0,
    _TEMPLATE.width_m,
    _TEMPLATE.title_block_top_m,
)
# Default-format note text measured on the ms package (farm run
# 20261015T235155114Z): 2.55 mm per character, 4.53 mm per line.
NOTE_GAP = 0.006
VIEW_LABEL_GAP = 0.004

# --- sheet 1: assembled views and the three settings details -------------------
# The pen at 1:2: front and right side by side down the left, labels under
# them; DETAIL C (the carriage plan at 2:1, turned marker-axis across) under
# them; DETAILs A and B at 2:1 across the top right with the as-shipped note
# under them.
FRONT_CENTER = (0.050, 0.192)
RIGHT_CENTER = (0.125, 0.192)
SETTINGS_NOTE_XY = (0.225, 0.150)
SETTINGS_NOTE_WIDTH = 70  # characters
CROP_NO_ERROR = 1  # swCropViewErrors_e.swCropViewErrors_NoError
DETAIL_POSITION_TOL_M = 1e-4
DETAIL_LETTER_GAP = 0.001
BOUNDARY_COLOR = 0  # COLORREF black, the outline's colour.
BOUNDED_ON_RIGHT = frozenset(("stud", "hanger"))
TRAIL_LINE_STYLE = 2  # swLineStyles_e.swLinePHANTOM: the explode trail

_CARRIAGE_STEMS = frozenset(
    (
        spec.ROD,
        spec.V_BLOCK,
        spec.FRAME,
        spec.THUMB_SCREW,
        spec.ROD_SET_SCREW,
        spec.MARKER,
    )
)


@dataclass(frozen=True)
class Detail:
    """One isolated, circle-cropped model view of a setting or a lock.

    ``model_centre`` (machine mm) lands on the sheet at ``centre``; the crop
    circle reaches ``radius_mm`` model millimetres round it. ``feature`` is the
    builder's settings sketch whose marked dimensions the detail prints
    (``None``: a lock shown, nothing dimensioned). ``axis_points`` (machine mm,
    from, to), when given, is the direction the view is turned to lay along
    sheet +X."""

    key: str
    orientation: str
    scale: tuple[int, int]
    model_centre: tuple[float, float, float]
    radius_mm: float
    centre: tuple[float, float]
    stems: frozenset[str]
    feature: str | None
    label_xy: tuple[float, float]
    axis_points: (
        tuple[tuple[float, float, float], tuple[float, float, float]] | None
    ) = None

    @property
    def title(self) -> str:
        return notes.SHEET_TITLES[self.key]

    @property
    def label(self) -> str:
        return f"pen {self.key} detail"

    @property
    def mm(self) -> float:
        """Sheet metres per model millimetre."""
        return self.scale[0] / self.scale[1] / 1000.0

    @property
    def crop_radius(self) -> float:
        return self.radius_mm * self.mm

    @property
    def model_centre_m(self) -> tuple[float, float, float]:
        return tuple(value / 1000.0 for value in self.model_centre)


STUD_DETAIL = Detail(
    key="stud",
    orientation="*Right",
    scale=(2, 1),
    model_centre=notes.STUD_DETAIL_CENTRE,
    radius_mm=notes.STUD_DETAIL_RADIUS,
    centre=(0.262, 0.214),
    stems=frozenset((spec.ROD, spec.STUD, spec.STUD_NUT, spec.WIRE)),
    feature=spec.STUD_FEATURE,
    label_xy=(0.246, 0.180),
)
HANGER_DETAIL = Detail(
    key="hanger",
    orientation="*Right",
    scale=(2, 1),
    model_centre=notes.HANGER_DETAIL_CENTRE,
    radius_mm=notes.HANGER_DETAIL_RADIUS,
    centre=(0.362, 0.214),
    stems=frozenset(
        (spec.HANGER, spec.HANGER_SCREW, spec.HANGER_NUT, spec.HANGER_JAM_NUT)
    ),
    feature=None,
    label_xy=(0.346, 0.174),
)
CARRIAGE_DETAIL = Detail(
    key="carriage",
    orientation="*Top",
    scale=(2, 1),
    model_centre=notes.CARRIAGE_DETAIL_CENTRE,
    radius_mm=notes.CARRIAGE_DETAIL_RADIUS,
    centre=(0.110, 0.058),
    stems=_CARRIAGE_STEMS,
    feature=spec.CARRIAGE_FEATURE,
    label_xy=(0.156, 0.090),
    axis_points=notes.CARRIAGE_AXIS_POINTS,
)
DETAILS = (STUD_DETAIL, HANGER_DETAIL, CARRIAGE_DETAIL)


def _top_plan_point(uv: tuple[float, float]) -> tuple[float, float, float]:
    """A Top-plane sketch point (u, v) = machine (X, -Z) as machine mm; the
    plan view projects Y away."""
    return (uv[0], notes.CARRIAGE_DETAIL_CENTRE[1], -uv[1])


# Each kept dimension's text point, machine mm, projected into its detail.
DIMENSION_TEXT_POINTS = {
    STUD_DETAIL.key: {
        spec.STUD_DIMENSION: notes.STUD_TEXT_POINT,
    },
    CARRIAGE_DETAIL.key: {
        spec.YAW_DIMENSION: _top_plan_point(spec.YAW_TEXT_UV),
        spec.NIB_DIMENSION: _top_plan_point(notes.NIB_TEXT_UV),
    },
}
# Every callout is two lines, which only the below compartment prints.
CALLOUT_LOCATION = "below"
CALLOUT_TEXT_PART = 4  # swDimensionTextParts_e: swDimensionTextCalloutBelow
if set(notes.DIMENSION_CALLOUTS) != {
    name for names in spec.DRAWING_DIMENSIONS.values() for name in names
}:
    raise AssertionError("every pen setting carries its callout")

# --- sheet 2: the exploded isometric, BOM and balloons ---------------------------
BOM_COLUMN_WIDTHS = {
    "item": 0.012,
    "part": 0.030,
    "description": 0.086,
    "sku": 0.028,
    "quantity": 0.012,
}
BOM_SKU_TITLE = "VENDOR SKU"
MADE_PART_SKU = "-"
BOM_ROW_HEIGHT = 0.006
BOM_ANCHOR = (
    SHEET_INNER_BORDER[2] - sum(BOM_COLUMN_WIDTHS.values()) - 0.003,
    SHEET_INNER_BORDER[3] - 0.004,
)
# The header and the marker's row wrap to two lines: the table measured 91.5 mm
# tall (farm run 20261016T064716571Z), not its 14 rows at BOM_ROW_HEIGHT.
BOM_WRAPPED_LINES = 2
EXPLODED_CAPTION_XY = (
    BOM_ANCHOR[0],
    BOM_ANCHOR[1]
    - (len(spec.BOM_ORDER) + 1 + BOM_WRAPPED_LINES) * BOM_ROW_HEIGHT
    - NOTE_GAP,
)
BALLOON_MARGIN = 0.012
# The exploded outline plus its balloon ring keeps left of the BOM.
EXPLODED_RIGHT_LIMIT = BOM_ANCHOR[0] - 0.006
EXPLODED_ISO_CENTER = (
    (SHEET_INNER_BORDER[0] + EXPLODED_RIGHT_LIMIT) / 2.0,
    (SHEET_INNER_BORDER[1] + SHEET_INNER_BORDER[3]) / 2.0,
)
# Largest first: the sheet scale, then smaller only if the ring overflows.
EXPLODED_SCALES = ((1.0, 2.0), (2.0, 5.0), (1.0, 3.0))

BOM_QUANTITIES = {stem: spec.QUANTITIES[stem] for stem in spec.BOM_ORDER}
BOM_COMPONENTS = tuple(BOM_QUANTITIES)
# Literal stems, so the config-dependency analysis reads exactly these rows.
PART_ROWS = {
    "pn-pen-hanger": _config.parts("pn-pen-hanger"),
    "pn-pen-rod": _config.parts("pn-pen-rod"),
    "pn-pen-v-block": _config.parts("pn-pen-v-block"),
    "vn-pen-marker": _config.parts("vn-pen-marker"),
    "pn-pen-frame": _config.parts("pn-pen-frame"),
    "vn-pen-set-screw": _config.parts("vn-pen-set-screw"),
    "vn-pen-rod-set-screw": _config.parts("vn-pen-rod-set-screw"),
    "pn-pen-adjust-screw": _config.parts("pn-pen-adjust-screw"),
    "vn-pen-adjust-nut": _config.parts("vn-pen-adjust-nut"),
    "vn-pen-wire": _config.parts("vn-pen-wire"),
    "vn-hanger-screw": _config.parts("vn-hanger-screw"),
    "vn-pen-hanger-nut": _config.parts("vn-pen-hanger-nut"),
    "vn-pen-hanger-jam-nut": _config.parts("vn-pen-hanger-jam-nut"),
}
if set(PART_ROWS) != set(BOM_COMPONENTS):
    raise AssertionError("BOM registry rows must cover exactly the pen families")
BOM_PART_NUMBERS = {stem: str(row["number"]) for stem, row in PART_ROWS.items()}
# The registry owns part numbers and vendor SKU; components own material/finish.
BOM_SKUS = {
    stem: " / ".join(str(sku) for sku in row.get("supplier_skus") or ())
    or MADE_PART_SKU
    for stem, row in PART_ROWS.items()
}
BOM_DESCRIPTIONS = dict(notes.BOM_DESCRIPTIONS)
BOM_IDENTITY_ALIASES = {number: stem for stem, number in BOM_PART_NUMBERS.items()}
BOM_NORMALIZED_ALIASES = {
    alias.casefold(): stem for alias, stem in BOM_IDENTITY_ALIASES.items()
}
# Every family is one separated body on the exploded view: each balloon walks
# its own part for a visible edge, except two pinned off the stack the stud,
# its jam nut and the rod's top make in the pictorial. There the three walked
# attachments sat within 2 mm of one sheet bearing at different radii, so
# leaders 2/9 and 8/9 crossed (farm run 20261016T061511876Z). The rod's
# balloon takes the vertical corner of its square nearest the viewer, low down
# (part mm: square x, z +-S/2, y up from the shoulder; the rod is placed
# unrotated); the stud's the sheet-rightmost point of its head's top edge
# (revolved about +Y; the octant's sheet-right is (sz, 0, -sx)). The wire's
# takes the sheet-leftmost point of its top end (extruded up +Y from the
# origin, unrotated): walked, it took the end by the strap's corner and its
# leader crossed the strap and the hanger screw (machinist review r3). The
# hanger's takes the strap's sheet-rightmost long edge at mid-length (part mm:
# Front-plane outline, top edge y 0, extruded from the bar seat z 0 to -T;
# placed unrotated): walked, it took the strap's top corner, its leader ran
# along screw 11's shank and landed beside balloon 11's arrow (machinist gate
# 2026-10-17). Sheet-right (-1, 0, 1) makes that edge the strap's -x side on
# its bar-seat face: a silhouette, clear of the screw, nuts and U guides.
_OCTANT_X, _, _OCTANT_Z = spec.EXPLODED_OCTANT
_ROD_ANCHOR_Y = 40.0
_HEAD_R = stud.HEAD_DIA / 2.0
_WIRE_R = wire.WIRE_DIA / 2.0
if (_OCTANT_Z, -_OCTANT_X) != (-1, 1):
    raise AssertionError("the hanger anchor assumes sheet-right is (-x, +z)")
HANGER_ANCHOR_MM = (
    (hanger.STRAP_TOP_X[0] + hanger.STRAP_BOT_X[0]) / 2.0,
    hanger.STRAP_BOT_Y / 2.0,
    hanger.STRAP_Z[1],
)
BALLOON_ANCHORS = {
    **{stem: BalloonAnchor() for stem in BOM_COMPONENTS},
    spec.ROD: BalloonAnchor(
        point_mm=(
            _OCTANT_X * rod.ROD_SECTION / 2.0,
            _ROD_ANCHOR_Y,
            _OCTANT_Z * rod.ROD_SECTION / 2.0,
        )
    ),
    spec.STUD: BalloonAnchor(
        point_mm=(
            _OCTANT_Z * _HEAD_R * math.sqrt(0.5),
            stud.OVERALL_LENGTH,
            -_OCTANT_X * _HEAD_R * math.sqrt(0.5),
        )
    ),
    spec.WIRE: BalloonAnchor(
        point_mm=(
            -_OCTANT_Z * _WIRE_R * math.sqrt(0.5),
            wire.WIRE_LEN,
            _OCTANT_X * _WIRE_R * math.sqrt(0.5),
        )
    ),
    spec.HANGER: BalloonAnchor(point_mm=HANGER_ANCHOR_MM),
}
EXPLODED_ORIENTATION = octant_view_name(*spec.EXPLODED_OCTANT)

EXPLODED_VIEW_NAMES = {
    ASSEMBLY_VIEW_CONFIGURATION: spec.EXPLODED_VIEW_NAME,
    SIMPLIFIED_VIEW_CONFIGURATION: simplified_name(spec.EXPLODED_VIEW_NAME),
}
if spec.SOURCE_CONFIGURATION != ASSEMBLY_VIEW_CONFIGURATION:
    raise AssertionError("the pen explode is authored in Default")

# --- sheet 3: the finished isometric beside the sequence and checks --------------
ASSEMBLY_ISO_CENTER = (0.062, 0.145)
STEPS_TOP = SHEET_INNER_BORDER[3] - 0.005
STEPS_LINE_WIDTH = 108  # characters


def _wrapped(lines: tuple[str, ...], *, width: int, heading: str | None = None) -> str:
    """Wrap each numbered line under its own number; one note per block."""
    out = [heading] if heading else []
    for line in lines:
        number, sep, rest = line.partition(". ")
        if sep and number.isdigit():
            out += textwrap.wrap(
                rest,
                width=width,
                initial_indent=f"{number}. ",
                subsequent_indent=" " * (len(number) + 2),
            )
        else:
            out += textwrap.wrap(line, width=width, subsequent_indent="   ")
    return "\n".join(out)


SETTINGS_NOTE = _wrapped((notes.SETTINGS_NOTE,), width=SETTINGS_NOTE_WIDTH)
ASSEMBLY_STEPS = _wrapped(
    notes.ASSEMBLY_STEPS, width=STEPS_LINE_WIDTH, heading="ASSEMBLY SEQUENCE"
)
ASSEMBLY_CHECKS = _wrapped(notes.ASSEMBLY_CHECKS, width=STEPS_LINE_WIDTH)

Box = tuple[float, float, float, float]


def _activate_sheet(adapter: Any, name: str) -> Any:
    ddoc = _early_bound(adapter.currentModel, "IDrawingDoc")
    if not ddoc.ActivateSheet(name):
        raise RuntimeError(f"failed to activate drawing sheet {name!r}")
    current = _early_bound(ddoc.GetCurrentSheet(), "ISheet")
    actual = str(current.GetName() or "")
    if actual != name:
        raise RuntimeError(f"active drawing sheet is {actual!r}, expected {name!r}")
    return current


def _sheet_findings(box: Box, *, right_limit: float | None = None) -> list[str]:
    """Why ``box`` (sheet metres) leaves the drawable sheet, if it does."""
    x0, y0, x1, y1 = box
    left, bottom, right, top = SHEET_INNER_BORDER
    if right_limit is not None:
        right = min(right, right_limit)
    findings = []
    if x0 < left or y0 < bottom or x1 > right or y1 > top:
        findings.append(f"leaves the drawable area {(left, bottom, right, top)}")
    tx0, ty0, tx1, ty1 = TITLE_BLOCK
    if x1 > tx0 and x0 < tx1 and y0 < ty1 and y1 > ty0:
        findings.append(f"enters the title block {TITLE_BLOCK}")
    return findings


def _assert_on_sheet(box: Box, *, label: str, right_limit: float | None = None) -> None:
    findings = _sheet_findings(box, right_limit=right_limit)
    if findings:
        raise RuntimeError(f"{label}: {box!r} " + "; ".join(findings))


def _note_box(note: Any, *, label: str) -> Box:
    """``INote.GetExtent``'s lower-left and upper-right corners, sheet metres."""
    values = tuple(float(value) for value in (note.GetExtent() or ()))
    if len(values) != 6 or not all(map(math.isfinite, values)):
        raise RuntimeError(f"{label}: invalid note extent {values!r}")
    box = (values[0], values[1], values[3], values[4])
    if box[0] >= box[2] or box[1] >= box[3]:
        raise RuntimeError(f"{label}: empty note extent {values!r}")
    return box


def _add_note_block(
    adapter: Any, sheet_name: str, text: str, xy: tuple[float, float], *, label: str
) -> Box:
    """A sheet-owned note (activate the sheet so no view owns it), proved
    printed as given and on the drawable sheet; returns its extent."""
    _activate_sheet(adapter, sheet_name)
    note = add_note(adapter, text, *xy)
    if note is None:
        raise RuntimeError(f"failed to place the pen {label}")
    note = _early_bound(note, "INote")
    printed = str(note.GetText() or "").replace("\r\n", "\n").replace("\r", "\n")
    if printed != text:
        raise RuntimeError(f"pen {label} printed as {printed!r}")
    box = _note_box(note, label=label)
    _assert_on_sheet(box, label=f"pen {label}")
    return box


def _view_outline(view: Any, *, label: str) -> Box:
    outline = tuple(float(value) for value in _early_bound(view, "IView").GetOutline())
    if len(outline) != 4 or outline[2] <= outline[0] or outline[3] <= outline[1]:
        raise RuntimeError(f"{label}: invalid view outline {outline!r}")
    return outline[0], outline[1], outline[2], outline[3]


def _grown(box: Box, margin: float) -> Box:
    return box[0] - margin, box[1] - margin, box[2] + margin, box[3] + margin


def _center_view_outline(
    adapter: Any, view: Any, center: tuple[float, float], *, label: str
) -> None:
    """Translate the view so its measured outline centres on ``center``."""
    view = _early_bound(view, "IView")
    x0, y0, x1, y1 = _view_outline(view, label=label)
    before = tuple(float(value) for value in view.Position)
    target = (
        before[0] + center[0] - (x0 + x1) / 2.0,
        before[1] + center[1] - (y0 + y1) / 2.0,
    )
    if not view.SetViewPosition(double_array(list(target)), False):
        raise RuntimeError(f"{label}: SetViewPosition refused {target!r}")
    adapter.currentModel.EditRebuild3()
    after = tuple(float(value) for value in view.Position)
    if len(after) != 2 or any(abs(a - b) > 1e-6 for a, b in zip(after, target)):
        raise RuntimeError(f"{label}: view moved to {after!r}, expected {target!r}")
    x0, y0, x1, y1 = _view_outline(view, label=label)
    if (
        abs((x0 + x1) / 2.0 - center[0]) > 1e-6
        or abs((y0 + y1) / 2.0 - center[1]) > 1e-6
    ):
        raise RuntimeError(f"{label}: measured outline did not centre at {center!r}")


def _set_view_scale(
    adapter: Any, view: Any, scale: tuple[float, float], *, label: str
) -> None:
    """Re-scale a placed drawing view and read the scale back."""
    view = _early_bound(view, "IView")
    view.ScaleRatio = double_array([float(scale[0]), float(scale[1])])
    adapter.currentModel.EditRebuild3()
    ratio = tuple(float(value) for value in view.ScaleRatio)
    if len(ratio) != 2 or abs(ratio[0] / ratio[1] - scale[0] / scale[1]) > 1e-9:
        raise RuntimeError(f"{label}: view scale reads {ratio!r}, expected {scale!r}")


def _scale_text(scale: tuple[float, float]) -> str:
    return f"{scale[0]:g} : {scale[1]:g}"


def _activate_view(adapter: Any, view: Any, *, label: str) -> str:
    name = view_name(adapter, view)
    if not _early_bound(adapter.currentModel, "IDrawingDoc").ActivateView(name):
        raise RuntimeError(f"failed to activate the {label} {name!r}")
    adapter.currentModel.ClearSelection2(True)
    return name


def _label_view(
    adapter: Any, view: Any, text: str, xy: tuple[float, float], *, label: str
) -> Box:
    """A view-owned label note at ``xy``, proved on the drawable sheet."""
    _activate_view(adapter, view, label=label)
    note = add_note(adapter, text, *xy)
    if note is None:
        raise RuntimeError(f"failed to label the {label}")
    box = _note_box(_early_bound(note, "INote"), label=label)
    _assert_on_sheet(box, label=f"{label} label")
    return box


def _component_stem(component: Any) -> str:
    component = _early_bound(component, "IComponent2")
    path = str(component.GetPathName() or "")
    if not path:
        raise RuntimeError(f"component {component.Name2!r} has no referenced path")
    return Path(path).stem.casefold()


def _validate_source(source_model: Any) -> None:
    """The builder-owned explodes exist, and the source opens collapsed with
    exactly the contracted families."""
    assembly = _early_bound(source_model, "IAssemblyDoc")
    manager = _early_bound(source_model.ConfigurationManager, "IConfigurationManager")
    configuration = _early_bound(manager.ActiveConfiguration, "IConfiguration")
    if str(configuration.Name) != ASSEMBLY_VIEW_CONFIGURATION:
        raise RuntimeError("pen source must open in its Default configuration")
    for owner, wanted in EXPLODED_VIEW_NAMES.items():
        names = tuple(assembly.GetExplodedViewNames2(owner) or ())
        if names != (wanted,):
            raise RuntimeError(f"pen {owner} exploded views {names!r} != {(wanted,)!r}")
    counts: dict[str, int] = {}
    for raw in tuple(assembly.GetComponents(True) or ()):
        component = _early_bound(raw, "IComponent2")
        stem = _component_stem(component)
        counts[stem] = counts.get(stem, 0) + 1
        total = _early_bound(component.GetTotalTransform(True), "IMathTransform")
        base = _early_bound(component.GetTotalTransform(False), "IMathTransform")
        if any(
            abs(float(actual) - float(expected)) > 1e-9
            for actual, expected in zip(total.ArrayData, base.ArrayData, strict=True)
        ):
            raise RuntimeError(
                f"pen source must open collapsed: {component.Name2!r} is displaced"
            )
    if counts != BOM_QUANTITIES:
        raise RuntimeError(f"pen families {counts!r} != contract {BOM_QUANTITIES!r}")


# --- sheet 1 ----------------------------------------------------------------------


def _placed_base_view(
    adapter: Any,
    orientation: str,
    center: tuple[float, float],
    title: str,
    *,
    label: str,
) -> Any:
    view = place_view(adapter, str(SOURCE), orientation, *center, scale=SHEET_SCALE)
    set_hidden_lines_removed(adapter, view)
    apply_view_configuration(adapter, view, role=ViewRole.PLAIN, label=label)
    _center_view_outline(adapter, view, center, label=label)
    x0, y0, x1, _y1 = _view_outline(view, label=label)
    _assert_on_sheet((x0, y0, x1, _y1), label=label)
    _label_view(adapter, view, title, (x0, y0 - VIEW_LABEL_GAP), label=label)
    return view


def _turn_detail(adapter: Any, view: Any, detail: Detail) -> None:
    """Turn ``view`` so ``detail.axis_points`` read along sheet +X, and prove
    it (the dt_crank_drive_gear A-A turn: ``IView.Angle`` less the axis's
    sheet angle)."""
    native = _early_bound(view, "IView")
    label = f"{detail.label} axis"

    def axis() -> tuple[float, float]:
        start, end = (
            model_point_in_view(
                adapter,
                native,
                tuple(value / 1000.0 for value in point),
                label=label,
            )
            for point in detail.axis_points or ()
        )
        return end[0] - start[0], end[1] - start[1]

    dx, dy = axis()
    native.Angle = float(native.Angle) - math.atan2(dy, dx)
    adapter.currentModel.EditRebuild3()
    dx, dy = axis()
    if dx <= 0.0 or abs(dy) > 1e-8:
        raise RuntimeError(f"{label} did not turn across: ({dx!r}, {dy!r})")
    _telemetry.info(f"{label}: turned to {math.degrees(float(native.Angle)):.3f} deg")


def _placed_detail(adapter: Any, detail: Detail) -> Any:
    """``detail`` uncropped and isolated: its orientation at its scale, moved
    so ``detail.model_centre`` lands on ``detail.centre``."""
    view = _early_bound(
        place_view(
            adapter, str(SOURCE), detail.orientation, *detail.centre, scale=detail.scale
        ),
        "IView",
    )
    set_hidden_lines_removed(adapter, view)
    apply_view_configuration(adapter, view, role=ViewRole.PLAIN, label=detail.label)
    if detail.axis_points is not None:
        _turn_detail(adapter, view, detail)
    label = f"{detail.label} centre"
    centre = model_point_in_view(adapter, view, detail.model_centre_m, label=label)
    position = tuple(float(value) for value in view.Position)
    target = [position[axis] + detail.centre[axis] - centre[axis] for axis in range(2)]
    if not view.SetViewPosition(double_array(target), False):
        raise RuntimeError(f"failed to move the {detail.label} onto its spot")
    adapter.currentModel.EditRebuild3()
    centre = model_point_in_view(adapter, view, detail.model_centre_m, label=label)
    if max(abs(a - b) for a, b in zip(centre, detail.centre)) > DETAIL_POSITION_TOL_M:
        raise RuntimeError(
            f"{detail.label} centre sits at {centre!r}, not {detail.centre!r}"
        )
    isolate_drawing_view_components(
        adapter, view, visible_stems=detail.stems, label=detail.label
    )
    return view


def _sketch_in_view(
    adapter: Any,
    view: Any,
    sheet_points: tuple[tuple[float, float], tuple[float, float]],
    kind: str,
    *,
    label: str,
) -> Any:
    """A ``kind`` ("circle": centre, rim point; "line": ends) at two sheet
    points (metres) in ``view``'s own sketch, left selected."""
    view = _early_bound(view, "IView")
    _activate_view(adapter, view, label=label)
    sketch = _early_bound(view.GetSketch(), "ISketch")
    transform = _early_bound(sketch.ModelToSketchTransform, "IMathTransform")
    utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    points = []
    for x, y in sheet_points:
        point = _early_bound(
            utility.CreatePoint(double_array([x, y, 0.0])), "IMathPoint"
        )
        projected = _early_bound(point.MultiplyTransform(transform), "IMathPoint")
        points.append(tuple(float(value) for value in projected.ArrayData))
    manager = _early_bound(adapter.currentModel.SketchManager, "ISketchManager")
    create = {"circle": manager.CreateCircle, "line": manager.CreateLine}[kind]
    previous = bool(manager.AddToDB)
    manager.AddToDB = False
    try:
        segment = create(*points[0], *points[1])
    finally:
        manager.AddToDB = previous
    if segment is None:
        raise RuntimeError(f"failed to sketch the {label} {kind}")
    return segment


def _sketch_view_circle(
    adapter: Any,
    view: Any,
    centre: tuple[float, float],
    radius: float,
    *,
    label: str,
) -> None:
    """A circle (sheet metres) in ``view``'s own sketch, left selected."""
    _sketch_in_view(
        adapter,
        view,
        (centre, (centre[0] + radius, centre[1])),
        "circle",
        label=label,
    )


def _add_explode_trail(
    adapter: Any,
    view: Any,
    trail: tuple[tuple[float, ...], tuple[float, ...]],
    *,
    label: str,
) -> None:
    """A black phantom line on the exploded ``view`` between two exploded
    model points (machine mm), read back as styled."""
    ends = tuple(
        model_point_in_view(
            adapter, view, tuple(value / 1000.0 for value in point), label=label
        )
        for point in trail
    )
    segment = _early_bound(
        _sketch_in_view(adapter, view, ends, "line", label=label), "ISketchSegment"
    )
    segment.Style = TRAIL_LINE_STYLE
    segment.Color = BOUNDARY_COLOR
    adapter.currentModel.ClearSelection2(True)
    adapter.currentModel.EditRebuild3()
    style, color = int(segment.Style), int(segment.Color)
    if (style, color) != (TRAIL_LINE_STYLE, BOUNDARY_COLOR):
        raise RuntimeError(f"{label}: trail reads style {style}, colour {color}")
    _telemetry.info(f"{label}: {ends[0]!r} -> {ends[1]!r}")


def _mark_detail_boundary(adapter: Any, parent: Any, detail: Detail) -> None:
    """The detail's boundary on its parent view: a black circle round what
    the detail shows, lettered at its upper right (machinist review, farm run
    20261016T082735510Z: the fitter could not tell where A and B come from)."""
    label = f"{detail.label} boundary"
    centre = model_point_in_view(adapter, parent, detail.model_centre_m, label=label)
    radius = detail.radius_mm * SHEET_SCALE[0] / SHEET_SCALE[1] / 1000.0
    _sketch_view_circle(adapter, parent, centre, radius, label=label)
    # A view-sketch circle prints in the sketch's grey (farm run
    # 20261016T092607223Z); colour the still-selected circle as the outline.
    selection = _early_bound(adapter.currentModel.SelectionManager, "ISelectionMgr")
    if int(selection.GetSelectedObjectCount2(-1)) != 1:
        raise RuntimeError(f"{label}: the sketched circle is not the one selection")
    _early_bound(adapter.currentModel, "IDrawingDoc").SetLineColor(BOUNDARY_COLOR)
    adapter.currentModel.ClearSelection2(True)
    adapter.currentModel.EditRebuild3()
    reach = radius * math.sqrt(0.5) + DETAIL_LETTER_GAP
    _label_view(
        adapter,
        parent,
        notes.DETAIL_LETTERS[detail.key],
        (centre[0] + reach, centre[1] + reach),
        label=label,
    )


def _crop(adapter: Any, view: Any, detail: Detail) -> None:
    """Crop ``view`` to the circle round ``detail.centre``: sketch the circle
    in the active view's own sketch and Crop2 while it is still selected."""
    view = _early_bound(view, "IView")
    _sketch_view_circle(
        adapter, view, detail.centre, detail.crop_radius, label=f"{detail.label} crop"
    )
    status = int(view.Crop2(False, False, 1))
    adapter.currentModel.ClearSelection2(True)
    adapter.currentModel.EditRebuild3()
    view.UpdateViewDisplayGeometry()
    cropped = bool(view.IsCropped())
    if status != CROP_NO_ERROR or not cropped:
        raise RuntimeError(
            f"{detail.label} is not cropped: Crop2 status {status}, IsCropped {cropped}"
        )
    _assert_on_sheet(
        (
            detail.centre[0] - detail.crop_radius,
            detail.centre[1] - detail.crop_radius,
            detail.centre[0] + detail.crop_radius,
            detail.centre[1] + detail.crop_radius,
        ),
        label=f"{detail.label} crop circle",
    )


def _detail(adapter: Any, detail: Detail) -> list[Any]:
    """Place ``detail``, import its settings (if any) at their text points,
    crop it, prove the kept dimensions survived, and label it."""
    view = _placed_detail(adapter, detail)
    annotations: list[Any] = []
    if detail.feature is not None:
        _show_base_view_sketches(adapter, view, (detail.feature,), label=detail.label)
        keep = {
            name: model_point_in_view(
                adapter,
                view,
                tuple(value / 1000.0 for value in xyz),
                label=f"{detail.label} {name} text",
            )
            for name, xyz in DIMENSION_TEXT_POINTS[detail.key].items()
        }
        annotations = curate_view_dimensions(
            adapter,
            view,
            keep=keep,
            view_label=detail.label,
            dimensions_by_feature=spec.DRAWING_DIMENSIONS,
        )
    _crop(adapter, view, detail)
    if detail.feature is not None:
        kept = {
            dimension_name(adapter, _early_bound(annotation, "IAnnotation"))
            for annotation in (_early_bound(view, "IView").GetAnnotations() or ())
        }
        lost = sorted(set(DIMENSION_TEXT_POINTS[detail.key]) - kept)
        if lost:
            raise RuntimeError(
                f"{detail.label} lost {lost} to its crop; kept {sorted(kept)}"
            )
    _label_view(adapter, view, detail.title, detail.label_xy, label=detail.label)
    return annotations


def _assert_dimension_ink_on_sheet(display: Any, *, label: str) -> None:
    """A dimension's native line ink (witness, dimension line, arrows) stays
    on the drawable sheet."""
    display = _early_bound(display, "IDisplayDimension")
    data = _early_bound(display.GetDisplayData(), "IDisplayData")
    points = []
    for index in range(int(data.GetLineCount())):
        line = tuple(float(value) for value in data.GetLineAtIndex2(index))
        if len(line) < 10:
            raise RuntimeError(f"{label}: incomplete native dimension line")
        points.extend(((line[4], line[5]), (line[7], line[8])))
    if not points or int(data.GetTextCount()) < 1:
        raise RuntimeError(f"{label}: missing native dimension display data")
    _assert_on_sheet(
        (
            min(point[0] for point in points),
            min(point[1] for point in points),
            max(point[0] for point in points),
            max(point[1] for point in points),
        ),
        label=f"{label} dimension ink",
    )


def _band(name: str) -> tuple[float, float]:
    """``name``'s nominal and symmetric band in SolidWorks system units."""
    if name in spec.ANGULAR_TOLERANCES:
        return math.radians(spec.YAW_DEG), math.radians(spec.ANGULAR_TOLERANCES[name])
    return spec.DIMENSION_NOMINALS[name] / 1000.0, spec.DIMENSION_TOLERANCES[
        name
    ] / 1000.0


def _assert_settings(displays: list[tuple[str, Any]], *, when: str) -> None:
    """Each setting reads its nominal (the angle 45, not its supplement), its
    symmetric band and places, and its callout."""
    for name, display in displays:
        nominal, band = _band(name)
        dimension = _early_bound(display.GetDimension2(0), "IDimension")
        tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
        value = abs(float(dimension.SystemValue))
        callout = str(display.GetText(CALLOUT_TEXT_PART) or "").replace("\r\n", "\n")
        if (
            abs(value - nominal) > 1e-8
            or int(tolerance.Type) != 4  # swTolSYMMETRIC
            or abs(float(tolerance.GetMaxValue()) - band) > 1e-9
            or abs(float(tolerance.GetMinValue()) + band) > 1e-9
            or int(display.GetPrimaryTolPrecision2()) != spec.TOLERANCE_PRECISION[name]
            or callout != notes.DIMENSION_CALLOUTS[name]
        ):
            raise RuntimeError(
                f"{when} {name}: value {value!r} (nominal {nominal!r}), tolerance "
                f"type {int(tolerance.Type)} {float(tolerance.GetMinValue())!r}.."
                f"{float(tolerance.GetMaxValue())!r} (band {band!r}), tol places "
                f"{int(display.GetPrimaryTolPrecision2())}, callout {callout!r}"
            )


def _place_settings_sheet(adapter: Any) -> Callable[[], None]:
    """Front and right at 1:2, the three details, the as-shipped note; returns
    the check that re-reads every setting once the drawing has settled."""
    _activate_sheet(adapter, SHEET_NAMES[0])
    _placed_base_view(
        adapter, "*Front", FRONT_CENTER, notes.VIEW_TITLES["front"], label="pen front"
    )
    right = _placed_base_view(
        adapter, "*Right", RIGHT_CENTER, notes.VIEW_TITLES["right"], label="pen right"
    )
    annotations = [
        annotation for detail in DETAILS for annotation in _detail(adapter, detail)
    ]
    set_dimension_callouts(
        adapter, annotations, dict(notes.DIMENSION_CALLOUTS), location=CALLOUT_LOCATION
    )
    assert_imported_precision(
        adapter,
        annotations,
        {
            name: places
            for names in spec.DRAWING_PRECISION.values()
            for name, places in names.items()
        },
    )
    displays = [
        (
            dimension_name(adapter, annotation),
            _early_bound(
                _early_bound(annotation, "IAnnotation").GetSpecificAnnotation(),
                "IDisplayDimension",
            ),
        )
        for annotation in annotations
    ]
    if sorted(name for name, _ in displays) != sorted(notes.DIMENSION_CALLOUTS):
        raise RuntimeError(f"pen details imported {sorted(n for n, _ in displays)}")
    for name, display in displays:
        _assert_dimension_ink_on_sheet(display, label=f"pen {name}")
    _assert_settings(displays, when="placed")
    # A and B are bounded on RIGHT, where the stud and the hanger screw both
    # show (on FRONT the strap hides the stud); A is drawn from the front and
    # says so in its title, as the turned plan C does.
    for detail in DETAILS:
        if detail.key in BOUNDED_ON_RIGHT:
            _mark_detail_boundary(adapter, right, detail)
    _add_note_block(
        adapter,
        SHEET_NAMES[0],
        SETTINGS_NOTE,
        SETTINGS_NOTE_XY,
        label="as-shipped note",
    )
    return lambda: _assert_settings(displays, when="settled")


# --- sheet 2 ----------------------------------------------------------------------

_INSERT_COLUMN_AFTER = 3  # swTableItemInsertPosition_After
_INSERT_COLUMN_DEFAULT_WIDTH = 0  # swInsertColumn_DefaultWidth


def _bom_cells(table: Any) -> tuple[tuple[str, ...], ...]:
    """Every displayed BOM cell, header row first."""
    return tuple(
        tuple(
            str(table.DisplayedText(row, column) or "").strip()
            for column in range(int(table.ColumnCount))
        )
        for row in range(int(table.RowCount))
    )


def _bom_column(
    header: tuple[str, ...], predicate: Callable[[str], bool], label: str
) -> int:
    matches = [index for index, cell in enumerate(header) if predicate(cell.upper())]
    if len(matches) != 1:
        raise RuntimeError(f"pen BOM has no unique {label} column: {header!r}")
    return matches[0]


def _validate_bom(adapter: Any, table: Any) -> tuple[tuple[str, str], ...]:
    """Rewrite part numbers, prove identities/descriptions/quantities and the
    item numbers the steps cite, add the registry's VENDOR SKU column after
    DESCRIPTION; return (stem, item number) in BOM order. Material and finish
    remain on component drawings."""
    table = _early_bound(table, "ITableAnnotation")
    contents = _bom_cells(table)
    rows = len(contents)
    columns = len(contents[0]) if contents else 0
    if rows != len(BOM_COMPONENTS) + 1 or columns < 4:
        raise RuntimeError(
            f"pen BOM is {rows}x{columns}; expected {len(BOM_COMPONENTS) + 1} rows "
            "and at least four columns"
        )
    header = contents[0]
    for title in ("MATERIAL", BOM_SKU_TITLE):
        if title in (cell.upper() for cell in header):
            raise RuntimeError(f"pen BOM template already has {title!r}")
    item_column = _bom_column(
        header, lambda cell: cell.startswith("ITEM NO"), "ITEM NO."
    )
    part_column = _bom_column(header, lambda cell: cell == "PART NUMBER", "PART NUMBER")
    description_column = _bom_column(
        header, lambda cell: cell == "DESCRIPTION", "DESCRIPTION"
    )
    quantity_column = _bom_column(header, lambda cell: cell.startswith("QTY"), "QTY.")

    actual: dict[str, tuple[int, str, str, str]] = {}
    for row_index, row in enumerate(contents[1:], start=1):
        text = row[part_column].casefold()
        stem = BOM_NORMALIZED_ALIASES.get(text, text)
        if stem in actual:
            raise RuntimeError(f"pen BOM repeats component family {stem!r}")
        actual[stem] = (
            row_index,
            row[item_column],
            row[description_column],
            row[quantity_column],
        )
    if set(actual) != set(BOM_COMPONENTS):
        raise RuntimeError(
            f"pen BOM identities {sorted(actual)!r} != {sorted(BOM_COMPONENTS)!r}"
        )
    # The sequence and checks cite these item numbers (spec.ITEM).
    numbering = {stem: values[1] for stem, values in actual.items()}
    expected_numbering = {stem: str(spec.ITEM[stem]) for stem in BOM_COMPONENTS}
    if numbering != expected_numbering:
        raise RuntimeError(
            f"pen BOM item numbers {numbering!r} != {expected_numbering!r}"
        )
    for stem, (row_index, _item, description, quantity) in actual.items():
        number = BOM_PART_NUMBERS[stem]
        if contents[row_index][part_column] != number:
            if not table.IsCellTextEditable(row_index, part_column):
                raise RuntimeError(f"pen BOM part-number cell for {stem!r} is locked")
            table.SetText2(row_index, part_column, False, number)
        if description != BOM_DESCRIPTIONS[stem]:
            raise RuntimeError(
                f"pen BOM description mismatch for {stem!r}: {description!r}"
            )
        if quantity != str(BOM_QUANTITIES[stem]):
            raise RuntimeError(
                f"pen BOM quantity for {stem!r} is {quantity!r}, "
                f"expected {BOM_QUANTITIES[stem]}"
            )

    # The parts carry no SKU property; made parts print MADE_PART_SKU.
    if not table.InsertColumn2(
        _INSERT_COLUMN_AFTER,
        description_column,
        BOM_SKU_TITLE,
        _INSERT_COLUMN_DEFAULT_WIDTH,
    ):
        raise RuntimeError("pen BOM refused the VENDOR SKU column")
    column = description_column + 1
    if not table.SetColumnTitle2(column, BOM_SKU_TITLE, False):
        raise RuntimeError("pen BOM VENDOR SKU column title did not set")
    for stem, (row_index, *_rest) in actual.items():
        if not table.IsCellTextEditable(row_index, column):
            raise RuntimeError(f"pen BOM VENDOR SKU cell for {stem!r} is locked")
        table.SetText2(row_index, column, False, BOM_SKUS[stem])

    header = _bom_cells(table)[0]
    widths = {
        "item": _bom_column(
            header, lambda cell: cell.startswith("ITEM NO"), "ITEM NO."
        ),
        "part": _bom_column(header, lambda cell: cell == "PART NUMBER", "PART NUMBER"),
        "description": _bom_column(
            header, lambda cell: cell == "DESCRIPTION", "DESCRIPTION"
        ),
        "sku": _bom_column(header, lambda cell: cell == BOM_SKU_TITLE, BOM_SKU_TITLE),
        "quantity": _bom_column(header, lambda cell: cell.startswith("QTY"), "QTY."),
    }
    if len(header) != len(BOM_COLUMN_WIDTHS) or set(widths) != set(BOM_COLUMN_WIDTHS):
        raise RuntimeError(f"pen BOM columns {header!r} are not the contract")
    for key, index in widths.items():
        width = BOM_COLUMN_WIDTHS[key]
        if abs(float(table.SetColumnWidth(index, width, 0)) - width) > 1e-6:
            raise RuntimeError(f"pen BOM {key} column width did not persist")
    for row in range(rows):
        table.SetRowHeight(row, BOM_ROW_HEIGHT, 0)
    if not adapter.currentModel.EditRebuild3():
        raise RuntimeError("pen BOM rebuild failed")
    settled = _bom_cells(table)
    for stem, (row_index, *_rest) in actual.items():
        for key, text in (("part", BOM_PART_NUMBERS[stem]), ("sku", BOM_SKUS[stem])):
            applied = settled[row_index][widths[key]]
            if applied != text:
                raise RuntimeError(
                    f"pen BOM {key} for {stem!r} reads {applied!r}, expected {text!r}"
                )
    return tuple((stem, actual[stem][1]) for stem in BOM_COMPONENTS)


def _fit_exploded(adapter: Any, view: Any, *, label: str) -> tuple[float, float]:
    """The largest ``EXPLODED_SCALES`` entry whose outline plus balloon ring
    fits left of the BOM; each candidate is applied, centred and re-read."""
    findings = []
    current = EXPLODED_SCALES[0]
    for scale in EXPLODED_SCALES:
        if scale != current:
            _set_view_scale(adapter, view, scale, label=label)
            current = scale
        _center_view_outline(adapter, view, EXPLODED_ISO_CENTER, label=label)
        ring = _grown(_view_outline(view, label=label), BALLOON_MARGIN)
        overflow = _sheet_findings(ring, right_limit=EXPLODED_RIGHT_LIMIT)
        if not overflow:
            _telemetry.info(f"{label}: ring {ring!r} fits at {_scale_text(scale)}")
            return scale
        findings.append(f"{_scale_text(scale)}: ring {ring!r} " + "; ".join(overflow))
    raise RuntimeError(f"{label}: no scale fits: " + " | ".join(findings))


def _make_explode_readable(
    view: Any, configuration: str, *, label: str
) -> Callable[[], None]:
    """Leave the exploded view's ``configuration`` readable by the balloon
    walker; return the call that restores the source's active configuration.

    ``_drawing_balloons._view_explode_offsets`` reads a NON-active
    configuration's steps directly, and makes an ACTIVE one readable by showing
    its explode on the model. Placed from the octant named view, the source's
    non-active Default Simplified read zero steps (farm run
    20261016T075516581Z), so when it does, Default Simplified is made the
    source's active configuration for the walk and Default shown again after.
    The source must come back as clean as it went in: the drawing save would
    otherwise write the released assembly.
    """
    bound = _early_bound(view, "IView")
    source = _early_bound(bound.ReferencedDocument, "IModelDoc2")
    manager = _early_bound(source.ConfigurationManager, "IConfigurationManager")

    def active_name() -> str:
        return str(_early_bound(manager.ActiveConfiguration, "IConfiguration").Name)

    active = active_name()
    owner = source.GetConfigurationByName(configuration)
    if owner is None:
        raise RuntimeError(f"{label}: source has no {configuration!r}")
    steps = int(_early_bound(owner, "IConfiguration").GetNumberOfExplodeSteps())
    _telemetry.event(
        "pen.explode_read", configuration=configuration, active=active, steps=steps
    )
    if steps or active == configuration:
        return lambda: None
    was_dirty = bool(source.GetSaveFlag())
    if not bool(source.ShowConfiguration2(configuration)) or (
        active_name() != configuration
    ):
        raise RuntimeError(
            f"{label}: cannot make {configuration!r} the source's active"
        )

    def restore() -> None:
        if not bool(source.ShowConfiguration2(active)) or active_name() != active:
            raise RuntimeError(f"{label}: cannot show the source's {active!r} again")
        if not bool(bound.IsExploded()):
            raise RuntimeError(f"{label}: restoring {active!r} collapsed the view")
        if bool(source.GetSaveFlag()) and not was_dirty:
            raise RuntimeError(
                f"{label}: switching the source's configuration dirtied it"
            )

    return restore


def _place_exploded_sheet(adapter: Any) -> Callable[[], None]:
    """The exploded isometric, its BOM (with vendor SKU) and one balloon per
    row; returns the check that proves every balloon after the last rebuild."""
    label = "pen exploded"
    _activate_sheet(adapter, SHEET_NAMES[1])
    exploded = place_view(
        adapter,
        str(SOURCE),
        EXPLODED_ORIENTATION,
        *EXPLODED_ISO_CENTER,
        scale=SHEET_SCALE,
    )
    set_high_quality_shaded_with_edges(adapter, exploded, label=label)
    # Configuration, then its own explode, then the BOM and balloons bind.
    configuration = apply_view_configuration(adapter, exploded, label=label)
    set_view_exploded_state(
        adapter, exploded, True, configuration=configuration, label=label
    )
    scale = _fit_exploded(adapter, exploded, label=label)
    table = insert_bom_table(
        adapter,
        exploded,
        anchor_xy=BOM_ANCHOR,
        expected_components=BOM_COMPONENTS,
        descriptions=BOM_DESCRIPTIONS,
        identity_aliases=BOM_IDENTITY_ALIASES,
        configuration_grouping="same-part",
        label="pen",
    )
    items = _validate_bom(adapter, table)
    restore = _make_explode_readable(exploded, configuration, label=label)
    try:
        landings = add_component_bom_balloons(
            adapter,
            exploded,
            items=items,
            anchors=BALLOON_ANCHORS,
            label="pen exploded-view BOM coverage",
            margin=BALLOON_MARGIN,
        )
    finally:
        primary_error = sys.exception()
        try:
            restore()
        except Exception as cleanup_error:
            if primary_error is None:
                raise
            _telemetry.warn(f"{label}: after balloon failure: {cleanup_error}")
    if len(landings) != sum(BOM_QUANTITIES.values()):
        raise RuntimeError(
            f"pen exploded view carries {len(landings)} balloons, expected one per "
            f"component ({sum(BOM_QUANTITIES.values())})"
        )
    _add_explode_trail(
        adapter,
        exploded,
        notes.ROD_SET_SCREW_TRAIL,
        label="pen rod set screw explode trail",
    )
    _add_note_block(
        adapter,
        SHEET_NAMES[1],
        f"{notes.EXPLODED_CAPTION}\nSCALE {_scale_text(scale)}",
        EXPLODED_CAPTION_XY,
        label="exploded-view caption",
    )
    return lambda: assert_balloon_landings(adapter, landings)


# --- sheet 3 ----------------------------------------------------------------------


def _place_steps_sheet(adapter: Any) -> None:
    """The finished assembly in full detail beside the sequence and checks."""
    label = "pen finished"
    _activate_sheet(adapter, SHEET_NAMES[2])
    finished = place_view(
        adapter, str(SOURCE), "*Isometric", *ASSEMBLY_ISO_CENTER, scale=SHEET_SCALE
    )
    set_high_quality_shaded_with_edges(adapter, finished, label=label)
    configuration = apply_view_configuration(
        adapter, finished, role=ViewRole.FULL_DETAIL, label=label
    )
    set_view_exploded_state(
        adapter, finished, False, configuration=configuration, label=label
    )
    _center_view_outline(adapter, finished, ASSEMBLY_ISO_CENTER, label=label)
    x0, y0, x1, y1 = _view_outline(finished, label=label)
    _assert_on_sheet((x0, y0, x1, y1), label=label)
    assert_full_detail_view(adapter, label="pen assembly")
    _label_view(
        adapter,
        finished,
        notes.VIEW_TITLES["finished"],
        (x0, y0 - VIEW_LABEL_GAP),
        label=label,
    )
    steps_x = x1 + NOTE_GAP
    steps = _add_note_block(
        adapter,
        SHEET_NAMES[2],
        ASSEMBLY_STEPS,
        (steps_x, STEPS_TOP),
        label="assembly sequence",
    )
    _add_note_block(
        adapter,
        SHEET_NAMES[2],
        ASSEMBLY_CHECKS,
        (steps_x, steps[1] - NOTE_GAP),
        label="assembly checks",
    )


# --- package ----------------------------------------------------------------------


def _place_package(adapter: Any) -> Callable[[], None]:
    new_project_drawing(adapter, layout=SPEC.layout, scale=SHEET_SCALE)
    create_blank_drawing_sheets(adapter, SHEET_NAMES, label="pen package")
    for sheet_name in SHEET_NAMES:
        sheet = _activate_sheet(adapter, sheet_name)
        scale = SHEET_SCALES[sheet_name]
        if not sheet.SetScale(float(scale[0]), float(scale[1]), False, False):
            raise RuntimeError(f"failed to set pen sheet scale: {sheet_name}")
    settings_settled = _place_settings_sheet(adapter)
    exploded_settled = _place_exploded_sheet(adapter)
    _place_steps_sheet(adapter)

    def settled() -> None:
        settings_settled()
        exploded_settled()

    return settled


@_telemetry.traced("drawing.pn_pen_assembly")
async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source assembly is missing: {SOURCE}")
    check("open pen drawing source", await adapter.open_model(str(SOURCE)))
    source_model = _early_bound(adapter.currentModel, "IModelDoc2")
    properties = read_required_properties(
        source_model,
        ("Number", "Revision", "Title", "Material Specification", "Finish", "Quantity"),
        required=("Number", "Revision", "Material Specification", "Finish", "Quantity"),
    )
    if properties["Number"] != spec.DRAWING_NUMBER:
        raise RuntimeError(
            f"pen source Number {properties['Number']!r} != {spec.DRAWING_NUMBER!r}"
        )
    _validate_source(source_model)

    settled = _place_package(adapter)
    return await finalize_drawing(
        adapter,
        OUTPUTS,
        layout=SPEC.layout,
        pdf_title=PDF_TITLE,
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
