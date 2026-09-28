"""Build a standalone offline HTML dashboard from saved experiment output."""
import json
from pipeline import ROOT, read, score
from experiments import EXPERIMENTS

def build():
    runs={name:read(ROOT/f'results/{name}.json') for name in EXPERIMENTS}
    for name,r in runs.items():
        if r['metrics']!=score(r['rows'],EXPERIMENTS[name][0]): raise ValueError('Saved scoring mismatch')
        if 'emotion_metrics' not in r: raise ValueError('Run emotions.py before building')
    data={'dataset':read(ROOT/'results/dataset.json'),'runs':runs,'analysis':read(ROOT/'results/analysis.json')}
    payload=json.dumps(data,ensure_ascii=False).replace('<','\\u003c').replace('\u2028','\\u2028').replace('\u2029','\\u2029')
    template=(ROOT/'dashboard.html.template').read_text(encoding='utf-8')
    if template.count('__SNAPSHOT__')!=1: raise ValueError('Template marker missing or duplicated')
    (ROOT/'dashboard.html').write_text(template.replace('__SNAPSHOT__',payload),encoding='utf-8')
    print('Built dashboard.html from validated saved outputs.')

if __name__=='__main__': build()
