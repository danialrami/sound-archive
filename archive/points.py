#!/usr/bin/env python3
"""
points.py — the 3D galaxy projection. Turns the high-dim embedding index into renderable
points: PCA→3D coordinates + k-means cluster ids, numpy-only. This is the data feed for the
galaxy frontend. v0 projects on demand (fine at 10^3-10^5); prod caches the projection and
swaps PCA for UMAP for nicer separation (contract identical — points still {x,y,z,cluster}).

  archive points [--scope archive] [--k-clusters 8] [--db PATH] [--json]

Point contract (what the frontend consumes):
  { catalog_number, filename, scope, x, y, z, cluster,
    brightness, duration_s, spectral_centroid_hz, hook, waveform }
  hook/waveform are URL paths (/hook/<cat>, /waveform/<cat>) the serve resolves.
"""
import os, sys, json, sqlite3, argparse
import numpy as np

def db_path(a): return getattr(a,"db",None) or os.environ.get("ARCHIVE_DB") or os.path.expanduser("~/.sound-archive/archive.db")

def _kmeans(X, k, iters=25, seed=0):
    rng = np.random.default_rng(seed)
    if len(X) <= k: return np.arange(len(X))
    C = X[rng.choice(len(X), k, replace=False)]
    lab = np.zeros(len(X), dtype=int)
    for _ in range(iters):
        d = ((X[:,None,:]-C[None,:,:])**2).sum(2)
        nl = d.argmin(1)
        if (nl==lab).all(): break
        lab = nl
        for j in range(k):
            m = lab==j
            if m.any(): C[j] = X[m].mean(0)
    return lab

def build_points(con, scope=None, k_clusters=8):
    con.row_factory = sqlite3.Row
    sql = "SELECT catalog_number,filename,scope,duration_s,brightness,spectral_centroid_hz,vector,embed_model FROM assets"
    p = []
    if scope: sql += " WHERE scope=?"; p.append(scope)
    rows = [dict(r) for r in con.execute(sql, p).fetchall()]
    rows = [r for r in rows if r.get("vector")]
    if not rows:
        return {"points": [], "n": 0, "projection": "pca-3d", "clusters": 0, "model": None, "dims": 0}
    V = np.array([json.loads(r["vector"]) for r in rows], dtype=np.float64)
    # PCA -> 3D (center, SVD, top-3 right-singular directions)
    Xc = V - V.mean(0)
    if V.shape[0] >= 3 and V.shape[1] >= 3:
        _,_,Vt = np.linalg.svd(Xc, full_matrices=False)
        P = Xc @ Vt[:3].T
    else:
        P = np.pad(Xc, ((0,0),(0,max(0,3-V.shape[1]))))[:, :3]
    # normalize each axis to [-1,1] for rendering
    span = np.maximum(np.abs(P).max(0), 1e-9)
    P = P / span
    kc = min(k_clusters, len(rows))
    lab = _kmeans(P, kc) if kc > 1 else np.zeros(len(rows), dtype=int)
    pts = []
    for i, r in enumerate(rows):
        pts.append({
            "catalog_number": r["catalog_number"], "filename": r["filename"], "scope": r["scope"],
            "x": round(float(P[i,0]),5), "y": round(float(P[i,1]),5), "z": round(float(P[i,2]),5),
            "cluster": int(lab[i]),
            "brightness": r["brightness"], "duration_s": r["duration_s"],
            "spectral_centroid_hz": r["spectral_centroid_hz"],
            "hook": "/hook/%s" % r["catalog_number"], "waveform": "/waveform/%s" % r["catalog_number"],
        })
    return {"points": pts, "n": len(pts), "projection": "pca-3d", "clusters": int(lab.max())+1,
            "model": rows[0]["embed_model"], "dims": int(V.shape[1])}

def main():
    ap = argparse.ArgumentParser(prog="archive points")
    ap.add_argument("--scope"); ap.add_argument("--k-clusters", type=int, default=8)
    ap.add_argument("--db"); ap.add_argument("--json", action="store_true")
    a = ap.parse_args()
    p = db_path(a)
    if not os.path.exists(p): sys.exit(f"no index at {p}")
    con = sqlite3.connect(p)
    out = build_points(con, a.scope, a.k_clusters)
    if a.json: print(json.dumps(out, indent=2)); return
    print(f"# galaxy points: n={out['n']} clusters={out['clusters']} proj={out['projection']} model={out['model']} dims={out['dims']}")
    for pt in out["points"][:12]:
        print(f"  {pt['catalog_number']:<14} c{pt['cluster']}  ({pt['x']:+.2f},{pt['y']:+.2f},{pt['z']:+.2f})  {(pt['filename'] or '')[:22]}")

if __name__ == "__main__": main()
