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
from contextlib import ExitStack, contextmanager
import importlib.abc
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import traceback
from types import ModuleType
import unittest
from unittest.mock import patch

DRIVER_PATH = Path(__file__).parent / "diagnostics/probe_mg_saved_thread_control.py"
HELPER_PATH = Path(__file__).parent / "diagnostics/_owned_native_session.py"


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

    def __exit__(self, *_):
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
    def GetName(self):
        return "Lever Geometry"


class SectionLabel:
    def GetLabel(self):
        return "H"


class View:
    def __init__(self, part, *, sheet=False, base=False):
        self.part, self.sheet, self.base = part, sheet, base
        self.Name = "Lever Geometry" if sheet else "Section View H-H"

    def GetSection(self):
        return None if self.sheet or self.base else SectionLabel()

    def GetBaseView(self):
        return View(self.part, base=True)

    @property
    def ReferencedDocument(self):
        return self.part


class Document:
    def __init__(self, path, kind, *, readonly=True):
        self.path, self.kind = str(path), kind
        self.readonly = readonly
        self.dirty = False
        self.part = None

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
        return ("Lever Geometry",)

    def GetViews(self):
        return ((View(self.part, sheet=True), View(self.part)),)

    def Sheet(self, name):
        if name != "Lever Geometry":
            raise AssertionError("unexpected sheet")
        return Sheet()

    def ActivateSheet(self, name):
        return name == "Lever Geometry"

    def GetCurrentSheet(self):
        return Sheet()


