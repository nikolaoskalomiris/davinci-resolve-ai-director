#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, os, re, shutil, subprocess, tempfile, uuid
from pathlib import Path

SCRIPT_ROOT=Path(__file__).resolve().parent
DEFAULT_CONTRACT=SCRIPT_ROOT/'AI-Director-Upstream-Source-Build-Contract-v2.json'
TREE_MANIFEST=SCRIPT_ROOT/'AI-Director-Upstream-Source-Tree-Manifest-v1.json'
CLEAN=('CL','_CL_','NVCC_PREPEND_FLAGS','NVCC_APPEND_FLAGS','CUDAARCHS','CMAKE_CUDA_ARCHITECTURES','HTTP_PROXY','HTTPS_PROXY','ALL_PROXY','NO_PROXY')

def req(v,m):
    if not v: raise RuntimeError(m)
def sha256(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(4*1024*1024),b''): h.update(b)
    return h.hexdigest().upper()
def blobsha(data):
    h=hashlib.sha1(); h.update(f'blob {len(data)}\0'.encode()); h.update(data); return h.hexdigest()
def readj(p): return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def run(args,**kw):
    cp=subprocess.run([str(x) for x in args],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf-8',errors='replace',**kw)
    return cp.returncode,cp.stdout
def logged(args,log,**kw):
    Path(log).parent.mkdir(parents=True,exist_ok=True)
    with Path(log).open('w',encoding='utf-8',newline='\n') as f:
        p=subprocess.Popen([str(x) for x in args],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True,encoding='utf-8',errors='replace',bufsize=1,**kw)
        assert p.stdout
        for line in p.stdout:
            print(line,end='',flush=True); f.write(line); f.flush()
        return p.wait()
def verify_tree(root,tm):
    expected={r['path']:r for r in tm['files']}; actual={p.relative_to(root).as_posix():p for p in Path(root).rglob('*') if p.is_file()}
    req(set(actual)==set(expected),'source leaf set mismatch')
    for rel,row in expected.items():
        d=actual[rel].read_bytes(); req(blobsha(d)==row['blob_sha1'],f'source blob mismatch {rel}'); req(len(d)==int(row['bytes']),f'source bytes mismatch {rel}')
def vcenv(c):
    vc=Path(c['toolchain']['tools']['vcvars64.bat']['path']); req(vc.is_file(),'vcvars missing')
    w=Path(tempfile.gettempdir())/f'aid-vcvars-{uuid.uuid4().hex}.cmd'
    w.write_text('@echo off\r\n'+f'call "{vc}" -vcvars_ver=14.44 >nul\r\n'+'if errorlevel 1 exit /b %errorlevel%\r\nset\r\n',encoding='ascii',newline='')
    try: rc,out=run(['cmd.exe','/d','/c',w],timeout=120)
    finally: w.unlink(missing_ok=True)
    req(rc==0,'vcvars failed'); env=dict(os.environ)
    for line in out.splitlines():
        if '=' in line:
            k,v=line.split('=',1); env[k]=v
    for k in CLEAN: env.pop(k,None)
    cuda=c['environment']['required_set']['CUDA_PATH']; nvcc=c['environment']['required_set']['CUDACXX']
    cmake=Path(c['toolchain']['tools']['cmake.exe']['path']); ninja=Path(c['toolchain']['tools']['ninja.exe']['path'])
    env['CUDA_PATH']=cuda; env['CUDA_HOME']=cuda; env['CUDA_PATH_V13_3']=cuda; env['CUDACXX']=nvcc
    env['PATH']=os.pathsep.join([str(cmake.parent),str(ninja.parent),str(Path(nvcc).parent),env.get('PATH','')])
    return env
def verify_tools(c):
    for name,row in c['toolchain']['tools'].items():
        p=Path(row['path']); req(p.is_file(),f'missing tool {name}'); req(sha256(p)==row['sha256'],f'tool SHA mismatch {name}')
    env=vcenv(c)
    for name in ['cl.exe','link.exe','lib.exe','rc.exe','mt.exe','cmake.exe','ninja.exe','nvcc.exe']:
        rc,out=run(['where.exe',name],env=env,timeout=30); req(rc==0 and out.strip(),f'where failed {name}')
        got=Path(out.splitlines()[0].strip()); exp=Path(c['toolchain']['tools'][name]['path'])
        req(os.path.normcase(str(got))==os.path.normcase(str(exp)),f'tool resolution mismatch {name}: {got}')
    return env
def stamp(src,c):
    p=src/'cmake'/'build-info.cmake'; bi=c['build_stamp_materialization']; req(sha256(p)==bi['generic_build_info_sha256'],'generic build-info mismatch')
    text=p.read_text(encoding='utf-8'); req('Compiled by the Unsloth team' not in text,'unexpected fingerprint')
    for op in bi['replace_exactly']:
        req(text.count(op['from'])==1,f'stamp source mismatch {op["from"]}'); text=text.replace(op['from'],op['to'],1)
    p.write_text(text,encoding='utf-8',newline='\n'); req(sha256(p)==bi['stamped_build_info_sha256'],'stamped build-info mismatch')
def dumpbin_path(c): return Path(c['toolchain']['tools']['link.exe']['path']).with_name('dumpbin.exe')
def deps(p,c):
    db=dumpbin_path(c); req(db.is_file(),'dumpbin missing'); rc,out=run([db,'/DEPENDENTS',p],timeout=120); req(rc==0,'dumpbin dependents failed')
    return sorted(set(re.findall(r'(?im)^\s*([A-Za-z0-9_.+\-]+\.dll)\s*$',out)))
def exports(p,c):
    db=dumpbin_path(c); rc,out=run([db,'/EXPORTS',p],timeout=120); req(rc==0,'dumpbin exports failed'); return [ln.strip() for ln in out.splitlines() if re.search(r'SSLServer|SSLClient',ln)]
def cuda_topology(p,c):
    cuda_root=Path(c['environment']['required_set']['CUDA_PATH'])
    cu=cuda_root/'bin'/'cuobjdump.exe'
    req(cu.is_file(),f'cuobjdump missing: {cu}')
    rc,ver=run([cu,'--version'],timeout=30)
    expected_release=f"release {c['toolchain']['cuda_toolkit']}"
    expected_build=c['toolchain']['nvcc']
    req(rc==0 and expected_release in ver and expected_build in ver,f'cuobjdump identity mismatch: {ver.strip()}')
    rc,a=run([cu,'-lelf',p],timeout=180); req(rc==0,'cuobjdump -lelf failed')
    rc,b=run([cu,'-lptx',p],timeout=180); req(rc==0,'cuobjdump -lptx failed')
    sass=sorted(set(re.findall(r'\.sm_([0-9]+a?)\.',a)),key=lambda x:(int(re.match(r'\d+',x).group()),x.endswith('a')))
    ptx=sorted(set(re.findall(r'\.sm_([0-9]+a?)\.',b)),key=lambda x:(int(re.match(r'\d+',x).group()),x.endswith('a')))
    return {'sass':sass,'ptx':ptx,'cuobjdump':{'path':str(cu),'sha256':sha256(cu),'version':ver.strip()}}
def parse_cache(p):
    o={}
    for line in p.read_text(encoding='utf-8',errors='replace').splitlines():
        if not line or line.startswith('//') or line.startswith('#') or '=' not in line or ':' not in line.split('=',1)[0]: continue
        kt,val=line.split('=',1); key,typ=kt.split(':',1); o[key]={'type':typ,'value':val}
    return o

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--source-root',required=True); ap.add_argument('--shared-cuda-root',required=True); ap.add_argument('--output-root',required=True); ap.add_argument('--contract',default=str(DEFAULT_CONTRACT)); ap.add_argument('--jobs',type=int,default=3); a=ap.parse_args()
    contract=readj(a.contract); req(sha256(a.contract)=='4E1B55ED7A95153D9BF3368C34FF5BAC98D994395E7369D924E7E668D5B0F1AA','contract SHA mismatch')
    tm=readj(TREE_MANIFEST); req(tm['accepted_source_tree']==contract['authority']['accepted_source_tree'],'tree manifest mismatch')
    source=Path(a.source_root); req(source.is_dir(),'source root missing'); verify_tree(source,tm); req(not (source/'.git').exists(),'source root must be VCS-free')
    out=Path(a.output_root); req(not out.exists(),f'output root exists: {out}'); out.mkdir(parents=True)
    work=out/'work'; src=work/'src'; build=work/'build'; candidate=out/'candidate'; logs=out/'logs'; shutil.copytree(source,src); candidate.mkdir(); logs.mkdir()
    verify_tree(src,tm); stamp(src,contract); env=verify_tools(contract)
    env['HTTP_PROXY']='http://127.0.0.1:9'; env['HTTPS_PROXY']='http://127.0.0.1:9'; env['ALL_PROXY']='http://127.0.0.1:9'; env['NO_PROXY']=''; env['GIT_ALLOW_PROTOCOL']='file'
    defs=contract['configure']['defines']; req('CMAKE_CUDA_ARCHITECTURES' not in defs and 'CUDAARCHS' not in env,'CUDA arch override detected')
    args=[contract['toolchain']['tools']['cmake.exe']['path'],'-S',str(src),'-B',str(build),'-G','Ninja']+[f'-D{k}={v}' for k,v in defs.items()]
    rc=logged(args,logs/'configure.log',cwd=work,env=env); req(rc==0,f'configure failed rc={rc}')
    cache=parse_cache(build/'CMakeCache.txt'); req(cache.get('LLAMA_OPENSSL',{}).get('value')=='OFF','LLAMA_OPENSSL drift'); req(cache.get('LLAMA_BUILD_BORINGSSL',{}).get('value')=='OFF','BORINGSSL drift'); req(cache.get('GGML_CUDA_CUB_3DOT2',{}).get('value')=='OFF','CUB drift'); req('CMAKE_CUDA_ARCHITECTURES' not in cache or not cache['CMAKE_CUDA_ARCHITECTURES']['value'],'CUDA arch cache override')
    rc=logged([contract['toolchain']['tools']['cmake.exe']['path'],'--build',str(build),'-j',str(a.jobs)],logs/'build.log',cwd=work,env=env); req(rc==0,f'build failed rc={rc}')
    ship=contract['shipping']['allowlist_sha256']; rows=[]
    for name,hist in ship.items():
        hits=[p for p in build.rglob(name) if p.is_file()]; req(len(hits)==1,f'expected one build output {name}, found {len(hits)}'); dst=candidate/name; shutil.copy2(hits[0],dst); rows.append({'name':name,'sha256':sha256(dst),'bytes':dst.stat().st_size,'historical_accepted_sha256':hist})
    marker=contract['shipping']['marker_file']; mb=(json.dumps(contract['shipping']['marker_json'],indent=2,ensure_ascii=False)+'\n').encode('utf-8'); (candidate/marker).write_bytes(mb); req(sha256(candidate/marker)==contract['shipping']['marker_expected_sha256'],'marker mismatch')
    renv=dict(env); shared=Path(a.shared_cuda_root); req(shared.is_dir(),'shared CUDA root missing'); [req((shared/n).is_file(),f'shared CUDA file missing: {n}') for n in ['cudart64_13.dll','cublas64_13.dll','cublasLt64_13.dll']]; renv['PATH']=os.pathsep.join([str(candidate),str(shared),renv.get('PATH','')])
    rc,ver=run([candidate/'llama-server.exe','--version'],cwd=candidate,env=renv,timeout=60); req(rc==0 and contract['build_stamp_materialization']['expected_runtime_version_fragment'] in ver,'server version binding failed')
    dep={n:deps(candidate/n,contract) for n in ['llama-server.exe','llama-server-impl.dll','llama-common.dll']}; crypt={n:any(x.upper()=='CRYPT32.DLL' for x in ds) for n,ds in dep.items()}; ext=sorted({x for ds in dep.values() for x in ds if re.search(r'(?i)(?:^|[-_])(ssl|crypto|boring|libressl)',x)}); sslx=exports(candidate/'llama-server-impl.dll',contract); req(not crypt['llama-server-impl.dll'] and not crypt['llama-common.dll'] and not ext and not sslx,'TLS-less surface gate failed')
    topo=cuda_topology(candidate/'ggml-cuda.dll',contract); req(topo['sass']==contract['source_causal_cuda_policy']['sass'] and topo['ptx']==contract['source_causal_cuda_policy']['ptx'],'CUDA topology mismatch')
    report={'schema_version':1,'test_id':'AI-Director-Upstream-Source-Build-v1','result':'PASS','contract_sha256':sha256(a.contract),'accepted_source_tree':tm['accepted_source_tree'],'candidate':str(candidate),'files':rows,'marker_sha256':sha256(candidate/marker),'version_output':ver,'tls':{'dependencies':dep,'crypt32':crypt,'external_ssl_dlls':ext,'focused_ssl_exports':sslx},'cuda':topo,'historical_byte_identity_required':False,'shared_cuda_root':str(shared),'clean_build_input_policy':'SOURCE_ONLY__NO_PREBUILT_UPSTREAM__NO_INSTALLED_RUNTIME_DEPENDENCY'}
    rp=out/'AI-Director-Upstream-Source-Build-v1.json'; rp.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
    print('AI-Director-Upstream-Source-Build-v1=PASS'); print(f'CANDIDATE={candidate}'); print(f'REPORT={rp}'); print(f'REPORT_SHA256={sha256(rp)}')
if __name__=='__main__': main()
