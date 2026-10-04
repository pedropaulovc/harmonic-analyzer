import * as THREE from 'three'
import { canonicalJson } from '../native-qualification-contract.mjs'
import type { NativeByteSpan } from './native-qualification-types'

/** Original material metadata and GPU storage, never a qualification verdict. */
export interface NativeMaterialByteSink {
  put(bytes: Uint8Array, options: { retention: 'static' }): Promise<{ sha256: string; byteLength: number }>
}
export interface NativeMaterialCapture {
  /** Called immediately before the real standard draw; does not replace it. */
  observeDraw(material: THREE.Material): void
  capture(material: THREE.Material, sink: NativeMaterialByteSink): Promise<string>
  dispose(): void
}
const propertyNames = [
  'side', 'shadowSide', 'transparent', 'opacity', 'alphaTest', 'alphaHash', 'alphaToCoverage',
  'depthTest', 'depthWrite', 'depthFunc', 'colorWrite', 'blending', 'blendSrc', 'blendDst',
  'blendEquation', 'blendSrcAlpha', 'blendDstAlpha', 'blendEquationAlpha', 'blendAlpha', 'blendColor',
  'premultipliedAlpha', 'polygonOffset', 'polygonOffsetFactor', 'polygonOffsetUnits', 'clipIntersection',
  'clipShadows', 'vertexColors', 'flatShading', 'wireframe', 'wireframeLinewidth', 'roughness', 'metalness',
  'emissiveIntensity', 'toneMapped', 'visible', 'forceSinglePass', 'dithering', 'stencilWrite',
  'stencilWriteMask', 'stencilFunc', 'stencilRef', 'stencilFuncMask', 'stencilFail', 'stencilZFail',
  'stencilZPass', 'color', 'emissive', 'specular', 'normalScale', 'aoMapIntensity', 'lightMapIntensity',
  'bumpScale', 'displacementScale', 'displacementBias', 'normalMapType', 'envMapIntensity',
  'reflectivity', 'refractionRatio', 'clearcoat', 'clearcoatRoughness', 'clearcoatNormalScale',
  'ior', 'transmission', 'thickness', 'attenuationDistance', 'attenuationColor', 'specularIntensity',
  'specularColor', 'sheen', 'sheenColor', 'sheenRoughness', 'iridescence', 'iridescenceIOR',
  'iridescenceThicknessRange', 'anisotropy', 'anisotropyRotation', 'dispersion',
] as const
const textureSlots = [
  'map', 'alphaMap', 'normalMap', 'roughnessMap', 'metalnessMap', 'emissiveMap', 'aoMap', 'lightMap',
  'bumpMap', 'displacementMap', 'envMap', 'clearcoatMap', 'clearcoatRoughnessMap', 'clearcoatNormalMap',
  'transmissionMap', 'thicknessMap', 'specularIntensityMap', 'specularColorMap', 'sheenColorMap',
  'sheenRoughnessMap', 'iridescenceMap', 'iridescenceThicknessMap', 'anisotropyMap',
] as const
function valueSnapshot(value: unknown): unknown {
  if (value === Infinity) return 'positive-infinity'
  if (value === -Infinity || typeof value === 'number' && !Number.isFinite(value)) throw new Error('Nonfinite original material property')
  if (value && typeof value === 'object') {
    const object = value as { isColor?: boolean; r?: number; g?: number; b?: number; toArray?: () => number[] }
    if (object.isColor) return [object.r, object.g, object.b]
    if (object.toArray) return object.toArray()
    if (Array.isArray(value)) return [...value]
  }
  return value
}
type Binding = { authority: 'actual-original-draw-sampler' | 'renderer-installed-texture'; uniform: string | null; unit: number | null; boundMatchesTexture: boolean | null }
type Sampler = { wrapS: number; wrapT: number; minFilter: number; magFilter: number; baseLevel: number; maxLevel: number; compareMode: number; compareFunc: number }
type Unmeasured = { authority: 'unmeasured-original-gpu-texture'; reason: string }
type GpuSource = { authority: 'original-renderer-gpu-texture-level0'; width: number; height: number; encoding: 'rgba8'; origin: 'texture-row0'; bytes: Uint8Array; sampler: Sampler; binding: Binding; format: number; type: number; internalFormat: string | null; premultiplyAlpha: boolean; unpackAlignment: number }
type TextureRecord = { slot: string; wrapS: number; wrapT: number; minFilter: number; magFilter: number; flipY: boolean; colorSpace: string; channel: number; offset: number[]; repeat: number[]; center: number[]; rotation: number; matrix: number[]; source: GpuSource | Unmeasured }
type MaterialRecord = { schemaVersion: 1; type: string; name: string; properties: Record<string, unknown>; clippingPlanes: number[][]; textures: TextureRecord[] }
const insist: (condition: unknown, message: string) => asserts condition = (condition, message) => { if (!condition) throw new Error(message) }

