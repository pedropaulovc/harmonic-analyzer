"""COM-conversation no-op replay benchmark (EXPERIMENT BRANCH ONLY; never merge).

Branch ``experiment/com-replay-20261110``. Design: reconcile-adapter-design.md
section 1. One farm leaf (``verify:replay_noop``) that holds the seat and runs
every native step as its own ``run_build`` subprocess:

0. clean build, unrecorded, outputs under ``replay-noop/run0`` (W0);
1. clean build recorded -> ``run1`` + ``logs/L1.jsonl.gz`` (W1);
2. clean build recorded -> ``run2`` + ``logs/L2.jsonl.gz`` (W2); K1;
3. replay of L1 with SolidWorks untouched (WR); K2; negative controls
   (another part's script, and L1 with one request float moved 1 ulp); K2b;
4. geometry digests D1/D2 of the two recorded artefacts; K3; K4;
5. rollback walk over a copy of A1 against L1's mass-property read points; K5.

``report.json`` is rewritten after every phase, and every K verdict's evidence
is also logged (bounded, at WARN) because a failed leaf publishes only its task
log. Only infrastructure or soundness faults exit non-zero (phase-0 build
failure, a watchdog exit, a negative control answering NOOP, documents still
open after a native step's own discard, an unwritable report); every other K
failure is a recorded result.

``native digest`` / ``native walk`` are the child entry points (they connect).
``--help`` imports neither pywin32 nor ``_session``.
"""

from __future__ import annotations

import argparse
import contextlib
import dataclasses
import hashlib
import io
import json
import math
import os
import shutil
import subprocess
import sys
import tarfile
import time
import traceback
from collections.abc import Iterator
from enum import StrEnum
from pathlib import Path
from typing import Any

SCRIPTS = Path(__file__).resolve().parents[1]
REPO = SCRIPTS.parents[1]
OUT = REPO / "cad" / "out" / "reports" / "replay-noop"
COM_REPLAY = SCRIPTS / "com_replay.py"
PREFIX = "experiment.replay_noop"
DEFAULT_STEM = "pd_transgear_arm_plate"
DEFAULT_CONTROL_STEM = "pd_transgear_arm"
SCHEMA = 1

_OPEN_SILENT = 1  # swOpenDocOptions_Silent
_DOC_PART = 1  # swDocPART
_SOLID_BODY = 0  # swSolidBody
_ROLL_TO_END = 1  # swMoveRollbackBarTo_e
_ROLL_BEFORE = 3
_ROLL_AFTER = 4
_MASS_ACCURACY = 2
_MOMENT_AT_CENTRE = 0
_ORIGIN_TYPE = "OriginProfileFeature"

# K3 tolerances: _assembly.assembly_geometry_digest rounding, in mm/kg units.
_TOLERANCE = {
    "mass_kg": 1e-6,
    "volume_mm3": 1e-3,
    "area_mm2": 1e-3,
    "com_mm": 1e-4,
    "moi_kgmm2": 1e-4,
    "extreme_mm": 1e-4,
    "dimension_si": 1e-12,
}
_READ_POINT_RTOL = 1e-9
_MASS_MEMBERS = ("Volume", "Mass", "SurfaceArea", "CenterOfMass")
_OBJECT_SAME = 1  # swObjectEquality_e.swObjectSame, ISldWorks.IsSame's answer
# Evidence logged per verdict: bounded so a task log stays readable.
_EVIDENCE_LINES = 45
_EVIDENCE_TOP = 12
_CLIP = 200
# Child timeouts (s): a hung child fails the leaf before the farm leaf timeout.
_RECORD_TIMEOUT = 900
_REPLAY_TIMEOUT = 600
_NATIVE_TIMEOUT = 1200


class Status(StrEnum):
    OK = "ok"
    ERROR = "error"
    SKIPPED = "skipped"


class Scope(StrEnum):
    """What a fatal fault invalidates: the seat (no further native step) or
    only the report's soundness (later phases still run)."""

    SEAT = "seat"
    REPORT = "report"


class Fatal(Exception):
    """An infrastructure or soundness fault that invalidates the report."""

    def __init__(self, reason: str, code: int = 1, scope: Scope = Scope.SEAT):
        super().__init__(reason)
        self.reason = reason
        self.code = code
        self.scope = scope


class Shape(StrEnum):
    """How the generated wrapper exposes a member (call it, or read/write it)."""

    METHOD = "method"
    GET = "get"
    PUT = "put"


