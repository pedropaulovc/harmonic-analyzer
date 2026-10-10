"""Two-sheet manufacturing package: custom collar and ground stock screw.

Native model dimensions own every reworked size, its places and its band.
The radial blind tap is a native Hole Wizard callout, including drill and
full-thread depths. Stock screw end/hex geometry is supplied, not reworked.
"""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

import _telemetry
import vn_cone_tip_collar_spec as spec
from _check import check
from _com import _early_bound
from _paths import CAD_ROOT
from _session import run_build
from _drawing_common import (
    DrawingOutputs, PmiDrawingPlacement, _select_view_entity, add_native_hole_callout,
    add_property_linked_note, assert_imported_precision, create_blank_drawing_sheets,
    curate_view_dimensions, dimension_name, finalize_drawing,
    model_point_in_view, new_project_drawing, project_part_pmi,
    read_required_properties, rebuild_drawing,
    set_dimension_callouts, set_hidden_lines_removed,
    set_hole_callout_precision, stamp_drawing_summary, view_name,
    visible_view_entities,
)
import _drawing_hidden_sketches as hidden_sketches
from _gtol_face_read import face_geometry
from _drawing_registry import DRAWINGS_BY_NAME
from _layout_geometry import format_findings
from diagnostics.drawing_layout_audit import audit_document
from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import place_view

SPEC = DRAWINGS_BY_NAME["vn_cone_tip_collar"]
PART_STEM = SPEC.artifact_stem
SOURCE = CAD_ROOT / "out" / "sldprt" / f"{PART_STEM}.SLDPRT"
OUTPUTS = DrawingOutputs(**SPEC.outputs)
SLDDRW = OUTPUTS.slddrw
PDF = OUTPUTS.pdf
PNG = OUTPUTS.png
SHEET_NAMES = ("Collar", "SetScrew")
SHEET_SCALES = {"Collar": (4, 1), "SetScrew": (20, 1)}
END_CENTER = (0.080, 0.170)
SIDE_CENTER = (0.205, 0.170)
# The radial tap view stands over the end view, left of the turning view.
# Over the turning view, at (205, 240) mm, its gauge dimensions crossed the
# top border by 3.2 and 8.8 mm, its note sat on NoseLength's lines, and the
# root gauge and position leaders ran through the hole callout (run 14 at
# 7fda4144f). Offsets below are from TAP_CENTER. The view spans +/-11.5 x
# +/-17.05 mm at 2:1. Run 14 put the tap mouth at (+3.3, +1.8) mm, the callout
# text at [-39, -1] x [-5.6, -2.1] mm from its callout point, the position
# frame's leader start at (-6.3, -3.5) mm from its point, and the view note's
# 62 x 4.3 mm box with its left/top corner at the note point.
TAP_CENTER = (0.065, 0.238)
TAP_SCALE = spec.RADIAL_TAP_VIEW_SCALE
ISO_CENTER = (0.345, 0.210)
END_KEEP = {"NoseDia": (0.027, 0.165), "FlatDistance": (0.080, 0.112)}
# CollarDia is a turned-profile sketch dimension, native to the side view.
SIDE_KEEP = {"CollarWidth": (0.205, 0.110), "CollarDia": (0.250, SIDE_CENTER[1]),
             "NoseLength": (0.182, 0.218), "ShoulderRadius": (0.282, 0.205)}
