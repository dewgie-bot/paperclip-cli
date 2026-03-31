from __future__ import annotations

import json

import responses as rsps

from .cli_test_helpers import BASE_URL, request_json, run_cli


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
