"""Draw the three installed forms from one Precision Matthews clamping kit.

Each explicitly configured member retains its four-view reference content.
REWORK additionally owns the existing HoldDownStud-only native manufacturing
controls; installed acceptance remains in the assembly's HD1-HD4 steps.
The twelve installed members are not twelve procurement units.
"""

from __future__ import annotations

import argparse
import sys
import math
from collections.abc import Callable
from pathlib import Path
from typing import Any

from solidworks_mcp.adapters.solidworks.drawing import (
    add_note, dimension_name, iter_views, place_view, view_name,
)
import _telemetry
from _session import run_build
from _drawing_registry import DRAWINGS_BY_NAME
from _part_properties import part_drawing_unit
from _purchased_variant_drawing import (
    build_purchased_variant_drawing,
    configure_reference_views,
)
from _part_configuration_exports import _sha256
from _com import _bind, _early_bound, _read_member
from _dimensions import _feature_display_dimensions
from _drawing_attachment import (
    _assert_attached_to,
    _assert_leader_lands,
    _is_same_attachment,
)
from _drawing_common import (
    read_required_properties, rebuild_drawing, set_high_quality_shaded_with_edges,
)
from _drawing_dimensions import (
    assert_imported_precision,
    set_dimension_callouts,
    set_reference_dimension,
)
from _drawing_hidden_sketches import curate_view_dimensions
from _drawing_view_display import set_hidden_lines_removed
from _feature_requirements import part_metadata, requirement
from _gtol_cone import ConeFace
from _gtol_cylinder import CylinderFace
from _gtol_planar import PlanarFace
from _printed_limits import limits
from _drawing_edge_dimensions import add_edge_dimension, assert_dimension_measures
from _drawing_edges import face_silhouettes_through, visible_view_entities
from _drawing_projection import model_points_in_view
from _drawing_notes import add_property_linked_note, property_link
from _drawing_selection import _select_view_entity
from _purchased_title_fit import _fit_title_note, assert_linked_value, source_property_expression
from _purchased_fastener_drawing import _box, _inside
import sh_vn_clamping_kit_hold_down_stud_spec as stud
import sh_vn_clamping_kit_t_nut_spec as tnut
import sh_vn_clamping_kit_flange_nut_spec as flange_nut
from ch_rocker_arm_tl_oblique_jig_assembly_spec import HOLD_DOWN_REFERENCE
from _layout_audit import display_box, estimated_text_runs
from _drawing_layout_audit import annotation_display
from _machinist_review_mode import MachinistReviewMode

MACHINIST_REVIEW = MachinistReviewMode.ENFORCE


SPEC = DRAWINGS_BY_NAME["sh_vn_clamping_kit_hardware"]
PART_STEM = SPEC.artifact_stem
SOURCE = SPEC.source
# These declarations describe only the saved/default HoldDownStud STEP. Other
# kit members retain their separately configured reference/export ownership.
FEATURE_SPEC_MODULE = "sh_vn_clamping_kit_hold_down_stud_spec"
# The footer's ITEM row: the catalogue designation in plain text.
ITEM = "52-PIECE CLAMPING KIT, 14 MM T-SLOT, 1/2-13 HARDWARE"
VARIANTS = (
    ("HoldDownStud", "[1] HOLD-DOWN STUD"),
    ("TNut", "[2] T-NUT"),
    ("FlangeNut", "[3] FLANGE NUT"),
)
PURCHASE_UNIT = "52-PIECE KIT"
GENERAL_TEXT = (
    "REFERENCE VIEWS; [2]/[3] AS SUPPLIED; [1] REWORK PER SHEET 2."
)
SHEET_SCALE = (2.0, 1.0)
SHEET_NAMES = ("REWORK",)
FRONT_CENTER = (0.120, 0.150)
END_CENTER = (FRONT_CENTER[0], 0.245)
ISO_CENTER = (0.330, 0.170)
FRONT_KEEP = {"FinishedLength": (0.060, FRONT_CENTER[1])}
END_KEEP: dict[str, tuple[float, float]] = {}
# The side-view attached callout reads this unchanged native source control;
# no duplicate imported chamfer dimension is printed in the end view.
END_VIEW_LABEL = "CUT END VIEW"
END_VIEW_LABEL_XY = (0.092, 0.224)
# Sheet 1's item label, in the same top band; right of the cut-end view.
# Sheet 1 carries the quantity, so this sheet needs no registry read.
ITEM_LABEL = VARIANTS[0][1]
ITEM_LABEL_XY = (0.150, 0.262)
STOCK_NOTE_XY = (0.025, 0.077)
THREAD_NOTE_XY = (0.065, 0.180)
THREAD_CALLOUT = f"{stud.THREAD}\nEXISTING THREAD\nNOT MODELLED"
LOWER_END_NOTE_XY = (0.155, 0.083)
CHAMFER_NOTE_XY = (0.155, 0.225)
ASSEMBLY_REFERENCE_XY = (0.025, 0.056)
STUD_REWORK_PROPERTIES = {
    "Stock Length": f"{stud.STOCK_LENGTH} IN STOCK",
    "Stock Note": stud.STOCK_NOTE,
    "Lower End Note": stud.LOWER_END_NOTE,
}
REQUIRED_PROPERTIES = (
    "Number", "Material Specification", "Finish", "Quantity", "Stock Name",
    "Supplier", "Supplier SKUs",
    *(f"{stud.CONFIGURATION} Rework {name}" for name in STUD_REWORK_PROPERTIES),
)


class _CutEndCone(ConeFace):
    """Disambiguate the coaxial factory and cut-end cones on the unchanged Y axis."""

    def matches(self, geometry) -> bool:
        return (
            super().matches(geometry)
            and len(geometry.box) == 6
            and abs(geometry.box[4] * 1000.0 - stud.LENGTH) <= self.tolerance_mm
        )


part_metadata(
    precision_sources=("DRAWING_PRECISION_BY_NAME",),
    fields={
        "volume_mm3": (stud.VOLUME_MM3, ("VOLUME_MM3",)),
        "material.finish": (stud.FINISH, ("FINISH",)),
        "notes.process": (stud.PROCESS, ("PROCESS",)),
    },
)
requirement(
    "finished_upper_end", kind="face",
    faces=(PlanarFace((0.0, 1.0, 0.0), stud.LENGTH),),
    requirements=("length", "note"),
    fields={
        "normal": ([0.0, 1.0, 0.0], ("__frame__",)),
        "length": (
            limits(stud.LENGTH, stud.LENGTH_PLACES, unit=stud.UNIT),
            ("LENGTH", "LENGTH_BAND"),
        ),
        "length_nominal": (stud.LENGTH, ("LENGTH",)),
        "note": (stud.DIMENSION_CALLOUTS["FinishedLength"], ("DIMENSION_CALLOUTS",)),
    },
    precision={"length": stud.LENGTH_PLACES},
)
requirement(
    "cut_end_chamfer", kind="chamfer", faces=(_CutEndCone(45.0),),
    requirements=("length", "note"),
    fields={
        "at": ([0.0, stud.LENGTH, 0.0], ("LENGTH", "__frame__")),
        "axis": ([0.0, 1.0, 0.0], ("__frame__",)),
        "length": ([0.0, stud.CUT_END_CHAMFER_MAX], ("CUT_END_CHAMFER_MAX",)),
        "length_nominal": (stud.CUT_END_CHAMFER_MAX, ("CUT_END_CHAMFER_MAX",)),
        "note": (stud.DIMENSION_CALLOUTS["CutEndChamfer"], ("DIMENSION_CALLOUTS",)),
    },
    precision={"length": stud.CUT_END_CHAMFER_PLACES},
)


def _visible_circular_rim(
    view: Any, *, y_mm: float, radius_mm: float, label: str
) -> Any:
    """Identify one actual +Y-axis rim; never attach to a projected centre."""
    centre = (0.0, y_mm / 1000.0, 0.0)
    radius = radius_mm / 1000.0
    matches = []
    for raw_edge in visible_view_entities(view, 1, label=label):
        edge = _early_bound(raw_edge, "IEdge")
        raw_curve = edge.GetCurve()
        if raw_curve is None:
            continue
        curve = _early_bound(raw_curve, "ICurve")
        if not curve.IsCircle():
            continue
        params = curve.CircleParams  # centre xyz, axis xyz, radius; metres
        if params is None or len(params) != 7:
            continue
        values = tuple(float(value) for value in params)
        if (
            all(math.isclose(value, expected, abs_tol=1e-9) for value, expected in zip(values[:3], centre))
            and math.isclose(abs(values[4]), 1.0, abs_tol=1e-9)
            and all(math.isclose(values[index], 0.0, abs_tol=1e-9) for index in (3, 5))
            and math.isclose(values[6], radius, abs_tol=1e-9)
        ):
            matches.append(edge)
    if len(matches) != 1:
        raise RuntimeError(f"{label}: expected one visible native rim, found {len(matches)}")
    return matches[0]


def lower_factory_end_edge(view: Any) -> Any:
    """The unmodified factory end-face rim, not the similarly sized cut end."""
    return _visible_circular_rim(
        view, y_mm=0.0,
        radius_mm=stud.RADIUS - stud.LOWER_FACTORY_CHAMFER,
        label="stud lower factory rim",
    )


def upper_cut_end_edge(view: Any) -> Any:
    """Prove the permanent end view exposes the new +Y face, not the factory end."""
    return _visible_circular_rim(
        view, y_mm=stud.LENGTH,
        radius_mm=stud.RADIUS - stud.CUT_END_CHAMFER_MAX,
        label="stud cut-end rim",
    )