# Every COM member the native children call, with the shape the generated
# wrapper (sldworks_2026) gives it on the interface each object is bound to;
# test_com_conversation checks this table against the wrapper.
NATIVE_MEMBERS: tuple[tuple[str, str, Shape], ...] = (
    ("ISldWorks", "OpenDoc6", Shape.METHOD),
    ("ISldWorks", "CloseDoc", Shape.METHOD),
    ("ISldWorks", "GetOpenDocumentByName", Shape.METHOD),
    ("ISldWorks", "IsSame", Shape.METHOD),
    ("ISldWorks", "IActiveDoc2", Shape.GET),
    ("ISldWorks", "CloseAllDocuments", Shape.METHOD),
    ("ISldWorks", "GetFirstDocument", Shape.METHOD),
    ("IModelDoc2", "GetPathName", Shape.METHOD),
    ("IModelDoc2", "GetTitle", Shape.METHOD),
    ("IModelDoc2", "GetNext", Shape.METHOD),
    ("IModelDoc2", "Extension", Shape.GET),
    ("IModelDoc2", "FeatureManager", Shape.GET),
    ("IModelDoc2", "GetEquationMgr", Shape.METHOD),
    ("IModelDoc2", "ForceRebuild3", Shape.METHOD),
    ("IModelDoc2", "FirstFeature", Shape.METHOD),
    ("IModelDocExtension", "CreateMassProperty", Shape.METHOD),
    ("IModelDocExtension", "CreateMassProperty2", Shape.METHOD),
    ("IModelDocExtension", "CustomPropertyManager", Shape.METHOD),
    ("IMassProperty2", "AccuracyLevel", Shape.GET),
    ("IMassProperty2", "AccuracyLevel", Shape.PUT),
    ("IMassProperty2", "Mass", Shape.GET),
    ("IMassProperty2", "Volume", Shape.GET),
    ("IMassProperty2", "SurfaceArea", Shape.GET),
    ("IMassProperty2", "CenterOfMass", Shape.GET),
    ("IMassProperty2", "GetMomentOfInertia", Shape.METHOD),
    ("IMassProperty", "Mass", Shape.GET),
    ("IMassProperty", "Volume", Shape.GET),
    ("IMassProperty", "SurfaceArea", Shape.GET),
    ("IMassProperty", "CenterOfMass", Shape.GET),
    ("IPartDoc", "GetBodies2", Shape.METHOD),
    ("IBody2", "GetMassProperties", Shape.METHOD),
    ("IBody2", "GetExtremePoint", Shape.METHOD),
    ("IBody2", "GetFaceCount", Shape.METHOD),
    ("IBody2", "GetEdgeCount", Shape.METHOD),
    ("IBody2", "GetVertexCount", Shape.METHOD),
    ("IFeature", "Name", Shape.GET),
    ("IFeature", "GetTypeName2", Shape.METHOD),
    ("IFeature", "IsSuppressed", Shape.METHOD),
    ("IFeature", "IsRolledBack", Shape.METHOD),
    ("IFeature", "GetNextFeature", Shape.METHOD),
    ("IFeature", "GetFirstDisplayDimension", Shape.METHOD),
    ("IFeature", "GetNextDisplayDimension", Shape.METHOD),
    ("IDisplayDimension", "GetDimension2", Shape.METHOD),
    ("IDimension", "FullName", Shape.GET),
    ("IDimension", "SystemValue", Shape.GET),
    ("ICustomPropertyManager", "GetNames", Shape.METHOD),
    ("ICustomPropertyManager", "Get6", Shape.METHOD),
    ("IEquationMgr", "GetCount", Shape.METHOD),
    ("IEquationMgr", "Equation", Shape.METHOD),
    ("IFeatureManager", "EditRollback", Shape.METHOD),
)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(
        json.dumps(value, indent=2, sort_keys=True, default=str) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def artefact_name(stem: str) -> str:
    """The dashed .SLDPRT name a part script saves (``_buildgraph.artefact_for``)."""
    return f"{stem.replace('_', '-')}.SLDPRT"


def tree_bytes(root: Path) -> int:
    return (
        sum(p.stat().st_size for p in root.rglob("*") if p.is_file())
        if root.is_dir()
        else 0
    )


# ---------------------------------------------------------------------------
# Parent: the leaf (never connects)
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class ChildRun:
    name: str
    rc: int | None
    wall_seconds: float
    log: str
    timed_out: bool = False

    def to_json(self) -> dict[str, Any]:
        return dataclasses.asdict(self)


class Leaf:
    def __init__(self, stem: str, control_stem: str):
        import _com_conversation as conversation
        import _telemetry
        import _watchdog

        self.conversation = conversation
        self.telemetry = _telemetry
        self.watchdog_codes = {
            _watchdog.EXIT_CRASH,
            _watchdog.EXIT_OP_TIMEOUT,
            _watchdog.EXIT_MODAL_DIALOG,
            _watchdog.EXIT_SEAT_NOT_READY,
        }
        self.stem = stem
        self.control_stem = control_stem
        self.script = SCRIPTS / f"build_{stem}.py"
        self.control_script = SCRIPTS / f"build_{control_stem}.py"
        self.part = artefact_name(stem)
        self.logs = OUT / "logs"
        self.a1 = OUT / "run1" / "sldprt" / self.part
        self.a2 = OUT / "run2" / "sldprt" / self.part
        self.a1_sha: str | None = None
        self.fatal: list[Fatal] = []
        self.report: dict[str, Any] = {
            "schema": SCHEMA,
            "experiment": "COM-conversation no-op replay (design section 1); never merge",
            "stem": stem,
            "control_stem": control_stem,
            "script": self.script.relative_to(REPO).as_posix(),
            "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "phases": {},
            "runs": {},
            "logs": {},
            "replay": None,
            "controls": {},
            "digests": {},
            "walk": None,
            "walls": {},
            "verdicts": {},
            "assumptions": {},
            "seat_safety": {"violations": []},
            "evidence": {},
            "exit": None,
        }

    # -- bookkeeping -------------------------------------------------------------

    def save(self) -> None:
        write_json(OUT / "report.json", self.report)

    @contextlib.contextmanager
    def phase(self, key: str, title: str) -> Iterator[None]:
        started = time.perf_counter()
        row: dict[str, Any] = {"title": title, "status": Status.ERROR.value}
        self.report["phases"][key] = row
        with self.telemetry.span(f"{PREFIX}.{key}", title=title):
            try:
                yield
                row["status"] = Status.OK.value
            except Fatal as exc:
                row.update(error=exc.reason, traceback=traceback.format_exc())
                self.fatal.append(exc)
                self.telemetry.error(f"{key}: FATAL {exc.reason}")
            except Exception as exc:  # noqa: BLE001 - a phase failure is a result
                row.update(
                    error=f"{type(exc).__name__}: {exc}",
                    traceback=traceback.format_exc(),
                )
                self.telemetry.warn(f"{key}: {type(exc).__name__}: {exc}")
            finally:
                row["seconds"] = time.perf_counter() - started
                self.save()

    def skip(self, key: str, title: str, reason: str) -> None:
        self.report["phases"][key] = {
            "title": title,
            "status": Status.SKIPPED.value,
            "reason": reason,
        }
        self.save()

    def evidence(self, key: str, lines: list[str]) -> None:
        """Bounded verdict evidence, logged at WARN because a failed leaf
        publishes only its task log (warnings and errors)."""
        bounded = lines[:_EVIDENCE_LINES]
        if len(lines) > _EVIDENCE_LINES:
            bounded.append(f"  ... {len(lines) - _EVIDENCE_LINES} more in report.json")
        self.report["evidence"][key] = bounded
        self.telemetry.warn("\n".join([f"evidence {key}:", *bounded]))

    def seat_stopped(self) -> bool:
        """Whether a fault makes any further native (seat) step unsafe or moot."""
        return any(fault.scope is Scope.SEAT for fault in self.fatal)

    def child(
        self,
        name: str,
        argv: list[str],
        timeout: float,
        env: dict[str, str] | None = None,
    ) -> ChildRun:
        environment = self.telemetry.inject_env(dict(os.environ, PYTHONHASHSEED="0"))
        environment.update(env or {})
        log = OUT / "children" / f"{name}.log"
        log.parent.mkdir(parents=True, exist_ok=True)
        started = time.perf_counter()
        timed_out = False
        with log.open("wb") as stream:
            try:
                rc: int | None = subprocess.run(
                    [sys.executable, *argv],
                    cwd=SCRIPTS,
                    env=environment,
                    stdout=stream,
                    stderr=subprocess.STDOUT,
                    timeout=timeout,
                    check=False,
                ).returncode
            except subprocess.TimeoutExpired:
                rc, timed_out = None, True
        run = ChildRun(
            name,
            rc,
            time.perf_counter() - started,
            log.relative_to(OUT).as_posix(),
            timed_out,
        )
        self.telemetry.event(
            f"{PREFIX}.child",
            **{f"child.{k}": v for k, v in run.to_json().items() if v is not None},
        )
        if rc in self.watchdog_codes:
            raise Fatal(f"{name}: watchdog exit {rc} (seat state unknown)", code=rc)
        if timed_out:
            raise Fatal(f"{name}: timed out after {timeout}s")
        if rc not in (0, None):
            tail = log.read_text(encoding="utf-8", errors="replace")[-1500:]
            self.telemetry.warn(f"{name}: exit {rc}; log tail:\n{tail}")
        return run

    def check_a1(self, when: str) -> None:
        if self.a1_sha is None:
            return
        actual = sha256(self.a1) if self.a1.is_file() else None
        self.report["seat_safety"][f"a1_sha256_{when}"] = actual
        if actual != self.a1_sha:
            violation = f"A1 changed {when}: {self.a1_sha} -> {actual}"
            self.report["seat_safety"]["violations"].append(violation)
            raise Fatal(violation)

    # -- phases ------------------------------------------------------------------

    def build(self, key: str, run: str, log: Path | None) -> None:
        argv = [
            str(COM_REPLAY),
            "record",
            str(self.script),
            "--out-root",
            str(OUT / run),
        ]
        argv += ["--timing", str(OUT / f"{run}.timing.json")]
        if log is not None:
            argv += ["--log", str(log)]
        child = self.child(run, argv, _RECORD_TIMEOUT)
        timing_path = OUT / f"{run}.timing.json"
        timing = (
            json.loads(timing_path.read_text(encoding="utf-8"))
            if timing_path.is_file()
            else None
        )
        self.report["runs"][run] = {"child": child.to_json(), "timing": timing}
        self.report["walls"][key] = child.wall_seconds
        if child.rc != 0:
            raise RuntimeError(f"{run} build exited {child.rc}")
        if log is not None:
            summary = self.log_summary(log)
            self.report["logs"][log.name] = summary
            self.evidence(f"counts {log.name}", render_counts(log.name, summary))

    def log_summary(self, log: Path) -> dict[str, Any]:
        conversation = self.conversation
        loaded = conversation.load(log)
        trailer = dict(loaded.trailer)
        capture = log.parent / trailer.get("capture_dir", "")
        kinds: dict[str, int] = {}
        interfaces: dict[str, int] = {}
        inert_members: dict[str, int] = {}
        on_inert_handles = 0
        for call in loaded.calls:
            kinds[call.kind.value] = kinds.get(call.kind.value, 0) + 1
            if call.origin is conversation.Origin.INERT:
                inert_members[call.site] = inert_members.get(call.site, 0) + 1
                continue
            interface = call.site.rpartition(".")[0] or call.site
            interfaces[interface] = interfaces.get(interface, 0) + 1
            on_inert_handles += _names_inert_handle([call.handle, call.args])
        recipe = sum(interfaces.values())
        return {
            "bytes": log.stat().st_size,
            "calls": len(loaded.calls),
            "recipe_calls": recipe,
            "inert_calls": len(loaded.calls) - recipe,
            "kinds": kinds,
            "calls_by_interface": _top(interfaces),
            "inert_by_member": _top(inert_members),
            "recipe_requests_on_inert_handles": on_inert_handles,
            "with_write_back": sum(1 for c in loaded.calls if c.outs),
            "raised": sum(1 for c in loaded.calls if c.raised is not None),
            "identity_comparisons": kinds.get("eq", 0),
            "capture_bytes_on_disk": tree_bytes(capture),
            "header": loaded.header.to_json(),
            "trailer": {k: v for k, v in trailer.items() if k != "types"},
            "types": sorted(trailer.get("types", {})),
        }

    def phase0(self) -> None:
        self.build("W0", "run0", None)

    def phase1(self) -> None:
        self.build("W1", "run1", self.logs / "L1.jsonl.gz")
        if not self.a1.is_file():
            raise RuntimeError(f"run1 produced no {self.a1}")
        self.a1_sha = sha256(self.a1)
        self.report["seat_safety"]["a1_sha256"] = self.a1_sha

    def phase2(self) -> None:
        self.build("W2", "run2", self.logs / "L2.jsonl.gz")
        comparison = self.conversation.compare_conversations(
            self.logs / "L1.jsonl.gz", self.logs / "L2.jsonl.gz"
        )
        self.report["verdicts"]["K1"] = {
            "pass": comparison["request_divergence"] is None,
            "criterion": "no recipe REQUEST divergence between L1 and L2 (Generator "
            "mask only); response differences are counted by member, never masked",
            **comparison,
        }
        self.evidence("K1", render_k1(self.report["verdicts"]["K1"]))

    def replay(
        self, name: str, script: Path, log: Path, scratch: str
    ) -> tuple[ChildRun, dict[str, Any] | None]:
        result = OUT / f"{scratch}.json"
        argv = [
            str(COM_REPLAY),
            "replay",
            str(script),
            "--log",
            str(log),
            "--base-outputs",
            str(OUT / "run1"),
            "--scratch",
            str(OUT / scratch),
            "--result",
            str(result),
        ]
        child = self.child(
            name, argv, _REPLAY_TIMEOUT, env={"OTEL_SERVICE_NAME": "part-replay"}
        )
        payload = (
            json.loads(result.read_text(encoding="utf-8")) if result.is_file() else None
        )
        return child, payload

    def phase3(self) -> None:
        child, result = self.replay(
            "replay", self.script, self.logs / "L1.jsonl.gz", "replay"
        )
        self.report["walls"]["WR"] = child.wall_seconds
        if result is None:
            raise RuntimeError(f"replay wrote no result (exit {child.rc})")
        self.report["replay"] = {
            "child": child.to_json(),
            "result": "replay.json",
            **_replay_summary(result),
        }
        self.report["verdicts"]["K2"] = {
            "pass": result["verdict"] == "noop"
            and result["served"] == result["recorded"]
            and not result.get("py_output_mismatches"),
            "criterion": "NOOP, every recorded recipe request served, Python "
            "outputs byte-equal to run1 (recipe-inert calls served best-effort)",
            "verdict": result["verdict"],
            "served": result["served"],
            "recorded": result["recorded"],
            "reason": result.get("reason"),
            "divergence": result.get("divergence"),
            "inert": result.get("inert"),
            "py_output_mismatches": result.get("py_output_mismatches"),
            "script_error": result.get("script_error"),
        }
        self.evidence("K2", render_k2(self.report["verdicts"]["K2"], result))

    def phase3b(self) -> None:
        l1 = self.logs / "L1.jsonl.gz"
        perturbed = self.logs / "L1-ulp.jsonl.gz"
        seq = _perturb_first_float(self.conversation, l1, perturbed)
        controls: dict[str, Any] = {}
        child, result = self.replay(
            "control-script", self.control_script, l1, "replay-ctrl-script"
        )
        controls["script"] = {
            "child": child.to_json(),
            "script": self.control_script.name,
            **_replay_summary(result),
        }
        child, result = self.replay(
            "control-ulp", self.script, perturbed, "replay-ctrl-ulp"
        )
        controls["ulp"] = {
            "child": child.to_json(),
            "perturbed_seq": seq,
            **_replay_summary(result),
        }
        self.report["controls"] = controls
        ulp_seq = (controls["ulp"].get("divergence") or {}).get("seq")
        verdicts = {name: control.get("verdict") for name, control in controls.items()}
        self.report["verdicts"]["K2b"] = {
            "pass": all(v == "diverged" for v in verdicts.values()) and ulp_seq == seq,
            "criterion": "both negative controls DIVERGED; the ulp control at the perturbed seq",
            "verdicts": verdicts,
            "ulp_expected_seq": seq,
            "ulp_divergence_seq": ulp_seq,
        }
        self.evidence("K2b", render_k2b(self.report["verdicts"]["K2b"], controls))
        vacuous = [name for name, verdict in verdicts.items() if verdict == "noop"]
        if vacuous:
            raise Fatal(
                f"K2b vacuous: negative control(s) {vacuous} replayed as NOOP",
                scope=Scope.REPORT,
            )

    def phase4(self) -> None:
        if not (self.a1.is_file() and self.a2.is_file()):
            raise RuntimeError("A1/A2 missing")
        before = (sha256(self.a1), sha256(self.a2))
        out = OUT / "digest"
        argv = [
            str(Path(__file__)),
            "native",
            "digest",
            "--a1",
            str(self.a1),
            "--a2",
            str(self.a2),
            "--out",
            str(out),
        ]
        child = self.child("digest", argv, _NATIVE_TIMEOUT)
        self.report["digests"] = {"child": child.to_json()}
        if (sha256(self.a1), sha256(self.a2)) != before:
            violation = "digest changed A1 or A2 on disk"
            self.report["seat_safety"]["violations"].append(violation)
            raise Fatal(violation)
        native = _read_json(out / "native.json")
        self.report["digests"]["native"] = native
        self.report["seat_safety"]["digest_residents"] = (native or {}).get(
            "residents_after"
        )
        if native and native.get("residents_after"):
            violation = (
                f"digest left cad/out documents open: {native['residents_after']}"
            )
            self.report["seat_safety"]["violations"].append(violation)
            raise Fatal(violation)
        d1, d2 = _read_json(out / "D1.json"), _read_json(out / "D2.json")
        if child.rc != 0 or d1 is None or d2 is None:
            raise RuntimeError(
                f"digest child exit {child.rc}; D1/D2 present: {d1 is not None}/{d2 is not None}"
            )
        differences = compare_digests(d1, d2)
        self.report["verdicts"]["K3"] = {
            "pass": not differences,
            "criterion": "D1 == D2 within assembly_geometry_digest tolerances; census identical",
            "tolerances": _TOLERANCE,
            "differences": differences[:200],
            "difference_count": len(differences),
        }
        self.evidence(
            "K3", render_k3(self.report["verdicts"]["K3"], (native or {}).get("u11"))
        )
        self.check_a1("after_digest")

    def k4(self) -> None:
        walls = self.report["walls"]
        l1 = self.report["logs"].get("L1.jsonl.gz")
        runs = self.report["runs"]
        if not ({"W0", "W1", "WR"} <= set(walls) and l1):
            raise RuntimeError(f"K4 needs W0, W1, WR and L1; have {sorted(walls)}")
        audit = (l1["trailer"].get("escape_audit") or {}).get("seconds") or 0.0
        w0, w1, wr = walls["W0"], walls["W1"], walls["WR"]
        window0 = (runs["run0"]["timing"] or {}).get("window_seconds")
        window1 = (runs["run1"]["timing"] or {}).get("window_seconds")
        archive = _archive_bytes(OUT / "run1")
        overhead = (w1 - audit - w0) / w0
        self.report["verdicts"]["K4"] = {
            "pass": wr <= 0.10 * w1 and overhead <= 0.03 and l1["bytes"] <= archive,
            "criterion": "WR <= 10% W1; (W1 - W0) <= 3% W0; L1 bytes <= run1 archive bytes",
            "walls_basis": "parent-measured subprocess walls (each includes interpreter start, imports, connect and teardown)",
            "W0": w0,
            "W1": w1,
            "W1_minus_escape_audit": w1 - audit,
            "escape_audit_seconds": audit,
            "WR": wr,
            "WR_over_W1": wr / w1,
            "record_overhead_over_W0": overhead,
            "record_overhead_unadjusted_over_W0": (w1 - w0) / w0,
            "window_basis": {
                "window0": window0,
                "window1": window1,
                "overhead": ((window1 - audit - window0) / window0)
                if window0 and window1
                else None,
                "replay_window": (self.report.get("replay") or {}).get(
                    "window_seconds"
                ),
            },
            "L1_bytes": l1["bytes"],
            "capture_bytes_on_disk": l1["capture_bytes_on_disk"],
            "run1_archive_bytes": archive,
            "archive_basis": "tar.gz of run1 outputs at _artifact_cache._PACK_LEVEL",
            "size_with_capture_pass": l1["bytes"] + l1["capture_bytes_on_disk"]
            <= archive,
        }
        self.evidence("K4", render_k4(self.report["verdicts"]["K4"]))

    def phase5(self) -> None:
        if not self.a1.is_file():
            raise RuntimeError("A1 missing")
        d1 = OUT / "digest" / "D1.json"
        copy = OUT / "walk" / f"{self.part.removesuffix('.SLDPRT')}~walk.SLDPRT"
        out = OUT / "walk.json"
        argv = [
            str(Path(__file__)),
            "native",
            "walk",
            "--a1",
            str(self.a1),
            "--copy",
            str(copy),
            "--log",
            str(self.logs / "L1.jsonl.gz"),
            "--reference",
            str(d1),
            "--out",
            str(out),
        ]
        child = self.child("walk", argv, _NATIVE_TIMEOUT)
        walk = _read_json(out)
        self.report["walk"] = {
            "child": child.to_json(),
            "report": "walk.json",
            **_walk_summary(walk),
        }
        if walk and walk.get("residents_after"):
            violation = f"walk left cad/out documents open: {walk['residents_after']}"
            self.report["seat_safety"]["violations"].append(violation)
            raise Fatal(violation)
        self.check_a1("after_walk")
        if child.rc != 0 or walk is None:
            raise RuntimeError(f"walk child exit {child.rc}")
        window1 = ((self.report["runs"].get("run1") or {}).get("timing") or {}).get(
            "window_seconds"
        )
        summary = _walk_summary(walk)
        self.report["verdicts"]["K5"] = {
            "pass": summary["all_features_reachable"]
            and summary["read_points_within_tolerance"]
            and summary["final_digest_equals_D1"],
            "report_only": True,
            "criterion": "every feature reachable by EditRollback(4); every L1 read point within 1e-9; final digest == D1",
            "walk_seconds": walk.get("walk_seconds"),
            "creation_reference_seconds": {
                "design_estimate": 68.0,
                "W1_window": window1,
            },
            **summary,
        }
        self.evidence("K5", render_k5(self.report["verdicts"]["K5"]))

    # -- assumptions ----------------------------------------------------------------

    def assumptions(self) -> None:
        l1 = self.report["logs"].get("L1.jsonl.gz") or {}
        trailer = l1.get("trailer") or {}
        replay = self.report.get("replay") or {}
        walk = self.report.get("walk") or {}
        verdicts = self.report["verdicts"]
        audit = trailer.get("escape_audit") or {}
        self.report["assumptions"] = {
            "R1": {
                "claim": "pywin32 paths accept proxies; nothing escapes the funnel",
                "wrappers_on_real_objects_at_exit": (audit.get("at_exit") or {}).get(
                    "wrappers_on_real_objects"
                ),
                "adopted_outside_calls": trailer.get("adopted_outside_calls"),
                "foreign_thread_calls": trailer.get("foreign_thread_calls"),
                "recipe_requests_on_inert_handles": l1.get(
                    "recipe_requests_on_inert_handles"
                ),
                "K2": (verdicts.get("K2") or {}).get("pass"),
            },
            "R2": {
                "claim": "no live type info needed offline",
                "sw_revision": (l1.get("header") or {}).get("sw_revision"),
                "K2": (verdicts.get("K2") or {}).get("pass"),
            },
            "R3": {
                "claim": "byref outputs captured and restored",
                "calls_with_write_back": l1.get("with_write_back"),
                "K2": (verdicts.get("K2") or {}).get("pass"),
            },
            "R4": {
                "claim": "identity comparisons replay identically",
                "identity_comparisons": l1.get("identity_comparisons"),
                "K2": (verdicts.get("K2") or {}).get("pass"),
            },
            "R5": {
                "claim": "com_error round-trips",
                "raised_calls": l1.get("raised"),
                "K1": (verdicts.get("K1") or {}).get("pass"),
                "K2": (verdicts.get("K2") or {}).get("pass"),
            },
            "R6": {
                "claim": "log size and overhead acceptable",
                "K4": (verdicts.get("K4") or {}).get("pass"),
            },
            "R7": {
                "claim": "PYTHONHASHSEED=0 leaves the build deterministic",
                "environment": (l1.get("header") or {}).get("environment"),
                "K1": (verdicts.get("K1") or {}).get("pass"),
            },
            "R8": {
                "claim": "outputs fully redirected",
                "record_writes_outside_out": trailer.get("writes_outside_out"),
                "replay_writes_outside_scratch": replay.get("writes_outside_scratch"),
                "replay_sandbox_violations": replay.get("sandbox_violations"),
            },
            "R10": {
                "claim": "Python reads of SolidWorks-written files replay identically",
                "captured_files": len(trailer.get("captured") or {}),
                "capture_bytes": trailer.get("capture_bytes"),
                "record_reads": len(trailer.get("reads") or []),
                "replay_read_mismatches": replay.get("read_mismatches"),
                "materialise_missing": replay.get("materialise_missing"),
            },
            "R11": {
                "claim": "connect-time adapter state suffices",
                "restoration": replay.get("r11"),
                "connect_time_module_state": "recipe-inert module caches (e.g. the "
                "seat identity) are outside the claim: their requests are served "
                "best-effort, see inert",
                "inert": replay.get("inert"),
            },
            "R12": {
                "claim": "replay telemetry is separable",
                "replay_service_name": "part-replay",
            },
            "R9": {
                "claim": "farm submitter runs stage 1",
                "status": "not exercised (stage 1 runs on the worker here)",
            },
            "R13": {
                "claim": "stage-1 CPU at parallelism 8",
                "status": "not exercised (one replay at a time)",
            },
            "U1": walk.get("u1"),
            "U3": {
                "walk_seconds": walk.get("walk_seconds"),
                "creation_reference_seconds": (
                    (verdicts.get("K5") or {}).get("creation_reference_seconds")
                ),
            },
            "U10": {
                "read_points_within_tolerance": walk.get(
                    "read_points_within_tolerance"
                ),
                "read_points": walk.get("read_point_count"),
            },
            "U11": ((self.report.get("digests") or {}).get("native") or {}).get("u11"),
            "U15": {
                "edit_rollback_false": walk.get("rollback_false"),
                "features": walk.get("features"),
            },
            "U16": walk.get("u16"),
            "not_exercised": [
                "U2",
                "U4",
                "U5",
                "U6",
                "U7",
                "U8",
                "U9",
                "U12",
                "U13",
                "U14",
                "U17",
                "U18",
                "U19",
            ],
        }


def _read_json(path: Path) -> dict[str, Any] | None:
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else None


def _replay_summary(result: dict[str, Any] | None) -> dict[str, Any]:
    if result is None:
        return {"verdict": None}
    keep = (
        "verdict",
        "reason",
        "served",
        "recorded",
        "recorded_total",
        "seconds",
        "window_seconds",
        "divergence",
        "inert",
        "rc",
        "script_error",
        "com_outputs",
        "py_outputs",
        "py_output_mismatches",
        "base_only_outputs",
        "materialised",
        "materialise_missing",
        "read_mismatches",
        "writes_outside_scratch",
        "sandbox_violations",
        "r11",
        "proxies_served",
        "live_interface_objects_at_end",
    )
    return {key: result.get(key) for key in keep}


def _walk_summary(walk: dict[str, Any] | None) -> dict[str, Any]:
    if walk is None:
        return {
            "all_features_reachable": False,
            "read_points_within_tolerance": False,
            "final_digest_equals_D1": False,
        }
    steps = walk.get("steps") or []
    unreachable = [
        s["feature"] for s in steps if not s.get("ok") and not s.get("folder")
    ]
    points = walk.get("read_points") or []
    return {
        "all_features_reachable": not unreachable and bool(steps),
        "unreachable_features": unreachable,
        "rollback_false": walk.get("rollback_false"),
        "read_point_count": len(points),
        "read_points_within_tolerance": bool(points)
        and all(p.get("within") for p in points),
        "read_points_outside": [p for p in points if not p.get("within")][:50],
        "final_digest_equals_D1": walk.get("final_digest_differences") == [],
        "final_digest_differences": (walk.get("final_digest_differences") or [])[:50],
        "walk_seconds": walk.get("walk_seconds"),
        "u1": walk.get("u1"),
        "u16": walk.get("u16"),
        "features": walk.get("features"),
    }


# ---------------------------------------------------------------------------
# Evidence rendering (bounded lines for the task log)
# ---------------------------------------------------------------------------


def _clip(value: Any) -> str:
    text = value if isinstance(value, str) else json.dumps(value, default=str)
    return text if len(text) <= _CLIP else f"{text[: _CLIP - 3]}..."


def _top(counts: dict[str, int], limit: int = 20) -> dict[str, int]:
    return dict(sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))[:limit])


