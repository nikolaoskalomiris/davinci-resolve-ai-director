from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import zipfile
from pathlib import Path

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[2]
STATE_PATH = ROOT / "build" / "package" / "release-state.json"
PUBLIC_STATE_PATH = ROOT / "build" / "package" / "public-repository-state.json"
APP_ROOT = ROOT / "src" / "application"
APP_MANIFEST = ROOT / "provenance" / "application" / "CANONICAL-SOURCE-MANIFEST.json"

EXPECTED_FIXED = {
    "build/direct/AI-Director-Direct-Source-Build-Contract-v1.json": "A9AB28E0E6068F161206CE98425378337609A822D6DDD18A813803969352F8BC",
    "build/direct/build_direct.py": "E44BAD3A1A278ED917AA117E05F6DB57D4B71F242AB9877DB29CD94D03A7E7D7",
    "build/direct/verify_direct_shipping_set.py": "16398A9A8587E81DB14849BE93E29091AB8B7ED972BA7B4CC1D5A75068133B6E",
    "build/upstream/AI-Director-Upstream-Source-Build-Contract-v2.json": "4E1B55ED7A95153D9BF3368C34FF5BAC98D994395E7369D924E7E668D5B0F1AA",
    "build/upstream/AI-Director-Upstream-Source-Tree-Manifest-v1.json": "BA63DE7FB74C287408C009EB13277418C726C6B6D635A6C2FB5CF7C408A3E5A5",
    "build/upstream/build_upstream.py": "61D95CBA4E6149353DE3EB63F872F21C85550F5E61F739A93D0A02B7905E7127",
    "build/upstream/reconstruct_source.py": "E269528EB96403BC1C7CA7CED62EC383E26E3DC97663CB8D4B36727483C9DE2D",
    "provenance/direct/AI-Director-Direct-Provenance-v1.json": "B597B7534E5291C8333A737248680056234712BE43CBD626D25685E2596B0EB3",
    "provenance/upstream/AI-Director-Upstream-Provenance-v1.json": "6BB550BDBCE28F1CEB1C3A8CC7F451FE804C456E31480093B99CB8F6BEFD5AF0",
    "provenance/runtime/runtime-base/RUNTIME-BASE.json": "85582421F420467E92E4914B35E0736BFFBD74C8CA3147F47BB6B4D06C0C16C1",
    "provenance/runtime/runtime-base/RUNTIME-BASE-MANIFEST.json": "D1EF384AE53AB4C7ED58FBB4A16047ED4428647DFF3854363C1CC92D15D4EA7E",
    "provenance/runtime/runtime-base/SHIPPING-INVENTORY.json": "A07A72CA71EF048A1AE894E3792CCE1D3521301743BB8F48E62218F5D798869F",
    "provenance/runtime/runtime-stack/RUNTIME-STACK.json": "872EF78E88D71E80332CEABEA685C8317F9F049669936C2C4A353B044E754E34",
    "provenance/runtime/runtime-stack/RUNTIME-STACK-MANIFEST.json": "AA04F057CA1B8788BB759DE23CFFD3B7CE65D6BA2F38B2D55C35A9BEF56EBA51",
    "branding/BRANDING.json": "0419B6BFA46B7DE1FF6A828A78A4C49B7DB819411A72A3A5867957E7A29A848B",
    "branding/BRANDING-MANIFEST.json": "FAA82500EA1FE467D70F65B68699E50FDD6ED13A8B85C653B70D693F122C348C",
    "installer/policies/Unified-Optional-Resolve-Integration-v1.3/POLICY.json": "7DDC3C4935DCAB70665C90BA5F475D31C9B11FACA5844218F3D310B9B74281FA",
    "runtime/support/Remove-AIDirectorManagedState-v1.ps1": "A781B5B6F290A0CD3EE722625D5F89B28D341A7A017C6533EEF5FAE493E45976",
    "runtime/support/Generate-AIDirectorRuntimePaths.ps1": "73404AF0C1CD248821D298107A4485D42FB1D8DD9FCABF78AB358703D26DC066",
    "installer/validators/Verify-AIDirectorRuntimeBaseNsis7zParity.py": "4FCAE5D987A5FC4102849EA2C37B66906F589F42AD30C5DAEAC940D4125786B7",
}