def upper_cut_chamfer_edge(view: Any) -> Any:
    """The actual upper bevel/barrel boundary, not the factory or end-face rim."""
    return _visible_circular_rim(
        view, y_mm=stud.LENGTH - stud.CUT_END_CHAMFER_MAX,
        radius_mm=stud.RADIUS,
        label="stud upper cut-end chamfer boundary",
    )


def add_rework_notes(adapter: Any, front: Any) -> Callable[[], None]:
    """Place native leaders on the factory end, thread blank and upper chamfer.

    Native b9e4d6b45bbb exposes the barrel silhouette only on model -X:
    its sheet line is X107.3, Y94.8..205.2 mm, not the +X contour. Keep
    that proven entity and select its midspan, independently checking both
    native attachment and leader landing; no alternate-entity fallback.
    """
    lower_radius = stud.RADIUS - stud.LOWER_FACTORY_CHAMFER
    lower_x = lower_radius / 2.0
    barrel_y = (
        stud.LOWER_FACTORY_CHAMFER + stud.LENGTH - stud.CUT_END_CHAMFER_MAX
    ) / 2.0
    source_model = _early_bound(front.ReferencedDocument, "IModelDoc2")
    angle = read_saved_cut_end_angle(source_model)
    chamfer_text = stud.cut_end_chamfer_callout(angle)
    model_points = (
        (lower_x / 1000.0, 0.0, math.sqrt(lower_radius**2 - lower_x**2) / 1000.0),
        (-stud.RADIUS / 1000.0, barrel_y / 1000.0, 0.0),
        (
            stud.RADIUS / 1000.0,
            (stud.LENGTH - stud.CUT_END_CHAMFER_MAX) / 1000.0,
            0.0,
        ),
    )
    points = model_points_in_view(
        adapter, front, model_points, label="stud native note landings",
    )
    lower_rim = lower_factory_end_edge(front)
    chamfer_rim = upper_cut_chamfer_edge(front)
    thread_flank = face_silhouettes_through(
        adapter, front,
        {"thread": (CylinderFace(stud.MAJOR_DIA, contains_y_mm=barrel_y), points[1])},
        label="stud existing thread blank",
    )["thread"]
    records = []
    for text, entity, kind, point, note_xy, label, printed in (
        (
            property_link(f"{stud.CONFIGURATION} Rework Lower End Note"),
            lower_rim, "EDGE", points[0],
            LOWER_END_NOTE_XY, "unmodified lower factory end", stud.LOWER_END_NOTE,
        ),
        (
            THREAD_CALLOUT, thread_flank, "SILHOUETTE", points[1],
            THREAD_NOTE_XY, "existing hold-down stud thread", THREAD_CALLOUT,
        ),
        (
            chamfer_text, chamfer_rim, "EDGE", points[2],
            CHAMFER_NOTE_XY, "upper cut-end chamfer", chamfer_text,
        ),
    ):
        # Select the resolved native entity before setting the selection point:
        # the historical sheet-coordinate EDGE hit-test failed for this rim.
        _select_view_entity(adapter, front, kind, None, label=label, entity=entity)
        drawing = adapter.currentModel
        manager = _early_bound(drawing.SelectionManager, "ISelectionMgr")
        if manager.SetSelectionPoint2(1, -1, point[0], point[1], 0.0) is not True:
            raise RuntimeError(f"{label}: failed to set the native selection point")
        note = drawing.InsertNote(text)
        if note is None:
            raise RuntimeError(f"{label}: failed to insert the native note")
        annotation = _early_bound(_early_bound(note, "INote").GetAnnotation(), "IAnnotation")
        if annotation is None:
            raise RuntimeError(f"{label}: native note has no annotation")
        if annotation.SetLeader3(1, 0, True, False, False, False) != 0:
            raise RuntimeError(f"{label}: failed to create the native leader")
        if not annotation.SetPosition2(note_xy[0], note_xy[1], 0.0):
            raise RuntimeError(f"{label}: failed to position the native note")
        rebuild_drawing(adapter, label=label)
        _assert_attached_to(
            adapter, annotation, entity, entity_type=kind,
            what="attached note", label=label,
        )
        _assert_leader_lands(annotation, point, what="attached note", label=label)
        records.append((_early_bound(note, "INote"), annotation, entity, kind, label, printed))
        drawing.ClearSelection2(True)

    def settled() -> None:
        read_saved_cut_end_angle(source_model)
        current_points = model_points_in_view(
            adapter, front, model_points, label="stud settled native note landings",
        )
        for (note, annotation, entity, kind, label, printed), point in zip(records, current_points, strict=True):
            owner = annotation.Owner
            if (
                int(annotation.OwnerType) != 0 or owner is None
                or view_name(adapter, _early_bound(owner, "IView")) != view_name(adapter, front)
                or str(note.GetText() or "").replace("\r\n", "\n") != printed
            ):
                raise RuntimeError(f"{label}: native note text or drawing-view ownership changed")
            _assert_attached_to(
                adapter, annotation, entity, entity_type=kind,
                what="attached note", label=label,
            )
            _assert_leader_lands(annotation, point, what="attached note", label=label)

    settled()
    return settled


def fit_stud_title_block(
    adapter: Any, *, sheet_name: str, number: str
) -> Callable[[], None]:
    """Fit only the complete source-linked Name/Number in their native cells."""
    drawing = _early_bound(adapter.currentModel, "IModelDoc2")
    document = _early_bound(drawing, "IDrawingDoc")
    sheet = _early_bound(document.GetCurrentSheet(), "ISheet")
    sheet_view = _early_bound(document.GetFirstView(), "IView")
    if sheet is None or sheet_view is None:
        raise RuntimeError("stud title block has no native sheet or sheet view")
    fields = {
        property_link("SW-Title(Title)"): ("Name", PART_STEM),
        property_link("Number"): ("DWG. NO.", number),
    }
    found: dict[str, list[Any]] = {expression: [] for expression in fields}
    note = sheet_view.GetFirstNote2()
    while note is not None:
        note = _early_bound(note, "INote")
        expression = source_property_expression(str(note.PropertyLinkedText))
        if expression in found:
            found[expression].append(note)
        note = note.GetNext()
    counts = {expression: len(notes) for expression, notes in found.items()}
    if any(count != 1 for count in counts.values()):
        raise RuntimeError(f"stud title block requires one note per source field: {counts!r}")
    checks = []
    for expression, (label, expected) in fields.items():
        note = found[expression][0]
        assert_linked_value(
            expression, expected, str(note.PropertyLinkedText), str(note.GetText()),
            label=f"{sheet_name} {label}",
        )
        checks.append(_fit_title_note(
            adapter, drawing, sheet, note, label=f"{sheet_name} {label}", minimum=0.003,
        ))

    def settled() -> None:
        if not document.ActivateSheet(sheet_name):
            raise RuntimeError(f"failed to activate stud title-check sheet {sheet_name!r}")
        for check_title in checks:
            check_title()

    return settled


def link_rework_material(
    adapter: Any, *, sheet_name: str, material: str
) -> Callable[[], None]:
    """Print the stud's Material Specification in REWORK's MATERIAL cell.

    Sheet 1 (_purchased_variant_drawing) prints the kit's Material
    Specification; this sheet's template cell linked the SOLIDWORKS library
    stand-in ("Plain Carbon Steel"), so the two sheets named two materials
    for the stud being cut (machinist review, 3/3 runs). Only this drawing's
    note link changes; the source model and saved template stay untouched.
    """
    document = _early_bound(adapter.currentModel, "IDrawingDoc")
    sheet_view = _early_bound(document.GetFirstView(), "IView")
    stand_in, specification = property_link("Material"), property_link("Material Specification")
    found = []
    note = sheet_view.GetFirstNote2()
    while note is not None:
        note = _early_bound(note, "INote")
        if source_property_expression(str(note.PropertyLinkedText)) == stand_in:
            found.append(note)
        note = note.GetNext()
    if len(found) != 1:
        raise RuntimeError(f"stud REWORK title block needs one MATERIAL link, found {len(found)}")
    (note,) = found
    note.PropertyLinkedText = str(note.PropertyLinkedText).replace(stand_in, specification)
    rebuild_drawing(adapter, label="stud REWORK material link")

    def settled() -> None:
        if not document.ActivateSheet(sheet_name):
            raise RuntimeError(f"failed to activate stud material-check sheet {sheet_name!r}")
        assert_linked_value(
            specification, material, str(note.PropertyLinkedText), str(note.GetText()),
            label=f"{sheet_name} MATERIAL",
        )

    settled()
    return settled