# TapStation reads under the view, left of datum B (above the end view's top,
# y 204 mm). The two-line TAP ROOT gauge reads level with the tap, left of the
# view; its leader runs straight through the circle.
TAP_KEEP = {
    "TapStation": (TAP_CENTER[0] - 0.021, TAP_CENTER[1] - 0.024),
    "TapRootLimit": (TAP_CENTER[0] - 0.030, TAP_CENTER[1]),
}
# Right of the view: the position frame level with the mouth, the hole
# callout's text 10 mm under it, starting past the view's right edge. The
# view note goes over the view, 3.7 mm inside the top border.
TAP_POSITION_FRAME_XY = (TAP_CENTER[0] + 0.0213, TAP_CENTER[1] + 0.0058)
TAP_CALLOUT_XY = (TAP_CENTER[0] + 0.0553, TAP_CENTER[1] - 0.0062)
TAP_NOTE_XY = (TAP_CENTER[0] - 0.030, TAP_CENTER[1] + 0.025)
# Between the turning view and the isometric, clear of the title block: at
# (350, 80) mm the 40:1 crop circle (radius 20.6 mm) ran 6.6 mm down into it,
# over the title text (run 16 at b760a440c). BoreDia reads up-right, clear
# of CollarDia's lower extension line (y 136 mm, x <= 251); the note under
# the circle, centred on it.
BORE_CENTER = (0.300, 0.110)
BORE_KEEP = {"BoreDia": (BORE_CENTER[0] + 0.035, BORE_CENTER[1] + 0.032)}
BORE_NOTE_XY = (BORE_CENTER[0] - 0.025, BORE_CENTER[1] - 0.026)
# Sheet 2 views are centred on the SCREW, not on the view box: the views are
# placed in Default, whose box holds the collar too, and the SetScrew
# configuration then left the screw 85 mm right of where its view was placed,
# with the end view's hex drawn over the screw's own thread (run 16).
SCREW_SCALE = 20
SCREW_MID_MM = (
    spec.SET_SCREW_SEAT_RADIUS + spec.SET_SCREW_LENGTH / 2.0, spec.TAP_STATION, 0.0,
)
# 15 mm right of run 17's 170 mm, so DogDia's left-hanging text clears the
# left border (see SCREW_KEEP); the side view's right end (264 mm) still
# stands 29 mm off the end view.
SCREW_CENTER = (0.185, 0.190)
SCREW_END_CENTER = (0.315, SCREW_CENTER[1])
# Under the end view, its label under it (59 x 4.3 mm, left/top corner).
SCREW_ISO_CENTER = (0.330, 0.118)
SCREW_ISO_NOTE_XY = (SCREW_ISO_CENTER[0] - 0.0295, SCREW_ISO_CENTER[1] - 0.012)
DOG_LEFT_X = SCREW_CENTER[0] - spec.SET_SCREW_LENGTH * SCREW_SCALE / 2000.0
THREAD_LEFT_X = DOG_LEFT_X + spec.DOG_LENGTH * SCREW_SCALE / 1000.0
# DogDia's text (and the edge callout above it) reads wholly over its upper
# extension line: placed across both (y +/-2 mm) its own dimension line ran
# up through the callout and the value (run 16). Placed there, SolidWorks
# hangs the text LEFT of its dimension line: run 17 read the text 63 mm wide
# ending at the line (box x 7.4 mm for the line at 70.6 mm, 5.3 mm over the
# left border). It cannot read right of the screw: its extension lines would
# cross the thread, and the 29 mm to the end view is narrower than the text.
# So the line stands 12 mm off the dog's free end, the text ending there.
# DogLength reads left of its extension lines, under.
SCREW_KEEP = {
    "DogDia": (DOG_LEFT_X - 0.012, SCREW_CENTER[1] + 0.013),
    "DogLength": (DOG_LEFT_X - 0.020, SCREW_CENTER[1] - 0.040),
}
DATUM_D_XY = (THREAD_LEFT_X + 0.003, SCREW_CENTER[1] + 0.003)
DOG_RUNOUT_XY = (DOG_LEFT_X - 0.040, SCREW_CENTER[1] - 0.027)


def _configuration(adapter, views, name):
    for view in views:
        native = _early_bound(view, "IView")
        native.ReferencedConfiguration = name
        if str(native.ReferencedConfiguration) != name:
            raise RuntimeError(f"view failed to reference {name}")
    rebuild_drawing(adapter, label=f"collar {name} views")


def _printable_above_callouts(callouts: dict[str, str]) -> dict[str, str]:
    """Refuse an above-callout SolidWorks would keep but not print (main's
    draw_pd_transgear_thumbnut guard: a line break in the above compartment
    reads back from COM yet nothing of the callout reaches the PDF)."""
    broken = sorted(name for name, text in callouts.items() if "\n" in text)
    if broken:
        raise RuntimeError(f"above-callouts with a line break do not print: {broken}")
    return callouts


# swViewEntityType_e.swViewEntityType_Face
_VIEW_FACES = 3


def _face_reading(face: Any) -> dict[str, Any]:
    """Owning body, surface identity, area (mm^2) and box (mm) of one face."""
    native = _early_bound(face, "IFace2")
    body = native.GetBody()
    geometry = face_geometry(face)
    return {
        "body": None if body is None else str(_early_bound(body, "IBody2").Name),
        "surface": None if geometry is None else geometry.identity,
        "area_mm2": round(float(native.GetArea()) * 1e6, 4),
        "box_mm": tuple(round(v * 1000.0, 4) for v in (geometry.box if geometry else ())),
    }


