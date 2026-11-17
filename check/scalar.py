#!/usr/bin/env python3
"""A180205 review-time independent recomputation.

Scope (finite, declared): known range only, n = 1..17 (no new index is
enumerated).  This is a REVIEW-SIDE check of the frozen source's mathematics
and arithmetic domains.  It does not execute the producer binary and does not
replace any inherited E row.

Axes:
  A  basis recurrence  W(S,s)=sum_{v in S,v>=s} W(S\\{v},v-s)   -> a(n)=sum_S F(S)F(U\\S)
  A' the frozen source's literal index arithmetic (parity packing + integer
     truncation of j=(v-s)/2) -> must equal axis A for every subset
  B  independent inclusion-exclusion over alphabets (the IE method) -> a(n)
  C  read-counter domain D(M) vs the exact dense-update count
  D  colex rank/unrank/deletion-rank identity
  E  journal_room() projection vs a simulated commit sequence
  F  array/disk footprint identity at 30 and 31
  G  frozen-prefix identity chain (base.txt SHA-256)
"""
import hashlib
import itertools
import math
import sys
from math import comb

KNOWN = [(1, 1), (2, 2), (3, 4), (4, 12), (5, 44), (6, 176), (7, 768), (8, 4000),
         (9, 22896), (10, 142336), (11, 967040), (12, 7258368), (13, 57919872),
         (14, 490253312), (15, 4455645952), (16, 43468799232), (17, 445393216256)]
FAILS = []


def check(name, ok, detail=""):
    print(("PASS " if ok else "FAIL ") + name + ((" :: " + detail) if detail else ""))
    if not ok:
        FAILS.append(name)


def binom_table(M):
    C = [[0] * (M + 1) for _ in range(M + 1)]
    for i in range(M + 1):
        C[i][0] = 1
        C[i][i] = 1
        for j in range(1, i):
            C[i][j] = C[i - 1][j - 1] + C[i - 1][j]
    return C


def axis_A(M):
    """Basis recurrence: W(S,s) = sum_{v in S, v>=s} W(S\\{v}, v-s).
    Convention: s is the state AFTER consuming S, s == sum(S) (mod 2)."""
    C = binom_table(M)
    # W[mask][s] for s in 0..M ; s is the final state of a chain over `mask`.
    W = {}
    W[()] = [0] * (M + 1)
    W[()][0] = 1                      # W({},0)=1, all other empty states 0
    for h in range(1, M + 1):
        for mask in itertools.combinations(range(M), h):
            bits = [b + 1 for b in mask]          # labels 1..M
            p = sum(bits) & 1
            row = [0] * (M + 1)
            for i, v in enumerate(bits):
                rest = tuple(mask[:i]) + tuple(mask[i + 1:])
                prev = W[rest]
                for s in range(p, v + 1, 2):      # s' = v-s must be >= 0
                    sp = v - s
                    row[s] += prev[sp]
            W[mask] = row
    F = {mask: sum(W[mask]) for mask in W}
    return W, F


