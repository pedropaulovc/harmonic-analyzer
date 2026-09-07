"""Explicit diagnostic-only document-frame interception; never a production policy."""

from contextlib import contextmanager
from dataclasses import asdict
from enum import StrEnum
import json
from pathlib import Path
from unittest.mock import patch

from _common import _early_bound
import _drawing_prepared_template as prepared
import _drawing_template_viewport as viewports


class FramePolicy(StrEnum):
    UNCHANGED = "unchanged"
    MEASURED_RESTORE = "measured_restore"


# The order matches the bundled Position a Document Window example. These are
# IModelView document-window properties, NOT ISldWorks application-frame fields.
FRAME_FIELDS = ("FrameLeft", "FrameWidth", "FrameTop", "FrameHeight", "FrameState")


def frame(view):
    value = {name: getattr(view, name) for name in FRAME_FIELDS}
    require_frame(value)
    return value


def require_frame(value):
    if (
        set(value) != set(FRAME_FIELDS)
        or any(type(item) is not int for item in value.values())
        or value["FrameWidth"] <= 0
        or value["FrameHeight"] <= 0
        or value["FrameState"] not in (0, 1)
    ):
        raise RuntimeError("invalid native visible document frame")


def failure_input(policy, spec, template, receipt_path, receipt_sha):
    """Pin the original source/spec, not the invalid unpublished derived file."""
    if not isinstance(policy, FramePolicy):
        raise ValueError("frame control requires an explicit policy enum")
    if policy is FramePolicy.UNCHANGED:
        if receipt_path is not None or receipt_sha is not None:
            raise ValueError("failure receipt requires measured_restore")
        return None
    if (
        receipt_path is None
        or not isinstance(receipt_sha, str)
        or len(receipt_sha) != 64
        or any(c not in "0123456789abcdef" for c in receipt_sha)
    ):
        raise ValueError("measured_restore requires a pinned failure receipt")
    path = Path(receipt_path).resolve(strict=True)
    if prepared._sha(path) != receipt_sha:
        raise RuntimeError("failure receipt SHA-256 differs")
    receipt = json.loads(path.read_text(encoding="utf-8"))
    template = Path(template).resolve(strict=True)
    inputs = receipt["inputs"]
    restore = receipt["viewport_restore"]
    if (
        receipt["status"] != "failed"
        or restore["status"] != "failed"
        or restore["target"] != receipt["viewport_before"]
        or restore["before"]["visible_box_pixels"]
        == restore["target"]["visible_box_pixels"]
        or restore["before"]["orientation3"] != restore["target"]["orientation3"]
        or prepared.TemplateSpec(
            tuple(inputs["spec"]["scale"]), inputs["spec"]["decimals"]
        )
        != spec
        or prepared._sha(template) != inputs["template_sha256"]
    ):
        raise RuntimeError("failure receipt does not match this viewport/source/spec")
    return {
        "receipt": {"path": str(path), "sha256": receipt_sha},
        "original_template": {
            "path": str(template),
            "sha256": inputs["template_sha256"],
        },
        "spec": asdict(spec),
        "solidworks_revision": inputs["solidworks_revision"],
        "failed_viewport": restore,
    }


def require_failure_input_unchanged(pin):
    if pin is None:
        return
    for name in ("receipt", "original_template"):
        item = pin[name]
        if prepared._sha(item["path"]) != item["sha256"]:
            raise RuntimeError(f"immutable frame-control {name} changed")


