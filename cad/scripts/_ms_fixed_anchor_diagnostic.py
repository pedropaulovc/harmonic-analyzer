"""MS-only, intentionally failing diagnostic of the frozen 9b3 floor anchor.

Private historical-input experiment, NOT a drawing fix or merge candidate.
Use the normal supervised drawing leaf. This module never replaces run_build,
connect, preferences, discard, teardown, admission, cache or retry behavior.
One logical request can have multiple platform work attempts; each entered
recipe process gets a fresh UUID directory under the existing failure uploader.

The first native pick precedes ALL extra target diagnostic observation. Only
AFTER its result do pixel captures/native reads/time permit later state changes.
Historic pid13320 is gone; this is not preserved-state or same-input604b proof.
This FIRST-PICK diagnostic intentionally does not run the original redraw retries.
"""
from __future__ import annotations

import contextlib
from datetime import UTC, datetime
import hashlib
import json
import os
from pathlib import Path
import sys
import traceback
import time
import uuid

import _drawing_balloons as balloons
import _ms_fixed_anchor_capture as capture
import _seat_forensics as forensics
import _telemetry
from _com import _early_bound


BASE_COMMIT = "9b3c8d2327aab7389f5bbf3d8439033d3ae17889"
SDK_COMMIT = "15875bda2bc6ad92247707032bd27c9953d0b927"
POINT_MM = (21.0, 4.3, 11.0)
SHEET_XY = (0.11378421190626398, 0.18420313206063238)
RECORDED_WINDOW = {
    "screen_width_px": 1280, "screen_height_px": 800,
    "frame_width_px": 1280, "frame_height_px": 752,
    "frame_state": "maximised", "frame_foreground": True,
    "monitors": 2, "view_visible_box_px": [253, 116, 1263, 714],
}
# Raw terminal9b3 packet, independently bound to its assembly execution token
# and failed drawing key a77854ea0dd2. No LF/CRLF/hash rewriting is permitted.
EXPECTED_INPUTS = {
    "sldasm/ms-measuring-stick.SLDASM": "644f1dab00d73ce223e1897b1b578abd6693be0a236504b81575163dba604430",
    "sldprt/ms-stick.SLDPRT": "88bfdbbbaa1ef4c713541745b1f8d2f818c8421b5a4bebead1100609add5aa84",
    "sldprt/ms-stop-block.SLDPRT": "c73b5e2eea870137524a74f5d606d1caf5a697ab281e7524da39b2366eb79e11",
    "sldprt/ms-stop-plate.SLDPRT": "954fdb31a61d09eadc86811c0ca2ade9221debca9588b01439198507ae967994",
    "sldprt/ms-vn-stop-plate-screw.SLDPRT": "67ab3aeb388295ff79dcd958e667e8fa4e6ed76f036384b310a61fb1b8835b93",
    "sldprt/ms-vn-thumb-screw.SLDPRT": "a87a0b97dd7a080c750dad709266e15869352baec110c0b0ef7480431bfbca3a",
}
TOKEN_PATH = "sldasm/.ms-measuring-stick.execution"
TOKEN_RAW_SHA256 = "915bc65c6b98cd67fa21335008182df5dcf58fbc608454b8251b3683e756e671"


class MSFirstPickObserved(RuntimeError):
    """Ordinary intentional stop; original first-result classification survives."""


async def refuse_finalize(*args, **kwargs):
    """Unconditional no-success guard, including an unexpectedly skipped target."""
    raise RuntimeError("MS_DIAGNOSTIC_FINALIZE_REFUSED: no successful drawing or cache publication")


def _digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def _require(condition, message):
    if not condition:
        raise RuntimeError("MS_DIAGNOSTIC_REFUSED: " + message)


