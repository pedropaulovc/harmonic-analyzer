r"""Create the three-sheet summing-lever fitter package (MHA-SM-00).

Sheet 1 shows the assembled lever on its knife mounts (front and right) with
the counter-spring screw height the level setting finds, a 1:1 knife-edge
detail showing the knife contact and the boss the free rock is read at, the
setting table (the settings and acceptances no visible model dimension
carries) and the notes. Sheet 2 is the builder-owned SM_EXPLODED isometric
with its BOM (vendor SKU added) and one balloon per BOM row. Sheet 3 is the
finished isometric at 1:4. The numbered fit-up steps and checks print in the
release's ASSEMBLY.md (#2889). The setting is the assembly's own sketch
dimension (``build_sm_summing_assembly._author_settings``), imported here; the explode
comes from ``sm_summing_explode_spec`` and every printed text comes from
``sm_summing_assembly_sheet``.

Usage:
    uv run python cad\scripts\draw_sm_summing_assembly.py sm-summing-assembly
"""

from __future__ import annotations

import argparse
import math
import re
import sys
import textwrap
from pathlib import Path
from typing import Any, Callable

from solidworks_mcp.adapters.com_variant import double_array, null_callout
from solidworks_mcp.adapters.solidworks.drawing import (
    add_note,
    place_view,
    view_name,
)

import _config
import _telemetry
import sm_summing_assembly_sheet as notes
import sm_summing_assembly_spec as spec
import sm_summing_explode_spec as explode
from _check import check
from _com import _early_bound
from _component_order import by_name
from _drawing_balloons import (
    BalloonAnchor,
    add_component_bom_balloons,
    assert_balloon_landings,
)
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    rebuild_drawing,
    set_high_quality_shaded_with_edges,
)
from _drawing_dimension_import import curate_view_dimensions
from _drawing_dimensions import (
    assert_imported_precision,
    offset_dimension_text,
    set_dimension_callouts,
    set_reference_dimension,
)
from _drawing_hidden_sketches import _show_base_view_sketches
from _drawing_projection import model_point_in_view
from _general_table import insert_general_table
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_types import DRAWING_TEMPLATES, DrawingLayout
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
from _machinist_review_mode import MachinistReviewMode
from _session import run_build
from _simplified_names import simplified_name
from stock_anchor_geom import ANCHOR_9490T1


# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE
SPEC = DRAWINGS_BY_NAME["sm_summing_assembly"]
ARTIFACT_STEM = SPEC.artifact_stem
SOURCE = SPEC.source
OUTPUTS = DrawingOutputs(
    SPEC.outputs["slddrw"],
    SPEC.outputs["pdf"],
    SPEC.outputs["png"],
)
SLDDRW = OUTPUTS.slddrw
PDF = OUTPUTS.pdf
PNG = OUTPUTS.png
PDF_TITLE = "Summing Lever Assembly Drawing Package"

SHEET_NAMES = (
    "ASSEMBLED + SETTINGS",
    "EXPLODED VIEW + BOM",
    "FINISHED ASSEMBLY",
)
if SPEC.layout is not DrawingLayout.LANDSCAPE:
    raise AssertionError("the summing package is landscape throughout")
SHEET_LAYOUTS = {name: DrawingLayout.LANDSCAPE for name in SHEET_NAMES}
ASSEMBLED_SCALE = (1.0, 5.0)
EXPLODED_SCALE = (1.0, 4.0)
# The finished isometric is centred over the usable field above the title
# block at the largest standard scale whose native outline fits it with
# FINISHED_CLEARANCE all round (machinist review of farm runs
# 20261117T143446475Z-fdea6028 and 20261117T150253462Z-123d40fd: at 1:5 it
# sat small in an empty sheet; at 1:3 left of the title block it was bunched
# against one edge). Its native outline, 113.7 x 206.2 mm at 1:3 (run
# 20261117T150253462Z-123d40fd's layout report), overfills the 200.7 mm
# field at 1:3; at 1:4 it is 85.3 x 154.7.
FINISHED_SCALE = (1.0, 4.0)
FINISHED_CLEARANCE = 0.010
SHEET_SCALES = dict(zip(SHEET_NAMES, (ASSEMBLED_SCALE, EXPLODED_SCALE, FINISHED_SCALE)))

# Sheet geometry, metres: the template's inner border and the title block in
# its lower-right corner.
_TEMPLATE = DRAWING_TEMPLATES[DrawingLayout.LANDSCAPE]
_BORDER = 0.0127
SHEET_INNER_BORDER = (
    _BORDER,
    _BORDER,
    _TEMPLATE.width_m - _BORDER,
    _TEMPLATE.height_m - _BORDER,
)
TITLE_BLOCK = (
    _TEMPLATE.title_block_left_m,
    0.0,
    _TEMPLATE.width_m,
    _TEMPLATE.title_block_top_m,
)

# --- Sheet 1 ------------------------------------------------------------------
# Front and right at 1:5 across the upper left, the 1:1 knife-edge detail to
# their right, the notes under the front view.
FRONT_CENTER = (0.068, 0.168)
RIGHT_CENTER = (0.185, 0.168)
# The screw height's dimension line stands this far outboard of the knife
# contact, on the side away from the gooseneck.
COUNTER_TEXT_OFFSET = 0.030
# DETAIL A's dowel proud (owner decision 2026-11-19, #3124 item 3).  Its
# dimension line stands DOWEL_PROUD_LINE_OFFSET right of the front mount's
# dowel axis, 2.9 mm clear of the mount's +X face (5.08 right of the axis).
# Its 7.1 mm span cannot hold the value and its three callout rows, which
# printed across both extension lines and the dimension line in farm run
# 20261119T202848942Z (machinist review, rule 14), so the text parks on a
# leader right of the line (offset_dimension_text, draw_fr_top_frame's
# HANGER_PIN_DEPTH_OFFSET_XY form): rows centred on the offset x, the value
# 2.78 mm over the offset y and the rows 5.56 mm apart under it; the widest
# row ("CROSSBAR UNDERSIDE", ~45 mm) starts 3 mm right of the line.
DOWEL_PROUD_LINE_OFFSET = 0.008
DOWEL_PROUD_TEXT_DX = 0.0255
DOWEL_PROUD_TEXT_DY = 0.006
# The proud's free end sits inside the mount's round hole, so a plain view
# can only draw it hidden (machinist review of the same run, rule 9: never
# dimension to a hidden line).  A broken-out window over the dowel's proud
# length, inside the mount's +X face and below its top seat, cuts the front
# mount to its mid-plane, the dowel's axis, so the free end prints as a
# visible edge.  The window's depth is measured from the view's nearest
# face, the lever's front trunnion end (HEX_DEPTH / 2 in front of the
# mount's mid-plane; nothing else in the assembly stands further +Z).
DOWEL_PROUD_WINDOW_HALF_WIDTH_MM = 3.0
DOWEL_PROUD_WINDOW_TOP_INSET_MM = 1.2
DOWEL_PROUD_WINDOW_BOTTOM_OVERRUN_MM = 1.5
DOWEL_PROUD_BREAK_OUT_DEPTH_MM = spec.lever.HEX_Z_OUTER_PLUS - spec.lever.KNIFE_SEAT_Z_PLUS
SEL_EDGES = 1  # swSelectType_e.swSelEDGES
NOTES_XY = (0.018, 0.098)
NOTES_WIDTH = 64  # characters; default-format note text

