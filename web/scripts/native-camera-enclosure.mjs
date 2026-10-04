// Node authority for a finite camera draw, after its full physical-state proof.
// This module never bounds sin/cos, invents raster observations, or relaxes the
// original local/world 1e-7 metre policy. Domains retain triangle support bounds,
// not the all-vertex TF arrays. Camera results are constructed afresh each call.
import { Matrix3, Matrix4, PerspectiveCamera } from 'three'

const POSITION_LIMIT = 1e-7
const MIN_NORMAL = 2 ** -126
const EPS64 = Number.EPSILON
const MAX_DOMAINS = 2048
const IDENTITY4 = Object.freeze([1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1])
const finite = value => Number.isFinite(value)
const absmax = range => Math.max(Math.abs(range[0]), Math.abs(range[1]))
const norm = values => Math.hypot(...values)
const insist = (condition, reason) => { if (!condition) throw new Error(reason) }
const outward = value => value + Math.max(Math.abs(value), MIN_NORMAL) * EPS64 * 16
const exact = (a, b) => a.length === b.length && a.every((value, i) => value === b[i])
const range = values => { insist(values.length === 6 && values.every(finite) && values.slice(0, 3).every((v, i) => v <= values[i + 3]), 'Finite ordered physical bounds required'); return [0, 1, 2].map(i => [values[i], values[i + 3]]) }
const emptyBounds = () => [Infinity, Infinity, Infinity, -Infinity, -Infinity, -Infinity]
function addError(interval, error) { return [interval[0] - outward(error), interval[1] + outward(error)] }
function linear(matrix, input, rows = 4, columns = 4) {
  return Array.from({ length: rows }, (_, row) => {
    let lo = 0, hi = 0, absolute = 0
    for (let column = 0; column < columns; column++) {
      const coefficient = matrix[row + column * rows], term = input[column]
      lo += coefficient * (coefficient < 0 ? term[1] : term[0]); hi += coefficient * (coefficient < 0 ? term[0] : term[1])
      absolute += Math.abs(coefficient) * absmax(term)
    }
    const pad = outward(absolute) * EPS64 * (columns * 4 + 4)
    return [lo - pad, hi + pad]
  })
}
// ES highp basic arithmetic: one ULP per operation. The MIN_NORMAL term also
// encloses permitted subnormal flushing. Every binary reduction tree of a dot
// has n products and n-1 sums. A contracted FMA removes rounding nodes, so the
// same sum-of-absolute-terms envelope covers fused and unfused reductions.
function ulpAllowance(magnitude) {
  insist(finite(magnitude) && magnitude >= 0 && magnitude < 2 ** 127, 'Float32 arithmetic enclosure overflows')
  return Math.max(MIN_NORMAL, 2 ** (Math.floor(Math.log2(Math.max(magnitude, MIN_NORMAL))) - 23))
}
function dotRound(coefficients, magnitudes) {
  let sum = 0, productError = 0
  for (let i = 0; i < coefficients.length; i++) { const magnitude = Math.abs(coefficients[i]) * magnitudes[i]; sum += magnitude; productError += ulpAllowance(magnitude) }
  let bound = productError
  for (let i = 1; i < coefficients.length; i++) bound += ulpAllowance(outward(sum + bound))
  return outward(bound)
}
function matrixError(original, uploaded, inputBounds, inputError, size = 4) {
  const magnitudes = inputBounds.map(absmax)
  return Array.from({ length: size }, (_, row) => {
    const coefficients = Array.from({ length: size }, (_, column) => uploaded[row + column * size])
    let error = 0
    for (let column = 0; column < size; column++) error += Math.abs(coefficients[column] - original[row + column * size]) * magnitudes[column] + Math.abs(coefficients[column]) * inputError[column]
    return outward(error + dotRound(coefficients, magnitudes.map((value, i) => value + inputError[i])))
  })
}
function homogeneous(point) { return [...point, [1, 1]] }
function transformPointInto(matrix, point, out, size = 4, homogeneousW = undefined) {
  for (let row = 0; row < size; row++) {
    let result = 0
    for (let column = 0; column < size; column++) result += matrix[row + column * size] * (column === 3 && homogeneousW !== undefined ? homogeneousW : point[column])
    out[row] = result
  }
  return out
}
// Include legal reassociation of the two linear dots, not only a materialized
// mvPosition. Each of the 16 polynomial terms may multiply P*A first or A*x
// first; the largest intermediate rounding envelope covers both trees.
function reassociatedClipError(view, projection, localBounds, localError) {
  const x = [...localBounds.map(absmax), 1], dx = [...localError, 0]
  return Array.from({ length: 4 }, (_, row) => {
    let sum = 0, error = 0, flushAmplification = 1
    for (let k = 0; k < 4; k++) for (let j = 0; j < 4; j++) {
      const p = Math.abs(projection[row + 4 * k]), a = Math.abs(view[k + 4 * j]), input = x[j] + dx[j]
      const term = p * a * input, left = input * ulpAllowance(p * a), right = p * ulpAllowance(a * input)
      sum += term; error += Math.max(left, right) + ulpAllowance(outward(term + Math.max(left, right)))
      flushAmplification = Math.max(flushAmplification, p, a, input, p * a, p * input, a * input)
    }
    for (let i = 1; i < 16; i++) error += ulpAllowance(outward(sum + error))
    // Sixteen degree-three terms need at most 32 products and 15 sums.
    // gamma(47), with one-ULP relative epsilon rather than half-ULP unit
    // roundoff, also encloses factoring/distributing either linear matrix dot.
    // Each flushed subnormal node is charged through all remaining factors.
    const operations = 47, epsilon = 2 ** -23
    const anyTree = (operations * epsilon * sum + operations * MIN_NORMAL * flushAmplification) / (1 - operations * epsilon)
    return outward(Math.max(error, anyTree))
  })
}

