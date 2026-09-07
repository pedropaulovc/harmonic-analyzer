"""Diagnostic frame experiment, using the real cache and document-ownership scopes."""

from copy import deepcopy
import json
from types import SimpleNamespace

import pytest

from diagnostics import _owned_native_documents as owned
from diagnostics import _prepared_frame_control as frames
from diagnostics import probe_prepared_template_cache as probe
from test_owned_native_documents_drawing import Model, native  # noqa: F401
from test_prepared_template_cache_probe_drawing import scene  # noqa: F401


@pytest.fixture
def frame_scene(scene, monkeypatch, tmp_path):  # noqa: F811
    scene.native.app.documents.clear()
    scene.native.app.ActiveDoc = scene.native.adapter.currentModel = None
    scene.baseline.clear()
    native_setup = probe.sheet_setup.new_project_drawing
    native_create = probe.sheet_setup.new_drawing
    writes = []
    measured = dict(zip(frames.FRAME_FIELDS, (2216, 1608, 141, 854, 0), strict=True))

    def install(model):
        base = type(model.ActiveView)

        class FrameView(base):
            def __getattr__(self, name):
                if name in frames.FRAME_FIELDS:
                    return self._frame[name]
                raise AttributeError(name)

            def __setattr__(self, name, value):
                if name not in frames.FRAME_FIELDS:
                    return super().__setattr__(name, value)
                writes.append((name, value))
                if scene.faults.get("frame_exception") == name:
                    raise RuntimeError("native frame setter rejected")
                if scene.faults.get("frame_clamp") != name:
                    self._frame[name] = value
                if callback := scene.faults.get("after_frame_setter"):
                    callback(model, name)

            def GetVisibleBox(self):
                f = self._frame
                lost = 1 if scene.faults.get("pixel_box_stuck") else 0
                return (
                    f["FrameLeft"],
                    f["FrameTop"],
                    f["FrameLeft"] + f["FrameWidth"] - lost,
                    f["FrameTop"] + f["FrameHeight"] - lost,
                )

            @property
            def Transform(self):
                values = list(super().Transform.ArrayData)
                values[12] *= self._frame["FrameHeight"] / measured["FrameHeight"]
                return SimpleNamespace(ArrayData=values)

        model.ActiveView.__class__ = FrameView
        model.ActiveView._frame = deepcopy(measured)
        if len(scene.created) > 1:
            model.ActiveView._frame["FrameWidth"] -= 1
            model.ActiveView._frame["FrameHeight"] -= 1
        return model

    def setup(adapter, **kwargs):
        model, sheet = native_setup(adapter, **kwargs)
        return install(model), sheet

    monkeypatch.setattr(probe.sheet_setup, "new_project_drawing", setup)
    monkeypatch.setattr(
        probe.sheet_setup,
        "new_drawing",
        lambda *a, **k: install(native_create(*a, **k)),
    )
    monkeypatch.setattr(probe, "printed_witness", lambda *a: {"printed": "exact"})
    monkeypatch.setattr(probe, "compare_printed", lambda *a: {"changed_pixel_count": 0})
    monkeypatch.setattr(frames, "_early_bound", lambda value, _: value)
    monkeypatch.setattr(probe.viewports, "_early_bound", lambda value, _: value)
    before = {"visible_box_pixels": [2216, 141, 3824, 995], "orientation3": [1.0] * 16}
    after = deepcopy(before)
    after["visible_box_pixels"] = [2216, 141, 3823, 994]
    receipt = tmp_path / "failed-production-receipt.json"
    receipt.write_text(
        json.dumps(
            {
                "status": "failed",
                "viewport_before": before,
                "inputs": {
                    "spec": {"scale": [2, 1], "decimals": 2},
                    "solidworks_revision": "34.3.0",
                    "template_sha256": probe.prepared._sha(scene.original),
                },
                "viewport_restore": {
                    "status": "failed",
                    "before": after,
                    "target": before,
                },
            }
        )
    )
    options = {
        "viewport": probe.Viewport.CAPTURED,
        "printed_format": probe.PrintedFormat.COMPARE,
        "frame_policy": frames.FramePolicy.MEASURED_RESTORE,
        "failure_receipt": receipt,
        "failure_receipt_sha256": probe.prepared._sha(receipt),
    }
    return SimpleNamespace(
        scene=scene, writes=writes, measured=measured, receipt=receipt, options=options
    )


def test_unchanged_production_policy_rejects_one_pixel_drift_without_frame_writes(
    frame_scene,
):
    f = frame_scene
    with pytest.raises(ExceptionGroup, match="prepared-template cache control"):
        f.scene.run(
            viewport=probe.Viewport.CAPTURED, printed_format=probe.PrintedFormat.COMPARE
        )
    report, _ = f.scene.report()
    assert "visible pixel box differs" in report["error"]
    assert f.writes == []
    assert report["frame_policy"] == "unchanged" and report["frame_control"] == {}


