"""Read native crankshaft edge curves on one uniquely named owned bytecopy.

No drawing, selection, conversion, BREP write, rebuild, save or export. Enumerate
one solid body (at most 256 edges); preserve line/circle positive controls and
PinHole feature/face membership. This does not yet prove drawing-context or
cold-reopen curve equality. Native execution requires a reviewed frozen source
and an explicit COM seat grant; AUTOSTART=0 and an expected PID are mandatory.
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

from _common import _early_bound, _feature_by_name, check  # noqa: E402
from diagnostics import probe_datum_policy_recipes as pilot  # noqa: E402
from diagnostics import _raw_edge_curve as raw  # noqa: E402
from diagnostics._owned_native_documents import run_copy_diagnostic  # noqa: E402
from diagnostics._owned_native_session import require_owned_diagnostic_environment  # noqa: E402
from diagnostics.probe_drawing_attachments import file_digest  # noqa: E402


def same(app, first, second):
    result = app.IsSame(first, second)
    raw.integer(result, 0, 1, "native IsSame")
    return result == 1


def capture_edges(adapter, report, checkpoint):
    model = adapter.currentModel
    bodies = raw.sequence(
        _early_bound(model, "IPartDoc").GetBodies2(0, False),
        label="solid bodies",
        minimum=1,
        maximum=1,
    )
    edges = raw.sequence(
        _early_bound(bodies[0], "IBody2").GetEdges(), label="body edges", maximum=256
    )
    feature = _feature_by_name(adapter, "PinHole")
    faces = raw.sequence(feature.GetFaces(), label="PinHole faces", maximum=64)
    report["feature"] = {"name": feature.Name, "face_count": len(faces)}
    if feature.Name != "PinHole":
        raise RuntimeError("named cross-hole feature changed")
    rows = report["edges"] = []
    for index, edge in enumerate(edges):
        row = {"index": index, "status": "reading"}
        rows.append(row)
        started = time.perf_counter()
        try:
            edge = _early_bound(edge, "IEdge")
            adjacent = raw.sequence(
                edge.GetTwoAdjacentFaces2(),
                label="adjacent faces",
                minimum=2,
                maximum=2,
            )
            row["PinHole_face_indices"] = [
                face_index
                for face_index, face in enumerate(faces)
                if any(
                    item is not None and same(adapter.swApp, face, item)
                    for item in adjacent
                )
            ]
            row["adjacent_surfaces"] = surfaces = []
            for face in adjacent:
                if face is None:
                    surfaces.append(None)
                    continue
                surface = _early_bound(
                    _early_bound(face, "IFace2").GetSurface(), "ISurface"
                )
                item = {
                    "identity": surface.Identity(),
                    "is_cylinder": surface.IsCylinder(),
                }
                surfaces.append(item)
                raw.integer(item["identity"], 4001, 4010, "surface identity")
                raw.boolean(item["is_cylinder"], "cylinder")
                if item["is_cylinder"]:
                    item["parameters"] = surface.CylinderParams
                    raw.numbers(item["parameters"], 7, "cylinder parameters")
            raw.read_edge(edge, row)
            row["status"] = "captured"
        except Exception as error:
            row.update(status="failed", error=repr(error))
        finally:
            row["seconds"] = time.perf_counter() - started
            checkpoint()
    report["coverage"] = {
        "line": [
            r["index"] for r in rows if r.get("existing_geometry", (None,))[0] == "line"
        ],
        "circle": [
            r["index"]
            for r in rows
            if r.get("existing_geometry", (None,))[0] == "circle"
        ],
        "PinHole_nonanalytic": [
            r["index"]
            for r in rows
            if r.get("PinHole_face_indices")
            and r.get("is_line") is False
            and r.get("is_circle") is False
        ],
    }
    if any(not indices for indices in report["coverage"].values()):
        raise RuntimeError("native line/circle/PinHole nonanalytic coverage incomplete")
    if any(row["status"] != "captured" for row in rows):
        raise RuntimeError(
            "one or more recorded edge call shapes failed; inspect raw evidence"
        )


async def probe(adapter, source, expected_hash, report_root):
    source = source.resolve(strict=True)
    report_root.mkdir(parents=True, exist_ok=True)
    directory = Path(tempfile.mkdtemp(prefix="crankshaft-curves-", dir=report_root))
    report_path = directory / "curves.json"
    copied = directory / f"crankshaft-{directory.name}.SLDPRT"
    report = {
        "status": "running",
        "source": str(source),
        "copy": str(copied),
        "expected_sha256": expected_hash,
        "errors": [],
        "final_guard_errors": [],
    }
    errors = []
    started = time.perf_counter()

    def checkpoint():
        report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    try:
        adapter.ownership.register_directory(directory)
        adapter.ownership.register_source(source)
        report["helpers"] = pilot.helper_fingerprints()
        report["adapter"] = pilot.adapter_fingerprints()
        report["revision"] = pilot.benchmark.revision("HEAD")
        report["source_before"] = file_digest(source)
        if report["source_before"] != expected_hash:
            raise RuntimeError(
                "original source hash differs from the pinned crankshaft"
            )
        shutil.copy2(source, copied)
        report["copy_before"] = file_digest(copied)
        if report["copy_before"] != expected_hash:
            raise RuntimeError("owned bytecopy differs from the pinned crankshaft")
        check("open owned curve source", await adapter.open_model(str(copied)))
        adapter.ownership.assert_current_owned()
        model = _early_bound(adapter.currentModel, "IModelDoc2")
        report["dirty_before_read"] = model.GetSaveFlag()
        report["source_dimensions_before"], handles = pilot.source_dimensions(
            model, "crankshaft", copied
        )
        try:
            capture_edges(adapter, report, checkpoint)
        except Exception as error:
            errors.append(error)
            report["errors"].append(repr(error))
        # Retain source/flag readback even when a curve call shape was rejected.
        report["source_dimensions_after"], after_handles = pilot.source_dimensions(
            model, "crankshaft", copied
        )
        report["dirty_after_read"] = model.GetSaveFlag()
        pilot.require_same_source(
            report["source_dimensions_before"],
            report["source_dimensions_after"],
            "curve reads",
            app=adapter.swApp,
            handles_before=handles,
            handles_after=after_handles,
        )
        if (
            report["dirty_before_read"] is not False
            or report["dirty_after_read"] is not False
        ):
            raise RuntimeError(
                "owned source was not clean across the read-only control"
            )
    except Exception as error:
        errors.append(error)
        report["errors"].append(repr(error))
    finally:
        try:
            await adapter.close_owned_documents()
            report["cleanup"] = "owned documents closed without save"
        except Exception as error:
            errors.append(error)
            report["cleanup_error"] = repr(error)
        for label, reader, expected in (
            ("helpers_final", pilot.helper_fingerprints, report.get("helpers")),
            ("adapter_final", pilot.adapter_fingerprints, report.get("adapter")),
            ("source_final", lambda: file_digest(source), expected_hash),
            ("copy_final", lambda: file_digest(copied), expected_hash),
        ):
            try:
                actual = reader()
                report[label] = actual
                if actual != expected:
                    raise RuntimeError(f"{label}: immutable input changed")
            except Exception as error:
                errors.append(error)
                report["final_guard_errors"].append(repr(error))
        report["seconds"] = time.perf_counter() - started
        report["status"] = "failed" if errors else "captured"
        checkpoint()
    if errors:
        raise ExceptionGroup("curve diagnostic failed; retained raw evidence", errors)
    return {"curve_report": str(report_path)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument(
        "--expected-sha256", default=pilot.EXPECTED_PART_HASHES["crankshaft"]
    )
    parser.add_argument("--report-root", type=Path, default=ROOT / "cad/out/reports")
    parser.add_argument("--worker", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args(argv)
    require_owned_diagnostic_environment()
    if not os.environ.get("HARMONIC_DIAGNOSTIC_SW_PID", "").isdigit():
        raise RuntimeError("curve control requires an explicit expected native PID")
    if os.environ.get("HARMONIC_REMOTE_CACHE_MODE") != "off":
        raise RuntimeError("curve control requires remote cache off")
    if args.expected_sha256 != pilot.EXPECTED_PART_HASHES["crankshaft"]:
        raise ValueError("curve control accepts only the pinned crankshaft source")
    if args.worker:
        return run_copy_diagnostic(
            lambda adapter: probe(
                adapter, args.source, args.expected_sha256, args.report_root
            )
        )
    import dodo

    dodo._run(
        [
            sys.executable,
            str(Path(__file__).resolve()),
            "--source",
            str(args.source.resolve()),
            "--expected-sha256",
            args.expected_sha256,
            "--report-root",
            str(args.report_root.resolve()),
            "--worker",
        ],
        "crankshaft curve readback",
        log_stem="crankshaft-curves",
        com=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