def _names_inert_handle(value: Any) -> bool:
    """Whether a recipe request names an object a recipe-inert call created
    (negative handles): inert results must never reach the build."""
    if isinstance(value, bool):
        return False
    if isinstance(value, int):
        return value < 0
    if isinstance(value, dict):
        return ("h" in value and _names_inert_handle(value["h"])) or any(
            _names_inert_handle(v) for k, v in value.items() if k != "h"
        )
    if isinstance(value, list):
        return any(_names_inert_handle(v) for v in value)
    return False


def _verdict_word(verdict: dict[str, Any]) -> str:
    return "PASS" if verdict.get("pass") else "FAIL"


def render_divergence(divergence: dict[str, Any] | None) -> list[str]:
    """A divergence with its caller frames and the five calls before it."""
    if not divergence:
        return []
    seq_new = divergence.get("seq_new")
    lines = [
        f"  at recipe #{divergence.get('index')} (seq {divergence.get('seq')}"
        + (f", new seq {seq_new}" if seq_new is not None else "")
        + f"): {divergence.get('side')}/{divergence.get('field')} differs, "
        f"kind {divergence.get('kind')}, phase {divergence.get('phase')}, "
        f"feature {divergence.get('feature')}",
    ]
    for side in ("expected", "actual"):
        call = divergence.get(side) or {}
        lines.append(
            f"    {side}: {call.get('site')} h={call.get('h')} from {call.get('caller')}"
        )
        if call:
            lines.append(f"      args {_clip(call.get('args'))}")
    preceding = divergence.get("preceding_response_difference")
    if preceding:
        lines.append(
            f"    nearest earlier response difference: #{preceding['index']} "
            f"{preceding['member']} {preceding['field']} {preceding['a']} vs "
            f"{preceding['b']} (from {preceding['caller']})"
        )
    for row in divergence.get("context") or []:
        lines.append(
            f"    before: seq {row['seq']} {row['site']} [{row['kind']}] h={row['h']} "
            f"from {row['caller']}: {_clip(row['args'])} -> {_clip(row['response'])}"
        )
    return lines


