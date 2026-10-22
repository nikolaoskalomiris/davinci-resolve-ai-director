@echo off
setlocal
set "ROOT=%~dp0"
set "PY=%ROOT%_toolchain\Python\3.11.9\python.exe"
set "CONTROL=%ROOT%build\package\check_state.py"
if not exist "%PY%" (
  echo ERROR: Owned Python missing: %PY%
  exit /b 2
)
if not exist "%CONTROL%" (
  echo ERROR: Public source checker missing: %CONTROL%
  exit /b 2
)
"%PY%" -B "%CONTROL%" %*
exit /b %ERRORLEVEL%
