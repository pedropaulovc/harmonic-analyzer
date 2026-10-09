"""Direct source-frame registration using ORB features on static machine regions."""

import cv2
import numpy as np


class MotionEstimator:
    """Map cropped frames to a reference in the supplied (half-resolution) pixels.

    Only static source-image features participate. The previous successful map
    moves the reference support mask into the next frame; it never contributes
    correspondences or accumulates into the estimated homography.
    """

    def __init__(
        self,
        ref_index: int,
        reference_bgr: np.ndarray,
        reference_mask: np.ndarray,
        static_mask: np.ndarray,
    ):
        self.ref_index = ref_index
        self._height, self._width = reference_bgr.shape[:2]
        self._orb = cv2.ORB_create(nfeatures=2500)
        self._matcher = cv2.BFMatcher(cv2.NORM_HAMMING)
        self._kernel = np.ones((5, 5), dtype=np.uint8)
        # Full-image low-variance support may include stationary background:
        # descriptor patches can cross thin rails, but their centers cannot.
        self._static_support = np.where(static_mask != 0, 255, 0).astype(np.uint8)
        centers = cv2.bitwise_and(
            self._eroded_mask(reference_mask), self._static_support
        )
        self._reference_points, self._reference_descriptors = self._features(
            reference_bgr, centers, self._static_support
        )
        self._last_h = np.eye(3, dtype=np.float64)

    def _eroded_mask(self, mask: np.ndarray) -> np.ndarray:
        return cv2.erode(
            np.where(mask != 0, 255, 0).astype(np.uint8),
            self._kernel,
            borderType=cv2.BORDER_CONSTANT,
            borderValue=0,
        )

    def _features(
        self, bgr: np.ndarray, centers: np.ndarray, patch_support: np.ndarray
    ):
        gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
        keypoints, descriptors = self._orb.detectAndCompute(gray, centers)
        if descriptors is None:
            return np.empty((0, 2), dtype=np.float32), None
        # ORB's mask tests centers only. Keep the full descriptor footprint in
        # low-variance texture, without requiring it to fit inside a thin rail.
        distance = cv2.distanceTransform(
            patch_support, cv2.DIST_L2, cv2.DIST_MASK_PRECISE
        )
        keep = [
            i
            for i, point in enumerate(keypoints)
            if distance[int(round(point.pt[1])), int(round(point.pt[0]))]
            >= point.size * 0.5 * np.sqrt(2.0)
        ]
        if not keep:
            return np.empty((0, 2), dtype=np.float32), None
        points = np.asarray([keypoints[i].pt for i in keep], dtype=np.float32)
        return points, descriptors[keep]

    @staticmethod
    def _ratio_matches(matches) -> dict[int, int]:
        return {
            pair[0].queryIdx: pair[0].trainIdx
            for pair in matches
            if len(pair) == 2 and pair[0].distance < 0.75 * pair[1].distance
        }

    def _plausible(self, h: np.ndarray, width: int, height: int) -> bool:
        """Reject singular maps, projective horizons, flips and extreme scales."""
        if not np.isfinite(h).all() or abs(h[2, 2]) < 1e-9:
            return False
        h /= h[2, 2]
        if abs(np.linalg.det(h)) < 1e-8:
            return False
        corners = np.array(
            [[0, 0, 1], [width - 1, 0, 1],
             [width - 1, height - 1, 1], [0, height - 1, 1]],
            dtype=np.float64,
        )
        mapped = corners @ h.T
        denominators = mapped[:, 2]
        if np.any(np.abs(denominators) < 1e-6) or not (
            np.all(denominators > 0) or np.all(denominators < 0)
        ):
            return False
        projected = mapped[:, :2] / denominators[:, None]
        if not np.isfinite(projected).all():
            return False
        edges = np.roll(projected, -1, axis=0) - projected
        next_edges = np.roll(edges, -1, axis=0)
        crosses = edges[:, 0] * next_edges[:, 1] - edges[:, 1] * next_edges[:, 0]
        if np.any(crosses <= 0):
            return False
        area = 0.5 * np.sum(
            projected[:, 0] * np.roll(projected[:, 1], -1)
            - projected[:, 1] * np.roll(projected[:, 0], -1)
        )
        reference_area = self._width * self._height
        if not reference_area / 16 <= area <= reference_area * 16:
            return False
        reference_center = np.array([self._width / 2, self._height / 2])
        return bool(
            np.max(np.linalg.norm(projected - reference_center, axis=1))
            <= 3 * np.hypot(self._width, self._height)
        )

    def estimate(
        self, index: int, t: float, bgr: np.ndarray, mask: np.ndarray
    ) -> dict:
        result = {
            "index": int(index),
            "t": float(t),
            "H": np.eye(3, dtype=np.float64).ravel().tolist(),
            "inlierRatio": 0.0,
            "method": "unobservable",
            "matchCount": 0,
            "inlierCount": 0,
        }
        if index == self.ref_index:
            self._last_h = np.eye(3, dtype=np.float64)
            result.update(inlierRatio=1.0, method="reference")
            return result
        if self._reference_descriptors is None or len(self._reference_points) < 8:
            return result
        height, width = bgr.shape[:2]
        support = cv2.warpPerspective(
            self._static_support,
            np.linalg.inv(self._last_h),
            (width, height),
            flags=cv2.INTER_NEAREST,
            borderMode=cv2.BORDER_CONSTANT,
            borderValue=0,
        )
        centers = cv2.bitwise_and(support, self._eroded_mask(mask))
        points, descriptors = self._features(bgr, centers, support)
        if descriptors is None or len(points) < 8:
            return result
        forward = self._ratio_matches(
            self._matcher.knnMatch(descriptors, self._reference_descriptors, k=2)
        )
        reverse = self._ratio_matches(
            self._matcher.knnMatch(self._reference_descriptors, descriptors, k=2)
        )
        matches = [(current, ref) for current, ref in forward.items()
                   if reverse.get(ref) == current]
        result["matchCount"] = len(matches)
        if len(matches) < 8:
            return result
        current_points = np.asarray([points[i] for i, _ in matches])
        reference_points = np.asarray([self._reference_points[j] for _, j in matches])
        h, inliers = cv2.findHomography(
            current_points, reference_points, cv2.RANSAC, 3.0,
            maxIters=2000, confidence=0.995,
        )
        if h is None or inliers is None:
            return result
        inlier_count = int(np.count_nonzero(inliers))
        ratio = inlier_count / len(matches)
        if inlier_count < 6 or ratio < 0.5 or not self._plausible(h, width, height):
            return result
        try:
            inverse = np.linalg.inv(h)
        except np.linalg.LinAlgError:
            return result
        if not np.isfinite(inverse).all():
            return result
        self._last_h = h
        result.update(
            H=h.ravel().tolist(), inlierRatio=float(ratio), method="orb",
            inlierCount=inlier_count,
        )
        return result
