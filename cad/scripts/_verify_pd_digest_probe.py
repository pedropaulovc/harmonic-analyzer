"""Read-only historical paper-drive evidence and paired raw-matrix experiment.

Importing this module neither initializes COM nor connects to a seat. The caller
owns the supervised session; this probe owns only documents opened after its
strictly empty GetDocuments inventory. It never repairs the saved assembly.
"""

from __future__ import annotations

import base64
import hashlib
from importlib import metadata
import json
import math
import os
from pathlib import Path, PurePosixPath
import stat
import statistics
import sys
import traceback
import time

from _com import _com_header, _com_invoke, _early_bound
import _telemetry


# Only these provenance constants differ in the baseline copy of this helper.
_ROLE = "candidate"
_SOURCE_REVISION = "1a0aac0d69cb82a2d3b8a96b4844166bfdcbaf29"
_ORIGINAL_ASSEMBLY_KEY = (
    "eb3fb517c6795f8f9fa0d15c9c823427ffd08e7a104c3b901b7113e7be7477aa"
)
_ROOT_SHA256 = "0f11e1af2fcc794bd3127275a0879e58deda4be3f22854592801913b698f3538"
_MASS_TEXT = "183988eb9b22aad9805cfdb59d5aa1d9bef39f00d069608fa78c83f50e9846a5"
_MASS_BYTE_SHA256 = "2e45d6a2da78e367a46ac11fe279e6b3140b9b7861081072c43f513f0fae843b"
_LEDGER_SHA256 = "c852c54446e25665e9f19e3925f86bc4042ae032a655746cb9311a5f3de35f2a"
_DOF_SHA256 = "9dbf5d7ed66d995a397d45fed884e837e2e141c71fb77dfc811b86d5f337aed0"
_DEFAULT = "Default"
_CHILD = "Default Simplified"
_PART_COUNT = 43
_INSTANCE_COUNT = 145
_MATRIX_BENCHMARK_PROTOCOL = "paper-drive-collapsed-raw-matrix-pairs/1"
_HISTORICAL_PROBE_PARENT = "645f955cd60a6d7580fe3f63c06a6485d28427a1"
_MATRIX_PAIR_ORDERS = ("AB", "BA", "AB", "BA", "AB", "BA")


def _require(condition, message):
    if not condition:
        raise RuntimeError(message)


def _error(report, location, error, *, required=True):
    evidence = {
        "location": location,
        "required": required,
        "type": type(error).__name__,
        "message": str(error),
        "traceback": "".join(traceback.format_exception(error)),
    }
    report["errors"].append(evidence)
    return evidence


def _clear_exception_frames(error):
    """Release frame locals across an exception graph without changing its evidence."""
    pending = [error]
    seen = set()
    while pending:
        current = pending.pop()
        identity = id(current)
        if identity in seen:
            continue
        seen.add(identity)
        traceback.clear_frames(current.__traceback__)
        for linked in (current.__cause__, current.__context__):
            if linked is not None:
                pending.append(linked)


def _capture(target, key, operation, report, location, *, required=True):
    """Retain an individual read failure, not a substituted native answer."""
    try:
        target[key] = operation()
    except Exception as error:
        target[key] = None
        evidence = _error(report, f"{location}.{key}", error, required=required)
        target.setdefault("read_errors", []).append(evidence)
        return False
    return True


def _required_errors(report):
    return [error for error in report["errors"] if error["required"]]


def _raise_required(report, location, *, except_locations=()):
    failures = [
        error
        for error in _required_errors(report)
        if error["location"] not in except_locations
    ]
    _require(
        not failures,
        f"{location}: required evidence failed at "
        + ", ".join(error["location"] for error in failures),
    )


def _boolean(value):
    _require(type(value) is bool, f"expected scalar boolean, received {value!r}")
    return value


def _integer(value):
    _require(type(value) is int, f"expected scalar integer, received {value!r}")
    return value


def _string(value, *, nonempty=False):
    _require(type(value) is str, f"expected string, received {value!r}")
    _require(not nonempty or value != "", "required nonempty string was empty")
    return value


def _strings(value):
    _require(
        type(value) in (tuple, list), "expected string collection, not null/scalar"
    )
    return [_string(item, nonempty=True) for item in value]


def _number(value):
    _require(type(value) in (int, float), f"expected finite number, received {value!r}")
    converted = float(value)  # Match the historical producer's float conversion.
    _require(math.isfinite(converted), f"non-finite native number: {converted!r}")
    return {"value": converted, "hex": converted.hex()}


def _numbers(value, count):
    _require(
        type(value) in (tuple, list) and len(value) == count,
        f"expected exactly {count} numeric array entries",
    )
    numbers = [_number(item) for item in value]
    return {
        "values": [item["value"] for item in numbers],
        "hex": [item["hex"] for item in numbers],
    }


def _bound(raw, interface):
    _require(raw is not None, f"{interface} dispatch was null")
    return _early_bound(raw, interface)


def _path_key(path):
    return os.path.normcase(str(Path(path).resolve()))


def _absolute_native_path(value):
    value = _string(value, nonempty=True)
    _require(Path(value).is_absolute(), f"native document path was relative: {value!r}")
    return _path_key(value)


def _matrix(raw, *, nullable=False):
    if raw is None:
        _require(nullable, "required native transform was null")
        return {"status": "absent", "values": None, "hex": None}
    transform = _bound(raw, "IMathTransform")
    try:
        evidence = _numbers(transform.ArrayData, 16)
        evidence["status"] = "present"
        return evidence
    finally:
        transform = raw = None


def _file_before(path, before, *, retain_bytes=False):
    key = str(path)
    before[key] = {"sha256": None, "byte_count": None}
    data = path.read_bytes()
    before[key].update(sha256=hashlib.sha256(data).hexdigest(), byte_count=len(data))
    if retain_bytes:
        before[key]["bytes_base64"] = base64.b64encode(data).decode("ascii")
    return data


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        _require(key not in result, f"duplicate JSON object key: {key!r}")
        result[key] = value
    return result


