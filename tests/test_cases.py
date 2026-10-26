import copy
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

from runsift import compare, validate


def bundle(cases=None):
    job = {'id': 'unit', 'status': 'passed', 'duration_ms': 10}
    if cases is not None:
        job['tests'] = cases
    return {'version': 1, 'run_id': 'demo', 'jobs': [job]}


def case(name, status='passed'):
    return {'id': name, 'status': status}


class CaseTest(unittest.TestCase):
    def test_old_bundles_keep_matching(self):
        result = compare(bundle(), bundle())
        self.assertTrue(result['match'])
        self.assertEqual(result['jobs'][0]['tests']['state'], 'unavailable')

    def test_reordering_and_no_mutation(self):
        a, b = bundle([case('a'), case('b')]), bundle([case('b'), case('a')])
        original = copy.deepcopy((a, b))
        self.assertTrue(compare(a, b)['match'])
        self.assertEqual((a, b), original)

    def test_failure_recovery_skips_and_renames(self):
        a = bundle([case('fails'), case('recovers', 'failed'), case('skip'), case('old')])
        b = bundle([case('fails', 'failed'), case('recovers'), case('skip', 'skipped'), case('new')])
        result = compare(a, b, 604800000, 10000)
        self.assertFalse(result['match'])
        self.assertEqual(result['summary']['changed'], 1)
        self.assertEqual(result['summary']['regressions'], 0)
        self.assertEqual(result['jobs'][0]['tests']['summary'],
                         dict(added=1, removed=1, changed=3, unchanged=0, newly_failing=1, recovered=1))

    def test_missing_data_is_not_removed_tests(self):
        for a, b in [(bundle(), bundle([case('a')])), (bundle([case('a')]), bundle()), (bundle(), bundle([]))]:
            result = compare(a, b)
            self.assertFalse(result['match'])
            self.assertEqual(result['jobs'][0]['tests']['state'], 'coverage_changed')
            self.assertIsNone(result['jobs'][0]['tests']['summary'])
        self.assertEqual(compare(bundle([case('a')]), bundle([]))['jobs'][0]['tests']['summary']['removed'], 1)

    def test_added_removed_jobs_and_same_ids_in_different_jobs(self):
        a = bundle([case('same')])
        b = copy.deepcopy(a)
        b['jobs'].append(dict(b['jobs'][0], id='other'))
        validate(b)
        added = next(j for j in compare(a, b)['jobs'] if j['id'] == 'other')
        self.assertEqual(added['tests']['summary']['added'], 1)
        removed = next(j for j in compare(b, a)['jobs'] if j['id'] == 'other')
        self.assertEqual(removed['tests']['summary']['removed'], 1)

    def test_failure_labels_are_not_false_recovery(self):
        self.assertFalse(compare(bundle([case('x', 'failed')]), bundle([case('x', 'skipped')]))['jobs'][0]['tests']['cases'][0]['recovered'])
        added = compare(bundle([]), bundle([case('x', 'failed')]))['jobs'][0]['tests']['cases'][0]
        self.assertFalse(added['newly_failing'])
        self.assertEqual(added['candidate_status'], 'failed')

    def test_invalid_cases_and_limits(self):
        for cases in [[case('a'), case('a')], [{'id': 'a', 'status': 'running'}], [{'id': 'a'}],
                      [{'id': 'a', 'status': []}], [case('bad/id')], 'bad']:
            with self.subTest(cases=cases), self.assertRaises(ValueError):
                validate(bundle(cases))
        value = bundle([case(str(i)) for i in range(10000)])
        validate(value)
        value['jobs'].append({'id': 'other', 'status': 'passed', 'duration_ms': 0, 'tests': [case('extra')]})
        with self.assertRaises(ValueError):
            validate(value)
        value = bundle()
        value['jobs'][0]['tests'] = None
        with self.assertRaises(ValueError):
            validate(value)

    def test_cli_test_only_change(self):
        with tempfile.TemporaryDirectory() as folder:
            a, b = Path(folder) / 'a.json', Path(folder) / 'b.json'
            a.write_text(json.dumps(bundle([case('example')])))
            b.write_text(json.dumps(bundle([case('example', 'failed')])))
            result = subprocess.run([sys.executable, 'runsift.py', str(a), str(b)], capture_output=True, text=True)
            self.assertEqual(result.returncode, 1)
            self.assertEqual(json.loads(result.stdout)['jobs'][0]['tests']['summary']['newly_failing'], 1)
            self.assertEqual(result.stderr, '')
