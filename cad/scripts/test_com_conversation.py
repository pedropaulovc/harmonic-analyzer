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
import dataclasses
import gzip
import importlib.util
import json
import math
import os
import socket
import subprocess
import struct
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
import _com_outcome
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

SHAPE_CLSID = "{0BADC0DE-0000-4000-8000-00000000A003}"
FACE_CLSID = "{0BADC0DE-0000-4000-8000-00000000A004}"
MASS_CLSID = "{0BADC0DE-0000-4000-8000-00000000A005}"
FEATURE_CLSID = "{0BADC0DE-0000-4000-8000-00000000A006}"


class ShapeServer(FakeServer):
    """One plate ``depth`` deep whose faces come in the order the seat lists
    them (``order``). Its volume and STL follow that order as SolidWorks'
    do: the volume sums face by face (the last bits move) and the STL lists
    one triangle per face, corners rotated and normal nudged by position."""

    ORDER = ("face:top", "face:bottom", "face:side")
    FACES = {
        "face:top": ((0.0, 1.0, 0.0), 0.1),
        "face:bottom": ((0.0, -1.0, 0.0), 0.2),
        "face:side": ((1.0, 0.0, 0.0), 0.3),
    }

    def __init__(self, order: tuple[str, ...] = ORDER) -> None:
        super().__init__()
        self.order = order
        self.depth = 0.0

    def invoke(self, target: FakeDispatch, dispid: int, flags: int, args: tuple) -> Any:
        if dispid < 20:
            return super().invoke(target, dispid, flags, args)
        self.calls += 1
        if dispid == 20:
            self.depth = args[0]
            return True
        if dispid == 21:
            return tuple(FakeDispatch(self, ident) for ident in self.order)
        if dispid == 22:
            return FakeDispatch(self, "mass")
        if dispid == 23:
            Path(args[0]).parent.mkdir(parents=True, exist_ok=True)
            Path(args[0]).write_bytes(self._stl())
            return True
        if dispid == 24:
            return self.FACES[target.ident][0]
        if dispid == 25:
            # Plain left-to-right addition (sum() compensates since 3.12).
            volume = 0.0
            for ident in self.order:
                volume += self.depth * self.FACES[ident][1]
            return volume
        if dispid == 26:
            # A symmetric plate: its centre of mass is noise around zero.
            noise = 1e-19 * self.order.index("face:bottom")
            return (noise, -noise, 0.0)
        if dispid == 28:
            return FakeDispatch(self, "feature:plate")
        return True  # 27: IFace2.Select

    def _stl(self) -> bytes:
        triangles = []
        for position, ident in enumerate(self.order):
            normal, _ = self.FACES[ident]
            corners = [
                struct.pack("<3f", *(self.depth * n + k for n in normal))
                for k in range(3)
            ]
            turn = position % 3
            facet = struct.pack("<3f", normal[0], normal[1] + 1e-7 * position, 0.0)
            triangles.append(
                facet + b"".join(corners[turn:] + corners[:turn]) + b"\0\0"
            )
        count = struct.pack("<I", len(triangles))
        return b"fake STL".ljust(80) + count + b"".join(triangles)


class IShapeApp(IApp):
    CLSID = pywintypes.IID(SHAPE_CLSID)

    def SetDepth(self, depth=0.0):  # noqa: N802
        return self._oleobj_.InvokeTypes(20, LCID, 1, (11, 0), ((5, 1),), depth)

    def GetFaces(self):  # noqa: N802
        return self._oleobj_.InvokeTypes(21, LCID, 1, (12, 0), ())

    def CreateMassProperty(self):  # noqa: N802
        ret = self._oleobj_.InvokeTypes(22, LCID, 1, (9, 0), ())
        if ret is not None:
            ret = Dispatch(ret, "CreateMassProperty", MASS_CLSID)
        return ret

    def ExportSTL(self, path=""):  # noqa: N802
        return self._oleobj_.InvokeTypes(23, LCID, 1, (11, 0), ((8, 1),), path)

    def CreateFeature(self):  # noqa: N802
        ret = self._oleobj_.InvokeTypes(28, LCID, 1, (9, 0), ())
        if ret is not None:
            ret = Dispatch(ret, "CreateFeature", FEATURE_CLSID)
        return ret


class IFeature(DispatchBaseClass):
    CLSID = pywintypes.IID(FEATURE_CLSID)
    coclass_clsid = None

    _prop_map_get_ = {"Name": (6, 2, (8, 0), (), "Name", None)}
    _prop_map_put_ = {"Name": ((6, LCID, 4, 0), ())}


class IFace2(DispatchBaseClass):
    CLSID = pywintypes.IID(FACE_CLSID)
    coclass_clsid = None

    def Select(self):  # noqa: N802
        return self._oleobj_.InvokeTypes(27, LCID, 1, (11, 0), ())

    _prop_map_get_ = {"Normal": (24, 2, (12, 0), (), "Normal", None)}


class IMassProperty(DispatchBaseClass):
    CLSID = pywintypes.IID(MASS_CLSID)
    coclass_clsid = None

    _prop_map_get_ = {
        "Volume": (25, 2, (5, 0), (), "Volume", None),
        "CenterOfMass": (26, 2, (12, 0), (), "CenterOfMass", None),
    }


win32com.client.CLSIDToClass.RegisterCLSID(SHAPE_CLSID, IShapeApp)
win32com.client.CLSIDToClass.RegisterCLSID(FACE_CLSID, IFace2)
win32com.client.CLSIDToClass.RegisterCLSID(FEATURE_CLSID, IFeature)
win32com.client.CLSIDToClass.RegisterCLSID(MASS_CLSID, IMassProperty)


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


async def shaped(
    adapter: Any,
    *,
    depth: float = 1.0,
    note: str = "BOND WITH LOCTITE 638",
    sha: str = "0123abc",
    measure: bool = True,
    export: bool = True,
    feature: str = "Plate",
) -> None:
    """A build that names its plate feature, then finds the plate's -Y face
    the way ``_holes.find_planar_face`` does (every face's normal, in the
    order the seat lists them), then writes properties, measures and exports."""
    app = IShapeApp(adapter.swApp._oleobj_)
    app.CreateFeature().Name = feature
    app.SetDepth(depth)
    chosen = None
    for raw in app.GetFaces():
        face = IFace2(raw)
        if face.Normal == (0.0, -1.0, 0.0):
            chosen = face
    chosen.Select()
    app.Add3("Generator", 30, f"harmonic-analyzer @ {sha}", 2)
    app.Add3("Note", 30, note, 2)
    if measure:
        mass = app.CreateMassProperty()
        assert mass.Volume > 0 and len(mass.CenterOfMass) == 3
    if export:
        app.ExportSTL(str(_paths.OUT_SLDPRT.parent / "stl" / "plate.STL"))


