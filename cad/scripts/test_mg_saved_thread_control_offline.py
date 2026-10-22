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
SOURCE_FIXTURE_PATH = Path(__file__).parent / "fixtures/mg_saved_thread_control_a189_native.json"


def recorded_diagnostic(case):
    return json.loads(FIXTURE_PATH.read_text(encoding="utf-8"))["diagnostics"][case]


def recorded_source():
    return json.loads(SOURCE_FIXTURE_PATH.read_text(encoding="utf-8"))
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
    prefixes = ("pythoncom", "pywintypes", "win32", "comtypes", "solidworks_mcp", "azure", "temporalio", "_artifact_cache", "_telemetry", "_watchdog", "_com", "_seat_forensics", "draw_mg_magnifying_bracket")

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
    def __init__(self, label, view):
        self.label, self.view = label, view
        self.native_identity = object()
        self.cut_only = True

    def GetLabel(self):
        return self.label

    def GetDisplayOnlySurfaceCut(self):
        return self.cut_only

    def SetDisplayOnlySurfaceCut(self, value):
        if type(value) is not bool:
            raise AssertionError("BOOL input required")
        self.view.document.app.mutators.append(("cut", value, self.view.document.path))
        self.view.document.app.on_write(self.view, "cut")
        if not self.view.document.app.refuse_write:
            self.cut_only = value
            self.view.document.dirty = True
        return None


class View:
    def __init__(self, part, sheet_name, section_label, *, sheet=False, base=False, document=None):
        self.part, self.sheet, self.base = part, sheet, base
        self.document = document
        self.native_identity = object()
        self.sheet_name, self.section_label = sheet_name, section_label
        self.Name = sheet_name if sheet else f"Section View {section_label}-{section_label}"
        self._angle = math.pi / 2
        self.cut = SectionLabel(section_label, self)
        self.parent = None
        self.Type = 2
        self.ReferencedConfiguration = "Default"
        self.ScaleDecimal = 3.0
        self.Position = [0.3, 0.2]
        self.updates = 0

    @property
    def Angle(self):
        return self._angle

    @Angle.setter
    def Angle(self, value):
        self.document.app.mutators.append(("angle", value, self.document.path))
        self.document.app.on_write(self, "angle")
        if not self.document.app.refuse_write:
            self._angle = value
            self.document.dirty = True

    def GetSection(self):
        return None if self.sheet or self.base else self.cut

    def GetBaseView(self):
        if self.parent is None:
            self.parent = View(self.part, self.sheet_name, self.section_label, base=True, document=self.document)
        return self.parent

    @property
    def ReferencedDocument(self):
        return self.part

    def IsBroken(self):
        return False

    def GetDisplayMode2(self):
        return 2

    def GetCThreadQuality(self):
        return True

    def GetUseParentDisplayMode(self):
        return False

    def GetFacettedHlrDisplay(self):
        return False

    def GetCThreads(self):
        if self.part.scene.is_sm:
            env = self.document.app.environment
            if self.updates == 0:
                env.diagnostic_calls += 1
                self.document.app.events.append(("diagnostic", "BracketMountingTaps"))
                env.before_diagnostic()
            phase = "after_generation" if self.updates else "before_generation"
            witness = env.sm_read(f"{phase}.threads")
            if witness.get("present") is not True:
                return None
            return [DisplayThread(self, index) for index in range(env.sm_read(f"{phase}.thread_count"))]
        self.document.app.on_read(self)
        return [DisplayThread(self, 0)]

    def UpdateViewDisplayGeometry(self):
        self.updates += 1
        self.document.app.generation.append(self.document.path)

    @property
    def ModelToViewTransform(self):
        return module("transform", view=self, ArrayData=[1.,0.,0.,0.,1.,0.,0.,0.,1.,0.,0.,0.,self.ScaleDecimal,0.,0.,0.])


class DisplayThread:
    def __init__(self, view, index):
        self.view, self.index = view, index

    def GetAnnotation(self):
        if self.view.part.scene.is_sm:
            phase = "after_generation" if self.view.updates else "before_generation"
            if self.view.document.app.environment.sm_read(f"{phase}.thread[{self.index}].annotation").get("present") is not True:
                return None
        return DisplayAnnotation(self.view, self.index)

    def GetDisplayData(self):
        return self.display("ICThread")

    def display(self, channel):
        if self.view.part.scene.is_sm:
            phase = "after_generation" if self.view.updates else "before_generation"
            if self.view.document.app.environment.sm_read(f"{phase}.thread[{self.index}].{channel}.display").get("present") is not True:
                return None
        return DisplayData(self.view, channel, self.index)


class DisplayAnnotation(DisplayThread):
    Visible, Layer = 1, ""

    def IsDangling(self):
        return False

    def GetAttachedEntityTypes(self):
        return ()

    def GetAttachedEntities3(self):
        return (self.view.part.scene.edge,)

    def GetDisplayData(self):
        return self.display("IAnnotation")


class DisplayData:
    def __init__(self, view, channel, index):
        self.view, self.channel, self.index = view, channel, index

    def count(self, kind):
        phase = "after_generation" if self.view.updates else "before_generation"
        key = f"{phase}.thread[{self.index}].{self.channel}.{kind}.count"
        if self.view.part.scene.is_sm:
            return self.view.document.app.environment.sm_read(key)
        result = recorded_diagnostic("b0")["reads"][key]
        result = self.view.document.app.count_fault(self.view, self.channel, kind, result)
        if isinstance(result, BaseException):
            trip(result)
        return result

    def GetLineCount(self):
        return self.count("lines")

    def GetPolyLineCount(self):
        return self.count("polylines")

    def GetArcCount(self):
        result = self.count("arcs")
        if self.view.part.scene.is_sm and self.view.updates and self.index == 3 and self.channel == "IAnnotation":
            self.view.document.app.environment.after_diagnostic()
        return result

    def payload(self, kind, index):
        if self.view.part.scene.is_sm:
            phase = "after_generation" if self.view.updates else "before_generation"
            return self.view.document.app.environment.sm_read(f"{phase}.thread[{self.index}].{self.channel}.{kind}[{index}]")
        return self.view.document.app.payload(self.view, self.channel, kind, index)

    def GetLineAtIndex2(self, index):
        return self.payload("lines", index)

    def GetPolylineAtIndex2(self, index):
        return self.payload("polylines", index)

    def GetArcAtIndex2(self, index):
        return self.payload("arcs", index)