RUNTIME_PUBLICATION = {
    "src/runtime-backend/config/vfx_runtime.json": "819376D4BF391176281D25E974BC18D0045BE64195BDFAA84A043E099E30CCAA",
    "src/runtime-backend/prompts/VFXDirector.txt": "F2717170396EF3E90702B33D7503EB4D66F2DB135B3CAA70BDA1A54D58F0BA10",
    "src/runtime-backend/ResolveVFXHost.py": "C0C26A6029229CD1D2C4F12B8382960D1271DC62152C5582E9457BD28EEDFEF1",
    "src/runtime-backend/StartVFX.py": "DB2C06C5625BCE154FCB5ABC1AE718063757076FFD87C1E9A2A26BAC61BBD5BA",
    "src/runtime-backend/VFXRuntime.py": "0C63A9010C5DD7B8BF0245C4F836162414DDF2B3CD655773921BF68156081C8C",
    "src/runtime-backend/MCP/vfx_mcp.template.json": "B1927C2C5D7468811A467C4264DE3F40AA05C5E9DA0D1C217C16C86A5189A64D",
    "provenance/runtime/manifests/direct-c8f321699.json": "26B20C378270E2C2A02097DD37A66E3CFBDBE691AADC2DBF03FD7021409A1CB2",
    "provenance/runtime/manifests/MCP-ADVANCED-NODE-DEPENDENCY-IMAGE-4.8.20.json": "785060B9D567F123E0685B3DDC518C4B2E88CE15FE355947BDCB4ECD316DCAE3",
    "provenance/runtime/manifests/MCP-ADVANCED-NODE-DEPENDENCY-IMAGE-4.15.3.json": "5F6A6CE58F7D8B9F96A2FC4FBDDE42E26A8E6538B4D590C1980700656C9AF9BD",
    "provenance/runtime/manifests/MCP-ADVANCED-NODE-DEPENDENCY-IMAGE-PROVENANCE-4.15.3.json": "165AC34CC84ACEEFCF8125E4832A80D850ECEA1FB90B986300DEA77616DA990C",
    "provenance/runtime/manifests/MCP-ADVANCED-NODE-NATIVE-REPRODUCIBILITY-4.15.3.json": "94ACAD418CB1698029EF69955FD2EBCAD503177DEAC2CBC633B7B3DF64B590F1",
    "provenance/runtime/manifests/MCP-COMPATIBILITY-4.10.4.json": "EC5EEF78244B01B8348FE4DC220DF4568730D7523C40DF1233A413F57BD1E5F9",
    "provenance/runtime/manifests/MCP-COMPATIBILITY-CONTRACT-4.10.4.json": "3ED68C583E5DB9CA148A28C64C64F5459C6B3CDC7A4915BAE016262217D33765",
    "provenance/runtime/manifests/MCP-DEPENDENCY-REUSE-4.10.4.json": "32F67966B54D516590BCD6A6CBFE5135CBDE72B5512C21FFC7751FD1F164BD74",
    "provenance/runtime/manifests/MCP-COMPATIBILITY-4.15.3.json": "6D0E91F0E6100CFEB6B074E08007040687E85877601EA3BA60178DB7F3655587",
    "provenance/runtime/manifests/MCP-COMPATIBILITY-CONTRACT-4.15.3.json": "57ECECA939B23F5E44D9A78909074159DEFACAA171DAED6B94E58BC6370AB95C",
    "provenance/runtime/manifests/MCP-DEPENDENCY-REUSE-4.15.3.json": "0A4C9714433CD702C26F9BC48760794C5E4C3D7494C304BBC16CFC00FC93A08E",
    "provenance/runtime/manifests/MCP-PYTHON-IMMUTABLE-ARTIFACT-MANIFEST-4.8.20.json": "C60DC63EA0C155276EA3E3261569782161DA08440A947DEF1425E4D6ACA6DF70",
    "provenance/runtime/manifests/MCP-PYTHON-RUNTIME-MANIFEST.json": "0626E8D266333115A8C2D7BCF3C14FD38DC122D265D6CD2FB4972DFB58E789D1",
    "provenance/runtime/manifests/MCP-UPDATE-STATE.json": "6C43814639E56084A3EC36B29D5C91CD39F786794A006B7FACEEEBCC4C802945",
    "provenance/runtime/manifests/NODE-RUNTIME-MANIFEST.json": "15616CF3583B8DA4FB40DE8F9C23286E6826ED698733973675E5B01877A72807",
    "provenance/runtime/manifests/python-3.11.9-installed-files.json": "F9CEED0AC915EB470260F6977BA9AF2D1786B598CEEB3D1487C8E75BF46A694C",
    "provenance/runtime/manifests/python-3.11.9.json": "40FA93575F42FAB78C1134067542256932DE3D7055BE1DE3387D205A1456859D",
    "provenance/runtime/manifests/RELEASE-PAYLOAD-MANIFEST-identity-v1.json": "91B9455A07D9C0C7B004CFCBEBE2114B77E805F2DB389E66F67B17BBDF04BEBE",
    "provenance/runtime/licenses/AdvancedMCP/THIRD-PARTY-PACKAGES-4.8.20.json": "935426A1E81FB50DB989C1ECE8005CEE23059E69692B4E5285D59BB4AF69FF75",
    "provenance/runtime/licenses/AdvancedMCP/THIRD-PARTY-PACKAGES-4.15.3.json": "22F1B0E06BFB32773837594C6EBB202E64CD6EA6E0C1A9913427D0BADFEB51B8",
    "provenance/runtime/licenses/FFmpeg/REDISTRIBUTION-ENGINEERING-NOTICE-8.1.3.txt": "4CA97B6986D2135B9161A189EDFB23E8AC2819B58C58909EDDF15EFB1DF1AA79",
    "provenance/runtime/licenses/Python/THIRD-PARTY-NOTICES.txt": "DB9ED823A6FC0BD345B0FA91D0697D0FBDE34A19A2A326D20AD2F54484CA8D14",
}

