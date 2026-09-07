"""Exact VIEW→selection→attachment observer for existing recipe call sites.

Production selectors/validators run unchanged. The explicit origin manifest
does not claim coordinate-picked annotations were migrated. Their normal
snapshot remains authoritative; observed type46 calls also receive exact
selection/attachment persistent-identity and raw geometry evidence here.
"""

from contextlib import contextmanager
from functools import wraps
import time

from _common import _early_bound
import _drawing_common as drawing
from diagnostics import probe_drawing_attachments as attachments
from diagnostics import _silhouette_attachment_witness as silhouette
from diagnostics import _view_intersection_curve_witness as intersection
from diagnostics._recipe_entity_acceptance import EntityWitnessPhase
from diagnostics._recipe_view_roles import ViewResolver
from diagnostics._view_curve_cold_identity import ColdIntersectionIdentities


def geometry(app, view, entity, kind, *, evidence=None):
    if kind == 46:
        return silhouette.snapshot(app, view, entity)[0]
    try:
        result = attachments.geometry(entity, kind)
    except attachments.UnsupportedGeometry:
        if kind != 1:
            raise
        return intersection.snapshot(entity, evidence if evidence is not None else {})
    if result[0] == "line" and kind == 1:
        if len(result[1]) != 2:
            raise RuntimeError("VIEW edge line needs exactly two endpoints")
        for point in result[1]:
            silhouette.finite_array(point, 3, label="VIEW line endpoint")
        return result
    if result[0] == "circle" and kind == 1:
        for raw, size in zip(result[1:], (7, 2, 3, 3), strict=True):
            silhouette.finite_array(raw, size, label="VIEW circular edge")
        return result
    if result[0] == "face" and kind == 2 and result[1] in (4001, 4002):
        silhouette.finite_array(
            result[2], 6 if result[1] == 4001 else 7, label="VIEW face parameters"
        )
        silhouette.finite_array(result[3], 6, label="VIEW face box")
        if result[4] is not None:
            silhouette.finite_array(result[4], 3, label="VIEW face normal")
        return result
    raise RuntimeError(f"unsupported VIEW role geometry {kind}: {result!r}")


