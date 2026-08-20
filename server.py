"""FastAPI app for the local AnnoPage web wrapper.

Every action here either manages this app's own local JSON state (targets,
captioning profiles, job records) or shells out to the already-installed
annopage_client executable (engines.py, job_runner.py). Nothing here imports
doc_api/doc_client or talks HTTP to AnnoPageAPI directly, and nothing here
touches the AnnoPage repo's own files.
"""
import shutil
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

import engines
import input_inspector
import job_runner
import store

BASE_DIR = Path(__file__).parent

app = FastAPI(title="AnnoPage local runner")
app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")
templates = Jinja2Templates(directory=BASE_DIR / "templates")


# --- pages -------------------------------------------------------------------

@app.get("/")
def index(request: Request):
    return templates.TemplateResponse(request, "index.html", {
        "targets": store.list_targets(),
        "profiles": store.list_profiles(),
    })


@app.get("/jobs")
def jobs_page(request: Request):
    return templates.TemplateResponse(request, "jobs.html", {
        "jobs": store.list_jobs(),
    })


@app.get("/jobs/{job_id}")
def job_detail_page(request: Request, job_id: str):
    job = store.get_job(job_id)
    if job is None:
        raise HTTPException(404, "Job nenalezen.")
    return templates.TemplateResponse(request, "job_detail.html", {
        "job": job,
    })


@app.get("/settings")
def settings_page(request: Request):
    return templates.TemplateResponse(request, "settings.html", {
        "targets": store.list_targets(),
        "profiles": store.list_profiles(),
        "engine_registry": store.list_engine_registry(),
    })


# --- targets -------------------------------------------------------------------

@app.get("/api/targets")
def api_list_targets():
    return store.list_targets()


@app.post("/api/targets")
async def api_create_target(request: Request):
    body = await request.json()
    label = (body.get("label") or "").strip()
    api_url = (body.get("api_url") or "").strip()
    api_key = (body.get("api_key") or "").strip()
    if not label or not api_url or not api_key:
        raise HTTPException(400, "label, api_url a api_key jsou povinné.")
    target = store.create_target(label, api_url, api_key)
    return {**target, "api_key": store.mask_key(target["api_key"])}


@app.delete("/api/targets/{target_id}")
def api_delete_target(target_id: str):
    if not store.delete_target(target_id):
        raise HTTPException(404, "Target nenalezen.")
    return {"ok": True}


# --- captioning profiles --------------------------------------------------------

@app.get("/api/captioning-profiles")
def api_list_profiles():
    return store.list_profiles()


@app.post("/api/captioning-profiles")
async def api_create_profile(request: Request):
    body = await request.json()
    label = (body.get("label") or "").strip()
    settings = body.get("settings")
    if not label or not isinstance(settings, dict):
        raise HTTPException(400, "label a settings (JSON objekt) jsou povinné.")
    return store.create_profile(label, settings)


@app.delete("/api/captioning-profiles/{profile_id}")
def api_delete_profile(profile_id: str):
    if not store.delete_profile(profile_id):
        raise HTTPException(404, "Profil nenalezen.")
    return {"ok": True}


# --- engines -------------------------------------------------------------------

@app.get("/api/engines")
def api_list_engines(target_id: str):
    target = store.get_target(target_id)
    if target is None:
        raise HTTPException(404, "Target nenalezen.")
    found, error = engines.list_engines(target["api_url"], target["api_key"])
    if error:
        return JSONResponse({"engines": [], "error": error}, status_code=502)
    return {"engines": found, "error": None}


# --- input inspection ------------------------------------------------------------

@app.post("/api/input/inspect")
async def api_inspect_input(request: Request):
    body = await request.json()
    return input_inspector.inspect_input_folder(body.get("path", ""))


@app.get("/api/input/browse")
def api_browse_input():
    return {
        "root": input_inspector.INPUT_ROOT,
        "available": Path(input_inspector.INPUT_ROOT).is_dir(),
        "candidates": input_inspector.browse_input_candidates(),
    }


# --- jobs ----------------------------------------------------------------------

@app.get("/api/jobs")
def api_list_jobs():
    return store.list_jobs()


@app.get("/api/jobs/{job_id}")
def api_get_job(job_id: str):
    job = store.get_job(job_id)
    if job is None:
        raise HTTPException(404, "Job nenalezen.")
    return job


@app.post("/api/jobs")
async def api_create_job(request: Request):
    body = await request.json()

    input_path = body.get("input_path", "")
    inspection = input_inspector.inspect_input_folder(input_path)
    if not inspection["ok"]:
        raise HTTPException(400, "; ".join(inspection["errors"]) or "Neplatná vstupní složka.")

    target_id = body.get("target_id")
    target = store.get_target(target_id)
    if target is None:
        raise HTTPException(400, "Vyberte platný target.")

    outputs = body.get("outputs") or {}
    output_path = (body.get("output_path") or "").strip()

    job = store.create_job(
        input_path=input_path,
        images_dir=inspection["images_dir"],
        alto_dir=inspection["alto_dir"],
        metadata_path=inspection["metadata_path"],
        target_id=target_id,
        target_label=target["label"],
        engine_name=(body.get("engine_name") or "").strip() or None,
        outputs=outputs,
        captioning_profile_id=body.get("captioning_profile_id") or None,
        output_dir=None,
    )

    output_dir = output_path or str(store.job_dir(job["id"]) / "output")
    changes = {"output_dir": output_dir}

    profile_id = body.get("captioning_profile_id")
    if profile_id:
        profile = store.get_profile(profile_id)
        if profile is None:
            store.update_job(job["id"], state="failed", error="Zvolený captioning profil neexistuje.")
            raise HTTPException(400, "Zvolený captioning profil neexistuje.")
        changes["captioning_settings_path"] = job_runner.write_captioning_settings(job["id"], profile["settings"])
        changes["captioning_profile_label"] = profile["label"]

    job = store.update_job(job["id"], **changes)
    job_runner.start_job(job["id"])
    return job


@app.get("/api/jobs/{job_id}/log")
def api_job_log(job_id: str, lines: int = 5):
    job = store.get_job(job_id)
    if job is None:
        raise HTTPException(404, "Job nenalezen.")
    return {"log": store.tail_log(job_id, lines)}


@app.get("/api/jobs/{job_id}/download")
def api_job_download(job_id: str):
    job = store.get_job(job_id)
    if job is None:
        raise HTTPException(404, "Job nenalezen.")
    if job["state"] != "done":
        raise HTTPException(400, "Job ještě neskončil.")

    zip_base = store.job_dir(job_id) / "download"
    zip_path = zip_base.with_suffix(".zip")
    if not zip_path.is_file():
        shutil.make_archive(str(zip_base), "zip", job["output_dir"])
    return FileResponse(zip_path, filename=f"annopage-{job_id}.zip")
