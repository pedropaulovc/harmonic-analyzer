"""Focused offline smoke harness for the actual disposable driver and runner.

Intended destination: cad/scripts/test_mg_saved_thread_control_offline.py.
Run once by the integration owner, not the payload author. Uses actual module
code with fake collaborators; no copied function bodies or source-string tests.
All driver writes are confined to TemporaryDirectory. Native/provider imports,
child processes, host kills, and os._exit are refused before modules are loaded.
"""

from __future__ import annotations

import argparse
import asyncio
import copy
from contextlib import ExitStack, contextmanager
import hashlib
import importlib.abc
import importlib.util
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import struct
import tempfile
import traceback
from types import ModuleType
import unittest
from unittest.mock import patch

DRIVER_PATH = Path(__file__).parent / "diagnostics/probe_mg_saved_thread_control.py"
HELPER_PATH = Path(__file__).parent / "diagnostics/_owned_native_session.py"
FIXTURE_PATH = Path(__file__).parent / "fixtures/mg_saved_thread_control_8863_native.json"


def recorded_diagnostic(case):
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))["diagnostics"][case]
DEFAULT = object()


class ProbeError(RuntimeError):
    pass


class BrokenText(ProbeError):
    def __str__(self):
        raise ValueError("exception text formatting failed")


def trip(error):
    raise error


def module(name, **members):
    value = ModuleType(name)
    value.__dict__.update(members)
    return value


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    value = importlib.util.module_from_spec(spec)
    sys.modules[name] = value
    spec.loader.exec_module(value)
    return value


class NoNativeImports(importlib.abc.MetaPathFinder):
    prefixes = ("pythoncom", "pywintypes", "win32", "comtypes", "solidworks_mcp", "azure", "temporalio", "_artifact_cache", "_telemetry", "_watchdog", "_com", "draw_mg_magnifying_bracket")

    def __init__(self):
        self.attempts = []

    def find_spec(self, fullname, path=None, target=None):
        if any(fullname.startswith(prefix) for prefix in self.prefixes):
            self.attempts.append(fullname)
            raise AssertionError(f"real native/provider import forbidden: {fullname}")
        return None


class Span:
    def __init__(self, telemetry, name):
        self.telemetry, self.name = telemetry, name

    def __enter__(self):
        self.telemetry.hit(self.name + ".enter")
        return self

    def __exit__(self, exc_type, error, original_tb):
        self.telemetry.exit_errors.append((self.name, exc_type, error, original_tb))
        self.telemetry.hit(self.name + ".exit")
        return False

    async def __aenter__(self):
        return self.__enter__()

    async def __aexit__(self, *args):
        return self.__exit__(*args)


class Telemetry:
    def __init__(self):
        self.failures = {}
        self.events = []
        self.exit_errors = []
        self.render_exception = False

    def hit(self, name):
        self.events.append(name)
        if name in self.failures:
            trip(self.failures[name])

    def aspan(self, name):
        return Span(self, name)

    def build_session(self, _name):
        return Span(self, "build")

    def info(self, *_args, **_kwargs):
        self.hit("info")

    def error(self, _message, **kwargs):
        if self.render_exception:
            str(kwargs["exc_info"][1])
        self.hit("error")

    def shutdown(self):
        self.hit("shutdown")


class Sheet:
    def __init__(self, name):
        self.name = name

    def GetName(self):
        return self.name


class SectionLabel:
    def __init__(self, label):
        self.label = label

    def GetLabel(self):
        return self.label


class View:
    def __init__(self, part, sheet_name, section_label, *, sheet=False, base=False):
        self.part, self.sheet, self.base = part, sheet, base
        self.sheet_name, self.section_label = sheet_name, section_label
        self.Name = sheet_name if sheet else f"Section View {section_label}-{section_label}"

    def GetSection(self):
        return None if self.sheet or self.base else SectionLabel(self.section_label)

    def GetBaseView(self):
        return View(self.part, self.sheet_name, self.section_label, base=True)

    @property
    def ReferencedDocument(self):
        return self.part


class SketchManager:
    def __init__(self, document):
        self.document = document

    @property
    def ActiveSketch(self):
        doc = self.document
        doc.app.events.append(("ActiveSketch", doc.kind, doc.active_sketch))
        if isinstance(doc.active_sketch, BaseException):
            trip(doc.active_sketch)
        return doc.active_sketch


class Document:
    def __init__(self, path, kind, *, readonly=True):
        self.path, self.kind = str(path), kind
        self.readonly = readonly
        self.dirty = False
        self.part = None
        self.app = None
        self.native_identity = object()
        self.sheet_name = "Lever Geometry" if "sm-summing-lever" in self.path else "Sheet1"
        self.section_label = "H" if self.sheet_name == "Lever Geometry" else "A"
        self.active_sketch = None
        self.sketch_manager_error = None
        self.scene = None
        self.extra_views = []

    @property
    def Extension(self):
        return self.scene

    def FirstFeature(self):
        return self.scene.wizard

    def GetBodies2(self, body_type, visible):
        if (body_type, visible) != (-1, False):
            raise AssertionError("all solid/sheet bodies including hidden required")
        return [self.scene.body]

    @property
    def SketchManager(self):
        if self.sketch_manager_error is not None:
            trip(self.sketch_manager_error)
        return SketchManager(self)

    def GetPathName(self):
        return self.path

    def GetTitle(self):
        return Path(self.path).name

    def GetType(self):
        return self.kind

    def GetSaveFlag(self):
        if isinstance(self.dirty, BaseException):
            trip(self.dirty)
        return self.dirty

    def IsOpenedReadOnly(self):
        if isinstance(self.readonly, BaseException):
            trip(self.readonly)
        return self.readonly

    def GetSheetNames(self):
        return (self.sheet_name,)

    def GetViews(self):
        return ((View(self.part, self.sheet_name, self.section_label, sheet=True),
                 View(self.part, self.sheet_name, self.section_label), *self.extra_views),)

    def Sheet(self, name):
        if name != self.sheet_name:
            raise AssertionError("unexpected sheet")
        return Sheet(name)

    def ActivateSheet(self, name):
        return name == self.sheet_name

    def GetCurrentSheet(self):
        return Sheet(self.sheet_name)

    def GetNext(self):
        return self.app.next_document(self)



class NativeObject:
    def __init__(self):
        self.native_identity = object()


class SourceFeature(NativeObject):
    def __init__(self, scene, name, kind, definition=None):
        super().__init__()
        self.scene, self.Name, self.kind, self.definition = scene, name, kind, definition
        self.next = self.child = self.owner = None
        self.faces = None
        self.type_error = self.definition_error = self.owner_error = None

    def GetTypeName2(self):
        if self.type_error is not None:
            trip(self.type_error)
        return self.kind

    def GetDefinition(self):
        if self.definition_error is not None:
            trip(self.definition_error)
        self.scene.definition_reads.append((self.Name, self.scene.phase))
        return self.definition

    def GetFirstSubFeature(self):
        return self.child

    def GetNextFeature(self):
        return self.next

    def GetNextSubFeature(self):
        return self.next

    def GetOwnerFeature(self):
        if self.owner_error is not None:
            trip(self.owner_error)
        return self.owner

    def GetFaces(self):
        return self.faces

    def IsRolledBack(self):
        return self.scene.accessed and self.kind != "HoleWzd"


class SourceDefinition:
    def __init__(self, scene, cosmetic=False):
        self.scene, self.cosmetic = scene, cosmetic
        values = recorded_diagnostic("b0")["reads"]
        self.values = {key.removeprefix("source."): value for key, value in values.items()
                       if key.startswith("source.") and isinstance(value, (str, int, float))}
        if cosmetic:
            self.values = {"ApplyThread": 1, "BlindDepth": 0.0, "Diameter": 0.00635,
                           "DiameterType": 0, "EndCondition": 1}

    def __getattr__(self, name):
        if name in self.values:
            value = self.values[name]
            if isinstance(value, BaseException):
                trip(value)
            return value
        raise AttributeError(name)

    @property
    def Edge(self):
        self.scene.edge_reads += 1
        if not self.cosmetic or not self.scene.accessed:
            raise AssertionError("selected Edge only inside confirmed cosmetic access")
        if self.scene.edge_error is not None:
            trip(self.scene.edge_error)
        return self.scene.selected_edge

    def AccessSelections(self, top_doc, component):
        if not self.cosmetic or top_doc is not self.scene.document or component is not None:
            raise AssertionError("wrong typed access or top document")
        if top_doc.readonly is not False:
            raise AssertionError("access on readonly document")
        self.scene.access_calls += 1
        self.scene.events.append("access")
        if isinstance(self.scene.access_result, BaseException):
            trip(self.scene.access_result)
        if self.scene.access_result is True:
            self.scene.accessed = True
            self.scene.phase = "accessed"
            top_doc.dirty = True
        return self.scene.access_result

    def ReleaseSelectionAccess(self):
        self.scene.release_calls += 1
        self.scene.events.append("release")
        if not self.scene.accessed:
            raise AssertionError("blind release forbidden")
        if self.scene.release_error is not None:
            trip(self.scene.release_error)
        self.scene.accessed = False
        self.scene.phase = "after"
        self.scene.on_release()
        return None


class SourceFace(NativeObject):
    def __init__(self, scene):
        super().__init__()
        self.scene = scene

    def GetEdges(self):
        return self.scene.edges

    def GetFeature(self):
        return self.scene.wizard


class SourceCurve:
    def __init__(self, scene):
        self.scene = scene

    def IsCircle(self):
        return True

    @property
    def CircleParams(self):
        return (0.0, 0.0, 0.0, 0.0, 0.0, 1.0, self.scene.radius)

    def GetEndParams(self):
        return self.scene.domain


class SourceTrim:
    def __init__(self, scene):
        self.scene = scene

    @property
    def UMinValue(self):
        return 0.0

    @property
    def UMaxValue(self):
        return self.scene.span

    @property
    def Sense(self):
        return True

    @property
    def StartPoint(self):
        return (self.scene.radius, 0.0, 0.0)

    @property
    def EndPoint(self):
        return (self.scene.radius * math.cos(self.scene.span), self.scene.radius * math.sin(self.scene.span), 0.0)


class SourceEdge(NativeObject):
    def __init__(self, scene):
        super().__init__()
        self.scene = scene
        self.curve_fetched = False

    def GetCurve(self):
        self.curve_fetched = True
        return SourceCurve(self.scene)

    def GetCurveParams3(self):
        if not self.curve_fetched:
            raise AssertionError("GetCurve prerequisite missing")
        return SourceTrim(self.scene)

    def Evaluate2(self, parameter, derivatives):
        if derivatives != 0:
            raise AssertionError("only endpoint positions requested")
        status = struct.unpack("<d", struct.pack("<II", self.scene.eval_status, 0))[0]
        return (self.scene.radius * math.cos(parameter), self.scene.radius * math.sin(parameter), 0.0, status)

    def GetBody(self):
        return self.scene.edge_body

    def GetTwoAdjacentFaces2(self):
        return self.scene.faces


class SourceLineCurve:
    def __init__(self, edge):
        self.edge = edge

    def IsCircle(self):
        return False

    @property
    def CircleParams(self):
        raise AssertionError("line has no circle parameters")

    def GetEndParams(self):
        return self.edge.domain


class SourceLineTrim:
    UMinValue, UMaxValue, Sense = 0.0, 1.0, True
    StartPoint, EndPoint = (0.0, 0.0, 0.0), (1.0, 0.0, 0.0)


class SourceLineEdge(SourceEdge):
    def __init__(self, scene):
        super().__init__(scene)
        self.domain = (True, 0.0, 1.0, False, False)
        self.eval_status = 1

    def GetCurve(self):
        self.curve_fetched = True
        return SourceLineCurve(self)

    def GetCurveParams3(self):
        if not self.curve_fetched:
            raise AssertionError("GetCurve prerequisite missing")
        return SourceLineTrim()

    def Evaluate2(self, parameter, derivatives):
        if derivatives != 0:
            raise AssertionError("only endpoint positions requested")
        status = struct.unpack("<d", struct.pack("<II", self.eval_status, 0))[0]
        return (parameter, 0.0, 0.0, status)