def _view_faces(view: Any, specs: dict[str, Any], *, label: str) -> dict[str, Any]:
    """The one face ``view`` draws for each face spec, taken from the view's
    own visible faces (main's draw_dt_cylinder_gear cam-face form).

    A face resolved on the part document and selected into the view read
    back as another face, in Default (4323e8d1e) and again in the view's own
    SetScrew configuration (7924d573e): "datum D pick resolved to a face
    other than the one named"."""
    candidates = [
        geometry
        for face in visible_view_entities(view, _VIEW_FACES, label=label)
        if (geometry := face_geometry(face)) is not None
    ]
    picked = {}
    for key, face_spec in specs.items():
        matches = [geometry for geometry in candidates if face_spec.matches(geometry)]
        if len(matches) != 1:
            listing = [
                (
                    geometry.identity,
                    tuple(round(float(value), 6) for value in geometry.parameters),
                    tuple(round(value * 1000.0, 3) for value in geometry.box),
                )
                for geometry in candidates
            ]
            raise RuntimeError(
                f"{label}: {key} {face_spec!r} matched {len(matches)} of the view's "
                f"{len(candidates)} visible faces; candidates (identity, parameters, "
                f"box mm): {listing}"
            )
        picked[key] = matches[0].face
    return picked


def _log_view_picks(adapter: Any, view: Any, faces: dict[str, Any], *, label: str) -> None:
    """Debug-log each picked face beside what selecting it in ``view`` returns,
    so a pick guard failure names both faces."""
    for key, face in faces.items():
        selected = _select_view_entity(
            adapter, view, "FACE", None, label=f"{label} {key}", entity=face
        )
        _telemetry.debug(
            f"{label} {key}: picked {_face_reading(face)}; the view selects "
            f"{_face_reading(selected)}; IsSame={int(adapter.swApp.IsSame(selected, face))}"
        )
    adapter.currentModel.ClearSelection2(True)


def _horizontal_axis(adapter, view):
    native = _early_bound(view, "IView")
    native.Angle = -math.pi / 2.0
    if abs(float(native.Angle) + math.pi / 2.0) > 1e-9:
        raise RuntimeError("collar axis is not horizontal on the turning view")
    rebuild_drawing(adapter, label="collar turning orientation")


def _precision(keep):
    """The part-authored places of only the names this view keeps
    (main's per-view form, draw_ch_connecting_rod)."""
    return {name: spec.DRAWING_PRECISION_BY_NAME[name] for name in keep}


def _require_full_thread_callout(display):
    """Qualify the native thread-depth variable without typing a thread size."""
    definitions = {part: str(display.GetText(part) or "") for part in (5, 6, 7, 8)}
    thread_parts = [part for part, text in definitions.items() if "<hw-threaddepth>" in text]
    if len(thread_parts) != 1 or not any("<hw-tapdrldepth>" in text for text in definitions.values()):
        raise RuntimeError(f"blind collar tap lost its native depth variables: {definitions!r}")
    part = thread_parts[0]
    updated = definitions[part].rstrip() + " FULL THREAD"
    display.SetText(part - 4, updated)
    if str(display.GetText(part) or "") != updated:
        raise RuntimeError("collar tap full-thread qualifier did not persist")


def _assert_functional_dimension_types(adapter, annotations):
    expected = {"TapStation": 1, "TapRootLimit": 6}  # BASIC / MAX
    observed = {}
    for annotation in annotations:
        name = dimension_name(adapter, annotation)
        if name in expected:
            display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
            dimension = _early_bound(display.GetDimension2(0), "IDimension")
            tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
            observed[name] = int(tolerance.Type)
    if observed != expected:
        raise RuntimeError(f"collar functional location/root limit lost native types: {observed}")


def _centre_view(adapter, view, model_mm, sheet_xy, *, label):
    """Move ``view`` so the model point ``model_mm`` lands on ``sheet_xy``."""
    view = _early_bound(view, "IView")
    model = tuple(value / 1000.0 for value in model_mm)
    at = model_point_in_view(adapter, view, model, label=label)
    position = tuple(float(value) for value in view.Position)
    if not view.SetViewPosition(double_array([
        position[i] + sheet_xy[i] - at[i] for i in range(2)
    ]), False):
        raise RuntimeError(f"cannot centre {label}")
    rebuild_drawing(adapter, label=f"{label} position")
    at = model_point_in_view(adapter, view, model, label=f"{label} readback")
    if math.dist(at, sheet_xy) > 1e-4:
        raise RuntimeError(f"{label} did not remain centred")


