#!/usr/bin/env node
// Worker Preview API contract: workers-sdk packages/deploy-helpers/src/preview/api.ts.
// Accepted cleanup scope: retire the Preview resource and its branch alias only.
// Immutable deployment URLs are retained; Preview DELETE does not revoke them.
import { readFile, appendFile } from 'node:fs/promises';
import { pathToFileURL } from 'node:url';

export const PPE = Object.freeze({ account: 'c8769c20b85cd2857afe22ef2f9a0a21', worker: 'harmonicanalyzer-com-ppe', subdomain: 'harmonicanalyzer-com-ppe' });
export const PROD = Object.freeze({ account: '6b2522c874d4613dc2bf47bd2ce521a2', worker: 'harmonicanalyzer-com-prod', subdomain: 'harmonicanalyzer-com-prod' });
const sleep = ms => new Promise(resolve => setTimeout(resolve, ms));
export function guardIdentity(identity, env = process.env) {
  for (const [key, expected] of [['CLOUDFLARE_ACCOUNT_ID', identity.account], ['CLOUDFLARE_WORKER_NAME', identity.worker], ['CLOUDFLARE_WORKERS_SUBDOMAIN', identity.subdomain]]) {
    if (env[key] !== expected) throw new Error(`${key} must equal the fixed ${expected}`);
  }
}
function required(name) {
  const value = process.env[name];
  if (!value) throw new Error(`Missing ${name}`);
  return value;
}
async function request(url, token, method = 'GET', body) {
  const response = await fetch(url, { method, signal: AbortSignal.timeout(30000), headers: { Authorization: `Bearer ${token}`, Accept: 'application/json', 'Content-Type': 'application/json', 'X-GitHub-Api-Version': '2022-11-28' }, ...(body === undefined ? {} : { body: JSON.stringify(body) }) });
  const text = await response.text();
  let data;
  try { data = text ? JSON.parse(text) : null; } catch { throw new Error(`${method} ${url}: invalid JSON (HTTP ${response.status})`); }
  if (!response.ok || data?.success === false) {
    const error = new Error(`${method} ${url}: HTTP ${response.status}: ${JSON.stringify(data)}`);
    error.status = response.status;
    error.data = data;
    throw error;
  }
  return data;
}
function repository() {
  const repo = required('GITHUB_REPOSITORY');
  if (!/^[\w.-]+\/[\w.-]+$/.test(repo)) throw new Error('Invalid GITHUB_REPOSITORY');
  return repo;
}
function gh(path, method, body) {
  return request(`https://api.github.com/repos/${repository()}${path}`, required('GH_TOKEN'), method, body);
}
async function ghList(path) {
  const result = [];
  for (let page = 1; ; page++) {
    const rows = await gh(`${path}${path.includes('?') ? '&' : '?'}per_page=100&page=${page}`);
    if (!Array.isArray(rows)) throw new Error(`Unexpected GitHub list schema: ${path}`);
    result.push(...rows);
    if (rows.length < 100) return result;
  }
}
async function* previewDeployments() {
  const [owner, name] = repository().split('/');
  let after = null;
  do {
    // Verified by GitHub schema introspection: Deployment.latestStatus, payload,
    // databaseId, commitOid, ref{name}; Repository.deployments supports environments.
    const result = await request('https://api.github.com/graphql', required('GH_TOKEN'), 'POST', {
      query: 'query PreviewDeployments($owner:String!,$name:String!,$after:String){repository(owner:$owner,name:$name){deployments(first:100,after:$after,environments:[\"web-preview\"]){nodes{databaseId commitOid payload ref{name} latestStatus{state}} pageInfo{hasNextPage endCursor}}}}',
      variables: { owner, name, after },
    });
    if (result.errors?.length) throw new Error(`GitHub deployment query failed: ${JSON.stringify(result.errors)}`);
    const connection = result.data?.repository?.deployments;
    if (!Array.isArray(connection?.nodes) || typeof connection.pageInfo?.hasNextPage !== 'boolean') throw new Error('Invalid GitHub deployment connection');
    for (const node of connection.nodes) {
      if (!node || !Number.isInteger(node.databaseId)) throw new Error('Invalid GitHub deployment database ID');
      yield node;
    }
    if (!connection.pageInfo.hasNextPage) return;
    const next = connection.pageInfo.endCursor;
    if (typeof next !== 'string' || !next || next === after) throw new Error('Invalid GitHub deployment pagination cursor');
    after = next;
  } while (true);
}
const previewPath = `/accounts/${PPE.account}/workers/workers/${PPE.worker}/previews`;
async function cf(path, method) {
  guardIdentity(PPE);
  return request(`https://api.cloudflare.com/client/v4${path}`, required('CLOUDFLARE_CLEANUP_API_TOKEN'), method);
}
export async function listPreviews() {
  const previews = [];
  for (let page = 1; ; page++) {
    const envelope = await cf(`${previewPath}?per_page=100&page=${page}`);
    if (!Array.isArray(envelope.result)) throw new Error('Unexpected Cloudflare Preview enumeration schema');
    for (const row of envelope.result) {
      if (typeof row.id !== 'string' || typeof row.name !== 'string' || typeof row.slug !== 'string') throw new Error('Invalid Cloudflare Preview resource');
    }
    previews.push(...envelope.result);
    const info = envelope.result_info;
    // Live Preview API returns page/per_page/count/total_count, not cursor pages.
    if (!Number.isInteger(info?.page) || !Number.isInteger(info?.per_page) || info.per_page < 1 || !Number.isInteger(info?.total_count) || info.total_count < 0 || info.page !== page) throw new Error('Invalid Preview pagination');
    if (info.page * info.per_page >= info.total_count) return previews;
  }
}
export async function deletePreview(name) {
  if (!name || name === 'main') throw new Error('Refusing empty/main Preview deletion');
  // Enumerate first: absence is verified by a successful list, never by swallowing
  // arbitrary 404s (which can also mean the parent Worker/account is wrong).
  const preview = (await listPreviews()).find(row => row.name === name);
  if (!preview) return false;
  try {
    await cf(`${previewPath}/${encodeURIComponent(preview.id)}`, 'DELETE');
  } catch (error) {
    if (error.status !== 404 || (await listPreviews()).some(row => row.id === preview.id)) throw error;
  }
  console.log(`Deleted Preview resource ${JSON.stringify(name)} (branch-only cleanup; immutable deployment URLs are retained)`);
  return true;
}
function previewUrl(preview) {
  const urls = preview.urls ?? [];
  for (const value of urls) {
    const url = new URL(value.startsWith('https://') ? value : `https://${value}`);
    if (url.protocol === 'https:' && url.hostname.endsWith(`-${PPE.worker}.${PPE.subdomain}.workers.dev`) && !url.username && !url.password) return url.origin;
  }
  throw new Error(`Preview ${preview.name} has no PPE workers.dev URL`);
}
export async function resolvePreviewUrl(branch, action, timeoutSeconds = 1200) {
  if (!Number.isFinite(timeoutSeconds) || timeoutSeconds < 1 || timeoutSeconds > 1200) throw new Error('Preview startup timeout must be 1..1200 seconds');
  const deadline = Date.now() + timeoutSeconds * 1000;
  do {
    const preview = (await listPreviews()).find(row => row.name === branch);
    if (preview) return previewUrl(preview);
    if (action === 'reopened') throw new Error('Reopened PR has no Preview after cleanup. Push a commit touching web/ to trigger native Cloudflare Builds; reopening alone does not build.');
    if (Date.now() < deadline) await sleep(Math.min(10000, deadline - Date.now()));
  } while (Date.now() < deadline);
  throw new Error('Native Cloudflare build did not create a Preview. Check native build logs. If pre-PR orphan cleanup removed it, push a commit touching web/; PR opening alone does not build.');
}
export async function waitForManifest(url, sha, branch, timeoutSeconds = 1200, equivalentCommit) {
  if (!/^[a-f0-9]{40}$/.test(sha)) throw new Error('Expected full commit SHA');
  if (!Number.isFinite(timeoutSeconds) || timeoutSeconds < 1 || timeoutSeconds > 1800) throw new Error('Timeout must be 1..1800 seconds');
  const manifestUrl = new URL(url);
  manifestUrl.pathname = `${manifestUrl.pathname.replace(/\/+$/, '')}/deployment.json`;
  manifestUrl.searchParams.set('commit', sha);
  const deadline = Date.now() + timeoutSeconds * 1000;
  let last = 'not available';
  do {
    let manifest;
    manifestUrl.searchParams.set('time', String(Date.now()));
    try {
      const response = await fetch(manifestUrl.href, { redirect: 'error', cache: 'no-store', signal: AbortSignal.timeout(Math.min(15000, Math.max(1, deadline - Date.now()))) });
      if (response.ok) {
        manifest = await response.json();
        if (manifest.commitSha === sha && (branch === undefined || manifest.branch === branch)) return equivalentCommit ? { url, commitSha: sha } : url;
        last = `manifest commit=${manifest.commitSha}, branch=${manifest.branch}`;
      } else last = `HTTP ${response.status}`;
    } catch (error) { last = error.message; }
    // Only the reporter enables this fallback. A generic standalone wait remains
    // exact-SHA-only. GitHub/API comparison failures must propagate, not be hidden
    // as a transient public-endpoint error.
    if (equivalentCommit && manifest?.branch === branch && /^[a-f0-9]{40}$/.test(manifest.commitSha) && await equivalentCommit(manifest.commitSha)) return { url, commitSha: manifest.commitSha };
    if (Date.now() < deadline) await sleep(Math.min(10000, deadline - Date.now()));
  } while (Date.now() < deadline);
  throw new Error(`Timed out waiting for ${sha} at ${url}: ${last}`);
}
export async function webTreeSha(commitSha) {
  if (!/^[a-f0-9]{40}$/.test(commitSha)) throw new Error('Expected full commit SHA for web tree comparison');
  const commit = await gh(`/git/commits/${commitSha}`);
  if (!/^[a-f0-9]{40}$/.test(commit.tree?.sha)) throw new Error('GitHub commit has no valid root tree');
  const root = await gh(`/git/trees/${commit.tree.sha}`);
  if (root.truncated || !Array.isArray(root.tree)) throw new Error('GitHub returned an incomplete root tree');
  const web = root.tree.find(entry => entry.path === 'web' && entry.type === 'tree');
  if (!/^[a-f0-9]{40}$/.test(web?.sha)) throw new Error('Commit has no valid web/ tree');
  return web.sha;
}
async function status(id, state, url, description) {
  await gh(`/deployments/${id}/statuses`, 'POST', { state, environment_url: url, description, auto_inactive: false });
}
async function publish(sha, branch, environment, resolveUrl, pr) {
  const deploymentBody = (ref, equivalentWebTree = false) => ({ ref, environment, auto_merge: false, required_contexts: [], transient_environment: environment === 'web-preview', production_environment: environment === 'web-production', payload: { manager: 'cloudflare-native', branch, ...(pr ? { pr } : {}), ...(equivalentWebTree ? { requestedSha: sha, identityProof: 'matching-web-tree' } : {}) } });
  let deployment = await gh('/deployments', 'POST', deploymentBody(sha));
  if (!deployment.id) throw new Error('GitHub did not create a deployment');
  await status(deployment.id, 'in_progress', undefined, 'Waiting for native Cloudflare build');
  try {
    const url = await resolveUrl();
    // Workers Builds evaluates its configured web/ watch paths against each push; a non-web-only PR
    // synchronize can legitimately retain an older native build. Object identity
    // of the entire web/ Git tree proves equivalence without executing PR code.
    const trees = new Map();
    const tree = commit => {
      if (!trees.has(commit)) trees.set(commit, webTreeSha(commit));
      return trees.get(commit);
    };
    const verified = await waitForManifest(url, sha, branch, 1200, async deployedSha => (await tree(deployedSha)) === (await tree(sha)));
    if (pr) {
      const current = await gh(`/pulls/${pr}`);
      if (current.state !== 'open' || current.head.sha !== sha) {
        await status(deployment.id, 'inactive', url, 'PR closed or superseded while native build ran');
        return;
      }
    }
    if (verified.commitSha !== sha) {
      await status(deployment.id, 'inactive', url, 'Head has identical web tree; recording actual deployed commit');
      deployment = await gh('/deployments', 'POST', deploymentBody(verified.commitSha, true));
      if (!deployment.id) throw new Error('GitHub did not create the actual-commit deployment');
    }
    await status(deployment.id, 'success', url, verified.commitSha === sha ? 'Exact native commit verified at /deployment.json' : 'Actual native commit verified; web tree matches requested head');
    console.log(url);
    if (process.env.GITHUB_OUTPUT) await appendFile(process.env.GITHUB_OUTPUT, `url=${url}\ncommit_sha=${verified.commitSha}\n`);
  } catch (error) {
    await status(deployment.id, 'failure', undefined, error.message.includes('Reopened PR has no Preview') ? 'Preview was cleaned up; push a commit touching web/ to trigger native Builds' : 'Native build unavailable or mismatched; check workflow error and native build logs');
    throw error;
  }
}
async function openPRs() {
  // Preserve any open PR sharing a name, including fork PRs conservatively.
  return ghList('/pulls?state=open');
}
async function deactivate(branches, open) {
  const liveBranches = new Set(open.map(pr => pr.head.ref));
  const liveSHAs = new Set(open.map(pr => pr.head.sha));
  let eligible = 0;
  let inactivated = 0;
  const unreadable = [];
  for await (const deployment of previewDeployments()) {
    let payload;
    try {
      const decodedPayload = typeof deployment.payload === 'string' ? JSON.parse(deployment.payload || '{}') : deployment.payload;
      // GraphQL's JSON scalar wraps the REST object payload in a JSON string.
      // Decode that string before matching its branch when the Git ref is gone.
      payload = typeof decodedPayload === 'string' ? JSON.parse(decodedPayload) : decodedPayload;
    } catch (error) {
      // An unreadable record does not establish ownership, even if its Git ref
      // matches. Preserve it but continue cleaning independently valid records.
      unreadable.push(new Error(`Deployment ${deployment.databaseId}: unreadable payload`, { cause: error }));
      continue;
    }
    const branch = payload?.manager === 'cloudflare-native' ? payload.branch : deployment.ref?.name;
    if (liveBranches.has(branch) || liveSHAs.has(deployment.commitOid)) continue;
    if (branches && !branches.has(branch)) continue;
    eligible++;
    if (deployment.latestStatus?.state !== 'INACTIVE') {
      await status(deployment.databaseId, 'inactive', undefined, 'Preview no longer belongs to an open PR');
      inactivated++;
    }
  }
  console.log(`GitHub web-preview cleanup: ${eligible} eligible deployment(s), ${inactivated} marked inactive`);
  if (unreadable.length) throw new AggregateError(unreadable, `Cleanup left unreadable deployments unchanged: ${unreadable.map(error => error.message).join('; ')}`);
}
export async function cleanup(branch) {
  guardIdentity(PPE);
  if (branch === 'main') {
    console.log('Preserving main: reserved for production');
    return;
  }
  const open = await openPRs();
  if (open.some(pr => pr.head.ref === branch)) {
    console.log(`Preserving ${JSON.stringify(branch)}: an open PR shares the branch`);
    return;
  }
  await deletePreview(branch);
  await deactivate(new Set([branch]), open);
}
export async function reconcile() {
  guardIdentity(PPE);
  const open = await openPRs();
  const live = new Set(open.map(pr => pr.head.ref));
  for (const preview of await listPreviews()) {
    if (preview.name === 'main' || live.has(preview.name)) continue;
    const created = typeof preview.created_on === 'string' && /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$/.test(preview.created_on) ? Date.parse(preview.created_on) : NaN;
    if (!Number.isFinite(created)) throw new Error(`Cannot safely reconcile Preview ${JSON.stringify(preview.name)}: invalid created_on`);
    // A branch push can finish before its PR opens. Give fresh orphan Previews a
    // 30-minute opening window; explicit closed-PR cleanup is still immediate.
    if (Date.now() - created < 30 * 60 * 1000) continue;
    // Re-read open PRs immediately before deletion: a reopened PR must survive.
    if ((await openPRs()).some(pr => pr.head.ref === preview.name)) continue;
    await deletePreview(preview.name);
  }
  // One paginated history scan for the entire scheduled reconciliation, not one
  // scan per orphan branch or one latest-status HTTP request per historical record.
  await deactivate(undefined, await openPRs());
}
export async function reportPreviewEvent(event) {
  const pr = event?.pull_request;
  if (!Number.isInteger(pr?.number) || pr.number < 1 || typeof pr.head?.ref !== 'string' || !pr.head.ref || !/^[a-f0-9]{40}$/.test(pr.head.sha) || typeof pr.head.repo?.full_name !== 'string' || !/^[\w.-]+\/[\w.-]+$/.test(pr.head.repo.full_name)) throw new Error('Malformed pull_request payload: expected PR number, branch, full SHA, and head repository');
  if (pr.head.repo.full_name !== repository()) {
    console.log('::notice::Skipping native Preview reporting: Cloudflare Git integration supports same-repository branches only; no fork deployment was created.');
    if (process.env.GITHUB_OUTPUT) await appendFile(process.env.GITHUB_OUTPUT, 'outcome=skipped\n');
    return { outcome: 'skipped' };
  }
  guardIdentity(PPE);
  if (pr.head.ref === 'main') throw new Error('main is reserved for production');
  await publish(pr.head.sha, pr.head.ref, 'web-preview', () => resolvePreviewUrl(pr.head.ref, event.action), pr.number);
  return { outcome: 'processed' };
}
async function main() {
  const [command, ...args] = process.argv.slice(2);
  if (command === 'list') console.log(JSON.stringify(await listPreviews(), null, 2));
  else if (command === 'delete' && args.length === 1) await deletePreview(args[0]);
  else if (command === 'cleanup' && args.length === 1) await cleanup(args[0]);
  else if (command === 'reconcile' && !args.length) await reconcile();
  else if (command === 'wait' && args.length >= 2 && args.length <= 4) console.log(await waitForManifest(args[0], args[1], args[2], args[3] === undefined ? 1200 : Number(args[3])));
  else if (command === 'preview' && !args.length) {
    const event = JSON.parse(await readFile(required('GITHUB_EVENT_PATH'), 'utf8'));
    await reportPreviewEvent(event);
  } else if (command === 'production' && !args.length) {
    guardIdentity(PROD);
    if (required('GITHUB_REF') !== 'refs/heads/main') throw new Error('Production reporting requires main');
    await publish(required('GITHUB_SHA'), 'main', 'web-production', async () => `https://${PROD.worker}.${PROD.subdomain}.workers.dev`);
  } else throw new Error('Usage: cloudflare-deployments.mjs preview|production|list|reconcile|delete BRANCH|cleanup BRANCH|wait URL SHA [BRANCH [TIMEOUT_SECONDS]]');
}
if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) main().catch(error => { console.error(error.message); process.exitCode = 1; });
