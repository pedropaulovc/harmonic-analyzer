r"""Create the native multi-sheet frame assembly drawing package.

The released ``frame.SLDASM`` stays authoritative and byte-for-byte unchanged.
This recipe consumes the builder-owned ``FRAME_EXPLODED`` presentation for one
native drawing view. It never creates, edits, deletes, or saves assembly
presentation definitions.
"""

from __future__ import annotations

import argparse
import hashlib
import math
import sys
from pathlib import Path
from typing import Any, Callable, Sequence

import _telemetry
from _common import _early_bound, check, run_build
from _drawing_common import (
    DrawingOutputs,
    _balloon_item_number,
    _edge_endpoint_key,
    _spread_balloons,
    add_component_bom_balloons,
    create_section_view,
    finalize_drawing,
    insert_bom_table,
    model_point_in_view,
    position_bom_balloon,
    rendered_balloon_circle,
    new_project_drawing,
    read_required_properties,
    set_arc_endpoints_to_center,
    set_reference_dimension,
    set_hidden_lines_visible,
    set_high_quality_shaded_with_edges,
    sheet_drawable_region,
)
from _drawing_registry import DRAWINGS_BY_NAME, DrawingLayout
from frame_attachment_spec import (
    BASE_SCREW_Y,
    CAP_TOP_Y,
    CASTING_FULL_THREAD_DEPTH,
    TOP_SCREW_Y,
    TUBE_CROSS_HOLE_DIAMETER,
)
from frame_cross_screw_spec import (
    HEAD_DIA as CROSS_SCREW_HEAD_DIA,
    SHANK_DIA as CROSS_SCREW_SHANK_DIA,
    SHANK_LEN as CROSS_SCREW_SHANK_LEN,
    THREAD as CROSS_SCREW_THREAD,
)
from solidworks_mcp.adapters.solidworks.drawing import add_note, place_view
from solidworks_mcp.adapters.pywin32_adapter import null_callout
from solidworks_mcp.adapters.com_variant import dispatch_array


SPEC = DRAWINGS_BY_NAME["frame_assembly"]
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
    "ASSEMBLED + JOINT SECTIONS",
    "EXPLODED VIEW + BOM",
    "FITTING + ASSEMBLY",
)
SHEET_LAYOUTS = {
    SHEET_NAMES[0]: DrawingLayout.LANDSCAPE,
    SHEET_NAMES[1]: DrawingLayout.PORTRAIT,
    SHEET_NAMES[2]: DrawingLayout.LANDSCAPE,
}
if SPEC.layout is not SHEET_LAYOUTS[SHEET_NAMES[0]]:
    raise AssertionError("the frame package primary sheet must remain landscape")
SHEET_SCALE = (1.0, 8.0)
WORKING_FRONT_CENTER = (0.053763, 0.163612)
BASE_SECTION_CENTER = (0.170714, 0.1823453)
TOP_SECTION_CENTER = (0.335290, 0.1815266)
JOINT_SECTION_SCALE = (1.0, 3.0)
EXPLODED_ISO_CENTER = (0.140, 0.198)
EXPLODED_ISO_SCALE = (1.0, 7.0)
ASSEMBLY_ISO_CENTER = (0.345, 0.172)
ASSEMBLY_ISO_SCALE = (1.0, 7.0)
SHEET_SCALES = {
    SHEET_NAMES[0]: SHEET_SCALE,
    SHEET_NAMES[1]: EXPLODED_ISO_SCALE,
    SHEET_NAMES[2]: ASSEMBLY_ISO_SCALE,
}
BOM_ANCHOR = (0.018, 0.414)

# Drawing-selection coordinate only. The manufacturing column pitch remains
# defined by the released source assembly and the part drawings.
_LEFT_COLUMN_X_M = -0.197

BOM_QUANTITIES = {
    "harmonic-base": 1,
    "tube-frame": 4,
    "tube-frame-cap": 4,
    "rocker-arm-support": 1,
    "lag-screw": 4,
    "top-frame": 1,
    "nameplate": 1,
    "fillister-screw": 4,
    "frame-cross-screw": 8,
    "gooseneck-set-screw": 1,
}
if sum(BOM_QUANTITIES.values()) != 29:
    raise AssertionError("the released frame assembly must contain 29 components")
BOM_COMPONENTS = tuple(BOM_QUANTITIES)
BOM_DESCRIPTIONS = {
    "harmonic-base": "TWO-PLATE FRAME BASE",
    "tube-frame": "OPEN-END TUBULAR FRAME COLUMN",
    "tube-frame-cap": "STEEL PUSH-ON CAP FOR 1 IN OD TUBE",
    "rocker-arm-support": "ROCKER-ARM SUPPORT CASTING",
    "lag-screw": "1/4-20 X 5/8 HEX-HEAD SCREW, 18-8 SS",
    "top-frame": "TOP-FRAME CASTING",
    "nameplate": "ENGRAVED BRASS MAKER'S NAMEPLATE",
    "fillister-screw": "BRASS #4-40 X 1/4 FILLISTER-HEAD SLOTTED SCREW",
    "frame-cross-screw": (
        "ZINC-PLATED STEEL #10-32 X 1-3/4 NARROW FILLISTER-HEAD SLOTTED SCREW"
    ),
    "gooseneck-set-screw": "STEEL 1/4-20 X 5/8 SQUARE-HEAD CUP-POINT SET SCREW",
}
BOM_PART_NUMBERS = {
    "harmonic-base": "MHA-035",
    "tube-frame": "MHA-083",
    "tube-frame-cap": "MHA-133",
    "rocker-arm-support": "MHA-089",
    "lag-screw": "MHA-039",
    "top-frame": "MHA-077",
    "nameplate": "MHA-086",
    "fillister-screw": "MHA-030",
    "frame-cross-screw": "MHA-132",
    "gooseneck-set-screw": "MHA-118",
}
BOM_IDENTITY_ALIASES = {number: stem for stem, number in BOM_PART_NUMBERS.items()}
BOM_NORMALIZED_ALIASES = {
    alias.casefold(): stem for alias, stem in BOM_IDENTITY_ALIASES.items()
}

if CROSS_SCREW_THREAD != "#10-32":
    raise AssertionError("MHA-132 must remain the approved #10-32 stock screw")
if TUBE_CROSS_HOLE_DIAMETER <= CROSS_SCREW_SHANK_DIA:
    raise AssertionError("tube match holes must clear the stock screw shank")
if CROSS_SCREW_SHANK_LEN >= CASTING_FULL_THREAD_DEPTH:
    raise AssertionError("stock cross screw must seat before reaching the tap bottom")

EXPLODED_VIEW_NAME = "FRAME_EXPLODED"
SOURCE_CONFIGURATION = "Default"

