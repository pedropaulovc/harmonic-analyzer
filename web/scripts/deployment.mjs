#!/usr/bin/env node
import { createHash } from 'node:crypto'
import { execFileSync } from 'node:child_process'
import { createWriteStream } from 'node:fs'
import { copyFile, mkdir, readFile, readdir, rename, rm, stat, writeFile } from 'node:fs/promises'
import { dirname, join, resolve } from 'node:path'
import { Readable, Transform } from 'node:stream'
import { pipeline } from 'node:stream/promises'
import { fileURLToPath } from 'node:url'
import { DEPLOYMENT_MODEL, MODEL_RELEASE_URL } from '../deployment-model.mjs'
import { assertNativeSourceAssociation } from '../model-representation.mjs'
import { nativeProvenanceFromModule } from './fetch-model.mjs'
import { ASSET_LIMIT, splitOversizedAssets, verifyTransportAssets } from './deployment-transport.mjs'

const WEB = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const DIST = join(WEB, 'dist')
const LIMIT = ASSET_LIMIT
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
  await verifyTransportAssets(DIST, manifest.assets)
}

try {
  const command = process.argv[2]
  if (process.argv.length !== 3 || !['fetch-model', 'build', 'deploy', 'preview'].includes(command)) {
    throw new Error('Usage: node scripts/deployment.mjs fetch-model|build|deploy|preview')
  }
  const expected = command === 'fetch-model' ? undefined : identity()
  if (command === 'fetch-model') {
    await verifyReleasedModel()
  } else if (command === 'build') {
    // Original footage is a local, explicitly opt-in verification input, not a
    // deployment asset. Fail rather than accidentally publish copyrighted media.
    try {
      await stat(join(WEB, 'public/reference-media'))
      throw new Error('public/reference-media is local verification footage; remove it from the deployment checkout before building')
    } catch (error) {
      if (error.code !== 'ENOENT') throw error
    }
    const approvedModel = await verifyReleasedModel()
    run('npm', ['run', 'test:performance'], { ...process.env, SPRING_MODEL_PATH: approvedModel })
    run('npm', ['run', 'build'], { ...process.env, SIMULATOR_BASE: '/' })
    const modelPath = join(DIST, DEPLOYMENT_MODEL.representation.path)
    await mkdir(dirname(modelPath), { recursive: true })
    await copyFile(approvedModel, modelPath)
    const assets = await splitOversizedAssets(DIST)
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
