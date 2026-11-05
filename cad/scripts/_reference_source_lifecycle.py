"""Read-only supplier source lifecycle shared by purchased reference drawings.

Document activation, checked configuration transitions and the source-file
byte guard used around drawing finalization. Kept apart from any one drawing
family so a spring, chain or kit sheet's implementation never enters another
family's dependency closure.
"""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from typing import Any

from _com import _early_bound
import _telemetry
from _purchased_fastener_drawing import _source_file_sha256
from _rebuild import active_configuration_name


@contextmanager
def _preserve_reference_source_file(source: Path, expected_sha256: str, *, label: str):
    """Prove drawing finalization never persists presentation edits to the part."""
    primary: BaseException | None = None
    try:
        yield
    except BaseException as error:
        primary = error
        raise
    finally:
        try:
            if _source_file_sha256(source) != expected_sha256:
                raise RuntimeError(
                    f"{label}: supplier source part bytes changed during drawing finalization"
                )
        except BaseException as preservation_error:
            if primary is not None:
                primary.add_note(
                    f"{label}: supplier source file preservation also failed: {preservation_error!r}"
                )
            else:
                raise


def _reference_rebuild_status(model: Any, *, label: str) -> int:
    status = _early_bound(model.Extension, "IModelDocExtension").NeedsRebuild2
    # swModelRebuildStatus_e is an integer bitmask, not a Boolean property.
    if type(status) is not int or status not in (0, 1, 2, 3):
        raise RuntimeError(f"{label}: invalid native source rebuild status {status!r}")
    return status


def _activate_reference_document(adapter: Any, model: Any, *, label: str) -> None:
    # Generated ActivateDoc3 declares Errors [in,out] (16387, 3), unlike the
    # OUT-only GetErrorCode2. Supply its scalar seed and consume the return tuple.
    # swDontRebuildActiveDoc=1: only the checked source transition may rebuild.
    result = adapter.swApp.ActivateDoc3(str(model.GetTitle()), False, 1, 0)
    if (
        not isinstance(result, tuple)
        or len(result) != 2
        or result[0] is None
        or type(result[1]) is not int
        or result[1] not in (0, 2)
    ):
        raise RuntimeError(f"{label}: document activation failed: {result!r}")
    activated = _early_bound(result[0], "IModelDoc2")
    active = adapter.swApp.ActiveDoc
    if (
        active is None
        or int(adapter.swApp.IsSame(activated, model)) != 1
        or int(adapter.swApp.IsSame(active, model)) != 1
    ):
        raise RuntimeError(f"{label}: document activation changed native identity")
    adapter.currentModel = activated


def _show_reference_configuration(
    adapter: Any, model: Any, name: str, *, label: str
) -> None:
    before = active_configuration_name(adapter, model)
    status = _reference_rebuild_status(model, label=label)
    _telemetry.info(
        f"{label}: source transition before: configuration={before!r}; "
        f"requested={name!r}; dirty={bool(model.GetSaveFlag())!r}; needs_rebuild={status!r}"
    )
    if before != name and model.ShowConfiguration2(name) is not True:
        raise RuntimeError(f"{label}: cannot activate source configuration {name!r}")
    if active_configuration_name(adapter, model) != name:
        raise RuntimeError(
            f"{label}: source configuration readback differs from {name!r}"
        )
    status = _reference_rebuild_status(model, label=label)
    if status != 0 and model.EditRebuild3() is not True:
        raise RuntimeError(f"{label}: cannot rebuild source configuration {name!r}")
    status = _reference_rebuild_status(model, label=label)
    after = active_configuration_name(adapter, model)
    _telemetry.info(
        f"{label}: source transition after: configuration={after!r}; "
        f"requested={name!r}; dirty={bool(model.GetSaveFlag())!r}; needs_rebuild={status!r}"
    )
    if after != name or status != 0:
        raise RuntimeError(
            f"{label}: source configuration {name!r} did not settle after rebuilding"
        )
