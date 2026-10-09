import * as THREE from 'three'

interface SpringDimensions {
  radius: number
  inset: number
  endCorrection: number
  turns: number
}
export interface SpringCullingBounds {
  update(span: number, restSpan: number): void
}
interface SpringEnvelope {
  negativeHook: THREE.Box3
  positiveHook: THREE.Box3
  coil: 'present' | 'absent'
  negativeTransition: 'present' | 'absent'
  positiveTransition: 'present' | 'absent'
  coilResidualRadius: number
  transitionResidualRadius: number
  tangentNormError: number
  validation: 'valid' | 'invalid'
}
const envelopes = new WeakMap<THREE.BufferGeometry, SpringEnvelope>()
const FLOAT32_EPSILON = 2 ** -23
const TURN_DENOMINATOR_FLOOR = 0.000001

/** Scan the actual decoded deformation attributes once, never the animated frame. */
function envelope(geometry: THREE.BufferGeometry): SpringEnvelope {
  const cached = envelopes.get(geometry)
  if (cached) return cached
  const result: SpringEnvelope = {
    negativeHook: new THREE.Box3(), positiveHook: new THREE.Box3(), coil: 'absent',
    negativeTransition: 'absent', positiveTransition: 'absent',
    coilResidualRadius: 0, transitionResidualRadius: 0, tangentNormError: 0, validation: 'valid',
  }
  const position = geometry.getAttribute('position')
  const coordinate = geometry.getAttribute('springCoordinate')
  const centre = geometry.getAttribute('springRestCentre')
  const tangent = geometry.getAttribute('springRestTangent')
  const point = new THREE.Vector3()
  if (!position || !coordinate || !centre || !tangent
    || coordinate.count !== position.count || centre.count !== position.count || tangent.count !== position.count) {
    result.validation = 'invalid'
  } else for (let i = 0; i < position.count; i++) {
    point.fromBufferAttribute(position, i)
    const kind = coordinate.getX(i), t = coordinate.getY(i)
    const x = tangent.getX(i), y = tangent.getY(i), z = tangent.getZ(i)
    if (!Number.isFinite(point.x + point.y + point.z + kind + t + x + y + z)
      || t < 0 || t > 1) { result.validation = 'invalid'; break }
    if (Math.abs(kind) > 1.5) {
      ;(kind < 0 ? result.negativeHook : result.positiveHook).expandByPoint(point)
      continue
    }
    if (Math.abs(kind) < 0.5) result.coil = 'present'
    else if (kind < 0) result.negativeTransition = 'present'
    else result.positiveTransition = 'present'
    const residual = Math.hypot(point.x - centre.getX(i), point.y - centre.getY(i), point.z - centre.getZ(i))
    if (!Number.isFinite(residual)) { result.validation = 'invalid'; break }
    if (Math.abs(kind) < 0.5) result.coilResidualRadius = Math.max(result.coilResidualRadius, residual)
    else result.transitionResidualRadius = Math.max(result.transitionResidualRadius, residual)
    result.tangentNormError = Math.max(result.tangentNormError, Math.abs(x * x + y * y + z * z - 1))
  }
  envelopes.set(geometry, result)
  return result
}

/**
 * Object-local bounds, not geometry bounds: prepared geometry can be shared by
 * springs with different live lengths. Three r180's Frustum.intersectsObject
 * explicitly prefers an object's boundingSphere over its geometry's rest sphere.
 * The same native mesh and sphere are used by colour and diagnostic passes.
 */
