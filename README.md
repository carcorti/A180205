# A180205: exact enumeration through n=28

Carlo Corti — Independent researcher — carlo.corti@outlook.com

**Release v1.0.1.** This package includes the manuscript source and matching
PDF, computational sources, canonical data and retained execution evidence.
The Zenodo series DOI identifies all releases; it does not identify one
immutable software version. Use the GitHub release tag for this exact package.

## Definition and result

For n>=1, count ordered permutations p of 0,...,n-1 admitting nonnegative
integers x[0],...,x[n] with `p[i] = x[i-1] + x[i]` for i=1,...,n. Witness
entries may repeat and may be zero. Reversals are counted separately.
The unique zero fixes the witness and separates two outward tails on
complementary actual label sets. The producer retains integer multiplicities;
it does not count Boolean reachability or standardize numerical label values.

`data/b180205.txt` contains exactly28 contiguous `n a(n)` rows, offset1,
and one terminal empty line (LF LF). The endpoint is
`a(28) = 1226245772785310491672576`. Rows1..17 reproduce the historical
R. H. Hardin baseline; rows18..28 are11 additional locally validated values.
Preliminary Meta AI candidates18/19 predated their official validation on
16 November2026; they are not presented as first appearing in those runs.
The first index uncomputed locally is29; this is not a worldwide-priority claim.

## Essential files

| Path | Role |
|---|---|
| `paper/A180205.tex`, `paper/A180205.pdf` | English monolithic manuscript with inline bibliography and matching PDF |
| `src/a180205.c`, `src/Makefile` | Exact reviewed producer source and publication build/check routing |
| `check/ie.cpp`, `check/crt.py` | Exact repeated-label IE source and original fail-closed CRT driver |
| `check/scalar.py`, `check/first18.py` | Original MiniMax scalar implementation and path-adapted wrapper |
| `check/test.py`, `check/book.py`, `check/hostile.py` | Exact historical known-domain regression sources, restored to their original layout for use |
| `check/shapes.py` | Isolated clone/archive/inventory and semantic rejection probes |
| `check/verify.py` | New bounded publication driver: inventory, evidence, stored-residue reconstruction, descriptor and small-domain checks |
| `proof/proof.tgz`, `proof/index.json` | Selected original runs, execution/build identities and qualification records; flat short archive names mapped to original paths, sizes, hashes, modes and roles |
| `proof/path.diff` | Complete Makefile/first18 publication-only routing differences |
| `LICENSE`, `CITATION.cff`, `.gitignore`, `sha256.txt` | Author-supplied MIT license, citation metadata, generated-file exclusions and exact payload inventory |

The original scientific C/C++/CRT code is unchanged. The public Makefile changes
`validation` to the short directory `check` and sends `make test` to the
bounded publication driver. Optimization/warning/link flags are unchanged.
The first18 wrapper changes only its dependency path to `check/scalar.py`.
The original Makefile/wrapper and historical executable identities remain in
the indexed evidence. A fresh public build has its own identity and is never
passed off as the original official run.

The evidence archive has345 logical original records,237 unique compressed
members and1834065 expanded unique bytes; its compressed size is266906 bytes.
Exact source files already visible in the payload are shared by the index,
not archived twice. Original path strings in logs/index are historical
provenance; the documented commands require no private workspace file.

## Verify retained results

Run from the extracted repository root; Python3.11 or later, standard library
only, no network or native binary execution required:

```bash
python3 -B check/verify.py
```

This requires the exact payload inventory, archive member identities and
canonical28-row table. It restores the selected original layout only in
automatically removed temporary storage, runs the exact original CRT source
against the retained18/26/28 residues and their committed controls/build
identities, and compares every row. It checks the original producer journal's
rank partitions, chained records and final chunk/cursor descriptors.
It also executes the definition-only interval predicate on every permutation
through8 and the original unpacked scalar recurrence through18.
Expected final output includes `PUBLIC PACKAGE CHECK PASS`, `rows: 28`,
`new_terms: false`, `original_F_W_replay: false`.

The interval/descriptor portions of this driver are new publication-side
checks, not the original regression script or independent third-party
replication. Producer, IE and scalar Python share the zero decomposition,
actual-label scalar transition and ordered-tail product; Python also uses
the parity restriction, without parity-packed storage. IE is a different
aggregation over repeatable alphabets. CRT uniqueness uses coprimality and
the factorial bound, conditional on correct complete residues. Digests and
work totals do not alone prove arithmetic correctness or faithful execution.

## Build and bounded native smoke

Original toolchain: GCC/G++13.3.0, Python3.12.3, OpenSSL3.0.13, Linux Mint22.3,
AMD Ryzen9 7940HS,64GB DDR5, eight OpenMP workers in the official run.
The smoke requires Linux, `make`, `gcc-13`, `g++-13`, OpenMP/libgomp and
OpenSSL development headers/libcrypto. The Makefile contains the exact flags;
`-march=native` makes rebuilt binaries host-specific. Historical executables
in the evidence serve original byte-identity checks and are not portable builds.

```bash
python3 -B check/verify.py --build
```

Equivalent check target:

```bash
make -C src test
```