DETAIL_SCALE = (1, 1)
DETAIL_CENTRE = (0.305, 0.172)
# The detail frames the knife contact, the mount, the boss and the eye of the
# boss hook: model centre between knife and boss axis, just above the knife.
DETAIL_MODEL_CENTRE_MM = (
    (spec.KNIFE_POINT[0] + spec.COUNTER_SCREW_POINT[0]) / 2.0,
    spec.BOSS_FACE_POINT[1] + 5.0,
)
DETAIL_RADIUS_MM = 52.0
DETAIL_MM = DETAIL_SCALE[0] / DETAIL_SCALE[1] / 1000.0  # sheet metres per model mm
DETAIL_CROP_RADIUS = DETAIL_RADIUS_MM * DETAIL_MM
DETAIL_LABEL_GAP = 0.005
DETAIL_LABEL_INSET = 0.040
CROP_NO_ERROR = 1  # swCropViewErrors_e.swCropViewErrors_NoError
DETAIL_POSITION_TOL_M = 1e-4
# DETAIL A's boundary on the 1:5 front view: black like the outlines, its
# letter centred under the circle in the open sheet below the lever, so no
# line (the circle, the knife-mount bolt) strikes it (farm r1: lettered at
# the upper right, the circle and the bolt ran through it). A note's
# position is its text's upper-left corner.
DETAIL_BOUNDARY_COLOR = 0  # COLORREF black
DETAIL_LETTER_GAP = 0.002
DETAIL_LETTER_HALF_WIDTH = 0.0013
# The setting table (rule 22: settings and acceptances no visible model
# dimension carries) runs along the top border, above every view on the sheet.
SETTING_TABLE_INSET = 0.004
SETTING_TABLE_VIEW_GAP = 0.004

# --- Sheet 2 ------------------------------------------------------------------
EXPLODED_ISO_CENTER = (0.112, 0.150)
BALLOON_MARGIN = 0.012
BOM_COLUMN_WIDTHS = {
    "item": 0.012,
    "part": 0.030,
    "description": 0.070,
    "sku": 0.028,
    "quantity": 0.012,
}
BOM_SKU_TITLE = "VENDOR SKU"
MADE_PART_SKU = "-"
BOM_ROW_HEIGHT = 0.006
BOM_ANCHOR = (0.226, 0.258)
# Wrapped full vendor Numbers determine the native table height, not its
# nominal row pitch. Target 6 mm below its rebuilt bottom; prove 4 mm of air
# with the caption's actual extent, including after the final rebuild.
EXPLODED_CAPTION_OFFSET = 0.006
EXPLODED_CAPTION_MIN_GAP = 0.004

# --- Sheet 3 ------------------------------------------------------------------
# The finished isometric, centred over the field above the title block; the
# fit-up steps and checks print in the release's ASSEMBLY.md (#2889).
FINISHED_FIELD = (
    SHEET_INNER_BORDER[0],
    TITLE_BLOCK[3],
    SHEET_INNER_BORDER[2],
    SHEET_INNER_BORDER[3],
)
ASSEMBLY_ISO_CENTER = (
    (FINISHED_FIELD[0] + FINISHED_FIELD[2]) / 2.0,
    (FINISHED_FIELD[1] + FINISHED_FIELD[3]) / 2.0,
)

BOM_QUANTITIES = {stem: spec.QUANTITIES[stem] for stem in notes.BOM_ORDER}
BOM_COMPONENTS = tuple(BOM_QUANTITIES)
# Literal stems, so the config-dependency analysis reads exactly these rows.
PART_ROWS = {
    "sm-knife-mount": _config.parts("sm-knife-mount"),
    "sm-vn-knife-hanger-washer": _config.parts("sm-vn-knife-hanger-washer"),
    "sm-vn-knife-hanger-stud": _config.parts("sm-vn-knife-hanger-stud"),
    "sm-vn-knife-mount-dowel": _config.parts("sm-vn-knife-mount-dowel"),
    "sm-summing-lever": _config.parts("sm-summing-lever"),
    "sm-vn-boss-hook": _config.parts("sm-vn-boss-hook"),
    "sm-vn-counter-spring": _config.parts("sm-vn-counter-spring"),
    "sm-gooseneck": _config.parts("sm-gooseneck"),
    "sm-gooseneck-end-plug": _config.parts("sm-gooseneck-end-plug"),
    "sm-vn-gooseneck-shoulder-screw": _config.parts("sm-vn-gooseneck-shoulder-screw"),
}
if set(PART_ROWS) != set(BOM_COMPONENTS):
    raise AssertionError("BOM registry rows must cover exactly the assembly families")
BOM_PART_NUMBERS = {stem: str(row["number"]) for stem, row in PART_ROWS.items()}
# The registry owns part numbers and vendor SKUs; made parts print "-".
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
# One balloon per BOM row, each on its own family's visible edge: every family
# is separated from its neighbours in the explode. The eyebolt's walked
# anchor was its shank's cut end, beside the since-retired jam nut's leader
# (machinist review on main and #1945); it is pinned to the open eye
# instead: the eye tip's dome-root circle, on its +Z side, which faces the
# +X+Y+Z isometric viewer (the eyebolt is placed unrotated, so part and
# machine axes agree).
EYEBOLT_BALLOON_POINT_MM = (
    ANCHOR_9490T1.eye_open_tip_mm[0],
    ANCHOR_9490T1.eye_open_tip_mm[1],
    ANCHOR_9490T1.wire_radius_mm,
)
BALLOON_ANCHORS = {stem: BalloonAnchor() for stem in BOM_COMPONENTS} | {
    spec.BOSS_HOOK: BalloonAnchor(point_mm=EYEBOLT_BALLOON_POINT_MM),
}

