"""Author the paper drive's named exploded presentation (PAPER_DRIVE_EXPLODED).

``_explode.author_explode_steps`` authors and proves each step of
``pd_paper_drive_explode_spec.plan_explode`` along a global axis; the chain
links and the other native pattern followers must read unmoved. The exploded
sheet's view at 1:3 references the teeth/thread-free Default Simplified copy.
"""

from __future__ import annotations

from typing import Any

import _explode
from _component_references import component_identity
from _explode import Step
from pd_paper_drive_explode_spec import (
    EXPLODED_VIEW_NAME,
    SOURCE_CONFIGURATION,
    Instance,
    member_family,
    plan_explode,
)


def exploded_view_name(configuration: str) -> str:
    """The named explode ``configuration`` owns."""
    return _explode.exploded_view_name(
        EXPLODED_VIEW_NAME, SOURCE_CONFIGURATION, configuration
    )


def _plan(_model: Any, components: Any, _baseline: Any) -> list[Step]:
    instances = [
        Instance(name=name, stem=member_family(*component_identity(component)))
        for name, component in components
    ]
    return [
        Step(step.label, tuple(names), step.axis, step.distance_mm)
        for step, names in plan_explode(instances)
    ]


def create_paper_drive_explode(adapter: Any, configuration_name: str) -> None:
    """Author the released presentation in the active ``configuration_name``
    (Default or Default Simplified) and restore the working model."""
    _explode.author_explode_steps(
        adapter,
        configuration_name,
        view=EXPLODED_VIEW_NAME,
        source=SOURCE_CONFIGURATION,
        step_prefix="PAPER DRIVE",
        plan=_plan,
    )
