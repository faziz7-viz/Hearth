#!/usr/bin/env python3
"""Explicitly configure one dedicated Hearth agent from local secrets and reviewed templates."""

import argparse
import hashlib
import json
import os
from pathlib import Path
import re
import ssl
import tempfile
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import HTTPRedirectHandler, HTTPSHandler, Request, build_opener

from elevenlabs_config import ROOT, TOOL_NAMES, render
from elevenlabs_setup import read_local, validate_value

STATE_PATH = ROOT / "backend/data/elevenlabs-setup.json"


class SetupError(Exception):
    """Only controlled, non-secret messages may reach the terminal."""


class NoRedirects(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class ElevenLabsAPI:
    def __init__(self, api_key: str):
        self.api_key = api_key
        try:
            import truststore
            context = truststore.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        except ImportError:
            context = ssl.create_default_context()
        self.opener = build_opener(HTTPSHandler(context=context), NoRedirects())

    def request(self, method: str, path: str, payload=None) -> dict:
        if not path.startswith("/v1/convai/") or "\n" in path:
            raise SetupError("Only the official ElevenLabs Agents API is allowed.")
        request = Request(
            "https://api.elevenlabs.io" + path,
            data=json.dumps(payload).encode() if payload is not None else None,
            headers={"xi-api-key": self.api_key, "Content-Type": "application/json"},
            method=method,
        )
        try:
            with self.opener.open(request, timeout=15) as response:
                return json.loads(response.read(2_000_000))
        except HTTPError as error:
            raise SetupError(f"ElevenLabs returned HTTP {error.code}. Check local key permissions, account access, and the reviewed payload. Response details were not printed.") from None
        except (URLError, TimeoutError, OSError, ValueError):
            raise SetupError("ElevenLabs could not be reached securely or returned invalid data. Saved setup IDs were retained; retry the same command. No secret values were printed.") from None

    def list_items(self, resource: str, key: str, search: str = "") -> list[dict]:
        items, cursor = [], None
        for _ in range(20):
            query = {"page_size": 100}
            if search:
                query["search"] = search
            if cursor:
                query["cursor"] = cursor
            page = self.request("GET", f"/v1/convai/{resource}?{urlencode(query)}")
            items.extend(page.get(key, []))
            cursor = page.get("next_cursor")
            if not cursor:
                return items
        raise SetupError("The workspace has too many pages to reconcile safely. No further changes were made.")


def identifier(value: str) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9_-]{1,200}", value):
        raise SetupError("A configured resource ID is invalid. Check the local ID, not its secret value.")
    return value


