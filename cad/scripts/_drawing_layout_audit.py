"""Live collection for the unified drawing layout audit (``_layout_audit``).

``finalize_drawing`` calls :func:`run_layout_audit` once the PDF is exported,
with the finished document still open. For every sheet it records, WITHOUT
activating the sheet (``IDrawingDoc::GetViews`` returns one row per sheet, led
by the sheet's own view):

* every annotation's rendered primitives (``IAnnotation::GetDisplayData``:
  lines, arcs, arrowheads, polylines, polygons, triangles, text runs with
  their lower-left positions, heights, angles, fonts), its registered leaders,
  and per type: a note's text/extent/balloon flag, a display dimension's
  hole-callout flag and its own ``IDisplayDimension::GetDisplayData``, a datum
  origin's ``GetAxisPoints2`` and labels;
* the Visible/Printable state of each layer those annotations sit on: an
  annotation on a layer that does not print is left out of the audit and
  counted per sheet in the report's summary (``hidden_layer``);
* every view's outline and orientation;
* actual document lineweight metrics/category enums and bounded drawing-component
  default/override readbacks, as evidence only (not model-ink classification);
* section lines (``IDrSection`` line, arrows, label origins, text height) and
  detail circles (``IView::GetDetailCircleInfo2``);
* tables, boxed from anchor + row/column spans (as ``_drawing_common`` does);
* the sheet size, zone margins and title-block keep-out;
* the sheet's page of the exported PDF (``_pdf_ink``): every text object with
  its tight glyph box, and every black stroke with its width and dash. The
  PDF is where text and model edges are measured; COM says what each is.

The dumps are audited by the SolidWorks-free ``_layout_audit.audit_dump`` and
written, with every finding, to the drawing's report
(``_drawing_registry.layout_report_path``), a declared task target that rides
the remote cache: the offline calibration and tests replay exactly what the
building seat saw, whether the leaf was built or restored.
"""

from __future__ import annotations

import json
import math
import time
from pathlib import Path
from typing import Any, Callable, Mapping

import _telemetry
from _common import _early_bound
from _drawing_registry import DRAWING_TEMPLATES, DrawingLayout
from _pdf_ink import PageInk, page_ink, read_pdf_ink
from _layout_audit import (
    DUMP_SCHEMA,
    LAYOUT_AUDIT_MODE,
    LayoutAuditMode,
    audit_report,
    enforced,
    layered_items,
    replace_text,
)

_ANNOT_DIM = 4
_ANNOT_NOTE = 6
_ANNOT_DATUM_ORIGIN = 16
# swAnnotationOwner_e.swAnnotationOwner_DrawingTemplate
_OWNER_DRAWING_TEMPLATE = 2
# swCThread, swCenterLine: GetPosition answered None for every one of them
# on the b49e13940 leaves (cone-swing-platform 14 + 1, top_frame's six
# sheets 98 cosmetic threads). The audit reads their ink from display data;
# only the same-spot duplicate check reads a position, and it skips an
# annotation without one. So a None position is no refusal for these two.
_ANCHORLESS = frozenset({1, 15})
# How far a PDF page may differ from its sheet's GetProperties2 size.
PAGE_SIZE_TOL_M = 0.0005
# swZoneMargin_e
_ZONE_MARGINS = {"top": 0, "bottom": 1, "right": 2, "left": 3}

# Official swLineWeights_e / swLineStyles_e / swDrawingComponentLineFontOption_e.
# These identify actual readbacks; none is a physical-width acceptance threshold.
_LINE_WEIGHTS = {
    -1: "swLW_NONE", 0: "swLW_THIN", 1: "swLW_NORMAL", 2: "swLW_THICK",
    3: "swLW_THICK2", 4: "swLW_THICK3", 5: "swLW_THICK4",
    6: "swLW_THICK5", 7: "swLW_THICK6", 8: "swLW_NUMBER",
    9: "swLW_LAYER", 10: "swLW_CUSTOM",
}
_LINE_STYLES = {
    0: "swLineCONTINUOUS", 1: "swLineHIDDEN", 2: "swLinePHANTOM",
    3: "swLineCHAIN", 4: "swLineCENTER", 5: "swLineSTITCH",
    6: "swLineCHAINTHICK", 7: "swLineDEFAULT",
}
_COMPONENT_LINEFONT_OPTIONS = (
    ("swDrawingComponentLineFontVisible", 1),
    ("swDrawingComponentLineFontHidden", 2),
    ("swDrawingComponentLineFontTangent", 3),
    ("swDrawingComponentLineFontHatch", 4),
    ("swDrawingComponentLineFontSpeedpak", 5),
)

# Official swDrawingViewTypes_e; a readback outside this declaration is unknown.
_DRAWING_VIEW_TYPES = {
    1: "swDrawingSheet", 2: "swDrawingSectionView", 3: "swDrawingDetailView",
    4: "swDrawingProjectedView", 5: "swDrawingAuxiliaryView", 6: "swDrawingStandardView",
    7: "swDrawingNamedView", 8: "swDrawingRelativeView", 9: "swDrawingDetachedView",
    10: "swDrawingAlternatePositionView",
}
_MAX_COMPONENTS_PER_CONTEXT = 512
_MAX_COMPONENT_DEPTH = 32

