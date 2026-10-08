import assert from 'node:assert/strict'
import { createHash } from 'node:crypto'
import { mkdtemp, mkdir, readFile, rm, writeFile } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { before, after, test } from 'node:test'
import { gunzipSync } from 'node:zlib'
import { splitOversizedAssets, verifyTransportAssets } from './deployment-transport.mjs'
import { createAssetWorker, negotiateCoding } from '../deployment-asset-worker.mjs'

// Node stand-in tests stream accounting only. Native FixedLengthStream and
// encodeBody passthrough must additionally be exercised with Wrangler/Chrome.
const originalFixedLengthStream = globalThis.FixedLengthStream
before(() => {
  globalThis.FixedLengthStream = class extends TransformStream {
    constructor(length) {
      let written = 0
      super({
        transform(bytes, controller) {
          written += bytes.byteLength
          if (written > length) throw new Error('Fixed length overflow')
          controller.enqueue(bytes)
        },
        flush() { if (written !== length) throw new Error('Fixed length truncation') },
      })
    }
  }
})
after(() => { globalThis.FixedLengthStream = originalFixedLengthStream })

let root, assets, worker, originals
before(async () => {
  root = await mkdtemp(join(tmpdir(), 'deployment-transport-'))
  await mkdir(join(root, 'assets'))
  originals = {
    '/assets/source-track.js': Buffer.from(`export default ${JSON.stringify('source diagnostic '.repeat(1_600_000))};\n`),
    '/model.glb': Buffer.concat([Buffer.from('glTF'), Buffer.alloc(26 * 1024 * 1024, 7)]),
  }
  for (const [route, bytes] of Object.entries(originals)) await writeFile(join(root, route.slice(1)), bytes)
  await writeFile(join(root, 'assets/small.js'), 'export default 1;')
  assets = await splitOversizedAssets(root)
  worker = createAssetWorker({ assets })
})
after(async () => { await rm(root, { recursive: true, force: true }) })

function binding(alter) {
  const calls = []
  return { calls, ASSETS: { async fetch(request) {
    calls.push(request)
    const path = new URL(request.url).pathname
    const bytes = await readFile(join(root, path.slice(1)))
    const replacement = await alter?.(request, bytes, calls.length)
    return replacement ?? new Response(bytes, { headers: { 'Content-Length': String(bytes.length) } })
  } } }
}
const request = (route, coding, extra = {}, method = 'GET') => new Request(`https://example.test${route}?cache=1`, {
  method, headers: { ...(coding === null ? {} : { 'Accept-Encoding': coding }), ...extra },
})

test('negotiates explicit refusal, wildcard precedence, qualities and identity default', () => {
  const variants = { gzip: {}, identity: {} }
  for (const [header, expected] of [
    [null, 'identity'], ['', 'identity'], ['gzip', 'gzip'], ['GZIP; Q=1', 'gzip'],
    ['gzip;q=0, *;q=1', 'identity'], ['*;q=0, gzip;q=1', 'gzip'],
    ['gzip;q=0.5', 'identity'], ['gzip;q=0.5, identity;q=0.1', 'gzip'],
    ['gzip;q=0, identity;q=0', null], ['br, *;q=0', null],
    ['*;q=0, identity;q=1', 'identity'], ['gzip;q=invalid', 'identity'],
    ['gzip;q=1, gzip;q=0', 'identity'],
  ]) assert.equal(negotiateCoding(header, variants), expected, header)
})

test('actual producer artifacts preserve decoded GLB and module bytes and sealed digests', async () => {
  await verifyTransportAssets(root, assets)
  assert.equal(assets['/assets/small.js'], undefined)
  for (const [route, original] of Object.entries(originals)) {
    const asset = assets[route]
    assert.equal(asset.sha256, createHash('sha256').update(original).digest('hex'))
    assert.ok(asset.variants.gzip.byteLength < asset.byteLength)
    assert.ok(asset.variants.identity.chunks.length > 1)
    for (const coding of ['gzip', 'identity']) {
      const env = binding()
      const response = await worker.fetch(request(route, coding), env)
      const encoded = Buffer.from(await response.arrayBuffer())
      assert.equal(response.status, 200)
      assert.equal(response.headers.get('content-length'), String(encoded.length))
      assert.equal(response.headers.get('content-encoding'), coding === 'gzip' ? 'gzip' : null)
      assert.equal(response.headers.get('vary'), 'Accept-Encoding')
      assert.match(response.headers.get('cache-control'), /no-transform/)
      assert.deepEqual(coding === 'gzip' ? gunzipSync(encoded) : encoded, original)
      assert.equal(createHash('sha256').update(encoded).digest('hex'), asset.variants[coding].sha256)
      for (const call of env.calls) {
        assert.equal(call.headers.get('accept-encoding'), 'identity')
        assert.equal(call.headers.get('range'), null)
        assert.equal(call.headers.get('if-none-match'), null)
        assert.equal(new URL(call.url).search, '')
      }
    }
  }
})