def render_counts(name: str, summary: dict[str, Any]) -> list[str]:
    trailer = summary.get("trailer") or {}
    lines = [
        f"{name}: {summary['calls']} calls (recipe {summary['recipe_calls']}, inert "
        f"{summary['inert_calls']}), {summary['bytes']} log bytes, captured "
        f"{len(trailer.get('captured') or {})} calls / "
        f"{trailer.get('capture_bytes')} bytes; write-back calls "
        f"{summary['with_write_back']}, identity ops "
        f"{summary['identity_comparisons']}, raised {summary['raised']}, recipe "
        f"requests on inert handles {summary['recipe_requests_on_inert_handles']}",
        f"  kinds {_clip(summary['kinds'])}",
        f"  by interface {_clip(_top(summary['calls_by_interface'], _EVIDENCE_TOP))}",
    ]
    if summary["inert_by_member"]:
        lines.append(
            f"  inert by member {_clip(_top(summary['inert_by_member'], _EVIDENCE_TOP))}"
        )
    return lines


def render_k1(k1: dict[str, Any]) -> list[str]:
    differences = k1.get("response_differences") or {}
    lines = [
        f"K1 {_verdict_word(k1)}: recipe calls L1/L2 {k1.get('recipe_calls')}, inert "
        f"{k1.get('inert_calls')}; {k1.get('response_difference_count')} response "
        f"differences over {len(differences)} members before any request divergence",
    ]
    divergence = k1.get("request_divergence")
    if divergence:
        lines += ["  REQUEST divergence:", *render_divergence(divergence)]
    examples = {e["member"]: e for e in k1.get("response_examples") or []}
    for member, count in list(differences.items())[:_EVIDENCE_TOP]:
        first = examples.get(member)
        detail = (
            f", first #{first['index']} {first['field']} {first['a']} vs {first['b']} "
            f"(from {first['caller']})"
            if first
            else ""
        )
        lines.append(f"  response {member}: {count}x{detail}")
    inert = k1.get("inert_differences") or {}
    if inert:
        lines.append(f"  inert count differences {_clip(inert)}")
    captures = k1.get("capture_differences") or []
    if captures:
        lines.append(
            f"  SolidWorks-written files differing: {len(captures)} "
            f"{_clip([(c['index'], c['member'], c['file']) for c in captures])}"
        )
    headers = k1.get("header_differences") or {}
    if headers:
        lines.append(f"  header differences {sorted(headers)}")
    return lines