CONTROL_PATHS = {
    "build_installer.py": ROOT / "installer" / "build_installer.py",
    "authoritative_build.py": ROOT / "build" / "package" / "authoritative_build.py",
    "acceptance_control.py": ROOT / "build" / "package" / "acceptance_control.py",
    "check_state.py": ROOT / "build" / "package" / "check_state.py",
    "runtime_base_control.py": ROOT / "runtime" / "runtime_base_control.py",
    "successor_policy.py": ROOT / "installer" / "successor_policy.py",
    "support/Remove-AIDirectorManagedState-v1.ps1": ROOT / "runtime" / "support" / "Remove-AIDirectorManagedState-v1.ps1",
    "support/Generate-AIDirectorRuntimePaths.ps1": ROOT / "runtime" / "support" / "Generate-AIDirectorRuntimePaths.ps1",
    "support/Install-AIDirectorMcpCompatibilityAssets-v1.ps1": ROOT / "runtime" / "support" / "Install-AIDirectorMcpCompatibilityAssets-v1.ps1",
    "support/Verify-AIDirectorRuntimeBaseNsis7zParity.py": ROOT / "installer" / "validators" / "Verify-AIDirectorRuntimeBaseNsis7zParity.py",
    "version_control.py": ROOT / "build" / "package" / "version_control.py",
    "build/system-toolchain/verify_system_toolchain.py": ROOT / "build" / "system-toolchain" / "verify_system_toolchain.py",
    "BUILD.cmd": ROOT / "BUILD.cmd",
    "CHECK-STATE.cmd": ROOT / "CHECK-STATE.cmd",
    "VERSION.cmd": ROOT / "VERSION.cmd",
}

def require(cond: bool, msg: str) -> None:
    if not cond:
        raise RuntimeError(msg)

def sha256(path: Path) -> str:
    h=hashlib.sha256()
    with path.open('rb') as f:
        for b in iter(lambda:f.read(4*1024*1024),b''): h.update(b)
    return h.hexdigest().upper()

def read_json(path: Path):
    return json.loads(path.read_text(encoding='utf-8-sig'))

def semver(s: str):
    m=re.fullmatch(r'(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)',str(s or ''))
    require(m is not None,f'Invalid semantic version: {s!r}')
    return tuple(map(int,m.groups()))

def verify_hash(rel: str, expected: str) -> None:
    p=ROOT/Path(rel)
    require(p.is_file(),f'Missing bound file: {rel}')
    require(sha256(p)==expected,f'Hash mismatch: {rel}')

def validate_operation_state():
    cache=ROOT/'_cache'
    lock=cache/'.builder-operation.lock'
    expected_op=str(os.environ.get('AI_DIRECTOR_EXPECT_OPERATION') or '')
    expected_pid=str(os.environ.get('AI_DIRECTOR_EXPECT_OPERATION_PID') or '')
    if lock.exists():
        require(expected_op and expected_pid,'Unexpected Builder operation lock exists')
        opf=lock/'operation.json'
        require(opf.is_file(),'Operation lock metadata missing')
        obj=read_json(opf)
        require(str(obj.get('operation') or '')==expected_op,'Operation lock kind mismatch')
        require(str(obj.get('pid') or '')==expected_pid,'Operation lock PID mismatch')
    else:
        require(not expected_op and not expected_pid,'Expected operation lock is absent')
    txs=[cache/'.version-preparation-transaction',cache/'.acceptance-promotion-transaction']
    for tx in txs:
        if tx.exists():
            require(bool(expected_op),f'Unexpected transaction residue: {tx.name}')

