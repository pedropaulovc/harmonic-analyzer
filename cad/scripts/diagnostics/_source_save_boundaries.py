"""Read-only alignment source presentation banks around unchanged recipe writes.

Only the required source dimension is calibrated, once, through its named
feature. Cached display handles are checked against freshly resolved IDimensions
at every boundary. This is not a complete source annotation/BREP inventory.
Disk drift is recorded here, not authorized: the pilot's existing after_recipe
and final immutable-copy gates still reject it after retaining both save banks.
"""

from contextlib import contextmanager, nullcontext
from enum import StrEnum
from functools import wraps
from pathlib import Path
import math
import sys
import time

from _common import _early_bound
import _drawing_common as drawing
from diagnostics import probe_drawing_attachments as attachments
from diagnostics._source_dimension_snapshot import finite, tolerance


class SourceObservation(StrEnum):
    ALIGNMENT_SAVE = "alignment_save"


STAGES = ("callouts", "precision", "native_save", "pdf_export")
DIMENSION = "ArborBoreDia@ArborBoreProfile"


def require_targets(variant, order):
    if variant is not None and (
        SourceObservation(variant) != SourceObservation.ALIGNMENT_SAVE
        or tuple(order) != ("alignment_pinion",)
    ):
        raise ValueError("source boundary control requires only alignment_pinion")


