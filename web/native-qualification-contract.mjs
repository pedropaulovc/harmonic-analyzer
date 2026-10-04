// Shared byte/state vocabulary only. Numerical authority stays in Node.
export function canonicalJson(value) {
  if (Array.isArray(value)) return `[${value.map(canonicalJson).join(',')}]`
  if (value && typeof value === 'object') return `{${Object.keys(value).sort().map(key => `${JSON.stringify(key)}:${canonicalJson(value[key])}`).join(',')}}`
  if (typeof value === 'number' && !Number.isFinite(value)) throw new TypeError('Nonfinite canonical number')
  const result = JSON.stringify(value)
  if (result === undefined) throw new TypeError('Undefined canonical value')
  return result
}
export function serializeNativeBinding(binding) {
  if (binding === null) return null
  return { ...binding, pattern: { source: binding.pattern.source, flags: binding.pattern.flags } }
}
/** Exact original writeCamera/setViewOffset/read-snapshot convention. This
 * canonicalizes an independently supplied camera, never a captured expectation. */
export function nativeExpectedCameraSnapshot(camera, logicalDimensions) {
  if (!camera || camera.quaternion?.length !== 4 || !camera.quaternion.every(Number.isFinite) || logicalDimensions?.length !== 2 || !logicalDimensions.every(value => Number.isFinite(value) && value > 0)) throw new TypeError('Finite original camera/logical viewport required')
  const [x, y, z, w] = camera.quaternion, length = Math.sqrt(x * x + y * y + z * z + w * w), inverse = length === 0 ? 0 : 1 / length
  const out = { ...camera, quaternion: length === 0 ? [0, 0, 0, 1] : [x * inverse, y * inverse, z * inverse, w * inverse] }
  const principal = camera.principalPointViewportPixels
  if (principal === undefined) delete out.principalPointViewportPixels
  else {
    if (principal.length !== 2 || !principal.every(Number.isFinite)) throw new TypeError('Finite original logical principal point required')
    const halfWidth = logicalDimensions[0] / 2, halfHeight = logicalDimensions[1] / 2
    out.principalPointViewportPixels = [halfWidth - (halfWidth - principal[0]), halfHeight - (halfHeight - principal[1])]
  }
  return out
}
export const nativeProgramSource = (vertexShader, fragmentShader) => `${vertexShader}\n---native-fragment---\n${fragmentShader}`
export function nativeSubmissionStateDescriptor(submitted) {
  const { geometryStateSHA256, submissionStateSHA256, ...state } = submitted
  return state
}
const vertexUniformRootCache = new Map()
function vertexUniformRoots(source) {
  if (typeof source !== 'string') return null
  if (vertexUniformRootCache.has(source)) return vertexUniformRootCache.get(source)
  let roots = null
  if (!source.includes('##') && !/^\s*#\s*define[^\n]*\buniform\b/m.test(source)) {
    const text = source.replace(/\/\*[\s\S]*?\*\//g, '').replace(/\/\/[^\n]*/g, ''), macros = new Set([...text.matchAll(/^\s*#\s*define\s+([A-Za-z_]\w*)/gm)].map(match => match[1]))
    const declarations = [...text.matchAll(/\buniform\s+(?:(?:highp|mediump|lowp)\s+)?([A-Za-z_]\w*)\s+([^;{}]+);/g)]
    if (declarations.length === (text.match(/\buniform\b/g)?.length ?? 0)) {
      roots = new Set()
      for (const declaration of declarations) {
        if (macros.has(declaration[1])) { roots = null; break }
        for (const name of declaration[2].split(',')) {
          const match = name.match(/^\s*([A-Za-z_]\w*)(?:\s*\[[^\]]+\])?\s*$/)
          if (!match || macros.has(match[1])) { roots = null; break }
          roots.add(match[1])
        }
        if (roots === null) break
      }
    }
  }
  vertexUniformRootCache.set(source, roots)
  return roots
}
/** Independently parse the actual vertex source once. Undeclared fragment-only
 * roots cannot affect geometry; unknown/macro/block profiles retain all. */
export function nativeGeometryUniforms(uniforms, vertexShaderText) {
  const roots = vertexUniformRoots(vertexShaderText)
  return uniforms.filter(uniform => !['modelViewMatrix', 'projectionMatrix', 'normalMatrix', 'viewMatrix', 'cameraPosition'].includes(uniform.name) && (!roots || roots.has(uniform.name.split(/[.[]/, 1)[0])))
}
export function nativeGeometryStateDescriptor(submitted, vertexShaderText) {
  return { path: submitted.path, family: submitted.family, vertexShader: submitted.vertexShader, fragmentShader: submitted.fragmentShader, attributes: submitted.attributes, canonicalSubmittedIndices: submitted.canonicalSubmittedIndices, drawRange: submitted.drawRange, activeUniforms: nativeGeometryUniforms(submitted.activeUniforms, vertexShaderText), matrixWorldF64: submitted.matrixWorldF64 }
}
export const nativeTFVaryingNames = Object.freeze({ local: 'baselineLocalPosition', world: 'baselineGPUWorldPosition', view: 'baselineViewPosition', clip: 'baselineClipPosition', objectNormal: 'baselineObjectNormal', viewNormal: 'nativeViewNormal', springCentre: 'nativeSpringCentre', springTangent: 'nativeSpringTangent' })
const expressions = { local: 'transformed', world: 'worldPosition.xyz', view: 'mvPosition.xyz', clip: 'gl_Position', objectNormal: 'objectNormal', viewNormal: 'vNormal', springCentre: 'springNewCentre', springTangent: 'springNewTangent' }
function mainClosingOffset(source) {
  const matches = [...source.matchAll(/\bvoid\s+main\s*\(\s*(?:void\s*)?\)\s*\{/g)]
  if (matches.length !== 1) throw new Error('One original main required')
  let depth = 1, comment = null
  for (let i = matches[0].index + matches[0][0].length; i < source.length; i++) {
    const ch = source[i], next = source[i + 1]
    if (comment === 'line') { if (ch === '\n') comment = null; continue }
    if (comment === 'block') { if (ch === '*' && next === '/') { comment = null; i++ } continue }
    if (ch === '/' && next === '/') { comment = 'line'; i++; continue }
    if (ch === '/' && next === '*') { comment = 'block'; i++; continue }
    if (ch === '{') depth++
    if (ch === '}' && --depth === 0) return i
  }
  throw new Error('Original main closing brace absent')
}
export function instrumentNativeVertexShader(source, fields) {
  if (!/^#version 300 es\b/.test(source)) throw new Error('Actual GLSL ES300 required')
  const seen = new Set()
  for (const field of fields) {
    if (!expressions[field.name] || seen.has(field.name) || field.components !== (field.name === 'clip' ? 4 : 3)) throw new Error('Unsupported/duplicate TF field')
    seen.add(field.name)
  }
  const close = mainClosingOffset(source)
  const epilogue = '\n' + fields.map(field => `  ${nativeTFVaryingNames[field.name]} = ${expressions[field.name]};`).join('\n') + '\n'
  const withOutputs = source.slice(0, close) + epilogue + source.slice(close), versionEnd = withOutputs.indexOf('\n') + 1
  const declarations = fields.map(field => `out highp vec${field.components} ${nativeTFVaryingNames[field.name]};`).join('\n') + '\n'
  return withOutputs.slice(0, versionEnd) + declarations + withOutputs.slice(versionEnd)
}
