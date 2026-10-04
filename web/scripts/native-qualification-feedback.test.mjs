import test from 'node:test'
import assert from 'node:assert/strict'
import { readFile } from 'node:fs/promises'
import { resolve } from 'node:path'
import { fileURLToPath, pathToFileURL } from 'node:url'
import ts from 'typescript'
import { Matrix3, Mesh, PlaneGeometry, ShaderMaterial, Texture } from 'three'
import { createNativeByteReader, sha256 } from './native-model-byte-proof.mjs'
import { prepareNativeMirrorSubmission, prepareNativeWarpSubmission } from './native-camera-enclosure.mjs'

// Parent-only revision controls select an exact materialized module, not a
// hand-reverted predicate. The stateful GL double executes the actual observer
// interception/readback path; it does not claim browser/GPU rendering proof.
async function loadModule(path, privateExports = []) {
  const source = await readFile(path, 'utf8')
  const compiled = ts.transpileModule(source, { compilerOptions: { target: ts.ScriptTarget.ES2022, module: ts.ModuleKind.ESNext } }).outputText
  const tree = ts.createSourceFile(path, compiled, ts.ScriptTarget.ES2022, true, ts.ScriptKind.JS)
  const replacements = []
  for (const statement of tree.statements) {
    if (!(ts.isImportDeclaration(statement) || ts.isExportDeclaration(statement)) || !statement.moduleSpecifier) continue
    const specifier = statement.moduleSpecifier.text
    const url = specifier.startsWith('.') ? new URL(specifier, pathToFileURL(path)).href : import.meta.resolve(specifier)
    replacements.push({ start: statement.moduleSpecifier.getStart(tree), end: statement.moduleSpecifier.end, text: JSON.stringify(url) })
  }
  let text = compiled
  for (const row of replacements.reverse()) text = text.slice(0, row.start) + row.text + text.slice(row.end)
  if (privateExports.length) text += `\nexport { ${privateExports.join(', ')} };\n`
  return import(`data:text/javascript;base64,${Buffer.from(text).toString('base64')}`)
}
const feedbackPath = resolve(process.env.NATIVE_PRESENTATION_FEEDBACK_PATH ?? fileURLToPath(new URL('../src/native-qualification-feedback.ts', import.meta.url)))
const consumerPath = resolve(process.env.NATIVE_PRESENTATION_CONSUMER_PATH ?? fileURLToPath(new URL('./native-qualification.mjs', import.meta.url)))
const { observeNativePrograms } = await loadModule(feedbackPath)
const { closePresentationSubmissions } = await loadModule(consumerPath, ['closePresentationSubmissions'])

