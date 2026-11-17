#!/usr/bin/env node
/**
 * Cloudflare Workers build (native Git integration) and manual deploys.
 *   node scripts/deployment.mjs build     # fetch the model, vite build, chunk assets over 25 MiB
 *   node scripts/deployment.mjs deploy    # main only, production worker
 *   node scripts/deployment.mjs preview   # PPE preview named after the branch
 */
import { execFileSync } from 'node:child_process'
import { readFile, readdir, stat, writeFile } from 'node:fs/promises'
import { dirname, join, resolve } from 'node:path'
import { fileURLToPath } from 'node:url'
import { fetchModel } from './fetch-model.mjs'
import { ASSET_LIMIT, splitOversizedAssets, verifyTransportAssets } from './deployment-transport.mjs'

const WEB = resolve(dirname(fileURLToPath(import.meta.url)), '..')
const DIST = join(WEB, 'dist')
const ASSET_MANIFEST = join(WEB, '.vite/deployment-assets.json')
const MODEL_ROUTE = '/models/ha-harmonic-analyzer.glb'
const run = (binary, args) => execFileSync(binary, args, { cwd: WEB, stdio: 'inherit' })
const git = (...args) => execFileSync('git', args, { cwd: WEB, encoding: 'utf8' }).trim()

function identity() {
  const commitSha = process.env.WORKERS_CI_COMMIT_SHA ?? git('rev-parse', 'HEAD')
  const branch = process.env.WORKERS_CI_BRANCH ?? git('branch', '--show-current')
  if (!/^[0-9a-f]{40}$/.test(commitSha)) throw new Error('WORKERS_CI_COMMIT_SHA must be the full Git commit SHA')
  if (!branch) throw new Error('Set WORKERS_CI_BRANCH when building from a detached HEAD')
  return { commitSha, branch }
}

async function assertAssetSizes(directory = DIST) {
  for (const entry of await readdir(directory, { withFileTypes: true })) {
    const path = join(directory, entry.name)
    if (entry.isDirectory()) await assertAssetSizes(path)
    else if ((await stat(path)).size > ASSET_LIMIT) throw new Error(`Workers Assets limit is 25 MiB: ${path} is larger`)
  }
}

async function assertDeployable(expected) {
  const actual = JSON.parse(await readFile(join(DIST, 'deployment.json'), 'utf8'))
  if (actual.commitSha !== expected.commitSha || actual.branch !== expected.branch) {
    throw new Error('dist/deployment.json does not match this commit and branch; run npm run build:deploy first')
  }
  await assertAssetSizes()
  const manifest = JSON.parse(await readFile(ASSET_MANIFEST, 'utf8'))
  if (manifest.commitSha !== expected.commitSha || !manifest.assets?.[MODEL_ROUTE]) throw new Error('Deployment chunk manifest is absent or stale; run npm run build:deploy first')
  await verifyTransportAssets(DIST, manifest.assets)
}

try {
  const command = process.argv[2]
  if (!['build', 'deploy', 'preview'].includes(command)) throw new Error('Usage: node scripts/deployment.mjs build|deploy|preview')
  const expected = identity()
  if (command === 'build') {
    // fetchModel writes public/models, which vite copies into dist.
    await fetchModel()
    run('npm', ['run', 'build'])
    const assets = await splitOversizedAssets(DIST)
    await writeFile(ASSET_MANIFEST, `${JSON.stringify({ ...expected, assets }, null, 2)}\n`)
    await writeFile(join(DIST, 'deployment.json'), `${JSON.stringify(expected)}\n`)
    await assertDeployable(expected)
  } else {
    await assertDeployable(expected)
    if (command === 'deploy') {
      if (expected.branch !== 'main') throw new Error('Production publishes main only; use npm run deploy:preview for other branches')
      run(process.execPath, ['node_modules/wrangler/bin/wrangler.js', 'deploy', '--config', 'wrangler.jsonc'])
    } else {
      run(process.execPath, ['node_modules/wrangler/bin/wrangler.js', 'preview', '--config', 'wrangler.ppe.jsonc', '--name', expected.branch])
    }
  }
} catch (error) {
  console.error(`Deployment failed: ${error.message}`)
  process.exitCode = 1
}
