# next-steps.md

**Written 2026-07-31 by Ciani, at the end of the CLAP-server session.** Read Part 0 first, then
jump to whichever of Part 3 / Part 4 you want to work on. Everything here is either shipped and
verifiable, or specified precisely enough to start typing.

---

## Part 0 — Where we left off, in one paragraph

`embed_clap` used to load a ~2 GB LAION-CLAP checkpoint **inside `main()`**, so it paid that load
on *every file* — 259,000 model loads for the library. Nothing errored, which is exactly why it ran
for a week unnoticed: a slow-but-correct pipeline is indistinguishable from a fast one from the
outside. That is fixed. There is now a resident-model server (`lufs-audio/sound-archive-embedding`,
service name `serve-embed`) running on carnyx, and a `remote` backend in the workchain component
that needs nothing but `python3` and `ffmpeg` on the library host. Two things remain unbuilt:
**batching** (`/embed_batch`, server side already done and tested) and **prose search**
(`/embed_text`, server side already done and tested). Both are client-side work.

### First thing to run next session

```bash
# 1. is the server proven-correct? (/readyz, NOT /healthz — see Part 2)
curl -s "$EMBED_CLAP_ENDPOINT/readyz" | jq '{ok, device, precision, model_rev, cosine_vs_golden}'

# 2. how far has the ingest actually got?
sqlite3 ~/.sound-archive/archive.db "SELECT COUNT(*) FROM assets;"
sqlite3 ~/.sound-archive/archive.db "SELECT embed_model, COUNT(*) FROM assets GROUP BY embed_model;"

# 3. what did the last run do?
python3 <lufs-workchain>/lib/workchain_runlog.py tail -n 60
```

**Record the ingest throughput (files/s) from the run log before doing anything else.** Part 3
explains why that number decides what to build.

---

## Part 1 — What shipped

### `lufs-audio/sound-archive-embedding` — the server (new repo)

`serve-embed` v0.1.0. Loads the checkpoint once, keeps it resident.

| Endpoint | Auth | Purpose |
| --- | --- | --- |
| `GET /healthz` | no | Liveness + what is loaded. **Does not imply correctness.** |
| `GET /readyz` | no | Fixture forward pass vs committed golden. 200 or 503. **This is the deploy gate.** |
| `GET /models` | no | Resident model descriptor |
| `POST /embed` | yes | One clip → 512-d L2-normed vector |
| `POST /embed_batch` | yes | N clips, one round-trip — **built and tested, no client yet** |
| `POST /embed_text` | yes | Text → same-space vector — **built and tested, no client yet** |

26 contract tests, no torch or checkpoint required. `PLAYBOOK.md` is the deploy procedure for a
human or an agent (carnyx default, klaxon loopback fallback, client wiring, parity, cutover).

### `lufs-audio/lufs-workchain` — PR #27, merged (`0404b6a`)

- `embed_clap` gains `backend: local | remote | auto`. `remote` = stdlib + ffmpeg only.
- Provenance in every record: `served_by`, `endpoint`, `model_rev`, `precision`, `device`.
  `outputs.schema_version` 1.0 → 1.1, additive.
- `embedding_wellformed` post-condition — **recomputes** the L2 norm rather than trusting the
  producer's `l2norm` field.
- `parity.py` — metamorphic local-vs-remote check, cosine ≥ 0.9999.
- `when: {param: [values]}` requirement guards, **fail-closed**.
- **Engine bug fixed:** `record_step_params` ran *after* `preflight_step`, so every guard hit its
  fail-closed path. Params now land first.
- `lib/workchain_runlog.py` — one run log per run, newest 25, autocleaned.
- Discovery drift fixed: `agent.json` / `llms.txt` hand-listed 10 components while the registry
  held 19.

Plus your `71464e6`: `is_audio_file()` rejected `.caf` and six other formats the scanner queues —
**30,117 files from Apple Sound Library alone**. See Part 5, item 1; the underlying duplication is
still there.

### `danialrami/sound-archive` — PR #13, merged

- Per-phase progress with rate and ETA. The hash pass (a full 337 GB read) used to print nothing.
- Per-file line *before* the work, so a stall is attributable to a specific file.
- Run logging: the batch opens **one** log and exports `$WORKCHAIN_RUNLOG` so all N engine
  invocations append to it.
- `--embedder clap-remote`, which warns loudly when `$EMBED_CLAP_ENDPOINT` is unset.
- Any failure now exits 1 — a partial ingest is not a success.

Plus your `2db36ce` / `a4160e5`: the `ingest.sh` herdr wrapper and `docs/02-ingest-runner.md`.

### `lufs-audio/lufs-runner` — PRs #1 and #2, merged

- **#1** — `RUNNER_IMAGE` was `:latest`, which tracks Ubuntu focal → **Python 3.8, EOL April 2025**.
  That is what capped numpy at 1.24.4 and broke CI. Default is now `:ubuntu-noble` (24.04 / 3.12).
  `check` now reports the image's os/python/node and warns on a mutable tag or EOL base.
