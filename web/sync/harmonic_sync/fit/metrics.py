"""Silhouette metrics in original source-video pixels, not render pixels.

Validation chamfer is symmetric and deliberately untruncated. The separate
camera objective clips outliers; it must never be reported as validation error.
Empty silhouettes/edge sets have insufficient support, not a perfect match.
"""
from __future__ import annotations

import math

import numpy as np
from scipy.ndimage import binary_erosion, distance_transform_edt


def _binary(value: np.ndarray) -> np.ndarray:
    result = np.asarray(value)
    if result.ndim != 2 or not result.size:
        raise ValueError("Expected a nonempty two-dimensional mask")
    return result.astype(bool, copy=False)


def _pair(first: np.ndarray, second: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    left, right = _binary(first), _binary(second)
    if left.shape != right.shape:
        raise ValueError(f"Image shapes differ: {left.shape} != {right.shape}")
    return left, right


def _scale(width: int, source_width: float) -> float:
    if not math.isfinite(source_width) or source_width <= 0:
        raise ValueError("source_width must be positive and finite")
    return source_width / width


def mask_edges(mask: np.ndarray) -> np.ndarray:
    """One-pixel inner silhouette boundary, including image-border pixels."""
    binary = _binary(mask)
    return binary & ~binary_erosion(binary, structure=np.ones((3, 3), dtype=bool), border_value=0)


def mask_iou(source_mask: np.ndarray, render_mask: np.ndarray) -> float | None:
    """Binary intersection/union; either empty support is unvalidated (None)."""
    source, render = _pair(source_mask, render_mask)
    if not source.any() or not render.any():
        return None
    return float(np.count_nonzero(source & render) / np.count_nonzero(source | render))


def _distances(source: np.ndarray, render: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    return distance_transform_edt(~render)[source], distance_transform_edt(~source)[render]


def chamfer_metrics(
    source_edges: np.ndarray,
    render_edges: np.ndarray,
    *,
    source_width: float = 1920,
) -> dict[str, float | None]:
    """Both directed distances and their mean, untruncated source-video pixels."""
    source, render = _pair(source_edges, render_edges)
    scale = _scale(source.shape[1], source_width)
    keys = ("sourceToRenderChamferPx", "renderToSourceChamferPx", "chamferPx")
    if not source.any() or not render.any():
        return dict.fromkeys(keys)
    forward, backward = _distances(source, render)
    source_to_render = float(forward.mean()*scale)
    render_to_source = float(backward.mean()*scale)
    return dict(zip(keys, (source_to_render, render_to_source,
                           .5*(source_to_render+render_to_source))))