def validate_state():
    require(STATE_PATH.is_file(),'release-state.json missing')
    state=read_json(STATE_PATH)
    require(state.get('schema_version')==5,'release-state schema mismatch')
    require(state.get('product')=='DaVinci Resolve AI Director','product mismatch')
    require(state.get('repository_mode')=='PUBLIC_SOURCE_REPOSITORY_V1','repository mode mismatch')
    accepted=semver(state.get('live_accepted_authority'))
    stable=semver(state.get('stable_version'))
    target=semver(state.get('target_version'))
    require(stable==accepted,'stable authority mismatch')
    mode=state.get('state_mode')
    require(mode in ('ACCEPTED_READY','TARGET_READY'),'unsupported version state')
    if mode=='ACCEPTED_READY': require(target==accepted,'ACCEPTED_READY target mismatch')
    else: require(target>accepted,'TARGET_READY target must be newer')
    canonical=state.get('canonical_application') or {}
    require(canonical.get('source_dir')=='src/application','canonical source path mismatch')
    require(canonical.get('manifest_path')=='provenance/application/CANONICAL-SOURCE-MANIFEST.json','canonical manifest path mismatch')
    require(sha256(APP_MANIFEST)==str(canonical.get('manifest_sha256') or '').upper(),'canonical manifest binding mismatch')
    bindings=state.get('control_bindings') or {}
    for key,path in CONTROL_PATHS.items():
        require(path.is_file(),f'Control missing: {key}')
        require(str(bindings.get(key) or '').upper()==sha256(path),f'Control binding mismatch: {key}')
    require(state.get('builder_control_sha256')==sha256(CONTROL_PATHS['build_installer.py']),'builder core binding mismatch')
    require(state.get('build_controller_sha256')==sha256(CONTROL_PATHS['authoritative_build.py']),'build controller binding mismatch')
    return state

def validate_application(state):
    m=read_json(APP_MANIFEST)
    require(m.get('schema_version')==2 and m.get('product')=='DaVinci Resolve AI Director','application manifest identity mismatch')
    require(m.get('version')==state.get('target_version'),'application manifest version mismatch')
    require(m.get('source_phase')==state.get('state_mode'),'application source phase mismatch')
    rows=m.get('files') or []
    require(len(rows)==13 and m.get('file_count')==13,'application manifest count mismatch')
    expected=set()
    for row in rows:
        rel=str(row.get('path') or '').replace('\\','/')
        require(rel and '..' not in Path(rel).parts,'unsafe application path')
        p=APP_ROOT/Path(rel)
        require(p.is_file(),f'application source missing: {rel}')
        require(p.stat().st_size==int(row.get('bytes') or -1),f'application size mismatch: {rel}')
        require(sha256(p)==str(row.get('sha256') or '').upper(),f'application hash mismatch: {rel}')
        expected.add(rel.lower())
    actual={p.relative_to(APP_ROOT).as_posix().lower() for p in APP_ROOT.rglob('*') if p.is_file()}
    require(actual==expected,f'application purity mismatch extra={sorted(actual-expected)} missing={sorted(expected-actual)}')

def validate_branding():
    for rel in ('branding/BRANDING.json','branding/BRANDING-MANIFEST.json'): verify_hash(rel,EXPECTED_FIXED[rel])
    m=read_json(ROOT/'branding/BRANDING-MANIFEST.json')
    for section in ('authoring_sources','shipping_assets'):
        for row in m.get(section) or []:
            rel='branding/'+str(row.get('path') or '').replace('\\','/')
            verify_hash(rel,str(row.get('sha256') or '').upper())

def validate_resolve():
    d=ROOT/'src/resolve-integration/RESOLVE-LAUNCHER.json'
    m=ROOT/'src/resolve-integration/RESOLVE-LAUNCHER-MANIFEST.json'
    require(d.is_file() and m.is_file(),'Resolve integration metadata missing')
    state=read_json(STATE_PATH)
    require(sha256(d)==str((state.get('active_resolve_launcher') or {}).get('manifest_sha256') or '').upper(),'Resolve descriptor binding mismatch')
    desc=read_json(d); require(sha256(m)==str(desc.get('source_manifest_sha256') or '').upper(),'Resolve source manifest binding mismatch')
    man=read_json(m)
    for row in man.get('files') or []:
        rel=str(row.get('path') or '')
        verify_hash('src/resolve-integration/'+rel,str(row.get('sha256') or '').upper())

