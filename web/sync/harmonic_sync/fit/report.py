"""Render-free reports and private, worst-first source/render overlay sheets.

All machine samples stay in acceptance denominators. Projection-conditioned
source support is not an independently observed part label, and crank inferred
from these same parts can never provide independent kinematics evidence.
"""
from __future__ import annotations

from collections import defaultdict
from collections.abc import Mapping, Sequence
import colorsys
import hashlib
import json
import math
import os
from pathlib import Path
import tempfile
from typing import Any

import numpy as np
from PIL import Image, ImageDraw

THRESHOLD_PX = 960.0
TARGET_FRACTION = 0.9
REQUIRED_IOU = 0.5
LIMITS = {
    "sourceGroups": "Per-group source support is projection-conditioned: source mask/edges are clipped near the rendered group. No independent source part labels exist; per-group IoU is not independently observed source-group IoU, even with tracked crank.",
    "crank": "Only independently tracked crank samples enter harmonic regressions. Inferred crank is fitted from the same moving parts being compared; held and inferred samples cannot validate kinematics.",
    "triage": "Kinematics-suspect requires harmonic correlation persistent in independent segments with different explicit fitted/manual setups. Local supported failures are setup-suspect, not proof of a setup defect. Insufficient phase/support or unresolved independent evidence is unvalidated.",
    "pixels": "Chamfer is symmetric and untruncated, in original source-video pixels: rectSourcePixels width / render width. Distributions retain all finite raw errors, including low-IoU samples. Acceptance requires mask IoU >= 0.5 and each supplied render-to-source/source-to-render chamfer <= 960 px; their mean cannot conceal a one-sided failure. Robust truncated camera loss is never an acceptance error.",
    "independentTakes": "Only the shot's driverViewId (largest machine view by median source mask area normalized to original source pixels) drives setup/crank. Other views may be independent takes: their numeric residuals remain pixel-alignment diagnostics, not independent mechanism/kinematics validation, even when they inherit a tracked crank.",
    "heldOut": "Setup parameters are fitted once at their first observable segment frame and then frozen. Fitting observations are excluded only from independent evidence for their fitted groups; dense raw pixel-alignment metrics still include every fitting frame/group.",
}


def _finite(value: Any) -> float | None:
    if value is None or isinstance(value, (bool, str, bytes)):
        return None
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) else None


def _safe(value: Any) -> Any:
    if isinstance(value, np.ndarray):
        return _safe(value.tolist())
    if isinstance(value, np.generic):
        return _safe(value.item())
    if isinstance(value, Mapping):
        return {str(key): _safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_safe(item) for item in value]
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    if isinstance(value, Path):
        return str(value)
    return value


def _atomic_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, prefix=f".{path.name}.", delete=False) as handle:
            temporary = Path(handle.name)
            handle.write(content)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def _atomic_json(path: Path, value: Any) -> None:
    _atomic_text(path, json.dumps(_safe(value), indent=2, allow_nan=False) + "\n")


def _distribution(values: Sequence[float], total: int, acceptance_values: Sequence[float] | None = None) -> dict[str, Any]:
    numbers = np.asarray(values, dtype=float)
    observed = len(numbers)
    qualified = np.asarray(values if acceptance_values is None else acceptance_values, dtype=float)
    validated = len(qualified)
    passing = int(np.count_nonzero(qualified <= THRESHOLD_PX))
    fraction = passing / total if total else None
    return {
        "sampledFrames": total, "validatedFrames": validated,
        "finiteMetricFrames": observed,
        "unvalidatedFrames": total - validated, "framesAtOrBelow960Px": passing,
        "medianPx": float(np.median(numbers)) if observed else None,
        "p90Px": float(np.percentile(numbers, 90)) if observed else None,
        "maxPx": float(numbers.max()) if observed else None,
        "fractionAtOrBelow960Px": fraction,
        "percentAtOrBelow960Px": 100 * fraction if fraction is not None else None,
        "thresholdPx": THRESHOLD_PX, "requiredFraction": TARGET_FRACTION,
        "requiredIoU": REQUIRED_IOU,
        "distributionPopulation": "all finite nonnegative raw chamfer samples, including low-IoU and unsupported observations; acceptance separately requires supported mask IoU >= 0.5 and each supplied directed chamfer <= 960 px; every sample remains in the denominator",
        "status": "unvalidated" if not total else "pass" if fraction >= TARGET_FRACTION else "fail",
    }


def _supported_error(frame: Mapping[str, Any]) -> float | None:
    error, iou = _finite(frame.get("chamferPx")), _finite(frame.get("iou"))
    if error is None or error < 0 or iou is None or not 0 <= iou <= 1:
        return None
    for key in ("sourceEdgePixels", "renderEdgePixels", "sourceMaskPixels", "renderMaskPixels", "visiblePixels"):
        if key in frame and (_finite(frame[key]) is None or float(frame[key]) <= 0):
            return None
    return error


def _acceptance_error(frame: Mapping[str, Any]) -> float | None:
    error = _supported_error(frame)
    if error is None or float(frame["iou"]) < REQUIRED_IOU:
        return None
    keys = ("renderToSourceChamferPx", "sourceToRenderChamferPx")
    directions = [_finite(frame.get(key)) for key in keys]
    if any(value is None or value < 0 for value in directions):
        return None
    return max(directions)