def read_saved_cut_end_angle(model: Any) -> float:
    """Read the saved HoldDownStud feature, without retargeting the drawing.

    The shared adapter owns a drawing here. Resolve its explicitly configured
    view's referenced part using the same IPartDoc lookup as the supplier guards.
    EdgeChamferAngle is radians; angle-distance uses leg zero.
    Bind raw native feature-display dispatches before checking source identity
    and precision; _early_bound alone does not wrap those raw objects.
    """
    part = _early_bound(model, "IPartDoc")
    feature = part.FeatureByName("CutEndChamfer")
    if feature is None:
        raise RuntimeError("cut-end chamfer: saved native feature is missing")
    feature = _early_bound(feature, "IFeature")
    definition = feature.GetDefinition()
    if definition is None:
        raise RuntimeError("cut-end chamfer: saved native definition is missing")
    definition = _early_bound(definition, "IChamferFeatureData2")
    if int(definition.Type) != 1:  # swChamferAngleDistance
        raise RuntimeError("cut-end chamfer: saved native type is not angle-distance")
    angle = definition.EdgeChamferAngle
    expected = math.radians(stud.CUT_END_CHAMFER_ANGLE_DEG)
    if not math.isclose(float(angle), expected, abs_tol=1e-9):
        raise RuntimeError(
            f"cut-end chamfer: native feature angle expected={expected!r} rad, "
            f"actual={angle!r} ({type(angle).__name__})"
        )
    distance = float(definition.GetEdgeChamferDistance(0))
    if not math.isclose(distance, stud.CUT_END_CHAMFER_MAX / 1000.0, abs_tol=1e-9):
        raise RuntimeError(f"cut-end chamfer: native feature distance changed: {distance!r} m")
    _telemetry.info(f"cut-end chamfer: saved native angle={angle!r} rad, distance={distance!r} m")
    dimension = _early_bound(model, "IModelDoc2").Parameter("CutEndChamfer@CutEndChamfer")
    if dimension is None:
        raise RuntimeError("cut-end chamfer: saved native dimension is missing")
    dimension = _early_bound(dimension, "IDimension")
    full_name = str(dimension.FullName or "")
    qualified = full_name.split("@")
    nominal = stud.CUT_END_CHAMFER_MAX / 1000.0
    tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
    if (
        len(qualified) != 3 or qualified[:2] != ["CutEndChamfer", "CutEndChamfer"]
        or not qualified[2] or int(dimension.DrivenState) != 2
        or not math.isclose(float(dimension.SystemValue), nominal, abs_tol=1e-9)
        or int(tolerance.Type) != stud.DIMENSION_TOLERANCE_TYPES["CutEndChamfer"]
        or not math.isclose(float(tolerance.GetMinValue()), -nominal, abs_tol=1e-12)
        or not math.isclose(float(tolerance.GetMaxValue()), 0.0, abs_tol=1e-12)
    ):
        raise RuntimeError("cut-end chamfer: native source identity, driver or MAX band changed")
    displays = []
    for raw in _feature_display_dimensions(feature):
        display = _bind(raw, "IDisplayDimension")
        candidate = _early_bound(display.GetDimension2(0), "IDimension")
        if str(candidate.FullName or "") == full_name:
            displays.append(display)
    if (
        len(displays) != 1
        or int(displays[0].GetPrimaryPrecision2()) != stud.CUT_END_CHAMFER_PLACES
    ):
        raise RuntimeError("cut-end chamfer: native source precision changed")
    return float(angle)


def set_machining_callouts(adapter: Any, annotations: list[Any]) -> None:
    """Read back the printed length callout without replacing its native size."""
    callouts = {"FinishedLength": stud.DIMENSION_CALLOUTS["FinishedLength"]}
    set_dimension_callouts(adapter, annotations, callouts)
    remaining = dict(callouts)
    for annotation in annotations:
        name = dimension_name(adapter, annotation)
        expected = remaining.pop(name, None)
        if expected is None:
            continue
        display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
        if display.GetText(4) != expected:  # swDimensionTextCalloutBelow
            raise RuntimeError(f"{name}: native machining callout did not persist")
    if remaining:
        raise RuntimeError(f"missing native machining callouts: {sorted(remaining)}")


def assert_machining_controls(adapter: Any, annotations: list[Any]) -> None:
    """Read the printed source-owned length driver, precision and tolerance."""
    remaining = {
        "FinishedLength": stud.LENGTH / 1000.0,
    }
    for annotation in annotations:
        name = dimension_name(adapter, annotation)
        if name not in remaining:
            raise RuntimeError(f"unexpected or duplicate stud control {name!r}")
        nominal = remaining.pop(name)
        display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
        dimension = _early_bound(display.GetDimension2(0), "IDimension")
        full_name = dimension.FullName
        qualified_name = full_name.split("@") if type(full_name) is str else []
        feature = next(
            feature for feature, names in stud.DRAWING_DIMENSIONS.items()
            if name in names
        )
        if (
            len(qualified_name) != 3
            or qualified_name[:2] != [name, feature]
            or not qualified_name[2]
        ):
            raise RuntimeError(f"{name}: native source feature changed: {full_name!r}")
        tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
        primary_value = dimension.SystemValue
        if int(dimension.DrivenState) != 2 or not math.isclose(
            float(primary_value), nominal, abs_tol=1e-9
        ):
            raise RuntimeError(f"{name}: native machining driver changed")
        if "(" in str(display.GetText(1) or "") or ")" in str(display.GetText(2) or ""):
            raise RuntimeError(f"{name}: machining control is displayed reference-only")
        if int(tolerance.Type) != stud.DIMENSION_TOLERANCE_TYPES[name]:
            raise RuntimeError(f"{name}: native tolerance type changed")
    if remaining:
        raise RuntimeError(f"missing native stud controls: {sorted(remaining)}")
    assert_imported_precision(
        adapter, annotations,
        {name: stud.DRAWING_PRECISION_BY_NAME[name] for name in FRONT_KEEP},
    )


def assert_rework_view_controls(adapter: Any, front: Any, end: Any) -> None:
    """Reacquire exact controls from their supported, permanent native owners."""
    expected = {
        view_name(adapter, front): ("*Front", set(FRONT_KEEP)),
        view_name(adapter, end): ("*Top", set(END_KEEP)),
    }
    if len(expected) != 2 or "" in expected:
        raise RuntimeError("stud machining views require two distinct native names")
    found: set[str] = set()
    annotations = []
    for raw_view in iter_views(adapter):
        view = _early_bound(raw_view, "IView")
        name = view_name(adapter, view)
        names = []
        for raw in view.GetAnnotations() or ():
            annotation = _early_bound(raw, "IAnnotation")
            control = dimension_name(adapter, annotation)
            if control not in stud.DIMENSION_TOLERANCE_TYPES:
                continue
            owner = annotation.Owner
            if (
                int(annotation.OwnerType) != 0  # swAnnotationOwner_DrawingView
                or owner is None
                or view_name(adapter, _early_bound(owner, "IView")) != name
            ):
                raise RuntimeError(f"{control}: native drawing-view owner changed")
            names.append(control)
            annotations.append(annotation)
        if name in expected:
            orientation, keep = expected[name]
            if view.GetOrientationName() != orientation:
                raise RuntimeError(f"{name}: stud machining-view orientation changed")
            if name in found or sorted(names) != sorted(keep):
                raise RuntimeError(f"{name}: native machining-control census changed: {names!r}")
            found.add(name)
        elif names:
            raise RuntimeError(f"{name}: unexpected native stud controls: {names!r}")
    if found != set(expected):
        raise RuntimeError("stud machining-control view is missing")
    upper_cut_end_edge(end)
    assert_machining_controls(adapter, annotations)
    read_saved_cut_end_angle(_early_bound(front.ReferencedDocument, "IModelDoc2"))
    _telemetry.info(
        "stud machining owner: FinishedLength@StudProfile in "
        f"{view_name(adapter, front)} (*Front); upper chamfer source-only, "
        f"visible cut-end rim in {view_name(adapter, end)} at Y={stud.LENGTH} mm"
    )




def _assert_stud_rework_properties(model: Any) -> dict[str, str]:
    properties = read_required_properties(
        model, REQUIRED_PROPERTIES, required=REQUIRED_PROPERTIES
    )
    for name, expected in STUD_REWORK_PROPERTIES.items():
        if properties[f"{stud.CONFIGURATION} Rework {name}"] != expected:
            raise RuntimeError(f"stud rework: stale source-linked {name!r}")
    for name, expected in {
        **STUD_REWORK_PROPERTIES,
        "Number": properties["Number"],
        "Quantity": str(stud.QUANTITY),
        "Material Specification": properties["Material Specification"],
        "Process": stud.PROCESS,
        "Finish": stud.FINISH,
        "Tolerance Class": stud.TOLERANCE_CLASS,
    }.items():
        actual = str(model.GetCustomInfoValue(stud.CONFIGURATION, name) or "")
        if actual.replace("\r\n", "\n") != expected.replace("\r\n", "\n"):
            raise RuntimeError(f"stud rework: native member {name!r} changed")
    return properties


def append_stud_rework_sheets(adapter: Any) -> tuple[Callable[[], None], ...]:
    """Append final branch part-only REWORK; assembly HD1-HD4 owns installed fit."""
    document = _early_bound(adapter.currentModel, "IDrawingDoc")
    if not document.ActivateSheet(SHEET_NAMES[0]):
        raise RuntimeError("failed to activate stud REWORK sheet")
    front = place_view(adapter, str(SOURCE), "*Front", *FRONT_CENTER, scale=SHEET_SCALE)
    end = place_view(adapter, str(SOURCE), "*Top", *END_CENTER, scale=SHEET_SCALE)
    iso = place_view(adapter, str(SOURCE), "*Isometric", *ISO_CENTER, scale=SHEET_SCALE)
    rework_views = [front, end, iso]
    configure_reference_views(adapter, stud.CONFIGURATION, rework_views)
    source_model = _early_bound(front.ReferencedDocument, "IModelDoc2")
    source_properties = _assert_stud_rework_properties(source_model)
    for view in rework_views:
        set_hidden_lines_removed(adapter, view)
    front_annotations = curate_view_dimensions(
        adapter, front, keep=FRONT_KEEP,
        view_label="finished length from unchanged lower end",
        dimensions_by_feature=stud.DRAWING_DIMENSIONS,
    )
    end_annotations = curate_view_dimensions(
        adapter, end, keep=END_KEEP, view_label="permanent upper cut-end view",
        dimensions_by_feature=stud.DRAWING_DIMENSIONS,
    )
    annotations = [*front_annotations, *end_annotations]
    assert_machining_controls(adapter, annotations)
    set_machining_callouts(adapter, annotations)
    if add_note(adapter, END_VIEW_LABEL, *END_VIEW_LABEL_XY) is None:
        raise RuntimeError("failed to label the permanent stud cut-end view")
    if add_note(adapter, ITEM_LABEL, *ITEM_LABEL_XY) is None:
        raise RuntimeError("failed to label the stud REWORK sheet's item")
    settled_notes = add_rework_notes(adapter, front)
    add_property_linked_note(
        adapter, f"{stud.CONFIGURATION} Rework Stock Note", *STOCK_NOTE_XY
    )
    if add_note(
        adapter, f"INSTALLED ACCEPTANCE:\n{HOLD_DOWN_REFERENCE}",
        *ASSEMBLY_REFERENCE_XY,
    ) is None:
        raise RuntimeError("failed to add the hold-down assembly acceptance reference")
    assert_rework_view_controls(adapter, front, end)

    def settled() -> None:
        if not document.ActivateSheet(SHEET_NAMES[0]):
            raise RuntimeError("failed to read stud REWORK controls")
        for view in rework_views:
            if (
                str(view.ReferencedConfiguration) != stud.CONFIGURATION
                or Path(view.GetReferencedModelName()).resolve() != SOURCE.resolve()
                or tuple(view.ScaleRatio) != SHEET_SCALE
            ):
                raise RuntimeError("stud rework view source/configuration/scale changed")
        _assert_stud_rework_properties(_early_bound(front.ReferencedDocument, "IModelDoc2"))
        assert_rework_view_controls(adapter, front, end)
        settled_notes()

    return (
        settled,
        fit_stud_title_block(
            adapter, sheet_name=SHEET_NAMES[0], number=source_properties["Number"],
        ),
        link_rework_material(
            adapter, sheet_name=SHEET_NAMES[0],
            material=source_properties["Material Specification"],
        ),
    )


