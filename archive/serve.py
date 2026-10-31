#!/usr/bin/env python3
"""
serve.py — read-only HTTP/JSON serve stub for the sound archive (the front-door read side,
generalized from lufs-recorder's serve). Runs on klaxon over the tailnet; co-located with
the index + audio so the <50ms hook/scrub promise holds (no cross-tailnet byte fetch).

  archive serve --db PATH --port 8788     # also serves the web/ front door at /  (one process, same-origin)

Endpoints (stub):
  GET /api/stats                      counts by scope/model
  GET /api/query?scope=&bright_max=&limit=   filtered listing (JSON)
  GET /api/like/<catalog>?k=5         nearest neighbours (brute-force cosine)
  GET /hook/<catalog>                 the pre-rendered hook clip (audio/wav)
  GET /waveform/<catalog>             the waveform PNG
  GET /stream/<catalog>               full take, HTTP range (on-demand only)
  GET /api/points?scope=&k_clusters=  3D galaxy projection (PCA-3D + k-means clusters)
  GET /api/surface?k=&session=&scope= ADJ morning surface (weighted blend)
  POST /api/act {catalog,action,session}   log a typed interaction
The ADJ surface + the typed interaction log (POST /api/act) are the next build on top.
"""
import os, json, sqlite3, argparse, math, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import surface as _surface, actlog as _actlog, points as _points
import subprocess, re
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs

DB=None
WEB_DIR=os.path.abspath(os.path.join(os.path.dirname(os.path.abspath(__file__)),"..","web"))
_MIME={".html":"text/html; charset=utf-8",".js":"application/javascript",".css":"text/css",
       ".md":"text/markdown; charset=utf-8",".png":"image/png",".svg":"image/svg+xml",
       ".ico":"image/x-icon",".json":"application/json",".woff2":"font/woff2"}
def _waveform_peaks(cat, bins=800):
    import numpy as np
    c=sqlite3.connect(DB); c.row_factory=sqlite3.Row
    row=c.execute("SELECT path,duration_s,peak_dbfs FROM assets WHERE catalog_number=?",(cat,)).fetchone()
    if not row or not row["path"] or not os.path.exists(row["path"]): return {"error":"not found"}
    raw=subprocess.run(["ffmpeg","-nostdin","-hide_banner","-v","error","-i",row["path"],
        "-ac","1","-ar","22050","-f","f32le","-"],capture_output=True).stdout
    x=np.frombuffer(raw,dtype=np.float32)
    bins=max(1,min(bins,4000))
    peaks=[]; rms=[]
    if x.size:
        idx=np.linspace(0,x.size,bins+1).astype(int)
        for i in range(bins):
            seg=x[idx[i]:idx[i+1]]
            if seg.size: peaks.append([round(float(seg.min()),4),round(float(seg.max()),4)]); rms.append(round(float(np.sqrt((seg**2).mean())),4))
            else: peaks.append([0.0,0.0]); rms.append(0.0)
    # integrated LUFS via ffmpeg ebur128 (on-demand; one extra pass)
    lufs=None
    try:
        er=subprocess.run(["ffmpeg","-nostdin","-hide_banner","-i",row["path"],"-af","ebur128","-f","null","-"],
                          capture_output=True,text=True).stderr
        m=re.findall(r"I:\s*(-?[0-9.]+)\s*LUFS", er)
        if m: lufs=float(m[-1])
    except Exception: pass
    return {"catalog_number":cat,"bins":len(peaks),"peaks":peaks,"rms":rms,
            "dur":row["duration_s"],"peak_dbfs":row["peak_dbfs"],"integrated_lufs":lufs}
def q(sql,p=()):
    c=sqlite3.connect(DB); c.row_factory=sqlite3.Row
    try: return [dict(r) for r in c.execute(sql,p).fetchall()]
    finally: c.close()

