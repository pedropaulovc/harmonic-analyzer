"""Declared source-model-dimension coverage; never fabricated geometry coverage.

GetDimension2 returns the underlying model parameter even when an annotation has
no geometry array. GetAttachedEntities3 also supports sketch segments (type 10),
which the generic geometry reader deliberately does not measure. This contract
proves exact source parameters instead; it makes no sketch-geometry/PID claim.

https://help.solidworks.com/2026/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IDisplayDimension~GetDimension2.html
https://help.solidworks.com/2026/english/api/sldworksapi/SolidWorks.Interop.sldworks~SolidWorks.Interop.sldworks.IAnnotation~GetAttachedEntities3.html
"""

from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path
import sys
from types import SimpleNamespace

from _common import _early_bound
from _drawing_marks import _named_dimension
import _telemetry
from diagnostics import _source_dimension_snapshot as source_reads
from diagnostics import probe_drawing_attachments as attachments


class SemanticCoverage(StrEnum):
    GEOMETRY = "geometry"
    MODEL_DIMENSIONS_ONLY = "model_dimensions_only"


@dataclass(frozen=True)
class ModelDimensionRole:
    feature: str
    name: str
    orientation: str
    display_type: int
    attachments: tuple[int, ...]
    printed: tuple[str, ...] = ()

    @property
    def key(self):
        return f"{self.name}@{self.feature}"


def _same(app, expected, actual, label):
    if expected is None or actual is None or app.IsSame(expected, actual) != 1:
        raise RuntimeError(f"model-dimension coverage {label}: native identity differs")


def _parameter(dimension, configuration):
    values = tuple(dimension.GetSystemValue3(3, configuration) or ())
    if len(values) != 1:
        raise RuntimeError("model-dimension coverage requires one configured value")
    tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
    return {
        "name": str(dimension.Name),
        "full_name": str(dimension.FullName),
        "parameter_type": int(dimension.GetType()),
        "value_system": source_reads.finite(values[0]),
        **source_reads.tolerance(dimension),
        **source_reads.tolerance_limits(tolerance),
    }


def _presentation(display):
    row = source_reads.display_presentation(display)
    if "exclusion" in row["text"]:
        raise RuntimeError("model-dimension coverage does not support hole callouts")
    return {
        **row,
        "primary_precision": int(display.GetPrimaryPrecision2()),
        "tolerance_precision": int(display.GetPrimaryTolPrecision2()),
    }


