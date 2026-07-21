# web — sound-archive frontend (design treatment)

The front door to the archive: **the galaxy** — a 3D projection of the vector
space with two toggleable looks, **Cloud** and **Graph**, plus the **Today**
(surface) and **Search** views and an `archive | all` scope switch.

**Status: design treatment.** It runs on *synthesised data against the real
`serve` API shapes* so it is alive without klaxon — reviewable and iterable now;
wiring it to the live `serve` is the next step. Daniel picked Cloud + Graph from
the three-direction treatment; this is that final.

## What's here

- `index.html` — self-contained, **no build step, no CDN**. A true-3D
  point-cloud engine in **Canvas2D** (orbit / zoom / perspective / depth-cue /
  pick), chosen deliberately so *preview == live* and the render is verifiable
  in a sandbox. Waveform preview + hook/stream playback are **synthesised
  in-browser** (per-cluster DSP archetypes — drones hum, piano arpeggiates,
  metallic rings, air hisses) so the detail panel is testable today; on klaxon
  these map to `/hook`, `/stream`, `/waveform`.

## The looks

- **Cloud** — deep-space: recordings as stars, timbral families as
  constellations, a slow reverent orbit.
- **Graph** — a precise scatter inside a labelled bounding cube
  (DARK↔BRIGHT · LOW↔HIGH · TONAL↔NOISY). Data-forward; retrieval stays honest
  (neighbours from `/api/like`, not projection-nearest).

## Views (shared)

- **Galaxy** — the hero, from `GET /api/points`.
- **Today** — `GET /api/surface?k=9`, each card tagged with *why* it surfaced
  (temporal / relevance:like-starred / novelty:cold / wildcard).
- **Search** — `GET /api/query` filters + a text box (real text→audio lands with
  CLAP's text tower on klaxon).
- **Interaction log** — a floating, draggable, minimise/close panel; every
  star / use / skip / played posts to `POST /api/act` and appends here (the
  flywheel's fuel).

## Deep links

`?look=cloud|graph` · `?view=galaxy|today|search` · `?scope=archive|all`
(work when the file is served directly, e.g. from `serve`).

## To wire to live `serve` (asks for the engine side)

1. **Peaks-JSON waveform** — e.g. `GET /api/waveform/<cat>?bins=800 →
   {peaks:[[min,max]…], rms:[…], dur, peak_dbfs, integrated_lufs}` so the
   waveform is drawn on-brand / cluster-tinted / resize-crisp (the lufs-recorder
   scope treatment) instead of embedding a fixed-palette server PNG. Keep the
   PNG as a cheap thumbnail fallback.
2. Add `cluster` (ideally `brightness`) to `/api/like` rows so neighbour dots
   colour correctly without a client-side join back to `/api/points`.
3. Confirm CORS on `/hook` + `/stream` if the frontend is ever served
   cross-origin (non-blocking on the tailnet / same-origin).

Then: replace the synthesised `API` / `buildArchive` block in `index.html` with
`fetch()` calls to `serve` — the data shapes already match, so it's a swap, not
a rewrite. At the real 10²–10⁵ scale, move the renderer to Three.js instanced
points + LOD (identical projection math and API contract).

---

Built by **Amacher**. Design record: `danialrami/agent-knowledge` →
`docs/product/sound-archive/`.
