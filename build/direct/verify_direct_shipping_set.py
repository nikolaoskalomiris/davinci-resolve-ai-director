#!/usr/bin/env python3
import argparse, hashlib, json
from pathlib import Path
SCRIPT_ROOT=Path(__file__).resolve().parent
DEFAULT_CONTRACT=SCRIPT_ROOT/'AI-Director-Direct-Source-Build-Contract-v1.json'
CONTRACT_SHA256='2327DC49A9CDA1A3186AA2C5B8392A96D764AB868E6F99BF0080E11DF37B63A7'
def req(v,m):
    if not v: raise RuntimeError(m)
def sha256(p):
    h=hashlib.sha256()
    with Path(p).open('rb') as f:
        for b in iter(lambda:f.read(4*1024*1024),b''): h.update(b)
    return h.hexdigest().upper()
def main():
    ap=argparse.ArgumentParser(); ap.add_argument('--shipping-dir',required=True); ap.add_argument('--contract',default=str(DEFAULT_CONTRACT)); ap.add_argument('--report'); ap.add_argument('--require-accepted-hashes',action='store_true'); a=ap.parse_args()
    cp=Path(a.contract); req(cp.is_file() and sha256(cp)==CONTRACT_SHA256,'contract identity mismatch'); c=json.loads(cp.read_text(encoding='utf-8-sig')); d=Path(a.shipping_dir); req(d.is_dir(),'shipping directory missing')
    expected={r['name']:r for r in c['shipping_set']}; actual={p.name:p for p in d.iterdir() if p.is_file()}; req(set(actual)==set(expected),f'shipping file set mismatch missing={sorted(set(expected)-set(actual))} extra={sorted(set(actual)-set(expected))}')
    rows=[]; matches=0
    for name in sorted(expected):
        h=sha256(actual[name]); ok=h==expected[name]['accepted_historical_sha256']; matches+=int(ok); rows.append({'name':name,'bytes':actual[name].stat().st_size,'sha256':h,'accepted_historical_sha256':expected[name]['accepted_historical_sha256'],'accepted_historical_match':ok})
    if a.require_accepted_hashes: req(matches==len(rows),f'accepted historical hash mode failed: {matches}/{len(rows)}')
    report={'schema':'ai-director-direct-shipping-verification/v1','result':'PASS','contract_sha256':CONTRACT_SHA256,'file_count':len(rows),'accepted_historical_hash_matches':matches,'files':rows,'official_accepted_replacement_authorized':False}
    if a.report: Path(a.report).write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
    print('DIRECT_SHIPPING_SET=PASS'); print(f'SHIPPING_FILES={len(rows)}'); print(f'ACCEPTED_HISTORICAL_HASH_MATCHES={matches}/{len(rows)}'); print('OFFICIAL_ACCEPTED_REPLACEMENT_AUTHORIZED=NO')
if __name__=='__main__': main()
