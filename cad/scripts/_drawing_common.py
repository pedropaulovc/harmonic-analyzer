"""Project drawing framework shared by every manufacturing print.

Raw project-agnostic COM calls remain in ``solidworks_mcp``.  This layer owns
the harmonic-analyzer book policy: ASME B landscape, the checked-in template,
reopen validation, exact PDF/PNG output, and fail-loud multi-leader callouts.
Part-specific views, dimensions, and notes belong in ``draw_<part>.py``.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path
from typing import Any, Iterable, Sequence
from xml.etree import ElementTree

import _telemetry
from _common import check
from _drawing_layout_check import (
    CollisionScope,
    LayoutElement,
    audit_layout,
    format_findings,
)
from _drawing_registry import ASME_B_DRWDOT, ASME_B_SLDDRT
from solidworks_mcp.adapters import sw_type_info as _sw_type_info
from solidworks_mcp.adapters.com_variant import dispatch_array
from solidworks_mcp.adapters.pywin32_adapter import null_callout
from solidworks_mcp.adapters.solidworks.drawing import (
    TOL_BASIC,
    add_note,
    curate_dimensions,
    dimension_name,
    iter_views,
    new_drawing,
    save_drawing,
    set_units_mm,
    view_name,
)


# swAnnotationType_e.swNote -- the view-owned annotation TYPE that becomes a
# free-standing layout element (the general-notes block, schedule cells). Tables
# are enumerated separately via IView.GetTableAnnotations.
_ANNOT_NOTE = 6

# swAnnotationType_e for the native GD&T symbols the recipes place at explicit
# sheet coordinates (datum tags, feature-control frames, surface-finish symbols).
# None of these interfaces expose a real bounding box (IDisplayData returns only
# leader-polluted primitives in a non-sheet coordinate space), so each is boxed
# as a nominal square around its GetPosition anchor. That nominal box is reliable
# enough to catch a symbol placed clear OFF the sheet (overflow) but too coarse
# to assert an OVERLAP without false positives -- a datum tag placed beside its
# own feature-control frame, standard GD&T practice, would self-collide -- so the
# symbols get ``NONE`` collision scope (overflow-checked, overlap-exempt).
# (Codex #269 thread 5 overflow; overlap declined with this rationale.)
_ANNOT_DATUM = 2
_ANNOT_GTOL = 5
_ANNOT_SFSYM = 7
_GDT_TYPES = frozenset({_ANNOT_DATUM, _ANNOT_GTOL, _ANNOT_SFSYM})
_NOMINAL_GDT_HALF_M = 0.008

# swAnnotationType_e.swDisplayDimension -- every linear/diameter dimension AND
# the native hole callouts (a diameter dim carrying "/ THRU" text). Like GD&T
# they expose only a text-anchor GetPosition (no clean box) and by design sit
# ON/ACROSS the view geometry they measure, so they get a small nominal box and
# ``NONE`` scope: overflow-checked + title-block keep-out (a callout dragged off
# the sheet or over the title block is caught) but NOT overlap-checked against
# views. Half-span is smaller than GD&T's -- dimension text is compact, and a
# tight box keeps the zero-slack overflow check false-positive-free on interior
# dims (Codex #269 thread 1).
_ANNOT_DIM = 4
_NOMINAL_DIM_HALF_M = 0.004

# The checked-in ASME B sheet format (asme-b-book.slddrt) bakes its title block
# in as lines + notes rather than a queryable ITitleBlock (sheet.TitleBlock is
# None), so its occupied region is reserved here as fixed keep-out boxes. Any
# element overlapping one fails the audit, so content can never land on the title
# block (Codex #269 threads 4). These MUST track create_drawing_standards.py --
# update if that sheet format's title block / projection symbol moves.
#
# (1) The title block proper: from its left rule (TITLE_X0) up to its top rule
# (TITLE_Y1), extending to the sheet's right and bottom edges (a conservative
# superset of the drawn frame's right/bottom rules, which sit 6 mm inside).
_TITLE_BLOCK_LEFT_M = 0.278  # create_drawing_standards.TITLE_X0
_TITLE_BLOCK_TOP_M = 0.080  # create_drawing_standards.TITLE_Y1
#
# (2) The third-angle projection symbol, drawn LEFT of the title block at
# create_drawing_standards.add_third_angle_symbol(0.252, 0.027, size=0.007). Its
# glyph (concentric circles + trapezoid + axis) spans cx-1.4r .. cx+3.6r+0.4r in
# x and cy±r in y; reserved with ~1 mm margin as its own box so the empty strip
# between it and the title block is NOT reserved (a notes block legitimately
# reaches x~253 mm at that height on top-crossbar).
_PROJ_SYMBOL_BOX_M = (0.242, 0.019, 0.281, 0.035)


ASME_B_WIDTH_M = 0.4318
ASME_B_HEIGHT_M = 0.2794
ASME_B_PNG_SIZE = (5100, 3300)
ASME_B_DPI = 300


@dataclass(frozen=True)
class DrawingOutputs:
    slddrw: Path
    pdf: Path
    png: Path


_GTOL_SYMBOLS = {
    "circular_runout": "GTOL-SRUN",
    "cylindricity": "GTOL-CYL",
    "flatness": "GTOL-FLAT",
    "parallelism": "GTOL-PARA",
    "position": "GTOL-POSI",
    "perpendicularity": "GTOL-PERP",
}


def property_link(property_name: str) -> str:
    """Return a source-model property link suitable for a drawing note."""
    if not property_name or '"' in property_name:
        raise ValueError(f"invalid drawing property name: {property_name!r}")
    return f'$PRPSHEET:"{property_name}"'


def _gtol_frame_xml(
    characteristic: str,
    tolerance: str,
    *,
    datums: Sequence[str] = (),
    diameter: bool = False,
) -> str:
    """Build the SOLIDWORKS-2022+ feature-control-frame XML payload."""
    symbol = _GTOL_SYMBOLS.get(characteristic)
    if symbol is None:
        raise ValueError(f"unsupported geometric characteristic: {characteristic!r}")
    if not tolerance:
        raise ValueError("feature-control-frame tolerance cannot be blank")
    if len(datums) > 3 or any(not d or len(d) > 2 for d in datums):
        raise ValueError(f"invalid datum reference sequence: {tuple(datums)!r}")
    root = ElementTree.Element("GtolFrame")
    ElementTree.SubElement(root, "ToleranceSymbol").text = symbol
    range_info = ElementTree.SubElement(root, "ToleranceRangeInfo")
    ElementTree.SubElement(range_info, "PrimaryToleranceValue").text = tolerance
    if diameter:
        ElementTree.SubElement(range_info, "PrimaryRangeSymbol").text = "phi"
    for datum in datums:
        compartment = ElementTree.SubElement(root, "DatumCompartment")
        detail = ElementTree.SubElement(compartment, "DatumDetail")
        ElementTree.SubElement(detail, "DatumLetter").text = datum
    return ElementTree.tostring(root, encoding="unicode", short_empty_elements=True)


def _select_view_entity(
    adapter: Any,
    view: Any,
    entity_type: str,
    xy: tuple[float, float],
    *,
    label: str,
) -> Any:
    draw = adapter.currentModel
    name = view_name(adapter, view)
    if not draw.ActivateView(name):
        raise RuntimeError(f"failed to activate {label} drawing view {name!r}")
    draw.ClearSelection2(True)
    if not draw.Extension.SelectByID2(
        "", entity_type, xy[0], xy[1], 0.0, False, 0, null_callout(), 0
    ):
        raise RuntimeError(
            f"failed to select {label} {entity_type.lower()} at "
            f"sheet ({xy[0]:g}, {xy[1]:g})"
        )
    count = int(draw.SelectionManager.GetSelectedObjectCount2(-1))
    entity = draw.SelectionManager.GetSelectedObject6(count, -1)
    if entity is None:
        raise RuntimeError(f"selected {label} {entity_type.lower()} has no entity")
    return entity


@_telemetry.traced("drawing.datum_feature", label_param="label")
def add_datum_feature(
    adapter: Any,
    view: Any,
    *,
    edge_xy: tuple[float, float],
    symbol_xy: tuple[float, float],
    datum: str,
    label: str,
) -> Any:
    """Attach a native datum-feature symbol to a drawing-view edge."""
    _select_view_entity(adapter, view, "EDGE", edge_xy, label=label)
    draw = adapter.currentModel
    tag = draw.InsertDatumTag2()
    if tag is None:
        raise RuntimeError(f"failed to insert datum {datum} ({label})")
    tag = _sw_type_info.early_bound_or_flag(
        tag, "IDatumTag", "SetLabel", "GetAnnotation", "GetLabel"
    )
    if not tag.SetLabel(datum):
        raise RuntimeError(f"failed to label datum feature {datum} ({label})")
    annotation = _sw_type_info.early_bound_or_flag(
        tag.GetAnnotation(), "IAnnotation", "SetPosition2"
    )
    if not annotation.SetPosition2(symbol_xy[0], symbol_xy[1], 0.0):
        raise RuntimeError(f"failed to position datum {datum} ({label})")
    if str(tag.GetLabel()) != datum:
        raise RuntimeError(f"datum feature label did not persist ({label})")
    draw.ClearSelection2(True)
    draw.EditRebuild3()
    return tag


@_telemetry.traced("drawing.feature_control_frame", label_param="label")
def add_feature_control_frame(
    adapter: Any,
    view: Any,
    *,
    edge_xy: tuple[float, float],
    frame_xy: tuple[float, float],
    characteristic: str,
    tolerance: str,
    datums: Sequence[str] = (),
    diameter: bool = False,
    quantity: str = "",
    label: str,
) -> Any:
    """Attach a native feature-control frame to a drawing-view edge."""
    edge = _select_view_entity(adapter, view, "EDGE", edge_xy, label=label)
    draw = adapter.currentModel
    gtol = draw.InsertGtol()
    if gtol is None:
        raise RuntimeError(f"failed to insert feature-control frame ({label})")
    gtol = _sw_type_info.early_bound_or_flag(
        gtol, "IGtol", "GetFrameCount", "AddFrame", "GetFrame", "GetAnnotation"
    )
    frame_count = int(gtol.GetFrameCount() or 0)
    if frame_count == 0:
        if not gtol.AddFrame():
            raise RuntimeError(f"failed to create feature-control frame ({label})")
        frame_count = int(gtol.GetFrameCount() or 0)
    if frame_count < 1:
        raise RuntimeError(f"feature-control frame has no frame ({label})")
    frame = gtol.GetFrame(1)
    migrated = frame is None
    if migrated:
        # Current SOLIDWORKS can instantiate an old-format empty GTol from the
        # project template. Seed its simple compartments before conversion:
        # SW 2026 drops tolerance display when an empty frame is converted first
        # and populated afterward. The saved annotation is still required to be
        # current-format IGtolFrame/XML below.
        datum_values = [*datums[:3], "", "", ""][:3]
        gtol.SetFrameSymbols2(
            1,
            f"<{_GTOL_SYMBOLS[characteristic]}>",
            diameter,
            "",
            False,
            "",
            "",
            "",
            "",
        )
        if not gtol.SetFrameValues2(1, tolerance, "", *datum_values):
            raise RuntimeError(
                f"failed to seed feature-control frame for migration ({label})"
            )
        if not gtol.CanConvertFormat():
            raise RuntimeError(
                f"feature-control frame cannot migrate to current format ({label})"
            )
        conversion_error = int(gtol.ConvertFormat())
        if conversion_error != 0:
            raise RuntimeError(
                f"feature-control frame migration failed ({label}): "
                f"error {conversion_error}"
            )
        frame = gtol.GetFrame(1)
    if frame is None:
        raise RuntimeError(
            f"current feature-control frame is unavailable after migration ({label})"
        )
    frame = _sw_type_info.early_bound_or_flag(
        frame, "IGtolFrame", "SetSymbolXml", "GetSymbolXml"
    )
    xml = _gtol_frame_xml(
        characteristic, tolerance, datums=datums, diameter=diameter
    )
    if not migrated and not frame.SetSymbolXml(xml):
        raise RuntimeError(f"SOLIDWORKS rejected feature-control frame XML ({label})")
    applied = str(frame.GetSymbolXml() or "")
    if _GTOL_SYMBOLS[characteristic] not in applied or tolerance not in applied:
        raise RuntimeError(f"feature-control frame did not persist ({label})")
    if int(gtol.GetFormat()) != 2:  # swGtolFormatType_e.GTOL_SW2022 (current)
        raise RuntimeError(f"feature-control frame remained in old format ({label})")
    if quantity:
        if not gtol.InsertBelowFrameTextAt(1, quantity):
            raise RuntimeError(f"failed to add feature quantity {quantity!r} ({label})")
        if str(gtol.GetBelowFrameTextAt(1) or "") != quantity:
            raise RuntimeError(f"feature quantity did not persist ({label})")
    annotation = _sw_type_info.early_bound_or_flag(
        gtol.GetAnnotation(),
        "IAnnotation",
        "GetAttachedEntityCount3",
        "SetAttachedEntities",
        "SetPosition2",
    )
    if int(annotation.GetAttachedEntityCount3()) != 1:
        if not annotation.SetAttachedEntities(dispatch_array([edge])):
            raise RuntimeError(f"failed to attach feature-control frame ({label})")
    gtol.SetLeader(True, 0, False, False)  # swLeaderSide_e.swLS_SMART
    if not annotation.SetPosition2(frame_xy[0], frame_xy[1], 0.0):
        raise RuntimeError(f"failed to position feature-control frame ({label})")
    draw.EditRebuild3()
    if (
        int(annotation.GetAttachedEntityCount3()) != 1
        or not bool(gtol.IsAttached())
        or int(gtol.GetLeaderCount()) != 1
    ):
        raise RuntimeError(f"feature-control frame lacks one attached leader ({label})")
    draw.ClearSelection2(True)
    return gtol


@_telemetry.traced("drawing.surface_finish", label_param="label")
def add_surface_finish(
    adapter: Any,
    view: Any,
    *,
    edge_xy: tuple[float, float],
    symbol_xy: tuple[float, float],
    roughness_ra: str,
    label: str,
) -> Any:
    """Attach a native machining-required surface-finish symbol to an edge."""
    _select_view_entity(adapter, view, "EDGE", edge_xy, label=label)
    draw = adapter.currentModel
    symbol = draw.Extension.InsertSurfaceFinishSymbol3(
        1,  # installed R2026x swSFSymType_e.swSFMachining_Req
        1,  # swLeaderStyle_e.swSTRAIGHT
        symbol_xy[0],
        symbol_xy[1],
        0.0,
        0,  # swSFLaySym_e.swSFNone
        10,  # swArrowStyle_e.swNO_ARROWHEAD
        "",
        "",
        "",
        "",
        "",
        "",
        "",
    )
    if symbol is None:
        raise RuntimeError(f"failed to insert Ra {roughness_ra} symbol ({label})")
    symbol = _sw_type_info.early_bound_or_flag(
        symbol, "ISFSymbol", "SetText", "GetSymbol", "GetText", "GetAnnotation"
    )
    if not symbol.SetText(8, f"Ra {roughness_ra}"):  # current-profile roughness value
        raise RuntimeError(f"failed to set Ra {roughness_ra} ({label})")
    if int(symbol.GetSymbol()) != 1:
        raise RuntimeError(f"surface-finish symbol type did not persist ({label})")
    if str(symbol.GetText(8) or "").strip() != f"Ra {roughness_ra}":
        raise RuntimeError(f"surface-finish roughness did not persist ({label})")
    annotation = _sw_type_info.early_bound_or_flag(
        symbol.GetAnnotation(), "IAnnotation", "SetPosition2"
    )
    if not annotation.SetPosition2(symbol_xy[0], symbol_xy[1], 0.0):
        raise RuntimeError(f"failed to position surface-finish symbol ({label})")
    draw.ClearSelection2(True)
    draw.EditRebuild3()
    return symbol


@_telemetry.traced("drawing.linked_note", label_param="property_name")
def add_property_linked_note(
    adapter: Any, property_name: str, x: float, y: float
) -> Any:
    """Place one note whose displayed text resolves from the source SLDPRT."""
    note = add_note(adapter, property_link(property_name), x, y)
    if note is None:
        raise RuntimeError(f"failed to add linked drawing note {property_name!r}")
    return note


@_telemetry.traced("drawing.linked_callout", label_param="property_name")
def add_property_linked_callout(
    adapter: Any,
    view: Any,
    *,
    property_name: str,
    edge_xy: tuple[float, float],
    note_xy: tuple[float, float],
) -> Any:
    """Attach one arrowed callout whose text resolves from the source SLDPRT."""
    draw = adapter.currentModel
    name = view_name(adapter, view)
    if not draw.ActivateView(name):
        raise RuntimeError(f"failed to activate linked-callout view {name!r}")
    draw.ClearSelection2(True)
    edge = _select_edge(adapter, *edge_xy, append=False)
    note = draw.InsertNote(property_link(property_name))
    if note is None:
        raise RuntimeError(f"failed to insert linked callout {property_name!r}")
    note = _sw_type_info.early_bound_or_flag(note, "INote", "GetAnnotation")
    annotation = note.GetAnnotation()
    if annotation is None:
        raise RuntimeError(f"linked callout has no annotation: {property_name!r}")
    annotation = _sw_type_info.early_bound_or_flag(
        annotation,
        "IAnnotation",
        "GetAttachedEntityCount3",
        "SetAttachedEntities",
        "SetLeader3",
        "SetPosition2",
        "GetLeaderCount",
    )
    if int(annotation.GetAttachedEntityCount3()) != 1:
        if not annotation.SetAttachedEntities(dispatch_array([edge])):
            raise RuntimeError(f"failed to attach linked callout {property_name!r}")
    status = annotation.SetLeader3(1, 0, True, False, False, False)
    if status != 0:
        raise RuntimeError(
            f"failed to create linked-callout leader {property_name!r}: {status}"
        )
    if not annotation.SetPosition2(note_xy[0], note_xy[1], 0.0):
        raise RuntimeError(f"failed to position linked callout {property_name!r}")
    draw.EditRebuild3()
    if (
        int(annotation.GetAttachedEntityCount3()) != 1
        or int(annotation.GetLeaderCount()) != 1
    ):
        raise RuntimeError(f"linked callout {property_name!r} lacks one arrow")
    draw.ClearSelection2(True)
    return note


@_telemetry.traced("drawing.hole_callout", label_param="label")
def add_native_hole_callout(
    adapter: Any,
    view: Any,
    *,
    edge_xy: tuple[float, float],
    callout_xy: tuple[float, float],
    label: str,
) -> Any:
    """Insert an associative Hole Wizard callout on a selected drawing edge."""
    _select_view_entity(adapter, view, "EDGE", edge_xy, label=label)
    draw = adapter.currentModel
    display = draw.AddHoleCallout2(callout_xy[0], callout_xy[1], 0.0)
    if display is None:
        raise RuntimeError(f"failed to insert native hole callout ({label})")
    # AddHoleCallout2 leaves its PropertyManager page open.  Accept it through
    # the documented swCommands_PmOK command so doit remains unattended.
    if not adapter.swApp.RunCommand(-2, ""):  # swCommands_e.swCommands_PmOK
        raise RuntimeError(f"failed to accept native hole callout ({label})")
    display = _sw_type_info.early_bound_or_flag(
        display, "IDisplayDimension", "IsHoleCallout", "GetAnnotation"
    )
    if not display.IsHoleCallout():
        raise RuntimeError(f"inserted annotation is not a hole callout ({label})")
    annotation = _sw_type_info.early_bound_or_flag(
        display.GetAnnotation(), "IAnnotation", "SetPosition2"
    )
    if not annotation.SetPosition2(callout_xy[0], callout_xy[1], 0.0):
        raise RuntimeError(f"failed to position native hole callout ({label})")
    draw.ClearSelection2(True)
    draw.EditRebuild3()
    return display


def read_required_properties(
    model: Any, names: Sequence[str], *, required: Iterable[str]
) -> dict[str, str]:
    properties = {
        name: str(model.GetCustomInfoValue("", name) or "") for name in names
    }
    missing = [name for name in required if not properties.get(name)]
    if missing:
        raise RuntimeError(f"source part properties are missing: {missing}")
    return properties


def read_required_view_properties(
    adapter: Any, view: Any, names: Sequence[str], *, required: Iterable[str]
) -> dict[str, str]:
    """Validate source properties through a drawing view's loaded reference.

    ``CreateDrawViewFromModelView3`` accepts a closed model's full path and loads
    the reference as part of view creation. Reading ``ReferencedDocument`` avoids
    a redundant explicit ``OpenDoc6`` before creating the drawing.
    """
    view = _sw_type_info.flagged(view, "IView")
    model_path = str(view.GetReferencedModelName() or "")
    model = adapter._attempt(
        lambda: adapter.swApp.GetOpenDocumentByName(model_path), default=None
    )
    if model is None:
        raise RuntimeError(
            f"drawing view reference is not loaded in session: {model_path!r}"
        )
    return read_required_properties(model, names, required=required)


def import_cosmetic_threads(adapter: Any, view: Any) -> tuple[int, int]:
    """Import a view's cosmetic threads and count seed plus pattern instances.

    ``IDrawingDoc.InsertModelAnnotations3`` with ``swInsertCThreads`` makes this
    independent of each seat's drawing annotation preferences.
    ``GetCThreadCount`` counts seed objects, while each
    ``ICThread.GetPatternedTransformsCount`` supplies its repeated instances.
    """
    view = _sw_type_info.early_bound_or_flag(
        view, "IView", "GetCThreadCount", "GetFirstCThread"
    )
    draw = adapter.currentModel
    name = view_name(adapter, view)
    draw.ActivateView(name)
    draw.ClearSelection2(True)
    selected = draw.Extension.SelectByID2(
        name, "DRAWINGVIEW", 0.0, 0.0, 0.0, False, 0, null_callout(), 0
    )
    if not selected:
        raise RuntimeError(f"failed to select drawing view {name!r}")
    adapter._attempt(
        lambda: draw.InsertModelAnnotations3(
            0,      # swImportModelItemsFromEntireModel
            0x1,    # swInsertCThreads
            False,
            True,
            True,
            False,
        )
    )
    adapter._attempt(lambda: adapter.currentModel.EditRebuild3())
    seed_count = int(adapter._get_attr_or_call(view, "GetCThreadCount") or 0)
    instance_count = 0
    thread = adapter._get_attr_or_call(view, "GetFirstCThread")
    visited = 0
    while thread is not None:
        visited += 1
        if visited > 10_000:
            raise RuntimeError("cosmetic-thread traversal exceeded 10,000 entries")
        thread = _sw_type_info.early_bound_or_flag(
            thread, "ICThread", "GetPatternedTransformsCount", "GetNext"
        )
        patterns = int(
            adapter._get_attr_or_call(thread, "GetPatternedTransformsCount") or 0
        )
        instance_count += 1 + patterns
        thread = adapter._get_attr_or_call(thread, "GetNext")
    if visited != seed_count:
        raise RuntimeError(
            f"cosmetic-thread count mismatch: API={seed_count}, traversed={visited}"
        )
    return seed_count, instance_count


def new_project_drawing(
    adapter: Any,
    *,
    property_view: str,
    scale: tuple[float, float] = (1.0, 1.0),
    decimals: int = 2,
) -> tuple[Any, Any]:
    for asset in (ASME_B_DRWDOT, ASME_B_SLDDRT):
        if not asset.is_file() or asset.stat().st_size == 0:
            raise FileNotFoundError(f"project drawing standard is missing: {asset}")

    draw = new_drawing(
        adapter,
        template=str(ASME_B_DRWDOT),
        width=ASME_B_WIDTH_M,
        height=ASME_B_HEIGHT_M,
    )
    sheet = adapter._get_attr_or_call(draw, "GetCurrentSheet")
    if sheet is None:
        raise RuntimeError("project drawing template has no current sheet")
    sheet_name = adapter._get_attr_or_call(sheet, "GetName")
    if not sheet_name:
        raise RuntimeError("project drawing template has no sheet name")
    configured = draw.SetupSheet6(
        sheet_name,
        2,  # swDwgPaperBsize
        12,  # swDwgTemplateCustom
        float(scale[0]),
        float(scale[1]),
        False,
        str(ASME_B_SLDDRT.resolve()),
        ASME_B_WIDTH_M,
        ASME_B_HEIGHT_M,
        property_view,
        True,
        0.0,
        0.0,
        0.0,
        0.0,
        0,
        0,
    )
    if not configured:
        raise RuntimeError("SetupSheet6 rejected the project ASME B sheet format")
    # 2 decimals by default: 3-decimal display (76.000) reads as false precision
    # next to the ±0.25 blanket tolerance. A drawing that genuinely needs finer
    # display (an exact inch conversion like 9.525) can pass decimals=3.
    set_units_mm(adapter, decimals=decimals)
    sheet = adapter._get_attr_or_call(draw, "GetCurrentSheet")
    if sheet is None or not sheet.SetScale(float(scale[0]), float(scale[1]), True, False):
        raise RuntimeError(f"failed to force ASME B sheet to {scale[0]:g}:{scale[1]:g}")
    template_name = str(adapter._get_attr_or_call(sheet, "GetTemplateName") or "")
    if Path(template_name).resolve() != ASME_B_SLDDRT.resolve():
        raise RuntimeError(
            f"sheet format provenance mismatch: {template_name!r} != {ASME_B_SLDDRT}"
        )
    assert_asme_b_sheet(adapter, sheet, phase="initial setup", scale=scale)
    draw.ForceRebuild3(False)
    draw.EditRebuild3()
    return draw, sheet


def set_hidden_lines_removed(adapter: Any, view: Any) -> None:
    ok = adapter._attempt(
        lambda: view.SetDisplayMode4(False, 2, False, False, True), default=False
    )
    if not ok:
        raise RuntimeError("failed to set hidden-lines-removed drawing view")


def set_hidden_lines_visible(adapter: Any, view: Any) -> None:
    """Show hidden edges (greyed) in ``view`` — for a view whose job is to
    communicate internal/cross-drilled features."""
    ok = adapter._attempt(
        lambda: view.SetDisplayMode4(False, 1, False, False, True), default=False
    )
    if not ok:
        raise RuntimeError("failed to set hidden-lines-visible drawing view")


def assert_asme_b_sheet(
    adapter: Any, sheet: Any, *, phase: str, scale: tuple[float, float] = (1.0, 1.0)
) -> None:
    properties = list(adapter._get_attr_or_call(sheet, "GetProperties") or [])
    if len(properties) < 7:
        raise RuntimeError(f"{phase}: incomplete drawing sheet properties {properties!r}")
    if properties[2:4] != [float(scale[0]), float(scale[1])]:
        raise RuntimeError(
            f"{phase}: drawing sheet scale is not "
            f"{scale[0]:g}:{scale[1]:g}: {properties!r}"
        )
    if (
        abs(properties[5] - ASME_B_WIDTH_M) > 1e-6
        or abs(properties[6] - ASME_B_HEIGHT_M) > 1e-6
    ):
        raise RuntimeError(f"{phase}: drawing sheet is not ASME B size: {properties!r}")


async def reopen_drawing(adapter: Any, path: Path) -> tuple[Any, Any]:
    model = adapter.currentModel
    title = str(adapter._get_attr_or_call(model, "GetTitle") or "")
    if not title:
        raise RuntimeError("saved drawing has no document title")
    adapter.swApp.CloseDoc(title)
    check(f"reopen saved drawing {path.name}", await adapter.open_model(str(path)))
    reopened = adapter.currentModel
    sheet = adapter._get_attr_or_call(reopened, "GetCurrentSheet")
    if sheet is None:
        raise RuntimeError("reopened drawing has no current sheet")
    return reopened, sheet


def render_pdf_png(pdf: Path, png: Path) -> None:
    import pypdfium2 as pdfium

    document = pdfium.PdfDocument(str(pdf))
    if len(document) != 1:
        raise RuntimeError(f"drawing PDF has {len(document)} pages, expected 1")
    page = document[0]
    image = page.render(scale=ASME_B_DPI / 72.0).to_pil()
    page.close()
    document.close()
    if image.size == (ASME_B_PNG_SIZE[0], ASME_B_PNG_SIZE[1] + 1):
        image = image.crop((0, 0, *ASME_B_PNG_SIZE))
    png.parent.mkdir(parents=True, exist_ok=True)
    image.save(png, dpi=(ASME_B_DPI, ASME_B_DPI))
    if image.size != ASME_B_PNG_SIZE:
        raise RuntimeError(
            f"ASME B PNG is {image.size}, expected {ASME_B_PNG_SIZE}"
        )


def sanitize_pdf_metadata(pdf: Path, *, title: str) -> None:
    """Replace seat/user PDF metadata while preserving the vector page."""
    from pypdf import PdfReader, PdfWriter

    reader = PdfReader(pdf)
    if len(reader.pages) != 1:
        raise RuntimeError(f"drawing PDF has {len(reader.pages)} pages, expected 1")
    writer = PdfWriter()
    writer.clone_document_from_reader(reader)
    metadata = {
        "/Title": title,
        "/Author": "Harmonic Analyzer Project",
        "/Subject": "Hobby-machinist manufacturing drawing",
        "/Keywords": "harmonic analyzer, manufacturing drawing, #4-40 UNC",
        "/Creator": "Harmonic Analyzer SolidWorks drawing pipeline",
        "/Producer": "Harmonic Analyzer Project",
    }
    writer.add_metadata(metadata)
    temporary = pdf.with_suffix(".sanitized.pdf")
    try:
        writer.write(temporary)
        temporary.replace(pdf)
    finally:
        temporary.unlink(missing_ok=True)
    reread = PdfReader(pdf).metadata or {}
    for key, value in metadata.items():
        if reread.get(key) != value:
            raise RuntimeError(f"PDF metadata {key} did not sanitize")


def _select_edge(adapter: Any, x: float, y: float, *, append: bool) -> Any:
    draw = adapter.currentModel
    selected = draw.Extension.SelectByID2(
        "", "EDGE", x, y, 0.0, append, 0, null_callout(), 0
    )
    if not selected:
        raise RuntimeError(f"failed to select hole edge at sheet point ({x}, {y})")
    index = int(draw.SelectionManager.GetSelectedObjectCount2(-1))
    edge = draw.SelectionManager.GetSelectedObject6(index, -1)
    if edge is None:
        raise RuntimeError(f"hole-edge selection {index} returned no entity")
    return edge


def add_hole_group_tags(
    adapter: Any,
    view: Any,
    tag: str,
    *,
    edge_points: Sequence[tuple[float, float]],
    note_positions: Sequence[tuple[float, float]],
) -> list[Any]:
    """Put the same short arrowed group tag on every hole in a group.

    ``IAnnotation.SetAttachedEntities`` throws for multiple edges on a note in
    SolidWorks 2026.  One leadered note per hole is both supported and clearer:
    the nearby schedule owns the full specification while every individual hole
    visibly carries its group letter.
    """
    if not edge_points:
        raise ValueError("hole group tags require at least one edge")
    if len(edge_points) != len(note_positions):
        raise ValueError("hole edge and tag-position counts differ")
    draw = adapter.currentModel
    name = view_name(adapter, view)
    if not draw.ActivateView(name):
        raise RuntimeError(f"failed to activate drawing view {name!r}")
    notes: list[Any] = []
    for edge_point, note_position in zip(edge_points, note_positions, strict=True):
        draw.ClearSelection2(True)
        edge = _select_edge(adapter, *edge_point, append=False)
        note = draw.InsertNote(tag)
        if note is None:
            raise RuntimeError(f"failed to insert hole group tag {tag!r}")
        note = _sw_type_info.early_bound_or_flag(note, "INote", "GetAnnotation")
        annotation = note.GetAnnotation()
        if annotation is None:
            raise RuntimeError(f"hole group tag has no annotation: {tag!r}")
        annotation = _sw_type_info.early_bound_or_flag(
            annotation,
            "IAnnotation",
            "GetAttachedEntityCount3",
            "SetAttachedEntities",
            "SetLeader3",
            "SetPosition2",
            "GetLeaderCount",
        )
        if int(annotation.GetAttachedEntityCount3()) != 1:
            if not annotation.SetAttachedEntities(dispatch_array([edge])):
                raise RuntimeError(f"failed to attach hole group tag {tag!r}")
        leader_status = annotation.SetLeader3(1, 0, True, False, False, False)
        if leader_status != 0:
            raise RuntimeError(
                f"failed to create hole-group tag leader: status={leader_status}"
            )
        if not annotation.SetPosition2(*note_position, 0.0):
            raise RuntimeError(f"failed to position hole group tag {tag!r}")
        draw.EditRebuild3()
        if (
            int(annotation.GetAttachedEntityCount3()) != 1
            or int(annotation.GetLeaderCount()) != 1
        ):
            raise RuntimeError(f"hole group tag {tag!r} lacks one attached arrow")
        notes.append(note)
    draw.ClearSelection2(True)
    return notes


def insert_marked_dimensions(adapter: Any, view: Any) -> list[Any]:
    """Import the source part's marked-for-drawing dimensions into ``view``.

    Parts mark exactly their manufacturing dimensions
    (``_drawing_marks.mark_dimensions_for_drawing``), so the import mask is
    ``swInsertDimensionsMarkedForDrawing`` only.
    """
    draw = adapter.currentModel
    name = view_name(adapter, view)
    draw.ActivateView(name)
    draw.ClearSelection2(True)
    selected = draw.Extension.SelectByID2(
        name, "DRAWINGVIEW", 0.0, 0.0, 0.0, False, 0, null_callout(), 0
    )
    if not selected:
        raise RuntimeError(f"failed to select drawing view {name!r}")
    result = adapter._attempt(
        lambda: draw.InsertModelAnnotations3(
            0,       # swImportModelItemsFromEntireModel
            0x8000,  # swInsertDimensionsMarkedForDrawing
            False,
            True,
            True,
            False,
        )
    )
    if not result or isinstance(result, str):
        return []
    annotations = [
        _sw_type_info.early_bound_or_flag(
            annotation, "IAnnotation", "GetSpecificAnnotation"
        )
        for annotation in result
    ]
    names = sorted(
        name
        for name in (dimension_name(adapter, annotation) for annotation in annotations)
        if name
    )
    _telemetry.info(
        f"model-item import {name}: annotations={len(annotations)}, "
        f"dimensions={names}"
    )
    return annotations


def delete_unnamed_imports(adapter: Any, annotations: list[Any]) -> list[Any]:
    """Remove automatic cosmetic-thread callouts from model annotation import."""
    draw = adapter.currentModel
    survivors: list[Any] = []
    for annotation in annotations:
        annotation = _sw_type_info.early_bound_or_flag(
            annotation, "IAnnotation", "Select2"
        )
        if dimension_name(adapter, annotation):
            survivors.append(annotation)
            continue
        draw.ClearSelection2(True)
        if not annotation.Select2(False, 0):
            raise RuntimeError("failed to select an automatic model annotation")
        draw.EditDelete()
    draw.ClearSelection2(True)
    draw.EditRebuild3()
    return survivors


def curate_view_dimensions(
    adapter: Any,
    view: Any,
    *,
    keep: dict[str, tuple[float, float]],
    view_label: str,
) -> list[Any]:
    """Import a view's marked model dimensions and keep exactly ``keep``.

    ``keep`` maps each surviving dimension's parametric name to its sheet
    position (meters).  Everything else the import produced is deleted; a
    missing expected dimension fails loud — the print must carry every
    manufacturing dimension the recipe promises.
    """
    annotations = delete_unnamed_imports(
        adapter, insert_marked_dimensions(adapter, view)
    )
    names = {dimension_name(adapter, annotation) for annotation in annotations}
    delete = tuple(sorted(name for name in names if name and name not in keep))
    curated = curate_dimensions(
        adapter, annotations, delete=delete, reposition=dict(keep)
    )
    present = {dimension_name(adapter, annotation) for annotation in curated}
    missing = sorted(set(keep) - present)
    if missing:
        raise RuntimeError(
            f"{view_label} view is missing model dimensions: {missing}; "
            f"available={sorted(present)}"
        )
    return curate_dimensions(adapter, curated, reposition=dict(keep))


def set_dimension_callouts(
    adapter: Any, annotations: Iterable[Any], below_text: dict[str, str]
) -> None:
    """Append callout text below named dimensions (e.g. THRU / depth notes).

    A bare Ø does not tell the machinist whether a hole is through or blind;
    ASME hole callouts carry that below the value.  Keyed on the parametric
    dimension name, so a value collision can never stamp the wrong hole.
    """
    remaining = dict(below_text)
    for annotation in annotations:
        annotation = _sw_type_info.early_bound_or_flag(
            annotation, "IAnnotation", "GetSpecificAnnotation"
        )
        name = dimension_name(adapter, annotation)
        text = remaining.pop(name, None)
        if text is None:
            continue
        display = adapter._attempt(lambda a=annotation: a.GetSpecificAnnotation())
        if display is None:
            raise RuntimeError(f"dimension {name!r} has no display annotation")
        display = _sw_type_info.early_bound_or_flag(
            display, "IDisplayDimension", "SetText"
        )
        adapter._attempt(
            lambda d=display, s=text: d.SetText(4, s)  # swDimensionTextCalloutBelow
        )
    if remaining:
        raise RuntimeError(
            f"dimension callouts not applied: {sorted(remaining)}"
        )
    adapter.currentModel.EditRebuild3()


def set_dimension_precision(
    adapter: Any, annotations: Iterable[Any], precision: dict[str, int]
) -> None:
    """Override the primary decimal places of specific NAMED dimensions.

    The document default (``set_units_mm``) is 2 decimals, which reads as false
    precision on most dims.  A dimension whose value is an exact conversion the
    notes cite to 3 places — e.g. the crank shaft bore, Ø9.525 = 3/8 in — must
    display 3 so the view matches the note (otherwise 9.53-on-view vs
    9.525-in-note reads as a contradiction).  Keyed on the parametric dimension
    name so a value collision can never repick the wrong dimension.
    """
    # swDimensionPrecisionSettings_e.swDoNotChangePrecisionSetting: leave the
    # dual / tolerance precisions untouched, override only the primary.
    do_not_change = -1
    remaining = dict(precision)
    for annotation in annotations:
        annotation = _sw_type_info.early_bound_or_flag(
            annotation, "IAnnotation", "GetSpecificAnnotation"
        )
        name = dimension_name(adapter, annotation)
        digits = remaining.pop(name, None)
        if digits is None:
            continue
        display = adapter._attempt(lambda a=annotation: a.GetSpecificAnnotation())
        if display is None:
            raise RuntimeError(f"dimension {name!r} has no display annotation")
        display = _sw_type_info.early_bound_or_flag(
            display, "IDisplayDimension", "SetPrecision3", "GetPrimaryPrecision2"
        )
        result = adapter._attempt(
            lambda d=display, n=digits: d.SetPrecision3(
                n, do_not_change, do_not_change, do_not_change
            )
        )
        if result is None:
            raise RuntimeError(f"failed to set precision on dimension {name!r}")
        # SetPrecision3 reports rejection via its RETURN STATUS, not by raising, so a
        # None-only check treats a failure code as success -- and the dim would ship
        # at the 2-decimal sheet default (Ø9.53) against a Ø9.525 note (codex #246).
        # The status enum's success value is undocumented, so verify the SIDE EFFECT:
        # read the primary precision back and confirm it took.
        applied = adapter._attempt(lambda d=display: d.GetPrimaryPrecision2())
        if applied != digits:
            raise RuntimeError(
                f"precision override on dimension {name!r} did not take: "
                f"requested {digits} decimals, dimension reports {applied}"
            )
    if remaining:
        raise RuntimeError(
            f"dimension precision not applied: {sorted(remaining)}"
        )
    adapter.currentModel.EditRebuild3()


def add_edge_dimension(
    adapter: Any,
    view: Any,
    *,
    p0: tuple[float, float],
    p1: tuple[float, float],
    text_xy: tuple[float, float],
    label: str,
) -> Any:
    """Dimension across two edges picked at explicit sheet points (meters).

    The adapter's ``add_overall_dimension`` derives its picks from
    ``IView.GetOutline``, which pads the geometry with a whitespace margin, so
    its coordinate picks can miss.  Recipes know their layout exactly — the
    explicit points make the pick deterministic.  Fails loud on either pick or
    on dimension creation.
    """
    draw = adapter.currentModel
    name = view_name(adapter, view)
    if not draw.ActivateView(name):
        raise RuntimeError(f"failed to activate drawing view {name!r}")
    draw.ClearSelection2(True)
    for index, (x, y) in enumerate((p0, p1)):
        selected = draw.Extension.SelectByID2(
            "", "EDGE", x, y, 0.0, index > 0, 0, null_callout(), 0
        )
        if not selected:
            raise RuntimeError(
                f"failed to select {label} edge {index} at sheet ({x:g}, {y:g})"
            )
    dimension = draw.AddDimension2(text_xy[0], text_xy[1], 0.0)
    draw.ClearSelection2(True)
    draw.EditRebuild3()
    if dimension is None:
        raise RuntimeError(f"failed to add the {label} dimension")
    return dimension


def set_basic_dimension(adapter: Any, dimension: Any, *, label: str) -> Any:
    """Box a drawing-native locating dimension as BASIC and verify the result."""
    display = _sw_type_info.early_bound_or_flag(
        dimension, "IDisplayDimension", "GetDimension"
    )
    model_dimension = _sw_type_info.early_bound_or_flag(
        display.GetDimension(), "IDimension", "SetToleranceType", "GetToleranceType"
    )
    if not model_dimension.SetToleranceType(TOL_BASIC):
        raise RuntimeError(f"failed to make {label} dimension BASIC")
    if int(model_dimension.GetToleranceType()) != TOL_BASIC:
        raise RuntimeError(f"{label} dimension did not retain BASIC tolerance")
    adapter.currentModel.EditRebuild3()
    return dimension


def hole_table_template(adapter: Any) -> Path:
    executable = adapter._attempt(
        lambda: adapter.swApp.GetExecutablePath(), default=None
    )
    if not executable:
        raise RuntimeError("SolidWorks executable path is unavailable")
    install_root = Path(str(executable)).parent
    relative = Path("lang") / "english" / "standard hole table--letters.sldholtbt"
    candidates = (install_root / relative, install_root / "SOLIDWORKS" / relative)
    for template in candidates:
        if template.is_file():
            return template
    raise FileNotFoundError(
        "native hole-table template is missing; checked "
        + ", ".join(str(path) for path in candidates)
    )


def insert_hole_table(
    adapter: Any,
    view: Any,
    *,
    datum_xy: tuple[float, float],
    hole_points: Sequence[tuple[float, float]],
    anchor_xy: tuple[float, float],
    basic_locations: bool = True,
    label: str,
) -> Any:
    """Insert the model-associated TAG/X LOC/Y LOC/SIZE hole table on ``view``.

    ``datum_xy`` picks the origin VERTEX and each ``hole_points`` entry picks a
    hole EDGE, all in sheet meters.  The table lands with its top-left corner at
    ``anchor_xy`` and is validated (row/column count + header) before returning.
    """
    draw = adapter.currentModel
    name = view_name(adapter, view)
    if not draw.ActivateView(name):
        raise RuntimeError(f"failed to activate hole-table view {name!r}")
    draw.ClearSelection2(True)
    datum = draw.Extension.SelectByID2(
        "", "VERTEX", datum_xy[0], datum_xy[1], 0.0, False, 1, null_callout(), 0
    )
    if not datum:
        raise RuntimeError(f"failed to select {label} hole-table datum vertex")
    for x, y in hole_points:
        selected = draw.Extension.SelectByID2(
            "", "EDGE", x, y, 0.0, True, 2, null_callout(), 0
        )
        if not selected:
            raise RuntimeError(
                f"failed to select {label} hole-table edge at sheet ({x:g}, {y:g})"
            )
    table = view.InsertHoleTable3(
        False,
        anchor_xy[0],
        anchor_xy[1],
        1,  # swBOMConfigurationAnchor_TopLeft
        "A",
        str(hole_table_template(adapter)),
        1,  # swHoleTableTagOrder_XY
        1,  # swHoleTable_AlphaNumericTags
        None,
    )
    draw.ClearSelection2(True)
    if table is None:
        raise RuntimeError(f"SolidWorks failed to create the {label} hole table")
    table = _sw_type_info.early_bound_or_flag(table, "IHoleTableAnnotation")
    feature = table.HoleTable
    if feature is None:
        raise RuntimeError("native hole table annotation has no feature")
    feature = _sw_type_info.early_bound_or_flag(feature, "IHoleTable")
    feature.CombineSameSize = False
    feature.CombineTags = False
    adapter.currentModel.EditRebuild3()
    table = _sw_type_info.early_bound(table, "ITableAnnotation")
    # Indexed COM properties such as Text2 are omitted by the late-bound
    # dispatch returned from IHoleTableAnnotation.  Wrap the same dispatch in
    # its generated early-bound interface before using the setter.
    if not _sw_type_info.is_early_bound(table, "ITableAnnotation"):
        raise RuntimeError("ITableAnnotation early-bound wrapper is unavailable")
    if basic_locations:
        for column, heading in ((1, "X LOC (BASIC)"), (2, "Y LOC (BASIC)")):
            if not table.IsCellTextEditable(0, column):
                raise RuntimeError(f"native hole-table header column {column} is not editable")
            table.SetText2(0, column, False, heading)
            applied_heading = str(table.DisplayedText2(0, column, False) or "")
            if applied_heading.upper() != heading:
                raise RuntimeError(
                    f"native hole-table header did not persist: {applied_heading!r}"
                )
        adapter.currentModel.EditRebuild3()
    rows = int(adapter._get_attr_or_call(table, "RowCount") or 0)
    columns = int(adapter._get_attr_or_call(table, "ColumnCount") or 0)
    contents = tuple(
        tuple(
            str(
                adapter._attempt(
                    lambda row=row, column=column: table.DisplayedText(row, column)
                )
                or ""
            )
            for column in range(columns)
        )
        for row in range(rows)
    )
    expected_rows = 1 + len(hole_points)
    if (rows, columns) != (expected_rows, 4):
        raise RuntimeError(
            f"native hole table is {rows}x{columns}, "
            f"expected {expected_rows}x4: {contents!r}"
        )
    header = contents[0]
    expected = (
        "TAG",
        "X LOC (BASIC)" if basic_locations else "X LOC",
        "Y LOC (BASIC)" if basic_locations else "Y LOC",
        "SIZE",
    )
    if tuple(value.upper() for value in header) != expected:
        raise RuntimeError(f"native hole-table header is unexpected: {header!r}")
    _telemetry.success(
        f"native hole table inserted: {rows - 1} holes, header={header}"
    )
    return table


def stamp_drawing_summary(adapter: Any, drawing_model: Any, fields: dict[int, str]) -> None:
    """Write and read-verify the drawing document summary metadata."""
    model_doc = _sw_type_info.early_bound_or_flag(drawing_model, "IModelDoc2")
    for field, value in fields.items():
        # SummaryInfo is a property: early binding splits it into a getter
        # (SummaryInfo(field)) and a setter (SetSummaryInfo(field, value)).
        # A 2-arg SummaryInfo(field, value) put only worked under late binding.
        model_doc.SetSummaryInfo(field, value)
        if model_doc.SummaryInfo(field) != value:
            raise RuntimeError(f"drawing summary field {field} did not persist")


# An isometric/pictorial view's axis-aligned outline is mostly empty diagonal
# space, so its box is not a faithful collision footprint -- give such views
# ``NONE`` collision scope. ``GetOrientationName`` returns the predefined view
# name (e.g. "*Isometric"); ortho views return "*Front"/"*Right"/... and
# projected / section / detail views return "".
_PICTORIAL_ORIENTATIONS = frozenset({"*isometric", "*dimetric", "*trimetric"})

# A note centered inside its owning view is treated as a hole tag / balloon
# (detail on the view) only when it is also SMALL: native hole-table tags span
# ~6 mm, whereas the general-notes block is >50 mm on a side. The size gate keeps
# the exemption narrow so a large general note accidentally dropped onto its own
# view is still audited as a collision (Codex #269).
_TAG_MAX_SPAN_M = 0.015


def _view_scope(adapter: Any, view: Any) -> CollisionScope:
    """``NONE`` for a pictorial view (empty diagonal box), ``ALL`` for an ortho view."""
    orientation = str(adapter._get_attr_or_call(view, "GetOrientationName") or "")
    if orientation.strip().lower() in _PICTORIAL_ORIENTATIONS:
        return CollisionScope.NONE
    return CollisionScope.ALL


def _is_small_tag(element: LayoutElement) -> bool:
    """True if ``element`` is small enough to be a hole tag / balloon, not a block."""
    return (
        element.xmax - element.xmin <= _TAG_MAX_SPAN_M
        and element.ymax - element.ymin <= _TAG_MAX_SPAN_M
    )


def _center_inside(element: LayoutElement, outline: tuple[float, float, float, float]) -> bool:
    """True if ``element``'s center lies within the ``(xmin,ymin,xmax,ymax)`` box."""
    cx = (element.xmin + element.xmax) / 2.0
    cy = (element.ymin + element.ymax) / 2.0
    xmin, ymin, xmax, ymax = outline
    return xmin <= cx <= xmax and ymin <= cy <= ymax