class SourceScene:
    def __init__(self, document, mode):
        self.document = document
        self.phase = "before"
        self.accessed = False
        self.access_calls = self.release_calls = self.edge_reads = 0
        self.access_result = True
        self.release_error = self.edge_error = None
        self.definition_reads, self.events = [], []
        self.radius, self.span, self.eval_status = 0.003175, math.tau, 1
        self.domain = (True, 0.0, math.tau, True, True)
        self.body = NativeObject()
        self.edge_body = self.body
        self.wizard = SourceFeature(self, "LeverTap", "HoleWzd", SourceDefinition(self))
        self.cosmetic = SourceFeature(self, "ActualCosmetic", "CosmeticThread", SourceDefinition(self, True))
        self.later = SourceFeature(self, "LaterCut", "Cut")
        self.wizard.next = self.later
        if mode != "wizard_only":
            self.wizard.child = self.cosmetic
            self.cosmetic.owner = self.wizard
        self.faces = [SourceFace(self), SourceFace(self)]
        self.wizard.faces = self.faces
        self.later.faces = self.faces[1:]
        self.edge = SourceEdge(self)
        self.edges = [self.edge]
        self.selected_edge = self.edge
        self.references = {}
        self.resolve_status = 0
        self.resolve_override = None
        self.on_release = lambda: None

    def GetPersistReference3(self, entity):
        key = next((key for key, known in self.references.items() if known is entity), None)
        if key is None:
            key = len(self.references) + 1
            self.references[key] = entity
        return bytes([key])

    def GetObjectByPersistReference3(self, reference):
        entity = self.references[reference[0]]
        if self.resolve_override is not None:
            entity = self.resolve_override(entity)
        return entity, self.resolve_status


class Application:
    def __init__(self):
        self.documents = []
        self.active = None
        self.control = True
        self.count_override = DEFAULT
        self.count_results = []
        self.count_values = []
        self.first_override = DEFAULT
        self.next_overrides = {}
        self.readonly = {1: DEFAULT, 3: DEFAULT}
        self.source_mode = "wizard_only"
        self.scenes = []
        self.prepare_scene = lambda _scene: None
        self.attach_error = None
        self.identity_override = None
        self.open_calls = []
        self.close_calls = []
        self.events = []
        self.auto_unload_part = False
        self.control_after_first_close = True
        self.after_open = lambda _doc: None
        self.before_open = lambda _path, _kind: None
        self.close_error = None
        self.open_warning = 0
        self.open_warnings = {}
        self.activation_calls = []

    def __setattr__(self, name, value):
        if name in ("UserControl", "Visible", "UserControlBackground"):
            raise AssertionError("native setting writes forbidden")
        object.__setattr__(self, name, value)

    def GetProcessID(self):
        if self.attach_error is not None:
            trip(self.attach_error)
        return 37136

    def RevisionNumber(self):
        return "34.3.0"

    def GetDocumentCount(self):
        self.events.append("GetDocumentCount")
        value = self.count_results.pop(0) if self.count_results else self.count_override
        if value is DEFAULT:
            value = len(self.documents)
        self.count_values.append(value)
        if isinstance(value, BaseException):
            trip(value)
        return value

    def GetDocuments(self):
        raise AssertionError("array inventory acceptance/fallback is forbidden")

    @property
    def ActiveDoc(self):
        return self.active

    @property
    def UserControl(self):
        self.events.append("UserControl")
        if isinstance(self.control, BaseException):
            trip(self.control)
        return self.control

    def IsSame(self, left, right):
        self.events.append("IsSame")
        if callable(self.identity_override):
            return self.identity_override(left, right)
        return self.identity_override if self.identity_override is not None else int(left.native_identity is right.native_identity)

    def OpenDoc6(self, path, kind, options, configuration, errors, warnings):
        self.open_calls.append((path, kind, options, configuration, errors, warnings))
        self.before_open(path, kind)
        if kind == 1 and self.documents:
            raise AssertionError("next pair opened before native emptiness")
        self.events.append(("OpenDoc6", Path(path).name))
        expected_options = 1 if kind == 1 and "mg-magnifying-bracket" in path else 3
        if (options, configuration, errors, warnings) != (expected_options, "", 0, 0):
            raise AssertionError("fixed SM/S1 open contract changed")
        readonly = bool(options & 2) if self.readonly[kind] is DEFAULT else self.readonly[kind]
        doc = Document(path, kind, readonly=readonly)
        doc.app = self
        if kind == 1:
            doc.scene = SourceScene(doc, self.source_mode)
            self.scenes.append(doc.scene)
            self.prepare_scene(doc.scene)
        if kind == 3:
            doc.part = next(item for item in self.documents if item.kind == 1)
        self.documents.append(doc)
        self.active = doc
        self.after_open(doc)
        case = "s1" if "mg-magnifying-bracket" in path else "sm_positive"
        return doc, 0, self.open_warnings.get((case, kind), self.open_warning if case == "s1" else 0)

    def ActivateDoc3(self, path, preferences, option, errors):
        self.activation_calls.append(path)
        if (preferences, option, errors) != (False, 1, 0):
            raise AssertionError("activation must not request rebuild/preferences")
        self.active = next(doc for doc in self.documents if doc.path == path)
        return self.active, 0

    def CloseDoc(self, title):
        self.close_calls.append(title)  # An unsafe ATTEMPT must fail the harness too.
        if not self.events or self.events[-1] != "UserControl" or self.control is not True:
            raise AssertionError("UserControl must be the final native close witness")
        if any(Path(doc.path).stem not in ("sm-summing-lever", "mg-magnifying-bracket", "mg-magnifying-bracket-native-thread")
               or type(doc.dirty) is not bool
               or (doc.dirty and ("mg-magnifying-bracket" not in doc.path or "diagnostic-copies" not in doc.path))
               for doc in self.documents):
            raise AssertionError("CloseDoc could touch an unowned/unknown-dirty or dirty SM document")
        if self.close_error is not None:
            trip(self.close_error)
        self.events.append("CloseDoc")
        target = next(doc for doc in self.documents if doc.GetTitle() == title)
        self.documents.remove(target)
        if target.kind == 3 and self.auto_unload_part:
            self.documents[:] = [doc for doc in self.documents if doc.kind != 1]
        self.active = self.documents[-1] if self.documents else None
        self.control = self.control_after_first_close

    def GetFirstDocument(self):
        self.events.append("GetFirstDocument")
        for doc in self.documents:
            doc.app = self
        value = self.first_override
        if value is DEFAULT:
            value = self.documents[0] if self.documents else None
        if isinstance(value, BaseException):
            trip(value)
        if isinstance(value, Document):
            value.app = self
        return value

    def next_document(self, doc):
        self.events.append("GetNext")
        if doc in self.next_overrides:
            value = self.next_overrides[doc]
        else:
            index = self.documents.index(doc) + 1
            value = self.documents[index] if index < len(self.documents) else None
        if isinstance(value, BaseException):
            trip(value)
        if isinstance(value, Document):
            value.app = self
        return value



class Adapter:
    def __init__(self, app):
        self.app = app
        self.swApp = None
        self.currentModel = None
        self.disconnect_error = None
        self.disconnect_calls = 0

    def _initialize_com_apartment(self):
        pass

    async def connect(self):
        raise AssertionError("ordinary adapter connect forbidden")

    async def disconnect(self):
        self.disconnect_calls += 1
        self.currentModel = None
        self.swApp = None
        if self.disconnect_error is not None:
            trip(self.disconnect_error)


class Environment:
    def __init__(self):
        self.app = Application()
        self.adapter = Adapter(self.app)
        self.telemetry = Telemetry()
        self.watchdog_events = []
        self.watchdog_stop_error = None
        self.cache_calls = []
        self.diagnostic_calls = 0
        self.after_diagnostic = lambda: None
        self.guard = NoNativeImports()
        self.blob_calls = []
        self.blob_payload = b"offline captured drawing fixture"
        self.blob_error = None
        self.blob_close_error = None
        self.before_diagnostic = lambda: None
        self.diagnostic_result = lambda feature: recorded_diagnostic("sm_positive" if feature == "BracketMountingTaps" else "b0")
        self.identity_override = None
        self.path_redirect = None
        self.copy_fs_attempts = []

    def credential(self):
        self.blob_calls.append("ManagedIdentityCredential")
        return module("fake_credential", close=lambda: self.blob_calls.append("credential.close"))

    def container(self, account_url, container, *, credential):
        self.blob_calls.append(("ContainerClient", account_url, container))

        def get_blob_client(blob):
            self.blob_calls.append(("get_blob_client", blob))

            def readall():
                self.blob_calls.append("readall")
                if self.blob_error is not None:
                    trip(self.blob_error)
                return self.blob_payload

            def download_blob():
                self.blob_calls.append("download_blob")
                return module("fake_download", readall=readall)

            return module("fake_blob", download_blob=download_blob)

        def close():
            self.blob_calls.append("container.close")
            if self.blob_close_error is not None:
                trip(self.blob_close_error)

        return module("fake_container", get_blob_client=get_blob_client, close=close)

    def restore_path(self, path):
        # Same strict unaliased-output policy as repository _restore_path;
        # Path.resolve is independently fault-injected for ancestor redirection.
        target = Path(os.path.abspath(path))
        output_root = self.driver.ROOT / "cad/out"
        if target == output_root or not target.is_relative_to(output_root) or target.resolve() != target:
            raise RuntimeError("uncertified output path")
        return target

    def stop(self):
        self.watchdog_events.append("stop")
        if self.watchdog_stop_error is not None:
            trip(self.watchdog_stop_error)

    def restore(self, key, outputs, label):
        if self.app.documents:
            raise AssertionError("restore attempted before native emptiness")
        self.cache_calls.append((key, outputs, label))
        return True

    def diagnostic(self, _adapter, _section, *, feature_name):
        expected = "BracketMountingTaps" if self.diagnostic_calls == 0 else "LeverTap"
        if feature_name != expected:
            raise AssertionError("wrong diagnostic feature/order")
        self.diagnostic_calls += 1
        self.app.events.append(("diagnostic", feature_name))
        self.before_diagnostic()
        self.after_diagnostic()
        return self.diagnostic_result(feature_name)

    @contextmanager
    def installed(self):
        def forbidden(*_args, **_kwargs):
            raise AssertionError("host process/kill/hard-exit action forbidden")

        with ExitStack() as stack:
            stack.enter_context(patch.dict(sys.modules))
            for name in tuple(sys.modules):
                if any(name.startswith(prefix) for prefix in self.guard.prefixes):
                    del sys.modules[name]
            diagnostics = module("diagnostics", __path__=[])
            win32 = module("win32com", __path__=[])
            client = module("win32com.client", GetActiveObject=lambda _name: self.app)
            win32.client = client
            stubs = {
                "diagnostics": diagnostics,
                "diagnostics._script_paths": module("diagnostics._script_paths"),
                "win32com": win32, "win32com.client": client,
                "_com": module("_com", _early_bound=lambda value, _kind: value),
                "_telemetry": self.telemetry,
                "_watchdog": module("_watchdog", start=lambda: self.watchdog_events.append("start"), stop=self.stop),
                "_artifact_cache": module("_artifact_cache", restore=self.restore, _restore_path=self.restore_path),
                "azure": module("azure", __path__=[]),
                "azure.identity": module("azure.identity", ManagedIdentityCredential=self.credential),
                "azure.storage": module("azure.storage", __path__=[]),
                "azure.storage.blob": module("azure.storage.blob", ContainerClient=self.container),
                "draw_mg_magnifying_bracket": module("draw_mg_magnifying_bracket", _mouth_thread_diagnostic=self.diagnostic),
                "solidworks_mcp": module("solidworks_mcp", __path__=[]),
                "solidworks_mcp.adapters": module("solidworks_mcp.adapters", __path__=[]),
                "solidworks_mcp.adapters.pywin32_adapter": module("solidworks_mcp.adapters.pywin32_adapter", PyWin32Adapter=lambda _config: self.adapter),
            }
            sys.modules.update(stubs)
            sys.meta_path.insert(0, self.guard)
            stack.callback(sys.meta_path.remove, self.guard)
            stack.enter_context(patch.object(sys, "dont_write_bytecode", True))
            stack.enter_context(patch.dict(os.environ, {"HARMONIC_COM_SEAT": "offline-fake", "HARMONIC_SW_AUTOSTART": "0", "HARMONIC_DIAGNOSTIC_SW_PID": "37136"}))
            stack.enter_context(patch.object(os, "_exit", forbidden))
            stack.enter_context(patch.object(os, "kill", forbidden))
            stack.enter_context(patch.object(subprocess, "Popen", forbidden))
            stack.enter_context(patch.object(subprocess, "run", forbidden))
            self.helper = load("diagnostics._owned_native_session", HELPER_PATH)
            self.driver = load("_saved_control_driver_under_test", DRIVER_PATH)
            yield self
            if self.guard.attempts:
                raise AssertionError(f"real imports attempted: {self.guard.attempts}")

    def run_driver(self):
        with tempfile.TemporaryDirectory(prefix="sm-control-offline-") as temporary:
            root = Path(temporary).resolve()
            driver = self.driver
            driver.ROOT = root
            driver.REPORT = root / "cad/out/reports/diagnostics/mg-saved-thread-control.json"
            driver.CONTRACT_PATH = root / "contract.json"
            # Fake provider bytes are real local temp files so copy/hash guards
            # execute normally. Native behavioral dictionaries stay unmodified.
            for case in driver.CONTRACT["cases"]:
                for kind in ("part", "drawing"):
                    payload = b"offline captured drawing fixture" if case["case"] == "s1" and kind == "drawing" else f"{case['case']} {kind}".encode()
                    case[kind].update(bytes=len(payload), sha256=hashlib.sha256(payload).hexdigest())
                    target = root / case[kind]["path"]
                    target.parent.mkdir(parents=True, exist_ok=True)
                    target.write_bytes(payload)
                case["historical_provenance"]["execution_token_canonical_md5"] = hashlib.md5(
                    (case["part"]["sha256"] + "\n").encode(), usedforsecurity=False,
                ).hexdigest()
            driver.CONTRACT_PATH.write_text(json.dumps(driver.CONTRACT), encoding="utf-8")
            original_identity = driver.file_identity

            def identity(path):
                if self.identity_override is not None:
                    value = self.identity_override(path)
                    if value is not DEFAULT:
                        return value
                for case in driver.CONTRACT["cases"]:
                    for kind in ("part", "drawing"):
                        if Path(path) == root / case[kind]["path"]:
                            if case["case"] == "s1" and kind == "drawing":
                                return original_identity(path)
                            return {key: case[kind][key] for key in ("bytes", "sha256")}
                return original_identity(path)

            original_open, original_mkdir = Path.open, Path.mkdir
            original_text, original_bytes = Path.write_text, Path.write_bytes
            original_resolve = Path.resolve

            def redirected_resolve(path, *args, **kwargs):
                target = Path(os.path.abspath(path))
                if self.path_redirect is not None:
                    ancestor = root / self.path_redirect
                    if target.is_relative_to(ancestor):
                        return root.parent / f"{root.name}-outside" / target.relative_to(ancestor)
                return original_resolve(path, *args, **kwargs)

            def record_copy_creation(path, operation):
                if "diagnostic-copies" in Path(path).parts:
                    self.copy_fs_attempts.append((operation, str(path)))

            def owned(path):
                if not Path(path).resolve().is_relative_to(root):
                    raise AssertionError(f"write outside temporary root refused: {path}")

            def guarded_open(path, mode="r", *args, **kwargs):
                if any(flag in mode for flag in "wax+"):
                    record_copy_creation(path, f"open:{mode}")
                    owned(path)
                return original_open(path, mode, *args, **kwargs)

            def guarded_mkdir(path, *args, **kwargs):
                record_copy_creation(path, "mkdir")
                owned(path)
                return original_mkdir(path, *args, **kwargs)

            def guarded_text(path, *args, **kwargs):
                owned(path)
                return original_text(path, *args, **kwargs)

            def guarded_bytes(path, *args, **kwargs):
                owned(path)
                return original_bytes(path, *args, **kwargs)

            with ExitStack() as stack:
                stack.enter_context(patch.object(Path, "resolve", redirected_resolve))
                stack.enter_context(patch.object(driver, "file_identity", identity))
                stack.enter_context(patch.object(sys, "argv", [str(DRIVER_PATH), "--disposable-source-tree"]))
                stack.enter_context(patch.object(Path, "open", guarded_open))
                stack.enter_context(patch.object(Path, "mkdir", guarded_mkdir))
                stack.enter_context(patch.object(Path, "write_text", guarded_text))
                stack.enter_context(patch.object(Path, "write_bytes", guarded_bytes))
                original_path = list(sys.path)
                stack.callback(lambda: sys.path.__setitem__(slice(None), original_path))
                code = driver.main()
            report = json.loads(driver.REPORT.read_text(encoding="utf-8"))
            captures = [json.loads(path.read_text(encoding="utf-8")) for path in root.glob("cad/out/reports/failures/mg-saved-thread-control/*/capture.json")]
            return code, report, captures


