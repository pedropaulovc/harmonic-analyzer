"""Purchased stock/installed-state layout, independent of the four-view builder.

View configurations are assigned before measuring/fitting. Supplier references
never dimension the installed span. The optional fifth view is an actually
authored maximum state, not a callback inserted behind a four-view contract.
Nominal dimension diagrams are sketch-only configurations, never surrogate parts.
Their assigned sketches are shown per view and rebuilt before fitting.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from math import isfinite
from pathlib import Path
from typing import Any

from solidworks_mcp.adapters.com_variant import double_array
from solidworks_mcp.adapters.solidworks.drawing import iter_views, place_view, view_name

from _check import check
from _com import _early_bound
import _config
from _drawing_common import (
    DrawingOutputs, assert_asme_b_sheet, finalize_drawing, new_project_drawing,
    read_required_properties, stamp_drawing_summary,
)
from _drawing_projection import model_point_in_view
from _drawing_registry import DRAWING_TEMPLATES, DrawingSpec
from _drawing_sheet_region import sheet_drawable_region
from _drawing_view_display import set_hidden_lines_removed
from _purchased_fastener_drawing import (
    _PROPERTIES, _box, _cell, _center_marks_without_lines, _fit_group, _inside,
    _literal_note, _purchased_title_block, _rebuild, add_purchased_footer,
    assert_supplier_view_fits, check_item, supplier_fit_cells, view_band_bottom,
)
from _rebuild import active_configuration_name
from _supplier_spring_reference import SUPPLIER_FREE_CONFIGURATION, SUPPLIER_MAX_CONFIGURATION


def supplier_state_cells(caption_y: float, *, maximum: bool) -> tuple:
    """Reserve an annotation band around every fitted native view."""
    if not maximum:
        return (
            _cell("free_front", 0.028, caption_y + 0.020, 0.235, 0.166),
            _cell("free_top", 0.028, 0.207, 0.235, 0.247),
            _cell("free_right", 0.267, caption_y + 0.026, 0.406, 0.165),
            _cell("installed_iso", 0.325, 0.190, 0.406, 0.252),
        )
    return (
        _cell("free_front", 0.028, 0.166, 0.242, 0.206),
        _cell("free_top", 0.028, 0.230, 0.242, 0.250),
        _cell("free_right", 0.267, 0.205, 0.406, 0.252),
        _cell("installed_iso", 0.325, 0.142, 0.406, 0.175),
        _cell("max_front", 0.028, caption_y + 0.020, 0.403, 0.122),
    )


async def build_supplier_spring_drawing(
    adapter: Any, spec: DrawingSpec, *, item: str,
    dimensions: Callable[[Any, dict[str, Any]], Sequence[Callable[[], None]] | None],
    supplier_margins: Mapping[str, tuple[float, float, float, float]],
    maximum: bool = False,
    stock_configuration: str = SUPPLIER_FREE_CONFIGURATION,
    prepare_views: Callable[
        [Any, dict[str, Any]], Sequence[Callable[[], None]] | None
    ] | None = None,
    include_right: bool = True,
    stock_caption: str = "SUPPLIER FREE STATE",
    installed_caption: str = "INSTALLED REPRESENTATION",
    right_caption: str = "SUPPLIER NOMINAL SECTIONS",
    cut_to_suit: bool = False,
    spring_metadata: bool = False,
    settled_checks: Sequence[Callable[[], None]] = (),
) -> dict[str, str]:
    source = spec.source
    if spec.source_kind != "part" or not source.is_file():
        raise FileNotFoundError(f"source purchased part is missing: {source}")
    check(f"open {spec.artifact_stem}", await adapter.open_model(str(source)))
    model = _early_bound(adapter.currentModel, "IModelDoc2")
    if Path(model.GetPathName()).resolve() != source.resolve():
        raise RuntimeError(f"opened purchased part is not {source}")
    installed = active_configuration_name(adapter, model)
    available = set(model.GetConfigurationNames() or ())
    required = {stock_configuration}
    if maximum:
        required.add(SUPPLIER_MAX_CONFIGURATION)
    if not installed or installed in required or not required <= available:
        raise RuntimeError(f"{spec.artifact_stem}: installed/supplier configurations missing or ambiguous")
    if spring_metadata:
        names = (*_PROPERTIES, "Material Specification", "Finish", "Manufacturing Notes")
        properties = read_required_properties(model, names, required=names)
        material_property = "Material Specification"
        finish = properties["Finish"]
        notes = properties["Manufacturing Notes"]
        document_title = properties["Title"]
    else:
        properties = read_required_properties(model, _PROPERTIES, required=_PROPERTIES)
        registry = _config.parts(source.stem)
        expected = {
            "Number": str(registry["number"]), "Title": source.stem,
            "Material": str(registry["material"]), "Stock Name": str(registry["stock_name"]),
            "Supplier": str(registry["supplier"]),
            "Supplier SKUs": ", ".join(str(sku) for sku in registry["supplier_skus"]),
        }
        for name, value in expected.items():
            if properties[name] != value:
                raise RuntimeError(f"{source.stem}: stale source {name}: {properties[name]!r} != {value!r}")
        material_property = "Material"
        finish = registry["finish"]
        if not isinstance(finish, str) or not finish.strip():
            raise RuntimeError(f"{source.stem}: registered purchased finish is empty")
        notes = str(registry.get("installation_notes", ""))
        document_title = str(registry["title"])
    check_item(item, label=spec.artifact_stem)
    caption_y = view_band_bottom(notes, label=spec.artifact_stem)
    cells = tuple(
        cell
        for cell in supplier_state_cells(caption_y, maximum=maximum)
        if include_right or cell[0] != "free_right"
    )
    if not include_right and not maximum:
        cells = tuple(
            _cell("installed_iso", 0.267, caption_y + 0.026, 0.406, 0.252)
            if cell[0] == "installed_iso" else cell
            for cell in cells
        )
    if "installed_iso" in supplier_margins:
        raise ValueError("installed isometric must retain its unannotated geometry cell")
    fit_cells = supplier_fit_cells(cells, supplier_margins, label=spec.artifact_stem)
    draw, sheet = new_project_drawing(adapter, layout=spec.layout)
    title_notes = _purchased_title_block(
        adapter, draw, material=properties[material_property],
        finish=finish, material_property=material_property,
    )
    title = f"{document_title} — Supplier and Installed Reference Drawing"
    stamp_drawing_summary(adapter, draw, {
        0: title, 1: "Purchased identification only; supplier sizes are reference dimensions",
        2: "Harmonic Analyzer Project",
        3: f"{spec.artifact_stem}; {properties['Supplier']}; {properties['Supplier SKUs']}",
        4: f"{stock_caption}; installed pictorial; separate maximum state"
           if maximum else f"{stock_caption}; separate installed pictorial",
    })
    orientations = {"free_front": "*Front", "free_top": "*Top", "free_right": "*Right",
                    "installed_iso": "*Isometric", "max_front": "*Front"}
    configurations = {key: stock_configuration for key in orientations}
    configurations["installed_iso"] = installed
    configurations["max_front"] = SUPPLIER_MAX_CONFIGURATION
    views: dict[str, Any] = {}
    for key, center, _ in cells:
        view = _early_bound(place_view(adapter, str(source), orientations[key], *center, scale=(1, 1)), "IView")
        view.ReferencedConfiguration = configurations[key]
        if str(view.ReferencedConfiguration) != configurations[key]:
            raise RuntimeError(f"{key}: supplier/installed configuration assignment failed")
        set_hidden_lines_removed(adapter, view)
        views[key] = view
    for view in views.values():
        view.UseSheetScale = 0
        view.ScaleRatio = double_array([1.0, 1.0])
    preparation_checks = prepare_views(adapter, views) if prepare_views else ()
    _rebuild(draw, phase="supplier states before fitting")
    for prepared_check in preparation_checks or ():
        prepared_check()
    scales = {}
    for keys in (("free_front", "free_top"), ("free_right",), ("installed_iso",), ("max_front",)):
        members = [(views[key], cell) for cell in fit_cells if (key := cell[0]) in keys]
        if members:
            scale = _fit_group(draw, members)
            scales.update({cell[0]: scale for _, cell in members})
    _center_marks_without_lines(list(views.values()), cells)
    scale = scales["free_front"]
    values = tuple(adapter._get_attr_or_call(sheet, "GetProperties2"))
    if len(values) != 8:
        raise RuntimeError("supplier sheet has incomplete native properties")
    sheet.SetProperties2(int(values[0]), int(values[1]), float(scale[0]), float(scale[1]),
                         False, float(values[5]), float(values[6]), False)
    sheet.CustomPropertyView = view_name(adapter, views["installed_iso"])
    if not sheet.CustomPropertyView:
        raise RuntimeError("supplier sheet has no installed property-source view")
    assert_asme_b_sheet(adapter, sheet, layout=spec.layout, phase="supplier states", scale=scale)
    fitted_names = {key: view_name(adapter, view) for key, view in views.items()}
    fitted_origins = {}
    for key, view in views.items():
        view.UpdateViewDisplayGeometry()
        origin = model_point_in_view(
            adapter, view, (0.0, 0.0, 0.0), label=f"{spec.artifact_stem} {key} fitted origin"
        )
        if not all(map(isfinite, origin)):
            raise RuntimeError(f"{key}: fitted model origin is not finite")
        fitted_origins[key] = origin
    dimension_checks = dimensions(adapter, views) or ()
    ddoc = _early_bound(draw, "IDrawingDoc")
    ddoc.ActivateView("")
    if not ddoc.GetEditSheet() or ddoc.ActiveDrawingView is not None:
        raise RuntimeError("cannot restore supplier sheet context for captions/footer")
    captions = {
        "free_front": f"{stock_caption} — FRONT",
        "free_top": f"{stock_caption} — TOP",
        "free_right": right_caption,
        "installed_iso": installed_caption,
        "max_front": "SUPPLIER MAXIMUM EXTENSION — NOT INSTALLED",
    }
    placed = []
    for key, center, cell in cells:
        ratio = scales[key]
        text = f"{captions[key]}  {ratio[0]}:{ratio[1]}"
        y = cell[1] - (0.016 if key == "free_right" else 0.012)
        note = _literal_note(adapter, text, center[0], y)
        bounds = _box(note.GetExtent(), label=text, kind="note")
        annotation = _early_bound(note.GetAnnotation(), "IAnnotation")
        if int(annotation.OwnerType) != 1:
            raise RuntimeError(f"{key}: state caption is not sheet-owned")
        x = center[0] - (bounds[2] - bounds[0]) / 2
        if not annotation.SetPosition(x, y, 0.0):
            raise RuntimeError(f"{key}: cannot center state caption")
        placed.append((note, text, text, (0.015, y - 0.008, 0.416, y + 0.001)))
    placed.extend(add_purchased_footer(adapter, draw, properties, item=item, notes=notes,
                                       cut_to_suit=cut_to_suit, label=spec.artifact_stem))
    _rebuild(draw, phase="supplier/installed annotations")
    actual = list(iter_views(adapter))
    if len(actual) != len(cells):
        raise RuntimeError(f"supplier sheet must have exactly {len(cells)} native views")
    template = DRAWING_TEMPLATES[spec.layout]
    region = sheet_drawable_region(adapter, sheet, width=template.width_m, height=template.height_m)
    border = (region.xmin, region.ymin, region.xmax, region.ymax)
    for key, _, cell in cells:
        view = views[key]
        if (Path(view.GetReferencedModelName()).resolve() != source.resolve()
                or str(view.ReferencedConfiguration) != configurations[key]
                or str(view.GetOrientationName()) != orientations[key]
                or tuple(view.ScaleRatio) != scales[key]
                or not _inside(_box(view.GetOutline(), label=key), cell)):
            raise RuntimeError(f"{key}: fitted native supplier-state view contract changed")
    for note, linked, resolved in title_notes:
        if note.PropertyLinkedText != linked or note.GetText() != resolved:
            raise RuntimeError("supplier-state title-block property resolution changed")
    def sheet_note_contract() -> None:
        for note, linked, resolved, cell in placed:
            if (int(_early_bound(note.GetAnnotation(), "IAnnotation").OwnerType) != 1
                    or note.PropertyLinkedText != linked
                    or note.GetText().replace("\r\n", "\n") != resolved
                    or not _inside(_box(note.GetExtent(), label=resolved, kind="note"), cell)
                    or not _inside(_box(note.GetExtent(), label=resolved, kind="note"), border)):
                raise RuntimeError(
                    f"supplier-state sheet note readback/owner/border contract failed: {resolved}"
                )

    sheet_note_contract()

    def settled_state_contract() -> None:
        rebuilt_views = {
            view_name(adapter, view): _early_bound(view, "IView")
            for view in iter_views(adapter)
        }
        if set(rebuilt_views) != set(fitted_names.values()):
            raise RuntimeError("final rebuilt supplier-state native view set changed")
        for key, _, cell in cells:
            view = rebuilt_views[fitted_names[key]]
            if (Path(view.GetReferencedModelName()).resolve() != source.resolve()
                    or str(view.ReferencedConfiguration) != configurations[key]
                    or str(view.GetOrientationName()) != orientations[key]
                    or tuple(view.ScaleRatio) != scales[key]
                    or not _inside(_box(view.GetOutline(), label=key), cell)):
                raise RuntimeError(f"{key}: final rebuilt supplier-state view contract changed")
            view.UpdateViewDisplayGeometry()
            origin = model_point_in_view(
                adapter, view, (0.0, 0.0, 0.0),
                label=f"{spec.artifact_stem} {key} settled origin",
            )
            if not all(map(isfinite, origin)) or any(
                abs(actual - expected) > 1e-6
                for actual, expected in zip(origin, fitted_origins[key], strict=True)
            ):
                raise RuntimeError(f"{key}: final rebuilt supplier-state view moved")
            if (view.GetFirstDisplayDimension6() is not None) != (key in supplier_margins):
                raise RuntimeError(
                    f"{key}: native dimensions do not match the reserved annotation cells"
                )
            assert_supplier_view_fits(
                adapter, view, cell, label=f"{spec.artifact_stem} {key}"
            )
        sheet_note_contract()

    paths = spec.outputs
    return await finalize_drawing(
        adapter, DrawingOutputs(slddrw=paths["slddrw"], pdf=paths["pdf"], png=paths["png"]),
        layout=spec.layout, pdf_title=title, scale=scale,
        settled_checks=(*settled_checks, *dimension_checks, settled_state_contract),
    )
