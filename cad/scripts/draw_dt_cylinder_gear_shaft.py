r"""Create the curated machinist drawing for the cylinder-gear arbor."""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

from solidworks_mcp.adapters.pywin32_adapter import null_callout
from solidworks_mcp.adapters.solidworks.drawing import (
    delete_view,
    dimension_name,
    iter_views,
    place_view,
    view_name,
)

from _check import check
from _com import _early_bound
from _drawing_centerline import add_view_centerline
from _drawing_common import (
    DrawingOutputs,
    finalize_drawing,
    new_project_drawing,
    read_required_properties,
    stamp_drawing_summary,
)
from _drawing_dimensions import (
    assert_imported_precision,
    set_dimension_callouts,
    set_reference_dimension,
)
from _drawing_finish import add_surface_finish
from _drawing_hidden_sketches import curate_view_dimensions
from _drawing_notes import add_property_linked_note
from _drawing_registry import DRAWINGS_BY_NAME
from _drawing_view_display import set_hidden_lines_removed
from _machinist_review_mode import MachinistReviewMode
from _part_properties import part_drawing_unit
from _paths import CAD_ROOT
from _session import run_build
from _surface_finish import surface_finish_by_key
import _telemetry
from cylinder_bank_layout import ARBOR_DOME_HEIGHT, ARBOR_LENGTH
from dt_cylinder_gear_shaft_spec import (
    DOME_CALLOUT,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    LENGTH_CALLOUT,
    SHAFT_DIA,
    SHAFT_DIA_CALLOUT,
    SHAFT_RADIUS,
    SURFACE_FINISHES,
)

# The model's spherical radius (build_dt_cylinder_gear_shaft.DOME_SPHERE_RADIUS):
# a cap of the dome height on the bar's radius.
DOME_SPHERE_RADIUS = (SHAFT_RADIUS**2 + ARBOR_DOME_HEIGHT**2) / (
    2.0 * ARBOR_DOME_HEIGHT
)


# Cached machinist review leaf: a FIX or ERROR verdict fails the build.
MACHINIST_REVIEW = MachinistReviewMode.ENFORCE

SPEC = DRAWINGS_BY_NAME["dt_cylinder_gear_shaft"]
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
# One orthographic view: a plain rod is fully defined by its side view plus a
# diameter, and drawing-guidelines.md rule 11 (turned parts read like the lathe) puts that diameter ON the side view.  The arbor is
# modelled axis-along-+Y (its assembly pose), so the side view is "*Front"
# rotated -90 deg (IView.Angle) -- axis horizontal, as the bar sits in the
# lathe.  An end view would carry nothing but the diameter it is not allowed to
# keep, so this sheet has none.
PROFILE_CENTER = (0.140, 0.190)
PROFILE_ROTATION = -math.pi / 2.0  # model +Y (arbor axis) -> sheet +x
SHAFT_FLANK_Y = PROFILE_CENTER[1] + SHAFT_DIA * SHEET_SCALE[0] / 2000.0
# The view centres on the bar's bounding box, domes included, so the cylinder
# (ARBOR_LENGTH, the span over both straps) is centred too.
SHAFT_LEFT_X = PROFILE_CENTER[0] - ARBOR_LENGTH * SHEET_SCALE[0] / 2000.0
SHAFT_RIGHT_X = PROFILE_CENTER[0] + ARBOR_LENGTH * SHEET_SCALE[0] / 2000.0
# The 168 shaft's isometric silhouette is a mostly-VERTICAL slender bar (~0.153
# m long at 1:1 -- taller than the drawable band), so the pictorial renders at
# 1:2 and says so in its own note.
ISO_CENTER = (0.330, 0.175)
ISO_SCALE = (1, 2)
# A circle sketch's diameter only imports into a view that FACES the circle, so
# it arrives in a temporary "*Top" donor and is then MOVED (never copied) onto
# the side view, which is where a turned part's diameters belong.  The donor
# then carries no manufacturing information and is deleted.  Pattern and
# verification from draw_pinion_handle (its grip/tube diameters make the same
# trip); a farm leaf of draw_cone_gear_shaft re-proved it on a stepped shaft.
DONOR_CENTER = (0.355, 0.248)
DONOR_KEEP = {"ShaftDia": (0.392, DONOR_CENTER[1])}
PROFILE_DIAMETERS = {"ShaftDia": (0.196, 0.222)}
# A short dimension's callout is far wider than the span it measures, so its
# text stands OUTSIDE the witness pair, clear of both lines, and the dimension
# line runs out under it: centred over the dome, both witnesses ran into
# "BOTH ENDS" (r1 machinist review), as on draw_ch_pivot_shaft's dome.
# Callout text runs ~2.75 mm a character at the template's dimension height.
CALLOUT_CHAR_WIDTH = 0.00275
CALLOUT_WITNESS_GAP = 0.003
DOME_TIP_X = SHAFT_RIGHT_X + ARBOR_DOME_HEIGHT * SHEET_SCALE[0] / 1000.0
# The sphere's centre sits on the axis, inside the bar.
DOME_CENTRE_X = DOME_TIP_X - DOME_SPHERE_RADIUS * SHEET_SCALE[0] / 1000.0
# A radial dimension's line runs from the sphere's centre to the LEFT end of
# the text's underline (the leader shoulder under "BOTH ENDS"), not to the
# text position: on the r4 render (keep (0.2500, 0.1780)) the shoulder began
# 14.15 mm left of and 5.5 mm below it, so the line ran out at ~40 deg below
# the axis, past the dome's rim, and its arrow sat on the length's witness
# (r4 machinist review). The keep below puts the shoulder on the line from
# the centre at ~17 deg, mid-way down the dome's lower arc (which spans ~35
# deg from the axis to the rim).
RADIUS_SHOULDER_OFFSET = (-0.01415, -0.0055)
DOME_RADIUS_LEADER_DEG = 17.0
_SHOULDER_X = DOME_TIP_X + 0.020
_SHOULDER_Y = PROFILE_CENTER[1] - (_SHOULDER_X - DOME_CENTRE_X) * math.tan(
    math.radians(DOME_RADIUS_LEADER_DEG)
)

