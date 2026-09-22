r"""Create the native four-sheet summing assembly drawing package.

The released ``summing.SLDASM`` stays authoritative and byte-for-byte
unchanged. This recipe consumes the builder-owned ``SUMMING_EXPLODED``
presentation and adds drawing-native associative fit measurements; it never
authors or saves source-assembly presentation or construction features.
"""

from __future__ import annotations

import argparse
import math
import hashlib
import sys
from pathlib import Path
from typing import Any, Callable

import _telemetry
from _common import _early_bound, _read_member, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_component_bom_balloons,
    create_blank_drawing_sheets,
    create_section_view,
    finalize_drawing,
    insert_bom_table,
    isolate_drawing_view_components,
    model_point_in_view,
    new_project_drawing,
    read_required_properties,
    set_arc_endpoints_to_center,
    set_hidden_lines_removed,
    set_high_quality_shaded_with_edges,
)
from _drawing_registry import DRAWINGS_BY_NAME, DrawingLayout
from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import add_note, place_view
from summing_assembly_spec import (
    BOM_COMPONENTS,
    BOM_DESCRIPTIONS,
    BOM_IDENTITY_ALIASES,
    BOM_NORMALIZED_ALIASES,
    BOM_PART_NUMBERS,
    BOM_QUANTITIES,
    EXPLODED_VIEW_NAME,
    SOURCE_CONFIGURATION,
)
from build_knife_hanger_stud import THREAD_TIP_ROOT_RADIUS_MM
from build_knife_mount import STUD_TAP_DIA
from build_summing_assembly import (
    HANGER_ENGAGEMENT_GENERAL_TOLERANCE_MM,
    HANGER_ENGAGEMENT_PRECISION,
    HANGER_ENGAGEMENT_TARGET_MM,
    HEX_Z_MID,
    KNIFE,
    KNIFE_MOUNT_TOP_Y,
)
from cone_pivot_post_installation import SUMMING_Z


SPEC = DRAWINGS_BY_NAME["summing_assembly"]
ARTIFACT_STEM = SPEC.artifact_stem
SOURCE = SPEC.source
OUTPUTS = DrawingOutputs(
    slddrw=SPEC.outputs["slddrw"],
    pdf=SPEC.outputs["pdf"],
    png=SPEC.outputs["png"],
)
SLDDRW = OUTPUTS.slddrw
PDF = OUTPUTS.pdf
PNG = OUTPUTS.png

SHEET_NAMES = (
    "ASSEMBLED VIEWS",
    "EXPLODED VIEW + BOM",
    "ASSEMBLY + SETUP",
    "HANGER FIT + INSPECTION",
)
SHEET_LAYOUTS = {name: DrawingLayout.LANDSCAPE for name in SHEET_NAMES}
if SPEC.layout is not DrawingLayout.LANDSCAPE:
    raise AssertionError("the summing package primary sheet must remain landscape")

ASSEMBLED_SCALE = (1.0, 4.0)
EXPLODED_SCALE = (1.0, 4.0)
INSTRUCTION_SCALE = (1.0, 6.0)
HANGER_FIT_SHEET_SCALE = (1.0, 1.0)
HANGER_PARENT_SCALE = (1.0, 2.0)
HANGER_SECTION_SCALE = (1.0, 1.0)
HANGER_DETAIL_SCALE = (4.0, 1.0)
SHEET_SCALES = {
    SHEET_NAMES[0]: ASSEMBLED_SCALE,
    SHEET_NAMES[1]: EXPLODED_SCALE,
    SHEET_NAMES[2]: INSTRUCTION_SCALE,
    SHEET_NAMES[3]: HANGER_FIT_SHEET_SCALE,
}

