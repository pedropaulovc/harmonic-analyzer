"""Manufacturing mixin for PyWin32 SolidWorks operations (Phase 5).

Implements material assignment (``IPartDoc::SetMaterialPropertyName2``),
cosmetic threads (``IFeatureManager::InsertCosmeticThread3``) and BOM
tables (``IModelDocExtension::InsertBomTable4`` read through
``ITableAnnotation``), including CSV export of BOM contents.
"""

from __future__ import annotations

import csv
import glob
from pathlib import Path
from typing import Any, cast

from .. import sw_type_info as _sw_type_info
from ..base import (
    AdapterResult,
    AdapterResultStatus,
    AddThreadParameters,
    ApplyMaterialParameters,
    CreateBomParameters,
    TappedHoleParameters,
)
from .features import _flag_feature_methods, _read_member, _select_by_point
from .parametrics import _active_configuration_name

# swFeatureNameID_e.swFmHoleWzd — the feature-data type CreateDefinition mints for
# a Hole Wizard hole. (All four hole-wizard enum ints below were validated by
# reflection into SolidWorks.Interop.swconst.dll — the doc bundle lists the
# swFeatureNameID_e members without integers.)
_SW_FM_HOLE_WZD = 25

# swWzdGeneralHoleTypes_e — the generic kind of hole.
_WZD_HOLE_TYPES = {"tap": 4}  # swWzdTap (straight tapped hole)

# swWzdHoleStandards_e — the fastener standard the size table is keyed to.
_WZD_HOLE_STANDARDS = {"ansi_inch": 0}  # swStandardAnsiInch

# swWzdHoleStandardFastenerTypes_e — the fastener/hole type within the standard.
_WZD_FASTENER_TYPES = {"tapped_hole": 27}  # swStandardAnsiInchTappedHole

# swEndConditions_e — how far the hole drills.
_WZD_END_TYPES = {"through_all": 1}  # swEndCondThroughAll

# NOTE: each map holds only combinations verified against the live Hole Wizard DB
# (see the pen-v-block build). Extend by adding the enum int from the interop DLL
# (or the swconst docs) — never guess a value; an invalid one fails CreateFeature.

# swCosmeticStandardType_e
_THREAD_STANDARDS = {
    "none": -2,
    "ansi_inch": 0,
    "ansi_metric": 1,
    "bsi": 2,
    "din": 4,
    "helicoil_inch": 6,
    "helicoil_metric": 7,
    "iso": 8,
    "jis": 9,
}

# swCosmeticEndConditions_e
_THREAD_END_TYPES = {
    "blind": 0,
    "blind_upto_next": 1,
    "through": 2,
    "blind_2dia": 3,
}

# swBomType_e
_BOM_TYPES = {
    "parts_only": 1,
    "top_level": 2,
    "indented": 3,
    "flattened": 4,
}

# Fallback install locations of the standard BOM table template (classic
# and 3DEXPERIENCE editions). The primary lookup derives the path from the
# running instance's executable instead.
_BOM_TEMPLATE_GLOBS = [
    r"C:\Program Files\SOLIDWORKS*\SOLIDWORKS\lang\english\bom-standard.sldbomtbt",
    r"C:\Program Files\SOLIDWORKS*\lang\english\bom-standard.sldbomtbt",
    r"C:\Program Files\Dassault Systemes\SOLIDWORKS*\SOLIDWORKS\lang\english"
    r"\bom-standard.sldbomtbt",
]


