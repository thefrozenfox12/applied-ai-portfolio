"""Verify saved predictions, request isolation, sampling, and derived metrics offline."""
import collections, json
from pipeline import ROOT, read, score, sha, payload, truth, clean
from experiments import EXPERIMENTS

checks=0
samples=read(ROOT/'results/samples.json')
for name,(mode,sample_key) in EXPERIMENTS.items():
    r=read(ROOT/f'results/{name}.json'); rows=r['rows']; labels=r['metrics']['labels']
    assert r['metrics']==score(rows,mode)
    assert len(rows)==(100 if sample_key=='binary' else 150)
    assert len({x['id'] for x in rows})==len(rows)
    assert [x['id'] for x in rows]==[x['id'] for x in samples[sample_key]]
    if sample_key=='binary': assert [x['source_line'] for x in rows]==list(range(1,101))
    else: assert collections.Counter(truth(x['rating'],'three_class') for x in rows)=={'POSITIVE':50,'NEUTRAL':50,'NEGATIVE':50}
    assert sha(r['prompt'].encode())==r['config']['prompt_sha256']
    assert sha(json.dumps(samples[sample_key],sort_keys=True).encode())==r['config']['sample_sha256']
    for row in rows:
        assert row['actual']==truth(row['rating'],mode)
        assert row['model_input']=={k:clean(row[k]) for k in ['title','text']}
        body=payload(**row['model_input'],mode=mode)
        body['model']=r['config']['model']; body['messages'][0]['content']=r['prompt']
        assert set(json.loads(body['messages'][1]['content']))=={'title','text'}
        assert len(body['messages'])==2
        assert sha(json.dumps(body,sort_keys=True).encode())==row['request_sha256']
        assert json.loads(row['response']['choices'][0]['message']['content'])==row['prediction']
        assert row['prediction']['sentiment'] in labels
        assert row['emotion_agrees']==(row['prediction']['emotion']==row['nrc']['emotion'])
        scores=row['nrc']['scores']; high=max(scores.values()); tied=sorted(k for k,v in scores.items() if v==high) if high else []
        assert row['nrc']['tied']==tied
        assert row['nrc']['emotion']==(tied[0] if tied else 'none')
        checks+=1
    e=r['emotion_metrics']; signal=[x for x in rows if x['nrc']['matched_tokens']]
    assert e['agreement_count']==sum(x['emotion_agrees'] for x in rows)
    assert e['agreement_rate']==e['agreement_count']/len(rows)
    assert e['no_signal']==len(rows)-len(signal)
    assert e['ties']==sum(len(x['nrc']['tied'])>1 for x in rows)
    assert e['llm_counts']==dict(collections.Counter(x['prediction']['emotion'] for x in rows))
    assert e['nrc_counts']==dict(collections.Counter(x['nrc']['emotion'] for x in rows))
    print(name+': saved output and derived metrics verified')
print(f'{checks} requests verified: title and text only, isolated history, exact output hashes.')

from analysis import build_analysis
saved_analysis = read(ROOT/'results/analysis.json')
assert saved_analysis == build_analysis(save_result=False), 'Supplementary analysis does not reproduce.'
print('Paired comparisons, emotion sensitivity, and seeded uncertainty estimates reproduce exactly.')