def _frame_distribution(frames: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    values = [value for frame in frames if (value := _finite(frame.get("chamferPx"))) is not None and value >= 0]
    qualified = [value for frame in frames if (value := _acceptance_error(frame)) is not None]
    return _distribution(values, len(frames), qualified)


def _key(frame: Mapping[str, Any]) -> tuple[str, str, Any]:
    return str(frame.get("shotId", "")), str(frame.get("viewId", "")), frame.get("index", frame.get("t"))


def _read_json(path: Path) -> dict[str, Any] | None:
    if not path.is_file():
        return None
    # A malformed artifact is an actionable error, not invisible missing data.
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"Expected a JSON object: {path}")
    return value


def _coverage_frames(video_id: str, root: Path, residuals: Mapping[str, Any]) -> tuple[list[dict[str, Any]], dict[str, Any], list[dict[str, Any]]]:
    census = _read_json(Path(__file__).resolve().parents[2] / "videos" / video_id / "shots.json") or {}
    # The census defines scope even if fitting aborted before serializing a shot.
    by_shot = {str(shot["id"]): dict(shot) for shot in census.get("shots", [])}
    for shot in residuals.get("shots", []):
        key = str(shot["id"])
        by_shot[key] = {**by_shot.get(key, {}), **shot}
    shots = list(by_shot.values())
    machine = {str(shot["id"]): shot for shot in shots if shot.get("classification") in ("machine", "transition")}
    frames: dict[tuple[str, str, Any], dict[str, Any]] = {}
    for row in residuals.get("frames", []):
        if str(row.get("shotId")) not in machine:
            continue
        key = _key(row)
        if key in frames:
            raise ValueError(f"Duplicate residual sample {key}")
        frames[key] = dict(row)
    expected_views, missing_views, unknown_counts = [], [], []
    for shot_id, shot in machine.items():
        for view in shot.get("views", []):
            view_id = str(view["viewId"])
            identity = {"shotId": shot_id, "viewId": view_id}
            expected_views.append(identity)
            source = _read_json(root / video_id / shot_id / view_id / "index.json")
            rows = source.get("frames", []) if source else []
            if not rows and census.get("fps") and "startFrame" in shot and "endFrame" in shot:
                numerator, denominator = census["fps"]
                fps = numerator / denominator
                first, stop = int(shot["startFrame"]), int(shot["endFrame"])
                first += (-first) % 2
                rows = [{"index": index, "t": index / fps} for index in range(first, stop, 2)]
            if not rows:
                unknown_counts.append(identity)
            for row in rows:
                key = (shot_id, view_id, row["index"])
                if key not in frames:
                    frames[key] = {**identity, "index": row["index"], "t": row.get("t"), "iou": None, "chamferPx": None, "crankSource": None, "reason": "missing sampled-frame residual", "groups": {}}
            actual = [row for key, row in frames.items() if key[:2] == (shot_id, view_id)]
            if not actual or any(_acceptance_error(row) is None for row in actual):
                missing_views.append({**identity, "sampledFrames": len(actual), "unvalidatedFrames": sum(_acceptance_error(row) is None for row in actual)})
    upstream = residuals.get("sourceCoverage", {})
    coverage = {"expectedViews": expected_views, "processedViews": len(expected_views) - len(missing_views), "missingViews": missing_views, "unknownSampleCountViews": unknown_counts, "reportedByFitter": upstream}
    return list(frames.values()), coverage, shots


def _setup_values(segment: Mapping[str, Any]) -> dict[str, str]:
    """Only observed/fitted setup differences establish independent setups."""
    provenance = segment.get("provenance", {})
    explicit = {str(key).replace("[", ".").replace("]", "") for key, source in provenance.items() if source in ("fitted", "manual")}
    values: dict[str, str] = {}
    def visit(value: Any, path: str) -> None:
        if isinstance(value, Mapping):
            for key, item in value.items():
                visit(item, f"{path}.{key}" if path else str(key))
        elif isinstance(value, (list, tuple)):
            for index, item in enumerate(value):
                visit(item, f"{path}.{index}")
        elif path != "crankTurns" and any(path == key or path.startswith(f"{key}.") for key in explicit):
            safe = _safe(value)
            if safe is not None:
                values[path] = json.dumps(safe, sort_keys=True, allow_nan=False)
    visit(segment.get("input", {}), "")
    return values


def _different_independent_setups(left: Mapping[str, Any], right: Mapping[str, Any]) -> bool:
    bounds = [_finite(segment.get(key)) for segment in (left, right) for key in ("start", "end")]
    if any(value is None for value in bounds):
        return False
    left_start, left_end, right_start, right_end = bounds
    if left_end <= left_start or right_end <= right_start or not (left_end <= right_start or right_end <= left_start):
        return False
    left_values, right_values = _setup_values(left), _setup_values(right)
    return any(left_values[key] != right_values[key] for key in left_values.keys() & right_values.keys())


def _driver_evidence(frame: Mapping[str, Any], drivers: Mapping[str, Any]) -> bool:
    if str(frame.get("validationScope", "")).startswith("independent-take"):
        return False
    driver = drivers.get(str(frame.get("shotId")))
    return driver is not None and str(frame.get("viewId")) == str(driver)


def _fit_observation(frame: Mapping[str, Any], detail: Mapping[str, Any]) -> bool:
    return (
        detail.get("heldOut") is False
        or str(detail.get("validationScope", "")).startswith("fit-frame")
        or str(frame.get("validationScope", "")).startswith("fit-frame")
    )


def _crank_support(observations: Sequence[Mapping[str, Any]], driver: Any) -> tuple[str, bool, bool]:
    frame = next((row for row in observations if driver is not None and str(row.get("viewId")) == str(driver)), None)
    source = frame.get("crankSource") if frame is not None else None
    if frame is None or str(frame.get("validationScope", "")).startswith("independent-take") or _finite(frame.get("turns")) is None or source not in ("tracked", "inferred", "held"):
        source = "unvalidated"
    support = frame.get("crankSupport", {}) if frame is not None else {}
    eligible = support.get("eligible")
    return source, eligible is True, not isinstance(eligible, bool)


