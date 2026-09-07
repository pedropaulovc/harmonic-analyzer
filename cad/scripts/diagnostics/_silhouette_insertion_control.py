"""Retain the historical SF silhouette insertion/rebuild negative control.

Two small proactive identity banks are necessary to observe pre-failure state.
Full geometry and fresh role resolution run only after the production validator
rejects. Nothing here can accept a rejected identity or replace its exception.
Current spring/journal roles use FACE and deliberately do not enroll here; the
frozen native repro and explicit historical test manifests retain this path.
"""

from contextlib import contextmanager
from functools import wraps
import time

from _common import _early_bound
import _drawing_common as drawing
import _drawing_silhouette_identity as persistent
from diagnostics import _silhouette_attachment_witness as silhouette
from diagnostics._owned_native_documents import Ownership
from diagnostics._recipe_view_roles import ViewResolver
from diagnostics._silhouette_identity_control import _capture, _dirty_flags, _reference


class InsertionBoundaries:
    def __init__(self, observer, adapter):
        self.observer, self.adapter = observer, adapter
        self.initial = {}

    def supports(self, label):
        role = self.observer.roles.get(label)
        return (
            role is not None
            and role.entity_kind == 46
            and role.annotation_kind == 7
            and role.resolver in (ViewResolver.JOURNAL, ViewResolver.SHANK)
        )

    def records(self, label):
        return self.observer.context_report.setdefault(
            "silhouette_insertion_boundaries", {}
        ).setdefault(label, {})

    def sample(self, label, phase, read):
        row = self.records(label)[phase] = {}
        started = time.perf_counter()
        models = {}
        try:
            adapter = self.adapter
            drawing_record = adapter.ownership.assert_current_owned()
            model = _early_bound(adapter.currentModel, "IModelDoc2")
            kind = model.GetType()
            if type(kind) is not int or kind != 3:
                raise RuntimeError(
                    "insertion capture requires the current owned drawing"
                )
            _, _, view = self.observer.selected[label]
            source = _early_bound(view.ReferencedDocument, "IModelDoc2")
            source_record = adapter.ownership._record(source)
            if source_record is None or source_record.ownership is not Ownership.COPY:
                raise RuntimeError("insertion capture requires an owned source copy")
            kind = source.GetType()
            if type(kind) is not int or kind != 1:
                raise RuntimeError("insertion source copy is not a part")
            models = {"drawing": model, "source": source}
            row["source_path"] = source.GetPathName()
            errors = _dirty_flags(models, row, "before")
            if errors:
                raise errors[0]

            def require_context():
                if adapter.ownership.assert_current_owned() is not drawing_record:
                    raise RuntimeError("fresh resolver changed owned drawing record")
                if (
                    adapter.ownership._record(source) is not source_record
                    or source_record.ownership is not Ownership.COPY
                ):
                    raise RuntimeError("fresh resolver changed owned source record")
                # Reuse the observer's existing native drawing-view inventory.
                from diagnostics.probe_drawing_attachments import views

                native_views = views(model)
                results = [
                    adapter.swApp.IsSame(view, current)
                    for current in native_views.values()
                ]
                if (
                    any(
                        type(value) is not int or value not in (0, 1)
                        for value in results
                    )
                    or results.count(1) != 1
                ):
                    raise RuntimeError(
                        "fresh resolver original view is not uniquely in captured drawing"
                    )
                for scope, first, second in (
                    ("source", source, view.ReferencedDocument),
                    ("current drawing", model, adapter.currentModel),
                    ("active drawing", model, adapter.swApp.ActiveDoc),
                ):
                    if first is None or second is None:
                        raise RuntimeError(f"fresh resolver has null {scope}")
                    result = adapter.swApp.IsSame(first, second)
                    if type(result) is not int or result != 1:
                        raise RuntimeError(f"fresh resolver changed exact {scope}")
                # No intervening observation between this final ownership check
                # and the resolver (SHANK can call ActivateView).
                if adapter.ownership.assert_current_owned() is not drawing_record:
                    raise RuntimeError("fresh resolver changed current ownership")

            read(
                row,
                _early_bound(model.Extension, "IModelDocExtension"),
                require_context,
            )
        except Exception as error:
            row["capture_error"] = repr(error)
        finally:
            _dirty_flags(models, row, "after")
            try:
                self.adapter.ownership.assert_current_owned()
                if (
                    models
                    and self.adapter.swApp.IsSame(
                        models["drawing"], self.adapter.currentModel
                    )
                    != 1
                ):
                    raise RuntimeError("insertion capture replaced current drawing")
            except Exception as error:
                row["final_ownership_error"] = repr(error)
            row["seconds"] = time.perf_counter() - started

    def identities(self, extension, entities, row, *, stored=None):
        references = dict(stored or {})
        for name, entity in entities.items():
            if entity is None:
                row[f"reference.{name}"] = {"error": "null native entity"}
                continue
            _capture(
                row,
                f"native_self.{name}",
                lambda e=entity: self.adapter.swApp.IsSame(e, e),
            )
            reference = _capture(
                row,
                f"reference.{name}",
                lambda e=entity, n=name: _reference(extension, e, row, n),
            )
            if reference is not None:
                references[name] = reference
        names = tuple(references)
        for index, first in enumerate(names):
            for second in names[index:]:
                # Keep stored-reference self controls at each boundary, but do
                # not repeat old/old cross-pairs when adding fresh handles.
                if (
                    entities
                    and first != second
                    and first not in entities
                    and second not in entities
                ):
                    continue
                _capture(
                    row,
                    f"persistent.{first}.{second}",
                    lambda a=first, b=second: extension.IsSamePersistentID(
                        persistent.byte_variant(references[a]),
                        persistent.byte_variant(references[b]),
                    ),
                )
        return references

    def selected(self, label, selection_row):
        if not self.supports(label):
            return
        # These exact bytes were already read by the successful selection gate.
        # Stored bytes are compared only with the native document comparator.
        bank = selection_row["silhouette"]["persistent_identity"]
        self.initial[label] = {
            f"pre_insert_{name}": bank[name]["reference"]
            for name in ("expected", "actual")
        }

        def read(row, extension, _require_context):
            expected, selected, _ = self.observer.selected[label]
            row["stored_selection_references"] = self.initial[label]
            for name, entity in (("expected", expected), ("selected", selected)):
                _capture(
                    row,
                    f"native_self.{name}",
                    lambda e=entity: self.adapter.swApp.IsSame(e, e),
                )
            self.identities(extension, {}, row, stored=self.initial[label])

        self.sample(label, "pre_insert_self", read)

    def attachment(self, annotation, row):
        annotation = _early_bound(annotation, "IAnnotation")
        kinds = annotation.GetAttachedEntityTypes()
        entities = annotation.GetAttachedEntities3()
        count = annotation.GetAttachedEntityCount3()
        row.update(attachment_types=kinds, attachment_count=count)
        if (
            not isinstance(kinds, (tuple, list))
            or tuple(kinds) != (46,)
            or not isinstance(entities, (tuple, list))
            or len(entities) != 1
            or entities[0] is None
            or type(count) is not int
            or count != 1
        ):
            raise RuntimeError("capture needs one complete SILHOUETTE attachment")
        return entities[0]

    def before_rebuild(self, label, annotation):
        def read(row, extension, _require_context):
            expected, selected, _ = self.observer.selected[label]
            attached = self.attachment(annotation, row)
            self.identities(
                extension,
                {"expected": expected, "selected": selected, "attached": attached},
                row,
                stored=self.initial[label],
            )

        self.sample(label, "post_style_pre_rebuild", read)

    def rejected(self, label, annotation, predicate_entities):
        def read(row, extension, require_context):
            expected, selected, view = self.observer.selected[label]
            attached = self.attachment(annotation, row)
            entities = {
                "expected": expected,
                "selected": selected,
                "attached": attached,
            }
            if predicate_entities:
                entities["predicate_attached"] = predicate_entities[1]
            row["view_name"] = view.GetName2()
            row["view_orientation"] = view.GetOrientationName()
            # Capture old wrappers before even the known fresh resolver runs.
            # In particular SHANK's existing ActivateView is a later boundary.
            references = self.identities(
                extension, entities, row, stored=self.initial[label]
            )
            faces = {}
            if label in self.observer.initial_faces:
                faces["pre_insert_selected"] = self.observer.initial_faces[label]

            def raw(name, entity):
                _capture(
                    row,
                    f"view_same.{name}",
                    lambda: self.adapter.swApp.IsSame(
                        _early_bound(entity, "ISilhouetteEdge").GetView(), view
                    ),
                )

                def geometry():
                    result, face = silhouette.snapshot(self.adapter.swApp, view, entity)
                    faces[name] = face
                    return result

                _capture(row, f"geometry.{name}", geometry)

            for name, entity in entities.items():
                raw(name, entity)
            role = self.observer.roles[label]
            row["fresh_resolver"] = {
                "name": role.resolver.value,
                "scope": "existing resolver; activates witnessed view"
                if role.resolver is ViewResolver.SHANK
                else "existing getter-only resolver",
            }
            fresh_started = time.perf_counter()
            try:
                require_context()
                fresh = role.resolve(self.observer.module, self.adapter, view)
                require_context()
                fresh_row = row["fresh_identity"] = {}
                self.identities(
                    extension, {"fresh": fresh}, fresh_row, stored=references
                )
                raw("fresh", fresh)
            except Exception as error:
                row["fresh_resolver"]["error"] = repr(error)
            finally:
                row["fresh_resolver"]["seconds"] = time.perf_counter() - fresh_started
            names = tuple(faces)
            for index, first in enumerate(names):
                for second in names[index:]:
                    _capture(
                        row,
                        f"face_same.{first}.{second}",
                        lambda a=first, b=second: self.adapter.swApp.IsSame(
                            faces[a], faces[b]
                        ),
                    )

        self.sample(label, "rejected_post_rebuild", read)

    @contextmanager
    def observe(self):
        original_style = drawing._style_surface_finish
        original_validator = drawing._validate_explicit_annotation_attachment

        @wraps(original_style)
        def styled(adapter, symbol, annotation, *, label):
            result = original_style(adapter, symbol, annotation, label=label)
            if adapter is self.adapter and self.supports(label):
                self.before_rebuild(label, annotation)
            return result

        @wraps(original_validator)
        def validated(adapter, annotation, view, entity, **kwargs):
            label = kwargs["label"]
            if adapter is not self.adapter or not self.supports(label):
                return original_validator(adapter, annotation, view, entity, **kwargs)
            records = self.records(label)
            evidence = records["production_predicate"] = {}
            original_same = persistent.require_same
            predicate_entities = []

            def recorded_same(model, expected, actual, *, label, evidence=None):
                predicate_entities[:] = (expected, actual)
                actual_evidence = (
                    records["production_predicate"] if evidence is None else evidence
                )
                return original_same(
                    model, expected, actual, label=label, evidence=actual_evidence
                )

            started = time.perf_counter()
            try:
                persistent.require_same = recorded_same
                return original_validator(adapter, annotation, view, entity, **kwargs)
            except Exception as error:
                evidence["original_error"] = repr(error)
                evidence["validator_seconds"] = time.perf_counter() - started
                # Restore before secondary capture; never retry the acceptance predicate.
                persistent.require_same = original_same
                try:
                    self.rejected(label, annotation, predicate_entities)
                except Exception as capture_error:
                    records["capture_error"] = repr(capture_error)
                raise
            finally:
                persistent.require_same = original_same
                evidence.setdefault("validator_seconds", time.perf_counter() - started)
                evidence["seconds_including_failure_capture"] = (
                    time.perf_counter() - started
                )

        try:
            drawing._style_surface_finish = styled
            drawing._validate_explicit_annotation_attachment = validated
            yield
        finally:
            drawing._style_surface_finish = original_style
            drawing._validate_explicit_annotation_attachment = original_validator
