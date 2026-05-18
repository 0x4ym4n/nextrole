"""Pin and run a local multilingual sentence encoder; no external inference calls."""
import argparse
import json
import os
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from sentence_transformers import SentenceTransformer

ROOT=Path(__file__).resolve().parents[1]
MODEL='sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2'
REVISION='e8f8c211226b894fcb81acc59f3b34ba3efd5f42'

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--corpus',default='data/demo.json');parser.add_argument('--serve',action='store_true');args=parser.parse_args()
    manifest=ROOT/'data/model.json'
    if manifest.exists():
        config=json.loads(manifest.read_text())
    else:
        config={'model':MODEL,'revision':REVISION}
        manifest.parent.mkdir(exist_ok=True);manifest.write_text(json.dumps(config,indent=2))
    model=SentenceTransformer(config['model'],revision=config['revision'],device='cpu')
    model.max_seq_length=128
    if not args.serve:
        path=ROOT/args.corpus;corpus=json.loads(path.read_text())
        # Title first: long descriptions truncate at the recorded token limit.
        texts=[j['title']+'. '+j['description'] for j in corpus['jobs']]
        vectors=model.encode(texts,batch_size=16,normalize_embeddings=True,show_progress_bar=True)
        for job,vector in zip(corpus['jobs'],vectors):job['embedding']=vector.tolist()
        corpus.update(model=config['model'],revision=config['revision'],dimension=int(vectors.shape[1]))
        out=path.with_name(path.stem+'_embeddings.json');out.write_text(json.dumps(corpus,ensure_ascii=False))
        print(json.dumps({'output':str(out),'jobs':len(texts),'dimension':corpus['dimension'],**config}));return
    class Handler(BaseHTTPRequestHandler):
        def log_message(self,*args):pass  # Never log query or candidate text.
        def do_GET(self):
            self.respond(200,{**config,'dimension':model.get_sentence_embedding_dimension(),'max_tokens':128})
        def respond(self,status,value):
            body=json.dumps(value).encode();self.send_response(status);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(body)));self.end_headers();self.wfile.write(body)
        def do_POST(self):
            try:
                if self.path!='/embed':self.respond(404,{'error':'not found'});return
                n=int(self.headers.get('Content-Length',0))
                if n<=0 or n>40000:self.respond(413,{'error':'invalid body size'});return
                text=json.loads(self.rfile.read(n))['text']
                if not isinstance(text,str) or len(text)>6500:raise ValueError()
                vector=model.encode(text,normalize_embeddings=True).tolist()
                self.respond(200,{'embedding':vector,**config})
            except (ValueError,KeyError,TypeError):self.respond(400,{'error':'invalid text'})
    print('NextRole local encoder ready on 127.0.0.1:8091',flush=True)
    HTTPServer(('127.0.0.1',8091),Handler).serve_forever()

if __name__=='__main__':
    os.environ.setdefault('TOKENIZERS_PARALLELISM','false')
    main()
