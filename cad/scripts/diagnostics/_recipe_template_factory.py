"""Opt-in factory selection for the owned full-recipe diagnostic only.

Both variants run the same loaded recipe and its complete existing acceptance
path. Materialization occurs before opening the owned part or entering the
recipe's drawing-creation scope. No shared helper/recipe globals are patched.
"""

import _drawing_sheet_setup as sheet_setup

from contextlib import contextmanager
from dataclasses import asdict
from enum import StrEnum
import os
from pathlib import Path
import time

import _drawing_prepared_template as prepared
from _drawing_build import normal_drawing_factory, prepared_drawing_factory
import _telemetry
from diagnostics import probe_datum_policy_recipes as pilot
from diagnostics.probe_prepared_template_cache import (
    cache_artifacts,
    require_environment,
)
from diagnostics._owned_native_documents import DocumentKind


class DrawingFactory(StrEnum):
    NORMAL = "normal"
    PREPARED = "prepared"


def require_factory_environment():
    try:
        expected_pid = int(os.environ.get("HARMONIC_DIAGNOSTIC_SW_PID", ""))
    except ValueError as error:
        raise RuntimeError(
            "factory control requires an explicit positive native PID"
        ) from error
    require_environment(expected_pid)


class RecipeTemplateFactory:
    def __init__(self, variant):
        if not isinstance(variant, DrawingFactory):
            raise ValueError("drawing factory requires an explicit variant enum")
        self.variant = variant
        self.inputs = {}
        self.initial = None
        self.row = None
        self.guards = {}

    async def configure(self, adapter, module, trial, directory):
        spec = module.TEMPLATE_SPEC
        if not isinstance(spec, prepared.TemplateSpec):
            raise RuntimeError("isolated recipe requires an explicit TemplateSpec")
        if self.initial is None:
            self.initial = {
                "helpers": pilot.helper_fingerprints(),
                "adapter": pilot.adapter_fingerprints(),
            }
        original = sheet_setup.PROJECT_DRWDOT.resolve(strict=True)
        adapter.ownership.register_source(original)
        self.inputs[str(original)] = prepared._sha(original)
        row = {
            "variant": self.variant.value,
            "spec": asdict(spec),
            "accessors": [],
            "operation_scopes": [],
            "setup_calls": 0,
            "timing_scope": "accessor includes input validation/preparation; setup is the inner factory only and is included in recipe_seconds; neither is the total diagnostic time",
        }
        self.row = trial["template_factory"] = row
        entry = None
        if self.variant is DrawingFactory.PREPARED:
            entry = await self._prepare(adapter, spec, Path(directory) / "cache", row)
        factory = (
            normal_drawing_factory(adapter, spec)
            if entry is None
            else prepared_drawing_factory(adapter, entry)
        )
        self.factory = factory

        def drawing_factory(actual_adapter, **kwargs):
            if actual_adapter is not adapter:
                raise RuntimeError("recipe setup received a different owned adapter")
            if row["setup_calls"]:
                raise RuntimeError("recipe setup may run only once")
            if set(kwargs) - {"property_view", "scale", "decimals"}:
                raise ValueError("unsupported recipe setup keyword")
            actual = prepared.TemplateSpec(
                kwargs.get("scale", (1, 1)), kwargs.get("decimals", 2)
            )
            if actual != spec:
                raise ValueError(
                    f"recipe setup changed scale/precision: {actual} != {spec}"
                )
            row["setup_calls"] += 1
            started = time.perf_counter()
            try:
                with _telemetry.span(
                    "diagnostic.recipe_template.setup", variant=self.variant.value
                ):
                    return factory(actual_adapter, **kwargs)
            finally:
                row["setup_seconds"] = time.perf_counter() - started

        return drawing_factory

    async def _prepare(self, adapter, spec, cache_root, row):
        pending = set()

        @contextmanager
        def operation_context(kind, path):
            path = Path(path).resolve()
            if not path.is_relative_to(cache_root.resolve()):
                raise RuntimeError("preparation escaped the owned trial cache")
            if path.parent not in pending:
                adapter.ownership.register_directory(path.parent)
                pending.add(path.parent)
            operation = {
                "operation": kind.value,
                "path": str(path),
                "status": "entered",
            }
            row["operation_scopes"].append(operation)
            if kind is prepared.TemplateOperation.CREATE:
                context = adapter.ownership.creating_document(
                    DocumentKind.DRAWING, path
                )
            elif kind is prepared.TemplateOperation.SAVE_AS:
                context = adapter.ownership.saving_as(path)
            else:
                raise RuntimeError("unsupported preparation ownership operation")
            try:
                with context:
                    yield
                operation["status"] = "completed"
            except Exception as error:
                operation.update(status="failed", error=repr(error))
                raise

        for access in ("miss", "hit"):
            observation = {"kind": access, "status": "running"}
            row["accessors"].append(observation)
            scope_start = len(row["operation_scopes"])
            started = time.perf_counter()
            try:
                entry = await prepared.prepare_project_drawing_template(
                    adapter,
                    scale=spec.scale,
                    decimals=spec.decimals,
                    cache_root=cache_root,
                    operation_context=operation_context,
                )
                observation.update(key=entry.key, path=str(entry.path))
                if access == "miss":
                    if len(pending) != 1:
                        raise RuntimeError(
                            "preparation needs exactly one owned staging directory"
                        )
                    adapter.ownership.relocate_prepared_template_directory(
                        next(iter(pending)), entry
                    )
                observed = [
                    item["operation"] for item in row["operation_scopes"][scope_start:]
                ]
                expected = ["create", "save_as", "create"] if access == "miss" else []
                if observed != expected:
                    raise RuntimeError(
                        f"{access}: unexpected native preparation operations: {observed}"
                    )
                artifacts = cache_artifacts(entry)
                if access == "hit" and artifacts != row["accessors"][0]["artifacts"]:
                    raise RuntimeError("prepared hit changed the exact cache entry")
                self.inputs.update(artifacts)
                observation.update(status="passed", artifacts=artifacts)
            except Exception as error:
                observation.update(status="failed", error=repr(error))
                raise
            finally:
                observation["seconds"] = time.perf_counter() - started
        return entry

    def require_used(self):
        if self.row is None or self.row["setup_calls"] != 1:
            raise RuntimeError("full recipe must execute exactly one selected factory")
        self.factory.require_used()

    def final_guards(self):
        """Read-only final guards also run after native recipe/title failure."""
        errors = []
        for path, expected in self.inputs.items():
            try:
                actual = prepared._sha(path)
                self.guards[path] = {"before": expected, "after": actual}
                if actual != expected:
                    raise RuntimeError(
                        f"immutable template/cache input changed: {path}"
                    )
            except Exception as error:
                self.guards.setdefault(path, {})["error"] = repr(error)
                errors.append(error)
        if self.initial is None:
            return errors
        for name, reader in (
            ("helpers", pilot.helper_fingerprints),
            ("adapter", pilot.adapter_fingerprints),
        ):
            try:
                actual = reader()
                self.guards[name] = {"before": self.initial[name], "after": actual}
                if actual != self.initial[name]:
                    raise RuntimeError(f"frozen factory {name} changed")
            except Exception as error:
                self.guards.setdefault(name, {})["error"] = repr(error)
                errors.append(error)
        return errors
