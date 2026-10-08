export const NATIVE_LINE_STATIONS = Object.freeze([0, 0.25, 0.5, 0.75, 1])

/** Diagnostic marker identities are not source-observed point anchors or FIT/CHECK roles. */
export function nativeLineEndpointId(viewId, lineId, endpoint) {
  return JSON.stringify(['native-line-endpoint', viewId, lineId, endpoint])
}

/** Released membership, real articulation and effective draw overrides, never name-prefix motion. */
export function fixedNativeLinePart(partPath, authority, effectiveSourceOverridePartPaths) {
  if (!authority?.paths?.has(partPath) || !Array.isArray(authority.bindings)
    || !Array.isArray(effectiveSourceOverridePartPaths)
    || effectiveSourceOverridePartPaths.some(path => typeof path !== 'string' || !path.trim())
    || new Set(effectiveSourceOverridePartPaths).size !== effectiveSourceOverridePartPaths.length) return false
  const ancestors = partPath.split('/').map((_, index, segments) => segments.slice(0, index + 1).join('/'))
  return !ancestors.some(path => effectiveSourceOverridePartPaths.includes(path))
    && !authority.bindings.some(binding => binding.motion !== 'paper-fixed'
      && ancestors.some(path => binding.pattern.test(path)))
}

/** Same held-out finite-segment geometry as fit-source.native_line_candidate_residual. */
export function nativeLineReadbackResidual(projected, observed) {
  const delta = [projected[1][0] - projected[0][0], projected[1][1] - projected[0][1]]
  const squared = delta[0] ** 2 + delta[1] ** 2
  if (!projected.every(point => point.length === 2 && point.every(Number.isFinite)) || squared <= 1e-12) throw new Error('Native line is degenerate in current GPU projection')
  const fractions = observed.map(point => ((point[0] - projected[0][0]) * delta[0] + (point[1] - projected[0][1]) * delta[1]) / squared)
  return {
    perpendicularErrorsPx: observed.map((point, index) => Math.hypot(point[0] - projected[0][0] - fractions[index] * delta[0], point[1] - projected[0][1] - fractions[index] * delta[1])),
    nativeSegmentCoversObservation: fractions.every(fraction => fraction >= 0 && fraction <= 1),
  }
}

/** Projects draw-bound world vertices, never inventory REST or fitted source coordinates. */
export function projectNativeLineWorld(parameters, world, rect, presentation) {
  return world.map(point => {
    const cv = parameters.rotation.map((row, index) => row.reduce((sum, value, axis) => sum + value * point[axis], parameters.translation[index]))
    if (!cv.every(Number.isFinite) || cv[2] <= 0) throw new Error('Qualified finite native line endpoint is behind the current source camera')
    let x = parameters.principal[0] + parameters.focal * cv[0] / cv[2]
    const y = parameters.principal[1] + parameters.focal * cv[1] / cv[2]
    if (presentation === 'horizontal-mirror') x = rect[2] - x
    return [rect[0] + x, rect[1] + y]
  })
}
