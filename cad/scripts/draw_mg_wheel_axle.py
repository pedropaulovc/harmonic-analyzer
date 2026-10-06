r"""Create the curated machinist drawing for the magnifying-wheel axle."""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, _early_bound, check, run_build
from _drawing_annotation_extent import (
    annotation_ink,
    assert_annotation_reservations,
    place_annotation_in_field,
    require_clear,
)
from _drawing_common import (
    DrawingOutputs,
    PmiDrawingPlacement,
    add_property_linked_note,
    add_surface_finish,
    curate_view_dimensions,
    dimension_name,
    rebuild_drawing,
    finalize_drawing,
    find_edge_near,
    project_part_pmi,
    new_project_drawing,
    read_required_properties,
    set_dimension_callouts,
    set_hidden_lines_removed,
    set_hidden_lines_visible,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME, DRAWING_TEMPLATES
from _surface_finish import surface_finish_by_key
from mg_wheel_axle_spec import (
    COLLAR_DIA as COLLAR_DIA,
    COLLAR_LEN,
    FLANGE_DIA,
    FLANGE_LEN,
    GEOMETRIC_CONTROLS,
    PART_DATUMS,
    STUD_DIA,
    STUD_LEN,
    SURFACE_FINISHES,
)
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
    view_outline,
)


SPEC = DRAWINGS_BY_NAME["mg_wheel_axle"]
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

SHEET_SCALE = (3.0, 1.0)
_K = SHEET_SCALE[0] / 1000.0  # model mm -> sheet meters
_TOTAL_LEN = FLANGE_LEN + STUD_LEN

# Front view: the profile (axle axis vertical, flange at the bottom).
# End view: the tip-side circles, third-angle above the front view.
FRONT_CENTER = (0.105, 0.100)
# The O35 flange at 3:1 makes this view a 105 mm circle, so y=0.215 ran its
# outline 3.4 mm into the top zone band. 0.208 clears it by ~3.6 mm and keeps
# the third-angle stack (end view above front, both on x=0.105) intact; the gap
# to the front view's upper dimensions is ~27 mm, so nothing crowds below.
END_CENTER = (0.105, 0.208)
ISO_CENTER = (0.310, 0.185)


def _front_y(model_y: float) -> float:
    return FRONT_CENTER[1] + (model_y - _TOTAL_LEN / 2.0) * _K


FRONT_KEEP = {
    "FlangeLength": (
        FRONT_CENTER[0] - FLANGE_DIA / 2.0 * _K - 0.018,
        _front_y(FLANGE_LEN / 2.0),
    ),
    "StudLength": (
        FRONT_CENTER[0] + FLANGE_DIA / 2.0 * _K + 0.030,
        _front_y(FLANGE_LEN + STUD_LEN / 2.0),
    ),
    "CollarLength": (
        FRONT_CENTER[0] + FLANGE_DIA / 2.0 * _K + 0.012,
        _front_y(_TOTAL_LEN - COLLAR_LEN / 2.0) - 0.0105,
    ),
}
END_KEEP = {
    "FlangeDia": (
        END_CENTER[0] - FLANGE_DIA / 2.0 * _K - 0.012,
        END_CENTER[1] + 0.045,
    ),
    "CollarDia": (
        END_CENTER[0] + FLANGE_DIA / 2.0 * _K + 0.015,
        END_CENTER[1] + 0.028,
    ),
    "StudDia": (
        END_CENTER[0] + FLANGE_DIA / 2.0 * _K + 0.015,
        END_CENTER[1] - 0.028,
    ),
}
# The stud's unilateral-minus running-fit band lives on its source-model dimension.
DIMENSION_CALLOUTS: dict[str, str] = {}

# Datum B's projected-symbol offset from the end-view centre. Placed off-axis at
# ~-54 deg so the tag's leader runs radially out of the stud circle clear of the
# O35 dimension ray and the O5.00 text (measured live while this tag was still
# sheet-authored; the same placement is now driven from the model PMI spec).
_DATUM_B_OFFSET = (0.038, -0.052)
_DATUM_B_ANGLE = math.atan2(_DATUM_B_OFFSET[1], _DATUM_B_OFFSET[0])

# The complete one-line process note fits the open band between the front
# and end views. It must not be shortened to fit beside the title block.
TEXT_FIELDS = {
    "CollarLength": (0.160, 0.116, 0.181, 0.126),
    "manufacturing notes": (0.018, 0.138, 0.260, 0.152),
    "stud bearing finish": (0.045, 0.098, 0.080, 0.126),
}


