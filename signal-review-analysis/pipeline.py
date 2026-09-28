"""Download, sample, classify, and score. Python standard library only."""
import argparse, collections, concurrent.futures, datetime, gzip, hashlib, json, os, random, re, time, urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent
DATA_URL = 'https://mcauleylab.ucsd.edu/public_datasets/data/amazon_2023/raw/review_categories/Gift_Cards.jsonl.gz'
MODEL = 'cyankiwi/Qwen3.6-35B-A3B-AWQ-4bit'
SEED = 6418
EMOTIONS = ['anger','anticipation','disgust','fear','joy','sadness','surprise','trust','none']
LABELS = {'binary':['POSITIVE','NEGATIVE'], 'three_class':['POSITIVE','NEUTRAL','NEGATIVE']}
RATING_PATTERN = re.compile(r'\b(?:zero|one|two|three|four|five|[0-5](?:\.0)?)\s*(?:[- ]?stars?\b|(?:out\s+of|/)\s*5\b)|[★☆⭐]{1,5}', re.I)

def sha(data): return hashlib.sha256(data).hexdigest()
def save(path, value):
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix(path.suffix+'.tmp'); tmp.write_text(json.dumps(value,ensure_ascii=False,indent=2),encoding='utf-8'); tmp.replace(path)
def read(path): return json.loads(path.read_text(encoding='utf-8'))
def clean(text): return RATING_PATTERN.sub('[rating omitted]',text)
def truth(rating,mode):
    return 'POSITIVE' if rating>=4 else ('NEUTRAL' if mode=='three_class' and rating==3 else 'NEGATIVE')

def prepare():
    path=ROOT/'data/Gift_Cards.jsonl.gz'; path.parent.mkdir(exist_ok=True)
    if not path.exists(): urllib.request.urlretrieve(DATA_URL,path)
    pools={k:[] for k in LABELS['three_class']}; counts=collections.Counter(); first=[]
    with gzip.open(path,'rt',encoding='utf-8') as f:
        for index,line in enumerate(f):
            row=json.loads(line)
            if row['rating'] not in (1,2,3,4,5): raise ValueError('Invalid rating')
            r={k:row.get(k) for k in ['title','text','verified_purchase','helpful_vote','timestamp','asin']}
            if not isinstance(r['title'],str) or not isinstance(r['text'],str): raise ValueError('Invalid review text')
            r.update(id=f'gc-{index+1:06d}',source_line=index+1,rating=int(row['rating']))
            r['model_input']={k:clean(r[k]) for k in ['title','text']}
            r['rating_masked']=any(r[k]!=r['model_input'][k] for k in ['title','text'])
            counts[r['rating']]+=1
            pools[truth(r['rating'],'three_class')].append(r)
            if len(first)<100: first.append(r)
    rng=random.Random(SEED)
    balanced=[r for cls in LABELS['three_class'] for r in rng.sample(pools[cls],50)]
    rng.shuffle(balanced)
    save(ROOT/'results/samples.json',{'binary':first,'three_class':balanced})
    save(ROOT/'results/dataset.json',{'source':DATA_URL,'sha256':sha(path.read_bytes()),'total':sum(counts.values()),'ratings':dict(sorted(counts.items())),'sample_seed':SEED})
    print('Dataset verified:',sum(counts.values()),'reviews;',dict(counts),flush=True)

def payload(title,text,mode):
    prompt=(ROOT/f'prompts/{mode}.txt').read_text(encoding='utf-8')
    return {'model':os.environ.get('REVIEW_MODEL',MODEL),'temperature':0,'seed':SEED,'max_tokens':384,'response_format':{'type':'json_schema','json_schema':{'name':'review_classification','strict':True,'schema':{'type':'object','properties':{'sentiment':{'type':'string','enum':LABELS[mode]},'emotion':{'type':'string','enum':EMOTIONS},'reason':{'type':'string'}},'required':['sentiment','emotion','reason'],'additionalProperties':False}}},'chat_template_kwargs':{'enable_thinking':False},'messages':[{'role':'system','content':prompt},{'role':'user','content':json.dumps({'title':title,'text':text},ensure_ascii=False)}]}

def call(title,text,mode):
    body=payload(title,text,mode)
    base_url=os.environ.get('REVIEW_BASE_URL')
    if not base_url: raise RuntimeError('Set REVIEW_BASE_URL before model calls.')
    endpoint=base_url.rstrip('/')+'/chat/completions'
    key=os.environ.get('REVIEW_API_KEY')
    if not key: raise RuntimeError('Set REVIEW_API_KEY before model calls.')
    failures=[]
    for attempt in range(3):
        try:
            request=urllib.request.Request(endpoint,json.dumps(body).encode(),{'Content-Type':'application/json','Authorization':'Bearer '+key})
            start=time.monotonic()
            with urllib.request.urlopen(request,timeout=120) as response: raw=json.load(response)
            content=raw['choices'][0]['message']['content']; pred=json.loads(content)
            if set(pred)!= {'sentiment','emotion','reason'} or pred['sentiment'] not in LABELS[mode] or pred['emotion'] not in EMOTIONS or not isinstance(pred['reason'],str): raise ValueError('Invalid model schema')
            return {'prediction':pred,'response':raw,'elapsed_seconds':round(time.monotonic()-start,3),'request_sha256':sha(json.dumps(body,sort_keys=True).encode()),'attempts':attempt+1,'prior_errors':failures}
        except Exception as exc:
            failures.append(type(exc).__name__+': '+str(exc))
            if attempt==2: raise RuntimeError('Model failed: '+'; '.join(failures)) from exc
            time.sleep(2**attempt)

