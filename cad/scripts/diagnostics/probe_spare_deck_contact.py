"""Read native T18 underside/deck contact in this checkout's saved complete top.

Requires an empty session, explicit existing SW PID, and the parent COM seat.
No save, rebuild, configuration/selection change, export, or persistent application
setting change. Native dependency search restores its working-directory effect.
"""

from __future__ import annotations

import argparse
import math
import os
from pathlib import Path
import re
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT / "cad/scripts"))

from _common import _early_bound  # noqa: E402
from _transforms import ROT_X_NEG90  # noqa: E402
import _telemetry  # noqa: E402
from build_paper_drive_assembly import SPARE_GEAR_POS  # noqa: E402
from harmonic_base_spec import STACK_HEIGHT  # noqa: E402
from diagnostics._owned_native_session import (  # noqa: E402
    require_owned_diagnostic_environment,
    run_owned_diagnostic,
)
from diagnostics.probe_assembly_health_targets import (  # noqa: E402
    OwnedAssembly,
    checkpoint,
    digest,
)

# Explicit numerical acceptance bounds, not a claimed kernel accuracy. Raw
# observations are retained without rounding. This is not a bbox/contact proxy.
CONTACT_M = 1e-8  # 0.00001 mm
DIRECTION = 1e-10


def bound(value, interface):
    if value is None:
        raise RuntimeError(f"missing native {interface}")
    return _early_bound(value, interface)


def doubles(value, size, label):
    if not isinstance(value, (tuple, list)) or len(value) != size:
        raise RuntimeError(f"{label}: expected {size} native doubles, got {value!r}")
    if any(type(item) is not float or not math.isfinite(item) for item in value):
        raise RuntimeError(f"{label}: malformed/nonfinite native doubles: {value!r}")
    return tuple(value)


def native_bool(value, label):
    if type(value) is not bool:
        raise RuntimeError(f"{label}: expected native Boolean, got {value!r}")
    return value


def native_int(value, label):
    if type(value) is not int:
        raise RuntimeError(f"{label}: expected native integer, got {value!r}")
    return value


def text(value, label):
    if type(value) is not str or not value:
        raise RuntimeError(f"{label}: missing native string: {value!r}")
    return value


def same(app, left, right, label):
    if left is None or right is None or native_int(app.IsSame(left, right), label) != 1:
        raise RuntimeError(f"{label}: native identity differs")


def near(actual, expected, epsilon, label):
    if len(actual) != len(expected) or any(
        abs(a - b) > epsilon for a, b in zip(actual, expected, strict=True)
    ):
        raise RuntimeError(f"{label}: {actual!r} differs from {expected!r}")


def vector(array, point):
    # _assembly.world_point's row-vector convention, using the selected native
    # handle's already-read transform (GetComponentByName only supports top level).
    return tuple(sum(point[i] * array[i * 3 + k] for i in range(3)) for k in range(3))


def world(array, point):
    return tuple(v + t for v, t in zip(vector(array, point), array[9:12], strict=True))


def local(array, point):
    translated = tuple(p - t for p, t in zip(point, array[9:12], strict=True))
    return tuple(
        sum(translated[k] * array[i * 3 + k] for k in range(3)) for i in range(3)
    )


def transform(component):
    array = doubles(
        bound(component.Transform2, "IMathTransform").ArrayData, 16, "Transform2"
    )
    near(array[12:13], (1.0,), 0.0, "unit component scale")
    rows = [array[i : i + 3] for i in (0, 3, 6)]
    for i in range(3):
        for j in range(3):
            near(
                (sum(a * b for a, b in zip(rows[i], rows[j], strict=True)),),
                (float(i == j),),
                DIRECTION,
                "rigid rotation",
            )
    determinant = sum(
        rows[0][i]
        * (
            rows[1][(i + 1) % 3] * rows[2][(i + 2) % 3]
            - rows[1][(i + 2) % 3] * rows[2][(i + 1) % 3]
        )
        for i in range(3)
    )
    near((determinant,), (1.0,), DIRECTION, "proper rotation")
    return array


