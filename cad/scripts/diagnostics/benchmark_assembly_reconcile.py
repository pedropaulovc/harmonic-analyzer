"""Experimental keyed two-occurrence mate reconciliation. --help and plan require no COM."""
from __future__ import annotations

import argparse
import base64
from contextlib import contextmanager
from dataclasses import asdict
import json
import math
import os
from pathlib import Path
import shutil
import statistics
import sys
import time
from typing import Any

# Deliberately no native imports until after argument parsing and seat guard.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _assembly_reconcile import DIMENSIONS, plan, recipe
from benchmark_feature_reconcile import Benchmark as PartBenchmark, digest, image_content_evidence, write_json

PREFIX = "experiment.assembly_reconcile"
DEFAULT_OUT = Path(__file__).resolve().parents[2] / "out" / "reports" / "assembly-reconcile"
BASELINE_DISTANCE_MM = 30.0
TARGET_DISTANCE_MM = 40.0

# SDK enum values (developing-solidworks v3.12.1 enums/*.md); every literal is
# re-checked against the seat's installed swconst.tlb before any document work.
DOC_PART, DOC_ASSEMBLY = 1, 2  # swDocumentTypes_e
OPEN_SILENT = 1  # swOpenDocOptions_Silent
ADD_COMPONENT_CURRENT_SELECTED_CONFIG = 0  # swAddComponentConfigOptions_e
FULLY_CONSTRAINED = 3  # swConstrainedStatus_e.swFullyConstrained
RESOLVED_SUPPRESSION_STATES = {2, 3}  # swComponentFullyResolved, swComponentResolved
MATE_TYPES = {"MateCoincident": 0, "MateDistanceDim": 5}  # swMateType_e
MATE_ALIGNMENTS = {"aligned": 0}  # swMateAlign_e.swMateAlignALIGNED
SELECT_DATUM_PLANE = 4  # swSelectType_e.swSelDATUMPLANES
PERSIST_OK = 0  # swPersistReferencedObjectStates_e.swPersistReferencedObject_Ok
THIS_CONFIGURATION = 1  # swInConfigurationOpts_e.swThisConfiguration / swSetValue_InThisConfiguration
SET_VALUE_SUCCESSFUL = 0  # swSetValueReturnStatus_e.swSetValue_Successful
NATIVE_LITERALS = {
    "swDocPART": DOC_PART, "swDocASSEMBLY": DOC_ASSEMBLY, "swOpenDocOptions_Silent": OPEN_SILENT,
    "swAddComponentConfigOptions_CurrentSelectedConfig": ADD_COMPONENT_CURRENT_SELECTED_CONFIG,
    "swFullyConstrained": FULLY_CONSTRAINED, "swComponentFullyResolved": 2, "swComponentResolved": 3,
    "swMateCOINCIDENT": MATE_TYPES["MateCoincident"], "swMateDISTANCE": MATE_TYPES["MateDistanceDim"],
    "swMateAlignALIGNED": MATE_ALIGNMENTS["aligned"], "swSelDATUMPLANES": SELECT_DATUM_PLANE,
    "swPersistReferencedObject_Ok": PERSIST_OK, "swThisConfiguration": THIS_CONFIGURATION,
    "swSetValue_InThisConfiguration": THIS_CONFIGURATION, "swSetValue_Successful": SET_VALUE_SUCCESSFUL,
    # Used by the reused part save and by the render path.
    "swSaveAsCurrentVersion": 0, "swSaveAsOptions_Silent": 1, "swSaveAsOptions_AvoidRebuildOnSave": 8,
    "swIsometricView": 7,
}
TRANSFORM_TOLERANCE = 1e-9  # unitless rotation/scale and metres translation
DISTANCE_TOLERANCE_MM = 1e-7
STALE_PATTERNS = ("*.SLDASM", "*.SLDPRT", "*.png", "*.json", "*.jsonl")


def native_path(path: Any) -> str:
    """Case-normalised absolute path for exact native reference comparisons."""
    return os.path.normcase(str(Path(str(path)).resolve()))


def expected_transform(translation_m: list[float]) -> list[float]:
    """Identity rotation rows [0:9], signed translation [9:12], scale [12]."""
    return [1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0, *translation_m, 1.0]


def transform_mismatch(actual: list[float], expected: list[float]) -> bool:
    return len(actual) != 16 or any(
        not math.isfinite(value) or abs(value - target) > TRANSFORM_TOLERANCE
        for value, target in zip(actual[:13], expected, strict=True))


def verify_native_literals() -> dict[str, int]:
    """Fail before any document work if a literal disagrees with the seat typelib."""
    from solidworks_mcp.adapters import sw_type_info
    observed = {name: sw_type_info.constant(name) for name in NATIVE_LITERALS}
    if observed != NATIVE_LITERALS:
        raise RuntimeError(f"Seat swconst disagrees with benchmark literals: {observed}")
    return observed


def pin_assembly_template(adapter: Any) -> dict[str, Any]:
    """Explicit seat-local template; read only, never changes the preference."""
    from solidworks_mcp.adapters import sw_type_info

    preference = sw_type_info.constant("swDefaultTemplateAssembly")  # raises if absent
    preference_value = adapter.swApp.GetUserPreferenceStringValue(preference)
    # The preference may be empty while SOLIDWORKS has a usable default.
    # GetDocumentTemplate resolves the template used by NewDocument; for an
    # assembly its remaining arguments are explicitly unused by the SDK.
    value = adapter.swApp.GetDocumentTemplate(DOC_ASSEMBLY, "", 0, 0.0, 0.0)
    path = Path(value) if isinstance(value, str) and value else None
    if path is None or path.suffix.lower() != ".asmdot" or not path.is_file() or not path.stat().st_size:
        raise RuntimeError(f"Resolved assembly template is not an existing .ASMDOT: resolved={value!r}, preference={preference_value!r}")
    return {"preference": "swDefaultTemplateAssembly", "preference_id": preference,
            "preference_value": preference_value, "resolver": "GetDocumentTemplate",
            "path": str(path), "sha256": digest(path), "bytes": path.stat().st_size,
            "seat_local": True, "in_recipe_cache_key": False}