def _authenticate(worker_root, source, report):
    """Authenticate the original ledger before trusting any of its child paths."""
    before = report["files_before"]
    fixed = {
        "root": (source, _ROOT_SHA256),
        "mass_sidecar": (
            source.parent / ".pd-paper-drive.massprops.sha",
            _MASS_BYTE_SHA256,
        ),
        "input_ledger": (source.parent / ".pd-paper-drive.inputs.json", _LEDGER_SHA256),
        "dof_sidecar": (source.parent / ".pd-paper-drive.dof.json", _DOF_SHA256),
        "root_execution": (source.parent / ".pd-paper-drive.execution", None),
    }
    data = {}
    authentication = report["authentication"]
    for label, (path, expected) in fixed.items():
        item = {"path": str(path), "expected_sha256": expected}
        authentication[label] = item
        try:
            data[label] = _file_before(path, before, retain_bytes=label != "root")
            item["actual_sha256"] = before[str(path)]["sha256"]
            if expected is not None:
                _require(
                    item["actual_sha256"] == expected,
                    f"original {label} SHA256 mismatch",
                )
            if label in ("mass_sidecar", "root_execution"):
                text = data[label].decode("ascii").strip()
                item["text"] = text
                wanted = _MASS_TEXT if label == "mass_sidecar" else _ROOT_SHA256
                _require(text == wanted, f"original {label} text mismatch")
            item["authenticated"] = True
        except Exception as error:
            item["authenticated"] = False
            _error(report, f"authentication.{label}", error)

    # Even failed fixed-artifact authentication retains every fixed prehash.
    _raise_required(report, "original root/sidecar authentication")
    ledger = json.loads(
        data["input_ledger"].decode("utf-8"), object_pairs_hook=_unique_object
    )
    _require(
        type(ledger) is dict and type(ledger.get("inputs")) is dict,
        "invalid input ledger",
    )
    inputs = ledger["inputs"]
    _require(
        all(type(tag) is str and type(digest) is str for tag, digest in inputs.items()),
        "ledger inputs must map strings to strings",
    )
    authentication["ledger_unique_input_count"] = len(inputs)
    _require(len(inputs) == 293, "original ledger must contain 293 unique inputs")
    part_dir = (worker_root / "cad/out/sldprt").resolve()
    _require(
        part_dir.is_relative_to(worker_root), "worker part directory escapes checkout"
    )
    native_tags = sorted(tag for tag in inputs if tag.lower().endswith(".sldprt"))
    token_tags = sorted(tag for tag in inputs if tag.lower().endswith(".execution"))
    _require(
        len(native_tags) == _PART_COUNT, "ledger must contain exactly 43 native parts"
    )
    _require(
        len(token_tags) == _PART_COUNT, "ledger must contain exactly 43 child tokens"
    )

    def local_part_path(tag):
        relative = PurePosixPath(tag)
        _require(
            not relative.is_absolute()
            and ".." not in relative.parts
            and "\\" not in tag,
            f"noncanonical or escaping ledger path: {tag!r}",
        )
        _require(
            relative.parent == PurePosixPath("cad/out/sldprt"),
            f"foreign ledger path: {tag!r}",
        )
        path = (worker_root / tag).resolve()
        _require(
            path.parent == part_dir and path.is_relative_to(worker_root),
            f"escaping child: {tag!r}",
        )
        return path

    native_paths = {tag: local_part_path(tag) for tag in native_tags}
    token_paths = {tag: local_part_path(tag) for tag in token_tags}
    _require(
        len(set(native_paths.values())) == _PART_COUNT, "aliased native part paths"
    )
    _require(
        len(set(token_paths.values())) == _PART_COUNT, "aliased execution token paths"
    )
    expected_tokens = {
        f"cad/out/sldprt/.{path.stem}.execution" for path in native_paths.values()
    }
    _require(
        set(token_tags) == expected_tokens, "native/token closure pairing mismatch"
    )
    authentication["parts"] = parts = []
    for tag, path in native_paths.items():
        token_tag = f"cad/out/sldprt/.{path.stem}.execution"
        token_path = token_paths[token_tag]
        item = {
            "native_path": str(path),
            "ledger_native_tag": tag,
            "token_path": str(token_path),
            "ledger_token_tag": token_tag,
            "ledger_token_md5": inputs[token_tag],
            "authenticated": False,
        }
        parts.append(item)
        native_data = token_data = None
        try:
            native_data = _file_before(path, before)
        except Exception as error:
            _error(report, f"authentication.{tag}.native_bytes", error)
        try:
            token_data = _file_before(token_path, before, retain_bytes=True)
        except Exception as error:
            _error(report, f"authentication.{tag}.token_bytes", error)
        if native_data is None or token_data is None:
            continue
        try:
            item["native_sha256"] = hashlib.sha256(native_data).hexdigest()
            item["token_text"] = token_data.decode("ascii").strip()
            canonical = token_data
            if b"\0" not in canonical[:8000]:
                canonical = canonical.replace(b"\r\n", b"\n")
            item["canonical_token_md5"] = hashlib.md5(canonical).hexdigest()
            _require(
                item["canonical_token_md5"] == inputs[token_tag],
                f"{token_tag}: ledger MD5 mismatch",
            )
            _require(
                item["native_sha256"] == item["token_text"],
                f"{tag}: native SHA/token mismatch",
            )
            item["authenticated"] = True
        except Exception as error:
            _error(report, f"authentication.{tag}", error)
    _raise_required(report, "native child authentication")
    authentication["complete"] = True
    return {_path_key(path) for path in native_paths.values()}


def _inventory(app, report, location):
    """GetDocuments includes hidden/library residents; never filter them away."""
    raw_documents = document = raw = None
    rows = []
    start = len(_required_errors(report))
    report["inventories"].append({"phase": location, "documents": rows})
    try:
        raw_documents = app.GetDocuments()
        if raw_documents is None:
            return rows
        _require(type(raw_documents) in (tuple, list), "GetDocuments returned a scalar")
        for index, raw in enumerate(raw_documents):
            row = {"index": index}
            rows.append(row)
            try:
                document = _bound(raw, "IModelDoc2")
                _capture(
                    row,
                    "path",
                    lambda: _string(document.GetPathName()),
                    report,
                    location,
                )
                _capture(
                    row, "title", lambda: _string(document.GetTitle()), report, location
                )
                if row.get("path"):
                    _capture(
                        row,
                        "path_key",
                        lambda: _absolute_native_path(row["path"]),
                        report,
                        location,
                    )
                else:
                    row["path_key"] = None
            except Exception as error:
                _error(report, f"{location}.document[{index}]", error)
            finally:
                document = raw = None
        _require(
            len(_required_errors(report)) == start,
            f"{location}: incomplete native inventory",
        )
        return rows
    finally:
        raw_documents = document = raw = None


def _active_identity(app):
    document = _bound(app.ActiveDoc, "IModelDoc2")
    try:
        path = _string(document.GetPathName(), nonempty=True)
        return {
            "path": path,
            "path_key": _absolute_native_path(path),
            "title": _string(document.GetTitle(), nonempty=True),
        }
    finally:
        document = None


def _configuration_metadata(model, assembly, name, report, location):
    result = {"requested_name": name}
    configuration = parent = None
    try:
        configuration = _bound(model.GetConfigurationByName(name), "IConfiguration")
        _capture(
            result,
            "name",
            lambda: _string(configuration.Name, nonempty=True),
            report,
            location,
        )
        _capture(
            result, "comment", lambda: _string(configuration.Comment), report, location
        )
        _capture(
            result,
            "derived",
            lambda: _boolean(configuration.IsDerived()),
            report,
            location,
        )
        try:
            parent = configuration.GetParent()
            if parent is None:
                result["parent"] = None
                result["parent_status"] = "absent"
                _require(
                    result.get("derived") is not True,
                    "derived configuration has no parent",
                )
            else:
                parent = _bound(parent, "IConfiguration")
                result["parent"] = _string(parent.Name, nonempty=True)
                result["parent_status"] = "present"
        except Exception as error:
            result["parent_status"] = "error"
            _error(report, f"{location}.parent", error)
        _capture(
            result,
            "exploded_view_count",
            lambda: _integer(assembly.GetExplodedViewCount2(name)),
            report,
            location,
        )
        try:
            names = assembly.GetExplodedViewNames2(name)
            if names is None:
                _require(
                    result.get("exploded_view_count") == 0,
                    "null exploded views with nonzero/unknown count",
                )
                result["exploded_view_names_status"] = "legitimate_null"
                names = []
            else:
                names = _strings(names)
                result["exploded_view_names_status"] = "present"
            result["exploded_view_names"] = names
            _require(
                len(names) == result.get("exploded_view_count"),
                "exploded view name/count mismatch",
            )
            _require(len(set(names)) == len(names), "duplicate exploded view names")
            result["exploded_views"] = views = []
            for view in names:
                owner = {"name": view}
                views.append(owner)
                _capture(
                    owner,
                    "owner_configuration",
                    lambda: _string(
                        assembly.GetExplodedViewConfigurationName(view), nonempty=True
                    ),
                    report,
                    location,
                )
        except Exception as error:
            _error(report, f"{location}.exploded_views", error)
    except Exception as error:
        _error(report, location, error)
    finally:
        configuration = parent = None
    return result


