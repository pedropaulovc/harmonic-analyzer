r"""Create the manufacturing drawing for the transgear disc hub (MHA-159).

The edge view is the ``*Top`` orientation turned a quarter turn so the hub's
axis lies horizontal, as it sits in the lathe (policy rule 7): the hub front
face on the left, the flange and the spigot on the right.  It carries the
turned profile: the three diameters beside their steps, the spigot's and
flange's lengths from the flange's rear face, the overall (spigot end to hub
front) as a reference under its faced-to-fit callout (set at the
paper-drive assembly's hub-facing step), and the flange's rear face and the
spigot's end square to the bore, datum A.  Looking down on +Y it sees the
radial oil hole end-on, so it also carries the hole's size and its
match-drill callout.  The face view is the ``*Back`` orientation (looking at
the hub front) turned to match -- exactly the third-angle LEFT view of that
profile -- so it sits on the profile's axis to its left and carries the
bore (datum A) with its flat and the screw holes on their printed bolt
circle.
"""

from __future__ import annotations

import argparse
import math
import sys
from dataclasses import dataclass
from typing import Any

import _telemetry
from _common import CAD_ROOT, _early_bound, check, run_build
from _drawing_common import (
    DrawingOutputs,
    ViewEdge,
    ViewEdges,
    add_feature_control_frame,
    add_property_linked_note,
    assert_imported_precision,
    curate_view_dimensions,
    dimension_name,
    finalize_drawing,
    model_points_in_view,
    new_project_drawing,
    read_required_properties,
    scan_view_edges,
    set_dimension_callouts,
    set_hidden_lines_removed,
    set_reference_dimension,
    stamp_drawing_summary,
)
from _drawing_registry import DRAWINGS_BY_NAME
from _gear_drawing_entities import visible_circle_edge
from _native_axis_datum import add_native_axis_datum
from paper_drive_assembly_steps import step_ref
from transgear_disc_hub_spec import (
    BORE_DATUM,
    BORE_DIA,
    BOSS_CLEARANCE_LIMITS,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    FLANGE_DIA,
    FLANGE_THICK,
    FLAT_CLEARANCE,
    GEOMETRIC_TOLERANCES_MM,
    HUB_FRONT_Z,
    HUB_LENGTH_CALLOUT,
    OIL_HOLE_CALLOUT_BELOW,
    SCREW_HOLE_CALLOUT_ABOVE,
    SCREW_HOLE_CALLOUT_BELOW,
    SLEEVE_NAME,
    SLEEVE_NUMBER,
    SPIGOT_CALLOUT_BELOW,
    SPIGOT_DIA,
    SPIGOT_LENGTH,
)
from solidworks_mcp.adapters.solidworks.drawing import (
    auto_center_marks,
    place_view,
)


SPEC = DRAWINGS_BY_NAME["transgear_disc_hub"]
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

# A Ø25.1 × 13.70 part: 3:1 keeps the #0-80 holes, the Ø1.2 oil hole and the
# thin flange legible with two views across the landscape sheet.
SHEET_SCALE = (3.0, 1.0)
VIEW_SCALE = (3, 1)
_S = SHEET_SCALE[0] / SHEET_SCALE[1] / 1000.0  # sheet metres per model mm
# *Top turned +90 degrees: model -Z (the hub front) to paper-left, model +X
# up.  *Back turned -90 degrees: model +X up, model +Y (the oil hole) right,
# which is the third-angle left view of that profile.
SIDE_VIEW_ANGLE = math.pi / 2.0
END_VIEW_ANGLE = -math.pi / 2.0
AXIS_Y = 0.165
SIDE_CENTER = (0.225, AXIS_Y)
END_CENTER = (0.090, AXIS_Y)
# Above the flange's diameter, the edge view's outermost dimension, and
# right of its extension lines.
ISO_CENTER = (0.374, 0.216)
NOTES_XY = (0.020, 0.062)