# FakeServer's RevisionNumber: what record_build reads before the window.
SW_REVISION = "34.3.0"


def _record(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, **kwargs: Any):
    out_root = tmp_path / "run1"
    monkeypatch.setattr(_paths, "OUT_SLDPRT", out_root / "sldprt")
    server = kwargs.pop("server", None) or FakeServer()
    build = kwargs.pop("build", scenario)
    adapter = FakeAdapter(server)
    log = tmp_path / "logs" / "L1.jsonl.gz"
    with conv.recording(
        adapter,
        script=Path(__file__),
        log=log,
        roots=conv.Roots(out_root),
        sw_revision=kwargs.pop("sw_revision", SW_REVISION),
        audit=kwargs.pop("audit", False),
        callers=kwargs.pop("callers", conv.CallerCapture.FULL),
    ):
        result = asyncio.run(build(adapter, **kwargs))
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


def test_a_proxys_hash_is_the_same_in_inert_and_recipe_code(tmp_path, monkeypatch):
    # hash() is a function of the COM object, not of whoever hashes it: a dict
    # filled by recipe code and probed by inert code (or the reverse) hits.
    inert_hash = conv._inert_entry(hash)
    inert_get = conv._inert_entry(dict.get)
    observed: list[tuple[Any, ...]] = []

    def probe(app: Any) -> None:
        plate = app.GetPart("plate")._oleobj_
        arm = app.GetPart("arm")._oleobj_
        first = inert_hash(arm)  # inert code meets arm first
        table = {plate: "plate", arm: "arm"}  # then recipe code
        observed.append(
            (
                first == hash(arm),
                inert_hash(plate) == hash(plate),
                inert_get(table, plate),
                inert_get(table, arm),
                table.get(app.GetPart("plate")._oleobj_),  # an equal new proxy
            )
        )

    log, _, _, _ = _record(tmp_path, monkeypatch, probe=probe)
    hashes = [c for c in conv.load(log).calls if c.op == "__hash__"]
    assert {c.origin for c in hashes} == {conv.Origin.INERT, conv.Origin.RECIPE}
    replayer, _, stop = _replay(log, tmp_path, monkeypatch, probe=probe)
    verdict, divergence, _ = replayer.finish()
    assert stop is None and verdict is conv.Verdict.NOOP and divergence is None
    assert observed == [(True, True, "plate", "arm", "plate")] * 2


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
        adapter,
        script=Path(__file__),
        log=log,
        roots=conv.Roots(out_root),
        sw_revision=SW_REVISION,
        audit=False,
    ):
        adapter.swApp.Open(str(template))
    loaded = conv.load(log)
    assert conv.check_inputs(loaded, loaded.header) == []
    template.write_bytes(b"template v2")
    monkeypatch.setenv("HARMONIC_FIT_GROUPS", "changed")
    mismatched = {m["input"] for m in conv.check_inputs(loaded, loaded.header)}
    assert "env:HARMONIC_FIT_GROUPS" in mismatched
    assert any(name.endswith("template.prtdot") for name in mismatched)


def test_a_log_of_another_format_is_an_input_mismatch(tmp_path, monkeypatch):
    # A schema-1 log mirrored each capture under its output path; it must
    # never be replayed by an engine that reads the flat layout.
    adapter = FakeAdapter(FakeServer())
    log = tmp_path / "L.jsonl.gz"
    with monkeypatch.context() as old:
        old.setattr(conv, "SCHEMA", conv.SCHEMA - 1)
        with conv.recording(
            adapter,
            script=Path(__file__),
            log=log,
            roots=conv.Roots(tmp_path / "out"),
            sw_revision=SW_REVISION,
            audit=False,
        ):
            adapter.swApp.Add(1.0, 2.0)
    loaded = conv.load(log)
    assert conv.check_inputs(loaded, loaded.header) == [
        {"input": "schema", "recorded": conv.SCHEMA - 1}
    ]


def test_another_or_unknown_solidworks_revision_refuses_the_replay(
    tmp_path, monkeypatch
):
    log, _, _, _ = _record(tmp_path / "base", monkeypatch)
    seat, _, _, _ = _record(tmp_path / "seat", monkeypatch, sw_revision="34.4.0")
    loaded = conv.load(log)
    assert loaded.header.sw_revision == SW_REVISION
    assert conv.check_inputs(loaded, conv.read_header(log)) == []
    other = {"input": "sw_revision", "recorded": SW_REVISION, "replay": "34.4.0"}
    assert conv.check_inputs(loaded, conv.read_header(seat)) == [other]
    unknown = dataclasses.replace(loaded.header, sw_revision=None)
    assert conv.check_inputs(dataclasses.replace(loaded, header=unknown), unknown) == [
        {"input": "sw_revision", "recorded": None, "replay": None}
    ]
    # The whole replay refuses before it installs anything or runs a script.
    scratch = tmp_path / "scratch"
    result = conv.replay_build(Path(__file__), log, scratch, None, seat_log=seat)
    assert result.verdict is conv.Verdict.INPUT_MISMATCH
    assert result.details["input_mismatches"] == [other]
    assert result.served == 0 and not scratch.exists()


def test_cli_replays_a_recorded_build_in_a_sandboxed_subprocess(tmp_path, monkeypatch):
    log, recorded, _, _ = _record(tmp_path, monkeypatch, audit=True)
    trailer = conv.load(log).trailer
    [[(rel, kept)]] = [list(files.items()) for files in trailer["captured"].values()]
    written = tmp_path / "run1" / rel
    assert rel == "sldprt/fake.SLDPRT" and kept == {
        "file": conv.capture_name(0),
        "sha256": conv.sha256_file(written),
        "size": written.stat().st_size,
    }
    captured = {rel: kept["sha256"]}
    # Stored flat under a short name, never under the output's own path.
    capture_dir = conv.capture_dir_of(log)
    stored = sorted(
        p.relative_to(capture_dir).as_posix()
        for p in capture_dir.rglob("*")
        if p.is_file()
    )
    assert stored == ["000000.gz"] and trailer["capture_stored_bytes"] > 0
    assert trailer["capture_files"] == 1
    assert len(conv.capture_name(999_999)) == len(conv.capture_name(0))
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
                "--seat-log",
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


_REORDERED = ("face:bottom", "face:side", "face:top")
_ALL_SAME = {"mass": "same", "requests": "same", "answers": "same", "stl": "same"}


def _shaped(
    root: Path, monkeypatch: pytest.MonkeyPatch, order=ShapeServer.ORDER, **kwargs
):
    server = ShapeServer(order)
    log, _, _, _ = _record(root, monkeypatch, server=server, build=shaped, **kwargs)
    return log