def _measured_display_box(rendered: dict[str, Any]) -> Any:
    """Normalize swTextPosition_e anchors before the lower-left ink boxer."""
    texts = []
    for item in rendered.get("texts", ()):
        width, height = float(item.get("w", 0)), float(item.get("h", 0))
        reference = int(item.get("ref", -1))
        position = tuple(float(value) for value in item.get("pos", ()))
        angle = float(item.get("ang", 0))
        if (
            min(width, height) <= 0
            or reference not in range(6)
            or len(position) < 2
            or not all(
                math.isfinite(value) for value in (width, height, angle, *position)
            )
        ):
            raise RuntimeError("kit: native rendered text geometry is unreadable")
        # swUPPER_LEFT, LOWER_LEFT, CENTER, UPPER_RIGHT, LOWER_RIGHT, UPPER_CENTER.
        dx, dy = (
            (0, -height),
            (0, 0),
            (-width / 2, -height / 2),
            (-width, -height),
            (-width, 0),
            (-width / 2, -height),
        )[reference]
        cosine, sine = math.cos(angle), math.sin(angle)
        texts.append(
            {
                **item,
                "ref": 1,
                "pos": (
                    position[0] + dx * cosine - dy * sine,
                    position[1] + dx * sine + dy * cosine,
                    0.0,
                ),
            }
        )
    return display_box({**rendered, "texts": texts})


def _stud_length_reference(
    adapter: Any, cells: tuple, views: list[Any]
) -> Callable[[], None]:
    """Measure the revolved model's two end rims, not its shorter straight land."""
    front = views[0]
    rims = []
    for raw in visible_view_entities(front, 1, label="kit stud end rims"):
        edge = _early_bound(raw, "IEdge")
        curve = _early_bound(edge.GetCurve(), "ICurve")
        if curve is None or curve.IsCircle() is not True:
            continue
        params = tuple(float(value) for value in curve.CircleParams)
        if (
            len(params) == 7
            and math.isclose(params[0], 0.0, abs_tol=1e-9)
            and math.isclose(params[2], 0.0, abs_tol=1e-9)
            and math.isclose(abs(params[4]), 1.0, abs_tol=1e-9)
            and any(
                math.isclose(params[1] * 1000, station, abs_tol=1e-5)
                and math.isclose(params[6] * 1000, radius, abs_tol=1e-5)
                for station, radius in (
                    (0.0, stud.RADIUS - stud.LOWER_FACTORY_CHAMFER),
                    (stud.LENGTH, stud.RADIUS - stud.CUT_END_CHAMFER_MAX),
                )
            )
        ):
            rims.append((params[1], edge))
    rims.sort(key=lambda item: item[0])
    if len(rims) != 2:
        raise RuntimeError("kit stud: expected exactly two native end rims")
    length_mm = (rims[1][0] - rims[0][0]) * 1000
    if not math.isclose(length_mm, stud.LENGTH, abs_tol=1e-5):
        raise RuntimeError(
            "kit stud: native overall length differs from the installed member"
        )
    entities = (rims[0][1], rims[1][1])
    _early_bound(front, "IView").UpdateViewDisplayGeometry()  # VT_VOID
    points = model_points_in_view(
        adapter,
        front,
        [(0.0, station, 0.0) for station, _edge in rims],
        label="kit stud overall end stations",
    )
    cell = cells[0][2]
    display = _early_bound(
        add_edge_dimension(
            adapter,
            front,
            p0=points[0],
            p1=points[1],
            text_xy=(cell[0] + 0.022, (points[0][1] + points[1][1]) / 2),
            label="kit stud overall length",
            orientation="vertical",
            entities=entities,
        ),
        "IDisplayDimension",
    )
    native = _early_bound(display.GetDimension2(0), "IDimension")
    native.DrivenState = 1  # swDimensionDriven: drawing-only reference measurement.
    annotation = _early_bound(display.GetAnnotation(), "IAnnotation")
    set_reference_dimension(adapter, annotation, label="kit stud overall length")

    def display_bounds() -> tuple[Any, Any]:
        rendered, errors = annotation_display(adapter, annotation)
        ink = _measured_display_box(rendered)
        text_ink = _measured_display_box({"texts": rendered.get("texts", ())})
        if errors or estimated_text_runs(rendered) or ink is None or text_ink is None:
            raise RuntimeError("kit stud: reference display is unreadable")
        return ink, text_ink

    _ink, text_ink = display_bounds()
    front_left = _box(front.GetOutline(), label="kit stud FRONT")[0]
    # Native83 centred the 17.67 mm reference text on its dimension line,
    # across the stud outline. Seat its measured right edge left of the view;
    # 2.5 mm authoring air retains a strict 2 mm settled clearance.
    shift = min(0.0, front_left - 0.0025 - text_ink.xmax)
    if shift < 0.0:
        position = tuple(
            float(value) for value in _read_member(annotation, "GetPosition")
        )
        if (
            annotation.SetPosition2(position[0] + shift, position[1], position[2])
            is not True
        ):
            raise RuntimeError("kit stud: reference relocation refused")

    def settled() -> None:
        present = [
            raw
            for raw in (front.GetAnnotations() or ())
            if int(adapter.swApp.IsSame(raw, annotation)) == 1
        ]
        if len(present) != 1:
            raise RuntimeError("kit stud: overall reference annotation was lost")
        assert_dimension_measures(
            adapter,
            display,
            expected_mm=length_mm,
            label="kit stud overall length",
            entities=entities,
        )
        if (
            int(native.DrivenState) != 1
            or int(annotation.Visible) != 1
            or (display.GetText(1), display.GetText(2)) != ("(", ")")
        ):
            raise RuntimeError("kit stud: overall reference display was lost")
        ink, text_ink = display_bounds()
        if (
            not _inside((ink.xmin, ink.ymin, ink.xmax, ink.ymax), cell)
            or text_ink.xmax
            > _box(front.GetOutline(), label="kit stud FRONT")[0] - 0.002
        ):
            raise RuntimeError(
                "kit stud: reference text/strokes leave the FRONT cell or cross its model clearance"
            )

    settled()
    return settled


def _note_text_box(
    annotation: Any, *, label: str = "kit thread note"
) -> tuple[float, float, float, float]:
    """Native rendered text only: INote.GetExtent also includes its fixed leader."""
    data = _early_bound(annotation.GetDisplayData(), "IDisplayData")
    texts = []
    for index in range(int(data.GetTextCount())):
        text = data.GetTextAtIndex(index)
        if not text.strip():
            continue
        width = float(data.GetTextInBoxWidthAtIndex(index))
        height = float(data.GetTextHeightAtIndex(index))
        if (
            not math.isfinite(width)
            or not math.isfinite(height)
            or min(width, height) <= 0
        ):
            raise RuntimeError(f"{label}: native thread text size is unreadable")
        texts.append(
            {
                "t": text,
                "w": width,
                "h": height,
                "pos": tuple(data.GetTextPositionAtIndex(index)),
                "ref": int(data.GetTextRefPositionAtIndex(index)),
                "ang": float(data.GetTextAngleAtIndex(index)),
            }
        )
    box = _measured_display_box({"texts": texts})
    if box is None:
        raise RuntimeError(f"{label}: native thread text is missing")
    return (box.xmin, box.ymin, box.xmax, box.ymax)


