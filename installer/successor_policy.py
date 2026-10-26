from __future__ import annotations

import hashlib
import re
from pathlib import Path

FORBIDDEN_LEGACY_MIGRATION_TOKENS = (
    "Invoke-AIDirectorLegacyRuntimeRetirement-v1.ps1",
    "AI-Director-Legacy-Runtime-Retirement.json",
    "RETIREMENT-MANIFEST.json",
)

INTEGRATION_REL = "Blackmagic Design\\DaVinci Resolve\\Support\\Workflow Integration Plugins\\com.aidirector.davinciresolve"
INTEGRATION_UNINSTALL_KEY = "Software\\Microsoft\\Windows\\CurrentVersion\\Uninstall\\DaVinciResolveAIDirectorResolveIntegration"
CLEANUP_HELPER_NAME = "Remove-AIDirectorManagedState-v1.ps1"
COMPAT_ASSET_HELPER_NAME = "Install-AIDirectorMcpCompatibilityAssets-v1.ps1"

EXPECTED_RUNTIME_BASE_V5_ARCHIVE_SHA256 = "1F51536B3507C93FE72504A6B72557C70BD09D1195760996B2FB7FB8E20D8C4A"
EXPECTED_RUNTIME_BASE_INVENTORY_SHA256 = "88249F66294113A0CC31E2527DAD6CFD6BEAB4A0B79C2A78F860B7C3D9261C7C"
EXPECTED_COMPAT_ASSET_HELPER_SHA256 = "99079478EB9C049F6B627678C47F7E8CF88209B45AD57857B1AFF02FAC984488"


def _sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(4 * 1024 * 1024), b""):
            h.update(block)
    return h.hexdigest().upper()


def _assert_accepted_runtime_base(builder_root: Path, args, kwargs) -> None:
    archive = None
    if args:
        candidate = args[0]
        if isinstance(candidate, (str, Path)):
            archive = Path(candidate)
    if archive is None:
        for key in ("shipping_runtime_archive", "runtime_archive", "archive"):
            candidate = kwargs.get(key)
            if isinstance(candidate, (str, Path)):
                archive = Path(candidate)
                break
    if archive is None or not archive.is_file():
        raise RuntimeError("0.3.21 successor installer policy could not identify the runtime-base archive argument.")
    if _sha256(archive) != EXPECTED_RUNTIME_BASE_V5_ARCHIVE_SHA256:
        raise RuntimeError("Runtime-base v4 archive is not the exact A6 full-Nsis7z-parity BCJ archive.")

    inventory = (
        builder_root
        / "provenance"
        / "runtime"
        / "runtime-base"
        / "SHIPPING-INVENTORY.json"
    )
    if not inventory.is_file() or _sha256(inventory) != EXPECTED_RUNTIME_BASE_INVENTORY_SHA256:
        raise RuntimeError("Runtime-base v4 shipping inventory identity mismatch.")


def _validate_cleanup_helper(builder_root: Path) -> None:
    helper = builder_root / "runtime" / "support" / CLEANUP_HELPER_NAME
    if not helper.is_file():
        raise RuntimeError(f"Managed-state cleanup helper missing: {helper}")
    low = helper.read_text(encoding="utf-8-sig").casefold()
    required = (
        'validateset("keep","remove")',
        "settingsmode",
        "settings.json",
        "aidir-(new|backup|rejected|failed)",
        ".davinci-resolve-mcp-managed.json",
        "fail_safe_unproven_managed_mcp",
        "pass_owned_state_removed",
    )
    missing = [token for token in required if token not in low]
    if missing:
        raise RuntimeError(f"Managed-state cleanup helper contract missing: {missing}")


def _validate_compat_asset_helper(builder_root: Path) -> None:
    helper = builder_root / "runtime" / "support" / COMPAT_ASSET_HELPER_NAME
    if not helper.is_file():
        raise RuntimeError(f"Compatibility-asset helper missing: {helper}")
    if _sha256(helper) != EXPECTED_COMPAT_ASSET_HELPER_SHA256:
        raise RuntimeError("Compatibility-asset helper hash mismatch.")