ASSEMBLED_FRONT_CENTER = (0.065, 0.158)
ASSEMBLED_RIGHT_CENTER = (0.185, 0.158)
ASSEMBLED_ISO_CENTER = (0.330, 0.158)
EXPLODED_ISO_CENTER = (0.105, 0.158)
INSTRUCTION_ISO_CENTER = (0.345, 0.190)
HANGER_PARENT_CENTER = (0.060, 0.205)
HANGER_SECTION_CENTER = (0.300, 0.205)
HANGER_DETAIL_CENTER = (0.095, 0.080)
HANGER_DETAIL_LABEL_XY = (0.070, 0.142)
BOM_ANCHOR = (0.195, 0.258)
# Only assembly-level requirements live here. Part drawings own component
# manufacture, and calculated native placements remain evidence rather than
# fitter tolerances. Keeping these drawing notes out of the assembly spec also
# keeps wording-only changes out of the native assembly rebuild closure.
ASSEMBLY_STEPS = "\n".join(
    (
        "MATCH-DRILL AND ASSEMBLY SEQUENCE",
        "1. OFF THE FRAME, FIT MHA-073 BETWEEN THE ACTUAL MHA-037 PAIR.",
        "   SEAT BOTH KNIFE CONTACTS, CENTER THE LEVER AXIALLY, AND VERIFY",
        "   FREE ROCK WITHOUT AXIAL RUB. RETAIN THIS FITTED PAIR AS A SET.",
        "2. OFFER THE FITTED SET TO THE MHA-077 UNDERSIDE. CENTER THE",
        "   KNIFE LINE ON THE CROSSBAR WIDTH. ALIGN THE ACTUAL MHA-073",
        "   COUNTER-BOSS TAP AXIS AND MHA-077 GUIDE-BORE AXIS IN ONE PLANE",
        "   NORMAL TO THE KNIFE AXIS; CLAMP WITHOUT DISTURBING THE FIT.",
        "3. MHA-077 MUST HAVE NO FINISHED HANGER-HOLE LOCATIONS. TRANSFER",
        "   FROM THE ACTUAL MHA-037 TAP AXES, THEN REMOVE THE FITTED SET.",
        "   PILOT AND MATCH-DRILL 2X MHA-077 FINAL CLEARANCE HOLES AT THE",
        "   TRANSFERRED CENTERS; NEVER ENTER THE MHA-037 TAPS. DO NOT",
        "   RECENTER TO CAD COORDINATES OR PRE-DRILLED MARKS. DEBURR;",
        "   RETAIN PAIR, FRONT/REAR, AND ORIENTATION MATCH MARKS.",
        "4. KEEP EACH MHA-119/MHA-131 WITH ITS IDENTIFIED SIDE. MEASURE,",
        "   TRIM, AND INSPECT EACH ACTUAL STACK PER SHEET 4; THEN ASSEMBLE",
        "   FROM ABOVE WITH WASHER ON CROSSBAR AND HEAD FULLY ON WASHER.",
        "5. THREAD MHA-005 DIRECTLY INTO THE MHA-073 COUNTER BOSS; NO NUT.",
        "   CLOCK THE OPEN EYE TO THE PULL PLANE AND APPLY REMOVABLE",
        "   MEDIUM-STRENGTH THREADLOCKER.",
        "6. LOOSEN THE MHA-032 SPRING-RETAINER SCREW ONLY AS NEEDED",
        "   FOR ACCESS. HOOK MHA-019 BETWEEN MHA-005 AND MHA-032, THEN",
        "   TIGHTEN THE SCREW TO CLAMP THE UPPER EYE AGAINST THE ARM END.",
        "   DO NOT APPLY THREADLOCKER TO THE MHA-032 RETAINER SCREW.",
        "7. WITH EXTERNAL MHA-118 BACKED CLEAR, SLIDE MHA-032 IN THE",
        "   MHA-077 GUIDE BORE. LEAVE THE POST FREE FOR FINAL BALANCE.",
        "8. AT FINAL MACHINE ASSEMBLY, THREAD 20 MHA-090 DIRECTLY INTO",
        "   THE 20 MHA-073 TAPPED SEATS; OMIT SUPPLIED NUTS. CLOCK EACH EYE",
        "   TO ITS MHA-011 SPRING PULL PLANE AND APPLY REMOVABLE",
        "   MEDIUM-STRENGTH THREADLOCKER. KEEP EACH CUT END RECESSED;",
        "   BACK OUT NO MORE THAN ONE TURN.",
        "9. AT CRANK HOME WITH ALL CHANNELS AT NEUTRAL, SLIDE MHA-032 UNTIL",
        "   MHA-073 IS LEVEL AND FREE-BALANCED; THEN TIGHTEN MHA-118.",
    )
)

ASSEMBLY_CHECKS = "\n".join(
    (
        "ASSEMBLY-ONLY FUNCTIONAL CHECKS",
        "1. MHA-077/MHA-037 PAIR AND FRONT/REAR MATCH MARKS ALIGN.",
        "   BOTH MHA-119 PASS FREELY; HEADS AND MHA-131 WASHERS BEAR FULLY.",
        "   EACH AS-BUILT FIT MEETS SHEET 4; NEITHER STUD FORCES OR BOTTOMS.",
        "2. MHA-073 COUNTER-BOSS TAP AND MHA-077 GUIDE-BORE AXES SHARE",
        "   ONE PLANE NORMAL TO THE KNIFE AXIS. BOTH KNIFE CONTACTS ARE",
        "   SEATED; MHA-073 IS CENTERED AND ROCKS FREELY WITHOUT AXIAL RUB,",
        "   CLAMPING, OR A LOCKING CONSTRAINT.",
        "3. MHA-005 IS DIRECTLY THREADED, HAS NO NUT, AND ITS EYE FOLLOWS",
        "   THE COUNTER-SPRING PULL PLANE.",
        "4. THE MHA-019 UPPER EYE IS CLAMPED BETWEEN THE MHA-032 SCREW",
        "   HEAD AND ARM END AND CANNOT ESCAPE; NO THREADLOCKER IS PRESENT.",
        "   THE LOWER LOOP STAYS ON MHA-005; THE TENSIONED COIL CLEARS",
        "   MHA-032 AND MHA-073.",
        "5. MHA-032 SLIDES FREELY BEFORE SETTING AND IS HELD BY MHA-118",
        "   AFTER THE NEUTRAL BALANCE IS ESTABLISHED.",
        "6. ALL 20 MHA-090 EYES FOLLOW THEIR MHA-011 SPRING PULL PLANES;",
        "   NO NUTS ARE FITTED. CUT ENDS STAY RECESSED ABOVE THE MHA-073",
        "   UNDERSIDE AND RETAIN AT LEAST TWO FULL THREADS.",
        "7. AT CRANK HOME / NEUTRAL CHANNEL SETTING, MHA-073 IS LEVEL AND",
        "   RETURNS THROUGH ITS INTENDED FREE ROCK WITHOUT BINDING.",
    )
)

SETUP_NOTES = "\n".join(
    (
        "NEUTRAL / FREE-ROCKING SETUP",
        "SAVED DEFAULT IS THE NEUTRAL REFERENCE POSE.",
        "LEVER_ROCK IS THE ONE INTENTIONAL FREE DOF; DO NOT LOCK IT.",
        "NO PARKED OR ENGAGED CONFIGURATION IS DEFINED IN THIS SUBASSEMBLY.",
        "SET FINAL BALANCE WITH INSTALLED SPRINGS, NOT A CAD SPRING LENGTH.",
    )
)