# These instructions carry only requirements that exist at assembly: matched
# fits, the one-setup coaxial casting threads, transfer-drilled tube holes,
# fitted stock caps, and checks against the actual purchased components. Part
# drawings still define the other manufacturing features.
ASSEMBLY_STEPS = "\n".join(
    (
        "MATCH-FIT AND ASSEMBLY SEQUENCE",
        "1. ROUGH-CUT MHA-083 OVERSIZE. DECK UP; FIT EACH MHA-035 SOCKET",
        "   TO ITS ASSIGNED ACTUAL TUBE: CLOSE HAND-SLIP, NO PERCEPTIBLE ROCK,",
        "   FULL SHOULDER SEATING. RETAIN COLUMN/CORNER/ORIENTATION MATCH MARKS.",
        "2. RESEAT EACH MATCHED COLUMN. THROUGH THE EXISTING CASTING BORES,",
        "   PILOT-TRANSFER THE LOWER AXIS THROUGH BOTH TUBE WALLS WITH A DRILL",
        "   BELOW THE #10-32 THREAD MINOR; PROTECT BOTH THREAD SEGMENTS.",
        f"   REMOVE COLUMN; ENLARGE BOTH WALLS TO DIA {TUBE_CROSS_HOLE_DIAMETER:.2f} "
        "AND DEBURR.",
        "   THE ACTUAL MHA-132 SHANK MUST PASS FREELY WITHOUT THREAD CONTACT.",
        "3. RESEAT EACH MATCHED COLUMN IN ITS BASE SOCKET.",
        "   FIT MHA-077 OVER THE COLUMNS, HUB OPPOSITE THE MHA-086 END.",
        "   FIT EACH TOP SOCKET TO ITS ASSIGNED ACTUAL MHA-083 TUBE:",
        "   CLOSE HAND-SLIP WITH NO PERCEPTIBLE ROCK.",
        "   SET EVERY FRONT/REAR CROSS-BORE AXIS TO THE CONTROLLING TOP-AXIS",
        "   HEIGHT ON SHEET 1; COMPARE GAUGE-PIN CENTRES FROM THE BASE UNDERSIDE.",
        "   CLAMP; RETAIN EACH TOP CORNER/COLUMN ORIENTATION MATCH MARK.",
        "4. AT THAT HEIGHT, FINAL MATCH-CUT EACH IDENTIFIED COLUMN TO THE",
        "   ACTUAL BASE/TOP/CAP STACK: MHA-133 FULLY ON ITS INSIDE SEAT,",
        "   SKIRT CLEAR OF THE RECESS FLOOR. DO NOT TRIM THE STOCK CAPS.",
        "   FINISH THE TOP CHAMFER; RESEAT COLUMNS AND RESET THE TOP-AXIS HEIGHT.",
        "5. THROUGH THE EXISTING MHA-077 CASTING BORES, PILOT-TRANSFER EACH TOP",
        "   AXIS THROUGH BOTH TUBE WALLS AS STEP 2; PROTECT BOTH THREAD SEGMENTS.",
        f"   REMOVE MHA-077/COLUMNS; ENLARGE BOTH WALLS TO DIA {TUBE_CROSS_HOLE_DIAMETER:.2f},",
        "   DEBURR, AND VERIFY FREE PASSAGE OF THE ACTUAL MHA-132 SHANK.",
        "6. REASSEMBLE MATCHED FRAME. INSTALL EIGHT MHA-132 FROM THE SIDES",
        "   USED FOR PILOT-DRILLING; TIGHTEN ONLY UNTIL EVERY HEAD SEATS.",
        "7. VERIFY EACH MHA-077 CAP RECESS CLEARS ITS ACTUAL MHA-133 SKIRT.",
        "   AFTER MATCH MARKS ALIGN AND MHA-132 HEADS SEAT, PUSH EACH CAP OVER",
        "   THE CHAMFERED OPEN END UNTIL THE TUBE REACHES THE CAP'S INSIDE SEAT.",
        "8. SEAT MHA-089 ON DECK, WINDOWS TOWARD LONG SIDES; INSTALL FOUR",
        "   MHA-039 TOP-DOWN AND DRAW DOWN EVENLY UNTIL ALL HEADS SEAT.",
        "9. INSTALL MHA-086 DECORATED FACE UP; SEAT ALL FOUR MHA-030 HEADS.",
        "10. START MHA-118 IN THE GOOSENECK HUB; LEAVE ITS CUP POINT CLEAR.",
    )
)
ASSEMBLY_CHECKS = "\n".join(
    (
        "ASSEMBLY-ONLY CHECKS",
        "1. ALL BASE/TOP MATCH MARKS ALIGN; COLUMNS ARE FULLY SEATED.",
        "   EACH FRONT/REAR TOP AXIS MEETS THE HEIGHT FROM THE BASE UNDERSIDE.",
        "2. ALL EIGHT MHA-132 HEADS SEAT WITHOUT TIPS BOTTOMING. EACH SHANK",
        "   CLEARS BOTH TUBE WALLS AND HAS POSITIVE THREAD ENGAGEMENT IN BOTH",
        "   NEAR AND FAR CASTING THREAD SEGMENTS.",
        "3. ALL FOUR MHA-133 CAPS REACH THEIR INSIDE SEATS; SKIRTS CLEAR THE",
        "   MHA-077 RECESSES, TOPS ARE EVEN, AND TUBE ENDS ARE NOT DISTORTED.",
        "4. MHA-089 AND MHA-086 LIE FLAT; ALL EIGHT OF THEIR SCREW HEADS BEAR.",
        "5. GOOSENECK BORE IS UNOBSTRUCTED WITH MHA-118 BACKED CLEAR.",
    )
)


def _as_tuple(value: Any, *, label: str) -> tuple[Any, ...]:
    if value is None or isinstance(value, str):
        raise RuntimeError(f"{label}: SolidWorks returned no object array")
    try:
        return tuple(value)
    except TypeError:
        return (value,)


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
    adapter: Any, text: str, xy: tuple[float, float], *, label: str
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


def _set_exploded_state(adapter: Any, view: Any, show: bool, *, label: str) -> None:
    bound = _early_bound(view, "IView")
    if str(bound.ReferencedConfiguration) != SOURCE_CONFIGURATION:
        raise RuntimeError(f"{label}: view must reference the Default configuration")
    returned = bool(bound.ShowExploded(show))
    actual = bool(bound.IsExploded())
    if actual != show:
        raise RuntimeError(
            f"{label}: exploded-state readback is {actual}, expected {show}"
        )
    if show and not returned:
        raise RuntimeError(f"{label}: ShowExploded returned false")
    adapter.currentModel.EditRebuild3()


