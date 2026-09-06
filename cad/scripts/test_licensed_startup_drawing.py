"""COM-free contracts for the single-launch CEF environment diagnostic."""

from contextlib import contextmanager
import json
import os
import subprocess
from unittest.mock import Mock

import pytest

from diagnostics import probe_licensed_startup as probe


DEFAULTS = {
    "PROCESSOR_ARCHITECTURE": "AMD64",
    "CommonProgramFiles": "C:/Program Files/Common Files",
    "CommonProgramW6432": "C:/Program Files/Common Files",
    "CommonProgramFiles(x86)": "C:/Program Files (x86)/Common Files",
}


def test_inherited_mode_preserves_every_environment_value():
    parent = {"SystemRoot": "C:/Windows", "UNRELATED": "unchanged"}
    child, changes = probe.child_environment("inherited", parent, {})
    assert child == parent and child is not parent
    assert changes == {}


def test_only_four_absent_values_change_in_child_not_parent():
    parent = {"SystemRoot": "C:/Windows", "UNRELATED": "unchanged"}
    original = dict(parent)
    child, changes = probe.child_environment("native-defaults", parent, DEFAULTS)
    assert parent == original
    assert child == {**parent, **DEFAULTS}
    assert changes == DEFAULTS


def test_existing_values_and_case_are_never_overwritten():
    parent = {"COMMONPROGRAMFILES": "D:/Explicit/Shared"}
    child, changes = probe.child_environment("native-defaults", parent, DEFAULTS)
    assert child["COMMONPROGRAMFILES"] == parent["COMMONPROGRAMFILES"]
    assert "CommonProgramFiles" not in child
    assert set(changes) == set(DEFAULTS) - {"CommonProgramFiles"}


@pytest.mark.parametrize("defaults", [{}, {**DEFAULTS, "PATH": "replacement"}])
def test_incomplete_or_expanded_default_scope_fails(defaults):
    with pytest.raises(ValueError, match="four"):
        probe.child_environment("native-defaults", {}, defaults)


def modal(**changes):
    return {
        "pid": 123,
        "hwnd": 456,
        "class": "#32770",
        "visible": True,
        "owner": 789,
        "owner_pid": 123,
        "owner_enabled": False,
        "title": "SOLIDWORKS Design",
        "texts": ["CEF for SOLIDWORKS is not installed."],
        "rect": [1, 2, 101, 202],
        **changes,
    }


def test_actual_owner_disabled_dialog_requires_continuous_duration():
    tracker = probe.DialogTracker(sustain_s=4)
    assert tracker.blocking([modal()], 1) == []
    assert tracker.blocking([modal()], 4.9) == []
    assert tracker.blocking([modal()], 5) == [modal()]


@pytest.mark.parametrize(
    "changes",
    [
        {"owner_enabled": True},
        {"owner": 0},
        {"owner_pid": 999},
        {"visible": False},
        {"class": "AfxWnd"},
    ],
)
def test_nonmodal_or_foreign_owner_never_blocks(changes):
    tracker = probe.DialogTracker(sustain_s=4)
    assert tracker.blocking([modal(**changes)], 1) == []
    assert tracker.blocking([modal(**changes)], 100) == []


def test_disappearing_blank_notification_resets_duration():
    tracker = probe.DialogTracker(sustain_s=4)
    notification = modal(title="", texts=[])
    assert tracker.blocking([notification], 1) == []
    assert tracker.blocking([], 3) == []
    assert tracker.blocking([notification], 5) == []
    assert tracker.blocking([notification], 8.9) == []


def test_changed_dialog_text_starts_a_new_evidence_interval():
    tracker = probe.DialogTracker(sustain_s=4)
    assert tracker.blocking([modal()], 1) == []
    changed = modal(texts=["Different dialog"])
    assert tracker.blocking([changed], 5) == []


def sample(*, pids=(123,), state="starting", windows=()):
    return {
        "processes": [{"name": "sldworks.exe", "pid": p} for p in pids],
        "state": state,
        "windows": list(windows),
    }


class Scene:
    def __init__(self, rows):
        self.rows = iter(rows)
        self.time = 0
        self.attaches = []
        self.captures = []

    def now(self):
        return self.time

    def sleep(self, seconds):
        self.time += seconds

    def read(self):
        return next(self.rows)

    def attach(self, pid):
        self.attaches.append(pid)
        return {"pid": pid, "revision": "34.3.0", "nonce": "test"}

    def run(self, **kwargs):
        return probe.observe_startup(
            read=self.read,
            attach=self.attach,
            capture=self.captures.append,
            now=self.now,
            sleep=self.sleep,
            timeout_s=10,
            **kwargs,
        )


