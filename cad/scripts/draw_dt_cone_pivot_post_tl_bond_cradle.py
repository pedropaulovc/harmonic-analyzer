r"""Create the drawing for the cone pivot post's bond cradle (MHA-DT-005-TL-01)."""

from __future__ import annotations

import argparse
import math
import sys
from typing import Any

import _telemetry
from _common import CAD_ROOT, _early_bound, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_property_linked_note,
    add_surface_finish,
    assert_imported_precision,
    create_section_view,
    finalize_drawing,
    model_point_in_view,
    new_project_drawing,
    read_required_properties,
    rebuild_drawing,
    set_dimension_callouts,
    set_hidden_lines_removed,
    stamp_drawing_summary,
    visible_view_entities,
)
from _drawing_hidden_sketches import curate_view_dimensions, part_sketches_shown
from _drawing_leaders import set_near_side_diameter
from _drawing_registry import DRAWINGS_BY_NAME
from _part_pmi import _face_geometry, _face_matches
from _surface_finish import surface_finish_by_key
from dt_cone_pivot_post_tl_bond_cradle_spec import (
    BODY_SADDLE_THICK,
    BODY_SADDLE_Y,
    CONE_PIN_NEAR_Y,
    DRAWING_DIMENSIONS,
    DRAWING_PRECISION_BY_NAME,
    SECTION_REFERENCE_SKETCHES,
    SURFACE_FINISHES,
    TAIL_SADDLE_Y,
    TAIL_SECTION_Y,
)
from solidworks_mcp.adapters.solidworks.drawing import dimension_name, place_view

SPEC = DRAWINGS_BY_NAME["dt_cone_pivot_post_tl_bond_cradle"]
PART_STEM = SPEC.artifact_stem
SOURCE = CAD_ROOT / "out" / "sldprt" / f"{PART_STEM}.SLDPRT"
OUTPUTS = DrawingOutputs(
    slddrw=SPEC.outputs["slddrw"], pdf=SPEC.outputs["pdf"], png=SPEC.outputs["png"]
)
SLDDRW, PDF, PNG = OUTPUTS.slddrw, OUTPUTS.pdf, OUTPUTS.png

# A 134 x 80 x 25 block: 1:1 fits plan, elevation and two sections on a B
# sheet; the pictorial goes 1:2 and says so in its note.
SHEET_SCALE = (1.0, 1.0)
VIEW_SCALE = (1, 1)
ISO_SCALE = (1, 2)
# Plan ("*Front", looking down -Z) and elevation ("*Right") are both turned
# so the post axis (+Y) runs left to right from foot B; the elevation sits
# under the plan, third-angle, with +Z up. Both sections are cut on the
# elevation: A-A through the near cone pin looks back at the body saddle
# (-Y), B-B between the crank pins and the tail saddle looks on to the tail
# saddle (+Y), so each shows one seat alone, on a saddle face it does not cut.
PLAN_CENTER = (0.115, 0.196)
ELEVATION_CENTER = (0.115, 0.096)
SECTION_A_CENTER = (0.252, 0.130)
SECTION_B_CENTER = (0.372, 0.130)
ISO_CENTER = (0.360, 0.228)
ISO_NOTE_XY = (0.232, 0.250)
NOTES_XY = (0.020, 0.062)
# Cutting lines run from just above the saddle tops to just below the base.
CUT_TOP_Z = -9.0
CUT_FOOT_Z = -43.0
# The section captions drop clear of the tilt under A-A.
CAPTION_DROP = 0.018
# Seat finish symbols stand outboard of the seat on the model's +X side
# (X, Z in mm), under the plan's dimensions and inside the sheet border;
# their leaders land on the arc 38 degrees off its bottom, clear of the
# diameter leader, the saddle-top corner and the cone pin.
SEAT_FINISH_SYMBOL = {"body_seat": (32.0, -6.0), "tail_seat": (24.0, 8.0)}
SEAT_FINISH_LANDING_DEG = 38.0

