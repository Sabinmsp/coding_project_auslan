# Deploying the 2D demo

Static files and client-side JavaScript only: no server logic, database or
API. Any static host works.

## 1. Build the bundle

```sh
python3 scripts/build_dist.py                 # full-resolution reference videos
python3 scripts/build_dist.py --small-videos  # reference videos re-encoded at 240px
```

`dist/` mirrors the URLs the page uses: `frontend/` at the root, and under
`assets/` only what the page can request -- `signs.json`, `letters.json`,
the letter and phrase clips they reference, and from `assets/signs/` the
manifest, face topology and the motion + video of every sign the manifest
marks available. Catalog, extraction log and QA sheets live in
`datasets/processed/` and never ship.

Size grows with the library. Measured at 225 extracted signs:

| | |
|---|---|
| letters + phrases | 20 MB motion, 25 MB video |
| library, per sign | ~130 KB motion + ~150 KB video |
| bundle at 225 signs | 114 MB, 518 files |
| **all 3,215 signs** | **~1.0 GB** (~0.5 GB with `--small-videos`, which cuts video 84%) |

Check your host's site-size and file-count limits before deploying the full
library. Motion JSON compresses well and hosts gzip it in transit, so what a
viewer downloads is much smaller than what is stored.

## 2. Test the bundle locally

```sh
python3 backend/serve.py 8002 dist
open http://localhost:8002
```

Use `backend/serve.py`, not `python3 -m http.server`: the built-in server ignores
HTTP Range requests, which breaks seeking in the reference video. Real
hosts support ranges.

## 3. Deploy

**Netlify** (drag and drop): app.netlify.com/drop, drop the `dist` folder.

```sh
npx netlify-cli deploy --dir=dist --prod     # Netlify CLI
npx vercel --prod dist                       # Vercel
npx wrangler pages deploy dist               # Cloudflare Pages
```

**GitHub Pages:** push the contents of `dist/` to a `gh-pages` branch.

`_headers` and `netlify.toml` set MIME types for `.mp4`/`.json` and stop the
manifest being cached, so a redeploy with more signs is picked up on reload.

## What a viewer downloads

Startup: ~100 KB gzipped (`index.html`, `src/`, `assets/signs.json`,
`assets/fingerspelling/letters.json`, and the 3,215-sign manifest, which is
~75 KB of that). After
that, only the signs a sentence uses: ~130 KB motion + video per sign,
cached for the session. Links work directly:
`https://your-site/?text=I go home tomorrow` or
`https://your-site/?gloss=hello fs:SABIN`.

## What is NOT deployed

- **Extraction.** Python + MediaPipe + ffmpeg, ~25 s of CPU per clip. When
  a sign exists in the corpus but isn't extracted, the page fingerspells
  the word and names the command (`scripts/build_library.py --only <id>`). Making
  that self-service needs a backend with a job queue -- a separate build.
- **`backend/llm_plan.py`.** It needs an API key, which must never be shipped to a
  browser. Run it locally; it prints a `?gloss=` link that plays the
  validated plan on the deployed site.

## Licensing

13 fingerspelling letters come from Auslan Signbank under CC BY-NC-ND 4.0:
non-commercial use, with attribution. Confirm the licence of the `rgb/`
corpus before making a public deployment.
