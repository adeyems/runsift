import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from runsift import MAX_BYTES, compare, load, validate


def bundle(*jobs, run='demo'):
    return {'version': 1, 'run_id': run, 'jobs': list(jobs)}


def job(name='unit', status='passed', duration=10):
    return {'id': name, 'status': status, 'duration_ms': duration}


class RunSiftTest(unittest.TestCase):
    def test_identity_and_job_order_do_not_create_changes(self):
        a = bundle(job('a'), job('b'), run='before')
        b = bundle(job('b'), job('a'), run='after')
        self.assertTrue(compare(a, b)['match'])
        self.assertEqual([j['id'] for j in compare(a, b)['jobs']], ['a', 'b'])

    def test_added_removed_and_empty(self):
        result = compare(bundle(job('old')), bundle(job('new', 'failed')))
        self.assertEqual(result['summary']['added'], 1)
        self.assertEqual(result['summary']['removed'], 1)
        self.assertEqual(result['summary']['regressions'], 0)
        self.assertTrue(all(j['duration_delta_ms'] is None for j in result['jobs']))
        self.assertTrue(compare(bundle(), bundle())['match'])

    def test_status_transitions(self):
        for status in ['failed', 'skipped', 'cancelled']:
            with self.subTest(status=status):
                self.assertEqual(compare(bundle(job()), bundle(job(status=status)))['summary']['regressions'], 1)
                self.assertEqual(compare(bundle(job(status=status)), bundle(job()))['summary']['recoveries'], 1)
        self.assertEqual(compare(bundle(job(status='failed')), bundle(job(status='cancelled')))['summary']['recoveries'], 0)

    def test_duration_deltas_including_zero(self):
        for duration, delta in [(0, -10), (10, 0), (15, 5)]:
            result = compare(bundle(job()), bundle(job(duration=duration)))
            self.assertEqual(result['jobs'][0]['duration_delta_ms'], delta)
            self.assertEqual(result['match'], delta == 0)
            self.assertEqual(result['summary']['regressions'], 0)

    def test_repeatable_and_no_input_mutation(self):
        a, b = bundle(job()), bundle(job(status='failed'))
        original = copy.deepcopy((a, b))
        self.assertEqual(compare(a, b), compare(a, b))
        self.assertEqual((a, b), original)

    def test_invalid_root_and_version(self):
        for value in [[], {}, dict(bundle(), version=True), dict(bundle(), version=2), dict(bundle(), extra=1)]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate(value)

    def test_invalid_jobs(self):
        for value in [job(status=[]), job(status='running'), job(duration=True), job(duration=-1),
                      job(duration=1.5), job(duration=604800001), job(name='bad/name'), job(name='\x1b'), {}, None]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                validate(bundle(value))
        with self.assertRaises(ValueError):
            validate(bundle(job(), job()))
        with self.assertRaises(ValueError):
            validate(bundle(*[job(str(i)) for i in range(1001)]))

    def test_input_boundaries(self):
        validate(bundle(job(name='x' * 128, duration=604800000)))
        validate(bundle(*[job(str(i)) for i in range(1000)]))
        with self.assertRaises(ValueError):
            validate(bundle(job(name='x' * 129)))

    def test_bad_json_encoding_duplicates_and_size(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / 'bad.json'
            for raw in [b'{', b'\xff', b'{"version":1,"version":1}', b'{"x":NaN}',
                        b'[' * 2000 + b']' * 2000, b'x' * (MAX_BYTES + 1)]:
                path.write_bytes(raw)
                with self.assertRaises(ValueError):
                    load(path)

    def test_example_report(self):
        result = compare(load('examples/baseline.json'), load('examples/candidate.json'))
        self.assertEqual(result['summary'], dict(added=1, removed=1, changed=1, unchanged=1, regressions=1, recoveries=0))

    def test_cli_exit_codes_and_streams(self):
        for candidate, code in [('examples/baseline.json', 0), ('examples/candidate.json', 1), ('missing.json', 2)]:
            result = subprocess.run([sys.executable, 'runsift.py', 'examples/baseline.json', candidate], capture_output=True, text=True)
            self.assertEqual(result.returncode, code)
            parsed = json.loads(result.stderr if code == 2 else result.stdout)
            self.assertIn('error' if code == 2 else 'summary', parsed)
            self.assertEqual(result.stdout if code == 2 else result.stderr, '')

    def test_same_failing_runs_match_without_claiming_success(self):
        result = compare(bundle(job(status='failed')), bundle(job(status='failed')))
        self.assertTrue(result['match'])
        self.assertEqual(result['jobs'][0]['candidate_status'], 'failed')
