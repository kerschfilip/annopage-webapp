FROM python:3.11-slim

# libgl1/libglib2.0-0/etc: doc_api imports cv2 (non-headless) to validate
# uploaded images - these are its usual runtime shared-lib dependencies.
RUN apt-get update && apt-get install -y --no-install-recommends \
        git libgl1 libglib2.0-0 libxcb1 libsm6 libxext6 libxrender1 \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir "anno-page[api] @ git+https://github.com/LIBCAS/AnnoPage.git"

# uvicorn's dev auto-reloader (on by default while PRODUCTION=False) scans
# the current working directory for .py files - without an explicit WORKDIR
# that defaults to "/" and it crashes walking into /proc.
WORKDIR /app

EXPOSE 8000
CMD ["annopage_api"]