// Same closed highp presentation kernels as the existing camera-enclosure
// behavioral fixtures. Uniform/attribute bytes below are read by the observer,
// serialized to a real CAS, and independently closed by the Node consumer.
const vertexShader = `#version 300 es
precision highp float;
in vec3 position;
in vec2 uv;
out vec2 imageUv;
void main() { imageUv=uv; gl_Position=vec4(position.xy,0.0,1.0); }`
const mirrorShader = `#version 300 es
precision highp float;
uniform sampler2D image;
in vec2 imageUv;
out vec4 colour;
#define gl_FragColor colour
void main() { gl_FragColor=texture2D(image,vec2(1.0-imageUv.x,imageUv.y)); }`
const warpShader = `#version 300 es
precision highp float;
uniform sampler2D image;
uniform mat3 inverseH;
uniform vec2 grid;
uniform vec4 sourceFromBacking;
uniform vec4 rect;
uniform bool warped;
uniform bool mask;
out vec4 colour;
#define gl_FragColor colour
void main() {
  vec2 source = gl_FragCoord.xy * sourceFromBacking.xy + sourceFromBacking.zw;
  if (any(lessThan(source, rect.xy)) || any(greaterThanEqual(source, rect.xy + rect.zw))) discard;
  vec3 local = inverseH * vec3(source, 1.0);
  vec2 p = warped ? local.xy / local.z : source - rect.xy;
  vec2 dimensions = warped ? grid : rect.zw;
  if (any(lessThan(p, vec2(0.0))) || any(greaterThanEqual(p, dimensions))) discard;
  if (mask) { gl_FragColor = vec4(0.0); return; }
  gl_FragColor = texture2D(image, vec2(p.x / dimensions.x, 1.0 - p.y / dimensions.y));
}`
const compositeShader = `#version 300 es
precision highp float;
uniform sampler2D image;
uniform vec4 imageRect;
uniform float weight;
uniform vec3 background;
uniform float stage;
in vec2 imageUv;
out vec4 nativeColour;
#define gl_FragColor nativeColour
void main() {
  vec4 layer = texture2D(image, imageRect.xy + imageUv * imageRect.zw);
  vec3 colour = layer.rgb;
  if (stage < 0.5) {
    colour = mix(12.92 * colour, 1.055 * pow(max(colour, vec3(0.0)), vec3(1.0 / 2.4)) - 0.055, step(vec3(0.0031308), colour));
    gl_FragColor = vec4(colour * weight * layer.a, weight * layer.a);
  } else {
    if (layer.a <= 0.0) discard;
    gl_FragColor = vec4(colour + background * max(0.0, 1.0 - layer.a), 1.0);
  }
}`
const warp = { kind: 'homography', unwarpedViewportPixels: [640, 480], renderToSourcePixels: [1, 0.125, 0, 0, 1, 0, 0, 0, 1] }
const rasterGeometry = { destinationViewportBackingPixels: [0, 0, 640, 480], destinationScissorBackingPixels: [0, 0, 640, 480], destinationCellSourcePixels: [1, 1], sourceGateBackingPixels: [0, 0, 640, 480], drawingBufferHeight: 480 }

