#!/usr/bin/env node
import { createHash } from 'node:crypto'
import { execFileSync } from 'node:child_process'
import { createReadStream, createWriteStream } from 'node:fs'
import { copyFile, mkdir, open, readFile, readdir, rename, rm, stat, writeFile } from 'node:fs/promises'
import { dirname, extname, join, relative, resolve } from 'node:path'
import { Readable, Transform } from 'node:stream'
import { pipeline } from 'node:stream/promises'
import { fileURLToPath } from 'node:url'
import { DEPLOYMENT_MODEL, MODEL_RELEASE_URL } from '../deployment-model.mjs'
import { assertNativeSourceAssociation } from '../model-representation.mjs'
import { nativeProvenanceFromModule } from './fetch-model.mjs'

const WEB = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const DIST = join(WEB, 'dist')
const LIMIT = 25 * 1024 * 1024
const CHUNK_SIZE = 24 * 1024 * 1024
const ASSET_MANIFEST = join(WEB, '.vite/deployment-assets.json')
const run = (binary, args, env = process.env) => execFileSync(binary, args, { cwd: WEB, env, stdio: 'inherit' })
const git = (...args) => execFileSync('git', args, { cwd: WEB, encoding: 'utf8' }).trim()
const identity = () => {
  const commitSha = process.env.WORKERS_CI_COMMIT_SHA ?? git('rev-parse', 'HEAD')
  const branch = process.env.WORKERS_CI_BRANCH ?? git('branch', '--show-current')
  if (!/^[0-9a-f]{40}$/.test(commitSha)) throw new Error('WORKERS_CI_COMMIT_SHA must be the exact full Git commit SHA')
  if (!branch) throw new Error('Set WORKERS_CI_BRANCH when building from detached HEAD; a branch preview must have its actual branch name')
  return { commitSha, branch }
}

async function verifyReleasedModel() {
  const model = DEPLOYMENT_MODEL.representation
  assertNativeSourceAssociation(DEPLOYMENT_MODEL, nativeProvenanceFromModule(await readFile(join(WEB, 'src/mechanics-data.ts'), 'utf8')))
  const cache = join(WEB, '.vite/deployment-model')
  await mkdir(cache, { recursive: true })
  const temporary = join(cache, `${model.sha256}.${process.pid}.download`)
  try {
    const response = await fetch(MODEL_RELEASE_URL, { signal: AbortSignal.timeout(180_000) })
    if (response.status !== 200 || !response.body) {
      await response.body?.cancel()
      throw new Error(`Approved optimized model is absent: HTTP ${response.status} at ${MODEL_RELEASE_URL}. Publish the exact approved SHA-named v39 asset; a model-less deployment is not permitted.`)
    }
    const hash = createHash('sha256')
    let byteLength = 0
    await pipeline(Readable.fromWeb(response.body), new Transform({
      transform(chunk, _encoding, callback) {
        byteLength += chunk.length
        if (byteLength > model.byteLength) return callback(new Error('Released model exceeds the approved byte length'))
        hash.update(chunk)
        callback(null, chunk)
      },
    }), createWriteStream(temporary, { flags: 'wx' }))
    const digest = hash.digest('hex')
    if (byteLength !== model.byteLength || digest !== model.sha256) {
      throw new Error(`Released model mismatch: ${digest} (${byteLength} bytes); expected ${model.sha256} (${model.byteLength} bytes)`)
    }
    const destination = join(cache, `${model.sha256}.glb`)
    await rename(temporary, destination)
    console.log(`Approved model verified: ${model.sha256} (${byteLength} bytes); ready for lossless static chunking`)
    return destination
  } finally {
    await rm(temporary, { force: true })
  }
}

async function assertAssetSizes(directory = DIST) {
  for (const entry of await readdir(directory, { withFileTypes: true })) {
    const path = join(directory, entry.name)
    if (entry.isDirectory()) await assertAssetSizes(path)
    else {
      const bytes = (await stat(path)).size
      if (bytes > LIMIT) throw new Error(`Workers Assets limit is 25 MiB: ${path} is ${bytes} bytes. Do not omit a runtime asset to hide this failure.`)
    }
  }
}

const contentTypes = {
  '.js': 'text/javascript; charset=utf-8', '.mjs': 'text/javascript; charset=utf-8',
  '.json': 'application/json', '.glb': 'model/gltf-binary', '.wasm': 'application/wasm',
  '.css': 'text/css; charset=utf-8', '.html': 'text/html; charset=utf-8',
  '.svg': 'image/svg+xml', '.png': 'image/png', '.jpg': 'image/jpeg',
  '.jpeg': 'image/jpeg', '.webp': 'image/webp', '.woff2': 'font/woff2',
}

async function hashFile(path) {
  const hash = createHash('sha256')
  for await (const bytes of createReadStream(path)) hash.update(bytes)
  return hash.digest('hex')
}

