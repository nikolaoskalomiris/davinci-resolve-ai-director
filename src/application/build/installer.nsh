# DaVinci Resolve AI Director current-user installer contract.
# electron-builder 26.15.x checks customInstallmode (lowercase m); later
# releases use the documented customInstallMode spelling. Define both hooks
# with one implementation so the contract stays explicit and version-safe.

!macro AI_DIRECTOR_FORCE_CURRENT_USER
    StrCpy $isForceCurrentInstall "1"
!macroend

!macro customInstallMode
    !insertmacro AI_DIRECTOR_FORCE_CURRENT_USER
!macroend

!macro customInstallmode
    !insertmacro AI_DIRECTOR_FORCE_CURRENT_USER
!macroend
