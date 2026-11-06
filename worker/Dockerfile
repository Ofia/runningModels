FROM runpod/pytorch:2.0.0-cu1290-torch280-ubuntu2404

WORKDIR /app

COPY worker/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY worker/handler.py .

CMD ["python3", "-u", "handler.py"]