class MathPoint:
    def __init__(self, xyz):
        self.ArrayData = list(xyz)

    def MultiplyTransform(self, transform):
        view = transform.view
        x, y, z = self.ArrayData
        # Synthetic orthogonal orientation puts model Z axis in view X.
        u, v = z, y
        c, s = math.cos(view.Angle), math.sin(view.Angle)
        return MathPoint([view.Position[0] + view.ScaleDecimal*(c*u-s*v),
                          view.Position[1] + view.ScaleDecimal*(s*u+c*v), x*view.ScaleDecimal])


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
        self.view_rows = None

    @property
    def Extension(self):
        return self.scene if self.kind == 1 else module("extension", GetUserPreferenceToggle=lambda *_args: True)

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
        if self.view_rows is None:
            self.view_rows = ((View(self.part, self.sheet_name, self.section_label, sheet=True, document=self),
                               View(self.part, self.sheet_name, self.section_label, document=self)),)
        return (tuple(self.view_rows[0]) + tuple(self.extra_views),)

    def ViewZoomtofit2(self):
        return None

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
        values = recorded_diagnostic("sm_positive" if scene.is_sm else "b0")["reads"]
        self.values = {key.removeprefix("source."): value for key, value in values.items()
                       if key.startswith("source.") and isinstance(value, (str, int, float))}
        if cosmetic:
            self.values = dict(recorded_source()["features"][33]["scalars"])
            if scene.is_sm:
                self.values.update(ApplyThread=0, BlindDepth=0.00495, DiameterType=2, EndCondition=0)

    def __getattr__(self, name):
        if name in self.values:
            value = self.values[name]
            if isinstance(value, BaseException):
                trip(value)
            return value
        raise AttributeError(name)

    @property
    def Edge(self):
        raise AssertionError("selected-edge getter forbidden in representation experiment")

    def AccessSelections(self, *_args):
        raise AssertionError("source selection access forbidden")

    def ReleaseSelectionAccess(self):
        raise AssertionError("source release forbidden")


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
        self.is_sm = "sm-summing-lever" in document.path
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
        self.wizard = SourceFeature(self, "BracketMountingTaps" if self.is_sm else "LeverTap",
                                    "HoleWzd", SourceDefinition(self))
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

    def GetUserPreferenceToggle(self, *_args):
        return True

    def GetCorrespondingEntity2(self, _entity):
        return None  # Actual B0 correspondence is NULL, never invent ownership.

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
        self.source_mode = "cosmetic"
        self.scenes = []
        self.prepare_scene = lambda _scene: None
        self.sm_source_mode = "cosmetic"
        self.prepare_sm_scene = lambda _scene: None
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
        self.mutators, self.generation = [], []
        self.on_write = lambda _view, _kind: None
        self.on_read = lambda _view: None
        self.refuse_write = False
        self.count_fault = lambda _view, _channel, _kind, value: value
        self.payload = lambda *_args: [0.,0.,0.,0.,0.3,0.2,0.,0.3,0.21,0.]

    def GetMathUtility(self):
        return module("math", CreatePoint=MathPoint)

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
        expected_options = 1 if kind == 3 and "mg-magnifying-bracket" in path else 3
        if (options, configuration, errors, warnings) != (expected_options, "", 0, 0):
            raise AssertionError("fixed SM/R1/C1 open contract changed")
        readonly = bool(options & 2) if self.readonly[kind] is DEFAULT else self.readonly[kind]
        doc = Document(path, kind, readonly=readonly)
        doc.app = self
        if kind == 1:
            is_sm = "sm-summing-lever" in path
            doc.scene = SourceScene(doc, self.sm_source_mode if is_sm else self.source_mode)
            self.scenes.append(doc.scene)
            (self.prepare_sm_scene if is_sm else self.prepare_scene)(doc.scene)
        if kind == 3:
            doc.part = next(item for item in self.documents if item.kind == 1)
        self.documents.append(doc)
        self.active = doc
        self.after_open(doc)
        case = "sm_positive" if "sm-summing-lever" in path else ("r1" if len(self.scenes) == 2 else "c1")
        return doc, 0, self.open_warnings.get((case, kind), self.open_warning if case != "sm_positive" else 0)

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
               or (doc.dirty and (doc.kind != 3 or doc.readonly is not False or "mg-magnifying-bracket" not in doc.path or "diagnostic-copies" not in doc.path))
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
        self.app.environment = self
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
        self.sm_diagnostic = recorded_diagnostic("sm_positive")
        self.sm_reader_fault = lambda _key, value: value
        self.sm_reader_calls = []
        self.image_calls = []
        self.identity_override = None
        self.path_redirect = None
        self.copy_fs_attempts = []

    def capture_image(self, path):
        self.image_calls.append(str(path))
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"synthetic offline image collaborator")
        return str(path)

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

    def sm_read(self, key):
        """Actual fixture values served through individually faultable native readers."""
        self.sm_reader_calls.append(key)
        value = self.sm_reader_fault(key, self.sm_diagnostic["reads"][key])
        if isinstance(value, BaseException):
            trip(value)
        return value

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
                "_com": module("_com", _early_bound=lambda value, _kind: value, double_array=lambda value: tuple(value)),
                "_seat_forensics": module("_seat_forensics", _grab_screen=self.capture_image),
                "_telemetry": self.telemetry,
                "_watchdog": module("_watchdog", start=lambda: self.watchdog_events.append("start"), stop=self.stop),
                "_artifact_cache": module("_artifact_cache", restore=self.restore, _restore_path=self.restore_path),
                "azure": module("azure", __path__=[]),
                "azure.identity": module("azure.identity", ManagedIdentityCredential=self.credential),
                "azure.storage": module("azure.storage", __path__=[]),
                "azure.storage.blob": module("azure.storage.blob", ContainerClient=self.container),
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
                    payload = b"offline captured drawing fixture" if case["case"] != "sm_positive" and kind == "drawing" else f"{'sm' if case['case'] == 'sm_positive' else 'bracket'} {kind}".encode()
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
                            if case["case"] != "sm_positive" and kind == "drawing":
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
            self.assertEqual(report["native_ship"], "NOT_SHIP")
            self.assertEqual([row[1] for row in env.app.open_calls], [1, 3, 1, 3, 1, 3])
            self.assertEqual(env.app.close_calls, ["sm-summing-lever.SLDDRW", "sm-summing-lever.SLDPRT",
                                                 "mg-magnifying-bracket-native-thread.SLDDRW", "mg-magnifying-bracket.SLDPRT",
                                                 "mg-magnifying-bracket-native-thread.SLDDRW", "mg-magnifying-bracket.SLDPRT"])
            self.assertEqual(env.app.documents, [])
            self.assertEqual(captures, [])

    def test_drawing_close_auto_unloads_part_without_stale_second_close(self):
        with Environment().installed() as env:
            env.app.auto_unload_part = True
            code, report, _ = env.run_driver()
            self.assertEqual(code, 0)
            self.assertEqual(env.app.close_calls, ["sm-summing-lever.SLDDRW", "mg-magnifying-bracket-native-thread.SLDDRW",
                                                 "mg-magnifying-bracket-native-thread.SLDDRW"])
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
                self.assertEqual(capture["primary_failure"]["operation"], "after_generation.thread[3].IAnnotation.arcs.count")
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
        # Keep the fault at its original post-diagnostic boundary. The passive
        # SM census now legitimately encounters it before collection completes;
        # cleanup must still refuse the same untrustworthy document identities.
        for result in (0, -1, 7, None, True, "1"):
            with self.subTest(result=result), Environment().installed() as env:
                env.after_diagnostic = lambda: setattr(env.app, "identity_override", lambda _left, _right: result)
                code, report, captures = env.run_driver()
                self.assertEqual(code, 1)
                self.assertFalse(report["cases"][0]["collection_completed"])
                self.assertEqual(report["cases"][0]["source_metadata"]["state"], "UNAVAILABLE")
                self.assertTrue(report["cases"][0]["source_metadata"]["errors"])
                source_error = report["cases"][0]["source_metadata"]["errors"][0]
                self.assertEqual(source_error["type"], "RuntimeError")
                self.assertIn("identity", source_error["message"])
                for key in ("operation", "type", "message"):
                    self.assertEqual(report["primary_failure"][key], source_error[key])
                self.assertTrue(captures[0]["primary_traceback"]["available"])
                self.assertEqual(report["cases"][1]["status"], "not_started")
                self.assertTrue(all(Path(call[0]).stem == "sm-summing-lever" for call in env.app.open_calls))
                self.assertEqual(sum(scene.access_calls for scene in env.app.scenes), 0)
                self.assertFalse(report["cases"][0]["inventories"]["before_close_0"]["enumerated"])
                self.assertEqual(env.app.close_calls, [])
                self.assertEqual(len(env.app.documents), 2)
                self.assertEqual(len(captures[0]["cases"][0]["closures"]), 2)
                self.assertTrue(all(row["status"] == "stranded_owned" for row in captures[0]["cases"][0]["closures"]))
        with Environment().installed() as env:
            env.after_diagnostic = lambda: setattr(
                env.app, "identity_override", lambda left, right: 1 if left is right else -1
            )
            code, report, captures = env.run_driver()
            self.assertEqual(code, 1)
            self.assertFalse(report["cases"][0]["collection_completed"])
            self.assertEqual(report["cases"][0]["source_metadata"]["state"], "UNAVAILABLE")
            self.assertTrue(report["cases"][0]["source_metadata"]["errors"])
            source_error = report["cases"][0]["source_metadata"]["errors"][0]
            self.assertEqual(source_error["type"], "RuntimeError")
            self.assertIn("identity", source_error["message"])
            for key in ("operation", "type", "message"):
                self.assertEqual(report["primary_failure"][key], source_error[key])
            self.assertTrue(captures[0]["primary_traceback"]["available"])
            self.assertEqual(report["cases"][1]["status"], "not_started")
            self.assertTrue(all(Path(call[0]).stem == "sm-summing-lever" for call in env.app.open_calls))
            self.assertEqual(sum(scene.access_calls for scene in env.app.scenes), 0)
            self.assertFalse(report["cases"][0]["inventories"]["before_close_0"]["enumerated"])
            self.assertTrue(any(row.get("raw") == -1 and ".identity.previous[" in row["operation"] for row in report["cases"][0]["identity_comparisons"]))
            self.assertEqual(env.app.close_calls, [])
            self.assertEqual(len(env.app.documents), 2)
            self.assertEqual(len(captures[0]["cases"][0]["closures"]), 2)
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

    def test_sm_final_hash_failure_prevents_representation_staging(self):
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

    def test_drawing_download_errors_or_hash_mismatch_cannot_open_or_replace_source(self):
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
                self.assertEqual(captures[0]["primary_failure"]["case"], "r1")
                self.assertEqual(captures[0]["primary_failure"]["operation"], "captured_blob.download")
                self.assertIn("credential.close", env.blob_calls)
                if mode == "access_denied":
                    self.assertEqual(captures[0]["primary_failure"]["type"], "BrokenText")
                    body_exit = next(row for row in env.telemetry.exit_errors if row[0] == "build")
                    self.assertIs(body_exit[2], env.blob_error)
                    self.assertTrue(any(frame.f_code is trip.__code__ for frame, _ in traceback.walk_tb(body_exit[3])))

    

    

    

    

    









