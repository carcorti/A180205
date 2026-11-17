#!/usr/bin/env python3
"""Additional persistence/closure fixtures. Project owner: Carlo Corti.

Runs only maximum17 known counts. Parent book.py charges the entire bounded
fixture as known-domain runtime, including every synthetic subcase.
"""
from pathlib import Path
import hashlib
import json
import shutil
import struct
import subprocess
import sys

if sys.flags.optimize:
    raise RuntimeError('Optimized Python is not supported for validation')

ROOT = Path(__file__).resolve().parents[1]
PROD = ROOT/'src/a180205'
AREA = ROOT/'outputs/dev0/hostile'


def run(args, expected=0):
    p = subprocess.run(list(map(str, args)), capture_output=True, timeout=10)
    assert p.returncode == expected, (args, p.returncode, p.stderr)
    return p.stderr


def main():
    area = AREA
    index = 1
    while area.exists():
        index += 1
        area = AREA.with_name('hostile'+str(index))
    area.mkdir()
    source_hash = hashlib.sha256((ROOT/'src/a180205.c').read_bytes()).hexdigest()
    binary_hash = hashlib.sha256(PROD.read_bytes()).hexdigest()
    bases = [p for p in (ROOT/'outputs/dev0').glob('test*/known17')
             if json.loads((p/'cfg.json').read_text())['source'] == source_hash
             and json.loads((p/'cfg.json').read_text())['executable'] == binary_hash]
    assert bases, 'no current canonical known17 fixture'
    base = sorted(bases)[-1]
    journal = (base/'evt.bin').read_bytes()
    records = [journal[i:i+1024] for i in range(0, len(journal), 1024)]
    # Freeze old prefixes as synthetic crash fixtures without altering originals.
    selected = [records[0]]
    for n in (2, 5):
        selected.append(next(r for r in records if struct.unpack_from('<Q', r, 16)[0] == 1
                             and struct.unpack_from('<Q', r, 40)[0] == n))
    for label, rec in zip(('zero', 'one', 'many'), selected):
        job = area/label
        shutil.copytree(base, job)
        seq = struct.unpack_from('<Q', rec, 8)[0]
        (job/'evt.bin').write_bytes(journal[:seq*1024])
        (job/'ctl.bin').write_bytes(rec)
        (job/'cnt.tsv').unlink()
        (job/'end.json').unlink()
        stderr = run([PROD, 'check', '--root', job, '--max', 17])
        expected = {'zero': 0, 'one': 1, 'many': 4}[label]
        assert f'complete_terms={expected}'.encode() in stderr
        run([PROD, 'run', '--root', job, '--max', 17, '--resume'])
        assert (job/'cnt.tsv').read_bytes() == (base/'cnt.tsv').read_bytes()
    # Extra uncommitted bytes are allowed, do not become coverage, check is read-only.
    tail = area/'tail'
    shutil.copytree(base, tail)
    for name in ('evt.bin', 'f.bin'):
        with (tail/name).open('ab') as f:
            f.write(b'UNCOMMITTED')
    before = {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in tail.iterdir()}
    run([PROD, 'check', '--root', tail, '--max', 17])
    assert before == {p.name: hashlib.sha256(p.read_bytes()).hexdigest() for p in tail.iterdir()}
    # Truncated committed state, changed config and final receipt fail closed.
    for i, name in enumerate(('ctl.bin', 'evt.bin', 'f.bin', 'cfg.json', 'end.json', 'base.txt')):
        job = area/f'trunc{i}'
        shutil.copytree(base, job)
        f = job/name
        f.write_bytes(f.read_bytes()[:10])
        run([PROD, 'check', '--root', job, '--max', 17], expected=1)
    # A self-consistent hash cannot make invalid semantic fields valid.
    for label, offset, value in (('phase', 16, 3), ('rank', 32, 1), ('future', 80+29*16, 1),
                                 ('reserved', 800, 1)):
        job = area/label
        shutil.copytree(base, job)
        rec = bytearray((job/'ctl.bin').read_bytes())
        struct.pack_into('<Q', rec, offset, value)
        rec[-32:] = hashlib.sha256(rec[:-32]).digest()
        (job/'ctl.bin').write_bytes(rec)
        allrec = bytearray((job/'evt.bin').read_bytes())
        allrec[-1024:] = rec
        (job/'evt.bin').write_bytes(allrec)
        run([PROD, 'check', '--root', job, '--max', 17], expected=1)
    # Exclusive lock prevents simultaneous writers and readers of a live writer.
    import fcntl
    with (base/'lock').open('rb') as lock:
        fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        run([PROD, 'check', '--root', base, '--max', 17], expected=1)
    # Appended data in an isolated baseline must not change frozen historical input.
    grow = area/'growth'
    (grow/'src').mkdir(parents=True)
    (grow/'data').mkdir()
    for f in ('a180205.c', 'Makefile', 'a180205'):
        shutil.copy2(ROOT/'src'/f, grow/'src'/f)
    (grow/'data/b180205.txt').write_bytes((ROOT/'data/b180205.txt').read_bytes().rstrip(b'\n')+b'\n18 0\n\n')
    run([grow/'src/a180205', 'run', '--root', grow/'job', '--max', 8])
    assert (grow/'job/base.txt').read_bytes() == (ROOT/'data/b180205.txt').read_bytes()
    assert (grow/'job/cnt.tsv').read_text().strip().splitlines()[-1] == '8 4000'
    ie = ROOT/'validation/ie'
    iebase = base.parent/'ie17'
    crt = ROOT/'validation/crt.py'
    for label, offset, value in (('iecursor', 16, 0), ('ieadds', 24, 0), ('ieresidue', 32, 2**61),
                                 ('iepad', 630, 1)):
        job = area/label
        shutil.copytree(iebase, job)
        rec = bytearray((job/'ctl.bin').read_bytes())
        if label == 'iepad':
            rec[offset] = value
        else:
            struct.pack_into('<Q', rec, offset, value)
        rec[-32:] = hashlib.sha256(rec[:-32]).digest()
        (job/'ctl.bin').write_bytes(rec)
        run([ie, 'check', '--root', job, '--max', 17], expected=1)
        assert subprocess.run([sys.executable, str(crt), str(job/'cnt.tsv')],
                              capture_output=True).returncode != 0
    # CRT rejects malformed, truncated and numerically mismatched residues.
    for label, transform in (('crtcr', lambda b: b.replace(b'\n', b'\r\n')),
                              ('crtneg', lambda b: b.replace(b'1 1 1', b'1 -1 1', 1)),
                              ('crtdup', lambda b: b+b.splitlines(keepends=True)[0]),
                              ('crtnum', lambda b: b.replace(b'1 1 1', b'1 2 2', 1))):
        job = area/label
        shutil.copytree(iebase, job)
        p = job/'cnt.tsv'
        p.write_bytes(transform(p.read_bytes()))
        assert subprocess.run([sys.executable, str(crt), str(p)], capture_output=True).returncode != 0
    print(json.dumps({'status': 'PASS', 'closure': ['zero', 'one', 'many', 'complete'],
                      'uncommitted_tail': 'ignored_read_only', 'known_maximum': 17,
                      'no_new_term_computed': True}))


if __name__ == '__main__':
    main()
