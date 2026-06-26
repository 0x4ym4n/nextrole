"""Generate report figures from recorded measurements, never illustrative metrics."""
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
ROOT=Path(__file__).resolve().parents[1]
data=json.loads((ROOT/'evidence/evaluation.json').read_text())
plt.rcParams.update({'font.family':'DejaVu Sans','font.size':11,'axes.spines.top':False,'axes.spines.right':False})
colors=['#7a9685','#407a69','#153f37']
fig,ax=plt.subplots(figsize=(8,4.4))
rows=[r for r in data['latency'] if r['concurrency']==1]
ax.bar([r['mode'].title() for r in rows],[r['p95_ms'] for r in rows],color=colors)
ax.set(ylabel='95th percentile response time (ms)',title='Local API latency on 118 public-feed vacancies')
for i,r in enumerate(rows):ax.text(i,r['p95_ms']+.1,f"{r['p95_ms']:.2f} ms",ha='center')
fig.text(.12,.02,'60 measured requests per mode; concurrency 1; loopback; warm CPU encoder.',fontsize=9)
fig.tight_layout(rect=(0,.05,1,1));fig.savefig(ROOT/'evidence/latency.png',dpi=200);plt.close(fig)
fig,ax=plt.subplots(figsize=(8,4.4))
modes=['exact','semantic','hybrid'];values=[data['synthetic_retrieval']['held_out'][m]['mean']['ndcg_at_10'] for m in modes]
ax.bar([m.title() for m in modes],values,color=colors);ax.set(ylim=(0,1.12),ylabel='nDCG@10')
ax.set_title('Synthetic retrieval regression\nAuthored fixtures, not human relevance evidence',fontsize=12,pad=12)
for i,v in enumerate(values):ax.text(i,v+.025,f'{v:.3f}',ha='center')
fig.text(.12,.02,'22 authored fictional vacancies; 4 held-out queries; related domains overlap development.',fontsize=8.5)
fig.tight_layout(rect=(0,.05,1,1));fig.savefig(ROOT/'evidence/synthetic-retrieval.png',dpi=200);plt.close(fig)
print('Generated evidence/latency.png and evidence/synthetic-retrieval.png')
