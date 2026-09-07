"""Drawing-only prepared setup, passed explicitly into each recipe.

The doit action already owns the machine COM seat. Materialization completes
before the recipe opens its source. The normal initializer stays in
``_drawing_sheet_setup``: preparation calls it, never this runner (no recursion).
Owned diagnostics may materialize with their CREATE/SAVE_AS scopes first, then
pass ``prepared_drawing_factory(adapter, entry, spec=requested)`` into the same recipe contract.
No process-global factory replacement or adapter mode is involved.
"""

from enum import StrEnum
from typing import Any, Callable

import _drawing_sheet_setup as sheet_setup
import _drawing_prepared_template as prepared
from _drawing_prepared_template import TemplateSpec
from _common import run_build
import _telemetry


class FactoryState(StrEnum):
    READY = "ready"
    CREATING = "creating"
    CREATED = "created"
    FAILED = "failed"


class ProjectDrawingFactory:
    """One explicit adapter/spec-bound drawing construction, with no retry."""

    def __init__(self, adapter: Any, spec: TemplateSpec, create: Callable, mode: str):
        if not isinstance(spec, TemplateSpec):
            raise TypeError("drawing factory requires an explicit TemplateSpec")
        self.adapter = adapter
        self.spec = spec
        self._create = create
        self.mode = mode
        self.state = FactoryState.READY

    def __call__(self, adapter: Any, *, property_view=None, scale=(1, 1), decimals=2):
        if adapter is not self.adapter:
            raise RuntimeError("drawing factory received a different adapter")
        if TemplateSpec(scale, decimals) != self.spec:
            raise ValueError("drawing factory spec differs from recipe setup")
        if self.state is not FactoryState.READY:
            raise RuntimeError("drawing factory may be called only once")
        self.state = FactoryState.CREATING
        try:
            with _telemetry.span("drawing.factory.create", mode=self.mode):
                result = self._create(
                    adapter, property_view=property_view, scale=scale, decimals=decimals
                )
        except BaseException:
            self.state = FactoryState.FAILED
            raise
        self.state = FactoryState.CREATED
        return result

    def require_used(self):
        if self.state is not FactoryState.CREATED:
            raise RuntimeError("recipe must complete exactly one drawing factory call")


def normal_drawing_factory(adapter, spec: TemplateSpec) -> ProjectDrawingFactory:
    """Explicit normal-setup control for owned diagnostics, never a fallback."""
    return ProjectDrawingFactory(
        adapter, spec, sheet_setup.new_project_drawing, "normal"
    )


def prepared_drawing_factory(
    adapter, entry: prepared.PreparedTemplate, *, spec: TemplateSpec
) -> ProjectDrawingFactory:
    """Consume the same validated entry in production and owned native pilots."""
    if not isinstance(entry, prepared.PreparedTemplate):
        raise TypeError("drawing factory requires an explicit PreparedTemplate")
    if entry.spec != prepared.canonical_spec(spec):
        raise RuntimeError(
            "prepared entry spec differs from requested canonical base precision"
        )

    def create(actual_adapter, **kwargs):
        # The normal initializer deliberately ignores property_view. The unchanged
        # finalizer selects the actual property-linked model view after creation.
        return prepared.inherited_drawing(actual_adapter, entry, spec=spec)

    return ProjectDrawingFactory(adapter, spec, create, "prepared")


async def prepare_drawing_factory(adapter, spec: TemplateSpec) -> ProjectDrawingFactory:
    """Prepare before source opening, under the caller's existing machine seat."""
    if not isinstance(spec, TemplateSpec):
        raise TypeError("drawing preparation requires an explicit TemplateSpec")
    entry = await prepared.prepare_project_drawing_template(
        adapter, decimals=spec.decimals
    )
    return prepared_drawing_factory(adapter, entry, spec=spec)


def run_drawing_build(build, *, spec: TemplateSpec) -> int:
    """Use the existing production connect/cleanup policy; change only setup."""
    if not isinstance(spec, TemplateSpec):
        raise TypeError("drawing runner requires an explicit TemplateSpec")
    # Refuse an uncoordinated hand launch before run_build can connect or execute
    # its existing CloseAllDocuments policy. Doit supplies the machine seat.
    prepared._seat()

    async def with_prepared_factory(adapter):
        factory = await prepare_drawing_factory(adapter, spec)
        artifacts = await build(adapter, drawing_factory=factory)
        factory.require_used()
        return artifacts

    return run_build(with_prepared_factory)
