"""Label every face of a part's STEP and bind requirement features to it offline.

prechips (issue #1204) binds each requirement in ``features.toml`` to a SET of
faces in the released STEP.  Ordinal ``ADVANCED_FACE`` ids alone are not a
contract -- the STEP writer may renumber them on any re-export -- so the export
labels the native faces and the face sets are read back by those labels:

1. :func:`label_all_faces` (the only COM step) walks the open part's solid
   bodies once, reads every face's native geometry (surface identity,
   parameters, outward normal, box: ``_gtol_face_read.face_geometry``) and
   gives each unnamed face a deterministic ASCII label (``HAF_F0001``...,
   numbered by rounded box, then walk position) with ``IPartDoc::SetEntityName``,
   verified by ``GetEntityName`` read-back.  A face that already carries a name
   (SolidWorks auto-names a face a mate references) keeps it as its label:
   renaming it would break that reference.
2. ``export_models --features`` writes the scoped STEP with
   ``swStepExportFaceEdgeProps`` on, which carries the labels into the
   ``ADVANCED_FACE`` entities, and split periodic faces on (the AP214
   representation v38 shipped: the rocker pivot bore as two Ø6.5 halves), so
   one labelled native face can label SEVERAL STEP faces.  Beside it,
   :func:`write_inventory` records every label with its native geometry, bound
   to the STEP's sha256.  Nothing rewrites the raw ``SaveAs3`` STEP bytes.
3. :func:`bind_features` needs no SolidWorks: it runs the drawing's selectors
   (``FaceSpec.matches``, the matcher the native walk used to run) over the
   inventory's recorded geometry and maps each claimed face's label to every
   STEP face it labels (``#<entity>/ADVANCED_FACE[<ordinal>]/<label>``).  A new
   or changed requirement therefore binds to an already-exported STEP; only a
   geometry change needs a new export.

The labels are transient state of the export session: the caller never saves
the native part (``export_models`` checks the ``.SLDPRT`` SHA-256 around every
labelled export).  Only :func:`label_all_faces` touches COM, and it imports the
COM helpers lazily, so everything else runs on a machine with no SolidWorks.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from collections import Counter
from pathlib import Path
from typing import Any, Iterable, Mapping, Sequence

from _gtol_face import FaceGeometry

FACE_LABEL_PREFIX = "HAF_F"
INVENTORY_SCHEMA = "harmonic-analyzer/face-inventory@1"
INVENTORY_SUFFIX = ".faces.json"
_FEATURE_KEY = re.compile(r"[a-z][a-z0-9]*(?:_[a-z0-9]+)*")
# ISO 10303-21: ``#12 = ADVANCED_FACE ( 'label', ( #bounds ), #surface, .T. ) ;``.
# A quote inside a string is doubled; the entity may wrap across lines.
_ADVANCED_FACE = re.compile(r"#(\d+)\s*=\s*ADVANCED_FACE\s*\(\s*'((?:[^']|'')*)'", re.DOTALL)
# Every entity instance: ``#n =`` at the start of the file or after the ``;``
# that ends the previous record (a ``#n`` reference is never followed by ``=``).
_INSTANCE = re.compile(r"(?:^|;)\s*#(\d+)\s*=")
# Label order key: a face's box rounded to 0.1 µm, so a sub-tolerance float
# wobble between two exports cannot reorder labels.
_BOX_DIGITS = 7
_SOLID_BODY = 0  # swBodyType_e.swSolidBody


class FeatureFaceError(RuntimeError):
    """A face set cannot be labelled, exported, inventoried or bound unambiguously."""


def _check_feature_key(feature: str) -> None:
    if not isinstance(feature, str) or _FEATURE_KEY.fullmatch(feature) is None:
        raise FeatureFaceError(
            f"feature key {feature!r} must match {_FEATURE_KEY.pattern} "
            "(lower-case ASCII words joined by single underscores)"
        )


def face_label(index: int) -> str:
    """The exported label of the ``index``-th unnamed face (1-based)."""
    if isinstance(index, bool) or not isinstance(index, int) or index < 1:
        raise FeatureFaceError(f"face label number {index!r} must be >= 1")
    return f"{FACE_LABEL_PREFIX}{index:04d}"


def face_ref(entity: int, ordinal: int, label: str) -> str:
    """One STEP face of a face set: entity id, ``ADVANCED_FACE`` ordinal (1-based,
    file order) and the label that put it in the set."""
    return f"#{entity}/ADVANCED_FACE[{ordinal}]/{label}"


def step_label_refs(step_text: str, labels: Iterable[str]) -> dict[str, list[str]]:
    """Every STEP face each inventory label labels, in file order.

    Refuses a duplicated STEP entity id, a label that labels no
    ``ADVANCED_FACE``, a face that carries no inventory label (``'NONE'`` or a
    stray name) and a repeated inventory label.  Every problem is collected and
    raised together.
    """
    labels = list(labels)
    problems: list[str] = []
    repeated = sorted(label for label, count in Counter(labels).items() if count > 1)
    if repeated:
        problems.append(f"inventory labels repeat: {repeated}")
    instances = Counter(int(number) for number in _INSTANCE.findall(step_text))
    problems += [f"#{entity}: STEP entity id defined {count} times" for entity, count in sorted(instances.items()) if count > 1]
    faces = _ADVANCED_FACE.findall(step_text)
    if not faces:
        raise FeatureFaceError("STEP carries no ADVANCED_FACE entities")
    refs: dict[str, list[str]] = {label: [] for label in labels}
    unlabelled: Counter[str] = Counter()
    for ordinal, (entity, raw) in enumerate(faces, start=1):
        label = raw.replace("''", "'")
        if label in refs:
            refs[label].append(face_ref(int(entity), ordinal, label))
        else:
            unlabelled[label] += 1
    problems += [f"{count} STEP face(s) labelled {label!r}, not an inventory label" for label, count in sorted(unlabelled.items())]
    missing = [label for label, found in refs.items() if not found]
    if missing:
        problems.append(f"inventory labels {missing} label no STEP face")
    if problems:
        raise FeatureFaceError("STEP face labels invalid: " + "; ".join(problems))
    return refs


def _box_key(geometry: FaceGeometry | None) -> tuple[float, ...]:
    return tuple(round(value, _BOX_DIGITS) for value in (geometry.box if geometry is not None else ()))


def assign_feature_patches(geometries: Sequence[Any], selectors: Mapping[str, Sequence[Any]]) -> dict[str, list[int]]:
    """Map each feature to the indices of EVERY face in ``geometries`` it claims.

    ``geometries`` are ``_gtol_face.FaceGeometry`` rows from one body walk.  A
    face matched by several selectors of the same feature counts once; one
    matched by two features is ambiguous and fails, as does a selector that
    matches nothing.  Patches are ordered by their rounded box (then walk
    position) so the order follows geometry, not traversal order.
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
            hits = {index for index, geometry in enumerate(geometries) if spec.matches(geometry)}
            if not hits:
                problems.append(f"{feature}: selector {spec!r} matched no face")
            claimed |= hits
        for index in claimed:
            claims.setdefault(index, []).append(feature)
        assigned[feature] = sorted(claimed, key=lambda index: (_box_key(geometries[index]), index))
    for index, features in sorted(claims.items()):
        if len(features) > 1:
            problems.append(f"face #{index} is claimed by {sorted(features)}")
    if problems:
        raise FeatureFaceError("feature face selection invalid: " + "; ".join(problems))
    return assigned