def render_k2(k2: dict[str, Any], result: dict[str, Any]) -> list[str]:
    inert = result.get("inert") or {}
    lines = [
        f"K2 {_verdict_word(k2)}: {k2.get('verdict')}, {k2.get('served')}/"
        f"{k2.get('recorded')} recipe requests served; {k2.get('reason')}",
        f"  inert: recorded {inert.get('recorded')}, served {inert.get('served')}, "
        f"unrecorded {inert.get('unserved')}, unconsumed {inert.get('unconsumed')}",
    ]
    for row in (inert.get("unserved_members") or [])[:5]:
        lines.append(
            f"    unrecorded inert {row['member']} x{row['count']} from {row['caller']}"
        )
    lines += render_divergence(k2.get("divergence"))
    error = k2.get("script_error")
    if error:
        lines.append(
            f"  script error {error.get('type')}: {_clip(error.get('message'))}"
        )
        tail = (error.get("traceback") or "").strip().splitlines()[-6:]
        lines += [f"    {_clip(line)}" for line in tail]
    for rel, digests in list((k2.get("py_output_mismatches") or {}).items())[:5]:
        lines.append(f"  Python output differs: {rel} {_clip(digests)}")
    for key in ("sandbox_violations", "read_mismatches", "materialise_missing"):
        rows = result.get(key) or []
        if rows:
            lines.append(f"  {key} ({len(rows)}): {_clip(rows[:3])}")
    r11 = result.get("r11") or {}
    if r11.get("mismatched"):
        lines.append(f"  R11 mismatched adapter state {_clip(r11['mismatched'])}")
    return lines


def render_k2b(k2b: dict[str, Any], controls: dict[str, Any]) -> list[str]:
    lines = [
        f"K2b {_verdict_word(k2b)}: verdicts {k2b.get('verdicts')}, ulp perturbed seq "
        f"{k2b.get('ulp_expected_seq')} diverged at {k2b.get('ulp_divergence_seq')}",
    ]
    for name, control in controls.items():
        lines.append(f"  {name}: {_clip(control.get('reason'))}")
    return lines


def render_k3(k3: dict[str, Any], u11: dict[str, Any] | None) -> list[str]:
    lines = [
        f"K3 {_verdict_word(k3)}: {k3.get('difference_count')} digest differences",
        *(f"  {_clip(d)}" for d in (k3.get("differences") or [])[:10]),
    ]
    if u11 is not None:
        lines.append(f"  U11 same-name open {_clip(u11)}")
    return lines


def render_k4(k4: dict[str, Any]) -> list[str]:
    return [
        f"K4 {_verdict_word(k4)}: W0 {k4['W0']:.2f}s W1 {k4['W1']:.2f}s WR "
        f"{k4['WR']:.2f}s; WR/W1 {k4['WR_over_W1']:.3f}; record overhead "
        f"{k4['record_overhead_over_W0']:+.4f} (unadjusted "
        f"{k4['record_overhead_unadjusted_over_W0']:+.4f}); L1 {k4['L1_bytes']} B, "
        f"captures {k4['capture_bytes_on_disk']} B, run1 archive "
        f"{k4['run1_archive_bytes']} B",
        f"  windows {_clip(k4.get('window_basis'))}",
    ]


def render_k5(k5: dict[str, Any]) -> list[str]:
    return [
        f"K5 {_verdict_word(k5)} (report only): features {k5.get('features')}, "
        f"unreachable {_clip(k5.get('unreachable_features'))}, read points "
        f"{k5.get('read_point_count')} within {k5.get('read_points_within_tolerance')}, "
        f"final digest == D1 {k5.get('final_digest_equals_D1')}, walk "
        f"{k5.get('walk_seconds')}s",
        f"  outside {_clip(k5.get('read_points_outside'))}",
        f"  final digest differences {_clip(k5.get('final_digest_differences'))}",
        f"  U1 {_clip(k5.get('u1'))}",
        f"  U16 {_clip((k5.get('u16') or {}).get('bar_kept_by_ForceRebuild3'))}",
    ]


def _perturb_first_float(conversation: Any, source: Path, target: Path) -> int:
    """Copy ``source`` with the first float request argument moved 1 ulp;
    return the seq of the perturbed request."""
    loaded = conversation.load(source)

    def nudge(value: Any) -> tuple[Any, bool]:
        if isinstance(value, dict) and set(value) == {"f"}:
            moved = math.nextafter(float.fromhex(value["f"]), math.inf)
            return {"f": moved.hex()}, True
        if isinstance(value, dict) and ("t" in value or "l" in value):
            tag = "t" if "t" in value else "l"
            items, done = _nudge_list(value[tag], nudge)
            return {tag: items}, done
        if isinstance(value, dict) and "v" in value:
            inner, done = nudge(value["v"][1])
            return {"v": [value["v"][0], inner]}, done
        return value, False

    writer = conversation.LogWriter(target)
    writer.header(loaded.header)
    perturbed: int | None = None
    for call in loaded.calls:
        if perturbed is None and call.origin is conversation.Origin.RECIPE:
            args, done = _nudge_list(call.args, nudge)
            if done:
                call = dataclasses.replace(call, args=args)
                perturbed = call.seq
        writer.emit(call)
    writer.close(loaded.trailer)
    if perturbed is None:
        raise RuntimeError("L1 has no float request argument to perturb")
    return perturbed


def _nudge_list(values: list[Any], nudge: Any) -> tuple[list[Any], bool]:
    out = list(values)
    for index, value in enumerate(values):
        moved, done = nudge(value)
        if done:
            out[index] = moved
            return out, True
    return out, False