INTERFACE_NOTES = "\n".join(
    (
        "EXTERNAL INSTALLATION INTERFACES - NOT BOM ITEMS",
        "MHA-077 / ACTUAL MHA-037 PAIR IS A NON-INTERCHANGEABLE SET.",
        "MHA-077 SUPPORTS THE HANGERS AND GUIDES MHA-032.",
        "MHA-118 LOCKS MHA-032 AFTER THE NEUTRAL SETUP.",
        "20X MHA-090 AND 20X MHA-011 BELONG TO THE CHANNEL ASSEMBLY.",
    )
)

HANGER_FIT_CONSTRUCTION = "\n".join(
    (
        "HANGER STUD CONSTRUCTION - MEASURE EACH IDENTIFIED SIDE",
        "T = ACTUAL MHA-077 THICKNESS AT THE TRANSFERRED HANGER HOLE.",
        "W = ACTUAL ASSIGNED MHA-131 THICKNESS; G = ACTUAL MOUNT GAP.",
        "E = TAP-MOUTH-TO-FINISHED-TIP DEPTH SHOWN IN DETAIL B.",
        "CUT ACTUAL UNDER-HEAD LENGTH L = T + W + G + E.",
        "MHA-119'S 45.10 UNDER-HEAD LENGTH IS REFERENCE ONLY; DO NOT CUT",
        "BOTH STUDS TO ONE ASSUMED STACK. CHAMFER EACH CUT TO THE EXISTING",
        "THREAD ROOT PER MHA-119; MEASURE THE FINISHED TIP AND CONE.",
        "MARK EACH BOLT FRONT/REAR; KEEP IT WITH ITS MHA-037/MHA-131 STATION.",
    )
)

HANGER_FIT_INSPECTION = "\n".join(
    (
        "AS-BUILT GEOMETRIC FIT - NOT A LOAD OR STRENGTH RATING",
        "USE ACTUAL VALUES: S=T+W+G; M=UNDER-HEAD TO COMPLETE-MALE START;",
        "F=COMPLETE MHA-037 FEMALE DEPTH; D=TAP-DRILL SHOULDER DEPTH.",
        "A=(RMAJ-RTIP)/TAN(ALPHA);",
        "O=MAX(0, MIN(F,E-A) - MAX(0,M-S)).",
        "REQUIRE E WITHIN DETAIL B'S GENERAL .XX BAND, O>0, AND E<D.",
        "IF E>F, REQUIRE MIN(RMAJ,RTIP+(E-F)/TAN(ALPHA))+Q<RDRILL;",
        "Q IS ACTUAL AXIS OFFSET. VERIFY FULL HEAD/WASHER SEATING, THE",
        "SPECIFIED GAP, BOTH KNIFE CONTACTS, AND FREE ROCK WITHOUT AXIAL RUB.",
    )
)


def _source_fingerprint(path: Path) -> tuple[int, int, str]:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    stat = path.stat()
    return stat.st_size, stat.st_mtime_ns, digest.hexdigest()


def _activate_sheet(adapter: Any, name: str) -> None:
    ddoc = _early_bound(adapter.currentModel, "IDrawingDoc")
    if not ddoc.ActivateSheet(name):
        raise RuntimeError(f"failed to activate drawing sheet {name!r}")
    current = _early_bound(ddoc.GetCurrentSheet(), "ISheet")
    if current is None:
        raise RuntimeError("drawing has no current sheet after activation")
    actual = str(current.GetName() or "")
    if actual != name:
        raise RuntimeError(f"active drawing sheet is {actual!r}, expected {name!r}")


def _add_note_block(
    adapter: Any,
    text: str,
    xy: tuple[float, float],
    *,
    label: str,
) -> Any:
    note = add_note(adapter, text, *xy)
    if note is None:
        raise RuntimeError(f"failed to add {label}")
    note = _early_bound(note, "INote")
    actual = str(note.GetText() or "").replace("\r\n", "\n").replace("\r", "\n")
    expected = text.replace("\r\n", "\n").replace("\r", "\n")
    if actual != expected:
        raise RuntimeError(
            f"{label} text did not persist "
            f"(actual_length={len(actual)}, expected_length={len(expected)})"
        )
    return note


def _component_point_in_assembly(
    component: Any,
    point: tuple[float, float, float],
) -> tuple[float, float, float]:
    """Transform one component-local point through its native assembly transform."""
    values = tuple(
        float(value)
        for value in _early_bound(
            _early_bound(component, "IComponent2").Transform2,
            "IMathTransform",
        ).ArrayData
    )
    if len(values) != 16:
        raise RuntimeError("summing drawing component transform is incomplete")
    x, y, z = point
    scale = values[12]
    return (
        scale * (x * values[0] + y * values[3] + z * values[6]) + values[9],
        scale * (x * values[1] + y * values[4] + z * values[7]) + values[10],
        scale * (x * values[2] + y * values[5] + z * values[8]) + values[11],
    )