def _member_thread_note(
    adapter: Any, cells: tuple, views: list[Any], *, member: str, spec: Any
) -> Callable[[], None]:
    """Author and relocate the native cosmetic-thread callout, never free text.

    Select the bore-owned cosmetic thread and request its native callout once
    if absent. Native canary 2267 proved that the returned INote has no direct
    geometry attachments: association is ICThread.ThreadCallout plus the
    owning thread annotation's bore attachments. Preserve both identities and
    the thread's geometry through relocation and read-only settled checks.
    """
    label = f"kit {member}"
    bore_feature = f"{spec.CONFIGURATION}ThreadBore"
    iso = _early_bound(views[3], "IView")
    # The member hook follows HLR fitting, before the finalizer authors this
    # mode. Inspect the same display mode that will print, then flush its
    # geometry before reading annotations. This is not a note-generation retry.
    set_high_quality_shaded_with_edges(adapter, iso, label=f"{label} isometric")

    def attachment_state(annotation: Any) -> tuple:
        attached = tuple(annotation.GetAttachedEntities3() or ())
        types = tuple(
            int(value) for value in (annotation.GetAttachedEntityTypes() or ())
        )
        count = int(annotation.GetAttachedEntityCount3())
        features = []
        for entity, kind in zip(attached, types):
            if entity is None:
                faces = ()
            elif kind == 1:  # swSelectType_e.swSelEDGES
                faces = _early_bound(entity, "IEdge").GetTwoAdjacentFaces2() or ()
            elif kind == 2:  # swSelectType_e.swSelFACES
                faces = (entity,)
            else:
                faces = ()
            names = []
            for face in faces:
                if face is not None:
                    feature = _early_bound(face, "IFace2").GetFeature()
                    if feature is not None:
                        names.append(str(_early_bound(feature, "IFeature").Name))
            features.append(tuple(names))
        return attached, types, count, tuple(features)

    def belongs_to_bore(state: tuple) -> bool:
        attached, types, count, features = state
        return (
            bool(attached)
            and count == len(attached) == len(types)
            and all(entity is not None for entity in attached)
            and all(kind in (1, 2) for kind in types)
            and any(bore_feature in names for names in features)
        )

    def bore_definition() -> tuple[Any, float]:
        part = _early_bound(iso.ReferencedDocument, "IPartDoc")
        raw_feature = part.FeatureByName(bore_feature)
        if raw_feature is None:
            raise RuntimeError(
                f"{label}: native bore feature {bore_feature!r} is missing"
            )
        feature = _early_bound(raw_feature, "IFeature")
        raw_definition = feature.GetDefinition()
        if feature.GetTypeName2() != "HoleWzd" or raw_definition is None:
            raise RuntimeError(f"{label}: native bore has no Hole Wizard definition")
        definition = _early_bound(raw_definition, "IWizardHoleFeatureData2")
        # Match _holes.wizard_holes' documented through-tap readback, not the
        # rounded catalogue drill. Native83 cut 10.71626 mm, not 10.716 mm.
        diameter = float(definition.ThruTapDrillDiameter)
        if not math.isfinite(diameter) or diameter <= 0.0:
            raise RuntimeError(
                f"{label}: native through-tap drill diameter is unreadable: {diameter!r}"
            )
        return feature, diameter

    def same_geometry(before: tuple, after: tuple) -> bool:
        return (
            before[1:3] == after[1:3]
            and len(before[0]) == len(after[0])
            and all(
                _is_same_attachment(
                    adapter, actual, expected, "EDGE" if kind == 1 else "FACE"
                )
                for expected, actual, kind in zip(
                    before[0], after[0], before[1], strict=True
                )
            )
        )

    def non_iso_callouts() -> list[tuple]:
        found = []
        for raw_view in views[:3]:
            view = _early_bound(raw_view, "IView")
            view.UpdateViewDisplayGeometry()
            for raw in view.GetAnnotations() or ():
                thread_annotation = _early_bound(raw, "IAnnotation")
                if int(thread_annotation.GetType()) != 1:  # swCThread
                    continue
                thread = _early_bound(
                    thread_annotation.GetSpecificAnnotation(), "ICThread"
                )
                raw_note = _read_member(thread, "ThreadCallout")
                if raw_note is None:
                    continue
                note = _early_bound(raw_note, "INote")
                annotation = _early_bound(note.GetAnnotation(), "IAnnotation")
                state = attachment_state(thread_annotation)
                if not belongs_to_bore(state):
                    raise RuntimeError(
                        f"{label}: cannot retire a non-isometric callout without "
                        f"{bore_feature} association; types={state[1][:8]!r}, "
                        f"count={state[2]}, features={state[3][:4]!r}"
                    )
                owner = _read_member(annotation, "Owner")
                if int(annotation.OwnerType) != 0 or owner is None:
                    raise RuntimeError(
                        f"{label}: native thread callout has no drawing-view owner"
                    )
                owner = _early_bound(owner, "IView")
                if int(adapter.swApp.IsSame(owner, view)) != 1:
                    raise RuntimeError(
                        f"{label}: non-isometric thread callout has an unexpected owner; "
                        f"view={str(view.GetName2())[:80]!r}, "
                        f"owner={str(owner.GetName2())[:80]!r}"
                    )
                if not any(
                    int(adapter.swApp.IsSame(annotation, item[3])) == 1
                    for item in found
                ):
                    found.append((view, thread_annotation, note, annotation, state))
        return found

    def retire_non_iso_callouts() -> None:
        # Native83's flange-nut RIGHT view cannot show the bore opening.
        # Deliberately author the callout in ISO, not a free-text replacement
        # or an undocumented transfer of the old CThread -> INote relationship.
        draw = _early_bound(adapter.currentModel, "IModelDoc2")
        for view, old_thread, old_note, old_annotation, before in non_iso_callouts():
            diagnostic = {
                "view": str(view.GetName2())[:80],
                "thread": str(old_thread.GetName())[:80],
                "text": str(old_note.GetText())[:120],
            }
            try:
                draw.ClearSelection2(True)
                selected = old_annotation.Select2(False, 0)
                manager = _early_bound(draw.SelectionManager, "ISelectionMgr")
                count = int(manager.GetSelectedObjectCount2(-1))
                kind = int(manager.GetSelectedObjectType3(1, -1)) if count else 0
                picked = manager.GetSelectedObject6(1, -1) if count == 1 else None
                picked_annotation = (
                    _early_bound(
                        _early_bound(picked, "INote").GetAnnotation(), "IAnnotation"
                    )
                    if kind == 15 and picked is not None  # swSelNOTES
                    else None
                )
                if (
                    selected is not True
                    or count != 1
                    or kind != 15
                    or picked_annotation is None
                    or int(adapter.swApp.IsSame(picked_annotation, old_annotation)) != 1
                ):
                    raise RuntimeError(
                        f"{label}: cannot select the non-isometric native note for retirement; "
                        f"count={count}, type={kind}, callout={diagnostic!r}"
                    )
                draw.EditDelete()  # VT_VOID: fresh native inventories below prove deletion.
                view.UpdateViewDisplayGeometry()
                fresh = [
                    annotation
                    for raw in view.GetAnnotations() or ()
                    if int((annotation := _early_bound(raw, "IAnnotation")).GetType())
                    == 1
                    and int(adapter.swApp.IsSame(annotation, old_thread)) == 1
                ]
                after = attachment_state(fresh[0]) if len(fresh) == 1 else None
                survivors = [
                    raw
                    for raw in view.GetNotes() or ()
                    if int(
                        adapter.swApp.IsSame(
                            _early_bound(
                                _early_bound(raw, "INote").GetAnnotation(),
                                "IAnnotation",
                            ),
                            old_annotation,
                        )
                    )
                    == 1
                ]
                if (
                    after is None
                    or not belongs_to_bore(after)
                    or not same_geometry(before, after)
                    or _read_member(
                        _early_bound(fresh[0].GetSpecificAnnotation(), "ICThread"),
                        "ThreadCallout",
                    )
                    is not None
                    or survivors
                ):
                    raise RuntimeError(
                        f"{label}: native callout retirement failed or changed its CThread/model "
                        f"geometry; matching_threads={len(fresh)}, surviving_notes={len(survivors)}, "
                        f"callout={diagnostic!r}"
                    )
                _telemetry.info(
                    f"{label}: retired non-isometric native thread note; {diagnostic!r}"
                )
            finally:
                draw.ClearSelection2(True)

    insertion_before: dict[str, Any] = {}

    def insert_callout(thread_annotation: Any, state: tuple) -> None:
        thread_name = str(thread_annotation.GetName())
        part = _early_bound(iso.ReferencedDocument, "IPartDoc")
        # ICThread's SDK overview documents this name-to-source-feature lookup.
        feature = part.FeatureByName(thread_name)
        definition: dict[str, Any] = {"feature_resolved": feature is not None}
        if feature is not None:
            feature = _early_bound(feature, "IFeature")
            definition["feature_type"] = str(feature.GetTypeName2())
            if definition["feature_type"] == "CosmeticThread":
                raw_data = feature.GetDefinition()
                if raw_data is not None:
                    data = _early_bound(raw_data, "ICosmeticThreadFeatureData")
                    definition.update(
                        standard=int(data.Standard),
                        standard_type=str(data.StandardType)[:80],
                        text=str(data.ThreadCallout)[:120],
                    )
        insertion_before.update(
            view=str(iso.GetName2())[:80],
            thread_name=thread_name[:120],
            attachment_count=state[2],
            attachment_types=state[1][:8],
            attachment_features=tuple(
                tuple(name[:64] for name in names[:4]) for names in state[3][:8]
            ),
            source_definition=definition,
            selected=False,
            requested=False,
        )
        draw = _early_bound(adapter.currentModel, "IModelDoc2")
        drawing = _early_bound(draw, "IDrawingDoc")
        previous = drawing.ActiveDrawingView
        previous_name = (
            _early_bound(previous, "IView").GetName2() if previous is not None else None
        )
        sheet_name = _early_bound(drawing.GetCurrentSheet(), "ISheet").GetName()
        primary_error: BaseException | None = None
        try:
            if drawing.ActivateView(iso.GetName2()) is not True:
                raise RuntimeError(
                    f"{label}: cannot activate thread-callout view; {insertion_before!r}"
                )
            draw.ClearSelection2(True)
            manager = _early_bound(draw.SelectionManager, "ISelectionMgr")
            # Follow the established drawing-annotation Select2 convention;
            # its reported success is not proof of the actual selection.
            selected = thread_annotation.Select2(False, 0)
            count = int(manager.GetSelectedObjectCount2(-1))
            kind = int(manager.GetSelectedObjectType3(1, -1)) if count else 0
            picked = manager.GetSelectedObject6(1, -1) if count else None
            picked_annotation = None
            if count == 1 and kind == 39 and picked is not None:
                # swSelectType_e.swSelCTHREADS = 39; drawing selections return ICThread.
                picked_annotation = _early_bound(
                    _early_bound(picked, "ICThread").GetAnnotation(),
                    "IAnnotation",
                )
            same = (
                picked_annotation is not None
                and int(adapter.swApp.IsSame(picked_annotation, thread_annotation)) == 1
            )
            insertion_before.update(
                selection_count=count,
                selection_type=kind,
                selection_name=(
                    str(picked_annotation.GetName())[:120]
                    if picked_annotation is not None
                    else None
                ),
                same_thread=same,
            )
            if selected is not True or count != 1 or kind != 39 or not same:
                raise RuntimeError(
                    f"{label}: cannot select cosmetic thread; {insertion_before!r}"
                )
            insertion_before["selected"] = True
            insertion_before["requested"] = True
            _telemetry.info(
                f"{label}: requesting native thread callout; {insertion_before!r}"
            )
            # VT_VOID. Native canary 2267 proved this creates the callout;
            # the same ICThread's subsequent ThreadCallout is the proof.
            drawing.InsertThreadCallout()
        except BaseException as error:
            primary_error = error
            raise
        finally:
            try:
                draw.ClearSelection2(True)
                restored = (
                    drawing.ActivateView(previous_name)
                    if previous_name is not None
                    else drawing.ActivateSheet(sheet_name)
                )
                active = drawing.ActiveDrawingView
                active_name = (
                    _early_bound(active, "IView").GetName2()
                    if active is not None
                    else None
                )
                active_sheet = _early_bound(
                    drawing.GetCurrentSheet(),
                    "ISheet",
                ).GetName()
                if (
                    restored is not True
                    or active_name != previous_name
                    or active_sheet != sheet_name
                ):
                    raise RuntimeError(
                        f"activation readback: expected view={previous_name!r}, "
                        f"sheet={sheet_name!r}; actual view={active_name!r}, "
                        f"sheet={active_sheet!r}, reported={restored!r}"
                    )
            except Exception as restore_error:
                message = (
                    f"{label}: cannot restore drawing activation: {restore_error!r}; "
                    f"insertion_before={insertion_before!r}"
                )
                if primary_error is not None:
                    primary_error.add_note(message)
                else:
                    raise RuntimeError(message) from restore_error

    def notes(*, author_missing: bool = False) -> list[tuple]:
        iso.UpdateViewDisplayGeometry()  # VT_VOID: immediate display-geometry access.
        found, observed = [], []
        thread_annotations = [
            annotation
            for raw in (iso.GetAnnotations() or ())
            if int((annotation := _early_bound(raw, "IAnnotation")).GetType()) == 1
            # swAnnotationType_e.swCThread
        ]
        threads, callouts = len(thread_annotations), 0
        for thread_annotation in thread_annotations:
            state = attachment_state(thread_annotation)
            thread = _early_bound(thread_annotation.GetSpecificAnnotation(), "ICThread")
            raw_note = _read_member(thread, "ThreadCallout")
            if raw_note is None:
                if author_missing and threads == 1 and belongs_to_bore(state):
                    insert_callout(thread_annotation, state)
                    iso.UpdateViewDisplayGeometry()
                    fresh = [
                        annotation
                        for raw in (iso.GetAnnotations() or ())
                        if int(
                            (annotation := _early_bound(raw, "IAnnotation")).GetType()
                        )
                        == 1
                        and int(adapter.swApp.IsSame(annotation, thread_annotation))
                        == 1
                    ]
                    if len(fresh) != 1:
                        raise RuntimeError(
                            f"{label}: selected cosmetic thread lost identity after "
                            f"insertion; matching_annotations={len(fresh)}, "
                            f"insertion_before={insertion_before!r}"
                        )
                    thread_annotation = fresh[0]
                    state = attachment_state(thread_annotation)
                    thread = _early_bound(
                        thread_annotation.GetSpecificAnnotation(),
                        "ICThread",
                    )
                    raw_note = _read_member(thread, "ThreadCallout")
                if raw_note is None:
                    if len(observed) < 4:
                        observed.append(
                            {
                                "callout": None,
                                "thread_count": state[2],
                                "thread_types": state[1][:8],
                                "thread_features": tuple(
                                    tuple(name[:64] for name in names[:4])
                                    for names in state[3][:8]
                                ),
                            }
                        )
                    continue
            callouts += 1
            note = _early_bound(raw_note, "INote")
            annotation = _early_bound(note.GetAnnotation(), "IAnnotation")
            attached, types, count, features = state
            if len(observed) < 4:
                observed.append(
                    {
                        "text": str(note.GetText())[:120],
                        "geometry_owner": "ICThread",
                        "count": count,
                        "types": types[:8],
                        "features": tuple(
                            tuple(name[:64] for name in names[:4])
                            for names in features[:8]
                        ),
                        "nulls": sum(entity is None for entity in attached),
                    }
                )
            if belongs_to_bore((attached, types, count, features)):
                found.append((note, annotation, thread_annotation, state))
        if len(found) != 1:
            # Diagnostic only: ordinary view notes are not a substitute for the
            # native ICThread -> ThreadCallout relationship.
            view_notes = tuple(iso.GetNotes() or ())
            view_note_texts = tuple(
                str(_early_bound(raw, "INote").GetText())[:120]
                for raw in view_notes[:4]
            )
            raise RuntimeError(
                f"{label}: expected one automatic isometric thread note from a "
                f"cosmetic thread attached to {bore_feature}; found={len(found)}, "
                f"cosmetic_threads={threads}, "
                f"callouts={callouts}, candidates={observed!r}, "
                f"view_notes={len(view_notes)}, view_note_texts={view_note_texts!r}, "
                f"insertion_before={insertion_before!r}"
            )
        return found

    native_bore_identity: tuple[str, int, float] | None = None
    correspondence_probed = False
    retire_non_iso_callouts()
    note, annotation, thread_annotation, geometry = notes(
        author_missing=True,
    )[0]
    text, linked = note.GetText(), note.PropertyLinkedText
    if not text.strip():
        raise RuntimeError(f"{label}: native thread callout has no text")

    def region() -> tuple[float, float, float, float]:
        top = max(_box(view.GetOutline(), label=label)[3] for view in views)
        return (cells[0][2][0] + 0.002, top + 0.002, cells[2][2][2] - 0.002, 0.253)

    bounds = _note_text_box(annotation, label=label)
    clear = region()
    position = tuple(float(value) for value in _read_member(annotation, "GetPosition"))
    target = (
        position[0] + (clear[0] + clear[2] - bounds[0] - bounds[2]) / 2,
        position[1] + (clear[1] + clear[3] - bounds[1] - bounds[3]) / 2,
        0.0,
    )
    if annotation.SetPosition2(*target) is not True:
        raise RuntimeError(f"{label}: native thread-note relocation refused")

    def rim_inventory(
        source: Any,
        current_bore: Any,
        diameter: float,
        record: dict,
        *,
        strict: bool,
        candidates: list[Any] | None = None,
        prior_candidates: list[Any] | None = None,
    ) -> list[tuple]:
        extension = _early_bound(source.Extension, "IModelDocExtension")
        manager = _early_bound(source.ConfigurationManager, "IConfigurationManager")
        active = manager.ActiveConfiguration
        context = {
            "view": str(iso.GetName2())[:80],
            "view_configuration": str(iso.ReferencedConfiguration)[:80],
            "view_model": str(iso.GetReferencedModelName())[:200],
            "source_model": str(source.GetPathName())[:200],
            "source_type": int(source.GetType()),
            "source_active_configuration": (
                str(_early_bound(active, "IConfiguration").Name)[:80]
                if active is not None
                else None
            ),
            "source_bore": str(current_bore.Name)[:80],
            "source_bore_type": str(current_bore.GetTypeName2())[:80],
            "source_bore_id": int(current_bore.GetID()),
            "source_bore_self_equality": int(
                adapter.swApp.IsSame(current_bore, current_bore)
            ),
        }
        record["context"] = context
        rims = []
        circles_seen, observed, matching_features = 0, [], []
        record.update(
            visible_circles=0,
            geometry_candidates=0,
            circle_params=observed,
            matching_geometry_features=matching_features,
        )
        for raw in visible_view_entities(iso, 1, label=f"{label} visible bore rim"):
            edge = _early_bound(raw, "IEdge")
            curve = _early_bound(edge.GetCurve(), "ICurve")
            if curve is None or curve.IsCircle() is not True:
                continue
            circle = tuple(
                float(value) for value in (_read_member(curve, "CircleParams") or ())
            )
            circles_seen += 1
            record["visible_circles"] = circles_seen
            if len(observed) < 6:
                observed.append(circle[:7])
            if (
                len(circle) != 7
                or not all(math.isfinite(value) for value in circle)
                or not math.isclose(circle[0], 0.0, abs_tol=1e-9)
                or not math.isclose(circle[1] * 1000, spec.HEIGHT, abs_tol=1e-5)
                or not math.isclose(circle[2], 0.0, abs_tol=1e-9)
                or not math.isclose(circle[3], 0.0, abs_tol=1e-9)
                or not math.isclose(abs(circle[4]), 1.0, abs_tol=1e-9)
                or not math.isclose(circle[5], 0.0, abs_tol=1e-9)
                or not math.isclose(circle[6] * 2, diameter, rel_tol=0.0, abs_tol=1e-8)
            ):
                continue
            record["geometry_candidates"] += 1
            if candidates is not None and len(candidates) < 4:
                candidates.append(edge)
            baseline_equalities = []
            for before_edge in prior_candidates or ():
                try:
                    equality = int(adapter.swApp.IsSame(edge, before_edge))
                except Exception as error:
                    # Causal telemetry only: activation can invalidate old
                    # wrappers. Never use this observation as an ownership gate.
                    equality = f"{type(error).__name__}: {str(error)[:120]}"
                baseline_equalities.append(equality)
            view_features = []
            for raw_face in edge.GetTwoAdjacentFaces2() or ():
                if raw_face is not None:
                    feature = _early_bound(raw_face, "IFace2").GetFeature()
                    if feature is not None and len(view_features) < 4:
                        feature = _early_bound(feature, "IFeature")
                        view_features.append(
                            (
                                str(feature.Name)[:64],
                                str(feature.GetTypeName2())[:64],
                            )
                        )
            # Follow _native_axis_datum's native-proven namespace boundary:
            # map the visible IEdge into the referenced source part and require
            # its exact view roundtrip. Features reached through the original
            # drawing edge are NOT compared with source-part features.
            canonical = extension.GetCorrespondingEntity2(edge)
            roundtrip = (
                iso.GetCorrespondingEntity(canonical) if canonical is not None else None
            )
            roundtrip_equality = (
                int(adapter.swApp.IsSame(roundtrip, edge))
                if roundtrip is not None
                else None
            )
            source_features, bore_owned = [], False
            if canonical is not None:
                source_edge = _early_bound(canonical, "IEdge")
                for raw_face in source_edge.GetTwoAdjacentFaces2() or ():
                    if raw_face is not None:
                        feature = _early_bound(raw_face, "IFace2").GetFeature()
                        if feature is not None:
                            feature = _early_bound(feature, "IFeature")
                            equality = int(adapter.swApp.IsSame(feature, current_bore))
                            bore_owned |= equality == 1
                            if len(source_features) < 4:
                                source_features.append(
                                    (
                                        str(feature.Name)[:64],
                                        str(feature.GetTypeName2())[:64],
                                        equality,
                                        int(adapter.swApp.IsSame(feature, feature)),
                                    )
                                )
            correspondence = {
                "view_features": tuple(view_features),
                "mapped_source_edge": canonical is not None,
                "view_roundtrip_equality": roundtrip_equality,
                "geometry_candidate": record["geometry_candidates"],
                "circle": circle,
                "baseline_visible_equalities": tuple(baseline_equalities),
                # (name, type, same source bore, self equality), all source-context.
                "source_features": tuple(source_features),
            }
            if len(matching_features) < 4:
                matching_features.append(correspondence)
            if strict and (canonical is None or roundtrip_equality != 1):
                raise RuntimeError(
                    f"{label}: native bore-rim source/view correspondence failed; "
                    f"context={context!r}, correspondence={correspondence!r}"
                )
            if canonical is not None and roundtrip_equality == 1 and bore_owned:
                rims.append((edge, circle))
        if strict and not rims:
            raise RuntimeError(
                f"{label}: expected one visible top bore rim owned by {bore_feature}; "
                f"found={len(rims)}, visible_circles={circles_seen}, "
                f"circle_params={observed!r}, matching_geometry_features={matching_features!r}, "
                f"context={context!r}"
            )
        return rims

    def active_landing(
        note_annotation: Any, rims: list[tuple]
    ) -> tuple[Any, tuple[float, float]]:
        edge, circle = rims[0]
        x, y, z, _ax, _ay, _az, radius = circle
        center, along_x, along_z = model_points_in_view(
            adapter,
            iso,
            ((x, y, z), (x + radius, y, z), (x, y, z + radius)),
            label=f"{label} native bore-rim projection",
        )
        text_box = _note_text_box(note_annotation, label=label)
        toward_text = (
            (text_box[0] + text_box[2]) / 2 - center[0],
            (text_box[1] + text_box[3]) / 2 - center[1],
        )
        basis_x = (along_x[0] - center[0], along_x[1] - center[1])
        basis_z = (along_z[0] - center[0], along_z[1] - center[1])
        weights = (
            sum(a * b for a, b in zip(basis_x, toward_text, strict=True)),
            sum(a * b for a, b in zip(basis_z, toward_text, strict=True)),
        )
        magnitude = math.hypot(*weights)
        if not math.isfinite(magnitude) or magnitude <= 0.0:
            raise RuntimeError(
                f"{label}: bore-rim landing has no readable projection toward its text"
            )
        # A support point of the projected REAL circle, facing the note.
        # This cannot select an arbitrary nearby exterior/silhouette edge.
        tip = tuple(
            center[index]
            + (basis_x[index] * weights[0] + basis_z[index] * weights[1]) / magnitude
            for index in range(2)
        )
        model_tip = (
            x + radius * weights[0] / magnitude,
            y,
            z + radius * weights[1] / magnitude,
        )
        eligible, trim_observed = [], []
        for candidate, _circle in rims:
            # CircleParams describes the underlying circle, not its trim.
            # Follow the native physical-edge proof used by the cone platform:
            # GetCurve must precede GetCurveParams3; GetClosestPointOn is on
            # IEdge (not the untrimmed ICurve).
            candidate.GetCurve()
            raw_trim = candidate.GetCurveParams3()
            if raw_trim is None:
                raise RuntimeError(
                    f"{label}: native bore-rim curve parameters are missing"
                )
            trim = _early_bound(raw_trim, "ICurveParamData")
            interval = (float(trim.UMinValue), float(trim.UMaxValue))
            closest = tuple(
                float(value)
                for value in (candidate.GetClosestPointOn(*model_tip) or ())
            )
            if (
                not all(math.isfinite(value) for value in interval)
                or interval[0] >= interval[1]
                or len(closest) < 4
                or not all(math.isfinite(value) for value in closest[:4])
            ):
                raise RuntimeError(
                    f"{label}: native bore-rim trim/closest point is unreadable; "
                    f"interval={interval!r}, closest={closest[:4]!r}"
                )
            distance = math.dist(model_tip, closest[:3])
            if len(trim_observed) < 6:
                trim_observed.append((interval, closest[3], distance))
            if distance <= 1e-8:
                eligible.append(candidate)
        if len(eligible) != 1:
            raise RuntimeError(
                f"{label}: expected one visible physical bore-rim edge at the leader tip; "
                f"circle_edges={len(rims)}, eligible_edges={len(eligible)}, "
                f"model_tip={model_tip!r}, trims={trim_observed!r}"
            )
        return eligible[0], tip

    def bore_landing(note_annotation: Any) -> tuple[Any, tuple[float, float]]:
        nonlocal native_bore_identity, correspondence_probed
        source = _early_bound(iso.ReferencedDocument, "IModelDoc2")
        drawing = _early_bound(adapter.currentModel, "IDrawingDoc")
        source_path = str(source.GetPathName())

        def active_configuration() -> str:
            manager = _early_bound(source.ConfigurationManager, "IConfigurationManager")
            active = manager.ActiveConfiguration
            name = (
                str(_early_bound(active, "IConfiguration").Name)
                if active is not None
                else ""
            )
            if not name:
                raise RuntimeError(
                    f"{label}: source active configuration is unreadable"
                )
            return name

        def drawing_activation() -> tuple[str | None, str]:
            raw = drawing.ActiveDrawingView
            name = (
                str(_early_bound(raw, "IView").GetName2()) if raw is not None else None
            )
            sheet = _early_bound(drawing.GetCurrentSheet(), "ISheet")
            return name, str(sheet.GetName())

        def drawing_configurations() -> tuple[tuple[str, str, str], ...]:
            found = []
            for raw_sheet in drawing.GetViews() or ():
                sheet_views = tuple(raw_sheet or ())
                if not sheet_views:
                    raise RuntimeError(f"{label}: drawing view inventory is unreadable")
                # GetViews documents the first entry as the sheet, not a model view.
                sheet_name = str(_early_bound(sheet_views[0], "IView").GetName2())
                for raw in sheet_views[1:]:
                    view = _early_bound(raw, "IView")
                    found.append(
                        (
                            sheet_name,
                            str(view.GetName2()),
                            str(view.ReferencedConfiguration),
                        )
                    )
            if not found:
                raise RuntimeError(f"{label}: drawing model-view inventory is empty")
            return tuple(sorted(found))

        previous = active_configuration()
        target_configuration = str(iso.ReferencedConfiguration)
        if not target_configuration:
            raise RuntimeError(f"{label}: view referenced configuration is unreadable")
        save_flag = bool(source.GetSaveFlag())
        before_activation = drawing_activation()
        before_views = drawing_configurations()
        first_control = not correspondence_probed
        before_sha = _sha256(Path(source_path)) if first_control else None
        correspondence_probed = True
        control = {
            "source_model": source_path[:200],
            "previous_configuration": previous[:80],
            "view_configuration": target_configuration[:80],
            "save_flag_before": save_flag,
            "source_sha256_before": before_sha,
        }
        baseline_candidates = []
        activation_attempted = False
        primary_error = None
        selected_rim, tip = None, None
        try:
            if first_control:
                # A single diagnostic observation, never an alternate acceptance
                # path: repeat this exact inventory/mapping shape after activation.
                control["baseline"] = {}
                before_bore = None
                try:
                    iso.UpdateViewDisplayGeometry()
                    before_bore, before_diameter = bore_definition()
                    rim_inventory(
                        source,
                        before_bore,
                        before_diameter,
                        control["baseline"],
                        strict=False,
                        candidates=baseline_candidates,
                    )
                except Exception as error:
                    # The inactive-configuration observation is not acceptance.
                    # Its failure must not replace the one strict target-config
                    # attempt or be mistaken for proof of a configuration cause.
                    control["baseline"]["error"] = (
                        f"{type(error).__name__}: {str(error)[:240]}"
                    )
                finally:
                    del before_bore
            if previous != target_configuration:
                activation_attempted = True  # Even a false/lying call can mutate state.
                reported = source.ShowConfiguration2(target_configuration)
                actual = active_configuration()
                control["activation"] = {
                    "reported": reported,
                    "actual_configuration": actual[:80],
                }
                if reported is not True or actual != target_configuration:
                    raise RuntimeError(
                        f"{label}: source configuration activation failed; "
                        f"requested={target_configuration!r}, reported={reported!r}, "
                        f"actual={actual!r}"
                    )
            iso.UpdateViewDisplayGeometry()
            current_bore, diameter = bore_definition()
            identity = (source_path, int(current_bore.GetID()), diameter)
            # GetID is unique within this document and persistent across sessions.
            # Keep only that scalar identity across configuration scopes, not a
            # source feature/edge wrapper that activation may invalidate.
            if native_bore_identity is None:
                native_bore_identity = identity
            elif identity != native_bore_identity:
                raise RuntimeError(
                    f"{label}: native bore feature/diameter changed; "
                    f"expected={native_bore_identity!r}, actual={identity!r}"
                )
            control["matched"] = {}
            rims = rim_inventory(
                source,
                current_bore,
                diameter,
                control["matched"],
                strict=True,
                prior_candidates=baseline_candidates,
            )
            selected_rim, tip = active_landing(note_annotation, rims)
        except BaseException as error:
            primary_error = error
            raise
        finally:
            cleanup_errors = []
            restored_configuration = None
            try:
                restored_configuration = active_configuration()
            except Exception as error:
                cleanup_errors.append(("configuration readback", error))
            # Restore even after a false/lying activation or failed readback.
            if activation_attempted or restored_configuration != previous:
                try:
                    reported = source.ShowConfiguration2(previous)
                    restored_configuration = active_configuration()
                    if reported is not True or restored_configuration != previous:
                        raise RuntimeError(
                            f"expected={previous!r}, reported={reported!r}, "
                            f"actual={restored_configuration!r}"
                        )
                except Exception as error:
                    cleanup_errors.append(("configuration restoration", error))
            control["restored_configuration"] = (
                restored_configuration[:80]
                if restored_configuration is not None
                else None
            )
            try:
                after_save_flag = bool(source.GetSaveFlag())
                control["save_flag_after"] = after_save_flag
                if after_save_flag != save_flag:
                    raise RuntimeError(
                        f"source save flag changed: {save_flag!r} -> {after_save_flag!r}"
                    )
            except Exception as error:
                cleanup_errors.append(("source unsaved state", error))
            try:
                after_activation = drawing_activation()
                control["drawing_activation_after"] = tuple(
                    name[:80] if name is not None else None for name in after_activation
                )
                if after_activation != before_activation:
                    raise RuntimeError(
                        f"drawing activation changed: {before_activation!r} -> "
                        f"{after_activation!r}"
                    )
            except Exception as error:
                cleanup_errors.append(("drawing activation", error))
            try:
                after_views = drawing_configurations()
                control["view_configurations_unchanged"] = after_views == before_views
                if after_views != before_views:
                    raise RuntimeError("drawing referenced configurations changed")
            except Exception as error:
                cleanup_errors.append(("drawing configurations", error))
            if first_control:
                try:
                    after_sha = _sha256(Path(source_path))
                    control["source_sha256_after"] = after_sha
                    if after_sha != before_sha:
                        raise RuntimeError("native source bytes changed")
                except Exception as error:
                    cleanup_errors.append(("native source SHA", error))
            if selected_rim is not None and restored_configuration == previous:
                try:
                    # Configuration changes can invalidate wrappers. Re-enumerate
                    # the VIEW after restoration; never return a canonical source
                    # edge or treat a merely nearby edge as the original rim.
                    iso.UpdateViewDisplayGeometry()
                    fresh = [
                        _early_bound(raw, "IEdge")
                        for raw in visible_view_entities(
                            iso, 1, label=f"{label} restored visible bore rim"
                        )
                        if int(adapter.swApp.IsSame(raw, selected_rim)) == 1
                    ]
                    control["restored_visible_rim_matches"] = len(fresh)
                    if len(fresh) != 1:
                        raise RuntimeError(
                            f"visible bore rim lost native identity after configuration "
                            f"restoration; matching_edges={len(fresh)}"
                        )
                    selected_rim = fresh[0]
                except Exception as error:
                    cleanup_errors.append(("restored visible rim", error))
            control["cleanup_errors"] = tuple(
                (stage, str(error)[:200]) for stage, error in cleanup_errors
            )
            diagnostic_error = None
            try:
                _telemetry.info(
                    f"{label}: native bore configuration control; {control!r}"
                )
            except Exception as error:
                # Observational logging must not mask a native failure or undo
                # restoration. The native ownership/geometry gates above remain
                # strict even when the telemetry sink itself is unavailable.
                diagnostic_error = error
                if primary_error is not None:
                    primary_error.add_note(
                        f"{label}: configuration-control logging failed: {error!r}"
                    )
            if cleanup_errors:
                if primary_error is not None:
                    for stage, error in cleanup_errors:
                        primary_error.add_note(
                            f"{label}: {stage} failed during restoration: {error!r}"
                        )
                else:
                    error = RuntimeError(
                        f"{label}: native bore configuration restoration failed; "
                        f"errors={control['cleanup_errors']!r}"
                    )
                    if diagnostic_error is not None:
                        error.add_note(
                            f"configuration-control logging failed: {diagnostic_error!r}"
                        )
                    for stage, cleanup_error in cleanup_errors:
                        error.add_note(f"{stage}: {cleanup_error!r}")
                    raise error from cleanup_errors[0][1]
        return selected_rim, tip

    native_rim, tip = bore_landing(annotation)
    # The SDK supports this setter on INote, not CThread. Whether this native
    # callout preserves its parent relationship is proved below, never assumed
    # from the setter result or the note's zero direct attachments.
    if annotation.SetLeaderAttachmentPointAtIndex(0, tip[0], tip[1], 0.0) is not True:
        raise RuntimeError(f"{label}: native bore-rim leader placement refused")

    def settled() -> None:
        current = notes()
        current_note, current_annotation, current_thread, current_geometry = current[0]
        if (
            current_note.GetText() != text
            # swObjectEquality.swObjectSame = 1 (SOLIDWORKS API Help).
            or int(adapter.swApp.IsSame(current_annotation, annotation)) != 1
            or int(adapter.swApp.IsSame(current_thread, thread_annotation)) != 1
            or current_note.PropertyLinkedText != linked
            or current_annotation.IsDangling() is not False
            or int(current_annotation.Visible) != 1
            or int(current_annotation.OwnerType) != 0  # swAnnotationOwner_DrawingView
            or int(
                adapter.swApp.IsSame(
                    _early_bound(_read_member(current_annotation, "Owner"), "IView"),
                    iso,
                )
            )
            != 1
            or not same_geometry(geometry, current_geometry)
            or not _inside(_note_text_box(current_annotation, label=label), region())
            or not _inside(
                _box(current_note.GetExtent(), label=text, kind="note"),
                (cells[0][2][0], cells[3][2][1], cells[2][2][2], 0.255),
            )
        ):
            raise RuntimeError(
                f"{label}: thread note lost identity, attachment or clearance"
            )
        remaining = non_iso_callouts()
        if remaining:
            raise RuntimeError(
                f"{label}: non-isometric native thread callout survived/returned; "
                f"count={len(remaining)}, views="
                f"{tuple(str(item[0].GetName2())[:80] for item in remaining[:4])!r}"
            )
        current_rim, current_tip = bore_landing(current_annotation)
        if int(adapter.swApp.IsSame(current_rim, native_rim)) != 1:
            raise RuntimeError(f"{label}: visible bore rim lost native identity")
        points = tuple(
            float(value) for value in current_annotation.GetLeaderPointsAtIndex(0) or ()
        )
        if (
            len(points) < 6
            or len(points) % 3
            or not all(math.isfinite(value) for value in points)
        ):
            raise RuntimeError(f"{label}: native thread-note leader is unreadable")
        _assert_leader_lands(
            current_annotation,
            current_tip,
            what="native thread note",
            label=label,
            tolerance=0.0001,
        )

    settled()
    return settled


