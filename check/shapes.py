#!/usr/bin/env python3
"""Local payload/isolation probes; no upload. Owner: Carlo Corti."""
from pathlib import Path
import json
import hashlib
import shutil
import subprocess
import tempfile
import zipfile

ROOT=Path(__file__).resolve().parents[1]
PUB=ROOT


def run(root,flags=(),success=True):
    cmd=['bwrap','--unshare-user','--unshare-pid','--ro-bind','/usr','/usr',
         '--ro-bind','/lib','/lib','--ro-bind','/lib64','/lib64',
         '--ro-bind','/etc','/etc','--ro-bind','/var/lib/texmf','/var/lib/texmf',
         '--proc','/proc','--dev','/dev','--tmpfs','/tmp',
         '--ro-bind',str(root),'/payload with spaces','--chdir','/payload with spaces',
         '/usr/bin/python3','-I','-B','-c',
         'from pathlib import Path; import runpy,sys; '
         'assert not Path("/home/carlo").exists(); '
         'sys.argv=["check/verify.py"]+'+repr(list(flags))+'; '
         'runpy.run_path("check/verify.py",run_name="__main__")']
    p=subprocess.run(cmd,capture_output=True,text=True,timeout=60)
    if (p.returncode==0)!=success:
        raise RuntimeError(str(p.returncode)+'\n'+p.stdout+p.stderr)
    return {'returncode':p.returncode,'stdout':p.stdout,'stderr':p.stderr,
            'private_workspace_visible':False,'payload_read_only':True,
            'flags':list(flags)}


def main():
    outcomes={}
    with tempfile.TemporaryDirectory(prefix='a180205-shapes-') as tmp:
        parent=Path(tmp)
        first=parent/'arbitrary renamed root';shutil.copytree(PUB,first)
        outcomes['arbitrary_root_build_tex']=run(first,('--build','--tex'))
        clone=parent/'clone';shutil.copytree(PUB,clone);(clone/'.git').mkdir()
        (clone/'.git/config').write_text('[core]\nrepositoryformatversion = 0\n')
        outcomes['clone_root_git_metadata']=run(clone)
        archive=parent/'provider.zip'
        with zipfile.ZipFile(archive,'w',zipfile.ZIP_DEFLATED) as out:
            for p in sorted(PUB.rglob('*')):
                if p.is_file():out.write(p,'carcorti-A180205-draft/'+str(p.relative_to(PUB)))
        extracted=parent/'extract';extracted.mkdir()
        with zipfile.ZipFile(archive) as z:z.extractall(extracted)
        outcomes['provider_zip_extraction']=run(extracted/'carcorti-A180205-draft')
        for case in ('missing','changed','unexpected','nested_git','git_file','table_semantics'):
            target=parent/case;shutil.copytree(PUB,target)
            if case=='missing':(target/'data/b180205.txt').unlink()
            elif case=='changed':
                p=target/'data/b180205.txt';p.write_bytes(p.read_bytes().replace(b'1 1\n',b'1 9\n',1))
            elif case=='unexpected':(target/'extra.txt').write_text('unexpected\n')
            elif case=='nested_git':
                p=target/'check/.git';p.mkdir();(p/'config').write_text('not root metadata\n')
            elif case=='git_file':(target/'.git').write_text('gitdir: private path\n')
            else:
                p=target/'paper/A180205_v4.tex';text=p.read_text()
                old='28 & 1226245772785310491672576';assert old in text
                p.write_text(text.replace(old,'28 & 1226245772785310491672577',1))
                # A matching new checksum must not hide a scientific table discrepancy.
                (target/'sha256.txt').write_text(''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+str(p.relative_to(target))+'\n' for p in sorted(target.rglob('*')) if p.is_file() and p.name!='sha256.txt'))
            outcomes['reject_'+case]=run(target,success=False)
    print(json.dumps({'status':'RAW DISTRIBUTION-SHAPE PASS',
        'owner':'Carlo Corti','remote_actions':False,'namespace':'user/pid/mount; no /home mounted',
        'outcomes':outcomes,'temporary_roots_removed':True},indent=2))


if __name__=='__main__':main()
