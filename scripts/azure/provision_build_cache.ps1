<#
.SYNOPSIS
  Provision the Azure Blob container that backs the harmonic-analyzer build cache
  (the backend of cad/scripts/_artifact_cache.py). Idempotent -- safe to re-run;
  every `az ... create`/`update` no-ops or converges when re-applied.

.DESCRIPTION
  The cache speaks plain object storage over HTTPS (443), so -- unlike the old SMB
  share -- it works from anywhere, including networks that block port 445, with no
  VPN, private endpoint, or mounted drive. There is nothing to "mount": a builder
  or dev box just sets a few env vars (printed at the end) and authenticates with
  its own identity.

  In the SAME resource group / region as vm-solidworks this creates / converges:
    * a Standard_LRS StorageV2 account (cheap, locally-redundant -- a cache is
      disposable, so no geo-redundancy)
    * a blob container `buildcache`
    * account last-access-time tracking, ON  (so retention can be true LRU)
    * a lifecycle policy: delete entries not READ for $RetentionDays days. Because
      a cache restore is a blob read, an artefact in active use keeps itself alive
      -- no scheduled cleanup job, no client-side touch.
    * keyless RBAC: *Storage Blob Data Contributor* granted to the signed-in
      operator (so a dev box with `az login` can pull/push) and to vm-solidworks's
      system-assigned managed identity (so the builder pushes with no secrets).

  Run once by an operator with az logged in to the Dev/Test subscription.
#>
[CmdletBinding()]
param(
  [string]$ResourceGroup  = 'RG-SOLIDWORKS-DEV',
  [string]$Location       = 'eastus2',
  [string]$StorageAccount = 'stswbuildcache07aba2',
  [string]$Container      = 'buildcache',
  [int]   $RetentionDays  = 7,
  [string]$BuilderVM      = 'vm-solidworks',
  [switch]$SkipBuilderIdentity
)
$ErrorActionPreference = 'Stop'

Write-Host ">> storage account $StorageAccount ($ResourceGroup / $Location) ..."
az storage account create `
  --name $StorageAccount `
  --resource-group $ResourceGroup `
  --location $Location `
  --sku Standard_LRS `
  --kind StorageV2 `
  --min-tls-version TLS1_2 `
  --allow-blob-public-access false `
  --tags purpose=harmonic-analyzer-build-cache managed-by=_artifact_cache.py `
  --only-show-errors --output none

$accountId = az storage account show -n $StorageAccount -g $ResourceGroup --query id -o tsv

Write-Host ">> blob container $Container ..."
az storage container-rm create `
  --resource-group $ResourceGroup `
  --storage-account $StorageAccount `
  --name $Container `
  --only-show-errors --output none

Write-Host ">> enable last-access-time tracking (needed for LRU retention) ..."
az storage account blob-service-properties update `
  --resource-group $ResourceGroup `
  --account-name $StorageAccount `
  --enable-last-access-tracking true `
  --only-show-errors --output none

Write-Host ">> lifecycle policy: delete entries not read for $RetentionDays days ..."
$policy = @{
  rules = @(@{
    enabled    = $true
    name       = 'expire-stale-cache'
    type       = 'Lifecycle'
    definition = @{
      filters = @{ blobTypes = @('blockBlob'); prefixMatch = @("$Container/") }
      actions = @{ baseBlob = @{ delete = @{ daysAfterLastAccessTimeGreaterThan = $RetentionDays } } }
    }
  })
}
$policyFile = New-TemporaryFile
$policy | ConvertTo-Json -Depth 10 | Set-Content -Path $policyFile -Encoding utf8
try {
  az storage account management-policy create `
    --resource-group $ResourceGroup `
    --account-name $StorageAccount `
    --policy "@$policyFile" `
    --only-show-errors --output none
} finally {
  Remove-Item $policyFile -Force -ErrorAction SilentlyContinue
}

function Grant-BlobContributor([string]$PrincipalId, [string]$PrincipalType, [string]$Label) {
  if (-not $PrincipalId) { Write-Host "   (skip $Label -- no principal id)"; return }
  # Idempotent: `az role assignment create` returns RoleAssignmentExists (non-zero)
  # on a duplicate, which would abort the whole script under ErrorActionPreference
  # 'Stop' on a re-run -- so skip when the assignment already exists (codex review).
  $have = az role assignment list `
    --assignee $PrincipalId --role 'Storage Blob Data Contributor' --scope $accountId `
    --query "length(@)" -o tsv 2>$null
  if ($have -and [int]$have -gt 0) { Write-Host "   ($Label already granted)"; return }
  Write-Host ">> grant Storage Blob Data Contributor to $Label ..."
  az role assignment create `
    --assignee-object-id $PrincipalId `
    --assignee-principal-type $PrincipalType `
    --role 'Storage Blob Data Contributor' `
    --scope $accountId `
    --only-show-errors --output none
}

# Operator (dev box with `az login`) -- pull/push from this machine's identity.
$me = az ad signed-in-user show --query id -o tsv 2>$null
Grant-BlobContributor $me 'User' 'signed-in operator'

# Builder VM -- system-assigned managed identity, so it pushes with no secrets.
if (-not $SkipBuilderIdentity) {
  $mi = az vm identity assign -n $BuilderVM -g $ResourceGroup `
        --query systemAssignedIdentity -o tsv 2>$null
  if (-not $mi) { $mi = az vm show -n $BuilderVM -g $ResourceGroup `
        --query identity.principalId -o tsv 2>$null }
  Grant-BlobContributor $mi 'ServicePrincipal' "$BuilderVM managed identity"
}

Write-Host ""
Write-Host "Done. Cache backend ready: $StorageAccount / container '$Container'."
Write-Host ""
Write-Host "Account / container / salt are committed defaults in _artifact_cache.py, and the"
Write-Host "default role is 'rw' -- every authorised seat pulls + publishes with NO setup."
Write-Host "Downgrade a seat only if you want to (gitignored file; or HARMONIC_CACHE_MODE):"
Write-Host "    Set-Content .harmonic-cache-mode ro    # pull only"
Write-Host "    Set-Content .harmonic-cache-mode off   # disable"
Write-Host ""
Write-Host "Auth is keyless (DefaultAzureCredential): `az login` on a dev box, the"
Write-Host "VM's managed identity on the builder. No drive to mount, no port 445."