def _visible_component_circle(
    view: Any,
    *,
    component_stem: str,
    height_mm: float,
    radius_mm: float,
    target_z_mm: float,
    label: str,
) -> Any:
    """Resolve one actual component edge by identity and native circle geometry."""
    view = _early_bound(view, "IView")
    full_components: dict[str, Any] = {}
    for raw_drawing_component in tuple(view.GetVisibleDrawingComponents() or ()):
        drawing_component = _early_bound(raw_drawing_component, "IDrawingComponent")
        component = _early_bound(drawing_component.Component, "IComponent2")
        name = str(component.Name2 or "").rsplit("/", 1)[-1]
        if name in full_components:
            raise RuntimeError(f"{label}: duplicate visible component {name!r}")
        full_components[name] = component

    candidates: list[tuple[tuple[float, ...], Any]] = []
    for raw_component in tuple(view.GetVisibleComponents() or ()):
        visible_component = _early_bound(raw_component, "IComponent2")
        if _component_stem(visible_component) != component_stem:
            continue
        name = str(visible_component.Name2 or "").rsplit("/", 1)[-1]
        full_component = full_components.get(name)
        if full_component is None:
            raise RuntimeError(f"{label}: component {name!r} has no full peer")
        transform_values = tuple(
            float(value)
            for value in _early_bound(
                full_component.Transform2,
                "IMathTransform",
            ).ArrayData
        )
        component_scale = transform_values[12]
        for raw_edge in tuple(view.GetVisibleEntities2(visible_component, 1) or ()):
            edge = _early_bound(raw_edge, "IEdge")
            curve = _early_bound(edge.GetCurve(), "ICurve")
            if curve is None or not curve.IsCircle():
                continue
            parameters = tuple(float(value) for value in curve.CircleParams)
            if len(parameters) < 7:
                raise RuntimeError(f"{label}: circular edge parameters are incomplete")
            center = _component_point_in_assembly(
                full_component,
                (parameters[0], parameters[1], parameters[2]),
            )
            actual_height_mm = center[1] * 1000.0
            actual_radius_mm = parameters[6] * component_scale * 1000.0
            if abs(actual_height_mm - height_mm) > 1e-5:
                continue
            if abs(actual_radius_mm - radius_mm) > 1e-5:
                continue
            candidates.append(
                (
                    (
                        abs(center[2] * 1000.0 - target_z_mm),
                        abs(center[0] * 1000.0 - KNIFE[0]),
                        center[2],
                        *parameters[:3],
                    ),
                    edge,
                )
            )
    if not candidates:
        raise RuntimeError(
            f"{label}: no {component_stem!r} circle at y={height_mm:g} mm, "
            f"radius={radius_mm:g} mm"
        )
    candidates.sort(key=lambda item: item[0])
    return candidates[0][1]


def _create_hanger_detail(adapter: Any, section: Any) -> Any:
    """Create a native enlarged detail around one real hanger/receiver interface."""
    draw = adapter.currentModel
    drawing = _early_bound(draw, "IDrawingDoc")
    section = _early_bound(section, "IView")
    if not drawing.ActivateView(str(section.GetName2() or "")):
        raise RuntimeError("failed to activate hanger section for detail")
    draw.ClearSelection2(True)
    tip_y = KNIFE_MOUNT_TOP_Y - HANGER_ENGAGEMENT_TARGET_MM
    detail_point_mm = (
        KNIFE[0],
        (KNIFE_MOUNT_TOP_Y + tip_y) / 2.0,
        SUMMING_Z + HEX_Z_MID,
    )
    center = model_point_in_view(
        adapter,
        section,
        tuple(value / 1000.0 for value in detail_point_mm),
        label="hanger engagement detail center",
    )
    radius = 0.012 * HANGER_SECTION_SCALE[0] / HANGER_SECTION_SCALE[1]
    sketch = _early_bound(section.GetSketch(), "ISketch")
    transform = _early_bound(sketch.ModelToSketchTransform, "IMathTransform")
    utility = _early_bound(adapter.swApp.GetMathUtility(), "IMathUtility")
    points = []
    for x, y in (center, (center[0] + radius, center[1])):
        point = _early_bound(
            utility.CreatePoint(double_array([x, y, 0.0])),
            "IMathPoint",
        )
        projected = _early_bound(point.MultiplyTransform(transform), "IMathPoint")
        points.append(tuple(float(value) for value in projected.ArrayData))
    manager = _early_bound(draw.SketchManager, "ISketchManager")
    if manager.CreateCircle(*points[0], *points[1]) is None:
        raise RuntimeError("failed to create native hanger detail fence")
    detail = drawing.CreateDetailViewAt4(
        *HANGER_DETAIL_CENTER,
        0.0,
        0,
        *HANGER_DETAIL_SCALE,
        "B",
        1,
        True,
        False,
        False,
        5,
    )
    if detail is None:
        raise RuntimeError("failed to create native hanger fit detail")
    detail = _early_bound(detail, "IView")
    detail.ScaleRatio = double_array(list(HANGER_DETAIL_SCALE))
    draw.ClearSelection2(True)
    draw.EditRebuild3()
    outline = tuple(float(value) for value in detail.GetOutline())
    position = tuple(float(value) for value in detail.Position)
    if len(outline) != 4 or len(position) != 2:
        raise RuntimeError("hanger detail has invalid bounds")
    target = [
        position[index]
        + HANGER_DETAIL_CENTER[index]
        - (outline[index] + outline[index + 2]) / 2.0
        for index in range(2)
    ]
    if not detail.SetViewPosition(double_array(target), False):
        raise RuntimeError("failed to position hanger fit detail")
    draw.EditRebuild3()
    if tuple(float(value) for value in detail.ScaleRatio) != HANGER_DETAIL_SCALE:
        raise RuntimeError("hanger detail scale did not persist")

    notes = tuple(_read_member(detail, "GetNotes") or ())
    if len(notes) != 1:
        raise RuntimeError(f"hanger detail has {len(notes)} native labels")
    note = _early_bound(notes[0], "INote")
    annotation = _early_bound(_read_member(note, "GetAnnotation"), "IAnnotation")
    if not annotation.SetPosition2(*HANGER_DETAIL_LABEL_XY, 0.0):
        raise RuntimeError("failed to position hanger detail label")
    circles = tuple(_read_member(section, "GetDetailCircles") or ())
    if len(circles) != 1:
        raise RuntimeError(f"hanger section has {len(circles)} detail fences")
    detail_circle = _early_bound(circles[0], "IDetailCircle")
    parent_label = (center[0] + 0.014, center[1] + 0.010)
    detail_circle.SetLabelPosition(*parent_label)
    draw.EditRebuild3()
    if math.dist(
        tuple(float(value) for value in detail_circle.GetLabelPosition()),
        parent_label,
    ) > 1e-8:
        raise RuntimeError("hanger detail parent label position did not persist")
    return detail


