"""Builds the annopage_client argv and runs it as a subprocess in the
background, tailing its combined stdout/stderr to update job state.

This never imports doc_api/doc_client or talks to DocAPI itself - it always
shells out to the already-installed annopage_client executable, the same way
AnnoPageWorker.process_job in AnnoPage's api/worker.py shells out to
`annopage`. If annopage_client's CLI flags change after a `git pull` of
AnnoPage, only this file needs updating.
"""
import json
import os
import re
import subprocess
import threading

import llm_aliases
import store

STATUS_RE = re.compile(r"^Job status: (?:\w+\.)?(\w+), progress: ([\d.]+)")
CREATED_RE = re.compile(r"^Job (\S+) created$")

OUTPUT_FLAGS = {
    "alto": "--output-alto",
    "embeddings": "--output-embeddings",
    "embeddings_jsonlines": "--output-embeddings-jsonlines",
    "renders": "--output-renders",
    "crops": "--output-crops",
    "image_captioning_prompts": "--output-image-captioning-prompts",
}


def build_argv(job: dict, target: dict) -> list[str]:
    argv = [
        "annopage_client",
        "--images", job["images_dir"],
    ]
    if job.get("alto_dir"):
        argv += ["--alto-xmls", job["alto_dir"]]
    if job.get("metadata_path"):
        argv += ["--metadata", job["metadata_path"]]

    argv += ["--output", job["output_dir"]]

    for key, flag in OUTPUT_FLAGS.items():
        if job["outputs"].get(key):
            argv.append(flag)

    if job.get("captioning_settings_path"):
        argv += ["--image-captioning-settings", job["captioning_settings_path"]]

    if job.get("engine_name"):
        argv += ["--engine-name", job["engine_name"]]

    argv += [
        "--api-url", target["api_url"],
        "--api-key", target["api_key"],
        "--logging-level", "INFO",
    ]
    return argv


def start_job(job_id: str) -> None:
    thread = threading.Thread(target=_run, args=(job_id,), daemon=True)
    thread.start()


def _run(job_id: str) -> None:
    job = store.get_job(job_id)
    if job is None:
        return

    target = store.get_target(job["target_id"])
    if target is None:
        store.update_job(job_id, state="failed", error="Cílový profil (target) už neexistuje.")
        return

    argv = build_argv(job, target)
    store.update_job(job_id, state="starting", argv=argv)

    os.makedirs(job["output_dir"], exist_ok=True)
    log_path = store.log_file(job_id)

    try:
        proc = subprocess.Popen(
            argv,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            bufsize=1,
        )
    except FileNotFoundError:
        store.update_job(job_id, state="failed", error="annopage_client nebyl nalezen na PATH.")
        return

    store.update_job(job_id, state="running", pid=proc.pid)

    with open(log_path, "w", encoding="utf-8") as log:
        for line in proc.stdout:
            log.write(line)
            log.flush()
            _handle_line(job_id, line.rstrip("\n"))

    exit_code = proc.wait()
    if exit_code == 0:
        store.update_job(job_id, state="done", exit_code=exit_code, progress=1.0)
    else:
        tail = _tail(log_path, 20)
        store.update_job(job_id, state="failed", exit_code=exit_code, error=tail)


def _handle_line(job_id: str, line: str) -> None:
    m = CREATED_RE.match(line)
    if m:
        store.update_job(job_id, remote_job_id=m.group(1))
        return

    m = STATUS_RE.match(line)
    if m:
        store.update_job(job_id, progress=float(m.group(2)), remote_state=m.group(1))
        return


def _tail(path, n: int) -> str:
    try:
        with open(path, "r", encoding="utf-8") as f:
            lines = f.readlines()
        return "".join(lines[-n:])
    except OSError:
        return ""


def write_captioning_settings(job_id: str, settings: dict) -> str:
    if "api" in settings:
        settings = {**settings, "api": llm_aliases.resolve_api(settings["api"])}
    path = store.job_dir(job_id) / "captioning_settings.json"
    with open(path, "w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2, ensure_ascii=False)
    return str(path)