def test_selected_measured_frame_restores_exact_defaults_prints_and_cache_hit(
    frame_scene,
):
    f = frame_scene
    original = (probe.viewports.capture, probe.viewports.restore)
    f.scene.run(**f.options)
    report, _ = f.scene.report()
    assert report["status"] == "passed"
    assert report["frame_control"]["status"] == "passed"
    assert (
        report["frame_control"]["mechanism_outcome"] == "restored_observed_pixel_drift"
    )
    assert report["frame_control"]["measured_frame_write_count"] == 20
    assert report["frame_control"]["observed_pixel_drift_count"] == 4
    assert (
        report["frame_control"]["initial_inventory"]
        == report["frame_control"]["final_inventory"]
        == []
    )
    assert f.writes == list(f.measured.items()) * 4
    assert len(f.scene.created) == 5 and len(f.scene.saves) == 1
    assert f.scene.native.app.closes == f.scene.created
    assert f.scene.native.app.documents == []
    assert report["accessors"][0]["artifacts"] == report["accessors"][1]["artifacts"]
    assert all(
        r["defaults"] == report["trials"][0]["defaults"] for r in report["trials"]
    )
    assert all(
        r["printed_delta"]["changed_pixel_count"] == 0 for r in report["trials"][1:]
    )
    assert all(r["status"] == "passed" for r in report["frame_control"]["restores"])
    assert original == (probe.viewports.capture, probe.viewports.restore)


@pytest.mark.parametrize(
    "fault,value,expected",
    [
        ("frame_clamp", "FrameWidth", "frame readback differs"),
        ("frame_exception", "FrameWidth", "frame setter rejected"),
        ("translation_readback", True, "viewport readback differs"),
        ("independent_extent_drift", True, "raw defaults did not persist exactly"),
        ("orientation", True, "orientation"),
    ],
)
def test_frame_control_never_waives_native_or_raw_default_failure(
    frame_scene, fault, value, expected
):
    f = frame_scene
    original = (probe.viewports.capture, probe.viewports.restore)
    f.scene.faults[fault] = value
    with pytest.raises(ExceptionGroup) as caught:
        f.scene.run(**f.options)
    assert expected in repr(caught.value)
    report, _ = f.scene.report()
    assert report["status"] == "failed"
    if fault != "independent_extent_drift":
        assert report["frame_control"]["status"] == "failed"
    assert len(report["accessors"]) == 1
    assert f.scene.native.app.documents == []
    assert original == (probe.viewports.capture, probe.viewports.restore)
    if fault == "orientation":
        assert f.writes == []


def test_remaining_pixel_drift_is_not_accepted_after_measured_frame_setters(
    frame_scene,
):
    f = frame_scene

    def leave_pixel_box_wrong(model, field):
        f.scene.faults["pixel_box_stuck"] = True

    f.scene.faults["after_frame_setter"] = leave_pixel_box_wrong
    with pytest.raises(ExceptionGroup) as caught:
        f.scene.run(**f.options)
    assert "visible pixel box differs" in repr(caught.value)
    assert f.writes == list(f.measured.items())
    assert f.scene.viewport_calls == []  # No scale/vector write after refused frame.


def test_initial_user_document_is_neither_resized_nor_closed(frame_scene):
    f = frame_scene
    user = Model(None, title="User dirty drawing", dirty=True)
    f.scene.native.app.documents.append(user)
    f.scene.native.app.ActiveDoc = user
    original = (probe.viewports.capture, probe.viewports.restore)
    with pytest.raises(ExceptionGroup) as caught:
        f.scene.run(**f.options)
    assert "empty initial documents" in repr(caught.value)
    assert f.scene.created == f.scene.native.app.closes == f.writes == []
    assert f.scene.native.app.documents == [user]
    assert original == (probe.viewports.capture, probe.viewports.restore)


@pytest.mark.parametrize("field", frames.FRAME_FIELDS)
def test_exact_ownership_checked_after_each_frame_setter_before_next_write(
    frame_scene, field
):
    f = frame_scene
    original = (probe.viewports.capture, probe.viewports.restore)

    def switch_active(model, name):
        if name == field:
            f.scene.native.app.ActiveDoc = None

    f.scene.faults["after_frame_setter"] = switch_active
    with pytest.raises(ExceptionGroup) as caught:
        f.scene.run(**f.options)
    assert "owned active" in repr(caught.value)
    assert [name for name, _ in f.writes] == list(
        frames.FRAME_FIELDS[: frames.FRAME_FIELDS.index(field) + 1]
    )
    assert f.scene.viewport_calls == []
    assert original == (probe.viewports.capture, probe.viewports.restore)


