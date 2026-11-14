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
import hashlib
import importlib.util
import itertools
import json
import math
import os
import socket
import subprocess
import struct
import sys
import time
import types
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
    # The log names the recording's script; the replay runs this one. The
    # driver counts every parse of a log.
    counting = (
        "import sys\n"
        f"sys.path.insert(0, {str(SCRIPTS)!r})\n"
        "import _com_conversation as conv\n"
        "load = conv.load\n"
        "def counted(path):\n"
        "    sys.stderr.write(f'parsed {path}\\n')\n"
        "    return load(path)\n"
        "conv.load = counted\n"
        "import com_replay\n"
        "sys.exit(com_replay.main(sys.argv[1:]))\n"
    )
    results = {}
    parsed = {}
    # Writes outside scratch anywhere else: test_a_replay_refuses_writes_outside_its_roots.
    escapes = ("", "dispatch", "write", "network")
    for escape in escapes:
        env = dict(os.environ, OTEL_SERVICE_NAME="part-replay")
        env["COM_REPLAY_TEST_ESCAPE"] = escape
        result = tmp_path / f"result-{escape or 'clean'}.json"
        proc = subprocess.run(
            [
                sys.executable,
                "-c",
                counting,
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
        parsed[escape] = [
            line for line in proc.stderr.splitlines() if line.startswith("parsed ")
        ]
    rc, clean = results[""]
    assert rc == 0 and clean["verdict"] == "noop", clean
    # One parse of the base log serves the replay and the fields read after it.
    assert parsed[""] == [f"parsed {log.resolve()}"]
    assert clean["solidworks_inputs"] == [] and clean["title_echoes"]["count"] == 0
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
        return {k: diff[k] for k in ("outcome", "outcome_signals", "judge_faults")}

    # A signal neither log holds is absent, and no fault of the judge.
    assert outcome("unmeasured", measure=False) == {
        "outcome": "unknown",
        "outcome_signals": {**_ALL_SAME, "mass": "absent"},
        "judge_faults": [],
    }
    assert outcome("unexported", export=False) == {
        "outcome": "unknown",
        "outcome_signals": {**_ALL_SAME, "stl": "absent"},
        "judge_faults": [],
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


# dt_crank_drive_gear's audit, 2026-11-12: one planar face's closest point to
# one query point, on an edge of the face, in two builds of the same part.
_QUERY = (0.03469681472658223, 0.0011400111338435352, 0.0049854)
_CLOSEST = (
    0.03440920666204291,
    0.0017941457814243432,
    1.3010426069826053e-18,
    0.03440920666204291,
    0.0017941457814243432,
)
_NOISY = (
    0.03440920659643762,
    0.0017941457525791945,
    0.0,
    0.03440920659643762,
    0.0017941457525791945,
)


def _closest(handle: int, *point: float, query=_QUERY) -> conv.Call:
    return conv.Call(
        0,
        handle,
        "InvokeTypes",
        [{"f": v.hex()} for v in query],
        "IFace2.GetClosestPointOn",
        result={"t": [{"f": v.hex()} for v in point]},
    )


def _answers(
    a: list[conv.Call], b: list[conv.Call], kind: str = "part"
) -> tuple[str, Any]:
    keyed_a, keyed_b = _com_outcome._keyed_calls(a), _com_outcome._keyed_calls(b)
    signal, detail = _com_outcome._answers_signal(keyed_a, keyed_b, a, b, kind)
    return signal.value, detail


def test_answers_to_one_request_within_float_noise_are_one_answer():
    noise = "1 answers within 33554432 ulps of the other build's"
    # 6.6e-11 m apart (9.5e6 ulps): beyond REL_TOL, so the aligned rule calls
    # them different, but one answer to the answers signal. Handles are erased.
    base, noisy = _closest(4, *_CLOSEST), _closest(9, *_NOISY)
    assert not _com_outcome._close(base.result, noisy.result)
    assert _answers([_closest(4, *_CLOSEST)], [_closest(9, *_NOISY)]) == (
        "same",
        {"IFace2.GetClosestPointOn": noise},
    )
    assert _answers([_closest(4, *_CLOSEST)], [_closest(9, *_CLOSEST)]) == (
        "same",
        None,
    )
    # Paired by assignment within one request, in any order.
    other = (0.0335, *_CLOSEST[1:])
    assert _answers(
        [_closest(4, *_CLOSEST), _closest(4, *other)],
        [_closest(9, *other), _closest(9, *_NOISY)],
    ) == ("same", {"IFace2.GetClosestPointOn": noise})
    # Just past the bound, or noise-close to another request's answer only,
    # or once more in one build: different.
    scale = _CLOSEST[0]
    past = (scale + 1.01 * 2**25 * math.ulp(scale), *_CLOSEST[1:])
    elsewhere = (0.03, *_QUERY[1:])
    for new in (
        [_closest(9, *past)],
        [_closest(9, *_NOISY, query=elsewhere)],
        [_closest(9, *_NOISY), _closest(9, *_NOISY)],
    ):
        signal, detail = _answers([_closest(4, *_CLOSEST)], new)
        assert signal == "different" and "IFace2.GetClosestPointOn" in detail
    # Only floats are noise: another string or structure is another answer.
    named = conv.Call(0, 4, "InvokeTypes", [], "IBody2.Name", result="Boss1")
    renamed = conv.Call(0, 4, "InvokeTypes", [], "IBody2.Name", result="Boss2")
    assert _answers([named], [renamed])[0] == "different"
    assert _answers([_closest(4, *_CLOSEST)], [_closest(4, *_CLOSEST[:3])])[0] == (
        "different"
    )


def _cylinder(*values: str) -> conv.Call:
    """``ISurface.CylinderParams`` answering ``values`` (float hex)."""
    return conv.Call(
        0,
        315,
        "InvokeTypes",
        [2, 0, 2, {"t": [12, 0]}, {"t": []}],
        "ISurface.CylinderParams",
        result={"t": [{"f": value} for value in values]},
    )


def test_subnormal_answers_are_no_measurement():
    # pn_vn_pen_set_screw (2026-11-12): CylinderParams of a face that is no
    # cylinder, on two workers. Only the high half of a module address in
    # the first double differs: 6.95e-310 against 6.95e-310, 2.6e10 ulps.
    zero, junk = (0.0).hex(), "0x0.0000043e97a1cp-1022"
    base = ("0x0.07ff900000002p-1022", *[zero] * 5, junk)
    new = ("0x0.07fff00000002p-1022", *[zero] * 5, junk)
    radius = (0.0037729).hex()
    real = (zero, (0.00635).hex(), zero, zero, (-1.0).hex(), zero, radius)
    assert _answers(
        [_cylinder(*base), _cylinder(*real)], [_cylinder(*new), _cylinder(*real)]
    ) == (
        "same",
        {
            "ISurface.CylinderParams": "1 answers within 33554432 ulps of the other build's"
        },
    )
    # A normal float that differs in the same answer still differs.
    axis = (*new[:4], (-1.0).hex(), *new[5:])
    flipped = (*base[:4], (1.0).hex(), *base[5:])
    assert _answers([_cylinder(*axis)], [_cylinder(*flipped)])[0] == "different"
    # An answer of zeros is not one with a normal float where it has zero.
    zeros = (zero,) * 7
    assert _answers([_cylinder(*zeros)], [_cylinder(*zeros[:6], radius)])[0] == (
        "different"
    )


def test_answers_pairing_works_only_on_the_answers_that_differ(monkeypatch):
    # One request (a face's area) answered 50,000 times, faces listed in
    # another order, five answers moved by float noise beyond REL_TOL: the
    # exact answers cancel and only those five are paired.
    def area(handle: int, value: float) -> conv.Call:
        return conv.Call(
            0,
            handle,
            "InvokeTypes",
            [],
            "IFace2.GetArea",
            result={"t": [{"f": value.hex()}, {"f": (1.0).hex()}]},
        )

    areas = [i * 1e-5 for i in range(50_000)]
    noisy = {7, 4_321, 20_000, 33_333, 49_999}
    base = [area(i, v) for i, v in enumerate(areas)]
    new = [area(i, v + 3e-9 if i in noisy else v) for i, v in enumerate(areas)][::-1]
    compared = 0
    close = _com_outcome._answer_close

    def counted(a: Any, b: Any) -> bool:
        nonlocal compared
        compared += 1
        return close(a, b)

    monkeypatch.setattr(_com_outcome, "_answer_close", counted)
    assert _answers(base, new) == (
        "same",
        {"IFace2.GetArea": "5 answers within 33554432 ulps of the other build's"},
    )
    assert compared <= len(noisy) ** 2 + len(noisy)
    # One of them past the bound: different, with the same bounded work.
    compared = 0
    new[0] = area(0, areas[-1] + 1e-8)
    assert _answers(base, new)[0] == "different"
    assert compared <= len(noisy) ** 2 + len(noisy)


def _echoing(title: str, equation: str = "DivisionSpacing", handle: int = 4):
    """ms_stick's shape (2026-11-12): the document's title and a dimension's
    full name, both carrying the seat's document counter, then that full name
    written into an equation."""
    name = f"D3@MinorPattern@{title}.Part"
    return [
        conv.Call(0, 1, "InvokeTypes", [], "IModelDoc2.GetTitle", result=title),
        conv.Call(1, 2, "InvokeTypes", [], "IDimension.FullName", result=name),
        conv.Call(2, 3, "InvokeTypes", ["Count"], "IApp.Get", result=0),
        conv.Call(
            3,
            handle,
            "InvokeTypes",
            [-1, f'"{name}" = "{equation}"', True],
            "IEquationMgr.Add2",
            result=0,
        ),
    ]


def test_a_request_echoing_a_title_counter_is_caused_by_the_seat():
    cause = _com_outcome.truth_cause
    at = {"index": 3, "field": "args"}
    base = _echoing("Part13")
    assert cause(base, _echoing("Part24"), at) == _com_outcome.TITLE_COUNTER_CAUSE
    # Anything else in the request differing is the script's own.
    assert cause(base, _echoing("Part24", "ScaleEndMargin"), at) == "request"
    assert cause(base, _echoing("Part24", handle=5), at) == "request"
    # A counter the script made up, with every answer the same.
    made_up = [*base[:3], _echoing("Part14")[3]]
    assert cause(base, made_up, at) == "request"
    # An earlier answer beyond noise is still named first.
    counted = [
        *_echoing("Part24")[:2],
        conv.Call(2, 3, "InvokeTypes", ["Count"], "IApp.Get", result=1),
        _echoing("Part24")[3],
    ]
    assert cause(base, counted, at) == "response:IApp.Get"
    # A missing request is no echo.
    assert cause(base, base[:3], {"index": 3, "field": "length"}) == "request"
    assert _com_outcome.carries_title_counter([{"t": ["D1@Sketch1@Assem3.Assembly"]}])
    assert not _com_outcome.carries_title_counter(["Partial11", 11, {"f": "0x1p0"}])


def _answered(site: str, result: Any, args: list[Any] | None = None) -> conv.Call:
    return conv.Call(0, 3, "InvokeTypes", args or [], site, result=result)


def test_a_dependents_cause_is_its_earliest_answer_beyond_handle_numbers():
    cause = _com_outcome.truth_cause
    at = {"index": 3, "field": "args"}
    added = _answered("IEquationMgr.Add2", 0, ["D1 = 2"])
    base = [
        _answered("early_bound", {"h": 20, "p": "PyIDispatch"}),
        _answered("IComponent2.GetPathName", "C:/parts/a.SLDPRT"),
        _answered("IApp.Get", 1),
        added,
    ]
    new = [
        _answered("early_bound", {"h": 21, "p": "PyIDispatch"}),
        _answered("IComponent2.GetPathName", "C:/parts/b.SLDPRT"),
        _answered("IApp.Get", 2),
        dataclasses.replace(added, args=["D1 = 3"]),
    ]
    # A part names the nearest answer that differs; an assembly or drawing
    # the earliest, past a new object numbered apart (a renumbering).
    assert cause(base, new, at) == "response:IApp.Get"
    for kind in ("assembly", "drawing"):
        assert cause(base, new, at, kind) == "response:IComponent2.GetPathName"
    # A renumbering alone is still SolidWorks answering otherwise first.
    renumbered = [new[0], *base[1:3], new[3]]
    assert cause(base, renumbered, at) == "response:early_bound"
    assert cause(base, renumbered, at, "drawing") == "response:early_bound"
    # An object either build had numbered already is another object: named
    # first, whatever differs after it.
    known = [_answered("early_bound", {"h": h, "p": "PyIDispatch"}) for h in (20, 21)]
    picked = _answered(
        "ISelectionMgr.GetSelectedObject6", {"h": 20, "p": "PyIDispatch"}
    )
    other = dataclasses.replace(picked, result={"h": 21, "p": "PyIDispatch"})
    at = {"index": 4, "field": "args"}
    assert cause(
        [*known, picked, base[1], added], [*known, other, new[1], new[3]], at, "drawing"
    ) == ("response:ISelectionMgr.GetSelectedObject6")


def test_a_dependents_request_carrying_float_noise_is_the_noises():
    cause = _com_outcome.truth_cause
    at = {"index": 2, "field": "args"}
    x = 0.14036  # dt_cone_tip_gear's note, 2026-11-13
    noisy = math.nextafter(x, 1.0)

    def placed(read: float, put: float, site: str = "IAnnotation.SetPosition2"):
        return [
            _answered("IAnnotation.GetPosition", {"t": [_f(read), _f(0.2), _f(0.0)]}),
            _answered("IView.GetName2", "Drawing View1"),
            _answered(site, True, [_f(put), _f(0.2), _f(0.0)]),
        ]

    base = placed(x, x)
    # The answer 1 ulp apart, carried into the request: the noise's.
    assert cause(base, placed(noisy, noisy), at, "drawing") == (
        "response:IAnnotation.GetPosition"
    )
    # A part's request is its script's, whatever preceded it.
    assert cause(base, placed(noisy, noisy), at) == "request"
    # Arguments beyond noise, or noise no answer carried, are the script's.
    assert cause(base, placed(noisy, x + 0.012), at, "drawing") == "request"
    assert cause(base, placed(x, noisy), at, "drawing") == "request"
    # As is another member, however close its arguments.
    moved = placed(noisy, noisy, "IAnnotation.SetPosition")
    assert cause(base, moved, {"index": 2, "field": "member"}, "drawing") == "request"


def _sw(
    site: str, *values: Any, flags: int = 1, result: Any = True, on: int = 3
) -> conv.Call:
    """SolidWorks member ``site`` called (``flags`` 1), read (2) or put (4) on
    handle ``on`` (3: the part document)."""
    header = [1, 0, flags, {"t": [11, 0]}, {"t": []}]
    return conv.Call(0, on, "InvokeTypes", [*header, *values], site, result=result)


def _qi(on: int, interface: str, handle: int) -> conv.Call:
    return conv.Call(
        0, on, "QueryInterface", [interface], "early_bound", result={"h": handle}
    )


def _f(value: float) -> dict[str, str]:
    return {"f": value.hex()}


def _fallback(member: str = "GetEdges", interface: str = "IEdge") -> list[conv.Call]:
    """The vendored ``_select_entity_geometric`` (its ``_BODY_ENTITY_MEMBERS``):
    the part's type, its body's edges or faces, each one's closest point, and
    the nearest selected."""
    return [
        _sw("IModelDoc2.GetType", result=1),
        _qi(3, "IPartDoc", 9),
        _sw("IPartDoc.GetBodies2", 0, False, result={"t": [{"h": 10}]}, on=9),
        _sw(f"IBody2.{member}", result={"t": [{"h": 11}, {"h": 12}]}, on=10),
        _sw(
            f"{interface}.GetClosestPointOn",
            _f(0.05),
            result={"t": [_f(0.04)] * 5},
            on=11,
        ),
        _sw(
            f"{interface}.GetClosestPointOn",
            _f(0.05),
            result={"t": [_f(0.05)] * 5},
            on=12,
        ),
        _qi(12, "IEntity", 13),
        _sw("IEntity.Select2", False, 0, on=13),
    ]


_EDGE_FALLBACK = _fallback()
_MEASURED = [
    _sw("IModelDocExtension.CreateMeasure", result={"h": 14}, on=4),
    _sw("IMeasure.ArcOption", 0, flags=4, result=None, on=14),
    _sw("IMeasure.Calculate", None, on=14),
    _sw("IMeasure.Diameter", flags=2, result=_f(0.012), on=14),
]
_FILLETED = [
    _sw("IModelDoc2.ClearSelection2", True),
    _sw("IFeatureManager.FeatureFillet3", _f(0.001), result={"h": 15}, on=2),
]


def _picked(
    found: bool,
    fallback=_EDGE_FALLBACK,
    measured=_MEASURED,
    after=_FILLETED,
    steering: conv.Call | None = None,
):
    """mg_magnifying_wheel's shape (2026-11-12): an edge selected by a point
    (``SelectByID2`` through the part document's extension); when it answers
    False, the vendored geometric fallback selects the closest edge itself;
    then the edge measured, the selection cleared, and the next feature."""
    selection = _sw(
        "IModelDocExtension.SelectByID2", "", "EDGE", _f(0.05), result=found, on=4
    )
    return [
        _sw("IFeatureManager.FeatureExtrusion3", _f(0.004), result={"h": 20}, on=2),
        _sw("IModelDoc2.ClearSelection2", True),
        _sw("IModelDoc2.Extension", flags=2, result={"h": 4}),
        steering or selection,
        *([] if found else fallback),
        *measured,
        *after,
    ]


def _seat_path(a: list[conv.Call], b: list[conv.Call]) -> dict[str, Any]:
    keyed = (_com_outcome._keyed_calls(a), _com_outcome._keyed_calls(b))
    return _com_outcome.seat_path(a, b, keyed)


def test_a_detour_of_reads_and_selections_is_a_seat_path(monkeypatch):
    path = _seat_path
    base, detour = _picked(True), _picked(False)
    block = {
        "base": [4, 4],
        "new": [4, 4 + len(_EDGE_FALLBACK)],
        "steered_by": "IModelDocExtension.SelectByID2",
    }
    assert path(base, detour) == {"path": "detour", "count": 1, "blocks": [block]}
    # The detour in the base build: the same, the other way round.
    assert path(detour, base)["blocks"] == [
        {**block, "base": block["new"], "new": [4, 4]}
    ]
    # The same fallback for a face.
    faced = _picked(False, _fallback("GetFaces", "IFace2"))
    assert path(base, faced)["path"] == "detour"
    # A put, even to a listed member, or a member not listed, is no read: the
    # detour changed something.
    for changed in (
        _sw("IFeature.Name", "Edge1", flags=4, result=None),
        _sw("IModelDoc2.Extension", {"h": 4}, flags=4, result=None),
        _sw("IModelDoc2.EditRebuild3"),
    ):
        fallback = [*_EDGE_FALLBACK[:-1], changed, _EDGE_FALLBACK[-1]]
        found = path(base, _picked(False, fallback))
        assert found["path"] == "not_read" and changed.site in found["detail"]
    # The measure tool's own option, after the detour only.
    assert path(base, _picked(False, [*_EDGE_FALLBACK, _MEASURED[1]]))["path"] == (
        "not_read"
    )
    # Any other answer differing, beyond noise.
    wider = [*_MEASURED[:3], _sw("IMeasure.Diameter", flags=2, result=_f(0.013), on=14)]
    found = path(base, _picked(False, measured=wider))
    assert found["path"] == "answer" and "IMeasure.Diameter" in found["detail"]
    # A request replaced, not inserted: no detour.
    chamfered = [_FILLETED[0], _sw("IFeatureManager.InsertFeatureChamfer", _f(0.001))]
    assert path(base, _picked(False, after=chamfered))["path"] == "unaligned"
    # Beyond the bound: blocks too long, or too many.
    monkeypatch.setattr(_com_outcome, "_DETOUR_CALLS", len(_EDGE_FALLBACK) - 1)
    assert path(base, detour)["path"] == "unaligned"
    monkeypatch.setattr(_com_outcome, "_DETOUR_CALLS", len(_EDGE_FALLBACK))
    monkeypatch.setattr(_com_outcome, "_DETOUR_BLOCKS", 0)
    assert path(base, detour)["path"] == "unaligned"


def test_only_a_selection_answer_steers_a_detour():
    # A request that changes the document answered otherwise (a property
    # added in one build only), then reads: the document differs where mass
    # and STL do not look.
    def added(answer: int) -> conv.Call:
        return _sw("ICustomPropertyManager.Add3", "Mat", 30, "Steel", 1, result=answer)

    found = _seat_path(
        _picked(True, steering=added(0)), _picked(False, steering=added(1))
    )
    assert found == {
        "path": "answer",
        "detail": "ICustomPropertyManager.Add3 answered otherwise at base 3 new 3",
    }


def test_a_detour_must_clear_the_selection_on_the_document_it_selected_in():
    kept = "after the block at base 4 new 4"
    # Never cleared before the next feature.
    found = _seat_path(
        _picked(True, after=_FILLETED[1:]), _picked(False, after=_FILLETED[1:])
    )
    assert found == {
        "path": "selection_kept",
        "detail": "base: IFeatureManager.FeatureFillet3 before "
        f"IModelDoc2.ClearSelection2 on the document selected in, {kept}",
    }
    # Cleared on another document (handle 30): the part's selection stays.
    elsewhere = [_sw("IModelDoc2.ClearSelection2", True, on=30), _FILLETED[1]]
    found = _seat_path(_picked(True, after=elsewhere), _picked(False, after=elsewhere))
    assert found["path"] == "selection_kept" and found["detail"].startswith(
        "base: IFeatureManager.FeatureFillet3 before"
    )

    # The document a selection selects in cannot be established: SelectByID2
    # on an extension (31) no IModelDoc2.Extension answered.
    def unowned(found: bool) -> conv.Call:
        return _sw("IModelDocExtension.SelectByID2", "", "EDGE", result=found, on=31)

    found = _seat_path(
        _picked(True, steering=unowned(True)), _picked(False, steering=unowned(False))
    )
    assert found == {
        "path": "selection_kept",
        "detail": f"base: a selection's document is not established, {kept}",
    }


def test_a_seat_path_is_judged_only_for_the_same_geometry_after_a_response(
    monkeypatch,
):
    from types import SimpleNamespace

    signals = {"mass": "same", "requests": "different", "answers": "different"}

    def judged(stl: str, outcome: str = "different") -> dict[str, Any]:
        found = {
            "outcome": outcome,
            "outcome_signals": {**signals, "stl": stl},
            "outcome_details": {},
            "judge_faults": [],
        }
        monkeypatch.setattr(_com_outcome, "outcome", lambda *args: found)
        base, new = (
            SimpleNamespace(calls=_picked(True)),
            SimpleNamespace(calls=_picked(False)),
        )
        return _com_outcome.judge(base, new, {"index": 4}, Path(), Path())

    found = judged("same")
    assert found["truth_cause"] == "response:IModelDocExtension.SelectByID2"
    assert found["seat_path"]["path"] == "detour" and found["judge_faults"] == []
    assert judged("different")["seat_path"] is None
    assert judged("absent", outcome="unknown")["seat_path"] is None

    def raising(*args):
        raise ValueError("misaligned")

    monkeypatch.setattr(_com_outcome, "seat_path", raising)
    found = judged("same")
    assert found["seat_path"] == {"path": "error", "detail": "ValueError: misaligned"}
    assert found["judge_faults"] == [
        {"step": "seat_path", "error": "ValueError: misaligned"}
    ]


def test_a_replay_reports_the_requests_that_carry_a_title_counter():
    import types

    import com_replay

    inert = conv.Call(
        4, 1, "InvokeTypes", ["Part9"], "IApp.Note", origin=conv.Origin.INERT
    )
    echoes = com_replay._title_echoes(
        types.SimpleNamespace(calls=[*_echoing("Part24"), inert])
    )
    assert echoes == {"count": 1, "first": ["3 IEquationMgr.Add2"]}
    plain = [call for call in _echoing("Part24") if call.site != "IEquationMgr.Add2"]
    assert com_replay._title_echoes(types.SimpleNamespace(calls=plain)) == {
        "count": 0,
        "first": [],
    }


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
    assert diff["judge_faults"] == [{"step": "stl", "error": "KeyError: 'file'"}]

    # Any fault of the judgement: unknown, recorded, the divergence kept.
    def fault(*args: Any) -> Any:
        raise RuntimeError("injected\njudge fault")

    monkeypatch.setattr(_com_outcome, "_mass_signal", fault)
    diff = _diff(base, reordered, tmp_path / "mass.json")
    assert diff["outcome_signals"]["mass"] == "absent"
    assert diff["outcome_details"]["mass"] == {
        "error": "RuntimeError: injected judge fault"
    }
    assert [fault["step"] for fault in diff["judge_faults"]] == ["mass", "stl"]
    monkeypatch.setattr(_com_outcome, "outcome", fault)
    monkeypatch.setattr(_com_outcome, "truth_cause", fault)
    diff = _diff(base, reordered, tmp_path / "all.json")
    assert diff["request_divergence"]["member_expected"] == "IFace2.Select"
    assert diff["truth_cause"] == "error:RuntimeError"
    assert diff["outcome"] == "unknown"
    assert set(diff["outcome_signals"].values()) == {"absent"}
    assert diff["outcome_details"]["truth_cause"]["error"].startswith("RuntimeError")
    assert [fault["step"] for fault in diff["judge_faults"]] == [
        "truth_cause",
        "outcome",
    ]


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


# --------------------------------------------------------------------------- #
# Assemblies and drawings: a script's own argument, PDFs and sidecars
# --------------------------------------------------------------------------- #
def minimal_pdf(line_end: float, stamp: str) -> bytes:
    """A one-page vector PDF as SolidWorks exports a sheet: one text run and
    one black stroked line from (20, 20) to (``line_end``, 20) points;
    ``stamp`` is its Info dictionary's creation date (bytes, never ink)."""
    return _sheet_pdf(f"20 20 m {line_end:g} 20 l S", stamp)


def _sheet_pdf(paths: str, stamp: str = "D:1", text: str = "DRAWING") -> bytes:
    """A one-page 300 x 100 point vector PDF: the text run ``text`` and the
    black 1 pt strokes of the path operators ``paths``."""
    content = f"BT /F1 12 Tf 20 60 Td ({text}) Tj ET 0 0 0 RG 1 w {paths}".encode()
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 100] /Contents 4 0 R "
        b"/Resources << /Font << /F1 5 0 R >> >> >>",
        b"<< /Length %d >>\nstream\n" % len(content) + content + b"\nendstream",
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        b"<< /CreationDate (" + stamp.encode() + b") >>",
    ]
    data = bytearray(b"%PDF-1.4\n")
    offsets = []
    for number, body in enumerate(objects, start=1):
        offsets.append(len(data))
        data += b"%d 0 obj\n" % number + body + b"\nendobj\n"
    xref = len(data)
    data += b"xref\n0 %d\n0000000000 65535 f \n" % (len(objects) + 1)
    data += b"".join(b"%010d 00000 n \n" % offset for offset in offsets)
    data += b"trailer\n<< /Size %d /Root 1 0 R /Info 6 0 R >>\n" % (len(objects) + 1)
    data += b"startxref\n%d\n%%%%EOF\n" % xref
    return bytes(data)


class DrawingServer(FakeServer):
    """FakeServer whose SaveTo writes a real vector PDF to a ``.pdf`` path:
    its line as long as the application's Name says (a request), stamped
    with the export's time as SolidWorks stamps its date."""

    def invoke(self, target: FakeDispatch, dispid: int, flags: int, args: tuple) -> Any:
        if dispid != 7 or not str(args[0]).lower().endswith(".pdf"):
            return super().invoke(target, dispid, flags, args)
        self.calls += 1
        path = Path(args[0])
        path.parent.mkdir(parents=True, exist_ok=True)
        line_end = float(self.names.get("app", "100"))
        path.write_bytes(minimal_pdf(line_end, f"D:{time.time_ns()}"))
        return True


def fake_run_drawing(build: Any) -> int:
    """:func:`fake_run_build` on a :class:`DrawingServer`."""
    adapter = FakeAdapter(DrawingServer())
    try:
        asyncio.run(build(adapter))
    except Exception:  # noqa: BLE001 - run_build's contract
        return 1
    return 0


# The record driver of an assembly or drawing build on the fake seat: the real
# CLI, recorder and exit-code mapping, SaveTo writing real PDFs.
DEPENDENT_DRIVER = """
import sys
import _session
import test_com_conversation as fixture
_session.run_build = fixture.fake_run_drawing
import com_replay
sys.exit(com_replay.main(sys.argv[1:]))
"""
# A drawing script as dodo runs one: its artifact stem is its one argument. It
# opens the model it draws, reads that model's STL itself, sets the line from
# its own settings (a request) and saves the drawing and its PDF.
DRAWING_SCRIPT = (
    "import json, sys\n"
    "from pathlib import Path\n"
    "import _paths\n"
    "from _session import run_build\n"
    "import test_com_conversation  # noqa: F401 -- the fake seat's interfaces\n"
    "async def build(adapter):\n"
    "    stem, out = sys.argv[1], _paths.OUT_SLDPRT.parent\n"
    "    settings = json.loads((Path(__file__).parent / 'drawing.json').read_text())\n"
    "    app = adapter.swApp\n"
    "    if not app.Open(str(out / 'sldprt' / 'sh-widget.SLDPRT')):\n"
    "        raise RuntimeError('the model is missing')\n"
    "    (out / 'stl' / 'sh-widget.STL').read_bytes()\n"
    "    app.Name = str(settings['line'])\n"
    "    app.SaveTo(str(out / 'slddrw' / f'{stem}.SLDDRW'))\n"
    "    app.SaveTo(str(out / 'pdf' / f'{stem}.PDF'))\n"
    "    return {}\n"
    "if __name__ == '__main__':\n"
    "    if len(sys.argv) != 2:\n"
    "        sys.exit(2)\n"
    "    sys.exit(run_build(build))\n"
)


def drawing_outputs(out: Path) -> None:
    """The model a :data:`DRAWING_SCRIPT` build draws, under output root ``out``."""
    (out / "sldprt").mkdir(parents=True, exist_ok=True)
    (out / "sldprt" / "sh-widget.SLDPRT").write_bytes(b"the model")
    (out / "stl").mkdir(exist_ok=True)
    (out / "stl" / "sh-widget.STL").write_bytes(b"its STL")


def test_cli_record_keeps_a_scripts_argument_and_measures_what_replay_lacks(tmp_path):
    script = tmp_path / "draw_sh_widget.py"
    script.write_text(DRAWING_SCRIPT, encoding="utf-8")
    (tmp_path / "drawing.json").write_text('{"line": 100}', encoding="utf-8")
    procs = {}
    for case, argv in {"argument": ["--", "sh_widget"], "none": []}.items():
        drawing_outputs(tmp_path / case / "out")
        procs[case] = subprocess.Popen(
            [
                sys.executable,
                "-c",
                DEPENDENT_DRIVER,
                "record",
                str(script),
                "--log",
                str(tmp_path / case / "L.jsonl.gz"),
                "--summary",
                str(tmp_path / case / "summary.json"),
                "--out-root",
                str(tmp_path / case / "out"),
                *argv,
            ],
            cwd=SCRIPTS,
            env=dict(os.environ, OTEL_EXPORTER_OTLP_ENDPOINT=""),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
    runs = {}
    for case, proc in procs.items():
        output, _ = proc.communicate(timeout=120)
        summary = json.loads((tmp_path / case / "summary.json").read_text("utf-8"))
        runs[case] = (proc.returncode, summary, output)
    rc, summary, output = runs["argument"]
    assert rc == 0 and summary["complete"], output
    assert summary["argv"] == ["sh_widget"]
    gaps = summary["replay_gaps"]
    # The engine's replay passes no argument, redirects only sldprt/, sldasm/,
    # png/ and stl/, and stages none of the models a build opens.
    assert {name: gaps[name] for name in gaps if name != "python_out_reads"} == {
        "argv": 1,
        "out_paths": {
            "count": 3,
            "first": [
                "pdf/sh_widget.PDF",
                "slddrw/sh_widget.SLDDRW",
                "sldprt/sh-widget.SLDPRT",
            ],
        },
        "out_paths_unredirected": {
            "count": 2,
            "first": ["pdf/sh_widget.PDF", "slddrw/sh_widget.SLDDRW"],
        },
        "out_inputs": {"count": 1, "first": ["sldprt/sh-widget.SLDPRT"]},
        "out_inputs_unredirected": {"count": 0, "first": []},
    }
    assert "stl/sh-widget.STL" in gaps["python_out_reads"]["first"]
    # Without its argument the script refuses, exactly as unrecorded: the
    # argument reaches it only through the driver.
    rc, summary, output = runs["none"]
    assert rc == 2 == summary["exit_code"], output
    assert summary["argv"] == [] and summary["replay_gaps"]["argv"] == 0


def test_the_replays_redirected_outputs_are_the_engines(tmp_path, monkeypatch):
    import com_replay

    monkeypatch.delitem(sys.modules, "_part_save", raising=False)
    before = {name: v for name, v in vars(_paths).items() if isinstance(v, Path)}
    for name, value in before.items():
        monkeypatch.setattr(_paths, name, value)  # restored after the test
    conv.redirect_outputs(tmp_path)
    moved = {
        value.relative_to(tmp_path).as_posix()
        for name, value in vars(_paths).items()
        if isinstance(value, Path) and value != before.get(name)
    }
    assert moved == set(com_replay._REDIRECTED)


def _captured_pdfs(root: Path, *pdfs: tuple[str, bytes]) -> tuple[Any, Path]:
    """A conversation whose build had SolidWorks write ``pdfs`` (path, bytes)
    and the capture directory holding them."""
    root.mkdir()
    captured: dict[str, dict[str, Any]] = {}
    for index, (rel, data) in enumerate(pdfs):
        name = conv.capture_name(index)
        (root / name).write_bytes(gzip.compress(data))
        digest = hashlib.sha256(data).hexdigest()
        captured[str(index + 3)] = {
            rel: {"file": name, "sha256": digest, "size": len(data)}
        }
    return types.SimpleNamespace(trailer={"captured": captured}), root


def test_a_drawings_pdf_is_judged_on_its_ink_not_its_bytes(tmp_path):
    def signal(a: tuple[Any, Path], b: tuple[Any, Path]) -> tuple[str, Any]:
        found, detail = _com_outcome._pdf_signal(
            _com_outcome.pdf_inks(*a), _com_outcome.pdf_inks(*b)
        )
        return found.value, detail

    sheet = "pdf/sh_widget.PDF"
    base = _captured_pdfs(tmp_path / "base", (sheet, minimal_pdf(100.0, "D:1")))
    again = minimal_pdf(100.0, "D:2")
    assert again != minimal_pdf(100.0, "D:1")
    assert signal(base, _captured_pdfs(tmp_path / "again", (sheet, again))) == (
        "same",
        None,
    )
    longer = _captured_pdfs(tmp_path / "longer", (sheet, minimal_pdf(120.0, "D:1")))
    assert signal(base, longer) == (
        "different",
        {sheet: "page 1: 1 path pieces base only, 1 new only"},
    )
    other = _captured_pdfs(tmp_path / "other", ("pdf/other.PDF", again))
    assert signal(base, other) == (
        "different",
        {"pdf/other.PDF": "new only", sheet: "base only"},
    )
    broken = _captured_pdfs(tmp_path / "broken", (sheet, b"%PDF-1.4 no objects"))
    assert signal(base, broken) == ("different", {sheet: "bytes"})
    none = _captured_pdfs(tmp_path / "none")
    assert signal(none, none) == ("absent", None)


# A PDF point in sheet metres (_pdf_ink.POINT_M).
_PT = 0.0254 / 72.0


def _cropped(
    jagged: bool = True, box: tuple[float, ...] = (50, 10, 150, 90), moved=False
) -> list[conv.Call]:
    """dt_pinion_arbor's detail view (2026-11-13): cropped with a jagged
    outline, its sheet outline read (``box``, points), the flag read back;
    ``moved``: then positioned elsewhere."""
    outline = {"t": [_f(value * _PT) for value in box]}
    calls = [
        _sw("IView.Crop2", True, False, 3, result=1, on=85),
        _sw("IView.GetOutline", result=outline, on=85),
        _sw("IView.CropViewJaggedOutline", flags=2, result=jagged, on=85),
    ]
    if moved:
        calls.append(_sw("IView.SetViewPosition", {"t": [_f(0.1), _f(0.2)]}, on=85))
    return calls


def test_a_drawings_jagged_outline_drawn_again_is_its_own_cause(tmp_path, monkeypatch):
    # The outline's unchanged stretches, and two wiggles between their ends.
    neck = "60 20 m 100 20 l 100 40 l S 100 60 m 100 80 l 60 80 l S "
    wiggle = "100 40 m 103 45 l 98 50 l 102 55 l 100 60 l S "
    again = "100 40 m 97 44 l 103 52 l 100 60 l S "
    sheet = "pdf/dt-pinion-arbor.PDF"
    built = itertools.count()

    def drawn(paths: str, calls: list[conv.Call], text: str = "DRAWING"):
        pdf = _sheet_pdf(neck + paths, text=text)
        found, root = _captured_pdfs(tmp_path / str(next(built)), (sheet, pdf))
        found.calls = calls
        return found, root

    def jagged(a: tuple[Any, Path], b: tuple[Any, Path]) -> bool:
        inks = _com_outcome.pdf_inks(*a), _com_outcome.pdf_inks(*b)
        return _com_outcome.jagged_outline(a[0], b[0], *inks)

    view = _cropped()
    base = drawn(wiggle, view)
    read: list[bytes] = []
    ink = _com_outcome._pdf_ink
    monkeypatch.setattr(
        _com_outcome, "_pdf_ink", lambda data: read.append(data) or ink(data)
    )
    found = _com_outcome.judge(*_pair(base, drawn(again, view)), kind="drawing")
    assert found["outcome_signals"]["pdf"] == "different"
    assert found["pdf_cause"] == _com_outcome.JAGGED_OUTLINE_CAUSE
    assert found["judge_faults"] == []
    # Each build's PDF is read once, for the signal and the cause alike.
    assert len(read) == 2
    # Nothing else may differ: a line moved inside the view's box...
    line = drawn(wiggle + "120 30 m 130 30 l S ", view)
    assert not jagged(line, drawn(wiggle + "120 35 m 130 35 l S ", view))
    # ... or swung about an unchanged end, or a closed shape moved...
    swung = drawn(wiggle + "100 20 m 110 30 l S ", view)
    assert not jagged(swung, drawn(wiggle + "100 20 m 112 30 l S ", view))
    loop = drawn(wiggle + "120 30 m 130 30 l 125 35 l 120 30 l S ", view)
    shifted = "121 30 m 131 30 l 126 35 l 121 30 l S "
    assert not jagged(loop, drawn(wiggle + shifted, view))
    # ... or any text, however the outline wiggles.
    assert not jagged(base, drawn(again, view, text="DRAWN"))
    # The wiggle must lie in a view read back as jagged, where it was read.
    for other in (
        _cropped(jagged=False),
        _cropped(box=(110, 10, 150, 90)),
        _cropped(moved=True),
    ):
        assert not jagged(drawn(wiggle, other), drawn(again, other))
    # A part or an assembly has no PDF to explain.
    assert _com_outcome.judge(*_pair(base, drawn(again, view)))["pdf_cause"] is None


def _pair(a: tuple[Any, Path], b: tuple[Any, Path]) -> tuple[Any, ...]:
    """:func:`_com_outcome.judge`'s positional arguments for two drawn
    sheets, with no request divergence."""
    return a[0], b[0], None, a[1], b[1]


def test_a_dependents_closest_distance_is_judged_by_its_distance(tmp_path):
    def measured(witness: float, distance: float = 0.006882839) -> list[conv.Call]:
        """dt_drive_train's ClosestDistance between two parallel faces,
        2026-11-13: the distance, then a witness point on each face."""
        points = [{"t": [_f(0.01), _f(y), _f(0.0)]} for y in (witness, witness + 0.007)]
        faces = [{"h": 5, "p": "PyIDispatch"}, {"h": 6, "p": "PyIDispatch"}]
        result = {"t": [_f(distance), *points]}
        return [_sw("IModelDoc2.ClosestDistance", *faces, result=result)]

    def answers(a: list[conv.Call], b: list[conv.Call], kind: str) -> str:
        base = types.SimpleNamespace(calls=a, trailer={})
        new = types.SimpleNamespace(calls=b, trailer={})
        streams = _com_outcome._streams(base, new)
        found = _com_outcome.outcome(base, new, tmp_path, tmp_path, streams, kind)
        return found["outcome_signals"]["answers"]

    base = measured(0.0)
    for kind in ("assembly", "drawing"):
        assert answers(base, measured(0.01747), kind) == "same"
        assert answers(base, measured(0.0, 0.0069), kind) == "different"
    # A part's answers are compared whole.
    assert answers(base, measured(0.01747), "part") == "different"


_HEADER = types.SimpleNamespace(
    engine="e", sw_revision="r", environment={}, provenance_mask=[], adapter_state={}
)


def _assembled(
    names: tuple[str, ...],
    visit: tuple[str, ...] | None = None,
    mate: str = "arbor",
    named: str = "IComponent2.Name2",
    title: str | None = None,
    first: int = 10,
    on: int = 4,
) -> conv.Conversation:
    """An assembly script that reads every component's name, then visits the
    components in name order (the sort #2686 brings), 2026-11-13: the
    components SolidWorks enumerated as ``names`` (from handle ``first``, of
    the document ``on``), each wrapped by pywin32, early-bound and named
    (``named``), then each selected in ``visit`` order (sorted by default),
    then a mate on ``mate``; then, with ``title``, the document's title
    echoed into an equation (:func:`_echoing`). Handles are numbered in
    allocation order."""
    raw = list(range(first, first + len(names)))
    bound = [handle + len(names) for handle in raw]
    listed = {"t": [{"h": handle, "p": "PyIDispatch"} for handle in raw]}
    calls = [_sw("IAssemblyDoc.GetComponents", False, result=listed, on=on)]
    calls += [
        conv.Call(0, handle, "GetTypeInfo", [], "__WrapDispatch") for handle in raw
    ]
    for handle, early, name in zip(raw, bound, names, strict=True):
        calls += [
            _qi(handle, "IComponent2", early),
            _sw(named, flags=2, result=name, on=early),
        ]
    of = dict(zip(names, bound, strict=True))
    for name in sorted(names) if visit is None else visit:
        calls.append(_sw("IComponent2.Select4", False, on=of[name]))
    calls.append(
        _sw("IAssemblyDoc.AddMate5", {"h": of[mate], "p": "PyIDispatch"}, on=on)
    )
    if title is not None:
        calls += _echoing(title)
    return conv.Conversation(_HEADER, calls, {})


def test_a_dependents_components_are_compared_by_name_not_enumeration_order():
    def split(base: conv.Conversation, new: conv.Conversation) -> tuple[Any, int]:
        named, arrays = _com_outcome.name_bound(base, new)
        return conv.compare_conversations(base, named)["request_divergence"], arrays

    base = _assembled(("brace", "arbor", "collar"))
    permuted = _assembled(("collar", "brace", "arbor"))
    # By position, the sorted visit's first request is on another handle: the
    # seat numbered the same components in its own enumeration order.
    positional = conv.compare_conversations(base, permuted)["request_divergence"]
    assert positional["field"] == "handle"
    assert split(base, permuted) == (None, 1)
    # Read as if enumerated in the base's order: every answer the base's.
    named, _ = _com_outcome.name_bound(base, permuted)
    assert conv.compare_conversations(base, named)["response_differences"] == {}
    # A mate on another component still diverges...
    divergence, arrays = split(
        base, _assembled(("collar", "brace", "arbor"), mate="brace")
    )
    assert arrays == 1 and divergence["field"] == "args"
    assert divergence["member_expected"] == "IAssemblyDoc.AddMate5"
    # ... as does a visit in each seat's enumeration order.
    listed = _assembled(("brace", "arbor", "collar"), ("brace", "arbor", "collar"))
    visited = _assembled(("collar", "brace", "arbor"), ("collar", "brace", "arbor"))
    divergence, arrays = split(listed, visited)
    assert arrays == 1 and divergence["field"] == "handle"
    # Nothing binds without the same distinct names, or for another read.
    for other in (
        _assembled(("collar", "brace", "axle"), mate="brace"),
        _assembled(("collar", "brace", "arbor"), named="IComponent2.GetPathName"),
    ):
        assert split(_assembled(("brace", "arbor", "collar")), other)[1] == 0
    twice = _assembled(("arbor", "brace", "arbor"))
    assert split(twice, _assembled(("brace", "arbor", "arbor")))[1] == 0
    # A drawing view's components are visited by their own name.
    drawn = "IDrawingComponent.Name"
    listed = _assembled(("brace", "arbor", "collar"), named=drawn)
    assert split(listed, _assembled(("collar", "brace", "arbor"), named=drawn)) == (
        None,
        1,
    )


def test_a_dependents_later_arrays_bind_on_top_of_earlier_ones():
    def built(first: tuple[str, ...], second: tuple[str, ...]) -> conv.Conversation:
        # Two documents' components listed, then a mate on the first's collar.
        collar = {"h": 10 + len(first) + first.index("collar"), "p": "PyIDispatch"}
        calls = [
            *_assembled(first).calls,
            *_assembled(second, mate="pin", first=30, on=5).calls,
            _sw("IAssemblyDoc.AddMate5", collar, on=4),
        ]
        return conv.Conversation(_HEADER, calls, {})

    base = built(("brace", "arbor", "collar"), ("rod", "pin"))
    new = built(("collar", "brace", "arbor"), ("pin", "rod"))
    named, arrays = _com_outcome.name_bound(base, new)
    # The last mate is on the first document's collar, renamed by the first
    # binding though a second came between.
    assert arrays == 2
    assert conv.compare_conversations(base, named)["request_divergence"] is None


def test_only_a_dependents_diff_binds_components_by_name(tmp_path, monkeypatch):
    import com_replay

    logs = {
        "base": _assembled(("brace", "arbor", "collar")),
        "new": _assembled(("collar", "brace", "arbor")),
        "titled": _assembled(("brace", "arbor", "collar"), title="Part13"),
        "retitled": _assembled(("collar", "brace", "arbor"), title="Part24"),
    }
    monkeypatch.setattr(conv, "load", lambda path: logs[Path(path).name])

    def diff(kind: str, base: str = "base", new: str = "new"):
        result = tmp_path / f"{kind}.json"
        argv = ["diff", base, new, "--kind", kind, "--result", str(result)]
        rc = com_replay.main(argv)
        return rc, json.loads(result.read_text("utf-8"))

    rc, found = diff("assembly")
    assert rc == 0 and found["request_divergence"] is None
    assert found["name_bound"]["arrays"] == 1
    assert found["name_bound"]["positional_divergence"]["field"] == "handle"
    # Bound, a script that also echoes a title counter is still a title echo.
    rc, found = diff("assembly", "titled", "retitled")
    assert found["truth_cause"] == _com_outcome.TITLE_COUNTER_CAUSE
    assert found["title_echo"] is True and found["name_bound"]["arrays"] == 1
    rc, found = diff("part")
    assert rc == 91 and found["request_divergence"]["field"] == "handle"
    assert "name_bound" not in found

    def broken(*_args: Any) -> None:
        raise RuntimeError("injected")

    # A binding that raises is a judge fault; the comparison stays positional.
    monkeypatch.setattr(_com_outcome, "name_bound", broken)
    rc, found = diff("assembly")
    assert rc == 91 and found["request_divergence"]["field"] == "handle"
    assert found["judge_faults"][0] == {
        "step": "name_bound",
        "error": "RuntimeError: injected",
    }


def test_an_assemblys_sidecars_are_compared_byte_for_byte(tmp_path):
    proof, dof = ".sh-widget.massprops.sha", ".sh-widget.dof.json"

    def directory(name: str, **files: str) -> Path:
        root = tmp_path / name
        root.mkdir()
        for file, text in files.items():
            (root / file).write_text(text, encoding="utf-8")
        return root

    def signal(a: Path | None, b: Path | None) -> tuple[str, Any]:
        found, detail = _com_outcome._sidecar_signal(a, b)
        return found.value, detail

    base = directory("base", **{proof: "ab\n"})
    assert signal(base, directory("same", **{proof: "ab\n"})) == ("same", None)
    moved = directory("moved", **{proof: "cd\n"})
    assert signal(base, moved) == ("different", {proof: "bytes"})
    freed = directory("freed", **{proof: "ab\n", dof: "{}"})
    assert signal(base, freed) == ("different", {dof: "new only"})
    assert signal(None, tmp_path / "missing") == ("absent", None)


def test_each_kind_is_judged_on_its_own_signals(tmp_path, monkeypatch):
    empty = types.SimpleNamespace(calls=[], trailer={})
    assert _com_outcome.SIGNALS == {
        "part": ("mass", "requests", "answers", "stl"),
        "assembly": ("mass", "requests", "answers", "sidecars"),
        "drawing": ("requests", "answers", "pdf"),
    }
    streams = _com_outcome._streams(empty, empty)
    for kind, names in _com_outcome.SIGNALS.items():
        found = _com_outcome.outcome(empty, empty, tmp_path, tmp_path, streams, kind)
        assert tuple(found["outcome_signals"]) == names

    def broken(*_args: Any, **_kwargs: Any) -> None:
        raise RuntimeError("injected")

    monkeypatch.setattr(_com_outcome, "outcome", broken)
    judged = _com_outcome.judge(empty, empty, None, tmp_path, tmp_path, kind="drawing")
    assert judged["outcome_signals"] == dict.fromkeys(
        ("requests", "answers", "pdf"), "absent"
    )


def test_a_dependents_seat_path_needs_its_own_geometry(monkeypatch):
    assert _com_outcome.GEOMETRY == {
        "part": ("mass", "stl"),
        "assembly": ("mass", "sidecars"),
        "drawing": ("pdf",),
    }

    def judged(kind: str, **geometry: str) -> dict[str, Any]:
        found = {
            "outcome": "different",
            "outcome_signals": {
                "requests": "different",
                "answers": "different",
                **geometry,
            },
            "outcome_details": {},
            "judge_faults": [],
        }
        monkeypatch.setattr(_com_outcome, "outcome", lambda *args: found)
        base = types.SimpleNamespace(calls=_picked(True))
        new = types.SimpleNamespace(calls=_picked(False))
        return _com_outcome.judge(base, new, {"index": 4}, Path(), Path(), kind=kind)

    # The same vendored selection fallback steers assemblies and drawings, so
    # their detours are judged once their own geometry is the base's.
    assert judged("drawing", pdf="same")["seat_path"]["path"] == "detour"
    assert judged("drawing", pdf="different")["seat_path"] is None
    found = judged("assembly", mass="same", sidecars="same")
    assert found["seat_path"]["path"] == "detour"
    assert judged("assembly", mass="same", sidecars="different")["seat_path"] is None
    # A part's geometry is mass and STL: a sheet's ink is no evidence of it.
    assert judged("part", pdf="same")["seat_path"] is None


def test_a_stream_that_differs_only_by_echoed_titles_is_a_title_echo(monkeypatch):
    echo = _com_outcome.title_echo
    base = _echoing("Part13")
    assert echo(base, _echoing("Part24"))
    # Anything else differing is no echo: a request, a missing request...
    assert not echo(base, _echoing("Part24", "ScaleEndMargin"))
    assert not echo(base, _echoing("Part24", handle=5))
    assert not echo(base, _echoing("Part24")[:3])
    # ... or an answer beyond noise, however late after the echo.
    count = conv.Call(4, 3, "InvokeTypes", ["Count"], "IApp.Get", result=0)
    later = [*base, count]
    answered = [*_echoing("Part24"), dataclasses.replace(count, result=1)]
    assert echo(later, [*_echoing("Part24"), count]) and not echo(later, answered)

    def judged(a: list[conv.Call], b: list[conv.Call]) -> dict[str, Any]:
        return _com_outcome.judge(
            types.SimpleNamespace(calls=a, trailer={}),
            types.SimpleNamespace(calls=b, trailer={}),
            {"index": 3, "field": "args"},
            Path(),
            Path(),
            kind="drawing",
        )

    found = judged(base, _echoing("Part24"))
    assert found["truth_cause"] == _com_outcome.TITLE_COUNTER_CAUSE
    assert found["title_echo"] is True and found["judge_faults"] == []
    assert judged(later, answered)["title_echo"] is False
    # Judged only after an echo was the first difference.
    assert judged(base, _echoing("Part24", "ScaleEndMargin"))["title_echo"] is None

    def broken(*_args: Any) -> bool:
        raise RuntimeError("injected")

    monkeypatch.setattr(_com_outcome, "title_echo", broken)
    found = judged(base, _echoing("Part24"))
    assert found["title_echo"] is None
    assert found["judge_faults"] == [
        {"step": "title_echo", "error": "RuntimeError: injected"}
    ]


def _late_name(handle: int, name: str) -> list[conv.Call]:
    """A component's ``Name2`` read late-bound (``_read_member``), as pywin32
    logs it: a wrap, the name's dispid, the property read."""
    return [
        conv.Call(0, handle, "GetTypeInfo", [], "__WrapDispatch"),
        conv.Call(0, handle, "GetIDsOfNames", [0, "Name2"], "__AttrToID__", result=59),
        conv.Call(0, handle, "Invoke", [59, 0, 2, 1], "CDispatch.Name2", result=name),
    ]


def _handles_of(handles: list[int]) -> dict[str, Any]:
    return {"t": [{"h": handle, "p": "PyIDispatch"} for handle in handles]}


def _seat_listed(
    title: str,
    reports: tuple[tuple[str, str], ...] = (("rod-1", "pin-1"), ("rod-2", "pin-2")),
    listed: tuple[str, ...] = ("arbor", "brace", "collar"),
    *,
    names: tuple[str, ...] = ("brace", "arbor", "collar"),
    aim: str = "collar",
    pick: bool = False,
    asked: tuple[tuple[str, float], ...] = (),
    related: tuple[tuple[int, float], ...] = (),
    volumes: tuple[float, ...] = (),
    classify: str = "",
    dated: str = "IModelDoc2.SummaryInfo",
    date: str = "Friday, November 13, 2026 7:01:14 PM",
) -> conv.Conversation:
    """The first same-key pairs after #2730 (2026-11-14, ch_channel and
    dt_drive_train) reduced: the document's title echoed into a component
    selection (``aim@title``) before anything was enumerated; the components
    SolidWorks enumerated as ``names``, read by name and visited in name order
    (:func:`_assembled`); an interference report listing ``reports`` in the
    seat's order, each pair's names read late-bound (ch_channel's); a
    late-bound name set over the components in ``listed`` order (a component
    pattern's ``before`` set, dt_drive_train's), each element then asked the
    ``asked`` question at its position (a parameter read, its answer), then
    with ``pick`` the set's first element added to the selection; then a
    ``dated`` read answering ``date`` (by default the save date, a session
    read). With ``volumes``, each report's volume is read after its names;
    with ``classify``, each reported component's path is read and then its
    transform (``read``, pd_paper_drive's chain classification) or its
    suppression set (``act``). ``related`` asks the set's element at each
    position about the element at another (its distance from it)."""
    calls = [
        _sw("IModelDoc2.GetTitle", result=title),
        _sw("IModelDocExtension.SelectByID2", f"{aim}@{title}", "COMPONENT", on=5),
        *_assembled(names).calls,
    ]
    found = [40 + index for index in range(len(reports))]
    calls.append(
        _sw("IInterferenceDetectionMgr.GetInterferences", result=_handles_of(found))
    )
    transforms = itertools.count(100)
    for index, (report, pair) in enumerate(zip(found, reports, strict=True)):
        members = [60 + 2 * index, 61 + 2 * index]
        result = _handles_of(members)
        calls.append(_sw("IInterference.Components", flags=2, result=result, on=report))
        for member, name in zip(members, pair, strict=True):
            calls += _late_name(member, name)
            if classify:
                path = f"C:/parts/{name}.SLDPRT"
                calls.append(_sw("IComponent2.GetPathName", result=path, on=member))
            if classify == "read":
                transform = {"h": next(transforms), "p": "PyIDispatch"}
                calls.append(
                    _sw(
                        "IComponent2.GetTotalTransform",
                        False,
                        result=transform,
                        on=member,
                    )
                )
            if classify == "act":
                calls.append(_sw("IComponent2.SetSuppression2", 2, result=1, on=member))
        if volumes:
            volume = _f(volumes[index])
            calls.append(_sw("IInterference.Volume", flags=2, result=volume, on=report))
    members = [80 + index for index in range(len(listed))]
    calls.append(_sw("IAssemblyDoc.GetComponents", True, result=_handles_of(members)))
    for member, name in zip(members, listed, strict=True):
        calls += _late_name(member, name)
    for member, (question, value) in zip(members if asked else (), asked, strict=True):
        read = [61, 0, 2, 1, question]
        site = "CDispatch.Parameter"
        calls.append(conv.Call(0, member, "Invoke", read, site, result=_f(value)))
    for position, (other, value) in enumerate(related):
        about = [63, 0, 2, 1, {"h": members[other], "p": "PyIDispatch"}]
        distance = _f(value)
        on = members[position]
        calls.append(conv.Call(0, on, "Invoke", about, "CDispatch.Distance", distance))
    if pick:
        first = {"h": members[0], "p": "PyIDispatch"}
        calls.append(_sw("ISelectionMgr.AddSelectionListObject", first, None, on=7))
    calls.append(_sw(dated, 2, flags=2, result=date))
    return conv.Conversation(_HEADER, calls, {})


# Another seat's order for :func:`_seat_listed`: the interference report, the
# name set and the components listed otherwise.
_ANOTHER_SEAT: dict[str, Any] = {
    "reports": (("rod-2", "pin-2"), ("rod-1", "pin-1")),
    "listed": ("collar", "arbor", "brace"),
    "names": ("collar", "brace", "arbor"),
}


def _seat_diff(
    tmp_path: Path, monkeypatch: Any, base: conv.Conversation
) -> tuple[dict[str, conv.Conversation], Any]:
    """``com_replay.py diff`` of fixture logs: the logs it reads (``base``, and
    ``new`` per diff; either replaceable) and the diff of a new log."""
    import com_replay

    logs: dict[str, conv.Conversation] = {"base": base}
    monkeypatch.setattr(conv, "load", lambda path: logs[Path(path).name])

    def diff(new: conv.Conversation, kind: str = "assembly") -> dict[str, Any]:
        logs["new"] = new
        result = tmp_path / "diff.json"
        com_replay.main(
            ["diff", "base", "new", "--kind", kind, "--result", str(result)]
        )
        return json.loads(result.read_text("utf-8"))

    return logs, diff


def test_a_dependents_title_echo_tolerates_only_what_the_seat_reordered(
    tmp_path, monkeypatch
):
    base = _seat_listed("Assem3", date="Friday, November 13, 2026 6:49:23 PM")
    logs, diff = _seat_diff(tmp_path, monkeypatch, base)
    seat = _ANOTHER_SEAT

    # Another seat: another title counter, the components and the interference
    # report enumerated in another order, another save date. The echo comes
    # before every array, yet the arrays are bound by name, and the rest is
    # the seat's order: the same requests, a no-op.
    found = diff(_seat_listed("Assem6", **seat))
    assert found["truth_cause"] == _com_outcome.TITLE_COUNTER_CAUSE
    assert found["name_bound"]["arrays"] == 1 and found["title_echo"] is True
    # A part's answers stay compared whole, in order.
    assert diff(_seat_listed("Assem6", **seat), "part")["title_echo"] is False
    # The echoed selection on another component is the script's own request.
    found = diff(_seat_listed("Assem6", **seat, aim="brace"))
    assert found["truth_cause"] == "request" and found["title_echo"] is None
    # A read set with one name changed is no reordering...
    changed = {**seat, "listed": ("collar", "axle", "brace")}
    assert diff(_seat_listed("Assem6", **changed))["title_echo"] is False
    # ... nor is an interference report pairing other components.
    paired = {**seat, "reports": (("rod-2", "pin-1"), ("rod-1", "pin-2"))}
    assert diff(_seat_listed("Assem6", **paired))["title_echo"] is False
    # Nor is an answer moved to an element asked another question: asked by
    # position, each component was asked something else in the other order.
    asked = (("D1@Sketch1", 5.0), ("D2@Sketch1", 7.0), ("D3@Sketch1", 9.0))
    logs["base"] = _seat_listed("Assem3", asked=asked)
    moved = (("D1@Sketch1", 9.0), ("D2@Sketch1", 5.0), ("D3@Sketch1", 7.0))
    assert diff(_seat_listed("Assem6", **seat, asked=moved))["title_echo"] is False
    # The same question of every component, answered per component, is only
    # the seat's order.
    uniform = tuple(("D1@Sketch1", value) for _, value in asked)
    logs["base"] = _seat_listed("Assem3", asked=uniform)
    same = tuple(("D1@Sketch1", value) for _, value in moved)
    assert diff(_seat_listed("Assem6", **seat, asked=same))["title_echo"] is True
    # Selecting the set's first element selects another component once the
    # seat listed it in another order, by the very same request...
    logs["base"] = _seat_listed("Assem3", pick=True)
    assert diff(_seat_listed("Assem6", **seat, pick=True))["title_echo"] is False
    # ... and is no difference when the set came in the base's order.
    alike = {**seat, "listed": ("arbor", "brace", "collar")}
    assert diff(_seat_listed("Assem6", **alike, pick=True))["title_echo"] is True
    # Only a session read may answer anything else: another property value is
    # the model's, however the components were enumerated.
    logs["base"] = _seat_listed("Assem3", dated="IModelDoc2.GetCustomInfoValue")
    custom = _seat_listed(
        "Assem6", **seat, dated="IModelDoc2.GetCustomInfoValue", date="BRASS"
    )
    assert diff(custom)["title_echo"] is False


def test_a_dependents_title_echo_reads_component_paths_and_transforms(
    tmp_path, monkeypatch
):
    base = _seat_listed("Assem3", classify="read")
    logs, diff = _seat_diff(tmp_path, monkeypatch, base)
    # pd_paper_drive (2026-11-14): its chain classification asks each
    # interfering component its path and transform, methods that only read.
    found = diff(_seat_listed("Assem6", **_ANOTHER_SEAT, classify="read"))
    assert found["title_echo"] is True
    # Any other method on those components acts on them: no echo.
    logs["base"] = _seat_listed("Assem3", classify="act")
    found = diff(_seat_listed("Assem6", **_ANOTHER_SEAT, classify="act"))
    assert found["title_echo"] is False


def test_a_dependents_interference_volumes_compare_within_the_modellers_tolerance(
    tmp_path, monkeypatch
):
    overlap = 12.285502183837625e-9
    base = _seat_listed("Assem3", volumes=(overlap, 3.0e-9))
    _, diff = _seat_diff(tmp_path, monkeypatch, base)

    def judged(*volumes: float, reports=_ANOTHER_SEAT["reports"]) -> tuple:
        seat = {**_ANOTHER_SEAT, "reports": reports}
        found = diff(_seat_listed("Assem6", **seat, volumes=volumes))
        return found["title_echo"], found["outcome_signals"]["answers"]

    # pd_paper_drive (2026-11-14): one overlap 5.2e-7 apart in builds of
    # identical geometry, the report in another order.
    assert judged(3.0e-9, 12.285495794652596e-9) == (True, "same")
    # 1e-4 apart is another overlap, and one that vanished another again.
    assert judged(3.0e-9, overlap * (1 + 1e-4)) == (False, "different")
    assert judged(0.0, overlap) == (False, "different")
    # So is an interference more, however small.
    more = (*_ANOTHER_SEAT["reports"], ("rod-3", "pin-3"))
    echo, answers = judged(3.0e-9, overlap, 1e-15, reports=more)
    assert echo is not True and answers == "different"


def test_a_dependents_relational_reads_name_the_element_they_ask_about(
    tmp_path, monkeypatch
):
    # #2761: the base lists arbor, brace, collar and asks each component
    # about the next one listed: arbor about brace, brace about collar.
    base = _seat_listed("Assem3", related=((1, 5.0), (2, 7.0)))
    logs, diff = _seat_diff(tmp_path, monkeypatch, base)
    seat = {**_ANOTHER_SEAT, "listed": ("brace", "arbor", "collar")}
    # Listed brace, arbor, collar, the same requests ask brace about arbor
    # and arbor about collar, though each component's answer is the base's.
    found = diff(_seat_listed("Assem6", **seat, related=((1, 7.0), (2, 5.0))))
    assert found["title_echo"] is False
    # Asked about itself, each component is asked the same in any order.
    logs["base"] = _seat_listed("Assem3", related=((0, 5.0), (1, 7.0), (2, 9.0)))
    itself = ((0, 7.0), (1, 5.0), (2, 9.0))
    assert diff(_seat_listed("Assem6", **seat, related=itself))["title_echo"] is True


def _display_probe(site: str, *values: Any, result: Any) -> conv.Call:
    """An inert IModelView read of ``_seat_forensics.display_geometry``, as
    the 2026-11-12 ms_stop_plate recording logged it."""
    header = [54, 0, 1, {"t": [24, 0]}, {"t": [{"t": [5, 1]}, {"t": [16389, 2]}]}]
    return conv.Call(
        0, -5, "InvokeTypes", [*header, *values], site, result, origin=conv.Origin.INERT
    )


def _projected(point: tuple[float, ...], x: str, y: str) -> conv.Call:
    return _display_probe(
        "IModelView.ProjectModelPoint",
        *map(_f, point),
        *[{"s": "Missing"}] * 3,
        result={"t": [{"f": x}, {"f": y}, _f(0.0)]},
    )


# ms_stop_plate's pass-1 answers: the origin's projection, and 1 mm along x.
_LEFT, _BOTTOM = "0x1.f414141414143p+7", "0x1.4be629edb1754p+9"
_X_AXIS = "0x1.f8ba7666bfeadp+7"


def _probes(box: list[Any], x_axis: str = _X_AXIS) -> list[conv.Call]:
    """One ``display_geometry`` probe: the window, then four projections."""
    return [
        _display_probe("IModelView.GetVisibleBox", result={"t": box}),
        _projected((0.0, 0.0, 0.0), _LEFT, _BOTTOM),
        _projected((1e-3, 0.0, 0.0), x_axis, _BOTTOM),
        _projected((0.0, 1e-3, 0.0), _LEFT, "0x1.4abc9159067f9p+9"),
        _projected((0.0, 0.0, 1e-3), _LEFT, _BOTTOM),
    ]


def test_the_seats_drawing_display_is_read_from_the_logs_own_answers():
    import com_replay

    def display(*calls: conv.Call) -> Any:
        return com_replay._display(types.SimpleNamespace(calls=list(calls)))

    # ms_stop_plate's pass 1 (its seat logged view_window=1010x678 px/mm=2.325).
    first = _probes([253, 36, 1263, 714])
    assert display(*first) == {"view_window": [1010, 678], "px_per_mm": 2.325}
    # The last probe is the display the build ended on.
    narrower = _probes([253, 36, 1263, 634])
    assert display(*first, *narrower)["view_window"] == [1010, 598]
    # An answer that cannot be read leaves its key out; no probe, no display.
    assert display(*_probes([253.0, 36, 1263, 714], _LEFT)) == {"px_per_mm": 2.325}
    assert display(*_echoing("Part24")) is None


def test_a_drawings_display_is_streamed_from_the_lines_the_engine_wrote(
    tmp_path, monkeypatch
):
    import com_replay

    recorded, _, _, _ = _record(tmp_path / "header", monkeypatch)
    log = tmp_path / "probed.jsonl.gz"
    calls = [*_echoing("Part24"), *_probes([253, 36, 1263, 714])]
    writer = conv.LogWriter(log)
    writer.header(conv.read_header(recorded))
    for seq, call in enumerate(calls):
        writer.emit(dataclasses.replace(call, seq=seq))
    writer.close({"status": "complete"})
    # The writer interned each probe's dispatch header; the stream never sees it.
    assert conv.load(log).calls[-1].args == calls[-1].args
    assert com_replay._logged_display(log) == com_replay._display(conv.load(log))
    assert com_replay._logged_display(log) == {
        "view_window": [1010, 678],
        "px_per_mm": 2.325,
    }
    assert com_replay._logged_display(recorded) is None


def test_only_a_drawings_recording_reads_its_display_on_the_seat(tmp_path, monkeypatch):
    import com_replay

    timing = {"rc": 0, "trailer": {"status": "complete", "calls": 2, "inert_calls": 0}}
    monkeypatch.setattr(conv, "record_build", lambda *_a, **_k: timing)
    monkeypatch.setattr(conv, "record_faults", lambda: [])
    monkeypatch.setattr(conv, "rerun_required", lambda: False)
    read: list[Path] = []

    def logged(log: Path) -> dict[str, Any]:
        read.append(log)
        return {"px_per_mm": 2.098}

    monkeypatch.setattr(com_replay, "_logged_display", logged)
    log = tmp_path / "L.jsonl.gz"

    def display(kind: str) -> Any:
        summary = tmp_path / f"{kind}.json"
        argv = ["record", "s.py", "--log", str(log), "--summary", str(summary)]
        assert com_replay.main([*argv, "--kind", kind]) == 0
        return json.loads(summary.read_text("utf-8"))["display"]

    # A part or an assembly never probes the display: its log is not re-read.
    assert display("part") is None and display("assembly") is None and read == []
    assert display("drawing") == {"px_per_mm": 2.098} and read == [log.resolve()]


def test_a_scripts_arguments_are_everything_after_the_first_double_dash():
    import com_replay

    parse = com_replay._arguments
    record = ["record", "draw_x.py", "--log", "L", "--summary", "S"]
    # dodo's two shapes (Recording.command): a part's, and a drawing's stem.
    assert parse([*record, "--kind", "part"]).argv == []
    drawing = parse([*record, "--kind", "drawing", "--", "sh_widget"])
    assert (drawing.script, drawing.kind, drawing.argv) == (
        Path("draw_x.py"),
        "drawing",
        ["sh_widget"],
    )
    # Options before it are the driver's; whatever follows, the script's.
    found = parse([*record, "--out-root", "O", "--", "--flag", "--", "x"])
    assert (found.out_root, found.argv) == (Path("O"), ["--flag", "--", "x"])
    # argparse never sees a script argument, so no patch release of it binds
    # one: a bare one is the driver's error, and only record passes any.
    with pytest.raises(SystemExit):
        parse([*record, "sh_widget"])
    assert parse(["diff", "a", "b", "--"]).argv == []
    with pytest.raises(SystemExit):
        parse(["diff", "a", "b", "--", "sh_widget"])


def test_a_diff_reports_each_logs_own_display(tmp_path, monkeypatch):
    import com_replay

    base = _shaped(tmp_path / "a", monkeypatch)
    new = _shaped(tmp_path / "b", monkeypatch, _REORDERED)
    # A shaped part probes no display.
    assert _diff(base, new, tmp_path / "none.json")["display"] == {
        "base": None,
        "new": None,
    }
    counted = {"base": {"calls": len(conv.load(base).calls)}}
    counted["new"] = {"calls": len(conv.load(new).calls)}
    monkeypatch.setattr(com_replay, "_display", lambda log: {"calls": len(log.calls)})
    assert _diff(base, new, tmp_path / "counted.json")["display"] == counted

    def broken(_log: Any) -> None:
        raise ValueError("injected")

    # A display that cannot be read costs the display, never the diff.
    monkeypatch.setattr(com_replay, "_display", broken)
    diff = _diff(base, new, tmp_path / "broken.json")
    assert diff["display"] == {"error": "ValueError: injected"}
    assert diff["truth_cause"] == "response:IFace2.Normal"
