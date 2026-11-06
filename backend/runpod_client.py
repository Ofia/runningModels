import base64
import os
import time

import requests

RUNPOD_API_KEY = os.environ["RUNPOD_API_KEY"]
RUNPOD_ENDPOINT_ID = os.environ["RUNPOD_ENDPOINT_ID"]
BASE_URL = f"https://api.runpod.ai/v2/{RUNPOD_ENDPOINT_ID}"
HEADERS = {"Authorization": f"Bearer {RUNPOD_API_KEY}"}

# ponytail: plain poll loop, cold starts can take minutes so runsync's own
# timeout isn't long enough — upgrade to webhooks if this ever feels slow.
POLL_INTERVAL_SECONDS = 2
JOB_TIMEOUT_SECONDS = 300


def generate_image(prompt: str, reference_paths: list[str] | None = None) -> bytes:
    payload = {"input": {"prompt": prompt}}
    if reference_paths:
        payload["input"]["reference_images"] = [
            base64.b64encode(open(p, "rb").read()).decode("utf-8")
            for p in reference_paths
        ]

    job = requests.post(f"{BASE_URL}/run", headers=HEADERS, json=payload, timeout=30).json()
    job_id = job["id"]

    deadline = time.monotonic() + JOB_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        status = requests.get(f"{BASE_URL}/status/{job_id}", headers=HEADERS, timeout=30).json()
        if status["status"] == "COMPLETED":
            return base64.b64decode(status["output"]["image_base64"])
        if status["status"] in ("FAILED", "CANCELLED", "TIMED_OUT"):
            raise RuntimeError(f"RunPod job {status['status']}: {status.get('error')}")
        time.sleep(POLL_INTERVAL_SECONDS)

    raise TimeoutError(f"RunPod job did not finish within {JOB_TIMEOUT_SECONDS}s")
