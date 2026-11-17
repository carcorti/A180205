#!/usr/bin/env python3
"""Bounded target-side regressions. Project owner: Carlo Corti.

Known-domain jobs only (maximum17). This entry point never computes a new term.
Runtime reservations and actual wall costs are cumulative across invocations.
"""
import hashlib
import fcntl
import itertools
import json
import os
from pathlib import Path
import shutil
import signal
import struct
import subprocess
import sys
import time

if sys.flags.optimize:
    raise RuntimeError('Optimized Python is not supported for validation')

ROOT = Path(__file__).resolve().parents[1]
AREA = ROOT / 'outputs/dev0'
PROD = Path(os.environ.get('A180205_TEST_PRODUCER', ROOT / 'src/a180205'))
IE = Path(os.environ.get('A180205_TEST_IE', ROOT / 'validation/ie'))
KNOWN = (ROOT / 'data/b180205.txt').read_text().strip()


def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()


def main():
    AREA.mkdir(exist_ok=True)
    lock = (AREA/'budget.lock').open('a')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    index = 1
    while (AREA / f'test{index}').exists():
        index += 1
    area = AREA / f'test{index}'
    area.mkdir()
    ledger = AREA / 'budget.json'
    book = json.loads(ledger.read_text()) if ledger.exists() else {
        'caps_seconds': {'known': 120, 'synthetic': 600}, 'executions': []}
    observations = []

    def run(name, args, expected=0, category='known', interrupt=False):
        spent = sum(e['seconds'] for e in book['executions'] if e['category'] == category)
        remaining = book['caps_seconds'][category] - spent
        if remaining < 1:
            raise RuntimeError(f'{category} cumulative budget exhausted')
        command = list(map(str, args))
        start = time.monotonic()
        status = None
        stdout = stderr = b''
        try:
            child = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                                     stdin=subprocess.DEVNULL, start_new_session=True)
            if interrupt:
                time.sleep(0.08)
                child.send_signal(signal.SIGTERM)
            try:
                stdout, stderr = child.communicate(timeout=min(remaining, 30))
            except subprocess.TimeoutExpired:
                os.killpg(child.pid, signal.SIGKILL)
                stdout, stderr = child.communicate()
                raise RuntimeError('deadline exceeded; not correctness evidence')
            status = child.returncode
        finally:
            elapsed = time.monotonic()-start
            book['executions'].append({'name': name, 'command': command, 'category': category,
                                       'seconds': elapsed, 'returncode': status,
                                       'source_sha256': sha(ROOT/'src/a180205.c'),
                                       'binary_sha256': sha(PROD), 'ie_sha256': sha(IE)})
            ledger.write_text(json.dumps(book, indent=2)+'\n')
            (area/f'{name}.out').write_bytes(stdout)
            (area/f'{name}.err').write_bytes(stderr)
        if status != expected:
            raise AssertionError((name, status, expected, stderr.decode(errors='replace')))
        observations.append({'name': name, 'status': 'PASS', 'seconds': elapsed})
        return stdout

    run('self', [PROD, 'selftest'], category='synthetic')
    run('ieself', [IE, 'selftest'], category='synthetic')
    run('crtself', [sys.executable, ROOT/'validation/crt.py', '--selftest'], category='synthetic')
    base = area/'known17'
    run('known17', [PROD, 'run', '--root', base, '--max', 17, '--threads', 8])
    assert (base/'cnt.tsv').read_text().strip() == KNOWN
    before = {p.name: sha(p) for p in base.iterdir()}
    run('check17', [PROD, 'check', '--root', base, '--max', 17], category='synthetic')
    run('complete', [PROD, 'run', '--root', base, '--max', 17, '--resume'], category='synthetic')
    assert before == {p.name: sha(p) for p in base.iterdir()}
    run('noclob', [PROD, 'run', '--root', base, '--max', 17], expected=1, category='synthetic')
    run('iemax17', [IE, 'run', '--root', area/'ie17', '--max', 17, '--threads', 8])
    run('iecheck', [IE, 'check', '--root', area/'ie17', '--max', 17], category='synthetic')
    exact = run('crtexact', [sys.executable, ROOT/'validation/crt.py', area/'ie17/cnt.tsv', '--ie', IE])
    assert exact.decode().strip() == KNOWN
    for maximum in (1, 2, 3):
        small = area/f'n{maximum}'
        run(f'small{maximum}', [PROD, 'run', '--root', small, '--max', maximum])
        run(f'smallcheck{maximum}', [PROD, 'check', '--root', small, '--max', maximum], category='synthetic')
        assert (small/'cnt.tsv').read_text().strip() == '\n'.join(KNOWN.splitlines()[:maximum])
    for t in (1, 2, 4, 16):
        job = area/f't{t}'
        run(f'thread{t}', [PROD, 'run', '--root', job, '--max', 8, '--threads', t,
                           '--quantum', 3])
        assert (job/'cnt.tsv').read_text().strip() == '\n'.join(KNOWN.splitlines()[:8])
    job = area/'resume'
    run('interrupt', [PROD, 'run', '--root', job, '--max', 17, '--quantum', 1],
        expected=2, interrupt=True)
    run('resume', [PROD, 'run', '--root', job, '--max', 17, '--resume'])
    assert (job/'cnt.tsv').read_bytes() == (base/'cnt.tsv').read_bytes()
    # Deterministic retained penultimate-layer rewind, independent of timing.
    rewind = area/'rewind'
    shutil.copytree(area/'t1', rewind)
    journal = (rewind/'evt.bin').read_bytes()
    record = next(journal[i:i+1024] for i in range(0, len(journal), 1024)
                  if struct.unpack_from('<Q', journal, i+24)[0] == 6
                  and struct.unpack_from('<Q', journal, i+32)[0] == 3)
    seq = struct.unpack_from('<Q', record, 8)[0]
    (rewind/'ctl.bin').write_bytes(record)
    (rewind/'evt.bin').write_bytes(journal[:seq*1024])
    (rewind/'cnt.tsv').unlink()
    (rewind/'end.json').unlink()
    run('rewind', [PROD, 'run', '--root', rewind, '--max', 8, '--resume'])
    assert (rewind/'cnt.tsv').read_bytes() == (area/'t1/cnt.tsv').read_bytes()
    # Independent initial-value interval predicate, no zero split or F recurrence.
    direct = []
    start = time.monotonic()
    for n in range(1, 9):
        count = 0
        for p in itertools.permutations(range(n)):
            c = 0
            low = 0
            high = n
            for j, v in enumerate(p, 1):
                c = v-c
                if j & 1:
                    high = min(high, c)
                else:
                    low = max(low, -c)
            count += low <= high
        direct.append((n, count))
    elapsed = time.monotonic()-start
    book['executions'].append({'name': 'direct8', 'category': 'known', 'seconds': elapsed,
                               'command': 'independent interval predicate in validation/test.py',
                               'returncode': 0})
    ledger.write_text(json.dumps(book, indent=2)+'\n')
    assert '\n'.join(f'{n} {c}' for n, c in direct) == '\n'.join(KNOWN.splitlines()[:8])
    for i, options in enumerate(([], ['--max', '0'], ['--max', '-1'], ['--max', '+1'],
                                 ['--max', '31'], ['--max', ' 1'], ['--max', '1x'],
                                 ['--max', '1', '--max', '2'], ['--wat', '1'],
                                 ['--seconds', '0'], ['--threads', '17'], ['--quantum', '262145'],
                                 ['--max'])):
        args = [PROD, 'run', '--root', area/'bad', *options]
        run(f'cli{i}', args, expected=1, category='synthetic')
        assert not (area/'bad').exists()
    for file, pos in [('f.bin', 100), ('ctl.bin', 32), ('evt.bin', 1030), ('cnt.tsv', 4)]:
        bad = area/f'bad{pos}'
        shutil.copytree(base, bad)
        p = bad/file
        data = bytearray(p.read_bytes())
        data[pos] ^= 1
        p.write_bytes(data)
        run(f'corrupt{pos}', [PROD, 'check', '--root', bad, '--max', 17],
            expected=1, category='synthetic')
    # Complete F vectors: direct permutations on each true subset; multiplicity.
    coeff_start = time.monotonic()
    f = (area/'t1/f.bin').read_bytes()
    import math
    offsets = [sum(math.comb(7, j) for j in range(h)) for h in range(8)]
    collision = False
    for mask in range(1 << 7):
        labels = [b+1 for b in range(7) if mask >> b & 1]
        count = 0
        for order in itertools.permutations(labels):
            s = 0
            for v in order:
                s = v-s
                if s < 0:
                    break
            else:
                count += 1
        rank = sum(math.comb(v-1, i+1) for i, v in enumerate(labels))
        slot = offsets[len(labels)]+rank
        got = int.from_bytes(f[16*slot:16*(slot+1)], 'little')
        assert got == count
        collision |= count > 1
    assert collision
    book['executions'].append({'name': 'coefficients7', 'category': 'known',
        'seconds': time.monotonic()-coeff_start, 'returncode': 0,
        'command': 'all128 true-label subset permutation oracles in validation/test.py'})
    ledger.write_text(json.dumps(book, indent=2)+'\n')
    result = {'status': 'PASS', 'tested_producer': str(PROD), 'tested_ie': str(IE),
              'tested_binary_sha256': sha(PROD), 'candidate': {str(p.relative_to(ROOT)): sha(p)
              for p in (ROOT/'src/a180205.c', ROOT/'src/Makefile', PROD,
                        ROOT/'validation/ie.cpp', IE, ROOT/'validation/crt.py')},
              'observations': observations, 'direct_interval_counts': direct,
              'all_small_subset_coefficients': 128,
              'new_term_computed': False}
    (area/'result.json').write_text(json.dumps(result, indent=2)+'\n')
    print(json.dumps({'status': 'PASS', 'evidence': str(area/'result.json'),
                      'budget_used': {c: sum(e['seconds'] for e in book['executions']
                                            if e['category'] == c) for c in ('known','synthetic')}}))


if __name__ == '__main__':
    main()