@contextmanager
def intercept(adapter, policy, evidence):
    """One measured attempt per drift; all production functions restore on exit.

    The first control admits NO baseline documents. This avoids assuming that
    document-window FrameState changes cannot affect another SDI/MDI window.
    Each write requires the same owned model, record and native model-view handle.
    """
    if policy is FramePolicy.UNCHANGED:
        yield
        return
    if policy is not FramePolicy.MEASURED_RESTORE:
        raise ValueError("unsupported frame-control policy")
    app = adapter.swApp
    evidence.update(status="running", baseline_frames=[], restores=[])
    documents = prepared._documents(app)
    evidence["initial_inventory"] = [prepared._state(model) for model in documents]
    if documents:
        evidence.update(
            status="failed", error="empty initial document inventory required"
        )
        raise RuntimeError("measured frame control requires empty initial documents")
    original_capture, original_restore = viewports.capture, viewports.restore

    def capture(model):
        value = original_capture(model)
        value["document_frame"] = frame(_early_bound(model.ActiveView, "IModelView"))
        return value

    def restore(native_app, model, target, observation):
        row = {"status": "running", "setters": []}
        observation["frame_control"] = row
        evidence["restores"].append(row)
        try:
            if int(native_app.GetProcessID()) != int(app.GetProcessID()):
                raise RuntimeError("frame control received another native application")
            record = adapter.ownership.assert_current_owned()
            model = _early_bound(model, "IModelDoc2")
            view = _early_bound(model.ActiveView, "IModelView")

            def guard():
                current = adapter.ownership.assert_current_owned()
                documents = prepared._documents(app)
                if (
                    current is not record
                    or not prepared._same(app, record.handle, model)
                    or not prepared._same(app, view, model.ActiveView)
                    or int(model.GetType()) != 3
                    or len(documents) != 1
                    or not prepared._same(app, documents[0], model)
                ):
                    raise RuntimeError(
                        "frame control exact owned document/view changed"
                    )

            guard()
            row["before"] = capture(model)
            row["target"] = target
            target_frame = target["document_frame"]
            # Validate all five requested values before ANY write.
            require_frame(target_frame)
            if row["before"]["orientation3"] != target["orientation3"]:
                raise RuntimeError("frame control cannot change viewport orientation")
            if (
                row["before"]["document_frame"] != target_frame
                or row["before"]["visible_box_pixels"] != target["visible_box_pixels"]
            ):
                for name in FRAME_FIELDS:
                    guard()
                    write = {
                        "property": name,
                        "requested": target_frame[name],
                        "status": "started",
                    }
                    row["setters"].append(write)
                    setattr(view, name, target_frame[name])
                    guard()
                    write.update(status="returned", frame_after=frame(view))
                row["after_frame"] = capture(model)
                if row["after_frame"]["document_frame"] != target_frame:
                    raise RuntimeError(
                        "native measured document frame readback differs"
                    )
            guard()
            # Original no-resize/orientation refusal, exact scale/translation/
            # transform equality, and the caller's defaults/ink gates are intact.
            original_restore(app, model, target, observation)
            guard()
            row["status"] = "passed"
        except Exception as error:
            row.update(status="failed", error=repr(error))
            observation.update(status="failed", error=repr(error))
            raise

    errors = []
    try:
        with (
            patch.object(viewports, "capture", capture),
            patch.object(viewports, "restore", restore),
        ):
            yield
    except Exception as error:
        errors.append(error)
    # Both module bindings have already been restored, even if validation failed.
    try:
        documents = prepared._documents(app)
        evidence["final_inventory"] = [prepared._state(model) for model in documents]
        if documents:
            raise RuntimeError("frame control did not return to empty native inventory")
        evidence["final_baseline_frames"] = []
    except Exception as error:
        evidence["final_inventory_error"] = repr(error)
        errors.append(error)
    restores = evidence["restores"]
    failed = errors or any(row["status"] != "passed" for row in restores)
    pixel_restores = [
        row
        for row in restores
        if row.get("before") is not None
        and row["before"]["visible_box_pixels"] != row["target"]["visible_box_pixels"]
    ]
    writes = sum(len(row["setters"]) for row in restores)
    evidence.update(
        status="failed" if failed else "passed",
        mechanism_outcome="failed"
        if failed
        else "restored_observed_pixel_drift"
        if pixel_restores
        else "restored_measured_frame_only"
        if writes
        else "no_frame_drift_observed",
        measured_frame_write_count=writes,
        observed_pixel_drift_count=len(pixel_restores),
        errors=[repr(e) for e in errors],
    )
    if errors:
        raise ExceptionGroup("diagnostic frame control/cleanup failed", errors)
