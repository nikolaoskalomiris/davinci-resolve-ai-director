@echo off
setlocal
set "ROOT=%~dp0"
set "PY=%ROOT%_toolchain\Python\3.11.9\python.exe"
set "CONTROL=%ROOT%build\package\version_control.py"
if not exist "%PY%" (
  echo VERSION_STATUS=ERROR
  echo ERROR=Owned Python missing: %PY%
  exit /b 2
)
if not exist "%CONTROL%" (
  echo VERSION_STATUS=ERROR
  echo ERROR=Version control missing: %CONTROL%
  exit /b 2
)
"%PY%" -B "%CONTROL%" %*
exit /b %ERRORLEVEL%
