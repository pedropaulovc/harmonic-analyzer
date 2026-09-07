"""One owned blank save/cold/print boundary, composed into the cache trial."""

from pathlib import Path

from _common import check
from diagnostics import probe_prepared_template_cache as cache


async def capture(adapter, spec, directory, trial, checkpoint):
    row = trial["cold"] = {"status": "running", "phase": "native_save"}
    path = (directory / "blank.SLDDRW").resolve()
    saved_hash = None
    errors = []
    try:
        cache.blank_witness(adapter)
        adapter.ownership.assert_current_owned()
        if path.exists():
            raise RuntimeError("blank native save requires a fresh owned target")
        with cache.timed(row, "save_seconds"), adapter.ownership.saving_as(path):
            model = adapter.currentModel
            model.ClearSelection2(True)
            row["save_result"] = model.SaveAs3(str(path), 0, 0)
            row["saved_path"] = str(model.GetPathName())
            # Existing proven legacy call shape: retain its integer, do not
            # invent an undocumented mapping to modern Options/status enums.
            if (
                type(row["save_result"]) is not int
                or not path.is_file()
                or path.stat().st_size == 0
                or Path(row["saved_path"]).resolve() != path
            ):
                raise RuntimeError(
                    "owned blank native save did not persist exact fresh path"
                )
        saved_hash = row["sha256_before"] = cache.prepared._sha(path)
        row["after_save_blank"] = cache.blank_witness(adapter, saved_path=path)
        row["after_save_defaults"] = cache.snapshot_defaults(adapter, spec)
        cache.compare_defaults(trial["defaults"], row["after_save_defaults"])
        row["phase"] = "cold_open"
        checkpoint()
        with cache.timed(row, "close_reopen_seconds"):
            await adapter.close_owned_documents()
            check("reopen owned blank", await adapter.open_model(str(path)))
        adapter.ownership.assert_current_owned()
        row["blank"] = cache.blank_witness(adapter, saved_path=path)
        reopened = adapter.currentModel
        row["viewport_before_restore"] = cache.viewports.capture(reopened)
        row["viewport_restore"] = {}
        with cache.timed(row, "viewport_restore_seconds"):
            adapter.ownership.assert_current_owned()
            if not cache.prepared._same(adapter.swApp, adapter.currentModel, reopened):
                raise RuntimeError(
                    "cold viewport restore lost the exact reopened drawing"
                )
            cache.blank_witness(adapter, saved_path=path)
            cache.viewports.restore(
                adapter.swApp, reopened, trial["viewport"], row["viewport_restore"]
            )
        row["phase"] = "cold_defaults"
        checkpoint()
        with cache.timed(row, "witness_seconds"):
            row["defaults"] = cache.snapshot_defaults(adapter, spec)
            cache.compare_defaults(trial["defaults"], row["defaults"])
        row["phase"] = "cold_print"
        checkpoint()
        printed_dir = directory / "cold"
        printed_dir.mkdir()
        adapter.ownership.register_directory(printed_dir)
        with cache.timed(row, "printed_seconds"):
            row["printed"] = cache.printed_witness(adapter, printed_dir)
            row["printed_delta"] = cache.compare_printed(
                trial["printed"], row["printed"]
            )
        row["after_print_defaults"] = cache.snapshot_defaults(adapter, spec)
        cache.compare_defaults(row["defaults"], row["after_print_defaults"])
        row["after_print_blank"] = cache.blank_witness(adapter, saved_path=path)
        row["after_print_viewport"] = cache.viewports.capture(adapter.currentModel)
        if row["after_print_viewport"] != trial["viewport"]:
            raise RuntimeError("cold printed trial changed the exact captured viewport")
    except Exception as error:
        row.update(error=repr(error), failed_phase=row["phase"])
        errors.append(error)
    finally:
        if saved_hash is not None:
            try:
                row["sha256_after"] = cache.prepared._sha(path)
                if row["sha256_after"] != saved_hash:
                    raise RuntimeError("saved blank changed during cold read/export")
            except Exception as error:
                row["final_hash_error"] = repr(error)
                errors.append(error)
        row["status"] = "failed" if errors else "passed"
        checkpoint()
    if errors:
        raise ExceptionGroup("owned blank save/cold comparison failed", errors)