class SolidWorksManufacturingMixin:
    """Expose SolidWorks manufacturing-prep methods via mixin-local helpers."""

    async def apply_material(
        self, params: ApplyMaterialParameters
    ) -> AdapterResult[dict[str, Any]]:
        return _apply_material_impl(self, params)

    async def add_thread(
        self, params: AddThreadParameters
    ) -> AdapterResult[dict[str, Any]]:
        return _add_thread_impl(self, params)

    async def insert_tapped_hole(
        self, params: TappedHoleParameters
    ) -> AdapterResult[dict[str, Any]]:
        return _insert_tapped_hole_impl(self, params)

    async def edit_hole_position(
        self, hole_name: str, rename_sketch: str
    ) -> AdapterResult[str]:
        return _edit_hole_position_impl(self, hole_name, rename_sketch)

    async def create_bom(
        self, params: CreateBomParameters
    ) -> AdapterResult[dict[str, Any]]:
        return _create_bom_impl(self, params)

    async def export_bom_csv(
        self, params: CreateBomParameters
    ) -> AdapterResult[dict[str, Any]]:
        return _export_bom_csv_impl(self, params)


def _apply_material_impl(
    adapter: Any, params: ApplyMaterialParameters
) -> AdapterResult[dict[str, Any]]:
    """Assign a material via ``IPartDoc::SetMaterialPropertyName2``.

    The active part document exposes the ``IPartDoc`` interface on the same
    dispatch as ``IModelDoc2``. ``SetMaterialPropertyName2`` returns nothing,
    so the assignment is verified by reading ``MaterialIdName`` back; a
    rebuild follows so mass properties reflect the new density.

    Args:
        adapter: A fully connected ``PyWin32Adapter``.
        params: Material name, database and configuration scope.

    Returns:
        AdapterResult[dict[str, Any]]: Applied material/configuration or
        error.
    """
    if not adapter.currentModel:
        return AdapterResult(status=AdapterResultStatus.ERROR, error="No active model")
    if not params.material.strip():
        return AdapterResult(
            status=AdapterResultStatus.ERROR, error="Material name is required"
        )

    def _material_operation() -> dict[str, Any]:
        model = adapter.currentModel
        configuration = params.configuration or _active_configuration_name(adapter)
        model = _flag_feature_methods(model, "IPartDoc")
        model.SetMaterialPropertyName2(configuration, params.database, params.material)

        applied = str(_read_member(model, "MaterialIdName") or "")
        if params.material not in applied:
            raise Exception(
                f"Material {params.material!r} was not applied (model reports "
                f"{applied!r}) — check the material exists in the database"
            )
        # ``EditRebuild3`` is an ``IModelDoc2`` member; ``model`` is rebound to
        # ``IPartDoc`` above for ``SetMaterialPropertyName2``, so drive the rebuild
        # off the still-``IModelDoc2`` ``currentModel`` handle (same document).
        adapter._attempt(lambda: adapter.currentModel.EditRebuild3())
        return {"material": params.material, "configuration": configuration}

    return cast(
        AdapterResult[dict[str, Any]],
        adapter._handle_com_operation("apply_material", _material_operation),
    )


def _add_thread_impl(
    adapter: Any, params: AddThreadParameters
) -> AdapterResult[dict[str, Any]]:
    """Add a cosmetic thread via ``IFeatureManager::InsertCosmeticThread3``.

    The target circular edge is selected by a point on it (subject to the
    view-dependent picking caveat on :func:`_select_by_point`). Lengths are
    converted from millimetres to metres for the API.

    Args:
        adapter: A fully connected ``PyWin32Adapter``.
        params: Edge location and thread specification.

    Returns:
        AdapterResult[dict[str, Any]]: Thread feature name/spec or error.
    """
    if not adapter.currentModel:
        return AdapterResult(status=AdapterResultStatus.ERROR, error="No active model")
    standard = _THREAD_STANDARDS.get(params.standard)
    if standard is None:
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error=f"Unknown thread standard: {params.standard!r} "
            f"(expected one of {sorted(_THREAD_STANDARDS)})",
        )
    end_type = _THREAD_END_TYPES.get(params.end_type)
    if end_type is None:
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error=f"Unknown thread end_type: {params.end_type!r} "
            f"(expected one of {sorted(_THREAD_END_TYPES)})",
        )

    def _thread_operation() -> dict[str, Any]:
        adapter._attempt(lambda: adapter.currentModel.ClearSelection2(True))
        if not _select_by_point(adapter, "EDGE", params.edge_point, 0, False):
            raise Exception(f"Failed to select a circular EDGE at {params.edge_point}")

        feature_manager = adapter.currentModel.FeatureManager
        feature_manager = _flag_feature_methods(feature_manager, "IFeatureManager")
        feature = feature_manager.InsertCosmeticThread3(
            standard,
            params.standard_type,
            params.size,
            params.diameter / 1000.0,
            end_type,
            params.depth / 1000.0,
            params.note,
        )
        if feature is None:
            raise Exception(
                "Failed to create cosmetic thread (the selected edge must be "
                "circular and the size valid for the standard)"
            )
        name = str(_read_member(feature, "Name") or "")
        return {"name": name, "standard": params.standard, "size": params.size}

    return cast(
        AdapterResult[dict[str, Any]],
        adapter._handle_com_operation("add_thread", _thread_operation),
    )


