import contextlib
import copy
import io
import json
import tempfile
import unittest
from pathlib import Path
from runsift import load, main, trend, validate
class LargeWorkloadTest(unittest.TestCase):
    def test_maximum_job_and_test_counts_through_cli_and_history(self):
        before={'version':1,'run_id':'before','jobs':[{'id':f'job-{i}','status':'passed','duration_ms':100,
                'tests':[{'id':f'case-{j}','status':'passed'} for j in range(10)]} for i in range(1000)]}
        after=copy.deepcopy(before);after['run_id']='after'
        for i,job in enumerate(after['jobs']):
            if i%2:job['status']='failed'
            if i%10==0:job['tests'][0]['status']='failed'
        with tempfile.TemporaryDirectory() as folder:
            a,b=Path(folder)/'a.json',Path(folder)/'b.json'
            a.write_text(json.dumps(before));b.write_text(json.dumps(after))
            self.assertEqual(len(load(a)['jobs']),1000)
            with contextlib.redirect_stdout(io.StringIO()) as out:
                self.assertEqual(main([str(a),str(b)]),1)
            report=json.loads(out.getvalue())
            self.assertEqual(report['summary']['changed'],600)
            self.assertEqual(report['summary']['regressions'],500)
            self.assertEqual(sum(j['tests']['summary']['newly_failing'] for j in report['jobs']),100)
        history=trend([{**before,'run_id':f'run-{i}'} for i in range(20)])
        self.assertEqual(len(history['jobs']),1000)
        self.assertTrue(all(j['observed_runs']==20 and j['adjacent_status_changes']==0 for j in history['jobs']))
        extra=copy.deepcopy(before);extra['jobs'][0]['tests'].append({'id':'overflow','status':'passed'})
        with self.assertRaisesRegex(ValueError,'10000'):validate(extra)
        extra=copy.deepcopy(before);extra['jobs'].append({'id':'overflow','status':'passed','duration_ms':0})
        with self.assertRaisesRegex(ValueError,'1000'):validate(extra)
