@echo off
setlocal
set "ROOT=%~dp0"
set "PY=%ROOT%_toolchain\Python\3.11.9\python.exe"
set "NODE=%ROOT%_toolchain\Node\24.18.0\node.exe"
set "ELECTRON=%ROOT%_toolchain\Archives\electron-v36.3.2-win32-x64.zip"
set "NSIS=%ROOT%_toolchain\Archives\nsis-3.0.4.1.7z"
set "NSIS_RES=%ROOT%_toolchain\Archives\nsis-resources-3.4.1.7z"
set "SEVENZIP=%ROOT%_toolchain\Archives\7zip-win-x64.tar.gz"
set "RUNTIME_BASE=%ROOT%_inputs\Runtime-Bases\CUDA13-Native-Base-v4\RUNTIME-BASE.7z"
set "CUDA_CUDART_REDIST=%ROOT%_inputs\Shared-CUDA\CUDA13.3.1\Archives\cuda_cudart-windows-x86_64-13.3.29-archive.zip"
set "CUDA_CUBLAS_REDIST=%ROOT%_inputs\Shared-CUDA\CUDA13.3.1\Archives\libcublas-windows-x86_64-13.6.0.2-archive.zip"
set "BOOTSTRAP=%ROOT%bootstrap\BOOTSTRAP.ps1"
set "CONTROL=%ROOT%build\package\authoritative_build.py"
set "NEED_BOOTSTRAP=0"

if not exist "%PY%" set "NEED_BOOTSTRAP=1"
if not exist "%NODE%" set "NEED_BOOTSTRAP=1"
if not exist "%ELECTRON%" set "NEED_BOOTSTRAP=1"
if not exist "%NSIS%" set "NEED_BOOTSTRAP=1"
if not exist "%NSIS_RES%" set "NEED_BOOTSTRAP=1"
if not exist "%SEVENZIP%" set "NEED_BOOTSTRAP=1"
if not exist "%RUNTIME_BASE%" set "NEED_BOOTSTRAP=1"
if not exist "%CUDA_CUDART_REDIST%" set "NEED_BOOTSTRAP=1"
if not exist "%CUDA_CUBLAS_REDIST%" set "NEED_BOOTSTRAP=1"

if not "%NEED_BOOTSTRAP%"=="1" goto bootstrap_complete
if not exist "%BOOTSTRAP%" (
  echo BOOTSTRAP_STATUS=ERROR
  echo ERROR=Bootstrap control missing: %BOOTSTRAP%
  exit /b 2
)
set "AI_DIRECTOR_BOOTSTRAP_SCRIPT=%BOOTSTRAP%"
set "BOOTSTRAP_SHA="
for /f "usebackq delims=" %%H in (`powershell.exe -NoProfile -NonInteractive -ExecutionPolicy Bypass -Command "$h=(Get-FileHash -LiteralPath $env:AI_DIRECTOR_BOOTSTRAP_SCRIPT -Algorithm SHA256).Hash.ToUpperInvariant(); Write-Output $h"`) do set "BOOTSTRAP_SHA=%%H"
set "AI_DIRECTOR_BOOTSTRAP_SCRIPT="
if /I not "%BOOTSTRAP_SHA%"=="53AE186FD91B8D557662CB91F8CC94A3CD2F8A68D34F5DDD49E45960F044C226" (
  echo BOOTSTRAP_STATUS=ERROR
  echo ERROR=Bootstrap control SHA256 mismatch.
  exit /b 3
)
if defined AI_DIRECTOR_BOOTSTRAP_ASSET_ROOT (
  powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%BOOTSTRAP%" -BuilderRoot "%ROOT:~0,-1%" -AssetRoot "%AI_DIRECTOR_BOOTSTRAP_ASSET_ROOT%"
) else (
  powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%BOOTSTRAP%" -BuilderRoot "%ROOT:~0,-1%"
)
set "BOOTSTRAP_RC=%ERRORLEVEL%"
if not "%BOOTSTRAP_RC%"=="0" exit /b %BOOTSTRAP_RC%
:bootstrap_complete
if not exist "%PY%" (
  echo ERROR: Owned Python missing after bootstrap: %PY%
  exit /b 2
)
if not exist "%CONTROL%" (
  echo ERROR: Public build controller missing: %CONTROL%
  exit /b 2
)
"%PY%" "%CONTROL%" %*
exit /b %ERRORLEVEL%