def _diff(base: Path, new: Path, result: Path) -> dict[str, Any]:
    """``com_replay.py diff``, as the shadow runs it."""
    import com_replay

    rc = com_replay.main(["diff", str(base), str(new), "--result", str(result)])
    payload = json.loads(result.read_text("utf-8"))
    assert rc == (0 if payload["request_divergence"] is None else 91)
    return payload


def _stl_bytes(log: Path) -> bytes:
    [kept] = [
        kept
        for files in conv.load(log).trailer["captured"].values()
        for rel, kept in files.items()
        if rel.endswith(".STL")
    ]
    return conv.capture_dir_of(log).joinpath(kept["file"]).read_bytes()


def test_a_face_order_change_diverges_on_a_response_and_makes_the_same_part(
    tmp_path, monkeypatch
):
    base = _shaped(tmp_path / "a", monkeypatch)
    reordered = _shaped(tmp_path / "b", monkeypatch, _REORDERED)
    # The seat's noise is real: another volume in the last bit, a centre of
    # mass that is noise around zero, other STL bytes.
    volume, com = (
        [
            c.result
            for log in (base, reordered)
            for c in conv.load(log).calls
            if c.site == site
        ]
        for site in ("IMassProperty.Volume", "IMassProperty.CenterOfMass")
    )
    assert volume[0] != volume[1] and _stl_bytes(base) != _stl_bytes(reordered)
    assert not _com_outcome._close(com[0], com[1])
    diff = _diff(base, reordered, tmp_path / "diff.json")
    divergence = diff["request_divergence"]
    assert (divergence["member_expected"], divergence["field"]) == (
        "IFace2.Select",
        "handle",
    )
    assert diff["truth_cause"] == "response:IFace2.Normal"
    assert diff["outcome"] == "same" and diff["outcome_signals"] == _ALL_SAME


def test_a_changed_dimension_diverges_on_a_request_and_makes_another_part(
    tmp_path, monkeypatch
):
    base = _shaped(tmp_path / "a", monkeypatch)
    deeper = _shaped(tmp_path / "b", monkeypatch, depth=1.5)
    diff = _diff(base, deeper, tmp_path / "diff.json")
    divergence = diff["request_divergence"]
    assert (divergence["member_expected"], divergence["field"]) == (
        "IShapeApp.SetDepth",
        "args",
    )
    assert diff["truth_cause"] == "request" and diff["outcome"] == "different"
    assert set(diff["outcome_signals"].values()) == {"different"}
    assert diff["outcome_details"]["mass"]["member"] == "IMassProperty.Volume"
    assert diff["outcome_details"]["requests"] == {"IShapeApp.SetDepth": [1, 1]}


def test_a_property_edit_is_another_part_and_provenance_is_not(tmp_path, monkeypatch):
    base = _shaped(tmp_path / "a", monkeypatch)
    noted = _shaped(tmp_path / "b", monkeypatch, note="BOND WITH LOCTITE 648")
    diff = _diff(base, noted, tmp_path / "diff.json")
    assert diff["truth_cause"] == "request" and diff["outcome"] == "different"
    assert diff["outcome_signals"] == {
        **_ALL_SAME,
        "requests": "different",
        "answers": "different",
    }
    assert diff["outcome_details"]["requests"] == {"IShapeApp.Add3": [1, 1]}
    # Another commit stamps another Generator value: masked, the same part.
    stamped = _shaped(tmp_path / "c", monkeypatch, sha="feedbee")
    diff = _diff(base, stamped, tmp_path / "stamped.json")
    assert diff["request_divergence"] is None and diff["truth_cause"] is None
    assert diff["outcome"] == "same" and diff["outcome_signals"] == _ALL_SAME


def test_an_outcome_without_mass_or_stl_is_unknown_unless_something_differs(
    tmp_path, monkeypatch
):
    def outcome(name: str, **kwargs: Any) -> dict[str, Any]:
        base = _shaped(tmp_path / name / "a", monkeypatch, **kwargs)
        new = _shaped(tmp_path / name / "b", monkeypatch, _REORDERED, **kwargs)
        diff = _diff(base, new, tmp_path / name / "diff.json")
        return {k: diff[k] for k in ("outcome", "outcome_signals")}

    assert outcome("unmeasured", measure=False) == {
        "outcome": "unknown",
        "outcome_signals": {**_ALL_SAME, "mass": "absent"},
    }
    assert outcome("unexported", export=False) == {
        "outcome": "unknown",
        "outcome_signals": {**_ALL_SAME, "stl": "absent"},
    }
    # Absent signals never hide a difference.
    base = _shaped(tmp_path / "c", monkeypatch, measure=False, export=False)
    deeper = _shaped(
        tmp_path / "d", monkeypatch, depth=2.0, measure=False, export=False
    )
    assert _diff(base, deeper, tmp_path / "d.json")["outcome"] == "different"
    # Measured on one side only: different, not unknown.
    measured = _shaped(tmp_path / "e", monkeypatch, export=False)
    diff = _diff(base, measured, tmp_path / "e.json")
    assert (diff["outcome"], diff["outcome_signals"]["mass"]) == (
        "different",
        "different",
    )
    # An STL capture that cannot be read is no evidence.
    left = _shaped(tmp_path / "f", monkeypatch)
    right = _shaped(tmp_path / "g", monkeypatch)
    for capture in conv.capture_dir_of(right).iterdir():
        capture.unlink()
    diff = _diff(left, right, tmp_path / "g.json")
    assert (diff["outcome"], diff["outcome_signals"]["stl"]) == ("unknown", "absent")


def test_outcome_noise_is_title_counters_provenance_and_last_bits():
    text = _com_outcome._text
    assert text("D1@Sketch1@Part11.Part") == text("D1@Sketch1@Part12.Part")
    assert text("Assem3") == text("Assem4") and text("Part11") != text("Partial11")
    assert text("harmonic-analyzer @ 1ee7f38") == text("harmonic-analyzer @ feedbee")
    assert text("summary: harmonic-analyzer @ 1ee7f38") != text(
        "summary: harmonic-analyzer @ feedbee"
    )

    def floats(*values: float) -> dict[str, Any]:
        return {"t": [{"f": v.hex()} for v in values]}

    # Within 1e-9 of the value's largest component, or of the floor.
    assert _com_outcome._close(floats(1.0, 1e-20), floats(1.0 + 1e-12, -1e-20))
    assert not _com_outcome._close(floats(1.0, 0.0), floats(1.0, 1e-8))
    assert not _com_outcome._close(floats(1e-19, 0.0), floats(0.0, 0.0))
    assert _com_outcome._close(floats(1e-19, 0.0), floats(0.0, 0.0), 0.5)
    # Handles are identity: kept by the aligned comparison, erased in sets.
    assert not _com_outcome._close({"h": 3, "p": "X"}, {"h": 4, "p": "X"})
    assert _com_outcome._keyed({"h": 3, "p": "X"}) == _com_outcome._keyed(
        {"h": 4, "p": "X"}
    )