class Harness:
    def __init__(self, adapter: Any, out: Path, template: dict[str, Any]):
        self.adapter = adapter
        self.out = out
        self.template = template
        self.phases: list[dict[str, Any]] = []
        # Child part creation and geometry/identity validation reuse the
        # qualified keyed-feature diagnostic unchanged (its events keep their
        # experiment.feature_reconcile names inside these spans).
        self.part = PartBenchmark(adapter, out)

    @contextmanager
    def phase(self, name: str, case: str, **attributes: Any):
        import _telemetry
        start = time.perf_counter()
        with _telemetry.span(f"{PREFIX}.{name}", case=case, **attributes) as span:
            ctx = span.get_span_context()
            row = {"phase": name, "case": case, "trace_id": f"{ctx.trace_id:032x}",
                   "span_id": f"{ctx.span_id:016x}", "status": "error"}
            try:
                yield
                row["status"] = "ok"
            finally:
                row["seconds"] = time.perf_counter() - start
                self.phases.append(row)

    def event(self, event_name: str, **attributes: Any) -> None:
        import _telemetry
        # Attribute keys are namespaced: _telemetry.event's first parameter is `name`.
        _telemetry.event(f"{PREFIX}.{event_name}", **{f"observed_{key}": value for key, value in attributes.items()})

    def model(self):
        from _com import _early_bound
        return _early_bound(self.adapter.currentModel, "IModelDoc2")

    def assembly(self):
        from _com import _early_bound
        return _early_bound(self.adapter.currentModel, "IAssemblyDoc")

    def extension(self):
        from _com import _early_bound
        return _early_bound(self.model().Extension, "IModelDocExtension")

    def same(self, first: Any, second: Any) -> bool:
        # SDK compare-selected-objects example: 1=same, 0=different, -1=unknown.
        return int(self.adapter.swApp.IsSame(first, second)) == 1

    def require_not_open(self, *paths: Path) -> None:
        for path in paths:
            if self.adapter.swApp.GetOpenDocumentByName(str(path)) is not None:
                raise RuntimeError(f"Document must not be loaded: {path}")

    def require_active(self) -> None:
        # EditRebuild3 works only in the context of the active document.
        active = self.adapter.swApp.ActiveDoc
        if active is None or not self.same(active, self.adapter.currentModel):
            raise RuntimeError("Target assembly is not the active document")

    def require_configuration(self, expected: str) -> str:
        """The current document must have exactly the declared, active configuration."""
        from _com import _early_bound
        model = self.model()
        names = tuple(str(name) for name in (model.GetConfigurationNames() or ()))
        active = _early_bound(_early_bound(model.ConfigurationManager, "IConfigurationManager").ActiveConfiguration,
                              "IConfiguration")
        if names != (expected,) or str(active.Name) != expected:
            raise RuntimeError(f"{model.GetPathName() or model.GetTitle()} configurations {names}, "
                               f"active {active.Name!r}; expected only {expected!r}")
        return expected

    async def open(self, path: Path, doc_type: int, configuration: str) -> None:
        # Explicit document type and configuration; every native output is fatal.
        answer = self.adapter.swApp.OpenDoc6(str(path), doc_type, OPEN_SILENT, configuration, 0, 0)
        if not isinstance(answer, (tuple, list)) or len(answer) != 3:
            raise RuntimeError(f"Unexpected OpenDoc6 readback: {answer!r}")
        document, errors, warnings = answer
        if document is None or errors or warnings:
            raise RuntimeError(f"OpenDoc6 failed/warned: errors={errors}, warnings={warnings}, path={path}")
        self.adapter.currentModel = document
        if native_path(self.model().GetPathName()) != native_path(path):
            raise RuntimeError(f"Opened wrong document: {self.model().GetPathName()} != {path}")

    def close(self, child: Path) -> None:
        """Close the assembly, then prove its referenced child is unloaded."""
        from _com import _early_bound
        self.part.close()
        loaded = self.adapter.swApp.GetOpenDocumentByName(str(child))
        if loaded is not None:
            title = _early_bound(loaded, "IModelDoc2").GetTitle()
            self.adapter.swApp.CloseDoc(title)
            self.event("child_closed_explicitly", child=child.name)
        self.require_not_open(child)

    def dependencies(self, path: Path) -> list[tuple[str, str]]:
        # Closed-document read; Searchflag=False reports where references were saved.
        answer = self.adapter.swApp.GetDocumentDependencies2(str(path), False, False, False)
        if not isinstance(answer, (tuple, list)) or not answer or len(answer) % 2:
            raise RuntimeError(f"Unexpected GetDocumentDependencies2 readback for {path}: {answer!r}")
        return [(str(answer[index]), str(answer[index + 1])) for index in range(0, len(answer), 2)]

    def retarget(self, assembly: Path, old_child: Path, new_child: Path) -> dict[str, Any]:
        """Repoint a closed byte-copied assembly to its byte-copied child."""
        self.require_not_open(assembly, old_child, new_child)
        before = self.dependencies(assembly)
        if len(before) != 1 or native_path(before[0][1]) != native_path(old_child):
            raise RuntimeError(f"Copied assembly does not reference exactly {old_child}: {before}")
        if not self.adapter.swApp.ReplaceReferencedDocument(str(assembly), before[0][1], str(new_child)):
            raise RuntimeError(f"ReplaceReferencedDocument failed: {assembly}")
        after = self.dependencies(assembly)
        if len(after) != 1 or native_path(after[0][1]) != native_path(new_child):
            raise RuntimeError(f"Retargeted assembly does not reference exactly {new_child}: {after}")
        return {"before": before, "after": after}

    def transform(self, component: Any) -> list[float]:
        from _com import _early_bound
        values = [float(value) for value in _early_bound(component.Transform2, "IMathTransform").ArrayData]
        if len(values) != 16:
            raise RuntimeError(f"Unexpected component transform: {values}")
        return values

    def set_fixed(self, component: Any, fixed: bool) -> None:
        # FixComponent/UnfixComponent are void and act on the selection.
        model = self.model()
        model.ClearSelection2(True)
        if not component.Select4(False, None, False):
            raise RuntimeError(f"Could not select component {component.Name2}")
        if fixed:
            self.assembly().FixComponent()
        else:
            self.assembly().UnfixComponent()
        model.ClearSelection2(True)
        if bool(component.IsFixed()) != fixed:
            raise RuntimeError(f"Component {component.Name2} did not become fixed={fixed}")

    def place(self, component: Any, translation_m: list[float]) -> None:
        """AddComponent5 coordinates are approximate; set and read back exactly."""
        from _com import _early_bound
        import pythoncom
        from win32com.client import VARIANT
        if bool(component.IsFixed()):
            self.set_fixed(component, False)
        target = [*expected_transform(translation_m), 0.0, 0.0, 0.0]
        utility = _early_bound(self.adapter.swApp.GetMathUtility(), "IMathUtility")
        # VT_R8 array: a VT_VARIANT array is silently ignored (adapter note).
        xform = utility.CreateTransform(VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_R8, target))
        if xform is None or not component.SetTransformAndSolve3(xform, True):
            raise RuntimeError(f"Could not place component {component.Name2}")
        if transform_mismatch(self.transform(component), expected_transform(translation_m)):
            raise RuntimeError(f"Placement readback mismatch for {component.Name2}: {self.transform(component)}")

    def preload(self, child: Path, configuration: str) -> None:
        """AddComponent5 requires the file in memory; load it hidden (adapter pattern)."""
        sw = self.adapter.swApp
        sw.DocumentVisible(False, DOC_PART)
        try:
            answer = sw.OpenDoc6(str(child), DOC_PART, OPEN_SILENT, configuration, 0, 0)
        finally:
            sw.DocumentVisible(True, DOC_PART)
        if not isinstance(answer, (tuple, list)) or len(answer) != 3:
            raise RuntimeError(f"Unexpected child OpenDoc6 readback: {answer!r}")
        document, errors, warnings = answer
        if document is None or errors or warnings:
            raise RuntimeError(f"Child preload failed/warned: errors={errors}, warnings={warnings}, path={child}")

    async def create(self, spec: dict[str, Any], child: Path) -> dict[str, Any]:
        """Full timed construction: template document, two keyed occurrences, three mates."""
        from _check import check
        from _com import _early_bound
        from solidworks_mcp.adapters.base import AddMateParameters, MateEntityRef
        document = self.adapter.swApp.NewDocument(self.template["path"], 0, 0.0, 0.0)
        if document is None:
            raise RuntimeError(f"NewDocument failed for pinned template {self.template['path']}")
        self.adapter.currentModel = document
        if int(self.model().GetType()) != DOC_ASSEMBLY:
            raise RuntimeError("Pinned template did not create an assembly")
        self.require_configuration(spec["configurations"]["assembly"])
        configuration = spec["configurations"]["child"]
        self.preload(child, configuration)
        self.require_active()
        components = {}
        for item in spec["components"]:
            raw = self.assembly().AddComponent5(str(child), ADD_COMPONENT_CURRENT_SELECTED_CONFIG, "",
                                                True, configuration, 0.0, 0.0, 0.0)
            if raw is None:
                raise RuntimeError(f"AddComponent5 failed for {item['key']}")
            components[item["key"]] = _early_bound(raw, "IComponent2")
        distance_m = spec["parameters_mm"]["distance"] / 1000
        # The mover starts on the intended +Z side. The recipe's FlipDimension
        # (True for this [mover, base] order, natively observed) selects that
        # side; the signed transform and Flipped readbacks verify it.
        self.place(components["base"], [0.0, 0.0, 0.0])
        self.place(components["mover"], [0.0, 0.0, distance_m])
        self.set_fixed(components["base"], True)
        if bool(components["mover"].IsFixed()):
            raise RuntimeError("Mover must remain floating")
        names = {key: str(component.Name2) for key, component in components.items()}
        for mate in spec["mates"]:
            options = {"distance": spec["parameters_mm"]["distance"], "flip": mate["flip"]} \
                if mate["mate_type"] == "distance" else {}
            # Adapter path: GetCorresponding planes -> CreateMateData -> CreateMate,
            # followed by its own EditRebuild3 (inside this timed creation span).
            created = check(f"mate {mate['key']}", await self.adapter.add_mate(AddMateParameters(
                mate_type=mate["mate_type"], alignment=mate["alignment"], entities=[
                    MateEntityRef(entity_type="PLANE", component=names["mover"], name=mate["mover_plane"]),
                    MateEntityRef(entity_type="PLANE", component=names["base"], name=mate["base_plane"]),
                ], **options)))
            raw = self.assembly().FeatureByName(created["name"]) if created.get("name") else None
            if raw is None:
                raise RuntimeError(f"Created mate {mate['key']} is not addressable: {created!r}")
            feature = _early_bound(raw, "IFeature")
            feature.Name = mate["name"]
            if str(feature.Name) != mate["name"]:
                raise RuntimeError(f"Mate rename failed: {created['name']} -> {mate['name']}")
        self.model().ClearSelection2(True)
        return {"component_names": names, "mate_count": len(spec["mates"]),
                "adapter_mate_rebuilds": len(spec["mates"])}

    def roles(self) -> dict[str, Any]:
        """Independent native role lookup: exactly one fixed and one floating occurrence."""
        from _com import _early_bound
        raw = self.assembly().GetComponents(True) or ()
        components = [_early_bound(component, "IComponent2") for component in raw]
        fixed = [component for component in components if bool(component.IsFixed())]
        floating = [component for component in components if not bool(component.IsFixed())]
        if len(components) != 2 or len(fixed) != 1 or len(floating) != 1 or self.same(fixed[0], floating[0]):
            raise RuntimeError(f"Expected one fixed and one floating occurrence, got {len(components)}")
        return {"base": fixed[0], "mover": floating[0]}

    def mate_group_names(self) -> list[str]:
        from _com import _early_bound
        names = []
        feature = self.model().FirstFeature()
        for _ in range(10000):
            if feature is None:
                break
            feature = _early_bound(feature, "IFeature")
            if str(feature.GetTypeName2()) == "MateGroup":
                sub = feature.GetFirstSubFeature()
                for _ in range(10000):
                    if sub is None:
                        break
                    sub = _early_bound(sub, "IFeature")
                    names.append(str(sub.Name))
                    sub = sub.GetNextSubFeature()
                else:
                    raise RuntimeError("Mate group walk did not terminate")
            feature = feature.GetNextFeature()
        else:
            raise RuntimeError("Feature tree walk did not terminate")
        return names

    def mate(self, item: dict[str, Any]):
        from _com import _early_bound
        raw = self.assembly().FeatureByName(item["name"])
        if raw is None:
            raise RuntimeError(f"Missing keyed mate {item['key']}: {item['name']}")
        return _early_bound(raw, "IFeature")

    def mate_dimension(self, feature: Any):
        """Named distance dimension, proven to be owned by the keyed mate feature."""
        from _com import _early_bound
        raw = self.model().Parameter(DIMENSIONS["distance"])
        if raw is None:
            raise RuntimeError(f"Missing mate dimension {DIMENSIONS['distance']}")
        dimension = _early_bound(raw, "IDimension")
        owner = dimension.GetFeatureOwner()
        if owner is None or not self.same(owner, feature):
            raise RuntimeError("Distance dimension is not owned by the keyed distance mate")
        return dimension

    def references(self, spec: dict[str, Any]) -> dict[str, str]:
        ext = self.extension()
        objects = {**self.roles(), **{item["key"]: self.mate(item) for item in spec["mates"]}}
        result = {}
        for key, native in objects.items():
            reference = ext.GetPersistReference3(native)
            if not reference:
                raise RuntimeError(f"Missing persistent reference: {key}")
            result[key] = base64.b64encode(bytes(int(x) & 255 for x in reference)).decode("ascii")
        return result

    def identity(self, ext: Any, encoded: str, native: Any, key: str) -> str:
        """Resolve one persisted reference to the independently found native object."""
        from _com import _early_bound
        import pythoncom
        from win32com.client import VARIANT
        reference = VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_UI1, base64.b64decode(encoded, validate=True))
        answer = ext.GetObjectByPersistReference3(reference)
        if not isinstance(answer, (tuple, list)) or len(answer) != 2:
            raise RuntimeError(f"Unexpected reference resolution for {key}: {answer!r}")
        resolved, state = answer
        if int(state) != PERSIST_OK or resolved is None:
            raise RuntimeError(f"Identity unresolved: {key}, state={state}")
        if self.same(resolved, native):
            return "direct"
        # SDK: resolution can return the base IFeature; its specific object is
        # obtained with GetSpecificFeature2. Only attempt that on a real IFeature.
        feature_iid = _early_bound(resolved, "IFeature").CLSID
        try:
            resolved._oleobj_.QueryInterface(feature_iid)
        except pythoncom.com_error as exc:
            raise RuntimeError(f"Identity lost: {key} resolved to a different non-feature object") from exc
        specific = _early_bound(resolved, "IFeature").GetSpecificFeature2()
        if specific is None or not self.same(specific, native):
            raise RuntimeError(f"Identity lost: {key}")
        return "specific_feature"

    def child_geometry(self, component: Any, child_spec: dict[str, Any], child_refs: dict[str, str]) -> dict[str, Any]:
        document = component.GetModelDoc2()
        if document is None:
            raise RuntimeError("Component child model is not loaded")
        previous = self.adapter.currentModel
        self.adapter.currentModel = document
        try:
            return self.part.validate(child_spec, child_refs)
        finally:
            self.adapter.currentModel = previous

    def validate(self, spec: dict[str, Any], refs: dict[str, str], child: Path,
                 child_refs: dict[str, str]) -> dict[str, Any]:
        """Identical native gates for baseline, clean, incremental and no-op."""
        from _com import _early_bound
        model = self.model()
        if int(model.GetType()) != DOC_ASSEMBLY:
            raise RuntimeError("Validation target is not an assembly")
        configuration = self.require_configuration(spec["configurations"]["assembly"])
        ext = self.extension()
        roles = self.roles()
        distance_m = spec["parameters_mm"]["distance"] / 1000
        expected = {"base": expected_transform([0.0, 0.0, 0.0]),
                    "mover": expected_transform([0.0, 0.0, distance_m])}
        components = {}
        for key, component in roles.items():
            document = component.GetModelDoc2()
            observed = {
                "name": str(component.Name2), "path": str(component.GetPathName()),
                "loaded_path": str(_early_bound(document, "IModelDoc2").GetPathName()) if document is not None else None,
                "referenced_configuration": str(component.ReferencedConfiguration),
                "suppression": int(component.GetSuppression2()),
                "suppressed": bool(component.IsSuppressed()),
                "fixed": bool(component.IsFixed()),
                "constrained_status": int(component.GetConstrainedStatus()),
                "transform": self.transform(component),
            }
            self.event("component", key=key, **{k: str(v) for k, v in observed.items()})
            if (observed["suppression"] not in RESOLVED_SUPPRESSION_STATES or observed["suppressed"]
                    or native_path(observed["path"]) != native_path(child)
                    or observed["loaded_path"] is None or native_path(observed["loaded_path"]) != native_path(child)
                    or observed["referenced_configuration"] != spec["configurations"]["child"]):
                raise RuntimeError(f"Component {key} health/resolution mismatch: {observed}")
            if transform_mismatch(observed["transform"], expected[key]):
                raise RuntimeError(f"Component {key} signed transform mismatch: {observed['transform']}")
            observed["identity"] = self.identity(ext, refs[key], component, key)
            components[key] = observed
        if components["mover"]["constrained_status"] != FULLY_CONSTRAINED:
            raise RuntimeError(f"Mover is not fully constrained: {components['mover']['constrained_status']}")
        if not self.same(roles["base"].GetModelDoc2(), roles["mover"].GetModelDoc2()):
            raise RuntimeError("Occurrences do not share the single child model")
        names = self.mate_group_names()
        if sorted(names) != sorted(item["name"] for item in spec["mates"]):
            raise RuntimeError(f"Unexpected mate set: {names}")
        mates = {}
        distance_mm = None
        for item in spec["mates"]:
            feature = self.mate(item)
            suppressed = feature.IsSuppressed2(THIS_CONFIGURATION, None)
            error = feature.GetErrorCode2()
            if not isinstance(error, (tuple, list)) or len(error) != 2:
                raise RuntimeError(f"Unexpected GetErrorCode2 readback: {error!r}")
            mate = _early_bound(feature.GetSpecificFeature2(), "IMate2")
            count = int(mate.GetMateEntityCount())
            entities = [_early_bound(mate.MateEntity(index), "IMateEntity2") for index in range(count)]
            owners = sorted(key for entity in entities for key, component in roles.items()
                            if self.same(entity.ReferenceComponent, component))
            observed = {
                "name": str(feature.Name), "type": str(feature.GetTypeName2()),
                "suppressed": [bool(value) for value in (suppressed or ())],
                "error_code": int(error[0] or 0), "error_is_warning": bool(error[1]),
                "mate_type": int(mate.Type), "alignment": int(mate.Alignment),
                "entity_count": count, "entity_owners": owners,
                "entity_reference_types": [int(entity.ReferenceType2) for entity in entities],
            }
            if item["type"] == "MateDistanceDim":
                observed["flipped"] = bool(mate.Flipped)
                actual = self.mate_dimension(feature).GetSystemValue3(THIS_CONFIGURATION, None)
                if not isinstance(actual, (tuple, list)) or len(actual) != 1:
                    raise RuntimeError(f"Unexpected mate dimension readback: {actual!r}")
                distance_mm = float(actual[0]) * 1000
                observed["distance_mm"] = distance_mm
            self.event("mate", key=item["key"], **{k: str(v) for k, v in observed.items()})
            # Declared policy: any error OR warning code is fatal.
            if (observed["name"] != item["name"] or observed["type"] != item["type"]
                    or observed["suppressed"] != [False] or observed["error_code"] != 0
                    or observed["mate_type"] != MATE_TYPES[item["type"]]
                    or observed["alignment"] != MATE_ALIGNMENTS[item["alignment"]]
                    or count != 2 or owners != ["base", "mover"]
                    or observed["entity_reference_types"] != [SELECT_DATUM_PLANE] * 2
                    or observed.get("flipped", item.get("flip")) != item.get("flip")):
                raise RuntimeError(f"Mate {item['key']} contract mismatch: {observed}")
            observed["identity"] = self.identity(ext, refs[item["key"]], feature, item["key"])
            mates[item["key"]] = observed
        expected_mm = spec["parameters_mm"]["distance"]
        if distance_mm is None or not math.isfinite(distance_mm) or abs(distance_mm - expected_mm) > DISTANCE_TOLERANCE_MM:
            raise RuntimeError(f"Distance mate {distance_mm} != {expected_mm} mm")
        geometry = self.child_geometry(roles["base"], spec["child"], child_refs)
        return {"configuration": configuration, "components": components, "mates": mates,
                "distance_mm": distance_mm, "child_geometry": geometry,
                "assembly_dirty": bool(model.GetSaveFlag())}

    async def operation(self, case: str, mode: str, spec: dict[str, Any], source: Path | None = None,
                        manifest: dict[str, Any] | None = None) -> dict[str, Any]:
        assembly = self.out / f"{case}.SLDASM"
        child = self.out / f"{case}-child.SLDPRT"
        configuration = spec["configurations"]["assembly"]
        started = time.perf_counter()
        decision = None
        retarget = None
        prepared_assembly_hash = None
        if mode != "clean":
            source_assembly = self.out / manifest["assembly_file"]
            source_child = self.out / manifest["child_file"]
        with self.phase("copy", case, mode=mode):
            if mode == "clean":
                shutil.copyfile(source, child)
            else:
                if (digest(source_assembly) != manifest["assembly_sha256"]
                        or digest(source_child) != manifest["child_sha256"]):
                    raise RuntimeError("Source assembly/child bytes no longer match persisted manifest")
                shutil.copyfile(source_assembly, assembly)
                shutil.copyfile(source_child, child)
            prepared_child_hash = digest(child)
        with self.phase("retarget", case, skipped=mode == "clean"):
            if mode != "clean":
                retarget = self.retarget(assembly, source_child, child)
                prepared_assembly_hash = digest(assembly)
        with self.phase("open", case, skipped=mode == "clean"):
            if mode != "clean":
                await self.open(assembly, DOC_ASSEMBLY, configuration)
                # The source child must never be what SolidWorks resolved.
                self.require_not_open(source_child)
        with self.phase("diff", case, skipped=mode == "clean"):
            decision = plan(manifest["recipe"], spec) if mode != "clean" else None
            if decision and decision.decision == "full_build":
                raise RuntimeError("Structural plan must be handled before native mutation")
        dimensions = []
        with self.phase("prevalidation", case, skipped=mode != "incremental"):
            if mode == "incremental":
                # Validate *all* copied-baseline contracts before the first mutation.
                self.validate(manifest["recipe"], manifest["references"], child,
                              manifest["child_feature_references"])
                distance = next(item for item in spec["mates"] if item["key"] == "distance")
                dimensions = [(self.mate_dimension(self.mate(distance)), value) for _key, value in decision.edits]
        creation = None
        with self.phase("edit", case, skipped=mode == "noop", mode=mode,
                        operation={"clean": "create", "incremental": "dimension_edit"}.get(mode, "none")):
            if mode == "clean":
                creation = await self.create(spec, child)
            elif mode == "incremental":
                for dimension, value in dimensions:
                    status = dimension.SetSystemValue3(value / 1000, THIS_CONFIGURATION, None)
                    if int(status) != SET_VALUE_SUCCESSFUL:
                        raise RuntimeError(f"SetSystemValue3 failed: {status}")
                # No live dimension handles across the close/reopen proof.
                dimensions.clear()
            elif not decision or decision.decision != "noop":
                raise RuntimeError(f"Expected no-op plan, got {decision}")
        with self.phase("rebuild", case, skipped=mode == "noop"):
            if mode != "noop":
                self.require_active()
                if not self.model().EditRebuild3():
                    raise RuntimeError("EditRebuild3 failed")
        with self.phase("validation_before_save", case):
            refs = self.references(spec) if mode == "clean" else manifest["references"]
            child_refs = manifest["child_feature_references"]
            before = self.validate(spec, refs, child, child_refs)
        with self.phase("save", case, skipped=mode == "noop"):
            if mode != "noop":
                # SaveAs without SaveReferenced: the child is never saved here.
                self.part.save(assembly)
            saved_hash = digest(assembly)
        with self.phase("close_before_reopen", case):
            self.close(child)
        with self.phase("reopen", case):
            await self.open(assembly, DOC_ASSEMBLY, configuration)
        with self.phase("validation_after_reopen", case):
            after = self.validate(spec, refs, child, child_refs)
        with self.phase("close_after_reopen", case):
            self.close(child)
        with self.phase("readback_integrity", case):
            if digest(assembly) != saved_hash:
                raise RuntimeError("Readback changed saved assembly bytes")
            if mode == "noop" and saved_hash != prepared_assembly_hash:
                raise RuntimeError("No-op mutated assembly bytes")
            final_child_hash = digest(child)
        return {"case": case, "mode": mode, "seconds": time.perf_counter() - started,
                "decision": asdict(decision) if decision else {"decision": "clean"},
                "creation": creation, "retarget": retarget,
                "before_save": before, "after_reopen": after,
                "path": assembly.name, "child_path": child.name,
                "assembly_sha256": saved_hash, "prepared_assembly_sha256": prepared_assembly_hash,
                # Evidence only: parent saves may churn child bytes; geometry is validated separately.
                "child_sha256": {"prepared": prepared_child_hash, "final": final_child_hash,
                                 "changed": prepared_child_hash != final_child_hash},
                "references": refs}

    async def fixture(self, spec: dict[str, Any], configuration: str, path: Path) -> dict[str, Any]:
        """Untimed-trial input: the qualified keyed-feature cylinder, saved once."""
        await self.part.create(spec)
        self.require_configuration(configuration)
        if not self.model().EditRebuild3():
            raise RuntimeError("Fixture EditRebuild3 failed")
        refs = self.part.refs()
        geometry = self.part.validate(spec, refs)
        self.part.save(path)
        self.part.close()
        return {"path": path.name, "sha256": digest(path), "configuration": configuration,
                "feature_references": refs, "geometry": geometry}

    async def render(self, row: dict[str, Any], configuration: str) -> dict[str, Any]:
        """Capture a saved trial outside all timed operation rows; never save it."""
        import _telemetry
        from _check import check
        from _com import _early_bound

        native = self.out / row["path"]
        child = self.out / row["child_path"]
        image_path = self.out / f"visual-{row['mode']}.png"
        original_hash = digest(native)
        with _telemetry.span(f"{PREFIX}.render", mode=row["mode"], timed_trial=False):
            await self.open(native, DOC_ASSEMBLY, configuration)
            view = None
            prior_graphics_updates = None
            try:
                original_document = self.model()
                activated = self.adapter.swApp.ActivateDoc3(native.name, False, 1, 0)
                if not isinstance(activated, (tuple, list)) or len(activated) != 2:
                    raise RuntimeError(f"Unexpected ActivateDoc3 readback: {activated!r}")
                document, errors = activated
                if document is None or int(errors) != 0:
                    raise RuntimeError(f"Capture activation failed/warned: {native}, errors={errors}")
                document = _early_bound(document, "IModelDoc2")
                active = self.adapter.swApp.ActiveDoc
                if active is None:
                    raise RuntimeError(f"No active document after capture activation: {native}")
                active = _early_bound(active, "IModelDoc2")
                if (native_path(active.GetPathName()) != native_path(native)
                        or not self.same(active, document) or not self.same(original_document, document)):
                    raise RuntimeError(f"Capture activated the wrong native document: {native}")
                self.adapter.currentModel = document
                raw_view = document.ActiveView
                if raw_view is None:
                    raise RuntimeError(f"Capture target has no active model view: {native}")
                view = _early_bound(raw_view, "IModelView")
                prior_graphics_updates = bool(view.EnableGraphicsUpdate)
                view.EnableGraphicsUpdate = True
                if not view.EnableGraphicsUpdate:
                    raise RuntimeError(f"Capture target refused graphics updates: {native}")
                document.ClearSelection2(True)
                document.ShowNamedView2("", 7)  # swIsometricView
                document.ViewZoomtofit2()
                document.GraphicsRedraw2()
                self.event("capture_prepared", native_file=native.name, activation_errors=int(errors),
                           active_path=active.GetPathName(), prior_graphics_updates=prior_graphics_updates)
                # Remove our prior image so stale bytes cannot masquerade as proof.
                image_path.unlink(missing_ok=True)
                check(f"render {row['mode']}", await self.adapter.export_image({
                    "file_path": str(image_path), "format_type": "png",
                    "width": 1600, "height": 1000, "view_orientation": "current",
                }))
                content = image_content_evidence(image_path)
            finally:
                try:
                    if view is not None and prior_graphics_updates is not None:
                        view.EnableGraphicsUpdate = prior_graphics_updates
                        if bool(view.EnableGraphicsUpdate) != prior_graphics_updates:
                            raise RuntimeError(f"Could not restore graphics updates: {native}")
                finally:
                    self.close(child)
            if digest(native) != original_hash:
                raise RuntimeError(f"Rendering changed native bytes: {native}")
        return {"mode": row["mode"], "native_file": native.name, "native_sha256": original_hash,
                "image_file": image_path.name, "image_sha256": digest(image_path),
                "image_dimensions": content["dimensions"], "image_content": content,
                "orientation": "isometric", "included_in_trial_timings": False}