def _side_x(z_mm: float) -> float:
    """Sheet X of a model-Z station on the edge view (the view centres on the
    part's z span, HUB_FRONT_Z..SPIGOT_LENGTH)."""
    return SIDE_CENTER[0] + (z_mm - (HUB_FRONT_Z + SPIGOT_LENGTH) / 2.0) * _S


HUB_FRONT_X = _side_x(HUB_FRONT_Z)
SPIGOT_END_X = _side_x(SPIGOT_LENGTH)
_FLANGE_R = FLANGE_DIA / 2.0 * _S
_SPIGOT_R = SPIGOT_DIA / 2.0 * _S

# Faced to fit at MHA-A06's hub step; the pointer comes from the step
# registry.
FIT_STEP_KEY = "hub-faced-to-nose"

# The D-bore's two native bands set its fits; each callout adds extent and
# the mating feature by name and number with the clearance the pair gives
# (this spec computes both).  No process word: a reamer
# would cut away the flat, and the dimensions define the D-profile (the
# crank drive gear's D-bore wording).
BORE_CALLOUT = "\n".join(
    (
        "THRU",
        f"(DIA CLR {BOSS_CLEARANCE_LIMITS[0]:.3f}-{BOSS_CLEARANCE_LIMITS[1]:.3f}",
        f"ON {SLEEVE_NAME}",
        f"{SLEEVE_NUMBER} BOSS)",
    )
)
FLAT_CALLOUT = "\n".join(
    (
        "BORE FLAT",
        f"(CLR {FLAT_CLEARANCE[0]:.3f}-{FLAT_CLEARANCE[1]:.3f}",
        f"ON {SLEEVE_NAME}",
        f"{SLEEVE_NUMBER} FLAT)",
    )
)

# Every size and callout sits outside the silhouettes.
# - Face view: the bolt circle diameter above-left, the screw-hole size (3X,
#   drilled through the flange) above-right, the flat's distance below-left
#   (the flat's side, so its dimension line stays clear of the bore's
#   leader) and the bore below-right, each with its fit callout under it.
# - Edge view: the hub's diameter inline left of the hub front face; the
#   spigot's and then the flange's inline right of the spigot's end, the
#   flange's outermost so the spigot's extension lines end inside it, the
#   spigot's callout under its text, clear of the part.  The two lengths
#   from the flange's rear face on one row above: the flange's text left of
#   the flange, the spigot's right of the spigot.  The overall, a reference
#   faced at assembly, on the next row up, outermost, its text and fit-up
#   callout right of the spigot end's extension line.  Its ends are the
#   spigot's and the hub's +X corners, so from a row above its extension
#   lines rise off the part; from below they ran down across the hub front
#   and the spigot end, under the spigot end frame's leader.  The oil hole's
#   size with its match-drill callout above-left, over the gap between the
#   two views, its text ending left of the overall's hub-front extension
#   line.
# - The two perpendicularity frames stand right of the spigot's end, inside
#   the flange's extension lines: the flange's below the spigot, its leader
#   level onto the rear face's lower half; the spigot end's above the
#   spigot's extension line, its leader on the end's upper half.
END_KEEP = {
    "BoltCircleDia": (END_CENTER[0] - 0.030, AXIS_Y + _FLANGE_R + 0.016),
    "ScrewHoleDia": (END_CENTER[0] + 0.036, AXIS_Y + _FLANGE_R + 0.016),
    "BoreDia": (END_CENTER[0] + 0.030, AXIS_Y - _FLANGE_R - 0.020),
    "FlatToAxis": (END_CENTER[0] - 0.030, AXIS_Y - _FLANGE_R - 0.020),
}
SIDE_KEEP = {
    "HubDia": (HUB_FRONT_X - 0.014, AXIS_Y),
    "SpigotDia": (SPIGOT_END_X + 0.036, AXIS_Y),
    "FlangeDia": (SPIGOT_END_X + 0.077, AXIS_Y),
    "FlangeThick": (_side_x(-FLANGE_THICK) - 0.014, AXIS_Y + _FLANGE_R + 0.008),
    "SpigotLength": (SPIGOT_END_X + 0.012, AXIS_Y + _FLANGE_R + 0.008),
    "HubLength": (SPIGOT_END_X + 0.040, AXIS_Y + _FLANGE_R + 0.024),
    "OilHoleDia": (HUB_FRONT_X - 0.052, AXIS_Y + _FLANGE_R + 0.040),
}
DIMENSION_CALLOUTS_BELOW = {
    "BoreDia": BORE_CALLOUT,
    "FlatToAxis": FLAT_CALLOUT,
    "ScrewHoleDia": SCREW_HOLE_CALLOUT_BELOW,
    "OilHoleDia": OIL_HOLE_CALLOUT_BELOW,
    "SpigotDia": SPIGOT_CALLOUT_BELOW,
    "HubLength": f"{HUB_LENGTH_CALLOUT},\nPER {step_ref(FIT_STEP_KEY)}",
}
DIMENSION_CALLOUTS_ABOVE = {"ScrewHoleDia": SCREW_HOLE_CALLOUT_ABOVE}

