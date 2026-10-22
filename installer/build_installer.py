from __future__ import annotations

import base64
import datetime
import importlib.util
import hashlib
import json
import mmap
import os
import re
import shutil
import subprocess
import struct
import traceback
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path

# The product-owned embedded Python uses python311._pth isolation, so sibling
# modules are not guaranteed to be present on sys.path. Load this builder-control
# module by explicit file path instead of relying on normal import discovery.
_RUNTIME_BASE_CONTROL_PATH = Path(__file__).resolve().parents[1] / "runtime" / "runtime_base_control.py"
_RUNTIME_BASE_CONTROL_SPEC = importlib.util.spec_from_file_location(
    "runtime_base_control",
    _RUNTIME_BASE_CONTROL_PATH,
)
if _RUNTIME_BASE_CONTROL_SPEC is None or _RUNTIME_BASE_CONTROL_SPEC.loader is None:
    raise RuntimeError(f"Unable to load runtime_base_control from {_RUNTIME_BASE_CONTROL_PATH}")
runtime_base_control = importlib.util.module_from_spec(_RUNTIME_BASE_CONTROL_SPEC)
_RUNTIME_BASE_CONTROL_SPEC.loader.exec_module(runtime_base_control)

PRODUCT_NAME = "DaVinci Resolve AI Director"
PRODUCT_PUBLISHER = "DaVinci Resolve AI Director"
PRODUCT_COPYRIGHT = "Copyright 2026 DaVinci Resolve AI Director"
BASE_VERSION = "0.3.6"

EXPECTED = {
    "app_report": "37CB5E94934F80CF6938DB6829E770D15D9F2293A93E74EFD5A946AA757F2FF7",
    "runtime_report": "42233023B342E6AE0411DE327A648D597CE413689DB6F3E52A68B86765D34CE2",
    "runtime_release_manifest": "130903A50DC38B9BDE0254C71F583967700ECF6456C7603ED782CA18C193DDB2",
    "app_exe": "18277D8E4D517044F58E2D54E1998246C2DBF2764585AE4CF1E8C6B7CEB205A5",
    "app_asar": "445C143AA4A6F89BEB49DF910BF0459BE3105811D2055C56820D264EBB19E596",
    "observer": "DAA80220B3F8A730A7EE3946BD3EF51E1B161C0195778B9014FCB360F8D895F6",
    "package_json": "20684935F33E0805DF7B42485699D75606B0AEE6CF9CC7C20FB1495E334FB773",
    "package_lock": "5A4FE65AC1F4133D3317ABDF90584E250C6118CAD7B0F8B4533109653E0DBC98",
    "source_mcp_config": "A37BB81692E6E9CE6CBF884975C354AC32724BD7FA04B8AA118B539453D78CDF",
    "source_mcp_pth": "9CD4F3D6F66C1E3FA1EF0A20F245358FF45F7B209F35F1A0E4CE1597D1A8612C",
    "source_backend_host": "C0C26A6029229CD1D2C4F12B8382960D1271DC62152C5582E9457BD28EEDFEF1",
    "accepted_runtime_archive": "40EE0AA67022B24FF0F7A7BE6E4DFF34A1B8BF2D269AE1FACE79C6BC9170F353",
    "shipping_runtime": "20BE244C03118FE762ECFDE041CAB7516AFA08B54632C51DE7AB9A869F5B88F4",
    "accepted_installer_036": "201C5EA043B80EA14921FCC52ED8647C6AB3DCC6A2B77D0E29B9A4FD010FDE27",
    "owned_electron_exe": "1048609FFA3A543291F71AD6CBD976858821F7A13FB50FF14F8DC2DD8A99C128",
}
EXPECTED_BUILDER_VERSION = "26.15.3"
EXPECTED_NODE_VERSION = "v24.18.0"
EXPECTED_ELECTRON_VERSION = "36.3.2"
EXPECTED_ELECTRON_ARCHIVE_SHA256 = "5475DC725D50C9CEE12C0D56E1FD093C3BAD75E9DFAFD9753FDDC3A085532A37"
ELECTRON_ARCHIVE_NAME = "electron-v36.3.2-win32-x64.zip"
ELECTRON_ARCHIVE_URL = "https://github.com/electron/electron/releases/download/v36.3.2/electron-v36.3.2-win32-x64.zip"

TEXT_EXTS = {
    ".json", ".txt", ".md", ".py", ".js", ".mjs", ".cjs", ".ps1",
    ".cmd", ".bat", ".xml", ".ini", ".cfg", ".toml", ".yaml", ".yml",
    ".nsh", ".nsi",
}

def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest().upper()

def assert_hash(label: str, path: Path, expected: str) -> str:
    if not path.is_file():
        raise RuntimeError(f"{label} missing: {path}")
    actual = sha256(path)
    if actual != expected:
        raise RuntimeError(f"{label} SHA mismatch. Expected={expected} Actual={actual} Path={path}")
    print(f"{label}: OK {actual}", flush=True)
    return actual

def run(args, *, cwd=None, env=None, log=None, ok_codes=(0,)) -> subprocess.CompletedProcess:
    cp = subprocess.run(
        [str(x) for x in args],
        cwd=str(cwd) if cwd else None,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        creationflags=(subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0),
    )
    if log:
        Path(log).parent.mkdir(parents=True, exist_ok=True)
        Path(log).write_text(cp.stdout, encoding="utf-8", errors="replace")
    if cp.returncode not in ok_codes:
        raise RuntimeError(
            f"Command failed exit={cp.returncode}: {' '.join(str(x) for x in args)}"
            + (f"\nLOG={log}" if log else "")
            + f"\n{cp.stdout[-6000:]}"
        )
    return cp















def exact_stream_offset(container: Path, payload: Path) -> int:
    payload_size = payload.stat().st_size
    prefix_len = min(1024 * 1024, payload_size)
    with payload.open("rb") as pf:
        prefix = pf.read(prefix_len)
    with container.open("rb") as cf:
        mm = mmap.mmap(cf.fileno(), 0, access=mmap.ACCESS_READ)
        try:
            start = 0
            while True:
                pos = mm.find(prefix, start)
                if pos < 0:
                    return -1
                if pos + payload_size <= len(mm):
                    ok = True
                    with payload.open("rb") as pf:
                        off = pos
                        while True:
                            block = pf.read(8 * 1024 * 1024)
                            if not block:
                                break
                            if mm[off:off + len(block)] != block:
                                ok = False
                                break
                            off += len(block)
                    if ok:
                        return pos
                start = pos + 1
        finally:
            mm.close()





