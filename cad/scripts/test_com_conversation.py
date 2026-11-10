"""Offline tests for COM-conversation record/replay (EXPERIMENT BRANCH ONLY).

No SolidWorks and no COM server: :class:`FakeDispatch` is a duck-typed
stand-in for pythoncom's ``PyIDispatch`` (the ``_com._RecordedInvoke``
precedent), registered with the engine as an interface type. Generated-style
wrappers (``IApp``/``IPart``, bogus CLSIDs) and pywin32's own late-bound
``CDispatch`` run their real code over it, so the funnel, the canonical form,
byref write-back, identity, errors and the sandbox are exercised exactly as a
build drives them. The one subprocess replay (``com_replay.py replay``) runs
the CLI end to end with the sandbox armed.
"""

from __future__ import annotations

import asyncio
import importlib.util
import json
import math
import os
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
from diagnostics import benchmark_replay_noop as leaf

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
    for escape in ("", "dispatch", "write"):
        env = dict(
            os.environ, OTEL_EXPORTER_OTLP_ENDPOINT="", OTEL_SERVICE_NAME="part-replay"
        )
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
    for escape in ("dispatch", "write"):
        rc, outcome = results[escape]
        assert rc == conv.EXIT_REPLAY_NOT_NOOP and outcome["verdict"] == "sandbox", (
            outcome
        )
        assert outcome["sandbox_violations"]
    assert not _SANDBOX_PROBE.exists()


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
    lines = leaf.render_k2(
        {"pass": False, "verdict": "diverged", "divergence": divergence},
        {"inert": replayer.inert_report()},
    )
    assert sum(line.startswith("    before: seq") for line in lines) == 5


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
    lines = leaf.render_k1({"pass": False, **requests})
    assert lines[1] == "  REQUEST divergence:" and len(lines) < leaf._EVIDENCE_LINES


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


def test_native_members_match_the_generated_wrapper():
    from solidworks_mcp.adapters._generated import sldworks_2026 as wrapper

    wrong = []
    for interface, member, shape in leaf.NATIVE_MEMBERS:
        cls = getattr(wrapper, interface)
        method = callable(cls.__dict__.get(member))
        actual = {
            leaf.Shape.METHOD: method and member not in cls._prop_map_get_,
            leaf.Shape.GET: member in cls._prop_map_get_ and not method,
            leaf.Shape.PUT: member in cls._prop_map_put_,
        }
        if not actual[shape]:
            wrong.append(f"{interface}.{member} is not a {shape.value}")
    assert not wrong, wrong


def test_ulp_control_log_diverges_at_the_perturbed_request(tmp_path, monkeypatch):
    log, _, _, _ = _record(tmp_path, monkeypatch)
    perturbed = log.with_name("L1-ulp.jsonl.gz")
    seq = leaf._perturb_first_float(conv, log, perturbed)
    first_float = next(c for c in conv.load(log).calls if c.site == "IApp.Add")
    assert seq == first_float.seq
    # The copy names the original's capture directory, so it replays unchanged.
    assert conv.load(perturbed).trailer["capture_dir"] == "L1.jsonl.gz.files"
    _, _, stop = _replay(perturbed, tmp_path, monkeypatch)
    assert stop is not None and stop.verdict is conv.Verdict.DIVERGED
    assert stop.divergence.seq == seq