def _nsis_escape_path(path: Path) -> str:
    return str(path).replace("$", "$$").replace('"', '$\\"')


def _replace_macro(text: str, macro_name: str, replacement: str) -> str:
    pattern = re.compile(
        rf"(?ms)^!macro\s+{re.escape(macro_name)}\s*$.*?^!macroend\s*$"
    )
    matches = list(pattern.finditer(text))
    if len(matches) != 1:
        raise RuntimeError(
            f"Expected exactly one !macro {macro_name}; found {len(matches)}"
        )
    return (
        text[: matches[0].start()]
        + replacement.rstrip()
        + "\n"
        + text[matches[0].end() :]
    )


def _uninstall_macro(builder_root: Path, integration_uninstaller_name: str) -> str:
    _validate_cleanup_helper(builder_root)
    helper = builder_root / "runtime" / "support" / CLEANUP_HELPER_NAME
    helper_nsis = _nsis_escape_path(helper)

    integration_uninstaller = f"$LOCALAPPDATA\\{INTEGRATION_REL}\\{integration_uninstaller_name}"
    integration_main = f"$LOCALAPPDATA\\{INTEGRATION_REL}\\main.js"
    integration_manifest = f"$LOCALAPPDATA\\{INTEGRATION_REL}\\manifest.xml"

    return rf'''!macro customUnInstall
    ${{if}} ${{isUpdated}}
        DetailPrint "Preserving DaVinci Resolve AI Director product runtime during update..."
        DetailPrint "Preserving validated managed runtime, MCP and user settings during update..."
    ${{else}}
        DetailPrint "Removing DaVinci Resolve AI Director managed state..."

        ; The machine-scoped Resolve Integration is removed first. If elevation
        ; is denied or removal cannot be proved, stop before current-user cleanup.
        SetShellVarContext all
        SetRegView 64
        StrCpy $R4 0

    aid_u_integration_begin:
        IfFileExists "{integration_uninstaller}" 0 aid_u_integration_verify_absent
        ClearErrors
        ExecShellWait "runas" "{integration_uninstaller}" "/S"
        IfErrors aid_u_integration_uac_retry 0
        StrCpy $R4 0
        Goto aid_u_integration_verify_absent

    aid_u_integration_verify_absent:
        IfFileExists "{integration_main}" aid_u_integration_retry_wait 0
        IfFileExists "{integration_manifest}" aid_u_integration_retry_wait 0
        ReadRegStr $R5 HKLM "{INTEGRATION_UNINSTALL_KEY}" "DisplayName"
        StrCmp $R5 "" aid_u_integration_removed aid_u_integration_retry_wait

    aid_u_integration_retry_wait:
        IntCmp $R4 80 aid_u_integration_timeout aid_u_integration_wait aid_u_integration_timeout

    aid_u_integration_wait:
        IntOp $R4 $R4 + 1
        Sleep 250
        Goto aid_u_integration_verify_absent

    aid_u_integration_uac_retry:
        SetShellVarContext current
        SetRegView lastused
        MessageBox MB_RETRYCANCEL|MB_ICONEXCLAMATION "Administrator approval is required to remove the DaVinci Resolve Workflow Integration. No AI Director settings, runtime, MCP, or application state has been removed. Choose Retry to request administrator approval again, or Cancel to leave AI Director installed." IDRETRY aid_u_integration_retry_elevation IDCANCEL aid_u_integration_cancel

    aid_u_integration_retry_elevation:
        SetShellVarContext all
        SetRegView 64
        StrCpy $R4 0
        Goto aid_u_integration_begin

    aid_u_integration_timeout:
        SetShellVarContext current
        SetRegView lastused
        MessageBox MB_RETRYCANCEL|MB_ICONEXCLAMATION "DaVinci Resolve Workflow Integration has not finished uninstalling. No AI Director settings, runtime, MCP, or application state has been removed. Choose Retry to try the integration removal again, or Cancel to leave AI Director installed." IDRETRY aid_u_integration_retry_after_timeout IDCANCEL aid_u_integration_cancel

    aid_u_integration_retry_after_timeout:
        SetShellVarContext all
        SetRegView 64
        StrCpy $R4 0
        Goto aid_u_integration_begin

    aid_u_integration_cancel:
        SetShellVarContext current
        SetRegView lastused
        DetailPrint "AI Director uninstall cancelled before local managed-state cleanup."
        Quit
    aid_u_integration_removed:
        SetShellVarContext current
        SetRegView lastused

        ; Settings retention is intentionally narrow: only the AI Director
        ; settings.json file can survive. Runtime, MCP, updater state and caches
        ; are never retained by this choice.
        MessageBox MB_YESNO|MB_ICONQUESTION|MB_DEFBUTTON2 "Keep your AI Director settings for a future installation?$\r$\n$\r$\nYes keeps only settings.json.$\r$\nNo performs a complete reset." IDYES aid_u_settings_keep IDNO aid_u_settings_remove

    aid_u_settings_keep:
        StrCpy $R8 "Keep"
        Goto aid_u_settings_selected

    aid_u_settings_remove:
        StrCpy $R8 "Remove"

    aid_u_settings_selected:
        SetOutPath "$PLUGINSDIR"
        File /oname={CLEANUP_HELPER_NAME} "{helper_nsis}"
        ClearErrors
        nsExec::ExecToStack '"$SYSDIR\\WindowsPowerShell\\v1.0\\powershell.exe" -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "$PLUGINSDIR\\{CLEANUP_HELPER_NAME}" -LocalAppData "$LocalAppData" -AppData "$APPDATA" -ReportPath "$TEMP\\AI-Director-Uninstall-Managed-State.json" -SettingsMode "$R8"'
        Pop $R6
        Pop $R7
        StrCmp $R6 "0" aid_u_managed_cleanup_ok 0
        DetailPrint "$R7"
        MessageBox MB_OK|MB_ICONSTOP "DaVinci Resolve AI Director could not safely remove all managed runtime/update state. An unknown or unproven MCP directory may be present, or cleanup verification failed. Protected state was preserved where possible. Review $TEMP\AI-Director-Uninstall-Managed-State.json and retry uninstall."
        Abort

    aid_u_managed_cleanup_ok:
        Delete "$PLUGINSDIR\\{CLEANUP_HELPER_NAME}"
        Delete "$DESKTOP\DaVinci Resolve AI Director.lnk"
        StrCmp $R8 "Keep" 0 aid_u_settings_removed
        DetailPrint "AI Director software, managed runtime, MCP and updater state removed; user settings retained."
        Goto aid_u_cleanup_done

    aid_u_settings_removed:
        DetailPrint "AI Director software, managed runtime, MCP, updater and user settings removed."

    aid_u_cleanup_done:
    ${{endif}}
!macroend'''