# swUserPreference* literal IDs read from installed swconst 34.3.0.150,
# SHA256 7F07CA30C4DB22B6D835494D86F5A0D10E8FDEAB9308C9C90132E70C7F4E21B3.
# The official preference enum pages list names, but omit these numeric IDs.
_DOCUMENT_WEIGHT_PREFS = (
    (0, "swPageSetupPrinterThinLineWeight", 48),
    (1, "swPageSetupPrinterNormalLineWeight", 49),
    (2, "swPageSetupPrinterThickLineWeight", 50),
    (3, "swPageSetupPrinterThick2LineWeight", 51),
    (4, "swPageSetupPrinterThick3LineWeight", 52),
    (5, "swPageSetupPrinterThick4LineWeight", 53),
    (6, "swPageSetupPrinterThick5LineWeight", 54),
    (7, "swPageSetupPrinterThick6LineWeight", 55),
)
_DOCUMENT_LINEFONT_PREFS = (
    # category, style preference, weight preference, custom preference
    ("visible_edges", ("swLineFontVisibleEdgesStyle", 54), ("swLineFontVisibleEdgesThickness", 53), ("swLineFontVisibleEdgesThicknessCustom", 89)),
    ("hidden_edges", ("swLineFontHiddenEdgesStyle", 56), ("swLineFontHiddenEdgesThickness", 55), ("swLineFontHiddenEdgesThicknessCustom", 90)),
    ("tangent_edges", ("swLineFontTangentEdgesStyle", 70), ("swLineFontTangentEdgesThickness", 69), ("swLineFontTangentEdgesThicknessCustom", 97)),
    ("cosmetic_threads", ("swLineFontCosmeticThreadStyle", 74), ("swLineFontCosmeticThreadThickness", 73), ("swLineFontCosmeticThreadThicknessCustom", 99)),
    ("hatch", ("swLineFontCrosshatchStyle", 68), ("swLineFontCrosshatchThickness", 67), ("swLineFontCrosshatchThicknessCustom", 96)),
    ("speedpak_edges", ("swLineFontSpeedPakDrawingsModelEdgesStyle", 401), ("swLineFontSpeedPakDrawingsModelEdgesThickness", 400), ("swLineFontSpeedPakDrawingsModelEdgesThicknessCustom", 122)),
    ("section_cutting_lines", ("swLineFontSectionLineStyle", 62), ("swLineFontSectionLineThickness", 61), ("swLineFontSectionLineThicknessCustom", 93)),
    ("emphasized_section_outline", ("swLineFontEmphasizedSectionOutlineStyle", 557), ("swLineFontEmphasizedSectionThickness", 558), ("swLineFontEmphasizedSectionThicknessCustom", 205)),
)
_DIMENSION_LINEFONT_SCOPES = (
    # scope, actual option ID, documented extension-line preference pairing
    ("swDetailingAngleDimension", 201, True),
    ("swDetailingArcLengthDimension", 202, True),
    ("swDetailingChamferDimension", 203, False),
    ("swDetailingDiameterDimension", 204, True),
    ("swDetailingHoleDimension", 205, False),
    ("swDetailingLinearDimension", 206, True),
    ("swDetailingOrdinateDimension", 207, True),
    ("swDetailingRadiusDimension", 208, False),
    ("swDetailingAngularRunningDimension", 209, True),
)
_EXTENSION_LINEFONT_PREFS = (
    ("swDimensionsExtensionLineStyle", 516),
    ("swDimensionsExtensionLineStyleThickness", 517),
    ("swDimensionsExtensionLineStyleThicknessCustom", 188),
)
_EXTENSION_SAME_AS_LEADER_PREF = ("swDimensionsExtensionLineStyleSameAsLeader", 551)
_NOTE_LINEFONT_PREFS = (
    ("swDetailingNoteLeaderLineStyle", 356),
    ("swDetailingNoteLeaderLineThickness", 357),
    ("swDetailingNoteLeaderLineThicknessCustom", 110),
)

_DISPLAY_PRIMITIVES = (
    ("lines", "GetLineCount", ("GetLineAtIndex3", "GetLineAtIndex2")),
    ("arcs", "GetArcCount", ("GetArcAtIndex2",)),
    ("arrows", "GetArrowHeadCount", ("GetArrowHeadAtIndex2",)),
    ("polylines", "GetPolyLineCount", ("GetPolylineAtIndex2",)),
    ("polygons", "GetPolygonCount", ("GetPolygonAtIndex",)),
    ("triangles", "GetTriangleCount", ("GetTriangleAtIndex",)),
    ("ellipses", "GetEllipseCount", ("GetEllipseAtIndex2",)),
)


def _round(values: Any) -> list[float]:
    """Floats rounded to 0.1 um -- far below ink, and a third of the JSON."""
    return [round(float(value), 7) for value in (values or ())]


class _Reader:
    """Tolerant COM reads: an accessor that does not apply returns ``default``.

    Every getter whose answer the audit consumes is ``need``: a scalar, count
    or geometry read answering None is a refusal. ``call`` is left only where
    None is the documented empty answer (``GetAnnotations``,
    ``GetSectionLines``, ``GetTableAnnotations``, ``GetDetailCircleInfo2``,
    ``GetSplitInformation`` on an unsplit table), where the value is not
    consumed by the audit (font, line spacing, scale, display mode,
    datum-origin axes and labels), where the default is the conservative
    answer (an annotation's layer name, or a layer ``GetLayer`` cannot
    resolve: its annotations are audited as printed), where SolidWorks
    answers None for a whole kind (``GetPosition`` of a cosmetic thread or
    a centerline, ``_ANCHORLESS``), or where a fallback
    read follows (``GetName2`` before ``Name``).

    Every refusal is counted per sheet under the accessor's name. A refused
    read can drop an annotation's ink or text from the audit, so any count is
    a gating ``com-read-errors`` finding. A read the audit cannot do without
    (``need``) also counts a ``None`` answer: SolidWorks often fails that way
    instead of raising.
    """

    def __init__(self, adapter: Any) -> None:
        self.adapter = adapter
        self.errors: dict[str, int] = {}
        # accessor -> [calls, seconds] over the whole collection: the one
        # attribution of layout.collect_com's time (8 s a sheet, 1.4 h a day
        # on 2026-09-27) to the reads that spend it.
        self.cost: dict[str, list[float]] = {}
        self.owners: dict[str, list[float]] = {}

    def _count(self, name: str) -> None:
        self.errors[name] = self.errors.get(name, 0) + 1

    def _spent(self, name: str, started: float) -> None:
        entry = self.cost.get(name)
        if entry is None:
            entry = self.cost[name] = [0, 0.0]
        entry[0] += 1
        entry[1] += time.perf_counter() - started

    def call(self, fn: Callable[[], Any], default: Any = None, *, name: str = "", required: bool = False) -> Any:
        name = name or _accessor(fn)
        started = time.perf_counter()
        try:
            value = fn()
        except Exception:
            self._spent(name, started)
            self._count(name)
            return default
        self._spent(name, started)
        if value is None and required:
            self._count(name)
        return default if value is None else value

    def need(self, fn: Callable[[], Any], default: Any = None, *, name: str = "") -> Any:
        """``call`` for a read whose ``None`` loses ink or text."""
        return self.call(fn, default, name=name, required=True)

    def optional(self, fn: Callable[[], Any]) -> Any:
        """A read whose refusal loses nothing (the audit falls back), so it is
        never counted as a ``com-read-errors`` refusal."""
        started = time.perf_counter()
        try:
            return fn()
        except Exception:
            return None
        finally:
            self._spent(_accessor(fn), started)

    def witness(
        self, fn: Callable[[], Any], *, name: str, allow_none: bool = False,
    ) -> tuple[Any, str | None]:
        """Evidence-only read: preserve a refusal's cause without changing gates.

        Unlike ``need``, these new diagnostics do not supply ink or geometry to
        the classifier. Their cost joins the existing collector aggregation;
        unreadability is serialized beside the evidence, not as a new finding.
        ``allow_none`` is only for a getter whose successful null is meaningful,
        such as a view with no base; it does not turn an exception into null.
        """
        started = time.perf_counter()
        try:
            value = fn()
        except Exception as exc:
            cause = f"exception:{type(exc).__name__}"
            hresult = getattr(exc, "hresult", None)
            if type(hresult) is int:
                cause += f":hresult={hresult}"
            return None, cause
        finally:
            self._spent(name, started)
        return (None, "missing") if value is None and not allow_none else (value, None)

    def first(self, fns: list[Callable[[], Any]], *, name: str) -> Any:
        """The first of some ARRAY-returning overloads that answers (a scalar 0
        or False would read as empty: never route a scalar getter here); one
        refusal counted only when all do
        (``GetLineAtIndex3`` refusing before ``GetLineAtIndex2`` answers is the
        expected path, not a lost primitive). An empty answer falls through to
        the next overload, but is returned, uncounted, when none answers with
        data; only raising or None from every overload is a refusal."""
        empty = None
        for position, fn in enumerate(fns):
            # Cost per overload position: ``name#0`` refusing on every row
            # is a fallback paid once per primitive.
            started = time.perf_counter()
            try:
                value = fn()
            except Exception:
                self._spent(f"{name}#{position}", started)
                continue
            self._spent(f"{name}#{position}", started)
            if value:
                return value
            if value is not None and empty is None:
                empty = value
        if empty is None:
            self._count(name)
        return empty

    def bind(self, obj: Any, interface: str) -> Any:
        if obj is None:
            return None
        started = time.perf_counter()
        try:
            return _early_bound(obj, interface)
        except Exception:
            self._count(f"bind {interface}")
            return None
        finally:
            self._spent(f"bind {interface}", started)

    def dumped(self, owner: str, started: float) -> None:
        """One whole annotation dump, attributed to its ``swAnnotationOwner_e``
        (0 view, 1 sheet, 2 template)."""
        entry = self.owners.get(owner)
        if entry is None:
            entry = self.owners[owner] = [0, 0.0]
        entry[0] += 1
        entry[1] += time.perf_counter() - started

    def cost_attributes(self, top: int = 12) -> dict[str, float]:
        """The ``top`` costliest accessors as span attributes, plus totals
        and the per-owner annotation dump cost."""
        ranked = sorted(self.cost.items(), key=lambda item: item[1][1], reverse=True)
        attributes: dict[str, float] = {
            "com.calls": int(sum(calls for calls, _ in self.cost.values())),
            "com.s": round(sum(seconds for _, seconds in self.cost.values()), 3),
        }
        for owner, (count, seconds) in sorted(self.owners.items()):
            attributes[f"annotations.{owner}.n"] = int(count)
            attributes[f"annotations.{owner}.s"] = round(seconds, 3)
        for name, (calls, seconds) in ranked[:top]:
            key = name.replace(" ", "_")
            attributes[f"com.{key}.calls"] = int(calls)
            attributes[f"com.{key}.s"] = round(seconds, 3)
        return attributes

    def take_errors(self) -> dict[str, int]:
        errors, self.errors = self.errors, {}
        return dict(sorted(errors.items()))


