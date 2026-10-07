import * as THREE from 'three'
import type { NativeObject } from './native-primitive-snapshot'

export interface NativeTargetShaderFeedbackRequest {
  renderer: THREE.WebGLRenderer
  camera: THREE.PerspectiveCamera
  scene: THREE.Scene
  object: NativeObject
  targetPrimitiveId: string
  /** Actual decoded geometry vertex indices, not positions in the index buffer. */
  targetVertexIndices: readonly number[]
  /** Pre-lease Float64 xyz rows in exactly the same order as targetVertexIndices. */
  cpuWorldPositions: Float64Array
  requestedTriangleIndexOffset: number
  controlSubmissionRevision: number
  associatedColourDraw: { drawRevision: number; contextRevision: number; viewId: string; timeSeconds: number | null }
  /** Recheck the Scene-owned lease and original colour association, never an old GPU frame. */
  beforeSample: () => void
}

export interface NativeTargetControlledSubmission {
  method: 'current-native-rasterizer-discard-target-control-submission'
  revision: number
  rendererFrameBefore: number
  targetRendererFrame: number | null
  rendererFrameAfter: number
  submittedAtPerformanceMs: number
  /** CPU return of the supported render call, not a whole-scene GPU fence. */
  completed: boolean
  completion: 'renderer-render-returned-not-full-scene-gpu-fence'
  targetNativeCallbackCount: number
  transformFeedbackSampled: boolean
  rasterizerDiscard: true
  colourRasterized: false
  associatedColourDraw: NativeTargetShaderFeedbackRequest['associatedColourDraw']
  camera: { matrixWorld: number[]; matrixWorldInverse: number[]; projectionMatrix: number[] }
  targetNativeSubmission: null | {
    objectUuid: string
    geometryUuid: string
    materialUuid: string
    group: null | { start: number; count: number; materialIndex: number | undefined }
  }
  cleanup: { status: 'restored' | 'failed'; failures: string[] }
}

export interface NativeTargetShaderSeal {
  encoding: 'exact-source-text'
  threeRevision: string
  programId: number
  programCacheKey: string
  materialUuid: string
  materialVersion: number
  originalVertexShaderSource: string
  originalFragmentShaderSource: string
  derivedVertexShaderSource: string
  derivedFragmentShaderSource: string
  feedbackProgramRelation: 'original-vertex-source-plus-clip-feedback-with-original-fragment-rasterizer-discard'
  declarationsInsertionOffset: number
  assignmentsInsertionOffset: number
  feedbackVaryings: readonly [string]
  comparisonLaw: 'matrix-only-on-decoded-float32-position'
}
export interface NativeTargetUniformSeal {
  encoding: 'exact-reflected-uniform-bytes'
  byteOrder: 'little-endian' | 'big-endian'
  /** Complete enumeration of original reflected metadata, not a claim that all values were readable. */
  reflectionComplete: boolean
  /** Separate from metadata enumeration: unreadable inactive entries have no guessed value. */
  valuesComplete: boolean
  matrixChecks: { name: string; expectedFloat32: number[]; observedFloat32: number[] | null; matches: boolean }[]
  uniforms: {
    name: string
    type: number
    size: number
    sampler: boolean | null
    feedbackUse: 'not-evaluated' | 'copied' | 'inactive-nonexecuted' | 'partial'
    readability: 'not-evaluated' | 'readable' | 'missing-location' | 'partial'
    elements: {
      name: string
      storage: 'Float32' | 'Int32' | 'Uint32'
      rawHex: string | null
      readability: 'readable' | 'missing-location'
      derivedLocation: 'not-evaluated' | 'active' | 'inactive'
      feedbackUse: 'not-evaluated' | 'copied' | 'inactive-nonexecuted'
    }[]
  }[]
}
export interface NativeTargetAttributeSeal {
  encoding: 'exact-selected-decoded-attribute-bytes'
  byteOrder: 'little-endian' | 'big-endian'
  targetPrimitiveId: string
  objectUuid: string
  geometryUuid: string
  targetVertexIndices: number[]
  coordinateClassRawHex: string
  attributes: {
    name: string
    originalLocation: number
    shaderType: number
    feedbackLocation: number | null
    feedbackUse: 'not-evaluated' | 'copied' | 'inactive'
    storage: string
    glType: number
    itemSize: number
    normalized: boolean
    integerPointer: boolean
    interleaved: boolean
    sourceStrideBytes: number
    sourceOffsetBytes: number
    sourceVersion: number
    packedStrideBytes: number
    selectedRawHex: string
  }[]
}
export interface NativeTargetDerivedDiagnostic {
  method: 'float64-inverse-projection-and-camera-world-from-observed-native-clip'
  precision: 'cpu-float64-derived-world-not-observed-gpu-world'
  cpuClipReferenceMethod: 'current-float64-view-and-projection-on-prelease-world'
  viewMatrixFloat64: number[]
  projectionMatrixFloat64: number[]
  projectionMatrixInverseFloat64: number[]
  cameraMatrixWorldFloat64: number[]
  qualification: 'inverse-projection-conditioning-may-amplify-error-not-global-bound'
}
export interface NativeTargetShaderFeedbackResult {
  status: 'measured' | 'unavailable'
  reason: string
  observedClipPositions: Float32Array | null
  cpuClipPositions: Float64Array | null
  derivedWorldPositions: Float64Array | null
  /** Euclidean norm in four-dimensional homogeneous clip coordinates; NOT metres. */
  maxObservedClipDelta: number | null
  perVertexClipDelta: Float64Array | null
  /** Float64 reconstruction diagnostic, NOT an observed GPU world-position delta. */
  maxDerivedWorldDeltaMetres: number | null
  perVertexDerivedWorldDeltaMetres: Float64Array | null
  derivedDiagnostic: NativeTargetDerivedDiagnostic | null
  independentNumericBoundMetres: null
  sourceProof: false
  sourceAcceptance: false
  qualification: 'observed-native-clip-arithmetic-derived-float64-world-not-gpu-world'
  eligibility: 'unresolved'
  shaderSeal: NativeTargetShaderSeal | null
  currentUniformSeal: NativeTargetUniformSeal | null
  attributeSeal: NativeTargetAttributeSeal | null
  controlledSubmission: NativeTargetControlledSubmission | null
}

const CLIP_OUTPUT = 'ompTargetFeedbackClipPosition'
const MAX_TARGET_VERTICES = 4096
const BYTE_ORDER = new Uint8Array(new Uint32Array([1]).buffer)[0] === 1 ? 'little-endian' : 'big-endian'
type UniformData = Float32Array | Int32Array | Uint32Array
interface UniformShape {
  storage: 'Float32' | 'Int32' | 'Uint32'
  width: number
  matrix?: true
  sampler?: true
}
interface ReflectedUniform {
  name: string
  type: number
  size: number
  elements: { name: string; value: UniformData | null }[]
}
interface PreparedAttribute {
  name: string
  packed: Uint8Array
  glType: number
  itemSize: number
  normalized: boolean
  integerPointer: boolean
}
interface CurrentProgram {
  id: number
  cacheKey: string
  program: WebGLProgram
  vertexShader: WebGLShader
  fragmentShader: WebGLShader
}
interface SavedGlState {
  program: WebGLProgram | null
  vertexArray: WebGLVertexArrayObject | null
  arrayBuffer: WebGLBuffer | null
  transformFeedback: WebGLTransformFeedback | null
  transformFeedbackBuffer: WebGLBuffer | null
  activeTexture: number
  rasterizerDiscard: boolean
}

function unavailable(reason: string): NativeTargetShaderFeedbackResult {
  return {
    status: 'unavailable', reason,
    observedClipPositions: null, cpuClipPositions: null, derivedWorldPositions: null,
    maxObservedClipDelta: null, perVertexClipDelta: null,
    maxDerivedWorldDeltaMetres: null, perVertexDerivedWorldDeltaMetres: null, derivedDiagnostic: null,
    independentNumericBoundMetres: null, sourceProof: false, sourceAcceptance: false,
    qualification: 'observed-native-clip-arithmetic-derived-float64-world-not-gpu-world', eligibility: 'unresolved',
    shaderSeal: null, currentUniformSeal: null, attributeSeal: null,
    controlledSubmission: null,
  }
}
function requireCondition(condition: unknown, reason: string): asserts condition {
  if (!condition) throw new Error(reason)
}
function rawHex(bytes: Uint8Array): string {
  let hex = ''
  for (const byte of bytes) hex += byte.toString(16).padStart(2, '0')
  return hex
}
function maskComments(source: string): string {
  return source.replace(/\/\*[\s\S]*?\*\/|\/\/[^\r\n]*/g, text => text.replace(/[^\r\n]/g, ' '))
}