def _archive_bytes(root: Path) -> int:
    from _artifact_cache import _PACK_LEVEL

    buffer = io.BytesIO()
    with tarfile.open(fileobj=buffer, mode="w:gz", compresslevel=_PACK_LEVEL) as tar:
        for path in sorted(root.rglob("*")):
            if path.is_file():
                tar.add(path, arcname=path.relative_to(root).as_posix())
    return buffer.getbuffer().nbytes


def compare_digests(a: dict[str, Any], b: dict[str, Any]) -> list[str]:
    """Differences between two geometry digests, numeric within tolerance."""
    out: list[str] = []

    def numeric(path: str, x: Any, y: Any, tolerance: float) -> None:
        xs = x if isinstance(x, list) else [x]
        ys = y if isinstance(y, list) else [y]
        if len(xs) != len(ys):
            out.append(f"{path}: length {len(xs)} != {len(ys)}")
            return
        for index, (p, q) in enumerate(zip(xs, ys, strict=True)):
            if isinstance(p, list) or isinstance(q, list):
                numeric(f"{path}[{index}]", p, q, tolerance)
                continue
            if p is None or q is None or not (abs(float(p) - float(q)) <= tolerance):
                out.append(f"{path}[{index}]: {p!r} != {q!r} (tol {tolerance})")

    def exact(path: str, x: Any, y: Any) -> None:
        if x != y:
            out.append(
                f"{path}: {json.dumps(x, default=str)[:300]} != {json.dumps(y, default=str)[:300]}"
            )

    for key in ("mass_kg", "volume_mm3", "area_mm2", "com_mm", "moi_kgmm2"):
        numeric(
            f"part.{key}",
            a.get("part", {}).get(key),
            b.get("part", {}).get(key),
            _TOLERANCE[key],
        )
    bodies_a, bodies_b = a.get("bodies", []), b.get("bodies", [])
    if len(bodies_a) != len(bodies_b):
        out.append(f"bodies: {len(bodies_a)} != {len(bodies_b)}")
    for index, (x, y) in enumerate(zip(bodies_a, bodies_b, strict=False)):
        for key in (
            "mass_kg",
            "volume_mm3",
            "area_mm2",
            "com_mm",
            "moi_kgmm2",
            "extreme_mm",
        ):
            numeric(f"bodies[{index}].{key}", x.get(key), y.get(key), _TOLERANCE[key])
        for key in ("faces", "edges", "vertices"):
            exact(f"bodies[{index}].{key}", x.get(key), y.get(key))
    for key in ("features", "custom_properties", "equations", "errors"):
        exact(key, a.get(key), b.get(key))
    dims_a, dims_b = a.get("dimensions", []), b.get("dimensions", [])
    exact("dimensions.names", [d[0] for d in dims_a], [d[0] for d in dims_b])
    for x, y in zip(dims_a, dims_b, strict=False):
        numeric(f"dimensions[{x[0]}]", x[1], y[1], _TOLERANCE["dimension_si"])
    return out


def benchmark(stem: str, control_stem: str) -> int:
    import _telemetry
    from opentelemetry import trace
    from opentelemetry.sdk.trace import SpanProcessor

    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    spans_path = OUT / "spans.jsonl"
    spans_path.write_text("", encoding="utf-8")

    class RetainedSpans(SpanProcessor):
        def __init__(self) -> None:
            self.completed: list[Any] = []

        def on_end(self, span: Any) -> None:
            if span.name.startswith(PREFIX):
                self.completed.append(span)

        def write(self) -> None:
            with spans_path.open("w", encoding="utf-8") as stream:
                for completed in self.completed:
                    stream.write(completed.to_json(indent=None) + "\n")

    retained = RetainedSpans()
    provider = trace.get_tracer_provider()
    if hasattr(provider, "add_span_processor"):
        provider.add_span_processor(retained)
    leaf = Leaf(stem, control_stem)
    code = 0
    reason = "completed"
    try:
        with _telemetry.build_session("replay-noop", script="benchmark_replay_noop"):
            with _telemetry.span(PREFIX, stem=stem, control_stem=control_stem) as root:
                context = root.get_span_context()
                leaf.report["trace_id"] = f"{context.trace_id:032x}"
                code, reason = _run_phases(leaf)
        leaf.report["retained_span_count"] = len(retained.completed)
    finally:
        leaf.report["exit"] = {"code": code, "reason": reason}
        try:
            leaf.save()
            retained.write()
        except Exception as exc:  # noqa: BLE001 - an unwritable report is fatal
            _telemetry.error(f"report could not be written: {exc}")
            code = code or 1
    _log_summary(leaf, code, reason)
    _telemetry.shutdown()
    return code


def _run_phases(leaf: Leaf) -> tuple[int, str]:
    with leaf.phase("phase0", "clean build, unrecorded (W0)"):
        leaf.phase0()
    if leaf.report["phases"]["phase0"]["status"] != Status.OK.value and not leaf.fatal:
        leaf.fatal.append(Fatal("phase 0 (unrecorded clean build) failed"))
    # (key, title, step, needs the seat)
    steps = (
        ("phase1", "clean build, recorded (L1, W1)", leaf.phase1, True),
        ("phase2", "clean build, recorded (L2, W2); K1", leaf.phase2, True),
        (
            "phase3",
            "replay of L1 with SolidWorks untouched (WR); K2",
            leaf.phase3,
            False,
        ),
        ("phase3b", "negative controls; K2b", leaf.phase3b, False),
        ("phase4", "geometry digests D1/D2; K3", leaf.phase4, True),
        ("k4", "walls and sizes; K4", leaf.k4, False),
        ("phase5", "rollback walk on a copy of A1; K5", leaf.phase5, True),
    )
    for key, title, step, needs_seat in steps:
        if needs_seat and leaf.seat_stopped():
            leaf.skip(key, title, "an earlier fault made further native steps unsafe")
            continue
        with leaf.phase(key, title):
            step()
    with leaf.phase("assumptions", "R/U evidence map"):
        leaf.assumptions()
    if leaf.fatal:
        first = leaf.fatal[0]
        watchdog = next((f.code for f in leaf.fatal if f.code != 1), None)
        return watchdog or first.code, "; ".join(f.reason for f in leaf.fatal)
    return 0, "completed; K verdicts are results, not exit codes"


def _log_summary(leaf: Leaf, code: int, reason: str) -> None:
    """The farm publishes no outputs of a failed leaf: the summary rides telemetry."""
    import _telemetry

    verdicts = {
        key: value.get("pass")
        for key, value in leaf.report["verdicts"].items()
        if isinstance(value, dict)
    }
    phases = {key: row.get("status") for key, row in leaf.report["phases"].items()}
    walls = {key: round(value, 2) for key, value in leaf.report["walls"].items()}
    replay = leaf.report.get("replay") or {}
    message = (
        f"replay-noop {leaf.stem}: exit {code} ({reason}); verdicts {verdicts}; "
        f"phases {phases}; walls {walls}; replay {replay.get('verdict')} "
        f"{replay.get('served')}/{replay.get('recorded')}"
    )
    _telemetry.event(
        f"{PREFIX}.summary",
        exit_code=code,
        reason=reason,
        verdicts=json.dumps(verdicts),
        phases=json.dumps(phases),
        walls=json.dumps(walls),
    )
    # One line per verdict, so the end of the task log reads on its own.
    headlines = [
        f"  {key}: {lines[0]}"
        for key, lines in leaf.report["evidence"].items()
        if lines and key.startswith("K")
    ]
    errors = [
        f"  {key}: {row.get('error')}"
        for key, row in leaf.report["phases"].items()
        if row.get("status") == Status.ERROR.value
    ]
    (_telemetry.success if code == 0 else _telemetry.error)(
        "\n".join([message, *headlines, *errors])
    )


# ---------------------------------------------------------------------------
# Native children (connect through run_build; one seat, strict open/close)
# ---------------------------------------------------------------------------


def _open(adapter: Any, path: Path) -> Any:
    """``OpenDoc6`` (silent), bound to the generated ``IModelDoc2`` so every
    member called on it has the shape :data:`NATIVE_MEMBERS` lists."""
    from _com import _early_bound

    answer = adapter.swApp.OpenDoc6(str(path), _DOC_PART, _OPEN_SILENT, "", 0, 0)
    if not isinstance(answer, (tuple, list)) or len(answer) != 3:
        raise RuntimeError(f"unexpected OpenDoc6 readback: {answer!r}")
    document, errors, warnings = answer
    if document is None or errors or warnings:
        raise RuntimeError(f"OpenDoc6 {path}: errors={errors} warnings={warnings}")
    document = _early_bound(document, "IModelDoc2")
    actual = Path(str(document.GetPathName()))
    if os.path.normcase(str(actual.resolve())) != os.path.normcase(str(path.resolve())):
        raise RuntimeError(f"opened {actual}, not {path}")
    return document