class OwnedControlSmoke(unittest.TestCase):
    def test_attach_primary_survives_span_disconnect_stop_and_shutdown(self):
        with Environment().installed() as env:
            primary = BrokenText()
            env.app.attach_error = primary
            env.adapter.disconnect_error = ProbeError("disconnect")
            env.watchdog_stop_error = ProbeError("watchdog stop")
            env.telemetry.failures.update({"sw.attach.exit": ProbeError("attach observer"), "build.exit": ProbeError("session exit"), "shutdown": ProbeError("shutdown")})
            env.telemetry.render_exception = True
            failures = []

            async def body(_adapter):
                self.fail("attach failure reached body")

            self.assertEqual(env.helper.run_owned_diagnostic(body, failures=failures), 1)
            self.assertIs(failures[0][1], primary)
            self.assertTrue(any(frame.f_code is trip.__code__ for frame, _ in traceback.walk_tb(failures[0][2])))
            self.assertEqual(env.adapter.disconnect_calls, 1)
            self.assertEqual(env.watchdog_events, ["start", "stop"])
            phases = [phase for phase, _, _ in failures]
            for phase in ("attach.span.exit", "disconnect", "watchdog.stop", "runner.observer", "build_session", "telemetry.shutdown"):
                self.assertIn(phase, phases)

    def test_actual_phase_error_reaches_its_span_and_root_context(self):
        for phase in ("attach", "disconnect", "body"):
            with self.subTest(phase=phase), Environment().installed() as env:
                primary = ProbeError(phase)
                if phase == "attach":
                    env.app.attach_error = primary
                elif phase == "disconnect":
                    env.adapter.disconnect_error = primary
                failures = []

                async def body(_adapter):
                    if phase == "body":
                        trip(primary)

                self.assertEqual(env.helper.run_owned_diagnostic(body, failures=failures), 1)
                self.assertIs(failures[0][1], primary)
                self.assertEqual(failures[0][0], phase)
                exits = {name: (kind, error, original_tb) for name, kind, error, original_tb in env.telemetry.exit_errors}
                self.assertIs(exits["build"][1], primary)
                self.assertIs(exits["sw.attach"][1], primary if phase == "attach" else None)
                self.assertIs(exits["sw.disconnect"][1], primary if phase == "disconnect" else None)
                self.assertTrue(any(frame.f_code is trip.__code__ for frame, _ in traceback.walk_tb(failures[0][2])))

    def test_connected_body_raises_same_exception_after_failed_disconnect_observer(self):
        with Environment().installed() as env:
            primary = ProbeError("body")
            env.telemetry.failures["sw.disconnect.enter"] = ProbeError("observer entry")
            env.adapter.disconnect_error = ProbeError("disconnect")
            failures = []

            async def body(_adapter):
                trip(primary)

            with self.assertRaises(ProbeError) as caught:
                asyncio.run(env.helper.connected_probe(env.adapter, body, failures=failures))
            self.assertIs(caught.exception, primary)
            self.assertIs(failures[0][1], primary)
            self.assertTrue(any(frame.f_code is trip.__code__ for frame, _ in traceback.walk_tb(failures[0][2])))
            self.assertEqual(env.adapter.disconnect_calls, 1)
            self.assertIn("disconnect.span.enter", [phase for phase, _, _ in failures])

    def test_runner_body_primary_survives_exception_rendering_and_shutdown(self):
        with Environment().installed() as env:
            primary = BrokenText()
            env.adapter.disconnect_error = ProbeError("secondary disconnect")
            env.telemetry.render_exception = True
            env.telemetry.failures["shutdown"] = ProbeError("secondary shutdown")
            failures = []

            async def body(_adapter):
                trip(primary)

            self.assertEqual(env.helper.run_owned_diagnostic(body, failures=failures), 1)
            self.assertIs(failures[0][1], primary)
            self.assertEqual(failures[0][0], "body")
            self.assertTrue(any(frame.f_code is trip.__code__ for frame, _ in traceback.walk_tb(failures[0][2])))
            self.assertIn("runner.observer", [phase for phase, _, _ in failures])
            self.assertIn("telemetry.shutdown", [phase for phase, _, _ in failures])
            self.assertEqual(env.adapter.disconnect_calls, 1)

    def test_teardown_only_error_is_actual_first_failure(self):
        with Environment().installed() as env:
            error = ProbeError("disconnect only")
            env.adapter.disconnect_error = error
            failures = []

            async def body(_adapter):
                return {"observed": True}

            self.assertEqual(env.helper.run_owned_diagnostic(body, failures=failures), 1)
            self.assertIs(failures[0][1], error)
            self.assertEqual(failures[0][0], "disconnect")

    def test_driver_attach_failure_exports_actual_original_not_runner_surrogate(self):
        with Environment().installed() as env:
            env.app.attach_error = BrokenText()
            env.adapter.disconnect_error = ProbeError("secondary disconnect")
            code, report, captures = env.run_driver()
            self.assertEqual(code, 1)
            self.assertEqual(report["primary_failure"]["type"], "BrokenText")
            self.assertEqual(report["primary_failure"]["operation"], "runner.attach")
            self.assertEqual(report["primary_failure"]["message"], "<exception text unavailable>")
            self.assertEqual(len(captures), 1)
            self.assertTrue(captures[0]["primary_traceback"]["available"])
            self.assertEqual(env.cache_calls, [])

    def test_initial_null_cursor_and_two_zero_counts_prove_empty(self):
        with Environment().installed() as env:
            code, report, captures = env.run_driver()
            self.assertEqual(code, 0)
            self.assertEqual(report["cases"][0]["isolation_gate"], "accepted")
            initial = report["cases"][0]["inventories"]["initial"]
            self.assertEqual(initial["method"], "GetFirstDocument/GetNext")
            self.assertEqual(initial["native_count_before"], 0)
            self.assertEqual(initial["native_count_after"], 0)
            self.assertEqual(initial["visited_count"], 0)
            self.assertEqual(initial["first_document_state"], "NULL")
            self.assertIs(initial["cursor_terminated"], True)
            self.assertIs(initial["enumerated"], True)
            self.assertEqual(env.app.count_values[:2], [0, 0])
            self.assertEqual(env.app.events[:3], ["GetDocumentCount", "GetFirstDocument", "GetDocumentCount"])
            self.assertEqual(captures, [])

    def test_any_initial_document_refuses_without_touching_it(self):
        with Environment().installed() as env:
            foreign = Document("C:/foreign/hidden.SLDPRT", 1)
            env.app.documents.append(foreign)
            code, report, _ = env.run_driver()
            self.assertEqual(code, 1)
            self.assertEqual(report["cases"][0]["isolation_gate"], "refused")
            self.assertEqual(env.cache_calls, [])
            self.assertEqual(env.app.close_calls, [])
            self.assertEqual(env.app.documents, [foreign])
            self.assertIsNone(env.app.active)
            initial = report["cases"][0]["inventories"]["initial"]
            self.assertEqual(initial["native_count_before"], 1)
            self.assertEqual(initial["native_count_after"], 1)
            self.assertEqual(initial["visited_count"], 1)
            self.assertIs(initial["enumerated"], True)
            self.assertIs(initial["cursor_terminated"], True)
            self.assertEqual(initial["documents"][0]["path"], foreign.path)

    def test_initial_user_control_must_be_actual_true(self):
        for value in (False, None, 1, ProbeError("unreadable UserControl")):
            with self.subTest(value_type=type(value).__name__), Environment().installed() as env:
                env.app.control = value
                code, report, captures = env.run_driver()
                self.assertEqual(code, 1)
                self.assertEqual(report["cases"][0]["isolation_gate"], "refused")
                self.assertEqual(env.cache_calls, [])
                self.assertEqual(env.app.close_calls, [])
                self.assertEqual(len(captures), 1)

    def test_boolean_document_count_cannot_certify_empty(self):
        with Environment().installed() as env:
            env.app.count_override = True
            code, report, captures = env.run_driver()
            self.assertEqual(code, 1)
            self.assertEqual(report["cases"][0]["isolation_gate"], "refused")
            self.assertEqual(env.cache_calls, [])
            self.assertEqual(env.app.close_calls, [])
            self.assertEqual(len(captures), 1)

    def test_actual_empty_user_control_true_observes_and_closes_drawing_first(self):
        with Environment().installed() as env:
            code, report, captures = env.run_driver()
            self.assertEqual(code, 0)
            self.assertEqual(report["status"], "observed")
            self.assertEqual(report["native_ship"], "NOT_EVALUATED")
            self.assertEqual([row[1] for row in env.app.open_calls], [1, 3, 1, 3])
            self.assertEqual(env.app.close_calls, ["sm-summing-lever.SLDDRW", "sm-summing-lever.SLDPRT",
                                                 "mg-magnifying-bracket-native-thread.SLDDRW", "mg-magnifying-bracket.SLDPRT"])
            self.assertEqual(env.app.documents, [])
            self.assertEqual(captures, [])

    def test_drawing_close_auto_unloads_part_without_stale_second_close(self):
        with Environment().installed() as env:
            env.app.auto_unload_part = True
            code, report, _ = env.run_driver()
            self.assertEqual(code, 0)
            self.assertEqual(env.app.close_calls, ["sm-summing-lever.SLDDRW", "mg-magnifying-bracket-native-thread.SLDDRW"])
            self.assertEqual(report["cases"][0]["closures"][1]["status"], "already_unloaded")
            two_owned = report["cases"][0]["inventories"]["after_open_drawing"]
            self.assertEqual(two_owned["native_count_before"], 2)
            self.assertEqual(two_owned["native_count_after"], 2)
            self.assertEqual(two_owned["visited_count"], 2)
            self.assertIs(two_owned["cursor_terminated"], True)
            self.assertIs(two_owned["enumerated"], True)
            unloaded = report["cases"][0]["inventories"]["before_close_1"]
            self.assertEqual(unloaded["native_count_before"], 0)
            self.assertEqual(unloaded["native_count_after"], 0)
            self.assertEqual(unloaded["visited_count"], 0)
            self.assertEqual(unloaded["first_document_state"], "NULL")
            self.assertIs(unloaded["cursor_terminated"], True)
            self.assertIs(unloaded["enumerated"], True)

    def test_each_open_requires_actual_read_only_readback(self):
        for kind in (1, 3):
            for value in (False, None, ProbeError("readonly unreadable")):
                with self.subTest(kind=kind, value_type=type(value).__name__), Environment().installed() as env:
                    env.app.readonly[kind] = value
                    code, report, captures = env.run_driver()
                    self.assertEqual(code, 1)
                    self.assertEqual(env.diagnostic_calls, 0)
                    self.assertFalse(report["cases"][0]["collection_completed"])
                    self.assertEqual(len(captures), 1)

    def test_unowned_new_document_blocks_every_close(self):
        with Environment().installed() as env:
            foreign = Document("C:/foreign/new-hidden.SLDPRT", 1)
            env.after_diagnostic = lambda: env.app.documents.append(foreign)
            code, report, captures = env.run_driver()
            self.assertEqual(code, 1)
            self.assertTrue(report["cases"][0]["collection_completed"])
            self.assertEqual(env.app.close_calls, [])
            self.assertIn(foreign, env.app.documents)
            self.assertEqual(len(captures), 1)
            self.assertTrue(all(row["status"] == "stranded_owned" for row in captures[0]["cases"][0]["closures"]))

    def test_cleanup_only_saveflag_failure_keeps_actual_traceback_and_exports(self):
        with Environment().installed() as env:
            primary = BrokenText()
            env.after_diagnostic = lambda: setattr(env.app.documents[0], "dirty", primary)
            code, report, captures = env.run_driver()
            self.assertEqual(code, 1)
            self.assertEqual(report["runner_exit_code"], 1)
            self.assertTrue(report["cases"][0]["collection_completed"])
            self.assertEqual(env.app.close_calls, [])
            self.assertEqual(len(captures), 1)
            capture = captures[0]
            self.assertEqual(capture["primary_failure"]["type"], "BrokenText")
            self.assertEqual(capture["primary_failure"]["message"], "<exception text unavailable>")
            self.assertTrue(any(frame["function"] == "GetSaveFlag" for frame in capture["primary_traceback"]["frames"]))
            self.assertTrue(all(row["status"] == "stranded_owned" for row in capture["cases"][0]["closures"]))

    def test_interrupt_is_retained_before_secondary_cleanup_failure(self):
        for exception_type in (SystemExit, KeyboardInterrupt):
            with self.subTest(exception_type=exception_type.__name__), Environment().installed() as env:
                primary = exception_type("original interrupt")

                def interrupt_diagnostic():
                    env.app.documents[0].dirty = ProbeError("secondary cleanup failure")
                    raise primary

                env.after_diagnostic = interrupt_diagnostic
                code, report, captures = env.run_driver()
                self.assertEqual(code, 1)
                self.assertEqual(report["runner_exit_code"], 1)
                self.assertEqual(env.app.close_calls, [])
                self.assertEqual(len(captures), 1)
                capture = captures[0]
                self.assertEqual(capture["primary_failure"]["type"], exception_type.__name__)
                self.assertEqual(capture["primary_failure"]["operation"], "collect")
                self.assertEqual(capture["primary_failure"]["message"], "original interrupt")
                self.assertTrue(any(frame["function"] == "interrupt_diagnostic" for frame in capture["primary_traceback"]["frames"]))
                self.assertTrue(any(row["type"] == "ProbeError" for row in capture["errors"]))
                self.assertTrue(all(row["status"] == "stranded_owned" for row in capture["cases"][0]["closures"]))

    def test_dirty_or_unknown_saveflag_never_closes(self):
        for value in (True, None, 0):
            with self.subTest(value=value), Environment().installed() as env:
                env.after_diagnostic = lambda: setattr(env.app.documents[0], "dirty", value)
                code, _, captures = env.run_driver()
                self.assertEqual(code, 1)
                self.assertEqual(env.app.close_calls, [])
                self.assertEqual(len(captures), 1)

    def test_user_control_rechecked_before_every_close(self):
        with Environment().installed() as env:
            env.app.control_after_first_close = False
            code, _, captures = env.run_driver()
            self.assertEqual(code, 1)
            self.assertEqual(env.app.close_calls, ["sm-summing-lever.SLDDRW"])
            self.assertEqual(len(env.app.documents), 1)
            self.assertEqual(captures[0]["cases"][0]["closures"][1]["status"], "stranded_owned")

    def test_unsupported_identity_cannot_authorize_close(self):
        with Environment().installed() as env:
            env.app.identity_override = -1
            code, report, captures = env.run_driver()
            self.assertEqual(code, 1)
            self.assertEqual(env.app.close_calls, [])
            self.assertTrue(any(row.get("raw") == -1 for row in report["cases"][0]["identity_comparisons"]))
            self.assertEqual(len(captures), 1)

    def test_initial_cursor_rejects_invalid_count_before_and_after(self):
        for phase in ("before", "after"):
            for value in (True, False, None, -1, 0.0, "0", ProbeError("count reader failed")):
                with self.subTest(phase=phase, value_type=type(value).__name__), Environment().installed() as env:
                    env.app.count_results = [value, 0] if phase == "before" else [0, value]
                    code, report, captures = env.run_driver()
                    self.assertEqual(code, 1)
                    self.assertEqual(report["cases"][0]["isolation_gate"], "refused")
                    self.assertFalse(report["cases"][0]["inventories"]["initial"]["enumerated"])
                    self.assertEqual(report["cases"][0]["inventories"]["initial"]["first_document_state"], "NULL")
                    self.assertEqual(len(env.app.count_values), 2)
                    self.assertTrue(any(row["operation"] == f"initial.GetDocumentCount.{phase}" for row in report["errors"]))
                    self.assertEqual(env.cache_calls, [])
                    self.assertEqual(env.app.open_calls, [])
                    self.assertEqual(env.app.close_calls, [])
                    self.assertEqual(len(captures), 1)

    def test_initial_cursor_count_drift_and_cardinality_mismatch_refuse(self):
        for shape in ("drift", "positive_count_null_first", "zero_count_nonnull_first", "short_chain", "null_first_with_resident"):
            with self.subTest(shape=shape), Environment().installed() as env:
                foreign = Document("C:/foreign/hidden.SLDPRT", 1)
                if shape == "drift":
                    env.app.count_results = [0, 1]
                elif shape == "positive_count_null_first":
                    env.app.count_override = 1
                elif shape == "zero_count_nonnull_first":
                    env.app.documents.append(foreign)
                    env.app.count_override = 0
                elif shape == "short_chain":
                    env.app.documents.append(foreign)
                    env.app.count_override = 2
                else:
                    env.app.documents.append(foreign)
                    env.app.first_override = None
                initial_documents = list(env.app.documents)
                code, report, captures = env.run_driver()
                self.assertEqual(code, 1)
                self.assertEqual(report["cases"][0]["isolation_gate"], "refused")
                self.assertFalse(report["cases"][0]["inventories"]["initial"]["enumerated"])
                self.assertTrue(any(row["operation"] == "initial.cursor.cardinality" for row in report["errors"]))
                self.assertEqual(len(env.app.count_values), 2)
                self.assertEqual(env.app.documents, initial_documents)
                self.assertEqual(env.cache_calls, [])
                self.assertEqual(env.app.open_calls, [])
                self.assertEqual(env.app.close_calls, [])
                self.assertEqual(len(captures), 1)

    def test_initial_cursor_cycles_and_native_duplicate_wrappers_refuse(self):
        for shape in ("self_loop", "cycle", "duplicate_wrapper"):
            with self.subTest(shape=shape), Environment().installed() as env:
                first = Document("C:/foreign/hidden-a.SLDPRT", 1)
                second = Document("C:/foreign/hidden-b.SLDPRT", 1)
                env.app.documents[:] = [first, second]
                if shape == "self_loop":
                    env.app.next_overrides[first] = first
                elif shape == "cycle":
                    env.app.next_overrides[second] = first
                else:
                    second.native_identity = first.native_identity
                code, report, captures = env.run_driver()
                self.assertEqual(code, 1)
                self.assertFalse(report["cases"][0]["inventories"]["initial"]["enumerated"])
                self.assertFalse(report["cases"][0]["inventories"]["initial"]["cursor_terminated"])
                self.assertTrue(any(row["message"] == "duplicate/cyclic native document cursor" for row in report["errors"]))
                self.assertLessEqual(report["cases"][0]["inventories"]["initial"]["visited_count"], 3)
                self.assertEqual(len(env.app.count_values), 2)
                self.assertEqual(env.app.documents, [first, second])
                self.assertEqual(env.cache_calls, [])
                self.assertEqual(env.app.open_calls, [])
                self.assertEqual(env.app.close_calls, [])
                self.assertEqual(len(captures), 1)

    def test_initial_cursor_reader_failure_is_not_null_termination(self):
        for member in ("GetFirstDocument", "GetNext"):
            with self.subTest(member=member), Environment().installed() as env:
                primary = ProbeError("actual cursor read failure")
                if member == "GetFirstDocument":
                    env.app.first_override = primary
                else:
                    foreign = Document("C:/foreign/hidden.SLDPRT", 1)
                    env.app.documents.append(foreign)
                    env.app.next_overrides[foreign] = primary
                code, report, captures = env.run_driver()
                self.assertEqual(code, 1)
                self.assertFalse(report["cases"][0]["inventories"]["initial"]["enumerated"])
                self.assertFalse(report["cases"][0]["inventories"]["initial"]["cursor_terminated"])
                self.assertEqual(len(env.app.count_values), 2)
                self.assertEqual(report["primary_failure"]["type"], "ProbeError")
                self.assertTrue(report["primary_failure"]["operation"].endswith(member))
                self.assertTrue(captures[0]["primary_traceback"]["available"])
                self.assertEqual(env.cache_calls, [])
                self.assertEqual(env.app.open_calls, [])
                self.assertEqual(env.app.close_calls, [])

    def test_cleanup_cursor_requires_native_self_and_distinct_identity(self):
        for result in (0, -1, 7, None, True, "1"):
            with self.subTest(result=result), Environment().installed() as env:
                env.after_diagnostic = lambda: setattr(env.app, "identity_override", lambda _left, _right: result)
                code, report, captures = env.run_driver()
                self.assertEqual(code, 1)
                self.assertTrue(report["cases"][0]["collection_completed"])
                self.assertFalse(report["cases"][0]["inventories"]["before_close_0"]["enumerated"])
                self.assertEqual(env.app.close_calls, [])
                self.assertEqual(len(env.app.documents), 2)
                self.assertTrue(all(row["status"] == "stranded_owned" for row in captures[0]["cases"][0]["closures"]))
        with Environment().installed() as env:
            env.after_diagnostic = lambda: setattr(
                env.app, "identity_override", lambda left, right: 1 if left is right else -1
            )
            code, report, captures = env.run_driver()
            self.assertEqual(code, 1)
            self.assertTrue(report["cases"][0]["collection_completed"])
            self.assertFalse(report["cases"][0]["inventories"]["before_close_0"]["enumerated"])
            self.assertTrue(any(row.get("raw") == -1 and ".identity.previous[" in row["operation"] for row in report["cases"][0]["identity_comparisons"]))
            self.assertEqual(env.app.close_calls, [])
            self.assertTrue(all(row["status"] == "stranded_owned" for row in captures[0]["cases"][0]["closures"]))

    def test_cleanup_cursor_drift_cardinality_cycles_and_duplicates_never_close(self):
        for shape in ("drift", "cardinality", "cycle", "duplicate_wrapper"):
            with self.subTest(shape=shape), Environment().installed() as env:
                def change_inventory():
                    first, second = env.app.documents
                    if shape == "drift":
                        env.app.count_results = [2, 3, 2, 3, 2, 3]
                    elif shape == "cardinality":
                        env.app.count_override = 3
                    elif shape == "cycle":
                        env.app.next_overrides[second] = first
                    else:
                        duplicate = Document(first.path, first.kind)
                        duplicate.native_identity = first.native_identity
                        env.app.documents.append(duplicate)

                env.after_diagnostic = change_inventory
                code, report, captures = env.run_driver()
                self.assertEqual(code, 1)
                self.assertTrue(report["cases"][0]["collection_completed"])
                self.assertFalse(report["cases"][0]["inventories"]["before_close_0"]["enumerated"])
                self.assertEqual(env.app.close_calls, [])
                self.assertTrue(all(row["status"] == "stranded_owned" for row in captures[0]["cases"][0]["closures"]))

    def test_cleanup_cursor_readers_preserve_error_and_independent_after_count(self):
        for member in ("GetFirstDocument", "GetNext", "count_before", "count_after",
                       "GetPathName", "GetTitle", "GetType", "GetSaveFlag"):
            with self.subTest(member=member), Environment().installed() as env:
                primary = ProbeError("original inventory reader")

                def fail_reader():
                    if member == "GetFirstDocument":
                        env.app.first_override = primary
                    elif member == "GetNext":
                        env.app.next_overrides[env.app.documents[0]] = primary
                    elif member == "count_before":
                        env.app.count_results = [primary, 2, primary, 2, primary, 2]
                    elif member == "count_after":
                        env.app.count_results = [2, primary, 2, primary, 2, primary]
                    else:
                        setattr(env.app.documents[0], member, lambda: trip(primary))

                env.after_diagnostic = fail_reader
                code, report, captures = env.run_driver()
                self.assertEqual(code, 1)
                self.assertEqual(report["runner_exit_code"], 1)
                self.assertTrue(report["cases"][0]["collection_completed"])
                initial_cleanup = report["cases"][0]["inventories"]["before_close_0"]
                self.assertFalse(initial_cleanup["enumerated"])
                if member != "count_after":
                    self.assertEqual(initial_cleanup["native_count_after"], 2)
                self.assertEqual(report["primary_failure"]["type"], "ProbeError")
                self.assertEqual(report["primary_failure"]["message"], "original inventory reader")
                self.assertTrue(captures[0]["primary_traceback"]["available"])
                self.assertEqual(env.app.close_calls, [])
                self.assertEqual(len(env.app.documents), 2)
                self.assertTrue(all(row["status"] == "stranded_owned" for row in captures[0]["cases"][0]["closures"]))
                if member == "GetPathName":
                    self.assertEqual(initial_cleanup["documents"][0]["title"], "sm-summing-lever.SLDPRT")
                    self.assertIs(initial_cleanup["documents"][0]["dirty"], False)
                    self.assertEqual(len(initial_cleanup["documents"]), 2)


    def test_two_pairs_have_independent_evidence_in_one_attached_callback(self):
        with Environment().installed() as env:
            code, report, captures = env.run_driver()
            self.assertEqual(code, 0)
            self.assertTrue(report["collection_completed"])
            self.assertEqual(report["cases"][0]["session_python_handles"], report["cases"][1]["session_python_handles"])
            self.assertEqual(report["cases"][0]["session_python_handles"]["adapter"], id(env.adapter))
            self.assertEqual(env.diagnostic_calls, 2)
            self.assertEqual(env.adapter.disconnect_calls, 1)
            self.assertEqual(env.telemetry.events.count("sw.attach.enter"), 1)
            self.assertEqual([row[0] for row in env.cache_calls], [
                env.driver.SM_POSITIVE["drawing"]["key"], env.driver.SM_POSITIVE["part"]["key"],
                env.driver.S1["part"]["key"],
            ])
            self.assertEqual(env.blob_calls, [
                "ManagedIdentityCredential",
                ("ContainerClient", "https://stswboot5qnlwu2vtr6gs.blob.core.windows.net", "results"),
                ("get_blob_client", env.driver.S1["drawing"]["blob"]),
                "download_blob", "readall", "container.close", "credential.close",
            ])
            for index, feature in enumerate(("BracketMountingTaps", "LeverTap")):
                case = report["cases"][index]
                self.assertEqual(case["status"], "observed")
                self.assertTrue(case["collection_completed"])
                self.assertEqual(case["diagnostic"]["feature"], feature)
                self.assertEqual(case["errors"], [])
                self.assertEqual(len(case["opens"]), 2)
                self.assertEqual(len(case["closures"]), 2)
                self.assertTrue(case["reads"]["base.reference_IsSame_opened_part"])
                for phase in ("initial", "final"):
                    self.assertTrue(case["inventories"][phase]["enumerated"])
                    self.assertEqual(case["inventories"][phase]["native_count_before"], 0)
                    self.assertEqual(case["inventories"][phase]["native_count_after"], 0)
                    self.assertEqual(case["inventories"][phase]["documents"], [])
                for kind in ("drawing", "part"):
                    self.assertEqual(case["reads"][f"staged.{kind}"], case["reads"][f"final.{kind}"])
                self.assertTrue(case["reads"]["final.currentModel_identity_restored"])
                self.assertTrue(case["reads"]["final.active_identity_restored"])
            self.assertEqual(report["cases"][1]["reads"]["sheet_names"], ["Sheet1"])
            self.assertEqual(report["cases"][1]["views"][1]["section_label"], "A")
            self.assertEqual(captures, [])

    def test_active_sketch_reads_enclose_entire_diagnostic_for_both_documents(self):
        with Environment().installed() as env:
            def during_diagnostic():
                for doc in env.app.documents:
                    doc.active_sketch = object()

            env.after_diagnostic = during_diagnostic
            code, report, _ = env.run_driver()
            self.assertEqual(code, 0)
            for case in report["cases"]:
                for name in ("source", "drawing"):
                    before = case["active_sketch"]["before_diagnostic_including_generation"][name]
                    after = case["active_sketch"]["after_diagnostic_including_generation"][name]
                    self.assertEqual(before, {"state": "NULL", "errors": []})
                    self.assertEqual(after, {"state": "PRESENT", "errors": []})
            events = [event for event in env.app.events if isinstance(event, tuple)
                      and event[0] in ("ActiveSketch", "diagnostic")]
            self.assertEqual([event[0] for event in events],
                             ["ActiveSketch", "ActiveSketch", "diagnostic", "ActiveSketch", "ActiveSketch"] * 2)
            self.assertEqual([event[1] for event in events if event[0] == "ActiveSketch"], [1, 3, 1, 3] * 2)

    def test_s1_sketch_read_failures_are_independent_unavailable_not_null(self):
        with Environment().installed() as env:
            primary = BrokenText()

            def prepare(doc):
                if "mg-magnifying-bracket" in doc.path:
                    if doc.kind == 1:
                        doc.sketch_manager_error = primary
                    else:
                        doc.active_sketch = object()

            env.app.after_open = prepare
            code, report, captures = env.run_driver()
            self.assertEqual(code, 1)
            self.assertEqual(report["cases"][0]["errors"], [])
            b0 = report["cases"][1]
            self.assertTrue(b0["collection_completed"])
            for phase in ("before_diagnostic_including_generation", "after_diagnostic_including_generation"):
                source = b0["active_sketch"][phase]["source"]
                self.assertEqual(source["state"], "UNAVAILABLE")
                self.assertEqual(source["errors"][0]["type"], "BrokenText")
                self.assertEqual(b0["active_sketch"][phase]["drawing"]["state"], "PRESENT")
            self.assertEqual(env.app.documents, [])
            self.assertEqual(captures[0]["primary_failure"]["case"], "s1")
            body_exit = next(row for row in env.telemetry.exit_errors if row[0] == "build")
            self.assertIs(body_exit[2], primary)
            self.assertTrue(any(frame.f_code is trip.__code__ for frame, _ in traceback.walk_tb(body_exit[3])))

    def test_wrong_reference_or_auto_loaded_document_never_gets_adopted(self):
        for case_index in (0, 1):
            for mode in ("wrong_path", "same_path_wrong_identity", "auto_loaded"):
                with self.subTest(case=case_index, mode=mode), Environment().installed() as env:
                    def change_reference(doc):
                        if doc.kind != 3 or ("mg-magnifying-bracket" in doc.path) != bool(case_index):
                            return
                        foreign = Document(doc.part.path if mode == "same_path_wrong_identity"
                                           else "C:/foreign/mg-magnifying-bracket.SLDPRT", 1)
                        doc.part = foreign
                        if mode == "auto_loaded":
                            env.app.documents.append(foreign)

                    env.app.after_open = change_reference
                    code, report, _ = env.run_driver()
                    self.assertEqual(code, 1)
                    self.assertEqual(env.diagnostic_calls, case_index)
                    failed = report["cases"][case_index]
                    self.assertEqual(len(failed["owned_documents"]), 2)
                    self.assertFalse(failed["collection_completed"])
                    if mode == "auto_loaded":
                        self.assertTrue(all(row["status"] == "stranded_owned" for row in failed["closures"]))
                        self.assertEqual(len(env.app.documents), 3)
                    else:
                        self.assertEqual(env.app.documents, [])
                    if case_index == 0:
                        self.assertEqual(report["cases"][1]["status"], "not_started")
                        self.assertEqual(env.blob_calls, [])

    def test_sm_final_hash_failure_prevents_s1_staging(self):
        with Environment().installed() as env:
            def changed_identity(path):
                if Path(path).name == "sm-summing-lever.SLDPRT" and env.diagnostic_calls:
                    return {"bytes": 1, "sha256": "changed"}
                return DEFAULT

            env.identity_override = changed_identity
            code, report, _ = env.run_driver()
            self.assertEqual(code, 1)
            self.assertEqual(report["cases"][1]["status"], "not_started")
            self.assertEqual(env.blob_calls, [])
            self.assertEqual(len(env.cache_calls), 2)
            self.assertEqual(env.app.documents, [])

    def test_s1_download_errors_or_hash_mismatch_cannot_open_or_replace_source(self):
        for mode in ("access_denied", "wrong_bytes"):
            with self.subTest(mode=mode), Environment().installed() as env:
                if mode == "access_denied":
                    env.blob_error = BrokenText()
                    env.blob_close_error = KeyboardInterrupt("secondary transport close")
                else:
                    env.blob_payload = b"wrong captured drawing"
                code, report, captures = env.run_driver()
                self.assertEqual(code, 1)
                self.assertEqual(report["cases"][0]["status"], "observed")
                self.assertEqual(report["cases"][1]["opens"], [])
                self.assertEqual(env.diagnostic_calls, 1)
                self.assertEqual(len(env.cache_calls), 2)
                self.assertEqual(env.app.documents, [])
                self.assertEqual(captures[0]["primary_failure"]["case"], "s1")
                self.assertEqual(captures[0]["primary_failure"]["operation"], "captured_blob.download")
                self.assertIn("credential.close", env.blob_calls)
                if mode == "access_denied":
                    self.assertEqual(captures[0]["primary_failure"]["type"], "BrokenText")
                    body_exit = next(row for row in env.telemetry.exit_errors if row[0] == "build")
                    self.assertIs(body_exit[2], env.blob_error)
                    self.assertTrue(any(frame.f_code is trip.__code__ for frame, _ in traceback.walk_tb(body_exit[3])))

    def test_s1_original_disk_hash_change_is_reported_after_owned_cleanup(self):
        with Environment().installed() as env:
            def change_bytes():
                if env.diagnostic_calls == 2:
                    (env.driver.ROOT / env.driver.S1["drawing"]["path"]).write_bytes(b"changed on disk")

            env.after_diagnostic = change_bytes
            code, report, _ = env.run_driver()
            self.assertEqual(code, 1)
            sm, b0 = report["cases"]
            self.assertEqual(sm["status"], "observed")
            self.assertEqual(b0["status"], "failed")
            self.assertNotEqual(b0["reads"]["staged.drawing"], b0["reads"]["final.drawing"])
            self.assertEqual(env.app.documents, [])

    def test_s1_dirty_copy_is_discarded_but_wrong_open_mode_refuses_access(self):
        for mode in ("dirty", "readonly"):
            with self.subTest(mode=mode), Environment().installed() as env:
                def prepare(doc):
                    if mode == "readonly" and "mg-magnifying-bracket" in doc.path and doc.kind == 1:
                        doc.readonly = True

                def dirty_after():
                    if mode == "dirty" and env.diagnostic_calls == 2:
                        env.app.documents[0].dirty = True

                env.app.after_open = prepare
                env.after_diagnostic = dirty_after
                code, report, _ = env.run_driver()
                self.assertEqual(code, 0 if mode == "dirty" else 1)
                self.assertEqual(report["cases"][0]["status"], "observed")
                self.assertEqual(env.app.documents, [])
                self.assertEqual(sum(scene.access_calls for scene in env.app.scenes), 0)
                if mode == "readonly":
                    self.assertEqual(env.diagnostic_calls, 1)

    def test_s1_original_baseexception_survives_cleanup_baseexception(self):
        with Environment().installed() as env:
            primary = KeyboardInterrupt("original S1 baseline diagnostic")

            def interrupt():
                if env.diagnostic_calls == 2:
                    env.app.close_error = SystemExit("secondary CloseDoc")
                    trip(primary)

            env.after_diagnostic = interrupt
            code, report, captures = env.run_driver()
            self.assertEqual(code, 1)
            self.assertEqual(report["cases"][0]["errors"], [])
            self.assertEqual(captures[0]["primary_failure"]["type"], "KeyboardInterrupt")
            self.assertEqual(captures[0]["primary_failure"]["case"], "s1")
            self.assertEqual(len(env.app.documents), 2)
            self.assertIn("after_diagnostic_including_generation", report["cases"][1]["active_sketch"])
            body_exit = next(row for row in env.telemetry.exit_errors if row[0] == "build")
            self.assertIs(body_exit[2], primary)
            self.assertTrue(any(frame.f_code is trip.__code__ for frame, _ in traceback.walk_tb(body_exit[3])))

    def test_s1_baseline_positive_ink_stops_without_claiming_flank_recovery(self):
        with Environment().installed() as env:
            key = "after_generation.thread[0].ICThread.lines.count"
            def diagnostic(feature):
                value = recorded_diagnostic("sm_positive" if feature == "BracketMountingTaps" else "b0")
                if feature == "LeverTap":
                    value["reads"][key] = 1
                    value["reads"]["after_generation.thread[0].ICThread.lines[0]"] = [0, 1, 2]
                return value
            env.diagnostic_result = diagnostic
            code, report, _ = env.run_driver()
            self.assertEqual(code, 0)
            b0 = report["cases"][1]
            self.assertEqual(b0["thread_ink"]["state"], "PRESENT")
            self.assertEqual(b0["thread_ink"]["positive_count_fields"], [key])
            self.assertTrue(b0["thread_ink"]["recommendation"].startswith("STOP;"))
            self.assertEqual(b0["diagnostic"]["reads"]["after_generation.thread[0].ICThread.lines[0]"], [0, 1, 2])
            self.assertEqual(env.diagnostic_calls, 2)
            self.assertEqual(report["native_ship"], "NOT_EVALUATED")

    def test_diagnostic_reader_failure_is_not_reported_as_zero_ink(self):
        with Environment().installed() as env:
            def diagnostic(feature):
                value = recorded_diagnostic("sm_positive" if feature == "BracketMountingTaps" else "b0")
                if feature == "LeverTap":
                    value["reads"] = {}
                    value["errors"] = {"after_generation.thread[0].ICThread.lines.count": "reader failed"}
                return value
            env.diagnostic_result = diagnostic
            code, report, _ = env.run_driver()
            self.assertEqual(code, 0)
            self.assertEqual(report["status"], "observed_with_diagnostic_read_errors")
            b0 = report["cases"][1]
            self.assertEqual(b0["thread_ink"]["state"], "UNAVAILABLE")
            self.assertEqual(b0["diagnostic"]["reads"], {})
            self.assertEqual(len(b0["diagnostic"]["errors"]), 1)