def _note_element(adapter: Any, annotation: Any, name: str) -> LayoutElement | None:
    """Box a free NOTE from ``INote.GetExtent`` (lower-left / upper-right in meters).

    A LEADERED note is deliberately pointing at (and sitting over) view geometry
    -- e.g. an arrowed hole-group tag -- so it is given ``NON_VIEW`` scope: its
    overlap with the view it points at is intended, but a collision with a free
    note / table / title block (and any off-sheet placement) is still audited.
    """
    leadered = int(adapter._get_attr_or_call(annotation, "GetLeaderCount") or 0) > 0
    note = adapter._attempt(
        lambda: adapter._get_attr_or_call(annotation, "GetSpecificAnnotation")
    )
    if note is None:
        return None
    note = _sw_type_info.early_bound_or_flag(note, "INote", "GetExtent")
    extent = adapter._attempt(lambda: adapter._get_attr_or_call(note, "GetExtent"))
    if not extent:
        return None
    x0, y0, _z0, x1, y1, _z1 = (float(v) for v in extent)
    return LayoutElement(
        name,
        "note",
        min(x0, x1),
        min(y0, y1),
        max(x0, x1),
        max(y0, y1),
        scope=CollisionScope.NON_VIEW if leadered else CollisionScope.ALL,
    )