def test_walk_read_points_follow_mass_property_handles(tmp_path):
    def call(seq, handle, op, args, site, result=None):
        return conv.Call(seq, handle, op, args, site, result)

    header_get = [0, 0, 2, {"t": [5, 0]}, {"t": []}]
    calls = [
        call(0, 1, "Invoke", [1, 0, 4, 0, "Boss1"], "IFeature.Name"),
        call(
            1,
            2,
            "InvokeTypes",
            [313, 0, 1, {"t": [9, 0]}, {"t": []}],
            "IModelDocExtension.CreateMassProperty2",
            {"h": 5, "p": "PyIDispatch"},
        ),
        call(
            2, 5, "QueryInterface", [], "__WrapDispatch", {"h": 6, "p": "PyIDispatch"}
        ),
        call(
            3, 6, "InvokeTypes", header_get, "IMassProperty2.Volume", {"f": (1.5).hex()}
        ),
        call(4, 7, "InvokeTypes", header_get, "IBody2.Volume", {"f": (9.0).hex()}),
        call(
            5,
            6,
            "InvokeTypes",
            header_get,
            "IMassProperty2.CenterOfMass",
            {"t": [{"f": (0.25).hex()}, {"f": (0.5).hex()}, {"f": (0.0).hex()}]},
        ),
    ]
    log = tmp_path / "points.jsonl.gz"
    writer = conv.LogWriter(log)
    writer.header(conv.Header(1, "x", "x", "", "", None, {}, [], {}, {}, ""))
    for item in calls:
        writer.emit(item)
    writer.close({})
    points = leaf._read_points(log)
    assert [(p["seq"], p["member"], p["feature"], p["recorded"]) for p in points] == [
        (3, "Volume", "Boss1", 1.5),
        (5, "CenterOfMass", "Boss1", [0.25, 0.5, 0.0]),
    ]
    assert all(p["creator"] == "CreateMassProperty2" for p in points)
    assert leaf._within(1.5, 1.5 * (1 + 5e-10)) and not leaf._within(
        1.5, 1.5 * (1 + 5e-9)
    )


def test_digest_comparison_uses_the_assembly_tolerances():
    body = {
        "mass_kg": 1.0,
        "volume_mm3": 100.0,
        "area_mm2": 50.0,
        "com_mm": [0.0, 0.0, 0.0],
        "moi_kgmm2": [1.0] * 6,
        "extreme_mm": [[1.0, 0.0, 0.0]] * 6,
        "faces": 6,
        "edges": 12,
        "vertices": 8,
    }
    digest = {
        "part": {k: body[k] for k in ("mass_kg", "volume_mm3", "area_mm2", "com_mm")}
        | {"moi_kgmm2": [1.0] * 9},
        "bodies": [body],
        "features": [["Boss1", "Extrusion", False]],
        "dimensions": [["D1@Sketch1@x.Part", 0.01]],
        "custom_properties": {},
        "equations": [],
        "errors": [],
    }
    assert leaf.compare_digests(digest, json.loads(json.dumps(digest))) == []
    nudged = json.loads(json.dumps(digest))
    nudged["bodies"][0]["volume_mm3"] += 5e-4  # inside 1e-3 mm^3
    assert leaf.compare_digests(digest, nudged) == []
    nudged["bodies"][0]["volume_mm3"] += 2e-3
    nudged["features"][0][2] = True
    differences = leaf.compare_digests(digest, nudged)
    assert len(differences) == 2 and differences[0].startswith("bodies[0].volume_mm3")


def test_clis_help_imports_no_com():
    for script in ("com_replay.py", "diagnostics/benchmark_replay_noop.py"):
        code = (
            "import runpy, sys\n"
            f"sys.argv = [{str(SCRIPTS / script)!r}, '--help']\n"
            "try:\n"
            f"    runpy.run_path({str(SCRIPTS / script)!r}, run_name='__main__')\n"
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


def test_experiment_modules_stay_out_of_every_recipe_closure():
    import _buildgraph

    experiment = ("_com_conversation.py", "com_replay.py", "benchmark_replay_noop.py")
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
        if Path(dep).name in experiment
    )
    assert not leaks
    importers = sorted(
        path.name
        for path in SCRIPTS.rglob("*.py")
        if path.name not in experiment
        and not path.name.startswith("test_")
        and any(
            name in path.read_text(encoding="utf-8")
            for name in ("_com_conversation", "com_replay", "benchmark_replay_noop")
        )
    )
    assert not importers


_K6_HELPER = (
    '"""Overlay-test helper: the function the K6 edits change."""\r\n'
    "\r\n"
    "\r\n"
    "def orient(app):\r\n"
    '    """Ask the application to add a step."""\r\n'
    "    step = 7\r\n"
    "    return app.Add(1.0, step)\r\n"
)
_K6_IDENTITY = (
    '"""Overlay-test provider: the commit the Generator stamp names."""\n'
    "\n"
    "\n"
    "def _git_sha() -> str:\n"
    '    """The recording\'s commit."""\n'
    '    return "0123abc"\n'
)