# Dimension text positions as MODEL points (mm); each view projects its own
# after it is placed and turned. Stations print from foot B, heights from
# the base top, transverse locations from the base's west side (X -40; the
# plan's top edge).
PLAN_KEEP = {
    "StopWidth": (0.0, -30.0, 0.0),
    "StopSideX": (-28.0, -21.0, 0.0),
    # The tail saddle's side offset, the saddle width, crank pin spots and
    # base width stack as baselines off the west edge, outside the base's
    # right end.
    "SaddleSideX": (-35.0, 128.0, 0.0),
    "SaddleWidth": (0.0, 136.0, 0.0),
    "CrankPinWestX": (-23.0, 144.0, 0.0),
    "CrankPinEastX": (-17.0, 152.0, 0.0),
    "BaseWidth": (0.0, 160.0, 0.0),
    "ConePinNearY": (-48.0, 14.0, 0.0),
    "ConePinFarY": (-56.0, 19.0, 0.0),
    "CrankPinY": (-64.0, 36.0, 0.0),
    "CrankPinDia": (-52.0, 100.0, 0.0),
}
ELEVATION_KEEP = {
    "BaseLength": (0.0, 55.0, -50.0),
    "BaseThick": (0.0, -22.0, -35.0),
    "StopHeight": (0.0, -22.0, -22.0),
    "StopThick": (0.0, -6.0, 6.0),
    "BodySaddleThick": (0.0, 15.0, 6.0),
    "TailSaddleThick": (0.0, 110.0, 6.0),
    # The saddle stations stack as baselines off foot B, one row each.
    "BodySaddleY": (0.0, 5.0, 15.0),
    "TailSaddleY": (0.0, 50.0, 24.0),
    # In the gap between the foot stop and the body saddle, outside the
    # silhouette and beside the saddle it measures.
    "BodySaddleHeight": (0.0, 5.0, -22.0),
    # Above the silhouette, beside the crank pin on its foot-B side.
    "CrankPinHeight": (0.0, 64.0, -4.0),
    "TailSaddleHeight": (0.0, 130.0, -22.0),
}
# Each seat's profile sketch is parallel to its section, so the section
# imports its diameter.
SECTION_A_KEEP = {
    # Outside the part, above the saddle top on the -X side, between the
    # 30.0's axis extension line and the saddle: the near-side leader meets
    # the seat's circle 70 degrees off its bottom, and a short arc extension
    # carries the seat up to it from the saddle-top corner (run-13 review:
    # the callout sat inside the saddle).
    "BodySeatDia": (-28.0, CONE_PIN_NEAR_Y, -10.0),
    "BodySeatAxisX": (-20.0, CONE_PIN_NEAR_Y, 12.0),
    "BodySeatAxisHeight": (-48.0, CONE_PIN_NEAR_Y, -12.0),
    # Under the base; the tilt reads below it.
    "ConePinEntryX": (-28.0, CONE_PIN_NEAR_Y, -48.0),
    # Under the base, outside the acute wedge on the gauge line's +X side,
    # 33 mm from the hole entry: the inclined pin-axis line and the 33.34
    # stay clear of the text (run-13 review); the caption drops clear of it
    # (CAPTION_DROP).
    "ConePinTilt": (7.5, CONE_PIN_NEAR_Y, -61.0),
    "ConePinHighEdge": (-58.0, CONE_PIN_NEAR_Y, -25.0),
}
SECTION_B_KEEP = {
    "TailSeatDia": (12.0, TAIL_SECTION_Y, 28.0),
    "TailSeatAxisX": (-20.0, TAIL_SECTION_Y, 12.0),
    "TailSeatAxisHeight": (-48.0, TAIL_SECTION_Y, -12.0),
}
DIMENSION_CALLOUTS = {
    "CrankPinDia": "4X DOWEL",
    "SaddleWidth": "2X",
    "SaddleSideX": "2X",
    "ConePinEntryX": "2X",
    "ConePinTilt": "2X",
    "ConePinHighEdge": "2X",
}


