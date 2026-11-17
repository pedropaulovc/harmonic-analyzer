"""Reusable ``IDrawingDoc`` COM helpers for building engineering drawings.

Generic, project-agnostic primitives that turn an already-open model into a
multi-view engineering drawing, driven through the same raw-COM surface as the
rest of the PyWin32 adapter (``adapter._attempt`` / ``adapter.swApp`` /
``adapter.currentModel`` / ``adapter._get_attr_or_call``). Any COM-capable
project can import these.

Design note — these are **module-level functions, not an adapter mixin**, on
purpose. Nothing in a part/assembly build graph imports this module (only a
drawing build script does), so editing it cannot change any part's or
assembly's geometry. That is what lets the harmonic-analyzer recipe digest
exclude ``adapters/solidworks/drawing.py`` from every part *and* assembly cache
key: the exclusion is safe precisely because the module is never imported —
hence never called — by any build script other than a drawing one. Wiring these
as a mixin on ``PyWin32Adapter`` would instead pull the module into every
adapter import and force a one-time whole-fleet rebuild, which we avoid.

All helpers take the live ``adapter`` first and run their COM inline (the same
threading context every ``_common`` build helper uses); they are null-checked
and fail loud only where a missing result means the drawing is unusable.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Callable
from contextlib import AbstractContextManager, nullcontext
from typing import Any, Literal

from .. import sw_type_info as _sw_type_info
from ..com_variant import double_array, null_callout

logger = logging.getLogger(__name__)

# swUserPreferenceStringValue_e template slots. The adapter's create_drawing uses
# slot 1 (the ASSEMBLY template) by mistake, so NewDocument returns null; the
# correct drawing slot is 10 (part=8, assembly=9, drawing=10 — matching the
# create_part/create_assembly probes in io.py).
_SW_PREF_TEMPLATE_PART = 8
_SW_PREF_TEMPLATE_DRAWING = 10

# --- swconst values used below (documented inline; this module stays free of a
# hard dependency on the generated swconst wrapper so it imports on any seat). --
_SW_DWG_TEMPLATE_NONE = 13  # swDwgTemplates_e.swDwgTemplateNone
_SW_DWG_TEMPLATE_ASIZE = 0  # swDwgTemplates_e.swDwgTemplateAsize (11x8.5 landscape)
_SW_DWG_TEMPLATE_BSIZE = 2  # swDwgTemplates_e.swDwgTemplateBsize (17x11 landscape)
_SW_PAPER_USER_DEFINED = 12  # swDwgPaperSizes_e.swDwgPapersUserDefined
# swDwgTemplates_e and swDwgPaperSizes_e share the same ints for the standard sizes
# (Asize=0, Bsize=2, ...), so a standard-size sheet setup passes ``template`` for BOTH
# the size template AND the paper size — see setup_sheet.
# Public size selectors for setup_sheet(template=...). NONE = a blank sheet (no
# stock border/title-block); pair it with paper_width/paper_height for a custom size.
SW_DWG_TEMPLATE_NONE = _SW_DWG_TEMPLATE_NONE
SW_DWG_TEMPLATE_ASIZE = _SW_DWG_TEMPLATE_ASIZE
SW_DWG_TEMPLATE_BSIZE = _SW_DWG_TEMPLATE_BSIZE
_SW_IMPORT_FROM_ENTIRE_MODEL = 0  # swImportModelItemsSource_e
_SW_INSERT_DIMS_MARKED = 0x8000  # swInsertAnnotation_e.swInsertDimensionsMarkedForDrawing
_SW_INSERT_DIMS_NOTMARKED = 0x80000  # swInsertAnnotation_e.swInsertDimensionsNotMarkedForDrawing
# "All dimensions" = marked OR not-marked; parametric dims created via the API are
# not reliably flagged "marked for drawing", so the marked-only mask misses them.
_SW_INSERT_DIMS_ALL = _SW_INSERT_DIMS_MARKED | _SW_INSERT_DIMS_NOTMARKED
_SW_INSERT_HOLE_CALLOUT = 0x100000  # swInsertAnnotation_e.swInsertholeCallout
# swInsertAnnotation_e.swInsertHoleWizardLocationDimensions — the LOCATION dims of a
# Hole Wizard hole live on its absorbed positioning sketch, which the marked/unmarked
# masks (even with HiddenFeatureDims) never pull; this dedicated bit is the ONLY way
# to import them, so a dimensioned wizard-hole position shows its X/Y locators on the
# drawing (verified live — without it the front view drops the set-screw locators).
_SW_INSERT_HOLE_WZD_LOCATION = 0x20000
_SW_CM_TYPE_HOLE = 0x1  # swAutoInsertCenterMarkTypes_e.swAutoInsertCenterMarkType_Hole
_SW_CM_TYPE_SLOTS = 0x4  # swAutoInsertCenterMarkTypes_e.swAutoInsertCenterMarkType_Slots
_SW_CM_CONN_NONE = 0  # swCenterMarkConnectionLine_e.swCenterMarkConnectionLine_None
_SW_ANNOT_CENTER_MARK = 13  # swAnnotationType_e.swCenterMarkSym

# Optional observer of every ``auto_center_marks`` call, set once by a
# downstream build (no telemetry dependency here, as with save_drawing's
# ``artifact_context``). It receives the view's name, its centre-mark count
# before and after AutoInsertCenterMarks2, the requested feature types and
# the call's result. Unset, the call makes no extra COM reads.
CenterMarkObserver = Callable[[dict[str, Any]], None]
CENTER_MARK_OBSERVER: CenterMarkObserver | None = None

# Like ``artifact_context``, placement observation has no telemetry dependency.
PlaceViewContext = Callable[[str, dict[str, Any]], AbstractContextManager[Any]]
_place_view_context: PlaceViewContext | None = None


def set_place_view_context(factory: PlaceViewContext | None) -> None:
    """Install or clear placement contexts; registration performs no COM work.

    ``factory(name, attributes)`` must return a context that propagates errors.
    Already-imported ``place_view`` aliases consult this factory on each call.
    Attributes come only from arguments; scale observation records an attempt,
    not verification that SolidWorks persisted the requested ratio.
    Names include an argument-derived source/orientation/placement hint, not an
    actual sheet identity. Stable ``phase_kind`` attributes support aggregation.
    """
    global _place_view_context
    _place_view_context = factory


# Document unit preferences (swUserPreferenceIntegerValue_e + value enums), read
# from the SOLIDWORKS 2026 swconst typelib on this seat.
_SW_PREF_UNIT_SYSTEM = 263  # swUserPreferenceIntegerValue_e.swUnitSystem
_SW_UNIT_SYSTEM_MMGS = 5  # swUnitSystem_e.swUnitSystem_MMGS
_SW_PREF_UNITS_LINEAR = 47  # swUserPreferenceIntegerValue_e.swUnitsLinear
_SW_LENGTH_MM = 0  # swLengthUnit_e.swMM
_SW_PREF_UNITS_LINEAR_DP = 49  # swUserPreferenceIntegerValue_e.swUnitsLinearDecimalPlaces
_SW_DOC_DRAWING = 3  # swDocumentTypes_e.swDocDRAWING

# Dimension text parts (swDimensionTextParts_e) + dimension type (swDimensionType_e).
_SW_DIM_TEXT_ALL = 0  # swDimensionTextAll (whole string incl. value — SetText only)
_SW_DIM_TEXT_PREFIX = 1  # swDimensionTextPrefix (leftmost, before the Ø/value)
_SW_DIM_TEXT_BELOW = 4  # swDimensionTextCalloutBelow
_SW_DIM_TYPE_DIAMETER = 6  # swDiameterDimension

# Sketch line style/weight (swLineStyles_e / swLineWeights_e) for symbol geometry.
_SW_LINE_SOLID = 0  # swLineCONTINUOUS
_SW_LINE_NORMAL = 1  # swLW_NORMAL
_SW_COLOR_BLACK = 0  # COLORREF 0x000000

# Dimension tolerance types (swTolType_e), for callers that stamp tolerances.
TOL_NONE = 0
TOL_BASIC = 1
TOL_LIMIT = 3
TOL_FIT = 7
TOL_BLOCK = 10


def _draw(adapter: Any) -> Any:
    """Return the active drawing document (``IDrawingDoc``/``IModelDoc2``).

    Raises if there is no active model — every helper here needs one, and a
    silent ``None`` would only defer the failure to a more confusing COM error.
    """
    model = getattr(adapter, "currentModel", None)
    if model is None:
        raise RuntimeError("No active drawing document (adapter.currentModel is None)")
    return model


def _ddoc(adapter: Any) -> Any:
    """The active drawing rebound to ``IDrawingDoc`` for its doc-type members.

    ``currentModel`` is always ``IModelDoc2`` (``io._bind_document``), which does
    NOT declare the drawing verbs (``ActivateView``/``ActivateSheet``/
    ``GetCurrentSheet``/``SetupSheet6``/``InsertModelAnnotations3``/
    ``GetFirstView``/``CreateDrawViewFromModelView3`` …); those live on
    ``IDrawingDoc``. Use this for those members and plain :func:`_draw` for the
    ``IModelDoc2`` members (``EditRebuild3``/``ClearSelection2``).
    """
    return _sw_type_info.early_bound(_draw(adapter), "IDrawingDoc")


def _resolve_drawing_template(adapter: Any) -> str:
    """Return a usable ``.drwdot`` path, or '' if none can be found.

    Prefers the configured default-drawing template (pref slot 10); if that is
    empty/missing, looks for a ``*.drwdot`` beside the part template.
    """
    app = adapter.swApp
    template = adapter._attempt(lambda: app.GetUserPreferenceStringValue(_SW_PREF_TEMPLATE_DRAWING))
    if isinstance(template, str) and template and os.path.isfile(template):
        return template
    part_t = adapter._attempt(lambda: app.GetUserPreferenceStringValue(_SW_PREF_TEMPLATE_PART))
    if isinstance(part_t, str) and part_t:
        directory = os.path.dirname(part_t)
        for entry in sorted(os.listdir(directory) if os.path.isdir(directory) else []):
            if entry.lower().endswith(".drwdot"):
                return os.path.join(directory, entry)
    return ""


def read_custom_properties(
    adapter: Any, names: list[str], *, model: Any = None
) -> dict[str, str]:
    """Read file-level custom properties off a model by name.

    Drives ``IModelDoc2.GetCustomInfoValue("", name)`` — the resolved-value read
    the build's ``apply_custom_properties`` verifies its writes through — for each
    requested name against ``model`` (defaults to ``adapter.currentModel``). Only
    non-empty values land in the returned dict, so a caller can tell a stamped
    property from a blank/absent one and fail loud on a missing make-critical field.

    Read the SOURCE model (e.g. the ``.SLDPRT`` right after ``open_model``, while it
    is still current) rather than the drawing: the drawing carries no custom
    properties of its own until they are linked, but the part it references does.
    """
    doc = model if model is not None else adapter.currentModel
    out: dict[str, str] = {}
    for name in names:
        val = adapter._attempt(
            lambda n=name: doc.GetCustomInfoValue("", n), default=""
        )
        if isinstance(val, str) and val:
            out[name] = val
    return out


def new_drawing(
    adapter: Any,
    *,
    template: str | None = None,
    width: float = 0.2794,
    height: float = 0.2159,
) -> Any:
    """Create a blank drawing document from a template.

    Replacement for the adapter's ``create_drawing`` (which reads the wrong
    template preference slot). ``template`` is an explicit ``.drwdot`` path (e.g. a
    project template checked into the repo); when omitted or missing, the seat's
    configured default is resolved instead. Creates the doc, flags it as a drawing,
    and sets it as ``adapter.currentModel``. ``width`` / ``height`` (meters) default
    to A-size landscape (11 x 8.5 in) and are only honored when the template leaves
    the sheet user-defined.
    """
    app = adapter.swApp
    if app is None:
        raise RuntimeError("SolidWorks application is not connected")
    if template and os.path.isfile(template):
        template = os.path.abspath(template)
    else:
        if template:
            logger.warning("drawing template %r not found; using seat default", template)
        template = _resolve_drawing_template(adapter)
    if not template:
        raise RuntimeError("No drawing template (.drwdot) configured on this seat")
    model = adapter._attempt(
        lambda: app.NewDocument(template, _SW_PAPER_USER_DEFINED, float(width), float(height))
    )
    if not model:
        raise RuntimeError(f"NewDocument failed for drawing template {template!r}")
    # Early-bind the new drawing exactly like the open path (_bind_document):
    # NewDocument hands back a raw dispatch, and without this currentModel stays
    # late-bound, so drawing COM calls (SelectByID2's None Callout, …) take the
    # dynamic path where a bare None mismatches. IModelDoc2's fallback resolves
    # the IDrawingDoc members, so no flag_doc is needed.
    model = _sw_type_info.early_bound(model, "IModelDoc2")
    adapter.currentModel = model
    return model


def resolve_sheet_format(adapter: Any, name: str = "a - landscape.slddrt") -> str:
    """Return the full path to a standard SolidWorks sheet-format (.slddrt), or ''.

    Derives the install's ``lang/<language>/sheetformat`` directory from the part
    template location, so it works across seats without a hard-coded path.
    """
    app = adapter.swApp
    part_t = adapter._attempt(lambda: app.GetUserPreferenceStringValue(_SW_PREF_TEMPLATE_PART))
    if not isinstance(part_t, str) or not part_t:
        return ""
    base = os.path.dirname(os.path.dirname(part_t))  # ...\SOLIDWORKS <ver>
    lang_dir = os.path.join(base, "lang")
    languages = os.listdir(lang_dir) if os.path.isdir(lang_dir) else []
    for lang in ["english", *languages]:
        candidate = os.path.join(base, "lang", lang, "sheetformat", name)
        if os.path.isfile(candidate):
            return candidate
    return ""


def apply_sheet_format(adapter: Any, format_path: str, *, keep_notes: bool = True) -> int | None:
    """Load a sheet-format (.slddrt) onto the current sheet (border + title block).

    The default ``Drawing.drwdot`` template ships a blank sheet, so apply a
    standard format to get an ASME border, zones, and a title-block frame. Also
    forces the sheet format visible (the blank template may hide it). Returns the
    ``swReloadTemplateResult_e`` code (0=Success, 2=FileNotFound, 3=CustomSheet,
    4=ViewOnly), or -1 if the sheet/path was unavailable.
    """
    draw = _draw(adapter)
    if not format_path or not os.path.isfile(format_path):
        logger.warning("sheet format not found: %r", format_path)
        return -1
    sheet = adapter._attempt(lambda: _ddoc(adapter).GetCurrentSheet())
    if not sheet:
        return -1
    sheet = _sw_type_info.early_bound_or_flag(
        sheet, "ISheet", "SetTemplateName", "ReloadTemplate"
    )
    adapter._attempt(lambda: sheet.SetTemplateName(format_path))
    result = adapter._attempt(lambda: sheet.ReloadTemplate(bool(keep_notes)), default=None)
    adapter._attempt(lambda: setattr(sheet, "SheetFormatVisible", True))
    adapter._attempt(lambda: draw.ForceRebuild3(False))
    return result


def setup_sheet(
    adapter: Any,
    *,
    template: int = _SW_DWG_TEMPLATE_ASIZE,
    scale: tuple[float, float] = (1.0, 1.0),
    first_angle: bool = False,
    property_view: str | None = None,
    paper_width: float = 0.0,
    paper_height: float = 0.0,
) -> bool:
    """Configure the active drawing's first sheet via ``SetupSheet6``.

    Defaults to ASME **third-angle** projection (``first_angle=False``) on an
    A-size landscape sheet at the given ``scale`` (numerator, denominator); pass
    ``template=_SW_DWG_TEMPLATE_BSIZE`` for a 17x11 B-size sheet. ``property_view``
    names the model view whose custom properties feed ``$PRPSHEET`` title-block
    links. Follows the API remark by issuing a ``ForceRebuild3`` afterward so the
    projection change takes effect.

    The paper size tracks ``template``: a standard size template (Asize/Bsize/...)
    passes its own int as the ``swDwgPaperSizes_e`` paper too (the enums align), so
    the sheet is that physical size — NOT hard-wired to A, which silently shrank a
    B-size setup back to 11x8.5.
    """
    draw = _draw(adapter)
    name = adapter._get_attr_or_call(_ddoc(adapter), "GetCurrentSheet")
    sheet_name = adapter._attempt(lambda: adapter._get_attr_or_call(name, "GetName"))
    sheet_name = sheet_name if isinstance(sheet_name, str) else ""
    paper = _SW_PAPER_USER_DEFINED if template == _SW_DWG_TEMPLATE_NONE else template
    ok = adapter._attempt(
        lambda: _ddoc(adapter).SetupSheet6(
            sheet_name,
            paper,
            template,
            float(scale[0]),
            float(scale[1]),
            bool(first_angle),
            "",  # TemplateName (custom only)
            float(paper_width),
            float(paper_height),
            property_view or "",
            False,  # RemoveModifiedNotes
            0.0, 0.0, 0.0, 0.0,  # zone margins
            0, 0,  # zone rows/cols
        ),
        default=False,
    )
    adapter._attempt(lambda: draw.ForceRebuild3(False))
    if not ok:
        logger.warning("SetupSheet6 returned False (sheet=%r)", sheet_name)
    return bool(ok)


def set_units_mm(adapter: Any, *, decimals: int = 2) -> None:
    """Set the active document's linear units to millimeters (MMGS).

    The parts are inch documents, so a fresh drawing inherits inch display — set
    mm here so every dimension reads in mm (matching the general note). Call
    before inserting dimensions. Select MMGS last because explicit component
    unit writes can switch the unit system to Custom.
    """
    draw = _draw(adapter)
    adapter._attempt(
        lambda: draw.SetUserPreferenceIntegerValue(_SW_PREF_UNITS_LINEAR, _SW_LENGTH_MM)
    )
    adapter._attempt(
        lambda: draw.SetUserPreferenceIntegerValue(_SW_PREF_UNITS_LINEAR_DP, int(decimals))
    )
    adapter._attempt(
        lambda: draw.SetUserPreferenceIntegerValue(_SW_PREF_UNIT_SYSTEM, _SW_UNIT_SYSTEM_MMGS)
    )


def set_units_inch(adapter: Any, *, decimals: int) -> None:
    """Set the active drawing to decimal-inch (IPS) presentation.

    Call before inserting dimensions. ``decimals`` (an ``int`` 0..8) is the
    linear decimal places. Writes the preferences below in order, unit system
    IPS last (explicit unit writes can switch the system to Custom), then reads
    every one back and raises ``RuntimeError`` listing any that differ.
    """
    if type(decimals) is not int or not 0 <= decimals <= 8:
        raise ValueError(f"decimals must be an int in 0..8, got {decimals!r}")
    draw = _draw(adapter)
    doc_type = draw.GetType()
    if doc_type != _SW_DOC_DRAWING:
        raise RuntimeError(
            f"set_units_inch requires a drawing document, got type {doc_type!r}"
        )
    ext = _sw_type_info.early_bound(draw.Extension, "IModelDocExtension")
    # (preference, swUserPreferenceOption_e scope, value) in write order; a bool
    # value is a toggle. Scope 0 is swDetailingNoOptionSpecified.
    preferences = [
        (47, 0, 3),  # swUnitsLinear = swINCHES
        (48, 0, 1),  # swUnitsLinearDecimalDisplay = swDECIMAL
        (49, 0, decimals),  # swUnitsLinearDecimalPlaces
        (522, 0, 0),  # swUnitsDecimalRounding = swUnitsDecimalRounding_HalfAway
        (62, 0, False),  # swUnitsLinearRoundToNearestFraction
        (265, 0, 3),  # swDetailingLeadingZero = swLeadingZero_DoNotShow
        (15, 0, 1),  # swDetailingDimTrailingZero = swDimShowTrailingZeroes
        (582, 0, 1),  # swDetailingTrailingZeroTolerance = show
        # swDetailingDualDimensions off for general Dimension (200), then
        # ArcLength, Chamfer, Diameter, Hole, Linear, Ordinate and Radius (202-208).
        *((43, scope, False) for scope in (200, 202, 203, 204, 205, 206, 207, 208)),
        (263, 0, 3),  # swUnitSystem = swUnitSystem_IPS, last
    ]
    for preference, scope, value in preferences:
        if type(value) is bool:
            ext.SetUserPreferenceToggle(preference, scope, value)
        else:
            ext.SetUserPreferenceInteger(preference, scope, value)
    mismatches = []
    for preference, scope, value in preferences:
        if type(value) is bool:
            actual = ext.GetUserPreferenceToggle(preference, scope)
        else:
            actual = ext.GetUserPreferenceInteger(preference, scope)
        if type(actual) is not type(value) or actual != value:
            mismatches.append(
                f"{preference}/{scope}: wanted {value!r}, read {actual!r}"
            )
    if mismatches:
        raise RuntimeError("Inch drawing units did not stick: " + "; ".join(mismatches))


def orientation_name(adapter: Any, view: Any) -> str:
    """Return an ``IView``'s model-orientation name (e.g. ``"*Front"``)."""
    name = adapter._get_attr_or_call(view, "GetOrientationName")
    return name if isinstance(name, str) else ""