def _state(model, extension, assembly, app, report, location):
    state = {}
    manager = configuration = selection = None
    _capture(
        state,
        "root_path",
        lambda: _string(model.GetPathName(), nonempty=True),
        report,
        location,
    )
    _capture(
        state,
        "root_title",
        lambda: _string(model.GetTitle(), nonempty=True),
        report,
        location,
    )
    _capture(state, "active_document", lambda: _active_identity(app), report, location)
    _capture(
        state,
        "opened_read_only",
        lambda: _boolean(model.IsOpenedReadOnly()),
        report,
        location,
    )
    _capture(
        state,
        "needs_rebuild",
        lambda: _integer(extension.NeedsRebuild2),
        report,
        location,
    )
    _capture(
        state, "save_flag", lambda: _boolean(model.GetSaveFlag()), report, location
    )
    _capture(
        state,
        "model_is_exploded",
        lambda: _boolean(model.IsExploded()),
        report,
        location,
    )
    try:
        exploded = extension.IsExploded()
        _require(
            type(exploded) is tuple and len(exploded) == 2,
            "Extension.IsExploded must return (bool, str)",
        )
        state["extension_is_exploded"] = {
            "is_exploded": _boolean(exploded[0]),
            "view_name": _string(exploded[1]),
        }
        if exploded[1] != "":
            _capture(
                state,
                "active_exploded_view_owner",
                lambda: _string(
                    assembly.GetExplodedViewConfigurationName(exploded[1]),
                    nonempty=True,
                ),
                report,
                location,
            )
        else:
            state["active_exploded_view_owner"] = None
            state["active_exploded_view_owner_status"] = "no_named_active_view"
    except Exception as error:
        state["extension_is_exploded"] = None
        _error(report, f"{location}.extension_is_exploded", error)
    _capture(
        state,
        "enable_presentation",
        lambda: _boolean(assembly.EnablePresentation),
        report,
        location,
    )
    try:
        manager = _bound(model.ConfigurationManager, "IConfigurationManager")
        configuration = _bound(manager.ActiveConfiguration, "IConfiguration")
        _capture(
            state,
            "active_configuration",
            lambda: _string(configuration.Name, nonempty=True),
            report,
            location,
        )
        if _capture(
            state,
            "display_states",
            lambda: _strings(configuration.GetDisplayStates()),
            report,
            location,
            required=False,
        ):
            states = state["display_states"]
            state["active_display_state"] = states[0] if states else None
            state["active_display_state_status"] = (
                "present" if states else "empty_collection"
            )
        else:
            state["active_display_state"] = None
            state["active_display_state_status"] = "read_failed"
    except Exception as error:
        _error(report, f"{location}.active_configuration", error)
    finally:
        manager = configuration = None
    try:
        selection = _bound(model.SelectionManager, "ISelectionMgr")
        _capture(
            state,
            "selection_count",
            lambda: _integer(selection.GetSelectedObjectCount2(-1)),
            report,
            location,
        )
    except Exception as error:
        _error(report, f"{location}.selection_count", error)
    finally:
        selection = None
    return state


def _mass(extension, report, location, *, required):
    result = {"status": "incomplete"}
    mass = None
    start = len(report["errors"])
    try:
        mass = _bound(extension.CreateMassProperty(), "IMassProperty")
        # The order is the producer's order, not a second adapter mass read.
        _capture(
            result,
            "volume",
            lambda: _number(mass.Volume),
            report,
            location,
            required=required,
        )
        _capture(
            result,
            "surface_area",
            lambda: _number(mass.SurfaceArea),
            report,
            location,
            required=required,
        )
        _capture(
            result,
            "mass",
            lambda: _number(mass.Mass),
            report,
            location,
            required=required,
        )
        _capture(
            result,
            "center_of_mass",
            lambda: _numbers(mass.CenterOfMass, 3),
            report,
            location,
            required=required,
        )
        _capture(
            result,
            "inertia",
            lambda: _numbers(mass.GetMomentOfInertia(0), 9),
            report,
            location,
            required=required,
        )
        if len(report["errors"]) == start:
            result["status"] = "complete"
        else:
            result["reason"] = "one or more direct mass-property reads failed"
    except Exception as error:
        result["reason"] = "direct CreateMassProperty failed or returned null"
        _error(report, location, error, required=required)
    finally:
        mass = None
    return result


def _components(assembly, allowed_parts, report, location):
    result = {"instances": [], "loaded_model_authentication_complete": True}
    raw_components = raw = component = loaded = None
    try:
        raw_components = assembly.GetComponents(True)
        _require(
            type(raw_components) in (tuple, list), "GetComponents(True) was null/scalar"
        )
        result["returned_count"] = len(raw_components)
        for index, raw in enumerate(raw_components):
            row = {"enumeration_index": index}
            result["instances"].append(row)
            here = f"{location}.instance[{index}]"
            try:
                component = _bound(raw, "IComponent2")
                _capture(
                    row,
                    "name",
                    lambda: _string(component.Name2, nonempty=True),
                    report,
                    here,
                )
                _capture(
                    row,
                    "reference_path",
                    lambda: _string(component.GetPathName(), nonempty=True),
                    report,
                    here,
                )
                _capture(
                    row,
                    "referenced_configuration",
                    lambda: _string(component.ReferencedConfiguration, nonempty=True),
                    report,
                    here,
                )
                _capture(
                    row,
                    "suppression",
                    lambda: _integer(component.GetSuppression2()),
                    report,
                    here,
                )
                _capture(
                    row, "fixed", lambda: _boolean(component.IsFixed()), report, here
                )
                _capture(
                    row, "visible", lambda: _integer(component.Visible), report, here
                )
                try:
                    loaded = component.GetModelDoc2()
                    if loaded is None:
                        row["loaded_model"] = {
                            "status": "null",
                            "path": None,
                            "authenticated": False,
                        }
                        raise RuntimeError(
                            "GetModelDoc2 returned null; loaded identity authentication incomplete (no resolution attempted)"
                        )
                    loaded = _bound(loaded, "IModelDoc2")
                    identity = row["loaded_model"] = {
                        "status": "nonnull",
                        "authenticated": False,
                    }
                    identity["path"] = _string(loaded.GetPathName(), nonempty=True)
                    identity["path_key"] = _absolute_native_path(identity["path"])
                    _require(
                        identity["path_key"] in allowed_parts,
                        "actual loaded model is outside authenticated own 43-part closure",
                    )
                    identity["authenticated"] = True
                except Exception as error:
                    result["loaded_model_authentication_complete"] = False
                    row.setdefault(
                        "loaded_model",
                        {"status": "read_failed", "path": None, "authenticated": False},
                    )
                    _error(report, f"{here}.loaded_model", error)
                finally:
                    loaded = None
                _capture(
                    row,
                    "transform",
                    lambda: _matrix(component.Transform2),
                    report,
                    here,
                )
                _capture(
                    row,
                    "total_transform_without_presentation",
                    lambda: _matrix(component.GetTotalTransform(False)),
                    report,
                    here,
                )
                _capture(
                    row,
                    "total_transform_with_presentation",
                    lambda: _matrix(component.GetTotalTransform(True)),
                    report,
                    here,
                )
                _capture(
                    row,
                    "presentation_transform",
                    lambda: _matrix(component.PresentationTransform, nullable=True),
                    report,
                    here,
                )
            except Exception as error:
                _error(report, here, error)
            finally:
                component = loaded = raw = None
        names = [row.get("name") for row in result["instances"]]
        result["distinct_name_count"] = len(
            set(name for name in names if name is not None)
        )
        _require(len(names) == _INSTANCE_COUNT, "expected all 145 top-level instances")
        _require(
            None not in names and len(set(names)) == _INSTANCE_COUNT,
            "expected 145 distinct nonempty instance names",
        )
    except Exception as error:
        _error(report, location, error)
    finally:
        raw_components = raw = component = loaded = None
    return result