EXPLODED_VIEW_NAMES = {
    ASSEMBLY_VIEW_CONFIGURATION: explode.EXPLODED_VIEW_NAME,
    SIMPLIFIED_VIEW_CONFIGURATION: simplified_name(explode.EXPLODED_VIEW_NAME),
}
if explode.SOURCE_CONFIGURATION != ASSEMBLY_VIEW_CONFIGURATION:
    raise AssertionError("the summing explode is authored in Default")

# Callouts print below the value (above-callout line breaks do not print).
CALLOUT_LOCATION = "below"
CALLOUT_TEXT_PART = 4  # swDimensionTextCalloutBelow
PRECISION = {
    name: places
    for names in spec.DRAWING_PRECISION.values()
    for name, places in names.items()
}


_STEP_LABEL = re.compile(r"(\d+)[A-HJ-NP-Z]?")


def _step_group(line: str) -> str | None:
    """The step number a numbered line belongs to ("1" for "1" and "1A"), or
    None for a heading or a plain line."""
    number, sep, _rest = line.partition(". ")
    match = _STEP_LABEL.fullmatch(number) if sep else None
    return match.group(1) if match else None


def _wrapped(lines: tuple[str, ...], *, width: int) -> str:
    """Wrap each numbered line under its own number or lettered sub-step
    label; one note per block."""
    out: list[str] = []
    for line in lines:
        number, _sep, rest = line.partition(". ")
        if _step_group(line) is not None:
            out += textwrap.wrap(
                rest,
                width=width,
                initial_indent=f"{number}. ",
                subsequent_indent=" " * (len(number) + 2),
                break_long_words=False,
                break_on_hyphens=False,
            )
        else:
            out += textwrap.wrap(
                line,
                width=width,
                subsequent_indent="   ",
                break_long_words=False,
                break_on_hyphens=False,
            )
    return "\n".join(out)


ASSEMBLED_NOTES = _wrapped(notes.ASSEMBLED_NOTES, width=NOTES_WIDTH)
# The detail's scale differs from the sheet's 1:5, so its label prints it.
DETAIL_LABEL = f"{notes.DETAIL_TITLE}\nSCALE {DETAIL_SCALE[0]} : {DETAIL_SCALE[1]}"


def _activate_sheet(adapter: Any, name: str) -> Any:
    ddoc = _early_bound(adapter.currentModel, "IDrawingDoc")
    if not ddoc.ActivateSheet(name):
        raise RuntimeError(f"failed to activate drawing sheet {name!r}")
    current = _early_bound(ddoc.GetCurrentSheet(), "ISheet")
    actual = str(current.GetName() or "")
    if actual != name:
        raise RuntimeError(f"active drawing sheet is {actual!r}, expected {name!r}")
    return current


def _add_note_block(
    adapter: Any, sheet_name: str, text: str, xy: tuple[float, float], *, label: str
) -> Any:
    """A sheet-owned note: activate the sheet so no view owns it."""
    _activate_sheet(adapter, sheet_name)
    note = add_note(adapter, text, *xy)
    if note is None:
        raise RuntimeError(f"failed to place the summing {label}")
    note = _early_bound(note, "INote")
    printed = str(note.GetText() or "").replace("\r\n", "\n").replace("\r", "\n")
    if printed != text:
        raise RuntimeError(f"summing {label} printed as {printed!r}")
    return note


def _view_outline(view: Any, *, label: str) -> tuple[float, float, float, float]:
    outline = tuple(float(value) for value in _early_bound(view, "IView").GetOutline())
    if len(outline) != 4 or outline[2] <= outline[0] or outline[3] <= outline[1]:
        raise RuntimeError(f"{label}: invalid view outline {outline!r}")
    return outline[0], outline[1], outline[2], outline[3]


def _assert_box_on_sheet(box: tuple[float, float, float, float], *, label: str) -> None:
    """``box`` stays inside the inner border and clear of the title block."""
    x0, y0, x1, y1 = box
    left, bottom, right, top = SHEET_INNER_BORDER
    findings = []
    if x0 < left or y0 < bottom or x1 > right or y1 > top:
        findings.append(f"leaves the inner border {SHEET_INNER_BORDER}")
    tx0, ty0, tx1, ty1 = TITLE_BLOCK
    if x1 > tx0 and x0 < tx1 and y0 < ty1 and y1 > ty0:
        findings.append(f"enters the title block {TITLE_BLOCK}")
    if findings:
        raise RuntimeError(f"{label}: outline {box!r} " + "; ".join(findings))


def _assert_view_on_sheet(view: Any, *, margin: float = 0.0, label: str) -> None:
    """The view's outline, grown by ``margin`` (a balloon ring), stays on the
    sheet and clear of the title block."""
    x0, y0, x1, y1 = _view_outline(view, label=label)
    _assert_box_on_sheet(
        (x0 - margin, y0 - margin, x1 + margin, y1 + margin), label=label
    )


def _center_view_outline(
    adapter: Any, view: Any, center: tuple[float, float], *, label: str
) -> None:
    """Translate the actual view outline so it centres on ``center``."""
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
    x0, y0, x1, y1 = _view_outline(view, label=label)
    if (
        abs((x0 + x1) / 2.0 - center[0]) > 1e-6
        or abs((y0 + y1) / 2.0 - center[1]) > 1e-6
    ):
        raise RuntimeError(f"{label}: measured outline did not centre at {center!r}")


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
        raise RuntimeError("summing source must open in its Default configuration")
    for owner, wanted in EXPLODED_VIEW_NAMES.items():
        names = tuple(assembly.GetExplodedViewNames2(owner) or ())
        if names != (wanted,):
            raise RuntimeError(
                f"summing {owner} exploded views {names!r} != {(wanted,)!r}"
            )
    counts: dict[str, int] = {}
    for name, component in by_name(assembly.GetComponents(True)):
        stem = _component_stem(component)
        counts[stem] = counts.get(stem, 0) + 1
        total = _early_bound(component.GetTotalTransform(True), "IMathTransform")
        base = _early_bound(component.GetTotalTransform(False), "IMathTransform")
        if any(
            abs(float(actual) - float(expected)) > 1e-9
            for actual, expected in zip(total.ArrayData, base.ArrayData, strict=True)
        ):
            raise RuntimeError(
                f"summing source must open collapsed: {name!r} is displaced"
            )
    if counts != BOM_QUANTITIES:
        raise RuntimeError(
            f"summing families {counts!r} != contract {BOM_QUANTITIES!r}"
        )


