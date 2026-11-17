# Installer-only, offline seed. Never replaces an existing provider or deletes a tree.
[CmdletBinding()]
param(
    [Parameter(Mandatory=$true)][string]$PayloadRoot,
    [Parameter(Mandatory=$true)][string]$ProductRoot
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$manifestHash = 'C30427CAA6DDF5C71D096645FD9A78155C8DD29E529F95221DC2015B20F1773B'
$stage = $null
$destination = $null

# ReparsePoint catches junctions/symlinks; file identity also rejects hard links.
Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
using Microsoft.Win32.SafeHandles;
public static class AIDProviderFileIdentity {
    [StructLayout(LayoutKind.Sequential)]
    public struct Info {
        public uint Attributes;
        public System.Runtime.InteropServices.ComTypes.FILETIME Creation, Access, Write;
        public uint Volume, SizeHigh, SizeLow, Links, IndexHigh, IndexLow;
    }
    [DllImport("kernel32.dll", SetLastError=true)]
    public static extern bool GetFileInformationByHandle(SafeFileHandle h, out Info info);
    public static void RequireSingleLink(string path) {
        using (var f = new System.IO.FileStream(path, System.IO.FileMode.Open,
                   System.IO.FileAccess.Read, System.IO.FileShare.Read)) {
            Info i;
            if (!GetFileInformationByHandle(f.SafeFileHandle, out i) || i.Links != 1)
                throw new System.IO.IOException("Provider file identity/link check failed");
        }
    }
}
'@

function Assert-PlainAncestry([string]$Path) {
    $full = [IO.Path]::GetFullPath($Path)
    $item = $full
    while ($item) {
        if (Test-Path -LiteralPath $item) {
            $entry = Get-Item -LiteralPath $item -Force
            if (($entry.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
                throw 'Reparse point in provider path'
            }
        } elseif ([IO.File]::Exists($item) -or [IO.Directory]::Exists($item)) {
            throw 'Inaccessible provider path'
        }
        $parent = [IO.Path]::GetDirectoryName($item)
        if ($parent -eq $item) { break }
        $item = $parent
    }
    return $full
}

function Get-VerifiedInventory([string]$Root) {
    $rootPath = Assert-PlainAncestry $Root
    if (-not [IO.Directory]::Exists($rootPath)) { throw 'Provider directory missing' }
    $manifest = Join-Path $rootPath 'PROVIDER-MANIFEST.json'
    [AIDProviderFileIdentity]::RequireSingleLink($manifest)
    if ((Get-FileHash -LiteralPath $manifest -Algorithm SHA256).Hash -cne $manifestHash) {
        throw 'Pinned provider manifest mismatch'
    }
    $data = [IO.File]::ReadAllText($manifest) | ConvertFrom-Json
    if ($data.schema_version -ne 1 -or $data.provider -cne 'brave-search' -or
        $data.version -cne '2.1.4' -or $data.entrypoint -cne 'dist/index.js' -or
        @($data.files).Count -ne 3589) { throw 'Provider manifest contract mismatch' }
    $expected = [Collections.Generic.Dictionary[string,object]]::new([StringComparer]::OrdinalIgnoreCase)
    $directories = [Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
    $expected.Add('PROVIDER-MANIFEST.json', $null)
    foreach ($empty in @('node_modules/@esbuild','node_modules/@nodelib','node_modules/@types')) {
        [void]$directories.Add($empty)
    }
    foreach ($row in $data.files) {
        $relative = [string]$row.path
        if ($relative -notmatch '^[A-Za-z0-9_@.+/-]+$' -or $relative.StartsWith('/') -or
            $relative -match '(^|/)(\.|\.\.)(/|$)' -or $relative.Contains('//') -or
            $relative.EndsWith('/') -or $relative -match '(^|/)[^/]*[. ](/|$)' -or
            $expected.ContainsKey($relative)) { throw 'Unsafe or duplicate provider path' }
        $expected.Add($relative, $row)
        $parts = $relative.Split('/')
        for ($i=1; $i -lt $parts.Length; $i++) {
            [void]$directories.Add(($parts[0..($i-1)] -join '/'))
        }
    }
    # Walk one level at a time: never recurse through a reparse point.
    $pending = [Collections.Generic.Queue[string]]::new()
    $pending.Enqueue($rootPath)
    $seen = [Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
    $seenDirectories = [Collections.Generic.HashSet[string]]::new([StringComparer]::OrdinalIgnoreCase)
    while ($pending.Count -gt 0) {
        $directory = $pending.Dequeue()
        foreach ($entry in @(Get-ChildItem -LiteralPath $directory -Force)) {
            if (($entry.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
                throw 'Provider reparse point rejected'
            }
            $relative = $entry.FullName.Substring($rootPath.TrimEnd('\').Length + 1).Replace('\','/')
            if ($entry.PSIsContainer) {
                if (-not $directories.Contains($relative) -or -not $seenDirectories.Add($relative)) { throw 'Unexpected provider directory' }
                $pending.Enqueue($entry.FullName)
            } else {
                if (-not $expected.ContainsKey($relative) -or -not $seen.Add($relative)) {
                    throw 'Unexpected or duplicate provider file'
                }
                [AIDProviderFileIdentity]::RequireSingleLink($entry.FullName)
                $row = $expected[$relative]
                if ($null -ne $row) {
                    if ($entry.Length -ne $row.bytes -or
                        (Get-FileHash -LiteralPath $entry.FullName -Algorithm SHA256).Hash -cne $row.sha256) {
                        throw 'Provider file size/hash mismatch'
                    }
                }
            }
        }
    }
    if ($seenDirectories.Count -ne $directories.Count) { throw 'Provider directory set incomplete' }
    if ($seen.Count -ne $expected.Count) { throw 'Provider file set incomplete' }
    # Recheck after traversal as well as before trusting manifest rows.
    if ((Get-FileHash -LiteralPath $manifest -Algorithm SHA256).Hash -cne $manifestHash) {
        throw 'Provider manifest changed during validation'
    }
    return $data
}

try {
    $payload = Assert-PlainAncestry $PayloadRoot
    $product = Assert-PlainAncestry $ProductRoot
    $destination = Join-Path $product 'Runtime\MCP\Brave\2.1.4'
    [void](Assert-PlainAncestry $destination)
    $inventory = Get-VerifiedInventory $payload
    if (Test-Path -LiteralPath $destination) {
        [void](Get-VerifiedInventory $destination)
        @{status='VERIFIED_RETAINED'; destination=$destination} | ConvertTo-Json -Compress
        exit 0
    }
    $parent = Split-Path -Parent $destination
    [void](Assert-PlainAncestry $parent)
    [void][IO.Directory]::CreateDirectory($parent)
    $stage = Join-Path $parent ('2.1.4.aidir-new-' + [Guid]::NewGuid().ToString('N'))
    if (Test-Path -LiteralPath $stage) { throw 'Operation staging collision' }
    [void][IO.Directory]::CreateDirectory($stage)
    foreach ($relative in @('PROVIDER-MANIFEST.json') + @($inventory.files | ForEach-Object { $_.path })) {
        $source = Join-Path $payload $relative
        $target = Join-Path $stage $relative
        [void](Assert-PlainAncestry $source)
        [void][IO.Directory]::CreateDirectory((Split-Path -Parent $target))
        [IO.File]::Copy($source, $target, $false)
    }
    foreach ($empty in @('node_modules/@esbuild','node_modules/@nodelib','node_modules/@types')) {
        [void][IO.Directory]::CreateDirectory((Join-Path $stage $empty))
    }
    [void](Get-VerifiedInventory $stage)
    [void](Assert-PlainAncestry $destination)
    # Directory.Move is a same-volume sibling rename, never a merge/replace.
    # A concurrent installer winning the destination race causes failure, not overwrite.
    [IO.Directory]::Move($stage, $destination)
    $stage = $null
    [void](Get-VerifiedInventory $destination)
    @{status='VERIFIED_SEEDED'; destination=$destination} | ConvertTo-Json -Compress
    exit 0
} catch {
    # Preserve operation-owned partial evidence. No recursive cleanup or rollback
    # ever touches an existing/possibly active provider. Retry requires operator review.
    @{status='FAIL_CLOSED'; destination=$destination; retained_stage=$stage; error=$_.Exception.Message} | ConvertTo-Json -Compress
    exit 1
}
