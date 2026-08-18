"""Resolves short LLM API aliases (as used in klient/prompts/*.json captioning
profiles, e.g. "api": "OpenRouter") to full completions URLs.

anno_page's own alias resolution (anno_page/core/llm_api_aliases.py, loaded
from AnnoPage/resources/llm_api_aliases.json) only activates when `annopage`
is invoked with --llm-api-aliases-path. AnnoPageWorker.process_job never
passes that flag, so inside this worker setup a captioning profile's "api"
value is used completely literally - a short alias like "OpenRouter" isn't a
valid URL and the captioning request fails with requests.exceptions.MissingSchema
(which then takes down that whole page's output, not just the caption - see
AnnoPage/api/worker.py / anno_page/engines/captioning.py).

So the webapp resolves known aliases itself before writing a job's
--image-captioning-settings file. Mirrors AnnoPage/resources/llm_api_aliases.json;
update this if that file gains new aliases.
"""

ALIASES = {
    "openai": "https://api.openai.com/v1/chat/completions",
    "chatgpt": "https://api.openai.com/v1/chat/completions",
    "openrouter": "https://openrouter.ai/api/v1/chat/completions",
    "cerit": "https://llm.ai.e-infra.cz/v1/chat/completions",
    "e-infra": "https://llm.ai.e-infra.cz/v1/chat/completions",
}


def resolve_api(value: str) -> str:
    """Returns the full URL for a known alias (case-insensitive), or value
    unchanged if it isn't one (assumed to already be a literal URL)."""
    return ALIASES.get(value.strip().lower(), value)