def component(owner, candidates, filename, parent, configuration=None):
    expected = (
        ROOT
        / "cad/out"
        / ("sldasm" if filename.endswith("SLDASM") else "sldprt")
        / filename
    ).resolve()
    matches = []
    for raw in candidates or ():
        item = bound(raw, "IComponent2")
        path = Path(text(item.GetPathName(), "component path")).resolve()
        if path != expected:
            continue
        cfg = text(item.ReferencedConfiguration, "referenced configuration")
        if configuration is None or cfg == configuration:
            matches.append(item)
    if len(matches) != 1:
        raise RuntimeError(
            f"expected one {filename}/{configuration}, found {len(matches)}"
        )
    item = matches[0]
    actual_parent = item.GetParent()
    if parent is None and actual_parent is not None:
        raise RuntimeError(f"{filename}: expected a top-level component")
    if parent is not None:
        same(owner.app, actual_parent, parent, f"{filename} parent")
    if native_bool(item.IsSuppressed(), "component suppression"):
        raise RuntimeError(f"{filename}: component is suppressed")
    model = bound(item.GetModelDoc2(), "IModelDoc2")
    wanted_kind = 2 if filename.endswith("SLDASM") else 1
    if native_int(model.GetType(), "model type") != wanted_kind:
        raise RuntimeError(f"{filename}: wrong native model type")
    identity = owner.identity(model)
    if identity != (str(expected), wanted_kind):
        raise RuntimeError(
            f"{filename}: referenced model differs from exact resolved input"
        )
    row = {
        "name": text(item.Name2, "component name"),
        "path": str(expected),
        "configuration": text(item.ReferencedConfiguration, "referenced configuration"),
        "model_identity": identity,
        "transform": transform(item),
        "source_sha256": owner.hashes[str(expected)],
    }
    return item, row


def plane_face(owner, item, normal, offset, evidence):
    result = item.GetBodies3(0)  # swSolidBody; early-bound retval + out BodiesInfo
    if not isinstance(result, tuple) or len(result) != 2:
        raise RuntimeError(f"GetBodies3: expected (bodies, info), got {result!r}")
    bodies, info = result
    if (
        not isinstance(bodies, (tuple, list))
        or len(bodies) != 1
        or not isinstance(info, (tuple, list))
        or len(info) != 1
    ):
        raise RuntimeError(
            "expected one configured solid body and matching body-info entry"
        )
    if (
        native_int(info[0], "body info") != 1
    ):  # swNormalBody_e; no assembly-cut variant accepted
        raise RuntimeError(f"expected unchanged normal component body, got {info!r}")
    body = bound(bodies[0], "IBody2")
    if native_int(body.GetType(), "body type") != 0:
        raise RuntimeError("configured component body is not solid")
    faces = body.GetFaces()
    if not isinstance(faces, (tuple, list)) or not faces:
        raise RuntimeError("configured body returned no face array")
    evidence.update(body_info=info, face_count=len(faces), planar_faces=[])
    matches = []
    for index, raw in enumerate(faces):
        face = bound(raw, "IFace2")
        same(owner.app, bound(face, "IEntity").GetComponent(), item, "face component")
        surface = bound(face.GetSurface(), "ISurface")
        if not native_bool(surface.IsPlane(), "surface IsPlane"):
            continue
        parameters = doubles(surface.PlaneParams, 6, "PlaneParams")
        sense = native_bool(face.FaceInSurfaceSense(), "FaceInSurfaceSense")
        outward = tuple(-v if sense else v for v in parameters[:3])
        near(
            (math.dist(outward, (0.0, 0.0, 0.0)),),
            (1.0,),
            DIRECTION,
            "unit face normal",
        )
        row = {
            "face_index": index,
            "plane": parameters,
            "surface_sense": "opposite" if sense else "same",
            "outward_normal": outward,
        }
        evidence["planar_faces"].append(row)
        signed = sum(n * p for n, p in zip(normal, parameters[3:], strict=True))
        if (
            math.dist(outward, normal) <= DIRECTION
            and abs(signed - offset) <= CONTACT_M
        ):
            matches.append((face, row))
    if len(matches) != 1:
        raise RuntimeError(
            f"expected one native support plane {normal}/{offset}, found {len(matches)}"
        )
    face, row = matches[0]
    evidence["selected"] = row
    return face, row


