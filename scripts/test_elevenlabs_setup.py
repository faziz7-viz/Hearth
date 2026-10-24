"""Offline checks for config boundaries and restart-safe account provisioning."""

import copy
import json
from pathlib import Path
import tempfile
import unittest

from elevenlabs_config import TOOL_NAMES, render
from elevenlabs_provision import SetupError, provision
from elevenlabs_setup import initialize, read_local, save_values


class FakeAccount:
    def __init__(self):
        self.secrets = []
        self.tools = []
        self.agent = {"agent_id": "agent_hearth", "workflow": None}
        self.lose_create_response_once = True
        self.create_calls = {"secrets": 0, "tools": 0}

    def list_items(self, resource, key, search=""):
        return copy.deepcopy(getattr(self, resource))

    def request(self, method, path, payload=None):
        if path == "/v1/convai/secrets" and method == "POST":
            self.create_calls["secrets"] += 1
            result = {"secret_id": "secret_hearth", "name": payload["name"], "type": "stored"}
            self.secrets.append(result)
            return copy.deepcopy(result)
        if path == "/v1/convai/tools" and method == "POST":
            self.create_calls["tools"] += 1
            result = {"id": f"tool_{len(self.tools) + 1}", **copy.deepcopy(payload)}
            self.tools.append(result)
            if len(self.tools) == 3 and self.lose_create_response_once:
                self.lose_create_response_once = False
                raise SetupError("Simulated lost response after server create")
            return copy.deepcopy(result)
        if path.startswith("/v1/convai/tools/"):
            tool = next(item for item in self.tools if item["id"] == path.split("/")[-1])
            if method == "PATCH":
                tool.update(copy.deepcopy(payload))
            return copy.deepcopy(tool)
        if path == "/v1/convai/agents/agent_hearth":
            if method == "PATCH":
                self.agent.update(copy.deepcopy(payload))
            return copy.deepcopy(self.agent)
        raise AssertionError((method, path))