class H(BaseHTTPRequestHandler):
    def _cors(self):
        self.send_header("Access-Control-Allow-Origin","*")
        self.send_header("Access-Control-Allow-Methods","GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers","Content-Type")
    def _json(self,obj,code=200):
        b=json.dumps(obj).encode(); self.send_response(code)
        self.send_header("Content-Type","application/json"); self._cors(); self.send_header("Content-Length",str(len(b)))
        self.end_headers(); self.wfile.write(b)
    def do_OPTIONS(self):
        self.send_response(204); self._cors(); self.send_header("Content-Length","0"); self.end_headers()
    def _file(self,col,cat,mime):
        rows=q("SELECT %s p FROM assets WHERE catalog_number=?"%col,(cat,))
        if not rows or not rows[0]["p"] or not os.path.exists(rows[0]["p"]): return self._json({"error":"not found"},404)
        data=open(rows[0]["p"],"rb").read(); self.send_response(200)
        self.send_header("Content-Type",mime); self._cors(); self.send_header("Content-Length",str(len(data)))
        self.send_header("Accept-Ranges","bytes"); self.end_headers(); self.wfile.write(data)
    def _static(self, path):
        rel = "index.html" if path in ("","/") else path.lstrip("/")
        fp = os.path.normpath(os.path.join(WEB_DIR, rel))
        if not fp.startswith(WEB_DIR) or not os.path.isfile(fp): return False
        data=open(fp,"rb").read()
        self.send_response(200)
        self.send_header("Content-Type", _MIME.get(os.path.splitext(fp)[1].lower(),"application/octet-stream"))
        self._cors(); self.send_header("Content-Length",str(len(data))); self.end_headers(); self.wfile.write(data)
        return True
    def do_GET(self):
        u=urlparse(self.path); parts=[x for x in u.path.split("/") if x]; qs=parse_qs(u.query)
        if u.path=="/api/stats":
            return self._json({"total":q("SELECT COUNT(*) n FROM assets")[0]["n"],
                               "by_scope":{r["scope"]:r["n"] for r in q("SELECT scope,COUNT(*) n FROM assets GROUP BY scope")}})
        if u.path=="/api/query":
            sql=("SELECT content_sha256,catalog_number,filename,scope,duration_s,brightness,"
                 "spectral_centroid_hz,sample_role,category,root_note,bpm,key,license,source,"
                 "hook_path,waveform_path FROM assets WHERE 1=1"); p=[]
            if "scope" in qs: sql+=" AND scope=?"; p.append(qs["scope"][0])
            if "bright_max" in qs: sql+=" AND brightness<=?"; p.append(float(qs["bright_max"][0]))
            # v2 musical / provenance filters (parameterized)
            if "role" in qs: sql+=" AND sample_role=?"; p.append(qs["role"][0])
            if "category" in qs: sql+=" AND category=?"; p.append(qs["category"][0])
            if "root_note" in qs: sql+=" AND root_note=?"; p.append(qs["root_note"][0])
            if "key" in qs: sql+=" AND key=?"; p.append(qs["key"][0])
            if "bpm_min" in qs: sql+=" AND bpm>=?"; p.append(float(qs["bpm_min"][0]))
            if "bpm_max" in qs: sql+=" AND bpm<=?"; p.append(float(qs["bpm_max"][0]))
            if "license" in qs: sql+=" AND license=?"; p.append(qs["license"][0])
            if "source" in qs: sql+=" AND source=?"; p.append(qs["source"][0])
            sql+=" ORDER BY indexed_at DESC LIMIT ?"; p.append(int(qs.get("limit",["50"])[0]))
            cmap=_points.cluster_map(sqlite3.connect(DB)); rows=q(sql,p)
            for r in rows: r["cluster"]=cmap.get(r.pop("content_sha256"))
            return self._json(rows)
        if len(parts)==3 and parts[0]=="api" and parts[1]=="like":
            rows=q("SELECT * FROM assets"); seed=[r for r in rows if r["catalog_number"]==parts[2]]
            if not seed: return self._json({"error":"not found"},404)
            sv=json.loads(seed[0]["vector"] or "[]")
            cmap=_points.cluster_map(sqlite3.connect(DB))
            def cos(a,b):
                if not a or not b: return -1
                d=sum(x*y for x,y in zip(a,b)); na=math.sqrt(sum(x*x for x in a)); nb=math.sqrt(sum(y*y for y in b))
                return d/(na*nb) if na and nb else -1
            out=[]
            for r in rows:
                if r["catalog_number"]==parts[2]: continue
                out.append({"catalog_number":r["catalog_number"],"filename":r["filename"],"scope":r["scope"],
                            "cluster":cmap.get(r["content_sha256"]),"brightness":r["brightness"],
                            "spectral_centroid_hz":r["spectral_centroid_hz"],
                            "sim":round(cos(sv,json.loads(r["vector"] or "[]")),4)})
            out.sort(key=lambda x:x["sim"],reverse=True)
            return self._json(out[:int(qs.get("k",["5"])[0])])
        if len(parts)==2 and parts[0]=="hook": return self._file("hook_path",parts[1],"audio/wav")
        if len(parts)==2 and parts[0]=="waveform": return self._file("waveform_path",parts[1],"image/png")
        if len(parts)==3 and parts[0]=="api" and parts[1]=="waveform":
            return self._json(_waveform_peaks(parts[2], int(qs.get("bins",["800"])[0])))
        if u.path=="/api/points":
            con=sqlite3.connect(DB)
            return self._json(_points.build_points(con, qs.get("scope",[None])[0], int(qs.get("k_clusters",["8"])[0])))
        if u.path=="/api/surface":
            con=sqlite3.connect(DB); 
            rows=_surface.surface(con, int(qs.get("k",["9"])[0]), qs.get("session",["default"])[0], qs.get("scope",["archive"])[0])
            return self._json(rows)
        if len(parts)==2 and parts[0]=="stream": return self._file("path",parts[1],"audio/wav")
        if self._static(u.path): return           # static front door: serve web/ at /
        self._json({"error":"unknown route"},404)
    def do_POST(self):
        u=urlparse(self.path)
        if u.path=="/api/act":
            ln=int(self.headers.get("Content-Length","0") or 0)
            try: body=json.loads(self.rfile.read(ln) or b"{}")
            except Exception: return self._json({"error":"bad json"},400)
            con=sqlite3.connect(DB); sha=_actlog.sha_for_catalog(con, body.get("catalog",""))
            if not sha: return self._json({"error":"unknown catalog"},404)
            _actlog.log_event(con, body.get("action","played"), sha, body.get("session","default"))
            return self._json({"ok":True,"action":body.get("action"),"catalog":body.get("catalog")})
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
