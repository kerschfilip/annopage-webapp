"""One-time, idempotent setup: registers a local "engine" (config.ini + model
weights, zipped) with a freshly-migrated AnnoPageAPI, so annopage_worker has
something to run - a fresh DB starts with zero engines registered.

Talks to DocAPI's admin endpoints directly (X-API-Key auth) via plain
`requests`. This is an operator bootstrap script run once by hand, not part
of the webapp's runtime request path - it never runs as a consequence of a
user submitting a job through the web UI.

By default builds an offline engine (non-textual element detection +
caption-to-region linking only, no external API key needed) from the model
weights already present in AnnoPage/resources/models/.

Pass --with-captioning to additionally register an OPENAI_COMPLETIONS_IMAGE_CAPTIONING
step (LLM-based). Two things are NOT obvious about this and matter if you're
adding it:

1. The engine's own config.ini must contain this step for captioning to run
   at all. The webapp's per-job "Captioning profil" (--image-captioning-settings)
   can only OVERRIDE api/api_key/categories/prompts of an EXISTING step
   (see AnnoPageWorker.update_image_captioning_config in AnnoPage/api/worker.py) -
   it cannot add the step to an engine that doesn't have one.
2. anno_page's LLM API aliases (openai/openrouter/... -> full URL, see
   AnnoPage/resources/llm_api_aliases.json) only resolve when `annopage` is
   invoked with --llm-api-aliases-path. AnnoPageWorker.process_job never
   passes that flag (and we can't change AnnoPage's code), so aliases never
   load in this setup - the API config value MUST be a literal full URL, not
   a short alias like "openai".

This script never bakes a real LLM key into the engine bundle by default -
keep that in a per-job Captioning profile in the webapp instead (Settings ->
captioning profiles), so it isn't sitting in a zip on the API's disk.

Pass --with-embeddings to additionally register a HUGGINGFACE_IMAGE_EMBEDDING
step (CLIP). It downloads its model from the HuggingFace Hub the first time
it runs inside the worker container - that container needs internet access
and, ideally, a persistent volume for its HF cache (see docker-compose.yml's
HF_HOME) so it isn't re-downloaded on every worker restart. --embedding-precision
defaults to float32, not bfloat16: PyTorch's CPU bfloat16 kernels are often
unoptimized (no native hardware bf16 path the way GPUs have), and inference
on even a couple of tiny regions can look hung for tens of minutes.

DocAPI's admin API has no endpoint to read a registered engine's config.ini
back - not even for admins. So after a successful registration this script
also writes the config.ini into this webapp's own data/engines.json (see
store.record_engine), which is what Settings' engine overview reads from -
it only knows about engines registered through this script, not ones added
any other way.
"""
import argparse
import configparser
import io
import json
import sys
import zipfile
from pathlib import Path

import requests

REPO_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_MODELS_DIR = REPO_ROOT / "AnnoPage" / "resources" / "models"
DEFAULT_PROMPT_SETTINGS = REPO_ROOT / "AnnoPage" / "resources" / "image_captioning_prompt.json"

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import store  # noqa: E402

ORGANIZER_CATEGORIES = [
    "Padding", "Image", "Photograph", "Caricature and comics", "Stamp",
    "Barcode and QR code", "Symbol, logo, coat of arms", "Vignette", "Frieze",
    "Signet", "Initial", "Other book decor", "Decorative inscription",
    "Musical notation", "Table", "Map", "Graph", "Geometric drawing",
    "Other technical drawing", "Diagram", "Floor plan",
    "Mathematical expression and equation", "Chemical formula and equation",
    "Exlibris", "Advertisement", "Handwritten note", "Image caption",
]

# Categories that trigger the (optional) captioning step. Kept separate from
# ORGANIZER_CATEGORIES above since captioning is deliberately only run on a
# subset - it costs LLM tokens per region.
DEFAULT_CAPTIONING_CATEGORIES = [
    "Photograph", "Geometric drawing", "Graph", "Caricature and comics",
    "Map", "Image", "Other technical drawing", "Floor plan", "Diagram", "Stamp",
]

# See docstring point 2: must be a literal URL, not an alias, in this setup.
# OpenRouter, not OpenAI directly: AnnoPage/resources/image_captioning_prompt.json's
# "model" is "openai/gpt-4.1-mini" - an OpenRouter-style provider-prefixed id
# that plain OpenAI's API would reject. If you override the prompt file/model
# per-job to a native OpenAI id, override --captioning-api to match.
DEFAULT_CAPTIONING_API = "https://openrouter.ai/api/v1/chat/completions"

DEFAULT_EMBEDDING_CATEGORIES = [
    "Photograph", "Geometric drawing", "Graph", "Caricature and comics",
    "Map", "Image", "Other technical drawing", "Floor plan", "Diagram",
]
# A real HuggingFace repo id - anno_page/engines/embedding.py does
# AutoModel.from_pretrained(MODEL), a short alias like "clip-ViT-L-14" is
# not valid here.
DEFAULT_EMBEDDING_MODEL = "openai/clip-vit-large-patch14"


