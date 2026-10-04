import test from 'node:test'
import assert from 'node:assert/strict'
import { createHash } from 'node:crypto'
import { Agent, createServer, request } from 'node:http'
import { connect } from 'node:net'
import { mkdtemp, readdir, readFile, writeFile, rm } from 'node:fs/promises'
import { tmpdir } from 'node:os'
import { join } from 'node:path'
import { createNativeByteStore } from './native-byte-store.mjs'

const hash = bytes => createHash('sha256').update(bytes).digest('hex')
const payload = Buffer.from([0, 255, 1, 128, 42, 0, 7, 99])

async function fixture(t, options = {}) {
  const root = await mkdtemp(join(tmpdir(), 'native-byte-store-test-'))
  const store = createNativeByteStore({ root, token: 'test-only-opaque-token', maxObjectBytes: 32, ...options })
  let nextHandled
  const server = createServer(async (req, res) => {
    const finished = nextHandled
    nextHandled = undefined
    try {
      if (!await store.handleRequest(req, res)) { res.statusCode = 404; res.end() }
    } finally { finished?.() }
  })
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve))
  const port = server.address().port
  const agent = new Agent({ keepAlive: true, maxSockets: 1 })
  t.after(async () => {
    await store.close({ removeRetained: true })
    agent.destroy()
    await new Promise(resolve => server.close(resolve))
    await rm(root, { recursive: true, force: true }) // Only this test's mkdtemp.
  })
  function post(bytes, { path = store.endpoint + hash(bytes), method = 'POST', headers = {} } = {}) {
    return new Promise((resolve, reject) => {
      const framing = headers['Transfer-Encoding'] === undefined ? { 'Content-Length': String(bytes.byteLength) } : {}
      const req = request({ agent, host: '127.0.0.1', port, path, method, headers: { 'Content-Type': 'application/octet-stream', ...framing, ...headers } }, res => {
        const chunks = []
        res.on('data', chunk => chunks.push(chunk))
        res.on('end', () => resolve({ status: res.statusCode, headers: res.headers, body: Buffer.concat(chunks).toString() }))
      })
      req.on('error', error => {
        error.message = `${method} ${path}: ${error.message}`
        reject(error)
      })
      req.end(bytes)
    })
  }
  return { root, store, port, post, handled: () => new Promise(resolve => { nextHandled = resolve }) }
}

test('actual streamed binary bytes are hashed, deduplicated and released only after consumption', async t => {
  const { store, post, root, port } = await fixture(t)
  const response = await post(payload, { headers: { Origin: `http://127.0.0.1:${port}` } })
  assert.equal(response.status, 201)
  assert.deepEqual(JSON.parse(response.body), { sha256: hash(payload), byteLength: payload.length, retention: 'transient' })
  assert.deepEqual(await store.get(hash(payload)), payload)
  const [runDirectory] = await readdir(root)
  assert.deepEqual(await readdir(join(root, runDirectory)), [hash(payload)])
  assert.equal((await post(payload)).status, 201)
  assert.deepEqual(await readdir(join(root, runDirectory)), [hash(payload)])
  await store.release(hash(payload))
  assert.equal(await store.has(hash(payload)), false)
  await assert.rejects(store.get(hash(payload)), { code: 'object-unavailable' })
})

test('wrong digest and short declared body never commit an object', async t => {
  const { store, post, root, port, handled } = await fixture(t)
  const wrong = hash(Buffer.from('not the uploaded body'))
  const response = await post(payload, { path: store.endpoint + wrong })
  assert.equal(response.status, 422)
  assert.deepEqual(JSON.parse(response.body), { error: 'sha256-mismatch' })
  assert.equal(await store.has(wrong), false)
  const done = handled()
  const socket = connect({ host: '127.0.0.1', port })
  socket.on('error', () => {})
  await new Promise(resolve => socket.once('connect', resolve))
  socket.end(`POST ${store.endpoint}${hash(payload)} HTTP/1.1\r\nHost: 127.0.0.1:${port}\r\nContent-Type: application/octet-stream\r\nContent-Length: ${payload.length + 1}\r\nConnection: close\r\n\r\n` + payload.toString('latin1'), 'latin1')
  await done
  socket.destroy()
  assert.equal(await store.has(hash(payload)), false)
  const [runDirectory] = await readdir(root)
  assert.deepEqual(await readdir(join(root, runDirectory)), [])
})

test('raw path, token, method, origin and media-type boundaries reject uploads', async t => {
  const { store, post, port } = await fixture(t)
  for (const suffix of ['../escape', '%2e%2e%2fescape', hash(payload) + '?claim=pass', hash(payload) + '/extra', hash(payload).toUpperCase()]) {
    assert.equal((await post(payload, { path: store.endpoint + suffix })).status, 400)
  }
  assert.equal((await post(payload, { path: '/__native-qualification/foreign/' + hash(payload) })).status, 404)
  assert.equal((await post(payload, { method: 'GET' })).status, 405)
  assert.equal((await post(payload, { headers: { Origin: 'https://unapproved.example' } })).status, 403)
  assert.equal((await post(payload, { headers: { Host: 'unapproved.example:1', Origin: 'http://unapproved.example:1' } })).status, 403)
  assert.equal((await post(payload, { headers: { Host: `unapproved.example:${port}`, Origin: `http://unapproved.example:${port}` } })).status, 403)
  assert.equal((await post(payload, { headers: { Host: `localhost:${port}`, Origin: `http://localhost:${port}` } })).status, 403)
  assert.equal((await post(payload, { headers: { Origin: 'null' } })).status, 403)
  assert.equal((await post(payload, { headers: { 'Content-Type': 'application/json' } })).status, 415)
  assert.equal((await post(payload, { headers: { 'Content-Encoding': 'gzip' } })).status, 415)
  assert.equal((await post(payload, { headers: { 'X-Native-Retention': 'pass' } })).status, 400)
  assert.equal(await store.has(hash(payload)), false)
  assert.equal((await post(payload, { headers: { Origin: `http://127.0.0.1:${port}` } })).status, 201)
  assert.deepEqual(await store.get(hash(payload)), payload)
})

