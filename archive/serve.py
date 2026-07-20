#!/usr/bin/env python3
"""
serve.py — read-only HTTP/JSON serve stub for the sound archive (the front-door read side,
generalized from lufs-recorder's serve). Runs on klaxon over the tailnet; co-located with
the index + audio so the <50ms hook/scrub promise holds (no cross-tailnet byte fetch).

  archive serve --db PATH --port 8788

Endpoints (stub):
  GET /api/stats                      counts by scope/model
  GET /api/query?scope=&bright_max=&limit=   filtered listing (JSON)
  GET /api/like/<catalog>?k=5         nearest neighbours (brute-force cosine)
  GET /hook/<catalog>                 the pre-rendered hook clip (audio/wav)
  GET /waveform/<catalog>             the waveform PNG
  GET /stream/<catalog>               full take, HTTP range (on-demand only)
The ADJ surface + the typed interaction log (POST /api/act) are the next build on top.
"""
import os, json, sqlite3, argparse, math
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs

DB=None
def q(sql,p=()):
    c=sqlite3.connect(DB); c.row_factory=sqlite3.Row
    try: return [dict(r) for r in c.execute(sql,p).fetchall()]
    finally: c.close()

class H(BaseHTTPRequestHandler):
    def _json(self,obj,code=200):
        b=json.dumps(obj).encode(); self.send_response(code)
        self.send_header("Content-Type","application/json"); self.send_header("Content-Length",str(len(b)))
        self.end_headers(); self.wfile.write(b)
    def _file(self,col,cat,mime):
        rows=q("SELECT %s p FROM assets WHERE catalog_number=?"%col,(cat,))
        if not rows or not rows[0]["p"] or not os.path.exists(rows[0]["p"]): return self._json({"error":"not found"},404)
        data=open(rows[0]["p"],"rb").read(); self.send_response(200)
        self.send_header("Content-Type",mime); self.send_header("Content-Length",str(len(data)))
        self.send_header("Accept-Ranges","bytes"); self.end_headers(); self.wfile.write(data)
    def do_GET(self):
        u=urlparse(self.path); parts=[x for x in u.path.split("/") if x]; qs=parse_qs(u.query)
        if u.path=="/api/stats":
            return self._json({"total":q("SELECT COUNT(*) n FROM assets")[0]["n"],
                               "by_scope":{r["scope"]:r["n"] for r in q("SELECT scope,COUNT(*) n FROM assets GROUP BY scope")}})
        if u.path=="/api/query":
            sql="SELECT catalog_number,filename,scope,duration_s,brightness,spectral_centroid_hz,hook_path,waveform_path FROM assets WHERE 1=1"; p=[]
            if "scope" in qs: sql+=" AND scope=?"; p.append(qs["scope"][0])
            if "bright_max" in qs: sql+=" AND brightness<=?"; p.append(float(qs["bright_max"][0]))
            sql+=" ORDER BY indexed_at DESC LIMIT ?"; p.append(int(qs.get("limit",["50"])[0]))
            return self._json(q(sql,p))
        if len(parts)==3 and parts[0]=="api" and parts[1]=="like":
            rows=q("SELECT * FROM assets"); seed=[r for r in rows if r["catalog_number"]==parts[2]]
            if not seed: return self._json({"error":"not found"},404)
            sv=json.loads(seed[0]["vector"] or "[]")
            def cos(a,b):
                if not a or not b: return -1
                d=sum(x*y for x,y in zip(a,b)); na=math.sqrt(sum(x*x for x in a)); nb=math.sqrt(sum(y*y for y in b))
                return d/(na*nb) if na and nb else -1
            out=[]
            for r in rows:
                if r["catalog_number"]==parts[2]: continue
                out.append({"catalog_number":r["catalog_number"],"filename":r["filename"],"scope":r["scope"],"sim":round(cos(sv,json.loads(r["vector"] or "[]")),4)})
            out.sort(key=lambda x:x["sim"],reverse=True)
            return self._json(out[:int(qs.get("k",["5"])[0])])
        if len(parts)==2 and parts[0]=="hook": return self._file("hook_path",parts[1],"audio/wav")
        if len(parts)==2 and parts[0]=="waveform": return self._file("waveform_path",parts[1],"image/png")
        if len(parts)==2 and parts[0]=="stream": return self._file("path",parts[1],"audio/wav")
        self._json({"error":"unknown route"},404)
    def log_message(self,*a): pass

def main():
    global DB
    ap=argparse.ArgumentParser(prog="archive serve")
    ap.add_argument("--db", default=os.environ.get("ARCHIVE_DB") or os.path.expanduser("~/.sound-archive/archive.db"))
    ap.add_argument("--host", default="127.0.0.1"); ap.add_argument("--port", type=int, default=8788)
    a=ap.parse_args(); DB=a.db
    print(f"sound-archive serve → http://{a.host}:{a.port}  (db: {DB})")
    HTTPServer((a.host,a.port), H).serve_forever()

if __name__=="__main__": main()
