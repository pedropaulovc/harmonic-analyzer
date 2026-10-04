import type * as THREE from 'three'
import { canonicalJson, instrumentNativeVertexShader, nativeExpectedCameraSnapshot, nativeGeometryStateDescriptor, nativeGeometryUniforms, nativeProgramSource, nativeSubmissionStateDescriptor, serializeNativeBinding } from '../native-qualification-contract.mjs'
import { createNativeFeedbackExecutor, observeNativePrograms } from './native-qualification-feedback'
import type { CapturedAttribute, CapturedNativeDraw, CapturedPresentationDraw, CapturedUniform, NativeFeedbackExecutor, NativeProgramObserver } from './native-qualification-feedback'
import type { Machine, Viewer } from './scene'
import type { NativeByteSpan, NativeDrawBinding, NativeNumericField, NativeNumericOutput, NativePresentationInventoryEntry, NativePresentationSubmission, NativeQualificationInventoryEntry, NativeRasterCapture, NativeRasterPlane, NativeSceneCapture, NativeStaticDrawable, NativeStaticManifest, NativeSubmittedPrimitive, NativeViewReceipt } from './native-qualification-types'
import { createNativeMaterialCapture } from './native-material-capture'
import type { NativeMaterialCapture } from './native-material-capture'

export type NativeByteRetention = 'transient' | 'static' | 'reference' | 'selected-case'
export interface NativeQualificationByteSink {
  put(bytes: Uint8Array, options: { retention: NativeByteRetention }): Promise<{ sha256: string; byteLength: number; retention?: NativeByteRetention }>
}
export interface NativeRawDrawableAssociation {
  path: string
  nodeIndex: number
  meshIndex: number
  primitiveIndex: number
  instanceOf: string | null
}
export interface NativeQualificationCaptureContext {
  sceneCapture: NativeSceneCapture
  /** Hash of the actual executed-code closure object already streamed by Main. */
  codeClosureSHA256: string
  /** Independently parsed metadata, not a producer-selected expectation. */
  rawDrawables: readonly NativeRawDrawableAssociation[]
  rawCaseRetention: NativeViewReceipt['rawCaseRetention']
  cameraOutputCapture: 'selected-measured-tf' | 'finite-linear-enclosure'
  /** Newly returned Node-adjudicated keys; acknowledgement deltas accumulate. */
  consumerVerifiedPhysicalStates: readonly string[]
}
export interface NativeQualificationProducer {
  beginView(viewId: string, epoch: number): void
  enableCapture(): void
  captureView(binding: NativeDrawBinding, byteSink: NativeQualificationByteSink, context: NativeQualificationCaptureContext): Promise<NativeViewReceipt>
  dispose(): void
}
const encoder = new TextEncoder()
const requireValue: (value: unknown, message: string) => asserts value = (value, message) => {
  if (!value) throw new Error(`Native qualification capture unavailable: ${message}`)
}
const sha256 = async (bytes: Uint8Array): Promise<string> => {
  const digest = await crypto.subtle.digest('SHA-256', bytes as BufferSource)
  return Array.from(new Uint8Array(digest), byte => byte.toString(16).padStart(2, '0')).join('')
}
function arrayBytes(array: ArrayBufferView): Uint8Array {
  return new Uint8Array(array.buffer, array.byteOffset, array.byteLength)
}
function uniformPart(uniform: CapturedUniform) {
  return { bytes: uniform.bytes, layout: { scalar: 'u8' as const, components: 1, count: uniform.bytes.byteLength } }
}
function componentType(array: ArrayBufferView): number {
  if (array instanceof Float32Array) return 5126
  if (array instanceof Uint32Array) return 5125
  if (array instanceof Uint16Array) return 5123
  if (array instanceof Int16Array) return 5122
  if (array instanceof Uint8Array || array instanceof Uint8ClampedArray) return 5121
  if (array instanceof Int8Array) return 5120
  throw new Error('Unsupported authentic native attribute component type')
}
function scalarLayout(array: ArrayBufferView, components: number, count: number): Pick<NativeByteSpan, 'scalar' | 'components' | 'count'> {
  if (array instanceof Float32Array) return { scalar: 'f32le', components, count }
  if (array instanceof Float64Array) return { scalar: 'f64le', components, count }
  if (array instanceof Uint32Array) return { scalar: 'u32le', components, count }
  return { scalar: 'u8', components: 1, count: array.byteLength }
}
function packedAttribute(attribute: THREE.BufferAttribute | THREE.InterleavedBufferAttribute): ArrayBufferView {
  if (!('isInterleavedBufferAttribute' in attribute)) return attribute.array
  const source = attribute.data.array
  const ArrayType = source.constructor as { new(length: number): typeof source }
  const packed = new ArrayType(attribute.count * attribute.itemSize)
  for (let vertex = 0; vertex < attribute.count; vertex++) {
    for (let component = 0; component < attribute.itemSize; component++) packed[vertex * attribute.itemSize + component] = source[vertex * attribute.data.stride + attribute.offset + component]!
  }
  return packed
}
function fieldsFor(names: readonly NativeNumericField[]): NativeNumericOutput['fields'] {
  let offset = 0
  return names.map(name => {
    const components = name === 'clip' ? 4 : 3
    const field = { name, offset, components } as NativeNumericOutput['fields'][number]
    offset += components
    return field
  })
}
function consumedFields(record: CapturedNativeDraw): { physical: NativeNumericField[]; camera: NativeNumericField[]; unavailable: NativeNumericOutput['unavailable'] } {
  const source = record.sources.vertexShader, physical: NativeNumericField[] = ['local'], camera: NativeNumericField[] = ['view', 'clip']
  const unavailable: NativeNumericOutput['unavailable'] = []
  const worldSourceEnabled = /^\s*#define (?:USE_ENVMAP|USE_SHADOWMAP|DISTANCE)\b/m.test(source) && /\bvec4\s+worldPosition\b/.test(source)
  // These admitted Three world expressions require modelMatrix. If the
  // original link removed it, adding a world varying would invent an input.
  // Keep the local/normal/centre/tangent epilogue together instead.
  if (worldSourceEnabled && record.uniforms.some(uniform => uniform.name === 'modelMatrix')) physical.push('world')
  else unavailable.push({ field: 'world', reason: worldSourceEnabled ? 'optimized-out' : 'not-consumed' })
  if (record.family === 'standard' && /\bvec3\s+objectNormal\b/.test(source) && !/^\s*#define FLAT_SHADED\b/m.test(source)) {
    physical.push('objectNormal')
    if (/\bvNormal\s*=/.test(source)) camera.push('viewNormal')
    else unavailable.push({ field: 'viewNormal', reason: 'not-consumed' })
  } else {
    unavailable.push({ field: 'objectNormal', reason: 'not-consumed' }, { field: 'viewNormal', reason: 'not-consumed' })
  }
  if (/\bvec3\s+springNewCentre\b/.test(source) && /\bvec3\s+springNewTangent\b/.test(source)) physical.push('springCentre', 'springTangent')
  else unavailable.push({ field: 'springCentre', reason: 'not-consumed' }, { field: 'springTangent', reason: 'not-consumed' })
  return { physical, camera, unavailable }
}

