import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from runsift import compare


def bundle(duration, status='passed'):
    return {'version': 1, 'run_id': 'synthetic', 'jobs': [{'id': 'unit', 'status': status, 'duration_ms': duration}]}


class ThresholdTest(unittest.TestCase):
    def test_absolute_boundary(self):
        for delta, match in [(99, True), (100, True), (101, False), (-100, True), (-101, False)]:
            with self.subTest(delta=delta):
                result = compare(bundle(1000), bundle(1000 + delta), duration_threshold_ms=100)
                self.assertEqual(result['match'], match)
                self.assertEqual(result['jobs'][0]['duration_delta_ms'], delta)
                self.assertEqual(result['jobs'][0]['duration_change_ignored'], match)

    def test_percent_boundary(self):
        for delta, match in [(99, True), (100, True), (101, False), (-100, True), (-101, False)]:
            self.assertEqual(compare(bundle(1000), bundle(1000 + delta), duration_threshold_percent=10)['match'], match)

    def test_both_must_be_exceeded(self):
        self.assertTrue(compare(bundle(1000), bundle(1150), 100, 20)['match'])
        self.assertTrue(compare(bundle(1000), bundle(1150), 200, 10)['match'])
        self.assertFalse(compare(bundle(1000), bundle(1201), 100, 20)['match'])

    def test_zero_baseline_and_zero_delta(self):
        self.assertFalse(compare(bundle(0), bundle(1), 0, 10000)['match'])
        result = compare(bundle(0), bundle(1), 1, 10000)
        self.assertTrue(result['match'])
        self.assertTrue(result['jobs'][0]['duration_change_ignored'])
        same = compare(bundle(0), bundle(0))['jobs'][0]
        self.assertFalse(same['duration_change_ignored'])
        self.assertFalse(same['duration_change_exceeds_thresholds'])

    def test_fractional_boundary_uses_exact_integer_math(self):
        self.assertTrue(compare(bundle(3), bundle(4), duration_threshold_percent=34)['match'])
        self.assertFalse(compare(bundle(3), bundle(4), duration_threshold_percent=33)['match'])

    def test_status_and_membership_never_ignored(self):
        result = compare(bundle(1000), bundle(1001, 'failed'), 604800000, 10000)
        self.assertFalse(result['match'])
        self.assertEqual(result['summary']['regressions'], 1)
        self.assertTrue(result['jobs'][0]['duration_change_ignored'])
        empty = dict(bundle(0), jobs=[])
        for a, b in [(empty, bundle(10)), (bundle(10), empty)]:
            result = compare(a, b, 604800000, 10000)
            self.assertFalse(result['match'])
            self.assertIsNone(result['jobs'][0]['duration_change_exceeds_thresholds'])
            self.assertIsNone(result['jobs'][0]['duration_change_ignored'])

    def test_defaults_and_rules_are_visible(self):
        a, b = bundle(100), bundle(101)
        original = copy.deepcopy((a, b))
        self.assertEqual(compare(a, b), compare(a, b, 0, 0))
        result = compare(a, b, 2, 3)
        self.assertEqual(result['comparison_rules']['duration_threshold_ms'], 2)
        self.assertEqual(result['comparison_rules']['duration_threshold_percent'], 3)
        self.assertEqual(result['summary']['unchanged'], 1)
        self.assertEqual((a, b), original)

    def test_invalid_thresholds(self):
        for value in [-1, True, 1.5, '10', None, 604800001]:
            with self.subTest(ms=value), self.assertRaises(ValueError):
                compare(bundle(0), bundle(0), duration_threshold_ms=value)
        for value in [-1, True, 1.5, '10', None, 10001]:
            with self.subTest(percent=value), self.assertRaises(ValueError):
                compare(bundle(0), bundle(0), duration_threshold_percent=value)

    def test_cli_tolerance_and_invalid_options(self):
        with tempfile.TemporaryDirectory() as folder:
            a, b = Path(folder) / 'a.json', Path(folder) / 'b.json'
            a.write_text(json.dumps(bundle(1000)))
            b.write_text(json.dumps(bundle(1100)))
            prefix = [sys.executable, 'runsift.py', str(a), str(b)]
            for options, code in [([], 1), (['--duration-threshold-ms', '100'], 0),
                                  (['--duration-threshold-percent', '10'], 0),
                                  (['--duration-threshold-ms', '-1'], 2)]:
                result = subprocess.run(prefix + options, capture_output=True, text=True)
                self.assertEqual(result.returncode, code)
                self.assertIn('error' if code == 2 else 'comparison_rules', json.loads(result.stderr if code == 2 else result.stdout))
            invalid = subprocess.run(prefix + ['--duration-threshold-percent', '1.5'], capture_output=True, text=True)
            self.assertEqual(invalid.returncode, 2)
            self.assertEqual(invalid.stdout, '')
