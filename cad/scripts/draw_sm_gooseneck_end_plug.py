r"""Create the manufacturing drawing for MHA-SM-05, the gooseneck end plug.

The SLDPRT remains authoritative.  This recipe supplies the views, places the
part's marked dimensions and the native tap callout, and links the notes;
sheet/template and export behaviour lives in ``_drawing_common``.

Owner rulings 2026-11-08 (Pedro), #2315: the plug is its own part, bonded
into MHA-SM-01's arm end with LOCTITE 638 at MHA-SM-00 and tapped #10-24
blind BEFORE bonding for the purchased MHA-SM-VN-56 shoulder screw (owner
ruling 2026-11-08 (Pedro), #2144 item 11.4: plain tap, no counterbore,
frames or datums).  The sheet carries, at 4:1:

* the SIDE VIEW (``*Front``), where a turned part's diameters sit beside its
  lengths (rule 11), on its axis centerline: the head Ø left of the end face,
  the spigot Ø right of its end (a reference: note 1's fit to the measured
  MHA-SM-01 bore governs), and the head and overall lengths over the part;
* the END VIEW (``*Left``, third-angle left of the side view): the end face,
  carrying the native blind-tap callout, which names the screw and states its
  engagement (owner minor sm-gooseneck-end-plug RV-01);

and the isometric at 2:1.  The sheet prints decimal inch (#290, the registry
row's drawing_unit).

Run with SolidWorks open::

    uv run python cad\scripts\draw_sm_gooseneck_end_plug.py sm-gooseneck-end-plug
"""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

from solidworks_mcp.adapters.solidworks.drawing import (
    dimension_name,
    place_view,
    remove_notes_matching,
)

import _telemetry
from _check import check
from _com import _early_bound
from _drawing_centerline import add_view_centerline
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    rebuild_drawing,
    stamp_drawing_summary,
)
from _drawing_dimension_import import curate_view_dimensions
from _drawing_dimensions import assert_imported_precision
from _drawing_hole_callout import add_native_hole_callout, set_hole_callout_precision
from _drawing_notes import add_property_linked_note
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_view_display import set_hidden_lines_removed
from _gear_drawing_entities import visible_circle_edge
from _hole_callout_thread_class import omit_title_block_thread_class
from _holes import DIAMETER_TOLERANCE_MM, _verify_tap_metadata
from _machinist_review_mode import MachinistReviewMode
from _part_properties import part_drawing_unit
from _paths import CAD_ROOT
from _session import run_build
from sm_gooseneck_end_plug_spec import (
    DIMENSION_CALLOUTS_BY_NAME,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    TAP_CALLOUT_BELOW,
    TAP_CALLOUT_PRECISION,
)
from sm_gooseneck_geom import PLUG_DIA, PLUG_HEAD_LENGTH, PLUG_LENGTH
from sm_gooseneck_spring_joint import (
    TAP_DRILL_DEPTH,
    TAP_DRILL_DIA,
    TAP_SPEC,
    TAP_THREAD_DEPTH,
)

# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME["sm_gooseneck_end_plug"]
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

# A Ø.50 x 1.02 plug at 4:1: the end view and the side view share one row
# midway between the top border and the title block; the isometric, at 2:1,
# stands right of the side view.
SHEET_SCALE = (4.0, 1.0)
VIEW_SCALE = (4, 1)
ISO_SCALE = (2, 1)
_S = VIEW_SCALE[0] / VIEW_SCALE[1] / 1000.0  # sheet metres per model mm
END_CENTER = (0.065, 0.170)
FRONT_CENTER = (0.190, 0.170)
ISO_CENTER = (0.355, 0.195)
_HALF_DIA = PLUG_DIA / 2.0 * _S


def _front_x(model_x: float) -> float:
    """Sheet x of model x on the side view, which centres the plug's box
    (x 0..PLUG_LENGTH, model +X right)."""
    return FRONT_CENTER[0] + (model_x - PLUG_LENGTH / 2.0) * _S


END_FACE_X = _front_x(0.0)
SPIGOT_END_X = _front_x(PLUG_LENGTH)
TOP_Y = FRONT_CENTER[1] + _HALF_DIA