class ModelDimensionCoverage:
    def __init__(self, adapter, manifest, source_model, path, trial):
        required = {
            f"{name}@{feature}"
            for feature, names in manifest.dimensions.items()
            for name in names
        }
        roles = {role.key: role for role in manifest.model_dimensions}
        if (
            manifest.coverage is not SemanticCoverage.MODEL_DIMENSIONS_ONLY
            or manifest.entity_labels
            or manifest.view_roles
            or manifest.basic
            or not roles
            or len(roles) != len(manifest.model_dimensions)
            or roles.keys() != required
            or not manifest.model_views
            or len(set(manifest.model_views)) != len(manifest.model_views)
            or any(
                role.orientation not in manifest.model_views for role in roles.values()
            )
        ):
            raise ValueError(
                "dimension-only policy requires a complete non-geometric manifest"
            )
        self.adapter, self.path, self.roles = adapter, Path(path).resolve(), roles
        self.views = manifest.model_views
        self.record = trial["model_dimension_coverage"] = {
            "policy": manifest.coverage.value,
            "captures": [],
            "roles": {
                key: {
                    "orientation": role.orientation,
                    "display_type": role.display_type,
                    "attachments": role.attachments,
                    "printed": role.printed,
                }
                for key, role in roles.items()
            },
        }
        adapter.ownership.assert_current_owned()
        _same(adapter.swApp, source_model, adapter.currentModel, "initial owned source")
        self.configuration = str(
            _early_bound(
                _early_bound(
                    source_model.ConfigurationManager, "IConfigurationManager"
                ).ActiveConfiguration,
                "IConfiguration",
            ).Name
        )
        if not self.configuration:
            raise RuntimeError("model-dimension coverage source configuration is empty")
        initial = self.record["initial_source_read"] = {
            "dirty_before": source_model.GetSaveFlag()
        }
        try:
            self.source_before, self.live_handles = self._source(adapter, source_model)
        except BaseException as error:
            initial["error"] = repr(error)
            raise
        finally:
            primary = sys.exception()
            try:
                initial["dirty_after"] = source_model.GetSaveFlag()
                adapter.ownership.assert_current_owned()
                _same(
                    adapter.swApp,
                    source_model,
                    adapter.currentModel,
                    "initial final source",
                )
                if initial["dirty_before"] != initial["dirty_after"]:
                    raise RuntimeError(
                        "initial model-dimension source read changed dirty state"
                    )
            except BaseException as guard_error:
                initial["guard_error"] = repr(guard_error)
                if primary is None:
                    raise
                primary.add_note(
                    f"initial model-dimension source guard: {guard_error!r}"
                )
        trial["model_dimension_source_before"] = self.source_before
        adapter.ownership.assert_current_owned()

    @_telemetry.traced("diagnostic.model_dimension_coverage.source")
    def _source(self, adapter, model):
        app = adapter.swApp
        model = _early_bound(model, "IModelDoc2")
        if (
            model is None
            or model.GetType() != 1
            or Path(model.GetPathName()).resolve() != self.path
        ):
            raise RuntimeError("model-dimension coverage needs the exact source PART")
        _same(
            app, model, app.GetOpenDocumentByName(str(self.path)), "source path lookup"
        )
        configuration = str(
            _early_bound(
                _early_bound(
                    model.ConfigurationManager, "IConfigurationManager"
                ).ActiveConfiguration,
                "IConfiguration",
            ).Name
        )
        if configuration != self.configuration:
            raise RuntimeError("model-dimension coverage source configuration changed")
        dirty = model.GetSaveFlag()
        rows, handles = {}, {}
        for key, role in self.roles.items():
            display, dimension = _named_dimension(
                SimpleNamespace(currentModel=model), role.feature, role.name
            )
            display = _early_bound(display, "IDisplayDimension")
            dimension = _early_bound(dimension, "IDimension")
            if display.Type2 != role.display_type:
                raise RuntimeError(f"{key}: source display kind differs")
            _same(app, model.Parameter(key), dimension, f"{key} named source parameter")
            _same(app, display.GetDimension2(0), dimension, f"{key} source display")
            native = _parameter(dimension, configuration)
            if (
                native["name"] != role.name
                or native["full_name"] != f"{key}@{self.path.stem}.Part"
            ):
                raise RuntimeError(
                    f"{key}: source parameter name/feature/model differs"
                )
            rows[key] = {"native": native, "presentation": _presentation(display)}
            handles[key] = dimension
        if model.GetSaveFlag() != dirty:
            raise RuntimeError(
                "model-dimension coverage source read changed dirty state"
            )
        _same(
            app,
            model,
            app.GetOpenDocumentByName(str(self.path)),
            "final source path lookup",
        )
        return {"configuration": configuration, "dimensions": rows}, handles

    @_telemetry.traced("diagnostic.model_dimension_coverage.drawing")
    def capture(self, adapter, *, source, configuration):
        if (
            adapter is not self.adapter
            or Path(source).resolve() != self.path
            or configuration != self.configuration
        ):
            raise RuntimeError("model-dimension coverage context changed")
        adapter.ownership.assert_current_owned()
        app, model = adapter.swApp, _early_bound(adapter.currentModel, "IModelDoc2")
        if model is None or model.GetType() != 3:
            raise RuntimeError("model-dimension coverage requires the owned DRAWING")
        _same(app, model, app.ActiveDoc, "active drawing")
        source_model = _early_bound(
            app.GetOpenDocumentByName(str(self.path)), "IModelDoc2"
        )
        if source_model is None:
            raise RuntimeError("model-dimension coverage source is not open")
        observation = {
            "source_dirty_before": source_model.GetSaveFlag(),
            "drawing_dirty_before": model.GetSaveFlag(),
        }
        self.record["captures"].append(observation)
        try:
            source_bank, handles = self._source(adapter, source_model)
            observation["source"] = source_bank
            if source_bank != self.source_before:
                raise RuntimeError("model-dimension coverage raw source bank changed")
            for key, old in self.live_handles.items():
                _same(app, old, handles[key], f"{key} live source parameter")
            # These handles have no authority beyond this built capture.
            self.live_handles = {}
            rows, orientations = {}, []

            def observe(view_key, view, inventory):
                _same(app, source_model, view.ReferencedDocument, "view source")
                if view.ReferencedConfiguration != configuration:
                    raise RuntimeError(
                        "model-dimension coverage view configuration changed"
                    )
                orientation = str(view.GetOrientationName())
                orientations.append(orientation)
                for annotation in inventory:
                    if (
                        annotation.GetType() == 6
                    ):  # Ordinary notes remain in the full ink bank.
                        if (
                            annotation.GetAttachedEntities3()
                            or annotation.GetAttachedEntityTypes()
                            or annotation.GetAttachedEntityCount3() != 0
                        ):
                            raise RuntimeError(
                                "dimension-only policy found an unexpected attached note role"
                            )
                        continue
                    if annotation.GetType() != 4:
                        raise RuntimeError(
                            "dimension-only policy found an unexpected geometry annotation role"
                        )
                    display = _early_bound(
                        annotation.GetSpecificAnnotation(), "IDisplayDimension"
                    )
                    dimension = _early_bound(display.GetDimension2(0), "IDimension")
                    key = str(dimension.FullName).rsplit("@", 1)[0]
                    if key not in self.roles or key in rows:
                        raise RuntimeError(
                            "model-dimension coverage dimension inventory differs"
                        )
                    role = self.roles[key]
                    if (
                        annotation.OwnerType != 0
                        or annotation.Visible != 1
                        or annotation.IsDangling() is not False
                        or display.IsReferenceDim() is not False
                        or display.Type2 != role.display_type
                        or orientation != role.orientation
                    ):
                        raise RuntimeError(
                            f"{key}: model dimension kind/visibility/view differs"
                        )
                    _same(app, view, annotation.Owner, f"{key} annotation owner")
                    _same(
                        app,
                        annotation,
                        display.GetAnnotation(),
                        f"{key} display roundtrip",
                    )
                    _same(
                        app, handles[key], dimension, f"{key} imported source parameter"
                    )
                    entities = tuple(annotation.GetAttachedEntities3() or ())
                    kinds = tuple(annotation.GetAttachedEntityTypes() or ())
                    if (
                        kinds != role.attachments
                        or len(entities) != len(kinds)
                        or annotation.GetAttachedEntityCount3() != len(kinds)
                        or any(entity is None for entity in entities)
                    ):
                        raise RuntimeError(
                            f"{key}: model dimension raw attachments differ"
                        )
                    native, presentation = (
                        _parameter(dimension, configuration),
                        _presentation(display),
                    )
                    expected = source_bank["dimensions"][key]
                    if native != expected["native"] or any(
                        presentation[field] != expected["presentation"][field]
                        for field in ("text", "show_dimension_value")
                    ):
                        raise RuntimeError(
                            f"{key}: imported raw parameter/presentation differs from source"
                        )
                    rows[key] = {
                        "view": view_key,
                        "orientation": orientation,
                        "annotation_key": f"{view.GetName2()}/{annotation.GetName()}",
                        "native": native,
                        "presentation": presentation,
                        "attachment_types": kinds,
                    }

            semantics = attachments.snapshot(model, app=app, view_observer=observe)
            observation["dimensions"] = rows
            if (
                rows.keys() != self.roles.keys()
                or semantics["dimensions_excluded"]
                or len(semantics["dimensions"]) != len(self.roles)
                or semantics["checked"]
                or semantics["semantic_attachments"]
                or sorted(orientations) != sorted(self.views)
            ):
                raise RuntimeError("dimension-only coverage inventory is not complete")
            return semantics, {"source": source_bank, "dimensions": rows}
        except BaseException as error:
            observation["error"] = repr(error)
            raise
        finally:
            primary = sys.exception()
            try:
                observation["source_dirty_after"] = source_model.GetSaveFlag()
                observation["drawing_dirty_after"] = model.GetSaveFlag()
                if (
                    observation["source_dirty_before"]
                    != observation["source_dirty_after"]
                    or observation["drawing_dirty_before"]
                    != observation["drawing_dirty_after"]
                ):
                    raise RuntimeError(
                        "model-dimension coverage read changed dirty flags"
                    )
                adapter.ownership.assert_current_owned()
                _same(app, model, adapter.currentModel, "final current drawing")
                _same(app, model, app.ActiveDoc, "final active drawing")
                _same(
                    app,
                    source_model,
                    app.GetOpenDocumentByName(str(self.path)),
                    "final source",
                )
            except BaseException as guard_error:
                observation["guard_error"] = repr(guard_error)
                if primary is None:
                    raise
                primary.add_note(f"model-dimension final guard: {guard_error!r}")

    def require_printed(self, annotations, bank):
        for key, role in self.roles.items():
            annotation_key = bank["dimensions"][key]["annotation_key"]
            if annotation_key not in annotations:
                raise RuntimeError(
                    f"{key}: model dimension has no native printed witness"
                )
            values = [
                row["value"] for row in annotations[annotation_key]["generic"]["texts"]
            ]
            if any(type(value) is not str for value in values):
                raise RuntimeError("model dimension printed witness is malformed")
            # IDisplayData pads native text runs (smpqcc8q: ' #4-40 UNC-2A ').
            # Trim for literal-presence checking only; retain and compare every
            # raw run unchanged below and in the independent full ink bank.
            lines = [
                line.strip()
                for value in values
                for line in value.splitlines()
                if line.strip()
            ]
            if any(lines.count(line) != 1 for line in role.printed):
                raise RuntimeError(f"{key}: required model callout text is not printed")
            if bank["dimensions"][key]["presentation"][
                "show_dimension_value"
            ] is False and lines != list(role.printed):
                raise RuntimeError(
                    f"{key}: whole-text display contains unexpected printed content"
                )
            bank["dimensions"][key]["native_text_values"] = values


def compare(before, after):
    if before.get("model_dimensions") != after.get("model_dimensions"):
        raise RuntimeError("cold reopen changed exact model-dimension coverage")