def _close(adapter: Any, document: Any, path: Path) -> None:
    """Close ``document`` (an :func:`_open` result) without saving."""
    adapter.swApp.CloseDoc(str(document.GetTitle()))
    if adapter.swApp.GetOpenDocumentByName(str(path)) is not None:
        raise RuntimeError(f"document did not close: {path}")


def _leave_seat_empty(adapter: Any) -> dict[str, Any]:
    """Close every open document WITHOUT saving (``_session``'s discard), so a
    probe bug becomes a recorded error, not a seat holding a cad/out file;
    the resident check that follows decides whether anything is left."""
    import _session

    try:
        _session.discard_open_documents(adapter)
    except Exception as exc:  # noqa: BLE001 - recorded; the resident check decides
        return {"discarded": False, "error": f"{type(exc).__name__}: {exc}"}
    return {"discarded": True}


def _residents(adapter: Any) -> list[str]:
    """``cad/out`` documents still open; unreadable counts as open."""
    import _session

    try:
        return _session._resident_output_documents(adapter)
    except Exception as exc:  # noqa: BLE001 - an unknown seat is not an empty one
        return [f"<resident check failed: {type(exc).__name__}: {exc}>"]


def _floats(value: Any, scale: float = 1.0) -> list[float] | None:
    if value is None:
        return None
    return [float(v) * scale for v in value]


def _features(document: Any) -> list[Any]:
    from _com import _com_invoke

    out = []
    feature = _com_invoke(document, "IModelDoc2", "FirstFeature")
    for _ in range(100_000):
        if feature is None:
            return out
        out.append(feature)
        feature = _com_invoke(feature, "IFeature", "GetNextFeature")
    raise RuntimeError("feature walk did not terminate")


def geometry_digest(document: Any) -> dict[str, Any]:
    """Part mass properties, per-body census, ordered feature census,
    dimension system values, custom properties and equations."""
    from _com import _com_invoke, _early_bound
    from _dimensions import _display_dimensions

    errors: list[str] = []
    model = _early_bound(document, "IModelDoc2")
    extension = _early_bound(model.Extension, "IModelDocExtension")
    mass = _early_bound(extension.CreateMassProperty2(), "IMassProperty2")
    mass.AccuracyLevel = _MASS_ACCURACY
    part = {
        "accuracy_level": int(mass.AccuracyLevel),
        "mass_kg": float(mass.Mass),
        "volume_mm3": float(mass.Volume) * 1e9,
        "area_mm2": float(mass.SurfaceArea) * 1e6,
        "com_mm": _floats(mass.CenterOfMass, 1e3),
        "moi_kgmm2": _floats(mass.GetMomentOfInertia(_MOMENT_AT_CENTRE), 1e6),
    }
    bodies = []
    for raw in _early_bound(model, "IPartDoc").GetBodies2(_SOLID_BODY, False) or ():
        body = _early_bound(raw, "IBody2")
        props = [float(v) for v in body.GetMassProperties(1.0)]
        extremes = []
        for axis in range(3):
            for sign in (-1.0, 1.0):
                direction = [sign if i == axis else 0.0 for i in range(3)]
                answer = body.GetExtremePoint(*direction)
                if (
                    not isinstance(answer, (tuple, list))
                    or len(answer) != 4
                    or not answer[0]
                ):
                    errors.append(f"GetExtremePoint {direction}: {answer!r}")
                    extremes.append(None)
                    continue
                extremes.append([float(v) * 1e3 for v in answer[1:]])
        bodies.append(
            {
                "com_mm": [v * 1e3 for v in props[0:3]],
                "volume_mm3": props[3] * 1e9,
                "area_mm2": props[4] * 1e6,
                "mass_kg": props[5],
                "moi_kgmm2": [v * 1e6 for v in props[6:12]],
                "faces": int(body.GetFaceCount()),
                "edges": int(body.GetEdgeCount()),
                "vertices": int(body.GetVertexCount()),
                "extreme_mm": extremes,
            }
        )
    bodies.sort(
        key=lambda b: (round(b["volume_mm3"], 3), [round(v, 4) for v in b["com_mm"]])
    )
    features = []
    dimensions = []
    for feature in _features(model):
        features.append(
            [
                str(_com_invoke(feature, "IFeature", "Name")),
                str(_com_invoke(feature, "IFeature", "GetTypeName2")),
                bool(_com_invoke(feature, "IFeature", "IsSuppressed")),
            ]
        )
        for dimension in _display_dimensions(feature):
            dimensions.append(
                [
                    str(_com_invoke(dimension, "IDimension", "FullName")),
                    float(_com_invoke(dimension, "IDimension", "SystemValue")),
                ]
            )
    manager = _early_bound(
        extension.CustomPropertyManager(""), "ICustomPropertyManager"
    )
    properties = {}
    for name in manager.GetNames() or ():
        answer = manager.Get6(name, False)
        properties[str(name)] = (
            [str(v) for v in answer]
            if isinstance(answer, (tuple, list))
            else str(answer)
        )
    equations = []
    raw_manager = model.GetEquationMgr()
    if raw_manager is not None:
        equation_manager = _early_bound(raw_manager, "IEquationMgr")
        equations = [
            str(equation_manager.Equation(i))
            for i in range(int(equation_manager.GetCount()))
        ]
    return {
        "part": part,
        "bodies": bodies,
        "features": features,
        "dimensions": dimensions,
        "custom_properties": properties,
        "equations": equations,
        "errors": errors,
    }


async def native_digest(adapter: Any, a1: Path, a2: Path, out: Path) -> dict[str, str]:
    out.mkdir(parents=True, exist_ok=True)
    report: dict[str, Any] = {"a1": str(a1), "a2": str(a2)}
    try:
        report["sha256_before"] = [sha256(a1), sha256(a2)]
        try:
            report["u11"] = _probe_same_name_open(adapter, a1, a2)
        except Exception as exc:  # noqa: BLE001 - U11 is report-only; D1/D2 still run
            report["u11"] = {
                "error": f"{type(exc).__name__}: {exc}",
                "traceback": traceback.format_exc(),
            }
        residents = _residents(adapter)
        if residents:
            raise RuntimeError(f"documents open after the U11 probe: {residents}")
        for label, path in (("D1", a1), ("D2", a2)):
            started = time.perf_counter()
            document = _open(adapter, path)
            try:
                digest = geometry_digest(document)
            finally:
                _close(adapter, document, path)
            digest["seconds"] = time.perf_counter() - started
            write_json(out / f"{label}.json", digest)
        report["sha256_after"] = [sha256(a1), sha256(a2)]
    finally:
        report["cleanup"] = _leave_seat_empty(adapter)
        report["residents_after"] = _residents(adapter)
        write_json(out / "native.json", report)
    return {"digest": str(out)}


def _probe_same_name_open(adapter: Any, a1: Path, a2: Path) -> dict[str, Any]:
    """U11: open A2 while A1 (same file name, other folder) is open. Leaves
    the seat empty either way: the titles collide, so it discards everything."""
    from _com import _early_bound

    probe: dict[str, Any] = {}
    try:
        first = _open(adapter, a1)
        answer = adapter.swApp.OpenDoc6(str(a2), _DOC_PART, _OPEN_SILENT, "", 0, 0)
        document, errors, warnings = (
            answer if isinstance(answer, (tuple, list)) else (answer, None, None)
        )
        returned = _early_bound(document, "IModelDoc2")
        probe.update(
            returned_document=returned is not None,
            errors=errors,
            warnings=warnings,
            returned_path=str(returned.GetPathName()) if returned is not None else None,
            returned_a1=(
                adapter.swApp.IsSame(returned, first) == _OBJECT_SAME
                if returned is not None
                else None
            ),
        )
    finally:
        probe["cleanup"] = _leave_seat_empty(adapter)
        probe["open_after_cleanup"] = [
            str(p)
            for p in (a1, a2)
            if adapter.swApp.GetOpenDocumentByName(str(p)) is not None
        ]
    if probe["open_after_cleanup"]:
        raise RuntimeError(
            f"U11 probe left documents open: {probe['open_after_cleanup']}"
        )
    return probe


def _read_points(log: Path) -> list[dict[str, Any]]:
    """L1's mass-property reads: GETs of Volume/Mass/SurfaceArea/CenterOfMass on
    an object a CreateMassProperty* call returned (or a QueryInterface of it),
    each with f(r) = the last IFeature.Name put before it."""
    import _com_conversation as conversation

    loaded = conversation.load(log)
    sources: dict[int, str] = {}
    points: list[dict[str, Any]] = []
    feature: str | None = None
    for call in loaded.calls:
        if call.kind is conversation.Kind.PUT and call.site.endswith("IFeature.Name"):
            names = [a for a in call.args if isinstance(a, str)]
            feature = names[-1] if names else feature
        result = call.result if isinstance(call.result, dict) else {}
        member = call.site.rpartition(".")[2]
        if member in ("CreateMassProperty", "CreateMassProperty2") and "h" in result:
            sources[result["h"]] = member
            continue
        if (
            call.kind is conversation.Kind.QI
            and call.handle in sources
            and "h" in result
        ):
            sources[result["h"]] = sources[call.handle]
            continue
        if (
            call.kind is conversation.Kind.GET
            and call.handle in sources
            and member in _MASS_MEMBERS
        ):
            value = _plain(call.result)
            if value is not None:
                points.append(
                    {
                        "seq": call.seq,
                        "member": member,
                        "creator": sources[call.handle],
                        "feature": feature,
                        "recorded": value,
                    }
                )
    return points