def test_source_change_controls_replay_through_an_overlay(tmp_path, monkeypatch):
    helpers = tmp_path / "helpers"
    helpers.mkdir()
    sources = {"k6_helper": _K6_HELPER, "k6_identity": _K6_IDENTITY}
    for module, text in sources.items():
        (helpers / f"{module}.py").write_bytes(text.encode("utf-8"))
    monkeypatch.syspath_prepend(str(helpers))
    helper = importlib.import_module("k6_helper")
    log, _, _, _ = _record(
        tmp_path, monkeypatch, probe=helper.orient, sha="0123abc", readback=True
    )
    script = tmp_path / "scripts" / "build_overlay_widget.py"
    script.parent.mkdir()
    script.write_text(
        "import sys\n"
        "import k6_helper\n"
        "import k6_identity\n"
        "from _session import run_build\n"
        "from test_com_conversation import scenario\n"
        "def build(adapter):\n"
        "    sha = k6_identity._git_sha()\n"
        "    return scenario(\n"
        "        adapter, probe=k6_helper.orient, sha=sha, readback=True\n"
        "    )\n"
        "if __name__ == '__main__':\n"
        "    sys.exit(run_build(build))\n",
        encoding="utf-8",
    )
    env = dict(
        os.environ,
        OTEL_EXPORTER_OTLP_ENDPOINT="",
        OTEL_SERVICE_NAME="part-replay",
        PYTHONPATH=str(helpers),
    )
    monkeypatch.setattr(leaf, "_K6_MODULE", "k6_helper")
    monkeypatch.setattr(leaf, "_K6_FUNCTION", "orient")
    monkeypatch.setattr(leaf, "_K6_PROVIDER_MODULE", "k6_identity")
    controls = {}
    for edit in leaf.SourceEdit:
        module, function = leaf._k6_target(edit)
        edited, description = leaf.source_edit(sources[module], function, edit)
        overlay = tmp_path / "overlays" / edit.value
        overlay.mkdir(parents=True)
        (overlay / f"{module}.py").write_bytes(edited.encode("utf-8"))
        result = tmp_path / f"{edit.value}.json"
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
                str(tmp_path / f"scratch-{edit.value}"),
                "--result",
                str(result),
                "--overlay",
                str(overlay),
            ],
            env=env,
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert result.is_file(), proc.stdout + proc.stderr
        payload = json.loads(result.read_text(encoding="utf-8"))
        child = leaf.ChildRun(edit.value, proc.returncode, 0.0, "-")
        controls[edit.value] = leaf._source_control(edit, description, child, payload)
    k6 = leaf._k6_verdict(controls)
    assert k6["pass"], (k6, controls)
    numeric = controls[leaf.SourceEdit.NUMERIC_LITERAL.value]
    assert numeric["member"] == "IApp.Add" and "k6_helper:orient:" in numeric["caller"]
    renamed = controls[leaf.SourceEdit.RENAME_LOCAL.value]["edit"]
    assert (renamed["from"], renamed["to"]) == ("step", "step_k6")
    cross = k6["cross_commit"]
    assert cross["substitution_count"] == 1
    assert cross["substituted_members"] == {"IApp.GetValue": 1}
    assert [(b["recorded"], b["replayed"]) for b in cross["bindings"]] == [
        ("harmonic-analyzer @ 0123abc", "harmonic-analyzer @ k6cross")
    ]
    same_commit = controls[leaf.SourceEdit.COMMENT_DOCSTRING.value]
    assert same_commit["substitutions"]["count"] == 0
    lines = leaf.render_k6(k6, controls)
    assert lines[0].startswith("K6 PASS") and len(lines) < leaf._EVIDENCE_LINES


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


def test_source_edits_keep_bytes_and_newlines_outside_the_edit():
    source = (
        "import os\r\n"
        "\r\n"
        "@staticmethod\r\n"
        "def target(a):\r\n"
        '    """Doc."""\r\n'
        '    label = "é"; count = 3\r\n'
        "    return os.sep * count + label + a\r\n"
    )
    edited, _ = leaf.source_edit(source, "target", leaf.SourceEdit.NUMERIC_LITERAL)
    assert edited == source.replace("count = 3", "count = 4")
    edited, described = leaf.source_edit(source, "target", leaf.SourceEdit.RENAME_LOCAL)
    assert described["from"] == "label"
    assert edited == source.replace("label", "label_k6")
    edited, _ = leaf.source_edit(source, "target", leaf.SourceEdit.COMMENT_DOCSTRING)
    lines = edited.split("\r\n")
    assert lines[2] == leaf._K6_COMMENT and lines[3] == "@staticmethod"
    assert "\n" not in edited.replace("\r\n", "")


