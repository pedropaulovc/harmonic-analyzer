"""Read-only slotted-sheet closure; no source enrollment or geometry setters.

The source/native role manifest is supplied by the owned pilot after separately
reviewed producer evidence. These sheet roles come from the unchanged recipe;
they do not invent source hashes, display kinds or attached entity identities.
"""

from enum import StrEnum
import math

from _drawing_view_packing import Rect
from diagnostics._model_dimension_coverage import SemanticCoverage
import slotted_screw_spec as spec


class LayoutObservation(StrEnum):
    BASELINE = "baseline"
    CANDIDATE = "candidate"


VIEWS = ("*Front", "*Top", "*Isometric")
DIMENSION_VIEWS = {
    "HeadDia@HeadProfile": "*Top",
    "HeadHt@Head": "*Front",
    "ShankLg@Shank": "*Front",
}


def require_selection(mode, targets, manifests):
    if mode is None:
        return
    if not isinstance(mode, LayoutObservation) or tuple(targets) != ("slotted_screw",):
        raise ValueError("slotted layout observation requires its one explicit target")
    if "slotted_screw" not in manifests:
        raise ValueError("slotted source enrollment requires reviewed native evidence")
    manifest = manifests["slotted_screw"]
    if (
        manifest.coverage is not SemanticCoverage.MODEL_DIMENSIONS_ONLY
        or manifest.dimensions != spec.DRAWING_DIMENSIONS
        or manifest.basic or manifest.entity_labels or manifest.view_roles
        or {row.key: row.orientation for row in manifest.model_dimensions} != DIMENSION_VIEWS
        or len(manifest.model_dimensions) != len(DIMENSION_VIEWS)
        or sorted(manifest.model_views) != sorted(VIEWS)
    ):
        raise ValueError("slotted source enrollment has an incomplete dimension contract")


def _values(raw, count, label):
    if (
        type(raw) not in (list, tuple) or len(raw) != count
        or any(type(v) not in (int, float) or not math.isfinite(v) for v in raw)
    ):
        raise RuntimeError(f"{label}: expected {count} finite native coordinates")
    return tuple(raw)


def _rect(raw):
    if type(raw) is not dict or set(raw) != {"xmin", "ymin", "xmax", "ymax"}:
        raise RuntimeError("annotation measurement rectangle is incomplete")
    return Rect(*_values([raw[k] for k in ("xmin", "ymin", "xmax", "ymax")], 4, "measurement"))


def _clearance(box, drawable):
    return {
        "left": box.xmin - drawable.xmin,
        "bottom": box.ymin - drawable.ymin,
        "right": drawable.xmax - box.xmax,
        "top": drawable.ymax - box.ymax,
    }


def layout_geometry(bank, views, drawable):
    """Use the existing complete native ink bank, including dimension tails.

    Coordinates are unrounded sheet metres. This observes border containment;
    it is not a replacement for production packing's view/obstacle gap gate.
    """
    drawable = Rect(*_values(drawable, 4, "drawable"))
    dimensions = bank["model_dimensions"]["dimensions"]
    if dimensions.keys() != DIMENSION_VIEWS.keys():
        raise RuntimeError("slotted dimension contract requires exactly three roles")
    if sorted(row["orientation"] for row in views.values()) != sorted(VIEWS):
        raise RuntimeError("slotted view contract requires exactly three orientations")
    boxes = {}
    for name, view in views.items():
        if _values(view["scale"], 2, "scale") != (6.0, 1.0):
            raise RuntimeError("slotted view scale must remain exactly 6:1")
        boxes[f"view:{name}"] = Rect(*_values(view["outline"], 4, "view outline"))
    annotations = bank["annotations"]
    for key, row in annotations.items():
        semantic = row["semantic"]
        if semantic["owner_type"] == 2:
            continue  # Sheet-format ink belongs to the existing template bank.
        if (
            semantic["kind"] not in (4, 6) or semantic["visible"] != 1
            or semantic["dangling"] is not False
            or row.get("measurement_exclusion") or "measurement" not in row
        ):
            raise RuntimeError(f"{key}: unsupported or hidden slotted measurement")
        boxes[key] = _rect(row["measurement"]["envelope"])
    for key, orientation in DIMENSION_VIEWS.items():
        row = dimensions[key]
        annotation_key = row["annotation_key"]
        if (
            row["orientation"] != orientation or annotation_key not in boxes
            or row["presentation"]["show_dimension_value"] is not True
            or annotations[annotation_key]["semantic"]["kind"] != 4
        ):
            raise RuntimeError(f"{key}: dimension visibility/view contract changed")
        strokes = annotations[annotation_key]["measurement"]["native_strokes"]
        if not strokes:
            raise RuntimeError(f"{key}: displayed dimension stroke bank is empty")
        envelope = boxes[annotation_key]
        for stroke in strokes:
            points = [_values(stroke[k], 2, "stroke") for k in ("start", "end")]
            width, = _values([stroke["width_m"]], 1, "stroke width")
            if width < 0 or any(
                not (envelope.xmin <= x - width / 2 <= x + width / 2 <= envelope.xmax
                     and envelope.ymin <= y - width / 2 <= y + width / 2 <= envelope.ymax)
                for x, y in points
            ):
                raise RuntimeError(f"{key}: dimension envelope omits native stroke ink")
    clearances = {key: _clearance(box, drawable) for key, box in boxes.items()}
    return {
        "drawable_m": list(drawable.bounds),
        "envelopes_m": {key: list(box.bounds) for key, box in boxes.items()},
        "clearances_m": clearances,
        "head_height_top_clearance_m": clearances[dimensions["HeadHt@Head"]["annotation_key"]]["top"],
        "border_status": "inside" if all(value >= 0 for row in clearances.values() for value in row.values()) else "outside",
    }


def require_border(mode, result):
    if not isinstance(mode, LayoutObservation):
        raise ValueError("explicit slotted observation arm required")
    if mode is LayoutObservation.CANDIDATE and result["border_status"] != "inside":
        raise RuntimeError("slotted candidate decorated ink crosses the native zone border")
