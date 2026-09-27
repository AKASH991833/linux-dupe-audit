#!/usr/bin/env python3
"""Read-only duplicate-file and similar-image auditor for local folders."""
from __future__ import annotations

import argparse
import csv
import hashlib
import os
import sys
from collections import defaultdict
from pathlib import Path

IMAGE_EXTENSIONS = {'.jpg', '.jpeg', '.png', '.webp', '.bmp', '.tif', '.tiff', '.gif'}
CHUNK_SIZE = 1024 * 1024


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for chunk in iter(lambda: stream.read(CHUNK_SIZE), b''):
            digest.update(chunk)
    return digest.hexdigest()


def walk_files(root: Path, follow_symlinks: bool = False):
    """Yield regular files in deterministic order, never following links by default."""
    def onerror(error):
        print(f'warning: cannot access {error.filename}: {error}', file=sys.stderr)

    for folder, dirs, files in os.walk(root, followlinks=follow_symlinks, onerror=onerror):
        dirs[:] = sorted(d for d in dirs if follow_symlinks or not (Path(folder) / d).is_symlink())
        for name in sorted(files):
            path = Path(folder) / name
            if not follow_symlinks and path.is_symlink():
                continue
            if path.is_file():
                yield path


def exact_groups(paths):
    """Hash only files of equal size, then group equal SHA-256 digests."""
    sizes = defaultdict(list)
    errors = []
    for path in paths:
        try:
            sizes[path.stat().st_size].append(path)
        except OSError as exc:
            errors.append((path, str(exc)))
    hashes = defaultdict(list)
    for size, candidates in sizes.items():
        if len(candidates) < 2:
            continue
        for path in candidates:
            try:
                hashes[(size, sha256(path))].append(path)
            except OSError as exc:
                errors.append((path, str(exc)))
    groups = [sorted(group) for group in hashes.values() if len(group) > 1]
    groups.sort(key=lambda group: str(group[0]))
    return groups, errors


def dhash(path: Path) -> int:
    """64-bit difference hash; ignores file metadata but not major visual changes."""
    from PIL import Image, ImageOps
    with Image.open(path) as source:
        image = ImageOps.exif_transpose(source).convert('L').resize((9, 8), Image.Resampling.LANCZOS)
        pixels = list(image.get_flattened_data() if hasattr(image, 'get_flattened_data') else image.getdata())
    result = 0
    for y in range(8):
        for x in range(8):
            result = (result << 1) | int(pixels[y * 9 + x] > pixels[y * 9 + x + 1])
    return result


def similar_pairs(paths, threshold: int = 5):
    """Return candidate pairs (distance <= threshold), not transitive groups."""
    hashes = []
    errors = []
    for path in paths:
        if path.suffix.lower() not in IMAGE_EXTENSIONS:
            continue
        try:
            hashes.append((path, dhash(path)))
        except (OSError, ValueError) as exc:
            errors.append((path, str(exc)))
    pairs = []
    for i, (left, first) in enumerate(hashes):
        for right, second in hashes[i + 1:]:
            distance = (first ^ second).bit_count()
            if distance <= threshold:
                pairs.append((left, right, distance))
    return sorted(pairs, key=lambda x: (x[2], str(x[0]), str(x[1]))), errors