def make_nsis_include(
    runtime_archive: Path,
    generator: Path,
    *,
    resolve_integration_setup: Path | None = None,
    resolve_integration_version: str | None = None,
    branding=None,
    branding_build_dir: Path | None = None,
    runtime_stack_archive: Path | None = None,
    runtime_stack_marker: str | None = None,
    runtime_stack_required_targets: list[str] | None = None,
    runtime_stack_partial_roots: list[str] | None = None,
) -> str:
    r = str(runtime_archive)
    g = str(generator)

    branding_schema = None
    installer_ui = {}
    branding_declarations = ""

    if branding is not None:
        branding_manifest = branding.get("manifest") or {}
        branding_schema = branding_manifest.get("schema_version")

        if branding_schema in (2, 3):
            if branding_build_dir is None:
                raise RuntimeError(
                    "Brand-v2/v3 NSIS generation requires the staged branding build directory."
                )

            installer_ui = branding_manifest.get("installer_ui") or {}
            header = installer_ui.get("header") or {}

            header_bitmap = (
                branding_build_dir
                / Path(str(header.get("bitmap") or "")).name
            )
            header_ui_resource = (
                branding_build_dir
                / Path(str(header.get("ui_resource") or "")).name
            )

            if not header_bitmap.is_file():
                raise RuntimeError(
                    f"Brand-v2/v3 staged header bitmap missing: {header_bitmap}"
                )

            if not header_ui_resource.is_file():
                raise RuntimeError(
                    f"Brand-v2/v3 staged header UI resource missing: {header_ui_resource}"
                )

            header_bitmap_nsis = _nsis_escape(str(header_bitmap))
            header_ui_nsis = _nsis_escape(str(header_ui_resource))
            header_title = _nsis_escape(str(header.get("title") or ""))
            header_font_size = int(header.get("title_font_size_pt"))
            header_font_weight = int(header.get("title_font_weight"))
            header_text_color = str(header.get("text_color_rgb") or "")

            branding_declarations = f"""
!ifndef BUILD_UNINSTALLER
!define MUI_HEADERIMAGE
!define MUI_UI_HEADERIMAGE "{header_ui_nsis}"
!define MUI_HEADERIMAGE_BITMAP "{header_bitmap_nsis}"
!define MUI_HEADERIMAGE_BITMAP_STRETCH "FitControl"
!define MUI_HEADER_TRANSPARENT_TEXT
!define MUI_TEXTCOLOR "{header_text_color}"
!define MUI_CUSTOMFUNCTION_GUIINIT aidBrandingHeaderGuiInit
!include "WinMessages.nsh"

Function aidBrandingHeaderGuiInit
    GetDlgItem $R0 $HWNDPARENT 1037
    CreateFont $R1 "$(^Font)" "{header_font_size}" "{header_font_weight}"
    SendMessage $R0 ${{WM_SETFONT}} $R1 0
    SendMessage $R0 ${{WM_SETTEXT}} 0 "STR:{header_title}"
FunctionEnd
!endif
"""
    integration_enabled = resolve_integration_setup is not None or resolve_integration_version is not None
    if integration_enabled and (resolve_integration_setup is None or not resolve_integration_version):
        raise RuntimeError("Optional Resolve Integration embedding requires both exact child Setup and target version.")
    if resolve_integration_setup is not None and not resolve_integration_setup.is_file():
        raise RuntimeError(f"Optional Resolve Integration child Setup missing: {resolve_integration_setup}")

    integration_declarations = ""
    integration_init = ""
    integration_install = ""
    if integration_enabled:
        child = _nsis_escape(str(resolve_integration_setup))
        version = str(resolve_integration_version)

        if branding_schema in (2, 3):
            page = installer_ui.get("resolve_integration_page") or {}

            page_heading = _nsis_escape(str(page.get("heading") or ""))
            page_checkbox = _nsis_escape(str(page.get("checkbox") or ""))
            page_info_heading = _nsis_escape(str(page.get("information_heading") or ""))
            page_info_text = _nsis_escape(str(page.get("information_text") or ""))

            integration_declarations = f"""
!ifndef BUILD_UNINSTALLER
!include "nsDialogs.nsh"
Var /GLOBAL aidIncludeResolveIntegration
Var /GLOBAL aidIntegrationCheckbox
Var /GLOBAL aidCreateDesktopShortcut
Var /GLOBAL aidDesktopShortcutCheckbox

!macro customPageAfterChangeDir
    Page custom aidResolveIntegrationPageCreate aidResolveIntegrationPageLeave
!macroend

Function aidResolveIntegrationPageCreate
    nsDialogs::Create 1018
    Pop $R0
    StrCmp $R0 "error" 0 +2
        Abort

    ${{NSD_CreateLabel}} 0 0u 100% 12u "{page_heading}"
    Pop $R1
    CreateFont $R4 "$(^Font)" "$(^FontSize)" "700"
    SendMessage $R1 ${{WM_SETFONT}} $R4 0

    ${{NSD_CreateCheckbox}} 0 18u 100% 12u "{page_checkbox}"
    Pop $aidIntegrationCheckbox
    ${{NSD_SetState}} $aidIntegrationCheckbox $aidIncludeResolveIntegration

    ${{NSD_CreateCheckbox}} 0 36u 100% 12u "Create a desktop shortcut"
    Pop $aidDesktopShortcutCheckbox
    ${{NSD_SetState}} $aidDesktopShortcutCheckbox $aidCreateDesktopShortcut

    ${{NSD_CreateLabel}} 0 58u 100% 12u "{page_info_heading}"
    Pop $R2
    SendMessage $R2 ${{WM_SETFONT}} $R4 0

    ${{NSD_CreateLabel}} 0 74u 100% 30u "{page_info_text}"
    Pop $R3

    nsDialogs::Show
FunctionEnd

Function aidResolveIntegrationPageLeave
    ${{NSD_GetState}} $aidIntegrationCheckbox $aidIncludeResolveIntegration
    ${{NSD_GetState}} $aidDesktopShortcutCheckbox $aidCreateDesktopShortcut
FunctionEnd
!endif
"""
        else:
            integration_declarations = f"""
!ifndef BUILD_UNINSTALLER
!include "nsDialogs.nsh"
Var /GLOBAL aidIncludeResolveIntegration
Var /GLOBAL aidIntegrationCheckbox
Var /GLOBAL aidCreateDesktopShortcut
Var /GLOBAL aidDesktopShortcutCheckbox

!macro customPageAfterChangeDir
    Page custom aidResolveIntegrationPageCreate aidResolveIntegrationPageLeave
!macroend

Function aidResolveIntegrationPageCreate
    nsDialogs::Create 1018
    Pop $R0
    StrCmp $R0 "error" 0 +2
        Abort

    ${{NSD_CreateLabel}} 0 0u 100% 12u "Installation options"
    Pop $R1

    ${{NSD_CreateLabel}} 0 14u 100% 20u "Choose whether to add AI Director to DaVinci Resolve."
    Pop $R2

    ${{NSD_CreateCheckbox}} 0 40u 100% 12u "Include DaVinci Resolve Workflow Integration"
    Pop $aidIntegrationCheckbox
    ${{NSD_SetState}} $aidIntegrationCheckbox $aidIncludeResolveIntegration

    ${{NSD_CreateCheckbox}} 0 56u 100% 12u "Create a desktop shortcut"
    Pop $aidDesktopShortcutCheckbox
    ${{NSD_SetState}} $aidDesktopShortcutCheckbox $aidCreateDesktopShortcut

    ${{NSD_CreateLabel}} 0 78u 100% 30u "Adds AI Director to DaVinci Resolve's Workflow Integration menu. You can install it separately later."
    Pop $R3
    nsDialogs::Show
FunctionEnd

Function aidResolveIntegrationPageLeave
    ${{NSD_GetState}} $aidIntegrationCheckbox $aidIncludeResolveIntegration
    ${{NSD_GetState}} $aidDesktopShortcutCheckbox $aidCreateDesktopShortcut
FunctionEnd
!endif
"""
        integration_init = '    StrCpy $aidIncludeResolveIntegration ${BST_CHECKED}\n    StrCpy $aidCreateDesktopShortcut ${BST_CHECKED}\n'
        integration_install = rf'''
    DetailPrint "Stage 4 of 5 - Applying DaVinci Resolve integration choice..."
    StrCmp $aidIncludeResolveIntegration "${{BST_CHECKED}}" aid_resolve_integration_install aid_resolve_integration_skip

aid_resolve_integration_install:
    DetailPrint "Installing optional DaVinci Resolve Workflow Integration..."
    SetOutPath "$PLUGINSDIR"
    !ifdef COMPRESS
        SetCompress off
    !endif
    File /oname=ai-director-resolve-integration-setup.exe "{child}"
    !ifdef COMPRESS
        SetCompress "${{COMPRESS}}"
    !endif

    ClearErrors
    ExecShellWait "runas" "$PLUGINSDIR\ai-director-resolve-integration-setup.exe" "/S"
    IfErrors aid_resolve_integration_failed 0

    SetShellVarContext all
    SetRegView 64
    IfFileExists "$LOCALAPPDATA\Blackmagic Design\DaVinci Resolve\Support\Workflow Integration Plugins\com.aidirector.davinciresolve\main.js" 0 aid_resolve_integration_failed_all_context
    IfFileExists "$LOCALAPPDATA\Blackmagic Design\DaVinci Resolve\Support\Workflow Integration Plugins\com.aidirector.davinciresolve\manifest.xml" 0 aid_resolve_integration_failed_all_context
    IfFileExists "$LOCALAPPDATA\Blackmagic Design\DaVinci Resolve\Support\Workflow Integration Plugins\com.aidirector.davinciresolve\{RESOLVE_LAUNCHER_UNINSTALLER_NAME}" 0 aid_resolve_integration_failed_all_context
    ReadRegStr $R3 HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\DaVinciResolveAIDirectorResolveIntegration" "DisplayVersion"
    StrCmp $R3 "{version}" aid_resolve_integration_success aid_resolve_integration_failed_all_context

aid_resolve_integration_success:
    SetShellVarContext current
    SetRegView lastused
    Delete "$PLUGINSDIR\ai-director-resolve-integration-setup.exe"
    DetailPrint "DaVinci Resolve Workflow Integration installed successfully."
    Goto aid_resolve_integration_done

aid_resolve_integration_failed_all_context:
    SetShellVarContext current
    SetRegView lastused

aid_resolve_integration_failed:
    Delete "$PLUGINSDIR\ai-director-resolve-integration-setup.exe"
    MessageBox MB_OK|MB_ICONEXCLAMATION "AI Director was installed, but the optional DaVinci Resolve Workflow Integration was not installed. You can run the separate AI Director Integration Setup later."
    Goto aid_resolve_integration_done

aid_resolve_integration_skip:
    DetailPrint "DaVinci Resolve Workflow Integration not selected; installing standalone AI Director only."

aid_resolve_integration_done:
'''

        desktop_shortcut_install = r'''
    DetailPrint "Stage 5 of 5 - Finalizing shortcuts and installation..."
    SetShellVarContext current
    StrCmp $aidCreateDesktopShortcut "${BST_CHECKED}" aid_desktop_shortcut_create aid_desktop_shortcut_remove

aid_desktop_shortcut_create:
    ClearErrors
    SetOutPath "$INSTDIR"
    CreateShortCut "$DESKTOP\DaVinci Resolve AI Director.lnk" "$INSTDIR\DaVinci Resolve AI Director.exe" "" "$INSTDIR\DaVinci Resolve AI Director.exe" 0
    IfErrors aid_desktop_shortcut_failed 0
    DetailPrint "Desktop shortcut created."
    Goto aid_desktop_shortcut_done

aid_desktop_shortcut_failed:
    DetailPrint "Desktop shortcut could not be created."
    MessageBox MB_OK|MB_ICONEXCLAMATION "AI Director was installed, but the desktop shortcut could not be created."
    Goto aid_desktop_shortcut_done

aid_desktop_shortcut_remove:
    Delete "$DESKTOP\DaVinci Resolve AI Director.lnk"
    DetailPrint "Desktop shortcut not selected."

aid_desktop_shortcut_done:
'''


    runtime_stack_install = ""
    runtime_stack_expected = runtime_stack_archive is not None
    if runtime_stack_expected:
        if runtime_stack_marker is None:
            raise RuntimeError("Runtime-stack embedding requires install marker.")
        if runtime_stack_required_targets is None or not runtime_stack_required_targets:
            raise RuntimeError("Runtime-stack embedding requires required install targets.")
        if runtime_stack_partial_roots is None or not runtime_stack_partial_roots:
            raise RuntimeError("Runtime-stack embedding requires partial-root guards.")
        if not runtime_stack_archive.is_file():
            raise RuntimeError(f"Runtime-stack archive missing: {runtime_stack_archive}")

        marker_rel = safe_relative_path(
            runtime_stack_marker,
            label="NSIS runtime-stack marker",
        ).as_posix()
        required_rels = [
            safe_relative_path(x, label="NSIS runtime-stack required target").as_posix()
            for x in runtime_stack_required_targets
        ]
        partial_rels = [
            safe_relative_path(x, label="NSIS runtime-stack partial root").as_posix()
            for x in runtime_stack_partial_roots
        ]

        def _nsis_rel(value: str) -> str:
            return _nsis_escape(value.replace("/", "\\"))

        marker_nsis = _nsis_rel(marker_rel)
        archive_nsis = _nsis_escape(str(runtime_stack_archive))
        marker_parent_rel = str(Path(marker_rel).parent).replace("\\", "/")
        cleanup_rels = list(dict.fromkeys(partial_rels + [marker_parent_rel]))
        cleanup_commands = "\n".join(
            f'    RMDir /r "$LocalAppData\\{_nsis_rel(rel)}"'
            for rel in cleanup_rels
        )

        present_checks = "\n".join(
            f'    IfFileExists "$LocalAppData\\{_nsis_rel(rel)}" 0 aid_runtime_stack_inconsistent'
            for rel in required_rels
        )
        absent_partial_checks = "\n".join(
            f'    IfFileExists "$LocalAppData\\{_nsis_rel(rel)}\\*.*" aid_runtime_stack_inconsistent 0'
            for rel in partial_rels
        )
        extracted_checks = "\n".join(
            f'    IfFileExists "$PLUGINSDIR\\aid-runtime-stack-out\\{_nsis_rel(rel)}" 0 aid_runtime_stack_extract_failed'
            for rel in [marker_rel] + required_rels
        )
        installed_checks = "\n".join(
            f'    IfFileExists "$LocalAppData\\{_nsis_rel(rel)}" 0 aid_runtime_stack_copy_failed'
            for rel in [marker_rel] + required_rels
        )

        runtime_stack_install = rf'''
    DetailPrint "Evaluating AI Director versioned runtime stack..."
    IfFileExists "$LocalAppData\{marker_nsis}" aid_runtime_stack_present aid_runtime_stack_absent

aid_runtime_stack_present:
{present_checks}
    DetailPrint "Existing complete AI Director runtime stack preserved."
    Goto aid_runtime_stack_done

aid_runtime_stack_absent:
{absent_partial_checks}
    DetailPrint "Installing AI Director versioned runtime stack..."
    SetOutPath "$PLUGINSDIR"
    !ifdef COMPRESS
        SetCompress off
    !endif
    File /oname=ai-director-runtime-stack.7z "{archive_nsis}"
    !ifdef COMPRESS
        SetCompress "${{COMPRESS}}"
    !endif

    CreateDirectory "$PLUGINSDIR\aid-runtime-stack-out"
    SetOutPath "$PLUGINSDIR\aid-runtime-stack-out"
    Nsis7z::Extract "$PLUGINSDIR\ai-director-runtime-stack.7z"
    Pop $R4
    SetOutPath $R4

{extracted_checks}

    CreateDirectory "$LocalAppData\AIDirector"

    ClearErrors
    CopyFiles /SILENT "$PLUGINSDIR\aid-runtime-stack-out\AIDirector\DaVinciResolve" "$LocalAppData\AIDirector"
    IfErrors aid_runtime_stack_copy_failed 0

    ClearErrors
    CopyFiles /SILENT "$PLUGINSDIR\aid-runtime-stack-out\AIDirector\Common" "$LocalAppData\AIDirector"
    IfErrors aid_runtime_stack_copy_failed 0

{installed_checks}

    RMDir /r "$PLUGINSDIR\aid-runtime-stack-out"
    Delete "$PLUGINSDIR\ai-director-runtime-stack.7z"
    DetailPrint "AI Director versioned runtime stack installed successfully."
    Goto aid_runtime_stack_done

aid_runtime_stack_extract_failed:
    RMDir /r "$PLUGINSDIR\aid-runtime-stack-out"
    Delete "$PLUGINSDIR\ai-director-runtime-stack.7z"
    MessageBox MB_OK|MB_ICONSTOP "AI Director runtime-stack extraction failed."
    Abort

aid_runtime_stack_copy_failed:
    ; All cleanup roots were proven absent before this install attempt.
    ; Remove only this attempt's additive stack bytes so a retry is recoverable.
{cleanup_commands}
    RMDir /r "$PLUGINSDIR\aid-runtime-stack-out"
    Delete "$PLUGINSDIR\ai-director-runtime-stack.7z"
    MessageBox MB_OK|MB_ICONSTOP "AI Director runtime-stack provisioning failed. Partial stack bytes from this attempt were removed."
    Abort

aid_runtime_stack_inconsistent:
    MessageBox MB_OK|MB_ICONSTOP "An incomplete AI Director versioned runtime stack already exists. Setup will not overwrite or merge it. Repair/remove that stack before reinstalling."
    Abort

aid_runtime_stack_done:
'''

    return f'''# DaVinci Resolve AI Director current-user installer contract.
# Permanent builder contract.
# Runtime is a portable initial seed; per-user path-bound files are generated at install time.
#
# Upgrade lifecycle rule:
# electron-builder removes the previously installed version before customInstall.
# Therefore runtime state MUST be re-evaluated inside customInstall. customInit
# performs an early consistency gate only; its seed flags are not trusted later.
{branding_declarations}
!macro AI_DIRECTOR_FORCE_CURRENT_USER
    StrCpy $isForceCurrentInstall "1"
!macroend

!macro customInstallMode
    !insertmacro AI_DIRECTOR_FORCE_CURRENT_USER
!macroend
{integration_declarations}
!ifndef BUILD_UNINSTALLER
ShowInstDetails show

Var /GLOBAL aidSeedProductRuntime
Var /GLOBAL aidSeedCommonRuntime
Var /GLOBAL aidSeedManagedMcp

Function aidEvaluateRuntimeSeedState
    StrCpy $aidSeedProductRuntime "0"
    StrCpy $aidSeedCommonRuntime "0"
    StrCpy $aidSeedManagedMcp "0"

    IfFileExists "$LocalAppData\\AIDirector\\DaVinciResolve\\*.*" aid_eval_product_exists aid_eval_product_absent

aid_eval_product_absent:
    StrCpy $aidSeedProductRuntime "1"
    Goto aid_eval_product_done

aid_eval_product_exists:
    IfFileExists "$LocalAppData\\AIDirector\\DaVinciResolve\\Manifests\\RELEASE-PAYLOAD-MANIFEST-identity-v1.json" 0 aid_eval_runtime_inconsistent
    IfFileExists "$LocalAppData\\AIDirector\\DaVinciResolve\\Runtime\\Node\\24.18.0\\node.exe" 0 aid_eval_runtime_inconsistent
    IfFileExists "$LocalAppData\\AIDirector\\DaVinciResolve\\Backend\\ResolveVFXHost.py" 0 aid_eval_runtime_inconsistent
    IfFileExists "$LocalAppData\\AIDirector\\DaVinciResolve\\MCP\\vfx_mcp.json" 0 aid_eval_runtime_inconsistent
    IfFileExists "$LocalAppData\\AIDirector\\DaVinciResolve\\Runtime\\Python\\MCP\\3.11.9\\python311._pth" 0 aid_eval_runtime_inconsistent
    Goto aid_eval_product_done

aid_eval_runtime_inconsistent:
    MessageBox MB_OK|MB_ICONSTOP "An incomplete DaVinci Resolve AI Director runtime already exists. Setup will not overwrite or merge it. Repair/remove that runtime before reinstalling."
    Abort

aid_eval_product_done:
    IfFileExists "$LocalAppData\\AIDirector\\Common\\*.*" aid_eval_common_done aid_eval_common_absent

aid_eval_common_absent:
    StrCpy $aidSeedCommonRuntime "1"

aid_eval_common_done:
    IfFileExists "$LocalAppData\\davinci-resolve-mcp\\*.*" aid_eval_mcp_exists aid_eval_mcp_absent

aid_eval_mcp_absent:
    StrCpy $aidSeedManagedMcp "1"
    Goto aid_eval_mcp_done

aid_eval_mcp_exists:
    IfFileExists "$LocalAppData\\davinci-resolve-mcp\\package.json" 0 aid_eval_mcp_inconsistent
    IfFileExists "$LocalAppData\\davinci-resolve-mcp\\src\\server.py" 0 aid_eval_mcp_inconsistent
    IfFileExists "$LocalAppData\\davinci-resolve-mcp\\bin\\davinci-resolve-advanced-mcp.mjs" 0 aid_eval_mcp_inconsistent
    Goto aid_eval_mcp_done

aid_eval_mcp_inconsistent:
    MessageBox MB_OK|MB_ICONSTOP "An incomplete managed DaVinci Resolve MCP runtime already exists. Setup will not overwrite or merge it. Repair/remove that runtime before reinstalling."
    Abort

aid_eval_mcp_done:
FunctionEnd

!macro customInit
    # Early consistency gate. electron-builder may subsequently run the
    # previous version's uninstaller, so these flags are deliberately
    # re-evaluated again in customInstall.
    Call aidEvaluateRuntimeSeedState
{integration_init}!macroend

!macro customInstall
    SetDetailsPrint both
    DetailPrint "Stage 1 of 5 - Checking installed AI Director state..."
    DetailPrint "Re-evaluating DaVinci Resolve AI Director runtime after previous-version removal..."
    Call aidEvaluateRuntimeSeedState

    DetailPrint "Stage 2 of 5 - Preparing AI Director core runtime..."
    StrCmp $aidSeedProductRuntime "1" aid_seed_required 0
    StrCmp $aidSeedCommonRuntime "1" aid_seed_required 0
    StrCmp $aidSeedManagedMcp "1" aid_seed_required aid_seed_not_required

aid_seed_required:
    SetOutPath "$PLUGINSDIR"

    !ifdef COMPRESS
        SetCompress off
    !endif
    File /oname=ai-director-runtime.7z "{r}"
    !ifdef COMPRESS
        SetCompress "${{COMPRESS}}"
    !endif

    File /oname=Generate-AIDirectorRuntimePaths.ps1 "{g}"

    CreateDirectory "$PLUGINSDIR\\aid-runtime-out"
    SetOutPath "$PLUGINSDIR\\aid-runtime-out"
    Nsis7z::Extract "$PLUGINSDIR\\ai-director-runtime.7z"
    Pop $R0
    SetOutPath $R0

    IfFileExists "$PLUGINSDIR\\aid-runtime-out\\AIDirector\\DaVinciResolve\\Runtime\\Node\\24.18.0\\node.exe" 0 aid_extract_failed
    IfFileExists "$PLUGINSDIR\\aid-runtime-out\\AIDirector\\Common\\*.*" 0 aid_extract_failed
    IfFileExists "$PLUGINSDIR\\aid-runtime-out\\davinci-resolve-mcp\\package.json" 0 aid_extract_failed
    Goto aid_extract_ok

aid_extract_failed:
    MessageBox MB_OK|MB_ICONSTOP "DaVinci Resolve AI Director embedded runtime extraction failed."
    Abort

aid_extract_ok:
    StrCmp $aidSeedProductRuntime "1" 0 aid_skip_product_copy
    DetailPrint "Provisioning DaVinci Resolve AI Director product runtime..."
    CreateDirectory "$LocalAppData\\AIDirector"
    ClearErrors
    CopyFiles /SILENT "$PLUGINSDIR\\aid-runtime-out\\AIDirector\\DaVinciResolve" "$LocalAppData\\AIDirector"
    IfErrors aid_copy_failed 0

aid_skip_product_copy:
    StrCmp $aidSeedCommonRuntime "1" 0 aid_skip_common_copy
    DetailPrint "Provisioning shared AI Director runtime..."
    CreateDirectory "$LocalAppData\\AIDirector"
    ClearErrors
    CopyFiles /SILENT "$PLUGINSDIR\\aid-runtime-out\\AIDirector\\Common" "$LocalAppData\\AIDirector"
    IfErrors aid_copy_failed 0

aid_skip_common_copy:
    StrCmp $aidSeedManagedMcp "1" 0 aid_skip_mcp_copy
    DetailPrint "Provisioning managed DaVinci Resolve MCP runtime..."
    ClearErrors
    CopyFiles /SILENT "$PLUGINSDIR\\aid-runtime-out\\davinci-resolve-mcp" "$LocalAppData"
    IfErrors aid_copy_failed 0

aid_skip_mcp_copy:
    DetailPrint "Binding per-user AI Director runtime paths..."
    nsExec::ExecToStack '"$SYSDIR\\WindowsPowerShell\\v1.0\\powershell.exe" -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "$PLUGINSDIR\\Generate-AIDirectorRuntimePaths.ps1" -LocalAppData "$LocalAppData"'
    Pop $R1
    Pop $R2
    StrCmp $R1 "0" aid_validate_installed_runtime 0
    DetailPrint "$R2"
    Goto aid_copy_failed

aid_validate_installed_runtime:
    IfFileExists "$LocalAppData\\AIDirector\\DaVinciResolve\\Runtime\\Node\\24.18.0\\node.exe" 0 aid_copy_failed
    IfFileExists "$LocalAppData\\AIDirector\\DaVinciResolve\\Backend\\ResolveVFXHost.py" 0 aid_copy_failed
    IfFileExists "$LocalAppData\\AIDirector\\DaVinciResolve\\MCP\\vfx_mcp.json" 0 aid_copy_failed
    IfFileExists "$LocalAppData\\AIDirector\\DaVinciResolve\\Runtime\\Python\\MCP\\3.11.9\\python311._pth" 0 aid_copy_failed
    IfFileExists "$LocalAppData\\davinci-resolve-mcp\\package.json" 0 aid_copy_failed
    Goto aid_seed_cleanup

aid_copy_failed:
    MessageBox MB_OK|MB_ICONSTOP "DaVinci Resolve AI Director runtime provisioning failed."
    Abort

aid_seed_cleanup:
    RMDir /r "$PLUGINSDIR\\aid-runtime-out"
    Delete "$PLUGINSDIR\\ai-director-runtime.7z"
    Delete "$PLUGINSDIR\\Generate-AIDirectorRuntimePaths.ps1"

aid_seed_not_required:
    DetailPrint "Existing complete DaVinci Resolve AI Director runtime preserved."
    DetailPrint "Stage 3 of 5 - Preparing AI Director acceleration runtime..."
{runtime_stack_install}    SetOutPath "$INSTDIR"
{integration_install}{desktop_shortcut_install}!macroend

!endif # !BUILD_UNINSTALLER

!macro customUnInstall
    ${{if}} ${{isUpdated}}
        DetailPrint "Preserving DaVinci Resolve AI Director product runtime during update..."
    ${{else}}
        DetailPrint "Removing DaVinci Resolve AI Director product runtime..."
        RMDir /r "$LocalAppData\\AIDirector\\DaVinciResolve"
        RMDir "$LocalAppData\\AIDirector"
    ${{endif}}
!macroend
'''

