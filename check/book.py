#!/usr/bin/env python3
"""Run one bounded diagnostic and append cumulative runtime evidence.

Project owner: Carlo Corti. No campaign runner. Scope is selected by maintainer;
maximum new-term enumeration is not authorized by this wrapper.
"""
import argparse
import fcntl
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import time

ROOT = Path(__file__).resolve().parents[1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--category', choices=('known', 'synthetic', 'nonnumeric'), required=True)
    ap.add_argument('--label', required=True)
    ap.add_argument('--timeout', type=float, default=60)
    ap.add_argument('command', nargs=argparse.REMAINDER)
    a = ap.parse_args()
    if not (a.label.isalnum() and 0 < a.timeout <= 600):
        raise ValueError('alphanumeric label and timeout in (0,600] required')
    area = ROOT/'outputs/dev0'
    lock = (area/'budget.lock').open('a')
    fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    path = area/'budget.json'
    book = json.loads(path.read_text())
    if (area/(a.label+'.out')).exists():
        raise FileExistsError('immutable diagnostic label already used')
    timeout = a.timeout
    if a.category != 'nonnumeric':
        used = sum(x['seconds'] for x in book['executions'] if x['category'] == a.category)
        timeout = min(timeout, book['caps_seconds'][a.category]-used)
        if timeout <= 0:
            raise RuntimeError('cumulative budget exhausted')
    cmd = a.command
    if cmd and cmd[0] == '--':
        cmd = cmd[1:]
    start = time.monotonic()
    with (area/(a.label+'.out')).open('xb') as out, (area/(a.label+'.err')).open('xb') as err:
        p = subprocess.Popen(cmd, stdin=subprocess.DEVNULL, stdout=out, stderr=err,
                             start_new_session=True)
        expired = False
        try:
            p.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            expired = True
            os.killpg(p.pid, signal.SIGKILL)
            p.wait()
    elapsed = time.monotonic()-start
    book['executions'].append({'name': a.label, 'command': cmd, 'category': a.category,
        'seconds': elapsed, 'returncode': p.returncode, 'deadline_exceeded': expired,
        'source_sha256': hashlib.sha256((ROOT/'src/a180205.c').read_bytes()).hexdigest(),
        'makefile_sha256': hashlib.sha256((ROOT/'src/Makefile').read_bytes()).hexdigest(),
        'argument_file_identities': {s: hashlib.sha256(Path(s).read_bytes()).hexdigest()
             for s in cmd if Path(s).is_file()}})
    path.write_text(json.dumps(book, indent=2)+'\n')
    print(json.dumps(book['executions'][-1]))
    return 124 if expired else p.returncode


if __name__ == '__main__':
    raise SystemExit(main())
