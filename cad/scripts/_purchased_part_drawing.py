"""Four-view purchased-part reference sheets for stock that is not a catalogued fastener.

This builder reads the part's own Material Specification / Finish /
Manufacturing Notes, as the spring builder does, and lays it out in the
fastener cells, with the part's note printed as its footer note.  The
Isometric scales on its own, so a compact loop's tall pictorial never shrinks
the orthographic views.
"""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Any, Literal

from _drawing_common import read_required_properties
from _drawing_registry import DrawingSpec
from _purchased_fastener_drawing import (
    NumberFit,
    SupplierDimensions,
    SupplierMargins,
    _PROPERTIES,
    _build_reference_sheet,
    _open_supplier_source_read_only,
    _retain_supplier_source_failure,
    _source_file_sha256,
    _supplier_source_checkpoint,
)


async def build_purchased_part_drawing(
    adapter: Any,
    spec: DrawingSpec,
    *,
    item: str,
    cut_to_suit: bool = False,
    supplier_dimensions: SupplierDimensions | None = None,
    supplier_margins: SupplierMargins | None = None,
    configuration: str | None = None,
    settled_checks: Sequence[Callable[[], None]] = (),
    supplier_data: Sequence[str] = (),
    title_block_setup: Callable[[Any], Callable[[], None]] | None = None,
    view_layout: Literal["standard", "supplier_top", "tall_top"] = "standard",
    number_fit: NumberFit = NumberFit.TEMPLATE,
    unit: str = "mm",
) -> dict[str, str]:
    """Front/Top/Right plus Isometric of a purchased part, its note in the footer.

    ``item`` is the catalogue designation on the ITEM row; ``cut_to_suit``
    marks stock its note cuts at assembly. Source identity/read-only state and
    bytes are observed through export and close; this detects mutation, not a
    native source-preservation guarantee.
    ``title_block_setup`` formats this drawing's existing linked notes after
    their source resolves and returns the check to repeat after the final rebuild.
    ``view_layout`` selects the purchased fastener cells, as for fasteners.
    ``number_fit`` opts a long registry number into the DWG. NO. fit.
    ``unit`` is the part's ``drawing_unit`` (``new_project_drawing``).
    """
    source = spec.source
    if spec.source_kind != "part" or not source.is_file():
        raise FileNotFoundError(f"source purchased part is missing: {source}")
    source_sha256 = _source_file_sha256(source)
    primary: BaseException | None = None
    source_evidence: list[dict[str, Any]] = []
    try:
        model = _open_supplier_source_read_only(
            adapter, source, label=spec.artifact_stem
        )
        names = (
            *_PROPERTIES,
            "Material Specification",
            "Finish",
            "Manufacturing Notes",
        )
        properties = read_required_properties(model, names, required=names)
        return await _build_reference_sheet(
            adapter,
            spec,
            properties=properties,
            finish=properties["Finish"],
            item=item,
            material_property="Material Specification",
            notes=properties["Manufacturing Notes"],
            cut_to_suit=cut_to_suit,
            supplier_dimensions=supplier_dimensions,
            supplier_margins=supplier_margins,
            configuration=configuration,
            settled_checks=settled_checks,
            supplier_data=supplier_data,
            title_block_setup=title_block_setup,
            number_fit=number_fit,
            view_layout=view_layout,
            unit=unit,
            source_checkpoint=_supplier_source_checkpoint(
                adapter,
                source,
                model,
                source_sha256,
                label=spec.artifact_stem,
                evidence=source_evidence,
                configuration=configuration,
            ),
        )
    except BaseException as error:
        primary = error
        raise
    finally:
        try:
            if _source_file_sha256(source) != source_sha256:
                raise RuntimeError(
                    f"{spec.artifact_stem}: supplier source part bytes changed during drawing"
                )
        except BaseException as preservation_error:
            if primary is not None:
                primary.add_note(
                    f"{spec.artifact_stem}: supplier source file preservation also failed: {preservation_error!r}"
                )
            else:
                _retain_supplier_source_failure(
                    spec, preservation_error, source_evidence
                )
        if primary is not None:
            _retain_supplier_source_failure(spec, primary, source_evidence)
