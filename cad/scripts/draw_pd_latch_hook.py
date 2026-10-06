r"""Create the manufacturing drawing for the latch hook (MHA-PD-014).

One face view (``*Front``, the plane of the strip) carries everything the
maker needs: the forming template's inner-edge radii (shortened radius
leaders: their centres are metres off the sheet) with the construction that
fixes them -- R845 centred on the top cut's line, R485 tangent to it at the
tangency run -- the free end's run to its round's centre and the reference
overall to its extreme, and the three drilled holes with their runs -- every
run measured from the square top cut, the sheet's datum edge.  The strip's
width and thickness are the stock's (title-block MATERIAL); the pin hole and
the rivet pair's midpoint are centred on the width by note.  An isometric
view shows the flat strip.
"""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, _early_bound, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_edge_dimension,
    add_property_linked_note,
    assert_dimension_measures,
    assert_imported_precision,
    curate_view_dimensions,
    dimension_name,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    set_arc_endpoints_to_max,
    set_dimension_callouts,
    set_hidden_lines_removed,
    set_reference_dimension,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from pd_latch_hook_geometry import (
    END_L,
    LOCAL_X_MAX,
    LOCAL_X_MIN,
    LOCAL_Y_MAX,
    LOCAL_Y_MIN,
    TIP_R,
)
from pd_latch_hook_spec import (
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    DRAWING_REFERENCE_PRECISION,
    INNER_R1_CALLOUT,
    INNER_R2_CALLOUT,
    JUNCTION_RUN_CALLOUT,
    OVERALL_LENGTH,
    PIN_HOLE_CALLOUT,
    RIVET_HOLE_CALLOUT,
    TIP_RUN_CALLOUT,
)
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
)

SPEC = DRAWINGS_BY_NAME["pd_latch_hook"]
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

# A 105 x 17 strip with Ø1.65 holes 3.9 apart: 3:1 keeps the rivet pair's
# two .XXX dimensions legible and the whole strip on the landscape sheet.
SHEET_SCALE = (3.0, 1.0)
VIEW_SCALE = (3, 1)
ISO_SCALE = (1, 1)
_S = SHEET_SCALE[0] / SHEET_SCALE[1]
FRONT_CENTER = (0.200, 0.160)
ISO_CENTER = (0.322, 0.100)
NOTES_XY = (0.020, 0.085)
# The view centre sits on the part's bounding-box centre (local X, Y, mm).
_MODEL_CENTER = ((LOCAL_X_MIN + LOCAL_X_MAX) / 2.0, (LOCAL_Y_MIN + LOCAL_Y_MAX) / 2.0)


def _sheet(model_x: float, model_y: float) -> tuple[float, float]:
    """Sheet XY (m) of a local model point (mm) on the face view."""
    return (
        FRONT_CENTER[0] + (model_x - _MODEL_CENTER[0]) * _S / 1000.0,
        FRONT_CENTER[1] + (model_y - _MODEL_CENTER[1]) * _S / 1000.0,
    )


DIMENSION_CALLOUTS = {
    "PinHoleDia": PIN_HOLE_CALLOUT,
    "RivetHoleDia": RIVET_HOLE_CALLOUT,
    "InnerR1": INNER_R1_CALLOUT,
    "InnerR2": INNER_R2_CALLOUT,
}
CALLOUTS_ABOVE = {
    "JunctionRun": JUNCTION_RUN_CALLOUT,
    "TipRun": TIP_RUN_CALLOUT,
}
# The template radii's centres sit 1.4 m and 2.5 m off the sheet at 3:1: a
# full-length radius line runs through the border and the title block.
SHORTENED_RADII = ("InnerR1", "InnerR2")

# Text positions: the runs stacked above the strip, shortest nearest, with
# the reference overall outermost; the template radii below their arcs and
# the pin hole's size between them, all clear of the notes; the rivet pair's
# run and pitch right of the top cut, its size below-right, where its leader
# meets the lower hole without crossing their extension lines.
FRONT_KEEP = {
    "JunctionRun": _sheet(-26.0, 10.0),
    "PinHoleRun": _sheet(-38.0, 16.0),
    "TipRun": _sheet(-50.0, 22.0),
    "InnerR1": _sheet(-38.0, -18.0),
    "InnerR2": _sheet(-95.0, -20.0),
    "PinHoleDia": _sheet(-72.0, -16.0),
    "RivetRun": _sheet(10.0, 7.0),
    "RivetPitch": _sheet(12.0, -1.0),
    "RivetHoleDia": _sheet(10.0, -14.0),
}
OVERALL_TEXT_Y = 28.0  # local mm above the top cut's centre
# Picks for the reference overall: the top cut, clear of the rivet holes,
# and the full round's flank a little above its extreme (re-anchored to the
# extreme natively).
_TOP_CUT_PICK = (0.0, 3.5)
_ROUND_PICK_DY = 1.0
_ROUND_PICK = (
    END_L[0] - math.sqrt(TIP_R**2 - _ROUND_PICK_DY**2),
    END_L[1] + _ROUND_PICK_DY,
)


