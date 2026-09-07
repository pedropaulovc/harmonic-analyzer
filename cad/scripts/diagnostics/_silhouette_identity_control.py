"""Observe rejected silhouette identities without changing any acceptance gate.

The official IsSame example supplies self-comparisons and persistent-reference
comparisons as independent controls. Run only on the already owned diagnostic
drawing. No selection, insertion, rebuild, save or geometry conversion occurs.
"""

from array import array
import math
import sys

from _common import _early_bound
from diagnostics._owned_native_documents import Ownership


def _type_name(value):
    return f"{type(value).__module__}.{type(value).__qualname__}"


def _raw_return(raw):
    """Describe the actual return, never infer an OUT tuple or unwrap an ID."""
    row = {"type": _type_name(raw)}
    variant_type = getattr(sys.modules.get("win32com.client"), "VARIANT", None)
    if isinstance(variant_type, type) and isinstance(raw, variant_type):
        row.update(variant_type=raw.varianttype, value=_raw_return(raw.value))
        return row
    if raw is None or type(raw) in (str, bool, int):
        row["value"] = raw
        return row
    if type(raw) is float:
        row["value"] = raw if math.isfinite(raw) else repr(raw)
        if not math.isfinite(raw):
            row["encoding"] = "nonfinite_repr"
        return row
    if isinstance(raw, (tuple, list, bytes, bytearray, array, memoryview)):
        values = raw.tolist() if isinstance(raw, memoryview) else list(raw)
        row["value"] = [
            value if value is None or type(value) in (str, bool, int)
            else _raw_return(value)
            for value in values
        ]
        row["element_types"] = [_type_name(value) for value in values]
        if isinstance(raw, array):
            row["typecode"] = raw.typecode
        if isinstance(raw, memoryview):
            row.update(format=raw.format, shape=list(raw.shape))
        return row
    if type(raw) is dict:
        row["entries"] = [
            {"key": _raw_return(key), "value": _raw_return(value)}
            for key, value in raw.items()
        ]
        return row
    row.update(representation=repr(raw), encoding="unsupported_object_repr")
    return row


def _reference(extension, entity, records, name):
    raw = extension.GetPersistReference3(entity)
    observation = records.setdefault("raw_returns", {})[name] = {"type": _type_name(raw)}
    try:
        observation.update(_raw_return(raw))
    except Exception as error:
        observation["observation_error"] = repr(error)
    # Keep the original validator, including rejection of wrapped/nested arrays.
    return _byte_reference(raw)


def _byte_reference(raw):
    if not isinstance(raw, (tuple, list, bytes)) or not raw:
        raise RuntimeError("native persistent reference is empty or has the wrong type")
    if any(type(value) is not int or not 0 <= value <= 255 for value in raw):
        raise RuntimeError("native persistent reference is not an unsigned-byte array")
    return tuple(raw)


def _variant(reference):
    import pythoncom
    from win32com.client import VARIANT

    return VARIANT(pythoncom.VT_ARRAY | pythoncom.VT_UI1, reference)


def _capture(records, name, operation):
    try:
        value = operation()
        records[name] = {"value": value}
        return value
    except Exception as error:
        records[name] = {"error": repr(error)}
        return None


def persistent_controls(extension, entities, records):
    """Retain literal IDs and native comparisons; missing IDs are not accepted."""
    references = {}
    for name, entity in entities.items():
        reference = _capture(
            records, name,
            lambda item=entity, label=name: _reference(extension, item, records, label),
        )
        if reference is not None:
            references[name] = reference
    for first, second in (
        ("expected", "expected"), ("selected", "selected"),
        ("expected", "selected"), ("selected", "selected_again"),
        ("expected_face", "selected_face"),
    ):
        label = f"compare.{first}.{second}"
        if first not in references or second not in references:
            records[label] = {"status": "missing_reference"}
            continue
        _capture(
            records, label,
            lambda a=first, b=second: int(extension.IsSamePersistentID(
                _variant(references[a]), _variant(references[b])
            )),
        )


def _dirty_flags(models, records, phase):
    errors = []
    for scope, model in models.items():
        row = records.setdefault(scope, {})
        try:
            row[f"dirty_{phase}"] = model.GetSaveFlag()
        except Exception as error:
            row[f"dirty_{phase}_error"] = repr(error)
            errors.append(error)
    return errors