def _table_element(adapter: Any, table: Any, name: str) -> LayoutElement | None:
    """Box a TABLE (``ITableAnnotation``) from its anchor plus column/row spans.

    The project's hole tables are inserted top-left-anchored
    (``swBOMConfigurationAnchor_TopLeft``), so the anchor position (read off the
    table's underlying ``IAnnotation``) is the top-left corner and the box grows
    right and DOWN from it.
    """
    table = _sw_type_info.early_bound_or_flag(
        table, "ITableAnnotation", "GetAnnotation"
    )
    inner = adapter._attempt(
        lambda: adapter._get_attr_or_call(table, "GetAnnotation")
    )
    if inner is None:
        return None
    inner = _sw_type_info.early_bound_or_flag(
        inner, "IAnnotation", "GetPosition"
    )
    position = adapter._attempt(
        lambda: adapter._get_attr_or_call(inner, "GetPosition")
    )
    if not position:
        return None
    rows = int(adapter._get_attr_or_call(table, "RowCount") or 0)
    columns = int(adapter._get_attr_or_call(table, "ColumnCount") or 0)
    width = sum(
        float(adapter._attempt(lambda i=i: table.GetColumnWidth(i)) or 0.0)
        for i in range(columns)
    )
    height = sum(
        float(adapter._attempt(lambda i=i: table.GetRowHeight(i)) or 0.0)
        for i in range(rows)
    )
    x, y = float(position[0]), float(position[1])
    return LayoutElement(name, "table", x, y - height, x + width, y)