# --- Settings -------------------------------------------------------------------


def _assert_callout(display: Any, name: str) -> None:
    text = str(display.GetText(CALLOUT_TEXT_PART) or "").replace("\r\n", "\n")
    if text != notes.DIMENSION_CALLOUTS[name]:
        raise RuntimeError(
            f"{name}: callout reads {text!r}, not {notes.DIMENSION_CALLOUTS[name]!r}"
        )


def _imported_setting(
    adapter: Any,
    view: Any,
    *,
    feature: str,
    dimension: str,
    text_xy: tuple[float, float],
    label: str,
) -> Any:
    """Show ``feature`` in ``view``, import its one marked dimension at
    ``text_xy``, stamp its callout and prove value and precision."""
    _show_base_view_sketches(adapter, view, (feature,), label=label)
    annotations = curate_view_dimensions(
        adapter,
        view,
        keep={dimension: text_xy},
        view_label=label,
        dimensions_by_feature={feature: notes.DRAWING_DIMENSIONS[feature]},
    )
    if len(annotations) != 1:
        raise RuntimeError(f"{label} must import exactly one dimension")
    set_dimension_callouts(
        adapter,
        annotations,
        {dimension: notes.DIMENSION_CALLOUTS[dimension]},
        location=CALLOUT_LOCATION,
    )
    assert_imported_precision(adapter, annotations, {dimension: PRECISION[dimension]})
    return _early_bound(annotations[0], "IAnnotation")


def _dimension_value_mm(display: Any) -> float:
    dimension = _early_bound(display.GetDimension2(0), "IDimension")
    return abs(float(dimension.SystemValue) * 1000.0)


def _counter_setting(adapter: Any, front: Any) -> Callable[[], None]:
    """The screw axis height over the knife contact level, a reference
    dimension on the front view."""
    label = "counter screw height"
    knife, screw = (
        model_point_in_view(
            adapter, front, (x / 1000.0, y / 1000.0, 0.0), label=f"{label} {name}"
        )
        for name, (x, y) in (
            ("knife", spec.KNIFE_POINT),
            ("screw", spec.COUNTER_SCREW_POINT),
        )
    )
    outboard = math.copysign(1.0, knife[0] - screw[0])
    text_xy = (knife[0] + outboard * COUNTER_TEXT_OFFSET, (knife[1] + screw[1]) / 2.0)
    annotation = _imported_setting(
        adapter,
        front,
        feature=spec.COUNTER_FEATURE,
        dimension=spec.COUNTER_DIMENSION,
        text_xy=text_xy,
        label=label,
    )
    display = _early_bound(
        set_reference_dimension(adapter, annotation, label=label), "IDisplayDimension"
    )
    if abs(_dimension_value_mm(display) - spec.COUNTER_SCREW_RISE) > 1e-4:
        raise RuntimeError(f"{label} reads {_dimension_value_mm(display):g} mm")
    _assert_callout(display, spec.COUNTER_DIMENSION)

    def settled() -> None:
        if (str(display.GetText(1) or ""), str(display.GetText(2) or "")) != ("(", ")"):
            raise RuntimeError(f"{label} is no longer a reference dimension")
        if abs(_dimension_value_mm(display) - spec.COUNTER_SCREW_RISE) > 1e-4:
            raise RuntimeError(f"{label}: settled nominal changed")
        if int(display.GetPrimaryPrecision2()) != spec.COUNTER_PRECISION:
            raise RuntimeError(f"{label}: settled precision changed")
        _assert_callout(display, spec.COUNTER_DIMENSION)

    return settled


def _dowel_proud_setting(
    adapter: Any, detail: Any
) -> tuple[Callable[[], None], Callable[[], None]]:
    """Each dowel's free end below the crossbar underside (the knife mount's
    clamped top seat), the proud MHA-SM-00 step 1 sets: a toleranced setting
    dimension on DETAIL A, the title block's .XX governing it. Returns its
    settled check and the deferred move of its text onto a leader."""
    label = "dowel proud"
    top, end = (
        model_point_in_view(
            adapter, detail, (x / 1000.0, y / 1000.0, 0.0), label=f"{label} {name}"
        )
        for name, (x, y) in (
            ("top", spec.DOWEL_PROUD_TOP_POINT),
            ("end", spec.DOWEL_PROUD_END_POINT),
        )
    )
    line_x = top[0] + DOWEL_PROUD_LINE_OFFSET
    mid_y = (top[1] + end[1]) / 2.0
    proud_mm = spec.DOWEL_PROUD_TOP_POINT[1] - spec.DOWEL_PROUD_END_POINT[1]
    annotation = _imported_setting(
        adapter,
        detail,
        feature=spec.DOWEL_PROUD_FEATURE,
        dimension=spec.DOWEL_PROUD_DIMENSION,
        text_xy=(line_x, mid_y),
        label=label,
    )

    def offset_text() -> None:
        offset_dimension_text(
            adapter,
            [annotation],
            {
                spec.DOWEL_PROUD_DIMENSION: (
                    line_x + DOWEL_PROUD_TEXT_DX,
                    mid_y + DOWEL_PROUD_TEXT_DY,
                )
            },
        )

    display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")

    def settled() -> None:
        if (str(display.GetText(1) or ""), str(display.GetText(2) or "")) != ("", ""):
            raise RuntimeError(f"{label} must print as a toleranced setting, not a reference")
        if abs(_dimension_value_mm(display) - proud_mm) > 1e-4:
            raise RuntimeError(f"{label} reads {_dimension_value_mm(display):g} mm")
        if int(display.GetPrimaryPrecision2()) != spec.DOWEL_PROUD_PRECISION:
            raise RuntimeError(f"{label}: precision changed")
        _assert_callout(display, spec.DOWEL_PROUD_DIMENSION)

    settled()
    return settled, offset_text


