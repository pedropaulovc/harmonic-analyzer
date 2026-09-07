"""Opt-in, content-addressed project DRWDOT materialization.

Call ``await prepare_project_drawing_template`` under the existing COM seat before
entering a recipe's drawing-creation scope. Construction only consumes a validated
entry; a missing/corrupt entry never falls back to another template or setup path.
No production recipe opts in until full-sheet native acceptance is complete.
"""

from contextlib import nullcontext
from dataclasses import asdict, dataclass
from enum import Enum
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import sys
import tempfile
import time

from _common import _early_bound, check
from _drawing_template_defaults import compare_defaults, snapshot_defaults
import _telemetry


class TemplateOperation(Enum):
    CREATE = "create"
    SAVE_AS = "save_as"


@dataclass(frozen=True)
class TemplateSpec:
    scale: tuple[float, float] = (1.0, 1.0)
    decimals: int = 2

    def __post_init__(self):
        if len(self.scale) != 2 or any(
            isinstance(n, bool) or not math.isfinite(n) or n <= 0 for n in self.scale
        ):
            raise ValueError("template scale requires two finite positive numbers")
        if type(self.decimals) is not int or self.decimals not in (2, 3):
            raise ValueError("prepared template precision must be 2 or 3")
        object.__setattr__(self, "scale", tuple(float(n) for n in self.scale))


@dataclass(frozen=True)
class PreparedTemplate:
    directory: Path
    key: str
    spec: TemplateSpec

    @property
    def path(self):
        return self.directory / "prepared.DRWDOT"