def _harmonics(frames: Sequence[Mapping[str, Any]], residuals: Mapping[str, Any]) -> list[dict[str, Any]]:
    segments = {str(segment["id"]): segment for segment in residuals.get("segments", [])}
    drivers = {str(shot["id"]): shot.get("driverViewId") for shot in residuals.get("shots", [])}
    results = []
    for channel in residuals.get("channelMapping", []):
        frequency = _finite(channel.get("radiansPerCrankTurn"))
        harmonic = channel.get("harmonic")
        group = f"channel-{harmonic}"
        rows: dict[str, list[tuple[float, float]]] = defaultdict(list)
        seen: set[tuple[str, Any]] = set()
        for frame in frames:
            turns = _finite(frame.get("turns"))
            if not _driver_evidence(frame, drivers) or frame.get("crankSource") != "tracked" or turns is None:
                continue
            detail = frame.get("groups", {}).get(group, {})
            if _fit_observation(frame, detail):
                continue
            error = _supported_error(detail)
            segment_id = str(frame.get("segmentId", ""))
            # Multiple views of the same frame are not independent observations.
            sample_key = (segment_id, frame.get("index", frame.get("t")))
            if error is not None and sample_key not in seen:
                rows[segment_id].append((turns, error))
                seen.add(sample_key)
        evidence = []
        for segment_id, samples in sorted(rows.items()):
            result: dict[str, Any] = {"segmentId": segment_id, "trackedSamples": len(samples), "rSquared": None, "harmonicAmplitudePx": None, "phaseSpanRadians": None, "phaseBins": None, "status": "unvalidated"}
            if frequency is None or frequency <= 0 or len(samples) < 12:
                evidence.append(result)
                continue
            samples.sort()
            values = np.asarray(samples, dtype=float)
            theta, errors = values[:, 0] * frequency, values[:, 1]
            span = float(np.ptp(theta))
            bins = len(np.unique(np.floor(np.remainder(theta, 2 * np.pi) / (2 * np.pi) * 8)))
            result.update(phaseSpanRadians=span, phaseBins=bins, medianPx=float(np.median(errors)))
            # A rank-poor short arc cannot distinguish a harmonic from drift.
            if span < 2 * np.pi or bins < 6:
                evidence.append(result)
                continue
            drift = theta - theta.mean()
            baseline = np.column_stack((np.ones(len(theta)), drift))
            design = np.column_stack((baseline, np.sin(theta), np.cos(theta)))
            coefficients, _, rank, _ = np.linalg.lstsq(design, errors, rcond=None)
            base_fit = baseline @ np.linalg.lstsq(baseline, errors, rcond=None)[0]
            base_sse = float(np.sum((errors - base_fit) ** 2))
            if rank < 4 or base_sse <= 1e-12:
                evidence.append(result)
                continue
            sse = float(np.sum((errors - design @ coefficients) ** 2))
            correlation = max(0.0, 1 - sse / base_sse)
            amplitude = float(np.hypot(coefficients[-2], coefficients[-1]))
            correlated = correlation >= 0.5 and amplitude >= max(1.0, 0.1 * float(np.median(errors)))
            result.update(rSquared=correlation, harmonicAmplitudePx=amplitude, harmonicCorrelated=correlated, status="supported")
            evidence.append(result)
        local_failures = [row for row in evidence if row["status"] == "supported" and row.get("medianPx", 0) > THRESHOLD_PX]
        correlated_segments = [row for row in evidence if row.get("harmonicCorrelated")]
        independent = any(
            _different_independent_setups(segments.get(left["segmentId"], {}), segments.get(right["segmentId"], {}))
            for index, left in enumerate(correlated_segments)
            for right in correlated_segments[index + 1:]
        )
        if independent:
            status = "kinematics-suspect"
        elif len(local_failures) == 1 and all(row["status"] == "supported" for row in evidence):
            status = "setup-suspect"
        else:
            status = "unvalidated"
        results.append({"group": group, "harmonic": harmonic, "inputIndex": channel.get("inputIndex"), "radiansPerCrankTurn": frequency, "source": "projection-conditioned", "crankEvidence": "tracked-driver-view-only", "status": status, "segments": evidence})
    return results