# swViewEntityType_e -> the interface that declares that entity kind's members.
_VIEW_ENTITY_INTERFACE = {
    1: "IEdge",  # swViewEntityType_Edge
    2: "IVertex",  # swViewEntityType_Vertex
    3: "IFace2",  # swViewEntityType_Face
    4: "ISilhouetteEdge",  # swViewEntityType_SilhouetteEdge
}


class _RawDispatch:
    """Carrier giving a bare ``PyIDispatch`` the ``_oleobj_`` binding reads."""

    __slots__ = ("_oleobj_",)

    def __init__(self, oleobj: Any) -> None:
        self._oleobj_ = oleobj


def raw_visible_entities(
    view: Any, component: Any, entity_kind: int
) -> tuple[Any, ...]:
    """``IView.GetVisibleEntities2`` WITHOUT pywin32 wrapping each element.

    The makepy wrapper returns the array through ``_ApplyTypes_``, which runs
    ``Dispatch()`` on EVERY element: remote ``GetTypeInfo``/``GetTypeAttr``
    round-trips, ~30 ms apiece. On a 22,486-edge engraved nameplate that wrapped
    call took 674 s; this ``InvokeTypes`` fetch took 2-4 s and returned the same
    elements in the same order. Elements come back as bare ``PyIDispatch``; bind
    only the ones you use with :func:`bind_view_entity`.

    What this does NOT remove: every element is still a cross-process proxy, and
    dropping the last reference to one costs a ``Release`` round-trip (5-9 ms
    measured; 117-206 s for that nameplate's tuple). Fetching the array at all
    pays it, so a caller that needs one element of a large component should find
    it by a narrower query instead.

    The dispid comes from the live object's name table, never hard-coded. A test
    double (no ``_oleobj_``) is called directly, as ``early_bound`` does.
    """
    bound_view = _sw_type_info.early_bound(view, "IView")
    oleobj = getattr(bound_view, "_oleobj_", None)
    if oleobj is None:
        return tuple(bound_view.GetVisibleEntities2(component, entity_kind) or ())
    # Imported here so this module keeps importing on machines without pywin32.
    import pythoncom

    dispid = oleobj.GetIDsOfNames("GetVisibleEntities2")
    raw = oleobj.InvokeTypes(
        dispid,
        0,
        pythoncom.DISPATCH_METHOD,
        (pythoncom.VT_VARIANT, 0),
        ((pythoncom.VT_DISPATCH, 1), (pythoncom.VT_I4, 1)),
        getattr(component, "_oleobj_", component),
        entity_kind,
    )
    return tuple(raw or ())


