"""Name a part's requirement-feature faces for the STEP export and read them back.

prechips (issue #1204) binds each requirement in ``features.toml`` to a SET of
faces in the released STEP.  Ordinal ``ADVANCED_FACE`` ids alone are not a
contract -- the STEP writer may renumber them on any re-export -- so the export
names the native faces and the face sets are read back by those names:

1. :func:`name_feature_faces` walks the open part's solid bodies once,
   resolves every selector ``export_features.feature_selectors(stem)``
   supplies with the same selector-owned geometry matcher the part PMI uses
   (``FaceSpec.matches``), and gives EVERY matching native face a
   deterministic ASCII name (``IPartDoc::SetEntityName``, verified by
   ``IPartDoc::GetEntityName`` read-back).  A selector matching nothing, or a
   face claimed by two features, fails loud.
2. ``export_models`` (the full export and the isolated ``--features`` bundles
   share one ``_save_feature_step`` path) writes the STEP with
   ``swUserPreferenceToggle_e.swStepExportFaceEdgeProps`` on, which carries the
   face names into the ``ADVANCED_FACE`` labels, and split periodic faces on
   (the AP214 representation v38 shipped: the issue #1204 spike
   found the v38 rocker-arm pivot bore as ``ADVANCED_FACE`` ordinals 1 and 16,
   two Ø6.5 halves). One named native periodic face can label SEVERAL STEP
   faces with the same name. ``export_models`` requires exactly two exported
   rocker pivot-bore patches. Nothing rewrites the raw ``SaveAs3`` STEP bytes.
3. :func:`step_face_sets` reads the labels back into face sets of STEP face
   references (``#<entity>/ADVANCED_FACE[<ordinal>]/<label>``) -- every face
   whose label a feature owns -- and refuses a missing feature or label, an
   unknown or malformed label, a label two features claim and a duplicated
   STEP entity id.

The names are transient state of the export session: the caller never saves
the native part (``export_models`` checks the ``.SLDPRT`` SHA-256 around every
named export).

Only :func:`name_feature_faces` touches COM, and it imports the COM helpers
lazily, so the STEP parser stays importable on a machine with no SolidWorks.
"""

from __future__ import annotations

import re
from collections import Counter
from typing import Any, Iterable, Mapping, Sequence

FACE_NAME_PREFIX = "HAF_"
_PATCH_SEPARATOR = "__P"
_FEATURE_KEY = re.compile(r"[a-z][a-z0-9]*(?:_[a-z0-9]+)*")
_NAME = re.compile(
    re.escape(FACE_NAME_PREFIX)
    + r"(?P<feature>[A-Z][A-Z0-9]*(?:_[A-Z0-9]+)*)"
    + re.escape(_PATCH_SEPARATOR)
    + r"(?P<patch>[0-9]{2,})"
)
# ISO 10303-21: ``#12 = ADVANCED_FACE ( 'label', ( #bounds ), #surface, .T. ) ;``.
# A quote inside a string is doubled; the entity may wrap across lines.
_ADVANCED_FACE = re.compile(
    r"#(\d+)\s*=\s*ADVANCED_FACE\s*\(\s*'((?:[^']|'')*)'", re.DOTALL
)
# Every entity instance: ``#n =`` at the start of the file or after the ``;``
# that ends the previous record (a ``#n`` reference is never followed by ``=``).
_INSTANCE = re.compile(r"(?:^|;)\s*#(\d+)\s*=")
# Patch order key: a face's box rounded to 0.1 µm, so a sub-tolerance float
# wobble between two exports cannot reorder patches.
_BOX_DIGITS = 7
_SOLID_BODY = 0  # swBodyType_e.swSolidBody


class FeatureFaceError(RuntimeError):
    """A feature face set cannot be named, exported or read back unambiguously."""


def _check_feature_key(feature: str) -> None:
    if not isinstance(feature, str) or _FEATURE_KEY.fullmatch(feature) is None:
        raise FeatureFaceError(
            f"feature key {feature!r} must match {_FEATURE_KEY.pattern} "
            "(lower-case ASCII words joined by single underscores)"
        )


