"""Opt-in drawing-only native-save experiment, never a production adapter mode.

Install this context BEFORE a source-boundary observer wraps common.save_drawing.
Only the native drawing call changes. PDF/PNG keep the adapter's legacy call
shape, order, artifact contexts and fresh-target behavior. The modern method's
Silent-only mask does not establish that referenced sources remain unwritten;
the caller must retain source/value/identity and cold-reopen witnesses.
"""

from contextlib import contextmanager, nullcontext
from enum import StrEnum
import os
from pathlib import Path
import time
from unittest.mock import patch

from solidworks_mcp.adapters.com_variant import null_dispatch
from solidworks_mcp.adapters.solidworks.drawing import _draw

from _common import _early_bound
import _drawing_common as common
import _telemetry


class DrawingSave(StrEnum):
    LEGACY = "legacy"
    EXTENSION_SILENT = "extension_silent"


def _artifacts(slddrw_path, pdf_path, png_path):
    rows = [("drawing", os.path.abspath(slddrw_path))]
    rows.extend(
        (kind, os.path.abspath(path))
        for kind, path in (("pdf", pdf_path), ("png", png_path))
        if path
    )
    native = Path(rows[0][1])
    expected = {"drawing": ".slddrw", "pdf": ".pdf", "png": ".png"}
    for kind, path in rows:
        target = Path(path)
        if target.suffix.lower() != expected[kind]:
            raise ValueError(
                f"diagnostic {kind} target has the wrong extension: {path}"
            )
        if target.parent.resolve() != native.parent.resolve():
            raise ValueError(
                "diagnostic exports must share the owned drawing directory"
            )
    if len({os.path.normcase(path) for _, path in rows}) != len(rows):
        raise ValueError("diagnostic artifact paths alias each other")
    return rows


def _file(path):
    if not path.is_file():
        return {"status": "absent"}
    return {"status": "present", "bytes": path.stat().st_size}


def _require_result(row, path):
    returned = row["returned"]
    if (
        not isinstance(returned, tuple)
        or len(returned) != 3
        or type(returned[0]) is not bool
        or type(returned[1]) is not int
        or type(returned[2]) is not int
    ):
        raise RuntimeError(
            f"modern SaveAs3 returned an invalid typed tuple: {returned!r}"
        )
    success, errors, warnings = returned
    row.update(errors=errors, warnings=warnings)
    if not success or errors:
        raise RuntimeError(f"modern SaveAs3 rejected drawing save: {returned!r}")
    if row["native_file"].get("bytes", 0) <= 0:
        raise RuntimeError(f"modern SaveAs3 produced no nonempty fresh file: {path}")
    actual = row["native_path_after"]
    if not actual or Path(actual).resolve() != path.resolve():
        raise RuntimeError(
            f"modern SaveAs3 did not reach exact drawing path: {actual!r}"
        )


def _modern_save(model, path, row):
    """Use makepy's typed DISPATCH nulls and returned [in,out] LONGs."""
    failures = []
    started = time.perf_counter()
    try:
        extension = _early_bound(model.Extension, "IModelDocExtension")
        with _telemetry.span("diagnostic.drawing_save.extension", path=str(path)):
            # IModelDocExtension.SaveAs3 DISPID315: BSTR,I4,I4,DISPATCH,
            # DISPATCH,[in,out] LONG,[in,out] LONG -> BOOL/errors/warnings.
            # CurrentVersion=0, Silent=1; SaveReferenced=4 is NOT set.
            row["returned"] = extension.SaveAs3(
                str(path), 0, 1, null_dispatch(), null_dispatch(), 0, 0
            )
    except Exception as error:
        failures.append(error)
    finally:
        row["native_call_seconds"] = time.perf_counter() - started
        for name, reader in (
            ("native_path_after", model.GetPathName),
            ("native_file", lambda: _file(path)),
        ):
            try:
                row[name] = reader()
            except Exception as error:
                failures.append(error)
    if len(failures) == 1:
        raise failures[0]
    if failures:
        raise ExceptionGroup("native save and readback failures", failures)
    _require_result(row, path)


def _save(
    adapter,
    slddrw_path,
    *,
    pdf_path=None,
    png_path=None,
    artifact_context=None,
    records,
):
    rows = _artifacts(slddrw_path, pdf_path, png_path)
    row = {
        "variant": DrawingSave.EXTENSION_SILENT.value,
        "status": "running",
        "path": rows[0][1],
        "failures": [],
        "version": 0,
        "options": 1,
        "export_data": "typed_null_dispatch",
        "advanced_options": "typed_null_dispatch",
    }
    records.append(row)
    failures, out = [], {}
    started = time.perf_counter()
    try:
        record = adapter.ownership.assert_current_owned()

        def require_current():
            if adapter.ownership.assert_current_owned() is not record:
                raise RuntimeError(
                    "owned document changed during drawing save observation"
                )

        draw = _draw(adapter)
        model = _early_bound(draw, "IModelDoc2")
        if model.GetType() != 3:
            raise RuntimeError("modern native save control requires an owned drawing")
        row["native_path_before"] = model.GetPathName()
        # Artifact observation brackets a complete authorized native rename.
        # Reconcile its inventory before observers or later exports read it.
        for kind, path in rows:
            context = (
                artifact_context(kind, path) if artifact_context else nullcontext()
            )
            with context:
                # Entry can perform native reads/checkpoints. Check afterwards,
                # before any stale deletion or active-document save/export.
                # Another owned document is not the cached draw/model above.
                require_current()
                save_scope = (
                    adapter.ownership.saving_as(path)
                    if kind == "drawing"
                    else nullcontext()
                )
                with save_scope:
                    try:
                        os.makedirs(os.path.dirname(path), exist_ok=True)
                        if os.path.exists(path):
                            os.remove(path)
                        if kind == "drawing":
                            _modern_save(model, Path(path), row)
                        if kind != "drawing":
                            draw.SaveAs3(path, 0, 0)
                        if not os.path.isfile(path):
                            raise RuntimeError(f"SaveAs3 produced no file: {path}")
                    except Exception as error:
                        failures.append(error)
                        raise
                require_current()
                out[kind] = path
        row["status"] = "passed"
        return out
    except Exception as error:
        if not any(error is existing for existing in failures):
            failures.append(error)
        row.update(status="failed", failures=[repr(item) for item in failures])
        if len(failures) > 1:
            raise ExceptionGroup(
                "drawing save and ownership failures", failures
            ) from None
        raise
    finally:
        row["seconds"] = time.perf_counter() - started


@contextmanager
def native_drawing_save_control(adapter, variant, *, records):
    """Scope a common.save_drawing alias; LEGACY does not patch anything.

    The caller owns the machine-global seat, exact PID and document lifecycle.
    Enter before SourceSaveBoundaries.observe(), exit after it. Only sibling
    output files in the registered owned drawing directory are authorized.
    Exceptions restore the original alias; there is no legacy retry/fallback.
    """
    if not isinstance(variant, DrawingSave):
        raise ValueError("native drawing save requires an explicit DrawingSave enum")
    if variant is DrawingSave.LEGACY:
        yield
        return

    def save(actual_adapter, *args, **kwargs):
        if actual_adapter is not adapter:
            raise RuntimeError("save control received a different owned adapter")
        return _save(adapter, *args, **kwargs, records=records)

    with patch.object(common, "save_drawing", save):
        yield