def _accessor(fn: Callable[[], Any]) -> str:
    return fn.__code__.co_names[-1] if fn.__code__.co_names else "?"


def _unreadable(source: str, cause: str) -> dict[str, Any]:
    return {"status": "unreadable", "source": source, "cause": cause}


def _witness_value(
    reader: _Reader, fn: Callable[[], Any], *, source: str, kind: str,
    enum: Mapping[int, str] | None = None,
) -> dict[str, Any]:
    """Serialize only a validated native scalar, never a COM object's repr."""
    value, cause = reader.witness(fn, name=source.split("(")[0])
    if cause is not None:
        return _unreadable(source, cause)
    return _witness_scalar(value, source=source, kind=kind, enum=enum)


def _witness_scalar(
    value: Any, *, source: str, kind: str, enum: Mapping[int, str] | None = None,
) -> dict[str, Any]:
    """Validate already-read tuple slots without inventing extra COM calls."""
    valid = False
    if kind == "integer":
        valid = type(value) is int and -(2**31) <= value < 2**31
    elif kind == "count":
        valid = type(value) is int and 0 <= value < 2**31
    elif kind == "bool":
        valid = type(value) is bool
    elif kind == "text":
        valid = type(value) is str and len(value) <= 1024
    elif kind == "m":
        valid = type(value) is float and math.isfinite(value) and value > 0
    if not valid:
        return _unreadable(source, f"invalid-{kind}:{type(value).__name__}")
    result: dict[str, Any] = {"status": "read", "source": source, "value": value}
    if kind == "m":
        result["unit"] = "m"
    if enum is not None:
        result["enum"] = enum.get(value)
        if result["enum"] is None:
            result.update(status="unreadable", cause="unknown-enum")
        elif enum is _LINE_WEIGHTS and value in (-1, 8, 9):
            result.update(status="unreadable", cause="unresolved-nonmetric-weight-enum")
        elif enum is _LINE_STYLES and value == 7:
            result.update(status="unreadable", cause="unresolved-default-style-enum")
    return result


def _witness_bind(
    reader: _Reader, fn: Callable[[], Any], interface: str, source: str, *,
    allow_none: bool = False,
) -> tuple[Any, str | None]:
    raw, cause = reader.witness(fn, name=source, allow_none=allow_none)
    if cause is not None or raw is None:
        return None, cause
    bound, cause = reader.witness(lambda: _early_bound(raw, interface), name=f"bind {interface}")
    return bound, f"bind {interface}:{cause}" if cause is not None else None


def _preference_witness(
    reader: _Reader, extension: Any, method: str, pref: tuple[str, int],
    scope: tuple[str, int], *, kind: str, enum: Mapping[int, str] | None = None,
) -> dict[str, Any]:
    source = f"IModelDocExtension.{method}({pref[0]}={pref[1]},{scope[0]}={scope[1]})"
    return _witness_value(
        reader, lambda: getattr(extension, method)(pref[1], scope[1]),
        source=source, kind=kind, enum=enum,
    )


def _document_linefont(
    reader: _Reader, extension: Any, style: tuple[str, int], weight: tuple[str, int],
    custom: tuple[str, int], scope: tuple[str, int],
) -> dict[str, Any]:
    result = {
        "scope": {"enum": scope[0], "value": scope[1]},
        "style": _preference_witness(reader, extension, "GetUserPreferenceInteger", style, scope, kind="integer", enum=_LINE_STYLES),
        "weight": _preference_witness(reader, extension, "GetUserPreferenceInteger", weight, scope, kind="integer", enum=_LINE_WEIGHTS),
        "authority": "selected-document-category; not individual annotation or PDF ownership",
    }
    custom_source = f"IModelDocExtension.GetUserPreferenceDouble({custom[0]}={custom[1]},{scope[0]}={scope[1]})"
    if result["weight"]["status"] != "read":
        result["custom_thickness"] = _unreadable(custom_source, "weight-unreadable; custom-getter-not-invoked")
    elif result["weight"]["value"] == 10:
        result["custom_thickness"] = _preference_witness(reader, extension, "GetUserPreferenceDouble", custom, scope, kind="m")
    else:
        result["custom_thickness"] = {"status": "inactive", "source": custom_source, "cause": "not-custom"}
    return result