def _add_hanger_engagement_dimension(adapter: Any, detail: Any) -> Any:
    """Add and verify the associative tap-mouth-to-finished-tip measurement."""
    tip_y = KNIFE_MOUNT_TOP_Y - HANGER_ENGAGEMENT_TARGET_MM
    station_z = SUMMING_Z + HEX_Z_MID
    mouth = _visible_component_circle(
        detail,
        component_stem="knife-mount",
        height_mm=KNIFE_MOUNT_TOP_Y,
        radius_mm=STUD_TAP_DIA / 2.0,
        target_z_mm=station_z,
        label="actual MHA-037 tap mouth",
    )
    tip = _visible_component_circle(
        detail,
        component_stem="knife-hanger-stud",
        height_mm=tip_y,
        radius_mm=THREAD_TIP_ROOT_RADIUS_MM,
        target_z_mm=station_z,
        label="actual MHA-119 finished tip",
    )
    draw = adapter.currentModel
    drawing = _early_bound(draw, "IDrawingDoc")
    detail = _early_bound(detail, "IView")
    if not drawing.ActivateView(str(detail.GetName2() or "")):
        raise RuntimeError("failed to activate hanger fit detail")
    draw.ClearSelection2(True)
    selection_manager = _early_bound(draw.SelectionManager, "ISelectionMgr")
    for append, raw_entity in ((False, mouth), (True, tip)):
        selection_data = _early_bound(
            selection_manager.CreateSelectData(),
            "ISelectData",
        )
        selection_data.View = detail
        if not _early_bound(raw_entity, "IEntity").Select4(append, selection_data):
            raise RuntimeError("failed to select actual hanger fit edge")
    display = draw.AddVerticalDimension2(0.150, 0.082, 0.0)
    draw.ClearSelection2(True)
    if display is None:
        raise RuntimeError("failed to add native hanger engagement measurement")
    display = set_arc_endpoints_to_center(
        adapter,
        display,
        label="hanger engagement actual-edge measurement",
    )
    display = _early_bound(display, "IDisplayDimension")
    dimension = _early_bound(display.GetDimension2(0), "IDimension")
    measured_mm = abs(float(dimension.SystemValue) * 1000.0)
    if abs(measured_mm - HANGER_ENGAGEMENT_TARGET_MM) > 1e-5:
        raise RuntimeError(
            "hanger engagement actual-edge measurement is "
            f"{measured_mm:g} mm, expected {HANGER_ENGAGEMENT_TARGET_MM:g} mm"
        )
    if int(
        display.SetPrecision3(HANGER_ENGAGEMENT_PRECISION, -1, -1, -1)
    ) < 0:
        raise RuntimeError("failed to set hanger engagement precision")
    tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
    band = HANGER_ENGAGEMENT_GENERAL_TOLERANCE_MM / 1000.0
    tolerance.Type = 11
    if not tolerance.SetValues(-band, band):
        raise RuntimeError("hanger engagement general tolerance was rejected")
    draw.EditRebuild3()
    if int(display.GetPrimaryPrecision2()) != HANGER_ENGAGEMENT_PRECISION:
        raise RuntimeError("hanger engagement precision did not persist")
    if (
        int(tolerance.Type) != 11
        or not math.isclose(float(tolerance.GetMinValue()), -band, abs_tol=1e-9)
        or not math.isclose(float(tolerance.GetMaxValue()), band, abs_tol=1e-9)
    ):
        raise RuntimeError("hanger engagement general tolerance did not persist")
    return display


def _place_hanger_fit_sheet(adapter: Any) -> None:
    """Place the real assembly section/detail and its as-built fit instructions."""
    parent = place_view(
        adapter,
        str(SOURCE),
        "*Front",
        *HANGER_PARENT_CENTER,
        scale=HANGER_PARENT_SCALE,
    )
    _set_exploded_state(adapter, parent, False, label="hanger fit parent")
    set_hidden_lines_removed(adapter, parent)
    visible_stems = frozenset(
        {"knife-mount", "knife-hanger-washer", "knife-hanger-stud"}
    )
    isolate_drawing_view_components(
        adapter,
        parent,
        visible_stems=visible_stems,
        label="hanger fit parent",
    )
    parent = _early_bound(parent, "IView")
    outline = tuple(float(value) for value in parent.GetOutline())
    if len(outline) != 4:
        raise RuntimeError("hanger fit parent has invalid outline")
    cut_x = model_point_in_view(
        adapter,
        parent,
        (KNIFE[0] / 1000.0, KNIFE_MOUNT_TOP_Y / 1000.0, SUMMING_Z / 1000.0),
        label="hanger-axis section station",
    )[0]
    section = create_section_view(
        adapter,
        parent,
        line_start=(cut_x, outline[1] - 0.002),
        line_end=(cut_x, outline[3] + 0.002),
        view_xy=HANGER_SECTION_CENTER,
        section_label="A",
        scale=HANGER_SECTION_SCALE,
        label="hanger-axis assembly section",
    )
    set_hidden_lines_removed(adapter, section)
    isolate_drawing_view_components(
        adapter,
        section,
        visible_stems=visible_stems,
        label="hanger-axis assembly section",
    )
    detail = _create_hanger_detail(adapter, section)
    set_hidden_lines_removed(adapter, detail)
    _add_hanger_engagement_dimension(adapter, detail)
    _add_note_block(
        adapter,
        "MHA-A07 - HANGER FIT + INSPECTION\n"
        "MHA-119 / MHA-131 / MHA-037 MATCHED TO MHA-077",
        (0.018, 0.263),
        label="hanger fit sheet identity",
    )
    _add_note_block(
        adapter,
        "DETAIL B - E IS ACTUAL TAP MOUTH TO FINISHED BOLT TIP",
        (0.030, 0.150),
        label="hanger engagement detail heading",
    )
    _add_note_block(
        adapter,
        HANGER_FIT_CONSTRUCTION,
        (0.165, 0.145),
        label="hanger fit construction",
    )
    _add_note_block(
        adapter,
        HANGER_FIT_INSPECTION,
        (0.165, 0.100),
        label="hanger fit inspection",
    )