def compare_pair(clean: dict[str, Any], incremental: dict[str, Any]) -> None:
    """Clean and edited results must agree on geometry/health, never on identities."""
    if abs(clean["distance_mm"] - incremental["distance_mm"]) > DISTANCE_TOLERANCE_MM:
        raise RuntimeError("Clean/incremental distance differs")
    for key in ("base", "mover"):
        a, b = clean["components"][key], incremental["components"][key]
        if (transform_mismatch(a["transform"], b["transform"][:13])
                or a["constrained_status"] != b["constrained_status"] or a["fixed"] != b["fixed"]):
            raise RuntimeError(f"Clean/incremental component {key} differs")
    a, b = clean["child_geometry"], incremental["child_geometry"]
    if any(abs(a["dimensions_mm"][key] - b["dimensions_mm"][key]) > 1e-7 for key in a["dimensions_mm"]):
        raise RuntimeError("Clean/incremental child dimensions differ")
    for first, second in zip(a["bounds_mm"], b["bounds_mm"], strict=True):
        if any(abs(x - y) > 1e-6 for x, y in zip(first, second, strict=True)):
            raise RuntimeError("Clean/incremental child extents differ")
    if not math.isclose(a["volume_mm3"], b["volume_mm3"], rel_tol=1e-9):
        raise RuntimeError("Clean/incremental child volume differs")


