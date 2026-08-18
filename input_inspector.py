"""Validates a user-supplied input folder before we build an annopage_client
command out of it - mirrors the klient/<run>/input/ layout: images/,
optional alto_xmls/, optional metadata.json.
"""
import json
import os
from pathlib import Path

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".tif", ".tiff"}

# In the Docker setup this is where docker-compose.yml bind-mounts host input
# data (see INPUT_ROOT env var there); outside Docker it just won't exist and
# browse_input_candidates() degrades to an empty list.
INPUT_ROOT = os.environ.get("INPUT_ROOT", "/data")
MAX_SCAN_DEPTH = 6
MAX_CANDIDATES = 200


def inspect_input_folder(path_str: str) -> dict:
    result = {
        "path": path_str,
        "ok": False,
        "errors": [],
        "images_dir": None,
        "images_count": 0,
        "alto_dir": None,
        "alto_count": 0,
        "metadata_path": None,
        "metadata_count": None,
    }

    if not path_str:
        result["errors"].append("Cesta nesmí být prázdná.")
        return result

    base = Path(path_str).expanduser()
    if not base.is_dir():
        result["errors"].append(f"Složka neexistuje: {base}")
        return result

    images_dir = base / "images"
    if not images_dir.is_dir():
        result["errors"].append("Chybí podsložka 'images'.")
    else:
        images = [p for p in images_dir.iterdir() if p.suffix.lower() in IMAGE_EXTENSIONS]
        result["images_dir"] = str(images_dir)
        result["images_count"] = len(images)
        if not images:
            result["errors"].append("Ve složce 'images' nejsou žádné obrázky.")

    alto_dir = base / "alto_xmls"
    if alto_dir.is_dir():
        alto_files = list(alto_dir.glob("*.xml"))
        result["alto_dir"] = str(alto_dir)
        result["alto_count"] = len(alto_files)

    metadata_path = base / "metadata.json"
    if metadata_path.is_file():
        result["metadata_path"] = str(metadata_path)
        try:
            with open(metadata_path, "r", encoding="utf-8") as f:
                data = json.load(f)
            result["metadata_count"] = len(data) if isinstance(data, dict) else None
        except (json.JSONDecodeError, OSError) as exc:
            result["errors"].append(f"metadata.json se nepodařilo načíst: {exc}")

    result["ok"] = not result["errors"]
    return result


def browse_input_candidates(root: str | None = None) -> list[dict]:
    """Scans root (default INPUT_ROOT) for directories that look like an
    input folder - i.e. have an 'images' subdirectory - so the UI can offer
    a picker instead of making the user type a container-side path."""
    base = Path(root or INPUT_ROOT)
    if not base.is_dir():
        return []

    candidates = []
    base_depth = len(base.parts)
    for dirpath, dirnames, _filenames in os.walk(base):
        dirnames[:] = [d for d in dirnames if not d.startswith(".")]
        current = Path(dirpath)
        depth = len(current.parts) - base_depth
        if depth >= MAX_SCAN_DEPTH:
            dirnames[:] = []
            continue

        if "images" in dirnames:
            info = inspect_input_folder(str(current))
            candidates.append({
                "path": str(current),
                "relative_path": str(current.relative_to(base)),
                "images_count": info["images_count"],
                "has_alto": info["alto_dir"] is not None,
                "has_metadata": info["metadata_path"] is not None,
            })
            if len(candidates) >= MAX_CANDIDATES:
                break

    candidates.sort(key=lambda c: c["relative_path"])
    return candidates