def _checked_height_dimension(
    adapter: Any, display: Any, *, expected_mm: float, label: str
) -> Any:
    display = _early_bound(display, "IDisplayDimension")
    dimension = _early_bound(display.GetDimension2(0), "IDimension")
    measured_mm = abs(float(dimension.SystemValue) * 1000.0)
    if abs(measured_mm - expected_mm) > 1e-5:
        raise RuntimeError(
            f"{label} measured {measured_mm:g}, expected {expected_mm:g} mm"
        )
    if int(display.SetPrecision3(1, -1, -1, -1)) < 0:
        raise RuntimeError(f"failed to set {label} precision")
    if int(display.GetPrimaryPrecision2()) != 1:
        raise RuntimeError(f"{label} did not retain one-place precision")
    adapter.currentModel.EditRebuild3()
    return display


def _component_point_in_assembly(
    component: Any, point: Sequence[float]
) -> tuple[float, float, float]:
    """Transform one component-local point through its exact native transform."""
    values = tuple(
        float(value)
        for value in _early_bound(
            _early_bound(component, "IComponent2").Transform2, "IMathTransform"
        ).ArrayData
    )
    if len(values) != 16 or len(point) != 3:
        raise RuntimeError("frame drawing component transform is incomplete")
    x, y, z = (float(value) for value in point)
    scale = values[12]
    return (
        scale * (x * values[0] + y * values[3] + z * values[6]) + values[9],
        scale * (x * values[1] + y * values[4] + z * values[7]) + values[10],
        scale * (x * values[2] + y * values[5] + z * values[8]) + values[11],
    )


def _visible_circle_at_height(
    view: Any,
    *,
    component_stem: str,
    height_mm: float,
    target_x_m: float,
    label: str,
    radius_mm: float | None = None,
) -> Any:
    """Resolve a visible circular edge by component identity and native geometry."""
    view = _early_bound(view, "IView")
    full_components: dict[str, Any] = {}
    for raw_drawing_component in _as_tuple(
        view.GetVisibleDrawingComponents(),
        label=f"{label} visible drawing components",
    ):
        drawing_component = _early_bound(raw_drawing_component, "IDrawingComponent")
        component = _early_bound(drawing_component.Component, "IComponent2")
        name = str(component.Name2 or "").rsplit("/", 1)[-1]
        if name in full_components:
            raise RuntimeError(f"{label}: duplicate visible component {name!r}")
        full_components[name] = component

    candidates: list[tuple[tuple[float, ...], Any]] = []
    for visible_component in _as_tuple(
        view.GetVisibleComponents(), label=f"{label} visible components"
    ):
        visible_component = _early_bound(visible_component, "IComponent2")
        if _component_stem(visible_component) != component_stem:
            continue
        name = str(visible_component.Name2 or "").rsplit("/", 1)[-1]
        full_component = full_components.get(name)
        if full_component is None:
            raise RuntimeError(f"{label}: component {name!r} has no full peer")
        for raw_edge in tuple(view.GetVisibleEntities2(visible_component, 1) or ()):
            edge = _early_bound(raw_edge, "IEdge")
            curve = _early_bound(edge.GetCurve(), "ICurve")
            if curve is None or not curve.IsCircle():
                continue
            parameters = tuple(float(value) for value in curve.CircleParams)
            if len(parameters) < 7:
                raise RuntimeError(f"{label}: circular edge has incomplete parameters")
            center = _component_point_in_assembly(full_component, parameters[:3])
            actual_height_mm = center[1] * 1000.0
            actual_radius_mm = parameters[6] * 1000.0
            if abs(actual_height_mm - height_mm) > 1e-5:
                continue
            if radius_mm is not None and abs(actual_radius_mm - radius_mm) > 1e-5:
                continue
            geometry_key = (
                abs(center[0] - target_x_m),
                center[0],
                center[2],
                actual_radius_mm,
                *parameters[:3],
            )
            candidates.append((geometry_key, edge))
    if not candidates:
        radius_detail = "" if radius_mm is None else f", radius {radius_mm:g} mm"
        raise RuntimeError(
            f"{label}: no {component_stem!r} circle at {height_mm:g} mm{radius_detail}"
        )
    candidates.sort(key=lambda item: item[0])
    return candidates[0][1]


def _add_entity_height_dimension(
    adapter: Any,
    view: Any,
    entity0: Any,
    entity1: Any,
    *,
    text_xy: tuple[float, float],
    label: str,
) -> Any:
    draw = adapter.currentModel
    drawing = _early_bound(draw, "IDrawingDoc")
    view = _early_bound(view, "IView")
    if not drawing.ActivateView(str(view.GetName2() or "")):
        raise RuntimeError(f"failed to activate view for {label}")
    draw.ClearSelection2(True)
    selection_manager = _early_bound(draw.SelectionManager, "ISelectionMgr")
    for append, raw_entity in ((False, entity0), (True, entity1)):
        selection_data = _early_bound(
            selection_manager.CreateSelectData(), "ISelectData"
        )
        selection_data.View = view
        if not _early_bound(raw_entity, "IEntity").Select4(append, selection_data):
            raise RuntimeError(f"failed to select exact entity for {label}")
    display = draw.AddVerticalDimension2(text_xy[0], text_xy[1], 0.0)
    draw.ClearSelection2(True)
    draw.EditRebuild3()
    if display is None:
        raise RuntimeError(f"failed to create {label}")
    return display