def test_ready_attaches_once_and_rechecks_same_native_pid():
    scene = Scene([sample(), sample(state="connected"), sample(state="connected")])
    result = scene.run()
    assert result["status"] == "ready"
    assert result["attach"]["revision"] == "34.3.0"
    assert scene.attaches == [123]


def test_ready_notification_does_not_mask_connectivity():
    scene = Scene(
        [
            sample(
                state="connected",
                windows=[modal(owner_enabled=True, title="", texts=[])],
            ),
            sample(state="connected"),
        ]
    )
    assert scene.run()["status"] == "ready"


def test_pending_owner_disabled_dialog_prevents_attach_even_when_connected():
    scene = Scene([sample(state="connected", windows=[modal()])] * 3)
    assert scene.run()["status"] == "modal_left_undismissed"
    assert scene.attaches == []
    assert len(scene.captures) == 1


@pytest.mark.parametrize(
    "rows",
    [
        [sample(pids=(123, 124))],
        [sample(), sample(pids=(124,))],
        [sample(), sample(pids=())],
    ],
)
def test_disappeared_replaced_or_multiple_native_processes_fail(rows):
    scene = Scene(rows)
    with pytest.raises(RuntimeError, match="native process"):
        scene.run()
    assert scene.attaches == []


def test_native_identity_is_rechecked_after_attach():
    scene = Scene([sample(state="connected"), sample(pids=(124,), state="connected")])
    with pytest.raises(RuntimeError, match="native process"):
        scene.run()


def test_native_identity_failure_keeps_both_observations_in_audit():
    scene = Scene([sample(), sample(pids=(124,))])
    audit = {}
    with pytest.raises(RuntimeError, match="native process"):
        scene.run(audit=audit)
    assert [row["processes"][0]["pid"] for row in audit["observations"]] == [123, 124]


def test_startup_timeout_does_not_attach_or_retry():
    scene = Scene([sample(pids=())] * 5)
    assert scene.run()["status"] == "startup_timeout_left_running"
    assert scene.attaches == []


@pytest.mark.parametrize(
    "changes", [{"nonce": "stale"}, {"pid": 999}, {"pid": True}, {"revision": ""}]
)
def test_stale_or_wrong_attach_receipt_fails(changes):
    receipt = {"nonce": "fresh", "pid": 123, "revision": "34.3.0", **changes}
    with pytest.raises(ValueError):
        probe.validate_attach(receipt, nonce="fresh", expected_pid=123)


def test_any_preexisting_session_or_connector_refuses_launch():
    for name in probe.LAUNCH_GUARD_NAMES:
        with pytest.raises(RuntimeError, match="existing"):
            probe.require_empty_inventory([{"name": name, "pid": 123}])


def test_source_contains_no_macro_or_model_mutation_calls():
    source = probe.Path(probe.__file__).read_text(encoding="utf-8")
    for forbidden in (
        "RunMacro2(",
        "Save3(",
        "OpenDoc",
        "CloseAllDocuments(",
        "recover_solidworks(",
        "stop_solidworks(",
        "SetValueEx(",
    ):
        assert forbidden not in source


def setup_launch(monkeypatch, tmp_path):
    import dodo
    from solidworks_mcp.adapters import sw_install

    events = []
    shortcut = tmp_path / "SOLIDWORKS Design.lnk"
    shortcut.write_bytes(b"fake shortcut - never executed")

    @contextmanager
    def seat(_):
        events.append("seat-enter")
        with monkeypatch.context() as scoped:
            scoped.setenv("HARMONIC_COM_SEAT", "test-owned-seat")
            yield 0
        events.append("seat-exit")

    monkeypatch.setattr(dodo, "_com_seat", seat)
    monkeypatch.setattr(probe, "native_defaults", lambda: DEFAULTS)
    monkeypatch.setattr(probe, "process_inventory", lambda: [])
    monkeypatch.setattr(
        sw_install,
        "resolve_launch_strategy",
        lambda: (sw_install.LaunchStrategy.PLATFORM_SHORTCUT, shortcut),
    )
    monkeypatch.setattr(probe, "os_snapshot", lambda: sample(state="connected"))
    monkeypatch.setattr(
        probe, "cef_modules", lambda pid: [{"pid": pid, "ModuleName": "libcef.dll"}]
    )

    def child(kind, request_path, receipt_path, **kwargs):
        assert os.environ["HARMONIC_COM_SEAT"] == "test-owned-seat"
        events.append(kind)
        request = json.loads(request_path.read_text(encoding="utf-8"))
        if kind == "launch-child":
            assert kwargs["environment"]["HARMONIC_COM_SEAT"] == "test-owned-seat"
            return {
                "nonce": request["nonce"],
                "environment": request["environment"],
                "shortcut": str(shortcut),
                "pid": 456,
            }
        return {"nonce": request["nonce"], "pid": 123, "revision": "34.3.0"}

    monkeypatch.setattr(probe, "run_child", child)
    return events


