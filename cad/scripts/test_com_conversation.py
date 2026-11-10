"""Offline tests for COM-conversation record/replay (``_com_conversation``).

No SolidWorks and no COM server: :class:`FakeDispatch` is a duck-typed
stand-in for pythoncom's ``PyIDispatch`` (the ``_com._RecordedInvoke``
precedent), registered with the engine as an interface type. Generated-style
wrappers (``IApp``/``IPart``, bogus CLSIDs) and pywin32's own late-bound
``CDispatch`` run their real code over it, so the funnel, the canonical form,
byref write-back, identity, errors and the sandbox are exercised exactly as a
build drives them. The subprocess tests run the driver (``com_replay.py``)
end to end: ``record`` against a fake ``run_build``, ``replay`` with the
sandbox armed.
"""

from __future__ import annotations

import ast
import asyncio
import importlib.util
import json
import math
import os
import socket
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
import pythoncom
import pywintypes
import win32com.client
import win32com.client.dynamic
from win32com.client import VARIANT, Dispatch, DispatchBaseClass

import _com
import _com_conversation as conv
import _paths
import _seat_forensics

SCRIPTS = Path(__file__).resolve().parent
REPO = SCRIPTS.parents[1]
LCID = 0
E_FAIL = -2147467259
E_NOTIMPL = -2147467263
DISP_E_MEMBERNOTFOUND = -2147352573
APP_CLSID = "{0BADC0DE-0000-4000-8000-00000000A001}"
PART_CLSID = "{0BADC0DE-0000-4000-8000-00000000A002}"
# Byref double array / byref dispatch argument types, numerically (the
# generated wrappers spell them the same way).
_OUT_DOUBLES = 16389
_OUT_DISPATCH = 16393
_SANDBOX_PROBE = REPO / "cad" / "out" / "com-replay-sandbox-probe.txt"


def _com_error(hresult: int, text: str) -> pywintypes.com_error:
    return pywintypes.com_error(
        hresult, text, (0, "Fake", text, None, 0, hresult), None
    )


class FakeServer:
    """One in-memory application: parts by name, properties, byref outputs."""

    NAMES = {"Add": 1, "GetPart": 2, "Volume": 10, "Name": 6}
    METHODS = frozenset({1, 2, 3, 4, 5, 7, 8, 9, 11, 12, 13, 14, 15})

    def __init__(self, volume_scale: float = 1.0) -> None:
        self.calls = 0
        self.names: dict[str, str] = {}
        self.properties: list[tuple[Any, ...]] = []
        self.volume_scale = volume_scale

    def root(self) -> FakeDispatch:
        return FakeDispatch(self, "app")

    def invoke(self, target: FakeDispatch, dispid: int, flags: int, args: tuple) -> Any:
        self.calls += 1
        if dispid in self.METHODS and flags == pythoncom.DISPATCH_PROPERTYGET:
            raise _com_error(DISP_E_MEMBERNOTFOUND, "member not found")
        ident = target.ident
        if dispid == 1:
            return args[0] + args[1]
        if dispid == 2:
            return FakeDispatch(self, f"part:{args[0]}")
        if dispid == 3:
            args[0].value = (0.1, 0.2, 0.1 + 0.2)
            return True
        if dispid == 4:
            args[0].value = FakeDispatch(self, "part:child")
            return True
        if dispid == 5:
            raise _com_error(E_FAIL, "boom")
        if dispid == 6:
            if flags & pythoncom.DISPATCH_PROPERTYPUT:
                self.names[ident] = args[0]
                return None
            return self.names.get(ident, ident)
        if dispid == 7:
            Path(args[0]).parent.mkdir(parents=True, exist_ok=True)
            Path(args[0]).write_bytes(
                b"written by the fake server for " + ident.encode()
            )
            return True
        if dispid == 8:
            return Path(args[0]).is_file()
        if dispid == 9:
            self.properties.append(args)
            return 0
        if dispid == 10:
            volume = {"part:plate": 1.25, "part:arm": 2.5}.get(ident, 0.5)
            return self.volume_scale * volume
        if dispid == 12:
            return 4242
        if dispid == 13:
            return "34.3.0"
        if dispid == 14:
            return "C:\\seat\\working"
        if dispid == 15:
            values = {name: value for name, _, value, _ in self.properties}
            if args[0] == "Summary":
                return f"summary: {values.get('Generator')}"
            return values.get(args[0], "")
        return f"answer-{dispid}"


class FakeDispatch:
    """Duck-typed PyIDispatch: every operation goes to the server."""

    def __init__(self, server: FakeServer, ident: str) -> None:
        self.server = server
        self.ident = ident

    def InvokeTypes(self, dispid, lcid, flags, ret, argtypes, *args):  # noqa: N802
        return self.server.invoke(self, dispid, flags, args)

    def Invoke(self, dispid, lcid, flags, result_wanted, *args):  # noqa: N802
        return self.server.invoke(self, dispid, flags, args)

    def GetIDsOfNames(self, *args):  # noqa: N802
        name = next(a for a in args if isinstance(a, str))
        if name not in FakeServer.NAMES:
            raise _com_error(DISP_E_MEMBERNOTFOUND, name)
        return FakeServer.NAMES[name]

    def GetTypeInfo(self, *args):  # noqa: N802
        raise _com_error(E_NOTIMPL, "no type information")

    def GetTypeInfoCount(self):  # noqa: N802
        return 0

    def QueryInterface(self, *args):  # noqa: N802
        return FakeDispatch(self.server, self.ident)  # a new object, same identity

    def __eq__(self, other: object) -> bool:
        return isinstance(other, FakeDispatch) and other.ident == self.ident

    def __hash__(self) -> int:
        return hash(self.ident)


conv.register_interface_type(FakeDispatch)