def validate_nsis_include(
    text: str,
    *,
    resolve_integration_setup: Path | None = None,
    resolve_integration_version: str | None = None,
    branding=None,
    runtime_stack_archive: Path | None = None,
    runtime_stack_marker: str | None = None,
    runtime_stack_required_targets: list[str] | None = None,
    runtime_stack_partial_roots: list[str] | None = None,
):
    macro_lines = [
        line.strip().casefold()
        for line in text.splitlines()
        if line.strip().casefold().startswith("!macro ")
    ]

    integration_expected = resolve_integration_setup is not None or resolve_integration_version is not None
    if integration_expected and (resolve_integration_setup is None or not resolve_integration_version):
        raise RuntimeError("NSIS validation requires both optional Resolve Integration child Setup and target version.")

    branding_schema = None
    if branding is not None:
        branding_schema = (branding.get("manifest") or {}).get("schema_version")

    expected_macros = [
        "customInstallMode",
        "customInit",
        "customInstall",
        "customUnInstall",
    ]
    if integration_expected:
        expected_macros.append("customPageAfterChangeDir")
    for name in expected_macros:
        target = f"!macro {name}".casefold()
        count = sum(1 for line in macro_lines if line == target)
        if count != 1:
            raise RuntimeError(
                f"NSIS macro definition count is not exactly one: {name} (actual={count})"
            )

    if "`$" in text:
        raise RuntimeError(
            "Generated NSIS include contains a leftover PowerShell escape sequence: backtick-dollar."
        )

    low = text.lower()
    if "setcompress off" not in low or 'setcompress "${compress}"' not in low:
        raise RuntimeError("Runtime File is not protected from NSIS recompression.")
    if "generate-aidirectorruntimepaths.ps1" not in low:
        raise RuntimeError("Install-time path generator is not embedded.")
    if low.count("call aidevaluateruntimeseedstate") != 2:
        raise RuntimeError(
            "Runtime seed state must be evaluated once in customInit and again in customInstall."
        )
    if "re-evaluating davinci resolve ai director runtime after previous-version removal" not in low:
        raise RuntimeError("Post-uninstall runtime re-evaluation marker is missing.")
    if "${if} ${isupdated}" not in low or "preserving davinci resolve ai director product runtime during update" not in low:
        raise RuntimeError("Update-aware product runtime preservation is missing from customUnInstall.")
    if 'rmdir /r "$localappdata\\aidirector"' in low:
        raise RuntimeError("Uninstaller would recursively delete shared AIDirector root.")
    if 'rmdir /r "$localappdata\\davinci-resolve-mcp"' in low:
        raise RuntimeError("Uninstaller would delete shared managed MCP.")

    if branding_schema in (2, 3):
        header_tokens = (
            "!define MUI_HEADERIMAGE",
            "!define MUI_UI_HEADERIMAGE",
            "ai-director-header-ui.exe",
            "!define MUI_HEADERIMAGE_BITMAP",
            "installerHeaderBanner.bmp",
            '!define MUI_HEADERIMAGE_BITMAP_STRETCH "FitControl"',
            "!define MUI_HEADER_TRANSPARENT_TEXT",
            '!define MUI_TEXTCOLOR "202020"',
            "!define MUI_CUSTOMFUNCTION_GUIINIT aidBrandingHeaderGuiInit",
            "Function aidBrandingHeaderGuiInit",
            'CreateFont $R1 "$(^Font)" "11" "700"',
            "SendMessage $R0 ${WM_SETFONT} $R1 0",
            "Welcome to AI Director",
        )
        for token in header_tokens:
            if token not in text:
                raise RuntimeError(
                    f"Brand-v2/v3 NSIS header contract missing: {token}"
                )
    else:
        for token in (
            "ai-director-header-ui.exe",
            "installerHeaderBanner.bmp",
            "aidBrandingHeaderGuiInit",
        ):
            if token in text:
                raise RuntimeError(
                    f"Brand-v2 NSIS header token leaked into non-v2 branding: {token}"
                )

    integration_tokens = (
        "include davinci resolve workflow integration",
        "add ai director launcher to davinci resolve",
        "aiddirectorresolveintegration",
        "ai-director-resolve-integration-setup.exe",
        'execshellwait "runas"',
    )

    if integration_expected:
        child = str(resolve_integration_setup)
        required_line = f'File /oname=ai-director-resolve-integration-setup.exe "{child}"'

        if [line.strip() for line in text.splitlines()].count(required_line) != 1:
            raise RuntimeError(
                "Core NSIS include must embed the exact Resolve Integration child Setup exactly once."
            )

        common_required_tokens = (
            "!include \"nsDialogs.nsh\"",
            "!macro customPageAfterChangeDir",
            "Page custom aidResolveIntegrationPageCreate aidResolveIntegrationPageLeave",
            "StrCpy $aidIncludeResolveIntegration ${BST_CHECKED}",
            "StrCpy $aidCreateDesktopShortcut ${BST_CHECKED}",
            "Var /GLOBAL aidDesktopShortcutCheckbox",
            "Create a desktop shortcut",
            "ShowInstDetails show",
            "SetDetailsPrint both",
            "Stage 1 of 5 - Checking installed AI Director state...",
            "Stage 2 of 5 - Preparing AI Director core runtime...",
            "Stage 3 of 5 - Preparing AI Director acceleration runtime...",
            "Stage 4 of 5 - Applying DaVinci Resolve integration choice...",
            "Stage 5 of 5 - Finalizing shortcuts and installation...",
            'CreateShortCut "$DESKTOP\\DaVinci Resolve AI Director.lnk" "$INSTDIR\\DaVinci Resolve AI Director.exe" "" "$INSTDIR\\DaVinci Resolve AI Director.exe" 0',
            'ExecShellWait "runas" "$PLUGINSDIR\\ai-director-resolve-integration-setup.exe" "/S"',
            "SetShellVarContext all",
            "SetShellVarContext current",
            'ReadRegStr $R3 HKLM "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\DaVinciResolveAIDirectorResolveIntegration" "DisplayVersion"',
            f'StrCmp $R3 "{resolve_integration_version}" aid_resolve_integration_success aid_resolve_integration_failed_all_context',
        )

        if branding_schema in (2, 3):
            ui_required_tokens = (
                '${NSD_CreateLabel} 0 0u 100% 12u "Installation options"',
                'Add AI Director launcher to DaVinci Resolve',
                '${NSD_CreateCheckbox} 0 36u 100% 12u "Create a desktop shortcut"',
                '${NSD_CreateLabel} 0 58u 100% 12u "Information"',
                "Adds an AI Director launcher to DaVinci Resolve's Workflow Integration menu.",
                'CreateFont $R4 "$(^Font)" "$(^FontSize)" "700"',
                "SendMessage $R1 ${WM_SETFONT} $R4 0",
                "SendMessage $R2 ${WM_SETFONT} $R4 0",
            )

            forbidden_old_copy = (
                "Choose whether to add AI Director to DaVinci Resolve.",
                "Include DaVinci Resolve Workflow Integration",
                "You can install it separately later.",
            )

            for token in forbidden_old_copy:
                if token in text:
                    raise RuntimeError(
                        f"Old Resolve Integration UX copy leaked into Brand-v2/v3: {token}"
                    )
        else:
            ui_required_tokens = (
                '${NSD_CreateLabel} 0 0u 100% 12u "Installation options"',
                '${NSD_CreateLabel} 0 14u 100% 20u "Choose whether to add AI Director to DaVinci Resolve."',
                "Include DaVinci Resolve Workflow Integration",
                "You can install it separately later.",
            )

        for token in common_required_tokens + ui_required_tokens:
            if token not in text:
                raise RuntimeError(
                    f"Core NSIS optional Resolve Integration contract missing: {token}"
                )

        shortcut_sequence = (
            'SetOutPath "$INSTDIR"\n'
            '    CreateShortCut "$DESKTOP\\DaVinci Resolve AI Director.lnk" '
            '"$INSTDIR\\DaVinci Resolve AI Director.exe" "" '
            '"$INSTDIR\\DaVinci Resolve AI Director.exe" 0'
        )
        if shortcut_sequence not in text:
            raise RuntimeError(
                "Desktop shortcut must bind its working directory and icon source to the installed application."
            )

        if "MUI_HEADER_TEXT" in text:
            raise RuntimeError(
                "Core NSIS optional page must not depend on MUI_HEADER_TEXT; use native nsDialogs controls only."
            )

        page_guard = '!ifndef BUILD_UNINSTALLER\n!include "nsDialogs.nsh"'

        if page_guard not in text:
            raise RuntimeError(
                "Core NSIS optional page declarations must be excluded from the BUILD_UNINSTALLER pass."
            )

        page_guard_start = text.index(page_guard)
        page_guard_end = text.index("!endif", page_guard_start)

        for guarded_token in (
            "!macro customPageAfterChangeDir",
            "Page custom aidResolveIntegrationPageCreate aidResolveIntegrationPageLeave",
            "Function aidResolveIntegrationPageCreate",
            "Function aidResolveIntegrationPageLeave",
        ):
            token_pos = text.index(guarded_token)

            if not (page_guard_start < token_pos < page_guard_end):
                raise RuntimeError(
                    f"Core NSIS optional page token escapes BUILD_UNINSTALLER guard: {guarded_token}"
                )

        if low.count("setcompress off") < 2:
            raise RuntimeError(
                "Embedded Resolve Integration child Setup is not protected from outer NSIS recompression."
            )

        if 'rmdir /r "$localappdata\\blackmagic design' in low or "deleteregkey hklm" in low:
            raise RuntimeError(
                "Core Setup must not directly delete/mutate the machine-scoped Resolve Integration ownership surface."
            )
    else:
        for token in integration_tokens:
            if token in low:
                raise RuntimeError(
                    f"Core NSIS include unexpectedly contains optional Resolve Integration token: {token}"
                )

    runtime_stack_expected = runtime_stack_archive is not None
    runtime_stack_tokens = (
        "ai-director-runtime-stack.7z",
        "aid_runtime_stack_present",
        "aid_runtime_stack_absent",
        "aid_runtime_stack_inconsistent",
        "AI Director versioned runtime stack",
    )

    if runtime_stack_expected:
        if runtime_stack_marker is None:
            raise RuntimeError("NSIS runtime-stack validation requires install marker.")
        if runtime_stack_required_targets is None or not runtime_stack_required_targets:
            raise RuntimeError("NSIS runtime-stack validation requires required targets.")
        if runtime_stack_partial_roots is None or not runtime_stack_partial_roots:
            raise RuntimeError("NSIS runtime-stack validation requires partial-root cleanup guards.")
        exact_archive_line = (
            'File /oname=ai-director-runtime-stack.7z "'
            + str(runtime_stack_archive)
            + '"'
        )
        if [line.strip() for line in text.splitlines()].count(exact_archive_line) != 1:
            raise RuntimeError(
                "Core NSIS include must embed the exact runtime-stack archive exactly once."
            )
        for token in runtime_stack_tokens:
            if token.lower() not in low:
                raise RuntimeError(
                    f"Core NSIS runtime-stack contract missing: {token}"
                )
        marker_win = str(runtime_stack_marker).replace("/", "\\")
        if f'$LocalAppData\\{marker_win}'.lower() not in low:
            raise RuntimeError("Core NSIS runtime-stack marker check is missing.")
        marker_parent_win = str(Path(str(runtime_stack_marker)).parent).replace("/", "\\")
        cleanup_roots = list(dict.fromkeys(
            [str(x).replace("/", "\\") for x in runtime_stack_partial_roots]
            + [marker_parent_win]
        ))
        for rel_win in cleanup_roots:
            cleanup_line = f'RMDir /r "$LocalAppData\\{rel_win}"'.lower()
            if cleanup_line not in low:
                raise RuntimeError(
                    f"Core NSIS runtime-stack copy-failure cleanup is missing: {rel_win}"
                )
        if "partial stack bytes from this attempt were removed" not in low:
            raise RuntimeError("Core NSIS runtime-stack recoverable-copy-failure message is missing.")
        for rel in runtime_stack_required_targets:
            rel_win = str(rel).replace("/", "\\")
            if f'$LocalAppData\\{rel_win}'.lower() not in low:
                raise RuntimeError(
                    f"Core NSIS runtime-stack required-file check is missing: {rel}"
                )
        if "davinci-resolve-mcp" in "\n".join(
            line for line in text.splitlines()
            if "runtime-stack" in line.lower() or "aid-runtime-stack-out" in line.lower()
        ).lower():
            raise RuntimeError(
                "Runtime-stack NSIS path unexpectedly references managed MCP."
            )
    else:
        for token in runtime_stack_tokens:
            if token.lower() in low:
                raise RuntimeError(
                    f"Core NSIS unexpectedly contains runtime-stack token: {token}"
                )