def _document_lineweights(reader: _Reader) -> dict[str, Any]:
    """Snapshot document values once; never substitute template or seat defaults."""
    source = "IModelDoc2.Extension"
    model, cause = _witness_bind(reader, lambda: reader.adapter.currentModel, "IModelDoc2", "adapter.currentModel")
    if cause is not None:
        return {"schema": 1, **_unreadable(source, cause)}
    extension, cause = _witness_bind(reader, lambda: model.Extension, "IModelDocExtension", source)
    if cause is not None:
        return {"schema": 1, **_unreadable(source, cause)}
    scope = ("swDetailingNoOptionSpecified", 0)
    metrics = {}
    for weight, pref_name, pref in _DOCUMENT_WEIGHT_PREFS:
        metric = _preference_witness(reader, extension, "GetUserPreferenceDouble", (pref_name, pref), scope, kind="m")
        metric["weight"] = {"enum": _LINE_WEIGHTS[weight], "value": weight}
        metrics[_LINE_WEIGHTS[weight]] = metric
    categories = {
        name: _document_linefont(reader, extension, style, weight, custom, scope)
        for name, style, weight, custom in _DOCUMENT_LINEFONT_PREFS
    }
    dimensions = {}
    for scope_name, option, has_extension in _DIMENSION_LINEFONT_SCOPES:
        scoped = (scope_name, option)
        dimension = {
            "leader": _document_linefont(
                reader, extension, ("swLineFontDimensionsStyle", 64),
                ("swLineFontDimensionsThickness", 63), ("swLineFontDimensionsThicknessCustom", 94), scoped,
            ),
        }
        if has_extension:
            dimension["extension"] = _document_linefont(reader, extension, *_EXTENSION_LINEFONT_PREFS, scoped)
            dimension["extension_same_as_leader"] = _preference_witness(
                reader, extension, "GetUserPreferenceToggle", _EXTENSION_SAME_AS_LEADER_PREF, scoped, kind="bool",
            )
        else:
            dimension["extension"] = {
                "status": "unreadable", "cause": "not-captured; extension-linefont-pairing-not-documented-for-scope",
            }
        dimensions[scope_name] = dimension
    categories["note_leaders"] = _document_linefont(reader, extension, *_NOTE_LINEFONT_PREFS, scope)
    result = {
        "schema": 1, "status": "read", "source": source,
        "metrics": metrics, "categories": categories, "dimensions": dimensions,
        "coverage": "named selected document categories/scopes only; consult per-view components and annotation display evidence",
    }
    if _has_unreadable(result):
        result["status"] = "unreadable"
    return result


def _component_lineweights(reader: _Reader, view: Any) -> dict[str, Any]:
    """Keep two native root contexts and the immediate base distinct."""
    result: dict[str, Any] = {
        "schema": 2, "status": "read",
        "max_components_per_view": 2 * _MAX_COMPONENTS_PER_CONTEXT,
        "contexts": {
            "current": _component_tree_lineweights(reader, view, in_child_context=False),
            "child": _component_tree_lineweights(reader, view, in_child_context=True),
        },
        "base_view": _base_view_description(reader, view),
        "coverage": "separate getter contexts and immediate base only; no effective width or PDF/model ownership proof",
    }
    if _has_unreadable(result):
        result["status"] = "unreadable"
    return result


def _base_view_description(reader: _Reader, view: Any) -> dict[str, Any]:
    """Describe only the immediate base; its native name need not be unique."""
    source = "IView.GetBaseView()"
    base, cause = _witness_bind(reader, lambda: view.GetBaseView(), "IView", source, allow_none=True)
    if cause is not None:
        return _unreadable(source, cause)
    if base is None:
        return {"status": "read", "source": source, "value": None}
    name = _witness_value(reader, lambda: base.GetName2(), source="IView.GetName2()", kind="text")
    if name["status"] == "read" and not name["value"]:
        name.update(status="unreadable", cause="empty-view-name")
    result = {
        "status": "read", "source": source, "name": name,
        "type": _witness_value(reader, lambda: base.Type, source="IView.Type", kind="integer", enum=_DRAWING_VIEW_TYPES),
        "coverage": "immediate returned base description; section names are not unique; no view/override identity proof",
    }
    if _has_unreadable(result):
        result["status"] = "unreadable"
    return result


def _component_tree_lineweights(
    reader: _Reader, view: Any, *, in_child_context: bool,
) -> dict[str, Any]:
    """Read one bounded getter-returned tree; never merge equal native names."""
    source = f"IView.RootDrawingComponent2(InChildContext={in_child_context})"
    root, cause = _witness_bind(
        reader, lambda: view.RootDrawingComponent2(in_child_context), "IDrawingComponent", source,
    )
    result: dict[str, Any] = {
        "status": "read", "source": source, "in_child_context": in_child_context,
        "max_components": _MAX_COMPONENTS_PER_CONTEXT, "max_depth": _MAX_COMPONENT_DEPTH, "components": [],
        "coverage": (
            "section temporary context requested; nonsection parent-view semantics; not exhaustive current-view override proof"
            if in_child_context else
            "current-view context requested by existing source convention; not effective width or PDF/model ownership proof"
        ),
    }
    if cause is not None:
        result.update(status="unreadable", cause=cause)
        return result
    # Index paths preserve distinct instances even when their names coincide.
    pending = [(root, [])]
    records = result["components"]
    while pending:
        component, path = pending.pop()
        record: dict[str, Any] = {
            "path": path,
            "name": _witness_value(reader, lambda: component.Name, source="IDrawingComponent.Name", kind="text"),
            "use_document_defaults": _witness_value(
                reader, lambda: component.UseDocumentDefaults,
                source="IDrawingComponent.UseDocumentDefaults", kind="bool",
            ),
        }
        records.append(record)
        defaults = record["use_document_defaults"]
        if defaults.get("value") is True:
            record["line_fonts"] = {"status": "inactive", "cause": "use-document-defaults"}
        else:
            record["line_fonts"] = {
                name: _component_linefont(reader, component, name, option)
                for name, option in _COMPONENT_LINEFONT_OPTIONS
            }
        count = _witness_value(
            reader, lambda: component.GetChildrenCount(), source="IDrawingComponent.GetChildrenCount()", kind="count",
        )
        record["children"] = count
        if count["status"] != "read":
            result["status"] = "unreadable"
            continue
        remaining = result["max_components"] - len(records) - len(pending)
        if count["value"] > remaining or (count["value"] and len(path) >= result["max_depth"]):
            record["children"] = {
                **count, "status": "unreadable",
                "cause": "component-limit" if count["value"] > remaining else "depth-limit",
            }
            result["status"] = "unreadable"
            continue
        if not count["value"]:
            continue
        children, cause = reader.witness(lambda: component.GetChildren(), name="IDrawingComponent.GetChildren")
        if cause is None and type(children) not in (tuple, list):
            cause = f"invalid-array:{type(children).__name__}"
        if cause is None and len(children) != count["value"]:
            cause = "child-count-mismatch"
        if cause is not None:
            record["children"] = _unreadable("IDrawingComponent.GetChildren()", cause)
            result["status"] = "unreadable"
            continue
        for index in range(len(children) - 1, -1, -1):
            child, cause = _witness_bind(
                reader, lambda i=index: children[i], "IDrawingComponent", "IDrawingComponent.GetChildren[]",
            )
            if cause is not None:
                record["children"].update(status="unreadable", cause=f"child-{index}:{cause}")
                result["status"] = "unreadable"
            else:
                pending.append((child, [*path, index]))
    if any(_has_unreadable(record) for record in records):
        result["status"] = "unreadable"
    return result


