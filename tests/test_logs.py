import copy
import unittest
from runsift import compare, validate

class LogTest(unittest.TestCase):
    def test_exact_grouping_and_missing_coverage(self):
        jobs=[{'id':name,'status':'failed','duration_ms':0,'log_excerpt':text} for name,text in [('a','synthetic failure'),('b','synthetic failure'),('c','other')]]
        jobs.append({'id':'missing','status':'failed','duration_ms':0})
        bundle={'version':1,'run_id':'r','jobs':jobs}
        report=compare(bundle,copy.deepcopy(bundle))
        grouped=report['failure_groups']['baseline']
        self.assertEqual(grouped['without_excerpt'],['missing'])
        self.assertIn(['a','b'],[g['job_ids'] for g in grouped['groups']])
        self.assertTrue(report['match'])
        self.assertNotIn('synthetic failure',str(report))
    def test_bounded_and_control_free(self):
        for text in ['é'*2049, '\x1b[31m', 123]:
            with self.assertRaises(ValueError): validate({'version':1,'run_id':'r','jobs':[{'id':'a','status':'failed','duration_ms':0,'log_excerpt':text}]})