// Evaluate only integer preprocessor conditionals; do not execute shader text.
function condition(text, defines) {
  const tokens = text.match(/defined|[A-Za-z_]\w*|\d+|&&|\|\||==|!=|<=|>=|[!()<>+\-*/%]/g) ?? []
  insist(tokens.join('') === text.replace(/\s/g, ''), 'Unsupported shader conditional syntax')
  let at = 0
  const precedence = { '||': 1, '&&': 2, '==': 3, '!=': 3, '<': 4, '>': 4, '<=': 4, '>=': 4, '+': 5, '-': 5, '*': 6, '/': 6, '%': 6 }
  function atom() {
    const token = tokens[at++]
    if (token === '!') return Number(!atom())
    if (token === '-') return -atom()
    if (token === '+') return atom()
    if (token === '(') { const value = expression(1); insist(tokens[at++] === ')', 'Unclosed shader conditional'); return value }
    if (token === 'defined') { const bracket = tokens[at] === '('; if (bracket) at++; const name = tokens[at++]; insist(/^[A-Za-z_]\w*$/.test(name), 'Invalid defined operand'); if (bracket) insist(tokens[at++] === ')', 'Unclosed defined operand'); return Number(defines.has(name)) }
    if (/^\d+$/.test(token)) return Number(token)
    insist(typeof token === 'string' && /^[A-Za-z_]\w*$/.test(token), 'Missing shader conditional operand')
    if (!defines.has(token)) return 0
    const value = defines.get(token)
    insist(/^\d+$/.test(value), `Noninteger shader conditional macro ${token}`)
    return Number(value)
  }
  function expression(minimum) {
    let left = atom()
    while (precedence[tokens[at]] >= minimum) {
      const operator = tokens[at++], right = expression(precedence[operator] + 1)
      if (operator === '||') left = Number(Boolean(left || right))
      else if (operator === '&&') left = Number(Boolean(left && right))
      else if (operator === '==') left = Number(left === right)
      else if (operator === '!=') left = Number(left !== right)
      else if (operator === '<') left = Number(left < right)
      else if (operator === '>') left = Number(left > right)
      else if (operator === '<=') left = Number(left <= right)
      else if (operator === '>=') left = Number(left >= right)
      else if (operator === '+') left += right
      else if (operator === '-') left -= right
      else if (operator === '*') left *= right
      else if (operator === '/') { insist(right !== 0, 'Zero shader conditional divisor'); left = Math.trunc(left / right) }
      else left %= right
    }
    return left
  }
  const result = expression(1); insist(at === tokens.length && finite(result), 'Unsupported shader conditional'); return Boolean(result)
}
function activeShader(source) {
  insist(/^#version 300 es\b/.test(source), 'Actual GLSL ES300 source required')
  const text = source.replace(/\/\*[\s\S]*?\*\//g, '').replace(/\/\/[^\n]*/g, ''), defines = new Map(), stack = [], body = []
  let enabled = true
  for (const line of text.split('\n')) {
    const directive = line.match(/^\s*#\s*(\w+)\s*(.*)$/)
    if (!directive) { if (enabled) body.push(line); continue }
    const [, kind, rest] = directive
    if (kind === 'if' || kind === 'ifdef' || kind === 'ifndef') {
      const selected = enabled && (kind === 'if' ? condition(rest, defines) : kind === 'ifdef' ? defines.has(rest.trim()) : !defines.has(rest.trim()))
      stack.push({ outer: enabled, taken: selected }); enabled = selected
    } else if (kind === 'elif') { const branch = stack.at(-1); insist(branch, 'Unmatched shader elif'); enabled = branch.outer && !branch.taken && condition(rest, defines); branch.taken ||= enabled }
    else if (kind === 'else') { const branch = stack.at(-1); insist(branch, 'Unmatched shader else'); enabled = branch.outer && !branch.taken; branch.taken = true }
    else if (kind === 'endif') { const branch = stack.pop(); insist(branch, 'Unmatched shader endif'); enabled = branch.outer }
    else if (kind === 'define' && enabled) {
      const match = rest.match(/^(\w+)(\([^)]*\))?(?:\s+(.*))?$/); insist(match, 'Unsupported shader macro')
      const protectedNames = /\b(?:mvPosition|gl_Position|transformedNormal|vNormal|modelViewMatrix|projectionMatrix|normalMatrix|viewMatrix|cameraPosition|imageUv|sourceFromBacking|inverseH|grid|rect|source|local|dimensions|p|normalize|vec2|vec3|vec4|mat3|highp|mediump|lowp)\b/
      insist(!protectedNames.test(match[1]) && !protectedNames.test(match[3] ?? ''), 'Macro changes a consumed camera expression')
      if (match[1] === 'texture2D') insist(!match[2] && match[3]?.trim() === 'texture', 'Unsupported actual texture2D macro alias')
      if (match[1] === 'gl_FragColor') insist(!match[2] && /^[A-Za-z_]\w*$/.test(match[3]?.trim() ?? ''), 'Unsupported actual fragment output macro alias')
      defines.set(match[1], match[2] ? `function${match[2]}` : match[3]?.trim() ?? '1')
    }
    else if (kind === 'undef' && enabled) defines.delete(rest.trim())
    else if (enabled && !['version', 'extension', 'pragma', 'define', 'undef'].includes(kind)) throw new Error(`Unresolved shader directive ${kind}`)
  }
  insist(stack.length === 0, 'Unclosed shader conditional')
  return { text: body.join('\n').replace(/\s+/g, ' '), defines }
}
function assignments(text, name) {
  const result = [], expression = new RegExp(`\\b${name}(?:\\s*\\.[xyzwrgba]+)?(?:\\s*\\[[^\\]]+\\])?\\s*([+*/-]?=)\\s*([^;]+);`, 'g')
  for (const match of text.matchAll(expression)) result.push(`${match[1]}${match[2].replace(/\s/g, '')}`)
  return result
}
function requireHighpKernel(text) {
  insist(/\bprecision\s+highp\s+float\s*;/.test(text) && !/\bprecision\s+(?:mediump|lowp)\s+float\s*;/.test(text), 'Actual highp Float32 shader arithmetic required')
  insist(!/\b(?:lowp|mediump)\s+(?:vec[234]|mat[234]|float)\s+(?:mvPosition|transformedNormal|vNormal|modelViewMatrix|projectionMatrix|normalMatrix|source|local|p|dimensions|sourceFromBacking|grid|rect|inverseH)\b/.test(text), 'Consumed camera/presentation intermediate uses non-highp precision')
}
function compactMain(text) {
  const matches = [...text.matchAll(/\bvoid\s+main\s*\(\s*(?:void\s*)?\)\s*\{/g)]
  insist(matches.length === 1, 'One original presentation main required')
  const begin = matches[0].index + matches[0][0].length
  let end = begin, depth = 1
  for (; end < text.length && depth; end++) { if (text[end] === '{') depth++; if (text[end] === '}') depth-- }
  insist(depth === 0, 'Original presentation main is unclosed')
  return text.slice(begin, end - 1).replace(/\s/g, '')
}
function closePresentationVertex(source) {
  const { text } = activeShader(source); requireHighpKernel(text)
  insist(compactMain(text) === 'imageUv=uv;gl_Position=vec4(position.xy,0.0,1.0);', 'Unsupported actual presentation position/UV kernel')
}
function closeImageSampler(submission) {
  const value = submission.uniforms.get('image')
  insist((value instanceof Uint32Array || value instanceof Int32Array) && value.length === 1 && value[0] >= 0, 'Fresh actual image sampler unit required')
}
export function prepareNativeMirrorSubmission(binding, raster) {
  insist(!binding.resolvedImagePlaneWarp && binding.presentation === 'horizontal-mirror', 'Actual horizontal mirror is not the active presentation branch')
  const submission = raster?.mirrorSubmission
  insist(submission?.uniforms instanceof Map, 'Fresh actual horizontal-mirror program/uniform bytes required')
  closePresentationVertex(submission.vertexShader); closeImageSampler(submission)
  const { text } = activeShader(submission.fragmentShader); requireHighpKernel(text)
  const main = compactMain(text), sample = 'gl_FragColor=texture2D(image,vec2(1.0-imageUv.x,imageUv.y));'
  insist(main === sample || main === sample + 'gl_FragColor=linearToOutputTexel(gl_FragColor);', 'Unsupported actual horizontal-mirror coordinate/support kernel')
  return { kind: 'closed-original-horizontal-mirror-v1', coordinateExpression: '(1-imageUv.x,imageUv.y)', colorAppearanceClaim: false }
}
/** Closed consumed expression profile. An active define or changed assignment is
 * refused rather than inferring camera dependencies from a uniform/path name. */
export function nativeCameraShaderProfile(vertexShader, { normalsNeeded, worldNeeded, spring = false } = {}) {
  const { text, defines } = activeShader(vertexShader)
  requireHighpKernel(text)
  const mainOpen = /\bvoid\s+main\s*\(\s*(?:void\s*)?\)\s*\{/.exec(text)
  insist(mainOpen, 'Original shader main absent')
  const begin = mainOpen.index + mainOpen[0].length
  let end = begin, depth = 1
  for (; end < text.length && depth; end++) { if (text[end] === '{') depth++; if (text[end] === '}') depth-- }
  insist(depth === 0, 'Original shader main is unclosed')
  const main = text.slice(begin, end - 1)
  const nonMain = (text.slice(0, mainOpen.index) + text.slice(end)).replace(/\buniform\s+(?:(?:highp|mediump|lowp)\s+)?(?:mat[234]|vec[234]|float)\s+(?:modelViewMatrix|projectionMatrix|normalMatrix|viewMatrix|cameraPosition)\s*;/g, '')
  insist(!/\b(?:modelViewMatrix|projectionMatrix|normalMatrix|viewMatrix|cameraPosition)\b/.test(nonMain), 'Camera dependency hidden in a physical helper function')
  for (const name of ['position', 'normal', 'modelMatrix', 'modelViewMatrix', 'projectionMatrix', 'normalMatrix', 'viewMatrix', 'cameraPosition', 'springWorldTranslationLow', 'springLength', 'springRestLength']) insist(assignments(main, name).length === 0, `Original physical/camera input ${name} is shadowed or mutated`)
  if (spring) {
    insist(assignments(main, 'springNewCentre').length === 0 && assignments(main, 'springNewTangent').length === 0, 'Spring curve witnesses have an unsupported later assignment')
    insist((main.match(/\bspringCurve\s*\(\s*springNewCentre\s*,\s*springNewTangent\s*\)\s*;/g) ?? []).length === 1, 'Original spring curve call/order required')
    const normalUse = assignments(main, 'objectNormal').some(value => value.includes('springNormal'))
    insist((main.match(/\bspringNewCentre\b/g) ?? []).length === 3 && (main.match(/\bspringNewTangent\b/g) ?? []).length === 3 + Number(normalUse), 'Unknown spring witness use or indirect mutation')
  }
  // The caller may pass false only for an independently captured linked-program
  // input optimized out by the actual fragment shader. Defaults describe source.
  normalsNeeded ??= assignments(text, 'vNormal').length > 0
  worldNeeded ??= assignments(text, 'worldPosition').length > 0
  for (const name of ['USE_BATCHING', 'USE_INSTANCING', 'USE_SKINNING', 'USE_MORPHTARGETS', 'USE_MORPHNORMALS', 'USE_DISPLACEMENTMAP', 'USE_LOGDEPTHBUF', 'USE_TANGENT']) insist(!defines.has(name), `Unsupported active camera kernel ${name}`)
  insist((text.match(/\bvoid\s+main\s*\(\s*(?:void\s*)?\)\s*\{/g) ?? []).length === 1, 'One original shader main required')
  insist(exact(assignments(text, 'transformed'), [spring ? '=springPosition(position,springNewCentre,springNewTangent)' : '=vec3(position)']), 'Unsupported original local expression')
  insist(exact(assignments(text, 'mvPosition'), ['=vec4(transformed,1.0)', '=modelViewMatrix*mvPosition']), 'Unsupported consumed view expression')
  insist(exact(assignments(text, 'gl_Position'), ['=projectionMatrix*mvPosition']), 'Unsupported consumed clip expression')
  let worldExpression = 'not-consumed'
  if (worldNeeded) {
    const expected = spring ? '=vec4(modelMatrix[3].xyz+(mat3(modelMatrix)*worldPosition.xyz+springWorldTranslationLow),1.0)' : '=modelMatrix*worldPosition'
    insist(exact(assignments(text, 'worldPosition'), ['=vec4(transformed,1.0)', expected]), 'Unsupported consumed world expression/order')
    worldExpression = spring ? 'split-world-translation-low-inner-before-high' : 'model-matrix-dot'
  }
  if (normalsNeeded) {
    const object = ['=vec3(normal)']; if (spring) object.push('=springNormal(objectNormal,springNewTangent)')
    insist(exact(assignments(text, 'objectNormal'), object), 'Unsupported original object normal expression')
    const transformed = ['=objectNormal', '=normalMatrix*transformedNormal']; if (defines.has('FLIP_SIDED')) transformed.push('=-transformedNormal')
    insist(exact(assignments(text, 'transformedNormal'), transformed) && exact(assignments(text, 'vNormal'), ['=normalize(transformedNormal)']), 'Unsupported consumed normalized view normal expression')
  }
  // Camera uniforms cannot be hidden behind a renamed operation or mutation.
  const mvUses = (text.match(/\bmodelViewMatrix\b/g) ?? []).length
  insist(mvUses === 2 + (defines.has('USE_TANGENT') ? 1 : 0), 'Unknown modelViewMatrix dependency')
  insist((text.match(/\bprojectionMatrix\b/g) ?? []).length === 2, 'Unknown projectionMatrix dependency')
  if (normalsNeeded) insist((text.match(/\bnormalMatrix\b/g) ?? []).length === 2, 'Unknown normalMatrix dependency')
  let remaining = text
  for (const statement of [
    /\bvec4\s+mvPosition\s*=\s*vec4\s*\(\s*transformed\s*,\s*1\.0\s*\)\s*;/g,
    /\bmvPosition\s*=\s*modelViewMatrix\s*\*\s*mvPosition\s*;/g,
    /\bgl_Position\s*=\s*projectionMatrix\s*\*\s*mvPosition\s*;/g,
    /\bv(?:ViewPosition|ClipPosition)\s*=\s*-\s*mvPosition\s*\.xyz\s*;/g,
    /\bvFogDepth\s*=\s*-\s*mvPosition\s*\.z\s*;/g,
  ]) remaining = remaining.replace(statement, '')
  insist(!/\b(?:mvPosition|gl_Position)\b/.test(remaining), 'Unknown camera intermediate use or indirect mutation')
  let remainingLocal = remaining
  for (const statement of [
    /\bvec3\s+transformed\s*=\s*vec3\s*\(\s*position\s*\)\s*;/g,
    /\bvec3\s+transformed\s*=\s*springPosition\s*\(\s*position\s*,\s*springNewCentre\s*,\s*springNewTangent\s*\)\s*;/g,
    /\bvec4\s+worldPosition\s*=\s*vec4\s*\(\s*transformed\s*,\s*1\.0\s*\)\s*;/g,
  ]) remainingLocal = remainingLocal.replace(statement, '')
  insist(!/\btransformed\b/.test(remainingLocal), 'Unknown local intermediate use or indirect mutation')
  if (normalsNeeded) {
    let remainingNormal = text
    for (const statement of [
      /\bvec3\s+objectNormal\s*=\s*vec3\s*\(\s*normal\s*\)\s*;/g,
      /\bobjectNormal\s*=\s*springNormal\s*\(\s*objectNormal\s*,\s*springNewTangent\s*\)\s*;/g,
      /\bvec3\s+transformedNormal\s*=\s*objectNormal\s*;/g,
      /\btransformedNormal\s*=\s*normalMatrix\s*\*\s*transformedNormal\s*;/g,
      /\btransformedNormal\s*=\s*-\s*transformedNormal\s*;/g,
      /\bvNormal\s*=\s*normalize\s*\(\s*transformedNormal\s*\)\s*;/g,
      /\b(?:varying|out)\s+(?:highp\s+)?vec3\s+vNormal\s*;/g,
    ]) remainingNormal = remainingNormal.replace(statement, '')
    insist(!/\b(?:objectNormal|transformedNormal|vNormal)\b/.test(remainingNormal), 'Unknown normal intermediate use or indirect mutation')
  }
  return Object.freeze({ kind: 'closed-three-linear-camera-v1', normalsNeeded, worldNeeded, view: 'modelViewMatrix * vec4(transformed,1)', clip: 'projectionMatrix * mvPosition', normal: normalsNeeded ? 'normalize(normalMatrix * objectNormal)' : 'not-consumed', flipSided: defines.has('FLIP_SIDED'), world: worldExpression, defines: Object.fromEntries(defines), trigPolicy: 'prior-actual-all-physical-and-curve-witness-only' })
}

/** Called once while the independently adjudicated actual local buffer is live.
 * Bounds enclose unions of authentic indexed triangles, including edges/faces.
 * No producer maximum/status enters this computation. */
export function createNativeCameraDomainSummary({ localActual, indices, drawRange, localMaxComponentError, localBoundsF64, objectNormalMinOriginalLength = null, objectNormalMaxOriginalLength = null, objectNormalMaxActualLength = null, objectNormalMaxEuclideanErrorBound = null, vertexCount }) {
  insist(localActual.actual instanceof Float32Array && localActual.components === 3 && Number.isSafeInteger(vertexCount) && vertexCount > 0, 'Actual all-vertex Float32 local bytes required')
  const { actual, stride, offset } = localActual
  insist(Number.isSafeInteger(stride) && stride >= 3 && Number.isSafeInteger(offset) && offset >= 0 && offset + 3 <= stride && actual.length === vertexCount * stride, 'All-vertex local buffer layout differs')
  insist(localMaxComponentError?.length === 3 && localMaxComponentError.every(value => finite(value) && value >= 0 && value <= POSITION_LIMIT), 'Adjudicated independent component errors required')
  range(localBoundsF64)
  insist(indices instanceof Uint32Array && drawRange?.mode === 4 && drawRange.start % 3 === 0 && drawRange.count > 0 && drawRange.count % 3 === 0 && drawRange.start >= 0 && drawRange.start + drawRange.count <= indices.length, 'Authentic triangle draw domain required')
  const localBoundsActual = emptyBounds(), includeVertex = (index, bounds) => {
    insist(index < vertexCount, 'Triangle index outside all-vertex proof')
    for (let axis = 0; axis < 3; axis++) {
      const value = actual[index * stride + offset + axis]; insist(finite(value), 'Nonfinite all-vertex local byte')
      bounds[axis] = Math.min(bounds[axis], value); bounds[axis + 3] = Math.max(bounds[axis + 3], value)
    }
  }
  for (let i = 0; i < vertexCount; i++) includeVertex(i, localBoundsActual)
  const triangleCount = drawRange.count / 3, block = Math.ceil(triangleCount / MAX_DOMAINS), domains = []
  for (let first = 0; first < triangleCount; first += block) {
    const bounds = emptyBounds(), count = Math.min(block, triangleCount - first)
    for (let triangle = first; triangle < first + count; triangle++) for (let corner = 0; corner < 3; corner++) includeVertex(indices[drawRange.start + triangle * 3 + corner], bounds)
    const original = bounds.map((value, i) => i < 3 ? value - localMaxComponentError[i] : value + localMaxComponentError[i - 3])
    domains.push({ id: domains.length, firstTriangleIndex: drawRange.start / 3 + first, triangleCount: count, localBoundsActual: bounds, localBoundsF64: original })
  }
  return Object.freeze({ vertexCount, triangleCount, localBoundsActual, localBoundsF64: [...localBoundsF64], localMaxComponentError: [...localMaxComponentError], objectNormalMinOriginalLength, objectNormalMaxOriginalLength, objectNormalMaxActualLength, objectNormalMaxEuclideanErrorBound, domains })
}
function independentMatrices(expectedView, posed) {
  const binding = expectedView.binding, record = binding.camera, [width, height] = binding.resolvedImagePlaneWarp?.unwarpedViewportPixels ?? binding.rectSourcePixels.slice(2)
  const nearFar = expectedView.cameraNearFar, supplied = expectedView.cameraMatrices
  insist(nearFar?.length === 2 && nearFar.every(finite) && nearFar[0] > 0 && nearFar[1] > nearFar[0] && supplied, 'Frozen original camera near/far and independently constructed camera matrices required')
  insist(width > 0 && height > 0 && record?.positionMetres?.length === 3 && record.quaternion?.length === 4 && [...record.positionMetres, ...record.quaternion, record.verticalFovDegrees].every(finite) && norm(record.quaternion) > 0, 'Independent finite logical camera required')
  const camera = new PerspectiveCamera(record.verticalFovDegrees, width / height, nearFar[0], nearFar[1])
  camera.position.fromArray(record.positionMetres); camera.quaternion.fromArray(record.quaternion).normalize()
  if (record.principalPointViewportPixels) camera.setViewOffset(width, height, width / 2 - record.principalPointViewportPixels[0], height / 2 - record.principalPointViewportPixels[1], width, height)
  camera.updateProjectionMatrix(); camera.updateMatrixWorld(true)
  for (const [name, matrix] of [['view', camera.matrixWorldInverse], ['projection', camera.projectionMatrix], ['world', camera.matrixWorld]]) {
    const values = supplied[name]?.elements ?? supplied[name]
    insist(values?.length === 16 && values.every(finite) && exact(values, matrix.elements), `Independent original camera ${name} matrix differs from sealed logical source camera`)
  }
  const world = new Matrix4().fromArray(posed.matrixWorld), view = new Matrix4().multiplyMatrices(camera.matrixWorldInverse, world), normal = new Matrix3().getNormalMatrix(view)
  return { world: world.elements, view: view.elements, projection: camera.projectionMatrix.elements, normal: normal.elements, camera }
}
function uniform(closed, name, expected) {
  const values = closed.uniforms.get(name)
  insist(values instanceof Float32Array && values.length === expected.length && values.every(finite) && exact(values, Array.from(expected, Math.fround)), `Fresh actual uploaded ${name} bytes differ from independent original CPU/camera`)
  return values
}
function normalBounds(matrix, uploaded, domain) {
  const minimum = domain.objectNormalMinOriginalLength, maximum = domain.objectNormalMaxOriginalLength, objectError = domain.objectNormalMaxEuclideanErrorBound
  insist(finite(minimum) && minimum > 0 && finite(maximum) && maximum >= minimum && finite(objectError) && objectError >= 0, 'Prior independent object normal length/enclosure statistics required')
  const inverse = new Matrix3().fromArray(matrix).invert().elements
  const inverseNorm = norm(inverse), matrixNorm = norm(matrix)
  insist(finite(inverseNorm) && inverseNorm > 0 && new Matrix3().fromArray(matrix).determinant() !== 0, 'Singular normal matrix')
  // Verify inverse residual and turn its computed Frobenius norm into a lower
  // singular-value bound; this is not a component box normalized through zero.
  let residualSquared = 0
  for (let row = 0; row < 3; row++) for (let column = 0; column < 3; column++) {
    let value = 0, absolute = 0
    for (let k = 0; k < 3; k++) { value += matrix[row + 3 * k] * inverse[k + 3 * column]; absolute += Math.abs(matrix[row + 3 * k] * inverse[k + 3 * column]) }
    residualSquared += (Math.abs(value - Number(row === column)) + outward(absolute) * EPS64 * 16) ** 2
  }
  const residual = outward(Math.sqrt(residualSquared)); insist(residual < 1, 'Normal inverse enclosure is singular/ambiguous')
  const smin = (1 - residual) / outward(inverseNorm) * (1 - EPS64 * 32), lower = smin * minimum * (1 - EPS64 * 32)
  const conversion = norm(matrix.map((value, i) => Math.abs(value - uploaded[i]))) * maximum
  const rounding = norm(Array.from({ length: 3 }, (_, row) => dotRound([uploaded[row], uploaded[row + 3], uploaded[row + 6]], [maximum + objectError, maximum + objectError, maximum + objectError])))
  const delta = outward(conversion + norm(uploaded) * objectError + rounding)
  insist(lower > delta && lower - delta >= MIN_NORMAL, 'View normal interval has no strictly positive length lower bound')
  const upper = outward(matrixNorm * maximum + delta)
  // GLSL ES 3.00 §4.5.1/§8.5 defines normalize as x/length(x), and sqrt
  // inherits 1/inversesqrt: enclose both that permitted two-division path
  // and the common direct inverse-sqrt/product lowering. Trig has no such law.
  // https://registry.khronos.org/OpenGL/specs/es/3.0/GLSL_ES_Specification_3.00.pdf
  const squareError = dotRound([upper, upper, upper], [upper, upper, upper])
  const squaredLower = (lower - delta) ** 2 - squareError, squaredUpper = outward(upper * upper + squareError)
  insist(squaredLower > MIN_NORMAL && squaredUpper <= 3.4028234663852886e38, 'normalize length-square interval reaches zero/subnormal/overflow')
  const inverseSqrtMax = 1 / Math.sqrt(squaredLower), inverseSqrtMin = 1 / Math.sqrt(squaredUpper), inverseSqrtError = 2 * ulpAllowance(inverseSqrtMax)
  const directRound = outward(upper * (inverseSqrtError + squareError / (2 * squaredLower ** 1.5)) + ulpAllowance(upper * (inverseSqrtMax + inverseSqrtError))) * Math.sqrt(3)
  const reciprocalLower = inverseSqrtMin - inverseSqrtError
  insist(reciprocalLower >= MIN_NORMAL && inverseSqrtMax + inverseSqrtError <= 2 ** 126, 'normalize sqrt reciprocal interval is outside defined division precision')
  const lengthError = outward(squareError / (2 * Math.sqrt(squaredLower)) + inverseSqrtError / (inverseSqrtMin * reciprocalLower) + 2.5 * ulpAllowance(1 / reciprocalLower))
  const lengthLower = lower - delta - lengthError
  insist(lengthLower >= MIN_NORMAL && upper + lengthError <= 2 ** 126, 'normalize length divisor interval is outside defined division precision')
  const divisionRound = outward(upper * lengthError / ((lower - delta) * lengthLower) + 2.5 * ulpAllowance(upper / lengthLower)) * Math.sqrt(3)
  const normalizationRound = Math.max(directRound, divisionRound), normalizedError = outward(2 * delta / lower + normalizationRound)
  return { minimumOriginalLength: minimum, minimumTransformedLength: lower, inverseFrobeniusNormUpper: outward(inverseNorm), minimumSingularValueLower: smin, preNormalizeEuclideanBound: delta, maxEuclideanBound: normalizedError, maxAngularBoundRadians: normalizedError < 1 ? Math.asin(normalizedError) : Math.PI, maxLengthBound: normalizationRound, normalizationPolicy: 'glsl-es-300-inherited-length-divisions-and-direct-inverse-sqrt' }
}
function clipPlanes(enclosure, projection) {
  return Array.from({ length: 6 }, (_, plane) => {
    const axis = Math.floor(plane / 2), sign = plane % 2 ? -1 : 1
    // Preserve z/w correlation: a perspective far plane is not the independent
    // w-box minus z-box (which becomes falsely ambiguous for deep triangles).
    const coefficients = Array.from({ length: 4 }, (_, column) => projection[3 + column * 4] + sign * projection[axis + column * 4])
    const ideal = linear(coefficients, enclosure.idealView, 1, 4)[0]
    return addError(ideal, enclosure.clipError[axis] + enclosure.clipError[3])
  })
}
function ratio(numerator, denominator) {
  insist(denominator[0] > 0, 'Homogeneous interval reaches zero/negative W')
  const values = [numerator[0] / denominator[0], numerator[0] / denominator[1], numerator[1] / denominator[0], numerator[1] / denominator[1]]
  return [Math.min(...values), Math.max(...values)]
}
function projectError(idealClip, errors) {
  const w = idealClip[3], lower = w[0] - errors[3]
  insist(lower > 0, 'Homogeneous divide interval reaches zero')
  return [0, 1].map(axis => outward((errors[axis] + absmax(idealClip[axis]) / w[0] * errors[3]) / lower))
}

function componentBounds(value, count, reason) {
  const values = typeof value === 'number' ? Array(count).fill(value) : value
  insist(values?.length === count && values.every(bound => finite(bound) && bound >= 0), reason)
  return values
}
function projectedPoint(idealView, projection, viewError, clipError, evidenceKind) {
  const idealClip = linear(projection, idealView), view = idealView.map((interval, axis) => addError(interval, axis < 3 ? viewError[axis] : 0))
  const clip = idealClip.map((interval, axis) => addError(interval, clipError[axis]))
  const planes = clipPlanes({ idealView, clipError }, projection)
  const finiteTransform = [...view, ...clip, ...planes].every(interval => interval.every(finite))
  const outside = finiteTransform && (clip[3][1] <= 0 || planes.some(plane => plane[1] < 0))
  const status = outside ? 'outside' : !finiteTransform || clip[3][0] <= 0 || planes.some(plane => plane[0] <= 0) ? 'ambiguous' : 'inside'
  // XY-clipped vertices still have meaningful finite projective coordinates;
  // authentic clipped-triangle support may use them. Never project W/near/far
  // ambiguity, even when an unrelated XY plane already proves outside.
  const projectable = finiteTransform && clip[3][0] >= MIN_NORMAL && clip[3][1] <= 2 ** 126 && planes[4][0] > 0 && planes[5][0] > 0
  const result = { status, projectable, view, clip, clipPlanes: planes, ndc: null, depth: null, evidenceKind, measuredCameraTF: false, fixedPixelFirstHitClaim: false }
  if (!projectable) return result
  const ndc = [0, 1, 2].map(axis => {
    const quotient = ratio(clip[axis], clip[3])
    return addError(quotient, 2.5 * ulpAllowance(absmax(quotient)))
  })
  const rawDepth = ndc[2].map(value => value * 0.5 + 0.5), depthRound = 0.5 * ulpAllowance(absmax(ndc[2]) + 1) + ulpAllowance(absmax(rawDepth))
  // Clip membership was proved BEFORE this normalized window-depth clamp.
  // It cannot manufacture admitted depth for before-near or zero-W points.
  const depth = addError(rawDepth, depthRound)
  result.ndc = ndc; result.depth = [Math.max(0, depth[0]), Math.min(1, depth[1])]
  return result
}
/** Evaluate an original authentic world point using the SAME prior camera
 * component bounds as qualifyNativeCameraEnclosure. The actual vertex program
 * consumes modelView*local, not a rounded cameraView*worldPoint: the required
 * clip bound carries that already-adjudicated Γ47/FMA/reassociation closure.
 * NDC/depth are same-point bounds, NOT a fixed-pixel triangle-plane claim. */
export function encloseNativeCameraPoint(worldPointF64, cameraMatrices, { viewPositionBound, clipErrorBound } = {}) {
  insist(worldPointF64?.length === 3 && worldPointF64.every(finite), 'Independent authentic finite world point required')
  const matrices = {}
  for (const name of ['world', 'view', 'projection']) {
    const values = cameraMatrices?.[name]?.elements ?? cameraMatrices?.[name]
    insist(values?.length === 16 && values.every(finite), `Independent finite camera ${name} matrix required`)
    matrices[name] = values
  }
  const viewError = componentBounds(viewPositionBound, 3, 'Same fresh prior camera view bounds required'), clipError = componentBounds(clipErrorBound, 4, 'Same fresh prior camera clip bounds required')
  const idealView = linear(matrices.view, homogeneous(Array.from(worldPointF64, value => [value, value])))
  return projectedPoint(idealView, matrices.projection, viewError, clipError, 'same-fresh-analytical-camera-bound-at-original-world-point')
}
/** Producer-free standalone projection fixtures only. This does NOT qualify a
 * complete modelView-local camera program and is NEVER its production fallback.
 * It encloses F32 input/matrix conversion and every fused/unfused/reassociated
 * reduction of one projection dot, using the same conservative Γ47 machinery. */
export function encloseNativeViewClipPoint(viewPointF64, projectionF64, viewPositionBound = POSITION_LIMIT) {
  insist(viewPointF64?.length === 3 && viewPointF64.every(finite), 'Independent finite original view point required')
  const projection = projectionF64?.elements ?? projectionF64
  insist(projection?.length === 16 && projection.every(finite), 'Independent finite original projection required')
  const suppliedError = componentBounds(viewPositionBound, 3, 'Finite nonnegative standalone view-position bounds required')
  const bounds = Array.from(viewPointF64, value => [value, value]), input = homogeneous(bounds)
  const viewError = Array.from(suppliedError, (error, axis) => outward(error + ulpAllowance(Math.abs(viewPointF64[axis]) + error)))
  const uploaded = Float32Array.from(projection)
  insist(uploaded.every(finite), 'Standalone uploaded Float32 projection overflows')
  const clipError = matrixError(projection, uploaded, input, [...viewError, 0]), flat = reassociatedClipError(IDENTITY4, uploaded, bounds, viewError)
  for (let axis = 0; axis < 4; axis++) clipError[axis] = outward(clipError[axis] + flat[axis])
  return projectedPoint(input, projection, viewError, clipError, 'standalone-one-projection-dot-not-full-camera-proof')
}
/** Close the actual presentation program once per camera. The uploaded inverse
 * is compared with an independently inverted F64 authored H, not a receipt max. */
export function prepareNativeWarpSubmission(binding, raster) {
  const warp = binding.resolvedImagePlaneWarp, submission = raster?.warpSubmission
  insist(warp?.kind === 'homography' && submission?.uniforms instanceof Map, 'Fresh actual source-warp program/uniform bytes required')
  closePresentationVertex(submission.vertexShader); closeImageSampler(submission)
  const { text } = activeShader(submission.fragmentShader)
  requireHighpKernel(text)
  for (const [name, expected] of [
    ['source', ['=gl_FragCoord.xy*sourceFromBacking.xy+sourceFromBacking.zw']],
    ['local', ['=inverseH*vec3(source,1.0)']],
    ['p', ['=warped?local.xy/local.z:source-rect.xy']],
    ['dimensions', ['=warped?grid:rect.zw']],
  ]) insist(exact(assignments(text, name), expected), `Unsupported actual warp ${name} expression`)
  const main = compactMain(text)
  const prefix = 'vec2source=gl_FragCoord.xy*sourceFromBacking.xy+sourceFromBacking.zw;if(any(lessThan(source,rect.xy))||any(greaterThanEqual(source,rect.xy+rect.zw)))discard;vec3local=inverseH*vec3(source,1.0);vec2p=warped?local.xy/local.z:source-rect.xy;vec2dimensions=warped?grid:rect.zw;if(any(lessThan(p,vec2(0.0)))||any(greaterThanEqual(p,dimensions)))discard;if(mask){gl_FragColor=vec4(0.0);return;}gl_FragColor=texture2D(image,vec2(p.x/dimensions.x,1.0-p.y/dimensions.y));'
  insist(main === prefix || main === prefix + 'gl_FragColor=linearToOutputTexel(gl_FragColor);', 'Unsupported actual warp coordinate/half-open support kernel')
  const m = warp.renderToSourcePixels
  insist(m?.length === 9 && m.every(finite), 'Independent finite authored warp required')
  const matrix = new Matrix3().set(...m), determinant = matrix.determinant()
  insist(finite(determinant) && determinant !== 0, 'Singular independent source homography')
  const inverse = matrix.clone().invert().elements, inverseUploaded = uniform(submission, 'inverseH', inverse), grid = uniform(submission, 'grid', warp.unwarpedViewportPixels)
  let residualSquared = 0
  for (let row = 0; row < 3; row++) for (let column = 0; column < 3; column++) {
    let value = 0, absolute = 0
    for (let k = 0; k < 3; k++) { const product = m[row * 3 + k] * inverse[k + 3 * column]; value += product; absolute += Math.abs(product) }
    residualSquared += (Math.abs(value - Number(row === column)) + outward(absolute) * EPS64 * 16) ** 2
  }
  const residual = outward(Math.sqrt(residualSquared)); insist(residual < 1, 'Original warp inverse has ambiguous finite residual')
  const inverseF64ErrorBound = outward(norm(inverse) * residual / (1 - residual))
  const rect = uniform(submission, 'rect', binding.rectSourcePixels), cell = raster.destinationCellSourcePixels, gate = raster.sourceGateBackingPixels
  insist(cell?.length === 2 && gate?.length === 4 && [...cell, ...gate, raster.drawingBufferHeight].every(finite) && cell.every(value => value > 0), 'Independent source gate/backing mapping required')
  const sourceFromBacking = [cell[0], -cell[1], -gate[0] * cell[0], (gate[1] + gate[3]) * cell[1]]
  const sourceUploaded = uniform(submission, 'sourceFromBacking', sourceFromBacking)
  for (const [name, value] of [['warped', 1], ['mask', 0]]) {
    const uploaded = submission.uniforms.get(name)
    insist((uploaded instanceof Uint32Array || uploaded instanceof Int32Array) && uploaded.length === 1 && uploaded[0] === value, `Fresh actual warp ${name} flag differs`)
  }
  return { kind: 'closed-original-source-warp-v1', inverse, inverseUploaded, inverseF64ErrorBound, logicalGrid: warp.unwarpedViewportPixels, grid, rect, sourceFromBacking, sourceUploaded }
}
function warpArithmeticError(proof, raster, sourceBounds) {
  insist(proof, 'Independently closed actual warp arithmetic required')
  const viewport = raster.destinationViewportBackingPixels
  insist(viewport?.length === 4 && viewport.every(finite), 'Actual warp destination viewport required')
  const backingMax = [Math.max(Math.abs(viewport[0]), Math.abs(viewport[0] + viewport[2])), Math.max(Math.abs(viewport[1]), Math.abs(viewport[1] + viewport[3]))]
  const sourceError = [0, 1].map(axis => outward(Math.abs(proof.sourceUploaded[axis] - proof.sourceFromBacking[axis]) * backingMax[axis] + Math.abs(proof.sourceUploaded[axis + 2] - proof.sourceFromBacking[axis + 2]) + (backingMax[axis] >= 2 ** 23 ? ulpAllowance(backingMax[axis]) * Math.abs(proof.sourceUploaded[axis]) : 0) + dotRound([proof.sourceUploaded[axis], proof.sourceUploaded[axis + 2]], [backingMax[axis], 1])))
  const input = [...sourceBounds, [1, 1]], transformed = linear(proof.inverse, input, 3, 3), delta = matrixError(proof.inverse, proof.inverseUploaded, input, [...sourceError, 0], 3)
  const inverseConstruction = proof.inverseF64ErrorBound * norm(input.map(absmax))
  for (let axis = 0; axis < 3; axis++) delta[axis] = outward(delta[axis] + inverseConstruction)
  const lower = transformed[2][0] - delta[2]
  insist(lower > MIN_NORMAL, 'Actual warp inverse homogeneous denominator interval reaches zero/subnormal')
  const pixelError = [0, 1].map(axis => {
    const idealMagnitude = absmax(transformed[axis]) / transformed[2][0], arithmetic = (delta[axis] + idealMagnitude * delta[2]) / lower
    const division = 2.5 * ulpAllowance(outward(idealMagnitude + arithmetic))
    const logicalGrid = proof.logicalGrid[axis]
    insist(proof.grid[axis] > 0 && logicalGrid > 0, 'Warp uploaded/logical grid must be positive')
    const gridConversion = (idealMagnitude + arithmetic + division) * Math.abs(logicalGrid / proof.grid[axis] - 1)
    const samplingDivide = 2.5 * ulpAllowance(outward((idealMagnitude + arithmetic + division) / proof.grid[axis])) * logicalGrid
    const mirrorYSubtract = axis === 1 ? ulpAllowance(outward(1 + (idealMagnitude + arithmetic + division) / proof.grid[axis])) * logicalGrid : 0
    return outward(arithmetic + division + gridConversion + samplingDivide + mirrorYSubtract)
  })
  return { nativePixelComponentBounds: pixelError, inverseDenominatorLower: lower, sourceFromBackingComponentBounds: sourceError }
}
function imageMap(binding, raster, ndcBounds, ndcError) {
  const rect = binding.rectSourcePixels, warp = binding.resolvedImagePlaneWarp, mirror = !warp && binding.presentation === 'horizontal-mirror'
  insist(['native', 'horizontal-mirror'].includes(binding.presentation), 'Unsupported source presentation')
  const logical = warp?.unwarpedViewportPixels ?? rect.slice(2)
  const pixel = [[(ndcBounds[0][0] + 1) * logical[0] / 2, (ndcBounds[0][1] + 1) * logical[0] / 2], [(1 - ndcBounds[1][1]) * logical[1] / 2, (1 - ndcBounds[1][0]) * logical[1] / 2]]
  const error = [ndcError[0] * logical[0] / 2, ndcError[1] * logical[1] / 2]
  if (mirror) {
    insist(raster?.mirrorProof, 'Independently closed actual mirror program required')
    // One highp input conversion plus the explicit highp (1-u) subtraction.
    // This concerns coordinates, not any RGB or texture-filter accuracy claim.
    error[0] = outward(error[0] + 2 * ulpAllowance(1) * logical[0])
    error[1] = outward(error[1] + ulpAllowance(1) * logical[1])
  }
  if (mirror) pixel[0] = [logical[0] - pixel[0][1], logical[0] - pixel[0][0]]
  let source, sourceError = error, denominatorLower = null, jacobian = [[1, 0], [0, 1]]
  if (warp) {
    insist(warp.kind === 'homography' && warp.renderToSourcePixels?.length === 9 && warp.renderToSourcePixels.every(finite), 'Closed finite source homography required')
    const m = warp.renderToSourcePixels, expanded = pixel.map((interval, i) => addError(interval, error[i])), den = linear([m[6], m[7], m[8]], [...expanded, [1, 1]], 1, 3)[0]
    insist(den[0] > 0, 'Warp homogeneous denominator interval reaches zero/boundary')
    denominatorLower = den[0]
    source = [0, 1].map(row => ratio(linear([m[row * 3], m[row * 3 + 1], m[row * 3 + 2]], [...expanded, [1, 1]], 1, 3)[0], den))
    const arithmetic = warpArithmeticError(raster?.warpProof, raster, source)
    const fullDomain = expanded.map((interval, axis) => addError(interval, arithmetic.nativePixelComponentBounds[axis]))
    const fullDen = linear([m[6], m[7], m[8]], [...fullDomain, [1, 1]], 1, 3)[0]
    insist(fullDen[0] > 0, 'Warp arithmetic-expanded homogeneous domain reaches zero/boundary')
    denominatorLower = fullDen[0]
    jacobian = [0, 1].map(row => [0, 1].map(axis => {
      const other = 1 - axis, a = m[row * 3 + axis], b = m[row * 3 + other], c = m[row * 3 + 2], g = m[6 + axis], h = m[6 + other], i = m[8]
      const coefficient = a * h - b * g, constant = a * i - c * g, interval = fullDomain[other]
      return outward(Math.max(Math.abs(coefficient * interval[0] + constant), Math.abs(coefficient * interval[1] + constant)) / fullDen[0] ** 2)
    }))
    sourceError = jacobian.map(row => outward(row[0] * (error[0] + arithmetic.nativePixelComponentBounds[0]) + row[1] * (error[1] + arithmetic.nativePixelComponentBounds[1])))
  } else source = [[rect[0] + pixel[0][0], rect[0] + pixel[0][1]], [rect[1] + pixel[1][0], rect[1] + pixel[1][1]]]
  // Raster viewport/scissor and source gate are independently sealed by the
  // consumer from the actual capture. Round-to-backing discrepancies are a
  // deterministic map error, not a guessed half-pixel producer allowance.
  let backingDiscrepancy = 0
  if (raster) {
    const { nativeViewportBackingPixels: native, destinationViewportBackingPixels: destination, destinationScissorBackingPixels: scissor, destinationCellSourcePixels: cell, sourceGateBackingPixels: gate, drawingBufferHeight } = raster
    for (const [name, values, size] of [['native viewport', native, 4], ['destination viewport', destination, 4], ['scissor', scissor, 4], ['source cell', cell, 2], ['source gate', gate, 4]]) insist(values?.length === size && values.every(finite), `Actual ${name} mapping absent/nonfinite`)
    insist(native[2] > 0 && native[3] > 0 && destination[2] > 0 && destination[3] > 0 && cell.every(value => value > 0) && finite(drawingBufferHeight), 'Actual backing viewport mapping is degenerate')
    const originX = (destination[0] - gate[0]) * cell[0], originY = (drawingBufferHeight - destination[1] - destination[3] - (drawingBufferHeight - gate[1] - gate[3])) * cell[1]
    if (!warp) backingDiscrepancy = norm([Math.max(Math.abs(originX - rect[0]), Math.abs(originX + destination[2] * cell[0] - rect[0] - rect[2])), Math.max(Math.abs(originY - rect[1]), Math.abs(originY + destination[3] * cell[1] - rect[1] - rect[3]))])
    else {
      insist(native[2] === Math.ceil(logical[0]) && native[3] === Math.ceil(logical[1]), 'Actual native warp backing viewport differs from sealed logical grid')
      // UVs use the logical grid divided by itself; the backing ceil changes
      // texel sampling support, not the continuous native-to-source map.
      backingDiscrepancy = 0
    }
    const scissorSource = [[(scissor[0] - gate[0]) * cell[0], (scissor[0] + scissor[2] - gate[0]) * cell[0]], [(gate[1] + gate[3] - scissor[1] - scissor[3]) * cell[1], (gate[1] + gate[3] - scissor[1]) * cell[1]]]
    return { source: source.map((interval, axis) => addError(interval, sourceError[axis] + backingDiscrepancy)), sourceError, maxPixelBound: outward(norm(sourceError) + backingDiscrepancy), backingDiscrepancy, warpDenominatorLower: denominatorLower, warpJacobianAbsUpper: jacobian, scissorSource }
  }
  return { source: source.map((interval, axis) => addError(interval, sourceError[axis])), sourceError, maxPixelBound: outward(norm(sourceError)), backingDiscrepancy, warpDenominatorLower: denominatorLower, warpJacobianAbsUpper: jacobian, scissorSource: null }
}
function intersects(a, b) { return a[0][0] <= b[0][1] && a[0][1] >= b[0][0] && a[1][0] <= b[1][1] && a[1][1] >= b[1][0] }
function footprintStatus(binding, mapped, supports) {
  const rect = binding.rectSourcePixels, own = [[rect[0], rect[0] + rect[2]], [rect[1], rect[1] + rect[3]]]
  if (!intersects(mapped.source, own) || mapped.scissorSource && !intersects(mapped.source, mapped.scissorSource)) return 'outside-source-support'
  // Only required, independently selected first-surface/rim footprints are
  // tested against ordered masks. A box intersecting a later ROI is not proof
  // that the physical primitive is absent or fully covered.
  if (!supports?.length) return 'potentially-visible-triangle-support'
  const layout = binding.sourceLayout, index = layout?.findIndex(entry => entry.viewId === binding.viewId)
  insist(index >= 0, 'Sealed ordered source layout lacks this view')
  for (const support of supports) {
    const p = support.sourceFootprintPixels
    insist(p?.length === 4 && p.every(finite) && p[0] <= p[2] && p[1] <= p[3], 'Independent source first-surface footprint required')
    const footprint = [[p[0] - mapped.maxPixelBound, p[2] + mapped.maxPixelBound], [p[1] - mapped.maxPixelBound, p[3] + mapped.maxPixelBound]]
    if (footprint.some((interval, axis) => interval[0] < own[axis][0] || interval[1] >= own[axis][1]) || mapped.scissorSource && footprint.some((interval, axis) => interval[0] < mapped.scissorSource[axis][0] || interval[1] >= mapped.scissorSource[axis][1])) return 'ambiguous-required-source-scissor-footprint'
    for (const later of layout.slice(index + 1)) {
      const a = binding.composite, b = later.composite, sameGroup = a?.mode === 'crossfade' && b?.mode === 'crossfade' && a.groupId === b.groupId, sameImage = sameGroup && a.imageLayerId === b.imageLayerId
      if (sameGroup && !sameImage || b?.mode === 'crossfade' && b.opacity < 1 && !sameImage) continue
      const r = later.rectSourcePixels, mask = [[r[0], r[0] + r[2]], [r[1], r[1] + r[3]]]
      if (intersects(footprint, mask)) return 'ambiguous-required-ordered-mask-footprint'
    }
  }
  return 'required-first-surface-footprints-enclosed'
}

/** The coreProof/cameraDomain are exclusively Node-adjudicated state. `closed`
 * is the current camera's independently byte-closed original GL submission. */
export function qualifyNativeCameraEnclosure({ coreProof, submitted, closed, staticEntry, posed, expectedView }) {
  const gaps = [], failures = [], binding = expectedView.binding, domain = coreProof.cameraDomain
  try {
    insist(coreProof.gaps?.length === 0 && coreProof.failures?.length === 0 && domain && Number.isSafeInteger(domain.vertexCount) && domain.vertexCount > 0 && coreProof.vertexCount === domain.vertexCount, 'Complete independently adjudicated all-vertex physical state required')
    insist(typeof closed.key === 'string' && /^[0-9a-f]{64}$/.test(closed.key) && coreProof.geometryStateSHA256 === closed.key && coreProof.originalProgramSHA256 === closed.programSHA256 && typeof closed.programSHA256 === 'string' && /^[0-9a-f]{64}$/.test(closed.programSHA256), 'Cached actual physical proof belongs to a different submitted geometry/program tuple')
    for (const name of ['local', ...(closed.normalsNeeded ? ['objectNormal'] : [])]) insist(coreProof.fields[name]?.vertexCount === domain.vertexCount && coreProof.fields[name].comparedComponentCount === domain.vertexCount * 3 && coreProof.fields[name].nonfiniteCount === 0 && coreProof.fields[name].outsideCount === 0, `Prior all-vertex ${name} proof is incomplete/failed`)
    insist(coreProof.fields.local.maxAbsoluteError <= POSITION_LIMIT && coreProof.fields.local.maxEuclideanError <= POSITION_LIMIT * Math.sqrt(3), 'Original independent physical position policy failed')
    if (closed.worldNeeded) insist(coreProof.fields.world?.vertexCount === domain.vertexCount && coreProof.fields.world.comparedComponentCount === domain.vertexCount * 3 && coreProof.fields.world.nonfiniteCount === 0 && coreProof.fields.world.outsideCount === 0 && coreProof.fields.world.maxAbsoluteError <= POSITION_LIMIT, 'Original independent all-world position policy failed')
    const profile = nativeCameraShaderProfile(closed.vertexShader, { normalsNeeded: closed.normalsNeeded, worldNeeded: closed.worldNeeded, spring: Boolean(staticEntry.springOracle) })
    const matrices = independentMatrices(expectedView, posed)
    for (const name of ['world', 'view', 'projection']) insist(exact(closed[name], matrices[name]), `Fresh actual submitted ${name} F64 matrix differs from independently solved original camera/input`)
    const view = uniform(closed, 'modelViewMatrix', matrices.view), projection = uniform(closed, 'projectionMatrix', matrices.projection)
    if (closed.worldNeeded) uniform(closed, 'modelMatrix', matrices.world)
    if (profile.world === 'split-world-translation-low-inner-before-high') uniform(closed, 'springWorldTranslationLow', [12, 13, 14].map(i => matrices.world[i] - Math.fround(matrices.world[i])))
    const normal = closed.normalsNeeded ? normalBounds(matrices.normal, uniform(closed, 'normalMatrix', matrices.normal), domain) : null
    const rasterGeometry = expectedView.rasterGeometry ? { ...expectedView.rasterGeometry } : null
    if (binding.resolvedImagePlaneWarp && rasterGeometry) rasterGeometry.warpProof = prepareNativeWarpSubmission(binding, rasterGeometry)
    if (!binding.resolvedImagePlaneWarp && binding.presentation === 'horizontal-mirror' && rasterGeometry) rasterGeometry.mirrorProof = prepareNativeMirrorSubmission(binding, rasterGeometry)
    const localBounds = range(domain.localBoundsF64), localError = domain.localMaxComponentError
    insist(localError.length === 3 && localError.every(value => finite(value) && value >= 0 && value <= POSITION_LIMIT), 'Node-derived all-local component error bounds absent')
    const construct = bounds => {
      const input = homogeneous(bounds), errors = [...localError, 0], idealView = linear(matrices.view, input), viewError = matrixError(matrices.view, view, input, errors), idealClip = linear(matrices.projection, idealView)
      const clipError = matrixError(matrices.projection, projection, idealView, viewError), flat = reassociatedClipError(view, projection, bounds, localError)
      for (let i = 0; i < 4; i++) clipError[i] = outward(clipError[i] + flat[i])
      return { idealView, viewError, idealClip, clipError, actualClip: idealClip.map((interval, i) => addError(interval, clipError[i])) }
    }
    const global = construct(localBounds), reports = []
    insist(domain.domains?.length > 0 && domain.domains.reduce((sum, cell) => sum + cell.triangleCount, 0) === submitted.drawRange.count / 3, 'Complete authentic triangle support domains required')
    let maxPixelBound = 0, ambiguousCount = 0, outsideCount = 0, potentiallyVisibleTriangleCount = 0
    for (const cell of domain.domains) {
      const enclosure = construct(range(cell.localBoundsF64)), planes = clipPlanes(enclosure, matrices.projection)
      if (planes.some(plane => plane[1] < 0)) { outsideCount++; reports.push({ id: cell.id, triangleCount: cell.triangleCount, status: 'proved-outside-homogeneous-clip-volume' }); continue }
      potentiallyVisibleTriangleCount += cell.triangleCount
      // A union-of-triangles support interval crossing near/far cannot select
      // the original/actual clipped correspondence, much less a nearest hit.
      if (enclosure.actualClip[3][0] <= 0 || planes[4][0] <= 0 || planes[5][0] <= 0) { ambiguousCount++; reports.push({ id: cell.id, triangleCount: cell.triangleCount, status: 'ambiguous-required-w-near-far-clipped-domain' }); continue }
      try {
        const supports = expectedView.cameraSupports?.filter(support => support.path === submitted.path && (support.domainId === cell.id || support.triangleIndex >= cell.firstTriangleIndex && support.triangleIndex < cell.firstTriangleIndex + cell.triangleCount))
        const frustumCrossing = planes.slice(0, 4).some(plane => plane[0] <= 0)
        if (frustumCrossing && !supports?.length) { ambiguousCount++; reports.push({ id: cell.id, triangleCount: cell.triangleCount, status: 'ambiguous-required-frustum-clipped-domain' }); continue }
        const ndc = [0, 1].map(i => ratio(enclosure.idealClip[i], enclosure.idealClip[3])), error = projectError(enclosure.idealClip, enclosure.clipError), mapping = imageMap(binding, rasterGeometry, ndc, error)
        const footprint = footprintStatus(binding, mapping, supports)
        const status = frustumCrossing && footprint === 'required-first-surface-footprints-enclosed' ? 'required-interior-first-surface-support-enclosed-frustum-clipped-primitive' : footprint
        if (status.startsWith('ambiguous-')) ambiguousCount++
        if (status !== 'outside-source-support') maxPixelBound = Math.max(maxPixelBound, mapping.maxPixelBound)
        reports.push({ id: cell.id, triangleCount: cell.triangleCount, status, homogeneousWLower: enclosure.actualClip[3][0], nearClipLower: planes[4][0], farClipLower: planes[5][0], ...mapping })
      } catch (error) { ambiguousCount++; reports.push({ id: cell.id, triangleCount: cell.triangleCount, status: 'ambiguous-required-projective-warp-domain', reason: error.message }) }
    }
    if (!expectedView.rasterGeometry) gaps.push(`${submitted.path}/${submitted.family}: independently sealed actual backing viewport/scissor/source-gate map absent`)
    if (ambiguousCount) gaps.push(`${submitted.path}/${submitted.family}: ${ambiguousCount} potentially visible authentic triangle support domains have unresolved clip/warp/mask boundaries`)
    if (!(maxPixelBound < 0.5) || !(maxPixelBound < 38.4)) failures.push(`${submitted.path}/${submitted.family}: finite source camera pixel bound exceeds strict source policy`)
    const summary = (components, error) => ({ vertexCount: domain.vertexCount, comparedComponentCount: domain.vertexCount * components, nonfiniteCount: 0, outsideCount: 0, maxAbsoluteError: Math.max(...error), maxEuclideanError: norm(error), maxAbsoluteErrorBound: Math.max(...error), maxEuclideanErrorBound: norm(error), evidenceKind: 'fresh-finite-analytical-enclosure-not-measured-camera-tf' })
    const fields = { view: summary(3, global.viewError.slice(0, 3)), clip: summary(4, global.clipError) }
    if (normal) fields.viewNormal = { ...summary(3, [normal.maxEuclideanBound, 0, 0]), maxAngularErrorRadians: normal.maxAngularBoundRadians, maxLengthError: normal.maxLengthBound, maxEnclosureEuclideanBound: normal.maxEuclideanBound }
    const selectedView = new Float64Array(4), selectedClip = new Float64Array(4), selectedNormal = new Float64Array(3)
    const selectedIntervals = { view: Array.from({ length: 3 }, () => [0, 0]), clip: Array.from({ length: 4 }, () => [0, 0]) }
    if (normal) selectedIntervals.viewNormal = Array.from({ length: 3 }, () => [0, 0])
    const selectedViewError = global.viewError.map(outward), selectedClipError = global.clipError.map(outward), selectedNormalError = normal ? outward(normal.maxEuclideanBound) : 0
    // Mutable workspace: inspect immediately, or provide your own interval out.
    // No actual selected camera value enters these preconstructed error bounds.
    const selectedVertexEnclosure = (originalLocal, originalObjectNormal = null, out = selectedIntervals) => {
      insist(originalLocal?.length === 3 && originalLocal.every(finite), 'Independent original selected local vertex required')
      for (let axis = 0; axis < 3; axis++) insist(originalLocal[axis] >= localBounds[axis][0] && originalLocal[axis] <= localBounds[axis][1], 'Selected original vertex lies outside independently adjudicated physical domain')
      transformPointInto(matrices.view, originalLocal, selectedView, 4, 1)
      transformPointInto(matrices.projection, selectedView, selectedClip)
      for (let axis = 0; axis < 3; axis++) { out.view[axis][0] = selectedView[axis] - selectedViewError[axis]; out.view[axis][1] = selectedView[axis] + selectedViewError[axis] }
      for (let axis = 0; axis < 4; axis++) { out.clip[axis][0] = selectedClip[axis] - selectedClipError[axis]; out.clip[axis][1] = selectedClip[axis] + selectedClipError[axis] }
      if (normal) {
        insist(originalObjectNormal?.length === 3 && originalObjectNormal.every(finite), 'Independent original selected object normal required')
        const originalLength = Math.hypot(originalObjectNormal[0], originalObjectNormal[1], originalObjectNormal[2])
        insist(originalLength >= domain.objectNormalMinOriginalLength * (1 - EPS64 * 32) && originalLength <= domain.objectNormalMaxOriginalLength * (1 + EPS64 * 32), 'Selected original normal lies outside independently adjudicated physical lengths')
        transformPointInto(matrices.normal, originalObjectNormal, selectedNormal, 3)
        const length = Math.hypot(selectedNormal[0], selectedNormal[1], selectedNormal[2]); insist(length > 0, 'Original selected normal is zero')
        for (let axis = 0; axis < 3; axis++) {
          const expected = (profile.flipSided ? -selectedNormal[axis] : selectedNormal[axis]) / length
          out.viewNormal[axis][0] = expected - selectedNormalError; out.viewNormal[axis][1] = expected + selectedNormalError
        }
      }
      return out
    }
    return {
      gaps, failures, fields, vertexCount: domain.vertexCount, selectedVertexEnclosure,
      cameraProof: {
        policy: 'finite-fresh-linear-enclosure-after-all-physical-bytes', profile,
        independentPositionLimitMetres: POSITION_LIMIT,
        sourcePixelLimits: { strictComponent: 38.4, strictCombined: 0.5 },
        domainStatus: ambiguousCount ? 'unmeasured-required-projective-domain' : potentiallyVisibleTriangleCount ? 'finite-potentially-visible-triangle-domains-enclosed' : 'proved-outside-all-authentic-triangle-domains',
        triangleDomainCount: reports.length, provedOutsideDomainCount: outsideCount,
        ambiguousDomainCount: ambiguousCount, potentiallyVisibleTriangleCount,
        maxPixelBound: gaps.length ? null : maxPixelBound,
        maxPixelBoundOfEnclosedDomains: maxPixelBound, normal, domains: reports,
        componentErrorBounds: { view: global.viewError.slice(0, 3), clip: [...global.clipError] },
        presentationProfile: rasterGeometry?.warpProof?.kind ?? rasterGeometry?.mirrorProof?.kind ?? 'native-direct',
        pixelBoundMeaning: 'finite-projected-geometry-camera-and-presentation-coordinate-bound; actual-first-surface-pixels-checked-separately',
        measuredCameraTF: false, sourceRGBAAppearanceClaim: false, continuousOrSweptClaim: false,
      },
    }
  } catch (error) { failures.push(`${submitted.path}/${submitted.family}: ${error.message}`); return { gaps, failures, fields: {}, vertexCount: 0, cameraProof: { policy: 'finite-fresh-linear-enclosure-after-all-physical-bytes', domainStatus: 'refused', measuredCameraTF: false, sourceRGBAAppearanceClaim: false, continuousOrSweptClaim: false } } }
}

/** Validate every submitted selected camera component against an enclosure
 * already constructed without looking at any selected camera output. */
export function validateNativeCameraSamples(proof, samples) {
  insist(typeof proof.selectedVertexEnclosure === 'function', 'Previously constructed camera enclosure required')
  const fields = {}, failures = [], names = proof.fields.viewNormal ? ['view', 'clip', 'viewNormal'] : ['view', 'clip'], shapeErrors = {}
  for (const name of names) {
    fields[name] = { vertexCount: 0, comparedComponentCount: 0, nonfiniteCount: 0, outsideCount: 0, maxAbsoluteError: 0 }
    shapeErrors[name] = `Selected actual ${name} camera field shape differs`
  }
  let vertexCount = 0, invalidPositiveWCount = 0
  const indexed = typeof samples.read === 'function' && Number.isSafeInteger(samples.vertexCount)
  if (indexed) insist(samples.vertexCount === proof.vertexCount, 'Selected camera TF must cover every actual vertex of the selected primitive')
  const iterator = indexed ? null : samples[Symbol.iterator]()
  while (true) {
    let sample
    if (indexed) { if (vertexCount === samples.vertexCount) break; sample = samples.read(vertexCount) }
    else { const next = iterator.next(); if (next.done) break; sample = next.value }
    const expected = proof.selectedVertexEnclosure(sample.originalLocal, sample.originalObjectNormal)
    vertexCount++
    for (const name of names) {
      const intervals = expected[name], actual = sample[name], summary = fields[name]
      insist(actual?.length === intervals.length, shapeErrors[name])
      summary.vertexCount++
      for (let i = 0; i < intervals.length; i++) {
        summary.comparedComponentCount++
        if (!finite(actual[i])) { summary.nonfiniteCount++; continue }
        if (actual[i] < intervals[i][0] || actual[i] > intervals[i][1]) summary.outsideCount++
        summary.maxAbsoluteError = Math.max(summary.maxAbsoluteError, Math.abs(actual[i] - (intervals[i][0] + intervals[i][1]) / 2))
      }
    }
    if (expected.clip[3][0] > 0 && !(sample.clip[3] > 0)) invalidPositiveWCount++
  }
  insist(vertexCount === proof.vertexCount, 'Selected camera TF must cover every actual vertex of the selected primitive')
  if (invalidPositiveWCount) failures.push(`${invalidPositiveWCount} selected vertices have zero/negative/nonfinite homogeneous W on the prior positive branch`)
  for (const name of names) if (fields[name].nonfiniteCount || fields[name].outsideCount) failures.push(`Selected actual ${name} is outside prior fresh analytical camera enclosure`)
  return { failures, gaps: [], fields, vertexCount, invalidPositiveWCount, evidenceKind: 'selected-measured-camera-tf-checked-against-prior-enclosure', allComponentsInside: failures.length === 0 }
}
