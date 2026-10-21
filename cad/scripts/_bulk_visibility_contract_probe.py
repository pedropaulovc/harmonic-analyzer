"""Branch-only native visibility experiment; never replaces production isolation.

The module is import-safe for pure offline tests: COM, SDK, telemetry and image
libraries are imported only by the explicit native entry point. See DEVELOPING.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import ExitStack, contextmanager
from dataclasses import asdict, dataclass
from enum import StrEnum
import hashlib
import json
import math
import os
from pathlib import Path
import time
import traceback
from typing import Any
import uuid


class Verdict(StrEnum):
    NOT_EXECUTED = "not_executed"
    RUNNING = "running"
    PASSED = "passed"
    CONSTRUCTION = "unsupported_construction"
    IDENTITY = "unsupported_identity"
    SINGLE = "single_control_failed"
    SELECTION = "selection_contract_failed"
    PLURAL = "plural_effect_failed"
    VISUAL = "unsupported_visual_oracle"
    PRESERVATION = "preservation_failed"
    RESTORATION = "restoration_failed"
    DEADLINE = "deadline_exceeded"
    INTERRUPTED = "interrupted"
    REFUSAL = "expected_refusal"
    INJECTED = "expected_injected_exception"


class Stage(StrEnum):
    CONSTRUCTION = "construction_identity"
    FUNDAMENTAL = "fundamental_native_capability"
    VISUAL = "visual_persistence"
    EXTENDED = "extended_contract"
    CLEANUP = "cleanup_handoff"


class Case(StrEnum):
    CONSTRUCTION = "C00"
    SINGLE_HIDE = "C01"
    SINGLE_SHOW = "C02"
    BULK_HIDE = "C03"
    BULK_SHOW = "C04"
    VISUAL = "C05"
    PERSISTENCE = "C06"
    CROSS_FAMILY = "C07"
    MIXED = "C08"
    HIDDEN_ANCESTOR = "C09"
    INHERITED_REFUSAL = "C10"
    MISSING_REFUSAL = "C11"
    NO_CHANGE = "C12"
    MARKED_VIEW = "C13"
    SHEET_CONTEXT = "C14"
    WRONG_VIEW = "C15"
    FLAGS_00 = "C16"
    FLAGS_01 = "C17"
    FLAGS_10 = "C18"
    FLAGS_11 = "C19"
    GRAPHICS_ENABLED = "C20"
    GRAPHICS_ENABLED_EXCEPTION = "C21"
    GRAPHICS_DISABLED = "C22"
    GRAPHICS_DISABLED_EXCEPTION = "C23"
    EXCEPTION_ENABLED = "C24"
    EXCEPTION_DISABLED = "C25"
    BETWEEN_ENABLED = "C26"
    BETWEEN_DISABLED = "C27"
    CLEANUP = "C28"
    NESTED_SELECTION = "C29"


class Export(StrEnum):
    BASELINE = "E0"
    REPEAT = "E1"
    HIDDEN = "E2"
    SHOWN = "E3"
    PERSISTED = "E4"
    REOPENED = "E5"


class SnapshotKind(StrEnum):
    FULL = "F"
    SOURCE = "S"


class RunMode(StrEnum):
    EXPERIMENT = "experiment"
    RESTORING = "restoring"
    CLEANUP = "cleanup"


class AcquisitionState(StrEnum):
    UNRESOLVED = "unresolved"
    PENDING = "owned_pending_admission"
    ADMITTED = "admitted"
    DISCARD_ATTEMPTED = "discard_attempted"


class ActivationState(StrEnum):
    PREPARING = "preparing"
    CALLING = "calling"
    VALIDATING = "validating"
    PASSED = "passed"
    FAILED = "failed"


class ActiveObservation(StrEnum):
    NOT_OBSERVED = "not_observed"
    OBSERVING = "observing"
    NULL = "null"
    OWNED = "owned"
    FOREIGN = "foreign_or_ambiguous"
    NON_NULL = "non_null"
    ERROR = "error"


class DrawingEditMode(StrEnum):
    SHEET = "sheet"
    FORMAT = "sheet_format"


class ViewId(StrEnum):
    A = "BulkTarget"
    B = "BulkSentinel"


class NodeId(StrEnum):
    N = "N"
    P1 = "P1"
    P2 = "P2"
    Q1 = "Q1"
    Q2 = "Q2"


class Family(StrEnum):
    P = "ch-rod-pivot-pin"
    Q = "ch-pivot-shaft"
    MISSING = "absent-fixture-family"


class Document(StrEnum):
    P = "part_P"
    Q = "part_Q"
    N_AUTHOR = "authoring_N"
    N = "canonical_N"
    R_AUTHOR = "authoring_R"
    R = "canonical_R"
    DRAWING = "fixture_drawing"


class Injection(StrEnum):
    NONE = "none"
    AFTER_SELECTION = "after_selection_before_command"
    BETWEEN_BATCHES = "after_first_batch_before_second_selection"


class Controls(StrEnum):
    RUNNING = "running"
    PASSED = "controls_passed"
    FAILED = "controls_failed"
    UNSUPPORTED = "unsupported"
    INTERRUPTED = "interrupted"


class ProbeFailure(RuntimeError):
    def __init__(self, verdict: Verdict, message: str):
        super().__init__(message)
        self.verdict = verdict


class PrewriteRefusal(ProbeFailure):
    def __init__(self, message: str):
        super().__init__(Verdict.REFUSAL, message)


class InjectedFailure(RuntimeError):
    def __init__(self, case: Case, point: Injection):
        self.case, self.point = case, point
        super().__init__(f"bulk-visibility-controlled:{case}:{point}")


@dataclass(frozen=True)
class NodeState:
    key: NodeId
    parent: NodeId | None
    family: Family | None
    own: bool
    component_path: str
    source_path: str
    configuration: str
    transform: tuple[float, ...]


PARENTS = {
    NodeId.N: None,
    NodeId.P1: NodeId.N,
    NodeId.P2: NodeId.N,
    NodeId.Q1: NodeId.N,
    NodeId.Q2: None,
}
FAMILIES = {
    NodeId.N: None,
    NodeId.P1: Family.P,
    NodeId.P2: Family.P,
    NodeId.Q1: Family.Q,
    NodeId.Q2: Family.Q,
}
LEAVES = (NodeId.P1, NodeId.P2, NodeId.Q1, NodeId.Q2)
SETUP_REBUILD_CASES = frozenset(
    (
        Case.CROSS_FAMILY,
        Case.MIXED,
        Case.HIDDEN_ANCESTOR,
        Case.NO_CHANGE,
        Case.MARKED_VIEW,
        Case.BETWEEN_ENABLED,
        Case.BETWEEN_DISABLED,
    )
)
MARKED_CASES = frozenset(
    (
        Case.MARKED_VIEW,
        Case.GRAPHICS_ENABLED,
        Case.GRAPHICS_ENABLED_EXCEPTION,
        Case.GRAPHICS_DISABLED,
        Case.GRAPHICS_DISABLED_EXCEPTION,
        Case.EXCEPTION_ENABLED,
        Case.EXCEPTION_DISABLED,
        Case.BETWEEN_ENABLED,
        Case.BETWEEN_DISABLED,
        Case.NESTED_SELECTION,
    )
)
OVERALL_BUDGET_SECONDS = 970.0
CLEANUP_BUDGET_SECONDS = 70.0
NORMAL_BUDGET_SECONDS = OVERALL_BUDGET_SECONDS - CLEANUP_BUDGET_SECONDS
PAGE_SIZE = (5100, 3300)
DPI = 300
MAX_IMAGE_BYTES = 256 * 1024 * 1024
MAX_FILES_BYTES = 192 * 1024 * 1024
MAX_REPORT_BYTES = 4 * 1024 * 1024
# Committed probe-owned copy of the published, known-positive assembly seed.
# Keep the exact identity in this recipe input; changed bytes must refuse.
ASSEMBLY_TEMPLATE_PATH = (
    Path(__file__).resolve().parents[1]
    / "templates"
    / "bulk-visibility-contract-probe.ASMDOT"
)
ASSEMBLY_TEMPLATE_SIZE = 19046
ASSEMBLY_TEMPLATE_SHA256 = (
    "1950533a66f08e77a710016d6dca1523bbe4ada8c294d37c0998b90208a58ea6"
)


def require(condition: bool, verdict: Verdict, message: str) -> None:
    if not condition:
        raise ProbeFailure(verdict, message)


def api_bool(value: Any, label: str, verdict: Verdict = Verdict.PRESERVATION) -> bool:
    require(
        type(value) is bool, verdict, f"{label}: expected API Boolean, got {value!r}"
    )
    return value


def api_int(value: Any, label: str, verdict: Verdict = Verdict.PRESERVATION) -> int:
    require(type(value) is int, verdict, f"{label}: expected integer, got {value!r}")
    return value


def _use_sheet_scale(value: Any, verdict: Verdict = Verdict.PRESERVATION) -> int:
    """Normalize this property's observed Boolean or documented integer flag."""
    require(
        type(value) in (bool, int) and value in (0, 1),
        verdict,
        f"UseSheetScale: expected Boolean or integer 0/1, got {value!r}",
    )
    return int(value)


def api_string(value: Any, label: str, *, empty: bool = False) -> str:
    require(
        type(value) is str and (empty or bool(value)),
        Verdict.PRESERVATION,
        f"{label}: missing/invalid native string {value!r}",
    )
    return value


def failure_verdict(error: BaseException) -> Verdict:
    if isinstance(error, ProbeFailure):
        return error.verdict
    if isinstance(error, (KeyboardInterrupt, SystemExit, InjectedFailure)):
        return Verdict.INTERRUPTED
    return getattr(error, "probe_verdict", Verdict.CONSTRUCTION)


def array(value: Any, label: str, *, empty: bool = False) -> tuple:
    if empty and value is None:
        return ()
    require(
        isinstance(value, (tuple, list)),
        Verdict.PRESERVATION,
        f"{label}: expected SAFEARRAY result, got {type(value).__name__}",
    )
    return tuple(value)


def matrix(value: Any, label: str) -> tuple[float, ...]:
    result = array(value, label)
    require(
        len(result) == 16
        and all(type(x) in (int, float) and math.isfinite(x) for x in result),
        Verdict.CONSTRUCTION,
        f"{label}: invalid 16-double transform",
    )
    return tuple(float(x) for x in result)


def translation(x: float) -> tuple[float, ...]:
    return (
        1.0,
        0.0,
        0.0,
        0.0,
        1.0,
        0.0,
        0.0,
        0.0,
        1.0,
        x,
        0.0,
        0.0,
        1.0,
        0.0,
        0.0,
        0.0,
    )


def equal_transform(actual: Sequence[float], expected: Sequence[float]) -> bool:
    return len(actual) == len(expected) == 16 and all(
        math.isfinite(a) and abs(a - b) <= (1e-9 if 9 <= i <= 11 else 1e-12)
        for i, (a, b) in enumerate(zip(actual, expected, strict=True))
    )


def effective(nodes: Mapping[NodeId, NodeState]) -> dict[NodeId, bool]:
    require(
        set(nodes) == set(NodeId),
        Verdict.PRESERVATION,
        "incomplete/extra fixture nodes",
    )
    result: dict[NodeId, bool] = {}
    for key in (NodeId.N, *LEAVES):
        node = nodes[key]
        require(
            node.key is key
            and type(node.own) is bool
            and node.parent == PARENTS[key]
            and node.family == FAMILIES[key],
            Verdict.PRESERVATION,
            f"{key}: wrong real-parent/family topology",
        )
        result[key] = node.own and (node.parent is None or result[node.parent])
    return result


def plan_families(
    nodes: Mapping[NodeId, NodeState], requested: frozenset[Family]
) -> tuple[tuple[NodeId, ...], tuple[NodeId, ...]]:
    """Fixture-only prewrite policy, preserving real parents and all no-op state."""
    effective(nodes)
    if not requested:
        raise PrewriteRefusal("empty family request")
    found = {node.family for node in nodes.values() if node.family is not None}
    missing = requested - found
    if missing:
        raise PrewriteRefusal(f"missing families: {sorted(missing)}")
    drawable = {
        node.family
        for node in nodes.values()
        if node.family is not None and (node.parent is None or nodes[node.parent].own)
    }
    if requested - drawable:
        raise PrewriteRefusal(
            f"requested families inherit hidden ancestors: {sorted(requested - drawable)}"
        )
    hide = tuple(
        key for key in LEAVES if nodes[key].own and nodes[key].family not in requested
    )
    show = tuple(
        key for key in LEAVES if not nodes[key].own and nodes[key].family in requested
    )
    return hide, show


def selected_bijection(
    identities: Sequence[Sequence[int]],
    types: Sequence[int],
    marks: Sequence[int],
    own_views: Sequence[int],
    selection_views: Sequence[int],
    count: int,
) -> None:
    """Validate native equality receipts, not Python wrapper/pointer equality."""
    require(
        type(count) is int
        and count > 0
        and len(identities) == count
        and all(len(row) == count for row in identities),
        Verdict.SELECTION,
        "partial/extra native selection",
    )
    require(
        all(
            value in (0, 1) and type(value) is int
            for row in identities
            for value in row
        ),
        Verdict.IDENTITY,
        "unsupported/inconsistent selected native identity",
    )
    require(
        all(sum(row) == 1 for row in identities)
        and all(sum(row[i] for row in identities) == 1 for i in range(count)),
        Verdict.SELECTION,
        "selection is not a duplicate-free exact identity bijection",
    )
    require(
        len(types) == len(marks) == len(own_views) == len(selection_views) == count
        and all(type(value) is int and value == 20 for value in types)
        and all(type(value) is int and value == 0 for value in marks),
        Verdict.SELECTION,
        "wrong selected type/mark/count",
    )
    require(
        all(
            type(value) is int and value == 1
            for value in (*own_views, *selection_views)
        ),
        Verdict.IDENTITY,
        "selected owning/selection view is not exact target view",
    )


def roi_box(centre: Sequence[float], half_width: float) -> tuple[int, int, int, int]:
    require(
        len(centre) >= 2
        and all(type(x) in (int, float) and math.isfinite(x) for x in centre)
        and type(half_width) in (int, float)
        and math.isfinite(half_width)
        and half_width > 0,
        Verdict.VISUAL,
        "nonfinite/invalid projection or ROI width",
    )
    x, y = centre[:2]
    scale = DPI / 0.0254
    box = (
        math.floor((x - half_width) * scale),
        math.floor(PAGE_SIZE[1] - (y + half_width) * scale),
        math.ceil((x + half_width) * scale),
        math.ceil(PAGE_SIZE[1] - (y - half_width) * scale),
    )
    require(
        0 <= box[0] < box[2] <= PAGE_SIZE[0] and 0 <= box[1] < box[3] <= PAGE_SIZE[1],
        Verdict.VISUAL,
        "ROI outside page",
    )
    return box


def checked_tuple(value: Any, label: str, *, save: bool) -> tuple:
    require(
        isinstance(value, tuple) and len(value) == 3,
        Verdict.CONSTRUCTION,
        f"{label}: unsupported generated out tuple {value!r}",
    )
    result, errors, warnings = value
    require(
        type(errors) is int and type(warnings) is int and errors == warnings == 0,
        Verdict.CONSTRUCTION,
        f"{label}: native errors/warnings {value!r}",
    )
    if save:
        require(result is True, Verdict.CONSTRUCTION, f"{label}: save rejected")
    else:
        require(result is not None, Verdict.CONSTRUCTION, f"{label}: null model")
    return value


def sha256(path: Path) -> str:
    with path.open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def normalized(path: str | Path) -> str:
    return os.path.normcase(str(Path(path).resolve()))


def assembly_template_evidence(value: Any) -> dict[str, Any]:
    """Record independent admission facts, not an inferred missing-file cause."""
    predicates: dict[str, bool | None] = {
        "is_string": type(value) is str,
        "nonempty": bool(value) if type(value) is str else None,
        "fully_qualified": None,
        "exists": None,
        "is_file": None,
        "assembly_suffix": None,
    }
    evidence = {
        "value": (
            value
            if type(value) in (str, int, bool, type(None))
            or (type(value) is float and math.isfinite(value))
            else repr(value)
        ),
        "type": type(value).__name__,
        "repr": repr(value),
        "predicates": predicates,
    }
    if type(value) is str and value:
        try:
            path = Path(value)
            predicates["fully_qualified"] = path.is_absolute()
            predicates["assembly_suffix"] = path.suffix.casefold() == ".asmdot"
            predicates["exists"] = path.exists()
            predicates["is_file"] = path.is_file()
        except (OSError, ValueError) as error:
            evidence["path_error"] = error_record(error)
    return evidence


def error_record(error: BaseException) -> dict[str, Any]:
    record = {
        "type": type(error).__name__,
        "message": str(error),
        "traceback": "".join(traceback.format_exception(error)),
        "notes": list(getattr(error, "__notes__", ())),
    }
    for name in ("hresult", "strerror", "excepinfo", "argerror"):
        if hasattr(error, name):
            record[name] = getattr(error, name)
    return record


def fixture_instances(
    rows: Sequence[Mapping[str, Any]],
    paths: Mapping[Document, Path],
    *,
    root_assembly: bool,
) -> dict[str, NodeId]:
    expected = {
        NodeId.P1: (Document.P, -0.015),
        NodeId.P2: (Document.P, 0.0),
        NodeId.Q1: (Document.Q, 0.015),
    }
    if root_assembly:
        expected.update({NodeId.N: (Document.N, 0.0), NodeId.Q2: (Document.Q, 0.030)})
    require(len(rows) == len(expected), Verdict.CONSTRUCTION, "fixture component count")
    names = {}
    for row in rows:
        name = api_string(row["path"], "fixture full instance path")
        matches = [
            key
            for key, (source, x) in expected.items()
            if row["source"] == normalized(paths[source])
            and equal_transform(row["transform"], translation(x))
        ]
        require(
            len(matches) == 1
            and name not in names
            and matches[0] not in names.values()
            and row["configuration"] == "Default"
            and row["visible"] == 1
            and type(row["visible"]) is int,
            Verdict.CONSTRUCTION,
            "fixture source/pose/configuration/visibility mismatch",
        )
        names[name] = matches[0]
    if root_assembly:
        inverse = {key: name for name, key in names.items()}
        parent = inverse[NodeId.N] + "/"
        require(
            all(
                inverse[key].startswith(parent)
                for key in (NodeId.P1, NodeId.P2, NodeId.Q1)
            )
            and not inverse[NodeId.Q2].startswith(parent),
            Verdict.CONSTRUCTION,
            "persisted real nested-parent/full-path composition mismatch",
        )
    return names