def _has_unreadable(value: Any) -> bool:
    if type(value) is dict:
        return value.get("status") == "unreadable" or any(_has_unreadable(item) for item in value.values())
    if type(value) is list:
        return any(_has_unreadable(item) for item in value)
    return False


def _component_linefont(reader: _Reader, component: Any, name: str, option: int) -> dict[str, Any]:
    args = f"{name}={option}"
    source = f"IDrawingComponent.GetLineThickness({args})"
    pair, cause = reader.witness(lambda: component.GetLineThickness(option), name="IDrawingComponent.GetLineThickness")
    # gen_py returns (VT_I4 retval, VT_BYREF|VT_R8 out Thickness), not metres alone.
    if cause is None and (type(pair) not in (tuple, list) or len(pair) != 2):
        cause = "invalid-retval-out-thickness-pair"
    if cause is not None:
        weight = _unreadable(source, cause)
        thickness = _unreadable(source, cause)
    else:
        weight = _witness_scalar(pair[0], source=source, kind="integer", enum=_LINE_WEIGHTS)
        if weight.get("value") == 10:
            thickness = _witness_scalar(pair[1], source=source, kind="m")
        else:
            # The out double has authority only for swLW_CUSTOM. Preserve a
            # finite scalar as raw readback, without treating it as a width.
            thickness = {"status": "inactive", "source": source, "cause": "not-custom"}
            if type(pair[1]) is float and math.isfinite(pair[1]):
                thickness.update(value=pair[1], unit="m")
            else:
                thickness = _unreadable(source, f"invalid-out-thickness:{type(pair[1]).__name__}")
    return {
        "option": {"enum": name, "value": option},
        "style": _witness_value(
            reader, lambda: component.GetLineStyle(option),
            source=f"IDrawingComponent.GetLineStyle({args})", kind="integer", enum=_LINE_STYLES,
        ),
        "weight": weight, "custom_thickness": thickness,
        "authority": "selected-component-settings; consult-use_document_defaults",
    }


def _lineweight_error(evidence: dict[str, Any], cause: str) -> None:
    evidence["status"] = "unreadable"
    errors = evidence["read_errors"]
    errors[cause] = errors.get(cause, 0) + 1


def _display_read(data: Any, getter: str, args: tuple[int, ...], evidence: dict[str, Any]) -> Any:
    """Observe the existing display read; no additional native calls or fallback."""
    try:
        raw = getattr(data, getter)(*args)
    except Exception as exc:
        _lineweight_error(evidence, f"{getter}:exception:{type(exc).__name__}")
        raise
    if getter == "GetLineCount":
        if type(raw) is not int or raw < 0:
            _lineweight_error(evidence, f"{getter}:invalid-count")
        return raw
    if not raw:
        _lineweight_error(evidence, f"{getter}:missing-or-empty")
        return raw
    if getter == "GetLineAtIndex2":
        _lineweight_error(evidence, "GetLineAtIndex2:unused-style-weight-slots")
        return raw
    if type(raw) not in (tuple, list) or len(raw) != 10:
        _lineweight_error(evidence, "GetLineAtIndex3:invalid-ten-double-row")
        return raw
    values = raw[2:4]
    if any(
        not (
            type(value) is int and -(2**31) <= value < 2**31
            or type(value) is float and math.isfinite(value) and value.is_integer() and -(2**31) <= value < 2**31
        )
        for value in values
    ):
        _lineweight_error(evidence, "GetLineAtIndex3:nonintegral-style-weight")
        return raw
    style, weight = (int(value) for value in values)
    key = f"{style}:{weight}"
    bins = evidence["bins"]
    if key not in bins:
        if len(bins) >= 128:
            _lineweight_error(evidence, "annotation-bin-limit")
            return raw
        bins[key] = {
            "style": _witness_scalar(style, source="IDisplayData.GetLineAtIndex3[2]", kind="integer", enum=_LINE_STYLES),
            "weight": _witness_scalar(weight, source="IDisplayData.GetLineAtIndex3[3]", kind="integer", enum=_LINE_WEIGHTS),
            "count": 0,
        }
    bins[key]["count"] += 1
    if _has_unreadable(bins[key]):
        evidence["status"] = "unreadable"
    return raw


def _dump_display(reader: _Reader, data: Any) -> dict[str, Any]:
    data = reader.bind(data, "IDisplayData")
    if data is None:
        return {}
    out: dict[str, Any] = {}
    lineweights: dict[str, Any] = {
        "status": "read", "source": "IDisplayData.GetLineAtIndex3",
        "bins": {}, "read_errors": {}, "max_bins": 128,
        "coverage": "rendered-annotation-lines; not PDF stroke ownership",
    }
    # A count is required like the rows it guards: a getter answering None
    # instead of raising would otherwise read as zero primitives, and their
    # ink would drop out of the audit with com-read-errors still clean.
    for key, count_name, getters in _DISPLAY_PRIMITIVES:
        count = int(reader.need(
            lambda c=count_name: _display_read(data, c, (), lineweights) if c == "GetLineCount" else getattr(data, c)(),
            0, name=count_name,
        ) or 0)
        rows = []
        for index in range(count):
            raw = reader.first(
                [
                    lambda g=getter, i=index: _display_read(data, g, (i,), lineweights)
                    if g.startswith("GetLineAtIndex") else getattr(data, g)(i)
                    for getter in getters
                ], name="/".join(getters)
            )
            if raw:
                rows.append(_round(raw))
        if rows:
            out[key] = rows
    lineweights["bins"] = list(lineweights["bins"].values())
    texts = []
    for index in range(int(reader.need(lambda: data.GetTextCount(), 0) or 0)):
        texts.append(
            {
                "t": str(reader.need(lambda i=index: data.GetTextAtIndex(i), "")),
                "pos": _round(reader.need(lambda i=index: data.GetTextPositionAtIndex(i), ())),
                "h": round(float(reader.need(lambda i=index: data.GetTextHeightAtIndex(i), 0.0)), 7),
                "ref": int(reader.need(lambda i=index: data.GetTextRefPositionAtIndex(i), -1)),
                "ang": round(float(reader.need(lambda i=index: data.GetTextAngleAtIndex(i), 0.0)), 7),
                "font": str(reader.call(lambda i=index: data.GetTextFontAtIndex(i), "")),
                "ls": round(float(reader.call(lambda i=index: data.GetTextLineSpacingAtIndex(i), 0.0)), 7),
            }
        )
        # The run's own width (MHA-DT-019, gdtdiag2: "BOTH CROWNS" 34.1 mm, as
        # printed). Its GetTextInBoxHeightAtIndex twin read 0.0 there, so the
        # height stays GetTextHeightAtIndex.
        width = reader.optional(lambda i=index: data.GetTextInBoxWidthAtIndex(i))
        if width:
            texts[-1]["w"] = round(float(width), 7)
    if texts:
        out["texts"] = texts
    # annotation_display callers truth-test this dict before using display_box;
    # diagnostics alone must not turn an absent display into rendered data.
    if out:
        out["lineweight_evidence"] = lineweights
    return out


