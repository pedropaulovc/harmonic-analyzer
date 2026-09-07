"""Attach-only, single-thread native measurements for the crank resolver."""

from __future__ import annotations

import argparse
from collections import defaultdict
from contextlib import ExitStack
import hashlib
import json
import os
from pathlib import Path
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
    import _drawing_entities as candidate
    import draw_crank_arm as recipe

    adapter.ownership.register_directory(directory)
    report = {"status": "running", "mode": mode, "samples": []}
    path = directory / "measurements.json"
    try:
        report["session"] = {
            "pid": int(adapter.swApp.GetProcessID()),
            "revision": str(adapter.swApp.RevisionNumber()),
            "inventory": adapter.ownership.evidence(),
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
        report["warmup"] = {}
        reference = resolve_sample(baseline, model, recipe.ENTITY_ROLES, "none", report["warmup"])
        order = "A" if mode == "profile" else "ABBA" * 3
        for index, variant in enumerate(order):
            row = {"index": index, "variant": variant, "status": "running"}
            report["samples"].append(row)
            persist_report(path, report)
            try:
                bank = resolve_sample(
                    baseline if variant == "A" else candidate,
                    model, recipe.ENTITY_ROLES, instrumentation, row,
                )
                row["identity"] = {
                    key: int(adapter.swApp.IsSame(reference[key], entity))
                    for key, entity in bank.items()
                }
                if set(bank) != set(reference) or set(row["identity"].values()) != {1}:
                    raise RuntimeError("variant changed a native role identity")
                if bool(model.GetSaveFlag()) != dirty:
                    raise RuntimeError("read-only resolver changed the dirty flag")
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
        report["final_inventory"] = adapter.ownership.evidence()
        persist_report(path, report)
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
