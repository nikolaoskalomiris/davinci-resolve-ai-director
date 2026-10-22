param(
    [string]$BuilderRoot,
    [string]$AssetRoot
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version 2.0

$ScriptRoot = Split-Path -Parent $MyInvocation.MyCommand.Path

if (-not $BuilderRoot) {
    $BuilderRoot = Split-Path -Parent $ScriptRoot
}

$BuilderRoot = (Resolve-Path -LiteralPath $BuilderRoot).Path

if ($AssetRoot) {
    $AssetRoot = (Resolve-Path -LiteralPath $AssetRoot).Path
}

$ManifestPath = Join-Path $ScriptRoot "bootstrap-inputs.json"
$ExpectedManifestSha256 = "72CCFE47EE2CA6575D3F5224D24B3FCE6BF38D57D1288ED90CB51D1D9D39C97C"

function Require {
    param(
        [bool]$Condition,
        [string]$Message
    )

    if (-not $Condition) {
        throw $Message
    }
}

function Get-Sha256 {
    param([string]$Path)

    return (
        Get-FileHash -LiteralPath $Path -Algorithm SHA256
    ).Hash.ToUpperInvariant()
}

function Write-Utf8NoBom {
    param(
        [string]$Path,
        [string]$Text
    )

    $Encoding = New-Object System.Text.UTF8Encoding($false)
    [System.IO.File]::WriteAllText($Path, $Text, $Encoding)
}

function Get-TreeStats {
    param([string]$Path)

    $Files = @(
        Get-ChildItem -LiteralPath $Path -File -Recurse -Force -ErrorAction Stop
    )

    [int64]$Bytes = 0
    foreach ($File in $Files) {
        $Bytes += [int64]$File.Length
    }

    return [pscustomobject]@{
        Files = $Files.Count
        Bytes = $Bytes
    }
}

function Test-ProcessAlive {
    param([int]$ProcessId)

    if ($ProcessId -le 0) {
        return $false
    }

    $Hit = @(
        Get-Process -Id $ProcessId -ErrorAction SilentlyContinue
    )

    return ($Hit.Count -gt 0)
}

function Remove-EmptyCacheRoot {
    param([string]$CacheRoot)

    if (Test-Path -LiteralPath $CacheRoot -PathType Container) {
        $Items = @(
            Get-ChildItem -LiteralPath $CacheRoot -Force -ErrorAction Stop
        )

        if ($Items.Count -eq 0) {
            Remove-Item -LiteralPath $CacheRoot -Force
        }
    }
}

function Assert-FileIdentity {
    param(
        [string]$Path,
        [int64]$ExpectedBytes,
        [string]$ExpectedSha256,
        [string]$Label
    )

    Require (Test-Path -LiteralPath $Path -PathType Leaf) "$Label missing: $Path"

    $Item = Get-Item -LiteralPath $Path

    Require (
        [int64]$Item.Length -eq [int64]$ExpectedBytes
    ) "$Label byte-count mismatch. Expected=$ExpectedBytes Actual=$($Item.Length)"

    $ActualSha = Get-Sha256 -Path $Path

    Require (
        $ActualSha -eq $ExpectedSha256.ToUpperInvariant()
    ) "$Label SHA256 mismatch. Expected=$ExpectedSha256 Actual=$ActualSha"

    return $ActualSha
}

function Invoke-Download {
    param(
        [string]$Url,
        [string]$Destination
    )

    try {
        [Net.ServicePointManager]::SecurityProtocol = (
            [Net.ServicePointManager]::SecurityProtocol -bor
            [Net.SecurityProtocolType]::Tls12
        )
    }
    catch {
    }

    $Client = New-Object System.Net.WebClient

    try {
        $Client.Headers.Add(
            "User-Agent",
            "AI-Director-Builder-Bootstrap/1.0"
        )

        $Client.DownloadFile($Url, $Destination)
    }
    finally {
        $Client.Dispose()
    }
}

function Assert-CleanPython {
    param(
        [string]$PythonRoot,
        [string]$ExpectedVersion
    )

    $PythonExe = Join-Path $PythonRoot "python.exe"
    $Pth = Join-Path $PythonRoot "python311._pth"

    Require (Test-Path -LiteralPath $PythonExe -PathType Leaf) "Owned Python executable missing."
    Require (Test-Path -LiteralPath $Pth -PathType Leaf) "Owned Python _pth missing."

    $OldEap = $ErrorActionPreference
    try {
        $ErrorActionPreference = "Continue"
        $VersionOutput = @(& $PythonExe --version 2>&1)
        $ExitCode = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $OldEap
    }

    Require ($ExitCode -eq 0) "Owned Python version check failed."

    $VersionText = ($VersionOutput | Out-String).Trim()
    Require ($VersionText -eq $ExpectedVersion) "Owned Python version mismatch: $VersionText"

    $PthLines = @(
        Get-Content -LiteralPath $Pth |
        ForEach-Object { $_.TrimEnd() }
    )

    Require ($PthLines.Count -eq 2) "Owned Python _pth must contain exactly two lines."
    Require ($PthLines[0] -eq "python311.zip") "Owned Python _pth line 1 mismatch."
    Require ($PthLines[1] -eq ".") "Owned Python _pth line 2 mismatch."

    $PthText = Get-Content -LiteralPath $Pth -Raw
    Require ($PthText -notmatch "[A-Za-z]:\\") "Owned Python _pth contains an absolute Windows path."
    Require ($PthText -notmatch "\\ProgramData\\") "Owned Python _pth contains ProgramData residue."
}

function Assert-Node {
    param(
        [string]$NodeRoot,
        [string]$ExpectedNodeVersion,
        [string]$ExpectedNpmVersion,
        [int]$ExpectedFileCount,
        [int64]$ExpectedTreeBytes
    )

    $NodeExe = Join-Path $NodeRoot "node.exe"
    $NpmCli = Join-Path $NodeRoot "node_modules\npm\bin\npm-cli.js"

    Require (Test-Path -LiteralPath $NodeExe -PathType Leaf) "Owned Node executable missing."
    Require (Test-Path -LiteralPath $NpmCli -PathType Leaf) "Owned npm CLI missing."

    $OldEap = $ErrorActionPreference

    try {
        $ErrorActionPreference = "Continue"

        $NodeOutput = @(& $NodeExe --version 2>&1)
        $NodeExit = $LASTEXITCODE

        $NpmOutput = @(& $NodeExe $NpmCli --version 2>&1)
        $NpmExit = $LASTEXITCODE
    }
    finally {
        $ErrorActionPreference = $OldEap
    }

    Require ($NodeExit -eq 0) "Owned Node version check failed."
    Require ($NpmExit -eq 0) "Owned npm version check failed."

    $NodeVersion = ($NodeOutput | Out-String).Trim()
    $NpmVersion = ($NpmOutput | Out-String).Trim()

    Require ($NodeVersion -eq $ExpectedNodeVersion) "Owned Node version mismatch: $NodeVersion"
    Require ($NpmVersion -eq $ExpectedNpmVersion) "Owned npm version mismatch: $NpmVersion"

    $Stats = Get-TreeStats -Path $NodeRoot

    Require (
        $Stats.Files -eq $ExpectedFileCount
    ) "Owned Node tree file-count mismatch. Expected=$ExpectedFileCount Actual=$($Stats.Files)"

    Require (
        [int64]$Stats.Bytes -eq [int64]$ExpectedTreeBytes
    ) "Owned Node tree byte-count mismatch. Expected=$ExpectedTreeBytes Actual=$($Stats.Bytes)"
}

function Assert-InputPresent {
    param($InputRow)

    if ($InputRow.id -eq "python-3.11.9-embeddable-x64") {
        $Dest = Join-Path $BuilderRoot ($InputRow.destination -replace "/", "\")
        if (-not (Test-Path -LiteralPath $Dest -PathType Container)) {
            return $false
        }

        Assert-CleanPython `
            -PythonRoot $Dest `
            -ExpectedVersion $InputRow.postcheck.python_version

        return $true
    }

    if ($InputRow.id -eq "node-24.18.0-win-x64") {
        $Dest = Join-Path $BuilderRoot ($InputRow.destination -replace "/", "\")
        if (-not (Test-Path -LiteralPath $Dest -PathType Container)) {
            return $false
        }

        Assert-Node `
            -NodeRoot $Dest `
            -ExpectedNodeVersion $InputRow.postcheck.node_version `
            -ExpectedNpmVersion $InputRow.postcheck.npm_version `
            -ExpectedFileCount ([int]$InputRow.postcheck.file_count) `
            -ExpectedTreeBytes ([int64]$InputRow.postcheck.tree_bytes)

        return $true
    }

    $DestinationFile = Join-Path $BuilderRoot (
        $InputRow.destination_file -replace "/", "\"
    )

    if (-not (Test-Path -LiteralPath $DestinationFile -PathType Leaf)) {
        return $false
    }

    [void](Assert-FileIdentity `
        -Path $DestinationFile `
        -ExpectedBytes ([int64]$InputRow.bytes) `
        -ExpectedSha256 ([string]$InputRow.sha256) `
        -Label ([string]$InputRow.id))

    return $true
}

function Recover-StaleBootstrapIfNeeded {
    param(
        [string]$CacheRoot,
        [string]$LockPath
    )

    $OrphanStages = @(
        Get-ChildItem `
            -LiteralPath $CacheRoot `
            -Directory `
            -Force `
            -ErrorAction SilentlyContinue |
        Where-Object {
            $_.Name -like ".bootstrap.staging-*"
        }
    )

    if (-not (Test-Path -LiteralPath $LockPath)) {
        if ($OrphanStages.Count -ne 0) {
            $OrphanStageNames = @()

            foreach ($OrphanStage in $OrphanStages) {
                $OrphanStageNames += [string]$OrphanStage.FullName
            }

            throw (
                "Orphan bootstrap staging evidence exists without a Builder lock: " +
                ($OrphanStageNames -join "; ")
            )
        }

        return
    }

    Require (
        Test-Path -LiteralPath $LockPath -PathType Container
    ) "Builder operation lock path is not a directory."

    $MetaPath = Join-Path $LockPath "operation.json"
    Require (
        Test-Path -LiteralPath $MetaPath -PathType Leaf
    ) "Builder operation lock metadata missing."

    $Meta = Get-Content -LiteralPath $MetaPath -Raw | ConvertFrom-Json

    Require (
        [string]$Meta.operation -eq "BOOTSTRAP"
    ) "Builder operation lock belongs to another operation: $($Meta.operation)"

    $OwnerPid = [int]$Meta.pid

    Require (
        $OwnerPid -ne $PID
    ) "Existing bootstrap lock unexpectedly has the current process PID."

    if (Test-ProcessAlive -ProcessId $OwnerPid) {
        throw "Active bootstrap owner still exists: PID=$OwnerPid"
    }

    $ExpectedStage = Join-Path $CacheRoot ".bootstrap.staging-$OwnerPid"

    foreach ($Stage in $OrphanStages) {
        Require (
            $Stage.FullName -eq $ExpectedStage
        ) "Unexpected bootstrap staging directory while recovering stale lock: $($Stage.FullName)"
    }

    if (Test-Path -LiteralPath $ExpectedStage) {
        Remove-Item -LiteralPath $ExpectedStage -Recurse -Force
    }

    Remove-Item -LiteralPath $LockPath -Recurse -Force

    Remove-EmptyCacheRoot -CacheRoot $CacheRoot

    Write-Host "BOOTSTRAP_STALE_RECOVERY=PASS"
}

try {
    Write-Host "AI_DIRECTOR_BUILDER_BOOTSTRAP_V1_2"
    Write-Host ("BUILDER_ROOT=" + $BuilderRoot)
    Write-Host ("ASSET_ROOT=" + $(if ($AssetRoot) { $AssetRoot } else { "<NONE>" }))
    Write-Host "BUILD_EXECUTED=False"
    Write-Host "SYSTEM_TOOLCHAIN_INSTALLATION=EXTERNAL_NOT_AUTO_INSTALLED"
    Write-Host "SYSTEM_TOOLCHAIN_VALIDATOR=build/system-toolchain/verify_system_toolchain.py"
    Write-Host "SETUP_EXECUTED=False"
    Write-Host "INSTALLED_PRODUCT_TOUCHED=False"

    Require (
        Test-Path -LiteralPath $ManifestPath -PathType Leaf
    ) "Bootstrap input manifest missing."

    $ManifestSha = Get-Sha256 -Path $ManifestPath

    Require (
        $ManifestSha -eq $ExpectedManifestSha256
    ) "Bootstrap input manifest SHA256 mismatch."

    Write-Host ("BOOTSTRAP_MANIFEST_SHA256=" + $ManifestSha)
    Write-Host "BOOTSTRAP_MANIFEST=PASS"

    $Manifest = Get-Content -LiteralPath $ManifestPath -Raw | ConvertFrom-Json

    Require (
        [int]$Manifest.schema_version -eq 1
    ) "Unsupported bootstrap manifest schema."

    Require (
        [string]$Manifest.id -eq "AI-Director-Builder-Bootstrap-Inputs-v1"
    ) "Unexpected bootstrap manifest identity."

    $Inputs = @($Manifest.inputs)

    Require ($Inputs.Count -eq 9) "Unexpected bootstrap input count."

    foreach ($InputRow in $Inputs) {
        $InputId = [string]$InputRow.id
        $Kind = [string]$InputRow.kind
        $ArchiveName = [string]$InputRow.archive_name

        Require (
            -not [string]::IsNullOrWhiteSpace($InputId)
        ) "Bootstrap input id is missing."

        Require (
            -not [string]::IsNullOrWhiteSpace($ArchiveName)
        ) "Bootstrap archive name is missing: $InputId"

        Require (
            -not [string]::IsNullOrWhiteSpace([string]$InputRow.url)
        ) "Bootstrap input URL missing: $InputId"

        if ($Kind -eq "ai_director_release_asset") {
            Require (
                -not [string]::IsNullOrWhiteSpace([string]$InputRow.asset_root_relative_path)
            ) "Runtime asset-root relative path missing: $InputId"
        }
    }

    Write-Host "BOOTSTRAP_INPUT_MANIFEST_ROWS=PASS"

    $CacheRoot = Join-Path $BuilderRoot "_cache"
    $LockPath = Join-Path $CacheRoot ".builder-operation.lock"

    Recover-StaleBootstrapIfNeeded `
        -CacheRoot $CacheRoot `
        -LockPath $LockPath

    $Missing = @()

    foreach ($InputRow in $Inputs) {
        $Present = Assert-InputPresent -InputRow $InputRow

        if ($Present) {
            Write-Host ("BOOTSTRAP_INPUT_PRESENT=" + $InputRow.id)
        }
        else {
            $Missing += $InputRow
            Write-Host ("BOOTSTRAP_INPUT_MISSING=" + $InputRow.id)
        }
    }

    if ($Missing.Count -eq 0) {
        Write-Host "BOOTSTRAP_INPUTS_ALREADY_COMPLETE=True"
        Write-Host "BOOTSTRAP_MUTATED=False"
        Write-Host "BOOTSTRAP_STATUS=PASS"
        exit 0
    }

    if (-not (Test-Path -LiteralPath $CacheRoot)) {
        New-Item -ItemType Directory -Path $CacheRoot | Out-Null
    }

    $StageRoot = Join-Path $CacheRoot (".bootstrap.staging-" + $PID)

    Require (
        -not (Test-Path -LiteralPath $StageRoot)
    ) "Current bootstrap staging directory already exists."

    try {
        New-Item -ItemType Directory -Path $LockPath -ErrorAction Stop | Out-Null
    }
    catch {
        throw "Could not acquire Builder bootstrap lock: $LockPath"
    }

    $Operation = [ordered]@{
        schema_version = 1
        operation = "BOOTSTRAP"
        pid = $PID
        builder_root = $BuilderRoot
        staging_path = $StageRoot
        started_utc = [DateTime]::UtcNow.ToString("o")
    }

    Write-Utf8NoBom `
        -Path (Join-Path $LockPath "operation.json") `
        -Text (($Operation | ConvertTo-Json -Depth 5) + "`n")

    New-Item -ItemType Directory -Path $StageRoot | Out-Null

    $Downloads = Join-Path $StageRoot "downloads"
    $Activate = Join-Path $StageRoot "activate"

    New-Item -ItemType Directory -Path $Downloads | Out-Null
    New-Item -ItemType Directory -Path $Activate | Out-Null

    Write-Host "BOOTSTRAP_LOCK=ACQUIRED"

    foreach ($InputRow in $Missing) {
        $InputId = [string]$InputRow.id
        $ArchiveName = [string]$InputRow.archive_name
        $DownloadPath = Join-Path $Downloads $ArchiveName

        if ($InputRow.kind -eq "ai_director_release_asset") {
            if ($AssetRoot) {
                $RelativeSource = [string]$InputRow.asset_root_relative_path
                $SourcePath = Join-Path $AssetRoot (
                    $RelativeSource -replace "/", "\"
                )

                Require (
                    Test-Path -LiteralPath $SourcePath -PathType Leaf
                ) "Local bootstrap asset missing: $SourcePath"

                Write-Host ("BOOTSTRAP_LOCAL_COPY_BEGIN=" + $InputId)
                Copy-Item -LiteralPath $SourcePath -Destination $DownloadPath
            }
            elseif ([string]$InputRow.url) {
                Write-Host ("BOOTSTRAP_DOWNLOAD_BEGIN=" + $InputId)
                Invoke-Download `
                    -Url ([string]$InputRow.url) `
                    -Destination $DownloadPath
            }
            else {
                throw (
                    "AI Director runtime asset URL is required. " +
                    "Provide a valid public URL or -AssetRoot offline mirror. Input=" +
                    $InputId
                )
            }
        }
        else {
            Require (
                -not [string]::IsNullOrWhiteSpace([string]$InputRow.url)
            ) "Official input URL missing: $InputId"

            Write-Host ("BOOTSTRAP_DOWNLOAD_BEGIN=" + $InputId)

            Invoke-Download `
                -Url ([string]$InputRow.url) `
                -Destination $DownloadPath
        }

        [void](Assert-FileIdentity `
            -Path $DownloadPath `
            -ExpectedBytes ([int64]$InputRow.bytes) `
            -ExpectedSha256 ([string]$InputRow.sha256) `
            -Label $InputId)

        Write-Host ("BOOTSTRAP_INPUT_FETCH_VERIFIED=" + $InputId)

        if ($InputId -eq "python-3.11.9-embeddable-x64") {
            $PythonStage = Join-Path $Activate "_toolchain\Python\3.11.9"

            New-Item -ItemType Directory -Path $PythonStage -Force | Out-Null

            Expand-Archive `
                -LiteralPath $DownloadPath `
                -DestinationPath $PythonStage `
                -Force

            $PthPath = Join-Path $PythonStage "python311._pth"

            Write-Utf8NoBom `
                -Path $PthPath `
                -Text "python311.zip`r`n.`r`n"

            Assert-CleanPython `
                -PythonRoot $PythonStage `
                -ExpectedVersion $InputRow.postcheck.python_version

            Write-Host "BOOTSTRAP_PYTHON_STAGE=PASS"
            continue
        }

        if ($InputId -eq "node-24.18.0-win-x64") {
            $NodeExtract = Join-Path $StageRoot "node-extract"

            New-Item -ItemType Directory -Path $NodeExtract -Force | Out-Null

            Expand-Archive `
                -LiteralPath $DownloadPath `
                -DestinationPath $NodeExtract `
                -Force

            $NodeArchiveRoot = Join-Path $NodeExtract ([string]$InputRow.archive_root)

            Require (
                Test-Path -LiteralPath $NodeArchiveRoot -PathType Container
            ) "Node archive root missing after extraction."

            $NodeStageParent = Join-Path $Activate "_toolchain\Node"
            $NodeStage = Join-Path $NodeStageParent "24.18.0"

            New-Item -ItemType Directory -Path $NodeStageParent -Force | Out-Null

            Move-Item `
                -LiteralPath $NodeArchiveRoot `
                -Destination $NodeStage

            Assert-Node `
                -NodeRoot $NodeStage `
                -ExpectedNodeVersion $InputRow.postcheck.node_version `
                -ExpectedNpmVersion $InputRow.postcheck.npm_version `
                -ExpectedFileCount ([int]$InputRow.postcheck.file_count) `
                -ExpectedTreeBytes ([int64]$InputRow.postcheck.tree_bytes)

            Write-Host "BOOTSTRAP_NODE_STAGE=PASS"
            continue
        }

        $RelativeDestination = [string]$InputRow.destination_file
        $StageFile = Join-Path $Activate (
            $RelativeDestination -replace "/", "\"
        )

        $StageParent = Split-Path -Parent $StageFile

        if (-not (Test-Path -LiteralPath $StageParent)) {
            New-Item -ItemType Directory -Path $StageParent -Force | Out-Null
        }

        Move-Item `
            -LiteralPath $DownloadPath `
            -Destination $StageFile

        [void](Assert-FileIdentity `
            -Path $StageFile `
            -ExpectedBytes ([int64]$InputRow.bytes) `
            -ExpectedSha256 ([string]$InputRow.sha256) `
            -Label ($InputId + " staged"))
    }

    Write-Host "BOOTSTRAP_STAGING=PASS"

    foreach ($InputRow in $Missing) {
        $InputId = [string]$InputRow.id

        if ($InputId -eq "python-3.11.9-embeddable-x64") {
            $SourceDir = Join-Path $Activate "_toolchain\Python\3.11.9"
            $TargetDir = Join-Path $BuilderRoot "_toolchain\Python\3.11.9"

            Require (
                -not (Test-Path -LiteralPath $TargetDir)
            ) "Python target appeared during bootstrap."

            New-Item `
                -ItemType Directory `
                -Path (Split-Path -Parent $TargetDir) `
                -Force | Out-Null

            Move-Item -LiteralPath $SourceDir -Destination $TargetDir

            Assert-CleanPython `
                -PythonRoot $TargetDir `
                -ExpectedVersion $InputRow.postcheck.python_version

            Write-Host "BOOTSTRAP_ACTIVATED=python-3.11.9-embeddable-x64"
            continue
        }

        if ($InputId -eq "node-24.18.0-win-x64") {
            $SourceDir = Join-Path $Activate "_toolchain\Node\24.18.0"
            $TargetDir = Join-Path $BuilderRoot "_toolchain\Node\24.18.0"

            Require (
                -not (Test-Path -LiteralPath $TargetDir)
            ) "Node target appeared during bootstrap."

            New-Item `
                -ItemType Directory `
                -Path (Split-Path -Parent $TargetDir) `
                -Force | Out-Null

            Move-Item -LiteralPath $SourceDir -Destination $TargetDir

            Assert-Node `
                -NodeRoot $TargetDir `
                -ExpectedNodeVersion $InputRow.postcheck.node_version `
                -ExpectedNpmVersion $InputRow.postcheck.npm_version `
                -ExpectedFileCount ([int]$InputRow.postcheck.file_count) `
                -ExpectedTreeBytes ([int64]$InputRow.postcheck.tree_bytes)

            Write-Host "BOOTSTRAP_ACTIVATED=node-24.18.0-win-x64"
            continue
        }

        $RelativeDestination = [string]$InputRow.destination_file
        $SourceFile = Join-Path $Activate (
            $RelativeDestination -replace "/", "\"
        )
        $TargetFile = Join-Path $BuilderRoot (
            $RelativeDestination -replace "/", "\"
        )

        Require (
            -not (Test-Path -LiteralPath $TargetFile)
        ) "$InputId target appeared during bootstrap."

        $TargetParent = Split-Path -Parent $TargetFile

        if (-not (Test-Path -LiteralPath $TargetParent)) {
            New-Item -ItemType Directory -Path $TargetParent -Force | Out-Null
        }

        Move-Item -LiteralPath $SourceFile -Destination $TargetFile

        [void](Assert-FileIdentity `
            -Path $TargetFile `
            -ExpectedBytes ([int64]$InputRow.bytes) `
            -ExpectedSha256 ([string]$InputRow.sha256) `
            -Label ($InputId + " activated"))

        Write-Host ("BOOTSTRAP_ACTIVATED=" + $InputId)
    }

    foreach ($InputRow in $Inputs) {
        Require (
            Assert-InputPresent -InputRow $InputRow
        ) "Post-bootstrap input validation failed: $($InputRow.id)"
    }

    Write-Host "BOOTSTRAP_POST_ACTIVATION_VALIDATION=PASS"

    Remove-Item -LiteralPath $StageRoot -Recurse -Force
    Remove-Item -LiteralPath $LockPath -Recurse -Force

    Remove-EmptyCacheRoot -CacheRoot $CacheRoot

    Require (
        -not (Test-Path -LiteralPath $CacheRoot)
    ) "Bootstrap cache residue remains after successful completion."

    Write-Host "BOOTSTRAP_FINAL_CACHE=ABSENT"
    Write-Host "BOOTSTRAP_MUTATED=True"
    Write-Host "BOOTSTRAP_STATUS=PASS"
    exit 0
}
catch {
    Write-Host "BOOTSTRAP_STATUS=ERROR"
    Write-Host ("ERROR=" + $_.Exception.Message)
    Write-Host "BOOTSTRAP_EVIDENCE_PRESERVED=True"
    exit 1
}