function fixture() {
  const geometry = new PlaneGeometry(2, 2), material = new ShaderMaterial(), texture = new Texture(), installedTexture = {}
  const object = new Mesh(geometry, material)
  const presentationEntries = new Map(), bindings = new Map(), textureBindings = new Map(), uniforms = new Map(), attributes = []
  const gl = {
    TRIANGLES: 4, LINE_STRIP: 3, FLOAT: 5126, UNSIGNED_INT: 5125, UNSIGNED_SHORT: 5123, UNSIGNED_BYTE: 5121,
    FLOAT_VEC2: 35664, FLOAT_VEC3: 35665, FLOAT_VEC4: 35666, FLOAT_MAT3: 35675, BOOL: 35670, SAMPLER_2D: 35678,
    ARRAY_BUFFER: 34962, ARRAY_BUFFER_BINDING: 34964, ELEMENT_ARRAY_BUFFER: 34963, ELEMENT_ARRAY_BUFFER_BINDING: 34965,
    COPY_READ_BUFFER: 36662, COPY_READ_BUFFER_BINDING: 36662, COPY_WRITE_BUFFER: 36663, COPY_WRITE_BUFFER_BINDING: 36663, BUFFER_SIZE: 34660,
    CURRENT_PROGRAM: 35725, ACTIVE_ATTRIBUTES: 35721, ACTIVE_UNIFORMS: 35718, VERTEX_SHADER: 35633, FRAGMENT_SHADER: 35632, SHADER_TYPE: 35663,
    VERTEX_ATTRIB_ARRAY_ENABLED: 34338, VERTEX_ATTRIB_ARRAY_BUFFER_BINDING: 34975, CURRENT_VERTEX_ATTRIB: 34342,
    VERTEX_ATTRIB_ARRAY_SIZE: 34339, VERTEX_ATTRIB_ARRAY_TYPE: 34341, VERTEX_ATTRIB_ARRAY_NORMALIZED: 34922,
    VERTEX_ATTRIB_ARRAY_STRIDE: 34340, VERTEX_ATTRIB_ARRAY_POINTER: 34373, VERTEX_ATTRIB_ARRAY_DIVISOR: 35070,
    ACTIVE_TEXTURE: 34016, TEXTURE0: 33984, TEXTURE_BINDING_2D: 32873, VIEWPORT: 2978, SCISSOR_BOX: 3088, SCISSOR_TEST: 3089,
    bufferData() {}, bufferSubData() {}, copyBufferSubData() {}, linkProgram() {},
    bindBuffer(target, buffer) { bindings.set(target, buffer) },
    getBufferParameter(target, parameter) { assert.equal(parameter, gl.BUFFER_SIZE); return bindings.get(target).bytes.length },
    getBufferSubData(target, offset, output) { output.set(bindings.get(target).bytes.subarray(offset, offset + output.byteLength)) },
    getParameter(parameter) {
      if (parameter === gl.CURRENT_PROGRAM) return program
      if (parameter === gl.ACTIVE_TEXTURE) return activeTexture
      if (parameter === gl.TEXTURE_BINDING_2D) return textureBindings.get(activeTexture) ?? null
      if (parameter === gl.VIEWPORT || parameter === gl.SCISSOR_BOX) return Int32Array.from([0, 0, 640, 480])
      if (parameter === gl.ARRAY_BUFFER_BINDING) return bindings.get(gl.ARRAY_BUFFER) ?? null
      if (parameter === gl.ELEMENT_ARRAY_BUFFER_BINDING) return bindings.get(gl.ELEMENT_ARRAY_BUFFER) ?? null
      if (parameter === gl.COPY_READ_BUFFER_BINDING || parameter === gl.COPY_WRITE_BUFFER_BINDING) return bindings.get(parameter) ?? null
      throw new Error(`Unexpected GL parameter ${parameter}`)
    },
    getProgramParameter(actualProgram, parameter) { assert.equal(actualProgram, program); return parameter === gl.ACTIVE_ATTRIBUTES ? attributes.length : uniforms.size },
    getAttachedShaders(actualProgram) { return actualProgram.shaders },
    getShaderSource(shader) { return shader.source }, getShaderParameter(shader) { return shader.type },
    getActiveAttrib(actualProgram, index) { return attributes[index].info },
    getAttribLocation(actualProgram, name) { return attributes.findIndex(row => row.info.name === name) },
    getVertexAttrib(location, parameter) {
      const row = attributes[location]
      if (parameter === gl.VERTEX_ATTRIB_ARRAY_ENABLED) return true
      if (parameter === gl.VERTEX_ATTRIB_ARRAY_BUFFER_BINDING) return row.buffer
      if (parameter === gl.VERTEX_ATTRIB_ARRAY_SIZE) return row.components
      if (parameter === gl.VERTEX_ATTRIB_ARRAY_TYPE) return gl.FLOAT
      if (parameter === gl.VERTEX_ATTRIB_ARRAY_NORMALIZED) return false
      if (parameter === gl.VERTEX_ATTRIB_ARRAY_STRIDE || parameter === gl.VERTEX_ATTRIB_ARRAY_DIVISOR) return 0
      throw new Error(`Unexpected attribute parameter ${parameter}`)
    },
    getVertexAttribOffset() { return 0 },
    getActiveUniform(actualProgram, index) { const [name, row] = [...uniforms][index]; return { name, type: row.type, size: 1 } },
    getUniformLocation(actualProgram, name) { return uniforms.has(name) ? { name } : null },
    getUniform(actualProgram, location) { return uniforms.get(location.name).value },
    activeTexture(unit) { activeTexture = unit }, isEnabled(parameter) { assert.equal(parameter, gl.SCISSOR_TEST); return true },
    drawElements() {}, drawArrays() {}, drawElementsInstanced() {}, drawArraysInstanced() {},
  }
  textureBindings.set(gl.TEXTURE0 + 2, installedTexture)
  let activeTexture = gl.TEXTURE0 + 3, program = null, primitive = gl.TRIANGLES, submittedGeometry = geometry
  for (const name of ['position', 'uv']) {
    const attribute = geometry.getAttribute(name)
    attributes.push({ info: { name, type: attribute.itemSize === 3 ? gl.FLOAT_VEC3 : gl.FLOAT_VEC2, size: 1 }, components: attribute.itemSize, buffer: { bytes: new Uint8Array(attribute.array.buffer) } })
  }
  bindings.set(gl.ELEMENT_ARRAY_BUFFER, { bytes: new Uint8Array(geometry.index.array.buffer) })
  const renderer = {
    getContext() { return gl }, properties: { get(value) { assert.equal(value, texture); return { __webglTexture: installedTexture } } },
    renderBufferDirect() { gl.drawElements(primitive, 6, gl.UNSIGNED_SHORT, 0) },
  }
  const observer = observeNativePrograms(renderer, new Map(), undefined, presentationEntries)
  function draw(kind, { phase = 'source-presentation', sourceRole = kind === 'source-composite' ? 'source-composite-image' : 'native-colour-stage', mask = false, stage = 0, weight = 0.375, invalidMode = false, missingPosition = false, badInverse = false } = {}) {
    presentationEntries.set(object, { kind, object, phase, sourceRole, inputTexture: texture })
    uniforms.clear()
    const set = (name, type, value) => uniforms.set(name, { type, value })
    set('image', gl.SAMPLER_2D, 2)
    if (kind === 'source-warp') {
      const inverse = Float32Array.from(new Matrix3().set(...warp.renderToSourcePixels).invert().elements)
      if (badInverse) inverse[0] = NaN
      set('inverseH', gl.FLOAT_MAT3, inverse); set('grid', gl.FLOAT_VEC2, Float32Array.from(warp.unwarpedViewportPixels))
      set('sourceFromBacking', gl.FLOAT_VEC4, Float32Array.from([1, -1, 0, 480])); set('rect', gl.FLOAT_VEC4, Float32Array.from([0, 0, 640, 480]))
      set('warped', gl.BOOL, true); set('mask', gl.BOOL, mask)
    } else if (kind === 'source-composite') {
      set('imageRect', gl.FLOAT_VEC4, Float32Array.from([0, 0, 1, 1])); set('weight', gl.FLOAT, weight)
      set('background', gl.FLOAT_VEC3, Float32Array.from([0, 0, 0])); set('stage', gl.FLOAT, stage)
    }
    program = { shaders: [{ type: gl.VERTEX_SHADER, source: vertexShader }, { type: gl.FRAGMENT_SHADER, source: kind === 'source-warp' ? warpShader : kind === 'horizontal-mirror' ? mirrorShader : compositeShader }] }
    primitive = invalidMode ? gl.LINE_STRIP : gl.TRIANGLES
    submittedGeometry = missingPosition ? { getAttribute() { return undefined } } : geometry
    renderer.renderBufferDirect({ projectionMatrix: { elements: [] } }, null, submittedGeometry, material, object, null)
  }
  return { observer, draw, geometry, dispose() { observer.restore(); geometry.dispose(); material.dispose(); texture.dispose() } }
}
function signature(result) { return result.presentations.map(row => [row.viewId, row.kind, row.phase, row.sourceRole]) }
async function closeRows(rows, viewId, geometry, resolvedImagePlaneWarp) {
  const objects = new Map()
  const span = (bytes, scalar = 'u8', components = 1, count = bytes.byteLength) => {
    const objectSHA256 = sha256(bytes); objects.set(objectSHA256, bytes)
    return { objectSHA256, objectByteLength: bytes.byteLength, byteOffset: 0, byteLength: bytes.byteLength, scalar, components, count }
  }
  const bytesOf = value => new Uint8Array(value.buffer, value.byteOffset, value.byteLength)
  const submissions = rows.map(row => ({
    kind: row.kind, viewId: row.viewId, phase: row.phase, sourceRole: row.sourceRole,
    vertexShader: span(Buffer.from(row.sources.vertexShader)), fragmentShader: span(Buffer.from(row.sources.fragmentShader)),
    activeUniforms: row.uniforms.map(uniform => ({ name: uniform.name, glType: uniform.type, arraySize: uniform.activeArraySize, bytes: span(uniform.bytes) })),
    attributes: row.attributes.map(({ name, componentType, normalized, stride, offset, divisor, enabled, bytes }) => ({ name, componentType, normalized, stride, offset, divisor, enabled, bytes: span(bytes) })),
    canonicalSubmittedIndices: span(bytesOf(row.indices), 'u32le', 1, row.indices.length), drawRange: row.drawRange,
    viewportBackingPixels: row.viewportBackingPixels, scissorBackingPixels: row.scissorBackingPixels, scissorTest: row.scissorTest, samplerBindings: row.samplerBindings,
  }))
  const reader = createNativeByteReader({ get(hash) { return objects.get(hash) } })
  const binding = { viewId, rectSourcePixels: [0, 0, 640, 480], resolvedImagePlaneWarp, presentation: resolvedImagePlaneWarp ? 'native' : 'horizontal-mirror' }
  return { binding, raster: await closePresentationSubmissions(reader, submissions, binding, rasterGeometry, geometry) }
}