def _assert_readability(
    adapter: Any, allocated: dict[str, Any], views: tuple[Any, ...], char_height: float
) -> None:
    """Check the final native note, collar text and all neighbouring ink."""
    annotations = dict(allocated)
    allocated_names = {
        str(_early_bound(item, "IAnnotation").GetName()) for item in allocated.values()
    }
    for index, view in enumerate(views):
        for raw in _early_bound(view, "IView").GetAnnotations() or ():
            annotation = _early_bound(raw, "IAnnotation")
            if int(annotation.Visible) in (2, 3):
                continue
            name = str(annotation.GetName())
            if name not in allocated_names:
                annotations[f"view {index}: {name}"] = annotation
    inks = assert_annotation_reservations(
        adapter,
        annotations,
        TEXT_FIELDS,
        row_limits={"manufacturing notes": 1},
        text_heights={"stud bearing finish": char_height, "FlangeLength": char_height},
        check_own_lines=("CollarLength",),
    )
    template = DRAWING_TEMPLATES[SPEC.layout]
    keepout = (template.title_block_left_m, 0.0, template.width_m, template.title_block_top_m)
    for label in TEXT_FIELDS:
        ink = inks[label]
        require_clear(label, ink.text, {"title block": keepout})
        for line in ink.lines:
            box = line.box()
            require_clear(label, (box.xmin, box.ymin, box.xmax, box.ymax), {"title block": keepout})


def _view_center_delta(
    adapter: Any, view: Any, intended: tuple[float, float], label: str
) -> tuple[float, float]:
    """Measured-vs-intended geometry-center delta for coordinate picks.

    ``place_view`` anchors on the model origin's projection, not the geometry
    box center, so a part that is not origin-symmetric (this axle spans
    y 0..17) lands its geometry offset from the requested center. Every
    layout constant in this recipe is authored about the intended geometry
    center; shifting by this delta makes the edge picks and text positions
    track wherever SolidWorks actually put the geometry.
    """
    outline = view_outline(adapter, view)
    if outline is None:
        raise RuntimeError(f"{label} drawing view has no outline")
    cx = (outline[0] + outline[2]) / 2.0
    cy = (outline[1] + outline[3]) / 2.0
    _telemetry.debug(
        f"{label} view geometry center ({cx:.4f}, {cy:.4f}) vs intended "
        f"({intended[0]:.4f}, {intended[1]:.4f})"
    )
    return cx - intended[0], cy - intended[1]