def test_a_divergence_is_labelled_at_or_after_the_last_named_feature(
    tmp_path, monkeypatch
):
    base = _shaped(tmp_path / "a", monkeypatch)
    # The divergence is the naming itself: at the feature.
    renamed = _shaped(tmp_path / "b", monkeypatch, feature="PlateBlank")
    divergence = _diff(base, renamed, tmp_path / "b.json")["request_divergence"]
    assert divergence["member_expected"] == "IFeature.Name"
    assert divergence["feature"] == "at Plate"
    assert "lies at the last IFeature.Name" in divergence["feature_basis"]
    # A later request: after it.
    deeper = _shaped(tmp_path / "c", monkeypatch, depth=1.5)
    divergence = _diff(base, deeper, tmp_path / "c.json")["request_divergence"]
    assert divergence["member_expected"] == "IShapeApp.SetDepth"
    assert divergence["feature"] == "after Plate"
    unnamed = {"feature": None}
    _com_outcome.label_feature(unnamed)
    _com_outcome.label_feature(None)
    assert unnamed == {"feature": None}


_SOLID = (0.002, 0.003, -0.125, 6.1e-05, 0.0231, 0.48)
_INERTIA = (2.46e-07, 2.57e-07, 1.14e-08, 1.5e-24, -3.0e-25, 2.0e-25)


def _body_mass(*values: float) -> conv.Call:
    """An ``IBody2.GetMassProperties`` answer: CenterOfMassX..Z, volume,
    area, mass, MomXX, MomYY, MomZZ, MomXY, MomZX, MomYZ (API reference)."""
    result = {"t": [{"f": float(v).hex()} for v in values]}
    return conv.Call(0, 1, "InvokeTypes", [], "IBody2.GetMassProperties", result=result)


def test_a_mass_property_array_is_judged_quantity_by_quantity():
    base = _body_mass(*_SOLID, *_INERTIA)

    def judged(*values: float) -> str:
        return _com_outcome._mass_signal([base], [_body_mass(*values)])[0].value

    volume, area, mass = _SOLID[3:]
    # Last-bit noise in every quantity, near-zero products of inertia
    # included: the same body.
    noisy = [math.nextafter(v, math.inf) for v in (*_SOLID, *_INERTIA)]
    assert judged(*noisy) == "same"
    assert judged(*_SOLID, *_INERTIA[:3], 3.0e-24, -1.0e-25, 0.0) == "same"
    # A 1e-6 relative change of any one quantity: another body. The volume's
    # (6e-11 m^3) is below 1e-9 of the array's largest element (the mass).
    for index, value in ((3, volume), (4, area), (5, mass)):
        changed = list(_SOLID)
        changed[index] = value * (1 + 1e-6)
        assert judged(*changed, *_INERTIA) == "different", index
    assert judged(*_SOLID, _INERTIA[0] * (1 + 1e-6), *_INERTIA[1:]) == "different"
    # A symmetric body's centre is noise around zero: judged on its length.
    centred = _body_mass(1e-19, -2e-19, 0.0, *_SOLID[3:], *_INERTIA)
    shifted = _body_mass(-3e-19, 0.0, 1e-19, *_SOLID[3:], *_INERTIA)
    assert _com_outcome._mass_signal([centred], [shifted])[0].value == "same"
    # The 13-element forms end with the accuracy, compared on its own.
    accurate = _body_mass(*noisy, 1.0)
    assert (
        _com_outcome._mass_signal([accurate], [_body_mass(*_SOLID, *_INERTIA, 1.0)])[
            0
        ].value
        == "same"
    )
    coarse = _body_mass(*_SOLID, *_INERTIA, 2.0)
    assert _com_outcome._mass_signal([accurate], [coarse])[0].value == "different"


def _mass(a: list[conv.Call], b: list[conv.Call]) -> tuple[str, Any]:
    signal, detail = _com_outcome._mass_signal(a, b)
    return signal.value, detail


def _bodies(*bodies: tuple[float, ...]) -> list[conv.Call]:
    return [_body_mass(*body, *_INERTIA) for body in bodies]


# One configuration's four bodies (centre x/y/z, volume, area, mass), placed
# like sh_vn_chain_link's (2026-11-11): two plates, two pins.
_LINKS = (
    (0.0, 0.0, 0.0, 6.1e-05, 0.0231, 0.48),
    (0.00635, 0.0, 0.0, 6.1e-05, 0.0231, 0.48),
    (0.003175, 0.0, -0.00205, 2.4e-07, 0.00041, 0.0019),
    (0.003175, 0.0, 0.00205, 2.4e-07, 0.00041, 0.0019),
)


def test_mass_measurements_match_in_any_order():
    base = _bodies(*_LINKS)
    # The same bodies measured in another order: the same part.
    assert _mass(base, _bodies(*_LINKS[1:], _LINKS[0]))[0] == "same"
    assert _mass(base, _bodies(_LINKS[1], _LINKS[0], *_LINKS[2:]))[0] == "same"
    # One body's volume 1e-6 larger, in another order: another part. The
    # detail names that body (the base's third) against its grown self (the
    # new build's second) and the volume, not the mirrored pin now in its
    # place, whose centre differs.
    grown = (*_LINKS[2][:3], _LINKS[2][3] * (1 + 1e-6), *_LINKS[2][4:])
    signal, detail = _mass(base, _bodies(_LINKS[1], grown, _LINKS[3], _LINKS[0]))
    assert signal == "different"
    assert {k: detail[k] for k in ("member", "quantity", "ordinal", "nearest")} == {
        "member": "IBody2.GetMassProperties",
        "quantity": "Volume",
        "ordinal": 2,
        "nearest": 1,
    }
    assert float(detail["tolerances"]) == pytest.approx(1e3, rel=0.01)
    # A body more: counted.
    assert _mass(base, _bodies(*_LINKS, _LINKS[0])) == (
        "different",
        {"counts": {"IBody2.GetMassProperties": [4, 5]}},
    )


