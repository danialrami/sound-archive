on klaxon's end:

🍏 …/sound-archive 🌿 main $  🐍 v3.14.6 🕚 2026-08-01 1:22:09 PM
👉 ./ingest.sh run --herdr
✓ API key present: /Users/danielramirez/.config/serve-embed/client.env
✓ readyz: ok=true device=cuda dim=512 rev=205e90eee527
✓ ingest launched in herdr pane w2:p1K
▸ check in: herdr pane read w2:p1K --source recent-unwrapped --lines 80
▸ stop:     herdr pane send-keys w2:p1K ctrl+c   (or: ingest.sh stop)
⏎
🍏 …/sound-archive 🌿 main $  🐍 v3.14.6 🕚 2026-08-01 1:22:11 PM
👉 ./ingest.sh --help
ingest.sh — drive + watch the sound-archive batch ingest

USAGE
  ./ingest.sh <run|watch|status|stop|preflight|help> [options]

COMMANDS
  run [--samples PATH] [--embedder clap-remote|clap|melstats]
      [--endpoint URL] [--env-file PATH]
      [--tmux | --herdr | --foreground] [--no-preflight] [--limit N]
      [--dry-run] [--force]
        Start/resume the ingest. Default: detached tmux session 'ingest'.
        --herdr      only inside a herdr pane (HERDR_ENV=1); splits a sibling pane.
        --foreground run in this shell (use inside a herdr pane you created).
        --force      stop any running ingest first.
        Fail-closed: refuses to start unless <endpoint>/readyz is ok:true and the
        env file has EMBED_API_KEY.

  watch [--stats] [--log FILE]
        Tail the run log (~/.workchain/runs/latest.log). --stats also polls the
        serve count every 30s.

  status        Is it running (tmux/pane/pid)? last log lines + DB count.
  stop          Ctrl+C to the ingest (tmux send-keys C-c, else SIGINT to its group).
  preflight     Check endpoint /readyz + key. Exits non-zero if not ready.
  help          This message.

DEFAULTS
  samples    /Users/danielramirez/Samples/Samples/sampleLibrary
  embedder   clap-remote          (chain archive-ingest-clap-remote.yaml)
  endpoint   $EMBED_CLAP_ENDPOINT or http://100.125.210.60:8770
  env-file   /Users/danielramirez/.config/serve-embed/client.env    (sourced for EMBED_API_KEY / EMBED_CLAP_ENDPOINT)
  db         /Users/danielramirez/.sound-archive/archive.db

CHECK-IN TOOLKIT
  Logs (terminal-agnostic)
    ./ingest.sh watch --stats
    tail -f ~/.workchain/runs/latest.log

  Progress / index state
    curl -s http://127.0.0.1:8788/api/stats
    sqlite3 ~/.sound-archive/archive.db "SELECT COUNT(*), MAX(indexed_at) FROM assets;"

  tmux (default launch)
    tmux list-sessions
    tmux attach -t ingest            (detach: Ctrl-b d)
    tmux send-keys -t ingest C-c     (stop — same as ./ingest.sh stop)

  herdr (from inside your herdr session)
    herdr workspace list
    herdr tab list --workspace <id>
    herdr pane read <pane> --source recent-unwrapped --lines 80
    herdr pane wait-output <pane> --match "resume:" --timeout 600000
    herdr pane send-keys <pane> ctrl+c