def _transform_runtime_base_v4_common_ownership(text: str) -> str:
    replacements = [
        (
            'Var /GLOBAL aidSeedCommonRuntime\n',
            '',
            'legacy core Common seed flag',
        ),
        (
            '    StrCpy $aidSeedCommonRuntime "0"\n',
            '',
            'legacy core Common seed initialization',
        ),
        (
            'aid_eval_product_done:\n'
            '    IfFileExists "$LocalAppData\\AIDirector\\Common\\*.*" aid_eval_common_done aid_eval_common_absent\n\n'
            'aid_eval_common_absent:\n'
            '    StrCpy $aidSeedCommonRuntime "1"\n\n'
            'aid_eval_common_done:\n',
            'aid_eval_product_done:\n',
            'legacy core Common seed evaluation',
        ),
        (
            '    StrCmp $aidSeedCommonRuntime "1" aid_seed_required 0\n',
            '',
            'legacy core Common extraction trigger',
        ),
        (
            '    IfFileExists "$PLUGINSDIR\\aid-runtime-out\\AIDirector\\Common\\*.*" 0 aid_extract_failed\n',
            '',
            'legacy core Common extraction assertion',
        ),
        (
            'aid_skip_product_copy:\n'
            '    StrCmp $aidSeedCommonRuntime "1" 0 aid_skip_common_copy\n'
            '    DetailPrint "Provisioning shared AI Director runtime..."\n'
            '    CreateDirectory "$LocalAppData\\AIDirector"\n'
            '    ClearErrors\n'
            '    CopyFiles /SILENT "$PLUGINSDIR\\aid-runtime-out\\AIDirector\\Common" "$LocalAppData\\AIDirector"\n'
            '    IfErrors aid_copy_failed 0\n\n'
            'aid_skip_common_copy:\n',
            'aid_skip_product_copy:\n',
            'legacy core Common copy block',
        ),
        (
            '    StrCmp $aidSeedCommonRuntime "1" aid_bind_paths\n',
            '',
            'legacy core Common path-binding trigger',
        ),
    ]

    out = text
    for old, new, label in replacements:
        count = out.count(old)
        if count != 1:
            raise RuntimeError(
                f"A6 runtime-base v4 Common ownership transform anchor mismatch ({label}); found {count}."
            )
        out = out.replace(old, new, 1)
    return out


