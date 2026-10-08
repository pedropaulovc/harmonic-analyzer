import assert from 'node:assert/strict'
import { inflateSync } from 'node:zlib'

/**
 * Lossless Node pixel adapter for GLTFLoader's embedded native PNG. It is only
 * for CPU geometry tests, not a browser ImageBitmap or a GPU/colour oracle.
 * Unsupported bitmap operations/formats fail instead of inventing an image.
 */
export async function nativeImageBitmap(blob, options = {}) {
  assert.ok(options.imageOrientation === undefined || options.imageOrientation === 'none')
  assert.ok(options.premultiplyAlpha === undefined || options.premultiplyAlpha === 'none')
  assert.ok(options.colorSpaceConversion === undefined || options.colorSpaceConversion === 'none')
  const bytes = Buffer.from(await blob.arrayBuffer())
  assert.ok(bytes.subarray(0, 8).equals(Buffer.from([137, 80, 78, 71, 13, 10, 26, 10])), 'Native bitmap requires actual PNG bytes')
  const compressed = []
  let width, height, channels
  for (let offset = 8; offset < bytes.length;) {
    assert.ok(offset + 12 <= bytes.length, 'Truncated PNG chunk header')
    const length = bytes.readUInt32BE(offset), type = bytes.toString('ascii', offset + 4, offset + 8)
    assert.ok(offset + 12 + length <= bytes.length, 'Truncated PNG chunk data')
    const data = bytes.subarray(offset + 8, offset + 8 + length)
    if (type === 'IHDR') {
      assert.equal(length, 13)
      width = data.readUInt32BE(0); height = data.readUInt32BE(4)
      assert.ok(width > 0 && height > 0 && width <= 16384 && height <= 16384)
      assert.equal(data[8], 8, 'Only the native PNG 8-bit channels are supported')
      assert.ok(data[9] === 2 || data[9] === 6, 'Only RGB/RGBA native PNG pixels are supported')
      channels = data[9] === 2 ? 3 : 4
      assert.deepEqual(Array.from(data.subarray(10)), [0, 0, 0], 'Only the native noninterlaced PNG codec is supported')
    } else if (type === 'IDAT') compressed.push(data)
    else if (type === 'IEND') break
    else if (type === 'tRNS') assert.fail('PNG colour-key transparency requires a separate decoded alpha channel')
    else assert.ok(type === 'PLTE' || type[0] === type[0].toLowerCase(), `Unsupported critical PNG chunk ${type}`)
    offset += 12 + length
  }
  assert.ok(width && height && channels && compressed.length)
  const rowBytes = width * channels
  const filtered = inflateSync(Buffer.concat(compressed), { maxOutputLength: (rowBytes + 1) * height })
  assert.equal(filtered.length, (rowBytes + 1) * height)
  const pixels = new Uint8Array(rowBytes * height)
  for (let y = 0; y < height; y++) {
    const filter = filtered[y * (rowBytes + 1)], row = y * rowBytes
    assert.ok(filter >= 0 && filter <= 4, `Unknown PNG row filter ${filter}`)
    for (let x = 0; x < rowBytes; x++) {
      const left = x >= channels ? pixels[row + x - channels] : 0
      const above = y > 0 ? pixels[row + x - rowBytes] : 0
      const upperLeft = y > 0 && x >= channels ? pixels[row + x - rowBytes - channels] : 0
      let predictor = 0
      if (filter === 1) predictor = left
      else if (filter === 2) predictor = above
      else if (filter === 3) predictor = (left + above) >>> 1
      else if (filter === 4) {
        const p = left + above - upperLeft
        const dl = Math.abs(p - left), da = Math.abs(p - above), du = Math.abs(p - upperLeft)
        predictor = dl <= da && dl <= du ? left : da <= du ? above : upperLeft
      }
      pixels[row + x] = filtered[y * (rowBytes + 1) + 1 + x] + predictor
    }
  }
  const rgba = new Uint8Array(width * height * 4)
  for (let pixel = 0; pixel < width * height; pixel++) {
    rgba[pixel * 4] = pixels[pixel * channels]
    rgba[pixel * 4 + 1] = pixels[pixel * channels + 1]
    rgba[pixel * 4 + 2] = pixels[pixel * channels + 2]
    rgba[pixel * 4 + 3] = channels === 4 ? pixels[pixel * channels + 3] : 255
  }
  return { width, height, data: rgba, close() { this.data = null } }
}
