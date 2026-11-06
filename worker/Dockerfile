FROM runpod/pytorch:2.4.0-py3.11-cuda12.4.1-devel-ubuntu22.04

WORKDIR /app

COPY worker/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    && pip uninstall -y torchvision

COPY worker/handler.py .

CMD ["python3", "-u", "handler.py"]
