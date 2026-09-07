"""A cold real accessor, without the prior diagnostic's warmup or extra setters."""

# Pytest injects the imported fixtures by these deliberately matching names.
# ruff: noqa: F811

import json
from pathlib import Path

import pytest

from diagnostics import _prepared_frame_control as frames
from diagnostics import probe_prepared_template_cache as probe
from test_owned_native_documents_drawing import native  # noqa: F401
from test_prepared_template_cache_probe_drawing import scene  # noqa: F401
from test_prepared_frame_control_drawing import frame_scene  # noqa: F401


def options(f):
    return {
        "scope": probe.Scope.ACCESSOR_ONLY,
        "failure_receipt": f.receipt,
        "failure_receipt_sha256": f.options["failure_receipt_sha256"],
    }


@pytest.mark.parametrize(
    "policy", [None, frames.FramePolicy.CAPTURE_ONLY, frames.FramePolicy.UNCHANGED]
)
def test_accessor_first_reproduces_actual_no_resize_failure_without_priming(
    frame_scene, policy, monkeypatch
):
    f = frame_scene
    original = (probe.viewports.capture, probe.viewports.restore)

    def forbidden(*a, **k):
        raise AssertionError(
            "accessor-only performed an extra factory or printed trial"
        )

    monkeypatch.setattr(probe, "trial", forbidden)
    monkeypatch.setattr(probe, "printed_witness", forbidden)
    with pytest.raises(ExceptionGroup) as caught:
        f.scene.run(**options(f), frame_policy=policy)
    assert "visible pixel box differs" in repr(caught.value)
    report, _ = f.scene.report()
    assert report["sequence"] == "accessor_only"
    assert report["scope"] == "production_preparation_accessor_only"
    assert report["frame_policy"] == (policy or frames.FramePolicy.CAPTURE_ONLY).value
    assert report["trials"] == []
    assert [row["kind"] for row in report["accessors"]] == ["miss"]
    assert [row["operation"] for row in report["operation_scopes"]] == [
        "create",
        "save_as",
        "create",
    ]
    assert all("viewport_control" not in row for row in report["operation_scopes"])
    assert len(f.scene.created) == 2 and len(f.scene.saves) == 1
    assert f.scene.native.app.closes == f.scene.created
    assert f.scene.native.app.documents == []
    assert f.writes == []
    # Only the earlier owned redraw; pixel refusal still prevents scale/pan writes.
    assert f.scene.viewport_calls == [("redraw", 1.0)]
    retained = list(Path(report["cache_root"]).glob("pending-*/receipt.json"))
    assert len(retained) == 1
    receipt = json.loads(retained[0].read_text())
    assert receipt["status"] == "failed"
    assert receipt["viewport_before"]["visible_box_pixels"] == [2216, 141, 3824, 995]
    assert receipt["viewport_restore"]["before"]["visible_box_pixels"] == [
        2216,
        141,
        3823,
        994,
    ]
    assert "after" not in receipt
    if policy is not frames.FramePolicy.UNCHANGED:
        assert len(report["frame_control"]["captures"]) == 2
        assert report["frame_control"]["restores"] == []
        assert (
            report["frame_control"]["captures"][-1]["document_frame"]["FrameWidth"]
            == 1607
        )
        assert "document_frame" not in receipt["viewport_restore"]["before"]
    assert original == (probe.viewports.capture, probe.viewports.restore)


def test_same_accessor_order_can_select_measured_restore_without_other_extra_work(
    frame_scene, monkeypatch
):
    f = frame_scene

    def forbidden(*a, **k):
        raise AssertionError("extra blank/printed trial in accessor-only scope")

    monkeypatch.setattr(probe, "trial", forbidden)
    monkeypatch.setattr(probe, "printed_witness", forbidden)
    f.scene.run(**options(f), frame_policy=frames.FramePolicy.MEASURED_RESTORE)
    report, _ = f.scene.report()
    assert report["status"] == "passed"
    assert report["trials"] == [] and len(report["accessors"]) == 1
    assert len(f.scene.created) == 2 and len(f.scene.saves) == 1
    assert f.writes == list(f.measured.items())
    assert [row[0] for row in f.scene.viewport_calls] == [
        "redraw",
        "scale",
        "translation",
        "redraw",
    ]
    assert (
        report["frame_control"]["mechanism_outcome"] == "restored_observed_pixel_drift"
    )
    assert report["frame_control"]["measured_frame_write_count"] == 5
    assert report["frame_control"]["observed_pixel_drift_count"] == 1
    assert all("viewport_control" not in row for row in report["operation_scopes"])
    assert f.scene.native.app.documents == []


def test_accessor_only_still_rejects_independent_defaults_change(frame_scene):
    f = frame_scene
    f.scene.faults["prepared_mismatch"] = True
    with pytest.raises(ExceptionGroup) as caught:
        f.scene.run(**options(f), frame_policy=frames.FramePolicy.MEASURED_RESTORE)
    assert "raw defaults did not persist exactly" in repr(caught.value)
    report, _ = f.scene.report()
    assert report["status"] == "failed" and report["trials"] == []
    assert len(f.scene.created) == 2 and len(f.scene.saves) == 1
    assert f.scene.native.app.documents == []