@pytest.mark.parametrize("mode", ["inherited", "native-defaults"])
def test_orchestration_uses_same_shortcut_seat_and_one_attach_without_parent_changes(
    monkeypatch, tmp_path, mode
):
    events = setup_launch(monkeypatch, tmp_path)
    original = dict(os.environ)
    audit = probe.launch_once(mode, report_root=tmp_path / "reports")
    assert events == ["seat-enter", "launch-child", "attach-child", "seat-exit"]
    assert audit["status"] == "ready"
    assert audit["parent_environment_unchanged"] is True
    assert dict(os.environ) == original
    assert audit["launch"]["shortcut"] == str(tmp_path / "SOLIDWORKS Design.lnk")
    assert len(list((tmp_path / "reports").glob("*/audit.json"))) == 1


def test_preexisting_process_aborts_before_launcher_and_preserves_parent(
    monkeypatch, tmp_path
):
    events = setup_launch(monkeypatch, tmp_path)
    monkeypatch.setattr(
        probe, "process_inventory", lambda: [{"name": "CATSTART.exe", "pid": 999}]
    )
    original = dict(os.environ)
    with pytest.raises(RuntimeError, match="existing"):
        probe.launch_once("native-defaults", report_root=tmp_path / "reports")
    assert "launch-child" not in events
    assert dict(os.environ) == original
    audit = json.loads(
        next((tmp_path / "reports").glob("*/audit.json")).read_text(encoding="utf-8")
    )
    assert audit["status"] == "failed"
    assert audit["parent_environment_unchanged"] is True


def test_timed_out_attach_does_not_retry_or_launch_again(monkeypatch, tmp_path):
    events = setup_launch(monkeypatch, tmp_path)
    child = probe.run_child

    def timeout(kind, *args, **kwargs):
        if kind == "attach-child":
            events.append(kind)
            raise subprocess.TimeoutExpired("owned-attach-child", 20)
        return child(kind, *args, **kwargs)

    monkeypatch.setattr(probe, "run_child", timeout)
    with pytest.raises(subprocess.TimeoutExpired):
        probe.launch_once("inherited", report_root=tmp_path / "reports")
    assert events.count("launch-child") == 1
    assert events.count("attach-child") == 1


def test_stale_child_file_prevents_even_process_creation(monkeypatch, tmp_path):
    receipt = tmp_path / "receipt.json"
    receipt.write_text("stale", encoding="utf-8")
    run = Mock()
    monkeypatch.setattr(probe.subprocess, "run", run)
    with pytest.raises(RuntimeError, match="stale"):
        probe.run_child("attach-child", tmp_path / "request.json", receipt)
    run.assert_not_called()


def test_child_without_machine_seat_refuses_before_reading_any_request(
    monkeypatch, tmp_path
):
    monkeypatch.delenv("HARMONIC_COM_SEAT", raising=False)
    with pytest.raises(RuntimeError, match="seat"):
        probe.child_main(
            "launch-child", tmp_path / "missing.json", tmp_path / "receipt.json"
        )


def test_diagnostic_raw_shortcut_preserves_inherited_baseline_when_production_repairs_env(
    monkeypatch, tmp_path
):
    from solidworks_mcp.adapters import sw_install

    monkeypatch.setenv("HARMONIC_COM_SEAT", "test-owned-seat")
    shortcut = tmp_path / "SOLIDWORKS Design.lnk"
    shortcut.write_bytes(b"never execute this fixture")
    monkeypatch.setattr(
        sw_install,
        "resolve_launch_strategy",
        lambda: (sw_install.LaunchStrategy.PLATFORM_SHORTCUT, shortcut),
    )
    production_launch = Mock(
        side_effect=AssertionError(
            "Production environment repair must not contaminate A/B"
        )
    )
    monkeypatch.setattr(sw_install, "launch_via_platform_shortcut", production_launch)
    raw_launch = Mock()
    monkeypatch.setattr(probe.os, "startfile", raw_launch)
    monkeypatch.setattr(probe, "process_inventory", lambda: [])
    request = tmp_path / "request.json"
    receipt = tmp_path / "receipt.json"
    environment = probe.selected_environment(os.environ)
    request.write_text(
        json.dumps(
            {"nonce": "fresh", "environment": environment, "shortcut": str(shortcut)}
        ),
        encoding="utf-8",
    )
    probe.child_main("launch-child", request, receipt)
    raw_launch.assert_called_once_with(str(shortcut))
    production_launch.assert_not_called()
    assert json.loads(receipt.read_text(encoding="utf-8"))["environment"] == environment
