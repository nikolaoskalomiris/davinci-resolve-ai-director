param(
    [Parameter(Mandatory=$true)][string]$ExtractedRuntimeRoot,
    [Parameter(Mandatory=$true)][string]$LocalAppData,
    [Parameter(Mandatory=$true)][string]$ReportPath
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2.0

$AdvancedVersion = '4.15.3'
$AdvancedRelative = 'AIDirector\DaVinciResolve\Runtime\MCP\Advanced\4.15.3'
$SeedRelative = 'AIDirector\DaVinciResolve\Updates\MCP\Bootstrap\davinci-resolve-mcp-4.15.3-931bc2cda8fd.tar.gz'
$ExpectedPayloadManifestSha256 = '093DB2168F3FAD4FD14915BADE393183DAA5FF4B3A4C6BF0C6856597A916A09D'
$ExpectedMandatoryManifestSha256 = '5F6A6CE58F7D8B9F96A2FC4FBDDE42E26A8E6538B4D590C1980700656C9AF9BD'
$ExpectedProvenanceSha256 = '165AC34CC84ACEEFCF8125E4832A80D850ECEA1FB90B986300DEA77616DA990C'
$ExpectedNativeReproSha256 = '94ACAD418CB1698029EF69955FD2EBCAD503177DEAC2CBC633B7B3DF64B590F1'
$ExpectedThirdPartyInventorySha256 = '22F1B0E06BFB32773837594C6EBB202E64CD6EA6E0C1A9913427D0BADFEB51B8'
$ExpectedSeedSha256 = 'E36B8CB5EB73A3BC2099E7D48E15EA119D6D8411D890651DF17B76BFD3781D5C'
$ExpectedImageFileCount = 4609
$ExpectedPayloadEntries = 4608

function Get-Sha256Upper {
    param([Parameter(Mandatory=$true)][string]$Path)
    return (Get-FileHash -LiteralPath $Path -Algorithm SHA256 -ErrorAction Stop).Hash.ToUpperInvariant()
}

function Write-JsonNoBom {
    param([Parameter(Mandatory=$true)][string]$Path,[Parameter(Mandatory=$true)][object]$Value)
    $parent = Split-Path -Parent $Path
    if ($parent -and -not (Test-Path -LiteralPath $parent)) {
        New-Item -ItemType Directory -Path $parent -Force -ErrorAction Stop | Out-Null
    }
    $utf8 = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($Path, (($Value | ConvertTo-Json -Depth 20) + "`n"), $utf8)
}

function Assert-FileHash {
    param([string]$Path,[string]$Expected,[string]$Label)
    if (-not (Test-Path -LiteralPath $Path -PathType Leaf)) {
        throw "$Label missing: $Path"
    }
    $actual = Get-Sha256Upper -Path $Path
    if ($actual -ne $Expected) {
        throw "$Label hash mismatch. Expected=$Expected Actual=$actual Path=$Path"
    }
}

function Assert-AdvancedImage {
    param([Parameter(Mandatory=$true)][string]$Root,[Parameter(Mandatory=$true)][string]$Label)

    if (-not (Test-Path -LiteralPath $Root -PathType Container)) {
        throw "$Label root missing: $Root"
    }

    Assert-FileHash -Path (Join-Path $Root 'PAYLOAD-SHA256.json') -Expected $ExpectedPayloadManifestSha256 -Label "$Label payload manifest"
    Assert-FileHash -Path (Join-Path $Root 'ADVANCED-NODE-MANDATORY-DEPENDENCY-IMAGE-MANIFEST.json') -Expected $ExpectedMandatoryManifestSha256 -Label "$Label mandatory manifest"
    Assert-FileHash -Path (Join-Path $Root 'ADVANCED-NODE-DEPENDENCY-IMAGE-PROVENANCE.json') -Expected $ExpectedProvenanceSha256 -Label "$Label provenance"
    Assert-FileHash -Path (Join-Path $Root 'NATIVE-REPRODUCIBILITY.json') -Expected $ExpectedNativeReproSha256 -Label "$Label native reproducibility"
    Assert-FileHash -Path (Join-Path $Root 'THIRD-PARTY-PACKAGES-4.15.3.json') -Expected $ExpectedThirdPartyInventorySha256 -Label "$Label third-party inventory"

    $manifest = Get-Content -LiteralPath (Join-Path $Root 'PAYLOAD-SHA256.json') -Raw | ConvertFrom-Json
    $rows = @($manifest.files)
    if ($rows.Count -ne $ExpectedPayloadEntries) {
        throw "$Label payload entry count mismatch. Expected=$ExpectedPayloadEntries Actual=$($rows.Count)"
    }

    $listed = @{}
    foreach ($row in $rows) {
        $rel = [string]$row.path
        if ([string]::IsNullOrWhiteSpace($rel) -or $rel.Contains('..') -or [System.IO.Path]::IsPathRooted($rel)) {
            throw "$Label unsafe payload path: $rel"
        }
        $p = Join-Path $Root ($rel.Replace('/', '\'))
        if (-not (Test-Path -LiteralPath $p -PathType Leaf)) {
            throw "$Label payload file missing: $rel"
        }
        if ((Get-Item -LiteralPath $p).Length -ne [long]$row.size) {
            throw "$Label payload size mismatch: $rel"
        }
        if ((Get-Sha256Upper -Path $p) -ne ([string]$row.sha256).ToUpperInvariant()) {
            throw "$Label payload hash mismatch: $rel"
        }
        $listed[$rel.ToLowerInvariant()] = $true
    }

    $actual = @(Get-ChildItem -LiteralPath $Root -File -Recurse)
    if ($actual.Count -ne $ExpectedImageFileCount) {
        throw "$Label image file count mismatch. Expected=$ExpectedImageFileCount Actual=$($actual.Count)"
    }
    foreach ($p in $actual) {
        $rel = $p.FullName.Substring($Root.Length).TrimStart('\').Replace('\','/')
        if ($rel -ieq 'PAYLOAD-SHA256.json') { continue }
        if (-not $listed.ContainsKey($rel.ToLowerInvariant())) {
            throw "$Label unexpected image file: $rel"
        }
    }
}

$sourceAdvanced = Join-Path $ExtractedRuntimeRoot $AdvancedRelative
$sourceSeed = Join-Path $ExtractedRuntimeRoot $SeedRelative
$targetAdvanced = Join-Path $LocalAppData $AdvancedRelative
$targetSeed = Join-Path $LocalAppData $SeedRelative

$createdAdvanced = $false
$createdSeed = $false
$report = [ordered]@{
    schema_version = 1
    status = 'RUNNING'
    advanced_version = $AdvancedVersion
    advanced_target = $targetAdvanced
    bootstrap_target = $targetSeed
    advanced_action = $null
    bootstrap_action = $null
    protected_active_source_mutation = $false
    protected_python_mutation = $false
    protected_manifest_mutation = $false
    protected_config_mutation = $false
}

try {
    Assert-AdvancedImage -Root $sourceAdvanced -Label 'source Advanced 4.15.3'
    Assert-FileHash -Path $sourceSeed -Expected $ExpectedSeedSha256 -Label 'source MCP 4.15.3 bootstrap seed'

    if (Test-Path -LiteralPath $targetAdvanced) {
        if (-not (Test-Path -LiteralPath $targetAdvanced -PathType Container)) {
            throw "Advanced target exists but is not a directory: $targetAdvanced"
        }
        Assert-AdvancedImage -Root $targetAdvanced -Label 'existing Advanced 4.15.3'
        $report.advanced_action = 'PRESERVED_VERIFIED'
    }
    else {
        $parent = Split-Path -Parent $targetAdvanced
        New-Item -ItemType Directory -Path $parent -Force -ErrorAction Stop | Out-Null
        $temp = "$targetAdvanced.aidir-new-$PID"
        if (Test-Path -LiteralPath $temp) {
            Remove-Item -LiteralPath $temp -Recurse -Force -ErrorAction Stop
        }
        Copy-Item -LiteralPath $sourceAdvanced -Destination $temp -Recurse -Force -ErrorAction Stop
        Assert-AdvancedImage -Root $temp -Label 'staged Advanced 4.15.3'
        Move-Item -LiteralPath $temp -Destination $targetAdvanced -ErrorAction Stop
        $createdAdvanced = $true
        $report.advanced_action = 'ADDED_VERIFIED'
    }

    $seedParent = Split-Path -Parent $targetSeed
    if (Test-Path -LiteralPath $targetSeed) {
        Assert-FileHash -Path $targetSeed -Expected $ExpectedSeedSha256 -Label 'existing MCP 4.15.3 bootstrap seed'
        $report.bootstrap_action = 'PRESERVED_VERIFIED'
    }
    else {
        New-Item -ItemType Directory -Path $seedParent -Force -ErrorAction Stop | Out-Null
        $tempSeed = "$targetSeed.aidir-new-$PID"
        Copy-Item -LiteralPath $sourceSeed -Destination $tempSeed -Force -ErrorAction Stop
        Assert-FileHash -Path $tempSeed -Expected $ExpectedSeedSha256 -Label 'staged MCP 4.15.3 bootstrap seed'
        Move-Item -LiteralPath $tempSeed -Destination $targetSeed -ErrorAction Stop
        $createdSeed = $true
        $report.bootstrap_action = 'ADDED_VERIFIED'
    }

    Assert-AdvancedImage -Root $targetAdvanced -Label 'final Advanced 4.15.3'
    Assert-FileHash -Path $targetSeed -Expected $ExpectedSeedSha256 -Label 'final MCP 4.15.3 bootstrap seed'

    $report.status = 'PASS_ADDITIVE_MCP_COMPATIBILITY_ASSETS'
    Write-JsonNoBom -Path $ReportPath -Value $report
    Write-Host 'A6_ADDITIVE_MCP_COMPATIBILITY_ASSETS=PASS'
    Write-Host ('ADVANCED_ACTION=' + $report.advanced_action)
    Write-Host ('BOOTSTRAP_ACTION=' + $report.bootstrap_action)
    exit 0
}
catch {
    if ($createdSeed -and (Test-Path -LiteralPath $targetSeed -PathType Leaf)) {
        Remove-Item -LiteralPath $targetSeed -Force -ErrorAction SilentlyContinue
    }
    if ($createdAdvanced -and (Test-Path -LiteralPath $targetAdvanced -PathType Container)) {
        Remove-Item -LiteralPath $targetAdvanced -Recurse -Force -ErrorAction SilentlyContinue
    }
    $report.status = 'FAIL_CLOSED'
    $report.error = $_.Exception.Message
    try { Write-JsonNoBom -Path $ReportPath -Value $report } catch {}
    Write-Host 'A6_ADDITIVE_MCP_COMPATIBILITY_ASSETS=FAIL_CLOSED'
    Write-Host ('ERROR=' + $_.Exception.Message)
    exit 1
}
