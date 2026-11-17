#!/usr/bin/env python3
"""Independent unpacked scalar-Python recount, ceiling18. No producer input.

Uses the frozen MiniMax review-side recurrence implementation. Shares the
proved zero-split theorem; no colex, parity-packed indexing, C arrays or CRT.
Operator-run validation only. Project owner: Carlo Corti.
"""
import argparse
import importlib.util
from pathlib import Path
import sys
import threading
import time

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'check/scalar.py'

def count(maximum):
    if not 1<=maximum<=18:
        raise ValueError('independent first-new recount supports1..18 only')
    spec=importlib.util.spec_from_file_location('review_scalar',SOURCE)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    m=maximum-1
    weights,tails=module.axis_A(m)
    del weights
    f=[0]*(1<<m)
    for labels,value in tails.items():
        f[sum(1<<b for b in labels)]=value
    del tails
    return [(n,sum(f[a]*f[((1<<(n-1))-1)^a] for a in range(1<<(n-1))))
            for n in range(1,maximum+1)]

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--max',type=int,choices=range(1,19),required=True)
    a=ap.parse_args();stop=threading.Event();start=time.monotonic()
    def heartbeat():
        while not stop.wait(5):
            print(f'PYTHON independent scalar recount max={a.max} elapsed_s={time.monotonic()-start:.0f}; no admission yet',file=sys.stderr,flush=True)
    worker=threading.Thread(target=heartbeat,daemon=True);worker.start()
    print(f'PYTHON independent scalar recount START max={a.max}',file=sys.stderr,flush=True)
    try:
        rows=count(a.max)
        for n,value in rows:print(n,value)
    finally:stop.set();worker.join()
    print(f'PYTHON recount COMPLETE elapsed_s={time.monotonic()-start:.0f}; comparison remains separate',file=sys.stderr,flush=True)
if __name__=='__main__':main()