def bind_view_entity(raw: Any, entity_kind: int) -> Any:
    """Bind one :func:`raw_visible_entities` element to its kind's interface.

    Constructing the generated class directly costs ~9 ms/element against
    ``Dispatch()``'s ~31 ms, and yields the same early-bound object
    ``early_bound`` would. Anything already wrapped (or a test double) passes
    through unchanged.
    """
    # A raw element is a bare PyIDispatch: it answers InvokeTypes but has no
    # ``_oleobj_``. Checked by shape, not by pywintypes class, so this module
    # still imports without pywin32.
    if hasattr(raw, "_oleobj_") or not hasattr(raw, "InvokeTypes"):
        return raw
    interface = _VIEW_ENTITY_INTERFACE[entity_kind]
    return _sw_type_info.early_bound(_RawDispatch(raw), interface)


def visible_component_entities(
    view: Any, component: Any, entity_kind: int
) -> list[Any]:
    """One component's visible entities in ``view``, each bound to its interface.

    Prefer this over calling ``GetVisibleEntities2`` on a makepy view, which pays
    the per-element ``Dispatch()`` cost (see :func:`raw_visible_entities`). When
    you only need a few elements, call :func:`raw_visible_entities` and bind
    those alone.
    """
    return [
        bind_view_entity(raw, entity_kind)
        for raw in raw_visible_entities(view, component, entity_kind)
    ]


