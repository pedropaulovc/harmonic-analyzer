// Finite-draw arithmetic enclosures, not a GLSL trigonometric accuracy claim.
// sin/cos/atan precision is unspecified by GLSL ES 3.00. Their *observed same
// program* centre/tangent witnesses are constrained by the original curve and
// every original position's unchanged 1e-7m check before normals are admitted.
const bits = new Uint32Array(1), floats = new Float32Array(bits.buffer)
export function nextFloat32(value, direction) {
  if (Number.isNaN(value) || (value === Infinity && direction > 0) || (value === -Infinity && direction < 0)) return value
  const rounded = Math.fround(value)
  if (rounded === 0) { bits[0] = direction > 0 ? 1 : 0x80000001; return floats[0] }
  floats[0] = rounded
  bits[0] += (rounded > 0) === (direction > 0) ? 1 : -1
  return floats[0]
}
/** One workspace per physical primitive, reused by every vertex. */
export function createF32EnclosureWorkspace() {
  const intervals = Array.from({ length: 512 }, () => new Float64Array(2)), vectors = Array.from({ length: 48 }, () => new Array(3))
  return { intervals, vectors, intervalCount: 0, vectorCount: 0, reset() { this.intervalCount = 0; this.vectorCount = 0 } }
}
function interval(lo, hi, workspace) {
  const out = workspace ? workspace.intervals[workspace.intervalCount++] : [0, 0]
  if (!out) throw new RangeError('Arithmetic workspace capacity exceeded')
  out[0] = lo; out[1] = hi
  return out
}
function vector(workspace) {
  const out = workspace ? workspace.vectors[workspace.vectorCount++] : new Array(3)
  if (!out) throw new RangeError('Vector workspace capacity exceeded')
  return out
}
export const pointInterval = (value, workspace) => interval(value, value, workspace)
function rounded(lo, hi, workspace) {
  if (!Number.isFinite(lo) || !Number.isFinite(hi)) throw new RangeError('Unbounded arithmetic enclosure')
  // Eight outward Float32 neighbours cover the admitted basic arithmetic
  // envelope. This is never a trigonometric ULP or continuous-state claim.
  for (let i = 0; i < 8; i++) { lo = nextFloat32(lo, -1); hi = nextFloat32(hi, 1) }
  return interval(lo, hi, workspace)
}
export const iadd = (a, b, workspace) => rounded(a[0] + b[0], a[1] + b[1], workspace)
export const isub = (a, b, workspace) => rounded(a[0] - b[1], a[1] - b[0], workspace)
export function imul(a, b, workspace) {
  const aa = a[0] * b[0], ab = a[0] * b[1], ba = a[1] * b[0], bb = a[1] * b[1]
  return rounded(Math.min(aa, ab, ba, bb), Math.max(aa, ab, ba, bb), workspace)
}
export function idiv(a, b, workspace) {
  if (b[0] <= 0 && b[1] >= 0) throw new RangeError('Division interval crosses zero')
  const aa = a[0] / b[0], ab = a[0] / b[1], ba = a[1] / b[0], bb = a[1] / b[1]
  return rounded(Math.min(aa, ab, ba, bb), Math.max(aa, ab, ba, bb), workspace)
}
export const contains = (range, value) => Number.isFinite(value) && value >= range[0] && value <= range[1]
function iv(values, workspace) { const out = vector(workspace); for (let i = 0; i < 3; i++) out[i] = pointInterval(values[i], workspace); return out }
function cross(a, b, workspace) {
  const out = vector(workspace)
  for (let i = 0; i < 3; i++) { const j = (i + 1) % 3, k = (i + 2) % 3; out[i] = isub(imul(a[j], b[k], workspace), imul(a[k], b[j], workspace), workspace) }
  return out
}
function dot(a, b, workspace) { return iadd(iadd(imul(a[0], b[0], workspace), imul(a[1], b[1], workspace), workspace), imul(a[2], b[2], workspace), workspace) }
function normalize(v, workspace) {
  const squares = vector(workspace)
  for (let i = 0; i < 3; i++) { const a = v[i]; squares[i] = rounded(a[0] <= 0 && a[1] >= 0 ? 0 : Math.min(a[0] * a[0], a[1] * a[1]), Math.max(a[0] * a[0], a[1] * a[1]), workspace) }
  const length2 = iadd(iadd(squares[0], squares[1], workspace), squares[2], workspace)
  if (!(length2[0] > 0)) throw new RangeError('Normal enclosure has no positive length lower bound')
  const length = rounded(Math.sqrt(length2[0]), Math.sqrt(length2[1]), workspace), out = vector(workspace)
  for (let i = 0; i < 3; i++) out[i] = idiv(v[i], length, workspace)
  return out
}
export function transportNormalEnclosure(rawNormal, rawRestTangent, actualTangent, rigid = false, workspace) {
  workspace?.reset()
  const normal = iv(rawNormal, workspace)
  if (rigid) return normal
  const from = iv(rawRestTangent, workspace), to = iv(actualTangent, workspace), axis = cross(from, to, workspace), k = cross(axis, normal, workspace), kk = cross(axis, k, workspace), cosine = dot(from, to, workspace)
  const denominator = iadd(pointInterval(1, workspace), cosine, workspace), floor = Math.fround(0.000001), out = vector(workspace)
  denominator[0] = Math.max(denominator[0], floor); denominator[1] = Math.max(denominator[1], floor)
  for (let i = 0; i < 3; i++) out[i] = iadd(iadd(normal[i], k[i], workspace), idiv(kk[i], denominator, workspace), workspace)
  return out
}
export function transformNormalEnclosure(objectEnclosure, normalMatrix, normalizeResult = true, workspace) {
  const out = vector(workspace)
  for (let row = 0; row < 3; row++) out[row] = iadd(iadd(imul(pointInterval(Math.fround(normalMatrix[row]), workspace), objectEnclosure[0], workspace), imul(pointInterval(Math.fround(normalMatrix[row + 3]), workspace), objectEnclosure[1], workspace), workspace), imul(pointInterval(Math.fround(normalMatrix[row + 6]), workspace), objectEnclosure[2], workspace), workspace)
  return normalizeResult ? normalize(out, workspace) : out
}
export function normalError(actual, original, enclosure, out = {}) {
  const actualLength = Math.hypot(actual[0], actual[1], actual[2]), expectedLength = Math.hypot(original[0], original[1], original[2])
  out.actualLength = actualLength; out.expectedLength = expectedLength
  out.euclideanError = Math.hypot(actual[0] - original[0], actual[1] - original[1], actual[2] - original[2])
  out.angularErrorRadians = actualLength > 0 && expectedLength > 0 ? Math.atan2(Math.hypot(actual[1] * original[2] - actual[2] * original[1], actual[2] * original[0] - actual[0] * original[2], actual[0] * original[1] - actual[1] * original[0]), actual[0] * original[0] + actual[1] * original[1] + actual[2] * original[2]) : null
  out.lengthError = Math.abs(actualLength - expectedLength)
  out.enclosureEuclideanBound = Math.hypot(Math.max(Math.abs(enclosure[0][0] - original[0]), Math.abs(enclosure[0][1] - original[0])), Math.max(Math.abs(enclosure[1][0] - original[1]), Math.abs(enclosure[1][1] - original[1])), Math.max(Math.abs(enclosure[2][0] - original[2]), Math.abs(enclosure[2][1] - original[2])))
  out.inside = contains(enclosure[0], actual[0]) && contains(enclosure[1], actual[1]) && contains(enclosure[2], actual[2])
  return out
}