class IApp(DispatchBaseClass):
    CLSID = pywintypes.IID(APP_CLSID)
    coclass_clsid = None

    def Add(self, a=0.0, b=0.0):  # noqa: N802
        return self._oleobj_.InvokeTypes(1, LCID, 1, (5, 0), ((5, 1), (5, 1)), a, b)

    def GetPart(self, name=""):  # noqa: N802
        ret = self._oleobj_.InvokeTypes(2, LCID, 1, (9, 0), ((8, 1),), name)
        if ret is not None:
            ret = Dispatch(ret, "GetPart", PART_CLSID)
        return ret

    def Measure(self, out=None):  # noqa: N802
        return self._oleobj_.InvokeTypes(3, LCID, 1, (11, 0), ((_OUT_DOUBLES, 3),), out)

    def FindChild(self, out=None):  # noqa: N802
        return self._oleobj_.InvokeTypes(
            4, LCID, 1, (11, 0), ((_OUT_DISPATCH, 3),), out
        )

    def Fail(self):  # noqa: N802
        return self._oleobj_.InvokeTypes(5, LCID, 1, (24, 0), ())

    def SaveTo(self, path=""):  # noqa: N802
        return self._oleobj_.InvokeTypes(7, LCID, 1, (11, 0), ((8, 1),), path)

    def Open(self, path=""):  # noqa: N802
        return self._oleobj_.InvokeTypes(8, LCID, 1, (11, 0), ((8, 1),), path)

    def Add3(self, name="", kind=0, value="", option=0):  # noqa: N802
        return self._oleobj_.InvokeTypes(
            9,
            LCID,
            1,
            (3, 0),
            ((8, 1), (3, 1), (8, 1), (3, 1)),
            name,
            kind,
            value,
            option,
        )

    def GetProcessID(self):  # noqa: N802
        return self._oleobj_.InvokeTypes(12, LCID, 1, (3, 0), ())

    def RevisionNumber(self):  # noqa: N802
        return self._oleobj_.InvokeTypes(13, LCID, 1, (8, 0), ())

    def GetCurrentWorkingDirectory(self):  # noqa: N802
        return self._oleobj_.InvokeTypes(14, LCID, 1, (8, 0), ())

    def GetValue(self, name=""):  # noqa: N802
        return self._oleobj_.InvokeTypes(15, LCID, 1, (8, 0), ((8, 1),), name)

    _prop_map_get_ = {"Name": (6, 2, (8, 0), (), "Name", None)}
    _prop_map_put_ = {"Name": ((6, LCID, 4, 0), ())}


class IPart(DispatchBaseClass):
    CLSID = pywintypes.IID(PART_CLSID)
    coclass_clsid = None

    def Rename(self, name=""):  # noqa: N802
        return self._oleobj_.InvokeTypes(11, LCID, 1, (24, 0), ((8, 1),), name)

    _prop_map_get_ = {
        "Name": (6, 2, (8, 0), (), "Name", None),
        "Volume": (10, 2, (5, 0), (), "Volume", None),
    }
    _prop_map_put_ = {"Name": ((6, LCID, 4, 0), ())}


win32com.client.CLSIDToClass.RegisterCLSID(APP_CLSID, IApp)
win32com.client.CLSIDToClass.RegisterCLSID(PART_CLSID, IPart)


class FakeAdapter:
    """What a build sees: COM state on attributes, like PyWin32Adapter."""

    def __init__(self, server: FakeServer | None = None) -> None:
        self.swApp = IApp(server.root()) if server else None
        self.raw = server.root() if server else None
        self.calls_made = 0

    def _attempt(self, operation: Any, default: Any = None) -> Any:
        try:
            return operation()
        except Exception:  # noqa: BLE001 - PyWin32Adapter._attempt's contract
            return default

    def _get_attr_or_call(self, obj: Any, name: str) -> Any:
        value = getattr(obj, name)
        return value() if callable(value) else value


def _seat_calls(adapter: Any, variant: str) -> None:
    """The native run's seat-provenance shapes: the same reads issued by the
    recipe-inert module, or straight from build code."""
    app = adapter.swApp
    if variant == "provenance":
        _seat_forensics.seat_provenance(adapter)
    elif variant == "inert-ab":
        _seat_forensics._seat_identity_of(adapter)
        _seat_forensics._seat_working_directory(adapter)
    elif variant == "inert-ba":
        _seat_forensics._seat_working_directory(adapter)
        _seat_forensics._seat_identity_of(adapter)
    elif variant == "direct-ab":
        app.GetProcessID()
        app.GetCurrentWorkingDirectory()
    elif variant == "direct-ba":
        app.GetCurrentWorkingDirectory()
        app.GetProcessID()


async def scenario(
    adapter: Any,
    *,
    variant: str = "",
    probe: Any = None,
    sha: str = "0123abc",
    year: str | None = None,
    readback: bool = False,
) -> dict[str, Any]:
    """Every path a build drives: early-bound methods and properties, typed
    returns, identity, byref outputs (values and an interface), a COM error,
    late binding, ``_com._com_invoke`` and a SolidWorks-written file."""
    app = adapter.swApp
    if probe is not None:
        probe(app)
    second = math.nextafter(2.25, 3.0) if variant == "ulp" else 2.25
    total = app.Add(1.5, second)
    plate = app.GetPart("plate")
    again = app.GetPart("plate")
    arm = app.GetPart("arm")
    plate.Name = "plate-renamed"
    doubles = VARIANT(_OUT_DOUBLES, (0.0, 0.0, 0.0))
    child = VARIANT(_OUT_DISPATCH, None)
    app.Measure(doubles)
    app.FindChild(child)
    try:
        app.Fail()
    except pythoncom.com_error as exc:
        failed = exc.hresult
    late = win32com.client.dynamic.Dispatch(adapter.raw)
    raw_parts = {
        app._oleobj_.InvokeTypes(2, LCID, 1, (9, 0), ((8, 1),), name)
        for name in ("plate", "plate", "arm")
    }
    out = _paths.OUT_SLDPRT / "fake.SLDPRT"
    saved = app.SaveTo(str(out))
    written = out.read_bytes()  # Python reads what "SolidWorks" wrote
    result = {
        "total": total.hex(),
        "same_part": plate == again,
        "other_part": plate == arm,
        "name": plate.Name,
        "volume": plate.Volume,
        "doubles": [v.hex() for v in doubles.value],
        "child_volume": child.value.Volume,
        "failed": failed,
        "late": late.Add(2.0, 3.0),
        "distinct_raw_parts": len(raw_parts),
        "title": _com._com_invoke(app, "IModelDoc2", "GetTitle"),
        "saved": saved,
        "written": written.decode(),
    }
    if variant == "extra":
        app.Add(0.0, 0.0)
    if variant != "short":
        stamps = {"Generator": f"harmonic-analyzer @ {sha}"}
        if year is not None:
            stamps["COPYRIGHT_YEAR"] = year
        for name, value in stamps.items():
            app.Add3(name, 30, value, 2)
            if not readback:
                continue
            # _custom_properties.apply_custom_properties' verify.
            back = app.GetValue(name)
            if back != value:
                raise RuntimeError(f"custom property {name!r} readback {back!r}")
        if readback:
            result["summary"] = app.GetValue("Summary")
    _seat_calls(adapter, variant)
    report = _paths.OUT_SLDPRT.parent / "py-output.json"
    report.write_text(json.dumps(result, sort_keys=True), encoding="utf-8")
    escape = os.environ.get("COM_REPLAY_TEST_ESCAPE")
    if escape == "dispatch":
        win32com.client.Dispatch("ComReplay.Bogus.NotRegistered.Server")
    if escape == "write":
        _SANDBOX_PROBE.write_text("must never exist", encoding="utf-8")
    if escape == "network":
        socket.create_connection(("192.0.2.1", 9), timeout=0.2)
    return result


