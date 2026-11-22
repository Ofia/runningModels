# RunningModel

Create a visual **identity** once — a character, a person, an object — then generate unlimited
new scenes of that same identity, from a browser.

Built on **FLUX.2 Klein 4B**, running on a rented GPU via RunPod Serverless.

```
Browser  <-->  Local backend (FastAPI)  <-->  RunPod Serverless worker
 (UI)          file management + relay         FLUX.2 Klein 4B
               no AI, no GPU                   the only GPU-heavy piece
```

## The problem it solves

Keeping a character visually consistent across many generated images normally means training a
LoRA per character — slow, fiddly, and expensive. FLUX.2 Klein supports **multi-reference
editing** natively: pass a reference image alongside a new prompt and the model preserves the
identity while applying the new scene.

So there's no fine-tuning here at all:

- **Creating an identity** → one text-to-image call → saved as `reference.png`
- **Generating a scene** → one image-edit call with `image=[reference.png]` + the new prompt

## Why it's split across three machines

A 2GB local GPU can't run a model that needs ~13GB. So generation happens on a rented GPU, and
everything that *doesn't* need one — the UI, identity bookkeeping, serving images — stays local
and free.

The worker scales to zero when idle (`workers.min = 0`), so a 4090 at $1.34/hr only bills
per-millisecond while a job is actually running.

## Running it

```bash
cp .env.example .env     # add RUNPOD_API_KEY and RUNPOD_ENDPOINT_ID
pip install -r backend/requirements.txt
uvicorn backend.main:app --reload
```

Open the browser UI, click **New Model**, describe an identity, then prompt it into new scenes.

Images live as plain files on disk — no database:

```
data/models/<slug>/
  meta.json          {name, prompt, created_at}
  reference.png
  generations/<timestamp>.png
```

## Stack

- **Frontend** — plain HTML/CSS/JS. No framework, no build step.
- **Backend** — FastAPI. File I/O and an HTTP relay to RunPod. Runs no AI.
- **Worker** — RunPod Serverless. Loads `Flux2KleinPipeline` once at container start and keeps
  it warm. Deployed by GitHub auto-build on push.
- **Queue routing** — submits via `/run` and polls `/status/{id}` rather than `/runsync`, because
  a cold start can take minutes and `runsync` times out first.

## Gotchas worth knowing

Documented in full in [`docs/architecture.md`](docs/architecture.md). The ones that cost the most time:

| Problem | Cause | Fix |
|---|---|---|
| `COPY` fails in the RunPod build | RunPod's GitHub-build Docker context is the **repo root**, even when the Dockerfile path points into a subfolder | Write `COPY` paths relative to the repo root |
| Job API 404s | `api.runpod.io` is the console/account API — the job API is `api.runpod.ai` | Pinned correctly in `backend/runpod_client.py` |
| `torchvision` ABI crash on import | The base image ships torch 2.4.0; `diffusers` needs `torch.accelerator` from 2.5+, and force-upgrading torch breaks the bundled `torchvision`/`torchaudio` | Uninstall both — the handler uses neither |

## Notes

- Model caching uses RunPod's host-level cached-model feature rather than a Network Volume —
  avoids per-GB-month storage cost and avoids pinning the endpoint to one data center, which
  would shrink the available GPU pool.
- FLUX.2 has no safety checker in this stack. Prompts pushing outside the base model's training
  distribution don't error; multi-reference edit mode just returns something close to the
  unmodified reference.
