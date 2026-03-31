"""Additional CLI coverage tests."""

from __future__ import annotations

import json

import pytest
import responses as rsps
from click.testing import CliRunner

from paperclip_cli import cli as cli_module
from paperclip_cli import client as client_module
from paperclip_cli.cli import cli
from paperclip_cli.client import PaperclipClient, PaperclipError


BASE_URL = "http://localhost:3100"


def run_cli(runner: CliRunner, *args: str, **kwargs):
    return runner.invoke(cli, ["--url", BASE_URL, *args], **kwargs)


def request_json(call) -> dict:
    body = call.request.body
    if isinstance(body, bytes):
        body = body.decode()
    return json.loads(body) if body else {}


@pytest.fixture
def runner():
    return CliRunner()


@pytest.mark.parametrize(
    "command",
    ["agent", "company", "goal", "heartbeat", "issue", "plugin", "project", "routine", "secret"],
)
def test_group_without_subcommand_shows_help(runner, command):
    result = run_cli(runner, command)
    assert result.exit_code == 0
    assert "Usage:" in result.output


def test_cli_configure_writes_config_and_client_reads_it(runner, monkeypatch, tmp_path):
    config_path = tmp_path / "config.json"
    monkeypatch.setattr(cli_module, "CONFIG_PATH", config_path)
    monkeypatch.setattr(client_module, "CONFIG_PATH", config_path)

    result = runner.invoke(cli, ["configure", "--url", f"{BASE_URL}/", "--token", "secret-token"])
    assert result.exit_code == 0
    assert "Configuration saved" in result.output
    assert "Token: ****" in result.output

    saved = json.loads(config_path.read_text())
    assert saved == {"base_url": BASE_URL, "token": "secret-token"}

    client = PaperclipClient()
    assert client.base_url == BASE_URL
    assert client.token == "secret-token"