def _insert_tapped_hole_impl(
    adapter: Any, params: TappedHoleParameters
) -> AdapterResult[dict[str, Any]]:
    """Create a Hole Wizard tapped hole on a face via the feature-data object.

    Uses the ``CreateDefinition(swFmHoleWzd)`` -> ``InitializeHole`` ->
    ``CreateFeature`` flow (the maintainable path; ``HoleWizard5`` takes 28
    positional args with 12 opaque ``Value`` slots). The resulting ``HoleWzd``
    feature carries the fastener designation, so a drawing gets a native hole
    callout with no hard-coded thread map.

    Args:
        adapter: A fully connected ``PyWin32Adapter``.
        params: Face point (mm), size token, standard/fastener/end/hole keys.

    Returns:
        AdapterResult[dict[str, Any]]: ``{name, type, standard, size}`` or error.
    """
    if not adapter.currentModel:
        return AdapterResult(status=AdapterResultStatus.ERROR, error="No active model")

    hole_type = _WZD_HOLE_TYPES.get(params.hole_type)
    if hole_type is None:
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error=f"Unknown hole_type: {params.hole_type!r} "
            f"(expected one of {sorted(_WZD_HOLE_TYPES)})",
        )
    standard = _WZD_HOLE_STANDARDS.get(params.standard)
    if standard is None:
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error=f"Unknown standard: {params.standard!r} "
            f"(expected one of {sorted(_WZD_HOLE_STANDARDS)})",
        )
    fastener = _WZD_FASTENER_TYPES.get(params.fastener_type)
    if fastener is None:
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error=f"Unknown fastener_type: {params.fastener_type!r} "
            f"(expected one of {sorted(_WZD_FASTENER_TYPES)})",
        )
    end_type = _WZD_END_TYPES.get(params.end_type)
    if end_type is None:
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error=f"Unknown end_type: {params.end_type!r} "
            f"(expected one of {sorted(_WZD_END_TYPES)})",
        )
    if len(params.face_point) != 3:
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error=f"face_point must be [x, y, z] mm, got {params.face_point!r}",
        )
    if not params.size.strip():
        return AdapterResult(
            status=AdapterResultStatus.ERROR, error="Hole size token is required"
        )

    def _hole_operation() -> dict[str, Any]:
        adapter._attempt(lambda: adapter.currentModel.ClearSelection2(True))
        feature_manager = adapter.currentModel.FeatureManager
        feature_manager = _flag_feature_methods(feature_manager, "IFeatureManager")

        data = feature_manager.CreateDefinition(_SW_FM_HOLE_WZD)
        if data is None:
            raise Exception("CreateDefinition(swFmHoleWzd) returned None")
        # InitializeHole seeds the data object; the placement face is selected
        # AFTER (CreateFeature reads the current selection as the location).
        data.InitializeHole(hole_type, standard, fastener, params.size, end_type)
        if not _select_by_point(adapter, "FACE", params.face_point, 0, False):
            raise Exception(
                f"Failed to select the placement FACE at {params.face_point} mm "
                "(is the point on a visible solid face?)"
            )
        feature = feature_manager.CreateFeature(data)
        if feature is None:
            raise Exception(
                f"CreateFeature failed -- size {params.size!r} may be invalid for "
                f"standard {params.standard!r}/{params.fastener_type!r}"
            )
        feature = _flag_feature_methods(feature, "IFeature")
        name = str(_read_member(feature, "Name") or "")
        type_name = str(_read_member(feature, "GetTypeName2") or "")
        if type_name != "HoleWzd":
            raise Exception(f"created feature is {type_name!r}, not a HoleWzd")
        return {
            "name": name,
            "type": type_name,
            "standard": params.standard,
            "size": params.size,
        }

    return cast(
        AdapterResult[dict[str, Any]],
        adapter._handle_com_operation("insert_tapped_hole", _hole_operation),
    )