def save_contact_sheet(output_path: str | Path, panels: Sequence[Mapping[str, Any]], group_ids: Mapping[str, int]) -> Path:
    """Save worst-first source | deterministic ID render | foreground blend.

    When IoU is supplied, unsupported IoU sorts first, then lowest IoU,
    with worst directed chamfer breaking ties. Legacy panels sort by raw
    chamfer. These are pixel diagnostics, not visual acceptance certification.
    Each source must already be cropped/presentation-aligned to its ID image.
    """
    if not panels:
        raise ValueError("A contact sheet needs at least one panel")
    output = Path(output_path).expanduser()
    has_iou = any("iou" in panel for panel in panels)
    def worst_first(panel: Mapping[str, Any]) -> tuple[float, ...]:
        error = _finite(panel.get("errorPx"))
        if not has_iou:
            return (0, 0) if error is None else (1, -error)
        iou = _finite(panel.get("iou"))
        if iou is not None and not 0 <= iou <= 1:
            iou = None
        keys = ("renderToSourceChamferPx", "sourceToRenderChamferPx")
        if any(key in panel for key in keys):
            directions = [_finite(panel.get(key)) for key in keys]
            worst = math.inf if any(value is None or value < 0 for value in directions) else max(directions)
        else:
            worst = math.inf if error is None else error
        return (0 if iou is None else 1, iou if iou is not None else 0, -worst)
    ordered = sorted(panels, key=worst_first)
    max_id = max(int(np.max(np.asarray(panel["ids"]))) for panel in ordered)
    palette = np.zeros((max_id + 1, 3), dtype=np.uint8)
    names = {int(index): name for name, index in group_ids.items()}
    for index in range(1, max_id + 1):
        name = names.get(index, f"unknown-id-{index}")
        hue = int.from_bytes(hashlib.sha256(name.encode()).digest()[:4], "big") / 2**32
        colour = (0.65, 0.65, 0.65) if name == "static" else colorsys.hsv_to_rgb(hue, 0.65, 0.95)
        palette[index] = np.rint(np.asarray(colour) * 255).astype(np.uint8)
    rows = []
    for panel in ordered:
        ids = np.asarray(panel["ids"])
        source = np.asarray(panel["source"])
        if ids.ndim != 2 or ids.dtype != np.uint16 or not ids.size:
            raise ValueError("Contact-sheet IDs must be nonempty HxW uint16")
        if source.shape != (*ids.shape, 3):
            raise ValueError("Source RGB and rendered ID image must share dimensions")
        if source.dtype != np.uint8:
            if not np.isfinite(source).all():
                raise ValueError("Source RGB must contain finite values")
            source = np.rint(np.clip(source * (255 if source.max() <= 1 else 1), 0, 255)).astype(np.uint8)
        render = palette[ids]
        blend = source.copy()
        visible = ids != 0
        blend[visible] = np.rint(source[visible] * 0.5 + render[visible] * 0.5).astype(np.uint8)
        images = [Image.fromarray(array) for array in (source, render, blend)]
        width = min(640, ids.shape[1])
        height = max(1, round(ids.shape[0] * width / ids.shape[1]))
        row = Image.new("RGB", (width * 3, height + 52), "#171717")
        draw = ImageDraw.Draw(row)
        error = _finite(panel.get("errorPx"))
        title = f"{panel.get('title', '')} | {'unvalidated' if error is None else f'{error:.2f} source px'}"
        if has_iou:
            def metric_label(value: Any) -> str:
                number = _finite(value)
                return "unvalidated" if number is None else f"{number:.3f}"
            title += (
                f" | IoU {metric_label(panel.get('iou'))}"
                f" | R2S {metric_label(panel.get('renderToSourceChamferPx'))} px"
                f" | S2R {metric_label(panel.get('sourceToRenderChamferPx'))} px"
            )
        # The default Pillow font is portable; unsupported glyphs are replaced.
        draw.text((8, 5), title.encode("latin-1", "replace").decode("latin-1"), fill="white")
        for column, (name, image) in enumerate(zip(("Source", "Render IDs", "Blend"), images, strict=True)):
            draw.text((column * width + 8, 29), name, fill="white")
            row.paste(image.resize((width, height), Image.Resampling.LANCZOS), (column * width, 52))
        rows.append(row)
    sheet = Image.new("RGB", (max(row.width for row in rows), sum(row.height for row in rows)), "#171717")
    y = 0
    for row in rows:
        sheet.paste(row, (0, y))
        y += row.height
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(dir=output.parent, prefix=f".{output.name}.", suffix=".png", delete=False) as handle:
            temporary = Path(handle.name)
        sheet.save(temporary, format="PNG")
        os.replace(temporary, output)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)
    return output