def _add_frame_height_dimensions(adapter: Any, front: Any) -> tuple[Any, Any]:
    """Add native overall and top-cross-screw setup heights."""
    base_bottom = _visible_circle_at_height(
        front,
        component_stem="harmonic-base",
        height_mm=0.0,
        target_x_m=-_LEFT_COLUMN_X_M,
        label="frame base underside",
    )
    cap_top = _visible_circle_at_height(
        front,
        component_stem="tube-frame-cap",
        height_mm=CAP_TOP_Y,
        target_x_m=-_LEFT_COLUMN_X_M,
        label="finished cap top",
    )
    overall = _add_entity_height_dimension(
        adapter,
        front,
        base_bottom,
        cap_top,
        text_xy=(0.092, 0.244),
        label="finished frame overall height",
    )
    overall = _checked_height_dimension(
        adapter,
        overall,
        expected_mm=CAP_TOP_Y,
        label="finished frame overall height",
    )
    overall = set_reference_dimension(
        adapter,
        _early_bound(overall, "IDisplayDimension").GetAnnotation(),
        label="finished frame overall height reference",
    )

    screw_head = _visible_circle_at_height(
        front,
        component_stem="frame-cross-screw",
        height_mm=TOP_SCREW_Y,
        target_x_m=-_LEFT_COLUMN_X_M,
        radius_mm=CROSS_SCREW_HEAD_DIA / 2.0,
        label="installed top cross-screw head",
    )
    screw_axis = _add_entity_height_dimension(
        adapter,
        front,
        base_bottom,
        screw_head,
        text_xy=(0.086, 0.254),
        label="installed top cross-screw axis height",
    )
    screw_axis = set_arc_endpoints_to_center(
        adapter, screw_axis, label="installed top cross-screw axis height"
    )
    screw_axis = _checked_height_dimension(
        adapter,
        screw_axis,
        expected_mm=TOP_SCREW_Y,
        label="installed top cross-screw axis height",
    )

    # An outside dimension can put its text to either side of the requested
    # anchor. Inspect the native shoulder/witness ink, not that anchor alone.
    drawing = _early_bound(adapter.currentModel, "IDrawingDoc")
    sheet = _early_bound(drawing.GetCurrentSheet(), "ISheet")
    properties = tuple(sheet.GetProperties2())
    region = sheet_drawable_region(
        adapter, sheet, width=float(properties[5]), height=float(properties[6])
    )
    for label, display in (("overall reference", overall), ("top axis", screw_axis)):
        display = _early_bound(display, "IDisplayDimension")
        annotation = _early_bound(display.GetAnnotation(), "IAnnotation")
        data = _early_bound(display.GetDisplayData(), "IDisplayData")
        text_count = int(data.GetTextCount())
        points = []
        for index in range(int(data.GetLineCount())):
            line = tuple(float(value) for value in data.GetLineAtIndex2(index))
            if len(line) < 10:
                raise RuntimeError(f"{label}: incomplete native dimension line")
            points.extend(((line[4], line[5]), (line[7], line[8])))
        if not points or text_count < 1:
            raise RuntimeError(f"{label}: missing native dimension display data")
        bounds = (
            min(point[0] for point in points),
            min(point[1] for point in points),
            max(point[0] for point in points),
            max(point[1] for point in points),
        )
        _telemetry.event(
            "drawing.frame_height_ink",
            label=label,
            annotation_position=tuple(annotation.GetPosition()),
            line_bounds=bounds,
            text=tuple(str(data.GetTextAtIndex(index)) for index in range(text_count)),
            text_positions=tuple(
                float(value)
                for index in range(text_count)
                for value in data.GetTextPositionAtIndex(index)
            ),
            text_heights=tuple(
                float(data.GetTextHeightAtIndex(index)) for index in range(text_count)
            ),
        )
        if (
            bounds[0] < region.xmin - 1e-6
            or bounds[1] < region.ymin - 1e-6
            or bounds[2] > region.xmax + 1e-6
            or bounds[3] > region.ymax + 1e-6
        ):
            raise RuntimeError(
                f"{label}: native dimension ink {bounds!r} crosses {region!r}"
            )
    return overall, screw_axis


def _create_joint_sections(adapter: Any, front: Any) -> tuple[Any, Any]:
    """Cut plan sections through the lower and upper cross-screw axes."""
    bound_front = _early_bound(front, "IView")
    outline = tuple(float(value) for value in bound_front.GetOutline())
    if len(outline) != 4 or outline[0] >= outline[2]:
        raise RuntimeError(f"working front view has invalid outline {outline!r}")
    line_x = (outline[0] - 0.002, outline[2] + 0.002)
    sections = []
    for axis_y_mm, center, section_label, label in (
        (BASE_SCREW_Y, BASE_SECTION_CENTER, "A", "base socket joint"),
        (TOP_SCREW_Y, TOP_SECTION_CENTER, "B", "top socket joint"),
    ):
        cut_y = model_point_in_view(
            adapter,
            front,
            (0.0, axis_y_mm / 1000.0, 0.0),
            label=f"{label} cutting-plane station",
        )[1]
        section = create_section_view(
            adapter,
            front,
            line_start=(line_x[0], cut_y),
            line_end=(line_x[1], cut_y),
            view_xy=center,
            section_label=section_label,
            scale=JOINT_SECTION_SCALE,
            label=label,
        )
        set_hidden_lines_visible(adapter, section)
        sections.append(section)
    return sections[0], sections[1]


def _component_stem(component: Any) -> str:
    component = _early_bound(component, "IComponent2")
    path = str(component.GetPathName() or "")
    if not path:
        raise RuntimeError(f"component {component.Name2!r} has no referenced path")
    return Path(path).stem.casefold()


def _validate_persisted_explode(source_model: Any) -> None:
    """Consume the builder-owned presentation without changing the assembly."""
    assembly = _early_bound(source_model, "IAssemblyDoc")
    manager = _early_bound(source_model.ConfigurationManager, "IConfigurationManager")
    configuration = _early_bound(manager.ActiveConfiguration, "IConfiguration")
    if str(configuration.Name) != SOURCE_CONFIGURATION:
        raise RuntimeError("frame source must open in its Default configuration")
    names = tuple(assembly.GetExplodedViewNames2(SOURCE_CONFIGURATION) or ())
    if names != (EXPLODED_VIEW_NAME,):
        raise RuntimeError(
            f"frame source exploded views {names!r} != {(EXPLODED_VIEW_NAME,)!r}"
        )
    components = tuple(assembly.GetComponents(True) or ())
    if len(components) != sum(BOM_QUANTITIES.values()):
        raise RuntimeError("frame source must contain exactly 29 components")
    for raw_component in components:
        component = _early_bound(raw_component, "IComponent2")
        total = _early_bound(component.GetTotalTransform(True), "IMathTransform")
        base = _early_bound(component.GetTotalTransform(False), "IMathTransform")
        if any(
            abs(float(actual) - float(expected)) > 1e-9
            for actual, expected in zip(total.ArrayData, base.ArrayData, strict=True)
        ):
            raise RuntimeError(
                f"frame source must open collapsed: {component.Name2!r} is displaced"
            )


def _normalized_bom_identity(text: str) -> str:
    normalized = text.strip().casefold()
    return BOM_NORMALIZED_ALIASES.get(normalized, normalized)


