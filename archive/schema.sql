-- sound-archive canonical index schema.
-- v0 (this file): plain sqlite; vector stored as JSON text; KNN brute-forced in query.py.
-- prod: add the sqlite-vec vec0 virtual table below and mirror `vector` into it; the
--       assets columns stay identical — only the ANN mechanism changes.

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
  key                 TEXT,               -- null in v0
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

-- Tombstoned duplicates (never deleted): every non-keeper points at its keeper.
CREATE TABLE IF NOT EXISTS dupes (
  path TEXT PRIMARY KEY, keeper_sha256 TEXT, reason TEXT, seen_at TEXT
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
