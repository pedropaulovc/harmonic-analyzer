"""Model I/O mixin for PyWin32 SolidWorks operations."""

from __future__ import annotations

import os
from datetime import datetime
from typing import Any, cast

from .. import sw_type_info as _sw_type_info
from ..base import (
    AdapterResult,
    AdapterResultStatus,
    ImportDxfDwgParameters,
    MassProperties,
    SolidWorksFeature,
    SolidWorksModel,
)
from ..com_variant import null_callout


class SolidWorksIOMixin:
    """Expose model open/save/create/configuration methods through a mixin."""

    @staticmethod
    def _adapter(obj: Any) -> Any:
        """Return the runtime adapter object for dynamic attribute access."""
        return cast(Any, obj)

    @staticmethod
    def _bind_document(model: Any) -> Any:
        """Early-bind a freshly acquired document to ``IModelDoc2``.

        The base interface carries the members call sites invoke directly
        (``GetEquationMgr``, ``GetActiveConfiguration``, ``ClearSelection2``,
        ``Extension`` …); doc-type members (``IPartDoc.GetBodies2``,
        ``IAssemblyDoc.GetComponents``, ``IDrawingDoc`` …) resolve through the
        wrapper's late-bound fallback. Without this, ``currentModel`` is a raw
        dispatch on which a zero-arg method like ``GetEquationMgr()`` resolves
        as a *property* and the direct call raises — the old code masked this by
        flagging the whole document interface on open.
        """
        return _sw_type_info.early_bound(model, "IModelDoc2")

    @staticmethod
    def _is_success(value: Any) -> bool:
        """Interpret SolidWorks save API return values consistently.

        Args:
            value: Return value from ``Save*`` COM calls.

        Returns:
            bool: ``True`` when return value indicates success.
        """
        if isinstance(value, bool):
            return value
        if isinstance(value, (int, float)):
            return value == 0
        return bool(value)

    @staticmethod
    def _unpack_out_result(value: Any) -> tuple[Any, tuple[Any, ...]]:
        """Split a makepy retval/[out] tuple into its two parts.

        Generated pywin32 wrappers return ``(retval, out1, ...)`` for methods
        such as ``OpenDoc6`` and ``Save3``. Scalar compatibility keeps unit
        doubles and wrappers for methods without outputs straightforward.
        """
        if isinstance(value, tuple):
            if not value:
                return None, ()
            return value[0], value[1:]
        return value, ()

    def _resolve_template_path(
        self, preferred_indices: list[int], extension: str
    ) -> str | None:
        """Resolve a template path from SolidWorks user preference slots.

        Args:
            preferred_indices: Preference indices to probe in order.
            extension: Expected template extension such as ``.prtdot``.

        Returns:
            str | None: First existing template match, otherwise first non-empty
            path candidate, or ``None`` if nothing is configured.
        """
        adapter = self._adapter(self)
        existing_match: str | None = None
        first_non_empty: str | None = None
        app = adapter.swApp
        if app is None:
            return None

        for index in preferred_indices:
            template = adapter._attempt(
                lambda idx=index: app.GetUserPreferenceStringValue(idx)
            )
            if not template or not isinstance(template, str):
                continue
            if first_non_empty is None:
                first_non_empty = template
            if template.lower().endswith(extension.lower()) and os.path.exists(
                template
            ):
                existing_match = template
                break

        return existing_match or first_non_empty

    def _read_model_title(self, model: Any) -> str:
        """Read a model title regardless of COM exposing method or property.

        Args:
            model: SolidWorks model COM object.

        Returns:
            str: Best-effort model title, defaulting to ``"Untitled"``.
        """
        adapter = self._adapter(self)
        title = adapter._attempt(lambda: adapter._get_attr_or_call(model, "GetTitle"))
        if isinstance(title, str) and title:
            return title

        title_value = getattr(model, "Title", None)
        if isinstance(title_value, str) and title_value:
            return title_value

        return "Untitled"

    async def open_model(self, file_path: str) -> AdapterResult[SolidWorksModel]:
        """Open a SolidWorks model file and set it as active on the adapter.

        Args:
            file_path: Path to a ``.sldprt``, ``.sldasm``, or ``.slddrw`` file.

        Returns:
            AdapterResult[SolidWorksModel]: Model metadata for the opened document.
        """
        adapter = self._adapter(self)
        if not adapter.is_connected():
            return AdapterResult(
                status=AdapterResultStatus.ERROR, error="Not connected to SolidWorks"
            )

        def _open() -> SolidWorksModel:
            """Open the model document."""
            resolved_path = os.path.abspath(file_path)
            file_path_lower = resolved_path.lower()
            if file_path_lower.endswith(".sldprt"):
                doc_type = adapter.constants["swDocPART"]
                model_type = "Part"
            elif file_path_lower.endswith(".sldasm"):
                doc_type = adapter.constants["swDocASSEMBLY"]
                model_type = "Assembly"
            elif file_path_lower.endswith(".slddrw"):
                doc_type = adapter.constants["swDocDRAWING"]
                model_type = "Drawing"
            else:
                raise ValueError(f"Unsupported file type: {resolved_path}")

            app = adapter.swApp
            open_result = app.OpenDoc6(resolved_path, doc_type, 1, "", 0, 0)
            # makepy returns the retval followed by OpenDoc6's two [out]
            # integers.  Retain the scalar form for compatible test doubles and
            # old wrappers while every real session now acquires ISldWorks via
            # EnsureDispatch.
            model, open_outs = self._unpack_out_result(open_result)
            open_errors = int(open_outs[0]) if len(open_outs) > 0 else 0
            open_warnings = int(open_outs[1]) if len(open_outs) > 1 else 0
            if not model:
                raise Exception(
                    f"Failed to open model: {resolved_path} "
                    f"(errors={open_errors}, warnings={open_warnings})"
                )

            model = self._bind_document(model)
            adapter.currentModel = model
            title = self._read_model_title(model)
            active_config = adapter._attempt(lambda: model.GetActiveConfiguration())
            config = (
                adapter._attempt(lambda: active_config.GetName(), default="Default")
                if active_config
                else "Default"
            )

            return SolidWorksModel(
                path=resolved_path,
                name=title,
                type=model_type,
                is_active=True,
                configuration=config,
                properties={
                    # swSumInfoSaveDate2 (9). ``GetSaveTime`` is absent from the
                    # makepy wrapper's name table (not early-bindable); ``SummaryInfo``
                    # is a declared ``IModelDoc2`` method returning the localized
                    # last-saved date string.
                    "last_modified": adapter._attempt(
                        lambda: model.SummaryInfo(9), default=None
                    ),
                },
            )

        return cast(
            AdapterResult[SolidWorksModel],
            adapter._handle_com_operation("open_model", _open),
        )

    async def close_model(self, save: bool = False) -> AdapterResult[None]:
        """Close the current SolidWorks model and optionally save first.

        Args:
            save: When ``True``, calls ``Save`` before closing.

        Returns:
            AdapterResult[None]: Result of the close operation.
        """
        adapter = self._adapter(self)
        if not adapter.currentModel:
            return AdapterResult(
                status=AdapterResultStatus.WARNING, error="No active model to close"
            )
        model = adapter.currentModel
        app = adapter.swApp
        if model is None or app is None:
            return AdapterResult(
                status=AdapterResultStatus.ERROR,
                error="SolidWorks application is not connected",
            )

        def _close() -> None:
            """Close the model document."""
            if save:
                model.Save()
            app.CloseDoc(model.GetTitle())
            adapter.currentModel = None

        return cast(
            AdapterResult[None],
            adapter._handle_com_operation("close_model", _close),
        )

    async def create_part(
        self, name: str | None = None, units: str | None = None
    ) -> AdapterResult[SolidWorksModel]:
        """Create a new part document and set it as active.

        Args:
            name: Reserved for future naming policy.
            units: Reserved for future units policy.

        Returns:
            AdapterResult[SolidWorksModel]: Metadata for the new part document.
        """
        adapter = self._adapter(self)
        if not adapter.is_connected():
            return AdapterResult(
                status=AdapterResultStatus.ERROR, error="Not connected to SolidWorks"
            )

        def _create() -> SolidWorksModel:
            """Create a new part."""
            _ = name, units
            model = None
            app = adapter.swApp
            if app is None:
                raise Exception("SolidWorks application is not connected")

            new_part = getattr(app, "NewPart", None)
            if callable(new_part):
                model = adapter._attempt(new_part)

            if not model:
                part_template = self._resolve_template_path([8, 0, 1, 2, 3], ".prtdot")
                if not part_template:
                    raise Exception("No part template configured in SolidWorks")
                model = app.NewDocument(part_template, 0, 0, 0)

            if not model:
                raise Exception("Failed to create new part")

            model = self._bind_document(model)
            adapter.currentModel = model
            title = self._read_model_title(model)
            return SolidWorksModel(
                path="",
                name=title,
                type="Part",
                is_active=True,
                configuration="Default",
                properties={"created": datetime.now().isoformat()},
            )

        return cast(
            AdapterResult[SolidWorksModel],
            adapter._handle_com_operation("create_part", _create),
        )

    async def create_assembly(
        self, name: str | None = None
    ) -> AdapterResult[SolidWorksModel]:
        """Create a new assembly document and set it as active.

        Args:
            name: Reserved for future naming policy.

        Returns:
            AdapterResult[SolidWorksModel]: Metadata for the new assembly document.
        """
        adapter = self._adapter(self)
        if not adapter.is_connected():
            return AdapterResult(
                status=AdapterResultStatus.ERROR, error="Not connected to SolidWorks"
            )

        def _create() -> SolidWorksModel:
            """Create a new assembly."""
            _ = name
            model = None
            app = adapter.swApp
            if app is None:
                raise Exception("SolidWorks application is not connected")

            new_assembly = getattr(app, "NewAssembly", None)
            if callable(new_assembly):
                model = adapter._attempt(new_assembly)

            if not model:
                asm_template = self._resolve_template_path([9, 2, 3, 1, 0], ".asmdot")
                if not asm_template:
                    raise Exception("No assembly template configured in SolidWorks")
                model = app.NewDocument(asm_template, 0, 0, 0)

            if not model:
                raise Exception("Failed to create new assembly")

            model = self._bind_document(model)
            adapter.currentModel = model
            title = self._read_model_title(model)
            return SolidWorksModel(
                path="",
                name=title,
                type="Assembly",
                is_active=True,
                configuration="Default",
                properties={"created": datetime.now().isoformat()},
            )

        return cast(
            AdapterResult[SolidWorksModel],
            adapter._handle_com_operation("create_assembly", _create),
        )

    async def create_drawing(
        self, name: str | None = None
    ) -> AdapterResult[SolidWorksModel]:
        """Create a new drawing document and set it as active.

        Args:
            name: Reserved for future naming policy.

        Returns:
            AdapterResult[SolidWorksModel]: Metadata for the new drawing document.
        """
        adapter = self._adapter(self)
        if not adapter.is_connected():
            return AdapterResult(
                status=AdapterResultStatus.ERROR, error="Not connected to SolidWorks"
            )

        def _create() -> SolidWorksModel:
            """Create a new drawing."""
            _ = name
            app = adapter.swApp
            if app is None:
                raise Exception("SolidWorks application is not connected")

            drw_template = app.GetUserPreferenceStringValue(1)
            if not drw_template:
                drw_template = app.GetUserPreferenceStringValue(0).replace(
                    "Part", "Drawing"
                )

            model = app.NewDocument(drw_template, 12, 0.2794, 0.2159)
            if not model:
                raise Exception("Failed to create new drawing")

            model = self._bind_document(model)
            adapter.currentModel = model
            title = self._read_model_title(model)
            return SolidWorksModel(
                path="",
                name=title,
                type="Drawing",
                is_active=True,
                configuration="Default",
                properties={"created": datetime.now().isoformat()},
            )

        return cast(
            AdapterResult[SolidWorksModel],
            adapter._handle_com_operation("create_drawing", _create),
        )

    async def import_dxf_dwg(
        self, params: ImportDxfDwgParameters
    ) -> AdapterResult[SolidWorksFeature]:
        """Import a DXF/DWG file into the active part as a sketch feature.

        Selects ``params.plane``, obtains an ``IImportDxfDwgData`` from
        ``ISldWorks::GetImportFileData``, configures it (import-to-existing-part,
        millimetre units, position/scale, merge points, hatch/dimension/relation
        toggles), then inserts the geometry via
        ``IFeatureManager::InsertDwgOrDxfFile2``. The returned feature's
        ``GetSpecificFeature2`` is the imported sketch, which callers cut.

        Positioning/scaling notes:
          * ``SetPosition("", swDwgEntitiesCentered, X, Y)`` centres the imported
            geometry then offsets it by ``(X, Y)`` metres.
          * ``SetSheetScale("", num, den)`` scales by ``num/den``; ``params.scale``
            is passed as ``(scale, 1.0)``.
          * ``LengthUnit``/``ImportMethod``/``ImportHatch``/``ImportDimensions``/
            ``AddSketchConstraints`` are indexed properties. The generated
            ``IImportDxfDwgData`` wrapper exposes their typed ``Set*`` accessors.

        Args:
            params: DXF/DWG import parameter bag.

        Returns:
            AdapterResult[SolidWorksFeature]: On success, ``data`` describes the
            inserted DXF/DWG feature (``type`` ``"ImportedDxfDwg"``).
        """
        adapter = self._adapter(self)
        if not adapter.currentModel:
            return AdapterResult(
                status=AdapterResultStatus.ERROR, error="No active model"
            )
        if not os.path.isfile(params.file_path):
            return AdapterResult(
                status=AdapterResultStatus.ERROR,
                error=f"DXF/DWG file not found: {params.file_path}",
            )

        def _import() -> SolidWorksFeature:
            app = adapter.swApp
            model = adapter.currentModel
            if app is None:
                raise Exception("SolidWorks application is not connected")

            # Select the placement plane (English name -> full SW plane name),
            # mirroring create_sketch's resolution + SelectByID2 fallback.
            plane_name_map = {
                "Top": "Top Plane",
                "Front": "Front Plane",
                "Right": "Right Plane",
                "XY": "Top Plane",
                "XZ": "Front Plane",
                "YZ": "Right Plane",
            }
            actual_plane = plane_name_map.get(params.plane, params.plane)
            selected = False
            plane_feature = adapter._attempt(
                lambda: _sw_type_info.early_bound_doc(model).FeatureByName(actual_plane),
                default=None,
            )
            if plane_feature:
                selected = bool(
                    adapter._attempt(
                        lambda pf=plane_feature: pf.Select2(False, 0), default=False
                    )
                )
            if not selected:
                selected = bool(
                    adapter._attempt(
                        lambda: model.Extension.SelectByID2(
                            actual_plane, "PLANE", 0, 0, 0, False, 0, null_callout(), 0
                        ),
                        default=False,
                    )
                )
            if not selected:
                raise Exception(f"Failed to select plane for DXF import: {actual_plane}")

            import_data = app.GetImportFileData(params.file_path)
            if import_data is None:
                raise Exception(
                    f"GetImportFileData returned None for {params.file_path}"
                )

            import_data = _sw_type_info.early_bound(
                import_data, "IImportDxfDwgData"
            )

            # swImportDxfDwg_ImportToExistingPart = 4; swMM = 0 (swLengthUnit_e).
            import_data.SetImportMethod("", 4)
            import_data.SetLengthUnit("", 0)
            import_data.SetImportHatch("", bool(params.import_hatch))
            import_data.SetImportDimensions("", bool(params.import_dimensions))
            import_data.SetAddSketchConstraints("", bool(params.add_constraints))

            # Position/scale are METHODS (no indexed-property marshalling needed).
            # swDwgImportEntitiesPositioning_e.swDwgEntitiesSpecifyPosition = 2:
            # the (X, Y) is the absolute location the imported geometry's ORIGIN
            # lands at (NOT a bbox-centred offset -- swDwgEntitiesCentered is 1);
            # callers that want the artwork centred pass an origin offset computed
            # from the file's bbox (see build_nameplate.ENGRAVING_POSITION).
            px, py = (params.position or [0.0, 0.0])[:2]
            adapter._attempt(
                lambda: import_data.SetPosition(
                    "", 2, float(px) / 1000.0, float(py) / 1000.0
                ),
                default=False,
            )
            if params.scale is not None:
                adapter._attempt(
                    lambda: import_data.SetSheetScale("", float(params.scale), 1.0),
                    default=False,
                )
            if params.merge_points:
                adapter._attempt(
                    lambda: import_data.SetMergePoints(
                        "", True, float(params.merge_distance) / 1000.0
                    ),
                    default=False,
                )

            feature = model.FeatureManager.InsertDwgOrDxfFile2(
                params.file_path, import_data
            )
            if feature is None:
                # Documented: returns null if the file contains solid-body data,
                # or when no planar face/plane was selected.
                raise Exception(
                    "InsertDwgOrDxfFile2 returned None (unsupported file contents "
                    "or no planar selection)"
                )

            name = adapter._attempt(lambda: feature.Name, default="") or "ImportedDxfDwg"
            adapter._attempt(lambda: model.ClearSelection2(True))
            return SolidWorksFeature(
                id=name,
                name=name,
                type="ImportedDxfDwg",
                parameters={
                    "file_path": params.file_path,
                    "plane": actual_plane,
                    "scale": params.scale,
                    "position": params.position,
                },
                properties={"created": datetime.now().isoformat()},
            )

        return cast(
            AdapterResult[SolidWorksFeature],
            adapter._handle_com_operation("import_dxf_dwg", _import),
        )

    async def get_dimension(self, name: str) -> AdapterResult[float]:
        """Read a named model dimension in millimetres.

        Args:
            name: Fully-qualified dimension name.

        Returns:
            AdapterResult[float]: Dimension value in millimetres.
        """
        adapter = self._adapter(self)
        if not adapter.currentModel:
            return AdapterResult(
                status=AdapterResultStatus.ERROR, error="No active model"
            )

        def _get() -> float:
            """Get the dimension value."""
            dimension = adapter.currentModel.Parameter(name)
            if not dimension:
                raise Exception(f"Dimension '{name}' not found")
            # SystemValue is reliable on SW 2025 (in meters, convert to mm)
            value = adapter._attempt(
                lambda: dimension.SystemValue, default=None
            )
            if value is None:
                # Fall back to GetValue3 for older SW versions
                value = adapter._attempt(
                    lambda: dimension.GetValue3(0, 0), default=None
                )
            if value is None:
                raise Exception(f"Failed to read dimension '{name}'")
            return cast(float, float(value) * 1000)

        return cast(
            AdapterResult[float],
            adapter._handle_com_operation("get_dimension", _get),
        )

    async def set_dimension(self, name: str, value: float) -> AdapterResult[None]:
        """Set a named model dimension in millimetres and rebuild.

        Args:
            name: Fully-qualified dimension name.
            value: New value in millimetres.

        Returns:
            AdapterResult[None]: Result of the set operation.
        """
        adapter = self._adapter(self)
        if not adapter.currentModel:
            return AdapterResult(
                status=AdapterResultStatus.ERROR, error="No active model"
            )

        def _set() -> None:
            """Set the dimension value."""
            dimension = adapter.currentModel.Parameter(name)
            if not dimension:
                raise Exception(f"Dimension '{name}' not found")

            # SetValue3 has gen_py parameter mapping issues on SW 2025.
            # SystemValue (in meters) is reliable.
            value_m = value / 1000.0
            adapter._attempt(
                lambda: setattr(dimension, "SystemValue", value_m),
                default=None,
            )

            # Rebuild: try EditRebuild3 first, fall back to ForceRebuild3
            rebuilt = adapter._attempt(
                lambda: adapter.currentModel.EditRebuild3(), default=None
            )
            if rebuilt is None:
                rebuilt = adapter._attempt(
                    lambda: adapter.currentModel.ForceRebuild3(True), default=None
                )
            if rebuilt is None:
                raise Exception("Failed to set dimension")

        return cast(
            AdapterResult[None],
            adapter._handle_com_operation("set_dimension", _set),
        )

    async def save_file(self, file_path: str | None = None) -> AdapterResult[None]:
        """Save the active model to its current path or to a new file path.

        Args:
            file_path: Optional target path for Save As.

        Returns:
            AdapterResult[None]: Result of the save operation.
        """
        adapter = self._adapter(self)
        if not adapter.currentModel:
            return AdapterResult(
                status=AdapterResultStatus.ERROR, error="No active model"
            )

        def _active_path() -> str:
            """Absolute on-disk path of the active doc, or ``""`` if unsaved."""
            path_attr = getattr(adapter.currentModel, "GetPathName", "")
            model_path = path_attr() if callable(path_attr) else path_attr
            return os.path.abspath(model_path) if model_path else ""

        def _silent_save_in_place() -> bool:
            """Save the active doc to its own path with a silent ``Save3``.

            ``swSaveAsOptions_Silent (1) | swSaveAsOptions_AvoidRebuildOnSave (8)``.
            The generated wrapper marshals the ``Errors``/``Warnings`` outputs
            and returns ``(success, errors, warnings)``; passing bare ``None``
            would fail the COM call and risk a blocking fallback save dialog.
            (``8`` is ``AvoidRebuildOnSave`` per the canonical
            ``swSaveAsOptions_e`` bitmask -- ``SaveReferenced`` is ``4`` -- so this
            saves only the active doc and skips a redundant save-time rebuild; it
            was historically mislabeled "SaveReferenced (8)".)
            """
            save_result = adapter._attempt(
                lambda: adapter.currentModel.Save3(1 | 8, 0, 0),
                default=False,
            )
            retval, _outs = self._unpack_out_result(save_result)
            return self._is_success(retval)

        def _save() -> None:
            """Save the model in place, or Save-As to a different path."""
            if file_path:
                resolved_path = os.path.abspath(file_path)

                # Saving the active doc to the path it was opened from is an
                # in-place save, NOT a Save-As: never CloseDoc/os.remove the doc
                # being saved (that disconnects it and deletes the file). Use
                # the silent in-place Save3 instead.
                if os.path.normcase(resolved_path) == os.path.normcase(_active_path()):
                    if _silent_save_in_place() and os.path.exists(resolved_path):
                        return
                    raise Exception(f"Failed to save in place: {resolved_path}")

                os.makedirs(os.path.dirname(resolved_path), exist_ok=True)

                # True Save-As to a different path: clear any stale target file
                # so SaveAs3 can write it. Safe because resolved_path is not the
                # active document.
                if adapter.swApp:
                    adapter._attempt(lambda: adapter.swApp.CloseDoc(resolved_path))
                if os.path.exists(resolved_path):
                    adapter._attempt(lambda: os.remove(resolved_path))

                save_as3_result = adapter.currentModel.SaveAs3(resolved_path, 0, 0)
                if not self._is_success(save_as3_result):
                    save_as = getattr(adapter.currentModel, "SaveAs", None)
                    if callable(save_as):
                        fallback_result = save_as(resolved_path)
                        if not self._is_success(fallback_result):
                            raise Exception(f"Failed to save as: {resolved_path}")
                    else:
                        raise Exception(f"Failed to save as: {resolved_path}")

                if not os.path.exists(resolved_path):
                    raise Exception(f"File not written after save: {resolved_path}")
                return

            # No path: silent in-place save of the active document.
            if _silent_save_in_place():
                return
            active = _active_path()
            if active and os.path.exists(active):
                return
            raise Exception("Failed to save file")

        return cast(
            AdapterResult[None],
            adapter._handle_com_operation("save_file", _save),
        )

    async def rebuild_model(self) -> AdapterResult[None]:
        """Force a model rebuild.

        Returns:
            AdapterResult[None]: Result of the rebuild operation.
        """
        adapter = self._adapter(self)
        if not adapter.currentModel:
            return AdapterResult(
                status=AdapterResultStatus.ERROR, error="No active model"
            )

        def _rebuild() -> None:
            """Rebuild the model."""
            success = adapter.currentModel.ForceRebuild3(False)
            if not success:
                raise Exception("Failed to rebuild model")

        return cast(
            AdapterResult[None],
            adapter._handle_com_operation("rebuild_model", _rebuild),
        )

    async def get_model_info(self) -> AdapterResult[dict[str, Any]]:
        """Collect summary metadata about the active model.

        Returns:
            AdapterResult[dict[str, Any]]: Model information payload.
        """
        adapter = self._adapter(self)
        if not adapter.currentModel:
            return AdapterResult(
                status=AdapterResultStatus.ERROR, error="No active model"
            )

        def _get_info() -> dict[str, Any]:
            """Get model information."""
            active_config = adapter.currentModel.GetActiveConfiguration()
            # 'Name' on Configuration is a property, not a method.
            config_name = getattr(active_config, "Name", "Default") if active_config else "Default"
            # Try GetSaveFlag (method) first, fallback to property
            is_dirty_raw = adapter._attempt(
                lambda: adapter.currentModel.GetSaveFlag(), default=None
            )
            is_dirty = bool(is_dirty_raw) if is_dirty_raw is not None else None
            feature_count = adapter._attempt(
                lambda: int(adapter.currentModel.FeatureManager.GetFeatureCount(True) or 0),
                default=0,
            )
            rebuild_status_raw = adapter._attempt(
                lambda: adapter.currentModel.GetRebuildStatus(), default=None
            )
            # GetRebuildStatus returns 0=ok, 1=needs rebuild, or None=failed
            rebuild_status = rebuild_status_raw if rebuild_status_raw is not None else None
            return {
                "title": adapter.currentModel.GetTitle(),
                "path": adapter.currentModel.GetPathName(),
                "type": adapter._get_document_type(),
                "configuration": config_name,
                "is_dirty": is_dirty,
                "feature_count": feature_count,
                "rebuild_status": rebuild_status,
            }

        return cast(
            AdapterResult[dict[str, Any]],
            adapter._handle_com_operation("get_model_info", _get_info),
        )

    async def list_configurations(self) -> AdapterResult[list[str]]:
        """List all configuration names on the active model.

        Returns:
            AdapterResult[list[str]]: Configuration names, or empty list when unavailable.
        """
        adapter = self._adapter(self)
        if not adapter.currentModel:
            return AdapterResult(
                status=AdapterResultStatus.ERROR,
                error="No active model",
            )

        def _list() -> list[str]:
            """List configurations."""
            raw_names = getattr(adapter.currentModel, "GetConfigurationNames", None)
            names = raw_names() if callable(raw_names) else raw_names
            if names is None:
                names = []
            if isinstance(names, str):
                return [names]

            normalized_names = [str(name) for name in names]
            if normalized_names:
                return normalized_names

            active_config = adapter._attempt(
                lambda: adapter.currentModel.GetActiveConfiguration(), default=None
            )
            active_name = adapter._attempt(
                lambda: active_config.GetName(), default=None
            )
            if active_name:
                return [str(active_name)]
            return []

        return cast(
            AdapterResult[list[str]],
            adapter._handle_com_operation("list_configurations", _list),
        )

    async def get_mass_properties(self) -> AdapterResult[MassProperties]:
        """Get mass properties for the active model.

        Returns:
            AdapterResult[MassProperties]: Computed mass, volume, area, COM, and inertia.
        """
        adapter = self._adapter(self)
        if not adapter.currentModel:
            return AdapterResult(
                status=AdapterResultStatus.ERROR, error="No active model"
            )

        def _get() -> MassProperties:
            """Get mass properties."""
            adapter._attempt(
                lambda: adapter.currentModel.ForceRebuild3(False), default=None
            )

            # Primary: Extension.CreateMassProperty() object API (most detailed)
            mass_props = adapter._attempt(
                lambda: adapter.currentModel.Extension.CreateMassProperty(),
                default=None,
            )

            if mass_props:
                volume = mass_props.Volume * 1e9
                surface_area = mass_props.SurfaceArea * 1e6
                mass = mass_props.Mass

                center_of_mass = [0.0, 0.0, 0.0]
                com = adapter._attempt(lambda: mass_props.CenterOfMass, default=None)
                if isinstance(com, (list, tuple)) and len(com) >= 3:
                    center_of_mass = [com[0] * 1000, com[1] * 1000, com[2] * 1000]

                moi = adapter._attempt(
                    lambda: mass_props.GetMomentOfInertia(0), default=None
                )
                if not isinstance(moi, (list, tuple)) or len(moi) < 9:
                    moi = [0.0] * 9
            else:
                # Fallback: GetMassProperties as attribute (tuple) or callable (SW 2022)
                gmp = getattr(adapter.currentModel, "GetMassProperties", None)
                if callable(gmp):
                    raw = adapter._attempt(gmp, default=None)
                elif isinstance(gmp, (list, tuple)):
                    raw = gmp
                else:
                    raw = None

                if not isinstance(raw, (list, tuple)) or len(raw) < 6:
                    raise Exception("Failed to get mass properties")

                center_of_mass = [
                    raw[0] * 1000.0,
                    raw[1] * 1000.0,
                    raw[2] * 1000.0,
                ]
                volume = raw[3] * 1e9
                surface_area = raw[4] * 1e6
                mass = raw[5]

                moi = [0.0] * 9
                if len(raw) >= 12:
                    moi[0] = raw[6]
                    moi[4] = raw[7]
                    moi[8] = raw[8]
                    moi[1] = raw[9]
                    moi[5] = raw[10]
                    moi[2] = raw[11]

            return MassProperties(
                volume=volume,
                surface_area=surface_area,
                mass=mass,
                center_of_mass=center_of_mass,
                moments_of_inertia={
                    "Ixx": moi[0],
                    "Iyy": moi[4],
                    "Izz": moi[8],
                    "Ixy": moi[1],
                    "Ixz": moi[2],
                    "Iyz": moi[5],
                },
            )

        return cast(
            AdapterResult[MassProperties],
            adapter._handle_com_operation("get_mass_properties", _get),
        )
