"""Start the isolated local demo. Ctrl-C stops only child services started here."""
import argparse
import json
import os
import signal
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
def ready(url,timeout=90):
    start=time.monotonic()
    while time.monotonic()-start<timeout:
        try:
            with urllib.request.urlopen(url,timeout=2) as r:
                if r.status==200:return
        except (OSError,ValueError):pass
        time.sleep(.5)
    raise RuntimeError(f'Service did not become ready: {url}')
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--dataset',choices=['demo','live'],default='demo');args=parser.parse_args()
    corpus=ROOT/f'data/{args.dataset}_embeddings.json'
    if not corpus.exists():raise SystemExit(f'Missing {corpus.name}; run prepare_data.py and embeddings.py first (see README).')
    for port in [3000,8090,8091]:
        with socket.socket() as s:
            if s.connect_ex(('127.0.0.1',port))==0:raise SystemExit(f'Port {port} already in use; an existing demo may be running. Do not start a second copy.')
    children=[]
    def stop(*_):raise KeyboardInterrupt()
    signal.signal(signal.SIGTERM,stop)
    def start(cmd,cwd,env=None):
        p=subprocess.Popen(cmd,cwd=cwd,env=env,start_new_session=True);children.append(p);return p
    try:
        start([str(ROOT/'.venv/bin/python'),'scripts/embeddings.py','--serve'],ROOT)
        ready('http://127.0.0.1:8091/health')
        env={**os.environ,'NEXTROLE_DATA':str(corpus)}
        start(['go','run','.'],ROOT/'api',env)
        ready('http://127.0.0.1:8090/health')
        start(['npm','run','start'],ROOT/'web')
        ready('http://127.0.0.1:3000')
        print('NextRole ready: http://127.0.0.1:3000 · Android emulator API: http://10.0.2.2:8090',flush=True)
        while all(p.poll() is None for p in children):time.sleep(1)
        raise RuntimeError('A service stopped; inspect its output above.')
    except KeyboardInterrupt:pass
    finally:
        for p in reversed(children):
            if p.poll() is None:os.killpg(p.pid,signal.SIGTERM)
        for p in children:
            try:p.wait(timeout=10)
            except subprocess.TimeoutExpired:os.killpg(p.pid,signal.SIGKILL)
if __name__=='__main__':main()
