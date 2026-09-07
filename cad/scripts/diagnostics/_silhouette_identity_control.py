"""Observe rejected silhouette identities without changing any acceptance gate.

The official IsSame example supplies self-comparisons and persistent-reference
comparisons as independent controls. Run only on the already owned diagnostic
drawing. No selection, insertion, rebuild, save or geometry conversion occurs.
"""

from _common import _early_bound


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
            lambda item=entity: _byte_reference(extension.GetPersistReference3(item)),
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