async function splitOversizedAssets(directory = DIST, assets = {}) {
  for (const entry of await readdir(directory, { withFileTypes: true })) {
    // This directory contains generated transport pieces, never runtime inputs.
    if (directory === DIST && entry.name === 'deployment-assets') continue
    const path = join(directory, entry.name)
    if (entry.isDirectory()) await splitOversizedAssets(path, assets)
    else {
      const byteLength = (await stat(path)).size
      if (byteLength <= LIMIT) continue
      const sha256 = await hashFile(path)
      const route = `/${relative(DIST, path).split('\\').join('/')}`
      const chunkDirectory = join(DIST, 'deployment-assets', sha256)
      await mkdir(chunkDirectory, { recursive: true })
      const source = await open(path, 'r')
      const chunks = []
      const buffer = Buffer.allocUnsafe(CHUNK_SIZE)
      try {
        for (let offset = 0; offset < byteLength;) {
          const length = Math.min(CHUNK_SIZE, byteLength - offset)
          let filled = 0
          while (filled < length) {
            const { bytesRead } = await source.read(buffer, filled, length - filled, offset + filled)
            if (bytesRead === 0) throw new Error(`Asset changed or ended while splitting: ${path}`)
            filled += bytesRead
          }
          const bytes = buffer.subarray(0, length)
          const name = `${chunks.length}.bin`
          await writeFile(join(chunkDirectory, name), bytes)
          chunks.push({
            path: `/deployment-assets/${sha256}/${name}`, byteLength: length,
            sha256: createHash('sha256').update(bytes).digest('hex'),
          })
          offset += length
        }
      } finally {
        await source.close()
      }
      // Remove the giant file only after every exact transport piece exists.
      assets[route] = {
        byteLength, sha256, contentType: contentTypes[extname(path)] ?? 'application/octet-stream',
        chunks,
      }
      await rm(path)
      console.log(`Chunked ${route}: ${byteLength} bytes into ${chunks.length} static assets`)
    }
  }
  return assets
}

async function assertDeployable(expected) {
  const actual = JSON.parse(await readFile(join(DIST, 'deployment.json'), 'utf8'))
  if (actual.commitSha !== expected.commitSha || actual.branch !== expected.branch) {
    throw new Error('dist/deployment.json does not match this commit and branch; run npm run build:deploy first')
  }
  await stat(join(DIST, 'index.html'))
  await assertAssetSizes()
  const manifest = JSON.parse(await readFile(ASSET_MANIFEST, 'utf8'))
  if (manifest.commitSha !== expected.commitSha || manifest.branch !== expected.branch
    || !manifest.assets?.[`/${DEPLOYMENT_MODEL.representation.path}`]) {
    throw new Error('Deployment chunk manifest is absent or stale; run npm run build:deploy first')
  }
  for (const asset of Object.values(manifest.assets)) {
    let total = 0
    const hash = createHash('sha256')
    for (const chunk of asset.chunks) {
      const path = join(DIST, chunk.path.slice(1))
      if ((await stat(path)).size !== chunk.byteLength || await hashFile(path) !== chunk.sha256) {
        throw new Error(`Deployment transport chunk is absent or corrupt: ${path}`)
      }
      for await (const bytes of createReadStream(path)) hash.update(bytes)
      total += chunk.byteLength
    }
    if (total !== asset.byteLength || hash.digest('hex') !== asset.sha256) {
      throw new Error('Deployment chunks do not reconstruct the exact original runtime asset')
    }
  }
}

try {
  const command = process.argv[2]
  if (process.argv.length !== 3 || !['build', 'deploy', 'preview'].includes(command)) {
    throw new Error('Usage: node scripts/deployment.mjs build|deploy|preview')
  }
  const expected = identity()
  if (command === 'build') {
    // Original footage is a local, explicitly opt-in verification input, not a
    // deployment asset. Fail rather than accidentally publish copyrighted media.
    try {
      await stat(join(WEB, 'public/reference-media'))
      throw new Error('public/reference-media is local verification footage; remove it from the deployment checkout before building')
    } catch (error) {
      if (error.code !== 'ENOENT') throw error
    }
    const approvedModel = await verifyReleasedModel()
    run('npm', ['run', 'build'], { ...process.env, SIMULATOR_BASE: '/' })
    const modelPath = join(DIST, DEPLOYMENT_MODEL.representation.path)
    await mkdir(dirname(modelPath), { recursive: true })
    await copyFile(approvedModel, modelPath)
    const assets = await splitOversizedAssets()
    await writeFile(ASSET_MANIFEST, `${JSON.stringify({ ...expected, assets }, null, 2)}\n`)
    await writeFile(join(DIST, 'deployment.json'), `${JSON.stringify(expected)}\n`)
    await assertDeployable(expected)
  } else {
    await assertDeployable(expected)
    if (command === 'deploy') {
      if (expected.branch !== 'main') throw new Error('Production publishes main only; use npm run deploy:preview for PPE branches')
      run(process.execPath, ['node_modules/wrangler/bin/wrangler.js', 'deploy', '--config', 'wrangler.jsonc'])
    } else {
      run(process.execPath, ['node_modules/wrangler/bin/wrangler.js', 'preview', '--config', 'wrangler.ppe.jsonc', '--name', expected.branch])
    }
  }
} catch (error) {
  console.error(`Deployment failed: ${error.message}`)
  process.exitCode = 1
}
