r"""Create the native multi-sheet frame assembly drawing package.

The released ``frame.SLDASM`` stays authoritative and byte-for-byte unchanged.
This recipe creates a transient exploded state in the open assembly, uses that
state for one native drawing view, saves the drawing package, and then closes
the dirty source assembly without saving it.
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from pathlib import Path
from typing import Any, Callable, Sequence

import _telemetry
from _common import _early_bound, check, run_build
from _drawing_common import (
    DrawingOutputs,
    add_component_bom_balloons,
    create_section_view,
    finalize_drawing,
    insert_bom_table,
    model_point_in_view,
    new_project_drawing,
    read_required_properties,
    set_arc_endpoints_to_center,
    set_reference_dimension,
    set_hidden_lines_visible,
)
from _drawing_registry import DRAWINGS_BY_NAME, DrawingLayout
from frame_attachment_spec import (
    BASE_SCREW_Y,
    CAP_TOP_Y,
    CASTING_FULL_THREAD_DEPTH,
    CASTING_TAP_DRILL_DEPTH,
    SCREW_SPOTFACE_DIAMETER,
    TOP_SCREW_SEAT_Z,
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
SHEET_SCALE = (1.0, 6.0)
WORKING_FRONT_CENTER = (0.080, 0.155)
BASE_SECTION_CENTER = (0.190, 0.165)
TOP_SECTION_CENTER = (0.325, 0.165)
JOINT_SECTION_SCALE = (1.0, 4.0)
EXPLODED_ISO_CENTER = (0.145, 0.205)
EXPLODED_ISO_SCALE = (1.0, 6.0)
ASSEMBLY_ISO_CENTER = (0.345, 0.145)
ASSEMBLY_ISO_SCALE = (1.0, 10.0)
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

# Distances are drawing-only displacements, not assembly requirements. The
# sequence first moves a part and its fasteners together, then pulls each
# fastener along its actual installation axis so mating faces remain readable.
_EXPLODE_Y = 1
_EXPLODE_X = 0
_EXPLODE_Z = 2
EXPLODE_STEP_COUNT = 12

# These instructions carry only requirements that exist at assembly: matched
# fits, the one-setup coaxial casting threads, transfer-drilled tube holes,
# fitted stock caps, and checks against the actual purchased components. Part
# drawings still define the other manufacturing features.
ASSEMBLY_STEPS = "\n".join(
    (
        "MATCH-FIT AND ASSEMBLY SEQUENCE",
        "PARTS ARRIVE COMPLETE TO THEIR CONTROLLED PART DRAWINGS.",
        "1. COLUMNS OUT: RUN AN ACTUAL MHA-132 THROUGH BOTH CASTING THREAD",
        "   SEGMENTS AT EVERY BASE/TOP SOCKET. EACH HEAD MUST SEAT BEFORE ITS",
        "   TIP BOTTOMS; REMOVE THE SCREWS.",
        "2. DECK UP. ASSIGN EACH MHA-083 TO ONE MHA-035 SOCKET; HAND-FIT TO",
        "   FULL SHOULDER SEATING WITHOUT BIND OR ROCK; MATCH-MARK CORNER/ORIENTATION.",
        "3. RESEAT EACH MATCHED COLUMN. THROUGH THE EXISTING CASTING BORES,",
        "   PILOT-TRANSFER THE LOWER AXIS THROUGH BOTH TUBE WALLS WITH A DRILL",
        "   SMALLER THAN THE 4.0386 TAP MINOR; PROTECT BOTH THREAD SEGMENTS.",
        f"   REMOVE COLUMN; ENLARGE BOTH WALLS TO DIA {TUBE_CROSS_HOLE_DIAMETER:.2f} "
        "AND DEBURR.",
        "   THE ACTUAL MHA-132 SHANK MUST PASS FREELY WITHOUT THREAD CONTACT.",
        "4. FIT MHA-077 OVER ALL COLUMNS, HUB EAST. SET BOTH FRONT AND REAR",
        "   CROSS-BORE AXES TO THE SHEET-1 HEIGHT DIMENSION; CLAMP LEVEL/SQUARE.",
        "   MATCH-MARK EACH TOP CORNER AND COLUMN ORIENTATION.",
        "5. THROUGH THE EXISTING MHA-077 CASTING BORES, PILOT-TRANSFER EACH TOP",
        "   AXIS THROUGH BOTH TUBE WALLS AS STEP 3; PROTECT BOTH THREAD SEGMENTS.",
        f"   REMOVE MHA-077/COLUMNS; ENLARGE BOTH WALLS TO DIA {TUBE_CROSS_HOLE_DIAMETER:.2f},",
        "   DEBURR, AND VERIFY FREE PASSAGE OF THE ACTUAL MHA-132 SHANK.",
        "6. REASSEMBLE MATCHED FRAME. INSTALL EIGHT MHA-132 FROM THEIR MARKED",
        "   ENTRY SIDES; TIGHTEN ONLY UNTIL EVERY HEAD SEATS.",
        "7. VERIFY EACH MHA-077 CAP RECESS CLEARS ITS ACTUAL MHA-133 SKIRT.",
        "   AFTER MATCH MARKS ALIGN AND MHA-132 HEADS SEAT, PUSH EACH CAP OVER",
        "   THE CHAMFERED OPEN END UNTIL THE TUBE REACHES THE CAP'S INSIDE SEAT.",
        "8. SEAT MHA-089 ON DECK, WINDOWS TOWARD LONG SIDES; INSTALL FOUR",
        "   MHA-039 TOP-DOWN AND DRAW DOWN EVENLY.",
        "9. INSTALL MHA-086 DECORATED FACE UP WITH FOUR MHA-030 SCREWS.",
        "10. START MHA-118 IN EAST HUB; LEAVE CUP POINT CLEAR OF GOOSENECK BORE.",
    )
)
ASSEMBLY_CHECKS = "\n".join(
    (
        "ASSEMBLY-ONLY CHECKS",
        "1. ALL BASE/TOP MATCH MARKS ALIGN; COLUMNS ARE FULLY SEATED AND THE",
        "   TOP FRAME IS LEVEL/SQUARE WITH FRONT/REAR AXES AT THE SHEET-1 HEIGHT.",
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
    if str(note.GetText() or "") != text:
        raise RuntimeError(f"{label} text did not persist")
    return note


def _set_exploded_state(adapter: Any, view: Any, show: bool, *, label: str) -> None:
    bound = _early_bound(view, "IView")
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
    if int(display.SetPrecision3(2, -1, -1, -1)) < 0:
        raise RuntimeError(f"failed to set {label} precision")
    if int(display.GetPrimaryPrecision2()) != 2:
        raise RuntimeError(f"{label} did not retain two-place precision")
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
            f"{label}: no {component_stem!r} circle at {height_mm:g} mm"
            f"{radius_detail}"
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
        target_x_m=_LEFT_COLUMN_X_M,
        label="frame base underside",
    )
    cap_top = _visible_circle_at_height(
        front,
        component_stem="tube-frame-cap",
        height_mm=CAP_TOP_Y,
        target_x_m=_LEFT_COLUMN_X_M,
        label="finished cap top",
    )
    overall = _add_entity_height_dimension(
        adapter,
        front,
        base_bottom,
        cap_top,
        text_xy=(0.017, WORKING_FRONT_CENTER[1]),
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
        target_x_m=_LEFT_COLUMN_X_M,
        radius_mm=CROSS_SCREW_HEAD_DIA / 2.0,
        label="installed top cross-screw head",
    )
    screw_axis = _add_entity_height_dimension(
        adapter,
        front,
        base_bottom,
        screw_head,
        text_xy=(0.027, WORKING_FRONT_CENTER[1]),
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


def _component_origin(component: Any) -> tuple[float, float, float]:
    component = _early_bound(component, "IComponent2")
    transform = _early_bound(component.Transform2, "IMathTransform")
    if transform is None:
        raise RuntimeError(f"component {component.Name2!r} has no transform")
    values = tuple(float(value) for value in transform.ArrayData)
    if len(values) != 16:
        raise RuntimeError(
            f"component {component.Name2!r} transform has {len(values)} values"
        )
    return values[9], values[10], values[11]


def _top_level_component_groups(
    assembly: Any,
) -> dict[str, tuple[Any, ...]]:
    assembly = _early_bound(assembly, "IAssemblyDoc")
    expected_total = sum(BOM_QUANTITIES.values())
    count = int(assembly.GetComponentCount(True))
    components = _as_tuple(
        assembly.GetComponents(True), label="frame top-level components"
    )
    if count != expected_total or len(components) != expected_total:
        raise RuntimeError(
            "frame top-level component count mismatch: "
            f"API={count}, returned={len(components)}, expected={expected_total}"
        )
    grouped: dict[str, list[Any]] = {stem: [] for stem in BOM_COMPONENTS}
    unexpected: list[str] = []
    for component in components:
        stem = _component_stem(component)
        if stem not in grouped:
            unexpected.append(stem)
            continue
        grouped[stem].append(component)
    wrong = {
        stem: len(items)
        for stem, items in grouped.items()
        if len(items) != BOM_QUANTITIES[stem]
    }
    if unexpected or wrong:
        raise RuntimeError(
            f"frame component families mismatch: unexpected={unexpected}, counts={wrong}"
        )
    return {stem: tuple(items) for stem, items in grouped.items()}


def _select_explode_components(
    source_model: Any, components: Sequence[Any], *, label: str
) -> tuple[str, ...]:
    source_model.ClearSelection2(True)
    selection_manager = _early_bound(source_model.SelectionManager, "ISelectionMgr")
    selection_data = _early_bound(selection_manager.CreateSelectData(), "ISelectData")
    if selection_data is None:
        raise RuntimeError(f"{label}: failed to create component selection data")
    selection_data.Mark = 1
    if int(selection_data.Mark) != 1:
        raise RuntimeError(f"{label}: selection mark 1 did not persist")
    names: list[str] = []
    for raw_component in components:
        component = _early_bound(raw_component, "IComponent2")
        name = str(component.Name2 or "")
        if not name or not component.Select4(True, selection_data, False):
            raise RuntimeError(f"{label}: failed to select component {name!r}")
        names.append(name)
    if len(names) != len(set(names)):
        raise RuntimeError(f"{label}: duplicate component identities {names!r}")
    return tuple(names)


def _add_native_explode_step(
    source_model: Any,
    configuration: Any,
    *,
    components: Sequence[Any],
    axis: int,
    reverse: bool,
    distance_m: float,
    label: str,
) -> Any:
    if axis not in {_EXPLODE_X, _EXPLODE_Y, _EXPLODE_Z} or distance_m <= 0.0:
        raise ValueError(f"{label}: invalid explode direction or distance")
    expected_names = _select_explode_components(source_model, components, label=label)
    before = int(configuration.GetNumberOfExplodeSteps())
    # AddExplodeStep2's generated early-bound wrapper returns
    # (IExplodeStep, swCreateExplodeStepError_e). The final [out] argument is
    # omitted deliberately; passing a BYREF VARIANT is the wrong convention for
    # InvokeTypes and silently loses the error code.
    result = configuration.AddExplodeStep2(
        float(distance_m),
        int(axis),
        bool(reverse),
        0.0,
        -1,
        False,
        True,
        False,
    )
    source_model.ClearSelection2(True)
    if not isinstance(result, tuple) or len(result) != 2:
        raise RuntimeError(f"{label}: incomplete AddExplodeStep2 result {result!r}")
    raw_step, error = result
    if int(error) != 0 or raw_step is None:
        raise RuntimeError(f"{label}: explode step failed with error {error!r}")
    step = _early_bound(raw_step, "IExplodeStep")
    step.Name = f"FRAME {label.upper()}"
    if str(step.Name or "") != f"FRAME {label.upper()}":
        raise RuntimeError(f"{label}: explode-step name did not persist")
    if not bool(source_model.EditRebuild3()):
        raise RuntimeError(f"{label}: rebuild failed after explode-step creation")
    after = int(configuration.GetNumberOfExplodeSteps())
    if after != before + 1:
        raise RuntimeError(f"{label}: explode-step count {before} -> {after}")
    actual_components = _as_tuple(
        step.GetComponents(), label=f"{label} explode-step components"
    )
    actual_names = {
        str(_early_bound(component, "IComponent2").Name2 or "")
        for component in actual_components
    }
    if actual_names != set(expected_names):
        raise RuntimeError(
            f"{label}: explode components {sorted(actual_names)!r} != "
            f"{sorted(expected_names)!r}"
        )
    if abs(float(step.ExplodeDistance) - distance_m) > 1e-9:
        raise RuntimeError(f"{label}: explode distance did not persist")
    return step


def _create_temporary_native_explode(
    adapter: Any, source_model: Any
) -> tuple[Any, str]:
    assembly = _early_bound(source_model, "IAssemblyDoc")
    configuration_manager = _early_bound(
        source_model.ConfigurationManager, "IConfigurationManager"
    )
    configuration = _early_bound(
        configuration_manager.ActiveConfiguration, "IConfiguration"
    )
    configuration_name = str(configuration.Name or "")
    if not configuration_name:
        raise RuntimeError("frame assembly has no active configuration")
    existing = int(assembly.GetExplodedViewCount2(configuration_name))
    if existing:
        raise RuntimeError(
            f"frame source already carries {existing} exploded view(s); "
            "refusing to alter a released definition"
        )
    if not assembly.CreateExplodedView():
        raise RuntimeError("failed to create transient frame exploded view")
    names = _as_tuple(
        assembly.GetExplodedViewNames2(configuration_name),
        label="frame exploded-view names",
    )
    if len(names) != 1:
        raise RuntimeError(f"frame exploded-view count mismatch: {names!r}")
    explode_name = str(names[0] or "")
    if not explode_name or not assembly.ShowExploded2(True, explode_name):
        raise RuntimeError(f"failed to activate frame exploded view {explode_name!r}")

    # CreateExplodedView can seed heuristic steps. They are unsuitable for a
    # checked package, so remove them before adding the deterministic sequence.
    for index in range(int(configuration.GetNumberOfExplodeSteps()) - 1, -1, -1):
        seed = _early_bound(configuration.GetExplodeStep(index), "IExplodeStep")
        seed_name = str(seed.Name or "") if seed is not None else ""
        if not seed_name or not configuration.DeleteExplodeStep(seed_name):
            raise RuntimeError(f"failed to remove auto explode step {seed_name!r}")
    if int(configuration.GetNumberOfExplodeSteps()) != 0:
        raise RuntimeError("auto explode steps remain before authored sequence")

    groups = _top_level_component_groups(assembly)
    lower_cross_screws: list[Any] = []
    top_cross_screws: list[Any] = []
    front_cross_screws: list[Any] = []
    rear_cross_screws: list[Any] = []
    for component in groups["frame-cross-screw"]:
        _x, y_m, z_m = _component_origin(component)
        y_mm = y_m * 1000.0
        if abs(y_mm - BASE_SCREW_Y) <= 1e-3:
            lower_cross_screws.append(component)
        elif abs(y_mm - TOP_SCREW_Y) <= 1e-3:
            top_cross_screws.append(component)
        else:
            raise RuntimeError(
                f"frame cross screw has unexpected axis height {y_mm:g} mm"
            )
        if z_m < 0.0:
            front_cross_screws.append(component)
        elif z_m > 0.0:
            rear_cross_screws.append(component)
        else:
            raise RuntimeError("frame cross screw lies on the assembly mid-plane")
    if (len(lower_cross_screws), len(top_cross_screws)) != (4, 4):
        raise RuntimeError("frame cross screws do not split into four lower/four top")
    if (len(front_cross_screws), len(rear_cross_screws)) != (4, 4):
        raise RuntimeError("frame cross screws do not split into four front/four rear")

    plans = (
        ("tube caps lift", groups["tube-frame-cap"], _EXPLODE_Y, False, 0.050),
        (
            "top frame clears columns",
            (
                *groups["top-frame"],
                *top_cross_screws,
                *groups["gooseneck-set-screw"],
            ),
            _EXPLODE_Y,
            False,
            0.150,
        ),
        (
            "front cross screws withdraw",
            front_cross_screws,
            _EXPLODE_Z,
            True,
            0.050,
        ),
        (
            "rear cross screws withdraw",
            rear_cross_screws,
            _EXPLODE_Z,
            False,
            0.050,
        ),
        (
            "gooseneck screw withdraws",
            groups["gooseneck-set-screw"],
            _EXPLODE_X,
            True,
            0.050,
        ),
        ("columns clear base seats", groups["tube-frame"], _EXPLODE_Y, False, 0.060),
        (
            "support lifts from deck",
            (*groups["rocker-arm-support"], *groups["lag-screw"]),
            _EXPLODE_Y,
            False,
            0.035,
        ),
        (
            "support moves beside base",
            (*groups["rocker-arm-support"], *groups["lag-screw"]),
            _EXPLODE_X,
            True,
            0.320,
        ),
        ("support screws withdraw", groups["lag-screw"], _EXPLODE_Y, False, 0.050),
        (
            "nameplate lifts from deck",
            (*groups["nameplate"], *groups["fillister-screw"]),
            _EXPLODE_Y,
            False,
            0.025,
        ),
        (
            "nameplate moves beside base",
            (*groups["nameplate"], *groups["fillister-screw"]),
            _EXPLODE_X,
            False,
            0.080,
        ),
        (
            "nameplate screws withdraw",
            groups["fillister-screw"],
            _EXPLODE_Y,
            False,
            0.035,
        ),
    )
    for label, components, axis, reverse, distance_m in plans:
        _add_native_explode_step(
            source_model,
            configuration,
            components=components,
            axis=axis,
            reverse=reverse,
            distance_m=distance_m,
            label=label,
        )
    if int(configuration.GetNumberOfExplodeSteps()) != EXPLODE_STEP_COUNT:
        raise RuntimeError("frame explode sequence did not retain all authored steps")
    if int(assembly.GetExplodedViewCount2(configuration_name)) != 1:
        raise RuntimeError("frame transient exploded-view count changed")
    return assembly, explode_name


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


def _activate_frame_package(adapter: Any, target: Any, target_title: str) -> Any:
    activation = adapter.swApp.ActivateDoc3(target_title, False, 2, 0)
    if not activation:
        raise RuntimeError("failed to reactivate frame package drawing")
    activated, errors = activation
    if activated is None or int(errors) != 0:
        raise RuntimeError(
            f"failed to reactivate frame package drawing (errors={errors})"
        )
    activated = _early_bound(activated, "IModelDoc2")
    if int(adapter.swApp.IsSame(activated, target)) != 1:
        raise RuntimeError("reactivated document is not the frame package drawing")
    adapter.currentModel = activated
    return activated


def _append_template_sheet(
    adapter: Any,
    target: Any,
    target_title: str,
    *,
    layout: DrawingLayout,
    new_name: str,
    label: str,
) -> None:
    donor_title = ""
    try:
        donor, donor_sheet = new_project_drawing(
            adapter, layout=layout, scale=SHEET_SCALE
        )
        donor = _early_bound(donor, "IModelDoc2")
        donor_sheet = _early_bound(donor_sheet, "ISheet")
        donor_title = str(donor.GetTitle() or "")
        donor_name = str(donor_sheet.GetName() or "")
        if not donor_title or not donor_name:
            raise RuntimeError(f"{label}: donor drawing is incomplete")
        _copy_selected_sheet(donor, donor_name, label=label)
        _activate_frame_package(adapter, target, target_title)
        _paste_blank_sheet(
            adapter,
            target,
            new_name=new_name,
            label=label,
        )
    finally:
        primary_error = sys.exception()
        cleanup_error: BaseException | None = None
        if donor_title:
            try:
                _activate_frame_package(adapter, target, target_title)
                adapter.swApp.CloseDoc(donor_title)
            except BaseException as exc:
                cleanup_error = exc
        if cleanup_error is not None:
            if primary_error is None:
                raise cleanup_error
            _telemetry.warn(f"{label}: donor cleanup failed: {cleanup_error}")


def _create_mixed_package_sheets(adapter: Any) -> None:
    """Create landscape/portrait/landscape sheets from the project templates."""
    target, initial = new_project_drawing(
        adapter, layout=SHEET_LAYOUTS[SHEET_NAMES[0]], scale=SHEET_SCALE
    )
    target = _early_bound(target, "IModelDoc2")
    initial = _early_bound(initial, "ISheet")
    initial.SetName(SHEET_NAMES[0])
    if str(initial.GetName() or "") != SHEET_NAMES[0]:
        raise RuntimeError("failed to name the frame package primary sheet")
    target_title = str(target.GetTitle() or "")
    if not target_title:
        raise RuntimeError("frame package drawing has no title")

    for sheet_name in SHEET_NAMES[1:]:
        _append_template_sheet(
            adapter,
            target,
            target_title,
            layout=SHEET_LAYOUTS[sheet_name],
            new_name=sheet_name,
            label=f"{sheet_name} frame sheet",
        )

    actual = tuple(_early_bound(target, "IDrawingDoc").GetSheetNames() or ())
    if actual != SHEET_NAMES:
        raise RuntimeError(f"frame package sheet order mismatch: {actual!r}")


def _place_package(adapter: Any) -> None:
    _create_mixed_package_sheets(adapter)

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
        "WORKING POSITION - A-A BASE JOINT / B-B TOP JOINT",
        (0.018, 0.263),
        label="working-view heading",
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
    add_component_bom_balloons(
        adapter,
        exploded,
        items=balloon_items,
        label="frame exploded-view BOM coverage",
        margin=0.012,
    )
    _add_note_block(
        adapter,
        "EXPLODED VIEW 1:6 - SEE SHEET 3 FOR INSTALLATION ORDER",
        (0.065, 0.080),
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
        "FINISHED ASSEMBLY 1:10",
        (0.300, 0.078),
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

    assembly: Any | None = None
    explode_name = ""
    artifacts: dict[str, str] | None = None
    try:
        assembly, explode_name = _create_temporary_native_explode(adapter, source_model)
        if not assembly.ShowExploded2(False, explode_name):
            raise RuntimeError(
                f"failed to collapse transient exploded view {explode_name!r} "
                "before placing drawing views"
            )
        if not bool(source_model.EditRebuild3()):
            raise RuntimeError("frame source rebuild failed after collapse")
        _place_package(adapter)
        artifacts = await finalize_drawing(
            adapter,
            OUTPUTS,
            layout=SPEC.layout,
            pdf_title="Frame Assembly Drawing Package",
            scale=SHEET_SCALE,
            expected_sheet_names=SHEET_NAMES,
            sheet_layouts=SHEET_LAYOUTS,
        )
    finally:
        primary_error = sys.exception()
        cleanup_errors: list[str] = []
        if assembly is not None and explode_name:
            try:
                if not assembly.ShowExploded2(False, explode_name):
                    cleanup_errors.append(
                        f"failed to collapse transient exploded view {explode_name!r}"
                    )
            except Exception as exc:  # noqa: BLE001
                cleanup_errors.append(
                    f"failed to collapse transient exploded view: {exc}"
                )

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
                cleanup_errors.append(
                    f"failed to close generated frame drawing: {exc}"
                )

        try:
            adapter.swApp.CloseDoc(source_title)
            if adapter.swApp.GetOpenDocumentByName(str(SOURCE.resolve())) is not None:
                cleanup_errors.append(
                    f"frame source {source_title!r} remained open after discard"
                )
        except Exception as exc:  # noqa: BLE001
            cleanup_errors.append(f"failed to close frame source {source_title!r}: {exc}")

        try:
            if _source_fingerprint(SOURCE) != fingerprint:
                cleanup_errors.append(
                    "frame drawing generation changed the released source assembly"
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
