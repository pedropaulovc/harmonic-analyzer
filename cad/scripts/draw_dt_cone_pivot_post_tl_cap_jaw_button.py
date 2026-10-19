r"""Create the drawing for the cone pivot post's cap jaw button (MHA-DT-05-TL-03)."""

from __future__ import annotations

import argparse
import sys
from typing import Any

from solidworks_mcp.adapters.solidworks.drawing import (
    delete_view,
    dimension_name,
    iter_views,
    place_view,
    view_name,
)

from _check import check
from _drawing_centerline import add_view_centerline
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
)
from _drawing_notes import add_property_linked_note
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_view_display import set_hidden_lines_removed
from _paths import CAD_ROOT
from _session import run_build
import _telemetry
import dt_cone_pivot_post_tl_cap_jaw_button_spec as part_spec
from _feature_requirements import part_metadata, requirement
from _printed_limits import limits
from _gtol_cylinder import CylinderFace
from _gtol_planar import PlanarFace
from dt_cone_pivot_post_tl_cap_jaw_button_spec import (
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    SPIGOT_CALLOUT,
)


SPEC = DRAWINGS_BY_NAME["dt_cone_pivot_post_tl_cap_jaw_button"]
PART_STEM = SPEC.artifact_stem
SOURCE = CAD_ROOT / "out" / "sldprt" / f"{PART_STEM}.SLDPRT"
OUTPUTS = DrawingOutputs(
    slddrw=SPEC.outputs["slddrw"], pdf=SPEC.outputs["pdf"], png=SPEC.outputs["png"]
)
SLDDRW, PDF, PNG = OUTPUTS.slddrw, OUTPUTS.pdf, OUTPUTS.png

# A O16 x 5 button: 4:1 keeps both steps and both diameters legible.
SHEET_SCALE = (4.0, 1.0)
VIEW_SCALE = (4, 1)
# One turned profile (axis horizontal) carries every size: the two axial
# sizes from the faced jaw face, each diameter beside its own step
# (machinist review round 1). The end view only donates the sketch
# diameters and is deleted.
PROFILE_CENTER = (0.140, 0.175)
DONOR_CENTER = (0.055, 0.175)
ISO_CENTER = (0.300, 0.175)
ISO_NOTE_XY = (0.265, 0.235)
PROFILE_KEEP = {
    "FaceThick": (0.136, 0.222),
    "OverallLength": (0.140, 0.238),
}


_AXIS = ([1.0, 0.0, 0.0], ("__frame__",))


part_metadata(precision_sources=("DRAWING_PRECISION_BY_NAME",))

requirement("spigot_end",
    kind="face",
    faces=(PlanarFace((1.0, 0.0, 0.0), part_spec.OVERALL_LENGTH),),
    requirements=("length",),
    fields={
        "normal": ([1.0, 0.0, 0.0], ("__frame__",)),
        "plane": (
            {"frame": "model", "axis": "x", "value": part_spec.OVERALL_LENGTH},
            ("OVERALL_LENGTH",),
        ),
        "length": (limits(part_spec.OVERALL_LENGTH, 1), ("OVERALL_LENGTH",)),
        "length_nominal": (part_spec.OVERALL_LENGTH, ("OVERALL_LENGTH",)),
    },
    precision={"length": 1},
)

requirement("jaw_face",
    kind="face",
    faces=(PlanarFace((-1.0, 0.0, 0.0), 0.0),),
    requirements=("thickness",),
    fields={
        "normal": ([-1.0, 0.0, 0.0], ("__frame__",)),
        "plane": ({"frame": "model", "axis": "x", "value": 0.0}, ("__frame__",)),
        "thickness": (limits(part_spec.FACE_THICK, 1), ("FACE_THICK",)),
    },
    precision={"thickness": 1},
)

DONOR_KEEP = {
    "FaceDia": (0.055, 0.230),
    "SpigotDia": (0.055, 0.120),
}
PROFILE_DIAMETER_XY = {
    "FaceDia": (0.100, 0.175),
    "SpigotDia": (0.180, 0.175),
}


