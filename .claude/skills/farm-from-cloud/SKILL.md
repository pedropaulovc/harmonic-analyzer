---
name: farm-from-cloud
description: Connect a Linux Claude Code cloud session (claude.ai/code container) to the SolidWorks build farm. Installs az + pwsh, logs in to Azure, issues submitter credentials through the Key Vault firewall without touching existing ones, then probes the Temporal frontend. Use when asked to "connect to the build farm", "provision farm creds" or "submit a farm build" from a cloud session rather than the Windows dev box.
---

# Build farm from a cloud session

The supported way for an agent to run a farm build is still
`scripts/farm-run.ps1` under `hub` on the Windows box (see AGENTS.md and
DEVELOPING.md "Supervised farm launches"). This skill covers the cloud-session
path. Steps 1-4 are proven; step 5 depends on the session's network policy.

## Known values (rg-solidworks-build-wu, tenant vezza.com.br)

| what | value |
|---|---|
| Temporal frontend (mTLS + JWT) | `farm-solidworks-07aba226.westus.cloudapp.azure.com:7233` |
| Key Vault | `kvsw5qnlwu2vtr6gs` (`https://kvsw5qnlwu2vtr6gs.vault.azure.net/`) |
| results / screens storage | `stswboot5qnlwu2vtr6gs` / `stswscreens5qnlwu2vtr6gs` |
| Log Analytics customer id | `58e8feaa-03c0-479c-afe9-5544b60b387d` (`log-solidworks-wu`) |
| tenant | `6f10d2eb-7cce-444c-bf11-d6fe61d7b8f8` |

Re-derive them if a deploy moved anything:
`az resource list -g rg-solidworks-build-wu -o table`,
`az network public-ip show -g rg-solidworks-build-wu -n pip-farm-control-wu --query dnsSettings.fqdn`.

## 1. Tools

```bash
uv tool install azure-cli                     # -> ~/.local/bin/az
curl -sSL -o /tmp/pwsh.tgz https://github.com/PowerShell/PowerShell/releases/download/v7.5.4/powershell-7.5.4-linux-x64.tar.gz
mkdir -p /opt/pwsh && tar xzf /tmp/pwsh.tgz -C /opt/pwsh && ln -sf /opt/pwsh/pwsh /usr/local/bin/pwsh
(cd ../solidworks-pool && uv sync --frozen)
```

`farm-run.ps1` runs under pwsh on Linux. Its run job there is the
`HARMONIC_FARM_RUN` environment marker in `/proc/<pid>/environ`, not a Windows
job object (DEVELOPING.md, `-Cancel`).

## 2. Azure login (device code, MFA tenant)

A plain `az login --use-device-code` signs in but returns "No subscriptions":
the vezza.com.br tenant requires MFA for ARM. Scope the login to the tenant so
the device flow asks for MFA:

```bash
az login --use-device-code --tenant 6f10d2eb-7cce-444c-bf11-d6fe61d7b8f8
```

Run it in the background, read the code from its output, and give the user the
URL and code. Expect subscription `Pay-As-You-Go Dev/Test`.

## 3. Never override existing credentials

