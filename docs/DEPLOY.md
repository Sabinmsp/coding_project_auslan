# Deploying the 2D demo

Static files and client-side JavaScript only: no server logic, database or
API. Any static host works.

## 1. Choose a build

| build | command | size (measured 2026-10-27) | fits |
|---|---|---|---|
| full library | `python3 scripts/build_dist.py` | 1,034 MB, 6,499 files, largest file 8.5 MB | Cloudflare Pages (20,000 files, 25 MiB/file); Netlify; **not** Vercel (CLI upload cap 100 MB Hobby, 1 GB Pro) |
| full library, small videos | `python3 scripts/build_dist.py --small-videos` | ~0.55 GB (estimate) | Cloudflare Pages, Netlify, Vercel Pro |
| **web demo** | `python3 scripts/build_dist.py --signs-from scripts/web_demo.txt --small-videos` | **88 MB, 858 files** | **everything, including Vercel Hobby (100 MB, little headroom)** |

The web demo ships the 390 signs that the app's own planner needs for
`scripts/web_demo.txt` (the demo sentences, the sample handbook's text as
written and as simplified, and ~300 everyday words),
plus every alternative their menus offer and all quick picks. Every other
sign stays in the manifest without a clip; the page fingerspells it and
says *"not included in this web demo"*, never that it doesn't exist. Add
lines to `scripts/web_demo.txt` to include more.

`--small-videos` re-encodes every reference video (library, letters,
phrases) at 240 px with ffmpeg. The avatar is unaffected; only the source
video panel is lower resolution.

`dist/` mirrors the URLs the page uses: `frontend/` at the root, and under
`assets/` only what the page can request. Catalog, extraction log and QA
sheets live in `datasets/processed/` and never ship. Host limits change:
check them before deploying.

### The AI summary (optional)

PDF reading and the offline summary run entirely in the browser and need no
server. The plain-English rewrite by Claude is a small serverless function:

| | |
|---|---|
| route | `POST /api/summarize` (`dist/api/summarize.py`, built from `backend/api_summarize.py` + `backend/summarize_llm.py`) |
| Vercel | runs it as a Python function; `dist/requirements.txt` installs `anthropic` |
| env var `ANTHROPIC_API_KEY` | required for AI summaries; set it in the Vercel project settings, never in the page |
| env var `ANTHROPIC_MODEL` | optional; default `claude-opus-5-5` |
| without them | the route answers 503 and the page says so and keeps its offline summary |
| other static hosts | the route doesn't exist; same fallback |

What is sent: only the ~60 excerpts the offline summariser picked (each
≤ 600 characters, with its page), never the whole PDF. A user uploading a
private document should know that excerpts go to the API when the AI switch
is on.

## 2. Test the bundle locally

```sh
python3 backend/serve.py 8005 dist
open http://localhost:8005
python3 tests/browser/test_controls.py 8005     # and test_behaviour.py
```

Use `backend/serve.py`, not `python3 -m http.server`: the built-in server
ignores HTTP Range requests, which breaks seeking in the reference video.
Real hosts support ranges. (`test_robustness.py` assumes the full library;
against the web demo its unreliable-sign checks don't apply.)

## 3. Deploy (only with the project owner's approval)

```sh
npx vercel deploy dist --prod                # Vercel (web demo build)
npx wrangler pages deploy dist               # Cloudflare Pages (any build)
npx netlify-cli deploy --dir=dist --prod     # Netlify
```

The build writes `vercel.json`, `_headers` and `netlify.toml`: MP4 and JSON
MIME types, and no caching of the manifest, so a redeploy with more signs is
picked up on reload. Nothing has been deployed so far.

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