def install_recorded_tree_aliases(scene):
    """Actual folder/scalar values in a synthetic lifecycle, not a native S1 result."""
    packet = recorded_source()
    rows = packet["features"]
    indices = (1, 2, 3, 4, 11, 14, 16)
    nodes = {index: SourceFeature(scene, rows[index]["name"], rows[index]["type"]) for index in indices}
    cursor = scene.later
    for node in nodes.values():
        cursor.next = node
        cursor = node
    ambient = SourceFeature(scene, rows[12]["name"], rows[12]["type"])
    directional = SourceFeature(scene, rows[13]["name"], rows[13]["type"])
    nodes[11].child, ambient.next = ambient, directional
    ambient.owner = directional.owner = nodes[11]
    scene.wizard.definition.values = dict(rows[30]["scalars"])
    scene.cosmetic.Name = rows[33]["name"]
    scene.cosmetic.definition.values = dict(rows[33]["scalars"])
    alias = bytes(packet["feature_reference_reads"]["before.feature[2].reference.bytes"])
    original_get, original_resolve = scene.GetPersistReference3, scene.GetObjectByPersistReference3
    scene.GetPersistReference3 = lambda entity: alias if entity in nodes.values() else original_get(entity)
    scene.GetObjectByPersistReference3 = lambda reference: (nodes[1], 0) if bytes(reference) == alias else original_resolve(reference)
    return nodes, alias


