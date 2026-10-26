#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, os, shutil, subprocess, tempfile, uuid
from pathlib import Path

SCRIPT_ROOT=Path(__file__).resolve().parent
DEFAULT_CONTRACT=SCRIPT_ROOT/'AI-Director-Direct-Source-Build-Contract-v1.json'
CONTRACT_SHA256='A9AB28E0E6068F161206CE98425378337609A822D6DDD18A813803969352F8BC'
CLEAN=('CL','_CL_','NVCC_PREPEND_FLAGS','NVCC_APPEND_FLAGS','CUDAARCHS','CMAKE_CUDA_ARCHITECTURES')

def req(v,m):
    if not v: raise RuntimeError(m)
def sha256(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(4*1024*1024),b''): h.update(b)
    return h.hexdigest().upper()
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
def git(root,*args):
    rc,o=run(['git','-C',root,*args],timeout=120); req(rc==0,f'git failed {args}: {o}'); return o.strip()
def vcenv(c):
    vc=Path(c['toolchain']['tools']['vcvars64.bat']['path']); req(vc.is_file(),'vcvars missing')
    w=Path(tempfile.gettempdir())/f'aid-direct-vcvars-{uuid.uuid4().hex}.cmd'
    w.write_text('@echo off\r\n'+f'call "{vc}" -vcvars_ver=14.44 >nul\r\n'+'if errorlevel 1 exit /b %errorlevel%\r\nset\r\n',encoding='ascii',newline='')
    try: rc,out=run(['cmd.exe','/d','/c',w],timeout=120)
    finally: w.unlink(missing_ok=True)
    req(rc==0,'vcvars failed'); env=dict(os.environ)
    for line in out.splitlines():
        if '=' in line:
            k,v=line.split('=',1); env[k]=v
    for k in CLEAN: env.pop(k,None)
    cuda=c['environment']['required_set']['CUDA_PATH']; nvcc=c['environment']['required_set']['CUDACXX']
    env['CUDA_PATH']=cuda; env['CUDA_HOME']=cuda; env['CUDA_PATH_V13_3']=cuda; env['CUDACXX']=nvcc
    cmake=Path(c['toolchain']['tools']['cmake.exe']['path']); ninja=Path(c['toolchain']['tools']['ninja.exe']['path'])
    env['PATH']=os.pathsep.join([str(cmake.parent),str(ninja.parent),str(Path(nvcc).parent),env.get('PATH','')])
    return env
def verify_tools(c):
    for name,row in c['toolchain']['tools'].items():
        p=Path(row['path']); req(p.is_file(),f'missing tool {name}: {p}'); req(sha256(p)==row['sha256'],f'tool SHA mismatch {name}')
    env=vcenv(c)
    for name in ['cl.exe','link.exe','lib.exe','rc.exe','mt.exe','cmake.exe','ninja.exe','nvcc.exe']:
        rc,out=run(['where.exe',name],env=env,timeout=30); req(rc==0 and out.strip(),f'where failed {name}')
        got=Path(out.splitlines()[0].strip()); exp=Path(c['toolchain']['tools'][name]['path'])
        req(os.path.normcase(str(got))==os.path.normcase(str(exp)),f'tool resolution mismatch {name}: {got}')
    rc,out=run(['where.exe','ccache.exe'],env=env,timeout=30); req(rc!=0 or not out.strip(),f'ccache executable must be absent: {out.strip()}')
    return env
def parse_cache(p):
    out={}
    for line in p.read_text(encoding='utf-8',errors='replace').splitlines():
        if not line or line.startswith('//') or line.startswith('#') or '=' not in line or ':' not in line.split('=',1)[0]: continue
        kt,val=line.split('=',1); key,typ=kt.split(':',1); out[key]={'type':typ,'value':val}
    return out
def same_or_child(candidate,parent):
    try: Path(candidate).resolve().relative_to(Path(parent).resolve()); return True
    except ValueError: return Path(candidate).resolve()==Path(parent).resolve()

