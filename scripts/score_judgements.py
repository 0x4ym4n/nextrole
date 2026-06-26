"""Score actual completed assessor CSVs against the stored pooled rankings."""
import argparse
import csv
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path

def main():
    parser=argparse.ArgumentParser();parser.add_argument('csv');parser.add_argument('--rankings',default='evidence/pooled_rankings.json');parser.add_argument('--output',default='evidence/human_relevance_results.json');args=parser.parse_args()
    with open(args.csv,newline='') as f:rows=list(csv.DictReader(f))
    if not rows:raise SystemExit('No assessments found')
    by_assessor=defaultdict(lambda:defaultdict(dict))
    for r in rows:
        if r.get('relevance_0_to_3') not in ['0','1','2','3'] or not r.get('assessor_id','').strip():raise SystemExit('Every row must contain a real assessor ID and an integer grade from 0 to 3')
        grades=by_assessor[r['assessor_id']][r['query_id']]
        if r['job_id'] in grades:raise SystemExit('Duplicate assessor/query/job judgement')
        grades[r['job_id']]=int(r['relevance_0_to_3'])
    rankings=json.loads(Path(args.rankings).read_text());result={}
    for assessor,queries in by_assessor.items():
        modes={}
        for mode in ['exact','semantic','hybrid']:
            scores=[]
            for qid,ranked in rankings.items():
                if qid not in queries:raise SystemExit(f'Missing query judgements for {assessor}/{qid}')
                labels=queries[qid];ids=ranked['modes'][mode]
                if any(j not in labels for lists in ranked['modes'].values() for j in lists):raise SystemExit('Incomplete pooled judgements')
                gains=[labels[j] for j in ids]
                ideal=sum((2**g-1)/math.log2(i+2) for i,g in enumerate(sorted(labels.values(),reverse=True)[:10]))
                dcg=sum((2**g-1)/math.log2(i+2) for i,g in enumerate(gains[:10]))
                scores.append({'query_id':qid,'precision_at_5':sum(g>=2 for g in gains[:5])/5,'pooled_ndcg_at_10':dcg/ideal if ideal else 0})
            modes[mode]={'per_query':scores,'precision_at_5':statistics.mean(s['precision_at_5'] for s in scores),'pooled_ndcg_at_10':statistics.mean(s['pooled_ndcg_at_10'] for s in scores)}
        result[assessor]=modes
    Path(args.output).write_text(json.dumps({'assessors':result,'limitation':'Pooled judgements only; no whole-corpus recall or population inference.'},indent=2))
    print(args.output)
if __name__=='__main__':main()
