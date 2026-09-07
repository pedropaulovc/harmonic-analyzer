"""Explicit owned-pilot inputs and existing production readback contracts.

Initial hashes pin exact native inputs observed on 2026-09-06. Matching execution
tokens were read for the two shafts; this does not prove builder provenance.
Alignment's explicit 2026-09-07 production-builder migration is recorded in
diagnostics/alignment_source_manifest.md; other input identities are unchanged.
Two fastener production-builder inputs are explicitly enrolled in
diagnostics/fastener_source_manifest.md; no prior target pin is changed.
No recipe, geometry, output path or production layout policy lives here.
"""

from dataclasses import dataclass, field
from importlib import import_module

import channel_lever_spec
import cone_pivot_screw_spec
import cone_tip_adjuster_spec
import fulcrum_shaft_spec
import pivot_shaft_spec
import rocker_arm_notes
from diagnostics._recipe_view_roles import VIEW_ROLES, ViewRole


@dataclass(frozen=True)
class RecipeTarget:
    source_sha256: str
    spec_module: str
    dimensions: dict[str, set[str]]
    basic: dict[str, set[str]] = field(default_factory=dict)
    entity_labels: dict[str, str] = field(default_factory=dict)
    view_roles: dict[str, ViewRole] = field(default_factory=dict)


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
    "cone_tip_adjuster": RecipeTarget(
        "f3578ac2b2ab95e478bc7bd72c316ebab057c125d5244af6fa2c3e12f4d48468",
        "cone_tip_adjuster_spec",
        cone_tip_adjuster_spec.DRAWING_DIMENSIONS,
    ),
    "cone_pivot_screw": RecipeTarget(
        "515019088b41d329b45f0487b9241123751ecac7d6c116481930ae9c45e89c36",
        "cone_pivot_screw_spec",
        cone_pivot_screw_spec.DRAWING_DIMENSIONS,
    ),
}


# Exact native bytes read from root outputs and compared with execution tokens
# on 2026-09-06; no claim that disk equality proves builder provenance.
_VIEW_SOURCE_HASHES = {
    # Actual authored production output; historical 858dc... receipts stay intact.
    "alignment_pinion": "9e09613dcdfeadcd76cfa4e28f2c9b6035ea1736bdb1bbcca1a7ecc3239c0632",
    "cone_gear_shaft": "8df108cb4053bd47bcc1acc8b83fede6e3a52a9d3c4f6341c1ab3702d512b0ab",
    "crank_drive_gear": "2cd81cf44def13c0bbd298617d16769206e4931eac41a04642ac6217e4880cb5",
    "crank_pinion": "08ea59d153d8801792a8b611981702d0b584b9e8a04a33e4b9cb322a3d9df6fc",
    "crankshaft": "3c0224617322e3a10cca4a5c52e2b0a3b4c82e7be7969c0b21faf4db58b4cd94",
    "cylinder_gear": "46fcb66a87fd35f8862e4a01e2225688b91ab7182608bce26159f59c5b14f120",
    "rack_pinion": "96f57e663d04d745e8ad67d36a5f9ea4ddbaece4c82b2dc312bca69d4d8005b8",
    "spring_hook": "29c04a0919e0f720915527bd62cdb90eed909de6d14e74b9068c106baa42ace5",
    "transgear_feed_pinion": "f9b033d0026ef26996a52f73fad3b3147c6f5e5b15333a306004dcaf435a0d77",
    "transgear_pinion": "4c079ba522ccf79fa90e75afa23303ba4c2f6541232e608525368e4cbb56d335",
}
for _target, _hash in _VIEW_SOURCE_HASHES.items():
    _spec_name = "spring_hook_notes" if _target == "spring_hook" else f"{_target}_spec"
    _spec = import_module(_spec_name)
    TARGETS[_target] = RecipeTarget(
        _hash,
        _spec_name,
        _spec.DRAWING_DIMENSIONS,
        view_roles=VIEW_ROLES[_target],
    )