class RecordedSourceIdentityBoundaries(unittest.TestCase):
    @staticmethod
    def observation(packet, comparison):
        operation = comparison["operation"].removeprefix("s1.")
        status = packet["persistent_statuses"].get(operation.removesuffix(".resolved_identity") + ".status")
        feature = None
        if operation.startswith("before.feature["):
            feature = packet["features"][int(operation.split("[", 1)[1].split("]", 1)[0])]
        return status, feature

    def test_all_recorded_identity_results_drive_the_actual_admission_guard(self):
        packet = recorded_source()
        with Environment().installed() as env:
            admitted = []
            for comparison in packet["persistent_comparisons"]:
                status, feature = self.observation(packet, comparison)
                # The recorded IsSame call was reached after the non-NULL
                # resolution guard. No resolved type/name was captured.
                admitted.append(env.driver.require_reference_identity(status, True, comparison["raw"], feature))
            self.assertEqual(admitted.count(False), 6)
            self.assertEqual(admitted.count(True), 237)
            for edge in packet["physical_edges"]:
                self.assertIs(edge["operations_complete"], True)
                self.assertIs(edge["owned_body_proven"], True)
            self.assertNotIn("selected_edge", packet)

    def test_every_recorded_core_probe_rejects_unknown_or_negative_identity(self):
        packet = recorded_source()
        with Environment().installed() as env:
            for comparison in packet["persistent_comparisons"]:
                status, feature = self.observation(packet, comparison)
                if feature is not None and env.driver.descriptive_tree_container(feature):
                    continue
                for changed_status, present, raw in (
                    (status, True, 0), (status, True, None), (status, True, True),
                    (status, True, -1), (None, True, 1), (False, True, 1),
                    (1, True, 1), (0, False, 1), (0, None, 1),
                ):
                    with self.subTest(operation=comparison["operation"], status=changed_status, present=present, raw=raw):
                        with self.assertRaises(RuntimeError):
                            env.driver.require_reference_identity(changed_status, present, raw, feature)
                status_key = comparison["operation"].removeprefix("s1.").removesuffix(".resolved_identity") + ".status"
                observed_status = packet["persistent_statuses"].pop(status_key)
                try:
                    missing_status, actual_feature = self.observation(packet, comparison)
                    with self.assertRaises(RuntimeError):
                        env.driver.require_reference_identity(missing_status, True, comparison["raw"], actual_feature)
                finally:
                    packet["persistent_statuses"][status_key] = observed_status
            # A selected Edge never receives a feature-container exception.
            with self.assertRaises(RuntimeError):
                env.driver.require_reference_identity(0, True, 0)

    def test_actual_six_exceptions_are_exact_and_structurally_conditional(self):
        packet = recorded_source()
        with Environment().installed() as env:
            for comparison in packet["persistent_comparisons"]:
                if comparison["raw"] != 0:
                    continue
                status, original = self.observation(packet, comparison)
                self.assertFalse(env.driver.require_reference_identity(status, True, 0, original))
                for field, value in (
                    ("type", "NewFolder"), ("type", "SolidBodyFolder"), ("type", "SurfaceBodyFolder"),
                    ("type", "FavoriteFolder"), ("type", "RefPlane"), ("type", "HoleWzd"),
                    ("type", "CosmeticThread"), ("name", None), ("name", ""),
                    ("parent_inventory_index", 0), ("non_root_occurrence", True),
                    ("rolled_back", None), ("definition_state", "UNAVAILABLE"),
                    ("definition_state", "PRESENT"), ("face_state", "PRESENT"), ("owner_state", "PRESENT"),
                ):
                    with self.subTest(index=original["index"], field=field, value=value):
                        changed = dict(original, **{field: value})
                        with self.assertRaises(RuntimeError):
                            env.driver.require_reference_identity(status, True, 0, changed)
                for field in ("name", "type", "parent_inventory_index", "rolled_back", "definition_state", "face_state", "owner_state"):
                    changed = dict(original)
                    del changed[field]
                    with self.assertRaises(RuntimeError):
                        env.driver.require_reference_identity(status, True, 0, changed)

    def test_recorded_first_parent_tree_requires_complete_names_types_and_relationships(self):
        # Thin native projection contains first-parent relations; full live
        # duplicate traversal relationships are exercised separately below.
        packet = recorded_source()
        rows = packet["features"]
        links = [{"index": row["index"], "parent_inventory_index": row["parent_inventory_index"]} for row in rows]
        with Environment().installed() as env:
            baseline = env.driver.structural_tree(rows, links)
            self.assertEqual(len(baseline["paths"]), 39)
            for field, value in (("name", None), ("type", ""), ("index", True),
                                 ("parent_inventory_index", 33), ("parent_inventory_index", False)):
                changed = [dict(row) for row in rows]
                changed[33][field] = value
                with self.subTest(field=field, value=value), self.assertRaises(RuntimeError):
                    env.driver.structural_tree(changed, links)
            with self.assertRaises(RuntimeError):
                env.driver.structural_tree(rows, links[:-1])
            renamed = [dict(row) for row in rows]
            renamed[2]["name"] = "Changed History"
            self.assertNotEqual(env.driver.structural_tree(renamed, links), baseline)

    

    

    


