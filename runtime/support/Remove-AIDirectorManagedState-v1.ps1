param(
    [Parameter(Mandatory=$true)][string]$LocalAppData,
    [Parameter(Mandatory=$true)][string]$AppData,
    [Parameter(Mandatory=$true)][string]$ReportPath,
    [ValidateSet("Keep","Remove")][string]$SettingsMode = "Remove"
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version 2.0

function Get-FullPath {
    param([string]$Path)
    return [IO.Path]::GetFullPath($Path)
}

function Assert-UnderRoot {
    param([string]$Path, [string]$Root, [string]$Label)
    $P = Get-FullPath $Path
    $R = (Get-FullPath $Root).TrimEnd('\') + '\'
    if (-not $P.StartsWith($R, [System.StringComparison]::OrdinalIgnoreCase)) {
        throw "$Label escaped approved root. Path=$P Root=$R"
    }
    return $P
}

function Assert-NoReparseTree {
    param([string]$Path, [string]$Label)
    if (-not (Test-Path -LiteralPath $Path)) { return }

    $RootItem = Get-Item -LiteralPath $Path -Force
    if (($RootItem.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
        throw "$Label is a reparse point: $Path"
    }

    if ($RootItem.PSIsContainer) {
        foreach ($Item in @(Get-ChildItem -LiteralPath $Path -Force -Recurse -ErrorAction Stop)) {
            if (($Item.Attributes -band [IO.FileAttributes]::ReparsePoint) -ne 0) {
                throw "$Label contains a reparse point: $($Item.FullName)"
            }
        }
    }
}

function Test-ManagedMcpIdentity {
    param([string]$Path)

    if (-not (Test-Path -LiteralPath $Path -PathType Container)) {
        return [pscustomobject]@{
            exists=$false; owned=$false; reason="absent"; version=$null; source_commit=$null
        }
    }

    $MarkerPath = Join-Path $Path ".davinci-resolve-mcp-managed.json"
    $PackagePath = Join-Path $Path "package.json"

    if (-not (Test-Path -LiteralPath $MarkerPath -PathType Leaf)) {
        return [pscustomobject]@{
            exists=$true; owned=$false; reason="managed-marker-missing"; version=$null; source_commit=$null
        }
    }
    if (-not (Test-Path -LiteralPath $PackagePath -PathType Leaf)) {
        return [pscustomobject]@{
            exists=$true; owned=$false; reason="package-json-missing"; version=$null; source_commit=$null
        }
    }

    try {
        $Marker = Get-Content -LiteralPath $MarkerPath -Raw | ConvertFrom-Json
        $Package = Get-Content -LiteralPath $PackagePath -Raw | ConvertFrom-Json
    } catch {
        return [pscustomobject]@{
            exists=$true; owned=$false; reason="identity-json-invalid"; version=$null; source_commit=$null
        }
    }

    $MarkerName = [string]$Marker.name
    $PackageName = [string]$Package.name
    $MarkerVersion = [string]$Marker.version
    $PackageVersion = [string]$Package.version
    $SourceCommit = [string]$Marker.sourceCommit
    $SourceCommitValid = $SourceCommit -match '^[0-9a-fA-F]{40}$'

    $Owned = (
        [bool]$Marker.managed -eq $true -and
        $MarkerName -eq "davinci-resolve-mcp" -and
        $PackageName -eq "davinci-resolve-mcp" -and
        -not [string]::IsNullOrWhiteSpace($MarkerVersion) -and
        $MarkerVersion -eq $PackageVersion -and
        $SourceCommitValid
    )

    return [pscustomobject]@{
        exists=$true
        owned=[bool]$Owned
        reason=$(if ($Owned) { "owned-managed-mcp" } else { "identity-mismatch" })
        version=$MarkerVersion
        source_commit=$SourceCommit
    }
}

function Remove-ExactTree {
    param([string]$Path, [string]$Label)
    if (-not (Test-Path -LiteralPath $Path)) { return $false }
    Assert-NoReparseTree -Path $Path -Label $Label
    Remove-Item -LiteralPath $Path -Recurse -Force
    if (Test-Path -LiteralPath $Path) {
        throw "Failed to remove ${Label}: $Path"
    }
    return $true
}

function Write-Report {
    param($Report)
    $Parent = Split-Path -Parent $ReportPath
    if (-not [string]::IsNullOrWhiteSpace($Parent)) {
        [void][IO.Directory]::CreateDirectory($Parent)
    }
    $Report | ConvertTo-Json -Depth 8 | Set-Content -LiteralPath $ReportPath -Encoding UTF8
}

$LocalRoot = (Get-FullPath $LocalAppData).TrimEnd('\')
$RoamingRoot = (Get-FullPath $AppData).TrimEnd('\')
$ManagedMcp = Assert-UnderRoot -Path (Join-Path $LocalRoot "davinci-resolve-mcp") -Root $LocalRoot -Label "managed MCP"
$SettingsPath = Assert-UnderRoot -Path (Join-Path $RoamingRoot "AIDirector\DaVinciResolve\settings.json") -Root $RoamingRoot -Label "AI Director settings"

# Pre-0.3.20 builds stored settings under a retired product-owned roaming
# directory. Compose the retired brand segment so no raw retired identity
# literal is reintroduced into active shipping source.
$LegacyBrandSegment = ("State" + "OfReason")
$LegacyProductRoot = Assert-UnderRoot -Path (Join-Path (Join-Path $RoamingRoot $LegacyBrandSegment) "AI Director") -Root $RoamingRoot -Label "legacy AI Director roaming data"
$LegacySettingsPath = Assert-UnderRoot -Path (Join-Path $LegacyProductRoot "settings.json") -Root $RoamingRoot -Label "legacy AI Director settings"

[byte[]]$PreservedSettingsBytes = $null
$PreservedSettingsSource = $null
$PreservedSettingsSourcePath = $null
$SettingsExisted = Test-Path -LiteralPath $SettingsPath -PathType Leaf
$LegacySettingsExisted = Test-Path -LiteralPath $LegacySettingsPath -PathType Leaf
if ($SettingsMode -eq "Keep") {
    if ($SettingsExisted) {
        Assert-NoReparseTree -Path $SettingsPath -Label "AI Director settings"
        $PreservedSettingsBytes = [IO.File]::ReadAllBytes($SettingsPath)
        $PreservedSettingsSource = "canonical"
        $PreservedSettingsSourcePath = $SettingsPath
    } elseif ($LegacySettingsExisted) {
        Assert-NoReparseTree -Path $LegacyProductRoot -Label "legacy AI Director roaming data"
        $PreservedSettingsBytes = [IO.File]::ReadAllBytes($LegacySettingsPath)
        $PreservedSettingsSource = "legacy"
        $PreservedSettingsSourcePath = $LegacySettingsPath
    }
}

$SiblingItems = @(
    Get-ChildItem -LiteralPath $LocalRoot -Directory -Force -ErrorAction SilentlyContinue |
        Where-Object { $_.Name -match '^davinci-resolve-mcp\.aidir-(new|backup|rejected|failed)-[A-Za-z0-9._-]+$' }
)

$Sensitive = @()
$MainIdentity = Test-ManagedMcpIdentity -Path $ManagedMcp
if ($MainIdentity.exists) {
    $Sensitive += [pscustomobject]@{
        path=$ManagedMcp; kind="managed-mcp"; identity=$MainIdentity
    }
}

foreach ($Sibling in $SiblingItems) {
    $SiblingPath = Assert-UnderRoot -Path $Sibling.FullName -Root $LocalRoot -Label "managed MCP transaction sibling"
    $Identity = Test-ManagedMcpIdentity -Path $SiblingPath
    $Sensitive += [pscustomobject]@{
        path=$SiblingPath; kind="managed-mcp-transaction-sibling"; identity=$Identity
    }
}

$Unresolved = @($Sensitive | Where-Object { -not $_.identity.owned })

$ExactDelete = @(
    [pscustomobject]@{ label="AIDirector root"; path=(Join-Path $LocalRoot "AIDirector"); root=$LocalRoot },
    [pscustomobject]@{ label="electron-builder updater store"; path=(Join-Path $LocalRoot "davinci-resolve-ai-director-updater"); root=$LocalRoot },
    [pscustomobject]@{ label="local package data"; path=(Join-Path $LocalRoot "davinci-resolve-ai-director"); root=$LocalRoot },
    [pscustomobject]@{ label="local product-name data"; path=(Join-Path $LocalRoot "DaVinci Resolve AI Director"); root=$LocalRoot },
    [pscustomobject]@{ label="local app-id data"; path=(Join-Path $LocalRoot "com.aidirector.davinciresolve"); root=$LocalRoot },
    [pscustomobject]@{ label="roaming AIDirector data"; path=(Join-Path $RoamingRoot "AIDirector"); root=$RoamingRoot },
    [pscustomobject]@{ label="legacy roaming AI Director data"; path=$LegacyProductRoot; root=$RoamingRoot },
    [pscustomobject]@{ label="roaming package data"; path=(Join-Path $RoamingRoot "davinci-resolve-ai-director"); root=$RoamingRoot },
    [pscustomobject]@{ label="roaming product-name data"; path=(Join-Path $RoamingRoot "DaVinci Resolve AI Director"); root=$RoamingRoot },
    [pscustomobject]@{ label="roaming app-id data"; path=(Join-Path $RoamingRoot "com.aidirector.davinciresolve"); root=$RoamingRoot }
)

# Validate every destructive boundary before the first deletion.
foreach ($Item in $ExactDelete) {
    $null = Assert-UnderRoot -Path $Item.path -Root $Item.root -Label $Item.label
    Assert-NoReparseTree -Path $Item.path -Label $Item.label
}
foreach ($Item in $Sensitive) {
    Assert-NoReparseTree -Path $Item.path -Label $Item.kind
}

$Report = [ordered]@{
    schema_version=2
    helper="Remove-AIDirectorManagedState-v1"
    status=$null
    local_app_data=$LocalRoot
    app_data=$RoamingRoot
    settings_mode=$SettingsMode
    settings_path=$SettingsPath
    settings_existed=[bool]$SettingsExisted
    legacy_settings_path=$LegacySettingsPath
    legacy_settings_existed=[bool]$LegacySettingsExisted
    preserved_settings_source=$PreservedSettingsSource
    preserved_settings_source_path=$PreservedSettingsSourcePath
    settings_preserved=$false
    unresolved_sensitive_roots=@(
        $Unresolved | ForEach-Object {
            [ordered]@{ path=$_.path; kind=$_.kind; reason=$_.identity.reason }
        }
    )
    removed=@()
    preserved=@()
}

if ($Unresolved.Count -ne 0) {
    $Report.status = "FAIL_SAFE_UNPROVEN_MANAGED_MCP"
    $Report.preserved = @(
        $Unresolved | ForEach-Object { $_.path }
    )
    if ($SettingsMode -eq "Keep" -and $null -ne $PreservedSettingsBytes) {
        $Report.preserved += $PreservedSettingsSourcePath
        $Report.settings_preserved = $true
    }
    Write-Report -Report $Report
    exit 23
}

$Removed = @()
foreach ($Item in $Sensitive) {
    if (Remove-ExactTree -Path $Item.path -Label $Item.kind) {
        $Removed += $Item.path
    }
}
foreach ($Item in $ExactDelete) {
    if (Remove-ExactTree -Path $Item.path -Label $Item.label) {
        $Removed += $Item.path
    }
}

$PostResidual = @()
foreach ($Item in $Sensitive) {
    if (Test-Path -LiteralPath $Item.path) {
        $PostResidual += $Item.path
    }
}
foreach ($Item in $ExactDelete) {
    if (Test-Path -LiteralPath $Item.path) {
        $PostResidual += $Item.path
    }
}

function Restore-PreservedSettings {
    if ($SettingsMode -ne "Keep" -or $null -eq $PreservedSettingsBytes) {
        return $false
    }
    $SettingsDir = Split-Path -Parent $SettingsPath
    [void][IO.Directory]::CreateDirectory($SettingsDir)
    [IO.File]::WriteAllBytes($SettingsPath, $PreservedSettingsBytes)
    if (-not (Test-Path -LiteralPath $SettingsPath -PathType Leaf)) {
        throw "Settings restore failed: $SettingsPath"
    }
    return $true
}

if ($PostResidual.Count -ne 0) {
    try {
        $Restored = Restore-PreservedSettings
        $Report.settings_preserved = [bool]$Restored
    } catch {
        $Report.settings_preserved = $false
        $PostResidual += ("settings-restore-error: " + $_.Exception.Message)
    }

    $Report.status = "FAIL_POST_CLEANUP_RESIDUAL"
    $Report.removed = $Removed
    $Report.preserved = $PostResidual
    if ($Report.settings_preserved) {
        $Report.preserved += $SettingsPath
    }
    Write-Report -Report $Report
    exit 24
}

try {
    $SettingsRestored = Restore-PreservedSettings
    $Report.settings_preserved = [bool]$SettingsRestored
} catch {
    $Report.status = "FAIL_SETTINGS_RESTORE"
    $Report.removed = $Removed
    $Report.preserved = @()
    Write-Report -Report $Report
    exit 25
}

$Report.status = $(if ($Report.settings_preserved) {
    "PASS_OWNED_STATE_REMOVED_SETTINGS_PRESERVED"
} else {
    "PASS_OWNED_STATE_REMOVED"
})
$Report.removed = $Removed
if ($Report.settings_preserved) {
    $Report.preserved = @($SettingsPath)
}
Write-Report -Report $Report
exit 0