class ViewEntityAcceptance:
    def __init__(self, module, manifest):
        self.module = module
        self.roles = manifest.view_roles
        if not self.roles or manifest.entity_labels:
            raise ValueError(
                "VIEW observer requires only an explicit VIEW role manifest"
            )
        self.recorded = {}
        self.coordinate = {}
        self.selected = {}
        self.initial_geometry = {}
        self.initial_faces = {}
        self.keys = {}
        self.cold_intersections = ColdIntersectionIdentities()
        self.context_report = {"context": "view", "stages": []}

    @contextmanager
    def stage(self, label, phase):
        row = {"label": label, "stage": phase}
        self.context_report["stages"].append(row)
        started = time.perf_counter()
        try:
            yield row
        except BaseException as error:
            row["error"] = repr(error)
            raise
        finally:
            row["seconds"] = time.perf_counter() - started

    def _attachment(self, adapter, view, annotation, expected, kind, row):
        if int(annotation.OwnerType) != 0:
            raise RuntimeError("VIEW annotation is not view-owned")
        silhouette.same(
            adapter.swApp, annotation.Owner, view, label="annotation view owner"
        )
        entities = annotation.GetAttachedEntities3()
        kinds = annotation.GetAttachedEntityTypes()
        row["attachment_types"] = kinds
        row["attachment_count"] = annotation.GetAttachedEntityCount3()
        if (
            not isinstance(entities, (list, tuple))
            or len(entities) != 1
            or not isinstance(kinds, (list, tuple))
            or any(type(value) is not int for value in kinds)
            or tuple(kinds) != (kind,)
            or type(row["attachment_count"]) is not int
            or row["attachment_count"] != 1
        ):
            raise RuntimeError("VIEW annotation needs one exact typed attachment")
        attached = entities[0]
        if kind == 46 and expected is not None:
            row["geometry"] = silhouette.require_same(
                adapter.swApp,
                view,
                expected,
                attached,
                drawing=adapter.currentModel,
                label="VIEW attachment",
                evidence=row.setdefault("silhouette", {}),
            )
        else:
            row["geometry"] = geometry(
                adapter.swApp,
                view,
                attached,
                kind,
                evidence=row.setdefault("curve_read", {}),
            )
            if expected is not None:
                silhouette.same(
                    adapter.swApp,
                    expected,
                    attached,
                    label="VIEW argument/attached entity",
                )
        label = row["label"]
        if (
            label in self.initial_faces
            and row["stage"] != EntityWitnessPhase.REOPENED.value
        ):
            attached_face = _early_bound(attached, "ISilhouetteEdge").GetFace()
            silhouette.same(
                adapter.swApp,
                self.initial_faces[label],
                attached_face,
                label="initial/attached silhouette face",
            )
        drawing._validate_native_pmi_placement(
            adapter, annotation, label="VIEW native placement"
        )
        return row["geometry"]

    @contextmanager
    def observe(self, adapter, unused_source_entities=None):
        from diagnostics._silhouette_insertion_control import InsertionBoundaries

        insertion = InsertionBoundaries(self, adapter)
        original_select = drawing._select_annotation_entity
        originals = {
            name: getattr(drawing, name)
            for name in (
                "add_datum_feature",
                "add_feature_control_frame",
                "add_surface_finish",
            )
        }
        patches = []

        def selected(actual_adapter, view, **kwargs):
            result = original_select(actual_adapter, view, **kwargs)
            label = kwargs["label"]
            if label not in self.roles:
                return result
            with self.stage(label, "selected") as row:
                if actual_adapter is not adapter or label in self.selected:
                    raise RuntimeError("unexpected/duplicate VIEW selection")
                expected = kwargs.get("entity")
                if expected is None:
                    expected = kwargs.get("edge_entity")
                role = self.roles[label]
                if (
                    str(view.GetOrientationName()) != role.orientation
                    or kwargs["entity_type"] != role.entity_type
                ):
                    raise RuntimeError("VIEW role orientation/type changed")
                manager = _early_bound(
                    adapter.currentModel.SelectionManager, "ISelectionMgr"
                )
                row["selected_count"] = manager.GetSelectedObjectCount2(-1)
                if type(row["selected_count"]) is not int or row["selected_count"] != 1:
                    raise RuntimeError("VIEW selection count is not exactly one")
                row["selected_kind"] = manager.GetSelectedObjectType3(1, -1)
                actual = manager.GetSelectedObject6(1, -1)
                if (
                    type(row["selected_kind"]) is not int
                    or row["selected_kind"] != role.entity_kind
                ):
                    raise RuntimeError("VIEW selection kind changed")
                if role.entity_kind == 46:
                    try:
                        silhouette.require_same(
                            adapter.swApp,
                            view,
                            expected,
                            actual,
                            drawing=adapter.currentModel,
                            label="VIEW selection",
                            evidence=row.setdefault("silhouette", {}),
                        )
                    except RuntimeError:
                        from diagnostics._silhouette_identity_control import capture

                        capture(adapter, view, expected, actual, row)
                        raise
                    row["argument_geometry"] = row["silhouette"]["expected"]
                    row["selected_geometry"] = row["silhouette"]["actual"]
                    self.initial_faces[label] = _early_bound(
                        actual, "ISilhouetteEdge"
                    ).GetFace()
                    if self.initial_faces[label] is None:
                        raise RuntimeError("selected silhouette face became null")
                else:
                    row["argument_geometry"] = geometry(
                        adapter.swApp,
                        view,
                        expected,
                        role.entity_kind,
                        evidence=row.setdefault("argument_curve_read", {}),
                    )
                    row["selected_geometry"] = geometry(
                        adapter.swApp,
                        view,
                        actual,
                        role.entity_kind,
                        evidence=row.setdefault("selected_curve_read", {}),
                    )
                    silhouette.same(
                        adapter.swApp,
                        expected,
                        actual,
                        label="VIEW argument/actual selection",
                    )
                self.initial_geometry[label] = row["selected_geometry"]
                self.selected[label] = (expected, actual, view)
                insertion.selected(label, row)
            return result

        def wrap(name, original):
            @wraps(original)
            def created(actual_adapter, view, **kwargs):
                label = kwargs["label"]
                explicit = (
                    kwargs.get("entity") is not None
                    or kwargs.get("edge_entity") is not None
                )
                if explicit != (label in self.roles):
                    raise RuntimeError(
                        f"unmanifested/missing explicit VIEW call {label!r}"
                    )
                if actual_adapter is not adapter:
                    raise RuntimeError("VIEW insertion changed adapter")
                if (
                    kwargs.get("entity_context", drawing.AnnotationEntityContext.VIEW)
                    != drawing.AnnotationEntityContext.VIEW
                ):
                    raise RuntimeError(
                        "VIEW observer cannot accept MODEL insertion context"
                    )
                result = original(actual_adapter, view, **kwargs)
                annotation = _early_bound(result.GetAnnotation(), "IAnnotation")
                if annotation is None:
                    raise RuntimeError(f"{label}: inserted annotation is null")
                if not explicit:
                    if label in self.coordinate:
                        raise RuntimeError(f"duplicate coordinate annotation {label!r}")
                    self.coordinate[label] = (
                        annotation,
                        view,
                        kwargs.get("entity_type", "EDGE"),
                    )
                    return result
                with self.stage(label, "inserted") as row:
                    if label in self.recorded or label not in self.selected:
                        raise RuntimeError(
                            "VIEW insertion lacks exactly one observed selection"
                        )
                    expected, actual, selected_view = self.selected[label]
                    silhouette.same(
                        adapter.swApp,
                        view,
                        selected_view,
                        label="VIEW selected/insertion view",
                    )
                    role = self.roles[label]
                    if int(annotation.GetType()) != role.annotation_kind:
                        raise RuntimeError("VIEW inserted annotation kind changed")
                    self._attachment(
                        adapter, view, annotation, actual, role.entity_kind, row
                    )
                    self.recorded[label] = (annotation, view, expected)
                return result

            return created

        try:
            drawing._select_annotation_entity = selected
            for name, original in originals.items():
                replacement = wrap(name, original)
                for owner in (drawing, self.module):
                    if not hasattr(owner, name):
                        continue
                    if getattr(owner, name) is not original:
                        raise RuntimeError(f"recipe has an unexpected {name} alias")
                    patches.append((owner, name, original))
                    setattr(owner, name, replacement)
            with insertion.observe():
                yield
        finally:
            for owner, name, original in reversed(patches):
                setattr(owner, name, original)
            drawing._select_annotation_entity = original_select

    def require_coverage(self):
        if (
            self.recorded.keys() != self.roles.keys()
            or self.selected.keys() != self.roles.keys()
        ):
            raise RuntimeError(
                f"incomplete VIEW role coverage: {sorted(self.recorded)} != {sorted(self.roles)}"
            )

    def drawing_snapshot(self, adapter, unused_source_entities=None, *, phase):
        phase = EntityWitnessPhase(phase)
        self.require_coverage()
        inventory = {}
        for view in attachments.views(adapter.currentModel).values():
            for raw in view.GetAnnotations() or ():
                annotation = _early_bound(raw, "IAnnotation")
                key = (str(view.GetName2()), str(annotation.GetName()))
                if key in inventory:
                    raise RuntimeError(f"duplicate VIEW annotation key {key}")
                inventory[key] = (annotation, view)
        result = {"explicit": {}, "coordinate_picked": {}}
        for label, (created, created_view, expected) in self.recorded.items():
            with self.stage(label, phase.value) as row:
                key = self._key(adapter, label, created, created_view, inventory, phase)
                annotation, view = inventory[key]
                role = self.roles[label]
                if (
                    str(view.GetOrientationName()) != role.orientation
                    or int(annotation.GetType()) != role.annotation_kind
                ):
                    raise RuntimeError(
                        f"{label}: VIEW annotation type/orientation changed"
                    )
                row["resolver"] = role.resolver.value
                row["resolver_side_effect"] = (
                    "activate_view"
                    if role.resolver in (ViewResolver.SHANK, ViewResolver.SHANK_FACE)
                    else "none"
                )
                resolved = role.resolve(self.module, adapter, view)
                if resolved is None:
                    raise RuntimeError(f"{label}: fresh VIEW role resolved null")
                if phase == EntityWitnessPhase.BUILT:
                    if role.entity_kind == 46:
                        silhouette.persistent.require_same(
                            adapter.currentModel, expected, resolved,
                            label=f"{label} original/fresh silhouette role",
                            evidence=row.setdefault("original_fresh_persistent_identity", {}),
                        )
                    else:
                        silhouette.same(
                            adapter.swApp,
                            expected,
                            resolved,
                            label=f"{label} original/fresh role",
                        )
                raw = self._attachment(
                    adapter, view, annotation, resolved, role.entity_kind, row
                )
                if (
                    phase == EntityWitnessPhase.BUILT
                    and raw != self.initial_geometry[label]
                ):
                    row["initial_geometry"] = self.initial_geometry[label]
                    raise RuntimeError(
                        f"{label}: raw VIEW geometry changed since selection"
                    )
                if role.entity_kind == 1 and raw[0] == "intersection_curve":
                    self.cold_intersections.observe(
                        adapter, label, key, resolved, raw,
                        phase=phase.value,
                        evidence=row.setdefault("cold_edge_identity", {}),
                    )
                result["explicit"][label] = {
                    "key": key,
                    "kind": role.entity_kind,
                    "geometry": raw,
                }
        for label, (created, created_view, entity_type) in self.coordinate.items():
            key = self._key(adapter, label, created, created_view, inventory, phase)
            row = {
                "key": key,
                "origin": "coordinate_pick_not_migrated",
                "requested_entity_type": entity_type,
            }
            if entity_type == "SILHOUETTE":
                annotation, view = inventory[key]
                with self.stage(
                    label, f"{phase.value}_coordinate_silhouette"
                ) as evidence:
                    row["geometry"] = self._attachment(
                        adapter, view, annotation, None, 46, evidence
                    )
            result["coordinate_picked"][label] = row
        return result

    def compare_cold(self, before, after):
        """Keep raw banks; classify only native-proved cold curve-ID metadata."""
        return self.cold_intersections.compare(before, after)

    def _key(self, adapter, label, created, created_view, inventory, phase):
        key = (
            (str(created_view.GetName2()), str(created.GetName()))
            if phase == EntityWitnessPhase.BUILT
            else self.keys[label]
        )
        if key not in inventory:
            raise RuntimeError(f"missing VIEW annotation role {label}: {key}")
        if phase == EntityWitnessPhase.BUILT:
            annotation, view = inventory[key]
            silhouette.same(
                adapter.swApp, created, annotation, label="built VIEW annotation"
            )
            silhouette.same(adapter.swApp, created_view, view, label="built VIEW view")
            self.keys[label] = key
        return key
