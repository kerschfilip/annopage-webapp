# AGENTS.md — handoff notes for agents working on this repo

Read this before making changes. It captures hard constraints the user set
early on, and real bugs already debugged so you don't re-discover them.

## What this is

A local web UI that replaces hand-typing `annopage_client` commands and
browsing output folders by hand, for testing the AnnoPage ML pipeline
against a **locally-run** AnnoPage stack (Postgres + AnnoPage API + AnnoPage
worker), not the production server.

This repo is meant to stand alone (its own git repo, standalone or nested
anywhere) - it needs [AnnoPage](https://github.com/LIBCAS/AnnoPage) cloned as
a **sibling directory** (see `README.md`'s Prerequisites) so
`register_engine.py` can read model weights from it, but nothing here
imports AnnoPage's Python code or needs to live inside its git repo.

User-facing usage: `README.md`. This file is the consolidated design/debug
history - there is no separate planning doc elsewhere, keep it that way.

## Hard constraints (do not violate these)

1. **Never modify anything inside `../AnnoPage`.** It's a fast-moving
   dependency the user periodically `git pull`s. Dockerfiles `pip install`
   from git, exactly like the host already does — never `COPY` or edit its
   files.
2. **`server.py`/`job_runner.py`/`engines.py` never import `doc_api`/`doc_client`
   or talk HTTP to AnnoPageAPI directly.** Every job-submission action shells
   out to the already-installed `annopage_client` executable — the same
   pattern `AnnoPageWorker.process_job` (`AnnoPage/api/worker.py`) uses to
   shell out to `annopage`. This keeps traffic indistinguishable from a
   manual CLI run.
3. **`scripts/register_engine.py` is the one deliberate exception** — it
   talks to DocAPI's admin endpoints directly via plain `requests`. That's
   fine: it's an operator bootstrap script run once by hand, never triggered
   by a user submitting a job through the web UI.
4. **Nothing here ever calls `https://annopage.orbis.lib.cas.cz`.** Every
   action targets whatever "target" the user saved in Settings — meant to be
   a locally-run instance. Never add code that could reach the real server.

## Architecture

```
server.py              FastAPI routes (pages + JSON API)
job_runner.py           builds annopage_client argv, runs it as a subprocess,
                         tails stdout to update job state; resolves LLM API
                         aliases before writing captioning settings
store.py                 JSON-file persistence: targets, captioning profiles,
                          jobs, local engine registry (data/*.json)
input_inspector.py        validates an input folder + scans /data for candidates
engines.py                  parses `annopage_client --list-engines` stdout
llm_aliases.py               short alias -> full completions URL (see below)
templates/ + static/          Jinja2 + vanilla JS, no build step
scripts/register_engine.py     standalone host-run admin bootstrap script
docker-compose.yml + docker/*.Dockerfile   4-service local stack
data/                           gitignored local state
```

Everything talks to a DocAPI-backed AnnoPage API. Auth in this dev setup
uses DocAPI's auto-provisioned test keys (created whenever `PRODUCTION=False`,
the default): `annopage.testadminkid.testadminkey` (admin, used by
`register_engine.py`), `annopage.testuserkid.testuserkey` (user, used by the
webapp/client), `annopage.testworkerkid.testworkerkey` (worker).

## Known gotchas already debugged — don't re-discover these

- **`cv2` (non-headless) needs system libs** (`libgl1`, `libglib2.0-0`,
  `libxcb1`, `libsm6`, `libxext6`, `libxrender1`) not in `python:3.11-slim`.
  Needed in the `api`, `worker`, *and* `webapp` images (the last one via
  `doc_api.adapter`, used by `annopage_client` itself).
- **No `WORKDIR` in `api.Dockerfile`** → uvicorn's dev auto-reloader (on
  whenever `PRODUCTION=False`) recursively scans the cwd for `.py` files;
  without a `WORKDIR` that's `/`, which crashes walking into `/proc`.
- **Engine files upload is `PUT`, not `POST`**: `PUT /v1/admin/engines/{name}/{version}/files`.
- **`torch` + `torchvision` must be installed together** from
  `https://download.pytorch.org/whl/cpu`, in the same `pip install` call —
  installing `torch` alone then letting `anno-page[tool]` pull its own
  `torchvision` causes an ABI mismatch (`torchvision::nms does not exist`).