def contact(owner, report):
    owner.assert_active()
    assembly = bound(owner.root, "IAssemblyDoc")
    top = assembly.GetComponents(True)
    paper, paper_row = component(owner, top, "paper-drive.SLDASM", None)
    frame, frame_row = component(owner, top, "frame.SLDASM", None)
    spare, spare_row = component(
        owner, paper.GetChildren(), "transgear-removable.SLDPRT", paper, "T18"
    )
    base, base_row = component(
        owner, frame.GetChildren(), "harmonic-base.SLDPRT", frame
    )
    report["components"] = {
        "paper": paper_row,
        "frame": frame_row,
        "spare": spare_row,
        "base": base_row,
    }
    spare_array, base_array = spare_row["transform"], base_row["transform"]
    near(
        spare_array[:9],
        tuple(v for row in ROT_X_NEG90 for v in row),
        DIRECTION,
        "spare rotation",
    )
    near(
        spare_array[9:12],
        tuple(v / 1000 for v in SPARE_GEAR_POS),
        CONTACT_M,
        "spare position",
    )
    identity = (1.0, 0.0, 0.0, 0.0, 1.0, 0.0, 0.0, 0.0, 1.0)
    for role in ("paper", "frame", "base"):
        near(
            report["components"][role]["transform"][:12],
            (*identity, 0.0, 0.0, 0.0),
            DIRECTION,
            f"{role} root pose",
        )
    report["planes"] = {"spare": {}, "deck": {}}
    underside, under_row = plane_face(
        owner, spare, (0.0, 0.0, -1.0), 0.0, report["planes"]["spare"]
    )
    deck, deck_row = plane_face(
        owner, base, (0.0, 1.0, 0.0), STACK_HEIGHT / 1000, report["planes"]["deck"]
    )
    under_normal = vector(spare_array, under_row["outward_normal"])
    deck_normal = vector(base_array, deck_row["outward_normal"])
    near(
        under_normal,
        tuple(-v for v in deck_normal),
        DIRECTION,
        "opposed support normals",
    )
    under_origin = world(spare_array, under_row["plane"][3:])
    deck_origin = world(base_array, deck_row["plane"][3:])
    separation = sum(
        n * (u - d)
        for n, u, d in zip(deck_normal, under_origin, deck_origin, strict=True)
    )
    report["plane_separation_m"] = separation
    near((separation,), (0.0,), CONTACT_M, "native support planes coplanar")
    # Closest point is on the trimmed IFace2, not its infinite ISurface. The
    # origin may be inside the bore: retain the actual returned boundary point.
    under_point = doubles(
        underside.GetClosestPointOn(0.0, 0.0, 0.0), 5, "underside closest point"
    )
    world_under = world(spare_array, under_point[:3])
    query = local(base_array, world_under)
    deck_point = doubles(deck.GetClosestPointOn(*query), 5, "deck closest point")
    world_deck = world(base_array, deck_point[:3])
    distance = math.dist(world_under, world_deck)
    report["contact"] = {
        "underside_xyzuv": under_point,
        "deck_query_local": query,
        "deck_xyzuv": deck_point,
        "underside_world": world_under,
        "deck_world": world_deck,
        "distance_m": distance,
    }
    near(
        (
            sum(
                n * (p - o)
                for n, p, o in zip(deck_normal, world_under, deck_origin, strict=True)
            ),
        ),
        (0.0,),
        CONTACT_M,
        "trimmed underside point on support plane",
    )
    near((distance,), (0.0,), CONTACT_M, "trimmed native face contact")
    owner.assert_active()
    # Re-resolve from the same top, retaining same-instance proof, not only names.
    final_top = assembly.GetComponents(True)
    final_paper, final_paper_row = component(
        owner, final_top, "paper-drive.SLDASM", None
    )
    final_frame, final_frame_row = component(owner, final_top, "frame.SLDASM", None)
    final_spare, final_spare_row = component(
        owner,
        final_paper.GetChildren(),
        "transgear-removable.SLDPRT",
        final_paper,
        "T18",
    )
    final_base, final_base_row = component(
        owner, final_frame.GetChildren(), "harmonic-base.SLDPRT", final_frame
    )
    for role, old, fresh, row in (
        ("paper", paper, final_paper, final_paper_row),
        ("frame", frame, final_frame, final_frame_row),
        ("spare", spare, final_spare, final_spare_row),
        ("base", base, final_base, final_base_row),
    ):
        same(owner.app, old, fresh, f"unchanged {role} instance")
        if row != report["components"][role]:
            raise RuntimeError(
                f"{role}: component/configuration/transform changed during reads"
            )


