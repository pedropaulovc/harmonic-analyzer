import { open, stat } from 'node:fs/promises'
import { runTool, sha256File } from './verify-reference.mjs'

/** Verify compressed original AVCC access units, not ffprobe's recovery/K flag. */
export function hasIdrAccessUnit(bytes, lengthSize) {
  if (![1, 2, 4].includes(lengthSize)) throw new Error('Unsupported original AVC NAL length size')
  let offset = 0, idr = false, nonIdr = false, vcl = false
  while (offset < bytes.length) {
    if (offset + lengthSize > bytes.length) throw new Error('Truncated original AVC NAL length')
    const length = bytes.readUIntBE(offset, lengthSize)
    offset += lengthSize
    if (!length || offset + length > bytes.length || bytes[offset] & 0x80) throw new Error('Invalid original AVC access unit')
    const type = bytes[offset] & 0x1f
    if (type >= 2 && type <= 4 || type === 5 && !(bytes[offset] & 0x60)) throw new Error('Unsupported original AVC picture header')
    if (type === 5) idr = true
    if (type === 1) nonIdr = true
    if (type === 1 || type === 5) vcl = true
    offset += length
  }
  if (!vcl) throw new Error('Unsupported original packet without an AVC picture')
  if (idr && nonIdr) throw new Error('Unsupported mixed original AVC access unit')
  return idr
}

export function sameOriginalFile(a, b) {
  return a.dev === b.dev && a.ino === b.ino && a.size === b.size && a.mtimeMs === b.mtimeMs && a.ctimeMs === b.ctimeMs
}

/** Eager, bounded preparation before HTTP readiness; no frame decode or media derivative. */
export async function originalAccessIndex(path, videoId, { signal } = {}) {
  const before = await stat(path)
  const sha256 = await sha256File(path)
  const { stdout } = await runTool('ffprobe', ['-v', 'error', '-select_streams', 'v:0', '-show_streams', '-show_packets', '-show_entries', 'stream=codec_name,is_avc,nal_length_size,time_base:packet=pts,pos,size', '-of', 'json', path], { signal })
  const probe = JSON.parse(stdout), stream = probe.streams?.[0]
  const timeBase = (stream?.time_base ?? '').split('/').map(Number)
  const lengthSize = Number(stream?.nal_length_size)
  if (stream?.codec_name !== 'h264' || stream.is_avc !== 'true' || timeBase.length !== 2 || timeBase.some(n => !Number.isSafeInteger(n) || n <= 0) || ![1, 2, 4].includes(lengthSize)) throw new Error(`Unsupported original native safe-access format: ${videoId}; requires timestamped H264 AVCC`)
  const packets = probe.packets ?? []
  if (!packets.length) throw new Error(`Original native safe-access index has no packets: ${videoId}`)
  let maximum = 0
  for (const packet of packets) {
    packet.pos = Number(packet.pos); packet.size = Number(packet.size)
    if (!Number.isSafeInteger(packet.pts) || packet.pts < 0 || !Number.isSafeInteger(packet.pos) || packet.pos < 0 || !Number.isSafeInteger(packet.size) || packet.size <= 0 || packet.pos + packet.size > before.size) throw new Error(`Unsupported original packet timestamps/extent: ${videoId}`)
    maximum = Math.max(maximum, packet.size)
  }
  const bytes = Buffer.allocUnsafe(maximum), idrPts = [], handle = await open(path, 'r')
  try {
    for (const packet of packets) {
      signal?.throwIfAborted()
      const { bytesRead } = await handle.read(bytes, 0, packet.size, packet.pos)
      if (bytesRead !== packet.size) throw new Error(`Original packet changed during indexing: ${videoId}`)
      if (hasIdrAccessUnit(bytes.subarray(0, packet.size), lengthSize)) idrPts.push(packet.pts)
    }
  } finally { await handle.close() }
  const pts = packets.map(packet => packet.pts).sort((a, b) => a - b)
  idrPts.sort((a, b) => a - b)
  if (pts.some((value, i) => i && value <= pts[i - 1]) || !idrPts.length || idrPts[0] !== pts[0]) throw new Error(`Original has unsupported ambiguous/pre-IDR presentation timestamps: ${videoId}`)
  const identity = await stat(path)
  if (!sameOriginalFile(before, identity)) throw new Error(`Original changed while preparing safe access: ${videoId}`)
  return { identity, index: { schemaVersion: 1, kind: 'original-h264-idr-access-index', source: { videoId, sha256, bytes: before.size }, timeBase, pts, idrPts } }
}