def face_record(label: str, geometry: FaceGeometry | None) -> dict[str, Any]:
    """The inventory row of one labelled native face: everything a selector reads."""
    if geometry is None:
        return {"label": label, "identity": 0, "parameters": [], "outward_normal": None, "box": []}
    values = [*geometry.parameters, *(geometry.outward_normal or ()), *geometry.box]
    if not all(math.isfinite(float(value)) for value in values):
        raise FeatureFaceError(f"{label}: non-finite native face geometry")
    return {
        "label": label,
        "identity": int(geometry.identity),
        "parameters": [float(value) for value in geometry.parameters],
        "outward_normal": None if geometry.outward_normal is None else [float(value) for value in geometry.outward_normal],
        "box": [float(value) for value in geometry.box],
    }


def label_all_faces(doc: Any, stem: str) -> list[dict[str, Any]]:
    """Label every face of the open part and return its inventory rows.

    Unnamed faces get :func:`face_label` numbers in rounded-box, then walk,
    order; a face that already carries a name keeps it.  Every label is read
    back, and two faces may not share one.  Run once per shown configuration:
    a face named in an earlier configuration keeps that name.
    """
    import _telemetry  # noqa: PLC0415
    from _com import _bind, _com_invoke, _early_bound  # noqa: PLC0415
    from _gtol_face_read import face_geometry  # noqa: PLC0415

    with _telemetry.span("export.face_labels", part=stem) as sp:
        part = _early_bound(doc, "IPartDoc")
        walked: list[tuple[Any, FaceGeometry]] = []
        for body in part.GetBodies2(_SOLID_BODY, False) or ():
            face = _com_invoke(body, "IBody2", "GetFirstFace")
            while face is not None:
                geometry = face_geometry(face)
                if geometry is None or not geometry.box:
                    # Non-analytic faces still need a box: it orders the labels.
                    box = tuple(_com_invoke(face, "IFace2", "GetBox") or ())
                    geometry = FaceGeometry(face, 0 if geometry is None else geometry.identity, (), None, box)
                walked.append((face, geometry))
                face = _com_invoke(face, "IFace2", "GetNextFace")
        bound = [_bind(face, "IFace2") for face, _geometry in walked]
        existing = [str(part.GetEntityName(face) or "") for face in bound]
        taken = {name for name in existing if name}
        records: list[dict[str, Any]] = []
        number = 0
        for index in sorted(range(len(walked)), key=lambda index: (_box_key(walked[index][1]), index)):
            label = existing[index]
            if not label:
                number += 1
                while face_label(number) in taken:
                    number += 1
                label = face_label(number)
                if not part.SetEntityName(bound[index], label):
                    raise FeatureFaceError(f"{stem}: SetEntityName({label!r}) returned False")
                readback = part.GetEntityName(bound[index])
                if readback != label:
                    raise FeatureFaceError(f"{stem}: labelled {label!r}, read back {readback!r}")
                taken.add(label)
            records.append(face_record(label, walked[index][1]))
        repeated = sorted(label for label, count in Counter(row["label"] for row in records).items() if count > 1)
        if repeated:
            raise FeatureFaceError(f"{stem}: faces share labels {repeated}")
        sp.set_attribute("faces.walked", len(walked))
        sp.set_attribute("faces.labelled", number)
        sp.set_attribute("faces.kept_names", sum(1 for name in existing if name))
    return records


