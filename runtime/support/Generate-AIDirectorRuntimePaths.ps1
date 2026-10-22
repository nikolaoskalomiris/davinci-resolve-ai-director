param(
    [Parameter(Mandatory=$true)][string]$LocalAppData
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version 2.0

$localRoot = [System.IO.Path]::GetFullPath($LocalAppData).TrimEnd('\')
$productRoot = Join-Path $localRoot 'AIDirector\DaVinciResolve'
$managedMcpRoot = Join-Path $localRoot 'davinci-resolve-mcp'
$mcpPythonRoot = Join-Path $productRoot 'Runtime\Python\MCP\3.11.9'
$mcpPython = Join-Path $mcpPythonRoot 'python.exe'
$nodeExe = Join-Path $productRoot 'Runtime\Node\24.18.0\node.exe'
$serverPy = Join-Path $managedMcpRoot 'src\server.py'
$advanced = Join-Path $managedMcpRoot 'bin\davinci-resolve-advanced-mcp.mjs'
$configPath = Join-Path $productRoot 'MCP\vfx_mcp.json'
$pthPath = Join-Path $mcpPythonRoot 'python311._pth'

$resolveScriptApi = 'C:\ProgramData\Blackmagic Design\DaVinci Resolve\Support\Developer\Scripting'
$resolveScriptModules = Join-Path $resolveScriptApi 'Modules'
$resolveScriptLib = 'C:\Program Files\Blackmagic Design\DaVinci Resolve\fusionscript.dll'

foreach ($required in @($productRoot,$managedMcpRoot,$mcpPython,$nodeExe,$serverPy,$advanced)) {
    if (-not (Test-Path -LiteralPath $required)) {
        throw ('Required runtime path is missing before path binding: ' + $required)
    }
}

$utf8NoBom = New-Object System.Text.UTF8Encoding($false)

$pthLines = @(
    'python311.zip',
    '.',
    'Lib\site-packages',
    'Lib\site-packages\win32',
    'Lib\site-packages\win32\lib',
    'Lib\site-packages\pythonwin',
    'Lib\site-packages\pywin32_system32',
    $managedMcpRoot,
    $resolveScriptModules
)
[System.IO.File]::WriteAllText(
    $pthPath,
    (($pthLines -join "`r`n") + "`r`n"),
    $utf8NoBom
)

$config = [ordered]@{
    mcpServers = [ordered]@{
        'davinci-resolve' = [ordered]@{
            command = $mcpPython
            args = @($serverPy)
            env = [ordered]@{
                RESOLVE_SCRIPT_API = $resolveScriptApi
                RESOLVE_SCRIPT_LIB = $resolveScriptLib
                PYTHONHOME = $mcpPythonRoot
                PYTHONPATH = $resolveScriptModules
            }
            timeout_ms = 120000
        }
        'davinci-resolve-full' = [ordered]@{
            command = $mcpPython
            args = @($serverPy, '--full')
            env = [ordered]@{
                RESOLVE_SCRIPT_API = $resolveScriptApi
                RESOLVE_SCRIPT_LIB = $resolveScriptLib
                PYTHONHOME = $mcpPythonRoot
                PYTHONPATH = $resolveScriptModules
            }
            timeout_ms = 120000
        }
        'davinci-resolve-advanced' = [ordered]@{
            command = $nodeExe
            args = @($advanced)
            env = [ordered]@{
                AAF_PROBE_PYTHON = $mcpPython
            }
            timeout_ms = 120000
        }
    }
}

$json = $config | ConvertTo-Json -Depth 12
[System.IO.File]::WriteAllText($configPath, ($json + "`r`n"), $utf8NoBom)

$parsed = Get-Content -LiteralPath $configPath -Raw | ConvertFrom-Json
if ($null -eq $parsed.mcpServers.'davinci-resolve') {
    throw 'Generated MCP config did not parse with the compound server.'
}
if ((Get-Content -LiteralPath $pthPath -Raw).IndexOf($managedMcpRoot, [System.StringComparison]::OrdinalIgnoreCase) -lt 0) {
    throw 'Generated python311._pth does not contain the managed MCP root.'
}

Write-Host 'PATH_BINDING_STATUS=PASS'
Write-Host ('MCP_CONFIG=' + $configPath)
Write-Host ('PYTHON_PTH=' + $pthPath)
