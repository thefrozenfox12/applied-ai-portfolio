import unittest
from analysis import emotion_sensitivity, uncertainty, quantile


def row(llm, primary, maxima, signal=1):
    return {'prediction': {'emotion': llm}, 'nrc': {'emotion': primary, 'tied': maxima, 'matched_tokens': signal}}


class AnalysisTests(unittest.TestCase):
    def test_tie_sensitivity_uses_same_denominator(self):
        rows = [row('joy', 'anticipation', ['anticipation', 'joy']),
                row('joy', 'joy', ['joy']), row('anger', 'trust', ['trust']),
                row('none', 'none', [], 0)]
        result = emotion_sensitivity(rows)
        self.assertEqual(result['signal_n'], 3)
        self.assertEqual(result['exact_signal_count'], 1)
        self.assertEqual(result['top_set_count'], 2)
        self.assertEqual(result['tie_break_only_count'], 1)
        self.assertEqual(result['no_signal_n'], 1)

    def test_no_signal_is_not_eight_way_compatibility(self):
        result = emotion_sensitivity([row('joy', 'none', [], 0)])
        self.assertEqual(result['top_set_count'], 0)
        self.assertIsNone(result['top_set_rate'])

    def test_ordered_sample_has_no_population_interval(self):
        result = uncertainty([], 'binary', 'binary')
        self.assertFalse(result['available'])

    def test_quantile_interpolates(self):
        self.assertEqual(quantile([0, 1, 2, 3], .5), 1.5)
        self.assertEqual(quantile([0, 1, 2, 3], .25), .75)

    def test_bootstrap_preserves_three_source_strata_in_binary_task(self):
        rows = []
        for rating in [5, 3, 1]:
            for index in range(50):
                actual = 'POSITIVE' if rating == 5 else 'NEGATIVE'
                predicted = 'POSITIVE' if rating >= 3 else 'NEGATIVE'
                rows.append({'rating': rating, 'actual': actual, 'prediction': {'sentiment': predicted}, 'rating_masked': False})
        result = uncertainty(rows, 'binary', 'three_class', resamples=20)
        self.assertEqual(result['intervals']['accuracy']['low'], 2/3)
        self.assertEqual(result['intervals']['accuracy']['high'], 2/3)
        self.assertEqual(result['intervals']['NEGATIVE.recall']['low'], .5)

if __name__ == '__main__':
    unittest.main()