def inventory_path(step: Path) -> Path:
    """The face inventory beside ``step``: ``<step stem>.faces.json``."""
    step = Path(step)
    return step.with_name(f"{step.stem}{INVENTORY_SUFFIX}")


def write_inventory(step: Path, records: Sequence[Mapping[str, Any]]) -> Path:
    """Write the face inventory of the just-exported ``step``, bound to its bytes.

    Every inventory label must label at least one STEP face and every STEP face
    must carry an inventory label (:func:`step_label_refs`)."""
    step = Path(step)
    content = step.read_bytes()
    step_label_refs(content.decode("latin-1"), (row["label"] for row in records))
    path = inventory_path(step)
    document = {
        "schema": INVENTORY_SCHEMA,
        "step": step.name,
        "step_sha256": hashlib.sha256(content).hexdigest(),
        "units": "m",
        "faces": [dict(row) for row in records],
    }
    partial = path.with_name(path.name + ".partial")
    partial.write_text(json.dumps(document, indent=1, sort_keys=True) + "\n", encoding="utf-8", newline="\n")
    partial.replace(path)
    return path


def read_inventory(step: Path) -> tuple[list[str], list[FaceGeometry]]:
    """The labels and selector geometry of ``step``'s inventory, which must bind
    that STEP's exact bytes."""
    step = Path(step)
    path = inventory_path(step)
    try:
        document = json.loads(path.read_text(encoding="utf-8"))
        content = step.read_bytes()
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise FeatureFaceError(f"{path}: unreadable face inventory ({exc})") from exc
    digest = hashlib.sha256(content).hexdigest()
    expected = (INVENTORY_SCHEMA, step.name, digest)
    recorded = (document.get("schema"), document.get("step"), document.get("step_sha256"))
    if recorded != expected:
        raise FeatureFaceError(f"{path}: records {recorded}, its STEP is {expected}")
    labels: list[str] = []
    geometries: list[FaceGeometry] = []
    for row in document.get("faces", ()):
        normal = row.get("outward_normal")
        labels.append(row["label"])
        geometries.append(
            FaceGeometry(
                None,
                int(row["identity"]),
                tuple(row["parameters"]),
                None if normal is None else tuple(normal),
                tuple(row["box"]),
            )
        )
    return labels, geometries


def bind_features(step: Path, selectors: Mapping[str, Sequence[Any]]) -> dict[str, list[str]]:
    """``{feature: [face_ref, ...]}`` for ``step`` from its face inventory.

    Each feature's claimed faces (in patch order) contribute every STEP face
    their labels carry, in file order.  No SolidWorks is involved."""
    labels, geometries = read_inventory(step)
    refs = step_label_refs(Path(step).read_bytes().decode("latin-1"), labels)
    assigned = assign_feature_patches(geometries, selectors)
    return {feature: [ref for index in indices for ref in refs[labels[index]]] for feature, indices in assigned.items()}


def step_feature_refs_valid(step_text: str, features: Mapping[str, Sequence[str]]) -> list[str]:
    """Problems with a manifest's recorded face sets against the exact STEP.

    Each ref must name an existing ``ADVANCED_FACE`` with that entity id,
    ordinal and label; a feature that names a label must name EVERY STEP face
    that label carries (a split periodic face is never half-bound); and no
    label may belong to two features."""
    faces = _ADVANCED_FACE.findall(step_text)
    by_label: dict[str, set[str]] = {}
    existing: set[str] = set()
    for ordinal, (entity, raw) in enumerate(faces, start=1):
        label = raw.replace("''", "'")
        ref = face_ref(int(entity), ordinal, label)
        existing.add(ref)
        by_label.setdefault(label, set()).add(ref)
    problems: list[str] = []
    owner: dict[str, str] = {}
    for feature, refs in features.items():
        unknown = sorted(set(refs) - existing)
        if unknown or len(set(refs)) != len(refs):
            problems.append(f"{feature} faces {list(refs)!r} name no or repeated STEP faces {unknown}")
            continue
        for label in {ref.rsplit("/", 1)[1] for ref in refs}:
            if owner.setdefault(label, feature) != feature:
                problems.append(f"{label}: claimed by features {sorted({owner[label], feature})}")
            if not by_label[label] <= set(refs):
                problems.append(f"{feature} faces omit STEP faces labelled {label!r}: {sorted(by_label[label] - set(refs))}")
    return problems