CUTOVER GATES (Part E of the serve-embed playbook)
  [3/4] resume: N already indexed, M to ingest   → N must be >= 63,151 (the baseline)
  Fresh sidecars  (~/.sound-archive/work/<hash>/archive/*.embedding.json):
      "served_by": "remote", "device": "cuda", "elapsed_ms" in the low hundreds
  Expect throughput far above the old ~275 files/hour (no more 2 GB load per file).

🍏 …/sound-archive 🌿 main $  🐍 v3.14.6 🕚 2026-08-01 1:28:14 PM
👉 ./ingest.sh status
! ingest: not running
▸ index: 128973 assets  (last indexed: 2026-08-01T18:21:38Z)
▸ run log tail (/Users/danielramirez/.workchain/runs/latest.log):
2026-08-01T13:27:01-0500 INFO  features completed
2026-08-01T13:27:01-0500 DEBUG /Users/danielramirez/repos/lufs-workchain/lib/workchain_verify.py:681: DeprecationWarning: datetime.datetime.utcnow() is deprecated and scheduled for removal in a future version. Use timezone-aware objects to represent datetimes in UTC: datetime.datetime.now(datetime.UTC).
2026-08-01T13:27:01-0500 DEBUG   "verified_at": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
2026-08-01T13:27:01-0500 DEBUG ✓ features — verified (4/4 checks passed)
2026-08-01T13:27:01-0500 INFO  Step completed: features  (0s)  ←  ClosedHH Lemon.wav
2026-08-01T13:27:01-0500 STEP  Executing step: hook  ←  ClosedHH Lemon.wav
2026-08-01T13:27:01-0500 FILE  step=hook file=/Users/danielramirez/Samples/Samples/sampleLibrary/NI/Astral Flutter Library/Samples/Drums/Hihat/ClosedHH Lemon.wav
2026-08-01T13:27:01-0500 DEBUG /Users/danielramirez/repos/lufs-workchain/lib/workchain_preflight.py:321: DeprecationWarning: datetime.datetime.utcnow() is deprecated and scheduled for removal in a future version. Use timezone-aware objects to represent datetimes in UTC: datetime.datetime.now(datetime.UTC).
2026-08-01T13:27:01-0500 DEBUG   "checked_at": datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ"),
2026-08-01T13:27:01-0500 DEBUG ✓ hook — dependencies satisfied (2/2 checks)
2026-08-01T13:27:01-0500 DEBUG Step runner initialized with context: /Users/danielramirez/.sound-archive/work/bce7f066235c/context.json
2026-08-01T13:27:01-0500 STEP  Running: hook
2026-08-01T13:27:02-0500 ERROR hook failed (clip or waveform missing)
2026-08-01T13:27:02-0500 ERROR Step failed: hook
2026-08-01T13:27:02-0500 ERROR Chain halted: step 'hook' failed

---
ingest.sh output:

🍏 …/sound-archive 🌿 main $  🐍 v3.14.6 🕚 2026-08-01 1:22:11 PM
👉 /Users/danielramirez/repos/sound-archive/ingest.sh run --foreground --samples /Users/danielramirez/Samples/Samples/sampleLibrary --embedder clap-remote --endpoint http://100.125.210.60:8770 --env-file /Users/danielramirez/.config/serve-embed/client.env --no-preflight
▸ foreground ingest: /Users/danielramirez/Samples/Samples/sampleLibrary (embedder=clap-remote, endpoint=http://100.125.210.60:8770, db=/Users/danielramirez/.sound-archive/archive.db)
=== archive ingest ===  2026-08-01T13:22:11-0500
  root     : /Users/danielramirez/Samples/Samples/sampleLibrary
  chain    : archive-ingest-clap-remote.yaml  (embedder=clap-remote)
  db       : /Users/danielramirez/.sound-archive/archive.db
  endpoint : http://100.125.210.60:8770
  run log  : /Users/danielramirez/.workchain/runs/20260801T182211.931316Z-archive-ingest-cdfeee.log
  autoclean: removed 1 old run log(s), keeping newest 25
[1/4] scan: walking /Users/danielramirez/Samples/Samples/sampleLibrary
  scan: 220000 entries seen, 218941 audio files so far (1s)
  scan: 250000 entries seen, 235946 audio files so far (2s)
scan: 243699 standard-audio files under /Users/danielramirez/Samples/Samples/sampleLibrary  (from 259319 entries, 2s)
[2/4] dedup L1: hashing 243699 files (reads every byte — this is the resume cost)
  hash: 2000/243699 files (0.8%)  1742 files/s  1.1GB at 958.1MB/s  eta 2m18s
  hash: 4000/243699 files (1.6%)  1379 files/s  2.4GB at 838.0MB/s  eta 2m53s
  hash: 6000/243699 files (2.5%)  1442 files/s  2.9GB at 719.1MB/s  eta 2m44s
  hash: 8000/243699 files (3.3%)  1471 files/s  3.6GB at 675.0MB/s  eta 2m40s
  hash: 10000/243699 files (4.1%)  1495 files/s  4.2GB at 638.9MB/s  eta 2m36s
  hash: 12000/243699 files (4.9%)  1491 files/s  4.9GB at 625.1MB/s  eta 2m35s
  hash: 14000/243699 files (5.7%)  1485 files/s  5.6GB at 610.5MB/s  eta 2m34s
  hash: 16000/243699 files (6.6%)  1499 files/s  6.2GB at 590.6MB/s  eta 2m31s
  hash: 18000/243699 files (7.4%)  1524 files/s  6.5GB at 561.7MB/s  eta 2m28s
  hash: 20000/243699 files (8.2%)  1537 files/s  6.8GB at 536.4MB/s  eta 2m25s
  hash: 22000/243699 files (9.0%)  1562 files/s  7.3GB at 529.7MB/s  eta 2m21s
  hash: 24000/243699 files (9.8%)  1574 files/s  7.7GB at 519.5MB/s  eta 2m19s
  hash: 26000/243699 files (10.7%)  1629 files/s  8.1GB at 518.5MB/s  eta 2m13s
  hash: 28000/243699 files (11.5%)  1645 files/s  8.7GB at 521.0MB/s  eta 2m11s
  hash: 30000/243699 files (12.3%)  1667 files/s  9.2GB at 525.5MB/s  eta 2m08s
  hash: 32000/243699 files (13.1%)  1595 files/s  11.8GB at 600.3MB/s  eta 2m12s
  hash: 32821/243699 files (13.5%)  1308 files/s  21.8GB at 891.2MB/s  eta 2m41s
  hash: 32948/243699 files (13.5%)  1095 files/s  30.5GB at 1.0GB/s  eta 3m12s
  hash: 34948/243699 files (14.3%)  1029 files/s  36.4GB at 1.1GB/s  eta 3m22s
  hash: 36948/243699 files (15.2%)  1053 files/s  37.5GB at 1.1GB/s  eta 3m16s
  hash: 38948/243699 files (16.0%)  1080 files/s  38.3GB at 1.1GB/s  eta 3m09s
  hash: 40948/243699 files (16.8%)  1097 files/s  39.5GB at 1.1GB/s  eta 3m04s
  hash: 42948/243699 files (17.6%)  1111 files/s  40.6GB at 1.1GB/s  eta 3m00s
  hash: 44948/243699 files (18.4%)  1127 files/s  41.8GB at 1.0GB/s  eta 2m56s
  hash: 46948/243699 files (19.3%)  1146 files/s  42.6GB at 1.0GB/s  eta 2m51s
  hash: 48948/243699 files (20.1%)  1158 files/s  43.7GB at 1.0GB/s  eta 2m48s
  hash: 50948/243699 files (20.9%)  1174 files/s  44.8GB at 1.0GB/s  eta 2m44s
  hash: 52948/243699 files (21.7%)  1193 files/s  45.6GB at 1.0GB/s  eta 2m39s
  hash: 54948/243699 files (22.5%)  1207 files/s  46.8GB at 1.0GB/s  eta 2m36s
  hash: 56948/243699 files (23.4%)  1217 files/s  47.9GB at 1.0GB/s  eta 2m33s
  hash: 58948/243699 files (24.2%)  1233 files/s  48.7GB at 1.0GB/s  eta 2m29s
  hash: 60948/243699 files (25.0%)  1244 files/s  49.9GB at 1.0GB/s  eta 2m26s
  hash: 62948/243699 files (25.8%)  1255 files/s  51.0GB at 1.0GB/s  eta 2m24s
  hash: 64948/243699 files (26.7%)  1270 files/s  51.8GB at 1.0GB/s  eta 2m20s
  hash: 66948/243699 files (27.5%)  1275 files/s  53.0GB at 1.0GB/s  eta 2m18s
  hash: 68948/243699 files (28.3%)  1283 files/s  54.2GB at 1.0GB/s  eta 2m16s
  hash: 70948/243699 files (29.1%)  1295 files/s  55.1GB at 1.0GB/s  eta 2m13s
  hash: 72948/243699 files (29.9%)  1303 files/s  56.2GB at 1.0GB/s  eta 2m11s
  hash: 74948/243699 files (30.8%)  1308 files/s  57.4GB at 1.0GB/s  eta 2m08s
  hash: 76948/243699 files (31.6%)  1313 files/s  58.6GB at 1024.0MB/s  eta 2m06s
  hash: 78948/243699 files (32.4%)  1327 files/s  59.4GB at 1022.3MB/s  eta 2m04s
  hash: 80948/243699 files (33.2%)  1334 files/s  60.6GB at 1022.6MB/s  eta 2m02s
  hash: 82948/243699 files (34.0%)  1339 files/s  61.8GB at 1022.2MB/s  eta 2m00s
  hash: 84948/243699 files (34.9%)  1350 files/s  62.6GB at 1019.1MB/s  eta 1m57s
  hash: 86948/243699 files (35.7%)  1357 files/s  63.6GB at 1017.2MB/s  eta 1m55s
  hash: 88948/243699 files (36.5%)  1350 files/s  66.0GB at 1.0GB/s  eta 1m54s
  hash: 90948/243699 files (37.3%)  1344 files/s  67.9GB at 1.0GB/s  eta 1m53s
  hash: 92948/243699 files (38.1%)  1337 files/s  69.7GB at 1.0GB/s  eta 1m52s
  hash: 94948/243699 files (39.0%)  1318 files/s  72.5GB at 1.0GB/s  eta 1m52s
  hash: 96948/243699 files (39.8%)  1310 files/s  74.5GB at 1.0GB/s  eta 1m52s
  hash: 98948/243699 files (40.6%)  1291 files/s  77.9GB at 1.0GB/s  eta 1m52s
  hash: 100948/243699 files (41.4%)  1271 files/s  81.2GB at 1.0GB/s  eta 1m52s
  hash: 102948/243699 files (42.2%)  1263 files/s  83.9GB at 1.0GB/s  eta 1m51s
  hash: 104948/243699 files (43.1%)  1253 files/s  86.4GB at 1.0GB/s  eta 1m50s
  hash: 106948/243699 files (43.9%)  1241 files/s  89.5GB at 1.0GB/s  eta 1m50s
  hash: 108948/243699 files (44.7%)  1246 files/s  90.6GB at 1.0GB/s  eta 1m48s
  hash: 110948/243699 files (45.5%)  1248 files/s  91.9GB at 1.0GB/s  eta 1m46s
  hash: 112948/243699 files (46.3%)  1239 files/s  94.1GB at 1.0GB/s  eta 1m45s
  hash: 114948/243699 files (47.2%)  1237 files/s  96.2GB at 1.0GB/s  eta 1m44s
  hash: 116948/243699 files (48.0%)  1236 files/s  98.2GB at 1.0GB/s  eta 1m42s
  hash: 118948/243699 files (48.8%)  1228 files/s  100.5GB at 1.0GB/s  eta 1m41s
  hash: 120948/243699 files (49.6%)  1223 files/s  102.7GB at 1.0GB/s  eta 1m40s
  hash: 122948/243699 files (50.5%)  1222 files/s  104.6GB at 1.0GB/s  eta 1m38s
  hash: 124948/243699 files (51.3%)  1222 files/s  106.3GB at 1.0GB/s  eta 1m37s
  hash: 126948/243699 files (52.1%)  1219 files/s  108.5GB at 1.0GB/s  eta 1m35s
  hash: 128948/243699 files (52.9%)  1219 files/s  110.2GB at 1.0GB/s  eta 1m34s
  hash: 130948/243699 files (53.7%)  1214 files/s  112.6GB at 1.0GB/s  eta 1m32s
  hash: 132948/243699 files (54.6%)  1204 files/s  115.9GB at 1.0GB/s  eta 1m31s
  hash: 134948/243699 files (55.4%)  1203 files/s  118.0GB at 1.1GB/s  eta 1m30s
  hash: 136948/243699 files (56.2%)  1193 files/s  121.6GB at 1.1GB/s  eta 1m29s
  hash: 138948/243699 files (57.0%)  1185 files/s  124.0GB at 1.1GB/s  eta 1m28s
  hash: 140948/243699 files (57.8%)  1182 files/s  126.1GB at 1.1GB/s  eta 1m26s
  hash: 142948/243699 files (58.7%)  1172 files/s  128.6GB at 1.1GB/s  eta 1m25s
  hash: 144948/243699 files (59.5%)  1168 files/s  130.7GB at 1.1GB/s  eta 1m24s
  hash: 146948/243699 files (60.3%)  1169 files/s  131.7GB at 1.0GB/s  eta 1m22s
  hash: 148948/243699 files (61.1%)  1153 files/s  135.4GB at 1.0GB/s  eta 1m22s
  hash: 150948/243699 files (61.9%)  1148 files/s  137.7GB at 1.0GB/s  eta 1m20s
  hash: 152948/243699 files (62.8%)  1148 files/s  139.3GB at 1.0GB/s  eta 1m19s
  hash: 154948/243699 files (63.6%)  1144 files/s  141.1GB at 1.0GB/s  eta 1m17s
  hash: 156948/243699 files (64.4%)  1135 files/s  144.2GB at 1.0GB/s  eta 1m16s
  hash: 158948/243699 files (65.2%)  1141 files/s  144.6GB at 1.0GB/s  eta 1m14s
  hash: 160948/243699 files (66.0%)  1147 files/s  145.2GB at 1.0GB/s  eta 1m12s
  hash: 162948/243699 files (66.9%)  1156 files/s  145.6GB at 1.0GB/s  eta 1m09s
  hash: 164948/243699 files (67.7%)  1163 files/s  146.0GB at 1.0GB/s  eta 1m07s
  hash: 166948/243699 files (68.5%)  1167 files/s  146.9GB at 1.0GB/s  eta 1m05s
  hash: 168948/243699 files (69.3%)  1172 files/s  147.6GB at 1.0GB/s  eta 1m03s
  hash: 170948/243699 files (70.1%)  1175 files/s  149.0GB at 1.0GB/s  eta 1m01s
  hash: 172948/243699 files (71.0%)  1175 files/s  150.5GB at 1.0GB/s  eta 1m00s
  hash: 174948/243699 files (71.8%)  1178 files/s  151.8GB at 1.0GB/s  eta 58s
  hash: 176948/243699 files (72.6%)  1171 files/s  154.5GB at 1.0GB/s  eta 56s
  hash: 178948/243699 files (73.4%)  1166 files/s  156.9GB at 1.0GB/s  eta 55s
  hash: 180948/243699 files (74.3%)  1164 files/s  158.7GB at 1.0GB/s  eta 53s
  hash: 182948/243699 files (75.1%)  1166 files/s  160.5GB at 1.0GB/s  eta 52s
  hash: 184948/243699 files (75.9%)  1162 files/s  163.7GB at 1.0GB/s  eta 50s
  hash: 186948/243699 files (76.7%)  1166 files/s  165.0GB at 1.0GB/s  eta 48s
  hash: 188948/243699 files (77.5%)  1169 files/s  166.3GB at 1.0GB/s  eta 46s
  hash: 190948/243699 files (78.4%)  1165 files/s  169.3GB at 1.0GB/s  eta 45s
  hash: 192948/243699 files (79.2%)  1163 files/s  171.2GB at 1.0GB/s  eta 43s
  hash: 194948/243699 files (80.0%)  1163 files/s  172.9GB at 1.0GB/s  eta 41s
  hash: 196948/243699 files (80.8%)  1169 files/s  173.3GB at 1.0GB/s  eta 39s
  hash: 198948/243699 files (81.6%)  1176 files/s  173.6GB at 1.0GB/s  eta 38s
  hash: 200948/243699 files (82.5%)  1183 files/s  174.2GB at 1.0GB/s  eta 36s
  hash: 202948/243699 files (83.3%)  1185 files/s  175.3GB at 1.0GB/s  eta 34s
  hash: 204948/243699 files (84.1%)  1188 files/s  176.1GB at 1.0GB/s  eta 32s
  hash: 206948/243699 files (84.9%)  1191 files/s  177.3GB at 1.0GB/s  eta 30s
  hash: 208948/243699 files (85.7%)  1193 files/s  178.7GB at 1.0GB/s  eta 29s
  hash: 210948/243699 files (86.6%)  1196 files/s  179.7GB at 1.0GB/s  eta 27s
  hash: 212948/243699 files (87.4%)  1205 files/s  179.8GB at 1.0GB/s  eta 25s
  hash: 214948/243699 files (88.2%)  1213 files/s  180.0GB at 1.0GB/s  eta 23s
  hash: 216948/243699 files (89.0%)  1211 files/s  182.0GB at 1.0GB/s  eta 22s
  hash: 218948/243699 files (89.8%)  1207 files/s  184.3GB at 1.0GB/s  eta 20s
  hash: 220948/243699 files (90.7%)  1203 files/s  186.7GB at 1.0GB/s  eta 18s
  hash: 222948/243699 files (91.5%)  1201 files/s  188.9GB at 1.0GB/s  eta 17s
  hash: 224948/243699 files (92.3%)  1196 files/s  192.1GB at 1.0GB/s  eta 15s
  hash: 226714/243699 files (93.0%)  1174 files/s  201.3GB at 1.0GB/s  eta 14s
  hash: 226796/243699 files (93.1%)  1144 files/s  212.7GB at 1.1GB/s  eta 14s
  hash: 226868/243699 files (93.1%)  1116 files/s  223.8GB at 1.1GB/s  eta 15s
  hash: 226948/243699 files (93.1%)  1089 files/s  234.6GB at 1.1GB/s  eta 15s
  hash: 228625/243699 files (93.8%)  1071 files/s  243.3GB at 1.1GB/s  eta 14s
  hash: 230625/243699 files (94.6%)  1071 files/s  245.7GB at 1.1GB/s  eta 12s
  hash: 232625/243699 files (95.5%)  1067 files/s  249.5GB at 1.1GB/s  eta 10s
  hash: 234625/243699 files (96.3%)  1059 files/s  254.5GB at 1.1GB/s  eta 8s
  hash: 236625/243699 files (97.1%)  1049 files/s  260.7GB at 1.2GB/s  eta 6s
  hash: 238625/243699 files (97.9%)  1039 files/s  266.2GB at 1.2GB/s  eta 4s
  hash: 240188/243699 files (98.6%)  1024 files/s  275.9GB at 1.2GB/s  eta 3s
  hash: 241949/243699 files (99.3%)  1010 files/s  285.1GB at 1.2GB/s  eta 1s
  hash: 243576/243699 files (99.9%)  996 files/s  295.2GB at 1.2GB/s  eta 0s
  hash: 243699/243699 files (100.0%)  980 files/s  303.7GB at 1.2GB/s  elapsed 4m08s
dedup L1: 241669 unique / 243699 files  (2030 exact-dupe copies collapsed)
dedup L2 (chromaprint): fpcalc not found — transcode-dupe pass DEFERRED (install chromaprint)
[3/4] resume: 128973 already indexed, 112696 to ingest
[4/4] ingest: 112696 files via archive-ingest-clap-remote.yaml
[1/112696] 545ca5b4  [archive]  /Users/danielramirez/Samples/Samples/sampleLibrary/Sonniss/Sonniss.com-GDC2024-GameAudioBundle5of9/Pole Position - Porsche Carrera GT 2005/Porsche, Carrera, GT, t7, Onbrd, Start, Idle, Steady, Blips, Off, Engine, Mix.wav
[1/112696] FAIL rc=1 after 1.76s: /Users/danielramirez/Samples/Samples/sampleLibrary/Sonniss/Sonniss.com-GDC2024-GameAudioBundle5of9/Pole Position - Porsche Carrera GT 2005/Porsche, Carrera, GT, t7, Onbrd, Start, Idle, Steady, Blips, Off, Engine, Mix.wav
        | Registered output: probe.probe -> /Users/danielramirez/.sound-archive/work/545ca5b491b9/archive/Porsche, Carrera, GT, t7, Onbrd, Start, Idle, Steady, Blips, Off, Engine, Mix.probe.json (type: json)
        | Registered output: features.features -> /Users/danielramirez/.sound-archive/work/545ca5b491b9/archive/Porsche, Carrera, GT, t7, Onbrd, Start, Idle, Steady, Blips, Off, Engine, Mix.features.json (type: json)
        | [in#0 @ 0x75700c000] Error opening input: Invalid data found when processing input
        | Error opening input file /Users/danielramirez/Samples/Samples/sampleLibrary/Sonniss/Sonniss.com-GDC2024-GameAudioBundle5of9/Pole Position - Porsche Carrera GT 2005/Porsche, Carrera, GT, t7, Onbrd, Start, Idle, Steady, Blips, Off, Engine, Mix.wav.
        | Error opening input files: Invalid data found when processing input
        | [in#0 @ 0x75b028000] Error opening input: Invalid data found when processing input
        | Error opening input file /Users/danielramirez/Samples/Samples/sampleLibrary/Sonniss/Sonniss.com-GDC2024-GameAudioBundle5of9/Pole Position - Porsche Carrera GT 2005/Porsche, Carrera, GT, t7, Onbrd, Start, Idle, Steady, Blips, Off, Engine, Mix.wav.
        | Error opening input files: Invalid data found when processing input
        | [13:26:34] ERROR: hook failed (clip or waveform missing)
        | Registered output: hook.hook_clip -> /Users/danielramirez/.sound-archive/work/545ca5b491b9/archive/Porsche, Carrera, GT, t7, Onbrd, Start, Idle, Steady, Blips, Off, Engine, Mix.hook.wav (type: file)
        | [13:26:34] ERROR: Step failed: hook
        | [13:26:34] ERROR: Chain halted: step 'hook' failed
[2/112696] f174d34d  [archive]  /Users/danielramirez/Samples/Samples/sampleLibrary/Sonniss/Sonniss.com-GDC2024-GameAudioBundle5of9/Pole Position - Morris Oxford 1969/Morris Oxford - t8 - EXT - MEDIUM - Various - Distant - D100.wav
[2/112696] FAIL rc=1 after 1.43s: /Users/danielramirez/Samples/Samples/sampleLibrary/Sonniss/Sonniss.com-GDC2024-GameAudioBundle5of9/Pole Position - Morris Oxford 1969/Morris Oxford - t8 - EXT - MEDIUM - Various - Distant - D100.wav
        | Registered output: probe.probe -> /Users/danielramirez/.sound-archive/work/f174d34dfd28/archive/Morris Oxford - t8 - EXT - MEDIUM - Various - Distant - D100.probe.json (type: json)
        | Registered output: features.features -> /Users/danielramirez/.sound-archive/work/f174d34dfd28/archive/Morris Oxford - t8 - EXT - MEDIUM - Various - Distant - D100.features.json (type: json)
        | [in#0 @ 0xa4d010000] Error opening input: Invalid data found when processing input
        | Error opening input file /Users/danielramirez/Samples/Samples/sampleLibrary/Sonniss/Sonniss.com-GDC2024-GameAudioBundle5of9/Pole Position - Morris Oxford 1969/Morris Oxford - t8 - EXT - MEDIUM - Various - Distant - D100.wav.
        | Error opening input files: Invalid data found when processing input
        | [in#0 @ 0xbd0c20000] Error opening input: Invalid data found when processing input
        | Error opening input file /Users/danielramirez/Samples/Samples/sampleLibrary/Sonniss/Sonniss.com-GDC2024-GameAudioBundle5of9/Pole Position - Morris Oxford 1969/Morris Oxford - t8 - EXT - MEDIUM - Various - Distant - D100.wav.
        | Error opening input files: Invalid data found when processing input
        | [13:26:36] ERROR: hook failed (clip or waveform missing)
        | Registered output: hook.hook_clip -> /Users/danielramirez/.sound-archive/work/f174d34dfd28/archive/Morris Oxford - t8 - EXT - MEDIUM - Various - Distant - D100.hook.wav (type: file)
        | [13:26:36] ERROR: Step failed: hook
        | [13:26:36] ERROR: Chain halted: step 'hook' failed
[3/112696] b1be6ae7  [archive]  /Users/danielramirez/Samples/Samples/sampleLibrary/Sonniss/Sonniss.com-GDC2024-GameAudioBundle5of9/Pole Position - Polaris Sportsman 500 XP 2006/Polaris Sportsman 500 - t9 - ONBRD - MEDIUM - Drive Various - ENGINE - Transmission - DPA4062.wav
[3/112696] FAIL rc=1 after 1.37s: /Users/danielramirez/Samples/Samples/sampleLibrary/Sonniss/Sonniss.com-GDC2024-GameAudioBundle5of9/Pole Position - Polaris Sportsman 500 XP 2006/Polaris Sportsman 500 - t9 - ONBRD - MEDIUM - Drive Various - ENGINE - Transmission - DPA4062.wav
        | Registered output: probe.probe -> /Users/danielramirez/.sound-archive/work/b1be6ae7f1c4/archive/Polaris Sportsman 500 - t9 - ONBRD - MEDIUM - Drive Various - ENGINE - Transmission - DPA4062.probe.json (type: json)
        | Registered output: features.features -> /Users/danielramirez/.sound-archive/work/b1be6ae7f1c4/archive/Polaris Sportsman 500 - t9 - ONBRD - MEDIUM - Drive Various - ENGINE - Transmission - DPA4062.features.json (type: json)
        | [in#0 @ 0x74ac1c000] Error opening input: Invalid data found when processing input
        | Error opening input file /Users/danielramirez/Samples/Samples/sampleLibrary/Sonniss/Sonniss.com-GDC2024-GameAudioBundle5of9/Pole Position - Polaris Sportsman 500 XP 2006/Polaris Sportsman 500 - t9 - ONBRD - MEDIUM - Drive Various - ENGINE - Transmission - DPA4062.wav.
        | Error opening input files: Invalid data found when processing input
        | [in#0 @ 0xc3cc20000] Error opening input: Invalid data found when processing input
        | Error opening input file /Users/danielramirez/Samples/Samples/sampleLibrary/Sonniss/Sonniss.com-GDC2024-GameAudioBundle5of9/Pole Position - Polaris Sportsman 500 XP 2006/Polaris Sportsman 500 - t9 - ONBRD - MEDIUM - Drive Various - ENGINE - Transmission - DPA4062.wav.
        | Error opening input files: Invalid data found when processing input
        | [13:26:37] ERROR: hook failed (clip or waveform missing)
        | Registered output: hook.hook_clip -> /Users/danielramirez/.sound-archive/work/b1be6ae7f1c4/archive/Polaris Sportsman 500 - t9 - ONBRD - MEDIUM - Drive Various - ENGINE - Transmission - DPA4062.hook.wav (type: file)
        | [13:26:37] ERROR: Step failed: hook
        | [13:26:37] ERROR: Chain halted: step 'hook' failed
[4/112696] 34640552  [archive]  /Users/danielramirez/Samples/Samples/sampleLibrary/Sonniss/Sonniss.com-GDC2024-GameAudioBundle5of9/Pole Position - Peugeot 205 T 16 GrB Evo 2 P200 1985/Peugeot 205 - t2 - ONBRD - RAMPS - Start Drive Off - ENGINE - Center - MKH8020.wav
[4/112696] FAIL rc=1 after 1.43s: /Users/danielramirez/Samples/Samples/sampleLibrary/Sonniss/Sonniss.com-GDC2024-GameAudioBundle5of9/Pole Position - Peugeot 205 T 16 GrB Evo 2 P200 1985/Peugeot 205 - t2 - ONBRD - RAMPS - Start Drive Off - ENGINE - Center - MKH8020.wav
        | Registered output: probe.probe -> /Users/danielramirez/.sound-archive/work/34640552e62a/archive/Peugeot 205 - t2 - ONBRD - RAMPS - Start Drive Off - ENGINE - Center - MKH8020.probe.json (type: json)
        | Registered output: features.features -> /Users/danielramirez/.sound-archive/work/34640552e62a/archive/Peugeot 205 - t2 - ONBRD - RAMPS - Start Drive Off - ENGINE - Center - MKH8020.features.json (type: json)
        | [in#0 @ 0xba0c1c000] Error opening input: Invalid data found when processing input
        | Error opening input file /Users/danielramirez/Samples/Samples/sampleLibrary/Sonniss/Sonniss.com-GDC2024-GameAudioBundle5of9/Pole Position - Peugeot 205 T 16 GrB Evo 2 P200 1985/Peugeot 205 - t2 - ONBRD - RAMPS - Start Drive Off - ENGINE - Center - MKH8020.wav.
        | Error opening input files: Invalid data found when processing input
        | [in#0 @ 0xc7f01c000] Error opening input: Invalid data found when processing input
        | Error opening input file /Users/danielramirez/Samples/Samples/sampleLibrary/Sonniss/Sonniss.com-GDC2024-GameAudioBundle5of9/Pole Position - Peugeot 205 T 16 GrB Evo 2 P200 1985/Peugeot 205 - t2 - ONBRD - RAMPS - Start Drive Off - ENGINE - Center - MKH8020.wav.
        | Error opening input files: Invalid data found when processing input
        | [13:26:39] ERROR: hook failed (clip or waveform missing)
        | Registered output: hook.hook_clip -> /Users/danielramirez/.sound-archive/work/34640552e62a/archive/Peugeot 205 - t2 - ONBRD - RAMPS - Start Drive Off - ENGINE - Center - MKH8020.hook.wav (type: file)
        | [13:26:39] ERROR: Step failed: hook
        | [13:26:39] ERROR: Chain halted: step 'hook' failed
[5/112696] 9bb4b0f7  [archive]  /Users/danielramirez/Samples/Samples/sampleLibrary/Sonniss/Sonniss.com-GDC2024-GameAudioBundle3of9/Pole Position - Audi Ur-Quattro 1983/Audi Quattro - t10 - EXT - FAST - Various - MS Decoded - RSM191.wav
[5/112696] FAIL rc=1 after 1.44s: /Users/danielramirez/Samples/Samples/sampleLibrary/Sonniss/Sonniss.com-GDC2024-GameAudioBundle3of9/Pole Position - Audi Ur-Quattro 1983/Audi Quattro - t10 - EXT - FAST - Various - MS Decoded - RSM191.wav
        | Registered output: probe.probe -> /Users/danielramirez/.sound-archive/work/9bb4b0f79166/archive/Audi Quattro - t10 - EXT - FAST - Various - MS Decoded - RSM191.probe.json (type: json)
        | Registered output: features.features -> /Users/danielramirez/.sound-archive/work/9bb4b0f79166/archive/Audi Quattro - t10 - EXT - FAST - Various - MS Decoded - RSM191.features.json (type: json)
        | [in#0 @ 0xa5b010000] Error opening input: Invalid data found when processing input
        | Error opening input file /Users/danielramirez/Samples/Samples/sampleLibrary/Sonniss/Sonniss.com-GDC2024-GameAudioBundle3of9/Pole Position - Audi Ur-Quattro 1983/Audi Quattro - t10 - EXT - FAST - Various - MS Decoded - RSM191.wav.
        | Error opening input files: Invalid data found when processing input
        | [in#0 @ 0xcb0c28000] Error opening input: Invalid data found when processing input
        | Error opening input file /Users/danielramirez/Samples/Samples/sampleLibrary/Sonniss/Sonniss.com-GDC2024-GameAudioBundle3of9/Pole Position - Audi Ur-Quattro 1983/Audi Quattro - t10 - EXT - FAST - Various - MS Decoded - RSM191.wav.
        | Error opening input files: Invalid data found when processing input
        | [13:26:40] ERROR: hook failed (clip or waveform missing)
        | Registered output: hook.hook_clip -> /Users/danielramirez/.sound-archive/work/9bb4b0f79166/archive/Audi Quattro - t10 - EXT - FAST - Various - MS Decoded - RSM191.hook.wav (type: file)
        | [13:26:40] ERROR: Step failed: hook
        | [13:26:40] ERROR: Chain halted: step 'hook' failed
[6/112696] 49bb6a4e  [archive]  /Users/danielramirez/Samples/Samples/sampleLibrary/Sonniss/Sonniss.com-GDC2024-GameAudioBundle3of9/Pole Position - Beechcraft Baron 58 1969/Beechcraft Baron 58 - t4 - EXT - LAND - By - Distant - ORTF - CMC6.wav
[6/112696] FAIL rc=1 after 1.43s: /Users/danielramirez/Samples/Samples/sampleLibrary/Sonniss/Sonniss.com-GDC2024-GameAudioBundle3of9/Pole Position - Beechcraft Baron 58 1969/Beechcraft Baron 58 - t4 - EXT - LAND - By - Distant - ORTF - CMC6.wav
        | Registered output: probe.probe -> /Users/danielramirez/.sound-archive/work/49bb6a4eb8fd/archive/Beechcraft Baron 58 - t4 - EXT - LAND - By - Distant - ORTF - CMC6.probe.json (type: json)
        | Registered output: features.features -> /Users/danielramirez/.sound-archive/work/49bb6a4eb8fd/archive/Beechcraft Baron 58 - t4 - EXT - LAND - By - Distant - ORTF - CMC6.features.json (type: json)
        | [in#0 @ 0x843010000] Error opening input: Invalid data found when processing input
        | Error opening input file /Users/danielramirez/Samples/Samples/sampleLibrary/Sonniss/Sonniss.com-GDC2024-GameAudioBundle3of9/Pole Position - Beechcraft Baron 58 1969/Beechcraft Baron 58 - t4 - EXT - LAND - By - Distant - ORTF - CMC6.wav.
        | Error opening input files: Invalid data found when processing input
        | [in#0 @ 0xa1ac28000] Error opening input: Invalid data found when processing input
        | Error opening input file /Users/danielramirez/Samples/Samples/sampleLibrary/Sonniss/Sonniss.com-GDC2024-GameAudioBundle3of9/Pole Position - Beechcraft Baron 58 1969/Beechcraft Baron 58 - t4 - EXT - LAND - By - Distant - ORTF - CMC6.wav.
        | Error opening input files: Invalid data found when processing input
        | [13:26:41] ERROR: hook failed (clip or waveform missing)
        | Registered output: hook.hook_clip -> /Users/danielramirez/.sound-archive/work/49bb6a4eb8fd/archive/Beechcraft Baron 58 - t4 - EXT - LAND - By - Distant - ORTF - CMC6.hook.wav (type: file)
        | [13:26:41] ERROR: Step failed: hook
        | [13:26:41] ERROR: Chain halted: step 'hook' failed
[7/112696] 5b384bc9  [archive]  /Users/danielramirez/Samples/Samples/sampleLibrary/Sonniss/Sonniss.com-GDC2024-GameAudioBundle6of9/Pole Position - The Warfare 2 Library/RPG - FIRING AND IMPACT - Through Car Roof Hit Metal - XY - MKH8040.wav
[7/112696] FAIL rc=1 after 0.43s: /Users/danielramirez/Samples/Samples/sampleLibrary/Sonniss/Sonniss.com-GDC2024-GameAudioBundle6of9/Pole Position - The Warfare 2 Library/RPG - FIRING AND IMPACT - Through Car Roof Hit Metal - XY - MKH8040.wav
        |                      ~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^
        |   File "/opt/homebrew/Cellar/python@3.14/3.14.6/Frameworks/Python.framework/Versions/3.14/lib/python3.14/subprocess.py", line 2198, in _communicate
        |     stderr = self._translate_newlines(stderr,
        |                                       self.stderr.encoding,
        |                                       self.stderr.errors)
        |   File "/opt/homebrew/Cellar/python@3.14/3.14.6/Frameworks/Python.framework/Versions/3.14/lib/python3.14/subprocess.py", line 1099, in _translate_newlines
        |     data = data.decode(encoding, errors)
        | UnicodeDecodeError: 'utf-8' codec can't decode byte 0xe4 in position 1623: invalid continuation byte
        | [13:26:42] ERROR: probe failed to produce /Users/danielramirez/.sound-archive/work/5b384bc95f6c/archive/RPG - FIRING AND IMPACT - Through Car Roof Hit Metal - XY - MKH8040.probe.json
        | Registered output: probe.probe -> /Users/danielramirez/.sound-archive/work/5b384bc95f6c/archive/RPG - FIRING AND IMPACT - Through Car Roof Hit Metal - XY - MKH8040.probe.json (type: json)
        | [13:26:42] ERROR: Step failed: probe
        | [13:26:42] ERROR: Chain halted: step 'probe' failed
[8/112696] d50261cd  [archive]  /Users/danielramirez/Samples/Samples/sampleLibrary/NI/Liquid Energy Library/Samples/Loops/Construction/Memory/Drums[124] Memory 4.wav
[8/112696] FAIL rc=1 after 0.44s: /Users/danielramirez/Samples/Samples/sampleLibrary/NI/Liquid Energy Library/Samples/Loops/Construction/Memory/Drums[124] Memory 4.wav
        |                      ~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^
        |   File "/opt/homebrew/Cellar/python@3.14/3.14.6/Frameworks/Python.framework/Versions/3.14/lib/python3.14/subprocess.py", line 2198, in _communicate
        |     stderr = self._translate_newlines(stderr,
        |                                       self.stderr.encoding,
        |                                       self.stderr.errors)
        |   File "/opt/homebrew/Cellar/python@3.14/3.14.6/Frameworks/Python.framework/Versions/3.14/lib/python3.14/subprocess.py", line 1099, in _translate_newlines
        |     data = data.decode(encoding, errors)
        | UnicodeDecodeError: 'utf-8' codec can't decode byte 0xe6 in position 303: invalid continuation byte
        | [13:26:42] ERROR: probe failed to produce /Users/danielramirez/.sound-archive/work/d50261cd0360/archive/Drums[124] Memory 4.probe.json
        | Registered output: probe.probe -> /Users/danielramirez/.sound-archive/work/d50261cd0360/archive/Drums[124] Memory 4.probe.json (type: json)
        | [13:26:42] ERROR: Step failed: probe
        | [13:26:42] ERROR: Chain halted: step 'probe' failed
[9/112696] 4dc610e2  [archive]  /Users/danielramirez/Samples/Samples/sampleLibrary/NI/Liquid Energy Library/Samples/Loops/Construction/Julien/Drums[126] Julien 2.wav
[9/112696] FAIL rc=1 after 0.45s: /Users/danielramirez/Samples/Samples/sampleLibrary/NI/Liquid Energy Library/Samples/Loops/Construction/Julien/Drums[126] Julien 2.wav
        |                      ~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^
        |   File "/opt/homebrew/Cellar/python@3.14/3.14.6/Frameworks/Python.framework/Versions/3.14/lib/python3.14/subprocess.py", line 2198, in _communicate
        |     stderr = self._translate_newlines(stderr,
        |                                       self.stderr.encoding,
        |                                       self.stderr.errors)
        |   File "/opt/homebrew/Cellar/python@3.14/3.14.6/Frameworks/Python.framework/Versions/3.14/lib/python3.14/subprocess.py", line 1099, in _translate_newlines
        |     data = data.decode(encoding, errors)
        | UnicodeDecodeError: 'utf-8' codec can't decode byte 0xa6 in position 303: invalid start byte
        | [13:26:43] ERROR: probe failed to produce /Users/danielramirez/.sound-archive/work/4dc610e2d92b/archive/Drums[126] Julien 2.probe.json
        | Registered output: probe.probe -> /Users/danielramirez/.sound-archive/work/4dc610e2d92b/archive/Drums[126] Julien 2.probe.json (type: json)
        | [13:26:43] ERROR: Step failed: probe
        | [13:26:43] ERROR: Chain halted: step 'probe' failed
[10/112696] 29a59fb9  [archive]  /Users/danielramirez/Samples/Samples/sampleLibrary/NI/Astral Flutter Library/Samples/Drums/Kick/Kick Fingers 3.wav
[10/112696] FAIL rc=1 after 1.42s: /Users/danielramirez/Samples/Samples/sampleLibrary/NI/Astral Flutter Library/Samples/Drums/Kick/Kick Fingers 3.wav
        | [in#0 @ 0xc55010000] too short LIST tag
        | [in#0 @ 0xc54c1c000] Error opening input: Invalid data found when processing input
        | Error opening input file /Users/danielramirez/Samples/Samples/sampleLibrary/NI/Astral Flutter Library/Samples/Drums/Kick/Kick Fingers 3.wav.
        | Error opening input files: Invalid data found when processing input
        | [in#0 @ 0xcbac28000] too short LIST tag
        | [in#0 @ 0xcbac20000] Error opening input: Invalid data found when processing input
        | Error opening input file /Users/danielramirez/Samples/Samples/sampleLibrary/NI/Astral Flutter Library/Samples/Drums/Kick/Kick Fingers 3.wav.
        | Error opening input files: Invalid data found when processing input
        | [13:26:44] ERROR: hook failed (clip or waveform missing)
        | Registered output: hook.hook_clip -> /Users/danielramirez/.sound-archive/work/29a59fb9cb91/archive/Kick Fingers 3.hook.wav (type: file)
        | [13:26:44] ERROR: Step failed: hook
        | [13:26:44] ERROR: Chain halted: step 'hook' failed
[11/112696] 10dcf7eb  [archive]  /Users/danielramirez/Samples/Samples/sampleLibrary/NI/Astral Flutter Library/Samples/Drums/Kick/Kick Medizin 1.wav
[11/112696] FAIL rc=1 after 2.04s: /Users/danielramirez/Samples/Samples/sampleLibrary/NI/Astral Flutter Library/Samples/Drums/Kick/Kick Medizin 1.wav
        | [in#0 @ 0x795010000] too short LIST tag
        | [in#0 @ 0x794c1c000] Error opening input: Invalid data found when processing input
        | Error opening input file /Users/danielramirez/Samples/Samples/sampleLibrary/NI/Astral Flutter Library/Samples/Drums/Kick/Kick Medizin 1.wav.
        | Error opening input files: Invalid data found when processing input
        | [in#0 @ 0xcab018000] too short LIST tag
        | [in#0 @ 0xcaac28000] Error opening input: Invalid data found when processing input
        | Error opening input file /Users/danielramirez/Samples/Samples/sampleLibrary/NI/Astral Flutter Library/Samples/Drums/Kick/Kick Medizin 1.wav.
        | Error opening input files: Invalid data found when processing input
        | [13:26:46] ERROR: hook failed (clip or waveform missing)
        | Registered output: hook.hook_clip -> /Users/danielramirez/.sound-archive/work/10dcf7eb0924/archive/Kick Medizin 1.hook.wav (type: file)
        | [13:26:46] ERROR: Step failed: hook
        | [13:26:46] ERROR: Chain halted: step 'hook' failed
[12/112696] 08b59f01  [archive]  /Users/danielramirez/Samples/Samples/sampleLibrary/NI/Astral Flutter Library/Samples/Drums/Kick/Kick Fingers 2.wav
[12/112696] FAIL rc=1 after 1.94s: /Users/danielramirez/Samples/Samples/sampleLibrary/NI/Astral Flutter Library/Samples/Drums/Kick/Kick Fingers 2.wav
        | [in#0 @ 0x80f010000] too short LIST tag
        | [in#0 @ 0x80ec1c000] Error opening input: Invalid data found when processing input
        | Error opening input file /Users/danielramirez/Samples/Samples/sampleLibrary/NI/Astral Flutter Library/Samples/Drums/Kick/Kick Fingers 2.wav.
        | Error opening input files: Invalid data found when processing input
        | [in#0 @ 0xbbac34000] too short LIST tag
        | [in#0 @ 0xbbb01c000] Error opening input: Invalid data found when processing input
        | Error opening input file /Users/danielramirez/Samples/Samples/sampleLibrary/NI/Astral Flutter Library/Samples/Drums/Kick/Kick Fingers 2.wav.
        | Error opening input files: Invalid data found when processing input
        | [13:26:48] ERROR: hook failed (clip or waveform missing)
        | Registered output: hook.hook_clip -> /Users/danielramirez/.sound-archive/work/08b59f01f089/archive/Kick Fingers 2.hook.wav (type: file)
        | [13:26:48] ERROR: Step failed: hook
        | [13:26:48] ERROR: Chain halted: step 'hook' failed
[13/112696] f610c0df  [archive]  /Users/danielramirez/Samples/Samples/sampleLibrary/NI/Astral Flutter Library/Samples/Drums/Kick/Kick Medizin 2.wav
[13/112696] FAIL rc=1 after 2.43s: /Users/danielramirez/Samples/Samples/sampleLibrary/NI/Astral Flutter Library/Samples/Drums/Kick/Kick Medizin 2.wav
        | [in#0 @ 0xb93018000] too short LIST tag
        | [in#0 @ 0xb93010000] Error opening input: Invalid data found when processing input
        | Error opening input file /Users/danielramirez/Samples/Samples/sampleLibrary/NI/Astral Flutter Library/Samples/Drums/Kick/Kick Medizin 2.wav.
        | Error opening input files: Invalid data found when processing input
        | [in#0 @ 0x820820000] too short LIST tag
        | [in#0 @ 0x821410000] Error opening input: Invalid data found when processing input
        | Error opening input file /Users/danielramirez/Samples/Samples/sampleLibrary/NI/Astral Flutter Library/Samples/Drums/Kick/Kick Medizin 2.wav.
        | Error opening input files: Invalid data found when processing input
        | [13:26:51] ERROR: hook failed (clip or waveform missing)
        | Registered output: hook.hook_clip -> /Users/danielramirez/.sound-archive/work/f610c0df202d/archive/Kick Medizin 2.hook.wav (type: file)
        | [13:26:51] ERROR: Step failed: hook
        | [13:26:51] ERROR: Chain halted: step 'hook' failed
[14/112696] bf9a2952  [archive]  /Users/danielramirez/Samples/Samples/sampleLibrary/NI/Astral Flutter Library/Samples/Drums/Kick/Kick Fingers 1.wav
[14/112696] FAIL rc=1 after 1.98s: /Users/danielramirez/Samples/Samples/sampleLibrary/NI/Astral Flutter Library/Samples/Drums/Kick/Kick Fingers 1.wav
        | [in#0 @ 0x759010000] too short LIST tag
        | [in#0 @ 0x758c1c000] Error opening input: Invalid data found when processing input
        | Error opening input file /Users/danielramirez/Samples/Samples/sampleLibrary/NI/Astral Flutter Library/Samples/Drums/Kick/Kick Fingers 1.wav.
        | Error opening input files: Invalid data found when processing input
        | [in#0 @ 0x813030000] too short LIST tag
        | [in#0 @ 0x813028000] Error opening input: Invalid data found when processing input
        | Error opening input file /Users/danielramirez/Samples/Samples/sampleLibrary/NI/Astral Flutter Library/Samples/Drums/Kick/Kick Fingers 1.wav.
        | Error opening input files: Invalid data found when processing input
        | [13:26:53] ERROR: hook failed (clip or waveform missing)
        | Registered output: hook.hook_clip -> /Users/danielramirez/.sound-archive/work/bf9a29526c92/archive/Kick Fingers 1.hook.wav (type: file)
        | [13:26:53] ERROR: Step failed: hook
        | [13:26:53] ERROR: Chain halted: step 'hook' failed
[15/112696] 07a1fc69  [archive]  /Users/danielramirez/Samples/Samples/sampleLibrary/NI/Astral Flutter Library/Samples/Drums/Kick/Kick Need.wav
[15/112696] FAIL rc=1 after 2.05s: /Users/danielramirez/Samples/Samples/sampleLibrary/NI/Astral Flutter Library/Samples/Drums/Kick/Kick Need.wav
        | [in#0 @ 0x94d018000] too short LIST tag
        | [in#0 @ 0x94d010000] Error opening input: Invalid data found when processing input
        | Error opening input file /Users/danielramirez/Samples/Samples/sampleLibrary/NI/Astral Flutter Library/Samples/Drums/Kick/Kick Need.wav.
        | Error opening input files: Invalid data found when processing input
        | [in#0 @ 0x7e2c28000] too short LIST tag
        | [in#0 @ 0x7e2c20000] Error opening input: Invalid data found when processing input
        | Error opening input file /Users/danielramirez/Samples/Samples/sampleLibrary/NI/Astral Flutter Library/Samples/Drums/Kick/Kick Need.wav.
        | Error opening input files: Invalid data found when processing input
        | [13:26:55] ERROR: hook failed (clip or waveform missing)
        | Registered output: hook.hook_clip -> /Users/danielramirez/.sound-archive/work/07a1fc692194/archive/Kick Need.hook.wav (type: file)
        | [13:26:55] ERROR: Step failed: hook
        | [13:26:55] ERROR: Chain halted: step 'hook' failed
[16/112696] bfe397b2  [archive]  /Users/danielramirez/Samples/Samples/sampleLibrary/NI/Astral Flutter Library/Samples/Drums/Shaker/Shaker Medizin.wav
[16/112696] FAIL rc=1 after 1.95s: /Users/danielramirez/Samples/Samples/sampleLibrary/NI/Astral Flutter Library/Samples/Drums/Shaker/Shaker Medizin.wav
        | [in#0 @ 0x753010000] too short LIST tag
        | [in#0 @ 0x752c1c000] Error opening input: Invalid data found when processing input
        | Error opening input file /Users/danielramirez/Samples/Samples/sampleLibrary/NI/Astral Flutter Library/Samples/Drums/Shaker/Shaker Medizin.wav.
        | Error opening input files: Invalid data found when processing input
        | [in#0 @ 0x949018000] too short LIST tag
        | [in#0 @ 0x948c28000] Error opening input: Invalid data found when processing input
        | Error opening input file /Users/danielramirez/Samples/Samples/sampleLibrary/NI/Astral Flutter Library/Samples/Drums/Shaker/Shaker Medizin.wav.
        | Error opening input files: Invalid data found when processing input
        | [13:26:57] ERROR: hook failed (clip or waveform missing)
        | Registered output: hook.hook_clip -> /Users/danielramirez/.sound-archive/work/bfe397b231fd/archive/Shaker Medizin.hook.wav (type: file)
        | [13:26:57] ERROR: Step failed: hook
        | [13:26:57] ERROR: Chain halted: step 'hook' failed
[17/112696] 80fe39ef  [archive]  /Users/danielramirez/Samples/Samples/sampleLibrary/NI/Astral Flutter Library/Samples/Drums/Shaker/Shaker Smooker.wav
[17/112696] FAIL rc=1 after 1.14s: /Users/danielramirez/Samples/Samples/sampleLibrary/NI/Astral Flutter Library/Samples/Drums/Shaker/Shaker Smooker.wav
        | [in#0 @ 0xb13010000] too short LIST tag
        | [in#0 @ 0xb12c1c000] Error opening input: Invalid data found when processing input
        | Error opening input file /Users/danielramirez/Samples/Samples/sampleLibrary/NI/Astral Flutter Library/Samples/Drums/Shaker/Shaker Smooker.wav.
        | Error opening input files: Invalid data found when processing input
        | [in#0 @ 0xbe7030000] too short LIST tag
        | [in#0 @ 0xbe7028000] Error opening input: Invalid data found when processing input
        | Error opening input file /Users/danielramirez/Samples/Samples/sampleLibrary/NI/Astral Flutter Library/Samples/Drums/Shaker/Shaker Smooker.wav.
        | Error opening input files: Invalid data found when processing input
        | [13:26:58] ERROR: hook failed (clip or waveform missing)
        | Registered output: hook.hook_clip -> /Users/danielramirez/.sound-archive/work/80fe39ef051f/archive/Shaker Smooker.hook.wav (type: file)
        | [13:26:58] ERROR: Step failed: hook
        | [13:26:58] ERROR: Chain halted: step 'hook' failed
[18/112696] 690084f6  [archive]  /Users/danielramirez/Samples/Samples/sampleLibrary/NI/Astral Flutter Library/Samples/Drums/Hihat/ClosedHH GlitterSmurf.wav
[18/112696] FAIL rc=1 after 1.19s: /Users/danielramirez/Samples/Samples/sampleLibrary/NI/Astral Flutter Library/Samples/Drums/Hihat/ClosedHH GlitterSmurf.wav
        | [in#0 @ 0xc03010000] too short LIST tag
        | [in#0 @ 0xc02c1c000] Error opening input: Invalid data found when processing input
        | Error opening input file /Users/danielramirez/Samples/Samples/sampleLibrary/NI/Astral Flutter Library/Samples/Drums/Hihat/ClosedHH GlitterSmurf.wav.
        | Error opening input files: Invalid data found when processing input
        | [in#0 @ 0x798c28000] too short LIST tag
        | [in#0 @ 0x798c20000] Error opening input: Invalid data found when processing input
        | Error opening input file /Users/danielramirez/Samples/Samples/sampleLibrary/NI/Astral Flutter Library/Samples/Drums/Hihat/ClosedHH GlitterSmurf.wav.
        | Error opening input files: Invalid data found when processing input
        | [13:26:59] ERROR: hook failed (clip or waveform missing)
        | Registered output: hook.hook_clip -> /Users/danielramirez/.sound-archive/work/690084f6c6f1/archive/ClosedHH GlitterSmurf.hook.wav (type: file)
        | [13:26:59] ERROR: Step failed: hook
        | [13:26:59] ERROR: Chain halted: step 'hook' failed
[19/112696] 0d8352a2  [archive]  /Users/danielramirez/Samples/Samples/sampleLibrary/NI/Astral Flutter Library/Samples/Drums/Hihat/OpenHH Fingers 1.wav
^[^[[19/112696] FAIL rc=1 after 1.40s: /Users/danielramirez/Samples/Samples/sampleLibrary/NI/Astral Flutter Library/Samples/Drums/Hihat/OpenHH Fingers 1.wav
        | [in#0 @ 0x8d0c20000] too short LIST tag
        | [in#0 @ 0x8d100c000] Error opening input: Invalid data found when processing input
        | Error opening input file /Users/danielramirez/Samples/Samples/sampleLibrary/NI/Astral Flutter Library/Samples/Drums/Hihat/OpenHH Fingers 1.wav.
        | Error opening input files: Invalid data found when processing input
        | [in#0 @ 0xc56c28000] too short LIST tag
        | [in#0 @ 0xc56c20000] Error opening input: Invalid data found when processing input
        | Error opening input file /Users/danielramirez/Samples/Samples/sampleLibrary/NI/Astral Flutter Library/Samples/Drums/Hihat/OpenHH Fingers 1.wav.
        | Error opening input files: Invalid data found when processing input
        | [13:27:00] ERROR: hook failed (clip or waveform missing)
        | Registered output: hook.hook_clip -> /Users/danielramirez/.sound-archive/work/0d8352a27955/archive/OpenHH Fingers 1.hook.wav (type: file)
        | [13:27:00] ERROR: Step failed: hook
        | [13:27:00] ERROR: Chain halted: step 'hook' failed
[20/112696] bce7f066  [archive]  /Users/danielramirez/Samples/Samples/sampleLibrary/NI/Astral Flutter Library/Samples/Drums/Hihat/ClosedHH Lemon.wav
^CTraceback (most recent call last):
  File "/Users/danielramirez/repos/sound-archive/archive/ingest_batch.py", line 352, in <module>
    if __name__=="__main__": main()
                             ~~~~^^
  File "/Users/danielramirez/repos/sound-archive/archive/ingest_batch.py", line 326, in main
    r=subprocess.run(["bash",engine,"-c",chain,"-o",workdir,p], env=env,
                     capture_output=True, text=True)
  File "/opt/homebrew/Cellar/python@3.14/3.14.6/Frameworks/Python.framework/Versions/3.14/lib/python3.14/subprocess.py", line 557, in run
    stdout, stderr = process.communicate(input, timeout=timeout)
                     ~~~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^
  File "/opt/homebrew/Cellar/python@3.14/3.14.6/Frameworks/Python.framework/Versions/3.14/lib/python3.14/subprocess.py", line 1221, in communicate
    stdout, stderr = self._communicate(input, endtime, timeout)
                     ~~~~~~~~~~~~~~~~~^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/opt/homebrew/Cellar/python@3.14/3.14.6/Frameworks/Python.framework/Versions/3.14/lib/python3.14/subprocess.py", line 2153, in _communicate
    ready = selector.select(timeout)
  File "/opt/homebrew/Cellar/python@3.14/3.14.6/Frameworks/Python.framework/Versions/3.14/lib/python3.14/selectors.py", line 398, in select
    fd_event_list = self._selector.poll(timeout)
KeyboardInterrupt