def _sha(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _json(value):
    return json.dumps(value, sort_keys=True, indent=2, allow_nan=False)


def preparation_inputs(adapter, spec):
    """Conservative complete module bytes, not a new function-level analyzer.

    Whole imported helper modules, adapter Python sources and config are included:
    unrelated edits inside those modules can over-invalidate preparation. Paths are
    checkout-relative; interpreter and exact native revision are explicit inputs.
    """
    import _drawing_common as common
    from _buildgraph import module_deps_of
    import solidworks_mcp

    root = Path(__file__).resolve().parents[2]
    entry = Path(common.__file__).resolve()
    # These are separate roots: CURRENT deliberately does not import PREPARED.
    # The second closure owns the raw validator and native measurement helpers.
    preparation_modules = (entry, Path(__file__).resolve())
    sources = set(preparation_modules)
    for preparation_module in preparation_modules:
        sources.update(Path(path) for path in module_deps_of(preparation_module))
    adapter_root = root / "SolidworksMCP-python/src/solidworks_mcp"
    if Path(solidworks_mcp.__file__).resolve().parent != adapter_root.resolve():
        raise RuntimeError(
            "prepared template requires this checkout's actual adapter source"
        )
    sources.update((root / "SolidworksMCP-python/src").rglob("*.py"))
    sources.update((root / "cad/config").rglob("*.yaml"))
    sources.update((root / "uv.lock", root / "pyproject.toml"))
    template = Path(common.PROJECT_DRWDOT).resolve(strict=True)
    if template.stat().st_size == 0:
        raise RuntimeError("original project drawing template is empty")
    revision = str(adapter.swApp.RevisionNumber())
    if not revision:
        raise RuntimeError("native SolidWorks revision is missing")
    return {
        "schema": 1,
        "template_sha256": _sha(template),
        "spec": json.loads(_json(asdict(spec))),
        "solidworks_revision": revision,
        "python": {
            "implementation": platform.python_implementation(),
            "version": sys.version,
            "architecture": platform.machine(),
        },
        "source_sha256": {
            path.relative_to(root).as_posix(): _sha(path) for path in sorted(sources)
        },
    }


def _key(inputs):
    return hashlib.sha256(_json(inputs).encode()).hexdigest()


def _read_entry(entry, inputs):
    try:
        manifest = json.loads(
            (entry.directory / "manifest.json").read_text(encoding="utf-8")
        )
        if (
            manifest["status"] != "validated"
            or manifest["inputs"] != inputs
            or manifest["key"] != entry.key
            or _key(inputs) != entry.key
        ):
            raise ValueError("manifest input identity differs")
        if not entry.path.is_file() or entry.path.stat().st_size == 0:
            raise ValueError("derived DRWDOT is missing or empty")
        if manifest["derived_sha256"] != _sha(entry.path):
            raise ValueError("derived DRWDOT hash differs")
        receipt = json.loads(
            (entry.directory / "receipt.json").read_text(encoding="utf-8")
        )
        if _sha(entry.directory / "receipt.json") != manifest["receipt_sha256"]:
            raise ValueError("validation receipt hash differs")
        if (
            receipt["status"] != "validated"
            or receipt["inputs"] != inputs
            or not receipt["before"]
            or not receipt["after"]
        ):
            raise ValueError("native validation receipt is incomplete")
        compare_defaults(receipt["before"], receipt["after"])
    except (OSError, ValueError, KeyError, TypeError, RuntimeError) as exc:
        raise RuntimeError(
            f"invalid prepared template entry {entry.directory}: {exc}"
        ) from exc
    return entry.path


def _seat():
    if not os.environ.get("HARMONIC_COM_SEAT"):
        raise RuntimeError(
            "prepared templates require the existing machine-global COM seat"
        )


def inherited_drawing(adapter, entry):
    """Verify then instantiate; no normalization, style setters or blank rebuilds."""
    import _drawing_common as common

    _seat()
    path = _read_entry(entry, preparation_inputs(adapter, entry.spec))
    draw = common.new_drawing(
        adapter,
        template=str(path),
        width=common.ASME_B_WIDTH_M,
        height=common.ASME_B_HEIGHT_M,
    )
    ddoc = _early_bound(draw, "IDrawingDoc")
    ddoc.EditSheet()
    sheet = _early_bound(ddoc.GetCurrentSheet(), "ISheet")
    if sheet is None:
        raise RuntimeError("prepared template returned no current sheet")
    common.assert_asme_b_sheet(
        adapter, sheet, phase="prepared setup", scale=entry.spec.scale
    )
    draw.ViewZoomtofit2()
    return draw, sheet


def _documents(app):
    return [_early_bound(raw, "IModelDoc2") for raw in app.GetDocuments() or ()]


def _state(model):
    path = str(model.GetPathName())
    return {
        "path": path,
        "title": str(model.GetTitle()),
        "kind": int(model.GetType()),
        "state": "dirty" if model.GetSaveFlag() else "clean",
        "visibility": "visible" if model.Visible else "hidden",
        "disk_sha256": _sha(path) if path else None,
    }


def _same(app, first, second):
    return (
        first is not None and second is not None and int(app.IsSame(first, second)) == 1
    )


def _verify_baseline(app, baseline, extra=()):
    current = _documents(app)
    if len(current) != len(baseline) + len(extra):
        raise RuntimeError("template preparation changed the document inventory")
    for model, state in baseline:
        matches = [item for item in current if _same(app, item, model)]
        if len(matches) != 1 or _state(matches[0]) != state:
            raise RuntimeError("template preparation changed a pre-existing document")
    for model in extra:
        if sum(_same(app, item, model) for item in current) != 1:
            raise RuntimeError("owned preparation drawing identity changed")


async def _prepare_native(adapter, spec, directory, receipt, operation_context):
    """Two owned blank documents; no borrowed source close/reopen or save."""
    import _drawing_common as common

    app = adapter.swApp
    baseline = [(model, _state(model)) for model in _documents(app)]
    if not baseline and not app.UserControl:
        raise RuntimeError(
            "cannot prepare in an empty background session: last CloseDoc can exit SolidWorks"
        )
    if any(state["visibility"] == "hidden" for _, state in baseline):
        raise RuntimeError(
            "prepare before opening hidden documents: CloseDoc can unload them"
        )
    previous = adapter.currentModel
    active = _early_bound(app.ActiveDoc, "IModelDoc2")
    if previous is not None and not any(
        _same(app, previous, model) for model, _ in baseline
    ):
        raise RuntimeError("adapter currentModel is not an open baseline document")
    receipt["baseline"] = [state for _, state in baseline]
    owned = None
    errors = []

    async def close_owned():
        nonlocal owned
        if owned is None:
            return
        _verify_baseline(app, baseline, [owned])
        if not _same(app, adapter.currentModel, owned) or not _same(
            app, app.ActiveDoc, owned
        ):
            raise RuntimeError("refusing to close an unexpected preparation document")
        check("close prepared drawing", await adapter.close_model(save=False))
        owned = None  # Never send the closed wrapper back to native code.
        _verify_baseline(app, baseline)

    path = directory / "prepared.DRWDOT"
    try:
        with operation_context(TemplateOperation.CREATE, path):
            owned, _ = common.new_project_drawing(
                adapter, scale=spec.scale, decimals=spec.decimals
            )
        _verify_baseline(app, baseline, [owned])
        receipt["before"] = snapshot_defaults(adapter, spec)
        with operation_context(TemplateOperation.SAVE_AS, path):
            if path.exists():
                raise RuntimeError("prepared template target must be fresh")
            owned.ClearSelection2(True)
            result = owned.SaveAs3(str(path), 0, 0)
            receipt["save_result"] = result
            receipt["saved_path"] = str(owned.GetPathName())
            # This complete legacy call shape has a committed native positive
            # control. Its integer Options is NOT the modern SaveAs flags enum.
            # Return integer is retained, not interpreted as an undocumented
            # status enum. Exact fresh path plus re-instantiated defaults gate it.
            if (
                type(result) is not int
                or not path.is_file()
                or path.stat().st_size == 0
            ):
                raise RuntimeError(
                    "prepared DRWDOT save did not succeed with a fresh file"
                )
            if Path(receipt["saved_path"]).resolve() != path:
                raise RuntimeError("prepared DRWDOT native path differs")
        await close_owned()
        with operation_context(
            TemplateOperation.CREATE, directory / "verification.SLDDRW"
        ):
            owned = common.new_drawing(
                adapter,
                template=str(path),
                width=common.ASME_B_WIDTH_M,
                height=common.ASME_B_HEIGHT_M,
            )
            ddoc = _early_bound(owned, "IDrawingDoc")
            ddoc.EditSheet()
            owned.ViewZoomtofit2()
        _verify_baseline(app, baseline, [owned])
        receipt["after"] = snapshot_defaults(adapter, spec)
        compare_defaults(receipt["before"], receipt["after"])
    except Exception as exc:
        errors.append(exc)
        # new_project_drawing assigns currentModel exactly once, inside its
        # new_drawing call, before normalization/style/rebuild operations. Those
        # later calls do not assign currentModel. Thus a failing setup leaves
        # the NewDocument-returned handle there. ActiveDoc alone is never proof:
        # require that adapter handle, absence from baseline, and the subsequent
        # exact baseline+one-created-document inventory before any close. A user
        # activation/reassignment or unexpected additional document stops cleanup.
        if owned is None:
            try:
                candidate = adapter.currentModel
                if (
                    candidate is not None
                    and not any(_same(app, candidate, model) for model, _ in baseline)
                    and _same(app, candidate, app.ActiveDoc)
                    and int(candidate.GetType()) == 3
                    and str(candidate.GetPathName()) == ""
                ):
                    owned = candidate
            except Exception as claim_error:
                receipt["partial_creation_claim_error"] = repr(claim_error)
                errors.append(claim_error)
    finally:
        try:
            await close_owned()
            _verify_baseline(app, baseline)
            if active is not None and not _same(app, app.ActiveDoc, active):
                # swDontRebuildActiveDoc=1; warning2 preserves a dirty baseline.
                restored, status = app.ActivateDoc3(str(active.GetTitle()), False, 1, 0)
                if status not in (0, 2) or not _same(app, restored, active):
                    raise RuntimeError("could not restore the original active document")
            adapter.currentModel = previous
            _verify_baseline(app, baseline)
            receipt["baseline_preserved"] = "exact_native_handles_and_state"
        except Exception as exc:
            receipt["cleanup_error"] = repr(exc)
            errors.append(exc)
    if errors:
        raise ExceptionGroup(
            "prepared template native operation/cleanup failed", errors
        )


async def prepare_project_drawing_template(
    adapter, *, scale=(1.0, 1.0), decimals=2, cache_root=None, operation_context=None
):
    """Prepare once, or verify an existing entry, under the caller's COM lock.

    ``operation_context(kind, exact_path)`` is optional. Owned-copy diagnostics
    supply their existing creating_document/saving_as scopes here; invoke this
    accessor BEFORE the recipe's outer creation scope. Default production calls
    use the narrow native inventory guard, not the diagnostic lifecycle framework.
    Failed staging directories/receipts are retained; no silent repair or retry.
    """
    _seat()
    spec = TemplateSpec(scale, decimals)
    inputs = preparation_inputs(adapter, spec)
    key = _key(inputs)
    root = (
        Path(cache_root)
        if cache_root is not None
        else Path(__file__).resolve().parents[1] / "out/prepared-drawing-templates"
    ).resolve()
    entry = PreparedTemplate(root / key, key, spec)
    if entry.directory.exists():
        with _telemetry.span("drawing.template.cache_hit", key=key):
            _read_entry(entry, inputs)
        return entry
    root.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix=f"pending-{key[:12]}-", dir=root))
    receipt = {"status": "preparing", "inputs": inputs}
    started = time.perf_counter()
    try:
        with _telemetry.span("drawing.template.prepare", key=key):
            await _prepare_native(
                adapter,
                spec,
                stage,
                receipt,
                operation_context or (lambda kind, path: nullcontext()),
            )
        if preparation_inputs(adapter, spec) != inputs:
            raise RuntimeError("template preparation inputs changed during native work")
        receipt["status"] = "validated"
    except Exception as exc:
        receipt.update(status="failed", error=repr(exc))
        raise
    finally:
        receipt["seconds"] = time.perf_counter() - started
        try:
            receipt["inputs_after"] = preparation_inputs(adapter, spec)
            if receipt["inputs_after"] != inputs:
                receipt["status"] = "failed"
                receipt["inputs_after_error"] = "input identity changed"
        except Exception as exc:
            receipt["status"] = "failed"
            receipt["inputs_after_error"] = repr(exc)
        (stage / "receipt.json").write_text(_json(receipt), encoding="utf-8")
    if receipt.get("inputs_after") != inputs:
        raise RuntimeError(
            "template preparation final input witness differs or is unreadable"
        )
    manifest = {
        "status": "validated",
        "key": key,
        "inputs": inputs,
        "derived_sha256": _sha(stage / "prepared.DRWDOT"),
        "receipt_sha256": _sha(stage / "receipt.json"),
    }
    (stage / "manifest.json").write_text(_json(manifest), encoding="utf-8")
    # The machine-global seat serializes native preparation and publication.
    # rename refuses an existing destination; never overwrite another entry.
    stage.rename(entry.directory)
    _read_entry(entry, inputs)
    return entry