test('same-epoch warp/crossfade and mirror/crossfade receipts close only their own view', async () => {
  const f = fixture()
  try {
    f.observer.begin('41:view-A')
    f.draw('source-warp')
    f.draw('source-warp', { phase: 'diagnostic-presentation', mask: true })
    f.draw('source-composite')
    f.observer.begin('41:view-B')
    f.draw('horizontal-mirror')
    f.draw('source-composite', { weight: 0.625 })
    f.draw('source-composite', { sourceRole: 'source-composite-sum', stage: 1 })
    const a = f.observer.take('41:view-A'), b = f.observer.take('41:view-B')
    assert.deepEqual(signature(a), [['view-A', 'source-warp', 'source-presentation', 'native-colour-stage'], ['view-A', 'source-warp', 'diagnostic-presentation', 'native-colour-stage'], ['view-A', 'source-composite', 'source-presentation', 'source-composite-image']])
    assert.deepEqual(signature(b), [['view-B', 'horizontal-mirror', 'source-presentation', 'native-colour-stage'], ['view-B', 'source-composite', 'source-presentation', 'source-composite-image'], ['view-B', 'source-composite', 'source-presentation', 'source-composite-sum']])
    const closedA = await closeRows(a.presentations, 'view-A', f.geometry, warp), closedB = await closeRows(b.presentations, 'view-B', f.geometry, null)
    const warpProof = prepareNativeWarpSubmission(closedA.binding, closedA.raster)
    assert.equal(warpProof.kind, 'closed-original-source-warp-v1')
    assert.deepEqual([...warpProof.inverseUploaded], [1, 0, 0, -0.125, 1, 0, 0, 0, 1])
    assert.equal(prepareNativeMirrorSubmission(closedB.binding, closedB.raster).coordinateExpression, '(1-imageUv.x,imageUv.y)')
    await assert.rejects(closeRows([...a.presentations, ...b.presentations], 'view-A', f.geometry, warp), /Foreign presentation draw phase\/view\/source role/)
  } finally { f.dispose() }
})