def _gdt_element(adapter: Any, annotation: Any, name: str) -> LayoutElement | None:
    """Box a native GD&T symbol as a nominal square around its GetPosition anchor.

    Datum tags / feature-control frames / surface-finish symbols expose no real
    bounding box, so a fixed nominal half-span is used -- good enough to catch a
    symbol placed clear off the sheet. Given ``NONE`` collision scope: the nominal
    box is too coarse to assert an overlap (a datum tag placed beside its own
    control frame would self-collide), so the symbol is overflow-checked only.
    """
    position = adapter._attempt(
        lambda: adapter._get_attr_or_call(annotation, "GetPosition")
    )
    if not position:
        return None
    x, y = float(position[0]), float(position[1])
    half = _NOMINAL_GDT_HALF_M
    return LayoutElement(
        name, "gdt", x - half, y - half, x + half, y + half, scope=CollisionScope.NONE
    )


def _dim_element(adapter: Any, annotation: Any, name: str) -> LayoutElement | None:
    """Box a display dimension / hole callout as a small nominal square (NONE scope).

    Like GD&T, a dimension exposes only a text-anchor ``GetPosition`` and sits on
    the geometry it measures, so it is overflow-checked and title-block-keep-out
    checked only -- never overlap-checked against a view (Codex #269 thread 1).
    """
    position = adapter._attempt(
        lambda: adapter._get_attr_or_call(annotation, "GetPosition")
    )
    if not position:
        return None
    x, y = float(position[0]), float(position[1])
    half = _NOMINAL_DIM_HALF_M
    return LayoutElement(
        name, "dim", x - half, y - half, x + half, y + half, scope=CollisionScope.NONE
    )