def _record(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, **kwargs: Any):
    out_root = tmp_path / "run1"
    monkeypatch.setattr(_paths, "OUT_SLDPRT", out_root / "sldprt")
    server = kwargs.pop("server", None) or FakeServer()
    adapter = FakeAdapter(server)
    log = tmp_path / "logs" / "L1.jsonl.gz"
    with conv.recording(
        adapter,
        script=Path(__file__),
        log=log,
        roots=conv.Roots(out_root),
        audit=kwargs.pop("audit", False),
        callers=kwargs.pop("callers", conv.CallerCapture.FULL),
    ):
        result = asyncio.run(scenario(adapter, **kwargs))
    return log, result, server, adapter


def _replay(log: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, **kwargs: Any):
    scratch = tmp_path / "scratch"
    monkeypatch.setattr(_paths, "OUT_SLDPRT", scratch / "sldprt")
    conversation = conv.load(log)
    materialiser = conv.Materialiser(conversation, conv.capture_dir_of(log), scratch)
    replayer = conv.Replayer(
        conversation,
        conv.Roots(scratch),
        materialise=materialiser,
        callers=conv.CallerCapture(conversation.trailer["callers"]),
    )
    adapter = FakeAdapter()
    stop = None
    result = None
    with conv.replaying(adapter, replayer):
        try:
            result = asyncio.run(scenario(adapter, **kwargs))
        except conv.ReplayStop as exc:
            stop = exc
    return replayer, result, stop


def test_unchanged_build_replays_as_noop_without_the_server(tmp_path, monkeypatch):
    log, recorded, server, _ = _record(tmp_path, monkeypatch)
    live_calls = server.calls
    replayer, replayed, stop = _replay(log, tmp_path, monkeypatch)
    verdict, divergence, _ = replayer.finish()
    assert stop is None and verdict is conv.Verdict.NOOP and divergence is None
    assert replayed == recorded
    assert server.calls == live_calls  # the replay never reached the server
    assert replayer.served == len(conv.load(log).calls) > 20


def test_recording_restores_the_adapters_real_objects(tmp_path, monkeypatch):
    _, _, _, adapter = _record(tmp_path, monkeypatch)
    assert type(adapter.swApp._oleobj_) is FakeDispatch
    assert type(adapter.raw) is FakeDispatch


def test_one_ulp_diverges_at_exactly_that_request(tmp_path, monkeypatch):
    log, _, _, _ = _record(tmp_path, monkeypatch)
    calls = conv.load(log).calls
    add = next(c for c in calls if c.site == "IApp.Add")
    replayer, _, stop = _replay(log, tmp_path, monkeypatch, variant="ulp")
    assert stop is not None and stop.verdict is conv.Verdict.DIVERGED
    assert stop.divergence.seq == add.seq and stop.divergence.side is conv.Side.REQUEST
    assert replayer.finish()[0] is conv.Verdict.DIVERGED  # sticky


def test_extra_request_diverges_and_a_short_build_is_unconsumed(tmp_path, monkeypatch):
    log, _, _, _ = _record(tmp_path, monkeypatch)
    _, _, stop = _replay(log, tmp_path, monkeypatch, variant="extra")
    assert stop is not None and stop.verdict is conv.Verdict.DIVERGED
    replayer, _, stop = _replay(log, tmp_path, monkeypatch, variant="short")
    assert stop is None and replayer.finish()[0] is conv.Verdict.UNCONSUMED
    log_short, _, _, _ = _record(tmp_path / "short", monkeypatch, variant="short")
    _, _, stop = _replay(log_short, tmp_path, monkeypatch)
    assert stop is not None and stop.verdict is conv.Verdict.EXHAUSTED


def test_kinds_identity_and_write_back_are_recorded(tmp_path, monkeypatch):
    log, recorded, _, _ = _record(tmp_path, monkeypatch)
    calls = conv.load(log).calls
    kinds = {(c.site, c.kind) for c in calls}
    assert ("IApp.Add", conv.Kind.CALL) in kinds
    add = next(c for c in calls if c.site == "IApp.Add")
    assert "test_com_conversation:scenario" in add.caller
    assert all(c.origin is conv.Origin.RECIPE for c in calls)
    assert ("IPart.Name", conv.Kind.PUT) in kinds
    assert ("IPart.Name", conv.Kind.GET) in kinds
    assert any(c.kind is conv.Kind.QI for c in calls)
    assert [c.result for c in calls if c.op == "__eq__"] == [True, True, False]
    assert [c.result for c in calls if c.op == "__hash__"] == [0, 0, 1]
    assert recorded["same_part"] is True and recorded["other_part"] is False
    assert recorded["distinct_raw_parts"] == 2  # equal raw dispatches dedup
    measure = next(c for c in calls if c.site == "IApp.Measure")
    assert measure.outs[0][0] == "value"
    child = next(c for c in calls if c.site == "IApp.FindChild")
    via, value = child.outs[0]
    assert via == "value" and value["p"] == "FakeDispatch"
    # The write-back's wrapping ran against the raw handle, after the call.
    assert next(c for c in calls if c.seq == child.seq + 1).handle == value["h"]
    failed = next(c for c in calls if c.site == "IApp.Fail")
    assert failed.raised["com_error"][0] == E_FAIL
    assert any(c.site == "IModelDoc2.GetTitle" for c in calls)
    assert any(c.op == "GetIDsOfNames" for c in calls)  # late-bound CDispatch path


def test_canonical_floats_are_bitwise():
    codec = conv.Codec(conv.Roots(Path("C:/nowhere")))
    assert codec.encode(0.0) != codec.encode(-0.0)
    assert codec.encode(2.25) != codec.encode(math.nextafter(2.25, 3.0))
    for value in (math.inf, -math.inf, 5e-324, -0.0, 0.1 + 0.2):
        assert codec.decode(codec.encode(value)).hex() == value.hex()
    assert math.isnan(codec.decode(codec.encode(math.nan)))
    assert not conv.same(True, 1) and not conv.same(1, 1.0)
    assert codec.encode((1.0,)) != codec.encode([1.0])