class MSFixedAnchorDiagnostic:
    """Scope only MS selection observers; leave the original session untouched."""

    def __init__(self, source, validate_source):
        self.source = Path(source).resolve()
        self.out = self.source.parent.parent
        self.original_validate = validate_source
        self.original_select = balloons._select_balloon_anchor
        self.original_hit = balloons._hit_test_edge
        self.original_scale = balloons._view_scale2
        self.target = None
        self.original_observed = None
        self.pick = self.target_entries = self.coordinate_comparisons = 0
        self.validated = self.comparison_done = False
        self.frame_hwnd = None
        self.primary_classification = None
        self.primary = None
        self.transaction = None
        self.phase = "recipe-entered-before-original-connect"
        self.attempt_id = f"{datetime.now(UTC):%Y%m%dT%H%M%S%fZ}-{os.getpid()}-{uuid.uuid4().hex}"
        self.directory = forensics.OUT_FAILURES / "ms-fixed-anchor-9b3" / self.attempt_id

    def _write(self, name, data):
        path = self.directory / f"{name}.json"
        record = {"schema": "ms-fixed-anchor-supervised/1", "attempt_id": self.attempt_id,
                  "utc": datetime.now(UTC).isoformat(), "phase": self.phase, "data": data}
        text = json.dumps(record, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
        with path.open("x", encoding="utf-8", newline="\n") as stream:
            stream.write(text)
        relative = "failures/" + path.relative_to(forensics.OUT_FAILURES).as_posix()
        # Authoritative JSON remains under the existing recursive failure upload;
        # its content + path also use normal recipe telemetry (no new transport).
        with contextlib.suppress(Exception):
            _telemetry.info("MS frozen-anchor diagnostic snapshot", diagnostic_id=self.attempt_id,
                            artifact=relative, snapshot_json=text,
                            snapshot_sha256=hashlib.sha256(text.encode("utf-8")).hexdigest())
        return relative

    def _best_effort_write(self, name, data):
        try:
            self._write(name, data)
        except Exception as exc:
            with contextlib.suppress(Exception):
                _telemetry.warn(f"MS diagnostic receipt {name} failed: {exc}", diagnostic_id=self.attempt_id)

    def __enter__(self):
        self.directory.mkdir(parents=True, exist_ok=False)
        self._write("attempt-start", {
            "pid": os.getpid(), "parent_pid": os.getppid(), "python": sys.executable,
            "python_version": sys.version, "traceparent": os.environ.get("TRACEPARENT"),
            "com_seat": os.environ.get("HARMONIC_COM_SEAT"),
            "source": str(self.source), "base_commit": BASE_COMMIT, "SDK_gitlink": SDK_COMMIT,
            "logical_request_policy": "one drawing target; existing platform redispatch may create up to3 work attempts; count physical executions separately",
            "historic_pid13320_preserved": False, "same_native_inputs_as604b": False,
            "observer_effects": "native reads/hashing/logging/original captures perturb timing and may affect state",
            "native_validation_pending": True,
        })
        balloons._hit_test_edge = self._hit_with_miss_observer
        balloons._select_balloon_anchor = self._select_target
        return self

    def __exit__(self, exc_type, exc, tb):
        balloons._hit_test_edge = self.original_hit
        balloons._select_balloon_anchor = self.original_select
        # run_build has already performed its original teardown and telemetry
        # shutdown. This is process metadata, not a new native-state observation.
        self._best_effort_write("attempt-exit", {
            "exception_type": exc_type.__name__ if exc_type else None,
            "exception": str(exc) if exc is not None else None,
            "native_exit": exc.code if isinstance(exc, SystemExit) else None,
            "target_entries": self.target_entries, "coordinate_target_picks": self.pick,
            "entity_comparison_ran": self.comparison_done,
            "primary_first_pick_classification": self.primary_classification,
            "primary_diagnostic_message": str(self.primary) if self.primary else None,
            "transaction": self.transaction,
            "classification_independent_of_capture_or_teardown_errors": True,
            "drawing_success_or_manufacturing_approval": False,
        })
        return False

    def _verify_packet(self, name):
        rows, errors = [], []
        for relative, expected in EXPECTED_INPUTS.items():
            path = self.out / relative
            row = {"path": str(path), "relative_out_path": relative, "expected_raw_sha256": expected}
            try:
                row["actual_raw_sha256"] = _digest(path)
                if row["actual_raw_sha256"] != expected:
                    errors.append(f"raw packet hash differs: {relative}")
            except OSError as exc:
                row["error"] = f"{type(exc).__name__}: {exc}"
                errors.append(f"packet unavailable: {relative}")
            rows.append(row)
        token = self.out / TOKEN_PATH
        token_row = {"path": str(token), "retained_raw_sha256": TOKEN_RAW_SHA256,
                     "comparison_contract": "normal restamped semantic token value; raw bytes recorded independently, never normalized into a passing hash"}
        try:
            token_row["actual_raw_sha256"] = _digest(token)
            token_row["token_value"] = token.read_text(encoding="utf-8").strip()
            if token_row["token_value"] != EXPECTED_INPUTS["sldasm/ms-measuring-stick.SLDASM"]:
                errors.append("assembly execution token value differs")
        except (OSError, UnicodeError) as exc:
            token_row["error"] = f"{type(exc).__name__}: {exc}"
            errors.append("assembly execution token unavailable")
        self._write(name, {"files": rows, "execution_token": token_row, "errors": errors, "hash_normalization": "NONE"})
        _require(not errors, "; ".join(errors))

    def observe(self, build):
        async def observed(adapter):
            self.phase = "original-connected-build-entered"
            try:
                self._verify_packet("packet-before-open")
                sources = {}
                for name in ("__main__", __name__, "_ms_fixed_anchor_capture", "_drawing_balloons",
                             "_drawing_scan", "_drawing_projection", "_seat_forensics", "_session",
                             "solidworks_mcp.adapters.pywin32_adapter", "solidworks_mcp.adapters.sw_type_info"):
                    module = sys.modules.get(name)
                    path = getattr(module, "__file__", None)
                    if path:
                        sources[name] = {"path": path, "actual_raw_sha256": _digest(path)}
                self._write("imported-sources", sources)
                # Obtain the OS pixel-capture handle EARLY, before any target
                # view/zoom. No diagnostic COM getters run before the first
                # native pick once the original target path is entered.
                self.frame_hwnd = forensics._frame_hwnd(adapter)
                _require(bool(self.frame_hwnd), "no grounded main-frame HWND for pixel capture")
                self._write("pixel-capture-preparation", {
                    "frame_hwnd": self.frame_hwnd, "native_capture_path": "_seat_forensics._grab_screen(window=preobtained_hwnd)",
                    "timing": "before source open/target zoom", "no_SaveBMP_or_SaveAs3": True,
                })
                return await build(adapter)
            except Exception as exc:
                self._best_effort_write("original-build-exception", {
                    "type": type(exc).__name__, "message": str(exc), "traceback": traceback.format_exc(),
                    "primary_first_pick_classification": self.primary_classification,
                    "primary_diagnostic_message": str(self.primary) if self.primary else None,
                })
                raise  # Normal run_build catches Exception, tears down, flushes, exits1.
        return observed

    def validate_source(self, source):
        self.original_validate(source)
        assembly = _early_bound(source, "IAssemblyDoc")
        root_configuration = str(_early_bound(
            _early_bound(source.ConfigurationManager, "IConfigurationManager").ActiveConfiguration,
            "IConfiguration").Name)
        rows = [{"instance": "root-assembly", "path": str(source.GetPathName() or ""),
                 "referenced_configuration": root_configuration,
                 "loaded_configuration": root_configuration}]
        components = tuple(assembly.GetComponents(True) or ())
        for raw in components:
            component = _early_bound(raw, "IComponent2")
            loaded = _early_bound(component.GetModelDoc2(), "IModelDoc2")
            active = _early_bound(_early_bound(loaded.ConfigurationManager, "IConfigurationManager").ActiveConfiguration,
                                  "IConfiguration")
            rows.append({"instance": str(component.Name2), "path": str(component.GetPathName() or ""),
                         "loaded_model_path": str(loaded.GetPathName() or ""),
                         "referenced_configuration": str(component.ReferencedConfiguration),
                         "loaded_configuration": str(active.Name)})
        expected = {Path(relative).name.casefold(): (self.out / relative, digest)
                    for relative, digest in EXPECTED_INPUTS.items()}
        errors = []
        for row in rows:
            path = Path(row["path"]).resolve()
            wanted = expected.get(path.name.casefold())
            row["actual_raw_sha256"] = _digest(path) if row["path"] else None
            row["expected_raw_sha256"] = wanted[1] if wanted else None
            row["expected_path"] = str(wanted[0]) if wanted else None
            if wanted is None or path != wanted[0].resolve() or row["actual_raw_sha256"] != wanted[1]:
                errors.append(f"loaded native packet/path differs: {row['instance']}")
            if (not row["referenced_configuration"]
                    or row["referenced_configuration"] != row["loaded_configuration"]
                    or ("loaded_model_path" in row and Path(row["loaded_model_path"]).resolve() != path)):
                errors.append(f"loaded configuration/model path differs: {row['instance']}")
        self._write("actual-loaded-native-inputs", {"components": rows, "errors": errors,
                                                   "root_configuration": root_configuration})
        _require(len(components) == 6 and root_configuration == "Default", "not the original collapsed six-component Default source")
        _require(not errors, "; ".join(errors))
        self.validated = True

    def _pixel_capture(self, name):
        """Pixel-only existing HWND capture: no COM, native save, or UI input."""
        from PIL import Image
        started = time.perf_counter_ns()
        result = {"started_monotonic_ns": started, "frame_hwnd": self.frame_hwnd,
                  "source": "_seat_forensics._grab_screen(window=preobtained_hwnd)",
                  "pre_pick_buffer": False, "COM_SaveBMP_or_PDF_used": False}
        path = self.directory / f"{name}.png"
        try:
            forensics._grab_screen(path, window=self.frame_hwnd)
            with Image.open(path) as image:
                result["bitmap_size_px"] = list(image.size)
            result.update(status="captured", artifact="failures/" + path.relative_to(forensics.OUT_FAILURES).as_posix(),
                          raw_sha256=_digest(path))
        except Exception as exc:
            result.update(status="capture_error", error=f"{type(exc).__name__}: {exc}")
        result["ended_monotonic_ns"] = time.perf_counter_ns()
        return result

    def _after_first_pick(self, selected, started_ns, returned_ns):
        # Native boolean/time are saved IN MEMORY before any extra observer.
        self.primary_classification = "original_first_hit" if selected else "original_first_miss"
        self.primary = MSFirstPickObserved(
            f"MS_DIAGNOSTIC_FIRST_PICK: {self.primary_classification}; intentional stop before balloon/finalization; "
            "NOT a full three-miss reproduction or drawing success")
        self.phase = "after_first_original_pick"
        adapter, view, leaf, anchor, xy = self.target
        result = self.transaction = {
            "phase": self.phase, "original_selected": selected,
            "original_started_monotonic_ns": started_ns, "original_returned_monotonic_ns": returned_ns,
            "original_native_call_elapsed_ns": returned_ns - started_ns,
            "original_scale2_read": self.original_observed.get("zoom_scale2") if self.original_observed is not None else None,
            "original_redraw_retries_executed": 0, "diagnostic_coordinate_calls": 0,
            "original_result_never_replaced": True, "capture_errors": [],
        }
        try:
            # Required order at STILL ORIGINAL zoom: pixels -> native -> pixels.
            result["pixels_before_native_observer"] = self._pixel_capture("after-first-pick-before-native")
            native_started = time.perf_counter_ns()
            try:
                snapshot = capture.collect_after_first_pick(adapter, view, leaf, anchor.point_mm, xy, balloons)
                display, seat = forensics._display_bags(adapter)
                result.update(collector=snapshot, display=display, seat=seat)
            finally:
                result["native_observer_interval_ns"] = [native_started, time.perf_counter_ns()]
                result["pixels_after_native_observer"] = self._pixel_capture("after-first-pick-after-native")
            result["pixel_frame_binding"] = {
                "status": "unsupported", "raster_distance_reported": False,
                "reason": "Main-frame HWND bitmap and IModelView current-view pixels are different frames. "
                          "Native view HWND/client/window rectangles and DPI are retained in collector queries, "
                          "but bitmap-origin/cross-process DPI equivalence has not been validated. No guessed pixel mapping.",
            }
            mismatches = {key: {"expected": expected, "actual": display.get(key)}
                          for key, expected in RECORDED_WINDOW.items() if display.get(key) != expected}
            result["recorded_window_mismatches"] = mismatches
            zoom = snapshot.get("queries", {}).get("IModelView.Scale2", {}).get("value")
            _require(not mismatches and isinstance(zoom, (int, float)) and abs(zoom - 86.36) < 1e-6,
                     "unsupported changed/unreadable post-result window/zoom; no setter or adjustment")
            _require(result["pixels_before_native_observer"]["status"] == "captured"
                     and result["pixels_after_native_observer"]["status"] == "captured",
                     "pixel acquisition failed; first-result classification retained")
            _require(snapshot.get("status") == "observed", "unsupported original first-pick target/frame/configuration binding")
            if selected:
                result["coordinate_hit_identity"] = snapshot.get("coordinate_hit_identity")
                _require(result["coordinate_hit_identity"] is not None
                         and result["coordinate_hit_identity"].get("status") == "bound",
                         "original coordinate hit did not bind exact target owner/view")
                result["transaction_outcome"] = "observer_reduced_non_reproduction"
            else:
                # Only the original MISS permits ONE diagnostic same-point call.
                # It does not invoke _hit_test_edge, zoom, redraw, or callbacks.
                current_zoom = self.original_scale(adapter.currentModel)
                _require(current_zoom is not None and abs(current_zoom - zoom) < 1e-6,
                         "zoom changed after observations; no diagnostic coordinate call")
                comparison_started = time.perf_counter_ns()
                self.coordinate_comparisons = result["diagnostic_coordinate_calls"] = 1
                result["diagnostic_same_point_pick"] = {
                    "arguments": ["", "EDGE", xy[0], xy[1], 0.0, False, 0, "null_callout", 0],
                    "sheet_xy_m": xy, "zoom_scale2_before": current_zoom,
                    "started_monotonic_ns": comparison_started, "outcome": "unknown",
                    "explicit_redraw_or_zoom_or_setter": False,
                }
                diagnostic_selected = adapter.currentModel.Extension.SelectByID2(
                    "", "EDGE", xy[0], xy[1], 0.0, False, 0, balloons.null_callout(), 0)
                comparison_returned = time.perf_counter_ns()
                result["diagnostic_same_point_pick"].update(
                    selected=diagnostic_selected, returned_monotonic_ns=comparison_returned, outcome="returned")
                if diagnostic_selected:
                    result["diagnostic_coordinate_identity"] = capture.collect_coordinate_identity(
                        adapter, view, leaf, anchor.point_mm, xy, balloons)
                    _require(result["diagnostic_coordinate_identity"].get("coordinate_hit_identity", {}).get("status") == "bound",
                             "diagnostic coordinate hit owner/view identity unsupported")
                    result["transaction_outcome"] = "original_miss_then_observed_same_point_hit"
                else:
                    self.comparison_done = True
                    result["exact_edge_after_both_coordinate_misses"] = capture.compare_exact_edge(
                        adapter, view, leaf, anchor.point_mm, xy, balloons, diagnostic_selected)
                    result["transaction_outcome"] = "both_coordinate_calls_missed_entity_diagnostic_retained"
        except Exception as exc:
            # A capture/refusal/cleanup problem is secondary to the saved native
            # first-result classification, never a replacement or fallback.
            result["capture_errors"].append({"type": type(exc).__name__, "message": str(exc),
                                             "traceback": traceback.format_exc()})
            result["transaction_outcome"] = "unsupported_or_capture_error"
            self.primary.add_note(f"Post-first-pick observation also failed/refused: {exc!r}")
        finally:
            try:
                adapter.currentModel.ClearSelection2(True)
                count = _early_bound(adapter.currentModel.SelectionManager, "ISelectionMgr").GetSelectedObjectCount2(-1)
                result["selection_cleanup"] = {"remaining_count": count, "status": "ok" if count == 0 else "error"}
                if count != 0:
                    self.primary.add_note(f"Diagnostic selection cleanup left {count} selections")
            except Exception as exc:
                result["selection_cleanup"] = {"status": "error", "error": f"{type(exc).__name__}: {exc}"}
                self.primary.add_note(f"Diagnostic selection cleanup failed: {exc!r}")
            self._best_effort_write("first-pick-transaction", result)
        raise self.primary  # Ordinary Exception: original zoom finally + run_build teardown.

    def _hit_with_miss_observer(self, adapter, xy, *, redraw=False, observed=None, on_miss=None, after_pick=None):
        if self.target is None:
            return self.original_hit(adapter, xy, redraw=redraw, observed=observed, on_miss=on_miss, after_pick=after_pick)
        self.pick += 1
        _require(self.pick == 1 and not redraw and after_pick is None, "only the original first target pick is allowed")
        self.original_observed = observed
        return self.original_hit(adapter, xy, redraw=redraw, observed=observed,
                                 on_miss=on_miss, after_pick=self._after_first_pick)

    def _select_target(self, adapter, view, *, stem, anchor, candidates, offsets, sheet_xy, label):
        if stem != "ms-stop-block":
            return self.original_select(adapter, view, stem=stem, anchor=anchor, candidates=candidates,
                                        offsets=offsets, sheet_xy=sheet_xy, label=label)
        # Memory-only guards here. Packet/hash/loaded checks finished earlier;
        # no extra diagnostic COM, hashing, file, telemetry, screenshot or wait
        # occurs in this target entry or between original zoom and native pick.
        self.target_entries += 1
        _require(self.target_entries == 1 and self.validated, "first target must follow earlier exact input validation")
        _require(tuple(anchor.point_mm or ()) == POINT_MM, "original frozen point changed")
        _require(len(candidates) == 1 and candidates[0].path.casefold() == "ms-stop-block-1", "wrong target component")
        _require(sheet_xy is not None and len(sheet_xy) == 2 and all(abs(a-b) < 1e-9 for a, b in zip(sheet_xy, SHEET_XY, strict=True)),
                 "original projected point changed")
        _require(balloons._FROZEN_REDRAW_RETRIES == 2 and balloons._HIT_ZOOM_HALF == .0025, "original recipe constants changed")
        self.target = adapter, view, candidates[0], anchor, sheet_xy
        try:
            self.original_select(adapter, view, stem=stem, anchor=anchor, candidates=candidates,
                                 offsets=offsets, sheet_xy=sheet_xy, label=label)
            raise RuntimeError("MS_DIAGNOSTIC_REFUSED: first-pick observer unexpectedly returned")
        finally:
            self.target = None