def _source_feature_control(adapter, source, records):
    """Exact owned Hook sweep control; no selections, geometry matching or saves.

    The official Get_Object_s_Persistent_Reference_ID VBA example uses a named
    BODYFEATURE. GetObjectByPersistReference3 has one OUT status: pywin32's
    generated result is (object, status), unlike GetPersistReference3's VARIANT.
    """
    row = records["source_feature_control"] = {"name": "Hook", "context": "source", "status": "running"}
    try:
        owned = adapter.ownership._record(source)
        if owned is None or owned.ownership is not Ownership.COPY or source.GetType() != 1:
            raise RuntimeError("Hook control requires the exact owned source PART")
        row["source_path"] = source.GetPathName()
        feature = _early_bound(_early_bound(source, "IPartDoc").FeatureByName("Hook"), "IFeature")
        if feature is None:
            raise RuntimeError("owned source has no named Hook feature")
        row.update(feature_name=feature.Name, feature_type=feature.GetTypeName2())
        if row["feature_name"] != "Hook" or row["feature_type"] != "Sweep":
            raise RuntimeError("positive control is not the named Hook sweep BODYFEATURE")
        extension = _early_bound(source.Extension, "IModelDocExtension")
        row["native_self"] = int(adapter.swApp.IsSame(feature, feature))
        reference = _reference(extension, feature, row, "feature")
        row["reference"] = reference
        row["persistent_self"] = int(extension.IsSamePersistentID(_variant(reference), _variant(reference)))
        returned = extension.GetObjectByPersistReference3(_variant(reference))
        roundtrip = row["roundtrip"] = {"return_type": _type_name(returned)}
        if not isinstance(returned, tuple) or len(returned) != 2:
            roundtrip["raw"] = _raw_return(returned)
            raise RuntimeError("Hook persistent round trip has unexpected generated OUT shape")
        handle, status = returned
        roundtrip.update(object_type=_type_name(handle), error_code=_raw_return(status))
        if handle is None or type(status) is not int or status != 0:
            raise RuntimeError("Hook persistent round trip returned null/error status")
        roundtrip["native_same"] = int(adapter.swApp.IsSame(feature, handle))
        if row["native_self"] != 1 or row["persistent_self"] != 1 or roundtrip["native_same"] != 1:
            raise RuntimeError("Hook positive-control identity did not pass")
        row["status"] = "passed"
    except Exception as error:
        row.update(status="failed", error=repr(error))


def capture(adapter, view, expected, selected, evidence):
    """Best-effort failure evidence; never replace the original rejection."""
    records = evidence.setdefault("persistent_identity_control", {})
    models = {}
    try:
        adapter.ownership.assert_current_owned()
        drawing = _early_bound(adapter.currentModel, "IModelDoc2")
        if drawing.GetType() != 3:
            raise RuntimeError("silhouette control requires the owned drawing")
        models = {
            "drawing": drawing,
            "source": _early_bound(view.ReferencedDocument, "IModelDoc2"),
        }
        # Drawing-context queries may themselves affect the referenced source.
        # Bracket BOTH documents before even the repeated selection/face reads.
        before_errors = _dirty_flags(models, records, "before")
        if before_errors:
            raise before_errors[0]
        manager = _early_bound(drawing.SelectionManager, "ISelectionMgr")
        if manager.GetSelectedObjectCount2(-1) != 1 or manager.GetSelectedObjectType3(1, -1) != 46:
            raise RuntimeError("silhouette control requires one unchanged type46 selection")
        again = manager.GetSelectedObject6(1, -1)
        if again is None:
            raise RuntimeError("repeated native selection read returned null")
        records["repeated_selection_same"] = int(adapter.swApp.IsSame(selected, again))
        entities = {
            "expected": expected, "selected": selected, "selected_again": again,
            "expected_face": _early_bound(expected, "ISilhouetteEdge").GetFace(),
            "selected_face": _early_bound(selected, "ISilhouetteEdge").GetFace(),
        }
        for scope, model in models.items():
            persistent_controls(
                _early_bound(model.Extension, "IModelDocExtension"), entities, records[scope]
            )
        _source_feature_control(adapter, models["source"], records)
    except Exception as error:
        records["capture_error"] = repr(error)
    finally:
        # Partial evidence still needs a final observation. Each failed flag
        # remains separate from the original native capture/identity exception.
        after_errors = _dirty_flags(models, records, "after")
        if after_errors:
            records.setdefault("capture_error", repr(after_errors[0]))
        if models:
            try:
                adapter.ownership.assert_current_owned()
            except Exception as error:
                field = "final_ownership_error" if "capture_error" in records else "capture_error"
                records[field] = repr(error)
