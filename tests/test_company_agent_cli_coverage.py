from __future__ import annotations

import pytest
import responses as rsps

from .cli_test_helpers import BASE_URL, request_json, run_cli


@rsps.activate
def test_company_commands_cover_table_empty_and_confirmation(runner):
    rsps.add(rsps.GET, f"{BASE_URL}/api/companies", json={"data": [{"id": "c1", "name": "Acme", "description": "Widgets"}]})
    rsps.add(rsps.GET, f"{BASE_URL}/api/companies", json=[])
    rsps.add(rsps.POST, f"{BASE_URL}/api/companies", json={"id": "c2", "name": "Beta"}, status=201)
    rsps.add(rsps.GET, f"{BASE_URL}/api/companies/c1", json={"id": "c1", "name": "Acme"})
    rsps.add(rsps.PATCH, f"{BASE_URL}/api/companies/c1", json={"id": "c1", "name": "Renamed"})
    rsps.add(rsps.POST, f"{BASE_URL}/api/companies/c1/archive", json={"ok": True})

    list_result = run_cli(runner, "company", "list")
    assert list_result.exit_code == 0
    assert "Acme" in list_result.output

    empty_result = run_cli(runner, "company", "list")
    assert empty_result.exit_code == 0
    assert "No companies found." in empty_result.output

    create_result = run_cli(runner, "company", "create", "--name", "Beta", "--description", "Desc", "--mission", "Grow")
    assert create_result.exit_code == 0
    assert "Created company" in create_result.output
    assert request_json(rsps.calls[2]) == {"name": "Beta", "description": "Desc", "mission": "Grow"}

    get_result = run_cli(runner, "company", "get", "c1")
    assert get_result.exit_code == 0
    assert '"id": "c1"' in get_result.output

    update_result = run_cli(runner, "company", "update", "c1", "--name", "Renamed", "--description", "Fresh", "--mission", "Win")
    assert update_result.exit_code == 0
    assert "Updated company c1" in update_result.output
    assert request_json(rsps.calls[4]) == {"name": "Renamed", "description": "Fresh", "mission": "Win"}

    delete_result = run_cli(runner, "company", "delete", "c1", input="y\n")
    assert delete_result.exit_code == 0
    assert "Archived company c1" in delete_result.output