def _transform_additive_compatibility_assets(text: str, builder_root: Path) -> str:
    _validate_compat_asset_helper(builder_root)
    helper = builder_root / "runtime" / "support" / COMPAT_ASSET_HELPER_NAME
    helper_nsis = _nsis_escape_path(helper)

    replacements = [
        (
            'Var /GLOBAL aidSeedManagedMcp\n',
            'Var /GLOBAL aidSeedManagedMcp\nVar /GLOBAL aidNeedMcpCompatibilityAssets\n',
            'global compatibility-assets flag',
        ),
        (
            '    StrCpy $aidSeedManagedMcp "0"\n',
            '    StrCpy $aidSeedManagedMcp "0"\n    StrCpy $aidNeedMcpCompatibilityAssets "1"\n',
            'compatibility-assets evaluation flag',
        ),
        (
            '    StrCmp $aidSeedManagedMcp "1" aid_seed_required aid_seed_not_required\n',
            '    StrCmp $aidSeedManagedMcp "1" aid_seed_required 0\n'
            '    StrCmp $aidNeedMcpCompatibilityAssets "1" aid_seed_required aid_seed_not_required\n',
            'runtime extraction decision',
        ),
        (
            '    DetailPrint "Binding per-user AI Director runtime paths..."\n',
            '    StrCmp $aidSeedProductRuntime "1" aid_bind_paths\n'
            '    StrCmp $aidSeedCommonRuntime "1" aid_bind_paths\n'
            '    StrCmp $aidSeedManagedMcp "1" aid_bind_paths aid_skip_path_binding\n\n'
            'aid_bind_paths:\n'
            '    DetailPrint "Binding per-user AI Director runtime paths..."\n',
            'path-binding guard',
        ),
        (
            '    Goto aid_seed_cleanup\n\naid_copy_failed:\n',
            '    Goto aid_after_core_seed\n\n'
            'aid_skip_path_binding:\n'
            '    DetailPrint "Preserving active MCP source, Python runtime, manifests, config and settings during compatibility-asset staging."\n\n'
            'aid_after_core_seed:\n'
            '    DetailPrint "Staging immutable MCP 4.15.3 compatibility assets without activating them..."\n'
            f'    nsExec::ExecToStack \'"$SYSDIR\\WindowsPowerShell\\v1.0\\powershell.exe" -NoProfile -NonInteractive -ExecutionPolicy Bypass -File "$PLUGINSDIR\\{COMPAT_ASSET_HELPER_NAME}" -ExtractedRuntimeRoot "$PLUGINSDIR\\aid-runtime-out" -LocalAppData "$LocalAppData" -ReportPath "$TEMP\\AI-Director-MCP-Compatibility-Assets.json"\'\n'
            '    Pop $R6\n'
            '    Pop $R7\n'
            '    StrCmp $R6 "0" aid_seed_cleanup 0\n'
            '    DetailPrint "$R7"\n'
            '    MessageBox MB_OK|MB_ICONSTOP "AI Director could not safely stage the immutable MCP 4.15.3 compatibility assets. Active MCP, Python, manifests, config and settings were not intentionally replaced. Review $TEMP\\AI-Director-MCP-Compatibility-Assets.json."\n'
            '    Abort\n\n'
            'aid_copy_failed:\n',
            'additive compatibility-assets invocation',
        ),
        (
            '    Delete "$PLUGINSDIR\\Generate-AIDirectorRuntimePaths.ps1"\n',
            '    Delete "$PLUGINSDIR\\Generate-AIDirectorRuntimePaths.ps1"\n'
            f'    Delete "$PLUGINSDIR\\{COMPAT_ASSET_HELPER_NAME}"\n',
            'compatibility helper cleanup',
        ),
    ]

    out = text
    for old, new, label in replacements:
        count = out.count(old)
        if count != 1:
            raise RuntimeError(
                f"A6 additive NSIS transform anchor mismatch ({label}); found {count}."
            )
        out = out.replace(old, new, 1)

    generator_pattern = re.compile(
        r'(?m)^    File /oname=Generate-AIDirectorRuntimePaths\.ps1 "[^"\r\n]+"\r?$'
    )
    generator_matches = list(generator_pattern.finditer(out))
    if len(generator_matches) != 1:
        raise RuntimeError(
            "A6 additive NSIS transform expected exactly one rendered path-generator File line; "
            f"found {len(generator_matches)}."
        )
    rendered = generator_matches[0].group(0).rstrip("\r")
    helper_line = f'    File /oname={COMPAT_ASSET_HELPER_NAME} "{helper_nsis}"'
    out = out[:generator_matches[0].start()] + rendered + "\n" + helper_line + out[generator_matches[0].end():]
    return out


