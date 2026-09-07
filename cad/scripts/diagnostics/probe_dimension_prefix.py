"""One real prefix-helper call on an owned cone-tip part copy; never save/export.

Native execution requires separate review and an explicit existing-PID seat grant.
Prefix text and its definition (GetText 1/5) must become the requested literal;
all other text compartments, numeric visibility and the five required source
dimension values/tolerances remain exact. This proves storage only, not printing
or persistence after save. The source SHA is supplied explicitly, never repinned.
"""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import shutil
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "cad/scripts"))

from _common import _early_bound, check  # noqa: E402
import _drawing_marks as marks  # noqa: E402
import _telemetry  # noqa: E402
from diagnostics import benchmark_drawing_recipes as benchmark  # noqa: E402
from diagnostics._owned_native_documents import run_copy_diagnostic  # noqa: E402
from diagnostics._owned_native_session import require_owned_diagnostic_environment  # noqa: E402
from diagnostics._source_dimension_snapshot import display_presentation  # noqa: E402
from diagnostics.probe_datum_policy_recipes import (  # noqa: E402
    adapter_fingerprints,
    helper_fingerprints,
    source_dimensions,
)
from diagnostics.probe_drawing_attachments import file_digest  # noqa: E402

FEATURE, DIMENSION = "BodyProfile", "BodyDiaDim"
PREFIX = "PREFIX CONTROL "


def same(app, expected, actual, label):
    if expected is None or actual is None:
        raise RuntimeError(f"{label}: null native object")
    result = app.IsSame(expected, actual)
    if type(result) is not int or result != 1:
        raise RuntimeError(f"{label}: native IsSame returned {result!r}")
    return result


def current(adapter, model, path):
    """Immediate mutation barrier, not merely equal document filenames."""
    adapter.ownership.assert_current_owned()
    app = adapter.swApp
    same(app, model, adapter.currentModel, "current owned part")
    same(app, model, app.ActiveDoc, "active owned part")
    same(app, model, app.GetOpenDocumentByName(str(path)), "named owned part")
    kind = model.GetType()
    if (
        type(kind) is not int
        or kind != 1
        or Path(model.GetPathName()).resolve() != path
    ):
        raise RuntimeError("wrong owned part path/kind")
    flag = model.GetSaveFlag()
    if type(flag) is not bool:
        raise RuntimeError("native source dirty flag is not Boolean")
    return flag


def capture(adapter, model, path, evidence):
    """Fresh exact named source/display handles; getters have their own bracket."""
    evidence["dirty_before_getters"] = current(adapter, model, path)
    errors, handles = [], None
    try:
        values, handles = source_dimensions(model, "cone_tip_adjuster", path)
        display, dimension = marks._named_dimension(adapter, FEATURE, DIMENSION)
        display = _early_bound(display, "IDisplayDimension")
        name = f"{DIMENSION}@{FEATURE}"
        same(adapter.swApp, handles[name], dimension, "named source dimension")
        full_name = dimension.FullName
        if full_name != f"{name}@{path.stem}.Part":
            raise RuntimeError(f"wrong exact source dimension owner: {full_name!r}")
        presentation = display_presentation(display)
        evidence.update(source=values, full_name=full_name, display=presentation)
        if "exclusion" in presentation["text"]:
            raise RuntimeError("prefix control does not support hole callouts")
    except Exception as error:
        evidence["getter_error"] = repr(error)
        errors.append(error)
    finally:
        try:
            evidence["dirty_after_getters"] = current(adapter, model, path)
            if evidence["dirty_before_getters"] != evidence["dirty_after_getters"]:
                raise RuntimeError("source getter bank changed the dirty flag")
        except Exception as error:
            evidence["getter_guard_error"] = repr(error)
            errors.append(error)
    if len(errors) == 1:
        raise errors[0]
    if errors:
        raise ExceptionGroup("source getter and ownership failures", errors)
    return handles


def require_transition(app, before, after, old_handles, new_handles):
    if before["source"] != after["source"] or before["full_name"] != after["full_name"]:
        raise RuntimeError(
            "prefix helper changed source values/tolerances/configuration"
        )
    if old_handles.keys() != new_handles.keys():
        raise RuntimeError("source dimension handle inventory changed")
    identity = {
        name: same(app, handle, new_handles[name], name)
        for name, handle in old_handles.items()
    }
    expected = {**before["display"], "text": dict(before["display"]["text"])}
    for part in ("1", "5"):
        expected["text"][part] = PREFIX
    if after["display"] != expected:
        raise RuntimeError("prefix/definition or another text/visibility field differs")
    return identity


