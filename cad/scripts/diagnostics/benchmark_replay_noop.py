"""COM-conversation no-op replay benchmark (EXPERIMENT BRANCH ONLY; never merge).

Branch ``experiment/com-replay-20261110``. Design: reconcile-adapter-design.md
section 1. One farm leaf (``verify:replay_noop``) that holds the seat and, for
each ``--stem STEM:CONTROL_STEM[:PROFILE]`` in turn, runs every native step as
its own ``run_build`` subprocess under ``replay-noop/<stem>/``:

0. clean build, unrecorded, outputs under ``run0`` (W0);
1. clean build recorded with full caller capture -> ``run1`` + ``logs/L1``
   (W1);
2. clean build recorded with the default (divergence-only) caller capture ->
   ``run2`` + ``logs/L2`` (W2); K1;
3. replay of L1 with SolidWorks untouched (WR); K2; negative controls
   (the control stem's script, and L1 with one request float moved 1 ulp); K2b;
6. source-change controls: L1 replayed against a mechanically edited copy of
   a helper the build runs (comment and docstring only; one local renamed: both
   NOOP; one numeric literal moved: DIVERGED), and with the Generator stamp's
   provider answering another commit's sha (NOOP: k6.cross_commit); K6;
4. geometry digests D1/D2 of the two recorded artefacts; K3; K4;
5. rollback walk over a copy of A1 against L1's mass-property read points; K5.

Profile ``full`` runs all of it; ``replay`` runs 1, 3, 3b and 6 only. Stems run
sequentially; a seat fault in one stops the rest. ``<stem>/report.json`` is
rewritten after every phase, ``report.json`` holds the combined summary, and
every K verdict's evidence is also logged (bounded, at WARN) because a failed
leaf publishes only its task log. Only infrastructure or soundness faults exit
non-zero (a stem's first build failing, a watchdog exit, a negative control
answering NOOP, documents still open after a native step's own discard, an
unwritable report); every other K failure is a recorded result.

``native digest`` / ``native walk`` are the child entry points (they connect).
``--help`` imports neither pywin32 nor ``_session``.
"""

from __future__ import annotations

import argparse
import ast
import contextlib
import dataclasses
import hashlib
import io
import json
import math
import os
import shutil
import statistics
import subprocess
import sys
import tarfile
import time
import traceback
from collections.abc import Iterator, Sequence
from enum import StrEnum
from pathlib import Path
from typing import Any

SCRIPTS = Path(__file__).resolve().parents[1]
REPO = SCRIPTS.parents[1]
OUT = REPO / "cad" / "out" / "reports" / "replay-noop"
COM_REPLAY = SCRIPTS / "com_replay.py"
PREFIX = "experiment.replay_noop"
DEFAULT_STEM_SPECS = ("pd_transgear_arm_plate:pd_transgear_arm:full",)
SCHEMA = 2

_OPEN_SILENT = 1  # swOpenDocOptions_Silent
_DOC_PART = 1  # swDocPART
_SOLID_BODY = 0  # swSolidBody
_ROLL_TO_END = 1  # swMoveRollbackBarTo_e
_ROLL_BEFORE = 3
_ROLL_AFTER = 4
_MASS_ACCURACY = 2
_MOMENT_AT_CENTRE = 0
# swMassPropertyAccuracyLevel_e: Lower, Medium, Higher.
_MASS_ACCURACY_LEVELS = (0, 1, 2)
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
# K6: the helper function the source-change controls edit. Every part build
# runs it through COM: save_part_and_images orients the part isometric
# (ShowNamedView2) before the save.
_K6_MODULE = "_part_save"
_K6_FUNCTION = "set_isometric_view"
_K6_COMMENT = "# K6 control: comment-only edit."
_K6_SUFFIX = "_k6"
# K6 cross-commit control: the provider the Generator stamp reads (git HEAD),
# overridden in the overlay to what another commit would stamp. Not hex, so it
# can never equal a recorded sha.
_K6_PROVIDER_MODULE = "_source_identity"
_K6_PROVIDER = "_git_sha"
_K6_FOREIGN_SHA = "k6cross"
# Calls whose presence makes a mechanical rename unsafe (they read names).
_INTROSPECTION = frozenset({"locals", "vars", "eval", "exec", "dir"})


class Status(StrEnum):
    OK = "ok"
    ERROR = "error"
    SKIPPED = "skipped"


class Scope(StrEnum):
    """What a fatal fault invalidates: the seat (no further native step) or
    only the report's soundness (later phases still run)."""

    SEAT = "seat"
    REPORT = "report"


class Profile(StrEnum):
    """Which phases a stem runs."""

    FULL = "full"  # 0-6: every K verdict
    REPLAY = "replay"  # 1, 3, 3b and 6: record once, replay, controls


class SourceEdit(StrEnum):
    """A mechanical edit of one helper function for the K6 controls."""

    COMMENT_DOCSTRING = "comment_docstring"  # a comment line, a docstring change
    RENAME_LOCAL = "rename_local"  # one local variable renamed throughout
    NUMERIC_LITERAL = "numeric_literal"  # one numeric literal moved by one step
    CROSS_COMMIT = "cross_commit"  # the Generator provider returns another sha


# The verdict each edit must replay to against the unchanged L1.
_K6_EXPECTED = {
    SourceEdit.COMMENT_DOCSTRING: "noop",
    SourceEdit.RENAME_LOCAL: "noop",
    SourceEdit.NUMERIC_LITERAL: "diverged",
    SourceEdit.CROSS_COMMIT: "noop",
}


def _k6_target(edit: SourceEdit) -> tuple[str, str]:
    """The module and top-level function an edit changes."""
    if edit is SourceEdit.CROSS_COMMIT:
        return _K6_PROVIDER_MODULE, _K6_PROVIDER
    return _K6_MODULE, _K6_FUNCTION


