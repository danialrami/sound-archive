#!/usr/bin/env python3
"""
Targeted unit tests for the `larc` spec (sound-archive#17), Units 01-04.

The repo ships no test suite, so these are the focused tests that pin the four unit
contracts. Everything runs against TEMP databases and temp WAVs — the real
~/.sound-archive/archive.db is never opened.

Run:  python3 tests/test_units.py
      python3 -m unittest discover -s tests -v
"""
import os, sys, json, stat, struct, wave, socket, tempfile, sqlite3, subprocess, unittest
import urllib.request, urllib.parse, time, signal

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LARC = os.path.join(ROOT, "bin", "larc")
ARCHIVE = os.path.join(ROOT, "bin", "archive")
SCHEMA = os.path.join(ROOT, "archive", "schema.sql")
sys.path.insert(0, ROOT)

SUBCOMMANDS = ["ingest", "query", "serve", "surface", "act", "points", "project", "migrate", "export"]


# ── helpers ──────────────────────────────────────────────────────────────────
def run(cmd, *args, db=None, cwd=ROOT):
    env = dict(os.environ)
    if db is not None:
        env["ARCHIVE_DB"] = db
    return subprocess.run(list(cmd) + list(args), cwd=cwd, env=env,
                          capture_output=True, text=True)


def larc(*args, db=None):
    return run([LARC], *args, db=db)


def write_wav(path, seconds=0.2, rate=48000):
    n = int(seconds * rate)
    with wave.open(path, "w") as w:
        w.setnchannels(1); w.setsampwidth(2); w.setframerate(rate)
        w.writeframes(b"".join(struct.pack("<h", int(3000 * (i % 50 - 25) / 25)) for i in range(n)))


def seed_db(path, rows):
    """Create a v2 index at `path` and insert `rows` (list of dicts)."""
    con = sqlite3.connect(path)
    con.executescript(open(SCHEMA).read())
    con.execute("PRAGMA user_version=2")
    for r in rows:
        cols = ",".join(r.keys())
        qs = ",".join("?" for _ in r)
        con.execute("INSERT INTO assets(%s) VALUES(%s)" % (cols, qs), list(r.values()))
    con.commit()
    con.close()


def tmp_wav(tmp, name):
    p = os.path.join(tmp, name)
    write_wav(p)
    return p


# ── Unit 01 ──────────────────────────────────────────────────────────────────
class Unit01CliTests(unittest.TestCase):
    def test_version_string_and_exit_0(self):
        out = larc("--version")
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(out.stdout.strip(), "larc 0.2.0 (sound-archive)")

    def test_help_exits_0_and_lists_subcommands(self):
        out = larc("--help")
        self.assertEqual(out.returncode, 0, out.stderr)
        for cmd in SUBCOMMANDS:
            self.assertIn(cmd, out.stdout)

    def test_larc_and_archive_are_executable(self):
        for p in (LARC, ARCHIVE):
            st = os.stat(p)
            self.assertTrue(st.st_mode & 0o111, "%s not executable" % p)
            self.assertTrue(os.access(p, os.X_OK), "%s not X_OK" % p)

    def test_dispatcher_covers_all_subcommands(self):
        src = open(LARC).read()
        for cmd in SUBCOMMANDS:
            self.assertIn(cmd + ")", src, "bin/larc missing dispatcher case for %r" % cmd)

    def test_archive_alias_delegates_to_larc(self):
        a = larc("--version")
        b = run([ARCHIVE], "--version")
        self.assertEqual(a.returncode, 0)
        self.assertEqual(b.returncode, 0)
        self.assertEqual(a.stdout, b.stdout)
        # and a real subcommand works through the alias
        with tempfile.TemporaryDirectory() as t:
            db = os.path.join(t, "a.db")
            seed_db(db, [])
            out = run([ARCHIVE], "query", "stats", "--json", db=db)
            self.assertEqual(out.returncode, 0, out.stderr)
            self.assertEqual(json.loads(out.stdout)["total"], 0)

    def test_setup_link_cli_symlinks_larc(self):
        with tempfile.TemporaryDirectory() as home:
            env = dict(os.environ, HOME=home)
            out = subprocess.run(["bash", os.path.join(ROOT, "setup.sh"), "link-cli"],
                                 cwd=ROOT, env=env, capture_output=True, text=True)
            self.assertEqual(out.returncode, 0, out.stderr)
            link = os.path.join(home, ".local", "bin", "larc")
            self.assertTrue(os.path.islink(link), "expected symlink at %s" % link)
            self.assertEqual(os.path.realpath(link), os.path.realpath(LARC))

    def test_first_run_calls_link_cli(self):
        src = open(os.path.join(ROOT, "setup.sh")).read()
        self.assertIn("cmd_link_cli", src)
        # first-run body must invoke it
        body = src.split("cmd_first_run(){", 1)[1].split("\n}", 1)[0]
        self.assertIn("cmd_link_cli", body)