def _edit_hole_position_impl(
    adapter: Any, hole_name: str, rename_sketch: str
) -> AdapterResult[str]:
    """Open the positioning sketch of a Hole Wizard hole for dimensioning.

    A ``HoleWzd`` feature places its location point on the selected face
    UN-dimensioned (an under-defined pick), so its position is neither parametric
    nor visible as a locator dimension on a drawing. This enters sketch-edit mode
    on that internal positioning sketch — the wizard sub-feature that is a
    ``ProfileFeature`` holding exactly one sketch point — after renaming it to
    ``rename_sketch`` (a stable handle so equations can address its dims), sets
    ``adapter.currentSketchManager`` / ``currentSketch`` so the ordinary
    ``add_sketch_*`` helpers apply, registers the point, and returns its entity
    id. The caller then anchors the point to the origin (X/Y driving dims) and
    ``exit_sketch``; the hole becomes fully defined and its locators import to a
    drawing like any other model dimension.

    Args:
        adapter: A fully connected ``PyWin32Adapter``.
        hole_name: ``Name`` of the ``HoleWzd`` feature to edit.
        rename_sketch: New name for the positioning sketch feature.

    Returns:
        AdapterResult[str]: registered point entity id (e.g. ``"Point_1"``), or
        error if the hole / its single-point positioning sketch is not found.
    """
    if not adapter.currentModel:
        return AdapterResult(status=AdapterResultStatus.ERROR, error="No active model")

    def _find() -> str:
        model = adapter.currentModel
        # Locate the HoleWzd feature by name.
        feat = adapter._attempt(lambda: model.FirstFeature(), default=None)
        wizard = None
        while feat is not None:
            feat = _sw_type_info.early_bound_or_flag(
                feat,
                "IFeature",
                "GetTypeName2",
                "GetNextFeature",
                "GetFirstSubFeature",
            )
            if str(_read_member(feat, "Name") or "") == hole_name and (
                str(_read_member(feat, "GetTypeName2") or "") == "HoleWzd"
            ):
                wizard = feat
                break
            feat = adapter._attempt(
                lambda f=feat: _read_member(f, "GetNextFeature"), default=None
            )
        if wizard is None:
            raise Exception(f"HoleWzd feature {hole_name!r} not found")

        # Its positioning sketch is the sub-feature that is a ProfileFeature
        # holding exactly one sketch point (the hole profile has several).
        sub = adapter._attempt(lambda: wizard.GetFirstSubFeature(), default=None)
        pos_feat = pos_sketch = None
        while sub is not None:
            sub = _sw_type_info.early_bound_or_flag(
                sub,
                "IFeature",
                "GetTypeName2",
                "GetSpecificFeature2",
                "GetNextSubFeature",
            )
            if str(_read_member(sub, "GetTypeName2") or "") == "ProfileFeature":
                spec = adapter._attempt(
                    lambda s=sub: _read_member(s, "GetSpecificFeature2"), default=None
                )
                spec = _sw_type_info.early_bound_or_flag(
                    spec, "ISketch", "GetSketchPoints2"
                )
                pts = (
                    adapter._attempt(
                        lambda s=spec: _read_member(s, "GetSketchPoints2"), default=None
                    )
                    or []
                )
                if len(pts) == 1:
                    pos_feat, pos_sketch = sub, spec
                    break
            sub = adapter._attempt(
                lambda s=sub: _read_member(s, "GetNextSubFeature"), default=None
            )
        if pos_sketch is None:
            raise Exception(
                f"no single-point positioning sketch under HoleWzd {hole_name!r}"
            )

        # Rename for stable equation addressing, then enter sketch-edit mode.
        adapter._attempt(lambda: setattr(pos_feat, "Name", rename_sketch))
        adapter._attempt(lambda: model.ClearSelection2(True))
        if not adapter._attempt(lambda: pos_feat.Select2(False, 0), default=False):
            raise Exception(f"could not select positioning sketch {rename_sketch!r}")
        adapter._attempt(lambda: model.EditSketch())
        adapter.currentSketchManager = adapter._attempt(
            lambda: model.SketchManager, default=None
        )
        adapter.currentSketch = pos_sketch
        point = adapter._attempt(lambda s=pos_sketch: s.GetSketchPoints2()[0], default=None)
        if point is None:
            raise Exception("positioning sketch point vanished after EditSketch")
        return cast(str, adapter._register_sketch_entity("Point", point))

    return cast(
        AdapterResult[str],
        adapter._handle_com_operation("edit_hole_position", _find),
    )