def latest_zip(models_dir: Path, subdir: str) -> Path:
    zips = sorted((models_dir / subdir).glob("*.zip"))
    if not zips:
        raise FileNotFoundError(f"No model zip found under {models_dir / subdir}")
    return zips[-1]


def build_config_ini(with_captioning: bool, captioning_api: str, captioning_api_key: str, captioning_categories: list[str],
                     with_embeddings: bool, embedding_model: str, embedding_categories: list[str], embedding_precision: str) -> str:
    config = f"""[OPERATION_1]
METHOD = YOLO_DETECTION
MODEL_PATH = ./annopage_nontextual_element_detector.pt
DETECTION_THRESHOLD = 0.283
IMAGE_SIZE = 1024

[OPERATION_2]
METHOD = CAPTION_YOLO_ORGANIZER
YOLO_PATH = ./annopage_captions_detector.pt
YOLO_IMAGE_SIZE = 1024
YOLO_DETECTION_THRESHOLD = 0.499
ORGANIZER_PATH = ./annopage_captions_organizer.pt
ORGANIZER_CATEGORIES = {json.dumps(ORGANIZER_CATEGORIES)}
"""
    next_op = 3
    if with_captioning:
        config += f"""
[OPERATION_{next_op}]
METHOD = OPENAI_COMPLETIONS_IMAGE_CAPTIONING
API = {captioning_api}
API_KEY = {captioning_api_key}
PROMPT_SETTINGS = ./image_captioning_prompt.json
CATEGORIES = {json.dumps(captioning_categories)}
NUM_PROCESSES = 2
MAX_ATTEMPTS = 3
"""
        next_op += 1

    if with_embeddings:
        config += f"""
[OPERATION_{next_op}]
METHOD = HUGGINGFACE_IMAGE_EMBEDDING
MODEL = {embedding_model}
DECIMAL_PLACES = 8
PRECISION = {embedding_precision}
CATEGORIES = {json.dumps(embedding_categories)}
"""
        next_op += 1

    return config


def build_bundle_zip(models_dir: Path, with_captioning: bool, captioning_api: str, captioning_api_key: str,
                     captioning_categories: list[str], prompt_settings_path: Path,
                     with_embeddings: bool, embedding_model: str, embedding_categories: list[str], embedding_precision: str) -> tuple[bytes, str]:
    detector_zip = latest_zip(models_dir, "non-textual_element_detector")
    captions_zip = latest_zip(models_dir, "captions_analyzer")
    print(f"Using {detector_zip.relative_to(REPO_ROOT)}")
    print(f"Using {captions_zip.relative_to(REPO_ROOT)}")

    config_ini = build_config_ini(with_captioning, captioning_api, captioning_api_key, captioning_categories,
                                  with_embeddings, embedding_model, embedding_categories, embedding_precision)

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as out:
        with zipfile.ZipFile(detector_zip) as src:
            out.writestr(
                "annopage_nontextual_element_detector.pt",
                src.read("annopage_nontextual_element_detector.pt"),
            )
        with zipfile.ZipFile(captions_zip) as src:
            for name in ("annopage_captions_detector.pt", "annopage_captions_organizer.pt", "annopage_captions_organizer.pt.cpu"):
                out.writestr(name, src.read(name))

        if with_captioning:
            if not prompt_settings_path.is_file():
                raise FileNotFoundError(f"Prompt settings file not found: {prompt_settings_path}")
            print(f"Using {prompt_settings_path.relative_to(REPO_ROOT) if prompt_settings_path.is_relative_to(REPO_ROOT) else prompt_settings_path}")
            out.write(prompt_settings_path, "image_captioning_prompt.json")

        out.writestr("config.ini", config_ini)

    # sanity check: config.ini's METHOD keys must be ones operation_factory accepts
    parser = configparser.ConfigParser()
    parser.read_string(config_ini)
    assert parser["OPERATION_1"]["METHOD"] == "YOLO_DETECTION"
    assert parser["OPERATION_2"]["METHOD"] == "CAPTION_YOLO_ORGANIZER"
    for section in parser.sections():
        if parser[section].get("METHOD") == "OPENAI_COMPLETIONS_IMAGE_CAPTIONING":
            assert with_captioning
        if parser[section].get("METHOD") == "HUGGINGFACE_IMAGE_EMBEDDING":
            assert with_embeddings

    return buf.getvalue(), config_ini