def _sheet(adapter: Any, view: Any, xyz_mm: tuple[float, float, float], label: str) -> tuple[float, float]:
    return model_point_in_view(
        adapter, view, tuple(v / 1000.0 for v in xyz_mm), label=label
    )


def _direction(adapter: Any, view: Any, axis: tuple[float, float, float], label: str) -> tuple[float, float]:
    """Sheet direction of a model axis in ``view``."""
    origin = _sheet(adapter, view, (0.0, 0.0, 0.0), f"{label} origin")
    tip = _sheet(adapter, view, axis, f"{label} axis")
    return tip[0] - origin[0], tip[1] - origin[1]


def _turn(
    adapter: Any,
    view: Any,
    axis: tuple[float, float, float],
    sheet_angle: float,
    *,
    label: str,
) -> None:
    """Turn ``view`` about its centre until model ``axis`` points along
    ``sheet_angle`` (radians, counter-clockwise from sheet +x)."""
    native = _early_bound(view, "IView")
    dx, dy = _direction(adapter, native, axis, label)
    angle = float(native.Angle) + sheet_angle - math.atan2(dy, dx)
    native.Angle = angle
    adapter.currentModel.EditRebuild3()
    dx, dy = _direction(adapter, native, axis, label)
    if abs(math.remainder(math.atan2(dy, dx) - sheet_angle, 2.0 * math.pi)) > 1e-6:
        raise RuntimeError(f"{label}: model {axis} points {math.atan2(dy, dx):g} rad after the turn")


def _require_up(adapter: Any, view: Any, *, label: str) -> None:
    dx, dy = _direction(adapter, view, (0.0, 0.0, 1.0), label)
    if dy <= 0.0 or abs(dx) > 1e-9:
        raise RuntimeError(f"{label}: model +Z is not sheet-up ({dx:g}, {dy:g})")


def _orient_section(adapter: Any, section: Any, *, x_right: bool, label: str) -> None:
    """Turn a section +Z up and make it look the intended way along the post.

    Looking down -Y with +Z up puts model -X on the sheet's right; looking
    down +Y puts +X there. A section that looks the wrong way has its cut
    direction reversed, then is turned again.
    """
    native = _early_bound(section, "IView")
    _turn(adapter, native, (0.0, 0.0, 1.0), math.pi / 2.0, label=label)
    dx, _ = _direction(adapter, native, (1.0, 0.0, 0.0), label)
    if (dx > 0.0) != x_right:
        drawing_section = _early_bound(native.GetSection(), "IDrSection")
        reversed_cut = not bool(drawing_section.GetReversedCutDirection())
        drawing_section.SetReversedCutDirection(reversed_cut)
        rebuild_drawing(adapter, label=f"reverse {label}")
        if bool(drawing_section.GetReversedCutDirection()) != reversed_cut:
            raise RuntimeError(f"{label}: cutting direction did not persist")
        _turn(adapter, native, (0.0, 0.0, 1.0), math.pi / 2.0, label=label)
        dx, _ = _direction(adapter, native, (1.0, 0.0, 0.0), label)
        if (dx > 0.0) != x_right:
            raise RuntimeError(f"{label}: still looks the wrong way after reversing")
    _require_up(adapter, native, label=label)


def _cut(
    adapter: Any,
    elevation: Any,
    y: float,
    *,
    center: tuple[float, float],
    letter: str,
    x_right: bool,
    label: str,
) -> Any:
    section = create_section_view(
        adapter,
        elevation,
        line_start=_sheet(adapter, elevation, (0.0, y, CUT_TOP_Z), f"{label} line top"),
        line_end=_sheet(adapter, elevation, (0.0, y, CUT_FOOT_Z), f"{label} line foot"),
        view_xy=center,
        section_label=letter,
        scale=VIEW_SCALE,
        label=label,
    )
    _orient_section(adapter, section, x_right=x_right, label=label)
    set_hidden_lines_removed(adapter, section)
    return section


def _keep(adapter: Any, view: Any, points: dict[str, tuple[float, float, float]], label: str) -> dict[str, tuple[float, float]]:
    return {name: _sheet(adapter, view, xyz, f"{label} {name}") for name, xyz in points.items()}