async def probe(adapter, source, expected_hash, candidate, report_root):
    if benchmark.revision("HEAD") != candidate:
        raise RuntimeError("prefix control must run the exact current candidate")
    directory = Path(tempfile.mkdtemp(prefix="dimension-prefix-", dir=report_root))
    copied = directory / f"cone-tip-{directory.name}.SLDPRT"
    report_path = directory / "prefix.json"
    report = {
        "status": "running",
        "candidate": candidate,
        "source": str(source),
        "copy": str(copied),
        "dimension": f"{DIMENSION}@{FEATURE}",
        "requested_prefix": PREFIX,
        "expected_sha256": expected_hash,
        "scope": "one helper call on owned PART; immediate/redraw storage; no save/export",
        "helpers": helper_fingerprints(),
        "adapter": adapter_fingerprints(),
    }
    errors = []

    def checkpoint():
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    def hashes(phase):
        values = {str(path): file_digest(path) for path in (source, copied)}
        report.setdefault("hashes", {})[phase] = values
        if any(value != expected_hash for value in values.values()):
            raise RuntimeError(f"{phase}: original/copy disk SHA changed")

    checkpoint()
    _telemetry.info("owned dimension-prefix control", report=str(report_path))
    try:
        adapter.ownership.register_directory(directory)
        adapter.ownership.register_source(source)
        report["original_before"] = file_digest(source)
        if report["original_before"] != expected_hash:
            raise RuntimeError("original source differs from the reviewed SHA")
        shutil.copy2(source, copied)
        hashes("copied")
        check("open owned prefix part", await adapter.open_model(str(copied)))
        model = _early_bound(adapter.currentModel, "IModelDoc2")
        before = report["before"] = {}
        old_handles = capture(adapter, model, copied, before)
        if before["dirty_before_getters"] or before["dirty_after_getters"]:
            raise RuntimeError("prefix control requires a clean opened copy")
        if before["display"]["text"]["1"] == PREFIX:
            raise RuntimeError("prefix positive control requires a changed literal")
        checkpoint()
        current(adapter, model, copied)
        started = time.perf_counter()
        try:
            report["helper_return"] = marks.set_dimension_prefix(
                adapter, FEATURE, DIMENSION, PREFIX
            )
        except Exception as error:
            report["helper_error"] = repr(error)
            errors.append(error)
        finally:
            report["helper_seconds"] = time.perf_counter() - started
        immediate = report["immediate"] = {}
        new_handles = capture(adapter, model, copied, immediate)
        checkpoint()
        if errors:
            raise errors[0]
        report["immediate_identity"] = require_transition(
            adapter.swApp, before, immediate, old_handles, new_handles
        )
        current(adapter, model, copied)
        model.GraphicsRedraw2()  # documented display boundary; no rebuild/save
        after = report["after_redraw"] = {}
        final_handles = capture(adapter, model, copied, after)
        report["after_redraw_identity"] = require_transition(
            adapter.swApp, before, after, old_handles, final_handles
        )
        hashes("before_close")
    except Exception as error:
        if not any(error is item for item in errors):
            errors.append(error)
    finally:
        # Existing helper knows which documents this callback owns; baseline
        # documents are never candidates, even if the active document changed.
        try:
            await adapter.close_owned_documents()
        except Exception as error:
            report["cleanup_error"] = repr(error)
            errors.append(error)
        for label, operation in (
            ("final_hash", lambda: hashes("after_close")),
            (
                "helper_guard",
                lambda: benchmark.check_fingerprints(
                    report["helpers"], helper_fingerprints(), "prefix runtime helpers"
                ),
            ),
            (
                "adapter_guard",
                lambda: benchmark.check_fingerprints(
                    report["adapter"], adapter_fingerprints(), "actual prefix adapter"
                ),
            ),
        ):
            try:
                operation()
            except Exception as error:
                report[f"{label}_error"] = repr(error)
                errors.append(error)
        report.update(
            status="failed" if errors else "passed", errors=[repr(e) for e in errors]
        )
        checkpoint()
    if len(errors) == 1:
        raise errors[0]
    if errors:
        raise ExceptionGroup("prefix control and final guards failed", errors)
    return {"report": str(report_path)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--expected-sha256", required=True)
    parser.add_argument("--candidate", default="HEAD")
    parser.add_argument("--report-root", type=Path, default=ROOT / "cad/out/reports")
    parser.add_argument("--worker", action="store_true")
    args = parser.parse_args(argv)
    require_owned_diagnostic_environment()
    pid = os.environ.get("HARMONIC_DIAGNOSTIC_SW_PID", "")
    if not pid.isdecimal() or int(pid) <= 0:
        raise ValueError("prefix control requires the explicitly granted native PID")
    if os.environ.get("HARMONIC_REMOTE_CACHE_MODE") != "off":
        raise ValueError("prefix control requires remote cache off")
    if len(args.expected_sha256) != 64 or any(
        c not in "0123456789abcdef" for c in args.expected_sha256
    ):
        raise ValueError("expected SHA must be 64 lowercase hexadecimal characters")
    source = args.source.resolve(strict=True)
    if source.suffix.upper() != ".SLDPRT":
        raise ValueError("prefix source must be a native PART")
    candidate = benchmark.revision(args.candidate)
    if candidate != benchmark.revision("HEAD"):
        raise ValueError("candidate must be the exact current helper revision")
    if not args.worker:
        import dodo

        dodo._run(
            [
                sys.executable,
                str(Path(__file__).resolve()),
                "--worker",
                "--source",
                str(source),
                "--expected-sha256",
                args.expected_sha256,
                "--candidate",
                candidate,
                "--report-root",
                str(args.report_root.resolve()),
            ],
            "owned dimension prefix control",
            com=True,
            log_stem="dimension-prefix",
        )
        return 0
    args.report_root.mkdir(parents=True, exist_ok=True)
    return run_copy_diagnostic(
        lambda adapter: probe(
            adapter, source, args.expected_sha256, candidate, args.report_root.resolve()
        )
    )


if __name__ == "__main__":
    raise SystemExit(main())