def register(api_url: str, admin_key: str, name: str, version: str, description: str, default: bool, bundle: bytes) -> None:
    headers = {"X-API-Key": admin_key}

    resp = requests.post(
        f"{api_url}/v1/admin/engines",
        json={"name": name, "version": version, "description": description, "default": default, "active": True},
        headers=headers,
        timeout=30,
    )
    if resp.status_code >= 400 and "already exists" not in resp.text.lower():
        print(resp.status_code, resp.text, file=sys.stderr)
        resp.raise_for_status()
    else:
        print(f"Engine metadata: {resp.status_code} {resp.text[:200]}")

    resp = requests.put(
        f"{api_url}/v1/admin/engines/{name}/{version}/files",
        headers=headers,
        files={"file": ("engine.zip", bundle, "application/zip")},
        timeout=180,
    )
    resp.raise_for_status()
    print(f"Engine files: {resp.status_code} {resp.text[:200]}")


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--api-url", default="http://localhost:8000")
    parser.add_argument("--admin-key", default="annopage.testadminkid.testadminkey",
                        help="DocAPI's auto-provisioned dev admin key when PRODUCTION=False (default).")
    parser.add_argument("--models-dir", default=str(DEFAULT_MODELS_DIR))
    parser.add_argument("--name", default="local-cpu")
    parser.add_argument("--version", default="v1")
    parser.add_argument("--description", default=None,
                        help="Defaults to a description that reflects --with-captioning/--with-embeddings.")
    parser.add_argument("--no-default", dest="default", action="store_false", default=True,
                        help="Don't mark this engine as the default - keeps whatever engine is "
                             "currently default as-is. Use this for a second/variant engine so "
                             "jobs that don't pick an engine explicitly keep using the old one.")

    parser.add_argument("--with-captioning", action="store_true",
                        help="Add an OPENAI_COMPLETIONS_IMAGE_CAPTIONING step. See module docstring "
                             "for two non-obvious requirements this comes with.")
    parser.add_argument("--captioning-api", default=DEFAULT_CAPTIONING_API,
                        help="Must be a literal completions URL, not an alias like 'openai' - see module docstring.")
    parser.add_argument("--captioning-api-key", default="REPLACE_VIA_CAPTIONING_PROFILE",
                        help="Placeholder baked into config.ini. Put the real key in a per-job "
                             "Captioning profile in the webapp instead (Settings page).")
    parser.add_argument("--captioning-categories", default=None,
                        help="JSON list of categories that trigger captioning. Defaults to a built-in list.")
    parser.add_argument("--prompt-settings", default=str(DEFAULT_PROMPT_SETTINGS),
                        help="Path to a {model, text: {category: prompt}, max_tokens} JSON file, bundled into the engine.")

    parser.add_argument("--with-embeddings", action="store_true",
                        help="Add a HUGGINGFACE_IMAGE_EMBEDDING (CLIP) step. Needs internet access "
                             "from the worker on first use to download the model from HuggingFace.")
    parser.add_argument("--embedding-model", default=DEFAULT_EMBEDDING_MODEL,
                        help="A HuggingFace repo id, not a short alias like 'clip-ViT-L-14'.")
    parser.add_argument("--embedding-categories", default=None,
                        help="JSON list of categories to embed. Defaults to a built-in list.")
    parser.add_argument("--embedding-precision", default="float32",
                        help="torch dtype for CLIP inference (float32/float16/bfloat16). Defaults to "
                             "float32 - bfloat16 has no efficient CPU kernel in this setup (--device cpu "
                             "always, no GPU passthrough in Docker) and can be dramatically slower, to "
                             "the point of looking hung on a couple of tiny test images.")
    args = parser.parse_args()

    captioning_categories = json.loads(args.captioning_categories) if args.captioning_categories else DEFAULT_CAPTIONING_CATEGORIES
    embedding_categories = json.loads(args.embedding_categories) if args.embedding_categories else DEFAULT_EMBEDDING_CATEGORIES

    if args.description is None:
        steps = ["non-textual detection", "caption linking"]
        if args.with_captioning:
            steps.append("LLM captioning")
        if args.with_embeddings:
            steps.append("CLIP embeddings")
        args.description = "Local offline engine: " + " + ".join(steps) + "."

    bundle, config_ini = build_bundle_zip(
        Path(args.models_dir), args.with_captioning, args.captioning_api, args.captioning_api_key,
        captioning_categories, Path(args.prompt_settings),
        args.with_embeddings, args.embedding_model, embedding_categories, args.embedding_precision,
    )
    register(args.api_url, args.admin_key, args.name, args.version, args.description, args.default, bundle)
    store.record_engine(target_api_url=args.api_url, name=args.name, version=args.version,
                        description=args.description, default=args.default, config_ini=config_ini)
    print(f"\nDone. Engine '{args.name}' v{args.version} registered" + (" as default engine." if args.default else " (not default - select it explicitly per job)."))
    print("Recorded locally in data/engines.json (visible in the webapp's Settings page).")


if __name__ == "__main__":
    main()