def validate_runtime_publication():
    for rel,sha in RUNTIME_PUBLICATION.items(): verify_hash(rel,sha)
    seed=read_json(ROOT/'provenance/runtime/mcp/MCP-SEED.json')
    require(seed.get('version')=='4.15.3','MCP seed version mismatch')
    require(seed.get('commit')=='931bc2cda8fd9049982a457de9ff70836c406cd7','MCP seed commit mismatch')
    require(int(seed.get('bytes') or -1)==6419447,'MCP seed byte-count mismatch')
    require(str(seed.get('sha256') or '').upper()=='E36B8CB5EB73A3BC2099E7D48E15EA119D6D8411D890651DF17B76BFD3781D5C','MCP seed hash mismatch')

def validate_bootstrap():
    obj=read_json(ROOT/'bootstrap/bootstrap-inputs.json')
    state=read_json(STATE_PATH)
    target_pending=(state.get('state_mode')=='TARGET_READY')
    require(obj.get('schema_version')==1 and len(obj.get('inputs') or [])==9,'bootstrap input contract mismatch')
    require(obj.get('normal_user_manual_toolchain_install_required') is True,'bootstrap must declare external manual system-toolchain prerequisites')
    require(obj.get('system_toolchain_installation_mode')=='EXTERNAL_MACHINE_PREREQUISITES_NOT_AUTO_INSTALLED','bootstrap system-toolchain installation mode mismatch')
    require(obj.get('system_toolchain_validator')=='build/system-toolchain/verify_system_toolchain.py','bootstrap system-toolchain validator mismatch')
    prereq=obj.get('system_toolchain_prerequisites') or {}
    require(prereq.get('platform')=='Windows x64','system-toolchain platform prerequisite mismatch')
    require(prereq.get('msvc_toolset')=='14.44.35207','system-toolchain MSVC prerequisite mismatch')
    require(prereq.get('windows_sdk')=='10.0.26100.0','system-toolchain Windows SDK prerequisite mismatch')
    require(prereq.get('cuda_toolkit')=='13.3','system-toolchain CUDA prerequisite mismatch')
    require(prereq.get('nvcc')=='V13.3.73','system-toolchain nvcc prerequisite mismatch')
    require(prereq.get('automatic_installation') is False,'system-toolchain auto-installation must remain disabled')
    shared_rows={x.get('id'):x for x in obj['inputs'] if str(x.get('id') or '').startswith('nvidia-')}
    require(set(shared_rows)=={'nvidia-cuda-cudart-13.3.1-windows-x86_64','nvidia-libcublas-13.3.1-windows-x86_64'},'shared CUDA bootstrap inputs missing')
    shared_contract=obj.get('shared_cuda_runtime_lane') or {}
    require(shared_contract.get('id')=='CUDA13.3.1-Dual-Shared-v2','shared CUDA runtime lane mismatch')
    require(shared_contract.get('bootstrap_source')=='NVIDIA_OFFICIAL_REDIST_13.3.1','shared CUDA bootstrap source mismatch')
    require(shared_contract.get('release_manifest_url')=='https://developer.download.nvidia.com/compute/cuda/redist/redistrib_13.3.1.json','shared CUDA NVIDIA manifest URL mismatch')
    require(shared_contract.get('installed_root')=='AIDirector/Common/Runtime/CUDA/13.3','shared CUDA installed root mismatch')
    require(shared_contract.get('ordinary_upstream_update_owns_shared_cuda') is False,'Upstream updater must not own shared CUDA')
    require(shared_contract.get('compiler_toolkit_is_shipping_runtime_source') is False,'Compiler Toolkit must not be shipping shared-CUDA source')
    cudart=shared_rows['nvidia-cuda-cudart-13.3.1-windows-x86_64']
    cublas=shared_rows['nvidia-libcublas-13.3.1-windows-x86_64']
    require(cudart.get('url')=='https://developer.download.nvidia.com/compute/cuda/redist/cuda_cudart/windows-x86_64/cuda_cudart-windows-x86_64-13.3.29-archive.zip','cudart public URL mismatch')
    require(int(cudart.get('bytes') or -1)==2589792 and str(cudart.get('sha256') or '').upper()=='1FEB7DD266813FFE8DBC24E115183A5AC35A4795C8D34ACA0DF85AB616B64D9C','cudart archive identity mismatch')
    require(cublas.get('url')=='https://developer.download.nvidia.com/compute/cuda/redist/libcublas/windows-x86_64/libcublas-windows-x86_64-13.6.0.2-archive.zip','cuBLAS public URL mismatch')
    require(int(cublas.get('bytes') or -1)==393706755 and str(cublas.get('sha256') or '').upper()=='62E9FA30560C8F0A28E0CDCF9D6FC1FED347BCFAB8847239B9AE1FDC1D86408A','cuBLAS archive identity mismatch')
    expected_members={
      'cudart64_13.dll':('B00CA6F53699120DA815BF3E06E2E4285FAE2F201235B883DCBB50EEC51E2A2A',551024),
      'cublas64_13.dll':('8C6BAC24474AF29627EC96500025A5D410A1B7E8FFA00E1FE13B1781FC6B3DDC',52697712),
      'cublasLt64_13.dll':('E323ABD89E0F03C1DB91A09D7AEB1928DE08E1F86192CC713B335FEFE3E368A9',463655536),
    }
    actual_members={}
    for row in (cudart,cublas):
        for member in row.get('redistributable_members') or []:
            actual_members[str(member.get('shipping_name') or '')]=(str(member.get('sha256') or '').upper(),int(member.get('bytes') or -1))
    require(actual_members==expected_members,'shared CUDA member identity contract mismatch')
    runtime=[x for x in obj['inputs'] if x.get('id')=='runtime-base-CUDA13-Native-Base-v5']
    require(len(runtime)==1,'runtime bootstrap input missing')
    row=runtime[0]
    require(row.get('destination_file')=='_inputs/Runtime-Bases/CUDA13-Native-Base-v5/RUNTIME-BASE.7z','runtime input destination mismatch')
    expected_url='https://github.com/nikolaoskalomiris/llama-cpp-flashnext-direct/releases/download/builder-inputs-v2/AI-Director-Runtime-Base-CUDA13-Native-Base-v5.7z'
    require(str(row.get('url') or '')==expected_url,'runtime-base candidate/public URL mismatch')
    require(int(row.get('bytes') or -1)==108500102,'runtime-base bootstrap byte-count mismatch')
    require(str(row.get('sha256') or '').upper()=='7AD5B820B68F8CC949B6FF656D7FC0977858E9CBFF41EC241EC5F913317AC46F','runtime-base bootstrap SHA-256 mismatch')
    require('local_source_relative_path' not in row,'engineering _source runtime fallback must not exist')
    require(row.get('asset_root_relative_path')=='AI-Director-Runtime-Base-CUDA13-Native-Base-v5.7z','runtime offline mirror path mismatch')
    if target_pending:
        pending = obj.get('public_runtime_asset_urls_bound') is False
        published = obj.get('public_runtime_asset_urls_bound') is True
        require(pending or published,'TARGET_READY runtime-base publication flag must be boolean')
        if pending:
            require(row.get('publication_status')=='PENDING_EXACT_ACCEPTANCE_PUBLICATION','TARGET_READY pending runtime-base publication status mismatch')
            url_bound=False
        else:
            require(row.get('publication_status')=='PUBLISHED','TARGET_READY published runtime-base publication status mismatch')
            url_bound=True
    else:
        require(obj.get('public_runtime_asset_urls_bound') is True,'accepted public runtime asset URLs must be bound')
        require(row.get('publication_status')=='PUBLISHED','accepted runtime-base publication status mismatch')
        url_bound=True
    archives={
      '_toolchain/Archives/electron-v36.3.2-win32-x64.zip':'5475DC725D50C9CEE12C0D56E1FD093C3BAD75E9DFAFD9753FDDC3A085532A37',
      '_toolchain/Archives/nsis-3.0.4.1.7z':'9877DF902530F96357D13A7A31AE2B9DF67F48B11FFC9A1700A7C961574EC5FA',
      '_toolchain/Archives/nsis-resources-3.4.1.7z':'593A9A92EF958321293AC6A2EE61E64BF1BD543142A5BD6B3D310709CC924103',
      '_toolchain/Archives/7zip-win-x64.tar.gz':'BE071F15BD6DA2F78FE81C6DDEF2009B0C4D8A51F36B780CB806C7E6DF95E1B3',
    }
    generated=True
    for rel,sha in archives.items():
        p=ROOT/rel
        if not p.is_file(): generated=False
        else: require(sha256(p)==sha,f'owned archive mismatch: {rel}')
    py=ROOT/'_toolchain/Python/3.11.9/python.exe'; node=ROOT/'_toolchain/Node/24.18.0/node.exe'
    if not py.is_file() or not node.is_file(): generated=False
    rb=ROOT/'_inputs/Runtime-Bases/CUDA13-Native-Base-v5/RUNTIME-BASE.7z'
    if rb.is_file(): require(rb.stat().st_size==108500102 and sha256(rb)=='7AD5B820B68F8CC949B6FF656D7FC0977858E9CBFF41EC241EC5F913317AC46F','runtime-base input identity mismatch')
    else: generated=False
    shared_archives={
      '_inputs/Shared-CUDA/CUDA13.3.1/Archives/cuda_cudart-windows-x86_64-13.3.29-archive.zip':('1FEB7DD266813FFE8DBC24E115183A5AC35A4795C8D34ACA0DF85AB616B64D9C',2589792),
      '_inputs/Shared-CUDA/CUDA13.3.1/Archives/libcublas-windows-x86_64-13.6.0.2-archive.zip':('62E9FA30560C8F0A28E0CDCF9D6FC1FED347BCFAB8847239B9AE1FDC1D86408A',393706755),
    }
    for rel,(digest,size) in shared_archives.items():
        p=ROOT/rel
        if not p.is_file(): generated=False
        else:
            require(p.stat().st_size==size,f'shared CUDA archive size mismatch: {rel}')
            require(sha256(p)==digest,f'shared CUDA archive hash mismatch: {rel}')
    return generated,url_bound

