import tempfile
import unittest
from pathlib import Path

from PIL import Image
from dupe_audit import dhash, exact_groups, main, similar_pairs, walk_files, review_and_delete


class DuplicateAuditTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)

    def test_exact_and_same_size_different_content(self):
        (self.root / 'a').write_bytes(b'foo')
        (self.root / 'b').write_bytes(b'foo')
        (self.root / 'c').write_bytes(b'bar')
        groups, errors = exact_groups(list(walk_files(self.root)))
        self.assertEqual([[p.name for p in group] for group in groups], [['a', 'b']])
        self.assertEqual(errors, [])

    def test_skips_symlinks_by_default(self):
        (self.root / 'a').write_bytes(b'a')
        (self.root / 'alias').symlink_to(self.root / 'a')
        self.assertEqual([p.name for p in walk_files(self.root)], ['a'])

    def test_similar_reencoded_images(self):
        image = Image.new('RGB', (80, 80), 'white')
        for x in range(40):
            for y in range(80):
                image.putpixel((x, y), (0, 0, 0))
        png, jpg = self.root / 'a.png', self.root / 'b.jpg'
        image.save(png)
        image.save(jpg, quality=95)
        self.assertEqual(dhash(png), dhash(jpg))
        pairs, errors = similar_pairs([png, jpg], 0)
        self.assertEqual(len(pairs), 1)
        self.assertEqual(errors, [])

    def test_cli_report_does_not_delete(self):
        (self.root / 'one').write_bytes(b'same')
        (self.root / 'two').write_bytes(b'same')
        report = self.root / 'report.csv'
        self.assertEqual(main([str(self.root), '--csv', str(report)]), 0)
        self.assertIn('exact,1', report.read_text())
        self.assertTrue((self.root / 'one').exists())
        self.assertEqual(main([str(self.root), '--csv', str(report)]), 0)
        self.assertEqual(len(list(self.root.iterdir())), 3)

    def test_interactive_keeps_one_and_requires_confirmation(self):
        paths = [self.root / name for name in ('a', 'b', 'c')]
        for path in paths:
            path.write_bytes(b'same')
        answers = iter(['1,2,3', '1,2', 'no', '1,2', 'DELETE'])
        self.assertEqual(review_and_delete([paths], lambda _: next(answers)), 0)
        self.assertTrue(all(path.exists() for path in paths))
        self.assertEqual(review_and_delete([paths], lambda _: next(answers)), 0)
        self.assertTrue(all(path.exists() for path in paths))
        self.assertEqual(review_and_delete([paths], lambda _: next(answers)), 2)
        self.assertFalse(paths[0].exists())
        self.assertFalse(paths[1].exists())
        self.assertTrue(paths[2].exists())

    def test_interactive_rehashes_and_skips_changed_files(self):
        first, second = self.root / 'a', self.root / 'b'
        first.write_bytes(b'same')
        second.write_bytes(b'same')
        def changed(_):
            second.write_bytes(b'edit')
            return '1'
        self.assertEqual(review_and_delete([[first, second]], changed), 0)
        self.assertTrue(first.exists())

    def test_invalid_threshold(self):
        with self.assertRaises(SystemExit):
            main([str(self.root), '--threshold', '65'])


if __name__ == '__main__':
    unittest.main()
