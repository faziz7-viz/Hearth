#!/usr/bin/env python3
"""Render exact ElevenLabs API payloads locally; never read API keys or contact a service."""

import argparse
import json
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
TOOL_NAMES = (
    "lookup_property", "check_open_jobs", "lookup_maintenance_context", "prepare_repair_draft",
)


def render(public_url: str, secret_id: str, tool_ids: list[str], max_seconds: int) -> dict[str, dict]:
    parsed = urlsplit(public_url)
    if (parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password
            or parsed.query or parsed.fragment or parsed.path not in ("", "/")):
        raise ValueError("Use the HTTPS gateway origin only, without a path, credentials, or query.")
    if not secret_id.strip() or secret_id.startswith("__"):
        raise ValueError("Supply the ElevenLabs workspace secret ID, not its secret value.")
    if not 60 <= max_seconds <= 600:
        raise ValueError("Choose a maximum duration between 60 and 600 seconds.")
    if tool_ids and (len(tool_ids) != 4 or len(set(tool_ids)) != 4 or any(not item for item in tool_ids)):
        raise ValueError("Supply four distinct tool IDs in the documented tool order.")
    replacements = {"__HEARTH_VOICE_PUBLIC_URL__": public_url.rstrip("/"), "__HEARTH_WORKSPACE_SECRET_ID__": secret_id}
    template = json.loads((ROOT / "docs/elevenlabs-tools.template.json").read_text())

    def replace(value):
        if isinstance(value, dict):
            return {key: replace(item) for key, item in value.items()}
        if isinstance(value, list):
            return [replace(item) for item in value]
        if isinstance(value, str):
            for old, new in replacements.items():
                value = value.replace(old, new)
        return value

    files = {f"{name}.json": replace(template[name]) for name in TOOL_NAMES}
    agent = json.loads((ROOT / "docs/elevenlabs-agent.template.json").read_text())
    agent["conversation_config"]["agent"]["prompt"]["prompt"] = (ROOT / "docs/elevenlabs-agent-prompt.md").read_text().strip()
    agent["conversation_config"]["conversation"]["max_duration_seconds"] = max_seconds
    if tool_ids:
        agent["conversation_config"]["agent"]["prompt"]["tool_ids"] = tool_ids
        files["agent.patch.json"] = agent
    return files


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--public-url", required=True, help="HTTPS origin pointing only to gateway port 8001")
    parser.add_argument("--secret-id", required=True, help="ElevenLabs workspace secret ID (never its value)")
    parser.add_argument("--tool-ids", nargs=4, metavar="ID", help="lookup_property, check_open_jobs, lookup_maintenance_context, prepare_repair_draft IDs")
    parser.add_argument("--max-seconds", type=int, default=600)
    parser.add_argument("--output-dir", type=Path, default=Path("/tmp/hearth-elevenlabs-config"))
    args = parser.parse_args()
    try:
        files = render(args.public_url, args.secret_id, args.tool_ids or [], args.max_seconds)
    except ValueError as error:
        parser.error(str(error))
    args.output_dir.mkdir(parents=True, exist_ok=True, mode=0o700)
    for name, payload in files.items():
        destination = args.output_dir / name
        destination.write_text(json.dumps(payload, indent=2) + "\n")
        destination.chmod(0o600)
        print(f"Prepared {destination}")
    if not args.tool_ids:
        print("Agent payload omitted until the four real workspace tool IDs are supplied.")
    print("Local files only. No account settings changed and no API key was read.")


if __name__ == "__main__":
    main()