def _check_state(state, source_key, configuration, *, clean):
    _require(
        _absolute_native_path(state.get("root_path")) == source_key,
        "root path is not authenticated own root",
    )
    active = state.get("active_document")
    _require(
        type(active) is dict and active.get("path_key") == source_key,
        "active document is not authenticated own root",
    )
    _require(
        state.get("opened_read_only") is True, "probe model is not opened read-only"
    )
    _require(
        state.get("active_configuration") == configuration,
        f"active configuration is not {configuration!r}",
    )
    if clean:
        _require(
            state.get("needs_rebuild") == 0,
            "as-open Default requests a rebuild; no fallback permitted",
        )
        _require(
            state.get("selection_count") == 0,
            "as-open Default has selections; full-model mass is ambiguous",
        )


def _snapshot(
    model, extension, assembly, app, source_key, allowed_parts, report, configuration
):
    location = "default" if configuration == _DEFAULT else "child"
    snapshot = report[location] = {"configuration_requested": configuration}
    snapshot["before"] = _state(
        model, extension, assembly, app, report, f"{location}.before"
    )
    _capture(
        snapshot,
        "configuration_names",
        lambda: _strings(model.GetConfigurationNames()),
        report,
        location,
    )
    snapshot["configurations"] = {
        name: _configuration_metadata(
            model, assembly, name, report, f"{location}.configuration[{name}]"
        )
        for name in (_DEFAULT, _CHILD)
    }
    _check_state(
        snapshot["before"], source_key, configuration, clean=configuration == _DEFAULT
    )
    names = snapshot.get("configuration_names")
    _require(
        type(names) is list and len(set(names)) == len(names),
        "incomplete/duplicate configuration names",
    )
    _require(
        [name for name in names if not name.endswith(" Simplified")] == [_DEFAULT],
        "Default must be the only nonsimplified configuration",
    )
    _require(_CHILD in names, "saved child configuration is missing")
    if configuration == _DEFAULT:
        snapshot["mass"] = _mass(extension, report, f"{location}.mass", required=True)
    elif (
        snapshot["before"].get("needs_rebuild") == 0
        and snapshot["before"].get("selection_count") == 0
    ):
        snapshot["mass"] = _mass(extension, report, f"{location}.mass", required=False)
    else:
        snapshot["mass"] = {
            "status": "unavailable",
            "reason": "as-activated child needs rebuild or has nonzero/unknown selections; no repair attempted",
        }
    snapshot["components"] = _components(
        assembly, allowed_parts, report, f"{location}.components"
    )
    snapshot["after"] = _state(
        model, extension, assembly, app, report, f"{location}.after"
    )
    _check_state(
        snapshot["after"], source_key, configuration, clean=configuration == _DEFAULT
    )
    if configuration == _CHILD:
        snapshot["geometry_state"] = (
            "as-activated, unreconciled child"
            if snapshot["before"].get("needs_rebuild") != 0
            or snapshot["after"].get("needs_rebuild") != 0
            else "as-activated child; no explicit rebuild"
        )
    return snapshot


def _historical_digest(snapshot):
    mass = snapshot["mass"]
    _require(mass["status"] == "complete", "Default mass read is incomplete")
    inertia = mass["inertia"]["values"]
    mass_row = (
        _DEFAULT,
        round(float(mass["mass"]["value"]), 6),
        round(float(mass["volume"]["value"]) * 1e9, 3),
        round(float(mass["surface_area"]["value"]) * 1e6, 3),
        tuple(
            round(float(value) * 1000, 4) for value in mass["center_of_mass"]["values"]
        ),
        tuple(round(float(inertia[index]), 4) for index in (0, 4, 8, 1, 2, 5)),
    )
    pose_rows = sorted(
        (
            row["name"],
            tuple(round(float(value), 6) for value in row["transform"]["values"][0:9]),
            tuple(round(float(value), 4) for value in row["transform"]["values"][9:12]),
        )
        for row in snapshot["components"]["instances"]
    )
    rows = [mass_row]
    rows.extend((_DEFAULT, *row) for row in pose_rows)
    payload = repr(rows)
    digest = hashlib.sha256(payload.encode("utf-8")).hexdigest()
    return {
        "original_sidecar_text": _MASS_TEXT,
        "reproduced_sha256": digest,
        "historical_digest_reproduced": digest == _MASS_TEXT,
        "payload": payload,
        "row_repr": [repr(row) for row in rows],
        "translation_units": "metres, rounded to four decimal places",
        "inertia_order": [0, 4, 8, 1, 2, 5],
    }


def _benchmark_matrix_values(value):
    """Common timed validator: primitives only, with no hex/report allocation."""
    _require(
        type(value) in (tuple, list) and len(value) == 16,
        "benchmark requires exactly 16 numeric array entries",
    )
    values = []
    for item in value:
        _require(type(item) in (int, float), "benchmark matrix entry is not numeric")
        converted = float(item)
        _require(math.isfinite(converted), "benchmark matrix entry is not finite")
        values.append(converted)
    return tuple(values)


def _benchmark_matrix_evidence(matrix):
    return {"values": list(matrix), "hex": [value.hex() for value in matrix]}


def _benchmark_read_matrix(component, arm, dispatch_type):
    raw = transform = data = None
    try:
        if arm == "A":
            raw = component.GetTotalTransform(True)
            transform = _bound(raw, "IMathTransform")
            data = transform.ArrayData
        else:
            _require(arm == "B", "unknown benchmark arm")
            raw = _com_invoke(component, "IComponent2", "GetTotalTransform", True)
            _require(raw is not None, "benchmark total transform was null")
            _require(
                isinstance(raw, dispatch_type),
                "raw total transform was not a PythonCOM PyIDispatch",
            )
            data = _com_invoke(raw, "IMathTransform", "ArrayData")
        return _benchmark_matrix_values(data)
    except BaseException as error:
        # Completed Invoke/Dispatch frames can otherwise retain the transform.
        _clear_exception_frames(error)
        raise
    finally:
        raw = transform = data = component = None


def _benchmark_compare_matrices(reference, actual, names, evidence):
    _require(
        len(reference) == len(actual) == len(names),
        "benchmark matrix comparison has incomplete inventory",
    )
    evidence.update(compared_components=len(names), values_equal=True, hex_equal=True)
    mismatches = evidence["mismatches"] = []
    for name, expected, observed in zip(names, reference, actual):
        _require(len(expected) == len(observed) == 16, "incomplete matrix comparison")
        values_equal = expected == observed
        hex_equal = [v.hex() for v in expected] == [v.hex() for v in observed]
        evidence["values_equal"] &= values_equal
        evidence["hex_equal"] &= hex_equal
        if not values_equal or not hex_equal:
            mismatches.append(
                {
                    "name": name,
                    "expected": _benchmark_matrix_evidence(expected),
                    "observed": _benchmark_matrix_evidence(observed),
                }
            )
    _require(not mismatches, "benchmark full-16-value/hex comparison failed")


def _benchmark_primitive_equal(before, after):
    _require(
        type(before) in (dict, list, tuple, str, int, float, bool, type(None))
        and type(after) in (dict, list, tuple, str, int, float, bool, type(None)),
        "benchmark state contains a nonprimitive object",
    )
    if type(before) is not type(after):
        return False
    if type(before) is dict:
        return before.keys() == after.keys() and all(
            _benchmark_primitive_equal(value, after[key])
            for key, value in before.items()
        )
    if type(before) in (tuple, list):
        return len(before) == len(after) and all(
            _benchmark_primitive_equal(left, right)
            for left, right in zip(before, after)
        )
    if type(before) is float:
        return (
            math.isfinite(before)
            and math.isfinite(after)
            and before == after
            and before.hex() == after.hex()
        )
    return before == after


def _benchmark_require_equal(before, after, evidence):
    evidence["equal"] = _benchmark_primitive_equal(before, after)
    if not evidence["equal"]:
        evidence.update(before=before, after=after)
    _require(evidence["equal"], "benchmark state changed")