# The side view's dimensions: the two lengths stacked over the part, the head
# length nearer; the head Ø left of the end face, in the gap to the end
# view's circle; the spigot Ø, with its two-row fit callout, right of the
# spigot's end, short of the isometric.
FRONT_KEEP = {
    "PlugHeadLength": (_front_x(PLUG_HEAD_LENGTH / 2.0), TOP_Y + 0.010),
    "PlugLength": (FRONT_CENTER[0], TOP_Y + 0.022),
    "PlugDia": (END_FACE_X - 0.014, FRONT_CENTER[1]),
    "PlugShankDia": (SPIGOT_END_X + 0.016, FRONT_CENTER[1]),
}
if set(FRONT_KEEP) != {name for names in DRAWING_DIMENSIONS.values() for name in names}:
    raise AssertionError("the end plug sheet does not place every marked dimension")

# The end view (*Left) looks at the end face along +X.  The tap's native
# callout stands over the end view, clear of the side view's stacked lengths,
# its top inside the border.  The callout text is centred on the anchor, and
# its widest line (ENGAGEMENT .220 MIN (1.16D)) is about 0.066 wide, so an
# anchor at 0.030 clipped it at the left border (machinist review, farm run
# 20261109T035321681Z, rule 13); 0.072 keeps it inside the border and left of
# the side view's 1.02 dimension.
TAP_CALLOUT_XY = (0.072, 0.240)

# The two note lines sit in the bottom left, under the views and left of
# the title block (x 0.216); the isometric's note sits under it.  The side
# view is a principal view at the sheet's scale, so it carries no label
# (drawing-guidelines.md rule 9).
NOTES_XY = (0.016, 0.110)
ISO_NOTE_XY = (0.320, 0.140)
TAPPED_HOLE_NOTE = "Tapped Hole"


def _require_saved_tap(model: Any) -> None:
    """Require the saved native receiver's size, class, blind ends, drill Ø
    and both depths."""
    feature = _early_bound(model, "IPartDoc").FeatureByName("ThreadBore")
    if feature is None:
        raise RuntimeError("saved end plug has no native ThreadBore")
    feature = _early_bound(feature, "IFeature")
    if str(feature.GetTypeName2()) != "HoleWzd":
        raise RuntimeError("saved end plug ThreadBore is not a native Hole Wizard tap")
    definition = feature.GetDefinition()
    if definition is None:
        raise RuntimeError("saved end plug ThreadBore has no hole definition")
    definition = _early_bound(definition, "IWizardHoleFeatureData2")
    if str(definition.FastenerSize).strip() != TAP_SPEC.size:
        raise RuntimeError("saved end plug ThreadBore has the wrong thread size")
    _verify_tap_metadata(definition, TAP_SPEC, "saved end plug ThreadBore")
    for member, expected, what in (
        ("TapDrillDiameter", TAP_DRILL_DIA, "tap drill"),
        ("TapDrillDepth", TAP_DRILL_DEPTH, "tap drill depth"),
        ("ThreadDepth", TAP_THREAD_DEPTH, "thread depth"),
    ):
        value = float(getattr(definition, member)) * 1000.0
        if not math.isfinite(value) or abs(value - expected) > DIAMETER_TOLERANCE_MM:
            raise RuntimeError(
                f"saved end plug {what} {value:.3f} != {expected:.3f} mm"
            )


def _assert_part_callouts(adapter: Any, annotations: list[Any]) -> None:
    """The part authors every callout below its dimension's value; the
    import must carry each one unchanged (the drawing never writes them,
    #1942)."""
    # swDimensionTextCalloutBelow = 4.
    expected = {(4, name): text for name, text in DIMENSION_CALLOUTS_BY_NAME.items()}
    found: dict[tuple[int, str], str] = {}
    for raw in annotations:
        annotation = _early_bound(raw, "IAnnotation")
        name = dimension_name(adapter, annotation)
        slots = [slot for slot, expected_name in expected if expected_name == name]
        if not slots:
            continue
        display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
        for slot in slots:
            found[(slot, name)] = str(display.GetText(slot) or "").replace("\r\n", "\n")
    if found != expected:
        raise RuntimeError(
            f"end plug dimension callouts did not import: {found!r} != {expected!r}"
        )