PROFILE_KEEP = {
    "Depth": (PROFILE_CENTER[0], 0.158),
    # Over the north (right-hand) dome, above the bar and right of the tip's
    # witness: a short .X height the "BOTH ENDS" callout makes a 2X statement.
    "DomeHeight": (
        DOME_TIP_X + CALLOUT_WITNESS_GAP + len(DOME_CALLOUT) * CALLOUT_CHAR_WIDTH / 2.0,
        0.206,
    ),
    # Right of the same dome, level with the bar's lower half: the leader
    # runs from the shoulder toward the sphere's centre.
    "DomeRadius": (
        _SHOULDER_X - RADIUS_SHOULDER_OFFSET[0],
        _SHOULDER_Y - RADIUS_SHOULDER_OFFSET[1],
    ),
}
# Ra on the one running surface: the O.D. the 20 cylinder gears turn on and
# both pedestals journal.  A revolved/extruded flank is a drawing SILHOUETTE,
# not a model edge, so the pick names that entity type.
# A straight-up leader (same x as the pick) keeps it off the geometry, as on
# draw_pivot_shaft's identical O.D. flank; the Ra text renders above the arm.
FINISH_EDGE = (SHAFT_LEFT_X + 0.038, SHAFT_FLANK_Y)
FINISH_SYMBOL = (FINISH_EDGE[0], 0.206)
# Note text height, as on draw_ch_pivot_shaft's identical O.D. symbol: at the
# template default the Ra text printed ~8 mm tall over the bar (r2 render).
FINISH_CHAR_HEIGHT = 0.0025


def _rotate_view(adapter: Any, view: Any, angle: float, *, label: str) -> None:
    """Rotate a placed drawing view about its center and verify it took."""
    ok = adapter._attempt(lambda: setattr(view, "Angle", float(angle)), default=False)
    if ok is False:
        raise RuntimeError(f"failed to rotate {label} drawing view")
    adapter.currentModel.EditRebuild3()
    applied = float(adapter._get_attr_or_call(view, "Angle") or 0.0)
    if abs(math.remainder(applied - angle, 2.0 * math.pi)) > 1e-6:
        raise RuntimeError(
            f"{label} view rotation did not take: {applied:g} rad, expected {angle:g}"
        )


def _move_dimension(
    adapter: Any,
    annotation: Any,
    target: Any,
    text_xy: tuple[float, float],
    *,
    source_view: Any,
) -> Any:
    """Move, never copy, a fitted model dimension and verify its new owner."""
    name = dimension_name(adapter, annotation)
    draw = adapter.currentModel
    ddoc = _early_bound(draw, "IDrawingDoc")
    if not ddoc.ActivateView(view_name(adapter, source_view)):
        raise RuntimeError(f"{name}: failed to activate source dimension view")
    draw.ClearSelection2(True)
    display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
    selection_name = str(display.GetNameForSelection() or "")
    if not selection_name or not draw.Extension.SelectByID2(
        selection_name, "DIMENSION", 0.0, 0.0, 0.0, False, 0, null_callout(), 0
    ):
        raise RuntimeError(
            f"failed to select model dimension {name}: {selection_name!r}"
        )
    ddoc.DragModelDimension(view_name(adapter, target), 2, text_xy[0], text_xy[1], 0.0)
    draw.ClearSelection2(True)
    draw.EditRebuild3()
    annotations = [
        _early_bound(item, "IAnnotation")
        for item in (_early_bound(target, "IView").GetAnnotations() or ())
    ]
    matches = [item for item in annotations if dimension_name(adapter, item) == name]
    if len(matches) != 1:
        raise RuntimeError(f"{name}: native dimension did not move into target view")
    return matches[0]


