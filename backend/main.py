import json
import re
import time
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI, HTTPException  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
from pydantic import BaseModel  # noqa: E402

from runpod_client import generate_image  # noqa: E402  (reads env vars at import time)

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data" / "models"
DATA_DIR.mkdir(parents=True, exist_ok=True)

app = FastAPI()
app.mount("/data", StaticFiles(directory=ROOT_DIR / "data"), name="data")


class CreateModelRequest(BaseModel):
    name: str
    prompt: str


class GenerateRequest(BaseModel):
    prompt: str


def slugify(name: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    if not slug:
        raise HTTPException(400, "Invalid name")
    return slug


@app.get("/models")
def list_models():
    models = []
    for model_dir in sorted(DATA_DIR.iterdir()):
        meta_path = model_dir / "meta.json"
        if meta_path.exists():
            models.append(json.loads(meta_path.read_text()))
    return models


@app.post("/models")
def create_model(req: CreateModelRequest):
    slug = slugify(req.name)
    model_dir = DATA_DIR / slug
    if model_dir.exists():
        raise HTTPException(409, f"Model '{slug}' already exists")

    image_bytes = generate_image(req.prompt)

    model_dir.mkdir(parents=True)
    (model_dir / "generations").mkdir()
    (model_dir / "reference.png").write_bytes(image_bytes)

    meta = {"slug": slug, "name": req.name, "prompt": req.prompt, "created_at": time.time()}
    (model_dir / "meta.json").write_text(json.dumps(meta))
    return meta


@app.get("/models/{slug}")
def get_model(slug: str):
    model_dir = DATA_DIR / slug
    meta_path = model_dir / "meta.json"
    if not meta_path.exists():
        raise HTTPException(404, "Model not found")

    meta = json.loads(meta_path.read_text())
    generations = sorted(p.name for p in (model_dir / "generations").glob("*.png"))
    return {**meta, "generations": generations}


@app.post("/models/{slug}/generate")
def generate(slug: str, req: GenerateRequest):
    model_dir = DATA_DIR / slug
    reference_path = model_dir / "reference.png"
    if not reference_path.exists():
        raise HTTPException(404, "Model not found")

    image_bytes = generate_image(req.prompt, reference_paths=[str(reference_path)])
    filename = f"{int(time.time() * 1000)}.png"
    (model_dir / "generations" / filename).write_bytes(image_bytes)
    return {"filename": filename}


# Mounted last so the API routes above take priority over the SPA catch-all.
app.mount("/", StaticFiles(directory=ROOT_DIR / "frontend", html=True), name="frontend")
