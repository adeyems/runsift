import json
import tempfile
from pathlib import Path
import contextlib
import io
import unittest
from runsift import trend, main

class HistoryTest(unittest.TestCase):
    def bundle(self,name,status):
        return {'version':1,'run_id':name,'jobs':[] if status is None else [{'id':'job','status':status,'duration_ms':10}]}
    def test_missing_observation_breaks_transitions(self):
        result=trend([self.bundle('a','passed'),self.bundle('b',None),self.bundle('c','failed'),self.bundle('d','passed')])
        job=result['jobs'][0]
        self.assertEqual(job['adjacent_status_changes'],1)
        self.assertEqual(job['missing_runs'],1)
        self.assertEqual(job['failed_runs'],1)
        self.assertEqual(result['run_ids'],['a','b','c','d'])
    def test_duplicate_ids_and_bounds(self):
        for bundles in ([],[self.bundle('a','passed')],[self.bundle('a','passed')]*2,[self.bundle(str(i),'passed') for i in range(21)]):
            with self.assertRaises(ValueError):trend(bundles)
        with contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(main(['history']),2)

    def test_cli_reads_history_in_supplied_order(self):
        with tempfile.TemporaryDirectory() as folder:
            paths=[Path(folder)/name for name in ('first.json','second.json')]
            for path,name,state in zip(paths,('z','a'),('passed','failed')):
                path.write_text(json.dumps(self.bundle(name,state)))
            with contextlib.redirect_stdout(io.StringIO()) as out:
                self.assertEqual(main(['history',*map(str,paths)]),0)
            self.assertEqual(json.loads(out.getvalue())['run_ids'],['z','a'])
