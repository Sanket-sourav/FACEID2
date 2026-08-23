# Railway builds this Dockerfile, so the exact Python version is guaranteed.
# 3.12 matches the pinned libraries in requirements.txt (onnxruntime 1.18.1
# etc. have no wheels for Python 3.13, which caused the first build failure).
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

# build-essential      : compiles insightface from source
# libgl1, libglib2.0-0 : runtime libraries opencv-python needs on slim images
RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential \
        libgl1 \
        libglib2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Dependencies first so this layer is cached while only code changes
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000
CMD ["python", "main.py", "serve"]