def view_outline(adapter: Any, view: Any) -> tuple[float, float, float, float] | None:
    """Return a view's geometry bounding box ``(xmin, ymin, xmax, ymax)`` in meters.

    Note: this is the view GEOMETRY box; dimension annotations extend beyond it,
    so leave extra margin when laying out.
    """
    box = adapter._attempt(lambda: view.GetOutline())
    if not box:
        return None
    vals = list(box)
    if len(vals) < 4:
        return None
    return (float(vals[0]), float(vals[1]), float(vals[2]), float(vals[3]))


def set_view_position(
    adapter: Any, view: Any, x: float, y: float, *, move_children: bool = True
) -> bool:
    """Move ``view`` so its geometric center sits at sheet ``(x, y)`` in meters.

    Uses ``IView::SetViewPosition`` (a method — reliable under late binding, unlike
    the ``Position`` property once the view is flagged). ``move_children`` drags an
    aligned view group along. Followed by ``EditRebuild3`` so the sheet updates.
    """
    draw = _draw(adapter)
    # The position MUST be a typed VT_ARRAY|VT_R8 VARIANT; a bare Python list
    # marshals as VT_ARRAY|VT_VARIANT, which SolidWorks silently ignores.
    ok = adapter._attempt(
        lambda: view.SetViewPosition(double_array([float(x), float(y)]), bool(move_children)),
        default=False,
    )
    adapter._attempt(lambda: draw.EditRebuild3())
    return bool(ok)


def place_view(
    adapter: Any,
    model_path: str,
    view_name: str,
    x: float,
    y: float,
    *,
    scale: tuple[float, float] | None = None,
) -> Any:
    """Place a standard model view on the current sheet and return the ``IView``.

    ``view_name`` is a SolidWorks named view — e.g. ``"*Front"``, ``"*Top"``,
    ``"*Right"``, ``"*Isometric"`` (the leading ``*`` is part of the name).
    ``x``/``y`` are the view-center position on the sheet, in METERS.
    ``scale`` (num, den) overrides the sheet scale for this view.
    """
    factory = _place_view_context
    attributes: dict[str, Any] = {}
    suffix = ""
    if factory is not None:
        attributes["scale_request"] = "specified" if scale is not None else "omitted"
        if isinstance(model_path, str):
            attributes["source_file"] = os.path.basename(model_path)
        if isinstance(view_name, str):
            attributes["orientation"] = view_name
        attributes["phase_kind"] = "placement"
        # Describe built-in numbers without moving native float conversions out
        # of _attempt. This is a placement hint, never an actual sheet identity.
        source = attributes.get("source_file", "<model>")
        orientation = view_name if type(view_name) is str else "<view>"
        placement = f"{source} {orientation}"
        if type(x) is float and type(y) is float:
            placement += f" x={x!r} y={y!r}"
        suffix = f" [{placement}]"
    with factory(f"drawing.place_view{suffix}", attributes) if factory is not None else nullcontext():
        with (
            factory(
                f"drawing.place_view.create{suffix}",
                {"phase_kind": "native_create_envelope"},
            )
            if factory is not None
            else nullcontext()
        ):
            view = adapter._attempt(
                lambda: _ddoc(adapter).CreateDrawViewFromModelView3(
                    model_path, view_name, float(x), float(y), 0.0
                )
            )
            if not view:
                raise RuntimeError(
                    f"CreateDrawViewFromModelView3 failed for {view_name!r} "
                    f"(model={model_path!r})"
                )
        with (
            factory(f"drawing.place_view.bind{suffix}", {"phase_kind": "binding"})
            if factory is not None
            else nullcontext()
        ):
            view = _sw_type_info.early_bound_or_flag(view, "IView")
        if scale is not None:
            with (
                factory(
                    f"drawing.place_view.scale{suffix}",
                    {"phase_kind": "native_scale_attempt"},
                )
                if factory is not None
                else nullcontext()
            ):
                adapter._attempt(
                    lambda: setattr(
                        view, "ScaleRatio", double_array([float(scale[0]), float(scale[1])])
                    )
                )
        return view


def create_standard_views(adapter: Any, model_path: str, *, first_angle: bool = False) -> bool:
    """Create the three aligned standard orthographic views for ``model_path``.

    Uses ``Create3rdAngleViews2`` (ASME third-angle) or ``Create1stAngleViews2``.
    The views honor the sheet scale, so call :func:`setup_sheet` first. Returns
    True on success.
    """
    draw = _draw(adapter)
    method = "Create1stAngleViews2" if first_angle else "Create3rdAngleViews2"
    ok = adapter._attempt(lambda: getattr(draw, method)(model_path), default=False)
    if not ok:
        logger.warning("%s failed for %r", method, model_path)
    return bool(ok)


def iter_views(adapter: Any):
    """Yield each real drawing ``IView`` on the current sheet.

    ``GetFirstView`` returns the sheet itself; the first ``GetNextView`` is the
    first actual drawing view, so we skip the sheet and iterate from there.
    """
    node = adapter._attempt(lambda: _ddoc(adapter).GetFirstView())  # the sheet
    if not node:
        return
    node = _sw_type_info.early_bound_or_flag(node, "IView", "GetNextView")
    node = adapter._get_attr_or_call(node, "GetNextView")  # first real view
    while node:
        node = _sw_type_info.early_bound_or_flag(node, "IView", "GetNextView")
        yield node
        node = adapter._get_attr_or_call(node, "GetNextView")


def delete_view(adapter: Any, view: Any) -> bool:
    """Delete a drawing view (e.g. a redundant projection) from the sheet."""
    draw = _draw(adapter)
    name = view_name(adapter, view)
    adapter._attempt(lambda: draw.ClearSelection2(True))
    ext = adapter._attempt(lambda: draw.Extension)
    if ext is not None:
        adapter._attempt(
            lambda: ext.SelectByID2(
                name, "DRAWINGVIEW", 0.0, 0.0, 0.0, False, 0, null_callout(), 0
            )
        )
    ok = adapter._attempt(lambda: draw.EditDelete(), default=False)
    adapter._attempt(lambda: draw.EditRebuild3())
    return bool(ok)


def view_name(adapter: Any, view: Any) -> str:
    """Return an ``IView``'s document name (``GetName2``), late-binding safe."""
    name = adapter._get_attr_or_call(view, "GetName2")
    return name if isinstance(name, str) else ""


def get_view_scale(adapter: Any, view: Any) -> tuple[int, int] | None:
    """Return a view's scale as an ``(num, den)`` integer ratio, or None.

    Standard views auto-scale to fit the sheet, so read the resulting ratio back
    (rather than assuming) to keep the title-block SCALE honest.
    """
    val = adapter._get_attr_or_call(view, "ScaleRatio")
    if not val or isinstance(val, str):
        return None
    vals = list(val)
    if len(vals) < 2 or not vals[1]:
        return None
    num, den = float(vals[0]), float(vals[1])
    # Normalize to small integers where possible (e.g. 2.0:1.0 -> 2:1).
    if num >= den and den:
        return (int(round(num / den)), 1) if abs(num / den - round(num / den)) < 1e-6 else (round(num, 3), round(den, 3))
    if den > num and num:
        return (1, int(round(den / num))) if abs(den / num - round(den / num)) < 1e-6 else (round(num, 3), round(den, 3))
    return (round(num, 3), round(den, 3))