class PyFUNCDESC:
    """Stands in for pywin32's attribute-only C struct."""

    __module__ = "pythoncom"

    def __init__(self) -> None:
        self.memid = 7
        self.args = ((8, 1),)

    def describe(self) -> str:  # methods are not data members
        return "funcdesc"


def test_pywin32_structs_replay_with_their_data_members():
    codec = conv.Codec(conv.Roots(Path("C:/nowhere")))
    encoded = codec.encode(PyFUNCDESC(), result=True)
    assert encoded == {
        "struct": "PyFUNCDESC",
        "attrs": {"args": {"t": [{"t": [8, 1]}]}, "memid": 7},
    }
    served = codec.decode(json.loads(json.dumps(encoded)))
    assert (served.memid, served.args) == (7, ((8, 1),))
    assert codec.decode(codec.encode((1, 2.5), result=True)) == (1, 2.5)


def test_paths_are_root_relative():
    roots = conv.Roots(Path("C:/Work/Out"), Path("C:/Work"))
    assert roots.encode("c:\\work\\out\\sldprt\\A.SLDPRT") == "<OUT>\\sldprt\\A.SLDPRT"
    assert roots.encode("C:/Work/Out/png") == "<OUT/>/png"
    assert roots.encode("C:\\Work\\cad\\t.prtdot") == "<REPO>\\cad\\t.prtdot"
    assert roots.encode("C:\\Workshop") == "C:\\Workshop"
    other = conv.Roots(Path("D:/Scratch"), Path("C:/Work"))
    assert other.decode("<OUT>\\sldprt\\A.SLDPRT") == "D:\\Scratch\\sldprt\\A.SLDPRT"


def test_provenance_mask_covers_only_the_generator():
    def call(*args: Any) -> conv.Call:
        return conv.Call(0, 1, "InvokeTypes", [9, 0, 1, [3, 0], [], *args], "IApp.Add3")

    def differs(
        a: conv.Call, b: conv.Call, mask: tuple = conv.PROVENANCE_MASK
    ) -> conv.Field | None:
        return conv.request_field(a, b.handle, b.op, b.args, mask)

    generator = call("Generator", 30, "harmonic-analyzer @ abc123", 2)
    rebuilt = call("Generator", 30, "harmonic-analyzer @ def456-dirty", 2)
    other = call("Material", 30, "harmonic-analyzer @ def456", 2)
    other_base = call("Material", 30, "harmonic-analyzer @ abc123", 2)
    assert differs(generator, rebuilt) is None
    assert differs(other_base, other) is conv.Field.ARGS
    assert differs(generator, rebuilt, mask=()) is conv.Field.ARGS


def test_changed_external_input_is_an_input_mismatch(tmp_path, monkeypatch):
    template = tmp_path / "outside" / "template.prtdot"
    template.parent.mkdir()
    template.write_bytes(b"template v1")
    out_root = tmp_path / "run1"
    adapter = FakeAdapter(FakeServer())
    log = tmp_path / "L.jsonl.gz"
    with conv.recording(
        adapter, script=Path(__file__), log=log, roots=conv.Roots(out_root), audit=False
    ):
        adapter.swApp.Open(str(template))
    assert conv.check_inputs(conv.load(log)) == []
    template.write_bytes(b"template v2")
    monkeypatch.setenv("HARMONIC_FIT_GROUPS", "changed")
    mismatched = {m["input"] for m in conv.check_inputs(conv.load(log))}
    assert "env:HARMONIC_FIT_GROUPS" in mismatched
    assert any(name.endswith("template.prtdot") for name in mismatched)