def _iter_view_annotations(adapter: Any, view: Any):
    """Yield each free ``LayoutElement`` (note, GD&T symbol or dimension) a view owns.

    ``IView.GetAnnotations`` returns dimensions, center marks, cosmetic-thread
    callouts, notes and GD&T symbols; NOTES (swNote), native GD&T symbols (datum
    tag / feature-control frame / surface-finish) and DISPLAY DIMENSIONS / hole
    callouts (swDisplayDimension) become elements. Tables come from
    ``GetTableAnnotations`` instead.
    """
    annotations = adapter._attempt(
        lambda: adapter._get_attr_or_call(view, "GetAnnotations")
    ) or []
    for annotation in annotations:
        annotation = _sw_type_info.early_bound_or_flag(
            annotation,
            "IAnnotation",
            "GetType",
            "GetName",
            "GetSpecificAnnotation",
            "GetPosition",
            "GetLeaderCount",
        )
        kind = int(adapter._get_attr_or_call(annotation, "GetType") or 0)
        name = str(adapter._get_attr_or_call(annotation, "GetName") or "")
        if kind == _ANNOT_NOTE:
            element = _note_element(adapter, annotation, name)
        elif kind in _GDT_TYPES:
            element = _gdt_element(adapter, annotation, name)
        elif kind == _ANNOT_DIM:
            element = _dim_element(adapter, annotation, name)
        else:
            continue
        if element is not None:
            yield element


