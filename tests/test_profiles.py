import json
import tempfile
import unittest
from pathlib import Path
from runsift import load_profile, save_profile, main

class ProfileTest(unittest.TestCase):
    def test_roundtrip_and_no_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'p.json'
            save_profile(path, 50, 10)
            self.assertEqual(load_profile(path)['duration_threshold_ms'], 50)
            with self.assertRaises(FileExistsError): save_profile(path, 0, 0)
            self.assertEqual(load_profile(path)['duration_threshold_percent'], 10)
    def test_invalid_profiles(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'p.json'
            for value in ['{}', '{"version":1,"version":1}', ' '*4097, json.dumps({'version': True, 'duration_threshold_ms': 0, 'duration_threshold_percent': 0}), json.dumps({'version': 1, 'duration_threshold_ms': -1, 'duration_threshold_percent': 0})]:
                path.write_text(value)
                with self.assertRaises(ValueError): load_profile(path)
    def test_cli_profile_conflict(self):
        self.assertEqual(main(['missing', 'missing', '--profile', 'p', '--duration-threshold-ms', '0']), 2)
    def test_cli_save_and_reuse(self):
        import io
        from contextlib import redirect_stdout
        with tempfile.TemporaryDirectory() as directory:
            a, b, profile = [Path(directory) / name for name in ('a.json', 'b.json', 'profile.json')]
            bundle = {'version': 1, 'run_id': 'demo', 'jobs': [{'id':'job','status':'passed','duration_ms':100}]}
            a.write_text(json.dumps(bundle))
            bundle['jobs'][0]['duration_ms'] = 120
            b.write_text(json.dumps(bundle))
            with redirect_stdout(io.StringIO()):
                self.assertEqual(main([str(a), str(b), '--duration-threshold-ms', '30', '--save-profile', str(profile)]), 0)
                self.assertEqual(main([str(a), str(b), '--profile', str(profile)]), 0)