test('HEAD, variant-specific validators, refusal and methods do not fetch chunks', async () => {
  const route = '/model.glb'
  const env = binding()
  const head = await worker.fetch(request(route, 'gzip', {}, 'HEAD'), env)
  assert.equal(head.body, null)
  assert.equal(head.headers.get('content-length'), String(assets[route].variants.gzip.byteLength))
  const tag = head.headers.get('etag')
  for (const candidate of [tag, `W/${tag}`, '*', `"other", ${tag}`]) {
    const response = await worker.fetch(request(route, 'gzip', { 'If-None-Match': candidate }), env)
    assert.equal(response.status, 304)
    assert.equal(response.headers.get('vary'), 'Accept-Encoding')
  }
  assert.equal(env.calls.length, 0)
  const identity = await worker.fetch(request(route, 'identity', { 'If-None-Match': tag }, 'HEAD'), env)
  assert.equal(identity.status, 200)
  assert.notEqual(identity.headers.get('etag'), tag)
  assert.equal((await worker.fetch(request(route, 'gzip;q=0, identity;q=0'), env)).status, 406)
  assert.equal((await worker.fetch(request(route, 'gzip', {}, 'POST'), env)).status, 405)
  assert.equal(env.calls.length, 0)
})

test('unreconstructed routes pass the exact request through ASSETS', async () => {
  const input = request('/assets/small.js', 'gzip', { Range: 'bytes=0-9' })
  let forwarded
  const response = new Response('native')
  assert.equal(await worker.fetch(input, { ASSETS: { fetch(value) { forwarded = value; return response } } }), response)
  assert.equal(forwarded, input)
})

test('missing first chunk, incorrect length, or unexpected binding encoding fails closed', async () => {
  for (const replacement of [
    () => new Response('missing', { status: 404 }),
    () => new Response('wrong', { headers: { 'Content-Length': '5' } }),
    (_request, bytes) => new Response(bytes, { headers: { 'Content-Encoding': 'gzip' } }),
  ]) {
    const response = await worker.fetch(request('/model.glb', 'gzip'), binding(replacement))
    assert.equal(response.status, 502)
    assert.equal(response.headers.get('cache-control'), 'no-store')
  }
})

test('later chunk failures and unannounced truncated bodies abort response consumption', async () => {
  for (const alter of [
    (_request, _bytes, index) => index === 2 ? new Response('missing', { status: 404 }) : undefined,
    (_request, bytes) => new Response(bytes.subarray(0, bytes.length - 1)),
  ]) {
    const response = await worker.fetch(request('/model.glb', 'identity'), binding(alter))
    await assert.rejects(response.arrayBuffer())
  }
})

test('producer verification independently detects sealed corruption and decoded mismatch', async () => {
  const invalid = structuredClone(assets)
  invalid['/model.glb'].variants.gzip.sha256 = '0'.repeat(64)
  await assert.rejects(verifyTransportAssets(root, invalid), /exact original/)
  const invalidDecoded = structuredClone(assets)
  invalidDecoded['/model.glb'].sha256 = '0'.repeat(64)
  await assert.rejects(verifyTransportAssets(root, invalidDecoded), /exact original/)
  const chunk = assets['/model.glb'].variants.gzip.chunks[0]
  const path = join(root, chunk.path.slice(1))
  const original = await readFile(path)
  try {
    await writeFile(path, Buffer.alloc(original.length))
    await assert.rejects(verifyTransportAssets(root, assets), /absent or corrupt/)
  } finally { await writeFile(path, original) }
})
