import test from 'node:test';
import assert from 'node:assert/strict';
import { createServer } from 'node:http';
import { PPE, PROD, guardIdentity, listPreviews, deletePreview, cleanup, reconcile, waitForManifest, webTreeSha, resolvePreviewUrl, reportPreviewEvent } from './cloudflare-deployments.mjs';

const sha = 'a'.repeat(40);
const preview = { id: 'preview-1', name: 'feature/a', slug: 'server-owned-slug', created_on: new Date(Date.now() - 60 * 60 * 1000).toISOString(), urls: ['https://server-owned-slug-ppe-harmonic-analyzer-com.ppe-harmonic-analyzer-com.workers.dev'] };
function envelope(rows, page = 1, perPage = 100, total = rows.length) {
  return { success: true, result: rows, result_info: { page, per_page: perPage, count: rows.length, total_count: total } };
}
function deploymentConnection(nodes, hasNextPage = false, endCursor = null) {
  return { data: { repository: { deployments: { nodes, pageInfo: { hasNextPage, endCursor } } } } };
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
    if (url === 'https://api.github.com/graphql') return json(deploymentConnection([{ databaseId: 7, commitOid: 'b'.repeat(40), ref: { name: 'old' }, payload: JSON.stringify({ manager: 'cloudflare-native', branch: preview.name }), latestStatus: { state: 'INACTIVE' } }, { databaseId: 8, commitOid: sha, ref: { name: 'live' }, payload: JSON.stringify({ manager: 'cloudflare-native', branch: 'live' }), latestStatus: { state: 'SUCCESS' } }]));
    if (options.method !== 'GET') {
      writes.push([url, options.method, options.body && JSON.parse(options.body)]);
      return json({ success: true, result: null });
    }
    if (url.includes('/pulls?')) return json([{ head: { ref: 'live', sha } }]);
    if (url.includes('/previews?')) return json(envelope([preview, { ...preview, id: 'live-preview', name: 'live' }, { ...preview, id: 'reserved', name: 'main' }]));
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
    if (url === 'https://api.github.com/graphql') return json(deploymentConnection([{ databaseId: 7, commitOid: sha, ref: null, payload: JSON.stringify({ manager: 'cloudflare-native', branch: preview.name }), latestStatus: { state: 'SUCCESS' } }]));
    if (options.method !== 'GET') {
      writes.push([url, options.method, options.body && JSON.parse(options.body)]);
      return json({ success: true, result: null });
    }
    if (url.includes('/pulls?')) return json([]);
    if (url.includes('/previews?')) return json(envelope([preview]));
    throw new Error(`Unexpected API request ${url}`);
  }, async () => {
    await cleanup(preview.name);
    assert.equal(writes[0][1], 'DELETE');
    assert.equal(writes[1][2].state, 'inactive');
    assert.equal(writes[1][2].auto_inactive, false);
  });
});