def save_state(state: dict, path: Path = STATE_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.is_symlink():
        raise SetupError("The local setup state must be a regular file.")
    descriptor, name = tempfile.mkstemp(prefix=".elevenlabs-setup-", dir=path.parent)
    try:
        with os.fdopen(descriptor, "w") as handle:
            json.dump(state, handle, indent=2)
            handle.write("\n")
        os.chmod(name, 0o600)
        os.replace(name, path)
    finally:
        Path(name).unlink(missing_ok=True)


def read_state(agent_id: str, path: Path = STATE_PATH) -> dict:
    if path.is_symlink():
        raise SetupError("The local setup state must be a regular file.")
    state = json.loads(path.read_text()) if path.exists() else {"agent_id": agent_id, "tools": {}}
    if state.get("agent_id") != agent_id:
        raise SetupError("Existing setup IDs belong to another agent. Keep this dedicated agent or review the local setup state before switching.")
    return state


def blank_workflow(workflow) -> bool:
    """Accept no workflow or ElevenLabs' one inert default start node only."""
    if workflow is None:
        return True
    if not isinstance(workflow, dict) or set(workflow) - {"nodes", "edges", "subgraphs", "prevent_subagent_loops"}:
        return False
    if "prevent_subagent_loops" in workflow and not isinstance(workflow["prevent_subagent_loops"], bool):
        return False
    if workflow.get("edges") or workflow.get("subgraphs"):
        return False
    nodes = workflow.get("nodes", {})
    if not isinstance(nodes, dict):
        return False
    if not nodes:
        return True
    if len(nodes) != 1:
        return False
    node = next(iter(nodes.values()))
    return (isinstance(node, dict) and node.get("type") == "start"
            and not (set(node) - {"type", "position", "edge_order", "parent_subgraph_id"})
            and node.get("edge_order", []) == [] and node.get("parent_subgraph_id") is None)


def provision(api: ElevenLabsAPI, values: dict[str, str], agent: dict, path: Path = STATE_PATH) -> dict:
    agent_id = identifier(values["ELEVENLABS_AGENT_ID"])
    # This helper intentionally refuses existing multi-node or procedure-driven agents.
    if not blank_workflow(agent.get("workflow")) or agent.get("procedures") or agent.get("phone_numbers") or agent.get("whatsapp_accounts"):
        raise SetupError("Use a new dedicated blank Hearth agent with no workflow, phone, WhatsApp, or procedures.")
    for key in ("HEARTH_WEBHOOK_SECRET", "HEARTH_VOICE_PUBLIC_URL", "HEARTH_VOICE_MAX_SECONDS"):
        validate_value(key, values[key])
    state = read_state(agent_id, path)
    fingerprint = hashlib.sha256(values["HEARTH_WEBHOOK_SECRET"].encode()).hexdigest()
    if state.get("secret_fingerprint") not in (None, fingerprint):
        raise SetupError("The local webhook secret changed. Review secret rotation before replacing the workspace credential.")
    if not state.get("secret_id"):
        # The name includes a fingerprint so a response lost before saving can be reconciled.
        secret_name = f"hearth-{agent_id}-{fingerprint[:12]}"
        candidates = [item for item in api.list_items("secrets", "secrets", secret_name) if item.get("name") == secret_name]
        if len(candidates) > 1:
            raise SetupError("More than one matching workspace secret exists. Review them before continuing.")
        secret = candidates[0] if candidates else api.request("POST", "/v1/convai/secrets", {
            "type": "new", "name": secret_name, "value": values["HEARTH_WEBHOOK_SECRET"],
        })
        state["secret_id"] = identifier(secret["secret_id"])
        state["secret_fingerprint"] = fingerprint
        save_state(state, path)
    secret_id = identifier(state["secret_id"])
    payloads = render(values["HEARTH_VOICE_PUBLIC_URL"], secret_id, [], int(values["HEARTH_VOICE_MAX_SECONDS"]))
    for name in TOOL_NAMES:
        payload = payloads[f"{name}.json"]
        # Disable test mocks explicitly so live requests always reach Hearth.
        payload["response_mocks"] = []
        tool_id = state["tools"].get(name)
        if tool_id:
            existing = api.request("GET", f"/v1/convai/tools/{identifier(tool_id)}")
            existing_config = existing.get("tool_config", {})
            existing_secret = existing_config.get("api_schema", {}).get("request_headers", {}).get("X-Hearth-Webhook-Secret", {})
            if existing_config.get("name") != name or existing_secret != {"secret_id": secret_id}:
                raise SetupError("A saved workspace tool no longer matches Hearth's credential and name. Review it before updating.")
        else:
            candidates = []
            for item in api.list_items("tools", "tools", name):
                config = item.get("tool_config", {})
                headers = config.get("api_schema", {}).get("request_headers", {})
                if config.get("name") == name and headers.get("X-Hearth-Webhook-Secret") == {"secret_id": secret_id}:
                    candidates.append(item)
            if len(candidates) > 1:
                raise SetupError("More than one matching Hearth tool exists. Review the duplicate tools before continuing.")
            if candidates:
                tool_id = identifier(candidates[0]["id"])
        if tool_id:
            api.request("PATCH", f"/v1/convai/tools/{identifier(tool_id)}", payload)
        else:
            result = api.request("POST", "/v1/convai/tools", payload)
            tool_id = identifier(result["id"])
        state["tools"][name] = tool_id
        save_state(state, path)
        print(f"Configured {name}.")
    tool_ids = [state["tools"][name] for name in TOOL_NAMES]
    payload = render(values["HEARTH_VOICE_PUBLIC_URL"], secret_id, tool_ids, int(values["HEARTH_VOICE_MAX_SECONDS"]))["agent.patch.json"]
    payload["version_description"] = "Hearth Milestone 4: four authenticated repair draft tools; approval stays in the app."
    api.request("PATCH", f"/v1/convai/agents/{agent_id}", payload)
    verified = api.request("GET", f"/v1/convai/agents/{agent_id}")
    configured_ids = verified.get("conversation_config", {}).get("agent", {}).get("prompt", {}).get("tool_ids", [])
    private = verified.get("platform_settings", {}).get("auth", {}).get("enable_auth")
    if set(configured_ids) != set(tool_ids) or private is not True:
        raise SetupError("The agent configuration did not verify. Keep voice disabled until its tool list and authentication are corrected.")
    state["public_url"] = values["HEARTH_VOICE_PUBLIC_URL"]
    state["configured"] = True
    save_state(state, path)
    return state


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    subcommands = parser.add_subparsers(dest="command", required=True)
    subcommands.add_parser("check-agent", help="Read agent accessibility only; no account changes")
    upload = subcommands.add_parser("provision", help="Upload one secret, four tools, and reviewed settings to a dedicated agent")
    upload.add_argument("--dedicated-agent-id", required=True, help="Must exactly match ELEVENLABS_AGENT_ID; this agent's prompt and tools will be replaced")
    args = parser.parse_args()
    try:
        _, local = read_local()
        values = {key: os.environ.get(key, local.get(key, "")) for key in (
            "ELEVENLABS_API_KEY", "ELEVENLABS_AGENT_ID", "HEARTH_WEBHOOK_SECRET", "HEARTH_VOICE_PUBLIC_URL", "HEARTH_VOICE_MAX_SECONDS",
        )}
        values["HEARTH_VOICE_MAX_SECONDS"] = values["HEARTH_VOICE_MAX_SECONDS"] or "600"
        if not values["ELEVENLABS_API_KEY"] or not values["ELEVENLABS_AGENT_ID"]:
            raise SetupError("Set the API key and dedicated agent ID locally first.")
        agent_id = identifier(values["ELEVENLABS_AGENT_ID"])
        api = ElevenLabsAPI(values["ELEVENLABS_API_KEY"])
        agent = api.request("GET", f"/v1/convai/agents/{agent_id}")
        if args.command == "check-agent":
            print("Agent is accessible with the locally configured key. No account settings changed.")
            print("Agents credits/minutes still need confirmation in your account's billing screen.")
        else:
            if args.dedicated_agent_id != agent_id:
                raise SetupError("The dedicated agent ID must match the local configuration exactly.")
            provision(api, values, agent)
            print("Dedicated Hearth agent configured and its private access/tool IDs verified. Live speech still needs testing.")
    except SetupError as error:
        parser.exit(1, str(error) + "\n")
    except (OSError, ValueError, KeyError, TypeError):
        parser.exit(1, "Setup stopped because local configuration or the API response was invalid. Saved IDs were retained. No secret values were printed.\n")


if __name__ == "__main__":
    main()