class Receipt:
    """Bounded atomic evidence; the report never hashes itself."""

    def __init__(self, root: Path, clock: Callable[[], float] = time.monotonic):
        self.root, self.clock = root, clock
        self.started = clock()
        self.stage = Stage.CONSTRUCTION
        self.stage_started = self.started
        self.case = Case.CONSTRUCTION
        self.counts: Counter[str] = Counter()
        self.primary: BaseException | None = None
        self.data: dict[str, Any] = {
            "schema_version": 1,
            "run_id": root.name,
            "arm": "suspended_add_selection_list_objects",
            "approved_base": "8fc78122da64b4b8a79a1aba5d94e84b912d1efc",
            "probe_controls_status": Controls.RUNNING,
            "handoff_allowed": False,
            "normal_drawing_outcome": "not_observed_by_probe",
            "outer_session_teardown": "not_observed_by_probe",
            "held_model_scope": "probe_exit",
            "external_acceptance": "requires_retrieval_leaf_result_and_parent_visual_review",
            "stages": {stage: {"status": Verdict.NOT_EXECUTED} for stage in Stage},
            "cases": {
                case: {
                    "status": Verdict.NOT_EXECUTED,
                    "operations": [],
                    "checkpoints": [],
                }
                for case in Case
            },
            "snapshots": {},
            "observations": [],
            "artifacts": [],
            "ledger": [],
            "primary_error": None,
            "secondary_errors": [],
            "bounds": {
                "seconds": OVERALL_BUDGET_SECONDS,
                "cleanup_reserve_seconds": CLEANUP_BUDGET_SECONDS,
                "normal_seconds": NORMAL_BUDGET_SECONDS,
                "F": 192,
                "S": 16,
                "case_slots": 32,
                "walked_entries": 48,
                "owned_bytes": MAX_FILES_BYTES,
                "report_bytes": MAX_REPORT_BYTES,
                "decoded_image_bytes": MAX_IMAGE_BYTES,
                "full_image_buffers": 3,
            },
        }
        require(
            root.is_dir() and not root.is_symlink() and not root.is_junction(),
            Verdict.CONSTRUCTION,
            "report root is not an owned regular directory",
        )
        self.checkpoint()

    def deadline(self, *, cleanup: bool = False) -> None:
        now = self.clock()
        elapsed = now - self.started
        stage_elapsed = now - self.stage_started
        limit = OVERALL_BUDGET_SECONDS if cleanup else NORMAL_BUDGET_SECONDS
        global_allowed = elapsed <= limit
        cleanup_allowed = not cleanup or stage_elapsed <= CLEANUP_BUDGET_SECONDS
        if global_allowed and cleanup_allowed:
            return
        binding = ""
        if not global_allowed:
            binding = "cleanup_global" if cleanup else "normal_global"
        if not cleanup_allowed:
            binding += ("," if binding else "") + "cleanup_stage"
        cleanup_limit = (
            f"; cleanup_stage_limit={CLEANUP_BUDGET_SECONDS!r}s" if cleanup else ""
        )
        raise ProbeFailure(
            Verdict.DEADLINE,
            f"deadline before {self.stage}/{self.case}: binding={binding}; "
            f"global_elapsed={elapsed!r}s; global_limit={limit!r}s; "
            f"stage_elapsed={stage_elapsed!r}s{cleanup_limit}",
        )

    def path(self, name: str) -> Path:
        path = self.root / name
        require(
            path.parent == self.root
            and name not in ("", ".", "..")
            and not path.is_symlink()
            and not path.is_junction(),
            Verdict.CONSTRUCTION,
            "artifact leaves owned flat directory",
        )
        return path

    def limits(self) -> None:
        entries = []
        for path in self.root.iterdir():
            require(len(entries) < 44, Verdict.VISUAL, "owned walked-entry ceiling")
            entries.append(path)
        size = 0
        for path in entries:
            require(
                path.is_file() and not path.is_symlink() and not path.is_junction(),
                Verdict.PRESERVATION,
                f"nonregular owned evidence: {path}",
            )
            item_size = path.stat().st_size
            limit = (
                16 * 1024 * 1024
                if path.suffix.upper() in (".SLDASM", ".SLDDRW")
                else 4 * 1024 * 1024
            )
            if path.name == "emergency.json":
                limit = 32 * 1024
            require(
                item_size <= limit,
                Verdict.VISUAL,
                f"individual artifact limit: {path.name}",
            )
            size += item_size
        require(size <= MAX_FILES_BYTES, Verdict.VISUAL, "owned byte ceiling")
        self.data["owned_files"] = len(entries)
        self.data["owned_bytes"] = size

    def checkpoint(self) -> None:
        self.data["operation_counts"] = dict(self.counts)
        self.data["elapsed_seconds"] = self.clock() - self.started
        payload = json.dumps(
            self.data, sort_keys=True, separators=(",", ":"), allow_nan=False
        ).encode()
        require(
            len(payload) <= MAX_REPORT_BYTES,
            Verdict.PRESERVATION,
            "report exceeds 4 MiB",
        )
        self.limits()
        temporary = self.path("report.json.tmp")
        existing_temporary = temporary.stat().st_size if temporary.exists() else 0
        require(
            self.data["owned_bytes"] - existing_temporary + len(payload)
            <= MAX_FILES_BYTES
            and self.data["owned_files"] + (not temporary.exists()) + 4 <= 48,
            Verdict.PRESERVATION,
            "atomic report temporary exceeds owned ceiling",
        )
        with temporary.open("wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        temporary.replace(self.path("report.json"))
        self.limits()

    def observe(self, kind: SnapshotKind, label: str, value: Any) -> None:
        require(
            isinstance(kind, SnapshotKind),
            Verdict.PRESERVATION,
            "invalid checkpoint kind",
        )
        self.counts[kind] += 1
        require(
            self.counts[kind] <= (192 if kind is SnapshotKind.FULL else 16),
            Verdict.PRESERVATION,
            f"{kind} checkpoint ceiling",
        )
        encoded = json.dumps(
            value, sort_keys=True, separators=(",", ":"), allow_nan=False
        )
        key = hashlib.sha256(encoded.encode()).hexdigest()
        self.data["snapshots"].setdefault(key, value)
        event = {
            "id": f"{kind}{self.counts[kind]:03}",
            "label": label,
            "content": key,
            "elapsed": self.clock() - self.started,
        }
        self.data["observations"].append(event)
        self.data["cases"][self.case]["checkpoints"].append(event["id"])

    def artifact(self, path: Path, kind: str) -> None:
        require(
            path.parent == self.root and path.is_file() and path.stat().st_size > 0,
            Verdict.PRESERVATION,
            f"missing owned artifact {path}",
        )
        self.limits()
        rows = self.data["artifacts"]
        require(
            path.name != "report.json"
            and all(row["relative_path"] != path.name for row in rows),
            Verdict.PRESERVATION,
            "artifact overwrite/self-hash refused",
        )
        rows.append(
            {
                "relative_path": path.name,
                "kind": kind,
                "size": path.stat().st_size,
                "sha256": sha256(path),
            }
        )

    def failure(self, error: BaseException, *, secondary: bool = False) -> None:
        item = {"stage": self.stage, "case": self.case, **error_record(error)}
        if secondary:
            self.data["secondary_errors"].append(item)
        elif self.primary is None:
            self.primary = error
            self.data["primary_error"] = item
        elif error is self.primary:
            self.data["primary_error"].update(error_record(error))
        else:
            self.data["secondary_errors"].append(item)
        try:
            self.checkpoint()
        except BaseException as report_error:
            error.add_note(f"report checkpoint also failed: {report_error!r}")
            self.data["secondary_errors"].append(error_record(report_error))
            try:
                payload = json.dumps(
                    {
                        "run_id": self.root.name,
                        "primary": (
                            {
                                **self.data["primary_error"],
                                **error_record(self.primary),
                            }
                            if self.primary is not None
                            else item
                        ),
                        "reported_error": item,
                        "report_error": repr(report_error),
                    },
                    default=str,
                ).encode()
                if len(payload) <= 32 * 1024:
                    self.path("emergency.json").write_bytes(payload)
            except BaseException as emergency_error:
                error.add_note(f"emergency receipt also failed: {emergency_error!r}")

    def terminal(self) -> None:
        if self.primary is not None:
            self.data["primary_error"].update(error_record(self.primary))
        self.checkpoint()
        path = self.path("report.json")
        print(
            "BULK_VISIBILITY_TERMINAL "
            + json.dumps(
                {
                    "run_id": self.root.name,
                    "probe_controls": self.data["probe_controls_status"],
                    "handoff_allowed": self.data["handoff_allowed"],
                    "report": str(path),
                    "size": path.stat().st_size,
                    "sha256": sha256(path),
                    "primary_error": self.data["primary_error"],
                },
                default=str,
            ),
            flush=True,
        )


@dataclass
class OwnedDocument:
    native: Any
    title: str | None
    path: Path | None
    kind: int | None
    generation: int
    state: AcquisitionState


@dataclass
class DrawingNode:
    state: NodeState
    drawing_component: Any
    component: Any


class NativeProbe:
    """One concrete experiment, with no selector strategy or recovery route."""

    def __init__(self, adapter: Any, root: Path, receipt: Receipt):
        # These imports belong exclusively to the farm-native entry point.
        import pythoncom
        from win32com.client import VARIANT
        from solidworks_mcp.adapters import sw_type_info
        import _telemetry

        self.adapter, self.root, self.receipt = adapter, root, receipt
        self.pythoncom, self.variant = pythoncom, VARIANT
        self.types, self.telemetry = sw_type_info, _telemetry
        self.app = self.bind(adapter.swApp, "ISldWorks")
        self.documents: dict[Document, OwnedDocument] = {}
        # Ownership survives failed admission. Only documents below are usable
        # by model()/activate(); acquisitions also retain rejected native returns.
        self.acquisitions: dict[Document, OwnedDocument] = {}
        self.generations: Counter[Document] = Counter()
        self.paths = {
            Document.P: root / "cad/out/sldprt/ch-rod-pivot-pin.SLDPRT",
            Document.Q: root / "cad/out/sldprt/ch-pivot-shaft.SLDPRT",
            Document.N: receipt.path(f"{receipt.root.name}-N.SLDASM"),
            Document.R: receipt.path(f"{receipt.root.name}-R.SLDASM"),
            Document.DRAWING: receipt.path(f"{receipt.root.name}-drawing.SLDDRW"),
        }
        self.tokens = {
            Document.P: root / "cad/out/sldprt/.ch-rod-pivot-pin.execution",
            Document.Q: root / "cad/out/sldprt/.ch-pivot-shaft.execution",
        }
        self.disk_baselines: dict[str, dict[str, Any]] = {}
        self.source_baselines: dict[Document, Any] = {}
        self.component_names: dict[str, NodeId] = {}
        self.view_baselines: dict[ViewId, Any] = {}
        self.view_handles: dict[ViewId, Any] = {}
        self.node_handles: dict[tuple[ViewId, NodeId], Any] = {}
        self.expected = {view: {key: True for key in NodeId} for view in ViewId}
        self.rois: dict[ViewId, dict[NodeId, tuple[int, int, int, int]]] = {}
        self.export_pages: dict[Export, dict[ViewId, Path]] = {}
        self.saved_drawing_hash: str | None = None
        self.harness_flags: dict[str, bool] | None = None
        self.mode = RunMode.EXPERIMENT
        self.receipt.data["binding"] = {
            "type_info_path": str(Path(self.types.__file__).resolve()),
            "type_info_sha256": sha256(Path(self.types.__file__)),
            "application_wrapper": f"{type(self.app).__module__}.{type(self.app).__qualname__}",
            "generated_route_not_native_type_authentication": True,
        }

    def bind(self, raw: Any, interface: str) -> Any:
        require(raw is not None, Verdict.CONSTRUCTION, f"null {interface}")
        try:
            wrapped = self.types.early_bound(raw, interface)
        except Exception as error:
            error.probe_verdict = Verdict.IDENTITY
            raise
        require(
            self.types.is_early_bound(wrapped, interface),
            Verdict.IDENTITY,
            f"generated invocation route unavailable: {interface}",
        )
        return wrapped

    def same(self, left: Any, right: Any) -> int:
        require(
            left is not None and right is not None,
            Verdict.IDENTITY,
            "null identity operand",
        )
        value = api_int(self.app.IsSame(left, right), "IsSame", Verdict.IDENTITY)
        require(
            value in (0, 1),
            Verdict.IDENTITY,
            f"unsupported native identity result {value}",
        )
        return value

    def identical(self, left: Any, right: Any, label: str) -> int:
        result = self.same(left, right)
        require(result == 1, Verdict.IDENTITY, f"{label}: different native object")
        return result

    def doubles(self, values: Sequence[float]) -> Any:
        return self.variant(
            self.pythoncom.VT_ARRAY | self.pythoncom.VT_R8, tuple(values)
        )

    def dispatches(self, values: Sequence[Any]) -> Any:
        return self.variant(
            self.pythoncom.VT_ARRAY | self.pythoncom.VT_DISPATCH, tuple(values)
        )

    def tick(self) -> None:
        # Mandatory finally restoration may use the reserved cleanup interval.
        if self.mode is not RunMode.RESTORING:
            self.receipt.deadline(cleanup=self.mode is RunMode.CLEANUP)

    @contextmanager
    def timed(self, bucket: str) -> Iterator[None]:
        self.tick()
        started = time.monotonic()
        operation = {"bucket": bucket, "status": Verdict.RUNNING}
        self.receipt.data["cases"][self.receipt.case]["operations"].append(operation)
        try:
            with self.telemetry.span(
                f"probe.bulk_visibility.{bucket}",
                case=self.receipt.case,
                stage=self.receipt.stage,
            ):
                yield
            operation["status"] = Verdict.PASSED
        except BaseException as error:
            if not isinstance(
                error, (ProbeFailure, InjectedFailure, KeyboardInterrupt, SystemExit)
            ):
                if not hasattr(error, "probe_verdict"):
                    error.probe_verdict = (
                        Verdict.VISUAL
                        if bucket in ("render", "export")
                        else Verdict.CONSTRUCTION
                    )
            operation["status"] = failure_verdict(error)
            operation["error"] = error_record(error)
            raise
        finally:
            operation["seconds"] = time.monotonic() - started

    def model(self, label: Document) -> Any:
        require(
            label in self.documents
            and self.documents[label].state is AcquisitionState.ADMITTED,
            Verdict.CONSTRUCTION,
            f"document not admitted for use: {label}",
        )
        return self.documents[label].native

    def draw(self) -> Any:
        return self.bind(self.model(Document.DRAWING), "IDrawingDoc")

    @contextmanager
    def acquiring(self, label: Document) -> Iterator[tuple[Any, ...]]:
        require(
            label not in self.acquisitions,
            Verdict.CONSTRUCTION,
            f"duplicate acquisition: {label}",
        )
        before = tuple(self.inventory().values())
        event = {
            "event": "acquire_started",
            "document": label,
            "preexisting_owned": sorted(self.documents),
        }
        self.receipt.data["ledger"].append(event)
        try:
            yield before
        except BaseException as error:
            # If no result was captured, there is no positively owned identity
            # to close. Preserve that uncertainty, never adopt an inventory delta.
            if label not in self.acquisitions:
                self.receipt.data.setdefault("unresolved_acquisitions", []).append(
                    {
                        "document": label,
                        "reason": "native acquisition did not yield a recorded model",
                        "error": error_record(error),
                    }
                )
            event["error"] = error_record(error)
            raise

    def acquired(self, label: Document, raw: Any, before: tuple[Any, ...]) -> Any:
        self.generations[label] += 1
        owned = OwnedDocument(
            raw, None, None, None, self.generations[label], AcquisitionState.UNRESOLVED
        )
        self.acquisitions[label] = owned
        event = {
            "event": "acquired",
            "document": label,
            "generation": owned.generation,
            "state": owned.state,
            "returned_non_null": raw is not None,
        }
        self.receipt.data["ledger"].append(event)
        try:
            self.identical(raw, raw, "acquired model positive identity")
            require(
                all(self.same(raw, prior) == 0 for prior in before),
                Verdict.IDENTITY,
                "acquisition returned a preexisting model",
            )
            current = array(
                self.app.GetDocuments(), "post-acquisition inventory", empty=True
            )
            require(
                sum(self.same(raw, candidate) for candidate in current) == 1,
                Verdict.IDENTITY,
                "acquired model not uniquely present in fresh inventory",
            )
            # Positive new ownership precedes binding/title/type/path admission.
            owned.state = AcquisitionState.PENDING
            model = self.bind(raw, "IModelDoc2")
            owned.native = model
            owned.title = api_string(model.GetTitle(), "acquired native title")
            event["title"] = owned.title
            return model
        except BaseException as error:
            event["error"] = error_record(error)
            raise
        finally:
            event["state"] = owned.state

    def claim(self, label: Document, kind: int, path: Path | None) -> Any:
        owned = self.acquisitions[label]
        require(
            owned.state is AcquisitionState.PENDING and label not in self.documents,
            Verdict.CONSTRUCTION,
            "acquisition has no pending positive ownership",
        )
        model, title = owned.native, owned.title
        require(
            type(title) is str and bool(title) and model.GetTitle() == title,
            Verdict.CONSTRUCTION,
            "empty/changed native title",
        )
        require(
            all(
                other is owned
                or other.title is None
                or other.title.casefold() != title.casefold()
                for other in self.acquisitions.values()
            ),
            Verdict.CONSTRUCTION,
            "duplicate/ambiguous owned document",
        )
        require(
            api_int(model.GetType(), "document type") == kind,
            Verdict.CONSTRUCTION,
            f"{label}: wrong document kind",
        )
        actual_path = model.GetPathName()
        require(
            type(actual_path) is str
            and (
                normalized(actual_path) == normalized(path)
                if path is not None
                else actual_path == ""
            ),
            Verdict.CONSTRUCTION,
            f"{label}: wrong canonical/authoring path {actual_path!r}",
        )
        source = None
        if label in (Document.P, Document.Q, Document.N, Document.R):
            source = self.source_state(label, model)
            prior = self.source_baselines.get(label)
            require(
                prior is None or source == prior,
                Verdict.PRESERVATION,
                f"source differs from preserved admission baseline: {label}",
            )
        elif kind == 2:
            require(
                array(model.GetConfigurationNames(), "authoring configurations")
                == ("Default",),
                Verdict.CONSTRUCTION,
                "assembly template configuration contract",
            )
        elif path is None:
            drawing = self.bind(model, "IDrawingDoc")
            require(
                len(array(drawing.GetSheetNames(), "initial sheets")) == 1,
                Verdict.CONSTRUCTION,
                "drawing template must contain one sheet",
            )
            initial = array(drawing.GetViews(), "initial view arrays")
            require(
                len(initial) == 1
                and len(array(initial[0], "initial sheet views")) == 1,
                Verdict.CONSTRUCTION,
                "drawing template unexpectedly contains real views",
            )
        else:
            require(
                model.IsOpenedReadOnly() is False and model.GetSaveFlag() is False,
                Verdict.CONSTRUCTION,
                "reopened fixture drawing not clean/writable",
            )
        self.ownership_inventory()
        # No native mutator can obtain this object until every admission check
        # above succeeds, including source read-only/configuration validation.
        owned.path, owned.kind, owned.state = path, kind, AcquisitionState.ADMITTED
        self.documents[label] = owned
        if source is not None:
            self.source_baselines.setdefault(label, source)
        self.receipt.data["ledger"].append(
            {
                "event": "claim",
                "document": label,
                "title": title,
                "path": str(path) if path else None,
                "kind": kind,
                "generation": owned.generation,
                "state": owned.state,
            }
        )
        return model

    @staticmethod
    def refreshable_drawing(label: Document, owned: OwnedDocument) -> bool:
        return (
            label is Document.DRAWING
            and owned.state is AcquisitionState.ADMITTED
            and owned.native is not None
            and type(owned.kind) is int
            and owned.kind == 3
        )

    def staged_title_refresh(
        self,
        label: Document,
        owned: OwnedDocument,
        title: str,
        kind: int,
        path: str,
        verdict: Verdict,
        context: str,
        *,
        unknown_pending_title: bool = False,
    ) -> dict[str, Any] | None:
        """Validate metadata after unique native matching, without changing it."""
        try:
            if owned.state is AcquisitionState.ADMITTED:
                require(
                    kind == owned.kind
                    and (
                        normalized(path) == normalized(owned.path)
                        if owned.path is not None
                        else path == ""
                    ),
                    verdict,
                    f"owned {context} path/type changed: {label}",
                )
            if title == owned.title or (
                unknown_pending_title
                and owned.state is AcquisitionState.PENDING
                and owned.title is None
            ):
                return None
            require(
                self.refreshable_drawing(label, owned) and kind == 3,
                verdict,
                f"owned {context} title changed: {label}",
            )
        except ProbeFailure as error:
            error.add_note(
                f"owned metadata: context={context!r}; document={label!r}; "
                f"generation={owned.generation!r}; state={owned.state!r}; "
                f"native_is_same=1; expected_title={owned.title!r}; "
                f"fresh_title={title!r}; "
                f"expected_path={(str(owned.path) if owned.path is not None else None)!r}; "
                f"fresh_path={path!r}; expected_kind={owned.kind!r}; fresh_kind={kind!r}"
            )
            raise
        return {
            "event": "title_refresh",
            "context": context,
            "document": label,
            "generation": owned.generation,
            "cached_title": owned.title,
            "fresh_title": title,
            "native_is_same": 1,
            "kind": kind,
            "path": path,
        }

    def commit_title_refreshes(self, staged: list[dict[str, Any]]) -> None:
        # Both callers finish the complete live/acquired bijection and collision
        # checks first. No native identity, admission metadata or state changes.
        for event in staged:
            self.acquisitions[event["document"]].title = event["fresh_title"]
            self.receipt.data["ledger"].append(event)

    def ownership_inventory(self, *, context: str = "inventory") -> dict[Document, Any]:
        found: dict[Document, Any] = {}
        titles: set[str] = set()
        staged: list[dict[str, Any]] = []
        for raw in array(self.app.GetDocuments(), "GetDocuments", empty=True):
            model = self.bind(raw, "IModelDoc2")
            matches = [
                label
                for label, owned in self.acquisitions.items()
                if owned.state in (AcquisitionState.PENDING, AcquisitionState.ADMITTED)
                and owned.native is not None
                and self.same(model, owned.native) == 1
            ]
            require(
                len(matches) == 1,
                Verdict.PRESERVATION,
                "unowned/ambiguous open document; no foreign close permitted",
            )
            label = matches[0]
            require(
                label not in found, Verdict.PRESERVATION, "duplicate document inventory"
            )
            owned = self.acquisitions[label]
            title = api_string(model.GetTitle(), "fresh owned inventory title")
            path = api_string(
                model.GetPathName(), "fresh owned inventory path", empty=True
            )
            kind = api_int(model.GetType(), "inventory type")
            event = self.staged_title_refresh(
                label, owned, title, kind, path, Verdict.PRESERVATION, context
            )
            if event is not None:
                staged.append(event)
            if title.casefold() in titles:
                error = ProbeFailure(
                    Verdict.PRESERVATION,
                    "ambiguous inventory title; no foreign close permitted",
                )
                error.add_note(
                    f"owned title collision: context={context!r}; document={label!r}; "
                    f"generation={owned.generation!r}; native_is_same=1; "
                    f"fresh_title={title!r}; fresh_path={path!r}; fresh_kind={kind!r}; "
                    f"collision_key={title.casefold()!r}; "
                    f"known_casefold_titles={sorted(titles)!r}"
                )
                raise error
            titles.add(title.casefold())
            found[label] = model
        require(
            set(found) == set(self.acquisitions),
            Verdict.PRESERVATION,
            "owned/unresolved acquisition unexpectedly absent",
        )
        self.commit_title_refreshes(staged)
        return found

    def inventory(self, *, context: str = "inventory") -> dict[Document, Any]:
        # Refuse pending/unresolved admission before a refresh can commit.
        require(
            set(self.acquisitions) == set(self.documents)
            and not self.receipt.data.get("unresolved_acquisitions"),
            Verdict.PRESERVATION,
            "pending/unresolved document not admitted",
        )
        return self.ownership_inventory(context=context)

    def activate(self, label: Document) -> Any:
        self.tick()
        self.model(label)  # Reject pending/failed-discard objects before activation.
        owned = self.documents[label]
        event: dict[str, Any] = {
            "event": "activation",
            "document": label,
            "generation": owned.generation,
            "cached_title": owned.title,
            "state": ActivationState.PREPARING,
            "pre_active": {"state": ActiveObservation.NOT_OBSERVED},
            "post_active": {"state": ActiveObservation.NOT_OBSERVED},
        }
        self.receipt.data["ledger"].append(event)
        try:
            require(
                owned.native is not None,
                Verdict.CONSTRUCTION,
                f"document handle invalidated before activation: {label}",
            )
            if self.refreshable_drawing(label, owned):
                self.inventory(context="activation")
            event["validated_title"] = owned.title
            event["pre_active"]["state"] = ActiveObservation.OBSERVING
            active = self.app.ActiveDoc
            if active is None:
                event["pre_active"] = {"state": ActiveObservation.NULL}
            else:
                matches = [
                    key
                    for key, candidate in self.documents.items()
                    if candidate.state is AcquisitionState.ADMITTED
                    and candidate.native is not None
                    and self.same(active, candidate.native) == 1
                ]
                event["pre_active"] = {
                    "state": (
                        ActiveObservation.OWNED
                        if len(matches) == 1
                        else ActiveObservation.FOREIGN
                    ),
                    "documents": matches,
                    "native_is_same": [1 for _ in matches],
                }
            event["arguments"] = [owned.title, False, 2, 0]
            event["state"] = ActivationState.CALLING
            result = self.app.ActivateDoc3(owned.title, False, 2, 0)
            event["state"] = ActivationState.VALIDATING
            event["result_type"] = type(result).__name__
            event["result_repr"] = repr(result)
            if isinstance(result, tuple):
                event["result_length"] = len(result)
                event["component_types"] = [type(item).__name__ for item in result]
                if result:
                    event["returned_model_null"] = result[0] is None
                if len(result) == 2:
                    event["status_type"] = type(result[1]).__name__
                    event["status_repr"] = repr(result[1])
                    if type(result[1]) in (str, int, bool, type(None)) or (
                        type(result[1]) is float and math.isfinite(result[1])
                    ):
                        event["status"] = result[1]
            require(
                isinstance(result, tuple)
                and len(result) == 2
                and type(result[1]) is int
                and result[1] == 0,
                Verdict.CONSTRUCTION,
                f"ActivateDoc3 failed: {result!r}",
            )
            event["returned_native_is_same"] = self.same(result[0], owned.native)
            require(
                event["returned_native_is_same"] == 1,
                Verdict.IDENTITY,
                "activated returned model: different native object",
            )
            event["post_active"]["state"] = ActiveObservation.OBSERVING
            active = self.app.ActiveDoc
            event["post_active"] = {
                "state": (
                    ActiveObservation.NULL
                    if active is None
                    else ActiveObservation.NON_NULL
                )
            }
            event["post_active"]["native_is_same"] = self.same(active, owned.native)
            require(
                event["post_active"]["native_is_same"] == 1,
                Verdict.IDENTITY,
                "fresh active document: different native object",
            )
            self.adapter.currentModel = owned.native
            event["state"] = ActivationState.PASSED
            return owned.native
        except BaseException as error:
            event["failed_at"] = event["state"]
            event["state"] = ActivationState.FAILED
            for key in ("pre_active", "post_active"):
                if event[key]["state"] is ActiveObservation.OBSERVING:
                    event[key] = {
                        "state": ActiveObservation.ERROR,
                        "error": error_record(error),
                    }
            event["error"] = error_record(error)
            raise

    def freeze_disk(self, label: Document) -> None:
        path = self.paths[label]
        require(
            path.is_file() and not path.is_symlink() and not path.is_junction(),
            Verdict.CONSTRUCTION,
            f"missing/nonregular declared input {path}",
        )
        self.disk_baselines[str(path)] = {
            "size": path.stat().st_size,
            "sha256": sha256(path),
        }
        if label in self.tokens:
            token = self.tokens[label]
            content = token.read_text(encoding="utf-8")
            require(
                len(content) <= 4096
                and content.strip() == self.disk_baselines[str(path)]["sha256"],
                Verdict.CONSTRUCTION,
                f"execution token does not identify input bytes: {token}",
            )
            self.disk_baselines[str(token)] = {
                "size": token.stat().st_size,
                "sha256": sha256(token),
                "contents": content,
            }

    def disk_snapshot(self) -> dict[str, Any]:
        observed = {}
        for name, baseline in self.disk_baselines.items():
            path = Path(name)
            require(
                path.is_file() and not path.is_symlink() and not path.is_junction(),
                Verdict.PRESERVATION,
                f"source disappeared/replaced: {path}",
            )
            row = {"size": path.stat().st_size, "sha256": sha256(path)}
            if "contents" in baseline:
                row["contents"] = path.read_text(encoding="utf-8")
            require(
                row == baseline,
                Verdict.PRESERVATION,
                f"source bytes/token changed: {path}",
            )
            observed[name] = row
        if self.saved_drawing_hash is not None:
            require(
                sha256(self.paths[Document.DRAWING]) == self.saved_drawing_hash,
                Verdict.PRESERVATION,
                "persisted drawing overwritten",
            )
        return observed

    def component_state(self, raw: Any) -> dict[str, Any]:
        component = self.bind(raw, "IComponent2")
        model = self.bind(component.GetModelDoc2(), "IModelDoc2")
        path = api_string(component.GetPathName(), "component source path")
        labels = [
            label
            for label in (Document.P, Document.Q, Document.N)
            if normalized(path) == normalized(self.paths[label])
        ]
        require(
            len(labels) == 1 and labels[0] in self.documents,
            Verdict.PRESERVATION,
            f"unadmitted component reference {path!r}",
        )
        self.identical(model, self.model(labels[0]), "component canonical model")
        suppression = api_int(component.GetSuppression(), "component suppression")
        require(
            suppression == 2,
            Verdict.CONSTRUCTION,
            f"component not fully resolved (suppression={suppression})",
        )
        return {
            "path": api_string(component.Name2, "full component instance path"),
            "source": normalized(path),
            "configuration": api_string(
                component.ReferencedConfiguration, "referenced configuration"
            ),
            "display_state": api_string(
                component.ReferencedDisplayState2,
                "referenced display state",
                empty=True,
            ),
            "suppression": suppression,
            "visible": api_int(component.Visible, "assembly visibility"),
            "transform": matrix(
                self.bind(component.Transform2, "IMathTransform").ArrayData,
                "component Transform2",
            ),
        }

    def assembly_components(self, raw: Any) -> list[dict[str, Any]]:
        assembly = self.bind(raw, "IAssemblyDoc")
        rows = [
            self.component_state(component)
            for component in array(
                assembly.GetComponents(False), "assembly components", empty=True
            )
        ]
        require(
            len({row["path"] for row in rows}) == len(rows),
            Verdict.PRESERVATION,
            "duplicate assembly component paths",
        )
        return sorted(rows, key=lambda row: row["path"])

    def source_state(self, label: Document, model: Any) -> dict[str, Any]:
        readonly = api_bool(model.IsOpenedReadOnly(), "source read-only")
        dirty = api_bool(model.GetSaveFlag(), "source dirty")
        require(
            readonly and not dirty,
            Verdict.PRESERVATION,
            f"source writable/dirty: {label}; readonly={readonly!r}, dirty={dirty!r}",
        )
        config_names = array(model.GetConfigurationNames(), "configuration names")
        require(
            0 < len(config_names) <= 4
            and len(set(config_names)) == len(config_names)
            and all(type(name) is str and name for name in config_names),
            Verdict.CONSTRUCTION,
            "configuration inventory bound/type",
        )
        if label in (Document.N, Document.R):
            require(
                config_names == ("Default",),
                Verdict.CONSTRUCTION,
                "fixture assembly must contain only Default",
            )
        active = self.bind(model.GetActiveConfiguration(), "IConfiguration").Name
        require(
            active == "Default",
            Verdict.PRESERVATION,
            f"active source configuration {active!r}",
        )
        configurations = {}
        for name in config_names:
            config = self.bind(model.GetConfigurationByName(name), "IConfiguration")
            require(
                config.Name == name,
                Verdict.CONSTRUCTION,
                "configuration lookup fallback",
            )
            states = array(config.GetDisplayStates(), "display-state names")
            limit = 2 if label in (Document.N, Document.R) else 4
            require(
                0 < len(states) <= limit
                and len(set(states)) == len(states)
                and all(type(state) is str and state for state in states)
                and api_int(config.GetDisplayStatesCount(), "display-state count")
                == len(states),
                Verdict.CONSTRUCTION,
                "display-state inventory bound/type",
            )
            entry: dict[str, Any] = {"display_states_active_first": states}
            if label in (Document.N, Document.R):
                visibility = {}
                for state in states:
                    result = config.GetDisplayStateComponentVisibility(
                        state, False, False
                    )
                    require(
                        isinstance(result, tuple) and len(result) == 2,
                        Verdict.CONSTRUCTION,
                        "unsupported display-state out tuple",
                    )
                    values = array(result[0], "display-state visibilities")
                    components = array(result[1], "display-state components")
                    require(
                        len(values) == len(components) > 0
                        and all(
                            type(value) is int and value in (0, 1) for value in values
                        ),
                        Verdict.CONSTRUCTION,
                        "display-state component pairing/value",
                    )
                    pairs = [
                        {"component": self.component_state(component), "shown": value}
                        for value, component in zip(values, components, strict=True)
                    ]
                    require(
                        len({row["component"]["path"] for row in pairs}) == len(pairs),
                        Verdict.PRESERVATION,
                        "duplicate display-state component",
                    )
                    visibility[state] = sorted(
                        pairs, key=lambda row: row["component"]["path"]
                    )
                entry["component_display_inventory"] = visibility
            else:
                entry["component_display_inventory"] = {
                    "not_applicable": "part_has_no_assembly_component_inventory"
                }
            configurations[name] = entry
        return {
            "path": normalized(model.GetPathName()),
            "type": api_int(model.GetType(), "source type"),
            "read_only": True,
            "dirty": False,
            "active_configuration": active,
            "configuration_names": config_names,
            "configurations": configurations,
            "components": self.assembly_components(model)
            if label in (Document.N, Document.R)
            else [],
        }

    def sources(self) -> dict[str, Any]:
        self.inventory()
        result = {}
        for label in (Document.P, Document.Q, Document.N, Document.R):
            if label not in self.documents:
                result[label] = {"not_loaded": True}
                continue
            model = self.bind(
                self.app.GetOpenDocumentByName(str(self.paths[label])), "IModelDoc2"
            )
            identity = self.identical(model, self.model(label), f"fresh source {label}")
            observed = self.source_state(label, model)
            prior = self.source_baselines.get(label)
            if prior is not None:
                require(
                    observed == prior,
                    Verdict.PRESERVATION,
                    f"source native/configuration/display/pose changed: {label}; observed={observed!r}",
                )
            result[label] = {
                "generation": self.generations[label],
                "fresh_native_is_same": identity,
                "state": observed,
            }
        active = self.app.ActiveDoc
        active_label = None
        if active is not None:
            matches = [
                label
                for label, owned in self.documents.items()
                if self.same(active, owned.native) == 1
            ]
            require(
                len(matches) == 1,
                Verdict.IDENTITY,
                "source snapshot active document not owned",
            )
            active_label = matches[0]
        return {
            "native": result,
            "disk": self.disk_snapshot(),
            "active_owned_document": active_label,
        }

    def source_checkpoint(self, label: str) -> None:
        with self.timed("readback"):
            self.receipt.observe(SnapshotKind.SOURCE, label, self.sources())
        self.receipt.checkpoint()

    def open_source(self, label: Document) -> None:
        self.tick()
        path = self.paths[label]
        require(
            self.app.GetOpenDocumentByName(str(path)) is None,
            Verdict.CONSTRUCTION,
            f"source already loaded before explicit open: {label}",
        )
        kind = 1 if label in (Document.P, Document.Q) else 2
        with self.acquiring(label) as before:
            result = self.app.OpenDoc6(
                str(path), kind, 3 if kind == 1 else 67, "Default", 0, 0
            )
            raw = result[0] if isinstance(result, tuple) and result else None
            self.acquired(label, raw, before)
            checked_tuple(result, f"open {label}", save=False)
            self.claim(label, kind, path)

    def rebuild(
        self, *, setup: bool = False, label: Document = Document.DRAWING
    ) -> None:
        bucket = "harness_setup.rebuild" if setup else "rebuild"
        with self.timed(bucket):
            self.activate(label)
            require(
                self.model(label).EditRebuild3() is True,
                Verdict.CONSTRUCTION,
                f"checked {bucket} rejected for {label}",
            )
            self.receipt.counts["harness_setup_rebuild" if setup else "rebuild"] += 1

    def save_native(self, label: Document, target: Document, options: int) -> None:
        path = self.paths[target]
        require(
            not path.exists(),
            Verdict.CONSTRUCTION,
            f"owned native overwrite refused: {path}",
        )
        self.tick()
        self.activate(label)
        print(f"BULK_VISIBILITY_SAVE {self.receipt.case} {path.name}", flush=True)
        with self.timed("save"):
            extension = self.bind(self.model(label).Extension, "IModelDocExtension")
            result = extension.SaveAs3(str(path), 0, options, None, None, 0, 0)
            checked_tuple(result, f"native copy {target}", save=True)
            self.receipt.counts["native_copy_save"] += 1
        self.receipt.artifact(path, "native_fixture")
        self.freeze_disk(target)

    def discard_inventory(self) -> dict[Document, dict[str, Any]]:
        """Freeze ownership while every handle is live; return no native refs."""
        require(
            all(
                owned.state in (AcquisitionState.PENDING, AcquisitionState.ADMITTED)
                and owned.native is not None
                for owned in self.acquisitions.values()
            ),
            Verdict.RESTORATION,
            "discard held: unresolved acquisition or prior close not reconciled",
        )
        current = array(self.app.GetDocuments(), "pre-discard inventory", empty=True)
        frozen: dict[Document, dict[str, Any]] = {}
        staged: list[dict[str, Any]] = []
        for raw in current:
            owners = [
                key
                for key, owned in self.acquisitions.items()
                if self.same(raw, owned.native) == 1
            ]
            require(
                len(owners) == 1,
                Verdict.RESTORATION,
                "discard held: foreign/unresolved live identity; CloseDoc can close hidden documents",
            )
            key = owners[0]
            require(
                key not in frozen,
                Verdict.RESTORATION,
                "duplicate owned identity before discard",
            )
            owned = self.acquisitions[key]
            model = self.bind(raw, "IModelDoc2")
            title = api_string(model.GetTitle(), "fresh owned discard title")
            path = api_string(
                model.GetPathName(), "fresh owned discard path", empty=True
            )
            kind = api_int(model.GetType(), "fresh owned discard type")
            event = self.staged_title_refresh(
                key,
                owned,
                title,
                kind,
                path,
                Verdict.RESTORATION,
                "discard",
                unknown_pending_title=True,
            )
            if event is not None:
                staged.append(event)
            if any(
                row["title"].casefold() == title.casefold() for row in frozen.values()
            ):
                collisions = {
                    label: row
                    for label, row in frozen.items()
                    if row["title"].casefold() == title.casefold()
                }
                error = ProbeFailure(
                    Verdict.RESTORATION,
                    "ambiguous discard title; no foreign close permitted",
                )
                error.add_note(
                    f"owned title collision: context='discard'; document={key!r}; "
                    f"generation={owned.generation!r}; native_is_same=1; "
                    f"fresh_title={title!r}; fresh_path={path!r}; fresh_kind={kind!r}; "
                    f"collision_key={title.casefold()!r}; conflicting_frozen={collisions!r}"
                )
                raise error
            frozen[key] = {
                "title": title,
                "path": path,
                "kind": kind,
                "generation": owned.generation,
                "state": owned.state,
            }
        require(
            set(frozen) == set(self.acquisitions),
            Verdict.RESTORATION,
            "owned/unresolved acquisition unexpectedly absent before discard",
        )
        self.commit_title_refreshes(staged)
        return frozen

    def reconcile_discard(
        self,
        label: Document,
        frozen: Mapping[Document, Mapping[str, Any]],
        owners: Mapping[Document, Any],
    ) -> None:
        """Require surviving candidates to retain their pre-close native owner."""
        survivors: dict[Document, Any] = {}
        for raw in array(self.app.GetDocuments(), "post-close inventory", empty=True):
            model = self.bind(raw, "IModelDoc2")
            title = api_string(model.GetTitle(), "post-close title")
            path = api_string(model.GetPathName(), "post-close path", empty=True)
            kind = api_int(model.GetType(), "post-close type")
            matches = [
                key
                for key, row in frozen.items()
                if title == row["title"]
                and kind == row["kind"]
                and (
                    normalized(path) == normalized(row["path"])
                    if path and row["path"]
                    else path == row["path"]
                )
            ]
            require(
                len(matches) == 1,
                Verdict.RESTORATION,
                "unexpected/ambiguous post-close survivor; no adoption permitted",
            )
            key = matches[0]
            require(
                key is not label,
                Verdict.RESTORATION,
                f"close retained owned target: {label}",
            )
            require(
                key not in survivors,
                Verdict.RESTORATION,
                "duplicate post-close survivor",
            )
            require(
                bool(path) and Path(path).is_absolute(),
                Verdict.RESTORATION,
                "pathless post-close survivor cannot be safely reacquired",
            )
            # Metadata only locates a candidate; two fresh aliases of a replaced
            # document do not prove continuity with the acquired native owner.
            lookup = self.app.GetOpenDocumentByName(path)
            require(
                lookup is not None and self.same(model, lookup) == 1,
                Verdict.RESTORATION,
                "post-close survivor lacks fresh canonical identity",
            )
            require(
                self.same(model, owners[key]) == 1,
                Verdict.RESTORATION,
                "post-close survivor changed pre-close owner identity",
            )
            survivors[key] = model
        for key, row in frozen.items():
            if key not in survivors and row["path"]:
                require(
                    self.app.GetOpenDocumentByName(row["path"]) is None,
                    Verdict.RESTORATION,
                    f"closed pathname still loaded: {key}",
                )
        active = self.app.ActiveDoc
        require(
            active is None
            or sum(self.same(active, model) for model in survivors.values()) == 1,
            Verdict.RESTORATION,
            "unexpected post-close active document",
        )
        # Commit reconciliation only after the complete fresh inventory passes.
        # Unknown, retained or ambiguous models leave the invalidated ledger held.
        for key, row in frozen.items():
            if key in survivors:
                self.acquisitions[key].native = survivors[key]
                continue
            self.acquisitions.pop(key)
            self.documents.pop(key, None)
            self.receipt.data["ledger"].append(
                {
                    "event": "discard",
                    "document": key,
                    "title": row["title"],
                    "generation": row["generation"],
                    "implicit": key is not label,
                    "remaining": sorted(self.acquisitions),
                }
            )

    def close(self, label: Document) -> None:
        if label not in self.acquisitions:
            return
        self.tick()
        try:
            frozen = self.discard_inventory()
        except BaseException as error:
            self.receipt.data["ledger"].append(
                {
                    "event": "discard_held",
                    "document": label,
                    "remaining_acquisitions": sorted(self.acquisitions),
                    "error": error_record(error),
                }
            )
            raise
        owned = self.acquisitions[label]
        owned.state = AcquisitionState.DISCARD_ATTEMPTED
        self.receipt.data["ledger"].append(
            {
                "event": "discard_attempt",
                "document": label,
                "title": frozen[label]["title"],
                "generation": owned.generation,
                "preclose_inventory": frozen,
            }
        )
        # Keep identity witnesses only for possible survivors, never the named
        # target. A disappeared dependency's witness is not called; a matching
        # live candidate must still prove continuity, or fail closed if its old
        # owner is disconnected. These witnesses never restore ownership alone.
        owners = {
            key: candidate.native
            for key, candidate in self.acquisitions.items()
            if key is not label
        }
        # Invalidate all usable model/view references before CloseDoc. A throwing
        # or partially effective close remains failed and non-retryable.
        for candidate in self.acquisitions.values():
            candidate.native = None
        self.adapter.currentModel = None
        self.view_handles.clear()
        self.node_handles.clear()
        try:
            self.app.CloseDoc(frozen[label]["title"])
            self.reconcile_discard(label, frozen, owners)
        finally:
            owners.clear()

    def close_all_owned(self) -> None:
        errors = []
        for label in (
            Document.DRAWING,
            Document.R_AUTHOR,
            Document.R,
            Document.N_AUTHOR,
            Document.N,
            Document.Q,
            Document.P,
        ):
            try:
                self.close(label)
            except BaseException as error:
                errors.append(error)
        try:
            require(
                not array(self.app.GetDocuments(), "empty inventory", empty=True)
                and self.app.ActiveDoc is None,
                Verdict.RESTORATION,
                "true empty interval not established",
            )
            for path in self.paths.values():
                require(
                    self.app.GetOpenDocumentByName(str(path)) is None,
                    Verdict.RESTORATION,
                    "saved fixture/source still resident",
                )
            require(
                not self.acquisitions
                and not self.receipt.data.get("unresolved_acquisitions"),
                Verdict.RESTORATION,
                "unresolved acquisitions remain after owned cleanup",
            )
        except BaseException as error:
            errors.append(error)
        self.adapter.currentModel = None
        if errors:
            for error in errors[1:]:
                errors[0].add_note(f"another owned-discard check failed: {error!r}")
            raise errors[0]

    def new_assembly(self, label: Document) -> Any:
        # swDefaultTemplateAssembly=9 remains diagnostic only. Creation uses one
        # committed, byte-pinned input, never a resolver or fallback.
        template = str(ASSEMBLY_TEMPLATE_PATH)
        evidence = assembly_template_evidence(template)
        predicates = evidence["predicates"]
        predicates.update(size_matches=None, sha256_matches=None)
        event: dict[str, Any] = {
            "document": label,
            "preference": {"status": "not_returned"},
            "explicit_input": evidence,
            "expected_identity": {
                "path": template,
                "size": ASSEMBLY_TEMPLATE_SIZE,
                "sha256": ASSEMBLY_TEMPLATE_SHA256,
            },
        }
        self.receipt.data.setdefault("assembly_templates", []).append(event)
        try:
            preference = self.app.GetUserPreferenceStringValue(9)
        except BaseException as error:
            event["preference"] = {"status": "error", "error": error_record(error)}
            # Use the existing failure recorder so checkpoint failure cannot
            # replace the exact native lookup exception being rethrown.
            self.receipt.failure(error)
            raise
        event["preference"] = assembly_template_evidence(preference)
        if predicates["fully_qualified"] is True and predicates["is_file"] is True:
            path = Path(template)
            event["file_identity"] = {
                "path": template,
                "size": path.stat().st_size,
                "sha256": sha256(path),
            }
            predicates["size_matches"] = (
                event["file_identity"]["size"] == ASSEMBLY_TEMPLATE_SIZE
            )
            predicates["sha256_matches"] = (
                event["file_identity"]["sha256"] == ASSEMBLY_TEMPLATE_SHA256
            )
        failed = [name for name, passed in predicates.items() if passed is not True]
        if not failed:
            event["chosen"] = event["file_identity"]
        # Persist preference diagnostics and independent input predicates BEFORE
        # refusal. A suffix/hash mismatch must not be labelled a missing file.
        self.receipt.checkpoint()
        require(
            not failed,
            Verdict.CONSTRUCTION,
            f"explicit assembly template refused: {', '.join(failed)}",
        )
        with self.acquiring(label) as before:
            self.acquired(label, self.app.NewDocument(template, 0, 0.0, 0.0), before)
            model = self.claim(label, 2, None)
        return model

    def insert(self, owner: Document, source: Document, x: float) -> Any:
        model = self.activate(owner)
        assembly = self.bind(model, "IAssemblyDoc")
        component = self.bind(
            assembly.AddComponent5(
                str(self.paths[source]), 0, "", True, "Default", 0.0, 0.0, 0.0
            ),
            "IComponent2",
        )
        self.component_state(component)
        self.identical(
            component.GetModelDoc2(), self.model(source), "inserted canonical reference"
        )
        model.ClearSelection2(True)
        require(
            component.Select2(False, 0) is True,
            Verdict.CONSTRUCTION,
            "placement selection rejected",
        )
        if api_bool(component.IsFixed(), "initial fixed"):
            assembly.UnfixComponent()
            require(
                component.IsFixed() is False, Verdict.CONSTRUCTION, "unfix not consumed"
            )
        transform = self.bind(
            self.app.GetMathUtility(), "IMathUtility"
        ).CreateTransform(self.doubles(translation(x)))
        component.Transform2 = self.bind(transform, "IMathTransform")
        require(
            equal_transform(
                matrix(
                    self.bind(component.Transform2, "IMathTransform").ArrayData,
                    "placed transform",
                ),
                translation(x),
            ),
            Verdict.CONSTRUCTION,
            "exact placement not consumed",
        )
        model.ClearSelection2(True)
        require(
            api_bool(component.Select2(False, 0), "select placed component"),
            Verdict.CONSTRUCTION,
            "cannot select placed component for fixing",
        )
        assembly.FixComponent()
        require(component.IsFixed() is True, Verdict.CONSTRUCTION, "fix not consumed")
        model.ClearSelection2(True)
        self.receipt.counts["placement"] += 1
        return component

    def check_poses(self, label: Document, *, root_assembly: bool) -> dict[str, NodeId]:
        return fixture_instances(
            self.assembly_components(self.model(label)),
            self.paths,
            root_assembly=root_assembly,
        )

    def classify_root(self) -> None:
        names = self.check_poses(Document.R, root_assembly=True)
        if self.component_names:
            require(
                names == self.component_names,
                Verdict.PRESERVATION,
                "persisted full instance paths changed",
            )
        self.component_names = names

    def construct(self) -> None:
        require(
            not array(self.app.GetDocuments(), "initial inventory", empty=True)
            and self.app.ActiveDoc is None,
            Verdict.CONSTRUCTION,
            "probe requires empty inventory; foreign models are not closed",
        )
        for label in (Document.P, Document.Q):
            self.freeze_disk(label)
        self.source_checkpoint("K00")
        for label in (Document.P, Document.Q):
            self.open_source(label)
        self.source_checkpoint("K01")
        self.receipt.data["inputs"] = {
            label: {
                "producer": "part:ch_rod_pivot_pin"
                if label is Document.P
                else "part:ch_pivot_shaft",
                "path": str(self.paths[label]),
                "token": str(self.tokens[label]),
                "disk": self.disk_baselines[str(self.paths[label])],
                "token_identity": self.disk_baselines[str(self.tokens[label])],
                "configuration": "Default",
                "read_only": True,
            }
            for label in (Document.P, Document.Q)
        }
        self.new_assembly(Document.N_AUTHOR)
        self.insert(Document.N_AUTHOR, Document.P, -0.015)
        self.insert(Document.N_AUTHOR, Document.P, 0.0)
        self.insert(Document.N_AUTHOR, Document.Q, 0.015)
        self.rebuild(label=Document.N_AUTHOR)
        self.check_poses(Document.N_AUTHOR, root_assembly=False)
        self.source_checkpoint("K02")
        self.save_native(Document.N_AUTHOR, Document.N, 11)
        self.source_checkpoint("K03")
        self.rebuild(label=Document.N_AUTHOR)
        self.check_poses(Document.N_AUTHOR, root_assembly=False)
        self.source_checkpoint("K04")
        self.close(Document.N_AUTHOR)
        self.open_source(Document.N)
        self.check_poses(Document.N, root_assembly=False)
        self.source_checkpoint("K05-canonical-N-before-R")
        self.new_assembly(Document.R_AUTHOR)
        self.insert(Document.R_AUTHOR, Document.N, 0.0)
        self.insert(Document.R_AUTHOR, Document.Q, 0.030)
        self.rebuild(label=Document.R_AUTHOR)
        self.check_poses(Document.R_AUTHOR, root_assembly=True)
        self.source_checkpoint("K06")
        self.save_native(Document.R_AUTHOR, Document.R, 11)
        self.source_checkpoint("K07")
        self.rebuild(label=Document.R_AUTHOR)
        self.check_poses(Document.R_AUTHOR, root_assembly=True)
        self.source_checkpoint("K08")
        self.close(Document.R_AUTHOR)
        self.source_checkpoint("K09")
        self.close_all_owned()
        self.receipt.counts["full_empty_interval"] += 1
        self.source_checkpoint("K10")
        for label in (Document.P, Document.Q, Document.N, Document.R):
            self.open_source(label)
        self.classify_root()
        self.source_checkpoint("K11")
        self.create_drawing()
        self._constructed_drawing_checkpoint()

    def _observe_drawing_edit_mode(
        self, drawing: Any, row: dict[str, Any], *, verdict: Verdict
    ) -> tuple[DrawingEditMode | None, Exception | None]:
        self.model(Document.DRAWING)
        row.update(
            document=Document.DRAWING,
            generation=self.documents[Document.DRAWING].generation,
            status=ActiveObservation.OBSERVING,
        )
        mode, error = None, None
        try:
            raw = drawing.GetEditSheet()
        except InjectedFailure:
            raise
        except Exception as caught:
            error = caught
        else:
            row.update(raw_type=type(raw).__name__, raw_repr=repr(raw))
            try:
                mode = (
                    DrawingEditMode.SHEET
                    if api_bool(raw, "GetEditSheet", verdict)
                    else DrawingEditMode.FORMAT
                )
            except InjectedFailure:
                raise
            except Exception as caught:
                error = caught
        if error is not None:
            row.update(status=ActiveObservation.ERROR, error=error_record(error))
        else:
            row.update(status=Verdict.PASSED, mode=mode)
        return mode, error

    def _require_drawing_sheet_mode(
        self,
        drawing: Any,
        row: dict[str, Any],
        *,
        verdict: Verdict = Verdict.CONSTRUCTION,
    ) -> None:
        row["required_mode"] = DrawingEditMode.SHEET
        mode, error = self._observe_drawing_edit_mode(drawing, row, verdict=verdict)
        if error is not None:
            raise error
        require(
            mode is DrawingEditMode.SHEET,
            verdict,
            "drawing must be in edit sheet mode",
        )

    def _normalize_drawing_sheet_mode(self, drawing: Any) -> None:
        model = self.model(Document.DRAWING)
        record: dict[str, Any] = {
            "event": "drawing_sheet_mode_normalization",
            "boundary": "admitted_new_drawing",
            "document": Document.DRAWING,
            "generation": self.documents[Document.DRAWING].generation,
            "active_identity": {"status": ActiveObservation.NOT_OBSERVED},
            "pre": {"status": ActiveObservation.NOT_OBSERVED},
            "normalization": {"status": ActiveObservation.NOT_OBSERVED},
            "post": {"status": ActiveObservation.NOT_OBSERVED},
            "before_views": {
                view_id: {"status": ActiveObservation.NOT_OBSERVED}
                for view_id in ViewId
            },
            "exports": {
                export: {"status": ActiveObservation.NOT_OBSERVED} for export in Export
            },
        }
        self.drawing_mode_record = record
        self.receipt.data["ledger"].append(record)
        record["active_identity"]["status"] = ActiveObservation.OBSERVING
        try:
            self.identical(self.app.ActiveDoc, model, "drawing sheet-mode receiver")
        except BaseException as error:
            record["active_identity"].update(
                status=ActiveObservation.ERROR, error=error_record(error)
            )
            raise
        record["active_identity"].update(status=Verdict.PASSED, native_identity=1)
        self._observe_drawing_edit_mode(
            drawing, record["pre"], verdict=Verdict.CONSTRUCTION
        )
        # Match new_project_drawing: this is a void mode normalizer, not a rebuild.
        record["normalization"]["status"] = ActivationState.CALLING
        try:
            drawing.EditSheet()
        except BaseException as error:
            record["normalization"].update(
                status=ActiveObservation.ERROR, error=error_record(error)
            )
            raise
        record["normalization"]["status"] = Verdict.PASSED
        self._require_drawing_sheet_mode(drawing, record["post"])

    def create_drawing(self) -> None:
        template = self.root / "cad/templates/harmonic-analyzer-landscape.DRWDOT"
        require(
            template.is_file(),
            Verdict.CONSTRUCTION,
            "declared landscape template absent",
        )
        with self.acquiring(Document.DRAWING) as before:
            self.acquired(
                Document.DRAWING,
                self.app.NewDocument(str(template), 12, 0.4318, 0.2794),
                before,
            )
            model = self.claim(Document.DRAWING, 3, None)
        drawing = self.draw()
        self._normalize_drawing_sheet_mode(drawing)
        sheet = self.bind(drawing.GetCurrentSheet(), "ISheet")
        sheet.SetName(ViewId.A)
        require(
            sheet.GetName() == ViewId.A,
            Verdict.CONSTRUCTION,
            "first-sheet rename rejected",
        )
        for view_id in ViewId:
            if view_id is ViewId.B:
                require(
                    drawing.NewSheet4(
                        ViewId.B,
                        12,
                        13,
                        5.0,
                        1.0,
                        False,
                        "",
                        0.4318,
                        0.2794,
                        "",
                        0.0,
                        0.0,
                        0.0,
                        0.0,
                        1,
                        1,
                    )
                    is True,
                    Verdict.CONSTRUCTION,
                    "blank sentinel sheet creation rejected",
                )
            require(
                drawing.ActivateSheet(view_id) is True,
                Verdict.CONSTRUCTION,
                "fixture sheet activation rejected",
            )
            current = self.bind(drawing.GetCurrentSheet(), "ISheet")
            props = array(current.GetProperties(), "sheet properties")
            require(
                current.GetName() == view_id
                and len(props) >= 7
                and abs(float(props[5]) - 0.4318) <= 1e-9
                and abs(float(props[6]) - 0.2794) <= 1e-9,
                Verdict.CONSTRUCTION,
                "fixture sheet name/size readback",
            )
            self._require_drawing_sheet_mode(
                drawing, self.drawing_mode_record["before_views"][view_id]
            )
            view = self.bind(
                drawing.CreateDrawViewFromModelView3(
                    str(self.paths[Document.R]), "*Front", 0.2159, 0.1397, 0.0
                ),
                "IView",
            )
            view.UseSheetScale = 0
            view.ScaleRatio = self.doubles((5.0, 1.0))
            require(
                _use_sheet_scale(view.UseSheetScale, Verdict.CONSTRUCTION) == 0
                and tuple(view.ScaleRatio) == (5.0, 1.0),
                Verdict.CONSTRUCTION,
                "explicit view scale not consumed",
            )
            require(
                drawing.ActivateSheet(view_id) is True
                and self.bind(drawing.GetCurrentSheet(), "ISheet").GetName() == view_id
                and drawing.ActiveDrawingView is None,
                Verdict.CONSTRUCTION,
                "sheet-owned page marker requires observed null active drawing view",
            )
            model.ClearSelection2(True)
            note = self.bind(
                model.InsertNote(f"BULKVIS-{view_id.name}-{self.receipt.root.name}"),
                "INote",
            )
            annotation = self.bind(note.GetAnnotation(), "IAnnotation")
            require(
                annotation.SetPosition(0.020, 0.250, 0.0) is True,
                Verdict.CONSTRUCTION,
                "page marker positioning rejected",
            )
            position = array(annotation.GetPosition(), "marker position")
            require(
                len(position) == 3
                and all(
                    abs(float(a) - b) <= 1e-9
                    for a, b in zip(position, (0.020, 0.250, 0.0), strict=True)
                )
                and note.GetText()
                == f"BULKVIS-{view_id.name}-{self.receipt.root.name}",
                Verdict.CONSTRUCTION,
                "page marker position/text readback",
            )
        self.rebuild()
        self.activate_view(ViewId.A)
        self.views()
        self.receipt.data["fixture"] = {
            "paths": {key: str(path) for key, path in self.paths.items()},
            "native_generations": dict(self.generations),
        }

    def _constructed_drawing_checkpoint(self) -> None:
        primary = None
        try:
            self.identity_controls()
        except BaseException as error:
            primary = error
            self.receipt.failure(primary)
        try:
            context = self.checkpoint("constructed-drawing")
        except BaseException as error:
            if primary is None:
                raise
            primary.add_note(f"constructed-drawing readback also failed: {error!r}")
            self.receipt.failure(error, secondary=True)
        if primary is not None:
            raise primary
        # The complete checkpoint, including its final receipt write, passed.
        self.harness_flags = dict(context["flags"])
        self.receipt.data["fixture"]["initial_flags"] = dict(self.harness_flags)

    def views(self) -> dict[ViewId, tuple[Any, dict[NodeId, DrawingNode]]]:
        result = {}
        drawing = self.draw()
        sheet_arrays = array(drawing.GetViews(), "all sheet views")
        require(
            len(sheet_arrays) == 2, Verdict.PRESERVATION, "all-view sheet count changed"
        )
        for raw_sheet in sheet_arrays:
            raw_views = array(raw_sheet, "sheet and real views")
            require(
                len(raw_views) == 2,
                Verdict.PRESERVATION,
                "extra/missing real fixture view",
            )
            sheet_view = self.bind(raw_views[0], "IView")
            # The sheet/pseudo-view names its sheet; only real views own .Sheet.
            name = api_string(sheet_view.Name, "fixture sheet view name")
            require(name in tuple(ViewId), Verdict.PRESERVATION, "unexpected sheet ID")
            view_id = ViewId(name)
            require(view_id not in result, Verdict.PRESERVATION, "duplicate sheet ID")
            sheet = self.bind(drawing.Sheet(name), "ISheet")
            require(
                api_string(sheet.GetName(), "fixture named sheet name") == name,
                Verdict.PRESERVATION,
                "named-sheet lookup mismatch",
            )
            view = self.bind(raw_views[1], "IView")
            require(
                self.bind(view.Sheet, "ISheet").GetName() == view_id,
                Verdict.PRESERVATION,
                "real-view sheet mismatch",
            )
            self.identical(
                view.ReferencedDocument, self.model(Document.R), "view source R"
            )
            transform = matrix(
                self.bind(view.ModelToViewTransform, "IMathTransform").ArrayData,
                "model-to-view transform",
            )
            state = {
                "name": api_string(view.Name, "view name"),
                "configuration": api_string(
                    view.ReferencedConfiguration, "view referenced configuration"
                ),
                "source": normalized(
                    self.bind(view.ReferencedDocument, "IModelDoc2").GetPathName()
                ),
                "orientation": view.GetOrientationName(),
                "scale": array(view.ScaleRatio, "view scale"),
                "use_sheet_scale": _use_sheet_scale(view.UseSheetScale),
                "position": array(view.Position, "view position"),
                "transform": transform,
            }
            require(
                state["orientation"] == "*Front"
                and state["configuration"] == "Default"
                and state["scale"] == (5.0, 1.0)
                and state["use_sheet_scale"] == 0,
                Verdict.CONSTRUCTION,
                "view projection/scale/configuration contract",
            )
            prior = self.view_baselines.get(view_id)
            if prior is not None:
                require(
                    all(
                        state[key] == prior[key]
                        for key in state
                        if key not in ("position", "transform")
                    )
                    and equal_transform(transform, prior["transform"])
                    and len(state["position"]) == len(prior["position"])
                    and all(
                        abs(float(a) - float(b)) <= 1e-9
                        for a, b in zip(
                            state["position"], prior["position"], strict=True
                        )
                    ),
                    Verdict.PRESERVATION,
                    "view layout/reference changed",
                )
            else:
                self.view_baselines[view_id] = state
            if view_id in self.view_handles:
                self.identical(
                    view, self.view_handles[view_id], "fresh view generation"
                )
            self.view_handles[view_id] = view
            root = self.bind(view.RootDrawingComponent2(False), "IDrawingComponent")
            require(
                root.IsRoot() is True,
                Verdict.CONSTRUCTION,
                "synthetic drawing root absent",
            )
            pending = [
                (raw, None)
                for raw in array(root.GetChildren(), "root children", empty=True)
            ]
            nodes = {}
            while pending:
                require(
                    len(nodes) + len(pending) <= 5,
                    Verdict.PRESERVATION,
                    "fixture node bound/cycle",
                )
                raw, parent = pending.pop()
                dc = self.bind(raw, "IDrawingComponent")
                require(
                    dc.IsRoot() is False, Verdict.PRESERVATION, "nested synthetic root"
                )
                component = self.bind(dc.Component, "IComponent2")
                component_state = self.component_state(component)
                key = self.component_names.get(component_state["path"])
                require(
                    key is not None and key not in nodes,
                    Verdict.PRESERVATION,
                    "unmapped/duplicate full drawing component path",
                )
                self.identical(dc.View, view, "drawing component own view")
                children = array(
                    dc.GetChildren(), "drawing component children", empty=True
                )
                require(
                    bool(children) == (key is NodeId.N),
                    Verdict.PRESERVATION,
                    "real nested ancestor/leaf composition changed",
                )
                require(
                    parent == PARENTS[key],
                    Verdict.PRESERVATION,
                    "real nested parent changed",
                )
                node = NodeState(
                    key,
                    parent,
                    FAMILIES[key],
                    api_bool(dc.Visible, "drawing component own visibility"),
                    component_state["path"],
                    component_state["source"],
                    component_state["configuration"],
                    tuple(component_state["transform"]),
                )
                if (view_id, key) in self.node_handles:
                    self.identical(
                        dc,
                        self.node_handles[view_id, key],
                        "fresh drawing-component generation",
                    )
                self.node_handles[view_id, key] = dc
                nodes[key] = DrawingNode(node, dc, component)
                pending.extend((child, key) for child in children)
            effective({key: node.state for key, node in nodes.items()})
            result[view_id] = (view, nodes)
        require(
            set(result) == set(ViewId),
            Verdict.PRESERVATION,
            "missing target/sentinel view",
        )
        return result

    def _flag_observations(
        self, views: Any, *, receiver_error: BaseException | None = None
    ) -> tuple[dict[str, bool], dict[str, Any], BaseException | None]:
        values: dict[str, bool] = {}
        evidence: dict[str, Any] = {
            "receiver": {
                "document": Document.DRAWING,
                "generation": self.generations[Document.DRAWING],
            },
            "dependencies": {},
            "values": {},
        }
        errors: list[BaseException] = []
        try:
            if receiver_error is not None:
                raise receiver_error
            model = self.model(Document.DRAWING)
            identity = self.identical(
                self.app.ActiveDoc, model, "active owned drawing for flags"
            )
            evidence["receiver"].update(status="passed", native_identity=identity)
        except BaseException as error:
            evidence["receiver"].update(status="failed", error=error_record(error))
            for key, owner, member in (
                ("A_disable", f"IView/{ViewId.A}", "DisableAutoUpdate"),
                ("B_disable", f"IView/{ViewId.B}", "DisableAutoUpdate"),
                ("automatic", "IDrawingDoc", "AutomaticViewUpdate"),
                ("graphics", "IModelView", "EnableGraphicsUpdate"),
                ("tree", "IFeatureManager", "EnableFeatureTree"),
                ("tree_window", "IFeatureManager", "EnableFeatureTreeWindow"),
            ):
                evidence["values"][key] = {
                    "owner": owner,
                    "member": member,
                    "provenance": {
                        "document": Document.DRAWING,
                        "generation": self.generations[Document.DRAWING],
                    },
                    "status": "blocked",
                    "dependency": "receiver",
                }
            return values, evidence, error

        provenance = {
            "document": Document.DRAWING,
            "generation": self.generations[Document.DRAWING],
        }

        def dependency(member: str, interface: str) -> Any:
            row = {
                "owner": "IModelDoc2",
                "member": member,
                "provenance": provenance,
            }
            evidence["dependencies"][member] = row
            try:
                raw = model if member == "drawing" else getattr(model, member)
                row.update(type=type(raw).__name__, is_null=raw is None)
                receiver = self.bind(raw, interface)
                row["status"] = "passed"
                return receiver
            except BaseException as error:
                row.update(status="failed", error=error_record(error))
                errors.append(error)
                return None

        drawing = dependency("drawing", "IDrawingDoc")
        model_view = dependency("ActiveView", "IModelView")
        tree = dependency("FeatureManager", "IFeatureManager")

        def read(
            key: str, receiver: Any, owner: str, member: str, depends_on: str
        ) -> None:
            row = {"owner": owner, "member": member, "provenance": provenance}
            evidence["values"][key] = row
            if receiver is None:
                row.update(status="blocked", dependency=depends_on)
                return
            try:
                raw = getattr(receiver, member)
                row.update(type=type(raw).__name__, repr=repr(raw))
                value = api_bool(raw, f"{owner}.{member}")
                row.update(status="passed", value=value)
                values[key] = value
            except BaseException as error:
                row.update(status="failed", error=error_record(error))
                errors.append(error)

        read(
            "A_disable",
            views[ViewId.A][0],
            f"IView/{ViewId.A}",
            "DisableAutoUpdate",
            "views",
        )
        read(
            "B_disable",
            views[ViewId.B][0],
            f"IView/{ViewId.B}",
            "DisableAutoUpdate",
            "views",
        )
        read("automatic", drawing, "IDrawingDoc", "AutomaticViewUpdate", "drawing")
        read("graphics", model_view, "IModelView", "EnableGraphicsUpdate", "ActiveView")
        read("tree", tree, "IFeatureManager", "EnableFeatureTree", "FeatureManager")
        read(
            "tree_window",
            tree,
            "IFeatureManager",
            "EnableFeatureTreeWindow",
            "FeatureManager",
        )
        return values, evidence, errors[0] if errors else None

    def flags(self) -> dict[str, bool]:
        values, _evidence, error = self._flag_observations(self.views())
        if error is not None:
            raise error
        return values

    def set_flags(self, flags: Mapping[str, bool]) -> None:
        before = self.flags()
        require(
            set(flags) == set(before)
            and all(type(value) is bool for value in flags.values()),
            Verdict.CONSTRUCTION,
            "invalid harness flag vector",
        )
        views = self.views()
        model = self.model(Document.DRAWING)
        self.identical(
            self.app.ActiveDoc, model, "active owned drawing for flag writes"
        )
        drawing = self.bind(model, "IDrawingDoc")
        model_view = self.bind(model.ActiveView, "IModelView")
        tree = self.bind(model.FeatureManager, "IFeatureManager")
        if before["A_disable"] != flags["A_disable"]:
            views[ViewId.A][0].DisableAutoUpdate = flags["A_disable"]
        if before["B_disable"] != flags["B_disable"]:
            views[ViewId.B][0].DisableAutoUpdate = flags["B_disable"]
        if before["automatic"] != flags["automatic"]:
            drawing.AutomaticViewUpdate = flags["automatic"]
        if before["graphics"] != flags["graphics"]:
            model_view.EnableGraphicsUpdate = flags["graphics"]
        if before["tree"] != flags["tree"]:
            tree.EnableFeatureTree = flags["tree"]
        if before["tree_window"] != flags["tree_window"]:
            tree.EnableFeatureTreeWindow = flags["tree_window"]
        self.receipt.counts["harness_flag_writes"] += sum(
            before[key] != flags[key] for key in before
        )
        require(
            self.flags() == dict(flags),
            Verdict.RESTORATION,
            "harness flag vector not consumed",
        )

    def activate_view(self, view_id: ViewId, *, sheet_only: bool = False) -> None:
        self.activate(Document.DRAWING)
        drawing = self.draw()
        require(
            drawing.ActivateSheet(view_id) is True,
            Verdict.RESTORATION,
            "ActivateSheet rejected",
        )
        if not sheet_only:
            view = self.views()[view_id][0]
            require(
                drawing.ActivateView(api_string(view.Name, "active view name")) is True,
                Verdict.RESTORATION,
                "ActivateView rejected",
            )
            self.identical(drawing.ActiveDrawingView, view, "active drawing view")
        else:
            require(
                drawing.ActiveDrawingView is None,
                Verdict.CONSTRUCTION,
                "sheet-only context not established; no guessed alternate route",
            )
        require(
            self.bind(drawing.GetCurrentSheet(), "ISheet").GetName() == view_id,
            Verdict.RESTORATION,
            "active sheet readback",
        )

    def selection(self, views: Any) -> list[dict[str, Any]]:
        manager = self.bind(
            self.model(Document.DRAWING).SelectionManager, "ISelectionMgr"
        )
        count = api_int(
            manager.GetSelectedObjectCount2(-1), "selected count", Verdict.SELECTION
        )
        require(0 <= count <= 2, Verdict.SELECTION, "unexpected selection cardinality")
        result = []
        for index in range(1, count + 1):
            raw = manager.GetSelectedObject6(index, -1)
            require(
                raw is not None and manager.GetSelectedObjectType3(index, -1) == 20,
                Verdict.SELECTION,
                "original/temporary selection is not component type 20",
            )
            matches = [
                (view_id, key)
                for view_id, (_, nodes) in views.items()
                for key, node in nodes.items()
                if self.same(raw, node.drawing_component) == 1
            ]
            require(
                len(matches) == 1,
                Verdict.IDENTITY,
                "selected dispatch not exact drawing object",
            )
            view_id, key = matches[0]
            # Identity to an independently enumerated DC precedes DC-specific access.
            dc = self.bind(raw, "IDrawingComponent")
            self.identical(dc.View, views[view_id][0], "selected own view")
            self.identical(
                manager.GetSelectedObjectsDrawingView2(index, -1),
                views[view_id][0],
                "selected manager view",
            )
            result.append(
                {
                    "view": view_id,
                    "node": key,
                    "mark": api_int(
                        manager.GetSelectedObjectMark(index), "selected mark"
                    ),
                    "type": 20,
                }
            )
        return result

    def _context_observations(
        self, views: Any
    ) -> tuple[dict[str, Any], BaseException | None]:
        context: dict[str, Any] = {"observations": {}}
        observations = context["observations"]
        errors: list[BaseException] = []
        try:
            model = self.model(Document.DRAWING)
            identity = self.identical(self.app.ActiveDoc, model, "active owned drawing")
            drawing = self.bind(model, "IDrawingDoc")
            observations["receiver"] = {
                "status": "passed",
                "document": Document.DRAWING,
                "generation": self.generations[Document.DRAWING],
                "native_identity": identity,
            }
        except BaseException as error:
            observations["receiver"] = {
                "status": "failed",
                "error": error_record(error),
            }
            for key in ("sheet", "view", "selection", "flags"):
                observations[key] = {"status": "blocked", "dependency": "receiver"}
            flags, evidence, _error = self._flag_observations(
                views, receiver_error=error
            )
            context["flags"] = flags
            context["flag_observations"] = evidence
            context["observation_error"] = error_record(error)
            return context, error

        def sheet() -> ViewId:
            name = self.bind(drawing.GetCurrentSheet(), "ISheet").GetName()
            require(name in tuple(ViewId), Verdict.PRESERVATION, "foreign active sheet")
            return ViewId(name)

        def active_view() -> ViewId | None:
            raw = drawing.ActiveDrawingView
            if raw is None:
                return None
            matches = [
                view_id
                for view_id, (view, _) in views.items()
                if self.same(raw, view) == 1
            ]
            require(
                len(matches) == 1, Verdict.IDENTITY, "unidentified active drawing view"
            )
            return matches[0]

        # These safe branches are independent once their owned receiver is proved.
        for key, reader in (
            ("sheet", sheet),
            ("view", active_view),
            ("selection", lambda: self.selection(views)),
        ):
            try:
                value = reader()
                context[key] = value
                observations[key] = {"status": "passed", "value": value}
            except BaseException as error:
                observations[key] = {"status": "failed", "error": error_record(error)}
                errors.append(error)
        flags, evidence, flag_error = self._flag_observations(views)
        context["flags"] = flags
        context["flag_observations"] = evidence
        if flag_error is not None:
            observations["flags"] = {
                "status": "failed",
                "error": error_record(flag_error),
            }
            errors.append(flag_error)
        else:
            observations["flags"] = {"status": "passed"}
        if errors:
            context["observation_error"] = error_record(errors[0])
        return context, errors[0] if errors else None

    def context(self, views: Any) -> dict[str, Any]:
        context, error = self._context_observations(views)
        if error is not None:
            raise error
        # Restoration compares semantic state, not diagnostic wrapper provenance.
        return {key: context[key] for key in ("sheet", "view", "selection", "flags")}

    def checkpoint(
        self,
        label: str,
        *,
        changed: tuple[NodeId, ...] = (),
        effect_verdict: Verdict = Verdict.PRESERVATION,
    ) -> dict[str, Any]:
        with self.timed("readback"):
            views = self.views()
            observed = {}
            mismatches = []
            for view_id, (_, nodes) in views.items():
                states = {key: node.state for key, node in nodes.items()}
                actual_effective = effective(states)
                wanted = {
                    key: self.expected[view_id][key]
                    and (PARENTS[key] is None or self.expected[view_id][PARENTS[key]])
                    for key in NodeId
                }
                for key in NodeId:
                    verdict = (
                        effect_verdict
                        if view_id is ViewId.A and key in changed
                        else Verdict.PRESERVATION
                    )
                    if (
                        states[key].own != self.expected[view_id][key]
                        or actual_effective[key] != wanted[key]
                    ):
                        mismatches.append(
                            (
                                verdict,
                                f"{view_id}/{key}: unexpected own/effective visibility at {label}",
                            )
                        )
                observed[view_id] = {
                    "nodes": {key: asdict(value) for key, value in states.items()},
                    "effective": actual_effective,
                    "view": self.view_baselines[view_id],
                }
            # Persist native values before raising an effect failure: a void
            # return alone never proves that either selected object changed.
            source_error = None
            try:
                sources = self.sources()
            except BaseException as error:
                source_error = error
                sources = {"observation_error": error_record(error)}
            context_error = None
            try:
                context, context_error = self._context_observations(views)
            except BaseException as error:
                context_error = error
                context = {"observation_error": error_record(error)}
            primary = (
                source_error
                or context_error
                or (ProbeFailure(*mismatches[0]) if mismatches else None)
            )
            if source_error is not None and context_error is not None:
                if self.receipt.primary is None:
                    self.receipt.failure(source_error)
                source_error.add_note(
                    f"context readback also failed: {context_error!r}"
                )
                self.receipt.failure(context_error, secondary=True)
            try:
                self.receipt.observe(
                    SnapshotKind.FULL,
                    label,
                    {
                        "views": observed,
                        "source": sources,
                        "context": context,
                        "visibility_mismatches": [
                            {"verdict": verdict, "message": message}
                            for verdict, message in mismatches
                        ],
                    },
                )
                self.receipt.checkpoint()
            except BaseException as report_error:
                if primary is None:
                    raise
                if self.receipt.primary is None:
                    self.receipt.failure(primary)
                primary.add_note(f"readback checkpoint also failed: {report_error!r}")
                self.receipt.failure(report_error, secondary=True)
                raise primary
            if source_error is not None:
                raise source_error
            if context_error is not None:
                raise context_error
            if mismatches:
                raise ProbeFailure(*mismatches[0])
        self.receipt.checkpoint()
        return context

    def identity_controls(self) -> None:
        positives: dict[str, int] = {}
        negatives: dict[str, int] = {}
        row = {
            "drawing_generation": self.generations[Document.DRAWING],
            "positive_is_same": positives,
            "negative_is_same": negatives,
        }
        self.receipt.data.setdefault("native_identity_controls", []).append(row)
        try:
            first, second = self.views(), self.views()
            for view_id in ViewId:
                positives[f"{view_id}/view_self"] = self.same(
                    first[view_id][0], first[view_id][0]
                )
                positives[f"{view_id}/fresh_view"] = self.same(
                    first[view_id][0], second[view_id][0]
                )
                for key in NodeId:
                    positives[f"{view_id}/fresh_component/{key}"] = self.same(
                        first[view_id][1][key].drawing_component,
                        second[view_id][1][key].drawing_component,
                    )
            negatives["distinct_views"] = self.same(
                first[ViewId.A][0], first[ViewId.B][0]
            )
            negatives["distinct_same_part_instances"] = self.same(
                first[ViewId.A][1][NodeId.P1].drawing_component,
                first[ViewId.A][1][NodeId.P2].drawing_component,
            )
            positives["drawing_self"] = self.same(
                self.model(Document.DRAWING), self.model(Document.DRAWING)
            )
            require(
                all(value == 1 for value in positives.values()),
                Verdict.IDENTITY,
                "native positive-control objects compare different",
            )
            require(
                all(value == 0 for value in negatives.values()),
                Verdict.IDENTITY,
                "distinct native positive-control objects compare equal",
            )
        except BaseException as error:
            row["error"] = error_record(error)
            raise

    def setup_visibility(
        self, changes: Mapping[NodeId, bool], *, rebuild: bool = True
    ) -> None:
        with self.timed("harness_setup"):
            self.activate_view(ViewId.A)
            nodes = self.views()[ViewId.A][1]
            for key, value in changes.items():
                require(
                    type(value) is bool and nodes[key].state.own != value,
                    Verdict.CONSTRUCTION,
                    f"redundant/unplanned scalar setup: {key}",
                )
                nodes[key].drawing_component.Visible = value
                require(
                    nodes[key].drawing_component.Visible is value,
                    Verdict.CONSTRUCTION,
                    "fixture scalar preparation rejected",
                )
                self.expected[ViewId.A][key] = value
                self.receipt.counts["setup_scalar_visibility"] += 1
        if rebuild:
            require(
                self.receipt.case in SETUP_REBUILD_CASES,
                Verdict.CONSTRUCTION,
                "unplanned harness setup rebuild",
            )
            self.rebuild(setup=True)

    def prepare_context(
        self, *, marked: bool = False, sheet_only: bool = False
    ) -> None:
        self.activate_view(
            ViewId.B if marked or sheet_only else ViewId.A, sheet_only=sheet_only
        )
        model = self.model(Document.DRAWING)
        model.ClearSelection2(True)
        if marked:
            views = self.views()
            manager = self.bind(model.SelectionManager, "ISelectionMgr")
            for index, key in enumerate((NodeId.P1, NodeId.P2)):
                data = self.bind(manager.CreateSelectData(), "ISelectData")
                data.View = views[ViewId.B][0]
                data.Mark = 16 if index == 0 else 32
                require(
                    views[ViewId.B][1][key].drawing_component.Select(index > 0, data)
                    is True,
                    Verdict.SELECTION,
                    "marked sentinel selection rejected",
                )
                self.receipt.counts["marked_select"] += 1
            require(
                self.selection(self.views())
                == [
                    {"view": ViewId.B, "node": NodeId.P1, "mark": 16, "type": 20},
                    {"view": ViewId.B, "node": NodeId.P2, "mark": 32, "type": 20},
                ],
                Verdict.SELECTION,
                "marked sentinel precondition mismatch",
            )

    def nested_selection_case(self) -> None:
        """Discriminate only two levels with an empty intermediate selection."""
        original = self.context(self.views())
        require(
            original["sheet"] is ViewId.B
            and original["view"] is ViewId.B
            and original["selection"]
            == [
                {"view": ViewId.B, "node": NodeId.P1, "mark": 16, "type": 20},
                {"view": ViewId.B, "node": NodeId.P2, "mark": 32, "type": 20},
            ],
            Verdict.SELECTION,
            "C29 requires the exact marked sentinel L0",
        )
        row = self.receipt.data["cases"][self.receipt.case]
        nested = row["nested_selection"] = {
            "scope": "two_levels_empty_intermediate_only",
            "phase": "outer_suspend_entered",
            "L0": original,
            "outer_resume": {"attempted": False},
        }
        manager = self.bind(
            self.model(Document.DRAWING).SelectionManager, "ISelectionMgr"
        )
        self.receipt.checkpoint()
        raw = manager.SuspendSelectionList()
        nested["outer_suspend"] = {"raw": repr(raw), "type": type(raw).__name__}
        require(
            api_int(raw, "C29 outer SuspendSelectionList", Verdict.SELECTION) == 1,
            Verdict.SELECTION,
            "C29 outer suspension did not report nonempty L0",
        )
        empty = {**original, "selection": []}
        nested["L1"] = self.context(self.views())
        require(
            nested["L1"] == empty,
            Verdict.SELECTION,
            "C29 outer suspension did not expose exact empty L1",
        )
        nested["phase"] = "outer_suspended"
        self.checkpoint("C29-outer-suspended")
        nested["phase"] = "inner_guard_entered"
        self.receipt.checkpoint()
        with self.selection_guard() as inner:
            nested["phase"] = "inner_selection_entered"
            self.receipt.checkpoint()
            self.model(Document.DRAWING).ClearSelection2(True)
            view, nodes = self.views()[ViewId.A]
            data = self.bind(inner.CreateSelectData(), "ISelectData")
            data.View, data.Mark = view, 0
            pins = (NodeId.P1, NodeId.P2)
            raw = inner.AddSelectionListObjects(
                self.dispatches(tuple(nodes[key].drawing_component for key in pins)),
                data,
            )
            nested["bulk_add"] = {"raw": repr(raw), "type": type(raw).__name__}
            added = api_int(raw, "C29 AddSelectionListObjects", Verdict.SELECTION)
            self.receipt.counts["bulk_add"] += 1
            require(added == 2, Verdict.SELECTION, "C29 partial bulk add")
            row.setdefault("selections", []).append(self.verify_batch(inner, pins))
            nested["phase"] = "inner_selected"
            self.checkpoint("C29-inner-selected")
            nested["phase"] = "inner_restore_entered"
            self.receipt.checkpoint()
        # No finally-pop: unexpected inner restoration aborts before this point.
        require(
            nested["inner_restored_context"] == empty,
            Verdict.RESTORATION,
            "C29 inner resume did not reproduce exact empty L1",
        )
        nested["phase"] = "outer_resume_entered"
        nested["outer_resume"]["attempted"] = True
        self.receipt.checkpoint()
        raw = manager.ResumeSelectionList2(False)
        nested["outer_resume"].update(
            completed=True, raw=repr(raw), type=type(raw).__name__
        )
        nested["L0_restored"] = self.context(self.views())
        require(
            nested["L0_restored"] == original,
            Verdict.RESTORATION,
            "C29 outer resume did not reproduce exact marked L0",
        )
        nested["phase"] = "outer_restored"
        self.checkpoint("C29-outer-resumed")

    @contextmanager
    def selection_guard(self) -> Iterator[Any]:
        original = self.context(self.views())
        manager = self.bind(
            self.model(Document.DRAWING).SelectionManager, "ISelectionMgr"
        )
        suspended = False
        primary: BaseException | None = None
        nested = (
            self.receipt.data["cases"][self.receipt.case].get("nested_selection")
            if self.receipt.case is Case.NESTED_SELECTION
            else None
        )

        def resume_selection() -> None:
            if suspended:
                if nested is not None:
                    nested["inner_resume"] = {"attempted": True}
                raw = manager.ResumeSelectionList2(False)
                if nested is not None:
                    nested["inner_resume"].update(
                        completed=True, raw=repr(raw), type=type(raw).__name__
                    )

        try:
            raw_result = manager.SuspendSelectionList()
            suspended = True
            if nested is not None:
                nested["inner_suspend"] = {
                    "raw": repr(raw_result),
                    "type": type(raw_result).__name__,
                }
                self.receipt.checkpoint()
            result = api_int(raw_result, "SuspendSelectionList", Verdict.SELECTION)
            require(
                result == (1 if original["selection"] else 0)
                and api_int(
                    manager.GetSelectedObjectCount2(-1),
                    "suspended selection count",
                    Verdict.SELECTION,
                )
                == 0,
                Verdict.SELECTION,
                "suspension did not preserve list/clear temporary list",
            )
            self.receipt.counts["selection_guard"] += 1
            self.activate_view(ViewId.A)
            yield manager
        except BaseException as error:
            primary = error
            raise
        finally:
            restoration_errors = []
            previous_mode, self.mode = self.mode, RunMode.RESTORING
            restore_started = time.monotonic()
            try:
                # Each independent restoration runs even if an earlier one fails.
                for restore in (
                    lambda: self.restore_a_update(original["flags"]["A_disable"]),
                    lambda: self.activate_view(
                        original["sheet"], sheet_only=original["view"] is None
                    ),
                    resume_selection,
                ):
                    try:
                        restore()
                    except BaseException as error:
                        restoration_errors.append(error)
                try:
                    restored_context = self.context(self.views())
                    if nested is not None:
                        nested["inner_restored_context"] = restored_context
                    require(
                        restored_context == original,
                        Verdict.RESTORATION,
                        "original ordered selection/marks/context/flags not restored",
                    )
                except BaseException as error:
                    restoration_errors.append(error)
                self.receipt.data["cases"][self.receipt.case]["operations"].append(
                    {
                        "bucket": "restore",
                        "seconds": time.monotonic() - restore_started,
                        "status": Verdict.RESTORATION
                        if restoration_errors
                        else Verdict.PASSED,
                    }
                )
                try:
                    self.checkpoint("selection-guard-restored")
                except BaseException as error:
                    restoration_errors.append(error)
            finally:
                self.mode = previous_mode
            if restoration_errors:
                if primary is not None:
                    for error in restoration_errors:
                        primary.add_note(f"restoration also failed: {error!r}")
                        self.receipt.failure(error, secondary=True)
                else:
                    raise ProbeFailure(
                        Verdict.RESTORATION,
                        "; ".join(repr(error) for error in restoration_errors),
                    )

    def restore_a_update(self, value: bool) -> None:
        view = self.views()[ViewId.A][0]
        if api_bool(view.DisableAutoUpdate, "restored A flag") != value:
            view.DisableAutoUpdate = value
        require(
            view.DisableAutoUpdate is value,
            Verdict.RESTORATION,
            "A update restore rejected",
        )

    def verify_batch(
        self, manager: Any, intended: tuple[NodeId, ...]
    ) -> dict[str, Any]:
        views = self.views()
        view, nodes = views[ViewId.A]
        count = api_int(
            manager.GetSelectedObjectCount2(-1),
            "batch selection count",
            Verdict.SELECTION,
        )
        require(
            count == len(intended),
            Verdict.SELECTION,
            "partial/extra selection before command",
        )
        raw = [manager.GetSelectedObject6(index, -1) for index in range(1, count + 1)]
        identities = [
            [self.same(item, nodes[key].drawing_component) for key in intended]
            for item in raw
        ]
        # Reject the raw identity matrix BEFORE reading drawing-component members.
        require(
            all(sum(row) == 1 for row in identities)
            and all(sum(row[i] for row in identities) == 1 for i in range(count)),
            Verdict.SELECTION,
            "selected raw dispatch not exact intended object",
        )
        types = [
            api_int(
                manager.GetSelectedObjectType3(index, -1),
                "batch type",
                Verdict.SELECTION,
            )
            for index in range(1, count + 1)
        ]
        marks = [
            api_int(
                manager.GetSelectedObjectMark(index), "batch mark", Verdict.SELECTION
            )
            for index in range(1, count + 1)
        ]
        require(
            all(value == 20 for value in types),
            Verdict.SELECTION,
            "wrong selected native type",
        )
        own = [
            self.same(self.bind(item, "IDrawingComponent").View, view) for item in raw
        ]
        selected_views = [
            self.same(manager.GetSelectedObjectsDrawingView2(index, -1), view)
            for index in range(1, count + 1)
        ]
        selected_bijection(identities, types, marks, own, selected_views, len(intended))
        self.identical(
            self.app.ActiveDoc, self.model(Document.DRAWING), "pre-command active model"
        )
        self.identical(
            self.draw().ActiveDrawingView, view, "pre-command active target view"
        )
        return {
            "intended": intended,
            "count": count,
            "identity_matrix": identities,
            "types": types,
            "marks": marks,
            "own_view": own,
            "selection_view": selected_views,
        }

    def apply(
        self,
        batches: tuple[tuple[bool, tuple[NodeId, ...]], ...],
        *,
        single: bool = False,
        injection: Injection = Injection.NONE,
    ) -> None:
        require(
            batches
            and all(
                keys
                and len(keys) == (1 if single else 2)
                and len(set(keys)) == len(keys)
                and all(key in LEAVES for key in keys)
                for _, keys in batches
            ),
            Verdict.SELECTION,
            "unplanned batch cardinality/node",
        )
        original_disable = self.flags()["A_disable"]
        with self.selection_guard() as manager:
            self.restore_a_update(True)
            for batch_index, (shown, keys) in enumerate(batches):
                with self.timed("selection"):
                    self.model(Document.DRAWING).ClearSelection2(True)
                    view, nodes = self.views()[ViewId.A]
                    data = self.bind(manager.CreateSelectData(), "ISelectData")
                    data.View, data.Mark = view, 0
                    if single:
                        require(
                            nodes[keys[0]].drawing_component.Select(False, data)
                            is True,
                            Verdict.SINGLE,
                            "documented single selection rejected",
                        )
                        self.receipt.counts["single_select"] += 1
                    else:
                        added = api_int(
                            manager.AddSelectionListObjects(
                                self.dispatches(
                                    tuple(nodes[key].drawing_component for key in keys)
                                ),
                                data,
                            ),
                            "AddSelectionListObjects",
                            Verdict.SELECTION,
                        )
                        self.receipt.counts["bulk_add"] += 1
                        require(
                            added == len(keys),
                            Verdict.SELECTION,
                            "partial bulk add; no command",
                        )
                    receipt = self.verify_batch(manager, keys)
                    self.receipt.data["cases"][self.receipt.case].setdefault(
                        "selections", []
                    ).append(receipt)
                print(
                    "BULK_VISIBILITY_SELECTED "
                    + json.dumps({"case": self.receipt.case, **receipt}),
                    flush=True,
                )
                self.receipt.checkpoint()
                if injection is Injection.AFTER_SELECTION:
                    raise InjectedFailure(self.receipt.case, injection)
                with self.timed("command"):
                    if shown:
                        self.model(Document.DRAWING).ShowComponent2()
                        self.receipt.counts["show"] += 1
                    else:
                        self.model(Document.DRAWING).HideComponent2()
                        self.receipt.counts["hide"] += 1
                for key in keys:
                    self.expected[ViewId.A][key] = shown
                effect_verdict = Verdict.SINGLE if single else Verdict.PLURAL
                self.checkpoint(
                    "post-command", changed=keys, effect_verdict=effect_verdict
                )
                self.restore_a_update(original_disable)
                self.rebuild()
                self.checkpoint(
                    "post-command-rebuild", changed=keys, effect_verdict=effect_verdict
                )
                effect = {
                    "case": self.receipt.case,
                    "batch": batch_index,
                    "consumed_nodes": list(keys),
                    "shown": shown,
                    "fresh_before_rebuild_and_after_rebuild": True,
                    "checkpoints": self.receipt.data["cases"][self.receipt.case][
                        "checkpoints"
                    ][-2:],
                }
                self.receipt.data["cases"][self.receipt.case].setdefault(
                    "effects", []
                ).append(effect)
                print("BULK_VISIBILITY_EFFECT " + json.dumps(effect), flush=True)
                self.receipt.checkpoint()
                if injection is Injection.BETWEEN_BATCHES and batch_index == 0:
                    raise InjectedFailure(self.receipt.case, injection)
                if batch_index + 1 < len(batches):
                    self.restore_a_update(True)

    def projected(self, point: Sequence[float], transform: Any) -> tuple[float, ...]:
        utility = self.bind(self.app.GetMathUtility(), "IMathUtility")
        native = self.bind(utility.CreatePoint(self.doubles(point)), "IMathPoint")
        projected = self.bind(native.MultiplyTransform(transform), "IMathPoint")
        values = array(projected.ArrayData, "projected point")
        require(
            len(values) == 3
            and all(
                type(value) in (int, float) and math.isfinite(value) for value in values
            ),
            Verdict.VISUAL,
            "invalid projected point",
        )
        return tuple(float(value) for value in values)

    def qualify_projection(self) -> None:
        projection = {}
        for view_id, (view, nodes) in self.views().items():
            transform = self.bind(view.ModelToViewTransform, "IMathTransform")
            origin = self.projected((0.0, 0.0, 0.0), transform)
            for vector, expected in (
                ((0.001, 0.0, 0.0), (0.005, 0.0)),
                ((0.0, 0.001, 0.0), (0.0, 0.005)),
                ((0.0, 0.0, 0.001), (0.0, 0.0)),
            ):
                point = self.projected(vector, transform)
                require(
                    all(
                        abs((point[i] - origin[i]) - expected[i]) <= 1e-9
                        for i in (0, 1)
                    ),
                    Verdict.VISUAL,
                    "Front projection axes/scale qualification failed",
                )
            rois, evidence = {}, {}
            for key in LEAVES:
                component_transform = self.bind(
                    nodes[key].component.Transform2, "IMathTransform"
                )
                root_point = self.projected((0.0, 0.0, 0.0), component_transform)
                centre = self.projected(root_point, transform)
                box = roi_box(centre, 0.008 if key in (NodeId.P1, NodeId.P2) else 0.020)
                require(
                    all(
                        box[2] <= prior[0]
                        or prior[2] <= box[0]
                        or box[3] <= prior[1]
                        or prior[3] <= box[1]
                        for prior in rois.values()
                    ),
                    Verdict.VISUAL,
                    "projected geometry ROIs overlap",
                )
                rois[key] = box
                evidence[key] = {
                    "centre": centre,
                    "roi": box,
                    "component_transform": matrix(
                        component_transform.ArrayData, "projection component matrix"
                    ),
                    "view_transform": matrix(
                        transform.ArrayData, "projection view matrix"
                    ),
                }
            self.rois[view_id] = rois
            projection[view_id] = evidence
        self.receipt.data["visual"] = {
            "projection": projection,
            "exports": {},
            "dpi": DPI,
            "mode": "RGB",
            "size": PAGE_SIZE,
            "renderer": "page.render(scale=300/72), defaults, white; RGB; right/bottom crop<=1",
        }
        self.baseline_cells: dict[tuple[ViewId, NodeId], bytes] = {}

    def image_account(
        self, *, buffers: int, width: int, height: int, retained_bytes: int = 0
    ) -> None:
        upper_bound = image_working_bytes(buffers, width, height, retained_bytes)
        self.receipt.data["image_buffer_high_water"] = max(
            self.receipt.data.get("image_buffer_high_water", 0), buffers
        )
        self.receipt.data["image_bytes_conservative_high_water"] = max(
            self.receipt.data.get("image_bytes_conservative_high_water", 0), upper_bound
        )

    def inspect_cells(
        self, export: Export, view_id: ViewId, image: Any
    ) -> dict[str, Any]:
        rows = {}
        prior_image = None
        if export is Export.REOPENED:
            from PIL import Image

            prior_image = Image.open(self.export_pages[Export.PERSISTED][view_id])
            require(
                prior_image.mode == "RGB",
                Verdict.VISUAL,
                "persisted raster mode changed",
            )
        try:
            for key, box in self.rois[view_id].items():
                with image.crop(box) as crop:
                    data, size = crop.tobytes(), crop.size
                if export is Export.BASELINE:
                    evidence = validate_rgb_cell(data, size, baseline=None)
                    self.baseline_cells[view_id, key] = data
                elif export is Export.REOPENED:
                    with prior_image.crop(box) as crop:
                        evidence = validate_rgb_cell(
                            data, size, baseline=crop.tobytes()
                        )
                else:
                    empty = view_id is ViewId.A and (
                        export is Export.HIDDEN
                        and key in (NodeId.P1, NodeId.P2)
                        or export is Export.PERSISTED
                        and key in (NodeId.P1, NodeId.P2, NodeId.Q1)
                    )
                    evidence = validate_rgb_cell(
                        data,
                        size,
                        baseline=self.baseline_cells[view_id, key],
                        hidden=empty,
                    )
                rows[key] = evidence
        finally:
            if prior_image is not None:
                prior_image.close()
        return rows

    def render_export(self, export: Export, pdf: Path) -> None:
        import importlib.metadata
        import pypdfium2 as pdfium
        from pypdf import PdfReader

        self.tick()
        reader = PdfReader(str(pdf))
        require(
            len(reader.pages) == 2, Verdict.VISUAL, "PDF did not export both sheets"
        )
        page_ids = {}
        for index, page in enumerate(reader.pages):
            require(
                int(page.get("/Rotate", 0)) == 0, Verdict.VISUAL, "rotated PDF page"
            )
            for box in (page.mediabox, page.cropbox):
                require(
                    abs(float(box.left)) <= 1e-9
                    and abs(float(box.bottom)) <= 1e-9
                    and abs(float(box.width) - 1224.0) <= 72.0 / DPI + 1e-6
                    and abs(float(box.height) - 792.0) <= 72.0 / DPI + 1e-6,
                    Verdict.VISUAL,
                    "PDF MediaBox/CropBox projection premise",
                )
            text = "".join(page.extract_text().split())
            matches = [
                view_id
                for view_id in ViewId
                if text.count(f"BULKVIS-{view_id.name}-{self.receipt.root.name}") == 1
            ]
            require(
                len(matches) == 1 and matches[0] not in page_ids.values(),
                Verdict.VISUAL,
                "missing/duplicate/ambiguous PDF page marker",
            )
            other = ViewId.B if matches[0] is ViewId.A else ViewId.A
            require(
                f"BULKVIS-{other.name}-{self.receipt.root.name}" not in text,
                Verdict.VISUAL,
                "both sheet markers on one PDF page",
            )
            page_ids[index] = matches[0]
        require(
            set(page_ids.values()) == set(ViewId),
            Verdict.VISUAL,
            "incomplete PDF page IDs",
        )
        from pypdfium2.version import PDFIUM_INFO, PYPDFIUM_INFO

        self.receipt.data["visual"]["library_versions"] = {
            "pypdfium2": PYPDFIUM_INFO.version,
            "pdfium": PDFIUM_INFO.version,
            "Pillow": importlib.metadata.version("Pillow"),
            "pypdf": importlib.metadata.version("pypdf"),
        }
        self.export_pages[export] = {}
        cells = {}
        document = pdfium.PdfDocument(str(pdf))
        try:
            require(len(document) == 2, Verdict.VISUAL, "renderer page count differs")
            for index in range(2):
                self.tick()
                page = document[index]
                bitmap = pil = image = None
                try:
                    require(
                        abs(float(page.get_width()) - 1224.0) <= 72.0 / DPI + 1e-6
                        and abs(float(page.get_height()) - 792.0) <= 72.0 / DPI + 1e-6,
                        Verdict.VISUAL,
                        "renderer page geometry differs",
                    )
                    retained = sum(len(data) for data in self.baseline_cells.values())
                    self.image_account(
                        buffers=3, width=5101, height=3301, retained_bytes=retained
                    )
                    bitmap = page.render(scale=DPI / 72.0)
                    pil = bitmap.to_pil()
                    image = pil.convert("RGB")
                    pil.close()
                    pil = None
                    bitmap.close()
                    bitmap = None
                    require(
                        image.size[0] in (5100, 5101) and image.size[1] in (3300, 3301),
                        Verdict.VISUAL,
                        "unexpected full-page raster dimensions",
                    )
                    if image.size != PAGE_SIZE:
                        cropped = image.crop((0, 0, *PAGE_SIZE))
                        image.close()
                        image = cropped
                    view_id = page_ids[index]
                    cells[view_id] = self.inspect_cells(export, view_id, image)
                    path = self.receipt.path(f"{export}-{view_id.name}.png")
                    require(not path.exists(), Verdict.VISUAL, "raster overwrite")
                    image.save(path, dpi=(DPI, DPI))
                    self.receipt.artifact(path, "full_page_png")
                    self.export_pages[export][view_id] = path
                    self.receipt.counts["page_render"] += 1
                finally:
                    if image is not None:
                        image.close()
                    if pil is not None:
                        pil.close()
                    if bitmap is not None:
                        bitmap.close()
                    page.close()
        finally:
            document.close()
        self.receipt.data["visual"]["exports"][export] = {
            "pdf": pdf.name,
            "page_ids": page_ids,
            "cells": cells,
        }
        if export is not Export.BASELINE:
            self.overlay(
                Export.PERSISTED if export is Export.REOPENED else Export.BASELINE,
                export,
            )

    def overlay(self, before: Export, after: Export) -> None:
        from PIL import Image
        import numpy as np

        for view_id in ViewId:
            self.tick()
            self.image_account(
                buffers=3,
                width=5100,
                height=3300,
                retained_bytes=sum(len(data) for data in self.baseline_cells.values()),
            )
            with (
                Image.open(self.export_pages[before][view_id]) as first,
                Image.open(self.export_pages[after][view_id]) as second,
                Image.new("RGB", PAGE_SIZE, "white") as result,
            ):
                require(
                    first.mode == second.mode == "RGB"
                    and first.size == second.size == PAGE_SIZE,
                    Verdict.VISUAL,
                    "overlay source mode/dimension mismatch",
                )
                for top in range(0, PAGE_SIZE[1], 4):
                    bottom = min(top + 4, PAGE_SIZE[1])
                    with (
                        first.crop((0, top, PAGE_SIZE[0], bottom)) as a_crop,
                        second.crop((0, top, PAGE_SIZE[0], bottom)) as b_crop,
                    ):
                        a, b = np.asarray(a_crop), np.asarray(b_crop)
                        same = np.all(a == b, axis=2)
                        ink_a, ink_b = np.any(a < 250, axis=2), np.any(b < 250, axis=2)
                        pixels = np.full_like(a, 255)
                        pixels[(ink_a | ink_b) & same] = (144, 144, 144)
                        pixels[ink_a & ~same] = (220, 0, 0)
                        pixels[ink_b & ~same] = (0, 70, 230)
                        with Image.fromarray(pixels) as tile:
                            result.paste(tile, (0, top))
                path = self.receipt.path(
                    f"{before}-vs-{after}-{view_id.name}-overlay.png"
                )
                require(not path.exists(), Verdict.VISUAL, "overlay overwrite")
                result.save(path, dpi=(DPI, DPI))
                self.receipt.artifact(path, "full_page_red_blue_overlay")
                self.receipt.counts["overlay"] += 1

    def export(self, export: Export) -> None:
        self.tick()
        pdf = self.receipt.path(f"{export}.pdf")
        require(not pdf.exists(), Verdict.VISUAL, "PDF overwrite refused")
        self.checkpoint(f"{export}-before-export")
        print(f"BULK_VISIBILITY_EXPORT {self.receipt.case} {export}", flush=True)
        with self.selection_guard():
            self.model(Document.DRAWING).ClearSelection2(True)
            with self.timed("export"):
                extension = self.bind(
                    self.model(Document.DRAWING).Extension, "IModelDocExtension"
                )
                drawing = self.draw()
                self._require_drawing_sheet_mode(
                    drawing,
                    self.drawing_mode_record["exports"][export],
                    verdict=Verdict.VISUAL,
                )
                result = extension.SaveAs3(str(pdf), 0, 1, None, None, 0, 0)
                require(
                    isinstance(result, tuple)
                    and len(result) == 3
                    and result[0] is True
                    and type(result[1]) is int
                    and type(result[2]) is int
                    and result[1] == result[2] == 0,
                    Verdict.VISUAL,
                    f"all-sheet PDF export failed: {result!r}",
                )
                self.receipt.counts["pdf_export"] += 1
                self.receipt.artifact(pdf, "all_page_pdf")
        self.checkpoint(f"{export}-after-export")
        with self.timed("render"):
            self.render_export(export, pdf)
        self.receipt.checkpoint()

    def visual_case(self) -> None:
        self.qualify_projection()
        self.export(Export.BASELINE)
        self.export(Export.REPEAT)  # Untouched, identical export/restore route.
        self.apply(((False, (NodeId.P1, NodeId.P2)),))
        self.export(Export.HIDDEN)
        self.apply(((True, (NodeId.P1, NodeId.P2)),))
        self.export(Export.SHOWN)

    def open_saved_drawing(self) -> None:
        path = self.paths[Document.DRAWING]
        require(
            path.is_file() and self.app.GetOpenDocumentByName(str(path)) is None,
            Verdict.CONSTRUCTION,
            "persisted drawing missing/already resident",
        )
        with self.acquiring(Document.DRAWING) as before:
            result = self.app.OpenDoc6(str(path), 3, 1, "", 0, 0)
            raw = result[0] if isinstance(result, tuple) and result else None
            self.acquired(Document.DRAWING, raw, before)
            checked_tuple(result, "open saved fixture drawing", save=False)
            self.claim(Document.DRAWING, 3, path)
        self.receipt.counts["drawing_reopen"] += 1
        self.activate(Document.DRAWING)
        self.views()
        self.identity_controls()
        require(
            self.flags() == self.harness_flags,
            Verdict.PRESERVATION,
            "persisted drawing update/graphics/tree flags changed",
        )

    def persistence_case(self) -> None:
        self.setup_visibility({NodeId.N: False}, rebuild=False)
        self.rebuild()  # Existing C06 post-set/pre-save rebuild, not one of seven setup rebuilds.
        self.checkpoint("before-drawing-copy-save")
        self.save_native(Document.DRAWING, Document.DRAWING, 27)
        self.saved_drawing_hash = sha256(self.paths[Document.DRAWING])
        self.checkpoint("after-drawing-copy-save")
        self.export(Export.PERSISTED)
        self.close_all_owned()
        self.receipt.counts["full_empty_interval"] += 1
        self.source_checkpoint("persistence-empty-interval")
        for label in (Document.P, Document.Q, Document.N, Document.R):
            self.open_source(label)
        self.classify_root()
        self.source_checkpoint("persistence-fresh-source-admission")
        self.open_saved_drawing()
        self.checkpoint("persistence-fresh-drawing")
        self.export(Export.REOPENED)
        self.receipt.data["persistence"] = {
            "drawing": str(self.paths[Document.DRAWING]),
            "sha256": self.saved_drawing_hash,
            "fresh_generations": dict(self.generations),
            "true_empty_interval": True,
        }

    def family_action(self, requested: frozenset[Family]) -> None:
        nodes = {key: node.state for key, node in self.views()[ViewId.A][1].items()}
        hide, show = plan_families(nodes, requested)
        batches = tuple(
            (shown, keys) for shown, keys in ((False, hide), (True, show)) if keys
        )
        if batches:
            self.apply(batches)
        else:
            self.receipt.data["cases"][self.receipt.case]["candidate_noop"] = True

    def wrong_view_request(self) -> None:
        views = self.views()
        requested = views[ViewId.B][1][NodeId.P1].drawing_component
        if (
            self.same(
                self.bind(requested, "IDrawingComponent").View, views[ViewId.A][0]
            )
            != 1
        ):
            raise PrewriteRefusal(
                "requested drawing component belongs to B, target is A"
            )
        raise ProbeFailure(
            Verdict.SELECTION,
            "wrong-view negative control unexpectedly authenticated A",
        )

    def case_checkpoint(self, label: str) -> None:
        if Document.DRAWING in self.documents:
            self.checkpoint(label)
        else:
            with self.timed("readback"):
                self.receipt.observe(
                    SnapshotKind.FULL,
                    label,
                    {"drawing": {"not_loaded": True}, "source": self.sources()},
                )
            self.receipt.checkpoint()

    def run_case(
        self,
        case: Case,
        action: Callable[[], None],
        *,
        setup: Mapping[NodeId, bool] | None = None,
        flag_overrides: Mapping[str, bool] | None = None,
        marked: bool = False,
        sheet_only: bool = False,
        expected_refusal: bool = False,
        expected_injection: Injection = Injection.NONE,
        discard_partial: bool = False,
    ) -> None:
        with self.telemetry.span(
            "probe.bulk_visibility.case", case=case, stage=self.receipt.stage
        ):
            self.case_body(
                case,
                action,
                setup=setup,
                flag_overrides=flag_overrides,
                marked=marked,
                sheet_only=sheet_only,
                expected_refusal=expected_refusal,
                expected_injection=expected_injection,
                discard_partial=discard_partial,
            )

    def case_body(
        self,
        case: Case,
        action: Callable[[], None],
        *,
        setup: Mapping[NodeId, bool] | None = None,
        flag_overrides: Mapping[str, bool] | None = None,
        marked: bool = False,
        sheet_only: bool = False,
        expected_refusal: bool = False,
        expected_injection: Injection = Injection.NONE,
        discard_partial: bool = False,
    ) -> None:
        self.receipt.case = case
        row = self.receipt.data["cases"][case]
        row["status"], row["candidate_entered"] = Verdict.RUNNING, False
        before = self.receipt.counts.copy()
        secondary_before = len(self.receipt.data["secondary_errors"])
        prepared_flags: dict[str, bool] | None = None
        primary: BaseException | None = None
        print(f"BULK_VISIBILITY_CASE {self.receipt.stage} {case} start", flush=True)
        self.receipt.checkpoint()
        try:
            if discard_partial:
                self.prepare_between()
            if setup:
                self.setup_visibility(setup)
            if flag_overrides:
                prepared_flags = self.flags()
                self.set_flags({**prepared_flags, **flag_overrides})
            if case not in (Case.CONSTRUCTION, Case.PERSISTENCE, Case.CLEANUP):
                self.prepare_context(marked=marked, sheet_only=sheet_only)
            if case is not Case.CONSTRUCTION:
                self.case_checkpoint("case-fresh-precondition")
            row["candidate_start_counts"] = dict(self.receipt.counts)
            candidate_before = self.receipt.counts.copy()
            row["candidate_entered"] = True
            try:
                action()
                require(
                    not expected_refusal and expected_injection is Injection.NONE,
                    Verdict.PRESERVATION,
                    "required negative control did not occur",
                )
                row["status"] = Verdict.PASSED
            except PrewriteRefusal as error:
                if not expected_refusal:
                    raise
                row["status"], row["expected_error"] = (
                    Verdict.REFUSAL,
                    error_record(error),
                )
            except InjectedFailure as error:
                if error.case is not case or error.point is not expected_injection:
                    raise
                if len(self.receipt.data["secondary_errors"]) != secondary_before:
                    row["status"] = Verdict.RESTORATION
                    raise
                row["status"], row["expected_error"] = (
                    Verdict.INJECTED,
                    error_record(error),
                )
            require(
                len(self.receipt.data["secondary_errors"]) == secondary_before,
                Verdict.RESTORATION,
                "negative control has secondary restoration/report failure",
            )
            row["candidate_operation_counts"] = {
                key: self.receipt.counts[key] - candidate_before[key]
                for key in (
                    "hide",
                    "show",
                    "bulk_add",
                    "single_select",
                    "selection_guard",
                    "rebuild",
                    "harness_setup_rebuild",
                    "setup_scalar_visibility",
                    "candidate_scalar_visibility",
                )
            }
            if case is Case.NO_CHANGE or expected_refusal:
                require(
                    not any(row["candidate_operation_counts"].values()),
                    Verdict.PRESERVATION,
                    "no-change/refusal candidate performed a mutation",
                )
            self.case_checkpoint("case-candidate-complete")
        except BaseException as error:
            primary = error
            if row["status"] is not Verdict.RESTORATION:
                row["status"] = failure_verdict(error)
            row["error"] = error_record(error)
            self.receipt.failure(error)
            raise
        finally:
            try:
                if prepared_flags is not None and Document.DRAWING in self.documents:
                    self.set_flags(prepared_flags)
                if discard_partial and Document.DRAWING in self.documents:
                    self.disk_snapshot()
                    self.close(Document.DRAWING)
                    self.receipt.counts["partial_drawing_discard"] += 1
                if primary is None:
                    if prepared_flags is not None or discard_partial:
                        self.case_checkpoint("case-harness-restored")
                    else:
                        row["coalesced_harness_checkpoint"] = row["checkpoints"][-1]
            except BaseException as restore:
                if primary is None:
                    primary = restore
                    row["status"] = Verdict.RESTORATION
                    row["error"] = error_record(restore)
                    self.receipt.failure(restore)
                    raise
                primary.add_note(f"case harness restoration also failed: {restore!r}")
                self.receipt.failure(restore, secondary=True)
            finally:
                row["operation_counts"] = dict(self.receipt.counts - before)
                try:
                    self.receipt.checkpoint()
                    print(f"BULK_VISIBILITY_CASE {case} {row['status']}", flush=True)
                except BaseException as report_error:
                    if primary is None:
                        row["status"] = failure_verdict(report_error)
                        row["error"] = error_record(report_error)
                        self.receipt.failure(report_error)
                        raise
                    primary.add_note(
                        f"case final checkpoint/log also failed: {report_error!r}"
                    )
                    self.receipt.failure(report_error, secondary=True)

    def stage(self, stage: Stage) -> None:
        self.receipt.stage, self.receipt.stage_started = stage, self.receipt.clock()
        self.receipt.data["stages"][stage] = {
            "status": Verdict.RUNNING,
            "started_seconds": self.receipt.stage_started - self.receipt.started,
        }
        self.receipt.checkpoint()

    def stage_passed(self) -> None:
        self.tick()
        row = self.receipt.data["stages"][self.receipt.stage]
        row["status"], row["seconds"] = (
            Verdict.PASSED,
            self.receipt.clock() - self.receipt.stage_started,
        )
        self.receipt.checkpoint()

    @contextmanager
    def stage_scope(self, stage: Stage) -> Iterator[None]:
        self.stage(stage)
        try:
            with self.telemetry.span("probe.bulk_visibility.stage", stage=stage):
                yield
                self.stage_passed()
        except BaseException as error:
            self.receipt.data["stages"][stage].update(
                status=failure_verdict(error),
                reason=str(error),
                seconds=self.receipt.clock() - self.receipt.stage_started,
            )
            raise

    def prepare_between(self) -> None:
        self.close(Document.DRAWING)
        self.expected[ViewId.A] = {key: key is not NodeId.N for key in NodeId}
        self.open_saved_drawing()
        self.receipt.counts["exception_drawing_reopen"] += 1

    def cleanup(self) -> None:
        self.mode = RunMode.CLEANUP
        self.receipt.data["cleanup"] = {"status": Verdict.RUNNING, "attempted": True}
        # Verify loaded native sources before discarding, and disk identities after.
        errors = []
        for operation in (
            self.sources,
            self.close_all_owned,
            lambda: self.source_checkpoint("cleanup-final-empty-and-source-disk"),
        ):
            try:
                operation()
            except BaseException as error:
                errors.append(error)
        self.receipt.data["cleanup"] = {
            "status": Verdict.RESTORATION if errors else Verdict.PASSED,
            "attempted": True,
            "remaining_owned": sorted(self.acquisitions),
            "errors": [error_record(error) for error in errors],
        }
        if errors:
            for error in errors[1:]:
                errors[0].add_note(f"another cleanup step failed: {error!r}")
            raise errors[0]
        self.receipt.data["cleanup"].update(
            inventory_empty=True, active_doc_null=True, source_disk=self.disk_snapshot()
        )

    def run(self) -> None:
        pins = (NodeId.P1, NodeId.P2)
        qs = (NodeId.Q1, NodeId.Q2)
        pair = ((False, pins), (True, pins))
        with self.stage_scope(Stage.CONSTRUCTION):
            self.run_case(Case.CONSTRUCTION, self.construct)
        with self.stage_scope(Stage.FUNDAMENTAL):
            self.run_case(
                Case.SINGLE_HIDE,
                lambda: self.apply(((False, (NodeId.P1,)),), single=True),
            )
            self.run_case(
                Case.SINGLE_SHOW,
                lambda: self.apply(((True, (NodeId.P1,)),), single=True),
            )
            self.run_case(Case.BULK_HIDE, lambda: self.apply(((False, pins),)))
            self.run_case(Case.BULK_SHOW, lambda: self.apply(((True, pins),)))
            self.receipt.data["stages"][Stage.FUNDAMENTAL]["observed_capability"] = {
                "documented_single_hide_show": True,
                "exact_two_object_hide_show": True,
            }
        with self.stage_scope(Stage.VISUAL):
            self.run_case(Case.VISUAL, self.visual_case)
            self.run_case(Case.PERSISTENCE, self.persistence_case)
        with self.stage_scope(Stage.EXTENDED):
            self.run_case(
                Case.CROSS_FAMILY,
                lambda: self.apply(
                    ((False, (NodeId.P1, NodeId.Q2)), (True, (NodeId.P1, NodeId.Q2)))
                ),
                setup={NodeId.N: True},
            )
            self.run_case(
                Case.MIXED,
                lambda: self.family_action(frozenset((Family.P,))),
                setup={NodeId.P1: False, NodeId.P2: False},
            )
            self.run_case(
                Case.HIDDEN_ANCESTOR,
                lambda: self.apply(pair),
                setup={NodeId.N: False, NodeId.Q1: True, NodeId.Q2: True},
            )
            self.run_case(
                Case.INHERITED_REFUSAL,
                lambda: self.family_action(frozenset((Family.P,))),
                expected_refusal=True,
            )
            self.run_case(
                Case.MISSING_REFUSAL,
                lambda: self.family_action(frozenset((Family.MISSING,))),
                expected_refusal=True,
            )
            self.run_case(
                Case.NO_CHANGE,
                lambda: self.family_action(frozenset((Family.Q,))),
                setup={NodeId.N: True, NodeId.P1: False, NodeId.P2: False},
            )
            self.run_case(
                Case.MARKED_VIEW,
                lambda: self.apply(pair),
                marked=True,
                setup={NodeId.P1: True, NodeId.P2: True},
            )
            self.run_case(Case.SHEET_CONTEXT, lambda: self.apply(pair), sheet_only=True)
            self.run_case(
                Case.WRONG_VIEW, self.wrong_view_request, expected_refusal=True
            )
            for case, disabled, automatic in (
                (Case.FLAGS_00, False, False),
                (Case.FLAGS_01, False, True),
                (Case.FLAGS_10, True, False),
                (Case.FLAGS_11, True, True),
            ):
                self.run_case(
                    case,
                    lambda: self.apply(pair),
                    flag_overrides={
                        "A_disable": disabled,
                        "B_disable": not disabled,
                        "automatic": automatic,
                    },
                )
            for success, failure, enabled in (
                (Case.GRAPHICS_ENABLED, Case.GRAPHICS_ENABLED_EXCEPTION, True),
                (Case.GRAPHICS_DISABLED, Case.GRAPHICS_DISABLED_EXCEPTION, False),
            ):
                vector = {
                    "A_disable": not enabled,
                    "graphics": enabled,
                    "tree": enabled,
                    "tree_window": enabled,
                }
                self.run_case(
                    success,
                    lambda: self.apply(pair),
                    marked=True,
                    flag_overrides=vector,
                )
                self.run_case(
                    failure,
                    lambda: self.apply(
                        ((False, pins),), injection=Injection.AFTER_SELECTION
                    ),
                    marked=True,
                    flag_overrides=vector,
                    expected_injection=Injection.AFTER_SELECTION,
                )
            for case, disabled in (
                (Case.EXCEPTION_ENABLED, False),
                (Case.EXCEPTION_DISABLED, True),
            ):
                self.run_case(
                    case,
                    lambda: self.apply(
                        ((False, pins),), injection=Injection.AFTER_SELECTION
                    ),
                    marked=True,
                    flag_overrides={"A_disable": disabled},
                    expected_injection=Injection.AFTER_SELECTION,
                )
            self.run_case(
                Case.NESTED_SELECTION, self.nested_selection_case, marked=True
            )
            for case, disabled in (
                (Case.BETWEEN_ENABLED, False),
                (Case.BETWEEN_DISABLED, True),
            ):
                self.run_case(
                    case,
                    lambda: self.apply(
                        ((False, qs), (True, pins)), injection=Injection.BETWEEN_BATCHES
                    ),
                    setup={NodeId.N: True, NodeId.P1: False, NodeId.P2: False},
                    marked=True,
                    flag_overrides={"A_disable": disabled},
                    expected_injection=Injection.BETWEEN_BATCHES,
                    discard_partial=True,
                )
        with self.stage_scope(Stage.CLEANUP):
            self.mode = RunMode.CLEANUP
            self.run_case(Case.CLEANUP, self.cleanup)
            expected_counts = {
                "hide": 16,
                "show": 14,
                "bulk_add": 33,
                "single_select": 2,
                "marked_select": 20,
                "setup_scalar_visibility": 18,
                "harness_setup_rebuild": 7,
                "native_copy_save": 3,
                "pdf_export": 6,
                "page_render": 12,
                "overlay": 10,
                "full_empty_interval": 2,
                "drawing_reopen": 3,
                "exception_drawing_reopen": 2,
                "partial_drawing_discard": 2,
                "placement": 5,
            }
            require(
                all(
                    self.receipt.counts[key] == value
                    for key, value in expected_counts.items()
                ),
                Verdict.PRESERVATION,
                f"expanded operation manifest differs: {dict(self.receipt.counts)}",
            )
            require(
                all(
                    row["status"] in (Verdict.PASSED, Verdict.REFUSAL, Verdict.INJECTED)
                    for row in self.receipt.data["cases"].values()
                ),
                Verdict.PRESERVATION,
                "mandatory case unexecuted/incomplete",
            )
            require(
                not self.receipt.data["secondary_errors"],
                Verdict.RESTORATION,
                "secondary error blocks controls_passed",
            )
        self.receipt.data["probe_controls_status"] = Controls.PASSED
        self.receipt.data["handoff_allowed"] = True


def rgb_evidence(data: bytes, width: int, height: int) -> dict[str, Any]:
    """Fixed ink/border evidence; accepts actual RGB bytes, no image/COM mock."""
    require(
        type(width) is int
        and type(height) is int
        and width >= 5
        and height >= 5
        and len(data) == width * height * 3,
        Verdict.VISUAL,
        "invalid RGB cell dimensions/length",
    )
    dark = sum(
        data[index] <= 224 and data[index + 1] <= 224 and data[index + 2] <= 224
        for index in range(0, len(data), 3)
    )
    border = True
    for y in range(height):
        ranges = (
            ((0, width),) if y < 2 or y >= height - 2 else ((0, 2), (width - 2, width))
        )
        for left, right in ranges:
            if any(
                value != 255
                for value in data[(y * width + left) * 3 : (y * width + right) * 3]
            ):
                border = False
    return {
        "dark_pixels": dark,
        "white_border": border,
        "all_white": all(value == 255 for value in data),
        "sha256": hashlib.sha256(data).hexdigest(),
        "size": (width, height),
    }


def image_working_bytes(
    buffers: int, width: int, height: int, retained_bytes: int = 0
) -> int:
    """Conservative decoded buffers plus the bounded aggregate row-tile reserve."""
    require(
        all(type(value) is int for value in (buffers, width, height, retained_bytes))
        and 1 <= buffers <= 3
        and 0 < width <= 5101
        and 0 < height <= 3301
        and retained_bytes >= 0,
        Verdict.VISUAL,
        "decoded-image dimensions/buffer ceiling",
    )
    upper_bound = buffers * width * height * 4 + retained_bytes + 1024 * 1024
    require(
        upper_bound <= MAX_IMAGE_BYTES, Verdict.VISUAL, "decoded-image byte ceiling"
    )
    return upper_bound


def validate_rgb_cell(
    data: bytes, size: tuple[int, int], *, baseline: bytes | None, hidden: bool = False
) -> dict[str, Any]:
    """The actual native-raster oracle, shared with pure byte-level edge tests."""
    evidence = rgb_evidence(data, *size)
    if baseline is None:
        require(
            not hidden and evidence["dark_pixels"] >= 256 and evidence["white_border"],
            Verdict.VISUAL,
            "unqualified empty/clipped/contaminated ink ROI",
        )
    elif hidden:
        require(evidence["all_white"], Verdict.VISUAL, "hidden component ink remains")
    else:
        require(
            data == baseline, Verdict.VISUAL, "baseline/restored/sentinel cell differs"
        )
    return evidence


def source_identity(root: Path) -> dict[str, Any]:
    """Read exact native-leaf metadata; never run at module import/test collection."""
    import subprocess

    require(
        os.environ.get("HARMONIC_BUILD_ORDER_SEED") == "farm"
        and os.environ.get("HARMONIC_SW_AUTOSTART") == "0",
        Verdict.CONSTRUCTION,
        "branch experiment is farm-only; no local native probe",
    )
    # One bounded read-only metadata invocation, not a status/build/cache check.
    environment = os.environ.copy()
    result = subprocess.run(
        [
            "git",
            "-c",
            "core.fsmonitor=false",
            "-c",
            f"core.hooksPath={os.devnull}",
            "-C",
            str(root),
            "rev-parse",
            "HEAD",
            "HEAD^{tree}",
        ],
        env=environment,
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    )
    values = result.stdout.splitlines()
    require(
        len(values) == 2
        and all(
            len(value) == 40 and all(char in "0123456789abcdef" for char in value)
            for value in values
        ),
        Verdict.CONSTRUCTION,
        "unreadable exact published commit/tree metadata",
    )
    commit, tree = values
    require(
        os.environ.get("HARMONIC_VERSION") == commit[:12],
        Verdict.CONSTRUCTION,
        "native leaf's worker-provided version does not match acquired head",
    )
    paths = (
        root / "cad/scripts/_bulk_visibility_contract_probe.py",
        root / "cad/scripts/draw_ch_channel_assembly.py",
        root / "dodo.py",
        root / "uv.lock",
        root
        / "SolidworksMCP-python/src/solidworks_mcp/adapters/_generated/sldworks_2026.py",
    )
    hashes = {str(path.relative_to(root)): sha256(path) for path in paths}
    return {
        "actual_commit": commit,
        "actual_tree": tree,
        "source_file_digests": hashes,
        "source_snapshot_digest": hashlib.sha256(
            json.dumps(hashes, sort_keys=True).encode()
        ).hexdigest(),
    }


async def run_bulk_visibility_probe(adapter: Any) -> None:
    """Existing leaf hook. Returns only after complete controls and owned cleanup."""
    root = Path(__file__).resolve().parents[2]
    parent = root / "cad/out/reports/failures/com-perf-bulk-visibility"
    for ancestor in (
        root,
        root / "cad",
        root / "cad/out",
        root / "cad/out/reports",
        root / "cad/out/reports/failures",
        parent,
    ):
        require(
            not ancestor.is_symlink() and not ancestor.is_junction(),
            Verdict.CONSTRUCTION,
            f"linked report ancestor refused: {ancestor}",
        )
    parent.mkdir(parents=True, exist_ok=True)
    directory = parent / uuid.uuid4().hex[:16]
    directory.mkdir()
    receipt = Receipt(directory)
    print(f"BULK_VISIBILITY_START {directory}", flush=True)
    probe: NativeProbe | None = None
    primary: BaseException | None = None
    with ExitStack() as native_scope:
        try:
            receipt.data["source_identity"] = source_identity(root)
            receipt.checkpoint()
            probe = NativeProbe(adapter, root, receipt)
            receipt.data["native_version"] = api_string(
                probe.app.RevisionNumber(), "native version"
            )
            native_scope.enter_context(
                probe.telemetry.span("probe.bulk_visibility", run_id=directory.name)
            )
            probe.run()
        except BaseException as error:
            primary = error
            receipt.failure(error)
            verdict = failure_verdict(error)
            case_row = receipt.data["cases"][receipt.case]
            if case_row["status"] in (Verdict.RUNNING, Verdict.PASSED):
                case_row["status"] = verdict
            if case_row["status"] is Verdict.RESTORATION:
                verdict = Verdict.RESTORATION
            receipt.data["stages"][receipt.stage].update(
                status=verdict, first_failed_case=receipt.case, reason=str(error)
            )
            receipt.data["probe_controls_status"] = (
                Controls.UNSUPPORTED
                if verdict in (Verdict.CONSTRUCTION, Verdict.IDENTITY, Verdict.VISUAL)
                else Controls.INTERRUPTED
                if verdict in (Verdict.INTERRUPTED, Verdict.DEADLINE)
                else Controls.FAILED
            )
            for row in receipt.data["cases"].values():
                if row["status"] is Verdict.NOT_EXECUTED:
                    row["reason"] = f"stopped at {receipt.case}: {error}"
            if probe is not None and not receipt.data.get("cleanup", {}).get(
                "attempted"
            ):
                receipt.case = Case.CLEANUP
                cleanup_row = receipt.data["cases"][Case.CLEANUP]
                cleanup_row.update(status=Verdict.RUNNING, candidate_entered=True)
                cleanup_row.pop("reason", None)
                before_cleanup = receipt.counts.copy()
                try:
                    probe.mode = RunMode.CLEANUP
                    with probe.stage_scope(Stage.CLEANUP):
                        with probe.telemetry.span(
                            "probe.bulk_visibility.case",
                            case=Case.CLEANUP,
                            stage=Stage.CLEANUP,
                        ):
                            probe.cleanup()
                    cleanup_row["status"] = Verdict.PASSED
                except BaseException as cleanup_error:
                    cleanup_row["status"] = failure_verdict(cleanup_error)
                    receipt.data["stages"][Stage.CLEANUP].update(
                        status=failure_verdict(cleanup_error), reason=str(cleanup_error)
                    )
                    receipt.data.setdefault("cleanup", {}).update(
                        status=failure_verdict(cleanup_error), attempted=True
                    )
                    error.add_note(f"owned cleanup also failed: {cleanup_error!r}")
                    receipt.failure(cleanup_error, secondary=True)
                finally:
                    cleanup_row["operation_counts"] = dict(
                        receipt.counts - before_cleanup
                    )
            elif probe is None:
                receipt.data["cleanup"] = {
                    "status": Verdict.NOT_EXECUTED,
                    "attempted": False,
                    "reason": "no native fixture construction entered",
                }
        finally:
            try:
                receipt.terminal()
            except BaseException as report_error:
                if primary is None:
                    raise
                primary.add_note(f"terminal report also failed: {report_error!r}")
                print(
                    f"BULK_VISIBILITY_TERMINAL_FAILED {directory} {report_error!r}",
                    flush=True,
                )
        if primary is not None:
            raise primary
        require(
            receipt.data["handoff_allowed"] is True,
            Verdict.PRESERVATION,
            "normal drawing blocked: controls/cleanup incomplete",
        )