def _iter_tables(adapter: Any, view: Any):
    """Yield each table ``LayoutElement`` owned by ``view`` (or the sheet view)."""
    tables = adapter._attempt(
        lambda: adapter._get_attr_or_call(view, "GetTableAnnotations")
    ) or []
    for table in tables:
        table = _sw_type_info.early_bound_or_flag(
            table, "ITableAnnotation", "GetAnnotation"
        )
        inner = adapter._attempt(
            lambda: adapter._get_attr_or_call(table, "GetAnnotation")
        )
        if inner is not None:
            inner = _sw_type_info.early_bound_or_flag(
                inner, "IAnnotation", "GetName"
            )
        name = (
            str(adapter._get_attr_or_call(inner, "GetName") or "")
            if inner is not None
            else "table"
        )
        element = _table_element(adapter, table, name)
        if element is not None:
            yield element


def collect_layout_elements(
    adapter: Any,
) -> tuple[list[LayoutElement], float, float]:
    """Gather every free-standing drawing element and the sheet size (meters).

    Elements are:

    * every real drawing view (``IView.GetOutline``), pictorial views given
      ``NONE`` collision scope so their empty diagonal box does not drive false
      collisions;
    * each NOTE a real view owns (the general-notes block and schedule cells); a
      SMALL note centered inside its own view is a hole tag / balloon sitting on
      the geometry and is scoped ``NON_VIEW`` (does not collide with its view);
    * every native GD&T symbol (datum tag / feature-control frame /
      surface-finish) and DISPLAY DIMENSION / hole callout, boxed nominally and
      scoped ``NONE`` (no real bbox API, and they sit on the geometry they
      annotate) -- overflow- and title-block-keep-out-checked only;
    * every TABLE (hole tables land on the SHEET view, so it is scanned too);
    * two reserved KEEP-OUT boxes -- the checked-in title block and its
      projection symbol -- so no content may land on either.

    Notes owned by the SHEET view are the sheet-format frame + zone labels (at
    the sheet edges by design) and are excluded.
    """
    drawing_model = adapter.currentModel
    sheet = adapter._get_attr_or_call(drawing_model, "GetCurrentSheet")
    if sheet is None:
        raise RuntimeError("drawing has no current sheet to audit layout on")
    properties = list(adapter._get_attr_or_call(sheet, "GetProperties") or [])
    if len(properties) < 7:
        raise RuntimeError(f"cannot read sheet size to audit layout: {properties!r}")
    width, height = float(properties[5]), float(properties[6])

    elements: list[LayoutElement] = []
    # Tables are deduped by name: SolidWorks can surface the same table under both
    # its owning view and the sheet, and a duplicated box would self-collide.
    tables: dict[str, LayoutElement] = {}
    for view in iter_views(adapter):
        name = view_name(adapter, view)
        outline = adapter._attempt(
            lambda v=view: adapter._get_attr_or_call(v, "GetOutline")
        )
        view_box: tuple[float, float, float, float] | None = None
        if outline:
            view_box = tuple(float(v) for v in outline)  # xmin,ymin,xmax,ymax
            elements.append(
                LayoutElement(
                    name,
                    "view",
                    *view_box,
                    scope=_view_scope(adapter, view),
                )
            )
        for element in _iter_view_annotations(adapter, view):
            # Record the owning view: a NON_VIEW annotation is exempt from
            # colliding with THIS view only, not other drawing views (Codex #269
            # thread 3).
            element = replace(element, owner=name)
            # A SMALL note centered inside its owning view is a hole tag / balloon
            # sitting on the geometry -- give it NON_VIEW scope so it does not
            # collide with the view it sits on (but still collides with a free
            # note / table, a DIFFERENT view, and is checked for OVERFLOW). A LARGE
            # note centered in its view is a general-notes block accidentally
            # dropped on the view, so it stays ALL-scope and the audit reports the
            # collision (Codex #269).
            if (
                element.kind == "note"
                and view_box is not None
                and _center_inside(element, view_box)
                and _is_small_tag(element)
            ):
                element = replace(element, scope=CollisionScope.NON_VIEW)
            elements.append(element)
        for table in _iter_tables(adapter, view):
            tables[table.label] = table

    # Hole tables anchor to the SHEET view, not a drawing view -- scan it for
    # tables only (its notes are the sheet-format frame + title block).
    sheet_view = adapter._attempt(lambda: drawing_model.GetFirstView())
    if sheet_view is not None:
        for table in _iter_tables(adapter, sheet_view):
            tables[table.label] = table

    elements.extend(tables.values())
    # Reserve the checked-in title block + its projection symbol as keep-outs: any
    # element overlapping either is flagged (the two never collide with each other).
    elements.append(
        LayoutElement(
            "title-block",
            "titleblock",
            _TITLE_BLOCK_LEFT_M,
            0.0,
            width,
            _TITLE_BLOCK_TOP_M,
        )
    )
    elements.append(LayoutElement("projection-symbol", "titleblock", *_PROJ_SYMBOL_BOX_M))
    return elements, width, height


