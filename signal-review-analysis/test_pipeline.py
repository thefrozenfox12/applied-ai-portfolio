import unittest
from unittest.mock import patch
from pipeline import LABELS, payload, truth, clean, score
from emotions import classify

class IntegrityTests(unittest.TestCase):
    def test_request_contains_only_text_and_no_shared_history(self):
        binary=payload('A title','A review','binary')
        three=payload('Another title','Another review','three_class')
        import json
        self.assertEqual([m['role'] for m in binary['messages']],['system','user'])
        self.assertEqual(json.loads(binary['messages'][1]['content']),{'title':'A title','text':'A review'})
        self.assertNotIn('A review',three['messages'][1]['content'])
        self.assertEqual(binary['response_format']['json_schema']['schema']['properties']['sentiment']['enum'],['POSITIVE','NEGATIVE'])
        self.assertEqual(three['response_format']['json_schema']['schema']['properties']['sentiment']['enum'],['POSITIVE','NEUTRAL','NEGATIVE'])

    def test_explicit_rating_leakage_mask(self):
        for phrase in ['Five Stars','1 star','4-star','5/5','3 out of 5','★★★★★']:
            self.assertEqual(clean(phrase),'[rating omitted]')
        self.assertEqual(clean('Five gifts, but only one worked.'),'Five gifts, but only one worked.')

    def test_label_mapping_boundary(self):
        self.assertEqual([truth(i,'binary') for i in range(1,6)],['NEGATIVE']*3+['POSITIVE']*2)
        self.assertEqual([truth(i,'three_class') for i in range(1,6)],['NEGATIVE']*2+['NEUTRAL']+['POSITIVE']*2)

    def test_imbalanced_accuracy_does_not_hide_minority(self):
        rows=[{'actual':'POSITIVE','prediction':{'sentiment':'POSITIVE'},'rating_masked':False} for _ in range(9)]
        rows.append({'actual':'NEGATIVE','prediction':{'sentiment':'POSITIVE'},'rating_masked':False})
        m=score(rows,'binary')
        self.assertEqual(m['accuracy'],.9)
        self.assertEqual(m['balanced_accuracy'],.5)
        self.assertEqual(m['matrix'],[[9,0],[1,0]])
        self.assertEqual(m['per_class']['NEGATIVE']['precision'],0)

    def test_wordlist_ties_repetition_and_no_signal(self):
        lex={'happy':{'joy','trust'}}
        r=classify('Happy happy.',lex)
        self.assertEqual(r['scores']['joy'],2)
        self.assertEqual(r['tied'],['joy','trust'])
        self.assertEqual(r['emotion'],'joy')
        self.assertEqual(classify('xyz',lex)['emotion'],'none')
        self.assertEqual(classify('not happy',lex)['scores']['joy'],1)

if __name__=='__main__': unittest.main()