- **#2** — `lufs-runner.sh update`: reinstalls the script, **rewrites the systemd unit** (prep only
  wrote it when absent, so unit changes could never reach a provisioned node), re-pulls the image,
  restarts slots. **Drains first** — asks the Actions API which of this node's runners are busy and
  waits, because restarting a busy slot kills a live build.

---

## Part 2 — Current state, and the three things that are verified

**carnyx** runs `serve-embed` under systemd, bound to its tailnet IP, fp32, CUDA.
**klaxon** runs the ingest against it via `--embedder clap-remote`; it needs no torch venv for that
path. **The four CI nodes still pin `:latest`** — see Part 5, item 2.

Three *different* correctness claims. None substitutes for another, and it is worth keeping them
straight when something looks wrong:

| Claim | Mechanism | When |
| --- | --- | --- |
| The output is a real vector | `embedding_wellformed` post-condition (recomputes the norm) | every run |
| The server still agrees with **itself** | `/readyz` vs committed golden | every readiness probe |
| The two backends agree with **each other** | `parity.py`, cosine ≥ 0.9999 | before cutover, after any upgrade |

Two decisions that deliberately override the written plan in
`agent-knowledge/docs/infra/audio-ml-stack/04-*`:

1. **fp32, not fp16.** klaxon already holds fp32 vectors; a mixed-precision index degrades
   retrieval in a way no test catches. Precision is stamped into `model_rev`.
2. **No silent fallback.** `backend: remote` fails loudly. `auto` warns. A silent fall back to the
   slow path is precisely how the original bug hid for a week.

---

## Part 3 — NEXT: batching against `/embed_batch`

### Measure before you build

The resident-model fix removed a multi-second cost per file. Once it is gone, the next bottleneck
may not be the embed step at all: **each component's `run.sh` makes ~3 python subprocess calls for
context reads, so a 5-step chain spawns ~15 python processes per file.** At ~30 ms each that is
~450 ms/file — which at 259k files is real, and batching the embed step would not touch it.

So: take the files/s from the run log, then work out which dominates.

- If per-file wall time is mostly **network + embed** → build batching (below).
- If it is mostly **process spawn** → the bigger win is collapsing the context reads (one python
  invocation per step instead of three, or a single context read passed through the environment).

Do not guess. The whole point of the run logs is that this is now measurable.

### The design (if batching wins)

The workchain component model is one-file-per-invocation, so batching cannot live inside
`embed_clap`. It goes in the driver, as a **pre-pass**, with the chain reusing the result:

```
for each chunk of K keepers:
    1. batch_embed.py  — decode K files, POST /embed_batch once, write K sidecars
    2. per-file chain  — embed_clap sees a valid sidecar and skips the network entirely
```

**New file:** `archive/batch_embed.py` (sound-archive).
- Takes a list of `(content_sha256, path)`, decodes each with `ffmpeg -ac 1 -ar 48000 -f f32le`.
- POSTs concatenated f32le PCM with `X-Clip-Lengths: n1,n2,…` (sample counts, not bytes).
- Writes each result to that file's deterministic workdir:
  `~/.sound-archive/work/<sha[:12]>/archive/<input_name>.embedding.json` — same path and same
  record shape `clap_remote.py` writes, including provenance.
- Cap the chunk: K × duration × 48000 × 4 bytes. K=32 at ~10 s ≈ 61 MB. Refuse rather than
  truncate, matching the server's `EMBED_MAX_SECONDS` behaviour.

**New behaviour in `embed_clap`:** a `reuse_existing: true` param (workchain).

> **This is a cache, and caches are how silent staleness gets in.** Reuse must be *verified*, never
> assumed. Before skipping, check that the sidecar (a) parses, (b) passes the same validation
> `clap_remote.py` applies before writing, and (c) its **`model_rev` equals the server's current
> `model_rev`** from `/healthz`. Any mismatch → recompute. This is exactly what `model_rev` was
> added for; without it, reuse would be unsafe and we should not build this at all.

**Tests that must exist before it ships:**
- a batched vector is bit-identical to the same clip embedded alone (already covered server-side);
- reuse **rejects** a sidecar whose `model_rev` differs from the live server;
- reuse **rejects** a corrupt / truncated / non-unit-norm sidecar;
- a chunk boundary does not drop or duplicate a file (run a chunk of K+1 and count records).

**Expected gain:** amortises the per-request round trip and lets the GPU work on real batches.
Meaningful but secondary to the resident-model fix already landed.

---

## Part 4 — NEXT: `/embed_text` as prose search

CLAP is a *joint* audio-text space, so a text query lands in the same 512-d space as the archive's
audio vectors. "bright metallic hit" becomes a real query with **no new model** — just the endpoint
that already exists.

**Where it goes:** `archive/serve.py`, alongside `/api/like` and `/api/query`.

```
GET /api/search?q=bright+metallic+hit&scope=archive&k=12
  -> [ { catalog_number, filename, scope, sim, hook_path, waveform_path }, ... ]
```

Return **the same row shape as `/api/like`** so the frontend can reuse its rendering unchanged.

**Implementation sketch:**
1. POST `{"text": q}` to `$EMBED_CLAP_ENDPOINT/embed_text` with `X-API-Key`.
2. Take the 512-d vector; cosine against stored vectors using the existing full-dim brute-force KNN
   in `archive/query.py` (do **not** use the PCA projection — that is navigation only).
