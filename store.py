"""Tiny JSON-file-backed CRUD stores: targets, captioning profiles, jobs.

Nothing here touches the AnnoPage repo or talks to DocAPI directly - it only
manages this app's own local state under data/.
"""
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock

DATA_DIR = Path(__file__).parent / "data"
JOBS_DIR = DATA_DIR / "jobs"
TARGETS_FILE = DATA_DIR / "targets.json"
PROFILES_FILE = DATA_DIR / "captioning_profiles.json"
ENGINES_FILE = DATA_DIR / "engines.json"

_lock = Lock()


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_json(path: Path, default):
    if not path.exists():
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _write_json(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    tmp.replace(path)


def mask_key(key: str) -> str:
    if not key:
        return ""
    if len(key) <= 4:
        return "*" * len(key)
    return f"{'*' * (len(key) - 4)}{key[-4:]}"


# --- targets ---------------------------------------------------------------

def list_targets(masked: bool = True) -> list[dict]:
    with _lock:
        targets = _read_json(TARGETS_FILE, [])
    if masked:
        return [{**t, "api_key": mask_key(t["api_key"])} for t in targets]
    return targets


def get_target(target_id: str) -> dict | None:
    with _lock:
        targets = _read_json(TARGETS_FILE, [])
    return next((t for t in targets if t["id"] == target_id), None)


def create_target(label: str, api_url: str, api_key: str) -> dict:
    target = {
        "id": str(uuid.uuid4()),
        "label": label,
        "api_url": api_url.rstrip("/"),
        "api_key": api_key,
        "created_at": _now(),
    }
    with _lock:
        targets = _read_json(TARGETS_FILE, [])
        targets.append(target)
        _write_json(TARGETS_FILE, targets)
    return target


def delete_target(target_id: str) -> bool:
    with _lock:
        targets = _read_json(TARGETS_FILE, [])
        remaining = [t for t in targets if t["id"] != target_id]
        if len(remaining) == len(targets):
            return False
        _write_json(TARGETS_FILE, remaining)
    return True


# --- captioning profiles ----------------------------------------------------

def list_profiles() -> list[dict]:
    with _lock:
        return _read_json(PROFILES_FILE, [])


def get_profile(profile_id: str) -> dict | None:
    return next((p for p in list_profiles() if p["id"] == profile_id), None)


def create_profile(label: str, settings: dict) -> dict:
    profile = {
        "id": str(uuid.uuid4()),
        "label": label,
        "settings": settings,
        "created_at": _now(),
    }
    with _lock:
        profiles = _read_json(PROFILES_FILE, [])
        profiles.append(profile)
        _write_json(PROFILES_FILE, profiles)
    return profile


def delete_profile(profile_id: str) -> bool:
    with _lock:
        profiles = _read_json(PROFILES_FILE, [])
        remaining = [p for p in profiles if p["id"] != profile_id]
        if len(remaining) == len(profiles):
            return False
        _write_json(PROFILES_FILE, remaining)
    return True


# --- engine registry (local record of what register_engine.py registered) ---
#
# DocAPI's admin API is write-only for engine files (POST metadata, PUT
# files) - there is no endpoint to read a registered engine's config.ini
# back, for admins or anyone else. So this is the only record of what an
# engine actually contains; it only knows about engines registered through
# register_engine.py, not ones added any other way.

def list_engine_registry() -> list[dict]:
    with _lock:
        return _read_json(ENGINES_FILE, [])


def record_engine(*, target_api_url: str, name: str, version: str, description: str,
                  default: bool, config_ini: str) -> dict:
    entry = {
        "target_api_url": target_api_url,
        "name": name,
        "version": version,
        "description": description,
        "default": default,
        "config_ini": config_ini,
        "registered_at": _now(),
    }
    with _lock:
        entries = _read_json(ENGINES_FILE, [])
        entries = [e for e in entries if not (e["target_api_url"] == target_api_url and e["name"] == name and e["version"] == version)]
        entries.append(entry)
        _write_json(ENGINES_FILE, entries)
    return entry


# --- jobs --------------------------------------------------------------------

def job_dir(job_id: str) -> Path:
    return JOBS_DIR / job_id


def job_file(job_id: str) -> Path:
    return job_dir(job_id) / "job.json"


def log_file(job_id: str) -> Path:
    return job_dir(job_id) / "run.log"


def tail_log(job_id: str, lines: int = 5) -> str:
    """Return the last `lines` lines of a job's log, without reading the
    whole file - a job over thousands of images can produce a log too large
    to load into a browser tab on every poll."""
    path = log_file(job_id)
    if not path.is_file():
        return ""
    block_size = 8192
    data = b""
    with open(path, "rb") as f:
        f.seek(0, os.SEEK_END)
        remaining = f.tell()
        while remaining > 0 and data.count(b"\n") <= lines:
            read_size = min(block_size, remaining)
            remaining -= read_size
            f.seek(remaining)
            data = f.read(read_size) + data
    text = data.decode("utf-8", errors="replace")
    return "\n".join(text.splitlines()[-lines:])


def create_job(**fields) -> dict:
    job_id = str(uuid.uuid4())
    job = {
        "id": job_id,
        "created_at": _now(),
        "state": "starting",
        "progress": None,
        "remote_job_id": None,
        "exit_code": None,
        "error": None,
        **fields,
    }
    job_dir(job_id).mkdir(parents=True, exist_ok=True)
    save_job(job)
    return job


def save_job(job: dict) -> None:
    with _lock:
        _write_json(job_file(job["id"]), job)


def get_job(job_id: str) -> dict | None:
    path = job_file(job_id)
    if not path.exists():
        return None
    with _lock:
        return _read_json(path, None)


def list_jobs() -> list[dict]:
    if not JOBS_DIR.exists():
        return []
    jobs = []
    for entry in JOBS_DIR.iterdir():
        job = get_job(entry.name)
        if job:
            jobs.append(job)
    jobs.sort(key=lambda j: j["created_at"], reverse=True)
    return jobs


def read_processing_info(job: dict) -> dict | None:
    """Reads <output_dir>/processing_info.json, written by the `annopage` CLI
    (AnnoPage/api/worker.py passes --output-processing-info-path) and bundled
    into every job's result.zip alongside alto/embeddings/etc. Returns None
    if the job's output dir doesn't have one yet (older jobs, or job not
    finished)."""
    output_dir = job.get("output_dir")
    if not output_dir:
        return None
    return _read_json(Path(output_dir) / "processing_info.json", None)


def update_job(job_id: str, **changes) -> dict | None:
    with _lock:
        job = _read_json(job_file(job_id), None)
        if job is None:
            return None
        job.update(changes)
        _write_json(job_file(job_id), job)
    return job