def annotation_display(adapter: Any, annotation: Any) -> tuple[dict[str, Any], dict[str, int]]:
    """One annotation's ``IAnnotation::GetDisplayData`` in the dump shape the
    audit reads, with every read SolidWorks refused (accessor -> count)."""
    reader = _Reader(adapter)
    bound = reader.bind(annotation, "IAnnotation")
    if bound is None:
        return {}, reader.take_errors()
    display = _dump_display(reader, reader.need(lambda: bound.GetDisplayData()))
    return display, reader.take_errors()


def _dump_annotation(reader: _Reader, raw: Any) -> dict[str, Any] | None:
    started = time.perf_counter()
    annotation = reader.bind(raw, "IAnnotation")
    if annotation is None:
        return None
    owner_type = int(reader.need(lambda: annotation.OwnerType, -1))
    if owner_type == _OWNER_DRAWING_TEMPLATE:
        # The title block's and sheet format's own notes, which the sheet
        # view's GetAnnotations returns beside the drawing's (~40 a B sheet).
        # No check reads anything of them but their owner (``sheet_owned``
        # drops them everywhere), so nothing else is read: in full they were
        # ~66% of the collector's COM reads, at ~2.8 ms a read. Replaying the
        # 147 sheets of the 111 cached drawing reports of 2026-09-27 with
        # them reduced to this record changes no finding, summary or advance.
        reader.dumped(f"owner{owner_type}", started)
        return {"owner_type": owner_type, "display": {}}
    kind = int(reader.need(lambda: annotation.GetType(), 0))
    record: dict[str, Any] = {
        "type": kind,
        "name": str(reader.need(lambda: annotation.GetName(), "")),
        "visible": int(reader.need(lambda: annotation.Visible, 1)),
        "owner_type": owner_type,
        "pos": _round((reader.call if kind in _ANCHORLESS else reader.need)(lambda: annotation.GetPosition(), ())),
        "layer": str(reader.call(lambda: annotation.Layer, "")),
    }
    leaders = []
    for index in range(int(reader.need(lambda: annotation.GetLeaderCount(), 0) or 0)):
        points = reader.need(lambda i=index: annotation.GetLeaderPointsAtIndex(i))
        if points:
            leaders.append(_round(points))
    if leaders:
        record["leaders"] = leaders
    record["display"] = _dump_display(reader, reader.need(lambda: annotation.GetDisplayData()))
    if not record["display"]:
        record["lineweight_evidence"] = _unreadable("IAnnotation.GetDisplayData", "no-rendered-display")
    specific = (
        reader.need(lambda: annotation.GetSpecificAnnotation())
        if kind in (_ANNOT_NOTE, _ANNOT_DIM, _ANNOT_DATUM_ORIGIN)
        else None
    )
    if kind == _ANNOT_NOTE:
        note = reader.bind(specific, "INote")
        if note is not None:
            record["note"] = {
                "text": str(reader.need(lambda: note.GetText(), "")),
                "extent": _round(reader.need(lambda: note.GetExtent(), ())),
                "balloon": bool(reader.need(lambda: note.IsBomBalloon(), False)),
            }
    elif kind == _ANNOT_DIM:
        display = reader.bind(specific, "IDisplayDimension")
        if display is not None:
            # IDisplayDimension::GetDisplayData is not read: on the d09c2b9eb
            # calibration leaves it equalled IAnnotation's for all 72 dimensions.
            record["dim"] = {"hole_callout": bool(reader.need(lambda: display.IsHoleCallout(), False))}
    elif kind == _ANNOT_DATUM_ORIGIN:
        origin = reader.bind(specific, "IDatumOrigin")
        if origin is not None:
            record["datum_origin"] = {
                "axis": _round(reader.call(lambda: origin.GetAxisPoints2(), ())),
                "x_label": str(reader.call(lambda: origin.XLabel, "")),
                "y_label": str(reader.call(lambda: origin.YLabel, "")),
            }
    reader.dumped(f"owner{record['owner_type']}", started)
    return record


def _layer_states(reader: _Reader, dump: Mapping[str, Any]) -> dict[str, dict[str, bool]]:
    """``ILayer`` Visible/Printable of each named layer the sheet's
    annotations and tables sit on (``layered_items``, so a dumped item's
    layer can't go unread). An annotation on a hidden or non-printing layer
    reads ``Visible`` 1 through COM but prints nothing (cone-swing-platform's
    profile thread callout on COSMETIC-THREADS-HIDDEN, 24cbab237), so the
    audit needs the layer to know what printed. A name ``GetLayer`` does not
    resolve is left out, and its annotations are audited as printed."""
    names = sorted({str(item.get("layer") or "") for item in layered_items(dump)} - {""})
    if not names:
        return {}
    manager = reader.bind(reader.need(lambda: reader.adapter.currentModel.GetLayerManager()), "ILayerMgr")
    if manager is None:
        return {}
    states = {}
    for name in names:
        layer = reader.bind(reader.call(lambda n=name: manager.GetLayer(n)), "ILayer")
        if layer is None:
            continue
        states[name] = {
            "visible": bool(reader.need(lambda: layer.Visible, True)),
            "printable": bool(reader.need(lambda: layer.Printable, True)),
        }
    return states