def format_scale(scale: tuple[int, int] | None) -> str:
    """Format a scale ratio as ``"2:1"`` (falls back to ``"NTS"`` if unknown)."""
    if not scale:
        return "NTS"
    return f"{scale[0]}:{scale[1]}"


def insert_model_dims(
    adapter: Any,
    view: Any,
    *,
    marked_only: bool = True,
    hole_callouts: bool = False,
    all_views: bool = False,
) -> list[Any]:
    """Pull the model's driven dimensions into ``view`` (``InsertModelAnnotations3``).

    Activates ``view`` first (annotations go into the *selected* view), then
    imports dimensions from the entire model. ``marked_only`` restricts to dims
    marked for drawing (the parametric named dims); set it False to pull every
    model dimension. Returns the inserted annotation objects (possibly empty).
    """
    draw = _draw(adapter)
    name = view_name(adapter, view)
    # Both activate AND select the view: InsertModelAnnotations3 targets the
    # currently *selected* drawing view, and activation alone does not select it.
    adapter._attempt(lambda: _ddoc(adapter).ActivateView(name))
    adapter._attempt(lambda: draw.ClearSelection2(True))
    ext = adapter._attempt(lambda: draw.Extension)  # property, not a method
    selected = False
    if ext is not None:
        selected = adapter._attempt(
            lambda: ext.SelectByID2(
                name, "DRAWINGVIEW", 0.0, 0.0, 0.0, False, 0, null_callout(), 0
            ),
            default=False,
        )
    if not selected:
        logger.warning("view %r not selected for annotation insert", name)
    types = _SW_INSERT_DIMS_MARKED if marked_only else _SW_INSERT_DIMS_ALL
    # Always pull Hole Wizard LOCATION dims — they sit on the wizard's absorbed
    # positioning sketch, which no marked/unmarked mask reaches; this is a no-op
    # when the model has no (dimensioned) wizard holes.
    types |= _SW_INSERT_HOLE_WZD_LOCATION
    if hole_callouts:
        types |= _SW_INSERT_HOLE_CALLOUT
    result = adapter._attempt(
        lambda: _ddoc(adapter).InsertModelAnnotations3(
            _SW_IMPORT_FROM_ENTIRE_MODEL,
            types,
            bool(all_views),
            True,   # DuplicateDims -> eliminate duplicates
            False,  # HiddenFeatureDims
            False,  # UsePlacementInSketch
        )
    )
    if not result:
        return []
    return list(result) if not isinstance(result, str) else []


def _delete_annotation(adapter: Any, annotation: Any) -> bool:
    """Select and delete one annotation (``IAnnotation``) from the drawing.

    Uses ``IAnnotation::Select2(Append, Mark)`` — it selects with a plain bool +
    long and needs no ``ISelectData``. (``Select3`` wants a real SelectData
    object; ``CreateSelectData`` marshals to null under this late-binding seat,
    so ``Select3`` silently returns False and selects nothing.) ``EditDelete``
    then removes the selected annotation.
    """
    draw = _draw(adapter)
    adapter._attempt(lambda: draw.ClearSelection2(True))
    ok = adapter._attempt(lambda a=annotation: a.Select2(False, 0), default=False)
    if ok:
        adapter._attempt(lambda: draw.EditDelete())
    return bool(ok)


def _note_text(adapter: Any, annotation: Any) -> str:
    """Text of a NOTE annotation (``INote::GetText``), or ``""`` for non-notes.

    ``GetSpecificAnnotation`` -> ``INote`` for a note; other annotation kinds
    (display dimensions, callouts) either lack a zero-arg ``GetText`` or raise,
    so this returns ``""`` for them — exactly the filter we want when hunting a
    stray descriptive note.
    """
    spec = adapter._attempt(lambda a=annotation: a.GetSpecificAnnotation(), default=None)
    if spec is None:
        return ""
    spec = _sw_type_info.early_bound_or_flag(spec, "INote", "GetText")
    txt = adapter._attempt(lambda s=spec: s.GetText(), default=None)
    return txt if isinstance(txt, str) else ""


def remove_notes_matching(adapter: Any, substring: str) -> int:
    """Delete every NOTE on the sheet whose text contains ``substring``.

    SolidWorks auto-inserts a descriptive hole-callout note for a Hole Wizard
    feature (e.g. ``"#5-40 Tapped Hole"``) alongside the leadered thread callout
    — a duplicate on an ASME print. This removes those notes by text match.
    Returns the number deleted. Case-insensitive.
    """
    target = substring.lower()
    hits: list[Any] = []
    for view in list(iter_views(adapter)):
        vf = _sw_type_info.early_bound_or_flag(view, "IView", "GetFirstAnnotation3")
        an = adapter._attempt(lambda x=vf: x.GetFirstAnnotation3(), default=None)
        while an is not None:
            anf = _sw_type_info.early_bound_or_flag(
                an, "IAnnotation", "GetNext3", "GetSpecificAnnotation", "Select2"
            )
            nxt = adapter._attempt(lambda x=anf: x.GetNext3(), default=None)
            if target in _note_text(adapter, anf).lower():
                hits.append(anf)
            an = nxt
    # Delete after traversal (EditDelete mutates the annotation linked list).
    return sum(1 for anf in hits if _delete_annotation(adapter, anf))


def annotate_holes_thru(
    adapter: Any,
    annotations: list[Any],
    *,
    text: str = "THRU",
    consolidate: bool = True,
    thread_map: dict[float, str] | None = None,
) -> int:
    """Turn the inserted diameter dims into ASME hole callouts (``NX Ø.. / THRU``).

    A bare ``Ø8`` doesn't tell the machinist whether the hole goes through or is
    blind; ASME hole callouts carry that. For every DIAMETER dimension in
    ``annotations`` (as returned by :func:`insert_model_dims`) this appends
    ``text`` below the value, so a through-bore reads ``Ø8.00 / THRU``.

    With ``consolidate`` (default), identical-diameter holes are collapsed to a
    single callout carrying an ``NX`` instance prefix (``2X Ø8.00 / THRU``) and
    the redundant duplicate dimensions are deleted — the ASME convention for a
    repeated feature (their center marks, inserted separately, remain on every
    instance).

    ``thread_map`` maps a hole's nominal diameter **in millimeters** to a thread
    spec (e.g. ``{2.5: "M3X0.5"}``): a tapped hole is modeled at its tap-drill
    diameter, so its callout must read the THREAD, not the drill Ø. A matched
    hole's whole callout is replaced with the spec (``M3X0.5 / THRU``). Matching
    is on the diameter in SYSTEM units (meters, via ``SystemValue``) so it is
    independent of the document's display units. Returns surviving callout count.

    Only pass annotations whose holes really are ``THRU``; for blind features use
    a per-hole ``"<depth> DEEP"`` callout instead.
    """
    # Gather every diameter display-dimension with its diameter in meters.
    diam: list[tuple[Any, Any, float | None]] = []  # (annotation, disp, dia_m)
    for ann in annotations or []:
        ann = _sw_type_info.early_bound_or_flag(
            ann, "IAnnotation", "GetSpecificAnnotation", "Select2"
        )
        disp = adapter._attempt(lambda a=ann: a.GetSpecificAnnotation())
        if not disp:
            continue
        disp = _sw_type_info.early_bound_or_flag(
            disp, "IDisplayDimension", "GetDimension", "SetText"
        )
        # Diameter-ness is a DISPLAY-dimension property (Type2 -> swDimensionType_e),
        # not IDimension.GetType (which reports the parameter type). Using Type2
        # also distinguishes a real Ø8 callout from an incidental 8 mm linear dim.
        if adapter._get_attr_or_call(disp, "Type2") != _SW_DIM_TYPE_DIAMETER:
            continue
        dim = adapter._attempt(lambda d=disp: d.GetDimension())
        dia_m: float | None = None
        if dim:
            dim = _sw_type_info.early_bound_or_flag(dim, "IDimension")
            # SystemValue is meters regardless of document units (unlike Value,
            # which reports the model's display units — inches here).
            raw = adapter._get_attr_or_call(dim, "SystemValue")
            try:
                dia_m = round(float(raw), 6)
            except (TypeError, ValueError):
                dia_m = None
        diam.append((ann, disp, dia_m))

    # Group identical diameters (by meters); an unreadable value groups alone, so
    # it still gets a plain THRU rather than a wrong NX merge.
    groups: dict[Any, list[tuple[Any, Any, float | None]]] = {}
    for idx, item in enumerate(diam):
        key: Any = item[2] if (consolidate and item[2] is not None) else ("solo", idx)
        groups.setdefault(key, []).append(item)

    # thread_map is given in mm; match on rounded meters.
    thread_m = {round(mm / 1000.0, 6): spec for mm, spec in (thread_map or {}).items()}

    count = 0
    for members in groups.values():
        _, keep_disp, dia_m = members[0]
        n = len(members)
        spec = thread_m.get(dia_m) if dia_m is not None else None
        # Set the WHOLE callout text absolutely (idempotent) rather than prepending
        # a prefix (which accumulates — "2X 2X 2X" — if the write runs more than
        # once, e.g. an adapter retry). ``<MOD-DIAM>`` is SolidWorks' Ø tag.
        if spec:
            # Tapped hole: modeled Ø is the tap drill; show the thread instead.
            label = f"{n}X {spec}" if n > 1 else spec
            adapter._attempt(lambda d=keep_disp, s=label: d.SetText(_SW_DIM_TEXT_ALL, s))
        elif n > 1 and dia_m is not None:
            label = f"{n}X <MOD-DIAM>{dia_m * 1000.0:.2f}"
            adapter._attempt(lambda d=keep_disp, s=label: d.SetText(_SW_DIM_TEXT_ALL, s))
        adapter._attempt(lambda d=keep_disp: d.SetText(_SW_DIM_TEXT_BELOW, text))
        count += 1
        for ann, _disp, _v in members[1:]:
            _delete_annotation(adapter, ann)
    return count