export function createSpringCullingBounds(mesh: THREE.Mesh, dimensions: SpringDimensions): SpringCullingBounds {
  const source = envelope(mesh.geometry)
  const sphere = new THREE.Sphere()
  ;(mesh as THREE.Mesh & { boundingSphere: THREE.Sphere }).boundingSphere = sphere
  mesh.frustumCulled = true
  let previousSpan = NaN, previousRestSpan = NaN
  // springTurn is I + [c]x + [c]x²/d. For a unit new tangent,
  // its transverse squared norm is (1 - |c|²/d)² + |c|². With
  // d=max(1+dot,1e-6), a decoded old-tangent squared-norm error δ
  // bounds that norm by 1 + δ/d + 2d. Allow additional Float32
  // normalization/arithmetic error, including near-antiparallel tangents.
  // This is conservative culling padding, not a GPU residual certificate.
  const normError = source.tangentNormError + 64 * FLOAT32_EPSILON
  const transitionPadding = source.transitionResidualRadius * (1 + normError / TURN_DENOMINATOR_FLOOR + 2 * TURN_DENOMINATOR_FLOOR)
  const { radius, inset, endCorrection, turns } = dimensions
  const angularSpeed = turns * 2 * Math.PI
  const radialSpeed = radius * angularSpeed
  // The decoded parameter and GPU angle multiplication can differ from the
  // original rest tangent. Bound their accumulated Float32 phase error and
  // retain ample highp sin/cos slack; this is not a raster/numeric certificate.
  const phaseSlack = 8 * FLOAT32_EPSILON * Math.abs(angularSpeed) + 0.01
  const phaseCosine = Math.cos(phaseSlack)
  const transitionHighZ = Math.max(0, radius, radius - 0.0015875 * Math.sin(-0.00014851266501942706))
  return {
    update(span, restSpan) {
      if (Object.is(span, previousSpan) && Object.is(restSpan, previousRestSpan)) return
      previousSpan = span; previousRestSpan = restSpan
      if (source.validation === 'invalid' || !Number.isFinite(Math.fround(span)) || !Number.isFinite(Math.fround(restSpan))) {
        // No finite enclosure means no culling, never a disappearing native mesh.
        sphere.center.set(0, 0, 0); sphere.radius = Infinity
        return
      }
      const height = span - 2 * inset - endCorrection
      const restHeight = restSpan - 2 * inset - endCorrection
      if (!Number.isFinite(Math.fround(height * height + radialSpeed * radialSpeed))
        || !Number.isFinite(Math.fround(restHeight * restHeight + radialSpeed * radialSpeed))) {
        sphere.center.set(0, 0, 0); sphere.radius = Infinity
        return
      }
      // Coil tangents share their winding phase: their ideal dot is
      // (h*h0 + k²*cos(deltaPhase))/(hypot(h,k)*hypot(h0,k)), independent
      // of the individual vertex parameter. Positive heights have no
      // antiparallel singularity. Malformed/compressed spans keep the floor.
      let coilDenominator = TURN_DENOMINATOR_FLOOR
      if (height > 0 && restHeight > 0 && phaseSlack < Math.PI / 2) {
        const minimumDot = (height * restHeight + radialSpeed * radialSpeed * phaseCosine)
          / (Math.hypot(height, radialSpeed) * Math.hypot(restHeight, radialSpeed))
        coilDenominator = Math.max(TURN_DENOMINATOR_FLOOR, 1 + minimumDot - 64 * FLOAT32_EPSILON)
      }
      const coilPadding = source.coilResidualRadius * (1 + normError / coilDenominator + 2 * TURN_DENOMINATOR_FLOOR)
      let minX = Infinity, minY = Infinity, minZ = Infinity
      let maxX = -Infinity, maxY = -Infinity, maxZ = -Infinity
      const shift = (span - restSpan) / 2
      const negative = source.negativeHook, positive = source.positiveHook
      if (!negative.isEmpty()) {
        minX = negative.min.x - shift; maxX = negative.max.x - shift
        minY = negative.min.y; maxY = negative.max.y
        minZ = negative.min.z; maxZ = negative.max.z
      }
      if (!positive.isEmpty()) {
        minX = Math.min(minX, positive.min.x + shift); maxX = Math.max(maxX, positive.max.x + shift)
        minY = Math.min(minY, positive.min.y); maxY = Math.max(maxY, positive.max.y)
        minZ = Math.min(minZ, positive.min.z); maxZ = Math.max(maxZ, positive.max.z)
      }
      if (source.coil === 'present') {
        const start = -span / 2 + inset, end = span / 2 - inset - endCorrection
        minX = Math.min(minX, Math.min(start, end) - coilPadding)
        maxX = Math.max(maxX, Math.max(start, end) + coilPadding)
        minY = Math.min(minY, -radius - coilPadding); maxY = Math.max(maxY, radius + coilPadding)
        minZ = Math.min(minZ, -radius - coilPadding); maxZ = Math.max(maxZ, radius + coilPadding)
      }
      if (source.negativeTransition === 'present' || source.positiveTransition === 'present') {
        // A cubic Bezier lies in its four-control-point convex hull. The
        // rotating p2 handle is <=1.5875mm on each axis for every live span.
        const offset = -(span - 0.0494792) / 2
        const bx = -0.0197104 + offset
        const lowX = Math.min(-0.022225 + offset, -0.0206375 + offset, bx - 0.0015875)
        const highX = Math.max(-0.022225 + offset, -0.0206375 + offset, bx + 0.0015875)
        const lowY = Math.min(0, radius, -0.0015875) - transitionPadding
        const highY = Math.max(0, radius, 0.0015875) + transitionPadding
        const highZ = transitionHighZ
        minY = Math.min(minY, lowY); maxY = Math.max(maxY, highY)
        if (source.negativeTransition === 'present') {
          minX = Math.min(minX, lowX - transitionPadding); maxX = Math.max(maxX, highX + transitionPadding)
          minZ = Math.min(minZ, -transitionPadding); maxZ = Math.max(maxZ, highZ + transitionPadding)
        }
        if (source.positiveTransition === 'present') {
          minX = Math.min(minX, -highX - transitionPadding); maxX = Math.max(maxX, -lowX + transitionPadding)
          minZ = Math.min(minZ, -highZ - transitionPadding); maxZ = Math.max(maxZ, transitionPadding)
        }
      }
      const padding = 128 * FLOAT32_EPSILON * Math.max(1, Math.abs(span), Math.abs(restSpan), coilPadding, transitionPadding)
      sphere.center.set((minX + maxX) / 2, (minY + maxY) / 2, (minZ + maxZ) / 2)
      sphere.radius = Math.hypot(maxX - minX, maxY - minY, maxZ - minZ) / 2 + padding
      if (!Number.isFinite(sphere.radius)) { sphere.center.set(0, 0, 0); sphere.radius = Infinity }
    },
  }
}
