"""Read-only same-session evidence; never a replacement attachment validator.

The source/selected/view entities may inhabit different native contexts. Record
both documented mapping directions and the original selected handle at each
stage. A null mapping, unknown IsSame result or read error remains evidence, not
permission to accept an attachment. There are no selection or document writes.
"""

from enum import StrEnum
from time import perf_counter

from _common import _early_bound
from diagnostics import probe_drawing_attachments as attachments


class EntityContextStage(StrEnum):
    SELECTED = "selected"
    IMMEDIATE = "immediate_native_validation"
    FINAL = "final_explicit_bank"


class EntityContextObservations:
    def __init__(self, labels, source_entities):
        self.labels = labels
        self.source_entities = source_entities
        self.selected = {}
        self.views = {}
        self.report = {
            "scope": "read-only mapping evidence; original native validators unchanged",
            "timing_scope": "timed read groups may contain several COM getters; included in recipe_seconds, not an uninstrumented performance result",
            "stages": [],
            "read_seconds_total": 0.0,
            "wall_seconds_total": 0.0,
        }

    def capture(
        self,
        adapter,
        view,
        argument,
        *,
        label,
        entity_type,
        stage,
        selected=None,
        annotation=None,
    ):
        stage = EntityContextStage(stage)
        role = self.labels[label]
        if stage == EntityContextStage.SELECTED:
            self.selected[role] = selected
            self.views[role] = view
        started = perf_counter()
        row = {
            "stage": stage.value,
            "role": role,
            "label": label,
            "entity_type": entity_type,
            "reads": {},
            "boundary": "after_original_selection"
            if stage == EntityContextStage.SELECTED
            else "before_original_validation",
        }
        self.report["stages"].append(row)

        def read(name, operation, *, handle=False):
            began = perf_counter()
            result = {"state": "interrupted"}
            try:
                value = operation()
                result = {"state": "null" if value is None else "value"}
                if not handle:
                    result["value"] = value
                return value
            except Exception as error:
                result = {"state": "error", "error": repr(error)}
                return None
            finally:
                result["seconds"] = perf_counter() - began
                row["reads"][name] = result

        def mapped(name, operation, *requirements):
            if any(value is None for value in requirements):
                row["reads"][name] = {
                    "state": "not_run",
                    "reason": "required native handle unavailable",
                    "seconds": 0.0,
                }
                return None
            return read(name, operation, handle=True)

        def same(name, first, second):
            if first is None or second is None:
                row["reads"][name] = {
                    "state": "not_run",
                    "reason": "required native handle unavailable",
                    "seconds": 0.0,
                }
                return
            read(name, lambda: int(adapter.swApp.IsSame(first, second)))

        source = self.source_entities[role]
        selected = self.selected.get(role)
        source_model = read(
            "source_model", lambda: view.ReferencedDocument, handle=True
        )
        if source_model is not None:
            read("source_path", lambda: str(source_model.GetPathName()))
            read("source_kind", lambda: int(source_model.GetType()))
            read(
                "source_configuration",
                lambda: str(source_model.ConfigurationManager.ActiveConfiguration.Name),
            )
        read("view_name", lambda: str(view.GetName2()))
        forward = read(
            "forward", lambda: view.GetCorrespondingEntity(source), handle=True
        )
        # The bundled corresponding-entities example invokes this on the PART
        # extension, not the drawing extension. Do not activate either document.
        extension = mapped(
            "source_extension",
            lambda: _early_bound(source_model.Extension, "IModelDocExtension"),
            source_model,
        )
        reverse_selected = mapped(
            "reverse_selected",
            lambda: extension.GetCorrespondingEntity2(selected),
            extension,
            selected,
        )
        attached = None
        if annotation is not None:
            annotation = read(
                "annotation",
                lambda: _early_bound(annotation, "IAnnotation"),
                handle=True,
            )
        if annotation is not None:
            read("annotation_name", lambda: str(annotation.GetName()))
            read("attachment_count", lambda: int(annotation.GetAttachedEntityCount3()))
            read(
                "attachment_types",
                lambda: tuple(annotation.GetAttachedEntityTypes() or ()),
            )
            native_attached = read(
                "attached_array",
                lambda: tuple(annotation.GetAttachedEntities3() or ()),
                handle=True,
            )
            if native_attached is not None:
                row["attachment_array_length"] = len(native_attached)
                row["attachment_nulls"] = [item is None for item in native_attached]
                if len(native_attached) == 1:
                    attached = native_attached[0]
            read("owner_type", lambda: int(annotation.OwnerType))
            owner = read("owner", lambda: annotation.Owner, handle=True)
            same("view_owner", view, owner)
        reverse_attached = mapped(
            "reverse_attached",
            lambda: extension.GetCorrespondingEntity2(attached),
            extension,
            attached,
        )

        for name, first, second in (
            ("source_argument", source, argument),
            ("source_selected", source, selected),
            ("source_forward", source, forward),
            ("selected_forward", selected, forward),
            ("source_reverse_selected", source, reverse_selected),
            ("source_attached", source, attached),
            ("selected_attached", selected, attached),
            ("forward_attached", forward, attached),
            ("source_reverse_attached", source, reverse_attached),
        ):
            same(name, first, second)
        if stage == EntityContextStage.SELECTED:
            manager = read(
                "selection_manager",
                lambda: _early_bound(
                    adapter.currentModel.SelectionManager, "ISelectionMgr"
                ),
                handle=True,
            )
            if manager is not None:
                count = read(
                    "selection_count", lambda: int(manager.GetSelectedObjectCount2(-1))
                )
                if count == 1:
                    current = read(
                        "selection_object",
                        lambda: manager.GetSelectedObject6(1, -1),
                        handle=True,
                    )
                    owner = read(
                        "selection_owner",
                        lambda: manager.GetSelectedObjectsDrawingView2(1, -1),
                        handle=True,
                    )
                    read(
                        "selection_type",
                        lambda: int(manager.GetSelectedObjectType3(1, -1)),
                    )
                    same("selected_current_selection", selected, current)
                    same("view_selection_owner", view, owner)
        native_kind = {"EDGE": 1, "FACE": 2, "SILHOUETTE": 46}[entity_type]
        for name, entity in (
            ("source", source),
            ("selected", selected),
            ("forward", forward),
            ("reverse_selected", reverse_selected),
            ("attached", attached),
            ("reverse_attached", reverse_attached),
        ):
            if entity is not None:
                read(
                    f"geometry_{name}",
                    lambda entity=entity: attachments.geometry(entity, native_kind),
                )
        row["read_seconds"] = sum(item["seconds"] for item in row["reads"].values())
        row["wall_seconds"] = perf_counter() - started
        self.report["read_seconds_total"] += row["read_seconds"]
        self.report["wall_seconds_total"] += row["wall_seconds"]