def test_cli_replays_a_recorded_build_in_a_sandboxed_subprocess(tmp_path, monkeypatch):
    log, recorded, _, _ = _record(tmp_path, monkeypatch, audit=True)
    trailer = conv.load(log).trailer
    captured = {
        rel: sha for files in trailer["captured"].values() for rel, sha in files.items()
    }
    assert list(captured) == ["sldprt/fake.SLDPRT"]
    kept = sorted(p.name for p in conv.capture_dir_of(log).rglob("*") if p.is_file())
    assert kept == ["fake.SLDPRT.gz"] and trailer["capture_stored_bytes"] > 0
    audit = trailer["escape_audit"]
    # The adapter's wrapper sat on a real object at entry and on a proxy at
    # exit; no wrapper created inside the window holds a real object.
    assert sum(audit["at_exit"]["wrappers_on_real_objects"].values()) < sum(
        audit["at_entry"]["wrappers_on_real_objects"].values()
    )
    assert audit["at_exit"]["wrappers_on_proxies"] > 0
    assert trailer["reads"] and trailer["writes_outside_out"] == []
    script = tmp_path / "build_fake_widget.py"
    script.write_text(
        "import sys\n"
        "from _session import run_build\n"
        "from test_com_conversation import scenario\n"
        "if __name__ == '__main__':\n"
        "    sys.exit(run_build(scenario))\n",
        encoding="utf-8",
    )
    # The log names the recording's script; the replay runs this one.
    results = {}
    # Writes outside scratch anywhere else: test_a_replay_refuses_writes_outside_its_roots.
    escapes = ("", "dispatch", "write", "network")
    for escape in escapes:
        env = dict(os.environ, OTEL_SERVICE_NAME="part-replay")
        env["COM_REPLAY_TEST_ESCAPE"] = escape
        result = tmp_path / f"result-{escape or 'clean'}.json"
        proc = subprocess.run(
            [
                sys.executable,
                str(SCRIPTS / "com_replay.py"),
                "replay",
                str(script),
                "--log",
                str(log),
                "--base-outputs",
                str(tmp_path / "run1"),
                "--scratch",
                str(tmp_path / f"scratch-{escape or 'clean'}"),
                "--result",
                str(result),
            ],
            env=env,
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert result.is_file(), proc.stdout + proc.stderr
        results[escape] = (
            proc.returncode,
            json.loads(result.read_text(encoding="utf-8")),
        )
    rc, clean = results[""]
    assert rc == 0 and clean["verdict"] == "noop", clean
    assert clean["com_outputs"] == captured
    assert (
        "py-output.json" in clean["py_outputs"] and clean["py_output_mismatches"] == {}
    )
    assert clean["read_mismatches"] == [] and clean["sandbox_violations"] == []
    assert (
        json.loads((tmp_path / "scratch-clean" / "py-output.json").read_text())
        == recorded
    )
    for escape in escapes[1:]:
        rc, outcome = results[escape]
        assert rc == conv.EXIT_REPLAY_NOT_NOOP and outcome["verdict"] == "sandbox", (
            escape,
            outcome,
        )
        assert outcome["sandbox_violations"], escape
    assert not _SANDBOX_PROBE.exists()


def test_a_replay_refuses_writes_outside_its_roots(tmp_path):
    scratch, side = tmp_path / "scratch", tmp_path / "side"
    elsewhere = str(tmp_path / "elsewhere.txt")
    replay = conv._FileObserver(scratch, conv.GuardMode.RAISE, [side])
    replay.observe("open", (str(scratch / "sldprt" / "x.SLDPRT"), "wb", 0))
    replay.observe("open", (str(side / "traces.jsonl"), "a", 0))
    replay.observe("open", (elsewhere, "r", 0))  # reading anywhere is not writing
    # subprocess.DEVNULL (platform.win32_ver runs one) opens the null device
    # read-write: nothing is kept, so it is not a write outside scratch.
    replay.observe("open", (os.devnull, None, os.O_RDWR))
    with pytest.raises(conv.SandboxViolation):
        replay.observe("open", (elsewhere, "w", 0))
    assert replay.written == {"sldprt/x.SLDPRT"} and len(replay.violations) == 1
    # A recording accounts the same write rather than refusing it.
    recording = conv._FileObserver(scratch, conv.GuardMode.WARN, [side])
    recording.observe("open", (elsewhere, "w", 0))
    assert [entry["path"] for entry in recording.outside] == [elsewhere]
    assert recording.violations == []


def _stub_seat_probes(monkeypatch: pytest.MonkeyPatch, identity: dict) -> None:
    """The seat probes that read the process table rather than COM, stubbed;
    ``identity`` is the module's connect-time cache."""
    monkeypatch.setattr(_seat_forensics, "_seat_identity", dict(identity))
    monkeypatch.setattr(_seat_forensics, "_process_started_at", lambda pid: None)
    monkeypatch.setattr(_seat_forensics, "_process_session_id", lambda pid: None)
    monkeypatch.setattr(_seat_forensics, "_process_memory", lambda pid: (None, None))
    monkeypatch.setattr(_seat_forensics, "_sldworks_pids", set)


def test_inert_requests_replay_in_any_order(tmp_path, monkeypatch):
    _stub_seat_probes(monkeypatch, {})
    log, _, _, _ = _record(tmp_path, monkeypatch, variant="inert-ab")
    inert = [c.site for c in conv.load(log).calls if c.origin is conv.Origin.INERT]
    assert inert == [
        "IApp.GetProcessID",
        "IApp.RevisionNumber",
        "IApp.GetCurrentWorkingDirectory",
    ]
    replayer, _, stop = _replay(log, tmp_path, monkeypatch, variant="inert-ba")
    assert stop is None and replayer.finish()[0] is conv.Verdict.NOOP
    report = replayer.inert_report()
    assert (report["served"], report["unserved"], report["unconsumed"]) == (3, 0, 0)


def test_the_same_reorder_in_build_code_diverges(tmp_path, monkeypatch):
    log, _, _, _ = _record(tmp_path, monkeypatch, variant="direct-ab")
    assert all(c.origin is conv.Origin.RECIPE for c in conv.load(log).calls)
    replayer, _, stop = _replay(log, tmp_path, monkeypatch, variant="direct-ba")
    assert stop is not None and stop.verdict is conv.Verdict.DIVERGED
    divergence = stop.divergence.to_json()
    assert divergence["field"] == "member"
    assert (divergence["member_expected"], divergence["member_actual"]) == (
        "IApp.GetProcessID",
        "IApp.GetCurrentWorkingDirectory",
    )
    assert "test_com_conversation:_seat_calls" in divergence["caller_actual"]
    assert "test_com_conversation:_seat_calls" in divergence["caller_expected"]
    assert len(divergence["context"]) == 5


def test_a_connect_time_seat_cache_does_not_steer_the_replay(tmp_path, monkeypatch):
    # Natively the seat identity is cached at connect, before the recording
    # window opens; a replay process never connected, so it asks again.
    _stub_seat_probes(
        monkeypatch, {"seat_pid": 4242, "seat_pid_source": "GetProcessID"}
    )
    log, _, _, _ = _record(tmp_path, monkeypatch, variant="provenance")
    inert = [c.site for c in conv.load(log).calls if c.origin is conv.Origin.INERT]
    assert inert == ["IApp.GetCurrentWorkingDirectory"]
    _stub_seat_probes(monkeypatch, {})
    replayer, _, stop = _replay(log, tmp_path, monkeypatch, variant="provenance")
    assert stop is None and replayer.finish()[0] is conv.Verdict.NOOP
    report = replayer.inert_report()
    assert [row["member"] for row in report["unserved_members"]] == [
        "IApp.GetProcessID"
    ]
    assert (report["served"], report["unconsumed"]) == (1, 0)


def test_inert_objects_have_their_own_handles(tmp_path, monkeypatch):
    helper = tmp_path / "inert_probe.py"
    helper.write_text(
        "def probe(app):\n    return app.GetPart('probe').Volume\n", encoding="utf-8"
    )
    spec = importlib.util.spec_from_file_location("inert_probe", helper)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    monkeypatch.setattr(conv, "_inert_modules", lambda: [module])
    plain, _, _, _ = _record(tmp_path / "plain", monkeypatch)
    # Called as module.function, the way build code calls a recipe-inert module.
    probed, _, _, _ = _record(
        tmp_path / "probed", monkeypatch, probe=lambda app: module.probe(app)
    )
    inert = [c for c in conv.load(probed).calls if c.origin is conv.Origin.INERT]
    assert inert and any(
        c.result.get("h", 0) < 0 for c in inert if c.op == "InvokeTypes"
    )
    assert module.probe.__qualname__ == "probe" and not hasattr(
        module.probe, "__wrapped__"
    )  # restored after the window
    comparison = conv.compare_conversations(plain, probed)
    assert comparison["request_divergence"] is None
    assert comparison["inert_calls"] == [0, len(inert)]
    # A reference bound before the window bypasses the marker: its calls stay
    # RECIPE and are ordered strictly (conservative, never hidden).
    bound, _, _, _ = _record(tmp_path / "bound", monkeypatch, probe=module.probe)
    assert all(c.origin is conv.Origin.RECIPE for c in conv.load(bound).calls)
    assert conv.compare_conversations(plain, bound)["request_divergence"] is not None


def test_k1_separates_request_divergence_from_response_differences(
    tmp_path, monkeypatch
):
    base, _, _, _ = _record(tmp_path / "a", monkeypatch)
    scaled, _, _, _ = _record(
        tmp_path / "b", monkeypatch, server=FakeServer(volume_scale=2.0)
    )
    responses = conv.compare_conversations(base, scaled)
    assert responses["request_divergence"] is None
    assert responses["response_differences"] == {
        "IPart.Volume": 1,
        "CDispatch.Volume": 1,  # the byref child is wrapped late-bound
    }
    example = responses["response_examples"][0]
    assert example["field"] == "result"
    assert "test_com_conversation:scenario" in example["caller"]
    extra, _, _, _ = _record(tmp_path / "c", monkeypatch, variant="extra")
    requests = conv.compare_conversations(base, extra)
    divergence = requests["request_divergence"]
    assert divergence["field"] == "member" and divergence["member_actual"] == "IApp.Add"
    assert len(divergence["context"]) == 5 and divergence["seq_new"] is not None


def test_caller_capture_modes(tmp_path, monkeypatch):
    full = conv.CallerCapture.FULL
    for mode in conv.CallerCapture:
        root = tmp_path / mode.value
        log, _, _, _ = _record(root, monkeypatch, callers=mode, variant="direct-ab")
        loaded = conv.load(log)
        clock = loaded.trailer["clock_seconds"]
        assert loaded.trailer["callers"] == mode.value
        assert any(c.caller for c in loaded.calls) is (mode is full)
        assert (clock["caller"] > 0) is (mode is full)
        assert clock["in_calls"] >= clock["com"] >= 0
        _, _, stop = _replay(log, root, monkeypatch, variant="direct-ba")
        divergence = stop.divergence.to_json()
        assert bool(divergence["caller_expected"]) is (mode is full)
        named = "test_com_conversation:_seat_calls" in divergence["caller_actual"]
        assert named is (mode is not conv.CallerCapture.OFF)


def test_capture_level_matches_the_output_archive():
    import _artifact_cache

    assert conv._CAPTURE_LEVEL == _artifact_cache._PACK_LEVEL


def test_cli_help_imports_no_com():
    script = SCRIPTS / "com_replay.py"
    code = (
        "import runpy, sys\n"
        f"sys.argv = [{str(script)!r}, '--help']\n"
        "try:\n"
        f"    runpy.run_path({str(script)!r}, run_name='__main__')\n"
        "except SystemExit as exc:\n"
        "    assert exc.code == 0, exc.code\n"
        "loaded = sorted(m for m in ('pythoncom', 'win32com', 'pywintypes', '_session') if m in sys.modules)\n"
        "assert not loaded, loaded\n"
    )
    proc = subprocess.run(
        [sys.executable, "-c", code],
        cwd=SCRIPTS,
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert proc.returncode == 0, proc.stdout + proc.stderr
    assert "usage" in proc.stdout


def test_recording_modules_stay_out_of_every_recipe_closure():
    import _buildgraph

    modules = ("_com_conversation.py", "com_replay.py", "_replay_shadow.py")
    scripts = [
        *_buildgraph.part_scripts(),
        *(_buildgraph.script_for(stem) for stem in _buildgraph.ASSEMBLY_ORDER),
        *sorted(SCRIPTS.glob("draw_*.py")),
    ]
    assert len(scripts) > 100
    leaks = sorted(
        f"{script.name} -> {Path(dep).name}"
        for script in scripts
        for dep in _buildgraph.module_deps_of(script)
        if Path(dep).name in modules
    )
    assert not leaks
    # Nothing else may import them: only dodo (outside cad/scripts) imports
    # _replay_shadow, and only the driver imports the engine.
    names = {"_com_conversation", "com_replay", "_replay_shadow"}

    def imported(source: bytes) -> set[str]:
        found: set[str] = set()
        for node in ast.walk(ast.parse(source)):
            if isinstance(node, ast.Import):
                found.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                found.add(node.module)
            elif isinstance(node, ast.Constant) and node.value in names:
                found.add(node.value)  # importlib.import_module("...") and kin
        return found & names

    # Controls: the scanner finds every import form and ignores prose, and the
    # closure walker does see these modules where they ARE imported.
    assert imported(b"import _replay_shadow\n") == {"_replay_shadow"}
    assert imported(b"from _com_conversation import load\n") == {"_com_conversation"}
    assert imported(b"importlib.import_module('com_replay')\n") == {"com_replay"}
    assert imported(b'"""Shadow recording (``_replay_shadow``)."""\n') == set()
    assert "_com_conversation.py" in {
        Path(dep).name for dep in _buildgraph.module_deps_of(SCRIPTS / "com_replay.py")
    }

    importers = []
    for path in SCRIPTS.rglob("*.py"):
        if path.name in modules or path.name.startswith("test_"):
            continue
        source = path.read_bytes()
        # Parse only a file that names one (a mention in prose is no import).
        if any(name.encode() in source for name in names) and imported(source):
            importers.append(f"{path.name} -> {sorted(imported(source))}")
    assert not importers


_HELPER = (
    '"""Replay-test helper: the function the source edits change."""\r\n'
    "\r\n"
    "\r\n"
    "def orient(app):\r\n"
    '    """Ask the application to add a step."""\r\n'
    "    step = 7\r\n"
    "    return app.Add(1.0, step)\r\n"
)
_IDENTITY = (
    '"""Replay-test provider: the commit the Generator stamp names."""\n'
    "\n"
    "\n"
    "def _git_sha() -> str:\n"
    '    """The recording\'s commit."""\n'
    '    return "0123abc"\n'
)
# The current source a later build replays against the recording: only a
# changed request may stop a replay, and a new commit's Generator stamp is a
# substitution, not a divergence.
_SOURCE_EDITS = {
    # A reworded docstring, a new comment (shifting every later line) and a
    # renamed local: the same requests.
    "cosmetic": (
        "replay_helper",
        _HELPER.replace(
            '"""Ask the application to add a step."""\r\n',
            '"""Ask the application to add one step."""\r\n    # reworded\r\n',
        ).replace("step", "increment"),
    ),
    "numeric": ("replay_helper", _HELPER.replace("step = 7", "step = 8")),
    "commit": ("replay_identity", _IDENTITY.replace("0123abc", "feedbee")),
}


def test_current_source_replays_against_an_older_recording(tmp_path, monkeypatch):
    helpers = tmp_path / "helpers"
    helpers.mkdir()
    (helpers / "replay_helper.py").write_bytes(_HELPER.encode("utf-8"))
    (helpers / "replay_identity.py").write_bytes(_IDENTITY.encode("utf-8"))
    monkeypatch.syspath_prepend(str(helpers))
    helper = importlib.import_module("replay_helper")
    log, _, _, _ = _record(
        tmp_path, monkeypatch, probe=helper.orient, sha="0123abc", readback=True
    )
    script = tmp_path / "scripts" / "build_source_widget.py"
    script.parent.mkdir()
    script.write_text(
        "import sys\n"
        "import replay_helper\n"
        "import replay_identity\n"
        "from _session import run_build\n"
        "from test_com_conversation import scenario\n"
        "def build(adapter):\n"
        "    sha = replay_identity._git_sha()\n"
        "    return scenario(\n"
        "        adapter, probe=replay_helper.orient, sha=sha, readback=True\n"
        "    )\n"
        "if __name__ == '__main__':\n"
        "    sys.exit(run_build(build))\n",
        encoding="utf-8",
    )
    results = {}
    for edit, (module, text) in _SOURCE_EDITS.items():
        source = tmp_path / "sources" / edit
        source.mkdir(parents=True)
        for name, original in (
            ("replay_helper", _HELPER),
            ("replay_identity", _IDENTITY),
        ):
            changed = text if name == module else original
            (source / f"{name}.py").write_bytes(changed.encode("utf-8"))
        env = dict(
            os.environ,
            PYTHONPATH=os.pathsep.join(
                filter(None, (str(source), os.environ.get("PYTHONPATH")))
            ),
        )
        result = tmp_path / f"{edit}.json"
        proc = subprocess.run(
            [
                sys.executable,
                str(SCRIPTS / "com_replay.py"),
                "replay",
                str(script),
                "--log",
                str(log),
                "--scratch",
                str(tmp_path / f"scratch-{edit}"),
                "--result",
                str(result),
            ],
            env=env,
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert result.is_file(), proc.stdout + proc.stderr
        results[edit] = (proc.returncode, json.loads(result.read_text("utf-8")))
    rc, cosmetic = results["cosmetic"]
    assert rc == 0 and cosmetic["verdict"] == "noop", cosmetic
    assert cosmetic["substitutions"]["count"] == 0
    rc, numeric = results["numeric"]
    assert rc == conv.EXIT_REPLAY_NOT_NOOP and numeric["verdict"] == "diverged"
    assert numeric["divergence"]["member_actual"] == "IApp.Add"
    assert "replay_helper:orient:" in numeric["divergence"]["caller_actual"]
    rc, commit = results["commit"]
    assert rc == 0 and commit["verdict"] == "noop", commit
    substitutions = commit["substitutions"]
    assert substitutions["count"] == 1
    assert substitutions["by_member"] == {"IApp.GetValue": 1}
    assert [(b["recorded"], b["replayed"]) for b in substitutions["bindings"]] == [
        ("harmonic-analyzer @ 0123abc", "harmonic-analyzer @ feedbee")
    ]


def _window(tmp_path: Path, adapter: FakeAdapter) -> Any:
    return conv.recording(
        adapter,
        script=Path(__file__),
        log=tmp_path / "L.jsonl.gz",
        roots=conv.Roots(tmp_path / "out"),
        audit=False,
    )


def _failing_emit(monkeypatch: pytest.MonkeyPatch) -> None:
    def emit(self: Any, call: Any) -> None:
        raise OSError("injected: the log volume is full")

    monkeypatch.setattr(conv.LogWriter, "emit", emit)


def test_an_engine_fault_is_a_record_fault_never_the_builds_error(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(conv, "_FAULTS", [])
    adapter = FakeAdapter(FakeServer())
    app = adapter.swApp
    with pytest.raises(conv.RecordFault, match="Recorder.call"):
        with _window(tmp_path, adapter):
            # The server's own failure is the build's: unchanged, no fault.
            with pytest.raises(pythoncom.com_error):
                app.Fail()
            assert conv.record_faults() == []
            _failing_emit(monkeypatch)
            try:
                app.Add(1.0, 2.0)
            except Exception:  # noqa: BLE001 - a build's own fallback
                pytest.fail("an engine fault reached the build's except Exception")
    faults = conv.record_faults()
    assert [fault["where"] for fault in faults] == ["Recorder.call"]
    assert faults[0]["type"] == "OSError" and "injected" in faults[0]["traceback"]
    assert type(adapter.swApp._oleobj_) is FakeDispatch  # teardown is unrecorded


def test_a_swallowed_engine_fault_stays_sticky_and_recording_stops(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(conv, "_FAULTS", [])
    adapter = FakeAdapter(FakeServer())
    app = adapter.swApp
    with _window(tmp_path, adapter) as recorder:
        _failing_emit(monkeypatch)
        try:
            app.Add(1.0, 2.0)
        except BaseException:  # noqa: BLE001 - a build that swallows everything
            pass
        # Pass-through from here on: real answers, nothing logged.
        assert recorder.closed
        assert app.Add(2.0, 3.0) == 5.0
    assert [fault["where"] for fault in conv.record_faults()] == ["Recorder.call"]


def test_an_audit_accounting_fault_never_fails_the_builds_file_io(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(conv, "_FAULTS", [])
    dispatcher = conv._AuditDispatcher()

    class Broken:
        mode = conv.GuardMode.WARN

        def observe(self, event: str, args: tuple) -> None:
            raise KeyError("injected")

    dispatcher.observer = Broken()
    dispatcher.hook("open", (str(tmp_path / "x.txt"), "w", 0))  # does not raise
    assert dispatcher.observer is None
    assert [fault["where"] for fault in conv.record_faults()] == ["audit"]

    class Refusing:
        mode = conv.GuardMode.RAISE

        def observe(self, event: str, args: tuple) -> None:
            raise conv.SandboxViolation("refused")

    dispatcher.observer = Refusing()  # a replay's refusal is the point
    with pytest.raises(conv.SandboxViolation):
        dispatcher.hook("open", (str(tmp_path / "x.txt"), "w", 0))


def test_the_replay_sandbox_refuses_the_network_but_not_loopback():
    sandbox = conv.Sandbox()
    sandbox.refuse_network("socket.connect", (None, ("127.0.0.1", 50123)))
    sandbox.refuse_network("socket.connect", (None, ("::1", 50123, 0, 0)))
    sandbox.refuse_network("socket.getaddrinfo", ("localhost", 80, 0, 0, 0))
    sandbox.refuse_network("socket.connect", (None, "\\\\.\\pipe\\local"))
    with pytest.raises(conv.SandboxViolation):
        sandbox.refuse_network("socket.connect", (None, ("192.0.2.1", 9)))
    with pytest.raises(conv.SandboxViolation):
        sandbox.refuse_network("socket.getaddrinfo", ("example.com", 443, 0, 0, 0))
    assert len(sandbox.violations) == 2


# A part build's driver run with a fake run_build: the real CLI, recorder and
# exit-code mapping, the fake application instead of a seat.
_RECORD_DRIVER = """
import asyncio, os, sys
import _session
import test_com_conversation as fixture

def fake_run_build(build):
    adapter = fixture.FakeAdapter(fixture.FakeServer())
    try:
        asyncio.run(build(adapter))
    except Exception:
        return 1
    return 0

_session.run_build = fake_run_build
if os.environ.get("COM_REPLAY_TEST_FAULT"):
    import _com_conversation as conv
    real = conv.LogWriter.emit
    def emit(self, call):
        if call.seq == 3:
            raise OSError("injected: the log volume is full")
        return real(self, call)
    conv.LogWriter.emit = emit
import com_replay
sys.exit(com_replay.main(sys.argv[1:]))
"""


def test_cli_record_exits_with_the_build_or_with_the_fault_code(tmp_path):
    script = tmp_path / "build_fake_widget.py"
    script.write_text(
        "import os, sys\n"
        "from _session import run_build\n"
        "from test_com_conversation import scenario\n"
        "async def build(adapter):\n"
        "    await scenario(adapter)\n"
        "    if os.environ.get('COM_REPLAY_TEST_SCRIPT_FAILS'):\n"
        "        raise RuntimeError('the script failed on its own')\n"
        "    return {}\n"
        "if __name__ == '__main__':\n"
        "    sys.exit(run_build(build))\n",
        encoding="utf-8",
    )
    # A clean recording through this driver: test_replay_shadow's end-to-end
    # test, which records, publishes and replays it.
    runs = {}
    for case, variable in (
        ("script", "COM_REPLAY_TEST_SCRIPT_FAILS"),
        ("fault", "COM_REPLAY_TEST_FAULT"),
    ):
        env = dict(os.environ, OTEL_EXPORTER_OTLP_ENDPOINT="")
        env[variable] = "1"
        summary = tmp_path / case / "summary.json"
        proc = subprocess.run(
            [
                sys.executable,
                "-c",
                _RECORD_DRIVER,
                "record",
                str(script),
                "--log",
                str(tmp_path / case / "L.jsonl.gz"),
                "--summary",
                str(summary),
                "--out-root",
                str(tmp_path / case / "out"),
            ],
            cwd=SCRIPTS,
            env=env,
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert summary.is_file(), proc.stdout + proc.stderr
        runs[case] = (proc.returncode, json.loads(summary.read_text("utf-8")))
    # The script's own failure is its exit code, exactly as unrecorded, and
    # the recording of it is complete.
    rc, script_failed = runs["script"]
    assert rc == 1 and script_failed["exit_code"] == 1
    assert script_failed["faults"] == [] and script_failed["complete"]
    # A recorder fault is the dedicated code; the recording is unusable.
    rc, faulted = runs["fault"]
    assert rc == conv.EXIT_RECORD_FAULT == faulted["exit_code"]
    assert not faulted["complete"]
    [fault] = faulted["faults"]
    assert fault["where"].startswith("Recorder.") and fault["type"] == "OSError"
    assert conv.load(tmp_path / "fault" / "L.jsonl.gz").trailer["faults"]


def test_cross_commit_replay_rebinds_the_generator_readback(tmp_path, monkeypatch):
    log, recorded, _, _ = _record(tmp_path, monkeypatch, sha="1ee7f38", readback=True)
    replayer, replayed, stop = _replay(
        log, tmp_path / "x", monkeypatch, sha="1ee7f3806e", readback=True
    )
    assert stop is None and replayer.finish()[0] is conv.Verdict.NOOP
    report = replayer.substitution_report()
    assert report["count"] == 1 and report["by_member"] == {"IApp.GetValue": 1}
    [binding] = report["bindings"]
    assert binding["rule"] == "Generator"
    assert binding["recorded"] == "harmonic-analyzer @ 1ee7f38"
    assert binding["replayed"] == "harmonic-analyzer @ 1ee7f3806e"
    # The same commit binds the value to itself and rewrites nothing.
    replayer, _, stop = _replay(
        log, tmp_path / "same", monkeypatch, sha="1ee7f38", readback=True
    )
    assert stop is None and replayer.substitution_report()["count"] == 0
    assert recorded["summary"] == "summary: harmonic-analyzer @ 1ee7f38"


def test_only_a_readback_equal_to_the_masked_value_is_rebound(tmp_path, monkeypatch):
    # "Summary" contains the recorded stamp but is not it: served as recorded,
    # never rewritten by substring (the script did not write that string).
    log, recorded, _, _ = _record(tmp_path, monkeypatch, sha="1ee7f38", readback=True)
    replayer, replayed, stop = _replay(
        log, tmp_path / "x", monkeypatch, sha="feedbee", readback=True
    )
    assert stop is None
    assert replayed["summary"] == recorded["summary"]
    assert "1ee7f38" in replayed["summary"] and "feedbee" not in replayed["summary"]
    assert replayer.substitution_report()["count"] == 1


def test_an_unmasked_property_that_differs_still_diverges(tmp_path, monkeypatch):
    log, _, _, _ = _record(
        tmp_path, monkeypatch, sha="1ee7f38", year="2026", readback=True
    )
    replayer, _, stop = _replay(
        log, tmp_path / "x", monkeypatch, sha="feedbee", year="2027", readback=True
    )
    assert stop is not None and stop.verdict is conv.Verdict.DIVERGED
    divergence = stop.divergence.to_json()
    assert divergence["member_expected"] == "IApp.Add3"
    assert divergence["field"] == "args"
    assert "2026" in divergence["expected"]["args"]
    assert "2027" in divergence["actual"]["args"]
    # The Generator before it was rebound and its readback served rebound.
    assert replayer.substitution_report()["count"] == 1
