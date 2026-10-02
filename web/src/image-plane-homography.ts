import type { ImagePlaneWarp, SourceLayoutEntry } from './scene'

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

export interface ImagePlaneFootprintContext {
  rectSourcePixels: readonly [number, number, number, number]
  unwarpedViewportPixels: readonly [number, number]
  sourceToRenderPixels: ImagePlaneWarp['renderToSourcePixels']
}

/** Validate the resolved support and invert once for an entire measurement certificate. */
export function prepareImagePlaneFootprintContext(context: Pick<SourceLayoutEntry, 'rectSourcePixels' | 'resolvedImagePlaneWarp'>, label: string): ImagePlaneFootprintContext | null {
  if (!context || typeof context !== 'object' || Array.isArray(context)
    || !Object.hasOwn(context, 'rectSourcePixels') || !Object.hasOwn(context, 'resolvedImagePlaneWarp')) throw new Error(`${label}: an explicit resolved image-plane context is required.`)
  const rect = context.rectSourcePixels
  if (!Array.isArray(rect) || rect.length !== 4) throw new Error(`${label}: a finite positive source ROI is required.`)
  rect.forEach((value) => finite(value, label))
  if (rect[0] < 0 || rect[1] < 0 || rect[2] <= 0 || rect[3] <= 0 || !Number.isFinite(rect[0] + rect[2]) || !Number.isFinite(rect[1] + rect[3])) throw new Error(`${label}: a finite positive source ROI is required.`)
  const warp = context.resolvedImagePlaneWarp
  if (warp === null) return null
  if (!warp || warp.kind !== 'homography' || !Array.isArray(warp.unwarpedViewportPixels) || warp.unwarpedViewportPixels.length !== 2
    || !Array.isArray(warp.renderToSourcePixels) || warp.renderToSourcePixels.length !== 9) throw new Error(`${label}: a resolved homography or explicit null is required.`)
  const [width, height] = warp.unwarpedViewportPixels
  finite(width, label); finite(height, label)
  if (width <= 0 || height <= 0) throw new Error(`${label}: native viewport dimensions must be positive.`)
  const m = warp.renderToSourcePixels
  m.forEach((value) => finite(value, label))
  const nativeCorners: ImagePlaneCorners = [[0, 0], [width, 0], [width, height], [0, height]]
  for (const point of nativeCorners) {
    const denominator = m[6] * point[0] + m[7] * point[1] + m[8]
    if (!Number.isFinite(denominator) || denominator <= 1e-10) throw new Error(`${label}: homography leaves the positive projective branch.`)
  }
  const sourceCorners = nativeCorners.map((point) => projectImagePlanePixel(warp, point))
  let orientation = 0
  for (let i = 0; i < 4; i++) {
    const a = sourceCorners[i]!, b = sourceCorners[(i + 1) % 4]!, c = sourceCorners[(i + 2) % 4]!
    a.forEach((value) => finite(value, label))
    const cross = (b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0])
    if (!Number.isFinite(cross) || cross === 0 || (orientation && Math.sign(cross) !== orientation)) throw new Error(`${label}: resolved source support must be a convex quadrilateral.`)
    orientation = Math.sign(cross)
  }
  const inverse: [number, number, number, number, number, number, number, number, number] = [
    m[4] * m[8] - m[5] * m[7], m[2] * m[7] - m[1] * m[8], m[1] * m[5] - m[2] * m[4],
    m[5] * m[6] - m[3] * m[8], m[0] * m[8] - m[2] * m[6], m[2] * m[3] - m[0] * m[5],
    m[3] * m[7] - m[4] * m[6], m[1] * m[6] - m[0] * m[7], m[0] * m[4] - m[1] * m[3],
  ]
  const determinant = m[0] * inverse[0] + m[1] * inverse[3] + m[2] * inverse[6]
  if (!Number.isFinite(determinant) || Math.abs(determinant) < 1e-12) throw new Error(`${label}: singular resolved homography.`)
  for (let i = 0; i < inverse.length; i++) inverse[i] = finite(inverse[i]! / determinant, label)
  return { rectSourcePixels: rect, unwarpedViewportPixels: warp.unwarpedViewportPixels, sourceToRenderPixels: inverse }
}

/** Corner extrema bound the entire convex final-source localization square on a positive branch. */
export function imagePlaneSourceFootprintBounds(context: ImagePlaneFootprintContext, sourcePoint: ImagePlanePoint, sourceSigmaPx: number, geometryRadiusViewportPx: number, label: string): [number, number, number, number] {
  if (!Array.isArray(sourcePoint) || sourcePoint.length !== 2) throw new Error(`${label}: a finite source pixel pair is required.`)
  finite(sourcePoint[0], label); finite(sourcePoint[1], label)
  finite(sourceSigmaPx, label); finite(geometryRadiusViewportPx, label)
  if (sourceSigmaPx < 0 || geometryRadiusViewportPx < 0) throw new Error(`${label}: localization and geometry radii must be nonnegative.`)
  const m = context.sourceToRenderPixels, rect = context.rectSourcePixels, [width, height] = context.unwarpedViewportPixels
  let minX = Infinity, minY = Infinity, maxX = -Infinity, maxY = -Infinity
  for (let i = 0; i < 4; i++) {
    const x = sourcePoint[0] + (i & 1 ? sourceSigmaPx : -sourceSigmaPx)
    const y = sourcePoint[1] + (i & 2 ? sourceSigmaPx : -sourceSigmaPx)
    if (!Number.isFinite(x) || !Number.isFinite(y) || x < rect[0] || y < rect[1] || x >= rect[0] + rect[2] || y >= rect[1] + rect[3]) throw new Error(`${label}: source localization footprint leaves the measured source ROI.`)
    const denominator = m[6] * x + m[7] * y + m[8]
    if (!Number.isFinite(denominator) || denominator <= 1e-10) throw new Error(`${label}: source localization footprint crosses the projective horizon.`)
    const nativeX = finite((m[0] * x + m[1] * y + m[2]) / denominator, label)
    const nativeY = finite((m[3] * x + m[4] * y + m[5]) / denominator, label)
    if (nativeX < 0 || nativeY < 0 || nativeX >= width || nativeY >= height) throw new Error(`${label}: source localization footprint leaves the measured source quadrilateral/native viewport.`)
    minX = Math.min(minX, nativeX); minY = Math.min(minY, nativeY)
    maxX = Math.max(maxX, nativeX); maxY = Math.max(maxY, nativeY)
  }
  // Source sigma is only inverse-mapped to select support; it remains final-source pixels in the budget.
  return [minX - geometryRadiusViewportPx, minY - geometryRadiusViewportPx, maxX + geometryRadiusViewportPx, maxY + geometryRadiusViewportPx]
}