`farm.py credentials issue` overwrites `~/.solidworks-pool/*` (or
`$SOLIDWORKS_POOL_CONFIG`'s directory) unconditionally. Abort if it exists. Use
a new submitter name per session (`ccr-<user>-<yyyymmdd>`, `<user>` from the
signed-in Azure account). Issuing signs a new
cert and token; it revokes nothing.

## 4. Issue credentials through the Key Vault firewall

The vault's firewall is `defaultAction: Deny` with only the user's home IP
allowed. Cloud egress rotates across `160.79.106.0/24` (the vault saw .21 while
ipify reported .16/.134/.135/.142), so a single /32 does not work. With the
user's explicit OK for this session, add the /24 temporarily and remove it on
exit, even on failure. Firewall changes take ~20-40 s to apply.

```bash
set -u; V=kvsw5qnlwu2vtr6gs; R=160.79.106.0/24
# farm.py writes beside $SOLIDWORKS_POOL_CONFIG, else into ~/.solidworks-pool.
D=$(dirname "${SOLIDWORKS_POOL_CONFIG:-$HOME/.solidworks-pool/config.json}")
for f in config.json ca.pem client.pem client-key.pem token.jwt; do
  test ! -e "$D/$f" || { echo "credentials exist: $D/$f - abort"; exit 1; }
done
U=$(az ad signed-in-user show --query userPrincipalName -o tsv | cut -d@ -f1 | cut -d'#' -f1 | tr -c 'A-Za-z0-9._\n-' '-')
trap 'az keyvault network-rule remove -n $V --ip-address $R -o none;
      az keyvault show -n $V --query properties.networkAcls.ipRules[].value -o tsv' EXIT
az keyvault network-rule add -n $V --ip-address $R -o none
cd ../solidworks-pool
for i in 1 2 3 4 5 6; do sleep 20
  uv run --frozen python farm.py credentials issue --name "ccr-$U-$(date +%Y%m%d)" \
    --server farm-solidworks-07aba226.westus.cloudapp.azure.com:7233 \
    --results-account stswboot5qnlwu2vtr6gs --screens-account stswscreens5qnlwu2vtr6gs \
    --logs-workspace 58e8feaa-03c0-479c-afe9-5544b60b387d \
    --vault-uri https://kvsw5qnlwu2vtr6gs.vault.azure.net/ && break
done
```

Confirm the trap's output shows only the original rule. The container is
ephemeral, so the credentials die with it and the next session repeats this step.

## 5. Reach the Temporal frontend

```bash
(cd ../solidworks-pool && timeout 60 uv run --frozen python farm.py workers)
```

This does not work from an Anthropic-hosted cloud session, whatever the
network access level. All egress goes through the agent proxy, and
`/root/.ccr/README.md` lists "gRPC / HTTP/2-only APIs, ... client-mTLS, ...
non-443 HTTPS ports" as not supported through it. The farm frontend is all
three: Temporal gRPC with a client certificate on 7233. The access level
(Trusted, Custom, Full) only chooses which hosts the proxy lets through. The
host is already allowed: the proxy opens the tunnel, then resets it right after
the ClientHello (`ws_closed_mid_exchange` in
`curl -sS "$HTTPS_PROXY/__agentproxy/status"`, seen 2026-10-07 under two proxy
instances, with and without the client cert), and `farm.py workers` hangs.

What would work, none of it tried:
- a self-hosted environment, whose egress leaves through your own network
  (https://code.claude.com/docs/en/self-hosted-environments)
- an HTTPS (443, no client cert) relay in front of the farm, which is a farm
  architecture change

Until then, submit from the Windows box. Steps 1-4 still give a cloud session
farm credentials and Azure access (Key Vault, storage, Log Analytics over
HTTPS) for read-only diagnostics.

## 6. Submit a test leaf (only where step 5 lists workers)

Use the supervised launcher with POSIX paths. `-LogDirectory` must sit outside
every Git worktree, and HEAD must be pushed:

```bash
pwsh -NoProfile -NonInteractive -File scripts/farm-run.ps1 \
  -Worktree "$PWD" -PoolHome /home/user/solidworks-pool \
  -LogDirectory /home/user/farm-runs -Targets part:pn_pen_rod -LeafTimeout 90 -Tag smoke
pwsh -NoProfile -File scripts/farm-run.ps1 -Watch -LogDirectory /home/user/farm-runs -Tag smoke
```

Cloud sessions have no `hub`, which AGENTS.md requires for agent launches
(no finite local timer). Ask the user how to supervise before launching. Bash
background jobs are capped at 2 h, so they only suit a single leaf.

A cache hit dispatches nothing and proves nothing. Check `-Status` for
`counts.requested` > 0 and follow the leaf with `farm.py watch <workflow-id>`.