def face_name(feature: str, patch: int) -> str:
    """The exported name of ``feature``'s ``patch``-th face (1-based)."""
    _check_feature_key(feature)
    if isinstance(patch, bool) or not isinstance(patch, int) or patch < 1:
        raise FeatureFaceError(f"{feature}: patch number {patch!r} must be >= 1")
    return f"{FACE_NAME_PREFIX}{feature.upper()}{_PATCH_SEPARATOR}{patch:02d}"


def _parse_name(name: str) -> tuple[str, int] | None:
    match = _NAME.fullmatch(name)
    if match is None:
        return None
    return match["feature"].lower(), int(match["patch"])


def face_ref(entity: int, ordinal: int, label: str) -> str:
    """One STEP face of a face set: entity id, ``ADVANCED_FACE`` ordinal (1-based,
    file order) and the label that put it in the set."""
    return f"#{entity}/ADVANCED_FACE[{ordinal}]/{label}"


def step_face_sets(
    step_text: str,
    expected_features: Iterable[str] | Mapping[str, Sequence[str]],
) -> dict[str, list[str]]:
    """Read one STEP's labelled ``ADVANCED_FACE`` entities into face sets.

    Returns ``{feature: [face_ref, ...]}`` by patch number, then file order:
    EVERY face whose label the feature owns, so a periodic native face split
    into several STEP faces sharing one label contributes all of them.

    ``expected_features`` is either the feature keys (manifest generation from
    the adjacent STEP: a label's feature is read from the name, and each
    feature's distinct patch numbers must be 1..n) or the ``{feature: labels}``
    :func:`name_feature_faces` assigned (the export itself: every assigned label
    must label at least one STEP face and every prefixed label must be
    assigned).  Labels without :data:`FACE_NAME_PREFIX` (``'NONE'`` on every
    unnamed face) are not claims and are ignored.  Every problem is collected
    and raised together.
    """
    problems: list[str] = []
    assigned = (
        {feature: list(labels) for feature, labels in expected_features.items()}
        if isinstance(expected_features, Mapping)
        else None
    )
    expected = list(assigned if assigned is not None else expected_features)
    for feature in expected:
        _check_feature_key(feature)
    if len(set(expected)) != len(expected):
        raise FeatureFaceError(f"expected features repeat a key: {expected}")
    owner: dict[str, str] = {}
    if assigned is not None:
        for feature, labels in assigned.items():
            for label in labels:
                parsed = _parse_name(label)
                if parsed is None or parsed[0] != feature:
                    problems.append(f"{feature}: assigned label {label!r} is not its face name")
                if owner.setdefault(label, feature) != feature:
                    problems.append(
                        f"{label}: claimed by features {sorted({owner[label], feature})}"
                    )

    instances = Counter(int(number) for number in _INSTANCE.findall(step_text))
    for entity, count in sorted(instances.items()):
        if count > 1:
            problems.append(f"#{entity}: STEP entity id defined {count} times")

    faces = _ADVANCED_FACE.findall(step_text)
    if not faces:
        raise FeatureFaceError("STEP carries no ADVANCED_FACE entities")
    found: dict[str, list[tuple[int, int, str]]] = {feature: [] for feature in expected}
    seen: Counter[str] = Counter()
    for ordinal, (entity, raw) in enumerate(faces, start=1):
        label = raw.replace("''", "'")
        if not label.startswith(FACE_NAME_PREFIX):
            continue
        seen[label] += 1
        parsed = _parse_name(label)
        if parsed is None:
            if seen[label] == 1:
                problems.append(f"{label}: malformed feature face name")
            continue
        feature = owner.get(label) if assigned is not None else parsed[0]
        if feature not in found:
            if seen[label] == 1:
                problems.append(
                    f"{label}: unknown feature {parsed[0]!r}" if assigned is None
                    else f"{label}: labels a STEP face but was never assigned"
                )
            continue
        found[feature].append((parsed[1], ordinal, face_ref(int(entity), ordinal, label)))

    refs = {
        feature: [ref for _patch, _ordinal, ref in sorted(faces_of)]
        for feature, faces_of in found.items()
    }

    for feature in expected:
        if not refs[feature]:
            problems.append(f"{feature}: no named STEP face")
            continue
        if assigned is not None:
            missing = [label for label in assigned[feature] if not seen[label]]
            if missing:
                problems.append(f"{feature}: assigned labels {missing} label no STEP face")
        else:
            numbers = sorted({patch for patch, _ordinal, _ref in found[feature]})
            if numbers != list(range(1, len(numbers) + 1)):
                problems.append(
                    f"{feature}: patch numbers {numbers} are not 1..{len(numbers)}"
                )
    if problems:
        raise FeatureFaceError("STEP feature faces invalid: " + "; ".join(problems))
    return refs


