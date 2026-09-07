"""Offline contracts for foundation diagnostic entrypoints and native arrays."""

from contextlib import asynccontextmanager
import asyncio
import importlib
import inspect
from types import SimpleNamespace as NS
from unittest.mock import AsyncMock, Mock

import pytest

import _telemetry
from diagnostics import probe_datum_dimension_attachment as datum
from diagnostics import probe_dimension_arrangement as arrangement
from diagnostics import probe_licensed_startup as startup


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "name",
    [
        "datum_dimension_attachment",
        "datum_frame_anchors",
        "datum_sheet_z",
        "datum_shoulder",
        "dimension_arrangement",
        "dimensions_after_gtol",
    ],
)
async def test_native_probe_entrypoint_span_contains_exact_failure(
    monkeypatch, tmp_path, name
):
    module = importlib.import_module(f"diagnostics.probe_{name}")
    failure = RuntimeError("early ownership/input refusal")
    events = []

    @asynccontextmanager
    async def span(label, **attributes):
        events.append(("start", label, attributes))
        try:
            yield object()
        except Exception as error:
            events.append(("failure", error))
            raise
        finally:
            events.append(("end", label))

    monkeypatch.setattr(_telemetry, "aspan", span)
    adapter = NS(ownership=NS(register_directory=Mock(side_effect=failure)))
    if name == "dimension_arrangement":
        monkeypatch.setattr(module, "read_inputs", Mock(side_effect=failure))
    with pytest.raises(RuntimeError) as caught:
        await module.probe(adapter, tmp_path / "source.SLDDRW", tmp_path)
    assert caught.value is failure
    assert events == [
        ("start", f"diagnostic.{name}", {}),
        ("failure", failure),
        ("end", f"diagnostic.{name}"),
    ]
    assert inspect.signature(module.probe) == inspect.signature(
        module.probe.__wrapped__
    )


@pytest.mark.parametrize("count,kinds", [(1, ()), (1, (1, 2)), (0, (1,))])
def test_datum_rejects_parallel_attachment_array_mismatch_before_capture(
    monkeypatch, count, kinds
):
    view = object()
    annotation = NS(
        GetType=lambda: 2,
        OwnerType=0,
        Owner=view,
        Visible=1,
        IsDangling=lambda: False,
        GetAttachedEntities3=lambda: (object(),),
        GetAttachedEntityTypes=lambda: kinds,
        GetAttachedEntityCount3=lambda: count,
    )
    tag = NS(GetAnnotation=lambda: annotation)
    annotation.GetSpecificAnnotation = lambda: tag
    adapter = NS(swApp=NS(IsSame=lambda a, b: int(a is b)))
    monkeypatch.setattr(datum, "_early_bound", lambda value, _: value)
    binding = Mock(return_value="model_geometry")
    capture = Mock(side_effect=AssertionError("truncated native capture was reached"))
    monkeypatch.setattr(datum, "binding", binding)
    monkeypatch.setattr(datum, "raw_display_data", capture)
    with pytest.raises(RuntimeError, match="datum native attachment count changed"):
        datum.datum_state(adapter, {"view": view, "display": object()}, annotation)
    binding.assert_not_called()
    capture.assert_not_called()


@pytest.mark.parametrize("pid", [None, "", "not-a-pid", "0", "-1", "1.5"])
@pytest.mark.parametrize("route", ["parent", "worker"])
def test_arrangement_rejects_invalid_pid_before_receipt_or_native(
    monkeypatch, tmp_path, pid, route
):
    monkeypatch.setenv("HARMONIC_REMOTE_CACHE_MODE", "off")
    monkeypatch.setenv("HARMONIC_SW_AUTOSTART", "0")
    monkeypatch.delenv("HARMONIC_DIAGNOSTIC_SW_PID", raising=False)
    if pid is not None:
        monkeypatch.setenv("HARMONIC_DIAGNOSTIC_SW_PID", pid)
    read = Mock(side_effect=AssertionError("receipt read before PID guard"))
    native = Mock(side_effect=AssertionError("native runner before PID guard"))
    monkeypatch.setattr(arrangement, "read_inputs", read)
    monkeypatch.setattr(arrangement, "run_copy_diagnostic", native)
    args = ["--receipt", str(tmp_path / "missing.json")]
    if route == "worker":
        args.append("--worker")
    with pytest.raises(RuntimeError, match="cache off and an explicit existing PID"):
        arrangement.main(args)
    read.assert_not_called()
    native.assert_not_called()


@pytest.mark.parametrize("timeout", ["0", "901", "nan", "inf"])
def test_licensed_startup_invalid_timeout_message_is_readable_ascii(
    monkeypatch, capsys, timeout
):
    launch = Mock(side_effect=AssertionError("invalid timeout launched native app"))
    monkeypatch.setattr(startup, "launch_once", launch)
    monkeypatch.setattr(
        startup.sys, "argv", ["probe", "inherited", "--timeout", timeout]
    )
    with pytest.raises(SystemExit) as caught:
        startup.main()
    assert caught.value.code == 2
    assert "--timeout must be within 1-900 seconds" in capsys.readouterr().err
    launch.assert_not_called()


@pytest.mark.parametrize("route", ["parent", "worker"])
@pytest.mark.parametrize("policy", tuple(arrangement.Arrangement))
def test_arrangement_valid_pid_preserves_parent_worker_arguments(
    monkeypatch, tmp_path, route, policy
):
    monkeypatch.setenv("HARMONIC_REMOTE_CACHE_MODE", "off")
    monkeypatch.setenv("HARMONIC_SW_AUTOSTART", "0")
    monkeypatch.setenv("HARMONIC_DIAGNOSTIC_SW_PID", "31860")
    receipt = tmp_path / "receipt.json"
    receipt.write_text("unused fixture input")
    output = tmp_path / "reports"
    read = Mock()
    parent = Mock()
    adapter = object()
    worker = AsyncMock(return_value="worker result")
    monkeypatch.setattr(arrangement, "read_inputs", read)
    monkeypatch.setattr(arrangement, "probe", worker)
    monkeypatch.setattr(
        arrangement,
        "run_copy_diagnostic",
        lambda callback: asyncio.run(callback(adapter)),
    )
    monkeypatch.setitem(arrangement.sys.modules, "dodo", NS(_run=parent))
    args = [
        "--receipt",
        str(receipt),
        "--report-root",
        str(output),
        "--arrangement",
        policy.value,
    ]
    if route == "worker":
        assert arrangement.main([*args, "--worker"]) == "worker result"
        worker.assert_awaited_once_with(
            adapter, receipt.resolve(), output.resolve(), arrangement=policy
        )
        parent.assert_not_called()
    if route == "parent":
        assert arrangement.main(args) == 0
        parent.assert_called_once_with(
            [
                arrangement.sys.executable,
                str(arrangement.Path(arrangement.__file__).resolve()),
                *args,
                "--worker",
            ],
            "one per-view native dimension arrangement",
            com=True,
            log_stem="dimension-arrangement",
        )
        worker.assert_not_awaited()
    read.assert_called_once_with(receipt.resolve())
    assert arrangement.os.environ["HARMONIC_DIAGNOSTIC_SW_PID"] == "31860"