/** Independent unwrapped F64 phase; constant curve construction is per state. */
export function createOriginalCurveWitnessEvaluator(parameters, length) {
  const p = parameters, height = length - 2 * p.insetM - p.endCorrectionM, arc = p.radiusM * p.turns * 2 * Math.PI, q = p.transition
  let p0, p1, p2, p3, transitionAngle
  if (q) {
    const shift = -(length - q.referenceLengthM) / 2, pitch = (length - 2 * p.insetM) / p.turns
    transitionAngle = Math.atan2(-p.radiusM, pitch / (2 * Math.PI))
    p0 = [q.x0M + shift, p.radiusM, 0]; p1 = [q.x1M + shift, p.radiusM, 0]; p3 = [q.x3M + shift, 0, p.radiusM]
    p2 = [p3[0] - q.handleOffsetM * Math.cos(transitionAngle) * Math.cos(q.polarRad), -q.handleOffsetM * Math.sin(transitionAngle) * Math.cos(q.polarRad), p.radiusM - q.handleOffsetM * Math.sin(q.polarRad)]
  }
  return (kind, t, out) => {
    if (Math.abs(kind) === 2) return null
    const centre = out.centre, tangent = out.tangent
    if (kind === 0) {
      const angle = t * p.turns * 2 * Math.PI, sine = Math.sin(angle), cosine = Math.cos(angle)
      out.unwrappedAngleRadians = angle
      centre[0] = -length / 2 + p.insetM + height * t; centre[1] = -p.radiusM * sine; centre[2] = p.radiusM * cosine
      tangent[0] = height; tangent[1] = -arc * cosine; tangent[2] = -arc * sine
    } else {
      if (!q) throw new Error('Original transition parameters absent')
      out.unwrappedAngleRadians = transitionAngle
      const u = 1 - t, a = u * u * u, b = 3 * u * u * t, c = 3 * u * t * t, d = t * t * t
      for (let i = 0; i < 3; i++) { centre[i] = a * p0[i] + b * p1[i] + c * p2[i] + d * p3[i]; tangent[i] = 3 * u * u * (p1[i] - p0[i]) + 6 * u * t * (p2[i] - p1[i]) + 3 * t * t * (p3[i] - p2[i]) }
    }
    const inverse = 1 / (Math.sqrt(tangent[0] * tangent[0] + tangent[1] * tangent[1] + tangent[2] * tangent[2]) || 1)
    for (let i = 0; i < 3; i++) tangent[i] *= inverse
    if (kind > 0) { centre[0] *= -1; centre[2] *= -1; tangent[0] *= -1; tangent[2] *= -1 }
    return out
  }
}
export function originalCurveWitness(parameters, kind, t, length) { return createOriginalCurveWitnessEvaluator(parameters, length)(kind, t, { centre: [0, 0, 0], tangent: [0, 0, 0] }) }

