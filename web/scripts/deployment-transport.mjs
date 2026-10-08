import { createHash } from 'node:crypto'
import { createReadStream, createWriteStream } from 'node:fs'
import { mkdir, open, readdir, rm, stat, writeFile } from 'node:fs/promises'
import { extname, join, relative } from 'node:path'
import { Readable } from 'node:stream'
import { pipeline } from 'node:stream/promises'
import { createGzip, createGunzip } from 'node:zlib'

export const ASSET_LIMIT = 25 * 1024 * 1024
const CHUNK_SIZE = 24 * 1024 * 1024
const contentTypes = {
  '.js': 'text/javascript; charset=utf-8', '.mjs': 'text/javascript; charset=utf-8',
  '.json': 'application/json', '.glb': 'model/gltf-binary', '.wasm': 'application/wasm',
  '.css': 'text/css; charset=utf-8', '.html': 'text/html; charset=utf-8',
}
export async function hashFile(path) {
  const hash = createHash('sha256')
  for await (const bytes of createReadStream(path)) hash.update(bytes)
  return hash.digest('hex')
}

async function sealVariant(root, sourcePath, decodedSha, coding) {
  const byteLength = (await stat(sourcePath)).size
  const sha256 = await hashFile(sourcePath)
  const directory = join(root, 'deployment-assets', decodedSha, coding)
  await mkdir(directory, { recursive: true })
  const source = await open(sourcePath, 'r')
  const chunks = []
  const buffer = Buffer.allocUnsafe(Math.min(CHUNK_SIZE, byteLength))
  try {
    for (let offset = 0; offset < byteLength;) {
      const length = Math.min(CHUNK_SIZE, byteLength - offset)
      let filled = 0
      while (filled < length) {
        const { bytesRead } = await source.read(buffer, filled, length - filled, offset + filled)
        if (!bytesRead) throw new Error(`Asset changed or ended while splitting: ${sourcePath}`)
        filled += bytesRead
      }
      const bytes = buffer.subarray(0, length)
      const name = `${chunks.length}.bin`
      await writeFile(join(directory, name), bytes)
      chunks.push({ path: `/deployment-assets/${decodedSha}/${coding}/${name}`, byteLength: length,
        sha256: createHash('sha256').update(bytes).digest('hex') })
      offset += length
    }
  } finally { await source.close() }
  return { byteLength, sha256, chunks }
}

// Validate sealed bytes independently from the writer and verify gzip decoding
// against the approved decoded digest, before removing any original input.
export async function verifyTransportAssets(root, assets) {
  for (const asset of Object.values(assets)) {
    for (const [coding, variant] of Object.entries(asset.variants)) {
      if (!['identity', 'gzip'].includes(coding)) throw new Error(`Unsupported transport coding: ${coding}`)
      const encoded = createHash('sha256')
      let total = 0
      async function* pieces() {
        for (const chunk of variant.chunks) {
          const path = join(root, chunk.path.slice(1))
          if ((await stat(path)).size !== chunk.byteLength || await hashFile(path) !== chunk.sha256) {
            throw new Error(`Deployment transport chunk is absent or corrupt: ${path}`)
          }
          for await (const bytes of createReadStream(path)) {
            total += bytes.length
            encoded.update(bytes)
            yield bytes
          }
        }
      }
      let stream = Readable.from(pieces())
      if (coding === 'gzip') stream = stream.compose(createGunzip())
      const decoded = createHash('sha256')
      let decodedLength = 0
      for await (const bytes of stream) { decoded.update(bytes); decodedLength += bytes.length }
      if (total !== variant.byteLength || encoded.digest('hex') !== variant.sha256
        || decodedLength !== asset.byteLength || decoded.digest('hex') !== asset.sha256) {
        throw new Error('Deployment chunks do not reconstruct the exact original runtime asset')
      }
    }
  }
}

export async function splitOversizedAssets(root, { limit = ASSET_LIMIT } = {}) {
  const assets = {}
  async function visit(directory) {
    for (const entry of await readdir(directory, { withFileTypes: true })) {
      if (directory === root && entry.name === 'deployment-assets') continue
      const path = join(directory, entry.name)
      if (entry.isDirectory()) { await visit(path); continue }
      const byteLength = (await stat(path)).size
      if (byteLength <= limit) continue
      const sha256 = await hashFile(path)
      const route = `/${relative(root, path).split('\\').join('/')}`
      const variants = { identity: await sealVariant(root, path, sha256, 'identity') }
      // Compress only runtime model/module formats with demonstrated savings;
      // native provenance and decoded module bytes are never rewritten.
      if (['.glb', '.js', '.mjs'].includes(extname(path))) {
        const temporary = `${path}.transport-gzip`
        try {
          await pipeline(createReadStream(path), createGzip({ level: 6 }), createWriteStream(temporary, { flags: 'wx' }))
          if ((await stat(temporary)).size < byteLength) variants.gzip = await sealVariant(root, temporary, sha256, 'gzip')
        } finally { await rm(temporary, { force: true }) }
      }
      const asset = { byteLength, sha256, contentType: contentTypes[extname(path)] ?? 'application/octet-stream', variants }
      await verifyTransportAssets(root, { [route]: asset })
      assets[route] = asset
      await rm(path)
      console.log(`Sealed ${route}: identity ${byteLength} bytes${variants.gzip ? `; gzip ${variants.gzip.byteLength} bytes` : ''}`)
    }
  }
  await visit(root)
  return assets
}
