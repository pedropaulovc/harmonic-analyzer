"""Author the complete machine's named exploded presentation (HA_EXPLODED).

``_explode.author_explode_steps`` authors and proves each step of
``ha_harmonic_analyzer_assembly_spec.plan_explode``: whole top-level
subassemblies move along a global axis while the frame and every subassembly
another step owns read unmoved. The exploded sheet's view references the
teeth/thread-free Default Simplified copy.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import _explode
from _explode import Step
from ha_harmonic_analyzer_assembly_spec import (
    EXPLODED_VIEW_NAME,
    SOURCE_CONFIGURATION,
    Instance,
    plan_explode,
)


def _plan(_model: Any, components: Any, _baseline: Any) -> list[Step]:
    instances = [
        Instance(
            name=name, stem=Path(str(component.GetPathName() or "")).stem.casefold()
        )
        for name, component in components
    ]
    return [
        Step(step.label, tuple(names), step.axis, step.distance_mm)
        for step, names in plan_explode(instances)
    ]


def create_harmonic_analyzer_explode(adapter: Any, configuration_name: str) -> None:
    """Author the released presentation in the active ``configuration_name``
    (Default or Default Simplified) and restore the working model."""
    _explode.author_explode_steps(
        adapter,
        configuration_name,
        view=EXPLODED_VIEW_NAME,
        source=SOURCE_CONFIGURATION,
        step_prefix="HARMONIC ANALYZER",
        plan=_plan,
    )