def dimension_name(adapter: Any, annotation: Any) -> str:
    """Short parametric name of the model dimension behind a display annotation.

    Returns e.g. ``"TopRun"`` / ``"Bore1Z"`` (``IDimension::Name``), or ``""`` if the
    annotation is not a model dimension. Curation keys on this STABLE per-feature name
    rather than the DISPLAYED value: values like ``6.00`` / ``4.00`` recur across
    unrelated features (chamfer legs, slit floor, hole locators), so a value match
    would delete or move the wrong dimension. (``FullName`` would be
    ``"Name@Feature@Model"``; ``Name`` is just the leading token.)
    """
    disp = adapter._attempt(lambda a=annotation: a.GetSpecificAnnotation())
    if not disp:
        return ""
    disp = _sw_type_info.early_bound_or_flag(disp, "IDisplayDimension", "GetDimension")
    dim = adapter._attempt(lambda d=disp: d.GetDimension())
    if not dim:
        return ""
    dim = _sw_type_info.early_bound_or_flag(dim, "IDimension")
    name = adapter._get_attr_or_call(dim, "Name")
    return name if isinstance(name, str) else ""


def dimension_full_name(adapter: Any, annotation: Any) -> str:
    """Fully-qualified name of the model dimension behind a display annotation.

    Returns e.g. ``"D2@Hole Thread1@pen-v-block.Part"`` (``IDimension::FullName``),
    or ``""`` if the annotation is not a model dimension. Unlike
    :func:`dimension_name` (the leading token only), this carries the FEATURE the
    dimension belongs to — the reliable way to assert that a specific feature's
    callout made it onto the sheet (e.g. a cosmetic-thread ``Hole Thread`` callout,
    whose rendered "#5-40 UNC" text lives in the un-readable calculated-value part).
    """
    disp = adapter._attempt(lambda a=annotation: a.GetSpecificAnnotation())
    if not disp:
        return ""
    disp = _sw_type_info.flagged(disp, "IDisplayDimension")
    dim = adapter._attempt(lambda d=disp: d.GetDimension())
    if not dim:
        return ""
    dim = _sw_type_info.flagged(dim, "IDimension")
    name = adapter._get_attr_or_call(dim, "FullName")
    return name if isinstance(name, str) else ""


def curate_dimensions(
    adapter: Any,
    annotations: list[Any],
    *,
    delete: tuple[str, ...] | frozenset[str] = (),
    reposition: dict[str, tuple[float, float]] | None = None,
) -> list[Any]:
    """Prune / relocate auto-inserted model dimensions by PARAMETRIC NAME.

    ``insert_model_dims(marked_only=False)`` pulls EVERY driven model dim, which
    over-dimensions an ASME print (a redundant intermediate an overall already fixes,
    a duplicated centreline on repeated features). Curate that result:

    - ``delete`` — dim names to remove (e.g. a duplicate hole-centreline, or an
      intermediate run an overall already sets). The feature stays fully defined by
      the survivors; deleting an OVER-constraining dim is an ASME cleanup, not a loss
      of information.
    - ``reposition`` — ``{name: (x, y)}`` sheet positions (meters, sheet origin
      bottom-left, via ``IAnnotation::SetPosition``) to move a crowded dim's text/
      leader clear of its neighbours.

    Matching is on :func:`dimension_name`. Returns the annotations that SURVIVE
    (deleted ones dropped), so a caller can keep threading the curated list.
    """
    delete_set = set(delete)
    moves = reposition or {}
    draw = _draw(adapter)
    survivors: list[Any] = []
    for ann in annotations or []:
        ann = _sw_type_info.early_bound_or_flag(
            ann, "IAnnotation", "GetSpecificAnnotation", "Select2", "SetPosition"
        )
        nm = dimension_name(adapter, ann)
        if nm and nm in delete_set:
            _delete_annotation(adapter, ann)
            continue
        if nm and nm in moves:
            x, y = moves[nm]
            adapter._attempt(
                lambda a=ann, X=x, Y=y: a.SetPosition(float(X), float(Y), 0.0)
            )
        survivors.append(ann)
    adapter._attempt(lambda: draw.EditRebuild3())
    return survivors


def add_overall_dimension(
    adapter: Any, view: Any, *, vertical: bool = True, offset: float = 0.012
) -> Any:
    """Add an explicit overall (bounding) linear dimension across a view's extremes.

    Auto-inserted model dims can leave a direction defined only by an internal chain
    (e.g. side-wall height + chamfer leg) with no single overall figure — ASME wants
    an overall size in each direction. This selects the view's two extreme edges
    (bottom+top for ``vertical``, else left+right; picked by sheet coordinate from the
    view outline) and dimensions across them with ``AddDimension2``, placing the text
    ``offset`` meters outside the view box.

    Best-effort: returns the new dimension, or None if the coordinate-based edge
    selection did not resolve two edges — the direction stays defined by its existing
    chain, so this only ever ADDS an overall, never removes a definition. Activate/
    select happen here; call after the views are placed and dims inserted.
    """
    draw = _draw(adapter)
    box = view_outline(adapter, view)
    if not box:
        return None
    xmin, ymin, xmax, ymax = box
    midx = (xmin + xmax) / 2.0
    midy = (ymin + ymax) / 2.0
    ext = adapter._attempt(lambda: draw.Extension)
    if ext is None:
        return None
    adapter._attempt(lambda: _ddoc(adapter).ActivateView(view_name(adapter, view)))
    adapter._attempt(lambda: draw.ClearSelection2(True))
    if vertical:
        (p0, p1), textpos = ((midx, ymin), (midx, ymax)), (xmin - offset, midy)
    else:
        (p0, p1), textpos = ((xmin, midy), (xmax, midy)), (midx, ymin - offset)
    ok0 = adapter._attempt(
        lambda: ext.SelectByID2("", "EDGE", p0[0], p0[1], 0.0, False, 0, null_callout(), 0),
        default=False,
    )
    ok1 = adapter._attempt(
        lambda: ext.SelectByID2("", "EDGE", p1[0], p1[1], 0.0, True, 0, null_callout(), 0),
        default=False,
    )
    if not (ok0 and ok1):
        logger.warning("overall-dim edge selection failed (bottom=%s top=%s)", ok0, ok1)
        adapter._attempt(lambda: draw.ClearSelection2(True))
        return None
    dim = adapter._attempt(lambda: draw.AddDimension2(textpos[0], textpos[1], 0.0))
    adapter._attempt(lambda: draw.EditRebuild3())
    return dim


