"""Explicit local inputs for the three-source MATERIAL experiment only.

Observed foundation eb39/e77 production outputs on 2026-09-07, not transplanted
historical pilot pins. Source/token SHA equality and successful native task spans
are recorded in material-template-centering.md. They do not prove this new
template candidate, cold drawing behavior, or complete source immutability.
"""

from dataclasses import replace

import tube_frame_spec
from diagnostics import probe_drawing_attachments as attachments
from diagnostics._recipe_acceptance_targets import (
    RecipeTarget,
    TARGETS as PILOT_TARGETS,
)

TARGETS = {
    "rocker_arm": replace(
        PILOT_TARGETS["rocker_arm"],
        source_sha256="eb78509e2ef6f765b40efac0d5d2f16fcea8e20a118e57f04ceaad1429b44cc5",
    ),
    "channel_lever": replace(
        PILOT_TARGETS["channel_lever"],
        source_sha256="7c07b92c1855ef5774f35513c0da2a5b799c2562e8bac5838bd12c6ed39d401e",
    ),
    "tube_frame": RecipeTarget(
        "5b3c9bb45e06965f262d5734612c065872ddf0decd2daaa10e4e887fc9061320",
        "tube_frame_spec",
        tube_frame_spec.DRAWING_DIMENSIONS,
    ),
}


def require_sources(sources):
    if sources.keys() != TARGETS.keys():
        raise RuntimeError(
            "material source manifest requires exactly rocker, lever, and tube"
        )
    expected = {}
    for target, path in sources.items():
        actual = attachments.file_digest(path)
        token = path.with_name(f".{path.stem}.execution")
        if actual != TARGETS[target].source_sha256:
            raise RuntimeError(
                f"material source {target}: exact local source hash mismatch: {actual}"
            )
        if not token.is_file() or token.read_text(encoding="utf-8").strip() != actual:
            raise RuntimeError(
                f"material source {target}: execution token does not match pinned bytes"
            )
        expected[str(path)] = actual
        expected[str(token)] = attachments.file_digest(token)
    return expected


def require_material_value(row, value, *, expected_vertical):
    if not value or row["text"] != value:
        raise RuntimeError(
            f"material field differs from exact source property: {value!r}"
        )
    if row["horizontal"] != 1 or row["vertical"] != expected_vertical:
        raise RuntimeError(
            "material field does not retain the explicitly selected alignment"
        )