def assign_feature_patches(
    geometries: Sequence[Any], selectors: Mapping[str, Sequence[Any]],
) -> dict[str, list[int]]:
    """Map each feature to the indices of EVERY face in ``geometries`` it claims.

    ``geometries`` are ``_gtol_face.FaceGeometry`` rows from one body walk.  A
    face matched by several selectors of the same feature counts once; one
    matched by two features is ambiguous and fails, as does a selector that
    matches nothing.  Patches are ordered by their rounded box (then walk
    position) so the numbering follows geometry, not traversal order.
    """
    problems: list[str] = []
    claims: dict[int, list[str]] = {}
    assigned: dict[str, list[int]] = {}
    for feature, specs in selectors.items():
        _check_feature_key(feature)
        if not specs:
            problems.append(f"{feature}: no face selector")
            continue
        claimed: set[int] = set()
        for spec in specs:
            hits = {
                index for index, geometry in enumerate(geometries)
                if spec.matches(geometry)
            }
            if not hits:
                problems.append(f"{feature}: selector {spec!r} matched no face")
            claimed |= hits
        for index in claimed:
            claims.setdefault(index, []).append(feature)
        assigned[feature] = sorted(
            claimed,
            key=lambda index: (
                tuple(round(value, _BOX_DIGITS) for value in geometries[index].box),
                index,
            ),
        )
    for index, features in sorted(claims.items()):
        if len(features) > 1:
            problems.append(f"face #{index} is claimed by {sorted(features)}")
    if problems:
        raise FeatureFaceError("feature face selection invalid: " + "; ".join(problems))
    return assigned


def name_feature_faces(doc: Any, stem: str) -> dict[str, list[str]]:
    """Name every face of ``stem``'s requirement features on the open part.

    Returns ``{feature: [names]}``, the exact claim :func:`step_face_sets`
    verifies after the STEP export.  Never renames: a face that already carries
    a name (SolidWorks auto-names a face a mate references) fails, because
    ``SetEntityName`` refuses it and overwriting would break that reference.
    """
    import _telemetry  # noqa: PLC0415
    from _com import _bind, _com_invoke, _early_bound  # noqa: PLC0415
    from _gtol_face_read import face_geometry  # noqa: PLC0415
    from export_features import feature_selectors  # noqa: PLC0415

    selectors = feature_selectors(stem)
    if not selectors:
        raise FeatureFaceError(f"{stem}: export_features declares no feature")
    identities = frozenset(
        spec.surface_identity for specs in selectors.values() for spec in specs
    )
    with _telemetry.span("export.feature_faces", part=stem) as sp:
        part = _early_bound(doc, "IPartDoc")
        geometries = []
        for body in part.GetBodies2(_SOLID_BODY, False) or ():
            face = _com_invoke(body, "IBody2", "GetFirstFace")
            while face is not None:
                geometry = face_geometry(face, identities=identities)
                if geometry is not None:
                    geometries.append(geometry)
                face = _com_invoke(face, "IFace2", "GetNextFace")
        assigned = assign_feature_patches(geometries, selectors)

        names: dict[str, list[str]] = {}
        for feature, indices in assigned.items():
            names[feature] = []
            for patch, index in enumerate(indices, start=1):
                name = face_name(feature, patch)
                face = _bind(geometries[index].face, "IFace2")
                existing = part.GetEntityName(face)
                if existing:
                    raise FeatureFaceError(
                        f"{stem}.{feature}: face already named {existing!r}; "
                        f"refusing to rename it {name!r}"
                    )
                if not part.SetEntityName(face, name):
                    raise FeatureFaceError(
                        f"{stem}.{feature}: SetEntityName({name!r}) returned False"
                    )
                readback = part.GetEntityName(face)
                if readback != name:
                    raise FeatureFaceError(
                        f"{stem}.{feature}: named {name!r}, read back {readback!r}"
                    )
                names[feature].append(name)
        sp.set_attribute("faces.walked", len(geometries))
        sp.set_attribute("faces.named", sum(len(v) for v in names.values()))
        sp.set_attribute("features", len(names))
    return names