def annotate_member(
    adapter: Any,
    configuration: str,
    cells: tuple,
    views: list[Any],
) -> tuple[Callable[[], None], ...]:
    if configuration == "HoldDownStud":
        checks = (_stud_length_reference(adapter, cells, views),)
    elif configuration == "TNut":
        checks = (
            _member_thread_note(adapter, cells, views, member="T-nut", spec=tnut),
        )
    elif configuration == "FlangeNut":
        checks = (
            _member_thread_note(
                adapter, cells, views, member="flange nut", spec=flange_nut
            ),
        )
    else:
        return ()
    return checks


async def build(adapter: Any) -> dict[str, str]:
    return await build_purchased_variant_drawing(
        adapter,
        SPEC,
        variants=VARIANTS,
        item=ITEM,
        purchase_unit=PURCHASE_UNIT,
        general_text=GENERAL_TEXT,
        annotate_member=annotate_member,
        additional_sheet_scales={name: SHEET_SCALE for name in SHEET_NAMES},
        append_sheets=append_stud_rework_sheets,
        unit=part_drawing_unit(PART_STEM),
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("part", choices=[PART_STEM])
    return parser.parse_args()


if __name__ == "__main__":
    _parse_args()
    _telemetry.set_service("drawing-export")
    sys.exit(run_build(build))
