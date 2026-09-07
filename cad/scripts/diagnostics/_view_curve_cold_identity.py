"""Cold identity for captured INTERSECTION_TYPE edges, never a geometry waiver.

Raw banks retain CurveTag. Only the cold caller may classify its changed integer
as metadata after the drawing's native persistent-ID comparator proves the same
edge. Live IsSame/full-raw checks remain in ViewEntityAcceptance unchanged.
"""

from copy import deepcopy
from pathlib import Path

from _common import _early_bound
import _drawing_silhouette_identity as persistent
from diagnostics._reopen_annotation_comparison import compare_reopened_annotations
from diagnostics.audit_drawing_snapshot_delta import _pointer


class ColdIntersectionIdentities:
    def __init__(self):
        self._built = {}
        self._reopened = {}

    def observe(self, adapter, label, key, entity, geometry, *, phase, evidence):
        """Called only after fresh owner/type/expected-to-attached IsSame checks.

        Keep bytes and value records, not old native document/entity wrappers.
        The caller separately pins source/configuration and the saved drawing.
        """
        if phase not in ("built", "reopened"):
            raise ValueError("unsupported intersection identity phase")
        if (
            type(geometry) is not tuple
            or len(geometry) != 2
            or geometry[0] != "intersection_curve"
            or type(geometry[1]) is not dict
            or type(geometry[1].get("identity")) is not int
            or geometry[1]["identity"] != 3004
        ):
            raise ValueError(
                "cold edge identity only supports captured INTERSECTION_TYPE"
            )
        records = self._built if phase == "built" else self._reopened
        if label in records:
            raise RuntimeError("duplicate intersection identity observation")
        model = _early_bound(adapter.currentModel, "IModelDoc2")
        kind, path = model.GetType(), str(model.GetPathName())
        evidence.update(drawing_path=path, drawing_kind=kind, phase=phase)
        if (
            type(kind) is not int
            or kind != 3
            or not path
            or not Path(path).is_absolute()
        ):
            raise RuntimeError("intersection identity requires the saved drawing")
        path = str(Path(path).resolve())
        first = self._built.get(label)
        if phase == "reopened" and (
            first is None or first["drawing_path"] != path or first["key"] != key
        ):
            raise RuntimeError(
                "cold intersection drawing/annotation differs from built"
            )
        if entity is None:
            raise RuntimeError("intersection identity cannot reference a null edge")
        extension = _early_bound(model.Extension, "IModelDocExtension")
        raw_reference = extension.GetPersistReference3(entity)
        evidence["return_type"] = type(raw_reference).__name__
        reference = persistent.byte_reference(raw_reference)
        evidence["reference"] = reference
        result = extension.IsSamePersistentID(
            persistent.byte_variant(reference), persistent.byte_variant(reference)
        )
        evidence["self_result"] = result
        if type(result) is not int or result != 1:
            raise RuntimeError(f"native persistent self-comparison returned {result!r}")
        if phase == "reopened":
            result = extension.IsSamePersistentID(
                persistent.byte_variant(first["reference"]),
                persistent.byte_variant(reference),
            )
            evidence["cross_cold_result"] = result
            if type(result) is not int or result != 1:
                raise RuntimeError(
                    f"native persistent cold comparison returned {result!r}"
                )
        # Publication follows all native checks. A caught failure cannot confer
        # permission to classify a later raw-bank difference as metadata.
        records[label] = {
            "drawing_path": path,
            "reference": reference,
            "key": deepcopy(key),
            "bank": {"key": deepcopy(key), "kind": 1, "geometry": deepcopy(geometry)},
        }

    def compare(self, before, after):
        """Exact cold bank comparison except proved integer CurveTag observations."""
        exact = compare_reopened_annotations(before, after)
        if exact["coordinate_roundoff"] or exact["zero_z_serialization"]:
            raise RuntimeError(
                "explicit entity bank unexpectedly used a coordinate budget"
            )
        allowed = {}
        for label, first in self._built.items():
            last = self._reopened.get(label)
            if last is None:
                continue
            if (
                before.get("explicit", {}).get(label) != first["bank"]
                or after.get("explicit", {}).get(label) != last["bank"]
            ):
                continue
            allowed[
                _pointer(("explicit", label, "geometry", 1, "trim", "CurveTag"))
            ] = label
        rejected, observations = [], []
        for change in exact["rejected"]:
            if (
                change["path"] in allowed
                and change["kind"] == "numeric"
                and type(change["before"]) is int
                and type(change["after"]) is int
            ):
                observations.append(
                    {**change, "native_cross_cold_edge_identity": "same"}
                )
                continue
            rejected.append(change)
        return {
            "status": "failed" if rejected else "passed",
            "rejected": rejected,
            "curve_tag_observations": observations,
            "scope": "explicit banks exact except native-PID-proven intersection CurveTag metadata; raw banks unchanged",
        }
