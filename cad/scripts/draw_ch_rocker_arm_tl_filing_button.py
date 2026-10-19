r"""Create the drawing for the rocker arm hub filing button (MHA-CH-06-TL-04)."""

from __future__ import annotations

import argparse
import sys
from typing import Any

from solidworks_mcp.adapters.solidworks.drawing import (
    dimension_name,
    place_view,
)

from _check import check
from _com import _early_bound
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    stamp_drawing_summary,
)
from _drawing_dimension_import import curate_view_dimensions
from _drawing_dimensions import (
    assert_imported_precision,
    move_model_dimension,
    set_dimension_callouts,
    set_reference_dimension,
)
from _drawing_leader_notes import add_attached_note
from _drawing_finish import add_surface_finish
from _drawing_notes import add_property_linked_note
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_view_display import set_hidden_lines_removed
from _paths import CAD_ROOT
from _session import run_build
from _surface_finish import surface_finish_by_key
import _telemetry
import ch_rocker_arm_tl_filing_button_spec as part_spec
from _feature_requirements import part_metadata, requirement
from _printed_limits import limits
from _gtol_cylinder import CylinderFace
from _gtol_planar import PlanarFace
from ch_rocker_arm_tl_filing_button_spec import (
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    OD_CALLOUT,
    OD_RUNOUT_CALLOUT,
    REFERENCE_CALLOUTS,
    REFERENCE_DIMENSIONS,
    RIM_CORNER_NOTE,
    SURFACE_FINISHES,
    THICKNESS_CALLOUT,
)


SPEC = DRAWINGS_BY_NAME["ch_rocker_arm_tl_filing_button"]
PART_STEM = SPEC.artifact_stem
SOURCE = CAD_ROOT / "out" / "sldprt" / f"{PART_STEM}.SLDPRT"
OUTPUTS = DrawingOutputs(
    slddrw=SPEC.outputs["slddrw"], pdf=SPEC.outputs["pdf"], png=SPEC.outputs["png"]
)
SLDDRW, PDF, PNG = OUTPUTS.slddrw, OUTPUTS.pdf, OUTPUTS.png

# A O10.2 x 4 washer-like button. Codex rounds 4-5: two diameters in the
# face view cross at the centre, and a bore sized on the edge view ends on
# hidden lines. So the face view keeps only the bore (seen true there), and
# the O.D. moves onto the edge view (rule b) beside the thickness. A section
# cannot host them: the diameters belong to the profile circle, and a moved
# circle diameter does not land in a section (run 20261007T173820652Z).
SHEET_SCALE = (4.0, 1.0)
VIEW_SCALE = (4, 1)
FACE_CENTER = (0.110, 0.180)
EDGE_CENTER = (0.200, 0.180)
ISO_CENTER = (0.310, 0.180)
ISO_NOTE_XY = (0.275, 0.240)
NOTES_XY = (0.020, 0.075)
FACE_KEEP = {
    "DiscDia": (0.165, 0.115),  # donor spot only
    # Centred over the face view so the whole fit callout sits inside the
    # border (codex: at x 0.060 its opening words left the sheet).
    "BoreDia": (0.115, 0.240),
}
# Right of the edge view: the O.D.'s mate callout is wider than the gap
# between the two views, and the isometric stands clear further right.
EDGE_XY = {"DiscDia": (0.245, 0.180)}
# The rim note leads to the face view's outer circle at lower left, clear of
# the bore leader (upper left) and the bore finish symbol (lower right).
RIM_PICK = (FACE_CENTER[0] - 0.0144, FACE_CENTER[1] - 0.0144)
RIM_NOTE_XY = (0.025, 0.145)

# The template centre-marks the bore as the face view is placed, so the
# explicit AutoInsertCenterMarks2 printed a second, identical mark over it
# (round-4 layout audit: DetailItem347/349 at one point; round 6: the view
# arrived marked; draw_sm_knife_mount #913). The sheet adds none; it proves
# the one.
_CENTER_MARK_ANNOTATION = 13  # swAnnotationType_e.swCenterMarkSym


def _prove_one_bore_mark(view: Any) -> None:
    marks = (
        _early_bound(view, "IView").GetAnnotationsByType(_CENTER_MARK_ANNOTATION) or ()
    )
    if len(marks) != 1:
        raise RuntimeError(f"expected one button-bore centre mark, found {len(marks)}")


_AXIS = ([0.0, 0.0, 1.0], ("__frame__",))


part_metadata(precision_sources=("DRAWING_PRECISION_BY_NAME", ("_surface_finish", "ra")))

requirement("rim",
    kind="boss",
    faces=(CylinderFace(part_spec.OD),),
    requirements=("dia",),
    fields={
        "at": ([0.0, 0.0, 0.0], ("__frame__",)),
        "axis": _AXIS,
        "dia": (
            limits(part_spec.OD, part_spec.OD_PLACES),
            ("OD", "OD_PLACES", ("ch_rocker_arm_spec", "HUB_DIA")),
        ),
        "dia_nominal": (part_spec.OD, ("OD", ("ch_rocker_arm_spec", "HUB_DIA"))),
    },
    precision={"dia": part_spec.OD_PLACES},
)

requirement("bore",
    kind="hole",
    faces=(CylinderFace(part_spec.BORE_DIA),),
    requirements=("note", "thru", "finish_ra"),
    fields={
        "at": ([0.0, 0.0, 0.0], ("__frame__",)),
        "axis": _AXIS,
        "dia_nominal": (part_spec.BORE_DIA, ("BORE_DIA",)),
        "thru": (True, (("draw_ch_rocker_arm_tl_filing_button", "build"),)),
        "note": (part_spec.BORE_FIT_NOTE, ("BORE_FIT_NOTE",)),
        "finish_ra": (part_spec.MACHINED_UM, ("SURFACE_FINISHES",)),
    },
    precision={"finish_ra": 1},
)