def document_state(owner):
    owner.assert_active()
    state = {}
    for path, model in owner.inventory().items():
        dirty = native_bool(model.GetSaveFlag(), "document dirty state")
        manager = bound(model.ConfigurationManager, "IConfigurationManager")
        cfg = text(
            bound(manager.ActiveConfiguration, "IConfiguration").Name,
            "active configuration",
        )
        rebuild = native_int(
            bound(model.Extension, "IModelDocExtension").NeedsRebuild2, "NeedsRebuild2"
        )
        state[str(path)] = {
            "configuration": cfg,
            "dirty": "dirty" if dirty else "clean",
            "needs_rebuild": rebuild,
        }
    if state[str(owner.source)]["needs_rebuild"] != 0:
        raise RuntimeError("saved top requires rebuild; diagnostic will not rebuild it")
    return state


def _raise_recorded_errors(label, errors):
    # Interruptions remain control flow, never members of an ExceptionGroup.
    # Retain secondary failures without replacing the first interruption.
    for error in errors:
        if isinstance(error, Exception):
            continue
        for secondary in errors:
            if secondary is not error:
                error.add_note(f"{label}; additional failure: {secondary!r}")
        raise error
    if errors:
        raise ExceptionGroup(label, errors)


def _record_checkpoint_error(report, errors, error, label):
    # The outer probe can encounter the same persistent write error already
    # retained inside measure's group. Preserve that object's first position.
    pending = list(errors)
    while pending:
        prior = pending.pop()
        if prior is error:
            error.add_note(f"{label} raised the same exception instance again")
            return "already_recorded"
        if isinstance(prior, BaseExceptionGroup):
            pending.extend(prior.exceptions)
    errors.append(error)
    report.setdefault("errors", []).append(repr(error))
    return "new"


def _final_checkpoint(report_path, report, errors, *, phase):
    group = {"phase": phase, "attempts": []}
    report.setdefault("final_checkpoints", []).append(group)
    initial_error = None
    # Any failed write may already have published "passed". Make one failure-
    # only write attempt, including ordinary errors, without repeating COM.
    for purpose in ("final", "failure_retry"):
        attempt = {
            "purpose": purpose,
            "report_status": report["status"],
            "outcome": "started",
        }
        group["attempts"].append(attempt)
        try:
            checkpoint(report_path, report)
        except BaseException as error:
            attempt.update(outcome="failed", error=repr(error))
            report["status"] = "failed"
            identity = _record_checkpoint_error(
                report, errors, error, f"{phase} {purpose} checkpoint"
            )
            if identity == "already_recorded":
                attempt["exception_identity"] = (
                    "same_as_initial" if error is initial_error else identity
                )
            if initial_error is None:
                initial_error = error
            continue
        # The file records "started" for its own write. Only an enclosing write
        # can persist this returned outcome; do not add a third evidence write.
        attempt["outcome"] = "returned"
        return