def _set_exploded_state(
    adapter: Any,
    view: Any,
    show: bool,
    *,
    label: str,
) -> None:
    bound = _early_bound(view, "IView")
    if str(bound.ReferencedConfiguration) != SOURCE_CONFIGURATION:
        raise RuntimeError(
            f"{label}: view must reference {SOURCE_CONFIGURATION!r}"
        )
    returned = bool(bound.ShowExploded(show))
    actual = bool(bound.IsExploded())
    if actual != show:
        raise RuntimeError(
            f"{label}: exploded-state readback is {actual}, expected {show}"
        )
    if show and not returned:
        raise RuntimeError(f"{label}: ShowExploded returned false")
    if not adapter.currentModel.EditRebuild3():
        raise RuntimeError(f"{label}: exploded-state rebuild failed")


def _component_stem(component: Any) -> str:
    component = _early_bound(component, "IComponent2")
    path = str(component.GetPathName() or "")
    if not path:
        raise RuntimeError(f"component {component.Name2!r} has no referenced path")
    return Path(path).stem.casefold()


def _validate_persisted_explode(source_model: Any) -> None:
    """Consume the builder-owned presentation without changing the assembly."""
    assembly = _early_bound(source_model, "IAssemblyDoc")
    manager = _early_bound(
        source_model.ConfigurationManager,
        "IConfigurationManager",
    )
    configuration = _early_bound(
        manager.ActiveConfiguration,
        "IConfiguration",
    )
    if str(configuration.Name) != SOURCE_CONFIGURATION:
        raise RuntimeError(
            f"summing source must open in {SOURCE_CONFIGURATION!r}"
        )
    names = tuple(
        assembly.GetExplodedViewNames2(SOURCE_CONFIGURATION) or ()
    )
    if names != (EXPLODED_VIEW_NAME,):
        raise RuntimeError(
            f"summing source exploded views {names!r} != "
            f"{(EXPLODED_VIEW_NAME,)!r}"
        )

    groups = {stem: 0 for stem in BOM_COMPONENTS}
    components = tuple(assembly.GetComponents(True) or ())
    for raw_component in components:
        component = _early_bound(raw_component, "IComponent2")
        stem = _component_stem(component)
        if stem not in groups:
            raise RuntimeError(
                f"summing source contains unexpected component "
                f"{component.Name2!r}: {stem!r}"
            )
        groups[stem] += 1
        total = _early_bound(
            component.GetTotalTransform(True),
            "IMathTransform",
        )
        base = _early_bound(
            component.GetTotalTransform(False),
            "IMathTransform",
        )
        if any(
            abs(float(actual) - float(expected)) > 1e-9
            for actual, expected in zip(
                total.ArrayData,
                base.ArrayData,
                strict=True,
            )
        ):
            raise RuntimeError(
                f"summing source must open collapsed: "
                f"{component.Name2!r} is displaced"
            )
    if groups != BOM_QUANTITIES:
        raise RuntimeError(
            f"summing source component counts {groups!r} != "
            f"{BOM_QUANTITIES!r}"
        )


def _normalized_bom_identity(text: str) -> str:
    normalized = text.strip().casefold()
    return BOM_NORMALIZED_ALIASES.get(normalized, normalized)


