#!/usr/bin/env python3
from __future__ import annotations
import argparse, hashlib, json, os, shutil, subprocess, tarfile, tempfile
from pathlib import Path, PurePosixPath

SCRIPT_ROOT = Path(__file__).resolve().parent
CONTRACT = SCRIPT_ROOT / 'AI-Director-Upstream-Source-Build-Contract-v2.json'
TREE_MANIFEST = SCRIPT_ROOT / 'AI-Director-Upstream-Source-Tree-Manifest-v1.json'
NORMALIZATION = SCRIPT_ROOT / 'normalization'

def req(v,m):
    if not v: raise RuntimeError(m)
def sha256(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(4*1024*1024),b''): h.update(b)
    return h.hexdigest().upper()
def blobsha_bytes(data:bytes):
    h=hashlib.sha1(); h.update(f'blob {len(data)}\0'.encode('ascii')); h.update(data); return h.hexdigest()
def readj(p): return json.loads(Path(p).read_text(encoding='utf-8-sig'))
def safe_extract(tf:tarfile.TarFile,dest:Path):
    root=dest.resolve()
    members=tf.getmembers()
    for m in members:
        name=m.name.replace('\\','/')
        pp=PurePosixPath(name)
        req(not pp.is_absolute() and '..' not in pp.parts, f'unsafe tar path: {name}')
        req(not (m.issym() or m.islnk() or m.isdev()), f'unsupported tar member type: {name}')
        target=(dest / Path(*pp.parts)).resolve()
        req(target==root or root in target.parents, f'tar escape: {name}')
    tf.extractall(dest,members=members)

def verify_tree(root:Path, manifest:dict):
    rows=manifest['files']; expected={r['path']:r for r in rows}
    actual={p.relative_to(root).as_posix():p for p in root.rglob('*') if p.is_file()}
    req(set(actual)==set(expected), f'source leaf set mismatch missing={sorted(set(expected)-set(actual))[:20]} extra={sorted(set(actual)-set(expected))[:20]}')
    for rel,row in expected.items():
        data=actual[rel].read_bytes()
        req(blobsha_bytes(data)==row['blob_sha1'], f'blob mismatch {rel}')
        req(len(data)==int(row['bytes']), f'byte-size mismatch {rel}')
    return len(rows)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('--source-archive',required=True)
    ap.add_argument('--output',required=True)
    a=ap.parse_args()
    contract=readj(CONTRACT); tm=readj(TREE_MANIFEST)
    arc=Path(a.source_archive); out=Path(a.output)
    pub=contract['public_source_acquisition']
    req(arc.is_file(),'source archive missing')
    req(arc.stat().st_size==int(pub['asset_size']),'source archive size mismatch')
    req(sha256(arc)==pub['asset_sha256'],'source archive SHA256 mismatch')
    req(tm['accepted_source_tree']==contract['authority']['accepted_source_tree'],'tree manifest contract mismatch')
    req(int(tm['file_count'])==3656,'tree manifest count mismatch')
    req(not out.exists(),f'output already exists: {out}')
    stage=Path(str(out)+'.staging')
    if stage.exists(): shutil.rmtree(stage)
    stage.mkdir(parents=True)
    try:
        with tarfile.open(arc,'r:gz') as tf: safe_extract(tf,stage)
        # Accept either rootless archive or one wrapping directory, but nothing ambiguous.
        expected_probe='CMakeLists.txt'
        source=stage
        if not (source/expected_probe).is_file():
            children=[p for p in stage.iterdir() if p.is_dir()]
            files=[p for p in stage.iterdir() if p.is_file()]
            req(len(children)==1 and not files and (children[0]/expected_probe).is_file(),'unexpected source archive root layout')
            wrapped=children[0]
            tmp=Path(str(stage)+'.flat')
            if tmp.exists(): shutil.rmtree(tmp)
            wrapped.rename(tmp)
            stage.rmdir(); tmp.rename(stage); source=stage
        for row in contract['public_source_acquisition']['normalization']:
            rel=row['path']; src=NORMALIZATION / Path(*PurePosixPath(rel).parts); dst=source / Path(*PurePosixPath(rel).parts)
            req(src.is_file(),f'normalization leaf missing: {rel}')
            data=src.read_bytes()
            req(len(data)==int(row['bytes']),f'normalization size mismatch: {rel}')
            req(blobsha_bytes(data)==row['sha'],f'normalization blob mismatch: {rel}')
            dst.parent.mkdir(parents=True,exist_ok=True); dst.write_bytes(data)
        n=verify_tree(source,tm)
        bi=source/'cmake'/'build-info.cmake'
        req(sha256(bi)==contract['build_stamp_materialization']['generic_build_info_sha256'],'generic build-info SHA mismatch after reconstruction')
        req(not any(p.name=='.git' for p in source.rglob('.git')),'reconstructed source contains .git')
        source.rename(out)
    except Exception:
        if stage.exists(): shutil.rmtree(stage,ignore_errors=True)
        raise
    report={'schema_version':1,'result':'PASS','source_archive_sha256':sha256(arc),'accepted_source_tree':tm['accepted_source_tree'],'verified_leaf_count':n,'output':str(out)}
    rp=out.parent/'AI-Director-Upstream-Source-Reconstruction-v1.json'
    rp.write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
    print('UPSTREAM_SOURCE_RECONSTRUCTION=PASS')
    print(f'ACCEPTED_SOURCE_TREE={tm["accepted_source_tree"]}')
    print(f'VERIFIED_SOURCE_LEAVES={n}')
    print(f'OUTPUT={out}')
if __name__=='__main__': main()