def score(rows,mode):
    labels=LABELS[mode]; matrix=[[0]*len(labels) for _ in labels]
    for r in rows:
        matrix[labels.index(r['actual'])][labels.index(r['prediction']['sentiment'])]+=1
    n=len(rows); correct=sum(matrix[i][i] for i in range(len(labels))); per={}
    for i,c in enumerate(labels):
        support=sum(matrix[i]); predicted=sum(row[i] for row in matrix); tp=matrix[i][i]
        precision=tp/predicted if predicted else 0; recall=tp/support if support else 0
        per[c]={'support':support,'predicted':predicted,'correct':tp,'precision':precision,'recall':recall,'f1':2*precision*recall/(precision+recall) if precision+recall else 0}
    return {'n':n,'correct':correct,'mismatches':n-correct,'accuracy':correct/n if n else 0,'balanced_accuracy':sum(v['recall'] for v in per.values())/len(labels),'macro_f1':sum(v['f1'] for v in per.values())/len(labels),'majority_baseline':max((sum(row) for row in matrix),default=0)/n if n else 0,'labels':labels,'matrix':matrix,'per_class':per,'masked_reviews':sum(r['rating_masked'] for r in rows)}

def run(mode,workers):
    sample=read(ROOT/'results/samples.json')[mode]; prompt=(ROOT/f'prompts/{mode}.txt').read_text(); prompt_hash=sha(prompt.encode())
    cache=ROOT/f'results/{mode}_checkpoint.json'
    config={'prompt_sha256':prompt_hash,'model':os.environ.get('REVIEW_MODEL',MODEL),'endpoint':'configured privately','temperature':0,'seed':SEED,'max_tokens':384,'enable_thinking':False,'response_format':'json_schema (strict)','sample_sha256':sha(json.dumps(sample,sort_keys=True).encode()),'pipeline_sha256':sha(Path(__file__).read_bytes())}
    checkpoint_config={**config,'endpoint_fingerprint':sha(os.environ.get('REVIEW_BASE_URL','').encode())}
    previous=read(cache) if cache.exists() else {'config':checkpoint_config,'rows':[]}
    if previous['config']!=checkpoint_config: raise RuntimeError('Checkpoint configuration changed; archive old checkpoint before rerunning.')
    done={r['id']:r for r in previous['rows']}
    def work(r):
        response=call(**r['model_input'],mode=mode)
        return {**r,**response,'actual':truth(r['rating'],mode)}
    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        futures={executor.submit(work,r):r for r in sample if r['id'] not in done}
        errors=[]
        for future in concurrent.futures.as_completed(futures):
            try: result=future.result()
            except Exception as exc:
                errors.append({'id':futures[future]['id'],'error':str(exc)})
                save(ROOT/f'results/{mode}_errors.json',errors)
                print('FAILED',futures[future]['id'],str(exc),flush=True)
                continue
            done[result['id']]=result
            save(cache,{'config':checkpoint_config,'rows':list(done.values())})
            print(mode,len(done),'/',len(sample),flush=True)
    if errors: raise RuntimeError(f'{len(errors)} reviews failed. Valid results retained; rerun to retry missing reviews.')
    rows=[done[r['id']] for r in sample]
    result={'mode':mode,'created_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),'config':config,'prompt':prompt,'metrics':score(rows,mode),'rows':rows}
    save(ROOT/f'results/{mode}.json',result)
    print(json.dumps(result['metrics'],indent=2),flush=True)

if __name__=='__main__':
    p=argparse.ArgumentParser(); p.add_argument('action',choices=['prepare','spotcheck','binary','three_class']); p.add_argument('--workers',type=int,default=3); args=p.parse_args()
    if args.action=='prepare': prepare()
    elif args.action=='spotcheck':
        tests=[('Loved it','Easy to use and exactly what I wanted.','POSITIVE'),('Unusable','The card never worked and support refused to help.','NEGATIVE')]
        output=[]
        for mode in LABELS:
            for title,text,expected in tests:
                result=call(title,text,mode); output.append({'mode':mode,'title':title,'text':text,'expected':expected,**result})
                assert result['prediction']['sentiment']==expected, result
        save(ROOT/'results/spotchecks.json',output); print('Four obvious sentiment spot checks passed.')
    else: run(args.action,args.workers)