def _benchmark_document_state(state, source_key):
    keys = (
        "root_path", "root_title", "active_document", "opened_read_only",
        "needs_rebuild", "save_flag", "model_is_exploded", "extension_is_exploded",
        "active_exploded_view_owner", "enable_presentation",
        "active_configuration", "selection_count",
    )
    _require(all(key in state for key in keys), "incomplete benchmark document state")
    _check_state(state, source_key, _DEFAULT, clean=True)
    _string(state["root_title"], nonempty=True)
    _integer(state["needs_rebuild"])
    _integer(state["selection_count"])
    for key in (
        "opened_read_only", "save_flag", "model_is_exploded", "enable_presentation"
    ):
        _boolean(state[key])
    active = state["active_document"]
    _string(active["path"], nonempty=True)
    _string(active["title"], nonempty=True)
    exploded = state["extension_is_exploded"]
    _require(type(exploded) is dict, "missing benchmark exploded-state observation")
    _boolean(exploded["is_exploded"])
    _string(exploded["view_name"])
    _require(
        state["model_is_exploded"] is False and exploded["is_exploded"] is False,
        "benchmark requires collapsed Default; no repair permitted",
    )
    if state["active_exploded_view_owner"] is None:
        _require(exploded["view_name"] == "", "missing named exploded-view owner")
    else:
        _string(state["active_exploded_view_owner"], nonempty=True)
    return {key: state[key] for key in keys}


def _benchmark_component_state(component, allowed_parts):
    loaded = None
    try:
        loaded = _bound(component.GetModelDoc2(), "IModelDoc2")
        loaded_path = _string(loaded.GetPathName(), nonempty=True)
        loaded_key = _absolute_native_path(loaded_path)
        _require(loaded_key in allowed_parts, "benchmark loaded model is unauthenticated")
        return {
            "name": _string(component.Name2, nonempty=True),
            "reference_path": _string(component.GetPathName(), nonempty=True),
            "referenced_configuration": _string(
                component.ReferencedConfiguration, nonempty=True
            ),
            "suppression": _integer(component.GetSuppression2()),
            "fixed": _boolean(component.IsFixed()),
            "visible": _integer(component.Visible),
            "loaded_model": {
                "status": "nonnull", "authenticated": True,
                "path": loaded_path, "path_key": loaded_key,
            },
            "transform": _matrix(component.Transform2),
            "total_transform_without_presentation": _matrix(
                component.GetTotalTransform(False)
            ),
            "total_transform_with_presentation": _matrix(
                component.GetTotalTransform(True)
            ),
            "presentation_transform": _matrix(
                component.PresentationTransform, nullable=True
            ),
        }
    finally:
        loaded = component = None


def _benchmark_observe(model, extension, assembly, app, source_key, report, location):
    start = len(report["errors"])
    state = _state(model, extension, assembly, app, report, location)
    report["raw_matrix_benchmark"].setdefault("document_observations", {})[location] = state
    _require(
        not any(error["required"] for error in report["errors"][start:]),
        "benchmark required state read failed",
    )
    return _benchmark_document_state(state, source_key)


def _benchmark_controls(cohort, names, dispatch_type, reference, benchmark):
    controls = benchmark["controls"]
    references = []
    component = None
    try:
        for index, component in enumerate(cohort):
            control = {"name": names[index], "status": "observing", "comparisons": {}}
            controls["components"].append(control)
            acquired = {}
            try:
                for label in ("A1", "A2", "B", "A3"):
                    arm = label[0]
                    controls["attempted_reads"][arm] += 1
                    acquired[label] = _benchmark_read_matrix(component, arm, dispatch_type)
                    controls["completed_reads"][arm] += 1
                for label, matrix in acquired.items():
                    comparison = control["comparisons"][label] = {}
                    _benchmark_compare_matrices(
                        [reference[index]], [matrix], [names[index]], comparison
                    )
                references.append(acquired["A1"])
                control["reference"] = _benchmark_matrix_evidence(acquired["A1"])
                control["raw_PyIDispatch_receipt"] = True
                control["status"] = "complete"
            finally:
                if control["status"] != "complete":
                    control["status"] = "failed"
                    control["available_reads"] = {
                        label: _benchmark_matrix_evidence(matrix)
                        for label, matrix in acquired.items()
                    }
        controls["status"] = "complete"
        return references
    finally:
        component = None


def _benchmark_pass(cohort, arm, dispatch_type, record):
    matrices = []
    component = None
    attempted = 0
    complete = False
    started = time.perf_counter_ns()
    try:
        for component in cohort:
            attempted += 1
            matrices.append(_benchmark_read_matrix(component, arm, dispatch_type))
        complete = True
        return matrices
    except BaseException as error:
        _clear_exception_frames(error)
        raise
    finally:
        component = None
        elapsed = time.perf_counter_ns() - started
        # Everything below, including evidence conversion, is outside timing.
        record.update(
            status="complete" if complete else "failed",
            attempted_reads=attempted,
            completed_reads=len(matrices),
            elapsed_ns=elapsed,
        )
        if complete:
            hex_rows = [[value.hex() for value in matrix] for matrix in matrices]
            record["matrix_hex_sha256"] = hashlib.sha256(
                json.dumps(hex_rows, separators=(",", ":")).encode("ascii")
            ).hexdigest()
        else:
            record["partial_matrices"] = [
                _benchmark_matrix_evidence(matrix) for matrix in matrices
            ]


def _benchmark_rounds(cohort, names, dispatch_type, reference, benchmark):
    for index, order in enumerate(_MATRIX_PAIR_ORDERS, 1):
        pair = {"round": index, "order": order, "arms": {}, "status": "failed"}
        benchmark["pairs"].append(pair)
        matrices = {}
        for arm in order:
            record = pair["arms"][arm] = {"status": "not_started"}
            matrices[arm] = _benchmark_pass(cohort, arm, dispatch_type, record)
        for label, expected, actual in (
            ("pair", matrices["A"], matrices["B"]),
            ("A_against_control", reference, matrices["A"]),
            ("B_against_control", reference, matrices["B"]),
        ):
            comparison = pair[label] = {}
            _benchmark_compare_matrices(expected, actual, names, comparison)
        a_ns = pair["arms"]["A"]["elapsed_ns"]
        b_ns = pair["arms"]["B"]["elapsed_ns"]
        _require(a_ns > 0 and b_ns > 0, "benchmark timer did not advance")
        pair.update(
            status="complete",
            a_minus_b_seconds=(a_ns - b_ns) / 1e9,
            one_minus_b_over_a=1.0 - b_ns / a_ns,
        )
    summary = benchmark["summary"] = {}
    for label, orders in (("all", ("AB", "BA")), ("AB", ("AB",)), ("BA", ("BA",))):
        pairs = [pair for pair in benchmark["pairs"] if pair["order"] in orders]
        a_ns = sum(pair["arms"]["A"]["elapsed_ns"] for pair in pairs)
        b_ns = sum(pair["arms"]["B"]["elapsed_ns"] for pair in pairs)
        summary[label] = {
            "pairs": len(pairs),
            "A_seconds": a_ns / 1e9, "B_seconds": b_ns / 1e9,
            "a_minus_b_seconds": (a_ns - b_ns) / 1e9,
            "one_minus_b_over_a": 1.0 - b_ns / a_ns,
            "median_paired_difference_seconds": statistics.median(
                pair["a_minus_b_seconds"] for pair in pairs
            ),
        }


