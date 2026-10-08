import test from 'node:test';
import assert from 'node:assert/strict';
import { PPE, PROD, guardIdentity, listPreviews, deletePreview, cleanup, reconcile, waitForManifest, webTreeSha } from './cloudflare-deployments.mjs';

const sha = 'a'.repeat(40);
const preview = { id: 'preview-1', name: 'feature/a', slug: 'server-owned-slug', urls: ['https://server-owned-slug-ppe-harmonic-analyzer-com.ppe-harmonic-analyzer-com.workers.dev'] };
function envelope(rows, page = 1, perPage = 100, total = rows.length) {
  return { success: true, result: rows, result_info: { page, per_page: perPage, count: rows.length, total_count: total } };
}
function json(data, status = 200) { return new Response(JSON.stringify(data), { status }); }
async function withAPI(fn, body) {
  const originalFetch = globalThis.fetch;
  const originalEnv = { ...process.env };
  Object.assign(process.env, { CLOUDFLARE_ACCOUNT_ID: PPE.account, CLOUDFLARE_WORKER_NAME: PPE.worker, CLOUDFLARE_WORKERS_SUBDOMAIN: PPE.subdomain, CLOUDFLARE_CLEANUP_API_TOKEN: 'test-cf', GH_TOKEN: 'test-gh', GITHUB_REPOSITORY: 'owner/repo' });
  globalThis.fetch = fn;
  try { await body(); } finally {
    globalThis.fetch = originalFetch;
    for (const key of Object.keys(process.env)) if (!(key in originalEnv)) delete process.env[key];
    Object.assign(process.env, originalEnv);
  }
}

test('fixed identity refuses production worker, account, and subdomain misuse', () => {
  const env = { CLOUDFLARE_ACCOUNT_ID: PPE.account, CLOUDFLARE_WORKER_NAME: PPE.worker, CLOUDFLARE_WORKERS_SUBDOMAIN: PPE.subdomain };
  guardIdentity(PPE, env);
  for (const [key, value] of [['CLOUDFLARE_ACCOUNT_ID', PROD.account], ['CLOUDFLARE_WORKER_NAME', PROD.worker], ['CLOUDFLARE_WORKERS_SUBDOMAIN', PROD.subdomain]]) assert.throws(() => guardIdentity(PPE, { ...env, [key]: value }), /must equal/);
});

test('Preview enumeration follows actual page/per_page/total_count envelope', async () => {
  const pages = [];
  await withAPI(async url => {
    const page = Number(new URL(url).searchParams.get('page'));
    pages.push(page);
    return json(envelope([{ ...preview, id: String(page), name: `branch-${page}` }], page, 1, 2));
  }, async () => {
    assert.equal((await listPreviews()).length, 2);
    assert.deepEqual(pages, [1, 2]);
  });
});

test('delete targets one exact Preview ID, never a Worker or branch-normalized collision', async () => {
  const requests = [];
  await withAPI(async (url, options) => {
    requests.push([url, options.method]);
    return json(options.method === 'DELETE' ? { success: true, result: null } : envelope([preview, { ...preview, id: 'other', name: 'feature-a' }]));
  }, async () => {
    assert.equal(await deletePreview('feature/a'), true);
    assert.equal(requests.length, 2);
    assert.match(requests[1][0], /\/workers\/workers\/ppe-harmonic-analyzer-com\/previews\/preview-1$/);
    assert.equal(requests[1][1], 'DELETE');
    await assert.rejects(deletePreview('main'), /Refusing/);
  });
});

test('verified absence is idempotent but authentication errors are not', async () => {
  await withAPI(async () => json(envelope([])), async () => assert.equal(await deletePreview('missing'), false));
  await withAPI(async () => json({ success: false, errors: [{ code: 10000, message: 'Authentication error' }] }, 403), async () => assert.rejects(deletePreview('missing'), /HTTP 403/));
});

test('DELETE 404 is idempotent only after a successful fresh list proves absence', async () => {
  let lists = 0;
  await withAPI(async (_url, options) => {
    if (options.method === 'DELETE') return json({ success: false, errors: [{ message: 'Not found' }] }, 404);
    return json(envelope(++lists === 1 ? [preview] : []));
  }, async () => assert.equal(await deletePreview(preview.name), true));
  await withAPI(async (_url, options) => options.method === 'DELETE' ? json({ success: false }, 404) : json(envelope([preview])), async () => assert.rejects(deletePreview(preview.name), /HTTP 404/));
});

test('closed PR cleanup preserves a branch shared by any open PR, including a fork', async () => {
  const requests = [];
  await withAPI(async url => {
    requests.push(url);
    return json([{ head: { ref: preview.name, sha, repo: { full_name: 'fork/repo' } } }]);
  }, async () => {
    await cleanup(preview.name);
    assert.equal(requests.length, 1);
    assert.match(requests[0], /pulls\?state=open/);
  });
});

test('reconciliation deletes late native-build orphans, preserving live and main Previews', async () => {
  const writes = [];
  await withAPI(async (url, options) => {
    if (options.method !== 'GET') {
      writes.push([url, options.method, options.body && JSON.parse(options.body)]);
      return json({ success: true, result: null });
    }
    if (url.includes('/pulls?')) return json([{ head: { ref: 'live', sha } }]);
    if (url.includes('/previews?')) return json(envelope([preview, { ...preview, id: 'live-preview', name: 'live' }, { ...preview, id: 'reserved', name: 'main' }]));
    if (url.includes('/deployments?')) return json([{ id: 7, sha: 'b'.repeat(40), ref: 'old', payload: { manager: 'cloudflare-native', branch: preview.name } }, { id: 8, sha, ref: 'live', payload: { manager: 'cloudflare-native', branch: 'live' } }]);
    if (url.includes('/deployments/7/statuses')) return json([{ state: 'inactive' }]);
    throw new Error(`Unexpected API request ${url}`);
  }, async () => {
    await reconcile();
    assert.equal(writes.filter(row => row[1] === 'DELETE').length, 1);
    assert.match(writes[0][0], /\/previews\/preview-1$/);
    // Previously inactive records stay inactive; live and main previews never deleted.
    assert.equal(writes.filter(row => row[1] === 'POST').length, 0);
  });
});