def _set_reference_precision(adapter: Any, display: Any, label: str) -> None:
    """Give the sheet-derived reference overall its spec-owned places.

    Every controlling dimension on this print is a model dimension whose
    places the part authored and ``assert_imported_precision`` reads back.
    The parenthesised overall (top cut to the full round's extreme) is a
    read-only sum with no model dimension to import, so its places come from
    the spec's ``DRAWING_REFERENCE_PRECISION``.  ``SetPrecision3`` reports
    rejection through its return status, so the side effect is read back.
    """
    places = DRAWING_REFERENCE_PRECISION[label]
    display = _early_bound(display, "IDisplayDimension")
    # -1: swDimensionPrecisionSettings_e do-not-change for the dual and both
    # tolerance places.
    adapter._attempt(
        lambda: display.SetPrecision3(DRAWING_REFERENCE_PRECISION[label], -1, -1, -1)
    )
    applied = adapter._attempt(display.GetPrimaryPrecision2)
    if applied != places:
        raise RuntimeError(
            f"{label}: sheet dimension prints {applied} decimal places, not {places}"
        )


def _shorten_radii(
    adapter: Any, annotations: list[Any], names: tuple[str, ...]
) -> None:
    """Foreshorten the named radius dimensions and read each one back.

    ``IDisplayDimension::ShortenedRadius`` draws the radius line toward the
    centre but stops it short of it -- the jogged radius for a centre beyond
    the sheet.  A property put that SolidWorks ignores still returns, so the
    flag is read back.
    """
    remaining = set(names)
    for annotation in annotations:
        annotation = _early_bound(annotation, "IAnnotation")
        name = dimension_name(adapter, annotation)
        if name not in remaining:
            continue
        display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
        display.ShortenedRadius = True
        if not bool(display.ShortenedRadius):
            raise RuntimeError(f"radius {name!r} did not keep its shortened leader")
        remaining.discard(name)
    if remaining:
        raise RuntimeError(f"radii not shortened: {sorted(remaining)}")


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open latch-hook source", await adapter.open_model(str(SOURCE)))
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
        ),
        required=(
            "Number",
            "Material Specification",
            "Finish",
            "Quantity",
            "Manufacturing Notes",
        ),
    )
    drawing_model, _sheet_obj = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Latch Hook Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "latch hook; edgewise-bent steel strip",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=VIEW_SCALE)
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    for view in (front, iso):
        set_hidden_lines_removed(adapter, view)

    annotations = curate_view_dimensions(
        adapter,
        front,
        keep=FRONT_KEEP,
        view_label="face",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    # Places (and so each dimension's title-block row) and the drilled-hole
    # bands are authored on the part; the sheet only proves the import kept
    # them.
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS)
    set_dimension_callouts(adapter, annotations, CALLOUTS_ABOVE, location="above")
    _shorten_radii(adapter, annotations, SHORTENED_RADII)
    if not auto_center_marks(adapter, front, holes=True, size=0.0015):
        raise RuntimeError(
            "failed to add ASME center marks to the latch-hook face view"
        )
    # The true overall, top cut to the full round's extreme, as a reference
    # outside the runs so nobody cuts the strip a radius short: TipRun ends
    # at the round's centre.
    label = "overall length reference"
    overall = add_edge_dimension(
        adapter,
        front,
        p0=_sheet(*_TOP_CUT_PICK),
        p1=_sheet(*_ROUND_PICK),
        text_xy=_sheet(-OVERALL_LENGTH / 2.0, OVERALL_TEXT_Y),
        label=label,
        orientation="horizontal",
    )
    set_arc_endpoints_to_max(adapter, overall, label=label)
    # Value-only: the top cut is a straight edge and the round the only arc
    # at that end; the value proves the extreme, not the centre, was taken.
    assert_dimension_measures(
        adapter, overall, expected_mm=OVERALL_LENGTH, label=label, tolerance_mm=1e-3
    )
    set_reference_dimension(
        adapter, _early_bound(overall, "IDisplayDimension").GetAnnotation(), label=label
    )
    _set_reference_precision(adapter, overall, label)
    add_property_linked_note(
        adapter, "Manufacturing Notes", *NOTES_XY, char_height=0.003
    )

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Latch Hook Manufacturing Drawing",
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