def _benchmark_report():
    return {
        "protocol": _MATRIX_BENCHMARK_PROTOCOL,
        "historical_probe_parent_revision": _HISTORICAL_PROBE_PARENT,
        "status": "not_started",
        "scope": "warm same-seat collapsed-PD matrix microbenchmark, not DT or build speed",
        "rpc_saving": "not_assessed",
        "ordering_limit": "balanced ordering reduces but does not eliminate temporal/cache bias",
        "timer": {
            "clock": "time.perf_counter_ns",
            "includes": "full-inventory acquisition, common primitive validation, result retention, transform release",
            "excludes": "collection, authentication, state reads, hex/equality/checksums, evidence and summaries",
            "B_only_overhead": "per-read isinstance(raw, PythonCOM dispatch type); not subtracted",
        },
        "expected_controls": {"A": 435, "B": 145},
        "expected_measured_reads": {"A": 870, "B": 870},
        "controls": {
            "status": "not_started", "sequence": ["A1", "A2", "B", "A3"],
            "attempted_reads": {"A": 0, "B": 0},
            "completed_reads": {"A": 0, "B": 0}, "components": [],
        },
        "pairs": [],
        "measured_attempted_reads": {"A": 0, "B": 0},
        "measured_completed_reads": {"A": 0, "B": 0},
        "state_observation_reads": "excluded from control and measured-read counts",
        "document_observations": {},
    }