def _break_out_dowel_end(adapter: Any, detail: Any) -> None:
    """Cut DETAIL A's window over the front dowel's proud length to the front
    mount's mid-plane, so the dowel's free end prints as a visible edge
    (rule 9: a section or breakout, never a hidden line); read back the
    section count and pick that edge (draw_mg_magnifier_assembly's
    _break_out_plain_end)."""
    label = f"{notes.DETAIL_TITLE} dowel broken-out window"
    view = _early_bound(detail, "IView")
    draw = adapter.currentModel
    x = spec.DOWEL_PROUD_TOP_POINT[0]
    top = spec.DOWEL_PROUD_TOP_POINT[1] - DOWEL_PROUD_WINDOW_TOP_INSET_MM
    bottom = spec.DOWEL_PROUD_END_POINT[1] - DOWEL_PROUD_WINDOW_BOTTOM_OVERRUN_MM
    centre_y, half_h = (top + bottom) / 2.0, (top - bottom) / 2.0
    model = [
        (
            x + DOWEL_PROUD_WINDOW_HALF_WIDTH_MM * math.cos(angle) * wobble,
            centre_y + half_h * math.sin(angle) * wobble,
        )
        for angle, wobble in (
            (index * math.pi / 4.0, (1.0, 0.92)[index % 2]) for index in range(8)
        )
    ]
    sheet = [
        model_point_in_view(
            adapter, view, (mx / 1000.0, my / 1000.0, 0.0), label=f"{label} point"
        )
        for mx, my in model
    ]
    _activate_view(adapter, view, label=label)
    sketch = _early_bound(view.GetSketch(), "ISketch")
    transform = _early_bound(sketch.ModelToSketchTransform, "IMathTransform")
    utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    points: list[float] = []
    for sx, sy in (*sheet, sheet[0]):
        point = _early_bound(
            utility.CreatePoint(double_array([sx, sy, 0.0])), "IMathPoint"
        )
        projected = _early_bound(point.MultiplyTransform(transform), "IMathPoint")
        points.extend(float(value) for value in projected.ArrayData)
    manager = _early_bound(draw.SketchManager, "ISketchManager")
    previous = bool(manager.AddToDB)
    manager.AddToDB = True
    try:
        segment = manager.CreateSpline(double_array(points))
    finally:
        manager.AddToDB = previous
    if segment is None:
        raise RuntimeError(f"failed to sketch the {label}")
    segment = _early_bound(segment, "ISketchSegment")
    selection = _early_bound(draw.SelectionManager, "ISelectionMgr")
    data = selection.CreateSelectData()
    data.View = view
    if not segment.Select4(False, data):
        raise RuntimeError(f"failed to select the {label}")
    if (
        _early_bound(draw, "IDrawingDoc").CreateBreakOutSection(
            DOWEL_PROUD_BREAK_OUT_DEPTH_MM / 1000.0
        )
        is not True
    ):
        raise RuntimeError(f"{label} was refused")
    draw.ClearSelection2(True)
    rebuild_drawing(adapter, label=label)
    count = int(view.GetBreakOutSectionCount())
    if count != 1:
        raise RuntimeError(f"{notes.DETAIL_TITLE} holds {count} broken-out sections, not 1")
    # The free end's edge, a little inside the dowel's radius off its axis.
    pick = model_point_in_view(
        adapter,
        view,
        ((x + 0.8) / 1000.0, spec.DOWEL_PROUD_END_POINT[1] / 1000.0, 0.0),
        label=f"{label} dowel end",
    )
    _activate_view(adapter, view, label=label)
    if not draw.Extension.SelectByID2(
        "", "EDGE", pick[0], pick[1], 0.0, False, 0, null_callout(), 0
    ):
        raise RuntimeError(f"{label}: no visible edge at the dowel's free end {pick!r}")
    kinds = [
        int(selection.GetSelectedObjectType3(index, -1))
        for index in range(1, int(selection.GetSelectedObjectCount2(-1)) + 1)
    ]
    draw.ClearSelection2(True)
    if SEL_EDGES not in kinds:
        raise RuntimeError(f"{label}: the dowel end pick selected {kinds}, no edge")
    _telemetry.info(
        f"{label}: broken out {DOWEL_PROUD_BREAK_OUT_DEPTH_MM:.3f} mm deep; the "
        f"dowel's free end is a visible edge (pick types {kinds})"
    )


def _activate_view(adapter: Any, view: Any, *, label: str) -> None:
    name = view_name(adapter, view)
    if not _early_bound(adapter.currentModel, "IDrawingDoc").ActivateView(name):
        raise RuntimeError(f"failed to activate the {label} {name!r}")
    adapter.currentModel.ClearSelection2(True)


def _placed_detail(adapter: Any) -> Any:
    """The uncropped 1:1 *Front model view, moved so the crop circle's model
    centre lands on ``DETAIL_CENTRE``."""
    label = notes.DETAIL_TITLE
    view = _early_bound(
        place_view(adapter, str(SOURCE), "*Front", *DETAIL_CENTRE, scale=DETAIL_SCALE),
        "IView",
    )
    apply_view_configuration(adapter, view, role=ViewRole.PLAIN, label=label)
    centre_m = (
        DETAIL_MODEL_CENTRE_MM[0] / 1000.0,
        DETAIL_MODEL_CENTRE_MM[1] / 1000.0,
        0.0,
    )
    centre = model_point_in_view(adapter, view, centre_m, label=f"{label} centre")
    position = tuple(float(value) for value in view.Position)
    target = [position[axis] + DETAIL_CENTRE[axis] - centre[axis] for axis in range(2)]
    if not view.SetViewPosition(double_array(target), False):
        raise RuntimeError(f"failed to move the {label} onto its spot")
    adapter.currentModel.EditRebuild3()
    centre = model_point_in_view(adapter, view, centre_m, label=f"{label} centre")
    if max(abs(a - b) for a, b in zip(centre, DETAIL_CENTRE)) > DETAIL_POSITION_TOL_M:
        raise RuntimeError(f"{label} centre sits at {centre!r}, not {DETAIL_CENTRE!r}")
    set_hidden_lines_removed(adapter, view)
    return view


def _view_sketch_circle(
    adapter: Any,
    view: Any,
    centre: tuple[float, float],
    radius: float,
    *,
    label: str,
    exact: bool,
) -> Any:
    """A circle (sheet metres) in ``view``'s own sketch, the view active;
    ``exact`` adds it to the database without sketch inference."""
    view = _early_bound(view, "IView")
    _activate_view(adapter, view, label=label)
    sketch = _early_bound(view.GetSketch(), "ISketch")
    transform = _early_bound(sketch.ModelToSketchTransform, "IMathTransform")
    utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    points = []
    for x, y in (centre, (centre[0] + radius, centre[1])):
        point = _early_bound(
            utility.CreatePoint(double_array([x, y, 0.0])), "IMathPoint"
        )
        projected = _early_bound(point.MultiplyTransform(transform), "IMathPoint")
        points.append(tuple(float(value) for value in projected.ArrayData))
    manager = _early_bound(adapter.currentModel.SketchManager, "ISketchManager")
    previous = bool(manager.AddToDB)
    manager.AddToDB = exact
    try:
        circle = manager.CreateCircle(*points[0], *points[1])
    finally:
        manager.AddToDB = previous
    if circle is None:
        raise RuntimeError(f"failed to sketch the {label} circle")
    return circle


