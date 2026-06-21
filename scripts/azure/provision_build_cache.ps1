<#
.SYNOPSIS
  Provision the Azure Files SMB share that backs the harmonic-analyzer build cache
  (the `dir` backend of cad/scripts/_artifact_cache.py). Idempotent -- safe to
  re-run; `az ... create` no-ops when the resource already exists.

.DESCRIPTION
  Creates, in the SAME resource group / region as vm-solidworks:
    * a Standard_LRS StorageV2 account (cheap, locally-redundant -- a cache is
      disposable, so no geo-redundancy)
    * an SMB file share `buildcache` (256 GiB quota cap; Standard shares bill on
      USED GB + transactions, so the cap costs nothing until filled)

  Azure Files has NO native lifecycle policy, so retention is handled separately
  by cleanup_build_cache.ps1 (a scheduled delete-older-than-7-days job).

  Run once by an operator with az logged in to the Dev/Test subscription. New
  builder machines do NOT run this -- they run mount_build_cache.ps1.
#>
[CmdletBinding()]
param(
  [string]$ResourceGroup = 'RG-SOLIDWORKS-DEV',
  [string]$Location      = 'eastus2',
  [string]$StorageAccount = 'stswbuildcache07aba2',
  [string]$Share         = 'buildcache',
  [int]   $QuotaGiB      = 256
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

Write-Host ">> file share $Share ($QuotaGiB GiB) ..."
az storage share-rm create `
  --resource-group $ResourceGroup `
  --storage-account $StorageAccount `
  --name $Share `
  --quota $QuotaGiB `
  --only-show-errors --output none

$unc = "\\$StorageAccount.file.core.windows.net\$Share"
Write-Host ""
Write-Host "Done. Share UNC path:"
Write-Host "    $unc"
Write-Host ""
Write-Host "Next, on each builder/dev machine:"
Write-Host "    # read-only puller (no SolidWorks seat):"
Write-Host "    scripts\azure\mount_build_cache.ps1 -Mode ro"
Write-Host "    # the SolidWorks seat that populates the cache:"
Write-Host "    scripts\azure\mount_build_cache.ps1 -Mode rw -Salt sw2024-sp3"
Write-Host "Then, ONCE on the always-on seat (vm-solidworks):"
Write-Host "    scripts\azure\cleanup_build_cache.ps1 -Register"
