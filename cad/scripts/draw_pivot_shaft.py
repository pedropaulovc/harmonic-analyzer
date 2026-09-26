r"""Create the curated machinist drawing for the rocker pivot shaft (MHA-065)."""

from __future__ import annotations

import argparse
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_property_linked_note,
    add_surface_finish,
    add_view_centerline,
    assert_imported_precision,
    curate_view_dimensions,
    dimension_name,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    set_dimension_callouts,
    set_hidden_lines_removed,
    set_reference_dimension,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from _surface_finish import surface_finish_by_key
from pivot_shaft_spec import (
    DOME_CALLOUT,
    DOME_HEIGHT,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    JOURNAL_LENGTH,
    LENGTH_CALLOUT,
    SHAFT_DIA,
    SHOULDER_DIA,
    SHOULDER_LENGTH,
    SURFACE_FINISHES,
)
from rocker_bank_layout import PIVOT_SHAFT_LENGTH
from solidworks_mcp.adapters.solidworks.drawing import place_view


SPEC = DRAWINGS_BY_NAME["pivot_shaft"]
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

SHEET_SCALE = (1.0, 1.0)
# One orthographic view: the side view carries every turned diameter and
# length (policy rule 7), all authored on the Right-plane half-profile, so
# "*Right" imports them natively with the axis horizontal, as the bar sits in
# the lathe. Model -Z runs to the sheet's right: the shouldered north end
# (the part origin) is on the LEFT, the plain cut-to-fit end on the right.
# An end view would carry nothing, so this sheet has none.
PROFILE_CENTER = (0.150, 0.190)
_MM = SHEET_SCALE[0] / 1000.0
# The view centres on the bar's bounding box, domes included.
_OVERALL = PIVOT_SHAFT_LENGTH + 2.0 * DOME_HEIGHT
NORTH_END_X = PROFILE_CENTER[0] - (_OVERALL / 2.0 - DOME_HEIGHT) * _MM
SOUTH_END_X = NORTH_END_X + PIVOT_SHAFT_LENGTH * _MM
SHOULDER_X = (
    NORTH_END_X + JOURNAL_LENGTH * _MM,
    NORTH_END_X + (JOURNAL_LENGTH + SHOULDER_LENGTH) * _MM,
)
SHAFT_FLANK_Y = PROFILE_CENTER[1] + SHAFT_DIA * _MM / 2.0
SHAFT_UNDER_Y = PROFILE_CENTER[1] - SHAFT_DIA * _MM / 2.0
SHOULDER_TOP_Y = PROFILE_CENTER[1] + SHOULDER_DIA * _MM / 2.0
# The 160 shaft's isometric silhouette is a slender bar taller than the
# drawable band at 1:1, so the pictorial renders at 1:2 and says so.
ISO_CENTER = (0.330, 0.175)
ISO_SCALE = (1, 2)

PROFILE_KEEP = {
    # Under the bar, centred: the REF span the cut-to-fit callout governs.
    "ShaftLength": (PROFILE_CENTER[0], 0.158),
    # The two diameters stand clear of the ends they measure: the body's
    # past the plain end, the shoulder's before the north end.
    "ShaftDia": (SOUTH_END_X + 0.018, PROFILE_CENTER[1]),
    "ShoulderDia": (NORTH_END_X - 0.022, PROFILE_CENTER[1]),
    # The short axial lengths stack above the north end: journal, then
    # shoulder, each over the feature it spans.
    "JournalLength": ((NORTH_END_X + SHOULDER_X[0]) / 2.0, 0.210),
    "ShoulderLength": ((SHOULDER_X[0] + SHOULDER_X[1]) / 2.0, 0.226),
    # Under the north dome: a short .X height the "BOTH ENDS" callout makes
    # a 2X statement.
    "DomeHeight": (NORTH_END_X - DOME_HEIGHT * _MM / 2.0, 0.172),
}
# Ra on the two running faces: the body the 20 hubs rock on, and the north
# journal in its ear. A revolved flank is a drawing SILHOUETTE, not a model
# edge, so the pick names that entity type; straight leaders keep off the
# geometry. The body's rides its top flank, the journal's its underside
# (the lengths stand over the journal).
BEARING_FINISH_EDGE = (PROFILE_CENTER[0] + 0.030, SHAFT_FLANK_Y)
BEARING_FINISH_SYMBOL = (BEARING_FINISH_EDGE[0], 0.206)
JOURNAL_FINISH_EDGE = ((NORTH_END_X + SHOULDER_X[0]) / 2.0, SHAFT_UNDER_Y)
JOURNAL_FINISH_SYMBOL = (JOURNAL_FINISH_EDGE[0] + 0.012, 0.172)


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open pivot-shaft source", await adapter.open_model(str(SOURCE)))
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
            0: "Pivot Shaft Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "pivot shaft; rocker bearing shaft; turned steel",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    profile = place_view(adapter, str(SOURCE), "*Right", *PROFILE_CENTER, scale=(1, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    for view in (profile, iso):
        set_hidden_lines_removed(adapter, view)

    profile_annotations = curate_view_dimensions(
        adapter,
        profile,
        keep=PROFILE_KEEP,
        view_label="profile",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    # Decimal places (and so the general-tolerance row each dimension claims)
    # are authored on the part; the sheet only proves the import kept them.
    assert_imported_precision(adapter, profile_annotations, DRAWING_PRECISION_BY_NAME)
    # #743 PR2: the plain end is cut to fit the installed brackets, so the
    # modelled length prints as a REFERENCE value and the callout under it is
    # the requirement. Keyed on the parametric name.
    length_annotations = [
        annotation
        for annotation in profile_annotations
        if dimension_name(adapter, annotation) == "ShaftLength"
    ]
    if len(length_annotations) != 1:
        raise RuntimeError("profile view does not carry exactly one shaft length")
    set_reference_dimension(adapter, length_annotations[0], label="pivot shaft length")
    set_dimension_callouts(adapter, length_annotations, {"ShaftLength": LENGTH_CALLOUT})
    set_dimension_callouts(adapter, profile_annotations, {"DomeHeight": DOME_CALLOUT})

    # The axis says which pairs of lines are diameters and is what the shop
    # indicates the bar on. The face pick sits mid-body, clear of every
    # placed annotation.
    add_view_centerline(
        adapter,
        profile,
        face_xy=(PROFILE_CENTER[0] - 0.030, PROFILE_CENTER[1]),
        label="pivot shaft axis centerline",
    )
    add_surface_finish(
        adapter,
        profile,
        edge_xy=BEARING_FINISH_EDGE,
        entity_type="SILHOUETTE",
        symbol_xy=BEARING_FINISH_SYMBOL,
        control=surface_finish_by_key(SURFACE_FINISHES, "pivot_bearing"),
        label="pivot bearing finish",
    )
    add_surface_finish(
        adapter,
        profile,
        edge_xy=JOURNAL_FINISH_EDGE,
        entity_type="SILHOUETTE",
        symbol_xy=JOURNAL_FINISH_SYMBOL,
        control=surface_finish_by_key(SURFACE_FINISHES, "pivot_journal"),
        label="pivot journal finish",
    )

    # 0.020: a note is left-aligned on its anchor, so the ink starts here. The
    # bound is the 12.7 mm zone margin (~0.0127); 0.020 clears it, and the
    # audit enforces it.
    add_property_linked_note(adapter, "Manufacturing Notes", 0.020, 0.085)
    add_property_linked_note(adapter, "Isometric View Note", 0.298, 0.118)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Pivot Shaft Manufacturing Drawing",
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