# ── Unit 02 ──────────────────────────────────────────────────────────────────
class Unit02MigrationTests(unittest.TestCase):
    V2_COLUMNS = ["sample_role", "category", "root_note", "f0_hz", "pitch_confidence",
                  "bpm_confidence", "bars", "source", "source_id", "creator", "license"]

    def test_verbatim_verification(self):
        with tempfile.NamedTemporaryFile(suffix=".db") as f:
            out = subprocess.check_output(["python3", "archive/migrate.py", "--db", f.name, "--json"], cwd=ROOT)
            data = json.loads(out)
            self.assertEqual(data["schema_version"], 2)
            out2 = subprocess.check_output(["python3", "archive/migrate.py", "--db", f.name, "--json"], cwd=ROOT)
            self.assertIs(json.loads(out2)["already_migrated"], True)

    def test_fresh_empty_db_gets_v2_schema(self):
        with tempfile.NamedTemporaryFile(suffix=".db") as f:
            out = larc("migrate", "--db", f.name, "--json")
            self.assertEqual(out.returncode, 0, out.stderr)
            data = json.loads(out.stdout)
            self.assertEqual(data["schema_version"], 2)
            self.assertFalse(data["already_migrated"])
            con = sqlite3.connect(f.name)
            cols = {r[1] for r in con.execute("PRAGMA table_info(assets)")}
            for c in self.V2_COLUMNS:
                self.assertIn(c, cols)
            self.assertEqual(con.execute("PRAGMA user_version").fetchone()[0], 2)
            con.close()

    def test_v0_to_v2_is_nondestructive(self):
        with tempfile.TemporaryDirectory() as t:
            db = os.path.join(t, "v0.db")
            con = sqlite3.connect(db)
            # the exact v0 assets table (pre-spec), plus live interaction_log rows
            con.executescript("""
                CREATE TABLE assets(content_sha256 TEXT PRIMARY KEY, catalog_number TEXT, path TEXT,
                  filename TEXT, scope TEXT, duration_s REAL, samplerate INTEGER, channels INTEGER,
                  peak_dbfs REAL, mean_dbfs REAL, spectral_centroid_hz REAL, rms_dbfs REAL,
                  brightness REAL, bpm REAL, key TEXT, feature_source TEXT, embed_model TEXT,
                  dim INTEGER, vector TEXT, hook_path TEXT, waveform_path TEXT, indexed_at TEXT);
                CREATE TABLE interaction_log(id INTEGER PRIMARY KEY AUTOINCREMENT, ts TEXT, action TEXT,
                  content_sha256 TEXT, session TEXT, weight REAL);
            """)
            con.execute("INSERT INTO assets(content_sha256,catalog_number,path,brightness,indexed_at)"
                        " VALUES('aa','lufs-aaaaaaaa','/tmp/a.wav',0.1,'2026-01-01T00:00:00Z')")
            con.execute("INSERT INTO assets(content_sha256,catalog_number,path) VALUES('bb','lufs-bbbbbbbb','/tmp/b.wav')")
            con.execute("INSERT INTO interaction_log(ts,action,content_sha256,session,weight)"
                        " VALUES('2026-01-01T00:00:00Z','star','aa','s',3.0)")
            con.commit(); con.close()

            out = larc("migrate", "--db", db, "--json")
            self.assertEqual(out.returncode, 0, out.stderr)
            data = json.loads(out.stdout)
            self.assertEqual(sorted(data["added_columns"]), sorted(self.V2_COLUMNS))
            self.assertFalse(data["already_migrated"])

            con = sqlite3.connect(db)
            self.assertEqual(con.execute("SELECT COUNT(*) FROM assets").fetchone()[0], 2)
            self.assertEqual(con.execute("SELECT COUNT(*) FROM interaction_log").fetchone()[0], 1)
            row = con.execute("SELECT catalog_number,brightness,indexed_at,sample_role,root_note,license"
                              " FROM assets WHERE content_sha256='aa'").fetchone()
            self.assertEqual(row, ("lufs-aaaaaaaa", 0.1, "2026-01-01T00:00:00Z", None, None, None))
            self.assertEqual(con.execute("PRAGMA user_version").fetchone()[0], 2)
            con.close()

            # idempotent second run
            out2 = larc("migrate", "--db", db, "--json")
            d2 = json.loads(out2.stdout)
            self.assertTrue(d2["already_migrated"])
            self.assertEqual(d2["added_columns"], [])

    def test_v2_filter_indexes_exist(self):
        with tempfile.NamedTemporaryFile(suffix=".db") as f:
            larc("migrate", "--db", f.name, "--json")
            con = sqlite3.connect(f.name)
            idx = {r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='index' AND tbl_name='assets'")}
            con.close()
            for name in ("idx_assets_sample_role", "idx_assets_category", "idx_assets_root_note",
                         "idx_assets_key", "idx_assets_bpm", "idx_assets_license"):
                self.assertIn(name, idx)

    def test_root_note_and_role_validators(self):
        sys.path.insert(0, os.path.join(ROOT, "archive"))
        import migrate
        for good in ("e1", "c4", "f#3", "bb2", "g-1", None):
            self.assertTrue(migrate.validate_root_note(good), good)
        for bad in ("E1", "H2", "e", "e11", "c#", "4", "e 1"):
            self.assertFalse(migrate.validate_root_note(bad), bad)
        for good in ("one_shot", "loop", "stem", "take", None):
            self.assertTrue(migrate.validate_sample_role(good))
        for bad in ("oneshot", "Loop", "break", ""):
            self.assertFalse(migrate.validate_sample_role(bad))

    def test_db_check_constraints_enforced(self):
        with tempfile.NamedTemporaryFile(suffix=".db") as f:
            larc("migrate", "--db", f.name, "--json")
            con = sqlite3.connect(f.name)
            con.execute("INSERT INTO assets(content_sha256,root_note) VALUES('ok','e1')")
            with self.assertRaises(sqlite3.IntegrityError):
                con.execute("INSERT INTO assets(content_sha256,root_note) VALUES('bad','E1')")
            with self.assertRaises(sqlite3.IntegrityError):
                con.execute("INSERT INTO assets(content_sha256,sample_role) VALUES('bad2','oneshot')")
            con.close()


# ── Unit 03 ──────────────────────────────────────────────────────────────────
def _seed_query_db(db, tmp):
    bass = tmp_wav(tmp, "bass_stab.wav")
    pad = tmp_wav(tmp, "warm_pad.wav")
    kick = tmp_wav(tmp, "kick.wav")
    seed_db(db, [
        dict(content_sha256="a"*64, catalog_number="lufs-aaaaaaaa", path=bass, filename="bass_stab.wav",
             scope="archive", duration_s=1.85, samplerate=48000, channels=2, peak_dbfs=-1.2,
             rms_dbfs=-14.8, brightness=0.2, sample_role="one_shot", category="bass", root_note="e1",
             f0_hz=41.2, pitch_confidence=0.94, bpm=None, key=None, source="openverse",
             source_id="uuid-1", creator="someone", license="cc0", indexed_at="2026-01-03T00:00:00Z"),
        dict(content_sha256="b"*64, catalog_number="lufs-bbbbbbbb", path=pad, filename="warm_pad.wav",
             scope="archive", duration_s=8.0, samplerate=48000, channels=2, brightness=0.5,
             sample_role="loop", category="pad", bpm=120.0, bpm_confidence=0.9, bars=4,
             key="D:minor", pitch_confidence=None, source="own", license="own",
             indexed_at="2026-01-02T00:00:00Z"),
        dict(content_sha256="c"*64, catalog_number="lufs-cccccccc", path=kick, filename="kick.wav",
             scope="reference", duration_s=0.4, samplerate=44100, channels=1, brightness=0.1,
             sample_role="one_shot", category="bd", root_note=None, pitch_confidence=0.4,
             source="freesound", source_id="12345", creator="fsuser", license="cc0",
             indexed_at="2026-01-01T00:00:00Z"),
    ])


class Unit03QueryTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.db = os.path.join(self.tmp, "q.db")
        _seed_query_db(self.db, self.tmp)

    def test_filter_by_role_category_license(self):
        out = larc("query", "filter", "--role", "one_shot", "--category", "bass",
                   "--license", "cc0", "--json", db=self.db)
        self.assertEqual(out.returncode, 0, out.stderr)
        rows = json.loads(out.stdout)
        self.assertEqual(len(rows), 1, rows)
        self.assertEqual(rows[0]["catalog_number"], "lufs-aaaaaaaa")

    def test_filter_by_each_axis(self):
        cases = [
            (["--role", "loop"], ["lufs-bbbbbbbb"]),
            (["--category", "pad"], ["lufs-bbbbbbbb"]),
            (["--root-note", "e1"], ["lufs-aaaaaaaa"]),
            (["--key", "D:minor"], ["lufs-bbbbbbbb"]),
            (["--bpm-min", "100"], ["lufs-bbbbbbbb"]),
            (["--bpm-max", "10"], []),
            (["--pitch-conf-min", "0.9"], ["lufs-aaaaaaaa"]),
            (["--source", "freesound"], ["lufs-cccccccc"]),
            (["--license", "own"], ["lufs-bbbbbbbb"]),
            (["--scope", "reference"], ["lufs-cccccccc"]),
        ]
        for args, expect in cases:
            out = larc("query", "filter", *args, "--json", db=self.db)
            self.assertEqual(out.returncode, 0, out.stderr)
            got = sorted(r["catalog_number"] for r in json.loads(out.stdout))
            self.assertEqual(got, sorted(expect), "filter %s -> %s" % (args, got))

    def test_stats_breakdowns(self):
        out = larc("query", "stats", "--json", db=self.db)
        self.assertEqual(out.returncode, 0, out.stderr)
        d = json.loads(out.stdout)
        self.assertEqual(d["by_role"], {"one_shot": 2, "loop": 1})
        self.assertEqual(d["by_category"], {"bass": 1, "pad": 1, "bd": 1})
        self.assertEqual(d["by_license"], {"cc0": 2, "own": 1})

    def test_db_flag_before_and_after_subcommand(self):
        # regression: argparse subparsers must not clobber --db/--json given before the subcommand
        env = {k: v for k, v in os.environ.items() if k != "ARCHIVE_DB"}
        before = subprocess.run([LARC, "query", "--db", self.db, "stats", "--json"],
                                cwd=ROOT, env=env, capture_output=True, text=True)
        after = subprocess.run([LARC, "query", "stats", "--db", self.db, "--json"],
                               cwd=ROOT, env=env, capture_output=True, text=True)
        self.assertEqual(before.returncode, 0, before.stderr)
        self.assertEqual(after.returncode, 0, after.stderr)
        self.assertEqual(json.loads(before.stdout)["total"], 3)
        self.assertEqual(json.loads(before.stdout)["total"], json.loads(after.stdout)["total"])

    def test_serve_api_query_filters(self):
        port = _free_port()
        proc = subprocess.Popen([LARC, "serve", "--db", self.db, "--host", "127.0.0.1", "--port", str(port)],
                                cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        try:
            _wait_port(port)
            def get(q):
                with urllib.request.urlopen("http://127.0.0.1:%d/api/query?%s" % (port, q), timeout=5) as r:
                    return json.loads(r.read())
            one = get(urllib.parse.urlencode({"role": "one_shot", "category": "bass", "license": "cc0"}))
            self.assertEqual([r["catalog_number"] for r in one], ["lufs-aaaaaaaa"])
            loops = get(urllib.parse.urlencode({"role": "loop", "bpm_min": "100"}))
            self.assertEqual([r["catalog_number"] for r in loops], ["lufs-bbbbbbbb"])
            src = get(urllib.parse.urlencode({"source": "freesound"}))
            self.assertEqual([r["catalog_number"] for r in src], ["lufs-cccccccc"])
        finally:
            proc.send_signal(signal.SIGINT)
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()


def _free_port():
    s = socket.socket(); s.bind(("127.0.0.1", 0)); p = s.getsockname()[1]; s.close(); return p


def _wait_port(port, tries=50):
    for _ in range(tries):
        try:
            with urllib.request.urlopen("http://127.0.0.1:%d/api/stats" % port, timeout=1):
                return
        except Exception:
            time.sleep(0.1)
    raise AssertionError("serve did not come up on port %d" % port)


# ── Unit 04 ──────────────────────────────────────────────────────────────────
class Unit04ExportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        self.db = os.path.join(self.tmp, "e.db")
        self.bass = tmp_wav(self.tmp, "bass_stab.wav")
        seed_db(self.db, [
            dict(content_sha256="a"*64, catalog_number="lufs-aaaaaaaa", path=self.bass,
                 filename="bass_stab.wav", scope="archive", duration_s=1.85, samplerate=48000,
                 channels=2, peak_dbfs=-1.2, rms_dbfs=-14.8, sample_role="one_shot",
                 category="bass", root_note="e1", f0_hz=41.2, pitch_confidence=0.94,
                 source="own", source_id="rec-70ac952a", creator="danielramirez", license="own",
                 vector=json.dumps([0.5] * 512), indexed_at="2026-01-01T00:00:00Z"),
        ])

    def test_payload_has_contract_fields_and_no_vector(self):
        out = larc("export", "lufs-aaaaaaaa", "--json", db=self.db)
        self.assertEqual(out.returncode, 0, out.stderr)
        d = json.loads(out.stdout)
        self.assertEqual(d["schema_version"], 2)
        self.assertFalse(d["recorded_use"])
        self.assertEqual(len(d["assets"]), 1)
        a = d["assets"][0]
        expected = {"content_sha256", "catalog_number", "path", "filename", "scope", "sample_role",
                    "category", "duration_s", "samplerate", "channels", "peak_dbfs", "rms_dbfs",
                    "root_note", "f0_hz", "pitch_confidence", "bpm", "bpm_confidence", "bars",
                    "key", "source", "source_id", "creator", "license"}
        self.assertEqual(set(a.keys()), expected)
        self.assertNotIn("vector", a)
        self.assertEqual(a["root_note"], "e1")
        self.assertEqual(a["category"], "bass")
        # top-level fields the built lsmp reads
        for k in ("path", "audio", "file"):
            self.assertEqual(d[k], self.bass)

    def test_lookup_by_content_sha256(self):
        out = larc("export", "a" * 64, "--json", db=self.db)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertEqual(json.loads(out.stdout)["assets"][0]["catalog_number"], "lufs-aaaaaaaa")

    def test_record_use_appends_use_event(self):
        out = larc("export", "lufs-aaaaaaaa", "--record-use", "--session", "strudel-pack", "--json", db=self.db)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertTrue(json.loads(out.stdout)["recorded_use"])
        con = sqlite3.connect(self.db)
        rows = con.execute("SELECT action,content_sha256,session,weight FROM interaction_log").fetchall()
        con.close()
        self.assertEqual(rows, [("use", "a" * 64, "strudel-pack", 5.0)])

    def test_no_record_use_leaves_log_empty(self):
        larc("export", "lufs-aaaaaaaa", "--json", db=self.db)
        con = sqlite3.connect(self.db)
        n = con.execute("SELECT COUNT(*) FROM interaction_log").fetchone()[0]
        con.close()
        self.assertEqual(n, 0)

    def test_missing_asset_exits_4_structured(self):
        out = larc("export", "lufs-deadbeef", "--json", db=self.db)
        self.assertEqual(out.returncode, 4, out.stdout)
        err = json.loads(out.stderr)
        self.assertEqual(err["error"], "missing_asset")
        self.assertEqual(err["exit_code"], 4)
        self.assertEqual(err["missing"][0]["reference"], "lufs-deadbeef")
        self.assertEqual(err["missing"][0]["reason"], "not_in_assets")

    def test_missing_path_exits_4(self):
        seed_db(self.db, [dict(content_sha256="d"*64, catalog_number="lufs-dddddddd",
                               path=os.path.join(self.tmp, "gone.wav"), filename="gone.wav")])
        out = larc("export", "lufs-dddddddd", "--json", db=self.db)
        self.assertEqual(out.returncode, 4)
        err = json.loads(out.stderr)
        self.assertEqual(err["missing"][0]["reason"], "path_missing_on_disk")

    def test_multi_asset_export(self):
        p2 = tmp_wav(self.tmp, "second.wav")
        seed_db(self.db, [dict(content_sha256="e"*64, catalog_number="lufs-eeeeeeee", path=p2, filename="second.wav")])
        out = larc("export", "lufs-aaaaaaaa", "lufs-eeeeeeee", "--record-use", "--json", db=self.db)
        self.assertEqual(out.returncode, 0, out.stderr)
        d = json.loads(out.stdout)
        self.assertEqual(len(d["assets"]), 2)
        con = sqlite3.connect(self.db)
        n = con.execute("SELECT COUNT(*) FROM interaction_log WHERE action='use'").fetchone()[0]
        con.close()
        self.assertEqual(n, 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