def test_mass_measurements_match_by_assignment_not_greedily():
    # Volumes 0.9 of the tolerance apart: mid is close to lo and to hi, lo
    # and hi are not close. Paired greedily in call order, mid takes lo and
    # strands the base's lo; the assignment pairs mid with hi.
    volume = _SOLID[3]
    step = 0.9 * _com_outcome.REL_TOL * volume
    lo, mid, hi = volume, volume + step, volume + 2 * step

    def body(value: float) -> conv.Call:
        return _body_mass(*_SOLID[:3], value, *_SOLID[4:], *_INERTIA)

    assert _mass([body(mid), body(lo)], [body(lo), body(hi)])[0] == "same"
    assert _mass([body(lo), body(lo)], [body(lo), body(hi)])[0] == "different"


def _measured(handle: int, volume: float, centre: tuple[float, ...]) -> list[conv.Call]:
    """One IMassProperty object read for its volume, then its centre."""
    return [
        conv.Call(
            0,
            handle,
            "InvokeTypes",
            [],
            "IMassProperty.Volume",
            result={"f": volume.hex()},
        ),
        conv.Call(
            0,
            handle,
            "InvokeTypes",
            [],
            "IMassProperty.CenterOfMass",
            result={"t": [{"f": c.hex()} for c in centre]},
        ),
    ]


def test_an_imassproperty_object_is_one_measurement():
    first, second = (1e-5, (0.01, 0.0, 0.0)), (2e-5, (0.0, 0.02, 0.0))
    base = [*_measured(7, *first), *_measured(8, *second)]
    # The same objects in another order, or their reads interleaved.
    assert _mass(base, [*_measured(3, *second), *_measured(4, *first)])[0] == "same"
    one, two = _measured(5, *first), _measured(6, *second)
    assert _mass(base, [one[0], two[0], one[1], two[1]])[0] == "same"
    # Each volume with the other's centre: the same answers per member, but
    # other bodies. The nearest unpaired one is judged on its volume.
    swapped = [*_measured(7, first[0], second[1]), *_measured(8, second[0], first[1])]
    signal, detail = _mass(base, swapped)
    assert (signal, detail["ordinal"], detail["nearest"]) == ("different", 0, 1)
    assert (detail["member"], detail["quantity"]) == ("IMassProperty.Volume", "Volume")


def _stl(*triangles: tuple[tuple[float, ...], ...], normal=(0.0, 0.0, 0.0)) -> bytes:
    """A binary STL: header, count, per triangle a facet normal (never
    judged), three corners and two attribute bytes."""
    body = b"".join(
        struct.pack("<3f", *normal)
        + b"".join(struct.pack("<3f", *corner) for corner in triangle)
        + b"\0\0"
        for triangle in triangles
    )
    return b"fake STL".ljust(80) + struct.pack("<I", len(triangles)) + body


def _compared(a: bytes, b: bytes) -> tuple[bool, str | None]:
    return _com_outcome._stl_comparison(
        _com_outcome._triangles(a), _com_outcome._triangles(b)
    )


def _geometry(a: list[tuple], b: list[tuple]) -> str | None:
    """What differs between two STLs' geometry, ``None`` for nothing."""
    same, detail = _compared(_stl(*a), _stl(*b))
    return None if same else detail


def _tilted(x: float, y: float) -> tuple[float, float, float]:
    """A point of a plane tilted like the platform's side walls, so its
    float32 corners carry noise."""
    return (10.0 + 0.98877 * x, 20.0 + y, -200.0 + 0.14944 * x)


def test_stl_geometry_ignores_how_a_planar_face_is_triangulated():
    p = [_tilted(x, y) for x, y in ((0, 0), (4, 0), (4, 3), (0, 3))]
    split = [(p[0], p[1], p[2]), (p[0], p[2], p[3])]
    assert _geometry(split, [(p[1], p[2], p[3]), (p[1], p[3], p[0])]) is None
    hexagon = [
        _tilted(5 * math.cos(k * math.pi / 3), 5 * math.sin(k * math.pi / 3))
        for k in range(6)
    ]
    fan = [(hexagon[0], hexagon[k], hexagon[k + 1]) for k in range(1, 5)]
    refan = [
        (hexagon[3], hexagon[(3 + k) % 6], hexagon[(4 + k) % 6]) for k in range(1, 5)
    ]
    assert _geometry(fan, refan) is None
    # Triangle order, corner rotation and facet normals are no geometry.
    shuffled = [(c, a, b) for a, b, c in reversed(fan)]
    assert _stl(*fan) != _stl(*shuffled, normal=(1.0, 2.0, 3.0))
    assert _compared(_stl(*fan), _stl(*shuffled, normal=(1.0, 2.0, 3.0))) == (
        True,
        None,
    )
    # A moved vertex, or the same face inside out, is other geometry.
    moved = [*hexagon[:2], _tilted(5.0, 0.001), *hexagon[3:]]
    assert _geometry(fan, [(moved[0], moved[k], moved[k + 1]) for k in range(1, 5)])
    assert _geometry(fan, [(a, c, b) for a, b, c in fan]).startswith("plane outlines")


def test_stl_geometry_tells_a_moved_hole_at_equal_area_and_vertices():
    # A 4 x 1 strip of squares with one left open: the same ten vertices and
    # the same area, the opening moved.
    def strip(*squares: int) -> list[tuple]:
        found = []
        for x in squares:
            a, b, c, d = (
                _tilted(x, 0),
                _tilted(x + 1, 0),
                _tilted(x + 1, 1),
                _tilted(x, 1),
            )
            found += [(a, b, c), (a, c, d)]
        return found

    assert _geometry(strip(0, 1, 3), strip(0, 1, 3)) is None
    assert _geometry(strip(0, 1, 3), strip(0, 2, 3)).startswith("plane outlines")


def test_stl_geometry_of_a_curved_face_is_its_facets():
    # A cylinder strip: each flat facet is a plane of its own.
    ring = [(10 * math.cos(k / 10), 10 * math.sin(k / 10)) for k in range(4)]
    low, high = [(x, y, 0.0) for x, y in ring], [(x, y, 5.0) for x, y in ring]
    facets = [
        triangle
        for k in range(3)
        for triangle in (
            (low[k], low[k + 1], high[k + 1]),
            (low[k], high[k + 1], high[k]),
        )
    ]
    assert _geometry(facets, list(reversed(facets))) is None
    # A triangle removed or added: other geometry.
    assert _geometry(facets, facets[:3] + facets[4:])
    assert _geometry(facets, [*facets, (low[0], low[2], high[1])])
    # A non-planar quad split along its other diagonal reads as other
    # geometry: the conservative direction (a missed reuse, never unsound).
    q = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.1), (1.0, 1.0, 0.0), (0.0, 1.0, 0.1)]
    assert _geometry(
        [(q[0], q[1], q[2]), (q[0], q[2], q[3])],
        [(q[1], q[2], q[3]), (q[1], q[3], q[0])],
    )
    # Anything but a well-formed binary STL is compared byte for byte.
    text = b"solid fake\nendsolid fake\n"
    assert _com_outcome._triangles(text).startswith("bytes:")
    assert _compared(text, text) == (True, None)
    assert _compared(text, text + b" ") == (False, "bytes")
    # A right-sized binary STL with a NaN or an infinity is its digest.
    corners = [(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)]
    finite = _stl(tuple(corners))
    for bad in (math.nan, math.inf, -math.inf):
        broken = _stl((corners[0], corners[1], (bad, 1.0, 0.0)))
        assert _com_outcome._triangles(broken).startswith("bytes:"), bad
        assert _compared(finite, broken) == (False, "bytes")


