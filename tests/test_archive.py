import json
import tempfile
import unittest
from pathlib import Path
from runsift import archive_bundle, load
class ArchiveTest(unittest.TestCase):
    def test_roundtrip_and_duplicate_preserves_original(self):
        with tempfile.TemporaryDirectory() as folder:
            root=Path(folder);archive=root/'archive';archive.mkdir();source=root/'source.json'
            bundle={'version':1,'run_id':'run-1','jobs':[]};source.write_text(json.dumps(bundle))
            destination=archive_bundle(source,archive)
            self.assertEqual(load(destination),bundle)
            original=destination.read_bytes()
            with self.assertRaises(FileExistsError):archive_bundle(source,archive)
            self.assertEqual(original,destination.read_bytes())
            bundle['run_id']='../escape';source.write_text(json.dumps(bundle))
            with self.assertRaises(ValueError):archive_bundle(source,archive)
            self.assertEqual(len(list(archive.iterdir())),1)

    def test_failed_sync_or_publication_leaves_no_archive(self):
        from unittest.mock import patch
        for operation in ('fsync', 'link'):
            with self.subTest(operation=operation), tempfile.TemporaryDirectory() as folder:
                root = Path(folder)
                archive = root / 'archive'
                archive.mkdir()
                source = root / 'source.json'
                source.write_text(json.dumps({'version': 1, 'run_id': 'run-1', 'jobs': []}))
                with patch('runsift.os.' + operation, side_effect=OSError('synthetic failure')):
                    with self.assertRaises(OSError):
                        archive_bundle(source, archive)
                self.assertEqual(list(archive.iterdir()), [])

    def test_concurrent_publishers_never_overwrite(self):
        from concurrent.futures import ThreadPoolExecutor
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            archive = root / 'archive'
            archive.mkdir()
            source = root / 'source.json'
            bundle = {'version': 1, 'run_id': 'run-1', 'jobs': []}
            source.write_text(json.dumps(bundle))
            def publish(_):
                try:
                    archive_bundle(source, archive)
                    return True
                except FileExistsError:
                    return False
            with ThreadPoolExecutor(max_workers=8) as pool:
                self.assertEqual(sum(pool.map(publish, range(16))), 1)
            self.assertEqual(load(archive / 'run-1.json'), bundle)
            self.assertEqual(len(list(archive.iterdir())), 1)