def _default_bom_template(adapter: Any) -> str:
    """Locate the installed ``bom-standard.sldbomtbt`` template.

    Primary lookup: ``<sldworks.exe dir>/lang/english/`` of the running
    instance (``ISldWorks::GetExecutablePath``), which is install-layout
    agnostic. Falls back to globbing the known classic / 3DEXPERIENCE
    install locations.

    Args:
        adapter: Connected adapter (for the application dispatch).

    Returns:
        str: Template path.

    Raises:
        Exception: When no installed template is found.
    """
    exe = adapter._attempt(lambda: adapter.swApp.GetExecutablePath(), default=None)
    if exe:
        candidate = (
            Path(str(exe)).parent / "lang" / "english" / "bom-standard.sldbomtbt"
        )
        if candidate.is_file():
            return str(candidate)
    for pattern in _BOM_TEMPLATE_GLOBS:
        matches = sorted(glob.glob(pattern))
        if matches:
            return matches[-1]
    raise Exception(
        "No BOM table template found under the SolidWorks install folder — "
        "pass an explicit .sldbomtbt template path"
    )


def _read_bom_table(adapter: Any, table: Any) -> dict[str, Any]:
    """Read a BOM table annotation's full contents.

    Args:
        adapter: Connected adapter (for ``_attempt``).
        table: The ``IBomTableAnnotation``/``ITableAnnotation`` dispatch.

    Returns:
        dict[str, Any]: ``rows``/``columns`` counts, ``header`` row and
        ``data`` rows (header excluded) as displayed text.
    """
    table = _flag_feature_methods(table, "ITableAnnotation")
    row_count = int(_read_member(table, "RowCount") or 0)
    column_count = int(_read_member(table, "ColumnCount") or 0)

    def _cell(row: int, column: int) -> str:
        value = adapter._attempt(lambda: table.DisplayedText(row, column), default=None)
        if value is None:
            value = adapter._attempt(lambda: table.Text(row, column), default="")
        return str(value or "")

    grid = [
        [_cell(row, column) for column in range(column_count)]
        for row in range(row_count)
    ]
    header = grid[0] if grid else []
    return {
        "rows": row_count,
        "columns": column_count,
        "header": header,
        "data": grid[1:],
    }