requirement("spigot",
    kind="boss",
    faces=(CylinderFace(part_spec.SPIGOT_DIA),),
    requirements=("dia", "note"),
    fields={
        "at": ([part_spec.FACE_THICK, 0.0, 0.0], ("FACE_THICK",)),
        "axis": _AXIS,
        "dia": (
            limits(part_spec.SPIGOT_DIA, 2, part_spec.SPIGOT_BAND),
            ("SPIGOT_DIA", "SPIGOT_BAND", ("dt_cone_pivot_post_spec", "BORE_DIA"),
             ("dt_cone_pivot_post_spec", "RUNNING_BORE_BAND")),
        ),
        "dia_nominal": (part_spec.SPIGOT_DIA, ("SPIGOT_DIA",)),
        "note": (part_spec.SPIGOT_CALLOUT, ("SPIGOT_CALLOUT", "POST_NUMBER")),
    },
    precision={"dia": 2},
)

requirement("cap_face",
    kind="face",
    faces=(PlanarFace((1.0, 0.0, 0.0), part_spec.FACE_THICK),),
    requirements=("thickness", "dia"),
    fields={
        "normal": ([1.0, 0.0, 0.0], ("__frame__",)),
        "plane": ({"frame": "model", "axis": "x", "value": part_spec.FACE_THICK}, ("FACE_THICK",)),
        "thickness": (limits(part_spec.FACE_THICK, 1), ("FACE_THICK",)),
        "thickness_nominal": (part_spec.FACE_THICK, ("FACE_THICK",)),
        "dia": (
            limits(part_spec.FACE_DIA, part_spec.FACE_PLACES),
            ("FACE_DIA", ("dt_cone_pivot_post_spec", "CONE_BOSS_DIA")),
        ),
        "dia_nominal": (part_spec.FACE_DIA, ("FACE_DIA",)),
    },
    precision={"thickness": 1, "dia": part_spec.FACE_PLACES},
)


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open cap-jaw-button source", await adapter.open_model(str(SOURCE)))
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
    drawing_model, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Cone Post Cap Jaw Button Drawing",
            1: "Harmonic Analyzer shop fixture drawing",
            2: "Harmonic Analyzer Project",
            3: "cone pivot post cap jaw button; turned aluminium; MHA-DT-05-TL-03",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    donor = place_view(adapter, str(SOURCE), "*Right", *DONOR_CENTER, scale=VIEW_SCALE)
    profile = place_view(adapter, str(SOURCE), "*Front", *PROFILE_CENTER, scale=VIEW_SCALE)
    # finalize_drawing shades the pictorial isometric with edges.
    place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=VIEW_SCALE)
    for view in (donor, profile):
        set_hidden_lines_removed(adapter, view)

    donor_annotations = curate_view_dimensions(
        adapter,
        donor,
        keep=DONOR_KEEP,
        view_label="diameter donor",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    profile_annotations = curate_view_dimensions(
        adapter,
        profile,
        keep=PROFILE_KEEP,
        view_label="turned profile",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    diameters = [
        move_model_dimension(
            adapter,
            annotation,
            profile,
            PROFILE_DIAMETER_XY[dimension_name(adapter, annotation)],
            source_view=donor,
        )
        for annotation in donor_annotations
    ]
    donor_name = view_name(adapter, donor)
    delete_view(adapter, donor)
    if any(view_name(adapter, view) == donor_name for view in iter_views(adapter)):
        raise RuntimeError("failed to delete the empty diameter donor view")

    annotations = [*diameters, *profile_annotations]
    # Places (and so each dimension's tolerance) are authored on the part; the
    # sheet only proves the import kept them.
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    # The spigot band's reason (drawing-guidelines.md rule 4 (tighten only for function, and name the mate)): the mate and the acceptance.
    set_dimension_callouts(adapter, diameters, {"SpigotDia": SPIGOT_CALLOUT})
    add_view_centerline(
        adapter, profile, face_xy=PROFILE_CENTER, label="button turning axis"
    )
    add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_XY)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Cone Post Cap Jaw Button Drawing",
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
