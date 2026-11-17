#!/usr/bin/env python3
"""Fail-closed retained-result/package checks. Owner and author: Carlo Corti.

New publication driver, not the historical producer or an independent proof
of its shared zero decomposition. No official census is started. Native smoke
is opt-in and capped at8; historical scalar comparison is capped at18.
"""
from pathlib import Path, PurePosixPath
import argparse
import hashlib
import importlib.util
import itertools
import json
import math
import os
import re
import shutil
import struct
import subprocess
import sys
import tarfile
import tempfile

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]


def need(condition, message):
    if not condition:
        raise ValueError(message)


def sha(data):
    return hashlib.sha256(data).hexdigest()


def relative(name):
    p=PurePosixPath(name)
    need(isinstance(name,str) and name and not p.is_absolute() and
         '..' not in p.parts and '.' not in p.parts and '\\' not in name and
         str(p)==name, 'unsafe relative path: '+str(name))
    return p


def inventory():
    expected={}
    raw=(ROOT/'sha256.txt').read_text()
    for line in raw.splitlines():
        h,sep,name=line.partition('  ')
        need(sep and len(h)==64 and all(c in '0123456789abcdef' for c in h),
             'malformed checksum record')
        relative(name)
        need(name not in expected and name!='sha256.txt', 'duplicate/self checksum')
        expected[name]=h
    need(expected, 'empty inventory')
    actual=set()
    for p in ROOT.rglob('*'):
        name=str(p.relative_to(ROOT))
        if name.split('/')[0]=='.git':
            need((ROOT/'.git').is_dir() and not (ROOT/'.git').is_symlink(),
                 'only root clone metadata directory is exempt')
            continue
        need(not p.is_symlink(), 'symlink payload: '+name)
        if p.is_file():actual.add(name)
    need(actual==set(expected)|{'sha256.txt'}, 'missing or unexpected payload files')
    for name,h in expected.items():
        need(sha((ROOT/name).read_bytes())==h,'changed payload: '+name)


def evidence():
    index=json.loads((ROOT/'proof/index.json').read_text())
    need(index['schema']==1 and index['owner']=='Carlo Corti','evidence schema/owner')
    archive=ROOT/relative(index['archive'])
    need(sha(archive.read_bytes())==index['sha256'],'archive identity')
    members={}
    declared={r['member'] for r in index['records'] if 'member' in r}
    limit=index['expanded_unique_bytes']
    expanded=0
    with tarfile.open(archive,'r:gz') as tar:
        for item in tar:
            relative(item.name)
            need(item.isfile() and item.name in declared and item.name not in members,
                 'unexpected/duplicate/nonregular archive member')
            expanded+=item.size
            need(expanded<=limit,'archive expansion beyond declared scope')
            members[item.name]=tar.extractfile(item).read()
    need(set(members)==declared and expanded==limit,'archive inventory/size')
    records={}
    for r in index['records']:
        name=r['original'];relative(name)
        need(name not in records,'duplicate restored path')
        data=(ROOT/relative(r['public'])).read_bytes() if 'public' in r else members[r['member']]
        need(len(data)==r['bytes'] and sha(data)==r['sha256'],'evidence changed: '+name)
        records[name]=(r,data)
    return records


def restore(records,destination):
    need(not destination.exists() and destination.parent.is_dir(),
         'restoration requires an absent destination and existing parent')
    need(not destination.resolve().is_relative_to(ROOT),'restore outside publication tree')
    destination.mkdir()
    for name,(record,data) in records.items():
        path=destination/relative(name);path.parent.mkdir(parents=True,exist_ok=True)
        with path.open('xb') as out:out.write(data)
        path.chmod(record['mode'])


def command(args,timeout=30,cwd=None):
    env=os.environ.copy();env.update({'PYTHONDONTWRITEBYTECODE':'1','OMP_DYNAMIC':'FALSE',
                                     'OMP_NUM_THREADS':'2','LC_ALL':'C'})
    run=subprocess.run(list(map(str,args)),capture_output=True,text=True,cwd=cwd,
                       timeout=timeout,env=env)
    need(run.returncode==0,'command failed: '+str(args)+'\n'+run.stdout[-3000:]+run.stderr[-3000:])
    return run.stdout