class S1Behavior(unittest.TestCase):
    def test_actual_recorded_positive_and_complete_zero_are_distinct(self):
        with Environment().installed() as env:
            positive = env.driver.thread_ink_summary(recorded_diagnostic("sm_positive"))
            zero = env.driver.thread_ink_summary(recorded_diagnostic("b0"))
            self.assertEqual(positive["state"], "PRESENT")
            self.assertTrue(positive["complete"])
            self.assertEqual(len(positive["positive_count_fields"]), 8)
            self.assertEqual(len(positive["positive_payload_fields"]), 28)
            self.assertEqual(zero["state"], "OBSERVED_ZERO")
            self.assertTrue(zero["complete"])
            self.assertEqual(zero["positive_count_fields"], [])

    def test_each_actual_zero_count_requires_an_actual_nonnegative_integer(self):
        original = recorded_diagnostic("b0")
        fields = [key for key in original["reads"] if key.endswith((".lines.count", ".polylines.count", ".arcs.count"))]
        self.assertEqual(len(fields), 12)
        with Environment().installed() as env:
            for key in fields:
                for value in (None, True, False, -1, 0.0, "0", DEFAULT):
                    with self.subTest(key=key, value_type=type(value).__name__):
                        diagnostic = copy.deepcopy(original)
                        if value is DEFAULT:
                            del diagnostic["reads"][key]
                        else:
                            diagnostic["reads"][key] = value
                        self.assertEqual(env.driver.thread_ink_summary(diagnostic)["state"], "UNAVAILABLE")

    def test_every_thread_annotation_display_and_list_witness_is_required(self):
        original = recorded_diagnostic("b0")
        fields = [key for key in original["reads"]
                  if key.endswith((".threads", ".thread_count", ".annotation", ".display"))
                  or key in ("before_generation.thread[0]", "after_generation.thread[0]")]
        with Environment().installed() as env:
            for key in fields:
                diagnostic = copy.deepcopy(original)
                del diagnostic["reads"][key]
                with self.subTest(key=key):
                    self.assertEqual(env.driver.thread_ink_summary(diagnostic)["state"], "UNAVAILABLE")
            for key in ("before_generation.thread_count", "after_generation.thread_count"):
                for value in (None, False, True, -1, 0, 1.0):
                    diagnostic = copy.deepcopy(original)
                    diagnostic["reads"][key] = value
                    self.assertEqual(env.driver.thread_ink_summary(diagnostic)["state"], "UNAVAILABLE")
            for error_key in ("before_generation.thread[0].ICThread.lines.count", "source.definition"):
                diagnostic = copy.deepcopy(original)
                diagnostic["errors"][error_key] = "actual reader failure"
                self.assertEqual(env.driver.thread_ink_summary(diagnostic)["state"], "UNAVAILABLE")

    def test_positive_count_stops_access_even_with_incomplete_evidence(self):
        with Environment().installed() as env:
            env.app.source_mode = "cosmetic"
            original = env.diagnostic_result
            def diagnostic(feature):
                value = original(feature)
                if feature == "LeverTap":
                    value["reads"]["before_generation.thread[0].ICThread.lines.count"] = 1
                    del value["reads"]["before_generation.thread[0].annotation"]
                return value
            env.diagnostic_result = diagnostic
            code, report, _ = env.run_driver()
            self.assertEqual(code, 0)
            self.assertEqual(report["cases"][1]["s1"]["state"], "STOP_BASELINE_PRIMITIVES")
            self.assertEqual(env.app.scenes[-1].access_calls, 0)
            self.assertEqual(env.app.scenes[-1].edge_reads, 0)

    def test_wizard_only_is_unavailable_without_selected_edge_substitution(self):
        with Environment().installed() as env:
            code, report, _ = env.run_driver()
            self.assertEqual(code, 0)
            evidence = report["cases"][1]["s1"]
            self.assertTrue(evidence["phases"]["before"]["complete"])
            self.assertEqual(evidence["cosmetic_candidate_count"], 0)
            self.assertEqual(evidence["intended_wizard_count"], 1)
            self.assertEqual(evidence["state"], "UNAVAILABLE")
            self.assertEqual(evidence["access_calls"], 0)
            self.assertEqual(env.app.scenes[-1].edge_reads, 0)

    def test_complete_access_release_reacquires_all_phases_and_discards_only_copies(self):
        with Environment().installed() as env:
            env.app.source_mode = "cosmetic"
            code, report, captures = env.run_driver()
            self.assertEqual(code, 0)
            sm, s1 = report["cases"]
            scene = env.app.scenes[-1]
            self.assertEqual(scene.events, ["access", "release"])
            self.assertEqual((scene.access_calls, scene.release_calls, scene.edge_reads), (1, 1, 1))
            evidence = s1["s1"]
            self.assertEqual(evidence["state"], "ACCESS_READ_RELEASE_OBSERVED")
            self.assertTrue(evidence["clean_comparison"])
            self.assertTrue(evidence["roll_forward_witness"])
            self.assertEqual(evidence["causal_conclusion"], "NOT_ESTABLISHED")
            self.assertTrue(evidence["selected_edge"]["wizard_face_association"])
            self.assertEqual(evidence["selected_edge"]["trimmed_circle"]["state"], "FULL_TRIMMED_CIRCLE")
            self.assertEqual(set(evidence["phases"]), {"before", "accessed", "after"})
            self.assertFalse(evidence["phases"]["accessed"]["all_features_rolled_forward"])
            self.assertEqual(set(phase for _, phase in scene.definition_reads), {"before", "accessed", "after"})
            self.assertEqual([row[2] for row in env.app.open_calls], [3, 3, 1, 3])
            self.assertNotEqual(sm["copy_root"], s1["copy_root"])
            for case in (sm, s1):
                for kind in ("part", "drawing"):
                    self.assertEqual(case["reads"][f"copy_before.{kind}"], case["reads"][f"copy_after.{kind}"])
                    self.assertEqual(case["reads"][f"staged.{kind}"], case["reads"][f"final.{kind}"])
                self.assertTrue(case["reads"]["final.inventory_empty"])
                self.assertEqual(case["reads"]["final.ActiveDoc_state"], "NULL")
                for row in case["opens"]:
                    self.assertEqual(Path(row["path"]).parent, Path(case["copy_root"]))
                    self.assertEqual(Path(row["path"]).name, Path(case["contract"][row["kind"]]["path"]).name)
            self.assertEqual(env.diagnostic_calls, 3)
            self.assertEqual(env.app.documents, [])
            self.assertEqual(captures, [])

    def test_incomplete_or_ambiguous_source_never_selects_one_good_candidate(self):
        for mode in ("second_cosmetic", "type_error", "definition_error", "owner_error",
                     "null_definition", "wrong_typed_definition", "unowned_owner", "scalar_error", "cycle", "subfeature_cycle"):
            with self.subTest(mode=mode), Environment().installed() as env:
                env.app.source_mode = "cosmetic"
                def prepare(scene):
                    if mode == "second_cosmetic":
                        scene.cosmetic.next = SourceFeature(scene, "Other", "CosmeticThread", SourceDefinition(scene, True))
                    elif mode == "null_definition":
                        scene.cosmetic.definition = None
                    elif mode == "wrong_typed_definition":
                        scene.cosmetic.definition = scene.wizard.definition
                    elif mode == "unowned_owner":
                        scene.cosmetic.owner = NativeObject()
                    elif mode == "scalar_error":
                        scene.wizard.definition.values["ThreadDiameter"] = ProbeError("scalar unavailable")
                    elif mode == "cycle":
                        scene.later.next = scene.wizard
                    elif mode == "subfeature_cycle":
                        scene.cosmetic.child = scene.wizard
                    else:
                        setattr(scene.later, mode, ProbeError("independent candidate inventory failed"))
                env.app.prepare_scene = prepare
                _, report, _ = env.run_driver()
                evidence = report["cases"][1]["s1"]
                self.assertEqual(evidence["state"], "UNAVAILABLE")
                self.assertEqual(evidence["access_calls"], 0)
                self.assertEqual(env.app.scenes[-1].release_calls, 0)
                self.assertTrue(evidence["phases"]["before"]["features"][0]["scalars"])

    def test_native_null_owner_is_observed_not_fabricated_failure(self):
        with Environment().installed() as env:
            env.app.source_mode = "cosmetic"
            env.app.prepare_scene = lambda scene: setattr(scene.cosmetic, "owner", None)
            code, report, _ = env.run_driver()
            self.assertEqual(code, 0)
            evidence = report["cases"][1]["s1"]
            self.assertEqual(evidence["access_calls"], 1)
            self.assertEqual(evidence["phases"]["before"]["features"][1]["owner_state"], "NULL")
            self.assertTrue(evidence["selected_edge"]["wizard_face_association"])

    def test_access_requires_actual_true_and_never_blindly_releases_or_retries(self):
        for value in (False, None, 1, "true", ProbeError("access state unknown")):
            with self.subTest(value_type=type(value).__name__), Environment().installed() as env:
                env.app.source_mode = "cosmetic"
                env.app.prepare_scene = lambda scene: setattr(scene, "access_result", value)
                _, report, _ = env.run_driver()
                evidence = report["cases"][1]["s1"]
                self.assertEqual(evidence["state"], "UNAVAILABLE")
                self.assertEqual((evidence["access_calls"], evidence["release_calls"]), (1, 0))
                self.assertEqual(env.app.scenes[-1].edge_reads, 0)
                self.assertIn("after", evidence["phases"])

    def test_selected_reader_primary_survives_one_release_failure_and_dirty_cleanup(self):
        with Environment().installed() as env:
            env.app.source_mode = "cosmetic"
            primary = BrokenText()
            def prepare(scene):
                scene.edge_error = primary
                scene.release_error = ProbeError("release secondary")
            env.app.prepare_scene = prepare
            code, report, captures = env.run_driver()
            self.assertEqual(code, 1)
            evidence = report["cases"][1]["s1"]
            self.assertEqual((evidence["access_calls"], evidence["release_calls"]), (1, 1))
            self.assertFalse(evidence["roll_forward_witness"])
            self.assertFalse(evidence["clean_comparison"])
            self.assertIn("after", evidence["phases"])
            self.assertEqual(report["primary_failure"]["type"], "BrokenText")
            self.assertIn("selected_edge", report["primary_failure"]["operation"])
            self.assertEqual(env.app.documents, [])
            self.assertTrue(captures[0]["primary_traceback"]["available"])
            root_exit = next(row for row in env.telemetry.exit_errors if row[0] == "build")
            self.assertIs(root_exit[2], primary)

    def test_persistent_status_or_native_identity_cannot_be_replaced_by_same_bytes(self):
        for mode in ("bool_status", "deleted", "null", "same_geometry_other_identity"):
            with self.subTest(mode=mode), Environment().installed() as env:
                env.app.source_mode = "cosmetic"
                def prepare(scene):
                    if mode == "bool_status":
                        scene.resolve_status = False
                    elif mode == "deleted":
                        scene.resolve_status = 4
                    elif mode == "null":
                        scene.resolve_override = lambda _entity: None
                    else:
                        scene.resolve_override = lambda _entity: NativeObject()
                env.app.prepare_scene = prepare
                code, report, _ = env.run_driver()
                self.assertEqual(code, 1)
                self.assertEqual(report["cases"][1]["s1"]["access_calls"], 0)
                self.assertEqual(env.app.documents, [])

    def test_arc_failed_evaluation_and_foreign_body_never_establish_clean_comparison(self):
        for mode in ("arc", "bad_status", "foreign_body", "domain_false", "domain_bool_range", "geometry_drift"):
            with self.subTest(mode=mode), Environment().installed() as env:
                env.app.source_mode = "cosmetic"
                def prepare(scene):
                    if mode == "arc":
                        scene.span = math.pi
                    elif mode == "bad_status":
                        scene.eval_status = 0
                    elif mode == "foreign_body":
                        scene.edge_body = NativeObject()
                    elif mode == "domain_false":
                        scene.domain = (False, 0.0, math.tau, True, True)
                    elif mode == "domain_bool_range":
                        scene.domain = (True, False, math.tau, True, True)
                    else:
                        scene.on_release = lambda: setattr(scene, "radius", 0.004)
                env.app.prepare_scene = prepare
                _, report, _ = env.run_driver()
                evidence = report["cases"][1]["s1"]
                failed_operation = mode in ("bad_status", "domain_false", "domain_bool_range")
                self.assertEqual(evidence["release_calls"], 0 if failed_operation else 1)
                self.assertFalse(evidence["clean_comparison"])
                if failed_operation:
                    self.assertFalse(evidence["phases"]["before"]["complete"])
                    self.assertFalse(evidence["display_generation_permitted"])
                self.assertEqual(evidence["causal_conclusion"], "NOT_ESTABLISHED")
                if mode == "arc":
                    self.assertEqual(evidence["selected_edge"]["trimmed_circle"]["state"], "NOT_FULL_OR_CONTRADICTORY")
                if mode == "geometry_drift":
                    self.assertFalse(evidence["selected_geometry_unchanged"])

    def test_unknown_dirty_foreign_document_or_user_control_strands_s1_without_close(self):
        for mode in ("dirty_none", "dirty_int", "foreign", "user_control", "identity"):
            with self.subTest(mode=mode), Environment().installed() as env:
                env.app.source_mode = "cosmetic"
                def prepare(scene):
                    def after_release():
                        if mode == "dirty_none":
                            scene.document.dirty = None
                        elif mode == "dirty_int":
                            scene.document.dirty = 1
                        elif mode == "foreign":
                            env.app.documents.append(Document("C:/foreign/hidden.SLDPRT", 1))
                        elif mode == "identity":
                            env.app.identity_override = -1
                        else:
                            env.app.control = False
                    scene.on_release = after_release
                env.app.prepare_scene = prepare
                code, report, _ = env.run_driver()
                self.assertEqual(code, 1)
                self.assertEqual(env.app.close_calls, ["sm-summing-lever.SLDDRW", "sm-summing-lever.SLDPRT"])
                self.assertTrue(all(row["status"] == "stranded_owned" for row in report["cases"][1]["closures"]))

    def test_copy_disk_drift_is_reported_after_cleanup_without_adopting_native_bytes(self):
        with Environment().installed() as env:
            env.app.source_mode = "cosmetic"
            env.app.prepare_scene = lambda scene: setattr(
                scene, "on_release", lambda: Path(scene.document.path).write_bytes(b"changed copy on disk"),
            )
            code, report, _ = env.run_driver()
            self.assertEqual(code, 1)
            s1 = report["cases"][1]
            self.assertEqual(s1["reads"]["staged.part"], s1["reads"]["final.part"])
            self.assertNotEqual(s1["reads"]["copy_before.part"], s1["reads"]["copy_after.part"])
            self.assertEqual(env.app.documents, [])


    def test_every_s1_view_reference_not_only_target_section_must_be_owned(self):
        with Environment().installed() as env:
            env.app.source_mode = "cosmetic"
            foreign = Document("C:/foreign/another.SLDPRT", 1)
            def prepare(doc):
                if doc.kind == 3 and "mg-magnifying-bracket" in doc.path:
                    doc.extra_views.append(View(foreign, doc.sheet_name, doc.section_label, base=True))
            env.app.after_open = prepare
            code, report, _ = env.run_driver()
            self.assertEqual(code, 1)
            self.assertEqual(env.app.scenes[-1].access_calls, 0)
            self.assertEqual(env.diagnostic_calls, 1)
            self.assertEqual(env.app.documents, [])
            self.assertTrue(any(".reference" in row["operation"] for row in report["cases"][1]["errors"]))

    def test_nonzero_or_unknown_open_warning_never_reaches_access(self):
        for warning in (1, None, False, "0"):
            with self.subTest(warning=warning), Environment().installed() as env:
                env.app.source_mode = "cosmetic"
                env.app.open_warning = warning
                code, _, _ = env.run_driver()
                self.assertEqual(code, 1)
                self.assertEqual(env.app.scenes[-1].access_calls, 0)
                self.assertEqual(env.app.documents, [])

    def test_source_open_mode_is_reread_after_baseline_before_access(self):
        with Environment().installed() as env:
            env.app.source_mode = "cosmetic"
            def change_mode():
                if env.diagnostic_calls == 2:
                    env.app.documents[0].readonly = True
            env.after_diagnostic = change_mode
            code, report, _ = env.run_driver()
            self.assertEqual(code, 1)
            s1 = report["cases"][1]
            self.assertIs(s1["reads"]["before_access.part.IsOpenedReadOnly"], True)
            self.assertIs(s1["reads"]["before_access.drawing.IsOpenedReadOnly"], True)
            self.assertEqual(s1["s1"]["access_calls"], 0)
            self.assertEqual(env.app.documents, [])

    def test_definitions_are_reacquired_not_read_through_stale_access_objects(self):
        with Environment().installed() as env:
            env.app.source_mode = "cosmetic"
            def prepare(scene):
                def release():
                    old_wizard, old_cosmetic = scene.wizard.definition, scene.cosmetic.definition
                    scene.wizard.definition = SourceDefinition(scene)
                    scene.cosmetic.definition = SourceDefinition(scene, True)
                    for old in (old_wizard, old_cosmetic):
                        old.values = {name: ProbeError("stale definition read") for name in old.values}
                scene.on_release = release
            env.app.prepare_scene = prepare
            code, report, _ = env.run_driver()
            self.assertEqual(code, 0)
            self.assertTrue(report["cases"][1]["s1"]["clean_comparison"])
            self.assertEqual(env.app.scenes[-1].edge_reads, 1)

    def test_native_body_or_definition_drift_blocks_clean_comparison(self):
        for mode in ("body", "definition"):
            with self.subTest(mode=mode), Environment().installed() as env:
                env.app.source_mode = "cosmetic"
                def prepare(scene):
                    def release():
                        if mode == "body":
                            scene.body = scene.edge_body = NativeObject()
                        else:
                            scene.wizard.definition.values["ThreadDiameter"] = 0.008
                    scene.on_release = release
                env.app.prepare_scene = prepare
                _, report, _ = env.run_driver()
                self.assertFalse(report["cases"][1]["s1"]["clean_comparison"])
                self.assertEqual(env.app.scenes[-1].events, ["access", "release"])

    def test_primitives_after_single_access_stop_without_flank_or_cause_claim(self):
        with Environment().installed() as env:
            env.app.source_mode = "cosmetic"
            original = env.diagnostic_result
            def diagnostic(feature):
                value = original(feature)
                if env.diagnostic_calls == 3:
                    value["reads"]["after_generation.thread[0].ICThread.lines.count"] = 1
                return value
            env.diagnostic_result = diagnostic
            code, report, _ = env.run_driver()
            self.assertEqual(code, 0)
            s1 = report["cases"][1]
            self.assertEqual(s1["after_access_thread_ink"]["state"], "PRESENT")
            self.assertIn("do not establish recovered flanks", s1["s1"]["stop"])
            self.assertEqual(s1["s1"]["causal_conclusion"], "NOT_ESTABLISHED")
            self.assertEqual(env.app.scenes[-1].events, ["access", "release"])
            self.assertEqual(env.diagnostic_calls, 3)


    def test_s1_rechecks_user_control_before_second_dirty_copy_close(self):
        with Environment().installed() as env:
            env.app.source_mode = "cosmetic"
            original_close = env.app.CloseDoc
            def close(title):
                original_close(title)
                if title == "mg-magnifying-bracket-native-thread.SLDDRW":
                    env.app.control = False
            with patch.object(env.app, "CloseDoc", close):
                code, report, _ = env.run_driver()
            self.assertEqual(code, 1)
            self.assertEqual(env.app.close_calls, [
                "sm-summing-lever.SLDDRW", "sm-summing-lever.SLDPRT",
                "mg-magnifying-bracket-native-thread.SLDDRW",
            ])
            self.assertEqual(report["cases"][1]["closures"][1]["status"], "stranded_owned")
            self.assertEqual(len(env.app.documents), 1)
            self.assertIs(env.app.documents[0].dirty, True)

    def test_void_release_is_not_a_boolean_success_contract_or_retry_trigger(self):
        with Environment().installed() as env:
            env.app.source_mode = "cosmetic"
            def prepare(scene):
                original_release = scene.cosmetic.definition.ReleaseSelectionAccess
                def bad_void():
                    original_release()
                    return False
                scene.cosmetic.definition.ReleaseSelectionAccess = bad_void
            env.app.prepare_scene = prepare
            code, report, _ = env.run_driver()
            self.assertEqual(code, 1)
            evidence = report["cases"][1]["s1"]
            self.assertFalse(evidence["release_returned"])
            self.assertFalse(evidence["clean_comparison"])
            self.assertEqual(env.app.scenes[-1].events, ["access", "release"])
            self.assertEqual(env.app.documents, [])

    def test_after_access_reader_error_remains_unavailable_not_observed_zero(self):
        with Environment().installed() as env:
            env.app.source_mode = "cosmetic"
            original = env.diagnostic_result
            def diagnostic(feature):
                value = original(feature)
                if env.diagnostic_calls == 3:
                    value["errors"]["after_generation.thread[0].ICThread.lines.count"] = "reader failed"
                return value
            env.diagnostic_result = diagnostic
            code, report, _ = env.run_driver()
            self.assertEqual(code, 0)
            self.assertEqual(report["status"], "observed_with_diagnostic_read_errors")
            self.assertEqual(report["cases"][1]["after_access_thread_ink"]["state"], "UNAVAILABLE")
            self.assertFalse(report["cases"][1]["s1"]["clean_comparison"])
            self.assertEqual(env.app.scenes[-1].events, ["access", "release"])