test('cleanup writes inactive status after deleting the closed branch Preview', async () => {
  const writes = [];
  await withAPI(async (url, options) => {
    if (options.method !== 'GET') {
      writes.push([url, options.method, options.body && JSON.parse(options.body)]);
      return json({ success: true, result: null });
    }
    if (url.includes('/pulls?')) return json([]);
    if (url.includes('/previews?')) return json(envelope([preview]));
    if (url.includes('/deployments?')) return json([{ id: 7, sha, ref: sha, payload: { manager: 'cloudflare-native', branch: preview.name } }]);
    if (url.includes('/statuses')) return json([{ state: 'success' }]);
    throw new Error(`Unexpected API request ${url}`);
  }, async () => {
    await cleanup(preview.name);
    assert.equal(writes[0][1], 'DELETE');
    assert.equal(writes[1][2].state, 'inactive');
    assert.equal(writes[1][2].auto_inactive, false);
  });
});

test('manifest verifies exact SHA AND branch, never generic HTTP 200', async () => {
  const url = 'https://example.workers.dev';
  await withAPI(async () => json({ commitSha: sha, branch: 'feature/a' }), async () => assert.equal(await waitForManifest(url, sha, 'feature/a', 1), url));
  await withAPI(async () => json({ commitSha: sha, branch: 'other' }), async () => assert.rejects(waitForManifest(url, sha, 'feature/a', 1), /Timed out/));
  await withAPI(async () => json({ commitSha: 'b'.repeat(40), branch: 'feature/a' }), async () => assert.rejects(waitForManifest(url, sha, 'feature/a', 1), /Timed out/));
});

test('non-web synchronize accepts only identical Git web subtree and returns actual native SHA', async () => {
  const nativeSha = 'b'.repeat(40);
  const requestedRoot = 'c'.repeat(40);
  const nativeRoot = 'd'.repeat(40);
  const web = 'e'.repeat(40);
  const url = 'https://example.workers.dev';
  await withAPI(async requestUrl => {
    if (requestUrl.includes('/deployment.json')) return json({ commitSha: nativeSha, branch: 'feature/a' });
    if (requestUrl.endsWith(`/git/commits/${sha}`)) return json({ tree: { sha: requestedRoot } });
    if (requestUrl.endsWith(`/git/commits/${nativeSha}`)) return json({ tree: { sha: nativeRoot } });
    if (requestUrl.includes('/git/trees/')) return json({ truncated: false, tree: [{ path: 'web', type: 'tree', sha: web }] });
    throw new Error(`Unexpected request ${requestUrl}`);
  }, async () => {
    const verified = await waitForManifest(url, sha, 'feature/a', 1, async actual => (await webTreeSha(actual)) === (await webTreeSha(sha)));
    assert.deepEqual(verified, { url, commitSha: nativeSha });
    assert.notEqual(verified.commitSha, sha);
  });
});

test('changed web tree, wrong branch, and invalid native SHA cannot use equivalence fallback', async () => {
  const nativeSha = 'b'.repeat(40);
  const url = 'https://example.workers.dev';
  let comparisons = 0;
  const unequal = async () => { comparisons++; return false; };
  await withAPI(async () => json({ commitSha: nativeSha, branch: 'feature/a' }), async () => assert.rejects(waitForManifest(url, sha, 'feature/a', 1, unequal), /Timed out/));
  assert.ok(comparisons > 0);
  comparisons = 0;
  await withAPI(async () => json({ commitSha: nativeSha, branch: 'other' }), async () => assert.rejects(waitForManifest(url, sha, 'feature/a', 1, unequal), /Timed out/));
  await withAPI(async () => json({ commitSha: 'not-a-sha', branch: 'feature/a' }), async () => assert.rejects(waitForManifest(url, sha, 'feature/a', 1, unequal), /Timed out/));
  assert.equal(comparisons, 0);
});

test('GitHub web tree proof fails closed on incomplete trees and API failures', async () => {
  await withAPI(async requestUrl => requestUrl.includes('/git/commits/') ? json({ tree: { sha } }) : json({ truncated: true, tree: [{ path: 'web', type: 'tree', sha }] }), async () => assert.rejects(webTreeSha(sha), /incomplete root tree/));
  await withAPI(async () => json({ message: 'Forbidden' }, 403), async () => assert.rejects(webTreeSha(sha), /HTTP 403/));
  await withAPI(async () => json({ commitSha: 'b'.repeat(40), branch: 'feature/a' }), async () => assert.rejects(waitForManifest('https://example.workers.dev', sha, 'feature/a', 1, async () => { throw new Error('GitHub proof unavailable'); }), /GitHub proof unavailable/));
});

test('exact SHA remains primary without GitHub web tree API calls', async () => {
  let called = false;
  await withAPI(async () => json({ commitSha: sha, branch: 'feature/a' }), async () => {
    assert.deepEqual(await waitForManifest('https://example.workers.dev', sha, 'feature/a', 1, async () => { called = true; throw new Error('Should not compare exact SHA'); }), { url: 'https://example.workers.dev', commitSha: sha });
    assert.equal(called, false);
  });
});