def _insert_bom(adapter: Any, params: CreateBomParameters) -> dict[str, Any]:
    """Insert a BOM table and return its contents.

    Args:
        adapter: Connected adapter with a non-``None`` ``currentModel``.
        params: BOM type, configuration and template.

    Returns:
        dict[str, Any]: Table contents per :func:`_read_bom_table` plus the
        resolved ``configuration`` and ``bom_type``.

    Raises:
        Exception: When the BOM cannot be created.
    """
    bom_type = _BOM_TYPES[params.bom_type]
    template = params.template or _default_bom_template(adapter)
    # SolidWorks does NOT default to the active configuration on an empty
    # string (per the API remarks), so it is resolved explicitly.
    configuration = params.configuration or _active_configuration_name(adapter)

    extension = adapter.currentModel.Extension
    extension = _flag_feature_methods(extension, "IModelDocExtension")
    table = extension.InsertBomTable4(
        template,
        0,  # X placement
        0,  # Y placement
        bom_type,
        configuration,
        False,  # Hidden — keep visible so the feature is inspectable
        0,  # IndentedNumberingType — only used for indented BOMs
        False,  # DetailedCutList
        False,  # DissolvePartLevelRows
    )
    if table is None:
        raise Exception(
            f"Failed to insert BOM table (type {params.bom_type!r}, "
            f"configuration {configuration!r}, template {template!r})"
        )
    contents = _read_bom_table(adapter, table)
    contents["configuration"] = configuration
    contents["bom_type"] = params.bom_type
    return contents


def _create_bom_impl(
    adapter: Any, params: CreateBomParameters
) -> AdapterResult[dict[str, Any]]:
    """Insert a BOM table via ``IModelDocExtension::InsertBomTable4``.

    Args:
        adapter: A fully connected ``PyWin32Adapter``.
        params: BOM type, configuration and template.

    Returns:
        AdapterResult[dict[str, Any]]: Table contents or error.
    """
    if not adapter.currentModel:
        return AdapterResult(status=AdapterResultStatus.ERROR, error="No active model")
    if params.bom_type not in _BOM_TYPES:
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error=f"Unknown bom_type: {params.bom_type!r} "
            f"(expected one of {sorted(_BOM_TYPES)})",
        )

    return cast(
        AdapterResult[dict[str, Any]],
        adapter._handle_com_operation(
            "create_bom", lambda: _insert_bom(adapter, params)
        ),
    )


def _export_bom_csv_impl(
    adapter: Any, params: CreateBomParameters
) -> AdapterResult[dict[str, Any]]:
    """Insert a BOM table and write its contents to a CSV file.

    Args:
        adapter: A fully connected ``PyWin32Adapter``.
        params: BOM options; ``file_path`` is the CSV destination.

    Returns:
        AdapterResult[dict[str, Any]]: Export summary (path, row/column
        counts) or error.
    """
    if not adapter.currentModel:
        return AdapterResult(status=AdapterResultStatus.ERROR, error="No active model")
    if params.bom_type not in _BOM_TYPES:
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error=f"Unknown bom_type: {params.bom_type!r} "
            f"(expected one of {sorted(_BOM_TYPES)})",
        )
    if not params.file_path.strip():
        return AdapterResult(
            status=AdapterResultStatus.ERROR,
            error="file_path is required for export_bom_csv",
        )

    def _export_operation() -> dict[str, Any]:
        contents = _insert_bom(adapter, params)
        path = Path(params.file_path)
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", newline="", encoding="utf-8") as handle:
            writer = csv.writer(handle)
            writer.writerow(contents["header"])
            writer.writerows(contents["data"])
        return {
            "file_path": str(path),
            "rows": contents["rows"],
            "columns": contents["columns"],
            "configuration": contents["configuration"],
        }

    return cast(
        AdapterResult[dict[str, Any]],
        adapter._handle_com_operation("export_bom_csv", _export_operation),
    )
