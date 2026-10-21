"""Nominal supplier diagram/installed-state layout, independent of the four-view builder.

View configurations are assigned before measuring/fitting. Supplier references
never dimension the installed span. The optional maximum view is a construction-only nominal gauge, not a callback inserted behind a four-view contract.
Nominal dimension diagrams are sketch-only configurations, never surrogate parts.
Their assigned sketches are shown per view and rebuilt before fitting.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping, Sequence
from math import isclose, isfinite
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


def reacquire_supplier_dimensions(
    adapter: Any, views: Mapping[str, Any], *,
    expected: Mapping[str, Mapping[str, str]],
    configurations: Mapping[str, str],
) -> dict[str, Any]:
    """Reacquire the entire native annotation inventory after the final rebuild.

    ``expected`` maps each view key to dimension-name/owner-sketch pairs,
    including empty installed pictorial inventories. No cached display object
    is accepted as proof of its continued presence on the rebuilt sheet.
    """
    rebuilt = {view_name(adapter, view): _early_bound(view, "IView")
               for view in iter_views(adapter)}
    if set(expected) != set(views):
        raise RuntimeError("supplier final annotation view inventory changed")
    found = {}
    for key, owners in expected.items():
        view = rebuilt.get(view_name(adapter, views[key]))
        if view is None or str(view.ReferencedConfiguration) != configurations[key]:
            raise RuntimeError(f"{key}: supplier final native view/configuration changed")
        present = {}
        for raw in view.GetAnnotations() or ():
            annotation = _early_bound(raw, "IAnnotation")
            if int(annotation.GetType()) != 4:  # swDisplayDimension
                continue
            display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
            native = display.GetDimension2(0)
            if native is None:
                raise RuntimeError(f"{key}: supplier native annotation lost its dimension")
            identity = str(_early_bound(native, "IDimension").FullName).split("@")
            if len(identity) < 2 or identity[0] not in owners or owners[identity[0]] != identity[1]:
                raise RuntimeError(f"{key}: unexpected supplier dimension owner {identity!r}")
            name = identity[0]
            if name in present or name in found:
                raise RuntimeError(f"{key}: duplicate supplier dimension {name}")
            present[name] = display
            found[name] = display
        if set(present) != set(owners) or int(view.GetDisplayDimensionCount()) != len(owners):
            raise RuntimeError(f"{key}: supplier final annotation inventory changed")
    return found


def assert_supplier_configuration_value(
    display: Any, configuration: str, expected_mm: float, *, label: str,
) -> None:
    """Read the exact model-owned SI value in the dimension's drawing configuration."""
    native = _early_bound(display.GetDimension2(0), "IDimension")
    values = tuple(native.GetSystemValue3(3, configuration) or ())
    if len(values) != 1 or not isclose(
        float(values[0]), expected_mm / 1000.0, rel_tol=0.0, abs_tol=1e-11,
    ):
        raise RuntimeError(f"{label}: exact configured supplier dimension changed")


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
    supplier_dimensions: Callable[[Any, dict[str, Any]], Sequence[Callable[[], None]] | None],
    supplier_margins: Mapping[str, tuple[float, float, float, float]],
    maximum: bool = False,
    stock_configuration: str = SUPPLIER_FREE_CONFIGURATION,
    prepare_views: Callable[
        [Any, dict[str, Any]], Sequence[Callable[[], None]] | None
    ] | None = None,
    include_right: bool = True,
    include_top: bool = True,
    installed_configuration: str | None = None,
    installed_variants: Sequence[tuple[str, str]] = (),
    stock_caption: str = "SUPPLIER NOMINAL STOCK DIAGRAM — NOT PART SHAPE",
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
    installed = installed_configuration or active_configuration_name(adapter, model)
    available = set(model.GetConfigurationNames() or ())
    required = {stock_configuration}
    if maximum:
        required.add(SUPPLIER_MAX_CONFIGURATION)
    if not installed or installed not in available or installed in required or not required <= available:
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
        if (include_right or cell[0] != "free_right")
        and (include_top or cell[0] != "free_top")
    )
    if not include_right and not maximum:
        cells = tuple(
            _cell("installed_iso", 0.267, caption_y + 0.026, 0.406, 0.252)
            if cell[0] == "installed_iso" else cell
            for cell in cells
        )
    if installed_variants:
        if (maximum or include_right or len(installed_variants) != 2
                or len({name for name, _label in installed_variants}) != 2
                or any(name not in available or name in required or not label.strip()
                       for name, label in installed_variants)):
            raise ValueError("two installed variants require distinct original configs and include_right=False")
        installed = installed_variants[0][0]
        cells = tuple(cell for cell in cells if cell[0] != "installed_iso") + (
            _cell("installed_iso", 0.267, caption_y + 0.026, 0.406, 0.165),
            _cell("installed_second_iso", 0.267, 0.190, 0.406, 0.252),
        )
    if any(key.startswith("installed_") for key in supplier_margins):
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
    if installed_variants:
        orientations["installed_second_iso"] = "*Isometric"
        configurations["installed_second_iso"] = installed_variants[1][0]
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
    for keys in (("free_front", "free_top"), ("free_right",), ("installed_iso",), ("installed_second_iso",), ("max_front",)):
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
    dimension_checks = supplier_dimensions(adapter, views) or ()
    ddoc = _early_bound(draw, "IDrawingDoc")
    ddoc.ActivateView("")
    if not ddoc.GetEditSheet() or ddoc.ActiveDrawingView is not None:
        raise RuntimeError("cannot restore supplier sheet context for captions/footer")
    captions = {
        "free_front": f"{stock_caption} — FRONT",
        "free_top": f"{stock_caption} — TOP",
        "free_right": right_caption,
        "installed_iso": installed_caption,
        "max_front": "SUPPLIER NOMINAL MAXIMUM EXTENSION — NOT INSTALLED",
        "installed_second_iso": installed_variants[1][1] if installed_variants else "",
    }
    if installed_variants:
        captions["installed_iso"] = installed_variants[0][1]
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