def _validate_summing_bom(
    adapter: Any,
    table: Any,
) -> tuple[tuple[str, str], ...]:
    table = _early_bound(table, "ITableAnnotation")
    rows = int(table.RowCount)
    columns = int(table.ColumnCount)
    if rows != len(BOM_COMPONENTS) + 1 or columns < 4:
        raise RuntimeError(
            f"summing BOM is {rows}x{columns}; expected "
            f"{len(BOM_COMPONENTS) + 1} rows and at least four columns"
        )
    contents = tuple(
        tuple(
            str(table.DisplayedText(row, column) or "").strip()
            for column in range(columns)
        )
        for row in range(rows)
    )
    header = tuple(cell.upper() for cell in contents[0])

    def column_named(
        predicate: Callable[[str], bool],
        label: str,
    ) -> int:
        matches = [
            index for index, cell in enumerate(header) if predicate(cell)
        ]
        if len(matches) != 1:
            raise RuntimeError(
                f"summing BOM has no unique {label} column: {header!r}"
            )
        return matches[0]

    item_column = column_named(
        lambda cell: cell.startswith("ITEM NO"),
        "ITEM NO.",
    )
    part_column = column_named(
        lambda cell: cell == "PART NUMBER",
        "PART NUMBER",
    )
    description_column = column_named(
        lambda cell: cell == "DESCRIPTION",
        "DESCRIPTION",
    )
    quantity_column = column_named(
        lambda cell: cell.startswith("QTY"),
        "QTY.",
    )
    for column, width in (
        (item_column, 0.020),
        (part_column, 0.034),
        (description_column, 0.145),
        (quantity_column, 0.020),
    ):
        actual_width = float(table.SetColumnWidth(column, width, 0))
        if abs(actual_width - width) > 1e-6:
            raise RuntimeError(
                f"summing BOM column width did not persist: {column}"
            )
    for row in range(rows):
        actual_height = float(table.SetRowHeight(row, 0.006, 0))
        if abs(actual_height - 0.006) > 1e-6:
            raise RuntimeError(
                f"summing BOM row height did not persist: {row}"
            )

    actual: dict[str, tuple[int, str, str, str]] = {}
    for row_index, row in enumerate(contents[1:], start=1):
        stem = _normalized_bom_identity(row[part_column])
        if stem in actual:
            raise RuntimeError(
                f"summing BOM repeats component family {stem!r}"
            )
        actual[stem] = (
            row_index,
            row[item_column],
            row[description_column],
            row[quantity_column],
        )
    if set(actual) != set(BOM_COMPONENTS):
        raise RuntimeError(
            f"summing BOM identities {sorted(actual)!r} != "
            f"{sorted(BOM_COMPONENTS)!r}"
        )
    expected_items = {
        str(item) for item in range(1, len(BOM_COMPONENTS) + 1)
    }
    actual_items = {values[1] for values in actual.values()}
    if actual_items != expected_items:
        raise RuntimeError(
            f"summing BOM item numbers {sorted(actual_items)!r} != "
            f"{sorted(expected_items)!r}"
        )

    for stem, (row_index, _item, description, quantity) in actual.items():
        expected_part_number = BOM_PART_NUMBERS[stem]
        if contents[row_index][part_column] != expected_part_number:
            if not table.IsCellTextEditable(row_index, part_column):
                raise RuntimeError(
                    f"summing BOM part-number cell for {stem!r} "
                    "is not editable"
                )
            table.SetText2(
                row_index,
                part_column,
                False,
                expected_part_number,
            )
            applied = str(
                table.DisplayedText2(
                    row_index,
                    part_column,
                    False,
                )
                or ""
            ).strip()
            if applied != expected_part_number:
                raise RuntimeError(
                    f"summing BOM part number for {stem!r} did not persist"
                )
        if description != BOM_DESCRIPTIONS[stem]:
            raise RuntimeError(
                f"summing BOM description mismatch for {stem!r}"
            )
        if quantity != str(BOM_QUANTITIES[stem]):
            raise RuntimeError(
                f"summing BOM quantity for {stem!r} is {quantity!r}, "
                f"expected {BOM_QUANTITIES[stem]}"
            )
    if not adapter.currentModel.EditRebuild3():
        raise RuntimeError("summing BOM rebuild failed")
    for stem, (row_index, _item, _description, _quantity) in actual.items():
        applied = str(
            table.DisplayedText(row_index, part_column) or ""
        ).strip()
        if applied != BOM_PART_NUMBERS[stem]:
            raise RuntimeError(
                f"summing BOM part number for {stem!r} "
                f"reverted to {applied!r}"
            )
    return tuple((stem, actual[stem][1]) for stem in BOM_COMPONENTS)


def _create_package_sheets(adapter: Any) -> None:
    _drawing, _sheet = new_project_drawing(
        adapter,
        layout=SPEC.layout,
        scale=ASSEMBLED_SCALE,
    )
    create_blank_drawing_sheets(
        adapter,
        SHEET_NAMES,
        label="summing assembly package",
    )
    for sheet_number, sheet_name in enumerate(SHEET_NAMES, start=1):
        _activate_sheet(adapter, sheet_name)
        sheet = _early_bound(
            _early_bound(
                adapter.currentModel,
                "IDrawingDoc",
            ).GetCurrentSheet(),
            "ISheet",
        )
        sheet_scale = SHEET_SCALES[sheet_name]
        if not sheet.SetScale(
            float(sheet_scale[0]),
            float(sheet_scale[1]),
            False,
            False,
        ):
            raise RuntimeError(
                f"failed to set native summing sheet scale: {sheet_name}"
            )
        _add_note_block(
            adapter,
            f"SHEET {sheet_number} OF {len(SHEET_NAMES)}",
            (0.018, 0.025),
            label="package sheet number",
        )