/**
 * Construct before the draw observer. No image decode, canvas surrogate or
 * renderer.initTexture is used. readPixels addresses the original renderer's
 * installed texture, and textureSize in a tiny GPU TF query measures its actual
 * level-zero dimensions. All touched GL bindings and pixel-pack state are
 * restored directly; Three's cached state therefore still describes reality.
 * Static storage is read once per actual GPU mutation and uploaded once per CAS.
 */
export function createNativeMaterialCapture(renderer: THREE.WebGLRenderer): NativeMaterialCapture {
  const gl = renderer.getContext() as WebGL2RenderingContext
  insist(typeof gl.getBufferSubData === 'function', 'Original material capture needs WebGL2')
  const drawArrays = gl.drawArrays
  const versions = new WeakMap<WebGLTexture, number>()
  const cached = new WeakMap<WebGLTexture, { key: string; width: number; height: number; bytes: Uint8Array }>()
  const snapshots = new WeakMap<THREE.Material, MaterialRecord>()
  const uploads = new WeakMap<NativeMaterialByteSink, Map<string, Promise<string>>>()
  const byteHashes = new WeakMap<Uint8Array, Promise<string>>()
  const mutationOriginals = new Map<string, (...args: unknown[]) => unknown>()
  const mutable = gl as unknown as Record<string, (...args: unknown[]) => unknown>
  let disposed = false
  let resources: { program: WebGLProgram; shaders: WebGLShader[]; vao: WebGLVertexArrayObject; feedback: WebGLTransformFeedback; buffer: WebGLBuffer; framebuffer: WebGLFramebuffer } | null = null
  for (const name of ['texImage2D', 'texSubImage2D', 'compressedTexImage2D', 'compressedTexSubImage2D', 'copyTexImage2D', 'copyTexSubImage2D', 'texStorage2D', 'generateMipmap', 'texParameteri', 'texParameterf']) {
    const original = mutable[name]!
    mutationOriginals.set(name, original)
    mutable[name] = function (...args: unknown[]) {
      const result = original.apply(this, args)
      const target = Number(args[0])
      const binding = target === gl.TEXTURE_2D ? gl.TEXTURE_BINDING_2D : target === gl.TEXTURE_CUBE_MAP || target >= gl.TEXTURE_CUBE_MAP_POSITIVE_X && target <= gl.TEXTURE_CUBE_MAP_NEGATIVE_Z ? gl.TEXTURE_BINDING_CUBE_MAP : null
      if (binding !== null) {
        const texture = gl.getParameter(binding) as WebGLTexture | null
        if (texture) versions.set(texture, (versions.get(texture) ?? 0) + 1)
      }
      return result
    }
  }
  function ensureResources() {
    if (resources) return resources
    const program = gl.createProgram(), vao = gl.createVertexArray(), feedback = gl.createTransformFeedback(), buffer = gl.createBuffer(), framebuffer = gl.createFramebuffer(), shaders: WebGLShader[] = []
    try {
      insist(program && vao && feedback && buffer && framebuffer, 'GPU material query resources unavailable')
      for (const [type, source] of [
        [gl.VERTEX_SHADER, '#version 300 es\nprecision highp float; precision highp int; uniform highp sampler2D originalTexture; flat out ivec2 nativeTextureDimensions; void main(){ nativeTextureDimensions=textureSize(originalTexture,0); gl_Position=vec4(0.0,0.0,0.0,1.0); }'],
        [gl.FRAGMENT_SHADER, '#version 300 es\nprecision highp float; out vec4 color; void main(){color=vec4(0.0);}'],
      ] as const) {
        const shader = gl.createShader(type); insist(shader, 'GPU texture dimension shader unavailable'); shaders.push(shader)
        gl.shaderSource(shader, source); gl.compileShader(shader)
        insist(gl.getShaderParameter(shader, gl.COMPILE_STATUS), `GPU dimension query compile failed: ${gl.getShaderInfoLog(shader)}`)
        gl.attachShader(program, shader)
      }
      gl.transformFeedbackVaryings(program, ['nativeTextureDimensions'], gl.INTERLEAVED_ATTRIBS); gl.linkProgram(program)
      insist(gl.getProgramParameter(program, gl.LINK_STATUS), `GPU dimension query link failed: ${gl.getProgramInfoLog(program)}`)
      resources = { program, shaders, vao, feedback, buffer, framebuffer }; return resources
    } catch (error) {
      if (program) gl.deleteProgram(program)
      for (const shader of shaders) gl.deleteShader(shader)
      if (vao) gl.deleteVertexArray(vao)
      if (feedback) gl.deleteTransformFeedback(feedback)
      if (buffer) gl.deleteBuffer(buffer)
      if (framebuffer) gl.deleteFramebuffer(framebuffer)
      throw error
    }
  }
  function dimensions(unit: number): [number, number] {
    insist(!gl.getParameter(gl.TRANSFORM_FEEDBACK_ACTIVE), 'Original transform feedback active during material capture')
    const own = ensureResources(), previous = {
      program: gl.getParameter(gl.CURRENT_PROGRAM) as WebGLProgram | null,
      vao: gl.getParameter(gl.VERTEX_ARRAY_BINDING) as WebGLVertexArrayObject | null,
      feedback: gl.getParameter(gl.TRANSFORM_FEEDBACK_BINDING) as WebGLTransformFeedback | null,
      buffer: gl.getParameter(gl.TRANSFORM_FEEDBACK_BUFFER_BINDING) as WebGLBuffer | null,
      discard: gl.isEnabled(gl.RASTERIZER_DISCARD),
    }
    let active = false
    try {
      gl.useProgram(own.program); gl.bindVertexArray(own.vao); gl.bindTransformFeedback(gl.TRANSFORM_FEEDBACK, own.feedback)
      gl.bindBuffer(gl.TRANSFORM_FEEDBACK_BUFFER, own.buffer); gl.bufferData(gl.TRANSFORM_FEEDBACK_BUFFER, 8, gl.STREAM_READ)
      gl.bindBufferBase(gl.TRANSFORM_FEEDBACK_BUFFER, 0, own.buffer)
      gl.uniform1i(gl.getUniformLocation(own.program, 'originalTexture'), unit); gl.enable(gl.RASTERIZER_DISCARD)
      gl.beginTransformFeedback(gl.POINTS); active = true; drawArrays.call(gl, gl.POINTS, 0, 1); gl.endTransformFeedback(); active = false
      const result = new Int32Array(2); gl.getBufferSubData(gl.TRANSFORM_FEEDBACK_BUFFER, 0, result)
      insist(gl.getError() === gl.NO_ERROR, 'Original GPU texture dimension query failed')
      insist(result[0]! > 0 && result[1]! > 0, 'Original GPU texture level-zero dimensions unavailable')
      return [result[0]!, result[1]!]
    } finally {
      if (active) gl.endTransformFeedback()
      gl.bindTransformFeedback(gl.TRANSFORM_FEEDBACK, previous.feedback); gl.bindBuffer(gl.TRANSFORM_FEEDBACK_BUFFER, previous.buffer)
      gl.bindVertexArray(previous.vao); gl.useProgram(previous.program)
      if (previous.discard) gl.enable(gl.RASTERIZER_DISCARD); else gl.disable(gl.RASTERIZER_DISCARD)
    }
  }
  function pixels(width: number, height: number, texture: WebGLTexture): Uint8Array {
    const own = ensureResources(), previous = {
      framebuffer: gl.getParameter(gl.READ_FRAMEBUFFER_BINDING) as WebGLFramebuffer | null,
      pack: gl.getParameter(gl.PIXEL_PACK_BUFFER_BINDING) as WebGLBuffer | null,
      alignment: gl.getParameter(gl.PACK_ALIGNMENT) as number,
      rowLength: gl.getParameter(gl.PACK_ROW_LENGTH) as number,
      skipPixels: gl.getParameter(gl.PACK_SKIP_PIXELS) as number,
      skipRows: gl.getParameter(gl.PACK_SKIP_ROWS) as number,
    }
    try {
      gl.bindFramebuffer(gl.READ_FRAMEBUFFER, own.framebuffer)
      gl.framebufferTexture2D(gl.READ_FRAMEBUFFER, gl.COLOR_ATTACHMENT0, gl.TEXTURE_2D, texture, 0)
      insist(gl.checkFramebufferStatus(gl.READ_FRAMEBUFFER) === gl.FRAMEBUFFER_COMPLETE, 'Original texture is not directly RGBA8-readable')
      insist(gl.getFramebufferAttachmentParameter(gl.READ_FRAMEBUFFER, gl.COLOR_ATTACHMENT0, gl.FRAMEBUFFER_ATTACHMENT_COMPONENT_TYPE) === gl.UNSIGNED_NORMALIZED, 'Original texture is not unsigned-normalized RGBA storage')
      gl.readBuffer(gl.COLOR_ATTACHMENT0); gl.bindBuffer(gl.PIXEL_PACK_BUFFER, null)
      gl.pixelStorei(gl.PACK_ALIGNMENT, 1); gl.pixelStorei(gl.PACK_ROW_LENGTH, 0); gl.pixelStorei(gl.PACK_SKIP_PIXELS, 0); gl.pixelStorei(gl.PACK_SKIP_ROWS, 0)
      const length = width * height * 4; insist(Number.isSafeInteger(length), 'GPU texture byte count exceeds safe storage')
      const bytes = new Uint8Array(length); gl.readPixels(0, 0, width, height, gl.RGBA, gl.UNSIGNED_BYTE, bytes)
      insist(gl.getError() === gl.NO_ERROR, 'Original GPU texture readPixels failed')
      insist(!gl.isContextLost(), 'Original texture GPU readback lost context')
      return bytes
    } finally {
      gl.framebufferTexture2D(gl.READ_FRAMEBUFFER, gl.COLOR_ATTACHMENT0, gl.TEXTURE_2D, null, 0)
      gl.bindFramebuffer(gl.READ_FRAMEBUFFER, previous.framebuffer); gl.bindBuffer(gl.PIXEL_PACK_BUFFER, previous.pack)
      gl.pixelStorei(gl.PACK_ALIGNMENT, previous.alignment); gl.pixelStorei(gl.PACK_ROW_LENGTH, previous.rowLength)
      gl.pixelStorei(gl.PACK_SKIP_PIXELS, previous.skipPixels); gl.pixelStorei(gl.PACK_SKIP_ROWS, previous.skipRows)
    }
  }
  function textureSource(texture: THREE.Texture, slot: string, originalDraw: boolean): GpuSource | Unmeasured {
    const properties = renderer.properties.get(texture) as { __webglTexture?: WebGLTexture; __version?: number }
    const installed = properties.__webglTexture
    if (!installed) return { authority: 'unmeasured-original-gpu-texture', reason: 'Original renderer has not installed this texture' }
    if ((texture as THREE.CubeTexture).isCubeTexture || (texture as THREE.Data3DTexture).isData3DTexture || (texture as THREE.DataArrayTexture).isDataArrayTexture || texture.type !== THREE.UnsignedByteType) {
      return { authority: 'unmeasured-original-gpu-texture', reason: slot === 'envMap' ? 'Current-code environment storage is not a raw embedded native RGBA8 image' : 'Original native GPU texture is not a two-dimensional unsigned-byte image' }
    }
    const savedActive = gl.getParameter(gl.ACTIVE_TEXTURE) as number
    let unit = savedActive - gl.TEXTURE0
    let binding: Binding = { authority: 'renderer-installed-texture', uniform: null, unit: null, boundMatchesTexture: null }
    const program = originalDraw ? gl.getParameter(gl.CURRENT_PROGRAM) as WebGLProgram | null : null
    if (program) {
      const location = gl.getUniformLocation(program, slot)
      if (location !== null) {
        const value: unknown = gl.getUniform(program, location)
        if (typeof value === 'number' && Number.isSafeInteger(value) && value >= 0) {
          unit = value; gl.activeTexture(gl.TEXTURE0 + unit)
          binding = { authority: 'actual-original-draw-sampler', uniform: slot, unit, boundMatchesTexture: gl.getParameter(gl.TEXTURE_BINDING_2D) === installed }
        }
      }
    }
    const previousTexture = gl.getParameter(gl.TEXTURE_BINDING_2D) as WebGLTexture | null
    try {
      gl.bindTexture(gl.TEXTURE_2D, installed)
      const samplerObject = gl.getParameter(gl.SAMPLER_BINDING) as WebGLSampler | null
      const parameter = (name: number): number => Number(samplerObject ? gl.getSamplerParameter(samplerObject, name) : gl.getTexParameter(gl.TEXTURE_2D, name))
      const sampler: Sampler = { wrapS: parameter(gl.TEXTURE_WRAP_S), wrapT: parameter(gl.TEXTURE_WRAP_T), minFilter: parameter(gl.TEXTURE_MIN_FILTER), magFilter: parameter(gl.TEXTURE_MAG_FILTER),
        baseLevel: Number(gl.getTexParameter(gl.TEXTURE_2D, gl.TEXTURE_BASE_LEVEL)), maxLevel: Number(gl.getTexParameter(gl.TEXTURE_2D, gl.TEXTURE_MAX_LEVEL)), compareMode: parameter(gl.TEXTURE_COMPARE_MODE), compareFunc: parameter(gl.TEXTURE_COMPARE_FUNC) }
      const key = canonicalJson([versions.get(installed) ?? 0, properties.__version ?? null, texture.version, texture.source.version, sampler])
      let result = cached.get(installed)
      if (!result || result.key !== key) {
        const [width, height] = dimensions(unit), bytes = pixels(width, height, installed)
        result = { key, width, height, bytes }; cached.set(installed, result)
      }
      return { authority: 'original-renderer-gpu-texture-level0', width: result.width, height: result.height, encoding: 'rgba8', origin: 'texture-row0', bytes: result.bytes, sampler, binding,
        format: texture.format, type: texture.type, internalFormat: texture.internalFormat, premultiplyAlpha: texture.premultiplyAlpha, unpackAlignment: texture.unpackAlignment }
    } catch (error) {
      return { authority: 'unmeasured-original-gpu-texture', reason: error instanceof Error ? error.message : String(error) }
    } finally { gl.bindTexture(gl.TEXTURE_2D, previousTexture); gl.activeTexture(savedActive) }
  }
  function snapshot(material: THREE.Material, originalDraw: boolean): MaterialRecord {
    insist(!disposed && !gl.isContextLost(), 'Original material capture disposed or GPU context lost')
    const object = material as unknown as Record<string, unknown>, properties: Record<string, unknown> = {}
    for (const name of propertyNames) if (object[name] !== undefined) properties[name] = valueSnapshot(object[name])
    const textures: TextureRecord[] = []
    for (const slot of textureSlots) {
      const texture = object[slot] as THREE.Texture | null | undefined
      if (!texture?.isTexture) continue
      textures.push({ slot, wrapS: texture.wrapS, wrapT: texture.wrapT, minFilter: texture.minFilter, magFilter: texture.magFilter, flipY: texture.flipY,
        colorSpace: texture.colorSpace, channel: texture.channel, offset: texture.offset.toArray(), repeat: texture.repeat.toArray(), center: texture.center.toArray(),
        rotation: texture.rotation, matrix: texture.matrix.toArray(), source: textureSource(texture, slot, originalDraw) })
    }
    return { schemaVersion: 1, type: material.type, name: material.name, properties, clippingPlanes: (material.clippingPlanes ?? []).map(plane => [plane.normal.x, plane.normal.y, plane.normal.z, plane.constant]), textures }
  }
  async function digest(bytes: Uint8Array): Promise<string> {
    const hash = await crypto.subtle.digest('SHA-256', bytes as Uint8Array<ArrayBuffer>)
    return Array.from(new Uint8Array(hash), byte => byte.toString(16).padStart(2, '0')).join('')
  }
  async function upload(bytes: Uint8Array, sink: NativeMaterialByteSink): Promise<string> {
    let digestPromise = byteHashes.get(bytes)
    if (!digestPromise) { digestPromise = digest(bytes); byteHashes.set(bytes, digestPromise) }
    const hash = await digestPromise
    let cache = uploads.get(sink)
    if (!cache) { cache = new Map(); uploads.set(sink, cache) }
    let result = cache.get(hash)
    if (!result) {
      result = sink.put(bytes, { retention: 'static' }).then(receipt => { insist(receipt.sha256 === hash && receipt.byteLength === bytes.byteLength, 'Material CAS receipt differs from actual bytes'); return hash })
      cache.set(hash, result)
      result.catch(() => { cache!.delete(hash) })
    }
    return result
  }
  return {
    observeDraw(material) { snapshots.set(material, snapshot(material, true)) },
    async capture(material, sink) {
      const record = snapshots.get(material) ?? snapshot(material, false), textures = []
      // Three temporarily changes DoubleSide to BackSide/FrontSide for its
      // approved transparent two-pass draw. Original side is restored before
      // this same-epoch transaction serializes the material identity.
      const properties = { ...record.properties, side: material.side }
      for (const texture of record.textures) {
        if (texture.source.authority === 'unmeasured-original-gpu-texture') { textures.push(texture); continue }
        const { bytes, ...source } = texture.source, objectSHA256 = await upload(bytes, sink)
        const span: NativeByteSpan = { objectSHA256, objectByteLength: bytes.byteLength, byteOffset: 0, byteLength: bytes.byteLength, scalar: 'u8', components: 4, count: source.width * source.height }
        textures.push({ ...texture, source: { ...source, bytes: span } })
      }
      return upload(new TextEncoder().encode(canonicalJson({ ...record, properties, textures })), sink)
    },
    dispose() {
      if (disposed) return
      disposed = true
      for (const [name, original] of mutationOriginals) mutable[name] = original
      mutationOriginals.clear()
      if (resources) {
        gl.deleteProgram(resources.program); for (const shader of resources.shaders) gl.deleteShader(shader)
        gl.deleteVertexArray(resources.vao); gl.deleteTransformFeedback(resources.feedback); gl.deleteBuffer(resources.buffer); gl.deleteFramebuffer(resources.framebuffer)
        resources = null
      }
    },
  }
}