# Close above the edge view, under the bore's fit callout: the thickness's
# mate callout stands above its value, so the dimension line runs under the
# value and clear of the callout (Claude review: below the value, the line
# struck the callout).
EDGE_KEEP = {
    "DiscThick": (0.200, 0.218),
}


requirement("hub_seat_face",
    kind="face",
    faces=(PlanarFace((0.0, 0.0, -1.0), 0.0),),
    requirements=("thickness",),
    fields={
        "normal": ([0.0, 0.0, -1.0], ("__frame__",)),
        "plane": ({"frame": "model", "axis": "z", "value": 0.0}, ("__frame__",)),
        "thickness": (limits(part_spec.THICKNESS, part_spec.THICKNESS_PLACES), ("THICKNESS",)),
        "thickness_nominal": (part_spec.THICKNESS, ("THICKNESS",)),
    },
    precision={"thickness": part_spec.THICKNESS_PLACES},
)

requirement("outer_face",
    kind="face",
    faces=(PlanarFace((0.0, 0.0, 1.0), part_spec.THICKNESS),),
    requirements=("thickness",),
    fields={
        "normal": ([0.0, 0.0, 1.0], ("__frame__",)),
        "plane": (
            {"frame": "model", "axis": "z", "value": part_spec.THICKNESS},
            ("THICKNESS",),
        ),
        "thickness": (limits(part_spec.THICKNESS, part_spec.THICKNESS_PLACES), ("THICKNESS",)),
    },
    precision={"thickness": part_spec.THICKNESS_PLACES},
)



async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open filing-button source", await adapter.open_model(str(SOURCE)))
    required = (
        "Number",
        "Material Specification",
        "Finish",
        "Quantity",
        "Manufacturing Notes",
        "Isometric View Note",
    )
    read_required_properties(
        adapter.currentModel, ("Revision", "Title", *required), required=required
    )
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Rocker Arm Hub Filing Button Drawing",
            1: "Harmonic Analyzer shop fixture drawing",
            2: "Harmonic Analyzer Project",
            3: "rocker arm hub filing button; hardened lapped O1; MHA-CH-06-TL-04",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    face = place_view(adapter, str(SOURCE), "*Front", *FACE_CENTER, scale=VIEW_SCALE)
    edge = place_view(adapter, str(SOURCE), "*Right", *EDGE_CENTER, scale=VIEW_SCALE)
    # finalize_drawing shades the pictorial isometric with edges.
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=VIEW_SCALE)
    for view in (face, edge, iso):
        set_hidden_lines_removed(adapter, view)

    annotations = []
    for annotation in curate_view_dimensions(
        adapter,
        face,
        keep=FACE_KEEP,
        view_label="face view",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    ):
        name = dimension_name(adapter, annotation)
        if name in EDGE_XY:
            annotation = move_model_dimension(
                adapter, annotation, edge, EDGE_XY[name], source_view=face
            )
        annotations.append(annotation)
    annotations += curate_view_dimensions(
        adapter,
        edge,
        keep=EDGE_KEEP,
        view_label="edge view",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    # Lower right on the bore circle, past the end of the bore dimension's
    # diameter line (Claude review: at 45 degrees the two arrows met there)
    # and clear of the vertical centre mark.
    bore_pick = (FACE_CENTER[0] + 0.00445, FACE_CENTER[1] - 0.01223)
    add_surface_finish(
        adapter,
        face,
        edge_xy=bore_pick,
        symbol_xy=(0.150, 0.130),
        leader_attach_xy=bore_pick,
        control=surface_finish_by_key(SURFACE_FINISHES, "bore"),
        label="filing button bore finish",
    )
    _prove_one_bore_mark(face)
    for name in sorted(REFERENCE_DIMENSIONS):
        matches = [a for a in annotations if dimension_name(adapter, a) == name]
        if len(matches) != 1:
            raise RuntimeError(f"expected one filing-button {name} reference dimension")
        display = set_reference_dimension(
            adapter,
            matches[0],
            label=f"filing button {name}",
            diameter=name.endswith("Dia"),
        )
        # drawing-guidelines.md rule 4 (tighten only for function, and name the mate) and drawing-guidelines.md rule 7 (notes: few, flagged, never a method): the matched fit rides the callout.
        for part, text in zip((3, 4), REFERENCE_CALLOUTS.get(name, ())):
            if text:  # swDimensionTextCalloutAbove / CalloutBelow
                display.SetText(part, text)
                if str(display.GetText(part) or "") != text:
                    raise RuntimeError(f"filing button {name} fit callout did not take")
    # Places (and so each dimension's tolerance) are authored on the part; the
    # sheet only proves the import kept them.
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    set_dimension_callouts(
        adapter, annotations, {"DiscDia": OD_CALLOUT}, location="below"
    )
    set_dimension_callouts(
        adapter,
        annotations,
        {"DiscDia": OD_RUNOUT_CALLOUT, "DiscThick": THICKNESS_CALLOUT},
        location="above",
    )
    add_attached_note(
        adapter,
        face,
        text=RIM_CORNER_NOTE,
        entity_xy=RIM_PICK,
        note_xy=RIM_NOTE_XY,
        label="filing button rim corner note",
    )
    add_property_linked_note(adapter, "Manufacturing Notes", *NOTES_XY)
    add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_XY)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Rocker Arm Hub Filing Button Drawing",
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