The driver compiles in disposable storage, runs self-tests, producer/IE through8,
read-only checks, CRT comparison and all128 true-label subset coefficients
against exhaustive orders. Temporary binaries and fixtures are removed even
on failure. No full28-term census, capacity30 fixture or sanitizer campaign
is started. Plain `make -C src all ie` builds local binaries; those are
generated outputs, not part of the frozen publication inventory. Remove them
with `make -C src clean` before checking the exact payload again.

## Manuscript check

The TeX uses standard article/AMS/Latin Modern/geometry/microtype/hyperref
packages, with no scientific input/include or external bibliography file.
With pdflatex installed:

```bash
python3 -B check/verify.py --tex
```

Two draftmode/no-shell-escape passes check references and box warnings in
temporary storage; no PDF is produced. Source checks do not inspect a rendered
PDF. The delivered PDF is generated from the same source and is included in
the checksum inventory. It contains the verified Zenodo series DOI.

To rebuild the PDF with pdfLaTeX, run from the repository root:

```bash
set -eu
build_dir=$(mktemp -d)
trap 'rm -rf "$build_dir"' EXIT
for pass in 1 2 3; do
  pdflatex -no-shell-escape -interaction=nonstopmode -halt-on-error \
    -output-directory "$build_dir" paper/A180205.tex
done
if grep -Eq 'Warning:|Error:|pdfTeX warning|Overfull|Underfull|Undefined control sequence|^!' "$build_dir/A180205.log"; then
  cat "$build_dir/A180205.log"
  exit 1
fi
cp "$build_dir/A180205.pdf" paper/A180205.pdf
```

A regenerated PDF may have different metadata bytes. Its SHA-256 must be
refreshed in `sha256.txt` before the exact-inventory verification is rerun.
The delivered PDF is retained by Git; `.gitignore` excludes only TeX auxiliary
files, Python caches and the two documented locally built executables.

## Isolated publication-shape audit

On Linux with bubblewrap user/mount namespaces enabled, the actual audit driver
is included so its evidence does not depend on a private preparation script:
run this audit from an extracted source archive, without a `.git` directory.
The ordinary verification commands above also support Git clones.

```bash
python3 -B check/shapes.py
```

It runs three positive payload shapes and eight rejection controls, including
missing/altered PDFs and a changed manuscript count with freshly updated
checksums. Each execution mounts
only the payload and standard system tools; `/home/carlo` is absent and the
payload is read-only. The first shape also builds/smokes the native code and
checks TeX in draftmode. All copy/archive/fixture roots are temporary and removed.
This is local validation, not PRE-UPLOAD or distributed-release verification.

## Historical evidence and limits

Restore the selected original records, if desired, into an absent directory
whose parent already exists, outside this publication tree:

```bash
python3 -B check/verify.py --restore /tmp/a180205-hist
```

The index validates every restored path, byte size, hash and mode. The root
must be new; existing destinations are refused. This runs no census. The
restored `src/Makefile`, source and original binaries match the original
records. The three historical Python regression sources expect that original
`validation/` layout and the17-row baseline, not the public28-row b-file.
For a deliberately chosen bounded re-execution of that old suite, use a fresh
restoration, create its `data/` directory, copy `runs/n18/oldb.txt` there as
`b180205.txt`, then run `make -C /tmp/a180205-hist/src test`. This is optional;
the publication smoke does not rerun the historical full suite.

Original qualification records distinguish ASan/UBSan<=17 with leak detection
off, Valgrind<=8 on the compatible x86-64-v3 build (possible OpenMP runtime
allocation disclosed), and inherited TSan/Archer on earlier builds with the
same parallel kernel. They are historical evidence, not fresh qualification
of a rebuilt public binary. Wider reviewer computations remain reported,
without expanding retained local validation domains. Review conversations,
obsolete drafts and service trees are not publication inputs.

Original large F/W intermediate tables and obsolete diagnostic payloads have
been intentionally discarded. They are not private dependencies or members of
this package. Stored-residue reconstruction and bounded checks remain runnable;
a full native-table audit on those original bytes is no longer available.
Regenerating tables would require new execution and would produce new records.
The package does not conceal this as lossless archival retention.

The run28 peak RSS was not measured. Principal arrays model about10.37GiB
(about10.62GiB with allowance). The earlier synthetic fixture measured
45821034496B RSS versus45818139392B arrays; it was not a computation through30.
Final command wall times total about1185s, excluding operator pauses. Exact
measurements remain in original indexed records rather than duplicate tables.

## Attribution, citation and status

Definition/baseline: [OEIS A180205](https://oeis.org/A180205), R. H. Hardin,
15 August2010. The manuscript cites actual related OEIS entries and their
contributors, the distinct four-window A180207 work, the colex article and
the versioned GCC manual. External literature is cited, not redistributed.
The existing MIT license is preserved; no additional license grant is invented.
Use CITATION.cff's preferred article metadata for this study.

Repository: https://github.com/carcorti/A180205

Zenodo release series: https://doi.org/10.5281/zenodo.24311714

Exact GitHub release: https://github.com/carcorti/A180205/releases/tag/v1.0.1

The series DOI may resolve to the latest archived release. Until Zenodo has
ingested v1.0.1, its latest version can still be v1.0; the GitHub tag identifies
this package without ambiguity. The previous v1.0 release remains immutable.
