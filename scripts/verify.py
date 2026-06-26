"""Capture exact command results without inventing or manually transcribing counts."""
import json
import platform
import subprocess
import time
from datetime import datetime,timezone
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
CHECKS=[
 ('go-tests',['go','test','-race','-count=1','-json','./...'],'api'),
 ('go-vet',['go','vet','./...'],'api'),
 ('go-benchmark',['go','test','-run','^$','-bench','BenchmarkRank10000','-benchmem','-count=1'],'api'),
 ('web-types',['npm','run','typecheck'],'web'),
 ('web-build',['npm','run','build'],'web'),
 ('flutter-analyze',['flutter','analyze'],'mobile'),
 ('flutter-tests',['flutter','test','--reporter','json'],'mobile'),
]
def main():
    rows=[]
    for name,cmd,cwd in CHECKS:
        start=time.monotonic();r=subprocess.run(cmd,cwd=ROOT/cwd,capture_output=True,text=True)
        path=ROOT/'evidence'/f'{name}.log';path.write_text(r.stdout+'\n'+r.stderr)
        rows.append(dict(check=name,command=cmd,exit_code=r.returncode,duration_s=time.monotonic()-start,log=path.name))
        print(name,r.returncode,flush=True)
    (ROOT/'evidence/verification.json').write_text(json.dumps({'recorded_at':datetime.now(timezone.utc).isoformat(),'platform':platform.platform(),'checks':rows},indent=2))
    if any(r['exit_code'] for r in rows):raise SystemExit(1)
if __name__=='__main__':main()