def test_source_edits_refuse_unsafe_targets():
    def edit(source: str, kind: Any) -> Any:
        return leaf.source_edit(source, "f", kind)

    with pytest.raises(ValueError, match="calls"):
        edit("def f():\n    x = 1\n    return locals()\n", leaf.SourceEdit.RENAME_LOCAL)
    with pytest.raises(ValueError, match="no docstring"):
        edit("def f():\n    return 1\n", leaf.SourceEdit.COMMENT_DOCSTRING)
    with pytest.raises(ValueError, match="no numeric literal"):
        edit("def f():\n    return True\n", leaf.SourceEdit.NUMERIC_LITERAL)
    # Bound by a lambda parameter, spelled by an f-string's ``=``, an
    # attribute of a nested class, or already taken: each is skipped.
    source = (
        "def f():\n"
        "    x = 1\n"
        "    g = lambda x: x\n"
        "    s = f'{x=}'\n"
        "    class C:\n"
        "        y = 2\n"
        "    y = 3\n"
        "    t = 4\n"
        "    t_k6 = 5\n"
        "    u = 6\n"
        "    return g, s, C, y, t, t_k6, u\n"
    )
    edited, described = edit(source, leaf.SourceEdit.RENAME_LOCAL)
    assert described["from"] == "g", described
    assert "g_k6 = lambda x: x" in edited and "return g_k6, s" in edited
    edited, described = edit(
        "def f():\n    g = 0.5\n    return g\n", leaf.SourceEdit.NUMERIC_LITERAL
    )
    assert described["to"] == math.nextafter(0.5, math.inf)


def test_final_digest_ignores_only_the_documents_name():
    part = {key: 1.0 for key in ("mass_kg", "volume_mm3", "area_mm2", "com_mm")}
    part["moi_kgmm2"] = 1.0
    digest = {"part": part, "dimensions": [["D1@Sketch1@plate.Part", 0.01]]}
    walked = {"part": part, "dimensions": [["D1@Sketch1@plate~walk.Part", 0.01]]}
    assert leaf.compare_digests(digest, walked) == []
    renamed = {"part": part, "dimensions": [["D2@Sketch1@plate~walk.Part", 0.01]]}
    assert leaf.compare_digests(digest, renamed)[0].startswith("dimensions.names")
    assert leaf.dimension_key("Name@Feature") == "Name@Feature"


def test_read_point_error_distribution_and_recorded_spread():
    points = [
        {
            "seq": 1,
            "member": "CenterOfMass",
            "feature": "Boss1",
            "recorded": [1e-12, 0.5, 0.25],
            "live_after_rebuild": [2e-12, 0.5, 0.25],
        },
        {
            "seq": 2,
            "member": "CenterOfMass",
            "feature": "Boss1",
            "recorded": [1e-12, 0.5 * (1 + 1e-12), 0.25],
            "live_after_rebuild": [1e-12, 0.5, 0.25],
        },
        {
            "seq": 3,
            "member": "Mass",
            "feature": "Boss1",
            "recorded": 2.0,
            "live_after_rebuild": 2.0,
        },
    ]
    errors = leaf._error_distribution(points, "live_after_rebuild")
    com = errors["CenterOfMass"]
    assert com["count"] == 2 and com["component_max"] == pytest.approx(0.5)
    assert com["vector_max"] == pytest.approx(2e-12)
    assert com["absolute_max"] == pytest.approx(1e-12)
    assert errors["Mass"]["component_max"] == 0.0
    spread = leaf._recorded_spread(points)
    assert [(s["member"], s["seqs"]) for s in spread] == [("CenterOfMass", [1, 2])]
    k5 = {
        "pass": False,
        **leaf._walk_summary({"steps": [], "read_points": points}),
        "mass_settings": {
            "reads": {"CreateMassProperty2 accuracy 2": {"accuracy_level": 2}},
            "versus_first": {
                "CreateMassProperty2 accuracy 2": {"Mass": {"component": 0.0}}
            },
            "versus_recorded_final": {"CreateMassProperty2 accuracy 2": {"Mass": None}},
        },
    }
    lines = leaf.render_k5(k5)
    assert any("CenterOfMass x2" in line for line in lines)
    assert any("(AccuracyLevel 2): 0 / n/a" in line for line in lines)