class PassiveSmScalarBoundaries(unittest.TestCase):
    def test_same_scalar_interfaces_preserve_each_owned_child_without_selection_or_geometry_reads(self):
        with Environment().installed() as env:
            def prepare(scene):
                def forbidden(*_args):
                    raise AssertionError("passive SM census must not request geometry or selection access")
                second = SourceFeature(scene, "SecondSyntheticChild", "CosmeticThread", SourceDefinition(scene, True))
                second.owner, scene.cosmetic.next = scene.wizard, second
                second.definition.values["BlindDepth"] = 0.003
                for feature in (scene.wizard, scene.cosmetic, second, scene.later):
                    feature.GetFaces = forbidden
                for child in (scene.cosmetic, second):
                    child.definition.AccessSelections = child.definition.ReleaseSelectionAccess = forbidden
                scene.document.GetBodies2 = forbidden
                scene.edge.GetCurve = forbidden
            env.app.prepare_sm_scene = prepare
            code, report, _ = env.run_driver()
            census = report["cases"][0]["source_metadata"]
            self.assertEqual(code, 0)
            self.assertEqual(census["state"], "OBSERVED")
            self.assertEqual(census["cosmetic_child_count"], 2)
            self.assertEqual(census["wizard"]["scalars"]["ThreadEndCondition"], 0)
            self.assertEqual(census["wizard"]["scalars"]["ThreadDepth"], 0.00495)
            self.assertEqual([child["scalars"]["BlindDepth"] for child in census["cosmetic_children"]], [0.00495, 0.003])
            self.assertEqual(census["enum_namespaces"], report["cases"][1]["source_observations"]["enum_namespaces"])
            self.assertEqual(census["causal_conclusion"], "NOT_ESTABLISHED")
            scene = env.app.scenes[0]
            self.assertEqual((scene.access_calls, scene.release_calls, scene.edge_reads), (0, 0, 0))
            self.assertFalse(scene.document.dirty)

    def test_missing_or_failed_sm_child_evidence_never_becomes_zero_or_admits_interventions(self):
        for mode in ("null_definition", "definition_error", "scalar_error", "null_scalar",
                     "wrong_owner", "owner_error", "unclassified_owner", "duplicate_wizard", "tree_error", "core_pid"):
            with self.subTest(mode=mode), Environment().installed() as env:
                def prepare(scene):
                    if mode == "null_definition":
                        scene.cosmetic.definition = None
                    elif mode == "definition_error":
                        scene.cosmetic.definition_error = RuntimeError("child definition unavailable")
                    elif mode in ("scalar_error", "null_scalar"):
                        scene.cosmetic.definition.values["BlindDepth"] = RuntimeError("child depth unavailable") if mode == "scalar_error" else None
                    elif mode == "wrong_owner":
                        scene.cosmetic.owner = scene.later
                    elif mode == "owner_error":
                        scene.cosmetic.owner_error = RuntimeError("native owner unavailable")
                    elif mode == "unclassified_owner":
                        scene.wizard.child = None
                        scene.later.next = scene.cosmetic
                        scene.cosmetic.owner_error = RuntimeError("unclassified top-level cosmetic owner unavailable")
                    elif mode == "duplicate_wizard":
                        scene.later.next = SourceFeature(scene, "BracketMountingTaps", "HoleWzd", SourceDefinition(scene))
                    elif mode == "tree_error":
                        scene.later.type_error = RuntimeError("tree type unavailable")
                    else:
                        scene.resolve_override = lambda _entity: scene.later
                env.app.prepare_sm_scene = prepare
                code, report, _ = env.run_driver()
                census = report["cases"][0]["source_metadata"]
                self.assertEqual(code, 1)
                self.assertEqual(census["state"], "UNAVAILABLE")
                self.assertNotIn("cosmetic_child_count", census)
                self.assertTrue(census["errors"])
                if mode in ("wrong_owner", "owner_error", "unclassified_owner"):
                    child = census["cosmetic_children"][0]
                    self.assertEqual(child["scalars"]["BlindDepth"], 0.00495)
                    self.assertEqual(child["wizard_owner_state"], "DIFFERENT" if mode == "wrong_owner" else "UNAVAILABLE")
                self.assertEqual(report["cases"][1]["status"], "not_started")
                self.assertEqual(env.diagnostic_calls, 1)
                self.assertEqual(sum(scene.access_calls for scene in env.app.scenes), 0)

    def test_native_owner_association_not_arbitrary_tree_pairing_selects_passive_children(self):
        with Environment().installed() as env:
            def prepare(scene):
                # A native-owned feature may also be enumerated at top level.
                scene.wizard.child = None
                scene.later.next = scene.cosmetic
                unrelated = SourceFeature(scene, "UnrelatedSyntheticCosmetic", "CosmeticThread", None)
                unrelated.owner = scene.later
                scene.cosmetic.next = unrelated
            env.app.prepare_sm_scene = prepare
            code, report, _ = env.run_driver()
            census = report["cases"][0]["source_metadata"]
            self.assertEqual(code, 0)
            self.assertEqual(census["state"], "OBSERVED")
            self.assertEqual(census["cosmetic_child_count"], 1)
            self.assertEqual(census["cosmetic_children"][0]["wizard_owner_state"], "SAME")
            self.assertEqual(census["cosmetic_children"][0]["parent_inventory_index"], None)
            self.assertEqual(env.app.scenes[0].edge_reads, 0)

    def test_complete_native_tree_with_no_child_reports_observed_absence_not_failure(self):
        with Environment().installed() as env:
            env.app.sm_source_mode = "wizard_only"
            code, report, _ = env.run_driver()
            census = report["cases"][0]["source_metadata"]
            self.assertEqual(code, 0)
            self.assertEqual(census["state"], "OBSERVED")
            self.assertEqual(census["cosmetic_child_count"], 0)
            self.assertEqual(census["cosmetic_children"], [])
            self.assertFalse(census["errors"])