class S1SafetyRepairs(unittest.TestCase):
    def test_redirected_copy_ancestor_refuses_before_any_creation_or_open(self):
        # Simulate resolve() through a symlink/junction without creating one or
        # needing Windows link privileges. The write guard records ATTEMPTS.
        for ancestor in ("cad/out/diagnostic-copies",
                         "cad/out/diagnostic-copies/mg-saved-thread-control"):
            with self.subTest(ancestor=ancestor), Environment().installed() as env:
                env.path_redirect = ancestor
                code, report, _ = env.run_driver()
                self.assertEqual(code, 1)
                self.assertIn("uncertified output path", report["primary_failure"]["message"])
                self.assertEqual(env.copy_fs_attempts, [])
                self.assertEqual(env.cache_calls, [])
                self.assertEqual(env.blob_calls, [])
                self.assertEqual(env.app.open_calls, [])
                self.assertEqual(env.app.close_calls, [])
                self.assertEqual(env.app.documents, [])
                self.assertEqual(report["cases"][1]["status"], "not_started")

    def test_copy_path_is_recertified_at_direct_ownership_and_cleanup(self):
        for boundary in ("direct_open", "cleanup"):
            with self.subTest(boundary=boundary), Environment().installed() as env:
                env.app.source_mode = "cosmetic"
                def redirect():
                    env.path_redirect = "cad/out/diagnostic-copies/mg-saved-thread-control"
                if boundary == "direct_open":
                    def after_open(doc):
                        if doc.kind == 1 and "mg-magnifying-bracket" in doc.path:
                            redirect()
                    env.app.after_open = after_open
                else:
                    env.app.prepare_scene = lambda scene: setattr(scene, "on_release", redirect)
                code, report, _ = env.run_driver()
                self.assertEqual(code, 1)
                self.assertEqual(env.app.close_calls, ["sm-summing-lever.SLDDRW", "sm-summing-lever.SLDPRT"])
                s1 = report["cases"][1]
                if boundary == "direct_open":
                    self.assertEqual(len(env.app.documents), 1)
                    self.assertEqual(s1["opens"][0]["ownership_state"], "UNAVAILABLE_STRANDED")
                    self.assertEqual(env.app.scenes[-1].access_calls, 0)
                else:
                    self.assertEqual(len(env.app.documents), 2)
                    self.assertTrue(all(row["status"] == "stranded_owned" for row in s1["closures"]))

    def test_unconfirmed_access_release_or_rollforward_never_generates_after_display(self):
        for mode in ("access_false", "access_unknown", "access_error", "release_error",
                     "release_nonvoid", "rolled_back", "rollback_unknown"):
            with self.subTest(mode=mode), Environment().installed() as env:
                env.app.source_mode = "cosmetic"
                def prepare(scene):
                    if mode == "access_false":
                        scene.access_result = False
                    elif mode == "access_unknown":
                        scene.access_result = 1
                    elif mode == "access_error":
                        scene.access_result = ProbeError("access failed")
                    elif mode == "release_error":
                        scene.release_error = ProbeError("release failed")
                    elif mode == "release_nonvoid":
                        release = scene.cosmetic.definition.ReleaseSelectionAccess
                        def bad_void():
                            release()
                            return False
                        scene.cosmetic.definition.ReleaseSelectionAccess = bad_void
                    elif mode == "rolled_back":
                        scene.on_release = lambda: setattr(scene, "accessed", True)
                    else:
                        scene.on_release = lambda: setattr(scene.later, "IsRolledBack", lambda: None)
                env.app.prepare_scene = prepare
                _, report, _ = env.run_driver()
                source = report["cases"][1]["s1"]
                self.assertFalse(source["display_generation_permitted"])
                self.assertFalse(source["clean_comparison"])
                self.assertIn("after", source["phases"])
                self.assertNotIn("after_access_diagnostic", report["cases"][1])
                self.assertEqual(env.diagnostic_calls, 2)
                self.assertEqual([Path(path).suffix for path in env.app.activation_calls],
                                 [".SLDDRW", ".SLDDRW", ".SLDPRT"])
                self.assertEqual(env.app.scenes[-1].release_calls, 0 if mode.startswith("access_") else 1)
                self.assertEqual(env.app.documents, [])

    def test_escaping_access_body_baseexception_precedes_release_failure(self):
        for primary in (KeyboardInterrupt("original interrupt"), SystemExit("original exit")):
            with self.subTest(primary=type(primary).__name__), Environment().installed() as env:
                env.app.source_mode = "cosmetic"
                env.app.prepare_scene = lambda scene: setattr(scene, "release_error", ProbeError("secondary release"))
                original = env.driver.trimmed_circle_summary
                interrupted = False
                def classify(reads):
                    nonlocal interrupted
                    if env.app.scenes[-1].accessed and not interrupted:
                        interrupted = True
                        trip(primary)  # Outside source_intervention.read(), after actual access True.
                    return original(reads)
                with patch.object(env.driver, "trimmed_circle_summary", classify):
                    code, report, captures = env.run_driver()
                self.assertEqual(code, 1)
                self.assertTrue(interrupted)
                self.assertEqual(report["primary_failure"]["operation"], "s1.access_body")
                self.assertEqual(report["primary_failure"]["type"], type(primary).__name__)
                source = report["cases"][1]["s1"]
                self.assertEqual(source["errors"][0]["operation"], "s1.access_body")
                self.assertTrue(any(row["operation"] == "s1.ReleaseSelectionAccess" for row in source["errors"][1:]))
                self.assertEqual(env.app.scenes[-1].events, ["access", "release"])
                self.assertFalse(source["display_generation_permitted"])
                self.assertEqual(env.diagnostic_calls, 2)
                root_exit = next(row for row in env.telemetry.exit_errors if row[0] == "build")
                self.assertIs(root_exit[2], primary)
                self.assertTrue(any(frame.f_code is trip.__code__ for frame, _ in traceback.walk_tb(root_exit[3])))
                self.assertTrue(captures[0]["primary_traceback"]["available"])
                self.assertEqual(env.app.documents, [])

    def test_positive_sm_counts_without_successful_payloads_cannot_admit_s1(self):
        for mode in ("reader_errors", "null", "empty", "invalid_value", "stale_errored_rows"):
            with self.subTest(mode=mode), Environment().installed() as env:
                diagnostic = recorded_diagnostic("sm_positive")
                fields = env.driver.thread_ink_summary(diagnostic)["positive_payload_fields"]
                self.assertEqual(len(fields), 28)
                for key in fields:
                    if mode == "reader_errors":
                        diagnostic["reads"].pop(key)
                        diagnostic["errors"][key] = "native row reader failed"
                    elif mode == "stale_errored_rows":
                        diagnostic["errors"][key] = "row read not successful"
                    else:
                        diagnostic["reads"][key] = {"null": None, "empty": [], "invalid_value": [False]}[mode]
                summary = env.driver.thread_ink_summary(diagnostic)
                self.assertEqual(summary["state"], "PRESENT")  # Counts still stop any intervention.
                self.assertEqual(len(summary["positive_count_fields"]), 8)
                self.assertEqual(summary["positive_payload_fields"], [])
                env.diagnostic_result = lambda _feature: diagnostic
                code, report, _ = env.run_driver()
                self.assertEqual(code, 1)
                self.assertEqual(env.diagnostic_calls, 1)
                self.assertEqual(report["cases"][1]["status"], "not_started")
                self.assertEqual(len(env.app.open_calls), 2)
                self.assertEqual(env.blob_calls, [])
                self.assertEqual(env.app.documents, [])

    def test_successful_sm_payloads_admit_despite_unrelated_optional_reader_error(self):
        with Environment().installed() as env:
            env.app.source_mode = "cosmetic"
            original = env.diagnostic_result
            def diagnostic(feature):
                value = original(feature)
                if feature == "BracketMountingTaps":
                    value["errors"]["source.CosmeticThreadType"] = "optional source reader unavailable"
                return value
            env.diagnostic_result = diagnostic
            code, report, _ = env.run_driver()
            self.assertEqual(code, 0)
            self.assertEqual(len(report["cases"][0]["thread_ink"]["positive_payload_fields"]), 28)
            self.assertEqual(report["cases"][0]["status"], "observed_with_diagnostic_read_errors")
            self.assertEqual(env.app.scenes[-1].events, ["access", "release"])
            self.assertEqual(env.diagnostic_calls, 3)

    def test_distinct_nonselected_line_requires_success_not_circle_classification(self):
        for phase in ("before", "after"):
            for mode in ("healthy", "bad_status", "domain_false", "domain_shape", "domain_flags", "evaluation_shape"):
                with self.subTest(phase=phase, mode=mode), Environment().installed() as env:
                    env.app.source_mode = "cosmetic"
                    def prepare(scene):
                        line = SourceLineEdge(scene)
                        scene.edges.append(line)
                        def configure():
                            if mode == "bad_status":
                                line.eval_status = 0
                            elif mode == "domain_false":
                                line.domain = (False, 0.0, 1.0, False, False)
                            elif mode == "domain_shape":
                                line.domain = (True, 0.0, 1.0)
                            elif mode == "domain_flags":
                                line.domain = (True, 0.0, 1.0, 0, False)
                            elif mode == "evaluation_shape":
                                line.Evaluate2 = lambda _parameter, _derivatives: (0.0, 0.0, 0.0)
                        if phase == "before":
                            configure()
                        else:
                            scene.on_release = configure
                    env.app.prepare_scene = prepare
                    code, report, _ = env.run_driver()
                    source = report["cases"][1]["s1"]
                    snapshot = source["phases"][phase]
                    self.assertEqual(len(snapshot["edges"]), 2)
                    self.assertEqual(snapshot["edges"][0]["trimmed_circle"]["state"], "FULL_TRIMMED_CIRCLE")
                    self.assertTrue(snapshot["edges"][0]["operations_complete"])
                    self.assertIs(snapshot["edges"][1]["reads"]["circle"], False)
                    self.assertEqual(snapshot["edges"][1]["operations_complete"], mode == "healthy")
                    if mode == "healthy":
                        self.assertEqual(code, 0)
                        self.assertTrue(source["clean_comparison"])
                        self.assertTrue(source["display_generation_permitted"])
                        self.assertEqual(env.diagnostic_calls, 3)
                    else:
                        self.assertEqual(code, 1)
                        self.assertFalse(snapshot["complete"])
                        self.assertFalse(source["clean_comparison"])
                        self.assertFalse(source["display_generation_permitted"])
                        self.assertEqual(source["release_calls"], 0 if phase == "before" else 1)
                        self.assertEqual(env.diagnostic_calls, 2)
                        self.assertTrue(any("edge[1]" in row["operation"] for row in source["errors"]))
                    self.assertEqual(env.app.documents, [])

    def test_open_warnings_refuse_at_boundary_including_sm_positive_and_wizard_only(self):
        for route in ("sm", "s1_cosmetic", "s1_wizard", "s1_positive"):
            for kind in (1, 3):
                for warning in (1, None, False, "0"):
                    with self.subTest(route=route, kind=kind, warning=warning), Environment().installed() as env:
                        index = 0 if route == "sm" else 1
                        case = "sm_positive" if index == 0 else "s1"
                        env.app.source_mode = "wizard_only" if route == "s1_wizard" else "cosmetic"
                        env.app.open_warnings[(case, kind)] = warning
                        if route == "s1_positive":
                            env.diagnostic_result = lambda _feature: recorded_diagnostic("sm_positive")
                        code, report, _ = env.run_driver()
                        self.assertEqual(code, 1)
                        self.assertEqual(env.diagnostic_calls, index)
                        failed = report["cases"][index]
                        self.assertEqual(failed["opens"][-1]["warnings"], warning)
                        self.assertIs(type(failed["opens"][-1]["warnings"]), type(warning))
                        self.assertEqual(failed["opens"][-1]["ownership_state"], "CERTIFIED_COPY")
                        self.assertTrue(failed["opens"][-1]["retained_owned"])
                        self.assertIsNone(failed["diagnostic"])
                        self.assertEqual(sum(scene.access_calls for scene in env.app.scenes), 0)
                        self.assertEqual(len(env.app.open_calls), index * 2 + (1 if kind == 1 else 2))
                        self.assertEqual(len(env.app.close_calls), len(env.app.open_calls))
                        self.assertEqual(env.app.documents, [])

    def test_warning_does_not_authorize_close_of_unknown_direct_result(self):
        for index in (0, 1):
            with self.subTest(case=index), Environment().installed() as env:
                case = "sm_positive" if index == 0 else "s1"
                env.app.open_warnings[(case, 1)] = 1
                def unknown_owner(doc):
                    if doc.kind == 1 and ("mg-magnifying-bracket" in doc.path) == bool(index):
                        doc.path = "C:/foreign/uncertified.SLDPRT"
                env.app.after_open = unknown_owner
                code, report, _ = env.run_driver()
                self.assertEqual(code, 1)
                failed = report["cases"][index]
                self.assertEqual(failed["opens"][-1]["warnings"], 1)
                self.assertEqual(failed["opens"][-1]["ownership_state"], "UNAVAILABLE_STRANDED")
                self.assertFalse(failed["opens"][-1].get("retained_owned", False))
                self.assertEqual(len(env.app.close_calls), index * 2)
                self.assertEqual(len(env.app.documents), 1)
                self.assertEqual(env.diagnostic_calls, index)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--driver", type=Path, default=DRIVER_PATH)
    parser.add_argument("--helper", type=Path, default=HELPER_PATH)
    args, unittest_args = parser.parse_known_args()
    DRIVER_PATH, HELPER_PATH = args.driver.resolve(strict=True), args.helper.resolve(strict=True)
    unittest.main(argv=[sys.argv[0], *unittest_args])
