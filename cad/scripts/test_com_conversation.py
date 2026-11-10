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
    METHODS = frozenset({1, 2, 3, 4, 5, 7, 8, 9, 11})

    def __init__(self) -> None:
        self.calls = 0
        self.names: dict[str, str] = {}
        self.properties: list[tuple[Any, ...]] = []

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
            return {"part:plate": 1.25, "part:arm": 2.5}.get(ident, 0.5)
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
        self.app = IApp(server.root()) if server else None
        self.raw = server.root() if server else None
        self.calls_made = 0


async def scenario(adapter: Any, *, variant: str = "") -> dict[str, Any]:
    """Every path a build drives: early-bound methods and properties, typed
    returns, identity, byref outputs (values and an interface), a COM error,
    late binding, ``_com._com_invoke`` and a SolidWorks-written file."""
    app = adapter.app
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
        app.Add3("Generator", 30, "harmonic-analyzer @ 0123abc", 2)
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
    server = FakeServer()
    adapter = FakeAdapter(server)
    log = tmp_path / "logs" / "L1.jsonl.gz"
    with conv.recording(
        adapter,
        script=Path(__file__),
        log=log,
        roots=conv.Roots(out_root),
        audit=kwargs.pop("audit", False),
    ):
        result = asyncio.run(scenario(adapter, **kwargs))
    return log, result, server, adapter


def _replay(log: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, **kwargs: Any):
    scratch = tmp_path / "scratch"
    monkeypatch.setattr(_paths, "OUT_SLDPRT", scratch / "sldprt")
    conversation = conv.load(log)
    materialiser = conv.Materialiser(conversation, conv.capture_dir_of(log), scratch)
    replayer = conv.Replayer(
        conversation, conv.Roots(scratch), materialise=materialiser
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
    assert type(adapter.app._oleobj_) is FakeDispatch
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


def test_provenance_mask_covers_only_the_generator(tmp_path):
    def conversation(*args: Any) -> conv.Conversation:
        call = conv.Call(0, 1, "InvokeTypes", [9, 0, 1, [3, 0], [], *args], "IApp.Add3")
        header = conv.Header(1, "x", "x", "", "", None, {}, [], {}, {}, "")
        return conv.Conversation(header, [call], {})

    generator = conversation("Generator", 30, "harmonic-analyzer @ abc123", 2)
    rebuilt = conversation("Generator", 30, "harmonic-analyzer @ def456-dirty", 2)
    other = conversation("Material", 30, "harmonic-analyzer @ def456", 2)
    other_base = conversation("Material", 30, "harmonic-analyzer @ abc123", 2)
    assert conv.first_divergence(generator, rebuilt) is None
    assert conv.first_divergence(other_base, other) is not None
    assert conv.first_divergence(generator, rebuilt, mask=()) is not None


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
        adapter.app.Open(str(template))
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