- **Old-style `templates.TemplateResponse(name, context)` breaks** with
  newer `fastapi`/`starlette` (unpinned deps pulled the latest at build
  time). Use the modern `TemplateResponse(request, name, context)`.
- **DocAPI's admin API is write-only for engine files** — there is no
  endpoint to read a registered engine's `config.ini` back, not even for
  admins. `register_engine.py` writes its own local record to
  `data/engines.json` (`store.record_engine`/`list_engine_registry`) — that's
  the only source of truth for what an engine contains, and it only knows
  about engines registered through this script.
- **LLM API aliases never resolve inside the worker.** `anno_page`'s alias
  resolution (`AnnoPage/resources/llm_api_aliases.json`) only activates when
  `annopage` is invoked with `--llm-api-aliases-path`, and
  `AnnoPageWorker.process_job` never passes that flag (can't change — that's
  AnnoPage code). So a captioning profile with `"api": "OpenRouter"` used to
  crash with `requests.exceptions.MissingSchema`. Fixed: `job_runner.write_captioning_settings`
  resolves known aliases via `llm_aliases.py` before writing the file.
- **CLIP embeddings on CPU: use `PRECISION = float32`, not `bfloat16`.**
  PyTorch's CPU bfloat16 kernels are often unoptimized; a couple of tiny test
  regions took ~40 minutes and looked exactly like a hang (100% CPU, zero new
  log lines). `register_engine.py --with-embeddings` defaults to
  `--embedding-precision float32` for this reason.
- **Worker must run `--logging-level=DEBUG`.** `AnnoPageWorker.process_job`
  only logs the `annopage` subprocess's stdout/stderr when it exits 0 *if*
  the level is DEBUG. At INFO, a job can "succeed" with zero output and you
  get no clue why — the failure (e.g. a captioning exception) is logged at
  ERROR regardless, but the surrounding context that explains it isn't.
- **A captioning failure kills the whole page's output, not just the
  caption.** `anno_page/engines/captioning.py:process_elements` does
  `item.result = captioning_result.data` without a None-check; when the LLM
  call fails, that raises and aborts `process_page()` for the entire image —
  detection, ALTO, everything. `parse_folder.py` catches it per-file and logs
  "Failed to process file", but the job still reports `exit_code=0`. This is
  an AnnoPage bug, not fixable here (would require editing `AnnoPage`) — just
  know that "job succeeded, output is empty" almost always means a per-file
  exception, and DEBUG-level worker logs are where to look.
- **DocAPI's `cancelled` job state isn't recognized by `doc_client`'s
  polling loop** (`_wait_for_results` only treats `done`/`failed` as
  terminal) — if you cancel a job via the admin API
  (`PATCH /v1/admin/jobs/{id}` with `{"state": "cancelled"}`), the webapp's
  `annopage_client` subprocess for that job will poll forever. You have to
  kill that process too (find it with `docker compose top annopage-webapp`,
  or via `/proc/*/cmdline` grep inside the container if PIDs don't line up).
- **The webapp's own job id ≠ DocAPI's job id.** Every job record has both
  `id` (ours, used in URLs/API) and `remote_job_id` (DocAPI's, shows up in
  worker/API logs). If someone gives you a job id from the logs, look it up
  by `remote_job_id`, not `id`.

## Developing

```bash
# rebuild + restart one service (fast iteration)
docker compose build annopage-webapp && docker compose up -d annopage-webapp

# full stack
docker compose up -d --build

# watch what the ML pipeline actually did (not just annopage_client's polling log)
docker compose logs -f annopage-worker

# disk fills up fast with the worker image (torch etc) - if a build fails on space:
docker builder prune -f
```

`scripts/register_engine.py` is idempotent and safe to re-run — metadata
POST returns 409 if unchanged (handled gracefully), files PUT always
succeeds and overwrites. Useful invocations:

```bash
# base offline engine (default)
python3 scripts/register_engine.py --api-url http://localhost:8000

# + LLM captioning + CLIP embeddings, as a second non-default engine
python3 scripts/register_engine.py --api-url http://localhost:8000 \
  --name local-cpu-captioning --version v1 --with-captioning --with-embeddings --no-default
```

## Things intentionally *not* built

- No image gallery on the job-detail page (removed on request — output can
  be hundreds of pages).
- No "manage engines" UI for composing a `config.ini` visually — engine
  registration stays a host-run script (`register_engine.py`), consistent
  with constraint #3 above.