/** Validate stock matrix-only scope; never use these chunks to construct a shader. */
function deriveFeedbackSource(source: string): {
  source: string; declarationsOffset: number; assignmentsOffset: number
} {
  const masked = maskComments(source)
  requireCondition(/^\s*#version\s+300\s+es\b/.test(masked), 'Only the original GLSL ES 3.00 shader is supported')
  requireCondition(!/\bompTargetFeedbackClipPosition\b/.test(masked), 'Feedback output name collides with the original shader')
  requireCondition(!/^\s*#\s*(?:define|undef)\s+(?:transformed|position|modelMatrix|modelViewMatrix|viewMatrix|projectionMatrix|mvPosition|worldPosition|gl_Position|main|vec3|vec4|out)\b/m.test(masked), 'Shader aliases make the current transformation law ambiguous')
  requireCondition(!/^\s*#\s*define\s+USE_(?:MORPHTARGETS|SKINNING|DISPLACEMENTMAP|INSTANCING\w*|BATCHING\w*)\b/m.test(masked), 'Active morph, skin, displacement, instancing or batching is unsupported')
  const mains = [...masked.matchAll(/\bvoid\s+main\s*\(\s*(?:void\s*)?\)\s*\{/g)]
  requireCondition(mains.length === 1, 'Original vertex shader must have exactly one inspectable main scope')
  const main = mains[0]!
  const open = main.index + main[0].length - 1
  let depth = 1
  let close = open + 1
  for (; close < masked.length && depth !== 0; close++) {
    if (masked[close] === '{') depth++
    else if (masked[close] === '}') depth--
  }
  requireCondition(depth === 0, 'Original vertex shader main scope is unterminated')
  close--
  requireCondition(!/\breturn\b/.test(masked.slice(open + 1, close)), 'Early shader return would bypass feedback assignments')
  let law = source.slice(open + 1, close)
  // Exact dormant stock chunks are excluded only after their enabling defines were refused.
  // This is a source-law check, not a private CPU/GPU deformation implementation.
  for (const chunk of [THREE.ShaderChunk.morphtarget_vertex, THREE.ShaderChunk.skinning_vertex, THREE.ShaderChunk.displacementmap_vertex]) {
    law = law.replace(chunk, '')
  }
  law = maskComments(law)
  const declaration = /\bvec3\s+transformed\s*=\s*vec3\s*\(\s*position\s*\)\s*;/g
  const declarations = [...law.matchAll(declaration)]
  requireCondition(declarations.length === 1, 'Compiled shader does not expose the stock matrix-only transformed position')
  const declarationIndex = declarations[0]!.index
  let scopeDepth = 0
  for (let i = 0; i < declarationIndex; i++) {
    if (law[i] === '{') scopeDepth++
    else if (law[i] === '}') scopeDepth--
  }
  requireCondition(scopeDepth === 0, 'transformed is not in the final main scope')
  law = law.replace(declaration, '')
  law = law.replace(/\bvec4\s+(?:mvPosition|worldPosition)\s*=\s*vec4\s*\(\s*transformed\s*,\s*1\.0\s*\)\s*;/g, '')
  requireCondition(!/\btransformed\b/.test(law), 'Additional transformed uses make the compiled shader law unsupported')
  requireCondition(/\bmvPosition\s*=\s*modelViewMatrix\s*\*\s*mvPosition\s*;/.test(law)
    && /\bgl_Position\s*=\s*projectionMatrix\s*\*\s*mvPosition\s*;/.test(law), 'Original compiled shader does not expose the stock projection law')
  const declarationsText = `out highp vec4 ${CLIP_OUTPUT};\n`
  const assignmentsText = `\n${CLIP_OUTPUT} = gl_Position;\n`
  return {
    source: source.slice(0, main.index) + declarationsText + source.slice(main.index, close) + assignmentsText + source.slice(close),
    declarationsOffset: main.index, assignmentsOffset: close,
  }
}

function uniformShape(gl: WebGL2RenderingContext, type: number): UniformShape {
  switch (type) {
    case gl.FLOAT: return { storage: 'Float32', width: 1 }
    case gl.FLOAT_VEC2: return { storage: 'Float32', width: 2 }
    case gl.FLOAT_VEC3: return { storage: 'Float32', width: 3 }
    case gl.FLOAT_VEC4: return { storage: 'Float32', width: 4 }
    case gl.FLOAT_MAT2: return { storage: 'Float32', width: 4, matrix: true }
    case gl.FLOAT_MAT3: return { storage: 'Float32', width: 9, matrix: true }
    case gl.FLOAT_MAT4: return { storage: 'Float32', width: 16, matrix: true }
    case gl.FLOAT_MAT2x3: case gl.FLOAT_MAT3x2: return { storage: 'Float32', width: 6, matrix: true }
    case gl.FLOAT_MAT2x4: case gl.FLOAT_MAT4x2: return { storage: 'Float32', width: 8, matrix: true }
    case gl.FLOAT_MAT3x4: case gl.FLOAT_MAT4x3: return { storage: 'Float32', width: 12, matrix: true }
    case gl.INT: case gl.BOOL: return { storage: 'Int32', width: 1 }
    case gl.INT_VEC2: case gl.BOOL_VEC2: return { storage: 'Int32', width: 2 }
    case gl.INT_VEC3: case gl.BOOL_VEC3: return { storage: 'Int32', width: 3 }
    case gl.INT_VEC4: case gl.BOOL_VEC4: return { storage: 'Int32', width: 4 }
    case gl.UNSIGNED_INT: return { storage: 'Uint32', width: 1 }
    case gl.UNSIGNED_INT_VEC2: return { storage: 'Uint32', width: 2 }
    case gl.UNSIGNED_INT_VEC3: return { storage: 'Uint32', width: 3 }
    case gl.UNSIGNED_INT_VEC4: return { storage: 'Uint32', width: 4 }
    case gl.SAMPLER_2D: case gl.SAMPLER_3D: case gl.SAMPLER_CUBE:
    case gl.SAMPLER_2D_SHADOW: case gl.SAMPLER_2D_ARRAY: case gl.SAMPLER_2D_ARRAY_SHADOW: case gl.SAMPLER_CUBE_SHADOW:
    case gl.INT_SAMPLER_2D: case gl.INT_SAMPLER_3D: case gl.INT_SAMPLER_CUBE: case gl.INT_SAMPLER_2D_ARRAY:
    case gl.UNSIGNED_INT_SAMPLER_2D: case gl.UNSIGNED_INT_SAMPLER_3D: case gl.UNSIGNED_INT_SAMPLER_CUBE: case gl.UNSIGNED_INT_SAMPLER_2D_ARRAY:
    case 0x8d66: // SAMPLER_EXTERNAL_OES, if reflected by the original renderer.
      return { storage: 'Int32', width: 1, sampler: true }
    default: throw new Error(`Unsupported reflected uniform type 0x${type.toString(16)}; no uniform fallback is performed`)
  }
}
function reflectUniforms(gl: WebGL2RenderingContext, program: WebGLProgram, seal: NativeTargetUniformSeal): ReflectedUniform[] {
  const uniforms: ReflectedUniform[] = []
  const count = gl.getProgramParameter(program, gl.ACTIVE_UNIFORMS) as number
  const infos: WebGLActiveInfo[] = []
  for (let i = 0; i < count; i++) {
    const info = gl.getActiveUniform(program, i)
    requireCondition(info && info.size > 0, 'Original program uniform reflection is unavailable')
    infos.push(info)
    seal.uniforms.push({ name: info.name, type: info.type, size: info.size, sampler: null, feedbackUse: 'not-evaluated', readability: 'not-evaluated', elements: [] })
  }
  seal.reflectionComplete = true
  let valuesComplete = true
  requireCondition(gl.getProgramParameter(program, gl.ACTIVE_UNIFORM_BLOCKS) === 0, 'Uniform blocks cannot be copied by this helper')
  for (let i = 0; i < infos.length; i++) {
    const info = infos[i]!
    const shape = uniformShape(gl, info.type)
    seal.uniforms[i]!.sampler = shape.sampler === true
    requireCondition(info.size === 1 || (info.name.match(/\[0\]/g)?.length === 1), `Ambiguous uniform array reflection: ${info.name}`)
    const elements: ReflectedUniform['elements'] = []
    for (let j = 0; j < info.size; j++) {
      const name = info.size === 1 ? info.name : info.name.replace('[0]', `[${j}]`)
      const location = gl.getUniformLocation(program, name)
      if (location === null) {
        elements.push({ name, value: null })
        seal.uniforms[i]!.elements.push({
          name, storage: shape.storage, rawHex: null, readability: 'missing-location',
          derivedLocation: 'not-evaluated', feedbackUse: 'not-evaluated',
        })
        valuesComplete = false
        continue
      }
      const observed: unknown = gl.getUniform(program, location)
      const values = typeof observed === 'number' || typeof observed === 'boolean' ? [Number(observed)] : observed
      requireCondition(values instanceof Float32Array || values instanceof Int32Array || values instanceof Uint32Array || Array.isArray(values), `Unsupported actual uniform value: ${name}`)
      requireCondition(values.length === shape.width, `Unexpected reflected uniform width: ${name}`)
      let value: UniformData
      if (shape.storage === 'Float32') value = values instanceof Float32Array ? values : new Float32Array(values)
      else if (shape.storage === 'Int32') value = values instanceof Int32Array ? values : new Int32Array(values)
      else value = values instanceof Uint32Array ? values : new Uint32Array(values)
      for (const component of value) requireCondition(Number.isFinite(component), `Nonfinite actual uniform: ${name}`)
      elements.push({ name, value })
      seal.uniforms[i]!.elements.push({
        name, storage: shape.storage,
        rawHex: rawHex(new Uint8Array(value.buffer, value.byteOffset, value.byteLength)),
        readability: 'readable', derivedLocation: 'not-evaluated', feedbackUse: 'not-evaluated',
      })
    }
    uniforms.push({ name: info.name, type: info.type, size: info.size, elements })
    const readableCount = elements.reduce((count, element) => count + Number(element.value !== null), 0)
    seal.uniforms[i]!.readability = readableCount === elements.length ? 'readable' : readableCount === 0 ? 'missing-location' : 'partial'
  }
  seal.valuesComplete = valuesComplete
  return uniforms
}
function requireMatrix(uniforms: readonly ReflectedUniform[], name: string, expected: readonly number[]): void {
  const uniform = uniforms.find(value => value.name === name)
  requireCondition(uniform?.type === 0x8b5c && uniform.size === 1 && uniform.elements.length === 1, `Required original active ${name} uniform is absent or unsupported; optimized-out values are not reconstructed`)
  const actual = uniform.elements[0]!.value
  requireCondition(actual instanceof Float32Array && actual.length === 16, `Required original ${name} uniform has no readable actual Float32 value; no value is reconstructed`)
  for (let i = 0; i < 16; i++) {
    requireCondition(Number.isFinite(expected[i]) && Object.is(actual[i], Math.fround(expected[i]!)), `Compiled material uniform state belongs to another native draw or camera: ${name}[${i}] observed ${actual[i]}, expected Float32 ${Math.fround(expected[i]!)}`)
  }
}
function uploadUniform(gl: WebGL2RenderingContext, type: number, location: WebGLUniformLocation, value: UniformData): void {
  switch (type) {
    case gl.FLOAT: gl.uniform1fv(location, value as Float32Array); break
    case gl.FLOAT_VEC2: gl.uniform2fv(location, value as Float32Array); break
    case gl.FLOAT_VEC3: gl.uniform3fv(location, value as Float32Array); break
    case gl.FLOAT_VEC4: gl.uniform4fv(location, value as Float32Array); break
    case gl.FLOAT_MAT2: gl.uniformMatrix2fv(location, false, value as Float32Array); break
    case gl.FLOAT_MAT3: gl.uniformMatrix3fv(location, false, value as Float32Array); break
    case gl.FLOAT_MAT4: gl.uniformMatrix4fv(location, false, value as Float32Array); break
    case gl.FLOAT_MAT2x3: gl.uniformMatrix2x3fv(location, false, value as Float32Array); break
    case gl.FLOAT_MAT3x2: gl.uniformMatrix3x2fv(location, false, value as Float32Array); break
    case gl.FLOAT_MAT2x4: gl.uniformMatrix2x4fv(location, false, value as Float32Array); break
    case gl.FLOAT_MAT4x2: gl.uniformMatrix4x2fv(location, false, value as Float32Array); break
    case gl.FLOAT_MAT3x4: gl.uniformMatrix3x4fv(location, false, value as Float32Array); break
    case gl.FLOAT_MAT4x3: gl.uniformMatrix4x3fv(location, false, value as Float32Array); break
    case gl.SAMPLER_2D: case gl.SAMPLER_3D: case gl.SAMPLER_CUBE:
    case gl.SAMPLER_2D_SHADOW: case gl.SAMPLER_2D_ARRAY: case gl.SAMPLER_2D_ARRAY_SHADOW: case gl.SAMPLER_CUBE_SHADOW:
    case gl.INT_SAMPLER_2D: case gl.INT_SAMPLER_3D: case gl.INT_SAMPLER_CUBE: case gl.INT_SAMPLER_2D_ARRAY:
    case gl.UNSIGNED_INT_SAMPLER_2D: case gl.UNSIGNED_INT_SAMPLER_3D: case gl.UNSIGNED_INT_SAMPLER_CUBE: case gl.UNSIGNED_INT_SAMPLER_2D_ARRAY:
    case 0x8d66: // Actual sealed SAMPLER_EXTERNAL_OES unit; no texture binding is changed.
    case gl.INT: case gl.BOOL: gl.uniform1iv(location, value as Int32Array); break
    case gl.INT_VEC2: case gl.BOOL_VEC2: gl.uniform2iv(location, value as Int32Array); break
    case gl.INT_VEC3: case gl.BOOL_VEC3: gl.uniform3iv(location, value as Int32Array); break
    case gl.INT_VEC4: case gl.BOOL_VEC4: gl.uniform4iv(location, value as Int32Array); break
    case gl.UNSIGNED_INT: gl.uniform1uiv(location, value as Uint32Array); break
    case gl.UNSIGNED_INT_VEC2: gl.uniform2uiv(location, value as Uint32Array); break
    case gl.UNSIGNED_INT_VEC3: gl.uniform3uiv(location, value as Uint32Array); break
    case gl.UNSIGNED_INT_VEC4: gl.uniform4uiv(location, value as Uint32Array); break
    default: throw new Error('Unsupported uniform upload; no omitted-uniform fallback is performed')
  }
}
/** Copy only actual usable derived slots; preserve unreadable and optimized-out metadata. */
function copyFeedbackUniforms(gl: WebGL2RenderingContext, program: WebGLProgram, uniforms: readonly ReflectedUniform[], seal: NativeTargetUniformSeal): void {
  requireCondition(gl.getProgramParameter(program, gl.ACTIVE_UNIFORM_BLOCKS) === 0, 'Active feedback program uniform blocks cannot be copied')
  const count = gl.getProgramParameter(program, gl.ACTIVE_UNIFORMS) as number
  const infos: WebGLActiveInfo[] = []
  for (let i = 0; i < count; i++) {
    const info = gl.getActiveUniform(program, i)
    requireCondition(info && info.size > 0, 'Actual feedback program uniform reflection is unavailable')
    requireCondition(uniforms.some(uniform => uniform.name === info.name), `Feedback program requires an unsealed original uniform: ${info.name}`)
    infos.push(info)
  }
  for (let i = 0; i < uniforms.length; i++) {
    const uniform = uniforms[i]!
    const uniformSeal = seal.uniforms[i]!
    const info = infos.find(value => value.name === uniform.name)
    let copied = 0
    let inactive = 0
    for (let j = 0; j < uniform.elements.length; j++) {
      const element = uniform.elements[j]!
      const elementSeal = uniformSeal.elements[j]!
      const location = gl.getUniformLocation(program, element.name)
      elementSeal.derivedLocation = location === null ? 'inactive' : 'active'
      if (location === null) {
        elementSeal.feedbackUse = 'inactive-nonexecuted'
        inactive++
      } else {
        requireCondition(info && info.type === uniform.type && info.size === uniform.size, `Feedback program requires an unsealed original uniform type or size: ${element.name}`)
        requireCondition(element.value !== null, `Feedback program requires an unreadable original uniform: ${element.name}; no value is substituted`)
        uploadUniform(gl, uniform.type, location, element.value)
        elementSeal.feedbackUse = 'copied'
        copied++
      }
      uniformSeal.feedbackUse = copied === uniform.elements.length ? 'copied'
        : inactive === uniform.elements.length ? 'inactive-nonexecuted' : 'partial'
    }
  }
  for (const name of ['modelViewMatrix', 'projectionMatrix']) {
    const uniform = seal.uniforms.find(value => value.name === name)
    requireCondition(uniform?.type === gl.FLOAT_MAT4 && uniform.size === 1
      && uniform.elements.length === 1 && uniform.elements[0]!.derivedLocation === 'active'
      && uniform.elements[0]!.feedbackUse === 'copied', `Required derived ${name} uniform is absent, inactive or unreadable; no value is reconstructed`)
  }
}
function attributeType(gl: WebGL2RenderingContext, attribute: THREE.BufferAttribute | THREE.InterleavedBufferAttribute): number {
  const array = attribute.array
  if (array instanceof Float32Array) return gl.FLOAT
  if (array instanceof Uint16Array) return 'isFloat16BufferAttribute' in attribute && attribute.isFloat16BufferAttribute ? gl.HALF_FLOAT : gl.UNSIGNED_SHORT
  if (array instanceof Int16Array) return gl.SHORT
  if (array instanceof Uint32Array) return gl.UNSIGNED_INT
  if (array instanceof Int32Array) return gl.INT
  if (array instanceof Int8Array) return gl.BYTE
  if (array instanceof Uint8Array || array instanceof Uint8ClampedArray) return gl.UNSIGNED_BYTE
  throw new Error(`Unsupported actual attribute storage: ${array.constructor.name}`)
}
function prepareAttributes(gl: WebGL2RenderingContext, program: WebGLProgram, request: NativeTargetShaderFeedbackRequest): {
  attributes: PreparedAttribute[]; seal: NativeTargetAttributeSeal
} {
  const geometry = request.object.geometry
  const position = geometry.getAttribute('position')
  requireCondition(position && position.array instanceof Float32Array && position.itemSize === 3 && !position.normalized, 'Target requires actual decoded, nonnormalized Float32 xyz POSITION')
  const interleavedPosition = position instanceof THREE.InterleavedBufferAttribute
  const positionStride = interleavedPosition ? position.data.stride : position.itemSize
  const positionOffset = interleavedPosition ? position.offset : 0
  const positionBits = new Uint32Array(position.array.buffer, position.array.byteOffset, position.array.length)
  const first = request.targetVertexIndices[0]!
  const firstOffset = first * positionStride + positionOffset
  const seen = new Set<number>()
  for (const index of request.targetVertexIndices) {
    requireCondition(Number.isSafeInteger(index) && index >= 0 && index < position.count && !seen.has(index), 'Target indices must be unique actual decoded vertex indices within POSITION')
    seen.add(index)
    const offset = index * positionStride + positionOffset
    for (let axis = 0; axis < 3; axis++) {
      requireCondition(Number.isFinite(position.array[offset + axis]) && positionBits[offset + axis] === positionBits[firstOffset + axis], 'Target rows are not one exact finite Float32 coordinate class')
    }
  }
  const seal: NativeTargetAttributeSeal = {
    encoding: 'exact-selected-decoded-attribute-bytes', byteOrder: BYTE_ORDER,
    targetPrimitiveId: request.targetPrimitiveId, objectUuid: request.object.uuid, geometryUuid: geometry.uuid,
    targetVertexIndices: Array.from(request.targetVertexIndices),
    coordinateClassRawHex: rawHex(new Uint8Array(position.array.buffer, position.array.byteOffset + firstOffset * 4, 12)),
    attributes: [],
  }
  const attributes: PreparedAttribute[] = []
  const count = gl.getProgramParameter(program, gl.ACTIVE_ATTRIBUTES) as number
  for (let i = 0; i < count; i++) {
    const info = gl.getActiveAttrib(program, i)
    requireCondition(info && info.size === 1, 'Array vertex attributes are unsupported')
    const shape = uniformShape(gl, info.type)
    requireCondition(!shape.matrix && shape.width <= 4, `Matrix vertex attribute is unsupported: ${info.name}`)
    const location = gl.getAttribLocation(program, info.name)
    requireCondition(location >= 0, `Missing original active attribute location: ${info.name}`)
    const attribute = geometry.getAttribute(info.name)
    requireCondition(attribute instanceof THREE.BufferAttribute || attribute instanceof THREE.InterleavedBufferAttribute, `Actual active attribute is missing or GPU-only: ${info.name}; no default attribute is substituted`)
    const interleaved = attribute instanceof THREE.InterleavedBufferAttribute
    requireCondition(!('isInstancedBufferAttribute' in attribute && attribute.isInstancedBufferAttribute)
      && !(interleaved && 'isInstancedInterleavedBuffer' in attribute.data && attribute.data.isInstancedInterleavedBuffer), `Instanced attribute is unsupported: ${info.name}`)
    requireCondition(Number.isInteger(attribute.itemSize) && attribute.itemSize >= 1 && attribute.itemSize <= 4, `Unsupported actual attribute dimensions: ${info.name}`)
    const glType = attributeType(gl, attribute)
    const integerPointer = glType === gl.INT || glType === gl.UNSIGNED_INT || ('gpuType' in attribute && attribute.gpuType === THREE.IntType)
    requireCondition(integerPointer === (shape.storage !== 'Float32'), `Actual integer/float attribute interpretation is ambiguous: ${info.name}`)
    const array = attribute.array
    const bytesPerElement = array.BYTES_PER_ELEMENT
    const stride = interleaved ? attribute.data.stride : attribute.itemSize
    const offset = interleaved ? attribute.offset : 0
    requireCondition(Number.isSafeInteger(stride) && stride >= attribute.itemSize && Number.isSafeInteger(offset) && offset >= 0 && offset + attribute.itemSize <= stride, `Invalid actual attribute layout: ${info.name}`)
    const packedStride = attribute.itemSize * bytesPerElement
    const packed = new Uint8Array(request.targetVertexIndices.length * packedStride)
    const raw = new Uint8Array(array.buffer, array.byteOffset, array.byteLength)
    for (let row = 0; row < request.targetVertexIndices.length; row++) {
      const index = request.targetVertexIndices[row]!
      const start = (index * stride + offset) * bytesPerElement
      requireCondition(index < attribute.count && start + packedStride <= raw.length, `Selected vertex exceeds actual attribute storage: ${info.name}`)
      for (let byte = 0; byte < packedStride; byte++) packed[row * packedStride + byte] = raw[start + byte]!
    }
    attributes.push({ name: info.name, packed, glType, itemSize: attribute.itemSize, normalized: attribute.normalized, integerPointer })
    seal.attributes.push({
      name: info.name, originalLocation: location, shaderType: info.type, storage: array.constructor.name, glType,
      feedbackLocation: null, feedbackUse: 'not-evaluated',
      itemSize: attribute.itemSize, normalized: attribute.normalized, integerPointer, interleaved,
      sourceStrideBytes: stride * bytesPerElement, sourceOffsetBytes: offset * bytesPerElement,
      sourceVersion: interleaved ? attribute.data.version : attribute.version,
      packedStrideBytes: packedStride, selectedRawHex: rawHex(packed),
    })
  }
  requireCondition(attributes.some(attribute => attribute.name === 'position'), 'Original compiled program has no active actual POSITION attribute')
  return { attributes, seal }
}
/** Camera-only Float64 arithmetic on pre-lease world rows and real GPU clip readback. */
function deriveClipDiagnostics(clip: Float32Array, referenceWorld: Float64Array, matrices: NativeTargetDerivedDiagnostic): {
  cpuClipPositions: Float64Array
  derivedWorldPositions: Float64Array
  perVertexClipDelta: Float64Array
  maxObservedClipDelta: number
  perVertexDerivedWorldDeltaMetres: Float64Array
  maxDerivedWorldDeltaMetres: number
} {
  requireCondition(clip.length % 4 === 0 && referenceWorld.length === clip.length / 4 * 3, 'GPU clip/pre-lease world row count differs')
  const count = clip.length / 4
  const cpuClipPositions = new Float64Array(clip.length)
  const derivedWorldPositions = new Float64Array(referenceWorld.length)
  const perVertexClipDelta = new Float64Array(count)
  const perVertexDerivedWorldDeltaMetres = new Float64Array(count)
  let maxObservedClipDelta = 0
  let maxDerivedWorldDeltaMetres = 0
  const view = matrices.viewMatrixFloat64
  const projection = matrices.projectionMatrixFloat64
  const inverseProjection = matrices.projectionMatrixInverseFloat64
  const cameraWorld = matrices.cameraMatrixWorldFloat64
  for (const matrix of [view, projection, inverseProjection, cameraWorld]) {
    requireCondition(matrix.length === 16 && matrix.every(Number.isFinite), 'Current camera diagnostic matrix must contain sixteen finite Float64 values')
  }
  for (let row = 0; row < count; row++) {
    const xyz = row * 3
    const xyzw = row * 4
    const x = referenceWorld[xyz]!
    const y = referenceWorld[xyz + 1]!
    const z = referenceWorld[xyz + 2]!
    const viewX = view[0]! * x + view[4]! * y + view[8]! * z + view[12]!
    const viewY = view[1]! * x + view[5]! * y + view[9]! * z + view[13]!
    const viewZ = view[2]! * x + view[6]! * y + view[10]! * z + view[14]!
    const viewW = view[3]! * x + view[7]! * y + view[11]! * z + view[15]!
    cpuClipPositions[xyzw] = projection[0]! * viewX + projection[4]! * viewY + projection[8]! * viewZ + projection[12]! * viewW
    cpuClipPositions[xyzw + 1] = projection[1]! * viewX + projection[5]! * viewY + projection[9]! * viewZ + projection[13]! * viewW
    cpuClipPositions[xyzw + 2] = projection[2]! * viewX + projection[6]! * viewY + projection[10]! * viewZ + projection[14]! * viewW
    cpuClipPositions[xyzw + 3] = projection[3]! * viewX + projection[7]! * viewY + projection[11]! * viewZ + projection[15]! * viewW
    const clipX = clip[xyzw]!
    const clipY = clip[xyzw + 1]!
    const clipZ = clip[xyzw + 2]!
    const clipW = clip[xyzw + 3]!
    const inverseX = inverseProjection[0]! * clipX + inverseProjection[4]! * clipY + inverseProjection[8]! * clipZ + inverseProjection[12]! * clipW
    const inverseY = inverseProjection[1]! * clipX + inverseProjection[5]! * clipY + inverseProjection[9]! * clipZ + inverseProjection[13]! * clipW
    const inverseZ = inverseProjection[2]! * clipX + inverseProjection[6]! * clipY + inverseProjection[10]! * clipZ + inverseProjection[14]! * clipW
    const inverseW = inverseProjection[3]! * clipX + inverseProjection[7]! * clipY + inverseProjection[11]! * clipZ + inverseProjection[15]! * clipW
    const worldW = cameraWorld[3]! * inverseX + cameraWorld[7]! * inverseY + cameraWorld[11]! * inverseZ + cameraWorld[15]! * inverseW
    requireCondition(Number.isFinite(worldW) && worldW !== 0, 'Observed clip cannot be reconstructed through the current camera matrices: homogeneous world divisor is zero or nonfinite')
    derivedWorldPositions[xyz] = (cameraWorld[0]! * inverseX + cameraWorld[4]! * inverseY + cameraWorld[8]! * inverseZ + cameraWorld[12]! * inverseW) / worldW
    derivedWorldPositions[xyz + 1] = (cameraWorld[1]! * inverseX + cameraWorld[5]! * inverseY + cameraWorld[9]! * inverseZ + cameraWorld[13]! * inverseW) / worldW
    derivedWorldPositions[xyz + 2] = (cameraWorld[2]! * inverseX + cameraWorld[6]! * inverseY + cameraWorld[10]! * inverseZ + cameraWorld[14]! * inverseW) / worldW
    const clipDelta = Math.hypot(clipX - cpuClipPositions[xyzw]!, clipY - cpuClipPositions[xyzw + 1]!, clipZ - cpuClipPositions[xyzw + 2]!, clipW - cpuClipPositions[xyzw + 3]!)
    const worldDelta = Math.hypot(derivedWorldPositions[xyz]! - x, derivedWorldPositions[xyz + 1]! - y, derivedWorldPositions[xyz + 2]! - z)
    requireCondition(Number.isFinite(clipDelta) && Number.isFinite(worldDelta), 'Nonfinite clip or Float64-derived world diagnostic')
    perVertexClipDelta[row] = clipDelta
    perVertexDerivedWorldDeltaMetres[row] = worldDelta
    maxObservedClipDelta = Math.max(maxObservedClipDelta, clipDelta)
    maxDerivedWorldDeltaMetres = Math.max(maxDerivedWorldDeltaMetres, worldDelta)
  }
  return { cpuClipPositions, derivedWorldPositions, perVertexClipDelta, maxObservedClipDelta, perVertexDerivedWorldDeltaMetres, maxDerivedWorldDeltaMetres }
}
function requireNoGlError(gl: WebGL2RenderingContext, stage: string): void {
  requireCondition(!gl.isContextLost(), `WebGL context was lost during ${stage}`)
  const error = gl.getError()
  requireCondition(error === gl.NO_ERROR, `WebGL error 0x${error.toString(16)} during ${stage}`)
}

/**
 * Synchronous, bounded arithmetic observation on the current ORIGINAL native program.
 * Scene must validate native colour submission, model/input/source-assembly freshness,
 * the complete selected coordinate class, and its Float64 reference BEFORE the lease.
 * No native CPU geometry/world evaluation occurs; only camera transforms of the
 * supplied PRE-lease Float64 world rows and the real GPU clip output are evaluated.
 *
 * Three r180 exposes currentProgram in renderer.properties; its shader objects remain
 * attached after deleteShader, so getShaderSource retrieves the actual compiled text.
 * The vertex copy adds exactly one vec4 output declaration and a final gl_Position copy.
 * The exact original fragment source is linked unchanged; rasterizer discard prevents
 * its execution while preserving the original vertex/fragment varying dependencies.
 * Full original uniform metadata and all readable values (including sampler units)
 * are sealed. Missing locations are explicitly unreadable with null bytes; they
 * are never filled from a material or CPU matrix. Only actual usable derived slots
 * with matching reflection and exact readable original values are copied, including
 * sealed sampler units without changing native texture bindings. Optimized-out slots
 * are labelled per element, never falsely described as copied. Required matrix slots,
 * custom hooks, deformation and ambiguous programs remain strict and unavailable.
 *
 * Only a real POINTS transform-feedback draw plus finite GPU Float32 clip readback
 * produces measured. World positions are separately derived using actual Float64
 * inverse-projection/camera-world matrices and homogeneous division, never observed
 * GPU world coordinates. Ill-conditioning can amplify the derived-world diagnostic.
 * Clip deltas are homogeneous four-dimensional norms, NOT metres. Neither diagnostic
 * is a global bound, raster/ray result, source acceptance or eligibility certificate.
 */
function measureNativeTargetClipFeedback(request: NativeTargetShaderFeedbackRequest, control: NativeTargetControlledSubmission): NativeTargetShaderFeedbackResult {
  let result = unavailable('Measurement did not execute')
  let gl: WebGL2RenderingContext | null = null
  let saved: SavedGlState | null = null
  let feedbackActive = false
  const shaders: WebGLShader[] = []
  const buffers: WebGLBuffer[] = []
  let program: WebGLProgram | null = null
  let vertexArray: WebGLVertexArrayObject | null = null
  let feedback: WebGLTransformFeedback | null = null
  try {
    requireCondition(THREE.REVISION === '180', `Unsupported Three revision ${THREE.REVISION}; current program API was inspected for r180`)
    requireCondition(request.targetPrimitiveId.length > 0, 'Target primitive identity is absent')
    const count = request.targetVertexIndices.length
    requireCondition(count > 0 && count <= MAX_TARGET_VERTICES, `Target coordinate class must contain 1..${MAX_TARGET_VERTICES} vertices`)
    requireCondition(request.cpuWorldPositions instanceof Float64Array && request.cpuWorldPositions.length === count * 3, 'Pre-lease Float64 xyz reference row count differs from the target class')
    for (const coordinate of request.cpuWorldPositions) requireCondition(Number.isFinite(coordinate), 'Pre-lease CPU reference contains a nonfinite coordinate')
    requireCondition(!('isInstancedMesh' in request.object && request.object.isInstancedMesh)
      && !('isSkinnedMesh' in request.object && request.object.isSkinnedMesh)
      && !('isBatchedMesh' in request.object && request.object.isBatchedMesh), 'Instanced, skinned or batched native objects are unsupported')
    requireCondition(Object.values(request.object.geometry.morphAttributes).every(attributes => !attributes || attributes.length === 0), 'Native morph attributes are unsupported')
    const material = request.object.material
    requireCondition(!Array.isArray(material), 'Multi-material native targets are unsupported')
    requireCondition(material.onBeforeCompile === THREE.Material.prototype.onBeforeCompile
      && material.customProgramCacheKey === THREE.Material.prototype.customProgramCacheKey, 'Custom native shader hooks, including springs, have no matrix-only comparison law')
    requireCondition(!('isShaderMaterial' in material && material.isShaderMaterial)
      && !('isRawShaderMaterial' in material && material.isRawShaderMaterial), 'Custom shader materials have no validated stock matrix-only law')
    const context = request.renderer.getContext()
    requireCondition('createTransformFeedback' in context && typeof context.createTransformFeedback === 'function', 'Native renderer has no WebGL2 transform-feedback support')
    gl = context
    requireNoGlError(gl, 'entry (a pre-existing error is not ignored)')
    requireCondition(!gl.getParameter(gl.TRANSFORM_FEEDBACK_ACTIVE), 'An existing active or paused transform-feedback session cannot be disturbed')
    for (const target of [gl.ANY_SAMPLES_PASSED, gl.ANY_SAMPLES_PASSED_CONSERVATIVE, gl.TRANSFORM_FEEDBACK_PRIMITIVES_WRITTEN]) {
      requireCondition(gl.getQuery(target, gl.CURRENT_QUERY) === null, 'An existing GPU query would be contaminated by the feedback draw')
    }
    const timer = gl.getExtension('EXT_disjoint_timer_query_webgl2') as { TIME_ELAPSED_EXT: number } | null
    requireCondition(!timer || gl.getQuery(timer.TIME_ELAPSED_EXT, gl.CURRENT_QUERY) === null, 'An existing GPU timer query would be contaminated by the feedback draw')
    const properties = request.renderer.properties.get(material) as {
      currentProgram?: CurrentProgram; programs?: Map<string, CurrentProgram>; __version?: number
    }
    const original = properties.currentProgram
    requireCondition(original && original.program && properties.__version === material.version, 'Original native material has no current renderer-compiled program for its current version')
    requireCondition(properties.programs instanceof Map && properties.programs.size === 1
      && properties.programs.values().next().value === original, 'Multiple or ambiguous original native program variants are unsupported')
    requireCondition(gl.isProgram(original.program) && gl.getProgramParameter(original.program, gl.LINK_STATUS), 'Original native renderer program is invalid or not linked')
    const attached = gl.getAttachedShaders(original.program)
    requireCondition(attached && attached.length === 2 && attached.includes(original.vertexShader) && attached.includes(original.fragmentShader), 'Actual original compiled shader objects are unavailable or ambiguous')
    requireCondition(gl.getShaderParameter(original.vertexShader, gl.SHADER_TYPE) === gl.VERTEX_SHADER
      && gl.getShaderParameter(original.fragmentShader, gl.SHADER_TYPE) === gl.FRAGMENT_SHADER, 'Original compiled shader stages do not match')
    const vertexSource = gl.getShaderSource(original.vertexShader)
    const fragmentSource = gl.getShaderSource(original.fragmentShader)
    requireCondition(vertexSource && fragmentSource, 'Actual original compiled shader source is unavailable')
    requireCondition(/^\s*#version\s+300\s+es\b/.test(maskComments(fragmentSource)), 'Original fragment/vertex GLSL versions do not match supported ES 3.00')
    const derived = deriveFeedbackSource(vertexSource)
    result.shaderSeal = {
      encoding: 'exact-source-text', threeRevision: THREE.REVISION, programId: original.id,
      programCacheKey: original.cacheKey, materialUuid: material.uuid, materialVersion: material.version,
      originalVertexShaderSource: vertexSource, originalFragmentShaderSource: fragmentSource,
      derivedVertexShaderSource: derived.source, declarationsInsertionOffset: derived.declarationsOffset,
      derivedFragmentShaderSource: fragmentSource,
      feedbackProgramRelation: 'original-vertex-source-plus-clip-feedback-with-original-fragment-rasterizer-discard',
      assignmentsInsertionOffset: derived.assignmentsOffset, feedbackVaryings: [CLIP_OUTPUT],
      comparisonLaw: 'matrix-only-on-decoded-float32-position',
    }
    result.currentUniformSeal = {
      encoding: 'exact-reflected-uniform-bytes', byteOrder: BYTE_ORDER,
      reflectionComplete: false, valuesComplete: false, matrixChecks: [], uniforms: [],
    }
    const worldMatrix = request.object.matrixWorld.elements
    const expectedMatrices = [
      ['projectionMatrix', request.camera.projectionMatrix.elements],
      ['modelViewMatrix', request.object.modelViewMatrix.elements],
    ] as const
    for (const [name, expected] of expectedMatrices) {
      const location = gl.getUniformLocation(original.program, name)
      const observed: unknown = location === null ? null : gl.getUniform(original.program, location)
      const expectedFloat32 = expected.map(value => Math.fround(value))
      const observedFloat32 = observed instanceof Float32Array && observed.length === 16 ? Array.from(observed) : null
      result.currentUniformSeal.matrixChecks.push({
        name, expectedFloat32, observedFloat32,
        matches: observedFloat32 !== null && expectedFloat32.every((value, i) => Object.is(value, observedFloat32[i])),
      })
    }
    const uniforms = reflectUniforms(gl, original.program, result.currentUniformSeal)
    requireCondition(worldMatrix[3] === 0 && worldMatrix[7] === 0 && worldMatrix[11] === 0 && worldMatrix[15] === 1, 'Current native world matrix is not affine')
    for (const [name, expected] of expectedMatrices) requireMatrix(uniforms, name, expected)
    const actualModelView = uniforms.find(uniform => uniform.name === 'modelViewMatrix')!.elements[0]!.value!
    const view = request.camera.matrixWorldInverse.elements
    for (let column = 0; column < 4; column++) {
      for (let row = 0; row < 4; row++) {
        const offset = column * 4 + row
        const value = view[row]! * worldMatrix[column * 4]! + view[row + 4]! * worldMatrix[column * 4 + 1]!
          + view[row + 8]! * worldMatrix[column * 4 + 2]! + view[row + 12]! * worldMatrix[column * 4 + 3]!
        requireCondition(Object.is(actualModelView[offset], Math.fround(value)), 'Current modelViewMatrix uniform does not belong to this native object and camera')
      }
    }
    const derivedDiagnostic: NativeTargetDerivedDiagnostic = {
      method: 'float64-inverse-projection-and-camera-world-from-observed-native-clip',
      precision: 'cpu-float64-derived-world-not-observed-gpu-world',
      cpuClipReferenceMethod: 'current-float64-view-and-projection-on-prelease-world',
      viewMatrixFloat64: Array.from(request.camera.matrixWorldInverse.elements),
      projectionMatrixFloat64: Array.from(request.camera.projectionMatrix.elements),
      projectionMatrixInverseFloat64: Array.from(request.camera.projectionMatrixInverse.elements),
      cameraMatrixWorldFloat64: Array.from(request.camera.matrixWorld.elements),
      qualification: 'inverse-projection-conditioning-may-amplify-error-not-global-bound',
    }
    result.derivedDiagnostic = derivedDiagnostic
    const prepared = prepareAttributes(gl, original.program, request)
    result.attributeSeal = prepared.seal
    requireNoGlError(gl, 'original program reflection')
    saved = {
      program: gl.getParameter(gl.CURRENT_PROGRAM) as WebGLProgram | null,
      vertexArray: gl.getParameter(gl.VERTEX_ARRAY_BINDING) as WebGLVertexArrayObject | null,
      arrayBuffer: gl.getParameter(gl.ARRAY_BUFFER_BINDING) as WebGLBuffer | null,
      transformFeedback: gl.getParameter(gl.TRANSFORM_FEEDBACK_BINDING) as WebGLTransformFeedback | null,
      transformFeedbackBuffer: gl.getParameter(gl.TRANSFORM_FEEDBACK_BUFFER_BINDING) as WebGLBuffer | null,
      activeTexture: gl.getParameter(gl.ACTIVE_TEXTURE) as number,
      rasterizerDiscard: gl.isEnabled(gl.RASTERIZER_DISCARD),
    }
    function compile(type: number, source: string): WebGLShader {
      const shader = gl!.createShader(type)
      requireCondition(shader, 'Could not allocate a scoped feedback shader')
      shaders.push(shader)
      gl!.shaderSource(shader, source)
      gl!.compileShader(shader)
      requireCondition(gl!.getShaderParameter(shader, gl!.COMPILE_STATUS), `Derived shader compilation failed: ${gl!.getShaderInfoLog(shader) ?? 'no driver log'}`)
      return shader
    }
    program = gl.createProgram()
    requireCondition(program, 'Could not allocate a scoped feedback program')
    gl.attachShader(program, compile(gl.VERTEX_SHADER, derived.source))
    gl.attachShader(program, compile(gl.FRAGMENT_SHADER, fragmentSource))
    gl.transformFeedbackVaryings(program, [CLIP_OUTPUT], gl.SEPARATE_ATTRIBS)
    gl.linkProgram(program)
    requireCondition(gl.getProgramParameter(program, gl.LINK_STATUS), `Derived feedback program link failed: ${gl.getProgramInfoLog(program) ?? 'no driver log'}`)
    requireCondition(gl.getProgramParameter(program, gl.TRANSFORM_FEEDBACK_VARYINGS) === 1, 'Derived program does not expose exactly one clip feedback output')
    const varying = gl.getTransformFeedbackVarying(program, 0)
    requireCondition(varying?.name === CLIP_OUTPUT && varying.type === gl.FLOAT_VEC4 && varying.size === 1, 'Derived clip transform-feedback output layout differs')
    gl.useProgram(program)
    copyFeedbackUniforms(gl, program, uniforms, result.currentUniformSeal)
    vertexArray = gl.createVertexArray()
    feedback = gl.createTransformFeedback()
    requireCondition(vertexArray && feedback, 'Could not allocate scoped feedback VAO/transform-feedback state')
    gl.bindVertexArray(vertexArray)
    const feedbackAttributeCount = gl.getProgramParameter(program, gl.ACTIVE_ATTRIBUTES) as number
    for (let i = 0; i < feedbackAttributeCount; i++) {
      const info = gl.getActiveAttrib(program, i)
      requireCondition(info && info.size === 1, 'Actual feedback vertex attribute reflection is unavailable')
      const originalAttribute = prepared.seal.attributes.find(attribute => attribute.name === info.name)
      requireCondition(originalAttribute?.shaderType === info.type, `Feedback vertex program requires an unsealed original attribute: ${info.name}`)
    }
    for (let i = 0; i < prepared.attributes.length; i++) {
      const attribute = prepared.attributes[i]!
      const attributeSeal = prepared.seal.attributes[i]!
      const location = gl.getAttribLocation(program, attribute.name)
      if (location < 0) {
        attributeSeal.feedbackUse = 'inactive'
        continue
      }
      attributeSeal.feedbackLocation = location
      const buffer = gl.createBuffer()
      requireCondition(buffer, 'Could not allocate a scoped selected-attribute buffer')
      buffers.push(buffer)
      gl.bindBuffer(gl.ARRAY_BUFFER, buffer)
      gl.bufferData(gl.ARRAY_BUFFER, attribute.packed, gl.STATIC_DRAW)
      gl.enableVertexAttribArray(location)
      if (attribute.integerPointer) gl.vertexAttribIPointer(location, attribute.itemSize, attribute.glType, 0, 0)
      else gl.vertexAttribPointer(location, attribute.itemSize, attribute.glType, attribute.normalized, 0, 0)
      gl.vertexAttribDivisor(location, 0)
      attributeSeal.feedbackUse = 'copied'
    }
    gl.bindTransformFeedback(gl.TRANSFORM_FEEDBACK, feedback)
    const clip = new Float32Array(count * 4).fill(NaN)
    const clipBuffer = gl.createBuffer()
    requireCondition(clipBuffer, 'Could not allocate a scoped clip feedback readback buffer')
    buffers.push(clipBuffer)
    gl.bindBuffer(gl.TRANSFORM_FEEDBACK_BUFFER, clipBuffer)
    gl.bufferData(gl.TRANSFORM_FEEDBACK_BUFFER, clip, gl.STREAM_READ)
    gl.bindBufferBase(gl.TRANSFORM_FEEDBACK_BUFFER, 0, clipBuffer)
    requireNoGlError(gl, 'feedback preparation')
    gl.enable(gl.RASTERIZER_DISCARD)
    gl.beginTransformFeedback(gl.POINTS)
    feedbackActive = true
    gl.drawArrays(gl.POINTS, 0, count)
    gl.endTransformFeedback()
    feedbackActive = false
    requireNoGlError(gl, 'actual target-only transform-feedback draw')
    gl.bindBuffer(gl.TRANSFORM_FEEDBACK_BUFFER, clipBuffer)
    gl.getBufferSubData(gl.TRANSFORM_FEEDBACK_BUFFER, 0, clip)
    requireNoGlError(gl, 'GPU Float32 feedback readback')
    for (const value of clip) requireCondition(Number.isFinite(value), 'GPU clip output is nonfinite or was not written')
    const diagnostic = deriveClipDiagnostics(clip, request.cpuWorldPositions, derivedDiagnostic)
    result.status = 'measured'
    result.reason = 'Actual current native gl_Position observed by target-only WebGL2 transform feedback; world diagnostics are separately derived in CPU Float64 and are not an independent global bound'
    result.observedClipPositions = clip
    result.cpuClipPositions = diagnostic.cpuClipPositions
    result.derivedWorldPositions = diagnostic.derivedWorldPositions
    result.maxObservedClipDelta = diagnostic.maxObservedClipDelta
    result.perVertexClipDelta = diagnostic.perVertexClipDelta
    result.maxDerivedWorldDeltaMetres = diagnostic.maxDerivedWorldDeltaMetres
    result.perVertexDerivedWorldDeltaMetres = diagnostic.perVertexDerivedWorldDeltaMetres
    control.transformFeedbackSampled = true
  } catch (error) {
    result.reason = error instanceof Error ? error.message : String(error)
  } finally {
    if (gl && saved) {
      const failures: string[] = []
      const context = gl
      const attempt = (action: () => void) => {
        try { action() } catch (error) { failures.push(error instanceof Error ? error.message : String(error)) }
      }
      if (feedbackActive) attempt(() => context.endTransformFeedback())
      // Indexed feedback buffer bases/ranges belong to the feedback object. Only our
      // own object was edited; rebinding the original restores every original slot.
      attempt(() => context.bindTransformFeedback(context.TRANSFORM_FEEDBACK, saved!.transformFeedback))
      attempt(() => context.bindBuffer(context.TRANSFORM_FEEDBACK_BUFFER, saved!.transformFeedbackBuffer))
      attempt(() => context.bindVertexArray(saved!.vertexArray))
      attempt(() => context.bindBuffer(context.ARRAY_BUFFER, saved!.arrayBuffer))
      attempt(() => context.useProgram(saved!.program))
      attempt(() => context.activeTexture(saved!.activeTexture))
      attempt(() => saved!.rasterizerDiscard ? context.enable(context.RASTERIZER_DISCARD) : context.disable(context.RASTERIZER_DISCARD))
      // No framebuffer, renderer render target, texture binding, other enabled state,
      // native material/geometry/object, or Three state-cache entry was modified.
      for (const buffer of buffers) attempt(() => context.deleteBuffer(buffer))
      if (feedback) attempt(() => context.deleteTransformFeedback(feedback))
      if (vertexArray) attempt(() => context.deleteVertexArray(vertexArray))
      if (program) attempt(() => context.deleteProgram(program))
      for (const shader of shaders) attempt(() => context.deleteShader(shader))
      attempt(() => requireNoGlError(context, 'native GL state restoration and scoped resource cleanup'))
      if (failures.length > 0) {
        control.cleanup.failures.push(...failures)
        control.transformFeedbackSampled = false
        clearMeasurement(result)
        result.reason = `Feedback/cleanup could not preserve a valid native context: ${failures.join('; ')}`
      }
    }
  }
  return result
}

interface ControlGlState {
  parameters: Map<number, unknown>
  capabilities: { capability: number; enabled: boolean }[]
  drawBuffers: number[]
  textures: { texture2D: WebGLTexture | null; textureCube: WebGLTexture | null; texture3D: WebGLTexture | null; textureArray: WebGLTexture | null; sampler: WebGLSampler | null }[]
  uniformBuffers: { buffer: WebGLBuffer | null; start: number; size: number }[]
  vertexValues: (Float32Array | Int32Array | Uint32Array)[]
  pixelStore: { parameter: number; value: number | boolean }[]
}

/** Internal live handles and logical renderer state; never part of a serialized receipt. */
export interface NativeDiagnosticRendererState {
  rawControlGlState: ControlGlState
  renderTarget: THREE.WebGLRenderTarget | null
  activeCubeFace: number
  activeMipmapLevel: number
  viewport: THREE.Vector4
  scissor: THREE.Vector4
  scissorTest: boolean
  clearColor: THREE.Color
  clearAlpha: number
}

export function captureNativeDiagnosticRendererState(renderer: THREE.WebGLRenderer): NativeDiagnosticRendererState {
  requireCondition(THREE.REVISION === '180', `Unsupported Three revision ${THREE.REVISION}; diagnostic state restoration was inspected for r180`)
  // resetState cannot restore this constructor-only EXT_clip_control mode.
  requireCondition(!renderer.capabilities.reversedDepthBuffer && !renderer.state.buffers.depth.getReversed(),
    'Reversed native depth/clip-control mode cannot be preserved by r180 resetState')
  const context = renderer.getContext()
  requireCondition('createTransformFeedback' in context && typeof context.createTransformFeedback === 'function', 'Native diagnostic state requires WebGL2')
  const gl = context
  requireNoGlError(gl, 'diagnostic state entry (a pre-existing error is not ignored)')
  const program = gl.getParameter(gl.CURRENT_PROGRAM) as WebGLProgram | null
  requireCondition(program === null || gl.isProgram(program) && !gl.getProgramParameter(program, gl.DELETE_STATUS),
    'Native diagnostic entry program is invalid or pending deletion')
  return {
    rawControlGlState: captureControlGlState(gl),
    renderTarget: renderer.getRenderTarget(),
    activeCubeFace: renderer.getActiveCubeFace(), activeMipmapLevel: renderer.getActiveMipmapLevel(),
    viewport: renderer.getViewport(new THREE.Vector4()), scissor: renderer.getScissor(new THREE.Vector4()),
    scissorTest: renderer.getScissorTest(),
    clearColor: renderer.getClearColor(new THREE.Color()), clearAlpha: renderer.getClearAlpha(),
  }
}

function nativeBlendEquation(gl: WebGL2RenderingContext, value: number): THREE.BlendingEquation {
  switch (value) {
    case gl.FUNC_ADD: return THREE.AddEquation
    case gl.FUNC_SUBTRACT: return THREE.SubtractEquation
    case gl.FUNC_REVERSE_SUBTRACT: return THREE.ReverseSubtractEquation
    case gl.MIN: return THREE.MinEquation
    case gl.MAX: return THREE.MaxEquation
    default: throw new Error(`Unsupported saved native blend equation 0x${value.toString(16)}`)
  }
}

function nativeBlendFactor(gl: WebGL2RenderingContext, value: number): THREE.BlendingSrcFactor {
  switch (value) {
    case gl.ZERO: return THREE.ZeroFactor
    case gl.ONE: return THREE.OneFactor
    case gl.SRC_COLOR: return THREE.SrcColorFactor
    case gl.ONE_MINUS_SRC_COLOR: return THREE.OneMinusSrcColorFactor
    case gl.DST_COLOR: return THREE.DstColorFactor
    case gl.ONE_MINUS_DST_COLOR: return THREE.OneMinusDstColorFactor
    case gl.SRC_ALPHA: return THREE.SrcAlphaFactor
    case gl.ONE_MINUS_SRC_ALPHA: return THREE.OneMinusSrcAlphaFactor
    case gl.DST_ALPHA: return THREE.DstAlphaFactor
    case gl.ONE_MINUS_DST_ALPHA: return THREE.OneMinusDstAlphaFactor
    case gl.SRC_ALPHA_SATURATE: return THREE.SrcAlphaSaturateFactor
    case gl.CONSTANT_COLOR: return THREE.ConstantColorFactor
    case gl.ONE_MINUS_CONSTANT_COLOR: return THREE.OneMinusConstantColorFactor
    case gl.CONSTANT_ALPHA: return THREE.ConstantAlphaFactor
    case gl.ONE_MINUS_CONSTANT_ALPHA: return THREE.OneMinusConstantAlphaFactor
    default: throw new Error(`Unsupported saved native blend factor 0x${value.toString(16)}`)
  }
}

/** Restore before disposing owned programs/VAOs. Every keeper is attempted on failure. */
export function restoreNativeDiagnosticRendererState(renderer: THREE.WebGLRenderer, saved: NativeDiagnosticRendererState): string[] {
  const failures: string[] = []
  const attempt = (action: () => void) => {
    try { action() } catch (error) { failures.push(error instanceof Error ? error.message : String(error)) }
  }
  let context: WebGL2RenderingContext | null = null
  try { context = renderer.getContext() as WebGL2RenderingContext }
  catch (error) { failures.push(error instanceof Error ? error.message : String(error)) }
  attempt(() => renderer.resetState())
  attempt(() => renderer.setRenderTarget(saved.renderTarget, saved.activeCubeFace, saved.activeMipmapLevel))
  attempt(() => renderer.setViewport(saved.viewport))
  attempt(() => renderer.setScissor(saved.scissor))
  attempt(() => renderer.setScissorTest(saved.scissorTest))
  attempt(() => renderer.setClearColor(saved.clearColor, saved.clearAlpha))
  // Logical setters above populate caches from logical values, which need not
  // equal the saved raw framebuffer/clear state. Invalidate those writes without
  // clearing the now-restored logical render target or rewinding info.render.frame.
  attempt(() => renderer.state.reset())
  if (!context) return failures
  const gl = context
  const raw = saved.rawControlGlState
  attempt(() => {
    const number = (parameter: number) => raw.parameters.get(parameter) as number
    const color = raw.parameters.get(gl.BLEND_COLOR) as ArrayLike<number>
    // @types/three r180 still declares the old eight-argument setter. The installed
    // r180 implementation has these exact ten arguments, including color/alpha.
    const setBlending = renderer.state.setBlending as unknown as (
      blending: THREE.Blending, equation: THREE.BlendingEquation, src: THREE.BlendingSrcFactor, dst: THREE.BlendingDstFactor,
      equationAlpha: THREE.BlendingEquation, srcAlpha: THREE.BlendingSrcFactor, dstAlpha: THREE.BlendingDstFactor,
      color: THREE.Color, alpha: number, premultipliedAlpha: boolean
    ) => void
    setBlending.call(renderer.state, THREE.CustomBlending,
      nativeBlendEquation(gl, number(gl.BLEND_EQUATION_RGB)), nativeBlendFactor(gl, number(gl.BLEND_SRC_RGB)),
      nativeBlendFactor(gl, number(gl.BLEND_DST_RGB)) as THREE.BlendingDstFactor,
      nativeBlendEquation(gl, number(gl.BLEND_EQUATION_ALPHA)), nativeBlendFactor(gl, number(gl.BLEND_SRC_ALPHA)),
      nativeBlendFactor(gl, number(gl.BLEND_DST_ALPHA)) as THREE.BlendingDstFactor,
      new THREE.Color(color[0]!, color[1]!, color[2]!), color[3]!, false)
    // Even disabled blending retains its saved equations/factors/color in GL.
    // Prime them faithfully first so a later custom draw cannot skip blendColor.
    if (!raw.capabilities.find(entry => entry.capability === gl.BLEND)!.enabled) renderer.state.setBlending(THREE.NoBlending)
  })
  // Unlike the dedicated blending boolean, the other capability caches reset to
  // unknown. Seed exact values; viewport/scissor reset to concrete canvas bounds.
  for (const entry of raw.capabilities) attempt(() => entry.enabled ? renderer.state.enable(entry.capability) : renderer.state.disable(entry.capability))
  attempt(() => renderer.state.viewport(new THREE.Vector4().fromArray(raw.parameters.get(gl.VIEWPORT) as ArrayLike<number>)))
  attempt(() => renderer.state.scissor(new THREE.Vector4().fromArray(raw.parameters.get(gl.SCISSOR_BOX) as ArrayLike<number>)))
  restoreControlGlState(gl, raw, failures)
  return failures
}

/** Snapshot the state touched by r180 render, its resetState, and our scoped raw TF. */
function captureControlGlState(gl: WebGL2RenderingContext): ControlGlState {
  const parameters = new Map<number, unknown>()
  for (const parameter of [
    gl.CURRENT_PROGRAM, gl.VERTEX_ARRAY_BINDING, gl.ARRAY_BUFFER_BINDING, gl.ELEMENT_ARRAY_BUFFER_BINDING,
    gl.TRANSFORM_FEEDBACK_BINDING, gl.TRANSFORM_FEEDBACK_BUFFER_BINDING,
    gl.COPY_READ_BUFFER_BINDING, gl.COPY_WRITE_BUFFER_BINDING, gl.PIXEL_PACK_BUFFER_BINDING,
    gl.PIXEL_UNPACK_BUFFER_BINDING, gl.UNIFORM_BUFFER_BINDING, gl.RENDERBUFFER_BINDING,
    gl.DRAW_FRAMEBUFFER_BINDING, gl.READ_FRAMEBUFFER_BINDING, gl.READ_BUFFER, gl.ACTIVE_TEXTURE,
    gl.BLEND_EQUATION_RGB, gl.BLEND_EQUATION_ALPHA, gl.BLEND_SRC_RGB, gl.BLEND_DST_RGB,
    gl.BLEND_SRC_ALPHA, gl.BLEND_DST_ALPHA, gl.BLEND_COLOR, gl.COLOR_WRITEMASK, gl.COLOR_CLEAR_VALUE,
    gl.DEPTH_WRITEMASK, gl.DEPTH_FUNC, gl.DEPTH_RANGE, gl.DEPTH_CLEAR_VALUE,
    gl.STENCIL_FUNC, gl.STENCIL_REF, gl.STENCIL_VALUE_MASK, gl.STENCIL_WRITEMASK,
    gl.STENCIL_FAIL, gl.STENCIL_PASS_DEPTH_FAIL, gl.STENCIL_PASS_DEPTH_PASS,
    gl.STENCIL_BACK_FUNC, gl.STENCIL_BACK_REF, gl.STENCIL_BACK_VALUE_MASK, gl.STENCIL_BACK_WRITEMASK,
    gl.STENCIL_BACK_FAIL, gl.STENCIL_BACK_PASS_DEPTH_FAIL, gl.STENCIL_BACK_PASS_DEPTH_PASS, gl.STENCIL_CLEAR_VALUE,
    gl.CULL_FACE_MODE, gl.FRONT_FACE, gl.POLYGON_OFFSET_FACTOR, gl.POLYGON_OFFSET_UNITS, gl.LINE_WIDTH,
    gl.VIEWPORT, gl.SCISSOR_BOX, gl.SAMPLE_COVERAGE_VALUE, gl.SAMPLE_COVERAGE_INVERT,
  ]) parameters.set(parameter, gl.getParameter(parameter))
  const capabilities = [
    gl.BLEND, gl.CULL_FACE, gl.DEPTH_TEST, gl.STENCIL_TEST, gl.SCISSOR_TEST, gl.POLYGON_OFFSET_FILL,
    gl.SAMPLE_ALPHA_TO_COVERAGE, gl.SAMPLE_COVERAGE, gl.DITHER, gl.RASTERIZER_DISCARD,
  ].map(capability => ({ capability, enabled: gl.isEnabled(capability) }))
  const drawBuffers: number[] = []
  const drawBufferCount = parameters.get(gl.DRAW_FRAMEBUFFER_BINDING) === null ? 1 : gl.getParameter(gl.MAX_DRAW_BUFFERS) as number
  for (let index = 0; index < drawBufferCount; index++) drawBuffers.push(gl.getParameter(gl.DRAW_BUFFER0 + index) as number)
  const uniformBuffers: ControlGlState['uniformBuffers'] = []
  const uniformBufferCount = gl.getParameter(gl.MAX_UNIFORM_BUFFER_BINDINGS) as number
  for (let index = 0; index < uniformBufferCount; index++) uniformBuffers.push({
    buffer: gl.getIndexedParameter(gl.UNIFORM_BUFFER_BINDING, index) as WebGLBuffer | null,
    start: gl.getIndexedParameter(gl.UNIFORM_BUFFER_START, index) as number,
    size: gl.getIndexedParameter(gl.UNIFORM_BUFFER_SIZE, index) as number,
  })
  const vertexValues: ControlGlState['vertexValues'] = []
  const attributeCount = gl.getParameter(gl.MAX_VERTEX_ATTRIBS) as number
  for (let index = 0; index < attributeCount; index++) vertexValues.push(gl.getVertexAttrib(index, gl.CURRENT_VERTEX_ATTRIB) as Float32Array | Int32Array | Uint32Array)
  const pixelStore = [
    gl.PACK_ALIGNMENT, gl.PACK_ROW_LENGTH, gl.PACK_SKIP_PIXELS, gl.PACK_SKIP_ROWS,
    gl.UNPACK_ALIGNMENT, gl.UNPACK_ROW_LENGTH, gl.UNPACK_IMAGE_HEIGHT, gl.UNPACK_SKIP_PIXELS,
    gl.UNPACK_SKIP_ROWS, gl.UNPACK_SKIP_IMAGES, gl.UNPACK_FLIP_Y_WEBGL,
    gl.UNPACK_PREMULTIPLY_ALPHA_WEBGL, gl.UNPACK_COLORSPACE_CONVERSION_WEBGL,
  ].map(parameter => ({ parameter, value: gl.getParameter(parameter) as number | boolean }))
  const textures: ControlGlState['textures'] = []
  const activeTexture = parameters.get(gl.ACTIVE_TEXTURE) as number
  try {
    const unitCount = gl.getParameter(gl.MAX_COMBINED_TEXTURE_IMAGE_UNITS) as number
    for (let unit = 0; unit < unitCount; unit++) {
      gl.activeTexture(gl.TEXTURE0 + unit)
      textures.push({
        texture2D: gl.getParameter(gl.TEXTURE_BINDING_2D) as WebGLTexture | null,
        textureCube: gl.getParameter(gl.TEXTURE_BINDING_CUBE_MAP) as WebGLTexture | null,
        texture3D: gl.getParameter(gl.TEXTURE_BINDING_3D) as WebGLTexture | null,
        textureArray: gl.getParameter(gl.TEXTURE_BINDING_2D_ARRAY) as WebGLTexture | null,
        sampler: gl.getParameter(gl.SAMPLER_BINDING) as WebGLSampler | null,
      })
    }
  } finally {
    gl.activeTexture(activeTexture)
  }
  requireNoGlError(gl, 'control state capture')
  return { parameters, capabilities, drawBuffers, textures, uniformBuffers, vertexValues, pixelStore }
}

function restoreControlGlState(gl: WebGL2RenderingContext, saved: ControlGlState, failures: string[]): void {
  const attempt = (action: () => void) => {
    try { action() } catch (error) { failures.push(error instanceof Error ? error.message : String(error)) }
  }
  const number = (parameter: number) => saved.parameters.get(parameter) as number
  const vector = (parameter: number) => saved.parameters.get(parameter) as ArrayLike<number>
  attempt(() => gl.bindFramebuffer(gl.DRAW_FRAMEBUFFER, saved.parameters.get(gl.DRAW_FRAMEBUFFER_BINDING) as WebGLFramebuffer | null))
  attempt(() => gl.bindFramebuffer(gl.READ_FRAMEBUFFER, saved.parameters.get(gl.READ_FRAMEBUFFER_BINDING) as WebGLFramebuffer | null))
  attempt(() => gl.drawBuffers(saved.drawBuffers))
  attempt(() => gl.readBuffer(number(gl.READ_BUFFER)))
  attempt(() => gl.bindRenderbuffer(gl.RENDERBUFFER, saved.parameters.get(gl.RENDERBUFFER_BINDING) as WebGLRenderbuffer | null))
  attempt(() => gl.bindTransformFeedback(gl.TRANSFORM_FEEDBACK, saved.parameters.get(gl.TRANSFORM_FEEDBACK_BINDING) as WebGLTransformFeedback | null))
  attempt(() => gl.bindVertexArray(saved.parameters.get(gl.VERTEX_ARRAY_BINDING) as WebGLVertexArrayObject | null))
  for (let index = 0; index < saved.uniformBuffers.length; index++) {
    const entry = saved.uniformBuffers[index]!
    attempt(() => {
      if (entry.buffer && entry.size > 0) gl.bindBufferRange(gl.UNIFORM_BUFFER, index, entry.buffer, entry.start, entry.size)
      else gl.bindBufferBase(gl.UNIFORM_BUFFER, index, entry.buffer)
    })
  }
  for (const [target, binding] of [
    [gl.ARRAY_BUFFER, gl.ARRAY_BUFFER_BINDING], [gl.ELEMENT_ARRAY_BUFFER, gl.ELEMENT_ARRAY_BUFFER_BINDING],
    [gl.TRANSFORM_FEEDBACK_BUFFER, gl.TRANSFORM_FEEDBACK_BUFFER_BINDING],
    [gl.COPY_READ_BUFFER, gl.COPY_READ_BUFFER_BINDING], [gl.COPY_WRITE_BUFFER, gl.COPY_WRITE_BUFFER_BINDING],
    [gl.PIXEL_PACK_BUFFER, gl.PIXEL_PACK_BUFFER_BINDING], [gl.PIXEL_UNPACK_BUFFER, gl.PIXEL_UNPACK_BUFFER_BINDING],
    [gl.UNIFORM_BUFFER, gl.UNIFORM_BUFFER_BINDING],
  ]) attempt(() => gl.bindBuffer(target!, saved.parameters.get(binding!) as WebGLBuffer | null))
  attempt(() => gl.useProgram(saved.parameters.get(gl.CURRENT_PROGRAM) as WebGLProgram | null))
  for (let unit = 0; unit < saved.textures.length; unit++) {
    const texture = saved.textures[unit]!
    attempt(() => gl.activeTexture(gl.TEXTURE0 + unit))
    attempt(() => gl.bindTexture(gl.TEXTURE_2D, texture.texture2D))
    attempt(() => gl.bindTexture(gl.TEXTURE_CUBE_MAP, texture.textureCube))
    attempt(() => gl.bindTexture(gl.TEXTURE_3D, texture.texture3D))
    attempt(() => gl.bindTexture(gl.TEXTURE_2D_ARRAY, texture.textureArray))
    attempt(() => gl.bindSampler(unit, texture.sampler))
  }
  attempt(() => gl.activeTexture(number(gl.ACTIVE_TEXTURE)))
  for (let index = 0; index < saved.vertexValues.length; index++) {
    const value = saved.vertexValues[index]!
    attempt(() => {
      if (value instanceof Int32Array) gl.vertexAttribI4iv(index, value)
      else if (value instanceof Uint32Array) gl.vertexAttribI4uiv(index, value)
      else gl.vertexAttrib4fv(index, value)
    })
  }
  for (const entry of saved.pixelStore) attempt(() => gl.pixelStorei(entry.parameter, entry.value))
  attempt(() => gl.blendEquationSeparate(number(gl.BLEND_EQUATION_RGB), number(gl.BLEND_EQUATION_ALPHA)))
  attempt(() => gl.blendFuncSeparate(number(gl.BLEND_SRC_RGB), number(gl.BLEND_DST_RGB), number(gl.BLEND_SRC_ALPHA), number(gl.BLEND_DST_ALPHA)))
  attempt(() => { const v = vector(gl.BLEND_COLOR); gl.blendColor(v[0]!, v[1]!, v[2]!, v[3]!) })
  attempt(() => { const v = vector(gl.COLOR_WRITEMASK); gl.colorMask(Boolean(v[0]), Boolean(v[1]), Boolean(v[2]), Boolean(v[3])) })
  attempt(() => { const v = vector(gl.COLOR_CLEAR_VALUE); gl.clearColor(v[0]!, v[1]!, v[2]!, v[3]!) })
  attempt(() => gl.depthMask(saved.parameters.get(gl.DEPTH_WRITEMASK) as boolean))
  attempt(() => gl.depthFunc(number(gl.DEPTH_FUNC)))
  attempt(() => { const v = vector(gl.DEPTH_RANGE); gl.depthRange(v[0]!, v[1]!) })
  attempt(() => gl.clearDepth(number(gl.DEPTH_CLEAR_VALUE)))
  for (const [face, func, ref, mask, writeMask, fail, depthFail, pass] of [
    [gl.FRONT, gl.STENCIL_FUNC, gl.STENCIL_REF, gl.STENCIL_VALUE_MASK, gl.STENCIL_WRITEMASK, gl.STENCIL_FAIL, gl.STENCIL_PASS_DEPTH_FAIL, gl.STENCIL_PASS_DEPTH_PASS],
    [gl.BACK, gl.STENCIL_BACK_FUNC, gl.STENCIL_BACK_REF, gl.STENCIL_BACK_VALUE_MASK, gl.STENCIL_BACK_WRITEMASK, gl.STENCIL_BACK_FAIL, gl.STENCIL_BACK_PASS_DEPTH_FAIL, gl.STENCIL_BACK_PASS_DEPTH_PASS],
  ]) {
    attempt(() => gl.stencilFuncSeparate(face!, number(func!), number(ref!), number(mask!)))
    attempt(() => gl.stencilMaskSeparate(face!, number(writeMask!)))
    attempt(() => gl.stencilOpSeparate(face!, number(fail!), number(depthFail!), number(pass!)))
  }
  attempt(() => gl.clearStencil(number(gl.STENCIL_CLEAR_VALUE)))
  attempt(() => gl.cullFace(number(gl.CULL_FACE_MODE)))
  attempt(() => gl.frontFace(number(gl.FRONT_FACE)))
  attempt(() => gl.polygonOffset(number(gl.POLYGON_OFFSET_FACTOR), number(gl.POLYGON_OFFSET_UNITS)))
  attempt(() => gl.lineWidth(number(gl.LINE_WIDTH)))
  attempt(() => { const v = vector(gl.VIEWPORT); gl.viewport(v[0]!, v[1]!, v[2]!, v[3]!) })
  attempt(() => { const v = vector(gl.SCISSOR_BOX); gl.scissor(v[0]!, v[1]!, v[2]!, v[3]!) })
  attempt(() => gl.sampleCoverage(number(gl.SAMPLE_COVERAGE_VALUE), saved.parameters.get(gl.SAMPLE_COVERAGE_INVERT) as boolean))
  for (const entry of saved.capabilities) attempt(() => entry.enabled ? gl.enable(entry.capability) : gl.disable(entry.capability))
  attempt(() => requireNoGlError(gl, 'controlled native submission state restoration'))
}

function validateControlRequest(request: NativeTargetShaderFeedbackRequest): THREE.Material {
  requireCondition(THREE.REVISION === '180', `Unsupported Three revision ${THREE.REVISION}; native control was inspected for r180`)
  requireCondition(request.scene instanceof THREE.Scene && request.camera instanceof THREE.PerspectiveCamera, 'Native control requires the actual Scene and current perspective camera')
  requireCondition(request.object instanceof THREE.Mesh, 'Requested triangle control requires an actual native Mesh')
  requireCondition(!('isInstancedMesh' in request.object && request.object.isInstancedMesh)
    && !('isSkinnedMesh' in request.object && request.object.isSkinnedMesh)
    && !('isBatchedMesh' in request.object && request.object.isBatchedMesh), 'Instanced, skinned or batched native objects are unsupported')
  let inScene = false
  for (let node: THREE.Object3D | null = request.object; node; node = node.parent) {
    requireCondition(node.visible, 'Native target has an invisible ancestor')
    if (node === request.scene) { inScene = true; break }
  }
  requireCondition(inScene && request.object.layers.test(request.camera.layers), 'Native target is not in the actual Scene/current camera layer')
  requireCondition(request.scene.overrideMaterial === null && !request.renderer.shadowMap.enabled
    && !request.renderer.xr.isPresenting, 'Override material, enabled shadow passes and presenting XR are unsupported by non-colour native control')
  // r180 resetState disables reversed depth/EXT_clip_control; it cannot re-enable
  // that constructor-only renderer mode through a supported public API.
  requireCondition(!request.renderer.capabilities.reversedDepthBuffer && !request.camera.reversedDepth,
    'Reversed native depth/clip-control mode cannot be preserved by r180 resetState')
  requireCondition(request.renderer.getRenderTarget() === null, 'Native control requires the current default colour framebuffer; offscreen resolve/mipmap side effects are unsupported')
  request.scene.traverseVisible(node => {
    if (!('material' in node)) return
    const material = node.material as THREE.Material | THREE.Material[]
    for (const entry of Array.isArray(material) ? material : [material]) {
      requireCondition(!entry.visible || !('transmission' in entry) || entry.transmission === 0, 'A native transmission pass would clear a framebuffer despite rasterizer discard')
    }
  })
  const geometry = request.object.geometry
  requireCondition(Object.values(geometry.morphAttributes).every(attributes => !attributes || attributes.length === 0), 'Native morph attributes are unsupported')
  const material = request.object.material
  requireCondition(!Array.isArray(material), 'Multi-material native targets are unsupported')
  requireCondition(material.visible && !('wireframe' in material && material.wireframe), 'Requested target is not an active native filled-triangle material')
  requireCondition(material.onBeforeCompile === THREE.Material.prototype.onBeforeCompile
    && material.customProgramCacheKey === THREE.Material.prototype.customProgramCacheKey, 'Custom native shader hooks, including springs, have no matrix-only comparison law')
  requireCondition(!('isShaderMaterial' in material && material.isShaderMaterial)
    && !('isRawShaderMaterial' in material && material.isRawShaderMaterial), 'Custom shader materials have no validated stock matrix-only law')
  requireCondition(request.targetPrimitiveId.length > 0 && typeof request.beforeSample === 'function', 'Native target identity or Scene seal check is absent')
  requireCondition(Number.isSafeInteger(request.controlSubmissionRevision) && request.controlSubmissionRevision > 0, 'Native control revision must be a positive safe integer')
  const association = request.associatedColourDraw
  requireCondition(association && Number.isSafeInteger(association.drawRevision) && association.drawRevision > 0
    && Number.isSafeInteger(association.contextRevision) && association.contextRevision >= 0 && association.viewId.length > 0
    && (association.timeSeconds === null || Number.isFinite(association.timeSeconds)), 'Original colour association tuple is invalid')
  const count = request.targetVertexIndices.length
  requireCondition(count > 0 && count <= MAX_TARGET_VERTICES, `Target coordinate class must contain 1..${MAX_TARGET_VERTICES} vertices`)
  requireCondition(request.cpuWorldPositions instanceof Float64Array && request.cpuWorldPositions.length === count * 3
    && request.cpuWorldPositions.every(Number.isFinite), 'Pre-lease Float64 xyz reference rows must match the complete target class and be finite')
  const position = geometry.getAttribute('position')
  requireCondition(position && position.array instanceof Float32Array && position.itemSize === 3 && !position.normalized, 'Target requires actual decoded, nonnormalized Float32 xyz POSITION')
  const stride = position instanceof THREE.InterleavedBufferAttribute ? position.data.stride : position.itemSize
  const attributeOffset = position instanceof THREE.InterleavedBufferAttribute ? position.offset : 0
  requireCondition(Number.isSafeInteger(stride) && stride >= position.itemSize && Number.isSafeInteger(attributeOffset)
    && attributeOffset >= 0 && attributeOffset + position.itemSize <= stride, 'Invalid actual decoded POSITION layout')
  const bits = new Uint32Array(position.array.buffer, position.array.byteOffset, position.array.length)
  const seen = new Set<number>()
  for (const index of request.targetVertexIndices) {
    requireCondition(Number.isSafeInteger(index) && index >= 0 && index < position.count && !seen.has(index), 'Target indices must be unique actual decoded vertex indices within POSITION')
    seen.add(index)
    for (let axis = 0; axis < 3; axis++) {
      const offset = index * stride + attributeOffset + axis
      const firstOffset = request.targetVertexIndices[0]! * stride + attributeOffset + axis
      requireCondition(Number.isFinite(position.array[offset]) && bits[offset] === bits[firstOffset], 'Target rows are not one exact finite Float32 coordinate class')
    }
  }
  const offset = request.requestedTriangleIndexOffset
  const total = geometry.index?.count ?? position.count
  const range = geometry.drawRange
  requireCondition(Number.isSafeInteger(range.start) && range.start >= 0 && range.start % 3 === 0
    && (range.count === Infinity || Number.isSafeInteger(range.count) && range.count >= 0 && range.count % 3 === 0), 'Native triangle draw range is invalid or unaligned')
  requireCondition(Number.isSafeInteger(offset) && offset >= range.start && offset % 3 === 0
    && offset + 3 <= Math.min(total, range.start + range.count), 'Requested triangle is outside the active native draw range')
  for (const group of geometry.groups) requireCondition(Number.isSafeInteger(group.start) && group.start >= 0 && group.start % 3 === 0
    && Number.isSafeInteger(group.count) && group.count >= 0 && group.count % 3 === 0, 'Native geometry group is invalid or unaligned')
  let triangleContainsTarget = false
  for (let corner = 0; corner < 3; corner++) {
    const index = geometry.index ? geometry.index.getX(offset + corner) : offset + corner
    requireCondition(Number.isSafeInteger(index) && index >= 0 && index < position.count, 'Requested triangle has an invalid decoded vertex index')
    if (seen.has(index)) triangleContainsTarget = true
  }
  requireCondition(triangleContainsTarget, 'Requested active triangle does not contain the selected coordinate class')
  for (const matrix of [request.object.matrixWorld, request.camera.matrixWorld, request.camera.matrixWorldInverse,
    request.camera.projectionMatrix, request.camera.projectionMatrixInverse]) {
    const determinant = matrix.determinant()
    requireCondition(matrix.elements.every(Number.isFinite) && Number.isFinite(determinant) && determinant !== 0,
      'Native control camera/object matrix is nonfinite or singular')
  }
  const world = request.object.matrixWorld.elements
  requireCondition(world[3] === 0 && world[7] === 0 && world[11] === 0 && world[15] === 1, 'Current native world matrix is not affine')
  return material
}

function clearMeasurement(result: NativeTargetShaderFeedbackResult): void {
  result.status = 'unavailable'
  result.observedClipPositions = null
  result.cpuClipPositions = null
  result.derivedWorldPositions = null
  result.maxObservedClipDelta = null
  result.perVertexClipDelta = null
  result.maxDerivedWorldDeltaMetres = null
  result.perVertexDerivedWorldDeltaMetres = null
  result.derivedDiagnostic = null
}

/**
 * Supported full render of the SAME actual Scene/current camera under rasterizer
 * discard. Its fresh control frame is not a new colour receipt or source epoch.
 * Target feedback is synchronous in the native onAfterRender, before a later mesh
 * can overwrite uniforms in a shared original program. Scene-owned seals see the
 * original callback/background/autoClear references, not our temporary scope.
 */
export function measureNativeTargetShaderFeedback(request: NativeTargetShaderFeedbackRequest): NativeTargetShaderFeedbackResult {
  let result = unavailable('Controlled native submission did not execute')
  let control: NativeTargetControlledSubmission | null = null
  let saved: NativeDiagnosticRendererState | null = null
  let gl: WebGL2RenderingContext | null = null
  let scope: { callback: NativeObject['onAfterRender']; background: THREE.Scene['background']; autoClear: boolean } | null = null
  let sampleAttempted = false
  let failure: string | null = null
  try {
    const material = validateControlRequest(request)
    request.beforeSample()
    const context = request.renderer.getContext()
    requireCondition('createTransformFeedback' in context && typeof context.createTransformFeedback === 'function', 'Native renderer has no WebGL2 transform-feedback support')
    gl = context
    requireNoGlError(gl, 'control entry (a pre-existing error is not ignored)')
    requireCondition(!gl.getParameter(gl.TRANSFORM_FEEDBACK_ACTIVE), 'An existing active or paused transform-feedback session cannot be disturbed')
    for (const target of [gl.ANY_SAMPLES_PASSED, gl.ANY_SAMPLES_PASSED_CONSERVATIVE, gl.TRANSFORM_FEEDBACK_PRIMITIVES_WRITTEN]) {
      requireCondition(gl.getQuery(target, gl.CURRENT_QUERY) === null, 'An existing GPU query would be contaminated by native control')
    }
    const timer = gl.getExtension('EXT_disjoint_timer_query_webgl2') as { TIME_ELAPSED_EXT: number } | null
    requireCondition(!timer || gl.getQuery(timer.TIME_ELAPSED_EXT, gl.CURRENT_QUERY) === null, 'An existing GPU timer query would be contaminated by native control')
    saved = captureNativeDiagnosticRendererState(request.renderer)
    scope = {
      callback: request.object.onAfterRender, background: request.scene.background, autoClear: request.renderer.autoClear,
    }
    const original = scope
    const camera = {
      matrixWorld: Array.from(request.camera.matrixWorld.elements),
      matrixWorldInverse: Array.from(request.camera.matrixWorldInverse.elements),
      projectionMatrix: Array.from(request.camera.projectionMatrix.elements),
    }
    const restoreScope = () => {
      request.object.onAfterRender = original.callback
      request.scene.background = original.background
      request.renderer.autoClear = original.autoClear
    }
    const callback: NativeObject['onAfterRender'] = function (this: NativeObject, renderer, scene, currentCamera, geometry, currentMaterial, group) {
      const receipt = control!
      receipt.targetNativeCallbackCount++
      restoreScope()
      try {
        if (!sampleAttempted) {
          sampleAttempted = true
          requireCondition(this === request.object && renderer === request.renderer && scene === request.scene
            && currentCamera === request.camera && geometry === request.object.geometry && currentMaterial === material,
          'Native callback object/renderer/Scene/camera/geometry/material does not match the requested current target')
          // r180 uses null for a single-material draw, even if geometry.groups is nonempty.
          requireCondition(group === null, 'Single-material native target callback has an unexpected active group')
          requireCondition(gl!.isEnabled(gl!.RASTERIZER_DISCARD) && request.renderer.info.render.frame > receipt.rendererFrameBefore,
            'Target native submission has no fresh rasterizer-discard renderer frame')
          receipt.targetRendererFrame = request.renderer.info.render.frame
          receipt.targetNativeSubmission = { objectUuid: this.uuid, geometryUuid: geometry.uuid, materialUuid: currentMaterial.uuid, group: null }
          for (const [name, expected] of Object.entries(camera)) requireCondition(request.camera[name as keyof typeof camera].elements.every((value, index) => Object.is(value, expected[index])), 'Current native camera changed during control submission')
          request.beforeSample()
          result = measureNativeTargetClipFeedback(request, receipt)
        }
      } catch (error) {
        failure ??= error instanceof Error ? error.message : String(error)
      } finally {
        // Preserve the original callback on every native invocation, including negatives.
        try { original.callback.call(this, renderer, scene, currentCamera, geometry, currentMaterial, group) }
        catch (error) { failure ??= error instanceof Error ? error.message : String(error) }
        request.object.onAfterRender = callback
        request.scene.background = null
        request.renderer.autoClear = false
      }
    }
    control = {
      method: 'current-native-rasterizer-discard-target-control-submission', revision: request.controlSubmissionRevision,
      rendererFrameBefore: request.renderer.info.render.frame, targetRendererFrame: null,
      rendererFrameAfter: request.renderer.info.render.frame, submittedAtPerformanceMs: performance.now(),
      completed: false, targetNativeCallbackCount: 0, transformFeedbackSampled: false, rasterizerDiscard: true, colourRasterized: false,
      completion: 'renderer-render-returned-not-full-scene-gpu-fence',
      associatedColourDraw: { ...request.associatedColourDraw }, camera, targetNativeSubmission: null,
      cleanup: { status: 'restored', failures: [] },
    }
    request.object.onAfterRender = callback
    request.scene.background = null
    request.renderer.autoClear = false
    gl.enable(gl.RASTERIZER_DISCARD)
    requireNoGlError(gl, 'native rasterizer-discard control setup')
    request.renderer.render(request.scene, request.camera)
    control.completed = true
    requireNoGlError(gl, 'supported full native control render')
    requireCondition(!failure, failure ?? 'Native callback failed')
    requireCondition(sampleAttempted && control.targetNativeSubmission !== null, 'Requested target was not submitted by the supported current native render')
  } catch (error) {
    result.reason = error instanceof Error ? error.message : String(error)
    clearMeasurement(result)
  } finally {
    const failures = control?.cleanup.failures ?? []
    const attempt = (action: () => void) => {
      try { action() } catch (error) { failures.push(error instanceof Error ? error.message : String(error)) }
    }
    if (scope) {
      const original = scope
      attempt(() => { request.object.onAfterRender = original.callback })
      attempt(() => { request.scene.background = original.background })
      attempt(() => { request.renderer.autoClear = original.autoClear })
    }
    if (saved) failures.push(...restoreNativeDiagnosticRendererState(request.renderer, saved))
    if (control) {
      control.rendererFrameAfter = request.renderer.info.render.frame
      control.cleanup.status = failures.length === 0 ? 'restored' : 'failed'
      result.controlledSubmission = control
    }
    if (failures.length > 0) {
      clearMeasurement(result)
      result.reason = `Controlled submission cleanup failed: ${failures.join('; ')}`
    }
  }
  return result
}
