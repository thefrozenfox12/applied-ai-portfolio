"""Add NRC word-count emotions without making any model calls."""
import argparse, collections, re, urllib.request, zipfile
from pipeline import ROOT, EMOTIONS, read, save, sha
URL='https://saifmohammad.com/WebDocs/Lexicons/NRC-Emotion-Lexicon.zip'
MEMBER='NRC-Emotion-Lexicon/NRC-Emotion-Lexicon-Wordlevel-v0.92.txt'
ORDER=sorted(e for e in EMOTIONS if e!='none')

def load_lexicon():
    path=ROOT/'data/NRC-Emotion-Lexicon.zip'
    path.parent.mkdir(parents=True,exist_ok=True)
    if not path.exists(): urllib.request.urlretrieve(URL,path)
    with zipfile.ZipFile(path) as z: data=z.read(MEMBER)
    lex=collections.defaultdict(set)
    for line in data.decode('utf-8-sig').splitlines():
        parts=line.split('\t')
        if len(parts)==3:
            word,emotion,score=parts
            if emotion in ORDER and score=='1': lex[word].add(emotion)
    if len(lex)<1000: raise ValueError('Lexicon did not parse correctly')
    return lex,sha(data)

def classify(text,lex):
    tokens=re.findall(r"[a-z]+(?:'[a-z]+)?",text.lower()); counts={e:0 for e in ORDER}; matched=0
    for token in tokens:
        if token in lex: matched+=1
        for e in lex.get(token,[]): counts[e]+=1
    high=max(counts.values()); tied=[e for e in ORDER if counts[e]==high] if high else []
    return {'emotion':tied[0] if tied else 'none','scores':counts,'tied':tied,'matched_tokens':matched,'total_tokens':len(tokens)}

def enrich(mode):
    lex,digest=load_lexicon(); result=read(ROOT/f'results/{mode}.json')
    for row in result['rows']:
        # Remove masking markers so the added words cannot contribute to NRC scores.
        text=' '.join(row['model_input'].values()).replace('[rating omitted]','')
        row['nrc']=classify(text,lex)
        row['emotion_agrees']=row['nrc']['emotion']==row['prediction']['emotion']
    rows=result['rows']; signal=[r for r in rows if r['nrc']['matched_tokens']]
    result['emotion_metrics']={'agreement_count':sum(r['emotion_agrees'] for r in rows),'agreement_rate':sum(r['emotion_agrees'] for r in rows)/len(rows),'with_signal':len(signal),'no_signal':len(rows)-len(signal),'ties':sum(len(r['nrc']['tied'])>1 for r in rows),'signal_agreement_count':sum(r['emotion_agrees'] for r in signal),'signal_agreement_rate':sum(r['emotion_agrees'] for r in signal)/len(signal) if signal else None,'llm_counts':dict(collections.Counter(r['prediction']['emotion'] for r in rows)),'nrc_counts':dict(collections.Counter(r['nrc']['emotion'] for r in rows))}
    result['nrc_method']={'source':URL,'member':MEMBER,'sha256':digest,'tie_break':'alphabetical among maximum scores; all tied labels retained','no_match':'none','tokenizer':"lowercase English words, retaining internal apostrophes; occurrence counts, no stemming or negation handling",'input':'same masked title and text as LLM, marker removed'}
    save(ROOT/f'results/{mode}.json',result)
    print(mode,result['emotion_metrics'])

if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('mode',choices=['binary','three_class','binary_balanced','three_class_first100','all'],default='all',nargs='?'); a=p.parse_args()
    for mode in (['binary','three_class','binary_balanced','three_class_first100'] if a.mode=='all' else [a.mode]): enrich(mode)