def _crop_detail(adapter: Any, view: Any) -> None:
    """Crop ``view`` to the circle round ``DETAIL_CENTRE``: sketch the circle
    in the active view's own sketch and Crop2 while it is still selected."""
    label = notes.DETAIL_TITLE
    view = _early_bound(view, "IView")
    _view_sketch_circle(
        adapter, view, DETAIL_CENTRE, DETAIL_CROP_RADIUS, label=label, exact=False
    )
    status = int(view.Crop2(False, False, 1))
    adapter.currentModel.ClearSelection2(True)
    adapter.currentModel.EditRebuild3()
    view.UpdateViewDisplayGeometry()
    cropped = bool(view.IsCropped())
    _telemetry.info(
        f"summing: {label} Crop2 status {status}, IsCropped {cropped}",
        crop_status=status,
        cropped=cropped,
    )
    if status != CROP_NO_ERROR or not cropped:
        raise RuntimeError(
            f"{label} is not cropped: Crop2 status {status}, IsCropped {cropped}"
        )


def _mark_detail_boundary(adapter: Any, front: Any) -> None:
    """DETAIL A's boundary on the 1:5 front view: a black circle round the
    region the 1:1 detail shows, lettered beneath it (rule 9: an
    enlarged view has a lettered boundary on its parent)."""
    label = f"{notes.DETAIL_TITLE} boundary"
    centre = model_point_in_view(
        adapter,
        front,
        (DETAIL_MODEL_CENTRE_MM[0] / 1000.0, DETAIL_MODEL_CENTRE_MM[1] / 1000.0, 0.0),
        label=label,
    )
    radius = DETAIL_RADIUS_MM * ASSEMBLED_SCALE[0] / ASSEMBLED_SCALE[1] / 1000.0
    circle = _early_bound(
        _view_sketch_circle(adapter, front, centre, radius, label=label, exact=True),
        "ISketchSegment",
    )
    # A view-sketch circle prints in the sketch's grey; colour it as the
    # outline (draw_pn_pen_assembly's detail boundaries).
    circle.Color = DETAIL_BOUNDARY_COLOR
    adapter.currentModel.ClearSelection2(True)
    adapter.currentModel.EditRebuild3()
    if int(circle.Color) != DETAIL_BOUNDARY_COLOR:
        raise RuntimeError(f"{label}: circle reads colour {int(circle.Color)}")
    _activate_view(adapter, front, label=label)
    letter_xy = (
        centre[0] - DETAIL_LETTER_HALF_WIDTH,
        centre[1] - radius - DETAIL_LETTER_GAP,
    )
    if add_note(adapter, notes.DETAIL_LETTER, *letter_xy) is None:
        raise RuntimeError(f"failed to letter the {label}")
    _telemetry.info(f"summing: {label} centre {centre!r} radius {radius!r}")


def _knife_detail(adapter: Any) -> tuple[Callable[[], None], Callable[[], None]]:
    """The 1:1 knife-edge detail: the knife contact and the boss face the
    setting table's rock row is read at, and the dowel's proud.

    Returns the proud's settled check and the deferred finish of DETAIL A:
    the proud's text onto its leader and the break-out of the dowel's free
    end. Until then the sheet runs exactly the order farm run
    20261119T202848942Z proved (crop, then show and import the setting):
    with the import, text offset and break-out before the crop, the exploded
    sheet's 'Default Simplified' read no explode steps (farm leaves
    drawing:sm_summing_assembly 20261119T222550Z, 225826Z and 230558Z), so
    ``build`` runs the finish only after the exploded sheet's balloons."""
    label = notes.DETAIL_TITLE
    view = _placed_detail(adapter)
    _crop_detail(adapter, view)
    proud_settled, offset_proud_text = _dowel_proud_setting(adapter, view)
    label_xy = (
        DETAIL_CENTRE[0] - DETAIL_LABEL_INSET,
        DETAIL_CENTRE[1] - DETAIL_CROP_RADIUS - DETAIL_LABEL_GAP,
    )
    _activate_view(adapter, view, label=label)
    if add_note(adapter, DETAIL_LABEL, *label_xy) is None:
        raise RuntimeError(f"failed to label the {label}")
    _assert_view_on_sheet(view, label=label)

    def finish() -> None:
        _activate_sheet(adapter, SHEET_NAMES[0])
        offset_proud_text()
        _break_out_dowel_end(adapter, view)
        if not bool(_early_bound(view, "IView").IsCropped()):
            raise RuntimeError(f"the {label} lost its crop to the dowel break-out")
        proud_settled()

    return proud_settled, finish


def _place_setting_table(adapter: Any, views: dict[str, Any]) -> None:
    """The sheet 1 setting table along the top border, above every view.

    A 1:5 view occupies its native outline; the cropped 1:1 detail occupies
    its crop circle (_drawing_detail_crop: the occupied box is the geometric
    circle), not its native outline, which farm run
    20261117T131841014Z-1d07290b read 17.5 mm over the circle's top."""
    label = "summing setting table"
    occupied_tops = {
        name: _view_outline(view, label=f"{label} {name}")[3]
        for name, view in views.items()
    }
    occupied_tops[notes.DETAIL_TITLE] = DETAIL_CENTRE[1] + DETAIL_CROP_RADIUS
    _activate_sheet(adapter, SHEET_NAMES[0])
    left, _bottom, _right, top = SHEET_INNER_BORDER
    box = insert_general_table(
        adapter,
        title=notes.SETTING_TABLE_TITLE,
        header=notes.SETTING_TABLE_HEADER,
        rows=notes.SETTING_TABLE_ROWS,
        top_left=(left + SETTING_TABLE_INSET, top - SETTING_TABLE_INSET),
        label=label,
    )
    _assert_box_on_sheet(box, label=label)
    _telemetry.info(
        f"{label}: box {box!r}; occupied view tops {occupied_tops!r}",
        occupied_tops=repr(occupied_tops),
    )
    clashes = {
        name: view_top
        for name, view_top in occupied_tops.items()
        if box[1] < view_top + SETTING_TABLE_VIEW_GAP
    }
    if clashes:
        raise RuntimeError(
            f"{label}: bottom {box[1]:.4f} m is within {SETTING_TABLE_VIEW_GAP} m "
            f"of the tops {clashes!r}"
        )