CANDIDATE_DESCRIPTOR = "BUILDER-CANDIDATE.json"
OVERLAY_DESCRIPTOR = "OVERLAY.json"
BRANDING_DESCRIPTOR = "BRANDING.json"
RESOLVE_LAUNCHER_DESCRIPTOR = "RESOLVE-LAUNCHER.json"
RUNTIME_STACK_DESCRIPTOR = "RUNTIME-STACK.json"
RUNTIME_STACK_MANIFEST_NAME = "RUNTIME-STACK-MANIFEST.json"
RUNTIME_STACK_ARCHIVE_NAME = "RUNTIME-STACK.7z"
RUNTIME_BASE_DESCRIPTOR = runtime_base_control.RUNTIME_BASE_DESCRIPTOR
BUILDER_CONTROL_VERSION = "2.7.2-clean-transactional-v0"
BRANDING_MANIFEST_NAME = "BRANDING-MANIFEST.json"
RESOLVE_LAUNCHER_MANIFEST_NAME = "RESOLVE-LAUNCHER-MANIFEST.json"
RESOLVE_LAUNCHER_PLUGIN_ID = "com.aidirector.davinciresolve"
RESOLVE_LAUNCHER_FILES = {"payload/main.js", "payload/manifest.xml"}
AI_DIRECTOR_INTEGRATION_PRODUCT_NAME = f"{PRODUCT_NAME} Integration"
AI_DIRECTOR_INTEGRATION_SETUP_PREFIX = f"{AI_DIRECTOR_INTEGRATION_PRODUCT_NAME} Setup"
AI_DIRECTOR_INTEGRATION_FILE_DESCRIPTION = "AI Director Workflow Integration Launcher"
RESOLVE_LAUNCHER_INSTALLER_PREFIX = AI_DIRECTOR_INTEGRATION_SETUP_PREFIX
RESOLVE_LAUNCHER_MACHINE_DATA_BINDING_MODE = "NSIS_3_0_4_1_SHELL_CONTEXT_ALL_LOCALAPPDATA_TO_PROGRAMDATA_V1"
RESOLVE_LAUNCHER_ACL_PROVISIONING_MODE = "SECURE_EMPTY_DIRECTORY_THEN_INHERIT_PAYLOAD_V1"
RESOLVE_LAUNCHER_UNINSTALLER_NAME = f"Remove {AI_DIRECTOR_INTEGRATION_PRODUCT_NAME}.exe"
RESOLVE_LAUNCHER_UNINSTALL_REGISTRY_KEY = r"Software\Microsoft\Windows\CurrentVersion\Uninstall\DaVinciResolveAIDirectorResolveIntegration"
UNIFIED_OPTIONAL_RESOLVE_INTEGRATION_POLICY = "unified-optional-resolve-integration-v1"
UNIFIED_OPTIONAL_RESOLVE_INTEGRATION_MODE = "ASSISTED_DEFAULT_CHECKED_EXACT_CHILD_SETUP_V1"
EXPECTED_MAKENSIS_SHA256 = "F2B2B7726AC0D4E720DFF52BFCA11A5518D550FC75ED34A48DC47921527293F0"
BRANDING_SOURCE_PATHS_V1 = [
    "source/AI-Director-Icon-Master.png",
    "source/AI-Director-Icon-Master.svg",
    "source/installerHeader.svg",
    "source/installerSidebar.svg",
]
BRANDING_SHIPPING_CONTRACT_V1 = {
    "build/icon.ico": None,
    "build/installerHeader.bmp": (150, 57, 24),
    "build/installerSidebar.bmp": (164, 314, 24),
    "build/uninstallerSidebar.bmp": (164, 314, 24),
}
BRANDING_NSIS_CONTRACT_V1 = {
    "installer_header": "150x57 24-bit RGB BMP",
    "installer_sidebar": "164x314 24-bit RGB BMP",
    "uninstaller_sidebar": "164x314 24-bit RGB BMP",
}

BRANDING_SOURCE_PATHS_V2 = [
    "source/AI-Director-Icon-Master.png",
    "source/AI-Director-Icon-Master.svg",
    "source/installerHeaderBanner.svg",
    "source/installerSidebar.svg",
    "source/nsis/ai-director-header-v2.rc",
    "source/nsis/ui_stub.c",
]
BRANDING_SHIPPING_CONTRACT_V2 = {
    "build/icon.ico": None,
    "build/installerHeaderBanner.bmp": (497, 57, 24),
    "build/installerSidebar.bmp": (164, 314, 24),
    "build/uninstallerSidebar.bmp": (164, 314, 24),
    "build/ai-director-header-ui.exe": None,
}
BRANDING_NSIS_CONTRACT_V2 = {
    "installer_header_banner": "497x57 24-bit RGB BMP",
    "installer_header_ui_resource": "Win32 IDD_INST full-band resource",
    "installer_sidebar": "164x314 24-bit RGB BMP",
    "uninstaller_sidebar": "164x314 24-bit RGB BMP",
}
BRANDING_SOURCE_PATHS_V3 = [
    "source/AI-Director-Icon-Master.png",
    "source/AI-Director-Icon-Master.svg",
    "source/AI-Director-Icon-Windows-Reference-256.png",
    "source/installerHeaderBanner.svg",
    "source/installerSidebar.svg",
    "source/nsis/ai-director-header-v2.rc",
    "source/nsis/ui_stub.c",
]
BRANDING_SHIPPING_CONTRACT_V3 = dict(BRANDING_SHIPPING_CONTRACT_V2)
BRANDING_NSIS_CONTRACT_V3 = dict(BRANDING_NSIS_CONTRACT_V2)
BRANDING_ICO_SIZES = [16, 20, 24, 32, 40, 48, 64, 96, 128, 256]












def safe_relative_path(value: str, *, label: str) -> Path:
    raw = str(value or "").replace("\\", "/")
    p = Path(raw)
    if not raw or p.is_absolute() or ".." in p.parts or ":" in raw:
        raise RuntimeError(f"Unsafe {label}: {value!r}")
    return p






def _branding_rows_by_path(rows, *, label: str) -> dict[str, dict]:
    if not isinstance(rows, list):
        raise RuntimeError(f"{label} must be a list.")
    out = {}
    for row in rows:
        if not isinstance(row, dict):
            raise RuntimeError(f"{label} entries must be objects.")
        rel = safe_relative_path(row.get("path"), label=f"{label} path").as_posix()
        key = rel.lower()
        if key in out:
            raise RuntimeError(f"Duplicate {label} path: {rel}")
        digest = str(row.get("sha256") or "").upper()
        if not re.fullmatch(r"[0-9A-F]{64}", digest):
            raise RuntimeError(f"Invalid SHA-256 in {label}: {rel}")
        out[key] = {"path": rel, "sha256": digest}
    return out


def validate_ico_contract(path: Path, *, require_32bpp_alpha: bool = False):
    data = path.read_bytes()
    if len(data) < 6:
        raise RuntimeError(f"ICO is too small: {path}")
    reserved, kind, count = struct.unpack_from("<HHH", data, 0)
    if reserved != 0 or kind != 1:
        raise RuntimeError(f"Invalid ICO header: {path}")
    if count != len(BRANDING_ICO_SIZES):
        raise RuntimeError(
            f"ICO frame count mismatch. Expected={len(BRANDING_ICO_SIZES)} Actual={count} Path={path}"
        )
    need = 6 + count * 16
    if len(data) < need:
        raise RuntimeError(f"ICO directory is truncated: {path}")
    sizes = []
    details = []
    for i in range(count):
        entry = 6 + i * 16
        width, height, _colors, _reserved, planes, bpp, byte_count, image_offset = struct.unpack_from(
            "<BBBBHHII", data, entry
        )
        width = 256 if width == 0 else width
        height = 256 if height == 0 else height
        sizes.append((width, height))
        if image_offset < need or byte_count <= 0 or image_offset + byte_count > len(data):
            raise RuntimeError(f"ICO frame payload range is invalid at index {i}: {path}")
        blob = data[image_offset:image_offset + byte_count]
        frame = {"size": width, "planes": planes, "directory_bpp": bpp, "format": None}
        if blob.startswith(b"\x89PNG\r\n\x1a\n"):
            if len(blob) < 26 or blob[12:16] != b"IHDR":
                raise RuntimeError(f"ICO PNG frame is malformed at {width}x{height}: {path}")
            png_width, png_height, bit_depth, color_type = struct.unpack_from(">IIBB", blob, 16)
            if (png_width, png_height) != (width, height):
                raise RuntimeError(f"ICO PNG frame dimensions mismatch at {width}x{height}: {path}")
            frame.update({"format": "PNG", "payload_bpp": 32 if (bit_depth, color_type) == (8, 6) else None})
            if require_32bpp_alpha and (planes != 1 or bpp != 32 or (bit_depth, color_type) != (8, 6)):
                raise RuntimeError(f"Brand-v3 ICO PNG frame must be 8-bit RGBA/32bpp at {width}x{height}: {path}")
        else:
            if len(blob) < 40:
                raise RuntimeError(f"ICO DIB frame is truncated at {width}x{height}: {path}")
            header_size = struct.unpack_from("<I", blob, 0)[0]
            dib_width = struct.unpack_from("<i", blob, 4)[0]
            dib_height = struct.unpack_from("<i", blob, 8)[0]
            dib_planes = struct.unpack_from("<H", blob, 12)[0]
            dib_bpp = struct.unpack_from("<H", blob, 14)[0]
            compression = struct.unpack_from("<I", blob, 16)[0]
            if header_size < 40 or dib_width != width or abs(dib_height) != height * 2:
                raise RuntimeError(f"ICO DIB geometry mismatch at {width}x{height}: {path}")
            frame.update({"format": "DIB", "payload_bpp": dib_bpp})
            if require_32bpp_alpha:
                if planes != 1 or bpp != 32 or dib_planes != 1 or dib_bpp != 32 or compression != 0:
                    raise RuntimeError(f"Brand-v3 ICO DIB frame must be uncompressed 32bpp at {width}x{height}: {path}")
                pixel_bytes = width * height * 4
                if header_size + pixel_bytes > len(blob):
                    raise RuntimeError(f"Brand-v3 ICO DIB pixels are truncated at {width}x{height}: {path}")
                pixels = blob[header_size:header_size + pixel_bytes]
                alpha = pixels[3::4]
                if not any(0 < value < 255 for value in alpha):
                    raise RuntimeError(f"Brand-v3 ICO frame lacks semi-transparent alpha at {width}x{height}: {path}")
                def alpha_at(x: int, y: int) -> int:
                    row = height - 1 - y
                    return pixels[(row * width + x) * 4 + 3]
                corners = (alpha_at(0, 0), alpha_at(width - 1, 0), alpha_at(0, height - 1), alpha_at(width - 1, height - 1))
                if max(corners) > 8:
                    raise RuntimeError(f"Brand-v3 ICO corner alpha exceeds shell-stability contract at {width}x{height}: {corners} Path={path}")
        details.append(frame)
    expected = [(x, x) for x in BRANDING_ICO_SIZES]
    if sizes != expected:
        raise RuntimeError(f"ICO frame dimensions mismatch. Expected={expected} Actual={sizes} Path={path}")
    return details