class Application:
    def __init__(self):
        self.documents = []
        self.active = None
        self.control = True
        self.null_array = False
        self.count_override = None
        self.readonly = {1: True, 3: True}
        self.attach_error = None
        self.identity_override = None
        self.open_calls = []
        self.close_calls = []
        self.events = []
        self.auto_unload_part = False
        self.control_after_first_close = True

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
        return len(self.documents) if self.count_override is None else self.count_override

    def GetDocuments(self):
        return None if self.null_array else tuple(self.documents)

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
        return self.identity_override if self.identity_override is not None else int(left is right)

    def OpenDoc6(self, path, kind, options, configuration, errors, warnings):
        self.open_calls.append((path, kind, options, configuration, errors, warnings))
        if (options, configuration, errors, warnings) != (3, "", 0, 0):
            raise AssertionError("readonly/silent open contract changed")
        doc = Document(path, kind, readonly=self.readonly[kind])
        if kind == 3:
            doc.part = next(item for item in self.documents if item.kind == 1)
        self.documents.append(doc)
        self.active = doc
        return doc, 0, 0

    def ActivateDoc3(self, path, preferences, option, errors):
        if (preferences, option, errors) != (False, 1, 0):
            raise AssertionError("activation must not request rebuild/preferences")
        self.active = next(doc for doc in self.documents if doc.path == path)
        return self.active, 0

    def CloseDoc(self, title):
        self.close_calls.append(title)  # An unsafe ATTEMPT must fail the harness too.
        if not self.events or self.events[-1] != "UserControl" or self.control is not True:
            raise AssertionError("UserControl must be the final native close witness")
        if any(Path(doc.path).stem != "sm-summing-lever" or doc.dirty is not False for doc in self.documents):
            raise AssertionError("CloseDoc could touch a foreign/dirty document")
        self.events.append("CloseDoc")
        target = next(doc for doc in self.documents if doc.GetTitle() == title)
        self.documents.remove(target)
        if target.kind == 3 and self.auto_unload_part:
            self.documents[:] = [doc for doc in self.documents if doc.kind != 1]
        self.active = self.documents[-1] if self.documents else None
        self.control = self.control_after_first_close


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

    def stop(self):
        self.watchdog_events.append("stop")
        if self.watchdog_stop_error is not None:
            trip(self.watchdog_stop_error)

    def restore(self, key, outputs, label):
        self.cache_calls.append((key, outputs, label))
        return True

    def diagnostic(self, _adapter, _section, *, feature_name):
        if feature_name != "BracketMountingTaps":
            raise AssertionError("wrong diagnostic feature")
        self.diagnostic_calls += 1
        self.after_diagnostic()
        return {"reads": {"fake_boundary": True}, "errors": {}}

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
                "_artifact_cache": module("_artifact_cache", restore=self.restore),
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
            driver.CONTRACT_PATH.write_text(json.dumps(driver.CONTROL), encoding="utf-8")
            original_identity = driver.file_identity

            def identity(path):
                for kind in ("part", "drawing"):
                    if Path(path) == root / driver.CONTROL[kind]["path"]:
                        return {key: driver.CONTROL[kind][key] for key in ("bytes", "sha256")}
                return original_identity(path)

            original_open, original_mkdir = Path.open, Path.mkdir
            original_text, original_bytes = Path.write_text, Path.write_bytes

            def owned(path):
                if not Path(path).resolve().is_relative_to(root):
                    raise AssertionError(f"write outside temporary root refused: {path}")

            def guarded_open(path, mode="r", *args, **kwargs):
                if any(flag in mode for flag in "wax+"):
                    owned(path)
                return original_open(path, mode, *args, **kwargs)

            def guarded_mkdir(path, *args, **kwargs):
                owned(path)
                return original_mkdir(path, *args, **kwargs)

            def guarded_text(path, *args, **kwargs):
                owned(path)
                return original_text(path, *args, **kwargs)

            def guarded_bytes(path, *args, **kwargs):
                owned(path)
                return original_bytes(path, *args, **kwargs)

            with ExitStack() as stack:
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

    def test_initial_null_array_refuses_before_restore_or_close(self):
        with Environment().installed() as env:
            env.app.null_array = True
            code, report, captures = env.run_driver()
            self.assertEqual(code, 1)
            self.assertEqual(report["isolation_gate"], "refused")
            self.assertEqual(env.cache_calls, [])
            self.assertEqual(env.app.open_calls, [])
            self.assertEqual(env.app.close_calls, [])
            self.assertEqual(len(captures), 1)

    def test_any_initial_document_refuses_without_touching_it(self):
        with Environment().installed() as env:
            foreign = Document("C:/foreign/hidden.SLDPRT", 1)
            env.app.documents.append(foreign)
            code, report, _ = env.run_driver()
            self.assertEqual(code, 1)
            self.assertEqual(report["isolation_gate"], "refused")
            self.assertEqual(env.cache_calls, [])
            self.assertEqual(env.app.close_calls, [])
            self.assertEqual(env.app.documents, [foreign])

    def test_initial_user_control_must_be_actual_true(self):
        for value in (False, None, 1, ProbeError("unreadable UserControl")):
            with self.subTest(value_type=type(value).__name__), Environment().installed() as env:
                env.app.control = value
                code, report, captures = env.run_driver()
                self.assertEqual(code, 1)
                self.assertEqual(report["isolation_gate"], "refused")
                self.assertEqual(env.cache_calls, [])
                self.assertEqual(env.app.close_calls, [])
                self.assertEqual(len(captures), 1)

    def test_boolean_document_count_cannot_certify_empty(self):
        with Environment().installed() as env:
            env.app.count_override = True
            code, report, captures = env.run_driver()
            self.assertEqual(code, 1)
            self.assertEqual(report["isolation_gate"], "refused")
            self.assertEqual(env.cache_calls, [])
            self.assertEqual(env.app.close_calls, [])
            self.assertEqual(len(captures), 1)

    def test_actual_empty_user_control_true_observes_and_closes_drawing_first(self):
        with Environment().installed() as env:
            code, report, captures = env.run_driver()
            self.assertEqual(code, 0)
            self.assertEqual(report["status"], "observed")
            self.assertEqual(report["native_ship"], "NOT_EVALUATED")
            self.assertEqual([row[1] for row in env.app.open_calls], [1, 3])
            self.assertEqual(env.app.close_calls, ["sm-summing-lever.SLDDRW", "sm-summing-lever.SLDPRT"])
            self.assertEqual(env.app.documents, [])
            self.assertEqual(captures, [])

    def test_drawing_close_auto_unloads_part_without_stale_second_close(self):
        with Environment().installed() as env:
            env.app.auto_unload_part = True
            code, report, _ = env.run_driver()
            self.assertEqual(code, 0)
            self.assertEqual(env.app.close_calls, ["sm-summing-lever.SLDDRW"])
            self.assertEqual(report["closures"][1]["status"], "already_unloaded")

    def test_each_open_requires_actual_read_only_readback(self):
        for kind in (1, 3):
            for value in (False, None, ProbeError("readonly unreadable")):
                with self.subTest(kind=kind, value_type=type(value).__name__), Environment().installed() as env:
                    env.app.readonly[kind] = value
                    code, report, captures = env.run_driver()
                    self.assertEqual(code, 1)
                    self.assertEqual(env.diagnostic_calls, 0)
                    self.assertFalse(report["collection_completed"])
                    self.assertEqual(len(captures), 1)

    def test_unowned_new_document_blocks_every_close(self):
        with Environment().installed() as env:
            foreign = Document("C:/foreign/new-hidden.SLDPRT", 1)
            env.after_diagnostic = lambda: env.app.documents.append(foreign)
            code, report, captures = env.run_driver()
            self.assertEqual(code, 1)
            self.assertTrue(report["collection_completed"])
            self.assertEqual(env.app.close_calls, [])
            self.assertIn(foreign, env.app.documents)
            self.assertEqual(len(captures), 1)
            self.assertTrue(all(row["status"] == "stranded_owned" for row in captures[0]["closures"]))

    def test_cleanup_only_saveflag_failure_keeps_actual_traceback_and_exports(self):
        with Environment().installed() as env:
            primary = BrokenText()
            env.after_diagnostic = lambda: setattr(env.app.documents[0], "dirty", primary)
            code, report, captures = env.run_driver()
            self.assertEqual(code, 1)
            self.assertEqual(report["runner_exit_code"], 0)
            self.assertTrue(report["collection_completed"])
            self.assertEqual(env.app.close_calls, [])
            self.assertEqual(len(captures), 1)
            capture = captures[0]
            self.assertEqual(capture["primary_failure"]["type"], "BrokenText")
            self.assertEqual(capture["primary_failure"]["message"], "<exception text unavailable>")
            self.assertTrue(any(frame["function"] == "GetSaveFlag" for frame in capture["primary_traceback"]["frames"]))
            self.assertTrue(all(row["status"] == "stranded_owned" for row in capture["closures"]))

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
            self.assertEqual(captures[0]["closures"][1]["status"], "stranded_owned")

    def test_unsupported_identity_cannot_authorize_close(self):
        with Environment().installed() as env:
            env.app.identity_override = -1
            code, report, captures = env.run_driver()
            self.assertEqual(code, 1)
            self.assertEqual(env.app.close_calls, [])
            self.assertTrue(any(row.get("raw") == -1 for row in report["identity_comparisons"]))
            self.assertEqual(len(captures), 1)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--driver", type=Path, default=DRIVER_PATH)
    parser.add_argument("--helper", type=Path, default=HELPER_PATH)
    args, unittest_args = parser.parse_known_args()
    DRIVER_PATH, HELPER_PATH = args.driver.resolve(strict=True), args.helper.resolve(strict=True)
    unittest.main(argv=[sys.argv[0], *unittest_args])
