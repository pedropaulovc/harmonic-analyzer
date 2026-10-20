"""MS-only, intentionally failing diagnostic of the frozen 9b3 floor anchor.

Private historical-input experiment, NOT a drawing fix or merge candidate.
Use the normal supervised drawing leaf. This module never replaces run_build,
connect, preferences, discard, teardown, admission, cache or retry behavior.
One logical request can have multiple platform work attempts; each entered
recipe process gets a fresh UUID directory under the existing failure uploader.

Extra native reads, hashing, logging and original miss captures perturb timing
and may affect state. The old failed pid13320 is gone: this is neither preserved
process-state reproduction nor a same-native-input comparison with 604b (whose
assembly bytes differ). Unsupported state is recorded/refused, never adjusted.
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


class MSFrozenAnchorSelected(RuntimeError):
    """The ORIGINAL target returned a choice; stop BEFORE its balloon/save."""


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
        self.inside_hit = self.reading = self.pre_read = False
        self.pick = self.target_entries = 0
        self.validated = self.comparison_done = False
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
        balloons._view_scale2 = self._scale_before_original_pick
        balloons._hit_test_edge = self._hit_with_miss_observer
        balloons._select_balloon_anchor = self._select_target
        return self

    def __exit__(self, exc_type, exc, tb):
        balloons._view_scale2 = self.original_scale
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
                return await build(adapter)
            except Exception as exc:
                self._best_effort_write("original-build-exception", {
                    "type": type(exc).__name__, "message": str(exc), "traceback": traceback.format_exc(),
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

    def _scale_before_original_pick(self, draw):
        value = self.original_scale(draw)
        if self.target is not None and self.inside_hit and not self.pre_read and not self.reading:
            self.pre_read = self.reading = True
            try:
                adapter, view, leaf, anchor, xy = self.target
                display, seat = forensics._display_bags(adapter)
                mismatches = {key: {"expected": expected, "actual": display.get(key)}
                              for key, expected in RECORDED_WINDOW.items() if display.get(key) != expected}
                data = capture.collect_pre_pick(adapter, view, leaf, anchor.point_mm, xy, balloons)
                self._write(f"pre-pick-{self.pick}", {
                    "display": display, "seat": seat, "collector": data, "zoom_scale2": value,
                    "recorded_window_status": "unsupported" if mismatches else "matches-recorded",
                    "recorded_window_mismatches": mismatches, "window_setters_used": False,
                })
                _require(value is not None and abs(value - 86.36) < 1e-6 and not mismatches,
                         "unsupported changed/unreadable zoom or window; no adjustment or same-state claim")
            finally:
                self.reading = False
        return value

    def _hit_with_miss_observer(self, adapter, xy, *, redraw=False, observed=None, on_miss=None):
        if self.target is None:
            return self.original_hit(adapter, xy, redraw=redraw, observed=observed, on_miss=on_miss)
        self.pick += 1
        _require(self.pick <= 3, "original target coordinate-pick contract changed")
        self.pre_read, self.inside_hit = False, True

        def miss():
            if on_miss is not None:
                on_miss()  # ORIGINAL captures first, at ORIGINAL zoom.
            if self.pick == 3 and not self.comparison_done:
                self.comparison_done = True
                _, view, leaf, anchor, target_xy = self.target
                try:
                    zoom = self.original_scale(adapter.currentModel)
                    if zoom is None or abs(zoom - 86.36) > 1e-6:
                        result = {"status": "unsupported", "reason": "original capture changed/unbound zoom", "zoom_scale2": zoom}
                    else:
                        result = capture.compare_exact_edge(adapter, view, leaf, anchor.point_mm, target_xy, balloons)
                    self._write("exact-edge-after-third-original-miss", result)
                except Exception as exc:
                    self._best_effort_write("exact-edge-capture-error", {"type": type(exc).__name__, "message": str(exc)})
                # Original local selected=False and eventual RuntimeError survive.
        try:
            edge, owner = self.original_hit(adapter, xy, redraw=redraw, observed=observed, on_miss=miss)
            self._best_effort_write(f"original-coordinate-result-{self.pick}", {"selected": edge is not None, "owner": owner,
                                                                                "original_result_not_replaced": True})
            return edge, owner
        finally:
            self.inside_hit = False

    def _select_target(self, adapter, view, *, stem, anchor, candidates, offsets, sheet_xy, label):
        if stem != "ms-stop-block":
            return self.original_select(adapter, view, stem=stem, anchor=anchor, candidates=candidates,
                                        offsets=offsets, sheet_xy=sheet_xy, label=label)
        self.target_entries += 1
        _require(self.target_entries == 1 and self.validated, "first target must follow exact loaded-input validation")
        _require(tuple(anchor.point_mm or ()) == POINT_MM, "original frozen point changed")
        _require(len(candidates) == 1 and candidates[0].path.casefold() == "ms-stop-block-1", "wrong target component")
        _require(balloons.view_name(adapter, view) == "Drawing View4", "wrong target view")
        _require(sheet_xy is not None and len(sheet_xy) == 2 and all(abs(a-b) < 1e-9 for a, b in zip(sheet_xy, SHEET_XY, strict=True)),
                 "original projected point changed")
        _require(balloons._FROZEN_REDRAW_RETRIES == 2 and balloons._HIT_ZOOM_HALF == .0025, "original retry/zoom contract changed")
        self._verify_packet("packet-before-target-pick")
        self.phase = "original-first-stop-block-target"
        self.target = adapter, view, candidates[0], anchor, sheet_xy
        try:
            self.original_select(adapter, view, stem=stem, anchor=anchor, candidates=candidates,
                                 offsets=offsets, sheet_xy=sheet_xy, label=label)
        except Exception:
            self.phase = "original-target-exception"
            raise  # In particular retain EXACT original three-miss RuntimeError.
        else:
            self.phase = "original-target-selected-stop-before-balloon"
            raise MSFrozenAnchorSelected("MS_DIAGNOSTIC_TARGET_SELECTED: original target returned a choice; stop before target balloon/finalization; not drawing success")
        finally:
            self.target = None