def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--source-root',required=True); ap.add_argument('--work-root',required=True); ap.add_argument('--output-root',required=True); ap.add_argument('--contract',default=str(DEFAULT_CONTRACT)); ap.add_argument('--jobs',type=int,default=max(1,os.cpu_count() or 1)); a=ap.parse_args()
    contract_path=Path(a.contract); req(contract_path.is_file(),'contract missing'); req(sha256(contract_path)==CONTRACT_SHA256,'contract SHA mismatch'); c=readj(contract_path)
    source=Path(a.source_root).resolve(); work=Path(a.work_root).resolve(); output=Path(a.output_root).resolve()
    req((source/'CMakeLists.txt').is_file(),'Direct source root invalid'); req((source/'.git').exists(),'Direct source must be an exact Git checkout so immutable commit/tree can be verified')
    sa=c['source_authority']; head=git(source,'rev-parse','HEAD'); tree=git(source,'rev-parse','HEAD^{tree}'); status=git(source,'status','--porcelain=v1','--untracked-files=all'); rev_count=git(source,'rev-list','--count','HEAD')
    req(head==sa['accepted_commit'],f'Direct HEAD mismatch: {head}'); req(tree==sa['accepted_tree'],f'Direct tree mismatch: {tree}'); req(status=='',f'Direct source checkout dirty: {status}'); req(int(rev_count)==int(sa['accepted_rev_count']),f'Direct revision count mismatch: {rev_count}')
    req(not work.exists(),f'work root must not exist: {work}'); req(not output.exists(),f'output root must not exist: {output}'); req(not same_or_child(work,source) and not same_or_child(output,source),'work/output must be outside Direct checkout')
    build=work/'b'; shipping=output/'shipping'; logs=output/'logs'; build.mkdir(parents=True); shipping.mkdir(parents=True); logs.mkdir(parents=True)
    representative=build/'CMakeFiles'/'CMakeScratch'/'TryCompile-XXXXXXXX'/'CMakeFiles'/'cmTC_XXXXXXXX.dir'/'Debug'/'cmTC_XXXXXXXX.obj'; req(len(str(representative))<220,f'work root violates conservative path limit: {len(str(representative))}')
    env=verify_tools(c)
    for k in c['environment']['required_absent']: req(not env.get(k),f'forbidden compiler injection variable present after sanitization: {k}')
    t=c['toolchain']['tools']; cmake=Path(t['cmake.exe']['path']); ninja=Path(t['ninja.exe']['path']); cl=Path(t['cl.exe']['path']); nvcc=Path(t['nvcc.exe']['path']); rc=Path(t['rc.exe']['path'])
    args=[str(cmake),'-S',source.as_posix(),'-B',build.as_posix(),'-G','Ninja',f'-DCMAKE_MAKE_PROGRAM:FILEPATH={ninja.as_posix()}',f'-DCMAKE_C_COMPILER:FILEPATH={cl.as_posix()}',f'-DCMAKE_CXX_COMPILER:FILEPATH={cl.as_posix()}',f'-DCMAKE_CUDA_COMPILER:FILEPATH={nvcc.as_posix()}',f'-DCMAKE_RC_COMPILER:FILEPATH={rc.as_posix()}']
    for k,v in c['configure']['cache'].items(): args.append(f'-D{k}={v}')
    req(not any('CMAKE_CUDA_ARCHITECTURES=' in x for x in args),'CMAKE_CUDA_ARCHITECTURES override forbidden')
    rc1=logged(args,logs/'configure.log',cwd=source,env=env); req(rc1==0,'Direct configure failed')
    cache=parse_cache(build/'CMakeCache.txt')
    for k,v in c['configure']['expected_cache_after_configure'].items(): req(k in cache and cache[k]['value']==v,f'Direct cache mismatch {k} expected={v} actual={cache.get(k)}')
    for k in c['configure']['must_be_absent_from_cache']: req(k not in cache or not cache[k]['value'],f'forbidden cache override present: {k}={cache.get(k,{}).get("value","")}')
    ui=build/'tools'/'ui'/'dist'; req(not ui.exists() or not any(p.is_file() for p in ui.rglob('*')),'unexpected UI assets generated')
    rc2=logged([str(cmake),'--build',build.as_posix(),'--parallel',str(a.jobs)],logs/'build.log',cwd=source,env=env); req(rc2==0,'Direct build failed')
    binroot=build/'bin'; req(binroot.is_dir(),'Direct build bin root missing')
    records=[]; accepted_matches=0; expected={r['name']:r for r in c['shipping_set']}
    for name,row in expected.items():
        matches=[p for p in binroot.rglob(name) if p.is_file() and p.name==name]; req(len(matches)==1,f'expected exactly one Direct output {name}, got {len(matches)}')
        dst=shipping/name; shutil.copy2(matches[0],dst); h=sha256(dst); match=h==row['accepted_historical_sha256']; accepted_matches+=int(match); records.append({'name':name,'bytes':dst.stat().st_size,'sha256':h,'accepted_historical_sha256':row['accepted_historical_sha256'],'accepted_historical_match':match})
    actual={p.name for p in shipping.iterdir() if p.is_file()}; req(actual==set(expected),f'Direct shipping set mismatch: {sorted(actual^set(expected))}')
    report={'schema':'ai-director-direct-source-build-result/v1','result':'PASS','official_accepted_runtime_replacement_authorized':False,'contract_sha256':CONTRACT_SHA256,'source':{'repository':sa['repository'],'head':head,'tree':tree,'worktree_clean':True},'shipping_files':records,'accepted_historical_hash_matches':accepted_matches,'accepted_historical_hash_total':len(records),'identity_interpretation':'Source-built Direct output is a candidate identity until separately accepted; historical hashes remain release authority.'}
    rp=output/'AI-Director-Direct-Source-Build-Result-v1.json'; rp.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
    print('DIRECT_SOURCE_BUILD=PASS'); print(f'SOURCE_HEAD={head}'); print(f'SOURCE_TREE={tree}'); print(f'SHIPPING_FILES={len(records)}'); print(f'ACCEPTED_HISTORICAL_HASH_MATCHES={accepted_matches}/{len(records)}'); print(f'OUTPUT={shipping}'); print(f'REPORT={rp}')
if __name__=='__main__': main()