def transform_nsis_include(text: str, builder_root: Path, integration_uninstaller_name: str) -> str:
    out = _replace_macro(text, "customUnInstall", _uninstall_macro(builder_root, integration_uninstaller_name))
    out = _transform_additive_compatibility_assets(out, builder_root)
    out = _transform_runtime_base_v4_common_ownership(out)
    low = out.casefold()
    residual = [
        token for token in FORBIDDEN_LEGACY_MIGRATION_TOKENS
        if token.casefold() in low
    ]
    if residual:
        raise RuntimeError(
            "0.3.21 generated NSIS contains forbidden legacy migration machinery: "
            + ", ".join(residual)
        )
    return out


def validate_successor_nsis(text: str, integration_uninstaller_name: str) -> None:
    low = text.casefold()
    required = (
        "preserving davinci resolve ai director product runtime during update",
        "preserving validated managed runtime, mcp and user settings during update",
        "keep your ai director settings for a future installation",
        "yes keeps only settings.json",
        "remove-aidirectormanagedstate-v1.ps1",
        '-settingsmode "$r8"',
        '-executionpolicy bypass -file',
        'execshellwait "runas"',
        "davinciresolveaidirectorresolveintegration",
        "unknown or unproven mcp directory may be present",
        "mb_retrycancel|mb_iconexclamation",
        "administrator approval is required to remove the davinci resolve workflow integration",
        "sleep 250",
        "idretry aid_u_integration_retry_elevation",
        "idcancel aid_u_integration_cancel",
        'delete "$desktop\\davinci resolve ai director.lnk"',
        'install-aidirectormcpcompatibilityassets-v1.ps1',
        'staging immutable mcp 4.15.3 compatibility assets without activating them',
        'preserving active mcp source, python runtime, manifests, config and settings during compatibility-asset staging',
        '-extractedruntimeroot "$pluginsdir\\aid-runtime-out"',
        'ai-director-mcp-compatibility-assets.json',
    )
    missing = [token for token in required if token not in low]
    if missing:
        raise RuntimeError(f"0.3.21 NSIS contract missing: {missing}")

    forbidden_core_common = (
        'var /global aidseedcommonruntime',
        'aid_eval_common_absent',
        'aid_eval_common_done',
        'strcmp $aidseedcommonruntime',
        '$pluginsdir\\aid-runtime-out\\aidirector\\common',
    )
    leaked_core_common = [token for token in forbidden_core_common if token in low]
    if leaked_core_common:
        raise RuntimeError(
            f"Runtime-base v4 core NSIS still owns Common payload state: {leaked_core_common}"
        )
    if (
        'copyfiles /silent "$pluginsdir\\aid-runtime-stack-out\\aidirector\\common" '
        '"$localappdata\\aidirector"'
    ) not in low:
        raise RuntimeError("Runtime-stack is not the sole installer owner of AIDirector/Common.")
    if integration_uninstaller_name.casefold() not in low:
        raise RuntimeError("Generated parent uninstall macro is not bound to the active Integration uninstaller filename.")
    if "remove davinci resolve ai director resolve integration.exe" in low:
        raise RuntimeError("Obsolete Integration uninstaller filename remains in generated parent uninstall macro.")
    if "bypass-file" in low:
        raise RuntimeError("Malformed PowerShell Bypass-File token remains in generated NSIS.")

    residual = [
        token for token in FORBIDDEN_LEGACY_MIGRATION_TOKENS
        if token.casefold() in low
    ]
    if residual:
        raise RuntimeError(f"Legacy migration machinery remains in generated NSIS: {residual}")


