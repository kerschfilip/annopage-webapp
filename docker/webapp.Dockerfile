FROM python:3.11-slim

# libgl1/libglib2.0-0/etc: doc_api.adapter (used by annopage_client) imports
# cv2 (non-headless) - these are its usual runtime shared-lib dependencies.
RUN apt-get update && apt-get install -y --no-install-recommends \
        git libgl1 libglib2.0-0 libxcb1 libsm6 libxext6 libxrender1 \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir \
    "fastapi>=0.100.0" \
    "uvicorn[standard]>=0.23.0" \
    "jinja2>=3.1.0" \
    "lxml>=4.9.0" \
    "requests>=2.31.0" \
    "anno-page[client] @ git+https://github.com/LIBCAS/AnnoPage.git"

WORKDIR /app
COPY . .

EXPOSE 8000
CMD ["python", "-m", "uvicorn", "server:app", "--host", "0.0.0.0", "--port", "8000"]