def validate_bmp_contract(path: Path, width: int, height: int, bits_per_pixel: int):
    data = path.read_bytes()
    if len(data) < 54 or data[:2] != b"BM":
        raise RuntimeError(f"Invalid BMP header: {path}")
    dib_size = struct.unpack_from("<I", data, 14)[0]
    if dib_size < 40:
        raise RuntimeError(f"Unsupported BMP DIB header: {path}")
    actual_width = struct.unpack_from("<i", data, 18)[0]
    actual_height = abs(struct.unpack_from("<i", data, 22)[0])
    actual_bpp = struct.unpack_from("<H", data, 28)[0]
    compression = struct.unpack_from("<I", data, 30)[0]
    if (actual_width, actual_height, actual_bpp) != (width, height, bits_per_pixel):
        raise RuntimeError(
            "BMP contract mismatch. "
            f"Expected={width}x{height} {bits_per_pixel}-bit "
            f"Actual={actual_width}x{actual_height} {actual_bpp}-bit Path={path}"
        )
    if compression != 0:
        raise RuntimeError(f"BMP must be uncompressed BI_RGB. Compression={compression} Path={path}")
    return actual_width, actual_height, actual_bpp


def _branding_contract_for_manifest(manifest: dict):
    schema = manifest.get("schema_version")

    if schema == 1:
        return (
            BRANDING_SOURCE_PATHS_V1,
            BRANDING_SHIPPING_CONTRACT_V1,
            BRANDING_NSIS_CONTRACT_V1,
        )

    if schema == 2:
        return (
            BRANDING_SOURCE_PATHS_V2,
            BRANDING_SHIPPING_CONTRACT_V2,
            BRANDING_NSIS_CONTRACT_V2,
        )

    if schema == 3:
        return (
            BRANDING_SOURCE_PATHS_V3,
            BRANDING_SHIPPING_CONTRACT_V3,
            BRANDING_NSIS_CONTRACT_V3,
        )

    raise RuntimeError(
        f"Unsupported branding manifest schema_version: {schema!r}"
    )


def validate_branding_manifest(root: Path, manifest: dict, expected_id: str):
    schema = manifest.get("schema_version")

    source_paths, shipping_contract, expected_nsis = (
        _branding_contract_for_manifest(manifest)
    )

    if manifest.get("branding_id") != expected_id:
        raise RuntimeError(
            f"Branding manifest identity mismatch. Expected={expected_id!r} Actual={manifest.get('branding_id')!r}"
        )

    if manifest.get("product") != PRODUCT_NAME:
        raise RuntimeError("Branding manifest product mismatch.")

    icon_contract = manifest.get("icon_contract") or {}

    if icon_contract.get("ico_frames") != BRANDING_ICO_SIZES:
        raise RuntimeError("Branding ICO frame contract mismatch.")

    if schema == 2:
        if icon_contract.get("action") != "carry-forward-byte-identical-from-AI-Director-Brand-v1":
            raise RuntimeError("Brand-v2 ICO carry-forward contract mismatch.")
        expected_policy = {
            "hashes_are_version_specific": True,
            "visual_change_requires_new_branding_version": True,
            "exports_are_reproducible_non_authoritative": True,
            "brand_v1_is_immutable_predecessor": True,
        }
        if (manifest.get("policy") or {}) != expected_policy:
            raise RuntimeError("Brand-v2 policy contract mismatch.")

    if schema == 3:
        expected_icon_contract = {
            "ico_frames": BRANDING_ICO_SIZES,
            "action": "stabilize-windows-shell-frames-32bpp-alpha-v1",
            "predecessor_branding_id": "AI-Director-Brand-v2",
            "predecessor_icon_sha256": "3713B977D5BD4926D7FA0EEA32BA86C9981608BC52840F56906FC84F1C0C1155",
            "all_frames_bits_per_pixel": 32,
            "small_frame_alpha": "32bpp-dib-with-semtransparent-alpha",
            "corner_alpha_max": 8,
            "source_reference": "source/AI-Director-Icon-Windows-Reference-256.png",
            "source_reference_sha256": "3AB53A43FA05FBEBE1F5AB487337BB325D3C19F64DB245B4E909B285D44FFDB7",
            "resample_filter": "Lanczos",
        }
        if icon_contract != expected_icon_contract:
            raise RuntimeError("Brand-v3 shell-stable ICO contract mismatch.")
        expected_policy = {
            "hashes_are_version_specific": True,
            "visual_change_requires_new_branding_version": True,
            "exports_are_reproducible_non_authoritative": True,
            "brand_v2_is_immutable_predecessor": True,
        }
        if (manifest.get("policy") or {}) != expected_policy:
            raise RuntimeError("Brand-v3 policy contract mismatch.")

    if schema in (2, 3):
        expected_installer_ui = {
            "mode": "FULL_WIDTH_BRANDED_HEADER_V1",
            "header": {
                "bitmap": "build/installerHeaderBanner.bmp",
                "ui_resource": "build/ai-director-header-ui.exe",
                "title": "Welcome to AI Director",
                "subtitle": "",
                "title_font_size_pt": 11,
                "title_font_weight": 700,
                "text_color_rgb": "202020",
                "transparent_text": True,
                "full_band_centered": True,
            },
            "resolve_integration_page": {
                "heading": "Installation options",
                "heading_font_weight": 700,
                "checkbox": "Add AI Director launcher to DaVinci Resolve",
                "information_heading": "Information",
                "information_heading_font_weight": 700,
                "information_text": "Adds an AI Director launcher to DaVinci Resolve's Workflow Integration menu.",
            },
        }

        if (manifest.get("installer_ui") or {}) != expected_installer_ui:
            raise RuntimeError(f"Brand-v{schema} installer UI contract mismatch.")

        expected_render_contract = {
            "inkscape_cli": True,
            "supersample_factor": 4,
            "resample_filter": "Lanczos",
            "colorspace": "sRGB",
            "channel_depth_bits": 8,
            "bmp_format": "BMP3",
            "bmp_bits_per_pixel": 24,
            "header": {
                "authoring_canvas": "497x57",
                "supersample_canvas": "1988x228",
                "final_canvas": "497x57",
            },
            "sidebar": {
                "authoring_canvas": "164x314",
                "supersample_canvas": "656x1256",
                "final_canvas": "164x314",
            },
        }

        if (manifest.get("render_contract") or {}) != expected_render_contract:
            raise RuntimeError(f"Brand-v{schema} render contract mismatch.")

    nsis_contract = manifest.get("nsis_contract") or {}

    if nsis_contract != expected_nsis:
        raise RuntimeError("Branding NSIS bitmap contract mismatch.")

    source_rows = _branding_rows_by_path(
        manifest.get("authoring_sources"),
        label="branding authoring_sources",
    )

    shipping_rows = _branding_rows_by_path(
        manifest.get("shipping_assets"),
        label="branding shipping_assets",
    )

    expected_source = {x.lower() for x in source_paths}
    expected_shipping = {x.lower() for x in shipping_contract}

    if set(source_rows) != expected_source:
        raise RuntimeError(
            f"Branding authoring source set mismatch. Expected={sorted(expected_source)} Actual={sorted(source_rows)}"
        )

    if set(shipping_rows) != expected_shipping:
        raise RuntimeError(
            f"Branding shipping asset set mismatch. Expected={sorted(expected_shipping)} Actual={sorted(shipping_rows)}"
        )

    for row in list(source_rows.values()) + list(shipping_rows.values()):
        assert_hash(
            f"branding asset {row['path']}",
            root / Path(row["path"]),
            row["sha256"],
        )

    validate_ico_contract(root / "build" / "icon.ico", require_32bpp_alpha=(schema == 3))

    for rel, contract in shipping_contract.items():
        if contract is not None:
            validate_bmp_contract(root / Path(rel), *contract)

    if schema in (2, 3):
        ui_resource = root / "build" / "ai-director-header-ui.exe"
        data = ui_resource.read_bytes()

        if len(data) < 2 or data[:2] != b"MZ":
            raise RuntimeError(
                f"Brand-v{schema} header UI resource is not a Win32 PE image: {ui_resource}"
            )

    return manifest


def load_active_branding(builder: Path, current: dict):
    entry = current.get("active_branding")
    if entry in (None, {}):
        return None
    if not isinstance(entry, dict):
        raise RuntimeError("CURRENT active_branding must be an object when present.")
    bid = str(entry.get("id") or "").strip()
    if not bid:
        raise RuntimeError("CURRENT active_branding id is missing.")
    root = builder / "branding"
    descriptor_path = root / BRANDING_DESCRIPTOR
    assert_hash(
        f"active branding descriptor {bid}", descriptor_path, str(entry.get("manifest_sha256") or "")
    )
    descriptor = json.loads(descriptor_path.read_text(encoding="utf-8-sig"))
    if descriptor.get("branding_id") != bid:
        raise RuntimeError(f"Active branding identity mismatch: {bid}")
    source_manifest_rel = safe_relative_path(
        descriptor.get("source_manifest") or BRANDING_MANIFEST_NAME,
        label="active branding source manifest",
    )
    source_manifest_path = root / source_manifest_rel
    assert_hash(
        f"active branding source manifest {bid}",
        source_manifest_path,
        str(descriptor.get("source_manifest_sha256") or ""),
    )
    source_manifest = json.loads(source_manifest_path.read_text(encoding="utf-8-sig"))
    validate_branding_manifest(root, source_manifest, bid)
    return {"id": bid, "root": root, "manifest": source_manifest}




def copy_branding_build_assets(branding, destination_build: Path):
    if branding is None:
        return []

    destination_build.mkdir(parents=True, exist_ok=True)

    manifest = branding["manifest"]
    _source_paths, shipping_contract, _nsis_contract = (
        _branding_contract_for_manifest(manifest)
    )

    rows = _branding_rows_by_path(
        manifest.get("shipping_assets"),
        label="effective branding shipping_assets",
    )

    copied = []

    for rel in shipping_contract:
        row = rows[rel.lower()]
        src = branding["root"] / Path(row["path"])
        dst = destination_build / Path(row["path"]).name

        shutil.copy2(src, dst)
        assert_hash(
            f"staged branding {dst.name}",
            dst,
            row["sha256"],
        )

        copied.append(dst.name)

    return copied





def _launcher_rows_by_path(rows, *, label: str) -> dict[str, dict]:
    if not isinstance(rows, list):
        raise RuntimeError(f"{label} must be a list.")
    out = {}
    for row in rows:
        if not isinstance(row, dict):
            raise RuntimeError(f"{label} entries must be objects.")
        rel = safe_relative_path(row.get("path"), label=f"{label} path").as_posix()
        key = rel.lower()
        if key in out:
            raise RuntimeError(f"Duplicate {label} path: {rel}")
        digest = str(row.get("sha256") or "").upper()
        if not re.fullmatch(r"[0-9A-F]{64}", digest):
            raise RuntimeError(f"Invalid SHA-256 in {label}: {rel}")
        out[key] = {"path": rel, "sha256": digest}
    return out


def validate_resolve_launcher_manifest(root: Path, manifest: dict, expected_id: str):
    if manifest.get("schema_version") != 1:
        raise RuntimeError("Unsupported Resolve launcher manifest schema_version.")
    if manifest.get("launcher_id") != expected_id:
        raise RuntimeError(
            f"Resolve launcher identity mismatch. Expected={expected_id!r} Actual={manifest.get('launcher_id')!r}"
        )
    if manifest.get("product") != PRODUCT_NAME:
        raise RuntimeError("Resolve launcher manifest product mismatch.")
    if manifest.get("plugin_id") != RESOLVE_LAUNCHER_PLUGIN_ID:
        raise RuntimeError("Resolve launcher plugin ID mismatch.")
    install_contract = manifest.get("install_contract") or {}
    expected_contract = {
        "scope": "machine",
        "requires_elevation": True,
        "core_setup_mutates_programdata": False,
        "plugin_folder_acl": "SYSTEM:F;Administrators:F;Users:RX;inheritance:removed",
    }
    if install_contract != expected_contract:
        raise RuntimeError(
            f"Resolve launcher install contract mismatch. Expected={expected_contract} Actual={install_contract}"
        )
    rows = _launcher_rows_by_path(manifest.get("files"), label="Resolve launcher files")
    expected_files = {x.lower() for x in RESOLVE_LAUNCHER_FILES}
    if set(rows) != expected_files:
        raise RuntimeError(
            f"Resolve launcher file set mismatch. Expected={sorted(expected_files)} Actual={sorted(rows)}"
        )
    for row in rows.values():
        assert_hash(f"Resolve launcher payload {row['path']}", root / Path(row["path"]), row["sha256"])

    manifest_xml = root / "payload" / "manifest.xml"
    try:
        xml_root = ET.parse(manifest_xml).getroot()
    except Exception as exc:
        raise RuntimeError(f"Resolve launcher manifest.xml is invalid XML: {exc}") from exc
    plugin = xml_root.find("Plugin")
    if xml_root.tag != "BlackmagicDesign" or plugin is None:
        raise RuntimeError("Resolve launcher manifest.xml BlackmagicDesign/Plugin structure mismatch.")
    expected_xml = {
        "Id": RESOLVE_LAUNCHER_PLUGIN_ID,
        "Name": PRODUCT_NAME,
        "FilePath": "main.js",
    }
    for tag, value in expected_xml.items():
        node = plugin.find(tag)
        actual = (node.text or "").strip() if node is not None else ""
        if actual != value:
            raise RuntimeError(f"Resolve launcher manifest.xml {tag} mismatch. Expected={value!r} Actual={actual!r}")
    version_node = plugin.find("Version")
    if version_node is None or not re.fullmatch(r"\d+\.\d+\.\d+", (version_node.text or "").strip()):
        raise RuntimeError("Resolve launcher manifest.xml Version must be x.y.z.")

    main_text = (root / "payload" / "main.js").read_text(encoding="utf-8-sig")
    required_tokens = [
        "child_process",
        "spawn",
        "process.env.LOCALAPPDATA",
        "DaVinci Resolve AI Director.exe",
        "DAVINCI_RESOLVE_AI_DIRECTOR_HOST_MODE",
        "standalone",
        "resolve-workflow-integration",
        "child.unref()",
        "app.quit()",
    ]
    for token in required_tokens:
        if token not in main_text:
            raise RuntimeError(f"Resolve launcher main.js required token missing: {token}")
    forbidden_tokens = [
        "WorkflowIntegration.node",
        "launcher-target.json",
        "AI-Director-Standalone-" + "Owned-Electron-Candidate",
        "State" + "OfReason",
        "SOR" + "_AI_DIRECTOR",
        "C:" + "\\\\AI\\\\",
    ]
    for token in forbidden_tokens:
        if token in main_text:
            raise RuntimeError(f"Resolve launcher main.js contains forbidden legacy/coupled token: {token}")
    return manifest