def _validate_frame_bom(adapter: Any, table: Any) -> tuple[tuple[str, str], ...]:
    table = _early_bound(table, "ITableAnnotation")
    rows = int(table.RowCount)
    columns = int(table.ColumnCount)
    if rows != len(BOM_COMPONENTS) + 1 or columns < 4:
        raise RuntimeError(
            f"frame BOM is {rows}x{columns}; expected "
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

    def column_named(predicate: Callable[[str], bool], label: str) -> int:
        matches = [index for index, cell in enumerate(header) if predicate(cell)]
        if len(matches) != 1:
            raise RuntimeError(f"frame BOM has no unique {label} column: {header!r}")
        return matches[0]

    item_column = column_named(lambda cell: cell.startswith("ITEM NO"), "ITEM NO.")
    part_column = column_named(lambda cell: cell == "PART NUMBER", "PART NUMBER")
    description_column = column_named(lambda cell: cell == "DESCRIPTION", "DESCRIPTION")
    quantity_column = column_named(lambda cell: cell.startswith("QTY"), "QTY.")
    # Use the portrait sheet width rather than wrapping descriptions into a
    # narrow table over the exploded view. Native minimum heights retain text.
    for column, width in (
        (item_column, 0.022),
        (part_column, 0.038),
        (description_column, 0.162),
        (quantity_column, 0.022),
    ):
        actual_width = float(table.SetColumnWidth(column, width, 0))
        if abs(actual_width - width) > 1e-6:
            raise RuntimeError(f"frame BOM column width did not persist: {column}")
    for row in range(rows):
        table.SetRowHeight(row, 0.006, 0)

    actual: dict[str, tuple[int, str, str, str]] = {}
    for row_index, row in enumerate(contents[1:], start=1):
        stem = _normalized_bom_identity(row[part_column])
        if stem in actual:
            raise RuntimeError(f"frame BOM repeats component family {stem!r}")
        actual[stem] = (
            row_index,
            row[item_column],
            row[description_column],
            row[quantity_column],
        )
    if set(actual) != set(BOM_COMPONENTS):
        raise RuntimeError(
            f"frame BOM identities {sorted(actual)!r} != {sorted(BOM_COMPONENTS)!r}"
        )
    expected_items = {str(item) for item in range(1, len(BOM_COMPONENTS) + 1)}
    actual_items = {values[1] for values in actual.values()}
    if actual_items != expected_items:
        raise RuntimeError(
            f"frame BOM item numbers {sorted(actual_items)!r} != "
            f"{sorted(expected_items)!r}"
        )

    for stem, (row_index, _item, description, quantity) in actual.items():
        expected_part_number = BOM_PART_NUMBERS[stem]
        if contents[row_index][part_column] != expected_part_number:
            if not table.IsCellTextEditable(row_index, part_column):
                raise RuntimeError(
                    f"frame BOM part-number cell for {stem!r} is not editable"
                )
            table.SetText2(row_index, part_column, False, expected_part_number)
            applied = str(
                table.DisplayedText2(row_index, part_column, False) or ""
            ).strip()
            if applied != expected_part_number:
                raise RuntimeError(
                    f"frame BOM part number for {stem!r} did not persist"
                )
        if description != BOM_DESCRIPTIONS[stem]:
            raise RuntimeError(f"frame BOM description mismatch for {stem!r}")
        if quantity != str(BOM_QUANTITIES[stem]):
            raise RuntimeError(
                f"frame BOM quantity for {stem!r} is {quantity!r}, "
                f"expected {BOM_QUANTITIES[stem]}"
            )
    adapter.currentModel.EditRebuild3()
    for stem, (row_index, _item, _description, _quantity) in actual.items():
        applied = str(table.DisplayedText(row_index, part_column) or "").strip()
        if applied != BOM_PART_NUMBERS[stem]:
            raise RuntimeError(
                f"frame BOM part number for {stem!r} reverted to {applied!r}"
            )
    return tuple((stem, actual[stem][1]) for stem in BOM_COMPONENTS)


def _copy_selected_sheet(draw: Any, sheet_name: str, *, label: str) -> None:
    draw.ClearSelection2(True)
    if not draw.Extension.SelectByID2(
        sheet_name,
        "SHEET",
        0.0,
        0.0,
        0.0,
        False,
        0,
        null_callout(),
        0,
    ):
        raise RuntimeError(f"{label}: failed to select sheet {sheet_name!r}")
    draw.EditCopy()


def _paste_blank_sheet(
    adapter: Any, drawing: Any, *, new_name: str, label: str
) -> None:
    drawing = _early_bound(drawing, "IModelDoc2")
    ddoc = _early_bound(drawing, "IDrawingDoc")
    before = tuple(ddoc.GetSheetNames() or ())
    returned = bool(ddoc.PasteSheet(2, 2))  # move to end; preserve view names
    after = tuple(ddoc.GetSheetNames() or ())
    added = tuple(name for name in after if name not in before)
    if len(after) != len(before) + 1 or len(added) != 1:
        raise RuntimeError(
            f"{label}: sheet paste failed (returned={returned!r}, "
            f"before={before!r}, after={after!r})"
        )
    if not returned:
        _telemetry.warn(f"{label}: PasteSheet returned false but created {added[0]!r}")
    if not ddoc.ActivateSheet(added[0]):
        raise RuntimeError(f"{label}: failed to activate pasted sheet {added[0]!r}")
    sheet = _early_bound(ddoc.GetCurrentSheet(), "ISheet")
    sheet.SetName(new_name)
    if str(sheet.GetName() or "") != new_name:
        raise RuntimeError(f"{label}: failed to rename pasted sheet {new_name!r}")


def _activate_frame_package(adapter: Any, target: Any) -> Any:
    target_title = str(target.GetTitle() or "")
    if not target_title:
        raise RuntimeError("frame package drawing has no title")
    activation = adapter.swApp.ActivateDoc3(target_title, False, 2, 0)
    if not activation:
        raise RuntimeError("failed to reactivate frame package drawing")
    activated, errors = activation
    if int(errors) != 0:
        raise RuntimeError(
            f"failed to reactivate frame package drawing (errors={errors})"
        )
    if activated is None:
        activated = adapter.swApp.ActiveDoc
    if activated is None:
        raise RuntimeError("frame package drawing did not become active")
    activated = _early_bound(activated, "IModelDoc2")
    if int(adapter.swApp.IsSame(activated, target)) != 1:
        raise RuntimeError("reactivated document is not the frame package drawing")
    adapter.currentModel = activated
    return activated


def _append_template_sheet(
    adapter: Any,
    target: Any,
    *,
    layout: DrawingLayout,
    new_name: str,
    label: str,
) -> None:
    donor_title = ""
    try:
        donor, donor_sheet = new_project_drawing(
            adapter, layout=layout, scale=SHEET_SCALES[new_name]
        )
        donor = _early_bound(donor, "IModelDoc2")
        donor_sheet = _early_bound(donor_sheet, "ISheet")
        donor_title = str(donor.GetTitle() or "")
        donor_name = str(donor_sheet.GetName() or "")
        if not donor_title or not donor_name:
            raise RuntimeError(f"{label}: donor drawing is incomplete")
        _copy_selected_sheet(donor, donor_name, label=label)
        _activate_frame_package(adapter, target)
        _paste_blank_sheet(
            adapter,
            target,
            new_name=new_name,
            label=label,
        )
    finally:
        primary_error = sys.exception()
        cleanup_error: Exception | None = None
        if donor_title:
            try:
                adapter.swApp.CloseDoc(donor_title)
                _activate_frame_package(adapter, target)
            except Exception as exc:
                cleanup_error = exc
        if cleanup_error is not None:
            if primary_error is None:
                raise cleanup_error
            _telemetry.warn(f"{label}: donor cleanup failed: {cleanup_error}")


def _create_mixed_package_sheets(adapter: Any) -> None:
    """Create landscape/portrait/landscape sheets from the project templates."""
    target, initial = new_project_drawing(
        adapter, layout=SHEET_LAYOUTS[SHEET_NAMES[0]], scale=SHEET_SCALES[SHEET_NAMES[0]]
    )
    target = _early_bound(target, "IModelDoc2")
    initial = _early_bound(initial, "ISheet")
    initial.SetName(SHEET_NAMES[0])
    if str(initial.GetName() or "") != SHEET_NAMES[0]:
        raise RuntimeError("failed to name the frame package primary sheet")

    for sheet_name in SHEET_NAMES[1:]:
        _append_template_sheet(
            adapter,
            target,
            layout=SHEET_LAYOUTS[sheet_name],
            new_name=sheet_name,
            label=f"{sheet_name} frame sheet",
        )

    actual = tuple(_early_bound(target, "IDrawingDoc").GetSheetNames() or ())
    if actual != SHEET_NAMES:
        raise RuntimeError(f"frame package sheet order mismatch: {actual!r}")


def _frame_visible_components(view: Any) -> dict[str, list[tuple[Any, Any]]]:
    full = {}
    for raw in view.GetVisibleDrawingComponents() or ():
        component = _early_bound(
            _early_bound(raw, "IDrawingComponent").Component, "IComponent2"
        )
        full[str(component.Name2).rsplit("/", 1)[-1]] = component
    families: dict[str, list[tuple[Any, Any]]] = {}
    for raw in view.GetVisibleComponents() or ():
        component = _early_bound(raw, "IComponent2")
        name = str(component.Name2).rsplit("/", 1)[-1]
        families.setdefault(_component_stem(component), []).append(
            (component, full[name])
        )
    return families


def _upper_frame_balloon_edges(
    adapter: Any, view: Any, families: dict[str, list[tuple[Any, Any]]]
) -> dict[str, Any]:
    """Choose exposed support-body and screw-head edges, not feet or shanks."""
    winners = {}
    for stem in ("rocker-arm-support", "lag-screw"):
        for component, full in families[stem]:
            name = str(component.Name2)
            for edge in view.GetVisibleEntities2(component, 1) or ():
                key = _edge_endpoint_key(adapter, edge)
                if key is None:
                    continue
                p0 = _component_point_in_assembly(full, key[:3])
                p1 = _component_point_in_assembly(full, key[3:6])
                score = (min(p0[1], p1[1]), -abs(p0[1] - p1[1]), name, *key)
                if stem not in winners or score > winners[stem][0]:
                    winners[stem] = (score, edge)
    if set(winners) != {"rocker-arm-support", "lag-screw"}:
        raise RuntimeError("missing visible upper support-body or screw-head edge")
    return {stem: row[1] for stem, row in winners.items()}


def _bind_left_column_balloon(
    adapter: Any, view: Any, note: Any, item: str,
    components: Sequence[tuple[Any, Any]],
) -> tuple[Any, Any, Any]:
    """Bind to an actual outer tube rim on the open left side of the view."""
    candidates = []
    for component, _full in components:
        rims = []
        for raw_edge in view.GetVisibleEntities2(component, 1) or ():
            curve = _early_bound(
                _early_bound(raw_edge, "IEdge").GetCurve(), "ICurve"
            )
            if not curve.IsCircle():
                continue
            circle = tuple(float(value) for value in curve.CircleParams)
            if abs(abs(circle[4]) - 1.0) < 1e-9:
                rims.append((circle[6], circle[1], raw_edge))
        if not rims:
            continue
        radius = max(row[0] for row in rims)
        rim = max(
            (row for row in rims if abs(row[0] - radius) < 1e-7),
            key=lambda row: row[1],
        )[2]
        note, _annotation, point = _bind_frame_balloon(adapter, view, note, rim, item)
        candidates.append((point[:2], rim))
    if not candidates:
        raise RuntimeError("no visible outer column rim for the BOM balloon")
    rim = min(candidates, key=lambda row: row[0])[1]
    note, annotation, _point = _bind_frame_balloon(adapter, view, note, rim, item)
    return note, annotation, rim


def _exposed_top_casting_edge(
    adapter: Any, view: Any, components: Sequence[tuple[Any, Any]]
) -> Any:
    candidates = []
    for component, full in components:
        for edge in view.GetVisibleEntities2(component, 1) or ():
            curve = _early_bound(_early_bound(edge, "IEdge").GetCurve(), "ICurve")
            if not curve.IsLine():
                continue
            key = _edge_endpoint_key(adapter, edge)
            if key is None:
                continue
            p0 = model_point_in_view(
                adapter,
                view,
                _component_point_in_assembly(full, key[:3]),
                label="top casting edge start",
            )
            p1 = model_point_in_view(
                adapter,
                view,
                _component_point_in_assembly(full, key[3:6]),
                label="top casting edge end",
            )
            length = math.hypot(p1[0] - p0[0], p1[1] - p0[1])
            if length >= 0.003:
                candidates.append(((min(p0[0], p1[0]), length, *key), edge))
    if not candidates:
        raise RuntimeError("top casting has no exposed right-side linear edge")
    return max(candidates, key=lambda row: row[0])[1]


def _frame_balloon_binding_readback(
    adapter: Any, annotation: Any, entity: Any, item: str,
) -> dict[str, Any]:
    """Keep entity, BOM, and leader failures distinct in native diagnostics."""
    note = _early_bound(annotation.GetSpecificAnnotation(), "INote")
    attached = tuple(annotation.GetAttachedEntities3() or ())
    points = tuple(float(value) for value in (annotation.GetLeaderPointsAtIndex(0) or ()))
    same = [int(adapter.swApp.IsSame(actual, entity)) for actual in attached]
    actual_item = str(note.GetBomBalloonText(True) or "").strip()
    dangling = bool(annotation.IsDangling())
    failures = []
    if len(attached) != 1:
        failures.append("entity_count")
    if same != [1]:
        failures.append("entity_identity")
    if actual_item != item:
        failures.append("bom_item")
    if dangling:
        failures.append("dangling")
    if len(points) < 6:
        failures.append("leader_points")
    position = tuple(annotation.GetPosition() or ())
    circle = rendered_balloon_circle(note, label=f"frame balloon {item}")
    return {
        "expected_item": item,
        "actual_item": actual_item,
        "expected_entity_type": type(entity).__name__,
        "actual_entity_types": [type(actual).__name__ for actual in attached],
        "entity_is_same": same,
        "dangling": dangling,
        "actual_leader_points": points,
        "annotation_position": position,
        "rendered_circle": circle,
        "anchor_to_circle_xy": (
            (circle[0] - position[0], circle[1] - position[1])
            if len(position) >= 2 else None
        ),
        "failed_checks": failures,
    }


def _bind_frame_balloon(
    adapter: Any, view: Any, note: Any, entity: Any, item: str
) -> tuple[Any, Any, tuple[float, float, float]]:
    note = _early_bound(note, "INote")
    annotation = _early_bound(note.GetAnnotation(), "IAnnotation")
    if not annotation.SetAttachedEntities(dispatch_array([entity])):
        raise RuntimeError(f"frame balloon {item} rejected its native target")
    adapter.currentModel.EditRebuild3()
    view.UpdateViewDisplayGeometry()
    adapter.currentModel.GraphicsRedraw2()
    note = _early_bound(annotation.GetSpecificAnnotation(), "INote")
    state = _frame_balloon_binding_readback(adapter, annotation, entity, item)
    if state["failed_checks"]:
        raise RuntimeError(f"frame balloon reattachment failed: {state!r}")
    points = state["actual_leader_points"]
    return note, annotation, points[-3:]


def _short_frame_balloon(
    adapter: Any, view: Any, note: Any, item: str, offset: tuple[float, float]
) -> None:
    note = _early_bound(note, "INote")
    annotation = _early_bound(note.GetAnnotation(), "IAnnotation")
    view.UpdateViewDisplayGeometry()
    adapter.currentModel.GraphicsRedraw2()
    attached = tuple(annotation.GetAttachedEntities3() or ())
    if len(attached) != 1:
        raise RuntimeError(f"frame balloon {item} has no unique native attachment")
    entity = attached[0]
    before = _frame_balloon_binding_readback(adapter, annotation, entity, item)
    if before["failed_checks"]:
        raise RuntimeError(f"frame balloon {item} has invalid placement input: {before!r}")
    leader = before["actual_leader_points"]
    # Native readback: the FIRST point meets the balloon; the LAST is the rim/
    # face arrowtip. Sheet XY determines placement and length; Z is view depth.
    target = (leader[-3] + offset[0], leader[-2] + offset[1])
    _telemetry.event("drawing.frame_short_balloon_before", item=item, target=target, **before)
    position_bom_balloon(
        adapter, [note], item_number=item, position_xy=target,
        label="frame short-leader balloon",
    )
    note = _early_bound(annotation.GetSpecificAnnotation(), "INote")
    annotation = _early_bound(note.GetAnnotation(), "IAnnotation")
    view.UpdateViewDisplayGeometry()
    adapter.currentModel.GraphicsRedraw2()
    after = _frame_balloon_binding_readback(adapter, annotation, entity, item)
    leader = after["actual_leader_points"]
    length = sum(
        math.hypot(
            leader[index + 3] - leader[index], leader[index + 4] - leader[index + 1]
        )
        for index in range(0, len(leader) - 3, 3)
    )
    failures = list(after["failed_checks"])
    if length > 0.030:
        failures.append("leader_length")
    circle = after["rendered_circle"]
    if any(abs(circle[index] - target[index]) > 1e-6 for index in range(2)):
        failures.append("circle_position")
    state = {"before": before, "after": after, "target_circle": target,
             "length_m": length, "failed_checks": failures}
    _telemetry.event("drawing.frame_short_balloon", item=item, **state)
    if failures:
        raise RuntimeError(f"frame balloon {item} short placement failed: {state!r}")




def _reattach_frame_balloons(
    adapter: Any, view: Any, balloons: Sequence[Any], items: Sequence[tuple[str, str]]
) -> None:
    families = _frame_visible_components(view)
    anchors = _upper_frame_balloon_edges(adapter, view, families)
    item_by_stem = dict(items)
    notes = {
        _balloon_item_number(adapter, note, label="frame balloon"): note
        for note in balloons
    }
    anchors["top-frame"] = _exposed_top_casting_edge(
        adapter, view, families["top-frame"]
    )
    for stem, entity in anchors.items():
        item = item_by_stem[stem]
        notes[item], _annotation, _point = _bind_frame_balloon(
            adapter, view, notes[item], entity, item
        )

    item = item_by_stem["tube-frame"]
    notes[item], _annotation, _rim = _bind_left_column_balloon(
        adapter, view, notes[item], item, families["tube-frame"]
    )

    item = item_by_stem["frame-cross-screw"]
    shanks = []
    for component, full in families["frame-cross-screw"]:
        if (
            abs(
                _component_point_in_assembly(full, (0.0, 0.0, 0.0))[1] * 1000.0
                - TOP_SCREW_Y
            )
            > 1e-5
        ):
            continue
        for raw_face in view.GetVisibleEntities2(component, 3) or ():
            face = _early_bound(raw_face, "IFace2")
            surface = _early_bound(face.GetSurface(), "ISurface")
            if (
                not surface.IsCylinder()
                or abs(
                    float(surface.CylinderParams[6]) - CROSS_SCREW_SHANK_DIA / 2000.0
                )
                > 1e-7
            ):
                continue
            notes[item], _annotation, point = _bind_frame_balloon(
                adapter, view, notes[item], face, item
            )
            shanks.append(((point[0], point[1]), face))
    if not shanks:
        raise RuntimeError("no visibly exposed upper cross-screw shank")
    # The leftmost native attachment is outside the casting/column silhouettes.
    face = min(shanks, key=lambda row: row[0])[1]
    notes[item], _annotation, _point = _bind_frame_balloon(
        adapter, view, notes[item], face, item
    )

    short = {
        item_by_stem["tube-frame"]: (-0.018, -0.012),
        item_by_stem["top-frame"]: (0.014, 0.010),
        item_by_stem["frame-cross-screw"]: (-0.016, -0.008),
    }
    _spread_balloons(
        adapter,
        view,
        [note for item, note in notes.items() if item not in short],
        margin=0.012,
    )
    for item, offset in short.items():
        _short_frame_balloon(adapter, view, notes[item], item, offset)
    adapter.currentModel.EditRebuild3()


def _place_package(adapter: Any) -> None:
    _create_mixed_package_sheets(adapter)
    for sheet_number, sheet_name in enumerate(SHEET_NAMES, start=1):
        _activate_sheet(adapter, sheet_name)
        sheet = _early_bound(
            _early_bound(adapter.currentModel, "IDrawingDoc").GetCurrentSheet(), "ISheet"
        )
        sheet_scale = SHEET_SCALES[sheet_name]
        if not sheet.SetScale(float(sheet_scale[0]), float(sheet_scale[1]), False, False):
            raise RuntimeError(f"failed to set native frame sheet scale: {sheet_name}")
        _add_note_block(
            adapter,
            f"SHEET {sheet_number} OF {len(SHEET_NAMES)}",
            (0.018, 0.025),
            label="package sheet number",
        )

    _activate_sheet(adapter, SHEET_NAMES[0])
    front = place_view(
        adapter,
        str(SOURCE),
        "*Front",
        *WORKING_FRONT_CENTER,
        scale=SHEET_SCALE,
    )
    _set_exploded_state(adapter, front, False, label="working front")
    set_hidden_lines_visible(adapter, front)
    _add_frame_height_dimensions(adapter, front)
    _create_joint_sections(adapter, front)
    _add_note_block(
        adapter,
        "TOP CROSS-BORE AXIS HEIGHT",
        (0.119, 0.254),
        label="controlling height identity",
    )

    _add_note_block(
        adapter,
        "WORKING POSITION - A-A BASE JOINT / B-B TOP JOINT",
        (0.130, 0.263),
        label="working-view heading",
    )
    _add_note_block(
        adapter,
        "SCALE 1:8",
        (0.030, 0.065),
        label="working-view scale",
    )

    _activate_sheet(adapter, SHEET_NAMES[1])
    exploded = place_view(
        adapter,
        str(SOURCE),
        "*Isometric",
        *EXPLODED_ISO_CENTER,
        scale=EXPLODED_ISO_SCALE,
    )
    _set_exploded_state(adapter, exploded, True, label="exploded isometric")
    set_high_quality_shaded_with_edges(
        adapter, exploded, label="frame exploded anchor visibility"
    )
    table = insert_bom_table(
        adapter,
        exploded,
        anchor_xy=BOM_ANCHOR,
        expected_components=BOM_COMPONENTS,
        descriptions=BOM_DESCRIPTIONS,
        identity_aliases=BOM_IDENTITY_ALIASES,
        configuration_grouping="same-part",
        label="frame",
    )
    balloon_items = _validate_frame_bom(adapter, table)
    balloons = add_component_bom_balloons(
        adapter,
        exploded,
        items=balloon_items,
        label="frame exploded-view BOM coverage",
        margin=0.012,
    )
    _reattach_frame_balloons(adapter, exploded, balloons, balloon_items)
    _add_note_block(
        adapter,
        "EXPLODED VIEW 1:7 - SEE SHEET 3 FOR INSTALLATION ORDER",
        (0.045, 0.075),
        label="exploded-view caption",
    )

    _activate_sheet(adapter, SHEET_NAMES[2])
    instruction_iso = place_view(
        adapter,
        str(SOURCE),
        "*Isometric",
        *ASSEMBLY_ISO_CENTER,
        scale=ASSEMBLY_ISO_SCALE,
    )
    _set_exploded_state(
        adapter, instruction_iso, False, label="assembly instruction isometric"
    )
    _add_note_block(adapter, ASSEMBLY_STEPS, (0.018, 0.263), label="assembly sequence")
    _add_note_block(adapter, ASSEMBLY_CHECKS, (0.018, 0.115), label="assembly checks")
    _add_note_block(
        adapter,
        "FINISHED ASSEMBLY 1:7",
        (0.300, 0.074),
        label="assembly isometric caption",
    )


async def build(adapter: Any) -> dict[str, str]:
    if not SOURCE.is_file():
        raise FileNotFoundError(f"source assembly is missing: {SOURCE}")
    fingerprint = _source_fingerprint(SOURCE)
    check("open frame drawing source", await adapter.open_model(str(SOURCE)))
    source_model = _early_bound(adapter.currentModel, "IModelDoc2")
    if bool(source_model.GetSaveFlag()):
        raise RuntimeError(
            "frame source assembly is already dirty; refusing to discard user changes"
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
        raise RuntimeError("frame source assembly has no document title")

    artifacts: dict[str, str] | None = None
    try:
        _validate_persisted_explode(source_model)
        _place_package(adapter)
        artifacts = await finalize_drawing(
            adapter,
            OUTPUTS,
            layout=SPEC.layout,
            pdf_title="Frame Assembly Drawing Package",
            scale=SHEET_SCALE,
            expected_sheet_names=SHEET_NAMES,
            sheet_layouts=SHEET_LAYOUTS,
            sheet_scales=SHEET_SCALES,
        )
    finally:
        primary_error = sys.exception()
        cleanup_errors: list[str] = []
        # A failed placement leaves an unsaved drawing active. Its views retain
        # the source assembly, so release the drawing before discarding source.
        if artifacts is None:
            try:
                active_model = adapter.currentModel
                if active_model is not None:
                    active_model = _early_bound(active_model, "IModelDoc2")
                    if int(active_model.GetType()) == 3:  # swDocDRAWING
                        drawing_title = str(active_model.GetTitle() or "")
                        if not drawing_title:
                            cleanup_errors.append(
                                "generated frame drawing has no title for close"
                            )
                        else:
                            adapter.swApp.CloseDoc(drawing_title)
            except Exception as exc:  # noqa: BLE001
                cleanup_errors.append(f"failed to close generated frame drawing: {exc}")

        try:
            adapter.swApp.CloseDoc(source_title)
            if adapter.swApp.GetOpenDocumentByName(str(SOURCE.resolve())) is not None:
                cleanup_errors.append(
                    f"frame source {source_title!r} remained open after discard"
                )
        except Exception as exc:  # noqa: BLE001
            cleanup_errors.append(
                f"failed to close frame source {source_title!r}: {exc}"
            )

        try:
            after_fingerprint = _source_fingerprint(SOURCE)
            if after_fingerprint != fingerprint:
                cleanup_errors.append(
                    "frame drawing generation changed the released source assembly "
                    f"(size, mtime_ns, SHA256): {fingerprint!r} -> "
                    f"{after_fingerprint!r}"
                )
        except Exception as exc:  # noqa: BLE001
            cleanup_errors.append(f"failed to verify frame source fingerprint: {exc}")

        if cleanup_errors:
            message = "; ".join(cleanup_errors)
            if primary_error is not None:
                _telemetry.warn(f"frame drawing cleanup after failure: {message}")
            else:
                raise RuntimeError(message)

    if artifacts is None:
        raise RuntimeError("frame drawing package returned no artifacts")
    return artifacts


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[ARTIFACT_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