def validate_public_repository_state():
    require(PUBLIC_STATE_PATH.is_file(),'public-repository-state.json missing')
    obj=read_json(PUBLIC_STATE_PATH)
    state=read_json(STATE_PATH)
    target_pending=(state.get('state_mode')=='TARGET_READY')
    require(obj.get('schema_version')==1,'public repository state schema mismatch')
    require(obj.get('layout')=='PUBLIC_SOURCE_REPOSITORY_V1','public repository layout mismatch')
    require(obj.get('system_toolchain_boundary_resolved') is True,'system-toolchain boundary must be resolved')
    require(obj.get('system_toolchain_policy')=='EXTERNAL_MACHINE_PREREQUISITES_STRICTLY_VALIDATED_NOT_AUTO_INSTALLED','system-toolchain public policy mismatch')
    require(obj.get('system_toolchain_validator')=='build/system-toolchain/verify_system_toolchain.py','public system-toolchain validator mismatch')
    require(obj.get('plain_build_from_accepted_ready_public_semantics')=='CHECKED_OUT_VERSION_NONMUTATING','plain public BUILD semantics mismatch')
    require(obj.get('plain_build_release_state_mutation') is False,'plain public BUILD must not mutate release state')
    require(obj.get('runtime_base_public_url')=='https://github.com/nikolaoskalomiris/llama-cpp-flashnext-direct/releases/download/builder-inputs-v2/AI-Director-Runtime-Base-CUDA13-Native-Base-v5.7z','runtime-base public/candidate state URL mismatch')
    require(str(obj.get('runtime_base_sha256') or '').upper()=='7AD5B820B68F8CC949B6FF656D7FC0977858E9CBFF41EC241EC5F913317AC46F','runtime-base public state SHA-256 mismatch')
    require(int(obj.get('runtime_base_bytes') or -1)==108500102,'runtime-base public state byte-count mismatch')
    if target_pending:
        pending = obj.get('runtime_base_public_url_bound') is False
        published = obj.get('runtime_base_public_url_bound') is True
        require(pending or published,'TARGET_READY runtime-base public URL flag must be boolean')
        if pending:
            require(obj.get('runtime_base_publication_status')=='PENDING_EXACT_ACCEPTANCE_PUBLICATION','TARGET_READY pending runtime-base publication status mismatch')
        else:
            require(obj.get('runtime_base_publication_status')=='PUBLISHED','TARGET_READY published runtime-base publication status mismatch')
    else:
        require(obj.get('runtime_base_public_url_bound') is True,'accepted runtime-base public URL state must be resolved')
        require(obj.get('runtime_base_publication_status')=='PUBLISHED','accepted runtime-base publication status mismatch')
    require(obj.get('shared_cuda_public_source_bound') is True,'shared CUDA public source must be bound')
    require(obj.get('shared_cuda_source')=='NVIDIA_OFFICIAL_REDIST_13.3.1','shared CUDA public source mismatch')
    require(obj.get('shared_cuda_release_manifest_url')=='https://developer.download.nvidia.com/compute/cuda/redist/redistrib_13.3.1.json','shared CUDA release manifest URL mismatch')
    require(obj.get('shared_cuda_compiler_toolkit_is_runtime_source') is False,'machine CUDA Toolkit must not source shipping shared CUDA')
    require(obj.get('shared_cuda_installed_root')=='AIDirector/Common/Runtime/CUDA/13.3','shared CUDA installed root state mismatch')
    require(obj.get('direct_public_readability_verified') is True,'Direct public readability must be verified')
    require(obj.get('direct_repository')=='nikolaoskalomiris/llama-cpp-flashnext-direct','Direct public repository mismatch')
    require(obj.get('direct_accepted_commit')=='c8f321699adbd0035c8c755bdefcb4182705262b','Direct accepted commit mismatch')
    require(obj.get('direct_accepted_tree')=='a17cf64683bc6877e2dbc4e0b4ef8933106257fb','Direct accepted tree mismatch')
    return obj