def _curate(adapter: Any, view: Any, points: dict[str, tuple[float, float, float]], label: str) -> list[Any]:
    return curate_view_dimensions(
        adapter,
        view,
        keep=_keep(adapter, view, points, label),
        view_label=label,
        dimensions_by_feature=DRAWING_DIMENSIONS,
    )


def _seat_finish(adapter: Any, view: Any, key: str, face_y: float, *, label: str) -> Any:
    """Hang a seat's finish symbol on its arc in a section.

    Each section looks on to a saddle face it does not cut, so the seat's
    arc there is a model edge of the seat face; the seat's straight edges
    along the post run end-on and drop out by their equal X.
    """
    control = surface_finish_by_key(SURFACE_FINISHES, key)
    arcs = []
    for raw in visible_view_entities(view, 1, label=f"{label} seat edges"):
        edge = _early_bound(raw, "IEdge")
        start, end = edge.GetStartVertex(), edge.GetEndVertex()
        if start is None or end is None:
            continue
        p0 = _early_bound(start, "IVertex").GetPoint()
        p1 = _early_bound(end, "IVertex").GetPoint()
        if abs(float(p0[0]) - float(p1[0])) * 1000.0 < 1.0:
            continue
        for face in edge.GetTwoAdjacentFaces2() or ():
            geometry = None if face is None else _face_geometry(face)
            if geometry is not None and _face_matches(geometry, control.face):
                arcs.append(raw)
                break
    if len(arcs) != 1:
        raise RuntimeError(f"{label}: expected one visible {key} arc, found {len(arcs)}")
    radius = control.face.diameter_mm / 2.0
    angle = math.radians(SEAT_FINISH_LANDING_DEG)
    symbol_x, symbol_z = SEAT_FINISH_SYMBOL[key]
    return add_surface_finish(
        adapter,
        view,
        symbol_xy=_sheet(adapter, view, (symbol_x, face_y, symbol_z), f"{label} finish symbol"),
        control=control,
        label=f"{label} {key} finish",
        char_height=0.0025,
        entity=arcs[0],
        leader_attach_xy=_sheet(
            adapter,
            view,
            (radius * math.sin(angle), face_y, -radius * math.cos(angle)),
            f"{label} finish landing",
        ),
    )


def _seat_diameter_near_side(adapter: Any, annotations: list[Any], name: str) -> None:
    """One arrow on the seat arc nearest the text; no line through the centre.

    The default diameter leader ran from the text through the seat centre to
    the far side, across the seat-axis dimensions that start there (run-9 to
    12 sheets); the shared near-side style stops it at the arc it measures.
    """
    for raw in annotations:
        annotation = _early_bound(raw, "IAnnotation")
        if dimension_name(adapter, annotation) == name:
            set_near_side_diameter(annotation, name)
            return
    raise RuntimeError(f"no imported {name} to give a near-side leader")


