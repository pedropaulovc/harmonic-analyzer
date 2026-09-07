"""Attach-only, single-thread native measurements for the crank resolver."""

from __future__ import annotations

import argparse
from collections import defaultdict
from contextlib import ExitStack
import hashlib
import json
import os
from pathlib import Path
import platform
import subprocess
import sys
import tempfile
import threading
import time
from types import ModuleType
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "cad/scripts"))

from _common import _early_bound, check  # noqa: E402
from diagnostics._owned_native_documents import run_copy_diagnostic  # noqa: E402
from diagnostics._owned_native_session import require_owned_diagnostic_environment  # noqa: E402
from diagnostics.probe_crank_arm_entities import persist_report, sha  # noqa: E402

BASE = "19431a0088519bd8755b941a3da73a699c0ed7e1"
SOURCE = ROOT / "cad/out/sldprt/crank-arm.SLDPRT"
TOKEN = SOURCE.with_name(".crank-arm.execution")


class NativeReads:
    """Time disjoint binding, method invocation and property-read intervals.

    Proxies exist only in this instrumented experiment. Results are unwrapped
    before native identity checks. No COM call leaves the invoking thread.
    """

    def __init__(self):
        self.thread = threading.get_ident()
        self.rows = defaultdict(lambda: {"count": 0, "seconds": 0.0, "failures": 0})

    def call(self, name, operation):
        if threading.get_ident() != self.thread:
            raise RuntimeError("native profiler left its invoking thread")
        row = self.rows[name]
        row["count"] += 1
        started = time.perf_counter()
        try:
            return operation()
        except Exception:
            row["failures"] += 1
            raise
        finally:
            row["seconds"] += time.perf_counter() - started

    def bind(self, value, interface):
        bound = self.call(
            f"bind.{interface}", lambda: _early_bound(unwrap(value), interface)
        )
        return NativeProxy(bound, interface, self)


class NativeProxy:
    def __init__(self, native, interface, reads):
        self.native, self.interface, self.reads = native, interface, reads

    def __getattr__(self, name):
        label = f"{self.interface}.{name}"
        member = self.reads.call(f"lookup.{label}", lambda: getattr(self.native, name))
        if not callable(member):
            return member
        return lambda *args, **kwargs: self.reads.call(
            f"call.{label}", lambda: member(*args, **kwargs)
        )


def unwrap(value):
    return value.native if isinstance(value, NativeProxy) else value


def baseline_module():
    import _drawing_entities as candidate

    source = subprocess.check_output(
        ["git", "show", f"{BASE}:cad/scripts/_drawing_entities.py"], cwd=ROOT
    )
    module = ModuleType("_entity_resolver_accepted_baseline")
    sys.modules[module.__name__] = module
    exec(compile(source, f"{BASE}/_drawing_entities.py", "exec"), module.__dict__)
    # Both variants consume the exact same immutable recipe selectors. Only
    # selector classes are shared; implementations and decoded records are not.
    for name in ("CircleEdge", "LineEdge", "ModelVertex", "FeatureFace", "FaceBoundary", "EdgeAdjacentFace"):
        setattr(module, name, getattr(candidate, name))
    return module, hashlib.sha256(source).hexdigest()


def resolve_sample(module, model, roles, instrumentation, measurement):
    import _part_pmi

    reads = NativeReads()
    with ExitStack() as stack:
        if instrumentation == "reads":
            stack.enter_context(patch.object(module, "_early_bound", reads.bind))
            stack.enter_context(patch.object(_part_pmi, "_early_bound", reads.bind))
        started = time.perf_counter()
        try:
            resolved = module.ModelEntities(model).resolve(roles)
        finally:
            measurement.update(
                seconds=time.perf_counter() - started, instrumentation=instrumentation,
                reads=dict(reads.rows), thread=reads.thread,
            )
    return {key: unwrap(value) for key, value in resolved.items()}


