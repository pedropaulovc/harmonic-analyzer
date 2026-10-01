import type { ImagePlaneWarp } from './scene'

export type ImagePlanePoint = readonly [number, number]
export type ImagePlaneCorners = readonly [ImagePlanePoint, ImagePlanePoint, ImagePlanePoint, ImagePlanePoint]

function finite(value: unknown, label: string): number {
  if (typeof value !== 'number' || !Number.isFinite(value)) throw new Error(`${label}: finite numeric coordinates are required.`)
  return value
}

/** Image-boundary TL/TR/BR/BL identities, not geometric screen-corner sorting. */
export function deriveImagePlaneWarp(viewport: readonly [number, number], corners: ImagePlaneCorners, label = 'Image-plane homography'): ImagePlaneWarp {
  if (!Array.isArray(viewport) || viewport.length !== 2 || !Array.isArray(corners) || corners.length !== 4) throw new Error(`${label}: exactly one viewport and four ordered corners are required.`)
  const width = finite(viewport[0], label), height = finite(viewport[1], label)
  if (width <= 0 || height <= 0) throw new Error(`${label}: viewport dimensions must be positive.`)
  for (const point of corners) {
    if (!Array.isArray(point) || point.length !== 2) throw new Error(`${label}: corners must be numeric pixel pairs.`)
    finite(point[0], label); finite(point[1], label)
  }
  // Normalize the measured target for stable arithmetic; the input domain is the unit square.
  const originX = corners.reduce((sum, point) => sum + point[0] / 4, 0)
  const originY = corners.reduce((sum, point) => sum + point[1] / 4, 0)
  const scale = Math.max(...corners.map((point) => Math.hypot(point[0] - originX, point[1] - originY)))
  if (!Number.isFinite(scale) || scale <= 0) throw new Error(`${label}: degenerate measured corners.`)
  const points = corners.map((point) => [(point[0] - originX) / scale, (point[1] - originY) / scale] as const)
  let orientation = 0
  for (let i = 0; i < 4; i++) {
    const a = points[i]!, b = points[(i + 1) % 4]!, c = points[(i + 2) % 4]!
    const cross = (b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0])
    if (!Number.isFinite(cross) || Math.abs(cross) <= 1e-10 || (orientation && Math.sign(cross) !== orientation)) throw new Error(`${label}: degenerate, concave or self-crossing corner order.`)
    orientation = Math.sign(cross)
  }
  const [p0, p1, p2, p3] = points as [ImagePlanePoint, ImagePlanePoint, ImagePlanePoint, ImagePlanePoint]
  const dx1 = p1[0] - p2[0], dx2 = p3[0] - p2[0], dx3 = p0[0] - p1[0] + p2[0] - p3[0]
  const dy1 = p1[1] - p2[1], dy2 = p3[1] - p2[1], dy3 = p0[1] - p1[1] + p2[1] - p3[1]
  const denominator = dx1 * dy2 - dx2 * dy1
  if (Math.abs(denominator) <= 1e-12) throw new Error(`${label}: singular corner homography.`)
  const g = (dx3 * dy2 - dx2 * dy3) / denominator
  const h = (dx1 * dy3 - dx3 * dy1) / denominator
  const a = p1[0] - p0[0] + g * p1[0], b = p3[0] - p0[0] + h * p3[0]
  const d = p1[1] - p0[1] + g * p1[1], e = p3[1] - p0[1] + h * p3[1]
  const determinant = a * (e - p0[1] * h) - b * (d - p0[1] * g) + p0[0] * (d * h - e * g)
  const denominators = [1, 1 + g, 1 + g + h, 1 + h]
  const denominatorScale = Math.max(...denominators.map(Math.abs))
  if (!Number.isFinite(determinant) || Math.abs(determinant) <= 1e-12 || denominators.some((value) => !Number.isFinite(value) || value <= denominatorScale * 1e-10)) throw new Error(`${label}: singular or denominator-crossing image-plane transform.`)
  const matrix: ImagePlaneWarp['renderToSourcePixels'] = [
    (scale * a + originX * g) / width, (scale * b + originX * h) / height, scale * p0[0] + originX,
    (scale * d + originY * g) / width, (scale * e + originY * h) / height, scale * p0[1] + originY,
    g / width, h / height, 1,
  ]
  if (matrix.some((value) => !Number.isFinite(value))) throw new Error(`${label}: nonfinite compiled homography.`)
  return { kind: 'homography', unwarpedViewportPixels: [width, height], renderToSourcePixels: matrix }
}

/** Row-major H applied to an unmirrored, top-left-origin native viewport pixel. */
export function projectImagePlanePixel(warp: ImagePlaneWarp, point: ImagePlanePoint): [number, number] {
  const m = warp.renderToSourcePixels, x = point[0], y = point[1]
  const denominator = m[6] * x + m[7] * y + m[8]
  return [(m[0] * x + m[1] * y + m[2]) / denominator, (m[3] * x + m[4] * y + m[5]) / denominator]
}