def _run_matrix_benchmark(
    model, extension, assembly, app, source_key, allowed_parts, default, report
):
    """Observe only: no save, rebuild, activation, selection or presentation writes."""
    import pythoncom
    from solidworks_mcp.adapters import sw_type_info

    benchmark = report["raw_matrix_benchmark"]
    cohort = []
    names = []
    raw_components = raw = component = None
    primary = None
    try:
        _require(
            report["historical_digest"]["historical_digest_reproduced"] is True,
            "benchmark requires original Default digest reproduction",
        )
        _raise_required(report, "benchmark admission")
        _require(
            report["authentication"].get("complete") is True
            and len(allowed_parts) == _PART_COUNT
            and len(report["files_before"]) == 91,
            "benchmark requires the complete authenticated 91-file closure",
        )
        benchmark["status"] = "observing"
        dispatch_type = pythoncom.TypeIIDs[pythoncom.IID_IDispatch]
        benchmark["dispatch_receipt_contract"] = (
            f"{dispatch_type.__module__}.{dispatch_type.__name__}"
        )
        source_files = {
            "probe": Path(__file__).resolve(),
            "com_helpers": Path(sys.modules[_early_bound.__module__].__file__).resolve(),
            "binding_helpers": Path(sw_type_info.__file__).resolve(),
            "generated_wrapper": Path(sw_type_info.__file__).resolve().parent
            / "_generated/sldworks_2026.py",
        }
        benchmark["source_identity"] = {
            "artifact_source_revision": _SOURCE_REVISION,
            "python_version": sys.version,
            "pywin32_version": metadata.version("pywin32"),
            "pythoncom_module": str(pythoncom.__file__),
            "files": {
                label: {"path": str(path), "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
                for label, path in source_files.items()
            },
        }
        for interface, member, expected in (
            ("IComponent2", "GetTotalTransform", (77, 0, 1, (9, 0), ((11, 1),))),
            ("IMathTransform", "ArrayData", (3, 0, 2, (12, 0), ())),
        ):
            actual = _com_header(interface, member)
            _require(actual == expected, f"unexpected generated {interface}.{member} header")
            benchmark.setdefault("generated_headers", {})[f"{interface}.{member}"] = actual
        benchmark["state_before"] = before = {
            "document": _benchmark_observe(
                model, extension, assembly, app, source_key, report, "benchmark.before"
            ),
            "components": [],
        }
        _benchmark_require_equal(
            _benchmark_document_state(default["after"], source_key),
            before["document"],
            benchmark.setdefault("default_document_matches", {}),
        )
        captured = {row["name"]: row for row in default["components"]["instances"]}
        _require(len(captured) == _INSTANCE_COUNT, "incomplete captured Default inventory")
        raw_components = assembly.GetComponents(True)
        _require(
            type(raw_components) in (tuple, list)
            and len(raw_components) == _INSTANCE_COUNT,
            "benchmark requires all 145 components",
        )
        for raw in raw_components:
            component = _bound(raw, "IComponent2")
            _require(
                sw_type_info.is_early_bound(component, "IComponent2")
                and isinstance(component._oleobj_, dispatch_type),
                "benchmark component is not a generated wrapper over real PyIDispatch",
            )
            cohort.append(component)
            row = _benchmark_component_state(component, allowed_parts)
            name = row["name"]
            _require(name in captured and name not in names, "benchmark cohort identity mismatch")
            _benchmark_require_equal(
                {key: captured[name][key] for key in row},
                row,
                benchmark.setdefault("default_component_matches", {}).setdefault(name, {}),
            )
            names.append(name)
            before["components"].append(row)
        raw_components = raw = component = None
        _require(len(names) == _INSTANCE_COUNT, "incomplete benchmark cohort")
        benchmark["component_order"] = names
        benchmark["generated_component_dispatch_receipts"] = len(cohort)
        sensitive = [
            row["name"] for row in before["components"]
            if not _benchmark_primitive_equal(
                row["total_transform_without_presentation"],
                row["total_transform_with_presentation"],
            )
        ]
        benchmark["presentation_coverage"] = {
            "configuration": _DEFAULT, "model_collapsed": True,
            "presentation_sensitive_components": sensitive,
            "true_false_equal_count": len(names) - len(sensitive),
            "coverage": (
                "already-present true/false presentation distinction"
                if sensitive
                else "collapsed-only coverage; presentation inclusion was not discriminated"
            ),
        }
        reference = [
            tuple(row["total_transform_with_presentation"]["values"])
            for row in before["components"]
        ]
        benchmark["controls"]["status"] = "observing"
        reference = _benchmark_controls(cohort, names, dispatch_type, reference, benchmark)
        _benchmark_rounds(cohort, names, dispatch_type, reference, benchmark)
    except BaseException as error:
        primary = error
        _error(report, "raw_matrix_benchmark", error)
        _clear_exception_frames(error)
    finally:
        # State reads are untimed and attempted even after a failed control/round.
        try:
            benchmark["state_after"] = after = {
                "document": _benchmark_observe(
                    model, extension, assembly, app, source_key, report, "benchmark.after"
                ),
                "components": [],
            }
            for component in cohort:
                after["components"].append(_benchmark_component_state(component, allowed_parts))
            if "state_before" in benchmark:
                _benchmark_require_equal(
                    benchmark["state_before"], after,
                    benchmark.setdefault("state_unchanged", {}),
                )
            _require(len(cohort) == _INSTANCE_COUNT, "benchmark cohort remained incomplete")
        except BaseException as error:
            _error(report, "raw_matrix_benchmark.post_state", error)
            _clear_exception_frames(error)
            if primary is None:
                primary = error
        finally:
            raw_components = raw = component = None
            cohort.clear()
            benchmark["component_handles_released_before_child_activation"] = True
        for arm in ("A", "B"):
            for kind in ("attempted", "completed"):
                benchmark[f"measured_{kind}_reads"][arm] = sum(
                    pair["arms"].get(arm, {}).get(f"{kind}_reads", 0)
                    for pair in benchmark["pairs"]
                )
        if primary is None and not (
            benchmark["controls"]["completed_reads"] == benchmark["expected_controls"]
            and benchmark["measured_completed_reads"] == benchmark["expected_measured_reads"]
            and len(benchmark["pairs"]) == 6
        ):
            primary = RuntimeError("benchmark completed-read counts were incomplete")
            _error(report, "raw_matrix_benchmark.counts", primary)
        benchmark["status"] = "complete" if primary is None else "failed"
        if primary is not None:
            if benchmark["controls"]["status"] == "observing":
                benchmark["controls"]["status"] = "failed"
            raise primary


def _close_owned(app, allowed, source_key, report):
    cleanup = report["cleanup"]
    cleanup["close_calls"] = []
    inventory = _inventory(app, report, "cleanup.before_close")
    # CloseDoc can also unload non-active hidden docs: refuse ALL closing if a
    # foreign document appears, rather than claiming arbitrary-doc preservation.
    bound = len(allowed) + 1
    for iteration in range(bound):
        if not inventory:
            cleanup["empty_ending_inventory"] = True
            cleanup["status"] = "complete"
            return
        _require(
            all(row.get("path_key") in allowed for row in inventory),
            "unexpected foreign document; no further CloseDoc permitted",
        )
        titles = [row.get("title") for row in inventory]
        _require(
            all(type(title) is str and title != "" for title in titles),
            "cannot close an empty/unknown title",
        )
        _require(
            len(set(titles)) == len(titles),
            "ambiguous document titles; cleanup refused",
        )
        chosen = next(
            (row for row in inventory if row["path_key"] == source_key), inventory[0]
        )
        call = {
            "iteration": iteration,
            "title": chosen["title"],
            "path": chosen["path"],
            "count_before": len(inventory),
        }
        cleanup["close_calls"].append(call)
        app.CloseDoc(chosen["title"])  # Generated VT_VOID: NEVER truth-test.
        remaining = _inventory(app, report, f"cleanup.after_close[{iteration}]")
        call["count_after"] = len(remaining)
        _require(
            len(remaining) < len(inventory),
            "CloseDoc inventory did not strictly decrease",
        )
        _require(
            all(row.get("path_key") != chosen["path_key"] for row in remaining),
            "exact-title CloseDoc left its document resident",
        )
        _require(
            {row.get("path_key") for row in remaining}.issubset(
                {row.get("path_key") for row in inventory}
            ),
            "new native document appeared during cleanup",
        )
        inventory = remaining
    raise RuntimeError("bounded native cleanup exhausted without an empty inventory")


def _hash_after(report):
    after = report["files_after"]
    for path, before in report["files_before"].items():
        item = after[path] = {"sha256": None, "byte_count": None, "unchanged": False}
        try:
            data = Path(path).read_bytes()
            item.update(sha256=hashlib.sha256(data).hexdigest(), byte_count=len(data))
            item["unchanged"] = (
                item["sha256"] == before["sha256"]
                and item["byte_count"] == before["byte_count"]
            )
            _require(
                item["unchanged"], f"protected artifact changed/unmeasured: {path}"
            )
        except Exception as error:
            _error(report, f"preservation.{path}", error)
    # Reassert immutable constants as well as before/after equality.
    for label in ("root", "mass_sidecar", "input_ledger", "dof_sidecar"):
        identity = report["authentication"].get(label)
        if identity is not None:
            actual = after.get(identity["path"], {}).get("sha256")
            if actual != identity["expected_sha256"]:
                _error(
                    report,
                    f"preservation.constant.{label}",
                    RuntimeError("original SHA256 not preserved"),
                )
    for label, wanted in (
        ("root_execution", _ROOT_SHA256),
        ("mass_sidecar", _MASS_TEXT),
    ):
        identity = report["authentication"].get(label)
        if identity is not None:
            try:
                text = Path(identity["path"]).read_bytes().decode("ascii").strip()
                after[identity["path"]]["text"] = text
                _require(text == wanted, f"original {label} text not preserved")
            except Exception as error:
                _error(report, f"preservation.text.{label}", error)
    report["preservation_complete"] = bool(after) and all(
        item["unchanged"] for item in after.values()
    )


def _report_bytes(report):
    return (
        json.dumps(report, allow_nan=False, ensure_ascii=True, indent=2) + "\n"
    ).encode("utf-8")


def _safe_report_destination(report_path, report):
    """Refuse aliases before any JSON write, including failure finalization."""
    destination = report.setdefault("report_destination", {})
    try:
        worker_root = Path(__file__).resolve().parents[2]
        expected = worker_root / "cad/out/reports/pd-paper-drive-digest-probe.json"
        _require(
            Path(report_path) == expected,
            "report output is not its fixed worker destination",
        )
        _require(
            expected.resolve() == expected,
            "unsafe expected report output: symlink or junction alias",
        )
        try:
            existing = expected.lstat()
        except FileNotFoundError:
            existing = None
        if existing is not None:
            _require(
                stat.S_ISREG(existing.st_mode),
                "unsafe expected report output: not a regular file",
            )
            _require(
                existing.st_nlink == 1,
                "unsafe expected report output: multiply-linked file",
            )
    except BaseException as error:
        destination.update(status="unsafe_expected_output", reason=str(error))
        raise
    destination.update(status="safe_expected_output", path=str(expected))
    return expected


def _write_report(report_path, report):
    report_path = _safe_report_destination(report_path, report)
    data = _report_bytes(report)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path = _safe_report_destination(report_path, report)
    with report_path.open("wb") as stream:
        _require(stream.write(data) == len(data), "short evidence JSON write")
        stream.flush()
        os.fsync(stream.fileno())
    return data


def _emit_report(data):
    # Hashes cover decoded bytes, NOT base64 text. Every numbered message is
    # self-identifying, so ordinary captured task.log suffices for reconstruction.
    chunk_bytes = 1536  # At most 2048 ASCII base64 characters per message.
    count = (len(data) + chunk_bytes - 1) // chunk_bytes
    whole = hashlib.sha256(data).hexdigest()
    prefix = f"PD_DIGEST_PROBE_JSON v=1 role={_ROLE} report_sha256={whole} chunks={count} bytes={len(data)}"
    # Required task-log evidence is a protocol, not severity-filtered INFO:
    # ordinary farm leaves default to warning-only console output.
    print(
        f"{prefix} encoding=base64 chunk_sha256=decoded_bytes BEGIN",
        file=sys.stderr,
        flush=True,
    )
    for index in range(count):
        chunk = data[index * chunk_bytes : (index + 1) * chunk_bytes]
        encoded = base64.b64encode(chunk).decode("ascii")
        checksum = hashlib.sha256(chunk).hexdigest()
        print(
            f"{prefix} chunk={index + 1}/{count} chunk_sha256={checksum} data={encoded}",
            file=sys.stderr,
            flush=True,
        )
    print(f"{prefix} END", file=sys.stderr, flush=True)


@_telemetry.traced("verify.paper_drive_saved_digest_probe")
async def inspect_saved_paper_drive(adapter, source: Path, report_path: Path) -> None:
    """Observe authenticated saved Default and the unreconciled in-memory child.

    Any required failure escapes this entrypoint before normal verification can
    continue. Native-equivalence approval is deliberately not this probe's job.
    """
    report = {
        "schema": "paper-drive-historical-digest-probe/1",
        "role": _ROLE,
        "source_revision": _SOURCE_REVISION,
        "raw_matrix_benchmark": _benchmark_report(),
        "original_assembly_cache_key": _ORIGINAL_ASSEMBLY_KEY,
        "original_cache_epoch": "3",
        "original_cache_salt": "sw2024-sp3",
        "probe_status": "observing",
        "native_equivalence": {
            "verdict": "not_assessed",
            "reason": "observation completeness and historical digest reproduction are not native equivalence",
        },
        "source_argument": str(source),
        "python_version": sys.version,
        "process_id": os.getpid(),
        "computer_name": os.environ.get("COMPUTERNAME"),
        "report_path": str(report_path),
        "authentication": {"complete": False},
        "files_before": {},
        "files_after": {},
        "inventories": [],
        "errors": [],
        "cleanup": {"status": "not_started", "empty_ending_inventory": None},
        "historical_digest": {"historical_digest_reproduced": None},
    }
    app = model = extension = assembly = opened = raw_model = None
    primary = None
    initial_empty = open_attempted = False
    allowed_parts = set()
    source_key = None
    requested_report_path = report_path
    safe_report_path = None
    report["report_destination"] = {
        "status": "not_validated",
        "caller_argument_valid": False,
    }
    # A bad caller argument may use a separately validated fixed destination.
    # An unsafe fixed destination must remain stderr-only, including retries.
    report_path = (
        Path(__file__).resolve().parents[2]
        / "cad/out/reports/pd-paper-drive-digest-probe.json"
    )
    report["report_path_argument"] = str(requested_report_path)
    report["report_path"] = str(report_path)
    try:
        worker_root = Path(__file__).resolve().parents[2]
        safe_report_path = _safe_report_destination(report_path, report)
        source = Path(source).resolve()
        requested_report_path = Path(requested_report_path).resolve()
        report["report_destination"]["caller_argument_valid"] = (
            requested_report_path == safe_report_path
        )
        _require(
            source == worker_root / "cad/out/sldasm/pd-paper-drive.SLDASM",
            "probe source is not its own worker checkout root",
        )
        _require(
            report["report_destination"]["caller_argument_valid"],
            "probe report argument must match its own declared output",
        )
        report["worker_root"] = str(worker_root)
        report["source"] = str(source)
        source_key = _path_key(source)
        allowed_parts = _authenticate(worker_root, source, report)
        app = _bound(adapter.swApp, "ISldWorks")
        initial = _inventory(app, report, "initial")
        _require(
            len(initial) == 0,
            "probe requires EMPTY GetDocuments inventory, including library residents; existing documents will not be closed",
        )
        initial_empty = True
        open_attempted = True
        opened = app.OpenDoc6(str(source), 2, 3, "", 0, 0)
        _require(
            type(opened) is tuple and len(opened) == 3,
            "generated OpenDoc6 must return (model, int, int)",
        )
        raw_model, errors, warnings = opened
        report["open"] = {
            "model_null": raw_model is None,
            "document_type": 2,
            "options": 3,
            "configuration": "",
        }
        _capture(report["open"], "errors", lambda: _integer(errors), report, "open")
        _capture(report["open"], "warnings", lambda: _integer(warnings), report, "open")
        model = _bound(raw_model, "IModelDoc2")
        # Capture the exact root title/read-only result before refusing load codes.
        _capture(
            report["open"],
            "title",
            lambda: _string(model.GetTitle(), nonempty=True),
            report,
            "open",
        )
        _capture(
            report["open"],
            "read_only",
            lambda: _boolean(model.IsOpenedReadOnly()),
            report,
            "open",
        )
        _require(report["open"]["errors"] == 0, "OpenDoc6 reported load errors")
        _require(
            report["open"].get("read_only") is True, "OpenDoc6 did not open read-only"
        )
        extension = _bound(model.Extension, "IModelDocExtension")
        assembly = _bound(model, "IAssemblyDoc")
        default = _snapshot(
            model, extension, assembly, app, source_key, allowed_parts, report, _DEFAULT
        )
        _raise_required(report, "untouched Default observation")
        report["historical_digest"] = historical = _historical_digest(default)
        if not historical["historical_digest_reproduced"]:
            _error(
                report,
                "historical_digest.mismatch",
                RuntimeError(
                    "as-open Default did not reproduce its own original massprops sidecar"
                ),
            )
        report["default_checkpoint_complete"] = True
        _write_report(safe_report_path, report)
        if historical["historical_digest_reproduced"]:
            _run_matrix_benchmark(
                model, extension, assembly, app, source_key, allowed_parts, default, report
            )
        else:
            report["raw_matrix_benchmark"].update(
                status="not_admitted", reason="original Default digest did not reproduce"
            )

        # Digest mismatch alone does not discard a safe, completed Default dump
        # or prevent the discriminating child observation. No adapter activation.
        _raise_required(
            report,
            "before child activation",
            except_locations=("historical_digest.mismatch",),
        )
        switch = report["child_activation"] = {"requested_configuration": _CHILD}
        switch["before"] = _state(
            model, extension, assembly, app, report, "child_activation.before"
        )
        _check_state(switch["before"], source_key, _DEFAULT, clean=True)
        _raise_required(
            report,
            "before direct child switch",
            except_locations=("historical_digest.mismatch",),
        )
        try:
            switch["returned_success"] = _boolean(model.ShowConfiguration2(_CHILD))
        finally:
            switch["after"] = _state(
                model, extension, assembly, app, report, "child_activation.after"
            )
        _require(
            switch["returned_success"] is True,
            "direct ShowConfiguration2 child activation failed",
        )
        _check_state(switch["after"], source_key, _CHILD, clean=False)
        child = _snapshot(
            model, extension, assembly, app, source_key, allowed_parts, report, _CHILD
        )
        default_names = {row["name"] for row in default["components"]["instances"]}
        child_names = {row.get("name") for row in child["components"]["instances"]}
        _require(
            default_names == child_names,
            "child instance inventory differs from captured Default",
        )
        _raise_required(report, "complete saved paper-drive observation")
    except BaseException as error:
        primary = error
        _error(report, "observation", error)
        # Completed traceback frames may otherwise retain mass/component/config
        # wrappers until after CloseDoc. The report retains their text, not COM.
        _clear_exception_frames(error)
    finally:
        model = extension = assembly = opened = raw_model = None
        try:
            adapter.currentModel = None
            report["cleanup"]["adapter_current_model_cleared"] = True
        except BaseException as error:
            _error(report, "cleanup.adapter_currentModel", error)
            _clear_exception_frames(error)
        if initial_empty and open_attempted and app is not None:
            try:
                _close_owned(app, allowed_parts | {source_key}, source_key, report)
            except BaseException as error:
                report["cleanup"]["status"] = "failed"
                _error(report, "cleanup.close_owned", error)
                _clear_exception_frames(error)
        else:
            report["cleanup"]["status"] = "no_close_attempted"
            report["cleanup"]["reason"] = (
                "no probe open after a confirmed empty inventory; preexisting documents are not owned"
            )
        if app is not None:
            try:
                ending = _inventory(app, report, "ending")
                report["cleanup"]["empty_ending_inventory"] = len(ending) == 0
                if initial_empty:
                    _require(len(ending) == 0, "probe left native documents resident")
            except BaseException as error:
                report["cleanup"]["status"] = "failed"
                _error(report, "cleanup.ending_inventory", error)
                _clear_exception_frames(error)
        app = None
        try:
            _hash_after(report)
        except BaseException as error:
            _error(report, "preservation", error)
            _clear_exception_frames(error)

    if primary is None and _required_errors(report):
        primary = RuntimeError(
            "paper-drive probe required observation/authentication/cleanup/preservation evidence failed"
        )
    report["probe_status"] = "failed" if primary is not None else "complete"
    if (
        safe_report_path is None
        or report["report_destination"]["status"] != "safe_expected_output"
    ):
        report["json_publication"] = "skipped_unsafe_expected_output"
        serialized = _report_bytes(report)
    else:
        try:
            serialized = _write_report(safe_report_path, report)
        except BaseException as error:
            _error(report, "publication.required_json_write", error)
            report["probe_status"] = "failed"
            if primary is None:
                primary = error
            serialized = _report_bytes(report)
    try:
        _emit_report(serialized)
    except BaseException as error:
        _error(report, "publication.task_log_chunks", error)
        report["probe_status"] = "failed"
        if primary is None:
            primary = error
        # Revalidate again inside _write_report; never retry an unsafe output.
        if (
            safe_report_path is not None
            and report["report_destination"]["status"] == "safe_expected_output"
        ):
            try:
                _write_report(safe_report_path, report)
            except BaseException as write_error:
                _error(report, "publication.failed_json_write", write_error)
    if primary is not None:
        primary.add_note(f"Paper-drive probe failed; evidence output: {report_path}")
        if len(_required_errors(report)) > 1:
            primary.add_note(
                "All required/cleanup/publication errors are retained in JSON/task-log evidence: "
                + ", ".join(error["location"] for error in _required_errors(report))
            )
        raise primary
