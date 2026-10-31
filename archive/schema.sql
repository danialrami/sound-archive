-- sound-archive canonical index schema.
-- v0 (this file): plain sqlite; vector stored as JSON text; KNN brute-forced in query.py.
-- prod: add the sqlite-vec vec0 virtual table below and mirror `vector` into it; the
--       assets columns stay identical — only the ANN mechanism changes.
--
-- Schema version: 2 (PRAGMA user_version = 2; see archive/migrate.py).
-- v2 adds the musical (sample_role, category, root_note, f0_hz, pitch_confidence,
-- bpm_confidence, bars) and provenance (source, source_id, creator, license) columns that
-- the downstream sample-pack builder (`lsmp`) needs. Every added column is nullable, so an
-- existing v0 index is migrated in place with ALTER TABLE ... ADD COLUMN only (no rewrite).

CREATE TABLE IF NOT EXISTS assets (
  content_sha256      TEXT PRIMARY KEY,   -- full 64-hex content hash (the key; never the 8-hex display id)
  catalog_number      TEXT,               -- lufs-<first8hex> — display only
  path                TEXT,               -- current canonical (keeper) path
  filename            TEXT,
  scope               TEXT,               -- archive | reference  (gates the ADJ surface, not the index)
  duration_s          REAL,
  samplerate          INTEGER,
  channels            INTEGER,
  peak_dbfs           REAL,
  mean_dbfs           REAL,
  spectral_centroid_hz REAL,
  rms_dbfs            REAL,
  brightness          REAL,
  bpm                 REAL,               -- null in v0 (deferred: librosa/essentia or sononym warm-start)
  key                 TEXT,               -- harmonic scale, e.g. 'D:minor' (distinct from root_note)
  -- ── v2: musical (role / pitch / tempo) ─────────────────────────────────────
  sample_role         TEXT CHECK (sample_role IS NULL OR sample_role IN ('one_shot','loop','stem','take')),
  category            TEXT,               -- 'bd' | 'sd' | 'hh' | 'oh' | 'cp' | 'rim' | 'perc' | 'bass' | 'pad' | 'lead' | 'chord' | 'fx' | 'vox' | 'atmo'
  root_note           TEXT CHECK (root_note IS NULL
                                  OR root_note GLOB '[a-g][0-9]'
                                  OR root_note GLOB '[a-g][#b][0-9]'
                                  OR root_note GLOB '[a-g]-[0-9]'
                                  OR root_note GLOB '[a-g][#b]-[0-9]'),  -- lowercase scientific pitch: e1, c4, f#3
  f0_hz               REAL,               -- detected fundamental frequency in Hz
  pitch_confidence    REAL,               -- [0.0, 1.0] confidence of fundamental pitch estimate
  bpm_confidence      REAL,               -- [0.0, 1.0] confidence of BPM estimate
  bars                INTEGER,            -- estimated bar count for loops (e.g. 1, 2, 4, 8)
  -- ── v2: provenance / license ───────────────────────────────────────────────
  source              TEXT,               -- 'own' | 'freesound' | 'openverse' | 'pack'
  source_id           TEXT,               -- upstream ID (Freesound numeric ID, Openverse UUID, lrex take_id)
  creator             TEXT,               -- upstream creator / artist handle
  license             TEXT,               -- 'own' | 'cc0' | 'cc-by' | 'cc-by-sa' | 'reference'
  -- ── v0 feature/embedding columns ───────────────────────────────────────────
  feature_source      TEXT,               -- native-melstats-v0 | sononym | librosa ...
  embed_model         TEXT,               -- melstats-v0 (placeholder) | laion-clap | muq-mulan
  dim                 INTEGER,
  vector              TEXT,               -- JSON float array (prod: also in vec0)
  hook_path           TEXT,
  waveform_path       TEXT,
  indexed_at          TEXT
);
CREATE INDEX IF NOT EXISTS idx_assets_scope ON assets(scope);
CREATE INDEX IF NOT EXISTS idx_assets_brightness ON assets(brightness);
-- v2 filter indexes (role / category / pitch / key / tempo / license).
CREATE INDEX IF NOT EXISTS idx_assets_sample_role ON assets(sample_role);
CREATE INDEX IF NOT EXISTS idx_assets_category ON assets(category);
CREATE INDEX IF NOT EXISTS idx_assets_root_note ON assets(root_note);
CREATE INDEX IF NOT EXISTS idx_assets_key ON assets(key);
CREATE INDEX IF NOT EXISTS idx_assets_bpm ON assets(bpm);
CREATE INDEX IF NOT EXISTS idx_assets_license ON assets(license);

-- Tombstoned duplicates (never deleted): every non-keeper points at its keeper.
CREATE TABLE IF NOT EXISTS dupes (
  path TEXT PRIMARY KEY, keeper_sha256 TEXT, reason TEXT, seen_at TEXT
);

-- Cached 3D galaxy projection (derived from the index; recompute after ingest batches).
-- Stable per-asset cluster + coords so /api/points, /api/surface, /api/like all colour
-- consistently without a per-request k-means. Projection is navigation; retrieval stays full-dim.
CREATE TABLE IF NOT EXISTS projection (
  content_sha256 TEXT PRIMARY KEY, cluster INTEGER, px REAL, py REAL, pz REAL,
  method TEXT, projected_at TEXT
);

-- The flywheel's irreplaceable asset: the typed, append-only interaction log.
-- Back this up religiously (see KB 05-scope-tagging-and-backup); nothing regenerates it.
CREATE TABLE IF NOT EXISTS interaction_log (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ts TEXT, action TEXT,               -- star | use | played | skip | more_like_this
  content_sha256 TEXT, session TEXT, weight REAL
);

-- prod (sqlite-vec):
-- .load vec0
-- CREATE VIRTUAL TABLE IF NOT EXISTS assets_vec USING vec0(content_sha256 TEXT PRIMARY KEY, embedding FLOAT[512]);
