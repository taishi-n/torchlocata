# Paths and storage

## Existing data across projects

Set `LOCATA_ROOT=/path/to/LOCATA` once in your application environment, or pass
`root` explicitly. It identifies the unpacked directory containing `dev/` or
`eval/`, and needs no manifest. Lookup is explicit `root`, then `LOCATA_ROOT`,
then the managed root. Invalid configured paths raise errors without fallback.
The selected absolute path is frozen in the Dataset, including under spawn.

Reader construction performs no network requests or directory creation. It
never writes indexes or caches beneath a corpus. Use an explicit root to select
an installation independently of environment settings.

## Explicit preparation

Install `locata-torch[download]`, then call `download_locata` before creating
DataLoader workers, or use `locata-torch download --split dev`. The API accepts
`dev`, `eval`, or a nonempty sequence, removes duplicates, and installs splits
in deterministic order. Repeat CLI `--split` to request both splits. Progress and
errors go to stderr; successful CLI commands print the unpacked root to stdout.
`locata-torch path` checks dev by default; use `locata-torch path --split eval`
for an eval-only managed installation. Repeat `path --split` to require both.

Storage lookup is explicit `data_dir`/`--data-dir`, then `LOCATA_DATA_DIR`, then
`platformdirs.user_data_path("locata-torch", appauthor=False, ensure_exists=False)`.
This persistent location is shared across environments. `LOCATA_ROOT` never
changes the download destination. An existing unpacked root cannot be used as
`data_dir`; use a separate store. The reader accepts only completed managed
splits when relying on default lookup.

```text
<data_dir>/
├── archives/zenodo-3630471/    # ZIPs, .part files, and partial identity records
├── datasets/zenodo-3630471/   # Returned root with completed dev/ and/or eval/
├── state/zenodo-3630471/      # Installation inventory and attribution records
├── staging/                  # Owned temporary extraction directories
└── locks/                    # Per-split process locks
```

The data release key is independent of Python package versions. This avoids
copying a large corpus whenever the library is upgraded. Each split is an entire
official archive; task/array selection affects reading, not transfer size.

## Integrity, resume, and recovery

Only the pinned [Zenodo v1 release](https://zenodo.org/records/3630471) is supported,
DOI `10.5281/zenodo.3630471`. Downloads stream in bounded chunks, request identity
encoding, and validate response sizes and HTTP ranges on every attempt. Transfers
use 30-second socket timeouts and at most three attempts. Transient HTTP errors
and short responses retain an identified partial file. A server ignoring Range
restarts that partial safely. Invalid ranges, unexpected encoding, or HTTP 416
raise an error. There is no public source-URL override.

All retained bytes are hashed before the final archive is accepted. Exact size
and the publisher's MD5 must match before extraction. MD5 checks integrity against
the publisher's metadata; the source remains pinned to official HTTPS URLs.
Completed archives are retained for offline re-extraction.

The downloader checks available space and validates original ZIP64 member names,
including names changed by Python's platform-specific normalization. It rejects
unsafe paths, types, collisions, symlinks, and non-portable Windows filenames, and
streams extraction with ZIP CRC checks. It writes to a fresh staging directory
on the destination filesystem.
A prepared manifest precedes atomic split installation; a complete manifest
follows it. An interruption between these operations is recovered by checking
the recorded inventory. Partial extraction remains outside the readable root.
One process lock serializes preparation of each split; waiting is bounded to
60 seconds.

Repeated requests verify the complete inventory, sizes, and CRCs and reuse the
installation without network activity or corpus writes. This verification reads
every installed file and can take time on a large corpus. Unknown destinations,
incompatible records, or altered files raise errors; there is no automatic
repair, merge, deletion, or overwrite. A completed split remains usable if a
later requested split fails. Failed new extraction cleans only its own staging;
crash remnants without a prepared manifest are not deleted automatically.

Both retained ZIPs and expanded splits occupy about 103.8 GB; allow at least
120 GB for a fresh installation. The estimate comes from official archive
metadata, not a full installation in this checkout.

## Attribution and evidence

Managed manifests record the exact source URL, size, MD5, observed hash,
inventory, DOI, citation, and [ODC-BY 1.0](https://opendatacommons.org/licenses/by/1-0/)
dataset notice. The library code uses Apache-2.0. No LOCATA data is bundled or
redistributed by this package. Follow the dataset's attribution requirements
when using it in research or other tools.

The transfer and installation code is tested with local HTTP servers and small
synthetic ZIP64 archives. The reader is separately tested on the existing LOCATA
snapshot. Real final-release transfer and VAD payload validation remain unverified;
see the [validation record](validation.md).
