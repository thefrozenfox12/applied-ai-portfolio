"""Offline supplementary evaluation; never calls a model or changes predictions."""
import collections
import random
from pipeline import ROOT, read, save, score, truth
from experiments import EXPERIMENTS

BOOTSTRAP_SEED = 6419
BOOTSTRAP_RESAMPLES = 10000


def quantile(values, q):
    ordered = sorted(values)
    position = (len(ordered) - 1) * q
    lower = int(position)
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)


def interval(values):
    return {'low': quantile(values, .025), 'high': quantile(values, .975)}


def emotion_sensitivity(rows):
    signal = [r for r in rows if r['nrc']['matched_tokens'] > 0]
    tied = [r for r in signal if len(r['nrc']['tied']) > 1]
    unique = [r for r in signal if len(r['nrc']['tied']) == 1]
    exact = sum(r['prediction']['emotion'] == r['nrc']['emotion'] for r in signal)
    compatible = sum(r['prediction']['emotion'] in r['nrc']['tied'] for r in signal)
    return {
        'signal_n': len(signal), 'no_signal_n': len(rows) - len(signal),
        'exact_signal_count': exact,
        'exact_signal_rate': exact / len(signal) if signal else None,
        'top_set_count': compatible,
        'top_set_rate': compatible / len(signal) if signal else None,
        'tie_break_only_count': compatible - exact,
        'tied_n': len(tied), 'unique_n': len(unique),
        'unique_agreement_count': sum(r['prediction']['emotion'] == r['nrc']['emotion'] for r in unique),
        'definition': 'Top-set compatibility counts the LLM label among NRC maximum-score emotions. Both comparisons use only reviews with nonzero NRC signal. This relaxed measure is not accuracy.',
    }


def uncertainty(rows, mode, sample_key, resamples=BOOTSTRAP_RESAMPLES):
    if sample_key == 'binary':
        return {'available': False, 'reason': 'First 100 rows are an ordered convenience sample. No population confidence interval is reported.'}
    rng = random.Random(BOOTSTRAP_SEED)
    strata = {c: [r for r in rows if truth(r['rating'], 'three_class') == c]
              for c in ['POSITIVE', 'NEUTRAL', 'NEGATIVE']}
    if any(len(group) != 50 for group in strata.values()):
        raise ValueError('Expected the fixed 50/50/50 sample.')
    draws = collections.defaultdict(list)
    for _ in range(resamples):
        sample = [row for group in strata.values() for row in rng.choices(group, k=len(group))]
        metrics = score(sample, mode)
        for metric in ['accuracy', 'balanced_accuracy', 'macro_f1']:
            draws[metric].append(metrics[metric])
        for label, values in metrics['per_class'].items():
            for metric in ['precision', 'recall', 'f1']:
                draws[label + '.' + metric].append(values[metric])
    return {
        'available': True, 'level': .95, 'method': 'stratified percentile bootstrap',
        'seed': BOOTSTRAP_SEED, 'resamples': resamples,
        'strata': {'POSITIVE': 50, 'NEUTRAL': 50, 'NEGATIVE': 50},
        'intervals': {key: interval(values) for key, values in draws.items()},
        'scope': 'Approximate sampling uncertainty for the fixed equal-three-stratum mixture. Assumes independent reviews within strata; not corpus-prevalence accuracy, model-run variability, or uncertainty in the rating benchmark. Percentile intervals have limited small-sample coverage and cannot reveal unseen failure modes.',
    }


def build_analysis(save_result=True):
    runs = {name: read(ROOT / f'results/{name}.json') for name in EXPERIMENTS}
    results = {}
    for name, run in runs.items():
        mode, sample_key = EXPERIMENTS[name]
        results[name] = {
            'mode': mode, 'sample_key': sample_key,
            'role': 'Reference' if name in ['binary', 'three_class'] else 'Supplementary',
            'sample_name': 'First 100 source rows' if sample_key == 'binary' else '150 rating-stratified reviews',
            'metrics': score(run['rows'], mode),
            'emotion_sensitivity': emotion_sensitivity(run['rows']),
            'uncertainty': uncertainty(run['rows'], mode, sample_key),
        }
    pairs = {}
    for sample, binary_name, three_name in [('first100', 'binary', 'three_class_first100'),
                                           ('balanced150', 'binary_balanced', 'three_class')]:
        left, right = runs[binary_name], runs[three_name]
        assert [r['id'] for r in left['rows']] == [r['id'] for r in right['rows']]
        for a, b in zip(left['rows'], right['rows']):
            assert a['model_input'] == b['model_input']
        matrix = [[0] * 3 for _ in range(2)]
        for a, b in zip(left['rows'], right['rows']):
            i = ['POSITIVE', 'NEGATIVE'].index(a['prediction']['sentiment'])
            j = ['POSITIVE', 'NEUTRAL', 'NEGATIVE'].index(b['prediction']['sentiment'])
            matrix[i][j] += 1
        pairs[sample] = {
            'n': len(left['rows']), 'binary_run': binary_name, 'three_class_run': three_name,
            'row_labels': ['POSITIVE', 'NEGATIVE'], 'column_labels': ['POSITIVE', 'NEUTRAL', 'NEGATIVE'],
            'prediction_transitions': matrix,
            'changed_labels': sum(matrix[0][1:]) + sum(matrix[1][:2]),
            'to_neutral': matrix[0][1] + matrix[1][1],
            'opposite_polarity': matrix[0][2] + matrix[1][0],
            'same_polarity': matrix[0][0] + matrix[1][2],
            'note': 'Paired descriptions on identical inputs, not a causal estimate. No predictions were supplied to another model request. Label definitions and scoring targets differ between tasks.',
        }
    # Fail if a supposedly frozen prompt/settings changed between paired experiments.
    for a, b in [('binary', 'binary_balanced'), ('three_class', 'three_class_first100')]:
        for key in ['prompt_sha256', 'model', 'temperature', 'seed', 'max_tokens', 'enable_thinking', 'response_format', 'endpoint']:
            assert runs[a]['config'][key] == runs[b]['config'][key], (a, b, key)
    result = {'runs': results, 'paired': pairs, 'schema_version': 1}
    if save_result:
        save(ROOT / 'results/analysis.json', result)
    return result

if __name__ == '__main__':
    result = build_analysis()
    for name, data in result['runs'].items():
        print(name, data['metrics']['accuracy'], data['emotion_sensitivity'])