test('a malformed own-view draw refuses that view without contaminating its valid neighbor', () => {
  const f = fixture()
  try {
    f.observer.begin('42:view-A'); f.draw('source-warp', { invalidMode: true }); f.draw('source-warp')
    f.observer.begin('42:view-B'); f.draw('horizontal-mirror', { missingPosition: true }); f.draw('horizontal-mirror')
    const a = f.observer.take('42:view-A'), b = f.observer.take('42:view-B')
    assert.deepEqual(a.failures, ['source-warp: Native primitive did not submit triangles'])
    assert.deepEqual(b.failures, ['horizontal-mirror: Actual native geometry has no position input'])
    assert.deepEqual(signature(a), [['view-A', 'source-warp', 'source-presentation', 'native-colour-stage']])
    assert.deepEqual(signature(b), [['view-B', 'horizontal-mirror', 'source-presentation', 'native-colour-stage']])
  } finally { f.dispose() }
})

test('known own-view nonfinite presentation bytes reach Node refusal instead of being silently dropped', async () => {
  const f = fixture()
  try {
    f.observer.begin('43:view-A'); f.draw('source-warp', { badInverse: true })
    f.observer.begin('43:view-B'); f.draw('horizontal-mirror')
    const a = f.observer.take('43:view-A'), b = f.observer.take('43:view-B')
    assert.deepEqual(signature(a), [['view-A', 'source-warp', 'source-presentation', 'native-colour-stage']])
    await assert.rejects(closeRows(a.presentations, 'view-A', f.geometry, warp), /Nonfinite actual active uniform/)
    const closed = await closeRows(b.presentations, 'view-B', f.geometry, null)
    assert.equal(prepareNativeMirrorSubmission(closed.binding, closed.raster).kind, 'closed-original-horizontal-mirror-v1')
  } finally { f.dispose() }
})

