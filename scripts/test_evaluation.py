import math
import unittest
from scripts.evaluate import metrics
from scripts.prepare_data import clean, skills, demo

class EvaluationTests(unittest.TestCase):
    def test_metrics_perfect_ranking(self):
        result=metrics([{'id':str(i)} for i in range(5)],{str(i):3 for i in range(5)})
        self.assertEqual(result,{'precision_at_5':1,'ndcg_at_10':1,'coverage':1})
    def test_empty_results_are_penalised(self):
        self.assertEqual(metrics([],{"x":3}),{'precision_at_5':0,'ndcg_at_10':0,'coverage':0})
    def test_short_list_precision_denominator_is_five(self):
        self.assertEqual(metrics([{'id':'a'}],{'a':3})['precision_at_5'],.2)
    def test_lower_rank_is_discounted(self):
        result=metrics([{'id':'b'},{'id':'a'}],{'a':3})
        self.assertAlmostEqual(result['ndcg_at_10'],1/math.log2(3))
    def test_strip_source_markup(self):
        self.assertEqual(clean('&lt;p&gt;Hello &amp; welcome&lt;/p&gt;'),'Hello & welcome')
    def test_skill_boundaries(self):
        self.assertIn('Go',skills('Go and Flutter'))
        self.assertNotIn('Go',skills('Google Django governance'))
    def test_fixtures_labelled_and_identifiable(self):
        jobs,_=demo();self.assertEqual(len(jobs),len({j['id'] for j in jobs}))
        self.assertTrue(all(j['source']=='Synthetic fixture' and not j['url'] for j in jobs))
if __name__=='__main__':unittest.main()