3. Small LRU on the query string → vector. Text embedding is deterministic for a given `model_rev`;
   key the cache on `(q, model_rev)` so a server change invalidates it for free.

**Three failure modes to handle honestly:**

- **Server down** → `503` with a reason. Never an empty result list: "no matches" and "the
  embedder is unreachable" must not look identical to the user.
- **Dimension mismatch** → `409`. The archive may still hold `melstats-v0` vectors at 64-d from
  before the CLAP switch. A 512-d text vector cosine'd against a 64-d row is meaningless. Check
  `SELECT DISTINCT embed_model, dim FROM assets` and refuse clearly, naming both dims.
- **Empty / whitespace query** → `400`, not a random vector.

**Tests:** a text query returns plausible neighbours on a small fixture set; dim mismatch is
refused with 409; server-down is 503 and not an empty list; the cache returns identical vectors and
is invalidated by a `model_rev` change.

**Why this is worth doing early:** it is the highest user-visible value left in the whole thread.
Everything else makes the archive faster to *build*; this makes it usable. It also pairs with the
Amacher "galaxy" frontend Search tab, which already exists in the design brief.

---

## Part 5 — Also queued, roughly in priority order

1. **Kill the audio-extension duplication.** The supported-format list lives in **two** places:
   workchain `lib/constants.sh` `SUPPORTED_AUDIO_EXTENSIONS` and sound-archive
   `archive/ingest_batch.py` `AUDIO`. Your `71464e6` restored parity by hand after `.caf` cost
   30,117 files — but they will drift again the moment either side adds a format. `constants.sh`
   is the natural owner (it is the engine's gate); the scanner should derive from it, with a check
   that fails if they diverge. Same defect class as the `agent.json` component list.
2. **Migrate the four CI nodes off EOL Python 3.8.** Now one command per node:
   ```bash
   cd ~/src/lufs-runner && git pull
   sudo ./lufs-runner.sh update --set-image myoung34/github-runner:ubuntu-noble
   sudo ./lufs-runner.sh check     # must report python 3.12
   ```
   Then `sound-archive-embedding/ci/verify.yml` can go back to `numpy>=1.26` and CI will test on
   the Python we actually ship on. Note 24.04 enforces PEP 668 — workflows need a venv.
3. **Verifier salvage backlog.** Six stacked PRs from 2026-06-11 were closed as unmergeable (main's
   verifier grew 8,847 → 37,486 bytes and renamed `contract` → `post_conditions`; merging them
   would have reverted it). Three contain capability that never landed:
   - **#5** — `relations` (input-vs-output: duration, channels, LUFS, pcm_md5), `matches`,
     `image_valid`, the metamorphic harness. **Biggest gap** — main can assert numeric
     post-conditions but cannot express input-vs-output relations.
   - **#9** — `on_fail: warn|error` with `WORKCHAIN_STRICT=1` promotion, and the `consumed_input`
     snapshot.
   - **#7** — evidence-bound certification: `component_digest` **plus** `evidence_digest`, ed25519,
     custody v1. **This is the certified, name-staked tier — the actual product.**
   Re-land in that order (#5 → #9 → #7); it was the original stack's own order and still right.
   Full detail in the Ciani handoff doc "Standing up the CLAP embed server".
4. **Per-step subprocess overhead** (see Part 3, "Measure before you build").
5. **`/caption` and `/embed_mert`** on the same resident server. The model-holder pattern
   generalises; the audio-ml suite already anticipates both.

---

## Part 6 — Open questions worth a decision next session

- **Is the ingest actually faster, and by how much?** Nothing here matters until that number
  exists. It also settles Part 3.
- **Should `archive-ingest-clap-remote.yaml` become the default chain** for `--embedder clap`,
  with the in-process path renamed to something that signals "reference implementation, not for
  library scale"? The current naming invites someone to pick the slow path by accident.
- **Do we re-embed the fp32/MPS vectors klaxon wrote before the cutover?** They are compatible
  (same model, same precision) so *no* is defensible — but they carry `model_rev: local-*`, so the
  index is honest about being mixed-provenance. Worth deciding deliberately rather than by default.
- **PEP 668 on the runners** — venv everywhere, or `--break-system-packages`? Venv is better
  practice; it just needs doing consistently across every workflow.

---

## Reference

- **Deploy procedure:** `lufs-audio/sound-archive-embedding` → `PLAYBOOK.md`
- **Design record:** `danialrami/agent-knowledge` → `docs/infra/audio-ml-stack/` (page 04 is the
  direct source for the server) and `docs/product/sound-archive/`
- **Ingest runner:** `docs/02-ingest-runner.md` in this repo
- **Run logs:** `~/.workchain/runs`, newest 25.
  `python3 <lufs-workchain>/lib/workchain_runlog.py list|tail|path`
- **Where the code lives:** server → `lufs-audio/sound-archive-embedding`; client backend →
  `lufs-audio/lufs-workchain/components/embed_clap`; driver → `archive/ingest_batch.py` here.