async def benchmark(adapter: Any, out: Path, trials: int) -> dict[str, str]:
    import _telemetry
    from opentelemetry import trace
    from opentelemetry.sdk.trace import SpanProcessor

    out.mkdir(parents=True, exist_ok=True)
    for pattern in STALE_PATTERNS:  # canonical declared directory only (main enforces)
        for stale in out.glob(pattern):
            stale.unlink()
    raw = out / "spans.jsonl"
    raw.write_text("", encoding="utf-8")

    class RetainedSpans(SpanProcessor):
        def __init__(self):
            self.count = 0
            self.error = None
            self.completed = []

        def on_end(self, span):
            if not span.name.startswith(PREFIX):
                return
            self.completed.append(span)
            self.count += 1
            # Serialize only when the root ends (also on exceptions): evidence IO
            # must not inflate operation timings.
            if span.name == PREFIX:
                try:
                    with raw.open("w", encoding="utf-8") as stream:
                        for completed in self.completed:
                            stream.write(completed.to_json(indent=None) + "\n")
                except Exception as exc:
                    self.error = exc
                    raise

    retained = RetainedSpans()
    provider = trace.get_tracer_provider()
    if not hasattr(provider, "add_span_processor"):
        raise RuntimeError("A real OTel SDK provider is required")
    provider.add_span_processor(retained)
    base_spec = recipe(BASELINE_DISTANCE_MM)
    target = recipe(TARGET_DISTANCE_MM)
    configuration = base_spec["configurations"]["assembly"]
    write_json(out / "target-recipe.json", target)
    with _telemetry.span(PREFIX, trials=trials) as root:
        root_context = root.get_span_context()
        if not root_context.is_valid or not root.is_recording():
            raise RuntimeError("Benchmark requires recording OTel spans")
        native_literals = verify_native_literals()
        template = pin_assembly_template(adapter)
        harness = Harness(adapter, out, template)
        cwd = str(adapter.swApp.GetCurrentWorkingDirectory())
        with harness.phase("fixture_child", "fixture"):
            fixture = await harness.fixture(base_spec["child"], base_spec["configurations"]["child"],
                                            out / "fixture-child.SLDPRT")
        fixture_path = out / fixture["path"]
        initial = await harness.operation("baseline", "clean", base_spec, fixture_path,
                                          {"child_feature_references": fixture["feature_references"]})
        manifest = {"schema": 1, "recipe": base_spec, "assembly_file": initial["path"],
                    "assembly_sha256": initial["assembly_sha256"], "child_file": initial["child_path"],
                    "child_sha256": digest(out / initial["child_path"]),
                    "references": initial["references"],
                    "child_feature_references": fixture["feature_references"],
                    "assembly_template": template, "seat_working_directory": cwd}
        manifest_path = out / "baseline-manifest.json"
        write_json(manifest_path, manifest)
        # Exercise persisted -- not in-memory -- recipe and reference readback.
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        protected = {name: digest(out / name) for name in
                     (manifest["assembly_file"], manifest["child_file"], fixture["path"])}
        structural_spec = recipe(TARGET_DISTANCE_MM)
        # Invert whatever flip the recipe currently declares: a real structural change.
        structural_spec["mates"][2]["flip"] = not structural_spec["mates"][2]["flip"]
        with harness.phase("diff", "structural_refusal"):
            structural = plan(manifest["recipe"], structural_spec)
            if structural.decision != "full_build" or structural.edits:
                raise RuntimeError("Structural edit was not refused before mutation")
        if any(digest(out / name) != value for name, value in protected.items()):
            raise RuntimeError("Structural refusal changed the baseline")
        results = []
        orders = []
        pair = {}
        for trial in range(trials):
            order = ("clean", "incremental") if trial % 2 == 0 else ("incremental", "clean")
            orders.append([*order, "noop"])
            pair = {}
            for mode in order:
                pair[mode] = await harness.operation(f"trial-{trial + 1}-{mode}", mode, target,
                                                     fixture_path if mode == "clean" else None,
                                                     manifest if mode != "clean" else
                                                     {"child_feature_references": fixture["feature_references"]})
                results.append(pair[mode])
            compare_pair(pair["clean"]["after_reopen"], pair["incremental"]["after_reopen"])
            edited = pair["incremental"]
            noop_manifest = {"recipe": target, "assembly_file": edited["path"],
                             "assembly_sha256": edited["assembly_sha256"], "child_file": edited["child_path"],
                             "child_sha256": edited["child_sha256"]["final"],
                             "references": edited["references"],
                             "child_feature_references": fixture["feature_references"]}
            results.append(await harness.operation(f"trial-{trial + 1}-noop", "noop", target, None, noop_manifest))
            if any(digest(out / name) != value for name, value in protected.items()):
                raise RuntimeError("Trials mutated the baseline assembly, child or fixture")
        visual_proof = [await harness.render(pair[mode], configuration) for mode in ("clean", "incremental")]
        if pin_assembly_template(adapter) != template:
            raise RuntimeError("Seat assembly template preference or bytes changed during the benchmark")
    if retained.error or retained.count < len(harness.phases) + 1:
        raise RuntimeError(f"Incomplete retained OTel evidence: {retained.count}, {retained.error}")
    modes = {row["case"]: row["mode"] for row in results}
    phase_medians = {
        mode: {name: statistics.median(row["seconds"] for row in harness.phases
                                       if row["phase"] == name and modes.get(row["case"]) == mode)
               for name in dict.fromkeys(row["phase"] for row in harness.phases if modes.get(row["case"]) == mode)}
        for mode in ("clean", "incremental", "noop")}
    report = {
        "schema": 1,
        "experimental_limits": "Only one generated cylinder inserted twice, base fixed, mover constrained by Top/Right coincident and one Front distance mate; only the named distance value is reconciled.",
        "trace_id": f"{root_context.trace_id:032x}", "trials": trials, "orders": orders,
        "assembly_template": template, "seat_working_directory": cwd, "native_literals": native_literals,
        "fixture_child": fixture, "initial_baseline": initial,
        "structural_decision": asdict(structural), "results": results,
        "trial_seconds": [{"case": row["case"], "mode": row["mode"], "seconds": row["seconds"]} for row in results],
        "phases": harness.phases, "phase_median_seconds": phase_medians,
        "raw_spans": raw.name, "retained_span_count": retained.count, "visual_proof": visual_proof,
        "median_seconds": {mode: statistics.median(row["seconds"] for row in results if row["mode"] == mode)
                           for mode in ("clean", "incremental", "noop")},
        "timing_note": "Warm-seat native operation wall times. Clean rows include child copy and full assembly creation from the pinned template; that creation span contains CreateMate's internal solves and the adapter's EditRebuild3 after each of the three mates, so the separate explicit rebuild phase is not all solver time. Incremental and no-op rows include assembly+child copy, closed-document ReplaceReferencedDocument retargeting with dependency readback, and open; incremental also includes copied-baseline prevalidation. All rows include validation, save (not no-op), close/reopen and readback. Fixture/baseline creation, renders and span serialization are excluded. Excludes process/connect/farm/cache overhead. The seat-local assembly template is pinned by path and hash but is not in the recipe cache key; only fresh forced runs are benchmark evidence.",
    }
    write_json(out / "report.json", report)
    return {"report": str(out / "report.json"), "spans": str(raw)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("benchmark", help="Run on an admitted, locked farm seat only")
    run.add_argument("--out", type=Path, default=DEFAULT_OUT)
    run.add_argument("--trials", type=int, default=3)
    diff = sub.add_parser("plan", help="Diff a persisted baseline manifest against a recipe JSON without COM")
    diff.add_argument("manifest", type=Path)
    diff.add_argument("recipe", type=Path)
    args = parser.parse_args()
    if args.command == "plan":
        before = json.loads(args.manifest.read_text(encoding="utf-8"))
        after = json.loads(args.recipe.read_text(encoding="utf-8"))
        if not isinstance(before, dict) or "recipe" not in before:
            parser.error("manifest must be a JSON object with a recipe")
        print(json.dumps(asdict(plan(before["recipe"], after)), indent=2))
        return 0
    if args.trials < 3:
        parser.error("--trials must be at least 3")
    if not os.environ.get("HARMONIC_COM_SEAT"):
        raise RuntimeError("Use the canonical verify:assembly_reconcile task; no standalone COM launch")
    if args.out.resolve() != DEFAULT_OUT.resolve():
        parser.error("--out must be the canonical declared diagnostic output directory")
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
    from _session import run_build
    return run_build(lambda adapter: benchmark(adapter, args.out.resolve(), args.trials))


if __name__ == "__main__":
    raise SystemExit(main())