def write_report(video_id: str, data_root: str | Path, residuals: Mapping[str, Any] | None = None) -> dict[str, Any]:
    """Regenerate private residuals.json, summary.json and summary.md.

    No rendering, source segmentation or crank fitting is performed. Existing
    contact-sheet paths are retained and missing sheets are explicitly listed.
    """
    root = Path(data_root).expanduser()
    directory = root / video_id / "report"
    if residuals is None:
        residuals = _read_json(directory / "residuals.json")
        if residuals is None:
            raise FileNotFoundError(directory / "residuals.json")
    if residuals.get("videoId", video_id) != video_id:
        raise ValueError("Residual videoId does not match report videoId")
    review = _read_json(directory / "review.json") or {}
    review_notes: list[dict[str, Any]] = []
    note_positions: dict[tuple[str, str, str], int] = {}
    # Explicit private review entries override retained entries for the same
    # shot/view/reason; unrelated notes survive future CLI regeneration.
    for notes in (residuals.get("reviewNotes", []), review.get("reviewNotes", [])):
        if not isinstance(notes, list):
            raise ValueError("reviewNotes must be a list")
        for note in notes:
            if not isinstance(note, Mapping):
                raise ValueError("Each review note must be an object")
            identity = tuple(str(note.get(key, "")) for key in ("shotId", "viewId", "reason"))
            if identity in note_positions:
                review_notes[note_positions[identity]] = dict(note)
            else:
                note_positions[identity] = len(review_notes)
                review_notes.append(dict(note))
    frames, coverage, shots = _coverage_frames(video_id, root, residuals)
    drivers = {str(shot["id"]): shot.get("driverViewId") for shot in shots}
    independent_views = [
        {"shotId": shot["id"], "viewId": view["viewId"], "driverViewId": shot.get("driverViewId"), "validationScope": "independent-take, not validated"}
        for shot in shots if shot.get("classification") in ("machine", "transition") and shot.get("driverViewId") is not None
        for view in shot.get("views", []) if str(view["viewId"]) != str(shot["driverViewId"])
    ]
    fit_frame_views = 0
    fit_group_observations = 0
    held_out_group_observations = 0
    for frame in frames:
        fitting = str(frame.get("validationScope", "")).startswith("fit-frame")
        for detail in frame.get("groups", {}).values():
            if _fit_observation(frame, detail):
                fit_group_observations += 1
                fitting = True
            else:
                held_out_group_observations += 1
        fit_frame_views += int(fitting)
    held_out_evidence = {
        "fitFrameViews": fit_frame_views,
        "fitGroupObservations": fit_group_observations,
        "heldOutGroupObservations": held_out_group_observations,
        "scope": "all raw machine group observations; fitting groups excluded from independent mechanics evidence only; held-out counts do not imply supported, tracked-driver harmonic evidence",
    }
    manual_needed_reasons = []
    for identity in coverage["missingViews"]:
        unsupported = [
            frame for frame in frames
            if str(frame.get("shotId")) == str(identity["shotId"])
            and str(frame.get("viewId")) == str(identity["viewId"])
            and _acceptance_error(frame) is None
        ]
        reasons = set()
        for frame in unsupported:
            iou = _finite(frame.get("iou"))
            if iou is not None and iou < REQUIRED_IOU:
                reasons.add(f"mask IoU below required {REQUIRED_IOU}")
            if frame.get("reason"):
                reasons.add(str(frame["reason"]))
            elif iou is None or iou >= REQUIRED_IOU:
                reasons.add("unsupported pixel-alignment sample")
        manual_needed_reasons.append({
            **identity, "reasons": sorted(reasons), "source": "sampled-frame support",
        })
    manual_needed_reasons.extend({**note, "source": "explicit private alignment review"} for note in review_notes)
    for frame in frames:
        driver = drivers.get(str(frame.get("shotId")))
        if driver is not None and str(frame.get("viewId")) != str(driver):
            frame["validationScope"] = "independent-take, not validated"
    frame_view_acceptance = _frame_distribution(frames)
    unique: dict[tuple[str, Any], list[dict[str, Any]]] = defaultdict(list)
    for frame in frames:
        unique[(str(frame.get("shotId")), frame.get("index", frame.get("t")))].append(frame)
    # A machine frame is accepted only when every expected view is supported.
    frame_errors = []
    qualified_frame_errors = []
    for observations in unique.values():
        errors = [_finite(frame.get("chamferPx")) for frame in observations]
        if errors and all(error is not None and error >= 0 for error in errors):
            frame_errors.append(max(errors))
        qualified = [_acceptance_error(frame) for frame in observations]
        if qualified and all(error is not None for error in qualified):
            qualified_frame_errors.append(max(qualified))
    acceptance = _distribution(frame_errors, len(unique), qualified_frame_errors)
    if coverage["unknownSampleCountViews"]:
        acceptance["status"] = frame_view_acceptance["status"] = "unvalidated"
    acceptance["unit"] = "unique sampled machine frame; worst view; any invalid view makes frame unvalidated"
    frame_view_acceptance["unit"] = "sampled machine frame-view"
    acceptance["validationScope"] = frame_view_acceptance["validationScope"] = "pixel alignment only; not independent mechanism validation"
    shot_reports = []
    for shot in shots:
        if shot.get("classification") not in ("machine", "transition"):
            continue
        shot_frames = [frame for frame in frames if frame.get("shotId") == shot["id"]]
        quality = _frame_distribution(shot_frames)
        statuses = [view.get("quality", {}).get("status", "unfitted") for view in shot.get("views", [])]
        manual = any(frame.get("cameraSource") == "manual" for frame in shot_frames) or "manual" in statuses
        usable = bool(statuses) and all(status in ("manual", "fitted") for status in statuses)
        status = "manual" if manual and usable and quality["status"] == "pass" else "fitted" if usable and quality["status"] == "pass" else "manual-needed"
        operational_review = [note for note in review_notes if str(note.get("shotId", "")) == str(shot["id"])]
        shot_reports.append({
            "id": shot["id"], "driverViewId": shot.get("driverViewId"),
            "numericStatus": status, "status": "manual-needed" if operational_review else status,
            "operationalReviewReasons": operational_review, "quality": quality,
            "validationScope": "pixel alignment", "views": shot.get("views", []),
        })
    crank_counts = {source: 0 for source in ("tracked", "inferred", "held", "unvalidated")}
    eligible_samples = 0
    unknown_support_samples = 0
    for (shot_id, _), observations in unique.items():
        source, eligible, unknown = _crank_support(observations, drivers.get(shot_id))
        eligible_samples += int(eligible)
        unknown_support_samples += int(unknown)
        crank_counts[source] += 1
    crank = {
        "counts": crank_counts,
        "fractions": {key: count / len(unique) if unique else None for key, count in crank_counts.items()},
        "sampledMachineExposures": len(unique),
        "denominator": "unique sampled machine exposures, counting only the shot's driverViewId; missing/unknown driver or crank support is unvalidated; non-driver duplicates never count as independent tracks",
        "kinematicsEvidence": "tracked-driver-view-only",
        "independentTrackedDriverSamples": crank_counts["tracked"],
        "unknownSampleCountViews": coverage["unknownSampleCountViews"],
        "supportEligibility": {
            "eligibleSamples": eligible_samples,
            "eligibleFraction": eligible_samples / len(unique) if unique else None,
            "sampledMachineExposures": len(unique),
            "unvalidatedSamples": unknown_support_samples,
            "method": ">=150 pixels at 480 width (squared scale), >=50% source-mask overlap; native projection-conditioned",
            "denominator": "all unique sampled machine exposures, driver-only support; unknown support remains unvalidated and never eligible",
        },
    }
    segment_metrics = []
    frames_by_segment: dict[str, list[dict[str, Any]]] = defaultdict(list)
    shot_segments = {str(shot["id"]): shot.get("segmentId") for shot in shots}
    for frame in frames:
        segment_id = frame.get("segmentId") or shot_segments.get(str(frame.get("shotId")))
        frames_by_segment[str(segment_id) if segment_id is not None else "unassigned"].append(frame)
    segment_ids = {str(segment["id"]) for segment in residuals.get("segments", [])} | frames_by_segment.keys()
    group_names = {str(group) for frame in frames for group in frame.get("groups", {})}
    group_names.update(f"channel-{channel['harmonic']}" for channel in residuals.get("channelMapping", []) if "harmonic" in channel)
    for segment_id in sorted(segment_ids):
        segment_frames = frames_by_segment.get(segment_id, [])
        groups = []
        for group in sorted(group_names):
            supported = [
                detail for frame in segment_frames
                if _supported_error(detail := frame.get("groups", {}).get(group, {})) is not None
            ]
            ious = np.asarray([float(detail["iou"]) for detail in supported], dtype=float)
            groups.append({
                "group": group,
                "chamfer": _frame_distribution([frame.get("groups", {}).get(group, {}) for frame in segment_frames]),
                "iou": {
                    "sampledObservations": len(segment_frames), "supportedObservations": len(supported),
                    "unsupportedObservations": len(segment_frames) - len(supported),
                    "median": float(np.median(ious)) if len(ious) else None,
                    "p90": float(np.percentile(ious, 90)) if len(ious) else None,
                    "min": float(ious.min()) if len(ious) else None,
                    "max": float(ious.max()) if len(ious) else None,
                },
            })
        segment_exposures: dict[tuple[str, Any], list[dict[str, Any]]] = defaultdict(list)
        for frame in segment_frames:
            segment_exposures[(str(frame.get("shotId")), frame.get("index", frame.get("t")))].append(frame)
        counts = {source: 0 for source in crank_counts}
        for (shot_id, _), observations in segment_exposures.items():
            source, _, _ = _crank_support(observations, drivers.get(shot_id))
            counts[source] += 1
        segment_metrics.append({
            "segmentId": segment_id,
            "validationScope": "raw pixel alignment; group source support projection-conditioned; not independent mechanics evidence; fitting observations included",
            "frameViewAcceptance": _frame_distribution(segment_frames),
            "groups": groups,
            "crank": {
                "counts": counts, "sampledMachineExposures": len(segment_exposures),
                "denominator": "unique shot/index exposures; driver-only crank observations; unknown driver/support unvalidated",
            },
        })
    contacts = []
    missing_contacts = []
    for item in residuals.get("contactSheets", []):
        path_value = item.get("path") if isinstance(item, Mapping) else item
        if not path_value:
            missing_contacts.append(item)
            continue
        path = Path(path_value).expanduser()
        if not path.is_absolute():
            path = directory / path
        contacts.append(str(path))
        if not path.is_file():
            missing_contacts.append(str(path))
    contact_shots = {item.get("shotId") for item in residuals.get("contactSheets", []) if isinstance(item, Mapping)}
    missing_shot_sheets = [shot["id"] for shot in shot_reports if shot["id"] not in contact_shots and not any(str(shot["id"]) in Path(path).stem for path in contacts)]
    seconds = _finite(residuals.get("runtimeSeconds"))
    snapshot = residuals.get("renderSnapshot") or {}
    partial = bool(residuals.get("partial", False))
    iteration = partial or snapshot.get("mode") == "development-iteration"
    report_scope = "partial-development-iteration" if iteration else "full-video-production" if residuals.get("partial") is False else "unspecified"
    acceptance["reportScope"] = frame_view_acceptance["reportScope"] = report_scope
    if iteration:
        acceptance["status"] = frame_view_acceptance["status"] = "unvalidated"
    timing = dict(residuals.get("timing") or {})
    clock_error = _finite(timing.get("maxSourceClockErrorSeconds"))
    if clock_error is not None and clock_error < 0:
        clock_error = None
    timing_acceptance = {
        "targetSeconds": 0.5,
        "maxSourceClockErrorSeconds": clock_error,
        "status": "unvalidated" if clock_error is None or iteration else "pass" if clock_error <= 0.5 else "fail",
        "reportScope": report_scope,
        "criterion": "source/model timestamp clock skew only; computation runtime and sampling/key gaps are not temporal alignment error",
    }
    summary = {
        "videoId": video_id, "sourceSha256": residuals.get("sourceSha256"), "modelSha256": residuals.get("modelSha256"),
        "renderSnapshot": snapshot, "renderer": residuals.get("renderer"),
        "partial": partial, "reportScope": report_scope,
        "reviewNotes": review_notes,
        "candidateInfeasibility": residuals.get("candidateInfeasibility", []),
        "candidateInfeasibilityClassification": "optimizer-domain-rejection",
        "acceptance": acceptance, "frameViewAcceptance": frame_view_acceptance,
        "shots": shot_reports, "fittedShots": [shot["id"] for shot in shot_reports if shot["status"] == "fitted"],
        "manualShots": [shot["id"] for shot in shot_reports if shot["status"] == "manual"],
        "manualNeededShots": [shot["id"] for shot in shot_reports if shot["status"] == "manual-needed"],
        "crank": crank, "segments": residuals.get("segments", []), "channelMapping": residuals.get("channelMapping", []),
        "segmentMetrics": segment_metrics,
        "harmonicRegressions": _harmonics(frames, residuals), "sourceCoverage": coverage, "limitations": LIMITS,
        "heldOutEvidence": held_out_evidence,
        "manualNeededReasons": manual_needed_reasons,
        "independentTakeViews": independent_views,
        "shotsWithoutDriverView": [shot["id"] for shot in shots if shot.get("classification") in ("machine", "transition") and shot.get("driverViewId") is None],
        "independentTakeFrameViews": sum(str(frame.get("validationScope", "")).startswith("independent-take") for frame in frames),
        "fitRuntimeSeconds": seconds, "timing": timing, "timingAcceptance": timing_acceptance,
        "shotTiming": residuals.get("shotTiming", []),
        "frozenValidationSeconds": _finite(residuals.get("frozenValidationSeconds")),
        "syncBytes": residuals.get("syncBytes"), "contactSheets": contacts, "missingContactSheets": missing_contacts,
        "shotsWithoutContactSheets": missing_shot_sheets,
        "outputs": {"residuals": str(directory / "residuals.json"), "summaryJson": str(directory / "summary.json"), "summaryMarkdown": str(directory / "summary.md")},
    }
    document = dict(residuals)
    document["videoId"] = video_id
    document["frames"] = frames
    document["reviewNotes"] = review_notes
    _atomic_json(directory / "residuals.json", document)
    _atomic_json(directory / "summary.json", summary)
    def number(value: Any) -> str:
        return "null (insufficient support)" if value is None else f"{value:.3f}"
    lines = [
        f"# Numerical sync report: {video_id}", "",
        f"Source SHA-256: `{summary['sourceSha256']}`",
        f"Model SHA-256: `{summary['modelSha256']}`", "",
        "## Acceptance (all sampled machine frames)", "",
        f"Status: **{acceptance['status']}**; sampled {acceptance['sampledFrames']}; validated {acceptance['validatedFrames']}; unvalidated {acceptance['unvalidatedFrames']}.",
        f"All-finite raw untruncated source-pixel chamfer median / p90 / max (including low-IoU observations): {number(acceptance['medianPx'])} / {number(acceptance['p90Px'])} / {number(acceptance['maxPx'])}.",
        f"Each supplied render→source AND source→render chamfer at most 960 px AND mask IoU at least {REQUIRED_IOU}: {number(acceptance['percentAtOrBelow960Px'])}% of all sampled frames (target 90%); the symmetric mean alone cannot pass a one-sided failure.",
        f"Frame-view support: {frame_view_acceptance['validatedFrames']} / {frame_view_acceptance['sampledFrames']}; low-IoU or missing support is never a success.",
        f"Fit computation runtime: {number(summary['fitRuntimeSeconds'])} s (not a temporal alignment acceptance metric).", "",
        "## Temporal alignment", "",
        f"Maximum source/model clock error: {number(clock_error)} s; bound 0.5 s; **{timing_acceptance['status']}**.",
        f"Maximum crank sample gap: {number(_finite(timing.get('maxCrankSampleGapSeconds')))} s; maximum camera key gap: {number(_finite(timing.get('maxCameraKeyGapSeconds')))} s.",
        "Sample/key gaps are diagnostics, not clock skew. Unmeasured clock error is unvalidated; computation runtime is never compared with the 0.5 s alignment bound.", "",
        "## Shot status", "",
    ]
    lines.extend(f"- {shot['id']}: {shot['status']} (numeric status: {shot['numericStatus']}); median {number(shot['quality']['medianPx'])} px, p90 {number(shot['quality']['p90Px'])} px, max {number(shot['quality']['maxPx'])} px; unvalidated {shot['quality']['unvalidatedFrames']}." for shot in shot_reports)
    lines.extend([
        "", "## Frozen whole-segment validation and runtime", "",
        f"Final frozen-setup re-pose/render validation runtime: {number(summary['frozenValidationSeconds'])} s; missing timing is not evidence that the final pass ran.",
        "Per-shot computation timings (not temporal alignment error):", "",
        "```json", json.dumps(_safe(summary["shotTiming"]), indent=2, allow_nan=False), "```", "",
    ])
    lines.extend(["", "## Independent-take scope", "", "All numeric acceptance/distribution fields above measure pixel alignment, not independent mechanism validation. Non-driver views never enter harmonic/kinematic evidence; a shot without driverViewId has no independent tracked-driver evidence.", "", "```json", json.dumps(_safe({"views": independent_views, "shotsWithoutDriverView": summary["shotsWithoutDriverView"]}), indent=2, allow_nan=False), "```"])
    lines.extend([
        "", "## Held-out independent mechanics evidence", "",
        f"Fitting frame-views: {fit_frame_views}; fitting group observations: {fit_group_observations}; held-out group observations: {held_out_group_observations}.",
        "Each setup parameter is fitted once at its first observable frame in the segment (later shots may supply previously hidden parameters); fitted/manual values are frozen for the final whole-segment re-pose/validation. Fitting groups never validate their own parameters in harmonic evidence. Other groups at the same frame remain eligible. Raw pixel-alignment distributions and their denominators above retain all fitting observations. Held-out counts alone do not establish independent mechanics evidence: support, independent tracked driver crank, phase coverage and existing harmonic criteria still apply.", "",
    ])
    lines.extend([
        "", "## Native render provenance", "",
        f"Report scope: **{report_scope}**; partial: **{partial}**. Development/partial iterations are not full-video production acceptance.",
        f"Commit: `{snapshot.get('gitCommit', 'unrecorded')}`; dirty: `{snapshot.get('gitDirty', 'unrecorded')}`.",
        f"Immutable snapshot directory: `{snapshot.get('directory', 'unrecorded')}`.",
        f"Bundle manifest SHA-256: `{snapshot.get('bundleManifestSha256', 'unrecorded')}`.",
        f"Actual native renderer: `{json.dumps(_safe(summary['renderer']), ensure_ascii=True, allow_nan=False)}`.",
    ])
    lines.extend(["", f"Crank-count denominator: {crank['sampledMachineExposures']} unique sampled machine exposures; only driver views contribute tracked/inferred/held counts. Missing driver support is unvalidated. Non-driver copies are not independently tracked."])
    support = crank["supportEligibility"]
    lines.extend([
        "", f"Driver crank-support eligibility: {support['eligibleSamples']} / {support['sampledMachineExposures']} exposures; fraction {number(support['eligibleFraction'])}; unknown/unvalidated support {support['unvalidatedSamples']}.",
        f"Support method: {support['method']}. Eligibility is projection-conditioned, not proof of independent tracking.",
        "", "## Per-segment raw pixel metrics", "",
        "All frame-views, including fitting observations and unsupported samples, remain in denominators. Group IoU/chamfer support is projection-conditioned; these aggregates do not establish held-out mechanics evidence. Unassigned samples are retained explicitly.", "",
        "| Segment | Supported / sampled frame-views | Median / p90 / max px | Tracked / inferred / held / unvalidated crank |",
        "| --- | --- | --- | --- |",
    ])
    for metric in segment_metrics:
        quality = metric["frameViewAcceptance"]
        counts = metric["crank"]["counts"]
        label = str(metric["segmentId"]).replace("|", "\\|").replace("\n", " ")
        lines.append(
            f"| {label} | {quality['validatedFrames']} / {quality['sampledFrames']} | "
            f"{number(quality['medianPx'])} / {number(quality['p90Px'])} / {number(quality['maxPx'])} | "
            + " / ".join(str(counts[source]) for source in ("tracked", "inferred", "held", "unvalidated")) + " |"
        )
    lines.extend(["", "Full per-group distributions and support counts:", "", "```json", json.dumps(_safe(segment_metrics), indent=2, allow_nan=False), "```"])
    lines.extend(["", "## Crank evidence", "", *(f"- {source}: {count}; fraction {number(crank['fractions'][source])}." for source, count in crank_counts.items()), "", "## Segment setups and flattened provenance", "", "```json", json.dumps(_safe(summary["segments"]), indent=2, allow_nan=False), "```", "", "## Harmonic residual triage (tracked only)", "", "Thresholds: at least 12 samples, one channel cycle, six of eight phase bins; sine/cosine improvement R² ≥ 0.5 over offset + linear drift; amplitude ≥ max(1 px, 10% median residual). Different segments require distinct fitted/manual setup inputs. Suspicion is not proof.", "", "```json", json.dumps(_safe(summary["harmonicRegressions"]), indent=2, allow_nan=False), "```", "", "## Source coverage", "", "```json", json.dumps(_safe(coverage), indent=2, allow_nan=False), "```", "", "## Evidence limitations", ""])
    lines.extend(f"- {value}" for value in LIMITS.values())
    lines.extend(["", "## Native candidate feasibility", "", "Classification: optimizer-domain-rejection. These counts record physical-domain exclusions during numerical candidate search, not automatically a model defect or an accepted final-state failure. Initial/manual/final-state validation remains strict.", ""])
    if summary["candidateInfeasibility"]:
        for entry in summary["candidateInfeasibility"]:
            lines.append(f"- Shot {entry.get('shotId', 'unrecorded')}:")
            for reason, count in entry.get("reasons", {}).items():
                lines.append(f"  - {reason}: {_safe(count)} rejected candidates.")
    else:
        lines.append("No optimizer-domain rejection counts recorded.")
    lines.append("Any supplied setup-suspect review of a chosen prior failing across a phase range is retained in Alignment-tool review below. A chosen setup prior is not a source measurement; rejection counts alone do not establish kinematics-suspect.")
    lines.extend(["", "## Alignment-tool review", "", "Human-inspected alignment outliers and actions are independent of the coarse 960 px numerical acceptance threshold; these notes do not alter pixel acceptance.", ""])
    if summary["reviewNotes"]:
        lines.extend(["```json", json.dumps(_safe(summary["reviewNotes"]), indent=2, allow_nan=False), "```"])
    else:
        lines.append("No human-inspection notes recorded; this is not evidence that all alignments were visually accepted.")
    lines.extend([
        "", "## Manual-needed shot/view reasons", "",
        "Unsupported samples and explicitly recorded private alignment-review reasons require attention even when broad 960 px pixel acceptance passes. Review reasons are retained/overridden only by explicit private review.json entries; no visual camera-outlier assessment is fabricated. These reasons do not change numerical pass criteria.", "",
        "| Shot | View | Reason | Evidence source |",
        "| --- | --- | --- | --- |",
    ])
    def table_cell(value: Any) -> str:
        return str(value).replace("|", "\\|").replace("\n", " ")
    for entry in manual_needed_reasons:
        reason = "; ".join(entry["reasons"]) if "reasons" in entry else entry.get("reason", "unspecified private review reason")
        lines.append("| " + " | ".join(table_cell(value) for value in (
            entry.get("shotId", ""), entry.get("viewId", ""), reason, entry["source"],
        )) + " |")
    if not manual_needed_reasons:
        lines.append("| — | — | No unsupported samples or explicit private review reasons recorded | Not a visual acceptance claim |")
    lines.extend(["", "## Worst-first contact sheets", ""])
    lines.extend(f"- [{Path(path).name}]({os.path.relpath(path, directory)})" for path in contacts)
    if missing_contacts or missing_shot_sheets:
        lines.append(f"Missing sheet evidence: {missing_contacts}; shots without sheets: {missing_shot_sheets}.")
    _atomic_text(directory / "summary.md", "\n".join(lines) + "\n")
    return _safe(summary)