@pytest.mark.parametrize(
    "change", ["hash", "spec", "template", "equal_box", "orientation"]
)
def test_failure_receipt_pins_reject_other_inputs_before_any_creation(
    frame_scene, change
):
    f = frame_scene
    receipt = json.loads(f.receipt.read_text())
    if change == "spec":
        receipt["inputs"]["spec"]["decimals"] = 3
    if change == "template":
        receipt["inputs"]["template_sha256"] = "0" * 64
    if change == "equal_box":
        receipt["viewport_restore"]["before"] = deepcopy(
            receipt["viewport_restore"]["target"]
        )
    if change == "orientation":
        receipt["viewport_restore"]["before"]["orientation3"][0] = -1
    f.receipt.write_text(json.dumps(receipt) + "\n")
    if change != "hash":
        f.options["failure_receipt_sha256"] = probe.prepared._sha(f.receipt)
    with pytest.raises(RuntimeError):
        f.scene.run(**f.options)
    assert not f.scene.created and not f.writes


@pytest.mark.parametrize(
    "name,value",
    [
        ("FrameWidth", 0),
        ("FrameHeight", -1),
        ("FrameState", 2),
        ("FrameLeft", 1.5),
        ("FrameTop", True),
    ],
)
def test_malformed_or_minimized_native_frames_fail_loud(frame_scene, name, value):
    values = deepcopy(frame_scene.measured)
    values[name] = value
    with pytest.raises(RuntimeError, match="invalid native visible document frame"):
        frames.frame(SimpleNamespace(**values))


def test_parent_forwards_explicit_frame_receipt_under_existing_seat(
    frame_scene, monkeypatch
):
    import dodo

    f = frame_scene
    calls = []
    monkeypatch.setattr(dodo, "_run", lambda *a, **k: calls.append((a, k)))
    probe.main(
        [
            "--expected-pid",
            "123",
            "--scale",
            "2",
            "1",
            "--decimals",
            "2",
            "--viewport",
            "captured",
            "--printed-format",
            "compare",
            "--frame-policy",
            "measured_restore",
            "--failure-receipt",
            str(f.receipt),
            "--failure-receipt-sha256",
            f.options["failure_receipt_sha256"],
        ]
    )
    command = calls[0][0][0]
    assert command[command.index("--frame-policy") + 1] == "measured_restore"
    assert command[command.index("--failure-receipt") + 1] == str(f.receipt.resolve())
    assert (
        command[command.index("--failure-receipt-sha256") + 1]
        == f.options["failure_receipt_sha256"]
    )
    assert calls[0][1]["com"] is True
    assert not f.scene.created


def test_primary_and_final_inventory_errors_both_survive_and_patches_restore(native):  # noqa: F811
    adapter = owned.DiagnosticAdapter(native.adapter)
    original = (probe.viewports.capture, probe.viewports.restore)
    evidence = {}
    with pytest.raises(ExceptionGroup) as caught:
        with frames.intercept(adapter, frames.FramePolicy.MEASURED_RESTORE, evidence):
            native.app.documents.append(Model(None, title="Unexpected user document"))
            raise RuntimeError("primary native validation rejected")
    assert len(caught.value.exceptions) == 2
    assert "primary native validation rejected" in repr(caught.value)
    assert "empty native inventory" in repr(caught.value)
    assert evidence["status"] == "failed" and len(evidence["errors"]) == 2
    assert original == (probe.viewports.capture, probe.viewports.restore)
    assert native.app.closes == []


@pytest.mark.parametrize(
    "option,value",
    [
        ("frame_policy", "measured_restore"),
        ("viewport", probe.Viewport.NORMAL),
        ("printed_format", probe.PrintedFormat.SKIP),
        ("failure_receipt", None),
        ("failure_receipt_sha256", None),
    ],
)
def test_frame_selection_requires_explicit_complete_control_before_creation(
    frame_scene, option, value
):
    f = frame_scene
    f.options[option] = value
    with pytest.raises(ValueError):
        f.scene.run(**f.options)
    assert not f.scene.created


def test_failure_receipt_is_rechecked_after_each_phase_not_just_at_start(
    frame_scene, monkeypatch
):
    f = frame_scene
    original = probe.printed_witness

    def change_receipt(*args):
        result = original(*args)
        f.receipt.write_text(f.receipt.read_text() + "\n")
        return result

    monkeypatch.setattr(probe, "printed_witness", change_receipt)
    with pytest.raises(ExceptionGroup) as caught:
        f.scene.run(**f.options)
    assert "frame-control receipt changed" in repr(caught.value)
    report, _ = f.scene.report()
    assert not report["accessors"] and not f.scene.saves and not f.writes


def test_default_interceptor_is_exact_noop_without_any_native_inventory(native):  # noqa: F811
    def forbidden():
        raise AssertionError("default unexpectedly touched native inventory")

    native.app.GetDocuments = forbidden
    original = (probe.viewports.capture, probe.viewports.restore)
    evidence = {}
    with frames.intercept(native.adapter, frames.FramePolicy.UNCHANGED, evidence):
        assert original == (probe.viewports.capture, probe.viewports.restore)
    assert evidence == {}


def test_frame_control_rejects_other_native_revision_before_creating_files(frame_scene):
    f = frame_scene
    f.scene.native.app.RevisionNumber = lambda: "34.4.0"
    with pytest.raises(RuntimeError, match="revision differs"):
        f.scene.run(**f.options)
    assert not f.scene.created