/** Shared transition control intervals come from all actual centres, never final
 * normals. All per-vertex interval/vector slots are reused. */
export function createFiniteCurveWitnessProof(parameters, length) {
  const p = parameters, L = Math.fround(length), radius = Math.fround(p.radiusM), height = isub(pointInterval(L), pointInterval(Math.fround(2 * p.insetM + p.endCorrectionM))), arc = Math.fround(p.radiusM * p.turns * 2 * Math.PI)
  const workspace = createF32EnclosureWorkspace(), transition = [null, null], data = { p0: null, p1: null, p3: null, T: null, U: null, control: null }
  if (p.transition) {
    const q = p.transition, shift = imul(isub(pointInterval(L), pointInterval(Math.fround(q.referenceLengthM))), pointInterval(-0.5))
    data.p0 = [iadd(pointInterval(Math.fround(q.x0M)), shift), pointInterval(radius), pointInterval(0)]
    data.p1 = [iadd(pointInterval(Math.fround(q.x1M)), shift), pointInterval(radius), pointInterval(0)]
    data.p3 = [iadd(pointInterval(Math.fround(q.x3M)), shift), pointInterval(0), pointInterval(radius)]
  }
  function transitionData(kind, t, centre) {
    if (!data.p0) throw new Error('Original transition parameters absent')
    workspace.reset()
    const T = pointInterval(t, workspace), U = isub(pointInterval(1, workspace), T, workspace), u2 = imul(U, U, workspace), t2 = imul(T, T, workspace)
    const a = imul(u2, U, workspace), b = imul(imul(pointInterval(3, workspace), u2, workspace), T, workspace), c = imul(imul(pointInterval(3, workspace), U, workspace), t2, workspace), d = imul(t2, T, workspace)
    data.T = T; data.U = U; data.control = null
    if (c[0] > 0) {
      const control = vector(workspace)
      for (let i = 0; i < 3; i++) control[i] = idiv(isub(isub(isub(pointInterval(kind > 0 && i !== 1 ? -centre[i] : centre[i], workspace), imul(a, data.p0[i], workspace), workspace), imul(b, data.p1[i], workspace), workspace), imul(d, data.p3[i], workspace), workspace), c, workspace)
      data.control = control
    }
    return data
  }
  function observe(kind, t, centre) {
    if (Math.abs(kind) !== 1) return
    const control = transitionData(kind, t, centre).control
    if (!control) return
    const index = kind > 0 ? 1 : 0
    if (!transition[index]) transition[index] = [[-Infinity, Infinity], [-Infinity, Infinity], [-Infinity, Infinity]]
    const previous = transition[index]
    for (let i = 0; i < 3; i++) { previous[i][0] = Math.max(previous[i][0], control[i][0]); previous[i][1] = Math.min(previous[i][1], control[i][1]); if (previous[i][0] > previous[i][1]) throw new Error('Transition centres disagree on shared native control point') }
  }
  function check(kind, t, centre, tangent, restTangent) {
    if (Math.abs(kind) === 2) return tangent[0] === restTangent[0] && tangent[1] === restTangent[1] && tangent[2] === restTangent[2]
    let expected
    if (kind === 0) {
      workspace.reset()
      const sine = idiv(pointInterval(-centre[1], workspace), pointInterval(radius, workspace), workspace), cosine = idiv(pointInterval(centre[2], workspace), pointInterval(radius, workspace), workspace)
      if (!contains(iadd(imul(sine, sine, workspace), imul(cosine, cosine, workspace), workspace), 1)) return false
      if (!contains(iadd(iadd(imul(pointInterval(L, workspace), pointInterval(-0.5, workspace), workspace), pointInterval(Math.fround(p.insetM), workspace), workspace), imul(height, pointInterval(t, workspace), workspace), workspace), centre[0])) return false
      const derivative = vector(workspace); derivative[0] = height; derivative[1] = imul(pointInterval(-arc, workspace), cosine, workspace); derivative[2] = imul(pointInterval(-arc, workspace), sine, workspace)
      expected = normalize(derivative, workspace)
    } else {
      const control = transition[kind > 0 ? 1 : 0]
      if (!control) return false
      const { p0, p1, p3, T, U } = transitionData(kind, t, centre), derivative = vector(workspace)
      const a = imul(pointInterval(3, workspace), imul(U, U, workspace), workspace), b = imul(imul(pointInterval(6, workspace), U, workspace), T, workspace), c = imul(pointInterval(3, workspace), imul(T, T, workspace), workspace)
      for (let i = 0; i < 3; i++) derivative[i] = iadd(iadd(imul(a, isub(p1[i], p0[i], workspace), workspace), imul(b, isub(control[i], p1[i], workspace), workspace), workspace), imul(c, isub(p3[i], control[i], workspace), workspace), workspace)
      expected = normalize(derivative, workspace)
      if (kind > 0) { const x = expected[0][0], z = expected[2][0]; expected[0][0] = -expected[0][1]; expected[0][1] = -x; expected[2][0] = -expected[2][1]; expected[2][1] = -z }
    }
    return contains(expected[0], tangent[0]) && contains(expected[1], tangent[1]) && contains(expected[2], tangent[2])
  }
  return { observe, check }
}