def rows(data):
    return [tuple(map(int,line.split())) for line in data.decode().splitlines() if line]


def direct():
    result=[]
    for n in range(1,9):
        accepted=0
        for p in itertools.permutations(range(n)):
            c=low=0;high=n
            for j,v in enumerate(p,1):
                c=v-c
                if j&1:high=min(high,c)
                else:low=max(low,-c)
            accepted+=low<=high
        result.append((n,accepted))
    return result


def retained(records,canonical):
    with tempfile.TemporaryDirectory(prefix='a180205-proof-') as tmp:
        hist=Path(tmp)/'hist';restore(records,hist)
        for n in (18,26,28):
            native=(hist/f'runs/n{n}/prod/cnt.tsv').read_bytes()
            need(rows(native)==canonical[:n],'original producer rows differ')
            exact=command([sys.executable,'-B',hist/'validation/crt.py',
                           hist/f'runs/n{n}/ie/cnt.tsv','--ie',hist/'validation/ie'])
            need(rows(exact.encode())==canonical[:n],'original retained-residue reconstruction differs')
            if n==28:
                regenerated=exact.rstrip('\n').encode()+b'\n\n'
                need(regenerated==(ROOT/'data/b180205.txt').read_bytes(),
                     'regenerated canonical b-file differs byte for byte')
                need(native+b'\n'==regenerated,'native table framing/value identity')
        # Descriptor/chain/frontier check only; never reads or regenerates F/W.
        journal=(hist/'runs/n28/prod/evt.bin').read_bytes()
        need(len(journal)%1024==0,'journal framing')
        previous_digest=bytes(32);h=1;rank=0;total=0;previous=None;completions=[]
        for i in range(len(journal)//1024):
            r=journal[i*1024:(i+1)*1024]
            need(sha(r[:-32])==r[-32:].hex() and r[592:624]==previous_digest,'journal chain')
            previous_digest=r[-32:]
            seq,phase,state_h,state_rank,n,cursor,reads=struct.unpack_from('<7Q',r,8)
            layer,lo,count=struct.unpack_from('<3Q',r,624)
            quantum=struct.unpack_from('<Q',r,728)[0]
            need(seq==i+1 and 1<=quantum<=262144,'record sequence/quantum')
            if count:
                need(layer==h and lo==rank and count<=math.comb(27,h)-rank,'DP rank partition')
                rank+=count;total+=count
                if rank==math.comb(27,h):h+=1;rank=0
                need((state_h,state_rank)==(h,rank),'DP frontier')
            if previous and previous[0]==1:
                pn,pc=previous[1:];limit=1 if pn==1 else 1<<(pn-2)
                hi=min(pc+quantum,limit)
                if n==pn:need(cursor==hi<limit,'partial convolution endpoint')
                else:
                    need(n==pn+1 and cursor==0 and hi==limit,'completion endpoint')
                    completions.append(pn)
            previous=(phase,n,cursor)
        need(total==2**27-1 and (h,rank)==(28,0) and previous==(2,29,0), 'final descriptor coverage')
        need(completions==list(range(1,29)),'convolution completion sequence')
        need(journal[-1024:]==(hist/'runs/n28/prod/ctl.bin').read_bytes(),'control/journal identity')
    return len(records)


def scalar(canonical):
    spec=importlib.util.spec_from_file_location('first18_public',ROOT/'check/first18.py')
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    need(module.count(18)==canonical[:18],'unpacked scalar comparison1..18')


def smoke(canonical):
    with tempfile.TemporaryDirectory(prefix='a180205-build-') as tmp:
        root=Path(tmp);(root/'src').mkdir();(root/'check').mkdir();(root/'data').mkdir()
        for name in ('src/a180205.c','src/Makefile','check/ie.cpp','check/crt.py','data/b180205.txt'):
            shutil.copyfile(ROOT/name,root/name)
        command(['make','-C',root/'src','all','ie'],timeout=60)
        producer=root/'src/a180205';ie=root/'check/ie'
        command([producer,'selftest']);command([ie,'selftest'])
        command([producer,'run','--root',root/'p8','--max','8','--threads','2','--quantum','3'])
        command([producer,'check','--root',root/'p8','--max','8'])
        command([ie,'run','--root',root/'i8','--max','8','--threads','2','--quantum','3'])
        command([ie,'check','--root',root/'i8','--max','8'])
        out=command([sys.executable,'-B',root/'check/crt.py',root/'i8/cnt.tsv','--ie',ie])
        need(rows(out.encode())==canonical[:8] and rows((root/'p8/cnt.tsv').read_bytes())==canonical[:8],
             'fresh native/IE8 mismatch')
        f=(root/'p8/f.bin').read_bytes()
        for mask in range(128):
            labels=[b+1 for b in range(7) if mask>>b&1];accepted=0
            for order in itertools.permutations(labels):
                state=0
                for v in order:
                    state=v-state
                    if state<0:break
                else:accepted+=1
            rank=sum(math.comb(v-1,i+1) for i,v in enumerate(labels))
            slot=sum(math.comb(7,j) for j in range(len(labels)))+rank
            need(int.from_bytes(f[16*slot:16*(slot+1)],'little')==accepted,'direct F coefficient')


def texcheck():
    with tempfile.TemporaryDirectory(prefix='a180205-tex-') as tmp:
        for i in range(2):
            command(['pdflatex','-draftmode','-no-shell-escape','-interaction=nonstopmode',
                     '-halt-on-error','-output-directory',tmp,ROOT/'paper/A180205.tex'])
        log=(Path(tmp)/'A180205.log').read_text()
        need(not any(x in log for x in ('LaTeX Warning:','LaTeX Error:','Overfull','Underfull',
                                        'Undefined control sequence')),'TeX log issue')
        need(not list(Path(tmp).glob('*.pdf')),'forbidden PDF')


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--build',action='store_true',help='also build and smoke native programs through8 in disposable storage')
    ap.add_argument('--tex',action='store_true',help='also check monolithic TeX in draftmode; no PDF')
    ap.add_argument('--restore',type=Path,help='restore selected historical records to a NEW external directory; run no census')
    args=ap.parse_args()
    inventory();records=evidence()
    if args.restore:
        need(not args.build and not args.tex,'restore is separate from execution')
        restore(records,args.restore);print('RESTORED selected historical records; no original large F/W tables');return
    raw=(ROOT/'data/b180205.txt').read_bytes()
    need(raw.endswith(b'\n\n') and not raw.endswith(b'\n\n\n') and b'\r' not in raw,'b-file framing')
    canonical=rows(raw)
    need([n for n,a in canonical]==list(range(1,29)),'canonical contiguous1..28')
    need(canonical[-1][1]==1226245772785310491672576,'endpoint')
    manuscript=(ROOT/'paper/A180205.tex').read_text()
    block=manuscript.split(r'\begin{tabular}{@{}rr@{\qquad}rr@{}}')[1].split(r'\end{tabular}')[0]
    table=[]
    for line in block.splitlines():
        match=re.fullmatch(r'(\d+) & (\d+) & (\d+) & (\d+) \\\\',line)
        if match:
            n,a,k,b=map(int,match.groups());table.extend(((n,a),(k,b)))
    need(sorted(table)==canonical,'manuscript table differs from canonical data')
    count=retained(records,canonical)
    need(direct()==canonical[:8],'definition-only permutation totals1..8')
    scalar(canonical)
    if args.build:smoke(canonical)
    if args.tex:texcheck()
    print(json.dumps({'status':'PUBLIC PACKAGE CHECK PASS','rows':28,'original_records':count,
        'retained_CRT_maxima':[18,26,28],'direct_permutations_through':8,'scalar_through':18,
        'native_smoke_through':8 if args.build else None,'TeX_draftmode':args.tex,
        'new_terms':False,'original_F_W_replay':False}))


if __name__=='__main__':
    try:main()
    except (ValueError,OSError,KeyError,subprocess.SubprocessError) as exc:
        print('PACKAGE CHECK FAILED: '+str(exc),file=sys.stderr);raise SystemExit(1)