class RepresentationBehavior(unittest.TestCase):
    def test_three_fresh_pairs_one_control_and_exactly_one_factor_each(self):
        with Environment().installed() as env:
            code, report, captures = env.run_driver()
            self.assertEqual(code, 0)
            self.assertEqual(captures, [])
            sm, r1, c1 = report["cases"]
            self.assertEqual([case["case"] for case in report["cases"]], ["sm_positive", "r1", "c1"])
            self.assertEqual(env.diagnostic_calls, 1)
            self.assertEqual(env.adapter.disconnect_calls, 1)
            self.assertEqual([call[2] for call in env.app.open_calls], [3, 3, 3, 1, 3, 1])
            self.assertEqual([(kind, value) for kind,value,_ in env.app.mutators], [("angle", 0.0), ("cut", False)])
            self.assertEqual(len({case["copy_root"] for case in report["cases"]}), 3)
            self.assertEqual(r1["reads"]["copy_before.part"], c1["reads"]["copy_before.part"])
            self.assertEqual(r1["reads"]["copy_before.drawing"], c1["reads"]["copy_before.drawing"])
            self.assertEqual(len(sm["thread_ink"]["positive_payload_fields"]), 28)
            for case in report["cases"]:
                self.assertTrue(case["collection_completed"])
                self.assertTrue(case["reads"]["final.inventory_empty"])
                self.assertEqual(case["reads"]["final.ActiveDoc_state"], "NULL")
                for kind in ("part", "drawing"):
                    self.assertEqual(case["reads"][f"staged.{kind}"], case["reads"][f"final.{kind}"])
                    self.assertEqual(case["reads"][f"copy_before.{kind}"], case["reads"][f"copy_after.{kind}"])
            for case in (r1, c1):
                experiment = case["representation"]
                self.assertEqual(experiment["state"], "OBSERVED_ZERO")
                self.assertEqual(experiment["native_ship"], "NOT_SHIP")
                self.assertTrue(experiment["confirmed"])
                self.assertEqual(experiment["mutator_calls"], 1)
                self.assertEqual(case["thread_ink"]["state"], "OBSERVED_ZERO")
                baseline = experiment["stages"]["baseline_before_generation"]["state"]
                self.assertEqual((baseline["angle"], baseline["cut_only"]), (math.pi/2, True))
                self.assertTrue(case["source_observations"]["clean_comparison"])
                self.assertEqual(set(case["source_observations"]["phases"]), {"before", "after"})
            self.assertEqual(env.app.documents, [])
            self.assertTrue(all(not scene.document.dirty for scene in env.app.scenes))

    def test_actual_recorded_summary_and_all_zero_boundaries(self):
        with Environment().installed() as env:
            positive = env.driver.thread_ink_summary(recorded_diagnostic("sm_positive"))
            self.assertEqual(len(positive["positive_payload_fields"]), 28)
            original = recorded_diagnostic("b0")
            self.assertEqual(env.driver.thread_ink_summary(original)["state"], "OBSERVED_ZERO")
            keys = [key for key in original["reads"] if key.endswith((".lines.count", ".polylines.count", ".arcs.count"))]
            self.assertEqual(len(keys), 12)
            for key in keys:
                for value in (None, True, False, -1, "0", 0.0, DEFAULT):
                    changed = copy.deepcopy(original)
                    if value is DEFAULT:
                        changed["reads"].pop(key)
                    else:
                        changed["reads"][key] = value
                    self.assertEqual(env.driver.thread_ink_summary(changed)["state"], "UNAVAILABLE")
            for key in list(original["reads"]):
                if key.endswith((".threads", ".thread_count", ".annotation", ".display")) or key.endswith(".thread[0]"):
                    changed = copy.deepcopy(original)
                    changed["reads"].pop(key)
                    self.assertEqual(env.driver.thread_ink_summary(changed)["state"], "UNAVAILABLE")
            changed = copy.deepcopy(original)
            changed["errors"]["native_reader"] = "unavailable"
            self.assertEqual(env.driver.thread_ink_summary(changed)["state"], "UNAVAILABLE")
            changed = copy.deepcopy(original)
            changed["reads"][keys[0]] = 1
            result = env.driver.thread_ink_summary(changed)
            self.assertTrue(result["positive_count_fields"])
            self.assertFalse(result["positive_payload_fields"])

    def test_invalid_fresh_baseline_never_writes_or_starts_c1(self):
        for mode in ("angle", "cut", "positive", "null", "bool", "negative", "reader", "configuration"):
            with self.subTest(mode=mode), Environment().installed() as env:
                def prepare(doc):
                    if doc.kind != 3 or "mg-magnifying-bracket" not in doc.path:
                        return
                    view = doc.GetViews()[0][1]
                    if mode == "angle":
                        view._angle = 0.0
                    elif mode == "cut":
                        view.cut.cut_only = False
                    elif mode == "configuration":
                        view.ReferencedConfiguration = ""
                env.app.after_open = prepare
                values = {"positive":1, "null":None, "bool":False, "negative":-1, "reader":ProbeError("native count failure")}
                if mode in values:
                    env.app.count_fault = lambda _view,_channel,kind,value: values[mode] if kind == "lines" else value
                code, report, _ = env.run_driver()
                self.assertEqual(code, 1)
                self.assertEqual(env.app.mutators, [])
                self.assertEqual(report["cases"][2]["status"], "not_started")
                self.assertEqual(env.app.documents, [])

    def test_native_factor_write_readback_is_required_without_retry(self):
        for kind in ("angle", "cut"):
            with self.subTest(kind=kind), Environment().installed() as env:
                env.app.on_write = lambda _view, actual: setattr(env.app, "refuse_write", actual == kind)
                code, report, _ = env.run_driver()
                self.assertEqual(code, 1)
                index = 1 if kind == "angle" else 2
                failed = report["cases"][index]
                self.assertTrue(failed["representation"]["attempted"])
                self.assertFalse(failed["representation"]["confirmed"])
                self.assertEqual(sum(actual == kind for actual,_,_ in env.app.mutators), 1)
                self.assertEqual(len([path for path in env.app.generation if path.startswith(failed["copy_root"])]), 1)
                self.assertEqual(env.app.documents, [])

    def test_dirty_part_unknown_saveflag_or_changed_readonly_strands_without_unsafe_close(self):
        for mode in ("part_dirty", "drawing_unknown", "part_mode", "drawing_mode", "control", "foreign", "identity"):
            with self.subTest(mode=mode), Environment().installed() as env:
                def change(view, _kind):
                    if mode == "part_dirty":
                        view.part.dirty = True
                    elif mode == "drawing_unknown":
                        view.document.GetSaveFlag = lambda: None
                    elif mode == "part_mode":
                        view.part.readonly = False
                    elif mode == "drawing_mode":
                        view.document.readonly = True
                    elif mode == "control":
                        env.app.control = False
                    elif mode == "foreign":
                        env.app.documents.append(Document("C:/foreign/other.SLDPRT", 1))
                    else:
                        env.app.identity_override = -1
                env.app.on_write = change
                code, report, _ = env.run_driver()
                self.assertEqual(code, 1)
                self.assertEqual(len(env.app.close_calls), 2)  # only completed SM
                self.assertTrue(env.app.documents)
                self.assertTrue(all(row["status"] == "stranded_owned" for row in report["cases"][1]["closures"]))
                self.assertEqual(report["cases"][2]["status"], "not_started")

    def test_first_mutator_baseexception_survives_readers_cleanup_and_source_after(self):
        with Environment().installed() as env:
            primary = KeyboardInterrupt("original representation write")
            def fail_write(_view, _kind):
                env.app.close_error = BrokenText()
                trip(primary)
            env.app.on_write = fail_write
            code, report, captures = env.run_driver()
            self.assertEqual(code, 1)
            self.assertEqual(report["primary_failure"]["type"], "KeyboardInterrupt")
            self.assertEqual(report["primary_failure"]["message"], "original representation write")
            self.assertIn("after", report["cases"][1]["source_observations"]["phases"])
            self.assertTrue(captures)
            body_exit = next(row for row in env.telemetry.exit_errors if row[0] == "build")
            self.assertIs(body_exit[2], primary)
            self.assertTrue(any(frame.f_code is trip.__code__ for frame,_ in traceback.walk_tb(body_exit[3])))

    def test_finite_payload_positive_is_not_flank_identity_and_c1_still_runs(self):
        with Environment().installed() as env:
            env.app.count_fault = lambda view,_channel,kind,value: 1 if view.document.dirty and kind == "lines" else value
            code, report, _ = env.run_driver()
            self.assertEqual(code, 0)
            for case in report["cases"][1:]:
                representation = case["representation"]
                self.assertEqual(representation["state"], "OBSERVED_POSITIVE")
                self.assertEqual(representation["causal_conclusion"], "NOT_ESTABLISHED")
                geometry = representation["stages"]["post_write_after_generation"]["geometry"]
                self.assertTrue(geometry["primitives"])
                self.assertIn("UNAVAILABLE", geometry["coordinate_frame_authority"])
                self.assertEqual(geometry["source_display_native_identity"], "UNAVAILABLE_NO_INVENTED_BRIDGE")
                self.assertEqual(case["native_ship"], "NOT_SHIP")

    def test_bad_positive_payload_is_unavailable_without_zero_substitution(self):
        for payload in (None, [], [0.]*10, [float("nan")]*10, [True]*10):
            with self.subTest(payload=payload), Environment().installed() as env:
                env.app.count_fault = lambda view,_channel,kind,value: 1 if view.document.dirty and kind == "lines" else value
                env.app.payload = lambda *_args: payload
                code, report, _ = env.run_driver()
                self.assertEqual(code, 1)
                self.assertEqual(report["cases"][1]["representation"]["state"], "UNAVAILABLE")
                self.assertTrue(report["cases"][1]["after_intervention_diagnostic"]["errors"])
                self.assertEqual(report["cases"][2]["status"], "not_started")

    def test_rotation_normalization_is_not_axis_aligned_screen_matching(self):
        with Environment().installed() as env:
            origin, scale, point = [0.3,0.2], 3., [0.01,0.002,0.]
            for angle in (0., math.pi/2, -math.pi/2):
                c,s = math.cos(angle), math.sin(angle)
                sheet = [origin[0]+scale*(c*point[0]-s*point[1]),
                         origin[1]+scale*(s*point[0]+c*point[1]), 0.]
                normalized = env.driver.normalized_point(sheet, origin, angle, scale)
                for actual, expected in zip(normalized, point):
                    self.assertAlmostEqual(actual, expected)

    def test_original_and_copy_disk_drift_are_refusals_after_owned_cleanup(self):
        for target in ("original", "copy"):
            with self.subTest(target=target), Environment().installed() as env:
                def change(view, _kind):
                    path = env.driver.ROOT / env.driver.R1["drawing"]["path"] if target == "original" else Path(view.document.path)
                    path.write_bytes(b"external disk drift")
                env.app.on_write = change
                code, report, _ = env.run_driver()
                self.assertEqual(code, 1)
                self.assertEqual(env.app.documents, [])
                self.assertEqual(report["cases"][2]["status"], "not_started")
                first, last = ("staged.drawing","final.drawing") if target == "original" else ("copy_before.drawing","copy_after.drawing")
                self.assertNotEqual(report["cases"][1]["reads"][first], report["cases"][1]["reads"][last])

    def test_core_or_tree_failure_blocks_mutation_but_recorded_virtual_aliases_do_not(self):
        for mode in ("aliases", "core", "unknown_type", "tree", "owner", "body"):
            with self.subTest(mode=mode), Environment().installed() as env:
                def prepare(scene):
                    nodes, _ = install_recorded_tree_aliases(scene)
                    if mode == "core":
                        scene.resolve_override = lambda _entity: scene.later
                    elif mode == "unknown_type":
                        nodes[2].kind = "NewFolder"
                    elif mode == "tree":
                        nodes[2].Name = ""
                    elif mode == "owner":
                        scene.cosmetic.owner_error = ProbeError("native owner unavailable")
                    elif mode == "body":
                        scene.edge_body = NativeObject()
                env.app.prepare_scene = prepare
                code, report, _ = env.run_driver()
                self.assertEqual(code, 0 if mode == "aliases" else 1)
                if mode == "aliases":
                    source = report["cases"][1]["source_observations"]
                    self.assertTrue(source["clean_comparison"])
                    optional = [row for row in source["reference_observations"].values() if not row["required"]]
                    self.assertEqual(len(optional), 12)
                    self.assertTrue(all(row["native_same"] == 0 and not row["native_identity_claim"] for row in optional))
                else:
                    self.assertEqual(env.app.mutators, [])


