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


def symmetric_chamfer(
    source_edges: np.ndarray,
    render_edges: np.ndarray,
    *,
    source_width: float = 1920,
) -> float | None:
    """Mean of both directed edge distances, untruncated, in source pixels.

    For a full-video render use source_width=1920. For a cropped/inset view use
    its rectSourcePixels width, so the answer still uses original-video pixels.
    Either empty edge set returns None, including when both sets are empty.
    """
    source, render = _pair(source_edges, render_edges)
    scale = _scale(source.shape[1], source_width)
    if not source.any() or not render.any():
        return None
    forward, backward = _distances(source, render)
    return float((forward.mean() + backward.mean()) * (0.5 * scale))


def robust_camera_score(
    source_mask: np.ndarray,
    source_edges: np.ndarray,
    render_mask: np.ndarray,
    render_edges: np.ndarray | None = None,
    *,
    source_width: float = 1920,
    truncation_px: float = 96.0,
) -> float:
    """Finite camera minimization loss: clipped chamfer + silhouette penalty.

    This robust loss is not an acceptance metric. Missing support gets a loss
    larger than any supported score, avoiding empty-render optimizer minima.
    """
    source, render = _pair(source_mask, render_mask)
    edges, projected = _pair(source_edges, mask_edges(render) if render_edges is None else render_edges)
    if edges.shape != source.shape:
        raise ValueError("Masks and edges must have the same shape")
    scale = _scale(source.shape[1], source_width)
    if not math.isfinite(truncation_px) or truncation_px <= 0:
        raise ValueError("truncation_px must be positive and finite")
    iou = mask_iou(source, render)
    if iou is None or not edges.any() or not projected.any():
        return float(2 * truncation_px + source_width)
    forward, backward = _distances(edges, projected)
    clip_pixels = truncation_px / scale
    chamfer = (np.minimum(forward, clip_pixels).mean() + np.minimum(backward, clip_pixels).mean()) * (0.5 * scale)
    return float(chamfer + truncation_px * (1 - iou))
