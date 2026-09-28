"""Supplementary controlled runs; original reference outputs stay intact."""
import argparse
import concurrent.futures
import datetime
import json
import os
from pathlib import Path
from pipeline import ROOT, MODEL, SEED, call, payload, read, save, score, sha, truth

EXPERIMENTS = {
    'binary': ('binary', 'binary'),
    'three_class': ('three_class', 'three_class'),
    'binary_balanced': ('binary', 'three_class'),
    'three_class_first100': ('three_class', 'binary'),
}

def run_experiment(name, workers=3):
    mode, sample_key = EXPERIMENTS[name]
    sample = read(ROOT / 'results/samples.json')[sample_key]
    prompt = (ROOT / f'prompts/{mode}.txt').read_text()
    request = payload('', '', mode)
    config = {
        'prompt_sha256': sha(prompt.encode()),
        'model': request['model'],
        'endpoint': 'configured privately',
        'temperature': 0, 'seed': SEED, 'max_tokens': 384,
        'enable_thinking': False, 'response_format': 'json_schema (strict)',
        'sample_sha256': sha(json.dumps(sample, sort_keys=True).encode()),
        'pipeline_sha256': sha((ROOT / 'pipeline.py').read_bytes()),
        'experiment_sha256': sha(Path(__file__).read_bytes()),
    }
    checkpoint = ROOT / f'results/{name}_checkpoint.json'
    checkpoint_config = {**config, 'endpoint_fingerprint': sha(os.environ.get('REVIEW_BASE_URL', '').encode())}
    existing = read(checkpoint) if checkpoint.exists() else {'config': checkpoint_config, 'rows': []}
    if existing['config'] != checkpoint_config:
        raise ValueError('Checkpoint configuration changed; archive it before changing the experiment.')
    completed = {r['id']: r for r in existing['rows']}
    errors = []

    def classify(row):
        return {**row, **call(**row['model_input'], mode=mode), 'actual': truth(row['rating'], mode)}

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        jobs = {executor.submit(classify, r): r for r in sample if r['id'] not in completed}
        for future in concurrent.futures.as_completed(jobs):
            try:
                result = future.result()
                completed[result['id']] = result
                save(checkpoint, {'config': checkpoint_config, 'rows': list(completed.values())})
                print(name, len(completed), '/', len(sample), flush=True)
            except Exception as exc:
                errors.append({'id': jobs[future]['id'], 'error': str(exc)})
                save(ROOT / f'results/{name}_errors.json', errors)
    if errors:
        raise RuntimeError(f'{len(errors)} failed; completed responses are checkpointed for a retry.')
    rows = [completed[r['id']] for r in sample]
    result = {
        'mode': mode, 'experiment': name, 'sample_key': sample_key,
        'created_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
        'config': config, 'prompt': prompt, 'metrics': score(rows, mode), 'rows': rows,
    }
    save(ROOT / f'results/{name}.json', result)
    print(json.dumps(result['metrics'], indent=2), flush=True)

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('experiment', choices=['binary_balanced', 'three_class_first100', 'all'])
    parser.add_argument('--workers', type=int, default=3)
    args = parser.parse_args()
    for name in (['binary_balanced', 'three_class_first100'] if args.experiment == 'all' else [args.experiment]):
        run_experiment(name, args.workers)