/**
 * Byte production only. Neither raw metadata, packet hashes nor an output cache
 * supplies an acceptance verdict; the independent Node consumer adjudicates.
 */
export function createNativeQualificationProducer({ machine, viewer }: { machine: Machine; viewer: Viewer }): NativeQualificationProducer {
  let disposed = false, enabled = false, capturing = false, viewGeneration = 0
  const paths = new Map<THREE.Object3D, string>()
  const presentationEntries = new Map<THREE.Object3D, NativePresentationInventoryEntry>()
  let inventory: readonly NativeQualificationInventoryEntry[] = []
  const viewEpochs = new Map<string, number>()
  const physicalOutputs = new Map<string, NativeNumericOutput[]>()
  const verifiedPhysicalStates = new Set<string>()
  let sourceAdmissionKey: string | null = null
  const staticManifests = new Map<string, string>()
  const byteHashes = new WeakMap<Uint8Array, Promise<string>>()
  const objectUploads = new Map<string, NativeByteRetention>()
  const attributeCopies = new WeakMap<THREE.BufferAttribute | THREE.InterleavedBufferAttribute, { version: number; array: ArrayBufferView; bytes: Uint8Array }>()
  const indexCopies = new WeakMap<THREE.BufferGeometry, { index: THREE.BufferAttribute | null; version: number; count: number; array: Uint32Array; bytes: Uint8Array }>()
  const submittedIndexBytes = new WeakMap<Uint32Array, Uint8Array>()
  const attributeIds = new WeakMap<object, number>()
  let nextAttributeId = 0
  const textBytes = new Map<string, Uint8Array>()
  let observer: NativeProgramObserver | null = null
  let feedback: NativeFeedbackExecutor | null = null
  let materialCapture: NativeMaterialCapture | null = null
  let currentSink: NativeQualificationByteSink | null = null
  const stableBytes = (text: string): Uint8Array => {
    const existing = textBytes.get(text)
    if (existing) return existing
    const bytes = encoder.encode(text); textBytes.set(text, bytes); return bytes
  }
  function digest(bytes: Uint8Array): Promise<string> {
    let hash = byteHashes.get(bytes)
    if (!hash) { hash = sha256(bytes); byteHashes.set(bytes, hash) }
    return hash
  }
  async function put(bytes: Uint8Array, layout: Pick<NativeByteSpan, 'scalar' | 'components' | 'count'>, retention: NativeByteRetention): Promise<NativeByteSpan> {
    requireValue(currentSink, 'binary sink is not installed')
    const objectSHA256 = await digest(bytes), previous = objectUploads.get(objectSHA256)
    // Static data is kept; transient output raw bytes live only until this await.
    // A transient object may already have been released after adjudication.
    // Re-execution must really stream its bytes again, not just its old SHA.
    if (!previous || previous === 'transient') {
      const uploaded = await currentSink.put(bytes, { retention })
      requireValue(uploaded.sha256 === objectSHA256 && uploaded.byteLength === bytes.byteLength, 'Node binary sink hash/length differs from actual bytes')
      objectUploads.set(objectSHA256, uploaded.retention ?? retention)
    }
    return { objectSHA256, objectByteLength: bytes.byteLength, byteOffset: 0, byteLength: bytes.byteLength, ...layout }
  }
  async function putParts(parts: { bytes: Uint8Array; layout: Pick<NativeByteSpan, 'scalar' | 'components' | 'count'> }[]): Promise<NativeByteSpan[]> {
    let length = 0
    const offsets = parts.map(part => {
      const alignment = part.layout.scalar === 'f64le' ? 8 : part.layout.scalar === 'u8' ? 1 : 4
      length = Math.ceil(length / alignment) * alignment
      const offset = length; length += part.bytes.byteLength; return offset
    })
    const bytes = new Uint8Array(length)
    for (let index = 0; index < parts.length; index++) bytes.set(parts[index]!.bytes, offsets[index]!)
    const object = await put(bytes, { scalar: 'u8', components: 1, count: length }, 'static')
    return parts.map((part, index) => ({ ...object, byteOffset: offsets[index]!, byteLength: part.bytes.byteLength, ...part.layout }))
  }
  async function jsonObject(value: unknown, retention: NativeByteRetention): Promise<string> {
    const bytes = encoder.encode(canonicalJson(value))
    const span = await put(bytes, { scalar: 'u8', components: 1, count: bytes.byteLength }, retention)
    return span.objectSHA256
  }
  function readAttribute(attribute: THREE.BufferAttribute | THREE.InterleavedBufferAttribute) {
    const version = 'isInterleavedBufferAttribute' in attribute ? attribute.data.version : attribute.version
    const cached = attributeCopies.get(attribute)
    if (cached?.version === version) return cached
    const array = packedAttribute(attribute), result = { version, array, bytes: arrayBytes(array) }
    attributeCopies.set(attribute, result); return result
  }
  function readIndex(geometry: THREE.BufferGeometry) {
    const index = geometry.getIndex(), count = geometry.getAttribute('position').count, version = index?.version ?? 0
    const cached = indexCopies.get(geometry)
    if (cached?.index === index && cached.version === version && cached.count === count) return cached
    const array = index ? Uint32Array.from(index.array) : Uint32Array.from({ length: count }, (_, vertex) => vertex)
    const result = { index, version, count, array, bytes: arrayBytes(array) }; indexCopies.set(geometry, result); return result
  }
  async function staticManifest(binding: NativeDrawBinding, context: NativeQualificationCaptureContext): Promise<string> {
    const provenance = machine.provenance
    requireValue(inventory.length === 462 && new Set(inventory.map(entry => entry.path)).size === 462, 'complete actual 462-drawable inventory is missing')
    requireValue(provenance.identity === 'matched' && provenance.sourceCommit === binding.modelSourceCommit && provenance.sourceSha256 === binding.modelRawSHA256 && provenance.observedSha256 === binding.modelDeliverySHA256 && provenance.observedByteLength === binding.modelDeliveryByteLength && context.codeClosureSHA256 === binding.currentBuildClosureSHA256, 'actual loaded delivery/raw/code identity differs from closed binding')
    const versionKey = canonicalJson({ rawDrawables: context.rawDrawables, code: context.codeClosureSHA256, raw: provenance.sourceSha256, delivery: provenance.observedSha256,
      drawables: inventory.map(entry => {
        const geometry = entry.object.geometry, index = geometry.getIndex()
        if (index && !attributeIds.has(index)) attributeIds.set(index, nextAttributeId++)
        return { path: entry.path, object: entry.object.uuid, geometry: geometry.uuid, association: entry.association, instanceOf: entry.instanceOf,
          rest: Array.from(entry.restMatrixWorldF64), bindingOwnerPath: entry.bindingOwnerPath, binding: serializeNativeBinding(entry.binding), station: entry.station,
          spring: entry.spring ? { stock: entry.spring.stock, restLengthM: entry.spring.restLengthM } : null,
          attributes: Object.entries(geometry.attributes).map(([name, attribute]) => {
            if (!attributeIds.has(attribute)) attributeIds.set(attribute, nextAttributeId++)
            return [name, attributeIds.get(attribute), 'isInterleavedBufferAttribute' in attribute ? attribute.data.version : attribute.version, attribute.itemSize, attribute.count, attribute.normalized]
          }),
          index: index ? [attributeIds.get(index), index.version, index.count] : null }
      }) })
    const existing = staticManifests.get(versionKey)
    if (existing) return existing
    const rawByPath = new Map(context.rawDrawables.map(drawable => [drawable.path, drawable]))
    requireValue(rawByPath.size === context.rawDrawables.length, 'independent raw mapping contains duplicate paths')
    const drawables: NativeStaticDrawable[] = []
    for (const entry of inventory) {
      const raw = rawByPath.get(entry.path) ?? (entry.instanceOf ? rawByPath.get(entry.instanceOf) : undefined)
      requireValue(raw, `independent raw association missing: ${entry.path}`)
      requireValue(entry.association.nodeIndex === raw.nodeIndex && entry.association.meshIndex === raw.meshIndex && entry.association.primitiveIndex === raw.primitiveIndex, `actual parser association differs: ${entry.path}`)
      requireValue(entry.instanceOf === (raw.path === entry.path ? raw.instanceOf : raw.path), `actual native instance ancestry differs: ${entry.path}`)
      const geometry = entry.object.geometry, attributes: NativeStaticDrawable['attributes'] = []
      const classifiers: Record<string, NativeByteSpan> = {}
      for (const [semantic, attribute] of Object.entries(geometry.attributes)) {
        const actual = readAttribute(attribute), bytes = await put(actual.bytes, scalarLayout(actual.array, attribute.itemSize, attribute.count), 'static')
        if (entry.spring && ['springCoordinate', 'springRestCentre', 'springRestTangent'].includes(semantic)) classifiers[semantic] = bytes
        else attributes.push({ semantic, componentType: componentType(actual.array), normalized: attribute.normalized, bytes })
      }
      const indices = readIndex(geometry)
      const rest = entry.restMatrixWorldF64 instanceof Float64Array ? entry.restMatrixWorldF64 : Float64Array.from(entry.restMatrixWorldF64)
      requireValue(rest.length === 16, `actual loaded rest matrix missing: ${entry.path}`)
      let spring: NativeStaticDrawable['spring'] = null
      if (entry.spring) {
        const coordinate = classifiers.springCoordinate, centre = classifiers.springRestCentre, tangent = classifiers.springRestTangent
        requireValue(coordinate && centre && tangent, `actual classifier attributes missing: ${entry.path}`)
        spring = { stock: entry.spring.stock, restLengthM: entry.spring.restLengthM, coordinate, restCentre: centre, restTangent: tangent }
      }
      drawables.push({ path: entry.path, mode: 4, ancestor: { rawNodeIndex: raw.nodeIndex, rawMeshIndex: raw.meshIndex, rawPrimitiveIndex: raw.primitiveIndex, rawPath: entry.instanceOf ?? raw.path, instanceOf: entry.instanceOf },
        bindingOwnerPath: entry.bindingOwnerPath, binding: serializeNativeBinding(entry.binding), station: entry.station, attributes,
        canonicalIndices: await put(indices.bytes, { scalar: 'u32le', components: 1, count: indices.array.length }, 'static'), restMatrixF64: await put(arrayBytes(rest), { scalar: 'f64le', components: 16, count: 1 }, 'static'), spring })
    }
    const manifest: NativeStaticManifest = { schemaVersion: 1, rawSHA256: provenance.sourceSha256, deliverySHA256: provenance.observedSha256!, deliveryByteLength: provenance.observedByteLength!, codeObjectSHA256: context.codeClosureSHA256, drawables }
    const hash = await jsonObject(manifest, 'static'); staticManifests.set(versionKey, hash); return hash
  }
  async function submittedAttribute(input: CapturedAttribute, record: CapturedNativeDraw | CapturedPresentationDraw): Promise<NativeSubmittedPrimitive['attributes'][number]> {
    const attribute = record.geometry.getAttribute(input.name)
    const packedFloat = input.enabled && input.componentType === 5126 && input.offset === 0 && (input.stride === 0 || input.stride === input.components * 4) && input.bytes.byteLength === record.vertexCount * input.components * 4
    if (attribute && input.enabled && !('isInterleavedBufferAttribute' in attribute) && input.offset === 0 && (input.stride === 0 || input.stride === attribute.itemSize * attribute.array.BYTES_PER_ELEMENT)) {
      const authentic = readAttribute(attribute)
      // This is an actual-byte equality check, not regenerated classifier data.
      requireValue(await digest(input.bytes) === await digest(authentic.bytes), `actual GPU attribute differs from current geometry: ${'path' in record ? record.path : record.kind}/${input.name}`)
    }
    return { name: input.name, componentType: input.componentType, normalized: input.normalized, stride: input.stride, offset: input.offset, divisor: input.divisor, enabled: input.enabled,
      bytes: await put(input.bytes, packedFloat ? { scalar: 'f32le', components: input.components, count: record.vertexCount } : { scalar: 'u8', components: 1, count: input.bytes.byteLength }, 'static') }
  }
  async function submitted(record: CapturedNativeDraw): Promise<NativeSubmittedPrimitive> {
    const vertex = stableBytes(record.sources.vertexShader), fragment = stableBytes(record.sources.fragmentShader)
    const attributes: NativeSubmittedPrimitive['attributes'] = []
    for (const attribute of record.attributes) attributes.push(await submittedAttribute(attribute, record))
    const coreUniforms = nativeGeometryUniforms(record.uniforms, record.sources.vertexShader)
    const coreNames = new Set(coreUniforms.map(uniform => uniform.name)), submissionUniforms = record.uniforms.filter(uniform => !coreNames.has(uniform.name))
    const matrixLayout = { scalar: 'f64le' as const, components: 16, count: 1 }
    const coreSpans = await putParts([...coreUniforms.map(uniformPart), { bytes: arrayBytes(record.matrixWorld), layout: matrixLayout }])
    const submissionSpans = await putParts([...submissionUniforms.map(uniformPart), { bytes: arrayBytes(record.modelViewMatrix), layout: matrixLayout }, { bytes: arrayBytes(record.projectionMatrix), layout: matrixLayout }])
    const uniformSpans = new Map([...coreUniforms.map((uniform, index) => [uniform.name, coreSpans[index]!] as const), ...submissionUniforms.map((uniform, index) => [uniform.name, submissionSpans[index]!] as const)])
    const activeUniforms = record.uniforms.map(uniform => ({ name: uniform.name, glType: uniform.type, arraySize: uniform.activeArraySize, bytes: uniformSpans.get(uniform.name)! }))
    let indices = submittedIndexBytes.get(record.indices)
    if (!indices) { indices = arrayBytes(record.indices); submittedIndexBytes.set(record.indices, indices) }
    const result: NativeSubmittedPrimitive = { path: record.path, family: record.family,
      vertexShader: await put(vertex, { scalar: 'u8', components: 1, count: vertex.byteLength }, 'static'), fragmentShader: await put(fragment, { scalar: 'u8', components: 1, count: fragment.byteLength }, 'static'), attributes,
      canonicalSubmittedIndices: await put(indices, { scalar: 'u32le', components: 1, count: record.indices.length }, 'static'), drawRange: record.drawRange, activeUniforms,
      matrixWorldF64: coreSpans[coreUniforms.length]!, modelViewF64: submissionSpans[submissionUniforms.length]!, projectionF64: submissionSpans[submissionUniforms.length + 1]!, geometryStateSHA256: '' }
    result.geometryStateSHA256 = await sha256(encoder.encode(canonicalJson(nativeGeometryStateDescriptor(result, record.sources.vertexShader))))
    return result
  }
  async function presentation(record: CapturedPresentationDraw): Promise<NativePresentationSubmission> {
    const vertex = stableBytes(record.sources.vertexShader), fragment = stableBytes(record.sources.fragmentShader)
    const attributes: NativePresentationSubmission['attributes'] = []
    for (const attribute of record.attributes) attributes.push(await submittedAttribute(attribute, record))
    const spans = await putParts(record.uniforms.map(uniformPart))
    const activeUniforms = record.uniforms.map((uniform, index) => ({ name: uniform.name, glType: uniform.type, arraySize: uniform.activeArraySize, bytes: spans[index]! }))
    let indices = submittedIndexBytes.get(record.indices)
    if (!indices) { indices = arrayBytes(record.indices); submittedIndexBytes.set(record.indices, indices) }
    return { kind: record.kind, viewId: record.viewId, phase: record.phase, sourceRole: record.sourceRole,
      vertexShader: await put(vertex, { scalar: 'u8', components: 1, count: vertex.byteLength }, 'static'), fragmentShader: await put(fragment, { scalar: 'u8', components: 1, count: fragment.byteLength }, 'static'),
      attributes, canonicalSubmittedIndices: await put(indices, { scalar: 'u32le', components: 1, count: record.indices.length }, 'static'), activeUniforms, drawRange: record.drawRange,
      viewportBackingPixels: record.viewportBackingPixels, scissorBackingPixels: record.scissorBackingPixels, scissorTest: record.scissorTest, samplerBindings: record.samplerBindings }
  }
  async function numeric(record: CapturedNativeDraw, submission: NativeSubmittedPrimitive, names: readonly NativeNumericField[], unavailable: NativeNumericOutput['unavailable'], retention: NativeByteRetention, submissionStateSHA256: string | null): Promise<NativeNumericOutput[]> {
    requireValue(feedback, 'feedback capture is not enabled')
    const originalProgramSHA256 = await sha256(stableBytes(nativeProgramSource(record.sources.vertexShader, record.sources.fragmentShader)))
    const rows: NativeNumericOutput[] = []
    // Probe each independently copied field if a combined instrumentation turns
    // an originally optimized-out input on. No new uniform/attribute is supplied.
    const batches: NativeNumericField[][] = [Array.from(names)]
    for (let index = 0; index < batches.length; index++) {
      const batch = batches[index]!, fields = fieldsFor(batch)
      let result: { source: string; output: Float32Array }
      try { result = feedback.execute(record, fields) }
      catch {
        if (batch.length > 1) batches.push(...batch.map(name => [name]))
        else unavailable.push({ field: batch[0]!, reason: 'uncaptured-replica-input' })
        continue
      }
      const source = stableBytes(result.source), stride = fields.reduce((sum, field) => sum + field.components, 0)
      rows.push({ path: record.path, family: record.family, geometryStateSHA256: submission.geometryStateSHA256, submissionStateSHA256, authority: 'epilogue-only-original-active-inputs', originalProgramSHA256,
        instrumentationSource: await put(source, { scalar: 'u8', components: 1, count: source.byteLength }, 'static'), output: await put(arrayBytes(result.output), { scalar: 'f32le', components: stride, count: record.vertexCount }, retention), fields, unavailable: [] })
    }
    if (unavailable.length) {
      if (rows.length) rows[0]!.unavailable = unavailable
      else {
        const source = stableBytes(instrumentNativeVertexShader(record.sources.vertexShader, []))
        rows.push({ path: record.path, family: record.family, geometryStateSHA256: submission.geometryStateSHA256, submissionStateSHA256, authority: 'epilogue-only-original-active-inputs', originalProgramSHA256,
          instrumentationSource: await put(source, { scalar: 'u8', components: 1, count: source.byteLength }, 'static'), output: await put(new Uint8Array(0), { scalar: 'f32le', components: 1, count: 0 }, retention), fields: [], unavailable })
      }
    }
    return rows
  }
  async function rasterPlane(capture: NativeRasterCapture | null, retention: NativeByteRetention): Promise<NativeRasterPlane> {
    requireValue(capture && capture.pixels.byteLength === capture.width * capture.height * 4, 'fresh full raster bytes are missing')
    const { pixels, ...metadata } = capture
    return { ...metadata, bytes: await put(pixels, { scalar: 'u8', components: 4, count: capture.width * capture.height }, retention) }
  }
  return {
    beginView(viewId: string, epoch: number): void {
      requireValue(!disposed && enabled && Number.isSafeInteger(epoch), 'beginView needs an enabled live producer and actual draw epoch')
      viewGeneration++
      inventory = machine.nativeQualificationInventory()
      paths.clear(); for (const entry of inventory) paths.set(entry.object, entry.path)
      presentationEntries.clear(); for (const entry of viewer.nativeQualificationPresentationInventory()) presentationEntries.set(entry.object, entry)
      const viewKey = `${epoch}:${viewId}`
      viewEpochs.set(viewId, epoch); materialCapture!.beginView(viewKey); observer!.begin(viewKey)
    },
    enableCapture(): void {
      requireValue(!disposed, 'producer was disposed')
      if (enabled) return
      inventory = machine.nativeQualificationInventory()
      for (const entry of inventory) paths.set(entry.object, entry.path)
      for (const entry of viewer.nativeQualificationPresentationInventory()) presentationEntries.set(entry.object, entry)
      try {
        materialCapture = createNativeMaterialCapture(viewer.renderer)
        observer = observeNativePrograms(viewer.renderer, paths, materialCapture.observeDraw, presentationEntries); feedback = createNativeFeedbackExecutor(observer.gl)
        viewer.setNativeQualificationCaptureMode('enabled'); enabled = true
      } catch (error) {
        observer?.restore(); feedback?.dispose(); materialCapture?.dispose()
        observer = null; feedback = null; materialCapture = null; throw error
      }
    },
    async captureView(binding: NativeDrawBinding, byteSink: NativeQualificationByteSink, context: NativeQualificationCaptureContext): Promise<NativeViewReceipt> {
      requireValue(!disposed && enabled && !capturing, 'producer is disabled, disposed, or already capturing')
      capturing = true; currentSink = byteSink
      try {
        requireValue(context.cameraOutputCapture === 'selected-measured-tf' || context.cameraOutputCapture === 'finite-linear-enclosure', 'explicit camera output capture policy is missing')
        requireValue(Array.isArray(context.consumerVerifiedPhysicalStates), 'Node physical cache acknowledgement is missing')
        const admissionKey = `${binding.modelRawSHA256}:${binding.modelDeliverySHA256}:${context.codeClosureSHA256}`
        if (sourceAdmissionKey !== admissionKey) { physicalOutputs.clear(); verifiedPhysicalStates.clear(); sourceAdmissionKey = admissionKey }
        for (const key of context.consumerVerifiedPhysicalStates) verifiedPhysicalStates.add(key)
        const capture = context.sceneCapture, epoch = viewEpochs.get(binding.viewId), generation = viewGeneration
        requireValue(capture.status === 'captured' && capture.viewId === binding.viewId && epoch === binding.sourceDrawRevision && capture.drawRevision === epoch && capture.completedDrawEpoch === binding.completedSceneDrawEpoch && capture.timeSeconds === binding.timeSeconds, 'completed scene/source draw epoch is stale')
        const viewKey = `${epoch}:${binding.viewId}`
        // Keep the independently bound raw camera. Model only the original
        // Scene write/read convention, using logical dimensions, never ceil FBOs.
        const logicalDimensions: readonly [number, number] = binding.resolvedImagePlaneWarp?.unwarpedViewportPixels ?? [binding.rectSourcePixels[2], binding.rectSourcePixels[3]]
        const expectedCamera = nativeExpectedCameraSnapshot(binding.camera, logicalDimensions), actualCamera = capture.camera
        const cameraMatches = actualCamera !== null
          && expectedCamera.positionMetres.every((value, index) => Math.abs(actualCamera.positionMetres[index]! - value) <= 1e-7)
          && (expectedCamera.quaternion.every((value, index) => Math.abs(actualCamera.quaternion[index]! - value) <= 1e-7)
            || expectedCamera.quaternion.every((value, index) => Math.abs(actualCamera.quaternion[index]! + value) <= 1e-7))
          && Math.abs(actualCamera.verticalFovDegrees - expectedCamera.verticalFovDegrees) <= 1e-7
          && canonicalJson(actualCamera.principalPointViewportPixels ?? null) === canonicalJson(expectedCamera.principalPointViewportPixels ?? null)
        requireValue(cameraMatches && canonicalJson(capture.rectSourcePixels) === canonicalJson(binding.rectSourcePixels) && capture.presentation === binding.presentation && canonicalJson(capture.resolvedImagePlaneWarp) === canonicalJson(binding.resolvedImagePlaneWarp) && canonicalJson(capture.sourceLayout) === canonicalJson(binding.sourceLayout), 'actual captured camera/support/layout differs from closed binding')
        const observed = observer!.take(`${epoch}:${binding.viewId}`)
        requireValue(observed.failures.length === 0, observed.failures.join('; '))
        const retention: NativeByteRetention = context.rawCaseRetention === 'retained-selected-case' ? 'selected-case' : 'transient'
        const staticNativeSHA256 = await staticManifest(binding, context)
        requireValue(capture.drawables.length === inventory.length, 'same-epoch drawable snapshots are incomplete')
        const states: unknown[] = []
        for (let index = 0; index < inventory.length; index++) {
          const entry = inventory[index]!, state = capture.drawables[index]!
          requireValue(state.path === entry.path && state.bindingOwnerPath === entry.bindingOwnerPath && state.station === entry.station && canonicalJson(serializeNativeBinding(state.binding)) === canonicalJson(serializeNativeBinding(entry.binding)), 'same-epoch actual binding/owner inventory differs')
          const materialSlotsSHA256: string[] = []
          for (const material of state.materials) materialSlotsSHA256.push(await materialCapture!.capture(material, byteSink, viewKey))
          states.push({ path: state.path, matrixWorldF64: await put(arrayBytes(state.matrixWorld), { scalar: 'f64le', components: 16, count: 1 }, 'static'), effectiveVisibility: state.effectiveVisibility,
            groups: state.groups, drawRange: state.drawRange, materialSlotsSHA256, bindingOwnerPath: state.bindingOwnerPath, binding: serializeNativeBinding(state.binding), station: state.station, springLengthM: state.springLengthM })
        }
        const drawableStateSHA256 = await jsonObject(states, 'static'), submissions: NativeSubmittedPrimitive[] = [], numericOutputs: NativeNumericOutput[] = []
        const uniqueDraws = new Set<string>()
        for (const record of observed.records) {
          const submission = await submitted(record), submissionKey = await sha256(encoder.encode(canonicalJson(nativeSubmissionStateDescriptor(submission))))
          if (uniqueDraws.has(submissionKey)) continue
          uniqueDraws.add(submissionKey); submissions.push(submission)
          const consumed = consumedFields(record), geometryKey = submission.geometryStateSHA256
          let physical = physicalOutputs.get(geometryKey)
          // Selected raw retention may arrive after a live-only cache hit. Re-run
          // the authentic replica rather than keeping every state's raw arrays
          // or pretending the discarded bytes were retained for this case.
          if (!physical || !verifiedPhysicalStates.has(geometryKey) || (retention === 'selected-case' && physical.some(row => objectUploads.get(row.output.objectSHA256) === 'transient'))) {
            physical = await numeric(record, submission, consumed.physical, consumed.unavailable, retention, null); physicalOutputs.set(geometryKey, physical)
          }
          if (context.cameraOutputCapture === 'finite-linear-enclosure') {
            numericOutputs.push(...physical.map((row, index) => index === 0 ? { ...row, unavailable: [...row.unavailable, ...consumed.camera.map(field => ({ field, reason: 'not-selected-for-measured-tf' as const }))] } : row))
          } else {
            numericOutputs.push(...physical)
            // Selected TF always executes the current original submission.
            // No camera payload survives only as a reference to released bytes.
            numericOutputs.push(...await numeric(record, submission, consumed.camera, [], retention, submissionKey))
          }
        }
        const presentationSubmissions: NativePresentationSubmission[] = []
        for (const record of observed.presentations) presentationSubmissions.push(await presentation(record))
        const raster = { nativeMaterialRGBA: await rasterPlane(capture.nativeMaterialRGBA, retention), nativeMaterialDepth: await rasterPlane(capture.nativeMaterialDepth, retention), nativePathID: await rasterPlane(capture.nativePathID, retention), nativeIDDepth: await rasterPlane(capture.nativeIDDepth, retention) }
        requireValue(!disposed && viewGeneration === generation && viewEpochs.get(binding.viewId) === epoch, 'view changed while its bytes streamed')
        return { schemaVersion: 1, binding, staticNativeSHA256, drawableStateSHA256, submitted: submissions, presentationSubmissions, numericOutputs, raster, rawCaseRetention: context.rawCaseRetention }
      } finally { currentSink = null; capturing = false }
    },
    dispose(): void {
      if (disposed) return
      disposed = true; enabled = false
      observer?.restore(); feedback?.dispose(); materialCapture?.dispose(); viewer.setNativeQualificationCaptureMode('disabled')
      paths.clear(); presentationEntries.clear(); viewEpochs.clear(); physicalOutputs.clear(); verifiedPhysicalStates.clear(); staticManifests.clear(); objectUploads.clear(); textBytes.clear()
    },
  }
}