# The two perpendicularity frames attach by entity, not by a sheet pick.  A
# face seen edge-on draws as its outer rim, a circle on the hub's axis (model
# Z) whose projection is the face's line; SelectByID2 on such a line found no
# edge here twice (runs 20261002T153039266Z and 20261002T160324403Z, sheet x
# 0.2346 above and below the axis), as it once did on the crankshaft's
# collar rim (run 20261001T035353825Z).  Each frame names its rim by model
# geometry, which the scan must match exactly once, and its leader lands on
# the rim's projected line at a model x, placed between the projected ends
# at run time.
# - Flange rear face, z 0, rim r 12.55: its line spans r 6.55-12.55 each side
#   of the axis.  On +X the 0-degree screw hole's edge on the face projects
#   across r 8.65-10.35 (BC 9.50 +/- 0.85) and the spigot length's extension
#   line rises from the spigot's +X corner along the whole stretch; on -X the
#   120- and 240-degree holes project at r 3.90-5.60, behind the spigot.  The
#   leader lands at x -9.55, mid-stretch, 3.00 (9.0 on the sheet) from
#   either corner.
# - Spigot end, z 3.65, rim r 6.55: its bore is round (the D-flat ends at
#   z 0) and its edge overlays r < 4.50; the leader lands at x +5.525, midway
#   along r 4.50-6.55, 1.025 (3.1 on the sheet) from either end.  The
#   spigot's length and the overall end at its +X corner and print above, so
#   their extension lines rise off the line.
# Each frame stands right of the spigot's end on its landing's side of the
# axis (model +X up: *Top's +X right, turned +90 degrees), centred in the
# band between the spigot's and the flange's extension lines.


@dataclass(frozen=True)
class RimFrame:
    """A perpendicularity frame on a face the edge view shows edge-on: the
    face's outer rim (model z and radius, mm, centred on the hub axis), the
    model x its leader lands at on the rim's line, and the frame's sheet
    position (metres)."""

    label: str
    rim_z_mm: float
    rim_radius_mm: float
    landing_x_mm: float
    frame_xy: tuple[float, float]


_BAND_DY = (_SPIGOT_R + _FLANGE_R) / 2.0
FLANGE_FACE_FRAME = RimFrame(
    label="flange rear face perpendicularity",
    rim_z_mm=0.0,
    rim_radius_mm=FLANGE_DIA / 2.0,
    landing_x_mm=-(SPIGOT_DIA + FLANGE_DIA) / 4.0,
    frame_xy=(SPIGOT_END_X + 0.010, AXIS_Y - _BAND_DY),
)
SPIGOT_END_FRAME = RimFrame(
    label="spigot end perpendicularity",
    rim_z_mm=SPIGOT_LENGTH,
    rim_radius_mm=SPIGOT_DIA / 2.0,
    landing_x_mm=(BORE_DIA + SPIGOT_DIA) / 4.0,
    frame_xy=(SPIGOT_END_X + 0.010, AXIS_Y + _BAND_DY),
)
# A rim matches within these of its modelled centre and radius (the part is
# built to the spec's sizes), its axis along the hub's.
_RIM_CENTER_TOL_MM = 1e-4
_RIM_RADIUS_TOL_MM = 1e-4
_HUB_AXIS = (0.0, 0.0, 1.0)
# Seen edge-on, a rim's +Y point projects onto its line's midpoint; the
# projection is exact to ~1e-9 m.
_EDGE_ON_TOL_M = 1e-6