@rsps.activate
def test_agent_commands_cover_payloads_and_runtime_updates(runner):
    rsps.add(rsps.GET, f"{BASE_URL}/api/companies/co1/agents", json={"data": [{"id": "a1", "name": "Alice", "jobTitle": "CTO", "runtimeState": "idle"}]})
    rsps.add(rsps.GET, f"{BASE_URL}/api/companies/co1/agents", json=[])
    rsps.add(rsps.POST, f"{BASE_URL}/api/companies/co1/agents", json={"id": "a1", "name": "CEO"}, status=201)
    rsps.add(rsps.POST, f"{BASE_URL}/api/companies/co1/agents", json={"id": "a2", "name": "Ops"}, status=201)
    rsps.add(rsps.POST, f"{BASE_URL}/api/companies/co1/agents", json={"id": "a3", "name": "Coder"}, status=201)
    rsps.add(rsps.GET, f"{BASE_URL}/api/agents/a1", json={"id": "a1", "name": "CEO"})
    rsps.add(rsps.PATCH, f"{BASE_URL}/api/agents/a1", json={"id": "a1", "name": "CEO 2"})
    rsps.add(rsps.DELETE, f"{BASE_URL}/api/agents/a1", status=204)
    rsps.add(rsps.POST, f"{BASE_URL}/api/agents/a1/wakeup", json={"ok": True})
    rsps.add(rsps.PATCH, f"{BASE_URL}/api/agents/a1/instructions-path", json={"path": "/tmp/AGENTS.md"})

    list_result = run_cli(runner, "agent", "list", "--company", "co1")
    assert list_result.exit_code == 0
    assert "Alice" in list_result.output
    assert "CTO" in list_result.output

    empty_result = run_cli(runner, "agent", "list", "--company", "co1")
    assert empty_result.exit_code == 0
    assert "No agents found." in empty_result.output

    ceo_result = run_cli(
        runner,
        "agent",
        "create",
        "--company",
        "co1",
        "--name",
        "CEO",
        "--role",
        "ceo",
        "--title",
        "Chief Executive Officer",
        "--cwd",
        "/tmp/work",
        "--effort",
        "high",
    )
    assert ceo_result.exit_code == 0
    ceo_payload = request_json(rsps.calls[2])
    assert ceo_payload["title"] == "Chief Executive Officer"
    assert ceo_payload["adapterConfig"]["model"] == "claude-opus-4-6"
    assert ceo_payload["adapterConfig"]["cwd"] == "/tmp/work"
    assert ceo_payload["adapterConfig"]["effort"] == "high"

    opencode_result = run_cli(
        runner,
        "agent",
        "create",
        "--company",
        "co1",
        "--name",
        "Ops",
        "--adapter",
        "opencode_local",
        "--cwd",
        "/tmp/repo",
        "--max-turns",
        "12",
    )
    assert opencode_result.exit_code == 0
    opencode_payload = request_json(rsps.calls[3])
    assert opencode_payload["runtimeConfig"] == {"maxTurnsPerRun": 12, "cwd": "/tmp/repo"}
    assert opencode_payload["adapterConfig"] == {"model": "anthropic/claude-sonnet-4-6"}

    codex_result = run_cli(
        runner,
        "agent",
        "create",
        "--company",
        "co1",
        "--name",
        "Coder",
        "--adapter",
        "codex_local",
        "--cwd",
        "/tmp/codex",
        "--max-turns",
        "7",
        "--runtime-config",
        '{"trace": true}',
        "--adapter-config",
        '{"sandbox":"workspace-write"}',
        "--json",
    )
    assert codex_result.exit_code == 0
    codex_payload = request_json(rsps.calls[4])
    assert codex_payload["runtimeConfig"] == {"maxTurnsPerRun": 7, "cwd": "/tmp/codex", "trace": True}
    assert codex_payload["adapterConfig"] == {"sandbox": "workspace-write"}

    get_result = run_cli(runner, "agent", "get", "a1")
    assert get_result.exit_code == 0
    assert '"name": "CEO"' in get_result.output

    update_result = run_cli(
        runner,
        "agent",
        "update",
        "a1",
        "--name",
        "CEO 2",
        "--title",
        "Lead",
        "--role",
        "ceo",
        "--reports-to",
        "a9",
        "--budget",
        "5000",
        "--adapter",
        "claude_local",
        "--model",
        "claude-haiku-4-6",
        "--max-turns",
        "15",
        "--cwd",
        "/tmp/agent",
        "--effort",
        "medium",
        "--runtime-config",
        '{"trace": "verbose"}',
    )
    assert update_result.exit_code == 0
    update_payload = request_json(rsps.calls[6])
    assert update_payload["budgetMonthlyCents"] == 5000
    assert update_payload["runtimeConfig"] == {
        "model": "claude-haiku-4-6",
        "maxTurnsPerRun": 15,
        "cwd": "/tmp/agent",
        "effort": "medium",
        "trace": "verbose",
    }

    delete_result = run_cli(runner, "agent", "delete", "a1", input="y\n")
    assert delete_result.exit_code == 0
    assert "Deleted agent a1" in delete_result.output

    wakeup_result = run_cli(runner, "agent", "wakeup", "a1")
    assert wakeup_result.exit_code == 0
    assert "Woke up agent a1" in wakeup_result.output

    instructions_result = run_cli(runner, "agent", "set-instructions", "a1", "--path", "/tmp/AGENTS.md")
    assert instructions_result.exit_code == 0
    assert "Set instructions path for a1" in instructions_result.output

def test_agent_rejects_invalid_json_options(runner):
    create_runtime = run_cli(
        runner,
        "agent",
        "create",
        "--company",
        "co1",
        "--name",
        "Broken",
        "--runtime-config",
        "{bad",
    )
    assert create_runtime.exit_code == 1
    assert "--runtime-config is not valid JSON" in create_runtime.output

    create_adapter = run_cli(
        runner,
        "agent",
        "create",
        "--company",
        "co1",
        "--name",
        "Broken",
        "--adapter-config",
        "{bad",
    )
    assert create_adapter.exit_code == 1
    assert "--adapter-config is not valid JSON" in create_adapter.output

    update_result = run_cli(runner, "agent", "update", "a1", "--runtime-config", "{bad")
    assert update_result.exit_code == 1
    assert "--runtime-config invalid JSON" in update_result.output
