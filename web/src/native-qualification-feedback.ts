import type * as THREE from 'three'
import { instrumentNativeVertexShader, nativeTFVaryingNames } from '../native-qualification-contract.mjs'
import type { NativeNumericOutput, NativePresentationInventoryEntry, NativePresentationSubmission, NativeProgramFamily } from './native-qualification-types'

// The observation, uniform upload, synchronous TF transaction and restoration
// follow the executed-shader-feedback.mjs private production capture. This
// version retains actual buffer readbacks, never accepts candidate/CPU inputs,
// and copies additional original spring intermediates in the same epilogue.
type Fields = NativeNumericOutput['fields']
export interface CapturedAttribute {
  name: string
  glType: number
  arraySize: number
  location: number
  components: number
  componentType: number
  normalized: boolean
  stride: number
  offset: number
  divisor: number
  enabled: boolean
  bytes: Uint8Array
}
export interface CapturedUniform {
  name: string
  type: number
  activeArraySize: number
  value: Float32Array | Int32Array | Uint32Array
  bytes: Uint8Array
}
export interface CapturedNativeDraw {
  path: string
  family: NativeProgramFamily
  geometry: THREE.BufferGeometry
  material: THREE.Material
  sources: { vertexShader: string; fragmentShader: string }
  attributes: CapturedAttribute[]
  uniforms: CapturedUniform[]
  indices: Uint32Array
  drawRange: { start: number; count: number; mode: 4 }
  matrixWorld: Float64Array
  modelViewMatrix: Float64Array
  projectionMatrix: Float64Array
  vertexCount: number
  unsupportedInput: string | null
}
export interface CapturedPresentationDraw extends Pick<CapturedNativeDraw, 'geometry' | 'sources' | 'attributes' | 'uniforms' | 'indices' | 'drawRange' | 'vertexCount'> {
  kind: NativePresentationSubmission['kind']
  viewId: string
  phase: NativePresentationSubmission['phase']
  sourceRole: NativePresentationSubmission['sourceRole']
  viewportBackingPixels: NativePresentationSubmission['viewportBackingPixels']
  scissorBackingPixels: NativePresentationSubmission['scissorBackingPixels']
  scissorTest: boolean
  samplerBindings: NativePresentationSubmission['samplerBindings']
}
export interface NativeProgramObserver {
  gl: WebGL2RenderingContext
  begin(key: string): void
  take(key: string): { records: CapturedNativeDraw[]; presentations: CapturedPresentationDraw[]; failures: string[] }
  restore(): void
}
export interface NativeFeedbackExecutor {
  execute(record: CapturedNativeDraw, fields: Fields): { source: string; output: Float32Array }
  dispose(): void
}
const requireValue: (value: unknown, message: string) => asserts value = (value, message) => {
  if (!value) throw new Error(message)
}
const floatUniformTypes = new Set([0x1406, 0x8b50, 0x8b51, 0x8b52, 0x8b5a, 0x8b5b, 0x8b5c, 0x8b65, 0x8b66, 0x8b67, 0x8b68, 0x8b69, 0x8b6a])
const unsignedUniformTypes = new Set([0x1405, 0x8dc6, 0x8dc7, 0x8dc8])
const floatAttributeTypes: ReadonlySet<number> = new Set([0x1406, 0x8b50, 0x8b51, 0x8b52])
const integerVectorUniformTypes: ReadonlySet<number> = new Set([0x8b53, 0x8b54, 0x8b55, 0x8b57, 0x8b58, 0x8b59])
function capturedUniformValue(type: number, actual: unknown): CapturedUniform['value'] {
  const Constructor = floatUniformTypes.has(type) ? Float32Array : unsignedUniformTypes.has(type) ? Uint32Array : Int32Array
  if (actual instanceof Constructor) return actual
  if (typeof actual === 'number' || typeof actual === 'boolean') return Constructor.of(Number(actual))
  return Constructor.from(actual as ArrayLike<number>)
}
function captureUniforms(gl: WebGL2RenderingContext, program: WebGLProgram): CapturedUniform[] {
  const uniforms: CapturedUniform[] = []
  for (let index = 0; index < gl.getProgramParameter(program, gl.ACTIVE_UNIFORMS); index++) {
    const info = gl.getActiveUniform(program, index)
    requireValue(info, 'Submitted active uniform information unavailable')
    for (let element = 0; element < info.size; element++) {
      const name = info.size > 1 ? info.name.replace('[0]', `[${element}]`) : info.name
      const location = gl.getUniformLocation(program, name)
      requireValue(location !== null, `Submitted active uniform has no location: ${name}`)
      const actual: unknown = gl.getUniform(program, location)
      requireValue(actual !== null, `Submitted uniform value unavailable: ${name}`)
      const value = capturedUniformValue(info.type, actual)
      uniforms.push({ name, type: info.type, activeArraySize: info.size, value, bytes: new Uint8Array(value.buffer, value.byteOffset, value.byteLength) })
    }
  }
  return uniforms
}
function submittedFamily(material: THREE.Material, sources: CapturedNativeDraw['sources'], uniforms: CapturedUniform[]): NativeProgramFamily {
  if (uniforms.some(uniform => uniform.name === 'nativePathId')) return 'nativeID'
  if (material.type === 'MeshDistanceMaterial' || /^\s*#define DISTANCE\b/m.test(sources.vertexShader)) return 'distance'
  if (material.type === 'MeshDepthMaterial') return 'depth'
  return 'standard'
}

/** Observe and always forward the real renderer/GL calls; never substitute a draw. */
export function observeNativePrograms(renderer: THREE.WebGLRenderer, paths: Map<THREE.Object3D, string>, observeMaterialDraw: ((material: THREE.Material) => void) | undefined, presentationEntries: ReadonlyMap<THREE.Object3D, NativePresentationInventoryEntry>): NativeProgramObserver {
  const gl = renderer.getContext() as WebGL2RenderingContext
  requireValue(typeof gl.getBufferSubData === 'function', 'Native qualification needs the existing WebGL2 renderer')
  const originalDirect = renderer.renderBufferDirect
  const originalDraws = new Map<string, (...args: number[]) => void>()
  const records = new Map<string, CapturedNativeDraw[]>()
  const failures = new Map<string, string[]>()
  const presentationRecords = new Map<string, CapturedPresentationDraw[]>()
  const presentationFailures = new Map<string, string[]>()
  const sourcesByProgram = new WeakMap<WebGLProgram, CapturedNativeDraw['sources']>()
  const bufferVersions = new WeakMap<WebGLBuffer, number>()
  const bufferBytes = new WeakMap<WebGLBuffer, { version: number; bytes: Uint8Array }>()
  const canonicalIndices = new WeakMap<Uint8Array, Uint32Array>()
  const implicitIndices = new Map<number, Uint32Array>()
  const originalBufferData = gl.bufferData, originalBufferSubData = gl.bufferSubData, originalCopyBufferSubData = gl.copyBufferSubData
  const originalLinkProgram = gl.linkProgram
  gl.linkProgram = function (this: WebGL2RenderingContext, program: WebGLProgram) {
    originalLinkProgram.call(this, program); sourcesByProgram.delete(program)
  }
  let viewKey: string | null = null
  let retainedEpoch: string | null = null
  let activeDraw: { path: string; presentation: NativePresentationInventoryEntry | null; object: THREE.Object3D; geometry: THREE.BufferGeometry; material: THREE.Material; camera: THREE.Camera } | null = null
  let disposed = false
  const bump = (target: number) => {
    const binding = target === gl.ARRAY_BUFFER ? gl.ARRAY_BUFFER_BINDING : target === gl.ELEMENT_ARRAY_BUFFER ? gl.ELEMENT_ARRAY_BUFFER_BINDING : target === gl.COPY_WRITE_BUFFER ? gl.COPY_WRITE_BUFFER_BINDING : null
    if (binding !== null) {
      const buffer = gl.getParameter(binding) as WebGLBuffer | null
      if (buffer) bufferVersions.set(buffer, (bufferVersions.get(buffer) ?? 0) + 1)
    }
  }
  gl.bufferData = function (this: WebGL2RenderingContext, ...args: Parameters<WebGL2RenderingContext['bufferData']>) {
    originalBufferData.apply(this, args)
    bump(args[0])
  } as WebGL2RenderingContext['bufferData']
  gl.bufferSubData = function (this: WebGL2RenderingContext, ...args: Parameters<WebGL2RenderingContext['bufferSubData']>) {
    originalBufferSubData.apply(this, args)
    bump(args[0])
  } as WebGL2RenderingContext['bufferSubData']
  gl.copyBufferSubData = function (this: WebGL2RenderingContext, ...args: Parameters<WebGL2RenderingContext['copyBufferSubData']>) {
    originalCopyBufferSubData.apply(this, args)
    bump(args[1])
  }
  function readBuffer(buffer: WebGLBuffer): Uint8Array {
    const version = bufferVersions.get(buffer) ?? 0
    const cached = bufferBytes.get(buffer)
    if (cached?.version === version) return cached.bytes
    const previous = gl.getParameter(gl.COPY_READ_BUFFER_BINDING) as WebGLBuffer | null
    try {
      gl.bindBuffer(gl.COPY_READ_BUFFER, buffer)
      const bytes = new Uint8Array(gl.getBufferParameter(gl.COPY_READ_BUFFER, gl.BUFFER_SIZE) as number)
      gl.getBufferSubData(gl.COPY_READ_BUFFER, 0, bytes)
      bufferBytes.set(buffer, { version, bytes })
      return bytes
    } finally { gl.bindBuffer(gl.COPY_READ_BUFFER, previous) }
  }
  renderer.renderBufferDirect = function (camera, scene, geometry, material, object, group) {
    const previous = activeDraw, path = paths.get(object), presentation = presentationEntries.get(object) ?? null
    activeDraw = viewKey && (path || presentation) ? { path: path ?? '', presentation, object, geometry, material, camera } : null
    try { return originalDirect.call(this, camera, scene, geometry, material, object, group) }
    finally { activeDraw = previous }
  }
  const mutableGL = gl as unknown as Record<string, (...args: number[]) => void>
  for (const name of ['drawElements', 'drawArrays', 'drawElementsInstanced', 'drawArraysInstanced']) {
    const original = mutableGL[name]!
    originalDraws.set(name, original)
    mutableGL[name] = function (this: WebGL2RenderingContext, ...args: number[]) {
      if (activeDraw && viewKey) {
        try {
          const program = gl.getParameter(gl.CURRENT_PROGRAM) as WebGLProgram | null
          requireValue(program, `Native draw has no current program: ${activeDraw.path}`)
          let sources = sourcesByProgram.get(program)
          if (!sources) {
            let vertexShader: string | null = null, fragmentShader: string | null = null
            for (const shader of gl.getAttachedShaders(program) ?? []) {
              const source = gl.getShaderSource(shader)
              if (gl.getShaderParameter(shader, gl.SHADER_TYPE) === gl.VERTEX_SHADER) vertexShader = source
              else fragmentShader = source
            }
            requireValue(vertexShader && fragmentShader, 'Attached original shader sources unavailable')
            sources = { vertexShader, fragmentShader }
            sourcesByProgram.set(program, sources)
          }
          const attributes: CapturedAttribute[] = []
          let unsupportedInput: string | null = null
          for (let index = 0; index < gl.getProgramParameter(program, gl.ACTIVE_ATTRIBUTES); index++) {
            const info = gl.getActiveAttrib(program, index)
            requireValue(info, 'Submitted attribute information unavailable')
            const location = gl.getAttribLocation(program, info.name)
            requireValue(location >= 0, `Submitted attribute inactive: ${info.name}`)
            const enabled = Boolean(gl.getVertexAttrib(location, gl.VERTEX_ATTRIB_ARRAY_ENABLED))
            const buffer = gl.getVertexAttrib(location, gl.VERTEX_ATTRIB_ARRAY_BUFFER_BINDING) as WebGLBuffer | null
            const bytes = enabled && buffer ? readBuffer(buffer) : new Uint8Array(Float32Array.from(gl.getVertexAttrib(location, gl.CURRENT_VERTEX_ATTRIB) as Float32Array).buffer)
            const attribute: CapturedAttribute = { name: info.name, glType: info.type, arraySize: info.size, location, enabled, bytes,
              components: gl.getVertexAttrib(location, gl.VERTEX_ATTRIB_ARRAY_SIZE) as number,
              componentType: gl.getVertexAttrib(location, gl.VERTEX_ATTRIB_ARRAY_TYPE) as number,
              normalized: Boolean(gl.getVertexAttrib(location, gl.VERTEX_ATTRIB_ARRAY_NORMALIZED)),
              stride: gl.getVertexAttrib(location, gl.VERTEX_ATTRIB_ARRAY_STRIDE) as number,
              offset: gl.getVertexAttribOffset(location, gl.VERTEX_ATTRIB_ARRAY_POINTER),
              divisor: gl.getVertexAttrib(location, gl.VERTEX_ATTRIB_ARRAY_DIVISOR) as number }
            if (!enabled || !buffer || attribute.divisor !== 0 || info.size !== 1 || !floatAttributeTypes.has(info.type)) unsupportedInput = `Uncaptured/non-vertex-array replica input: ${info.name}`
            attributes.push(attribute)
          }
          const uniforms = captureUniforms(gl, program), position = activeDraw.geometry.getAttribute('position')
          requireValue(position, 'Actual native geometry has no position input')
          const elementBuffer = gl.getParameter(gl.ELEMENT_ARRAY_BUFFER_BINDING) as WebGLBuffer | null
          let indices: Uint32Array, start: number, count: number
          requireValue(args[0] === gl.TRIANGLES, 'Native primitive did not submit triangles')
          if (name === 'drawElements' || name === 'drawElementsInstanced') {
            requireValue(elementBuffer, 'Indexed native submission has no actual element buffer')
            const bytes = readBuffer(elementBuffer), type = args[2]!
            const size = type === gl.UNSIGNED_INT ? 4 : type === gl.UNSIGNED_SHORT ? 2 : type === gl.UNSIGNED_BYTE ? 1 : 0
            requireValue(size && bytes.byteLength % size === 0 && args[3]! % size === 0, 'Unsupported actual index representation')
            let canonical = canonicalIndices.get(bytes)
            if (!canonical) {
              const source = type === gl.UNSIGNED_INT ? new Uint32Array(bytes.buffer, bytes.byteOffset, bytes.byteLength / size) : type === gl.UNSIGNED_SHORT ? new Uint16Array(bytes.buffer, bytes.byteOffset, bytes.byteLength / size) : bytes
              canonical = Uint32Array.from(source); canonicalIndices.set(bytes, canonical)
            }
            indices = canonical
            start = args[3]! / size; count = args[1]!
          } else {
            // A real drawArrays submission has the implicit ordered vertex indices.
            let implicit = implicitIndices.get(position.count)
            if (!implicit) { implicit = Uint32Array.from({ length: position.count }, (_, index) => index); implicitIndices.set(position.count, implicit) }
            indices = implicit
            start = args[1]!; count = args[2]!
          }
          if (name.endsWith('Instanced')) unsupportedInput = 'Instanced draw requires separately captured instance inputs'
          requireValue(start >= 0 && count >= 0 && start + count <= indices.length, 'Actual native draw range exceeds its index buffer')
          if (activeDraw.presentation) {
            const entry = activeDraw.presentation, samplerBindings: CapturedPresentationDraw['samplerBindings'] = []
            const previousUnit = gl.getParameter(gl.ACTIVE_TEXTURE) as number
            try {
              for (const uniform of uniforms) {
                if (uniform.type !== gl.SAMPLER_2D) continue
                const unit = uniform.value[0]!
                const texture = uniform.name === 'image' ? entry.inputTexture : null
                gl.activeTexture(gl.TEXTURE0 + unit)
                const bound = gl.getParameter(gl.TEXTURE_BINDING_2D) as WebGLTexture | null
                const properties: unknown = texture ? renderer.properties.get(texture) : null
                const installed = properties && typeof properties === 'object' && '__webglTexture' in properties ? properties.__webglTexture : undefined
                samplerBindings.push({ uniform: uniform.name, unit, boundMatchesMaterialTexture: texture && installed ? bound === installed : null, textureUUID: texture?.uuid ?? null, textureVersion: texture?.version ?? null })
              }
            } finally { gl.activeTexture(previousUnit) }
            const rows = presentationRecords.get(viewKey) ?? []
            rows.push({ kind: entry.kind, viewId: viewKey.slice(viewKey.indexOf(':') + 1), phase: entry.phase, sourceRole: entry.sourceRole,
              geometry: activeDraw.geometry, sources, attributes, uniforms, indices, drawRange: { start, count, mode: 4 }, vertexCount: position.count,
              viewportBackingPixels: Array.from(gl.getParameter(gl.VIEWPORT) as Int32Array) as [number, number, number, number],
              scissorBackingPixels: Array.from(gl.getParameter(gl.SCISSOR_BOX) as Int32Array) as [number, number, number, number], scissorTest: gl.isEnabled(gl.SCISSOR_TEST), samplerBindings })
            presentationRecords.set(viewKey, rows)
          } else {
            const record: CapturedNativeDraw = { ...activeDraw, sources, attributes, uniforms, indices, drawRange: { start, count, mode: 4 },
              family: submittedFamily(activeDraw.material, sources, uniforms),
              matrixWorld: Float64Array.from(activeDraw.object.matrixWorld.elements), modelViewMatrix: Float64Array.from(activeDraw.object.modelViewMatrix.elements),
              projectionMatrix: Float64Array.from(activeDraw.camera.projectionMatrix.elements), vertexCount: position.count, unsupportedInput }
            if (record.family === 'standard') observeMaterialDraw?.(record.material)
            const rows = records.get(viewKey) ?? []
            rows.push(record); records.set(viewKey, rows)
          }
        } catch (error) {
          if (activeDraw.presentation) {
            const rows = presentationFailures.get(viewKey) ?? []
            rows.push(`${activeDraw.presentation.kind}: ${error instanceof Error ? error.message : String(error)}`); presentationFailures.set(viewKey, rows)
          } else {
            const rows = failures.get(viewKey) ?? []
            rows.push(`${activeDraw.path}: ${error instanceof Error ? error.message : String(error)}`); failures.set(viewKey, rows)
          }
        }
      }
      return original.apply(this, args)
    }
  }
  return { gl, begin(key: string) {
    requireValue(!disposed, 'Native observer disposed')
    const epoch = key.slice(0, key.indexOf(':'))
    if (epoch !== retainedEpoch) { records.clear(); failures.clear(); presentationRecords.clear(); presentationFailures.clear(); retainedEpoch = epoch }
    viewKey = key; records.set(key, []); failures.set(key, []); presentationRecords.set(key, []); presentationFailures.set(key, [])
  },
    take(key: string) {
      const result = { records: records.get(key) ?? [], presentations: presentationRecords.get(key) ?? [], failures: [...(failures.get(key) ?? []), ...(presentationFailures.get(key) ?? [])] }
      records.delete(key); failures.delete(key); presentationRecords.delete(key); presentationFailures.delete(key); return result
    },
    restore() {
      if (disposed) return
      disposed = true; viewKey = null; records.clear(); failures.clear(); presentationRecords.clear(); presentationFailures.clear()
      renderer.renderBufferDirect = originalDirect
      for (const [name, original] of originalDraws) mutableGL[name] = original
      gl.bufferData = originalBufferData; gl.bufferSubData = originalBufferSubData; gl.copyBufferSubData = originalCopyBufferSubData
      gl.linkProgram = originalLinkProgram
    } }
}

function uploadUniform(gl: WebGL2RenderingContext, program: WebGLProgram, uniform: CapturedUniform): void {
  const location = gl.getUniformLocation(program, uniform.name)
  if (location === null) return
  const type = uniform.type
  // captureUniforms normalizes original getUniform readbacks by this GL type.
  // Reuse those immutable typed values: no copy, candidate or CPU provider.
  const floats = uniform.value as Float32Array, ints = uniform.value as Int32Array, uints = uniform.value as Uint32Array
  if (type === gl.FLOAT) gl.uniform1fv(location, floats)
  else if (type === gl.FLOAT_VEC2) gl.uniform2fv(location, floats)
  else if (type === gl.FLOAT_VEC3) gl.uniform3fv(location, floats)
  else if (type === gl.FLOAT_VEC4) gl.uniform4fv(location, floats)
  else if (type === gl.FLOAT_MAT2) gl.uniformMatrix2fv(location, false, floats)
  else if (type === gl.FLOAT_MAT3) gl.uniformMatrix3fv(location, false, floats)
  else if (type === gl.FLOAT_MAT4) gl.uniformMatrix4fv(location, false, floats)
  else if (type === gl.FLOAT_MAT2x3) gl.uniformMatrix2x3fv(location, false, floats)
  else if (type === gl.FLOAT_MAT2x4) gl.uniformMatrix2x4fv(location, false, floats)
  else if (type === gl.FLOAT_MAT3x2) gl.uniformMatrix3x2fv(location, false, floats)
  else if (type === gl.FLOAT_MAT3x4) gl.uniformMatrix3x4fv(location, false, floats)
  else if (type === gl.FLOAT_MAT4x2) gl.uniformMatrix4x2fv(location, false, floats)
  else if (type === gl.FLOAT_MAT4x3) gl.uniformMatrix4x3fv(location, false, floats)
  else if (type === gl.INT || type === gl.BOOL || (!floatUniformTypes.has(type) && !unsignedUniformTypes.has(type) && !integerVectorUniformTypes.has(type))) gl.uniform1iv(location, ints)
  else if (type === gl.INT_VEC2 || type === gl.BOOL_VEC2) gl.uniform2iv(location, ints)
  else if (type === gl.INT_VEC3 || type === gl.BOOL_VEC3) gl.uniform3iv(location, ints)
  else if (type === gl.INT_VEC4 || type === gl.BOOL_VEC4) gl.uniform4iv(location, ints)
  else if (type === gl.UNSIGNED_INT) gl.uniform1uiv(location, uints)
  else if (type === gl.UNSIGNED_INT_VEC2) gl.uniform2uiv(location, uints)
  else if (type === gl.UNSIGNED_INT_VEC3) gl.uniform3uiv(location, uints)
  else if (type === gl.UNSIGNED_INT_VEC4) gl.uniform4uiv(location, uints)
  else throw new Error(`Unsupported original active uniform ${uniform.name}/${type}`)
}

/** Persistent replicas contain no numerical replacement or invented input. */
export function createNativeFeedbackExecutor(gl: WebGL2RenderingContext): NativeFeedbackExecutor {
  const replicas = new Map<string, { program: WebGLProgram; shaders: WebGLShader[]; source: string }>()
  const inputBuffers = new WeakMap<Uint8Array, WebGLBuffer>()
  const allocatedInputs = new Set<WebGLBuffer>()
  const reusableVAO = gl.createVertexArray(), reusableFeedback = gl.createTransformFeedback(), reusableOutput = gl.createBuffer()
  if (!reusableVAO || !reusableFeedback || !reusableOutput) {
    gl.deleteVertexArray(reusableVAO); gl.deleteTransformFeedback(reusableFeedback); gl.deleteBuffer(reusableOutput)
  }
  requireValue(reusableVAO && reusableFeedback && reusableOutput, 'Native feedback reusable resources unavailable')
  let outputCapacity = 0
  function replica(record: CapturedNativeDraw, fields: Fields) {
    const source = instrumentNativeVertexShader(record.sources.vertexShader, fields)
    const key = `${source}\n---native-fragment---\n${record.sources.fragmentShader}`
    const cached = replicas.get(key)
    if (cached) return cached
    const shaders: WebGLShader[] = [], program = gl.createProgram()
    requireValue(program, 'Native feedback program allocation failed')
    try {
      for (const [type, text] of [[gl.VERTEX_SHADER, source], [gl.FRAGMENT_SHADER, record.sources.fragmentShader]] as const) {
        const shader = gl.createShader(type); requireValue(shader, 'Native feedback shader allocation failed'); shaders.push(shader)
        gl.shaderSource(shader, text); gl.compileShader(shader)
        requireValue(gl.getShaderParameter(shader, gl.COMPILE_STATUS), `Original epilogue replica compile failed: ${gl.getShaderInfoLog(shader)}`)
        gl.attachShader(program, shader)
      }
      gl.transformFeedbackVaryings(program, fields.map(field => nativeTFVaryingNames[field.name]), gl.INTERLEAVED_ATTRIBS); gl.linkProgram(program)
      requireValue(gl.getProgramParameter(program, gl.LINK_STATUS), `Original epilogue replica link failed: ${gl.getProgramInfoLog(program)}`)
      const result = { program, shaders, source }; replicas.set(key, result); return result
    } catch (error) { gl.deleteProgram(program); for (const shader of shaders) gl.deleteShader(shader); throw error }
  }
  return {
    execute(record: CapturedNativeDraw, fields: Fields): { source: string; output: Float32Array } {
      requireValue(!gl.isContextLost(), 'Native feedback context lost')
      requireValue(!gl.getParameter(gl.TRANSFORM_FEEDBACK_ACTIVE), 'Original renderer transform feedback is active')
      if (record.unsupportedInput) throw new Error(record.unsupportedInput)
      // Vertex texture fetches need authentic texture/sampler readbacks as well.
      // Capturing a sampler's integer alone is not its original input closure.
      if (/^\s*#define (?:USE_DISPLACEMENTMAP|USE_SKINNING|USE_MORPHTARGETS)\b/m.test(record.sources.vertexShader)) throw new Error('Uncaptured original vertex texture input')
      for (const uniform of record.uniforms) {
        const name = uniform.name.replace(/\[.*$/, '').replace(/[.*+?^${}()|[\]\\]/g, '\\$&')
        if (new RegExp(`\\buniform\\s+(?:(?:lowp|mediump|highp)\\s+)?[iu]?sampler\\w+\\s+${name}\\b`).test(record.sources.vertexShader)) throw new Error(`Uncaptured original vertex texture input: ${uniform.name}`)
      }
      const compiled = replica(record, fields), captured = new Map(record.uniforms.map(uniform => [uniform.name, uniform]))
      for (let index = 0; index < gl.getProgramParameter(compiled.program, gl.ACTIVE_UNIFORMS); index++) {
        const info = gl.getActiveUniform(compiled.program, index); requireValue(info, 'Replica uniform information unavailable')
        for (let element = 0; element < info.size; element++) {
          const name = info.size > 1 ? info.name.replace('[0]', `[${element}]`) : info.name, actual = captured.get(name)
          if (!actual || actual.type !== info.type || actual.activeArraySize < info.size) throw new Error(`Uncaptured replica uniform: ${name}`)
        }
      }
      const inputs = new Map(record.attributes.map(attribute => [attribute.name, attribute]))
      for (let index = 0; index < gl.getProgramParameter(compiled.program, gl.ACTIVE_ATTRIBUTES); index++) {
        const info = gl.getActiveAttrib(compiled.program, index); requireValue(info, 'Replica attribute information unavailable')
        const actual = inputs.get(info.name)
        if (!actual || !actual.enabled || actual.glType !== info.type || actual.arraySize !== info.size) throw new Error(`Uncaptured replica attribute: ${info.name}`)
      }
      const previous = { program: gl.getParameter(gl.CURRENT_PROGRAM) as WebGLProgram | null, vao: gl.getParameter(gl.VERTEX_ARRAY_BINDING) as WebGLVertexArrayObject | null,
        array: gl.getParameter(gl.ARRAY_BUFFER_BINDING) as WebGLBuffer | null, feedback: gl.getParameter(gl.TRANSFORM_FEEDBACK_BINDING) as WebGLTransformFeedback | null,
        feedbackBuffer: gl.getParameter(gl.TRANSFORM_FEEDBACK_BUFFER_BINDING) as WebGLBuffer | null, discard: gl.isEnabled(gl.RASTERIZER_DISCARD) }
      const vao = reusableVAO, feedback = reusableFeedback
      let active = false
      try {
        requireValue(vao && feedback, 'Native feedback state allocation failed')
        gl.useProgram(compiled.program); gl.bindVertexArray(vao)
        for (const attribute of record.attributes) {
          const location = gl.getAttribLocation(compiled.program, attribute.name)
          if (location < 0) continue
          let buffer = inputBuffers.get(attribute.bytes)
          if (!buffer) {
            buffer = gl.createBuffer() ?? undefined; requireValue(buffer, 'Native feedback input allocation failed'); allocatedInputs.add(buffer)
            gl.bindBuffer(gl.ARRAY_BUFFER, buffer); gl.bufferData(gl.ARRAY_BUFFER, attribute.bytes, gl.STATIC_DRAW); inputBuffers.set(attribute.bytes, buffer)
          } else gl.bindBuffer(gl.ARRAY_BUFFER, buffer)
          gl.enableVertexAttribArray(location); gl.vertexAttribPointer(location, attribute.components, attribute.componentType, attribute.normalized, attribute.stride, attribute.offset)
        }
        for (const uniform of record.uniforms) uploadUniform(gl, compiled.program, uniform)
        const stride = fields.reduce((sum, field) => sum + field.components, 0), outputBuffer = reusableOutput
        gl.bindTransformFeedback(gl.TRANSFORM_FEEDBACK, feedback); gl.bindBuffer(gl.TRANSFORM_FEEDBACK_BUFFER, outputBuffer)
        const requiredBytes = record.vertexCount * stride * 4
        if (requiredBytes > outputCapacity) { gl.bufferData(gl.TRANSFORM_FEEDBACK_BUFFER, requiredBytes, gl.STREAM_READ); outputCapacity = requiredBytes }
        gl.bindBufferBase(gl.TRANSFORM_FEEDBACK_BUFFER, 0, outputBuffer); gl.enable(gl.RASTERIZER_DISCARD)
        gl.beginTransformFeedback(gl.POINTS); active = true; gl.drawArrays(gl.POINTS, 0, record.vertexCount); gl.endTransformFeedback(); active = false
        const output = new Float32Array(record.vertexCount * stride)
        gl.getBufferSubData(gl.TRANSFORM_FEEDBACK_BUFFER, 0, output)
        requireValue(!gl.isContextLost() && gl.getError() === gl.NO_ERROR, 'Native feedback GL readback failed')
        return { source: compiled.source, output }
      } finally {
        if (active) gl.endTransformFeedback()
        gl.bindTransformFeedback(gl.TRANSFORM_FEEDBACK, previous.feedback)
        gl.bindVertexArray(previous.vao); gl.bindBuffer(gl.ARRAY_BUFFER, previous.array)
        gl.bindBuffer(gl.TRANSFORM_FEEDBACK_BUFFER, previous.feedbackBuffer); gl.useProgram(previous.program)
        if (previous.discard) gl.enable(gl.RASTERIZER_DISCARD); else gl.disable(gl.RASTERIZER_DISCARD)
      }
    },
    dispose() {
      for (const { program, shaders } of replicas.values()) { gl.deleteProgram(program); for (const shader of shaders) gl.deleteShader(shader) }
      replicas.clear()
      for (const buffer of allocatedInputs) gl.deleteBuffer(buffer)
      allocatedInputs.clear(); gl.deleteBuffer(reusableOutput); gl.deleteTransformFeedback(reusableFeedback); gl.deleteVertexArray(reusableVAO)
    },
  }
}