def load_active_resolve_launcher(builder: Path, current: dict):
    entry = current.get("active_resolve_launcher")
    if entry in (None, {}):
        return None
    if not isinstance(entry, dict):
        raise RuntimeError("CURRENT active_resolve_launcher must be an object when present.")
    lid = str(entry.get("id") or "").strip()
    if not lid:
        raise RuntimeError("CURRENT active_resolve_launcher id is missing.")
    root = builder / "src" / "resolve-integration"
    descriptor_path = root / RESOLVE_LAUNCHER_DESCRIPTOR
    assert_hash(
        f"active Resolve launcher descriptor {lid}",
        descriptor_path,
        str(entry.get("manifest_sha256") or ""),
    )
    descriptor = json.loads(descriptor_path.read_text(encoding="utf-8-sig"))
    if descriptor.get("launcher_id") != lid:
        raise RuntimeError(f"Active Resolve launcher identity mismatch: {lid}")
    source_manifest_rel = safe_relative_path(
        descriptor.get("source_manifest") or RESOLVE_LAUNCHER_MANIFEST_NAME,
        label="active Resolve launcher source manifest",
    )
    source_manifest_path = root / source_manifest_rel
    assert_hash(
        f"active Resolve launcher source manifest {lid}",
        source_manifest_path,
        str(descriptor.get("source_manifest_sha256") or ""),
    )
    source_manifest = json.loads(source_manifest_path.read_text(encoding="utf-8-sig"))
    validate_resolve_launcher_manifest(root, source_manifest, lid)
    return {"id": lid, "root": root, "manifest": source_manifest}







def _runtime_stack_supported_sms(value, *, label: str) -> list[str]:
    if not isinstance(value, list) or not value:
        raise RuntimeError(f"{label} supported_sms must be a non-empty list.")
    out = []
    for item in value:
        s = str(item).strip().lower()
        if not re.fullmatch(r"(?:75|80|86|89|90|120a?|121a?)", s):
            raise RuntimeError(f"{label} contains unsupported SM token: {item!r}")
        out.append(s)
    if len(set(out)) != len(out):
        raise RuntimeError(f"{label} supported_sms contains duplicates.")
    return out


def validate_runtime_stack_manifest(
    root: Path,
    manifest: dict,
    candidate_id: str,
    *,
    verify_source_files: bool = True,
):
    if not isinstance(manifest, dict):
        raise RuntimeError("Runtime-stack manifest must be a JSON object.")
    if manifest.get("schema_version") != 2:
        raise RuntimeError("Runtime-stack manifest schema_version must be 2 for builder v2.6.1.")
    if manifest.get("runtime_stack_id") != candidate_id:
        raise RuntimeError(
            "Runtime-stack manifest identity mismatch. "
            f"Expected={candidate_id!r} Actual={manifest.get('runtime_stack_id')!r}"
        )
    if manifest.get("runtime_line") != "cuda13":
        raise RuntimeError("Runtime-stack runtime_line must be 'cuda13'.")
    if manifest.get("toolkit_line") != "13.3":
        raise RuntimeError("Runtime-stack toolkit_line must be '13.3'.")
    if manifest.get("toolkit_version") != "13.3.1":
        raise RuntimeError("Runtime-stack toolkit_version must be '13.3.1'.")
    support_policy_id = str(manifest.get("support_policy_id") or "").strip()
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,79}", support_policy_id):
        raise RuntimeError("Runtime-stack support_policy_id is missing or invalid.")
    if manifest.get("managed_mcp_mutation") is not False:
        raise RuntimeError(
            "Runtime-stack candidates must declare managed_mcp_mutation=false."
        )

    driver_policy = manifest.get("driver_policy")
    if not isinstance(driver_policy, dict):
        raise RuntimeError("Runtime-stack driver_policy must be an object.")
    if str(driver_policy.get("vendor") or "").strip().lower() != "nvidia":
        raise RuntimeError("Runtime-stack driver_policy vendor must be nvidia.")
    if str(driver_policy.get("platform") or "").strip().lower() != "windows":
        raise RuntimeError("Runtime-stack driver_policy platform must be windows.")
    if int(driver_policy.get("minimum_driver_major") or 0) != 580:
        raise RuntimeError(
            "Runtime-stack driver_policy minimum_driver_major must be 580 for CUDA 13 minor-version compatibility."
        )
    if driver_policy.get("compatibility_basis") != "CUDA_13_MINOR_VERSION_COMPATIBILITY":
        raise RuntimeError(
            "Runtime-stack driver_policy compatibility_basis must be CUDA_13_MINOR_VERSION_COMPATIBILITY."
        )

    gpu_policy = manifest.get("gpu_policy")
    if not isinstance(gpu_policy, dict):
        raise RuntimeError("Runtime-stack gpu_policy must be an object.")
    if int(gpu_policy.get("minimum_sm") or 0) != 75:
        raise RuntimeError("Runtime-stack GPU policy minimum_sm must be 75.")
    policy_sms = _runtime_stack_supported_sms(
        gpu_policy.get("supported_sms"),
        label="runtime-stack gpu_policy",
    )

    cuda = manifest.get("cuda")
    direct = manifest.get("direct")
    upstream = manifest.get("upstream")
    for label, obj in (("cuda", cuda), ("direct", direct), ("upstream", upstream)):
        if not isinstance(obj, dict):
            raise RuntimeError(f"Runtime-stack {label} section must be an object.")

    cuda_root = safe_relative_path(
        cuda.get("install_root"),
        label="runtime-stack CUDA install_root",
    ).as_posix()
    if cuda_root != "AIDirector/Common/Runtime/CUDA/13.3":
        raise RuntimeError(
            "Runtime-stack CUDA install_root must be "
            "AIDirector/Common/Runtime/CUDA/13.3."
        )

    direct_root = safe_relative_path(
        direct.get("install_root"),
        label="runtime-stack Direct install_root",
    ).as_posix()
    expected_direct_prefix = (
        f"AIDirector/DaVinciResolve/Runtime/Llama/Stacks/{candidate_id}/Direct/"
    )
    if not direct_root.startswith(expected_direct_prefix):
        raise RuntimeError(
            "Runtime-stack Direct install_root must be versioned below "
            f"{expected_direct_prefix}"
        )
    if direct.get("source_mode") != "exact-source":
        raise RuntimeError("Runtime-stack Direct source_mode must be exact-source.")
    if str(direct.get("source_commit") or "").lower() != (
        "c8f321699adbd0035c8c755bdefcb4182705262b"
    ):
        raise RuntimeError("Runtime-stack Direct source_commit is not accepted c8f321699.")
    direct_sms = _runtime_stack_supported_sms(
        direct.get("supported_sms"),
        label="runtime-stack Direct",
    )

    upstream_root = safe_relative_path(
        upstream.get("install_root"),
        label="runtime-stack Upstream install_root",
    ).as_posix()
    expected_upstream_root = (
        f"AIDirector/DaVinciResolve/Runtime/Llama/Stacks/{candidate_id}/Upstream/Current"
    )
    if upstream_root != expected_upstream_root:
        raise RuntimeError(
            "Runtime-stack Upstream install_root must be the updater-owned Current root: "
            f"{expected_upstream_root}"
        )
    if upstream.get("source_mode") != "source-successor":
        raise RuntimeError(
            "Runtime-stack Upstream source_mode must be source-successor because "
            "the accepted predecessor source commit is not recoverable."
        )
    if upstream.get("accepted_predecessor_ref") != "b11160-mix-a6922cc":
        raise RuntimeError("Runtime-stack Upstream predecessor ref mismatch.")
    if str(upstream.get("accepted_predecessor_commit") or "").lower() != (
        "a3c12db9dfc9a5bdf93df199ec370e9faf117c69"
    ):
        raise RuntimeError("Runtime-stack Upstream predecessor commit mismatch.")
    upstream_commit = str(upstream.get("source_commit") or "").strip().lower()
    if not re.fullmatch(r"[0-9a-f]{40}", upstream_commit):
        raise RuntimeError("Runtime-stack Upstream successor source_commit must be a full SHA-1.")
    upstream_ref = str(upstream.get("source_ref") or "").strip()
    if not upstream_ref:
        raise RuntimeError("Runtime-stack Upstream successor source_ref is required.")
    upstream_sms = _runtime_stack_supported_sms(
        upstream.get("supported_sms"),
        label="runtime-stack Upstream",
    )

    if upstream.get("ownership") != "UPSTREAM_ONLY_TRANSACTIONAL_UPDATER_V2":
        raise RuntimeError(
            "Runtime-stack Upstream ownership must preserve the transactional Upstream-only updater."
        )
    update_policy = upstream.get("update_policy")
    if not isinstance(update_policy, dict):
        raise RuntimeError("Runtime-stack Upstream update_policy must be an object.")
    if update_policy.get("enabled") is not True:
        raise RuntimeError("Runtime-stack Upstream update_policy must be enabled.")
    if update_policy.get("repository") != "unslothai/llama.cpp":
        raise RuntimeError("Runtime-stack Upstream updater repository must be unslothai/llama.cpp.")
    if update_policy.get("bundle_profile") != "cuda13-portable":
        raise RuntimeError("Runtime-stack Upstream bundle_profile must be cuda13-portable.")
    if update_policy.get("runtime_line") != "cuda13":
        raise RuntimeError("Runtime-stack Upstream update runtime_line must be cuda13.")
    if update_policy.get("toolkit_line") != "13.3":
        raise RuntimeError("Runtime-stack Upstream update toolkit_line must be 13.3.")
    if update_policy.get("compatibility_scope") != "LOCAL_GPU_AND_STACK_CONTRACT":
        raise RuntimeError(
            "Runtime-stack Upstream update compatibility_scope must be LOCAL_GPU_AND_STACK_CONTRACT."
        )
    shared_cuda_root = safe_relative_path(
        update_policy.get("shared_cuda_root"),
        label="runtime-stack Upstream shared_cuda_root",
    ).as_posix()
    if shared_cuda_root != cuda_root:
        raise RuntimeError(
            "Runtime-stack Upstream updater must use the same product-owned shared CUDA root."
        )
    seed_marker = safe_relative_path(
        update_policy.get("seed_marker"),
        label="runtime-stack Upstream seed_marker",
    ).as_posix()
    expected_seed_marker = f"{upstream_root}/UNSLOTH_PREBUILT_INFO.json"
    if seed_marker != expected_seed_marker:
        raise RuntimeError(
            f"Runtime-stack Upstream seed_marker must be {expected_seed_marker}."
        )

    if direct_sms != policy_sms or upstream_sms != policy_sms:
        raise RuntimeError(
            "Runtime-stack GPU support policy must be identical for Direct and Upstream."
        )

    marker = safe_relative_path(
        manifest.get("install_marker"),
        label="runtime-stack install_marker",
    ).as_posix()
    expected_marker = (
        f"AIDirector/DaVinciResolve/Runtime/Stacks/{candidate_id}/"
        f"{RUNTIME_STACK_MANIFEST_NAME}"
    )
    if marker != expected_marker:
        raise RuntimeError(
            f"Runtime-stack install_marker must be {expected_marker}."
        )

    payload_files = manifest.get("payload_files")
    if not isinstance(payload_files, list) or not payload_files:
        raise RuntimeError("Runtime-stack payload_files must be a non-empty list.")

    allowed_prefixes = (
        cuda_root + "/",
        direct_root + "/",
        upstream_root + "/",
    )
    target_rows = {}
    source_seen = set()
    for row in payload_files:
        if not isinstance(row, dict):
            raise RuntimeError("Runtime-stack payload file entries must be objects.")
        source_rel = safe_relative_path(
            row.get("source"),
            label="runtime-stack payload source",
        )
        target_rel = safe_relative_path(
            row.get("target"),
            label="runtime-stack payload target",
        )
        source_posix = source_rel.as_posix()
        target_posix = target_rel.as_posix()
        if not source_posix.startswith("payload/"):
            raise RuntimeError(
                f"Runtime-stack payload sources must be below payload/: {source_posix}"
            )
        if not any(target_posix.startswith(prefix) for prefix in allowed_prefixes):
            raise RuntimeError(
                "Runtime-stack payload target is outside versioned/additive roots: "
                f"{target_posix}"
            )
        if target_posix.lower().startswith("davinci-resolve-mcp/"):
            raise RuntimeError("Runtime-stack payload may not mutate managed MCP.")
        key = target_posix.lower()
        if key in target_rows:
            raise RuntimeError(f"Duplicate runtime-stack payload target: {target_posix}")
        if source_posix.lower() in source_seen:
            raise RuntimeError(f"Duplicate runtime-stack payload source: {source_posix}")
        source_seen.add(source_posix.lower())
        expected = str(row.get("sha256") or "").upper()
        if not re.fullmatch(r"[0-9A-F]{64}", expected):
            raise RuntimeError(
                f"Invalid runtime-stack payload SHA-256 for {target_posix}."
            )
        if verify_source_files:
            source_path = root / source_rel
            assert_hash(
                f"runtime-stack payload {target_posix}",
                source_path,
                expected,
            )
        target_rows[key] = target_posix

    required_install_targets = manifest.get("required_install_targets")
    if not isinstance(required_install_targets, list) or not required_install_targets:
        raise RuntimeError(
            "Runtime-stack required_install_targets must be a non-empty list."
        )
    required_normalized = []
    required_keys = set()
    for raw in required_install_targets:
        rel = safe_relative_path(
            raw,
            label="runtime-stack required install target",
        ).as_posix()
        key = rel.lower()
        if key in required_keys:
            raise RuntimeError(
                f"Duplicate runtime-stack required install target: {rel}"
            )
        required_keys.add(key)
        if key not in target_rows:
            raise RuntimeError(
                "Runtime-stack required install target is not a payload target: "
                f"{rel}"
            )
        required_normalized.append(rel)

    payload_keys = set(target_rows)
    if required_keys != payload_keys:
        missing_required_rows = sorted(payload_keys - required_keys)
        unexpected_required_rows = sorted(required_keys - payload_keys)
        raise RuntimeError(
            "Runtime-stack required_install_targets must exactly equal payload targets. "
            f"Missing={json.dumps(missing_required_rows)} "
            f"Unexpected={json.dumps(unexpected_required_rows)}"
        )

    seed_marker_key = seed_marker.lower()
    if seed_marker_key not in target_rows:
        raise RuntimeError(
            "Runtime-stack payload must include the Upstream updater seed marker: "
            f"{seed_marker}"
        )

    if verify_source_files:
        marker_row = next(
            row for row in payload_files
            if safe_relative_path(
                row.get("target"),
                label="runtime-stack payload target",
            ).as_posix().lower() == seed_marker_key
        )
        seed_marker_path = root / safe_relative_path(
            marker_row.get("source"),
            label="runtime-stack Upstream seed marker source",
        )
        try:
            seed_info = json.loads(seed_marker_path.read_text(encoding="utf-8-sig"))
        except Exception as exc:
            raise RuntimeError(
                f"Runtime-stack Upstream seed marker is not valid JSON: {seed_marker_path}"
            ) from exc
        if seed_info.get("upstream_tag") != upstream.get("accepted_predecessor_ref"):
            raise RuntimeError(
                "Runtime-stack Upstream seed marker upstream_tag must preserve the accepted predecessor release identity."
            )
        if str(seed_info.get("source_commit") or "").lower() != upstream_commit:
            raise RuntimeError(
                "Runtime-stack Upstream seed marker source_commit must match the successor source commit."
            )
        if seed_info.get("platform") != "windows-x64-cuda":
            raise RuntimeError("Runtime-stack Upstream seed marker platform must be windows-x64-cuda.")
        if seed_info.get("bundle_profile") != update_policy.get("bundle_profile"):
            raise RuntimeError("Runtime-stack Upstream seed marker bundle_profile mismatch.")
        if seed_info.get("runtime_line") != "cuda13":
            raise RuntimeError("Runtime-stack Upstream seed marker runtime_line must be cuda13.")
        if seed_info.get("toolkit_line") != "13.3":
            raise RuntimeError("Runtime-stack Upstream seed marker toolkit_line must be 13.3.")
        if seed_info.get("ai_director_runtime_stack_id") != candidate_id:
            raise RuntimeError("Runtime-stack Upstream seed marker stack identity mismatch.")
        if str(seed_info.get("ai_director_source_tree") or "").lower() != str(upstream.get("source_tree") or "").lower():
            raise RuntimeError("Runtime-stack Upstream seed marker source tree mismatch.")
        marker_sms = _runtime_stack_supported_sms(
            seed_info.get("ai_director_supported_sms"),
            label="runtime-stack Upstream seed marker",
        )
        if marker_sms != upstream_sms:
            raise RuntimeError("Runtime-stack Upstream seed marker GPU policy mismatch.")

    mandatory_targets = {
        f"{cuda_root}/cudart64_13.dll".lower(),
        f"{cuda_root}/cublas64_13.dll".lower(),
        f"{cuda_root}/cublasLt64_13.dll".lower(),
        f"{direct_root}/llama-server.exe".lower(),
        f"{upstream_root}/llama-server.exe".lower(),
        seed_marker.lower(),
    }
    missing_mandatory = sorted(mandatory_targets - set(target_rows))
    if missing_mandatory:
        raise RuntimeError(
            "Runtime-stack payload is missing mandatory runtime targets: "
            + json.dumps(missing_mandatory)
        )
    missing_required = sorted(
        mandatory_targets - {x.lower() for x in required_normalized}
    )
    if missing_required:
        raise RuntimeError(
            "Runtime-stack required_install_targets must include the mandatory "
            "CUDA/Direct/Upstream anchors: "
            + json.dumps(missing_required)
        )

    return manifest




