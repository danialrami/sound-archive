# web — sound-archive frontend

The front door to the archive: **the galaxy** — a 3D projection of the vector
space with two toggleable looks, **Cloud** and **Graph**, plus the **Today**
(surface) and **Search** views and an `archive | all` scope switch.

## Live + demo — one file, auto-detecting

`index.html` is self-contained (**no build step, no CDN**) and runs in two modes,
chosen automatically at load:

- **Live** — when a real sound-archive `serve` is reachable (same-origin, or
  `?api=<base>`), confirmed by the `GET /api/stats` `{total, by_scope}` shape.
  All data, waveforms, and audio come from `serve`.
- **Demo** — otherwise, a synthesised archive drives everything so the page is
  alive standalone (e.g. the published preview). Force it with `?demo=1`.

The renderer is a true-3D point-cloud engine in **Canvas2D** (orbit / zoom /
perspective / depth-cue / pick), chosen so *preview == live* and the render is
verifiable in a sandbox. At real 10²–10⁵ scale, swap to Three.js instanced
points + LOD — identical projection math and API contract.

## Endpoints consumed (Ciani's contract, sound-archive #1 + #3)

| Endpoint | Use |
|---|---|
| `GET /api/points?scope=archive\|reference` | the galaxy; both scopes loaded up front so scope-toggle + neighbour clicks resolve locally |
| `GET /api/surface?k=9&session=morning&scope=archive` | Today cards (+ `why` tags) |
| `GET /api/like/<cat>?k=6` | neighbours (full-dim; carries `cluster`,`brightness`,`spectral_centroid_hz`) |
| `GET /api/query?scope=&bright_max=&limit=` | Search (text + duration filtered client-side until CLAP text tower) |
| `GET /api/waveform/<cat>?bins=<W>` | detail waveform — real peaks + `peak_dbfs` + `integrated_lufs`, drawn on-brand |
| `GET /hook/<cat>` · `/stream/<cat>` | audition (hook) + full stream |
| `POST /api/act {catalog,action,session}` | star / use / skip / played → the interaction log |

**3D is navigation only** — retrieval stays full-dim via `/api/like` (neighbours
are *not* the projection-nearest points).

## The looks

- **Cloud** — deep-space: recordings as stars, timbral families as
  constellations, a slow reverent orbit.
- **Graph** — a precise scatter inside a labelled bounding cube
  (DARK↔BRIGHT · LOW↔HIGH · TONAL↔NOISY). Data-forward.

Both currently colour by `cluster`. Per Ciani's note, `cluster` is a projection
artifact (stable until re-project) while `brightness` is the intrinsic axis — a
brightness ramp for Graph's DARK↔BRIGHT axis is a nice future toggle.

## Deep links

`?look=cloud|graph` · `?view=galaxy|today|search` · `?scope=archive|all` ·
`?demo=1` · `?api=<base>` (work when served directly, e.g. from `serve`).

## To verify on live `serve` (for Ciani, during the static mount)

The live path is written to the #3 contract but was authored against synthesised
shapes (no serve in Amacher's sandbox). Worth a smoke-test when you mount `web/`:

1. `GET /api/points?scope=reference` — the frontend loads it to complete the
   in-memory model; if `reference` isn't a valid scope value it's caught and the
   galaxy just runs archive-only. Confirm the scope value.
2. `/api/query` — the UI passes `scope`, `bright_max`, `limit`; text + max-duration
   are filtered client-side (server text→audio lands with the CLAP text tower).
3. `/hook` + `/stream` play via an `<audio>` element (needs the CORS you added).

Built by **Amacher**. Design record: `danialrami/agent-knowledge` →
`docs/product/sound-archive/`.