def _place_assembled_sheet(
    adapter: Any,
) -> tuple[Callable[[], None], Callable[[], None]]:
    """Front and right at 1:5 (the screw height on the front), the knife-edge
    detail, the setting table and the notes; returns the settled check and
    DETAIL A's deferred dowel break-out."""
    _activate_sheet(adapter, SHEET_NAMES[0])
    views = {}
    for name, centre in (("*Front", FRONT_CENTER), ("*Right", RIGHT_CENTER)):
        label = f"summing assembled {name}"
        view = place_view(adapter, str(SOURCE), name, *centre, scale=ASSEMBLED_SCALE)
        set_hidden_lines_removed(adapter, view)
        apply_view_configuration(adapter, view, role=ViewRole.PLAIN, label=label)
        _assert_view_on_sheet(view, label=label)
        views[name] = view
    counter_settled = _counter_setting(adapter, views["*Front"])
    _mark_detail_boundary(adapter, views["*Front"])
    proud_settled, break_out_dowel = _knife_detail(adapter)
    _place_setting_table(adapter, views)
    _add_note_block(
        adapter, SHEET_NAMES[0], ASSEMBLED_NOTES, NOTES_XY, label="assembled notes"
    )

    def settled() -> None:
        counter_settled()
        proud_settled()

    return settled, break_out_dowel


# --- BOM ------------------------------------------------------------------------

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
        raise RuntimeError(f"summing BOM has no unique {label} column: {header!r}")
    return matches[0]


def _validate_bom(adapter: Any, table: Any) -> tuple[tuple[str, str], ...]:
    """Rewrite part numbers, prove identities/descriptions/quantities, add the
    registry's VENDOR SKU column after DESCRIPTION; return (stem, item number)
    in BOM order. Material and finish remain on the component drawings."""
    table = _early_bound(table, "ITableAnnotation")
    contents = _bom_cells(table)
    rows = len(contents)
    columns = len(contents[0]) if contents else 0
    if rows != len(BOM_COMPONENTS) + 1 or columns < 4:
        raise RuntimeError(
            f"summing BOM is {rows}x{columns}; expected {len(BOM_COMPONENTS) + 1} rows "
            "and at least four columns"
        )
    header = contents[0]
    for title in ("MATERIAL", BOM_SKU_TITLE):
        if title in (cell.upper() for cell in header):
            raise RuntimeError(f"summing BOM template already has {title!r}")
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
            raise RuntimeError(f"summing BOM repeats component family {stem!r}")
        actual[stem] = (
            row_index,
            row[item_column],
            row[description_column],
            row[quantity_column],
        )
    if set(actual) != set(BOM_COMPONENTS):
        raise RuntimeError(
            f"summing BOM identities {sorted(actual)!r} != {sorted(BOM_COMPONENTS)!r}"
        )
    items = {values[1] for values in actual.values()}
    if items != {str(item) for item in range(1, len(BOM_COMPONENTS) + 1)}:
        raise RuntimeError(
            f"summing BOM item numbers {sorted(items)!r} are not contiguous"
        )
    for stem, (row_index, _item, description, quantity) in actual.items():
        number = BOM_PART_NUMBERS[stem]
        if contents[row_index][part_column] != number:
            if not table.IsCellTextEditable(row_index, part_column):
                raise RuntimeError(
                    f"summing BOM part-number cell for {stem!r} is locked"
                )
            table.SetText2(row_index, part_column, False, number)
        if description != BOM_DESCRIPTIONS[stem]:
            raise RuntimeError(f"summing BOM description mismatch for {stem!r}")
        if quantity != str(BOM_QUANTITIES[stem]):
            raise RuntimeError(
                f"summing BOM quantity for {stem!r} is {quantity!r}, "
                f"expected {BOM_QUANTITIES[stem]}"
            )

    if not table.InsertColumn2(
        _INSERT_COLUMN_AFTER,
        description_column,
        BOM_SKU_TITLE,
        _INSERT_COLUMN_DEFAULT_WIDTH,
    ):
        raise RuntimeError("summing BOM refused the VENDOR SKU column")
    column = description_column + 1
    if not table.SetColumnTitle2(column, BOM_SKU_TITLE, False):
        raise RuntimeError("summing BOM VENDOR SKU column title did not set")
    for stem, (row_index, *_rest) in actual.items():
        if not table.IsCellTextEditable(row_index, column):
            raise RuntimeError(f"summing BOM VENDOR SKU cell for {stem!r} is locked")
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
        raise RuntimeError(f"summing BOM columns {header!r} are not the contract")
    for key, index in widths.items():
        width = BOM_COLUMN_WIDTHS[key]
        if abs(float(table.SetColumnWidth(index, width, 0)) - width) > 1e-6:
            raise RuntimeError(f"summing BOM {key} column width did not persist")
    for row in range(rows):
        table.SetRowHeight(row, BOM_ROW_HEIGHT, 0)
    if not adapter.currentModel.EditRebuild3():
        raise RuntimeError("summing BOM rebuild failed")
    settled = _bom_cells(table)
    for stem, (row_index, *_rest) in actual.items():
        for key, text in (("part", BOM_PART_NUMBERS[stem]), ("sku", BOM_SKUS[stem])):
            applied = settled[row_index][widths[key]]
            if applied != text:
                raise RuntimeError(
                    f"summing BOM {key} for {stem!r} reads {applied!r}, expected {text!r}"
                )
    return tuple((stem, actual[stem][1]) for stem in BOM_COMPONENTS)


def _bom_vertical_limits(table: Any) -> tuple[float, float]:
    """Read the top-left-anchored BOM after its rows have grown to fit."""
    table = _early_bound(table, "ITableAnnotation")
    annotation = _early_bound(table.GetAnnotation(), "IAnnotation")
    top = float(annotation.GetPosition()[1])
    heights = tuple(float(table.GetRowHeight(row)) for row in range(int(table.RowCount)))
    if not math.isfinite(top) or not heights or any(
        not math.isfinite(height) or height <= 0.0 for height in heights
    ):
        raise RuntimeError("summing BOM has invalid native row heights or position")
    return top - sum(heights), top