@pytest.mark.parametrize(
    "extra",
    [
        {"viewport": probe.Viewport.CAPTURED},
        {"printed_format": probe.PrintedFormat.COMPARE},
        {"failure_receipt": None, "failure_receipt_sha256": None},
    ],
)
def test_accessor_only_rejects_changed_experiment_scope_before_creation(
    frame_scene, extra
):
    f = frame_scene
    selected = options(f) | extra
    with pytest.raises(ValueError):
        f.scene.run(**selected)
    assert f.scene.created == f.writes == []


def test_capture_only_patches_only_getters_not_the_production_restore(frame_scene):
    f = frame_scene
    from diagnostics import _owned_native_documents as owned

    adapter = owned.DiagnosticAdapter(f.scene.native.adapter)
    original = (probe.viewports.capture, probe.viewports.restore)
    with frames.intercept(adapter, frames.FramePolicy.CAPTURE_ONLY, {}):
        assert probe.viewports.capture is not original[0]
        assert probe.viewports.restore is original[1]
    assert original == (probe.viewports.capture, probe.viewports.restore)


def test_capture_only_frame_metadata_cannot_add_a_production_acceptance_gate(
    frame_scene, monkeypatch
):
    f = frame_scene
    original_capture = probe.viewports.capture

    def stable_visible_viewport(model):
        # Document-frame dimensions include non-visible client/decorations;
        # the production acceptance contract is the unchanged six-field view.
        value = original_capture(model)
        value["visible_box_pixels"] = [2216, 141, 3824, 995]
        value["transform"][12] = model.ActiveView.Scale2
        return value

    monkeypatch.setattr(probe.viewports, "capture", stable_visible_viewport)
    f.scene.run(**options(f))
    report, _ = f.scene.report()
    assert report["status"] == "passed" and f.writes == []
    captures = report["frame_control"]["captures"]
    assert captures[0]["document_frame"]["FrameWidth"] == 1608
    assert captures[-1]["document_frame"]["FrameWidth"] == 1607
    receipt = json.loads(
        (Path(report["accessors"][0]["directory"]) / "receipt.json").read_text()
    )
    target = receipt["viewport_before"]
    assert set(target) == {
        "scale2",
        "transform",
        "translation3",
        "orientation3",
        "visible_box_pixels",
        "document_visibility",
    }
    assert receipt["viewport_restore"]["after"] == target
    assert all(
        "document_frame" not in receipt["viewport_restore"][name]
        for name in ("before", "target", "after_scale", "after")
    )


def test_capture_only_returns_original_value_and_retains_independent_evidence(
    frame_scene, monkeypatch
):
    from types import SimpleNamespace

    f = frame_scene
    value = {"translation3": [1.0, 2.0, 0.0]}
    monkeypatch.setattr(probe.viewports, "capture", lambda model: value)
    evidence = {}
    model = SimpleNamespace(ActiveView=SimpleNamespace(**f.measured))
    with frames.intercept(
        f.scene.native.adapter, frames.FramePolicy.CAPTURE_ONLY, evidence
    ):
        observed = probe.viewports.capture(model)
        assert observed is value and "document_frame" not in value
        observed["translation3"][0] = 99
    assert evidence["captures"][0]["translation3"] == [1.0, 2.0, 0.0]
    assert evidence["captures"][0]["document_frame"] == f.measured


def test_accessor_first_cli_defaults_to_capture_only_before_entering_existing_runner(
    frame_scene, monkeypatch
):
    import dodo

    f = frame_scene
    calls = []
    monkeypatch.setattr(dodo, "_run", lambda *a, **k: calls.append((a, k)))
    probe.main(
        [
            "--scope",
            "accessor_only",
            "--expected-pid",
            "123",
            "--scale",
            "2",
            "1",
            "--failure-receipt",
            str(f.receipt),
            "--failure-receipt-sha256",
            f.options["failure_receipt_sha256"],
        ]
    )
    command = calls[0][0][0]
    assert command[command.index("--frame-policy") + 1] == "capture_only"
    assert command[command.index("--scope") + 1] == "accessor_only"
    assert command[command.index("--viewport") + 1] == "normal"
    assert command[command.index("--printed-format") + 1] == "skip"
    assert calls[0][1]["com"] is True and command[-1] == "--worker"
    assert not f.scene.created


def test_accessor_print_combination_refused_by_parent_before_seat_or_attach(
    frame_scene, monkeypatch
):
    import dodo

    f = frame_scene

    def forbidden(*a, **k):
        raise AssertionError("invalid control reached the seat runner")

    monkeypatch.setattr(dodo, "_run", forbidden)
    with pytest.raises(ValueError, match="forbids"):
        probe.main(
            [
                "--scope",
                "accessor_only",
                "--expected-pid",
                "123",
                "--printed-format",
                "compare",
                "--failure-receipt",
                str(f.receipt),
                "--failure-receipt-sha256",
                f.options["failure_receipt_sha256"],
            ]
        )