def _nudged(point: tuple[float, ...], axis: int, ulps: int) -> tuple[float, ...]:
    """``point`` as float32 with one coordinate ``ulps`` float32 steps away."""
    bits = struct.unpack("<i", struct.pack("<f", point[axis]))[0]
    moved = struct.unpack("<f", struct.pack("<i", bits + ulps))[0]
    return tuple(moved if i == axis else c for i, c in enumerate(point))


def _plate(columns: int, *flipped: int) -> list[tuple]:
    """A tilted plate of unit squares, each split along one diagonal (the
    other for the ``flipped`` ones)."""
    found = []
    for x in range(columns):
        a, b, c, d = _tilted(x, 0), _tilted(x + 1, 0), _tilted(x + 1, 1), _tilted(x, 1)
        found += [(a, b, d), (b, c, d)] if x in flipped else [(a, b, c), (a, c, d)]
    return found


def _moved(triangles: list[tuple], points: dict[tuple, tuple]) -> list[tuple]:
    return [tuple(points.get(p, p) for p in triangle) for triangle in triangles]


def _float32(point: tuple[float, ...]) -> tuple[float, ...]:
    return struct.unpack("<3f", struct.pack("<3f", *point))


def _eps(triangles: list[tuple]) -> float:
    largest = max(abs(c) for triangle in triangles for p in triangle for c in p)
    ulp = math.ldexp(1.0, math.frexp(largest)[1] - 24)
    return _com_outcome._STL_VERTEX_ULPS * ulp


def test_stl_vertices_within_float32_noise_are_one():
    plate = _plate(4)
    corners = sorted({p for triangle in plate for p in triangle})
    # 2026-11-12, fr_nameplate: the same model wrote 415-458 of 25348
    # vertices 1-3 float32 ulps of the coordinate off, or 2e-16 where the
    # other wrote 0.
    noise = {p: _nudged(p, k % 2, 1 + k % 3) for k, p in enumerate(corners) if k % 2}
    same, detail = _compared(_stl(*plate), _stl(*_moved(plate, noise)))
    assert same
    assert detail.startswith(f"{len(noise)} vertices paired within eps")
    # The same, re-triangulated: still the same geometry.
    assert _compared(_stl(*_plate(4)), _stl(*_moved(_plate(4, 1, 2), noise)))[0]
    # Exact zeros against float64 residues, re-triangulated: both STLs take
    # one representative, so the residue moves no triangle to another plane.
    flat = [(float(x), float(y), 0.0) for x, y in ((0, 0), (5, 0), (5, 3), (0, 3))]
    square = [(flat[0], flat[1], flat[2]), (flat[0], flat[2], flat[3])]
    other = [(flat[1], flat[2], flat[3]), (flat[1], flat[3], flat[0])]
    residue = {flat[2]: (5.0, 3.0, 2.0**-52), flat[3]: (0.0, 3.0, -(2.0**-50))}
    assert _compared(_stl(*square), _stl(*_moved(square, residue)))[0]
    assert _compared(_stl(*square), _stl(*_moved(other, residue)))[0]
    assert _compared(_stl(*_moved(other, residue)), _stl(*square))[0]


def test_stl_vertices_beyond_eps_or_paired_ambiguously_are_other_geometry():
    plate = _plate(4)
    eps = _eps(plate)
    p = _tilted(2, 1)
    x, y, z = _float32(p)
    detail = _geometry(plate, _moved(plate, {p: (x + 2 * eps, y, z)}))
    assert detail.startswith("vertices: 1 base only, 1 new only: one with 0 within")
    # A vertex split in two within eps: a vertex more.
    split = plate[:3] + _moved(plate[3:], {p: _nudged(p, 0, 1)})
    assert _geometry(plate, split) == "vertices: 0 base only, 1 new only"
    # Two of the other STL's vertices within eps of one.
    a, b, c, far = _tilted(0, 0), _tilted(1, 0), _tilted(0, 1), _tilted(9, 9)
    q = _float32(_tilted(1, 1))
    base = [(a, b, q), (a, c, far)]
    two = [(a, b, _nudged(q, 1, 1)), (a, c, _nudged(q, 1, -1))]
    assert "one with 2 within eps" in _geometry(base, two)
    # One within eps of a vertex both STLs have.
    near = [(a, b, q), (a, c, _nudged(q, 1, 2))]
    assert "of a matched vertex" in _geometry(near, [(a, b, q), (a, c, far)])
    # One whose counterpart is also within eps of another of its own.
    crowded = [(a, b, _nudged(q, 1, -1)), (a, c, _nudged(q, 1, 1))]
    assert "not mutually unique" in _geometry(crowded, [(a, b, q), (a, c, far)])


def test_stl_noise_does_not_hide_a_moved_hole():
    def strip(*squares: int) -> list[tuple]:
        return [t for x in squares for t in _plate(4)[2 * x : 2 * x + 2]]

    corners = sorted({p for triangle in strip(0, 2, 3) for p in triangle})
    noise = {p: _nudged(p, 1, 1) for p in corners[::3]}
    detail = _geometry(strip(0, 1, 3), _moved(strip(0, 2, 3), noise))
    assert detail.startswith("plane outlines: 1 base only, 1 new only (")
    assert f"({len(noise)} vertices paired within eps" in detail


def _corrupt_stl_record(log: Path) -> None:
    """Drop the file name from the log's record of its STL capture (the
    engine's capture comparison reads only its sha256)."""
    lines = gzip.decompress(log.read_bytes()).decode("utf-8").splitlines()
    for index, text in enumerate(lines):
        line = json.loads(text)
        if "trailer" not in line:
            continue
        for files in line["trailer"]["captured"].values():
            for rel, kept in files.items():
                if rel.endswith(".STL"):
                    del kept["file"]
        lines[index] = json.dumps(line)
    log.write_bytes(gzip.compress(("\n".join(lines) + "\n").encode("utf-8")))


