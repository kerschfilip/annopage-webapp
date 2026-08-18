"""Runs `annopage_client --list-engines` and parses its stdout.

The parser matches format_engines() in AnnoPage's api/client.py line for
line - that function's output is the contract, not any internal API shape:

    Available engines:

    Name: 'foo'
    Description: short text
    Name: 'bar'
    Description:
    multi
    line text
"""
import subprocess


def list_engines(api_url: str, api_key: str) -> tuple[list[dict], str | None]:
    argv = [
        "annopage_client",
        "--list-engines",
        "--api-url", api_url,
        "--api-key", api_key,
    ]
    try:
        proc = subprocess.run(argv, capture_output=True, text=True, timeout=30)
    except FileNotFoundError:
        return [], "annopage_client nebyl nalezen na PATH. Je nainstalovaný AnnoPage balíček?"
    except subprocess.TimeoutExpired:
        return [], "Časový limit vypršel při dotazu na dostupné engine."

    output = proc.stdout + proc.stderr
    if proc.returncode != 0:
        return [], output.strip() or f"annopage_client skončil s kódem {proc.returncode}"

    return _parse_engines(output), None


def _parse_engines(output: str) -> list[dict]:
    lines = output.splitlines()
    engines: list[dict] = []
    current: dict | None = None
    collecting_description = False

    for line in lines:
        if line.startswith("Name: '"):
            if current is not None:
                engines.append(current)
            name = line[len("Name: '"):].rstrip("'")
            current = {"name": name, "description": ""}
            collecting_description = False
            continue

        if current is None:
            continue

        if line == "Description:":
            collecting_description = True
            continue

        if line.startswith("Description: "):
            current["description"] = line[len("Description: "):]
            collecting_description = False
            continue

        if collecting_description:
            if line.strip() == "":
                collecting_description = False
            else:
                current["description"] = (current["description"] + "\n" + line).strip()

    if current is not None:
        engines.append(current)

    return engines