class RepresentationAdditionalBoundaries(unittest.TestCase):
    def test_image_failure_is_explicit_gap_and_keeps_original_capture_error(self):
        with Environment().installed() as env:
            env.app.count_fault = lambda view,_channel,kind,value: 1 if view.document.dirty and kind == "lines" else value
            error = ProbeError("desktop unavailable")
            with patch.object(sys.modules["_seat_forensics"], "_grab_screen", lambda _path: trip(error)):
                code, report, _ = env.run_driver()
            self.assertEqual(code, 1)
            case = report["cases"][1]
            stage = case["representation"]["stages"]["post_write_before_generation"]
            self.assertEqual(stage["visual"]["state"], "GAP")
            self.assertEqual(report["primary_failure"]["message"], "desktop unavailable")
            self.assertTrue(case["after_intervention_diagnostic"]["reads"])
            self.assertEqual(env.app.documents, [])

    def test_each_bracket_open_warning_and_actual_mode_refuses_before_write(self):
        for case in ("r1", "c1"):
            for kind in (1, 3):
                for value in (None, False, 1):
                    with self.subTest(case=case, kind=kind, value=value), Environment().installed() as env:
                        env.app.open_warnings[(case, kind)] = value
                        code, report, _ = env.run_driver()
                        self.assertEqual(code, 1)
                        self.assertEqual(len(env.app.mutators), 0 if case == "r1" else 1)
                        self.assertFalse(report["cases"][1 if case == "r1" else 2]["collection_completed"])
        for kind, value in ((1, False), (1, None), (3, True), (3, None)):
            with self.subTest(kind=kind, value=value), Environment().installed() as env:
                def alter(doc):
                    if "mg-magnifying-bracket" in doc.path and doc.kind == kind:
                        doc.readonly = value
                env.app.after_open = alter
                code, report, _ = env.run_driver()
                self.assertEqual(code, 1)
                self.assertEqual(env.app.mutators, [])
                self.assertTrue(env.app.documents)
                self.assertEqual(report["cases"][2]["status"], "not_started")