def _table_record(reader: _Reader, raw: Any) -> dict[str, Any] | None:
    """A table's box: top-left anchor, then visible rows down and columns right."""
    table = reader.bind(raw, "ITableAnnotation")
    if table is None:
        return None
    inner = reader.bind(reader.need(lambda: table.GetAnnotation()), "IAnnotation")
    if inner is None:
        return None
    position = _round(reader.need(lambda: inner.GetPosition(), ()))
    if len(position) < 2:
        return None
    rows = int(reader.need(lambda: table.RowCount, 0) or 0)
    columns = int(reader.need(lambda: table.ColumnCount, 0) or 0)
    row_indices = list(range(rows))
    split = reader.call(lambda: table.GetSplitInformation(0, 0, 0, 0))
    if split and len(split) >= 5 and int(split[0]) == 1:
        _direction, _index, count, first, last = (int(value) for value in split[:5])
        if count > 1 and 0 <= first <= last < rows:
            row_indices = list(range(first, last + 1))
            if first > 0:
                row_indices.insert(0, 0)
    width = sum(float(reader.need(lambda i=i: table.GetColumnWidth(i), 0.0)) for i in range(columns))
    height = sum(float(reader.need(lambda i=i: table.GetRowHeight(i), 0.0)) for i in row_indices)
    x, y = position[0], position[1]
    return {
        "name": str(reader.need(lambda: inner.GetName(), "table")),
        "box": _round((x, y - height, x + width, y)),
        "layer": str(reader.call(lambda: inner.Layer, "")),
    }


def _dump_view(
    reader: _Reader, view: Any, *, is_pictorial: Callable[[str], bool]
) -> dict[str, Any]:
    view = reader.bind(view, "IView")
    orientation = str(reader.need(lambda: view.GetOrientationName(), ""))
    record: dict[str, Any] = {
        "name": str(reader.need(lambda: view.GetName2(), "")),
        "type": int(reader.need(lambda: view.Type, -1)),
        "orientation": orientation,
        "pictorial": bool(is_pictorial(orientation)),
        "outline": _round(reader.need(lambda: view.GetOutline(), ())),
        "scale": _round(reader.call(lambda: view.ScaleRatio, ())),
        "display_mode": int(reader.call(lambda: view.GetDisplayMode2(), -1)),
    }
    native_lineweights = _component_lineweights(reader, view)
    native_lineweights["emphasize_outline"] = _witness_value(
        reader, lambda: view.EmphasizeOutline, source="IView.EmphasizeOutline", kind="bool",
    )
    if _has_unreadable(native_lineweights):
        native_lineweights["status"] = "unreadable"
    record["native_lineweights"] = native_lineweights
    record["annotations"] = [
        item
        for item in (
            _dump_annotation(reader, annotation)
            for annotation in (reader.call(lambda: view.GetAnnotations(), ()) or ())
        )
        if item is not None
    ]
    sections = []
    for raw in reader.call(lambda: view.GetSectionLines(), ()) or ():
        section = reader.bind(raw, "IDrSection")
        if section is None:
            continue
        text_format = reader.bind(reader.need(lambda s=section: s.GetTextFormat()), "ITextFormat")
        sections.append(
            {
                "label": str(reader.need(lambda s=section: s.GetLabel(), "")),
                "line": _round(reader.need(lambda s=section: s.GetLineInfo(), ())),
                "arrows": _round(reader.need(lambda s=section: s.GetArrowInfo(), ())),
                "texts": _round(reader.need(lambda s=section: s.GetTextInfo(), ())),
                "text_height": round(
                    float(reader.need(lambda: text_format.CharHeight, 0.0)) if text_format else 0.0, 7
                ),
            }
        )
    if sections:
        record["sections"] = sections
    detail = reader.call(lambda: view.GetDetailCircleInfo2())
    if detail:
        record["detail_circles_info"] = _round(detail)
    return record


def collect_sheet_dumps(
    adapter: Any,
    *,
    stem: str,
    pdf: Path,
    sheet_layouts: Mapping[str, DrawingLayout],
    is_pictorial: Callable[[str], bool],
) -> list[dict[str, Any]]:
    """One dump per sheet of the adapter's open drawing, no sheet activated,
    each carrying its page of the exported ``pdf``."""
    with _telemetry.span("layout.read_pdf", pdf=pdf.name) as span:
        pages = read_pdf_ink(pdf)
        span.set_attribute("pages", len(pages))
    with _telemetry.span("layout.collect_com", stem=stem) as span:
        reader = _Reader(adapter)
        try:
            dumps = _collect_com(
                adapter, reader, stem=stem, pdf=pdf, pages=pages, sheet_layouts=sheet_layouts, is_pictorial=is_pictorial
            )
        finally:
            for key, value in reader.cost_attributes().items():
                span.set_attribute(key, value)
        span.set_attribute("sheets", len(dumps))
    return dumps


def _collect_com(
    adapter: Any,
    reader: _Reader,
    *,
    stem: str,
    pdf: Path,
    pages: list[PageInk],
    sheet_layouts: Mapping[str, DrawingLayout],
    is_pictorial: Callable[[str], bool],
) -> list[dict[str, Any]]:
    ddoc = _early_bound(adapter.currentModel, "IDrawingDoc")
    # GetViews' sheet order is undetermined; the PDF prints GetSheetNames order.
    # Both are read strictly: a tolerant empty answer would audit no sheet and
    # cache a clean report.
    page_of = {str(name): page for page, name in enumerate(ddoc.GetSheetNames() or ())}
    if not page_of or len(pages) != len(page_of):
        raise RuntimeError(
            f"layout audit: {len(page_of)} sheet(s) but {len(pages)} page(s) in {pdf.name}"
        )
    rows = ddoc.GetViews() or ()
    native_lineweights = _document_lineweights(reader)
    dumps = []
    for index, row in enumerate(rows):
        entries = list(row or ())
        if not entries:
            continue
        try:
            dump = _dump_sheet(
                reader, ddoc, entries, index=index, stem=stem, pdf=pdf, pages=pages, page_of=page_of,
                sheet_layouts=sheet_layouts, is_pictorial=is_pictorial,
            )
            dump["native_lineweights"] = native_lineweights
        except Exception as exc:
            raise _collector_fault(stem, dumps, reader, exc) from exc
        dumps.append(dump)
    audited = sorted(str(dump["sheet"]) for dump in dumps)
    if audited != sorted(page_of):
        raise RuntimeError(f"layout audit: dumped sheets {audited}, drawing has {sorted(page_of)}")
    return dumps


def _collector_fault(stem: str, dumps: list[dict[str, Any]], reader: _Reader, exc: Exception) -> RuntimeError:
    """The error a collector fault raises, and a warn saying how far it got.

    Fail loud: no report is written. What was collected up to the fault
    (the sheets dumped, each one's refused reads, and the refusals on the
    sheet it died in) rides the error and the warn instead.
    """
    done = {str(dump["sheet"]): dump["read_errors"] for dump in dumps}
    progress = f"{len(done)} sheet(s) dumped {done}; refused reads on the failing sheet {dict(reader.errors)}"
    _telemetry.warn(f"layout audit {stem}: collector fault after {progress}: {exc}")
    return RuntimeError(f"layout audit {stem}: collector fault after {progress}: {exc}")


