import { createWriteStream } from 'node:fs'
import { rename, rm } from 'node:fs/promises'
import { randomUUID } from 'node:crypto'
import { Readable } from 'node:stream'
import { pipeline } from 'node:stream/promises'
import { types } from 'node:util'

const CHUNK_CHARACTERS = 64 * 1024

// Match JSON.stringify without a replacer. Delegate scalar escaping/numbers and
// invalid BigInt refusal to the native serializer, but never stringify a report,
// sample, capture or array as one string. Repeated references are NOT deduplicated.
function jsonValue(value, key) {
  const type = typeof value
  if (value !== null && (type === 'object' || type === 'function' || type === 'bigint')) {
    const toJSON = value.toJSON
    if (typeof toJSON === 'function') value = toJSON.call(value, key)
  }
  if (types.isNumberObject(value)) return +value
  if (types.isStringObject(value)) return String(value)
  if (types.isBooleanObject(value)) return Boolean.prototype.valueOf.call(value)
  if (types.isBigIntObject(value)) return BigInt.prototype.valueOf.call(value)
  return value
}

const omitted = value => value === undefined || typeof value === 'function' || typeof value === 'symbol'

function* jsonParts(value, ancestors, depth = 0) {
  if (value === null || typeof value !== 'object') {
    yield JSON.stringify(value)
    return
  }
  if (JSON.isRawJSON?.(value)) {
    yield JSON.stringify(value)
    return
  }
  if (ancestors.has(value)) throw new TypeError('Converting circular structure to JSON')
  ancestors.add(value)
  try {
    const indent = '  '.repeat(depth), childIndent = `${indent}  `
    if (Array.isArray(value)) {
      const length = value.length
      yield '['
      for (let index = 0; index < length; index++) {
        yield `${index ? ',' : ''}\n${childIndent}`
        const child = jsonValue(value[index], String(index))
        yield* jsonParts(omitted(child) ? null : child, ancestors, depth + 1)
      }
      yield length ? `\n${indent}]` : ']'
    } else {
      yield '{'
      let count = 0
      for (const key of Object.keys(value)) {
        const child = jsonValue(value[key], key)
        if (omitted(child)) continue
        yield `${count++ ? ',' : ''}\n${childIndent}`
        yield JSON.stringify(key)
        yield ': '
        yield* jsonParts(child, ancestors, depth + 1)
      }
      yield count ? `\n${indent}}` : '}'
    }
  } finally {
    ancestors.delete(value)
  }
}

function* jsonChunks(report) {
  const value = jsonValue(report, '')
  if (omitted(value)) throw new TypeError('Report has no JSON representation')
  let parts = [], characters = 0
  for (const part of jsonParts(value, new Set())) {
    if (characters + part.length > CHUNK_CHARACTERS && parts.length) {
      yield parts.join('')
      parts = []; characters = 0
    }
    // Do not split escaped strings across UTF-16 surrogate pairs. A single
    // scalar is still subject to native JSON.stringify's string-size limit.
    if (part.length >= CHUNK_CHARACTERS) yield part
    else { parts.push(part); characters += part.length }
  }
  if (parts.length) yield parts.join('')
  yield '\n'
}

/**
 * Publish the complete existing pretty-JSON shape with stream backpressure.
 * Extra serialization memory is bounded by one scalar, one 64Ki-character
 * chunk, traversal depth/object keys and the stream buffers, not output size.
 * The measured report itself remains caller-owned and resident. Failed writes
 * leave any previous complete report intact, never a truncated final JSON.
 */
export async function writeJsonReport(path, report) {
  const temporary = `${path}.${randomUUID()}.tmp`
  let created = false
  try {
    const destination = createWriteStream(temporary, { flags: 'wx' })
    destination.once('open', () => { created = true })
    await pipeline(Readable.from(jsonChunks(report), { objectMode: false }), destination)
    await rename(temporary, path)
  } catch (error) {
    let cause = error, detail = error instanceof Error ? error.message : String(error)
    try { if (created) await rm(temporary, { force: true }) }
    catch (cleanupError) {
      detail += `; temporary-file cleanup failed: ${cleanupError instanceof Error ? cleanupError.message : String(cleanupError)}`
      cause = new AggregateError([error, cleanupError], `Report write and temporary-file cleanup failed: ${detail}`, { cause: error })
    }
    throw new Error(`Unable to write complete JSON report ${path}: ${detail}`, { cause })
  }
}
