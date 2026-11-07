import base64
import io

import runpod
import torch
from diffusers import Flux2KleinPipeline
from PIL import Image

pipe = Flux2KleinPipeline.from_pretrained(
    "black-forest-labs/FLUX.2-klein-4B", torch_dtype=torch.bfloat16
)
pipe.enable_model_cpu_offload()


def _decode(b64_png: str) -> Image.Image:
    return Image.open(io.BytesIO(base64.b64decode(b64_png))).convert("RGB")


def _encode(img: Image.Image) -> str:
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("utf-8")


def handler(job):
    data = job["input"]
    kwargs = dict(
        prompt=data["prompt"],
        width=data.get("width", 1024),
        height=data.get("height", 1024),
        num_inference_steps=data.get("steps", 4),
    )

    refs = data.get("reference_images")
    if refs:
        kwargs["image"] = [_decode(r) for r in refs]

    result = pipe(**kwargs).images[0]
    return {"image_base64": _encode(result)}


runpod.serverless.start({"handler": handler})
