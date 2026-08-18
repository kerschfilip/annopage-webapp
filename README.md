# AnnoPage local runner

A small local web UI that replaces hand-typing `annopage_client` commands
and browsing output folders by hand.

It never imports `doc_api`/`doc_client` or talks HTTP to AnnoPageAPI itself,
and it never modifies anything inside the `AnnoPage` repo. Every action
shells out to the already-installed `annopage_client` executable, the same
way `AnnoPageWorker.process_job` in `AnnoPage/api/worker.py` shells out to
`annopage`. Nothing here ever calls the production server
(`annopage.orbis.lib.cas.cz`) — it only talks to whatever target you save in
Settings, meant to be a locally-run `annopage_api` + `annopage_worker`.

See `AGENTS.md` for architecture notes and a list of non-obvious bugs
already debugged in this setup — read that before changing anything.

## Prerequisites

Clone [AnnoPage](https://github.com/LIBCAS/AnnoPage) as a **sibling
directory** to this repo:

```
some-folder/
  AnnoPage/            git clone https://github.com/LIBCAS/AnnoPage.git
  annopage-webapp/      this repo
```

`scripts/register_engine.py` reads model weights from
`AnnoPage/resources/models/` (LFS-tracked — make sure LFS content is pulled)
and the default prompt file from `AnnoPage/resources/image_captioning_prompt.json`.
Nothing else here needs a local AnnoPage checkout — the Docker images
install the `anno-page` package straight from GitHub.

## Run it with Docker (recommended)

`docker compose up -d` brings up the whole local stack: Postgres, the
AnnoPage API, an AnnoPage worker (CPU-only — Docker Desktop has no GPU
passthrough), and this webapp. Everything lives in its own container/image
you can throw away with `docker compose down -v`.

```bash
docker compose up -d --build
```

First build pulls/builds ~4 images; the worker image (torch, ultralytics,
transformers, pero-ocr) is the heavy one (a few GB) and takes a few minutes.
Make sure you have several GB of free disk before building.

Open the webapp at **http://localhost:8080**. The API is also published at
http://localhost:8000 if you want to poke it directly (e.g. its `/docs`).

### One-time: register an engine

A fresh database has **zero engines**, so the worker has nothing to run
until one is registered. Run this once (from the host, not inside a
container — it just needs network access to the published API port):

```bash
python3 scripts/register_engine.py --api-url http://localhost:8000
```

This builds a `config.ini` + model-weights ZIP from `AnnoPage/resources/models/`
(non-textual element detection + caption-to-region linking, no LLM key
needed) and registers it as the default engine via DocAPI's admin endpoints,
using the dev admin key that `annopage_api` auto-provisions when
`PRODUCTION=False` (the default). Safe to re-run — it's idempotent.

### Optional: a second engine with LLM captioning and/or CLIP embeddings

The default engine deliberately has no captioning/embedding steps, so an LLM
API key pasted into a "Captioning profil" in the webapp does nothing on its
own — the engine's own `config.ini` needs an `OPENAI_COMPLETIONS_IMAGE_CAPTIONING`
step for that override to have anything to act on. To add one as a second,
non-default engine (so it doesn't change what jobs get by default):

```bash
python3 scripts/register_engine.py --api-url http://localhost:8000 \
  --name local-cpu-captioning --version v1 \
  --with-captioning --with-embeddings --no-default
```

Then pick `local-cpu-captioning` explicitly from the **Engine** dropdown per
job, and put the real key in a Captioning profile (Settings) rather than
baking it into the engine.

Two non-obvious things this ran into (see the docstring in
`scripts/register_engine.py` for the full detail):

- **LLM API aliases** (`"api": "OpenRouter"`, as used in production-style
  captioning profiles) don't resolve inside `annopage` in this setup — the
  webapp now resolves known aliases (openai/openrouter/cerit/e-infra) to a
  full URL itself before writing a job's `--image-captioning-settings` file
  (`llm_aliases.py`), so pasting a profile copied from production just works.
- **CLIP embeddings default to `float32`, not `bfloat16`** — PyTorch's CPU
  bfloat16 kernels are often unoptimized and can turn a couple of tiny test
  regions into a 40-minute "job that looks hung." Override
  `--embedding-precision` only if you know what you're doing.

Every registration is also recorded locally in `data/engines.json` (DocAPI
has no endpoint to read an engine's `config.ini` back, even for admins) —
visible under **Settings → Registrované enginy**.

### One-time: add a target

`data/` is gitignored (it holds API keys), so a fresh checkout starts with
none. Add one from **Settings**: label anything, API URL
`http://annopage-api:8000` (the in-network hostname — not `localhost`, since
the webapp itself runs inside the Docker network), API key
`annopage.testuserkid.testuserkey` (the auto-provisioned dev user key).

### Input folders

`docker-compose.yml` bind-mounts this repo's own `input-data/` (read-only,
gitignored except for a `.gitkeep` placeholder) into the webapp container at
`/data`. Drop input folders in there on the host, e.g.
`input-data/my-book/input/{images,alto_xmls,metadata.json}`, then in the
**New job** form use the *container-side* path:

```
/data/my-book/input
```

not the path as it appears on your Mac — or just pick it from the
auto-discovered dropdown instead of typing it. Edit the volume mapping in
`docker-compose.yml` if you'd rather point at input data living elsewhere.

The worker runs with `--logging-level=DEBUG` on purpose: `AnnoPageWorker.process_job`
(`AnnoPage/api/worker.py`) only logs the `annopage` subprocess's stdout/stderr
when a job *succeeds* if the level is DEBUG - at INFO you get no visibility
into what actually ran, even when a job "succeeds" with empty output. The
webapp's own job log (Job detail page) only shows `annopage_client`'s polling
status, not the pipeline's own log - for that, use the command below.

CLIP embeddings cache under `/data/hf-cache` inside the worker container
(`HF_HOME`, a Docker volume) so the model isn't re-downloaded on every
restart - but `docker compose down -v` wipes it along with everything else.

### Useful commands

```bash
docker compose logs -f annopage-worker   # watch job processing (DEBUG-level)
docker compose ps                         # container status
docker compose down                       # stop, keep data (DB, jobs, engines)
docker compose down -v                    # stop and wipe everything - clean slate
```

## Run it without Docker

Requires `annopage_client` to already be installed and on `PATH` (it's
installed together with the `AnnoPage` package, extra `client`).

```bash
pip install -e .
uvicorn server:app --reload
```

Then open http://127.0.0.1:8000. You'll still need a running `annopage_api`
(+ `annopage_worker` if you want jobs to actually complete, + a registered
engine) to point a target at — see `AnnoPage/api/README.md`.

## Usage

1. **Settings** — add a target (a running `annopage_api` + `annopage_worker`
   instance: label, API URL, API key). Optionally add a captioning profile
   (paste the contents of an `IMAGE_CAPTIONING_SETTINGS.json`-shaped file).
   Registered engines (via `register_engine.py`) are also listed here, each
   with its full `config.ini`.
2. **New job** — either pick a suggested input folder (auto-discovered by
   scanning the bind-mounted `/data` for directories containing `images/`)
   or type a path manually, pick a target/engine (its description shows once
   selected)/outputs, submit.
3. **Job detail** — live status/progress bar and a live-tailed log while it
   runs, then a download-zip button and the on-disk output path once done.
   No inline image gallery by design — output can be hundreds of pages.
4. **Historie** — list of past runs.

## Data

All local state (targets, captioning profiles, job records, per-job logs
and downloaded zips) lives under `data/`, which is gitignored (and, in the
Docker setup, bind-mounted so it survives `docker compose down`).