def test_stem_specs_and_profiles():
    parser = leaf._parser()
    args = parser.parse_args(["benchmark", "--stem", "a:b", "--stem", "c:a:replay"])
    assert args.stems == [
        leaf.StemSpec("a", "b", leaf.Profile.FULL),
        leaf.StemSpec("c", "a", leaf.Profile.REPLAY),
    ]
    for bad in ("a", "a:a", "a:b:fast", "a::full"):
        with pytest.raises(SystemExit):
            parser.parse_args(["benchmark", "--stem", bad])
    assert leaf._PROFILE_PHASES[leaf.Profile.REPLAY] == {
        "phase1",
        "phase3",
        "phase3b",
        "phase6",
    }
    assert leaf._PROFILE_PHASES[leaf.Profile.FULL] == {k for k, _, _ in leaf._PHASES}


def test_replay_profile_runs_its_phases_and_a_seat_fault_stops_later_stems(
    tmp_path, monkeypatch
):
    import contextlib

    import _telemetry

    monkeypatch.setattr(leaf, "OUT", tmp_path)
    # Phase spans stay in this process: no exporter sees a test's stems.
    monkeypatch.setattr(_telemetry, "span", lambda *a, **k: contextlib.nullcontext())
    ran: list[tuple[str, str]] = []

    def stem(name: str, profile: Any) -> Any:
        built = leaf.Leaf(leaf.StemSpec(name, "other", profile))
        for key, _, _ in leaf._PHASES:
            monkeypatch.setattr(built, key, lambda key=key: ran.append((name, key)))
        monkeypatch.setattr(built, "assumptions", lambda: None)
        return built

    first = stem("first", leaf.Profile.REPLAY)
    leaf._run_stem(first, [])
    assert ran == [("first", key) for key in ("phase1", "phase3", "phase3b", "phase6")]
    phases = first.report["phases"]
    assert phases["phase0"]["reason"] == "not in the replay profile"
    assert first.report["exit"]["code"] == 0
    assert (tmp_path / "first" / "report.json").is_file()
    # An earlier stem's artefact rewritten: that stem faults, later ones stop.
    first.a1.parent.mkdir(parents=True)
    first.a1.write_bytes(b"A1")
    first.a1_sha = leaf.sha256(first.a1)
    first.a1.write_bytes(b"changed")
    second = stem("second", leaf.Profile.FULL)
    leaf._run_stem(second, [first])
    assert ran[-1][0] == "first" and second.report["exit"]["code"] is None
    assert first.seat_stopped() and leaf._combined_exit([first, second])[0] == 1
    assert first.report["seat_safety"]["violations"]


def test_k4_judges_the_default_caller_capture():
    def summary(callers: str, engine: float) -> dict[str, Any]:
        return {
            "callers": callers,
            "calls": 1000,
            "bytes": 100,
            "capture_bytes_stored": 50,
            "clock_seconds": {"engine": engine, "caller": 0.0},
            "trailer": {"escape_audit": {"seconds": 1.0}},
        }

    full = leaf._record_cost(103.0, 100.0, 90.0, 88.0, summary("full", 0.02), 200)
    default = leaf._record_cost(
        102.0, 100.0, 89.0, 88.0, summary("divergence", 0.01), 120
    )
    assert full["overhead_over_W0"] == pytest.approx(0.02)
    assert default["engine_us_per_call"] == pytest.approx(10.0)
    assert default["log_plus_captures_bytes"] == 150 > default["archive_bytes"]
    k4 = {
        "pass": False,
        "W0": 100.0,
        "W1": 103.0,
        "WR": 5.0,
        "WR_over_W1": 5 / 103,
        "window0": 88.0,
        "replay_window": 0.5,
        "default_callers": "divergence",
        "by_callers": {"full": full, "divergence": default},
    }
    lines = leaf.render_k4(k4)
    assert any("callers=divergence (default, judged)" in line for line in lines)
    assert any("vs outputs tar.gz 120 B" in line for line in lines)