test('cleanup paginates bulk latestStatus and does not abandon older active deployments', async () => {
  const writes = [];
  const cursors = [];
  await withAPI(async (url, options) => {
    if (url === 'https://api.github.com/graphql') {
      const body = JSON.parse(options.body);
      cursors.push(body.variables.after);
      assert.match(body.query, /latestStatus\{state\}/);
      return json(body.variables.after === null
        ? deploymentConnection([{ databaseId: 1, commitOid: sha, ref: null, payload: JSON.stringify({ manager: 'cloudflare-native', branch: preview.name }), latestStatus: { state: 'INACTIVE' } }], true, 'older-page')
        : deploymentConnection([{ databaseId: 2, commitOid: sha, ref: null, payload: JSON.stringify({ manager: 'cloudflare-native', branch: preview.name }), latestStatus: { state: 'SUCCESS' } }]));
    }
    if (options.method !== 'GET') {
      writes.push([url, JSON.parse(options.body)]);
      return json({ success: true });
    }
    if (url.includes('/pulls?')) return json([]);
    if (url.includes('/previews?')) return json(envelope([]));
    throw new Error(`Unexpected per-deployment/status request ${url}`);
  }, async () => {
    await cleanup(preview.name);
    assert.deepEqual(cursors, [null, 'older-page']);
    assert.equal(writes.length, 1);
    assert.match(writes[0][0], /\/deployments\/2\/statuses$/);
    assert.equal(writes[0][1].state, 'inactive');
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

test('reopened missing Preview fails immediately with a required new web push instruction', async () => {
  let requests = 0;
  await withAPI(async () => { requests++; return json(envelope([])); }, async () => {
    await assert.rejects(resolvePreviewUrl(preview.name, 'reopened'), /Push a commit touching web\/.*reopening alone does not build/);
    assert.equal(requests, 1);
  });
});

test('reopened existing Preview is returned without asking for a new push', async () => {
  await withAPI(async () => json(envelope([preview])), async () => assert.equal(await resolvePreviewUrl(preview.name, 'reopened'), preview.urls[0]));
});

test('opened missing Preview keeps bounded startup wait and actionable native-build diagnostics', async () => {
  await withAPI(async () => json(envelope([])), async () => assert.rejects(resolvePreviewUrl(preview.name, 'opened', 1), /Check native build logs.*pre-PR orphan cleanup.*push a commit touching web\//));
});

test('hourly reconciliation grants fresh orphan Previews a 30-minute PR-opening window', async () => {
  let deletions = 0;
  await withAPI(async (url, options) => {
    if (url === 'https://api.github.com/graphql') return json(deploymentConnection([]));
    if (url.includes('/pulls?')) return json([]);
    if (url.includes('/previews?')) return json(envelope([{ ...preview, created_on: new Date(Date.now() - 10 * 60 * 1000).toISOString() }]));
    if (options.method === 'DELETE') { deletions++; return json({ success: true }); }
    throw new Error(`Unexpected request ${url}`);
  }, async () => {
    await reconcile();
    assert.equal(deletions, 0);
  });
});

test('explicit closed-PR cleanup deletes even a newly created Preview immediately', async () => {
  let deletions = 0;
  await withAPI(async (url, options) => {
    if (url === 'https://api.github.com/graphql') return json(deploymentConnection([]));
    if (url.includes('/pulls?')) return json([]);
    if (url.includes('/previews?')) return json(envelope([{ ...preview, created_on: new Date().toISOString() }]));
    if (options.method === 'DELETE') { deletions++; return json({ success: true }); }
    throw new Error(`Unexpected request ${url}`);
  }, async () => {
    await cleanup(preview.name);
    assert.equal(deletions, 1);
  });
});

test('scheduled deletion fails closed when an orphan creation timestamp is missing or malformed', async () => {
  for (const created_on of [undefined, 'invalid-date']) {
    let deletions = 0;
    await withAPI(async (url, options) => {
      if (url.includes('/pulls?')) return json([]);
      if (url.includes('/previews?')) return json(envelope([{ ...preview, created_on }]));
      if (options.method === 'DELETE') deletions++;
      throw new Error(`Unexpected request ${url}`);
    }, async () => {
      await assert.rejects(reconcile(), /invalid created_on/);
      assert.equal(deletions, 0);
    });
  }
});

test('consumer skips valid fork event before any API, credential check, or GitHub deployment', async () => {
  let requests = 0;
  await withAPI(async () => { requests++; throw new Error('Unsupported fork must not call an API'); }, async () => {
    delete process.env.GITHUB_OUTPUT;
    delete process.env.GH_TOKEN;
    delete process.env.CLOUDFLARE_CLEANUP_API_TOKEN;
    process.env.CLOUDFLARE_ACCOUNT_ID = PROD.account;
    const event = { action: 'opened', pull_request: { number: 13, head: { ref: 'feature/fork', sha, repo: { full_name: 'fork/repo' } } } };
    assert.deepEqual(await reportPreviewEvent(event), { outcome: 'skipped' });
    assert.equal(requests, 0);
  });
});

test('consumer does not turn malformed payloads into successful fork skips', async () => {
  let requests = 0;
  const valid = { number: 13, head: { ref: 'feature/a', sha, repo: { full_name: 'fork/repo' } } };
  await withAPI(async () => { requests++; throw new Error('Malformed event must not call an API'); }, async () => {
    for (const event of [null, {}, { pull_request: { ...valid, number: '13' } }, { pull_request: { ...valid, head: { ...valid.head, sha: 'bad-sha' } } }, { pull_request: { ...valid, head: { ...valid.head, ref: '' } } }, { pull_request: { ...valid, head: { ...valid.head, repo: null } } }]) await assert.rejects(reportPreviewEvent(event), /Malformed pull_request payload/);
    assert.equal(requests, 0);
  });
});

test('same-repository main is rejected before Preview API or deployment writes', async () => {
  let requests = 0;
  await withAPI(async () => { requests++; throw new Error('main must not call Preview API'); }, async () => {
    await assert.rejects(reportPreviewEvent({ pull_request: { number: 13, head: { ref: 'main', sha, repo: { full_name: 'owner/repo' } } } }), /reserved for production/);
    assert.equal(requests, 0);
  });
});

test('standalone manifest wait joins real HTTP base URLs with and without trailing slashes', async t => {
  const server = createServer((request, response) => {
    const pathname = new URL(request.url, 'http://localhost').pathname;
    if (pathname !== '/deployment.json' && pathname !== '/application/deployment.json') {
      response.writeHead(404, { 'Content-Type': 'text/plain' });
      response.end('Only canonical manifest paths are served');
      return;
    }
    response.writeHead(200, { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' });
    response.end(JSON.stringify({ commitSha: sha, branch: 'feature/a' }));
  });
  t.after(async () => {
    server.closeAllConnections();
    await new Promise((resolve, reject) => server.close(error => error ? reject(error) : resolve()));
  });
  await new Promise((resolve, reject) => {
    server.once('error', reject);
    server.listen(0, '127.0.0.1', resolve);
  });
  const origin = `http://127.0.0.1:${server.address().port}`;
  for (const base of [origin, `${origin}/`, `${origin}/application`, `${origin}/application/`]) {
    assert.equal(await waitForManifest(base, sha, 'feature/a', 1), base);
  }
  // These are real 200 JSON responses, not echo/mocked fetch assertions: the
  // oracle still rejects content from the wrong deployed commit or branch.
  await assert.rejects(waitForManifest(`${origin}/`, 'b'.repeat(40), 'feature/a', 1), /Timed out/);
  await assert.rejects(waitForManifest(`${origin}/`, sha, 'wrong-branch', 1), /Timed out/);
});