class SourceSaveBoundaries:
    def __init__(
        self, adapter, module, trial, checkpoint, source, before, handles, reader
    ):
        self.adapter, self.module, self.source = adapter, module, source
        self.path = Path(trial["copy_source"]).resolve()
        self.before, self.handles, self.reader = before, handles, reader
        self.checkpoint = checkpoint
        self.stages = []
        self.display = None
        self.initial_tolerance = None
        self.initial_display_type = None
        self.initial_value = None
        self.report = trial["source_boundaries"] = {
            "variant": SourceObservation.ALIGNMENT_SAVE.value,
            "source": str(self.path),
            "scope": "one named source display; no generic annotation/BREP scan; no save-policy change",
            "banks": [],
        }
        if set(handles) != {DIMENSION} or set(before["dimensions"]) != {DIMENSION}:
            raise RuntimeError(
                "source boundary control requires exact alignment dimension manifest"
            )

    def _same(self, expected, actual, label):
        if (
            expected is None
            or actual is None
            or int(self.adapter.swApp.IsSame(expected, actual)) != 1
        ):
            raise RuntimeError(f"source boundary {label} identity changed")

    def _calibrate(self):
        feature = _early_bound(
            _early_bound(self.source, "IPartDoc").FeatureByName("ArborBoreProfile"),
            "IFeature",
        )
        if feature is None or feature.Name != "ArborBoreProfile":
            raise RuntimeError("source boundary has no exact ArborBoreProfile feature")
        display, seen, matches = feature.GetFirstDisplayDimension(), [], []
        while display is not None:
            display = _early_bound(display, "IDisplayDimension")
            if len(seen) >= 64 or any(
                int(self.adapter.swApp.IsSame(display, old)) == 1 for old in seen
            ):
                raise RuntimeError("source display calibration repeats/exceeds bound")
            seen.append(display)
            dimension = _early_bound(display.GetDimension2(0), "IDimension")
            if dimension is None:
                raise RuntimeError("source display calibration returned null dimension")
            if dimension.FullName == self.before["dimensions"][DIMENSION]["full_name"]:
                self._same(self.handles[DIMENSION], dimension, "calibrated dimension")
                matches.append(display)
            display = feature.GetNextDisplayDimension(display)
        self.report["calibration_display_count"] = len(seen)
        if len(matches) != 1:
            raise RuntimeError(
                "source boundary needs one unambiguous observed source display"
            )
        self.display = matches[0]

    def capture(self, label):
        row = {"boundary": label}
        self.report["banks"].append(row)
        started = time.perf_counter()
        try:
            row["dirty_before_read"] = self.source.GetSaveFlag()
            row["disk_sha256"] = attachments.file_digest(self.path)
            self._same(
                self.source,
                self.adapter.swApp.GetOpenDocumentByName(str(self.path)),
                "document",
            )
            values, handles = self.reader()
            row["source"] = values
            nominal = values["dimensions"][DIMENSION]["value_system"]
            if type(nominal) not in (int, float) or not math.isfinite(nominal):
                raise RuntimeError("source boundary nominal is not finite numeric data")
            if values != self.before or handles.keys() != self.handles.keys():
                raise RuntimeError("source boundary parameters/tolerance/BASIC changed")
            for name, handle in handles.items():
                self._same(self.handles[name], handle, "parameter")
            if self.display is None:
                self._calibrate()
            dimension = _early_bound(self.display.GetDimension2(0), "IDimension")
            self._same(self.handles[DIMENSION], dimension, "display parameter")
            # swSpecifyConfiguration=3 accepts one BSTR. Keep the raw scalar in
            # addition to the pilot's existing 12-decimal manufacturing witness.
            raw_values = dimension.GetSystemValue3(3, self.before["configuration"])
            row["raw_system_values"] = raw_values
            if (
                not isinstance(raw_values, (tuple, list))
                or len(raw_values) != 1
                or type(raw_values[0]) not in (int, float)
                or not math.isfinite(raw_values[0])
            ):
                raise RuntimeError("source boundary raw value is not one finite scalar")
            if self.initial_value is not None and raw_values[0] != self.initial_value:
                raise RuntimeError("source boundary raw dimension value changed")
            self.initial_value = raw_values[0]
            native_tolerance = _early_bound(dimension.Tolerance, "IDimensionTolerance")
            row["tolerance"] = {
                **tolerance(dimension),
                "minimum": finite(native_tolerance.GetMinValue()),
                "maximum": finite(native_tolerance.GetMaxValue()),
            }
            if (
                self.initial_tolerance is not None
                and row["tolerance"] != self.initial_tolerance
            ):
                raise RuntimeError("source boundary tolerance limits changed")
            self.initial_tolerance = row["tolerance"]
            row["is_hole_callout"] = self.display.IsHoleCallout()
            if type(row["is_hole_callout"]) is not bool or row["is_hole_callout"]:
                raise RuntimeError("source GetText bank does not support hole callouts")
            row["display"] = {
                "type": self.display.Type2,
                "primary_precision": self.display.GetPrimaryPrecision2(),
                "tolerance_precision": self.display.GetPrimaryTolPrecision2(),
                "text": {str(part): self.display.GetText(part) for part in range(1, 9)},
            }
            if any(
                type(row["display"][key]) is not int
                for key in ("type", "primary_precision", "tolerance_precision")
            ):
                raise RuntimeError("source display returned a noninteger native field")
            if (
                self.initial_display_type is not None
                and row["display"]["type"] != self.initial_display_type
            ):
                raise RuntimeError("source display type changed")
            self.initial_display_type = row["display"]["type"]
            if any(type(value) is not str for value in row["display"]["text"].values()):
                raise RuntimeError("source display returned nonstring text")
            row["dirty_after_read"] = self.source.GetSaveFlag()
            if any(
                type(row[key]) is not bool
                for key in ("dirty_before_read", "dirty_after_read")
            ):
                raise RuntimeError("source dirty flag is not native bool")
            if row["dirty_before_read"] != row["dirty_after_read"]:
                raise RuntimeError("source boundary getters changed the dirty flag")
        except BaseException as error:
            row["error"] = repr(error)
            raise
        finally:
            row["read_seconds"] = time.perf_counter() - started
            primary = sys.exception()
            try:
                self.checkpoint()
            except BaseException as error:
                if primary is None:
                    raise
                primary.add_note(f"source evidence checkpoint also failed: {error!r}")
        return row

    @contextmanager
    def boundary(self, label):
        if len(self.stages) >= len(STAGES):
            raise RuntimeError("source boundary operation order/count changed")
        if (
            self.stages != list(STAGES[: len(self.stages)])
            or label != STAGES[len(self.stages)]
        ):
            raise RuntimeError("source boundary operation order/count changed")
        self.stages.append(label)
        self.capture(f"before_{label}")
        try:
            yield
        except BaseException as error:
            self.report.setdefault("operation_errors", []).append(
                {"boundary": label, "error": repr(error)}
            )
            raise
        finally:
            primary = sys.exception()
            try:
                self.capture(f"after_{label}")
            except BaseException as error:
                if primary is None:
                    raise
                primary.add_note(
                    f"after_{label} source observation also failed: {error!r}"
                )

    @contextmanager
    def observe(self):
        self.capture("initial")
        originals = {
            name: getattr(self.module, name)
            for name in ("set_dimension_callouts", "set_dimension_precision")
        }
        original_save = drawing.save_drawing

        def wrapped(label, original):
            @wraps(original)
            def call(adapter, *args, **kwargs):
                if adapter is not self.adapter:
                    raise RuntimeError("source boundary recipe changed adapter")
                with self.boundary(label):
                    return original(adapter, *args, **kwargs)

            return call

        def save(adapter, *args, artifact_context=None, **kwargs):
            if adapter is not self.adapter:
                raise RuntimeError("source boundary save changed adapter")

            @contextmanager
            def artifact(kind, path):
                expected = {
                    "drawing": self.module.OUTPUTS.slddrw,
                    "pdf": self.module.OUTPUTS.pdf,
                }
                if (
                    kind not in expected
                    or Path(path).resolve() != expected[kind].resolve()
                ):
                    raise RuntimeError("source boundary save has unexpected output")
                with (
                    artifact_context(kind, path) if artifact_context else nullcontext()
                ):
                    with self.boundary(
                        "native_save" if kind == "drawing" else "pdf_export"
                    ):
                        yield

            return original_save(adapter, *args, artifact_context=artifact, **kwargs)

        try:
            for label, (name, original) in zip(
                STAGES[:2], originals.items(), strict=True
            ):
                if getattr(drawing, name) is not original:
                    raise RuntimeError("source boundary recipe helper alias changed")
                setattr(self.module, name, wrapped(label, original))
            drawing.save_drawing = save
            yield
        finally:
            for name, original in originals.items():
                setattr(self.module, name, original)
            drawing.save_drawing = original_save

    def require_used(self):
        if self.stages != list(STAGES):
            raise RuntimeError(
                "source boundary control did not observe all four operations"
            )