def _place_package(adapter: Any) -> None:
    _create_package_sheets(adapter)

    _activate_sheet(adapter, SHEET_NAMES[0])
    front = place_view(
        adapter,
        str(SOURCE),
        "*Front",
        *ASSEMBLED_FRONT_CENTER,
        scale=ASSEMBLED_SCALE,
    )
    right = place_view(
        adapter,
        str(SOURCE),
        "*Right",
        *ASSEMBLED_RIGHT_CENTER,
        scale=ASSEMBLED_SCALE,
    )
    assembled_iso = place_view(
        adapter,
        str(SOURCE),
        "*Isometric",
        *ASSEMBLED_ISO_CENTER,
        scale=ASSEMBLED_SCALE,
    )
    for label, view in (
        ("assembled front", front),
        ("assembled right", right),
        ("assembled isometric", assembled_iso),
    ):
        _set_exploded_state(adapter, view, False, label=label)
    set_hidden_lines_removed(adapter, front)
    set_hidden_lines_removed(adapter, right)
    set_high_quality_shaded_with_edges(
        adapter,
        assembled_iso,
        label="summing assembled isometric",
    )
    _add_note_block(
        adapter,
        "ASSEMBLED NEUTRAL REFERENCE - LEVER ROCK REMAINS FREE",
        (0.112, 0.263),
        label="assembled-view heading",
    )
    _add_note_block(
        adapter,
        "FRONT 1:4",
        (0.040, 0.080),
        label="front-view caption",
    )
    _add_note_block(
        adapter,
        "RIGHT 1:4",
        (0.160, 0.080),
        label="right-view caption",
    )
    _add_note_block(
        adapter,
        "ASSEMBLED ISOMETRIC 1:4",
        (0.290, 0.080),
        label="assembled-isometric caption",
    )

    _activate_sheet(adapter, SHEET_NAMES[1])
    exploded = place_view(
        adapter,
        str(SOURCE),
        "*Isometric",
        *EXPLODED_ISO_CENTER,
        scale=EXPLODED_SCALE,
    )
    _set_exploded_state(
        adapter,
        exploded,
        True,
        label="exploded isometric",
    )
    set_high_quality_shaded_with_edges(
        adapter,
        exploded,
        label="summing exploded isometric",
    )
    table = insert_bom_table(
        adapter,
        exploded,
        anchor_xy=BOM_ANCHOR,
        expected_components=BOM_COMPONENTS,
        descriptions=BOM_DESCRIPTIONS,
        identity_aliases=BOM_IDENTITY_ALIASES,
        configuration_grouping="same-part",
        label="summing",
    )
    balloon_items = _validate_summing_bom(adapter, table)
    add_component_bom_balloons(
        adapter,
        exploded,
        items=balloon_items,
        label="summing exploded-view BOM coverage",
        margin=0.012,
    )
    _add_note_block(
        adapter,
        "EXPLODED ISOMETRIC 1:4",
        (0.060, 0.263),
        label="exploded-view heading",
    )
    _add_note_block(
        adapter,
        "SEE SHEET 3 FOR ASSEMBLY; SHEET 4 FOR HANGER FIT/INSPECTION",
        (0.060, 0.075),
        label="exploded-view caption",
    )

    _activate_sheet(adapter, SHEET_NAMES[2])
    instruction_iso = place_view(
        adapter,
        str(SOURCE),
        "*Isometric",
        *INSTRUCTION_ISO_CENTER,
        scale=INSTRUCTION_SCALE,
    )
    _set_exploded_state(
        adapter,
        instruction_iso,
        False,
        label="instruction isometric",
    )
    set_high_quality_shaded_with_edges(
        adapter,
        instruction_iso,
        label="summing instruction isometric",
    )
    _add_note_block(
        adapter,
        ASSEMBLY_STEPS,
        (0.018, 0.263),
        label="assembly sequence",
    )
    _add_note_block(
        adapter,
        ASSEMBLY_CHECKS,
        (0.018, 0.165),
        label="assembly functional checks",
    )
    _add_note_block(
        adapter,
        SETUP_NOTES,
        (0.265, 0.128),
        label="neutral setup",
    )
    _add_note_block(
        adapter,
        INTERFACE_NOTES,
        (0.265, 0.094),
        label="external interfaces",
    )
    _add_note_block(
        adapter,
        "FINISHED ASSEMBLY 1:6",
        (0.315, 0.145),
        label="instruction-isometric caption",
    )

    _activate_sheet(adapter, SHEET_NAMES[3])
    _place_hanger_fit_sheet(adapter)


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source assembly is missing: {SOURCE}")
    fingerprint = _source_fingerprint(SOURCE)
    check("open summing drawing source", await adapter.open_model(str(SOURCE)))
    source_model = _early_bound(adapter.currentModel, "IModelDoc2")
    if bool(source_model.GetSaveFlag()):
        raise RuntimeError(
            "summing source assembly is already dirty; "
            "refusing to discard user changes"
        )
    read_required_properties(
        source_model,
        (
            "Number",
            "Revision",
            "Title",
            "Material Specification",
            "Finish",
            "Quantity",
        ),
        required=(
            "Number",
            "Revision",
            "Material Specification",
            "Finish",
            "Quantity",
        ),
    )
    source_title = str(source_model.GetTitle() or "")
    if not source_title:
        raise RuntimeError("summing source assembly has no document title")

    artifacts: dict[str, str] | None = None
    try:
        _validate_persisted_explode(source_model)
        _place_package(adapter)
        artifacts = await finalize_drawing(
            adapter,
            OUTPUTS,
            layout=SPEC.layout,
            pdf_title="Summing Assembly Drawing Package",
            scale=ASSEMBLED_SCALE,
            expected_sheet_names=SHEET_NAMES,
            sheet_layouts=SHEET_LAYOUTS,
            sheet_scales=SHEET_SCALES,
        )
    finally:
        primary_error = sys.exception()
        cleanup_errors: list[str] = []
        if artifacts is None:
            try:
                active_model = adapter.currentModel
                if active_model is not None:
                    active_model = _early_bound(active_model, "IModelDoc2")
                    if int(active_model.GetType()) == 3:
                        drawing_title = str(active_model.GetTitle() or "")
                        if not drawing_title:
                            cleanup_errors.append(
                                "generated summing drawing has no title for close"
                            )
                        else:
                            adapter.swApp.CloseDoc(drawing_title)
            except Exception as exc:  # noqa: BLE001
                cleanup_errors.append(
                    f"failed to close generated summing drawing: {exc}"
                )

        try:
            adapter.swApp.CloseDoc(source_title)
            if (
                adapter.swApp.GetOpenDocumentByName(str(SOURCE.resolve()))
                is not None
            ):
                cleanup_errors.append(
                    f"summing source {source_title!r} remained open after discard"
                )
        except Exception as exc:  # noqa: BLE001
            cleanup_errors.append(
                f"failed to close summing source {source_title!r}: {exc}"
            )

        try:
            after_fingerprint = _source_fingerprint(SOURCE)
            if after_fingerprint != fingerprint:
                cleanup_errors.append(
                    "summing drawing generation changed the released source "
                    "assembly (size, mtime_ns, SHA256): "
                    f"{fingerprint!r} -> {after_fingerprint!r}"
                )
        except Exception as exc:  # noqa: BLE001
            cleanup_errors.append(
                f"failed to verify summing source fingerprint: {exc}"
            )

        if cleanup_errors:
            message = "; ".join(cleanup_errors)
            if primary_error is not None:
                _telemetry.warn(
                    f"summing drawing cleanup after failure: {message}"
                )
            else:
                raise RuntimeError(message)

    if artifacts is None:
        raise RuntimeError("summing drawing package returned no artifacts")
    return artifacts


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[ARTIFACT_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