async def capture(adapter, directory, mode, instrumentation):
    import dodo
    import _drawing_entities as candidate
    import draw_crank_arm as recipe

    adapter.ownership.register_directory(directory)
    report = {"status": "running", "mode": mode, "samples": []}
    path = directory / "measurements.json"
    try:
        report["session"] = {
            "pid": int(adapter.swApp.GetProcessID()),
            "revision": str(adapter.swApp.RevisionNumber()),
            "private_gb": dodo._sw_commit_gb(),
            "inventory": adapter.ownership.evidence(),
        }
        report["inputs"] = {
            "head": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
            "adapter": subprocess.check_output(["git", "-C", "SolidworksMCP-python", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
            "python": sys.executable, "host": platform.node(),
            "recipe_sha256": sha(Path(recipe.__file__)),
            "selectors": {key: repr(value) for key, value in recipe.ENTITY_ROLES.items()},
        }
        if mode == "inventory":
            report["status"] = "passed"
            return {"report": str(path)}
        adapter.ownership.register_source(SOURCE)
        adapter.ownership.register_source(TOKEN)
        source_hash = sha(SOURCE)
        if TOKEN.read_text().strip() != source_hash:
            raise RuntimeError("local source differs from its genuine execution token")
        report["source_sha256"] = source_hash
        report["resolver_sha256"] = sha(Path(candidate.__file__))
        baseline, report["baseline_resolver_sha256"] = baseline_module()
        check("open local crank source", await adapter.open_model(str(SOURCE)))
        model = _early_bound(adapter.currentModel, "IModelDoc2")
        if str(model.ConfigurationManager.ActiveConfiguration.Name) != "Default":
            raise RuntimeError("resolver experiment requires the Default configuration")
        if Path(model.GetPathName()).resolve() != SOURCE.resolve():
            raise RuntimeError("resolver experiment has the wrong source")
        dirty = bool(model.GetSaveFlag())

        def stationary_input():
            recipe.require_source(adapter, model)
            if int(adapter.swApp.IsSame(adapter.currentModel, model)) != 1:
                raise RuntimeError("resolver current source changed")
            if bool(model.GetSaveFlag()) != dirty:
                raise RuntimeError("read-only resolver changed the dirty flag")
            if mode != "abba":
                return {}
            from diagnostics.probe_drawing_attachments import views

            drawing = adapter.swApp.GetOpenDocumentByName(str(recipe.OUTPUTS.slddrw))
            if drawing is None:
                raise RuntimeError("ABBA requires the warmed local production drawing open")
            identities = {}
            for name, view in views(_early_bound(drawing, "IModelDoc2")).items():
                identities[name] = int(adapter.swApp.IsSame(view.ReferencedDocument, model))
                if identities[name] != 1 or str(view.ReferencedConfiguration) != "Default":
                    raise RuntimeError(f"{name}: production view source/configuration changed")
            if len(identities) != 4:
                raise RuntimeError("ABBA requires all four production views")
            return identities

        report["stationary_input"] = stationary_input()
        report["warmup"] = {}
        reference = resolve_sample(baseline, model, recipe.ENTITY_ROLES, "none", report["warmup"])
        order = "A" if mode == "profile" else "ABBA" * 3
        for index, variant in enumerate(order):
            row = {"index": index, "variant": variant, "status": "running"}
            report["samples"].append(row)
            persist_report(path, report)
            try:
                row["views_before"] = stationary_input()
                bank = resolve_sample(
                    baseline if variant == "A" else candidate,
                    model, recipe.ENTITY_ROLES, instrumentation, row,
                )
                row["identity"] = {}
                if set(bank) != set(reference):
                    raise RuntimeError("variant changed the role key set")
                for key, entity in bank.items():
                    row["identity"][key] = int(adapter.swApp.IsSame(reference[key], entity))
                if set(row["identity"].values()) != {1}:
                    raise RuntimeError("variant changed a native role identity")
                row["views_after"] = stationary_input()
                row["status"] = "passed"
            except Exception as error:
                row.update(status="failed", error=repr(error))
                raise
            finally:
                persist_report(path, report)
        report["status"] = "passed"
    except Exception as error:
        report.update(status="failed", error=repr(error))
        raise
    finally:
        primary = sys.exception()
        errors = []
        for name, read in (
            ("final_inventory", adapter.ownership.evidence),
            ("private_gb_after", dodo._sw_commit_gb),
        ):
            try:
                report[name] = read()
            except Exception as error:
                report[name] = {"error": repr(error)}
                errors.append(error)
        if errors:
            report.update(status="failed", final_errors=[repr(error) for error in errors])
        try:
            persist_report(path, report)
        except Exception as error:
            errors.append(error)
        if errors:
            raise ExceptionGroup(
                "resolver experiment and final evidence failures",
                ([primary] if primary else []) + errors,
            ) from None
    return {"report": str(path)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("inventory", "profile", "abba"))
    parser.add_argument("--instrumentation", choices=("reads", "none"), default="reads")
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    require_owned_diagnostic_environment()
    if not args.worker:
        import dodo

        dodo._run(
            [sys.executable, str(Path(__file__).resolve()), args.mode,
             "--instrumentation", args.instrumentation, "--worker"],
            "entity resolver performance", com=True, log_stem="entity-resolver-performance",
        )
        return 0
    if not os.environ.get("HARMONIC_COM_SEAT"):
        raise RuntimeError("resolver experiment worker requires the locked parent")
    reports = ROOT / "cad/out/reports"
    reports.mkdir(parents=True, exist_ok=True)
    directory = Path(tempfile.mkdtemp(prefix="entity-resolver-performance-", dir=reports))
    return run_copy_diagnostic(lambda adapter: capture(adapter, directory, args.mode, args.instrumentation))


if __name__ == "__main__":
    raise SystemExit(main())