def _bore_view(adapter):
    """Native circular crop, using the existing cone/arbor drawing sequence."""
    view = _early_bound(place_view(
        adapter, str(SOURCE), "*Bottom", *BORE_CENTER, scale=spec.BORE_VIEW_SCALE,
    ), "IView")
    _configuration(adapter, (view,), "Collar")
    if tuple(float(value) for value in view.ScaleRatio) != tuple(spec.BORE_VIEW_SCALE):
        raise RuntimeError("collar bore view lost its source scale")
    _centre_view(adapter, view, (0.0, 0.0, 0.0), BORE_CENTER, label="collar bore axis")
    draw = adapter.currentModel
    if not _early_bound(draw, "IDrawingDoc").ActivateView(view_name(adapter, view)):
        raise RuntimeError("cannot activate collar bore crop")
    before = tuple(float(value) for value in view.GetOutline())
    sketch = _early_bound(view.GetSketch(), "ISketch")
    transform = _early_bound(sketch.ModelToSketchTransform, "IMathTransform")
    utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    radius = spec.BORE_FINISHED_DIA_LIMITS_MM[1] * spec.BORE_VIEW_SCALE[0] / (
        2000.0 * spec.BORE_VIEW_SCALE[1]
    ) + 0.003
    points = []
    for x, y in (BORE_CENTER, (BORE_CENTER[0] + radius, BORE_CENTER[1])):
        point = _early_bound(utility.CreatePoint(double_array([x, y, 0.0])), "IMathPoint")
        projected = _early_bound(point.MultiplyTransform(transform), "IMathPoint")
        points.append(tuple(float(value) for value in projected.ArrayData))
    manager = _early_bound(draw.SketchManager, "ISketchManager")
    previous = bool(manager.AddToDB)
    manager.AddToDB = False
    try:
        circle = manager.CreateCircle(*points[0], *points[1])
    finally:
        manager.AddToDB = previous
    if circle is None:
        raise RuntimeError("cannot sketch collar bore crop circle")
    status = int(view.Crop2(False, False, 1))
    draw.ClearSelection2(True)
    rebuild_drawing(adapter, label="collar bore crop")
    view.UpdateViewDisplayGeometry()
    after = tuple(float(value) for value in view.GetOutline())
    if status != 1 or not view.IsCropped():
        raise RuntimeError(f"collar bore crop failed: {status}")
    if len(before) != 4 or len(after) != 4 or after[2] - after[0] >= before[2] - before[0]:
        raise RuntimeError("collar bore crop did not reduce the native outline")
    if bool(view.CropViewJaggedOutline) or bool(view.CropViewNoOutline):
        raise RuntimeError("collar bore crop lost its plain circle boundary")
    set_hidden_lines_removed(adapter, view)
    marks = curate_view_dimensions(
        adapter, view, keep=BORE_KEEP, view_label="collar enlarged bore",
        dimensions_by_feature=spec.DRAWING_DIMENSIONS,
    )
    assert_imported_precision(adapter, marks, _precision(BORE_KEEP))
    set_dimension_callouts(adapter, marks, {"BoreDia": "REAM THRU"})
    add_property_linked_note(adapter, "Bore View Note", *BORE_NOTE_XY)
    return view


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part missing: {SOURCE}")
    check("open custom collar", await adapter.open_model(str(SOURCE)))
    read_required_properties(adapter.currentModel, (
        "Number", "Revision", "Title", "Material Specification", "Finish",
        "Quantity", "Manufacturing Notes", "Isometric View Note", "Radial Tap View Note",
        "Bore View Note", "Installation Notes",
    ), required=("Number", "Material Specification", "Manufacturing Notes",
                 "Radial Tap View Note", "Bore View Note", "Installation Notes"))
    drawing, _sheet = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALES["Collar"], layout=SPEC.layout,
    )
    create_blank_drawing_sheets(adapter, SHEET_NAMES, label="custom cone collar package")
    stamp_drawing_summary(adapter, drawing, {
        0: "Cone Tip Collar Manufacturing Drawing", 1: "Harmonic Analyzer hobby-machinist drawing",
        2: "Harmonic Analyzer Project", 3: "Custom steel collar and reworked stock set screw",
        4: "Project-owned ASME B drawing standard",
    })
    ddoc = _early_bound(drawing, "IDrawingDoc")
    if not ddoc.ActivateSheet("Collar"):
        raise RuntimeError("cannot activate collar sheet")
    end = place_view(adapter, str(SOURCE), "*Bottom", *END_CENTER, scale=(4, 1))
    side = place_view(adapter, str(SOURCE), "*Front", *SIDE_CENTER, scale=(4, 1))
    tap = place_view(adapter, str(SOURCE), "*Right", *TAP_CENTER, scale=TAP_SCALE)
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=(2, 1))
    _configuration(adapter, (end, side, tap, iso), "Collar")
    _horizontal_axis(adapter, side)
    _horizontal_axis(adapter, tap)
    for view in (end, side, tap, iso):
        set_hidden_lines_removed(adapter, view)
    end_marks = curate_view_dimensions(adapter, end, keep=END_KEEP,
                                      view_label="collar end", dimensions_by_feature=spec.DRAWING_DIMENSIONS)
    side_marks = curate_view_dimensions(adapter, side, keep=SIDE_KEEP,
                                       view_label="collar turning view", dimensions_by_feature=spec.DRAWING_DIMENSIONS)
    marks = end_marks + side_marks
    assert_imported_precision(adapter, marks, _precision(END_KEEP | SIDE_KEEP))
    # TapRootGauge is a blanked sketch: main's hidden-owner importer shows it
    # in this view for the import (draw_ch_rocker_arm_tl_pivot_screw).
    tap_marks = hidden_sketches.curate_view_dimensions(
        adapter, tap, keep=TAP_KEEP, view_label="collar radial process controls",
        dimensions_by_feature=spec.DRAWING_DIMENSIONS,
    )
    assert_imported_precision(adapter, tap_marks, _precision(TAP_KEEP))
    _assert_functional_dimension_types(adapter, tap_marks)
    set_dimension_callouts(adapter, tap_marks, {"TapRootLimit": "TAP ROOT"})
    # Source geometry is asymmetric and the views are rotated: use the native
    # model-to-sheet transform rather than assuming the view's box centre is
    # the bore origin or that world +Y still projects vertically.
    def point(view, xyz_mm, label):
        return model_point_in_view(
            adapter, view, tuple(value / 1000.0 for value in xyz_mm), label=label,
        )

    tap_rim = point(
        tap, (spec.FLAT_DISTANCE, spec.TAP_STATION, spec.TAP_DRILL_DIA / 2.0),
        "collar tap outer mouth",
    )
    project_part_pmi(
        adapter,
        placements={
            "datum:A": PmiDrawingPlacement(
                view=end, position=(0.120, 0.210),
                attachment_xy=point(end, (spec.BORE_MODEL_DIA_MM / 2.0, 1.0, 0.0), "collar bore datum"),
            ),
            "datum:B": PmiDrawingPlacement(
                view=side, position=(0.168, 0.162),
                attachment_xy=point(side, (0.0, 0.0, spec.NOSE_DIA / 2.0 - spec.EDGE_BREAK), "collar south datum"),
            ),
            "datum:C": PmiDrawingPlacement(
                view=end, position=(0.126, 0.152),
                attachment_xy=point(end, (spec.FLAT_DISTANCE, spec.TAP_STATION, 0.0), "collar clock datum"),
            ),
            "radial_tap_position": PmiDrawingPlacement(
                view=tap, position=TAP_POSITION_FRAME_XY, attachment_xy=tap_rim,
            ),
        },
        datums=spec.COLLAR_DATUMS, controls=spec.COLLAR_CONTROLS,
        label="collar retained dog and wall position",
    )
    # In the radial projection the tap mouth is a real circle on the flat.
    callout = add_native_hole_callout(
        adapter, tap,
        edge_xy=tap_rim,
        callout_xy=TAP_CALLOUT_XY, label="custom collar blind set screw tap",
    )
    set_hole_callout_precision(callout, {
        "hw-tapdrldepth": spec.TAP_DEPTH_PRECISION,
        "hw-threaddepth": spec.TAP_DEPTH_PRECISION,
    }, label="collar tap drill and full thread depths")
    _require_full_thread_callout(callout)
    add_property_linked_note(adapter, "Manufacturing Notes", 0.016, 0.080)
    add_property_linked_note(adapter, "Installation Notes", 0.016, 0.048)
    add_property_linked_note(adapter, "Isometric View Note", 0.310, 0.160)
    add_property_linked_note(adapter, "Radial Tap View Note", *TAP_NOTE_XY)
    _bore_view(adapter)

    if not ddoc.ActivateSheet("SetScrew"):
        raise RuntimeError("cannot activate ground screw sheet")
    screw = place_view(adapter, str(SOURCE), "*Front", *SCREW_CENTER, scale=(SCREW_SCALE, 1))
    screw_end = place_view(
        adapter, str(SOURCE), "*Right", *SCREW_END_CENTER, scale=(SCREW_SCALE, 1),
    )
    screw_iso = place_view(adapter, str(SOURCE), "*Isometric", *SCREW_ISO_CENTER, scale=(2, 1))
    _configuration(adapter, (screw, screw_end, screw_iso), "SetScrew")
    for view, centre, name in (
        (screw, SCREW_CENTER, "ground screw side view"),
        (screw_end, SCREW_END_CENTER, "ground screw end view"),
        (screw_iso, SCREW_ISO_CENTER, "ground screw isometric"),
    ):
        _centre_view(adapter, view, SCREW_MID_MM, centre, label=name)
        set_hidden_lines_removed(adapter, view)
    marks = curate_view_dimensions(adapter, screw, keep=SCREW_KEEP,
                                  view_label="ground stock screw", dimensions_by_feature=spec.DRAWING_DIMENSIONS)
    assert_imported_precision(adapter, marks, _precision(SCREW_KEEP))
    # Above the value: the freed lane where the old break dimension stood.
    set_dimension_callouts(
        adapter, marks, _printable_above_callouts({"DogDia": spec.DOG_EDGE_CALLOUT}),
        location="above",
    )
    # The major and dog diameters draw as a revolve's flank SILHOUETTES, not
    # model edges, so an EDGE pick at their projected points misses (farm run
    # at a0defd137: "failed to select ... datum:D edge at sheet (0.219831,
    # 0.221844)"). Attach to the FACE (main's draw_dt_pinion_cam_pin form),
    # taken from the faces the view draws; the projected point stays as the
    # frame's leader landing.
    screw_faces = _view_faces(
        screw,
        {
            **{datum.key: datum.face for datum in spec.SCREW_DATUMS},
            **{control.key: control.face for control in spec.SCREW_CONTROLS},
        },
        label="ground stock screw faces",
    )
    _log_view_picks(adapter, screw, screw_faces, label="ground stock screw")
    project_part_pmi(
        adapter,
        placements={
            "datum:D": PmiDrawingPlacement(
                view=screw, position=DATUM_D_XY,
                entity=screw_faces["datum:D"], attachment_type="FACE",
            ),
            "ground_dog_runout": PmiDrawingPlacement(
                view=screw, position=DOG_RUNOUT_XY,
                entity=screw_faces["ground_dog_runout"], attachment_type="FACE",
                # Mid-length, half a radius off the axis: inside the dog
                # face's projection, not on its silhouette, where a
                # landing could re-solve onto the neighbouring flank.
                leader_attachment_xy=point(
                    screw,
                    (spec.SET_SCREW_SEAT_RADIUS + spec.DOG_LENGTH / 2.0,
                     spec.TAP_STATION + spec.DOG_DIA / 4.0, 0.0),
                    "ground dog runout face",
                ),
            ),
        },
        datums=spec.SCREW_DATUMS, controls=spec.SCREW_CONTROLS,
        label="ground dog relative to retained stock thread",
    )
    add_property_linked_note(adapter, "Manufacturing Notes", 0.016, 0.080)
    add_property_linked_note(adapter, "Isometric View Note", *SCREW_ISO_NOTE_XY)
    for sheet in SHEET_NAMES:
        if not ddoc.ActivateSheet(sheet):
            raise RuntimeError(f"cannot audit collar package sheet {sheet}")
        rebuild_drawing(adapter, label=f"collar {sheet} layout audit")
        findings = audit_document(adapter)
        if findings:
            raise RuntimeError("collar manufacturing layout:\n" + format_findings(findings))
    return await finalize_drawing(
        adapter, OUTPUTS, pdf_title="Cone Tip Collar Manufacturing Drawing",
        scale=SHEET_SCALES["Collar"], layout=SPEC.layout, sheet_scales=SHEET_SCALES,
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
