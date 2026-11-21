"""Test-only: synthetic labelled STEPs and face inventories for feature bundles.

A real bundle STEP labels every native face (``HAF_F####``) and its
``.faces.json`` records each label's native geometry. Here each claimed face's
recorded parameters carry an id that one :class:`IdSelector` matches, standing
in for a drawing's geometric selectors, so the REAL manifest writer, inventory
reader and binding gates run over feature names from the real declarations.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from pathlib import Path

import pytest

import export_features
from _export_feature_faces import (
    face_label,
    face_record,
    inventory_path,
    write_inventory,
)
from _gtol_face import FaceGeometry

SURFACE = 4001  # any surface identity: IdSelector matches by id


class IdSelector:
    """Matches exactly the inventory rows whose parameters carry ``ident``."""

    surface_identity = SURFACE

    def __init__(self, ident: int) -> None:
        self.ident = ident

    def matches(self, geometry: FaceGeometry) -> bool:
        return geometry.parameters == (float(self.ident),)

    def __repr__(self) -> str:
        return f"IdSelector({self.ident})"


def step_bytes(
    labels: Sequence[str],
    *,
    name: str = "part.STEP",
    stamp: str = "2026-10-01T22:03:24",
    first: int = 10,
    stride: int = 1,
    newline: str = "\n",
) -> bytes:
    """An ISO 10303-21 file whose ADVANCED_FACEs carry ``labels`` in order."""
    rows = [
        "ISO-10303-21;",
        "HEADER;",
        "FILE_DESCRIPTION (( 'STEP AP214' ), '1' );",
        f"FILE_NAME ('{name}', '{stamp}', ( '' ), ( '' ), 'SwSTEP 2.0', 'SolidWorks 2026', '' );",
        "FILE_SCHEMA (( 'AUTOMOTIVE_DESIGN' ));",
        "ENDSEC;",
        "DATA;",
    ]
    for index, label in enumerate(labels):
        entity = first + stride * index
        quoted = label.replace("'", "''")
        rows.append(
            f"#{entity} = ADVANCED_FACE ( '{quoted}', ( #{entity + 1} ), #{entity + 2}, .T. ) ;"
        )
    rows.extend(("ENDSEC;", "END-ISO-10303-21;"))
    return newline.join(rows).encode("ascii")


def write_labelled_step(
    step: Path,
    features: Sequence[str],
    *,
    patches: Mapping[str, int] | None = None,
    split: Mapping[str, int] | None = None,
    stamp: str = "2026-10-01T22:03:24",
    newline: str = "\n",
) -> dict[str, tuple[IdSelector, ...]]:
    """Write ``step`` and its inventory and return selectors claiming each feature.

    Every feature gets ``patches[feature]`` (default 1) native faces, each
    exported as ``split[feature]`` (default 1) STEP faces; one unclaimed face
    pads each end, as a real part has faces no requirement names.
    """
    patches = dict(patches or {})
    split = dict(split or {})
    rows: list[tuple[int, int]] = [(-1, 0)]
    for ident, feature in enumerate(features, start=1):
        rows += [(ident, patch) for patch in range(patches.get(feature, 1))]
    rows.append((-2, 0))
    labels = [face_label(number) for number in range(1, len(rows) + 1)]
    copies = {
        ident: split.get(features[ident - 1], 1)
        for ident in range(1, len(features) + 1)
    }
    step_labels = [
        label
        for label, (ident, _patch) in zip(labels, rows)
        for _copy in range(copies.get(ident, 1))
    ]
    step.parent.mkdir(parents=True, exist_ok=True)
    step.write_bytes(
        step_bytes(step_labels, name=step.name, stamp=stamp, newline=newline)
    )
    write_inventory(
        step,
        [
            face_record(
                label,
                FaceGeometry(
                    None,
                    SURFACE,
                    (float(ident),),
                    None,
                    (float(ident), float(patch), 0.0, 0.0, 0.0, 0.0),
                ),
            )
            for label, (ident, patch) in zip(labels, rows)
        ],
    )
    return {
        feature: (IdSelector(ident),) for ident, feature in enumerate(features, start=1)
    }


def rewrite_step(step: Path, content: bytes) -> None:
    """Replace ``step``'s bytes and rebind its unchanged inventory rows to them."""
    faces = json.loads(inventory_path(step).read_text(encoding="utf-8"))["faces"]
    step.write_bytes(content)
    write_inventory(step, faces)


def write_bundle(
    stem: str,
    step: Path,
    *,
    patches: Mapping[str, int] | None = None,
    split: Mapping[str, int] | None = None,
) -> dict[str | None, dict[str, tuple[IdSelector, ...]]]:
    """Write ``stem``'s bundle STEP and every member STEP beside it, labelled for
    the real declarations' feature names; the rocker pivot bore exports as two
    STEP halves unless ``split`` says otherwise. Returns selectors per scope."""
    split = {**export_features.STEP_FACE_COUNTS.get(stem, {}), **(split or {})}
    selectors = {
        None: write_labelled_step(
            step,
            list(export_features.feature_selectors(stem)),
            patches=patches,
            split=split,
        )
    }
    for cfg, member in export_features.member_step_paths(stem).items():
        selectors[cfg] = write_labelled_step(
            step.with_name(member.name),
            list(export_features.feature_selectors(stem, cfg)),
            stamp="2026-10-01T22:03:25",
        )
    return selectors


def bind_manifest(
    stem: str,
    step: Path,
    selectors: Mapping[str | None, Mapping[str, Sequence[IdSelector]]],
    *,
    revision: str,
) -> Path:
    """Run the real ``write_manifest`` with the drawing's selectors replaced."""
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(
            export_features, "feature_selectors", lambda _stem, cfg=None: selectors[cfg]
        )
        return export_features.write_manifest(stem, step, revision=revision)