test('retaking or rebeginning one view consumes or replaces only that key within the epoch', () => {
  const f = fixture()
  try {
    f.observer.begin('44:view-A'); f.draw('source-warp'); f.draw('source-warp', { invalidMode: true })
    f.observer.begin('44:view-B'); f.draw('horizontal-mirror')
    assert.deepEqual(signature(f.observer.take('44:view-A')), [['view-A', 'source-warp', 'source-presentation', 'native-colour-stage']])
    assert.deepEqual(f.observer.take('44:view-A'), { records: [], presentations: [], failures: [] })
    f.observer.begin('44:view-A'); f.draw('source-composite')
    assert.deepEqual(signature(f.observer.take('44:view-A')), [['view-A', 'source-composite', 'source-presentation', 'source-composite-image']])
    assert.deepEqual(signature(f.observer.take('44:view-B')), [['view-B', 'horizontal-mirror', 'source-presentation', 'native-colour-stage']])
  } finally { f.dispose() }
})

test('advancing the epoch removes every prior view record and failure while retaining the fresh view', async () => {
  const f = fixture()
  try {
    f.observer.begin('45:view-A'); f.draw('source-warp'); f.draw('source-warp', { invalidMode: true })
    f.observer.begin('45:view-B'); f.draw('horizontal-mirror')
    f.observer.begin('46:view-A'); f.draw('source-warp')
    const fresh = f.observer.take('46:view-A')
    assert.deepEqual(f.observer.take('45:view-A'), { records: [], presentations: [], failures: [] })
    assert.deepEqual(f.observer.take('45:view-B'), { records: [], presentations: [], failures: [] })
    assert.deepEqual(fresh.failures, [])
    const closed = await closeRows(fresh.presentations, 'view-A', f.geometry, warp)
    assert.equal(prepareNativeWarpSubmission(closed.binding, closed.raster).kind, 'closed-original-source-warp-v1')
  } finally { f.dispose() }
})

test('one view retains source and diagnostic submissions while a fresh epoch clears old failures', async () => {
  const f = fixture()
  try {
    f.observer.begin('47:view-A'); f.draw('source-warp', { invalidMode: true })
    f.observer.begin('48:view-A'); f.draw('source-warp'); f.draw('source-warp', { phase: 'diagnostic-presentation', mask: true })
    const fresh = f.observer.take('48:view-A')
    assert.deepEqual(fresh.failures, [])
    assert.deepEqual(signature(fresh), [['view-A', 'source-warp', 'source-presentation', 'native-colour-stage'], ['view-A', 'source-warp', 'diagnostic-presentation', 'native-colour-stage']])
    const closed = await closeRows(fresh.presentations, 'view-A', f.geometry, warp)
    assert.deepEqual([...prepareNativeWarpSubmission(closed.binding, closed.raster).inverseUploaded], [1, 0, 0, -0.125, 1, 0, 0, 0, 1])
  } finally { f.dispose() }
})