def _lower_caption(adapter: Any, view: Any, drop: float) -> None:
    """Move a section's native caption down the sheet by ``drop`` metres,
    keeping its linked fields (``draw_fr_top_frame._position_view_caption``)."""
    view = _early_bound(view, "IView")
    captions = []
    for raw_note in view.GetNotes() or ():
        note = _early_bound(raw_note, "INote")
        linked_text = str(note.PropertyLinkedText or "")
        if all(token in linked_text for token in ("<VLNAME>", "<VLLABEL>", "<VLSCALEV>")):
            captions.append((note, linked_text))
    if len(captions) != 1:
        raise RuntimeError(f"expected one native linked view caption, found {len(captions)}")
    note, linked_text = captions[0]
    annotation = _early_bound(note.GetAnnotation(), "IAnnotation")
    x, y = (float(value) for value in tuple(annotation.GetPosition())[:2])
    target = (x, y - drop)
    if not annotation.SetPosition2(*target, 0.0):
        raise RuntimeError("failed to position native view caption")
    rebuild_drawing(adapter, label="lower section caption")
    position = tuple(float(value) for value in annotation.GetPosition())
    if math.dist(position[:2], target) > 1e-6:
        raise RuntimeError("native view caption position did not persist")
    if str(note.PropertyLinkedText or "") != linked_text:
        raise RuntimeError("view caption lost its native view-label fields")


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source part is missing: {SOURCE}")

    check("open bond-cradle source", await adapter.open_model(str(SOURCE)))
    source_model = adapter.currentModel
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
    drawing_model, _sheet_model = new_project_drawing(
        adapter, property_view=PART_STEM, scale=SHEET_SCALE, layout=SPEC.layout
    )
    stamp_drawing_summary(
        adapter,
        drawing_model,
        {
            0: "Cone Post Bond Cradle Drawing",
            1: "Harmonic Analyzer shop fixture drawing",
            2: "Harmonic Analyzer Project",
            3: "cone pivot post bond cradle; steel, built up and doweled; MHA-DT-005-TL-01",
            4: "Generated from the project-owned ASME B drawing standard",
        },
    )

    plan = place_view(adapter, str(SOURCE), "*Front", *PLAN_CENTER, scale=VIEW_SCALE)
    elevation = place_view(adapter, str(SOURCE), "*Right", *ELEVATION_CENTER, scale=VIEW_SCALE)
    # finalize_drawing shades the pictorial isometric with edges.
    place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=ISO_SCALE)
    _turn(adapter, plan, (0.0, 1.0, 0.0), 0.0, label="plan")
    _turn(adapter, elevation, (0.0, 1.0, 0.0), 0.0, label="elevation")
    _require_up(adapter, elevation, label="elevation")
    for view in (plan, elevation):
        set_hidden_lines_removed(adapter, view)

    plan_annotations = _curate(adapter, plan, PLAN_KEEP, "plan")
    elevation_annotations = _curate(adapter, elevation, ELEVATION_KEEP, "elevation")

    # Each section's reference sketch (seat axis from the west side; the cone
    # pin's tilt, hole position and gauge height) lies in its cutting plane
    # and is saved hidden: the sections are cut and dimensioned while the
    # part shows them.
    with part_sketches_shown(
        adapter,
        source_model,
        SECTION_REFERENCE_SKETCHES,
        label="seat sections",
        base_view=elevation,
    ):
        section_a = _cut(
            adapter,
            elevation,
            CONE_PIN_NEAR_Y,
            center=SECTION_A_CENTER,
            letter="A",
            x_right=False,
            label="section A-A",
        )
        section_b = _cut(
            adapter,
            elevation,
            TAIL_SECTION_Y,
            center=SECTION_B_CENTER,
            letter="B",
            x_right=True,
            label="section B-B",
        )
        section_a_annotations = _curate(adapter, section_a, SECTION_A_KEEP, "section A-A")
        section_b_annotations = _curate(adapter, section_b, SECTION_B_KEEP, "section B-B")

    annotations = [
        *plan_annotations,
        *elevation_annotations,
        *section_a_annotations,
        *section_b_annotations,
    ]
    set_dimension_callouts(adapter, annotations, DIMENSION_CALLOUTS)
    _seat_diameter_near_side(adapter, section_a_annotations, "BodySeatDia")
    # Places (and so each dimension's tolerance) are authored on the part; the
    # sheet only proves the import kept them.
    assert_imported_precision(adapter, annotations, DRAWING_PRECISION_BY_NAME)
    for view, key, face_y, label in (
        (section_a, "body_seat", BODY_SADDLE_Y + BODY_SADDLE_THICK, "section A-A"),
        (section_b, "tail_seat", TAIL_SADDLE_Y, "section B-B"),
    ):
        _seat_finish(adapter, view, key, face_y, label=label)
        _lower_caption(adapter, view, CAPTION_DROP)
    add_property_linked_note(adapter, "Manufacturing Notes", *NOTES_XY)
    add_property_linked_note(adapter, "Isometric View Note", *ISO_NOTE_XY)

    return await finalize_drawing(
        adapter,
        OUTPUTS,
        pdf_title="Cone Post Bond Cradle Drawing",
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
