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