def load_active_runtime_stack(builder: Path, current: dict):
    entry = current.get("active_runtime_stack")
    if entry in (None, {}):
        return None
    if not isinstance(entry, dict):
        raise RuntimeError("CURRENT active_runtime_stack must be an object when present.")
    sid = str(entry.get("id") or "").strip()
    if not sid:
        raise RuntimeError("CURRENT active_runtime_stack id is missing.")
    root = builder / "provenance" / "runtime" / "runtime-stack"
    descriptor_path = root / RUNTIME_STACK_DESCRIPTOR
    assert_hash(f"active runtime-stack descriptor {sid}", descriptor_path, str(entry.get("manifest_sha256") or ""))
    descriptor = json.loads(descriptor_path.read_text(encoding="utf-8-sig"))
    if descriptor.get("schema_version") != 2:
        raise RuntimeError("Canonical runtime-stack descriptor schema mismatch.")
    if descriptor.get("runtime_stack_id") != sid:
        raise RuntimeError(f"Active runtime-stack identity mismatch: {sid}")
    if descriptor.get("application_source_authority") != "CANONICAL" or descriptor.get("application_composition_active") is not False:
        raise RuntimeError("Runtime-stack application composition must be disabled under canonical source architecture.")
    if "application_files" in descriptor:
        raise RuntimeError("Runtime-stack descriptor still carries application replacements.")
    state_contract = {
        "archive_sha256": descriptor.get("archive_sha256"),
        "runtime_line": descriptor.get("runtime_line"),
        "toolkit_line": descriptor.get("toolkit_line"),
        "toolkit_version": descriptor.get("toolkit_version"),
        "support_policy_id": descriptor.get("support_policy_id"),
    }
    for key, expected in state_contract.items():
        observed = entry.get(key)
        if observed not in (None, "") and str(observed) != str(expected):
            raise RuntimeError(f"CURRENT active_runtime_stack {key} mismatch. Expected={expected!r} Actual={observed!r}")
    source_manifest_rel = safe_relative_path(descriptor.get("source_manifest") or RUNTIME_STACK_MANIFEST_NAME, label="active runtime-stack source manifest")
    source_manifest_path = root / source_manifest_rel
    assert_hash(f"active runtime-stack source manifest {sid}", source_manifest_path, str(descriptor.get("source_manifest_sha256") or ""))
    source_manifest = json.loads(source_manifest_path.read_text(encoding="utf-8-sig"))
    validate_runtime_stack_manifest(root, source_manifest, sid, verify_source_files=False)
    archive_path = root / RUNTIME_STACK_ARCHIVE_NAME
    # Historical accepted runtime-stack bytes are comparison authority, not a
    # normal public source-build input. Validate them only when deliberately present.
    if archive_path.is_file():
        assert_hash(f"active runtime-stack archive {sid}", archive_path, str(descriptor.get("archive_sha256") or ""))
        if int(descriptor.get("archive_bytes") or -1) != archive_path.stat().st_size:
            raise RuntimeError(f"Active runtime-stack archive size mismatch: {sid}")
    else:
        archive_path = None
    return {"id": sid, "root": root, "descriptor": descriptor, "manifest": source_manifest, "manifest_path": source_manifest_path, "archive_path": archive_path}








def find_makensis(builder: Path) -> Path:
    cache = builder / "_cache" / "electron-builder-v1.3" / "nsis-3.0.4.1"
    hits = []
    if cache.is_dir():
        for p in cache.rglob("makensis.exe"):
            if (p.parent / "Include").is_dir() and (p.parent / "Plugins").is_dir():
                hits.append(p)
    if len(hits) != 1:
        raise RuntimeError(f"Expected exactly one root NSIS makensis.exe in accepted cache; found {len(hits)}")
    assert_hash("accepted cached makensis.exe", hits[0], EXPECTED_MAKENSIS_SHA256)
    return hits[0]


def _nsis_escape(value: str) -> str:
    return str(value).replace("$", "$$").replace('"', '$\\"')


def build_resolve_launcher_installer(
    builder: Path,
    work: Path,
    launcher,
    target_version: str,
    *,
    branding=None,
    log: Path,
) -> Path:
    validate_resolve_launcher_manifest(launcher["root"], launcher["manifest"], launcher["id"])
    makensis = find_makensis(builder)
    project = work / "resolve-launcher-installer"
    dist = project / "dist"
    project.mkdir(parents=True, exist_ok=True)
    dist.mkdir(parents=True, exist_ok=True)
    installer_name = f"{RESOLVE_LAUNCHER_INSTALLER_PREFIX} {target_version}.exe"
    out = dist / installer_name
    main_src = launcher["root"] / "payload" / "main.js"
    manifest_src = launcher["root"] / "payload" / "manifest.xml"
    version4 = target_version + ".0"
    plugin_dir = rf"$LOCALAPPDATA\Blackmagic Design\DaVinci Resolve\Support\Workflow Integration Plugins\{RESOLVE_LAUNCHER_PLUGIN_ID}"
    uninstall_key = RESOLVE_LAUNCHER_UNINSTALL_REGISTRY_KEY
    lines = [
        "Unicode true",
        "RequestExecutionLevel admin",
        f'Name "{AI_DIRECTOR_INTEGRATION_PRODUCT_NAME}"',
        f'Caption "{AI_DIRECTOR_INTEGRATION_PRODUCT_NAME}"',
        f'OutFile "{_nsis_escape(str(out))}"',
        "ShowInstDetails show",
        "ShowUninstDetails show",
        "SetCompressor /SOLID lzma",
        f'VIProductVersion "{version4}"',
        f'VIAddVersionKey /LANG=1033 "ProductName" "{AI_DIRECTOR_INTEGRATION_PRODUCT_NAME}"',
        f'VIAddVersionKey /LANG=1033 "FileDescription" "{AI_DIRECTOR_INTEGRATION_FILE_DESCRIPTION}"',
        f'VIAddVersionKey /LANG=1033 "FileVersion" "{target_version}"',
        f'VIAddVersionKey /LANG=1033 "ProductVersion" "{target_version}"',
        f'VIAddVersionKey /LANG=1033 "CompanyName" "{PRODUCT_PUBLISHER}"',
        f'VIAddVersionKey /LANG=1033 "LegalCopyright" "{PRODUCT_COPYRIGHT}"',
    ]
    if branding:
        validate_branding_manifest(branding["root"], branding["manifest"], branding["id"])
        icon = branding["root"] / "build" / "icon.ico"
        lines.extend([
            f'Icon "{_nsis_escape(str(icon))}"',
            f'UninstallIcon "{_nsis_escape(str(icon))}"',
        ])
    lines.extend([
        "",
        'Section "Install"',
        "  SetShellVarContext all",
        "  SetRegView 64",
        f'  StrCpy $INSTDIR "{plugin_dir}"',
        '  RMDir /r "$INSTDIR"',
        '  CreateDirectory "$INSTDIR"',
        '  nsExec::ExecToStack \'"$SYSDIR\\icacls.exe" "$INSTDIR" /inheritance:r /grant:r "*S-1-5-18:(OI)(CI)(F)" "*S-1-5-32-544:(OI)(CI)(F)" "*S-1-5-32-545:(OI)(CI)(RX)" /C /Q\'',
        '  Pop $0',
        '  Pop $1',
        '  StrCmp $0 "0" acl_ok',
        '    DetailPrint "Failed to secure Resolve Integration plugin folder. icacls exit=$0 output=$1"',
        '    RMDir /r "$INSTDIR"',
        '    Abort',
        '  acl_ok:',
        '  SetOutPath "$INSTDIR"',
        f'  File /oname=main.js "{_nsis_escape(str(main_src))}"',
        f'  File /oname=manifest.xml "{_nsis_escape(str(manifest_src))}"',
        f'  WriteUninstaller "$INSTDIR\\{RESOLVE_LAUNCHER_UNINSTALLER_NAME}"',
        f'  WriteRegStr HKLM "{uninstall_key}" "DisplayName" "{AI_DIRECTOR_INTEGRATION_PRODUCT_NAME}"',
        f'  WriteRegStr HKLM "{uninstall_key}" "DisplayVersion" "{target_version}"',
        f'  WriteRegStr HKLM "{uninstall_key}" "Publisher" "{PRODUCT_PUBLISHER}"',
        f'  WriteRegStr HKLM "{uninstall_key}" "UninstallString" \'"$INSTDIR\\{RESOLVE_LAUNCHER_UNINSTALLER_NAME}"\'',
        f'  WriteRegStr HKLM "{uninstall_key}" "QuietUninstallString" \'"$INSTDIR\\{RESOLVE_LAUNCHER_UNINSTALLER_NAME}" /S\'',
        f'  WriteRegDWORD HKLM "{uninstall_key}" "NoModify" 1',
        f'  WriteRegDWORD HKLM "{uninstall_key}" "NoRepair" 1',
        f'  WriteRegDWORD HKLM "{uninstall_key}" "SystemComponent" 1',
        '  DetailPrint "Resolve Integration installed. Restart DaVinci Resolve if it is currently running."',
        "SectionEnd",
        "",
        'Section "Uninstall"',
        "  SetShellVarContext all",
        "  SetRegView 64",
        f'  StrCpy $INSTDIR "{plugin_dir}"',
        f'  DeleteRegKey HKLM "{uninstall_key}"',
        '  Delete "$INSTDIR\\main.js"',
        '  Delete "$INSTDIR\\manifest.xml"',
        f'  Delete "$INSTDIR\\{RESOLVE_LAUNCHER_UNINSTALLER_NAME}"',
        '  RMDir "$INSTDIR"',
        "SectionEnd",
        "",
    ])
    script = project / "resolve-launcher.nsi"
    script.write_text("\n".join(lines), encoding="utf-8", newline="\n")
    low = script.read_text(encoding="utf-8").lower()
    fixed_target = plugin_dir.lower()
    required = [
        "requestexecutionlevel admin",
        RESOLVE_LAUNCHER_PLUGIN_ID.lower(),
        "$localappdata\\blackmagic design\\davinci resolve\\support\\workflow integration plugins\\",
        f'strcpy $instdir "{fixed_target}"',
        "icacls.exe",
        "*s-1-5-32-545:(oi)(ci)(rx)",
        "writeuninstaller",
        "deleteregkey hklm",
        f'viaddversionkey /lang=1033 "companyname" "{PRODUCT_PUBLISHER.lower()}"',
        f'viaddversionkey /lang=1033 "legalcopyright" "{PRODUCT_COPYRIGHT.lower()}"',
    ]
    for token in required:
        if token not in low:
            raise RuntimeError(f"Generated Resolve launcher NSIS contract missing: {token}")
    fixed_assignment = f'strcpy $instdir "{fixed_target}"'
    if low.count(fixed_assignment) != 2:
        raise RuntimeError("Generated Resolve launcher NSIS must force the fixed ProgramData target in install and uninstall sections.")
    shell_bound_assignment = "setshellvarcontext all\n  setregview 64\n  " + fixed_assignment
    if low.count(shell_bound_assignment) != 2:
        raise RuntimeError(
            "Generated Resolve launcher NSIS must bind the fixed machine target only after "
            "SetShellVarContext all in both install and uninstall sections."
        )
    if low.count("setshellvarcontext all") != 2:
        raise RuntimeError("Generated Resolve launcher NSIS must set all-users shell context exactly twice.")
    if "$commonprogramdata" in low:
        raise RuntimeError(
            "Generated Resolve launcher NSIS uses $COMMONPROGRAMDATA, which is not supported by the pinned NSIS 3.0.4.1 toolchain."
        )
    if "$programdata" in low:
        raise RuntimeError("Generated Resolve launcher NSIS uses invalid $PROGRAMDATA.")
    if "everyone" in low:
        raise RuntimeError("Generated Resolve launcher NSIS script must not grant Everyone permissions.")
    acl_command = 'nsexec::exectostack \'"$sysdir\\icacls.exe" "$instdir" /inheritance:r /grant:r "*s-1-5-18:(oi)(ci)(f)" "*s-1-5-32-544:(oi)(ci)(f)" "*s-1-5-32-545:(oi)(ci)(rx)" /c /q\''
    if low.count(acl_command) != 1:
        raise RuntimeError("Generated Resolve launcher NSIS must secure the empty plugin directory exactly once before writing payload files.")
    if "/t /c /q" in low:
        raise RuntimeError("Generated Resolve launcher NSIS must not recursively strip child-file ACL inheritance.")
    create_pos = low.index('createdirectory "$instdir"')
    acl_pos = low.index(acl_command)
    acl_ok_pos = low.index("acl_ok:")
    out_pos = low.index('setoutpath "$instdir"')
    main_pos = low.index("file /oname=main.js")
    manifest_pos = low.index("file /oname=manifest.xml")
    uninstaller_pos = low.index("writeuninstaller")
    if not (create_pos < acl_pos < acl_ok_pos < out_pos < main_pos < manifest_pos < uninstaller_pos):
        raise RuntimeError("Generated Resolve launcher NSIS ACL provisioning order is unsafe; directory ACL must be established before payload creation.")
    run([makensis, "/V4", script], cwd=project, log=log)
    if not out.is_file():
        raise RuntimeError(f"Expected Resolve Integration installer missing: {out}")
    return out