class SetupTests(unittest.TestCase):
    def test_init_preserves_existing_values_and_secret_on_repeat(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / ".env"
            path.write_text('ELEVENLABS_API_KEY="local-test-value"\nUNRELATED="keep me"\n')
            initialize(path)
            first_text, first = read_local(path)
            initialize(path)
            second_text, second = read_local(path)
            self.assertEqual(first, second)
            self.assertEqual(first_text, second_text)
            self.assertEqual(first["ELEVENLABS_API_KEY"], "local-test-value")
            self.assertIn('UNRELATED="keep me"', second_text)
            self.assertGreaterEqual(len(first["HEARTH_WEBHOOK_SECRET"]), 32)
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_local_update_replaces_duplicate_key_without_touching_other_values(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / ".env"
            path.write_text('ELEVENLABS_AGENT_ID=old\nOTHER=kept\nELEVENLABS_AGENT_ID=also_old\n')
            save_values({"ELEVENLABS_AGENT_ID": "agent_hearth"}, path)
            content, values = read_local(path)
            self.assertEqual(content.count("ELEVENLABS_AGENT_ID="), 1)
            self.assertIn("OTHER=kept", content)
            self.assertEqual(values["ELEVENLABS_AGENT_ID"], "agent_hearth")

    def test_exact_tools_have_three_auth_headers_and_no_approval_or_mocks(self):
        rendered = render("https://hearth.example", "secret_workspace", [], 600)
        self.assertEqual(set(rendered), {f"{name}.json" for name in TOOL_NAMES})
        for name in TOOL_NAMES:
            payload = rendered[f"{name}.json"]
            config = payload["tool_config"]
            self.assertEqual(payload["response_mocks"], [])
            self.assertEqual(config["response_timeout_secs"], 20)
            self.assertEqual(config["execution_mode"], "immediate")
            self.assertEqual(config["interruption_mode"], "allow")
            schema = config["api_schema"]
            self.assertEqual(schema["url"], f"https://hearth.example/voice/tools/{name}")
            self.assertEqual(schema["request_headers"], {
                "X-Hearth-Webhook-Secret": {"secret_id": "secret_workspace"},
                "X-Hearth-Binding": {"variable_name": "secret__hearth_binding"},
                "X-ElevenLabs-Conversation-Id": {"variable_name": "system__conversation_id"},
            })
            self.assertNotIn("session_id", schema["request_body_schema"]["properties"])
        prepare = rendered["prepare_repair_draft.json"]["tool_config"]["api_schema"]["request_body_schema"]
        self.assertEqual(prepare["required"], ["draft_id", "expected_revision", "fields"])
        self.assertEqual(prepare["properties"]["draft_id"]["type"], ["string", "null"])
        self.assertEqual(prepare["properties"]["expected_revision"]["type"], "integer")
        self.assertNotIn("status", prepare["properties"]["fields"]["properties"])

    def test_agent_only_allows_text_mode_override_and_has_no_extra_tools(self):
        ids = ["tool_1", "tool_2", "tool_3", "tool_4"]
        agent = render("https://hearth.example", "secret_workspace", ids, 300)["agent.patch.json"]
        self.assertTrue(agent["platform_settings"]["auth"]["enable_auth"])
        self.assertEqual(agent["platform_settings"]["auth"]["allowlist"], [])
        privacy = agent["platform_settings"]["privacy"]
        self.assertTrue(privacy.get("delete_transcript_and_pii", False))
        self.assertEqual(privacy["retention_days"], 7)
        overrides = agent["platform_settings"]["overrides"]["conversation_config_override"]
        self.assertEqual(overrides["conversation"], {"text_only": True, "max_duration_seconds": False})
        self.assertFalse(any(overrides["agent"]["prompt"].values()))
        prompt = agent["conversation_config"]["agent"]["prompt"]
        self.assertEqual(prompt["tool_ids"], ids)
        self.assertFalse(prompt["enable_parallel_tool_calls"])
        enabled_system_tools = {name: config for name, config in prompt["built_in_tools"].items() if config is not None}
        self.assertEqual(set(enabled_system_tools), {"end_call"})
        end_call = enabled_system_tools["end_call"]
        self.assertEqual(end_call["type"], "system")
        self.assertEqual(end_call["name"], "end_call")
        self.assertEqual(end_call["params"], {"system_tool_type": "end_call"})
        self.assertTrue(end_call["description"].strip())
        self.assertEqual(prompt["mcp_server_ids"], [])
        self.assertIn("{{hearth_context}}", prompt["prompt"])
        self.assertEqual(agent["conversation_config"]["conversation"]["max_duration_seconds"], 300)

    def test_native_closing_tool_disables_interruptions_without_pre_tool_speech(self):
        agent = render("https://hearth.example", "secret_workspace", ["tool_1", "tool_2", "tool_3", "tool_4"], 300)["agent.patch.json"]
        end_call = agent["conversation_config"]["agent"]["prompt"]["built_in_tools"]["end_call"]
        self.assertEqual(end_call.get("interruption_mode"), "disable_during_tool_and_turn")
        self.assertEqual(end_call.get("pre_tool_speech"), "off")

    def test_render_rejects_non_https_credentials_paths_and_duplicate_tools(self):
        for url in ("http://localhost:8000", "https://secret@demo.example", "https://demo.example/api", "https://demo.example?key=x"):
            with self.subTest(url=url), self.assertRaises(ValueError):
                render(url, "secret_id", [], 600)
        with self.assertRaises(ValueError):
            render("https://demo.example", "secret_id", ["same"] * 4, 600)

    def test_provision_recovers_lost_create_response_without_duplicate_tools(self):
        account = FakeAccount()
        values = {
            "ELEVENLABS_AGENT_ID": "agent_hearth", "HEARTH_WEBHOOK_SECRET": "fixture-only-secret-" * 3,
            "HEARTH_VOICE_PUBLIC_URL": "https://hearth.example", "HEARTH_VOICE_MAX_SECONDS": "600",
        }
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "setup.json"
            with self.assertRaises(SetupError):
                provision(account, values, account.agent, path)
            result = provision(account, values, account.agent, path)
            provision(account, values, account.agent, path)
            self.assertEqual(account.create_calls, {"secrets": 1, "tools": 4})
            self.assertEqual(set(result["tools"]), set(TOOL_NAMES))
            self.assertTrue(result["configured"])
            self.assertNotIn(values["HEARTH_WEBHOOK_SECRET"], path.read_text())
            self.assertEqual(path.stat().st_mode & 0o777, 0o600)

    def test_provision_refuses_existing_workflow_before_account_writes(self):
        account = FakeAccount()
        with self.assertRaises(SetupError):
            provision(account, {"ELEVENLABS_AGENT_ID": "agent_hearth"}, {"workflow": {"nodes": {"existing": {}}}})
        self.assertEqual(account.create_calls, {"secrets": 0, "tools": 0})

    def test_provision_accepts_default_inert_start_node(self):
        account = FakeAccount()
        account.lose_create_response_once = False
        account.agent["workflow"] = {
            "nodes": {"start": {"type": "start", "position": {"x": 0, "y": 0},
                                  "edge_order": [], "parent_subgraph_id": None}},
            "edges": {}, "subgraphs": {}, "prevent_subagent_loops": False,
        }
        values = {
            "ELEVENLABS_AGENT_ID": "agent_hearth", "HEARTH_WEBHOOK_SECRET": "fixture-only-secret-" * 3,
            "HEARTH_VOICE_PUBLIC_URL": "https://hearth.example", "HEARTH_VOICE_MAX_SECONDS": "600",
        }
        with tempfile.TemporaryDirectory() as folder:
            result = provision(account, values, account.agent, Path(folder) / "setup.json")
        self.assertTrue(result["configured"])
        self.assertEqual(account.agent["name"], "Hearth Demo")

    def test_provision_refuses_nontrivial_start_node_variants(self):
        start = {"type": "start", "position": {"x": 0, "y": 0}, "edge_order": [], "parent_subgraph_id": None}
        variants = [
            {"nodes": {"start": {**start, "edge_order": ["edge"]}}, "edges": {}},
            {"nodes": {"start": start}, "edges": {"edge": {"target": "tool"}}},
            {"nodes": {"start": start}, "subgraphs": {"nested": {}}},
            {"nodes": {"start": {**start, "parent_subgraph_id": "nested"}}},
            {"nodes": {"start": start, "tool": {"type": "tool"}}},
            {"nodes": {"start": {**start, "tools": ["tool_1"]}}},
            {"nodes": {"start": start}, "prevent_subagent_loops": "unexpected"},
        ]
        for workflow in variants:
            with self.subTest(workflow=workflow):
                account = FakeAccount()
                with self.assertRaises(SetupError):
                    provision(account, {"ELEVENLABS_AGENT_ID": "agent_hearth"}, {"workflow": workflow})
                self.assertEqual(account.create_calls, {"secrets": 0, "tools": 0})


if __name__ == "__main__":
    unittest.main()