async def measure(adapter, report, report_path, expected_sha):
    owner = None
    errors = []
    completed = False
    try:
        source = (ROOT / "cad/out/sldasm/harmonic-analyzer.SLDASM").resolve(strict=True)
        if digest(source) != expected_sha:
            raise RuntimeError("saved top SHA differs from explicit expected input")
        owner = OwnedAssembly(adapter, source)
        report.update(
            source=str(source),
            input_hashes=owner.hashes,
            baseline_inventory=sorted(map(str, owner.inventory())),
        )
        checkpoint(report_path, report)
        await owner.open()
        report["before"] = document_state(owner)
        checkpoint(report_path, report)
        contact(owner, report)
        report["after"] = document_state(owner)
        if report["after"] != report["before"]:
            raise RuntimeError("native inspection changed document state")
        completed = True
    except BaseException as error:
        errors.append(error)
    finally:
        if owner is not None:
            try:
                await owner.close()
                report["final_inventory"] = sorted(map(str, owner.inventory()))
            except BaseException as error:
                errors.append(error)
            try:
                report["inputs"] = owner.input_evidence()
                if any(
                    row["status"] != "unchanged" for row in report["inputs"].values()
                ):
                    raise RuntimeError("saved input hashes changed or unreadable")
            except BaseException as error:
                errors.append(error)
        report.update(
            status="passed" if completed and not errors else "failed",
            errors=[repr(e) for e in errors],
        )
        _final_checkpoint(report_path, report, errors, phase="measure")
    _raise_recorded_errors("spare seating diagnostic failed", errors)


async def probe(adapter, directory, expected_sha):
    import solidworks_mcp.adapters.pywin32_adapter as runtime_adapter

    if (
        not Path(runtime_adapter.__file__)
        .resolve()
        .is_relative_to(ROOT / "SolidworksMCP-python")
        or Path(sys.prefix).resolve() != ROOT / ".venv"
    ):
        raise RuntimeError(
            "native probe requires this checkout's pinned adapter and own venv"
        )
    report_path = directory / "contact.json"
    report = {
        "status": "running",
        "root": str(ROOT),
        "python": sys.executable,
        "root_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT, text=True
        ).strip(),
        "adapter_commit": subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=ROOT / "SolidworksMCP-python", text=True
        ).strip(),
        "diagnostic_sha256": digest(Path(__file__)),
        "expected_top_sha256": expected_sha,
        "pid": adapter.swApp.GetProcessID(),
        "revision": adapter.swApp.RevisionNumber(),
        "scope": "saved active top configuration; T18 component planes and one trimmed-face contact witness; no whole-body clearance/render proof",
        "contact_limit_m": CONTACT_M,
        "direction_limit": DIRECTION,
    }
    started = None
    errors = []
    completed = False
    try:
        started = time.perf_counter()
        await measure(adapter, report, report_path, expected_sha)
        completed = True
    except BaseException as error:
        errors.append(error)
    finally:
        try:
            if started is not None:
                report["inspection_and_owned_cleanup_seconds"] = (
                    time.perf_counter() - started
                )
        except BaseException as error:
            errors.append(error)
        if not completed or errors:
            report["status"] = "failed"
        report.setdefault("errors", []).extend(repr(error) for error in errors)
        _final_checkpoint(report_path, report, errors, phase="probe")
    _raise_recorded_errors("spare seating inspection/report failed", errors)
    return {"report": str(report_path)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--top-sha256", required=True)
    parser.add_argument("--worker", action="store_true")
    args = parser.parse_args()
    require_owned_diagnostic_environment()
    if os.environ.get("HARMONIC_REMOTE_CACHE_MODE") != "off" or not re.fullmatch(
        r"[1-9][0-9]*", os.environ.get("HARMONIC_DIAGNOSTIC_SW_PID", "")
    ):
        raise RuntimeError("requires cache off and an explicit positive running SW PID")
    if not re.fullmatch(r"[0-9a-f]{64}", args.top_sha256):
        raise ValueError("expected top SHA must be 64 lowercase hexadecimal digits")
    if not args.worker:
        sys.path.insert(0, str(ROOT))
        import dodo

        label = "saved top spare seating"
        with dodo._com_seat(label) as waited:
            with _telemetry.span(f"task {label}", label=label, seat_wait_s=waited):
                dodo._exec(
                    [
                        sys.executable,
                        str(Path(__file__).resolve()),
                        "--top-sha256",
                        args.top_sha256,
                        "--worker",
                    ],
                    label,
                )
        return 0
    reports = ROOT / "cad/out/reports"
    reports.mkdir(parents=True, exist_ok=True)
    directory = Path(tempfile.mkdtemp(prefix="spare-deck-contact-", dir=reports))
    return run_owned_diagnostic(
        lambda adapter: probe(adapter, directory, args.top_sha256)
    )


if __name__ == "__main__":
    raise SystemExit(main())