def main():
    require(ROOT.is_dir(),'repository root missing')
    require(not (ROOT/'_source').exists(),'engineering _source tree must not exist in public repository')
    require(not (ROOT/'.projection-state.json').exists(),'projection-state marker must be retired')
    validate_operation_state()
    state=validate_state()
    validate_application(state)
    for rel,sha in EXPECTED_FIXED.items(): verify_hash(rel,sha)
    validate_branding(); validate_resolve(); validate_runtime_publication()
    public_state=validate_public_repository_state()
    generated,url_bound=validate_bootstrap()
    print('PUBLIC_SOURCE_LAYOUT=PASS')
    print('DOCUMENTATION_INTEGRITY_BOUND=False')
    print('ACTIVE_APPLICATION_OVERLAY_COUNT=0')
    print('HISTORICAL_RUNTIME_STACK_ARCHIVE_REQUIRED=False')
    print('OWNED_TOOLCHAIN=' + ('PASS' if generated else 'ABSENT_BOOTSTRAP_REQUIRED'))
    print('PUBLIC_RUNTIME_ASSET_URL_BOUND=' + ('True' if url_bound else 'False'))
    print('SHARED_CUDA_PUBLIC_SOURCE_BOUND=True')
    print('SHARED_CUDA_BOOTSTRAP_SOURCE=NVIDIA_OFFICIAL_REDIST_13.3.1')
    print('SYSTEM_TOOLCHAIN_BOUNDARY=EXTERNAL_STRICT_VALIDATOR_BOUND')
    print('PLAIN_PUBLIC_BUILD_SEMANTICS=CHECKED_OUT_VERSION_NONMUTATING')
    print('DIRECT_PUBLIC_READABILITY=VERIFIED_ANONYMOUS_P1')
    print('P1_PUBLIC_INPUT_AVAILABILITY=PASS_ACCEPTED_INPUTS')
    print('TARGET_RUNTIME_BASE_PUBLICATION=' + ('PUBLISHED' if url_bound else 'PENDING_EXACT_ACCEPTANCE_PUBLICATION'))
    print('LIVE_ACCEPTED_AUTHORITY=' + str(state.get('live_accepted_authority')))
    print('TARGET_VERSION=' + str(state.get('target_version')))
    print('VERSION_STATE=' + str(state.get('state_mode')))
    print('APPLICATION_SOURCE_AUTHORITY=' + str(state.get('application_source_authority')))
    print('CHECK_STATE_STATUS=PASS')
    if generated and not url_bound:
        builder_state='HEALTHY_TARGET_READY_LOCAL_BUILD_INPUTS_PRESENT_PUBLICATION_PENDING'
    elif generated:
        builder_state='HEALTHY_PUBLIC_SOURCE_BUILD_READY'
    else:
        builder_state='HEALTHY_PUBLIC_SOURCE_CHECKOUT_BOOTSTRAP_REQUIRED'
    print('BUILDER_STATE=' + builder_state)
    return 0

if __name__=='__main__':
    try:
        raise SystemExit(main())
    except Exception as exc:
        print('CHECK_STATE_STATUS=ERROR')
        print('ERROR=' + str(exc))
        raise SystemExit(2)
