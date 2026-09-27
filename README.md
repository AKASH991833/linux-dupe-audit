# Linux Dupe Audit

A **read-only** Python CLI for auditing local folders on Linux. It finds byte-identical files with SHA-256 and, optionally, suggests visually similar photos using dHash. No delete, trash, or overwrite operation exists. Review results yourself before removing anything.

## Why two hashes?

| Mode | What it detects | Limit |
| --- | --- | --- |
| Exact (default) | Files with the same size and SHA-256 content digest | A resize, compression, metadata change, or re-encoding changes the digest. |
| `--similar` | Image pairs whose 64-bit difference hashes are close | An *approximate visual candidate*, not proof of identical content; false positives and misses are possible. |

The scanner compares same-size files only in exact mode, then hashes them in 1 MiB chunks. Similar mode normalizes EXIF orientation, converts to grayscale, scales to 9x8, and compares adjacent pixels. Hamming distance 0 is the closest; the default threshold of 5 is a starting point, not a guarantee. Pairwise comparison is O(n²) in the number of supported images; use small folders first. Animated GIFs use the first frame. Screenshots, flat-color images, rotated/cropped pictures, and different aspect ratios can produce misleading matches. **Always inspect the files before deciding to delete.**

## Quick start

Python 3.10+ recommended. Exact matching uses only the standard library; photo matching and tests need Pillow.

```bash
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -r requirements.txt
python3 dupe_audit.py ~/Pictures
python3 dupe_audit.py ~/Pictures --similar --threshold 5 --csv ~/dupe-report.csv
```

To run only exact matching without installing anything: `python3 dupe_audit.py ~/Downloads`. For a stricter photo search use `--threshold 0`. `--threshold` accepts 0-64, and `--similar` must be enabled for it to affect the report. Paths with spaces work if quoted. CSV columns are `kind,group,distance,path,other_path`; exact groups have one row per path, similar candidates one row per pair. The CSV is overwritten if it already exists, so choose an output path carefully; the report file itself is excluded from the scan if it lies inside the folder.

```bash
python3 -m unittest discover -s tests -v
python3 dupe_audit.py --help
```

### Example

```text
Scanned 3 files. Exact duplicate groups: 1.

Exact group 1 (2 files):
  /home/akash/Pictures/a.jpg
  /home/akash/Pictures/copy/a.jpg

Visually similar candidate pairs (not exact duplicates): 1.
  1. distance=2: /home/akash/Pictures/a.jpg <> /home/akash/Pictures/a-small.jpg
```

## Safety and scope

- No symlink traversal by default; inaccessible files are skipped with warnings and exit code 1. The CLI never modifies scanned files. An invalid argument or report write failure exits 2.
- `--csv` writes a report and may overwrite an existing report. Don't run against sensitive folders if you plan to share its output: full local paths are printed and stored in CSV.
- This audits **local files only**. It does not access Google Photos or any cloud account. To scan a cloud library, export it first and review the export's privacy and storage needs.
- Matching SHA-256 digests is a practical exact-duplicate test, not a byte-by-byte final comparison. Extremely unlikely hash collisions remain theoretically possible.

## Project layout

- `dupe_audit.py` - CLI, streaming SHA-256 scan, image dHash, CSV report.
- `tests/test_dupe_audit.py` - tests for content grouping, symlinks, re-encoded images, non-deletion, report behavior.
- `requirements.txt` - Pillow for similar-image mode and tests.

Built as a small Linux operations tool: deterministic scans, predictable exit codes, no destructive defaults, and tests before changes.