@_telemetry.traced("drawing.hole_callout_below")
def _set_tap_callout_below(display: Any, text: str) -> None:
    """Write ``text`` under the native tap callout and read it back.

    swDimensionTextCalloutBelowDefinition (8) pairs with the writable
    swDimensionTextCalloutBelow (4); the prefix, size and depth definitions
    stay untouched, so the Hole Wizard variables stay associative
    (draw_pd_guide_lock._set_hole_callout_below)."""
    definitions = {part: str(display.GetText(part) or "") for part in (5, 6, 7, 8)}
    # SolidWorks may store CRLF row breaks; compare both sides without CR.
    below = definitions[8].replace("\r", "").rstrip()
    updated = f"{below}\n{text}" if below else text
    display.SetText(4, updated)
    if str(display.GetText(8) or "").replace("\r", "") != updated or any(
        str(display.GetText(part) or "") != definitions[part] for part in (5, 6, 7)
    ):
        raise RuntimeError(
            "end plug tap callout location rows or native definitions did not "
            f"persist: {[str(display.GetText(part) or '') for part in (5, 6, 7, 8)]!r}"
        )


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open end plug source", await adapter.open_model(str(SOURCE)))
    _require_saved_tap(adapter.currentModel)
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
        adapter,
        property_view=PART_STEM,
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        unit=part_drawing_unit(PART_STEM),
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Gooseneck End Plug Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "gooseneck end plug; turned 1018; bonded spigot; blind tap",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )
    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=VIEW_SCALE)
    end = place_view(adapter, str(SOURCE), "*Left", *END_CENTER, scale=VIEW_SCALE)
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    # A turned part needs no hidden lines: the tap is fully defined by its
    # native callout (drawing-guidelines.md rule 9).
    for view in (front, end, iso):
        set_hidden_lines_removed(adapter, view)

    annotations = curate_view_dimensions(
        adapter,
        front,
        keep=FRONT_KEEP,
        view_label="side",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    # Decimal places (and so the general-tolerance row each dimension claims)
    # are authored on the part; the sheet only proves the import kept them.
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    _assert_part_callouts(adapter, annotations)
    # The side view's axis (the template centre-marks the end view's circles
    # as the view is placed, draw_mg_wheel_drum).
    add_view_centerline(
        adapter,
        front,
        face_xy=(_front_x(PLUG_HEAD_LENGTH / 2.0), FRONT_CENTER[1] + _HALF_DIA / 2.0),
        label="end plug axis centerline",
    )

    # The blind tap, natively called out on the end face: the title block's
    # THREADS row owns the 2B class (drawing-guidelines.md rule 2), its depths
    # print at two places, and the screw and its engagement print under the
    # native rows.
    tap_edge = visible_circle_edge(adapter, end, TAP_DRILL_DIA)
    tap_callout = add_native_hole_callout(
        adapter,
        end,
        edge=tap_edge,
        callout_xy=TAP_CALLOUT_XY,
        label=f"end plug {TAP_SPEC.size} blind tap",
    )
    omit_title_block_thread_class(tap_callout, label="end plug tap")
    set_hole_callout_precision(
        tap_callout, TAP_CALLOUT_PRECISION, label="end plug tap depths"
    )
    _set_tap_callout_below(tap_callout, TAP_CALLOUT_BELOW)
    rebuild_drawing(adapter, label="end plug tap callout")

    add_property_linked_note(adapter, "Manufacturing Notes", *NOTES_XY)
    add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_XY)

    # SolidWorks pins its own "#10-24 Tapped Hole" note beside a tap's native
    # callout; the callout already states the thread, so any such label goes,
    # and finalize_drawing's count then proves none is left.
    removed_tap_labels = remove_notes_matching(adapter, TAPPED_HOLE_NOTE)
    _telemetry.info(f"removed {removed_tap_labels} automatic tapped-hole label(s)")

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Gooseneck End Plug Manufacturing Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        redundant_note_substrings=(TAPPED_HOLE_NOTE,),
        expected_redundant_notes=0,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