def add_third_angle_symbol(
    adapter: Any, cx: float, cy: float, *, size: float = 0.005, layer: str = "PROJECTION"
) -> bool:
    """Draw the ASME/ISO third-angle projection symbol centred near ``(cx, cy)``.

    The symbol is the truncated-cone glyph: two concentric circles (the cone seen
    end-on) beside a trapezoid (the cone seen in profile), with the cone's NARROW
    end pointing TOWARD the circles — the defining feature of THIRD-angle
    projection (first-angle points the narrow end away). ``size`` is the outer
    circle radius (meters); the trapezoid sits to the right of the circles.

    Drawn as sheet sketch geometry on a dedicated solid-black PRINTING layer, so
    the glyph renders crisp (a default sketch layer can export faint/blue); the
    default layer is restored afterward. Draw it while the SHEET is active (e.g.
    right after sheet setup): inserting dimensions leaves a drawing VIEW active,
    and sheet sketch geometry drawn then lands inside that view instead.

    ``cx``/``cy``/``size`` are true SHEET positions/size (meters): sheet sketch
    geometry is authored in SHEET-SCALE space, so the inputs are divided by the
    sheet's scale here to land the glyph where asked regardless of that scale.
    """
    draw = _draw(adapter)
    sm = adapter._attempt(lambda: draw.SketchManager)
    if sm is None:
        logger.warning("no SketchManager; cannot draw projection symbol")
        return False
    # Sheet sketch geometry lands in whatever view is ACTIVE; dimension insertion
    # leaves a drawing view active, so activate the sheet first or the glyph is
    # drawn into (and clipped by) that view instead of onto the sheet.
    scale = 1.0
    sheet = adapter._attempt(lambda: _ddoc(adapter).GetCurrentSheet())
    if sheet:
        sheet = _sw_type_info.early_bound_or_flag(
            sheet, "ISheet", "GetName", "GetProperties"
        )
        sheet_name = adapter._get_attr_or_call(sheet, "GetName")
        if isinstance(sheet_name, str) and sheet_name:
            adapter._attempt(lambda: _ddoc(adapter).ActivateSheet(sheet_name))
        props = adapter._attempt(lambda: sheet.GetProperties())
        if props and not isinstance(props, str):
            vals = list(props)  # [paperSize, template, scale1, scale2, ...]
            if len(vals) >= 4 and vals[3]:
                scale = float(vals[2]) / float(vals[3])
    adapter._attempt(
        lambda: draw.CreateLayer2(
            layer, "ASME projection symbol", _SW_COLOR_BLACK,
            _SW_LINE_SOLID, _SW_LINE_NORMAL, True, True,
        )
    )
    adapter._attempt(lambda: draw.SetCurrentLayer(layer))
    adapter._attempt(lambda: draw.ClearSelection2(True))

    # Sheet sketch space is scaled by the sheet scale; divide to land at true coords.
    cx = float(cx) / scale
    cy = float(cy) / scale
    r = float(size) / scale
    # Concentric circles (cone end view) at (cx, cy).
    adapter._attempt(lambda: sm.CreateCircle(cx, cy, 0.0, cx + r, cy, 0.0))
    adapter._attempt(lambda: sm.CreateCircle(cx, cy, 0.0, cx + r / 2.0, cy, 0.0))
    # Trapezoid (cone side view) to the right: short (narrow) edge nearest the
    # circles, tall (wide) edge far — narrow end points back at the circles.
    lx = cx + r + r * 0.6          # near (narrow) edge x
    rx = lx + 2.0 * r              # far (wide) edge x
    _sheet_line(adapter, sm, lx, cy - r / 2.0, lx, cy + r / 2.0)   # narrow edge
    _sheet_line(adapter, sm, rx, cy - r, rx, cy + r)               # wide edge
    _sheet_line(adapter, sm, lx, cy + r / 2.0, rx, cy + r)         # top slant
    _sheet_line(adapter, sm, lx, cy - r / 2.0, rx, cy - r)         # bottom slant
    # Horizontal axis through both views.
    _sheet_line(adapter, sm, cx - r * 1.4, cy, rx + r * 0.4, cy)
    # Restore the default layer so nothing drawn afterward inherits PROJECTION.
    adapter._attempt(lambda: draw.SetCurrentLayer(""))
    adapter._attempt(lambda: draw.EditRebuild3())
    return True


def auto_center_marks(
    adapter: Any,
    view: Any,
    *,
    holes: bool = True,
    slots: bool = False,
    size: float = 0.0025,
) -> bool:
    """Auto-insert center marks on the circular features in ``view``.

    Uses document defaults off by design so ``size`` (meters) applies. ASME
    requires center marks on cylindrical/bored features; this is the batch path
    (``IView::AutoInsertCenterMarks2``).
    """
    insert_type = 0
    if holes:
        insert_type |= _SW_CM_TYPE_HOLE
    if slots:
        insert_type |= _SW_CM_TYPE_SLOTS
    if insert_type == 0:
        return False
    observer = CENTER_MARK_OBSERVER
    before = _center_mark_count(adapter, view) if observer else None
    ok = adapter._attempt(
        lambda: view.AutoInsertCenterMarks2(
            insert_type,
            _SW_CM_CONN_NONE,
            False,  # LinearSlotCenter
            False,  # ArcSlotCenter
            False,  # UseDocumentDefaults -> honor size below
            float(size),
            0.001,  # Gap
            True,   # ExtendedLines
            True,   # CenterLineFont
            0.0,    # Angle
        ),
        default=False,
    )
    if observer:
        observer(
            {
                "view": adapter._attempt(lambda: view_name(adapter, view), default=""),
                "before": before,
                "after": _center_mark_count(adapter, view),
                "holes": holes,
                "slots": slots,
                "ok": bool(ok),
            }
        )
    return bool(ok)


_REFUSED = object()


def _center_mark_count(adapter: Any, view: Any) -> int | None:
    """The view's centre-mark annotations, or None when the read is refused.

    A view with none answers an empty array or None (no array), so only a
    raised read is a refusal."""
    marks = adapter._attempt(lambda: view.GetAnnotationsByType(_SW_ANNOT_CENTER_MARK), default=_REFUSED)
    if marks is _REFUSED:
        return None
    return len(marks or ())


def add_note(
    adapter: Any,
    text: str,
    x: float,
    y: float,
    *,
    height: float | None = None,
) -> Any:
    """Insert a free note at sheet position ``(x, y)`` (meters) and return it.

    Placement is done by setting the note's annotation position after insertion
    (``InsertNote`` drops it at a default spot). Used for the general-notes
    block and any title-block fallbacks.
    """
    draw = _draw(adapter)
    adapter._attempt(lambda: draw.ClearSelection2(True))
    note = adapter._attempt(lambda: draw.InsertNote(text))
    if not note:
        logger.warning("InsertNote failed for %r", text[:40])
        return None
    note = _sw_type_info.early_bound_or_flag(note, "INote", "GetAnnotation")
    ann = adapter._attempt(lambda: note.GetAnnotation())
    if ann:
        ann = _sw_type_info.early_bound_or_flag(ann, "IAnnotation", "SetPosition")
        ok = adapter._attempt(lambda: ann.SetPosition(float(x), float(y), 0.0), default=False)
        if not ok:
            logger.warning("note SetPosition failed for %r", text[:40])
    else:
        logger.warning("note GetAnnotation returned None for %r", text[:40])
    _ = height  # text sizing left to the sheet/document defaults for now
    return note


