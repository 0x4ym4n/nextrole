"""Reproducible runtime measurements and synthetic retrieval regression.

Synthetic graded relevance labels are authored fixtures, NOT human judgments.
They demonstrate retrieval behaviour and must not be used as real-world accuracy.
"""
import argparse
import csv
import hashlib
import json
import math
import platform
import random
import statistics
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path
import requests

ROOT=Path(__file__).resolve().parents[1]
CASES=[
    ('dev','Flutter Developer',{'demo-001':3,'demo-002':3,'demo-003':2,'demo-019':3}),
    ('dev','Data Analyst',{'demo-009':3,'demo-010':3,'demo-011':2,'demo-020':3}),
    ('dev','UX Designer',{'demo-014':3,'demo-015':3}),
    ('dev','Backend Developer',{'demo-007':3,'demo-008':2,'demo-021':3}),
    ('test','Mobile Application Engineer',{'demo-001':3,'demo-002':3,'demo-003':2,'demo-004':2,'demo-019':3}),
    ('test','Platform Engineer',{'demo-012':3,'demo-013':3}),
    ('test','مطور تطبيقات',{'demo-001':3,'demo-002':3,'demo-003':2,'demo-019':3}),
    ('test','محلل بيانات',{'demo-009':3,'demo-010':3,'demo-011':2,'demo-020':3}),
]
def post(base,payload):
    r=requests.post(base+'/api/v1/search',json=payload,timeout=35);r.raise_for_status();return r.json()
def metrics(rows,labels):
    gains=[labels.get(j['id'],0) for j in rows]
    dcg=sum((2**g-1)/math.log2(i+2) for i,g in enumerate(gains[:10]))
    ideal=sum((2**g-1)/math.log2(i+2) for i,g in enumerate(sorted(labels.values(),reverse=True)[:10]))
    return {'precision_at_5':sum(g>=2 for g in gains[:5])/5,'ndcg_at_10':dcg/ideal if ideal else 0,'coverage':int(bool(rows))}
def mean(rows):return {k:statistics.mean(r[k] for r in rows) for k in rows[0]}
def synthetic(base):
    health=requests.get(base+'/health',timeout=5).json()
    if health['dataset']!='synthetic-functional-fixtures':raise ValueError('Synthetic evaluation requires synthetic corpus server')
    development=[]
    for threshold in [0.25,0.35,0.40,0.45,0.55,0.65]:
        scores=[metrics(post(base,{'query':q,'mode':'hybrid','min_score':threshold,'page_size':50})['results'],labels) for split,q,labels in CASES if split=='dev']
        development.append({'threshold':threshold,**mean(scores)})
    chosen=max(development,key=lambda r:(r['ndcg_at_10'],r['precision_at_5'],r['threshold']))['threshold']
    output={}
    for mode in ['exact','semantic','hybrid']:
        rows=[]
        for split,q,labels in CASES:
            if split!='test':continue
            result=post(base,{'query':q,'mode':mode,'min_score':chosen,'page_size':50})
            rows.append({'query':q,**metrics(result['results'],labels),'ids':[j['id'] for j in result['results']]})
        output[mode]={'per_query':rows,'mean':mean([{k:r[k] for k in ['precision_at_5','ndcg_at_10','coverage']} for r in rows])}
    return {'evidence_type':'synthetic authored regression; not participant or real vacancy relevance evidence','model':health,'development':development,'selected_threshold':chosen,'held_out':output,'case_definition_sha256':hashlib.sha256(json.dumps(CASES,ensure_ascii=False).encode()).hexdigest()}
def latency(base):
    rows=[]
    for mode in ['exact','semantic','hybrid']:
        for _ in range(3):post(base,{'query':'Engineer','mode':mode})
        for workers in [1,4]:
            def once(i):
                start=time.perf_counter()
                try:post(base,{'query':['Engineer','Developer','Designer','Analyst'][i%4],'mode':mode});return (time.perf_counter()-start)*1000,False
                except requests.RequestException:return (time.perf_counter()-start)*1000,True
            with ThreadPoolExecutor(max_workers=workers) as pool:values=list(pool.map(once,range(60)))
            times=sorted(t for t,_ in values)
            rows.append({'mode':mode,'concurrency':workers,'requests':len(times),'warmup_per_mode':3,'p50_ms':statistics.median(times),'p95_ms':times[math.ceil(.95*len(times))-1],'max_ms':max(times),'errors':sum(e for _,e in values)})
    return rows
def pool(base):
    """Export blinded pooled candidates. Labels remain blank for real assessors."""
    existing=ROOT/'evidence/human_judgement_pool.csv'
    if existing.exists():
        with existing.open(newline='') as f:
            if any(r.get('relevance_0_to_3','').strip() or r.get('assessor_id','').strip() for r in csv.DictReader(f)):
                raise FileExistsError('Existing human judgements must be preserved; move the completed assessment to a named archival file before creating a new pool.')
    rows=[];rankings={};queries=['Software Engineer','Data Analyst','Product Designer','Backend Developer','مطور تطبيقات','محلل بيانات']
    for i,q in enumerate(queries):
        candidates={};rankings[f'q{i+1}']={'query':q,'modes':{}}
        for mode in ['exact','semantic','hybrid']:
            results=post(base,{'query':q,'mode':mode,'page_size':10})['results']
            rankings[f'q{i+1}']['modes'][mode]=[j['id'] for j in results]
            for j in results:candidates[j['id']]=j
        for j in candidates.values():rows.append({'query_id':f'q{i+1}','query':q,'job_id':j['id'],'title':j['title'],'company':j['company'],'description':j['description'],'relevance_0_to_3':'','assessor_id':''})
    random.Random(3070).shuffle(rows)
    with (ROOT/'evidence/human_judgement_pool.csv').open('w',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=list(rows[0]));writer.writeheader();writer.writerows(rows)
    (ROOT/'evidence/pooled_rankings.json').write_text(json.dumps(rankings,indent=2,ensure_ascii=False))
    return len(rows)
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--live-api',default='http://127.0.0.1:8090');parser.add_argument('--fixture-api',default='http://127.0.0.1:8092');args=parser.parse_args()
    health=requests.get(args.live_api+'/health',timeout=5).json()
    result={'recorded_at':datetime.now(timezone.utc).isoformat(),'platform':platform.platform(),'python':platform.python_version(),'live_corpus':health,'synthetic_retrieval':synthetic(args.fixture_api),'latency':latency(args.live_api),'human_pool_rows':pool(args.live_api),'limitations':['Single machine; loopback network; local CPU encoder; no real network or production concurrency claim.','Synthetic test queries share occupational domains with development; this is not independent real-world relevance evidence.','Public-feed sample is convenience-based and predominantly European/international, not a representative MENA sample.','Human judgement pool remains unlabelled; no user study has been conducted.']}
    (ROOT/'evidence/evaluation.json').write_text(json.dumps(result,indent=2,ensure_ascii=False));print(json.dumps(result,ensure_ascii=False))
if __name__=='__main__':main()