def static_audit_resolve_launcher_installer(
    installer: Path,
    launcher,
    work: Path,
    *,
    target_version: str,
    makensis_log: Path,
):
    # NSIS installers are validated from the exact pinned compiler inputs rather than
    # by treating the generated executable as a generic 7-Zip archive. The accepted
    # makensis.exe hash is guarded by find_makensis(), the generated script is
    # contract-checked before compilation, and this post-build audit re-verifies the
    # exact source payload, exact File directives, compiler log, and PE output.
    validate_resolve_launcher_manifest(launcher["root"], launcher["manifest"], launcher["id"])
    if not installer.is_file():
        raise RuntimeError(f"Resolve Integration installer missing for static audit: {installer}")
    size = installer.stat().st_size
    if size < 4096:
        raise RuntimeError(f"Resolve Integration installer is unexpectedly small: {size} bytes")

    with installer.open("rb") as fh:
        head = fh.read(4096)
    if len(head) < 64 or head[:2] != b"MZ":
        raise RuntimeError("Resolve Integration installer is not a valid MZ executable.")
    pe_offset = int.from_bytes(head[0x3C:0x40], "little")
    if pe_offset < 0x40:
        raise RuntimeError(f"Resolve Integration installer PE header offset is invalid: {pe_offset}")
    with installer.open("rb") as fh:
        fh.seek(pe_offset)
        pe_signature = fh.read(4)
    if pe_signature != b"PE\x00\x00":
        raise RuntimeError("Resolve Integration installer PE signature is invalid.")

    project = work / "resolve-launcher-installer"
    script = project / "resolve-launcher.nsi"
    if not script.is_file():
        raise RuntimeError(f"Generated Resolve launcher NSIS script missing: {script}")
    script_text = script.read_text(encoding="utf-8")
    script_low = script_text.lower()
    expected_fixed_target = (
        rf"$LOCALAPPDATA\Blackmagic Design\DaVinci Resolve\Support\Workflow Integration Plugins\{RESOLVE_LAUNCHER_PLUGIN_ID}"
    ).lower()
    expected_assignment = f'strcpy $instdir "{expected_fixed_target}"'
    expected_shell_bound_assignment = "setshellvarcontext all\n  setregview 64\n  " + expected_assignment
    if script_low.count(expected_shell_bound_assignment) != 2:
        raise RuntimeError(
            "Post-build Resolve launcher NSIS audit failed machine ProgramData binding contract."
        )
    if "$commonprogramdata" in script_low or "$programdata" in script_low:
        raise RuntimeError(
            "Post-build Resolve launcher NSIS audit found an unsupported ProgramData pseudo-constant."
        )

    acl_command = 'nsexec::exectostack \'"$sysdir\\icacls.exe" "$instdir" /inheritance:r /grant:r "*s-1-5-18:(oi)(ci)(f)" "*s-1-5-32-544:(oi)(ci)(f)" "*s-1-5-32-545:(oi)(ci)(rx)" /c /q\''
    if script_low.count(acl_command) != 1:
        raise RuntimeError("Post-build Resolve launcher NSIS audit failed ACL provisioning contract.")
    if "/t /c /q" in script_low:
        raise RuntimeError("Post-build Resolve launcher NSIS audit found recursive ACL mutation that can strip payload-file read access.")
    create_pos = script_low.index('createdirectory "$instdir"')
    acl_pos = script_low.index(acl_command)
    acl_ok_pos = script_low.index("acl_ok:")
    out_pos = script_low.index('setoutpath "$instdir"')
    main_pos = script_low.index("file /oname=main.js")
    manifest_pos = script_low.index("file /oname=manifest.xml")
    uninstaller_pos = script_low.index("writeuninstaller")
    if not (create_pos < acl_pos < acl_ok_pos < out_pos < main_pos < manifest_pos < uninstaller_pos):
        raise RuntimeError("Post-build Resolve launcher NSIS audit found unsafe ACL/payload creation order.")

    rows = _launcher_rows_by_path(launcher["manifest"].get("files"), label="effective Resolve launcher files")
    payload_hashes = {}
    required_file_lines = []
    for rel in RESOLVE_LAUNCHER_FILES:
        expected = rows[rel.lower()]["sha256"]
        source = launcher["root"] / rel
        assert_hash(f"Resolve launcher compiler input {rel}", source, expected)
        payload_hashes[rel] = expected
        required_file_lines.append(
            f'File /oname={Path(rel).name} "{_nsis_escape(str(source))}"'
        )

    normalized_lines = [line.strip() for line in script_text.splitlines()]
    for required_line in required_file_lines:
        if normalized_lines.count(required_line) != 1:
            raise RuntimeError(
                f"Generated Resolve launcher NSIS must contain exactly one compiler input line: {required_line}"
            )

    if not makensis_log.is_file() or makensis_log.stat().st_size <= 0:
        raise RuntimeError(f"Resolve Integration makensis log missing or empty: {makensis_log}")

    pe_metadata = validate_pe_project_metadata(
        installer,
        target_version=target_version,
        product_name=AI_DIRECTOR_INTEGRATION_PRODUCT_NAME,
        file_description=AI_DIRECTOR_INTEGRATION_FILE_DESCRIPTION,
    )

    audit = {
        "mode": "PINNED_NSIS_COMPILER_INPUT_PE_MACHINE_DATA_ACL_AND_METADATA_AUDIT_V4",
        "machine_data_binding_mode": RESOLVE_LAUNCHER_MACHINE_DATA_BINDING_MODE,
        "acl_provisioning_mode": RESOLVE_LAUNCHER_ACL_PROVISIONING_MODE,
        "installer_bytes": size,
        "installer_pe_valid": True,
        "pe_metadata": pe_metadata,
        "nsis_script_sha256": sha256(script),
        "makensis_log_sha256": sha256(makensis_log),
        "payload_sha256": payload_hashes,
        "installer_executed": False,
    }
    print("RESOLVE_LAUNCHER_STATIC_AUDIT_MODE=" + audit["mode"], flush=True)
    print("RESOLVE_LAUNCHER_NSIS_SCRIPT_SHA256=" + audit["nsis_script_sha256"], flush=True)
    print("RESOLVE_LAUNCHER_MAKENSIS_LOG_SHA256=" + audit["makensis_log_sha256"], flush=True)
    print("RESOLVE_LAUNCHER_PE_AUDIT=PASS", flush=True)
    print("RESOLVE_LAUNCHER_PE_METADATA_AUDIT=PASS", flush=True)
    print("RESOLVE_LAUNCHER_COMPILER_INPUT_AUDIT=PASS", flush=True)
    print("RESOLVE_LAUNCHER_MACHINE_DATA_BINDING_AUDIT=PASS", flush=True)
    print("RESOLVE_LAUNCHER_MACHINE_DATA_BINDING_MODE=" + audit["machine_data_binding_mode"], flush=True)
    print("RESOLVE_LAUNCHER_ACL_PROVISIONING_AUDIT=PASS", flush=True)
    print("RESOLVE_LAUNCHER_ACL_PROVISIONING_MODE=" + audit["acl_provisioning_mode"], flush=True)
    return audit


























def read_exe_version_info(exe: Path) -> dict[str, str]:
    escaped = str(exe).replace("'", "''")
    script = (
        f"$v=(Get-Item -LiteralPath '{escaped}').VersionInfo;"
        "$o=[ordered]@{"
        "file_version=[string]$v.FileVersion;"
        "product_version=[string]$v.ProductVersion;"
        "company_name=[string]$v.CompanyName;"
        "product_name=[string]$v.ProductName;"
        "file_description=[string]$v.FileDescription;"
        "legal_copyright=[string]$v.LegalCopyright;"
        "original_filename=[string]$v.OriginalFilename"
        "};"
        "$j=$o|ConvertTo-Json -Compress;"
        "[Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($j))"
    )
    lines = [line.strip() for line in run([
        "powershell.exe", "-NoProfile", "-NonInteractive", "-Command", script
    ]).stdout.splitlines() if line.strip()]
    if not lines:
        raise RuntimeError(f"Could not read EXE version information: {exe}")
    try:
        payload = base64.b64decode(lines[-1], validate=True).decode("utf-8")
        info = json.loads(payload)
    except Exception as exc:
        raise RuntimeError(f"Could not decode EXE VersionInfo for {exe}: {lines[-1]!r}") from exc
    keys = ("file_version", "product_version", "company_name", "product_name", "file_description", "legal_copyright", "original_filename")
    if not isinstance(info, dict) or set(info) != set(keys):
        raise RuntimeError(f"Unexpected EXE VersionInfo object for {exe}: {info!r}")
    return {key: str(info.get(key) or "").strip() for key in keys}


def read_exe_versions(exe: Path) -> tuple[str, str]:
    info = read_exe_version_info(exe)
    return info["file_version"], info["product_version"]


def validate_pe_project_metadata(exe: Path, *, target_version: str, product_name: str, file_description: str) -> dict[str, str]:
    info = read_exe_version_info(exe)
    if not version_prefix_matches(info["file_version"], target_version) or not version_prefix_matches(info["product_version"], target_version):
        raise RuntimeError(f"PE version mismatch for {exe}: {info}")
    if info["company_name"] != PRODUCT_PUBLISHER:
        raise RuntimeError(f"PE CompanyName mismatch for {exe}: {info}")
    if info["product_name"] != product_name:
        raise RuntimeError(f"PE ProductName mismatch for {exe}: {info}")
    if info["file_description"] != file_description:
        raise RuntimeError(f"PE FileDescription mismatch for {exe}: {info}")
    if info["legal_copyright"] != PRODUCT_COPYRIGHT:
        raise RuntimeError(f"PE LegalCopyright mismatch for {exe}: {info}")
    return info


def version_prefix_matches(observed: str, expected: str) -> bool:
    nums = re.findall(r"\d+", observed or "")
    exp = expected.split(".")
    return nums[:3] == exp[:3]













def main():
    raise RuntimeError("build_installer.py is an internal build core. Use BUILD.cmd.")

# Active 0.3.20 successor policy is loaded by explicit file path so the
# product-owned isolated Python does not depend on sibling sys.path behavior.
_SUCCESSOR_POLICY_PATH = Path(__file__).resolve().with_name("successor_policy.py")
_SUCCESSOR_POLICY_SPEC = importlib.util.spec_from_file_location(
    "aidirector_successor_policy",
    _SUCCESSOR_POLICY_PATH,
)
if _SUCCESSOR_POLICY_SPEC is None or _SUCCESSOR_POLICY_SPEC.loader is None:
    raise RuntimeError(f"Unable to load successor policy: {_SUCCESSOR_POLICY_PATH}")
_aid_successor_policy = importlib.util.module_from_spec(_SUCCESSOR_POLICY_SPEC)
_SUCCESSOR_POLICY_SPEC.loader.exec_module(_aid_successor_policy)
_aid_successor_policy.install_successor_policy(globals(), Path(__file__).resolve().parents[1])

if __name__ == "__main__":
    result = main()
    if isinstance(result, int):
        raise SystemExit(result)