test('explicit expected origin admits only that origin including preflight', async t => {
  const { post, port } = await fixture(t, { allowedOrigin: 'https://qualification.example' })
  assert.equal((await post(payload, { headers: { Origin: `http://127.0.0.1:${port}` } })).status, 403)
  const preflight = await post(Buffer.alloc(0), { method: 'OPTIONS', headers: { Origin: 'https://qualification.example' } })
  assert.equal(preflight.status, 204)
  assert.equal(preflight.headers['access-control-allow-origin'], 'https://qualification.example')
  assert.equal((await post(payload, { headers: { Origin: 'https://qualification.example' } })).status, 201)
})

test('both length-declared and chunked oversize bodies leave no CAS or temporary file', async t => {
  const { post, store, root } = await fixture(t)
  const large = Buffer.alloc(33, 123)
  assert.equal((await post(large, { headers: { 'Content-Length': '33' } })).status, 413)
  assert.equal((await post(large, { headers: { 'Transfer-Encoding': 'chunked' } })).status, 413)
  assert.equal(await store.has(hash(large)), false)
  const [runDirectory] = await readdir(root)
  assert.deepEqual(await readdir(join(root, runDirectory)), [])
})

test('selected/static/reference archives survive normal close; old files never establish availability', async t => {
  const { store, root } = await fixture(t)
  await writeFile(join(root, 'unrelated-report.json'), '{"pass":true}')
  await writeFile(join(root, hash(payload)), payload)
  assert.equal(await store.has(hash(payload)), false)
  const selected = await store.put(payload)
  assert.equal((await store.retain(selected.sha256)).retention, 'selected-case')
  const staticBytes = Buffer.from('static attributes')
  const referenceBytes = Buffer.from('independent reference')
  await store.put(staticBytes, { retention: 'static' })
  await store.put(referenceBytes, { retention: 'reference' })
  const temporaryBytes = Buffer.from('unretained output')
  await store.put(temporaryBytes)
  for (const bytes of [payload, staticBytes, referenceBytes]) {
    await store.release(hash(bytes))
    assert.deepEqual(await store.get(hash(bytes)), bytes)
  }
  const runDirectory = (await readdir(root)).find(name => name.startsWith('native-bytes-'))
  await writeFile(join(root, runDirectory, 'foreign-file'), 'not ours')
  await store.close()
  assert.deepEqual((await readdir(join(root, runDirectory))).sort(), [hash(payload), hash(staticBytes), hash(referenceBytes), 'foreign-file'].sort())
  assert.equal(await readFile(join(root, 'unrelated-report.json'), 'utf8'), '{"pass":true}')
  assert.deepEqual(await readFile(join(root, hash(payload))), payload)
  await assert.rejects(store.get(hash(payload)), { code: 'store-closed' })
  await assert.rejects(store.put(payload), { code: 'store-closed' })
})

test('changed or truncated stored bytes cannot satisfy get', async t => {
  const { store, root } = await fixture(t)
  const entry = await store.put(payload)
  const [runDirectory] = await readdir(root)
  const path = join(root, runDirectory, entry.sha256)
  await writeFile(path, Buffer.alloc(payload.length, 3))
  await assert.rejects(store.get(entry.sha256), { code: 'object-integrity-failed' })
  await writeFile(path, payload.subarray(0, payload.length - 1))
  await assert.rejects(store.get(entry.sha256), { code: 'object-integrity-failed' })
})

test('close drains accepted writes and explicit cleanup removes only owned archives', async t => {
  const { store, root } = await fixture(t)
  const pending = store.put(payload, { retention: 'selected-case' })
  const closing = store.close({ removeRetained: true })
  assert.deepEqual(await pending, { sha256: hash(payload), byteLength: payload.length, retention: 'selected-case' })
  await closing
  assert.deepEqual(await readdir(root), [])
  await assert.rejects(store.put(payload), { code: 'store-closed' })
})

test('atomic publication never replaces or deletes an unexpected foreign CAS pathname', async t => {
  const { store, root } = await fixture(t)
  const first = await store.put(Buffer.from('initialize owned directory'))
  const [runDirectory] = await readdir(root)
  const foreignPath = join(root, runDirectory, hash(payload))
  await writeFile(foreignPath, 'foreign bytes')
  await assert.rejects(store.put(payload), { code: 'EEXIST' })
  assert.equal(await store.has(hash(payload)), false)
  await store.release(first.sha256)
  await store.close({ removeRetained: true })
  assert.equal(await readFile(foreignPath, 'utf8'), 'foreign bytes')
  assert.deepEqual(await readdir(join(root, runDirectory)), [hash(payload)])
})