def exploded_caption_xy(bom_bottom: float) -> tuple[float, float]:
    """Follow the rebuilt BOM bottom without changing its full identities."""
    return BOM_ANCHOR[0], bom_bottom - EXPLODED_CAPTION_OFFSET


def _assert_exploded_caption(adapter: Any, table: Any, note: Any) -> None:
    _activate_sheet(adapter, SHEET_NAMES[1])
    bottom, top = _bom_vertical_limits(table)
    extent = tuple(float(value) for value in note.GetExtent())
    if len(extent) != 6 or not all(math.isfinite(value) for value in extent):
        raise RuntimeError(f"summing exploded caption has invalid extent {extent!r}")
    box = (extent[0], extent[1], extent[3], extent[4])
    if box[2] <= box[0] or box[3] <= box[1]:
        raise RuntimeError(f"summing exploded caption has empty extent {extent!r}")
    gap = bottom - box[3]
    _telemetry.info(
        "summing BOM and exploded caption native clearance",
        bom_top_mm=top * 1000.0,
        bom_bottom_mm=bottom * 1000.0,
        caption_box_mm=tuple(value * 1000.0 for value in box),
        caption_gap_mm=gap * 1000.0,
    )
    _assert_box_on_sheet(box, label="summing exploded caption")
    if gap < EXPLODED_CAPTION_MIN_GAP:
        raise RuntimeError(
            f"summing exploded caption has {gap * 1000.0:.3f} mm below the BOM; "
            f"requires {EXPLODED_CAPTION_MIN_GAP * 1000.0:.1f} mm"
        )


def _place_exploded_sheet(adapter: Any) -> Callable[[], None]:
    """The exploded isometric, its BOM (with vendor SKU) and one balloon per
    BOM row; returns the check that proves every balloon again after the last
    rebuild."""
    label = "summing exploded"
    _activate_sheet(adapter, SHEET_NAMES[1])
    exploded = place_view(
        adapter, str(SOURCE), "*Isometric", *EXPLODED_ISO_CENTER, scale=EXPLODED_SCALE
    )
    set_high_quality_shaded_with_edges(adapter, exploded, label=label)
    # Configuration, then its own explode, then the BOM and balloons bind.
    configuration = apply_view_configuration(adapter, exploded, label=label)
    set_view_exploded_state(
        adapter, exploded, True, configuration=configuration, label=label
    )
    _center_view_outline(adapter, exploded, EXPLODED_ISO_CENTER, label=label)
    _assert_view_on_sheet(exploded, margin=BALLOON_MARGIN, label=label)
    table = insert_bom_table(
        adapter,
        exploded,
        anchor_xy=BOM_ANCHOR,
        expected_components=BOM_COMPONENTS,
        descriptions=BOM_DESCRIPTIONS,
        identity_aliases=BOM_IDENTITY_ALIASES,
        configuration_grouping="same-part",
        label="summing",
    )
    items = _validate_bom(adapter, table)
    landings = add_component_bom_balloons(
        adapter,
        exploded,
        items=items,
        anchors=BALLOON_ANCHORS,
        label="summing exploded-view BOM coverage",
        margin=BALLOON_MARGIN,
    )
    if len(landings) != len(BOM_COMPONENTS):
        raise RuntimeError(
            f"summing exploded view carries {len(landings)} balloons, "
            f"expected one per BOM row ({len(BOM_COMPONENTS)})"
        )
    bottom, _top = _bom_vertical_limits(table)
    caption = _add_note_block(
        adapter,
        SHEET_NAMES[1],
        notes.EXPLODED_CAPTION,
        exploded_caption_xy(bottom),
        label="exploded-view caption",
    )
    if not adapter.currentModel.EditRebuild3():
        raise RuntimeError("summing exploded caption rebuild failed")
    _assert_exploded_caption(adapter, table, caption)

    def settled() -> None:
        assert_balloon_landings(adapter, landings)
        _assert_exploded_caption(adapter, table, caption)

    return settled


def _place_finished_sheet(adapter: Any) -> None:
    """The finished assembly in full detail, centred."""
    label = "summing finished"
    _activate_sheet(adapter, SHEET_NAMES[2])
    finished = place_view(
        adapter, str(SOURCE), "*Isometric", *ASSEMBLY_ISO_CENTER, scale=FINISHED_SCALE
    )
    set_high_quality_shaded_with_edges(adapter, finished, label=label)
    configuration = apply_view_configuration(
        adapter, finished, role=ViewRole.FULL_DETAIL, label=label
    )
    set_view_exploded_state(
        adapter, finished, False, configuration=configuration, label=label
    )
    _center_view_outline(adapter, finished, ASSEMBLY_ISO_CENTER, label=label)
    _assert_view_on_sheet(finished, margin=FINISHED_CLEARANCE, label=label)
    assert_full_detail_view(adapter, label="summing assembly")


def _create_sheets(adapter: Any) -> None:
    new_project_drawing(
        adapter, layout=SPEC.layout, scale=ASSEMBLED_SCALE, unit=notes.UNIT
    )
    create_blank_drawing_sheets(adapter, SHEET_NAMES, label="summing package")
    for name in SHEET_NAMES:
        sheet = _activate_sheet(adapter, name)
        numerator, denominator = SHEET_SCALES[name]
        if not sheet.SetScale(float(numerator), float(denominator), False, False):
            raise RuntimeError(f"failed to set summing sheet scale: {name}")


@_telemetry.traced("drawing.sm_summing_assembly")
def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source assembly is missing: {SOURCE}")
    check("open summing drawing source", adapter.open_model(str(SOURCE)))
    source_model = _early_bound(adapter.currentModel, "IModelDoc2")
    properties = read_required_properties(
        source_model,
        ("Number", "Revision", "Title", "Material Specification", "Finish", "Quantity"),
        required=("Number", "Revision", "Material Specification", "Finish", "Quantity"),
    )
    if properties["Number"] != notes.DRAWING_NUMBER:
        raise RuntimeError(
            f"summing source Number {properties['Number']!r} != {notes.DRAWING_NUMBER!r}"
        )
    _validate_source(source_model)

    _create_sheets(adapter)
    assembled_settled, break_out_dowel = _place_assembled_sheet(adapter)
    exploded_settled = _place_exploded_sheet(adapter)
    _place_finished_sheet(adapter)
    break_out_dowel()

    def settled() -> None:
        assembled_settled()
        exploded_settled()

    return finalize_drawing(
        adapter,
        OUTPUTS,
        layout=SPEC.layout,
        pdf_title=PDF_TITLE,
        scale=ASSEMBLED_SCALE,
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
