"""Explicit owned-pilot inputs and existing production readback contracts.

Hashes pin the exact native inputs observed on 2026-09-06. Matching execution
tokens were read for the two shafts; this does not prove builder provenance.
No recipe, geometry, output path or production layout policy lives here.
"""

from dataclasses import dataclass, field

import channel_lever_spec
import fulcrum_shaft_spec
import pivot_shaft_spec
import rocker_arm_notes


@dataclass(frozen=True)
class RecipeTarget:
    source_sha256: str
    spec_module: str
    dimensions: dict[str, set[str]]
    basic: dict[str, set[str]] = field(default_factory=dict)
    entity_labels: dict[str, str] = field(default_factory=dict)


def _shaft_labels(stem, spec):
    return {
        **{
            f"{stem} shaft PMI {row.key}": row.key
            for row in (
                *spec.PART_DATUMS,
                *spec.GEOMETRIC_CONTROLS,
            )
        },
        f"{stem} bearing finish": "bearing_finish",
    }


TARGETS = {
    "rocker_arm": RecipeTarget(
        "3bfb6da45b91e5a73b24c74baf81141899149e3c327aa943930baed3fba4d4a0",
        "rocker_arm_notes",
        rocker_arm_notes.DRAWING_DIMENSIONS,
    ),
    "channel_lever": RecipeTarget(
        "6a994561f19487029c938cd7cca5047acbdfbf686020514be538ef5a632e0841",
        "channel_lever_spec",
        channel_lever_spec.DRAWING_DIMENSIONS,
        channel_lever_spec.SOURCE_BASIC_DIMENSIONS,
    ),
    "fulcrum_shaft": RecipeTarget(
        "73eeb75dcb1f24ca70b5f5ad2212d7b829a94af3a518b7c3830ff6c58e47d740",
        "fulcrum_shaft_spec",
        fulcrum_shaft_spec.DRAWING_DIMENSIONS,
        entity_labels=_shaft_labels("fulcrum", fulcrum_shaft_spec),
    ),
    "pivot_shaft": RecipeTarget(
        "e5bcdb79849aac9ce6068188ccf0c6e2fd1222e82f1d8b4d75e0fd2723f01dc5",
        "pivot_shaft_spec",
        pivot_shaft_spec.DRAWING_DIMENSIONS,
        entity_labels=_shaft_labels("pivot", pivot_shaft_spec),
    ),
}