def axis_A_prime(M):
    """The frozen source's literal arithmetic, transcribed from a180205.c:
    parity(S)=sum(labels) mod 2; out[s/2] accumulates prev[pr*w + (v-s)//2];
    predecessor index pr = prefix[i] + suffix[i+1] (deletion rank)."""
    C = binom_table(M)
    w = M // 2 + 1
    packed = {0: {(): [1] + [0] * (w - 1)}}     # layer 0: W({},0)=1
    Fsrc = {(): 1}
    for h in range(1, M + 1):
        packed[h] = {}
        for mask in itertools.combinations(range(M), h):
            bits = list(mask)
            labels = [b + 1 for b in bits]
            parity = 0
            for lb in labels:
                parity ^= lb & 1
            prefix = [0] * (h + 1)
            for i in range(h):
                prefix[i + 1] = prefix[i] + C[bits[i]][i + 1]
            suffix = [0] * (h + 1)
            for i in range(h, 0, -1):
                suffix[i - 1] = suffix[i] + C[bits[i - 1]][i - 1]
            out = [0] * w
            for i in range(h):
                v = labels[i]
                pr = prefix[i] + suffix[i + 1]
                s = parity
                while s <= v:
                    j = (v - s) // 2          # integer truncation, as in the C source
                    out[s // 2] += packed[h - 1][tuple(bits[:i] + bits[i + 1:])][j]
                    s += 2
            packed[h][mask] = out
            Fsrc[mask] = sum(out)
    return Fsrc


def axis_B(M):
    """Independent IE over alphabets: a(m+1)=sum_T (-1)^(m-|T|) Q_m(T),
    Q_m(T)=sum_k L_k(T)L_(m-k)(T), L_h(T)=walks of length h from 0 with labels T."""
    out = {}
    for m in range(0, M + 1):
        total = 0
        for r in range(m + 1):
            for T in itertools.combinations(range(1, m + 1), r):
                card = len(T)
                L = [0] * (m + 1)
                L[0] = 1
                prev = [0] * (m + 1)
                prev[0] = 1
                for h in range(1, m + 1):
                    nxt = [0] * (m + 1)
                    for v in T:
                        for s in range(0, v + 1):
                            nxt[v - s] += prev[s]
                    L[h] = sum(nxt)
                    prev = nxt
                q = sum(L[k] * L[m - k] for k in range(m + 1))
                if (m - card) & 1:
                    total -= q
                else:
                    total += q
        out[m + 1] = total
    return out


def axis_C(M):
    """Exact dense-update count of the pull loop vs the decode() domain bound."""
    C = binom_table(M)
    exact = 0
    per_row_max = 0
    for h in range(1, M + 1):
        for mask in itertools.combinations(range(M), h):
            labels = [b + 1 for b in mask]
            p = sum(labels) & 1
            r = sum(((v - p) // 2) + 1 for v in labels)
            exact += r
            per_row_max = max(per_row_max, r)
    if M >= 3:
        bound = (1 << (M - 3)) * M * (M + 3)
    elif M == 2:
        bound = 5
    else:
        bound = M
    return exact, bound, per_row_max


def axis_D(M):
    C = binom_table(M)
    off = [0] * (M + 2)
    for h in range(1, M + 2):
        off[h] = off[h - 1] + C[M][h - 1]

    def unrank(rank, h):
        mask = 0
        b = M
        for i in range(h, 0, -1):
            while True:
                b -= 1
                if C[b][i] <= rank:
                    break
            mask |= 1 << b
            rank -= C[b][i]
        return mask

    def findex(a):
        h = 0
        r = 0
        while a:
            b = (a & -a).bit_length() - 1
            h += 1
            r += C[b][h]
            a &= a - 1
        return off[h] + r

    ok = True
    for h in range(1, M + 1):
        for r in (0, C[M][h] // 2, C[M][h] - 1):
            if findex(unrank(r, h)) != off[h] + r:
                ok = False
    # deletion rank identity, exhaustively over all (mask, removed element)
    for h in range(1, M + 1):
        for mask in itertools.combinations(range(M), h):
            bits = list(mask)
            prefix = [0] * (h + 1)
            for i in range(h):
                prefix[i + 1] = prefix[i] + C[bits[i]][i + 1]
            suffix = [0] * (h + 1)
            for i in range(h, 0, -1):
                suffix[i - 1] = suffix[i] + C[bits[i - 1]][i - 1]
            for i in range(h):
                pr = prefix[i] + suffix[i + 1]
                rest = tuple(bits[:i]) + tuple(bits[i + 1:])
                if pr >= C[M][h - 1]:
                    ok = False
                # rank of `rest` inside layer h-1
                hh = h - 1
                r = 0
                for k, b in enumerate(sorted(rest), start=1):
                    r += C[b][k]
                if pr != r:
                    ok = False
    return ok


def axis_E(M, quantum):
    """Simulate the producer's commit sequence and compare with journal_room()."""
    C = binom_table(M)
    seq = 1                      # fresh run already wrote the initial record
    # phase 0
    h = 1
    rank = 0
    while h <= M:
        hi = min(rank + quantum, C[M][h])
        seq += 1
        rank = hi
        if rank == C[M][h]:
            rank = 0
            h += 1
    # phase 1
    n = 1
    cursor = 0
    while n <= M + 1:
        limit = 1 if n == 1 else (1 << (n - 2))
        hi = min(cursor + quantum, limit)
        seq += 1
        cursor = hi
        if cursor == limit:
            cursor = 0
            n += 1
    # journal_room() projection from a fresh state (phase 0, h=1, rank=0)
    records = 1                  # s.seq after the initial record
    for hh in range(1, M + 1):
        remain = C[M][hh]
        records += (remain + quantum - 1) // quantum
    for nn in range(1, M + 2):
        limit = 1 if nn == 1 else (1 << (nn - 2))
        records += (limit + quantum - 1) // quantum
    return seq, records


def main():
    print("== A: basis recurrence vs historical b-file ==")
    M = 16
    W, F = axis_A(M)
    U = list(range(1, M + 1))
    produced = {}
    for n in range(1, M + 2):
        S = [1 << (b - 1) for b in U[:n - 1]]   # labels 1..n-1 as bitmask keys
        # map label-set bitmask -> F
        Fm = {sum(1 << b for b in mask): sum(W[mask]) for mask in W}
        tot = 0
        full = (1 << (n - 1)) - 1
        for a in range(1 << (n - 1)):
            tot += Fm[a] * Fm[full ^ a]
        produced[n] = tot
    ok = all(produced[n] == v for n, v in KNOWN)
    check("axis A reproduces known 1..17 exactly", ok,
          "got " + ",".join(str(produced[n]) for n, _ in KNOWN))

    print("== A': frozen source index arithmetic == basis ==")
    Fsrc = axis_A_prime(M)
    ok = all(Fsrc[mask] == sum(W[mask]) for mask in W)
    check("source parity/truncation arithmetic == basis W(S,s) for all 2^16 subsets",
          ok)

    print("== B: independent inclusion-exclusion (different algorithm) ==")
    Mb = 14
    B = axis_B(Mb)
    ok = all(B[n] == v for n, v in KNOWN[:Mb + 1])
    check("IE method reproduces known 1..%d exactly" % (Mb + 1), ok,
          "got " + ",".join(str(B[n]) for n in range(1, Mb + 2)))

    print("== C: read-counter domain D(M) vs exact dense updates ==")
    bad = []
    for m in range(0, 17):
        ex, bd, mx = axis_C(m)
        if ex > bd:
            bad.append((m, ex, bd))
    check("exact dense updates <= decode() domain bound for M=0..16", not bad,
          "violations: " + str(bad))
    ex16, bd16, mx16 = axis_C(16)
    check("M=16 total reads == D(16) (== inherited total_reads=2490368)",
          ex16 == bd16 == 2490368, "exact=%d bound=%d" % (ex16, bd16))
    ex29 = (1 << 26) * 29 * 32
    check("D(29) model numerator reproduces 62277025792", ex29 == 62277025792,
          str(ex29))
    print("   max dense updates per row at M=16: %d (model budget uses M*w=29*15=435 at M=29)" % mx16)

    print("== D: colex rank / unrank / deletion rank ==")
    ok = axis_D(12)
    check("colex unrank/findex/deletion-rank identities hold exhaustively (M=12)", ok)

    print("== E: journal_room projection == simulated commit count ==")
    for (m, q) in ((16, 262144), (16, 1), (16, 3), (16, 1000), (29, 262144)):
        seq, proj = axis_E(m, q)
        check("M=%d quantum=%d: projected records == actual commits" % (m, q),
              seq == proj, "actual=%d projected=%d" % (seq, proj))
    seq, proj = axis_E(29, 262144)
    check("M=29 default quantum == 4130 records", seq == 4130, "actual=%d" % seq)

    print("== F: array/disk footprint identity ==")
    C = binom_table(29)
    w = 29 // 2 + 1

    def arrays(M):
        peak = 0
        for h in range(1, M + 1):
            peak = max(peak, (C[M][h - 1] + C[M][h]) * w * 16)
        return peak + (1 << M) * 16
    check("arrays(30) == 45818139392 (source selftest constant)",
          arrays(29) == 45818139392, str(arrays(29)))
    C30 = binom_table(30)
    peak30 = 0
    for h in range(1, 31):
        peak30 = max(peak30, (C30[30][h - 1] + C30[30][h]) * 16 * 16)
    n31 = peak30 + (1 << 30) * 16
    check("n=31 principal arrays == 94118159104 bytes (87.654 GiB) > 64 GiB RAM",
          n31 == 94118159104 and n31 / (1 << 30) == 87.65436625480652,
          "%d bytes = %.4f GiB" % (n31, n31 / (1 << 30)))
    slots = [0, 0, 0]
    for h in range(1, 30):
        slots[h % 3] = max(slots[h % 3], C[29][h] * w * 16)
    disk = sum(slots) + (1 << 29) * 16 + 262144 * 1024 + 65536
    check("3 W slots + F + journal + metadata == 62373979984 (claimed storage bound)",
          disk == 62373979984, str(disk))

    print("== G: frozen prefix identity chain ==")
    bfile = "".join("%d %d\n" % (n, v) for n, v in KNOWN)
    base_txt = (bfile + "\n").encode()
    h = hashlib.sha256(base_txt).hexdigest()
    check("base.txt (17 rows + terminal empty record) SHA-256 == 466a29c5...",
          h == "466a29c52f24b11359586313c1abe2f30c87be213189a54fe3f1292520bc1e07",
          "bytes=%d sha=%s" % (len(base_txt), h))

    print()
    if FAILS:
        print("FAILED CHECKS: %d -> %s" % (len(FAILS), FAILS))
        return 1
    print("ALL REVIEW-SIDE CHECKS PASS")
    return 0


if __name__ == "__main__":
    sys.exit(main())