def test_a_judge_fault_costs_its_signal_never_the_ground_truth(tmp_path, monkeypatch):
    base = _shaped(tmp_path / "a", monkeypatch)
    reordered = _shaped(tmp_path / "b", monkeypatch, _REORDERED)
    _corrupt_stl_record(reordered)
    diff = _diff(base, reordered, tmp_path / "diff.json")
    assert diff["request_divergence"]["member_expected"] == "IFace2.Select"
    assert diff["truth_cause"] == "response:IFace2.Normal"
    assert diff["outcome"] == "unknown"
    assert diff["outcome_signals"] == {**_ALL_SAME, "stl": "absent"}
    assert diff["outcome_details"]["stl"]["error"] == "KeyError: 'file'"

    # Any fault of the judgement: unknown, recorded, the divergence kept.
    def fault(*args: Any) -> Any:
        raise RuntimeError("injected\njudge fault")

    monkeypatch.setattr(_com_outcome, "_mass_signal", fault)
    diff = _diff(base, reordered, tmp_path / "mass.json")
    assert diff["outcome_signals"]["mass"] == "absent"
    assert diff["outcome_details"]["mass"] == {
        "error": "RuntimeError: injected judge fault"
    }
    monkeypatch.setattr(_com_outcome, "outcome", fault)
    monkeypatch.setattr(_com_outcome, "truth_cause", fault)
    diff = _diff(base, reordered, tmp_path / "all.json")
    assert diff["request_divergence"]["member_expected"] == "IFace2.Select"
    assert diff["truth_cause"] == "error:RuntimeError"
    assert diff["outcome"] == "unknown"
    assert set(diff["outcome_signals"].values()) == {"absent"}
    assert diff["outcome_details"]["truth_cause"]["error"].startswith("RuntimeError")


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

    modules = (
        "_com_conversation.py",
        "_com_outcome.py",
        "com_replay.py",
        "_replay_shadow.py",
    )
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
    # _replay_shadow, and only the driver (and its _com_outcome) the engine.
    names = {"_com_conversation", "_com_outcome", "com_replay", "_replay_shadow"}

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
    driver_deps = {
        Path(dep).name for dep in _buildgraph.module_deps_of(SCRIPTS / "com_replay.py")
    }
    assert {"_com_conversation.py", "_com_outcome.py"} <= driver_deps

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
                "--seat-log",
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


def _failing_wrap(monkeypatch: pytest.MonkeyPatch) -> None:
    wrap = conv.Recorder.wrap
    failed: list[Any] = []

    def failing_once(self: Any, value: Any, origin: Any) -> Any:
        if not failed:
            failed.append(value)
            raise OSError("injected: the proxy could not be built")
        return wrap(self, value, origin)

    monkeypatch.setattr(conv.Recorder, "wrap", failing_once)


def _classes(faults: list[dict[str, str]]) -> list[tuple[str, str]]:
    return [(fault["where"], fault["recovery"]) for fault in faults]