def test_configure_ignores_invalid_existing_config(runner, monkeypatch, tmp_path):
    config_path = tmp_path / "config.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text("{invalid json")
    monkeypatch.setattr(cli_module, "CONFIG_PATH", config_path)

    result = runner.invoke(cli, ["configure", "--url", f"{BASE_URL}/"])
    assert result.exit_code == 0

    saved = json.loads(config_path.read_text())
    assert saved == {"base_url": BASE_URL}


def test_client_defaults_when_config_is_invalid(monkeypatch, tmp_path):
    config_path = tmp_path / "config.json"
    config_path.write_text("{broken")
    monkeypatch.setattr(client_module, "CONFIG_PATH", config_path)

    client = PaperclipClient()
    assert client.base_url == client_module.DEFAULT_URL
    assert client.token == ""
    assert client._headers() == {"Content-Type": "application/json"}


@rsps.activate
def test_client_handles_204_and_text_errors(monkeypatch, tmp_path):
    config_path = tmp_path / "config.json"
    config_path.write_text(json.dumps({"base_url": BASE_URL, "token": "cfg-token"}))
    monkeypatch.setattr(client_module, "CONFIG_PATH", config_path)

    client = PaperclipClient()

    rsps.add(rsps.POST, f"{BASE_URL}/api/plugins/install", status=204)
    rsps.add(rsps.PATCH, f"{BASE_URL}/api/projects/p1", status=204)
    rsps.add(rsps.DELETE, f"{BASE_URL}/api/issues/i1", status=204)
    rsps.add(rsps.GET, f"{BASE_URL}/api/plugins", body="boom", status=500)

    assert client.post("/plugins/install", {"name": "x"}) == {}
    assert client.patch("/projects/p1", {"name": "x"}) == {}
    assert client.delete("/issues/i1") == {}
    assert rsps.calls[0].request.headers["Authorization"] == "Bearer cfg-token"

    with pytest.raises(PaperclipError) as exc_info:
        client.get("/plugins")
    assert exc_info.value.status_code == 500
    assert str(exc_info.value) == "HTTP 500: boom"


@rsps.activate
def test_status_success_and_paperclip_error_output(runner):
    rsps.add(rsps.GET, f"{BASE_URL}/api/health", json={"version": "1.2.3"})
    rsps.add(rsps.GET, f"{BASE_URL}/api/health", json={"error": "down"}, status=503)

    ok_result = run_cli(runner, "status")
    assert ok_result.exit_code == 0
    assert "Paperclip is running" in ok_result.output
    assert '"version": "1.2.3"' in ok_result.output

    error_result = run_cli(runner, "status")
    assert error_result.exit_code == 1
    assert "Paperclip is not reachable" in error_result.output
    assert "HTTP 503: down" in error_result.output


def test_status_handles_unexpected_exceptions_in_json_and_text(runner, monkeypatch):
    monkeypatch.setattr(PaperclipClient, "health", lambda self: (_ for _ in ()).throw(RuntimeError("boom")))

    json_result = run_cli(runner, "status", "--json")
    assert json_result.exit_code == 1
    assert json.loads(json_result.output)["error"] == "boom"

    text_result = run_cli(runner, "status")
    assert text_result.exit_code == 1
    assert "Could not connect" in text_result.output
    assert "boom" in text_result.output


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


@rsps.activate
def test_goal_issue_approval_plugin_heartbeat_and_secret_commands(runner):
    rsps.add(rsps.GET, f"{BASE_URL}/api/companies/co1/goals", json={"data": [{"id": "g1", "title": "Launch", "status": "active"}]})
    rsps.add(rsps.GET, f"{BASE_URL}/api/companies/co1/goals", json=[])
    rsps.add(rsps.POST, f"{BASE_URL}/api/companies/co1/goals", json={"id": "g2", "title": "Scale"}, status=201)
    rsps.add(rsps.GET, f"{BASE_URL}/api/goals/g1", json={"id": "g1", "title": "Launch"})
    rsps.add(rsps.PATCH, f"{BASE_URL}/api/goals/g1", json={"id": "g1", "title": "Expand"})
    rsps.add(rsps.DELETE, f"{BASE_URL}/api/goals/g1", status=204)
    rsps.add(rsps.GET, f"{BASE_URL}/api/companies/co1/issues", json={"data": [{"id": "i1", "title": "Ship", "status": "todo", "assigneeUserId": "u1"}]})
    rsps.add(rsps.GET, f"{BASE_URL}/api/companies/co1/issues", json=[])
    rsps.add(rsps.POST, f"{BASE_URL}/api/companies/co1/issues", json={"id": "i2", "title": "Test"}, status=201)
    rsps.add(rsps.PATCH, f"{BASE_URL}/api/issues/i1", json={"id": "i1", "status": "done"})
    rsps.add(rsps.DELETE, f"{BASE_URL}/api/issues/i1", status=204)
    rsps.add(rsps.GET, f"{BASE_URL}/api/issues/i1", json={"id": "i1", "title": "Ship"})
    rsps.add(rsps.GET, f"{BASE_URL}/api/companies/co1/approvals", json={"data": [{"id": "ap1", "type": "budget", "status": "pending", "requestedByAgentId": "a1"}]})
    rsps.add(rsps.GET, f"{BASE_URL}/api/companies/co1/approvals", json=[])
    rsps.add(rsps.POST, f"{BASE_URL}/api/approvals/ap1/approve", json={"ok": True})
    rsps.add(rsps.POST, f"{BASE_URL}/api/approvals/ap1/reject", json={"ok": True})
    rsps.add(rsps.GET, f"{BASE_URL}/api/plugins", json={"data": [{"name": "clock", "version": "1.0", "description": "Time"}]})
    rsps.add(rsps.GET, f"{BASE_URL}/api/plugins", json=[])
    rsps.add(rsps.GET, f"{BASE_URL}/api/plugins/examples", json={"data": [{"name": "starter", "description": "Example"}]})
    rsps.add(rsps.GET, f"{BASE_URL}/api/plugins/examples", json=[])
    rsps.add(rsps.POST, f"{BASE_URL}/api/plugins/install", json={"ok": True})
    rsps.add(rsps.GET, f"{BASE_URL}/api/companies/co1/heartbeat-runs", json={"runs": [
        {
            "id": "run-success",
            "agentId": "agent-1",
            "status": "success",
            "invocationSource": "cron",
            "triggerDetail": "daily",
            "startedAt": "2026-03-30T00:00:00.000Z",
        },
        {
            "id": "run-failed",
            "agentId": "agent-2",
            "status": "failed",
            "invocationSource": "manual",
            "triggerDetail": "retry",
            "startedAt": "2026-03-30T01:00:00.000Z",
        },
    ]})
    rsps.add(rsps.GET, f"{BASE_URL}/api/companies/co1/heartbeat-runs", json={"runs": []})
    rsps.add(rsps.GET, f"{BASE_URL}/api/companies/co1/secrets", json={"secrets": [{"id": "s1", "name": "API_KEY", "createdAt": "2026-03-30T02:00:00.000Z"}]})
    rsps.add(rsps.GET, f"{BASE_URL}/api/companies/co1/secrets", json={"secrets": []})

    goal_list = run_cli(runner, "goal", "list", "--company", "co1")
    assert goal_list.exit_code == 0
    assert "Launch" in goal_list.output

    goal_empty = run_cli(runner, "goal", "list", "--company", "co1")
    assert goal_empty.exit_code == 0
    assert "No goals found." in goal_empty.output

    goal_create = run_cli(runner, "goal", "create", "--company", "co1", "--title", "Scale", "--description", "Grow")
    assert goal_create.exit_code == 0
    assert request_json(rsps.calls[2]) == {"title": "Scale", "description": "Grow"}

    goal_get = run_cli(runner, "goal", "get", "g1")
    assert goal_get.exit_code == 0
    assert '"id": "g1"' in goal_get.output

    goal_update = run_cli(runner, "goal", "update", "g1", "--title", "Expand", "--description", "New", "--status", "done")
    assert goal_update.exit_code == 0
    assert request_json(rsps.calls[4]) == {"title": "Expand", "description": "New", "status": "done"}

    goal_delete = run_cli(runner, "goal", "delete", "g1", input="y\n")
    assert goal_delete.exit_code == 0
    assert "Deleted goal g1" in goal_delete.output

    issue_list = run_cli(runner, "issue", "list", "--company", "co1")
    assert issue_list.exit_code == 0
    assert "Ship" in issue_list.output
    assert "u1" in issue_list.output

    issue_empty = run_cli(runner, "issue", "list", "--company", "co1")
    assert issue_empty.exit_code == 0
    assert "No issues found." in issue_empty.output

    issue_create = run_cli(runner, "issue", "create", "--company", "co1", "--title", "Test", "--description", "Desc", "--goal", "g1")
    assert issue_create.exit_code == 0
    assert request_json(rsps.calls[8]) == {"title": "Test", "description": "Desc", "goalId": "g1"}

    issue_update = run_cli(runner, "issue", "update", "i1", "--title", "Ship 2", "--description", "Done", "--status", "done", "--assignee", "a5")
    assert issue_update.exit_code == 0
    assert request_json(rsps.calls[9]) == {
        "title": "Ship 2",
        "description": "Done",
        "status": "done",
        "assigneeAgentId": "a5",
    }

    issue_delete = run_cli(runner, "issue", "delete", "i1", input="y\n")
    assert issue_delete.exit_code == 0

    issue_get = run_cli(runner, "issue", "get", "i1")
    assert issue_get.exit_code == 0
    assert '"title": "Ship"' in issue_get.output

    approval_list = run_cli(runner, "approval", "list", "--company", "co1")
    assert approval_list.exit_code == 0
    assert "budget" in approval_list.output

    approval_empty = run_cli(runner, "approval", "list", "--company", "co1")
    assert approval_empty.exit_code == 0
    assert "No approvals found." in approval_empty.output

    approval_approve = run_cli(runner, "approval", "approve", "ap1", "--json")
    assert approval_approve.exit_code == 0
    assert json.loads(approval_approve.output) == {"ok": True}

    approval_reject = run_cli(runner, "approval", "reject", "ap1", "--json")
    assert approval_reject.exit_code == 0
    assert json.loads(approval_reject.output) == {"ok": True}

    plugin_list = run_cli(runner, "plugin", "list")
    assert plugin_list.exit_code == 0
    assert "clock" in plugin_list.output

    plugin_empty = run_cli(runner, "plugin", "list")
    assert plugin_empty.exit_code == 0
    assert "No plugins installed." in plugin_empty.output

    examples = run_cli(runner, "plugin", "examples")
    assert examples.exit_code == 0
    assert "starter" in examples.output

    examples_empty = run_cli(runner, "plugin", "examples")
    assert examples_empty.exit_code == 0
    assert "No example plugins found." in examples_empty.output

    plugin_install = run_cli(runner, "plugin", "install", "https://example.com/plugin.git", "--json")
    assert plugin_install.exit_code == 0
    assert request_json(rsps.calls[20]) == {"url": "https://example.com/plugin.git"}

    heartbeat_list = run_cli(runner, "heartbeat", "list", "--company", "co1", "--limit", "1")
    assert heartbeat_list.exit_code == 0
    assert "run-succ" in heartbeat_list.output or "run-suc" in heartbeat_list.output
    assert "daily" in heartbeat_list.output

    heartbeat_empty = run_cli(runner, "heartbeat", "list", "--company", "co1")
    assert heartbeat_empty.exit_code == 0
    assert "No heartbeat runs found." in heartbeat_empty.output

    secret_list = run_cli(runner, "secret", "list", "--company", "co1")
    assert secret_list.exit_code == 0
    assert "API_KEY" in secret_list.output

    secret_empty = run_cli(runner, "secret", "list", "--company", "co1")
    assert secret_empty.exit_code == 0
    assert "No secrets found." in secret_empty.output
    assert "local_trusted mode" in secret_empty.output


@rsps.activate
def test_project_commands_cover_archive_and_update_validation(runner):
    rsps.add(rsps.GET, f"{BASE_URL}/api/companies/co1/projects", json={"projects": [{"id": "p1", "name": "Roadmap", "status": "planned", "description": "Quarter"}]})
    rsps.add(rsps.GET, f"{BASE_URL}/api/companies/co1/projects", json={"projects": []})
    rsps.add(rsps.POST, f"{BASE_URL}/api/companies/co1/projects", json={"id": "p2", "name": "Platform"}, status=201)
    rsps.add(rsps.GET, f"{BASE_URL}/api/projects/p1", json={"id": "p1", "name": "Roadmap"})
    rsps.add(rsps.PATCH, f"{BASE_URL}/api/projects/p1", json={"id": "p1", "name": "Platform"})
    rsps.add(rsps.PATCH, f"{BASE_URL}/api/projects/p1", json={"id": "p1", "archivedAt": "2026-03-30T00:00:00.000Z"})
    rsps.add(rsps.DELETE, f"{BASE_URL}/api/projects/p1", status=204)
    rsps.add(rsps.PATCH, f"{BASE_URL}/api/projects/p1", json={"id": "p1", "archivedAt": "2026-03-30T00:00:00.000Z"})
    rsps.add(rsps.PATCH, f"{BASE_URL}/api/projects/p1", json={"id": "p1", "archivedAt": None})

    list_result = run_cli(runner, "project", "list", "--company", "co1")
    assert list_result.exit_code == 0
    assert "Roadmap" in list_result.output

    empty_result = run_cli(runner, "project", "list", "--company", "co1")
    assert empty_result.exit_code == 0
    assert "No projects found." in empty_result.output

    create_result = run_cli(
        runner,
        "project",
        "create",
        "--company",
        "co1",
        "--name",
        "Platform",
        "--description",
        "Build it",
        "--goal",
        "g1",
        "--lead",
        "a1",
        "--color",
        "#123456",
    )
    assert create_result.exit_code == 0
    assert request_json(rsps.calls[2]) == {
        "name": "Platform",
        "description": "Build it",
        "goalId": "g1",
        "leadAgentId": "a1",
        "color": "#123456",
    }

    get_result = run_cli(runner, "project", "get", "p1")
    assert get_result.exit_code == 0
    assert '"name": "Roadmap"' in get_result.output

    no_fields = run_cli(runner, "project", "update", "p1")
    assert no_fields.exit_code == 1
    assert "No fields to update" in no_fields.output

    update_result = run_cli(
        runner,
        "project",
        "update",
        "p1",
        "--name",
        "Platform",
        "--description",
        "Fresh",
        "--status",
        "paused",
        "--goal",
        "g2",
        "--lead",
        "a2",
    )
    assert update_result.exit_code == 0
    assert request_json(rsps.calls[4]) == {
        "name": "Platform",
        "description": "Fresh",
        "status": "paused",
        "goalId": "g2",
        "leadAgentId": "a2",
    }

    archive_delete = run_cli(runner, "project", "delete", "p1", "--yes")
    assert archive_delete.exit_code == 0
    archive_payload = request_json(rsps.calls[5])
    assert "archivedAt" in archive_payload

    force_delete = run_cli(runner, "project", "delete", "p1", "--yes", "--force")
    assert force_delete.exit_code == 0
    assert "Deleted project p1" in force_delete.output

    archive_result = run_cli(runner, "project", "archive", "p1")
    assert archive_result.exit_code == 0
    assert "Archived project p1" in archive_result.output

    unarchive_result = run_cli(runner, "project", "unarchive", "p1")
    assert unarchive_result.exit_code == 0
    assert "Unarchived project p1" in unarchive_result.output


@rsps.activate
def test_routine_commands_cover_tables_validation_and_triggers(runner):
    rsps.add(rsps.GET, f"{BASE_URL}/api/companies/co1/routines", json={"routines": [{
        "id": "r1",
        "title": "Daily sync",
        "status": "active",
        "concurrencyPolicy": "coalesce_if_active",
        "assigneeAgentId": "a1",
    }]})
    rsps.add(rsps.GET, f"{BASE_URL}/api/companies/co1/routines", json={"routines": []})
    rsps.add(rsps.POST, f"{BASE_URL}/api/companies/co1/routines", json={"id": "r2", "title": "Reporter"}, status=201)
    rsps.add(rsps.GET, f"{BASE_URL}/api/routines/r1", json={"id": "r1", "title": "Daily sync"})
    rsps.add(rsps.PATCH, f"{BASE_URL}/api/routines/r1", json={"id": "r1", "title": "Updated"})
    rsps.add(rsps.PATCH, f"{BASE_URL}/api/routines/r1", json={"id": "r1", "status": "archived"})
    rsps.add(rsps.POST, f"{BASE_URL}/api/routines/r1/triggers", json={"trigger": {
        "id": "t1",
        "kind": "schedule",
        "nextRunAt": "2026-03-31T09:00:00.000Z",
    }})
    rsps.add(rsps.POST, f"{BASE_URL}/api/routines/r1/triggers", json={"id": "t2", "kind": "webhook"})
    rsps.add(rsps.POST, f"{BASE_URL}/api/routines/r1/run", json={"runId": "run-1"})
    rsps.add(rsps.GET, f"{BASE_URL}/api/routines/r1/runs", json={"runs": [{
        "id": "run-1",
        "status": "success",
        "source": "manual",
        "triggeredAt": "2026-03-30T03:00:00.000Z",
        "linkedIssueId": "i1",
    }]})
    rsps.add(rsps.GET, f"{BASE_URL}/api/routines/r1", json={"triggers": []})
    rsps.add(rsps.GET, f"{BASE_URL}/api/routines/r1", json={"triggers": [{
        "id": "t1",
        "kind": "schedule",
        "enabled": True,
        "cronExpression": "0 9 * * *",
        "nextRunAt": "2026-03-31T09:00:00.000Z",
    }, {
        "id": "t2",
        "kind": "webhook",
        "enabled": False,
        "signingMode": "hmac",
        "nextRunAt": None,
    }]})

    list_result = run_cli(runner, "routine", "list", "--company", "co1")
    assert list_result.exit_code == 0
    assert "Daily sync" in list_result.output

    empty_result = run_cli(runner, "routine", "list", "--company", "co1")
    assert empty_result.exit_code == 0
    assert "No routines found." in empty_result.output

    create_result = run_cli(
        runner,
        "routine",
        "create",
        "--company",
        "co1",
        "--project",
        "p1",
        "--name",
        "Reporter",
        "--assignee",
        "a1",
        "--description",
        "Send report",
        "--goal",
        "g1",
        "--priority",
        "high",
        "--status",
        "paused",
        "--concurrency",
        "always_enqueue",
        "--catchup",
        "enqueue_missed_with_cap",
    )
    assert create_result.exit_code == 0
    assert request_json(rsps.calls[2]) == {
        "title": "Reporter",
        "projectId": "p1",
        "assigneeAgentId": "a1",
        "priority": "high",
        "status": "paused",
        "concurrencyPolicy": "always_enqueue",
        "catchUpPolicy": "enqueue_missed_with_cap",
        "description": "Send report",
        "goalId": "g1",
    }

    get_result = run_cli(runner, "routine", "get", "r1")
    assert get_result.exit_code == 0
    assert '"title": "Daily sync"' in get_result.output

    no_fields = run_cli(runner, "routine", "update", "r1")
    assert no_fields.exit_code == 1
    assert "No fields to update." in no_fields.output

    update_result = run_cli(
        runner,
        "routine",
        "update",
        "r1",
        "--name",
        "Updated",
        "--description",
        "Refined",
        "--status",
        "paused",
        "--assignee",
        "a2",
        "--priority",
        "critical",
        "--concurrency",
        "skip_if_active",
    )
    assert update_result.exit_code == 0
    assert request_json(rsps.calls[4]) == {
        "title": "Updated",
        "description": "Refined",
        "status": "paused",
        "assigneeAgentId": "a2",
        "priority": "critical",
        "concurrencyPolicy": "skip_if_active",
    }

    archive_result = run_cli(runner, "routine", "archive", "r1", input="y\n")
    assert archive_result.exit_code == 0
    assert "Archived routine r1" in archive_result.output

    missing_cron = run_cli(runner, "routine", "trigger-add", "r1", "--kind", "schedule")
    assert missing_cron.exit_code == 1
    assert "--cron is required for schedule triggers" in missing_cron.output

    schedule_trigger = run_cli(
        runner,
        "routine",
        "trigger-add",
        "r1",
        "--kind",
        "schedule",
        "--cron",
        "0 9 * * *",
        "--timezone",
        "America/Chicago",
        "--label",
        "Morning",
    )
    assert schedule_trigger.exit_code == 0
    assert "Added schedule trigger" in schedule_trigger.output
    assert request_json(rsps.calls[6]) == {
        "kind": "schedule",
        "label": "Morning",
        "cronExpression": "0 9 * * *",
        "timezone": "America/Chicago",
    }

    webhook_trigger = run_cli(runner, "routine", "trigger-add", "r1", "--kind", "webhook", "--json")
    assert webhook_trigger.exit_code == 0
    assert json.loads(webhook_trigger.output)["id"] == "t2"

    run_result = run_cli(runner, "routine", "run", "r1")
    assert run_result.exit_code == 0
    assert "Triggered routine r1" in run_result.output

    runs_result = run_cli(runner, "routine", "runs", "r1")
    assert runs_result.exit_code == 0
    assert "success" in runs_result.output
    assert "i1" in runs_result.output

    triggers_empty = run_cli(runner, "routine", "triggers", "r1")
    assert triggers_empty.exit_code == 0
    assert "No triggers configured." in triggers_empty.output

    triggers_result = run_cli(runner, "routine", "triggers", "r1")
    assert triggers_result.exit_code == 0
    assert "0 9 * * *" in triggers_result.output
    assert "hmac" in triggers_result.output


@rsps.activate
def test_project_json_paths_and_delete_confirmation(runner):
    rsps.add(rsps.GET, f"{BASE_URL}/api/companies/co1/projects", json={"projects": [{"id": "p1", "name": "Roadmap"}]})
    rsps.add(rsps.POST, f"{BASE_URL}/api/companies/co1/projects", json={"id": "p2", "name": "Platform"}, status=201)
    rsps.add(rsps.GET, f"{BASE_URL}/api/projects/p1", json={"id": "p1", "name": "Roadmap"})
    rsps.add(rsps.PATCH, f"{BASE_URL}/api/projects/p1", json={"id": "p1", "name": "Updated"})
    rsps.add(rsps.PATCH, f"{BASE_URL}/api/projects/p1", json={"id": "p1", "archivedAt": "2026-03-31T00:00:00.000Z"})
    rsps.add(rsps.PATCH, f"{BASE_URL}/api/projects/p1", json={"id": "p1", "archivedAt": "2026-03-31T00:00:00.000Z"})
    rsps.add(rsps.PATCH, f"{BASE_URL}/api/projects/p1", json={"id": "p1", "archivedAt": None})

    list_result = run_cli(runner, "project", "list", "--company", "co1", "--json")
    assert list_result.exit_code == 0
    assert json.loads(list_result.output)[0]["id"] == "p1"

    create_result = run_cli(runner, "project", "create", "--company", "co1", "--name", "Platform", "--json")
    assert create_result.exit_code == 0
    assert json.loads(create_result.output)["id"] == "p2"

    get_result = run_cli(runner, "project", "get", "p1", "--json")
    assert get_result.exit_code == 0
    assert json.loads(get_result.output)["name"] == "Roadmap"

    update_result = run_cli(runner, "project", "update", "p1", "--name", "Updated", "--json")
    assert update_result.exit_code == 0
    assert json.loads(update_result.output)["name"] == "Updated"

    delete_result = run_cli(runner, "project", "delete", "p1", input="y\n")
    assert delete_result.exit_code == 0
    assert "Archived project p1" in delete_result.output

    archive_result = run_cli(runner, "project", "archive", "p1", "--json")
    assert archive_result.exit_code == 0
    assert json.loads(archive_result.output)["id"] == "p1"

    unarchive_result = run_cli(runner, "project", "unarchive", "p1", "--json")
    assert unarchive_result.exit_code == 0
    assert json.loads(unarchive_result.output)["archivedAt"] is None


@rsps.activate
def test_routine_json_paths_and_empty_runs(runner):
    rsps.add(rsps.GET, f"{BASE_URL}/api/companies/co1/routines", json={"routines": [{"id": "r1", "title": "Daily sync"}]})
    rsps.add(rsps.POST, f"{BASE_URL}/api/companies/co1/routines", json={"id": "r2", "title": "Reporter"}, status=201)
    rsps.add(rsps.GET, f"{BASE_URL}/api/routines/r1", json={"id": "r1", "title": "Daily sync"})
    rsps.add(rsps.PATCH, f"{BASE_URL}/api/routines/r1", json={"id": "r1", "title": "Updated"})
    rsps.add(rsps.POST, f"{BASE_URL}/api/routines/r1/run", json={"runId": "run-1"})
    rsps.add(rsps.GET, f"{BASE_URL}/api/routines/r1/runs", json={"runs": [{"id": "run-1", "status": "success"}]})
    rsps.add(rsps.GET, f"{BASE_URL}/api/routines/r1/runs", json={"runs": []})
    rsps.add(rsps.GET, f"{BASE_URL}/api/routines/r1", json={"triggers": [{"id": "t1", "kind": "api"}]})

    list_result = run_cli(runner, "routine", "list", "--company", "co1", "--json")
    assert list_result.exit_code == 0
    assert json.loads(list_result.output)[0]["id"] == "r1"

    create_result = run_cli(
        runner,
        "routine",
        "create",
        "--company",
        "co1",
        "--project",
        "p1",
        "--name",
        "Reporter",
        "--assignee",
        "a1",
        "--json",
    )
    assert create_result.exit_code == 0
    assert json.loads(create_result.output)["id"] == "r2"

    get_result = run_cli(runner, "routine", "get", "r1", "--json")
    assert get_result.exit_code == 0
    assert json.loads(get_result.output)["title"] == "Daily sync"

    update_result = run_cli(runner, "routine", "update", "r1", "--name", "Updated", "--json")
    assert update_result.exit_code == 0
    assert json.loads(update_result.output)["title"] == "Updated"

    run_result = run_cli(runner, "routine", "run", "r1", "--json")
    assert run_result.exit_code == 0
    assert json.loads(run_result.output)["runId"] == "run-1"

    runs_json_result = run_cli(runner, "routine", "runs", "r1", "--json")
    assert runs_json_result.exit_code == 0
    assert json.loads(runs_json_result.output)[0]["id"] == "run-1"

    runs_empty_result = run_cli(runner, "routine", "runs", "r1")
    assert runs_empty_result.exit_code == 0
    assert "No runs found." in runs_empty_result.output

    triggers_result = run_cli(runner, "routine", "triggers", "r1", "--json")
    assert triggers_result.exit_code == 0
    assert json.loads(triggers_result.output)[0]["kind"] == "api"


ERROR_CASES = [
    (["company", "list"], rsps.GET, f"{BASE_URL}/api/companies"),
    (["company", "create", "--name", "Acme"], rsps.POST, f"{BASE_URL}/api/companies"),
    (["company", "get", "c1"], rsps.GET, f"{BASE_URL}/api/companies/c1"),
    (["company", "update", "c1", "--name", "Renamed"], rsps.PATCH, f"{BASE_URL}/api/companies/c1"),
    (["company", "delete", "c1", "--yes", "--force"], rsps.DELETE, f"{BASE_URL}/api/companies/c1"),
    (["company", "archive", "c1"], rsps.POST, f"{BASE_URL}/api/companies/c1/archive"),
    (["company", "unarchive", "c1"], rsps.PATCH, f"{BASE_URL}/api/companies/c1"),
    (["agent", "list", "--company", "co1"], rsps.GET, f"{BASE_URL}/api/companies/co1/agents"),
    (["agent", "create", "--company", "co1", "--name", "Alice"], rsps.POST, f"{BASE_URL}/api/companies/co1/agents"),
    (["agent", "get", "a1"], rsps.GET, f"{BASE_URL}/api/agents/a1"),
    (["agent", "update", "a1", "--name", "Alice"], rsps.PATCH, f"{BASE_URL}/api/agents/a1"),
    (["agent", "delete", "a1", "--yes"], rsps.DELETE, f"{BASE_URL}/api/agents/a1"),
    (["agent", "wakeup", "a1"], rsps.POST, f"{BASE_URL}/api/agents/a1/wakeup"),
    (["agent", "set-instructions", "a1", "--path", "/tmp/AGENTS.md"], rsps.PATCH, f"{BASE_URL}/api/agents/a1/instructions-path"),
    (["goal", "list", "--company", "co1"], rsps.GET, f"{BASE_URL}/api/companies/co1/goals"),
    (["goal", "create", "--company", "co1", "--title", "Launch"], rsps.POST, f"{BASE_URL}/api/companies/co1/goals"),
    (["goal", "update", "g1", "--title", "Launch"], rsps.PATCH, f"{BASE_URL}/api/goals/g1"),
    (["goal", "delete", "g1", "--yes"], rsps.DELETE, f"{BASE_URL}/api/goals/g1"),
    (["goal", "get", "g1"], rsps.GET, f"{BASE_URL}/api/goals/g1"),
    (["issue", "list", "--company", "co1"], rsps.GET, f"{BASE_URL}/api/companies/co1/issues"),
    (["issue", "create", "--company", "co1", "--title", "Bug"], rsps.POST, f"{BASE_URL}/api/companies/co1/issues"),
    (["issue", "update", "i1", "--title", "Bug"], rsps.PATCH, f"{BASE_URL}/api/issues/i1"),
    (["issue", "delete", "i1", "--yes"], rsps.DELETE, f"{BASE_URL}/api/issues/i1"),
    (["issue", "get", "i1"], rsps.GET, f"{BASE_URL}/api/issues/i1"),
    (["approval", "list", "--company", "co1"], rsps.GET, f"{BASE_URL}/api/companies/co1/approvals"),
    (["approval", "approve", "ap1"], rsps.POST, f"{BASE_URL}/api/approvals/ap1/approve"),
    (["approval", "reject", "ap1"], rsps.POST, f"{BASE_URL}/api/approvals/ap1/reject"),
    (["plugin", "list"], rsps.GET, f"{BASE_URL}/api/plugins"),
    (["plugin", "examples"], rsps.GET, f"{BASE_URL}/api/plugins/examples"),
    (["plugin", "install", "clock"], rsps.POST, f"{BASE_URL}/api/plugins/install"),
    (["project", "list", "--company", "co1"], rsps.GET, f"{BASE_URL}/api/companies/co1/projects"),
    (["project", "create", "--company", "co1", "--name", "Roadmap"], rsps.POST, f"{BASE_URL}/api/companies/co1/projects"),
    (["project", "get", "p1"], rsps.GET, f"{BASE_URL}/api/projects/p1"),
    (["project", "update", "p1", "--name", "Roadmap"], rsps.PATCH, f"{BASE_URL}/api/projects/p1"),
    (["project", "delete", "p1", "--yes", "--force"], rsps.DELETE, f"{BASE_URL}/api/projects/p1"),
    (["project", "archive", "p1"], rsps.PATCH, f"{BASE_URL}/api/projects/p1"),
    (["project", "unarchive", "p1"], rsps.PATCH, f"{BASE_URL}/api/projects/p1"),
    (["routine", "list", "--company", "co1"], rsps.GET, f"{BASE_URL}/api/companies/co1/routines"),
    (["routine", "create", "--company", "co1", "--project", "p1", "--name", "Daily", "--assignee", "a1"], rsps.POST, f"{BASE_URL}/api/companies/co1/routines"),
    (["routine", "get", "r1"], rsps.GET, f"{BASE_URL}/api/routines/r1"),
    (["routine", "update", "r1", "--name", "Daily"], rsps.PATCH, f"{BASE_URL}/api/routines/r1"),
    (["routine", "archive", "r1", "--yes"], rsps.PATCH, f"{BASE_URL}/api/routines/r1"),
    (["routine", "trigger-add", "r1", "--kind", "webhook"], rsps.POST, f"{BASE_URL}/api/routines/r1/triggers"),
    (["routine", "run", "r1"], rsps.POST, f"{BASE_URL}/api/routines/r1/run"),
    (["routine", "runs", "r1"], rsps.GET, f"{BASE_URL}/api/routines/r1/runs"),
    (["routine", "triggers", "r1"], rsps.GET, f"{BASE_URL}/api/routines/r1"),
    (["heartbeat", "list", "--company", "co1"], rsps.GET, f"{BASE_URL}/api/companies/co1/heartbeat-runs"),
    (["secret", "list", "--company", "co1"], rsps.GET, f"{BASE_URL}/api/companies/co1/secrets"),
]


@pytest.mark.parametrize(("args", "method", "url"), ERROR_CASES)
@rsps.activate
def test_commands_render_paperclip_errors(runner, args, method, url):
    rsps.add(method, url, json={"error": "broken"}, status=500)

    result = run_cli(runner, *args)

    assert result.exit_code == 1
    assert "broken" in result.output