def check_drawing_layout(adapter: Any) -> None:
    """Fail loud if any two drawing elements collide or one runs off the sheet.

    Runs at the end of every recipe's layout, right before the drawing is saved
    (see :func:`finalize_drawing`), so a print can never ship with a note landed
    on a view or a table hanging over the border -- defects the dimensional and
    format gates cannot see.
    """
    with _telemetry.span("drawing.layout_audit") as span:
        elements, width, height = collect_layout_elements(adapter)
        overlaps, overflows = audit_layout(elements, width, height)
        if span is not None:
            span.set_attribute("elements", len(elements))
            span.set_attribute("overlaps", len(overlaps))
            span.set_attribute("overflows", len(overflows))
        if not overlaps and not overflows:
            _telemetry.success(
                f"drawing layout clean: {len(elements)} elements, "
                "no overlaps or overflows"
            )
            return
        raise RuntimeError(
            "drawing layout audit failed "
            f"({len(overlaps)} overlap(s), {len(overflows)} overflow(s)):\n"
            + format_findings(overlaps, overflows)
        )


async def finalize_drawing(
    adapter: Any,
    outputs: DrawingOutputs,
    *,
    pdf_title: str,
    scale: tuple[float, float] = (1.0, 1.0),
) -> dict[str, str]:
    """Save, reopen-validate, and export the finished drawing (SLDDRW/PDF/PNG).

    The reopen round-trips make the saved artifact prove its own sheet scale
    and format; the PDF is metadata-sanitized and rendered to the exact ASME B
    PNG.  Returns the artifact dict every drawing recipe returns from build().
    """
    drawing_model = adapter.currentModel
    drawing_model.ClearSelection2(True)
    drawing_model.EditRebuild3()
    sheet = adapter._get_attr_or_call(drawing_model, "GetCurrentSheet")
    if sheet is None:
        raise RuntimeError("finished drawing has no current sheet")
    sheet_name = adapter._get_attr_or_call(sheet, "GetName")
    if not sheet_name or not drawing_model.ActivateSheet(sheet_name):
        raise RuntimeError("failed to activate drawing sheet for export")
    if not sheet.SetScale(float(scale[0]), float(scale[1]), False, False):
        raise RuntimeError("failed to set final drawing sheet scale")
    assert_asme_b_sheet(adapter, sheet, phase="before save", scale=scale)

    # The layout is now complete -- audit element collisions / sheet overflow on
    # the finished sheet before the first save, so a broken layout never reaches
    # the saved SLDDRW / PDF / PNG.
    check_drawing_layout(adapter)

    artifacts = save_drawing(adapter, str(outputs.slddrw))
    drawing_model, sheet = await reopen_drawing(adapter, outputs.slddrw)
    if not sheet.SetScale(float(scale[0]), float(scale[1]), False, False):
        raise RuntimeError("failed to persist reopened drawing sheet scale")
    check(
        "save final drawing sheet scale",
        await adapter.save_file(str(outputs.slddrw)),
    )
    drawing_model, sheet = await reopen_drawing(adapter, outputs.slddrw)
    assert_asme_b_sheet(adapter, sheet, phase="post-save reopen", scale=scale)
    artifacts.update(save_drawing(adapter, "", pdf_path=str(outputs.pdf)))
    sanitize_pdf_metadata(outputs.pdf, title=pdf_title)
    render_pdf_png(outputs.pdf, outputs.png)
    artifacts["png"] = str(outputs.png.resolve())
    if set(artifacts) != {"drawing", "pdf", "png"}:
        raise RuntimeError(f"drawing export incomplete: {artifacts!r}")
    return artifacts


def draw_note_table(
    adapter: Any,
    *,
    rows: Sequence[Sequence[str]],
    column_x: Sequence[float],
    row_y: Sequence[float],
) -> None:
    """Place a compact schedule using aligned notes.

    Geometry stays in the checked-in sheet format.  The drawing recipe supplies
    only row content, so future prints can reuse the same uncluttered schedule
    layout without adding table objects or template-specific anchors.
    """
    if len(rows) != len(row_y):
        raise ValueError("table row content and row positions differ")
    for y, row in zip(row_y, rows, strict=True):
        if len(row) != len(column_x):
            raise ValueError("table row has the wrong number of columns")
        for x, text in zip(column_x, row, strict=True):
            if add_note(adapter, text, x, y) is None:
                raise RuntimeError(f"failed to add schedule cell {text!r}")