def face_rim(edges: ViewEdges, frame: RimFrame) -> ViewEdge:
    """The one visible circle on the hub axis at ``frame``'s rim station and
    radius; none or several raise, listing every circle the scan holds."""
    centre = (0.0, 0.0, frame.rim_z_mm)

    def is_rim(circle: tuple[float, ...]) -> bool:
        offset = sum(abs(a - b) for a, b in zip(circle[:3], centre))
        tilt = 1.0 - abs(sum(a * b for a, b in zip(circle[3:6], _HUB_AXIS)))
        return (
            offset <= _RIM_CENTER_TOL_MM
            and abs(circle[6] - frame.rim_radius_mm) <= _RIM_RADIUS_TOL_MM
            and tilt <= 1e-6
        )

    matches = [item for item in edges.circles if is_rim(item.circle)]
    if len(matches) != 1:
        candidates = "; ".join(
            "r {6:.4f} at ({0:.4f}, {1:.4f}, {2:.4f}) axis ({3:.3f}, {4:.3f}, {5:.3f})".format(
                *item.circle
            )
            for item in edges.circles
        )
        raise RuntimeError(
            f"{frame.label}: expected one visible rim r {frame.rim_radius_mm:g} mm "
            f"at z {frame.rim_z_mm:g} mm on the hub axis in the {edges.label!r} "
            f"scan, matched {len(matches)} of {len(edges.circles)} circles: "
            f"{candidates or 'none'}"
        )
    return matches[0]


def rim_landing(
    frame: RimFrame,
    minus_end: tuple[float, float],
    plus_end: tuple[float, float],
) -> tuple[float, float]:
    """Where ``frame``'s leader lands: its model x along the rim's projected
    line, from the rim's -X end to its +X end (sheet metres)."""
    t = (frame.landing_x_mm + frame.rim_radius_mm) / (2.0 * frame.rim_radius_mm)
    return (
        minus_end[0] + t * (plus_end[0] - minus_end[0]),
        minus_end[1] + t * (plus_end[1] - minus_end[1]),
    )


