"""Read-only acceptance for a recipe's exact model-scoped attachment roles.

The production validator executes unchanged. Its diagnostic observer records
which explicit roles were actually exercised, then rechecks them after the full
recipe and against freshly resolved source topology after cold reopen. It never
selects, inserts, moves, saves, or accepts an unsupported geometry exclusion.
"""

from contextlib import contextmanager
from enum import StrEnum

from _common import _early_bound
import _drawing_common as drawing
from _drawing_entities import FaceBoundary, FeatureFace, ModelEntities
from diagnostics import probe_drawing_attachments as attachments


class EntityWitnessPhase(StrEnum):
    BUILT = "built"
    REOPENED = "reopened"


class EntityAcceptance:
    def __init__(self, module, manifest):
        self.labels = manifest.entity_labels
        self.roles = module.ENTITY_ROLES
        if set(self.roles) != set(self.labels.values()):
            raise RuntimeError(
                "recipe entity roles differ from the acceptance manifest"
            )
        self.kinds = {}
        self.requests = dict(self.roles)
        for role, selector in self.roles.items():
            if isinstance(selector, FaceBoundary):
                self.kinds[role] = ("EDGE", 1)
                self.requests[f"face:{role}"] = selector.face
                continue
            if isinstance(selector, FeatureFace):
                self.kinds[role] = ("FACE", 2)
                self.requests[f"face:{role}"] = selector
                continue
            raise ValueError(f"{role}: unsupported acceptance selector {selector!r}")
        self.recorded = {}
        self.keys = {}
        self.validator = drawing._validate_explicit_annotation_attachment

    def source_snapshot(self, model):
        entities = ModelEntities(model).resolve(self.requests)
        rows = {
            role: {
                "entity": attachments.geometry(entities[role], self.kinds[role][1]),
                "controlled_face": attachments.geometry(entities[f"face:{role}"], 2),
            }
            for role in self.roles
        }
        return rows, entities

    @contextmanager
    def observe(self, adapter, source_entities):
        def validate(actual_adapter, annotation, view, entity, *, entity_type, label):
            self.validator(
                actual_adapter,
                annotation,
                view,
                entity,
                entity_type=entity_type,
                label=label,
            )
            if actual_adapter is not adapter or label not in self.labels:
                raise RuntimeError(f"unexpected explicit annotation witness {label!r}")
            role = self.labels[label]
            if role in self.recorded:
                raise RuntimeError(f"duplicate explicit annotation witness {role!r}")
            if entity_type != self.kinds[role][0]:
                raise RuntimeError(f"{role}: explicit attachment type changed")
            if int(adapter.swApp.IsSame(entity, source_entities[role])) != 1:
                raise RuntimeError(
                    f"{role}: explicit attachment is not its source role"
                )
            self.recorded[role] = (annotation, view, str(annotation.GetName()))

        if drawing._validate_explicit_annotation_attachment is not self.validator:
            raise RuntimeError(
                "explicit annotation validator changed before observation"
            )
        drawing._validate_explicit_annotation_attachment = validate
        try:
            yield
        finally:
            drawing._validate_explicit_annotation_attachment = self.validator

    def require_coverage(self):
        if self.recorded.keys() != self.roles.keys():
            raise RuntimeError(
                f"explicit annotation coverage mismatch: {sorted(self.recorded)} "
                f"!= {sorted(self.roles)}"
            )

    def drawing_snapshot(self, adapter, source_entities, *, phase):
        phase = EntityWitnessPhase(phase)
        self.require_coverage()
        inventory = {}
        for view in attachments.views(adapter.currentModel).values():
            for raw in view.GetAnnotations() or ():
                annotation = _early_bound(raw, "IAnnotation")
                key = (str(view.GetName2()), str(annotation.GetName()))
                if key in inventory:
                    raise RuntimeError(f"duplicate native annotation identity {key}")
                inventory[key] = (annotation, view)
        result = {}
        for role, (created, created_view, name) in self.recorded.items():
            key = (
                (str(created_view.GetName2()), name)
                if phase == EntityWitnessPhase.BUILT
                else self.keys[role]
            )
            if key not in inventory:
                raise RuntimeError(
                    f"{role}: expected explicit annotation is missing: {key}"
                )
            annotation, view = inventory[key]
            if phase == EntityWitnessPhase.BUILT and (
                int(adapter.swApp.IsSame(created, annotation)) != 1
                or int(adapter.swApp.IsSame(created_view, view)) != 1
            ):
                raise RuntimeError(f"{role}: final recipe replaced its annotation/view")
            expected_kind = (
                2 if role.startswith("datum:") else 7 if role == "bearing_finish" else 5
            )
            if int(annotation.GetType()) != expected_kind:
                raise RuntimeError(f"{role}: native annotation kind changed")
            self.validator(
                adapter,
                annotation,
                view,
                source_entities[role],
                entity_type=self.kinds[role][0],
                label=f"{phase} {role}",
            )
            result[role] = {
                "view": key[0],
                "name": name,
                "kind": expected_kind,
                "entity_kind": self.kinds[role][1],
                "geometry": attachments.geometry(
                    annotation.GetAttachedEntities3()[0], self.kinds[role][1]
                ),
            }
        if phase == EntityWitnessPhase.BUILT:
            self.keys = {
                role: (row["view"], row["name"]) for role, row in result.items()
            }
        return result