def set_annotation_tolerance(
    adapter: Any,
    annotation: Any,
    tol_type: int,
    *,
    min_val: float = 0.0,
    max_val: float = 0.0,
) -> bool:
    """Apply a tolerance type to a dimension annotation.

    ``annotation`` is an ``IAnnotation`` (as returned by ``insert_model_dims``);
    its underlying ``IDisplayDimension``/``IDimension`` receives the tolerance.
    ``TOL_BASIC`` boxes a locating dimension for a true-position frame;
    ``TOL_LIMIT``/``TOL_FIT`` carry ``min_val``/``max_val``.
    """
    disp = adapter._attempt(lambda: annotation.GetSpecificAnnotation())
    dim = adapter._attempt(lambda: disp.GetDimension()) if disp else None
    if dim is None:
        return False
    ok = adapter._attempt(
        lambda: dim.SetToleranceType(int(tol_type)), default=False
    )
    if tol_type in (TOL_LIMIT, TOL_FIT) and (min_val or max_val):
        adapter._attempt(lambda: dim.SetToleranceValues(float(min_val), float(max_val)))
    return bool(ok)


def _sheet_line(adapter: Any, sm: Any, x0: float, y0: float, x1: float, y1: float) -> None:
    adapter._attempt(
        lambda: sm.CreateLine(float(x0), float(y0), 0.0, float(x1), float(y1), 0.0)
    )


def _sheet_rect(adapter: Any, sm: Any, x0: float, y0: float, x1: float, y1: float) -> None:
    _sheet_line(adapter, sm, x0, y0, x1, y0)
    _sheet_line(adapter, sm, x1, y0, x1, y1)
    _sheet_line(adapter, sm, x1, y1, x0, y1)
    _sheet_line(adapter, sm, x0, y1, x0, y0)


def draw_border_and_title_block(
    adapter: Any,
    title_rows: list[str],
    *,
    width: float = 0.2794,
    height: float = 0.2159,
    margin: float = 0.006,
    block_w: float = 0.105,
    row_h: float = 0.010,
) -> bool:
    """Draw a simple ASME-style border rectangle + a bottom-right title block.

    A deliberate alternative to the stock SolidWorks sheet format, which drags in
    an inch tolerance table and ``INSERT COMPANY NAME`` placeholders and collides
    with the view layout. Here the frame is drawn from sheet sketch lines and the
    title block holds exactly ``title_rows`` (top-to-bottom), so the sheet says
    only what this drawing means. All coordinates are meters, sheet origin
    bottom-left.
    """
    draw = _draw(adapter)
    sm = adapter._attempt(lambda: draw.SketchManager)
    if sm is None:
        logger.warning("no SketchManager on drawing; cannot draw border")
        return False
    # Outer border.
    _sheet_rect(adapter, sm, margin, margin, width - margin, height - margin)
    # Title-block box in the bottom-right corner, with one row per title line.
    rows = max(1, len(title_rows))
    x0 = width - margin - block_w
    y0 = margin
    x1 = width - margin
    y1 = margin + rows * row_h
    _sheet_rect(adapter, sm, x0, y0, x1, y1)
    for i in range(1, rows):
        y = y0 + i * row_h
        _sheet_line(adapter, sm, x0, y, x1, y)
    adapter._attempt(lambda: draw.ClearSelection2(True))
    # Text: top row first, so iterate rows from the top down.
    for i, text in enumerate(title_rows):
        y = y1 - (i + 0.5) * row_h
        add_note(adapter, text, x0 + 0.004, y)
    adapter._attempt(lambda: draw.EditRebuild3())
    return True


def delete_all_tables(adapter: Any) -> int:
    """Delete every table annotation on the drawing; return the count removed.

    A stock sheet format ships unused tables (revision / BOM / general / weldment)
    that clutter a single-part print. Tables live per drawing view
    (``IView::GetTableAnnotations``) AND on the sheet node itself, so this scans the
    sheet (``GetFirstView``) plus every real view; each table is removed via its
    ``IAnnotation`` (``ITableAnnotation::GetAnnotation`` -> Select2 + EditDelete).
    Generic — a caller that wants to KEEP the title-block table should strip
    selectively instead (by ``ITableAnnotation::Type``).
    """
    draw = _draw(adapter)
    nodes: list[Any] = []
    sheet_view = adapter._attempt(lambda: _ddoc(adapter).GetFirstView())  # the sheet node
    if sheet_view:
        nodes.append(
            _sw_type_info.early_bound_or_flag(
                sheet_view, "IView", "GetTableAnnotations"
            )
        )
    nodes.extend(iter_views(adapter))
    removed = 0
    for view in nodes:
        tables = adapter._attempt(lambda v=view: v.GetTableAnnotations())
        if not tables or isinstance(tables, str):
            continue
        for tbl in list(tables):
            if not tbl:
                continue
            tbl = _sw_type_info.early_bound_or_flag(
                tbl, "ITableAnnotation", "GetAnnotation"
            )
            ann = adapter._attempt(lambda t=tbl: t.GetAnnotation())
            if ann and _delete_annotation(
                adapter,
                _sw_type_info.early_bound_or_flag(ann, "IAnnotation", "Select2"),
            ):
                removed += 1
    adapter._attempt(lambda: draw.EditRebuild3())
    return removed


def save_as_template(adapter: Any, path: str) -> str:
    """Save the current drawing as a reusable ``.drwdot`` template (SaveAs3 by
    extension). Deletes any stale target, then gates on the file existing (SaveAs3's
    return code is unreliable). Returns the absolute path; raises if nothing landed.
    """
    draw = _draw(adapter)
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    if os.path.exists(path):
        adapter._attempt(lambda p=path: os.remove(p))
    adapter._attempt(lambda p=path: draw.SaveAs3(os.path.abspath(p), 0, 0))
    if not os.path.exists(path):
        raise RuntimeError(f"template SaveAs3 produced no file: {path}")
    return os.path.abspath(path)


def save_drawing(
    adapter: Any,
    slddrw_path: str,
    *,
    pdf_path: str | None = None,
    png_path: str | None = None,
    artifact_context: (
        Callable[[Literal["drawing", "pdf", "png"], str], AbstractContextManager[None]]
        | None
    ) = None,
) -> dict[str, str]:
    """Save the drawing and export sibling PDF/PNG via IModelDocExtension.SaveAs3.

    Delete each stale target, call the bound extension's ``SaveAs3`` once
    (format inferred from the filename extension), then require native success,
    zero errors, and a newly created file. Nonzero native warnings are logged.
    COM and filesystem errors propagate; requested artifacts must all succeed.

    ``artifact_context(kind, absolute_path)`` optionally supplies an observation
    context for each requested output: ``drawing``, ``pdf``, or ``png``. It wraps
    preparation, the save, and the file check, so observers see failures as well
    as elapsed time. Contexts must propagate exceptions. Without a factory,
    saves use ``nullcontext``. Returns the created artifacts' absolute paths.
    """
    draw = _draw(adapter)
    out: dict[str, str] = {}
    artifacts: tuple[tuple[Literal["drawing", "pdf", "png"], str | None], ...] = (
        ("drawing", slddrw_path),
        ("pdf", pdf_path),
        ("png", png_path),
    )
    for key, path in artifacts:
        if not path:
            continue
        path = os.path.abspath(path)
        context = artifact_context(key, path) if artifact_context else nullcontext()
        with context:
            os.makedirs(os.path.dirname(path), exist_ok=True)
            if os.path.exists(path):
                os.remove(path)
            extension = _sw_type_info.early_bound(draw.Extension, "IModelDocExtension")
            result = extension.SaveAs3(path, 0, 1, None, None, 0, 0)
            if (
                type(result) is not tuple
                or len(result) != 3
                or type(result[0]) is not bool
                or type(result[1]) is not int
                or type(result[2]) is not int
            ):
                raise RuntimeError(f"SaveAs3 returned invalid native status for {path}: {result!r}")
            ok, errors, warnings = result
            if warnings:
                logger.warning("SaveAs3 warnings=%s for %s", warnings, path)
            if not ok or errors:
                raise RuntimeError(
                    f"SaveAs3 failed for {path}: success={ok}, errors={errors}, warnings={warnings}"
                )
            if not os.path.isfile(path):
                raise RuntimeError(f"SaveAs3 produced no file: {path}")
            out[key] = path
    return out