def _rim_attachment(
    adapter: Any, view: Any, edges: ViewEdges, frame: RimFrame
) -> tuple[Any, tuple[float, float]]:
    """``frame``'s rim edge and its leader's landing, projected from the rim
    at run time; logs where the rim's line lies on the sheet."""
    rim = face_rim(edges, frame)
    r_m, z_m = frame.rim_radius_mm / 1000.0, frame.rim_z_mm / 1000.0
    minus_end, plus_end, side_point = model_points_in_view(
        adapter,
        view,
        ((-r_m, 0.0, z_m), (r_m, 0.0, z_m), (0.0, r_m, z_m)),
        label=f"{frame.label} rim",
        names=("-X end", "+X end", "+Y point"),
    )
    middle = ((minus_end[0] + plus_end[0]) / 2.0, (minus_end[1] + plus_end[1]) / 2.0)
    if math.dist(side_point, middle) > _EDGE_ON_TOL_M:
        raise RuntimeError(
            f"{frame.label}: the rim is not edge-on in the edge view: its +Y "
            f"point projects to {side_point}, its line's midpoint is {middle}"
        )
    landing = rim_landing(frame, minus_end, plus_end)
    _telemetry.info(
        f"{frame.label} rim projects from ({minus_end[0]:.5f}, {minus_end[1]:.5f}) "
        f"at -X to ({plus_end[0]:.5f}, {plus_end[1]:.5f}) at +X; leader lands at "
        f"({landing[0]:.5f}, {landing[1]:.5f}); the layout puts the face at sheet "
        f"x {_side_x(frame.rim_z_mm):.5f}"
    )
    return rim.edge, landing


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open disc-hub source", await adapter.open_model(str(SOURCE)))
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
            0: "Transgear Disc Hub Manufacturing Drawing",
            1: "Harmonic Analyzer hobby-machinist book drawing",
            2: "Harmonic Analyzer Project",
            3: "transgear disc hub; turned brass hub and flange",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    end = place_view(adapter, str(SOURCE), "*Back", *END_CENTER, scale=VIEW_SCALE)
    side = place_view(adapter, str(SOURCE), "*Top", *SIDE_CENTER, scale=VIEW_SCALE)
    for view, angle, label in (
        (end, END_VIEW_ANGLE, "face view"),
        (side, SIDE_VIEW_ANGLE, "edge view"),
    ):
        native = _early_bound(view, "IView")
        native.Angle = angle
        if abs(math.remainder(float(native.Angle) - angle, 2.0 * math.pi)) > 1e-9:
            raise RuntimeError(f"failed to rotate the disc-hub {label}")
    drawing_model.EditRebuild3()
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=VIEW_SCALE)
    for view in (end, side, iso):
        set_hidden_lines_removed(adapter, view)

    end_annotations = curate_view_dimensions(
        adapter,
        end,
        keep=END_KEEP,
        view_label="face",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    side_annotations = curate_view_dimensions(
        adapter,
        side,
        keep=SIDE_KEEP,
        view_label="edge",
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )
    annotations = [*end_annotations, *side_annotations]
    # Decimal places (and so the general-tolerance row each dimension claims)
    # are authored on the part; the sheet only proves the import kept them.
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    # Faced to fit at assembly: the modelled overall prints as a REFERENCE
    # value and the callout under it is the requirement; the blank it is
    # faced from is the Manufacturing Notes' make-to size.
    length_annotations = [
        annotation
        for annotation in side_annotations
        if dimension_name(adapter, annotation) == "HubLength"
    ]
    if len(length_annotations) != 1:
        raise RuntimeError("edge view does not carry exactly one hub overall")
    set_reference_dimension(adapter, length_annotations[0], label="hub overall")
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS_BELOW)
    set_dimension_callouts(
        adapter, annotations, DIMENSION_CALLOUTS_ABOVE, location="above"
    )
    for view, label in ((end, "face"), (side, "edge")):
        if not auto_center_marks(adapter, view, holes=True, size=0.0025):
            raise RuntimeError(
                f"failed to add ASME center marks to the hub {label} view"
            )
    # Datum A, the bore, on the face view where it shows round; the view has
    # no datum tag yet, as the native placement requires.
    add_native_axis_datum(
        adapter,
        end,
        entity=visible_circle_edge(adapter, end, BORE_DIA),
        source_path=SOURCE,
        radius_m=BORE_DIA / 2000.0,
        datum=BORE_DATUM,
        label="hub bore axis",
        shoulder=True,
        stability_tolerance_m=0.0001,
    )
    side_edges = scan_view_edges(side, label="hub edge view rims")
    for frame, key in (
        (FLANGE_FACE_FRAME, "flange rear face perpendicularity to bore"),
        (SPIGOT_END_FRAME, "spigot end perpendicularity to bore"),
    ):
        rim, landing = _rim_attachment(adapter, side, side_edges, frame)
        add_feature_control_frame(
            adapter,
            side,
            edge_entity=rim,
            leader_attach_xy=landing,
            frame_xy=frame.frame_xy,
            characteristic="perpendicularity",
            tolerance=GEOMETRIC_TOLERANCES_MM[key],
            datums=(BORE_DATUM,),
            label=frame.label,
        )
    # Re-assert the display mode now the last annotation has landed: an
    # annotation attached after placement can leave a view's edge set
    # unregenerated, and only a real mode change rebuilds it.
    for view in (end, side):
        set_hidden_lines_removed(adapter, view)
    add_property_linked_note(adapter, "Manufacturing Notes", *NOTES_XY)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Transgear Disc Hub Manufacturing Drawing",
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