def _dump_sheet(
    reader: _Reader,
    ddoc: Any,
    entries: list[Any],
    *,
    index: int,
    stem: str,
    pdf: Path,
    pages: list[PageInk],
    page_of: Mapping[str, int],
    sheet_layouts: Mapping[str, DrawingLayout],
    is_pictorial: Callable[[str], bool],
) -> dict[str, Any]:
    """One sheet's dump: ``entries`` is its ``GetViews`` row (sheet view first)."""
    sheet_view = reader.bind(entries[0], "IView")
    name = str(reader.call(lambda: sheet_view.GetName2(), "") or reader.need(lambda: sheet_view.Name, ""))
    sheet = reader.bind(reader.need(lambda n=name: ddoc.Sheet(n)), "ISheet")
    if sheet is None:
        raise RuntimeError(f"layout audit cannot reach sheet {name!r}")
    properties = _round(reader.need(lambda: sheet.GetProperties2(), ()))
    layout = sheet_layouts.get(name)
    template = DRAWING_TEMPLATES[layout] if layout is not None else None
    width, height = properties[5], properties[6]
    zone = {
        side: float(reader.need(lambda c=code: sheet.GetZoneMargin(c), 0.0))
        for side, code in _ZONE_MARGINS.items()
    }
    dump: dict[str, Any] = {
        "schema": DUMP_SCHEMA,
        "stem": stem,
        "sheet": name,
        "index": index,
        "page": page_of.get(name, -1),
        "layout": layout.value if layout is not None else "",
        "width": width,
        "height": height,
        "zone": zone,
        "views": [_dump_view(reader, view, is_pictorial=is_pictorial) for view in entries[1:]],
        "sheet_annotations": [
            item
            for item in (
                _dump_annotation(reader, annotation)
                for annotation in (reader.call(lambda: sheet_view.GetAnnotations(), ()) or ())
            )
            if item is not None
        ],
    }
    if template is not None:
        dump["title_block"] = _round(
            (template.title_block_left_m, 0.0, width, template.title_block_top_m)
        )
    tables: dict[str, dict[str, Any]] = {}
    for view in entries:
        view = reader.bind(view, "IView")
        for raw in reader.call(lambda v=view: v.GetTableAnnotations(), ()) or ():
            record = _table_record(reader, raw)
            if record is not None:
                tables[record["name"]] = record
    dump["tables"] = list(tables.values())
    dump["layers"] = _layer_states(reader, dump)
    page = dump["page"]
    if not 0 <= page < len(pages):
        raise RuntimeError(
            f"layout audit: sheet {name!r} is page {page} of {pdf.name}, which has {len(pages)}"
        )
    # A page of another size, or an origin/scale mismatch, would place all
    # the ink wrong; the size is checked here, placement by the text match
    # rate in _layout_audit.sheet_model.
    ink = pages[page]
    if abs(ink.width - width) > PAGE_SIZE_TOL_M or abs(ink.height - height) > PAGE_SIZE_TOL_M:
        raise RuntimeError(
            f"layout audit: sheet {name!r} is {width * 1000:.1f} x {height * 1000:.1f} mm but page "
            f"{page} of {pdf.name} is {ink.width * 1000:.1f} x {ink.height * 1000:.1f} mm"
        )
    dump["ink"] = page_ink(ink)
    dump["read_errors"] = reader.take_errors()
    return dump


def run_layout_audit(
    adapter: Any,
    *,
    stem: str,
    pdf: Path,
    report: Path,
    sheet_layouts: Mapping[str, DrawingLayout],
    is_pictorial: Callable[[str], bool],
    mode: LayoutAuditMode = LAYOUT_AUDIT_MODE,
) -> None:
    """Dump and audit every sheet, write ``report``; raise on a finding
    ``enforced`` for ``stem`` under ``mode`` (every gating one under GATE,
    the ``ENFORCED_KINDS`` and the stem's ``STEM_ENFORCED_KINDS`` under REPORT).

    A collector or audit fault fails the drawing in every mode: a report that
    silently skipped a sheet would under-count the fleet calibration. The
    previous build's report is removed first, so a fault leaves no stale
    findings beside the new PDF, and the new one lands atomically.
    """
    with _telemetry.span(f"layout.audit {stem}", stem=stem, mode=mode.value) as span:
        report.unlink(missing_ok=True)
        started = time.perf_counter()
        dumps = collect_sheet_dumps(
            adapter, stem=stem, pdf=pdf, sheet_layouts=sheet_layouts, is_pictorial=is_pictorial
        )
        collected = time.perf_counter() - started
        with _telemetry.span("layout.findings", stem=stem) as child:
            finding_started = time.perf_counter()
            content, gating = audit_report(stem, mode, dumps)
            child.set_attribute("findings_s", round(time.perf_counter() - finding_started, 3))
            for kind, count in content["summary"]["findings"].items():
                child.set_attribute(f"findings.{kind}", count)
        summary = content["summary"]
        summary["collect_s"] = round(collected, 3)
        summary["total_s"] = round(time.perf_counter() - started, 3)
        replace_text(report, json.dumps(content, separators=(",", ":")))
        for record in content["findings"]:
            _telemetry.debug(f"layout finding {stem}: {record['kind']}: {record['detail']}")
        span.set_attribute("sheets", summary["sheets"])
        span.set_attribute("gating", summary["gating"])
        span.set_attribute("collect_s", summary["collect_s"])
        hidden = sum(summary["hidden_layer"].values())
        span.set_attribute("hidden_layer", hidden)
        if hidden:
            _telemetry.info(f"layout audit {stem}: annotations on non-printing layers, not audited: {summary['hidden_layer']}")
        degenerate = sum(summary["degenerate_lines"].values())
        span.set_attribute("degenerate_lines", degenerate)
        if degenerate:
            _telemetry.info(f"layout audit {stem}: zero-length display lines, no ink: {summary['degenerate_lines']}")
        read_errors = sum(sum(d["read_errors"].values()) for d in dumps)
        span.set_attribute("read_errors", read_errors)
        if read_errors:
            _telemetry.warn(
                f"layout audit {stem}: {read_errors} refused COM read(s): "
                + "; ".join(f"{d['sheet']}: {d['read_errors']}" for d in dumps if d["read_errors"])
            )
        for kind, count in summary["findings"].items():
            span.set_attribute(f"findings.{kind}", count)
        _telemetry.info(
            f"layout audit {stem}: {summary['sheets']} sheet(s), {summary['gating']} gating, "
            f"{summary['findings']} -> {report}"
        )
        failing = enforced(mode, gating, stem=stem)
        if failing:
            raise RuntimeError(
                f"drawing layout audit failed for {stem} ({mode.value} mode): {len(failing)} "
                f"enforced finding(s):\n" + "\n".join(f"  - {finding.format()}" for finding in failing)
            )
