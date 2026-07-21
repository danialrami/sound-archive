#!/usr/bin/env python3
"""
points.py — the 3D galaxy projection. PCA->3D coordinates + k-means clusters, numpy-only.

Projection is a CACHED, per-asset artifact (like the index): `archive project` computes it
over the whole archive and PERSISTS cluster + (px,py,pz) to the `projection` table, so
/api/points, /api/surface and /api/like all colour by the SAME stable cluster without a
per-request k-means. 3D is navigation; retrieval stays full-dim (via /api/like). Recompute
after ingest batches. Prod swaps PCA->UMAP (contract identical: still {x,y,z,cluster}).

  archive project [--scope all] [--k-clusters 8] [--db PATH]   # compute + persist
  archive points  [--scope archive] [--db PATH] [--json]       # read (persisted, else on-the-fly)
"""
import os, sys, json, sqlite3, argparse, datetime
import numpy as np

def db_path(a): return getattr(a,"db",None) or os.environ.get("ARCHIVE_DB") or os.path.expanduser("~/.sound-archive/archive.db")

def _kmeans(X, k, iters=25, seed=0):
    rng=np.random.default_rng(seed)
    if len(X)<=k: return np.arange(len(X))
    C=X[rng.choice(len(X),k,replace=False)]; lab=np.zeros(len(X),int)
    for _ in range(iters):
        nl=((X[:,None,:]-C[None,:,:])**2).sum(2).argmin(1)
        if (nl==lab).all(): break
        lab=nl
        for j in range(k):
            m=lab==j
            if m.any(): C[j]=X[m].mean(0)
    return lab

def _project(con, k_clusters=8):
    con.row_factory=sqlite3.Row
    # NB: vector is JSON text — an unembedded row is the STRING "null", not SQL NULL, so we can't
    # filter in SQL. Parse defensively and keep only real, equal-length vectors (drop null/ragged)
    # so PCA never sees a 1-D/object array. Robust + idempotent across mixed/partial indexes.
    from collections import Counter
    vecs=[]
    for r in con.execute("SELECT content_sha256,vector FROM assets").fetchall():
        try: v=json.loads(r["vector"]) if r["vector"] else None
        except Exception: v=None
        if isinstance(v,list) and len(v)>0: vecs.append((r["content_sha256"], v))
    if not vecs: return [], 0
    dim=Counter(len(v) for _,v in vecs).most_common(1)[0][0]   # modal dim; drop odd ones out
    vecs=[(s,v) for s,v in vecs if len(v)==dim]
    shas=[s for s,_ in vecs]
    V=np.asarray([v for _,v in vecs], dtype=float)             # guaranteed 2-D now
    Xc=V-V.mean(0)
    if V.shape[0]>=3 and V.shape[1]>=3:
        _,_,Vt=np.linalg.svd(Xc, full_matrices=False); P=Xc@Vt[:3].T
    else:
        P=np.pad(Xc,((0,0),(0,max(0,3-V.shape[1]))))[:,:3]
    P=P/np.maximum(np.abs(P).max(0),1e-9)
    kc=min(k_clusters,len(vecs)); lab=_kmeans(P,kc) if kc>1 else np.zeros(len(vecs),int)
    out=[(shas[i], int(lab[i]), float(P[i,0]), float(P[i,1]), float(P[i,2])) for i in range(len(vecs))]
    return out, (int(lab.max())+1 if len(out) else 0)

def project(con, k_clusters=8):
    """Compute + PERSIST the projection. Returns cluster count."""
    con.execute("""CREATE TABLE IF NOT EXISTS projection(content_sha256 TEXT PRIMARY KEY,
        cluster INTEGER, px REAL, py REAL, pz REAL, method TEXT, projected_at TEXT)""")
    rows,nc=_project(con,k_clusters)
    ts=datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
    con.execute("DELETE FROM projection")
    con.executemany("INSERT INTO projection VALUES(?,?,?,?,?,?,?)",
                    [(s,c,x,y,z,"pca-3d+kmeans",ts) for (s,c,x,y,z) in rows])
    con.commit()
    return nc or 0

def cluster_map(con):
    try: return {r[0]: r[1] for r in con.execute("SELECT content_sha256,cluster FROM projection").fetchall()}
    except sqlite3.OperationalError: return {}

def build_points(con, scope=None, k_clusters=8):
    con.row_factory=sqlite3.Row
    persisted={r[0]:r for r in con.execute(
        "SELECT content_sha256,cluster,px,py,pz FROM projection").fetchall()} if _has_proj(con) else {}
    if not persisted:  # fall back to on-the-fly (never break the endpoint)
        rows,_=_project(con,k_clusters); persisted={s:(s,c,x,y,z) for (s,c,x,y,z) in rows}
    sql="SELECT content_sha256,catalog_number,filename,scope,duration_s,brightness,spectral_centroid_hz,embed_model,dim FROM assets"
    p=[]
    if scope and scope!="all": sql+=" WHERE scope=?"; p.append(scope)
    pts=[]; model=None; dims=None
    for r in con.execute(sql,p).fetchall():
        pr=persisted.get(r["content_sha256"]);
        if not pr: continue
        model=r["embed_model"]; dims=r["dim"] or dims
        pts.append({"catalog_number":r["catalog_number"],"filename":r["filename"],"scope":r["scope"],
                    "x":round(pr[2],5),"y":round(pr[3],5),"z":round(pr[4],5),"cluster":int(pr[1]),
                    "brightness":r["brightness"],"duration_s":r["duration_s"],
                    "spectral_centroid_hz":r["spectral_centroid_hz"],
                    "hook":"/hook/%s"%r["catalog_number"],"waveform":"/waveform/%s"%r["catalog_number"]})
    clusters=(max((pt["cluster"] for pt in pts), default=-1)+1)
    return {"points":pts,"n":len(pts),"projection":"pca-3d","clusters":clusters,"model":model,"dims":dims or 0}

def _has_proj(con):
    try: return con.execute("SELECT COUNT(*) FROM projection").fetchone()[0]>0
    except sqlite3.OperationalError: return False

def main():
    ap=argparse.ArgumentParser(prog="archive points/project")
    ap.add_argument("mode", nargs="?", default="points", choices=["points","project"])
    ap.add_argument("--scope"); ap.add_argument("--k-clusters", type=int, default=8)
    ap.add_argument("--db"); ap.add_argument("--json", action="store_true")
    a=ap.parse_args(); p=db_path(a)
    if not os.path.exists(p): sys.exit(f"no index at {p}")
    con=sqlite3.connect(p)
    if a.mode=="project":
        nc=project(con,a.k_clusters); print(f"projected {con.execute('SELECT COUNT(*) FROM projection').fetchone()[0]} assets into {nc} clusters (persisted)")
        return
    out=build_points(con,a.scope,a.k_clusters)
    if a.json: print(json.dumps(out,indent=2)); return
    print(f"# galaxy: n={out['n']} clusters={out['clusters']} proj={out['projection']} model={out['model']}")
    for pt in out["points"][:12]:
        print(f"  {pt['catalog_number']:<14} c{pt['cluster']} ({pt['x']:+.2f},{pt['y']:+.2f},{pt['z']:+.2f}) {(pt['filename'] or '')[:22]}")

if __name__=="__main__": main()