def test_a_fault_before_the_result_is_in_hand_aborts_the_build_for_a_rerun(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(conv, "_FAULTS", [])
    adapter = FakeAdapter(FakeServer())
    app = adapter.swApp
    with pytest.raises(conv.RecordFault, match="Recorder.call"):
        with _window(tmp_path, adapter) as recorder:
            # The server's own failure is the build's: unchanged, no fault.
            with pytest.raises(pythoncom.com_error):
                app.Fail()
            assert conv.record_faults() == []
            _failing_wrap(monkeypatch)
            try:
                app.Add(1.0, 2.0)
            except Exception:  # noqa: BLE001 - a build's own fallback
                pytest.fail("an engine fault reached the build's except Exception")
    faults = conv.record_faults()
    assert _classes(faults) == [("Recorder.call", "rerun")]
    assert faults[0]["type"] == "OSError" and "injected" in faults[0]["traceback"]
    assert conv.rerun_required() and recorder.trailer["status"] == "faulted"
    assert type(adapter.swApp._oleobj_) is FakeDispatch  # teardown is unrecorded


def test_a_swallowed_rerun_fault_stays_sticky_and_recording_stops(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(conv, "_FAULTS", [])
    adapter = FakeAdapter(FakeServer())
    app = adapter.swApp
    with _window(tmp_path, adapter) as recorder:
        _failing_wrap(monkeypatch)
        try:
            app.Add(1.0, 2.0)
        except BaseException:  # noqa: BLE001 - a build that swallows everything
            pass
        # Pass-through from here on: real answers, nothing logged.
        assert recorder.closed
        assert app.Add(2.0, 3.0) == 5.0
    assert _classes(conv.record_faults()) == [("Recorder.call", "rerun")]
    assert conv.rerun_required()


@pytest.mark.parametrize("site", ["log", "capture"])
def test_a_fault_once_the_result_is_in_hand_degrades_and_the_build_carries_on(
    tmp_path, monkeypatch, site
):
    monkeypatch.setattr(conv, "_FAULTS", [])
    adapter = FakeAdapter(FakeServer())
    app = adapter.swApp
    saved = tmp_path / "out" / "sldprt" / "x.SLDPRT"
    with _window(tmp_path, adapter) as recorder:
        if site == "log":
            _failing_emit(monkeypatch)
            assert app.Add(1.0, 2.0) == 3.0  # the real result, never an error
        else:

            def capture(self: Any, seq: int, watch: Any) -> None:
                raise FileNotFoundError(2, "injected: No such file or directory")

            monkeypatch.setattr(conv.Recorder, "_capture", capture)
            assert app.SaveTo(str(saved)) is True and saved.is_file()
        assert recorder.closed
        assert app.Add(2.0, 3.0) == 5.0  # pass-through from here on
    assert _classes(conv.record_faults()) == [(f"Recorder.{site}", "degraded")]
    assert not conv.rerun_required()
    assert recorder.trailer["status"] == "degraded"
    assert recorder.trailer["faults"] == [
        {"where": f"Recorder.{site}", "recovery": "degraded"}
    ]


def test_a_fault_closing_the_window_degrades_and_never_raises(tmp_path, monkeypatch):
    monkeypatch.setattr(conv, "_FAULTS", [])
    adapter = FakeAdapter(FakeServer())

    def close(self: Any, trailer: Any) -> None:
        raise OSError("injected: the trailer could not be written")

    monkeypatch.setattr(conv.LogWriter, "close", close)
    with _window(tmp_path, adapter):
        assert adapter.swApp.Add(1.0, 2.0) == 3.0
    assert _classes(conv.record_faults()) == [("recording.close", "degraded")]
    assert type(adapter.swApp._oleobj_) is FakeDispatch  # restored all the same


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
    assert _classes(conv.record_faults()) == [("audit", "degraded")]

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


# The drivers' fake seat. ``_session.run_build`` with the fake application in
# place of SolidWorks: connect, build, exit code (a failure is exit 1).
def fake_run_build(build: Any) -> int:
    adapter = FakeAdapter(FakeServer())
    try:
        asyncio.run(build(adapter))
    except Exception:  # noqa: BLE001 - run_build's contract
        return 1
    return 0


_PYWIN32_GOOD_SINGLE = win32com.client._get_good_single_object_


def pywin32_as_for_a_real_seat() -> None:
    """Unrecorded runs: pywin32 wraps a FakeDispatch as it wraps a real
    PyIDispatch (its ``isinstance(PyIDispatchType)`` test cannot see a duck
    type; a recording's funnel does the same for its proxies)."""

    def good_single(obj: Any, obUserName: Any = None, resultCLSID: Any = None) -> Any:  # noqa: N803
        if isinstance(obj, FakeDispatch):
            return Dispatch(obj, obUserName, resultCLSID)
        return _PYWIN32_GOOD_SINGLE(obj, obUserName, resultCLSID)

    win32com.client._get_good_single_object_ = good_single


def inject_record_fault(site: str) -> None:
    """Driver runs: make the recorder's own code fail at one site."""
    if site == "log":  # degraded: the fourth call's log line
        emit = conv.LogWriter.emit

        def failing_emit(self: Any, call: Any) -> None:
            if call.seq == 3:
                raise OSError("injected: the log volume is full")
            emit(self, call)

        conv.LogWriter.emit = failing_emit
    elif site == "capture":  # degraded: keeping SaveTo's file (MAX_PATH)

        def failing_capture(self: Any, seq: int, watch: Any) -> None:
            raise FileNotFoundError(2, "injected: No such file or directory")

        conv.Recorder._capture = failing_capture
    elif site == "wrap":  # rerun: the proxy of a returned interface
        wrap = conv.Recorder.wrap

        def failing_wrap(self: Any, value: Any, origin: Any) -> Any:
            if conv.is_interface(value):
                raise OSError("injected: the proxy could not be built")
            return wrap(self, value, origin)

        conv.Recorder.wrap = failing_wrap


# A part build's driver run on the fake seat: the real CLI, recorder and
# exit-code mapping. COM_REPLAY_TEST_FAULT names an inject_record_fault site.
_RECORD_DRIVER = """
import os, sys
import _session
import test_com_conversation as fixture
_session.run_build = fixture.fake_run_build
fixture.inject_record_fault(os.environ.get("COM_REPLAY_TEST_FAULT", ""))
import com_replay
sys.exit(com_replay.main(sys.argv[1:]))
"""
# The same build unrecorded (``python <script>`` on the fake seat, outputs
# redirected like the record driver's --out-root): argv = script, out root.
_UNRECORDED_DRIVER = """
import sys
from pathlib import Path
import _session
import _com_conversation as conv
import test_com_conversation as fixture
fixture.pywin32_as_for_a_real_seat()
_session.run_build = fixture.fake_run_build
conv.redirect_outputs(Path(sys.argv[2]))
sys.exit(conv.run_script(Path(sys.argv[1])))
"""


def test_cli_record_exits_with_the_build_unless_a_fault_requires_a_rerun(tmp_path):
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
    # test, which records, publishes and replays it. All runs at once.
    cases = {
        "script": {"COM_REPLAY_TEST_SCRIPT_FAILS": "1"},
        "log": {"COM_REPLAY_TEST_FAULT": "log"},
        "capture": {"COM_REPLAY_TEST_FAULT": "capture"},
        "wrap": {"COM_REPLAY_TEST_FAULT": "wrap"},
        "unrecorded": {},
    }
    procs = {}
    for case, variables in cases.items():
        env = dict(os.environ, OTEL_EXPORTER_OTLP_ENDPOINT="", **variables)
        (tmp_path / case).mkdir()
        command = (
            [_UNRECORDED_DRIVER, str(script), str(tmp_path / case / "out")]
            if case == "unrecorded"
            else [
                _RECORD_DRIVER,
                "record",
                str(script),
                "--log",
                str(tmp_path / case / "L.jsonl.gz"),
                "--summary",
                str(tmp_path / case / "summary.json"),
                "--out-root",
                str(tmp_path / case / "out"),
            ]
        )
        with (tmp_path / case / "driver.log").open("w", encoding="utf-8") as output:
            procs[case] = subprocess.Popen(
                [sys.executable, "-c", *command],
                cwd=SCRIPTS,
                env=env,
                stdout=output,
                stderr=subprocess.STDOUT,
            )
    runs = {}
    for case, proc in procs.items():
        rc = proc.wait(timeout=120)
        output = (tmp_path / case / "driver.log").read_text("utf-8", errors="replace")
        summary = tmp_path / case / "summary.json"
        assert case == "unrecorded" or summary.is_file(), output
        runs[case] = (
            rc,
            json.loads(summary.read_text("utf-8")) if summary.is_file() else None,
            conv._tree_files(tmp_path / case / "out"),
            output,
        )
    rc, _, unrecorded, output = runs["unrecorded"]
    assert rc == 0 and set(unrecorded) == {"py-output.json", "sldprt/fake.SLDPRT"}, (
        output
    )
    # The script's own failure is its exit code, exactly as unrecorded, and
    # the recording of it is complete.
    rc, script_failed, _, _ = runs["script"]
    assert rc == 1 and script_failed["exit_code"] == 1
    assert script_failed["faults"] == [] and script_failed["complete"]
    # A fault after the call's result was in hand: recording stops, the build
    # finishes on its real results (outputs byte-identical to the unrecorded
    # build, exit 0), and the recording is unusable.
    for site in ("log", "capture"):
        rc, degraded, outputs, output = runs[site]
        assert rc == 0 == degraded["exit_code"], output
        assert outputs == unrecorded, output
        assert not degraded["complete"]
        [fault] = degraded["faults"]
        assert (fault["where"], fault["recovery"]) == (f"Recorder.{site}", "degraded")
        assert "nothing of it is published" in output
        trailer = conv.load(tmp_path / site / "L.jsonl.gz").trailer
        assert trailer["status"] == "degraded"
    # A fault where the build's result cannot be guaranteed: the dedicated
    # exit code, for dodo to re-run the build unrecorded.
    rc, rerun, _, output = runs["wrap"]
    assert rc == conv.EXIT_RECORD_FAULT == rerun["exit_code"], output
    assert not rerun["complete"]
    [fault] = rerun["faults"]
    assert (fault["where"], fault["recovery"], fault["type"]) == (
        "Recorder.call",
        "rerun",
        "OSError",
    )
    assert conv.load(tmp_path / "wrap" / "L.jsonl.gz").trailer["status"] == "faulted"


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