def _set_spherical_reference(adapter: Any, annotation: Any, *, label: str) -> None:
    """Print the dome's model radius as the ASME spherical reference ``(SR.32)``.

    The radius is read-only: a spherical cap of the printed dome height on the
    toleranced diameter already fixes it. Whatever radius prefix the display
    carries is kept behind the ``(S``; the readback proves it stuck (the
    MHA-CH-05 pivot shaft's and MHA-DT-01 crankshaft's domes print the same
    way).
    """
    annotation = _early_bound(annotation, "IAnnotation")
    display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
    existing = str(display.GetText(1) or "")  # swDimensionTextPrefix
    prefix = "(S" + existing
    display.SetText(1, prefix)
    display.SetText(2, ")")  # swDimensionTextSuffix
    applied = (str(display.GetText(1) or ""), str(display.GetText(2) or ""))
    _telemetry.info(
        f"{label}: spherical reference prefix {existing!r} -> {applied[0]!r}, "
        f"suffix {applied[1]!r}"
    )
    if applied != (prefix, ")"):
        raise RuntimeError(
            f"failed to mark {label} as a spherical reference: {applied}"
        )


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open cylinder-gear-shaft source", await adapter.open_model(str(SOURCE)))
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
        unit=part_drawing_unit("dt-cylinder-gear-shaft"),
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Cylinder Gear Shaft Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "cylinder gear shaft; stationary arbor; turned steel",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    profile = place_view(adapter, str(SOURCE), "*Front", *PROFILE_CENTER, scale=(1, 1))
    donor = place_view(adapter, str(SOURCE), "*Top", *DONOR_CENTER, scale=(1, 1))
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    # Rotate BEFORE dimension import so the Depth dim lands on the displayed
    # (horizontal) geometry.
    _rotate_view(adapter, profile, PROFILE_ROTATION, label="profile")
    for view in (profile, iso):
        set_hidden_lines_removed(adapter, view)

    # Donor first: its diameter must exist before it can be re-homed, and the
    # side view's own import then answers for nothing but the length.
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
        view_label="profile",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    for annotation in donor_annotations:
        name = dimension_name(adapter, annotation)
        profile_annotations.append(
            _move_dimension(
                adapter,
                annotation,
                profile,
                PROFILE_DIAMETERS[name],
                source_view=donor,
            )
        )
    donor_name = view_name(adapter, donor)
    # The vendor helper currently casts void EditDelete() to false. Verify
    # deletion against the native sheet view collection, not that return value.
    delete_view(adapter, donor)
    if any(view_name(adapter, view) == donor_name for view in iter_views(adapter)):
        raise RuntimeError("failed to delete the empty diameter-donor view")
    # Decimal places (and so the general-tolerance row each dimension claims)
    # are authored on the part; the sheet only proves the import kept them.
    assert_imported_precision(adapter, profile_annotations, DRAWING_PRECISION_BY_NAME)
    # U34b: the arbor is cut to fit between the installed pedestals, so the
    # modelled length prints as a REFERENCE value and the callout under it is
    # the requirement. Keyed on the parametric name, like every other lookup.
    length_annotations = [
        annotation
        for annotation in profile_annotations
        if dimension_name(adapter, annotation) == "Depth"
    ]
    if len(length_annotations) != 1:
        raise RuntimeError("profile view does not carry exactly one arbor length")
    set_reference_dimension(adapter, length_annotations[0], label="arbor length")
    set_dimension_callouts(adapter, length_annotations, {"Depth": LENGTH_CALLOUT})
    set_dimension_callouts(
        adapter,
        profile_annotations,
        {"DomeHeight": DOME_CALLOUT, "DomeRadius": DOME_CALLOUT},
    )
    radius_annotations = [
        annotation
        for annotation in profile_annotations
        if dimension_name(adapter, annotation) == "DomeRadius"
    ]
    if len(radius_annotations) != 1:
        raise RuntimeError("profile view does not carry exactly one dome radius")
    _set_spherical_reference(adapter, radius_annotations[0], label="arbor dome radius")
    # Above the value: the Ø's dimension line runs down to the bar, so the
    # below lane would sit on it.
    set_dimension_callouts(
        adapter, profile_annotations, {"ShaftDia": SHAFT_DIA_CALLOUT}, location="above"
    )

    # A bare rectangle does not say which pair of lines is the O.D.; the axis
    # does, and it is what the shop indicates the bar on.  The face pick sits
    # left of the diameter's witness line, clear of every placed annotation.
    add_view_centerline(
        adapter,
        profile,
        face_xy=(PROFILE_CENTER[0] - 0.040, PROFILE_CENTER[1]),
        label="arbor axis centerline",
    )
    add_surface_finish(
        adapter,
        profile,
        edge_xy=FINISH_EDGE,
        entity_type="SILHOUETTE",
        symbol_xy=FINISH_SYMBOL,
        control=surface_finish_by_key(SURFACE_FINISHES, "arbor_bearing"),
        label="arbor bearing finish",
        char_height=FINISH_CHAR_HEIGHT,
    )

    # 0.020: a note is left-aligned on its anchor, so the ink starts here. The
    # bound is the 12.7 mm zone margin (~0.0127), which the re-centred border
    # rule now matches (~0.0126); 0.020 clears both, and the audit enforces it.
    add_property_linked_note(adapter, "Manufacturing Notes", 0.020, 0.085)
    add_property_linked_note(adapter, "Isometric View Note", 0.298, 0.118)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Cylinder Gear Shaft Manufacturing Drawing",
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