def install_successor_policy(namespace: dict, builder_root: Path) -> None:
    legacy_make = namespace.get("make_nsis_include")
    legacy_validate = namespace.get("validate_nsis_include")
    if not callable(legacy_make) or not callable(legacy_validate):
        raise RuntimeError("Expected make_nsis_include / validate_nsis_include functions are unavailable.")

    _validate_cleanup_helper(builder_root)
    _validate_compat_asset_helper(builder_root)

    integration_product_name = str(namespace.get("AI_DIRECTOR_INTEGRATION_PRODUCT_NAME") or "")
    integration_uninstaller_name = str(namespace.get("RESOLVE_LAUNCHER_UNINSTALLER_NAME") or "")
    expected_integration_uninstaller_name = f"Remove {integration_product_name}.exe"
    if not integration_product_name or integration_uninstaller_name != expected_integration_uninstaller_name:
        raise RuntimeError(
            "Successor uninstall policy is not bound to the active Integration public naming contract."
        )
    if "/" in integration_uninstaller_name or "\\" in integration_uninstaller_name:
        raise RuntimeError("Unsafe Integration uninstaller filename in active naming contract.")

    def make_nsis_include_successor(*args, **kwargs):
        _assert_accepted_runtime_base(builder_root, args, kwargs)
        text = legacy_make(*args, **kwargs)
        out = transform_nsis_include(text, builder_root, integration_uninstaller_name)
        validate_successor_nsis(out, integration_uninstaller_name)
        return out

    def validate_nsis_include_successor(text: str, *args, **kwargs):
        # The replacement uninstall macro deliberately retains the accepted
        # update-preservation wording, so the inherited independent validator can
        # run normally. No exception-message whitelist is used.
        legacy_validate(text, *args, **kwargs)
        validate_successor_nsis(text, integration_uninstaller_name)

    namespace["make_nsis_include"] = make_nsis_include_successor
    namespace["validate_nsis_include"] = validate_nsis_include_successor
