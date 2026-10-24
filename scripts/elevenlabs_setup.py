#!/usr/bin/env python3
"""Keep ElevenLabs configuration in Hearth's local .env, without printing secrets."""

import argparse
import getpass
import json
import os
from pathlib import Path
import re
import secrets
import shlex
import tempfile
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / ".env"
KEYS = (
    "ELEVENLABS_API_KEY", "ELEVENLABS_AGENT_ID", "HEARTH_WEBHOOK_SECRET",
    "HEARTH_VOICE_PUBLIC_URL", "HEARTH_VOICE_MAX_SECONDS",
)
ASSIGNMENT = re.compile(r"^\s*(?:export\s+)?([A-Za-z_][A-Za-z_0-9]*)\s*=(.*)$")


def read_local(path: Path = ENV_PATH) -> tuple[str, dict[str, str]]:
    if path.is_symlink():
        raise ValueError("Use a regular local .env file, not a symbolic link.")
    text = path.read_text() if path.exists() else ""
    values = {}
    for line in text.splitlines():
        match = ASSIGNMENT.match(line)
        if match and match.group(1) in KEYS:
            parts = shlex.split(match.group(2), comments=True)
            if len(parts) > 1:
                raise ValueError("A voice configuration value contains unquoted spaces. Quote it locally.")
            values[match.group(1)] = parts[0] if parts else ""
    return text, values


def save_values(changes: dict[str, str], path: Path = ENV_PATH) -> None:
    original, _ = read_local(path)
    lines, used = [], set()
    for line in original.splitlines():
        match = ASSIGNMENT.match(line)
        key = match.group(1) if match else None
        if key in changes:
            if key not in used:
                lines.append(f"{key}={json.dumps(changes[key])}")
                used.add(key)
        else:
            lines.append(line)
    for key, value in changes.items():
        if key not in used:
            lines.append(f"{key}={json.dumps(value)}")
    descriptor, temporary_name = tempfile.mkstemp(prefix=".env.", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w") as temporary:
            temporary.write("\n".join(lines) + "\n")
        os.chmod(temporary_name, 0o600)
        os.replace(temporary_name, path)
    finally:
        Path(temporary_name).unlink(missing_ok=True)


def validate_value(key: str, value: str) -> None:
    if not value.strip() or "\n" in value or "\r" in value:
        raise ValueError("Enter one nonempty value locally.")
    if key == "HEARTH_WEBHOOK_SECRET" and len(value) < 32:
        raise ValueError("The webhook secret must have at least 32 characters.")
    if key == "HEARTH_VOICE_PUBLIC_URL":
        parsed = urlsplit(value)
        if (parsed.scheme != "https" or not parsed.hostname or parsed.username or parsed.password
                or parsed.path not in ("", "/") or parsed.query or parsed.fragment):
            raise ValueError("Enter the HTTPS gateway origin only, without a path or credentials.")
    if key == "HEARTH_VOICE_MAX_SECONDS" and (not value.isdigit() or not 60 <= int(value) <= 600):
        raise ValueError("The demo maximum duration must be between 60 and 600 seconds.")


def initialize(path: Path = ENV_PATH) -> None:
    _, existing = read_local(path)
    changes = {key: "" for key in KEYS if key not in existing}
    if not existing.get("HEARTH_WEBHOOK_SECRET"):
        changes["HEARTH_WEBHOOK_SECRET"] = secrets.token_urlsafe(48)
    if not existing.get("HEARTH_VOICE_MAX_SECONDS"):
        changes["HEARTH_VOICE_MAX_SECONDS"] = "600"
    save_values(changes, path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subcommands = parser.add_subparsers(dest="command", required=True)
    subcommands.add_parser("init", help="Create missing entries and a random webhook secret; preserve existing values")
    subcommands.add_parser("check", help="Report configured/missing only; never display values")
    setter = subcommands.add_parser("set", help="Enter one value with hidden input in your local terminal")
    setter.add_argument("key", choices=KEYS)
    args = parser.parse_args()
    try:
        if args.command == "init":
            initialize()
            print("Local .env prepared with private permissions. Existing values were preserved.")
        elif args.command == "set":
            value = getpass.getpass(f"Enter {args.key} locally (hidden): ").strip()
            validate_value(args.key, value)
            save_values({args.key: value})
            print(f"Saved {args.key} locally. Restart Hearth's backend and gateway to load it.")
        else:
            _, values = read_local()
            for key in KEYS:
                effective = os.environ.get(key, values.get(key, ""))
                print(f"{key}: {'configured' if effective.strip() else 'missing'}")
    except (OSError, ValueError) as error:
        # Do not print exception text from file contents, network calls, or secret input.
        parser.exit(1, "Could not update or check local configuration. Check the file permissions and value format. No values were printed.\n")


if __name__ == "__main__":
    main()