def _shift(
    points: dict[str, tuple[float, float]], dx: float, dy: float
) -> dict[str, tuple[float, float]]:
    return {name: (x + dx, y + dy) for name, (x, y) in points.items()}


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open wheel-axle source", await adapter.open_model(str(SOURCE)))
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
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Wheel Axle Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "wheel axle; flanged stud; turned steel",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=(3, 1))
    end = place_view(adapter, str(SOURCE), "*Top", *END_CENTER, scale=(3, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(3, 1))
    for view in (front, iso):
        set_hidden_lines_removed(adapter, view)
    # The O5 stud hides under the O9 collar from the tip side; show it greyed
    # so its diameter and GD&T attach to a real circle.
    set_hidden_lines_visible(adapter, end)

    fdx, fdy = _view_center_delta(adapter, front, FRONT_CENTER, "front")
    edx, edy = _view_center_delta(adapter, end, END_CENTER, "end")

    def fpt(x: float, y: float) -> tuple[float, float]:
        return (x + fdx, y + fdy)

    def ept(x: float, y: float) -> tuple[float, float]:
        return (x + edx, y + edy)

    front_annotations = curate_view_dimensions(
        adapter, front, keep=_shift(FRONT_KEEP, fdx, fdy), view_label="front"
    )
    end_annotations = curate_view_dimensions(
        adapter, end, keep=_shift(END_KEEP, edx, edy), view_label="end"
    )
    set_dimension_callouts(
        adapter, [*front_annotations, *end_annotations], DIMENSION_CALLOUTS
    )
    allocated = {
        dimension_name(adapter, annotation): annotation
        for annotation in [*front_annotations, *end_annotations]
    }
    heights = annotation_ink(adapter, allocated["FlangeLength"], label="ordinary flange text").heights
    char_height = heights[0]
    if any(abs(height - char_height) > 1e-7 for height in heights):
        raise RuntimeError("axle ordinary dimension has mixed native text heights")
    if not auto_center_marks(adapter, end, holes=True, size=0.0025):
        raise RuntimeError("failed to add ASME center marks to axle end view")

    flange_face_edge = find_edge_near(
        adapter,
        front,
        fpt(FRONT_CENTER[0] + FLANGE_DIA / 4.0 * _K, _front_y(0.0)),
        axis="y",
        label="flange seating face pick",
    )
    stud_circle_top = find_edge_near(
        adapter,
        end,
        ept(END_CENTER[0], END_CENTER[1] + STUD_DIA / 2.0 * _K),
        axis="y",
        label="stud circle top pick",
    )
    collar_circle_left = find_edge_near(
        adapter,
        end,
        ept(END_CENTER[0] - COLLAR_DIA / 2.0 * _K, END_CENTER[1]),
        axis="x",
        label="collar circle left pick",
    )
    stud_circle_at_datum_b = find_edge_near(
        adapter,
        end,
        ept(
            END_CENTER[0] + STUD_DIA / 2.0 * _K * math.cos(_DATUM_B_ANGLE),
            END_CENTER[1] + STUD_DIA / 2.0 * _K * math.sin(_DATUM_B_ANGLE),
        ),
        axis="y",
        label="stud circle datum-B pick",
    )

    # GD&T is model PMI (mg_wheel_axle_spec.PART_DATUMS/GEOMETRIC_CONTROLS,
    # authored by build_mg_wheel_axle) — project it and place it where the
    # hand-authored symbols used to sit. Which VIEW receives each annotation
    # depends on its attachment (a datum tag only lands in a view aligned
    # with its face), and the projection fails loud on any mismatch. Placements track the measured view-centre deltas
    # (fpt/ept), the same corrections the retired edge picks used.
    pmi = project_part_pmi(
        adapter,
        placements={
            "datum:A": PmiDrawingPlacement(
                view=front,
                position=fpt(
                    FRONT_CENTER[0] + FLANGE_DIA / 4.0 * _K + 0.006,
                    _front_y(0.0) - 0.016,
                ),
                attachment_xy=flange_face_edge,
            ),
            "datum:B": PmiDrawingPlacement(
                view=end,
                position=ept(
                    END_CENTER[0] + _DATUM_B_OFFSET[0],
                    END_CENTER[1] + _DATUM_B_OFFSET[1],
                ),
                attachment_xy=stud_circle_at_datum_b,
            ),
            # +0.052 in y put the frame's 8 mm half-box 8.3 mm over the top
            # margin. Held to +0.045 and pushed out to +0.058 in x, which keeps
            # it clear of the flange circle (52.5 mm radius) without reaching
            # the 0.4191 right margin (a frame grows RIGHT by its full width).
            "stud_perpendicularity": PmiDrawingPlacement(
                view=end,
                position=ept(END_CENTER[0] + 0.058, END_CENTER[1] + 0.045),
                attachment_xy=stud_circle_top,
            ),
            "collar_runout": PmiDrawingPlacement(
                view=end,
                position=ept(END_CENTER[0] - 0.075, END_CENTER[1] - 0.045),
                attachment_xy=collar_circle_left,
            ),
        },
        datums=PART_DATUMS,
        controls=GEOMETRIC_CONTROLS,
        label="wheel axle PMI",
    )
    # The finish stays attached to the native stud silhouette in the profile.
    # Correct only the inherited text height to the ordinary sheet text;
    # neither the finish requirement nor the attached entity changes.
    stud_flank_y = _front_y(FLANGE_LEN + STUD_LEN / 2.0)
    finish = add_surface_finish(
        adapter,
        front,
        # A cylinder's side outline is a SILHOUETTE, not a model edge.
        edge_xy=fpt(FRONT_CENTER[0] - STUD_DIA / 2.0 * _K, stud_flank_y),
        # The ordinary-sized text stays in the empty lane left of the stud.
        symbol_xy=fpt(0.045, stud_flank_y),
        control=surface_finish_by_key(SURFACE_FINISHES, "stud_bearing"),
        label="stud bearing finish",
        entity_type="SILHOUETTE",
        char_height=char_height,
    )

    notes = add_property_linked_note(adapter, "Manufacturing Notes", 0.020, 0.145)
    allocated.update(pmi)
    allocated["manufacturing notes"] = _early_bound(notes, "INote").GetAnnotation()
    allocated["stud bearing finish"] = _early_bound(finish, "ISFSymbol").GetAnnotation()
    rebuild_drawing(adapter, label="wheel axle annotation fields")
    for label, field in TEXT_FIELDS.items():
        place_annotation_in_field(adapter, allocated[label], label=label, field=field)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        spec=SPEC,
        pdf_title="Wheel Axle Manufacturing Drawing",
        scale=SHEET_SCALE,
        layout=SPEC.layout,
        settled_checks=(
            lambda: _assert_readability(adapter, allocated, (front, end), char_height),
        ),
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
