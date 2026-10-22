"""Native catalogue bead reference on the actual keeper-chain seed semicircle.

The rod/bead intersection is smaller than the sphere and cannot carry this
size. No pitch, rod, sag or coupler value has supplier numeric authority.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any

from _com import _early_bound
from _drawing_hidden_sketches import curate_view_dimensions
from _supplier_dimensions import (
    assert_supplier_reference_dimension,
    supplier_reference_dimension,
)
import dt_vn_keeper_chain_spec as chain


def annotate_keeper_bead(adapter: Any, views: Mapping[str, Any]) -> Callable[[], None]:
    """Import the true diameter driving the unchanged revolved seed bead."""
    view = _early_bound(views["*Front"], "IView")
    source = _early_bound(view.ReferencedDocument, "IModelDoc2")
    source_path = str(source.GetPathName())
    configuration = str(view.ReferencedConfiguration)
    if not source_path or not configuration:
        raise RuntimeError("keeper catalogue bead size has no native owner/configuration")
    outline = tuple(float(value) for value in view.GetOutline())
    name = chain.CATALOGUE_BEAD_DIMENSION
    annotations = curate_view_dimensions(
        adapter,
        view,
        keep={name: (outline[2] + 0.006, outline[3] + 0.006)},
        view_label="keeper catalogue bead diameter",
        dimensions_by_feature=chain.DRAWING_DIMENSIONS,
    )
    if len(annotations) != 1:
        raise RuntimeError("keeper catalogue bead diameter: expected one native source dimension")
    display = _early_bound(
        _early_bound(annotations[0], "IAnnotation").GetSpecificAnnotation(),
        "IDisplayDimension",
    )
    if int(display.Type2) != 6:  # swDimensionType_e.swDiameterDimension
        raise RuntimeError("keeper catalogue bead size is not a native diameter")
    presentation = {
        "label": f"{name}@SeedProfile",
        "units": "in",
        "configuration": configuration,
        "precision": chain.DRAWING_REFERENCE_PRECISION[name],
        "expected_mm": chain.BEAD_DIA,
        "presentation": "diameter",
        "fraction_denominator": 32,
        "callout": "CATALOGUE BEAD SIZE",
    }
    supplier_reference_dimension(adapter, display, **presentation)

    def settled() -> None:
        # Reacquire from the final view, never retain an annotation COM proxy
        # across rebuild as proof of the surviving source/inventory.
        found = []
        for orientation, raw_view in views.items():
            final_view = _early_bound(raw_view, "IView")
            count = int(final_view.GetDisplayDimensionCount())
            if count != (1 if orientation == "*Front" else 0):
                raise RuntimeError("keeper catalogue bead reference inventory changed")
            if orientation != "*Front":
                continue
            final_source = _early_bound(final_view.ReferencedDocument, "IModelDoc2")
            if (
                str(final_source.GetPathName()) != source_path
                or str(final_view.ReferencedConfiguration) != configuration
            ):
                raise RuntimeError("keeper catalogue bead size changed native owner/configuration")
            for raw_annotation in final_view.GetAnnotations() or ():
                annotation = _early_bound(raw_annotation, "IAnnotation")
                if int(annotation.GetType()) != 4:  # swAnnotationType_e.swDisplayDimension
                    continue
                final_display = _early_bound(annotation.GetSpecificAnnotation(), "IDisplayDimension")
                native = _early_bound(final_display.GetDimension2(0), "IDimension")
                if (
                    int(final_display.Type2) != 6
                    or str(native.Name) != name
                    or str(native.FullName).split("@")[1:2] != ["SeedProfile"]
                ):
                    raise RuntimeError("keeper catalogue bead size lost its native source diameter")
                source_dimension = final_source.Parameter(f"{name}@SeedProfile")
                if source_dimension is None:
                    raise RuntimeError("keeper catalogue bead source dimension disappeared")
                owner_dimension = _early_bound(source_dimension, "IDimension")
                if str(owner_dimension.FullName) != str(native.FullName):
                    raise RuntimeError("keeper catalogue bead dimension is not owned by the viewed source")
                raw_values = owner_dimension.GetSystemValue3(3, [configuration])
                explicit_values = owner_dimension.GetSystemValue3(3, configuration)
                print(
                    "keeper configured getter diagnostic: "
                    f"configuration={configuration!r} owner={owner_dimension.FullName!r} "
                    f"list_type={type(raw_values).__name__} list_value={raw_values!r} "
                    f"bstr_type={type(explicit_values).__name__} bstr_value={explicit_values!r}",
                    flush=True,
                )
                values = tuple(raw_values or ())
                if len(values) != 1 or abs(float(values[0]) * 1000.0 - chain.BEAD_DIA) > 1e-5:
                    raise RuntimeError("keeper catalogue bead source value changed in the viewed configuration")
                if int(_early_bound(native.Tolerance, "IDimensionTolerance").Type) != 0:
                    raise RuntimeError("keeper catalogue bead size acquired an unprovided tolerance")
                assert_supplier_reference_dimension(adapter, final_display, **presentation)
                found.append(final_display)
        if len(found) != 1:
            raise RuntimeError("keeper catalogue bead diameter: final native inventory is not one")

    return settled
