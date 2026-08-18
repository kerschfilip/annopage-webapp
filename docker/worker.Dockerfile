FROM python:3.11-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
        git build-essential libgl1 libglib2.0-0 libxcb1 libsm6 libxext6 libxrender1 \
    && rm -rf /var/lib/apt/lists/*

# CPU-only torch+torchvision from the same wheel index, installed together
# so their ABI versions match - and so the "tool" extra below finds both
# already satisfied and doesn't pull mismatched/CUDA wheels (there's no GPU
# passthrough in Docker Desktop anyway).
RUN pip install --no-cache-dir torch torchvision --index-url https://download.pytorch.org/whl/cpu

RUN pip install --no-cache-dir "anno-page[worker,tool] @ git+https://github.com/LIBCAS/AnnoPage.git"

CMD ["annopage_worker", "--device", "cpu"]