def review_and_delete(groups, input_fn=input):
    """Manually select exact copies; protect one survivor and rehash before unlinking."""
    removed = 0
    for number, group in enumerate(groups, 1):
        print(f'\nExact group {number}:')
        for index, path in enumerate(group, 1):
            print(f'  {index}. {path}')
        choice = input_fn('Numbers to DELETE (comma-separated; Enter skips): ').strip()
        if not choice:
            continue
        try:
            selected = [int(part.strip()) for part in choice.split(',')]
        except ValueError:
            print('Skipped: invalid selection.')
            continue
        if (not selected or len(set(selected)) != len(selected)
                or any(index < 1 or index > len(group) for index in selected)
                or len(selected) >= len(group)):
            print('Skipped: select distinct valid numbers and keep at least one copy.')
            continue
        survivors = [path for index, path in enumerate(group, 1) if index not in selected]
        try:
            fingerprints = []
            for path in group:
                if path.is_symlink() or not path.is_file():
                    raise OSError(f'file changed or became symlink: {path}')
                fingerprints.append((path.stat().st_size, sha256(path)))
            if len(set(fingerprints)) != 1:
                raise OSError('files changed since scan or are no longer identical')
        except OSError as exc:
            print(f'Skipped: {exc}', file=sys.stderr)
            continue
        targets = [group[index - 1] for index in selected]
        print('Keep:', ', '.join(map(str, survivors)))
        print('Permanently delete:', ', '.join(map(str, targets)))
        if input_fn('Type DELETE to confirm this group: ').strip() != 'DELETE':
            print('Skipped: not confirmed.')
            continue
        for path in targets:
            try:
                if path.is_symlink() or (path.stat().st_size, sha256(path)) != fingerprints[0]:
                    raise OSError('file changed before deletion')
                if not any(s.is_file() and not s.is_symlink() and
                           (s.stat().st_size, sha256(s)) == fingerprints[0]
                           for s in survivors):
                    raise OSError('no verified surviving copy')
                path.unlink()
                removed += 1
                print(f'Deleted: {path}')
            except OSError as exc:
                print(f'warning: could not delete {path}: {exc}', file=sys.stderr)
    print(f'\nPermanently deleted {removed} files.')
    return removed


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description='Read-only local duplicate audit; NEVER deletes files.')
    parser.add_argument('folder', type=Path, help='folder to scan recursively')
    parser.add_argument('--interactive', action='store_true', help='review and permanently delete selected EXACT copies only')
    parser.add_argument('--similar', action='store_true', help='also compare photos using dHash (requires Pillow)')
    parser.add_argument('--threshold', type=int, default=5, help='maximum dHash Hamming distance, 0-64 (default: 5)')
    parser.add_argument('--csv', type=Path, help='write report to this CSV (outside scanned folder recommended)')
    args = parser.parse_args(argv)
    if not args.folder.is_dir():
        parser.error('folder must be an existing directory')
    if not 0 <= args.threshold <= 64:
        parser.error('--threshold must be between 0 and 64')
    if args.similar:
        try:
            import PIL  # noqa: F401
        except ImportError:
            parser.error('photo matching needs Pillow: python3 -m pip install -r requirements.txt')
    files = list(walk_files(args.folder))
    if args.csv:
        output = args.csv.absolute()
        files = [path for path in files if path.absolute() != output]
    groups, errors = exact_groups(files)
    print(f'Scanned {len(files)} files. Exact duplicate groups: {len(groups)}.')
    rows = []
    exact_pairs = set()
    for number, group in enumerate(groups, 1):
        print(f'\nExact group {number} ({len(group)} files):')
        for path in group:
            print(f'  {path}')
            rows.append(('exact', number, '', str(path), ''))
        for i, left in enumerate(group):
            for right in group[i + 1:]:
                exact_pairs.add(frozenset((left, right)))
    if args.similar:
        pairs, image_errors = similar_pairs(files, args.threshold)
        errors.extend(image_errors)
        pairs = [pair for pair in pairs if frozenset(pair[:2]) not in exact_pairs]
        print(f'\nVisually similar candidate pairs (not exact duplicates): {len(pairs)}.')
        for number, (left, right, distance) in enumerate(pairs, 1):
            print(f'  {number}. distance={distance}: {left} <> {right}')
            rows.extend([('similar', number, distance, str(left), str(right))])
    if args.interactive:
        review_and_delete(groups)
    if args.csv:
        try:
            with args.csv.open('w', newline='', encoding='utf-8') as stream:
                writer = csv.writer(stream)
                writer.writerow(('kind', 'group', 'distance', 'path', 'other_path'))
                writer.writerows(rows)
            print(f'\nReport: {args.csv}')
        except OSError as exc:
            print(f'error: cannot write report: {exc}', file=sys.stderr)
            return 2
    for path, reason in errors:
        print(f'warning: skipped {path}: {reason}', file=sys.stderr)
    return 1 if errors else 0


if __name__ == '__main__':
    raise SystemExit(main())