class RequiredControlAndPathRepairs(unittest.TestCase):
    def test_good_sm_payload_plus_failed_required_reader_refuses_and_retains_exact_first_exception(self):
        failures = (
            "before_generation.thread[0].IAnnotation.arcs.count",
            "after_generation.thread[0].ICThread.lines[1]",
            "after_generation.thread[1].IAnnotation.display",
        )
        for failed_key in failures:
            for error in (ProbeError("required native reader"), KeyboardInterrupt("required native interruption")):
                with self.subTest(key=failed_key, error=type(error).__name__), Environment().installed() as env:
                    env.sm_reader_fault = lambda key,value: error if key == failed_key else value
                    env.after_diagnostic = lambda: setattr(env.app, "close_error", BrokenText())
                    code, report, captures = env.run_driver()
                    self.assertEqual(code, 1)
                    sm = report["cases"][0]
                    self.assertTrue(sm["thread_ink"]["positive_payload_fields"])
                    self.assertFalse(sm["thread_ink"]["complete"])
                    self.assertFalse(sm["collection_completed"])
                    self.assertEqual(report["primary_failure"]["operation"], failed_key)
                    self.assertEqual(report["primary_failure"]["type"], type(error).__name__)
                    self.assertEqual(report["cases"][1]["status"], "not_started")
                    self.assertEqual(report["cases"][2]["status"], "not_started")
                    self.assertEqual(len(env.app.open_calls), 2)
                    self.assertEqual(env.app.mutators, [])
                    self.assertEqual(env.blob_calls, [])
                    self.assertIn("after_generation.thread[3].IAnnotation.arcs.count", env.sm_reader_calls)
                    body_exit = next(row for row in env.telemetry.exit_errors if row[0] == "build")
                    self.assertIs(body_exit[2], error)
                    self.assertTrue(any(frame.f_code is trip.__code__ for frame,_ in traceback.walk_tb(body_exit[3])))
                    self.assertEqual(captures[0]["primary_failure"]["operation"], failed_key)
                    self.assertTrue(any(row["type"] == "BrokenText" for row in report["errors"]))

    def test_valid_required_sm_with_optional_null_bridge_and_unknown_frame_admits_both_cases(self):
        with Environment().installed() as env:
            env.app.prepare_sm_scene = lambda scene: setattr(scene, "GetCorrespondingEntity2", lambda _entity: None)
            code, report, _ = env.run_driver()
            self.assertEqual(code, 0)
            sm = report["cases"][0]
            self.assertTrue(sm["thread_ink"]["complete"])
            self.assertEqual(len(sm["thread_ink"]["positive_payload_fields"]), 28)
            self.assertEqual(sm["diagnostic"]["errors"], {})
            self.assertEqual(sm["diagnostic"]["reads"]["before_generation.thread[0].attachment[0].canonical"],
                             {"present": False})
            self.assertEqual(sm["optional_evidence"]["display_coordinate_frame"], "UNAVAILABLE_NO_PRIMARY_FRAME_AUTHORITY")
            self.assertEqual([(kind,value) for kind,value,_ in env.app.mutators], [("angle",0.0),("cut",False)])
            self.assertTrue(all(case["collection_completed"] for case in report["cases"]))

    def test_sm_typed_counts_all_payloads_and_each_required_witness_are_admission_requirements(self):
        changes = (
            ("before_generation.thread[0].ICThread.lines.count", None),
            ("before_generation.thread[0].ICThread.lines.count", False),
            ("before_generation.thread[0].ICThread.lines.count", 6.0),
            ("before_generation.thread[0].ICThread.lines.count", -1),
            ("after_generation.thread[0].ICThread.lines[0]", None),
            ("after_generation.thread[0].ICThread.lines[0]", []),
            ("after_generation.thread[0].ICThread.lines[0]", [float("nan")]*10),
            ("after_generation.thread[0].ICThread.lines[0]", [0.]*10),
            ("after_generation.thread[0].annotation", {"present": False}),
            ("after_generation.thread[1].IAnnotation.display", {"present": False}),
            ("after_generation.threads", {"present": False}),
        )
        for key,value in changes:
            with self.subTest(key=key, value=value), Environment().installed() as env:
                env.sm_diagnostic["reads"][key] = value
                code, report, _ = env.run_driver()
                self.assertEqual(code, 1)
                self.assertFalse(report["cases"][0]["collection_completed"])
                self.assertEqual(report["cases"][1]["status"], "not_started")
                self.assertEqual(env.app.mutators, [])
                self.assertEqual(env.blob_calls, [])
                self.assertEqual(env.app.documents, [])

    def test_sm_no_successful_payload_never_admits_interventions(self):
        for mode in ("all_zero", "null", "empty", "nonfinite", "reader_error"):
            with self.subTest(mode=mode), Environment().installed() as env:
                def change(key, value):
                    if mode == "all_zero" and key.endswith((".lines.count", ".polylines.count", ".arcs.count")):
                        return 0
                    if any(marker in key for marker in (".lines[", ".polylines[", ".arcs[")):
                        return {"null": None, "empty": [], "nonfinite": [float("nan")],
                                "reader_error": ProbeError("native payload unavailable")}.get(mode, value)
                    return value
                env.sm_reader_fault = change
                code, report, _ = env.run_driver()
                self.assertEqual(code, 1)
                self.assertFalse(report["cases"][0]["thread_ink"]["positive_payload_fields"])
                self.assertEqual(report["cases"][1]["status"], "not_started")
                self.assertEqual(env.app.mutators, [])
                self.assertEqual(env.app.documents, [])

    def test_redirected_image_ancestor_refuses_before_capture_collaborator(self):
        with Environment().installed() as env:
            env.path_redirect = "cad/out/reports/diagnostics/representation-images"
            env.app.count_fault = lambda view,_channel,kind,value: 1 if view.document.dirty and kind == "lines" else value
            code, report, _ = env.run_driver()
            self.assertEqual(code, 1)
            self.assertEqual(env.image_calls, [])  # driver guard, not fake writer containment
            case = report["cases"][1]
            self.assertEqual(case["representation"]["stages"]["post_write_before_generation"]["visual"]["state"], "GAP")
            self.assertEqual(report["primary_failure"]["operation"], "post_write_before_generation.image")
            self.assertEqual(report["primary_failure"]["message"], "uncertified output path")
            self.assertEqual(report["cases"][2]["status"], "not_started")
            self.assertEqual(env.app.documents, [])

    def test_redirected_copy_ancestors_refuse_before_creation_and_open(self):
        for ancestor in ("cad/out/diagnostic-copies", "cad/out/diagnostic-copies/mg-saved-thread-control"):
            with self.subTest(ancestor=ancestor), Environment().installed() as env:
                env.path_redirect = ancestor
                code, report, _ = env.run_driver()
                self.assertEqual(code, 1)
                self.assertEqual(env.copy_fs_attempts, [])
                self.assertEqual(env.app.open_calls, [])
                self.assertEqual(env.app.close_calls, [])
                self.assertEqual(report["cases"][1]["status"], "not_started")

    def test_copy_path_recertification_refuses_direct_result_or_cleanup_after_redirect(self):
        for phase in ("direct_result", "cleanup"):
            with self.subTest(phase=phase), Environment().installed() as env:
                def redirect():
                    env.path_redirect = "cad/out/diagnostic-copies"
                if phase == "direct_result":
                    env.app.after_open = lambda _doc: redirect()
                else:
                    env.after_diagnostic = redirect
                code, report, _ = env.run_driver()
                self.assertEqual(code, 1)
                self.assertEqual(env.app.close_calls, [])
                self.assertTrue(env.app.documents)
                self.assertEqual(report["cases"][1]["status"], "not_started")
                if phase == "direct_result":
                    self.assertEqual(len(env.app.open_calls), 1)
                    self.assertEqual(report["cases"][0]["opens"][0]["ownership_state"], "UNAVAILABLE_STRANDED")
                else:
                    self.assertTrue(all(row["status"] == "stranded_owned" for row in report["cases"][0]["closures"]))


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--driver", type=Path, default=DRIVER_PATH)
    parser.add_argument("--helper", type=Path, default=HELPER_PATH)
    args, unittest_args = parser.parse_known_args()
    DRIVER_PATH, HELPER_PATH = args.driver.resolve(strict=True), args.helper.resolve(strict=True)
    unittest.main(argv=[sys.argv[0], *unittest_args])
