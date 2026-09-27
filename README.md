# Linux Dupe Audit

A Python CLI for local Linux and Termux folders: detect exact duplicate files with SHA-256, flag visually similar photos with dHash, and optionally review exact copies for interactive deletion. It **never deletes by default**. It does not access Google Photos or cloud-only images.

## Install and run

Python 3.10+; exact matching uses the standard library. Pillow is needed for `--similar` and tests.

```bash
git clone https://github.com/AKASH991833/linux-dupe-audit.git
cd linux-dupe-audit
python3 -m pip install -r requirements.txt
python3 dupe_audit.py ~/Pictures
python3 dupe_audit.py ~/Pictures --similar --threshold 5 --csv ~/dupe-report.csv
python3 -m unittest discover -s tests -v
```

Exact mode groups equal-size files, then reads their SHA-256 digests in 1 MiB chunks. Similar mode normalizes EXIF orientation, converts supported images to grayscale and 9x8 pixels, and compares their 64-bit difference hashes. Threshold 0 means the closest hash match; default 5 allows modest changes. Similar matches are *candidates*, not proof: compressed/resized photos may match, but flat images can falsely match and crops/rotations can be missed. Similar comparisons take O(n²) in the image count. Animated GIFs use their first frame. Inspect every match before removing anything.

CSV columns: `kind,group,distance,path,other_path`. A CSV path is excluded from the scanned set, but an existing report at that path is overwritten. Full local paths can reveal private information: don't share a report unreviewed. Symlinks are skipped by default; unreadable files are skipped with a warning and exit code 1. Invalid arguments and report errors exit 2.

## Android / Termux

This scans **files saved on the phone**, not photos that exist only in Google Photos. If all photos are cloud-only, download or export them to local storage first, with enough free space. No Google Photos API access is included.

```bash
pkg update
pkg install python git python-pillow
termux-setup-storage  # accept the Android storage prompt
git clone https://github.com/AKASH991833/linux-dupe-audit.git
cd linux-dupe-audit
python dupe_audit.py ~/storage/pictures --similar
```

If `python-pillow` is not available on your Termux build, try `python -m pip install Pillow`. The folder may instead be `~/storage/downloads`; choose where your downloaded photos really are. Check Termux storage permission in Android Settings if access is denied.

## Select and delete exact duplicates

```bash
python3 dupe_audit.py ~/Pictures --interactive
# In Termux: python dupe_audit.py ~/storage/pictures --interactive
```

Each exact SHA-256 group is numbered. Enter comma-separated numbers to delete, or press Enter to skip. You must leave at least one copy. Before deletion the tool rehashes the files, shows the survivors and selected paths, and requires typing `DELETE` for that group. **Deletion is permanent local deletion, not Google Photos Trash.** Back up first; Android/cloud sync behavior can vary. Visually similar matches are *never* offered for deletion because their match is approximate.

## Files

- `dupe_audit.py`: CLI, exact hash, dHash, CSV, reviewed deletion.
- `tests/test_dupe_audit.py`: unit tests including unchanged files, symlinks, re-encoded images, and deletion safeguards.
- `requirements.txt`: Pillow for images/tests.

SHA-256 collisions are theoretically possible. This is a practical duplicate audit, not a cryptographic guarantee or a substitute for checking your backups.
