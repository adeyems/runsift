import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path
from runsift import compare, main, render_text

class TextReportTest(unittest.TestCase):
    def test_coverage_timing_and_no_raw_logs(self):
        before = {'version': 1, 'run_id': 'before', 'jobs': [{'id': 'build', 'status': 'passed', 'duration_ms': 100, 'tests': []}]}
        after = {'version': 1, 'run_id': 'after', 'jobs': [{'id': 'build', 'status': 'failed', 'duration_ms': 101, 'log_excerpt': 'PRIVATE_SYNTHETIC_EXCERPT'}]}
        text = render_text(compare(before, after, 5, 0))
        self.assertIn('passed -> failed', text)
        self.assertIn('+1 ms (within thresholds)', text)
        self.assertIn('coverage_changed', text)
        self.assertNotIn('PRIVATE_SYNTHETIC_EXCERPT', text)
        with tempfile.TemporaryDirectory() as temp:
            a, b = Path(temp)/'a.json', Path(temp)/'b.json'
            a.write_text(json.dumps(before)); b.write_text(json.dumps(after))
            with contextlib.redirect_stdout(io.StringIO()) as out:
                self.assertEqual(main([str(a), str(b), '--format', 'text']), 1)
            self.assertIn('DIFFERENT', out.getvalue())
            with contextlib.redirect_stdout(io.StringIO()) as out:
                self.assertEqual(main([str(a), str(a), '--format', 'text']), 0)
            self.assertIn('MATCH', out.getvalue())