/** Normal reference is the affine differential of the protected original
 * position evaluator. Auxiliary basis points establish no mesh ancestry. */
export function createOriginalSpringNormalReference(oracle) {
  const attribute = size => ({ array: new Float32Array(size), itemSize: size, count: 1, normalized: false, isInterleavedBufferAttribute: false })
  const probe = { position: attribute(3), springCoordinate: attribute(2), springRestCentre: attribute(3), springRestTangent: attribute(3) }
  const centre = new Float64Array(3), basis = new Float64Array(3), columns = new Float64Array(9)
  let constructionComponentBound = 0
  function deformNormal(attributes, length, index, out) {
    const kind = attributes.springCoordinate.array[index * 2], raw = attributes.normal.array, start = index * 3
    constructionComponentBound = 0
    if (Math.abs(kind) === 2) { for (let axis = 0; axis < 3; axis++) out[axis] = raw[start + axis]; return out }
    probe.springCoordinate.array[0] = kind; probe.springCoordinate.array[1] = attributes.springCoordinate.array[index * 2 + 1]
    for (let axis = 0; axis < 3; axis++) { const value = attributes.springRestCentre.array[start + axis]; probe.position.array[axis] = value; probe.springRestCentre.array[axis] = value; probe.springRestTangent.array[axis] = attributes.springRestTangent.array[start + axis] }
    oracle.deform(probe, length, 0, centre)
    let maximumColumnError = 0
    const fromMagnitude = Math.abs(probe.springRestTangent.array[0]) + Math.abs(probe.springRestTangent.array[1]) + Math.abs(probe.springRestTangent.array[2])
    const intermediateBound = 8 * fromMagnitude * fromMagnitude / oracle.parameters.rotationDenominatorFloor + 4 * fromMagnitude + 1
    for (let axis = 0; axis < 3; axis++) {
      const original = probe.position.array[axis], offset = Math.max(1, Math.abs(original) * 2 ** -22)
      probe.position.array[axis] = original + offset
      const representedDelta = probe.position.array[axis] - original
      if (!(representedDelta > 0) || !Number.isFinite(representedDelta)) throw new RangeError('Original normal differential basis is unresolved')
      oracle.deform(probe, length, 0, basis)
      for (let row = 0; row < 3; row++) {
        columns[axis * 3 + row] = (basis[row] - centre[row]) / representedDelta
        // Outward F64 construction envelope for the original scalar evaluator,
        // subtraction, represented division and subsequent linear combination.
        maximumColumnError = Math.max(maximumColumnError, (Math.abs(basis[row]) + Math.abs(centre[row]) + intermediateBound) * Number.EPSILON * 512 / representedDelta)
      }
      probe.position.array[axis] = original
    }
    const x = raw[start], y = raw[start + 1], z = raw[start + 2], magnitude = Math.abs(x) + Math.abs(y) + Math.abs(z)
    for (let row = 0; row < 3; row++) out[row] = columns[row] * x + columns[row + 3] * y + columns[row + 6] * z
    constructionComponentBound = maximumColumnError * magnitude + Number.EPSILON * 16 * (Math.abs(out[0]) + Math.abs(out[1]) + Math.abs(out[2]) + magnitude)
    return out
  }
  return Object.freeze({ deformNormal, centre, get constructionComponentBound() { return constructionComponentBound }, policy: 'protected-original-F64-position-affine-differential-with-outward-construction-bound; no ported spring law' })
}