def _plain(encoded: Any) -> Any:
    if isinstance(encoded, dict) and "f" in encoded:
        return float.fromhex(encoded["f"])
    if isinstance(encoded, dict) and ("t" in encoded or "l" in encoded):
        values = [_plain(v) for v in encoded.get("t", encoded.get("l"))]
        return values if all(isinstance(v, float) for v in values) else None
    return None


def _mass_reading(extension: Any, creator: str) -> dict[str, Any]:
    from _com import _early_bound

    interface = (
        "IMassProperty2" if creator == "CreateMassProperty2" else "IMassProperty"
    )
    mass = _early_bound(getattr(extension, creator)(), interface)
    return {member: _plain_live(getattr(mass, member)) for member in _MASS_MEMBERS}


def _plain_live(value: Any) -> Any:
    if isinstance(value, (tuple, list)):
        return [float(v) for v in value]
    return float(value)


def _within(recorded: Any, live: Any) -> bool:
    xs = recorded if isinstance(recorded, list) else [recorded]
    ys = live if isinstance(live, list) else [live]
    return len(xs) == len(ys) and all(
        math.isclose(x, y, rel_tol=_READ_POINT_RTOL, abs_tol=1e-15)
        for x, y in zip(xs, ys, strict=True)
    )


async def native_walk(
    adapter: Any, a1: Path, copy: Path, log: Path, reference: Path, out: Path
) -> dict[str, str]:
    from _com import _com_invoke, _early_bound

    report: dict[str, Any] = {"a1": str(a1), "copy": str(copy)}
    try:
        report["a1_sha256_before"] = sha256(a1)
        copy.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(a1, copy)
        points = _read_points(log)
        by_feature: dict[str | None, list[dict[str, Any]]] = {}
        for point in points:
            by_feature.setdefault(point["feature"], []).append(point)
        report["read_points_without_feature"] = len(by_feature.get(None, []))
        document = _open(adapter, copy)
        try:
            model = _early_bound(document, "IModelDoc2")
            extension = _early_bound(model.Extension, "IModelDocExtension")
            manager = _early_bound(model.FeatureManager, "IFeatureManager")
            features = [
                (
                    str(_com_invoke(f, "IFeature", "Name")),
                    str(_com_invoke(f, "IFeature", "GetTypeName2")),
                    f,
                )
                for f in _features(model)
            ]
            names = [name for name, _, _ in features]
            origin = next(
                (i for i, (_, kind, _) in enumerate(features) if kind == _ORIGIN_TYPE),
                None,
            )
            if origin is None or origin + 1 >= len(features):
                raise RuntimeError(f"no feature after {_ORIGIN_TYPE}: {names}")
            tree = features[origin + 1 :]
            report["features"] = len(tree)
            walk_started = time.perf_counter()
            started = time.perf_counter()
            first_ok = bool(manager.EditRollback(_ROLL_BEFORE, tree[0][0]))
            report["u1"] = {
                "first": tree[0][0],
                "ok": first_ok,
                "seconds": time.perf_counter() - started,
                "rolled_back": sum(
                    bool(_com_invoke(f, "IFeature", "IsRolledBack")) for _, _, f in tree
                ),
                "of": len(tree),
            }
            steps = []
            checked = []
            u16 = []
            for name, kind, feature in tree:
                started = time.perf_counter()
                ok = bool(manager.EditRollback(_ROLL_AFTER, name))
                step: dict[str, Any] = {
                    "feature": name,
                    "type": kind,
                    "ok": ok,
                    "folder": "Folder" in kind,
                    "seconds": time.perf_counter() - started,
                }
                steps.append(step)
                if not ok or name not in by_feature:
                    continue
                rolled_before = sum(
                    bool(_com_invoke(f, "IFeature", "IsRolledBack")) for _, _, f in tree
                )
                for point in by_feature[name]:
                    live = _mass_reading(extension, point["creator"])[point["member"]]
                    checked.append(
                        {
                            **point,
                            "live_before_rebuild": live,
                            "within_before_rebuild": _within(point["recorded"], live),
                        }
                    )
                started = time.perf_counter()
                model.ForceRebuild3(False)
                step["rebuild_seconds"] = time.perf_counter() - started
                rolled_after = sum(
                    bool(_com_invoke(f, "IFeature", "IsRolledBack")) for _, _, f in tree
                )
                u16.append(
                    {
                        "feature": name,
                        "rolled_back_before": rolled_before,
                        "rolled_back_after": rolled_after,
                    }
                )
                for row in checked[-len(by_feature[name]) :]:
                    live = _mass_reading(extension, row["creator"])[row["member"]]
                    row["live_after_rebuild"] = live
                    row["within"] = _within(row["recorded"], live)
            report["walk_seconds"] = time.perf_counter() - walk_started
            report["steps"] = steps
            report["rollback_false"] = sum(1 for s in steps if not s["ok"])
            report["read_points"] = checked
            report["read_points_unvisited"] = [
                p
                for feature, rows in by_feature.items()
                if feature not in {s["feature"] for s in steps if s["ok"]}
                for p in rows
            ][:50]
            report["u16"] = {
                "bar_kept_by_ForceRebuild3": all(
                    r["rolled_back_before"] == r["rolled_back_after"] for r in u16
                ),
                "rows": u16,
            }
            started = time.perf_counter()
            report["roll_to_end"] = bool(manager.EditRollback(_ROLL_TO_END, ""))
            report["roll_to_end_seconds"] = time.perf_counter() - started
            final = geometry_digest(model)
            write_json(out.with_name("walk-final-digest.json"), final)
            expected = _read_json(reference)
            report["final_digest_differences"] = (
                compare_digests(expected, final) if expected else ["no D1 reference"]
            )
        finally:
            _close(adapter, document, copy)
        report["a1_sha256_after"] = sha256(a1)
        if report["a1_sha256_after"] != report["a1_sha256_before"]:
            raise RuntimeError("A1 changed during the walk")
    finally:
        report["cleanup"] = _leave_seat_empty(adapter)
        report["residents_after"] = _residents(adapter)
        write_json(out, report)
    return {"walk": str(out)}


# ---------------------------------------------------------------------------
# Entry
# ---------------------------------------------------------------------------


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="benchmark_replay_noop.py",
        description=__doc__.split("\n\n", 1)[0],
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser(
        "benchmark", help="the verify:replay_noop leaf (seat held by doit)"
    )
    run.add_argument("--stem", default=DEFAULT_STEM)
    run.add_argument("--control-stem", default=DEFAULT_CONTROL_STEM)
    native = sub.add_parser("native", help="child entry points (connect)")
    steps = native.add_subparsers(dest="step", required=True)
    digest = steps.add_parser("digest", help="D1/D2 geometry digests (+ U11 probe)")
    digest.add_argument("--a1", type=Path, required=True)
    digest.add_argument("--a2", type=Path, required=True)
    digest.add_argument("--out", type=Path, required=True)
    walk = steps.add_parser("walk", help="rollback walk over a copy of A1 (K5)")
    walk.add_argument("--a1", type=Path, required=True)
    walk.add_argument("--copy", type=Path, required=True)
    walk.add_argument("--log", type=Path, required=True)
    walk.add_argument("--reference", type=Path, required=True)
    walk.add_argument("--out", type=Path, required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    args = parser.parse_args(argv)
    if not os.environ.get("HARMONIC_COM_SEAT"):
        parser.error("seat not held: run the canonical verify:replay_noop task")
    sys.path.insert(0, str(SCRIPTS))
    if args.command == "benchmark":
        for script in (
            SCRIPTS / f"build_{args.stem}.py",
            SCRIPTS / f"build_{args.control_stem}.py",
        ):
            if not script.is_file():
                parser.error(f"no build script {script.name}")
        return benchmark(args.stem, args.control_stem)
    for path in (args.out, getattr(args, "copy", None)):
        if path is not None and OUT.resolve() not in path.resolve().parents:
            parser.error(f"{path} is outside {OUT}")
    from _session import run_build

    if args.step == "digest":
        return run_build(
            lambda adapter: native_digest(adapter, args.a1, args.a2, args.out)
        )
    return run_build(
        lambda adapter: native_walk(
            adapter, args.a1, args.copy, args.log, args.reference, args.out
        )
    )


if __name__ == "__main__":
    sys.exit(main())