@dataclasses.dataclass(frozen=True)
class StemSpec:
    """One stem the leaf benchmarks: its part, its negative-control part and
    its phase profile (``STEM:CONTROL_STEM[:PROFILE]`` on the command line)."""

    stem: str
    control_stem: str
    profile: Profile = Profile.FULL

    @classmethod
    def parse(cls, text: str) -> StemSpec:
        parts = text.split(":")
        if len(parts) not in (2, 3) or not all(parts):
            raise argparse.ArgumentTypeError(
                f"{text!r}: expected STEM:CONTROL_STEM[:{'|'.join(Profile)}]"
            )
        try:
            profile = Profile(parts[2]) if len(parts) == 3 else Profile.FULL
        except ValueError as exc:
            raise argparse.ArgumentTypeError(f"{text!r}: {exc}") from exc
        if parts[0] == parts[1]:
            raise argparse.ArgumentTypeError(f"{text!r}: the control is the stem")
        return cls(parts[0], parts[1], profile)

    def label(self) -> str:
        return f"{self.stem}:{self.control_stem}:{self.profile.value}"


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
    def __init__(self, spec: StemSpec):
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
        self.spec = spec
        self.stem = spec.stem
        self.control_stem = spec.control_stem
        self.profile = spec.profile
        self.out = OUT / spec.stem
        self.script = SCRIPTS / f"build_{spec.stem}.py"
        self.control_script = SCRIPTS / f"build_{spec.control_stem}.py"
        self.part = artefact_name(spec.stem)
        self.logs = self.out / "logs"
        self.l1 = self.logs / "L1.jsonl.gz"
        self.l2 = self.logs / "L2.jsonl.gz"
        self.a1 = self.out / "run1" / "sldprt" / self.part
        self.a2 = self.out / "run2" / "sldprt" / self.part
        self.a1_sha: str | None = None
        self.fatal: list[Fatal] = []
        self.report: dict[str, Any] = {
            "schema": SCHEMA,
            "experiment": "COM-conversation no-op replay (design section 1); never merge",
            "stem": spec.stem,
            "control_stem": spec.control_stem,
            "profile": spec.profile.value,
            "script": self.script.relative_to(REPO).as_posix(),
            "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "phases": {},
            "runs": {},
            "logs": {},
            "replay": None,
            "controls": {},
            "source_controls": {},
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
        write_json(self.out / "report.json", self.report)

    @contextlib.contextmanager
    def phase(self, key: str, title: str) -> Iterator[None]:
        started = time.perf_counter()
        row: dict[str, Any] = {"title": title, "status": Status.ERROR.value}
        self.report["phases"][key] = row
        with self.telemetry.span(f"{PREFIX}.{key}", title=title, stem=self.stem):
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
        self.telemetry.warn("\n".join([f"evidence {self.stem} {key}:", *bounded]))

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
        log = self.out / "children" / f"{name}.log"
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
            log.relative_to(self.out).as_posix(),
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

    def build(self, key: str, run: str, log: Path | None, callers: str = "") -> None:
        argv = [
            str(COM_REPLAY),
            "record",
            str(self.script),
            "--out-root",
            str(self.out / run),
        ]
        argv += ["--timing", str(self.out / f"{run}.timing.json")]
        if callers:
            argv += ["--callers", callers]
        if log is not None:
            argv += ["--log", str(log)]
        child = self.child(run, argv, _RECORD_TIMEOUT)
        timing_path = self.out / f"{run}.timing.json"
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
            "capture_bytes_stored": tree_bytes(capture),
            "callers": trailer.get("callers"),
            "clock_seconds": trailer.get("clock_seconds"),
            "header": loaded.header.to_json(),
            "trailer": {k: v for k, v in trailer.items() if k != "types"},
            "types": sorted(trailer.get("types", {})),
        }

    def phase0(self) -> None:
        self.build("W0", "run0", None)

    def phase1(self) -> None:
        # Full caller capture: L1 is what the replay, the controls and K1 cite.
        self.build("W1", "run1", self.l1, "full")
        if not self.a1.is_file():
            raise RuntimeError(f"run1 produced no {self.a1}")
        self.a1_sha = sha256(self.a1)
        self.report["seat_safety"]["a1_sha256"] = self.a1_sha

    def phase2(self) -> None:
        # The engine's default (divergence-only) capture: K4 judges this one.
        self.build("W2", "run2", self.l2)
        comparison = self.conversation.compare_conversations(self.l1, self.l2)
        self.report["verdicts"]["K1"] = {
            "pass": comparison["request_divergence"] is None,
            "criterion": "no recipe REQUEST divergence between L1 and L2 (Generator "
            "mask only); response differences are counted by member, never masked",
            **comparison,
        }
        self.evidence("K1", render_k1(self.report["verdicts"]["K1"]))

    def replay(
        self,
        name: str,
        script: Path,
        log: Path,
        scratch: str,
        overlay: Path | None = None,
    ) -> tuple[ChildRun, dict[str, Any] | None]:
        result = self.out / f"{scratch}.json"
        argv = [
            str(COM_REPLAY),
            "replay",
            str(script),
            "--log",
            str(log),
            "--base-outputs",
            str(self.out / "run1"),
            "--scratch",
            str(self.out / scratch),
            "--result",
            str(result),
        ]
        if overlay is not None:
            argv += ["--overlay", str(overlay)]
        child = self.child(
            name, argv, _REPLAY_TIMEOUT, env={"OTEL_SERVICE_NAME": "part-replay"}
        )
        payload = (
            json.loads(result.read_text(encoding="utf-8")) if result.is_file() else None
        )
        return child, payload

    def phase3(self) -> None:
        child, result = self.replay("replay", self.script, self.l1, "replay")
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
            "substitutions": result.get("substitutions"),
        }
        self.evidence("K2", render_k2(self.report["verdicts"]["K2"], result))

    def phase3b(self) -> None:
        perturbed = self.logs / "L1-ulp.jsonl.gz"
        seq = _perturb_first_float(self.conversation, self.l1, perturbed)
        controls: dict[str, Any] = {}
        child, result = self.replay(
            "control-script", self.control_script, self.l1, "replay-ctrl-script"
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

    def phase6(self) -> None:
        """K6: L1 replayed against mechanically edited copies of helpers the
        build runs, imported from an overlay directory: three source edits of
        one helper, and the Generator provider answering for another commit."""
        import _buildgraph

        closure = {Path(dep).name for dep in _buildgraph.module_deps_of(self.script)}
        controls: dict[str, Any] = {}
        for edit in SourceEdit:
            module, function = _k6_target(edit)
            target = SCRIPTS / f"{module}.py"
            if target.name not in closure:
                raise RuntimeError(
                    f"{target.name} is not in {self.script.name}'s closure"
                )
            source = target.read_bytes().decode("utf-8")
            edited, description = source_edit(source, function, edit)
            overlay = self.out / "overlays" / edit.value
            overlay.mkdir(parents=True, exist_ok=True)
            (overlay / target.name).write_bytes(edited.encode("utf-8"))
            child, result = self.replay(
                f"k6-{edit.value}",
                self.script,
                self.l1,
                f"replay-k6-{edit.value}",
                overlay=overlay,
            )
            controls[edit.value] = _source_control(edit, description, child, result)
        self.report["source_controls"] = controls
        self.report["verdicts"]["K6"] = _k6_verdict(controls)
        self.evidence("K6", render_k6(self.report["verdicts"]["K6"], controls))
        numeric = controls[SourceEdit.NUMERIC_LITERAL.value]
        if numeric["verdict"] == "noop":
            raise Fatal(
                "K6 vacuous: the numeric-literal control replayed as NOOP",
                scope=Scope.REPORT,
            )

    def phase4(self) -> None:
        if not (self.a1.is_file() and self.a2.is_file()):
            raise RuntimeError("A1/A2 missing")
        before = (sha256(self.a1), sha256(self.a2))
        out = self.out / "digest"
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
        runs = self.report["runs"]
        l1 = self.report["logs"].get(self.l1.name)
        l2 = self.report["logs"].get(self.l2.name)
        if not ({"W0", "W1", "W2", "WR"} <= set(walls) and l1 and l2):
            raise RuntimeError(f"K4 needs W0-W2, WR, L1 and L2; have {sorted(walls)}")
        w0, w1, wr = walls["W0"], walls["W1"], walls["WR"]
        window0 = (runs["run0"]["timing"] or {}).get("window_seconds")
        modes = {
            summary["callers"]: _record_cost(
                walls[key],
                w0,
                (runs[run]["timing"] or {}).get("window_seconds"),
                window0,
                summary,
                _archive_bytes(self.out / run),
            )
            for key, run, summary in (("W1", "run1", l1), ("W2", "run2", l2))
        }
        default = modes[self.conversation.DEFAULT_CALLERS.value]
        self.report["verdicts"]["K4"] = {
            "pass": wr <= 0.10 * w1
            and default["overhead_over_W0"] <= 0.03
            and default["log_plus_captures_bytes"] <= default["archive_bytes"],
            "criterion": "WR <= 10% W1; with the default caller capture (L2): "
            "(W2 - W0) <= 3% W0 and log + gzip captures <= tar.gz of its outputs",
            "walls_basis": "parent-measured subprocess walls (each includes interpreter start, imports, connect and teardown)",
            "archive_basis": "tar.gz of the run's outputs at _artifact_cache._PACK_LEVEL; captures gzip at the same level",
            "W0": w0,
            "W1": w1,
            "WR": wr,
            "WR_over_W1": wr / w1,
            "window0": window0,
            "replay_window": (self.report.get("replay") or {}).get("window_seconds"),
            "default_callers": self.conversation.DEFAULT_CALLERS.value,
            "by_callers": modes,
        }
        self.evidence("K4", render_k4(self.report["verdicts"]["K4"]))

    def phase5(self) -> None:
        if not self.a1.is_file():
            raise RuntimeError("A1 missing")
        d1 = self.out / "digest" / "D1.json"
        copy = self.out / "walk" / f"{self.part.removesuffix('.SLDPRT')}~walk.SLDPRT"
        out = self.out / "walk.json"
        argv = [
            str(Path(__file__)),
            "native",
            "walk",
            "--a1",
            str(self.a1),
            "--copy",
            str(copy),
            "--log",
            str(self.l1),
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
                "capture_stored_bytes": trailer.get("capture_stored_bytes"),
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
        "substitutions",
        "overlay",
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
        "read_point_errors": {
            "after_rebuild": _error_distribution(points, "live_after_rebuild"),
            "before_rebuild": _error_distribution(points, "live_before_rebuild"),
        },
        "recorded_spread": _recorded_spread(points),
        "mass_settings": walk.get("mass_settings"),
        "final_digest_equals_D1": walk.get("final_digest_differences") == [],
        "final_digest_differences": (walk.get("final_digest_differences") or [])[:50],
        "walk_seconds": walk.get("walk_seconds"),
        "u1": walk.get("u1"),
        "u16": walk.get("u16"),
        "features": walk.get("features"),
    }


def _errors(recorded: Any, live: Any) -> dict[str, float] | None:
    """How far apart a recorded and a live read are: the largest
    per-component relative error (the measure ``_within`` judges, relative to
    the larger magnitude), the largest component difference relative to the
    vector's largest component, and the largest absolute difference."""
    xs = recorded if isinstance(recorded, list) else [recorded]
    ys = live if isinstance(live, list) else [live]
    if live is None or len(xs) != len(ys):
        return None
    deltas = [abs(x - y) for x, y in zip(xs, ys, strict=True)]
    scales = [max(abs(x), abs(y)) for x, y in zip(xs, ys, strict=True)]
    largest = max(scales)
    return {
        "component": max(
            (d / s if s else 0.0) for d, s in zip(deltas, scales, strict=True)
        ),
        "vector": max(deltas) / largest if largest else 0.0,
        "absolute": max(deltas),
    }


def _error_distribution(points: list[dict[str, Any]], key: str) -> dict[str, Any]:
    """Per member: the spread of read-point errors, and the tolerance that
    would have passed every point (per component, and per vector)."""
    by_member: dict[str, list[dict[str, float]]] = {}
    for point in points:
        errors = _errors(point.get("recorded"), point.get(key))
        if errors is not None:
            by_member.setdefault(point["member"], []).append(errors)
    out: dict[str, Any] = {}
    for member, rows in sorted(by_member.items()):
        component = [r["component"] for r in rows]
        vector = [r["vector"] for r in rows]
        out[member] = {
            "count": len(rows),
            "component_max": max(component),
            "component_median": statistics.median(component),
            "vector_max": max(vector),
            "vector_median": statistics.median(vector),
            "absolute_max": max(r["absolute"] for r in rows),
            "rtol_to_pass_component": max(component),
            "rtol_to_pass_vector": max(vector),
        }
    return out


def _record_cost(
    wall: float,
    w0: float,
    window: float | None,
    window0: float | None,
    summary: dict[str, Any],
    archive: int,
) -> dict[str, Any]:
    """One recorded build's cost against the unrecorded W0: wall and build
    window overheads, the recorder's own clock (time inside recorded calls,
    split into the real COM call, caller capture, file capture and the rest of
    the engine), and its stored bytes against its outputs' archive."""
    audit = ((summary.get("trailer") or {}).get("escape_audit") or {}).get(
        "seconds"
    ) or 0.0
    clock = summary.get("clock_seconds") or {}
    calls = summary["calls"]
    engine = clock.get("engine")
    return {
        "wall": wall,
        "escape_audit_seconds": audit,
        "overhead_over_W0": (wall - audit - w0) / w0,
        "overhead_unadjusted_over_W0": (wall - w0) / w0,
        "window": window,
        "window_overhead_over_window0": (window - audit - window0) / window0
        if window and window0
        else None,
        "calls": calls,
        "clock_seconds": clock,
        "engine_us_per_call": engine * 1e6 / calls
        if engine is not None and calls
        else None,
        "log_bytes": summary["bytes"],
        "capture_bytes_stored": summary["capture_bytes_stored"],
        "log_plus_captures_bytes": summary["bytes"] + summary["capture_bytes_stored"],
        "archive_bytes": archive,
    }


def _recorded_spread(points: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Recorded reads of one member that the attribution gives the same
    feature, yet differ: the build read several model states under one name
    (the walk can reproduce only the state after that feature)."""
    groups: dict[tuple[str | None, str], list[dict[str, Any]]] = {}
    for point in points:
        groups.setdefault((point["feature"], point["member"]), []).append(point)
    spread = []
    for (feature, member), rows in groups.items():
        first = rows[0]
        worst = max(
            (_errors(first["recorded"], row["recorded"]) or {"component": 0.0})[
                "component"
            ]
            for row in rows
        )
        if worst > 0:
            spread.append(
                {
                    "feature": feature,
                    "member": member,
                    "seqs": [row["seq"] for row in rows],
                    "component_max": worst,
                }
            )
    return sorted(spread, key=lambda row: -row["component_max"])[:20]


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
        f"{trailer.get('capture_bytes')} bytes ({summary['capture_bytes_stored']} "
        f"stored gzip); write-back calls {summary['with_write_back']}, identity ops "
        f"{summary['identity_comparisons']}, raised {summary['raised']}, recipe "
        f"requests on inert handles {summary['recipe_requests_on_inert_handles']}",
        f"  callers {summary.get('callers')}, clock {_clip(summary.get('clock_seconds'))}",
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
    substitutions = result.get("substitutions") or {}
    for binding in substitutions.get("bindings") or []:
        lines.append(
            f"  masked {binding['rule']} at seq {binding['seq']}: "
            f"{binding['recorded']!r} -> {binding['replayed']!r}; "
            f"{substitutions.get('count')} readbacks rebound "
            f"{_clip(substitutions.get('by_member'))}"
        )
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


def _num(value: Any, spec: str) -> str:
    return "n/a" if value is None else format(value, spec)


def render_k4(k4: dict[str, Any]) -> list[str]:
    lines = [
        f"K4 {_verdict_word(k4)}: W0 {k4['W0']:.2f}s W1 {k4['W1']:.2f}s WR "
        f"{k4['WR']:.2f}s; WR/W1 {k4['WR_over_W1']:.3f}; window0 "
        f"{_num(k4.get('window0'), '.2f')}s, replay window "
        f"{_num(k4.get('replay_window'), '.2f')}s",
    ]
    for mode, cost in (k4.get("by_callers") or {}).items():
        default = " (default, judged)" if mode == k4.get("default_callers") else ""
        lines += [
            f"  callers={mode}{default}: wall {cost['wall']:.2f}s, overhead "
            f"{cost['overhead_over_W0']:+.4f} (unadjusted "
            f"{cost['overhead_unadjusted_over_W0']:+.4f}), window "
            f"{_num(cost['window'], '.2f')}s ("
            f"{_num(cost['window_overhead_over_window0'], '+.4f')}); engine "
            f"{_num(cost['engine_us_per_call'], '.1f')} us/call over "
            f"{cost['calls']} calls",
            f"    clock {_clip(cost['clock_seconds'])}",
            f"    log {cost['log_bytes']} B + gzip captures "
            f"{cost['capture_bytes_stored']} B = {cost['log_plus_captures_bytes']} B "
            f"vs outputs tar.gz {cost['archive_bytes']} B",
        ]
    return lines


def render_k5(k5: dict[str, Any]) -> list[str]:
    lines = [
        f"K5 {_verdict_word(k5)} (report only): features {k5.get('features')}, "
        f"unreachable {_clip(k5.get('unreachable_features'))}, read points "
        f"{k5.get('read_point_count')} within {k5.get('read_points_within_tolerance')}, "
        f"final digest == D1 {k5.get('final_digest_equals_D1')}, walk "
        f"{k5.get('walk_seconds')}s",
    ]
    errors = (k5.get("read_point_errors") or {}).get("after_rebuild") or {}
    for member, row in errors.items():
        lines.append(
            f"  {member} x{row['count']}: per-component rel max "
            f"{row['component_max']:.3g} median {row['component_median']:.3g}; "
            f"vector rel max {row['vector_max']:.3g} median "
            f"{row['vector_median']:.3g}; abs max {row['absolute_max']:.3g}"
        )
    spread = k5.get("recorded_spread") or []
    if spread:
        lines.append(
            f"  recorded reads differing under one feature attribution: "
            f"{len(spread)}; worst {_clip(spread[:3])}"
        )
    lines += render_mass_settings(k5.get("mass_settings"))
    lines += [
        f"  outside {_clip(k5.get('read_points_outside'))}",
        f"  final digest differences {_clip(k5.get('final_digest_differences'))}",
        f"  U1 {_clip(k5.get('u1'))}",
        f"  U16 {_clip((k5.get('u16') or {}).get('bar_kept_by_ForceRebuild3'))}",
    ]
    return lines


def render_mass_settings(settings: dict[str, Any] | None) -> list[str]:
    if not settings:
        return []
    if settings.get("error"):
        return [f"  mass settings probe error: {_clip(settings['error'])}"]
    lines = [
        "  final model re-read (worst per-component rel vs first read / vs L1's last read):"
    ]
    for label, row in (settings.get("reads") or {}).items():
        first = (settings.get("versus_first") or {}).get(label) or {}
        recorded = (settings.get("versus_recorded_final") or {}).get(label) or {}
        level = row.get("accuracy_level")
        lines.append(
            f"    {label}{'' if level is None else f' (AccuracyLevel {level})'}: "
            f"{_num(_worst(first), '.3g')} / {_num(_worst(recorded), '.3g')}"
        )
    return lines


def _worst(errors: dict[str, dict[str, float] | None]) -> float | None:
    values = [e["component"] for e in errors.values() if e is not None]
    return max(values) if values else None


def render_k6(k6: dict[str, Any], controls: dict[str, Any]) -> list[str]:
    cross = k6.get("cross_commit") or {}
    lines = [
        f"K6 {_verdict_word(k6)}: {k6.get('target')}; edited function reaches COM "
        f"{k6.get('edited_function_reaches_com')}; k6.cross_commit "
        f"{'PASS' if cross.get('pass') else 'FAIL'} ({cross.get('substitution_count')} "
        f"readbacks rebound in {_clip(cross.get('substituted_members'))})",
    ]
    for name, control in controls.items():
        substitutions = control.get("substitutions") or {}
        lines.append(
            f"  {name}: expected {control['expected']}, got {control['verdict']} "
            f"({control['served']}/{control['recorded']} served, loaded from overlay "
            f"{control['loaded_from_overlay']}, Python outputs differing "
            f"{len(control['py_output_mismatches'] or {})}, substitutions "
            f"{substitutions.get('count')}); edit {_clip(control['edit'])}"
        )
        if control["verdict"] != "noop":
            lines.append(
                f"    {control['member']} from {control['caller']}: "
                f"{_clip(control['reason'])}"
            )
    for binding in cross.get("bindings") or []:
        lines.append(
            f"  cross_commit binding at seq {binding['seq']}: {binding['recorded']!r} "
            f"-> {binding['replayed']!r}"
        )
    return lines


# ---------------------------------------------------------------------------
# K6 source-change controls: mechanical, AST-verified edits of one function
# ---------------------------------------------------------------------------


def source_edit(
    source: str, function: str, edit: SourceEdit
) -> tuple[str, dict[str, Any]]:
    """Apply one mechanical edit to the top-level ``function`` of ``source``
    and return the edited source with what changed. Each edit is verified on
    the AST: the comment/docstring edit leaves the docstring-free AST equal,
    the rename equals an AST-level rename, the literal edit changes that one
    constant, the cross-commit edit only appends a constant override of the
    function. Raises ValueError when the function offers no safe target."""
    tree = ast.parse(source)
    node = _function_def(tree, function)
    if edit is SourceEdit.COMMENT_DOCSTRING:
        return _edit_comment_docstring(source, node)
    if edit is SourceEdit.RENAME_LOCAL:
        return _edit_rename_local(source, tree, node)
    if edit is SourceEdit.CROSS_COMMIT:
        return _edit_foreign_provider(source, tree, node)
    return _edit_numeric_literal(source, node)


def _edit_foreign_provider(
    source: str, tree: ast.Module, node: ast.FunctionDef | ast.AsyncFunctionDef
) -> tuple[str, dict[str, Any]]:
    """Append ``def <provider>(): return <foreign sha>`` so every importer of
    the provider (bound after the module ran) stamps another commit's sha;
    nothing in git or the environment changes."""
    arguments = node.args
    if (
        isinstance(node, ast.AsyncFunctionDef)
        or arguments.posonlyargs
        or arguments.args
        or arguments.vararg
        or arguments.kwonlyargs
        or arguments.kwarg
    ):
        raise ValueError(f"{node.name} is not a synchronous zero-argument provider")
    newline = "\r\n" if "\r\n" in source else "\n"
    tail = "" if source.endswith(("\n", "\r")) else newline
    edited = (
        f"{source}{tail}{newline}{newline}"
        f"# K6 cross-commit control: the stamp another commit writes.{newline}"
        f"def {node.name}() -> str:  # noqa: F811{newline}"
        f"    return {_K6_FOREIGN_SHA!r}{newline}"
    )
    after = ast.parse(edited)
    override = after.body[-1]
    returns = getattr(override, "body", [None])[0]
    if not (
        ast.dump(ast.Module(body=after.body[:-1], type_ignores=[])) == ast.dump(tree)
        and isinstance(override, ast.FunctionDef)
        and override.name == node.name
        and isinstance(returns, ast.Return)
        and isinstance(returns.value, ast.Constant)
        and returns.value.value == _K6_FOREIGN_SHA
    ):
        raise ValueError(f"{node.name}: the override changed more than the provider")
    return edited, {"function": node.name, "returns": _K6_FOREIGN_SHA}


def _function_def(
    tree: ast.Module, name: str
) -> ast.FunctionDef | ast.AsyncFunctionDef:
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if node.name == name:
                return node
    raise ValueError(f"no top-level function {name}")


def _splice(source: str, edits: list[tuple[int, int, int, int, str]]) -> str:
    """Replace AST spans ``(line, col, end_line, end_col)`` -- 1-based lines,
    UTF-8 byte columns -- with text, keeping every other byte (and the file's
    newlines) as it was."""
    lines = io.StringIO(source, newline="").readlines()
    starts = [0]
    for line in lines:
        starts.append(starts[-1] + len(line))

    def offset(line: int, col: int) -> int:
        prefix = lines[line - 1].encode("utf-8")[:col].decode("utf-8")
        return starts[line - 1] + len(prefix)

    text = source
    for line, col, end_line, end_col, replacement in sorted(edits, reverse=True):
        start, end = offset(line, col), offset(end_line, end_col)
        text = text[:start] + replacement + text[end:]
    return text


def _docstring_free(source: str) -> str:
    tree = ast.parse(source)
    for node in ast.walk(tree):
        scopes = (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
        if isinstance(node, scopes) and ast.get_docstring(node, clean=False):
            node.body = node.body[1:] or [ast.Pass()]
    return ast.dump(tree)


def _edit_comment_docstring(
    source: str, node: ast.FunctionDef | ast.AsyncFunctionDef
) -> tuple[str, dict[str, Any]]:
    doc = ast.get_docstring(node, clean=False)
    if not doc:
        raise ValueError(f"{node.name} has no docstring")
    literal = node.body[0]
    first = (node.decorator_list[0] if node.decorator_list else node).lineno
    newline = "\r\n" if "\r\n" in source else "\n"
    changed = f"{doc} (K6 control: docstring-only edit.)"
    edited = _splice(
        source,
        [
            (
                literal.lineno,
                literal.col_offset,
                literal.end_lineno or literal.lineno,
                literal.end_col_offset or 0,
                repr(changed),
            ),
            (first, 0, first, 0, _K6_COMMENT + newline),
        ],
    )
    after = ast.get_docstring(_function_def(ast.parse(edited), node.name), clean=False)
    if _docstring_free(edited) != _docstring_free(source) or after != changed:
        raise ValueError(
            f"{node.name}: the edit changed more than a comment and the docstring"
        )
    return edited, {
        "function": node.name,
        "comment_before_line": first,
        "docstring_end": _clip(changed[-80:]),
    }


def _bound_otherwise(node: ast.FunctionDef | ast.AsyncFunctionDef) -> set[str]:
    """Names that some construct other than a plain assignment binds inside
    ``node``: renaming only their ``ast.Name`` uses would change behaviour."""
    names: set[str] = set()
    for inner in ast.walk(node):
        if isinstance(inner, ast.arg):
            names.add(inner.arg)
        elif isinstance(inner, (ast.Global, ast.Nonlocal)):
            names.update(inner.names)
        elif isinstance(inner, ast.ExceptHandler) and inner.name:
            names.add(inner.name)
        elif isinstance(inner, ast.alias):
            names.add((inner.asname or inner.name).split(".")[0])
        elif isinstance(inner, (ast.MatchAs, ast.MatchStar)) and inner.name:
            names.add(inner.name)
        elif isinstance(inner, ast.MatchMapping) and inner.rest:
            names.add(inner.rest)
        elif isinstance(inner, (ast.FunctionDef, ast.AsyncFunctionDef)):
            names.add(inner.name)
        elif isinstance(inner, ast.ClassDef):
            # A class body's assignments are attributes, not locals.
            names.add(inner.name)
            names.update(
                n.id
                for n in ast.walk(inner)
                if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)
            )
    names.discard(node.name)
    return names


def _identifiers(tree: ast.AST) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(tree):
        for field in ("id", "arg", "attr", "name", "asname", "rest"):
            value = getattr(node, field, None)
            if isinstance(value, str):
                names.add(value)
        if isinstance(node, (ast.Global, ast.Nonlocal)):
            names.update(node.names)
    return names


def _edit_rename_local(
    source: str, tree: ast.Module, node: ast.FunctionDef | ast.AsyncFunctionDef
) -> tuple[str, dict[str, Any]]:
    reads_names = sorted(
        {
            n.func.id
            for n in ast.walk(node)
            if isinstance(n, ast.Call)
            and isinstance(n.func, ast.Name)
            and n.func.id in _INTROSPECTION
        }
    )
    if reads_names:
        raise ValueError(f"{node.name} calls {reads_names}: a rename is observable")
    blocked = _bound_otherwise(node)
    taken = _identifiers(tree)
    stores = sorted(
        (
            n
            for n in ast.walk(node)
            if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Store)
        ),
        key=lambda n: (n.lineno, n.col_offset),
    )
    for store in stores:
        old, new = store.id, f"{store.id}{_K6_SUFFIX}"
        if old in blocked or new in taken:
            continue
        uses = [n for n in ast.walk(node) if isinstance(n, ast.Name) and n.id == old]
        edited = _splice(
            source,
            [
                (
                    n.lineno,
                    n.col_offset,
                    n.end_lineno or n.lineno,
                    n.end_col_offset or 0,
                    new,
                )
                for n in uses
            ],
        )
        expected = ast.parse(source)
        for n in ast.walk(_function_def(expected, node.name)):
            if isinstance(n, ast.Name) and n.id == old:
                n.id = new
        # Differs when the source text names the variable some other way,
        # e.g. an f-string ``{x=}`` whose literal part spells the name.
        if ast.dump(ast.parse(edited)) != ast.dump(expected):
            continue
        return edited, {
            "function": node.name,
            "from": old,
            "to": new,
            "occurrences": len(uses),
        }
    raise ValueError(f"{node.name} has no local that renames mechanically")


def _edit_numeric_literal(
    source: str, node: ast.FunctionDef | ast.AsyncFunctionDef
) -> tuple[str, dict[str, Any]]:
    constants = sorted(
        (
            n
            for n in ast.walk(node)
            if isinstance(n, ast.Constant) and type(n.value) in (int, float)
        ),
        key=lambda n: (n.lineno, n.col_offset),
    )
    if not constants:
        raise ValueError(f"{node.name} has no numeric literal")
    first = constants[0]
    value = first.value
    moved = value + 1 if isinstance(value, int) else math.nextafter(value, math.inf)
    edited = _splice(
        source,
        [
            (
                first.lineno,
                first.col_offset,
                first.end_lineno or first.lineno,
                first.end_col_offset or 0,
                repr(moved),
            )
        ],
    )
    expected = ast.parse(source)
    for n in ast.walk(_function_def(expected, node.name)):
        if isinstance(n, ast.Constant) and (n.lineno, n.col_offset) == (
            first.lineno,
            first.col_offset,
        ):
            n.value = moved
    if ast.dump(ast.parse(edited)) != ast.dump(expected):
        raise ValueError(
            f"{node.name}: the literal edit changed more than one constant"
        )
    return edited, {
        "function": node.name,
        "line": first.lineno,
        "from": value,
        "to": moved,
    }


def _source_control(
    edit: SourceEdit,
    description: dict[str, Any],
    child: ChildRun,
    result: dict[str, Any] | None,
) -> dict[str, Any]:
    result = result or {}
    modules = (result.get("overlay") or {}).get("modules") or {}
    module = modules.get(_k6_target(edit)[0]) or {}
    divergence = result.get("divergence") or {}
    return {
        "edit": description,
        "expected": _K6_EXPECTED[edit],
        "verdict": result.get("verdict"),
        "reason": result.get("reason"),
        "served": result.get("served"),
        "recorded": result.get("recorded"),
        "loaded_from_overlay": module.get("from_overlay"),
        "overlay_module": module,
        "py_output_mismatches": result.get("py_output_mismatches"),
        "substitutions": result.get("substitutions"),
        "script_error": result.get("script_error"),
        "member": divergence.get("member_actual"),
        "caller": divergence.get("caller_actual"),
        "divergence": divergence or None,
        "child": child.to_json(),
    }


def _k6_verdict(controls: dict[str, Any]) -> dict[str, Any]:
    """K6 passes when the behaviour-preserving edits replay as NOOP (every
    request served, Python outputs equal), the literal edit DIVERGES, every
    replay imported the edited module, the divergence names the edited
    function as its caller (so the edited code ran and reached COM: the NOOP
    controls are not vacuous), and the cross-commit control replays NOOP with
    the recorded Generator rebound to the foreign one and read back rebound."""
    numeric = controls[SourceEdit.NUMERIC_LITERAL.value]
    reaches = f"{_K6_MODULE}:{_K6_FUNCTION}:" in (numeric.get("caller") or "")
    expected = {
        name: control["verdict"] == control["expected"]
        and control["loaded_from_overlay"] is True
        and (
            control["expected"] != "noop"
            or (
                control["served"] == control["recorded"]
                and not control["py_output_mismatches"]
            )
        )
        for name, control in controls.items()
    }
    cross = controls[SourceEdit.CROSS_COMMIT.value]
    substitutions = cross.get("substitutions") or {}
    foreign = [
        binding
        for binding in substitutions.get("bindings") or []
        if binding["recorded"] != binding["replayed"]
        and binding["replayed"].endswith(f"@ {_K6_FOREIGN_SHA}")
    ]
    cross_commit = {
        "pass": expected[SourceEdit.CROSS_COMMIT.value]
        and bool(foreign)
        and substitutions.get("count", 0) >= 1,
        "criterion": f"{_K6_PROVIDER_MODULE}.{_K6_PROVIDER} answering "
        f"{_K6_FOREIGN_SHA!r}: NOOP, every request served, Python outputs equal, "
        "the recorded Generator bound to the foreign one and >= 1 readback rebound",
        "bindings": foreign,
        "substitution_count": substitutions.get("count"),
        "substituted_members": substitutions.get("by_member"),
    }
    return {
        "pass": all(expected.values()) and reaches and cross_commit["pass"],
        "criterion": "comment/docstring and local-rename edits NOOP with every request "
        "served and Python outputs equal; numeric-literal edit DIVERGED with the "
        "edited function as the caller; cross_commit as stated; every replay "
        "imported the edited module",
        "target": f"{_K6_MODULE}.{_K6_FUNCTION}",
        "as_expected": expected,
        "edited_function_reaches_com": reaches,
        "cross_commit": cross_commit,
        "input_pins": "the header pins the engine sha, ENVIRONMENT_KEYS and external "
        "files named in COM arguments; script and helper source are never pinned "
        "(header.script_sha256 is informational), so changed source is replayed, "
        "never refused as input_mismatch; the Generator stamp is the one masked "
        "argument, bound recorded -> replayed and substituted in equal readbacks",
        "verdicts": {name: control["verdict"] for name, control in controls.items()},
    }


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
    exact(
        "dimensions.names",
        [dimension_key(d[0]) for d in dims_a],
        [dimension_key(d[0]) for d in dims_b],
    )
    for x, y in zip(dims_a, dims_b, strict=False):
        numeric(
            f"dimensions[{dimension_key(x[0])}]",
            x[1],
            y[1],
            _TOLERANCE["dimension_si"],
        )
    return out


def dimension_key(full_name: str) -> str:
    """A dimension's full name ``Name@Feature@<document>.Part`` with the
    document's name replaced: the walk's copy and A1 are the same part under
    different file names."""
    head, at, document = full_name.rpartition("@")
    if not at or "@" not in head:
        return full_name
    _, dot, extension = document.rpartition(".")
    return f"{head}@<document>{dot}{extension if dot else ''}"


def benchmark(specs: Sequence[StemSpec]) -> int:
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
    combined: dict[str, Any] = {
        "schema": SCHEMA,
        "experiment": "COM-conversation no-op replay (design section 1); never merge",
        "started_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "stems": [],
        "exit": None,
    }
    leaves: list[Leaf] = []
    try:
        with _telemetry.build_session("replay-noop", script="benchmark_replay_noop"):
            labels = ",".join(spec.label() for spec in specs)
            with _telemetry.span(PREFIX, stems=labels) as root:
                context = root.get_span_context()
                combined["trace_id"] = f"{context.trace_id:032x}"
                for spec in specs:
                    leaf = Leaf(spec)
                    leaf.report["trace_id"] = combined["trace_id"]
                    leaves.append(leaf)
                    _run_stem(leaf, leaves[:-1])
                _recheck_earlier(leaves, "at_end")
        combined["retained_span_count"] = len(retained.completed)
    finally:
        for leaf in leaves:
            if (leaf.report.get("exit") or {}).get("code") is not None:
                code, reason = _exit_of(leaf)
                leaf.report["exit"] = {"code": code, "reason": reason}
        code, reason = _combined_exit(leaves)
        combined["exit"] = {"code": code, "reason": reason}
        combined["stems"] = [_stem_row(leaf) for leaf in leaves]
        try:
            for leaf in leaves:
                leaf.save()
            write_json(OUT / "report.json", combined)
            retained.write()
        except Exception as exc:  # noqa: BLE001 - an unwritable report is fatal
            _telemetry.error(f"report could not be written: {exc}")
            code = code or 1
    for leaf in leaves:
        _log_summary(leaf)
    _log_combined(combined, code)
    _telemetry.shutdown()
    return code


def _run_stem(leaf: Leaf, earlier: list[Leaf]) -> None:
    """One stem's phases, unless an earlier stem stopped the seat or an
    earlier stem's artefact changed since it was recorded."""
    import _telemetry

    stopped = [other.stem for other in earlier if other.seat_stopped()]
    if not stopped:
        stopped = _recheck_earlier(earlier, f"before_{leaf.stem}")
    if stopped:
        leaf.report["exit"] = {
            "code": None,
            "reason": f"not run: a seat fault in {stopped} stopped later stems",
        }
        leaf.save()
        return
    started = time.perf_counter()
    with _telemetry.span(f"{PREFIX}.stem", stem=leaf.stem, profile=leaf.profile.value):
        code, reason = _run_phases(leaf)
    leaf.report["exit"] = {"code": code, "reason": reason}
    leaf.report["seconds"] = time.perf_counter() - started
    leaf.save()


def _recheck_earlier(leaves: list[Leaf], when: str) -> list[str]:
    """Re-hash every earlier stem's A1: no later step may write it. Returns
    the stems whose A1 changed (a seat fault recorded on that stem)."""
    changed = []
    for leaf in leaves:
        try:
            leaf.check_a1(when)
        except Fatal as fault:
            leaf.fatal.append(fault)
            changed.append(leaf.stem)
        leaf.save()
    return changed


# Phases per profile, in run order: (key, title, needs the seat).
_PHASES = (
    ("phase0", "clean build, unrecorded (W0)", True),
    ("phase1", "clean build, recorded with full caller capture (L1, W1)", True),
    ("phase2", "clean build, recorded with default caller capture (L2, W2); K1", True),
    ("phase3", "replay of L1 with SolidWorks untouched (WR); K2", False),
    ("phase3b", "negative controls; K2b", False),
    ("phase6", "source-change controls; K6", False),
    ("phase4", "geometry digests D1/D2; K3", True),
    ("k4", "walls and sizes; K4", False),
    ("phase5", "rollback walk on a copy of A1; K5", True),
)
_PROFILE_PHASES = {
    Profile.FULL: frozenset(key for key, _, _ in _PHASES),
    Profile.REPLAY: frozenset({"phase1", "phase3", "phase3b", "phase6"}),
}


def _run_phases(leaf: Leaf) -> tuple[int, str]:
    selected = _PROFILE_PHASES[leaf.profile]
    first_build = True
    for key, title, needs_seat in _PHASES:
        if key not in selected:
            leaf.skip(key, title, f"not in the {leaf.profile.value} profile")
            continue
        if needs_seat and leaf.seat_stopped():
            leaf.skip(key, title, "an earlier fault made further native steps unsafe")
            continue
        with leaf.phase(key, title):
            getattr(leaf, key)()
        failed = leaf.report["phases"][key]["status"] != Status.OK.value
        if first_build and failed and not leaf.fatal:
            leaf.fatal.append(Fatal(f"{key} (the stem's first clean build) failed"))
        first_build = False
    with leaf.phase("assumptions", "R/U evidence map"):
        leaf.assumptions()
    return _exit_of(leaf)


def _exit_of(leaf: Leaf) -> tuple[int, str]:
    if leaf.fatal:
        first = leaf.fatal[0]
        watchdog = next((f.code for f in leaf.fatal if f.code != 1), None)
        return watchdog or first.code, "; ".join(f.reason for f in leaf.fatal)
    return 0, "completed; K verdicts are results, not exit codes"


def _combined_exit(leaves: list[Leaf]) -> tuple[int, str]:
    """The leaf's exit: the first stem's fault code (a watchdog code first),
    0 when every stem ran without an infrastructure or soundness fault."""
    exits = [(leaf.stem, *_exit_of(leaf)) for leaf in leaves]
    faults = [(stem, code, reason) for stem, code, reason in exits if code]
    if not faults:
        return 0, f"{len(leaves)} stem(s) completed; K verdicts are results"
    watchdog = next((code for _, code, _ in faults if code != 1), None)
    return watchdog or faults[0][1], "; ".join(
        f"{stem}: {reason}" for stem, _, reason in faults
    )


def _stem_row(leaf: Leaf) -> dict[str, Any]:
    return {
        "stem": leaf.stem,
        "control_stem": leaf.control_stem,
        "profile": leaf.profile.value,
        "report": f"{leaf.stem}/report.json",
        "exit": leaf.report.get("exit"),
        "seconds": leaf.report.get("seconds"),
        "verdicts": _verdict_passes(leaf),
        "phases": {k: row.get("status") for k, row in leaf.report["phases"].items()},
        "walls": {k: round(v, 2) for k, v in leaf.report["walls"].items()},
        "seat_safety_violations": leaf.report["seat_safety"]["violations"],
    }


def _verdict_passes(leaf: Leaf) -> dict[str, Any]:
    return {
        key: value.get("pass")
        for key, value in leaf.report["verdicts"].items()
        if isinstance(value, dict)
    }


def _log_summary(leaf: Leaf) -> None:
    """The farm publishes no outputs of a failed leaf: the summary rides telemetry."""
    import _telemetry

    exit_ = leaf.report.get("exit") or {}
    code = exit_.get("code")
    verdicts = _verdict_passes(leaf)
    phases = {key: row.get("status") for key, row in leaf.report["phases"].items()}
    walls = {key: round(value, 2) for key, value in leaf.report["walls"].items()}
    replay = leaf.report.get("replay") or {}
    message = (
        f"replay-noop {leaf.stem} ({leaf.profile.value}): exit {code} "
        f"({exit_.get('reason')}); verdicts {verdicts}; phases {phases}; walls "
        f"{walls}; replay {replay.get('verdict')} "
        f"{replay.get('served')}/{replay.get('recorded')}"
    )
    _telemetry.event(
        f"{PREFIX}.summary",
        stem=leaf.stem,
        profile=leaf.profile.value,
        exit_code=-1 if code is None else code,
        reason=str(exit_.get("reason")),
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


def _log_combined(combined: dict[str, Any], code: int) -> None:
    import _telemetry

    rows = [
        f"  {row['stem']} ({row['profile']}): exit {(row['exit'] or {}).get('code')}, "
        f"verdicts {row['verdicts']}, {_num(row['seconds'], '.0f')}s"
        for row in combined["stems"]
    ]
    reason = (combined.get("exit") or {}).get("reason")
    (_telemetry.success if code == 0 else _telemetry.error)(
        "\n".join([f"replay-noop: exit {code} ({reason})", *rows])
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


def _mass_settings(
    model: Any, extension: Any, points: list[dict[str, Any]]
) -> dict[str, Any]:
    """Report-only, on the opened final model before any rollback: mass
    properties read twice through CreateMassProperty, through
    CreateMassProperty2 at its default and at each AccuracyLevel, and once
    more after ForceRebuild3; each read compared with the first and with L1's
    last recorded read of each member (the build's final state)."""
    from _com import _early_bound

    reads: dict[str, dict[str, Any]] = {}

    def read(label: str, creator: str, accuracy: int | None = None) -> None:
        interface = (
            "IMassProperty2" if creator == "CreateMassProperty2" else "IMassProperty"
        )
        mass = _early_bound(getattr(extension, creator)(), interface)
        row: dict[str, Any] = {}
        if accuracy is not None:
            mass.AccuracyLevel = accuracy
        if interface == "IMassProperty2":
            row["accuracy_level"] = int(mass.AccuracyLevel)
        row.update({m: _plain_live(getattr(mass, m)) for m in _MASS_MEMBERS})
        reads[label] = row

    try:
        read("CreateMassProperty", "CreateMassProperty")
        read("CreateMassProperty again", "CreateMassProperty")
        read("CreateMassProperty2 default", "CreateMassProperty2")
        for level in _MASS_ACCURACY_LEVELS:
            read(f"CreateMassProperty2 accuracy {level}", "CreateMassProperty2", level)
        model.ForceRebuild3(False)
        read("CreateMassProperty after ForceRebuild3", "CreateMassProperty")
    except Exception as exc:  # noqa: BLE001 - a report-only probe records its failure
        return {"error": f"{type(exc).__name__}: {exc}", "reads": reads}
    final = {point["member"]: point for point in points}
    first = reads["CreateMassProperty"]
    return {
        "reads": reads,
        "recorded_creators": sorted({point["creator"] for point in points}),
        "recorded_final": {
            member: {k: p[k] for k in ("seq", "creator", "feature")}
            for member, p in final.items()
        },
        "versus_first": {
            label: {m: _errors(first[m], row[m]) for m in _MASS_MEMBERS}
            for label, row in reads.items()
        },
        "versus_recorded_final": {
            label: {
                m: _errors(final[m]["recorded"], row[m]) if m in final else None
                for m in _MASS_MEMBERS
            }
            for label, row in reads.items()
        },
    }


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
            report["mass_settings"] = _mass_settings(model, extension, points)
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
    run.add_argument(
        "--stem",
        dest="stems",
        action="append",
        type=StemSpec.parse,
        metavar=f"STEM:CONTROL_STEM[:{'|'.join(Profile)}]",
        help=f"repeatable; stems run in order (default {' '.join(DEFAULT_STEM_SPECS)})",
    )
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
        specs = args.stems or [StemSpec.parse(text) for text in DEFAULT_STEM_SPECS]
        stems = [spec.stem for spec in specs]
        if len(set(stems)) != len(stems):
            parser.error(f"a stem is listed twice: {stems}")
        for spec in specs:
            for stem in (spec.stem, spec.control_stem):
                if not (SCRIPTS / f"build_{stem}.py").is_file():
                    parser.error(f"no build script build_{stem}.py")
        return benchmark(specs)
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
