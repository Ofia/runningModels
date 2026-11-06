# RunningModel — Architecture

A browser UI for creating visual "identities" (a character/person/object) once
and generating many new scenes of that same identity, using FLUX.2 Klein 4B.

## Three stations

```
Browser  <-->  Local backend (FastAPI)  <-->  RunPod Serverless endpoint
 (UI)           (file management +             (FLUX.2 Klein 4B,
                 RunPod relay, no AI)            the only GPU-heavy piece)
```

1. **Browser** (`frontend/`) — plain HTML/CSS/JS, no framework, no build step.
   Left sidebar lists identities + "New Model" button. Main panel shows the
   selected identity's reference image, a gallery of every scene generated
   for it, and a prompt bar.

2. **Local backend** (`backend/`) — FastAPI. Manages identity folders on
   disk, relays generation requests to RunPod, serves images back to the
   browser as static files. Runs no AI itself — just file I/O and HTTP
   relay.

3. **RunPod Serverless worker** (`worker/`) — the only piece touching a GPU.
   Loads `Flux2KleinPipeline` once at container startup and keeps it warm
   across requests. Receives a prompt (+ optional reference image) over
   RunPod's job API, returns a generated PNG.

## Why it has to be split this way

The local machine's GPU (2GB VRAM) can't run a model that needs ~13GB, so
generation must happen on a rented GPU. Everything that *doesn't* need a GPU
(identity bookkeeping, the UI, serving images) stays local and free.

## Identity consistency

FLUX.2 Klein natively supports **multi-reference editing**: pass one or more
reference images alongside a prompt, and the model keeps the visual identity
from those references while applying the new scene/prompt. This is the whole
mechanism — no LoRA, no fine-tuning per identity.

- Creating an identity = one **text-to-image** call (no reference yet) ->
  saved as `reference.png`.
- Generating a new scene = one **image-edit** call with `image=[reference.png]`
  + the new prompt -> saved into `generations/`.

## Data layout

```
data/models/<slug>/
  meta.json            # {name, prompt, created_at}
  reference.png
  generations/
    <timestamp>.png
```

Plain files on disk — no database. `data/` is gitignored; nothing generated
here ever leaves the local machine except the RunPod API calls needed to
produce each image.

## Dependencies

**Backend** (`backend/requirements.txt`)
- `fastapi`, `uvicorn[standard]` — HTTP server
- `python-dotenv` — loads `RUNPOD_API_KEY` / `RUNPOD_ENDPOINT_ID` from `.env`
- `requests` — calls RunPod's job API
- `pip-system-certs` — makes `requests` trust the OS certificate store
  (needed on this machine; see "Known gotchas" below)

**Worker** (`worker/requirements.txt`, inside the RunPod container only)
- `torch>=2.5.0` — the base image ships 2.4.0, which lacks the
  `torch.accelerator` API `diffusers` needs
- `diffusers>=0.32.0` — provides `Flux2KleinPipeline`
- `transformers`, `accelerate`, `sentencepiece`, `pillow` — model/image
  plumbing
- `runpod` — the serverless worker SDK (`runpod.serverless.start(...)`)
- `torchvision` and `torchaudio` are explicitly **uninstalled** in the
  Dockerfile — see gotchas.

## Deployment model

- **Where**: RunPod Serverless, deployed via GitHub auto-build (pushes to
  `Ofia/runningModels` → RunPod builds `worker/Dockerfile` automatically).
- **GPU**: `ADA_24` pool (RTX 4090, 24GB) — $1.34/hr, billed per-millisecond,
  only while a job is actually running.
- **Scaling**: `workers.min = 0` (scales to zero when idle — no cost while
  not generating), `workers.max = 1` (single user, no need for concurrency).
- **Routing**: `QUEUE` type — the backend submits via `/run` and polls
  `/status/{id}` (see `backend/runpod_client.py`), not `/runsync`, because
  cold starts (model load) can take minutes and `runsync`'s own timeout
  isn't long enough.
- **Model caching**: using RunPod's built-in "Cached model" host-level
  caching for the HF repo, not a Network Volume — avoids both the
  per-GB-month storage cost and pinning the endpoint to a single data
  center (which would shrink the GPU pool down to its availability there).
- **No HF token configured** — the model is public, so it works
  unauthenticated, just with slower/rate-limited downloads. Add one in the
  RunPod console if cold starts become a problem.

## Known gotchas (worth knowing before touching `worker/` again)

- **RunPod's GitHub-build Docker context is the repo root**, even when the
  "Dockerfile path" field points into a subdirectory. `COPY` paths in
  `worker/Dockerfile` must be written relative to the repo root (e.g.
  `COPY worker/handler.py .`), not relative to the Dockerfile's own folder.
- **The job API lives at `api.runpod.ai`** — not `api.runpod.io`, which is
  the console/account API. Easy to mix up; `backend/runpod_client.py` is
  pinned to the right one.
- **The base image's `torchvision`/`torchaudio` are compiled against its
  bundled torch build.** Force-upgrading `torch` via pip (needed for
  `diffusers`) breaks both at import time with an ABI mismatch. Fix: just
  uninstall them — the handler doesn't use either.
- **FLUX.2 has no safety_checker/moderation step anywhere in this stack.**
  Prompts that push toward content the base model's training data excluded
  don't error — the multi-reference edit mode just tends to return
  something very close to the unmodified reference image instead.
